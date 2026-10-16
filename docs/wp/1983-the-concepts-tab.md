# WP-1983 — The Concepts tab

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1978 (the new tree); 1981 soft (the parameter map it links)
Priority: P2 2026-10-16 — back to P2: WP-1978's tree is built (PR #1004)

## Goal

The Concepts tab explains how rietx works to a reader who already knows Rietveld refinement. It
covers the life of a fit, the parameters as a crystallographer groups them, how to read the
report, and why correlated parameters are reported the way they are. Each page is short, starts
with its answer, and links the Theory section behind every physics claim.

## Context

The maintainer asked for a mental-model part of the manual (WP-1975 § A). They found the old
Part 1 too dense and too narrative. In particular they asked for:
- a structured overview of the `.rex` project with minimal narrative (the generated tree is
  WP-1981's; this tab explains what it is for);
- the parameters grouped as a crystallographer expects (cell with structure, microstructure,
  instrument, and background as its own group, with how it interacts with humps);
- the four additions they chose: a life-of-a-fit page, a scope column, GSAS-II/TOPAS/FullProf
  names beside rietx's, and measured usage tiers plus a newcomer check.

**Rules for these pages** (WP-1975 § F8, § C4):
- The first audience knows the method. Explain rietx's choices, not Rietveld refinement.
- The headline stays in view and the evidence sits a fold away. Measurement diaries (dates,
  venvs, timings, WP history) leave the page for `docs/VALIDATION.md`, the WPs and the release
  notes. Differences from other codes go in labelled callouts.
- A physics claim links its Theory section; WP-1978's test checks the link resolves.
- Titles are "About …". No page passes 50 000 characters.
- Microsoft's style as the base, with the repo's rules winning (WP-1982).

**Where the content is now** (old tree, `docs/manual/using/`, measured 2026-10-15). Part 1 is
25 chapters and 15 885 lines. The largest are `files.md` 1988, `series.md` 1832,
`refining.md` 1521, `data.md` 1412, `indexing.md` 1315 and `results.md` 1012.
`using/concepts.md` holds the angular-signature parameter table (lines 15-33) and the
correlation figures, and its hand-drawn plan mermaid (461-474), which drifted from
`mccusker_structural` once already.
Background and humps are in Part 2's `background.md:131-177` and `using/data.md:1160-1379`.
Mine these; do not move them whole.

This tab shows no fit output, so it can start before the report-text rewrite (WP-1985). Where
a page must show a report, quote the shape and link the Reference page.

### Inherited

- **2026-10-16, from WP-1981.** The soft dependency is met. The parameter map is
  `docs/docs/reference/parameters.md` (grouped as cell and structure, phase amount and
  intensity corrections, microstructure, instrument, time of flight, background, named
  variables), and every preset's stages are drawn on `reference/plans.md`, generated from
  the plan objects. A Concepts page that explains staging should link the plan page
  instead of drawing a ladder by hand, since the old tree's hand-drawn one drifted.
  `vars.*` now has a help entry, so a page about named variables can link the map's
  "Named variables" group.
- **2026-10-16, from WP-1978.** The new tree is `docs/docs/` (PR #1004). Its `conf.py` takes
  the fenced constants, the citation style, the mermaid theme and the `{source}` role from
  `docs/sphinx_shared.py`, which the old `conf.py` imports too. `tests/test_manual.py` builds
  it as the `built_docs_tree` fixture (xdist group `manual-build`), reads its pages as
  `DOCS_PAGES`, and holds each to the page contract (`_contract_breaches`).
  `test_every_theory_link_from_concepts_and_guides_resolves` reads markdown links into
  `../theory/` and checks the built page and the section a fragment names, by HTML id or by
  MyST slug; `{ref}` and `{doc}` roles are left to `-W`. Heading anchors reach depth 3. The
  page contract fails a
  page with no answer sentence under its H1, one over 50 000 characters, and a section whose
  first sentence leans back (`_BACK_REFERENCE`).

## Non-goals

- Generated tables (WP-1981): this tab links them.
- Retiring the old chapters (WP-1986).

## Tasks

- [ ] About a fit: the life of a fit, from pattern and models to result and history, as one
      diagram with a paragraph a box.
- [ ] About parameters: the groups, what each is for, its scope (instrument, specimen, phase,
      atom), and the background-and-humps story; the full tables live in WP-1981's map.
- [ ] About the report: its three layers and what each can and cannot claim.
- [ ] About correlations and esds: why a direction the data does not move has no esd.
- [ ] About the project: what each file in a `.rex` is for, linking the generated tree.
- [ ] Usage tiers: which calls most fits use, measured from the examples and tutorials, and a
      newcomer check of the tab.
- [ ] Skill: none.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py -n auto --dist loadgroup
```

## Handover log

- **2026-10-16** — filed from WP-1975's slate. No open WP owns explanation pages: 1443 fixes
  eleven passages in the old Part 1, and its `### Inherited` says those fixes land in the new
  tree.
