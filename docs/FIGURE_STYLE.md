# Figure style

How to make figures for this project. Follow these rules directly. Tool-agnostic: they apply whether you're using matplotlib, plotly, gnuplot, Origin, or slide software.

## Approach

The figure carries the explanation and the prose annotates it. Show the real data, strip everything that isn't load-bearing, and make the caption say what to conclude.

## Always

- **Show the actual data, not an abstraction of it.** Real measured patterns, real model output, real samples. Never a stylised box labelled "Model" where the model's output would fit.
- **Strip chrome to what the reader needs.** No gridlines, no chart title, no tick marks at values nobody reads. Keep full axes when the numbers matter; a bare frame when only the shape matters.
- **Encode epistemic status in line style, consistently.** Solid = measured or directly computed. Dashed = fitted, modelled, or estimated. Dotted = extrapolated or hypothetical. Keep this fixed across every figure in a document.
- **Label curves in place, in the curve's own color,** when there are two or three of them and space allows. Use a legend box only for four or more series, or for categorical scatter.
- **Share the scale across panels meant to be compared.** Different scales on side-by-side panels is the fastest way to mislead.
- **Order sequences left to right, or bottom to top for stacks.** The progression does the work; don't add arrows.
- **State units and conditions on the axes**, and anything needed to reproduce the measurement in the caption.
- **Admit any degradation.** If you downsampled, smoothed, rescaled, cropped, or clipped for legibility, say so in the caption.
- **Vary more than color.** Highlighted points are also larger; fitted curves are also dashed. A figure must survive being printed in greyscale.

## Never

Rainbow or `jet` colormaps. Gridlines by default. Chart titles (the caption is the title). Legend boxes for two labelled curves. 3D bar charts, pie charts, or 3D perspective on 2D data. Decorative color. Repeating the same axis label on every panel of a grid. "Figure 3: Results" as a caption. Clipart or generic AI-brain imagery. Rescaling a difference curve or truncating an axis without saying so.

## Pick the genre first

| Genre | Use when | Chrome |
|---|---|---|
| **Quantitative plot** | The numbers matter | Full axes, ticks, labels |
| **Stack / waterfall** | One pattern per condition, ordered | Full x-axis, offset y, no y ticks |
| **2D map** | Two continuous variables, intensity as the third | Full axes, colorbar with units |
| **Small-multiples grid** | Sweeping one parameter over few values | Frame only; labels once, outside |
| **Schematic** | Explaining a process or instrument | Thin outer border, no axes |
| **Specimen** | The raw data is itself the point | None |

## Diffraction patterns

**Observed vs. calculated.** The standard refinement plot, in this order top to bottom:

1. Observed intensity as **markers** (points or crosses), not a line — it's discrete counts.
2. Calculated intensity as a **continuous line** over the top.
3. **Bragg tick marks** below the pattern, one row per phase, labelled by phase.
4. **Difference curve** (obs − calc) below that, on the same intensity scale, plotted about its own zero.

Never smooth the observed data. If the difference curve is scaled to be visible, put the factor in the caption. Quote fit statistics in the caption or a corner annotation, not in a title.

**Axes.** Use 2θ in degrees and state the wavelength or source — a 2θ axis is meaningless without it. Use *Q* (Å⁻¹) instead whenever you overlay or compare data collected at different wavelengths, and *d*-spacing for time-of-flight neutron data. Intensity is normally arbitrary units; label it "Intensity (arb. units)" rather than inventing precision. Square-root or log intensity scaling is fine to bring out weak features, but say which you used.

**Insets for weak features.** Draw the box on the parent axes and connect it to the inset. Keep the inset's x-axis in the same units; state its magnification if the y-axis is rescaled.

**Stacks.** For a series over temperature, time, pressure, or composition: constant vertical offset, identical x-range, each trace labelled with its parameter value at the right-hand end. Offset by a fixed amount, not a proportional one, so relative intensities stay readable. Drop the y tick labels — the axis is offset intensity and the numbers mean nothing.

**2D maps** for a dense in-situ series: x = 2θ or *Q*, y = time or temperature, intensity as a perceptually uniform sequential colormap with a labelled colorbar. State the scaling. This replaces a stack once the stack exceeds roughly twenty traces.

**Refined parameters vs. condition.** Markers with error bars, one panel per parameter, sharing the x-axis in a vertical column. Say in the caption what the error bars are — estimated standard deviations from the refinement, propagated uncertainty, or a repeatability estimate — because they are not the same thing and readers assume the most flattering one.

## Curves and general graphs

- **Ground truth or analytic reference: solid, in a neutral dark color.** Fits and estimates: same color, dashed.
- **Twin axes must be color-matched** to their series — axis line, ticks, and label all take the series color, or don't use a twin axis.
- **Tick only at values you name.** If the point is that two peaks sit at x₁ and x₂, tick x₁ and x₂ and nothing else.
- **Wide aspect for patterns and time series**, roughly 2:1. Square only for genuinely isotropic 2D data.
- **Small-multiples grids:** columns are the parameter sweep, rows are the representations. Column headers on top once, row labels on the left once. No per-panel titles. Non-uniform sweep values are fine, and usually better — space them where the change happens.

## Schematics

- Embed the real thing at each stage: the actual pattern, the actual sample, the actual model output.
- **One accent color per diagram**, on the single most important object. Everything else is line art on white.
- Two label registers together: a plain-language name and the formal symbol.
- Stacked cards mean "many of these". Ellipsis dots mean "steps omitted". Operations get a circled glyph.
- Left-to-right flow, feedback routed underneath.
- Credit the source in the caption if you adapted someone else's diagram.

## Color

Assign by role and keep the assignment fixed for the whole document. Hue is your choice; the roles are not.

| Role | Treatment |
|---|---|
| Background population, the whole set | One base color, small markers |
| The subset under discussion | One contrasting color, larger markers |
| Measured / observed | Neutral dark, markers |
| Calculated / modelled | Same or adjacent hue, continuous line |
| Residual / difference | Muted, visually subordinate |
| Ordered series (T, t, composition) | Sequential perceptually uniform ramp, in order |
| Intensity in a 2D map | Perceptually uniform sequential map |
| The one crucial object in a schematic | A single saturated accent, used once |

Color must mean something. Never assign it arbitrarily to "series 1" and "series 2" when one of them is the thing you're actually pointing at.

## Captions

Full sentences that assign panel positions, name parameter values, and say what to conclude.

- ❌ Figure 3: Diffraction results.
- ✅ Rietveld fit to the 300 K pattern (λ = 0.8265 Å): observed (points), calculated (line), Bragg positions (ticks), and difference (below, ×3). The unindexed peak at 12.4° is an unidentified impurity.

Refer to figures as "the figure below" or "the pattern above" rather than numbering them, unless the venue requires numbers.

## Before you finish

- [ ] Genre chosen deliberately
- [ ] Real data shown, not an abstraction
- [ ] No gridlines, no title, ticks only at values that are read
- [ ] Solid = measured, dashed = modelled, and consistent throughout
- [ ] Panels meant to be compared share a scale
- [ ] Diffraction x-axis states wavelength, or uses *Q*
- [ ] Intensity scaling (linear, sqrt, log) stated if not linear
- [ ] Error bars identified as esds, propagated, or repeatability
- [ ] Legible in greyscale
- [ ] Any smoothing, rescaling, cropping, or clipping admitted in the caption
- [ ] Caption is a full sentence that says what to conclude
