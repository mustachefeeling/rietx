"""Branchable refinement history: an append-only DAG of restorable states,
plus the per-iteration event stream emitted alongside it."""

from .aggregate import EventsSummary, summarize_events
from .events import EventRecord, EventStream, RunHeader, read_events
from .store import append_record, fingerprint, read_records
from .tree import RefinementTree

__all__ = [
    "EventRecord",
    "EventStream",
    "EventsSummary",
    "RefinementTree",
    "RunHeader",
    "append_record",
    "fingerprint",
    "read_events",
    "read_records",
    "summarize_events",
]
