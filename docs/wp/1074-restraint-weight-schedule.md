# WP-1074 — The restraint weight schedule: c_w per stage

Milestone: v1.0.x · Status: ⬜
Depends on: WP-0406 (the restraint rows this scales) — post-freeze is fine:
one additive defaulted `Stage` field

## Goal

A stage can scale every restraint's weight, so a plan starts stiff and
relaxes as the model improves — eq (7)'s c_w, per McCusker §8. Gap 6 of the
McCusker audit (`../milestones/v1.0.md` § Appendix).

## Context

- **The prescription** (§8): the refinement minimises S = S_y + c_w·S_G, and
  c_w "is set high at the beginning … [and] can then be reduced during the
  course of the refinement". Today `weight` is per-restraint and static
  (`model/restraints.py`: rows are √weight·(computed − target)/σ), and
  `Stage` (`schemas/plan.py`) has no restraint field, so a schedule needs N
  hand-edited copies of the model between fits.
- **The shape**: one scalar per stage multiplying every restraint row's
  weight, applied at stage compile — constant within a stage, changed only
  between stages, which is frozen-per-stage discreteness applied as designed
  rather than an exception to it.
- **Default is the identity.** `None`/1.0 leaves every existing plan and
  every pinned number bit-identical — the dispersion lesson: a moved default
  moves suites that thought they pinned a protocol. No preset adopts a
  schedule in this WP; `mccusker_structural` may, later, with a measurement.
- **One `StageSpec`** (`schemas/plan.py`; `schemas/history.py` and
  `agent.py` re-export) — the field lands once and is inherited everywhere,
  and it serializes with the plan, so the stage record already states the
  applied scale (the record-field invariant satisfied by the schema itself).
- **Statistics exclusion is untouched**: restraint rows stay out of
  Rwp/DW/Bérar-Lelann (WP-0406/0407); a scale changes the rows' magnitude,
  not their block membership (`model/rows.py` — the one edit, if any, is
  where the weight enters row assembly).
- Additive defaulted schema field; no version bump (events precedent).

## Non-goals

- Automatic scheduling (reduce-on-convergence heuristics) — the caller or a
  plan decides; this WP is the mechanism.
- Per-restraint schedules (the per-restraint `weight` already exists; the
  stage scalar composes with it).
- Preset changes.

## Tasks

- [ ] The `Stage` field (name it against eq 7, cite it), threaded to the
      restraint row assembly at stage compile; identity default pinned
      bit-identical against a pre-change fit.
- [ ] A two-stage schedule test: stiff first stage holds geometry through a
      deliberately bad start, relaxed second stage converges; the
      §8 failure-mode note ("if the geometric assumptions are invalid, the
      refinement will not progress") quoted in the docstring.
- [ ] Manual sentence (`using/concepts.md`) + `AGENT_PROTOCOL.md` row.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_restraints.py -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- McCusker et al. (1999), §8 eq (7). Local copy at
  `~/zotero-linker/derived/YWSBLSIS/`.
- WP-0406 (restraint penalty rows), WP-0407 (the statistics exclusion).

## Handover log

- **2026-08-15** — created from the McCusker audit (WP-1068); gap 6.
