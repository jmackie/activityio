#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import numpy as np
from pandas import Series, Timedelta, TimedeltaIndex

from activityio import tools
from activityio._util import exceptions
from activityio._types import (
    DataFrameSubclass, new_column_sugar, special_columns)


class ActivityData(DataFrameSubclass):
    _metadata = ['start']

    def __getitem__(self, key):
        """Create the illusion of Series subclasses in the DataFrame."""
        item = super().__getitem__(key)
        try:
            return special_columns.REGISTRY[key](item)
        except:
            return item

    @property
    def time(self):   # makes accessing the index more readable
        if isinstance(self.index, TimedeltaIndex):
            return self.index
        else:
            # because recursion problems with super().__getattr__()
            raise AttributeError('index is not TimedeltaIndex')

    def recording_time(self, samplingfreq=1):
        """Time spent in an activity."""
        dummy = Series(1, index=self.index)   # important: is filled!
        resampled = dummy.resample('%ds' % samplingfreq).mean()
        recording = np.logical_not(
            np.isnan(resampled.values))[1:]   # shorten for indexing diffs
        timediffs = np.diff(resampled.index.total_seconds())
        time_sec = timediffs[recording].sum()
        return Timedelta(seconds=time_sec)

    # NOTE: .rolling() takes a `min_periods` argument, but I think for most
    # purposes here we want to only consider a full window.

    def rollmean(self, column, seconds, *, samplingfreq=1):
        """Rolling mean by time."""
        return self._get_resampled(
            column, samplingfreq).rolling(seconds).mean()

    @new_column_sugar(needs=('lon', 'lat'), name='dists_m')
    def haversine(self, **kwargs):
        lon, lat = (self[ax].radians.values for ax in ('lon', 'lat'))
        return tools.haversine(lon, lat, **kwargs)

    @new_column_sugar(needs=('lon', 'lat'), name='bearing_deg')
    def bearing(self, **kwargs):
        lon, lat = (self[ax].radians.values for ax in ('lon', 'lat'))
        return tools.bearing(lon, lat, **kwargs)

    def vam(self):
        dtime = np.diff(self.index.total_seconds())
        # numpy.diff doesn't prepend an NaN
        dtime = np.insert(dtime, 0, np.nan)
        dvert = self._try_get('alt').diff()
        return special_columns.VAM(dvert / dtime)

    def gradient(self):
        alt, dist = (self._try_get(key) for key in ('alt', 'dist'))
        return special_columns.Gradient(rise=alt.diff(), run=dist.diff())

    # Private methods
    # ---------------
    def _finish_up(self, *, column_spec, start=None, timeoffsets=None):
        """A pseudo-init method, used internally."""
        for old_key, column_cls in column_spec.items():
            try:
                old_column = self.pop(old_key)  # no default
            except KeyError:
                continue

            new = column_cls(old_column)
            self[new.colname] = new

        self.start = start
        if timeoffsets is not None:
            self.index = TimedeltaIndex(timeoffsets, unit='s', name='time')

        # No point hanging on to completely empty columns!
        self.dropna(axis=1, how='all', inplace=True)

    def _get_resampled(self, column, samplingfreq=1):
        rule = '%ds' % samplingfreq
        return self._try_get(column).resample(rule).mean()  # missing --> NaNs

    def _try_get(self, key):
        """Try and get a required column from the data."""
        try:
            return self[key]
        except KeyError as e:
            raise exceptions.RequiredColumnError(key) from e
