# WP-1978 — The new manual's tree: six tabs beside the old, and its page contract

Milestone: unscheduled · Status: ✅ 2026-10-16 — `docs/docs/` builds with six tabs and the page contract is tested, PR #1004
Track: The repo's own process
Depends on: —

## Goal

A second Sphinx tree, built beside `docs/manual/`, renders under pydata-sphinx-theme with six
top tabs and a front page of three audience cards. Tests hold every page in it to the page
contract, the register and the evidence trail.

## Context

WP-1975 re-planned the manual and chose its toolchain from a spike. Its decisions, restated:

- **Migration: a new tree beside the old.** Each old chapter is retired once its content has
  been mined (WP-1986). The old tree's guards stay green throughout.
- **Toolchain: Sphinx with pydata-sphinx-theme** (spike, WP-1975 § I). Keep MyST, myst-nb,
  sphinx-design, sphinxcontrib-bibtex and sphinxcontrib-mermaid. The spike's `conf.py`
  (`docs/wp/1975-spike/sphinx/conf.py`) is the starting point for the theme options and the
  switcher. Its `{source}` role is a 15-line stand-in. The old tree's role reports an
  unresolvable name as a build error and resolves module constants, so that one is kept.
- **Layout: six tabs.** Start (install, first fit, notebooks), Guides (how-to, by topic),
  Concepts (explanation), Reference (API, parameter map, files, CLI, GUI, diagnostics),
  Theory (today's Part 2), Switching (for users of other codes). Each tab is one Diátaxis
  type except Start and Switching. Titles do the type labelling: "How to …" for a guide,
  "About …" for a concept.
- **Front page: three cards, in this order.** New to rietx; Coming from another code;
  Supervising an agent. The agent itself is served by the skill and the markdown twin
  (WP-1980), never by front-page prose.
- **The page contract is tested, on the new tree only.** A test fails a page that has no
  answer sentence under its H1, passes 50 000 characters, or opens a section on a
  back-reference ("as above"). Old chapters are exempt until retired.
- **The trail.** Theory keeps today's check: every displayed equation has a `*Source:*` line
  whose symbol imports, and every bib entry is cited. An equation on any other page carries
  the same. A physics claim on a Concepts or Guides page links its Theory section, and a test
  checks that the link resolves.
- **The register guard carries over.** `tests/test_manual.py::test_the_manual_keeps_its_register`
  (no em dash, no bold `**` in prose) applies to the new tree.
- **Admonitions use the `:::` colon fence.** Vale lints a colon-fenced admonition and skips a
  backtick-fenced one (measured in the spike, WP-1975 § I), and WP-1982 runs Vale here.
- **The skill page is dropped.** The new tree does not render the skill. A "For agents" page
  under Reference says what it is and links its published copy at `/skill/rietx/`.

Seams in the old tree, for reuse rather than copy: `docs/manual/conf.py` (substitutions at 165,
glossary writer 304-411, tutorial copy 427-456, `{source}` role 645-660);
`tests/test_manual.py` (build fixture at 79, register guard near 773); `tests/test_manual_api.py`
(name resolution and the API-surface partition, which read code spans and fences and so work
on any MyST tree). `rietx.org/` is the landing page and the manual is `/manual.html`
(`docs/landing/README.md`); this WP builds the tree locally and leaves deployment to WP-1979.

## Non-goals

- Deploying it, versions and redirects: WP-1979.
- The markdown twin and `llms.txt`: WP-1980.
- Generated reference pages: WP-1981. Vale: WP-1982.
- Page content beyond a stub per tab and the front page: WPs 1983, 1984, 1986.

## Tasks

- [x] The tree: a directory (`docs/docs/`, chosen over `docs/site/`), `conf.py`
      from the spike's, six tab indexes, the front page with its three cards, `-W` clean.
- [x] Theory tab infrastructure: `math_numfig`, the shared `references.bib`, the `{source}`
      role and `myst_substitutions` shared with the old `conf.py` rather than copied, so one
      change reaches both trees. Importing the old `conf.py` runs `_write_glossary()` and
      `_copy_tutorials()` and sets its whole Sphinx config, so move the shared parts into a
      module both trees import.
- [x] Page-contract tests on the new tree: answer sentence, 50 000-character cap, no
      back-reference opener.
- [x] Register guard and trail tests extended to the new tree; the Theory-link check for
      Concepts and Guides pages.
- [x] `tests/test_manual_api.py`'s name resolution and partition read the new tree as well.
- [x] Skill: none. The skill is unchanged; WP-1981's "For agents" page links it.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py -n auto --dist loadgroup
```

## References

- Procida, D. Diátaxis. https://diataxis.fr
- pydata-sphinx-theme documentation, version switcher and announcement banner.

## Handover log

- **2026-10-16** — closed. The rebuild now has a tree to write into. `docs/docs/` builds
  under pydata-sphinx-theme with six tabs and a front page of three audience cards. Each tab
  is a one-paragraph stub. The fenced constants, the citation style and the `{source}` role
  now live in one module that both trees import, so a retuned threshold reaches both. Tests
  hold every new page to the page contract, and the old tree's register, trail and
  name-resolution guards read the new tree too. Nothing is deployed yet.

  *Done.* `docs/sphinx_shared.py` holds what both conf.py files share: the substitutions
  (minus `release` and `N_TUTORIALS`, which are per build), the author-year citation style
  and its registration, the mermaid theme, and the `{source}` role. The old `conf.py` keeps
  its glossary writer, tutorial copy and skill page. It reaches the module through a
  `sys.path` append, since `docs/` is not a package. `docs/docs/` was chosen over
  `docs/site/` because `docs/landing/site/` and `docs/lite/site/` are both gitignored build
  outputs. In `tests/test_manual.py`, `built_docs_tree` builds the new tree in the
  `manual-build` group. The four built-HTML guards run on both builds. The register guard,
  the citation sets and the three `{source}` tests read `DOCS_PAGES` too. New tests cover
  the page contract (`_contract_breaches`), the Theory-link check and the front page's
  cards and tabs. Each rule has a parametrised case that makes it fail on purpose.
  `tests/test_manual_api.py` reads every new page, Theory included, because a code span on
  any page is a name a reader may type. `pydata-sphinx-theme>=0.23` joined the `docs`
  extra, at the version the spike measured.

  *Review.* `/code-review high --fix` found nine issues and fixed eight in one commit. A
  Theory link may name its section by MyST slug as well as by HTML id; I limited that to
  H1 to H3, the depth `conf.py` gives anchors. A link to the tree root crashed the check. A
  dot inside a code span passed as an answer sentence. Messages named pages by file name,
  and the new tree has seven `index.md`. The three built-HTML scans became one helper.
  `conf.py` now takes the distribution name from `_about`. Declined: holding notebooks to
  the page contract. None exists in the tree yet, so the decision went to WP-1986's
  `### Inherited`.

  *Measured.* Venv `[dev]`, macOS arm64. The new tree builds `-W` in about 2 s and the old
  one in about 13 s, one run each. `tests/test_manual.py` went from 23 tests to 44.
  `tests/test_manual_api.py` stays at 17. Probes confirmed both guards reach the new tree:
  a planted `rx.no_such_export` failed name resolution, and a planted em dash and bold mark
  failed the register guard. The fast selection after the review, run alone, gave 10630
  passed, 2 failed, 191 skipped and 2 xfailed in 3:50. Both failures were this handover's
  own edits to `test_docs_consistency.py`'s inputs: CLAUDE.md one line over its cap, and an
  example link in 1983's `### Inherited` read as a real one. After the fix that file and
  `test_help.py` pass, so the tree stands at 10632 passed. The six added test functions cost
  0.07 s in total in that run.

  *Gotchas.* pydata-sphinx-theme writes a Jinja template, `_static/webpack-macros.html`, into
  the build output, so the built-HTML guards skip `_static/`. The new tree's `index.html`
  has the landing page's name, so the landing exclusion applies to the old build only. The
  phone-width screenshot from headless Chrome was clipped, so the layout at 390 px is
  unverified. The desktop front page was checked by eye.

  *Forward references.* Written into the `### Inherited` of 1979, 1980, 1981, 1982, 1983,
  1984, 1986 and 1545. 1545 had been told the new tree renders its notebooks, and it does
  not yet. 1979 to 1984 are back to P2 now the tree exists, and 1986 waits on 1985 alone.

  Next: 1979 (deployment and versions) and 1981 (the generated reference pages) can start
  at once. 1983 and 1984 can start too, since neither shows fit output. Guides and Theory
  (1986) wait for 1985's report text.
- **2026-10-16** — filed from WP-1975's slate. No open WP owned a new tree: 1443 fixes
  passages in the old chapters, and its `### Inherited` already says the rebuild is coming.
