# WP-1073 — Capillary sample displacement: eq (4) for Debye-Scherrer geometry

Milestone: v1.0.x · Status: ⬜
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

- [ ] `capillary_displacement_shift_deg` in `model/corrections.py` (cited,
      conventions by physics), the two `Parameter` fields + radius on the
      geometry, the refusal for a missing radius.
- [ ] Forward call sites + analytic Jacobian + traced twin; cross-backend
      row if a new derivative path needs one (`test_cross_backend.METHODS`
      grows whenever a derivative path does).
- [ ] The two trend templates and the layer-2 action rows; the Geometry
      docstring rewritten to name eq (4) and keep the transmission
      statement.
- [ ] Synthetic recovery test + the 11-BM null; `AGENT_PROTOCOL.md` row;
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

- **2026-08-15** — created from the McCusker audit (WP-1068); gap 7.
