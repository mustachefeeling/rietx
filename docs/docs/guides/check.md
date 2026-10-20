(guide-check)=
# How to check a pattern before fitting

Call `rietx.diagnose` on the pattern, read its `signal_cutoffs` first, then draw the pattern under your model's reflection ticks.

Neither step needs a fit, and neither changes the pattern.

## Read the pattern diagnostics

`diagnose` measures the pattern with no model.
Pass the wavelength, so it can screen for a Kβ or tungsten Lα line.
This runs on the GSAS-II tutorial fluorapatite pattern that ships with rietx:

```{literalinclude} ../../../examples/guides/check.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/check.py -->
```text
signal cutoffs: []
dead channels: [] | sigma measured: False
steps per FWHM: 4.6 over 76 peaks
contamination: []
air-scatter gain: 0.75
```

`print(d)` lists all eighteen fields, starting with `signal_cutoffs`.
Read the five above in this order:

1. `signal_cutoffs` names an end of the range where the counts collapsed and stayed down, behind a beamstop or past the detector's edge.
   Its `two_theta` is where to set the fit range.
   Every other field is measured over the whole range, so after you trim, call `diagnose` again on the trimmed range.
2. `dead_channels` names short runs that count almost nothing with a tiny σ.
   Such a channel can carry thousands of times the weight of a live one, and it drags the background down to meet it.
   Exclude it as [How to limit the fit range or leave out a region](range.md) shows.
   The check needs the file to give a σ for each point, so on this pattern, which gives none, the empty list means not checked.
   `coverage_plateau` is `None` when σ was not measured.
3. `steps_per_fwhm` is how many 2θ steps span the top of a typical peak.
   The IUCr guidelines ask for five to ten {cite}`mccusker1999`.
   This pattern has 4.6, so the integrated intensities are slightly under-sampled, and the fit reports `PATTERN_UNDERSAMPLED`.
   Only a new measurement at a finer step fixes it.
4. `contamination` lists Kβ or tungsten Lα lines, each at a fixed ratio to its parent reflection.
   It stays empty without a wavelength, and for a synchrotron wavelength, which has no anode lines.
5. `air_scatter_gain` measures the low-angle rise from air scatter.
   Above 0.3, `auto_background` adds a 1/2θ term to the background.

## Check the starting cell against the peaks

`PatternData.plot` with `model=` draws one row of reflection ticks per phase under the data, at the positions the model gives now:

```{literalinclude} ../../../examples/guides/check.py
:language: python
:start-after: "# guide: ticks start"
:end-before: "# guide: ticks end"
```

Each tick should sit under a peak.
A cell 1 % too large puts every fluorapatite tick about 0.3° to the left of its peak between 25° and 40°.
An offset that is the same at every angle points to a zero shift.
An offset that grows with angle comes from the cell or the wavelength, which peak positions alone cannot tell apart.
A peak with no tick is an impurity, or a phase you have not declared.

`model=` needs the linear intensity axis, and refuses any other `y_scale`.

## Size the background from the diagnostics

`auto_background` reads two of the diagnostics and sizes a background model to the pattern.
It returns the model with the scores it chose on:

```{literalinclude} ../../../examples/guides/check.py
:language: python
:start-after: "# guide: background start"
:end-before: "# guide: background end"
```

<!-- output of examples/guides/check.py -->
```text
BackgroundPSpline with 41 coefficients
knot step 3°: hump score 0.162, trigger 0.05
air-scatter term True: gain 0.75, trigger 0.3
```

It sets the knots 3° apart because `amorphous_hump_score` is above its trigger, and 8° apart otherwise.
It adds the air-scatter term because `air_scatter_gain` is above its trigger.
When you will fit a narrower range, pass `two_theta_limits`, so the knots stay inside it.
Assign `choice.background` to `Instrument.background`.

The full script is `examples/guides/check.py`.

## See also

- [How to limit the fit range or leave out a region](range.md) acts on what this check finds.
- [Pattern diagnostics](../reference/pattern-diagnostics.md) gives all eighteen fields and the measurements behind them.
