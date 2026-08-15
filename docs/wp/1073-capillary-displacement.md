# WP-1073 — Capillary sample displacement: eq (4) for Debye-Scherrer geometry

Milestone: v1.0.x · Status: ✅ 2026-08-15 — eq (4) on both forward paths and
the analytic chain, position templates and actions keyed by geometry, and the
measured finding that 11-BM is where the correction must *not* be refined
Depends on: — (post-freeze is fine: additive defaulted schema fields; a
laboratory capillary user is the beneficiary)

## Goal

`debye_scherrer` gains the two-axis capillary displacement correction
Δ2θ = (x·sin 2θ − y·cos 2θ)/R (McCusker eq 4), refinable, wired through the
analytic Jacobian and both trend-analysis layers. Gap 7 of the McCusker
audit (`../milestones/v1.0.md` § Appendix).

## Context

- **The current design statement must be engaged, not silently overwritten.**
  `schemas/instrument.py` (the `Geometry` docstring, ~line 300) says only
  `zero_shift` moves `debye_scherrer` peaks, and that the package "does not
  model it rather than inventing one". That was written before the paper was
  read: eq (4) *is* the published correction for a capillary off the centre
  of the 2θ circle, so the not-inventing argument no longer applies to this
  geometry. It still applies to `flat_plate_transmission`, whose docstring
  keeps its statement.
- **Where it is defensible to omit and where it is not** (the audit's
  reading): at a synchrotron with a crystal analyser the paper says
  displacement error is eliminated — so 11-BM NAC is the *null* test
  (recovered x, y ≈ 0) — and a laboratory Debye-Scherrer or Guinier camera
  is where the omission bites.
- **The seams**: `displacement_shift_deg` / `transparency_shift_deg`
  (`model/corrections.py:92,109`) are the pattern to follow; call sites in
  `model/forward.py` (~303 and ~1138) apply per-geometry shifts; the
  analytic peak-chain Jacobian and the traced twin (`backend/traced.py`)
  both consume the shift, so the derivative lands once in the shared chain.
  No new backend op — sin/cos exist; mind the hot-path constant rule
  (`xp.asarray` lifts inside the traced call).
- **The geometry needs a radius.** eq (4) divides by the goniometer radius;
  `Geometry.goniometer_radius_mm` exists (`schemas/instrument.py:355`,
  `float | None`) — check it is honoured for `debye_scherrer`, and refuse
  x/y varying while it is `None`, naming what is missing.
- **Conventions by physics, not letters** (the invariant): x and y are the
  capillary's displacements from the centre of the 2θ circle; state which
  axis is which by its signature (the sin 2θ term is the displacement along
  the beam, the cos 2θ term perpendicular — verify against the geometry
  before writing it down, and cite eq 4 in the docstring).
- **Trend templates**: `report/layer1.py` (~350) carries `cos_theta`
  (flat-plate displacement) and the transparency shape; eq (4) adds sin 2θ
  and cos 2θ shapes for this geometry, and `layer2.py`'s template→action map
  gains the rows — which closes §12.3's question ("is the 2θ correction
  right for the geometry?") for capillary instruments. The collinear-
  template rule stands: nested single fits, reported non-separable when they
  are.
- **Degeneracy posture**: both parameters default 0 and `vary=False`; freed
  by lab capillary workflows, never by default (the aniso-CIF lesson:
  reading a file must not change what a plan frees). zero + x + y is three
  positional corrections — the identifiability layer and `analyse_trends`
  exist for exactly this; the AGENT_PROTOCOL row says when freeing them is
  sensible.
- Validation: synthetic injection (shift a synthetic capillary pattern by
  known x, y; recover both to tolerance), plus the 11-BM null above.
- Additive defaulted schema fields — old projects load; no version bump
  (events precedent).

## Non-goals

- Guinier geometry as its own `Geometry` member (eq 4 covers the
  displacement; a Guinier preset is its own decision).
- Touching `flat_plate_transmission`'s no-displacement statement.
- Refining the radius (it is knowable from the instrument — the µR/µt
  precedent: recorded, not smoothed over).

## Tasks

- [x] `capillary_displacement_shift_deg` in `model/corrections.py` (cited,
      conventions by physics), the two `Parameter` fields + radius on the
      geometry, the refusal for a missing radius.
- [x] Forward call sites + analytic Jacobian + traced twin; cross-backend
      row if a new derivative path needs one (`test_cross_backend.METHODS`
      grows whenever a derivative path does).
- [x] The two trend templates and the layer-2 action rows; the Geometry
      docstring rewritten to name eq (4) and keep the transmission
      statement.
- [x] Synthetic recovery test + the 11-BM null; `AGENT_PROTOCOL.md` row;
      manual sentence. PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_capillary_displacement.py tests/test_cross_backend.py -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- McCusker et al. (1999), §5 eq (4), §12.3. Local copy at
  `~/zotero-linker/derived/YWSBLSIS/`.

## Handover log

- **2026-08-15** — **shipped.** Five commits, `wp1073-capillary-displacement`
  off `a189de0`. No `### Inherited` existed on arrival (WP-1072 posted only
  into 1067's and 1074's mailboxes), so nothing was pruned.

  **Done.** `capillary_displacement_shift_deg` (`model/corrections.py`), the
  two `Parameter` fields on `Geometry` plus `CAPILLARY_OFFSETS` as the one
  authority for the pair of names, `Instrument.debye_scherrer(goniometer_
  radius_mm=…)`, both forward shift sites, `scalar_chain_supported`, the
  `capillary_offsets` cross-backend config, geometry-keyed position templates
  and actions with two new `ActionKind` members, `THRESHOLDS_VERSION` 0.9 →
  1.0, the `capillary_displacement` compare variant, the GUI wizard field,
  `tests/test_capillary_displacement.py` (14 rows), AGENT_PROTOCOL §8.18 +
  a degeneracy-table row, Part 1's paragraph and Part 2's eq (4) block.

  **The paper's letters do not travel, so the signs are derived, not
  transcribed.** Eq (4) is printed `(x·sin2θ − y·cos2θ)/R` with no figure,
  and GSAS-II pairs its `DisplaceX` with the *cos 2θ* term — the opposite
  letter. First order in |d|/R, the apparent angle at the goniometer centre
  moves by (d·t̂)/R with t̂ = (−sin2θ, cos2θ), giving
  `Δ2θ = (−a·sin2θ + b·cos2θ)/R` with a along the beam (downstream positive)
  and b perpendicular (positive toward increasing 2θ). That equals eq (4)
  under x = −a, y = −b, which is algebra about the two expressions and not a
  claim about the paper's axes: **checked, the paper has no figure to
  supply** — six figures, all profile plots (11 embedded images, exactly the
  six once the multi-panel ones are counted), and "the respective
  displacements of the capillary from the centre of the 2θ circle" is the
  entire definition. Eq (3) has the same gap and survives it because one
  component plus the Bragg-Brentano convention is unambiguous. The test
  checks the expression against an exact ray-circle intersection, and asserts
  the gap is second order *and non-zero*.

  **Two premises in the Context above did not survive measurement.**

  1. *"11-BM NAC is the null test (recovered x, y ≈ 0)."* It is not a null
     test, it is a degeneracy test. Over NAC's certified 2-24° the trio
     {1, sin2θ, cos2θ} has a unit-column Gram eigenvalue of **1.6e-5**, so
     the fit slides along the null direction to a bound: a = +1.000 mm (its
     max) ± 2.78, b = +0.72 ± 1.01, ρ(zero, across) = **−1.0000**, two
     eigenvalue-0 soft modes, `BOUND_HIT` + `HIGH_CORRELATION`. Rwp
     **improves** 0.14025 → 0.13843 while a walks out of the acceptance
     band, 10.25121 → 10.23976 Å (**1117 ppm**, 5.6× the ±2e-3 allowed).
     On 11-BM LaB6 660a over 2-60° (min eig 9.3e-4) the same experiment
     returns +0.544 ± 0.054 and +0.527 ± 0.041 mm — *10σ from zero* — with
     a 4.156850 → 4.154113 Å (−658 ppm off the beamline-calibrated value,
     which itself sits 16 ppm from the SRM 660a certificate) and Rwp
     0.08849 → 0.08368. **The paper's "eliminated by CA geometry" is a
     statement about the instrument, not a licence to refine and expect
     zero.** Both datasets are 2θ-short at 0.41 Å, which is the whole
     mechanism.
  2. *"a neglected offset leaves a position signature the report names."*
     It does not, at convergence. On the synthetic (0.30/−0.20 mm, 8-140°)
     the zero shift and the cell imitate most of eq (4): a comes back
     −290 ppm out and the converged report suggests **no** position action
     at all, while the `zero` stage's own rung names
     `refine_capillary_offset_along_beam` at 0.66. WP-1058's rule with a
     concrete case; both halves are asserted.

  **A latent defect fixed on the way.** `_POSITION_ACTIONS` was
  geometry-blind, so a capillary or transmission fit whose peaks followed
  cos θ was told to `refine_sample_displacement` — force-fixed outside
  `bragg_brentano` by `params/vector.py`. Measured on the WP-1012 apply
  fixture (a Debye-Scherrer instrument): both flat-plate actions were
  suggested and the route answered 409 "structurally fixed" for both. Now
  the templates *and* the actions are keyed by geometry.

  **Design decisions worth knowing.** (a) The offsets are **force-fixed when
  the geometry declares no radius**, not merely refused on an explicit
  `vary` — without R the forward branch skips the term, so a free entry
  would be a dead column the solver moves and the model never reads.
  (b) `flat_plate_transmission`'s action row is left byte-for-byte as it
  was: that geometry models no displacement either, so its two aberration
  actions also name held parameters, but the *diagnosis* there is at least
  the right one (a flat specimen off the axis) where for a capillary neither
  the shape nor the parameter was — see 1003's mailbox.
  (c) The two 11-BM rows are **not** marked `slow` although they read real
  data: both fits together cost 2.9 s and they skip cleanly without the
  file, so the fast gate is where the evidence belongs.

  **Numbers**, `[dev]` venv (no jax/torch — every jax/torch row in
  `test_cross_backend.py` self-skipped), darwin/arm64, Python 3.12.12,
  numpy 2.5.2, package 1.0.0.dev0. Fast selection, `main` at `a189de0`:
  **2365 passed, 112 skipped**; this tree at `153ef00`: **2383 passed, 117
  skipped** — +18 passed, +5 skipped, +23 collected, and the +23 accounts
  exactly:

  | where | passed | skipped |
  |---|---|---|
  | `test_capillary_displacement.py` (new) | 14 | 0 |
  | `test_fitreport_layers.py` (the geometry meta-test) | 1 | 0 |
  | `test_compare_ui.py` (the variant) | 1 | 0 |
  | `test_cross_backend.py` (`capillary_offsets`, 7 items) | 2 | 5 |

  The cross-backend row's five skips are the four missing-backend ones and
  **"no axial columns in this config"** — this state frees no FCJ parameter,
  so the axial-agreement test declines it. Worth stating because it is
  exactly the trap `tests/CLAUDE.md` names: reading the two runs as +19/+4
  (the naive "my new tests all pass" count) hides a skip, and the arithmetic
  only closes when the skip is named.

  Wall clock 2:34 and 2:41 for the two runs, minutes apart on an otherwise
  idle machine — quote as a range, not a record. vitest **408 passed**
  (was 407: the wizard parity row now covers a sixth `debye_scherrer`
  field), `svelte-check` 372 files / 0 errors, Sphinx `-W` clean, ruff clean.
  The **full** suite, once on the final tree: **2491 passed, 126 skipped**
  in 24:21, green. It had to fire, and the reason is worth keeping: the
  offsets themselves cannot move an acceptance number (no acceptance
  instrument declares a goniometer radius, so both are force-fixed and the
  forward branch is skipped), but the *report vocabulary* changed on every
  `debye_scherrer` state, and 11-BM NAC, 11-BM LaB6 and the agent-eval
  landing states are all capillary. Nothing moved; the acceptance suites
  read cells and Bisos, not template names.

  **Next.** Nothing left in this WP. For **1003**: two `ActionKind` members
  and `THRESHOLDS_VERSION` 1.0 join the frozen surface, and the
  `flat_plate_transmission` asymmetry in (b) is left to ratify — pushed into
  its `### Inherited`.

- **2026-08-15** — created from the McCusker audit (WP-1068); gap 7.
