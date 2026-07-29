# WP-1001 — Validation matrix + tolerance policy

Milestone: v1.0 · Status: 🔶 in progress
Depends on: —

## Goal

Every acceptance assertion in the repo is registered in one machine-readable
**validation matrix** that names what its tolerance is referenced to, the
matrix cannot silently drift from the suites (a new acceptance test without a
row fails the fast suite), `docs/VALIDATION.md` is generated from it, and the
one default the v1.0 API freeze would lock in the wrong position —
`Source.dispersion` — is decided on measurement rather than on inertia.

## Context

Nine real-data acceptance suites exist (`tests/test_acceptance_*.py`:
`capillary`, `dispersion`, `fap`, `nac`, `qpa_roundrobin`, `sequential`,
`srm660c`, `srm676a`, `stephens`) plus the reference-free
`tests/test_cross_backend.py`. Their tolerances were each chosen well and
argued for in a docstring, but the *set* of them has never been looked at as
one object, and nothing stops the next suite from inventing an eighth kind of
reference or quietly loosening a bar.

The policy prose lives in
[../DESIGN.md](../DESIGN.md#testing--validation-policy) (NIST certificates as
absolute anchors; GSAS-II as convention-aware consistency; "a disagreement's
*shape* is evidence"). `README.md` §Validation has a hand-maintained table
that already says "eight" when there are nine suites — which is exactly the
drift this WP exists to make impossible.

**The anti-drift design to copy is WP-0604's.** The theory manual is guarded by
`tests/test_manual.py`: fenced constants injected from the live package, every
equation's `*Source:*` symbol must import, every bib entry must be cited. The
same shape applies here — the matrix is data, the doc is generated, and the
guards run in the **fast** suite so the cost is paid per-push and not nightly.

### The scope's three tiers do not survive contact with the suites

The pre-split roadmap asked for "exact / tight-scientific / statistical".
Surveying every numeric assertion in the nine suites finds **seven** distinct
things a bar can be referenced to, and two of them are not tolerance tiers at
all — they are kinds of evidence, and they are the strongest evidence the repo
has:

| Tier | Referenced to | Example |
|---|---|---|
| `identity` | floating-point arithmetic | capillary `abs(Δa) < 1e-9` Å between two of our own fits; FAP `b == a rel=1e-12`; QPA closure `abs=1e-6` |
| `certificate` | a certified value **with** its stated uncertainty | SRM 676a c/a within 1e-4 (cert k=2 is ~21 ppm); SRM 660c `abs(Δa) < 2e-4` Å, explicitly *interim* |
| `cross_code` | another code's converged result, its protocol adopted | FAP Rwp `rel=0.10` vs GSAS 0.1005 on a matching 5750 channels |
| `spread` | a published inter-laboratory spread, never σ | QPA `MAJOR_TOL = 6.0` / `TRACE_TOL = 2.0` wt % |
| `own_result` | this package's other result under a fixed protocol | sequential chained vs independent, `abs=1.0` wt %; NAC Rietveld vs Le Bail `< 5e-4` Å |
| `characterisation` | nothing — asserts the *shape* of a known systematic, or that a model is **inadmissible** | QPA sample 4; Stephens cone (12/43 → 0/43); SRM 676a's `abs(da - dc) < 1.5e-4` uniformity |
| `prediction` | a parameter-free prediction written down **before** the measurement | capillary ΔB = c(µR)·λ²/2 (predicted 0.0166542, measured 0.0166542); the dispersion suite against the frozen `V03_ERRORS` |

And one thing that is **not** a tier and must be labelled so it is never read
as one: the `ceiling` — `rwp < 0.20`, `gof < 2.0`, `status == "converged"`.
These are regression bars. They carry no accuracy claim, they are loose by
construction, and a matrix that counted them as validation would score the
whole v0.5 milestone as delivering nothing (see the next paragraph).

**The v0.5 method result is the reason the last two tiers must exist.** Not one
of that milestone's eight corrections is well judged by Δ Rwp: two provably
cannot move it, one moves it the *wrong way* when it is right, and the two
largest accuracy wins are invisible in it. A validation matrix whose columns
were agreement indices would be blind to the best work in the repo.

### Inherited

From **WP-0602** (agent JSON surface, landed 2026-07-29) — two serialization
facts that bite golden-file comparisons:

- **`Provenance` gained `solver`** (default `"trf"`) and now stamps the *live*
  `report_thresholds_version` (0.1 → 0.3 as serialized; the schema default
  was stale for two versions).  Any matrix that diffs serialized results
  against stored goldens must regenerate or mask these fields — and if the
  matrix ever compares `trf` vs `lm` rows, the provenance now distinguishes
  them without a side channel.
- **`StageResult` gained `n_constraint_truncations`** and results can carry a
  `CONSTRAINT_ACTIVE` info diagnostic under `solver="lm"`; diagnostic-set
  equality checks need the new code in their vocabulary.

From **WP-0508** (flat-plate absorption, landed 2026-07-28) — a new suite, a
new *kind* of tolerance, and a dataset with a documented circularity.

- **An eighth acceptance suite exists**: `tests/test_acceptance_capillary.py`
  (slow, ~17 s), on `11BM_LaB6_660a.fxye` — NIST SRM 660a LaB₆ at APS 11-BM in
  the beamline's documented 0.81 mm Kapton bore.
- **Its tolerances are a tier the matrix does not yet have: *identity*
  tolerances.** The capillary correction is an exact reparameterisation of
  {scale, Biso}, so the assertions are |ΔRwp| < 1e-6, |Δa| < 1e-9 Å and
  |ΔB − predicted| < 1e-5 Å² *between two fits*, not agreement with an external
  value. Measured margins are 3e-8, 8e-12 and ~1e-7, i.e. two to four orders
  inside the bars. This tier is not referenced to a certificate, to a
  participant spread, or to σ — it is referenced to floating-point arithmetic,
  and the policy should name it rather than force it into an accuracy band.
- **The cell from that dataset must never enter the matrix as an anchor.** λ was
  calibrated at the beamline against LaB₆ itself (`# Calibration from:
  .../11bmb_3843.calib`), so a refined LaB₆ cell reproduces the standard by
  construction. It lands 16 ppm from the SRM 660a certificate, which is worth
  recording as consistency and nothing more. The absolute anchors stay SRM 660c
  and SRM 676a.
- **The v0.5 milestone record ends with a table this WP should adopt**
  ([../milestones/v0.5.md](../milestones/v0.5.md)): for each of the eight
  corrections, Δ Rwp versus what it actually changes. Not one of the eight is
  well judged by Δ Rwp — two cannot move it, one moves it the wrong way when it
  is right, and the two largest accuracy wins are invisible in it. A validation
  matrix whose columns are agreement indices would score this milestone as
  having delivered nothing.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — two measured ceilings
that a tolerance policy written from certificates alone would violate.

- **SRM 676a is a `c/a` anchor, not an absolute-axis anchor.** Measured c/a is
  +30 ppm vs certificate, but the absolute axes are −313/−283 ppm — a uniform
  lab d-scale systematic, asserted as such rather than absorbed into a widened
  band. A tolerance written against the certificate's own ±8e-6 would be
  unmeetable by construction on lab data. The tier this belongs in is
  "certificate-grade on the *ratio*, systematics-limited on the scale".
- **The achievable GoF for analytical-PSF lab fits is floor-limited at
  1.5–1.9** (Cline et al. 2015, J. Res. NIST 120, 173, for this instrument
  class; FPA reaches 1.08 and is fenced to v2). Measured 1.61 on corundum with
  Rexp ≈ 8.9 %, so Rwp = 14.4 % is mostly counting statistics, not misfit. A
  policy demanding GoF → 1 would be demanding FPA.

From **WP-0507** (anode wavelengths, landed 2026-07-28) — **every acceptance
number in the repo is a Cu measurement, and that is now a stated gap rather
than an unstated assumption.** Six anodes ship (Cr/Fe/Co/Cu/Mo/Ag, plus Kα1-only
variants); none but Cu has a dataset behind it, so what is validated is the
*table and its checks*, not a refinement at those wavelengths. Two things for
the matrix:

- **A non-Cu dataset is the single cheapest new tier** — Co Kα on an Fe-bearing
  specimen is the routine real case (Cu Kα fluoresces Fe: µ/ρ = 297.7 vs 56.2)
  and would exercise the parts of the chain that are wavelength-dependent all
  at once: dispersion (f′ = −3.3 e for Fe at Co Kα, 180 eV under its K edge),
  absorption, and the per-anode Kβ contamination check.
- **Wavelength scale is a validation axis of its own.** All six anodes come from
  one column of one evaluation (NIST XRTE SRD 128) and the shipped Cu pair is
  bit-identical to it; a test asserts that, because if the table were ever
  re-sourced, every cell in `tests/data` would move with it and *no other
  assertion in the suite would notice*. Any tolerance policy on cell parameters
  is downstream of that assertion — the SRM 676a ±30 ppm result above is
  measured on this scale.

From **WP-0505** (sequential series, landed 2026-07-28) — a new acceptance
suite, and a *tier* the policy does not yet name.
`tests/test_acceptance_sequential.py` refits the eight round-robin sample-1
mixtures as a warm-started chain under the v0.3 QPA protocol imported wholesale
from `test_acceptance_qpa_roundrobin`, so what it measures is the chaining and
nothing else. Its assertions are the *same* participant-spread tolerances, plus
a "chained agrees with independent" band of 1 wt %. Two consequences:

- **The comparison target is this package's own other result**, not a
  certificate and not another code — a third kind of anchor beside the
  absolute (SRM) and cross-code (GSAS) ones the scope names, and the tier it
  belongs in is closer to "exact" than either: two runs of the same protocol
  differing only in starting values should agree far inside any physical
  tolerance, and 1 wt % is generous rather than tight.
- **Its numbers move when the round-robin protocol moves.** The chained pass
  reproduces the v0.3 independent-fit record exactly (RMS |ΔW| 2.26 wt %, worst
  5.13, mean Rwp 0.1278) because it *is* that protocol; the WP-0504 note above
  about re-measuring if dispersion is switched on by default therefore applies
  to this suite too, in lockstep.

From **WP-0401** (op shim, landed 2026-07-24): current baselines to write the
matrix against are SRM 660c Rwp 8.66 % and NAC Rwp 9.31 % (unchanged across the
shim refactor, verified bit-identical). SRM 660c's cell sits +28 ppm from the
CIF block value under an explicitly *interim* ±2e-4 Å band — the residual bias
there is unmodelled equatorial divergence, tube tails and monochromator
passband, i.e. the same FPA territory.

From **WP-0503** (Stephens anisotropic strain, landed 2026-07-27) — **do not
name Hamilton's R-ratio test as the arbiter of "are these parameters
justified".** Measured on the 7251-channel round-robin patterns: at α = 0.05 it
blesses a *0.13 %* χ² improvement from three inert parameters on corundum
exactly as it blesses a real 6.9 % one on brucite. Hamilton's threshold does
not grow with the channel count, so on modern step-scanned patterns almost any
added parameter clears it. ΔBIC separated the same pair by +488 vs −17 (its
ln(N) penalty does grow with N), and is the statistic the policy should quote.
Both are already implemented in `report/layer2.py`.

Also from WP-0503, a third acceptance *shape* the policy should recognise
alongside "absolute anchor" and "cross-code consistency": **a test that asserts
a model is inadmissible.** `tests/test_acceptance_stephens.py` asserts that an
Rwp improvement both statistical tests bless is nonetheless rejected by a
physics guard (the strain-variance cone), on real data. That tier is neither
exact nor statistical — it is "characterisation", the same tier round-robin
sample 4 occupies for microabsorption, and the matrix needs a name for it.

From **WP-0504** (anomalous f′/f″, landed 2026-07-27) — **every acceptance
number recorded in `docs/milestones/` was measured with dispersion OFF, and
turning it on is the right default for v1.0.** `Source.dispersion` shipped
opt-in precisely so that landing it did not invalidate the record; flipping the
default is a re-measurement of the whole matrix, and that is this WP's job.

What the flip is worth, measured, not projected: on the eight IUCr round-robin
sample-1 mixtures under the *identical* v0.3 protocol, the QPA error goes from
RMS 2.26 → **0.69 wt %** and worst |ΔW| 5.13 → **1.39 wt %**. It also
**re-derives a v0.3 conclusion**: the signed bias shape v0.3 attributed to
untreated microabsorption is mostly neglected dispersion (the giveaway was
fluorite coming back *high*, which microabsorption could not explain).
`test_sample1_bias_has_the_dispersion_shape` carries the corrected reasoning
while still asserting the dispersion-off shape, because that suite deliberately
stays comparable to v0.3.

Three consequences for the policy:

* Numbers to re-measure when the default flips: every QPA figure in
  `milestones/v0.3.md`, and the lab Rwp/Biso baselines (SRM 660c moves Rwp
  8.661 → 8.640 % and B(La)/B(B) by 12 %/22 % — the cell does **not** move,
  4.156895 Å either way, so the absolute anchor is safe).
* The **`DISPERSION_NEGLECTED` diagnostic** (`refine.py`) already names which
  species and by how much. A validation matrix entry that runs dispersion-off
  should assert the diagnostic is present, not merely tolerate it.
* This is a fourth acceptance shape, alongside 0503's "assert a model is
  inadmissible": **a pre-registered prediction about numbers already
  recorded.** The prediction here was parameter-free (each phase's Bragg power
  ratio), written into the WP before the refits, and beat itself (predicted RMS
  0.83, measured 0.69). The matrix should have a name for that tier — it is
  much stronger evidence than a tolerance being met.

From **WP-0601** (bounded LM solver, landed 2026-07-28) — a benchmark
methodology this WP can adopt wholesale, and one result that is a validation
question rather than a solver one.

- **`examples/bench_solver.py` is the shape a driver/config comparison should
  take**, and each of its three rules exists because breaking it produces a
  misleading number: both arms timed in the *same process against current main*
  (every pre-WP-0605 wall-clock figure in this repo is stale by 1.23×); the
  stopping rule fixed *before* anything is compared (Coelho 2018 §2.4.2: a
  loose criterion favours the more erratic updater); and the quality column
  reported as ΔBIC, never Hamilton and never Δ Rwp. Measured result, for the
  record: the two drivers tie (0.74-1.04×, identical minimum on two of three
  protocols, ΔBIC −13 on the third).
- **Start-dependence is the missing axis of the validation matrix, and it
  changes a conclusion.** Sweeping `Stage.strain_seed` over 400/800/1600/3000
  on round-robin brucite leaves the Stephens coefficients spanning ~100 %
  relative spread under *both* drivers, and moves the unconstrained fit in and
  out of the physical cone (15, 12, 0, 0 reflections violating). A single-start
  acceptance number would have called that specimen either fine or broken
  depending on which seed the suite happened to pin. Any tolerance policy this
  WP writes should say how many starts a quoted parameter has to survive —
  `docs/solver-survey.md` §E6 set exactly that kill criterion in advance, and
  it fired.

## Non-goals

- **No new dataset.** The non-Cu (Co Kα on an Fe-bearing specimen) gap WP-0507
  identified is real and is the cheapest *next* tier, but acquiring and
  provenancing a dataset is its own work. This WP records the gap in the
  matrix as an explicit hole rather than filling it.
- **No CI wiring** — that is [1002](1002-ci-matrix.md). This WP must leave the
  guards runnable by the plain fast-suite command, which is what 1002 will
  schedule.
- **No API decisions** beyond the one default this WP is chartered to decide
  (`Source.dispersion`). Signature freezes are [1003](1003-api-freeze-pypi.md).
- **Not FPA.** The SRM 660c ±8e-6 certificate band and GoF → 1 are both
  FPA-territory and fenced to v2; the policy states them as characterised
  ceilings, not as targets.

## Tasks

- [x] **Tier vocabulary + registry.** `tests/validation_matrix.py`: the seven
      tiers plus `ceiling`, each with a written rule, and one row per
      acceptance test naming its tier(s), reference, dataset and what it
      claims. Frozen measured margins where a row has them.
- [x] **Anti-drift guards** (`tests/test_validation_matrix.py`, **fast** suite):
      every `test_acceptance_*.py` test function has a row and every row names
      a live test (AST-collected, so it cannot pass by import side effect);
      every row's tier is in the closed vocabulary; every non-`ceiling` row
      names a reference; the dataset names resolve against `tests/data`.
- [x] **`docs/VALIDATION.md` generated from the registry**, with the committed
      file asserted byte-identical to the regeneration — the manual's
      executable-doc design applied to the matrix.
- [x] **Decide the `Source.dispersion` default on measurement.** Census what
      default-on would raise on (untabulated Z, on-edge wavelengths, the
      Kα1/Kα2 line guard) before touching the default; record the decision and
      its grounds either way.
- [x] **Start-dependence policy**, with the rule stated in the matrix and
      applied to the one place it is known to bite (Stephens coefficients).
- [ ] **Reconcile README §Validation** with the generated matrix (it says
      "eight suites"; there are nine).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_validation_matrix.py -q     # the guards
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow" # fast suite
.venv/bin/python -m pytest -n auto --dist loadgroup               # full, incl. acceptance
.venv/bin/python -m ruff check src tests examples
```

The matrix is "green" when every acceptance test in the tree is registered
with a tier, `docs/VALIDATION.md` matches its regeneration byte-for-byte, and
the full suite passes.

## References

- Madsen et al. (2001) *J. Appl. Cryst.* **34**, 409 — IUCr CPD QPA round
  robin; the participant spread the `spread` tier is referenced to.
- Cline et al. (2015) *J. Res. NIST* **120**, 173 — the 1.5–1.9 GoF floor for
  analytical-PSF lab fits.
- Hamilton (1965) *Acta Cryst.* **18**, 502 — the R-ratio test the policy
  declines to use as arbiter, and why.
- NIST SRM 660c / 660a / 676a certificates; GSAS-II fluorapatite tutorial
  (`FAP.EXP`); provenance for all of it in `tests/data/README.md`.

## Handover log

- **2026-07-29** — expanded from stub into a full WP: goal, the seven-tier
  finding (the scope's three do not survive contact with the suites), tasks,
  acceptance. Starting on the registry.
- **2026-07-22** — created as a stub from the ROADMAP split.
