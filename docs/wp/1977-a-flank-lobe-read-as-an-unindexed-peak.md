# WP-1977 — a flank lobe read as an unindexed peak

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-15 — a flag that fires wrongly: it drives `add_impurity_phase` on two round-robin fits

## Goal

Layer 0 calls a residual peak unindexed only when no modelled reflection
explains it. A lobe of misfit on the flank of a strong peak counts as
explained.

## Context

**What Layer 0 does today** (`report/layer0.py`, `build_layer0`). It finds
positive residual peaks of Δ/σ ≥ 5 (`residual_peak_indices`). A peak with no
tick within `LAYER0_MATCH_TOL_DEG` (0.08° 2θ) becomes `unmatched_obs`. The
window is a fixed angle. It does not scale with the peak's width, and it
does not look at the residual's shape around the peak.

**What exposed it (WP-1908, PR #927).** Ticks used to sit about 0.11° below
the peaks on cpd-1c, because they lacked the displacement shift. After
WP-1908 the ticks sit on the peaks. Six residual peaks on cpd-1c (31.62°,
36.08°, 47.40°, 56.46°, 62.70°, 67.80°) sit 0.15-0.19° below strong zincite
ticks, on calculated curves of 650-1860 counts. They are the flank lobes of a
profile misfit. The old, misplaced ticks put them inside the window by
accident. Now they read as unindexed peaks. Across twelve `qpa_plan` fits,
`unmatched_obs` moved in both directions (cpd-1c 6 → 11, cpd-4 30 → 18).
Layer 1 then suggests `add_impurity_phase` on cpd-1c (0.30) and cpd-1f
(0.40), and neither specimen has an impurity. WP-1908's Tasks hold every
before/after number.

**Second consumer of the constant.** `EXTRA_PEAK_ON_REFLECTION` reads
`LAYER0_MATCH_TOL_DEG` to ask whether a declared component sits on a
predicted line. A change to the constant moves that check too, so the WP
either keeps the two together or splits them on purpose.

**What a result carries.** `build_layer0` takes a `RefinementResult`, not the
compiled model. It has `ticks`, `tick_hkl`, `y_calc` and the residual. It has
no per-reflection width. A width-scaled window needs the width from
somewhere, such as the local FWHM of `y_calc` around the tick or a new
companion field.

**Open questions, unmeasured.**

- A width-scaled window (k·FWHM), a test of the residual's sign pattern
  (a lobe beside a strong calculated peak with an opposite lobe on its other
  side is a shape or position misfit), or both.
- What GSAS-II, FullProf and TOPAS do for the same question. Search before
  designing (root CLAUDE.md, prior art).

## Non-goals

- Tick placement. WP-1908 settled it.
- Layer 1's action ranking, except where a changed `unmatched_obs` moves it.

## Tasks

- [ ] Reproduce on cpd-1c under `qpa_plan` over 5-150°. List each
      `unmatched_obs` with its distance to the nearest tick, that tick's
      calculated height and the local FWHM.
- [ ] Survey prior art for the same test. Record what each code does.
- [ ] Choose and land the rule. Keep `EXTRA_PEAK_ON_REFLECTION` on the same
      authority or split it with a reason.
- [ ] Re-measure WP-1908's twelve fits. A real impurity must still read as
      unmatched: use a synthetic pattern with a second phase added.
- [ ] Tests + obs/calc/diff PNGs of the flank-lobe cases to `tests/output/`.
- [ ] Skill: the `unmatched_obs` reference row, if what it means changes.

## Acceptance

On cpd-1c and cpd-1f under `qpa_plan`, no `unmatched_obs` sits on the flank
of a strong reflection, and Layer 1 does not suggest `add_impurity_phase`.
On a synthetic pattern with an unmodelled second phase, its strongest
isolated peaks still read as `unmatched_obs`.

## References

- WP-1908, § Tasks last item and its 2026-10-13 handover entry.
- PR #927 § Not done.

## Handover log

- **2026-10-15** — filed from WP-1908's open question (PR #927). No open WP
  owns Layer 0's matching window: a search of the open WPs for unindexed and
  unmatched peaks found none on this question.
