---
name: fap-fit
runs: 1
max_turns: 40
timeout_seconds: 1500
allowed_tools: [Read, Grep, Glob, Skill, Bash, Write]
---
FAP.XRA is a lab powder pattern of fluorapatite, Ca5(PO4)3F, collected on a Bragg-Brentano diffractometer with Cu Kα radiation (doublet, no monochromator). fluorapatite.cif is the starting model. Refine the structure against the pattern with rietx and write me a short report.md: the refined cell parameters with esds, and a list of which refined numbers you would not yet put in a paper and why.

rietx is installed for the python interpreter /home/user/rietx/.venv/bin/python. Your working directory holds FAP.XRA and fluorapatite.cif.
