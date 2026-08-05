# WP-1028 — Robustness on data and CIFs we did not author

Milestone: v1.0 · Status: ⬜
Depends on: — (1007 soft: it restructures guard *reporting*, this adds guards)

<!--
Every item here was hit by driving the package end-to-end over nine unfamiliar
refinement targets from a third-party paper (branch `wpem-benchmark`, not
merged; see "Provenance" at the bottom). Nothing in this WP was found by
reading the code.
-->

## Goal

`pxrdref` survives a stranger's CIF and a stranger's pattern: it either
refines, or it fails with a diagnostic that names the cause. No crash on a
2.35 PiB allocation, no `status="converged"` at Rwp = 7 225 %, no silent
fifteen-minute stall, no `KeyError` on a species string that half the world's
CIFs use.

## Context

Measured on lab Cu Kα and synchrotron data from
<https://github.com/Bin-Cao/PyWPEM/tree/main/CASES> plus eleven structures
pulled from COD. Reproductions are in the branch's `studies/wpem_bench/`; the
branch is *not* merged, so restate anything needed rather than linking code.

### (a) Two species syntaxes reject valid CIFs — at two lookups, not one

**Two** functions read `Atom.species` and both carry the *same* regex
`^([A-Za-z]{1,2})(\d*[+-])?$`: `crystallography/dispersion.py::normalize_element`
(f′/f″) and `crystallography/scattering.py::normalize_species` (f₀, which
differs only in trying a tabulated ion before falling back to the element).
Two forms in the wild fail both:

| form | example | where |
|---|---|---|
| site label in the type-symbol column | `O1`, `O2`, `Cl1` | 6 of 11 COD entries used; AMCSD-derived ones especially |
| charge written **sign-first** | `O-2`, `Ni+3`, `Li+1` | ICSD exports; `CASES/Insitu XRD/LiNiO2.cif` |

`Structure.from_cif` passes the value through and `compile_model` then raises
`KeyError: cannot read an element symbol from species 'O1'`. Only the
*sign-first* and *site-label* forms fail; the trailing-sign `Cl1-` reads fine.

**Withdrawn 2026-07-30: this is not a reach regression from WP-1001.** The
original entry claimed these files loaded fine while `Source.dispersion`
defaulted to `None`. They did not. `compile_phase_sites`
(`structure_factor.py:149`) has called `normalize_species` unconditionally
since v0.1, and `compile_model` calls `resolve_dispersion` one line *above* it
(`forward.py:1134`) — so making dispersion the default moved the raise up a
line and changed the message, arguably for the worse, since "no
Waasmaier-Kirfel coefficients" at least names a table. Measured by compiling a
two-atom NaCl model with the second species relabelled:

```text
dispersion=off species='Cl1':  KeyError: no Waasmaier-Kirfel coefficients for species 'Cl1'
dispersion=off species='Cl-1': KeyError: no Waasmaier-Kirfel coefficients for species 'Cl-1'
dispersion=ON  species='Cl1':  KeyError: cannot read an element symbol from species 'Cl1'
dispersion=ON  species='Cl-1': KeyError: cannot read an element symbol from species 'Cl-1'
```

Three consequences for the fix: `dispersion=None` is **not** a workaround to
offer anyone, there is no ≤ v0.6 behaviour to reproduce bit-identically here,
and a normalisation reaching only `normalize_element` fixes nothing. Two
aggravations stand: the failure lands at the first `fit()` rather than at
`from_cif`, and the message names a species rather than a file or a site.

Fix direction unchanged, and now load-bearing for *both* consumers: normalise
at CIF read (`crystallography/cif.py`), recording what changed as a
`Diagnostic` so the substitution is visible rather than silent, and keep
`normalize_element` strict for hand-built structures. Note
ions must still resolve to the element for f′/f″ (core-level effect) while
`scattering.normalize_species` keeps the ion for f₀ — that asymmetry is
deliberate (CLAUDE.md) and must survive.

### (b) `generate_reflections` has no range guard — 2.35 PiB

`crystallography/symmetry.py:154` builds `np.meshgrid(rng_h, rng_k, rng_l)`.
With a collapsed cell the ranges reach 63747 × 63747 × 81527 and numpy raises
`_ArrayMemoryError: Unable to allocate 2.35 PiB`. Crash-class: the process
dies. Bound the hkl count (or d_min-implied range) and raise a diagnostic
naming the cell that produced it, before allocating.

### (c) No divergence guard — `status="converged"` at Rwp = 7 225 %

A starting cell 3 % off puts every reflection outside its frozen evaluation
window. The refinement does not error: it returns `status="converged"` with
`zero_shift` and all five profile terms pinned to bounds, at Rwp = 7 225 %
(Le Bail on Ti-15Nb from the source paper's own starting cells) and
2.6 × 10⁵ % for a three-phase Le Bail. AGENT_PROTOCOL §1 states the ≈1 %
precondition and `report/layer2.py` has emitted `reindex_or_recheck_cell`
since v0.2 — but at that Rwp nobody builds a report, and a batch caller sees
"converged". Add a `MODEL_FAR_FROM_DATA` diagnostic (Rwp above an
obviously-broken threshold after a stage) naming window coverage as the likely
cause.

### (d) A stage that cannot converge burns 15 minutes and reports success

`optimize/least_squares.py` passes `max_nfev = max_iter × n_par` to TRF with
`Stage.max_iter = 100`, so at 46 free parameters one stage may spend **4 600**
residual-plus-Jacobian evaluations. Measured on three NaCl/Li₂CO₃ mixtures —
identical models, identical parameter counts, same-sized patterns — wall clock
ran **39 s, 858 s and 2 838 s**, a 73× spread with no corresponding difference
in the answer. The stages that stall are the degenerate groups
AGENT_PROTOCOL §3 already enumerates, so they are predictable *before* the
solve. Surface `outcome.status == "max_iter"` as a diagnostic rather than
folding it into the stage result, and consider a lower default cap.

### (e) March-Dollase feeds inf/NaN to the solver when `r` underflows

`PreferredOrientation.r` is `min=0.0, transform="softplus"`, meant to keep it
strictly positive. It does not: the softplus pre-image runs to −∞, `r` reaches
exactly 0, and `model/preferred_orientation.py:92-93` evaluates `(1 − c)/r`,
emitting `RuntimeWarning: divide by zero` and returning inf/NaN. Nothing
raises — the residual becomes garbage and TRF grinds its whole budget. On the
90 wt % NaCl mixture that turned a 3-second stage into one that had not
returned after **ten minutes**. Bounding `r` to 0.15–6 fixed the stall *and*
the fit (Rwp 30.8 % → 13.2 %). r = 1 is the identity and a March coefficient
outside that range describes a texture no powder mount produces, so a default
floor costs nothing.

### (f) `compute_qpa` raises where it should diagnose

`optimize/qpa.py:189` raises `ValueError: phase scales give a non-positive
scaled total (Σ S·ZMV = 0.0)` from inside `_build_result`. In a
`refine_sequential` run one pattern whose scale hit zero destroyed **all 157
refinements** — and for a single-phase model the answer is 100 % by
definition, so the computation should not have been on the critical path at
all. Skip QPA below two phases; degrade to a diagnostic otherwise.

### (g) Le Bail is unstable on multiphase patterns

`CompiledModel.lebail_update` partitions `max(y_obs − y_bkg, 0)` **per phase**
with no mechanism to arbitrate two phases claiming the same channel, so they
inflate one another without bound. The failure tracks phase count exactly:

| phases | case | Le Bail Rwp |
|---|---|---|
| 1 | PbSO₄ | 7.48 % (converges) |
| 1 | Tb₂BaCoO₅ | 17.3–24.8 % (converges) |
| 2 | NaCl/Li₂CO₃ | 742–3 334 % |
| 2 | (Mn,Ru)₂O₃ + RuO₂ | 1 769–9 281 % |
| 3 | Ti-15Nb | 2.6 × 10⁵ % |

It survives seeding both the profile widths and the background, so it is the
partition and not the starting point. Either damp the per-phase update, refuse
`mode="lebail"` above one phase with a clear error, or document the fence.
Rietveld ties intensities to atoms and has no such freedom.

### (h) Two caller-protocol requirements nothing states

- **A Le Bail refinement needs an outer fixed-point loop.** One
  `fit(mode="lebail")` walks the staged plan once, but extracted intensities
  are frozen inside each least-squares run (the frozen-per-stage invariant), so
  intensities and profile converge only by alternating. PbSO₄ pass 1 stops at
  Rwp 20.756 % with an unphysical **V = +0.0615**; passes 2–4 reach 10.247 %
  with the Caglioti curve sane. The loop is **not monotone** — a later pass can
  be worse — so whatever iterates must keep the best node.
- **`ProfileTCHZ`'s `W = 1e-3` default is a synchrotron line** (FWHM ≈ 0.03°).
  On lab data with 0.15–0.40° peaks the frozen windows are an order of
  magnitude narrower than the lines. `auto_background` compounds it: it picks
  the order but starts every coefficient at **0.0**, and `lebail_update` runs
  before the background is ever fitted, so on a pattern whose background is 5×
  its strongest peak the whole pedestal goes to the Bragg reflections on cycle
  one.

### Inherited

**From [1041](1041-indexing-benchmark-gallery.md) closing, 2026-08-05 — indexing
robustness under contamination is now measured, so do not re-derive it, and one
result changes what "survives a stranger's pattern" means for the gate.**

A sweep injecting k impurity lines into the certified LaB6 list is
`test_impurity_lines_cost_the_certificate_its_grade_long_before_its_rank`. Two
things transfer to this WP:

- **What contamination breaks is the *grade*, not the answer, and by arithmetic.**
  The truth indexes exactly its own 25 lines at every k and never an injected one,
  so `indexed_fraction` = 25/(25+k) and the 0.9 bar falls between k = 2 and k = 3.
  A stranger's pattern with a few extra lines therefore drops to `low` on
  `indexed_fraction_low` while the cell is still right and still first. That is
  worth a diagnostic-wording check when you write yours: the caveat names the
  symptom, not the cause.
- **The real limit is `n_unindexed`, and it is an absolute budget.** Told it may
  leave 3 lines unindexed on a list carrying 12 impurities, the search returns the
  truth **nowhere** rather than second — first-rank rate 8/8 at k = 6, 5/8 at 9,
  2/8 at 12, 0/8 at 18. A stranger's multi-phase pattern is exactly this case, and
  the fix is not a tolerance.

Also relevant to "no silent stall": the whole indexing acceptance suite is 41 rows
and 22-26 min, and its budgets are runaway guards with ≥8× headroom measured, not
timers.

**From [1041](1041-indexing-benchmark-gallery.md), 2026-08-05 — your §"the payoff"
paragraph is half withdrawn, and the σ_sys item you were filed is unchanged.**
`best_or_none()` no longer returns a cell on the calibrated LaB6 protocol: it did
so only while `trial_error`'s dedup key was scale-invariant and could return one
cubic candidate per search, which denied the a·√2 supercell its vote. With
`engines.solution_key` fixed, all three engines find the truth *and* both centrings
of that supercell, and all three reach `high`. The certified cell's own `high` and
its −2 ppm are untouched — only the uniqueness is gone, and it was a bug's doing.
The paragraph in Context is corrected in place; nothing else in this WP moves. The
`sigma_sys_deg` naming item you own (the residual the template *leaves*, 0.0078°,
against the amplitude a window must span, 0.037°) is untouched and still filed here.

**From [1036](1036-crystal-system-settings.md), closed 2026-08-04 — a new
refusal on the path every external CIF takes, and 1036 established that a plain
CIF can trip it.**

`ParameterTable._collect` now calls
`crystallography.symmetry.check_cell_angles(sg, angles)`, which **raises** when
a symmetry-fixed angle disagrees with the value its space group demands, beyond
`SYMMETRY_ANGLE_TOL_DEG = 1e-3`°. 1036 swept the 3 CIFs this repo ships plus the
14 COD entries this benchmark pulls and found **zero** disagreements, so nothing
here breaks today — but that is 17 files *we* chose, and this WP's whole subject
is files we did not. The reader does not enforce consistency: a CIF declaring
`P m m m` with `_cell_angle_beta 93.2` loads and stores 93.2 verbatim, which is
how 1036 established all three defects are reachable from a plain CIF.

The realistic external case is not that malformed one. It is a file quoting a
*refined* β = 90.002(3) under an orthorhombic symbol — an experimenter
reporting a measurement, not a mistake — which exceeds 1e-3° and will now raise
at the first `parameters()` / `set_vary` / stage compile rather than refine.

Two things to weigh, and **neither is raising the tolerance**: 1036 chose 1e-3°
by consequence, not by comfort (a fixed angle wrong by δ biases d-spacings by
8.3 ppm per 1e-3°), so widening it re-admits the bias it exists to stop. And
the deviation is real information about the specimen or the refinement that
produced the file, so the useful outcome here is a **diagnostic naming it**
rather than a bare raise. Note where that has to live: 1036 refused rather than
normalised precisely because `ParameterTable` has no diagnostics channel — a
*reader* does, so if a real external corpus turns up files in this state the fix
belongs in `structure_from_cif`, alongside item (a)'s species normalisation,
where a correction can be recorded as provenance instead of applied silently.

**From the 2026-07-30 assessment session — a bound that can exclude the right
answer, which is this WP's shape exactly ("a guard, a bound, a default").**
`indexing.quality.volume_envelope` is documented and used as an **upper envelope**
on the cell volume and is fed straight into the engines as a hard search ceiling
(`dichotomy.py:487`, `trial_error.py:274,455`). Checked against Smith (1977): it
is a least-squares **mean line**, average discrepancy 10.6 %, deviations −29 % to
+32 %, and the low side is the ordinary case because it is what missing weak
lines produce. With p the fraction of possible lines detected the bound stands in
ratio 1.4025·p to the truth, so it **excludes the true cell below p = 0.713** —
and 28.7 % is Smith's own quoted worst case, so there is no margin at all against
the worst pattern in his calibration set.

Three things to know before fixing it. `VOLUME_ENVELOPE_SLACK = 1.5` already
exists but is applied only in `consensus.py:302` to *flag* an already-found
candidate — the fatal use has no slack, which is inverted. The test that guards
it (`test_volume_envelope_contains_the_true_volume`) feeds `generate_reflections`,
a complete line list at p = 1.0, so it validates the geometry in the most
favourable regime and is blind to the calibration; a regression here needs an
*incomplete* line list. And the docstrings and manual were corrected on
2026-07-30 to say "estimate" with the numbers, so the false claim is gone but the
**behaviour is unchanged** — the fix is still owed. Search-scope aspects are in
[1030](1030-engine-scaling-low-symmetry.md); the guard-and-default aspect is
yours if 1030 does not reach it first.

**From WP-1026 (2026-07-30, third session) — a refuting caveat that fires on
correct cells, which is a robustness statement rather than an indexing one.**
`predicted_but_absent` is one of the five `INDEX_REFUTING_CAVEATS`, and it is
counted against the candidate's **lattice** group, because that is the only model
that exists before `determine_extinction_symbol` runs. So every phase whose space
group has extinctions beyond its centring refutes its own correct cell. Measured
end to end on the certified SRM 676a corundum pattern: the cell is recovered to
+101 ppm in a and +16 ppm in c, ranked first with the right centring, and carries
`predicted_but_absent = 12` — the R-3c c-glide, seen through the lattice R-3m.
The candidate is graded `low` and `best_or_none()` returns None.

Three things before touching it. It is exactly the blind spot
`fom.predicted_seen_fraction`'s docstring already states ("legitimately absent
reflections count against a *correct* cell"), promoted to a caveat that refutes —
so the fix is not new knowledge, it is making the gate act on knowledge the panel
already carries. The screen that *can* separate the two cases exists
(`indexing/extinction.py`, WP-1025) and costs ~2 s plus ~0.1 s per class, but
`index_pattern` does not run it, so this is an integration decision with a price,
not a new measurement. And the honest interim behaviour is arguably what happens
now — abstaining on a cell the package cannot yet distinguish from an oversized
one — so if you leave it, say so in the caveat's own text rather than in a
handover log.

**That caveat now has its control, and it means what its name says (WP-1026,
2026-07-30, fourth session).** NIST SRM 660c LaB6 is **P m -3 m**, which
extinguishes nothing, and indexed end to end it carries `predicted_but_absent`
**0 of 30** with `predicted_seen_fraction` **1.000**, against corundum's 11-12
and 0.86. So the entry above is confirmed rather than merely argued: the caveat
tracks space-group absences seen through the lattice group, and reading a firing
as "this cell is too big" is the mistake. `test_a_certified_cubic_cell_is_
recovered_with_no_extinction_caveat` is that control and will fail if a fix
changes the meaning rather than the coverage.

**Three more from the same session, all measured on that pattern, all of the
shape this WP owns — a guard, a bound, a default.**

- **`indexing/pick.py`'s `not_separable` screen misses six components, and no one
  knob reaches them.** Thirteen weak components share a group with a strong one
  here; seven are flagged and six survive, failing **three different** conditions:
  four are simply *too far* (1.73-2.99 fitted FWHM, against
  `PEAK_SATELLITE_NEAR_FWHM` = 1.5); one fails `reseeded()` because the detection
  seed slid into the tail and the *new* component took the real line, so the slot
  labels are the wrong way round; and one sits on a group whose fit is **not
  refuted** (χ²_red 1.38), which the screen's own docstring calls a deliberate
  keep. Widening 1.5 would reach four of six and is a knob, not a measurement.
  What the survivors *are* is settled: five are axial-divergence tails — the sign
  flips at 90° 2θ, which nothing else in a Bragg-Brentano pattern does — and one
  is a Kα2 residual on a mate's resolved second line, i.e. an alias
  `detect_peaks` dropped (`PEAK_KALPHA2_ALIAS`, 23 dropped here) that `fit_group`
  re-created at 3 % of the parent's area. Cost, measured: **125 ppm on a
  certified cell** (−127 with them in, −2 with them out) and a shift fit
  consistent with zero where the truth is +0.037°. The census is pinned by
  `test_the_unflagged_tail_components_escape_for_three_different_reasons`, so a
  fix has a table to move rather than a threshold to guess at.
- **An assumed allowance destroys the weighting the peak fitter measured, and
  that is a second cost nobody had priced.** `DEFAULT_UNKNOWN_SHIFT_DEG` = 0.05°
  is added *in quadrature to every line's σ*, so on this pattern the real lines
  (σ ≈ 0.0005°) and the tail components (σ ≈ 0.005°) go from a **100×** precision
  contrast to **1.005**. That is why `fit_shift_model`, which weights by each
  line's own σ, recovers the displacement anyway (+0.0367 ± 0.0015° against a
  parameter-free geometric prediction of +0.0415°) while the *search*, on the
  identical list, fits +0.009 ± 0.016°. If the allowance is ever revisited, the
  question is not only whether 0.05° is the right size but whether a flat
  quadrature addition is the right *shape* — a multiplicative widening would
  preserve the ordering.
- **`sigma_sys_deg` means two different things to the screen and to the search,
  and only one of them indexes.** `ShiftScreen.sigma_sys_deg` is the scatter the
  winning template *leaves* (0.0078° here). Declare that as `SearchSpec.
  sigma_sys_deg` and the search returns **no candidate at all**, because it
  matches against **uncorrected** positions — `refine_with_shift` fits the
  template only after a candidate survives — so the window still has to span the
  shift itself (+0.037°). The two differ by 4.3×, the docstrings do not
  distinguish them, and the obvious protocol ("measure the systematic on a
  standard, declare it") therefore fails silently by finding nothing. Either
  rename one, or let a declared template *correct* the observed positions before
  matching. Pinned in `test_what_the_unflagged_tail_components_cost_the_
  certified_cell`.

**And the payoff, so the size of the prize is on record: with those three
handled the gate reaches `high`.** Same pattern, off-lattice components removed
and the systematic measured rather than assumed: **a = 4.156772 Å, −2 ppm** from
the certification CIF, M₂₀ = 1120, **zero caveats** on that candidate — the first
time `high` has been reached on real data. The pipeline's arithmetic is sound to
the part per million; what stands between it and a *blind* certified answer is a
peak list.

**The half of that sentence about `best_or_none()` is withdrawn (WP-1041,
2026-08-05).** It returned a cell only because a dedup bug was suppressing two
rivals: all three engines also find both centrings of the a·√2 supercell, and with
`engines.solution_key` fixed those reach `high` too, so the "exactly one high
candidate" rule declines. The certified cell's own `high` is untouched; what the
row now shows is that the *gate* never separated the truth from its supercell —
`caveats_for` reads `predicted_but_absent` (0 for all three here) and never
`unmatched_observed` (17 against 91 and 136). Fixing that is WP-1041's, not this
WP's; it is noted here only so this paragraph is not read as still true.

**A geometrical ambiguity the enumeration cannot reach from one side (WP-1026,
same session).** `ambiguity.ambiguity_partners` enumerates **derivative**
lattices — sublattices of index 2-4, i.e. supercells — so a rival with *smaller*
volume is not in the enumeration at all. One exists for the commonest lattice
there is: tetragonal P at (a/√2, a) gives Q = (2h² + 2k² + l²)/a², and
2(h²+k²)+l² represents **exactly** the integers h²+k²+l² does (both miss
precisely 4ⁿ(8m+7)), so it is isospectral with cubic P *everywhere* — not within
a tolerance. Measured: 0 partners reported from the cubic side, while from the
tetragonal side the cubic **is** found (index 2, **zero** discriminating
reflections, the report correctly saying nothing in range separates them). Both
engines find the rival on the real pattern. Why it matters here rather than only
being untidy: the gate refuses `high` to a candidate with an ambiguity partner,
so whichever of an isospectral pair happens to be the larger cell can be
promoted while its equal cannot — a confident singleton produced by the
enumeration's direction rather than by the data. Two rows pin it
(`test_positions_alone_cannot_separate_lab6_from_a_half_volume_rival` asserts the
0 partners *and* says in place that the fix is to delete that assertion).

From **WP-1014** (import & in-GUI editing, landed 2026-07-30): **the upload route
is now the front door for files nobody here authored**, which makes it this WP's
most interesting surface. `imports.preview_pattern` catches
`ValueError/OSError/RuntimeError/KeyError/IndexError` from the reader and turns
them into a 400 quoting the parser (with the staging path scrubbed out); anything
outside that set becomes a 500 with a type name, which is the shape of failure
worth hunting here. Two known-good behaviours to keep: a filename is reduced to its
leaf (`../../../etc/lab6.cif` stages as `lab6.cif`), and the size cap is checked
against the *declared* `Content-Length` before a byte is read.

Also relevant: `_as_structure` now refuses an atom species with no
Waasmaier-Kirfel entry, naming the atom. Real CIFs carry `D`, `Wat`, `OH` and
worse, so **how often that fires on external files is a measurement this WP can
make** — and if it fires on files that ought to work, the fix is a species-mapping
step at import, not removing the check (it only moves the failure from stage
compile to the field it was typed in).

From **WP-1007** (landed 2026-07-30) — **`GuardFinding` now exists, so the codes
this WP adds have a home**, and the note that asked for an open vocabulary was
honoured: `GuardFinding(code, paths, value, message)` in `strategy/staged.py`,
`code` a plain `str` and not a `Literal` closed over the original six. Three
practical consequences:

- Add a guard by adding a **constructor classmethod** to `GuardFinding` (that is
  where the format string belongs — the same text used to be written at three
  call sites) and a branch in `refine._guard_diagnostics`. `paths` is a tuple and
  it *must* be populated: `Diagnostic.where` is now built from it, and this WP's
  own findings (an hkl-range refusal, a non-positive ΣS·ZMV) are exactly the kind
  a client wants to click through to a parameter.
- **`str(finding)` is a published surface.** `tests/test_capabilities.py` pins the
  rendered strings as *literals*; a new constructor wants a row in its
  `RENDERINGS` table.
- `MODEL_FAR_FROM_DATA` and the surfaced `max_iter` outcome are the two that are
  not per-parameter — decide whether they are `GuardFinding`s with an empty
  `paths` or `Diagnostic`s emitted directly from `_build_result`, and say which in
  the handover. `value` is `None`-able precisely for the numberless case (a
  parameter at its bound uses it that way).

Also from **WP-1007**: `PreferredOrientation` is now exported from
`pxrdref.__init__` — that half of this WP's note is done, so its task list is
only the `r` floor. And `capabilities().features` carries `preferred_orientation`
derived from `Phase.model_fields`, so nothing there needs editing when you touch
the block.

## Non-goals

- No new *physics*. Every item is a guard, a bound, a default or a message.
- Not `GuardReport` → `GuardFinding` restructuring — **done in WP-1007**
  (2026-07-30); the codes added here land in that vocabulary, see `### Inherited`.
- Not the QPA texture bias (see the Inherited note in WP-1004/1007 chain and
  the spherical-harmonics v2 fence) — that is accuracy, not robustness.

## Tasks

- [ ] Normalise CIF species at read with a recording `Diagnostic`; cover `O1`
      and `O-2` forms; keep `normalize_element` strict elsewhere. Assert the
      fix with `dispersion` both on *and* `None`, since both lookups reject
      these forms (§(a))
- [ ] hkl-range guard in `generate_reflections` + diagnostic naming the cell
- [ ] `MODEL_FAR_FROM_DATA` diagnostic; surface `max_iter` stage outcomes
- [ ] Floor `PreferredOrientation.r` (and audit other softplus `min=0.0`
      parameters for the same reachable-zero bug)
- [ ] `compute_qpa`: skip below two phases, diagnose instead of raising
- [ ] Le Bail multiphase: damp, refuse, or fence — decide and record
- [ ] AGENT_PROTOCOL: Le Bail fixed-point loop + the width/background seeding
      precondition (may land first, independently — it is documentation)
- [ ] Tests: one regression per item, from the reproductions in the branch

## Acceptance

Every item has a test that fails before the fix. Plus:

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow" -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Cao et al., *AI-Driven Structure Refinement of X-ray Diffraction*,
  arXiv:2602.16372 — the datasets these were found on.
- Crystallography Open Database — the eleven structures; ids recorded in the
  branch's `studies/wpem_bench/fetch_cifs.py`.

## Provenance

Found on branch **`wpem-benchmark`** (pushed, deliberately not merged), which
benchmarks this package against WPEM on that paper's data. The branch carries
the reproductions, a published report, and the benchmark's own findings; only
the library defects are promoted here. Nothing in the branch is a dependency —
this WP is self-contained.

## Handover log

- **2026-07-30** — §(a)'s *attribution* withdrawn (still ⬜; no code touched).
  The defect is real and unchanged; blaming WP-1001 was not. Gotcha for
  whoever implements it: `Atom.species` has two consumers with the same regex,
  and only one of them is new. Lesson worth generalising — the benchmark
  measured the *failure* but reasoned the *cause*, and reasoning stopped at
  the first raise it saw. Next: nothing new; the task list stands.
- **2026-07-29** — created from the `wpem-benchmark` benchmark run. Nine
  refinement targets attempted, eight refined, one ((Mn,Ru)₂O₃) killed by (b).
  Items (a)–(h) are all measured, not inferred; every number above came from a
  run, and the branch has the logs.
