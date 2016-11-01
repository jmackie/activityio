#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
General tools that complement the API.

"""
from itertools import groupby, accumulate
from math import exp

import numpy as np


EARTH_RADIUS = 6371e3   # metres


def wbalance(power, timer_sec, *, CP, Wprime=None, first_value=0):
    """Calculate W' balance

    Parameters
    ----------
    power, timer_sec : numpy arrays
        Power (watts) and timer/timeoffsets (seconds).
    CP : scalar number
        Critical power value.
    Wprime : scalar number, optional
        A Wprime value in kilojoules.
    first_value : int, optional
        The initial value of the returned array, for which W' obviously cannot
        be calculated. Zero is sensible, but 'nan' could also be used.
    """
    wbal = [first_value]

    timedeltas_sec = timer_sec[1:] - timer_sec[:-1]

    # Iterate over sub- and supra-CP sections alternately.
    sections = groupby(zip(timedeltas_sec, power), lambda x: x[1] <= CP)

    to_recover = 0

    for lt_CP, section in sections:

        deltatime, powers = zip(*section)

        if lt_CP:

            if to_recover:   # anything?
                deltaCP = (CP - power for power in powers)
                recovery_time = accumulate(deltatime)
                tau_consts = (546 * exp(-0.01 * dcp) + 316 for dcp in deltaCP)
                wbal.extend(to_recover * exp(-tu / tau)
                            for tu, tau in zip(recovery_time, tau_consts))
            else:
                wbal.extend(0 for _ in deltatime)   # fill

        else:
            deltapwr = (power - CP for power in powers)
            cum_work = accumulate(  # LOL
                dt * dpwr for dt, dpwr in zip(deltatime, deltapwr))

            # Work is accumulated *on top of* whatever the
            # previous (end-recovery) W' balance state is.
            last_wbal = wbal[-1]
            cum_work = (last_wbal + work for work in cum_work)

            wbal.extend(cum_work)
            to_recover = wbal[-1]

    wbal = np.array(wbal)
    wbal /= 1000   # kJ

    if Wprime is not None:
        wbal = Wprime - wbal

    return wbal


def haversine(lon, lat, *, fill=0):
    """Great-circle distances between two points on a sphere.

    Parameters
    ----------
    lon, lat: numpy arrays or lists
        Positional coordinates in *radians*.
    fill: scalar
        An appropriate missing value for the start.

    Returns
    -------
    numpy array
        Distance(s) between adjacent points in metres.

    Examples
    --------
    >>> from activityio.tools import haversine
    >>> dist = haversine(np.radians([-77.037852, -77.043934]),
    ...                  np.radians([38.898556, 38.897147]))
    >>> '{:.1f} metres'.format(dist[-1])  # ignoring the leading zero
    '549.2 metres'

    References
    ----------
    https://rosettacode.org/wiki/Haversine_formula#Python
    http://www.movable-type.co.uk/scripts/latlong.html
    http://andrew.hedges.name/experiments/haversine/
    """
    lon, lat = np.asarray(lon), np.asarray(lat)   # check
    dlon, dlat = np.diff(lon), np.diff(lat)

    a = (np.sin(dlat / 2)**2
         + np.cos(lat[:-1])
         * np.cos(lat[1:])
         * np.sin(dlon / 2)**2)

    c = 2 * np.arcsin(np.sqrt(a)) * EARTH_RADIUS

    return np.concatenate(([fill], c))


def bearing(lon, lat, *, final=False, fill=np.nan):
    """Get bearing from positional coordinates.

    Parameters
    ----------
    lon, lat: numpy arrays or lists
        Positional coordinates in *radians*.
    final : bool, optional
        The initial bearing (also known as the forward azimuth) is returned by
        default, but if `final=True` the final bearing is returned instead.
    fill: scalar
        An appropriate missing value for the start.

    Returns
    -------
    numpy array
        Direction of travel between adjacent points in decimal degrees.

    References
    ----------
    http://www.movable-type.co.uk/scripts/latlong.html
    """
    lon, lat = np.asarray(lon), np.asarray(lat)   # check

    if final:
        lon, lat = lon[::-1], lat[::-1]

    raw_bearing = np.arctan2(
        np.sin(np.diff(lon)) * np.cos(lat[1:]),
        np.cos(lat[:-1]) * np.sin(lat[1:]) -
        np.sin(lat[:-1]) * np.cos(lat[1:]) * np.cos(np.diff(lon)))

    bearing = (np.degrees(raw_bearing) + 360) % 360  # degrees

    if final:
        bearing = (bearing + 180) % 180

    return np.concatenate(([fill], bearing))
