# WP-1960 — spherical-harmonics texture: preferred orientation with no single axis

Milestone: unscheduled · Status: ⬜
Track: Candidates — named on a use case, not yet on a measurement
Depends on: — (#131 is the design record this WP carries forward)
Priority: P3 2026-10-14 — a workaround covers the single-fibre case (March-Dollase); two named users want the general one (#131's author, whose SRM 1976a plate was rejected as an acceptance case for want of it, and the outside lab of WP-1325's 2026-10-13 entry); no WP waits on it

## Goal

`Phase.texture` declares a symmetrised spherical-harmonic correction to the
pole density (Von Dreele 1997) to a declared even order. Its coefficients
refine through exact linear columns. The default driver keeps the pole
density non-negative at every reflection. The coefficients compare term by
term with GSAS-II's under a conversion this WP measures and states.

## Context

### Why it left the fence

Three uses, each on the record:

- **#131** (2026-08-25, moved from PR #119) is the design proposal. A NIST
  SRM 1976a sintered-alumina plate, refined in TOPAS with
  `PO_Spherical_Harmonics` at order 4 and a large leading term, was
  rejected as an X-ray acceptance case because a comparison against it
  would measure the missing feature. The pattern and its `.inp` sit on
  the contributor's archive, not in this repo. The refined values are on
  the issue and stay out of this file (root CLAUDE.md § Licensing, data).
- **WP-1325's 2026-10-13 entry**: an outside lab that relies on TOPAS names
  spherical-harmonics texture as its other gap.
- **Two readers drop it today.** `read_topas_inp` reports
  `PO_Spherical_Harmonics` as not imported, with the message "the texture
  is dropped and the intensities it explained are not"
  (`io/projects/coverage.py:259`). The GSAS-II reader's `_hap`
  (`io/projects/gsas2.py:1066-1073`) records an `SH` entry's *stale
  March-Dollase* slots and drops its order and coefficients. GSAS-II's
  `Pref.Ori.` list is `[kind, MD ratio, MD flag, MD axis, SH order,
  {coefficients}, penalty hkls, penalty tolerance]` (5.8.4,
  `GSASIIstrIO.py:3059-3071`). Nothing reads that record yet, so the
  defect is latent.

The ROADMAP and DESIGN.md (*Texture fence revised*) entries of 2026-10-14
record the move.

### What exists

- **March-Dollase** (`model/preferred_orientation.py`, Dollase 1986): one
  axis, one `r`. Its multiplier P is folded into the reflection intensity
  `base` at `model/forward.py:1685-1696`, memoised on (cell, r), and only in
  Rietveld mode (compile at `forward.py:3780`). Its analytic column is
  `po_intensity_grad` (`forward.py:2310`), routed by `_PO_PATH`
  (`optimize/least_squares.py:92`) and listed in `_INTENSITY_ONLY` (`:152`).
  The schema is `PreferredOrientation` (`schemas/structure.py:219`) on
  `Phase.preferred_orientation` (`:977`). The `mccusker_structural` plan frees
  it in its own stage after the displacements (`strategy/staged.py:390`).
- **`report/texture.py`**: the Layer-1 March-Dollase axis screen. It extracts
  a per-reflection correction f_k from the residual and scores each axis by
  R². P below is linear in its coefficients, so the same extraction answers
  "what would order L explain" with one weighted linear solve per order.
  That use is a follow-up (Non-goals).
- **Positivity precedent**: `strain_cone_inequalities`
  (`optimize/least_squares.py:1713`) builds `lm.LinearInequality` rows
  T·θ + c ≥ 0 for the Stephens cone. It skips a block when nothing in it is
  free or the start is infeasible. The guard `STEPHENS_STRAIN_NOT_POSITIVE`
  covers TRF and joint fits, which hold no inequality.
- **Basis precedent**: `crystallography/stephens.py` and `wyckoff.adp_basis`
  derive their allowed terms from the operators with the exact-rational
  `wyckoff._nullspace_int`. That kernel does not carry over (D6).
- **Joint fits**: `params/multi.SharingMap` shares every non-scale phase
  parameter by default, March-Dollase included (`multi.py:151-173`);
  `per_histogram=["phases.*.preferred_orientation.*"]` gives each mount its own.
- **Le Bail and Pawley**: `refine.mode_fixed_path` (`refine.py:301`) is the
  force-fix list. It does not hold March-Dollase or extinction (measured
  below).

### The model

For one histogram and cylindrical sample symmetry, Von Dreele (1997) after
Bunge (1982) gives a per-reflection multiplier:

    P_h = 1 + Σ_{l = 2, 4, …, L} (4π / (2l+1)) · Σ_n C_l^n · k_l(ψ) · K_l^n(h)

- K_l^n are the real symmetrised harmonics of the reflection's direction in
  a crystal frame, orthonormal on the sphere. Only the (l, n) the Laue class
  allows appear.
- k_l(ψ) = √((2l+1)/4π) · P_l(cos ψ) is the sample harmonic. ψ is the angle
  between the scattering vector and the sample's symmetry axis.
- l = 0 is the constant the phase scale already carries. Declaring it would be
  an exact degeneracy (TOPAS fixes its `sh_c00` at 1 for this reason). Odd l
  vanishes under Friedel symmetry. A basis that emits either is wrong.
- P is affine in C, so the identity is C = 0 and a column is the basis value
  times the intensity with P divided out.
- The texture index is J = 1 + Σ (C_l^n)² / (2l+1) (GSAS-II's
  `G2lat.textureIndex`, 5.8.4 `GSASIIlattice.py:3467`).

Check the equation, the normalisation and J against Von Dreele (1997) before
Task 2. The paper is not in the local corpus; this form is read off
GSAS-II's `SHPOcal` (`GSASIIstrMath.py:3010`).

### Measured while scoping (2026-10-14, e66fb223)

1. **GSAS-II 5.8.4's sample angle ψ at its default goniometer angles**
   (`G2lat.SamAng`, called as `SHPOcal` calls it): `Bragg` gives ψ = 90° at
   every 2θ from 10° to 120°. `Debye` gives ψ = θ (5°, 15°, 30°, 45°, 60°).
   So in GSAS-II a Bragg-Brentano plate's cylinder axis lies in the plate,
   and its capillary model has a θ-dependent sample term. D2 turns on this.
2. **Allowed terms per Laue class**, from the group characters
   n_l = (1/|G⁺|) Σ χ_l(ω_R) over the proper rotations (even l is
   inversion-even, so the proper part decides), against GSAS-II's
   `GenSHCoeffT`/`OdfChk` counts:

   | Laue | l = 2, 4, 6, 8 | order 4 | order 6 | order 8 |
   |---|---|---|---|---|
   | -1 | 5, 9, 13, 17 | 14 | 27 | 44 |
   | 2/m | 3, 5, 7, 9 | 8 | 15 | 24 |
   | mmm | 2, 3, 4, 5 | 5 | 9 | 14 |
   | 4/m | 1, 3, 3, 5 | 4 | 7 | 12 |
   | 4/mmm | 1, 2, 2, 3 | 3 | 5 | 8 |
   | -3 | 1, 3, 5, 5 | 4 | 9 | 14 |
   | -3m1, -31m | 1, 2, 3, 3 | 3 | 6 | 9 |
   | 6/m | 1, 1, 3, 3 | 2 | 5 | 8 |
   | 6/mmm | 1, 1, 2, 2 | 2 | 4 | 6 |
   | m-3 | 0, 1, **2**, 1 | 1 | 3 | 4 |
   | m-3m | 0, 1, 1, 1 | 1 | 2 | 3 |

   Every row agrees with GSAS-II except **m-3, where GSAS-II carries one term
   at l = 6 (and at l = 10) against the group's two**. `OdfChk` and `GetKcl`
   treat `m3` exactly as `m3m`, so GSAS-II fits an m-3 phase with m-3m's
   functions. A cubic phase has no term at order 2. Counts are a sanity aid
   only: the Rᵀ trap (root CLAUDE.md) passes every count, so the tests
   assert which functions span the space.
3. **Two Rietveld-only multipliers are dead columns under Le Bail.** SRM 660c
   (`examples/srm660c_lab.build_model`), a stage freeing the cell with
   `preferred_orientation.r` (start 0.9) or `extinction` (start 0): under
   `mode="lebail"` r ends 1.7e-13 from its start and extinction at 3.2e-14,
   both with esd `None`, `refinable=True`, empty `held_because`, listed in
   `StageResult.freed`, and no diagnostic. Under Rietveld both move with an
   esd. `mode_fixed_path` holds neither. The texture block joins that list in
   Task 4. The two existing siblings are a separate defect, proposed for
   § What fires, and what stays silent rather than folded here, because they
   land alone and sooner.
4. **A GSAS-II golden needs care.** `GetKsl`/`GetKcl` called directly from
   GSAS-II's own environment returned 0.0 for every input, with the binaries
   reported found. Generate the golden through `SHPOcal` or the scriptable
   API, and check first that P ≠ 1 for a non-zero coefficient.

### Decisions, each with the practice behind it

Task 1 settles D1 and D2 against the papers and writes the outcome here.
The rest stand unless Task 1's reading overturns one.

- **D1 — the convention is Von Dreele's, as GSAS-II implements it.** GSAS-II
  is open and runs in `~/Code/rietx-bench` (5.8.4, its pixi environment), so
  agreement with it is a measurement. Its C are the orientation
  distribution's own coefficients, independent of the geometry, so a joint
  fit sharing them across two histograms of one mount is consistent, and J is
  defined on them. TOPAS's `spherical_harmonics_hkl` is a function of hkl
  alone, with the sample term folded in and a normalisation not read here. A
  shared TOPAS-style coefficient would mean two things across two geometries,
  so TOPAS is a conversion at its reader, measured against its own output.
- **D2 — ψ comes from `Geometry.kind`, and the sample symmetry is cylindrical
  only.** No `sample_symmetry` field. GSAS-II's histogram-level SH
  correction is "cylindrical symmetry only" too (`SHPOcal`'s docstring). In
  every geometry rietx models, ψ is one value for every reflection:
  `bragg_brentano` puts the scattering vector along the plate normal
  (ψ = 0°); `flat_plate_transmission` is ITC case (3a), whose normal bisects
  the beams, so the scattering vector lies in the plate (ψ = 90°);
  `debye_scherrer` puts it perpendicular to the spinning capillary axis
  (ψ = 90°). k_l(ψ) is then a per-l constant, and the open question is which
  frame the coefficients are quoted in. Recommended: the physical ψ above,
  because J and the sign of C_2^0 then describe the specimen. The cost is
  that a Bragg-Brentano coefficient differs from GSAS-II's. For one P,
  GSAS-II's C is rietx's times P_l(1)/P_l(0) = −2, 8/3, −16/5, 128/35 for
  l = 2, 4, 6, 8 (measurement 1),
  and that GSAS-II's default capillary model, with ψ = θ, has no constant
  conversion. The alternative is GSAS-II's ψ, which makes Bragg-Brentano
  coefficients identical and J a number about a fibre axis the plate does
  not have. Decide after reading Von Dreele (1997) on the frame.
- **D3 — the order is declared.** GSAS-II takes it from a menu in the
  histogram panel. TOPAS takes it as `PO_Spherical_Harmonics(sh, order)`.
  Even, at least 2. An order with no allowed term for the Laue class is
  refused, naming the lowest order that has one (a cubic phase at order 2).
- **D4 — positivity is a linear inequality under the default driver and a
  guard elsewhere.** GSAS-II's practice is a soft penalty
  (`SH-Pref.Ori.`, weight 1/toler², default toler 0.1) at hkls the user
  lists (`GSASIIstrMath.py:847-872`). Here P ≥ 0 at every reflection of the
  stage's frozen list is linear in C, so it takes `strain_cone_inequalities`'
  shape, and the identity start C = 0 is strictly inside. It is linear in θ
  only while the cell is held. K_l^n(h) is a function of h's Cartesian
  direction, which moves with the metric in every class but the cubic ones.
  Stephens' rows multiply integer hkl monomials and have no such dependence.
  So the rows are built from K at the stage's starting cell, and a stage
  freeing the cell beside C holds positivity only to first order. Between
  reflections P can still go negative. `TEXTURE_NOT_POSITIVE` samples P over
  the directions of the Laue class's asymmetric unit at the answer and fires
  under any driver. Zero is on the boundary, so the test is one-sided. Its
  message says the coefficients are not quotable as a pole density, never
  that the specimen is textured.
- **D5 — placement and exclusivity.** `Phase.texture`, beside
  `Phase.preferred_orientation`, shared in a joint fit by the same default
  and overridden the same way. Declaring both is two names for one effect
  and is refused (GSAS-II's `Pref.Ori.` holds one kind).
- **D6 — the basis is derived from the operators, with GSAS-II's functions
  as the golden.** The symmetry action on degree-l harmonics is irrational
  for three- and six-fold axes, so `_nullspace_int` does not apply. The
  rational route through hkl monomials (Stephens' construction at degree L)
  mixes the orders and needs the metric to remove l = 0, so its coefficients
  would compare with no other code. Construction: real orthonormal harmonics
  of the reciprocal vector's Cartesian direction; per l, the invariant
  subspace is the range of the Reynolds projector (1/|G⁺|) Σ D_l(R) over the
  Laue group's proper rotations, which are orthogonal in Cartesian space and
  so well conditioned; the frame follows the operators (polar axis on the
  principal axis, the monoclinic two-fold whichever cell edge carries it,
  [111]* on rhombohedral axes), and the basis is chosen to coincide with
  GSAS-II's K_l^n in GSAS-II's frame (`G2lat.CrsAng`, `GSASIIlattice.py:2859`).
  Where it cannot coincide, the conversion matrix is recorded instead. The
  coefficients are the parameters, with no DOF indirection, because the
  basis is symmetric by construction (Stephens needs DOFs because its
  monomials are not). The basis is evaluated at the representative hkl. An
  invariant function needs no orbit average, so the frozen orbit serves as a
  test, not a cost.

### Licensing

GSAS-II is a behavioural reference and a source of goldens; no code is
ported (ATTRIBUTION.md: custom Argonne licence with a grant-back clause).
MAUD (Lutterotti, BSD-3) implements harmonic texture and may be ported with
attribution; its ATTRIBUTION row names this path. TOPAS is closed, so its
Technical Reference only. A copy sits on the maintainer's OneDrive
(`TOPAS-5 Technical_Reference.pdf`) and could not be read on 2026-10-14
because it was not downloaded. Bunge's tables are published numbers.

### Inherited

## Non-goals

- **An orientation distribution refined from several sample orientations**
  (GSAS-II's phase-level Texture tab). It needs pole figures, which one
  histogram does not contain, and non-cylindrical sample symmetry (rolling
  mmm, shear 2/m) goes with it.
- **Odd orders.** A powder cannot break Friedel symmetry.
- **Replacing March-Dollase.** It is one parameter against 2-44 here and the
  better-conditioned model for one fibre axis.
- **Choosing the order automatically.** The order scan over `report/texture.py`'s
  extracted corrections is the follow-up. File it once Task 2's basis exists.
- **The pole-figure render.** WP-1318 builds the directional surface for
  Stephens strain; an inherited note there says the two share it.
- **GSAS-I `.EXP` texture terms.** No file in the tree carries one.
- **A texture editor in the GUI's model panel**, unless March-Dollase has one
  by the time this starts (none on 2026-10-14).

## Tasks

- [ ] **Pin the convention.** Read Von Dreele (1997), Bunge's chapter on
      symmetrised harmonics with the table GSAS-II's cubic coefficients cite
      (its `BOH`, "Table 15.2.1 … 1993, p 501"), and the TOPAS Technical
      Reference on `spherical_harmonics_hkl` and `PO_Spherical_Harmonics`.
      Decide D2. Write the GSAS-II and TOPAS conversions here. Generate the
      golden: GSAS-II 5.8.4's P for each Laue class's standard setting, the
      three monoclinic unique axes and rhombohedral axes, orders up to 8, a
      fixed hkl list and cell per class, under `Bragg` and `Debye`. Commit the
      numbers only, as JSON under `tests/data/` with a README provenance row
      naming the generator script (measurement 4 says how not to call it).
- [ ] **`crystallography/harmonics.py`**: the real harmonics, the projector,
      the frame and the canonical basis (D6), with the Rᵀ trap named in the
      docstring. Tests: the span equals GSAS-II's for every class except
      m-3 at l = 6, where GSAS-II's is a proper subspace (measurement 2); for
      every one of gemmi's settings, the orbit average of a random harmonic
      under h → Rᵀh lies in the span (the "true metric lies in the span"
      check, one rank up); counts equal the character formula.
- [ ] **Schema**: `SphericalHarmonicTexture` (`order`, `coefficients`
      as name → `Parameter`, default value 0, `vary=False`) on
      `Phase.texture`. Validators refuse an odd order and a phase declaring
      both blocks (D5). The two refusals that need the Laue class, an order
      with no term (D3) and a name outside the allowed set, raise in
      `ParameterTable.__init__` (root CLAUDE.md, "Pydantic knows no
      crystallography"). Names in a bijection with GSAS-II's C(l,n), carrying no bracket
      or comma; proposed `c4_0`, `c4_4`, `c4_neg4`, never TOPAS's `p`/`m`
      letters, which mark a different split. JSON round trip. Bump
      `SCHEMA_VERSION` (0.54 at e66fb223; re-read it). A `help.py` entry for
      `phases.*.texture.*`, the `gui/src/lib/history.ts` `PLACES` row with a
      rebuilt dist, and a derived `capabilities()` feature flag.
- [ ] **Parameter table and holds**: one entry per allowed coefficient;
      `mode_fixed_path` gains `.texture.` (measurement 3); check that the
      absent-phase hold (WP-1301) reaches `phases.i.texture.*` as it reaches
      `preferred_orientation.r`.
- [ ] **Forward model**: compile the (l, n) set and the per-l factor
      (4π/(2l+1))·k_l(ψ) onto the compiled phase at stage compile, Rietveld
      only. Evaluate K at the current cell and fold P into `base` beside
      March-Dollase, memoised on (cell, C). No code path runs when
      `texture is None`. C = 0 gives P = 1 exactly, so both fits are
      bit-identical to a texture-free one (the goldens declare
      `compiled.set_enabled`). The traced twin goes through `xp` inside
      `backend.traced.active`, with no frozen numpy constant on the left of
      an operator. No kernel change is expected: check that `model/compiled.py`
      reads `base` after P is folded.
- [ ] **Jacobian**: `texture_intensity_grad` beside `po_intensity_grad`
      (the intensity with P divided out, computed directly so P = 0 is safe,
      times the factor and K), a `_TEXTURE_PATH` route, an `_INTENSITY_ONLY`
      row and a declared reach. The cell columns must carry ∂P/∂cell the way
      they carry March-Dollase's: verify it. The oracle is exactness at a
      100 % step, the parameter being linear (root CLAUDE.md, the branch
      oracle rule). A `tests/test_cross_backend.py` config with texture and a
      free cell.
- [ ] **Positivity and the record** (D4): `texture_positivity_inequalities`
      beside `strain_cone_inequalities`; `TEXTURE_NOT_POSITIVE` as a new
      `GuardFinding`; per-phase result fields for J and for the minimum P
      over the observed reflections and over the sphere, each with its
      writer named (WP-1076). These fields are the correction's evidence. Rwp
      is not (root CLAUDE.md).
- [ ] **Plans**: every stage that frees `phases.*.preferred_orientation.r`
      also frees `phases.*.texture.*`, which matches only a declared block.
      `PLAN_INFO` says so.
- [ ] **Readers and writers**: TOPAS `PO_Spherical_Harmonics(sh, order)`
      imports into `Phase.texture` through Task 1's conversion, measured
      against TOPAS's own output (root CLAUDE.md, a foreign unit). The
      coverage row splits: `spherical_harmonics_hkl` inside a width equation,
      as in the Durham ZrMo₂O₈ file of WP-1130, is hkl-dependent broadening
      and stays reported. GSAS-II's `_hap` reads an `SH` entry's order and
      coefficients instead of the stale slots, and the import refuses a
      `Debye` histogram whose goniometer angles make ψ vary with θ, unless D2
      took GSAS-II's ψ. The CIF and FullProf writers state the block or say
      they cannot (`io/exporters.py:464`, `io/projects/fullprof.py:3466`
      show what March-Dollase does).
- [ ] **`rietx compare`**: a `+ spherical-harmonics texture` variant beside
      `preferred_orientation`, run on the `brucite` standard
      (`qarr/brucite.prn`; `viz/compare.py` has no cpd-2 standard), and its
      row in `tests/test_compare_ui.py`.
- [ ] **Manual**: the equation in Part 2 (`corrections.md`, with its
      `*Source:*` line) replacing the "not implemented yet" sentence; the
      § Scope sentence in `manual.md`; Part 1 prose on declaring a block and
      reading J and the guard.
- [ ] **Tests and acceptance**: the units above; synthetic recovery
      (noise-free patterns from known C for an m-3m, a 6/mmm, a -3m1, an mmm
      and a 2/m phase, under `bragg_brentano` and `debye_scherrer`, recovered
      from C = 0 to 1e-6 relative; with Poisson noise, within 3 esd); the
      GSAS-II golden; cpd-2 below; obs/calc/diff PNGs to `tests/output/`.
- [ ] **Skill**: a reference row for `TEXTURE_NOT_POSITIVE` and the
      `phases.*.texture.*` family, and the routing row an agent needs to
      choose between March-Dollase and an order (tagged Hypothesis until the
      cpd-2 numbers exist).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_harmonics.py tests/test_texture.py tests/test_cross_backend.py tests/test_compare_ui.py
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_acceptance_qpa_roundrobin.py
.venv/bin/python -m ruff check src tests examples
```

- **Construction**: synthetic C recovered as above, and the identity
  bit-identical at `texture=None` and at C = 0.
- **Cross-code**: P equals the GSAS-II golden to 1e-12 relative wherever the
  bases coincide, through the stated conversion elsewhere.
- **Real data, public**: IUCr CPD round-robin sample 2 (`qarr/cpd-2.prn`;
  brucite, P-3m1, strongly platy), the protocol of
  `test_sample2_brucite_march_dollase` with the brucite block swapped for
  order 4 and order 6. Gate: every weighed fraction within the suite's
  `MAJOR_TOL` (6.0 wt %), the bar March-Dollase meets today, and C_2^0's sign reads platy under D2's
  frame. Report the weighed-composition errors beside March-Dollase's. That
  accuracy number is the evidence, and Rwp is not.
- **Real data, if contributed**: the SRM 1976a plate against its TOPAS
  refinement, coefficients term by term. It needs the owner's pattern and
  `.inp` in the tree under the mg2044 precedent (PR #120). Ask on #131.

## References

- Von Dreele, R. B. (1997). *J. Appl. Cryst.* 30, 517-525. Not in the local
  corpus; citation from memory, check it.
- Bunge, H.-J. (1982). *Texture Analysis in Materials Science*. Butterworths
  (GSAS-II cites the 1993 Cuvillier reprint). Not held.
- Järvinen, M. (1993). *J. Appl. Cryst.* 26, 525-531, symmetrised harmonics
  as a Rietveld correction. Not held; citation from memory.
- Popa, N. C. (1992). *J. Appl. Cryst.* 25, 611-616. Not held; citation from
  memory.
- Whitfield, P. S. (2009). *J. Appl. Cryst.* 42, 134-136, on order choice
  and its cost. Not held; citation from memory.
- Dollase, W. A. (1986). *J. Appl. Cryst.* 19, 267; March, A. (1932).
  *Z. Kristallogr.* 81, 285. The single-axis model kept beside it.
- Toby, B. H. & Von Dreele, R. B. (2013). *J. Appl. Cryst.* 46, 544-549
  (GSAS-II). GSAS-II 5.8.4, read as behaviour: `GSASIIstrMath.SHPOcal`
  (3010), `penaltyFxn`'s `SH-Pref.Ori.` (847-872); `GSASIIlattice.OdfChk`
  and `GenSHCoeffT` (2792-2857), `CrsAng` (2859), `SamAng` (2929), `BOH`,
  `Lnorm`, `GetKcl`, `GetKsl` (2995-3106), `textureIndex` (3467).
- Coelho, A. A., TOPAS 5 Technical Reference, `PO_Spherical_Harmonics` and
  `spherical_harmonics_hkl`.

## Handover log

### 2026-10-14 — filed, and the fence moved

Spherical-harmonics texture is now scheduled work rather than a v2 line item,
and the design questions #131 left open are mostly answered before any code.
Two of its three open questions are settled from prior art: the sample term
comes from the geometry, and the order is declared. The third, which frame
the coefficients are quoted in, now has numbers on both sides and waits only
on reading Von Dreele (1997). Scoping also found that GSAS-II, the code this
WP takes as its golden, is itself one term short for Laue class m-3, so its
numbers cannot be copied blind.

- **Done.** This file; the ROADMAP § v2+ entry and table row, root CLAUDE.md's
  fence list, a DESIGN.md *Texture fence revised* entry, the manual's two
  "planned for v2" sentences (the § Scope one also said neutron data were not
  implemented, stale since WP-1134), the TOPAS coverage message, the MAUD
  attribution row, and WP-1318's inherited note. No open WP owns this work:
  WP-1318 names it as a non-goal, and WP-1325 only records the request.
- **Measured** at e66fb223, `[dev]`, darwin/arm64 (§ Measured while scoping
  has the numbers): GSAS-II 5.8.4's ψ per instrument type, the per-class term
  counts with the m-3 discrepancy, and the Le Bail dead columns for
  March-Dollase and extinction. The probes are scratchpad scripts, not
  committed: `g2_samang.py`, `sh_counts.py`, `lebail_po_probe.py`.
- **Reviewed.** `/code-review high --fix` made seven fixes, all accepted. D4's
  rows are linear in C, and in θ only while the cell is held. The
  Laue-class refusals move to `ParameterTable.__init__`. The compare task
  names the `brucite` standard, since `viz/compare.py` has no cpd-2 one.
  D2's conversion states its direction. The manual's texture sentence moved
  after the TOF exception it had split. The stale fence claims in WP-1325's
  `### Inherited` and in `model/preferred_orientation.py`'s docstring were
  corrected. WP-1318's own Non-goals bullet was left, its inherited note
  saying it is stale.
- **Suite.** The fast selection passed, 9591 passed, 186 skipped, 1 xfailed,
  `[dev]`, darwin/arm64, with the review running beside it. No test was
  added. The full selection was not run, since nothing here moves a
  measured number.
- **Not filed.** The Le Bail dead columns for `preferred_orientation.r` and
  `extinction` have no open owner (1343 and 1418 touch `mode_fixed_path` for
  magnetic widths only). They were offered to the maintainer as a separate WP
  under § What fires, and what stays silent, and are not in this one's tasks
  beyond the texture block's own entry. No skill row was added for them,
  because the fix makes the workaround moot.
- **Gotchas.** The TOPAS Technical Reference on the maintainer's OneDrive was
  a cloud placeholder and could not be read. GSAS-II's harmonic functions
  return zeros when called directly (measurement 4).

Next: get the papers in References, Von Dreele (1997) first because it decides
D2. Then Task 1, whose golden every later test compares against.
