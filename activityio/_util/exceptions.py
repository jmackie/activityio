#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exceptions for this package.

"""


class ActivityIOError(Exception):
    """Base exception."""
    _default_message = ''

    def __init__(self, message=None):
        super().__init__(message if message else self._default_message)


class InvalidFileError(Exception):
    def __init__(self, fmt):
        determiner = 'an' if fmt[0] in ('aeiou' + 's') else 'a'  # grammar
        message = "this doesn't look like %s %s file!" % (determiner, fmt)
        super().__init__(message)


class RequiredColumnError(ActivityIOError):
    def __init__(self, column, cls=None):
        if cls is None:
            message = '{!r} column not found'.format(column)
        else:
            message = '{!r} column should be of type {!s}'.format(column, cls)
        super().__init__(message)


# Exceptions specific to the fit subpackage
# -----------------------------------------
class FITFileHeaderError(ActivityIOError):
    pass


class FITMessageHeaderError(ActivityIOError):
    pass
