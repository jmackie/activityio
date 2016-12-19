#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This module was generated automatically.

I sincerely apologise for it looking so disgusting.

"""
from math import isnan
import struct

class BaseType:
    __slots__ = ('name', 'identifier', 'fmt', 'parse')

    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)

    @property
    def size(self):
        return struct.calcsize(self.fmt)

    @property
    def type_num(self):
        return self.identifier & 0x1F


BASE_TYPE_BYTE = BaseType(name='byte', identifier=0x0D, fmt='B', parse=lambda x: None if x == 0xFF else x)

# Decide how invalid values are to be handled with the `parse` attribute.
BASE_TYPES = {
    0x00: BaseType(name='enum',    identifier=0x00, fmt='B', parse=lambda x: None if x == 0xFF else x),
    0x01: BaseType(name='sint8',   identifier=0x01, fmt='b', parse=lambda x: None if x == 0x7F else x),
    0x02: BaseType(name='uint8',   identifier=0x02, fmt='B', parse=lambda x: None if x == 0xFF else x),
    0x83: BaseType(name='sint16',  identifier=0x83, fmt='h', parse=lambda x: None if x == 0x7FFF else x),
    0x84: BaseType(name='uint16',  identifier=0x84, fmt='H', parse=lambda x: None if x == 0xFFFF else x),
    0x85: BaseType(name='sint32',  identifier=0x85, fmt='i', parse=lambda x: None if x == 0x7FFFFFFF else x),
    0x86: BaseType(name='uint32',  identifier=0x86, fmt='I', parse=lambda x: None if x == 0xFFFFFFFF else x),
    0x07: BaseType(name='string',  identifier=0x07, fmt='s', parse=lambda x: x.split(b'\x00')[0] or None),
    0x88: BaseType(name='float32', identifier=0x88, fmt='f', parse=lambda x: None if isnan(x) else x),
    0x89: BaseType(name='float64', identifier=0x89, fmt='d', parse=lambda x: None if isnan(x) else x),
    0x0A: BaseType(name='uint8z',  identifier=0x0A, fmt='B', parse=lambda x: None if x == 0x0 else x),
    0x8B: BaseType(name='uint16z', identifier=0x8B, fmt='H', parse=lambda x: None if x == 0x0 else x),
    0x8C: BaseType(name='uint32z', identifier=0x8C, fmt='I', parse=lambda x: None if x == 0x0 else x),
    0x0D: BASE_TYPE_BYTE}

BASE_TYPES_BY_NAME = {bt.name: bt for bt in BASE_TYPES.values()}

