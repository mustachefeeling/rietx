---
name: fap-judge
runs: 1
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Grep, Glob, Skill, Bash]
---
My colleague refined our fluorapatite pattern with `fit.py` and sent me what it printed, `fit_output.txt`. Which of the refined numbers can go in the paper as they stand, and what should they change before the next run?

rietx is installed for the python interpreter /home/user/rietx/.venv/bin/python. Your working directory holds fit.py, fit_output.txt, FAP.XRA and fluorapatite.cif.
