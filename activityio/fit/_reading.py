#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Translate the `_protocol` module functionality to be consistent with
this package's API.

"""
from datetime import datetime

from dateutil.relativedelta import relativedelta
import pytz

from activityio.fit._protocol import gen_fit_messages, DataMessage
from activityio._util import drydoc, types


TZ_UTC = pytz.timezone('UTC')

YEARS_20 = relativedelta(years=20)   # for formatting timestamps


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

    timestamp = message_dict.pop('timestamp_s', None)
    if timestamp:
        message_dict['timestamp'] = (
            datetime.fromtimestamp(timestamp) + YEARS_20)   # UTC time

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
    data = types.ActivityData.from_records(gen_records(file_path))

    if 'unknown' in data:    # TODO: look into why this is happening.
        del data['unknown']

    if 'timestamp' in data:
        timestamps = data.pop('timestamp')  # UTC
        tstart = timestamps[0]

        timezone = pytz.timezone(tz_str) if tz_str is not None else TZ_UTC
        tz_offset = timezone.utcoffset(tstart)
        timestamps += tz_offset

        timeoffsets = timestamps - tstart
        data._finish_up(column_spec=COLUMN_SPEC,
                        start=tstart, timeoffsets=timeoffsets)
    else:
        data._finish_up(column_spec=COLUMN_SPEC)

    return data
