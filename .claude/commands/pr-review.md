---
description: Review an outside pull request — triage the backlog, test the merged tree, post findings, merge only the clear-cut
---

Review pull requests from outside the repository. `$ARGUMENTS` is a list of PR
numbers, or empty.

**With numbers, review those, in the order given** — `/pr-review 126 116` does
126 then 116. Your ordering never overrides the one you were handed. **With no
argument, triage and stop**: print the ranked backlog and let the user choose.
Do not start reviewing the top row on your own.

This command is for *other people's* PRs. The maintainer's own work is gated by
`/wp-handover` steps 6 and 9, which run the same merged-tree suite from the
session that wrote the code. A number naming the maintainer's own PR is still
honoured — a stale open PR sometimes needs re-gating — but the governance signal
in triage rank 2 and the public review in step 8 do not apply to it, and you say
so in one line rather than reviewing yourself in public.

## Triage — the no-argument mode

**One network call, no checkout, no diff:**

```sh
gh pr list --state open --limit 30 \
  --json number,title,author,files,mergeable,statusCheckRollup,reviewDecision
```

`files[]` carries per-file `additions`/`deletions`, so **reviewable size is a jq
filter, never a `git diff`**: exclude `^tests/data/|^src/rietx/data/` and sum the
rest. This is the difference between reading a PR and reading a data file —
measured 2026-08-25, #125 is 48,791 lines of which 708 are reviewable, #120 is
50,112 of which 575. A triage that spends those lines has already lost the
session it was meant to save.

Print one row per PR — number, title, reviewable lines, mergeable, CI, whether a
maintainer has ever commented — **and the reason for its rank**, so the user can
overrule you knowing what you saw. Rank by:

1. **It touches a WP that is in flight.** Read the in-flight list the same way
   `.claude/hooks/session_start.py` does: the `Status:` glyph 🔄 in
   `docs/wp/[0-9]*.md`. A PR editing the WP file you have open right now is the
   one that can collide with what is being typed.
2. **An outside PR edits maintainer-only machinery** — `docs/ROADMAP.md`,
   `docs/wp/**`. `CONTRIBUTING.md` § "Maintainer-only machinery" de-scopes that
   protocol for outsiders, so this is a governance question for the user, not a
   defect. It is cheap to answer and blocks nothing, which is why it ranks high.
   The signal is author-conditional: on the maintainer's own PR those edits are
   the work.
3. **It conflicts with main.** This is **not a review**. Post a one-line rebase
   request and move on — reviewing a tree that cannot merge spends a
   fifteen-to-thirty-minute suite run on a tree nobody will ever land.
4. **Collision degree**: how many other open PRs touch its files. Merge the
   low-degree ones first, because every merge stales the diffs of the PRs that
   share a file with it, and a review that has gone stale has to be redone.
5. **Cost**: reviewable lines, ascending.

**List the maintainer's own open PRs, but mark them and rank them last.** They
are gated by `/wp-handover`, not here, and signal 2 does not apply to them —
editing `docs/ROADMAP.md` and `docs/wp/**` is the work on one's own PR, not a
governance question. Measured 2026-08-25: ranked without the author condition,
#128 sorted third on a signal that should never have fired for it.

Two honest limits on the rank, to be said once and not defended. It does not
know which small PR unblocks work the user has not started. And **collision
degree counts files, not difficulty** — colliding on `docs/manual/using/data.md`
costs a paragraph to resolve and colliding on `src/rietx/refine.py` costs a
re-review, but the rank weighs them the same, so a trivial PR that touches a
popular doc sinks further than it deserves (#126, ten lines, sits four rows below
PRs a hundred times its size). The user overrules this with arguments; that is
what arguments are for.

## Reviewing one PR

1. **Read the thread once** — `gh pr view N --comments`. The thread *is* the
   record of previous rounds; there is no local notes file and there should not
   be one. If earlier rounds exist, this review is **incremental**: diff only
   `<last-reviewed-sha>..<head>` and say which round this is, the way the #98 and
   #108 reviews did.
2. **Classify the changed files before reading any diff.** Take the file list,
   split it into code, docs, gui and data, and only then read:

   ```sh
   git diff BASE HEAD -- . ':(exclude)tests/data/*' ':(exclude)src/rietx/data/*'
   ```

   **Never a bare `gh pr diff`.** It will hand you fifty thousand lines of
   measured intensities, and you will have paid for them before you notice.
3. **Check data files by property, never by content.** Line and column count,
   header, file mode, a provenance row in `tests/data/README.md`, a row in
   `tests/validation_matrix.py` where a standard is claimed. A file entering the
   **wheel** (`src/rietx/data/`) must state its licence where it ships — a PyPI
   upload publishes harder than a repository does (root `CLAUDE.md` § Licensing).
   Nothing enforces any of this: the #108 review caught a 1.5 MB `.xy` committed
   at mode 755 with no provenance row by reading its properties, not its numbers.
4. **Prepare the bench and build the merged tree.** One shared worktree at
   `.claude/worktrees/pr-bench` with one venv — not one per PR, which would cost
   several hundred megabytes each and, on the evidence of the ten stale trees
   already in that directory, never be reclaimed.

   **Address the bench with `-C`, never with `cd`.** The shell's working
   directory persists between tool calls, so a `cd` typed in an earlier step
   silently retargets a later `git reset --hard`, and the two trees are
   indistinguishable in ordinary output: the bench sits *inside* the main
   checkout, shares its remote, and answers `git rev-parse --short origin/main`
   identically. `git -C` cannot be defeated that way and puts the target in the
   command rather than in invisible session state. Measured on this command's
   first outing: a `cd` added to a `gh pr list` that did not need one (gh reads
   the remote, and the bench has the same one) sent the next four commands into
   the main checkout.

   ```sh
   BENCH=.claude/worktrees/pr-bench
   git -C "$BENCH" fetch origin main
   git -C "$BENCH" fetch origin "pull/N/head:refs/pr/N" --force
   git -C "$BENCH" reset --hard origin/main
   git -C "$BENCH" merge --no-edit refs/pr/N
   git -C "$BENCH" diff origin/main --stat        # the PR's own contribution
   ```

   **Fetch into a named ref, not `FETCH_HEAD`.** `FETCH_HEAD` is *per worktree*
   (`.git/worktrees/pr-bench/FETCH_HEAD`, beside the main checkout's own), so a
   fetch run anywhere else leaves the bench merging whatever it last fetched —
   silently, and a stale head still merges. `refs/pr/N` lives in the common dir,
   survives the next fetch, and is what the round-2 diff
   (`refs/pr/N@{1}..refs/pr/N`, or a recorded sha) and `git merge-tree
   origin/main refs/pr/N` want anyway.

   **`reset --hard` is the whole reset; never `git clean -fdx`.** `-x` deletes
   *ignored* files, which in this repo means `gui/node_modules`,
   `docs/manual/_generated`, `tests/output/`, every cache, any `*.rex/` project
   a person left in the tree, and the bench's own `.venv`. Reaching for
   `-e .venv` to protect the venv is the sign the command is wrong for the job.
   Tracked files are what a PR changes and `reset --hard` handles them; an
   untracked build artefact between two PRs is harmless.

   **Treat the main checkout as someone else's.** It usually carries a live WP
   session on its own branch, and the destructive half of this ritual has no
   business there.

   **The merged tree is the tree under test.** Branch protection is
   `strict: false`, so nothing else ever tests it — not CI, not the contributor.
   A merge conflict here **is** the finding: report it, ask for a rebase, stop.

   Build the venv with `uv venv --python 3.12 && uv pip install -e ".[dev,jax]"`,
   and reinstall only when the PR touches `pyproject.toml`. The extras are
   deliberately not `wp-start`'s `[dev]`: they match `nightly.yml`'s `full` job,
   so a count here is comparable to the nightly log and the cross-backend rows
   are passes rather than skips. A new skip is not a new pass.
5. **Run the ladder the touched paths select**, every pytest call with
   `-n auto --dist loadgroup` (`tests/conftest.py` refuses a run without it):
   - **docs/manual only** → `test_docs_consistency.py`, `test_manual.py`,
     `test_manual_api.py`, and the `-W` sphinx build.
   - **`gui/` only** → `npm --prefix gui ci && npm --prefix gui run build`, then
     `git diff --exit-code src/rietx/gui/static` (the committed dist must match a
     fresh build), `npm --prefix gui test`, `npm --prefix gui run check`.
     `gui.yml` is not a required check, so this is a real gap rather than a
     duplicate of CI.
   - **`src/` or `tests/`** → the fast suite, then **the slow tests covering the
     PR's area**.
   - **always** → `.venv/bin/python -m ruff check src tests examples`.

   The slow selection is the point of running anything locally. `ci.yml` runs
   `-m "not slow"` and `nightly.yml` has no `pull_request` trigger, so **the
   acceptance suites never run on a PR** — that is how #108's red got through, in
   a module marked `pytestmark = pytest.mark.slow`. CI being green tells you
   almost nothing here; all fourteen open PRs were green on 2026-08-25.

   The **whole** `-m slow` suite fires once, at the merge gate in step 9, not on
   every round. Quote every count with its venv **and** platform
   (`tests/CLAUDE.md` § Quoting numbers), and as a range, never a record.
6. **Check conformance against `CLAUDE.md`, sized to the PR.** Under roughly 400
   reviewable lines, read the diff yourself — spawning agents costs more than it
   saves, and most PRs are this size. Above it, write the reviewable diff to the
   scratch directory **once** and dispatch one `pr-conformance` agent per touched
   subtree, each pointed at that file and at the `CLAUDE.md` governing its
   subtree. They return findings only, so a four-thousand-line diff never enters
   this session.

   **Verify every finding yourself before any of it is posted.** The agents run
   capped and quote the rule they claim was broken; checking a quotation is cheap
   and posting a wrong finding to a contributor is not.

   Do not restate the invariants in this file. They live in `CLAUDE.md`, they
   change, and a copy here would be a second authority that drifts out of date
   while looking authoritative. The classes worth naming, because an outside
   contributor misses them most: a `Literal` member or a defaulted field with no
   writer, a physics function with no citation, a new correction offering an Rwp
   comparison as its evidence, a reader repairing a file without a diagnostic,
   GPL-derived code, a new diagnostic code with no `docs/AGENT_PROTOCOL.md` row,
   and new physics with Part 1 prose but no Part 2 manual equation.
7. **Run `/code-review high N` for ordinary correctness**, and only for `src/`
   changes above the step-6 threshold. Name the level explicitly — with none
   given it reuses the last level typed, which makes a review's depth depend on
   what happened earlier in the session. Step 6 covers what it cannot know;
   running both over a ten-line documentation fix is waste.
8. **Split the output by audience, because they need different things.**

   **Public**, posted to the PR: what you checked *independently* and what it
   produced, then a numbered "what I would want before merge" list, with named
   follow-ups kept separate from it. This is the shape of the #108 review and it
   works because it separates the blocking from the merely noticed. End with one
   attribution line, and put the same line on a merge commit body, which is
   public too:

   > *Reviewed with Claude Code on behalf of @yue-here.*

   **Private**, to the user in the terminal: what the PR is *for* and what it
   changes for someone using the package, in plain language with no dot-paths or
   symbol names in the opening paragraph; then what you ran and what it said;
   then the open questions.

   **Findings go public, questions come to the user.** A question the contributor
   can answer is a finding — ask it in the review. A question about whether the
   design is wanted at all, or about an outside PR editing ROADMAP and WP files,
   is the maintainer's. **Do not post the review while one is outstanding**: ask
   first, then post once the answer is in.
9. **Merge or close only the clear-cut, and stop for everything else.** Merge
   with `gh pr merge --merge`, matching the repo's merge-commit history, and only
   when **all** of these hold: required checks green; the step-5 ladder green on
   the merged tree with counts quoted; the **full `-m slow` suite green on the
   merged tree**; no conformance finding; no new public surface left
   undocumented; every added data file carrying provenance, and a licence if it
   ships in the wheel; no maintainer-machinery edit; and no open question. Name
   which of these each merge satisfied, in the private report.

   Close only when the contributor asked for it, or when the work has been folded
   into another PR — #112 and #114 were closed into #108 that way, and neither
   was a rejection.

   Anything else **stops and asks**. Merging is hard to undo and it is someone
   else's contribution; a held PR costs a day, a wrong merge costs the history.
10. **Report to the person, not to the log**: the plain-language paragraph first,
    then what was run, then the open questions, then the PR URL. End with exactly
    `PR N: <decision>` — `merged`, `closed`, `review posted`, `rebase requested`,
    or `held, waiting on you`.
