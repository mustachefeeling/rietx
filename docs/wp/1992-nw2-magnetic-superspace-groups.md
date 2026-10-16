# WP-1992 — N-W2 (group half): magnetic superspace groups generated from the operators

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (N-W1 landed as PR #682; 1419 soft, the `representation/` package it extends)
Priority: P3 2026-10-16 — library code with a contributor ready to build it, but no user-visible result until N-W5 (the magnetic Fourier forward model) lands on it

## Goal

`crystallography/superspace/` generates the (3+1)D magnetic superspace group
(MSSG) for each irrep at a real propagation vector, and pins its counts and
sign patterns against published tables. This is the group half of chunk N-W2
in #678's cut; the allowed-subspace function and the forward model are later
chunks.

## Context

Issue #678 (mustachefeeling, 2026-10-02) cuts modulated structures (#258)
into ten chunks, N-W1 to N-W10. Background for a reader new to it: a
modulated structure has atoms displaced by a wave that does not repeat with
the cell, and its symmetry needs a superspace group with one extra
dimension for the wave's phase. A magnetic one adds time reversal (1′).

Decided on #678, 2026-10-08: N-W2's group half and N-W3 (WP-1993) open after
TOF T-1 merges; one WP per chunk, numbered when cut; N-W4 onward wait for
the magnetic forward seam. T-1 merged on 2026-10-13 (PRs #911 and #961,
WP-1927). Cut 2026-10-16 from the issue triage. Modulated structures are
still behind ROADMAP § v2+; this WP and WP-1993 are the library half that
the decision lets in.

The reporter's scope for the group half (their comment of 2026-10-06): θ on
the operator, {1′|000½}, generating the MSSG per irrep, with the P222/I222,
SrFeO₃ and Stokes & Campbell (2022) Fig. 4 pins. It changes neither
`schemas/structure.py` nor the forward model.

Checked at `138d55dc`:

- N-W1 is on `main`: `crystallography/superspace/` (`operators.py`,
  `generation.py`, `symbols.py`), unexported.
- The irreps code #678 calls `magnetic/irreps.py` now lives in
  `crystallography/representation/irreps.py` (moved by #842 and #889 under
  WP-1419). The "real-k door" is opened there.
- spgrep is a dependency (`spgrep>=0.7`).

First act, before the design is fixed (decided 2026-10-08): check that
spgrep's little group and small irreps hold at an irrational k. A rational k
must be reproduced at its float value, and a near-rational k must not snap.

#682's three follow-ups fold into this WP's PR: the `number` field,
function-level references, and the hand-typed 775/24 counts.

Licensing: papers only (#678 § Prior art). The ISO(3+d)D tables forbid
redistribution, so rietx ships a generator and pins published counts.

### Inherited

## Non-goals

- The allowed-subspace function (N-W2's second half), the schema (N-W4)
  and the forward model (N-W5).
- #678's amendments A3–A6, which belong to N-W4, N-W5, N-W8 and N-W10, and
  A1, which lands in WP-1418 (#795's k-search).

## Tasks

- [ ] The spgrep check at an irrational k, recorded here before any design.
- [ ] θ on `SuperspaceOperator` and {1′|000½}; MSSG generation per irrep through the real-k door.
- [ ] #682's three follow-ups.
- [ ] Tests: the P222/I222, SrFeO₃ and Stokes & Campbell (2022) Fig. 4 pins; the 9 303 d = 1 MSSG count as an opt-in slow test
- [ ] Skill: none expected while the package stays unexported; say why at handover

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -k superspace -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Stokes, Campbell & van Smaalen (2011), *Acta Cryst.* A67, 45.
- Perez-Mato, Ribeiro, Petříček & Aroyo (2012), *J. Phys.: Condens. Matter* 24, 163201.
- Stokes & Campbell (2022), as cited in #678 (journal details to confirm at the WP's start).
- Issues #678, #258, #682.

## Handover log

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #678).
  The maintainer decided to cut N-W2's group half and N-W3 now that T-1 has
  merged. Checked against the tree at `138d55dc`: N-W1 is on `main`, and the
  irreps code sits in `representation/irreps.py`. No open WP owns it: WP-1418
  and WP-1419 own the commensurate magnetic track. Next: the spgrep check.
