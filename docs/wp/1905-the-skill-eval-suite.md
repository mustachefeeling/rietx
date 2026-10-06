# WP-1905 — the skill eval suite: `claude plugin eval` over the skill tree, cases from real failures, judge-free first

Milestone: unscheduled · Status: 🔄 2026-10-06 — claimed by @yue-here
Track: The repo's own process
Depends on: 1904
Priority: P2 2026-10-04 — the decision WP-1906 and WP-1532 wait on: no body change lands without a before-and-after it can read

## Goal

`tests/eval_skill/` builds a throwaway plugin from any skill tree and runs
`claude plugin eval` over a registered case set, so a body change is measured
against the current body and against no skill at all, on two models, before it
merges. Three cases exist, each written from a wrong turn an agent took, and
the first tier of graders costs no judge calls.

## Context

WP-1904 measured the strategy this WP implements; its handover holds the
numbers. What a fresh session needs from it:

- **The harness is first-party.** `claude plugin eval` (Claude Code ≥ 2.1.289)
  takes a plugin directory, runs each case `runs` times with the plugin and
  the same number without it, scores with six grader types, and writes
  `aggregate-result.json` plus an HTML report. Four grader types are free and
  deterministic (`regex` over the reply, a file or the trace; `tool_used`;
  `tool_order`; `file_exists`); two call a judge (`llm`, three votes, PASS at
  two; `baseline`, against a reference transcript). Each run is a `claude -p`
  child in an isolated home: no user settings, no `CLAUDE.md`, no other skills.
  Fixtures come from a `scaffold_script` run with `--scaffold`; a shell grant
  needs `--allow-tools Bash` and a sandbox backend (`bubblewrap`, `socat` on
  Linux, which the pilot had to install). Docs:
  <https://code.claude.com/docs/en/plugin-evals>.
- **The skill tree is not a plugin, and should not become one.** A plugin
  manifest inside `.claude/skills/rietx/` would change how every session in
  this repository loads the skill (namespacing, precedence over user skills),
  and the two committed copies must stay byte-identical to `docs/skill/rietx/`
  (`tests/test_skill_cli.py`). So the suite **builds** a plugin:
  `build.py <tree> <out>` copies the skill tree under `<out>/skills/rietx/`,
  writes `.claude-plugin/plugin.json`, and lays the cases beside it. The
  condition is therefore the tree handed to `build`, which is how the repo's
  three earlier rounds enforce a condition (`tests/CLAUDE.md` § Three eval
  protocols): in the workspace, never in the prompt. Two trees → two builds →
  two runs of one suite; `--ablation none` on the second skips a baseline arm
  that would repeat the first's.
- **The pilot, 2026-10-04.** Two cases ran on Haiku and Sonnet for the
  current body and WP-1904's prototype; the cases, their graders, the build
  script and every result JSON are in `docs/wp/1904-eval/pilot/`. Four
  findings decide this protocol. (1) `fap-judge` is a ceiling on Sonnet: 4 of
  4 in every arm for both bodies at N = 2; on Haiku it separates (4 of 4
  with, 3 of 4 without). Keep it as Haiku's regression guard and build the
  deciding cases from failures the current body shows. (2) A fit case
  cannot run concurrently: four with-arm fits on four cores took 10-15 min
  each inside the sandbox against 11 s for the same script outside, and two
  of four cells timed out at 1 500 s. Measure one fit inside the sandbox
  first, set `timeout_seconds` from it, run `-j 1`, one round at a time;
  whether the sandbox's read-only venv also defeats the numba kernel cache
  is unmeasured. (3) With-arm runs did more work than without-arm runs on
  the from-scratch case (eight Le Bail passes, a report, a second fit), so
  tokens and wall time per run are read-outs beside the score, and a run
  that ends promising to write its report later scores as not written.
  (4) One cell read files outside its workspace; keep the placement round's
  `leak` read-out. Costs measured: Haiku $0.16 (judge) and $0.60 (fit) for
  both arms; Sonnet $0.14-0.18 (judge) and $0.23-0.62 (fit) a run.
- **Cases are written from failures, never from the body.** The sources on
  hand: issue #661's fourteen wrong turns (a reflection table without a fit,
  the flattened background paths, the width boxes, the isotope spellings);
  WP-1504 round B's stalls on the figure surface (`docs/wp/1504-eval/runs/`);
  the placement round's episode. A case that the current body already passes
  at 3 of 3 on both models and no skill fails is a regression guard; one the
  current body fails is the eval the rewrite is judged on. Keep both and say
  which is which in the case's `description`.
- **Three tiers, cheapest first.** Tier 0, triggering: ~20 prompts, half
  should-trigger and half near-miss should-not (agentskills.io's
  description-optimisation recipe), graded by `tool_used: Skill` with
  `arm: both` and `min: 0, max: 0` on the negatives; judge-free. Tier 1,
  outcome by a free grader: a number in a written file (`regex` with
  `{source: file}`, e.g. the fluorapatite cell `9\.37[0-3]` and `6\.88[5-7]`
  in `report.md`), a verb called (`tool_used: Bash` with `input_match`), a
  reference opened (`regex` on `trace`). Tier 2, judgement by rubric: short
  answers only, rubric as PASS and FAIL conditions, `--judge-model sonnet`,
  and "suspect the judge before the skill" when the skill fired and Δ is
  negative (the docs' own rule).
- **Read-outs fixed before a round runs**, in `tests/eval_skill/PROTOCOL.md`
  in the three earlier rounds' form: per case and arm the score, the pass
  rate, cost and wall time; whether the skill fired; which reference files
  were opened; the trace kept (`--keep-temp`) for the route. **Decision rule
  for a body change**: paired per-case Δ against the current body, N = 3 per
  arm on Haiku and Sonnet; no case may lose more than one grader's worth, and
  the with-skill token count per run is reported beside the score, because
  the rewrite's claim is cost at equal score.
- **A case's expected answer is a measurement** (`tests/CLAUDE.md` § An
  eval's expected answer): every numeric grader's window is read off a
  converged fit and the GSAS reference (`tests/data/README.md`), never off
  the body's prose.
- **Price.** The pilot's two-arm Haiku case cost $0.16; a Sonnet run of a
  case that fits costs more and is measured in the first round. Every round
  passes `--max-cost-usd`, and the menu goes to the maintainer before any
  cell runs (WP-1504's rule).

## Non-goals

- The rewrite itself: WP-1906 (judged by this suite).
- Running the suite in CI on every PR: WP-1907 schedules the judge-free tier
  nightly once the suite is stable.
- A leaderboard, a published benchmark, or any case on data without a
  peer-reviewed or public citation.

## Tasks

- [x] `tests/eval_skill/build.py`: a plugin directory from a skill tree and
      the case set; `test_eval_skill.py` pins that every case's fixture
      exists, every grader file parses, and `PROTOCOL.md` quotes each prompt
- [x] `PROTOCOL.md`, registered before the first scored round: the question,
      the conditions, the models, N, the read-outs and the decision rule above
- [x] The three cases: `fap-judge` (from the placement round), `fap-fit`
      (from scratch: cell in `report.md` by regex, a fit run by `tool_used`,
      the caveat by rubric), and one from issue #661 (the agent is handed a
      TOPAS `.inp` or a GSAS `.EXP` and asked to reproduce the fit; the
      mapping rows are the graders)
- [x] The trigger set, tier 0, with its twenty prompts reviewed by the
      maintainer before any run — written 2026-10-04
      (`tests/eval_skill/cases/trigger/`), reviewed 2026-10-06 (two changed)
- [ ] The first round: the current body on Haiku and Sonnet, N = 3, both
      arms, costed menu first; numbers to this file's handover and to
      WP-1906's `### Inherited`
- [x] Tests, `tests/test_eval_skill.py`; the suite out of the wheel
- [x] Skill: none — the suite measures the skill and adds no rule to it

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_eval_skill.py tests/test_skill.py -q
.venv/bin/python tests/eval_skill/build.py docs/skill/rietx /tmp/skill-eval && claude plugin eval /tmp/skill-eval --case fap-judge --runs 1 --ablation none --model haiku --scaffold --allow-tools Bash --trust-plugin --no-publish --json /tmp/skill-eval.json
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1904 (the strategy and the pilot); `tests/eval_skill_placement/PROTOCOL.md`
  (the episode and the rubric); `tests/CLAUDE.md` § Four eval protocols.
- `claude plugin eval` docs: <https://code.claude.com/docs/en/plugin-evals>;
  agentskills.io on evaluating skills and optimising descriptions;
  Anthropic, "Demystifying evals for AI agents" (20-50 tasks from real
  failures; read the transcripts; balance should-fire and should-not).
- Issue #661; `docs/wp/1504-eval/`.

## Handover log

### 2026-10-04 (2nd session) — the suite built and registered; nothing has run

The skill now has an eval suite that can be pointed at any body and read
against fixed rules, but no scored round has run, so it has measured nothing
yet. A plugin is built from any skill tree with one command. Three outcome
cases and twenty triggering prompts are registered, and a read-out script turns
a round's result into the protocol's numbers and applies the decision rule
between two bodies. Two things the pilot reported turn out to be unreadable as
quoted. The harness scores the same run differently in one-arm and two-arm
mode. And the CIF's starting cell passed the pilot's cell windows, so a fit
that went nowhere scored as a correct answer. Next: the maintainer reviews the
twenty trigger prompts and picks from the costed menu below. Then one fit is
timed inside the sandbox (Amendment 1.1), and then the baseline round runs on
Haiku and Sonnet.

**Done** (7 WP commits; draft PR #699):
- `build.py` with `--body`, `--python` and `--case`. It records each build in
  `build.json` with a `SKILL.md` hash and a whole-tree hash. The placement
  runner's episode recipe is now one function, `build_episode`, that both
  suites call.
- **The cases.** `fap-judge` is a regression guard, with its rubric quoted
  from the placement runner and pinned equal by test. `fap-fit` is a deciding
  case: its windows are measured, and it asks for value(esd) so the starting
  cell cannot pass. `fap-gsas-reproduce` is issue #661's mapping rows on
  FAP.EXP (cell, Rwp, the O7 z, the file's wavelengths). It is provisional
  until the first round, and each window's measurement is in its description.
- **The trigger set**, under `cases/trigger/`: ten "Should fire." and ten
  "Should not fire." prompts. Each has one `Skill` grader matching rietx by
  name, `arm: both`.
- **`PROTOCOL.md` 1.0**: read-outs R0-R5, and the decision rule's tolerance
  per case (1/4, 1/7, 1/8). Tier 0 runs one-armed with neither `--scaffold`
  nor `--allow-tools`.
- **`readout.py`**: `show` prints the read-outs and `compare` applies the
  rule. It exits 0 when the rule holds, 1 when it fails, 2 when undecided.
- **Housekeeping.** `tests/CLAUDE.md` § Four eval protocols names the suite
  (reflowed to stay under its cap). `### Inherited` was pruned on arrival:
  the pilot's four findings were folded into Context.

**Measured** (`[dev]` venv, Linux, 4 cores):
- **The windows**, by the cases lane, scripts kept only in that session's
  scratchpad. From-scratch FAP fits span a = 9.370962(82)-9.373355(75) Å and
  c = 6.885326(79)-6.887045(73) Å. GSAS's 9.371724(36) and 6.885867(37) lie
  inside that span, and `lab_bragg_brentano` lands at 9.369043(992), outside.
- **The axial term explains the GSAS gap.** Under the GSAS-mirroring plan of
  `tests/test_acceptance_fap.py`, rietx gives 9.372794(75), +114 ppm. With
  the axial term held at 0, as GSAS's asym is, it gives 9.371721(78), −0 ppm.
  The test's docstring attributes the gap to a d-scale convention instead.
  Offered as a separate task, not filed in a WP.
- **The harness's score is not comparable across ablation modes.** The
  pilot's `fap-fit` scored 1 of 7 two-arm and 2 of 8 under `--ablation none`
  for the same state. `readout.py` rescores every run over the graders a
  two-arm round keeps, and equals the harness on all 12 two-arm pilot runs.
- **Tests.** `tests/test_eval_skill.py` adds 97 fast tests and 1 slow one,
  27 test functions in all, 0.40 s together by `tests.added_test_times`; none
  joins the slow tail. One fast run (`-n auto`, alone on the machine, 26:32)
  gave 3 failed, 8245 passed and 172 skipped, 8420 in all.
  - Two failures were this branch's and are fixed. A trigger prompt named a
    TiO₂ polymorph that is also the package's reserved old name, which
    `test_no_stale_name` refuses anywhere outside its allowlist, so
    `fire-tio2-fractions` became `fire-caco3-fractions`. And 17 text I/O
    calls lacked `encoding=`, caught by `test_portability`.
  - The third, `test_merge_replay`'s conflict test, is the container's.
    Git 2.43 has no `merge-file --diff-algorithm`, and the test fails alone
    with nothing of this branch in it.
  - The fixed files re-run green (141 tests across the four affected files).
    So this tree's fast selection is 8247 passed, 172 skipped and that one
    environmental failure.
  - Main's count was not measured, so the delta of 97 is the new file's
    collection, not a difference of two runs. No full suite ran, as the
    branch is test- and docs-only.
- **Lanes** (`session_usage.py lanes`). This session's peak context was 282K.

| lane | est | requests | main at dispatch | re-read | main requests | left in main | main edits after | redo | lane $ | in-session $ | saved $ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cases | 35 | 56 | 208K | 0K of 0K | 6 | 19K | 1 | 0 | 3.52 | 6.30 | +2.19 |
| protocol | 30 | 55 | 239K | 6K of 23K | 16 | 34K | 6 | 0 | 3.36 | 5.71 | +1.04 |

  Two items were kept. `build` (~25) was decided at 138K, under the line, and
  `trigger` (~12, actual 5) at 229K. Actual over estimated requests was 1.60.
  The trial row is in `process.md`, saving +$3.23, 19 % of the session. The
  replay over this container's two sessions has the selective policy laning
  0 items for +0 %, because neither session's history meets its threshold.

**Gotchas:**
- **Branch and worktree.** This is a cloud container on the designated branch
  `claude/rietx-skill-evaluation-uhvtob`. Moving that local branch to main
  after #698 merged was refused as destructive. So the work sits in worktree
  `wp1905-skill-eval-suite` and is pushed with
  `git push origin HEAD:claude/rietx-skill-evaluation-uhvtob`, a
  fast-forward.
- **No round can run from this container as configured.** The auto-mode
  classifier refused even `claude --version`. The first round needs a
  machine where the CLI may run, with `bubblewrap` and `socat`, and an
  interpreter outside `$HOME`.
- **`readout.py` was written before any trace was kept.** It assumes the
  Claude Code transcript shape, and PROTOCOL § Assumptions lists five checks
  for the first kept trace.
- **Two review findings were declined.** First, a run whose trace is missing
  still counts toward N. The protocol makes `--keep-temp` mandatory and
  `show` lists the missing traces, but the code does not refuse such runs.
  Second, tier 0's "of 30" counts void and errored runs. Both are worth an
  amendment if the first round meets either.
- **PROTOCOL 1.0 was edited after registration but before any run.** The
  tier-0 grants and the grader's rietx match changed. After the first run,
  any change is a dated amendment.
- **`fap-gsas-reproduce` can be gamed.** An answer that copies FAP.EXP's own
  numbers passes all four value graders. Only `ran_fit` and
  `file_wavelengths` stand against it.

**The costed menu** (pilot prices, WP-1904; nothing here is authorised):

| item | runs | estimate | suggested `--max-cost-usd` |
|---|---|---|---|
| A. Amendment 1.1: one `fap-fit` run in the sandbox, alone, Haiku | 1 | ~$0.30 | 1 |
| B. `--tag fap`, today's body, two-arm, Haiku | 18 | ~$4.1 | 8 |
| C. `--tag fap`, today's body, two-arm, Sonnet | 18 | ~$3.6-8.5 | 15 |
| D. tier 0, Haiku, after the prompt review | 60 | $2-6 (Hypothesis: unmeasured) | 6 |
| E. tier 0, Sonnet, after the prompt review | 60 | $3-8 (Hypothesis: unmeasured) | 10 |

Next, in order:
1. The maintainer reviews the twenty prompts and picks from the menu.
2. Item A, then set both fit cases' `timeout_seconds` as Amendment 1.1.
3. Items B and C at `-j 1`, one at a time. Check § Assumptions on the
   first kept trace before quoting anything.
4. The numbers go here, and the baseline goes to WP-1906's `### Inherited`.
5. Tier 0 runs last.

- **2026-10-04** — created by WP-1904's session, from its pilot. No open WP
  owns a skill eval: 1338's placement round is closed and its runner refuses
  today's body; 1504's round measures the figure surface, not the skill text.
  Next: `build.py` and the protocol, then the costed menu.
