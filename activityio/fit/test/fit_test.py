#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import collections
import csv
import itertools
import json
import numbers
from operator import attrgetter, methodcaller
import os
import pprint
import sys
import re

import activityio.fit._protocol as fit


RE_DIGIT = re.compile(r'\d{1}')


class fvu:
    """The FitCSVTool gives us these tuples after the message header
    information."""
    __slots__ = ('field', 'value', 'units')

    def __init__(self, field, value, units):
        self.field, self.value, self.units = field, value, units

    def __repr__(self):
        """prints like a tuple."""
        return str((self.field, self.value, self.units))

    def should_compare(self):
        """exceptions/known issues."""
        if isinstance(self.value, str) and len(self.value) == 0:
            return False

        if self.field == 'unknown':
            return False

        # FIX: this diff is a problem
        if self.field.startswith('enhanced'):
            return False

        return True


class FieldValues(collections.UserList):

    def __init__(self, data):
        self.data = list(data)
        self.mesg_type = getattr(data, 'mesg_type', None)  # preserve

    @property
    def mesg(self):
        return getattr(self, 'mesg_type', None)

    @mesg.setter
    def mesg(self, value):
        self.mesg_type = fit.MESSAGE_TYPES.get(value, {})
        if self.mesg_type:
            # remap keys to field names
            self.mesg_type = {v['field_name']: v
                              for _, v in self.mesg_type.items()}

    @classmethod
    def fromrow(cls, row):
        row = row[3:]  # ignore meta cells
        n = len(row)
        if (n-1) % 3 != 0:
            raise ValueError('len(row) is not a multiple of 3')
        tuples = [row[stop-3:stop] for stop in range(3, n, 3)]
        return cls(fvu(*t) for t in tuples if any(t))

    def filter(self):
        cls = type(self)

        # KNOWN DIFF: FitCSVTools handles dynamic messages differently
        if any('subfields' in v for v in self.mesg.values()):
            return cls([])

        return cls(m for m in self if m.should_compare())

    def __str__(self):
        return pprint.pformat(self)


def emulate_sdk_output(filepath):
    """Parses a FIT file with this library and generates rows in a similar
    format to the FitCSVTool (provided with the FIT SDK)."""
    for mesg in fit.gen_fit_messages(filepath):
        if isinstance(mesg, fit.DataMessage):
            meta = (type(mesg).__name__.replace('Message', ''),
                    mesg.header.local_message_type,
                    mesg.name)
            fvs = FieldValues(fvu(*m) for m in mesg.decode())
            fvs.mesg = meta[-1]
            yield meta, fvs


def sdk_output(filepath):
    with open(filepath) as csvfile:
        csvfile.readline()  # ignore header
        for row in csv.reader(csvfile):
            meta = row[:3]
            if meta[0] != 'Data':  # filtering here
                continue
            fvs = FieldValues.fromrow(row)
            fvs.mesg = meta[-1]
            yield meta, fvs


def compare(sdk_meta, sdk_fvs, pkg_meta, pkg_fvs):
    # Compare meta
    for want, got in zip(sdk_meta, pkg_meta):
        if type(got)(want) != got:
            raise MetaMismatchError(want, got)

    mesg_type = sdk_fvs.mesg

    # Compare (field, value, unit)
    sdk_fvs = sdk_fvs.filter()
    pkg_fvs = pkg_fvs.filter()

    # First check the lengths
    if len(sdk_fvs) != len(pkg_fvs):
        raise NFieldsError(sdk_meta[-1], sdk_fvs, pkg_fvs)

    # Now check the values
    for sdk, pkg in zip(sdk_fvs, pkg_fvs):
        want, got = sdk.value, pkg.value
        # match up the types
        if isinstance(got, bytes):
            got = got.decode('utf-8')
        try:
            want = type(got)(want)
        except ValueError:

            # KNOWN DIFF: FitCSVTool doesn't apply scale/offsets
            m = mesg_type.get(sdk.field, {})
            if 'scale' in m or 'offset' in m:
                continue

            raise WantGotError(sdk_meta[-1], sdk.field, want, got)

        # KNOWN DIFF: FitCSVTool just gives raw codes
        #             where we give decoded strings
        if isinstance(got, str) and RE_DIGIT.search(want):
            continue

        if want != got:
            raise WantGotError(sdk_meta[-1], sdk.field, want, got)


class MetaMismatchError(Exception):
    def __init__(self, want, got):
        feedback = 'SDK gave %r but we produced %r' % (want, got)
        super().__init__(feedback)


class NFieldsError(Exception):
    def __init__(self, mesg_name, sdk_fvs, pkg_fvs):
        self.missing = {fv.field for fv in sdk_fvs} ^ {fv.field for fv in pkg_fvs}
        if len(sdk_fvs) > len(pkg_fvs):
            feedback = 'package is missing %r' % self.missing
        else:
            feedback = 'package also produced %r' % self.missing

        super().__init__(feedback)
        self.mesg_name = mesg_name
        self.sdk_fvs = sdk_fvs
        self.pkg_fvs = pkg_fvs


class WantGotError(Exception):
    def __init__(self, mesg_name, field_name, want, got):
        feedback = '{!s}({!s}) wanted {!r} got {!r}'.format(
            mesg_name, field_name, want, got)

        super().__init__(feedback)
        self.want, self.got = want, got


class NRowError(Exception):
    def __init__(self, want, got):
        feedback = 'SDK gave %d but we produced %d' % (want, got)
        super().__init__(feedback)


def test_reading():
    here = os.path.abspath(os.path.dirname(__file__))
    files = os.path.join(here, 'files')

    to_test = []
    for fp in os.listdir(files):
        bare, ext = os.path.splitext(fp)
        if ext == '.fit':
            to_test.append(os.path.join(files, bare))

    for f in to_test:
        sdk_gen = sdk_output(f + '.csv')
        pkg_gen = emulate_sdk_output(f + '.fit')
        # need zip_longest to check lens
        data = itertools.zip_longest(sdk_gen, pkg_gen)

        MISSING = collections.defaultdict(set)

        for mesg_count, (sdk_data, pkg_data) in enumerate(data, 1):

            if sdk_data is None:
                raise NRowError('sdk ran out at %d' % mesg_count)
            elif pkg_data is None:
                raise NRowError('pkg ran out at %d' % mesg_count)

            try:
                compare(*sdk_data, *pkg_data)
            except NFieldsError as e:
                print(e)
                MISSING[e.mesg_name].update(e.missing)
            except WantGotError as e:
                raise e

        assert dict(MISSING) == {}


if __name__ == '__main__':
    test_reading()
