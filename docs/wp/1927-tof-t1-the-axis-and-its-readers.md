# WP-1927 — TOF T-1: the time-of-flight axis and its readers

Milestone: unscheduled · Status: ⬜
Track: The specimen is not an angle, and the neutron follow-through
Depends on: —
Priority: P2 2026-10-11 — a fence decision with a named user and a branch ready to rebase, no longer held by the index cap (WP-1920); the forward-model cuts wait on it

## Goal

A neutron time-of-flight bank is read into rietx with its axis, and refused by
name everywhere a pattern would be computed. No forward model changes.

## Context

Issue #193 (mustachefeeling). The fence ruling of 2026-09-24 held TOF until
the magnetic milestone closed, and then took it on the contributor's
clean-room branch (`tof-cleanroom-20260923` or its successor) in cuts: T-1
the axis and the readers, T-2/T-3 profile and spectrum, T-5 multi-bank.
**Decided 2026-10-08: T-1 is taken now, alone.** The ruling held TOF to keep
a second large arm out of review beside the magnetic queue. That queue has
largely cleared, and T-1 touches neither the forward model nor the magnetic
code. T-2/T-3 and T-5 stay behind the fence until the magnetic milestone
closes (ROADMAP § v2+). At most one TOF PR is open at a time.

What T-1 carries, from the reporter's comment of 2026-10-07:
- The axis and the readers. A bank is read, and refused by name wherever a
  pattern would be computed.
- **#442 is decided inside this cut** as "a bank carries no CW rows", as the
  2026-09-24 ruling asked. The CW width rows `instrument.profile.u…y` do not
  exist on a bank, so WP-1414's "matched, not freed" rule has nothing to
  match there.
- **The legacy LANSCE layer** sits in `io/legacy/` on the branch. The
  2026-09-24 ruling left `io/legacy/` against `io/formats/` to this cut's
  review.
- **The NPDF fixture question does not arise in T-1.** Its legacy tests are
  synthetic and the real-calibration fixture is left out.

Checked against the tree at `5d1f5f67`: the GSAS `.prm` reader refuses a TOF
bank by name (`io/instrument_profile.py:218`). A reader that opens a pattern
is added through `src/rietx/io/CLAUDE.md`'s recipe, and its repairs follow the
root CLAUDE.md reader invariant (a repair the reader can say it made, the
axis never trusted). #618 (Mantid instrument values: with provenance, never
the files) sits beside the fence and is not part of T-1.

### Inherited

- **2026-10-11, from WP-1920 (closed, PR #906): the API index has room, and
  where T-1's names go is decided.** `api.md` is 33 292 B under one 39 000 B
  ceiling for every `api*.md`. The maintainer placed T-1's names by shape.
  `read_gsas_tof_iparm` leaves `SKILL_EXCLUDED_VERBS` for a row in
  `api-io.md`, beside the other readers of another program's file.
  `TOFSource`, `ProfileTOF` and `IncidentSpectrum` go to a new `api-tof.md`,
  one `TECHNIQUES` entry in `docs/skill/make_api_index.py`, which this WP's PR
  creates. `PatternData.tof` goes through `TECHNIQUE_FIELDS`, as
  `Phase.rigid_bodies` does. `Instrument.source` accepting a `TOFSource`
  renders in `api.md` as before. This differs from the reporter's default on
  #808, which kept the classes in `api.md`.

- **2026-10-11, from the issue triage (#193): the `read_gsas2_instprm` ruling
  of 2026-09-18 is recorded only in WP-1419.** WP-1419's Inherited (about line
  360) rules one reader dispatching on the file's own `Type`, never a `_tof`
  sibling. `io/instrument_profile.py` already reads `Type`, keys
  `CW_TYPES`/`HISTOGRAM_TYPES`, and refuses a flight-time bank by name, and
  that refusal is the branch. If the two halves return different types,
  dispatch moves up a level and discriminates on `kind`. The reporter's branch
  keeps two readers and offered on 2026-09-18 to make it one, "one commit" if
  asked. This WP's tasks carry the readers and not this spelling. Checked
  against the tree at 7d9be3cb: `read_gsas2_instprm` is at
  `io/instrument_profile.py:1610`, and this file had no "instprm" line.

- **2026-10-11, from the issue triage (#678): the 2026-10-08 thread decisions
  on the superspace cuts are in no WP file.** This WP only orders N-W2 and N-W3
  after T-1. Decided on the thread: N-W2 opens with a check of spgrep's little
  group and small irreps at an irrational k (a rational k reproduced at its
  float value, a near-rational k that must not snap), and #682's three
  follow-ups (the `number` field, function-level references, the hand-typed
  775/24 counts) fold into N-W2's PR. Not decided: the reporter's amendments
  A1-A6 (q-determination through M-8, an N-W3a/b split, one `Modulation.q`,
  Laue-invariant classes, k₂ on the residue, satellite widths). They are
  taken when N-W2's and N-W3's WPs are cut, and the cutter reads the thread.
  A1's answer lands in WP-1418's #795 entry. Checked against the tree at
  7d9be3cb: `crystallography/superspace/` holds `generation.py`,
  `operators.py` and `symbols.py` only.

- **2026-10-13, from WP-1908 (PR #927): a tick's drawn angle is one function,
  and a time-of-flight axis owes it a twin.** `CompiledModel.apparent_two_theta`
  is where the forward model reads the angle at which a peak is drawn.
  `CompiledModel.reflection_positions` (WP-1908's post-merge review round)
  is the walk over a phase's cell and emission lines that
  `refine._build_result`, `multi._ticks` and `viz.snapshot.stage_ticks` all
  call, and `report.satellites` calls `apparent_two_theta` itself. A
  flight-time axis draws a peak at a time, so neither can serve it. The TOF
  position map needs its own twin of that pair, with the three builders
  choosing between them in one place, or ticks drift from the peaks they label
  again. WP-1908's edits sit at `forward.py` near the position memo in
  `phase_peaks`, the tick loops in `refine.py` and `multi.py`, and
  `viz/snapshot.py`. Checked against #911's hunks: none touches those lines.

## Non-goals

- The TOF profile, spectrum and forward model (T-2/T-3), multi-bank (T-5).
- The constant-wavelength reads #362 lists (`CompiledModel.tt`,
  `line_wavelengths`, `sigma_measured`): they wait for a second compiled
  model, which T-1 does not build.
- Modulated structures (#678): their N-W2 and N-W3 cuts open after this one
  merges.

## Tasks

- [ ] The TOF axis and the readers, from the branch rebased on `main`
- [ ] A bank refused by name at every compute entry point, each refusal tested
- [ ] #442: a bank carries no CW rows, with the joint-fit case it names tested
- [ ] `help.py` rows for any new reader option; `io.readers.PATTERN_FORMATS` and `capabilities()` arms
- [ ] Tests (synthetic banks only; no real-calibration fixture)
- [ ] Skill: a reference row for reading a TOF bank and what it cannot yet do

## Acceptance

A synthetic TOF bank reads with its axis, every compute entry point refuses it
by name, and the joint case of #442 is silent because no CW row exists.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issues #193, #442, #618, #362; the contributor's branch `tof-cleanroom-20260923`.
- WP-1414 ("matched, not freed"), WP-1134 (CW neutron).

## Handover log

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #193).
  Checked against the tree at `5d1f5f67`: the `.prm` reader's TOF refusal is
  in place and no TOF reader exists; no open WP owns it: the fence held it,
  and WP-1419's TOF entry records the chain, never the cut. Decided
  2026-10-08 by the maintainer: T-1 now, alone. *Next:* the contributor's PR
  rebased on `main`.
