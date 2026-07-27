"""WP-0408 torch backend: op contract and process isolation.

Everything here needs torch (``pytest.importorskip``) except the claim the
subprocess test proves: a numpy-only *process* never imports torch.

The cross-backend *agreement matrix* deliberately does not live here — it lives
in ``tests/test_cross_backend.py``, whose ``"torch"`` row this WP activates.
What is here is what that matrix cannot express: the op-level contract, process
isolation, and the device-specific claims.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from pxrdref.backend import resolve_backend  # noqa: E402
from pxrdref.backend.api import _OP_NAMES, NumpyBackend  # noqa: E402

_MPS = torch.backends.mps.is_available()
requires_mps = pytest.mark.skipif(not _MPS, reason="no Apple GPU / MPS build")


# ----------------------------------------------------------------------
# the op contract
# ----------------------------------------------------------------------
def test_every_shim_op_is_implemented():
    """The whole WP-0401 vocabulary, present and callable.

    ``_OP_NAMES`` is the shared tuple the Protocol is written from, so a new op
    added for one backend cannot silently go missing on this one.
    """
    xp = resolve_backend("torch")
    missing = [op for op in _OP_NAMES if not callable(getattr(xp, op, None))]
    assert not missing, f"TorchBackend is missing shim ops: {missing}"
    assert callable(xp.linalg.inv) and callable(xp.linalg.det)
    assert xp.pi == np.pi


def test_ops_accept_numpy_arguments_and_match_numpy():
    """torch ops take tensors only, so the backend coerces — and the coercion
    must not change any value.  This is the property the hot path relies on when
    it hands a frozen numpy constant to ``xp.*``."""
    xp, npb = resolve_backend("torch"), NumpyBackend()
    a = np.array([0.25, 1.5, 4.0])
    b = np.array([2.0, 0.5, -1.0])
    m = np.array([[4.0, 1.0], [1.0, 3.0]])
    cases = {
        "exp": (xp.exp(a), npb.exp(a)),
        "sqrt": (xp.sqrt(a), npb.sqrt(a)),
        "log": (xp.log(a), npb.log(a)),
        "radians": (xp.radians(a), npb.radians(a)),
        "degrees": (xp.degrees(a), npb.degrees(a)),
        "sign": (xp.sign(b), npb.sign(b)),
        "power": (xp.power(a, 1.5), npb.power(a, 1.5)),
        "clip": (xp.clip(b, 0.0, 1.0), npb.clip(b, 0.0, 1.0)),
        "maximum": (xp.maximum(a, 1.0), npb.maximum(a, 1.0)),
        "minimum": (xp.minimum(a, b), npb.minimum(a, b)),
        "where": (xp.where(a > 1.0, a, 0.0), npb.where(a > 1.0, a, 0.0)),
        "matmul": (xp.matmul(m, a[:2]), npb.matmul(m, a[:2])),
        "einsum": (xp.einsum("ni,ij,nj->n", m, m, m), npb.einsum("ni,ij,nj->n", m, m, m)),
        "sum": (xp.sum(a), npb.sum(a)),
        "cumsum": (xp.cumsum(a), npb.cumsum(a)),
        "diff": (xp.diff(a), npb.diff(a)),
        "stack": (xp.stack([a, b]), npb.stack([a, b])),
        "concatenate": (xp.concatenate([a, b]), npb.concatenate([a, b])),
        "full_like": (xp.full_like(a, 2.5), npb.full_like(a, 2.5)),
        "inv": (xp.linalg.inv(m), npb.linalg.inv(m)),
        "det": (xp.linalg.det(m), npb.linalg.det(m)),
    }
    for name, (got, want) in cases.items():
        np.testing.assert_allclose(np.asarray(got), want, rtol=1e-12, atol=1e-14,
                                   err_msg=f"op {name}")
    assert xp.isfinite(np.array([1.0, np.inf])).tolist() == [True, False]


def test_complex_ops_match_numpy():
    """The structure factor's complex path: ``exp`` of an imaginary argument,
    ``conj``, ``real`` — and ``imag`` of a *real* array, which torch's own
    ``imag`` refuses but numpy returns as zeros."""
    xp, npb = resolve_backend("torch"), NumpyBackend()
    z = np.array([0.3 + 0.4j, -1.0 + 2.0j])
    np.testing.assert_allclose(np.asarray(xp.exp(z)), npb.exp(z), rtol=1e-12)
    np.testing.assert_allclose(np.asarray(xp.conj(z)), npb.conj(z), rtol=1e-12)
    # |F|² the way structure_factors_squared spells it — the traced F on the
    # left, which is the rule the module docstring states
    zt = xp.asarray(z)
    np.testing.assert_allclose(np.asarray(xp.real(zt * xp.conj(zt))),
                               npb.real(z * npb.conj(z)), rtol=1e-12)
    real = np.array([1.0, 2.0])
    np.testing.assert_array_equal(np.asarray(xp.imag(real)), npb.imag(real))
    assert xp.zeros(3, dtype=np.complex128).dtype == torch.complex128


def test_scatter_primitives_are_functional():
    """``window_add``/``segment_sum`` via out-of-place ``index_add``: a NEW
    tensor, input untouched (the WP-0401 contract for immutable backends)."""
    xp = resolve_backend("torch")
    y = torch.zeros(6, dtype=torch.float64)
    out = xp.window_add(y, 2, 5, np.array([1.0, 2.0, 3.0]))
    assert out is not y
    assert np.allclose(np.asarray(y), 0.0)
    assert np.allclose(np.asarray(out), [0, 0, 1, 2, 3, 0])

    vals = np.array([1.0, 2.0, 4.0, 8.0, 16.0])
    seg = np.array([0, 2, 2, 0, 3])
    got = np.asarray(xp.segment_sum(vals, seg, 5))
    np.testing.assert_array_equal(got, np.bincount(seg, weights=vals, minlength=5))


def test_dtype_is_bound_once_per_instance():
    """WP-0401's "bind once, not per op": device and dtype are fixed by the
    instance, so a ``dtype=np.float64`` request from the hot path is honoured by
    *kind* — which on MPS means fp32, the whole point of the device."""
    cpu = resolve_backend("torch")
    assert cpu.asarray(np.zeros(2), dtype=np.float64).dtype == torch.float64
    assert cpu.asarray(np.zeros(2, dtype=np.complex128)).dtype == torch.complex128
    if _MPS:
        mps = resolve_backend("torch-mps")
        assert mps.asarray(np.zeros(2), dtype=np.float64).dtype == torch.float32
        assert mps.zeros(2, dtype=np.complex128).dtype == torch.complex64
        assert mps.device.type == "mps"


def test_backends_are_cached_and_named():
    assert resolve_backend("torch") is resolve_backend("torch")
    assert resolve_backend("torch").name == "torch"
    if _MPS:
        assert resolve_backend("torch-mps") is resolve_backend("torch-mps")
        assert resolve_backend("torch-mps") is not resolve_backend("torch")
        assert resolve_backend("torch-mps").name == "torch-mps"


# ----------------------------------------------------------------------
# isolation
# ----------------------------------------------------------------------
def test_numpy_only_process_never_imports_torch():
    """torch is a ~500 MB import; a numpy-path refinement must never trigger it
    (the WP-0402 claim for jax, restated for the second optional backend)."""
    code = """
import sys
import numpy as np
import pxrdref as pr
from pxrdref.model.forward import compile_model
from pxrdref.params.vector import ParameterTable

structure = pr.Structure(phases=[pr.Phase(
    name="LaB6", space_group="P m -3 m", cell=pr.Cell.cubic(4.1568),
    atoms=[pr.Atom(label="La", species="La", x=pr.Parameter(value=0.0),
                   y=pr.Parameter(value=0.0), z=pr.Parameter(value=0.0),
                   biso=pr.Parameter(value=0.4))],
    scale=pr.Parameter(value=1e-4, min=0.0, transform="softplus"))])
instrument = pr.Instrument.debye_scherrer(wavelength=1.5406)
tt = np.arange(15.0, 60.0, 0.05)
pattern = pr.PatternData(two_theta=tt.tolist(), intensity=[50.0] * len(tt))
table = ParameterTable(structure, instrument)
model = compile_model(structure, instrument, pattern)
model.evaluate(table.decode(table.x0()))
assert "torch" not in sys.modules, "numpy-only path imported torch"
"""
    proc = subprocess.run([sys.executable, "-c", code],
                          cwd=Path(__file__).parent.parent,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
