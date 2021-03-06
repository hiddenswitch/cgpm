# -*- coding: utf-8 -*-

#   Copyright (c) 2010-2016, MIT Probabilistic Computing Project
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import base64
import copy
import math

from collections import defaultdict
from datetime import datetime

import venture.shortcuts as vs

from cgpm.cgpm import CGpm
from cgpm.utils import config as cu
from cgpm.utils import general as gu


class VsCGpm(CGpm):
    """CGpm specified by a Venturescript program."""

    def __init__(self, outputs, inputs, rng=None, sp=None, **kwargs):
        # Set the rng.
        self.rng = rng if rng is not None else gu.gen_rng(1)
        seed = self.rng.randint(1, 2**31 - 1)
        # Basic input and output checking.
        if len(set(outputs)) != len(outputs):
            raise ValueError('Non unique outputs: %s' % outputs)
        if len(set(inputs)) != len(inputs):
            raise ValueError('Non unique inputs: %s' % inputs)
        if not all(o not in inputs for o in outputs):
            raise ValueError('Duplicates: %s, %s' % (inputs, outputs))
        if not all(i not in outputs for i in inputs):
            raise ValueError('Duplicates: %s, %s' % (inputs, outputs))
        # Retrieve the ripl.
        self.ripl = kwargs.get('ripl', vs.make_lite_ripl(seed=seed))
        self.mode = kwargs.get('mode', 'church_prime')
        # Execute the program.
        self.source = kwargs.get('source', None)
        if self.source is not None:
            self.ripl.set_mode(self.mode)
            self.ripl.execute_program(self.source)
        # Load any plugins.
        self.plugins = kwargs.get('plugins', None)
        if self.plugins:
            for plugin in self.plugins.split(','):
                self.ripl.load_plugin(plugin.strip())
        # Force the mode to church_prime.
        self.ripl.set_mode('church_prime')
        # Create the CGpm.
        if not kwargs.get('supress', None):
            self.ripl.evaluate('(%s)' % ('make_cgpm' if sp is None else sp,))
        # Check correct outputs.
        if len(outputs) != len(self.ripl.sample('simulators')):
            raise ValueError('source.simulators list disagrees with outputs.')
        self.outputs = outputs
        # Check correct inputs.
        if len(inputs) != self.ripl.evaluate('(size inputs)'):
            raise ValueError('source.inputs list disagrees with inputs.')
        self.inputs = inputs
        # Check overriden observers.
        if len(self.outputs) != self.ripl.evaluate('(size observers)'):
            raise ValueError('source.observers list disagrees with outputs.')
        # Evidence and labels for incorporate/unincorporate.
        self.obs = defaultdict(lambda: defaultdict(dict))

    def incorporate(self, rowid, query, evidence=None):
        evidence = self._validate_incorporate(rowid, query, evidence)
        for q, value in query.iteritems():
            self._observe_cell(rowid, q, value, evidence)

    def unincorporate(self, rowid):
        if rowid not in self.obs:
            raise ValueError('Never incorporated: %d' % rowid)
        for q in self.outputs:
            self._forget_cell(rowid, q)
        assert len(self.obs[rowid]['labels']) == 0
        del self.obs[rowid]

    def logpdf(self, rowid, query, evidence=None):
        return 0

    def simulate(self, rowid, query, evidence=None, N=None):
        ev_in, ev_out = self._validate_simulate(rowid, query, evidence)
        # Observe output variables in evidence.
        for q,v in ev_out.iteritems():
            self._observe_cell(rowid, q, v, ev_in)
        # Run local inference in rowid scope, with 15 steps of MH.
        if ev_out:
            self.ripl.infer('(mh (atom %i) all %i)' % (rowid, 15))
        # Retrieve samples, with 5 steps of MH between predict.
        def retrieve_sample(q, l):
            # XXX Only run inference on the latent variables in the block.
            # self.ripl.infer('(mh (atom %i) all %i)' % (rowid, 5))
            return self._predict_cell(rowid, q, ev_in, l)
        labels = [self._gen_label() for q in query]
        samples = {q: retrieve_sample(q, l) for q, l in zip(query, labels)}
        # Forget predicted query variables.
        for label in labels:
            self.ripl.forget(label)
        # Forget output variables in evidence.
        for q, v in ev_out.iteritems():
            self._forget_cell(rowid, q)
        return samples

    def logpdf_score(self):
        raise NotImplementedError

    def transition(self, program=None, N=None):
        if program is None:
            num_iters = N if N is not None else 1
            self.ripl.infer('(transition %d)' % (num_iters,))
        else:
            self.ripl.execute_program(program)

    def to_metadata(self):
        metadata = dict()
        metadata['source'] = self.source
        metadata['outputs'] = self.outputs
        metadata['inputs'] = self.inputs
        metadata['mode'] = self.mode
        metadata['plugins'] = self.plugins
        # Save the observations. We need to convert integer keys to strings.
        metadata['obs'] = VsCGpm._obs_to_json(copy.deepcopy(self.obs))
        metadata['binary'] =  base64.b64encode(self.ripl.saves())
        metadata['factory'] = ('cgpm.venturescript.vscgpm', 'VsCGpm')
        return metadata

    @classmethod
    def from_metadata(cls, metadata, rng=None):
        ripl = vs.make_lite_ripl()
        ripl.loads(base64.b64decode(metadata['binary']))
        cgpm = VsCGpm(
            outputs=metadata['outputs'],
            inputs=metadata['inputs'],
            ripl=ripl,
            source=metadata['source'],
            mode=metadata['mode'],
            supress=True,
            plugins=metadata['plugins'],
            rng=rng,)
        # Restore the observations. We need to convert string keys to integers.
        # XXX Eliminate this terrible defaultdict hack. See Github #187.
        obs_converted = VsCGpm._obs_from_json(metadata['obs'])
        cgpm.obs = defaultdict(lambda: defaultdict(dict))
        for key, value in obs_converted.iteritems():
            cgpm.obs[key] = defaultdict(dict, value)
        return cgpm

    # --------------------------------------------------------------------------
    # Internal helpers.

    def _predict_cell(self, rowid, query, evidence, label):
        inputs = [evidence[i] for i in self.inputs]
        args = str.join(' ', map(str, [rowid] + inputs))
        i = self.outputs.index(query)
        return self.ripl.predict(
            '((lookup simulators %i) %s)' % (i, args), label=label)

    def _observe_cell(self, rowid, query, value, evidence):
        inputs = [evidence[i] for i in self.inputs]
        label = '\''+self._gen_label()
        args = str.join(' ', map(str, [rowid] + inputs + [value, label]))
        i = self.outputs.index(query)
        self.ripl.evaluate('((lookup observers %i) %s)' % (i, args))
        self.obs[rowid]['labels'][query] = label[1:]

    def _forget_cell(self, rowid, query):
        if query not in self.obs[rowid]['labels']: return
        label = self.obs[rowid]['labels'][query]
        self.ripl.forget(label)
        del self.obs[rowid]['labels'][query]

    def _gen_label(self):
        return 't%s%s' % (
            self.rng.randint(1,100),
            datetime.now().strftime('%Y%m%d%H%M%S%f'))

    def _validate_incorporate(self, rowid, query, evidence=None):
        if evidence is None: evidence = {}
        if not query:
            raise ValueError('No query: %s.' % query)
        # All evidence present, and no nan values.
        if rowid not in self.obs and set(evidence) != set(self.inputs):
            raise ValueError('Miss evidence: %s, %s' % (evidence, self.inputs))
        if not set.issubset(set(query), set(self.outputs)):
            raise ValueError('Unknown query: %s,%s' % (query, self.outputs))
        if any(math.isnan(evidence[i]) for i in evidence):
            raise ValueError('Nan evidence: %s' % evidence)
        if any(math.isnan(query[i]) for i in query):
            raise ValueError('Nan query (nan): %s' % query)
        # Evidence optional if (rowid,q) previously incorporated, or must match.
        if rowid in self.obs:
            if any(q in self.obs[rowid]['labels'] for q in query):
                raise ValueError('Observation exists: %d, %s' % (rowid, query))
            if evidence:
                self._check_matched_evidence(rowid, evidence)
        else:
            self.obs[rowid]['evidence'] = dict(evidence)
        return self.obs[rowid]['evidence']

    def _validate_simulate(self, rowid, query, evidence=None):
        if evidence is None: evidence = {}
        ev_in = {q:v for q,v in evidence.iteritems() if q in self.inputs}
        ev_out = {q:v for q,v in evidence.iteritems() if q in self.outputs}
        if rowid not in self.obs and set(ev_in) != set(self.inputs):
            raise ValueError('Missing evidence: %s, %s' % (ev_in, self.inputs))
        if any(math.isnan(evidence[i]) for i in evidence):
            raise ValueError('Nan evidence: %s' % evidence)
        if not all(i in self.inputs or i in self.outputs for i in evidence):
            raise ValueError('Unknown evidence: %s' % evidence)
        if rowid in self.obs:
            if ev_out and any(q in self.obs[rowid]['labels'] for q in ev_out):
                raise ValueError('Observation exists: %d, %s' % (rowid, query))
            if ev_in:
                self._check_matched_evidence(rowid, ev_in)
            else:
                ev_in = self.obs[rowid]['evidence']
        assert set(ev_in) == set(self.inputs)
        return ev_in, ev_out

    def _check_matched_evidence(self, rowid, evidence):
        # Avoid creating 'evidence' by the defaultdict.
        exists = (rowid in self.obs) and ('evidence' in self.obs[rowid])
        if exists and evidence != self.obs[rowid]['evidence']:
            raise ValueError(
                'Given evidence contradicts dataset: %d, %s, %s' %
                (rowid, evidence, self.obs[rowid]['evidence']))

    @staticmethod
    def _obs_to_json(obs):
        def convert_key_int_to_str(d):
            assert all(isinstance(c, int) for c in d)
            return {str(c): v for c, v in d.iteritems()}
        obs2 = convert_key_int_to_str(obs)
        for r in obs2:
            obs2[r]['evidence'] = convert_key_int_to_str(obs2[r]['evidence'])
            obs2[r]['labels'] = convert_key_int_to_str(obs2[r]['labels'])
        return obs2

    @staticmethod
    def _obs_from_json(obs):
        def convert_key_str_to_int(d):
            assert all(isinstance(c, (str, unicode)) for c in d)
            return {int(c): v for c, v in d.iteritems()}
        obs2 = convert_key_str_to_int(obs)
        for r in obs2:
            obs2[r]['evidence'] = convert_key_str_to_int(obs2[r]['evidence'])
            obs2[r]['labels'] = convert_key_str_to_int(obs2[r]['labels'])
        return obs2
