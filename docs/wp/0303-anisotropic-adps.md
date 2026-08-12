# WP-0303 — Anisotropic ADPs

Milestone: v0.3 · Status: ✅ 2026-07-23
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
  [`schemas/structure.py`](../../src/anatase/schemas/structure.py). Keep
  `biso` as the default representation — every existing test, plan glob
  (`phases.*.atoms.*.biso`) and acceptance run depends on it. Aniso is opt-in
  per atom, not a global mode switch.
- Forward model: the Debye-Waller factor in
  [`crystallography/structure_factor.py`](../../src/anatase/crystallography/structure_factor.py)
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
[`optimize/statistics.py`](../../src/anatase/optimize/statistics.py) — a
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

- [x] Optional aniso ADP block in the atom schema (isotropic stays default);
      JSON round-trip test incl. the `extra="forbid"` / ±inf conventions
- [x] Anisotropic Debye-Waller in the structure factor over the frozen op
      subsets, with the R·U·Rᵀ / Rᵀh conventions documented in the docstring
- [x] Isotropic-limit equivalence test: U_ij = Uiso·δ_ij reproduces the Biso
      path to machine precision — *with a correction, see below*
- [x] Site-symmetry U_ij constraints wired from WP-0301
- [x] Positive-definiteness diagnostic (non-positive eigenvalue → structured
      `Diagnostic`, guard in the staged runner)
- [x] Analytic ∂|F|²/∂U_ij columns + FD agreement test
- [x] CIF export of aniso ADPs with esds (round-trip through gemmi)
- [x] Refinement test on a structure with known aniso ADPs; record the
      background-absorption R² alongside the fit

## Acceptance

Isotropic limit matches the Biso path to 1e-12 relative; a synthetic aniso
perturbation is recovered within esds under site constraints; CIF round-trips;
background absorption stays below the 0.25 guard on the acceptance run.

```sh
.venv/bin/python -m pytest tests/test_aniso_adp.py -q
.venv/bin/python -m pytest
```

**Measured (2026-07-23)**: 243 passed, 22.6 s (whole suite, acceptance
included).  Rutile round trip from isotropic-equivalent starting tensors:
U11 = 0.00960(63) vs 0.0092 truth, U33 = 0.00640(93) vs 0.0068, GoF 1.03,
anisotropy resolved at 3.4σ.  Worst background-absorption R² over the ADP
DOFs **0.007** (guard 0.25); no ADP left the positive-definite cone.

## References

- Trueblood et al. (1996) Acta Cryst. A52, 770 — ADP nomenclature.
- Grosse-Kunstleve & Adams (2002) J. Appl. Cryst. 35, 477 — ADP symmetry
  constraints (cctbx, BSD-style; cross-check reference).

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
- **2026-07-23** — **complete**, seven commits, all checklist items landed;
  243 tests pass including the three real-data acceptance runs, which are
  numerically untouched (the isotropic branch of the structure factor is
  byte-for-byte the old expression).

  **Two corrections to this WP's own text**, both worth keeping in mind:

  1. *The isotropic limit is not U_ij = Uiso·δ_ij.* It is
     U^ij = Uiso·G*_ij/(a*_i a*_j) — the two coincide only when the
     reciprocal axes are orthogonal (cubic/tetragonal/orthorhombic). For a
     hexagonal cell the equivalent tensor has U12 = Uiso/2. Written as
     `adp.isotropic_u6`; the equivalence test runs on an orthorhombic *and* a
     hexagonal cell for exactly this reason.
  2. *The isotropic-limit test is not "the cheapest guard against a transpose
     error"* — in a group whose operators are all diagonal it cannot catch
     one at all, because Uiso·G* is invariant under both R·(·)·Rᵀ and
     Rᵀ·(·)·R. The genuine guard is
     `test_orbit_sum_matches_explicit_P1_expansion`: expand a P6₃/m orbit
     into P1, give each image its own R·U*·Rᵀ, and compare. Both tests were
     mutation-checked against a deliberately transposed einsum. (The
     hexagonal isotropic case does catch it, but only because the metric is
     non-orthogonal *and* the rotations are non-symmetric — do not rely on
     that in a monoclinic setting.)

  **Design decisions worth knowing:**
  - ADP DOFs are **absolute** (U = Σₖ θₖ·Bₖ), unlike WP-0302's coordinate
    DOFs which are displacements from an anchor. The pattern basis spans the
    whole allowed subspace, so this enforces the site symmetry exactly rather
    than preserving whatever asymmetry the input carried. θ₀ comes from a
    least-squares projection; a tensor outside the subspace is a hard error
    naming the nearest allowed one, not a silent symmetrisation.
  - Working in U* (= U^ij a*_i a*_j) rather than U^ij inside the structure
    factor makes "R·U·Rᵀ on the image" and "Rᵀh on the parent" the *same*
    computation. In U^ij they agree only because the a* diagonal happens to
    commute with the group's rotations — true in every real setting, but a
    contingency this code does not need to depend on.
  - `structure_from_cif(..., aniso=True)` is **opt-in**, on the same logic as
    the schema field: reading a file must not silently change which
    parameters a plan frees. Note COD 1000236 (the NAC acceptance structure)
    *does* carry aniso ADPs, so a default-on import would have flipped that
    acceptance run to anisotropic without anyone asking.
  - The positive-definiteness test runs on the stored U^ij matrix, not
    U_cart. They are related by a congruence, so Sylvester's law gives the
    same eigenvalue *signs* and no cell is needed in the guard — but the
    magnitudes are only physical in U_cart (`adp.principal_values`).
  - Symmetry-locked components (U13/U23 on rutile's 4f) never enter θ and so
    are absent from `result.parameters`, exactly like locked coordinates.
    Consumers must not assume all six are reported.

  **Not done / next:**
  - `AnisoU.isotropic(uiso, cell)` exists as a constructor but nothing calls
    it automatically — there is no "promote this site from biso to aniso"
    verb yet. Worth adding when a strategy wants to escalate a site
    mid-refinement (natural fit for WP-0308's Layer-2 suggested actions).
  - The FitReport does not yet mention ADP anisotropy or the
    `ADP_NOT_POSITIVE_DEFINITE` diagnostic in Layer 2; it surfaces through
    `RefinementResult.diagnostics` only.
  - `background_absorption` screens ADP DOFs but the FitReport's own
    thresholds text still says "Biso"; cosmetic, not wrong.

- **2026-07-23 (review pass)** — post-completion once-over found one gap:
  the public `Structure.from_cif` did not forward `aniso` (only the internal
  reader had it; the WP tests imported that directly, so nothing pinned the
  front door). Fixed + pinned by `test_public_from_cif_forwards_aniso`.
  Also probed beyond the suite, all clean: mixed iso/aniso sites in one phase
  (Jacobian vs FD ~6e-6), Le Bail frees no adp DOFs, tied-cell esds reach the
  exported CIF (`b` carries `a`'s su), history checkout round-trips aniso
  tensors bit-exact and restores free adp paths.
