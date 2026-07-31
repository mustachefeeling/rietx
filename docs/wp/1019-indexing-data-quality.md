# WP-1019 — Data-quality gate and the systematic-error model

Milestone: v1.0 · Status: ✅ complete 2026-07-30
Depends on: 1018

## Goal

Before any engine runs, a `PeakList` is judged fit to index or not — and any
systematic 2θ shift is fitted with the *physically correct* template (zero
shift vs specimen displacement vs transparency) and **named**, rather than
absorbed into one constant as every program in the literature does.

## Goal, restated as the finding it encodes

Both source papers conclude that data quality decides success —
*"Lack of attention to data quality, even if followed by use of the most
efficient programs, will usually lead to failure"* (Bergmann et al. 2004). This
WP is that sentence made executable: the module measures whether the data can
support indexing and **abstains** when it cannot, the same move Layer 1's
global maturity gate makes.

## Context

- **The shift model is the one genuine improvement over every program the 2004
  paper benchmarks.** Those programs fit a single constant "zeropoint". Both
  bethanechol ICDD entries carry ~0.10° 2θ, and the paper itself *hypothesises*
  it is a **specimen-displacement** error — but had no way to test that. This
  package already distinguishes the three causes.
- **Reuse the template vocabulary verbatim** from `report/layer2.py`'s
  `_POSITION_TEMPLATES` / `_POSITION_ACTIONS` (`layer2.py:47-52`) so the
  package has one name per physical cause:

  | template | cause | shift |
  |---|---|---|
  | `constant` | zero shift | δ(θ) = z |
  | `cos_theta` | specimen displacement | δ(θ) = s·cos θ |
  | `sin_2theta` | transparency | δ(θ) = t·sin 2θ |

- **Fit each template alone — nested single fits, never jointly.** Restate
  Layer 1's *measured* reason in the docstring: a joint fit of collinear
  templates returned "a 0.02° zero-point error as a 1.8° constant cancelled by
  a −1.8° cosθ" (`report/layer1.py:301-306`). Score on residual sums of
  squares and call the winner distinguishable only at
  `SEPARABILITY_MIN_SS_RATIO = 2.0` — **import it from `report.schemas`**, do
  not restate the number.
- When separable, emit `INDEX_SHIFT_DETECTED` naming the template's physics.
  When not, emit `INDEX_SHIFT_MODEL_AMBIGUOUS`: the **cell stands** (all three
  templates remove the same amount at the sampled angles) but the *cause* is
  not claimed. That asymmetry is the point — it is the same shape as Layer 2
  reporting collinear templates as non-separable rather than picking one.
  **Corrected on measurement (2026-07-30): "all three" is wrong and
  "competitive" is right** — over 10-25° the three templates' predictions differ
  by 0.046° on a 0.10° shift, but the one that disagrees is the one the data
  rejects; over the templates that fit comparably the spread is 0.0011°. The
  conclusion holds, the reasoning does not, and `prediction_spread_deg` now
  reports the number instead of the claim being asserted.
- The residual scatter after the shift fit sets a global `σ_sys` floor, which
  WP-1020's tolerance model adds in quadrature to each line's own σ(Q).
- **Dominant zone / dominant row.** A cell axis much shorter than the other two
  makes most low-angle lines share a zero Miller index (Werner's short-axis
  test); a much longer one gives a dominant row. Both are classic reasons a
  wrong cell scores well. ~~and both are detectable in Q-space before any
  search~~ — **that last clause is false, measured 2026-07-30 and recorded in
  the handover log.** Neither is a summary statistic of a peak list: a dominant
  zone is the statement that the low-angle lines satisfy a *2-D* quadratic form
  and a dominant row is an arithmetic progression k²B among the low Q values, so
  each is a search. The census that was tried scores dominant-zone cells at
  +0.9σ and a *general* monoclinic cell at +3.3σ. Owed to WP-1021/1022.
  The 2004 paper notes bethanechol has a dominant row (b ≫ a, c).
- **The volume envelope**: Smith (1977) `V ≈ 0.6·d_N³/(1/N − 0.0052)`, which at
  N = 20 is `V ≈ 13.39·d₂₀³` for triclinic, scaled per system. Used as the
  default `max_volume` and to flag `INDEX_VOLUME_UNPHYSICAL` later.
  **"Scaled per system" turned out to need two factors, not one** (Laue orbit
  ×  centring multiplicity): with the Laue factor alone the envelope *excluded*
  corundum's true volume, 125 Å³ against 255. The scaling is derived here rather
  than taken from the paper — see the handover log's open item.
- **Abstention is a result, not a failure.** `DataQualityReport.supports_indexing`
  and `abstained_reason` are what `index_pattern` reads before spending any
  budget.

### Inherited

From **WP-1018**: `PeakList.usable()` filters ghost-flagged and user-excluded
lines — the σ census and every screen here run on `usable()`, not on `peaks`.
`PeakList.from_positions` produces lines with an *assumed* σ and sets
`PEAK_SIGMA_ASSUMED`; the gate must treat an assumed σ as unmeasured (it is the
input the bethanechol benchmark arrives as, WP-1026) and say so rather than
quoting a precision it does not have.

Landed 2026-07-30, and four things sharpen what this WP has to do:

- **Read `PeakList.source`, not the flags, for the assumed-σ question.** It is
  `"fitted"` or `"positions"`, one field on the list, and it is what
  `PEAK_SIGMA_ASSUMED` is emitted from. `PEAK_UNUSABLE_FLAGS` deliberately does
  **not** drop `sigma_assumed` or `unresolved_shoulder` lines — they are still
  evidence, just less precise evidence, and their σ says so.
- **The diagnostics translator is already public and already handles a
  handed-in list**: `indexing.diagnostics.peak_diagnostics(peaks, detection=None)`.
  Call it rather than re-deriving `PEAK_SIGMA_ASSUMED` here, and add this WP's
  `INDEX_*` codes alongside rather than inside it — a peak list's flags and a
  data-quality verdict are different statements.
- **A precision floor already exists in the fitter, and this WP's σ_sys sits on
  top of it.** Per-line σ carries `√max(χ²_red, 1)` (via
  `statistics.normal_covariance(chi2_floor=True)`) but deliberately **not**
  Bérar-Lelann — that estimator is about serial correlation across a whole
  pattern, and a 40-400-point window is not that population. If this WP's σ_sys
  ends up looking like a serial-correlation term, do not reach for BL per peak;
  ~150 independent inflations compounded into the tolerance model is the failure
  mode being avoided.
- **σ is now calibrated — the premise of this WP holds.** WP-1018 closed
  2026-07-30 with the pull ensemble measured: `(2θ_fit − 2θ_true)/σ_fit` has mean
  +0.032 / std 0.971 on a synchrotron single line and mean −0.083 / std 0.980 on
  a lab Cu Kα doublet, over ~1300 fitted lines each, against bars `|mean| < 0.15`
  and `std ∈ [0.85, 1.20]` written before the measurement. So the σ census and
  the `SEPARABILITY_MIN_SS_RATIO` screen may read σ as a known scale: it is
  unbiased to ~0.1σ and correctly scaled to ~3 %.
- **Size any ensemble this WP builds by the standard error, not by the sample
  count.** WP-1018's own plan asked for 200 groups; 200 is ample for a `std` bar
  and **not** for a `mean` one (SE 0.07 against a 0.15 bar), and a 200-group
  subsample read −0.15 where the converged value was −0.08. Its test now asserts
  `3·SE < bar` before asserting the bar. Any σ_sys or separability threshold
  validated by simulation here wants the same guard.
- **The one thing σ does not cover is exactly this WP's subject.** Per-line
  σ(2θ) is 2e-4 to 2e-3° on strong lines; the bethanechol shift is ~0.10°. That
  is two to three orders of magnitude, so the shift is *richly* determined and
  the difficulty is entirely in **attributing** it to the right template, never
  in detecting it. It also means a downstream tolerance built from σ alone
  rejects the true cell on real data — σ_sys is not a refinement, it is what
  makes the tolerance usable.
- **A residual −0.08σ position bias survives on doublet data**, localised to the
  detection-seeded window rather than the estimator (four other mechanisms were
  measured and excluded; 1018's handover log). 2e-5° in degrees, i.e. nothing
  next to the shifts here — but it is a *bias*, so a statistic that averages
  positions over many lines does not average it away. The shift screen fits
  coefficients from many lines at once: `constant` would absorb it as a −2e-5°
  zero point, four orders below anything reportable.

## Non-goals

- No cell search (WP-1021-1023), no FoM panel or Q-space machinery (WP-1020).
- The shift is **fitted and reported**, not refined jointly with a cell — that
  happens inside `refine_candidate` (WP-1020) with this WP's chosen template.
- No goniometer-radius diagnostic — that is `INDEX_CELL_SYSTEMATIC_UNQUANTIFIED`
  in WP-1024, where a cell actually exists to attach it to.

## Tasks

- [x] `indexing/quality.py` + `DataQualityReport` in `schemas/indexing.py`:
      σ census (median/worst σ(2θ), and σ(Q)/Q against mean line spacing),
      line count against each system's metric DOF.
- [x] Nested single-template screen over `constant` / `cos_theta` /
      `sin_2theta`, importing `SEPARABILITY_MIN_SS_RATIO` from
      `report.schemas`; report coefficient, stderr, separability ratio.
      **Plus `prediction_spread_deg`, which the plan did not have and which is
      what makes "the cell stands" checkable** — see the handover log.
- [ ] ~~Dominant-zone and dominant-row detection in Q-space.~~ **Measured no-go
      — neither is detectable from a census.** The statistic was written,
      measured, and removed; the detection is owed to WP-1021/1022, which have
      been told. Handover log has the numbers.
- [x] Smith (1977) volume envelope; the abstention gate
      (`supports_indexing`, `abstained_reason`). Envelope reported **per
      system** and scaled by Laue orbit factor × centring multiplicity — the
      published triclinic constant excluded corundum's true volume by 2×.
- [x] Diagnostics: `INDEX_SHIFT_DETECTED`, `INDEX_SHIFT_MODEL_AMBIGUOUS`,
      `PEAK_POSITION_PRECISION`, and `INDEX_DATA_INSUFFICIENT` for the
      abstention (the plan had no code for it). `INDEX_DOMINANT_ZONE` is not
      emitted — see above.
- [x] `tests/test_indexing_quality.py` — 31 tests, ~2 s.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_quality.py -q
.venv/bin/python -m ruff check src tests examples
```

Criterion: on a synthetic pattern given a pure cos θ displacement over a 2θ
range where the templates *are* separable, the screen names `cos_theta` and
the recovered coefficient is within 2 σ of the injected one; over a short
low-angle range it emits `INDEX_SHIFT_MODEL_AMBIGUOUS` and names no cause.

## References

- Bergmann, J., Le Bail, A., Shirley, R. & Zlokazov, V. (2004).
  *Z. Kristallogr.* **219**, 783-790 — the ~0.10° bethanechol shift and the
  specimen-displacement hypothesis (§"Recommendations, hints and tips").
- Smith, G. S. (1977). *J. Appl. Cryst.* **10**, 252-255 — unit-cell volume
  from one line.
- Werner, P.-E., Eriksson, L. & Westdahl, M. (1985). *J. Appl. Cryst.* **18**,
  367-370 — the monoclinic short-axis (dominant zone) test.
- `report/layer1.py:301-306` (the measured collinearity failure),
  `report/layer2.py:47-52` (template names), `report/schemas.py`
  (`SEPARABILITY_MIN_SS_RATIO`).

## Handover log

- **2026-07-30 — CLOSED.** `indexing/quality.py`,
  `DataQualityReport`/`ShiftScreen`/`ShiftTemplateFit` in `schemas/indexing.py`,
  `diagnostics.quality_diagnostics`, `tests/test_indexing_quality.py` (31 tests,
  ~2 s). Fast suite 1135 passed / 66 skipped in 68 s, ruff clean.

  **The design question this WP's plan left open, and the answer:** *what is
  knowable from a peak list alone.* Everything the plan asked for except the
  shift is a property of the list. The shift is **not** — with no cell there is
  nothing to deviate from. So `fit_shift_model(two_theta, deviation, esd)` takes
  deviations; `assess_peak_list` screens the shift only when the caller supplies
  `reference_two_theta` (a certified cell, an internal standard, a candidate cell
  an engine proposed); and with none it reports `shift.source == "unavailable"`
  rather than a shift of zero it never measured. What *is* computable with no data
  at all is the **separability geometry** — `template_collinearity(two_theta)`
  needs only the angles, so it is a statement about the experiment rather than the
  specimen, and it can be read before a specimen is even loaded.

  *Four measurements, each of which changed something.*

  1. **"The cell stands when the cause is ambiguous" is true only with the word
     *competitive* in it.** Over 10-25° 2θ with a 0.10° cos θ displacement (the
     bethanechol case), all three templates' predicted corrections differ by
     **0.046°** — nearly half the shift, Δd/d ≈ 2e-3, a 0.2 % cell error if the
     wrong one is applied. That looked like a refutation of the plan. It is not:
     `sin_2theta` is not *competitive* there (its residual SS exceeds the ratio
     bar), and over the two templates that are, the spread is **0.0011°**, 1 % of
     the shift. So the plan's conclusion survives with its reasoning narrowed —
     a template the data rejects is not a candidate cause, and averaging it in
     overstates the risk forty-fold. `ShiftScreen.prediction_spread_deg` now
     *reports* the number instead of the docstring asserting the claim, and both
     numbers are pinned in the test.
  2. **Dominant zone and dominant row are not detectable from a census. A
     measured no-go.** The plan asserted both "are detectable in Q-space before
     any search"; they are not, because neither is a summary statistic. A dominant
     zone is the statement that the low-angle lines satisfy a **two-dimensional**
     quadratic form; a dominant row is an arithmetic progression k²B hiding among
     the low Q values. Each is a *search*. The obvious census — Ito's
     most-repeated Q difference — was implemented, measured and removed: at σ(Q)
     from a 0.002° list it scores dominant-zone cells (c = 3.1 and 2.7 Å) at
     **+0.9σ and +0.8σ** against a permutation null while scoring a *general*
     monoclinic cell at **+3.3σ**; against a uniform null a **cubic** list scores
     **+15.6σ**, because Q = A(h²+k²+l²) makes every difference a multiple of A.
     It detects commensurability, not zones. Two side notes worth keeping: the
     permutation null (same spacing multiset, order destroyed) is the right null
     and it is what exposed the statistic as useless — a uniform null would have
     "confirmed" it on the cubic case; and `INDEX_DOMINANT_ZONE` is therefore
     *not* an emitted code, with a test asserting its absence so it cannot creep
     back. WP-1021/1022 have been told in their `### Inherited` sections.
  3. **Smith's envelope needs two scalings, and the second was found by the
     envelope excluding the right answer.** The Laue orbit factor is obvious in
     hindsight (a cubic lattice shows ~24× fewer *distinct* lines than triclinic
     at equal volume, so the published triclinic constant bounds a cubic search
     24× too tightly). Centring is not: with Laue scaling alone, corundum's
     envelope came out at **125 Å³ against a true 255 Å³** — R-centring
     extinguishes two thirds of hkl. Centring is part of the answer (WP-1025's
     extinction symbol), so the default is the worst case each system allows, with
     `centring_multiplicity=` to tighten it later. The envelope is reported **per
     system** because they span 96×, and `_LAUE_ORBIT_FACTOR` is checked against
     `generate_reflections` rather than tabulated.
  4. **`tan_theta` had to be excluded from the shift basis, and it is not
     pedantry.** A tanθ deviation *is* a cell error; offering it would let the
     screen explain a shift by changing the very answer indexing is about to
     produce. Measured: a pure tanθ deviation leaves the best *shift* template at
     r² < 0.95, so it is not absorbed. Also measured, and worth knowing before
     tuning anything: `constant` and `cos θ` stay **0.96 collinear even over
     10-140°** (1.0000 → 0.9987 → 0.9852 → 0.9646 as the range extends), so
     separability must be decided on the residual-SS ratio against real data and
     never on the geometry alone.

  *Two thresholds this WP added beyond the plan*, both in `schemas/indexing.py`
  with their reasoning: `MIN_LINES_PER_DOF = 5` (with `METRIC_DOF` per system, so
  20 lines is 20× over-determined for cubic and 3.3× for triclinic — "enough
  lines" is not one number, and the report lists *which systems* the data
  supports) and `MAX_RELATIVE_SIGMA_Q = 1e-3` (a resolving power: at 1e-3 two
  cells differing by 0.1 % in a lattice parameter are indistinguishable, which is
  the scale derivative-lattice ambiguity lives at). Plus one diagnostic code the
  plan had no slot for, `INDEX_DATA_INSUFFICIENT`, which is what an abstention
  emits.

  *Open, and it wants the user rather than a session.* **The per-system scaling of
  Smith's envelope is derived here, not published.** Smith (1977) is quoted in
  this WP only in its triclinic form, and the paper reportedly gives per-symmetry
  factors; the two scalings above are this session's derivation (Laue orbit factor
  × centring multiplicity), validated against `generate_reflections` and against
  four real cells rather than against the paper. A clean copy of *J. Appl. Cryst.*
  **10**, 252-255 would let the derived factors be replaced by, or checked
  against, the published ones — and the WP-0501 b₂ episode is the precedent for
  why that matters.

- **2026-07-29** — created from the indexing plan.
