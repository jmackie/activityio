#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
General utilities to be used internally.

"""
import numpy as np


def transformer(functions):
    """Apply functions to a pandas.DataFrame by column name

    Returned function should be passed to the ``apply`` method of DataFrames.

    http://stackoverflow.com/questions/26434123

    Parameters
    ----------
    functions : dict
        A dictionary of functions, the keys for which determine the columns
        to which those functions should be applied.
    """
    def func(col):
        if col.name not in functions:
            return col
        else:
            return functions[col.name](col)
    return func


def zip_staggered(iterable):
    ls = list(iterable)   # need to consume the iterable, sadly
    return zip(ls[:-1], ls[1:])


def make_lap_column(length, new_lap_i):
    laps = np.zeros(length)
    laps[new_lap_i] = 1
    return laps.cumsum().astype(np.int64)


def semicircles_to_degrees(semicircles):
    """Positional data conversion for *.fit files

    https://github.com/kuperov/fit/blob/master/R/fit.R
    """
    return (semicircles * 180 / 2**31 + 180) % 360 - 180
