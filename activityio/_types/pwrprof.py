#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from functools import partial
import operator

import numpy as np
from pandas import Timedelta

from activityio._types.base import DataFrameSubclass


class PowerProfile(DataFrameSubclass):
    _metadata = ['id']

    @staticmethod   # Becomes a bound method of ActivityData
    def from_activitydata(activitydata, durations, *, id=None):
        """Create a power profile for a given set of durations (given in
        seconds). The returned DataFrame-like object is also given an
        identifier (`id`) which is used by the `meld` method."""
        resampled_pwr = activitydata._get_resampled('pwr')

        mmp_gen = ({'duration': Timedelta(seconds=dur),
                    'pwr': resampled_pwr.rolling(dur).mean().max()}
                   for dur in durations)

        prof = PowerProfile.from_records(mmp_gen).set_index('duration')
        prof.id = id or activitydata.start
        return prof

    def meld(self, other):
        """Reduce two power profiles by taking the best (or only) value."""

        prof_l = self[['pwr']]      # only interested in
        prof_r = other[['pwr']]     # the power column

        joined = prof_l.join(prof_r, how='outer', lsuffix='_l', rsuffix='_r')
        reduced = joined.max(axis=1).to_frame('pwr')
        origins = joined.idxmax(axis=1)  # column names: 'pwr_l', 'pwr_r'

        # Construct 'came_from' identifiers. If they already exist in self,
        # they are recycled to allow for profile reducing.
        nrow, _ = joined.shape
        existing_came_from = self.get('came_from', None)
        if existing_came_from is not None:
            ids_l = np.array(list(existing_came_from))   # keep object dtype
        else:
            ids_l = np.array([prof_l.id] * nrow)

        ids_r = np.array([prof_r.id] * nrow)

        reduced['came_from'] = nanwhere(origins, is_eq('pwr_l'), ids_l, ids_r)

        return PowerProfile(reduced)


# Some local utilities
# --------------------
def nanwhere(series, condition_func, x, y):
    """Like np.where, only keeps NaNs."""
    return np.where(
        series.isnull(), np.nan, np.where(
            condition_func(series), x, y))

def is_eq(lhs):
    return partial(operator.eq, lhs)
