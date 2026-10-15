# WP-1978 — The new manual's tree: six tabs beside the old, and its page contract

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P2 2026-10-16 — a feature the maintainer asked for, and the tree every other rebuild WP (1979-1986) writes into

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

- [ ] The tree: a directory (name it at the start; `docs/site/` or `docs/docs/`), `conf.py`
      from the spike's, six tab indexes, the front page with its three cards, `-W` clean.
- [ ] Theory tab infrastructure: `math_numfig`, the shared `references.bib`, the `{source}`
      role and `myst_substitutions` shared with the old `conf.py` rather than copied, so one
      change reaches both trees. Importing the old `conf.py` runs `_write_glossary()` and
      `_copy_tutorials()` and sets its whole Sphinx config, so move the shared parts into a
      module both trees import.
- [ ] Page-contract tests on the new tree: answer sentence, 50 000-character cap, no
      back-reference opener.
- [ ] Register guard and trail tests extended to the new tree; the Theory-link check for
      Concepts and Guides pages.
- [ ] `tests/test_manual_api.py`'s name resolution and partition read the new tree as well.
- [ ] Skill: none. The skill is unchanged; WP-1981's "For agents" page links it.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html <new tree> <new tree>/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py -n auto --dist loadgroup
```

## References

- Procida, D. Diátaxis. https://diataxis.fr
- pydata-sphinx-theme documentation, version switcher and announcement banner.

## Handover log

- **2026-10-16** — filed from WP-1975's slate. No open WP owned a new tree: 1443 fixes
  passages in the old chapters, and its `### Inherited` already says the rebuild is coming.
