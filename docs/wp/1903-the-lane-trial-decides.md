# WP-1903 — The lane trial decides whether a WP session sends long items to subagents

Milestone: unscheduled · Status: 🔄 2026-10-07 — evidence in, decision leaning adopt; paused to re-measure seven trial sessions on the second machine
Track: The repo's own process
Depends on: —
Priority: P4 2026-10-01 — was P3 (cost only: the replay put the saving at about a fifth of a WP session's bill): down a rung until three trial rows are in the record

## Goal

At least three WP sessions have run under `/wp-lanes`, and their measurements
are in the record. On that evidence the lane rule goes into `/wp-start` step
6b, changes and is tried again, or is withdrawn with the reason written down.

## Context

**What exists** (PR #586, 2026-10-01).

- `docs/milestones/process.md` § Lanes within a WP is the record. It holds the
  replay over 174 WP sessions, the crossover table and the trial table this
  WP reads. Read that section first. It is about 1,000 words.
- `.claude/hooks/session_usage.py` reads Claude Code's transcripts under
  `~/.claude/projects`. `baseline` re-runs the replay, and its `--u`, `--mo`
  and `--d` options take measured values in place of the assumed ones.
  `lanes <session-id>` measures one trial session. `context <session-id>`
  prints the main context now. A session's id is the name of the directory
  that holds its scratchpad. `tests/test_session_usage.py` pins it.
- `/wp-lanes NNNN` starts a WP session in place of `/wp-start NNNN`. It runs
  `/wp-start`, then sends an item to a lane when the main context is over 150K
  and the item's estimate is 20 or more requests. One lane runs at a time, in
  the session's worktree. The lane does not commit. The main session checks
  its diff, re-runs its tests and commits.
- `/wp-handover` step 3b runs the measurement whenever a session dispatched
  lanes. It puts the tables in that WP's handover entry and appends one row to
  the record's trial table.

**What the replay predicted.** Laning every item saved 20% or cost 4% of the
modelled reads and writes, depending on *u*. The selective policy above saved
19-28%, and 11-21% under heavier checking or one lane in five redone. Sessions
peaking under 300K saved about 1%. The replay is a model over real
trajectories, and five of its inputs are guesses:

| input | assumed | what the trial row calls it |
|---|---|---|
| *u*, code a lane re-reads that the main session held | 0-40K | re-read (*u*) |
| main-session requests to dispatch and check one lane | 5 | main requests per lane |
| tokens a lane leaves in the main context | 8K | left in main |
| how well a session guesses an item's length | exact | actual / estimated requests |
| how often a lane's work is fixed or redone | never | lanes fixed / redone |

**What the rows cannot show.** Whether lane-written code is as good. Read it
off each trial session's handover entry: the findings `/wp-handover` step 6
raised on lane-written diffs, and anything the lane prompt failed to carry. A
lane loads the CLAUDE.md files but no MEMORY.md, so a forgotten memory rule
shows up there.

**Gotchas.**

- The transcripts live only on the machine that ran the session, and Claude
  Code deletes old ones (`cleanupPeriodDays`). Run the evaluation on the
  maintainer's machine, before the trial sessions age out. Each row is also
  committed to the record, so the summary survives either way.
- *In-session $* and *saved $* rest on the same model as the replay. The lane
  side is measured. The window from dispatch to commit counts every main
  request as lane overhead, which favours keeping the item.
- A trial session that never passes 150K dispatches nothing. Its `lanes:
  keep` lines still measure estimate accuracy, but the measurement only runs
  when a lane was dispatched. Pick trial WPs with several implement-and-test
  items, and expect long sessions.
- `baseline` re-reads whatever transcripts the machine holds, so its numbers
  drift from the record's. Quote the run's date with them.

## Non-goals

- Lanes for reading. `/wp-start` step 6b already delegates reads above ~50 KB.
- Parallel lanes or lanes in separate worktrees. They save wall-clock time,
  not tokens, and their test runs would compete on one machine.
- Sonnet or Haiku lanes. Their cache reads cost the same as Opus or half of
  it, and the model follows the judgement an item needs.
- `/pr-review`'s delegation. It has its own measurement (#548).

## Tasks

- [x] Wait for three trial rows, with at least six lanes among them. Each
      comes from a WP session started with `/wp-lanes NNNN`. Those sessions
      commit their rows under their own WP numbers.
- [x] Re-run the replay with the trial's medians,
      `python3 .claude/hooks/session_usage.py baseline --u U --mo MO --d D`,
      and put its output in this WP's handover entry with the run's date.
- [x] Read each trial session's handover entry for the quality evidence
      above. List the review findings on lane-written code, and what the lane
      prompts lacked.
- [ ] Decide, then land the decision:
      - **adopt**: move the rule into `/wp-start` step 6b with thresholds read
        off the re-run's crossover table, delete `/wp-lanes`, and keep
        `/wp-handover` step 3b, since it only fires when lanes ran;
      - **adjust**: change the thresholds or the lane prompt in `/wp-lanes`,
        and ask for more trial rows;
      - **withdraw**: delete `/wp-lanes` and `/wp-handover` step 3b, keep
        `session_usage.py`, and close this WP 🛑 with the reason.
- [ ] Write the decision and its evidence at the end of process.md § Lanes
      within a WP.
- [ ] Skill: none. The agent skill is for driving rietx, and this is a rule
      for changing it (root CLAUDE.md § Roadmap, the three destinations).

**A bar to start from**, proposed 2026-10-01 and not yet agreed with the
maintainer. Adopt if the re-run's selective row saves at least 10%, at most
one lane in five was redone, and the findings on lane-written code are no
worse than usual. The 10% is half the replay's middle figure, chosen to leave
room for what the model leaves out. Confirm or replace it before deciding.

## Acceptance

The decision is written into the record with the trial rows and the re-run
behind it, and the commands and tests agree with it:

```sh
python3 .claude/hooks/session_usage.py baseline --u U --mo MO --d D
.venv/bin/python -m pytest tests/test_session_usage.py tests/test_docs_consistency.py tests/test_workflow_hooks.py -n auto --dist loadgroup
```

## References

- `docs/milestones/process.md` § What a session's reading costs (#548, the
  cache-read mechanism and the reading bars) and § Lanes within a WP (#586).
- Prices: Opus 5.5 $4 input, $20 output, $0.20 cache read, $5 5-minute write,
  $8 1-hour write per million tokens. Sonnet 5.5 $2, $10, $0.20, $2.50, $4.
  Haiku 4.5 $1, $5, $0.10, $1.25, $2. They are `PRICES` in the script.

## Handover log

- **2026-10-07** — **The trial says lanes pay, and the decision waits on one
  check.** Nine sessions sent 24 items to lanes, and every session came out
  ahead on the cost model, by a median 21%. Re-run with the trial's measured
  inputs, the replay still has the selective rule cutting modelled reads and
  writes by 18%, and by 11-14% under pessimistic settings. Two lanes wrote a
  correctness bug that the handover review caught, and both bugs came from
  something the lane prompt did not carry. The maintainer leans towards
  adopting, but first wants the seven trial sessions whose transcripts are
  not on this machine re-measured on the other computer, which holds them.
  This session ran under `/wp-lanes` and dispatched no lane, because its only
  implementation item was a three-line fix.

  *Done.*
  - Inherited pruned (`b0e9c0d7`). Both entries were trial rows already in
    process.md's table, and 1534's "re-run on the maintainer's machine" is
    this session's re-run.
  - `baseline` prints one sign convention (`2d6e632a`). The policy table
    printed a change in cost and the peak-context bands a saving, so
    WP-1523 read +26% and −31% from one run as a contradiction. They were
    the same verdict: at its 74K re-read, lanes cost more. Both blocks now
    print a change, and both headers say negative is a saving.

  *Which session is which WP.* ec2ca17f WP-1529; 46f97a56 WP-1531 (with
  1533); c77ba4ec WP-1534, a cloud container; 6dc4faa1 WP-1323; e6ef1126
  WP-1510; 0433c291 WP-1527 (with 1504's round E); 38257a74 WP-1523;
  d1d1ba33 WP-1905, a cloud container; 23ba0bb7 WP-1906. Only 46f97a56 and
  23ba0bb7 are on this machine.

  *Measured* (2026-10-07, this Mac; the replay reads 46 WP sessions from
  2026-09-20 on, since older transcripts have aged out).
  - Trial medians over the nine rows: re-read 3K, 10 main requests per lane,
    16K left in main, actual/estimated requests 1.60. Weighted per lane
    instead: 0K, 8, 15K.
  - `baseline --u 3000 --u 20000 --u 40000 --mo 10 --d 16000`:

    | policy | items laned | u = 3K | u = 20K | u = 40K |
    |---|---|---|---|---|
    | lane every item | 421 | +9% | +20% | +33% |
    | lane when main > 200K | 308 | +16% | +23% | +32% |
    | lane when main > 150K and item >= 20 requests | 73 | −18% | −15% | −12% |
    | same, mo doubled and d = 20K | 73 | −11% | −8% | −5% |
    | same, one lane in five redone | 73 | −14% | −11% | −7% |

    By peak context (selective, u = 20K): under 300K +1% (17 sessions),
    300-450K −7% (13), above 450K −21% (17). Crossover at an 80K lane base:
    65 requests at 150K main, 42 at 200K, 33 at 250K, 28 at 300K, 22 at
    400K. Lane bases measured 66-79K, so the 80K row is the one to read.
  - The same 46 sessions under the original assumptions (`--u 0 --u 20000
    --u 40000`, mo 5, d 8K): selective −23% / −20% / −17%. The record's 174
    gave −28% / −23% / −19%. So the measured inputs cost about 3-5 points,
    and the shrunken window about 5.
  - Totals over the nine rows: $90.82 saved; 2 of 24 lanes redone (8%),
    both in WP-1510; 11 of 24 edited by the main session after return. 3 of
    24 lanes lost money, $0.54-1.65 each, all in WP-1510 and all 22 requests
    or fewer. Lanes that won saved up to $7.56.
  - **Re-measuring the two local sessions today gives larger savings than
    the record's rows.** 46f97a56 reads +$23.08 over its five lanes (row
    +16.73) and 23ba0bb7 +$0.41 (row +0.10). The script changed after those
    rows were written (`subagent_dirs` and later), so the rows may be
    conservative. This is one reason to re-measure the other seven.
  - Models: `/wp-lanes` says general-purpose on the default model, so a lane
    inherits the main session's. Every lane with a model column ran Opus 5.5
    except one in WP-1510, `duplicate_line surface sync`, on Sonnet 5.5,
    which lost $1.65. The other seven sessions' tables lack the column.

  *Quality evidence* (task 3), from each session's handover entry.
  - WP-1534: one correctness bug in lane code. A phase released mid-stage
    skipped the new probe, because the prompt named one entry path and not
    the second. Caught by the review.
  - WP-1527: the review fixed the TOPAS writer, written by the
    `1527-writers-rule` lane, which had dropped a magnetic site's ion.
  - WP-1510: the first corundum lane died on the 600 s stream watchdog
    during a long test run. The re-dispatch was told to keep commands under
    8 min. That rule is in the maintainer's memory, which a lane cannot see.
  - WP-1523: the lane needed a revised design sent by `SendMessage` after
    its first report. It re-read 74K and left 72K in main, both far above
    every other lane. It was an item needing a decision partway, which the
    rule already says to keep.
  - WP-1531, 1529, 1323, 1905, 1906: no review finding attributed to lane
    code. WP-1531's lanes deviated from their prompts on sound, reported
    calls, as 1534's did.
  - Decision lines went missing in three sessions (1534 twice, 1539 for two
    items, 1906 for two kept items). The kept-item table then has no
    estimate for them. Whether 1534's two failed `DECISION` or were never
    written plainly is still unchecked; its transcript was in a cloud
    container.

  *The other computer.* Pull this branch (`iterative-plotting-parasol`), then
  from its worktree:

  ```sh
  for s in ec2ca17f c77ba4ec 6dc4faa1 e6ef1126 0433c291 38257a74 d1d1ba33; do
    f=$(find ~/.claude/projects -name "$s*.jsonl" | head -1)
    echo "== $s ${f:-MISSING}"
    [ -n "$f" ] && python3 .claude/hooks/session_usage.py lanes "$(basename "$f" .jsonl)"
  done
  python3 .claude/hooks/session_usage.py baseline --u 3000 --u 20000 --u 40000 --mo 10 --d 16000
  ```

  `lanes` takes the full id, never a prefix, hence the `find`. Compare each
  session's printed trial row with its row in process.md § Lanes within a
  WP: saved $, lanes fixed / redone, re-read, left in main. Expect c77ba4ec
  and d1d1ba33 to be missing, since they ran in cloud containers. That
  machine's `baseline` reads a different set of sessions, so quote its date
  and session count beside the row above.

  *Gotchas.* The record's rows were written by different versions of
  `session_usage.py`, so a row and today's re-measure of the same session
  disagree. Correct a row only with a note saying which script version
  measured it. `.claude/hooks/worktree_only.py` refuses a `git grep` over
  `origin/main` here; use plain `grep -r` over the tree.

  *Next*, in order:
  1. Run the block above on the other computer. If the re-measured savings
     stay positive and the redo count stays at 2, adopt. If they turn
     negative in more than one session, report back before deciding.
  2. Adopt, as the maintainer leans: move the rule (150K, 20 requests,
     unchanged) into `/wp-start` step 6b with the dispatch protocol from
     `/wp-lanes` steps 3-5, and add three prompt rules: name every code
     path the change reaches, restate the memory rules that bear on the
     item (the 8-minute command limit among them), and write a decision
     line for every item. Delete `/wp-lanes` and repoint the three
     references to it (`wp-handover.md` step 3b, `session_usage.py`'s
     docstring, process.md). Keep step 3b and the script.
  3. Write the decision and its evidence at the end of process.md § Lanes
     within a WP, then close ✅.

- **2026-10-01** — created. No open WP owns session token economics. 1506 and
  1507, the two open ones on this track, are about CI and the WP index.

  This session measured whether subagents could make a WP session cheaper, and
  built a trial to test the answer on real work. Over 174 sessions, re-reading
  the context is two-thirds of the bill, and most of it is accumulation. A
  replay says that sending only long items, late in a session, to subagents
  saves about a fifth. Sending every item is fragile. Nothing in the package
  changed.

  *Done* (PR #586, four commits): `session_usage.py` with its tests, the
  record section, `/wp-lanes`, and `/wp-handover` step 3b. `/wp-lanes` began
  as a command to run after `/wp-start`. The maintainer pointed out that a
  session runs its checklist straight through after `/wp-start`, so it became
  the entry point, and the measurement moved into the handover, which the
  session invokes itself.

  *Measured*: the record's numbers, from `baseline` on 2026-10-01. Fast
  selection 7,072 passed, 157 skipped (`.venv` with `[dev]`, macOS). CI was
  green on the PR head `b94e4fad`.

  *Gotchas*: the first CI run failed on `test_portability`, which rejects any
  text I/O without `encoding=` in every test file. Run the fast selection
  before pushing a new test file.

  *Next*: merge #586, then start three or four WP sessions with
  `/wp-lanes NNNN`. Once three rows are in, run `/wp-start 1903`.
