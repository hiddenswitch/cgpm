import math
from math import log

import numpy as np
import matplotlib.pyplot as plt
from scipy.special import betaln

import gpmcc.utils.general as gu

class Binomial(object):
    """Binomial data type with beta prior on binomial parameter theta.

    Does not require additional argumets (distargs=None).
    All X values should be 1. or 0.
    """

    cctype = 'binomial'

    def __init__(self, N=0, k=0, alpha=1, beta=1, distargs=None):
        """Optional arguments:
        -- N: number of datapoints
        -- k: number of hits (1)
        -- alpha: beta hyperparameter
        -- beta: beta hyperparameter
        -- distargs: not used
        """
        # Sufficient statistics.
        self.N = N
        self.k = k
        # Hyperparameter.
        self.alpha = alpha
        self.beta = beta

    def set_hypers(self, hypers):
        assert hypers['alpha'] > 0
        assert hypers['beta'] > 0
        self.alpha = hypers['alpha']
        self.beta = hypers['beta']

    def transition_params(self, prior=False):
        return

    def insert_element(self, x):
        assert x == 1.0 or x == 0.0
        self.N += 1
        self.k += x

    def remove_element(self, x):
        assert x == 1. or x == 0.
        self.N -= 1
        self.k -= x

    def predictive_logp(self, x):
        return Binomial.calc_predictive_logp(x, self.N, self.k, self.alpha,
            self.beta)

    def marginal_logp(self):
        return Binomial.calc_marginal_logp(self.N, self.k, self.alpha,
            self.beta)

    def singleton_logp(self, x):
        return Binomial.calc_predictive_logp(x, 0, 0, self.alpha, self.beta)

    def predictive_draw(self):
        if np.random.random() < self.alpha / (self.alpha + self.beta):
            return 1.
        else:
            return 0.

    @staticmethod
    def construct_hyper_grids(X, n_grid=30):
        grids = dict()
        grids['alpha'] = gu.log_linspace(1./float(len(X)), float(len(X)),
            n_grid)
        grids['beta'] = gu.log_linspace(1./float(len(X)), float(len(X)),
            n_grid)
        return grids


    @staticmethod
    def calc_predictive_logp(x, N, k, alpha, beta):
        if int(x) not in [0, 1]:
            return float('-inf')
        log_denom = log(N + alpha + beta)
        if x == 1.0:
            return log(k + alpha) - log_denom
        else:
            return log(N - k + beta) - log_denom

    @staticmethod
    def calc_marginal_logp(N, k, alpha, beta):
        return gu.log_nchoosek(N, k) + betaln(k + alpha, N - k + beta) \
            - betaln(alpha, beta)

    @staticmethod
    def calc_hyper_logps(clusters, grid, hypers, target):
        lps = []
        for g in grid:
            hypers[target] = g
            lp = sum(Binomial.calc_marginal_logp(cluster.N, cluster.k,
                **hypers) for cluster in clusters)
            lps.append(lp)
        return lps

    @staticmethod
    def plot_dist(X, clusters, distargs=None, ax=None, Y=None, hist=True):
        # Create a new axis?
        if ax is None:
            _, ax = plt.subplots()
        # Set up x axis.
        X_hist = np.histogram(X,bins=2)[0]
        X_hist = X_hist/float(len(X))
        # Compute weighted pdfs
        Y = [0, 1]
        K = len(clusters)
        pdf = np.zeros((K, 2))
        ax.bar(Y, X_hist, color='black', alpha=1, edgecolor='none')
        W = [log(clusters[k].N) - log(float(len(X))) for k in xrange(K)]
        if math.fabs(sum(np.exp(W)) -1.) > 10. ** (-10.):
            import ipdb; ipdb.set_trace()
        for k in xrange(K):
            pdf[k, :] = np.exp([W[k] + clusters[k].predictive_logp(y)
                    for y in Y])
            color, alpha = gu.curve_color(k)
            ax.bar(Y, pdf[k,:], color=color, edgecolor='none', alpha=alpha)
        # Plot the sum of pdfs.
        ax.bar(Y, np.sum(pdf, axis=0), color='none', edgecolor="red",
            linewidth=3)
        ax.set_xlim([-.1,1.9])
        ax.set_ylim([0,1.0])
        # Title
        ax.set_title(clusters[0].cctype)
        return ax
