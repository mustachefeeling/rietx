# WP-1051 — Sequential escalation ladder + chain hygiene

Milestone: v1.0 (proposed 2026-07-30) · Status: ⬜
Depends on: —

## Goal

The warm-start chain's fallback becomes a three-rung ladder (warm-collapsed →
warm-staged → cold-staged), and a pattern that stays diverged after the last
rung is quarantined: flagged, excluded from the reseed statistics, and never
used to seed its successor.

## Context

SrRietveld's automation result (Tian *et al.* 2013, §3): in a warm-started
series the full staged scheme is usually unnecessary — run everything-at-once
and "the step-by-step scheme only turned on if a refinement diverges".
`sequential.py` already has the fast path as the *default* (`_collapse` unions
every stage's globs into one `"warm_refit"` stage; `refit="single"`) and one
fallback rung (`_reseed_needed` → refit **cold** with the full `base_plan`,
keep the better by `_better`). Three gaps, found by reading the chain flow on
2026-07-30:

- **No intermediate rung.** The ladder jumps from warm-collapsed straight to
  cold-staged, discarding the warm start entirely — yet warm + full
  `base_plan` is the cheap middle option (`refit="stages"` exists as a
  series-global switch, so the machinery is already there; measured on the
  IUCr ramp, staged-warm ≈ 904 iterations vs collapsed-warm 838 vs unchained
  2863 — the docstrings at `sequential.py:129-131` quote it). Ladder:
  warm-collapsed → warm-staged → cold-staged, each rung only on failure of
  the previous, keep-best across all attempts.
- **Chain hygiene defect.** A pattern whose cold refit *also* diverges still
  becomes `previous` for the next pattern and its Rwp still joins
  `accepted_rwp` (`sequential.py:426-430`) — so a doubly-failed pattern seeds
  its successor with garbage and drags the reseed median that decides every
  later trigger. Fix: the successor seeds from the last *accepted* pattern;
  the failed entry is flagged with a new `SEQUENTIAL_UNRECOVERED` diagnostic
  (level `"warning"` — the two existing sequential fences are `"info"`) and
  its Rwp is excluded from `accepted_rwp`.
- **Trigger inventory is narrow and undocumented.** Only
  `status == "diverged"` or `rwp > reseed_factor × median(accepted_rwp)`
  fire (`_reseed_needed`, `sequential.py:523-530`); guard firings
  (HIGH_CORRELATION, at-bounds…) and parameter jumps are inert as triggers.
  Decide and record — the likely answer is *keep* Rwp/divergence as the only
  automatic triggers (guards fire legitimately on converged patterns, and
  `SEQUENTIAL_DISCONTINUITY` is a post-hoc series property), but the decision
  belongs in the module docstring, not in silence.

Bookkeeping: `SeriesEntry` already carries `reseeded: bool` and `rwp_warm`;
extend to say *which rung won* (e.g. `rung: Literal["warm", "warm_staged",
"cold"]`, default `"warm"`) rather than a second boolean —
`schemas/sequential.py:30-78`, and the schema mirror tests will pin it.
`n_iterations` already sums all attempts (`sequential.py:414,420`); keep that
contract. `plot_trajectory` rings reseeded points — an unrecovered point
should render distinctly (or be documented as rendered-but-flagged).

## Non-goals

- Per-pattern plan control in the API (`plan`/`refit` stay series-global;
  `prepare` stays value-only).
- Agent-surface exposure of `reseed_factor` / the ladder (the
  `refine_sequential` task keeps its current fields).
- Protocol-ensemble accuracy estimates (running the chain under two
  background/profile models and quoting the spread, SrRietveld's two-engine
  device) — v2 idea, recorded here so it isn't relitigated.

## Tasks

- [ ] Ladder: insert the warm + `base_plan` rung in `_chain`'s reseed block;
      keep-best via `_better` across all rungs; `SeriesEntry.rung`.
- [ ] Hygiene: unrecovered pattern seeds nothing and joins no median;
      successor chains from last accepted; `SEQUENTIAL_UNRECOVERED`
      diagnostic (warning) with the rung history in `data`.
- [ ] Trigger decision recorded in the module docstring (and, if the answer
      changes, implemented + tested).
- [ ] Tests, `tests/test_sequential.py` style (synthetic series, forced
      `reseed_factor=1.0`): ladder tries rungs in order and stops at first
      success; keep-best bookkeeping; an injected unrecoverable pattern (e.g.
      corrupted y) is flagged, its successor's warm start comes from the last
      good pattern, and the reseed median ignores it; trajectory plot/CSV
      round-trip with the new field.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_acceptance_sequential.py -q
.venv/bin/python -m ruff check src tests examples
```

Criterion: the hygiene test passes (unrecovered pattern quarantined), and the
IUCr-ramp acceptance still converges every pattern with chained cost within
the measured range quoted in its module docstring (compare runs, not records).

## References

- Tian, P. *et al.* (2013). *J. Appl. Cryst.* **46**, 255–258.
  doi:10.1107/S0021889812045967 — SrRietveld;
  §3 for the diverge-then-escalate scheme and the two-engine dispersion idea
  fenced above.

## Handover log

- **2026-07-30** — created from the Toby 2024 / SrRietveld literature review;
  gaps verified against `sequential.py` control flow (anchors in Context).
