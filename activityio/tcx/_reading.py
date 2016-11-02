#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

from pandas import to_datetime

from activityio._util.xml_reading import gen_nodes, sans_ns
from activityio._util import drydoc, types
from activityio._util.exceptions import InvalidFileError


DATETIME_FMT = '%Y-%m-%dT%H:%M:%S.%fZ'    # UTC


COLUMN_SPEC = {
    'altitude_meters': types.Altitude,
    'cadence': types.Cadence,
    'distance_meters': types.Distance,
    'longitude_degrees': types.Longitude,
    'latitude_degrees': types.Latitude,
    'speed': types.Speed,
    'watts': types.Power,
}


def format_trackpoint(trackpoint):
    """Recursively extract tag text."""
    return {sans_ns(child.tag): child.text for child in trackpoint.iter()
            # ignore tags with no text, i.e. parent nodes
            if child.text.strip()}


def titlecase_to_undercase(string):
    """ ColumnName --> column_name """
    under = re.sub(r'([A-Z]{1})',
                   lambda pattern: '_' + pattern.group(1).lower(),
                   string)
    return under.lstrip('_')


@drydoc.gen_records
def gen_records(file_path):
    nodes = gen_nodes(file_path, ('Trackpoint',), with_root=True)

    root = next(nodes)
    if sans_ns(root.tag) != 'TrainingCenterDatabase':
        raise InvalidFileError("this doesn't look like a tcx file!")

    trackpoints = nodes
    for trkpt in trackpoints:
        yield format_trackpoint(trkpt)


def read_and_format(file_path):
    data = types.ActivityData.from_records(gen_records(file_path))
    times = data.pop('Time')    # should always be there
    data = data.astype('float64', copy=False)   # try and make numeric

    # Prettier column names!
    data.columns = map(titlecase_to_undercase, data.columns)

    timestamps = to_datetime(times, format=DATETIME_FMT, utc=True)
    timeoffsets = timestamps - timestamps[0]
    data._finish_up(column_spec=COLUMN_SPEC,
                    start=timestamps[0], timeoffsets=timeoffsets)

    return data
