#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Avoid repeating documentation. A bit hacky but it will do.

"""
import inspect


def gen_records(func):
    """Generator function for iterating over individual file records.

    "Records" are dictionary objects representing a single "sample" of data;
    i.e. a row in a tabular representation. Note this can be passed to
    the `from_records` constructor method of `pandas.DataFrame`s.
    """
    this_func = inspect.stack()[0][3]
    this_doc = globals().get(this_func).__doc__
    func.__doc__ = this_doc
    return func
