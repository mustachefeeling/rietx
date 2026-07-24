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

## Inherited

From **WP-0308** (multi-histogram, landed 2026-07-24) — it shipped, and it is
**not** the substrate for this WP. `MultiParameterTable` and
`run_multi_least_squares` build *one joint residual* over patterns that share
structural parameters; a sequential series is N separate refinements chained
pattern to pattern, so neither is reusable here. 0308 fenced it from its side.
The enabling piece stays history `cherry_pick`, as the pointer above says.

Two inherited constraints worth knowing before designing:

- **Multi-histogram fits deliberately run with history OFF** and do not enter
  the `RefinementTree` DAG — a multi-pattern fingerprint was judged a deeper
  change and left as a documented future seam. This WP is the opposite case: it
  is *built* on the DAG, one node chain per pattern, so it does not inherit
  that limitation but should not assume 0308 solved any of the persistence
  question either.
- **Rietveld only, upstream.** 0308 raises `NotImplementedError` for Le Bail
  and Pawley because per-pattern extracted intensities are not shared. A
  *sequential* Le Bail series has no such problem (each pattern is its own
  extraction), so that restriction does not carry over — but the per-node
  `ReflectionState` serialization that makes Le Bail restorable across a
  checkout is what this WP depends on for warm starts.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
