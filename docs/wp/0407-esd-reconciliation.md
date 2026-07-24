# WP-0407 — esd reconciliation (Bérar-Lelann placement)

Milestone: v0.4 · Status: ⬜ not started
Depends on: —

## Goal

Reported per-parameter physical esds actually carry the Bérar-Lelann
serial-correlation inflation that the docstrings and the v0.2 milestone
record describe, and the returned correlation matrix becomes a true Pearson
matrix (unit diagonal) — which also revives the high-correlation guard that
is currently dead.

## Context

ROADMAP flagged this as a docs-vs-behaviour mismatch. Tracing it during v0.4
planning (2026-07-24) found the mismatch has a single mechanical cause, and
that cause additionally breaks a guard. **Both findings were verified
numerically**, not just read.

`covariance_estimates` ([`optimize/least_squares.py`](../../src/pxrdref/optimize/least_squares.py),
end of file) does:

```python
cov  = np.linalg.pinv(JTJ) * chi2_red              # no BL
diag = np.sqrt(np.maximum(np.diag(cov), 0.0)) * berar_lelann_factor(data)
corr = cov / np.outer(diag, diag)                  # <-- diag already carries BL
```

Because `corr` is normalised by the **inflated** diagonal, the returned
"correlation" matrix is `true_corr / BL²` — its diagonal is `1/BL²`, not 1.
Measured on a synthetic collinear case with BL = 5.18: correlation diagonal
= 0.0372 (= 1/BL²), true ρ = −0.699 reported as −0.026.

Two consequences follow:

1. **Reported physical esds are effectively RAW.** `stderr_physical`
   ([`params/vector.py`](../../src/pxrdref/params/vector.py)) rebuilds
   `cov_phys = correlation · outer(s, s)` with `s = chain · stderr_internal`
   and `stderr_internal` already ×BL. The `1/BL²` inside `correlation`
   cancels the `BL²` in `outer(s, s)` **exactly** (verified: physical esd ≡
   raw χ²·(JᵀJ)⁻¹ esd to floating-point equality). So the reported esd is the
   raw one, while `Statistics`' module docstring, `covariance_estimates`'
   docstring and [`../milestones/v0.2.md`](../milestones/v0.2.md) all say the
   esd is inflated. `RefinementResult.qpa`'s σ(W), which routes through
   `physical_covariance` → `_cov_free`, inherits the same cancellation.
   Note the inconsistency this creates: the `correlation=None` fallback path
   (`var = C²·(s·s)`, pre-v0.3 behaviour) *does* report inflated esds — so
   today the same parameter gets a different esd depending on whether a
   correlation matrix was available.
2. **The high-correlation guard is dead.** `check_guards`
   ([`strategy/staged.py`](../../src/pxrdref/strategy/staged.py)) thresholds
   `|corr[i,j]| > 0.98`, but every entry is ÷BL² (÷12 at BL ≈ 3.4, ÷27 at
   5.2), so a genuinely degenerate ρ = 0.99 pair reports ≈ 0.08 and never
   trips. Masked because the only guard tests assert it does *not* fire
   (`tests/test_extinction.py`, `tests/test_preferred_orientation.py`).

### Decision — reconcile by INFLATING (fix the placement)

```python
sqrt = np.sqrt(np.maximum(np.diag(cov), 0.0))
corr = cov / np.outer(sqrt, sqrt)      # true Pearson, unit diagonal
diag = sqrt * berar_lelann_factor(data)
```

One change fixes both: reported physical esds become genuinely ×BL (matching
every docstring and the v0.2 record — whose headline **a = 4.156895(25)** is
already the inflated number, 7×10⁻⁶ × 3.4 ≈ 24×10⁻⁶, so the record's claim
becomes true rather than needing a retraction), and the correlation matrix
becomes honest so the 0.98 guard means what it says. The alternative
direction (keep raw esds, edit the docs) would *still* have to fix the `1/BL²`
diagonal — the correlation matrix is wrong regardless — so it is strictly
more doc-churn for a worse scientific story.

### Ripples to expect

- `tests/test_acceptance_srm660c.py`: `a_err < 5e-5` still passes (≈24×10⁻⁶);
  the comment above it currently *claims* inflation, so it becomes accurate.
  The `1.5 < esd_inflation < 6.0` assertion is untouched.
- QPA σ(W) becomes ×BL. The round-robin tolerances are referenced to the
  published participant spread and deliberately never lean on σ(W)
  ([CLAUDE.md](../../CLAUDE.md), [../milestones/v0.3.md](../milestones/v0.3.md)),
  so nothing breaks; re-measure any σ(W) digits quoted in records.
  `tests/test_qpa.py` asserts *relative* properties (correlated < independent)
  and is unaffected.
- **The guard may now fire in staged plans.** That is the point, but it is a
  behaviour change: watch the acceptance runs for guard-driven differences
  and report them rather than silencing the guard.
- The memory note `esd-berar-lelann-conditioning` documents the *pre-fix*
  behaviour and must be updated or deleted when this lands.

## Non-goals

Replacing Bérar-Lelann with Andreev's bias-corrected figure of merit (the
documented conservatism — E[χ²']/χ² = 1 + 4/π ≈ 1.51 even for white noise —
stays as-is and stays documented); changing what `esd_inflation` reports;
touching the covariance's penalty-row handling.

## Tasks

- [ ] Fix `covariance_estimates`: unit-diagonal correlation from the raw
      sqrt-diagonal, BL applied only to the returned esd diagonal; update
      the docstring to describe what it now does
- [ ] Re-measure SRM 660c; correct the comment in
      `tests/test_acceptance_srm660c.py` and the running text in
      `docs/milestones/v0.2.md` if any raw digits are quoted
- [ ] Regression test: a known-collinear pair (e.g. zero-shift ~ sample
      displacement freed together) now trips the 0.98 guard, and the returned
      correlation matrix has unit diagonal
- [ ] Re-measure QPA σ(W); confirm no acceptance tolerance regresses and
      update quoted digits in records
- [ ] Update/delete the `esd-berar-lelann-conditioning` memory note

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_srm660c.py tests/test_qpa.py tests/test_v02_core.py -q
.venv/bin/python -m pytest -q
```

Measured: reported SRM 660c `a`-esd is the BL-inflated value (≈24–25×10⁻⁶,
still < 5×10⁻⁵); the returned correlation matrix has unit diagonal; the
correlation guard trips on a deliberately collinear pair.

## References

- Bérar & Lelann (1991) J. Appl. Cryst. 24, 1 — serial-correlation esd
  inflation.
- Andreev (1994) J. Appl. Cryst. 27, 288 — bias-corrected figure of merit
  (cited as the known conservatism, formula not reproduced).

## Handover log

- **2026-07-24** — created during v0.4 planning. Root cause traced and
  **numerically verified**: `corr = cov/outer(diag,diag)` normalises by the
  BL-inflated diagonal ⇒ correlation diagonal = 1/BL² (measured 0.0372 at
  BL = 5.18), which cancels BL exactly in `stderr_physical` (measured: equals
  the raw esd to floating-point equality) and deflates the guard's ρ by BL².
  Decision recorded: inflate/fix-the-placement.
