# WP-1902 — the solve cost as a quadratic form, and the doublet question first

Milestone: v1.9 · Status: 🔄 2026-10-01 — the spike and `solve/cost.py` landed (PR #580); the "poor" bar is open
Depends on: —
Priority: P2 2026-09-30 — the design gate for the direct-space route; every engine chunk reads this cost

## Goal

`solve/cost.py` evaluates the profile χ² of a structure from its intensity
vector alone, as a quadratic form built once from a compiled Le Bail / Pawley
model, agreeing with Rietveld-mode `evaluate`. The first task settles whether
lab doublet data can use it.

## Context

Scoped in issue #562 (chunk S0, plus the prototype comment's amendment (a)) and
WP-1515, reviewed adversarially on 2026-09-30. With Ω (per-reflection profiles),
the cell and the background held, and W = diag(1/σ²):
χ²(I) = c − 2rᵀI + IᵀMI, with M = ΩᵀWΩ, r = ΩᵀW(y − b), c = (y − b)ᵀW(y − b).

**What the review measured** (Cu LaB₆, exact overlaps, scratch probes):

- The identity holds to 4e-16 about S0's **own** unconstrained least-squares
  answer. About rietx's fitted Pawley intensities it is 1e-7 (restraint rows,
  ≥ 0 bounds, `ftol`), and about Le Bail intensities 2.4e-2. So **the floor
  comes from S0's own solve**, never from `lebail_update` or the Pawley buffers,
  and I_P may go negative.
- **The proposed identity test is tautological**: χ² − χ²_min against the same
  quadratic form passes for any Ω, a wrong one included. The failing test is
  Ω·I(structure) against Rietveld-mode `evaluate`.
- **Lab doublets are the open question.** Le Bail and Pawley share one I across
  emission lines and apply no per-line Lp (`model/forward.py`, `lp_lines = None`),
  so Lp(Kα2)/Lp(Kα1) − 1, which runs −0.6 % to +1.4 % over 20–130°, is missing.
  NAC is single-line and hides it. The FAP lab pattern does not.
  **Spike first**: does Ω built per line (from `derivative_bases` or by
  linearity, never from batch internals) match Rietveld `evaluate` on FAP? If
  not, the cost refuses multi-line data by name, which would exclude the common
  case.
- The restraint rows in `pb.restraint` include WP-1459's off-data ridge rows as
  well as the equal-split ones. S0 builds M from Ω directly and excludes both.
- V = M⁻¹ does not exist under exact overlap. Any covariance view goes through
  `statistics.normal_covariance` (equilibrated, rootless directions absent).
- M is banded plus a rank-q update after the background is projected out
  (prototype, amendment (a)). Store it sparse plus low rank when N_refl is large.

Refusals by name: a magnetic phase; a Rietveld-mode model; a poor or
unconverged extraction.

## Non-goals

- Engines, moves, tempering, grading (later WPs).
- The compiled |F|² kernel (S4): defer until its own measurement, since the
  prototype showed incremental moves, not the kernel, set throughput.

## Tasks

- [ ] Spike: per-line Ω against Rietveld `evaluate` on FAP (lab doublet) and NAC; record the residuals and the decision
- [ ] `solve/cost.py`: c, r, M, the floor from S0's own solve, χ² from I
- [ ] Tests: Ω·I equals `evaluate` to 1e-14 at ten random moves on NAC and on FAP; a wrong Ω fails; the three refusals
- [ ] Skill: none until a public entry exists

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_solve_cost.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- David (2004), *J. Appl. Cryst.* 37, 621: equivalence of the Rietveld and correlated-intensity costs (cited for the concept; abstract read only).
- Spillman & Shankland (2021), *CrystEngCommun* 23, 6481 (GALLOP is GPL-3: concepts only).
- Issue #562; WP-1515.

## Handover log

- **2026-10-01** — The solve cost is on `main`. `solve/cost.py` turns a Le Bail or
  Pawley extraction into a quadratic form in the reflection intensities, so a
  structure trial is scored without a pattern evaluation. The doublet spike came
  first and showed multi-line data needs no refusal. *Done:* PR #580
  (`4ab339f7`), merged as `604a5bb7` by `/pr-review` after two review rounds.
  *Measured* by the contributor: Ω·I against `evaluate` at ten random moves,
  2.8e-16 on NAC and 3.6e-16 on FAP. The doublet error the review predicted is
  real (2.6e-3 on FAP) and arises only when Ω is built on a Le Bail or Pawley
  compile, which this cost does not do. *Gotchas* from the review: the nuisance
  pseudo-inverse is equilibrated through `column_rescale`, because an impurity's
  stored scale otherwise set the cutoff for the background columns (χ² ×37 at a
  stored scale of 1e4). `nuisance="scale"` takes the impurity's atoms as
  declared, a Le Bail placeholder included. *Open:* the "poor" bar (review
  item 7) is the maintainer's to set here. Two refusals the contributor proposed
  are follow-ups for their own PR: a phase with `propagation_vector`, and a
  declared harmonic under `"pawley"`, both of which now drop out as absent.
  *Next:* the bar, then the engine chunks that read this cost.

- **2026-09-30** — created, from the 2026-09-30 issue triage (issue #562). No
  open WP owns it. The figures above are the review agent's scratch probes at
  `e3e6486a`, not yet reproduced in a session of this WP.
