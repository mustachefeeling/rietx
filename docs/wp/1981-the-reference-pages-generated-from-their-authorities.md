# WP-1981 — The reference pages, generated from their authorities

Milestone: unscheduled · Status: ✅ 2026-10-16 — ten Reference pages, eight generated (PR #1009)
Track: The repo's own process
Depends on: 1978 (the new tree)

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
  `using/concepts.md` drifted once: it omitted the `extra_components` stage that
  `mccusker_structural` inserts sixth of eleven (fixed by hand 2026-10-16). Generate the
  ladder from the plan objects so it cannot drift again.
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
- **The tree (WP-1978).** The new tree is `docs/docs/` (PR #1004). Its `conf.py` takes
  the fenced constants, the citation style, the mermaid theme and the `{source}` role from
  `docs/sphinx_shared.py`, which the old `conf.py` imports too. `tests/test_manual.py` builds
  it as the `built_docs_tree` fixture (xdist group `manual-build`), reads its pages as
  `DOCS_PAGES`, and holds each to the page contract (`_contract_breaches`).
  `tests/test_manual_api.py`'s `PAGES` now holds every page of the new tree, its Theory tab
  included, so a name in a code span on any page must resolve and counts toward the partition.
  The Reference tab is a stub at `reference/index.md`.

## Non-goals

- Rewriting diagnostic text (WP-1985). The Switching tab's prose (WP-1984) links the
  foreign-name map and the roadmap, and does not restate them.

## Tasks

- [x] Parameter map: grouped tables from `PARAMETER_HELP`, with the grouping held in the docs
      build, and a test that every glob lands in exactly one group.
- [x] `vars.*` help family in `help.py`, with the GUI `PLACES` row, vitest and dist rebuild.
- [x] Plan ladder from `PLAN_INFO`/`PLAN_PRESETS`, one diagram per preset.
- [x] API reference: autodoc or a generator over `__all__`, grouped by likely use, and
      `tests/api_surface.py`'s partition reading it. *Done as a generator over the skill
      index's own selection, with `__all__` as its floor; the partition does not count it
      as documentation (see the handover).*
- [x] Diagnostic index: every code, its level and where it is raised.
- [x] Project tree from a built example, annotated from the writer constants.
- [x] Roadmap from the milestone records.
- [x] Foreign-name map with its test against the readers' constants.
- [x] The "For agents" page.
- [x] Skill: none; the skill keeps its own generated `api.md`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_manual_api.py tests/test_reference_pages.py tests/test_manual.py -n auto --dist loadgroup
npm --prefix gui test
```

## Handover log

- **2026-10-16** — closed. The new manual has a Reference tab a reader can use. It holds
  ten pages, and eight are built from the code each time the manual builds, so none can
  disagree with the installed package. A reader can look up any exported call with its
  signature, find every refinable parameter grouped by what it does, see each plan preset's
  stages drawn, look up any diagnostic code, see what a `.rex` project holds, and translate
  a parameter's name to or from GSAS-II, GSAS, TOPAS and FullProf. Nothing is deployed yet;
  that is WP-1979.

  *Done.* `docs/reference_pages.py`, beside `sphinx_shared.py`, generates the bodies;
  `docs/docs/conf.py` writes them into an ignored `docs/docs/_generated/`, and each
  committed page under `reference/` is a title, an answer sentence and one `{include}`.
  Pages: `api.md`, `api-techniques.md`, `api-types.md` (the skill index's `SECTIONS`, its
  `TECHNIQUES`, and the rest of `rietx.__all__`, each entry rendered by
  `make_api_index._entry` as a definition), `parameters.md` (`PARAMETER_GROUPS`, six groups
  and fourteen leaves, an ungrouped glob fails the build), `plans.md` (one mermaid chain per
  preset), `diagnostics.md` (246 codes walked from source in three shapes), `project.md`
  (walked from `build_example("fap")`, every entry named by its writer's constant),
  `roadmap.md` (`ROADMAP.md`'s unshipped named milestones), `foreign-names.md` (hand-written)
  and `agents.md` (hand-written). `vars.*` has a `PARAMETER_HELP` entry, a `PLACES` row
  (`"exp"`) and a rebuilt dist. `resolve_plan`'s mode mapping is now
  `staged._MODE_SUBSTITUTES`. The page contract now reads a generated body in place
  (`test_manual._as_rendered`). The two tests that read `ROADMAP.md` joined CI's docs job.
  The Inherited entry from WP-1978 was folded into Context on arrival; it was still true.

  *Decisions.* The API reference is a generator, not autodoc. Autodoc would render whole
  docstrings, which are written in the rulebook register. The WP's "the partition reading
  it" was read as "the reference covers `__all__` and counts as nobody's documentation":
  `test_manual_api.py` skips `_generated/`, because a generated page that documented every
  name would turn the coverage gate into a tautology. The API tiers come from the skill
  index's own selection rather than a new hand-written grouping.

  *Review.* `/code-review high --fix` found ten issues and fixed eight in one commit. The
  worst: the FullProf column was checked case-insensitively, so `x` and `biso` matched
  rietx's own lowercase keys and a wrong name could not fail. It now reads the `.pcr`
  column headers the reader quotes, exactly. Also fixed: a `*_CODES` table named files that
  only cap a code, an annotated table was skipped, the project tree assumed row order, a
  patch dev build named the wrong release, the skill index loaded six times per build, and
  every build rewrote every body. Declined: widening the include regex to bodies with option
  lines (no page uses one), and retargeting the `blob/main` source links (WP-1979's, now in
  its Inherited).

  *Measured.* Venv `[dev]`, macOS arm64, alone on the machine. Fast selection: 1 failed,
  10771 passed, 185 skipped, 2 xfailed in 4:47. The failure was this handover's own stale
  WP index, before `wp_index.py` ran. Collected fast cases went from 10939 on `origin/main`
  138d55dc (a snapshot) to 10957, the 18 cases of the 17 added tests. `added_test_times`:
  4.42 s over the 17, of which 3.63 s is the diagnostic walk's cross-check against the
  skill's walk and 0.69 s the foreign-name check. Vitest 586 passed; svelte-check clean. The
  full suite was not run: the source changes are one help entry and `resolve_plan` reading
  a dict, which move no measured number. Built pages: the parameter map is 44 737 characters
  of its 50 000 cap, the third API page 37 671.

  *Gotchas.* Mermaid 11.12.1 reads `*` in a node label as emphasis and decodes `#42;` before
  doing so; only `\*` keeps a glob's stars. MyST keeps the underscore in a heading slug
  (`#mccusker_default`) while the HTML id is `mccusker-default`; MyST maps one to the other.
  `profile_only` and `pawley_default` build equal plans, so a plan cannot be named by
  comparing it. A page can drop pydata's right sidebar with
  `html_theme.sidebar_secondary.remove: true` front matter, which the foreign-name table
  needed at 1400 px. Some API summary lines carry WP numbers from their docstrings; that is
  in WP-1982's Inherited. The parameter map is near the page cap, so the next family or two
  may force a split.

  *Forward references.* Written into the `### Inherited` of 1979 (source links pin `main`,
  roadmap reads its own version), 1980 (expand the includes, unescape `\*`), 1982 (generated
  bodies are outside the register guard), 1983 and 1984 (their soft dependency is met, with
  page paths), 1985 (the diagnostic index awaits its explanation column) and 1986 (which old
  pieces the new pages replace; the glossary's non-parameter arms have no new page yet).

  *After the handover, the maintainer's review.* Five commits. The deferred bucket of the
  manual's coverage partition may not grow (`DEFERRED_CEILING` = 39 in `tests/api_surface.py`,
  failing on growth only), and `docs/RELEASING.md` step 2 now reads the list, records the
  count and lowers the ceiling at every cut. The parameter map explains dotted names and
  `*` before its tables. The cell entries in `rietx.help` are "Lattice parameter a, b, c"
  and "α, β, γ". The atoms lead names what GSAS-II and FullProf do with a special position.
  μ_B renders as a subscript on the generated pages (`_notation`). The API section headings
  are labels in `make_api_index`, so the skill's `api*.md` and both copies were regenerated.
  The review produced six style rules: four are in the user-level `yue-docs-style` skill,
  and all six, with their checkable halves, are in WP-1982's Inherited. The help corpus
  rewrite is folded into WP-1985. `yue-prose` construction 7 had said "the heading carries
  the claim", which contradicted the heading rule. The maintainer settled it by the
  heading's use: a heading is read alone in a contents list and must make sense there, so
  construction 7, its examples and `yue-docs-style` now all say so. Tests after the review: the manual, reference,
  help, GUI-help and skill files all pass, 547 cases across the runs.

  Next: 1979 and 1983 can start at once. 1984 can link the foreign-name map and roadmap.
  The glossary's other arms (stage fields, peak flags, reader options, instrument fields,
  search fields) need a home in Reference before WP-1986 retires the old tree; that is
  unowned and is named in 1986's Inherited.
- **2026-10-16** — filed from WP-1975's slate. No open WP owns an API reference, a grouped
  parameter map or a `vars.*` help family; the maintainer asked for the last two in WP-1975 § A.
