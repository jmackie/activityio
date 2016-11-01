#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Translate the `_protocol` module functionality to be consistent with
this package's API.

"""
from datetime import datetime, timedelta

from activityio.fit._protocol import gen_fit_messages, DataMessage
from activityio._util import drydoc, types


DATETIME_1990 = datetime(year=1990, month=1, day=1)


COLUMN_SPEC = {     # see Profile.xlsx for expected column names
    'altitude_m': types.Altitude,
    'cadence_rpm': types.Cadence,
    'distance_m': types.Distance,
    'heart_rate_bpm': types.HeartRate,
    'position_lat_semicircles': types.Latitude._from_semicircles,
    'position_long_semicircles': types.Longitude._from_semicircles,
    'power_watts': types.Power,
    'speed_m/s': types.Speed,
    'temperature_C': types.Temperature,
}


def message_filter(message, keep=('record', 'lap')):
    return isinstance(message, DataMessage) and message.name in keep


def make_key(field):
    if field[2]:
        return field[0] + '_' + field[2]
    else:
        return field[0]


def format_message(message):
    decoded = message.decode()   # (name, value, units)

    message_dict = {make_key(field): field[1] for field in decoded}

    try:
        message_dict['timestamp_s'] = (
            DATETIME_1990 + timedelta(seconds=message_dict['timestamp_s']))
    except KeyError:
        pass

    return message.name, message_dict


@drydoc.gen_records
def gen_records(file_path):
    messages = filter(message_filter, gen_fit_messages(file_path))
    lap = 1
    for name, message in (format_message(message) for message in messages):
        if name == 'lap':
            lap += 1
        else:
            message['lap'] = lap
            yield message


def read_and_format(file_path):
    data = types.ActivityData.from_records(gen_records(file_path))

    if 'timestamp_s' in data:
        timestamps = data.pop('timestamp_s')
        timeoffsets = timestamps - timestamps[0]
        data._finish_up(column_spec=COLUMN_SPEC,
                        start=timestamps[0], timeoffsets=timeoffsets)
    else:
        data._finish_up(column_spec=COLUMN_SPEC)

    return data
