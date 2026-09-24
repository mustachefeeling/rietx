# WP-1455 — a spline penalty in the pattern's units

Milestone: unscheduled · Status: ⬜
Depends on: —
Priority: P2 2026-09-24 — the default background of every P-spline fit changes with the intensity unit; the stiff side shows in GoF, the flexible side is derived silent; P1 if task 1 measures a structural answer moving with nothing fired

## Goal

The P-spline smoothness penalty means the same thing whatever unit the
intensities are in. `auto_background` gives the same fitted background on a
pattern and on that pattern times 1000. Its knots span the fitted range
rather than the whole file.

## Context

**The mechanism.** `BackgroundPSpline`'s penalty rows are √λ·D₂c
(`src/rietx/model/forward.py:3022-3025`). The coefficients c are in
intensity units, while every data row is divided by σ. Multiply y and σ by
k: the data rows do not change, the penalty rows scale by k, and the
effective λ scales by k². With Poisson σ the relative stiffness grows with
the count level instead. The default is `lambda_smooth = 1.0`
(`src/rietx/schemas/instrument.py:1077`), and `auto_background` passes 1.0
(`src/rietx/background/auto.py:48`).

**Measured 2026-09-24 on a public pattern.** The pattern is 11-BM NAC
(`tests/data/11BM_NAC.fxye`), started from `examples/nac_11bm.py`'s
converged model. `auto_background` chose 8 knots at λ = 1, and every
coefficient was seeded at the 5th percentile of y. Intensity, σ and every
phase scale were multiplied by k. The fit used the default Rietveld plan
over 2-24°.

| k | max \|D₂c\| / k | Rwp |
|---|---|---|
| 10⁻⁴ | 184 | 0.09335 |
| 10⁻² | 171 | 0.09335 |
| 1 | 25.9 | 0.09370 |
| 10² | 0.0046 | 0.09404 |

A unit change alone takes the background from unpenalised to a straight
line. NAC's own count level sits in the transition. The weight fractions
agree to 0.01 wt % at every k, because NAC's background is smooth and 8°
knots cannot reach a reflection. So this pattern shows the mechanism and
not its cost. The script is short enough to rebuild from this paragraph.

**Private evidence, fit qualities only.** This is the session WP-1453
describes. On a high-count synchrotron series the default left a
straight-line background that went negative at high angle, with Rwp 0.18.
Lowering λ by 10⁴ and refining the knots to 0.75° gave Rwp 0.028. The agent
worked out λ ≈ 1/σ² for itself and wrote it into its own helper.

**The other direction is derived, not measured.** Data in small units
(normalised, or a rate with an esd column) make the penalty vanish. A fine
spline can then absorb broad Bragg intensity. That is the failure
`BackgroundPSpline` exists to prevent (its docstring). Root CLAUDE.md
§ background flexibility says what it costs: ADPs biased up and scales, and
so fractions, biased down, while Rwp improves.

**The fitted range.** `auto_background` takes its knot range from
`diagnose(data)`, which is the whole file (`auto.py:47-49`). The function
takes no limits argument, so a fit with `two_theta_limits` leaves every
coefficient beyond the limit held by the penalty alone.

**The skill.** `SKILL.md:77-78` says `rx.auto_background(data)` "does the
right thing".

**What a fix moves.** Any change to the penalty's scale moves every
converged P-spline fit. Which goldens declare a P-spline, and what each one
does, is a decision to take in the WP (tests/CLAUDE.md).

**Prior art, not yet read.** Eilers & Marx (1996) choose λ against the data
by cross-validation or AIC. Check how GSAS-II and TOPAS scale a smoothness
penalty on a background before choosing.

## Non-goals

- Choosing λ per pattern by cross-validation. That is a selector, and WP-1130
  closed on a background selector's gate.
- The background level (WP-1130).

## Tasks

- [ ] Measure the flexible side. Take a public pattern with broad
      reflections (the broad-peak LaB₆ case in `references/judging.md`, or
      another public set), scale it down, and fit with fine knots. Record
      whether a Biso or a fraction moves, and whether
      `background_absorption` or any guard fires. This sets the priority.
- [ ] Decide the scale, and write the decision here. The two candidates:
      divide the penalty rows by one σ frozen at compile (the median over
      the fitted channels), which makes λ dimensionless for every caller; or
      keep the units and derive λ in `auto_background` from the counts,
      which fixes only the helper.
- [ ] Land it, with the goldens' decision recorded.
- [ ] `auto_background` spans the fitted range: take `two_theta_limits`, or
      read the range the fit will use.
- [ ] Tests: unit invariance. At k ∈ {10⁻³, 1, 10³} the fitted background
      divided by k agrees to 1e-6 relative, on NAC and on a synthetic
      pattern with a structured background.
- [ ] Skill: the `SKILL.md:77` sentence, and the seed note in
      `references/judging.md` if the scale changes what a seed means.

## Acceptance

The unit-invariance test passes. The table above, rerun, shows one row
repeated four times.

```sh
.venv/bin/python -m pytest tests/test_background*.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Eilers, P. H. C. & Marx, B. D. (1996). *Statistical Science* **11**, 89.
- WP-1055 (background evidence), WP-1130 (the background level, closed),
  WP-1309 (a measured background's σ).

## Handover log

- **2026-09-24** — created from the review of an agent session on a private
  series, where the default left a straight-line background. Measured the
  mechanism the same day on public NAC (the table above), at `2d42303a`.
  Next: task 1, the flexible side, which sets the priority.
