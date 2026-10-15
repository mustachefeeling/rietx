# WP-1984 — The Switching tab

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1978 (the new tree); 1981 soft (the foreign-name map and the roadmap it links)
Priority: P3 2026-10-16 — down a rung from P2: nothing can start until 1978's tree exists

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
