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

### (i) The picker takes a rising left edge for a peak — the envelope repair is decided

Found by eye in WP-1041's gallery review (2026-08-05), in one figure, after
every green test had missed it — and it is a class, not the one-off this repo
had recorded twice. On four of the six bundled round-robin patterns (brucite,
corundum, fluorite, magnetite — all start at 5.00° 2θ) the lowest picked line
sits 0.31 FWHM or less from the first channel, lies on no known lattice, and
**reaches `PeakList.usable()`**: two carry no flag at all, and the other two
carry only `position_at_bound`, which is not in `PEAK_UNUSABLE_FLAGS`. Zincite
and zircon escape only because their first real line is far from the start;
LaB6 because its data begins at 20.3°. It had been recorded as one dataset's
artifact (sized into `REAL_DATA_N_UNINDEXED = 3`) when it is a property of any
pattern whose first channel is on a rising edge.

The cause is one line of `background.background_envelope`: each knot's x is its
window's **centre**, so the first knot sits half a window (~1.5°) inside the
data and `np.interp` **clamps flat** below it. Against a falling background the
clamp sits far under the truth and the whole first 1.5° reads as positive net —
on all seven round-robin patterns `y[0]` is 1.5-2× `env[0]`, z = 4.7-6.9σ on
the first channel against a 5σ bar. A flat-extrapolation artifact, not a
threshold that needs raising.

**The fix is decided and measured (user's call, 2026-08-06: "prefer simple and
robust"). Repair the envelope, then flag what survives — not an edge guard.**

1. Anchor one extra knot at each **data edge**, linearly extrapolated from the
   two nearest — four lines, no new tunable. Measured across the seven: false
   edge lines **5 → 1**, and no line away from the edge is lost on any pattern
   (zincite 50→50, zircon 50→50, cpd-1a 34→34; the rest fall by exactly their
   artifact count). Brucite's survivor drops 6.07σ → 5.01σ. An edge guard was
   rejected for scoring the same on the artifacts and worse on a genuine first
   line, which it cannot tell apart. **Do not crop the pattern** — that
   discards a real low-angle line on a specimen that has one.
2. A line standing where the envelope is **extrapolated rather than
   interpolated** is on a background nobody measured, so it carries a new flag
   saying exactly that — report, don't refuse
   ([1043](1043-agent-and-human-indexing.md)): the component is real intensity,
   and the consumer that can weigh that should be given the chance.
   `position_at_bound` is not the flag to reuse: it caught two of the five and
   means something else.

This is a library behaviour change on the path every external pattern takes and
it moves picker output on four acceptance datasets — run
`tests/test_acceptance_indexing.py` before closing (CLAUDE.md rule; the
`REAL_DATA_N_UNINDEXED` sizing is exactly what moves).

### (j) A symmetry-fixed angle in an external CIF raises where a reader could diagnose

Since WP-1036, `ParameterTable._collect` calls
`crystallography.symmetry.check_cell_angles(sg, angles)`, which **raises** when
a symmetry-fixed angle disagrees with its space group beyond
`SYMMETRY_ANGLE_TOL_DEG = 1e-3`°. The 17 files this repo chose carry zero
disagreements; the realistic external case is a file quoting a *refined*
β = 90.002(3) under an orthorhombic symbol — an experimenter reporting a
measurement, not a mistake — which now raises at the first `parameters()` /
`set_vary` / stage compile rather than refining. Neither half of the fix is
raising the tolerance: 1036 chose 1e-3° by consequence (a fixed angle wrong by
δ biases d-spacings by 8.3 ppm per 1e-3°), and the deviation is real
information about the specimen or the refinement that produced the file. The
useful outcome is a **reader-side `Diagnostic` naming it**:
`structure_from_cif`, beside §(a)'s species normalisation, where a correction
is recorded as provenance instead of applied silently — `ParameterTable` stays
strict (it has no diagnostics channel, which is why 1036 refused rather than
normalised).

### (k) Indexing-side guards and bounds — filed here, not yet scheduled

Three items of this WP's shape (a guard, a bound, a default), measured
2026-07-30 on the certified SRM 660c LaB6 pattern. The *gate/grade* redesign
moved to [1043](1043-agent-and-human-indexing.md); these bounds did not. The
prize is on record: with the off-lattice components removed and the systematic
measured rather than assumed, the gate reached `high` at **−2 ppm**
(M₂₀ = 1120, zero caveats) — what stands between the pipeline and a blind
certified answer is a peak list, not arithmetic.

- **`volume_envelope` is a mean line used as a ceiling.** Checked against
  Smith (1977): average discrepancy 10.6 %, deviations −29 % to +32 %, and low
  is the ordinary case because missing weak lines produce it. With p the
  fraction of possible lines detected the bound stands at 1.4025·p × truth, so
  it **excludes the true cell below p = 0.713** — and 28.7 % is Smith's own
  quoted worst case, so there is no margin at all. `VOLUME_ENVELOPE_SLACK`
  = 1.5 exists but only in `consensus.py` to *flag* an already-found
  candidate; the fatal uses have none — re-verified on arrival 2026-08-07:
  `dichotomy.py:612`, `trial_error.py:297,502` and `svd.py:756` all feed the
  raw envelope as a hard search ceiling. The guard test
  (`test_volume_envelope_contains_the_true_volume`) feeds a complete line list
  (p = 1.0) and is blind to the calibration — a regression test needs an
  *incomplete* one. Docstrings were corrected 2026-07-30; the behaviour fix is
  still owed.
- **`sigma_sys_deg` means two things, and only one of them indexes.**
  `ShiftScreen.sigma_sys_deg` is the residual the winning template *leaves*
  (0.0078° there); `SearchSpec.sigma_sys_deg` must span the uncorrected shift
  itself (+0.037°, 4.3× larger) because the search matches **uncorrected**
  positions — `refine_with_shift` runs only after a candidate survives. So the
  obvious protocol ("measure the systematic on a standard, declare it") finds
  **nothing**, silently. Rename one, or let a declared template *correct* the
  observed positions before matching. Pinned in
  `test_what_the_unflagged_tail_components_cost_the_certified_cell`. (WP-1045
  is about to make `SearchSpec` the one mirrored surface — if it lands first,
  this naming decision belongs there.)
- **`pick.py`'s `not_separable` screen misses six components, for three
  different reasons** — four too far (1.73-2.99 fitted FWHM against
  `PEAK_SATELLITE_NEAR_FWHM` = 1.5), one failing `reseeded()` with the slot
  labels swapped, one on an unrefuted group (χ²_red 1.38, the screen's
  documented deliberate keep) — so no one knob reaches them. What they are is
  settled: five axial-divergence tails (the sign flips at 90° 2θ, which
  nothing else in a Bragg-Brentano pattern does), one a Kα2 alias re-created
  by `fit_group` at 3 % of the parent's area. Cost, measured: **125 ppm on a
  certified cell** (−127 with them in, −2 with them out). The census is pinned
  by `test_the_unflagged_tail_components_escape_for_three_different_reasons` —
  a fix has a table to move, not a threshold to guess at.

Two measured facts to keep beside any diagnostic wording written in this WP:
contamination breaks the **grade**, not the answer (the truth indexes exactly
its own 25 lines at every injected k, so `indexed_fraction` = 25/(25+k) and
the 0.9 bar falls between k = 2 and 3 — a caveat should name the symptom, not
the cause), and `n_unindexed` is an **absolute budget**, not a tolerance
(allowed 3 on a list carrying 12 impurities, the truth comes back **nowhere**:
first-rank 8/8 at k = 6, 0/8 at 18 — a stranger's multi-phase pattern is
exactly this case). And `DEFAULT_UNKNOWN_SHIFT_DEG` = 0.05° is added in
quadrature to every line's σ, flattening a measured 100× precision contrast to
1.005 — if that allowance is revisited, the *shape* (flat quadrature against a
multiplicative widening that preserves the ordering) matters as much as the
size.

### Landing a new code (mechanics from WP-1007/1014)

- `GuardFinding(code, paths, value, message)` lives in `strategy/staged.py`;
  add a guard as a **constructor classmethod** there plus a branch in
  `refine._guard_diagnostics`. `paths` must be populated — `Diagnostic.where`
  is built from it, and this WP's findings (an hkl-range refusal, a
  non-positive ΣS·ZMV) are exactly what a client clicks through to a
  parameter. `str(finding)` is a published surface:
  `tests/test_capabilities.py` pins the rendered strings as literals, so a new
  constructor wants a `RENDERINGS` row. `code` is deliberately an open
  vocabulary, not a `Literal`.
- `MODEL_FAR_FROM_DATA` and the surfaced `max_iter` outcome are the two that
  are not per-parameter — decide `GuardFinding` with empty `paths` against
  `Diagnostic` emitted from `_build_result`, and say which in the handover.
  `value` is `None`-able precisely for the numberless case.
- **The GUI upload route is the front door for files nobody here authored.**
  `imports.preview_pattern` turns reader
  `ValueError/OSError/RuntimeError/KeyError/IndexError` into a 400 quoting the
  parser (staging path scrubbed); anything outside that set is a 500 with a
  type name — the shape of failure worth hunting here. Keep: a filename is
  reduced to its leaf, and the size cap is checked against the declared
  `Content-Length` before a byte is read. `_as_structure` refuses a species
  with no Waasmaier-Kirfel entry, naming the atom — real CIFs carry `D`,
  `Wat`, `OH` and worse, so how often that fires on external files is a
  measurement this WP can make; if it fires on files that ought to work, the
  fix is a species-mapping step at import, not removing the check.
- `PreferredOrientation` is exported from `pxrdref.__init__` and
  `capabilities().features["preferred_orientation"]` derives itself from
  `Phase.model_fields` — §(e)'s remaining work is only the `r` floor.

## Non-goals

- No new *physics*. Every item is a guard, a bound, a default or a message.
- Not `GuardReport` → `GuardFinding` restructuring — **done in WP-1007**
  (2026-07-30); the codes added here land in that vocabulary, see § Landing a
  new code.
- Not the QPA texture bias (see the Inherited note in WP-1004/1007 chain and
  the spherical-harmonics v2 fence) — that is accuracy, not robustness.

## Tasks

- [x] Normalise CIF species at read with a recording `Diagnostic`; cover `O1`
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
- [ ] Envelope edge knots: anchor a knot at each data edge, linearly
      extrapolated from the two nearest; across the round-robin seven, false
      edge lines 5 → 1 with no non-edge line lost (§(i))
- [ ] Flag lines standing on extrapolated envelope span — a new flag, not
      `position_at_bound`; then `tests/test_acceptance_indexing.py`
      (`REAL_DATA_N_UNINDEXED` sizing moves) (§(i))
- [ ] Cell-angle disagreement in an external CIF: reader-side `Diagnostic`
      recording the correction as provenance; `ParameterTable` stays strict
      (§(j))
- [ ] Tests: one regression per item, from the reproductions in the branch

(§(k) is filed, not scheduled: its three bounds stay in Context until a
session picks them up or [1045](1045-indexing-search-controls.md) claims the
`sigma_sys_deg` naming.)

## Acceptance

Every item has a test that fails before the fix. Plus:

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow" -q
.venv/bin/python -m ruff check src tests examples
```

And once §(i) lands (it moves picker output on four acceptance datasets):

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
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
