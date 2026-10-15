# WP-1981 — The reference pages, generated from their authorities

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1978 (the new tree)
Priority: P3 2026-10-16 — down a rung from P2: nothing can start until 1978's tree exists

## Goal

The Reference tab holds six pages built at docs-build time from the code that owns each fact.
They are the parameter map, the plan ladder, the API reference, the diagnostic index, the
project tree and the roadmap. A seventh page, the foreign-name map, is written by hand and
checked against the readers. None of these pages can drift from the package, because none of
them is typed.

## Context

WP-1975 decided that **every registry projection is generated** (§ F8). Prose pages are
written; tables of names are built. The maintainer's original ask (WP-1975 § A) included
tables of *all* parameters grouped as a crystallographer expects. Cell and structure go
together, microstructure is a group, the instrument is a group, and the background is its own
group, with schema paths unchanged. They also asked for an API overview grouped by how likely
each call is to be used, and a WP for a `vars.*` help family.

Facts measured 2026-10-15 (WP-1975 § B2-B4):
- **Parameters.** `rietx.help.PARAMETER_HELP` holds 82 globs over 69 entries (`HelpEntry`:
  title, description, unit, default, typical, anchor, label). Nothing groups them today. The
  candidate groups are instrument, specimen, TOF, background (Chebyshev / fixed-plus /
  P-spline, plus `extra_components` humps and declared peaks), phase, atoms, rigid bodies and
  microstrain. `help_registry()` feeds the GUI too (`/api/help`, `gui/src/lib/help.ts`), so
  adding a group *field* costs a GUI rebuild; a grouping kept in the docs build costs none.
- **`vars.*` has no help family.** Adding one touches `gui/src/lib/history.ts` `PLACES`, its
  vitest and the dist (root CLAUDE.md § Conventions).
- **Background and humps.** Humps join the background curve; declared peaks join the ticks
  under `"(extra)"`. Extra components are deliberately not nested under `background`, because
  every preset's first stage frees `instrument.background.*` and fnmatch `*` crosses dots.
  GSAS-II also keeps humps in its Background (WP-1975 § G3). The parameter map says this in
  its background group.
- **Plans.** `PLAN_PRESETS` and `PLAN_INFO` (8 presets). The old tree's plan mermaid in
  `using/concepts.md` has drifted: it omits the `extra_components` stage that
  `mccusker_structural` inserts sixth of eleven. Generate the ladder from the plan objects.
- **API.** `rietx.__all__` holds 115 explicit names plus every schema class. There is no API
  reference at all today (no autodoc). `docs/skill/make_api_index.py` already groups the
  agent-facing index (`SECTIONS`), and its groups are a starting point for "by how likely".
- **Diagnostics.** 271 codes across 41 files. The skill's `references/diagnostics*.md` holds
  one agent-facing row per code. The index here is for a person, and WP-1985 adds the
  per-code explanation it should show.
- **Project tree.** Writer constants a generator can read: `project.PROJECT_JSON`,
  `HISTORY_FILE`, `LIVE_DIR`, `EXPORTS_DIR`; `gui.peaks.PEAKS_FILE`;
  `gui.session.EXPORT_DEFAULTS`; `runs.*_FILE` and `runs.RUN_ID_RE`; `_about.PROJECT_SUFFIX`.
  Build an example with `rietx.examples.build_example("fap", into)` and walk it, so the tree
  shown is one that exists.
- **Roadmap.** Built from the open milestones (`docs/ROADMAP.md`'s table and
  `docs/milestones/<name>.md`), so the switcher reads direction. It replaces a "what rietx
  does not do" page, which the maintainer declined.
- **Foreign names.** No rietx↔GSAS-II/TOPAS/FullProf map exists. The vocabularies are in the
  readers: `io/projects/gsas2.py` (`SAMPLE_PARAMETERS`, `INSTPRM_*`), `topas.py`
  (`_KEYWORDS_READ`, `_CELL_KEYS`, `_ADP_KEYS`), `fullprof.py`, and `io/projects/coverage.py`.
  The map is hand-written and a test checks each foreign name against those constants.
- **For agents.** A short page saying what the skill is, linking `/skill/rietx/`. The old
  tree rendered the whole skill as one 702 000-character page; the new one does not.

## Non-goals

- Rewriting diagnostic text (WP-1985). The Switching tab's prose (WP-1984) links the
  foreign-name map and the roadmap, and does not restate them.

## Tasks

- [ ] Parameter map: grouped tables from `PARAMETER_HELP`, with the grouping held in the docs
      build, and a test that every glob lands in exactly one group.
- [ ] `vars.*` help family in `help.py`, with the GUI `PLACES` row, vitest and dist rebuild.
- [ ] Plan ladder from `PLAN_INFO`/`PLAN_PRESETS`, one diagram per preset.
- [ ] API reference: autodoc or a generator over `__all__`, grouped by likely use, and
      `tests/api_surface.py`'s partition reading it.
- [ ] Diagnostic index: every code, its level and where it is raised.
- [ ] Project tree from a built example, annotated from the writer constants.
- [ ] Roadmap from the milestone records.
- [ ] Foreign-name map with its test against the readers' constants.
- [ ] The "For agents" page.
- [ ] Skill: none; the skill keeps its own generated `api.md`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_manual_api.py -n auto --dist loadgroup
npm --prefix gui test
```

## Handover log

- **2026-10-16** — filed from WP-1975's slate. No open WP owns an API reference, a grouped
  parameter map or a `vars.*` help family; the maintainer asked for the last two in WP-1975 § A.
