# WP-1054 — Layer-2 honesty on the abstained branch: the phantom-phase invitation

Milestone: v1.0 · Status: ⬜
Depends on: —

## Goal

An abstained FitReport whose action list no longer *invites* the wrong move: when
peak-position evidence says the cell is wrong, `reindex_or_recheck_cell` is an
emitted action (not a buried alternative), `add_impurity_phase` is confidence-capped
with the shift evidence attached, and an un-modelled foreign peak can no longer
manufacture an unflagged texture detection that outranks the impurity call.

## Context

**The measured failure, three sightings.** The Layer-2 emitters were built for the
mature branch; the abstained branch reuses only `layer0_actions` + `texture_actions`
(`report/__init__.py::build_report`, abstain arm). Consequences, all measured:

1. **Wrong cell → confident impurity proposal.** On the +0.4 % cell scenario
   (`tests/test_fitreport_layers.py` fixture family: `_truth()` LaB₆,
   `Cell.cubic(4.1568*1.004)`), Rwp 0.719 abstains (correct), the displaced peaks
   read as 33 `unmatched_obs`, and the **only** surviving action is
   `add_impurity_phase` at 0.9 — the truth appears solely in that action's
   rationale hedge and `alternatives`. `reindex_or_recheck_cell` is emitted only in
   `suggest_actions` (mature branch), i.e. it is structurally unreachable exactly
   when the cell is most wrong (measured 2026-08-11; same shape re-measured on
   broad-peak data: 0.6° lor_size + 0.05° zero → abstain + `add_impurity_phase`
   0.7 from residual-lobe "unmatched" peaks).
2. **A real model consumed the invitation.** WP-1053's pilot (closed 2026-08-11):
   on E7, on-haiku quoted `add_impurity_phase` 0.9 verbatim as grounds for its
   wrong verdict; sonnet had to actively decline by indexing the unmatched peaks
   itself. The report sat on the wrong side of the split — the one place it moved
   an outcome, it moved it toward the phantom phase.
3. **Impurity manufactures texture.** A pure impurity injection (Gaussian at
   29.35°, ~900 counts, the `test_fitreport_layers` doping recipe) produced
   `TextureAnalysis.detected=True` — axis (1,0,1), r=0.574, R²=0.66 — because the
   foreign intensity leaks into the Le Bail-style per-reflection extraction
   (`report/texture.py::_extracted_corrections` partitions `y_obs − background` by
   calculated share; a peak the model does not predict is partitioned onto its
   neighbours). The resulting `refine_preferred_orientation` at 0.66 **outranked**
   `add_impurity_phase` at 0.40. Measured 2026-08-11; nothing in the report links
   the two or warns that one can produce the other.

**Why `explained_by_shift` did not catch case 1**: it pads shifted regions by
`mean_fwhm` (~0.03–0.05° on sharp data), but a 0.4 % cell error displaces
high-angle peaks by 0.05–0.15° — outside the pad and outside the 0.08°
tick-matching tolerance, so the observed peaks look unmatched. The padding is
right for the mature branch's small shifts and wrong for exactly the regime the
abstained branch handles. The validity-radius gate failures
(`outside_validity_radius` in `RegionAttribution.gate_failures`) already carry the
evidence that positions, not contents, are wrong — they are just never consulted
by the impurity emitter.

**Two cautions that bound the fix.** (a) *The position family is unresolvable at
abstention* — the same validity-radius signature is produced by a wrong cell
**and** by a gross zero/displacement error (measured: broad-peak data + a 0.05°
zero error, correct cell, fails validity on 4/15 regions). So the emitted action
must carry the whole family — `reindex_or_recheck_cell` with the calibration
candidates in `alternatives` and a rationale that says the data has not chosen —
never a confident reindex singleton; indexing's own shift allowance
(`INDEX_SHIFT_ALLOWANCE`) is why reindexing is still the safe *first* member.
(b) *The evidence consulted is the gate failure, not the failed coefficients*:
a gate-failed region's coefficient values must not be read as causes
(`RegionAttribution`'s documented rule); what the emitter may use is the failure
kind, its |Δ2θ|-vs-FWHM magnitude, and its χ² share.

**Design frame (user directive, 2026-08-11 session): evidence over verdicts.**
Keep every peak in `unmatched` (Layer-0 evidence is correct — those peaks *are*
unmatched); fix the *verdict layer*: which action kinds are emitted, at what
confidence, carrying which evidence. Nothing here deletes information; the
never-a-confident-wrong-singleton invariant is the yardstick.

The same directive owns one general evidence-preservation item folded in here
(2026-08-11, user decision): `TextureAnalysis.best_axis` is nulled whenever
`detected=False` — the best-scoring axis is computed and then discarded, so a
reasoning consumer reading r²=0.39 (the pore-proxy measurement) cannot see
*which* axis got that score. Change it to always-populated evidence
(`detected` stays the branch field, per its docstring). Verified against the
one deployed consumer: `gui/src/panels/Report.svelte` filters texture rows on
`t.detected` before rendering the axis, so the change is display-invariant
there; re-check `agent.py`/`test_agent_surface.py` pins in-session.

**Collision note.** WP-1057 (resolution-limited abstention wording) edits the
same abstain arm of `build_report` and the abstention reason strings this WP's
tests will assert against. This WP is the recommended first lander; whichever
lands second must expect the other's wording/tests and coordinate via
`### Inherited`.

**Versioning.** No new `ActionKind` is needed (`reindex_or_recheck_cell` exists
since v0.2). Changed *emission conditions* are a behaviour change a consumer sees:
decide and document whether that is a `THRESHOLDS_VERSION` 0.3 → 0.4 bump
(`report/schemas.py` pins the constants; the version travels in every report).
Precedent: WP-1024 changed only a rationale and explicitly did not bump.

## Non-goals

- No change to Layer-0 peak detection or the `unmatched` list itself.
- No change to the maturity gate or its thresholds — abstention fired correctly
  in every measured case; this WP fixes what survives it.
- No delivery-timing work (`diagnose` task, per-stage reports) — WP-1058.
- No general evidence-restructure of `detected` semantics beyond texture's
  cross-talk caveat; the identifiability layer is WP-1056.

## Tasks

- [ ] Emit `reindex_or_recheck_cell` from the abstained branch when
      validity-radius failures carry substantial χ² share (the mature-branch
      emitter's condition, evaluated on the attribution list the abstained branch
      already has). Rationale quotes the measured shifts vs FWHM.
- [ ] Make the impurity emitter position-aware in the large-shift regime:
      unmatched peaks consistent with the validity-radius/shift evidence cap
      `add_impurity_phase` confidence and put `reindex_or_recheck_cell` first in
      `alternatives`, with the count of shift-consistent vs shift-inconsistent
      peaks in the rationale (a genuinely foreign line — E5's 29.34° — must keep
      its strong call: the zero-shift-plus-impurity double injection is the
      regression case).
- [ ] Texture cross-talk: when strong `unmatched_obs` evidence coexists with a
      texture detection, annotate the `TextureAnalysis` (caveat field or
      documented rationale clause) and cap `refine_preferred_orientation`
      confidence below the impurity action's — the 0.66-outranks-0.40 inversion is
      the pinned regression. Keep axis/r/R² populated (evidence preserved).
- [ ] `TextureAnalysis.best_axis` becomes always-populated evidence (`detected`
      unchanged as the branch field); docstring updated, GUI/agent consumers
      re-checked (the GUI's `detected` filter is verified above).
- [ ] Decide and document the `THRESHOLDS_VERSION` question for the emission
      changes; update `docs/AGENT_PROTOCOL.md` §6/§7 rows that describe the
      abstained branch's action inventory.
- [ ] Tests: cell-wrong abstained state (top active action set), broad-peak
      variant, impurity/texture inversion, double-injection control + obs/calc/diff
      PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_fitreport_layers.py tests/test_preferred_orientation.py tests/test_report_loop.py -q
.venv/bin/python -m ruff check src tests examples
```

On the +0.4 % cell abstained fixture, `reindex_or_recheck_cell` is an emitted
action and `add_impurity_phase` no longer stands alone at 0.9; on the impurity
fixture, the impurity action outranks the texture action; the WP-1052 loop suite
still passes (E5's genuine impurity keeps its call).

## References

- WP-1052/1053 findings (closed; restated above — E6/E7 invitation, measured
  consumer cost).
- `docs/DESIGN.md` § "Outputs & fit assessment" (never a confident wrong
  singleton).
- 2026-08-11 planning-session measurements (this file § Context is their record;
  scenario scripts reused `tests/test_fitreport_layers.py` fixtures and are
  reproducible from them).

## Handover log

- **2026-08-11** — created, from the FitReport design review (evidence-over-
  verdicts directive) + WP-1053's pilot findings. Not started.
