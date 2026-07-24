"""Backend op shim (WP-0401): ``xp = get_backend()`` in the hot path.

WP-0402 adds the jax backend: ``resolve_backend("jax")`` / ``set_backend("jax")``
import jax lazily, and ``jax_backend.make_jax_jacobian`` builds the chunked
jacfwd Jacobian callable (imported lazily by the solver, never here).

WP-0403 adds ``linalg64``: the fp64 host boundary every backend's Jacobian
crosses, and the :class:`MixedPrecisionPolicy` that decides whether columns
(and *only* columns) may be computed below fp64.
"""

from .api import (
    Backend,
    JaxBackend,
    NumpyBackend,
    get_backend,
    resolve_backend,
    set_backend,
)
from .linalg64 import (
    FP32_JACOBIAN,
    FP64,
    MixedPrecisionPolicy,
    get_precision_policy,
    precision_policy,
    require_fp64,
    set_precision_policy,
    to_host_fp64,
)

__all__ = ["Backend", "JaxBackend", "NumpyBackend", "get_backend",
           "resolve_backend", "set_backend",
           "FP32_JACOBIAN", "FP64", "MixedPrecisionPolicy",
           "get_precision_policy", "precision_policy", "require_fp64",
           "set_precision_policy", "to_host_fp64"]
