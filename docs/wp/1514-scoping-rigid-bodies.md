# WP-1514 — Scoping rigid bodies: the milestone that makes the parameter map nonlinear

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (1319 soft, the fragment file; 1515 and 1516 soft, the sibling scopings it is placed against)
Priority: P2 2026-09-28 — a scoping WP: the structure-solution milestone 1515 scopes waits on the decision this one takes

## Goal

A queued milestone draft for rigid bodies and Z-matrices (#195): WP files,
a ROADMAP section, and a DESIGN.md entry if a locked decision moves. The
draft answers one question before any other: where the nonlinear map from a
body's parameters to its atoms' coordinates lives, and how coordinate esds
come back out of it. It is sized, ordered, and placed against v1.6, v1.7
and the two sibling scopings (1515, 1516). This WP builds nothing.

## Context

**Unfenced 2026-09-28.** "Z-matrices and rigid bodies (#195)" sat in
ROADMAP § v2+. The grounds for moving it are in DESIGN.md § Locked
decisions, *Structure fence revised*. The same day this WP was re-scoped
from an implementation WP to a scoping one, because the measurement below
put the work at milestone size.

**Why it is milestone-sized** (measured on `c1bd21dd`).

- **It breaks a stated design property.** The parameter table is "an
  affine constraint block **p_phys = C·p_free + d** (sparse C, rebuilt at
  every stage boundary, constant during a least-squares run — a constant
  matmul stays exact under the future autodiff backends)"
  (`src/rietx/params/vector.py:8`). A rotation cannot be written as a
  constant C.
- **Many readers depend on C's fixed structure.** `moving_paths` has 36
  references in 6 files, `column_reach` 14 in 3, `unmeasured_rows` 9 in 7,
  and `rebase_anchored_dofs` 7 in 2. `stderr_physical` computes
  σ² = diag(C·Cov·Cᵀ). `decode` has 52 call sites in 18 files. The traced
  twin (`backend/traced.py`) rebuilds the same map for jax and torch.
- **The one precedent does not transfer.** v1.6's magnetic moment is the
  only non-affine parameterisation in the package (`vector.py:1203`). Its
  DOFs are a modulus and angles. The components are locked entries,
  refreshed at commit, and "a component has no `C` row, so it has no esd".
  That was right for a direction a powder cannot determine. A rigid body's
  atom coordinates carry esds that bond lengths, the geometry propagation
  in `model/geometry.py`, and the CIF all need.
- **The work reaches past the core.** Restraint partials
  (`model/restraints.py`, whose second consumer is the geometry esds), the
  analytic Jacobian's declared reach (`_column_extras`), the cross-backend
  rows, riding hydrogens, the CIF writer, the GUI's structure table and 3D
  viewer, history serialization, `help.py` and manual Part 2.
- **For scale:** v1.6, the magnetic structure, is 7 WPs over one non-affine
  parameterisation.

**What the source run needed.** `solution case 1` (private corpus map § 5;
WP-1510 has the source) has two metal sites and two rigid aromatic ligands
in the asymmetric unit.
- At about 2.4 effective observations per parameter, free atoms let the
  rings buckle to chase intensity.
- The agent built an 18-DOF body outside rietx: per ligand an anchor atom,
  an axis and a twist, as a Rodrigues rotation of an ideal template. It
  pushed coordinates in through `set_values`.
- The Rietveld handoff held ring shape with `BondRestraint` on the 1-2, 1-3
  and 1-4 distances at `restraint_weight_scale=100`.
- Two disorder copies of each ligand were tethered by a penalty in a raw
  scipy loop, because rietx's restraints (`Bond`, `Angle` and `Value`,
  `schemas/structure.py:623-676`) are all equalities.
- Hydrogens were placed by hand for the CIFs.

**Rigid bodies are useful without a solver.** Any molecular crystal or MOF
refinement wants them. So the first rung stands alone, and 1515's milestone
builds on it.

### Inherited

- **2026-09-30, from the issue triage (issue #561): the reporter's scoping
  proposal for this WP.** Thirteen independent chunks R0-R12 off `main`, each
  with a test that can fail; R0 (rotation mathematics) and R1 (`Fragment`)
  touch no v1.6 file. The design's one load-bearing move is a typed
  `derived: list[DerivedBlock]` beside the affine block in
  `params/vector.py`, with `decode`, `local_jacobian` and `reach_pattern()`
  surfaces, so body-atom coordinates get esds (TOPAS's rule, Coelho 2015
  § 10.22.8) while the moment keeps its "no C row, no esd" rule. Prior art is
  clean-room (manuals and papers; FOX is GPL, concepts only). Two public
  cases: acridine form IX (COD 2242872) and diacetylene at 5 K (COD 1577467).
  *Checked at `e3e6486a`*: the `vector.py` lines it quotes (`:8-10`, `:1132`,
  `:1218-1223`) are on `4de25284` and were not re-measured; a cost-only
  proposal, no code. Seven questions are open and are the maintainer's: where
  the map lives, orientation convention, the moment migrating later, the
  anti-bump pair list, whether R0/R1 may start before v1.6 closes, chunk
  numbering (the next unused number is 1527 here, and 1527 is now taken by
  the species WP, so 1528), and the skill file. Decision pending (batch item,
  2026-09-30). Its companion is #562, under WP-1515.

## What the scoping decides

1. **Where the map lives.** (a) A C that depends on θ, rebuilt from the
   body map's local Jacobian at each evaluation. Every reader of C is kept,
   and "constant during a run" is broken. (b) A nonlinear stage in the
   forward model after C, as the moment does, with coordinate esds
   propagated through the body map's own Jacobian. (c) Whatever the prior
   art does that neither of these is. Measure each against the readers
   above.
2. **The parameterisation.** Quaternion or Euler angles, the body's origin,
   torsions as a Z-matrix or as named rotatable bonds, and a body sitting on
   a special position.
3. **The restraints the milestone needs.** A tether (a maximum distance,
   so an inequality), and planarity for a ring that is not rigid.
4. **Hydrogens** riding on a body, written to the CIF.
5. **Where a fragment comes from.** An ideal template, a CIF fragment, or
   WP-1319's molecular XYZ. SMILES comes later, behind an optional
   dependency.
6. **The public acceptance corpus.** Molecular and MOF structures with
   public powder data and published models.
7. **Placement.** Before, beside or after v1.7, and its relation to 1515's
   milestone.

## Non-goals

- Building any of it. A throwaway spike to measure (1) is allowed, and
  nothing from it merges.
- Global search (1515).

## Tasks

- [ ] Prior art with licences, searching the maintainer-local paper corpus
      first (root CLAUDE.md § Roadmap; its location is in the
      maintainer's memory).
- [ ] Measure the placements in (1) against the readers of C: what each
      changes, and what it does to esd propagation.
- [ ] The public acceptance corpus, with provenance for
      `tests/data/README.md`.
- [ ] The smallest first rung that is useful alone.
- [ ] The milestone draft: WP files, a ROADMAP section with the rows'
      order, and a DESIGN.md entry if a locked decision moves. **Open the
      milestone's WPs in the next unused number block, checked against
      `origin/main` and the open PRs on the day you file.** A sibling
      scoping may be filing at the same time.
- [ ] The maintainer's decision recorded here. This WP closes on it.

## Acceptance

The draft's WP files exist and are self-contained, ROADMAP carries the
queued section, and the index is regenerated. The maintainer's decision on
where the map lives is recorded in this file.

```sh
python3 .claude/hooks/wp_index.py
.venv/bin/python -m pytest tests/test_docs_consistency.py -n auto --dist loadgroup
```

## References

- Coelho, A. A. (2000). *J. Appl. Cryst.* 33, 899–908. Rigid bodies and
  Z-matrices in whole-profile simulated annealing (TOPAS; papers only).
- Coelho, A. A. (2018). *J. Appl. Cryst.* 51, 210–218. TOPAS's
  computer-algebra layer, cited in the `ExtraComponent` contract. Verify the
  pages before quoting them.
- Favre-Nicolin, V. & Černý, R. (2002). *J. Appl. Cryst.* 35, 734–743. FOX
  (licence unverified; papers only until checked).
- Toby, B. H. & Von Dreele, R. B. (2013). *J. Appl. Cryst.* 46, 544–549.
  GSAS-II (BSD-style; verify its LICENSE before reading code).
- David, W. I. F. et al. (2006). *J. Appl. Cryst.* 39, 910–915. DASH
  (commercial; papers only).

## Handover log

- **2026-09-28** — created as an implementation WP and re-scoped the same
  day into this scoping WP, after the measurement in Context put it at
  milestone size. Nothing started.
