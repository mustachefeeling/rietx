# WP-1038 — Pre-indexing 2θ shift from reflection pairs

Milestone: v1.0 · Status: ⬜
Depends on: WP-1019, WP-1024

## Goal

`assess_peak_list` measures a systematic 2θ shift **from the peak list alone** —
no cell, no indices, no reference — so `effective_sigma_sys` can stop assuming one.
This is the single structural reason every real dataset abstains.

## Context

### Why this matters more than anything else in the indexing block

`grade` (`consensus.py:317-340`) needs **zero** caveats for `high`.
`effective_sigma_sys` (`engines.py:413-429`) trusts `quality.shift.sigma_sys_deg`
only when `shift.source == "measured"`, and `assess_peak_list` can only reach that
when the caller supplies `reference_two_theta`. On real data nobody can, so
`INDEX_SHIFT_ALLOWANCE` fires, `shift_allowance_assumed` caps confidence at
`medium`, and **`best_or_none()` is structurally `None` on all eight known-cell
datasets — including the five that rank the truth first.**

`quality.py`'s module docstring (lines 25-32) currently asserts the opposite of
this WP: *"a shift is identifiable only against a reference."* That thesis is what
this work refutes, and rewriting it is part of the job.

### This is not a novel idea — DICVOL04 ships it

**Boultif & Louër (2004) §3.1(ii)** adopts Dong, Wu & Chen (1999) as its *a priori*
option for shifts ~0.10° 2θ, and supplies the false-pair rule so we do not have to
invent one:

> partition the pairs into a positive-shift and a negative-shift category, take the
> more populous, and admit it **as soon as the difference between the categories is
> ≥ 2**. If that is not verified, run the indexing search **under both hypotheses**.

Its measured demonstration — barium titanyl hydrate, V = 2596 Å³: with +0.20° 2θ
added artificially, **no solution in 7 s**; with the a priori correction, solution
in **3 s**. Table 2 separately shows refining the shift alongside the cell roughly
doubles M₂₀ (97 vs 41; 235 vs 145; 69 vs 50).

**Le Bail (2004) §VII** independently reaches the same conclusion from the other
direction: *"Adding the zeropoint as a supplementary parameter in the Monte Carlo
calculations is also very demanding in time and was not made. **The zeropoint
problem is really something to be solved before indexing.**"* McMaille's own
±0.05° tolerance comes from inflating the peak width to 2–3× the true FWHM — the
same number and the same device as our `DEFAULT_UNKNOWN_SHIFT_DEG = 0.05`, reached
independently.

### The physics, restated so this file is self-contained

Two reflections form a pair when `d_hkl = m·d_h'k'l'` with `(h',k',l') = m·(h,k,l)`,
m integer — harmonics of one plane. Bragg then gives **exactly**

    m·sin θ_B = sin θ'_B

with no knowledge of the cell, the system or the indices. With a constant zero
shift (`2θ_B = 2θ_obs + 2θ_z`), Dong eq. (5) solves it in closed form:

    2θ_z = 2·arctan[ (sin θ' − m·sin θ) / (m·cos θ − cos θ') ]

**Dong eq. (6) is wrong as printed — do not transcribe it.** Verified against the
source file, not the OCR: implicit differentiation of `m·sin(θ+z) = sin(θ'+z)`
gives

    dz = [cos θ'_B·dθ' − m·cos θ_B·dθ] / (m·cos θ_B − cos θ'_B)

so the sensitivity to the **low-angle** member is `m·cos θ_B/(m·cos θ_B − cos θ'_B)`
— which is algebraically identical to the `(m² − m·cos(θ'−θ))/D` term the paper
attaches to `|Δ2θ'|`, using `D = m² + 1 − 2m·cos(θ'−θ) = (m·cos θ_B − cos θ'_B)²`.
At m = 2, θ = 10° the two coefficients are **1.9088** and **0.9089** and the paper
swaps them. Only the derived form reads correctly: the low line's error is
amplified by ~m, which is why the method wants a high harmonic order against a
well-measured low line. **Derive it, pin it against a central difference, and leave
a test recording the discrepancy** so the next reader does not "fix" the code back
to the paper.

### Design constraints this package imposes

- **Generalise past a constant.** The pair relation is exact for *any* shift model;
  substitute `2θ_B = 2θ_obs + δ(2θ_obs)` and solve for the coefficient. Our real
  datasets are **cos θ displacement-dominated** (corundum −0.061 ± 0.014° against
  an independently measured −0.065°; LaB6 +0.0367 ± 0.0015° against a
  parameter-free geometric prediction of +0.0415°), so a constant-only estimator is
  biased. `quality.shift_template_basis` / `template_collinearity` already build the
  three-template basis; reuse, do not restate. Fit templates **alone, never
  jointly** — Layer 1 measured a joint fit returning "a 0.02° zero-point error as a
  1.8° constant cancelled by a −1.8° cos θ".
- **Harmonic pairs straddle the 2θ range by construction** (`sin θ' = m·sin θ`
  forces θ' > θ), which is better geometry for separating templates than the general
  line set. But it also bounds supply: `m·sin θ ≤ 1` means the low member sits below
  2θ = 60° for m = 2 and below ~39° for m = 3. **How many pairs the corpus actually
  offers is unknown — that is task 0.**
- **What a search window must span is the shift's *amplitude*, not the residual
  scatter after removing it.** `ShiftScreen.sigma_sys_deg` is the latter.
  `refine_with_shift` runs only *after* a candidate survives, so if
  `effective_sigma_sys` starts returning a measured ~0.005° the window narrows below
  the systematic and the certified cell indexes **zero** lines — the exact 11σ
  failure `DEFAULT_UNKNOWN_SHIFT_DEG`'s docstring is about. The
  `lab6_calibrated` fixture (`tests/test_acceptance_indexing.py:536-539`) already
  computes `sigma_sys_deg=abs(amplitude)` by hand for this reason; a new
  `allowance_deg` field computed once in the screen replaces that hand-rolled step.
- **`ShiftScreen.source` is a `Literal`.** Prefer a third value
  (`"reflection_pairs"`) over widening `"measured"`: the two are different
  measurements with different failure modes (a wrong reference vs accidental
  agreement) and the agent's next action differs. Put *trust* in a separate
  constant (`TRUSTED_SHIFT_SOURCES`) so the label never has to lie. Adding a
  vocabulary member bumps `INDEXING_THRESHOLDS_VERSION`.
- **Clearing the caveat without adopting a template is the trap.** A cell found in
  a widened window has *absorbed* the shift (+1400 ppm measured on corundum). If
  `shift_allowance_assumed` disappears, `index_pattern` must also adopt the measured
  template into `spec.shift_template` — and only when the cause is safe to name
  (`separable`, or `prediction_spread_deg` within the median σ). Otherwise adopt
  nothing and keep the caveat.

### Non-obvious counter-evidence, recorded up front

The most decisive test is also the one the literature says may fail. Bethanechol's
ICDD entries (PDF 43-1748, 46-1964) carry a **−0.10° 2θ zeropoint**, squarely the
regime DICVOL04 names for this method — but Le Bail (2004) §VII says of exactly
those entries: *"Any self-calibration from these original data failed to estimate
that zeropoint error."* Our own suite independently records the 2004 shift
hypothesis coming back **unanswerable** (`max_collinearity` 1.0000). A negative
result here is a real possibility and is still worth having; it is cheap.

### Licensing

Dong et al. (1999) and Boultif & Louër (2004) are open literature — implement from
the papers. PowderX and DICVOL are not to be ported.

## Non-goals

- Refining the shift *after* a candidate exists — that is `refine_with_shift`, and
  it already works.
- Changing `DEFAULT_UNKNOWN_SHIFT_DEG` (WP-1042 territory if ever).
- Re-spiking Monte Carlo — WP-1040.

## Tasks

- [ ] **Task 0 — how many pairs does the corpus actually offer?** For corundum,
      SRM 660c, cpd-1a, the ten bethanechol sets and the HL2 list, record candidate
      triples, accepted pairs, category populations, and wall clock. **Write the
      acceptance bars after this table exists, not before.** No `src/` change.
- [ ] The pair relation, its Newton generalisation to the three templates, and the
      **derived** σ propagation — with the test that records Dong eq. (6)'s printed
      coefficients being swapped (1.9088 vs 0.9089 at m = 2, θ = 10°).
- [ ] A robust estimator with a stated refusal: DICVOL04's sign-category rule
      (more populous category wins, **margin ≥ 2**), plus a seeded permutation null
      so the false-positive rate is *measured* rather than asserted.
- [ ] `ShiftScreen.allowance_deg` — what a search window must span — computed once
      and consumed by `effective_sigma_sys`; delete the `lab6_calibrated` fixture's
      hand computation.
- [ ] `ShiftScreen.source` gains `"reflection_pairs"`; `TRUSTED_SHIFT_SOURCES`;
      `INDEXING_THRESHOLDS_VERSION` bump; `quality.py`'s module-docstring thesis
      rewritten.
- [ ] `assess_peak_list(..., shift_from_pairs=True)` wired, template adoption in
      `index_pattern` gated on the cause being safe to name,
      `INDEX_SHIFT_FROM_PAIRS` diagnostic + `AGENT_PROTOCOL.md` row. **This commit
      changes default behaviour** — `shift_from_pairs=False` must reproduce every
      prior number bit-for-bit, and a test must exercise that escape.
- [ ] Acceptance rows: corundum and SRM 660c against their independently known
      shifts (see Context); the bethanechol **A − C = 0.100°** differential, which
      needs no cell at all; a two-phase pair list (corundum + zincite lines, one
      shift) reproducing Dong's own NiO-impurity result on bundled data.
      `validation_matrix.py` Claims + regenerate `docs/VALIDATION.md`.
- [ ] Theory manual: Dong eq. (5) with its `*Source:*` line, `dong1999` in
      `references.bib`, and the paragraph in `docs/manual/indexing.md` asserting a
      shift is unknowable from the list alone.

## Acceptance

The shift is recovered with no reference on at least the two certified datasets,
within their independently known values; the false-positive rate on structureless
line lists is measured and stated; and `shift_from_pairs=False` reproduces every
pre-change number.

```sh
.venv/bin/python -m pytest tests/test_indexing_shift_pairs.py tests/test_indexing_quality.py \
    tests/test_indexing_engines.py tests/test_validation_matrix.py -n auto
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

## References

- Dong, Wu & Chen (1999), *J. Appl. Cryst.* **32**, 850-853 — the method.
  `/Users/yue/zotero-linker/derived/RPSYEN7Y/`
- Boultif & Louër (2004), *J. Appl. Cryst.* **37**, 724 — §3.1(ii) adopts it, and
  supplies the sign-category rule and the 7 s → 3 s demonstration.
  `/Users/yue/zotero-linker/derived/I2VA3ZAB/`
- Le Bail (2004), *Powder Diffr.* **19**, 249 — §VI–VII: solve the zeropoint before
  indexing; and the bethanechol counter-evidence.
  `/Users/yue/zotero-linker/derived/7AEVVGH6/`
- Dong (1999), *J. Appl. Cryst.* **32**, 838 — PowderX, which implements the pair
  search. `/Users/yue/zotero-linker/derived/4ZBNLND9/`

## Handover log

- **2026-08-04** — created from the source-literature review. The eq. (6) finding
  was derived and checked against the source file this session; everything else
  here is quoted from the papers or from prior WP handover logs and **has not been
  re-measured**. Task 0 exists because the pair supply on this corpus is genuinely
  unknown: `m·sin θ ≤ 1` confines the low member of an m = 3 pair below ~39° 2θ, and
  a 20-line monoclinic list may not yield three pairs at all.
