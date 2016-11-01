#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""


"""
from datetime import datetime, timedelta
from itertools import islice

from activityio._util.xml_reading import gen_nodes, sans_ns
from activityio._util import drydoc, types
from activityio._util.exceptions import InvalidFileError


DATETIME_FMT = '%Y-%m-%dT%H:%M:%S'    # timezone unspecified


COLUMN_SPEC = {
    'alt': types.Altitude,
    'cad': types.Cadence,
    'dist': types.Distance,
    'hr': types.HeartRate,
    'pwr': types.Power,
    'spd': types.Speed,
    'temp': types.Temperature,
}


def format_sample(sample):
    return {sans_ns(child.tag): float(child.text) for child in
            # Need to ignore the first (sample) element
            islice(sample.iter(), 1, None)}


@drydoc.gen_records
def gen_records(file_path):
    find_these = ['time', 'sample']
    nodes = gen_nodes(file_path, find_these, with_root=True)

    root = next(nodes)
    if sans_ns(root.tag) != 'pwx':
        raise InvalidFileError("this doesn't look like a pwx file!")

    start_time = datetime.strptime(next(nodes).text, DATETIME_FMT)
    find_these.pop(0)

    samples = nodes

    for sample in samples:
        sample_dict = format_sample(sample)
        sample_dict['timestamp'] = (
            start_time + timedelta(seconds=sample_dict['timeoffset']))
        yield sample_dict


def read_and_format(file_path):
    data = types.ActivityData.from_records(gen_records(file_path))

    timestamps = data.pop('timestamp')
    timeoffsets = data.pop('timeoffset')
    data._finish_up(column_spec=COLUMN_SPEC,
                    start=timestamps[0], timeoffsets=timeoffsets)

    return data
