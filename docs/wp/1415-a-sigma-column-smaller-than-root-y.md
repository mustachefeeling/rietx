# WP-1415 — a σ column smaller than √y

Milestone: unscheduled · Status: ⬜
Depends on: —

## Goal

Two diagnostics that quietly assumed a Poisson-scale σ hold up on a pattern
whose file carries a smaller one. `PATTERN_UNDERSAMPLED` measures its peak
widths on Bragg peaks and not on noise ripples, and a dead detector channel
inside the fitted window is named as such, with the channels, instead of
surfacing as fourteen parameters at their bounds.

## Context

Issues #274 and #275 (2026-09-07), both measured on `origin/main` `2ba7a9a3`
with the public APDW workshop set for Co₃O₄ (ILL D1B, λ = 2.52 Å,
`300q-300K.dat`). The file's σ is monitor-normalised and propagated, so the
median σ/√y is 0.289. That is most constant-wavelength neutron data, and it
is the right σ: GoF sits at 5–10 on a visually excellent fit because the data
are about 3.5× more precise than √y. Root CLAUDE.md § Invariants says to use
the file's σ when present, and every weighted residual divides by it
(WP-1029). Neither issue asks for that to change. Both are consumers that
took √y for granted.

**#275 — `PATTERN_UNDERSAMPLED` counts noise as peaks.**
`background/diagnostics.py::sampling_steps_per_fwhm` hands
`_median_steps_per_fwhm` the net signal over the rolling envelope divided by
σ, and finds peaks on that with `find_peaks(height=5.0, distance=3,
prominence=SAMPLING_PROMINENCE_SIGMA)`. With σ 3.5× smaller than √y, z is
3.5× larger, and noise ripples about two channels wide clear the threshold.

| σ used | steps per FWHM | peaks counted | warning |
|---|---|---|---|
| the file's own σ | 1.84 | 113 | fires, asks for FWHM/5 |
| σ = √y | 6.85 | 16 | silent |
| the truth (half-height width of the strongest line, 1.10° at 0.1° steps) | 11.0 | 13 unique reflections | — |

The pattern is sampled at FWHM/11 and told to re-collect at FWHM/5. In a
sequential series the finding fires on every pattern and
`SEQUENTIAL_PERSISTENT_FINDING` promotes it to a property of the model,
correctly, of a false positive. The bands `STEPS_PER_FWHM_MIN`/`MAX` are
quoted from McCusker et al. 1999 and stay (root CLAUDE.md: they set a level,
never a gate). What changes is the peak *selection*: measure the width on
the strongest few peaks above a fraction of the maximum, or refuse to trust a
median over more peaks than a diffraction pattern can plausibly have. Either
is decided by measuring both on this file and on the fixtures the suite
already carries.

**#274 — two dead PSD cells inside the window, and nothing names them.**

```
   2θ        y      σ
 128.49   36503   55.145      live
 128.59       3    1.000      dead cell
 128.69       5    1.414      dead cell
```

Weights are 1/σ², so a channel with σ = 1 is worth about 3 000 live channels
at σ = 55. Like for like, 12-term Chebyshev background, axial asymmetry
refined:

| fitted window | background | Rwp | background at 128.6° |
|---|---|---|---|
| dead channels inside | 12-term Chebyshev | 0.08724 | −2059 |
| dead channels inside | P-spline, 8° knots | 0.17797 | −586 |
| dead channels inside | 4-term Chebyshev | 0.17733 | −3326 |
| dead channels excluded (`(127, 150)`, as the tutorial's FullProf `.pcr` does) | 12-term Chebyshev | 0.00739 | 35158 |

Every background is dragged through zero at the top of the range. The
Caglioti terms run to their bounds (u, v pinned; w = x = y = 0) and all three
Biso pin at zero. The fit emits `BACKGROUND_ABSORPTION` ×15, `BOUND_HIT` ×14,
`HIGH_CORRELATION`, `DATA_SUPPORT_LOW` and `PATTERN_UNDERSAMPLED` (#275
above). All symptoms. Fourteen parameters at bounds is the loudest thing a fit
can say short of refusing, and none of the fourteen is the problem.

What the package has: `signal_cutoffs` (same module) returns the leading
cutoff only (`edge='low'`, 2.99°, 22 channels). The trailing two-channel
dropout is below `CUTOFF_MIN_DEG = 1.0` and interior besides. Its own
docstring describes this failure shape on an ILL D20 file.

**The shape of the fix.** A dead cell has a signature no live channel has: its
intensity and its σ are both an order of magnitude below their neighbours',
and σ ≈ √max(y, 1), Poisson of nothing. A model-free census beside
`signal_cutoffs` finds those channels and reports them, on the `diagnostics=`
channel at read (`read_pattern`, WP-1047) and in the fit's list at compile.
It reports and applies nothing. `project.fitted_mask` is the one authority
on which channels a run fits (WP-1033), and `excluded_regions` is the
caller's. The finding names the channels and the interval to exclude.
Thresholds are measured on this file and on the D20 file `signal_cutoffs`
documents, never on one. `signal_cutoffs` may additionally admit a short
dropout at either edge, which is the issue's second ask.

**Data.** The APDW set is public. Whether it may enter `tests/data/` depends
on its stated licence (root CLAUDE.md: data carries its own fence, per file);
`tests/data/README.md` records the answer. A synthetic pattern with two dead
channels and a σ column at 0.3·√y reproduces both defects without it.

### Inherited

- **From WP-1442, 2026-09-20: the contamination census in the same function
  counts noise for a second reason, and 1442 wants one peak selection for
  both.** `diagnose` hands `_contamination_flags` a `find_peaks(net/σ,
  height=5, distance=3)` census with no prominence, on the rolling
  10th-percentile envelope, which sits under the data on a steep background.
  On a 4–40° organic pattern with a Poisson σ that census found 292 peaks
  against 23 from `_median_steps_per_fwhm`'s prominence-gated count. Whichever
  WP lands first owns the selection and the other imports it; do not grow two.

- **From WP-1434, 2026-09-18: the bound test is now scaled by each
  parameter's own esd, so a misdeclared σ moves it.** `BOUND_HIT`'s loose half
  asks whether the value sits within a hundredth of an esd of its limit, and
  esds scale with σ. A σ column smaller than √y shrinks every esd and tightens
  this test by the same factor, which makes `BOUND_HIT` a third diagnostic
  this WP's fixture perturbs rather than a bystander. The `BOUND_HIT ×14`
  count in § Context was measured under the old distance test and needs
  re-measuring.

## Non-goals

- Replacing the file's σ with √y anywhere. The issues are explicit that the
  σ is right.
- Excluding channels on the package's authority. Report, name, suggest.
- Retuning `STEPS_PER_FWHM_MIN`/`MAX` or `CUTOFF_MIN_DEG`.

## Tasks

- [ ] `_median_steps_per_fwhm` selects the peaks it measures on by intensity
      relative to the pattern's maximum (or caps the count it trusts); both
      candidates measured on the D1B file and every fixture in the suite,
      the numbers in the handover, one chosen.
- [ ] A dead-channel census in `background/diagnostics.py`, reported at read
      and at compile with the channels and the interval; `GuardFinding`
      constructor and `help.py` entry.
- [ ] `signal_cutoffs` admits a short dropout at an edge, if the D1B and D20
      files agree it is separable from a cliff.
- [ ] Tests: the synthetic pattern above for both defects; the APDW file if
      its licence admits it, else the numbers quoted here in the docstring.
- [ ] Skill: a `references/diagnostics.md` row for the new code, and a
      `references/surprises.md` row that a correct σ smaller than √y gives
      GoF 5–10 on a good fit and must not be "fixed".

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_readers_robust.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issues #274, #275 (2026-09-07; `origin/main` `2ba7a9a3`).
- McCusker, L. B., Von Dreele, R. B., Cox, D. E., Louër, D. & Scardi, P.
  (1999), *J. Appl. Cryst.* **32**, 36 — §2, the sampling guideline.
- WP-1029 (every weighted residual divides by `sig()`), WP-1033
  (`fitted_mask`), WP-1047 (a reader repairs only where it says so).

## Handover log

- **2026-09-15** — created, from the 2026-09-15 issue triage (issues #274,
  #275). Grouped because one σ column smaller than √y breaks both, and the
  same D1B file measures both. Checked against the tree: the peak finder
  thresholds on net/σ, and `signal_cutoffs` is edge-only with a 1° minimum.
