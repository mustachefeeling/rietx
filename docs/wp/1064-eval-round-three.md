# WP-1064 — Agent eval round 3: measured epistemic truth, decision-grade scorer, python-capable arm

Milestone: v1.0 · Status: ⬜
Depends on: WP-1063 (the 0.8 clause must be the one measured; a mid-round
content change is forbidden by the round's own rules); feeds WP-1003 (the
trajectory default, the Layer-2 posture and the refine_json pull surface are
decided from this round's pre-registered criteria)

## Goal

Round 3 runs eval protocol 2.0: episodes whose expected answers are
**measured before registration** and are the epistemic outcomes the package
exists for ("needs more information", "an assumption is wrong", "a good
refinement is impossible but a janky one still informs"), a deterministic
decision-quality scorer, and a **python-capable arm** that answers
report-vs-tools-vs-package-sufficient empirically — with kill/keep criteria
pre-registered per component, so a null has consequences instead of a
re-run.

## Context

**Why the redesign.** Two rounds have produced no interpretable delivery
effect: round 1 (WP-1053, 48 runs) was null with a measured mechanism
(agents never generate the states where the report speaks); round 2
(WP-1059, 30 runs) was invalidated by its own truth rows — E8 cannot be
passed as written (the default plan frees the planted zero and the reached
state is correctly quiet) and R1's expected `ambiguous` is refuted by the
rival measurement (χ² 3.4890 vs 4.0752 on 5332 points). What round 2 did
establish: `ambiguous` becomes *sayable* only with a report (8/16
report-bearing position cells vs 0/4 in `off`); the trajectory arms did
worse than report-only (0/6 vs 2/6) at ~2× the calls (median 2.0 `off` →
4.5 `both`; 23/24 budget exhaustions were haiku in trajectory arms); §9
instruction produced zero bootstrap calls; and the scorer punished the
target behaviour — two E2 cells recovered the planted truth *and* answered
`ambiguous`, scoring fail. The outcome measure (parameter recovery on
mostly-solvable planted rows) is structurally unable to credit the epistemic
outcomes the design thesis is about. Round 3 realigns the measurement with
the thesis. `tests/CLAUDE.md` § "An eval's expected answer is a measurement,
not a definition" is this WP's operating rule, applied constructively.

**Protocol 2.0** (`tests/eval_report_agent/` — `PROTOCOL.md`,
`build_fixtures.py`, `run_refine.py`, `scorer.py`, `grid.py`). Bump
justified four ways at once: episode set, answer schema, scoring rules and
condition axis all move; a 2.0 run is deliberately not poolable with 1.1.
Fix the round-2 leak: `condition.json` moves **out** of the agent workspace
(the shim reads it from a sibling path the prompt never names). Everything
below is written into PROTOCOL.md 2.0 and **dated before any run**.

**Episodes.** Every expected answer is a measurement made at fixture build,
landed as slow tests pinning the landing states (1059's pattern), with
pre-registered decision bands. Where a measurement refuses the intended
design (e.g. a window on which the rivals do not tie), redesign the fixture
until the measurement supports the registration — before the round, never
after.

| ID | Data | Design | Expected | Verifying measurement |
|---|---|---|---|---|
| N1 needs-more-info | SRM 660c truncated to ~20.3–56° **in `episode.json` itself** (nothing to widen into; the overlay can only narrow) | real displaced specimen, disp knocked −0.0801 → −0.02 | `ambiguous` + next_action `extend_range_or_calibrate` | rival fits on the window tie within the pre-registered band [0.99, 1.01]; confirm no reachable state is correctly quiet (the aberration is in the *data* — E8's failure mode cannot recur) |
| E8′ synthetic ambiguous (replaces E8) | LaB₆ `_truth(lo=20, hi=56)` | plant **displacement** −0.02 in the start — E2's shape on E8's window; no default stage frees it (1059's own prescription) | `ambiguous` | rival tie exact by construction (χ² ratio 1.0000, already measured — a synthetic row *can* pose the rival question; it can only ever answer "tie"); the wrong-family state's clause firing is pinned in `test_fitreport_layers.py` (E8-short block) |
| C1 declining-is-wrong (R1 successor) | SRM 660c full window | disp knocked to −0.02 | `converged` **with tol restored** {abs: 0.005} + `none` | the 1059 rival measurement (3.4890 vs 4.0752; zero-only biases *a* +100 ppm); confirm the ridge (−0.120) and the zero-absorber state fail the tol while the swap (−0.0801) passes. Verdict-only re-scoring would recreate the round-2 tension in mirror (a zero-absorbed `converged` at 63σ would pass); the tol is what makes the row honest. Direct test of the 0.8 clause |
| W1 wrong assumption: phase list | `tests/data/11BM_NAC.fxye`, model = NAC only | real unmodelled CaF₂ | `impurity_suspected` + `add_phase` | with/without-CaF₂ fits, Δχ² decisive; strong `unmatched_obs` at the CaF₂ lines. The one row with a real climbing-confidence trajectory signal (0.3 → 0.6 → 0.9, WP-1058) — **the trajectory default is decided here or nowhere**. 59.5k channels ⇒ multi-MB episode.json, ~1.5 s fits; say so in the fixture docstring |
| W2 wrong assumption: instrument | one `qarr/*.prn` (Cu Kα doublet), source declared **single-line** | the Kα2 satellites read impurity-shaped; the correct reading is the instrument model | `assumption_wrong` + `fix_instrument_model` | refit with the doublet: Δχ² decisive **and** the unmatched peaks vanish — the discriminator against `impurity_suspected` (an impurity's peaks survive a source fix) |
| J1 impossible-but-janky | LaB₆ pore proxy (WP-1057 fixture: guest scatterer in the data only), deliverable declared per sub-row | converges Rwp 0.0405, GoF 2.97 | phase_id sub-row: `converged` + `none`; structure sub-row: `ambiguous` + `chemistry_or_contents` | the pinned 2026-08-12 numbers (lebail_gap ×2.4, alternating-sign contents clause), re-measured at fixture build. §4b run as an episode: one state, two correct answers, decided by declared purpose |
| R2, E1 | unchanged from 1.1 | solvable controls | `converged` | existing measurements — kept so `underclaimed` means something |

Second tier, built only if the core shows an effect: J2 (qarr sample 4, the
designed Brindley failure, deliverable=QPA, `converged` +
`report_with_caveat` — the µR fence firing is the measurement, from the v0.3
acceptance), E7 for 1059's deferred hypothesis (b), the second effort tier.

**Scorer v2 — deterministic, no LLM judge** (closed vocabularies make one
unnecessary). `answer.json` v2: `verdict` ∈ {converged, impurity_suspected,
**assumption_wrong**, abstain, ambiguous}; `next_action` ∈ {none,
extend_range_or_calibrate, add_phase, fix_instrument_model,
collect_better_data, chemistry_or_contents, report_with_caveat}, graded by
membership in a per-row registered *set* (near-equivalents must not fail on
wording); `summary` free text, unscored (mining counts its citations
descriptively) — and mining reads the `delivered`/`probed` surfaces, never
word-matches the summary: in round 2 three cells voiced `exchangeable` with
the clause never delivered, one of them in `off` (1063's mining). Round 2's
kept transcripts carried no thinking blocks (measured: 0 characters over all
30), so `voiced` was only a floor on what was read — round 3 keeps thinking
blocks in its kept transcripts; the python arm's tool calls are unaffected
either way, its citations are not. `passed` = verdict match ∧ tol-recovery
where registered ∧
next_action in the registered set where registered. New flag
**`underclaimed`** — the mirror of `overclaimed`: expected `converged`,
answered non-committal. It is what distinguishes "declined correctly"
(verdict match on measured-ambiguous rows) from "declines everything"
(underclaims on the solvable controls). Both flags descriptive; `passed`
stays the single grade. Grids report the epistemic group and the solvable
group as **separate count tables** (generalising round 2's rule); counts,
never percentages; dated, never CI.

**Conditions and matrix.** Core, pre-registered: **{off, report, python} ×
{N1, C1, W1, W2} × {Sonnet, Haiku} = 24 runs**, plus **{surface} × {W1, C1}
× 2 models = 4** for the trajectory decision. `prompt`/`both` are dropped —
round 2 answered the §9 question (instruction produced zero bootstraps).
Budget from 1059's measured figure: ~56 k tokens per JSON run, ~100–150 k
estimated per python run ⇒ ~2.3 M core; second tier extends only cells that
showed an effect. Effort pinned per run; model IDs recorded as the harness
reports them.

**Pre-registered hypotheses**, each naming its cells: (a) with the 0.8
clause, both-free ridge cells drop to 0 and swap states appear on C1/N1;
(b) `ambiguous`-only-with-report replicates on N1; (c) python cells match or
beat JSON `report` cells on decision quality, and their wins cite pulled
evidence — the report-vs-tools-vs-package answer; (d) W1 `surface` cells
beat W1 `report` cells outright, or the trajectory default flips; (e) W2
separates `assumption_wrong` from `impurity_suspected` (the Layer-0 surface
reading is the designed trap).

**The python-capable arm.** Workspace: episode inputs in library-native
form; a verbatim copy of `docs/AGENT_PROTOCOL.md` (the manual ships with the
package — present in **all** python cells; it is part of the surface being
tested, not a treatment); `prompt.md` (answer contract, budget ~6
fit-bearing script runs, hard cap by transcript audit). anatase installed
**non-editable into a venv outside the repo tree**; no repo checkout
reachable; the truth tree stays scorer-side. Required artifacts:
`answer.json` v2 + `final_result.json` (the agent's chosen final
`RefinementResult.model_dump_json()`) — a scorer adapter reads the same
planted-path/tol/watch logic off it where JSON arms read the last ok call in
`calls.jsonl`; `report_present`/`trajectory_rungs` record null (the
condition audit is N/A by design in this arm). Forbidden and audited
(round-2 pattern): reading any repo path, the truth tree, eval docs, the
network — a violating transcript invalidates its cell. Mined per cell:
called `ref.report()`? read identifiability/background evidence?
`suggest()`? `branch`/`compare`? `predict_then_verify`? `compare_rivals`?
That usage record arbitrates the delivery question: pass-without-reading ⇒
the report is a convenience; pass-by-reading ⇒ the report is the
load-bearing pull bundle; fail-where-JSON-report-arms-pass ⇒ push delivery
matters. **No report-off python arm**: one arm plus usage mining answers all
three branches; a crippled-package arm tests a package nobody ships and is
deferred unless the single arm is ambiguous.

**Kill/keep, pre-registered** (written into PROTOCOL.md 2.0 before the
round; the decisions land in 1003's `### Inherited` at close):

| Component | Killed/demoted if | Action on kill |
|---|---|---|
| Report contract (Layer 0 + background/identifiability/lebail_gap evidence) | **not on trial** — content value is measured (WP-1055/1056/1057; Jacobian-derived evidence cannot be re-derived by any consumer) with three consumers; an eval null cannot outweigh that | n/a; removal would be a 1003 decision needing new grounds |
| Layer 2 prose/actions | cells that read Layer 2 do no better than cells reading the evidence tables (mining decides which was read), and the causal record stays negative (E7 round 1, R1 first rung round 2). Decidability precondition (1063's mining): round 2's converged reports carried empty action lists (`report` cells received any `ActionKind` in 1/6 — actions lived only in the rungs), so at least one episode's **converged** report must carry actions or this row is undecidable again; W1 is the candidate, verified at fixture build | demote in AGENT_PROTOCOL to "hypotheses to verify"; soften confidence language; no schema removal pre-freeze |
| `RefineRequest.report_trajectory=True` default | surface cells again cost more calls with no decision-quality gain on W1 — its one real-signal row. The criterion is content, not cost: 1063's mining refuted "paid for and unread" (rung content entered context in 11 of the 12 trajectory-bearing cells, 8 probed `.trajectory` by name) — do not re-litigate this as a cost question | flip to False; record in 1003, resolving the library/agent asymmetry the freeze flags |
| refine_json pull surface | python wins route through pulls JSON lacks and JSON arms fail those same rows | add the `compare_exchanges` arm pre-freeze for 1003 to ratify, or document refine_json as the constrained one-call surface with python primary |
| The delivery-eval programme | round 3, with measured rows and clean audits, still yields no interpretable signal at budgeted N | stop A/B rounds; the injection suite remains the report's evidence base; 1003 records delivery claims as unmeasured — the honest sunk-cost exit |

## Non-goals

- No CI-asserted outcome grid, no percentages, no benchmark claim — a dated
  pilot grid, as ever.
- No LLM judge in the scorer.
- No autopilot anywhere: the round measures whether *informing* works; it
  adds no API that drives.
- No crippled-package python arm in the core (grounds above).
- No mid-round content or protocol change — defects found mid-round are
  recorded post-hoc (the round-2 discipline) and fixed for a successor.

## Tasks

- [ ] PROTOCOL.md 2.0: conditions, episodes with their verifying
  measurements and tie bands, hypotheses (a)–(e) with named cells, the
  kill/keep table, scoring rules, the `condition.json` relocation — dated
  before any run
- [ ] Episode fixtures + slow landing-state tests: N1, E8′ (E8 retired, its
  record kept), C1 (R1 retired likewise, tol restored), W1, W2, J1 — each
  test pins the verifying measurement; build_fixtures grows the deliverable
  axis for J1's sub-rows; verify at build that W1's **converged** report
  carries actions (the Layer-2 row's decidability precondition, from 1063)
- [ ] Scorer v2 + `test_scorer.py` extensions: `assumption_wrong`,
  next_action set membership, `underclaimed`, the deliverable axis, the
  python-arm `final_result.json` adapter
- [ ] Python-arm harness: workspace builder (non-editable install to a venv
  outside the tree, manual copy, prompt), audit extensions (repo-path /
  truth / network reads), usage-mining fields added to
  `mine_transcripts.py` (from WP-1063) — quoting their token vocabulary
  from the live schemas, never string literals (1063's rule; the frozen
  clause phrase is the one deliberate exception, because the record cannot
  change and the live sentence did)
- [ ] `grid.py`: the two group tables (epistemic / solvable)
- [ ] Run the core 28 runs in the Claude Code harness; audit per the
  round-2 pattern; grids from `scorecards.json`; raw record to `eval-runs/`
- [ ] Close-out: findings + kill/keep outcomes restated into 1003's
  `### Inherited` (trajectory default, Layer-2 posture, refine_json arm);
  narrative to `docs/milestones/v1.0.md`; "say which numbers moved"

## Acceptance

```sh
.venv/bin/python -m pytest tests/eval_report_agent          # incl. the slow landing-state pairs
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

Plus: PROTOCOL.md 2.0 dated before the round; the dated grid with both group
tables in the handover; the round record in `eval-runs/` per its README's
contract; venv and platform quoted with every count.

## References

- `tests/eval_report_agent/PROTOCOL.md` (1.1) § Episode validity — the two
  defects this round's fixtures resolve, and the rule that they are fixed by
  redesign and re-registration, never by re-scoring on sight.
- WP-1053 / WP-1059 handovers and `docs/milestones/v1.0.md` § Appendix —
  the two prior grids and their mechanisms.
- Bergmann, Le Bail, Shirley & Zlokazov (2004), *Z. Kristallogr.* **219**,
  783 — the counts-not-percentages scoreboard discipline this harness
  quotes.

## Handover log

- **2026-08-13** — created, from the post-1059 FitReport design review. The
  round's design decisions confirmed with the maintainer: full round 3
  including the python-capable arm; the `report_trajectory` default is
  decided from this round's W1 cells, not flipped pre-emptively.
- **2026-08-13 (session start)** — branch `wp1064-eval-round-three`;
  `### Inherited` (1063's mined counts) pruned. Folded: the
  trajectory-was-read counts into the `report_trajectory` kill row (the
  criterion is decision quality, not cost); the Layer-2 decidability
  precondition (a converged report must carry actions — W1 verified at
  build) into that kill row and the fixtures task; the
  mine-`delivered`/`probed`-never-summary rule and the keep-thinking-blocks
  requirement into the scorer paragraph; the live-schema token-vocabulary
  rule into the harness task. Deleted as already incorporated: the W2-trap
  registration against Layer 0's unmatched peaks — the W2 episode row and
  hypothesis (e) were written from that finding.
