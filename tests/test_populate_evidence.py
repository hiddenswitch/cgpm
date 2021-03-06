# -*- coding: utf-8 -*-

# Copyright (c) 2015-2016 MIT Probabilistic Computing Project

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
import pytest

from cgpm.mixtures.view import View
from cgpm.crosscat.state import State

"""Test suite for View._populate_evidence.

Ensures that View._populate_evidence correctly retrieves values from the
dataset.
"""


# ------------------------------------------------------------------------------
# Tests for cgpm.mixtures.view.View

def retrieve_view():
    X = np.asarray([
        [1,    np.nan,        2,      -1,      np.nan],
        [1,         3,        2,      -1,          -5],
        [1,    np.nan,   np.nan,  np.nan,      np.nan],
    ])
    outputs = [0,1,2,3,4]
    return View(
        {c: X[:,c].tolist() for c in outputs},
        outputs=[-1] + outputs,
        cctypes=['normal']*5,
        Zr=[0,1,2]
    )


def test_view_hypothetical_unchanged():
    view = retrieve_view()

    rowid = -1
    query1 = {3:-1}
    evidence1 = {1:1, 2:2}
    evidence2 = view._populate_evidence(rowid, query1, evidence1)
    assert evidence1 == evidence2


def test_view_only_rowid_to_populate():
    view = retrieve_view()

    # Can query X[2,0] for simulate.
    rowid = 2
    query1 = [0]
    evidence1 = {}
    evidence2 = view._populate_evidence(rowid, query1, evidence1)
    assert evidence2 == {-1: view.Zr(rowid)}


def test_view_constrain_cluster():
    view = retrieve_view()

    # Cannot constrain cluster assignment of observed rowid.
    rowid = 1
    query1 = {-1: 2}
    evidence1 = {}
    with pytest.raises(ValueError):
        view._populate_evidence(rowid, query1, evidence1)


def test_view_values_to_populate():
    view = retrieve_view()

    rowid = 0
    query1 = [1]
    evidence1 = {4:2}
    evidence2 = view._populate_evidence(rowid, query1, evidence1)
    assert evidence2 == {0:1, 2:2, 3:-1, 4:2, -1: view.Zr(rowid)}

    rowid = 0
    query1 = {1:1}
    evidence1 = {4:2}
    evidence2 = view._populate_evidence(rowid, query1, evidence1)
    assert evidence2 == {2:2, 0:1, 3:-1, 4:2, -1: view.Zr(rowid)}


# ------------------------------------------------------------------------------
# Tests for cgpm.crosscat.state.State

def retrieve_state():
    X = np.asarray([
        [1,    np.nan,        2,      -1,      np.nan],
        [1,         3,        2,      -1,          -5],
        [1,    np.nan,   np.nan,  np.nan,      np.nan],
    ])
    outputs = [0,1,2,3,4]
    return State(
        X,
        outputs=outputs,
        cctypes=['normal']*5,
        Zv={0:0, 1:0, 2:0, 3:0, 4:0},
        Zrv={0:[0,1,2]}
    )

def test_state_constrain_logpdf():
    state = retrieve_state()
    # Cannot query X[2,0] for logpdf.
    rowid = 2
    query1 = {0:2}
    evidence1 = {}
    with pytest.raises(ValueError):
        state._validate_query_evidence(rowid, query1, evidence1)

def test_state_constrain_errors():
    state = retrieve_state()

    rowid = 1
    query1 = {1:1, 4:1}
    evidence1 = {}
    with pytest.raises(ValueError):
        state._validate_query_evidence(rowid, query1, evidence1)

    rowid = 1
    query1 = {1:3}
    evidence1 = {4:-5}
    with pytest.raises(ValueError):
        state._validate_query_evidence(rowid, query1, evidence1)

    rowid = 1
    query1 = {0:1, 1:3}
    evidence1 = {}
    with pytest.raises(ValueError):
        state._validate_query_evidence(rowid, query1, evidence1)
