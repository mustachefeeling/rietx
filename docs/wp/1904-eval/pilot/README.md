# The WP-1904 pilot: `claude plugin eval` over the skill tree

What ran on 2026-10-04, kept so WP-1905 can start from it rather than from
the WP's prose. Nothing here is a registered protocol; WP-1905 registers one.

- `evals/`: the two cases as `claude plugin eval` reads them. `fap-judge` is
  the placement round's episode (`tests/eval_skill_placement/`: its prompt and
  its four rubric items verbatim as `llm` graders); `fap-fit` is a refinement
  from scratch with the cell graded by regex on `report.md` and the caveat by
  rubric. Each `fixture.sh` copies the episode files from `$EPISODE`, a
  directory holding `FAP.XRA`, `fluorapatite.cif`, `fit.py`
  (`colleague_fit.py`) and `fit_output.txt` (its printed output). Each
  `prompt.md` names this container's interpreter,
  `/home/user/rietx/.venv/bin/python`; substitute both paths before running,
  or the `ran_fit` grader fails on a machine where that path is dead.
- A plugin is built from a skill tree as `build_pilot.py` does: the tree
  copied to `<plugin>/skills/rietx/`, a `.claude-plugin/plugin.json`, and
  `evals/` beside it. The run was
  `claude plugin eval <plugin> --scaffold --allow-tools Bash Write
  --trust-plugin --no-publish --keep-temp --json <out>.json`, with `--runs`,
  `--model`, `--judge-model sonnet` and `--max-cost-usd` per round, and
  `--ablation none` on the second body so the no-skill arm is not repeated.
  The sandbox backend (`bubblewrap`, `socat`) had to be installed first.
- `*.json`: the harness's `aggregate-result` files for each round, the
  numbers WP-1904's handover quotes.
- `../SKILL.compressed.txt`: the prototype body the Sonnet round compared
  against the current one. A measurement of the direction, not the rewrite.
