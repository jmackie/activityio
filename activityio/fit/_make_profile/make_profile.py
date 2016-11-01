#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from operator import itemgetter
from os import path
from pprint import pformat

import xlrd


here = path.abspath(path.dirname(__file__))

PROFILE_XLSX_PATH = path.join(here, 'Profile.xlsx')

WORKBOOK = xlrd.open_workbook(PROFILE_XLSX_PATH)

COLNAMES_TYPES = ('type_name', 'base_type', 'value_name',
                  'value', 'comment')

COLNAMES_MESSAGES = ('message_name', 'field_def_num', 'field_name',
                     'field_type', 'array', 'components', 'scale',
                     'offset', 'units', 'bits', 'accumulate',
                     'ref_field_name', 'ref_field_value',
                     'comment', 'products', 'example')


class Row:
    __slots__ = tuple()

    def __init__(self, sheet, i):
        row = sheet.row_values(i)
        for name, value in zip(self.__slots__, row):
            setattr(self, name, value)   # values are received as strings

    def __iter__(self):
        for slot in self.__slots__:
            yield getattr(self, slot)

    def __getitem__(self, item):
        return getattr(self, self.__slots__[item])

    @property
    def is_empty(self):
        return not any(bool(cell) for cell in self)


class TypesRow(Row):
    __slots__ = COLNAMES_TYPES

    def __init__(self, sheet, i):
        super().__init__(sheet, i)

        if self.value:
            # Try and make the 'value' attribute numeric, bearing in
            # mind that it could be hexadecimal.
            try:
                self.value = int(self.value)
            except ValueError:
                self.value = int(self.value, 16)


class MessagesRow(Row):
    __slots__ = COLNAMES_MESSAGES

    @property
    def is_banner(self):
        # Based on banner text being placed in the 4th cell only.
        cells = [not bool(cell) for cell in self]
        fourth_cell = cells.pop(3)
        return not fourth_cell and all(cells)

    @property
    def field_data(self):
        keys = self.__slots__[1:]
        values = (getattr(self, name) for name in keys)
        return dict(zip(keys, values))


def read_types_sheet():
    sheet = WORKBOOK.sheet_by_name('Types')

    types = {}

    # i is our row counter; ignore the first (header) row.
    i, nrow = 1, sheet.nrows

    while i < nrow:
        # NB: there are various empty rows (sometimes more than one)
        # scattered throughout the Profile.xlsx file for sh*ts 'n' gigs.
        row = TypesRow(sheet, i)

        if row.is_empty:
            i += 1
            continue

        this_type_name = row.type_name
        types[this_type_name] = {'base_type': row.base_type, 'values': {}}

        i += 1
        row = TypesRow(sheet, i)

        while not row[0]:   # is the first column still empty?

            if row.is_empty:
                i += 1
                break

            types[this_type_name]['values'][row.value] = row.value_name

            i += 1
            if i == nrow:
                break
            else:
                row = TypesRow(sheet, i)

    return types


def read_messages_sheet(verbose=False):
    sheet = WORKBOOK.sheet_by_name('Messages')

    messages = {}

    # Book keeping:
    i, nrow = 1, sheet.nrows
    previous = None
    break_again = False

    while i < nrow:

        row = MessagesRow(sheet, i)

        if row.is_empty or row.is_banner:
            i += 1
            continue

        current_message_name = row.message_name
        current_message = {}

        i += 1
        row = MessagesRow(sheet, i)

        while not row[0]:    # is the first column still empty?

            if row.is_empty or row.is_banner:
                i += 1
                break

            # Subfields have no field number, if we encounter one
            # we need to traverse the subfields and append them to
            # the `previous` regular field.
            if row.field_def_num == '':
                subfields = {}

                while row.field_def_num == '' and not row[0]:

                    subfield_data = row.field_data
                    field_name = subfield_data['field_name']

                    subfields[field_name] = cleanup_subfield(subfield_data)

                    i += 1
                    row = MessagesRow(sheet, i)

                    if row.is_empty or row.is_banner:
                        i += 1
                        row = MessagesRow(sheet, i)
                        break_again = True   # HACK: break out of two loops
                        break

                previous['subfields'] = subfields

                if break_again:
                    break_again = False
                    break

            field_data = row.field_data
            field_num = field_data.pop('field_def_num')

            current_message[field_num] = previous = remove_empty(field_data)

            i += 1
            if i == nrow:
                break
            else:
                row = MessagesRow(sheet, i)

        messages[current_message_name] = current_message

    return messages


def remove_empty(x: dict):
    return dict(filter(itemgetter(1), x.items()))


def cleanup_subfield(subfield_data):
    try:
        ref_name = format_subfield_array(subfield_data['ref_field_name'])
        assert len(ref_name) == 1
        subfield_data.update(ref_field_name=ref_name.pop())
    except:
        pass

    try:
        subfield_data.update(ref_field_value=format_subfield_array(
            subfield_data['ref_field_value']))
    except:
        pass

    return remove_empty(subfield_data)


def format_subfield_array(array):
    return set(array.strip().replace('\n', '').split(','))


types_sheet = read_types_sheet()
messages_sheet = read_messages_sheet()


if __name__ == '__main__':

    # We're going to write a module...
    lines = []

    # Use pretty print, but format the first part manually.
    lines.append('MESSAGE_TYPES = {{\n {!s}'.format(
        pformat(messages_sheet, indent=4)[1:]))

    types_sheet_sans_basetype = {key: value['values']
                                 for key, value in types_sheet.items()}
    lines.append('TYPES_INFO = {{\n {!s}'.format(
        pformat(types_sheet_sans_basetype, indent=4)[1:]))

    lines.append('GLOBAL_MESG_NUMS = {{\n {!s}'.format(
        pformat(types_sheet['mesg_num']['values'], indent=4)[1:]))

    code = '\n\n'.join(lines)
    code += '\n'  # trailing new line

    outfile = path.join(path.dirname(here), '_profile.py')
    basetypes_file = path.join(here, 'BASE_TYPES.py')

    with open(outfile, 'wt', encoding='utf-8') as out, \
         open(basetypes_file, 'rt', encoding='utf-8') as basetypes:

        out.writelines(basetypes)
        out.write(code)
