# WP-1108 — The license beside the numbers: shipping the statistics placement

Milestone: v1.1 · Status: ⬜
Depends on: 1107 (the grid that chose the placement)

## Goal

The identifiability clause — the exchange finding, the swap experiment and
the WP-1065 license — reaches the one place the 2.2 round measured agents
actually reading: beside the statistics keys. The package change ships what
the round's shim projection simulated, with a named writer and a test
pinning the delivered shape against the shim's.

## Context

Protocol 2.2 (WP-1107, `eval-runs/2026-08-19-round4`, the v1.1 appendix)
measured placement as the pre-registered rule required: the license text
entered agent context in **4/4** `report_stat` cells against **3/4**
`report` cells, added no overclaim, and took `report__haiku`/C1's impurity
trap to `report_stat__haiku`/C1's clean pass (displacement recovered
−0.080098 against truth −0.0801). The 2.1 mechanism it repairs: agents pipe
the JSON response to a file and grep the statistics back, and the summary
string is what the greps drop (license in context in 2 of 12 cells,
WP-1065).

The round's arm was a shim projection — `run_refine._project_license_placement`
renders the clause from the delivered evidence with the package's own
`identifiability_clause`, excises the exact appended substring from
`report.summary`, and injects `result.statistics["identifiability_clause"]`.
Shipping it is **not** "one additive field whose writer is already named"
(which is why 1107 filed this WP instead of executing it): three design
questions are open, each with a measured stake.

- **Move or copy.** The shim *moved* the clause (one copy, one location) —
  but the shipped `report.summary` is consumed by every existing reader,
  and removing the clause from it is a content change the eval was not
  designed to license (1107's non-goal: the content half closed with
  1055–1057). A copy puts the same sentence in two places, against "one
  authority per fact"; a copy stamped by the same renderer at the same
  build is one authority *rendering twice*, which the codebase accepts
  elsewhere only when a test pins the two bit-identical. Decide, and pin
  whichever wins.
- **The writer.** `Statistics` is written at fit time by the optimizer;
  the clause exists only after `build_report` runs (and only when a report
  is built at all). A report-derived string on the result means either
  `build_report` mutates its input's statistics (a writer the schema must
  declare — WP-1076: a declared name is a claim), or the field lives on
  `FitReport` adjacent to a *statistics block the report itself carries* —
  the report already opens with `rwp`/`gof`, so the honest home may be a
  report-level field beside those rather than `RefinementResult.statistics`
  at all. The 2.2 arm injected into the *response's* statistics because
  that is what agents grep; the shipped seam must reproduce that grep-path
  without violating the schema's writer discipline.
- **The contract.** A new serialized field is additive (defaulted, absent
  when the clause does not fire — never null-as-answer); whether it bumps
  `report_thresholds_version` (a consumer-visible emission change: yes,
  by 1.2's own precedent) and what `textdoc`/the GUI render for it are
  part of the change, per the placement-fields pattern (WP-1106).

Keep the recorded stance: the license is stated, the verdict is not — no
`decisive` boolean, no verdict token (`report/schemas.py`, the 0.9 entry).

The reference implementation (from 1107's handover): the shim projection and
its tests (`run_refine.py`, `test_scorer.py` § the 2.2 projections) define
the delivered shape — the shipped field must make the projection a no-op or
replace it, and `test_shim_delivers_exactly_what_the_condition_declares` is
where the equivalence is pinned. The mined anchor (`LICENSE_PHRASE`,
`mine_transcripts.py`) is pinned to the live clause by test — reword the
license and that pin breaks by design; freeze the phrase for the archived
records before re-quoting.

## Design note (2026-08-19)

**Copy, not move.** The clause stays in `report.summary` and is *also*
delivered as `result.statistics.identifiability_clause`. The round measured
placement, not content (1107's non-goal), so excising the clause from the
summary would change what every existing summary consumer reads — the GUI
report panel, `textdoc`, every `StageReport` rung (`for_stage` copies
`self.summary` verbatim), and any human — on evidence that was never
collected: the 2.2 `report` arm's failure was *delivery* (the greps drop the
summary), not content (it added no overclaim). The one-authority rule is
kept in the strongest form available: `build_report` calls
`identifiability_clause` **once** and writes the one returned string to both
places in the same build — one authority rendering once, written twice — and
a test pins the delivered pair: the summary carries `"; " + clause` exactly
when the field is set, byte-identical.

**The writer is `build_report`, writing `result.statistics
.identifiability_clause` — a declared cross-document write.** The
alternatives lose on measured grounds:

- *A `FitReport`-level field* (beside `report.rwp`/`report.gof`) is a
  different placement from the one the round measured — `jq
  .result.statistics` and every statistics-block grep never see it — and
  shipping an unmeasured variant is what 1107 existed to prevent.
- *A fit-time stamp* (the optimizer or `refine` writing it) puts a
  THRESHOLDS_VERSION-governed sentence — reworded at 0.8 and 0.9, each
  change eval-measured — into every result whether or not a report is ever
  built. That changes the report-off response shape (an arm 1107 measured
  as clause-free), couples the two contracts so a thresholds bump moves
  result bytes, and inverts "a report is derived from a result, so it rides
  beside one, never inside" (root CLAUDE.md).

`build_report` mutating its input is the honest form of the measured
conditionality: the clause reaches the statistics exactly when a report was
built, which is exactly when the 2.2 arm delivered it ("both inert when the
report is withheld"). The write is declared on the field (WP-1076: a
declared name is a claim — the docstring names `build_report` as the only
writer), idempotent (the renderer is deterministic from the evidence), and
validated (`Base` has `validate_assignment=True`). No agent-layer
special-casing is needed: `refine_json` builds the report before
serialization and `Refinement.report()` reads the same `result_` object
`fit()` returned, so the python surface and the JSON surface get the same
fact from the same writer.

**Rendering (2026-08-19, task 3).** `textdoc` renders nothing: the `.rxt`
document is the *editable* view — settings, plan, parameter rows — and
carries no statistics and no report content, so there is no line for the
field to join. The GUI renders the sentence exactly once already: the
Report panel receives `report.model_dump()` and shows `summary`, which
keeps its copy; the GUI never displays the serialized `Statistics` block
(its readouts are the rwp/gof headline numbers), so rendering the field
would put the same sentence twice in one view. The statistics placement
exists for the pipe-and-grep path, which no GUI window has. History-node
metrics build their own `Statistics` at commit time, before any report
exists, so a node honestly carries `None` — "no report built" at that
state, never a missed write.

**The absent state is `None`**, covering both "no clause crossed the
comment threshold" and "no report was built" — the honest empty state
(WP-1076), declared on the field; it can never read as a verdict, and no
verdict token enters (the 0.9 stance). `None` serializes as `null` like
every other absent-for-cause statistics field (`durbin_watson`,
`esd_inflation`); a bespoke omit-when-None serializer for one field would
be a novelty seam. Per-histogram `HistogramResult.statistics` declares the
field and nothing writes it (the clause is whole-fit — the
`max_shift_over_esd` precedent); the transient per-stage results in
`_stage_report` are stamped and thrown away, which keeps each rung's
summary and its own statistics in agreement. SCHEMA_VERSION stays 0.2: a
new defaulted field is a safe addition by `schemas/common.py`'s own rule;
the consumer-visible emission change is the report contract's, so
`report_thresholds_version` bumps to 1.3.

## Non-goals

- Re-running any eval cells: the placement decision is made and dated
  (v1.1 appendix); this WP ships it.
- Rewording the license or the clause (the E8p overclaim question belongs
  to the next eval round, not to this seam).
- Any change to the retired `report_with_caveat` / `caveats` contract —
  harness-side, closed with 1107.

## Tasks

- [x] Decide move-vs-copy and the writer (design note in this file, with
      the one-authority argument written out); the schema field lands with
      its writer named and its absent-state honest.
- [x] The renderer stays the one authority: whatever ships is produced by
      `identifiability_clause`, never a second sentence.
- [x] `report_thresholds_version` bump + changelog entry in
      `report/schemas.py`; `textdoc` and both GUI windows render the field
      (or deliberately do not, with the reason recorded here).
- [ ] The shim's `license_placement="statistics"` projection re-pinned
      against the shipped field (no-op or replaced); eval fast selection
      green.
- [ ] AGENT_PROTOCOL/manual: the field documented where §4 step 6 names
      the decision band (Part 1 name-resolution tests will enforce it).

## Acceptance

```sh
.venv/bin/python -m pytest tests/eval_report_agent tests/test_fitreport_layers.py -q
.venv/bin/python -m ruff check src tests examples
```

The field is delivered in a real `refine_json` response bit-identically to
what the 2.2 `report_stat` arm delivered, and the grep an agent runs on the
statistics block returns the license.

## References

- WP-1107 (the round, the rule, the grid), WP-1065 (the license sentence
  and the 2-of-12 finding), WP-1106 (the placement-fields pattern this
  follows).
- `docs/milestones/v1.1.md` § Appendix — eval protocol 2.2 (the dated
  grids and read-outs).

## Handover log

- **2026-08-19** — created by WP-1107's Task 5: the grid favoured the
  statistics placement by the pre-registered rule, and the shipped form is
  an open design (writer, move-vs-copy, contract), so it is filed rather
  than executed.
