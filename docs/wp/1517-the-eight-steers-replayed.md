# WP-1517 — The eight steers, replayed: does the package raise what the person caught?

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (reads 1323, 1510-1516 as each lands)
Priority: P3 2026-09-28 — a measurement, not a fix; it becomes the acceptance other WPs in this track quote

## Goal

A repeatable measure of the track's aim: data and metadata in, a structure
out, with no person at the plot. Replay `solution case 1` with an agent
driving rietx from the person's first two messages and the same metadata.
Count which of the eight interventions the person made are raised without
the person, by the package or by the agent reading its output. Run once at
baseline, then after each WP of this track lands.

## Context

**Source.** `solution case 1` (private corpus map § 5), described in
WP-1510. Over two days the person sent 32 messages. Eight of them caught
something no diagnostic had raised:

| # | What the person caught | Where a fix lives |
|---|---|---|
| 1 | The background was flat. A Le Bail fit had absorbed a diffuse hump, and two hours of annealing ran against it. | 1323's fold |
| 2 | A metal-heteroatom bond class they believed absent, which became the chemistry prior | 1515 (priors as data) |
| 3 | A ring that was not flat | 1514 |
| 4 | Disorder of the ligand as well as the metal | 1514 (copies), 1515 |
| 5 | Whether a supercell explains it without disorder | 1511 (doublings) |
| 6 | A strong low-angle reflection left out of every structure fit | none yet |
| 7 | Stacking faults, the phase being layered | 1516 |
| 8 | A ring clash in an ordered configuration | 1513 |

Row 6 has no WP. `LOW_ANGLE_UNMODELLED` suggested a lower limit that kept
the reflection. The agent chose a higher one itself, and nothing reported
that a strong line was now outside the window. Decide at the baseline round
whether that deserves a diagnostic.

**Method rules from earlier rounds** (maintainer memory):
- Usefulness to an agent is measured with real agents, with model and
  effort as variables. A deterministic proxy does not count.
- A registered round is not authorisation to run it. Each round is offered
  with a cost, and only the cells the maintainer picks run.
- The data are unpublished, so the harness and transcripts stay with the
  data. This file records counts and the rubric only.

The precedents are WP-1053, 1307 and 1504.

**Scoring.** A steer counts as raised when the package emits a diagnostic
naming it, or the agent acts on it unprompted and says why. Each row needs
a written rubric before the baseline, so a later round cannot redefine
success.

## Non-goals

- Any fix. Each lives in the WP the table names.
- A public fixture of this pattern (WP-1450's rule).

## Tasks

- [ ] The rubric per row, written here before any round runs.
- [ ] The replay harness, kept beside the data: the person's first two
      messages, the metadata, the pattern, a clean tree, the skill as
      shipped.
- [ ] Baseline round (after the maintainer picks the cells), with counts
      recorded here.
- [ ] A decision on row 6.
- [ ] A round after each WP of this track lands, with its count.

## Acceptance

This file holds an 8 × rounds table of raised or not raised, each round
dated with its source commit, model and effort. The count at baseline is
recorded before any fix is credited with moving it.

## References

- WP-1053, 1307 and 1504, the agent-evaluation precedents.

## Handover log

- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1510 to 1516. Nothing started.
