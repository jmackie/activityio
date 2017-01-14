#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pandas import DataFrame

from activityio._types import ActivityData, special_columns
from activityio._util import drydoc, exceptions
from activityio._util.xml_reading import (
    gen_nodes, recursive_text_extract, sans_ns)


DATETIME_FMT = '%Y-%m-%dT%H:%M:%S.%fZ'    # UTC, with fractional seconds

COLUMN_SPEC = {
    'atemp': special_columns.Temperature,
    'cad': special_columns.Cadence,
    'ele': special_columns.Altitude,
    'hr': special_columns.HeartRate,
    'lon': special_columns.Longitude,
    'lat': special_columns.Latitude,
}


@drydoc.gen_records
def gen_records(file_path):
    nodes = gen_nodes(file_path, ('trkpt',), with_root=True)

    root = next(nodes)
    if sans_ns(root.tag) != 'gpx':
        raise exceptions.InvalidFileError('gpx')

    trackpoints = nodes

    for trkpt in trackpoints:
        trkpt_dict = recursive_text_extract(trkpt)

        trkpt_dict.update(dict(trkpt.items()))  # lat, lon
        try:
            trkpt_dict['time'] = datetime.strptime(
                trkpt_dict['time'], DATETIME_FMT)
        except KeyError:
            pass

        yield trkpt_dict


def read_and_format(file_path):
    data = DataFrame.from_records(gen_records(file_path))

    # I've encountered files without time values, which kinda precludes
    # us creating an ActivityData instance.
    if 'time' in data:
        timestamps = data.pop('time')
        timeoffsets = timestamps - timestamps[0]

        data = ActivityData(data).astype('float64')

        data._finish_up(column_spec=COLUMN_SPEC,
                        start=timestamps[0], timeoffsets=timeoffsets)

        # We should be able to rely on always having lon and lat columns, so
        # may as well append a distance column.
        data[special_columns.Distance.colname] = data.haversine().cumsum()

    else:
        data = data.astype('float64', copy=False)

    return data
