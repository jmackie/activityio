#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A bonus module for prettifying console output.

"""
import sys


TEXT_DECORATIONS = {
    'header': '\033[95m',
    'blue': '\033[94m',
    'green': '\033[92m',
    'warning': '\033[93m',
    'fail': '\033[91m',
    'bold': '\033[1m',
    'underline': '\033[4m',
    'end': '\033[0m',
}


class indented_stdout:
    """Context manager for indenting anything sent to stdout.

        >>> with indented_stdout(2):
        ...    print('this is indented')
        ...
          this is intended
    """
    def __init__(self, indent=4):
        self.indent = ' ' * indent
        self.should_indent = True

    def write(self, text):
        if self.should_indent:
            text = self.indent + text
        # https://docs.python.org/3/library/sys.html#sys.__stdout__
        sys.__stdout__.write(text)
        self.should_indent = text.endswith('\n')    # for next time

    def __enter__(self):
        sys.stdout = self
        return self

    def __exit__(self, type, value, traceback):
        sys.stdout = sys.__stdout__


def decorate(text, *decorations):
    """Return a text string with ANSI escape codes pre- and appended.

    Parameters
    ----------
    text : str
        Text to be decorated.
    *decorations : str
        Currently supported escape codes are:
            + header
            + blue
            + green
            + warning
            + fail
            + bold
            + underline
            + end
    """
    decors = ''.join(TEXT_DECORATIONS[d] for d in decorations)
    end = TEXT_DECORATIONS['end']
    return decors + text + end


def printd(text, *decorations, **kwargs):
    """Print decorated."""
    to_write = decorate(text, *decorations)
    print(to_write, **kwargs)
