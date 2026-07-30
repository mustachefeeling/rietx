# WP-1019 — Data-quality gate and the systematic-error model

Milestone: v1.0 · Status: ⬜ not started
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
- The residual scatter after the shift fit sets a global `σ_sys` floor, which
  WP-1020's tolerance model adds in quadrature to each line's own σ(Q).
- **Dominant zone / dominant row.** A cell axis much shorter than the other two
  makes most low-angle lines share a zero Miller index (Werner's short-axis
  test); a much longer one gives a dominant row. Both are classic reasons a
  wrong cell scores well, and both are detectable in Q-space before any search.
  The 2004 paper notes bethanechol has a dominant row (b ≫ a, c).
- **The volume envelope**: Smith (1977) `V ≈ 0.6·d_N³/(1/N − 0.0052)`, which at
  N = 20 is `V ≈ 13.39·d₂₀³` for triclinic, scaled per system. Used as the
  default `max_volume` and to flag `INDEX_VOLUME_UNPHYSICAL` later.
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
- **σ is measured but not yet *calibrated*.** WP-1018 merged with its σ pull
  calibration outstanding (see its handover log). This WP's whole premise is
  that per-line σ can be trusted enough to abstain on, so **run or write that
  test before tuning anything here** — the `SEPARABILITY_MIN_SS_RATIO` screen
  and the σ census both read σ as if its scale were known.

One measured fact worth having before the shift screen is written: on clean
synthetics the fitter recovers injected positions to **0.0005°** with reported
σ(2θ) of 0.0003-0.0006°, i.e. 1-2σ. So the ~0.10° bethanechol shift this WP
exists to model is **two to three orders of magnitude above** the per-line
precision — the shift is richly determined, and the difficulty is entirely in
*attributing* it to the right template, never in detecting it.

## Non-goals

- No cell search (WP-1021-1023), no FoM panel or Q-space machinery (WP-1020).
- The shift is **fitted and reported**, not refined jointly with a cell — that
  happens inside `refine_candidate` (WP-1020) with this WP's chosen template.
- No goniometer-radius diagnostic — that is `INDEX_CELL_SYSTEMATIC_UNQUANTIFIED`
  in WP-1024, where a cell actually exists to attach it to.

## Tasks

- [ ] `indexing/quality.py` + `DataQualityReport` in `schemas/indexing.py`:
      σ census (median/worst σ(2θ), and σ(Q)/Q against mean line spacing),
      line count against each system's metric DOF.
- [ ] Nested single-template screen over `constant` / `cos_theta` /
      `sin_2theta`, importing `SEPARABILITY_MIN_SS_RATIO` from
      `report.schemas`; report coefficient, stderr, separability ratio.
- [ ] Dominant-zone and dominant-row detection in Q-space.
- [ ] Smith (1977) volume envelope; the abstention gate
      (`supports_indexing`, `abstained_reason`).
- [ ] Diagnostics: `INDEX_SHIFT_DETECTED`, `INDEX_SHIFT_MODEL_AMBIGUOUS`,
      `INDEX_DOMINANT_ZONE`, `PEAK_POSITION_PRECISION` — each `where`-tagged
      and each suggestion naming a concrete call.
- [ ] `tests/test_indexing_quality.py`: synthetic peak lists carrying a known
      zero shift, a known displacement and a known transparency —
      **assert the right template wins when the 2θ range makes them separable,
      and that both are reported (not one chosen) when it does not**; assert
      the gate abstains on a 6-line list and on an inflated-σ list.

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

- **2026-07-29** — created from the indexing plan.
