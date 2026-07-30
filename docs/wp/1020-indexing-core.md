# WP-1020 — Indexing core: Q-space, reduced cells, Bravais, FoM panel, ambiguity

Milestone: v1.0 · Status: ⬜ not started
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
  exact `Fraction` arithmetic via `_nullspace_int`. Call it with the
  **transposed** rotations (CLAUDE.md: reciprocal-space symmetry action is Rᵀ).
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
  appears only at the loosest tolerance is `INDEX_BRAVAIS_AMBIGUOUS`, not an
  answer. Same device as `direction="both"` in `sequential.py`.
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

- [ ] `indexing/qspace.py`: Q form, σ(Q) propagation, A..F ↔ cell with
      **analytic** delta-method esds (do not finite-difference — the analytic
      preference everywhere else in this package), symmetry subspaces via
      `adp_basis(Rᵀ)`.
- [ ] `refine_candidate(peaks, assignment, *, system, shift_model)`: weighted
      linear solve `min Σ wᵢ(Qᵢ − Σ M_ip θ_p)²`, `w = 1/σ_eff²`, plus at most
      one nonlinear shift coefficient with an analytic Jacobian column
      `∂Q/∂δ = −(π/180)·sin(2θ)/λ²·t(θ)`; esds from `χ²_red·pinv(MᵀWM)`.
- [ ] `indexing/reduce.py`: Niggli/Delaunay via gemmi with a spglib
      cross-check (an identity test, not a fallback); two-opinion Bravais with
      the tolerance sweep; conventional-cell derivation; the χ² reduced-cell
      equality used for dedup. `INDEX_BRAVAIS_AMBIGUOUS`.
- [ ] `indexing/fom.py`: `m20`, `f20`, `m20_reversed`, `m20_symmetric`,
      `wrip20`, `mcm20`/`lebail_rwp`, `indexed_fraction`,
      **`predicted_seen_fraction`** — each with its citation and blind spot;
      the Borda ranking helper; `fom_panel_disagrees`.
- [ ] `indexing/ambiguity.py`: HNF derivative-lattice enumeration (index 2-4),
      partner test, `discriminating_reflections`.
- [ ] `schemas/indexing.py`: `FigureOfMerit`, `AmbiguityPartner`,
      `CellCandidate`.
- [ ] `docs/manual/indexing.md` — the Q form, the FoM definitions, the σ(Q)
      propagation. Every displayed equation needs a `*Source:*` line whose
      symbol imports, fenced constants need a `conf.py` line **and** a use, and
      every new bib entry must be cited: `tests/test_manual.py` fails the fast
      suite otherwise.
- [ ] `tests/test_indexing_core.py` + `tests/test_indexing_reduce.py`:
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

- **2026-07-29** — created from the indexing plan. gemmi/spglib reduction and
  Bravais availability verified in `.venv` the same day (see Context) — an
  earlier draft of this plan wrongly assumed both had to be written by hand.
