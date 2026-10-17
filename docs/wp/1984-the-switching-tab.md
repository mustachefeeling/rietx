# WP-1984 — The Switching tab

Milestone: unscheduled · Status: ✅ 2026-10-17 — the Switching tab: at a glance, TOPAS, GSAS-II and FullProf pages, validation, roadmap
Track: The repo's own process
Depends on: 1978 (the new tree); 1981 soft (the foreign-name map and the roadmap it links)

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

- **2026-10-17** — A person who uses TOPAS, GSAS-II or FullProf can now judge rietx from one
  tab. It says which data rietx fits (X-ray, constant-wavelength neutron, joint fits, and no
  time-of-flight refinement), what each feature was checked against, how each of the three
  programs maps onto a rietx refinement, and which comparisons exist with what agreement. The
  validation page is honest in both directions. rietx's cell agrees with TOPAS to 16 ppm on
  cBN and sits 98 ppm from TOPAS where TOPAS and GSAS-II differ by 2668 ppm, and its Rwp on
  LaB6 with cBN is twice TOPAS's, because rietx has no Pearson VII peak. Nothing compares
  rietx's refined numbers with FullProf's, and the FullProf page says so.
  - **Done.** Five pages and an index in `docs/docs/switching/` (`at-a-glance`, `topas`,
    `gsas2`, `fullprof`, `validation`; `roadmap` moved in from `reference/` with `git mv`),
    a link from `concepts/fit.md` § Inputs to at-a-glance § Data rietx fits (the inherited
    item from 1983), and `examples/switching.py` with its test in `tests/test_examples.py`.
    The script runs the fluorapatite refinement once and asserts every figure the three code
    pages quote from a file rietx wrote or read: the four-stage plan's freed counts, the
    TOPAS file's tie and hold lines, the `.instprm` conversion, `FAP.EXP`'s 28 variables and
    the free set the `.pcr` codewords map back to, and the text of the two diagnostics the
    pages quote. Vale terms added: `Rp`, `Gaultois`.
  - **Measured.** `[dev]` venv (no jax or torch), darwin/arm64, no other pytest tree seen
    running. Fast selection `-m "not slow"`: 10 729 passed, 191 skipped, 2 xfailed, 1 failed
    in 3:56 (one run). The failure was `test_portability` catching `read_text()` without an
    encoding in the new example, which a docs-only run of the manual tests had not covered;
    fixed, and `test_portability` plus the example test pass alone. One test added, so
    passed+skipped should be one over main's. Main's own count was not measured (§ Running's
    rule), so the +1 is not checked against a baseline. The added test took 13.6 s in that
    loaded run and 7.3 s alone, two fits and four file round trips. It is not marked `slow`
    for the reason `test_examples.py`'s docstring gives: per-push execution is the value, and
    the other example tests cost the same order. Full selection not run: the WP moved no
    measured number.
  - **Review.** `/code-review high --fix` found six. Fixed: `test_reference_pages` scanned
    only `reference/` for the roadmap's include and went red on the move (the scan now covers
    the tree); a sentence saying 28 minus 20 is the 12 coordinates (it is 8); a listing
    called "the first lines" of an `.instprm` that skipped its comment line and the lines
    after `Y`. Reworded: the TOPAS excerpt introduced as free parameters but showing a held
    `th2_offset ! 0`. No action: two uncommitted files that were this session's own. And my
    `### Inherited` note on WP-1985, which is closed, tripped
    `test_inherited_is_h3_and_closed_wps_have_consumed_theirs`; it is removed, and the example
    asserts the two quoted messages instead, so a rewrite goes red there.
  - **Gotchas.** (1) `tests/test_manual_api.py` runs every python block in the new tree in a
    fresh namespace and resolves every dotted name in a code span, so a block that needs a fit
    carries `<!-- api-doc: no-exec — reason -->`, and `Instrument.source.lines` fails where
    `instrument.source.lines.*` passes. (2) Vale runs from the repo root with the styles
    synced (`vale sync`), and a subshell is the only way here, since a bare `cd` is refused.
    (3) A heading with markup in it (`LaB<sub>6</sub>`) gives a slug nobody can link, so the
    validation headings are plain text. (4) VALIDATION.md's FAP row says the plan frees 20
    and GSAS 28 and that "the whole difference is the 12 coordinate DOFs". That does not add
    (20 + 12 = 32), and the page states what does (the plan leaves the 12 out and frees four
    the file does not). The file is generated from
    `tests/validation_matrix.py`, and the row is left as found. (5) Not done: the pages were not opened in
    a browser, the GSAS-II recipe on `gsas2.md` is not run (its keys are read from the 5.8.4
    source), and the "four more" is arithmetic, not a listing.
  - **Next.** WP-1986 first: it moves Guides, so the feature table's "Read more" column can
    point at the guide for each task (its `### Inherited` has the note). Then WP-1980 gives
    every page, these included, a markdown twin. A check of the three code pages by a user of
    each program would settle what this session could not: whether the paired examples are the
    ones they would reach for.
- **2026-10-16** — filed from WP-1975's slate. No open WP owns a comparison with other codes.
