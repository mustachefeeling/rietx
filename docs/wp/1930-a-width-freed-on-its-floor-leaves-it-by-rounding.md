# WP-1930 — a width freed on its floor leaves it by rounding

Milestone: unscheduled · Status: 🔄 2026-10-09 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: —
Priority: P1 2026-10-08 — a published acceptance number (VALIDATION.md, the landing page) that `main` reproduces on no platform, χ²_red 12.48 on Linux against 9.69 on macOS, every assertion green; `profile.y` defaults to 0.0, its floor, and six preset plans free it there

## Goal

A stage that frees a softplus row sitting on its floor reaches the same
minimum on every platform, either because the row starts where its gradient
is order one or because the plan says why it stays held. The LaB₆ + cBN
acceptance case has one minimum, VALIDATION.md quotes it, and a bar tight
enough to see a 12.5 against 9.7 change guards it.

## Context

Issue #832 (mustachefeeling, 2026-10-08), found while investigating #831
(WP-1929). The third item of #836 (seed a floor row before freeing it, or
fire `SOFTPLUS_FREED_AT_FLOOR`) is the same work and lands here.

**The mechanism.** A softplus entry with `min=0` maps 0 to an internal
coordinate of about −27.6 (the `to_internal` clamp, physical 1e-12), where
dp/du ≈ 1e-12 and the Jacobian column is about 1e-8 of its neighbours. TRF
starts there with a gradient near zero, so whether a step ever lifts the row
depends on rounding. `TCHZ_DEFAULTS` has `"y": 0.0`
(`schemas/instrument.py:1036`), and `strategy/staged.py` frees
`instrument.profile.y` in six preset plans (lines 366, 387, 423, 452, 499,
552), so every default-instrument fit that runs one of them is exposed.

**What was measured** (#832's comment; Linux x86-64 WSL2 numpy 2.5.3, macOS
arm64 numpy 2.5.2 with Accelerate; each fit 1-4 s):

| tree | χ²_red | Rwp | LaB₆ wt % | `profile.y` |
|---|---|---|---|---|
| published (VALIDATION.md, landing page) | — | 0.1645 | 17.874 ± 0.314 | — |
| `d2f683a0`, both machines | 9.6615 | 0.16453 | 17.874 ± 0.314 | 0.0384 |
| `a3f9140a`, Linux | 12.4753 | 0.18696 | 17.656 ± 0.383 | 1e-12 (floor) |
| `a3f9140a`, macOS | 9.6917 | 0.16478 | 17.841 ± 0.314 | 0.0376 |

- The published row was written at `d2f683a0` (WP-1541's re-measure,
  2026-10-03), when both machines agreed. A bisect over all 77 first-parent
  merges to `a3f9140a`, on both machines, finds one step: **#700**
  (`c6eaff7d`, WP-1534, `Atom.biso` unbounded). Before it, the `biso` stage
  (where `profile.y` is still free, the free set being cumulative) lifts the
  row on both machines to one point. After it, Linux leaves it on the floor
  and macOS escapes in 60 iterations. The reporter's reading, not measured:
  unbounding Biso changes TRF's bound-distance scaling of those columns.
- The `profile` stage already ended 41 apart in cost before #700 (289199.582
  against 289158.745), harmlessly.
- **Every assertion in `test_acceptance_lab6_cbn.py` passes at both minima**
  (8 of 8). Nothing asserts χ², and the Rwp bar is a factor of 4
  (0.081-0.324). The nightly slow suite runs on Linux, so it passes at 12.48.
- **Seeding probe (option a).** Lifting `profile.y` at the start of the
  `profile` stage (to ln 2 internal, to 0.05°, or `Stage(..., seed=0.05)`)
  gives one minimum on both machines at both trees: χ²_red 9.8402, Rwp
  0.16604, LaB₆ 17.761 ± 0.312. It is a *higher* minimum, and there the
  Gaussian is clamped (Γ_G² < 0 at 98-100 % of points), so u, v, w are
  undetermined: esds `None` or ρ = ±1.000, `RESOLUTION_UNCONSTRAINED` in
  every arm. QPA, cBN cell and B x agree across arms to 5 digits. So seeding
  alone trades platform dependence for three dead columns; it would need the
  clamped triple held, or option (b) (free the row in its own short stage with
  what it trades against held).
- Same mechanism, milder, on BT-1 neutron: `profile.y` on its floor on both
  machines, at a different internal coordinate (WP-1929's case).

**Checked against the tree at `a3f9140a`** (this worktree's `[dev]` venv,
macOS arm64): the macOS row reproduces to every printed digit. χ²_red
9.6916891, Rwp 0.16478432, `profile.y` 0.037593 ± 0.001422, `profile.x`
0.003082, `w` 7.48e-6, diagnostics `CAPILLARY_OFFSET_UNAVAILABLE`,
`DISPERSION_NEGLECTED`, `RESOLUTION_NOT_POSITIVE`,
`RESOLUTION_UNCONSTRAINED`. The Linux row was not reproduced here (no Linux
machine; the nightly does not print χ²).

**Decided 2026-10-08 (maintainer), after a precedent search.**

- **Package:** a stage that frees a softplus row sitting on its floor starts
  it a short way inside, through `Stage.seed`'s existing path. This is #836's
  third item. The seed's size and where it comes from are this WP's to
  measure and state in the docstring.
- **LaB₆ + cBN:** option (a) with the Gaussian held. `profile.y` starts
  inside its floor, and u, v and w are held, because at that minimum the data
  cannot determine them (Γ_G² < 0 at 98-100 % of points). Option (b) has no
  precedent found. Option (c) is refused: on macOS the data put `y` at
  0.0376 ± 0.0014, 26σ from zero.
- **Order:** the reporter measures (a) with the Gaussian held on both
  platforms before it is adopted, then VALIDATION.md's row is re-measured.
  Asked on the issue the same day.

The precedents: MINUIT warns that a transformed parameter at its limit sees
a zero derivative and can stay blocked there, which is this WP's mechanism.
TOPAS gives width parameters a positive minimum (`pv_fwhm` 1e-6, `la` 1e-5,
`lh`/`lg` 0.001; Technical Reference Table 2.1) and applies limits inside
its solver, so a parameter at its minimum still sees its real slope. GSAS-II
sets no limits by default. scipy's TRF moves a start strictly inside its own
bounds, but rietx's floor is the softplus transform and not a scipy bound
(`internal_bounds` maps a lower bound ≤ 1e-12 to −∞), so that protection
does not apply.

**Measured 2026-10-09** (this worktree's `[dev]` venv, macOS arm64; the
handover log has the tables).

- **Rounding picks the minimum on one machine.** On the shipped plan,
  multiplying `w`'s start by (1 + k·1e-14) for k = ±1, ±3, ±7, 20 put five
  of seven starts at χ²_red 12.4753, `y` on its floor: Linux's number to
  every digit. The unperturbed macOS start is the minority outcome.
- **#700 is the trigger, not the cause.** With `biso` bounded (0, 25) again,
  k = 0 gives the published 9.661528, and k = −1 still lands on the floor
  (12.95). The floor trap predates #700, which moved where the coin lands.
- **Exposure.** Six presets free `instrument.profile.y` on its floor in
  their `profile` stage, on all three instrument presets, and
  `lab_sample_refine` frees the four phase widths on theirs. Extinction,
  roughness and the magnetic widths were already seeded. A hump's height
  (counts) and an extra peak's area are the floor rows left with no size.
- **The held protocol** reaches χ²_red 10.1518150 at every seed from 0 to
  0.05° and every perturbation, the reporter's two-platform 10.15182. BT-1's
  `y` goes back to its floor from every seed (χ²_red 1.9279825 throughout).
- **The seed is 1e-3°, not 0.05°.** At 0.05° nine synthetic suites whose
  true width is zero ran out of iterations or moved, and the free-Gaussian
  plan stopped at 9.84. At 1e-3° all nine pass unchanged and the free plan
  reaches 9.661408 at every perturbation, with `w` on its floor and the
  resolution diagnostics firing, so holding the Gaussian still stands.

### Inherited

(empty)

## Non-goals

- Which esds a floor row's neighbours report: WP-1929.
- A coefficient read off its floor after the fit: WP-1914.
- The PVII/FPA peak-shape gap the suite's own comments name as why Rwp is
  worse than TOPAS's.

## Tasks

- [x] Reproduce the Linux minimum on one machine: the `biso` stage started
      from each platform's `profile`-stage end state, or the probe the
      reporter offers. Confirm or refute the bound-scaling reading of #700.
- [x] Count the exposure: of the acceptance suites and the six presets, which
      free a softplus row at its floor, and which of those end on it.
- [x] The decided protocol on LaB₆ + cBN, option (a) with u, v and w held,
      measured on both platforms (the reporter's run, or this WP's on Linux
      CI), and on BT-1 to see whether it moves.
- [x] The package side: `Stage` seeds a floor row it frees (#836 item 3),
      through `Stage.seed`'s existing path, with the seed's size and source in
      the docstring. A diagnostic only if a caller can still free one unseeded.
- [ ] A χ² or Rwp band on `test_acceptance_lab6_cbn.py` tight enough to see
      12.5 against 9.7 (the reporter suggests Rwp within 2 % of the
      re-measured value), run on both nightly platforms. *Landed and green
      on macOS 2026-10-09; the Linux nightly after merge is the second run.*
- [x] Re-measure VALIDATION.md's row and the landing page's copy on the
      chosen protocol (`docs/landing/README.md` says how the page's numbers
      are rebuilt).
- [x] Tests, with obs/calc/diff PNGs to `tests/output/`.
- [x] Skill: if a diagnostic lands, its `references/judging.md` row; if the
      protocol is a rule an agent applies by hand, SKILL.md §2's seed rule.
      *The row went to `diagnostics.md`, beside the stage codes, paid for by
      two cuts; no hand rule, since the package now seeds.*

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_lab6_cbn.py tests/test_acceptance_wavelength.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

Linux and macOS reach the same χ²_red on LaB₆ + cBN to 1e-4 relative, the
new band fails at 12.48, and VALIDATION.md's row is reproduced to every
printed digit on both.

## References

- Issues #832, #831, #836; PR #700 (WP-1534).
- WP-1541 (the re-measure the published row came from), WP-1929, WP-1914.
- TOPAS 5 Technical Reference, § 2.5 and Table 2.1 (default limits); ROOT
  `TMinuit` documentation, parameter limits.
- Coleman, T. F. & Li, Y. (1996). *SIAM J. Optim.* 6, 418-445 (the
  trust-region reflective method scipy's TRF implements, strictly feasible
  iterates).

## Handover log

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #832,
  and #836's third item). Checked against the tree at `a3f9140a`: the macOS
  minimum reproduces to every printed digit; the Linux one was not tried. No
  open WP owns it: 1534, whose merge is the bisect's step, is closed; 1541,
  which wrote the published row, is closed; 1929 takes the esds and 1914 the
  after-fit reading. Rated P1 for the published number no platform
  reproduces. Decided the same day by the maintainer: seed a floor row a
  stage frees, and option (a) with the Gaussian held for LaB₆ + cBN, measured
  by the reporter on both platforms before it is adopted.
