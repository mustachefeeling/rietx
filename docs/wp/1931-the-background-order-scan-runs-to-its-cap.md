# WP-1931 — the background order scan runs to its cap

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1542 soft: the same `auto_background` call and its seed default)
Priority: P3 2026-10-08 — the selector returns its cap on both shipped 11-BM standards and says nothing; measured harmless there (bias ≤ 0.7 % of a background ≤ 0.4 % of the peak), so the cost is a choice that reads as made and was not

## Goal

`select_chebyshev_order` says when its scan ran to `max_order` instead of
stopping, and the co-refined P-spline's stiffness λ is chosen from the data
by a stated criterion (REML proposed), with the effective degrees of freedom
reported beside it.

## Context

Issue #833 (mustachefeeling, 2026-10-08).

**The selector** (`background/select.py:75`). It fits Chebyshev orders 2 to
`max_order` on peak-masked channels (`peak_mask`, net ≤ 3σ over an arPLS
baseline) and keeps the BIC minimum, stopping early once the Durbin-Watson d
reaches `dw_stop` = 1.8. `auto_background(kind="chebyshev")` calls it with the
default `max_order` = 16 (`background/auto.py:87`). The P-spline branch never
calls a selector: it builds `BackgroundPSpline.for_range(…, lambda_smooth=1.0)`
(`auto.py:106`), λ weighed against the data at compile (root CLAUDE.md, the
background clause; WP-1454).

**What was measured** (#833, `main` at `a3f9140a`, macOS arm64):

| file | range | masked channels | `max_order` | selected | stopped by DW | d over the scan |
|---|---|---|---|---|---|---|
| `11BM_Si640c.xy` | 8-30° | 20 540 | 16 | 16 | no | 0.43-0.86 |
| `11BM_Si640c.xy` | 8-30° | 20 540 | 32 | 32 | no | 0.43-1.02 |
| `11BM_LaB6_660a.fxye` | 4-30° | 47 062 | 16 | 16 | no | 0.75-0.93 |
| `11BM_LaB6_660a.fxye` | 4-30° | 47 062 | 32 | 31 | no | 0.75-0.98 |

Two causes: the BIC gain per term (50-800) dwarfs the penalty ln m ≈ 10 at
20 000-47 000 channels, and the masked residual's serial correlation comes
from profile misfit, so d stays under 1.8 at any order. On these two
standards the choice is harmless: synthetic replicates from each converged
fit (4 per arm, Gaussian noise at the file's σ) give a background bias at the
12 strongest peaks of at most 0.7 % of a background that is itself at most
0.4 % of the peak, and |z| on scale, Biso, zero and cell of 0.4-1.1 at both
orders (Bérar-Lelann factor divided out). Where the choice does matter is
WP-1055's over-flexible fixture: Biso 0.958 / 0.000 against a true 0.5 while
every agreement index improved.

**Checked against the tree at `a3f9140a`** (this worktree's `[dev]` venv,
macOS arm64): the Si640c rows reproduce, `selected` 16 and 32 at
`max_order` 16 and 32, `stopped_by_whiteness` False both times, on 20 542
masked channels (the issue's 20 540; the probe's 8-30° crop was inclusive at
both ends). The LaB₆ rows were not re-run.

**The proposal** (#833):

1. `select_pspline_lambda(data, …)`: λ by REML on the penalised linear
   problem at the Le Bail stage, where the background competes only with free
   intensities. The second-difference penalty is the random-effects
   precision, so in the Gaussian linear case the criterion is exact and needs
   one eigendecomposition of the penalty in the data metric.
   `FitReport.background` carries tr(H), the effective degrees of freedom.
2. `select_chebyshev_order` emits `BACKGROUND_ORDER_AT_CAP` when it returns
   `max_order`.
3. `auto_background(seed=True)` as the default. That is #725's proposal, and
   WP-1542 owns it (its Inherited, 2026-10-05 and this triage's entry).

**Prior art.** Inside the field, GSAS, GSAS-II, TOPAS and FullProf all leave
the background order to the user. Outside it, a smooth nuisance curve is a
penalised spline with its smoothing parameter chosen by REML or marginal
likelihood (Wood 2011); Reiss & Ogden (2009) show REML under-smooths less
often than GCV (Craven & Wahba 1979, the classical fallback); the penalised
fit's Bayesian covariance has whole-curve coverage (Marra & Wood 2012).
**Licensing:** mgcv, the reference implementation of Wood's method, is
GPL, so this is built from the papers only.

**What a session must square first.** WP-1454 made λ a number weighed
against the data (√(λ·m)/σ̄, frozen at compile), and WP-1055 measures the
too-flexible side as `BACKGROUND_ABSORPTION`. A data-chosen λ changes what
every P-spline fit frees by default, so `FitReport.background`'s absorption
table on the acceptance suites is read before and after. Choosing λ at the Le
Bail stage and then holding it through the Rietveld stages is a protocol
claim the proposal makes and has not measured.

### Inherited

(empty)

## Non-goals

- The seed default (#725, #833 item 3): WP-1542.
- A too-low background left at its seed under Le Bail: WP-1542.
- Changing the arPLS mask or `select_arpls_lambda`.

## Tasks

- [ ] `BACKGROUND_ORDER_AT_CAP` from `select_chebyshev_order` (and through
      `auto_background(kind="chebyshev")`), naming the cap and the last d.
      Independently landable.
- [ ] Measure REML's λ on Si640c, LaB₆ 660a and WP-1055's fixture before
      building the selector: interior or not, tr(H), and Biso on the fixture.
- [ ] `select_pspline_lambda`, with its reference in the docstring, and the
      decision whether `auto_background` calls it by default (the
      maintainer's).
- [ ] tr(H) on `FitReport.background`.
- [ ] Tests, and the acceptance suites' `BACKGROUND_ABSORPTION` table before
      and after, with obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: the new code's `references/judging.md` row; a SKILL.md line only
      if the default changes.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_auto_background_seed.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The selected λ is interior on both standards and on WP-1055's fixture, whose
Biso lands within 2 esd of 0.5 at that λ. Replicate coverage on the two
standards does not move. `select_chebyshev_order` at its default on Si640c
emits `BACKGROUND_ORDER_AT_CAP`.

## References

- Issue #833; #725 (WP-1542).
- WP-1055 (`FitReport.background`, the over-flexible fixture), WP-1454 (λ
  against the data), WP-1309.
- Wood, S. N. (2011). *J. R. Statist. Soc.* B 73, 3-36,
  doi:10.1111/j.1467-9868.2010.00749.x.
- Reiss, P. T. & Ogden, R. T. (2009). *J. R. Statist. Soc.* B 71, 505-523,
  doi:10.1111/j.1467-9868.2008.00695.x.
- Marra, G. & Wood, S. N. (2012). *Scand. J. Statist.* 39, 53-74,
  doi:10.1111/j.1467-9469.2011.00760.x.
- Craven, P. & Wahba, G. (1979). *Numer. Math.* 31, 377-403.

## Handover log

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #833).
  Checked against the tree at `a3f9140a`: the Si640c rows reproduce (16 and
  32 selected at caps 16 and 32, never stopped by DW). No open WP owns the
  order or λ choice: 1454 and 1055 are closed, 1460 is about a declared air
  term beside the P-spline, 1542 owns the seed half (item 3, folded there).
