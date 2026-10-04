# WP-1905 — the skill eval suite: `claude plugin eval` over the skill tree, cases from real failures, judge-free first

Milestone: unscheduled · Status: ⬜
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
  current body and WP-1904's prototype; its numbers and the four findings
  that decide this protocol are the `### Inherited` entry below, and the
  cases themselves are in `docs/wp/1904-eval/pilot/`.
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

### Inherited

- **From WP-1904 (2026-10-04), the pilot this suite grows from.** Four
  findings decide the protocol. (1) `fap-judge` is a ceiling on Sonnet: 4 of
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
  both arms; Sonnet $0.14-0.18 (judge) and $0.23-0.62 (fit) a run. The two
  cases, their graders, the build script and every result JSON are in
  `docs/wp/1904-eval/pilot/`.

## Non-goals

- The rewrite itself: WP-1906 (judged by this suite).
- Running the suite in CI on every PR: WP-1907 schedules the judge-free tier
  nightly once the suite is stable.
- A leaderboard, a published benchmark, or any case on data without a
  peer-reviewed or public citation.

## Tasks

- [ ] `tests/eval_skill/build.py`: a plugin directory from a skill tree and
      the case set; `test_eval_skill.py` pins that every case's fixture
      exists, every grader file parses, and `PROTOCOL.md` quotes each prompt
- [ ] `PROTOCOL.md`, registered before the first scored round: the question,
      the conditions, the models, N, the read-outs and the decision rule above
- [ ] The three cases: `fap-judge` (from the placement round), `fap-fit`
      (from scratch: cell in `report.md` by regex, a fit run by `tool_used`,
      the caveat by rubric), and one from issue #661 (the agent is handed a
      TOPAS `.inp` or a GSAS `.EXP` and asked to reproduce the fit; the
      mapping rows are the graders)
- [ ] The trigger set, tier 0, with its twenty prompts reviewed by the
      maintainer before any run
- [ ] The first round: the current body on Haiku and Sonnet, N = 3, both
      arms, costed menu first; numbers to this file's handover and to
      WP-1906's `### Inherited`
- [ ] Tests, `tests/test_eval_skill.py`; the suite out of the wheel
- [ ] Skill: none — the suite measures the skill and adds no rule to it

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_eval_skill.py tests/test_skill.py -q
.venv/bin/python tests/eval_skill/build.py docs/skill/rietx /tmp/skill-eval && claude plugin eval /tmp/skill-eval --case fap-judge --runs 1 --ablation none --model haiku --scaffold --allow-tools Bash --trust-plugin --no-publish --json /tmp/skill-eval.json
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1904 (the strategy and the pilot); `tests/eval_skill_placement/PROTOCOL.md`
  (the episode and the rubric); `tests/CLAUDE.md` § Three eval protocols.
- `claude plugin eval` docs: <https://code.claude.com/docs/en/plugin-evals>;
  agentskills.io on evaluating skills and optimising descriptions;
  Anthropic, "Demystifying evals for AI agents" (20-50 tasks from real
  failures; read the transcripts; balance should-fire and should-not).
- Issue #661; `docs/wp/1504-eval/`.

## Handover log

- **2026-10-04** — created by WP-1904's session, from its pilot. No open WP
  owns a skill eval: 1338's placement round is closed and its runner refuses
  today's body; 1504's round measures the figure surface, not the skill text.
  Next: `build.py` and the protocol, then the costed menu.
