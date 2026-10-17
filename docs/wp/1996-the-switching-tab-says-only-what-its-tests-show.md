# WP-1996 — The Switching tab says only what its tests show

Milestone: unscheduled · Status: 🔄 2026-10-17 — a review of WP-1984's pages, fixed in one session
Track: The repo's own process
Depends on: 1984 (the pages)
Priority: P2 2026-10-17 — wrong numbers on the page a switcher judges rietx by, nothing flags them

## Goal

Every figure on the Switching tab (`docs/docs/switching/`) agrees with the test that measures
it, and every quoted file line is asserted by `examples/switching.py`. The validation page also
gives the comparisons with a certificate or a weighed composition.

## Context

A review of WP-1984 (closed 2026-10-17, PR #1025) on 2026-10-17 found these. No open WP owns
them: 1986 moves Guides and Theory, 1980 makes markdown twins, and 1911 owns the foreign
writers' behaviour, which the FullProf finding below leaves unchanged.

- `at-a-glance.md` said magnetic structures had no comparison with another code, while
  `validation.md` lists a magnetic child phase among the TOPAS 6 calculated patterns
  (`tests/test_topas_p1_ties.py`, `topas_export_child_magnetic_ycalc.txt`).
- `validation.md` quoted v0.2's fluorapatite figures (9.73 %, +116 ppm) as the mirrored
  protocol's result, beside today's table (9.25 %, +83 ppm). The source,
  `validation_matrix.TIERS["cross_code"]`, and `DESIGN.md` state them in the present tense.
- The PowderLine engine gap appeared as 2665 and 2668 ppm. From the committed reference
  files the cubic a differs by 2668.2 ppm relative to GSAS-II's value and 2661.1 relative to
  TOPAS's; 2665 is the gap over their mean. The test computes 2668
  (`test_acceptance_powderline.py:177`), so 2668 is the figure everywhere.
- `validation.md` said every row runs in CI against real data and that `VALIDATION.md` holds
  them all. The texture and calculated-pattern rows compare calculated data and are not in the
  matrix. It also said every comparison checks the channel count; fluorapatite, LaB6 + cBN and
  silicon do.
- The fluorapatite "frees four that the file does not" was arithmetic. Measured: the plan
  frees `axial_sl`, which GSAS held, and a six-term Chebyshev against three terms of GSAS's
  function 5. The matrix row said the whole difference was the 12 coordinate DOFs.
- `at-a-glance.md` said other codes report only an Rwp and a table, which TOPAS and GSAS-II
  users know is false.
- The `.instprm` on `gsas2.md` was written from the TOPAS page's fit, which held the zero
  at 0, and sat below a plan that frees the zero. The held zero moves the cell 110 ppm.
- `examples/switching.py` claimed to assert every quoted figure and asserted about half.
- FullProf 8.20 (February 2025, `~/Code/rietx-bench/tools/fullprof/files/fp2k`) applies the
  Laue-class cell constraints itself. Run on the page's `flags.pcr` it prints `Cell constraints
  according to Laue symmetry: 6/m` and rewrites the codewords `41 0 51 0 0 0` as
  `41 41 51 0 0 41`. The manual (`Docs/FullProf_Manual.pdf`, Line 11-4) still says CF must
  equal CA and CB in the hexagonal system. So the writer is right, and the page's reason was
  wrong.

## Non-goals

- The foreign writers' behaviour (WP-1911).
- Guides links from the feature table (WP-1986).

## Tasks

- [x] `examples/switching.py` asserts every quoted line at six significant figures; the
      `.instprm` comes from the four-stage fit; the held zero's 110 ppm is asserted.
- [x] The three code pages quote what the script asserts; FullProf's cell constraints stated
      as measured.
- [x] `at-a-glance.md` and `validation.md` corrected; the certificate and round-robin rows added.
- [x] `validation_matrix.py` (tier text, 2668, the FAP free set), `VALIDATION.md` regenerated,
      the FAP row's free set asserted; `DESIGN.md`, `recipe.md`, root `CLAUDE.md` at 2668.
- [x] Skill: none. Nothing here changes how an agent drives rietx.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_examples.py tests/test_validation_matrix.py "tests/test_acceptance_fap.py::test_the_file_states_a_wider_free_set_than_this_plan" -n auto --dist loadgroup
vale docs/docs
```

## Handover log

- **2026-10-17** — filed from a review of WP-1984's pages.
