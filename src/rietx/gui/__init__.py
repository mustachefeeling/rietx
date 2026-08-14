"""The human GUI: a session model, and a localhost server over it (WP-1008).

``rietx gui my_sample.rex`` serves the app; ``GuiSession`` is the whole
surface it serves.  The split is the point — see :mod:`rietx.gui.session` for
why every verb lives there and nothing about HTTP does.
"""

from __future__ import annotations

from .imports import MAX_UPLOAD_BYTES, UPLOAD_KINDS, UploadStore
from .server import DEFAULT_PORT, ROUTES, UPLOAD_ROUTES, build_server, main, serve
from .session import EVENT_RING, RESERVED_ROUTES, GuiError, GuiSession, RunState

__all__ = [
    "DEFAULT_PORT",
    "EVENT_RING",
    "GuiError",
    "GuiSession",
    "MAX_UPLOAD_BYTES",
    "RESERVED_ROUTES",
    "ROUTES",
    "RunState",
    "UPLOAD_KINDS",
    "UPLOAD_ROUTES",
    "UploadStore",
    "build_server",
    "main",
    "serve",
]
