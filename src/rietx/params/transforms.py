"""Reparameterisations between internal (optimiser) and physical values.

``softplus`` keeps strictly-positive quantities (widths, scale factors) away
from a hard zero bound: p = log(1 + e^u) is smooth, monotonic, and p > 0 for
all finite u, so the optimiser works in an unconstrained variable.
"""

from __future__ import annotations

import numpy as np

_SOFTPLUS_MIN = 1e-12


def _sigmoid(u: float) -> float:
    """1/(1+e^−u), evaluated in the branch that cannot overflow."""
    if u >= 0.0:
        return float(1.0 / (1.0 + np.exp(-u)))
    e = np.exp(u)
    return float(e / (1.0 + e))


def to_physical(u: float, kind: str) -> float:
    if kind == "identity":
        return u
    if kind == "softplus":
        return float(np.logaddexp(0.0, u))  # log(1 + e^u), overflow-safe
    if kind == "exp":
        return float(np.exp(u))
    if kind == "logit":
        return _sigmoid(u)
    raise ValueError(f"unknown transform {kind!r}")


def to_internal(p: float, kind: str) -> float:
    if kind == "identity":
        return p
    if kind == "softplus":
        p = max(p, _SOFTPLUS_MIN)
        # inverse softplus: u = log(e^p − 1) = p + log(1 − e^−p)
        return float(p + np.log(-np.expm1(-p)))
    if kind == "exp":
        return float(np.log(max(p, _SOFTPLUS_MIN)))
    if kind == "logit":
        p = min(max(p, _SOFTPLUS_MIN), 1.0 - _SOFTPLUS_MIN)
        return float(np.log(p / (1.0 - p)))
    raise ValueError(f"unknown transform {kind!r}")


def dphys_dinternal(u: float, kind: str) -> float:
    """dp/du — the chain-rule factor for esd propagation."""
    if kind == "identity":
        return 1.0
    if kind == "softplus":
        return _sigmoid(u)
    if kind == "exp":
        return float(np.exp(u))
    if kind == "logit":
        s = _sigmoid(u)
        return float(s * (1.0 - s))
    raise ValueError(f"unknown transform {kind!r}")


def internal_bounds(lo: float, hi: float, kind: str) -> tuple[float, float]:
    """Map physical bounds into the internal space (transforms are monotonic)."""
    if kind == "identity":
        return lo, hi
    ilo = -np.inf if lo <= _SOFTPLUS_MIN else to_internal(lo, kind)
    ihi = np.inf if not np.isfinite(hi) else to_internal(hi, kind)
    return ilo, ihi
