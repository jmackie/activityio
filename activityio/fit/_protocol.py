#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Implement the Flexible and Interoperable data Transfer (FIT) protocol.

TODO:
-----
    + field components
    + accumulators

"""
from contextlib import contextmanager
from struct import unpack

from activityio.fit._profile import (
    BASE_TYPE_BYTE, BASE_TYPES, BASE_TYPES_BY_NAME,
    MESSAGE_TYPES, TYPES_INFO, GLOBAL_MESG_NUMS)
from activityio._util.exceptions import ActivityIOError, InvalidFileError


EMPTY_DICT = {}    # single instance to save some memory


class FitFile:
    """A file-like object specific to *.fit files.

    Attributes
    ----------
    bytes_left : int
        Bytes left to be read in the file. Initialised to its proper value
        when the file header is read.
    local_messages : dict
        Unique definition messages, associated with an integer index, that
        have been parsed from the file.
    profile_version, protocol_version : float
        File version information taken from the file header.
    reader : _io.BufferedReader
        Open file to be read.
    """
    def __init__(self, reader):
        """Initialise a new FitFile instance.

        Parameters
        ----------
        reader : _io.BufferedReader
            Returned value of the ``open`` builtin.
        """
        self.reader = reader
        self.bytes_left = 0
        self.local_messages = {}   # i.e. definition messages, by number

    def read(self, size):
        """Read from an open file, keeping track of bytes left."""
        self.bytes_left -= size
        return self.reader.read(size)

    def skip_bytes(self, size):
        """Seek an open file, keeping track of bytes left."""
        self.bytes_left -= size
        self.reader.seek(size, 1)   # from current position

    def set_version_info(self, version_info):
        """Decode version info the same way the FIT SDK does.

        Version info is a list containing a byte and a short unpacked from the
        file header.
        """
        prot, prof = version_info
        self.protocol_version = float(
            '{:.0f}.{:.0f}'.format(prot >> 4, prot & ((1 << 4) - 1)))
        self.profile_version = float(
            '{:.0f}.{:.0f}'.format(prof / 100, prof % 100))


class FitMessageHeader:
    """From the FIT SDK release 20.03.00

    The record header is a one byte bit field. There are actually two types of
    record header: normal header and compressed timestamp header. The header
    type is indicated in the most significant bit (msb) of the record header.
    The normal header identifies whether the record is a definition or data
    message, and identifies the local message type. A compressed timestamp
    header is a special compressed header that may also be used with some
    local data messages to allow a compressed time format.
    """
    __slots__ = ('_message_cls', 'local_message_type', 'time_offset')

    def message_cls(self, fitfile):
        return self._message_cls(self, fitfile)   # partial'd, kinda


class NormalHeader(FitMessageHeader):
    """From the FIT SDK release 20.03.00

    Normal Header Bit Field Description
    -----------------------------------

    =====  =============  ========================
    Bit        Value      Description
    =====  =============  ========================
      7          0        Normal header
      6        0 or 1     Message type:
                            1: definition message
                            2: data message
      5     0 (default)   Message type specific
      4          0        Reserved
     0-3        0-15      Local message type
    =====  =============  ========================
    """
    __slots__ = tuple()

    def __init__(self, header_byte):
        self._message_cls = (
            DefinitionMessage if bool(header_byte & 0x40) else DataMessage)
        # `local_message_type` is the key (int) for the definition
        # associated with this message
        self.local_message_type = header_byte & 0xF    # bits 0-3
        self.time_offset = None


class CompressedTimestampHeader(FitMessageHeader):
    """From the FIT SDK release 20.03.00

    Compressed Timestamp Header Description
    ---------------------------------------

    The compressed timestamp header is a special form of record header that
    allows some timestamp information to be placed within the record header,
    rather than within the record content. In applicable use cases, this
    allows data to be recorded without the need of a 4 byte timestamp in every
    data record.

    =====  =============  ========================
    Bit        Value      Description
    =====  =============  ========================
      7          1        Compressed timestamp
     5-6        0-3       Local message type
     0-4        0-31      Time offset (seconds)
    =====  =============  ========================

    NOTE: this type of record header is used for a *data message only*.
    """
    __slots__ = tuple()

    def __init__(self, header_byte):
        self._message_cls = DataMessage
        self.local_message_type = (header_byte >> 5) & 0x3   # bits 5-6
        self.time_offset = header_byte & 0x1F                # bits 0-4


class DefinitionMessage:
    """From the FIT SDK release 20.03.00

    The definition message is used to create an association between the local
    message type contained in the record header, and a Global Message Number
    that relates to the global FIT message.


    Definition Message Contents
    ---------------------------

    ======  =======================  =============  ===========================
    Byte    Description                 Length      Value
    (bytes)
    ======  =======================  =============  ===========================
      0     Reserved                       1         0
      1     Architecture                   1         0 or 1
                                                       0: little endian
                                                       1: big endian
     2-3    Global message number          2         Unique to each message
      4     Fields                         1         Number of fields in the
                                                     data message
      5     Field definition(s)            3         See table below
     ...                              (per field)
    ======  =======================  =============  ===========================

    """
    __slots__ = ('header', 'name', 'type', 'field_defs')

    def __init__(self, header, fitfile):
        self.header = header

        __, big_endian = unpack('<2B', fitfile.read(2))   # ignore reserved
        endian = '>' if big_endian else '<'

        global_mesg_num, field_count = unpack(endian+'HB', fitfile.read(3))
        self.name = GLOBAL_MESG_NUMS.get(global_mesg_num, 'unknown')
        self.type = MESSAGE_TYPES.get(self.name, EMPTY_DICT)

        self.field_defs = [FieldDefinition(fitfile, self.type, endian)
                           for _ in range(field_count)]

        # Save this local message.
        fitfile.local_messages[header.local_message_type] = self


class DataMessage:
    """The useful part of a *.fit file.

    The header identifies an associated definition message. We pull the
    field definitions from that message and use them to parse data from
    the fitfile.
    """
    __slots__ = ('header', 'name', 'field_defs', 'field_values')

    def __init__(self, header, fitfile):
        self.header = header

        def_message = fitfile.local_messages.get(header.local_message_type)
        if def_message is None:
            raise MessageHeaderError('invalid local message type (%d)' %
                                     header.local_message_type)

        self.name = def_message.name

        # Not assigning to self yet as we need to filter out the
        # invalid definitions and values.
        field_defs = def_message.field_defs
        field_values = [field.read(fitfile) for field in field_defs]

        # Invalid values (tested by .parse()) are returned as None.
        valid = [i for i, val in enumerate(field_values) if val is not None]
        # Get rid.
        self.field_defs = [field_defs[i] for i in valid]
        self.field_values = [field_values[i] for i in valid]

    def decode(self):
        """Decode like the FitCSVTool.

        Returns
        -------
        [(name, value, units), (name, value, units), ...]
        """
        defs_values = zip(self.field_defs, self.field_values)
        first_parse = [self._extract(*data) for data in defs_values]

        has_subfields = any(field_def.is_dynamic
                            for field_def in self.field_defs)

        if has_subfields:
            return self._resolve_subfields(first_parse)
        else:
            return first_parse

    @staticmethod
    def _extract(field_def, field_value):
        """Replicating the FitCSVTool output.

        Spits out a (name, value, units) tuple.
        """
        name = field_def.name

        if isinstance(field_value, bytes):
            value = field_value
        elif name in TYPES_INFO:
            value = TYPES_INFO[name].get(field_value, field_value)
        else:
            value = apply_scale_offset(field_def, field_value)

        units = field_def.data.get('units', '')

        return name, value, units

    def _resolve_subfields(self, first_parse):
        """Go back over parsed data to resolve dynamic fields.

        Note: record messages don't have subfields.
        """
        field_def_names = tuple(field_def.name
                                for field_def in self.field_defs)
        bad_messages = []

        # Need lists here for mutability.
        names, values, units = (list(column) for column in zip(*first_parse))

        for i, field in enumerate(zip(self.field_defs, values)):

            if is_dynamic(*field):    # also the value
                field_def, raw = field
                subfields = field_def.data['subfields']

                # Find the name of the field definition from which
                # we should to retrieve the parsed value.
                ref_field_name = single_from(subf['ref_field_name']
                                             for subf in subfields.values())

                try:
                    # The value that tells us which subfield to use.
                    ref_value = values[field_def_names.index(ref_field_name)]
                except ValueError:
                    bad_messages.append(i)   # scrap this message
                    continue

                try:
                    # They key to the matching subfield.
                    subfield_key, = (key for key, value in subfields.items()
                                     if ref_value in value['ref_field_value'])
                except ValueError:
                    bad_messages.append(i)   # scrap this message
                    continue

                subfield_match = subfields[subfield_key]

                new_name = subfield_match['field_name']
                new_base_type = BASE_TYPES_BY_NAME.get(new_name, BASE_TYPE_BYTE)
                field_def.update(name=new_name, base_type=new_base_type)

                names[i] = new_name
                values[i] = field_def.read(raw=raw)
                units[i] = subfield_match.get('units', '')

        return list(data for i, data in enumerate(zip(names, values, units))
                    if i not in bad_messages)


class FieldDefinition:
    """From the FIT SDK release 20.03.00

    Field Definition Contents
    -------------------------

    ======  =================  ===============================================
     Byte    Name               Description
    ======  =================  ===============================================
      0     Field definition   Defined in the gloabl FIT profile for the
            number             specified FIT message.
      1     Size               Size (in bytes) of the specified FIT message's
                               field.
      2     Base type          Base type of the specified FIT message's field.
    ======  =================  ===============================================

    """
    __slots__ = ('size', 'base_type', 'data', 'is_dynamic', 'name', 'endian')

    def __init__(self, fitfile, message_type, endian):
        # NOTE: reading single bytes, so no need to apply endianness here.
        def_num, self.size, base_type_num = unpack('<3B', fitfile.read(3))
        self.base_type = BASE_TYPES.get(base_type_num, BASE_TYPE_BYTE)
        self.data = message_type.get(def_num, EMPTY_DICT)
        self.is_dynamic = 'subfields' in self.data
        self.name = self.data.get('field_name', 'unknown')
        self.endian = endian   # for reference

    @property
    def n_bytes(self):
        return self.size // self.base_type.size

    @property
    def fmt(self):
        """Format for struct.unpacking."""
        return '{0.endian}{0.n_bytes}{0.base_type.fmt}'.format(self)

    def read(self, fitfile=None, raw=None):
        """Parse data from this field definition.

        Data is either read directly from the file or an existing buffer. If
        this is a dynamic field definition (i.e. has subfields) and we're
        reading from a file, raw bytes are returned.
        """

        # Dynamic fields need to be unpacked later.
        dont_unpack = self.is_dynamic and raw is None

        if raw is None:
            raw = fitfile.read(self.size)

        if dont_unpack:
            return raw
        else:
            value, *ignore = unpack(self.fmt, raw)  # TODO: check/improve this
            return self.base_type.parse(value)      # checks validity

    def update(self, **kwargs):
        """Update instance attributes from kwargs."""
        for name, value in kwargs.items():
            setattr(self, name, value)


class FileHeaderError(ActivityIOError):
    pass


class MessageHeaderError(ActivityIOError):
    pass


def read_file_header(fitfile):
    """Read the *.fit file header, modifying `fitfile` in place.

    Attributes added to `fitfile`:
        + version info (protocol_version and profile_version)
        + bytes_left

    The file object is also advanced to the start of the first message header.
    """
    header_data = fitfile.read(12)

    if header_data[8:12] != b'.FIT':
        raise InvalidFileError("this doesn't look like a fit file!")

    # Larger fields are explicitly little endian from SDK.
    header_size, *version_info, data_size = unpack('<2BHI4x', header_data)
    fitfile.set_version_info(version_info)

    extra_header = header_size - 12
    if extra_header:
        if extra_header < 2:
            raise FileHeaderError('irregular file header size')

        fitfile.skip_bytes(extra_header)

    fitfile.bytes_left = data_size


def read_fit_message(fitfile):
    """Parse a message (header + contents)."""
    header_byte, = unpack('<B', fitfile.read(1))
    # A value of 0 in bit 7 indicates that this is a normal header.
    header_cls = (CompressedTimestampHeader if (header_byte & 0x80) else
                  NormalHeader)
    header = header_cls(header_byte)

    message = header.message_cls(fitfile)

    return message


@contextmanager
def open_fit(file_path):
    reader = open(file_path, 'rb')
    yield FitFile(reader)
    reader.close()


def is_dynamic(field_def, field_value=None):
    """Implements two checks for a dynamic field defintion."""
    if field_value is not None:
        return field_def.is_dynamic and isinstance(field_value, bytes)
    else:
        return field_def.is_dynamic


def apply_scale_offset(field_def, field_value):
    """From the FIT SDK release 20.03.00

    The FIT SDK supports applying a scale or offset to binary fields. This
    allows efficient representation of values within a particular range and
    provides a convenient method for representing floating point values in
    integer systems. A scale or offset may be specified in the FIT profile for
    binary fields (sint/uint etc.) only. When specified, the binary quantity
    is divided by the scale factor and then the offset is subtracted, yielding
    a floating point quantity.
    """
    scale = field_def.data.get('scale', 1)
    offset = field_def.data.get('offset', 0)
    return field_value / scale - offset


def which_one(iterable):
    """Index of the first True value in an iterable."""
    it = enumerate(iterable)
    i, x = next(it)
    while not x:
        i, x = next(it)
    return i


def single_from(iterable):
    """Check that an iterable contains one unique value, and return it."""
    unique_vals = set(iterable)
    if len(unique_vals) != 1:
        raise ValueError('multiple unique values found')
    return unique_vals.pop()


def gen_fit_messages(file_path):
    """Generator function for iterating over *.fit file messages.

    Parameters
    ----------
    file_path : str
        Path to the ANT/Garmin fit file.

    Yields
    ------
    DefintionMessage or DataMessage
        Parsed messages from `file_path`.
    """
    with open_fit(file_path) as fitfile:
        read_file_header(fitfile)       # inplace changes

        while fitfile.bytes_left > 2:   # 2 byte CRC at the end of the file
            yield read_fit_message(fitfile)
