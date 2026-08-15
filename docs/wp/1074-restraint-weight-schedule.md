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

### Inherited

**From [1072](1072-geometry-table.md), 2026-08-15 — `model/restraints.py` now
has a second consumer, and it is not a restraint.** The geometry table builds
`_Bond` / `_Angle` items with `sigma = 1.0` and `weight = 1.0` and calls
`restraint_partials` on them, precisely so that its `pref = √weight/σ` is 1 and
the returned partials are ∂(distance or angle)/∂p unweighted. Those partials
become every reported esd.

So **where the stage scalar enters decides whether this WP silently corrupts
the geometry esds.** Multiply it into `_Bond.weight` / `_Angle.weight`, or into
`pref` inside `restraint_partials`, and every geometry esd comes back scaled by
√c_w — with no test failing that a reader would connect to the change: the
distances are computed elsewhere, and `stderr / stderr_diagonal` is a ratio, so
the one number the geometry tests compare against a Monte Carlo is the only
thing that would move. The safe seam is the one this file already names — "where
the weight enters row assembly", i.e. the *residual and Jacobian row build*, not
the compiled item and not the shared partials function.

Whichever seam you pick, pin it: `tests/test_geometry_table.py`'s
`test_esd_matches_a_monte_carlo_through_decode` is the assertion that would
have caught it, and a fixture carrying both restraints *and* a non-unit c_w is
the direct check.

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
