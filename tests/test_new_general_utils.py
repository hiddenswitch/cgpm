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

"""
Tests for debugging subroutines in logpdf_multirow.
"""
import numpy as np
from itertools import product

from cgpm.mixtures.view import View
from cgpm.utils.general import logsumexp, deep_merged

def initialize_view():
    data = np.array([[1, 1]])
    D = len(data[0])
    outputs = range(D)
    X = {c: data[:, i].tolist() for i, c in enumerate(outputs)}
    view = View(
        X,
        outputs=[1000] + outputs,
        alpha=1.,
        cctypes=['bernoulli']*D,
        hypers={
            i: {'alpha': 1., 'beta': 1.} for i in outputs},
        Zr=[0])
    return view

def test_deep_merged_multirow():
    query = {0: {0: 1}, 1: {0: 1}}
    evidence = {0: {1000: 1}, 1: {1000: 1}}
    joint_input = {0: {0: 1, 1000: 1},
                   1: {0: 1, 1000: 1}}

    merged_input = deep_merged(query, evidence)
    assert joint_input == merged_input

def test_deep_merged_singlerow():
    query = {0: 1}
    evidence = {1000: 1}
    joint_input = {0: 1, 1000: 1}

    merged_input = deep_merged(query, evidence)
    assert joint_input == merged_input