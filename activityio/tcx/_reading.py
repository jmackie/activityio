#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

from pandas import to_datetime

from activityio._types import ActivityData, special_columns
from activityio._util import drydoc, exceptions
from activityio._util.xml_reading import (
    gen_nodes, recursive_text_extract, sans_ns)


CAP = re.compile(r'([A-Z]{1})')

# According to Garmin, all times are stored in UTC.
DATETIME_FMT = '%Y-%m-%dT%H:%M:%SZ'
# Despite what the schema says, there are files out
# in the wild with fractional seconds...
DATETIME_FMT_WITH_FRAC = '%Y-%m-%dT%H:%M:%S.%fZ'

COLUMN_SPEC = {
    'altitude_meters': special_columns.Altitude,
    'cadence': special_columns.Cadence,
    'distance_meters': special_columns.Distance,
    'longitude_degrees': special_columns.Longitude,
    'latitude_degrees': special_columns.Latitude,
    'speed': special_columns.Speed,
    'watts': special_columns.Power,
}


def titlecase_to_undercase(string):
    """ ColumnName --> column_name """
    under = CAP.sub(lambda pattern: '_' + pattern.group(1).lower(), string)
    return under.lstrip('_')


@drydoc.gen_records
def gen_records(file_path):
    nodes = gen_nodes(file_path, ('Trackpoint',), with_root=True)

    root = next(nodes)
    if sans_ns(root.tag) != 'TrainingCenterDatabase':
        raise exceptions.InvalidFileError('tcx')

    trackpoints = nodes
    for trkpt in trackpoints:
        yield recursive_text_extract(trkpt)


def read_and_format(file_path):
    data = ActivityData.from_records(gen_records(file_path))
    times = data.pop('Time')                    # should always be there
    data = data.astype('float64', copy=False)   # try and make numeric

    # Prettier column names!
    data.columns = map(titlecase_to_undercase, data.columns)

    try:
        timestamps = to_datetime(times, format=DATETIME_FMT, utc=True)
    except ValueError:  # bad format, try with fractional seconds
        timestamps = to_datetime(times, format=DATETIME_FMT_WITH_FRAC, utc=True)

    timeoffsets = timestamps - timestamps[0]
    data._finish_up(column_spec=COLUMN_SPEC,
                    start=timestamps[0], timeoffsets=timeoffsets)

    return data
