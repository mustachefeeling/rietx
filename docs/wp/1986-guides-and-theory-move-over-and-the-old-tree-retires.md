# WP-1986 — Guides and Theory move over, and the old tree retires

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1978 (the new tree); 1985 (the report text the guides show); 1979 (redirect stubs)
Priority: P3 2026-10-16 — waits on 1985 alone now that WP-1978's tree is built (PR #1004)

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
