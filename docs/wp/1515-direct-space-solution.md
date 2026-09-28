# WP-1515 — Direct-space solution: from a verified cell to ranked structures

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: 1514 (rigid bodies); 1513 soft (the census its clash term reads); 1511 soft (the verified cell it starts from)
Priority: P3 2026-09-28 — rated one rung down for its hard dependency on 1514; the agent's own engine is the workaround until then

## Goal

A provisional `rietx.solve`, shaped like `rietx.indexing`. It takes a
verified cell, a space-group shortlist, the contents with their fragments,
and the person's chemistry priors. It returns distinct candidate structures,
ranked, with the evidence behind each, and agreement across independent
seeds comes first. It streams progress on the event ladder so `rietx watch`
shows the current leader, and hands the winner to a Rietveld plan with its
bodies intact. It never returns a confident singleton.

## Context

**Unfenced 2026-09-28.** "Structure solution from an indexed cell" sat in
ROADMAP § v2+ beside charge flipping (#198), which stays there. The grounds
are in DESIGN.md § Locked decisions, *Structure fence revised*.

**Source.** `solution case 1` (private corpus map § 5), described in
WP-1510. What the agent built, and what it measured:

- **Engine.** Parallel tempering (Earl & Deem 2005): six replicas,
  temperatures geometric from 3 to 300 in χ² units, neighbour swaps every
  50 steps, with block, global and reset moves. One compiled `Refinement`
  held for the whole run, `predict()` per evaluation, and its own analytic
  scale. **20-35 ms an evaluation.** An earlier multistart that called
  `fit()` per trial ran 10-20 s a trial.
- **Cost.** χ², plus a clash penalty, plus a soft coordination prior. The
  prior said what the person knew: how many ligand atoms each metal binds,
  how many metals each bridging atom binds, and no reward for a
  metal-heteroatom bond the person had ruled out.
- **The prior was necessary.** Annealing on the profile alone reached a
  low χ² with chemically absurd coordination.
- **Seeds were the evidence.** Four independent runs from random starts
  converged on one chemistry class, their Rwp within 2 % of each other.
  Transplanting the analogue structure's coordinates did worse than a blind
  start.
- **Wall clock.** Each batch ran 30-80 min. Six Monitor watches on these
  runs expired with no events, and the person had to ask "plot the leader?".
- **Every stage after the solution was a hypothesis test, by hand:** split
  sites, occupancy scans, all partitions of the disorder copies into two
  configurations, and a two-phase alternative scored by ΔBIC. WP-1517 lists
  which of them the person prompted.

**Why the agent did not use FOX or GSAS-II.** At the start it proposed
GSAS-II, and the person approved installing it. Its notes from an earlier
session recorded a pyobjcryst pipeline whose results were untrustworthy: a
stale cached cost, a clash term the least-squares step ignored, and texture
nobody verified. It then built on rietx's `predict()` and never mentioned
GSAS-II again. So an agent that has a fast evaluate path in the package it
is already driving stays in that package. The host for this should be
rietx.

**The cost function is the first design choice.** The run used the full
profile χ² through `predict()`. DASH instead fits correlated integrated
intensities from a Pawley extraction (David et al. 2006), which is far
cheaper per evaluation. rietx has Pawley mode with overlap restraints
(`PAWLEY_OVERLAP_UNRESOLVED`). Measure both on one case before choosing.

**The anytime precedent is indexing's.** WP-1042 gave `index_pattern` a
bounded quick default with a whole-run ceiling, a streamed shortlist and a
`preset="full"` escape. The same shape fits here.

## Non-goals

- Charge flipping and difference Fourier maps (#198, #197), still fenced.
- Space-group determination beyond the extinction screen's ranked classes.
- A second engine before the first is measured.

## Tasks

- [ ] Design note in this file: the answer type, the cost (profile against
      extracted intensities, measured), the move set, the seed-agreement
      statistic, the events. Maintainer decision recorded.
- [ ] Source public powder data with published structures across metal,
      organic and metal-organic cases, with provenance in
      `tests/data/README.md`.
- [ ] The engine, the priors as declared data, the clash term on WP-1513's
      census.
- [ ] The handoff: a winner becomes a `Refinement` with bodies and a plan.
- [ ] Events on the ladder, and the leader drawn by `rietx watch`.
- [ ] Manual Part 1 and 2, the provisional-module entry, `help.py`.
- [ ] Skill: a `references/` shape file for solving a structure.

## Acceptance

Each public case solved from random starts to within a stated RMS
displacement of the published model, with the seeds agreeing. `solution
case 1` replayed privately reaches the chemistry class the session found
(counts and ratios only in the handover).

```sh
.venv/bin/python -m pytest tests/test_solve*.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Earl, D. J. & Deem, M. W. (2005). *Phys. Chem. Chem. Phys.* 7, 3910–3916.
  Parallel tempering.
- David, W. I. F., Shankland, K., van de Streek, J., Pidcock, E., Motherwell,
  W. D. S. & Cole, J. C. (2006). *J. Appl. Cryst.* 39, 910–915. DASH.
- Coelho, A. A. (2000). *J. Appl. Cryst.* 33, 899–908.
- Favre-Nicolin, V. & Černý, R. (2002). *J. Appl. Cryst.* 35, 734–743.

## Handover log

- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1510 to 1514, 1516 and 1517. Nothing started.
