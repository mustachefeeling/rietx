# WP-1305 — The series deliverable, and the checks the agent ran by hand

Milestone: v1.3 · Status: ⬜
Depends on: 1304 (the text lands in `SKILL.md`)

## Goal

§4b names the fourth deliverable and its stopping rows; `suggest` answers the question
the agent actually had (ΔBIC per candidate, not only Δχ²); whether a
`SEQUENTIAL_DISCONTINUITY` can verify itself is measured and decided.

## Context

- **The hole in §4b.** It answers "good enough" for three deliverables (phase ID, QPA,
  structure). The ramp run's deliverable was none of them: "what does the cell do with
  temperature" is a parameter against a series variable. The agent built its own stopping
  rules, and they were the right ones: model selection by ΔBIC and the rival χ² ratio,
  never by Rwp; the step verified by an independent **cold** refit at 430 and 440 °C;
  tan θ vs cos θ to separate a cell change from a specimen-height jump; CaF₂ as an
  internal standard bounding 2θ drift to ±27 ppm over 280 K; and the explicit split,
  precision on the shape of a(T) at ±0.00015 Å, no accuracy claim on the absolute beyond
  ~100 ppm, because nothing pinned the 2θ scale. ~34 of its 90 calls went to these
  checks. `suggest` was called 5× and the agent still did fit-with/without by hand, so
  Δχ² ranking did not answer its question; in the 86-run campaign `suggest` was called 0
  times.
- **Stop rules arrive in the brief.** In that campaign the stop criterion came from the
  coordinator's brief every time; one worker in four judged itself by a fit statistic,
  the others by a script exiting or a comparison table matching, which is what an
  orchestrator with no better sentence to copy will ask for. So (a) is written as
  sentences a brief can copy (WP-1304's two-readers rule).

### (a) `SKILL.md` §4b, fourth deliverable: a parameter as a function of a series variable

Deciding rows: `SEQUENTIAL_PATH_DEPENDENT` (an ordering artefact; `direction="both"` is
the only way to have it), `SEQUENTIAL_PERSISTENT_FINDING` (is the phase there at all),
`SEQUENTIAL_DISCONTINUITY` (a real step or a wander: check that pattern's own fit),
`PHASE_UNCONSTRAINED` (held, after WP-1301), plus two things no diagnostic can say and the
agent must: a stated 2θ-scale anchor (an internal standard, a calibrant, or none) and the
precision/accuracy split (esds are precision on the shape of a(T); nothing pins the
absolute without an anchor). The operational definition, written once: *good enough is
reached when every quoted number names the one thing that would have to be wrong for it
to be wrong, and that thing has been checked.*

**The row is paid for, not appended.** `docs/skill/rietx/SKILL.md` is capped at
32 000 B / 500 lines by `tests/test_skill.py` and measured 31 593 B / 470 lines on
arrival — 407 B and 30 lines of headroom against a row worth ~700 B. WP-1304's rule
decides where the difference comes from: **a lookup leaves the body, a rule and its
decisive number stay**, so the long-form evidence goes to `references/judging.md` (which
already holds §4/§4b's measurements under per-deliverable headings) and the cap is not
raised — raising it is the decision the cap exists to make visible.

**Which call prints the rows.** The body points a reader at `ref.summary(deliverable=…)`,
so the name has to be one that call accepts, and the §4b row names the rows it prints.
`Refinement._deliverable_lines()` already routes `deliverable="series"` to a branch
printing `"series deliverable rows: pending WP-1305 a"`. But a caller of
`refine_sequential` holds no `Refinement` at all, and no single pattern carries a
`SEQUENTIAL_*` row, so `SeriesResult.summary()` — the series' own termination view —
is where the deciding rows have to live; `Refinement.summary(deliverable="series")` says
what one pattern of a series can answer and names the other call.

### (b) `delta_bic` on `CandidateGroup`

`schemas/suggest.py:82-94` (79e5ae82): `gain − len(members)·ln(N)` with N the residual
length the probe used, from `report/layer2.delta_bic`'s form (Schwarz 1978) under the
Gauss-Newton prediction (the first-order equivalent of N·ln(χ²_r/χ²_f); stated as such in
the field doc and the manual). `_summary` (`strategy/suggest.py:183-202`) quotes it;
WP-1302's termination view prints it as its condition (c). `SCHEMA_VERSION` bump. Test:
on a fit where freeing a parameter is refused by ΔBIC in a full refit, the predicted sign
agrees (the ramp's `sample_displacement` at 25 °C, ΔBIC +6.7 measured by the agent;
synthetic). WP-1302 left the consumer stubbed: `Refinement.summary()` prints
`"next: run suggest"` unconditionally for stop condition (c), and
`docs/manual/using/results.md` § Printing a result documents that placeholder by name —
both take the real ΔBIC line here.

### (c) Discontinuity verification, measure first

`SequentialRefinement.fit(..., verify_discontinuities=False)`: after
`_discontinuity_diagnostics`, for each hit cold-fit patterns k and k+1 through
`_fit_one(..., previous=None)` (history suffix `.verify`), attach `value` = cold step /
chain step and a message clause. The module docstring (`sequential.py:55-68`) stays true:
this is a post-walk check, never a ladder trigger. **Decision rule, fixed before
measuring:** on the ramp it must separate the real step (430→440 °C, ratio ≈ 1) from the
CaF₂ wander (284→295 °C; after 1301 there should be no such diagnostic at all, and the
value is then the step's reproduction) and cost ≤ 10 % of the chain's wall clock. Ship
default-off if the cost bar fails; do not ship if the separation fails; record either
outcome here.

## Non-goals

A general model-selection engine; Hamilton's R-ratio (ΔBIC is the protocol's choice, §8).
Any change to the ladder or `_reseed_needed`.

## Tasks

- [ ] (a) the §4b text in `SKILL.md`, as copyable sentences.
- [x] (b) `delta_bic` + `_summary` + `SCHEMA_VERSION` bump + docs (`using/report.md` §
      Which parameter to free next — where `suggest` is actually documented; `refining.md`
      only mentions it — plus `results.md` § Printing a result and the release notes) +
      the sign test.
- [ ] (c) the verify flag behind the decision rule; the measurement in the handover
      with wall-clock ranges; the decision recorded.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_suggest*.py tests/test_sequential*.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The decision-rule measurement quoted in the handover with wall-clock ranges, never a
single figure.

## References

- Schwarz (1978), *Ann. Statist.* **6**, 461-464 (BIC).
- WP-1016 (series events), WP-1051 (quarantine), WP-1127 (first-rung budget); the ramp
  audit (maintainer memory `agent-surface-audit-insitu-ramp`).

## Handover log

- **2026-08-28** — created, from the parked v1.3 plan.
