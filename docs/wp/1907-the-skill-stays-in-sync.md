# WP-1907 — the skill stays in sync: constants and formulas pinned to the package, a changed-surface check at review, the judge-free tier nightly

Milestone: unscheduled · Status: 🔄 2026-10-07 — claimed by @yue-here
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
  example, and no test could see it. *(Superseded in part 2026-10-07: WP-1906's
  rewrite fixed the width seed — SKILL.md §1 now gives Γ_G² = U·tan²θ + V·tanθ
  + W and `W ≈ (0.6·H)²` — and `PLAN_INFO["lab_bragg_brentano"]` no longer
  recommends what rule 6 forbids. The class is unguarded still.)* The manual solves this class with MyST
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
- **One sync mechanism is already in place** (WP-1906). The body's worked
  default (§10) is held line for line equal to `examples/skill_worked_default.py`
  by `test_the_worked_default_is_the_example_that_runs`, and
  `tests/test_examples.py` runs that script. A recommendation in package text
  (`PLAN_INFO.when_to_use`) is a constant the claims check can pin too.
- **What "the judge-free tier" is** (WP-1905). The harness filters cases by
  tag, so tier 0 is `--tag trigger --ablation none` with neither `--scaffold`
  nor `--allow-tools`: twenty one-grader cases, no fixture, no fit, no shell
  (`tests/eval_skill/PROTOCOL.md` § Tier 0). The fit cases need a sandbox
  backend and minutes a run, so they are not nightly material. A CI job needs
  a Claude Code install (≥ 2.1.289) and credentials, and `readout.py show`
  reports the fire and quiet rates a floor is set on. Rounds D and E (N = 3):
  Haiku fired 26/30 and stayed quiet 30/30 at $1.91 and 14 min; all four
  misses are prompts naming a file tier 0 does not provide, so scaffold an
  empty file per name (a dated amendment) before a floor is set on Haiku's
  fire rate. `readout.py`'s `LEAK` lines are not floor material. Linux CI
  needs only an interpreter outside the home directory.

## Non-goals

- Prose semantics: whether a rule is still *good advice* is WP-1905's suite,
  not a test.
- The references' size caps: `tests/skill_caps.py`, unchanged.

## Tasks

- [x] A claims pass: every numeric constant and formula the body quotes is
      either rendered by `docs/skill/make_api_index.py`'s machinery from the
      package (a substitution table, committed output) or asserted by a test
      against the attribute it quotes; the width formula fixed by it
- [x] A changed-surface step in CI's lint job: the public names, plan names,
      diagnostic codes and `help.py` keys a PR changes, crossed against the
      skill tree's mentions, printed as the rows to re-read; failing only on a
      name that vanished
- [x] ~~`nightly.yml`~~ `skill-eval.yml`, on demand (re-scoped 2026-10-07 by
      the maintainer: a subscription, no API credits, so no nightly spend):
      WP-1905's judge-free tier, Haiku or Sonnet, `--max-cost-usd` set, floors
      in `floors.json` under PROTOCOL.md § Floors; `model-watch.yml` opens an
      issue weekly when the models page lists a new Haiku or Sonnet ID
- [x] `(Measured: …)` tags name their WP; a test reads each against the index
- [x] Tests for each of the above
- [x] Skill: none — this WP guards the skill and adds no rule to it (two
      body rules corrected to what the package does, rules 7 and 14)

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
