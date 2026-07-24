"""Backend op shim (WP-0401): ``xp = get_backend()`` in the hot path."""

from .api import Backend, NumpyBackend, get_backend, set_backend

__all__ = ["Backend", "NumpyBackend", "get_backend", "set_backend"]
