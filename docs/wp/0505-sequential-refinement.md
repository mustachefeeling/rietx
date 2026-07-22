# WP-0505 — SequentialRefinement with warm start

Milestone: v0.5 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- SequentialRefinement with warm start (in-situ series)

## Context pointers

- The enabling piece already shipped in v0.2: history `cherry_pick` replays a
  node's recorded stage *action* (not its values) on the current state — see
  `docs/milestones/v0.2.md` (History / events) and `history/tree.py`.
- Distinct from WP-0308: a series of separate refinements chained pattern to
  pattern, not one joint residual.
- `vmap`-batched series stays fenced in v2.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
