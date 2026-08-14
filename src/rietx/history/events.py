"""Per-iteration event stream — the live telemetry of a running refinement.

Same JSONL record style as the history log (a tagged ``record`` field per
line), but a *separate* file: history nodes are ~10 kB immutable checkpoints,
events are one-line heartbeats emitted from inside the least-squares loop.

The hot-loop invariant holds here too: :meth:`EventStream.emit` touches only
plain dicts and ``json.dumps`` — no pydantic anywhere near the residual.
:class:`EventRecord` (pydantic) exists for *reading* the log back with
validation, never for writing.

Event kinds (closed set, versioned with the schema):

* ``fit_start`` / ``fit_end`` — one refinement run (mode, plan, statistics);
* ``stage_start`` / ``stage_end`` — one staged-plan stage (freed paths, costs).
  ``stage_start`` carries ``index`` (**1-based**, so it reads "stage 3 of 5"
  directly) and ``n_stages``;
* ``eval`` — one residual evaluation inside scipy TRF (cost, eval counter).
  scipy exposes no per-iteration callback, so the residual closure itself is
  the hook; ``n_eval`` counts every call (function + finite-difference), which
  is exactly the quantity that tracks wall-clock progress;
* ``index_start`` / ``index_end`` — one **indexing** run (WP-1024).  A separate
  pair rather than a reuse of ``fit_start``/``fit_end`` because an indexing run
  has none of what a refinement run has: no mode, no Rwp, no history node.  What
  it *does* have is engines and systems, and those go on the open ``data`` dict —
  the progress in between is emitted as ``stage_start``/``stage_end`` with
  ``index``, ``n_stages``, ``engine`` and ``system``, so ``rietx watch``
  and the GUI's progress reporting need no new case at all.  Since WP-1037 that
  ladder is **flat and per (engine × system)** — plus a unit per dominant-zone
  probe rung and per validation fit — and its ``n_stages`` is **revisable
  mid-run**: probe and validation counts are unknowable at ``index_start``
  (the probe runs only after an empty search, the validation count only after
  consensus), so a consumer treats ``n_stages`` as the current best claim
  rather than a constant.  Revising a field's *value* is not a change of its
  meaning, so the additivity rule below holds and the version does not move.
  WP-1042 rides the same rule: every ladder emission carries
  ``elapsed_seconds`` (+ ``remaining_seconds`` under a declared ceiling), a
  finished search unit's ``stage_end`` carries ``provisional`` cells with no
  confidence field, and each completed system adds a ``consensus:<system>``
  unit whose ``stage_end`` carries the graded shortlist in the WP-1043
  evidence shape — added fields and added *units*, no new kind;

Every line carries ``t`` (Unix seconds) so a tail of the file doubles as a
progress bar; ``rietx watch`` renders it as the console pane.

**Adding a field to an existing kind does not bump**
:data:`EVENT_SCHEMA_VERSION`.  ``data`` is an open dict on both sides: readers
render whatever keys arrive (``watch.py`` iterates ``Object.entries``) and
:class:`EventRecord` validates the envelope, not the payload — so an older
reader tailing a newer log shows the new key and misses nothing it knew about.
A **new kind**, a **removed or renamed field**, or a change of a field's
*meaning* is what the version is for.  ``stage_start.index``/``n_stages``
(WP-1006) were added under exactly this rule; the note is here because the
reflex is to bump, and a version that moves for additive changes stops being
usable as a compatibility signal.  A cancelled run's ``fit_end`` carries
``status="cancelled"`` and *omits* ``rwp``/``gof`` — there is no fitted result
to report — which is the same rule seen from the reader's side: a consumer
reads ``data`` with ``.get``, never by unpacking a fixed shape.

**Version 2** (WP-1024) is the rule's other half made real:
``index_start``/``index_end`` are new *kinds*, so the constant moves.  WP-1006
declined to add them in advance precisely because a kind nothing emits is an
untested guess about a loop that did not exist; now the loop exists
(``index_pattern``) and emits them.  The per-engine progress inside the run
deliberately reuses ``stage_start``/``stage_end`` with extra ``data`` keys, which
is additive and would not have bumped anything on its own.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from ..schemas.common import Base

#: "2" since WP-1024 added the ``index_start``/``index_end`` kinds.  Read the
#: module docstring's additivity rule before changing it: a new kind bumps, an
#: added ``data`` field does not.
EVENT_SCHEMA_VERSION = "2"

EventKind = Literal["fit_start", "stage_start", "eval", "stage_end", "fit_end",
                    "index_start", "index_end"]


class EventRecord(Base):
    """A validated view of one event line — for readers, not the hot loop."""

    record: Literal["event"] = "event"
    v: str = EVENT_SCHEMA_VERSION
    t: float
    kind: EventKind
    data: dict[str, Any] = Field(default_factory=dict)


class EventStream:
    """Append-only JSONL sink (and/or a callback) for refinement events.

    ``path`` — file to append to (created; parent must exist).
    ``callback`` — called with each event dict after it is written; exceptions
    in the callback are the caller's problem (they propagate — a monitoring
    hook that crashes the refinement is a bug you want to see, not swallow).
    """

    def __init__(self, path: str | Path | None = None, callback=None):
        self.path = Path(path) if path is not None else None
        self.callback = callback
        self._fh = open(self.path, "a", encoding="utf-8") if self.path else None
        self.n_written = 0

    def emit(self, kind: str, **data: Any) -> None:
        event = {"record": "event", "v": EVENT_SCHEMA_VERSION,
                 "t": time.time(), "kind": kind, "data": data}
        if self._fh is not None:
            self._fh.write(json.dumps(event) + "\n")
            self._fh.flush()
        if self.callback is not None:
            self.callback(event)
        self.n_written += 1

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "EventStream":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def as_event_stream(events) -> EventStream | None:
    """Normalise the ``events=`` argument of ``Refinement.fit``."""
    if events is None or isinstance(events, EventStream):
        return events
    if callable(events):
        return EventStream(callback=events)
    return EventStream(path=events)


def read_events(path: str | Path) -> list[EventRecord]:
    """Read an event log back, validating each line."""
    out: list[EventRecord] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(EventRecord.model_validate_json(line))
    return out
