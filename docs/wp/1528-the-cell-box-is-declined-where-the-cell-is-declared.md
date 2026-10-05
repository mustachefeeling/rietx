# WP-1528 — the cell box is declined where the cell is declared

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-05 — was P4: #719, the post-solve clamp itself builds a zero-volume cell and fit() raises, so a Le Bail ladder loses that hypothesis

## Goal

`Cell`'s docstring says why its six parameters carry no default box, and issue
#283 closes on that reason.

## Context

Issue #283 reported a degenerate cell running away in the solver. The guard
landed under WP-1321 (`DegenerateCellError`, `CELL_DEGENERATE_PROBE`, commit
`0ae0e063`). A default box on `Cell` was tried and withdrawn (`178e6017`). WP-1321
is ✅, so what its fix did not cover is filed here.

**The reason, checked at `e3e6486a`:** a finite stored bound is the caller's
claim. `params.vector.cell_window` keeps it (`vector.py:~467-472`) and skips its
own support-based window, and `ParameterTable.bounds()` is ordered on purpose so
that nothing makes a side finite ahead of it (`:2344-2351`). A schema box would
therefore act on every free cell: it changes TRF's trust-region scaling even
when never hit (cpd-1c went from 82 to 400 iterations, 6.30 to 9.04 wt % with
windows on every phase, per the `cell_window` docstring), and it would appear in
`ParameterRow` and the `.rxt` document as a claim the user never made.

**What other programs do** (read, with gaps): TOPAS uses a value-relative
default window, a, b, c within Max(1.5, 0.995·Val − 0.05) to 1.005·Val + 0.05 and
angles within Val ± 0.2, read from a search summary of the manual; cctbx checks
validity (`unit_cell.is_degenerate`, `unit_cell_angles_are_feasible`) and
bounds nothing; FullProf limits are optional and per file. No program read
ships a fixed hard default box on a cell. GSAS-II, SHELXL, Jana2020 and scipy
were skimmed or not checked.

**Decided 2026-09-30:** keep the limit as a window built at table-build time
(`freeze_cell_windows`, `cell_window`, the post-solve `clamp_cell_runaway`) and
put no box on `Cell`. Still open, and only if a measurement asks for it: a
*visible* phase whose cell runs to a degenerate angle inside one stage. The
guard neutralises and counts each probe. If it needs anything, it is a finding,
not a bound.

### Inherited

- **2026-10-05, from the issue triage (issue #719): `clamp_cell_runaway`
  can itself build a zero-volume cell, and `fit()` then raises
  `DegenerateCellError`.** It clamps each free cell parameter to its own
  safety window (`CELL_SAFETY_FRACTION` 0.15, `CELL_SAFETY_ANGLE_DEG` 6.0)
  without asking whether the six make a cell, and `_run_stage` reads the
  result in `_answer_significance` → `phase_support` (`refine.py:3513`,
  `:3560`), outside the guards that wrap the solver. *Checked at `32ef5a6`*
  with the reporter's snippet (P1 Le Bail of a wrong cell on synthetic
  silicon, `[dev]`, Linux): `profile_only`'s 4th stage raises (the issue saw
  it one plan later). The stage starts at det +55.46; TRF returns lengths of
  −16200 to +1383 Å and angles past ±360°, every one det > 0, so no guard
  fires; the clamp puts all six on window edges and that corner has det
  −63.51. `multi.py:714` calls the same clamp. The reporter proposes no fix;
  restoring the stage's start cell (the WP-1301 collapse-restore precedent)
  or catching the raise where the answer is read is the maintainer's choice,
  and either keeps 1528's "a finding, not a bound".

## Non-goals

- Any new bound, window or clamp.
- Measuring how often a visible phase probes a degenerate angle since the guard
  landed: a separate WP if someone wants the number.

## Tasks

- [ ] `Cell`'s docstring (`schemas/structure.py:136-145`) states the reason above in a few sentences
- [ ] Skill: none

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Foadi & Evans (2011), the paper cctbx's header cites for the angle feasibility check (not read).
- Issue #283; WP-1321.

## Handover log

- **2026-09-30** — created, from the 2026-09-30 issue triage (issue #283).
  Checked against the tree at `e3e6486a`: the `Cell` fields are still bare
  `Parameter` objects and the guard is in place. No open WP owns it: WP-1321,
  which closed the guard half, is ✅.
