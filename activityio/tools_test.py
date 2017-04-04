#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import doctest

from activityio import tools


def test_docs():
    res = doctest.testmod(tools)
    assert res.failed == 0
