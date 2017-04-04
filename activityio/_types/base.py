#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from functools import wraps

from pandas import DataFrame, Series

from activityio._util import exceptions


__all__ = ('DataFrameSubclass', 'SeriesSubclass',  # using * import elsewhere
           'series_property', 'new_column_sugar')


class DataFrameSubclass(DataFrame):
    _metadata = []

    @property
    def _constructor(self):
        return self.__class__

    def __finalize__(self, other, method=None, **kwargs):
        """Propagate metadata from other to self."""
        for name in self._metadata:
            object.__setattr__(self, name, getattr(other, name, None))
        return self


class SeriesSubclass(Series):
    _metadata = []

    @property
    def _constructor(self):
        return self.__class__

    def __finalize__(self, other, method=None, **kwargs):
        """Propagate metadata from other to self."""
        for name in self._metadata:
            object.__setattr__(self, name, getattr(other, name, None))
        return self


class series_property:
    """A simple descriptor that emulates property, but returns a Series."""
    def __init__(self, fget):
        self.fget = fget

    def __get__(self, obj, objtype=None):
        return Series(self.fget(obj))


def new_column_sugar(needs: tuple, name=None):
    """Decorator for certain methods of ActivityData that create new columns
    using the special column types.

    Parameters
    ----------
    needs : tuple
        A tuple of column names.
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
                    raise exceptions.RequiredColumnError(need)

            # Fine, so construct the new Series.
            out = func(self, *args, **kwargs)
            return Series(out, index=self.index, name=name)
        return wrapper
    return real_decorator
