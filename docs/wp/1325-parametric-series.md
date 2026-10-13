# WP-1325 — parametric series: a parameter as a function of the series axis

Milestone: unscheduled · Status: 🔄 2026-10-13 — claimed by @yue-here (Claude session); scoping the declaration first
Track: Candidates — named on a use case, not yet on a measurement
Depends on: — (1119 soft: a named coefficient is a named variable)
Priority: P3 2026-09-23 — named on a use case, not on a measurement; per-pattern fits cover it

## Goal

A series can refine a parameter as a declared function of the series axis —
temperature, time, composition — across all its patterns in **one joint
residual**, with the function's coefficients as the refined parameters and
their esds from the joint covariance (Stinton & Evans 2007, "parametric
Rietveld"). A thermal-expansion coefficient, a transition temperature or a
rate is then a *measured* number with an esd, rather than a line fitted
afterwards to a trajectory of per-pattern values whose esds are each
conditional on their own pattern.

## Context

**This is a candidate.** It is on the roadmap because of a use case, not a
measurement, and its first task is the measurement that decides whether it
opens. It was named during the 2026-09-01 roadmap reorder as the gap between
three things the package already has.

- `sequential.py` chains N fits by warm start and reports **trajectories**;
  WP-1305's fourth deliverable prints a parameter against the series axis.
  That is the *output* whose *input* form this WP is: today the function is
  fitted to the trajectory, so every point's esd is conditional on its
  pattern's other parameters and the chain is path-dependent by construction
  (`direction="both"` flags it).
- `multi.py` stacks patterns into **one joint residual** (multi-histogram,
  WP-0308). That is the seam a parametric fit needs: N patterns, one θ.
- The tie machinery is affine, p = C·θ + d with constant C (WP-0301, WP-1070).
  A parametric tie that is *linear in its coefficients* — a(T_k) = a₀ + a₁·T_k
  on pattern k — is exactly an affine tie per pattern with C_k = [1, T_k], so
  the linear case needs **no new Jacobian branch**: `_column_extras` reads
  the reach off C, and the whole-model FD column covers what a branch does
  not claim. Nonlinear forms (Arrhenius, a critical exponent) are the same
  fence as WP-1119's `Parameter.expr`.
- Issue #212's conserved elemental ratio across a reduction series is a
  parametric constraint in disguise: linear in the phase scales, constant
  across the series axis.

**Prior art, concepts only.** TOPAS's parametric refinement (Stinton & Evans
2007) refines the function's coefficients directly against all patterns;
GSAS-II's sequential refinement fits a function to the sequential *table*
afterwards, which is the weaker form the package already has. The design
decision this WP owes is where the declaration lives — a `SeriesTie(path,
function, axis, coefficients)` beside `RefinementState.ties` is the shape that
keeps `Refinement._ties` the one authority for what is the user's.

**What the measurement has to say.** On the 68-pattern ZrMo₂O₈ ramp (the
v1.1 trigger series): the coefficient and esd from a line through the
trajectory, against the same coefficient from a joint fit with a = a₀ + a₁·T
over a window of patterns. If the two coefficients agree within an esd and
the joint esd is not smaller, the trajectory form is enough and this WP closes
as a finding. Cost is the second number: a joint residual over N patterns is
N× the rows, and WP-1125 measured that profiling a linear block buys no
evaluation, so the wall-clock ratio against the chain is reported, not
assumed.

### Inherited

- **2026-10-13, from user feedback (an outside lab, by email to the
  maintainer): the first use case from outside the package, and it is 2-D
  across many specimens, not 1-D across one.** The lab runs rietx and TOPAS
  side by side on the same combinatorial-library datasets. They report rietx
  as strong on simple-to-medium problems. On the hard ones (gradual, broad,
  interfering peaks) they rely on TOPAS: they parametrise values as
  **polynomial surfaces** over the library and refine the surface
  coefficients against all datasets at once, especially for weak or broad
  features. In their words, it is "the only way" to get consistent, smoothly
  evolving models across a library, and to decouple measurable quantities
  from how the diffuse features are modelled. Four things this changes for
  the design.
  (1) **The axis is a vector, not a scalar.** A surface over composition
  (x, y) is still linear in its coefficients, p_k = Σ_j c_j·φ_j(x_k, y_k),
  so the affine C covers it unchanged. The declaration should therefore take
  per-pattern basis values (or an n-D axis) rather than one series axis, or
  a 1-D `SeriesTie` will need reshaping later. The "no library of physical
  models" non-goal still holds, since the caller supplies the basis.
  (2) **Many specimens, not one crystal.** `SharingMap`'s default is "one
  specimen, one crystal", and `MultiParameterTable` copies a single starting
  `Structure` into every histogram. A library varies in cell, occupancy and
  broadening from specimen to specimen, so it needs per-pattern starting
  values, with the surface tie as a third choice between shared and
  per-histogram.
  (3) **The targets include per-histogram paths.** Weak or broad features
  live in `instrument.*` (background, `extra_components`), which the default
  map already makes per-histogram. So the tie has to reach scoped
  `hist.{h}.` paths, not only shared ones.
  (4) **Priority.** The header's "per-pattern fits cover it" is the claim
  this report disputes for libraries. It is still a use case, not a
  measurement, so the first task stands; a library dataset, if one can be
  had, would be the second series to measure on. Re-rating the priority is
  left to the maintainer. (The same email names spherical-harmonics texture
  as their other gap. That is the v2 fence, not this WP.)
- **2026-10-11, from the issue triage: issue #212's restraint row is
  [1942](1942-a-soft-restraint-on-a-sum-across-phases.md), and #349's three
  exports went with it.** The two entries that said nobody had cut it (the
  2026-09-04 one from 1119 and the 2026-09-21 one about #349) are replaced by
  this line. The row stays one instance of a parametric constraint, so this
  WP keeps citing #212; the seam, the measured workaround and the exports
  live in 1942.
- **2026-09-04, from [1119](1119-named-variables.md): the soft dependency is
  discharged, and one piece of your scope is now unowned.** A named coefficient
  is a named variable and that object exists: `Refinement.add_variable(name,
  value, min=, max=, transform=)` gives `vars.<name>`, an ordinary dot-path that
  `parameters()` lists, `set_vary("vars.*")` frees and a fit refines with an
  esd; `Refinement.tie` takes `{path: coefficient}` so one variable can be
  written in terms of others; and a variable is persisted in
  `RefinementState.variables`, so a checkout restores it. Two things to carry
  across. (1) **A variable's bounds are the only bounds the solve sees** — a
  tied dependent is not a free column, so a coefficient other than 1 can put it
  outside its own `min`/`max` and the failure is a pydantic error naming
  nothing (skill `references/surprises.md` § 8.22). A parametric coefficient
  driving several patterns' parameters has to be bounded for its dependents.
  (2) **The linear relation is exact and the nonlinear one does not exist**:
  `p = C·θ + d` is what the constraint block computes, so a coefficient times a
  series axis is free, and anything with a product or a power of the axis in it
  is outside the machinery entirely.
- **2026-09-02, from the magnetic scattering track
  ([1329](1329-moment-in-a-series.md)): a second use case, named, not
  measured.** An ordered moment through T_N is an order parameter, m ∝
  (1 − T/T_N)^β, nonlinear in β and T_N, so it is the `Parameter.expr` fence
  rather than this WP's linear form; 1329 delivers the |m|(T) trajectory
  with held patterns marked and leaves the exponent to the user. If this
  WP's measurement on the ZrMo₂O₈ ramp says the joint form is worth having,
  the moment trajectory is the second series to measure it on.

## Non-goals

- A library of physical models. One declared function, linear in its
  coefficients, is the deliverable.
- Replacing the chain: it stays the exploratory tool and the seed.
- Nonlinear functions of the axis (fenced with `Parameter.expr`, WP-1119).

## Tasks

- [ ] The measurement above, on the ZrMo₂O₈ ramp: trajectory-line coefficient
      and esd against a joint a₀ + a₁·T fit over 10 patterns, and the
      wall-clock ratio. Decide open / close-as-finding on it.
- [ ] **Survey the prior art for declaring a parametric model, before
      `SeriesTie` takes a shape.** The goal is a declaration that is easy to
      write and hard to get wrong, because a **self-driving lab** will write
      it: an orchestrator or agent, from a composition database, with nobody
      reading the fit as it runs.
      Read four families of precedent, concepts only (licensing rule):
      - **Crystallography:** TOPAS `prm` equations and parametric macros
        (Stinton & Evans 2007, user docs only); GSAS-II's sequential and
        parametric fits; FullProf's multi-pattern constraints.
      - **General fitting:** lmfit's `Parameters` with `expr`.
      - **Model-formula languages** (Wilkinson & Rogers 1973; patsy and
        formulaic): how `1 + x + y + x:y + I(x**2)` names a basis, and how a
        design matrix is built from per-sample metadata.
      - **Autonomous-experimentation stacks:** how a closed-loop campaign
        describes samples and their coordinates to an analysis step.
      Then answer the questions the design owes:
      1. **Data, not code.** Can the declaration be JSON-round-trippable
         state (the `extra_components` "state, never code" rule), so an
         orchestrator can write it, a history node can store it and a replay
         can rebuild it?
      2. **Where the axis lives.** How are per-pattern coordinates attached:
         beside each `PatternData`, or in the declaration?
      3. **Refusals before a solve.** Which mistakes are refused, each naming
         its fix?
         - a design matrix with lower rank than its basis (too few, or
           collinear, compositions);
         - a pattern with no coordinate;
         - a coefficient bound that its dependents violate (the 1119 hazard
           above);
         - a target that is held, `mode_fixed` or symmetry-tied.
      4. **Conditioning.** How are raw compositions centred and scaled, so
         the coefficients' esds are not an artefact of the units?
      5. **A growing campaign.** How does the fit behave when patterns arrive
         one at a time, and when one is quarantined (WP-1051's rule)?
      Write the comparison and the chosen shape into this WP before the next
      task builds it.
- [ ] `SeriesTie` on the series surface, resolved into `multi.py`'s joint
      table as per-pattern affine ties; bit-identical to `refine_multi` when
      the function is a constant.
- [ ] esds of the coefficients from the joint covariance, marked unmeasured
      where a pattern contributes no gradient (WP-1110 item 14's rule).
- [ ] `SeriesResult.summary(deliverable="series")` prints the coefficients
      beside the trajectory it already prints.
- [ ] Manual Part 1 `using/series.md`; Part 2 the equation with its *Source*
      line; the skill's series reference.
- [ ] Tests on a synthetic ramp with a known a(T): a₁ within one esd of truth,
      the esd no larger than the trajectory-line's; obs/calc/diff PNGs to
      `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_multi_histogram.py tests/test_parametric_series.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95 —
  parametric Rietveld refinement.
- WP-0308 (the joint residual), WP-0505 / WP-1051 / WP-1127 (the chain),
  WP-1305 (the series deliverable), WP-1119 (named variables), issue #212.

## Handover log

- **2026-10-13 (reconstructed post hoc)** — two planning commits landed on
  `main` this morning without a handover entry, and the session-start hook
  flagged the WP for repair. Neither one changed code or measured anything.
  Together they say this WP's first outside user wants a 2-D surface across a
  combinatorial library rather than a 1-D line through a ramp. They also say
  the declaration has to be designed for an automated writer (a self-driving
  lab) before it is built.
  - `a9a577e` added the 2026-10-13 `### Inherited` entry from the outside
    lab's email: the axis is a vector, there are many specimens, targets
    include `hist.{h}.` paths, and the priority claim is disputed.
  - `b23bb9a` added the prior-art survey task (second in Tasks) with its five
    design questions.
  - The diff does not say which session wrote them or why they were not
    handed over. Both touch only this file.

  Next: the survey task, then the measurement.
- **2026-09-01** — created as a candidate during the roadmap reorder; carries
  a use case and a seam, no measurement. First task is the measurement.
