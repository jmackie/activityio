#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exceptions for this package.

"""
class ActivityIOError(Exception):
    """The base exception for all this package's exceptions."""
    _default_message = ''

    def __init__(self, message=None):
        super().__init__(message if message else self._default_message)


class InvalidFileError(Exception):
    _default_message = 'unexpected file format'

