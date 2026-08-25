# WP-1202 — The help corpus, served and meta-tested

Milestone: v1.2 · Status: ⬜
Depends on: — (before WP-1203, which renders it)

## Goal

One authority for what a parameter, a peak flag, a plan field or a wizard field
*is*, with its unit, default and typical range, served to the GUI on the rows
that carry the thing and rendered into the manual from the same source. After
this WP a description exists in exactly one place.

## Context

Findings (2026-08-25):

- `title=` is the GUI's only help mechanism: 169 strings across the frontend,
  all hover-only, the longest 324 characters (`lib/controls.ts:141`). The two
  hand-written corpora are `lib/wizard.ts` (17 titles, instrument and import
  fields, pinned by `wizard.test.ts:178-207`) and `lib/controls.ts` (22
  titles, the indexing form, pinned by `controls.test.ts:55-60`).
- `ParameterRow` (`src/rietx/schemas/params.py:82-121`) carries `path, value,
  vary, lo, hi, transform, tie, locked, esd, mode_fixed` plus `refinable` and
  `held_because`. **No description, unit, default or typical range** exists on
  a parameter row anywhere, and nothing in `gui/src` says what `w`, `zero` or
  `biso` mean.
- `Field(description=)` exists in `schemas/indexing.py` (18) and
  `schemas/plan.py` (8) only; the GUI reads neither (`Plan.svelte` hard-codes
  its own titles for `max_iter`, `seed`, `strain_seed`, `lebail_cycles`).
- Prose the GUI already gets from the package: `PlanInfo` (`strategy/
  staged.py:446-467`: `title, description, modes, when_to_use`, bijection
  with `PLAN_PRESETS` pinned by `tests/test_params_surface.py:441-460`),
  `SearchPresetCapability`, engine descriptions, `PatternFormat.sniff/sigma`
  and `READER_OPTIONS[*].help` (`io/formats/base.py:141-155`). All of it was
  written for `capabilities()` consumers, not for a person.
- `PeakFlag` vocabulary: `schemas/indexing.py:428-442` (thirteen values);
  `PEAK_UNUSABLE_FLAGS` at `:472-474`; served as `flag_vocabulary` by
  `session.py:1442-1444` and never read by the client. The flags render as
  bare tokens with no tooltip (`Peaks.svelte:579-586`).
- The manual has no glossary; Part 1's guard (`tests/test_manual_api.py`)
  resolves dotted names and dot-paths and executes python blocks. Fenced
  constants are injected from the live package in `docs/manual/conf.py`.

Design:

- `src/rietx/help.py`: a frozen `HelpEntry(title, description, unit, default,
  typical, anchor)` and a registry keyed by **path family**, matched with the
  same `fnmatch` the plans use: `instrument.zero_shift`,
  `instrument.profile.[uvwxy]`, `instrument.geometry.*`,
  `instrument.background.c*`, `instrument.source.lines.*.wavelength`,
  `phases.*.cell.*`, `phases.*.scale`, `phases.*.atoms.*.{occ,biso,dof.*,
  adp.*}`, `phases.*.{gauss_size,gauss_strain,lor_size,lor_strain}`,
  `phases.*.preferred_orientation.*`, `phases.*.microstrain.*`,
  `phases.*.extinction.*` (the vocabulary the `ParameterTable` produces; the
  committed fnmatch corpus `tests/data/gui/fnmatch_cases.json` lists it).
  Separate arms keyed by name: `PeakFlag` members, the indexing diagnostic
  codes the peaks route emits, `StageSpec` fields, `READER_OPTIONS` and the
  wizard's instrument preset fields, the plan presets (`PLAN_INFO` is already
  the authority: the arm re-exports it, never restates).
- `ParameterRow.help: HelpEntry | None`, filled in `GuiSession.params`
  (`session.py:541-565`) by family match; `GET /api/help` serves the whole
  registry once for the non-parameter arms.
- `docs/manual/using/glossary.md` is **generated** in `conf.py` from the
  registry (a MyST include written at build time, like the fenced constants),
  reference register, one entry per family in path order. Every `anchor` is
  a heading id in the built manual.
- Prose under `/yue-docs-style`, reference register: name, what it is, unit,
  default, typical range, what moves it. No rhetorical framing.

Rules from the root CLAUDE.md that bind here: a derived flag rots silently
(`_SURFACE_FLAGS`), so **every arm is meta-tested against its live registry**;
adding a public field (`ParameterRow.help`) fails the manual's coverage
partition until documented (`tests/api_surface.py`); `SCHEMA_VERSION` moves
by one for the added field, comment beside the constant.

## Non-goals

- No rendering: the popover is WP-1203; this WP changes nothing under
  `gui/src`.
- No change to `PlanInfo`, `PatternFormat` or `READER_OPTIONS` prose: those
  are `capabilities()` contracts. The corpus carries the person-facing text
  beside them.
- No theory: an entry links to the Part 2 chapter that has the equation.

## Tasks

- [x] `src/rietx/help.py`: `HelpEntry`, the family registry, `help_for(path)`,
      the named arms; exported from `rietx` and documented in Part 1.
- [x] `ParameterRow.help_key` (a family key, not the entry — see the
      handover) filled in `Refinement.parameters`; `SCHEMA_VERSION` bump with
      its reason; `GET /api/help` route (in `server.ROUTES`, disjointness
      test still green).
- [ ] `tests/test_help.py`: every family the fnmatch corpus vocabulary
      produces matches exactly one entry; every `PeakFlag`, every
      `PLAN_INFO` key, every `StageSpec` field, every `READER_OPTIONS` name
      and every wizard preset field has an entry; every entry's `anchor`
      resolves in the built manual (the dead-link guard WP-1017 planned).
- [x] `docs/manual/using/glossary.md` generated in `conf.py`; toctree wired;
      `-W` build green; `test_manual_api` partition green for the new names.
- [x] Write the entries (the long part): parameters, flags, stage fields,
      reader options, preset fields. Each under `/yue-docs-style`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_manual.py tests/test_manual_api.py tests/test_gui_server.py -q
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m ruff check src tests examples
```

## References

- McCusker et al. (1999) J. Appl. Cryst. 32, 36: the typical ranges for the
  profile and displacement parameters quoted in the entries.
- `docs/AGENT_PROTOCOL.md`: the diagnostic-code rows the flag arm must agree
  with (`test_every_vocabulary_member_appears_in_the_protocol`).

## Handover log

- **2026-08-25** — created from the v1.2 triage.
