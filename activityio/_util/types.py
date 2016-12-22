#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from functools import wraps

import numpy as np
from pandas import DataFrame, Series, Timedelta, TimedeltaIndex

from activityio import tools
from activityio._util.exceptions import ActivityIOError


SPECIAL_COLUMNS = {}    # grows on import via @special decorator


class RequiredColumnError(ActivityIOError):
    def __init__(self, column, cls=None):
        if cls is None:
            message = '{!r} column not found'.format(column)
        else:
            message = '{!r} column should be of type {!s}'.format(column, cls)
        super().__init__(message)


def new_column_sugar(needs: tuple, name=None):
    """Decorator for certain methods of ActivityData that create new columns
    using the special column types specified here.

    Parameters
    ----------
    needs : tuple
        A tuple of colnames.
    name : str, optional
        The name for the returned Series object.

    Returns
    -------
    Series
        Suitable for joining to the existing data.

    Raises
    ------
    RequiredColumnError
        If a column specified in `needs` is not present.
    """
    def real_decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for need in needs:
                if need not in self:
                    raise RequiredColumnError(need)

            # Fine, so construct the new Series.
            out = func(self, *args, **kwargs)
            return Series(out, index=self.index, name=name)
        return wrapper
    return real_decorator


class ActivityData(DataFrame):
    _metadata = ['start', '_athlete']

    @property
    def _constructor(self):
        return ActivityData

    def __finalize__(self, other, method=None, **kwargs):
        """Propagate metadata from other to self."""
        for name in self._metadata:
            object.__setattr__(self, name, getattr(other, name, None))
        return self

    def __getitem__(self, key):
        """Create the illusion of Series subclasses in the DataFrame."""
        item = super().__getitem__(key)
        try:
            return SPECIAL_COLUMNS[key](item)
        except:
            return item

    def _finish_up(self, *, column_spec, start=None, timeoffsets=None):
        for old_key, column_cls in column_spec.items():
            # DataFrame.pop() does not take a default arg
            try:
                old_column = self.pop(old_key)
            except KeyError:
                continue

            new = column_cls(old_column)
            self[new.colname] = new

        self.start = start
        if timeoffsets is not None:
            self.index = TimedeltaIndex(timeoffsets, unit='s', name='time')

        # No point hanging on to completely empty columns!
        self.dropna(axis=1, how='all', inplace=True)

    @property
    def time(self):   # makes accessing the index more readable
        if isinstance(self.index, TimedeltaIndex):
            return self.index
        else:
            # because recursion problems with super().__getattr__()
            raise AttributeError('index is not TimedeltaIndex')

    def rollmean(self, column, seconds, *, samplingfreq=1):
        """Apply rolling mean by time to column."""
        return (self._get_resampled(column, samplingfreq)
                    .rolling(seconds).mean())

    def normpwr(self):
        """Training Peaks 'Normalised Power' (NP) metric."""
        window = 30
        smooth_pwr = self._get_resampled('pwr').rolling(window).mean()
        return np.mean(smooth_pwr**4)**0.25

    def recording_time(self, samplingfreq=1):
        """Time spent in an activity."""
        dummy = Series(1, index=self.index)   # important: is filled!
        resampled = dummy.resample('%ds' % samplingfreq).mean()
        recording = np.logical_not(
            np.isnan(resampled.values))[1:]   # shorten for indexing diffs
        timediffs = np.diff(resampled.index.total_seconds())
        time_sec = timediffs[recording].sum()
        return Timedelta(seconds=time_sec)

    def xpwr(self):
        """Dr Skiba's xPower."""
        window = 25
        weights = tools.ema_weights(window)
        smooth_pwr = self._get_resampled('pwr').rolling(window).apply(
            lambda arr: np.sum(arr * weights))
        return np.mean(smooth_pwr**4)**0.25

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
        return VAM(dvert / dtime)

    def gradient(self):
        alt, dist = (self._try_get(key) for key in ('alt', 'dist'))
        return Gradient(rise=alt.diff(), run=dist.diff())

    def pwr_prof(self, durations, *, duration_index=True, return_gen=False):
        """Extract best powers for given durations.

        Parameters
        ----------
        durations : iterable
            Time durations (in seconds) for which best powers are to be found.
        duration_index : bool, optional
            Should the durations be made into the index of the returned data,
            or left as a column?
        return_gen : bool, optional
            Return a generator of (duration, best_power) pairs?

        Returns
        -------
        pandas.DataFrame
        """
        resampled_pwr = self._get_resampled('pwr')
        gen = ((dur, resampled_pwr.rolling(dur).mean().max())  # MMP
               for dur in durations)

        if return_gen:
            return gen

        df = DataFrame(gen, columns=('duration', 'pwr'))
        return df.set_index('duration') if duration_index else df

    def _get_resampled(self, column, samplingfreq=1):
        rule = '%ds' % samplingfreq
        return self._try_get(column).resample(rule).mean()  # missing --> NaNs

    def _try_get(self, key):
        """Try and get a required column from the data."""
        try:
            return self[key]
        except KeyError as e:
            raise RequiredColumnError(key) from e


class SeriesSubclass(Series):
    _metadata = ['colname', 'base_unit']

    @property
    def _constructor(self):
        return self.__class__

    def __finalize__(self, other, method=None, **kwargs):
        """Propagate metadata from other to self."""
        for name in self._metadata:
            object.__setattr__(self, name, getattr(other, name, None))
        return self

    def __init__(self, data, *args, **kwargs):
        super().__init__(data, *args, **kwargs)
        self._name = self.__class__.colname     # use class attribute

    # NOTE: subclasses should follow the structure...
    #   + classmethods (i.e. alternative constructors; private!)
    #   + general methods
    #   + properties


def special(cls):
    """Decorator for easily growing the SPECIAL_COLUMNS global dict."""
    global SPECIAL_COLUMNS
    SPECIAL_COLUMNS[cls.colname] = cls
    return cls


class series_property:
    """A simple descriptor that emulates property, but returns a Series."""
    def __init__(self, fget):
        self.fget = fget
        self.__doc__ = fget.__doc__

    def __get__(self, obj, objtype=None):
        return Series(self.fget(obj))


@special
class Altitude(SeriesSubclass):
    colname = 'alt'
    base_unit = 'm'

    @property
    def ascent(self):
        deltas = self.diff()
        cls = type(self)
        return cls(np.where(deltas > 0, deltas, 0))

    @property
    def descent(self):
        deltas = self.diff()
        cls = type(self)
        return cls(np.where(deltas < 0, deltas, 0))

    @series_property
    def ft(self):
        """ metres --> feet """
        return self * 3.28084


@special
class Cadence(SeriesSubclass):
    colname = 'cad'
    base_unit = 'rpm'


@special
class Distance(SeriesSubclass):
    colname = 'dist'
    base_unit = 'm'

    @classmethod
    def _from_discrete(cls, data, *args, **kwargs):
        return cls(data.cumsum(), *args, **kwargs)

    @series_property
    def km(self):
        """ metres --> kilometres """
        return self / 1000

    @series_property
    def miles(self):
        """ metres --> miles """
        return self / 1000 * 0.621371


@special
class Gradient(SeriesSubclass):
    colname = 'grad'
    base_unit = 'fraction'

    _metadata = ['_rise', '_run'] + SeriesSubclass._metadata

    def __init__(self, *args, rise=None, run=None, **kwargs):
        if rise is not None and run is not None:
            self._rise, self._run = rise.values, run.values
            super().__init__(rise/run, *args, **kwargs)
        else:
            super().__init__(*args, **kwargs)

    @series_property
    def pct(self):
        """ fraction --> % """
        return self * 100

    @series_property
    def radians(self):
        """ fraction --> radians """
        return np.arctan2(self._rise, self._run)

    @series_property
    def degrees(self):
        """ fraction --> degrees """
        return np.rad2deg(np.arctan2(self._rise, self._run))


@special
class HeartRate(SeriesSubclass):
    colname = 'hr'
    base_unit = 'bpm'


@special
class LapCounter(SeriesSubclass):
    colname = 'lap'
    base_unit = '#'


class LonLat(SeriesSubclass):
    base_unit = 'degrees'

    @classmethod
    def _from_semicircles(cls, data, *args, **kwargs):
        # https://github.com/kuperov/fit/blob/master/R/fit.R
        deg = (data * 180 / 2**31 + 180) % 360 - 180
        return cls(deg, *args, **kwargs)

    @series_property
    def radians(self):
        """ degrees --> radians """
        return np.radians(self)


@special
class Longitude(LonLat):
    colname = 'lon'


@special
class Latitude(LonLat):
    colname = 'lat'


@special
class Pace(SeriesSubclass):
    colname = 'pace'
    base_unit = 'sec/m'

    @series_property
    def min_per_km(self):
        return self * 1000

    @series_property
    def min_per_mile(self):
        return self * 1000 / 1.61


@special
class Power(SeriesSubclass):
    colname = 'pwr'
    base_unit = 'watts'

    def to_work(self):
        dt = np.diff(self.index.total_seconds())
        dt = np.concatenate(([np.nan], dt))
        return Work(self * dt)

    def wbalance(self, CP, **kwargs):
        wbal = tools.wbalance(power=self.values,
                              timer_sec=self.index.total_seconds(),
                              CP=CP, **kwargs)
        return Series(wbal, index=self.index, name='wbalance')


@special
class Speed(SeriesSubclass):
    colname = 'speed'
    base_unit = 'm/s'

    @classmethod
    def _from_kph(cls, data, *args, **kwargs):
        return cls(data / 60**2 * 1000, *args, **kwargs)

    def to_pace(self):
        tds = (1 / self).apply(Timedelta, args=('s',))
        return Pace(tds)

    @series_property
    def kph(self):
        """ metres/second --> kilometres/hour """
        return self * 60**2 / 1000

    @property
    def mph(self):
        """ metres/second --> miles/hour """
        return self.kph / 1.61    # self.kph is already a Series


@special
class Temperature(SeriesSubclass):
    colname = 'temp'
    base_unit = 'degrees_C'


@special
class VAM(SeriesSubclass):
    colname = 'vam'
    base_unit = 'm/s'


@special
class Work(SeriesSubclass):
    colname = 'work'
    base_unit = 'J'

    @series_property
    def kj(self):
        """ joules --> kilojoules """
        return self / 1000
