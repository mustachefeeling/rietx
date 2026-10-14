# WP-1965 — a parametric law declared by formula, condition and glob

Milestone: unscheduled · Status: ⬜
Track: Candidates — named on a use case, not yet on a measurement
Depends on: 1325 (the declaration this lowers onto)
Priority: P3 2026-10-14 — writing the lists by hand is the workaround, and no user has asked yet

## Goal

A parametric law can be declared in the notation statisticians already use.
Its terms come from a formula string, its subset from a condition on the
coordinates, and its target from a glob. Each form is lowered to today's
`ParametricTie` when the declaration is resolved, so the stored declaration
keeps its current data form.

## Context

Filed as a stub on 2026-10-14, from a review of WP-1325's API against prior
art, at the maintainer's request to fold the review's findings into 1325 or
follow-up WPs. These three share one seam (`schemas/parametric.py` and
`params.parametric.resolve_parametric`), one decision (how a declaration is
spelled) and a lower priority than 1325's correctness tasks. So they are one
WP, apart from 1325.

### A formula for the terms

Today a polynomial's terms are nested lists: `[[], ["T"], ["T", "T"]]` is
a + b·T + c·T². R, patsy, formulaic and statsmodels all spell a basis as a
Wilkinson formula (Wilkinson & Rogers 1973). WP-1325 § The shape already
allowed a formula as input sugar, "parsed to that form by a closed grammar,
never `I()`", and nobody built it.

WP-1119 declined an expression parser for linear ties, on four grounds. Each
needs an answer here.

1. **A second parser for one language.** `Parameter.expr` is reserved for an
   arithmetic language. A Wilkinson formula names basis terms and does no
   arithmetic, so it is a different language. The overlap is `^` and `*`,
   below.
2. **A stored string joins `PROJECT_FORMAT_VERSION`.** Lower the formula at
   construction and never store it. The resolved declaration stores `terms`,
   as it does now.
3. **A silent failure mode.** This one binds. In R and patsy, `x*y` means
   `x + y + x:y`. Inside a formula, `x^2` (R) or `x**2` (patsy) is crossing
   to degree 2, and for one numeric column it is just `x`. A power needs
   `I(x^2)` or `poly(x, 2)`. A grammar that reads `x*y` as the product term
   alone, or `T^2` as a square, means something else to every statistician
   who types it. So either follow Wilkinson exactly, with a closed construct
   for powers, or refuse `*` and `^` and say why. Decide in the first task.
4. **Pre-empting the TOPAS boundary** that WP-1118 parked. A Wilkinson
   formula is not TOPAS syntax, so the risk is small.

### A subset by condition

`ParametricTie.patterns` is a list of indices into the patterns as passed,
and `design` rows follow the subset's order. A library that drops one bad
pattern shifts every later index, so every subset has to be rewritten by
hand. A phase field is also a region of composition, which a condition on the
coordinate columns states directly (`T < 800`, `x between 0.1 and 0.3`).
Tidy-data practice keys rows by a sample ID. CAMEO keys each sample by
composition, position and process (WP-1325 § Prior art).

`PatternData` has no label field (`schemas/pattern.py`).
`HistogramResult.label` exists on the result side. Decide whether a label
column on `CoordinateTable` or a condition is the key.

Decide what is stored. Patsy's lesson, which 1325 applies to the reference
and scale, is that a coefficient's meaning must not move when patterns join.
Subset membership is different: a new pattern inside a phase field should
join that field's law. So storing the condition, and re-evaluating it at
each resolution, may be right here. A `design` basis keeps positional rows,
or needs a key per row.

### A glob for the target

1325's design said "targets as globs". The code takes one bare path, and
`ParametricTie._check` refuses a glob. An orthorhombic cell linear in T is
three declarations with three names. A glob would expand at resolution into
one declaration per matched path, each with its own coefficients.

- **Naming.** Coefficients are `vars.<name>_<j>`, and a name must be one
  identifier. An expansion needs a naming rule that cannot collide.
- **What a glob may match.** `phases.0.cell.*` on a cubic phase matches `b`
  and `c` (tied to `a`) and three locked angles, and each of those is refused
  as a target today. A blocked glob is reported, never silent (root
  CLAUDE.md § A hold), so the expansion skips them and says which.

### Inherited

- **2026-10-14, from [1325](1325-parametric-series.md) (seventh session,
  PR #977): a result now carries each law as resolved.**
  `RefinementResult.parametric_laws[k].tie` is the declaration with its
  reference and scale filled in, the form a refit passes back. A formula,
  condition or glob spelling should resolve to that same `ParametricTie`,
  so a result read back can be refitted whichever spelling declared it.

## Non-goals

- Storing a formula string. It is lowered at construction.
- Arithmetic inside a formula (`I()` beyond a closed power construct), and
  laws nonlinear in their coefficients:
  [1964](1964-a-nonlinear-law-through-the-derived-block.md).
- A pandas dependency. A condition reads `CoordinateTable` columns.

## Tasks

- [ ] Decide the formula grammar: Wilkinson exactly, with a closed power
  construct, or a refusal of `*` and `^`. Write the decision and its reason
  here.
- [ ] The parser, lowering to `terms`. Tests: every formula in
  `using/series.md` lowers to the hand-written terms, and every refusal
  names its fix.
- [ ] A subset by condition, or by label. Decide what is stored, and pin a
  dropped pattern by test: the law covers the same specimens afterwards.
- [ ] A glob target, expanded at resolution, with skipped paths reported.
- [ ] Manual: `using/series.md` § Declaring one shows the new forms beside
  the data form.
- [ ] Skill: the series reference's parametric row, or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_parametric_series.py tests/test_manual_api.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Wilkinson, G. N. & Rogers, C. E. (1973). *Appl. Stat.* 22, 392-399 —
  symbolic description of factorial models.
- Kusne, A. G. et al. (2020). *Nat. Commun.* 11, 5966 — CAMEO.
- WP-1119 § Decisions taken, 2026-09-04, item 4 (no expression parser for
  linear ties); WP-1325 § Prior art and § The shape.

## Handover log

- **2026-10-14** — Filed as a stub from a review of 1325's API against prior
  art. No open WP owned declaration syntax: 1325 owns the declaration and
  its correctness, and these three items are sugar over it at a lower
  priority. Next: the grammar decision.
