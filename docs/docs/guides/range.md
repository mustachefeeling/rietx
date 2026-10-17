(guide-range)=
# How to limit the fit range or leave out a region

Pass `two_theta_limits` to `Refinement.fit` to fit one stretch of 2θ, and set `PatternData.excluded_regions` to leave intervals inside it out.

Both leave the measured points in the pattern, and both include their end points.

## Set the range and exclude a region

This fit uses the GSAS-II tutorial fluorapatite pattern that ships with rietx, which runs from 15° to 130.04° 2θ in 0.02° steps.
It fits 20° to 120° and leaves out 30° to 31°.
Nothing at 30-31° needs excluding in this pattern.
The interval stands in for a sample-holder line or a dead detector strip in yours.

```{literalinclude} ../../../examples/guides/range.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/range.py -->
```text
5753 channels in the file
4950 channels fitted
20.0 to 120.0
```

The range holds 5001 channels, and the excluded degree holds 51 of them.
The result's arrays, such as `RefinementResult.two_theta`, hold only the channels the fit used, and every statistic counts only those.

`excluded_regions` takes a list of `(low, high)` pairs in degrees.
An interval written high to low, or with equal ends, is refused with a `ValidationError`.
A `two_theta_limits` written high to low is refused too.

To find where a pattern's signal stops, run `rietx.diagnose` before the fit and read `signal_cutoffs`.
[How to check a pattern before fitting](check.md) shows it.

## Know which calls keep the range

`fit` never reuses an earlier range.
Called without `two_theta_limits`, it fits the whole pattern.
`Refinement.run_stage` called without one uses the range of the last fit or stage.

Each history node records the range its stage ran over, but not the excluded regions, which belong to the pattern.
So `Refinement.checkout` restores the node's range for the next `run_stage`, and leaves the pattern's excluded regions as they are.
`rietx.replay` recomputes a node over the node's range and the excluded regions of the pattern you pass it:

```{literalinclude} ../../../examples/guides/range.py
:language: python
:start-after: "# guide: replay start"
:end-before: "# guide: replay end"
```

<!-- output of examples/guides/range.py -->
```text
5001 channels in the replay
```

The replay still covers 20° to 120°, and includes the 51 channels the fit left out.
Restore `excluded_regions` before a replay that should match the fit.

## Cut the pattern instead

`PatternData.crop(low, high)` returns a new, shorter pattern, and keeps the excluded regions.
Use it to hand a smaller pattern to a tool that reads the whole thing.
For a fit, prefer the range: the pattern stays the file you measured.

## Set them in a project

A project stores both settings in its `project.json`, and its `fit` and `run_stage` use them.
Give them to `Project.create`, or change them afterwards with `Project.set_excluded_regions` and an assignment to `project.doc.two_theta_limits`.
`Project.fitted_mask` returns which channels the next run fits, one value per channel:

```{literalinclude} ../../../examples/guides/range.py
:language: python
:start-after: "# guide: project start"
:end-before: "# guide: project end"
```

<!-- output of examples/guides/range.py -->
```text
4950 channels the next run fits
5751 channels after the change
```

`save` writes the settings to `project.json`.
The history needs no save, because it is written as each stage runs.
In the GUI, the plot panel sets the same two fields.

The full script is `examples/guides/range.py`.

## See also

- [About a project](../concepts/project.md) describes what `project.json` and the history each hold.
