"""Linear regression model y = w . x trained with mini-batch SGD, and FedAvg."""
import numpy as np

from .dataset import N_FEATURES


def init_weights():
    return np.zeros(N_FEATURES)


def local_train(w, X, y, epochs=5, lr=0.01, batch=32, seed=0):
    """Train starting from the weights w using ONLY the local data. Returns new weights."""
    rng = np.random.default_rng(seed)
    w = w.copy()
    for _ in range(epochs):
        idx = rng.permutation(len(X))
        for i in range(0, len(X), batch):
            b = idx[i:i + batch]
            grad = 2 * X[b].T @ (X[b] @ w - y[b]) / len(b)      # gradient of the MSE
            w -= lr * grad
    return w


def mae(w, X, y):
    return float(np.mean(np.abs(X @ w - y)))


def fedavg(updates):
    """updates = [(weights, n_samples), ...]  ->  average weighted by the amount of data."""
    total = sum(n for _, n in updates)
    return sum(w * (n / total) for w, n in updates)
