#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from activityio._util.xml_reading import gen_nodes, sans_ns
from activityio._util import drydoc, types
from activityio._util.exceptions import InvalidFileError


DATETIME_FMT = '%Y-%m-%dT%H:%M:%S.%fZ'    # UTC


COLUMN_SPEC = {
    'atemp': types.Temperature,
    'cad': types.Cadence,
    'ele': types.Altitude,
    'hr': types.HeartRate,
    'lon': types.Longitude,
    'lat': types.Latitude,
}


def format_trackpoint(trackpoint):
    """Recursively extract tag text."""
    return {sans_ns(child.tag): child.text for child in trackpoint.iter()
            # ignore tags with no text, i.e. parent nodes
            if child.text.strip()}


@drydoc.gen_records
def gen_records(file_path):
    nodes = gen_nodes(file_path, ('trkpt',), with_root=True)

    root = next(nodes)
    if sans_ns(root.tag) != 'gpx':
        raise InvalidFileError("this doesn't look like a gpx file!")

    trackpoints = nodes

    for trkpt in trackpoints:
        trkpt_dict = format_trackpoint(trkpt)
        trkpt_dict.update(
            dict(trkpt.items()),   # lat, lon
            time=datetime.strptime(trkpt_dict['time'], DATETIME_FMT))

        yield trkpt_dict


def read_and_format(file_path):
    data = types.ActivityData.from_records(gen_records(file_path))

    timestamps = data.pop('time')
    timeoffsets = timestamps - timestamps[0]

    data = data.astype('float64', copy=False)   # try and make numeric

    data._finish_up(column_spec=COLUMN_SPEC,
                    start=timestamps[0], timeoffsets=timeoffsets)

    # We should be able to rely on always having lon and lat columns, so
    # may as well append a distance column.
    data[types.Distance.colname] = data.haversine().cumsum()

    return data
