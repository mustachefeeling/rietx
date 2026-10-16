# WP-1993 — N-W3: satellites at a real q, to order m, with (h k l m) rows

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (N-W1 landed as PR #682; 1992 soft, the same package)
Priority: P3 2026-10-16 — library code with a contributor ready to build it; the k-search (#795, WP-1418) and both future forward models read it

## Goal

`crystallography/satellites.py` generates satellite reflections at a real
(irrational) modulation vector q, to a stated harmonic order m, as
(h k l m) rows with their absences derived from the superspace operators.
Every existing rational-q fixture stays bit-identical at m = ±1.

## Context

Issue #678 (mustachefeeling, 2026-10-02), chunk N-W3. A satellite is a
reflection at H + m·q, where H is a reciprocal-lattice vector of the
average cell and m an integer harmonic.

Decided on #678, 2026-10-08: N-W3 opens after TOF T-1 merges, which it did
on 2026-10-13 (PRs #911, #961). Cut 2026-10-16 from the issue triage, with
WP-1992 (N-W2's group half). Modulated structures stay behind ROADMAP § v2+
apart from these two library chunks.

#678's acceptance for N-W3: every 1326 fixture bit-identical at m = ±1; de
Wolff's (c/s), (6₃/h) and W^{P4bm}_{qq1̄} conditions derived from the
operators; the 1326 negative control still fails.

**Decision owed at this WP's start: amendment A2** (#678, comment of
2026-10-06). It splits N-W3 in two:

- N-W3a (S): `satellite_positions(space_group, cell, λ, range, q,
  harmonics)`, the distinct positions at a real q. The k-search and both
  forward models read this one call.
- N-W3b (M): the (h k l m) rows, the dedup under the (3+1)D point group,
  the labelled absences and the commensurate coincidence merge.

The 2026-10-08 reply deferred all six amendments to the cut. A2 is the one
that changes this WP's shape. The others belong to later chunks (see
Non-goals).

Checked at `138d55dc`: `crystallography/satellites.py` exists and serves the
commensurate magnetic track (WP-1326); N-W1's operators are in
`crystallography/superspace/`.

### Inherited

## Non-goals

- The structure factor at a satellite (N-W5, N-W6) and satellite widths (N-W8).
- Amendments A1 (WP-1418), A3 (N-W4), A4 (N-W5), A5 (N-W10) and A6 (N-W8).

## Tasks

- [ ] Decide A2 with the maintainer and record it here as `Decided YYYY-MM-DD`.
- [ ] Satellite positions at a real q (N-W3a, or the whole chunk if A2 is declined).
- [ ] The (h k l m) rows, dedup, absences and coincidence merge.
- [ ] Tests: the 1326 fixtures bit-identical at m = ±1; the three de Wolff conditions; the negative control
- [ ] Skill: none expected while the package stays unexported; say why at handover

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -k "satellite or superspace" -q
.venv/bin/python -m ruff check src tests examples
```

## References

- de Wolff, Janssen & Janner (1981), *Acta Cryst.* A37, 625.
- Stokes, Campbell & van Smaalen (2011), *Acta Cryst.* A67, 45.
- Issues #678, #258, #795.

## Handover log

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #678).
  The maintainer decided to cut N-W2's group half and N-W3 now that T-1 has
  merged. Checked against the tree at `138d55dc`: `satellites.py` exists for
  the commensurate track. No open WP owns it: WP-1326 owns commensurate
  satellites. Next: the A2 decision.
