# WP-1454 — `auto_background`'s choices survive the fit

Milestone: unscheduled · Status: ⬜
Depends on: —
Priority: P2 2026-09-24 — the default background of every P-spline fit: its stiffness follows the intensity unit, its knots ignore the fitted range, and every preset frees an air term it declined; the flexible side is derived silent, P1 if task 3 measures a structural answer moving with nothing fired

## Goal

`auto_background` makes three choices, and each one holds through the fit.
The smoothness penalty is equally stiff whatever unit the intensities are
in. The knots span the range the fit uses. An air-scatter term it left off
stays off.

## Context

**The evidence.** A 2026-09-24 transcript review read an agent session that
drove rietx at `644dff84` through the skill. The data were a private
synchrotron in-situ series of 48 patterns: `in-situ series 1` in the private
`yue-here/rietx-corpus-map`, which says where the data, the scripts and the
transcript live. Quote only what the runs did (CONTRIBUTING, WP-1450). All
three choices below failed there, and the first and third are measured
again here on public data.

### 1. The penalty's units

`BackgroundPSpline`'s penalty rows are √λ·D₂c
(`src/rietx/model/forward.py:3022-3025`). The coefficients c are in
intensity units, while every data row is divided by σ. Multiply y and σ by
k: the data rows do not change, the penalty rows scale by k, and the
effective λ scales by k². With Poisson σ the relative stiffness grows with
the count level instead. The default is `lambda_smooth = 1.0`
(`src/rietx/schemas/instrument.py:1077`), and `auto_background` passes 1.0
(`src/rietx/background/auto.py:49`).

Measured 2026-09-24 on 11-BM NAC (`tests/data/11BM_NAC.fxye`), starting from
the walkthrough's converged model. Intensity, σ and every phase scale are
multiplied by k, and the default Rietveld plan runs over 2-24°:

```python
base, ref0, _, _ = nac_11bm.run()            # examples/nac_11bm.py
for k in (1e-4, 1e-2, 1.0, 1e2):
    data = base.model_copy(update={"intensity": list(np.asarray(base.intensity) * k),
                                   "sigma": list(np.asarray(base.sig()) * k)})
    structure = ref0.fitted_structure.model_copy(deep=True)
    for p in structure.phases:
        p.scale.value *= k
    ins = ref0.fitted_instrument.model_copy(deep=True)
    ins.background = bk = rx.auto_background(data)       # 8 knots, λ = 1
    for c in bk.coefficients:
        c.value = float(np.percentile(data.intensity, 5))
    ref = rx.Refinement(structure, ins, history=False)
    r = ref.fit(data, two_theta_limits=(2.0, 24.0), telemetry=False)
    c = [p.value for p in ref.fitted_instrument.background.coefficients]
    print(k, r.statistics.rwp, np.abs(np.diff(c, 2)).max() / k)
```

| k | max \|D₂c\| / k | Rwp |
|---|---|---|
| 10⁻⁴ | 184 | 0.09335 |
| 10⁻² | 171 | 0.09335 |
| 1 | 25.9 | 0.09370 |
| 10² | 0.0046 | 0.09404 |

A unit change alone takes the background from unpenalised to a straight
line. NAC's own count level sits in the transition. The weight fractions
agree to 0.01 wt % at every k, because NAC's background is smooth and 8°
knots cannot reach a reflection. So this pattern shows the mechanism and not
its cost.

On the private series the default gave a straight line across the fitted
4-40°, at Rwp 0.18. Lowering λ by 10⁴, refining the knots to 0.75° and
confining them to the fitted range gave Rwp 0.028. The agent worked out
λ ≈ 1/σ² for itself and wrote it into its own helper.

The other direction is derived, not measured. Data in small units
(normalised, or a rate with an esd column) make the penalty vanish. A fine
spline can then absorb broad Bragg intensity. That is the failure
`BackgroundPSpline` exists to prevent (its docstring). Root CLAUDE.md
§ background flexibility says what it costs: ADPs biased up and scales, and
so fractions, biased down, while Rwp improves.

### 2. The fitted range

`auto_background` takes its knot range from `diagnose(data)`, which is the
whole file (`auto.py:47-49`). The function takes no limits argument. On the
private series the fit stopped at 40° while the knots ran to 92°, so the
coefficients past 40° were held by the penalty alone. They extended the
straight line to negative values at about 75-92°, where there were no data.
Inside the fitted range the background stayed positive.

### 3. The air term

The air-scatter term defaults to off: `Parameter(value=0.0, min=0.0,
transform="softplus")`, with `vary` False
(`src/rietx/schemas/instrument.py:1078`). `auto_background` turns it on only
when `diag.air_scatter_gain > AIR_SCATTER_TRIGGER`. But all seven presets
free `instrument.background.*` (`src/rietx/strategy/staged.py:284-431`),
and that glob includes `.air`. A plan replaces the vary flags (WP-1208), so
the declined term is freed on every fit. This is issue #211's shape, which
WP-1435 fixed for a caller's own holds.

The cost shows in the diagnostics. `check_guards` appends a
`HIGH_CORRELATION` finding for every pair above `correlation_guard` (0.98),
and a `FLAT_DIRECTION` finding as well at or above `FLAT_DIRECTION_RHO`
(1 − 5·10⁻⁴) (`staged.py:1544-1561`). One flat direction across n columns
can therefore produce n(n−1) rows. Measured 2026-09-24 on NAC, from the same
walkthrough model, with `BackgroundPSpline.for_range(1.9, 24.1, …)` seeded at
the 5th percentile:

| knots | λ | coefficients | rows | background-only rows | Rwp |
|---|---|---|---|---|---|
| 8° | 1 | 6 | 2 | 1 | 0.09366 |
| 2° | 10⁻⁴ | 14 | 1 | 0 | 0.08628 |
| 0.75° | 10⁻⁴ | 33 | 1075 | 1074 | 0.08484 |

At 0.75° the 1074 rows are 561 `HIGH_CORRELATION` and 513 `FLAT_DIRECTION`.
561 is every pair among the 34 background parameters. The same fit with
`ref.hold("instrument.background.air")` gives **zero** correlation rows, at
Rwp 0.08484 both ways. So the whole flood is one direction: the 1/(2θ)
column inside the span of a fine spline.

On the private series, 1643 of 1644 rows on one fit were about background
coefficients alone. The agent's first completed fit printed about 8 kB,
most of it these rows, and the agent then dropped every background-only
row. With them it lost sight of `CAPILLARY_OFFSET_UNAVAILABLE`, which asked
for a goniometer radius on 48 of 48 patterns of each final chain. The
instrument file states a secondary radius (TOPAS `Rs`), which is probably
that number (WP-1455).

### The skill

`SKILL.md:77-78` says `rx.auto_background(data)` "does the right thing".
`references/judging.md` and `references/batch.md` quote `worst_absorption`
only as 0.46 against 0.08. The guard is `BACKGROUND_ABSORPTION_GUARD = 0.25`
(`staged.py:878`), and no skill file names it.

### What a fix moves

A new penalty scale moves every converged P-spline fit. Holding a declined
air term moves every fit whose plan freed it, even where Rwp does not
change. Which goldens declare a P-spline, and what each one does, is a
decision to take here (tests/CLAUDE.md).

**Prior art, not yet read.** Eilers & Marx (1996) choose λ against the data
by cross-validation or AIC. Check how GSAS-II and TOPAS scale a smoothness
penalty on a background before choosing.

## Non-goals

- Choosing λ per pattern by cross-validation. That is a selector, and WP-1130
  closed on a background selector's gate.
- The background level (WP-1130).
- Changing `correlation_guard` or `FLAT_DIRECTION_RHO`.

## Tasks

- [ ] The air term. Decide how a declined term stays off, and write the
      decision here. The candidates: presets free `instrument.background.c*`,
      plus the air term only where the model turned it on; or the declined
      term is held the way a caller's hold is, which needs a seam because a
      model carries no holds. Land it, and measure NAC at 0.75° again.
- [ ] If any fit in the fast selection still reports one degeneracy as many
      pair rows after that, file a WP to group them into one finding. The
      candidates are connected components of the thresholded pairs, or the
      flat eigen-directions of the Jacobi-scaled normal matrix, and every
      reader of the rows is audited first (WP-1103). If none does, record
      the zero here.
- [ ] Measure the flexible side of the penalty. Take a public pattern with
      broad reflections, scale it down and fit with fine knots. Record
      whether a Biso or a fraction moves, and whether `background_absorption`
      or any guard fires. This sets the priority.
- [ ] Decide the penalty's scale, and write the decision here. Either divide
      the penalty rows by one σ frozen at compile (the median over the fitted
      channels), which makes λ dimensionless for every caller; or keep the
      units and derive λ in `auto_background` from the counts, which fixes
      only the helper. Land it, with the goldens' decision recorded.
- [ ] `auto_background` spans the fitted range: take `two_theta_limits`, or
      read the range the fit will use.
- [ ] Tests. Unit invariance: at k ∈ {10⁻³, 1, 10³} the fitted background
      divided by k agrees within the spread the same fit shows when
      restarted, measured first and never chosen (tests/CLAUDE.md § Budgets
      in tests). And NAC at 0.75° knots: no correlation row names a declined
      air term.
- [ ] Skill: the `SKILL.md:77` sentence; the 0.25 threshold beside the 0.46
      example; and the seed note in `references/judging.md`, if the new scale
      changes what a seed means.

## Acceptance

The table in § 1, rerun, shows one row four times. NAC at 0.75° knots
reports no air-term correlation rows.

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_background_measured.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Eilers, P. H. C. & Marx, B. D. (1996). *Statistical Science* **11**, 89.
- WP-1055 (background evidence), WP-1130 (the background level, closed),
  WP-1309 (a measured background's σ), WP-1208 and WP-1435 (a plan replaces
  vary flags; a hold outranks a glob), issue #211, WP-1103 (the reader
  audit).

## Handover log

- **2026-09-24** — created from the review of an agent session on a private
  series. Both NAC tables were measured the same day, at `2d42303a`. The
  private-series numbers were re-read from that session's saved results.
  Next: the air term, then the flexible-side measurement.
