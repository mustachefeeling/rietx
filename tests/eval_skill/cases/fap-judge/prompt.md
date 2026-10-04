---
description: >-
  Regression guard. The skill-placement round's episode (WP-1338): a colleague's
  fluorapatite fit and its printed output, four rubric items on what may be
  quoted. WP-1904's pilot: 4 of 4 with the skill and 3 of 4 without on Haiku, a
  ceiling (4 of 4 in every arm) on Sonnet.
tags: [judge, fap]
runs: 3
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Grep, Glob, Skill, Bash]
---
My colleague refined our fluorapatite pattern with `fit.py` and sent me what it printed, `fit_output.txt`. Which of the refined numbers can go in the paper as they stand, and what should they change before the next run?

rietx is installed for the python interpreter @PYTHON@. Your working directory holds fit.py, fit_output.txt, FAP.XRA and fluorapatite.cif.
