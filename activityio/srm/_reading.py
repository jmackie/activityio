#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from contextlib import contextmanager
from datetime import datetime, timedelta
from itertools import accumulate
from math import nan
from struct import unpack, calcsize

from activityio._types import ActivityData, special_columns
from activityio._util import drydoc, exceptions


DATETIME_1880 = datetime(year=1880, month=1, day=1)

COLUMN_SPEC = {
    'alt': special_columns.Altitude,
    'cad': special_columns.Cadence,
    'hr': special_columns.HeartRate,
    'kph': special_columns.Speed._from_kph,
    'lap': special_columns.LapCounter,
    'lat': special_columns.Latitude,
    'lon': special_columns.Longitude,
    'metres': special_columns.Distance._from_discrete,
    'temp': special_columns.Temperature,
    'watts': special_columns.Power,
}


class SRMHeader:
    __slots__ = ('days_since_1880', 'wheel_circum', 'recording_interval',
                 'block_count', 'marker_count', 'comment_len', '_comment')

    def __init__(self, srmfile):
        fmt = '<2H2B2HxB' + '70s'
        raw = srmfile.read(calcsize(fmt))
        values = list(unpack(fmt, raw))  # need a list for pop()

        values[2] /= values.pop(3)  # recording_interval (seconds; 1 / Hz)

        for name, value in zip(self.__slots__, values):
            setattr(self, name, value)

    @property
    def comment(self):
        return self._comment.decode('utf-8', 'replace').rstrip('\x00')

    @property
    def date(self):
        # Training date (days since Jan 1, 1880)
        return DATETIME_1880 + timedelta(days=self.days_since_1880)


class SRMMarker:
    __slots__ = ('_comment', 'active', 'start', 'end', 'average_watts',
                 'average_hr', 'average_cadence', 'average_speed', 'pwc150')

    def __init__(self, srmfile):
        fmt = self.fmt(srmfile.version)
        raw = srmfile.read(calcsize(fmt))
        values = unpack(fmt, raw)

        for name, value in zip(self.__slots__, values):
            setattr(self, name, value)

        self._fixup()

    @staticmethod
    def fmt(version):
        comment_len = 3 if version < 6 else 255
        fmt = '<%ds' % comment_len
        fmt += 'B7H' if version < 9 else 'B2L5H'
        return fmt

    @property
    def comment(self):
        return self._comment.decode('utf-8', 'replace').rstrip('\x00')

    def _fixup(self):
        # Make sure markers are consistently one-indexed,
        # then zero-index them.
        self.start = max(self.start, 1) - 1
        self.end = max(self.end, 1) - 1

        # Some srmwin versions wrote markers with start > end.
        self.start, self.end = sorted([self.start, self.end])


class SRMSummaryMarker(SRMMarker):
    """SRM Files always contain at least one marker that encompasses
    the entire file."""


class SRMBlock:
    __slots__ = ('sec_since_midnight', 'chunk_count', 'end')

    def __init__(self, srmfile):
        fmt = self.fmt(srmfile.version)
        raw = srmfile.read(calcsize(fmt))
        hsec_since_midnight, self.chunk_count = unpack(fmt, raw)

        # hsec --> sec.
        self.sec_since_midnight = timedelta(seconds=hsec_since_midnight / 100)

        self.end = None   # set later

    @staticmethod
    def fmt(version):
        return '<L' + ('H' if version < 9 else 'L')


class SRMCalibrationData:
    __slots__ = ('zero', 'slope', '_data_count')

    def __init__(self, srmfile):
        self.zero, self.slope = unpack('<2H', srmfile.read(4))

        # We'll also consume the data count here, as it's safer
        # to use the sum of block chunk counts.
        fmt = '<%sx' % ('H' if srmfile.version < 9 else 'L')
        self._data_count, = unpack(fmt, srmfile.read(calcsize(fmt)))


class SRMPreamble:
    __slots__ = ('header', 'summary_marker', 'markers', 'blocks',
                 'calibration', 'data_count')

    def __init__(self, srmfile):
        self.header = SRMHeader(srmfile)

        self.summary_marker = SRMSummaryMarker(srmfile)
        self.markers = [SRMMarker(srmfile)
                        for _ in range(self.header.marker_count)]

        blocks = [SRMBlock(srmfile)
                  for _ in range(self.header.block_count)]
        block_ends = accumulate(block.chunk_count for block in blocks)
        for block, end in zip(blocks, block_ends):
            setattr(block, 'end', end)
        self.blocks = blocks

        self.calibration = SRMCalibrationData(srmfile)
        self.data_count = sum(block.chunk_count for block in blocks)


class SRMChunk:
    __slots__ = ('watts', 'cad', 'hr', 'kph', 'alt', 'temp',
                 'metres', 'lat', 'lon')  # variable

    def __init__(self, srmfile, recording_interval):
        self.metres = nan
        self.lat, self.lon = nan, nan

        if srmfile.version < 7:
            self.watts, self.kph = self.compact_power_speed(srmfile)
            self.cad, self.hr = unpack('<BB', srmfile.read(2))
            self.alt, self.temp = nan, nan
        else:
            values = unpack('<HBBllh', srmfile.read(14))
            for name, value in zip(self.__slots__, values):
                setattr(self, name, value)

            if srmfile.version == 9:
                latlon = unpack('<ll', srmfile.read(8))
                self.lat, self.lon = (l * 180 / 0x7fffffff for l in latlon)

            self.temp *= 0.1
            self.kph = 0 if (self.kph < 0) else self.kph * 3.6 / 1000
            self.metres = recording_interval * self.kph / 3.6

    @staticmethod
    def compact_power_speed(srmfile):
        pwr_spd = unpack('<3B', srmfile.read(3))
        # Ew.
        watts = (pwr_spd[1] & 0x0f) | (pwr_spd[2] << 0x4)
        kph = ((pwr_spd[1] & 0xf0) << 3 | (pwr_spd[0] & 0x7f)) * 3 / 26
        return watts, kph

    def __iter__(self):
        for name in self.__slots__:
            yield name, getattr(self, name)


@contextmanager
def open_srm(file_path):
    reader = open(file_path, 'rb')

    magic = reader.read(4).decode('utf-8')
    if magic[:3] != 'SRM':
        raise exceptions.InvalidFileError('srm')
    reader.version = int(magic[-1])

    yield reader

    reader.close()


@drydoc.gen_records
def gen_records(file_path):
    with open_srm(file_path) as srmfile:
        preamble = SRMPreamble(srmfile)

        header = preamble.header

        markers, blocks = preamble.markers, preamble.blocks
        markers.reverse()  # for
        blocks.reverse()   # popping

        try:   # there may only be a summary marker
            current_marker = markers.pop()
        except IndexError:
            pass

        current_block = blocks.pop()

        timestamp = header.date + current_block.sec_since_midnight
        rec_int = header.recording_interval
        rec_int_td = timedelta(seconds=rec_int)
        lap = 1

        for i in range(preamble.data_count):
            chunk = dict(SRMChunk(srmfile, rec_int))
            chunk['metres']

            if i == current_block.end:
                current_block = blocks.pop()
                timestamp = header.date + current_block.sec_since_midnight
            else:
                timestamp += rec_int_td

            if markers and i == current_marker.end:  # short-circuiting
                lap += 1
                current_marker = markers.pop()

            chunk.update(timestamp=timestamp, lap=lap)

            yield chunk


def read_and_format(file_path):
    data = ActivityData.from_records(gen_records(file_path))

    timestamps = data.pop('timestamp')
    timeoffsets = timestamps - timestamps[0]

    data._finish_up(column_spec=COLUMN_SPEC,
                    start=timestamps[0],
                    timeoffsets=timeoffsets)

    return data
