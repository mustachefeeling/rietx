# WP-1063 — Fit-level exchange clause + `compare_rivals`: name the swap, ship the experiment

Milestone: v1.0 · Status: ✅ 2026-08-13 — clause at fit level (THRESHOLDS_VERSION 0.8), `compare_rivals` shipped, the round-2 transcripts mined
Depends on: WP-1056, WP-1059 (both closed — their findings are restated below);
before WP-1003 (the clause is public report text, and 1003 § Inherited carries
it as a freeze question)

## Goal

The exchange clause makes a fit-level claim and names the swap experiment
instead of inviting the ridge; `compare_rivals()` ships as the on-demand
version of that experiment (numbers, no verdict); `THRESHOLDS_VERSION` moves
0.7 → 0.8; and the 30 kept round-2 transcripts are mined for what agents
actually read, before the wording is finalised.

## Context

**The measured defect (WP-1059, 30 real agent runs, 2026-08-13).** The
WP-1056 exchange clause ends "— the data cannot tell which is physical, and a
confident verdict is not supported" (`src/rietx/report/identifiability.py`,
`identifiability_clause()`, the firing-exchange branch). Seven of the twenty
position-episode cells answered that sentence by freeing **both** rivals onto
the degenerate ridge the manual forbids (AGENT_PROTOCOL §4b: "resolved by
protocol … never by freeing the rival into the same fit") — at the best Rwp
in the round (E2 displacement +0.014 against truth 0.000; R1 −0.120/−0.128
against −0.0801). Every cell that reached truth got there by **swapping**
which parameter was free. The sentence names a degeneracy without naming the
action, and freeing the rival is what a reader does with that.

**The claim is also wrong at data level.** On real SRM 660c the R² 0.9977
"exchangeable" zero↔displacement pair is resolved decisively by the fair
rival test — each parameter freed alone with the other **held at its null**:
zero-only Rwp 0.09361 / χ² 4.0752 against disp-only 0.08661 / 3.4890 on 5332
points, and the zero-only model biases *a* by +100 ppm. R² is a *geometric*
measure of column overlap; at these counting statistics the 0.23 % it leaves
unexplained is decisive. So the honest claim is "this **fit** cannot tell" —
and the honest next step is the measurement, which costs seconds
(`tests/CLAUDE.md` § "An eval's expected answer is a measurement": that
round cost 1.7 M tokens; fitting each rival alone costs seconds).

**Do not retune `EXCHANGEABLE_MIN_R2`.** The over-refusal at high N is real,
but the fix is the claim's level, not the threshold: with the claim at fit
level, the gate honestly triggers "run the swap" at any N. A retune would
need its own calibration campaign and buys nothing the wording change does
not. Record this reasoning in the 0.8 changelog entry.

**"Held at its null" is load-bearing.** 1003's Inherited phrasing ("re-fit
with the rival free and the fitted one held") is underspecified — held at
*what value*? The measurement that invalidated R1 held the partner at its
**null identity**, not at its fitted or knocked value; the lazy converged
state (zero free, disp held at −0.02) is *not* one of the two rivals (its
Rwp 0.09127 ≠ zero-only's 0.09361). The clause and the helper must both
encode the null-holding, or consumers will run a confounded experiment.

**Proposed replacement** for the clause's final two lines (final wording may
adjust from the mining output; the three properties are fixed):

```
f"(R² = {worst.r2:.4f}){others} — this fit cannot tell which is "
f"physical; resolve it by measurement, never by freeing both into one "
f"fit (that is a ridge): fit each of the pair alone with the other "
f"held at its null and compare χ²"
```

(i) fit-level claim — honest on R1, where the data *did* choose; (ii) the
forbidden action named beside the allowed one — naming only the degeneracy is
what invited the ridge; (iii) the experiment, not the API — summary strings
stay API-free; AGENT_PROTOCOL names the helper.

**Where the current text is pinned.** `tests/test_fitreport_layers.py`
asserts, on the E2 aberrant state and the E8-short wrong-family state, that
`"exchangeable with the held instrument.geometry.sample_displacement"` (resp.
`…zero_shift`) appears in `report.summary` and that `"ambiguous"` does
**not** (the verdict is the reader's — keep that pin). Update these to assert
the new sentence's *shape* (`"held at its null"`, `"compare χ²"`), never a
second full copy of the string (`tests/CLAUDE.md` § Guards that go quiet).
`docs/AGENT_PROTOCOL.md` §4 step 6 quotes the reading and must track it.

**`compare_rivals` design.** Module-level in `src/rietx/report/layer2.py`
beside `predict_then_verify` (the exact precedent: branch-based,
solve-bearing, on-demand, exported from `rietx.report`):

```python
def compare_rivals(refinement, data,
                   finding: ExchangeFinding | tuple[str, str]) -> RivalComparison
```

Two branch fits from the converged state — rival A: partner free, held-path
at its null; rival B: held-path free, partner at its null; the rest of the
free set unchanged in both, so parameter counts are equal and the raw χ²
comparison is fair without an information criterion (docstring says so,
citing the R1 numbers above as the motivating measurement). Refuses by name:
a pair member with no null identity (the message points at the protocol
resolution — calibrant-fixed zero, wider window — instead), and Pawley mode
(mirror `exchangeability_scan`'s fence). Returns `RivalComparison` (new model
in `report/schemas.py`): per rival {freed_path, held_path, held_at, chi2,
rwp, n_points, freed value + esd, node_id | None} plus `chi2_ratio` —
**deliberately no `decisive` field**. The reasoner gets the experiment, not
the conclusion (the no-autopilot fence: report and suggest inform, never
drive). Cost: two warm bounded fits, seconds.

**The report build stays solve-free.** `compare_rivals` is never referenced
from `build_report`/`assess_*`; land a test asserting a report build performs
zero fits (spy on the solve path), which also documents the invariant.

**refine_json reach: declined for now, on the record.** The JSON call is
stateless and the experiment needs a converged `Refinement` in hand. If
WP-1064's python arm shows the swap is the winning move, the measured
follow-up is `compare_exchanges: bool = False` on `RefineRequest` (post-fit,
response arm `rival_comparisons`) for 1003 to ratify. Restate this into
1003's `### Inherited` at close.

**Transcript mining, first — its output feeds the final wording.** The kept
round-2 record is `eval-runs/2026-08-13-round2/` (gitignored; may be absent
on a fresh clone — the tool must say so rather than stack-trace): 30
`transcripts/agent-*.jsonl` + `.meta.json` (model), joined to
`scorecards.json` by cell. Extract, deterministically: **field citations**
(which report/evidence tokens appear in assistant text — `exchangeable`,
`identifiability`, `lebail_gap`, `worst_absorption`, `soft_mode`, each
`ActionKind` literal, `confidence`), counted per condition × model ×
episode; **ridge mechanism** (for the 7 both-free cells, whether the clause
was echoed before the both-free overlay was written — tool-call order);
**rung usage** (in surface/both arms, whether any trajectory rung content was
quoted — distinguishes "read and misled" from "paid for and unread", which
decides whether 1064's trajectory kill criterion is about content or cost).
Counts, never percentages; and the standing caveat: **quoting is reading,
not benefiting** — round 1's E7 cell quoted the report verbatim and was
wrong with it.

## Non-goals

- No eval-protocol bump and no episode fixes — WP-1064 is protocol 2.0 and
  carries E8's redesign and R1's re-registration; a mid-round content change
  is forbidden by the round's own rules, which is why this WP lands first.
- No `EXCHANGEABLE_MIN_R2` retune (grounds above, recorded in the changelog).
- No refine_json arm for `compare_rivals` (declined on the record, above).
- No new guard, diagnostic code or `ActionKind` — the clause is summary text
  and the helper is a library call.

## Tasks

- [x] `tests/eval_report_agent/mine_transcripts.py` + unit test on a small
  committed synthetic transcript fixture; run it over the round-2 record;
  counts table into the handover entry; round-3-relevant findings restated
  into WP-1064's `### Inherited`
- [x] Clause rewording in `identifiability.py` + the two
  `test_fitreport_layers.py` pins updated to shape assertions (keep the
  `"ambiguous" not in summary` pin)
- [x] `THRESHOLDS_VERSION = "0.8"` + changelog entry in `report/schemas.py`
  (clause rewording; `compare_rivals`/`RivalComparison` added; gates
  unchanged, and why — the R² geometric argument)
- [x] `RivalComparison` model + `compare_rivals()` in `layer2.py`, exported
  from `rietx.report`; tests: the R1-shaped happy path, equal-param-count
  fairness, both refusals by name, `chi2_ratio` orientation
- [x] Solve-free report-build test (spy on the solve path)
- [x] `docs/AGENT_PROTOCOL.md`: §4 step 6 tracks the new wording and makes
  the swap the first resolution; §4b keeps the ridge fence and adds the
  sanctioned experiment beside it; §9 gains a `compare_rivals` paragraph
  beside `predict_then_verify`
- [x] Close-out: 1003 `### Inherited` gets the declined-arm note; "say which
  numbers moved" (passed+skipped by exactly the tests added, both
  selections, venv and platform quoted)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_fitreport_layers.py tests/test_capabilities.py tests/test_agent_surface.py tests/eval_report_agent
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

Plus: the changelog carries 0.8 with the gates-unchanged rationale; the
clause-pin tests fail on a deliberate wording edit with the expected message
(the quiet-guard check), then pass restored; AGENT_PROTOCOL rows updated.

## References

- WP-1059 handover + `tests/eval_report_agent/PROTOCOL.md` § Episode
  validity — the ridge counts and the R1 rival measurement this WP acts on.
- `docs/milestones/v1.0.md` § Appendix (2026-08-13) — the round-2 grid and
  the clause finding's narrative.

## Handover log

- **2026-08-13** — **closed.** All seven items landed, in the WP's own order:
  mining first (its output fed the wording), then the clause, then the helper.

  **Done.**
  - `tests/eval_report_agent/mine_transcripts.py` + `fixture_round/` (a
    committed two-cell synthetic record) + 20 unit tests. Three surfaces:
    **probed** (the agent's query names a field), **delivered** (its text came
    back in a tool result), **voiced** (assistant prose or the `answer.json`
    it wrote). Self-check: it reproduces 1059's 7-of-20 both-free count from
    the record unprompted.
  - The clause: `— this fit cannot tell which is physical; resolve it by
    measurement, never by freeing both into one fit (that is a ridge): fit
    each of the pair alone with the other held at its null and compare χ²`.
    `THRESHOLDS_VERSION` 0.8, with the no-retune rationale in the changelog.
  - `report.compare_rivals` + `RivalComparison`/`RivalFit`, exported from
    `rietx.report`; solve-free report build pinned by spying on the solver.
  - AGENT_PROTOCOL §4 step 6 / §4b / §9; mailbox notes into 1064 and 1003.

  **The mined counts** (30 cells = 5 conditions × 2 models × {E2, E8, R1};
  `[dev]` venv, darwin/arm64; counts, never percentages):

  | measurement | count |
  |---|---|
  | cells the clause *sentence* reached | 13 of 30 (both 4, report 3, prompt 3, surface 3, off 0; E2 7, R1 6, **E8 0**) |
  | cells that probed the `exchanges` table | 3 of 30 (delivered 7, voiced 12) |
  | both-free position cells | 7 of 20 (E2 3, R1 4) — 1059's figure, reproduced |
  | of those, clause in context **before** the both-free overlay | **6 of 7** |
  | of those, clause *voiced* before it | 2 of 7 |
  | E2+R1 cells that got the clause and freed both | 6 of 13 |
  | E2+R1 cells that never got it and freed both | 1 of 7 |
  | cells shipped a trajectory | 12 — probed by name 8, rung content in context **11**, voiced 8 |
  | cells receiving any `ActionKind` | off 0/6, report **1/6**, prompt 1/6, surface 5/6, both 6/6 |

  **Gotchas, all measured while building the miner.** (i) A token in *prompt
  prose* is not a delivery — the §5/§6 excerpts name the whole action
  vocabulary, and a loose match scored 24 of 30 cells on `add_impurity_phase`
  before the package had sent anything; delivery is matched in JSON form,
  probing and voicing loosely. (ii) An overlay written by a `Write` payload
  is an escaped string a brace scan of the serialized input cannot reach, and
  one ridge cell used a Bash heredoc — so overlay detection is tool-agnostic,
  scanning the *values*. (iii) A trajectory probe is answered by
  `tool_use_id`, not adjacency: one cell filtered rungs through
  `jq '{stage, rwp}'`, so real content arrived with no marker field.
  (iv) The kept transcripts carry **no thinking blocks** (0 characters over
  all 30), so `voiced` is a floor on what was read, not a measure of it.

  **Numbers moved.** Fast suite (`-n auto --dist loadgroup -m "not slow"`,
  `[dev]` venv — jax and torch both absent — python 3.12.12, darwin/arm64):
  main `9065d6f` **2198 passed, 108 skipped** → this branch **2228 passed,
  108 skipped**. +30 passed, +0 skipped, exactly the 30 tests added (20 in
  `test_mine_transcripts.py`, 10 in `test_fitreport_layers.py`); no new skip.
  Targeted acceptance selection: 173 passed. Wall clock 2:52 on the branch
  against 3:54 on main, same machine minutes apart — a range, not a figure,
  and the branch has *more* tests.

  **Deliberately not done, with reasons.** No `EXCHANGEABLE_MIN_R2` retune
  (the 0.8 changelog carries the argument: R² is geometric, so no threshold
  on it makes "the data cannot tell" true). No `refine_json` arm — declined
  on the record into 1003's mailbox with the condition that would take it up.
  No root-CLAUDE.md rule: "a clause naming a degeneracy must name the action
  that resolves it" is a genuine standing rule and was drafted, but `CLAUDE.md`
  is at exactly its 600-line cap and the only fits required dropping meaning
  ("collinear *angular* templates", "share-based *global* maturity"), which is
  what the cap exists to prevent. It is a candidate for the next compression
  pass; until then it lives in `identifiability_clause`'s docstring (where a
  clause author reads it) and AGENT_PROTOCOL §4 step 6.

  **Next.** [1064](1064-eval-round-three.md) — its `### Inherited` carries the
  four mining findings that change its design, including the two that move
  pre-registered rows: Layer 2 never reached the JSON report arms in round 2,
  and hypothesis (d)'s mechanism is wrong on `surface__haiku/R1`.

- **2026-08-13** — created, from the post-1059 FitReport design review
  (assessment: content and delivery decompose; this WP is the content half —
  the one measured consumer-facing defect and the pull-tool that
  operationalises its fix).
