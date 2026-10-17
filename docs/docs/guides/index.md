# Guides

Each guide does one task from start to finish, and its title names the task as "How to …".

Each guide's fits are a script in `examples/guides/`, run by the test suite, and the output a guide shows is what its script printed.

## Before the fit

- [How to check a pattern before fitting](check.md) reads `rietx.diagnose` and draws the reflection ticks.
- [How to limit the fit range or leave out a region](range.md) sets `two_theta_limits` and `PatternData.excluded_regions`.

## Background

- [How to use a measured blank as the background](blank.md) holds an empty-container scan under the pattern with `BackgroundFixedPlusChebyshev`.
- [How to add a hump to the background](hump.md) declares a broad Gaussian for amorphous or container scattering.

## Constraints and plans

- [How to keep a parameter fixed whatever the plan frees](hold.md) uses `Refinement.hold`.
- [How to tie parameters together](tie.md) makes parameters equal, or one a linear function of others.
- [How to restrain a bond length or an angle](restrain.md) adds chemistry as weighted observations.
- [How to add a stage to a refinement plan](plan.md) edits a preset or builds a plan.

## Running a fit

- [How to run a plan one stage at a time](stage.md) uses `Refinement.run_stage` and a report at each stage.
- [How to choose the next parameter to free](next.md) reads `Refinement.suggest` and measures the move with `compare_freed`.
- [How to watch or stop a running fit](watch.md) uses `rietx watch`, a cancel token, and the switches that turn recording off.

## Series

- [How to fit a temperature series](series.md) chains one refinement per pattern with `refine_sequential` and reads a trajectory.
- [How to check a series for path dependence](path.md) runs the chain both ways and refits a flagged step from cold.

```{toctree}
:hidden:

check
range
blank
hump
hold
tie
restrain
plan
stage
next
watch
series
path
```
