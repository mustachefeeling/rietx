# WP-0303 — Anisotropic ADPs

Milestone: v0.3 · Status: ⬜ not started
Depends on: WP-0301

## Goal

Refine anisotropic displacement parameters U_ij under site-symmetry
constraints, with a positive-definiteness guard and the isotropic path left
untouched as the default.

## Context

Today the package is isotropic-only: `Biso` in Å² (= 8π²·Uiso) on every atom,
and CIF import already does a **U_eq fallback from anisotropic ADPs** (v0.1,
`crystallography/cif.py`) — so anisotropic data comes in and is currently
collapsed. This WP stops collapsing it.

Where the work lands:

- Schema: an optional aniso block on the atom in
  [`schemas/structure.py`](../../src/pxrdref/schemas/structure.py). Keep
  `biso` as the default representation — every existing test, plan glob
  (`phases.*.atoms.*.biso`) and acceptance run depends on it. Aniso is opt-in
  per atom, not a global mode switch.
- Forward model: the Debye-Waller factor in
  [`crystallography/structure_factor.py`](../../src/pxrdref/crystallography/structure_factor.py)
  becomes T = exp(−2π²·Σ_ij U_ij h_i h_j a*_i a*_j) evaluated per symmetry op.
  Under op R, U transforms as R·U·Rᵀ in direct-space terms — and the
  reciprocal-space index action is **Rᵀ** (see the symmetry.py comment). Get
  both right and cross-check against the isotropic limit: setting
  U_ij = Uiso·δ_ij must reproduce the existing Biso path bit-for-bit. That
  equivalence test is the cheapest guard against a transpose error.
- Constraints: the allowed U_ij pattern per site comes from WP-0301's ADP
  constraint rows (same code path as coordinates — do not derive it twice).
- CIF export must round-trip aniso ADPs, not just import them.

Guard: an unconstrained U tensor can go non-positive-definite and produce a
physically meaningless (and numerically divergent at high Q) structure factor.
Surface a structured diagnostic when any refined U has a non-positive
eigenvalue, in the style of the existing guards in
[`optimize/statistics.py`](../../src/pxrdref/optimize/statistics.py) — a
diagnostic the strategy engine and the FitReport can see, not a bare warning.

Background coupling matters here: the background-absorption block projection
(`optimize.statistics.background_absorption`, threshold 0.25) exists precisely
because a flexible background biases ADPs. Aniso ADPs have more freedom to be
biased, so the acceptance run must report the absorption number, not assume it.

## Non-goals

- Anisotropic *strain broadening* (Stephens) — that is peak width, not ADPs,
  and belongs to WP-0503.
- TLS / rigid-body ADPs (v2 fence).

## Tasks

- [ ] Optional aniso ADP block in the atom schema (isotropic stays default);
      JSON round-trip test incl. the `extra="forbid"` / ±inf conventions
- [ ] Anisotropic Debye-Waller in the structure factor over the frozen op
      subsets, with the R·U·Rᵀ / Rᵀh conventions documented in the docstring
- [ ] Isotropic-limit equivalence test: U_ij = Uiso·δ_ij reproduces the Biso
      path to machine precision
- [ ] Site-symmetry U_ij constraints wired from WP-0301
- [ ] Positive-definiteness diagnostic (non-positive eigenvalue → structured
      `Diagnostic`, guard in the staged runner)
- [ ] Analytic or chained ∂|F|²/∂U_ij columns + FD agreement test
- [ ] CIF export of aniso ADPs with esds (round-trip through gemmi)
- [ ] Refinement test on a structure with known aniso ADPs; record the
      background-absorption R² alongside the fit

## Acceptance

Isotropic limit is bit-equivalent to the Biso path; a synthetic aniso
perturbation is recovered within esds under site constraints; CIF round-trips;
background absorption stays below the 0.25 guard on the acceptance run.

```sh
.venv/bin/python -m pytest tests/test_aniso_adp.py -q
.venv/bin/python -m pytest
```

## References

- Trueblood et al. (1996) Acta Cryst. A52, 770 — ADP nomenclature.
- Grosse-Kunstleve & Adams (2002) J. Appl. Cryst. 35, 477 — ADP symmetry
  constraints (cctbx, BSD-style; cross-check reference).

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
