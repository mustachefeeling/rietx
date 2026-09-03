# WP-1336 — the fit does not say it is unusable: the status channel and the width census

Milestone: unscheduled · Status: ⬜
Depends on: — (1310 soft: how findings arrive on the result)

## Goal

A programmatic caller can tell a usable fit from an unusable one without
reading prose. `status` means one thing, stated in its own docstring, and the
channel that judges quality is named beside it. And a refinement whose
declared instrument profile is an order of magnitude away from the measured
peak widths is told so, by the diagnostic that already contains the sentence.

## Context

Two issues, one complaint: **the package knew, and the field named for whether
the solve worked said it worked.**

**#243 — `status="converged"` on solves whose own diagnostics report
`MODEL_FAR_FROM_DATA` at Rwp 84–235 %.** Reproducible on the repo's own
acceptance fixture, with the profile left unseeded:

```python
data = rx.read_pattern("tests/data/11BM_NAC.fxye")
s = rx.Structure.from_cif("tests/data/cod_1000236.cif")
i = rx.Instrument.debye_scherrer(wavelength=0.413957)
i.background = BackgroundChebyshev.with_terms(6)          # profile NOT seeded
r = rx.Refinement(s, i).fit(data, mode="lebail",
                            plan=rx.RefinementPlan.lab_sample_refine(),
                            two_theta_limits=(2.0, 24.0))
r.status            # -> converged
r.statistics.rwp    # -> 0.8380
{d.code for d in r.diagnostics}   # -> includes MODEL_FAR_FROM_DATA
```

Seeding the profile as `examples/nac_11bm.py` does gives Rwp 0.1594 with no
`MODEL_FAR_FROM_DATA`, so the fixture is fine and the configuration is simply
a bad one — which is the point. Also seen on the reporter's own data at
Rwp 2.35, and on a third dataset at 1.73–1.84 where a cell ran onto a schema
bound while `status` still read `converged`. Across a 550-pattern tranche
their driver branched on `status` and treated every row as usable.

**The design constraint the issue does not know about.** `status` is
`Literal["converged", "max_iter", "diverged"]` on both `RefinementResult` and
`StageResult` (`schemas/results.py`), and `StageResult`'s docstring states
the rule: *"`status` is the solver's, and the vocabulary is exactly the three
terminations the solver produces — `optimize/least_squares.py` builds its
outcome three ways and there is no fourth."* A `converged_with_findings`
member is not a solver termination, so the issue's first option is the one
shape this WP should **not** take without overturning that rule on the record.
(WP-1076 is why the fourth member `"skipped"` left — nothing set it — which is
a different reason; a fourth member *with* a writer would pass 1076 and still
break the docstring's rule.) `RefinementResult` itself has **no class
docstring** — the class opens on a `#:` comment — so the statement the
reporter could not find does not exist anywhere yet. The two options that
remain fit the existing grain:

- say in the field's docstring that `status` reports **optimiser exit only**
  and carries no claim about fit quality, naming `diagnostics` as the channel
  that does — the reporter says this alone would resolve it, and that they
  could not find the statement;
- and/or a **derived predicate** on `RefinementResult` answering "is this fit
  usable" by consulting both, which is the `capabilities()` idiom (a flag that
  is an expression, never a literal) one rank down.

**#249 — `PEAK_WIDTH_LAW_MISMATCH` is unreachable from the Rietveld path.**
`indexing/diagnostics.py::_width_diagnostics` compares the measured FWHM
census against the instrument's declared width law and warns past
`WIDTH_MISMATCH_RATIO` in either direction, and `help.py` frames the fork
better than any new prose would: *"Either the specimen is broadened, which is
a finding, or the declared instrument is wrong, which is a setup error. The
message carries the ratio so the two can be told apart."*

It is computed from a `Detection`, so it is reachable only from indexing.
Confirmed on the tree: `refine.py`, `report/` and `strategy/` import nothing
from `indexing`. A Rietveld refinement that declares an instrument profile
never runs the census, though `PEAK_WIDTH_CENSUS_N = 12`
(`schemas/indexing.py`) is the same twelve-most-prominent-lines check a user
is otherwise advised to do by hand.

What it cost: a ~40 000-point synchrotron pattern, correctly transcribed
instrument profile, two phases, no size or microstrain parameters. Median
observed FWHM ≈ 0.032–0.035° against a modelled 0.0026–0.0046° — a factor of
~9–13, far outside the threshold — and Rwp 0.674 against a 0.092 reference.
The Rietveld path emitted `outside_validity_radius` ×14 (correct, but
position-flavoured, and its remedy text points *away* from a width cause) and
`gram_condition` ×10. Nothing named the width. Both width channels that do run
went quiet, correctly:

- `report.strain[*]` returned `detected: false`, `r2: 0.0` for every phase —
  right for its stated purpose, since `analyse_strain` is scoped to
  directional (Stephens) anisotropy and this deficit is isotropic. It is also
  the most expensive computation in the report path (1335), so the one width
  analysis that ran spent ~110 s answering a question that could not detect
  this.
- `report.microstructure[*].size_agreement`, `strain_agreement` and
  `size_strain_collinearity` were all `null`, there being no size/strain
  parameters to compare.

So the model was wrong about peak width by an order of magnitude and every
channel either declined to look or looked in a different direction.

**The issue asks a question rather than asserting a bug, and it is the right
question:** is the siloing deliberate? The census needs a `Detection`, which a
refinement does not build, so this may be a real design boundary — in which
case the useful change is a **callable precondition check**
(`check_instrument_against(data)`) rather than wiring the existing path
through. Take that decision explicitly; either answer is defensible and the
choice should be visible.

## Non-goals

- Making the unseeded configuration converge. The fits in #243 should not have
  converged well; the report is only that two channels contradict each other.
- Deduplicating per-stage findings, and the stale `BOUND_HIT` — 1310.
- Any new width physics. `PEAK_WIDTH_LAW_MISMATCH` already says the right
  thing; this is about its reach.
- The profile-width *ceiling* — a refined width that walked to an absurd
  value with nothing raised (#102) — is 1311 item 4. This WP is the other
  direction: a *declared* width an order of magnitude under the measured
  census. One width diagnostic each, and each names the other.

## Tasks

- [ ] Give `RefinementResult` the class docstring it lacks, and state there
      what `status` claims and what it does not, naming `diagnostics` as the
      quality channel.
- [ ] Decide whether a derived usability predicate lands, and if so make it an
      expression over the live diagnostics vocabulary rather than a literal
      (WP-1037's rule: a derived flag rots silently when its name and its
      export drift).
- [ ] Decide the width-census question — wire the census into the refinement
      path, or ship `check_instrument_against(data)` as a precondition call —
      and write the reason for the choice into the module that owns it.
- [ ] A synthetic acceptance case: a broad pattern fitted with a narrow
      declared instrument and no size/strain parameters now names the width.
      Needs no data file.
- [ ] Tests: the #243 reproduction asserts the two channels agree about the
      same solve; the census fires on the synthetic case and stays silent on
      the suite's seeded fixtures.
- [ ] Skill: `references/judging.md` — that `status` is optimiser exit, and
      the width row. `references/diagnostics.md` gains
      `PEAK_WIDTH_LAW_MISMATCH` on the refinement side if it becomes reachable
      there (86 B of headroom; see 1338).

## Acceptance

The #243 script's `status` and diagnostics no longer contradict each other by
a documented reading; a narrow-instrument synthetic fit names the width.

```sh
.venv/bin/python -m pytest tests/test_report_apply.py tests/test_help.py tests/test_skill.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issues #243, #249 — rietx 1.3.0, `SCHEMA_VERSION` 0.16, `main` plus PRs #206
  and #233.
- `src/rietx/help.py` — the one place what a name *is* is written (WP-1202).

## Handover log

- **2026-09-03** — created, from the 2026-09-03 issue triage (issues #243,
  #249). The `status` vocabulary was checked against the tree first: it is the
  three-member solver literal WP-1076 pinned, which rules out the issue's
  first suggestion and leaves its second and third. Re-checked the same day:
  `RefinementResult` has no class docstring at all; the rule that rules out a
  fourth member is the docstring's (status is the solver's), not WP-1076's;
  1311 item 4 named as the other width direction.
