# WP-1506 — a planning-doc PR runs the tests that read it, and CI gates on one check

Milestone: unscheduled · Status: ✅ 2026-10-09 — the docs-only skip and `ci-ok` live since 2026-09-27; the CI-time cut (task 7) moved to 1547
Track: The repo's own process
Depends on: — (the branch-protection change is the maintainer's, by hand)

## Goal

A PR that changes only planning documents reports green in about two minutes,
after running the tests that read those documents. Every code PR records its
per-test timings, so the next cut to CI time is chosen from numbers.

## Context

**The regression.** WP-1002 (2026-07-29, commit 2e6e89b6) gave `ci.yml` a
`paths-ignore` list for planning docs. WP-1003 (2026-08-16, commit 1a77e293)
removed it at the visibility flip. The fast jobs had become branch-protection
required checks, and a workflow skipped by a path filter never reports them,
so a docs-only PR could not have merged. Nothing replaced the skip. Every
planning-doc PR has run the whole matrix since, once when readied and again
on main after the merge.

**Measured 2026-09-27.** Merged PRs from 2026-08-27 to 2026-09-27, each read
as `git diff --name-only <merge>^1 <merge>` over origin/main's first parent:

- 232 PRs merged. 49 changed only files under `docs/wp/`, `docs/milestones/`,
  `docs/releases/`, `docs/ROADMAP.md`, `docs/DESIGN.md` and
  `tests/test_docs_consistency.py`. Adding the CLAUDE.md files and the skill
  copies makes 53. Tests read those four extra (`test_skill.py`, the manual
  build), so they stay on the code side.
- A readied PR runs 6 jobs. Wall time was 20-22 min over the last ten
  non-draft runs. Runner queue wait was 2-46 s, so GitHub Free's limit of 20
  concurrent jobs did not bind.
- The fast legs took 12-21 min each. On one commit (run 36303484975) py3.14
  took 12:03 and py3.11 20:12. Install steps took 1-3 s, so the uv cache
  works. Collection takes 1.6 s locally. The time is the tests.
- Locally the fast selection is 1 372 worker-seconds (junit `time` with
  `-o junit_duration_report=total`, 10-core Mac, another session running,
  2:40 wall). The 50 slowest tests take 52% of it. The 6 434 tests under 1 s
  take 26%. The longest xdist group is 82 s (`indexing-ceiling`), so no group
  sets the wall clock.
- For scale: WP-1002 measured the fast leg at about 3 min on 2026-07-29,
  and WP-1003 put the jax leg at about 10 min on 2026-08-16.

**Why the fix needs a summary check.** `ci.yml`'s header (commit 44847142)
records two facts. A job skipped by a job-level `if` reports success. A
skipped *matrix* job does not expand: it reports once, under the literal name
`fast py${{ matrix.python }}`. The required contexts on 2026-09-27 are
`lint`, `fast py3.11` to `fast py3.14` and `fast jax`, with `strict: false`
(`gh api repos/yue-here/rietx/branches/main/protection`). Skipping those jobs
on a docs PR would leave four required contexts that never appear, and the
PR could not merge.

The standard answer is one summary job. It `needs:` every gating job, runs
`if: always()`, and fails when any needed job failed or was cancelled. Branch
protection then requires `lint` and that job only. `re-actors/alls-green`
packages this with an `allowed-skips` input; a short shell step over
`toJSON(needs)` does the same. Once only the summary is required, the matrix
can be sharded or trimmed without touching branch protection again.

**Which tests read the planning docs is measured, not grepped.** A text
search for `ROADMAP|docs/wp|milestones|releases|DESIGN.md` hits 16 test files,
most of them in comments. An audit hook (`sys.addaudithook`, event `open`,
in a throwaway plugin) over one fast run lists the test files that open a
path in the planning set. That list is the docs job's selection. Expect
`test_docs_consistency.py`, `test_no_stale_name.py` and
`test_workflow_hooks.py` among them.

**The draft guard stays.** A draft PR runs lint alone, and `gh pr ready`
fires the gating run. The summary job has to pass a matrix skipped because
the PR is a draft. That is safe because a draft cannot merge.

**The fast tier grows by its tail.** Half the time is 50 tests. The repo
forbids a wall-clock assertion in a test (tests/CLAUDE.md § Budgets in
tests), so the guard is a report. The fast jobs upload junit timings, and
`/wp-handover` reads the rows for tests the branch added. Named members of
the tail today, in local serial seconds:

- Two tests in `test_magnetic_isotropy.py` each compute `isotropy.analyse` on
  F m -3 m: 26 s alone, about 70 s under suite load. This is folded into
  [1418](1418-the-magnetic-structure-is-determined.md)'s Inherited, since
  that WP owns the function.
- The 230-group and every-setting sweeps take 128 s together (9%).
  `test_the_sweep_over_the_230_settings_at_gamma` takes 44 s. Three
  230-group tests in `test_magnetic_irreps.py` take 67 s. And
  `test_symmetry_orbits.py::test_the_invariant_holds_across_every_setting_gemmi_knows`
  takes 17 s. A sample could stay in the fast tier with the whole sweep
  nightly. A break in an unsampled group would then show the next morning,
  and the WP states that trade rather than assuming it. Choose the sample by
  trap, never at random: 79 of gemmi's 564 settings were once served wrong
  under a correct count (root CLAUDE.md, cell ties).

**Considered and not taken:**

- A merge queue. GitHub offers it only on organization-owned repos, and
  yue-here/rietx belongs to a personal account. Moving the repo to a free
  organization would make it available.
- Larger runners. They need a Team or Enterprise organization plan and are
  always billed per minute.
- A self-hosted runner. GitHub advises against one on a public repo, since a
  fork's PR can run code on it, and contributors work from forks.
- Workflow-level path filters. WP-1003 removed them for the reason above.

## Non-goals

- The GUI dist and its write path to main: WP-1313. Its branch-protection
  change and this one are both the maintainer's, by hand, and are cheapest
  done in one sitting.
- Why `isotropy.analyse` is slow: WP-1418.
- The nightly's length: 1:40 for the Linux full suite on 2026-09-26, most of
  it indexing-acceptance fixture setup.
- The ROADMAP and cap conflicts: WP-1507.

## Tasks

- [x] Measure which test files open a planning-set path, with the audit hook
      over one fast run. Record the planning set and the list in `ci.yml`,
      beside the jobs that use them.
- [x] `ci.yml`: a `changes` job, using `git diff --name-only` against the PR
      base, or against `github.event.before` on a push. Add a `docs` job
      running the measured list, gate the matrix jobs on `changes`, and add
      the `ci-ok` summary job. In this commit the matrix still runs on every
      PR, so nothing is skipped while protection still names the matrix.
- [x] By hand, maintainer: branch protection requires `lint` and `ci-ok`.
      This WP carries the written instruction, as WP-1313 does. Done
      2026-09-27, after PR #504 merged.
- [x] Turn the skip on. Check a planning-only PR (`ci-ok` green in about two
      minutes) and a code PR (`ci-ok` waits for every leg). Make one leg fail
      on purpose once and confirm `ci-ok` goes red (tests/CLAUDE.md § Guards
      that go quiet instead of red).
- [x] ~~Main pushes: a planning-only merge skips the matrix the same way.~~
      Not taken, 2026-09-27. `ci.yml` cancels a run when the next push to
      its ref arrives. 51 of main's 240 runs in the month to 2026-09-27 were
      cancelled that way. A docs-only merge that skipped the matrix would then
      leave the cancelled code merge untested. Nobody waits on a main run, so
      the skip there would save runner minutes only.
- [x] The fast jobs upload their junit timings (`--junitxml`,
      `-o junit_duration_report=total`). `/wp-handover` reads the rows for
      the tests the branch added. The rule goes in tests/CLAUDE.md § Budgets
      in tests.
- [x] ~~From two weeks of those timings, choose the next cut and record its
      numbers. The options are sampling the named sweeps, sharding, or fewer
      Pythons on a PR. Sharding must keep each `xdist_group` whole. Five legs
      times N shards meets the 20-job limit when two PRs are readied
      together, so sharding probably comes with a smaller PR matrix.~~ Moved to
      [1547](1547-the-fast-tiers-tail.md) on 2026-10-09, with the timings
      measured there.
- [x] tests/CLAUDE.md § CI and `ci.yml`'s header say what gates now.
- [x] Skill: none. This changes how the repo is tested, not how rietx is
      driven.

## By hand: branch protection

The maintainer makes this change once, by hand. It replaces the five matrix
contexts with `ci-ok` and keeps `lint`. App 15368 is GitHub Actions, and
naming it stops another app's status from satisfying the check.

```sh
gh api -X PATCH repos/yue-here/rietx/branches/main/protection/required_status_checks \
  --input - <<'EOF'
{"strict": false, "checks": [{"context": "lint", "app_id": 15368},
                             {"context": "ci-ok", "app_id": 15368}]}
EOF
```

In the web UI it is Settings → Branches → `main` → "Require status checks to
pass": remove the four `fast py3.x` rows and `fast jax`, then add `ci-ok`.

Do it in the same sitting as the merge that turns the skip on, in either
order. Between the two acts a docs-only PR waits for contexts that never
report, and nothing else is harmed. After the change, an open PR whose
branch predates `ci-ok` reports no such check. It can merge once `main` is
merged into it.

## Acceptance

- A PR touching only `docs/wp/**` shows `ci-ok` green within about two
  minutes, with the docs job's tests run and passed.
- A PR touching `src/` shows `ci-ok` pending until every leg finishes, and
  red when a leg fails (checked once on purpose).
- The required contexts are `lint` and `ci-ok`:

```sh
gh api repos/yue-here/rietx/branches/main/protection --jq .required_status_checks.contexts
gh run list --workflow ci.yml --limit 10 --json headBranch,conclusion,createdAt,updatedAt
.venv/bin/python -m pytest tests/test_docs_consistency.py
```

## References

- docs.github.com: "Troubleshooting required status checks" (a skipped job
  reports success, a filtered workflow reports nothing); "Managing a merge
  queue" (organization-owned repos only); "Larger runners" (Team and
  Enterprise plans only).
- `re-actors/alls-green`, a GitHub Action for the summary job.
- Commits 2e6e89b6 (WP-1002's `paths-ignore`), 1a77e293 (WP-1003 removed
  it), f147e0ea and 44847142 (the draft guard, and what a skipped matrix
  reports).

## Handover log

### 2026-10-09 — closed: the CI-time cut moved to 1547

This WP did what its title says. A PR changing only planning documents has
gone green in about two minutes since 2026-09-27, and branch protection
gates on `lint` and `ci-ok`. The cut to CI time it was waiting two weeks of
timings for is now WP-1547. Those timings showed a bigger problem than a
trim: the median fast leg rose from 21.7 to 31.1 min in the week to
2026-10-09, mostly from three files.

*Done.* Task 7 struck through and pointed at 1547. The Inherited section
was consumed. The WP-1519 note about the probe line pasted into three
nightly legs is still open, so it moved to 1547's Context, since 1547's last
task may reshape the nightly. The WinError 206 note was already fixed by
WP-1541. The 1547 note was the move itself. No WP's Priority moved: 1507
depends on this one softly, through the docs job, and that job is live.

*Next.* Nothing here. The CI-time work is 1547's.

### 2026-10-06 — the planning set takes the session machinery

PR #798 changed only `.claude/commands/pr-review.md` and a comment in
`.claude/hooks/session_start.py`, and it ran the full matrix, because
nothing under `.claude/` was in the planning set. The maintainer asked for
the set to cover that kind of change.

Measured as task 1 was, over one fast run on main `443c0c1a` (macOS arm64,
`[dev,jax]`, 8523 passed, 103 skipped, 2 failed, both known on main). The
audit hook was loaded through a temporary `.pth` file, because Homebrew's
Python already ships a `sitecustomize`. It logged every open, listing and
`git grep` under `.claude/`, tagged with the running test:

- The four commands, `agents/pr-conformance.md`, the issue-review skill and
  `settings.json` are opened by no test. `test_no_stale_name`'s `git grep`
  reads them as it reads every tracked file.
- `handover_owed`, `no_top_level_cd`, `session_start`, `worktree_create`,
  `worktree_only`, `worktree_remove` and `wp_claim` are imported or run only
  by `test_workflow_hooks`.
- Three paths stay code:
  - `session_usage.py`, which `test_session_usage` imports;
  - `wp_index.py`, which `test_merge_replay` runs as a script;
  - `skills/rietx/`, the shipped skill, which `test_skill_cli` reads.
- The audit hook misses a script started as a program, because the
  interpreter loads it without an audited open. A text search over `tests/`
  for every file name above covered that gap, and it is how `wp_index.py`'s
  second reader was found.
- Ten unrelated test files logged an `os.listdir` of `.claude/hooks`. That
  is the import system listing a `sys.path` entry that `test_workflow_hooks`
  added in the same worker, not a read.

`ci.yml`'s pattern now names those paths, and a hook not listed by name
stays code. `tests/CLAUDE.md` § CI says the same. Checked against sample
file lists with the pattern applied as the `changes` job applies it. #798's
two files route to docs, and each of the three code paths, a new hook and
`settings.local.json` route to code. This PR edits `ci.yml`, so it runs the
full matrix itself. Task 7, the cut from two weeks of timings, is untouched.

### 2026-09-27 (2nd session, after the merge) — the skip is live

The maintainer merged PR #504 at 13:55 UTC and moved branch protection to
`lint` and `ci-ok`. The protection endpoint now returns `["lint","ci-ok"]`.
The merge's own run on main took the code path: `changes` chose code, the
docs job skipped and the full matrix ran. The PR carrying this entry changes
only this file, so it is the first docs-only PR under the new protection.
Its first run (36324259032) went green 47 s after it was created, with the
matrix skipped, and GitHub reported the PR mergeable (`CLEAN`).

*Open.* #450's branch predates `ci-ok`, so it waits on that check until
main is merged into it. Task 7 waits for two weeks of timings, from about
2026-10-11.

### 2026-09-27 (2nd session) — the docs-only skip, written and checked live

A PR that changes only planning documents can now report green in under two
minutes. Before this it waited 20 minutes. It runs the four test files that
read those documents, and one summary check says whether the suite chosen for
the PR passed. Two throwaway PRs against this branch showed both halves. The
docs-only one went green in 79 s. The one with a failing leg waited for every
leg and then went red. Nothing changes for anyone until the maintainer merges
PR #504 and swaps the five matrix contexts in branch protection for `ci-ok`.
Pushes to main still run the whole matrix. A skip there would leave a
cancelled code run untested, and that happens often.

*Done.*

- The audit hook. A `sitecustomize.py` on `PYTHONPATH` chained to Homebrew's
  own and hooked `open`, `os.listdir`, `os.scandir` and `subprocess.Popen`.
  A pytest plugin put the current test id in the environment, so child
  Pythons inherited it. Readers found: `test_docs_consistency.py` (310
  planning paths), `test_workflow_hooks.py` (279, through the hooks it
  runs) and `test_portability.py` (it parses `test_docs_consistency.py`).
  `test_no_stale_name.py` reads through `git grep`, and only the Popen record
  showed it. The other grep hits for planning words are comments, docstrings
  and strings, checked one by one. The manual build opens no planning path.
- `ci.yml`: `changes`, `docs` and `ci-ok`, with the matrix gated on
  `scope == 'code'` and the draft guard moved onto `changes` and `ci-ok`.
  `changes` diffs GitHub's merge commit against its first parent with
  `--no-renames`. Twelve `ci-ok` cases and ten classifier cases were checked
  locally, and actionlint is clean (it caught a planted typo).
- Task 5 not taken, with its reason in the checklist.
- The junit upload per leg, `tests/added_test_times.py` with two tests,
  handover step 6, and the rule in `tests/CLAUDE.md`. That file's cap went
  from 296 to 302, with the reason beside the number.
- § By hand: branch protection, with the exact `gh api` call.
- Forward references in 1313's and 1507's Inherited.
- The `/code-review high --fix` pass found three bugs in the report and fixed
  them. An xdist-grouped case is named `name@group` (539 such cases on the
  CI py3.13 leg). A re-signed `def` counted as added. An untracked file was
  invisible. It also flagged that one run's per-test seconds are a figure
  where root CLAUDE.md asks for a range. The handover step now says the
  rows rank a test and do not time it. Two findings were declined. The
  explicit `-o junit_duration_report=total` is pytest's default and stays as
  a pin. `always()` on `ci-ok` stays, because a skipped required check reads
  as success.

*Measured* (`[dev]` venv, darwin arm64, unless the line says CI):

- Fast selection on the final tree: 6536 passed, 151 skipped. The claim
  commit gave 6534 and 151. The +2 are the two added tests (0.01 s and
  0.00 s), and there is no new skip. Main had not moved, so this is the tree
  that lands. The full selection was not run, because nothing here moves a
  measured number.
- The docs job's four files locally: 119 passed, 9.5 s wall.
- CI, probe #506 (docs only, run 36311608127): 79 s from creation to a green
  `ci-ok`. `changes` waited 36 s in the queue and ran for 6 s. `docs` took
  28 s, with 119 passed in 15.5 s.
- CI, probe #507 (py3.14 fails at collection, run 36311617692): the legs ran
  17:58 to 21:19. py3.14 finished with 6524 passed, 163 skipped and 4 errors.
  `ci-ok` started 2 s after the last leg and went red, reading
  `fast: failure` and `fast-jax: success`. Five junit artifacts of about
  126 KB each expire after 30 days.
- CI py3.13 junit: 4428 worker-seconds over 4202 test functions, parameter
  cases summed. The slowest 50 take 60 %, the 50th takes 16.5 s and the top
  10 take 1349 s. The same measure locally gives 1659 worker-seconds and
  57 %, with the 50th at 5.8 s.

*Gotchas.*

- Under xdist a collection error does not stop the run. The other tests
  still run and the exit code is 1 at the end, so a probe that fails at
  collection costs a full leg.
- A job whose `needs` was skipped is skipped too. `ci-ok` carries its own
  draft condition because `always()` would otherwise run it on a draft.
- The worktree guard refuses `PYTHONPATH=… python`. Run it from a
  scratchpad script.

*Next.*

1. The maintainer merges #504 and runs the § By hand call in the same
   sitting, in either order. An open PR whose branch predates `ci-ok` needs
   main merged into it. Then check the acceptance: `contexts` reads `lint`
   and `ci-ok`, and the first real docs-only PR shows `ci-ok` in about two
   minutes. Tick task 3.
2. From about 2026-10-11, do task 7. Download two weeks of `junit-*`
   artifacts with `gh run download <id> -n junit-py3.13` and choose the cut.
   The named sweeps are the first candidates. The WP closes with task 7.

- **2026-09-27** — Created by a session the maintainer asked to find where
  the repo's CI and merge drag comes from. The docs-only skip was a
  regression: WP-1003 removed it for a reason that a summary check answers.
  The measurements above are that session's, taken from `gh run list`, the
  job logs, and one local fast run with junit timings. Next: the audit-hook
  measurement, then `ci-ok` with the matrix still unconditional.
