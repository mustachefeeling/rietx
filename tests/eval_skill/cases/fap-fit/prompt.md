---
description: >-
  Deciding case. A refinement from scratch, WP-1904's pilot `fap-fit` carried
  over: FAP.XRA and fluorapatite.cif only, the cell graded by regex on
  report.md, the fit by `tool_used`, the caveat by rubric. In the pilot the
  current body failed it on Sonnet, 0 of 2 with the skill (no report.md: one
  run timed out at 1 500 s under two-way concurrency, one stopped at 1 347 s
  without writing it) against 2 of 2 without; on Haiku 1 of 1 with, 0 of 1
  without. The cell windows are an envelope, measured 2026-10-04 on rietx
  1.7.0.dev0 ([dev] venv, linux): from-scratch fits on the Cu Kα preset run
  from a = 9.370962(82), c = 6.885326(79) (zero refined, no axial term) to
  a = 9.373355(75), c = 6.887045(73) (displacement and axial refined), with
  GSAS's converged cell from FAP.EXP, 9.371724(36) and 6.885867(37), between
  them. Each window is that span plus one esd each side, so a fit refining
  zero and displacement together (`lab_bragg_brentano`: 9.369043(992),
  FLAT_DIRECTION) fails. That is narrower than the pilot's 9\.37[0-3] and
  6\.88[5-7]. The graders also ask for value(esd) notation, because the CIF's
  starting cell (9.3717, 6.8859) lies inside any window that holds GSAS's.
  The pilot's Haiku with-arm run passed both cell graders on the starting
  values while its refined a was 9.367913. timeout_seconds and max_turns are
  set from the pilot (1 500 s timed out two of four cells under contention,
  and one run used 29 turns), to be re-measured in the first round at -j 1.
tags: [fit, fap]
runs: 3
max_turns: 60
timeout_seconds: 2400
allowed_tools: [Read, Grep, Glob, Skill, Bash, Write]
---
FAP.XRA is a lab powder pattern of fluorapatite, Ca5(PO4)3F, collected on a Bragg-Brentano diffractometer with Cu Kα radiation (doublet, no monochromator). fluorapatite.cif is the starting model. Refine the structure against the pattern with rietx and write me a short report.md: the refined cell parameters a and c with their esds in value(esd) notation, as in 1.2345(6) Å, and a list of which refined numbers you would not yet put in a paper and why.

rietx is installed for the python interpreter @PYTHON@. Your working directory holds FAP.XRA and fluorapatite.cif.
