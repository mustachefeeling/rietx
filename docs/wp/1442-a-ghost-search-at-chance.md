# WP-1442 — a ghost search at chance: the Kβ flag fires where Kβ cannot exist

Milestone: unscheduled · Status: 🔄 2026-09-21 — claimed by @yue-here
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
source kind consulted. The wavelengths are referenced (ATTRIBUTION.md), and the
0.15° floor is derived in `GHOST_TOL_DEG`'s docstring from the Kβ table's
precision (Δ2θ ≈ 0.02° at 60°); the matching rule, the ratio window and the
parent count are v0.2's own, uncited, and unmeasured until now.

**It flags at the chance rate where Kβ cannot exist.** Every
`tests/data/qarr/*.prn` and `nist_srm660c_100a.cif` was collected behind a
graphite diffracted-beam monochromator (`tests/data/README.md`). Both callers
run against a control in which the ghost wavelength is replaced by 26 fake
values from 0.84λ to 0.99λ, re-measured 2026-09-21 on `cb84295a` over those 17
patterns (1 108 fitted lines, `Instrument.bragg_brentano(radiation="CuKa")`):

| per pattern | Kβ flags | W Lα flags | fake-λ control |
|---|---|---|---|
| fitted list (`pick_peaks` → `flag_ghosts`) | 0.94 | 0.24 | 1.01 Kβ, 0.95 W |
| channel census (`diagnose`) | 3.06 | 0.94 | 2.56 Kβ |

The real wavelength buys nothing on either path. On the fitted list it scores
*under* the control. Every flagged line is dropped from `usable()`; the fitted
path's 16 raw Kβ flags mark 14 lines, because a ghost is flagged once per
parent and the same line is reached by two of them. The flagged ratios run
0.008–0.319 with a median of 0.054, scattered like the control's.

**The demo pattern.** Its xrdml declares a focusing mirror, no filter element,
and a PIXcel1D with a 25–80 % pulse-height window, so a small residual Kβ is
physically possible on that instrument. The data carry none:

| | flags |
|---|---|
| `diagnose`, real wavelengths | 34 (20 Kβ, 14 W) |
| fake-λ control on the same census | mean 19.6, max 34 |
| `pick_peaks` fitted list | 7 lines at 5.9–18.4°, six of them `position_at_bound` |

Every one of those numbers is unchanged on `cb84295a`, after WP-1415 rebuilt
the census (2026-09-21 re-measurement; the fitted list carries 12 marks over
those 7 lines, and the flagged ratios run 0.028–0.595 with a median of
0.161).

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

| `PatternDiagnostics` field | at the filing (`b8df0a0e`) | today (`cb84295a`) |
|---|---|---|
| `peak_fraction` | 0.67 | 0.67 |
| `n_peaks` (this census) | 292 | 197 |
| `n_peaks_measured` (`_median_steps_per_fwhm`, prominence-gated) | 23 | 21 |
| contamination flags | 34 | 34 |

The same function's sampling count already carries
`prominence=SAMPLING_PROMINENCE_SIGMA`, added after the same failure on
synthetic LaB6 (module docstring). The census feeding the contamination check
never got it.

**WP-1415 landed the shared selection and moved none of the flags.** It is
this WP's sibling on the σ side, a σ smaller than √y inflating z the same way,
and it closed 2026-09-21. `diagnose` now makes one `find_peaks` call and reads
it at two floors off the same near-maximum: `SAMPLING_HEIGHT_FRACTION` × the
99.9th percentile of net for the census, and `GHOST_RATIO_RANGE[0]` × the same
percentile for the ghost candidates. That took the demo's census from 292 to
197 and left its 34 flags exactly where they were, because the ghost search
reads the **lower** of the two floors. So the pool this check searches is still
the Kapton hump's noise maxima, and the census gate task 3 asks for cannot be
the fix on its own.

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

**Two more paths to a false flag**, both re-measured on `cb84295a`.
(1) `identify_anode` from the wavelength alone: the BT-1 neutron pattern
`mg090.Cu311.gsas` at 1.5404 Å is "CuKa", and `diagnose` flags three ghosts on
it (one Kβ, two W Lα). (2) The σ-widened window has no cap. On `FAP.XRA` the
`not_separable` and `unresolved_shoulder` fits at 64.330° carry position esds
of 1 961° and 11 390°, a `no_intensity` line at 105.788° carries 4.2e15°, and
32 of that pattern's 35 raw flags come from a line whose own esd exceeds 1°.
Also, a ghost is flagged once per parent, so a Kα1/Kα2 pair fitted as two
lines flags it twice (cpd-1b 31.716°, cpd-4 33.737°).

**What the source knows.** `Source` declares lines, polarisation, dispersion and
harmonics; nothing says filter or monochromator.
`Instrument.bragg_brentano(monochromator_two_theta=)` folds a diffracted-beam
monochromator into the polarisation factor only. The xrdml reader
(`_read_scan`) reads `anodeMaterial`, `usedWavelength` and `radius` under
`<incidentBeamPath>` and never looks at `<xRayMirror>`, `<monochromator>` or
`<filter>`; brml and rasx read no optics element either. Task 5 teaches each
reader the paths before anything can be kept.

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
- `_median_steps_per_fwhm`'s thresholds (`STEPS_PER_FWHM_MIN`/`MAX`,
  `SAMPLING_PROMINENCE_SIGMA`) and its σ side: WP-1415. Its peak *selection*
  is shared, per task 3 and the note in 1415's Inherited.
- A filter absorption-edge term in the background (Cline 2015): a correction,
  with its own WP if it is ever wanted.

## Tasks

- [x] The finding is joint: candidates are gathered per parent and a
      contamination is reported only when several in-range strong parents
      carry one at a common ratio. The spread bar and the parent count are
      measured on the injection ladder and the 17-pattern control above,
      numbers in the handover. `ContaminationFlag` carries the fitted ratio
      and the parents, and the per-line flags derive from it. Control: 0
      flags; injections: r recovered.
- [x] `GHOST_RATIO_RANGE`'s ceiling from Hölzer Table VI with margin (about
      0.25), the docstring citing the table and the "≤ ~0.2" line gone.
- [x] The pool the check searches is not a noise census. WP-1415 landed the
      shared selection, so the open half is which floor the ghost search reads:
      the prominence gate `_median_steps_per_fwhm` already has, or a fitted
      list only. The census floor cannot serve it, because a 1 % ghost sits six
      times under that bar. `n_peaks` and `peak_density_per_deg` re-measured on
      the demo pattern (197 today, from 292) and on every fixture, in the
      handover.
- [x] The σ-widened window is capped, and a line with a degenerate position
      esd is never a candidate. `FAP.XRA` is the fixture.
- [x] A source that cannot emit the line never runs the search — **split out
      to [WP-1445](1445-the-optics-nobody-declared.md)** on 2026-09-22, with
      the maintainer's decision. It needs a schema seam and three readers
      taught new file paths, and the joint finding removed the wrong answer it
      was filed against (the BT-1 neutron pattern, 3 flags → 0). The
      measurements taken for it are in that file's § Context, including the one
      that reframes it: `monochromator_two_theta` is consumed into a
      polarisation factor and discarded, so seventeen fixtures that sit behind
      a graphite monochromator cannot tell anyone.
- [x] One flag per ghost line, whatever the parents.
- [x] Manual: the `results.md` warning rewritten around the joint finding, a
      pointer to `diagnose` from the reading-data or refining chapter, the two
      `help.py` entries. Skill: the `references/diagnostics-indexing.md` row
      says what the ratio means, and a `references/surprises.md` row that an
      unfiltered tube is 0.14, so a 0.3 "ghost" is a reflection.
- [x] Tests: the fake-λ control on the monochromated fixtures (0 flags), the
      injection ladder, the neutron and FAP cases; PNGs to `tests/output/`
      where a picture is the evidence.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_peak_picking.py tests/test_capabilities.py
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

### 2026-09-20 — opened

The Kβ and W Lα contamination flags cannot be trusted as they stand. On
seventeen laboratory patterns collected behind a graphite monochromator, where
neither line can reach the detector, the search flags lines at the same rate as
a control fed a made-up wavelength, and each flag drops a real reflection from
the list indexing runs on. A public demo notebook shows the same search
returning thirty-four flags on a pattern whose strongest line has nothing at
its Kβ position. The search does find a real leak when one is injected, and the
one thing that tells the two apart is that a real leak has the same ratio at
every strong line. Nothing in the code changed; this entry files the evidence
and the fix.

*Measured* (`.venv` `[dev]`, macOS, `origin/main` `b8df0a0e`): everything in
§ Context. The scripts were ad hoc and are not committed; the control replaces
`_KBETA["CuKa"]` and `_W_LA1` by 26 fake wavelengths from 0.84λ to 0.99λ and
counts `kind == "kbeta"` flags, and the injection adds r × the net signal at
the same-d parent position over a rolling 10th-percentile baseline.

*Gotchas*: the roadmap sat exactly at its 784-line cap, so the row's line was
paid for by rewrapping one v1.3 paragraph at 81 columns, no words changed. The
demo's data file is the user's, on GitHub, and is cited by URL rather than
copied into `tests/data/`.

*Review pass* (`/code-review high --fix`, one commit for its six fixes, all
to this file): the xrdml reader reads no optics element at all, so task 5
teaches the readers the paths first; "19 lines" was 19 flags on fewer lines;
`-q` dropped from the acceptance command (`addopts` has one); the non-goal
that fenced `_median_steps_per_fwhm`'s peak selection contradicted task 3 and
now fences its thresholds and σ side only; the 0.15° floor is derived in its
docstring and is no longer called unmeasured; the H1 carries the row's
subtitle. Declined none. It skipped three as outside the diff: `identify_anode`
takes the first match, not the nearest (unambiguous by construction); the
`results.md` warning presents corundum's three flags as genuine (task 7);
fourteen sibling WPs carry the same `-q`.

*Not done, deliberately*: no skill row yet. An agent driving rietx today should
read a per-line ghost flag as a coincidence until task 1 lands; that sentence
belongs in the skill with the joint finding, not ahead of it.

Next: task 1 (the joint finding) first, since it alone would have turned the
demo's 34 flags into none and decides the shape of every other task; then the
census gate (task 3) together with WP-1415, so one peak selection serves both;
the source gate (task 5) last, because it needs a schema decision.

