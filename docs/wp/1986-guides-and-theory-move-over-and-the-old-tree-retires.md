# WP-1986 — Guides and Theory move over, and the old tree retires

Milestone: unscheduled · Status: 🔄 2026-10-20 — claimed by @yue-here (8th session); Guides: 23 of 25 written, 18 and 24 waiting on other WPs; Start tab, compatibility and the settings page moved; the other chapters' reference moves before the tree retires
Track: The repo's own process
Depends on: 1978 (the new tree); 1985 (the report text the guides show); 1979 (redirect stubs)
Priority: P2 2026-10-16 — unblocked: WP-1979 built the redirect stubs (PR #1023)

## Goal

The Guides tab holds one "How to …" page per task, mined from the old Part 1. Part 2 lives under
the Theory tab with all its guards. Every old chapter has been retired behind a redirect stub,
and the old tree is gone.

## Context

WP-1975 decided the migration (§ F8): the new tree is built beside the old, and each old
chapter is retired once its content has been mined, so the guards stay green throughout. Old
chapters keep their URLs until they retire, then get an HTML redirect stub (WP-1979 provides
the mechanism; GitHub Pages has no server-side redirects).

**Superseded in part, 2026-10-17 (the maintainer's decision).** The old tree retires all at
once, when the last guide lands, never chapter by chapter. The old chapters link each other
densely (`using/refining`, `using/files` and `using/data` each have 20-24 inbound links), so
retiring one at a time would mean rewriting links in chapters that are themselves about to
go. Until then each mined chapter stays up beside its guide, and nothing in the old tree
changes as a guide is written.

**Order** (§ F8): Concepts, Reference and Switching start first because they show no fit
output. Guides and the tutorials wait for the report-text rewrite (WP-1985), so they show the
new output from the start.

**Part 2 becomes the Theory tab.** Its guards carry over unchanged (`tests/test_manual.py`):
- fenced constants are MyST substitutions injected from the live package;
- every displayed equation carries a `*Source:*` line whose symbol imports;
- every bib entry is cited;
- the built HTML holds no unrendered TeX.
`docs/manual/check_equations.py` measures furo's layout and needs porting to
pydata-sphinx-theme's.

**Guides.** One task per page, titled "How to …", with a single answer sentence under the H1
(WP-1978's contract). Code shown is code that ran: the authority for a walkthrough is
`examples/` (root CLAUDE.md § Conventions), and the manual `{literalinclude}`s it. Mine from the
old chapters; `refining.md`, `data.md`, `files.md`, `series.md`, `indexing.md` and `results.md`
are the largest. The spike's guide (`docs/wp/1975-spike/sphinx/guides/calibrate.md`) shows the
shape. The old `files.md` calibration snippet called `ref.fitted_instrument` after binding
`result = rx.refine(...)`, so it could not run (fixed 2026-10-16). A `RefinementResult`
carries no instrument, so write the new one from a `Refinement`.

**GUI chapters** (`gui-quickstart|guide|power.md`) have their own guard
(`tests/test_gui_manual.py`), which partitions routes and panels. Move it with them.

**Agent admonitions** stay only where a supervising person needs them (§ F8).

### What the new tree already provides

Folded 2026-10-17 from the `### Inherited` notes WPs 1978-1985 left; each was checked against
the tree that day.

- **The tree** is `docs/docs/` (WP-1978, PR #1004). Its `conf.py` takes the fenced constants,
  the citation style, the mermaid theme and the `{source}` role from `docs/sphinx_shared.py`,
  which the old `conf.py` imports too. `tests/test_manual.py` builds it as the
  `built_docs_tree` fixture (xdist group `manual-build`), reads its pages as `DOCS_PAGES`, and
  holds each to the page contract (`_contract_breaches`). The `{source}` coverage test holds on
  every page of the new tree. `test_every_bib_entry_is_cited` counts citations across both
  trees, so an entry stays cited while its chapter is half moved.
- **Markdown twins** (WP-1980). Every page in `docs/docs/` gets `page.html.md`, written by the
  HTML build (`docs/markdown_twin.py`) and held to the page contract too: one H1, an answer
  sentence, at most 50 000 characters, no MyST left
  (`test_every_page_has_a_twin_that_keeps_the_contract`). A chapter whose twin passes the cap
  must be split. The twin handles the old tree's node types
  (`test_the_twin_writes_every_node_type_the_old_tree_uses`); `{download}` (six uses in the old
  tree) has a handler no test has run. A node type with no handler fails `-W` as
  `unknown node type`: add it to `_normalise` or `TwinTranslator`. Each moved page gets a line
  in `llms.txt` under its tab's H2, carrying its answer sentence. The site root's `llms.txt`
  (`docs_versions.assemble`) already points into `/docs/`.
- **Vale** (WP-1982) gates `docs/docs/` in CI's lint job and fails on an error. Over the whole
  old manual it found 463 errors (417 spellings, such as identifiers outside backticks and
  American forms, 14 banned words, 8 "fnmatch") and 458 warnings. Each moved chapter carries
  its share of those fixes; a domain word goes in `docs/vale/terms.txt`. CI writes the
  generated bodies (`reference_pages.write_bodies()`) before Vale runs.
- **Redirect stubs** (WP-1979). `docs/docs_versions.py`: retiring a chapter adds one row to
  `RETIRED` (old path to new page, both without `.html`; the new one may carry `#heading`) in
  the commit that deletes the chapter. `OLD_PAGES` freezes the 46 pages the old tree published
  (15 Part 2, 25 Part 1, six tutorials), and `tests/test_docs_versions.py` fails while one is
  neither built nor in `RETIRED`. `pages.yml` writes each stub at deploy time, into `stable/`
  once a release holds the page and into `dev/` until then.
- **Reference pages** (WP-1981, 1985). `reference/parameters.md` covers the old glossary's
  parameter arm; its other arms (stage fields, peak flags, reader options) have no new page
  yet. `reference/plans.md` replaces the plan diagram in `using/concepts.md`.
  `reference/agents.md` replaces the old tree's rendering of the skill (`_write_skill`). The
  diagnostic page is `reference/diagnostics.md` plus six subsystem pages, each code a section
  from `rietx.help.DIAGNOSTIC_HELP`; the glossary's diagnostics arm is `diagnostics`.
- **Report text** (WP-1985) is rewritten: the rustc-style line form, `FitReport.summary` one
  sentence a line, every message reworded. A guide shows the new text.

### Notes by task

**Theory.**
- Done 2026-10-17: the Concepts and Switching links into Part 2 now read
  `../theory/<chapter>.md#<id>`. `_OLD_THEORY_LINK` in `tests/test_manual.py` now fails a link
  to a moved chapter's old address, and no longer checks any other link to the site.

**Guides.**
- How a guide is built (2026-10-17). A guide `docs/docs/guides/<page>.md` runs its fits in
  `examples/guides/<page>.py`, same stem. The page `{literalinclude}`s the slice between
  `# guide: start` and `# guide: end` (marker above the imports, `:language: python`), and
  quotes printed output in a `text` fence under `<!-- output of examples/guides/<page>.py -->`.
  The script asserts every number the page quotes, below the end marker.
  `tests/test_examples.py::test_every_guide_script_prints_what_its_page_quotes` globs the
  scripts, so a new one joins with no test of its own, and fails a quoted block the script did
  not print. A block that only builds objects runs inline against `rietx.examples`'
  fluorapatite (`test_python_blocks_execute_or_say_why`). Each fluorapatite fit takes under a
  second. A number that differs between the compiled and numpy paths (`RIETX_COMPILED=0`) is
  quoted as a bound: the hold guide's unheld cell moved 318 ppm on one and 332 on the other.
- The guide map is WP-1975's 25 tasks (§ "The 25 most-needed how-tos"; its line numbers
  are from 2026-10-15). Done 2026-10-17, from `using/concepts.md`: 1 `hold.md`, 2 `tie.md`
  (named variables folded in), 3 `restrain.md` (the c_w schedule folded in), 4 `plan.md`
  (the presets' order folded in, without the heavy-atoms departure and the Stephens rule).
  From `using/refining.md` and `using/cli.md`: 5 `stage.md` (with `stage_reports=True`), 23
  `watch.md` (watching, stopping from the page or a `CancelToken`, `events=`, telemetry off).
  From `using/data.md` and `using/results.md` (3rd session): 6 `range.md`, 7 `hump.md`, 8
  `blank.md`, 25 `check.md`. From `using/report.md` and `using/series.md` (4th session): 13 `next.md`, 14
  `series.md`, 15 `path.md`, 16 `equation.md`; from `using/history.md` and `using/model.md` (5th session): 21 `branch.md`, 12 `interval.md`, 11 `cell.md`; from `using/exports.md`: 19 `export.md`; from the Switching pages and `using/files.md`: 22 `foreign.md`; from `using/qpa.md`: 20 `qpa.md`. The series guides share a synthetic LaB6 ramp,
  `examples/guides/_lab6_ramp.py`, which the guide test skips by its underscore. From
  `using/model.md` (6th session, 2026-10-19): 9 `holder.md`, on a synthetic steel line that
  `examples/guides/_holder_line.py` adds to the fluorapatite scan; from `using/data.md` and
  `using/files.md`: 10 `calibrate.md`, on a synthetic LaB₆ and CeO₂ pair on two setups
  (`_calibration_pair.py`); from `using/series.md`: 17 `joint.md`, on a synthetic corundum
  X-ray and neutron pair whose neutron wavelength is 300 ppm off (`_corundum_pair.py`).
  Left: 18, 24.
  Item 18 waits on WP-1910 and WP-1510, whose findings on the shipped
  fluorapatite pattern it would otherwise document; item 24 on the magnetic WPs in flight
  (1326, 1327, 1418). Item 10 has the spike's page to start from, but no
  LaB6 pattern ships in `rietx.examples`. The maintainer chose (2026-10-17) to fetch data a
  guide needs rather than ship it: `rietx.examples.fetch` downloads a `REMOTE_FILES` entry from
  `tests/data/` at a pinned commit, and `test_examples.py`'s `fetched_state` fixture fills the
  cache so the suite stays offline. A calibration guide can add a LaB6 or the 11-BM Si 640c
  file there (a new file in `tests/data/` needs `REMOTE_COMMIT` moved to a commit holding it).
- **Data choices, 2026-10-19, open for the maintainer to reverse.** The maintainer asked
  the session to use its best judgement and leave the decisions recorded here until they
  have time. Item 9 uses a synthetic steel line on the real fluorapatite scan, and the page
  says so; the alternative is a real holder scan the maintainer supplies. Item 10 uses a
  synthetic standard and sample, as tutorial 04 does; the measured real options are in the
  5th session's entry, and a lab LaB₆ scan with a sample from the same diffractometer would
  beat all three. Item 17 uses a synthetic corundum pair, built as
  `tests/test_joint_xray_neutron.py` builds its own, with a neutron wavelength 300 ppm off
  so the page can refine it. The real Nd₂Ru₂O₇ pair (`mg090.fxye` and `mg090.Cu311.gsas`,
  Gaultois et al. 2013) is the better demonstration, but its `tests/data/README.md` row
  states no licence, so serving it through `rietx.examples.fetch` waits on the data owner's
  agreement. Swapping it in later means a `REMOTE_FILES` entry, a new `joint.py` and the
  page's quoted output; `test_acceptance_wavelength.py::_joint` already runs the fit.
  Two candidates outside
  the list: fixing the origin of a polar space group (`Phase.floating_origin`, after WP-1912
  lands, which owns that behaviour), and the plan's "one departure" paragraph.
- A guide that says what a diagnostic code *does* (a hold, a quarantine, a withheld
  statement) quotes the package's own `Diagnostic.explanation` rather than restating the
  verdict, so the text follows the code. The generality milestone
  (`docs/milestones/generality.md`, WPs 2002-2007) will demote or remove verdicts and
  automatic actions that rest on rietx's own thresholds (folded 2026-10-19 from WP-2001).
- The agent-supervision checklists left the tutorial notebooks (WP-1545), and the front
  page's "Supervising an agent" card links the guides, so a guide is their home. The last
  copies are each notebook's `## Checking an agent's work` section at `7472e200`
  (`git show 7472e200:examples/tutorials/0N_*.py`, notebooks 01-05). Each maps SKILL §4's
  rules to what a person checks: status and diagnostics first, the difference curve region
  by region, correlations near 1, chemistry, a tie's premise, Rwp last (folded 2026-10-19).
- The tutorial notebooks link the new tree on the stable path (`https://rietx.org/docs/stable/…`),
  and `tests/test_tutorials.py::test_a_tutorial_links_only_pages_the_manual_has` fails on a
  link to a page `docs/docs/` does not build, so renaming or removing a guide or Concepts page
  runs that test (folded 2026-10-19 from WP-1545).
- `using/concepts.md` is mined except § The parameter groups and § Why the groups correlate,
  which the Concepts pages already cover. The old chapter stays up until retirement.
- `theory/intensities.md` § The magnetic structure factor lost its link to
  `using/refining.md` § When the magnetic peaks are broader (label `sec-magnetic-width`),
  because the new tree has no such page yet. Link the guide that replaces it.
- A question a newcomer asked of the Concepts tab, not checked against the code: does a fit's
  first stage estimate the phase scale, or start from the stored value (the parameter map's
  default is 1.0)? That goes in the guide on starting a fit. (The second question, whether
  excluded regions survive a checkout or a replay, is answered in `range.md`, 2026-10-17.)
- Part 1 material the Concepts pages now cover, so a retiring chapter can point there:
  `using/concepts.md` § The parameter groups and § Why the groups correlate
  (`concepts/parameters.md`, `concepts/correlations.md`); `using/data.md` § Explicit humps
  (`parameters.md` § Humps); the `.rex` part of `using/files.md` (`concepts/project.md`);
  `using/report.md`'s layer descriptions (`concepts/report.md`).
- Stale in the old chapters: `report.md` counts the Layer 1 gates as four where the code has
  four region checks plus a global gate, and its `FitReport` table omits `microstructure`;
  `files.md` says `Project.open` checks four bindings where the code has nine refusals, and
  calls `history.jsonl` append-only though `RefinementTree.save` rewrites it;
  `src/rietx/report/apply.py`'s docstring says "four of the sixteen" kinds where `ActionKind`
  has 18.
- The Switching tab's feature table (`switching/at-a-glance.md` § Features and what they were
  checked against) has a "Read more" column linking Concepts and Reference pages. Point each row
  at its guide once the guides exist. Those pages' python blocks carry `no-exec` lines naming
  `examples/switching.py`, so a rename of anything it calls fails `tests/test_examples.py`.

**Retirement.**
- **What the guides did not take, measured 2026-10-19 (7th session).** The guides took the
  old chapters' how-tos. Each chapter's reference and explanation, which WP-1975's
  per-chapter table splits off, has no home yet. Retiring the tree now would delete it, and
  2 044 of the 2 199 public names the coverage partition counts as documented are spelled
  only in Part 1 (the generated API pages do not count, by design). So the residue moves
  first, as a Reference, Concepts or Start page per chapter, with light edits as the GUI
  chapters had. Survey by chapter (old line ranges), covered meaning a new page states the
  facts:
  - Covered: concepts, constraints, gui-*, qpa, skill (minor: concepts' "one departure" and
    Stephens rule, qpa's `amorphous_hump_score` cue).
  - No home at all: install (moved 2026-10-19), first-refinement (example projects, the
    minimal call, `refine` against `Refinement`, Le Bail first and `lebail_scaffold`, NAC,
    `status`/`usable`), quickstart (the tutorial index), compatibility, agents
    (`model_dump(mode="json")`, wrapping a tool, `capabilities()` arm by arm, the six
    contracts), recipe (PowderLine, whole chapter), indexing (all 1 380 lines; guide 18
    takes the procedure, the reference part needs a page too).
  - Gaps: cli (`rietx index`, `events`, `html`, `compare`, `gui` options, the watcher's
    routes, 46-571); data (field tables for `Parameter`, `PatternData`, `Phase`/`Cell`/`Atom`,
    instrument constructors, `Source`, neutron and TOF set-up, λ/n harmonics, `Geometry`,
    `ProfileTCHZ`, background kinds, 20-1055); exports (calculated pattern, plot options,
    `render_structure` 130-501, magnetic reflection rows, magCIF); files (TOF reading,
    magCIF, magnetic phases from TOPAS and FullProf, a project with no structure,
    `ProjectFormat`, `Stance`, the per-format models, the history-log format); glossary
    (the `help` arms other than parameters and diagnostics: stage settings, peak flags and
    origins, reader options, instrument presets, indexing search settings; `help_for`);
    history (node fields and action kinds, `diff`/`api_call`/`order`, tree identity, the
    `history=` table, 13-455); model (`ParameterRow`, `TieSpec`, bounds and the cell window,
    `set_vary`'s return and `set_values`' refusals, `at_bound`); refining (entry points and
    where `backend`/`solver` go, modes and `lebail_passes`, λ/n check, the magnetic cluster
    241-802, `intermediate_ftol`, `PlanSpec` persistence, `Provenance`); report (Layer 0 and
    1 object detail, texture and directional strain, the evidence blocks,
    `check_rigid_bodies`, `rietx compare`); results (`Statistics`, bonding geometry,
    observation count, what `diagnose` measures, printing a result, `Progress`); series
    (a phase appearing part-way, `carry`, quarantine, a moment through a transition, the
    joint-fit profile scan, per-histogram report, the parametric refusals).
  - About 1 000 lines are magnetic (refining, files, series, data, exports), waiting on
    guide 24's WPs for the procedure; their reference part can move before.
- The old tree's 14 Part 2 pages are one-line `{include}`s of `docs/docs/theory/`, and its
  root page includes the Theory index's conventions, scope and units between two markers.
  Delete them with the tree and add their `RETIRED` rows then.
- The old tree's three GUI chapters (`using/gui-*.md`) now show their screenshots from
  `docs/docs/screenshots/` (`../../docs/screenshots/…`), and nothing guards them; they go
  with the tree and take `RETIRED` rows to `start/gui-quickstart` and `reference/gui-guide`,
  `reference/gui-power` (2026-10-19).
- The new tree has no page for `using/compatibility.md`, and root CLAUDE.md names its
  § Provisional by declaration as the one home of the promise that indexing and the GUI's
  routes may change in any release ("`{ref}`d not restated"). `reference/gui-power.md` now
  states the routes are provisional without that `{ref}`. Give the promise a page before the
  old tree goes, and point both back at it (found by the 6th session's review, 2026-10-19).
  Done 2026-10-19 (7th session): `reference/compatibility.md`, its stale lines fixed (the
  agent envelope, the foreign readers' count and writers); `gui-power.md` `{ref}`s it,
  `test_manual_api.py`'s `COMPATIBILITY_PAGE` and root CLAUDE.md name it. The skill's link
  (`references/diagnostics-indexing.md:124`) moves with the other skill links, once
  `/docs/stable/` exists.
- Three pieces of WP-1979's task 4 belong here, because none of the 13 pages `help.py`'s
  anchors name exists in the new tree yet: a versioned docs base beside `_about.DOCS_URL`
  (`dev` for a `.dev0` build, `X.Y` otherwise; the mapping `docs_versions.docs_version` moves
  into the package, since `_about.py` imports nothing); `help.py`'s anchors and the GUI's
  `docs_url` (`gui/session.py`) on that base; and
  `tests/test_help.py::test_every_anchor_resolves_in_the_built_manual` pointed at the new
  tree's build.
- When the old tree goes, its `pages.yml` build step goes too, and the stubs remain.
- Also at retirement (the 7th session's review): `docs/docs/make_figures.py`'s `hump()`
  docstring cites `docs/manual/using/data.md` for the Si 640c table; repoint it at that
  table's new page. `docs/wp/1975-spike/tools/build_myst.sh:10` and `build_sphinx.sh:8`
  copy from the old `using/figures/` and are broken since the figures moved; they are a
  closed spike's record, so leave them.
- Nothing renders the tutorial notebooks under Start yet. `myst_nb` is loaded in the new
  `conf.py`, but the copy step (`_copy_tutorials`) is in the old one and moves at retirement.
  `DOCS_PAGES` globs `.md` only, so once a notebook lands under Start the page contract, the
  register guard and name resolution skip it until the glob widens. Whether a notebook keeps
  the page contract is decided at that move. Done 2026-10-19 (7th session, by a lane):
  `sphinx_shared.copy_tutorials` serves both trees, `start/tutorials.md` is the index,
  and the notebooks' twins keep the contract except the answer sentence, because every
  tutorial opens on its authorship note (`NOTEBOOK_WAIVED` in `tests/test_manual.py`, a
  tripwire that fails once a notebook keeps the rule). WP-1545 is closed, so the fix is
  this WP's: move the note below the opening paragraph in each `examples/tutorials/NN_*.py`
  (`01_quickstart.py:4`), rebuild with `build.py`, and delete the waiver. A twin
  writes a notebook's inline figure out as a file: six of the seven twins measured
  62 752 to 551 259 characters with the base64 in, 7 561 to 39 799 without.
  `DOCS_PAGES` stays markdown-only, for the reason written at the glob.
- A seventh notebook, `02b_steering_a_refinement`, sits between 02 and 03 (the source glob is
  now `[0-9][0-9]*_*.py`). The old tree's hidden toctree lists it, and the Start tab's
  rendering takes it when `_copy_tutorials` moves. Its URL is new, so `OLD_PAGES` needs no row
  for it (folded 2026-10-19 from WP-1545).

**GUI chapters.**
- Moved 2026-10-19 (6th session, by a lane): `start/gui-quickstart.md` (the tutorial),
  `reference/gui-guide.md` and `reference/gui-power.md` (reference, as WP-1975's
  classification table has them), stems kept so each old page maps to one new one. The
  screenshots and `make_screenshots.py` moved to `docs/docs/`, and `check_equations.py`
  imports from beside itself. `tests/test_gui_manual.py` globs the new tree and resolves each
  image path from its page. Notebook 03 links `reference/gui-guide.html#peaks` on the stable
  path. The quickstart's agent admonition went (§ F8); its "routes are provisional" warning
  survives in `gui-power.md`, without the `{ref}` to the old compatibility page.
- `start/gui-quickstart.md` § Where to go next links the Guides index where the old page
  linked the Python quickstart. Repoint it when the tutorials render under Start.

## Non-goals

- The tutorials themselves (WP-1545 owns them).

## Tasks

- [x] Theory: Part 2's chapters moved, guards pointed at the new tree, `check_equations.py`
      ported. (2026-10-17. The old tree keeps a one-line include at each old path, so Part
      1's 79 references into Part 2 still resolve; those 14 pages take their `RETIRED` rows
      when the old tree goes.)
- [ ] Guides: one page per task, mined chapter by chapter. The old chapter stays up until
      the whole old tree retires (task 4); see Context, 2026-10-17. Twenty-three of 25 written
      (2026-10-17, map under Notes by task).
- [x] GUI chapters moved with `test_gui_manual.py`. (2026-10-19; the old copies stay up,
      unguarded, until the tree retires. Notes under GUI chapters.)
- [ ] Each chapter's reference and explanation re-homed (survey under Notes by task,
      Retirement, 2026-10-19). Done 2026-10-19: Start (install, a first fit in Python, the
      tutorial notebooks), Reference compatibility and the `help` arms (`settings.md`).
      Done 2026-10-20: `reference/cli.md` (`using/cli` whole; retires to it);
      `reference/data.md` and `reference/instrument.md` (`using/data`; retires to `data`);
      `reference/history.md` (`using/history` and `files.md` § The history log);
      `reference/programs.md` (`using/agents`) and `reference/recipe.md` (`using/recipe`);
      `reference/result.md`, `derived.md` and `pattern-diagnostics.md` (`using/results`;
      retires to `result`); `reference/report.md`, `report-evidence.md` and `comparison.md`
      (`using/report`; retires to `report`); `reference/pattern-files.md`,
      `structure-files.md` and `instrument-files.md` (`files.md` lines 1-806).
      Left: `files.md` from § Refinement files another program wrote, series, refining, model, exports,
      qpa and indexing, as Concepts or Reference pages, chapter by chapter.
- [ ] The old tree's build, guards and `pages.yml` steps removed once no chapter is left; the
      landing page's link to `/manual.html` pointed at `/docs/`.
- [ ] Skill: links into the manual updated to the new URLs.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_gui_manual.py tests/test_landing.py -n auto --dist loadgroup
```

## Handover log

### 2026-10-19 (7th session) — the Start tab, the compatibility promise and the settings page, and what retirement still needs

The new manual's Start tab now holds what a newcomer needs: an install page, a
first fit in Python, and the seven tutorial notebooks, beside the GUI tutorial.
Reference gained the compatibility promise and a page for the stage settings,
flags and options the old glossary listed. Measuring what retirement needs
showed the plan was short. The guides took only the old chapters' how-tos, so
most chapters' reference and explanation have no new home yet. And 2 044 of the
2 199 public names the documentation gate counts are named only in the old
Part 1. So the old tree cannot retire when the last guide lands, as decided on
2026-10-17. Each chapter's remaining reference moves first, which is several
more sessions of the same kind of work as this one.

*Done.* A survey by a subagent, checked here on ten names, mapped every old
chapter to its new home or its gaps (Notes by task, Retirement, first bullet); a
task joined the checklist for it. Pages: `start/install.md`,
`start/first-fit.md` (the old first-refinement chapter whole, links mapped,
every quoted number re-run), `start/tutorials.md` (the notebook index),
`reference/compatibility.md` (stale lines fixed: the agent envelope, the foreign
registry's four formats and writers; `gui-power.md` `{ref}`s it again;
`COMPATIBILITY_PAGE` and root CLAUDE.md name it), `reference/settings.md`
(generated by `reference_pages.vocabularies()` from the six `rietx.help` arms
with no page of their own; an arm on no page raises). `sphinx_shared.copy_tutorials`
serves both trees. The twin writes a notebook's inline figure out as a file. The
eight figure pairs and `make_figures.py` moved to `docs/docs/`, the old chapters
reach them at `../../docs/figures/`, and `test_nothing_gitignores_a_shown_image`
asks git about every image either tree shows. Four help strings reworded for Vale.
`/code-review high --fix` read `main...HEAD`, 99 files including the 6th
session's merged guides, because local `main` was behind: 10 found, 4 fixed (the
holder guide's `model_copy(update=)` skipped validation, so it now assigns; two
quoted claims asserted; peak origins named in the settings lead; a temp directory
removed), and one more by hand (the install page's Rosetta check). Declined:
`test_manual.py` keeps its own tutorial list beside `sphinx_shared`'s, as an
independent check on it; `make_figures.py`'s `hump()` docstring and notebook
03's `/docs/stable/` link wait for retirement and the 1.10 cut (Retirement notes).
No `### Inherited` note went out: WP-1545, which owns the tutorials' authorship
note, is closed, so that fix is this WP's (Retirement notes). The skill's three
links stay until `/docs/stable/` exists, and `help.py`'s anchors until their
targets do.

*Measured* (`[dev]`, darwin/arm64). The partition: of 2 238 surface names, 2 199
documented across both trees, 155 by the new tree alone, so 2 044 are documented
only in Part 1 and 696 of the 701 provisional ones. Method: set
`tests.test_manual_api.PAGES` to the new tree's pages and diff `documented_names()`.
Notebook twins: six of seven over the 50 000 cap at 62 752 to 551 259 characters
with the base64 figures in, 7 561 to 39 799 written out; `llms-full.txt`
2 501 369 → 1 134 361 bytes; the 12 PNGs add about 520 kB a version. First fit:
Rwp 0.1337 and 0.0933, a 10.251216(40) Å and the 13-node history, as the old
chapter printed. Fast selection on the final tree, alone: 10 835 passed, 191
skipped, 2 xfailed, one run of 4:58. Against CI's py3.14 junit for the 6th
session's tree (run 39287327732): 11 028 items against 11 022, +6, the six
cases added (`test_reference_pages` 3, `test_manual` 2 from parametrising the
tutorial tests over both trees, `test_manual_api` 1). The 6th session's local
11 136 came from a venv collecting more modules than this fresh one.
`tests.added_test_times`: 0.10 s over the five added functions. The full
selection did not run: the one `src/` change is help text.

Lanes (`session_usage.py lanes`): two, each estimated at 30.

| lane | est | requests | main at dispatch | re-read | left in main | lane $ | main $ | in-session $ | saved $ |
|---|---|---|---|---|---|---|---|---|---|
| tutorials-under-start | 30 | 73 | 232K | 9K of 101K | 45K | 4.31 | 1.41 | 7.65 | +1.75 |
| first-fit | 30 | 100 | 288K | 7K of 7K | 13K | 4.38 | 0.39 | 8.97 | +4.20 |

Saved +$5.95, 27 % of the session; estimates ran 2.88× short. The baseline's
selective policy over all 145 sessions: −7 %.

*Gotchas.* `grep` here is `ugrep`, and zsh globs an unquoted `--include=*.md`.
A new worktree needs `vale sync` once, for the Microsoft style. A bare
`/code-review` on a clean tree diffs against local `main`, so pass
`origin/main..HEAD`.

Next: the remaining Reference pages, one old chapter at a time, largest gaps
first. In order: the CLI (`rietx index`, `events`, `html`, `compare`, the
`gui` options, the watcher's routes); the schema fields from `data.md`, with
the neutron and TOF set-up; history's node model; `capabilities()` and the six
contracts from `agents.md`; recipe; the results, report and series object
detail; the per-format detail from `files.md`. After each, re-run the partition
measurement above, since the count of names only Part 1 documents is the
progress number. Then guides 18 and 24 when WPs 1910, 1510 and the magnetic
WPs land. Then retirement. One choice is the maintainer's and blocks nothing
yet: whether to retire before guides 18 and 24, by moving the indexing and
magnetic reference as pages of their own.

### 2026-10-19 — three guides on synthetic data, the GUI chapters moved, and an axial-divergence defect filed

The Guides tab now explains how to fit a peak from the sample holder, how to
calibrate an instrument on a standard and reuse it, and how to fit an X-ray and
a neutron pattern together. All three run on synthetic data their pages call
synthetic. The maintainer asked the session to choose, and the choices are
recorded under Notes by task for reversal. Writing them measured three things a
user would not see. A profile reused on another setup moves a crystallite size
by about 9 esd while Rwp stays put. A joint fit with a neutron wavelength 300
ppm off moves the shared cell by 3 esd and reports nothing. And the two
axial-divergence ratios are interchangeable, so `lab_calibrate` returned them
swapped, about 14 esd each from the truth, with no finding: filed as WP-2012.
The three GUI chapters moved to the new tree with their screenshots and guard.
Twenty-three of the 25 guides are written, and the last two wait on other WPs.

*Done.* Pages `docs/docs/guides/{holder,calibrate,joint}.md` with scripts and
one helper each (`examples/guides/_holder_line.py`, `_calibration_pair.py`,
`_corundum_pair.py`); the index gained Instrument and Several radiations
sections. `LAYER0_MATCH_TOL_DEG` joined `docs/sphinx_shared.py`'s substitutions
(the 0.08° that both `EXTRA_PEAK_ON_REFLECTION` and Layer 0's peak matching
use), and `test_manual_api.py`'s fully declared model gained a `PeakComponent`
so `instrument.extra_components.0.center` resolves. The GUI chapters went by a
lane to `start/gui-quickstart.md`, `reference/gui-guide.md` and
`reference/gui-power.md`; the screenshots and `make_screenshots.py` to
`docs/docs/`; the root and `gui/` CLAUDE.md name the script's new path; notes
under GUI chapters. Inherited pruned on arrival: WP-2001's generality note and
WP-1545's supervision checklists went under Guides, 02b under Retirement,
notebook 03's link under GUI chapters (now repointed), and `series.py` prints
its `Trajectory` whole, as WP-1545 asked. Two skill rows in
`references/numbers.md` (the profile from another setup; compare the cells
before a joint fit). Forwarded: the GUI move into WP-1317 and WP-1313. Filed:
WP-2012 (no open WP owned the axial ratios; 1460 is about ridges, not two
minima). `/code-review high --fix` over the session's range found 9 and fixed
5: the holder helper now stores a list (an array in `PatternData.intensity`
made `model_dump_json` raise), the calibration page names W's own stage and the
two `FLOOR_HIT` findings, the status header, a test comment, a repeated
`standard("first")`. Declined: `holder.md`'s inline declaration block, because
a block that only builds objects runs inline by this WP's guide pattern (the
hump guide's does too); `_corundum_pair.py` predicting twice to set the scale,
because scaling the first prediction could move the pinned numbers. Recorded
under Retirement: the routes' provisional promise has no new-tree page.

*Measured* (`[dev]`, darwin/arm64; every guide's printed output identical on
`RIETX_COMPILED=0`). Holder, fluorapatite under `mccusker_structural` 15-130°
with a synthetic ferritic-steel 110 line at 44.65° (area 60, FWHM 0.12°):
ignored, O7's x moves 1.91 esd from the clean fit; excluded 44.3-45.1°, 0.25,
and every esd grows by at most 3.9 %; declared, 0.22, and the line comes back
44.6507(77)°, 67.5(61), 0.122(25). Declared on the clean pattern at 44.6°, the
peak ends on three bounds with area 7.7(96) and `EXTRA_PEAK_NO_INTENSITY`
silent, because that code fires only at exactly zero area (at 60° it does).
Calibration, synthetic LaB₆/CeO₂ (300 Å, 1.0e-3) on two setups, the second
with twice W and X, H/L held at 3/200: matched size 300.8(22) Å, strain
0.001021(43); crossed 325.3(27) and 281.5(21) Å (8.9 and 9.5 esd), Rwp within
0.001; only the narrower profile shows a Gaussian size, 1530(230) Å. Both axial
ratios free: S/L 0.01451(76), H/L 0.02531(66) against 0.025 and 0.015, and the
two predicted patterns are bit-identical when swapped. On data with no axial
divergence and both free, the compiled and numpy paths agree on values and
differ up to 2× on the other widths' esds (in WP-2012). Joint, synthetic
corundum, neutron λ 300 ppm long: alone, a 4.7588780(41) and 4.757485(31) Å
(−293 ppm); jointly with `hist.1` λ free, +298.4 ppm at 5.1 ppm a esd, a within
an esd of the truth, x(O) esd 0.67 of the X-ray pattern's and z(Al) 0.96;
held, a 3.1 esd off and both coordinates' esds 1.2× and 1.7× the X-ray's, no
finding. Each fit runs in under a second. Fast selection on the final tree
(main at `2df48c95`, unmoved since the session began, no other suite running):
10 951 passed, 185 skipped, 2 xfailed, one run of 4:43. Collected 11 136
against 11 133 on a snapshot of `origin/main`, +3, the three guide cases. From
the junit file under full load: `holder` 15.7 s, `calibrate` 5.4 s, `joint`
5.0 s; `test_examples.py` totals 272.9 s across workers.
`tests.added_test_times` sees no added function, since the three parametrise
one. They stay in the fast tier for the reason `test_examples.py`'s docstring
gives. The full selection did not run: no `src/` change, so no measured number
can move.

Lanes (`session_usage.py lanes`): one lane, gui-chapters, estimated 40 and
taking 86 requests (2.15×), dispatched at 357K, re-read 7K of 99K, 16 main
requests and 28K left in main, 5 main edits after (the rulebook paths and the
WP notes), no redo; lane $4.62, main $1.45, in-session $9.80, saved +$3.71
(+16 % of the session). The baseline's selective policy over all sessions:
215 against the in-session cost, −4 %.

*Gotchas.* The worktree guard refuses `cat >> file <<EOF` and a multi-line
`sed` on a repo file, and a refused `sed` inside a `&&` chain lets the
following `git commit` run without it: an item was committed without its WP
tick once, fixed by a follow-up commit. A MyST link to a heading containing ⊕
slugs to a double hyphen (`#the-instrument--sample-width-split`), and an
included heading in backticks keeps its underscore (`plans.md#lab_calibrate`);
the tutorials' stable HTML slugs differ. `WAVELENGTH_CALIBRATION` lands on
`result.histograms[1].diagnostics`, never at the top level. `format_su` gives
two digits of esd (`0.01451(76)`).

Next: item 18 once WP-1910 and WP-1510 land, and item 24 once the magnetic WPs
(1326, 1327, 1418) settle. Then retirement (task 4), which now also owes the
provisional-routes promise a page; then the skill links. Two decisions wait on
the maintainer: whether Mike Gaultois agrees to `rietx.examples.fetch` serving
the Nd₂Ru₂O₇ pair, which would replace item 17's synthetic data; and WP-2012's
fix.

### 2026-10-18 — six guides on history, results and other programs, and two indexing defects

The Guides tab now explains how to branch a refinement and roll back, how to
quote lattice parameters with their esds, how to quote a parameter that ended on
its bound, how to export a CIF and a reflection table, how to find weight
fractions in a mixture, and how to open a GSAS, TOPAS or FullProf refinement and
write one back. Two of them show a pitfall on real shipped data. Changing only
the declared Cu Kα wavelength by 60 ppm moves fluorapatite's a by 7.6 esd. A
1.4 wt % CaF₂ impurity in the NAC pattern reads 3.1 ± 2.3 wt % because the
structural preset frees its extinction. Trying to write the indexing guide found
that the formula's volume window excludes the true cell of most inorganic solids,
and that the extinction screen demotes fluorapatite's true class. Twenty of the
25 guides are written.

*Done.* Pages `docs/docs/guides/{branch,cell,interval,export,qpa,foreign}.md`
with their `examples/guides/` scripts; the index now has Results and Other
programs sections. `qpa.md` runs on the shipped NAC scan with CaF₂ added as
`examples/nac_11bm.py` does. `foreign.md` opens the shipped `FAP.EXP` and
writes `.inp`, `.pcr` (with `write_zero_shift=True`, since the writer refuses
a non-zero zero shift otherwise), a GSAS-II phase CIF and an `.instprm`. Filed:
WP-1510 `### Inherited` (`SearchSpec.from_formula`'s window excludes 7 of 9
known cells, every inorganic one but NaCl) and WP-1910 `### Inherited` (the
fluorapatite screen, four ways). `/code-review high --fix` found 8 and fixed 6:
`foreign.md` now lists the FullProf writer's other refusals (extinction,
preferred orientation, texture, absorption, roughness away from off);
`export.md` names the tenth CIF loop and the script checks each loop's tag
group; the index's Results section; `interval.py`, `branch.py` and `qpa.py`
assert the figures their pages quote (3.2 µm², the 1.7 % χ² gap); the Status
line's remaining items restored. Declined: `branch.py` reads the private
`alt._head_id`, because no public accessor exists; the shown
`tempfile.mkdtemp()` leaves a directory per test run, kept because the page
shows readers that call.

*Measured* (`[dev]`, darwin/arm64; every guide's printed output identical on
`RIETX_COMPILED=0`). Fluorapatite, `mccusker_structural` over 15-130°: a
9.370962(82) Å, V 523.629(12) Å³ (diagonal esd 0.011), Bérar-Lelann factor
2.15; at the GSAS tutorial's 1.5405/1.5443 Å a moves 66 ppm, and GSAS's own
cell is 148 ppm above that. Extinction 0 ± 1.945 µm² on its floor, profile
interval 0 to 0.742 (the esd's 1.645 reach is 3.2); Ca1 Biso 0.479 ± 0.060,
interval 0.368 to 0.593, 1.85 and 1.91 esd. Branching: node Rwp 0.1031
against 0.0988; replays 0.1022 and 0.0992, the first carrying
`FROZEN_COMPILE_STALE` at a 1.7 % χ² gap. NAC + CaF₂ over 2-24°:
structural preset CaF₂ 3.09 ± 2.32 wt % (scale ~ extinction ρ 0.996, both
Biso on their floor, Rwp 0.082); CaF₂ extinction and Biso held, 1.37 ± 0.07
(Rwp 0.089); `mccusker_default` 1.38 ± 0.07; a `lor_strain` width profile
admits no other fraction. µR at 0.414 Å is 0.002, so Brindley moves nothing.
Calibration candidates for item 10, measured: the 11-BM SRM 660a LaB₆ scan
calibrates under `lab_calibrate` in 3.5 s at Rwp 0.082, but reused on NAC its X
is 26 % above NAC's own and every sample-broadening term ends at 0 (Rwp 0.165
against 0.136 with NAC's own widths); NIST's lab SRM 660c calibrates in 0.5 s
at Rwp 0.087 with `RESOLUTION_NOT_POSITIVE` (U −5.2e-4), and no sample from
that instrument exists. Indexing fluorapatite (`pick_peaks` 15-60°, 45
peaks): narrowed to hexagonal and trigonal, V ≤ 800, 11 s; unnarrowed 120 s;
the true cell first both ways, `best_or_none()` `None`. Fast selection on
the final tree, main merged (no move), no other suite running: 10 921
passed, 185 skipped, 2 xfailed, one run of 6:28. passed+skipped +6 against
the 4th session's 11 100, the six new guide cases. `tests.added_test_times`
sees no added function (they parametrise one); from the junit file the six
took 8-46 s each under full load, `interval` 46 s and `qpa` 40 s, each about
9-10 s alone. They stay in the fast tier for the reason `test_examples.py`'s
docstring gives. The full selection did not run: docs and examples cannot
move a measured number.

*Gotchas.* An `Atom` takes `Parameter` objects, never bare floats. A temp
directory created above the `# guide: start` marker trips ruff's E402, so the
shown code creates it. The FullProf writer refuses a fit whose extinction is
not 0. `profile_fraction` refuses a phase with no free width term unless
given `axes=`.

Next: three data choices, which only the maintainer can make. Item 9 (a
holder line): no shipped pattern has one, so a synthetic peak added to a real
pattern, or a fetched file. Item 10 (calibration): the measured options
above, or a synthetic pair as tutorial 04 uses. Item 17 (a joint X-ray and
neutron fit): the Nd₂Ru₂O₇ pair in `tests/data/` is published (Gaultois et
al. 2013) but has no licence row, so fetching it needs the data owner's word;
the alternative is a synthetic pair. Then 18 once WP-1910 and WP-1510 land,
and 24 once the magnetic WPs settle. The GUI chapters, retirement and skill
links follow the last guide.

### 2026-10-17 (4th session) — four guides on choosing a parameter and on series, and three defects they found

The Guides tab now explains how to decide which parameter to free next, how to fit a
temperature series, how to check that a series trend is not made by the chain, and how
to refine a cell edge as an equation of temperature. The three series guides run on seven
synthetic LaB6 patterns made from a known cell, so each page can say how close the fit
came. Writing them found three defects in the package. The default plan's last stage
stops about 10 % of χ² above the minimum that one more run of the same stage reaches,
and nothing says so. `suggest` can recommend a parameter that sits on its bound and
cannot move. And a cubic cell's step in a series is flagged three times. They are filed
in WPs 1421, 1998 and 1524. Eleven of the 25 planned guides remain.

*Done.* Pages `docs/docs/guides/{next,series,path,equation}.md` with their
`examples/guides/` scripts; a Series section in the guides index. The series scripts share
`examples/guides/_lab6_ramp.py` (tutorial 05's settings), and
`tests/test_examples.py` skips a guide file whose name starts with `_`. `next.md` teaches
comparing two branches of one node, because the fit a stage leaves is not at its own
minimum here (the window finding below). Filed: WP-1421 `### Inherited`, re-rated P3 →
P2 (the frozen windows move the minimum); WP-1524 `### Inherited` (a tied cubic cell's
step flagged three times, which `moved_paths` already de-duplicates); new WP-1998, P2
(`suggest` scores a candidate on its floor as if it could move both ways, and
`best_or_none` ignores ΔBIC). No open WP owned `suggest`: 1050 and 1434 are closed.
`/code-review high --fix` found 8 and fixed 5: the ramp reads its CIF once instead of
leaving a temp directory per call; "peaks 50 % too wide" became W 50 % too large, about
20 % in width; `equation.py` asserts the correlation and the slope gap its page quotes;
the noise floor renders from `{{ SUGGEST_MIN_GAIN }}`; the Status count. Fixed by hand:
`next.md`'s narrowing section showed ΔBIC refusing extinction on the fit before the
re-solve, while on the re-solved fit the same query favours it (+1.4) though it cannot
leave its floor. The page now says so and the script asserts it. The series page states
`MIN_POINTS_FOR_PERSISTENCE` (5), asserted. Declined: de-duplicating the ramp against
tutorial 05, because a notebook must be self-contained (WP-1545 owns it, and its
"50 % too wide" has the same slip).

*Measured* (`[dev]`, darwin/arm64; every guide line identical on `RIETX_COMPILED=0`).
Fluorapatite, hand-run `scale_bkg` → `cell` → `profile` over 15-130°: Rwp 0.1022, and
0.0940 after one empty stage on a branch; the same `profile` stage with
`window_slack_deg` 0.5 / 1.0 / 2.0 ends at 0.0967 / 0.0947 / 0.0945.
`mccusker_default`: 0.0992 → 0.0940 (χ² −9.5 %); `mccusker_structural` and
`lab_sample_refine` 0.0 %. `FROZEN_COMPILE_STALE` stays silent (0.8 % at fixed
parameters). Freeing the Kα2 weight against the re-solved fit: 0.464(6) from 0.5, t = −6.0,
ΔBIC +31.0 at N_eff 1297; extinction ΔBIC +148 against the fit before the re-solve, −7
after. LaB6 ramp: chain 0.45-0.5 s, both ways 0.9 s, every cell within 2 esd of truth,
forward and backward under 0.01 esd apart; a 2 % jump verified cold at 1.00× and rescued
on the `warm_staged` rung (warm Rwp 0.96 → 0.039). Joint line fit 0.45 s: slope
2.07744(80) × 10⁻⁵ Å/K against 2.0783 × 10⁻⁵, form statistic 3.8 against a cut of 11.1;
a 9.4 × 10⁻⁵ Å bow is rejected at 591.0. Fast selection on the final tree (main had not
moved, no other suite running): 10 915 passed, 185 skipped, 2 xfailed, one run of 6:07;
passed+skipped +4 against the 3rd session's 11 096, the four new guide cases.
`tests.added_test_times` sees no added function (the cases parametrise an existing one);
from the junit file the four took 3.3-9.9 s each under full `-n auto` load. The full
selection did not run: docs, examples and a test glob cannot move a measured number.

*Gotchas.* The worktree guard refuses some compound shell lines (a heredoc chained to
other commands), so write a probe as a scratchpad script and run it alone. The dot-path check reads prose
code spans, so a model field that is not a parameter (`goniometer_radius_mm`) is named by
its class, `Geometry.goniometer_radius_mm`. Ruff sorts `_lab6_ramp` before `rietx`.

Next: item 17 (a joint X-ray and neutron fit, a refined wavelength) needs a data choice.
The real pair is the Nd₂Ru₂O₇ 11-BM + BT-1 files in `tests/data/` (published, Gaultois
et al. 2013), which `rietx.examples.fetch` could serve, but `tests/data/README.md` gives
them no licence row; the other route is a synthetic pair like the ramp. Then 21
(`using/history.md`), 10 (calibration; choose LaB6 or the fetched Si 640c), and 9, 11,
12, 18-20, 22, 24.

### 2026-10-17 (3rd session) — four guides on the pattern and its background, and data fetched on first use

The Guides tab now covers what to do with a pattern before and around the fit: check it,
set the fit range and leave regions out, hold a measured blank under it, and add a hump for
a container halo. The blank and hump guides needed a real empty-capillary scan, which the
installed package did not have, so rietx can now download the 11-BM silicon scan and its
empty Kapton capillary on first use, checked against a hash, instead of shipping 3 MB more
in every wheel. Writing the range guide found that a pattern accepted an inverted excluded
region and silently excluded nothing; that is now refused. Fifteen of the 25 planned guides
remain.

*Done.* Pages `docs/docs/guides/{check,range,blank,hump}.md`, each with its
`examples/guides/` script, under two new index sections. `rietx.examples.fetch`,
`RemoteFile`, `REMOTE_FILES`, `REMOTE_COMMIT` (the maintainer chose fetching over bundling
or reading `tests/data/`); three offline tests in `test_example_projects.py`, and the
`fetched_state` fixture in `test_examples.py`. `PatternData` and `compile_model` refuse an
inverted or empty interval with `check_interval`'s sentence (one test in `test_project.py`),
staged in the 1.10 notes under Code to check, and `fetch` under New. The manual's dot-path
check stopped at a numeric segment, so it had never checked an indexed path such as
`phases.0.cell.a`; it now keeps indices and reads each as 0. Both manuals passed as they
stood. The guides answer the newcomer's checkout and replay question: a node records the
range and not the exclusions. `/code-review high --fix` found 9 and fixed 6: an inverted
region appended to the list (no validator runs) is refused when the mask is built, and
`project.fitted_mask` refuses inverted limits as `compile_model` does; `fetch` writes a
partial file of its own per call and catches a body dropped mid-read; the guide scripts read
`result.parameter`; the pages name `magnetic_width` as the preset that frees only the
polynomial. Two were handover items (this Status line, the release record's count). Declined:
the bracket assertion in the dot-path check can never fire, because no token can hold a `[`,
and making it work would flag python such as `lines[0]` in the pages, so which spans count as
paths needs deciding first.

*Measured* (`[dev]`, darwin/arm64). The preset `mccusker_default` on the Si 640c pair: blank
scale 0.836(19) against three Chebyshev terms and 0.695(32) against six; the acceptance
protocol's three-term figure is 0.8374(113). Built with `vary_scale=False`, the scale still
refines (to 0.84), because every preset frees `instrument.background.*`; `hold` keeps it at
1.0. `mccusker_structural` with one hump reproduces the old chapter: Biso esd 0.100 → 0.019
Å² with the hump, 0.040 with three more polynomial terms; the hump at 4.19(11)° FWHM
5.57(26)° on three terms, 5.25(5)° FWHM 1.96(13)° on six. Every guide line prints the same on
`RIETX_COMPILED=0`. Each Si fit takes 0.4-0.6 s; one real download took 0.44 s and a cache
hit 1 ms. The empty capillary's smoothed envelope peaks at 5.01° 2θ, d 4.71 Å.
Fast selection on the final tree (main had not moved): 10 910 passed, 1 failed, 185 skipped,
2 xfailed, one run of 4:56 with no other suite running. The failure was the skill's size
budget, tripped by the line added to `surprises.md` § 8.29 (presets free the blank's scale,
so hold it); cut to fit, and `test_skill`, `test_skill_cli` and `test_docs_consistency` then
gave 206 passed. Added this session: four test functions and four guide cases;
`tests.added_test_times` gives the four functions 0.01 s in that run. The full selection did
not run: the refusals change only inputs that used to mask nothing, and `fetch` reaches no
fit.

*Gotchas.* The dot-path check reads code blocks' variable names too: a variable named
`instrument` makes `instrument.extra_components` a path to check, so the hump page names it
`capillary`. A `fetch` file seeded from `tests/data/` must match `REMOTE_FILES`' hash, which
`test_every_remote_file_is_the_test_data_file_it_names` holds. `fetch` is expected not to work
in the browser build (inferred, not tested) and says what path to fill by hand.
`hold.py` (2nd session) failed on Linux CI from the moment #1034 merged, main included: its
fit's last stage stopped on its iteration budget there, and the script asserted `converged`.
The page quotes no status, so the assertion now accepts either. Its later assertions had
never run on Linux. The other guides' status assertions passed there.

Next: `using/report.md` (13, choosing the next parameter), then `using/series.md` (14-17) and
`using/history.md` (21). Item 10 (calibration) can now fetch its standard; decide between a
lab LaB6 file and the 11-BM Si 640c.

### 2026-10-17 (2nd session) — the Guides tab begins, six guides and the pattern for the rest

The new manual's Guides tab now holds six "How to" pages: keep a parameter fixed through a
plan, tie parameters, restrain a bond or an angle, add a stage to a plan, run a plan one
stage at a time, and watch or stop a running fit. Every fit a guide shows is a short script
run against the fluorapatite tutorial data rietx ships, so a reader can run it as written,
and every number a page quotes is checked by the test suite against what the script
printed. The old chapters they came from are untouched, as decided. Nineteen of WP-1975's
25 planned guides remain, and the way to write each is now settled.

*Done.* Pages `docs/docs/guides/{hold,tie,restrain,plan,stage,watch}.md`, each with
`examples/guides/<same>.py`; the convention and the guide map are under Notes by task,
Guides. One test, `test_every_guide_script_prints_what_its_page_quotes`, runs every script
in `examples/guides/` and fails a quoted output block the script did not print. Blocks
that only build objects run inline against `rietx.examples`, so the new pages carry two
no-exec blocks (a mixed-site occupancy tie, a series hook) and no other. The Parameter map
said `*` matches one part of a name; it crosses dots, and the page now says so. A
`### Inherited` note went to WP-1912: the polar-origin guide waits for its default.
`/code-review high --fix` found 9 and fixed 6 (one by hand): the hold page quoted 318
ppm, which the numpy path prints as 332, so the line now rounds to 100 ppm; the watch
guide denied that a run holds the observed intensities, which `snapshot.json` does; the
stage guide named a mechanism its comparison does not show; a series must call
`add_variable` in its constrain hook; quoted blocks now match at a line start; `watch.py`
names a token that never fired. Declined: a marker over a non-`text` fence (none exists),
and declaring the compiled or numpy path in the tie, restrain and stage scripts, whose
printed values agree on both paths on darwin. If CI's Linux legs disagree, round those
lines as the hold line was.

*Measured* (`[dev]`, darwin/arm64). Each fluorapatite fit takes 0.7-1.0 s. The three
scripts that quote exact values print the same on `RIETX_COMPILED=0`. The restraint guide's
three P-O restraints at sigma 0.01 Å move each bond by 0.0011 Å at most against a fit
where they pull on nothing, so on 5 751 points the data place the bonds. The synthetic c_w
case in `tests/test_restraints.py` re-run: 4.837 Å and 148.6 sigma under a flat weight, as
the old chapter said (that test's docstring truncates them to 4.83 and 148). Fast
selection on the final tree: 10 903 passed, 185 skipped, 2 xfailed, one run of 5:50 with
no other suite running. This session added six items, the six guide cases; main moved
during the session, so no before-and-after pair is quoted. `tests.added_test_times`: the
six cases total 96.8 s in that run, six subprocesses under full `-n auto` load (17.9 s
wall for the six alone). They stay in the fast tier beside `switching.py`'s case, for
the reason `test_examples.py`'s docstring gives. The full selection did not run: docs,
examples and one test cannot move a measured number. Acceptance command plus
`test_examples`: 131 passed. Vale over the guides: 0 errors, 0 warnings.

*Gotchas.* A `literalinclude` needs `:language: python`, or the twin and the page show
the code unhighlighted. Put `# guide: start` above the imports so a reader sees where
`data` and `structure` come from. A fitted value from an ill-conditioned fit (the unheld
cell) moves by percent between the compiled and numpy paths; quote it as a rounded figure.
Python unbinds an `except ... as` name after the block, so a script that asserts on the
exception keeps its own reference.

Next: Guides from `using/data.md` (items 6, 7, 8 and 25: fit range and excluded regions,
a hump, a measured blank, checking a pattern before fitting), since it is the next largest
source and its items share a fixture. Item 8 needs a blank, and none ships in
`rietx.examples`; decide between bundling one and a no-exec reason before writing it.
Then `using/report.md` (13), `using/series.md` (14-17) and `using/history.md` (21).

- **2026-10-17** — Theory now lives in the new manual. The fourteen chapters are pages
  of the Theory tab, numbered as before, each opening with a sentence saying what it
  answers, and they pass Vale, the page contract and the equation-width check under the
  new theme. The old manual still shows them, through a one-line include at each old
  path, because Part 1 refers into them 79 times by equation and section number and
  rewriting those in chapters about to be mined into Guides would be wasted work. So
  Theory moved first and retires with the old tree, not one chapter at a time as
  WP-1975 § F8 planned for Part 1.

  *Done.* Inherited folded into Context by task, with one correction (`OLD_PAGES` holds
  46 pages, not 48). Part 2 moved to `docs/docs/theory/`; the Theory index carries the
  conventions, scope and units text, and the old root page includes it between two
  markers. Answer sentences under ten chapter titles. Three out-links fixed:
  `sec-units` now lives in both builds, `{doc}manual` became that `{ref}`, and the link
  to `using/refining.md`'s magnetic-width section was dropped (Guides note). 17 Concepts
  and Switching links rewritten to `../theory/…`; the link check now fails a link to a
  moved chapter's old address and covers Switching. `custom.css` in the new tree hides
  the bibliography label (the reference list printed `[AS64]` beside every entry since
  WP-1978) and lays out numbered equations as a grid. The three citation guards read
  both builds, under the `manual-build` group they lacked. `check_equations.py` moved
  and measures the new tree. Vale: equation numbers cited from papers spelled out,
  coinages reworded, 46 terms added to `terms.txt`, one Vale exemption round the
  McCusker quote in `estimation.md`. Root CLAUDE.md says where Part 2's source is.
  `/code-review high --fix` found 9 and fixed 5 (a paragraph split by the Vale
  comments, the landing page counted as a moved chapter, four stale chapter paths in
  `test_voigt.py`, `ATTRIBUTION.md` and `magnetic/operators.py`, ambiguous row labels).
  Declined: restoring a failure for every unknown `rietx.org` link (Part 1 and the
  skill are legal targets until retirement), and the duplicated CSS (the old copy goes
  with the old tree). No `### Inherited` note went out: 23 open WPs name Part 2 or an
  old chapter path, and each old path now holds a comment naming its new one.

  *Measured* (`[dev]`, darwin/arm64). Under pydata-sphinx-theme six equations ran under
  their own numbers by up to 191 px; the text column is about 645 px at a 1440 px
  window and 720 px at 1100. After the grid rule and six two-line reflows, all 156
  numbered equations fit at both widths. Vale over `docs/docs/`: 97 errors in the
  moved chapters before, 0 after. Acceptance files plus `test_vale`,
  `test_docs_versions` and `test_help`: 183 passed. The largest Theory twin is
  `estimation` at 40 831 characters, under the 50 000 cap. Fast selection on the final
  tree: 10 865 passed, 185 skipped, 2 xfailed (one run, 5:50, alone; the one red row
  there was the root CLAUDE.md line cap, fixed and re-run green). Against main that
  should be +3 items: the three citation guards now run once per build. The renamed
  link test is the one row `tests.added_test_times` reports, 0.06 s. The full
  selection did not run: no measured number can move in a docs-and-guards change.

  *Gotchas.* An HTML comment ends a paragraph in MyST, so a Vale exemption comment goes
  on blank lines round the whole paragraph. A link from a Concepts page into Theory must
  use the MyST heading slug (`#esds-and-the-bérar-lelann-inflation`), which differs from
  the HTML id wherever a heading has an accent or a symbol. The old tree's Part 2
  numbering and the new tree's agree only while both toctrees list the chapters in the
  same order.

  Next: Guides (task 2), one Part 1 chapter at a time. Decided after this entry was
  written: the old tree retires all at once when the last guide lands, so a guide
  leaves its old chapter untouched (Context, 2026-10-17).
- **2026-10-16** — filed from WP-1975's slate. No open WP owns the migration; 1443's passage
  fixes land here as each chapter is mined.
