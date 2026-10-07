# WP-1907 — the skill stays in sync: constants and formulas pinned to the package, a changed-surface check at review, the judge-free tier nightly

Milestone: unscheduled · Status: ✅ 2026-10-07 — the body's numbers checked against the package, a changed-surface report in CI, evidence tags read against the index, tier 0 on demand with a weekly model watch
Track: The repo's own process
Depends on: 1905 soft (the nightly tier is its suite)

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
  (`tests/eval_skill/PROTOCOL.md` § Tier 0). Amendment 1.2 since adds
  `--scaffold`, for the empty files the prompts name. The fit cases need a sandbox
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

- **2026-10-07** — closed in one session, under the lane trial. The skill
  body's numbers and formulas are now checked against the package, so a
  changed default or a reordered ratio fails a test that names the row. The
  first pass found two rules that were wrong. Rule 14 read `chi2_ratio` as
  loser over winner, but the package orders it held over partner, so an agent
  whose held parameter won would have called a settled pair unresolved. Rule 7
  said "0.98 or more" for a guard that fires strictly above. A pull request now
  prints the skill rows that quote any public name, plan, diagnostic code or
  help key it touches, and fails only when it removes a name the skill still
  uses. An evidence tag must name a WP in the index, and the tag must also name
  any WP that later superseded it. The model-drift check runs on demand, since
  the maintainer has a subscription and no API credits. A weekly job opens an
  issue when the models page lists a new Haiku or Sonnet ID.

  *Done.* `tests/test_skill_claims.py`: sixteen claims, each checked against
  the package attribute it quotes, and six numbers declared not to be claims,
  each with its reason. Any other number in the body fails. `tests/skill_surface.py`
  runs in CI's lint job, and `_engine_codes` now shares its AST walk. The
  evidence-tag gate is in `test_skill.py`. `.github/workflows/skill-eval.yml`
  runs tier 0 on Haiku or Sonnet, using `CLAUDE_CODE_OAUTH_TOKEN` or
  `ANTHROPIC_API_KEY`, and stops green when neither is set.
  `.github/workflows/model-watch.yml` reads the models page and checks it
  against `tests/eval_skill/models_seen.txt`. PROTOCOL.md gained § Floors and
  Amendment 1.2: nine trigger cases now start with an empty file of the name
  their prompt gives, through a new `empty` verb in `build.py`. `floors.json`
  is empty. Inherited was pruned on arrival and folded into Context. WP-1906
  had already fixed the width seed and `PLAN_INFO`'s `lab_bragg_brentano`
  text, and the Context paragraph says so. Item 3 was re-scoped from nightly
  to on demand at the maintainer's word.

  *Measured.* The fast suite on the `[dev]` venv, macOS arm64, alone on the
  machine: 8654 passed, 167 skipped, 3 failed. Two failures were the committed
  skill copies, which were re-synced afterwards and pass. The third is
  `test_backend_shim[toy_anomalous]`, which fails on bare `main` (#760,
  WP-1905's log). The branch adds 94 cases in 24 functions, 5.97 s in total.
  The slowest is the tag-to-index check, at 2.66 s over 16 cases. Main was not
  re-measured, so the +94 is the added count, not a measured delta. The full
  suite did not run: no `src/` changed. The lane measurement:

  | lane | est | requests | main at dispatch | re-read | main requests | left in main | saved $ |
  |---|---|---|---|---|---|---|---|
  | changed-surface | 25 | 21 | 164K | 0K | 5 | 14K | +0.23 |
  | eval-on-demand | 30 | 41 | 200K | 0K of 5K | 8 | 20K | +0.54 |

  The trial row saved +$0.78, 8 % of the session. The tool printed kept 0 and
  fixed 0. The true figures are 2 kept, and 1 lane fixed by a Python rewrite
  that the tool does not count; WP-1903's Inherited has both. In the replay,
  the selective policy saves 21 % across 73 sessions.

  *Review.* `/code-review high --fix` reported nine findings and fixed six:
  - a renamed file's names are now read at the base (`--no-renames`);
  - the changed-line diff is limited to `src/rietx/*.py`, so a GUI rebuild no
    longer floods it;
  - a model ID needs a version digit;
  - the eval workflow's token is read-only;
  - a WP that is ⬜ or 🛑 supersedes nothing;
  - two stale doc lines.
  This session fixed a seventh: a run with no score now counts against no
  floor. Two were declined. Word-like names in src comments still count as
  touched, because telling a comment from code on a partial diff line needs a
  redesign, and the step only reports. `tier0_rates` still counts
  `score == 1` while the floors count `passed`, two definitions that agree on
  a one-grader case.

  *Gotchas.* The claims pass covers the body only, and the numbers in the
  references are not classified. That is deliberate: the references carry
  measurements, which the tag gate dates. The 29 corpus-tagged rows name a
  campaign rather than a WP, as the corpus rule asks. The Context paragraph
  counted 96 tags. The gate's grammar finds 46 closing tags, in four files.
  `fire-judge-calibration` names no file, so it gets none, and two of Round
  D's four Haiku misses stay unexplained. `claude plugin eval` has not yet run
  with an OAuth token.

  *Next.* First, the maintainer runs `claude setup-token` and stores the
  result as the repository secret `CLAUDE_CODE_OAUTH_TOKEN`. Then they
  dispatch skill-eval on Haiku. That first run shows whether the harness
  accepts the token, and its dated § Results entry sets the floors. The margin
  each floor sits below the run's passes is still to be decided. After that,
  dispatch it when model-watch opens an issue, and add the new IDs to
  `models_seen.txt`.

- **2026-10-04** — created by WP-1904's session. No open WP owns skill drift:
  1338's gates are names and bytes, 1507 is the WP index. Next: the claims
  pass, since it fixes a wrong formula on the way.
