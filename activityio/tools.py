#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
General tools that complement the API.

"""
import numpy as np


EARTH_RADIUS = 6371e3   # metres


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
        default, but if ``final=True`` the final bearing is returned instead.
    fill: scalar
        An appropriate missing value for the start.

    Returns
    -------
    numpy array
        Direction of travel between adjacent points in decimal degrees.

    Examples
    --------
        >>> lon = -0.8514, -0.8518
        >>> lat = 52.0503, 52.0495
        >>> bearing(np.radians(lon), np.radians(lat))
        array([          nan,  197.09216497])

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


def exp_weights(n):
    """Simple exponential weights function.

        >>> w = exp_weights(3)
        >>> print(w)
        [ 0.14285714  0.28571429  0.57142857]
        >>> sum(w)
        1.0
    """
    alpha = 2 / (n + 1)
    weights = np.array([alpha * (1 - alpha)**(-i) for i in range(n)])
    return weights / weights.sum()


def ewa(n, *, ignore_nan=True):
    """Exponentially weighted average.

    Returns a callable suitable for ``DataFrame.rolling().apply()``.

    Notes
    -----
    Effectively ``min_periods=n``, as is the default behaviour of pandas.
    """
    weights = exp_weights(n)
    sumfunc = np.nansum if ignore_nan else np.sum

    def func(arr):
        return sumfunc(arr * weights) if len(arr) == n else np.nan
    return func
