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

import math
import warnings

from math import lgamma
from math import log

import numpy as np

from cgpm.utils import validation as vu


colors = ['red', 'blue', 'green', 'magenta', 'orange', 'purple', 'brown',
    'black']

def gen_rng(seed=None):
    if seed is None:
        seed = np.random.randint(low=1, high=2**31)
    return np.random.RandomState(seed)

def curve_color(k):
    return (colors[k], .7) if k < len(colors) else ('gray', .3)

def merged(*dicts):
    result = {}
    for d in dicts:
        result.update(d)
    return result

def is_disjoint(*args):
    return not set.intersection(*(set(a) for a in args))

def log_normalize(logp):
    """Normalizes a np array of log probabilites."""
    return np.subtract(logp, logsumexp(logp))

def normalize(p):
    """Normalizes a np array of probabilites."""
    return np.asarray(p, dtype=float) / sum(p)

def logp_crp(N, Nk, alpha):
    """Returns the log normalized P(N,K|alpha), where N is the number of
    customers and K is the number of tables.
    https://www.cs.princeton.edu/~blei/papers/GershmanBlei2012.pdf#page=4 (eq 8)
    """
    return len(Nk)*log(alpha) + np.sum(lgamma(c) for c in Nk) \
        + lgamma(alpha) - lgamma(N+alpha)

def logp_crp_unorm(N, K, alpha):
    """Returns the log unnormalized P(N,K|alpha), where N is the number of
    customers and K is the number of tables. Use for effeciency to avoid
    computing terms that are not a function of alpha.
    """
    return K*log(alpha) + lgamma(alpha) - lgamma(N+alpha)

def logp_crp_gibbs(Nk, Z, i, alpha, m):
    """Compute the CRP probabilities for a Gibbs transition of customer i,
    with table counts Nk, table assignments Z, and m auxiliary tables."""
    # XXX F ME
    K = sorted(Nk) if isinstance(Nk, dict) else xrange(len(Nk))
    singleton = Nk[Z[i]] == 1
    m_aux = m-1 if singleton else m
    p_table_aux = alpha/float(m)
    p_current = lambda : p_table_aux if singleton else Nk[Z[i]]-1
    p_other = lambda t : Nk[t]
    p_table = lambda t: p_current() if t == Z[i] else p_other(t)
    return [log(p_table(t)) for t in K] + [log(p_table_aux)]*m_aux

def logp_crp_fresh(N, Nk, alpha, m=1):
    """Compute the CRP probabilities for a fresh customer i=N+1, with
    table counts Nk, total customers N=sum(Nk), and m auxiliary tables."""
    log_crp_numer = np.log(Nk + [alpha/m]*m)
    logp_crp_denom = log(N + alpha)
    return log_crp_numer - logp_crp_denom

def log_pflip(logp, array=None, size=None, rng=None):
    """Categorical draw from a vector logp of log probabilities."""
    p = np.exp(log_normalize(logp))
    return pflip(p, array=array, size=size, rng=rng)

def pflip(p, array=None, size=None, rng=None):
    """Categorical draw from a vector p of probabilities."""
    if array is None:
        array = range(len(p))
    if len(p) == 1:
        return array[0] if size is None else [array[0]] * size
    if rng is None:
        rng = gen_rng()
    p = normalize(p)
    if 10.**(-8.) < math.fabs(1.-sum(p)):
        warnings.warn('pflip probability vector sums to %f.' % sum(p))
    return rng.choice(array, size=size, p=p)

def logsumexp(array):
    # https://github.com/probcomp/bayeslite/blob/master/src/math_util.py
    if len(array) == 0:
        return float('-inf')
    m = max(array)

    # m = +inf means addends are all +inf, hence so are sum and log.
    # m = -inf means addends are all zero, hence so is sum, and log is
    # -inf.  But if +inf and -inf are among the inputs, or if input is
    # NaN, let the usual computation yield a NaN.
    if math.isinf(m) and min(array) != -m and \
       all(not math.isnan(a) for a in array):
        return m

    # Since m = max{a_0, a_1, ...}, it follows that a <= m for all a,
    # so a - m <= 0; hence exp(a - m) is guaranteed not to overflow.
    return m + math.log(sum(math.exp(a - m) for a in array))

def logmeanexp(array):
    # https://github.com/probcomp/bayeslite/blob/master/src/math_util.py
    inf = float('inf')
    if len(array) == 0:
        # logsumexp will DTRT, but math.log(len(array)) will fail.
        return -inf

    # Treat -inf values as log 0 -- they contribute zero to the sum in
    # logsumexp, but one to the count.
    #
    # If we pass -inf values through to logsumexp, and there are also
    # +inf values, then we get NaN -- but if we had averaged exp(-inf)
    # = 0 and exp(+inf) = +inf, we would sensibly get +inf, whose log
    # is still +inf, not NaN.  So strip -inf values first.
    #
    # Can't say `a > -inf' because that excludes NaNs, but we want to
    # include them so they propagate.
    noninfs = [a for a in array if not a == -inf]

    # probs = map(exp, logprobs)
    # log(mean(probs)) = log(sum(probs) / len(probs))
    #   = log(sum(probs)) - log(len(probs))
    #   = log(sum(map(exp, logprobs))) - log(len(logprobs))
    #   = logsumexp(logprobs) - log(len(logprobs))
    return logsumexp(noninfs) - math.log(len(array))

def logmeanexp_weighted(log_A, log_W):
    # https://github.com/probcomp/bayeslite/blob/master/src/math_util.py
    # Given log W_0, log W_1, ..., log W_{n-1} and log A_0, log A_1,
    # ... log A_{n-1}, compute
    #
    #   log ((W_0 A_0 + ... + W_{n-1} A_{n-1})/(W_0 + ... + W_{n-1}))
    #   = log (exp log (W_0 A_0) + ... + exp log (W_{n-1} A_{n-1}))
    #     - log (exp log W_0 + ... + exp log W_{n-1})
    #   = log (exp (log W_0 + log A_0) + ... + exp (log W_{n-1} + log A_{n-1}))
    #     - log (exp log W_0 + ... + exp log W_{n-1})
    #   = logsumexp (log W_0 + log A_0, ..., log W_{n-1} + log A_{n-1})
    #     - logsumexp (log W_0, ..., log W_{n-1})
    #
    # XXX Pathological cases -- infinities, NaNs.
    assert len(log_W) == len(log_A)
    return logsumexp([log_w + log_a for log_w, log_a in zip(log_W, log_A)]) \
        - logsumexp(log_W)

def log_linspace(a, b, n):
    """linspace from a to b with n entries over log scale."""
    return np.exp(np.linspace(log(a), log(b), n))

def log_nCk(n, k):
    """log(choose(n,k)) with overflow protection."""
    if n == 0 or k == 0 or n == k:
        return 0
    return log(n) + lgamma(n) - log(k) - lgamma(k) - log(n-k) - lgamma(n-k)

def simulate_crp(N, alpha, rng=None):
    """Generates random N-length partition from the CRP with parameter alpha."""
    if rng is None:
        rng = gen_rng()

    assert N > 0 and alpha > 0.
    alpha = float(alpha)

    partition = [0]*N
    Nk = [1]
    for i in xrange(1,N):
        K = len(Nk)
        ps = np.zeros(K+1)
        for k in xrange(K):
            ps[k] = float(Nk[k])
        ps[K] = alpha
        ps /= (float(i) - 1 + alpha)
        assignment = pflip(ps, rng=rng)
        if assignment == K:
            Nk.append(1)
        elif assignment < K:
            Nk[assignment] += 1
        else:
            raise ValueError("Invalid assignment: %i, max=%i" % (assignment, K))
        partition[i] = assignment

    assert max(partition)+1 == len(Nk)
    assert len(partition)==N
    assert sum(Nk) == N

    K = len(Nk)
    # if K > 1:
    #     rng.shuffle(partition)
    return partition

def simulate_crp_constrained(N, alpha, Cd, Ci, Rd, Ri, rng=None):
    """Simulates a CRP with N customers and concentration alpha. Cd is a list,
    where each entry is a list of friends. Ci is a list of tuples, where each
    tuple is a pair of enemies."""
    if rng is None:
        rng = gen_rng()

    vu.validate_crp_constrained_input(N, Cd, Ci, Rd, Ri)
    assert N > 0 and alpha > 0.

    # Initial partition.
    Z = [-1]*N

    # Friends dictionary from Cd.
    friends = {col:block for block in Cd for col in block}

    # Assign customers.
    for cust in xrange(N):
        if Z[cust] > -1: continue
        # Find valid tables for cust and friends.
        assert all(Z[f] == -1 for f in friends.get(cust, [cust]))
        prob_table = [0] * (max(Z)+1)
        for t in xrange(max(Z)+1):
            # Current customers at table t.
            t_custs = [i for i,z in enumerate(Z) if z==t]
            prob_table[t] = len(t_custs)
            # Does f \in {cust \union cust_friends} have an enemy in table t?
            for tc in t_custs:
                for f in friends.get(cust, [cust]):
                    if not vu.check_compatible_customers(Cd,Ci,Ri,Rd,f,tc):
                        prob_table[t] = 0
                        break
        # Choose from valid tables using CRP.
        prob_table.append(alpha)
        assignment = pflip(prob_table, rng=rng)
        for f in friends.get(cust, [cust]):
            Z[f] = assignment

    # At most N tables.
    assert all(0 <= t < N for t in Z)
    assert vu.validate_crp_constrained_partition(Z, Cd, Ci, Rd, Ri)
    return Z

def build_rowid_blocks(Zvr):
    A = np.asarray(Zvr).T
    U = map(tuple, A)
    return {u:np.where(np.all(A==u, axis=1))[0] for u in U}
