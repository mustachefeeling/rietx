# WP-1202 — The help corpus, served and meta-tested

Milestone: v1.2 · Status: ✅ 2026-08-25 — 87 entries in one module, every arm crossed against its live vocabulary both ways
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
- [x] `tests/test_help.py`: every family the fnmatch corpus vocabulary
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

### 2026-08-25 — one place where a name is explained, and 87 explanations in it

Anyone can now ask what a refinable parameter, a peak flag, a stage setting, a
reader option or an instrument preset field actually is, and get the same answer
whichever way they ask. Before this there was no answer anywhere for a
parameter: nothing in the tree said what the profile width terms or the
displacement parameters mean, and the GUI's only help was hover text kept in two
hand-maintained TypeScript lists. There are now 87 descriptions in one module,
each with its unit, the value it starts from and a range to compare a refined
number against, and the manual has grown a glossary generated from them rather
than written a second time. The cost was almost entirely writing: the machinery
is small, and what it buys is that a description can no longer drift from the
thing it describes, because every arm is crossed against the live list of names
it claims to cover, in both directions.

**Done.**

- `src/rietx/help.py`: `HelpEntry`, 33 parameter families over 44 globs, and
  six named arms (13 `PeakFlag` members, 12 `PEAK_*` diagnostic codes, 9
  `StageSpec` fields, 2 reader options, 11 instrument preset fields, 7 plan
  presets projected from `PLAN_INFO`). `help_key_for`, `help_for`,
  `help_registry`, all three exported.
- `ParameterRow.help_key`, filled in `Refinement.parameters`; `SCHEMA_VERSION`
  0.7 → 0.8; `GET /api/help` beside `capabilities`, not behind the 409.
- `docs/manual/using/glossary.md`: a committed head with the API, plus an
  entry body written at build time by `conf.py` into `docs/manual/_generated/`.
- `tests/test_help.py`, 18 tests.
- Root CLAUDE.md § Conventions gains the authority rule; cap 869 → 882.

**Measured** (`[dev]` only, darwin/arm64, Python 3.12.12, on **main merged into
this branch** — main moved under the session, PR #130).

- Fast suite 2814 passed / 117 skipped, from a 2796 / 117 baseline: +18, exactly
  the tests added, and no skip moved. The WP's own acceptance selection is 158
  passed against a 140 baseline, the same +18.
- The wire measurement that changed the design. Inlining a `HelpEntry` on every
  parameter row costs 3.4× the `/api/params` payload (20.8 kB → 70.0 kB on the
  NAC example at 95 rows, 17.8 → 61.1 kB on FAP at 82), on a call the GUI makes
  after every mutating verb. The family key costs 20.8 → 24.2 kB, 1.16×, against
  40.7 kB for the whole registry fetched once.
- Coverage is exact, not approximate: every path both example models produce
  matches exactly one family (95/95 and 82/82 rows carry a key, none unmatched),
  and every family glob matches at least one live path.
- The manual builds `-W` clean with the glossary in it; every one of the
  entries' anchors resolves in the built HTML.

**Two departures from this WP's own design line**, both measured rather than
preferred.

- The row carries `help_key`, the family glob, not `help`, the entry. The
  numbers are above. A client needs no `fnmatch` for it: the `parameters` arm
  lists every glob that reaches each entry, so a key indexes it directly.
- It is filled in `Refinement.parameters`, not in `GuiSession.params` as the
  design said. Filled only by the GUI, a Python caller's row would read
  `help_key=None`, which says "no family claims this path" when the truth was
  "nobody looked" — the defaulted-answer failure WP-1076 went through the result
  rows for.

**Three corrections to the design's own findings**, all found by reading the
live vocabulary rather than the WP.

- `phases.*.extinction` is a bare scalar on `Phase`, not `phases.*.extinction.*`.
- `phases.*.preferred_orientation.r` is **absent from
  `tests/data/gui/fnmatch_cases.json`**, whose two models carry no PO block. That
  corpus therefore cannot be the coverage authority on its own, and
  `tests/test_help.py` builds its own models with every optional block present.
- A third table path renaming existed that neither the WP nor I had found:
  `phases.N.atoms.M.aniso.uIJ` loses its `aniso` segment. The rename map in the
  test asserts it is exhaustive, which is what surfaced it; without that
  assertion six ADP components would have sat silently outside the unit and
  default checks.

**Gotchas for the successor.**

- The generated glossary body lives in `docs/manual/_generated/`, gitignored,
  **not** under `using/`. `tests/test_manual_api.py` globs `using/*.md`, so a
  page that exists only after a sphinx build would make the test suite's file
  list depend on whether one had run.
- `UNIT_DISPLAY` is checked both ways. Adding a `Parameter(unit=…)` spelling
  with no display form fails `tests/test_help.py`, and so does leaving a display
  form no schema reaches. `EmissionLine.wavelength` gained `unit="A"` in WP-1134
  and had no spelling until this WP.
- The anchor guard shares `tests/test_manual.py`'s session-scoped sphinx build
  through `xdist_group("manual-build")`. A test that reads the built manual must
  carry that mark or a second worker rebuilds the tree.
- The full suite was **not** fired, and the reason is the rule's own: this
  change cannot move a measured number. No residual, Jacobian or solver code was
  touched; `refine.py` changed by one import and one keyword argument on a cold
  path after the fit, and no slow test pins `SCHEMA_VERSION`.

**Next: WP-1203, which renders this.** Its `### Inherited` already carries what
it needs and cannot read off the code: that the row holds a key rather than an
entry and why, the arm names and their key vocabularies, that `anchor` is a
built-manual heading id with no URL shape chosen yet, and that `gui/CLAUDE.md`
deliberately has no help rule yet because this WP changed nothing under
`gui/src`. The first decision there is what a popover links to, since that fixes
whether `anchor` stays an id or becomes a path.

- **2026-08-25** — created from the v1.2 triage.
