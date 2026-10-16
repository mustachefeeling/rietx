# WP-1983 — The Concepts tab

Milestone: unscheduled · Status: ✅ 2026-10-17
Track: The repo's own process
Depends on: 1978 (the new tree); 1981 soft (the parameter map it links)

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

**The tree and its guards** (WP-1978, PR #1004). The new tree is `docs/docs/`.
`tests/test_manual.py` builds it as the `built_docs_tree` fixture (xdist group
`manual-build`), reads its pages as `DOCS_PAGES` and holds each to the page contract
(`_contract_breaches`). The contract fails a page with no answer sentence under its H1, a page
over 50 000 characters, and a section whose first sentence leans back (`_BACK_REFERENCE`).
`test_every_theory_link_from_concepts_and_guides_resolves` reads markdown links into
`../theory/` and checks the built page and the section a fragment names, by HTML id or by MyST
slug. `{ref}` and `{doc}` roles are left to `-W`. Heading anchors reach depth 3.

**Theory links point at the old tree until WP-1986** (decided 2026-10-16). The new Theory tab
holds only its index and `references.md`. Part 2 is still `docs/manual/*.md` (14 chapters,
5 415 lines), served at `rietx.org/<chapter>.html`. Moving it here would mean re-pointing 27
cross-references from Part 1 and porting the equation guards and `check_equations.py`, which
is WP-1986's Theory item. So a Concepts page links `https://rietx.org/<chapter>.html#<id>`,
and the link check learns to resolve that form against the old tree's build. WP-1986 rewrites
each such link to `../theory/` as it moves the chapter.

**What the pages link instead of restating** (WP-1981). The parameter map is
`docs/docs/reference/parameters.md`, grouped as cell and structure, phase amount and intensity
corrections, microstructure, instrument, time of flight, background, and named variables
(`vars.*`). Every preset's stages are drawn on `reference/plans.md`, generated from the plan
objects. A page that explains staging links that page and draws no ladder by hand, since the
old tree's hand-drawn one drifted.

**Vale** (WP-1982). CI's lint job runs Vale on every committed page of `docs/docs/`, and an
error fails it: British spelling against en_GB plus the term list, the banned words, "fnmatch"
in prose, and a few Microsoft rules. Warnings print and pass: a synonym the term list rejects
("cell edge", "thermal parameter"), notation left as text (`U_iso`), "caller" and "buys". Run
`vale sync && vale docs/docs` before pushing. A crystallographic word Vale does not know goes
in `docs/vale/terms.txt`, then `python docs/vale/terms.py`. A one-word heading is a suggestion,
and so are "glob", "schema" and "column" until a page explains them.

## Non-goals

- Generated tables (WP-1981): this tab links them.
- Retiring the old chapters (WP-1986).

## Tasks

- [x] The Theory-link check resolves `https://rietx.org/<chapter>.html#<id>` against the old
      tree's build, with a case that makes it fail on a missing page and a missing id.
- [x] About a fit: the life of a fit, from pattern and models to result and history, as one
      diagram with a paragraph a box.
- [x] About parameters: the groups, what each is for, its scope (instrument, specimen, phase,
      atom), and the background-and-humps story; the full tables live in WP-1981's map.
- [x] About the report: its three layers and what each can and cannot claim.
- [x] About correlations and esds: why a direction the data does not move has no esd.
- [x] About the project: what each file in a `.rex` is for, linking the generated tree.
- [x] Usage tiers: which calls most fits use, measured from the examples and tutorials, and a
      newcomer check of the tab.
- [x] Skill: none.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py -n auto --dist loadgroup
```

## Handover log

- **2026-10-17** — closed. The new manual has a Concepts tab: six short pages that explain
  how rietx works to someone who already refines in another program. They cover a fit from
  inputs to history, the parameter groups with the background and its humps, the report's
  three layers, why a direction the data do not move has no esd, the project directory,
  and which calls most fits make. Each physics claim links its Theory section. Theory still
  lives in the old tree, so the links point there, and a test resolves them against the old
  build until WP-1986 moves Part 2. Before merge, a reader playing a GSAS-II and TOPAS user
  found two wrong claims and a dozen terms used before they were explained, and the code
  review found five more claims at odds with the code. All are fixed.

  *Arrival.* The three `### Inherited` entries (1978, 1981, 1982) all still held and were
  folded into Context on 2026-10-16. One gap the WP had not seen: the Theory tab was empty,
  so "link the Theory section" had nowhere to land. The maintainer chose old-tree links with
  a checked resolver over moving Part 2 early (14 chapters, 5 415 lines, 27 Part 1
  cross-references) or deferring the links.

  *Done.* `docs/docs/concepts/` `fit.md`, `parameters.md`, `report.md`, `correlations.md`,
  `project.md`, `usage.md`, listed in `index.md`. `tests/test_manual.py`'s Theory-link check
  reads `https://rietx.org/<chapter>.html#<id>` against `built_manual` by HTML id (that tree
  makes no heading slugs) and fails any other `rietx.org` link from Concepts or Guides.
  `tests/test_manual_api.py`'s `_included_slice` reads the lines a `{literalinclude}` shows,
  cut by whole lines as Sphinx does, and refuses `:lines:`/`:pyobject:` slices it cannot
  read. Tutorial 02 uses `rx.viz`, which the whole-file read had flagged. Nine substitutions
  were added to `docs/sphinx_shared.py`, so every threshold the pages quote is the live
  constant: the five Layer 1 gates, `MIN_COEF_SIGNIFICANCE`, `PHASE_SUPPORT_SIGMA`,
  `SEPARABILITY_MIN_SS_RATIO`, and `LAYER0_PEAK_SIGMA`, which is read off `build_layer0`'s
  signature. `bcc`, `crystallographer` and `oxygens` were added to `docs/vale/terms.txt`.

  *Measured.* The usage tiers come from tracing nine scripts (the six tutorials,
  `nac_11bm`, `skill_worked_default`, `srm660c_lab`) with `sys.setprofile`. A call counts
  when the calling frame is the script and the callee's code is in the package. That counts
  calls only, so field reads are absent. `stage_trajectory` is a developer tool that needs
  arguments and was left out. The tracer was not committed. To re-measure after a new
  tutorial, run each script under `runpy` with that profile hook. Each script took 1-26 s,
  [dev] venv, darwin/arm64. Fast suite on the final tree, same venv and platform, alone:
  10728 passed, 191 skipped, 2 xfailed, 5:15. One failure in that run was the WP index,
  staled by this close's own Status edit mid-run; regenerated, `test_docs_consistency.py`
  is 25 passed. The session added no test functions (two extended, one helper), so
  passed+skipped should equal `main`'s. CI's matrix is the comparison. Vale: 0 errors,
  0 warnings over the seven Concepts pages. The full suite did not run, since no measured
  number can move.

  *Review.* `/code-review high --fix` made ten fixes, and nine were kept. It wrongly
  inverted the `needs_held_cell` row into "a cell is held". The row is the wavelength
  (`refine.py:2403`, `_wavelength_paths()`), so that line was restored with its better
  wording. The review left three things unfixed: `unreadable` is also the catch-all
  abstention kind, `IMPURITY_SIGMA` renders as "8.0", and "0.98" and "1 %" stay written out
  as defaults. The newcomer check's findings were folded in, except these: `usage.md` was
  kept (this WP asks for the measurement), the index's two framing lines were kept
  (WP-1978's), and no scope statement on neutron, TOF or joint fits was added. Two questions
  stay unanswered: whether stage 1 seeds the scale, and whether excluded regions survive a
  checkout.

  *Gotchas.* Vale is not in the venv. `brew install vale` (3.24.0) was this machine's
  install. Tutorial 06 writes `rietx_output/` into the working directory, so a run from the
  repo root leaves it untracked there. `/code-review --fix` edits pages too, so read its page
  diffs before committing.

  Next: WP-1984 (Switching) or WP-1980 (markdown twins), both unblocked. 1980's `### Inherited`
  now lists the three node types this tab adds. WP-1986 inherits the link rewrite and the
  stale old-chapter claims the mining found.
- **2026-10-16** — filed from WP-1975's slate. No open WP owns explanation pages: 1443 fixes
  eleven passages in the old Part 1, and its `### Inherited` says those fixes land in the new
  tree.
