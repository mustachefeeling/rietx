# WP-1458 — a tick with nothing behind it moves the low-angle boundary

Milestone: unscheduled · Status: ✅ 2026-09-24 — all four tasks landed from outside in PR #456; the boundary is the first reflection the data sees, judged over all its line images
Depends on: — (1327 soft: its magnetic tick row is the case that found it)

## Goal

`LOW_ANGLE_UNMODELLED` places "below the first reflection" at the lowest
reflection that carries calculated intensity the data could see. A phase, a
declared peak or a magnetic row that puts only an empty tick below the first
real line no longer silences it.

## Context

Issue #436 (2026-09-23), found re-running WP-1327's acceptance for PR #433
under a null magnetic group. The mechanism is on `main` and needs no
magnetism.

**The mechanism.** `refine._first_reflection_fwhm` (`refine.py:5235` at
`8fbafe5`) takes `min` over every list in the `ticks` dict that
`_build_result` made (all phases, every emission line, plus
`components.EXTRA_TICK_KEY` for declared peaks), by position only.
`_low_angle_diagnostics` (`refine.py:5266`) measures
`[two_theta_min, first_tick − 2·FWHM)` and returns `[]` when that region
holds fewer than ten channels. The docstring's rule is "the region no
reflection — of any phase, any emission line — can reach". The code applies
it as "no tick", and a tick with nothing behind it reaches nothing.

**Checked against the tree at `8fbafe5`** with the issue's script:
synthetic LaB6 from `tests/test_refine_synthetic.synthesize()`, plus an
unmodelled Gaussian hump at 4.0° (400 counts, σ 0.3°) below LaB6 (100) at
5.72°, `plan="mccusker_default"`.

| fit | Rwp | `LOW_ANGLE_UNMODELLED` |
|---|---|---|
| LaB6 alone | 0.1357 | fires: "537 channels below the first reflection (5.72° − 2×FWHM = 5.68°) carry a mean weighted-squared residual 78.68, 6.80× the whole-pattern reduced χ² (11.58)" |
| LaB6 + a cubic dummy, a = 30 Å, `scale` fixed at 1e-14 | 0.1357 | silent |

Both reproduce the issue's numbers exactly. The dummy's lowest tick is at
2.51°, below the data, so the region holds no channel.

**Cases that meet it without a contrived dummy**, from the issue: a minority
phase with a small or fixed scale and a large cell; a phase
`PHASE_UNCONSTRAINED` is holding (WP-1301 keeps its ticks); a declared
`PeakComponent` at low angle; and a magnetic row on a group the data does
not support (#433, the `"<phase> (magnetic)"` tick row).

**The design choice, which is this WP's to make and measure.** Two readings
of "a reflection that can reach the region":

- **Per phase, on the existing authority.** Drop the ticks of any phase
  whose `CompiledModel.phase_support` is below
  `forward.PHASE_SUPPORT_SIGMA` (1.0). This adds no new threshold, and
  `phase_support`'s docstring asks for no second opinion on "can the data
  see this phase". It covers the dummy and the held phase. It does not cover
  a supported phase's empty magnetic row, or a declared peak whose area sits
  at zero, since both belong to rows that are not a phase's.
- **Per reflection.** The lowest tick whose peak height at the fitted values
  exceeds `PHASE_SUPPORT_SIGMA`·σ locally: the same threshold one rank down.
  It covers every case above, but needs per-reflection heights, which the
  ticks dict does not carry. Look for where `phase_component` builds them
  before adding a second evaluation.

Measure both on the four cases above, and on the shipped acceptance fits
where the code fires today, before choosing. A choice that silences one of
those is a regression.

**The skill row changes with it.** `docs/skill/rietx/references/diagnostics.md:56`
says the region is read "every phase, every emission line". The row, and
`docs/manual/using/results.md:499`, say what the new boundary is.

## Non-goals

- The two remedies the message offers, and the 3× threshold on the
  residual. Only the boundary moves.
- Layer 0's `unmatched_calc` for the dummy's positions, which is right as
  it stands.

## Tasks

- [x] Measure both readings on the four cases and on every fixture where
      the code fires at `8fbafe5`; record the table in this file.
- [x] Implement the chosen boundary in `_first_reflection_fwhm`, and update
      its docstring's rule to say what the code does.
- [x] Tests: the issue's pair (fires without the dummy, and now fires with
      it too); a held phase's ticks do not silence it; every existing
      `LOW_ANGLE_UNMODELLED` test unchanged.
- [x] Skill: the `LOW_ANGLE_UNMODELLED` row in `references/diagnostics.md`
      names the new boundary; re-sync with `rietx skill --install . --copy`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_low_angle_region.py -q
.venv/bin/python -m pytest tests/test_skill.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

None beyond the issue and WP-1301's `phase_support`; no physics changes.

## Handover log

### 2026-09-24 — done from outside: the boundary is the first reflection the data sees

All four tasks landed in PR #456, merged as `dab23473`. It came from an outside
contributor with a `WP-1458:` commit and no touch of this file. Issue #436 was
named without a closing keyword, so it was closed by hand with a note naming
the PR.

`LOW_ANGLE_UNMODELLED` now bounds its region at the lowest tick whose
reflection reaches `PHASE_SUPPORT_SIGMA` (1σ) on some emission line. That is
`phase_support`'s quantity and threshold, read one reflection at a time, so no
new constant entered. A tick with nothing behind it no longer moves the
boundary. The cases are a phase held at a vanishing scale, a declared peak at
zero area, and a reflection whose |F| is zero.

**Decided (by the contributor, from measurement).** Neither of this WP's two
readings works on its own. Judged per phase, the issue's own pair stays silent:
the dummy's summed curve reaches 1.23σ from two coincident reflections at
0.62σ each. Judged per image, the published BT-1 Cu(311) Nd₂Ru₂O₇ fit goes
silent. Its λ/2 (111) image carries 0.095σ beside its primary's 2.86σ, and
dropping the image grows the region from 36 to 185 channels and moves the
ratio from 5.92× to 2.66×. The reflection separates them, judged over all its
line images, which is how `tick_hkl` already pairs a tick with its hkl.

Task 1's table, measured by the contributor on the synthetic LaB6 of
`test_refine_synthetic.synthesize()` with a 400-count hump at 4.0°
(`mccusker_default`, Rwp 0.1357 in every row):

| case | before | per phase | per image | per reflection (shipped) |
|---|---|---|---|---|
| LaB6 alone | fires 6.80× | fires | fires | fires 6.80× |
| + a = 30 Å dummy, scale fixed 1e-14 (1.23σ) | silent | silent | fires | fires 6.80× |
| + same dummy, held by `PHASE_UNCONSTRAINED` | silent | fires | fires | fires 6.79× |
| + same dummy, scale free (1.12σ) | silent | silent | fires | fires 6.79× |
| + `PeakComponent` at 3.3°, area 0 | silent | silent | fires | fires 6.80× |
| doubled cell, half-order ticks with \|F\| = 0 | silent | silent | fires | fires 6.80× |

Of every fixture in the suite, eight fire at `54a049d2` (ten fits). All ten
still fire with the boundary unchanged. The only disagreement among the
readings is the per-image silence on the λ/2 fit above. 34 other fits moved
their boundary upward, and none started or stopped firing.

**What the merge makes possible.** `CompiledModel.reflection_support` and
`extra_peak_support` give each reflection's and each declared peak's strongest
calculated point in σ. `_build_result` builds `tick_support` beside `ticks` and
`tick_hkl`, through the same mask and sort, #433's magnetic row included. It is
a local and not a result field.

**What it deliberately does not do.** The two remedies, the 3× ratio and the
ten-channel floor are unchanged. Exactly coincident reflections are judged one
by one. Summing a multiplet would make the dummy case silent again, with the
boundary at 3.24°. `multi.py` has no low-angle diagnostic before or after, so a
joint fit still gets none; that belongs with WP-1344.

**Measured on the merged tree** (darwin arm64, python 3.12, `[dev,jax]`, a
suite from another repository sharing the machine): fast suite 6087 passed,
89 skipped (#456 alone on `14239188`); the whole `-m slow` suite once, on
`14239188` + #452 + #456, whose tree is the one main reached at `dab23473`:
197 passed, 7 skipped, 1 xfailed.

- **2026-09-24** — created, from the 2026-09-24 issue triage (issue #436).
  Checked against the tree at `8fbafe5`: both fits reproduce the issue's
  Rwp and message exactly, and the boundary is taken by position at
  `refine.py:5251-5254`. Next: measure the two readings before choosing.
