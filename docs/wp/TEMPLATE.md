# WP-NNNN — <title>

Milestone: v0.X · Status: ⬜ not started
Depends on: WP-MMMM (or —)

<!--
Status values: ⬜ not started · 🔶 in progress · ✅ shipped.
Keep the Status line here and the WP's row in ../ROADMAP.md in sync.
A WP file must be self-contained: a session that reads ONLY this file
(plus the auto-loaded CLAUDE.md) can start work. Link specific DESIGN.md
sections instead of restating them, but restate anything short and
load-bearing (a formula, a threshold, a fence) directly.
-->

## Goal

1–2 sentences: what exists, and works, when this WP is done.

## Context

Everything a fresh session needs and cannot get from CLAUDE.md alone:
- Source files to touch, and the seams to extend.
- Relevant invariants (link `../DESIGN.md#...` sections; restate the short ones).
- Prior measured findings that constrain the design.
- Licensing fences (what may be ported, what is concepts-only).

## Non-goals

Explicit fences: what looks adjacent but belongs to another WP or milestone.

## Tasks

Each item ≈ one commit, independently landable, prefixed in the commit
message with the WP id (`WP-NNNN: ...`). Check off as they land.

- [ ] ...
- [ ] ...
- [ ] Tests (unit/property; acceptance if this WP carries it) + obs/calc/diff PNGs to `tests/output/`

## Acceptance

Measurable criterion + the exact command(s) that verify it, e.g.:

```sh
.venv/bin/python -m pytest tests/test_xxx.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

Papers (author, year, journal), datasets, cross-code targets.

## Handover log

Append-only, newest first. An entry is REQUIRED before ending any session
that touched this WP — done / in flight / next / gotchas.

- **YYYY-MM-DD** — created.
