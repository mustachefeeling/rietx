# WP-1442 — A ghost search at chance

Milestone: unscheduled · Status: ⬜
Depends on: — (1415 soft)

## Goal

A Kβ or W Lα contamination flag means the pattern carries that line. The
finding is joint across the strong reflections and quotes one ratio, the census
it runs on cannot count noise as peaks, a source that cannot emit the line never
runs the search, and a line with a degenerate position esd matches nothing.

## Context

Measured 2026-09-20 on `origin/main` `b8df0a0e`, prompted by a new user's public
demo notebook (github.com/LLongley94/rietx_demo, `example_bim.ipynb`, cell 7):
`rx.diagnose(data, wavelength=1.5406)` on a 4–40° transmission scan of an
organic on Kapton returned 34 contamination flags, 20 Kβ and 14 W Lα, and the
notebook's own caption reads them as the software checking for Kβ peaks.

**The rule.** One implementation,
`background.diagnostics.contamination_flags_from_peaks` (WP-1018), two callers:
`diagnose` hands it a `find_peaks` census of net height over the rolling
envelope (`_contamination_flags`), `indexing.pick.flag_ghosts` hands it the
fitted list. For each of the `GHOST_N_PARENTS = 8` strongest lines it predicts
the same-d position at λ_Kβ (per anode, `_KBETA`, NIST SRD 128 / Hölzer 1997)
and at W Lα1 (Bearden 1967), and flags any weaker line within
`max(GHOST_TOL_DEG = 0.15°, 3·√(σ_g² + σ_p²))` whose intensity ratio lies in
`GHOST_RATIO_RANGE = (0.005, 0.6)`. Each flag is per line and independent of
every other. `PeakList.usable()` drops a flagged line, so `index_pattern` never
sees it, and `PEAK_CONTAMINATION_LINE` reports the count. The anode is
`identify_anode(wavelength)`, the nearest tabulated Kα1 within 0.01 Å, with no
source kind consulted. The wavelengths are referenced (ATTRIBUTION.md); the
matching rule and every threshold are v0.2's own, uncited, and unmeasured until
now.

**It flags at the chance rate where Kβ cannot exist.** Every
`tests/data/qarr/*.prn` and `nist_srm660c_100a.cif` was collected behind a
graphite diffracted-beam monochromator (`tests/data/README.md`). `pick_peaks`
plus the rule, against a control in which the ghost wavelength is replaced by
26 fake values from 0.84λ to 0.99λ:

| | Kβ flags | W Lα flags | fake-λ control, Kβ flags |
|---|---|---|---|
| 17 monochromated patterns, 1 295 fitted lines | 15 | 4 | 1.1 per pattern, mean |
| per pattern | 0.9 | 0.2 | |

All 19 lines were dropped from `usable()`. Their ratios run 0.008–0.32,
scattered like the control's.

**The demo pattern.** Its xrdml declares a focusing mirror, no filter element,
and a PIXcel1D with a 25–80 % pulse-height window, so a small residual Kβ is
physically possible on that instrument. The data carry none:

| | flags |
|---|---|
| `diagnose`, real wavelengths | 34 (20 Kβ, 14 W) |
| fake-λ control on the same census | mean 19.5, max 34 |
| `pick_peaks` fitted list | 7, all at 5.9–8.2° and all `position_at_bound` |

The decisive number is the strongest line. A leak is one ratio across the
pattern, and at 19.27° the predicted Kβ position holds 0.007 of the parent (net
height, ±0.1°) while 18.18° holds 0.030 and 22.29° 0.037. Sixteen of the 20 Kβ
flags are noise maxima on the Kapton hump between 4.75 and 5.63°, four
"parents" and twelve "ghosts", at ratios 0.16–0.60. The W flag at 18.37° is a
weak real reflection beside the 18.2° peak.

**Why the census is noise.** `diagnose` finds peaks with
`find_peaks(net/σ, height=5, distance=3)` and no prominence, on
`net = y − background_envelope(tt, y)`. The envelope is a rolling 10th
percentile in 3° windows, a peak-robust, λ-free stand-in chosen in v0.2 for
baseline-*shape* questions (hump, air scatter), where a small low bias is
harmless. Under a census it is not: a 10th percentile of a noisy window sits
about 1.3σ under the mean, on a steep curved background the window's percentile
lands further under the level, and on the demo pattern the envelope sits under
the data everywhere, so net/σ clears 5 across two thirds of the channels.

| `PatternDiagnostics` field | value |
|---|---|
| `peak_fraction` | 0.67 |
| `n_peaks` (this census) | 292 |
| `n_peaks_measured` (`_median_steps_per_fwhm`, prominence-gated) | 23 |

The same function's sampling count already carries
`prominence=SAMPLING_PROMINENCE_SIGMA`, added after the same failure on
synthetic LaB6 (module docstring). The census feeding the contamination check
never got it. WP-1415 is the sibling on the σ side (a σ smaller than √y
inflates z the same way) and touches `_median_steps_per_fwhm`; the two must
not each grow their own peak selection.

**The rule does find a real leak, and the ratio is what separates it.** A
same-d Kβ image injected into corundum, zincite and cpd-1e (all Kβ-free) at
ratio r:

| r | Kβ flags, corundum / zincite / cpd-1e | reported ratios |
|---|---|---|
| 0.005 | 1 / 5 / 3 | |
| 0.01 | 5 / 8 / 5 | 0.007–0.011, plus the chance ones |
| 0.05 | 9 / 10 / 6 | 0.043–0.055 |
| 0.15 | 10 / 11 / 16 | 0.135–0.161 |

cpd-1e's three chance flags sit at 0.037, 0.081 and 0.319 at every r. A
contamination is one number across all strong parents; a coincidence is one
line. The current test never compares parents.

**The literature.** Hölzer et al. 1997 Table VI, corrected Kβ1,3/Kα1,2 at a
precision better than 4 %: Cu 0.141, Cr 0.139–0.147, Mn 0.140, Fe 0.143–0.152,
Co 0.137, Ni 0.147–0.150. An unfiltered tube is 0.14, the 0.6 ceiling admits
four times that, and the docstring's "≤ ~0.2" has no source. Cheary, Coelho &
Cline 2004: most diffractometers operate with Kβ filtering or some form of
monochromatisation. Cline et al. 2015: a Kβ filter leaves an absorption edge in
the background on the low-energy side of the profiles, a fingerprint of a
filtered instrument that no ghost search sees. No Rietveld code detects Kβ:
TOPAS models it as a declared emission-profile component, EVA and HighScore
strip it with a ratio the user supplies. Whether Kβ is present is a property of
the optics.

**Two more paths to a false flag.** (1) `identify_anode` from the wavelength
alone: the BT-1 neutron pattern `mg090.Cu311.gsas` at 1.5404 Å is "CuKa", and
`diagnose` flags two ghosts on it. (2) The σ-widened window has no cap: on
`FAP.XRA` two unresolved-shoulder fits carry position esds of 1587° and 9217°,
matched every parent, and produced all 35 of that pattern's flags. Also, a ghost
is flagged once per parent, so a Kα1/Kα2 pair fitted as two lines flags it twice
(cpd-1b 31.716°, cpd-4 33.737°).

**What the source knows.** `Source` declares lines, polarisation, dispersion and
harmonics; nothing says filter or monochromator.
`Instrument.bragg_brentano(monochromator_two_theta=)` folds a diffracted-beam
monochromator into the polarisation factor only. The xrdml reader sees the
`<xRayMirror>`, `<monochromator>` and `<filter>` elements and keeps none.

**Where it is documented.** Part 1 `using/results.md` § "How finely the peaks
were sampled" › "Everything else `diagnose` measures", with the warning box on
`contamination`; one cross-reference sentence in `using/refining.md`;
`help.py` `ghost_kbeta` / `ghost_tungsten`; the skill's
`references/diagnostics-indexing.md` row for `PEAK_CONTAMINATION_LINE`
("Subtract it"). Nothing in the theory part. A reader looking for `diagnose`
from the reading-data or refining chapters does not find it.

## Non-goals

- Stripping Kβ, or modelling it as an emission line. `_RADIATIONS` fences it and
  `capabilities.AnodeCapability.kbeta` says why: one |F|² cannot serve Kβ and
  Kα together.
- Retuning `background_envelope` for `auto_background`'s shape questions, which
  it answers well; only what the census reads changes.
- `_median_steps_per_fwhm`'s own peak selection: WP-1415.
- A filter absorption-edge term in the background (Cline 2015): a correction,
  with its own WP if it is ever wanted.

## Tasks

- [ ] The finding is joint: candidates are gathered per parent and a
      contamination is reported only when several in-range strong parents
      carry one at a common ratio. The spread bar and the parent count are
      measured on the injection ladder and the 17-pattern control above,
      numbers in the handover. `ContaminationFlag` carries the fitted ratio
      and the parents, and the per-line flags derive from it. Control: 0
      flags; injections: r recovered.
- [ ] `GHOST_RATIO_RANGE`'s ceiling from Hölzer Table VI with margin (about
      0.25), the docstring citing the table and the "≤ ~0.2" line gone.
- [ ] The census `diagnose` hands the check gets the prominence gate
      `_median_steps_per_fwhm` already has, or the check runs on a fitted list
      only. `n_peaks` and `peak_density_per_deg` re-measured on the demo
      pattern (from 292) and on every fixture, in the handover. One selection
      serves this and WP-1415.
- [ ] The σ-widened window is capped, and a line with a degenerate position
      esd is never a candidate. `FAP.XRA` is the fixture.
- [ ] A source that cannot emit the line never runs the search: `neutron_cw`
      skips; for `xray_cw` a declared filter or monochromator narrows the
      ratio window or skips. Design call for the maintainer: a `Source` field
      or a `Geometry` one, filled by the xrdml/brml/rasx readers where the file
      says. The demo's optics are the worked case.
- [ ] One flag per ghost line, whatever the parents.
- [ ] Manual: the `results.md` warning rewritten around the joint finding, a
      pointer to `diagnose` from the reading-data or refining chapter, the two
      `help.py` entries. Skill: the `references/diagnostics-indexing.md` row
      says what the ratio means, and a `references/surprises.md` row that an
      unfiltered tube is 0.14, so a 0.3 "ghost" is a reflection.
- [ ] Tests: the fake-λ control on the monochromated fixtures (0 flags), the
      injection ladder, the neutron and FAP cases; PNGs to `tests/output/`
      where a picture is the evidence.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_peak_picking.py tests/test_capabilities.py -q
.venv/bin/python -m pytest tests/test_acceptance_indexing.py   # usable() feeds every engine
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Hölzer, G., Fritsch, M., Deutsch, M., Härtwig, J. & Förster, E. (1997),
  *Phys. Rev. A* **56**, 4554–4568, Table VI (the Kβ1,3/Kα1,2 ratios).
- Cheary, R. W., Coelho, A. A. & Cline, J. P. (2004), *J. Res. NIST* **109**,
  1–25, the tube-tails section on Kβ filtering.
- Cline, J. P., Mendenhall, M. H., Black, D., Windover, D. & Henins, A. (2015),
  *J. Res. NIST* **120**, 173, on the filter's absorption edge.
- Bearden, J. A. (1967), *Rev. Mod. Phys.* **39**, 78 (W Lα1); NIST SRD 128.
- The public demo notebook: github.com/LLongley94/rietx_demo, `example_bim.ipynb`,
  measured 2026-09-20; its data file is that repository's, not this one's.
- WP-1018 (the one ghost implementation), WP-0507 (per-anode Kβ), WP-1028 (the
  envelope's edges), WP-1415 (the σ sibling).

## Handover log

- **2026-09-20** — created from the measurements above; nothing in the tree
  changed.
