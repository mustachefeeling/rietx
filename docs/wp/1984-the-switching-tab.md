# WP-1984 — The Switching tab

Milestone: unscheduled · Status: 🔄 2026-10-17 — claimed by @yue-here
Track: The repo's own process
Depends on: 1978 (the new tree); 1981 soft (the foreign-name map and the roadmap it links)
Priority: P2 2026-10-16 — back to P2: WP-1978's tree is built (PR #1004)

## Goal

A user of TOPAS, GSAS-II or FullProf can judge rietx in a few minutes from one tab. It holds
rietx at a glance, a page for each of the three codes, the validation evidence, and the
roadmap.

## Context

The switcher is the second of three front-page audiences (WP-1975 § F8). They want a verdict,
not a course.

**Precedent** (WP-1975 § F6). Polars' "Coming from pandas" has two parts. First comes
"Differences in concepts", explaining why it behaves differently. Then comes "Key syntax
differences", with paired code blocks, pandas first and Polars second. No Rietveld code
publishes such a comparison.

**What rietx has to draw on**, none of it stated as a comparison today:
- the README feature list (modes, data types, corrections, readers and writers for TOPAS,
  FullProf, GSAS and GSAS-II);
- `docs/VALIDATION.md`'s tiers, especially the `cross_code` rows run with the other code's
  protocol adopted. Examples: FAP against GSAS-II; LaB6 + cBN against TOPAS to under 50 ppm;
  TOPAS Y_calc at zero cycles for seven exported models; a GSAS-II spherical-harmonics texture
  golden;
- the readers in `io/projects/*`, which already know each code's vocabulary. WP-1981 builds
  the foreign-name map from them, and this tab links it;
- the maintainer's essay `why.html` for why rietx differs.

**Decisions** (WP-1975 § F8):
- **No "what rietx does not do" page.** A roadmap of features in development and planned
  stands in its place, generated from the open milestones (WP-1981). It must not go stale the
  way `compatibility.md:172` did.
- Differences from other codes go in labelled callouts. Every claim at a glance links its
  validation row; a cell without evidence is not written.
- Comparing against another code means adopting its protocol (root CLAUDE.md § Conventions).
  A page quoting an agreement quotes the protocol with it.

### Inherited

- **2026-10-17, from WP-1983 (closed).** The Concepts tab never says which data rietx
  covers: neutron, time of flight, joint fits of several patterns. A newcomer check asked
  for it, and the answer belongs in this WP's "rietx at a glance" table. Once that table
  exists, link it from `docs/docs/concepts/fit.md` § Inputs, where the pattern and the
  instrument are introduced, so the Concepts tab does not grow a second copy of the scope.
- **2026-10-16, from WP-1982.** Vale reads every committed page of `docs/docs/` in CI's
  lint job, and an error-level alert fails it. The errors are British spelling against the
  en_GB dictionary plus the term list, the maintainer's banned words, "fnmatch" in prose and
  a few Microsoft rules. Warnings are printed and do not fail: a synonym the term list
  rejects ("cell edge", "thermal parameter"), notation left as text (`U_iso`), a program's
  role ("caller") and a price ("buys"). Run `vale sync && vale docs/docs` before pushing
  (`CONTRIBUTING.md`). A crystallographic word Vale does not know goes in
  `docs/vale/terms.txt`, then `python docs/vale/terms.py`. A one-word section heading is
  flagged as a suggestion, and so is "glob", "schema" or "column" until a page explains it.
- **2026-10-16, from WP-1981.** The soft dependency is met. The foreign-name map is
  `docs/docs/reference/foreign-names.md`, with GSAS-II, GSAS, TOPAS and FullProf columns
  and a Conversions section (U, V, W units, FullProf's swapped X and Y, Uiso against B,
  SH/L, polarization, TOPAS moments and scale). A test holds every foreign name to a
  string literal in that format's reader or writer. The roadmap is
  `reference/roadmap.md`. Link both, and do not restate the conversions.
  One fact for the prose: the GSAS-II `.gpx` and TOPAS readers build a `Structure` only,
  so the instrument names in those columns come from `.instprm` and from rietx's writers.
- **2026-10-16, from WP-1978.** The new tree is `docs/docs/` (PR #1004). Its `conf.py` takes
  the fenced constants, the citation style, the mermaid theme and the `{source}` role from
  `docs/sphinx_shared.py`, which the old `conf.py` imports too. `tests/test_manual.py` builds
  it as the `built_docs_tree` fixture (xdist group `manual-build`), reads its pages as
  `DOCS_PAGES`, and holds each to the page contract (`_contract_breaches`).
  `switching/index.md` is a stub, and the front page's "Coming from another code" card links
  it.

## Non-goals

- The foreign-name map and roadmap themselves (WP-1981).
- Readers for new formats.

## Tasks

- [ ] rietx at a glance: features × modes × data types, every cell linked to its Guides or
      Concepts page and its validation row.
- [ ] Coming from TOPAS, from GSAS-II and from FullProf: differences in concepts, then paired
      snippets (an `.inp` line or a GSAS-II setting beside the rietx call), linking the
      foreign-name map.
- [ ] Validation: what was compared with what, under which protocol, and the result, drawn
      from `docs/VALIDATION.md` without its diary.
- [ ] The roadmap page placed here, from WP-1981.
- [ ] Skill: none.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py -n auto --dist loadgroup
```

## Handover log

- **2026-10-16** — filed from WP-1975's slate. No open WP owns a comparison with other codes.
