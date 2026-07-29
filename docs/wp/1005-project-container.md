# WP-1005 — Project container

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1004

## Goal

A `.pxrd/` project directory that holds everything a refinement session is —
model, pattern bytes, history, UI state — creatable, openable and savable
through `Project.create/open/save`, so the GUI (and anyone else) has one
durable thing to point at instead of four loose files.

## Context

- **A directory, not a zip.** The history JSONL's crash-safety story is
  append-only writes by one writer; zipping would force rewrite-on-save and
  lose it. Layout: `project.json`, a **verbatim copy of the pattern file**
  (original bytes — the readers' esd-column semantics must survive, and
  `io/readers.py:6` says the esd column is never overridden, so the bytes are
  the contract), `history.jsonl`, `live/`, `exports/`.
- `schemas/project.py`: `DataRef` (relative filename, sha256, format,
  n_points, range); `ProjectDoc` (structure, instrument, mode, plan, limits,
  `patterns: list[DataRef]` — **length 1 in v1**, the designed-for
  multi-histogram seam — `history_file`, `ui: dict`). Schema conventions
  apply: `extra="forbid"`, `ser_json_inf_nan="strings"` — ±inf bounds must
  survive the JSON round-trip and are tested.
- `src/pxrdref/project.py`: `Project.create/open/save`. `open()` re-reads the
  pattern via `io.readers.read_pattern` (`io/readers.py:21`), checks the file
  sha256 against `DataRef.sha256`, and cross-checks
  `TreeHeader.data_fingerprint` (`schemas/history.py:213` — sha256 over
  two_theta + intensity bytes, set at `history/tree.py:60`). A mismatch is a
  **hard error**: `replay` already enforces exactly this rule at
  `refine.py:1380`, and a project that silently rebound a history tree to
  different data would be the confident-wrong-singleton failure one level up.
- `ui: dict` is deliberately untyped at this layer — the GUI owns its keys
  (Simple/Advanced toggle, panel layout); the container just persists them.

### Inherited

From **WP-1004**: `ParameterRow` and the unified `PlanSpec` in
`schemas/plan.py` are what `ProjectDoc.plan` stores — do not re-declare a
plan shape here.

## Non-goals

- No multi-pattern projects (the `list[DataRef]` seam exists; length > 1 is
  a later milestone's work, alongside multi-histogram GUI).
- No server, no locking across processes — one project per process is
  WP-1008's session rule, not this container's.
- No migration tooling for foreign formats (GSAS `.gpx` import etc.).

## Tasks

- [ ] `schemas/project.py`: `DataRef` + `ProjectDoc`, with the ±inf
      round-trip test alongside the existing schema tests.
- [ ] `src/pxrdref/project.py`: `Project.create` (copies pattern bytes,
      computes sha256, writes `project.json`, initialises `history.jsonl`,
      `live/`, `exports/`).
- [ ] `Project.open`: re-read via `read_pattern`, sha256 check,
      `data_fingerprint` cross-check — mismatch raises; re-open mid-history
      resumes at head.
- [ ] `Project.save`: persists `ProjectDoc` (model state + ui), never
      rewrites the pattern bytes or the JSONL.
- [ ] `tests/test_project.py`: round-trip incl. ±inf bounds, fingerprint
      mismatch raises, re-open mid-history resumes at head, esd column
      survives the copy (read the copy, compare weights).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_project.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- `refine.py:1380` — the fingerprint-mismatch rule this container extends
  from replay to open.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.
