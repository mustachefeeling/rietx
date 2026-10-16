# Plan presets

A plan preset is a named list of stages, and this page draws each one from the plan objects rietx runs.

A stage frees the parameters its globs match.
Staging is cumulative, so each stage refines with every earlier stage's parameters still free.
Pass a preset by name, as `fit(plan="lab_calibrate")`, or build one with `RefinementPlan` and edit its `stages` list.

```{include} ../_generated/plans.md
```
