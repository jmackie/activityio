#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reading logic for SRM files. Should cover versions 5--9.

"""
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import reduce
from itertools import accumulate
from math import nan
from operator import ior
from struct import unpack, calcsize

from activityio._util import drydoc, types
from activityio._util.exceptions import InvalidFileError


DATETIME_1880 = datetime(year=1880, month=1, day=1)


COLUMN_SPEC = {
    'alt': types.Altitude,
    'cad': types.Cadence,
    'hr': types.HeartRate,
    'kph': types.Speed._from_kph,
    'lap': types.LapCounter,
    'lat': types.Latitude,
    'lon': types.Longitude,
    'metres': types.Distance._from_discrete,
    'temp': types.Temperature,
    'watts': types.Power,
}


class SRMHeader:
    __slots__ = ('days_since_1880', 'wheel_circum', 'recording_interval',
                 'block_count', 'marker_count', 'comment_len', '_comment')

    def __init__(self, srmfile):
        raw = srmfile.read(self.size)
        values = list(unpack(self.fmt, raw))
        values[2] /= values.pop(3)   # recording_interval (seconds; 1 / Hz)

        for name, value in zip(self.__slots__, values):
            setattr(self, name, value)

    @property
    def fmt(self):
        return '<2H2B2HxB' + '70s'

    @property
    def size(self):
        return calcsize(self.fmt)

    @property
    def comment(self):
        return self._comment.decode().rstrip('\x00')

    @property
    def date(self):
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

        # Data fixup: make sure markers are consistently one-indexed.
        self.start = max(self.start, 1)
        self.end = max(self.end, 1)
        # Data fixup: some srmwin versions wrote markers with start > end.
        self.start, self.end = sorted([self.start, self.end])

    @staticmethod
    def fmt(version):
        comment_len = 3 if version < 6 else 255
        fmt = '<%ds' % comment_len
        fmt += 'B7H' if version < 9 else 'B2L5H'
        return fmt

    @property
    def comment(self):
        return self._comment.decode().rstrip('\x00')

    @property
    def indices(self):
        """start and stop attributes, zero-indexed."""
        return {self.start - 1, self.end - 1}   # one-indexed!


class SRMBlock:
    __slots__ = ('sec_since_midnight', 'chunk_count', 'end')

    def __init__(self, srmfile):
        fmt = self.fmt(srmfile.version)
        raw = srmfile.read(calcsize(fmt))
        hsec_since_midnight, self.chunk_count = unpack(fmt, raw)

        # hsec to sec.
        self.sec_since_midnight = timedelta(seconds=hsec_since_midnight / 100)

        self.end = None   # set later

    @staticmethod
    def fmt(version):
        return '<L' + ('H' if version < 9 else 'L')


class SRMChunk:
    __slots__ = ('watts', 'cad', 'hr', 'kph', 'alt', 'temp', 'metres',
                 'lat', 'lon')

    def __init__(self, srmfile):

        self.lat, self.lon = nan, nan   # sensible default

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
            self.kph = 0 if self.kph < 0 else self.kph * 3.6 / 1000

        # Need to *make* a distance field (recording interval is in sec)
        self.metres = srmfile.recording_interval * self.kph / 3.6

    @staticmethod
    def compact_power_speed(srmfile):
        pwr_spd = unpack('<3B', srmfile.read(3))
        watts = (pwr_spd[1] & 0x0f) | (pwr_spd[2] << 0x4)
        kph = ((pwr_spd[1] & 0xf0) << 3 | (pwr_spd[0] & 0x7f)) * 3 / 26
        return watts, kph

    def __iter__(self):
        for name in self.__slots__:
            yield name, getattr(self, name)

    def as_dict(self):
        return {name: value for name, value in self}


@contextmanager
def open_srm(file_path):
    reader = open(file_path, 'rb')

    magic = reader.read(4).decode()
    if magic[:3] != 'SRM':
        raise InvalidFileError("this doesn't look like an srm file!")
    reader.version = int(magic[3])

    yield reader
    reader.close()


@drydoc.gen_records
def gen_records(file_path):
    with open_srm(file_path) as srmfile:
        header = SRMHeader(srmfile)
        srmfile.recording_interval = header.recording_interval  # useful!

        markers = deque(    # deque for popleft()
            SRMMarker(srmfile) for __ in range(header.marker_count + 1))

        blocks = deque(
            SRMBlock(srmfile) for __ in range(header.block_count))

        block_ends = accumulate(block.chunk_count for block in blocks)
        for block, end in zip(blocks, block_ends):
            setattr(block, 'end', end)

        # Calibration data
        zero, slope = unpack('<2H', srmfile.read(4))

        data_count_fmt = '<%sx' % ('H' if srmfile.version < 9 else 'L')
        data_count, = unpack(data_count_fmt,
                             srmfile.read(calcsize(data_count_fmt)))

        # data_count might overflow at 64k, so use sum from blocks instead
        data_count = sum(block.chunk_count for block in blocks)

        # Start generating the chunks (i.e. records)
        # ------------------------------------------

        # Stuff for creating timestamps
        current_block = blocks.popleft()
        timestamp = header.date + current_block.sec_since_midnight
        rec_int = timedelta(seconds=header.recording_interval)

        # Stuff for creating a lap counter
        lap = 0
        new_lap_i = deque(
            reduce(ior, (marker.indices for marker in markers)))
        next_lap = new_lap_i.popleft()

        for i in range(data_count):
            chunk = SRMChunk(srmfile).as_dict()

            if i == current_block.end:
                current_block = blocks.popleft()
                timestamp = header.date + current_block.sec_since_midnight
            else:
                timestamp += rec_int

            if i == next_lap:
                lap += 1
                if new_lap_i:   # are there any more lap triggers?
                    next_lap = new_lap_i.popleft()

            chunk.update(timestamp=timestamp, lap=lap)

            yield chunk


def read_and_format(file_path):
    data = types.ActivityData.from_records(gen_records(file_path))

    timestamps = data.pop('timestamp')
    timeoffsets = timestamps - timestamps[0]

    data._finish_up(column_spec=COLUMN_SPEC,
                    start=timestamps[0], timeoffsets=timeoffsets)

    return data
