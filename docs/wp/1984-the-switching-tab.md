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

**State on arrival (2026-10-17).** The new tree is `docs/docs/` (WP-1978). `tests/test_manual.py`
holds each page to the page contract, and `tests/test_manual_api.py` runs every python block
that can run and resolves every dotted name in the new tree too, so a block that needs a fit
carries a `<!-- api-doc: no-exec — reason -->` line. Vale reads every page in CI's lint job
(`vale sync && vale docs/docs`, from the repo root), and an error-level alert fails it. The
foreign-name map `reference/foreign-names.md` (WP-1981) is linked, never restated. The GSAS-II
`.gpx` and TOPAS readers build a `Structure` only, so the instrument names in the map come from
`.instprm` and from rietx's writers. The scope answer the Concepts tab lacked (neutron, time of
flight, joint fits) is in at-a-glance § Data rietx fits, linked from `concepts/fit.md`.

## Non-goals

- The foreign-name map and roadmap themselves (WP-1981).
- Readers for new formats.

## Tasks

- [x] rietx at a glance: features × modes × data types, every cell linked to its Guides or
      Concepts page and its validation row. (Guides has only an index until WP-1986, so the
      "Read more" column links Concepts and Reference pages.)
- [x] Coming from TOPAS, from GSAS-II and from FullProf: differences in concepts, then paired
      snippets (an `.inp` line or a GSAS-II setting beside the rietx call), linking the
      foreign-name map. (Every figure a page quotes is asserted by `examples/switching.py`.)
- [x] Validation: what was compared with what, under which protocol, and the result, drawn
      from `docs/VALIDATION.md` without its diary.
- [x] The roadmap page placed here, from WP-1981. (`git mv` from `reference/`.)
- [x] Skill: none.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py -n auto --dist loadgroup
```

## Handover log

- **2026-10-16** — filed from WP-1975's slate. No open WP owns a comparison with other codes.
