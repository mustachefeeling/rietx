# WP-1986 — Guides and Theory move over, and the old tree retires

Milestone: unscheduled · Status: ⬜
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

### Inherited

- **2026-10-17, from WP-1980.** Every page moved into `docs/docs/` now gets a markdown twin,
  `page.html.md`, written by the HTML build (`docs/markdown_twin.py`). The twin is held to
  the page contract too: one H1, an answer sentence, at most 50 000 characters and no MyST
  left in it (`test_every_page_has_a_twin_that_keeps_the_contract`). A Theory chapter whose
  equations push its twin past the cap must be split. The twin already handles the old
  tree's node types: notes and warnings, titled admonitions, math, `{eq}` and `{cite}`, the
  bibliography, the `only-light`/`only-dark` image pairs, tab sets and dropdowns
  (`test_the_twin_writes_every_node_type_the_old_tree_uses`). `{download}` (six uses in
  the old tree) has a handler that no test has run. A node type with no handler fails `-W`
  as `unknown node type`; add it to `_normalise` or `TwinTranslator`.
  Each moved page also gets a line in `llms.txt`, under the H2 of its tab, carrying its
  answer sentence. When the old tree retires, the site root's `llms.txt`
  (`docs_versions.assemble`) already points into `/docs/`, so it needs no change.
- **2026-10-17, from WP-1984.** The Switching tab's feature table
  (`docs/docs/switching/at-a-glance.md` § Features and what they were checked against) has a
  "Read more" column that links Concepts and Reference pages, because Guides held only an
  index when it was written. Point each row at the guide for that task once the guides exist.
  The TOPAS, GSAS-II and FullProf pages also hold `rietx.org/…` links to the old manual's
  Theory chapters (`parameterisation.html`, for one), which the retirement must re-point as
  it does the Concepts tab's. The pages' python blocks carry `no-exec` lines that name
  `examples/switching.py`, so a rename of anything that script calls fails
  `tests/test_examples.py`, not the manual build.
- **2026-10-17, from WP-1983.** Two questions a newcomer check asked of the Concepts tab
  have no page yet, and both belong in Guides. Neither has been checked against the code.
  First, does a fit's first stage estimate the phase scale, or start from the stored value
  (the parameter map gives a default of 1.0)? That belongs in the guide on starting a fit.
  Second, do excluded regions survive a `Refinement.checkout` or a `rx.replay`? They live
  in `project.json` and no history node records them (`schemas/project.py`), so a checkout
  should keep the current ones and a replay should use whatever the pattern carries. That
  belongs in the guide on excluding a region.
- **2026-10-17, from WP-1983.** The six Concepts pages link Part 2 on the site, as
  `https://rietx.org/<chapter>.html#<id>` (16 links into six chapters, nine of them
  `estimation`). Moving a chapter
  means rewriting its links to `../theory/<chapter>.md#<id>` in the same commit.
  `tests/test_manual.py`'s `_OLD_THEORY_LINK` branch resolves the old form against the old
  tree's build, by HTML id only. Delete it once the last chapter has moved, and the check
  then reads `../theory/` links alone. Part 1 material the pages now cover, so a retiring
  chapter can point there: `using/concepts.md` § The parameter groups and § Why the groups
  correlate (concepts/parameters.md, concepts/correlations.md); `using/data.md` § Explicit
  humps (parameters.md § Humps); the `.rex` part of `using/files.md` (concepts/project.md);
  `using/report.md`'s layer descriptions (concepts/report.md). Stale in the old chapters,
  for whoever mines them into Guides: `report.md` counts the Layer 1 gates as four where
  the code has four region checks plus a global gate, and its `FitReport` table omits
  `microstructure`; `files.md` says `Project.open` checks four bindings where the code has
  nine refusals, and calls `history.jsonl` append-only though `RefinementTree.save`
  rewrites it; `src/rietx/report/apply.py`'s docstring says "four of the sixteen" kinds
  where `ActionKind` has 18.
- **2026-10-16, from WP-1979 (closed).** The stub mechanism is `docs/docs_versions.py`.
  Retiring a chapter adds one row to its `RETIRED` map (old path to new page, both without
  `.html`, the new one may carry `#heading`) in the same commit that deletes the chapter.
  `OLD_PAGES` freezes the 48 pages the old tree published, and
  `tests/test_docs_versions.py` fails while one is neither built nor in `RETIRED`. pages.yml
  writes each stub at deploy time. It points into `stable/` once a release holds the page, and
  into `dev/` until then. Three pieces of WP-1979's task 4 move here, because none of the 13
  pages `help.py`'s anchors name exists in the new tree yet:
  - a versioned docs base beside `_about.DOCS_URL`, from `dev` for a `.dev0` build and `X.Y`
    otherwise (the mapping is `docs_versions.docs_version`, which then moves into the
    package, since `_about.py` imports nothing);
  - `help.py`'s anchors and the GUI's `docs_url` (`gui/session.py:265`) on that base;
  - `tests/test_help.py::test_every_anchor_resolves_in_the_built_manual` pointed at the new
    tree's build.
  When the old tree goes, its `pages.yml` build step goes too, and the stubs remain.
- **2026-10-16, from WP-1985 (closed).** The report text a guide shows is rewritten (the
  rustc-style line form, `FitReport.summary` one sentence a line, every message reworded).
  The Reference tab's diagnostic page is now `reference/diagnostics.md`, a table linking
  six subsystem pages (`diagnostics-refinement.md` and five more), each code a section
  with its explanation from `rietx.help.DIAGNOSTIC_HELP`. The glossary's diagnostics arm
  is `diagnostics` (was `peak_diagnostics`) and now holds all 253 codes. Vale reads
  `docs/docs/_generated/` too, and CI writes the bodies before Vale runs.
- **2026-10-16, from WP-1982.** A chapter moved into `docs/docs/` meets Vale in CI's lint
  job, which fails on an error. Over the whole old manual the house configuration finds
  463 errors: 417 spellings (code identifiers outside backticks such as `str` and `c_w`,
  American forms such as "serializable", and words the term list may yet take), 14 banned
  words ("just" 12) and 8 "fnmatch". It also prints 458 warnings, among them 101 notation
  left as text, 62 "caller" and 35 prices. Expect each chapter's move to carry its share of
  those fixes. A word that belongs in the domain goes in `docs/vale/terms.txt`.
- **2026-10-16, from WP-1981.** Three old-tree pieces now have a replacement in the new
  Reference tab. The glossary (`using/glossary.md`, written by the old `conf.py`'s
  `_write_glossary`) is covered for parameters by `reference/parameters.md`. Its other arms
  (stage fields, peak flags, reader options and the rest) have no new page yet. The plan
  diagram in `using/concepts.md` is replaced by `reference/plans.md`. The old tree's
  702 000-character rendering of the skill (`_write_skill`) is replaced by
  `reference/agents.md`, which links the skill instead.
- **2026-10-16, from WP-1978.** The new tree is `docs/docs/` (PR #1004). Its `conf.py` takes
  the fenced constants, the citation style, the mermaid theme and the `{source}` role from
  `docs/sphinx_shared.py`, which the old `conf.py` imports too. `tests/test_manual.py` builds
  it as the `built_docs_tree` fixture (xdist group `manual-build`), reads its pages as
  `DOCS_PAGES`, and holds each to the page contract (`_contract_breaches`). Theory moves into
  `docs/docs/theory/`, whose `references.md` already renders the shared bibliography.
  `test_every_bib_entry_is_cited` counts citations across both trees, so an entry stays cited
  while its chapter is half moved. The `{source}` coverage test holds on every page of the new
  tree, not only Theory. Nothing renders the tutorial notebooks under Start yet: `myst_nb` is
  loaded, but the copy step (`_copy_tutorials`) stays in the old `conf.py`, and retiring that
  tree is when it moves. `DOCS_PAGES` globs `.md` only, so once a notebook lands under Start
  the page contract, the register guard and name resolution skip it until the glob widens.
  Whether a notebook keeps the page contract is a decision for that move.

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
