# WP-1803 — the body seam: a derived block, or a linearisation inside C

Milestone: v1.8 · Status: 🔄 2026-10-01 — claimed by @mustachefeeling
Depends on: 1801
Priority: P2 2026-09-30 — the decision every later rigid-body WP waits on; it carries the six open questions of the 2026-09-30 review

## Goal

A measured decision, recorded in `docs/DESIGN.md` § Parameter system, on how a
body's atom coordinates enter the parameter table with esds. Nothing from the
spike merges except that record.

## Context

The table is one affine block, `p_phys = C·p_free + d`, constant during a
least-squares run (`params/vector.py:8-10`). A body atom's coordinates are not
affine in the rotation vector. Issue #561 proposes a typed `derived` block
beside the affine one. The adversarial review found a **cheaper alternative
worth measuring first: linearise the body per stage inside C**,
x = x₀ + M⁻¹·[−R₀rᵢ]×·δω + o, re-exponentiate at commit in the slot
`_refresh_moment_components` holds (`vector.py:1292`). C stays constant, every
reader and the traced twin stay unchanged, and esds are exact at the anchor. The
price is an O(|δω|²) non-rigidity inside a stage: about 0.13 % bond stretch
(≈ 0.002 Å) for a 3° step, and a closing zero-increment pass for exact esds.

**Measure**, on a synthetic body: the stretch against step size, the esd
difference from the exact chain rule (J·Cov·Jᵀ by finite differences of
`decode`, never a hand formula sharing code with the map), and the iteration
count.

**Six questions to settle in the record** (each from the review):

1. The seam: derived block or linearised C. Question 1 of #561, now with a number.
2. The Cartesian frame contract: a closed-form `xp` matrix pinned against
   `cartesian_basis`, since `cartesian_basis` uses `np.linalg.cholesky` and the
   traced twin cannot. The magnetic twin declines for this reason
   (`backend/traced.py:125-137`).
3. Whether the cell is a live input to the map or frozen per stage. Live makes
   every cell column reach every body atom, moves body coordinates in a cell-only
   stage and in Le Bail (where `.atoms.` is force-fixed), and cannot honour a hold.
4. The semantics of an anchored rotation. Equal increments are not equal
   orientations, so `rebase_anchored_dofs`, `displace_anchored_dofs`
   (`vector.py:1707-1800`) and the series carry (WP-1333) need a rule, not a
   subtraction.
5. Which ties onto a body DOF or a derived row are refused. Today a tie whose
   source is a derived row flattens to `d` and returns a short column with no
   error; `apply_value_scale` refuses the analogous case (`vector.py:2310-2324`).
6. Anti-bump pairs are frozen per plan, since a per-stage rebuild moves the
   restraint row count that WP-1074's rule fixes mid-plan.

Also measured or confirmed here: `_structural_column` never matches a body
column (`_STRUCTURAL_PATH` accepts only `atoms.N.(dof|adp).N`), so body DOFs
take the exact `_peak_chain_column` path and no Jacobian branch is needed.

**Sequencing, decided 2026-09-30:** v1.6 ships whole, so the table change this
spike licenses is cut as a WP but does not start until v1.6 closes. The spike
itself edits no repo file but DESIGN.md and may run now.

## Non-goals

- Shipping any table change. That is the WP this record licenses.
- Torsions, restraints, special positions.

## Tasks

- [x] Spike script in the scratchpad: the linearised body, the exact chain, the stretch and esd numbers
- [x] The six answers, in DESIGN.md § Parameter system, with the measured figures
- [ ] Re-cut the remaining chunks (R2b onward) as WPs from the record; R3 is sized L, with the anchored-rotation kind, tie refusals, `help.py`, `gui/src/lib/history.ts` PLACES and the `ParameterRow` field pin
- [x] Skill: none

## Acceptance

The DESIGN.md clause exists and quotes the numbers. `tests/test_docs_consistency.py` passes.

## References

- Coelho (2015), *TOPAS-Academic V6 Technical Reference*, § 10.22.8: body-atom esds propagate from the body parameters.
- Issue #561; WP-1514; the 2026-09-30 review in WP-1514's `### Inherited`.

## Handover log

- **2026-09-30** — created, from the 2026-09-30 issue triage (issue #561). No
  open WP owns it. The review's stale line references (`vector.py:1218-1223` is
  now `:1259-1260`, `:1132-1136` is `:1175-1178`, `:1252` is `:1292`) were
  re-found at `e3e6486a` and are the ones quoted here.
- **2026-10-01** — claimed by @mustachefeeling. Spike run on a synthetic C₆Br
  body in a triclinic P‑1 cell (two seeds, numpy backend, Mac) against
  `beb48147`; the record is the DESIGN.md § Parameter system clause "Rigid
  bodies", with the conditions under it. Decision: the typed `derived` block.
  The linearised route reaches the same body (≤ 4e‑8 Å) but only by repeating
  the stage 4–5 times (16–21 TRF iterations against 6–8 for one solve with the
  map in `decode`), and its esds are exact only on the closing pass. Positive
  arms: a planted cross‑product sign is caught by the commit‑time consistency
  check (0.29–0.33 Å against 0.004 Å) and not by a bond check; a stale anchor
  is caught only by the bond check (1.9–2.3e‑3 Å against ≤ 1.1e‑15 Å).
  Re‑run once on a fresh tree at `beb48147`: every non‑timing number
  bit‑identical. Not done here: the re‑cut of R2b onward (proposed in the PR
  body as text for the maintainer; R5 is not cut); answer 6 is a judgement,
  not a measurement.
