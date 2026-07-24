"""Backend op shim — the small array-op vocabulary the hot path speaks.

The forward model, structure factor, lattice and profile code call ``xp.*``
(``xp = get_backend()``) instead of bare ``np.*``, so that an autodiff backend
(jax, WP-0402; torch, WP-0408) can be swapped in without per-call branching.
Design record: docs/DESIGN.md ("locked decisions" — backend namespace object,
one autodiff backend at a time; "risks" — backend drift is contained by keeping
this vocabulary minimal and cross-testing every backend against numpy).

Discipline
----------
* **Every op added here is a per-backend maintenance liability.**  Add one only
  when hot-path code genuinely needs it; compile-time code (window edges,
  quadrature node placement, design matrices, the TRF driver, statistics)
  stays plain numpy and must not acquire ``xp`` calls.
* The numpy backend's attributes *are* the numpy functions — zero overhead, so
  the numpy path cannot regress.  Hot-loop code binds ``xp = get_backend()``
  once per compiled-model call, never per op.
* Python operators (``+ * / @ **``) and array methods (``.sum()``, ``.real``)
  are already backend-polymorphic and are NOT part of the vocabulary.
* ``einsum`` must support the five signatures the model uses:
  ``"nk,mkc->mnc"`` (transposed-rotation indices), ``"mnc,cd,mnd->mn"``
  (anisotropic Debye-Waller), ``"ni,ij,nj->n"`` (d-spacings),
  ``"mi,ij,mj->m"`` (March-Dollase angles), ``"i,in->n"`` (form factors).
* Complex is first-class: ``exp`` must accept complex128, and ``conj``/
  ``real``/``imag`` exist for the structure factor.  complex128 on host; a
  reduced-precision policy is WP-0403's business, not this module's.
* No ``scipy.special``: the hot path has none today; the WP-0405 Faddeeva
  profile is built *on* this op set, not into it.

Scatter primitives
------------------
``window_add(y, i0, i1, vals)`` is THE scatter op.  The residual only ever
accumulates onto *contiguous frozen windows* whose bounds ``(i0, i1)`` are
python ints fixed at stage compile — legal static slice bounds under tracing.
Deliberately NOT a general index-array scatter: data-dependent indices are
exactly what the frozen-per-stage discreteness invariant exists to forbid.
The signature is functional — callers must thread the return value
(``y = xp.window_add(y, i0, i1, vals)``); the numpy implementation mutates
``y`` in place and returns it, immutable-array backends return a new array.

``segment_sum(vals, seg_ids, n)`` sums ``vals`` into ``n`` buckets keyed by the
frozen integer map ``seg_ids`` (the March-Dollase orbit average).  numpy:
``bincount(weights=...)``; jax: ``segment_sum``; torch: ``index_add``.
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np


class Backend(Protocol):
    """Structural type of a backend namespace (attributes are array ops)."""

    name: str
    pi: float
    linalg: Any  # .inv and .det on stacks of small (3×3) matrices

    # elementwise (exp complex-capable)
    exp: Any
    sqrt: Any
    log: Any
    sin: Any
    cos: Any
    tan: Any
    arcsin: Any
    arccos: Any
    radians: Any
    degrees: Any
    abs: Any
    sign: Any
    power: Any
    clip: Any
    maximum: Any
    minimum: Any
    where: Any
    isfinite: Any
    # reductions / linear algebra
    einsum: Any
    matmul: Any
    sum: Any
    cumsum: Any
    diff: Any
    # construction
    asarray: Any
    zeros: Any
    zeros_like: Any
    full_like: Any
    concatenate: Any
    stack: Any
    # complex support
    conj: Any
    real: Any
    imag: Any

    def window_add(self, y: Any, i0: int, i1: int, vals: Any) -> Any:
        """Return ``y`` with ``vals`` added on the static window ``[i0, i1)``."""
        ...

    def segment_sum(self, vals: Any, seg_ids: Any, n: int) -> Any:
        """Sum ``vals`` into ``n`` buckets keyed by the frozen ``seg_ids``."""
        ...


class NumpyBackend:
    """The reference backend: attributes *are* numpy functions (fp64 host)."""

    name = "numpy"
    pi = np.pi
    linalg = np.linalg

    exp = staticmethod(np.exp)
    sqrt = staticmethod(np.sqrt)
    log = staticmethod(np.log)
    sin = staticmethod(np.sin)
    cos = staticmethod(np.cos)
    tan = staticmethod(np.tan)
    arcsin = staticmethod(np.arcsin)
    arccos = staticmethod(np.arccos)
    radians = staticmethod(np.radians)
    degrees = staticmethod(np.degrees)
    abs = staticmethod(np.abs)
    sign = staticmethod(np.sign)
    power = staticmethod(np.power)
    clip = staticmethod(np.clip)
    maximum = staticmethod(np.maximum)
    minimum = staticmethod(np.minimum)
    where = staticmethod(np.where)
    isfinite = staticmethod(np.isfinite)

    einsum = staticmethod(np.einsum)
    matmul = staticmethod(np.matmul)
    sum = staticmethod(np.sum)
    cumsum = staticmethod(np.cumsum)
    diff = staticmethod(np.diff)

    asarray = staticmethod(np.asarray)
    zeros = staticmethod(np.zeros)
    zeros_like = staticmethod(np.zeros_like)
    full_like = staticmethod(np.full_like)
    concatenate = staticmethod(np.concatenate)
    stack = staticmethod(np.stack)

    conj = staticmethod(np.conj)
    real = staticmethod(np.real)
    imag = staticmethod(np.imag)

    @staticmethod
    def window_add(y: np.ndarray, i0: int, i1: int, vals: np.ndarray) -> np.ndarray:
        # in-place is safe here: callers own y (freshly created accumulation
        # buffer) and thread the return value per the functional contract
        y[i0:i1] += vals
        return y

    @staticmethod
    def segment_sum(vals: np.ndarray, seg_ids: np.ndarray, n: int) -> np.ndarray:
        return np.bincount(seg_ids, weights=vals, minlength=n)


_BACKEND: Backend = NumpyBackend()


def get_backend() -> Backend:
    """The active backend namespace (bind once per compiled-model call)."""
    return _BACKEND


def set_backend(backend: Backend) -> None:
    """Install a backend namespace globally (one backend at a time — see
    docs/DESIGN.md).  The staged runner flips this per refinement; user code
    should not need to call it directly."""
    global _BACKEND
    _BACKEND = backend
