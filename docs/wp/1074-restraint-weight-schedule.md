# WP-1074 — The restraint weight schedule: c_w per stage

Milestone: v1.0.x · Status: ✅ 2026-08-16
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
- **`model/restraints.py` has a second consumer, and it is not a restraint**
  (from WP-1072, verified still true on arrival): `model/geometry.py` builds
  `_Bond`/`_Angle` items with `sigma = 1.0`, `weight = 1.0` (lines 331, 339)
  and calls `restraint_partials` (line 382) precisely so that `pref =
  √weight/σ` is 1 and the partials come back as ∂(distance or angle)/∂p
  unweighted. Those partials become every reported geometry esd. So **where
  the stage scalar enters decides whether this WP silently corrupts them**:
  multiplied into `_Bond.weight`/`_Angle.weight`, or into `pref` inside
  `restraint_partials`, every geometry esd comes back scaled by √c_w, and no
  test a reader would connect to the change fails — the distances are computed
  elsewhere and `stderr / stderr_diagonal` is a ratio, so the Monte Carlo
  comparison is the only number that moves. The seam is the *residual and
  Jacobian row build* (`model/rows.py`, `optimize/least_squares.py`), not the
  compiled item and not the shared partials function.

## Non-goals

- Automatic scheduling (reduce-on-convergence heuristics) — the caller or a
  plan decides; this WP is the mechanism.
- Per-restraint schedules (the per-restraint `weight` already exists; the
  stage scalar composes with it).
- Preset changes.

## Tasks

- [x] The `Stage` field (name it against eq 7, cite it), threaded to the
      restraint row assembly at stage compile; identity default pinned
      bit-identical against a pre-change fit.
- [x] A two-stage schedule test: stiff first stage holds geometry through a
      deliberately bad start, relaxed second stage converges; the
      §8 failure-mode note ("if the geometric assumptions are invalid, the
      refinement will not progress") quoted in the docstring.
- [x] Pin the geometry seam: a fixture carrying both restraints *and* a
      non-unit c_w leaves every geometry esd unmoved. The Monte Carlo the
      mailbox named does **not** catch this (measured, both bugs injected):
      its fixture declares no restraints and runs at c_w = 1, so a leak
      conditioned on the model is invisible to it.
- [x] Manual sentence (`using/concepts.md`) + `AGENT_PROTOCOL.md` row (§8.19).
- [x] Tests + obs/calc/diff PNGs to `tests/output/` (both schedule plans,
      inspected: the failed fit's difference curve is unremarkable).

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

- **2026-08-16** — **closed.** All five tasks landed; the mailbox is consumed.

  **Done.** `Stage.restraint_weight_scale` (eq 7's c_w, default 1.0), mirrored
  by `StageSpec` and `NodeAction`, threaded through `compile_model` onto
  `CompiledModel` at stage compile, and applied by multiplying √c_w into the
  **assembled** rows in exactly two places — `CompiledModel.restraint_residual`
  (which every backend reaches through `rows.assemble`) and the analytic block
  in `least_squares`. `RestraintReport.weight_scale` records the value a report
  was measured under. Manual: `using/concepts.md` § "Relaxing the restraints as
  the model improves"; `AGENT_PROTOCOL.md` § 8.19 (§8's count is now nineteen).
  Root CLAUDE.md gained the seam rule (cap 683 → 700, justification in
  `test_docs_consistency.py`); `gui/CLAUDE.md` gained the derived-stage-keys
  clause.

  **Measured — the identity default.** A restrained five-stage rutile fit is
  bit-identical to `main` at `1fbbbdd`: Rwp, GoF, χ², the restrained coordinate,
  its esd, the cell and the restraint deviation all agree to the last bit of the
  hex float (probe run against a `main` worktree on `PYTHONPATH`, same venv).

  **Measured — what a schedule buys.** P -1, six coordinate DOFs on two weak
  oxygens, 35 reflections over 12–34°, 1100 points; start at Zr–O1 = 3.729 Å for
  a true 1.865 Å bond. Flat c_w = 1 throughout: **converges** at 4.834 Å, 148σ
  in tension, 0.425 rms from truth, Rwp 0.03926, GoF 1.231. c_w = 300 then 1:
  stiff stage 1.866 Å (0.03σ), relaxed stage 1.872 Å (0.33σ), 0.00107 rms,
  Rwp 0.03266, GoF 1.024. Same plan shape, same data, same start.

  **Two synthetic attempts failed first, and the reason is the finding.** P1
  cannot demonstrate this at all: the inverted structure is an exact powder
  degeneracy (|F(h)|² is unchanged by x → −x) that preserves every interatomic
  distance, so restraints cannot separate the two at *any* c_w — measured, the
  permanently-stiff plan reached the wrong basin with its restraints satisfied
  to 0.15σ. Rutile also cannot: one coordinate DOF, and every start from ±0.02
  to ±0.12 converges to the same x. A centrosymmetric group with weak scatterers
  and few reflections is what fails the way §8 describes. Also measured: whether
  a bad start escapes the basin is *direction*-dependent, not magnitude — of
  five displacement directions at 0.14, one escapes, so the test pins specific
  coordinates rather than claiming a magnitude threshold.

  **Gotcha for anything touching `model/restraints.py`.** The 1072 mailbox named
  `test_esd_matches_a_monte_carlo_through_decode` as the assertion that would
  catch a c_w reaching the geometry esds. It does not, and both halves were
  injected to check: that fixture declares no restraints and runs at c_w = 1, so
  a leak *conditioned on the model* passes it (simulated: esds ×10 at c_w = 100,
  file green), while an unconditional factor in `pref` fails it and passes the
  new pin. Both tests now say so in their docstrings.

  **Gotcha the fast suite caught, and the more serious of the two.**
  `test_textdoc.py` pins `gui/src/lib/rxt.ts`'s `STAGE_WORDS` against
  `StageSpec.model_fields`. What it was pointing at was not a highlighter: the
  `.rxt` renderer and parser each carried the same hard-coded key tuple, so a
  new `StageSpec` field renders nowhere, parses nowhere, and is **dropped on
  every save** — `strain_seed`'s own loss one rank up. `gui.textdoc.STAGE_KEYS`
  is derived now, the round trip is pinned against the model, and the dist was
  rebuilt (vitest 408 passed, svelte-check 372 files 0 errors). No
  `FORMAT_VERSION` bump: the events precedent, no line's meaning changed.

  **Not done, deliberately.** No preset adopts a schedule (a Non-goal; it needs
  a measurement on real restrained data, not a synthetic). No `viz/compare` row:
  that registry's standards are the acceptance protocols, none of which declares
  a restraint, so a variant there would be an exact no-op rather than a
  comparison. `refine.replay` does **not** apply a node's c_w, checked rather
  than assumed: it passes `stderr_internal=None`, so it produces no esds, no
  geometry esds and no scale covariance, and the restraint rows are excluded
  from every data-row statistic — c_w cannot move any number it returns.

  **Counts** — `[dev]` only (no jax, no torch, so `test_cross_backend.py` and
  the two backend files self-skip), darwin/arm64, Python 3.12.12, this tree.
  Fast selection **2395 passed, 117 skipped** against 1073's final-tree
  **2383 / 117**: +12 passed, +0 skipped, +12 collected, and the +12 is exactly
  what landed — 8 in `test_restraints.py` for the field, 2 for the schedule
  pair, 1 in `test_geometry_table.py`, 1 in `test_textdoc.py`. Wall clock
  **2:38 idle and 7:45 while the full suite ran beside it** — the range is the
  point, not either figure.

  **On arrival**, pruned `### Inherited`: 1072's warning was still true
  (checked `geometry.py:331,339,382` before folding), so it became the Context
  bullet on the seam and the check it asked for became a task; nothing was
  stale.
- **2026-08-15** — created from the McCusker audit (WP-1068); gap 6.
