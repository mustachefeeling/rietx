---
description: >-
  Regression guard. Issue #661's mapping rows, on the other-program file this
  repository can publish: the agent is handed GSAS's converged refinement of
  FAP.XRA (FAP.EXP: 28 variables, Rwp 0.1005) and asked to reproduce it. No
  body has run it. #661's mapping table was written for a TOPAS .inp, and
  today's api.md already says to read the wavelengths and excluded regions
  off `model.stated`, so the first round decides whether this is a guard or a
  deciding case. Every window was measured 2026-10-04 on rietx 1.7.0.dev0
  ([dev] venv, linux); the cell and o7_z windows are an envelope of two
  references plus one rietx esd each side. Cell: GSAS's 9.371724(36),
  6.885867(37), and rietx under GSAS's
  protocol, 9.372794(75), 6.886635(72) (tests/test_acceptance_fap.py's plan
  plus GSAS's twelve coordinate DOFs) or 9.371721(78), 6.885891(80) with the
  axial term held at zero as GSAS's asym is. The cell fails the
  Zero_Error/Specimen_Displacement rows misread (both refined: a = 9.368403;
  zero in place of displacement, axial held: 9.370370) and the emission-line
  row with axial refined (the Hölzer preset: 9.373412). With axial held, the
  preset lands inside (9.372340), so `file_wavelengths` reads the script for
  the file's own lines. rwp, [0.085, 0.115), spans GSAS's 0.1005 and rietx's
  0.0900 (U, V, W refined) to 0.1103 (exclusion dropped, axial refined; 0.1203
  with axial held fails). It fails the
  background row misapplied (GSAS's 3 function-5 terms as a 3-term Chebyshev:
  0.179; the preset's 4: 0.132) and the width units (GU/GV/GW divided by 100,
  not 10⁴: 0.356; undivided, the box refuses U = 2). o7_z is the coordinate
  row: quote atoms.j.z, never dof.k, which stayed under 0.002 in every run.
  Its window spans GSAS's 0.070641 and rietx's 0.07043(69) to 0.07069(58).
  A copy of FAP.EXP's own numbers passes all four value graders; only
  `ran_fit` and `file_wavelengths` stand against it. max_turns is set from
  the pilot's fap-fit, and timeout_seconds from fap-fit's Amendment 1.1.
tags: [fit, fap, gsas, reproduce]
runs: 3
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Grep, Glob, Skill, Bash, Write]
---
FAP.EXP is GSAS's converged Rietveld refinement of FAP.XRA, a powder pattern of fluorapatite, Ca5(PO4)3F, from a lab Bragg-Brentano diffractometer with Cu Kα radiation. I want to know whether rietx agrees with GSAS on these data, so reproduce that refinement with rietx: the same model, with the same parameters refined. Save the script you ran as reproduce.py, and write rietx's refined values to answer.json as {"a": ..., "c": ..., "o7_z": ..., "rwp": ...}: a and c in Å, o7_z the fractional z coordinate of the site labelled O7, and rwp as a fraction, not a percentage.

rietx is installed for the python interpreter @PYTHON@. Your working directory holds FAP.XRA and FAP.EXP.
