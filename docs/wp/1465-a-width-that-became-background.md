# WP-1465 — a phase width that became background, and an absorption screen that never ran

Milestone: unscheduled · Status: ⬜
Depends on: —
Priority: P2 2026-09-25 — a width grows 15× and Rwp 7.5× with no warning, on the series path; every Le Bail and Pawley report reads 0.0 for a screen that never ran

## Goal

A phase whose width grows until it stands in for something the model lacks
(a second phase, a diffuse signal, the background) is named by a finding
before `STRAIN_UNUSUALLY_LARGE` trips at 1.5°. And a fit where the background
absorption screen had nothing to screen says so, rather than reporting 0.0.

## Context

Issue #451 (2026-09-24), a design proposal from a real operando series and a
synthetic reproduction. The skill already carries the mechanism
(`references/diagnostics.md`, the `BACKGROUND_ABSORPTION` row: "a phase width
can be the absorber"), and WP-1130 § Finding 2 measured it: a cubic phase at a
5.0°/cosθ Gaussian FWHM against a 0.15° instrument, "a second background".
Nothing in the code fires on it.

**Two gaps, both checked at `07952d4e`.**

1. **The absorption screen has no target in Le Bail or Pawley mode, and its
   empty state reads as a measurement.**
   `optimize.statistics._structural_targets` screens free paths under
   `phases.` ending `.biso`, `.scale`, `.occ`, or holding `.adp.`. Le Bail
   and Pawley force-fix every one of those (`mode_fixed`), so
   `block_projection_r2` returns `{}`. `report/background.py:107-123` then
   sets `worst_absorption = 0.0` and `worst_absorption_path = None`.
   *Reproduced* on the LaB6 test model (`tests.test_schemas.make_lab6`,
   λ 0.4139 Å, 3-30°, 8-term Chebyshev, cell and `lor_strain` free):

   | mode | `identifiability.background_absorption` | `report.background.worst_absorption` |
   |---|---|---|
   | rietveld | 3 rows, worst 0.052 (`atoms.0.biso`) | 0.052 |
   | pawley | `{}` | 0.0 |
   | lebail | `{}` | 0.0 |

   The issue named Pawley only. Le Bail is the same gap. A Rietveld stage that
   frees no scale, Biso, occupancy or ADP (background only, say) produces the
   same `{}`; that case is unmeasured. This is WP-1076's rule (a field whose
   empty state reads as an answer; the honest empty state is `None`). The
   readers are `report/layer0.py:107` (a `>=` against
   `BACKGROUND_ABSORPTION_NOTABLE`), `report/layer2.py:505-509` (a
   confidence and a sentence), and the skill row.

2. **No screen has a phase width as its target.** `lor_strain`,
   `gauss_strain`, `lor_size`, `gauss_size` (and a Stephens block,
   `phases.i.microstrain.dof.k`) are never projected onto the background
   block. `HIGH_CORRELATION` cannot see the trade, since it is pairwise ρ and
   `block_projection_r2`'s own docstring calls that the wrong statistic
   against a many-term block. `_structural_targets` is "the one list both
   screens read", so adding the widths there changes `BACKGROUND_ABSORPTION`
   on every fit that frees one. That needs measuring before it lands.

**The reporter's synthetic** (script in the issue, about 25 s for 33 fits):
phase B, the LaB6 model with the cell +0.4 %, grows from 0 to 50 wt % across
11 patterns. Each pattern is fitted cold with a *one-phase* model (13-term
Chebyshev; cell, `lor_strain`, and in Rietveld scale and Biso). A two-phase
Pawley arm is the control.

| f_B | 1-phase Pawley ε_L | 1-phase Pawley Rwp | 1-phase Rietveld Rwp | max R² (Rietveld) | 2-phase control Rwp / ε_L |
|---|---|---|---|---|---|
| 0.00 | 0.020 | 1.56 % | 1.56 % | 0.064 | 1.55 % / 0.020 |
| 0.20 | 0.139 | 7.97 % | 7.98 % | 0.130 | 1.57 % / 0.020 |
| 0.50 | 0.305 | 11.74 % | 11.87 % | 0.207 | 1.57 % / 0.020 |

No warning-level code fires on any one-phase fit. The width grows 15× and
Rwp 7.5×. Not reproduced here: the table is the reporter's, and the first
task re-runs it.

**The reporter's own follow-up narrows it** (issue comment, 2026-09-24). On
the operando series, with the background *fixed* from a measured empty-cell
scan, the widths still grew 2-4× their first-scan value at a lower Rwp. So
there the width was filling a broad signal above the physical background,
not trading with a polynomial, and a width-versus-background projection
(gap 2) would not have fired. What would have fired is a **series** trigger:
a phase width exceeding k× its early-scan value while Rwp rises over the
same scans. It needs no Jacobian. The reporter now ranks it first, gap 1
unchanged, gap 2 last.

**Where a series trigger sits.** `sequential.py` already derives series-level
findings from per-pattern results: `SEQUENTIAL_DISCONTINUITY` (a trajectory
jump), `SEQUENTIAL_PERSISTENT_FINDING` (`_persistent_diagnostics`, one code
on most patterns). A trend in a width trajectory is a third reading of the
same trajectories. `references/series.md`'s "microstrain evolves" rule
stays: a width may legitimately grow, so the finding points at the rule
rather than judging.

**Two refusals the issue already made, both kept.** No width cap: WP-1130
measured that a binding cap moves the background the right way and Rwp the
wrong way, so it cannot be calibrated from Rwp. No change to
`STRAIN_UNUSUALLY_LARGE`: its text is right, and it fires late.

### Inherited

(none yet)

## Non-goals

- The instrument-profile-versus-measured-width census and the meaning of
  `status`: WP-1336 (#243, #249).
- A model-free background estimate: WP-1130, closed 🛑 on its own gate.
- Deciding *what* the width absorbed. The finding names the growth and the
  rule to read; the phase search is the caller's.

## Tasks

- [ ] Re-run the issue's synthetic on this tree, and record the ε_L, Rwp and
      code table beside the reporter's. Add the per-phase width R² against
      the background block for both modes (the Jacobian is on the fit;
      the reporter could not serialize it).
- [ ] Gap 1: `worst_absorption` and `absorption` take `None` where no target
      was screened, and the layer-0/layer-2 readers and the report text say
      "not measured". Decide whether a Rietveld stage with no structural
      target free is the same case, and measure it.
- [ ] The series trigger: a finding when a phase width exceeds k× its
      early-pattern value while Rwp rises over the same patterns. Choose k
      and "early" from the synthetic (15× at f_B 0.5) and the operando
      numbers (3.4× at onset), and measure its firing rate on the series the
      suite already runs, where the widths are right.
- [ ] Gap 2, only if the first task's R² separates the soak from a clean fit:
      widths as absorption targets, either in `_structural_targets` or as a
      second target list, with the effect on `BACKGROUND_ABSORPTION` counted
      on the acceptance standards before and after.
- [ ] Tests: the synthetic (slow-marked if it stays near 25 s), a Le Bail
      and a Pawley report asserting `None`, and a clean series asserting
      silence. Obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: the `BACKGROUND_ABSORPTION` row in `references/diagnostics.md`
      says "not measured" for Le Bail and Pawley; a row in
      `references/series.md` for the new finding, beside the "microstrain
      evolves" rule.

## Acceptance

On the synthetic, the one-phase chain carries the series finding from the
onset and the two-phase control does not. A Le Bail and a Pawley fit report
`None`, not 0.0. The suite's existing series fire nothing new.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #451 and its 2026-09-24 comment (the fixed-background re-fit).
- WP-1130 § Finding 2 (the width as a second background, measured).
- WP-1076 (an empty state that reads as an answer).
- Stephens, P. W. (1999). *J. Appl. Cryst.* 32, 281-289 (the anisotropic
  strain block a width screen must include).

## Handover log

- **2026-09-25** — created, from the 2026-09-25 issue triage (issue #451).
  Checked against the tree at `07952d4e`: gap 1 reproduced in Pawley and
  also in Le Bail (both `{}` and 0.0; Rietveld 0.052 on the same pattern),
  gap 2 read in `optimize/statistics.py:205-230`. The synthetic table and
  the operando follow-up are the reporter's and are not reproduced here.
  Next: the first task.
