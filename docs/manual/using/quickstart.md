# One fit, end to end

Three objects go in and one comes out. A `PatternData` from `read_pattern`, a
`Structure` from a CIF, an `Instrument` describing the diffractometer; a
`RefinementResult` comes back.

<!-- api-doc: no-exec — it reads a pattern file the reader supplies -->
```python
import rietx as pr

data = pr.read_pattern("my_sample.xye")
structure = pr.Structure.from_cif("my_phase.cif")
instrument = pr.Instrument.debye_scherrer(wavelength=0.4139090)

result = pr.refine(data, structure, instrument)
print(result.status, result.statistics.rwp)
```

`refine` is the one-shot form. It discards the session, so its history
defaults to off — the object form below keeps one, and that is the form to
reach for the moment a fit needs more than one attempt.

## Free parameters in groups, in order

**Do not free everything at once.** The correlations between parameter groups
are severe, and a simultaneous release from a poor starting point walks into a
local minimum a staged release avoids. So a fit here is a *plan* of stages,
each run to convergence before the next group is freed, in the order McCusker
et al. (1999) set out.

`RefinementPlan` carries the presets, named by what they are for:

```python
import rietx as pr

pr.RefinementPlan.mccusker_default()      # scale+bkg -> zero -> cell -> W -> U,V,X,Y
pr.RefinementPlan.mccusker_structural()   # ... then coordinates, displacement, PO
pr.RefinementPlan.lab_bragg_brentano()    # ... with sample displacement, Ka2, FCJ axial
pr.RefinementPlan.lab_calibrate()         # instrument calibration, certified cell HELD
pr.RefinementPlan.lab_sample_refine()     # sample against a frozen calibrated instrument
pr.RefinementPlan.profile_only()          # Le Bail
pr.RefinementPlan.pawley_default()        # Pawley
```

`Refinement.fit` also takes a plan by name (`plan="mccusker_default"`), and
`PLAN_INFO` reports each preset's title, description and when to use it, so a
program can offer the choice without hard-coding a list.

**Which order, and why each rule is not negotiable, is the protocol's
subject, not this manual's.** Read
[`docs/AGENT_PROTOCOL.md`](https://github.com/yue-here/rietx/blob/main/docs/AGENT_PROTOCOL.md)
§2 for the turn-on order and the three ordering rules that carry more weight
than they look like — widths last with `W` before `U,V,X,Y`, the background
before anything that can imitate it, and the structure freed last.

## Structure-free first

The order that matters most is one stage earlier than any plan: **get the
peaks in the right places before asking a structure to explain their
intensities.** A Le Bail fit (`mode="lebail"`) refines the cell, the zero and
the profile with the intensities extracted per reflection rather than
computed, so it converges from a much worse start and tells you whether the
cell and profile are right *independently of whether the structure is*. Only
then is a Rietveld fit (`mode="rietveld"`, the default) being asked a fair
question.

It pays a second way. A Le Bail fit's report flags observed peaks the model
does not account for — an impurity phase shows up as unmatched peaks at
positions you can identify, before it has had a chance to distort a
structural refinement by being absorbed into a background or a width.

## The whole thing

This is `examples/nac_11bm.py`, run by the test suite on every push. It
refines Na₂Ca₃Al₂F₁₄ against APS 11-BM synchrotron data: Le Bail first, then
the CaF₂ impurity its report exposes, then Rietveld.

```{literalinclude} ../../../examples/nac_11bm.py
:language: python
:caption: examples/nac_11bm.py
```

Six things in it are worth naming, because they are the shape of every fit
after this one:

- **One `Refinement` is the session.** `Refinement.fit` can be called again;
  `Refinement.fitted_structure` and `Refinement.fitted_instrument` return the
  models as the last fit left them, ready to seed the next.
- **Every stage auto-commits a node**, so `Refinement.history` holds both
  refinements *and* the model edit between them. `Refinement.edit` is what
  makes adding the impurity a recorded move rather than a fresh start, and
  `RefinementTree.tag` names a node to come back to.
- **A plan is editable.** `plan.stages.append(pr.Stage("biso", [...]))` adds a
  displacement stage after the preset's, and `Stage` takes fnmatch globs over
  the parameter dot-paths (`phases.*.atoms.*.biso`).
- **`RefinementResult.parameter`** looks one parameter up by path, with its
  esd: `result.parameter("phases.0.cell.a").stderr`.
- **`RefinementResult.diagnostics`** is the channel for "your answer is wrong
  although Rwp is fine". Read it every time; [](report.md) says what the codes
  mean and what they do not.
- **`build_report`** turns the result into a `FitReport` — where the misfit
  is, what would fix it, and whether it is confident enough to say so.

## What you get back

`RefinementResult.status` says whether the solver converged;
`RefinementResult.statistics` carries the fit statistics, of which
`Statistics.rwp` and `Statistics.gof` are the two usually quoted, and
`Statistics.n_points`, `Statistics.n_free_parameters` and
`Statistics.esd_inflation` are what make them interpretable. The observed,
calculated and background curves are on the result as
`RefinementResult.y_obs`, `RefinementResult.y_calc` and
`RefinementResult.y_background`, over `RefinementResult.two_theta`.

`RefinementResult.plot` writes an obs/calc/difference figure with matplotlib
(the `viz` extra).

**Rwp is not the answer.** It is a fit statistic, and this package can show
you a fit whose Rwp improved while its atomic displacement parameters and
phase fractions moved *away* from the truth. What the package hands you
instead is [](report.md); the judgement behind it is AGENT_PROTOCOL §4.
