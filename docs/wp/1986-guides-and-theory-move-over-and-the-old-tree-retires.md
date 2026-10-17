# WP-1986 — Guides and Theory move over, and the old tree retires

Milestone: unscheduled · Status: 🔄 2026-10-17 — claimed by @yue-here
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
- The six Concepts pages link Part 2 as `https://rietx.org/<chapter>.html#<id>` (16 links into
  six chapters, nine of them `estimation`). The Switching tab's TOPAS, GSAS-II and FullProf
  pages hold such links too (`parameterisation.html`, for one). Moving a chapter means
  rewriting its links to `../theory/<chapter>.md#<id>` in the same commit.
  `_OLD_THEORY_LINK` in `tests/test_manual.py` resolves the old form against the old build by
  HTML id; delete it once the last chapter has moved.

**Guides.**
- Two questions a newcomer asked of the Concepts tab belong here, neither checked against the
  code. Does a fit's first stage estimate the phase scale, or start from the stored value (the
  parameter map's default is 1.0)? That goes in the guide on starting a fit. Do excluded regions
  survive `Refinement.checkout` or `rx.replay`? They live in `project.json` and no history node
  records them (`schemas/project.py`), so a checkout should keep the current ones and a replay
  should use whatever the pattern carries. That goes in the guide on excluding a region.
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
- Three pieces of WP-1979's task 4 belong here, because none of the 13 pages `help.py`'s
  anchors name exists in the new tree yet: a versioned docs base beside `_about.DOCS_URL`
  (`dev` for a `.dev0` build, `X.Y` otherwise; the mapping `docs_versions.docs_version` moves
  into the package, since `_about.py` imports nothing); `help.py`'s anchors and the GUI's
  `docs_url` (`gui/session.py`) on that base; and
  `tests/test_help.py::test_every_anchor_resolves_in_the_built_manual` pointed at the new
  tree's build.
- When the old tree goes, its `pages.yml` build step goes too, and the stubs remain.
- Nothing renders the tutorial notebooks under Start yet. `myst_nb` is loaded in the new
  `conf.py`, but the copy step (`_copy_tutorials`) is in the old one and moves at retirement.
  `DOCS_PAGES` globs `.md` only, so once a notebook lands under Start the page contract, the
  register guard and name resolution skip it until the glob widens. Whether a notebook keeps
  the page contract is decided at that move.

## Non-goals

- The tutorials themselves (WP-1545 owns them).

## Tasks

- [ ] Theory: Part 2's chapters moved, guards pointed at the new tree, `check_equations.py`
      ported.
- [ ] Guides: one page per task, mined chapter by chapter; each mined chapter retired behind
      its stub in the same commit.
- [ ] GUI chapters moved with `test_gui_manual.py`.
- [ ] The old tree's build, guards and `pages.yml` steps removed once no chapter is left; the
      landing page's link to `/manual.html` pointed at `/docs/`.
- [ ] Skill: links into the manual updated to the new URLs.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_gui_manual.py tests/test_landing.py -n auto --dist loadgroup
```

## Handover log

- **2026-10-16** — filed from WP-1975's slate. No open WP owns the migration; 1443's passage
  fixes land here as each chapter is mined.
