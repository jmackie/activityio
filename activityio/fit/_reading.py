#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Translate the `_protocol` module functionality to be consistent with
this package's API.

"""
from datetime import datetime, timedelta

import pytz

from activityio.fit._protocol import gen_fit_messages, DataMessage
from activityio._types import ActivityData, special_columns
from activityio._util import drydoc


TZ_UTC = pytz.timezone('UTC')

DATETIME_1990 = datetime(year=1989, month=12, day=31)

COLUMN_SPEC = {     # see Profile.xlsx for expected column names
    'altitude_m': special_columns.Altitude,
    'cadence_rpm': special_columns.Cadence,
    'distance_m': special_columns.Distance,
    'heart_rate_bpm': special_columns.HeartRate,
    'position_lat_semicircles': special_columns.Latitude._from_semicircles,
    'position_long_semicircles': special_columns.Longitude._from_semicircles,
    'power_watts': special_columns.Power,
    'speed_m/s': special_columns.Speed,
    'temperature_C': special_columns.Temperature,
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

    timestamp = message_dict.pop('timestamp_s', None)
    if timestamp:
        message_dict['timestamp'] = (  # UTC time
            DATETIME_1990 + timedelta(seconds=timestamp))

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


def read_and_format(file_path, *, tz_str=None):
    data = ActivityData.from_records(gen_records(file_path))

    try:
        del data['unknown']
    except KeyError:
        pass

    if 'timestamp' in data:
        timestamps = data.pop('timestamp')  # UTC

        timezone = pytz.timezone(tz_str) if tz_str is not None else TZ_UTC
        tz_offset = timezone.utcoffset(timestamps[0])
        timestamps += tz_offset
        tstart = timestamps[0]

        timeoffsets = timestamps - tstart
        data._finish_up(column_spec=COLUMN_SPEC,
                        start=tstart, timeoffsets=timeoffsets)
    else:
        data._finish_up(column_spec=COLUMN_SPEC)

    return data
