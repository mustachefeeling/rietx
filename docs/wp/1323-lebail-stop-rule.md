# WP-1323 — the Le Bail alternation has a stop rule, and a scope

Milestone: unscheduled · Status: ⬜
Depends on: —

## Goal

The package owns the Le Bail alternation: one call runs the
extract-intensities / refine-profile cycle to a fixed point under a pass cap,
keeps the best pass, and stops on a non-monotone Rwp, recording why it
stopped. The skill's §2 rule 4 sends an agent to that call instead of asking
for a hand loop with no cap, and says which job is *not* a Le Bail job at all:
calibrating an instrument on a standard whose structure is known is a staged
Rietveld pass, because the structure pins the intensities and there is nothing
to alternate.

## Context

From issue #210, filed 2026-09-01 by a contributor whose agent followed the
rule as written.

**The rule, verbatim** (`docs/skill/rietx/SKILL.md` §2 rule 4, restated in
`references/judging.md` §2 rules 4-5): *iterate the whole plan to a fixed
point; one `fit()` is not enough, and keep the best pass, not the last.* It
carries the measurement that motivates it (PbSO4: pass 1 stops at Rwp
20.756 % with an unphysical Caglioti V = +0.0615, passes 2-4 reach 10.247 %;
Tb2BaCoO5 gets *worse*, 17.3 % → 18.7 %) and no pass cap, no stop condition,
and no restriction on which parameters the alternation suits.

**Why it wanders.** The extracted per-hkl intensities are frozen inside each
least-squares run (the frozen-per-stage invariant), so intensities and profile
converge only by alternating — and the alternation is not a descent on one
objective. Where the profile subspace is nearly flat, each re-extraction moves
the valley floor *within* that subspace.

**Measured cost** (#210, a six-phase lab pattern at 0.05° steps): an
unconstrained Le Bail with five free cells and all four Caglioti terms took
**~40 of a ~100-minute session**; pass 2 came out worse than pass 1 (Rwp
0.1697 → 0.1703), `instrument.profile.x` ran to its upper bound, and
`HIGH_CORRELATION instrument.profile.v ~ w` (ρ = −0.999) fired and was iterated
past. The same calibration as one staged Rietveld pass, then held, took
**43.8 s**. The two softest Hessian directions were both profile degeneracies
(`profile.y` against a phase's `lor_strain` at eigenvalue 3.35e-5;
`profile.u` ↔ `profile.v` at 9.83e-4; next mode 1.4e-2), and `profile.x`
reached its bound *because* a Le Bail on a real specimen frees no
sample-broadening term, so every specimen Lorentzian width had nowhere to go
but the instrument's x/y.

**Where it lives.** The partition is `CompiledModel.lebail_update`; the
extracted intensities are serialised per history node (`ReflectionState`); the
plan runner `strategy/staged.py` is the one place a cycle can be a stage
boundary without breaking the frozen-per-stage invariant — so the alternation
is a *plan-level* loop, not a solver-level one. `RefinementPlan` already owns
the schedule (`intermediate_ftol`, WP-1123); a pass cap is the same kind of
field. The termination view (`str(result)`, WP-1302) is where the stop reason
must appear.

**Prior art, concepts only.** GSAS-II runs Le Bail extraction for a declared
number of cycles inside its refinement loop; TOPAS and FullProf refine
per-hkl intensities inside the least squares (Pawley-like), so they have no
alternation to diverge. The package's Pawley mode already has the second
shape (a θ block with equal-split restraints on overlapped groups); this WP
does not change it.

## Non-goals

- Pawley mode, and the partition formula itself.
- A Le Bail-specific solver. The stop rule is a plan field and a diagnostic.
- Deciding for the caller whether their job is Le Bail or Rietveld — the skill
  says which is which; the package reports what the alternation did.

## Tasks

- [ ] Reproduce #210's shape on a fixture in tree (a multi-phase lab pattern
      with free cells and Caglioti terms), and record the per-pass Rwp table
      for the unconstrained alternation. This is the baseline every later
      number is measured against.
- [ ] `RefinementPlan.lebail_passes` (cap) with keep-best and a stop on
      non-monotone Rwp; the schedule is the plan's and one authority applies
      it, as `stage_ftols()` does for tolerances. Bit-identical at one pass.
- [ ] `LEBAIL_ALTERNATION_STOPPED` diagnostic naming the reason (cap reached,
      non-monotone, converged) and the pass kept; reaches `str(result)`.
- [ ] Skill §2 rule 4 and `references/judging.md` §2 rewritten: name the
      verb, state the cap, and the scope clause — a known structure is a
      staged Rietveld job.
- [ ] Manual Part 1 `using/refining.md`: the alternation and its stop rule;
      Part 2 needs no new equation (the partition is documented).
- [ ] Tests: PbSO4 reaches 10.247 % without a hand loop; Tb2BaCoO5 returns
      pass 1's answer rather than pass 2's; the #210 fixture stops before the
      wander, and the diagnostic says why. obs/calc/diff PNGs to
      `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_lebail_alternation.py tests/test_skill.py
.venv/bin/python -m ruff check src tests examples
```

The wall-clock on the #210 fixture is reported as a range against the
baseline table, never gated.

## References

- Le Bail, A., Duroy, H. & Fourquet, J. L. (1988). *Mater. Res. Bull.* 23,
  447-452 — the intensity partitioning.
- Issue #210 — the measurements above.
- WP-1057 (the Le Bail gap in the report), WP-1123 (the plan owns the
  schedule), WP-1302 (the termination view).

## Handover log

- **2026-09-01** — created from issue #210 during the roadmap reorder; no code
  touched. First task is the baseline table.
