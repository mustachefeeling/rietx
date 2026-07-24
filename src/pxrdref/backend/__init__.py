"""Backend op shim (WP-0401): ``xp = get_backend()`` in the hot path.

WP-0402 adds the jax backend: ``resolve_backend("jax")`` / ``set_backend("jax")``
import jax lazily, and ``jax_backend.make_jax_jacobian`` builds the chunked
jacfwd Jacobian callable (imported lazily by the solver, never here).
"""

from .api import (
    Backend,
    JaxBackend,
    NumpyBackend,
    get_backend,
    resolve_backend,
    set_backend,
)

__all__ = ["Backend", "JaxBackend", "NumpyBackend", "get_backend",
           "resolve_backend", "set_backend"]
