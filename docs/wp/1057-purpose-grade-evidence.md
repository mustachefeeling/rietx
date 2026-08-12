# WP-1057 — Purpose-grade evidence: the Le Bail gap, resolution-limited abstention, and stopping criteria

Milestone: v1.0 · Status: ⬜
Depends on: —

## Goal

The report can answer "is this fit good enough *for what I need*" without lowering
any bar: a structural-vs-profile split (the Le Bail gap) lands as the phase-ID
triage statistic; the abstention text distinguishes "model wrong" from
"resolution-limited"; incoherent intensity misfit gets its contents-type summary
line; and AGENT_PROTOCOL gains a "declare the deliverable" section mapping
phase-ID / QPA / structure goals to the report rows that decide them.

## Context

**The regime this serves** (user directive, 2026-08-11): much real work is
non-ideal — nanoparticle broadening that erases fine detail, porous frameworks
(MOFs, zeolites) whose intensities are off because of unknown pore contents —
and the operator may only need a phase-ID-grade fit. The report must let an agent
recognise that as a legitimate stopping point rather than push finer corrections.

**Measured grounds (2026-08-11 planning session; scenarios reuse
`tests/test_fitreport_layers.py::_truth()` LaB₆ fixtures — scripts were
scratch-only, reproducible from the recipes here):**

1. **The gates already auto-scale to information content** — no "nanoparticle
   mode" needed. With 0.6° Lorentzian size broadening in truth *and* model, a
   +0.008° zero error (confidence 0.997 on sharp data) produces silence: GoF
   1.02, zero suggestions. Right behaviour; keep it.
2. **But the low-information abstention is unlabelled.** Same broad data with a
   0.05° zero error: abstains via the explained-fraction clause with gate tally
   `gram_condition` 12 / validity 4 / local_r2 4 of 15 regions — and the
   gram-failed regions carry **R² ≈ 0.99** (example: cond 1.2e5). The basis
   *explains* the misfit; the five edit-directions are indistinguishable on
   merged peaks. That is "misfit readable only in aggregate at this resolution",
   currently spelled with the same words as "model wrong" (plus a misleading
   `add_impurity_phase` 0.7 — WP-1054's territory).
3. **Pore-content proxy** (guest O at LaB₆'s 1b site, occ 0.6, Biso 2.0, in
   truth only): the report localises perfectly — intensity carries **83 % of
   misfit**, per-region intensity errors ±10–20 % with **alternating sign**
   ((100) −20 %, (110) +15 %, (111) −12 %: structure-factor interference, the
   unmodelled-scatterer signature), best template R² 0.12, texture correctly
   below its bar — and emits **zero actions**. Honest, but the expert inference
   ("contents wrong, positions/profile fine, phase ID is safe") is left
   unstated.
4. **The deciding statistic is the Le Bail gap, measured 2.1×**: converged
   Rietveld on the host model Rwp 0.0399 / GoF 2.93; Le Bail with the same
   phases Rwp 0.0190 / GoF 1.39. "Le Bail ≈ noise, Rietveld ≫" = every line
   indexed, profile right, intensity model wrong. This field has been in the
   design record's Layer-0 inventory ("Le Bail-vs-Rietveld Rwp gap,
   structural-vs-profile triage", DESIGN.md § Outputs — the "ships in v0.1"
   list) and has never landed in the schema.

**Mechanics for the gap.** Cheapest honest version: an evaluate-only Le Bail
partition at the converged state (`CompiledModel.lebail_update` iterations with θ
frozen — no refinement, so frozen-per-stage discreteness is untouched), reported
beside the Rietveld Rwp with its convention documented; a branch fit is the
expensive alternative. Decide in-session; either is additive
(`FitReport`/Layer-0 field, defaulted). Rietveld-mode only, and meaningless when
the mode already is Le Bail/Pawley — absent-for-cause, like the WP-1043 evidence
arm's figures. **Protocol honesty about the 2.1×**: the measured gap above came
from a short Le Bail *fit* (background + cell + zero freed), not the θ-frozen
evaluate-only partition proposed as the cheap mechanism — on the proxy the cell
and zero were already true so the difference should be small, but re-measure
with the chosen mechanism before quoting the number in the field's docstring.

**Collision note.** WP-1054 edits the same abstain arm and its action set; this
WP's resolution-limited wording changes the abstained summary/reason strings
1054's tests may assert. 1054 is the recommended first lander; whichever lands
second coordinates via `### Inherited`.

**Protocol half.** AGENT_PROTOCOL already teaches that Rwp is a nearly useless
absolute (§4) and that abstention is a result (§6). What it lacks is *purpose*:
a section mapping deliverable → rows → stopping criterion — phase ID:
`unmatched` empty + Le Bail gap small → done at any absolute Rwp; QPA:
scale/Biso/background-absorption rows (WP-1055) are the ones that bias
fractions; structure: everything, plus WP-1056's exchangeability. Tiering per
the user directive: a floor for weaker agents ("verify before acting; treat
capped confidence as unresolved") without a ceiling for stronger ones. The
report itself stays purpose-neutral — purpose lives where judgment lives.

### Inherited

**From [1054](1054-abstained-branch-honesty.md), closed 2026-08-12 — you are
the second lander on the abstained arm; here is what it looks like now.**
`build_report`'s abstain arm assembles `layer0_actions` (ticks threaded
through) + `reindex_action` (the shared emitter — fires on a *count fraction*
of misfitting regions beyond the validity radius) + `texture_actions`, runs
`cap_texture_crosstalk`, applies the veto, and **sorts by confidence** — your
wording edits land on that structure. The abstention *reason strings*
(`maturity_gate`) are untouched, so your resolution-limited wording starts
clean. Tests now asserting on the abstained action set, which your changes
must expect: `test_report_loop.py::test_e6_wrong_cell_applies_no_position_action`
(reindex tops the list, `top_blocked_nonstage` names it) and the four
WP-1054 tests at the end of `test_fitreport_layers.py` (cell-wrong, broad
lobes, texture inversion, double injection). `THRESHOLDS_VERSION` is already
0.4 this milestone — a further 1057 bump is a fresh decision, not implied.

## Non-goals

- No lowering of any gate or threshold; "good enough" is a different question
  answered exactly, not a relaxed standard.
- No auto-detection of "the user only wants phase ID" — the protocol section
  teaches *declaring* it; inferring it is an agent's judgment call.
- No abstained-branch action fixes (WP-1054), background section (WP-1055),
  identifiability (WP-1056), delivery timing (WP-1058).

## Tasks

- [ ] Le Bail gap field: evaluate-only partition at the converged state,
      additive Layer-0/report field with both numbers and the mode caveat;
      absent-for-cause in Le Bail/Pawley mode.
- [ ] Resolution-limited abstention flavour: when `gram_condition` dominates the
      gate-failure tally with high per-region R², the abstained summary says so
      in those terms (aggregate misfit readable, per-kind attribution not) —
      wording change + a structured reason field, no threshold semantics change.
- [ ] Contents-type intensity summary: intensity share high + no angular
      template fits + sign-alternating per-region intensity coefficients →
      one summary clause naming the pattern and pointing at the Le Bail gap;
      evidence stays in `attribution` as today.
- [ ] `docs/AGENT_PROTOCOL.md` § "Declare the deliverable": the three goal
      profiles with their rows and stopping criteria, the capability-tier floor,
      and the measured 2.1× worked example.
- [ ] Tests: pore-proxy fixture (gap ≈ 2× reported, contents clause present),
      broad-peak fixture (resolution-limited wording), sharp converged reference
      (no gap clause, no noise) + obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_fitreport_layers.py -q
.venv/bin/python -m ruff check src tests examples
```

The pore-proxy fixture's report carries the Le Bail gap and the contents-type
clause; the protocol section exists and quotes it; the broad-peak abstention
names resolution, not model error.

## References

- `docs/DESIGN.md` § "Outputs & fit assessment" (the unlanded Layer-0 inventory
  item this WP completes).
- Toby (2006) Powder Diffr. 21 (Rwp's meaning; the § 4 stance this extends).
- 2026-08-11 measurements — this file § Context is their dated record.

## Handover log

- **2026-08-11** — created, from the non-ideal-data design discussion
  (nanoparticle + MOF regimes). Not started.
