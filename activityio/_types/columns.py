#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import numpy as np
from pandas import Series, Timedelta

from activityio import tools
from activityio._types.base import SeriesSubclass, series_property


REGISTRY = {}    # grows at import-time via the below metaclass


class SpecialRegistrar(type):
    def __init__(cls, name, bases, namespace):
        if name != 'SpecialColumn':
            REGISTRY[cls.colname] = cls
        super().__init__(name, bases, namespace)


class SpecialColumn(SeriesSubclass, metaclass=SpecialRegistrar):
    _metadata = ['colname', 'base_unit']

    def __init__(self, data, *args, **kwargs):
        super().__init__(data, *args, **kwargs)
        self._name = self.__class__.colname     # use *class* attribute


# ----------------------------------------------------------
# NOTE: subclasses should follow the structure...
#   + classmethods (i.e. alternative constructors; private!)
#   + general methods
#   + properties
# ----------------------------------------------------------


class Altitude(SpecialColumn):
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


class Cadence(SpecialColumn):
    colname = 'cad'
    base_unit = 'rpm'


class Distance(SpecialColumn):
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


class Gradient(SpecialColumn):
    colname = 'grad'
    base_unit = 'fraction'

    _metadata = ['_rise', '_run'] + SpecialColumn._metadata

    def __init__(self, *args, rise=None, run=None, **kwargs):
        if rise is not None and run is not None:
            self._rise, self._run = rise.values, run.values
            super().__init__(rise / run, *args, **kwargs)
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


class HeartRate(SpecialColumn):
    colname = 'hr'
    base_unit = 'bpm'


class LapCounter(SpecialColumn):
    colname = 'lap'
    base_unit = '#'


class LonLat(SpecialColumn):
    colname = 'lonlat'
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


class Longitude(LonLat):
    colname = 'lon'


class Latitude(LonLat):
    colname = 'lat'


class Pace(SpecialColumn):
    colname = 'pace'
    base_unit = 'sec/m'

    @series_property
    def min_per_km(self):
        return self * 1000

    @series_property
    def min_per_mile(self):
        return self * 1000 / 1.61


class Power(SpecialColumn):
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


class Speed(SpecialColumn):
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


class Temperature(SpecialColumn):
    colname = 'temp'
    base_unit = 'degrees_C'


class VAM(SpecialColumn):
    colname = 'vam'
    base_unit = 'm/s'


class Work(SpecialColumn):
    colname = 'work'
    base_unit = 'J'

    @series_property
    def kj(self):
        """ joules --> kilojoules """
        return self / 1000
