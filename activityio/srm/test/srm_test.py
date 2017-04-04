#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check the output of ``activityio.srm`` against that of Rainer Clasen's ``srmcmd``.

"""
from datetime import datetime
import os

import numpy as np
import pandas as pd

from activityio import srm


# setup
here = os.path.abspath(os.path.dirname(__file__))
files = os.path.join(here, 'files')
criterion = pd.read_csv(os.path.join(files, '71d257.csv'), '\t')
myattempt = srm.read(os.path.join(files, '71d257.srm'))


def test_timestamps():
    start = datetime.fromtimestamp(criterion['time'][1])
    assert start == myattempt.start

    fin = datetime.fromtimestamp(criterion['time'].iloc[-1])
    assert fin == (myattempt.start + myattempt.time[-1])


def test_columns():
    # Directly comparable columns
    for column in 'cad hr pwr temp'.split():
        assert all(np.isclose(criterion[column].values,
                              myattempt[column].values))
    # Other
    assert all(np.isclose(criterion['ele'].values,
                          myattempt['alt'].values))

    assert all(np.isclose(criterion['speed'].values,
                          myattempt['speed'].kph.values.round(2)))
