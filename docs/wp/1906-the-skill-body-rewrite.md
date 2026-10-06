# WP-1906 — the skill body rewrite: under 5 000 tokens, rules first, evidence in the references, the contradictions resolved

Milestone: unscheduled · Status: ✅ 2026-10-07 — body at 16 999 B, the decision rule holding on Haiku and Sonnet
Track: The repo's own process
Depends on: 1905 (the before-and-after it is judged by); 1532 soft (its fourteen rows land on the rewritten body)

## Goal

`SKILL.md`'s body is at or under `SKILL_BUDGET_BYTES` (17 000 B, the
specification's 5 000 tokens), every rule it carried still holds, the
contradictions WP-1904's audit listed are resolved by stating the condition
each side holds under, and WP-1905's suite shows no case losing against the
current body on Haiku or Sonnet, at fewer input tokens per run.

## Context

WP-1904's audit (`docs/wp/1904-eval/audit.md`) is the work list; this file
restates what decides the design.

- **Where the bytes go.** The body below the frontmatter is 29 687 B, about
  8 700 tokens measured on Haiku (WP-1904). By paragraph class: actionable
  rules 43 %, evidence 23 %, rhetoric and framing 12 %, routing and headings
  15 %, code 7 %. About 8.2 kB of it is restated in `judging.md`,
  `abstention.md` and `surprises.md` (the audit's § D table, rule by rule).
  Evidence plus rhetoric is about 10.4 kB against a 12.7 kB overage, so the
  budget is reachable without losing a rule.
- **Why the budget is a cliff and not a preference.** Claude Code keeps only
  a skill's first 5 000 tokens after context compaction. On the current body
  that cut falls at line 232 of 439: § 4b (the deliverable table), § 6
  (abstention) and § 10 (the worked default) are what a long session loses.
  So the rewrite orders each section by stakes, and the whole body by what a
  session that has already fit once still needs.
- **The contradictions to resolve** (the audit's § B, each with line numbers):
  Le Bail first against "a known structure is no Le Bail job"; the worked
  default breaking its own rules 4 and 5 (a string plan cannot set
  `lebail_passes`, and the background is never seeded); "not negotiable"
  against "a default"; the width seed `W ≈ (FWHM/2)²` against the package's
  own `Γ_G² = U·tan²θ + V·tanθ + W` (so W ≈ FWHM² at low angle, which is also
  what the body's own `W = 1e-3 → FWHM ≈ 0.03°` implies); stop condition 26's
  raw ΔBIC against § 4's N/f²; a 0.5 % cell move called implausible beside a
  1 % starting tolerance; an `ambiguous` verdict that is no field value.
  Each is resolved by writing the condition, checked against the installed
  package, not by picking a side.
- **Structure.** § 5, 7, 8 and 9 exist only as reference-file titles while the
  routing table cites them as body sections; rule 23 is missing; `api.md` is
  routed four times. Reference headings cite the body's rule numbers ("§2
  rules 4-5", "§3 rule 8", "Step 9…17"), so a renumbering edits those
  headings in the same change, and `test_the_body_carries_the_judgement_core`
  pins the seven `## N.` anchors and the phrase "stop condition".
- **Style, from the sources WP-1904 collected.** Imperative; one rule per
  row: the action, the API name, the one-clause reason where the reason
  changes what the agent does. State the positive action where one exists
  and keep a genuine prohibition as one. No intensifiers, no "X is not Y; it
  is Z", no appeal to an unnamed measurement: a reason is a link to the
  reference row that holds the number. Anthropic's current guidance is that
  Claude 4.5+ over-triggers on emphatic language, and the skill-creator
  guide's yellow flag is an ALL-CAPS MUST. "Neuralese" was considered and
  declined: the measured compression results (LLMLingua, telegraphic
  rewrites) test fact retention, not rule compliance, and a terse rule the
  maintainer cannot review is a rule nobody can audit. Tables and short rows
  are the compression; the words stay English.
- **The gaps at fit time** (the audit's § E): a first-call sequence that
  holds together, the plan by data type, instrument setup from a `.prm`, the
  width seed as a parameter path, multi-phase setup, how to read
  `print(result)`, what to do when `max_shift_over_esd` is large, the
  `vary=False` hold trap, the fit range. Each takes the cheapest place that
  holds it (CONTRIBUTING.md § The agent skill): a `help.py` entry or a
  `Diagnostic.suggestion` first, a reference row keyed by a name second, the
  body only for what every fit needs, paid for by a cut.
- **The prototype.** WP-1904 had a compressed body drafted under these rules
  and ran it through `tests/test_skill.py` and the suite's two cases; its
  handover says what it scored and what it lost. The prototype is a
  measurement of the direction, not the rewrite: it is in
  `docs/wp/1904-eval/SKILL.compressed.txt` to be read, not copied.

### Measured inputs (folded from Inherited on arrival, 2026-10-06)

- **From WP-1904 (2026-10-04), the prototype's numbers.** The prototype
  body (`docs/wp/1904-eval/SKILL.compressed.txt`) is 16 401 B and 5 297
  tokens on Haiku against 8 683; `tests/test_skill.py` (137 tests) passed
  with it in place. On Sonnet at N = 2 it lost nothing on `fap-judge`
  (a ceiling there) and produced the only completed with-skill `fap-fit`
  cell of either body under the pilot's CPU contention, so the direction is
  not refuted and not yet shown: 1905's serial round is the measurement.
  Two of its choices need a decision here: its worked default converges
  `usable` over 15-90° and ends `max_iter` over the whole 15-130° range, so
  the example states its range or the plan changes; and it uses a Chebyshev
  background because the P-spline default fired about 778 `HIGH_CORRELATION`
  findings between spline coefficients in its author's run, which is a
  package question (dedup or a different pairing rule) before it is a skill
  one. Both prototype-driven Sonnet runs followed its worked default line
  for line, so what the example says is what an agent does.
- **From WP-1905 (2026-10-04), the suite this rewrite is judged by.** A
  candidate is measured as `tests/eval_skill/build.py docs/skill/rietx <out>
  --body <file>`, run `--ablation none` beside today's body's two-arm round,
  and read with `tests/eval_skill/readout.py compare`; the rule is
  `tests/eval_skill/PROTOCOL.md` § The decision rule. Two things change how
  the pilot's numbers above read. The harness's own score is not comparable
  across ablation modes (the same `fap-fit` state scored 1 of 7 two-arm and
  2 of 8 one-arm), so the pilot's current-against-prototype Sonnet scores set
  a 7-weight score against an 8-weight one; `readout.py` rescores both on the
  same graders. And `fap-fit`'s cell windows are now measured and ask for
  value(esd), because the CIF's starting cell sat inside the pilot's windows:
  the pilot's Haiku with-skill pass was on starting values.
- **From WP-1905 (2026-10-06), the baseline.** Today's body was measured on
  Haiku and Sonnet at N = 3 (`tests/eval_skill/PROTOCOL.md` § Results; result
  files in `docs/wp/1905-eval/round1/`). Compare a candidate's with-skill
  arm against `B2.json` and `B.json`'s `fap-judge` rows on Haiku, and against
  `C.json` on Sonnet. Five things bear on the rewrite.
  - **Haiku's `fap-fit` is the deciding case.** All three with-skill runs
    freed zero and displacement together and reported a = 9.3683(16) Å,
    c = 6.8833(12) Å, outside the window. All three without the skill landed
    inside it. The body's worked default is what Haiku follows, as the
    prototype's Sonnet runs showed (above).
  - **On Sonnet today's body passes every case 3 of 3**, so there the rewrite
    can only be checked for regressions.
  - **The no-skill arm is not skill-free on Sonnet.** It found the wheel's
    copy (`rietx skill`, site-packages) in four of six fit-case runs. The
    decision rule never reads that arm, but a case's role does.
  - **Tier 0 found one over-trigger**: Sonnet loads the skill to convert a
    CIF to POSCAR, three runs of three, which the description's "before
    drawing a crystal structure from a CIF" invites. Haiku's four misses are
    tier 0's absent fixtures, not the description.
  - A build for a round needs `--venv DIR` outside `/Users`, `/tmp` and the
    plugin root on macOS (PROTOCOL § Prerequisites).

## Non-goals

- New physics or new rules: a rule enters the body only from a measured
  failure, with its row in a reference.
- The references' own prose, except the headings that cite body rule
  numbers and the rows that take evidence moved out of the body.
- The description's wording: tier 0 of WP-1905 measures it, and a change to
  it is its own commit with the trigger-set numbers.

## Tasks

- [x] Resolve the audit's § B contradictions, each as one condition clause
      checked on the package, and fix the width formula
- [x] Move the § D duplicates out: a link per rule to the row that holds the
      evidence; cut the rhetoric classes the audit lists
- [x] Re-order: § 1-4 by stakes, the worked default and the stop conditions
      inside the first 5 000 tokens; fix § numbering and rule 23; the
      reference headings that cite rule numbers
- [x] The worked default runs as written (`examples/` holds it, the manual
      `{literalinclude}`s it, `tests/test_examples.py` runs it)
- [x] The § E gaps: each placed by the placement rule or declined with a
      reason, row by row in the handover
- [x] WP-1905's suite: the rewritten body against the current one, N = 3,
      Haiku and Sonnet, tokens per run beside the score; the decision rule
      applied and recorded
- [x] `rietx skill --install . --copy`; `tests/test_skill.py` green; the
      budget met without raising a cap
- [x] Skill: this WP is the skill change
- [x] §10 says a task reproducing another program's refinement adopts
      its protocol (its file's wavelengths, its refined set), not the worked
      default; one round on Haiku and Sonnet (Sonnet's F2 lost
      `file_wavelengths` 3 of 3 by copying §10)

## Acceptance

```sh
.venv/bin/python -m tests.skill_caps          # SKILL.md: 0 over its budget
.venv/bin/python -m pytest tests/test_skill.py tests/test_skill_cli.py tests/test_docs_consistency.py tests/test_examples.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1904's audit and prototype, `docs/wp/1904-eval/`.
- agentskills.io specification (body < 5 000 tokens, < 500 lines) and its
  best-practices page ("add what the agent lacks, omit what it knows");
  Anthropic skill-authoring best practices; Claude Code skills docs (the
  5 000-token compaction keep).
- McCusker et al. (1999) *J. Appl. Cryst.* **32**, 36; Toby (2024) *J. Appl.
  Cryst.* **57**, 175 — the two sources the body's protocol rests on.

## Handover log

- **2026-10-07** — Closed. The last task fixed the one loss the rewrite
  had measured. On a task to reproduce another program's refinement, Sonnet
  had copied the worked example and used generic wavelengths. One clause now
  sends that task to the comparison rule, which names the file's
  wavelengths. On the final body the decision rule holds on both models, and
  Sonnet scores 1.00 on every case at fewer tokens than today's body on both
  fit cases. The body is 16 999 B, 1 B under its budget, so anything WP-1532
  adds to it is paid for by a cut.

  *Done.* §10's opening: "To reproduce another program's fit, follow §4
  instead". §4's comparison rule: "adopt its file's wavelengths, refined set,
  held parameters and excluded regions". Six trims pay for both (an
  introduction, the P-spline clause, rule 17's second sentence, §10's last
  line, rules 12 and 20 by a few words).

  *Measured* (round G, N = 3, against B and C; `tests/eval_skill/PROTOCOL.md`
  § Round G, result files in `docs/wp/1906-eval/`). Sonnet: fap-fit 1.00,
  fap-gsas-reproduce 1.00 (`file_wavelengths` 3 of 3, from 0 of 3 in F2),
  fap-judge 1.00; tokens per run 838k → 482k and 1136k → 929k on the fit
  cases. Haiku: fap-fit 0.43 → 1.00, fap-gsas-reproduce 0.46 → 0.38,
  fap-judge 0.83 → 0.92. Haiku's reproduce runs parse FAP.EXP by hand and fail
  the cell graders on both bodies, so `file_wavelengths` is the only
  difference there. $4.74 for the round; $11.60 over the WP. Tests after the
  edit ([dev] venv, darwin/arm64): `test_skill.py`, `test_skill_cli.py`,
  `test_docs_consistency.py`, `test_manual.py`, 198 passed. No test was added
  and nothing numeric moved, so the fast selection was not rerun. Its last run
  is the entry below. No lane ran in this part: the item needed this session's
  judgement and the maintainer's spend.

  *Review.* Prose only since the last `/code-review`, so none ran: the
  change is SKILL.md text, the protocol's Results and WP files.

  Next: nothing on this WP. WP-1532's rows land on this body next, each paid
  for by a cut (its Inherited). Measuring Opus on the suite is unpriced and
  open.

- **2026-10-06** — The skill's body is now a third shorter than before (16 996 B
  against 29 687), under the 5 000-token budget that survives compaction, and
  it measures better rather than worse. Haiku driving a fit from scratch now
  lands the fluorapatite cell in all three runs, where the old body sent all
  three down a degenerate route: its worked example freed the zero and the
  sample displacement together, and the package's own plan description
  recommended the same thing. Sonnet scores as before on every case at under
  half the tokens on the from-scratch fit. One small loss remains: on a task
  that asks to reproduce another program's refinement, Sonnet copies the
  worked example instead of adopting that program's wavelengths.

  *Done.* Items 1-3 as one rewrite: each of the audit's § B contradictions is
  now a condition. Le Bail is for a cell with no trusted structure, so rules
  4-5 govern a Le Bail run and show the plan object and the seeded coefficient.
  The width seed is `W ≈ (0.6·H)²`, `X ≈ 0.6·H`, from Γ_G² = U·tan²θ + V·tanθ
  + W and the TCHZ combination (0.61·H for equal halves). Stop condition 25
  is the t-ratio then ΔBIC at N/f². The swap's licence is
  `RivalComparison.chi2_ratio`, since `ambiguous` is no field value. A cell
  move is judged against its start's error, not 0.5 %. The esd rule says the
  inflation is already in. Rules keep 1-22, so no reference heading moved,
  and the stop conditions are 23-25, closing the gap. `lab_bragg_brentano`'s
  `PLAN_INFO` text now states rule 6's condition. Evidence the body alone
  carried went to `judging.md` (Hill 1992, Schwarzenbach 1989, the
  coordination-number reading). `docs/manual/conf.py` renders a plain-text
  link label, which the budgeted body uses. Item 4 by a lane:
  `examples/skill_worked_default.py`, held equal to §10 by
  `test_the_worked_default_is_the_example_that_runs`. No `{literalinclude}`
  was added, because the manual already renders the body's block through its
  skill chapter. Rounds F1 and F2 are in `tests/eval_skill/PROTOCOL.md`
  § Results, with result files in `docs/wp/1906-eval/`.

  *§ E gaps, row by row* (all in the body unless declined): 1 first-call
  sequence, §10 plus §2's Le Bail paragraph. 2 plan by data type, §2's
  *When* column. 3 instrument beyond lab Cu, §1's geometry and wavelength
  rows (`debye_scherrer(wavelength)`, api § In); `flat_plate_transmission`
  declined, being api.md's. 4 width seed as a path, §1 and §10. 5
  multi-phase, §1 (`Structure(phases=[...])`). 6 `result.usable`, rule 9. 7
  reading `print(result)`, §4's opening. 8 diagnostics to action, §4's
  opening (`d.suggestion` then grep). 9 the `vary=False` trap, §3
  (`ref.hold`). 10 a Layer-2 suggestion, §4b (`predict_then_verify`); the
  three-line branch recipe declined, being history.md's. 11 QPA fields, §4b
  (`result.qpa.phases`, `weight_fraction`, `zmv`). 12 fit range and
  exclusions, §1. 13 writing the answer, §10 (`write_refinement_cif`,
  `write_qpa_table`). 14 a large `max_shift_over_esd`, rule 9.

  *Measured* ([dev] venv, darwin/arm64). On FAP.XRA with the Cu Kα preset:
  `lab_bragg_brentano` ends `max_iter`, unusable, a = 9.3691(8) Å with
  FLAT_DIRECTION; `mccusker_structural` with a Chebyshev background converges
  at a = 9.37096(9), c = 6.88532(9) over the full range in 4-13 s. The width
  seed changes nothing on FAP (its lines are 0.076°, within 2.5× of the
  default). The P-spline default adds 770 `HIGH_CORRELATION` and two
  `FLAT_DIRECTION` to the same fit (sent to WP-1460). Eval rounds against
  B (Haiku) and C (Sonnet), N = 3, rule holding in F1 and F2:

  | round | fap-fit | fap-gsas-reproduce | fap-judge | $ |
  |---|---|---|---|---|
  | F1 Haiku | 0.43 → 1.00 | 0.46 → 0.38 | 0.83 → 0.83 | 1.75 |
  | F2 Haiku | 0.43 → 1.00 | 0.46 → 0.46 | 0.83 → 0.58 (= −t) | 2.54 |
  | F2 Sonnet | 1.00 → 1.00 | 1.00 → 0.88 | 1.00 → 1.00 | 2.57 |

  Tokens per run fell on six of nine F2 rows (Sonnet `fap-fit` 838k → 365k).
  Session spend $6.86 against the maintainer's ~$9.

  Lanes (`/wp-lanes` trial): one lane, `worked-default-runs`, estimated 22
  requests and took 14; dispatched at 205K; re-read 0K of 5K; 5 main requests
  and 9K left in main to check it; no edits after, no redo; $0.79 lane, saved
  +$0.10 (+1 % of the session). The selective policy's replay row: 72
  sessions, −24 %. Only the laned item carries a decision line: the body
  rewrite started at ~150K and the eval rounds needed the maintainer's spend,
  so both were kept, but neither got its `lanes: keep` line, and the tool
  counts 0 kept.

  *Review* (`/code-review high --fix`, seven findings, four fixed after the
  rounds ran). §10 now passes `report=report` to `summary()`, which otherwise
  built a second report under `plan=None` and lost the plan's veto. §2 says
  "Biso and ADPs" where "displacements" read as sample displacement.
  `history.md`'s agent loop and `numbers.md`'s report call no longer name
  `lab_bragg_brentano`: two siblings the rewrite missed. Declined: a wider
  plain-label pattern in `conf.py` (no link in the tree needs it), a
  friendlier error in the drift test's import lookup (it still catches the
  drift), and §10 printing diagnostics three times (the loop prints `where`,
  which `print(result)` does not). F1 and F2 measured the body before these
  edits, which change one argument and one word in it.

  *Counts* ([dev] venv, darwin/arm64, fast selection, on origin/main
  443c0c1a merged in): 8458 passed, 160 skipped, 1 failed, against 8455 /
  160 / 1 on bare 443c0c1a with the same venv. That is +3, the three tests
  added. The one failure, `test_numpy_path_bit_identical_to_golden
  [toy_anomalous]` (residual off its golden by 1.6e-11), fails on bare main
  too: it arrived with the merges of 2026-10-06, whose CI runs were each
  cancelled by the next push, and this branch touches no numerics. The full
  selection did not run: nothing here moves a measured number. Added-test
  cost, one run under `-n auto`: `test_skill_worked_default_example_runs`
  10.9 s, the two drift tests 0.00 s. The example test stays in the fast
  tier for `test_examples.py`'s stated reason: a broken walkthrough should
  fail on the push that broke it.

  *Gotchas.* The worktree guard refuses `claude plugin eval` typed in Bash
  (it reads "eval"), so the round runs from a script file. The fit cases'
  graders read the script text, so `file_wavelengths` cannot see an
  instrument read from the program's file without `.wavelengths` written.
  That is the instrument, and here the Sonnet runs did use the preset, so
  the loss is real. A F2 Haiku `fap-gsas-reproduce` run hit the 60-turn cap,
  which is where its token rise comes from.

  Next: the new last task. Add one clause to §10's opening (paid for by a cut,
  4 B left) saying a reproduce task adopts that program's protocol (§4), then
  run one round on each model against B and C (≈ $5). Then close: the goal
  holds already, and the rest of the WP is done.

- **2026-10-04** — created by WP-1904's session. No open WP owns the body's
  size or its contradictions: 1338 closed with the budget ratchet, and 1532
  places fourteen rows but rewrites nothing. Next: wait for 1905's first
  round, then start from the audit's § B.
