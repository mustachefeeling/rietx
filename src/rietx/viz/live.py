"""Live monitoring session: an event log and a per-stage snapshot, in one
directory.

``LiveSession(directory)`` is passed as ``events=`` to ``Refinement.fit``. It
is an :class:`~rietx.history.events.EventStream` writing ``events.jsonl``, and
it additionally writes ``snapshot.json`` and ``status.json`` after every stage.
``rietx watch`` is a static file server with a polling page on top — no
websockets, no framework, the live view being a file that keeps getting
replaced.

**This module imports no plotting library**, and a test pins that by putting
``None`` into ``sys.modules["plotly"]`` and recording a run. Until WP-1402 it
wrote a self-contained plotly page per stage, which cost the fit megabytes of
serialisation on its own thread, cost the reader their zoom on every reload,
and meant a base install could not record a live view at all. The numbers go
to :mod:`rietx.viz.snapshot` now and the viewer draws them.

``fit.html`` is no longer written. ``rietx html`` and
:func:`~rietx.viz.html.write_html` are untouched, so the self-contained
emailable page stays a capability; what stopped is producing it unasked.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..history.events import EventStream
from .snapshot import write_snapshot


class LiveSession(EventStream):
    """Event stream + per-stage snapshot files in one directory."""

    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        # truncate any previous run's log so the console pane starts clean
        (self.dir / "events.jsonl").write_text("", encoding="utf-8")
        super().__init__(path=self.dir / "events.jsonl")

    def write_snapshot(self, model, table, outcome, stage_name: str) -> None:
        """Called by ``Refinement.fit`` after each stage commit."""
        payload = write_snapshot(self.dir, model, table, outcome, stage_name)
        # from the payload, never recomputed: one stage has one Rwp, and a
        # second computation of it is a second answer waiting to disagree
        stats = payload["statistics"]
        (self.dir / "status.json").write_text(json.dumps({
            "stage": payload["stage"], "rwp": stats["rwp"],
            "gof": stats["gof"], "chi2": stats["chi2"],
            "n_free": stats["n_free"],
        }, indent=1), encoding="utf-8")
