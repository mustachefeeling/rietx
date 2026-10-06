# WP-1907 — the skill stays in sync: constants and formulas pinned to the package, a changed-surface check at review, the judge-free tier nightly

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1905 soft (the nightly tier is its suite)
Priority: P3 2026-10-04 — a wrong number in the skill is a wrong turn an agent takes with the docstrings there to recover from; P2 if a stale constant is found to have cost a user a fit

## Goal

A change to the package that moves what the skill states fails a test or a
CI job naming the skill row, the way a renamed dot-path already does; and the
skill's numbers are rendered from the package rather than typed.

## Context

- **What is pinned today, and what is not.** `tests/test_skill.py` walks
  every dotted name in every skill file against the installed package (234
  names), pins the generated `api*.md` byte for byte, and
  `tests/test_docs_consistency.py` holds every diagnostic code and every
  `help.py` vocabulary member to a row somewhere in the tree. **Nothing pins
  a value or a formula.** WP-1904 checked the body's by hand: the plan list
  omits `magnetic_width` (a routing choice, fine); `RIVAL_DECISIVE_MIN_CHI2_RATIO`,
  the `W` default and the three verbs it names resolve; the width seed
  `W ≈ (FWHM/2)²` contradicts the package's Caglioti form and the body's own
  example, and no test could see it. The manual solves this class with MyST
  substitutions injected from the live package in `conf.py`
  (`tests/test_manual.py`); the skill is plain Markdown shipped in the wheel,
  so the equivalent is a **generated-and-committed** pass, as `api.md` is.
- **How the skill drifts.** 114 commits touched the skill tree since
  2026-06-01, 73 of them in changes that also touched `src/`; of the 24 commit
  subjects naming the skill since August, two record stale skill text found
  at review (WP-1523, WP-1541). The sessions that find it are the ones that
  read the skill while changing the surface it describes, so the gate belongs
  at review: a PR that changes a public name, a plan, a `help.py` entry, a
  diagnostic code or a schema default prints the skill rows that quote it.
- **Model drift is the other half.** A body tuned on today's models is
  measured again when the models move; the judge-free tier of WP-1905's suite
  on Haiku is cheap enough to run nightly beside the `nightly.yml` full job
  and to fail on a case that drops below its recorded floor.
- **Evidence tags age.** `(Measured: …)` rows (96 of them, 10 `Hypothesis`)
  carry no commit or date, so a measurement that a later WP overturned reads
  as current. A tag that names the WP that measured it can be checked
  against the WP index for a later WP that cites and supersedes it.

### Inherited

- **From WP-1905 (2026-10-04), what "the judge-free tier" is.** The harness
  filters cases by tag, not grader type, so the judge-free run is
  `--tag trigger --ablation none` with neither `--scaffold` nor
  `--allow-tools`: twenty one-grader cases, no fixture, no fit, no shell
  (`tests/eval_skill/PROTOCOL.md` § Tier 0). The fit cases carry an `llm`
  grader and need a sandbox backend (`bubblewrap`, `socat`) and minutes per
  run, so they are not nightly material as they stand. A CI job also needs a
  Claude Code install and credentials in the environment, and
  `readout.py show` reports the fire and quiet rates a floor would be set on.
- **From WP-1905 (2026-10-06), tier 0's first numbers, and the fixture it
  needs first.** The twenty prompts were reviewed and ran at N = 3
  (`tests/eval_skill/PROTOCOL.md` § Rounds D and E). Haiku fired 26 of 30 and
  stayed quiet 30 of 30, at $1.91 and 14 min a round. Sonnet fired 30 of 30
  and stayed quiet 27 of 30, at $4.58. All four of Haiku's misses are the
  instrument's. Each prompt names a file tier 0 does not provide, the agent
  asks for it before any fit, and the skill never loads. So scaffold an empty
  file per name a prompt gives (a dated amendment) before a nightly floor is
  set on Haiku's fire rate. Two more things for the job. `readout.py`'s
  `LEAK` lines read JSON pointers in written content and the run's own `/tmp`
  as paths, so a floor must not be set on them. And on macOS the sandbox
  denies `/Users` and `/tmp`; Linux CI is the pilot's case and needs only an
  interpreter outside the home directory.

## Non-goals

- Prose semantics: whether a rule is still *good advice* is WP-1905's suite,
  not a test.
- The references' size caps: `tests/skill_caps.py`, unchanged.

## Tasks

- [ ] A claims pass: every numeric constant and formula the body quotes is
      either rendered by `docs/skill/make_api_index.py`'s machinery from the
      package (a substitution table, committed output) or asserted by a test
      against the attribute it quotes; the width formula fixed by it
- [ ] A changed-surface step in CI's lint job: the public names, plan names,
      diagnostic codes and `help.py` keys a PR changes, crossed against the
      skill tree's mentions, printed as the rows to re-read; failing only on a
      name that vanished
- [ ] `nightly.yml`: WP-1905's judge-free tier on Haiku, `--max-cost-usd`
      set, the floor per case recorded in `PROTOCOL.md`
- [ ] `(Measured: …)` tags name their WP; a test reads each against the index
- [ ] Tests for each of the above
- [ ] Skill: none — this WP guards the skill and adds no rule to it

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_skill.py tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1904 (the by-hand claims check and the churn numbers); `tests/test_skill.py`;
  `tests/test_manual.py` (the substitution pattern); `docs/skill/make_api_index.py`.

## Handover log

- **2026-10-04** — created by WP-1904's session. No open WP owns skill drift:
  1338's gates are names and bytes, 1507 is the WP index. Next: the claims
  pass, since it fixes a wrong formula on the way.
