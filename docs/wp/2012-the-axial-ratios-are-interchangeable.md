# WP-2012 — The two axial-divergence ratios are interchangeable, and a fit reports one branch

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-19 — a silent wrong pair of numbers on `lab_calibrate`, the one preset that frees both ratios; the profile it fits is right, so only a reader of S/L and H/L is misled

## Goal

A fit never reports S/L and H/L as two measured numbers when swapping them leaves the pattern
unchanged. Either the presets free one of the two, or the result says the pair is
interchangeable, and the help text stops telling a reader to fit them together.

## Context

**The symmetry, measured 2026-10-19** (WP-1986's calibration guide, `[dev]`, darwin/arm64).
`Refinement.predict` on LaB₆ under Cu Kα with `instrument.geometry.axial_sl = 0.025,
axial_hl = 0.015` and with the two swapped gives arrays equal to the last bit
(`examples/guides/calibrate.py` asserts it below its markers). So the profile in
`profiles/fcj.py` is symmetric under S ↔ H, and no pattern can choose between the two
assignments.

**What a fit does with it.** `lab_calibrate`'s `lines_axial` stage frees
`instrument.geometry.axial_*`. On the guide's synthetic LaB₆ standard (made with S/L 0.025 and
H/L 0.015), the fit started from both at 0 returned S/L 0.01451(76) and H/L 0.02531(66): the
swapped branch, each about 14 esd from its true value. The only finding was
`HIGH_CORRELATION` on zero shift against displacement. No finding names the axial pair,
because at the swapped minimum the two are not strongly correlated: the two minima are
separate points, not a ridge.

**Where the package tells a reader to do this.** `src/rietx/help.py`'s
`instrument.geometry.axial_sl` entry says "Fit it on a standard together with `axial_hl`. The
two are strongly correlated and are usually reported as a pair." The `axial_hl` entry says
"refining one and holding the other is a common protocol". The guide
`docs/docs/guides/calibrate.md` now holds H/L at the receiving slit's height over the
goniometer radius and says why.

**A second, smaller finding on the same pair.** On a synthetic standard with no axial
divergence at all, both ratios free, the fit reports `FLAT_DIRECTION` (ρ = −1.000). There the
compiled and numpy paths (`RIETX_COMPILED=0`) agree on every value but not on the esds of the
other width terms: W 0.003032(58) against 0.00303(12), U 0.00399(15) against 0.00399(21). The
`FLAT_DIRECTION` message also differs: only the numpy path appends "Flagged in stages:
lines_axial, biso." That points at `statistics.normal_covariance`'s `rcond` cut landing on
either side of the flat eigenvalue, by path. Not reproduced in a test yet.

**Practice (recalled, not checked this session).** GSAS-II refines one combined SH/L. FullProf
refines S_L and D_L separately. TOPAS's full axial model takes the slit and Soller dimensions,
not these ratios. Finger, Cox and Jephcoat (1994, *J. Appl. Cryst.* **27**, 892) define both.
Read the paper for whether the symmetry is the model's or this implementation's before
choosing a fix.

## Tasks

- [ ] Read Finger, Cox and Jephcoat (1994) on the S ↔ H symmetry, and check `profiles/fcj.py`
      against it.
- [ ] Decide the fix with the maintainer: `lab_calibrate` frees S/L alone with H/L held at
      its declared value; or one combined parameter, as GSAS-II has; or a finding when both
      are free.
- [ ] Rewrite the two `help.py` entries to say the pair is interchangeable, and follow a
      changed preset into the skill's `lab_calibrate` row (`docs/skill/rietx/SKILL.md`, the
      presets table) and the calibration guide's axial paragraph.
- [ ] Look for the class's siblings: any other pair of parameters the model treats
      symmetrically, where a fit can land on either assignment.
- [ ] Reproduce the esd difference between the compiled and numpy paths in a test, or show
      it cannot happen once the pair is no longer both free.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_examples.py -k calibrate -n auto --dist loadgroup
```

## Handover log

- **2026-10-19, filed by WP-1986's sixth session.** No open WP owns the axial ratios: a
  `git grep` for `axial_sl`/`axial_hl` over `docs/wp/` on `origin/main` finds only closed WPs
  (0402-0605, 1014, 1018), and WP-1460 (one finding per degeneracy) is about ridges reported
  once per pair, not about two separate minima. Measured on `[dev]`, darwin/arm64, against
  `origin/main` at `2df48c95` plus WP-1986's branch.
