# WP-1020 — Indexing core: Q-space, reduced cells, Bravais, FoM panel, ambiguity

Milestone: v1.0 · Status: ✅ 2026-07-30
Depends on: 1018 (1019 soft)

## Goal

Everything the three engines share: the Q(hkl) quadratic form and its
symmetry-allowed subspaces, weighted candidate refinement, reduced cells and
Bravais determination, the figure-of-merit **panel**, and geometrical-ambiguity
enumeration. After this WP a cell can be scored, reduced, classified and
compared — no engine yet.

## Context

- **Q is linear in the metric, and that is load-bearing three times over.**
  With hkl assigned, `Q = 1/d² = Ah² + Bk² + Cl² + Dkl + Ehl + Fhk` where
  `(A..F) = (G*₁₁, G*₂₂, G*₃₃, 2G*₂₃, 2G*₁₃, 2G*₁₂)`. Consequences: candidate
  refinement is *weighted linear* least squares; WP-1022's trial-and-error is
  an exact n×n solve; and WP-1021's dichotomy bounds are attained exactly at
  box corners, so it searches A..F rather than (a,b,c,α,β,γ). d and 2θ are
  **not** linear in the metric — that is why indexing works in Q.
  *Source*: Altomare, Cuocci, Moliterni & Rizzi (2019), IT Vol. H ch. 3.4,
  eq. (3.4.2).
- **`inv_d_squared` already exists after WP-1018** (extracted from
  `lattice.d_spacings`); use it, do not re-derive `1/d²` from `d`.
- **The symmetry-allowed metric subspace needs no new code and no case
  table.** The allowed G* patterns span `∩ker(A(R) − I)` under
  `A(R)[U] = R U Rᵀ` — which is *exactly*
  `crystallography.wyckoff.adp_basis(rotations)`, already implemented over
  exact `Fraction` arithmetic via `_nullspace_int`. ~~Call it with the
  **transposed** rotations (CLAUDE.md: reciprocal-space symmetry action is Rᵀ).~~
  **Corrected on measurement (2026-07-30): call it with the rotations
  UNTRANSPOSED.** The Rᵀ rule is about *hkl*; a tensor contracting with h twice is
  invariant under U → R·U·Rᵀ, and G\* is such a tensor. The transposed call returns
  the *direct* metric's invariants — the same dimension in every system, so the
  criterion below is satisfied by the wrong subspace (hexagonal came out F = −A
  where the reciprocal metric has F = +A). See the handover log.
  Dimensions must come out 1/2/2/2/3/4/6 for cubic / tetragonal / hexagonal /
  trigonal / orthorhombic / monoclinic / triclinic — assert that against
  `params.vector._CELL_TIES` and `_FIXED_ANGLES`, i.e. the derived answer must
  reproduce the tabulated one. This is `wyckoff._compatible_lattice`'s trick
  one rank down, and it is why it stays correct in non-standard settings.
- **Reduction and Bravais are already in the dependencies — verified
  2026-07-29 in `.venv` (gemmi 0.7.5, spglib 2.7.0), both hard deps, MPL-2.0
  and BSD-3, neither on the licensing fence:**
  `gemmi.GruberVector(cell, centring, track_change_of_basis=True)` with
  `.niggli_reduce()`, `.buerger_reduce()`, `.selling()` (Delaunay),
  `.is_niggli`, `.normalize()`, `.get_cell()`, `.change_of_basis` (a
  `gemmi.Op`); `gemmi.find_lattice_symmetry(cell, centring, max_obliq)` and
  `find_lattice_2fold_ops` (Le Page 1982); `spglib.niggli_reduce`,
  `delaunay_reduce`, and `get_symmetry_dataset((lattice,[[0,0,0]],[1]),
  symprec)` returning `.international`, `.std_lattice`,
  `.transformation_matrix`. Measured: the bethanechol cell
  `(8.875,16.408,7.137,90,93.84,90)` reduces in one step to
  `(7.137,8.875,16.408,90,90,93.84)` with change-of-basis `y,z,x`; a bcc
  primitive cell is order-24 to gemmi and `Im-3m` with `std_lattice = 10×10×10`
  to spglib. **Do not hand-write Niggli/Delaunay.**
- **Two independent opinions on Bravais, for free.** gemmi's tolerance is a Le
  Page **obliquity in degrees**; spglib's is a distance **`symprec` in Å**.
  Different parameterisations of the same question, so run both and sweep the
  tolerance (obliquity 0.5/1/2/3°; symprec from the propagated cell esds).
  Report the highest symmetry **stable across the sweep**; symmetry that
  appears only at the loosest tolerance is ambiguous, not an answer. Same device
  as `direction="both"` in `sequential.py`. (The *diagnostic*
  `INDEX_BRAVAIS_AMBIGUOUS` went to WP-1024: this WP emits none, having no answer
  to qualify. `BravaisScreen.ambiguous` and `.methods_disagree` carry the verdict.)
- **What must still be hand-written**: the tolerance-aware cell-equality
  metric, the derivative-lattice enumeration, and conventional-cell selection
  when metric symmetry exceeds the reduced primitive cell's.
- **Dedup is a χ² test, not a percentage.** Two candidates are the same lattice
  when their Niggli-reduced A..F vectors agree under `χ² = ΔᵀΣ⁻¹Δ` against
  `χ²₆(0.99)` with their joint covariance; fall back to a relative bound
  (0.5 %) only when covariances are absent. A fixed percentage merges distinct
  synchrotron cells and splits noisy lab ones — per-line σ doing work again.
- **The FoM panel must score coverage in BOTH directions, and this is
  measured, not aesthetic.** Prior art check D (tag `guillemot-study`,
  `studies/guillemot/out/audit_full.txt` — see References for how to read it):
  screening MnSb_34, whose answer is known, **NaSb ranks first on share of
  observed intensity indexed (83.7 %) with 390 predicted lines of which 9.0 %
  are present**, above the truth MnSb (79.2 % indexed, **56.5 %** of its own 23
  lines seen). A big cell indexes everything and means nothing. So
  `predicted_seen_fraction` is a **first-class ranking member**, not a
  post-hoc validation field. This is also Oishi-Tomiyasu's (2013) argument for
  the reversed de Wolff FoM, reached independently on this repo's own data.
- Every FoM function's docstring carries author/year/journal **and its blind
  spot**, and the blind spot is copied verbatim into
  `FigureOfMerit.blind_spot` so a consumer never sees a number without it:
  M₂₀ counts *lattice*-possible lines, so it is blind to space-group
  extinctions and is wrecked by one impurity line; F_N lives in 2θ, so a
  refined zero can manufacture a large value; `lebail_rwp` rewards flexibility.
- **Ranking is never on one member**: `(len(found_by) desc, Borda over the
  panel, volume asc)` — volume-ascending as Occam's tiebreak, since between two
  cells indexing the same lines the smaller is the lattice and the larger is a
  supercell.
- **Geometrical ambiguity is reported, never resolved.** Distinct lattices can
  give calculated patterns with identical line positions (Mighell & Santoro
  1975); the powder pattern carries only the *length* of the reciprocal vector.
  Enumerate derivative lattices of index 2-4 via integer matrices in Hermite
  normal form (a small closed set: 7 / 13 / 35), reduce, skip those reducing to
  the parent (a setting change is dedup, not ambiguity), and test the rest
  against the observed Q set. Report partners with their transformation matrix
  **and their `discriminating_reflections`** — the hkl that would break the
  tie, with the 2θ and intensity that would have to be present. That last part
  is what makes the report actionable rather than merely honest, and it is the
  structural twin of Layer 2's "extend the fit range".

### Inherited

From **WP-1018**: `inv_d_squared` is in `crystallography/lattice.py`; import it.
`ObservedPeak` carries `q` and `q_esd` already propagated, so do not recompute
from `two_theta_esd`.

**Correction (WP-1018, 2026-07-30): the σ(Q) constant this section carried was
wrong by a factor of 2.** It read `σ(Q) = (π/180)·sin(2θ)/λ²·σ(2θ)`; the correct
propagation is

    σ(Q) = (π/90)·sin(2θ)/λ²·σ(2θ)

Differentiating Q = 4sin²θ/λ² with respect to 2θ *in degrees* picks up **two**
halvings-and-doublings that partly cancel: `dQ/dθ_rad = 4·sin(2θ)/λ²`, then
`dθ_rad/d(2θ°) = (π/180)/2`, giving `(π/90)`. Applying only the degree
conversion and forgetting the θ = (2θ)/2 chain — or the reverse — is exactly how
the π/180 form arises. Verified against a central difference (ratio 1.0000000014
for π/90, 0.5000000007 for π/180) and pinned in
`tests/test_peak_picking.py`. The implementation in
`schemas.indexing.q_esd_of_two_theta` is correct; **import it rather than
retyping the constant**, and note that an engine that had silently used the old
form would have weighted every line by 4× its true 1/σ², i.e. been four times
too confident.

Also from **WP-1018**: `PeakList` exposes `q()`, `q_esd()`, `two_theta()`,
`two_theta_esd()` and `intensity()` as arrays over `usable()` only — ghosts,
failed fits and caller exclusions are already out, so an engine does not filter.
A `PeakList` validator re-derives every peak's `q` from its `two_theta` and the
list wavelength and raises on disagreement, so hand-building an `ObservedPeak`
with a stale `q` fails loudly rather than mis-indexing quietly.

**The caveat that used to sit here is discharged: σ(2θ) is now calibrated, so a
tolerance model may be tuned against it.** WP-1018 closed 2026-07-30 with the
pull ensemble measured — `(2θ_fit − 2θ_true)/σ_fit` has mean +0.032 / std 0.971
on a synchrotron single line and mean −0.083 / std 0.980 on a lab Cu Kα doublet,
over ~1300 fitted lines each. Three consequences for this WP:

- **σ(2θ) is unbiased to ~0.1σ and correctly scaled to ~3 %.** A "3σ(Q)" window
  here really admits ~99.7 % of correctly-indexed lines; it is not secretly a 2σ
  or 5σ window. Tolerance constants may be written as multiples of σ_eff.
- **What σ does *not* cover is the systematic shift**, and the ratio is the
  reason WP-1019 exists: per-line σ(2θ) is 2e-4 to 2e-3° on strong lines, while
  the bethanechol shift is ~0.10° — two to three orders larger. So σ_eff without
  a σ_sys floor will reject the *true* cell on real data. Do not soften the
  σ-scaling to compensate; add the floor (1019) or, if 1019 has not landed, fit
  `constant` here and keep σ_sys explicit rather than folded into a fudged
  tolerance.
- **A residual −0.08σ bias exists on doublet data** and is localised to the
  detection-seeded window, not the estimator (four other mechanisms were
  measured and excluded — see 1018's handover). In degrees it is 2e-5°, so it is
  irrelevant to any Q window this WP will set; it matters only if some future
  statistic averages positions over many lines, where a bias does not average
  down.

Also worth carrying: **rank-then-measure applies to any census this WP takes.**
The width census that sets the fitter's windows reads ~10 % wide on a doublet
because it measures the *composite* FWHM; a Q-space census that ranks by
intensity and then measures inherits the same trap in a new costume.

From **WP-1019** (soft): `DataQualityReport.shift_template` names which
template `refine_candidate` should carry as its one nonlinear column, and
`σ_sys` is the floor added in quadrature to each line's σ(Q). If 1019 has not
landed, default to `constant` and `σ_sys = 0` and leave the seam.

From **WP-1019** (landed 2026-07-30), five things this WP must not re-derive:

- **The API is `assess_peak_list(peaks, *, reference_two_theta=None,
  sigma_sys_deg=None)` → `DataQualityReport`**, and the shift screen is
  *conditional*: with no cell there is nothing to deviate from, so a shift is
  identifiable only against reference positions. `shift.source` is `"measured"`
  or `"unavailable"`, and `"unavailable"` is the **normal** state at index time.
  So `refine_candidate` cannot expect a template from 1019 on the first pass —
  default to `constant` and, once a candidate exists, feed its own predicted
  positions back through `fit_shift_model(tt, tt − ref, esd)` to attribute the
  shift *afterwards*. That is the seam, and it is the right way round.
- **`ShiftScreen.prediction_spread_deg` is the number the tolerance model wants
  when `separable` is False** — the largest disagreement, over the angles
  sampled, between the corrections the *competitive* templates predict. Measured:
  0.0011° over 10-25° for a 0.10° cos θ shift (1 % of it), against 0.046° if the
  rejected template is included. Add `sigma_sys_deg` in quadrature to each line's
  σ(Q) as planned; treat `prediction_spread_deg` as a *separate systematic* on the
  cell, not as another σ to combine — it is a bias direction, not scatter.
- **`DataQualityReport.volume_envelope` is a dict per system, not a float**, and
  it is scaled by Laue orbit factor × worst-case centring multiplicity. Read the
  entry for the system being searched. With the Laue factor alone the envelope
  *excluded* corundum's true volume (125 Å³ against 255); with neither, a cubic
  search would be bounded 96× too tightly. `volume_envelope(..., 
  centring_multiplicity=n)` tightens it once WP-1025 knows the extinction symbol.
- **`METRIC_DOF` already exists** in `schemas/indexing.py` (cubic 1 … triclinic
  6) with `MIN_LINES_PER_DOF = 5`, and `DataQualityReport.systems_supported` is
  the list of systems the data can support at all. Import them rather than
  hardcoding 1/2/2/3/4/6 — 1022's Inherited note already says the same thing
  about `adp_basis(Rᵀ)`, and these two must agree.
- **`tan_theta` is deliberately not a shift template.** A tanθ deviation is a
  *cell* error and belongs to `refine_candidate`'s cell columns; if a shift
  screen were ever given it, it could "explain" a shift by changing the answer.

## Non-goals

- No search engines (1021-1023), no consensus or confidence gate (1024), no
  space-group screen (1025).
- No hand-written Niggli or Delaunay — see Context.
- Ambiguity enumeration stops at index 4; higher-index derivative lattices are
  a fence, recorded not attempted.

## Tasks

- [x] `indexing/qspace.py`: Q form, σ(Q) propagation, A..F ↔ cell with
      **analytic** delta-method esds (do not finite-difference — the analytic
      preference everywhere else in this package), symmetry subspaces via
      ~~`adp_basis(Rᵀ)`~~ **`adp_basis(R)` — untransposed; see the handover log,
      the transposed call gives the direct metric's invariants with the same
      dimension in every system.**
- [x] `refine_candidate(peaks, assignment, *, system, shift_model)`: weighted
      linear solve `min Σ wᵢ(Qᵢ − Σ M_ip θ_p)²`, `w = 1/σ_eff²`, plus at most
      one nonlinear shift coefficient with an analytic Jacobian column
      ~~`∂Q/∂δ = −(π/180)·sin(2θ)/λ²·t(θ)`~~ **`−(π/90)·…` — the same
      factor-of-2 this file's σ(Q) line carried**; esds from
      `χ²_red·pinv(MᵀWM)`, routed through `statistics.normal_covariance`.
- [x] `indexing/reduce.py`: Niggli/Delaunay via gemmi with a spglib
      cross-check (an identity test, not a fallback); two-opinion Bravais with
      the tolerance sweep; conventional-cell derivation; the χ² reduced-cell
      equality used for dedup. `BravaisScreen.ambiguous` /
      `.methods_disagree` carry the verdict; the `INDEX_BRAVAIS_AMBIGUOUS`
      *diagnostic* is left to WP-1024, where a `CellCandidate` exists to attach
      it to (this WP emits no diagnostics — it has no answer to qualify).
- [x] `indexing/fom.py`: `m20`, `f_n`, `indexed_fraction` (lines **and**
      intensity), **`predicted_seen_fraction`** — each with its citation and
      blind spot as a *field*; the Borda ranking helper; `fom_panel_disagrees`;
      `lattice_group`, `predicted_lines`, `match_lines`,
      `nearest_discrepancy`. **`m20_reversed`, `m20_symmetric`, `wrip20` and
      `mcm20` are NOT implemented** — their formulas need their papers before
      they can be attributed correctly (handover log). `lebail_rwp` needs a Le
      Bail fit against a candidate, i.e. WP-1024's `structure_from_candidate`.
- [x] `indexing/ambiguity.py`: HNF derivative-lattice enumeration (index 2-4 —
      7/13/35 matrices, verified), partner test, `discriminating_reflections`.
- [x] `schemas/indexing.py`: `FigureOfMerit`, `AmbiguityPartner`,
      `CellCandidate`.
- [x] `docs/manual/indexing.md` — the Q form, the FoM definitions, the σ(Q)
      propagation. Every displayed equation needs a `*Source:*` line whose
      symbol imports, fenced constants need a `conf.py` line **and** a use, and
      every new bib entry must be cited: `tests/test_manual.py` fails the fast
      suite otherwise.
- [x] `tests/test_indexing_core.py` + `tests/test_indexing_reduce.py` (40
      tests, ~7 s):
      metric-subspace dimensions vs `_CELL_TIES`; **exact linear recovery** of
      A..F from a random cell with true assignments (to 1e-10 — the linearity
      claim, checked); **Niggli idempotence and unimodular invariance**
      (`niggli(niggli(C)) == niggli(C)`, `niggli(T·C) == niggli(C)` for random
      integer T with `|det T| = 1`) via hypothesis; and a **paired** FoM test —
      M₂₀ invariant under a unimodular setting change, F_N explicitly *not*
      invariant under a zero shift, which turns a documented blind spot into a
      tested one.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_core.py tests/test_indexing_reduce.py -q
.venv/bin/python -m pytest tests/test_manual.py -q
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

Criterion: the derived metric-subspace dimensions equal the tabulated cell DOF
for every crystal system; Niggli reduction is idempotent and unimodular-invariant
on 200 hypothesis-generated cells; and on the check-D data the truth outranks
the 390-line impostor once `predicted_seen_fraction` is in the panel.

## References

- Altomare, A., Cuocci, C., Moliterni, A. & Rizzi, R. (2019). "Indexing a
  powder diffraction pattern", *International Tables for Crystallography*
  Vol. H (*Powder Diffraction*), ch. 3.4, pp. 270-281. **Note the year**: the
  chapter cites Oishi-Tomiyasu (2016) and Louër & Boultif (2014), so it cannot
  be the 2007 some filenames carry. Confirm the editor line against the volume
  before it enters ATTRIBUTION.md.
- de Wolff, P. M. (1968). *J. Appl. Cryst.* **1**, 108-113 — M₂₀.
- Smith, G. S. & Snyder, R. L. (1979). *J. Appl. Cryst.* **12**, 60-65 — F_N.
- Oishi-Tomiyasu, R. (2013). *J. Appl. Cryst.* **46**, 1277-1282 — reversed and
  symmetric de Wolff FoM, and the asymmetry argument this WP measures.
- Altomare, A. *et al.* (2009). *J. Appl. Cryst.* **42**, 768-775 — WRIP20.
- Le Bail, A. (2008). In *Principles and Applications of Powder Diffraction* —
  McM₂₀.
- Mighell, A. D. & Santoro, A. (1975). *J. Appl. Cryst.* **8**, 372-374 —
  geometrical ambiguities; transformation-matrix examples in IT-H Table 3.4.2.
- Le Page, Y. (1982). *J. Appl. Cryst.* **15**, 255-259 — the 2-fold search
  behind `gemmi.find_lattice_2fold_ops`.
- Prior art at the tag `guillemot-study` (**not merged into `main`**; §D's
  numbers are restated in Context, so this is corroboration):

  ```sh
  git show guillemot-study:studies/guillemot/out/audit_full.txt   # §D
  git show guillemot-study:studies/guillemot/match_hl2.py         # the screen
  ```

## Handover log

- **2026-07-30 — CLOSED.** `indexing/{qspace,reduce,fom,ambiguity}.py`,
  `FigureOfMerit`/`AmbiguityPartner`/`CellCandidate` in `schemas/indexing.py`,
  `docs/manual/indexing.md`, and `tests/test_indexing_{core,reduce}.py` (40 tests,
  ~7 s). Fast suite 1175 passed / 66 skipped in 40 s; **full suite including the
  `slow` real-data acceptance 1251 passed / 70 skipped / 0 failed** (this
  worktree's venv is `[dev,jax]`, so the torch rows self-skip); ruff clean; manual
  `-W` clean with its five guards green. One environment note for whoever quotes
  numbers next: pytest's final count line does not survive this shell's background
  capture — the counts above are derived from the progress characters, and the
  authoritative signal is the exit code. **No engine and no diagnostics** — this WP has
  no answer to qualify, so `INDEX_BRAVAIS_AMBIGUOUS` and the rest go to 1024 where
  a `CellCandidate` exists to attach them to.

  *Four defects. Three of them passed the test that "should" have caught them,
  which is the lesson worth carrying more than the fixes.*

  1. **The metric subspace was derived from the *transposed* rotations, and the
     dimension test passed anyway.** CLAUDE.md's "reciprocal-space symmetry action
     is Rᵀ" is about **hkl**: h → Rᵀh. A tensor that contracts with h *twice* is
     therefore invariant under U → R·U·Rᵀ — the same statement, since
     (Rᵀh)ᵀU(Rᵀh) = hᵀ(RURᵀ)h — and G\* is such a tensor, exactly like the U\* form
     of an ADP. Passing Rᵀ returns the invariants of the **direct** metric G. Same
     dimension in every system, because the transposed set is a group too, so
     1/2/2/2/3/4/6 came out right and the acceptance criterion was met by the wrong
     subspace; the hexagonal basis had F = −A (direct cos γ = −½) where the
     reciprocal metric has F = +A. What catches it is asserting that the **true**
     metric lies in the span, which is now a test.
  2. **A Gauss-Newton sign error that looks right in the θ block.** For
     r = (Q(2θ − s·t) − Mθ)·w, both ∂r/∂θ and ∂r/∂s are negative, so the step
     solves [+M·w, −∂r/∂s]·Δ = r — *both* flipped together. Flipping only the θ
     block is locally correct on its own (+M·w·Δθ = r is the right linear solve),
     which is why it looked fine; the shift column then has the wrong relative
     sign and s runs away. Measured: −11.65 for an injected +0.05°.
  3. **M₂₀ was not invariant under a unimodular setting change, by 5 %.** N_poss
     counts predictions up to the N-th observed line, and that line *is* one of
     the predictions, so a strict comparison makes the count depend on fp
     rounding: the same lattice in two settings gave N_poss 20 and 19 and M₂₀
     76.43 and 80.45. The boundary now carries a relative tie tolerance
     (`_BOUNDARY_RTOL`), and the invariance is asserted rather than assumed.
  4. **A perfect cell scored M₂₀ = 0.** The figure divides by ⟨ΔQ⟩, which → 0
     when a candidate fits within fp noise; unfloored it is infinite, and the
     obvious zero-guard ranks the *right* answer last. Both were seen. ⟨ΔQ⟩ and
     F_N's ⟨|Δ2θ|⟩ are now floored at the median σ — a *meaning*, not an epsilon:
     a discrepancy below the measurement precision is not knowable, and per-line σ
     is exactly what this package has and 1968 did not. Measured, the floor makes
     M₂₀ scale exactly inversely with the data's precision (10× worse σ → 10×
     smaller M₂₀), which is the right behaviour for a signal-to-noise ratio.

  *Two dependency facts worth not rediscovering.* `gemmi.is_niggli` is **not** a
  fixed-point test on floating-point input — a rhombohedral cell (3, 3, 3, 65°,
  65°, 65°) whose reduction changes nothing to 1e-15 reports `False` on the second
  pass — so the field is named `already_reduced`, documented as gemmi's own
  predicate, and idempotence is asserted on the parameters. And the two Bravais
  opinions genuinely disagree on pseudosymmetry *because their tolerances are
  different kinds of number*: on a 1 %-tetragonal cell gemmi (obliquity ≥ 1°) says
  cubic while spglib (symprec ≤ 0.01 Å) says tetragonal, so the screen keeps each
  method's tightest answer separately (`system_gemmi`, `system_spglib`) and takes
  the conservative one, instead of pairing tolerances that are not comparable.
  Monotonicity in the tolerance is asserted, and it is what makes "stable across
  the sweep" equal to "the tightest tolerance's answer".

  *What is deliberately NOT in `fom.py`, and it needs the user rather than a
  session.* `m20_reversed`, `m20_symmetric` (Oishi-Tomiyasu 2013), `wrip20`
  (Altomare 2009) and `mcm20` (Le Bail 2008) are **not implemented**: their
  formulas cannot be written down from memory with correct attribution, and
  guessing one and citing a paper for it is precisely the WP-0501 b₂ failure in a
  new costume. The panel's *argument* — coverage scored in both directions — is
  fully implemented via `indexed_fraction` and `predicted_seen_fraction`, which is
  what the measured §D result actually demands; the extra figures would add
  independent opinions to the Borda count, not a missing capability. `lebail_rwp`
  is a different matter: it needs a Le Bail fit against a candidate structure,
  i.e. WP-1024's `structure_from_candidate`, so it belongs there.

  *One number this WP owes 1021-1023.* `refine_candidate` without a shift is a
  single `lstsq` on an (N, m) system — no iteration, no scipy call, because it is
  the engines' inner loop. With a shift it is Gauss-Newton (≤ 8 steps, converging
  in 2-3). Do not add a shift column inside a search loop; fit the shift *after* a
  candidate survives.

- **2026-07-29** — created from the indexing plan. gemmi/spglib reduction and
  Bravais availability verified in `.venv` the same day (see Context) — an
  earlier draft of this plan wrongly assumed both had to be written by hand.
