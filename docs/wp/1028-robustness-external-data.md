# WP-1028 — Robustness on data and CIFs we did not author

Milestone: v1.0 · Status: ✅ 2026-08-07
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

**The audit this asked for came back clean, and the reason is worth keeping
(2026-08-07).** Fourteen softplus parameters declare `min=0.0`
(`Parameter.positive`, roughness `b`/`c`, `air_scatter`, phase `scale`,
`extinction`, the four size/strain widths, `r`). Every one of them except `r`
has **zero as its identity**: extinction 0 ⇒ E ≡ 1, a zero width ⇒ no
broadening, `air_scatter` 0 ⇒ no pedestal, a zero scale ⇒ the phase
contributes nothing. `r` is the only one whose identity is **interior**
(r = 1) with a **singularity at the bound**, because the March factor divides
by it. So the bug is not "softplus with min=0" — it is "softplus with min=0
*and* a pole at zero", and that pattern has exactly one instance. (Extinction's
own 1/x asymptote is already evaluated on a clamped `xsafe`.) The rule that
follows is small enough to state: a softplus `min=0.0` is fine wherever zero
is the off state, and needs a real floor wherever the physics divides.

Two implementation notes. `params.transforms.internal_bounds` maps any lower
bound ≤ 1e-12 to **−∞**, and `log(1+e^u)` underflows to exactly 0.0 below
u ≈ −745 — that pair is the whole mechanism, and a positive bound breaks it
because the internal bound becomes finite. And the broken bound **outlives the
default**: a project or history node written before the fix carries
`min: 0.0` explicitly and would deserialize straight back into the stall, so
`PreferredOrientation` repairs a bound at or below the softplus floor in a
validator, and leaves any positive bound a caller chose alone.

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

**Resolved 2026-08-07, and it was none of those three: the partition was not a
partition.** `y_bragg`, the denominator each reflection's share is taken
against, was built **inside** the per-phase loop, so every phase divided by its
*own* calculated curve and multiplied by the *whole* observed excess — wherever
two phases overlap, the same counts were issued twice. The shares now sum to 1
across all phases at every channel, which is the fixed point Le Bail et al.
(1988) describes; the fix is one pass boundary moved (profiles and the total
first, shares second) and no new tunable.

Measured on a synthetic LaB₆ + CaF₂ pattern, Σ calculated Bragg / Σ observed
excess: **1.79 → 1.0000**, with one phase 1.0000 both before and after — and
the bit-identity goldens pass, so the single-phase path really is untouched.

**Two corrections to what was filed here, both of the "a reported cause is not
a measurement" shape.** The overcount **converges**; it does not "inflate one
another without bound" — the ratio is identical after 1 cycle and after 8
(pinned by `test_the_overcount_is_a_fixed_point_not_a_runaway`). And the Rwp
table above is therefore *downstream* of the partition rather than a direct
reading of it: a fixed 1.79× overcount does not by itself give 742 %, so those
figures are the overcount compounding through the profile stages that follow.
The table is left standing because it is what was observed; only its
attribution is corrected.

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

**Landed 2026-08-07, and the decided numbers reproduced exactly.** Re-measured
across the same seven with `pick_peaks` + `PeakList.usable()`: false edge lines
(a usable line within 1.5° of the first channel) **5 → 1**, **zero** lines lost
away from the edge on any pattern — matching positions within 0.05°, which
matters because the raw position lists differ by sub-tolerance shifts
everywhere and a set comparison reads those as losses. `y[0]/env[0]` falls from
1.62-2.09 to **1.36-1.76** across the seven, so the envelope is closer to the
truth at the edge without being exact — brucite's survivor is what that
remainder looks like. (The absolute usable counts here are 18-68 rather than
the 34-50 quoted above; that figure came from a differently-configured call.
The *invariant* the note asserted — unchanged away from the edge — holds:
zincite 27 → 27, zircon 68 → 68, cpd-1a 36 → 36.)

The flag is `background_extrapolated`, and `background.diagnostics.
envelope_measured_span` is the one authority on where interpolation actually
happens, kept beside the envelope so the two cannot drift. On the seven it
fires on exactly two lines: brucite's 5.179° survivor and one corundum line at
150.088° past the *upper* edge — the right-hand half of the same defect, which
nobody had looked for. Both stay in `usable()`.

Two knock-ons for whoever touches this next. A new `PeakFlag` member is a
failing parity test until `gui/src/lib/pxt.ts` restates it and the committed
dist is rebuilt (`test_textdoc.py::test_the_highlighter_quotes_the_parsers_words`
caught it, which is the meta-test working). And `REAL_DATA_N_UNINDEXED = 3` in
`tests/test_acceptance_indexing.py` is sized on a comment that names the
corundum 5.17° edge artifact as one of its three — that artifact is now gone,
so the comment is stale even where the number still passes.

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

**Landed 2026-08-07, and the one decision this needed was a *size*.** The
reader corrects and records; `ParameterTable` is untouched and still refuses.
But "correct it" cannot be unconditional, because two very different files
reach this code and the reader cannot tell them apart by intent — only by
magnitude:

- A **reported** angle (β = 90.002 under `P m m m`) is an experimenter quoting
  a refined value. The symbol is almost certainly right; snapping to 90° costs
  at most 830 ppm of d-spacing (at the 0.1° edge; linear, and 8.3 ppm at
  1e-3°) and buys a model that refines instead of raising.
- A **structural** disagreement (β = 93.2 under `P m m m`, the case WP-1036
  actually found) is the symbol and the angle contradicting each other. An
  orthorhombic cell *cannot* have β = 93.2, so one of the two is wrong and a
  reader has no basis to pick — snapping it would silently discard a genuinely
  monoclinic cell.

Hence `CIF_ANGLE_CORRECT_MAX_DEG = 0.1`: below it, correct and emit
`CIF_CELL_ANGLE_CORRECTED` (warning, `where` on the angle's path, suggestion
pointing at the space group that leaves it free); above it, leave the value
byte-for-byte and let the existing raise stand. The band's two edges are pinned
by test against `SYMMETRY_ANGLE_TOL_DEG` below and the measured 3.2° case above.

### (k) Indexing-side guards and bounds — handed off, 2026-08-07

Three items of this WP's shape (a guard, a bound, a default), measured
2026-07-30 on the certified SRM 660c LaB6 pattern. They were filed here because
they *are* guards and bounds; they are not landing here because every one of
them belongs to a surface an open indexing WP is about to change, and a bound
fixed under a different WP's redesign is a bound fixed twice. Moved verbatim,
with their measurements, into:

- **[1045](1045-indexing-search-controls.md)** — `sigma_sys_deg` meaning two
  different things (the residual a template *leaves*, 0.0078°, against the
  amplitude a window must *span*, 0.037°; declaring the first finds nothing,
  silently), and `volume_envelope` used as a hard search ceiling when Smith
  (1977) fitted it as a mean line (it excludes the true cell below p = 0.713,
  and the existing `VOLUME_ENVELOPE_SLACK` is applied only where it does not
  matter). Both are `SearchSpec` fields, and 1045 is what makes `SearchSpec`
  one mirrored surface.
- **[1043](1043-agent-and-human-indexing.md)** — `pick.py`'s six unflagged tail
  components, which cost **125 ppm on a certified cell** and are what stands
  between this pipeline and a blind certified answer. 1043 owns the evidence
  view they are evidence in, and the payoff (`high` at −2 ppm, zero caveats —
  the first `high` on real data) is its subject rather than this WP's.

The gate/grade redesign those bounds were filed beside had already moved to
1043.

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
  are not per-parameter — **decided 2026-08-07: `Diagnostic` emitted from
  `_build_result`, not `GuardFinding` with empty `paths`.** `GuardFinding`
  exists to carry paths a client can click through to a parameter; a finding
  with none is the wrong shape for it, and both of these are statements about
  the *run*. Same for `QPA_UNAVAILABLE` — though that one *does* name paths
  (the dead scales), it is emitted where the QPA is computed rather than from
  `check_guards`, which never sees it. So five codes landed here without a
  `RENDERINGS` row, correctly: nothing added a `GuardFinding` constructor.
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
- [x] hkl-range guard in `generate_reflections` + diagnostic naming the cell
- [x] `MODEL_FAR_FROM_DATA` diagnostic; surface `max_iter` stage outcomes
- [x] Floor `PreferredOrientation.r` (and audit other softplus `min=0.0`
      parameters for the same reachable-zero bug)
- [x] `compute_qpa`: skip below two phases, diagnose instead of raising
- [x] Le Bail multiphase: ~~damp, refuse, or fence~~ — the partition
      denominator now spans every phase, which is what makes it a
      partition; 1.79 → 1.0000 on two phases, 1.0000 unchanged on one
- [x] AGENT_PROTOCOL: Le Bail fixed-point loop + the width/background seeding
      precondition — both were already written; what this session owed was
      *correcting* the block, since §(g)'s fix made "do not use it above one
      phase" false, and measuring the seeding claim (571× on cycle one)
- [x] Envelope edge knots: anchor a knot at each data edge, linearly
      extrapolated from the two nearest; across the round-robin seven, false
      edge lines 5 → 1 with no non-edge line lost (§(i))
- [x] Flag lines standing on extrapolated envelope span — a new flag, not
      `position_at_bound`; then `tests/test_acceptance_indexing.py`
      (`REAL_DATA_N_UNINDEXED` sizing moves) (§(i))
- [x] Cell-angle disagreement in an external CIF: reader-side `Diagnostic`
      recording the correction as provenance; `ParameterTable` stays strict
      (§(j))
- [x] Tests: one regression per item — `tests/test_robustness_external.py`,
      32 rows, one section per item, every one failing before its fix

(§(k) was handed to [1045](1045-indexing-search-controls.md) and
[1043](1043-agent-and-human-indexing.md) rather than landing here — the
grounds are in that section.)

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

- **2026-08-07** — **all ten items (a)-(j) landed; §(k) stays filed, not
  scheduled.** Branch `wp1028-robustness-external-data`, ten commits, one per
  item plus the arrival prune.

  **Done.** (a) `normalize_cif_species` rewrites the sign-first charge and the
  site-label type symbol onto the canonical grammar, only when the result
  resolves in the Waasmaier-Kirfel table, recording `CIF_SPECIES_NORMALISED`;
  both lookups stay strict. (b) `MAX_HKL_GRID_POINTS = 3e7` refuses a collapsed
  cell before `np.meshgrid`. (c)/(d) `MODEL_FAR_FROM_DATA` and `STAGE_MAX_ITER`
  as `Diagnostic`s from `_build_result`. (e) `MARCH_R_MIN/MAX = 0.15/6`, with a
  validator that repairs a stored `min: 0.0`. (f) `compute_qpa` returns `None`
  and the caller emits `QPA_UNAVAILABLE`; single-phase is 100 % by definition
  and never reaches that path. (g) the Le Bail partition denominator spans every
  phase. (h) the AGENT_PROTOCOL Le Bail block corrected and measured. (i)
  envelope edge knots + the `background_extrapolated` flag. (j)
  `CIF_CELL_ANGLE_CORRECTED` up to `CIF_ANGLE_CORRECT_MAX_DEG = 0.1`.

  **Numbers, `[dev,jax,torch,docs]` venv on darwin/arm64** (jax, torch and
  sphinx all import here, so no module-level `importorskip` fires and collected
  == passed+skipped): fast selection **1924 passed, 5 skipped in 3:56**, against
  main's 1897 collected — +32, exactly this session's new module
  `tests/test_robustness_external.py`, all passes and no new skip. Ruff clean.
  GUI: 390 vitest, svelte-check 0 errors, dist rebuilt.

  **Three things a reader should not take on trust from the WP text above, all
  re-measured here.** §(g)'s filed cause was wrong in shape — the multiphase
  overcount **converges** to a fixed 1.79× rather than inflating without bound,
  so the 742-3334 % Rwp table is downstream of the partition, not a reading of
  it. §(e)'s "audit other softplus `min=0.0` parameters" came back with exactly
  one instance, and the reason generalises better than a list: the bug is
  "softplus `min=0` **and a pole at zero**", and `r` is the only parameter whose
  identity is interior. §(i)'s decided numbers reproduced exactly (5 → 1 edge
  lines, 0 lost away from the edge) **but only when positions are matched within
  0.05°** — a set comparison of raw positions reads sub-tolerance shifts as
  losses and says three patterns lost lines.

  **Gotchas for the next session.** A new `PeakFlag` is a failing parity test
  until `gui/src/lib/pxt.ts` restates it *and* the committed dist is rebuilt
  (`npm --prefix gui ci` first — the workspace ships without `node_modules`).
  `REAL_DATA_N_UNINDEXED = 3` in `tests/test_acceptance_indexing.py` is
  justified by a comment naming corundum's 5.17° edge artifact as one of its
  three; §(i) removed that artifact, so the comment is stale even where the
  number still passes — the sweep behind it (2 fails, 3 works, 5-6 lose the
  cell) was run with the artifact present and would want redoing before anyone
  leans on it. And `MODEL_FAR_FROM_DATA_RWP` is 0.8 rather than the obvious 1.0
  because Rwp = 1 is not the ceiling of the broken cases but their **attractor**:
  a windowed-out model's only escape is driving the scale to zero, which
  *converges* at 0.99999.

  **Next**: §(k)'s three indexing bounds are the only unscheduled work left here
  (`volume_envelope` used as a ceiling when it is a mean line, `sigma_sys_deg`
  meaning two things, `pick.py`'s six escapees) — and the `sigma_sys_deg` naming
  belongs in [1045](1045-indexing-search-controls.md) if that lands first.

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
