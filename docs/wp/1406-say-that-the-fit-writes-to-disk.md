# WP-1406 — say that the fit writes to disk

Milestone: unscheduled · Status: ⬜
Depends on: 1403 (the behaviour being documented); 1405 (the sentence the skill
body carries); 1402 (the break being recorded)

## Goal

The track's behaviour changes are written down where each audience reads: a
library user learns that a fit now writes to disk and how to stop it, a person
learns what `rietx watch` shows them, and an agent learns the one fact that
changes how it handles an exception. WP-1403 is not shippable without this.

## Context

Three audiences, three registers, and the house rule that a session's findings
go to three different destinations (WP-1330): a rule an agent *driving* rietx
needs goes in the skill, a rule for *changing* the package goes in a CLAUDE.md,
and a measurement goes in a WP handover. This WP places the first two; WP-1404
already placed the third.

### One clause in the root CLAUDE.md is falsified

> The **run state is not an event** — `EventKind` is closed, so a run's status
> travels beside the stream and `live/events.jsonl` stays the one thing `watch`
> tails.

The **rule** survives exactly: state beside the stream, never an `EventKind`,
and WP-1401's cross-process liveness is that rule carried one rank out. The
**sentence** does not: `watch` reads a run's metadata, its status and its
snapshot as well. Edit it in this change, or the rulebook describes code that
does not exist. Keep the reason, which is the part that matters.

### The manual

- **`using/cli.md`** § `rietx watch` (around line 115) — the no-argument mode,
  the run list, what each liveness word means and especially that **abandoned**
  is a third answer rather than a rounding, the JSON routes, and above all how a
  run comes to exist at all. The `rietx --help` block near line 16 is a
  hand-kept copy of `cli.py`'s string: update it too. Nothing crosses those two
  today; a one-line guard would be cheap, but it is not this WP's job — note it
  and move on.

  *Superseded in part, 2026-09-15.* This bullet also asked for "the cancel
  button and what it does to the other process, the read-only serving flag".
  Neither exists in the tree. The button is WP-1405's and WP-1405 has not
  started, so `watch.py` carries no cancel route and the package's only
  `CancelToken()` is `gui/session.py`'s, for the GUI's own fits. There is no
  read-only flag either: `rietx watch` takes a directory, `--port` and `--open`.
  Reading-only is a property of the reader's design rather than something a flag
  selects, which is how the chapter now states it. Both go to WP-1405's manual
  pass.
- **`using/files.md`** — the `.rex` tree is drawn twice, as a mermaid diagram
  (line 16) and an annotated listing (line 241); **both** gain the run
  directories, and a new subsection covers the working directory's `.rietx/`
  with the sentence no test can enforce: it is unrelated to `$HOME/.rietx` and
  **no env var moves it**. Then, plainly, **what a run directory contains** —
  every free parameter's value at every recorded evaluation, and no pattern
  bytes. A reader on a shared filesystem is entitled to that in the manual and
  not in a WP file.
- **`using/refining.md`** § Watching a run (around line 561) — `telemetry=`, the
  env switch, retention by age and size, and the sentence a library user will be
  annoyed not to find: *a fit now writes to disk by default, and here is how to
  stop it.* Put it early in the section, not in a note at the end. Sizes are
  quoted from WP-1404's measured ranges and from nowhere else.
- **`using/compatibility.md`** — the `fit.html` break and the change to
  `<project>/live/`'s contents. The promise is a preview and anything may change
  in any release, but every break is recorded.

  *Narrowed, 2026-09-15.* The `fit.html` break's **record** already exists:
  WP-1402 wrote it into `docs/milestones/v1.4.md` § Breaks on the day it landed,
  which is where a break goes when no milestone is open. Two other things are
  missing. WP-1403's recording is a **user-facing addition with no entry** in
  that record's Additions list, and it is the largest one of the track. And the
  chapter itself says nothing about the run layout, which is a second process's
  contract carrying no version string. Both land here.
- Part 2 is untouched: this track adds no physics, so no equation and no fenced
  constant moves.

### The skill

Its body takes only what holds for **every** fit, and it is capped.

*Superseded, 2026-09-15.* The one fact this WP reserved for the body was:

> A human may be watching, and may stop you. A `RefinementCancelled` you did not
> request is not a bug in your call: the completed stages are kept, and
> `.completed_stages` and `.node_id` say where the work stands.

**It is not true yet, so it is not written.** A fit raises
`RefinementCancelled` only when its own caller passed `cancel=`; there is no
cancel file in `runs.py`, no poll in `RunRecorder`, and `fit` creates no token of
its own. The sentence describes WP-1405's feature, and WP-1405 has not started.
Writing it now would put a confident falsehood in the one document every agent
reads whole, which is the failure the skill's measurement tags exist to prevent.
It moves to WP-1405, whose `### The material the chapters are written from

Folded out of `### Inherited` on 2026-09-15, from WP-1401, WP-1402 and
WP-1403. Each fact below was checked against the tree on the way in; the
mailbox is consumed and gone.

**What a run directory contains**, so a page can say it plainly: the event log,
`meta.json` (label, created, package version, the working directory, the command
line), `status.json` (state, pid, host, heartbeat, stage, Rwp, gof),
`snapshot.json` (the stage's curves), `summary.txt` (the termination view), and
`run.lock`. 204 kB in total on a five-stage synthetic fit.

**Three consequences a user will meet, and all three want a sentence.** A run
directory holds every free parameter's value at every recorded evaluation, so on
a shared filesystem that is a disclosure nobody opted into; no pattern bytes are
ever copied. A fit run inside somebody else's package leaves `.rietx/` in
*their* working directory, and this will be reported as a bug at least once. And
a `.gitignore` of `*` is written into the runs root, so it does not turn up in
`git status`.

**The switches, in the order a page should give them:** `RIETX_TELEMETRY=0` for
the whole process and everything under it, `telemetry=False` for one call,
`telemetry=<path>` to put runs somewhere else, and `runs.set_enabled` inside a
process. The environment outranks the keyword and there is deliberately no value
that argues back.

**Two locations, one spelling.** `$HOME/.rietx` is the GUI's per-user state and
`RIETX_STATE_DIR` moves that one alone; the working directory's `.rietx/` is the
runs root and no variable moves it. The page has to keep these apart or it
teaches the wrong knob.

**A project's `live/` holds one directory per run now**, so a GUI project and an
agent fitting the same project no longer interleave one log. `files.md` was
corrected in four words; the chapter is this WP's.

**Retention deletes by age and size** (a 1 GiB ceiling, a week's floor, oldest
terminal run first) and warns rather than deleting when nothing is old enough. A
user who wants their evidence kept should be told that nothing inside the floor
is ever removed.

**`LiveSession` no longer writes `fit.html`.** It writes `snapshot.json`. What
does *not* break: a `fit.html` already on disk still opens, `rietx watch` serves
it at `/api/run/<id>/legacy` and by its bare name through the static fallback,
and `rietx html` / `viz.html.write_html` are untouched. `runs.SNAPSHOT_FILE` is
`snapshot.json`, `runs.LEGACY_SNAPSHOT_FILE` is `fit.html`,
`Run.has_legacy_snapshot` sits beside `has_snapshot`.

**The routes are provisional by declaration, like the GUI's.** `watch.py` serves
`/`, `/plotly.js`, `/api/runs`, `/api/run/<id>`, `/api/run/<id>/events?offset=`,
`/api/run/<id>/snapshot` (JSON now, not a page) and `/api/run/<id>/legacy`.
Nothing pins them, so a chapter naming them says what `using/gui-quickstart.md`
says about the GUI's.

**`using/cli.md` § `rietx watch` is the floor rather than the chapter.** WP-1401
rewrote it and WP-1402 corrected one sentence in place, both times because the
old text stated things the command had stopped doing. What is still missing is
everything a reader *needs* rather than everything that was false.

*Deleted as stale, 2026-09-15.* WP-1401's last entry reserved a skill row saying
"pass `events=`, it is nearly free", and noted it would be moot if WP-1403
recorded anyway. WP-1403 shipped, so it is moot: an agent that passes nothing
still gets a run directory, and telling it to pass `events=` would be advice
about a knob it no longer needs to touch.

## Non-goals

- **No code.** If a docs session finds a behaviour that cannot be written down
  honestly, that is a bug report against the WP that shipped it, not a fix here.
- **No screenshots in the manual for the watcher**, unless WP-1401's page turns
  out to need them. `make_screenshots.py` drives the GUI; extending it to a
  second server is its own decision.
- **No skill body sentence about `telemetry=` or the watcher's existence.** An
  agent does not need to know the plumbing; it needs to know the exception can
  arrive unasked. Resist the second sentence.

## Tasks

Rewritten 2026-09-15 on arrival, against the tree rather than against the plan.
Two items changed shape and one moved out; the reasons are in Context above.

- [x] Prune: three findings superseded in part, the `### Inherited` mailbox
      consumed, this list rewritten.
- [x] The root CLAUDE.md clause, edited to keep the rule and drop the false half.
- [x] `runs.py`'s own comments, which are the same defect one rank down: three
      of them still say `meta.json` and `run.lock` are unwritten and `RunStatus`
      names fields "absent from every file in the tree", while `RunRecorder`
      writes all of them. Comments, not code, so the no-code non-goal holds.
- [x] `using/cli.md` (both the section and the `--help` block) and
      `using/files.md`.
- [x] `using/refining.md`, with the writes-to-disk sentence early and the sizes
      quoted from WP-1404.
- [x] `using/compatibility.md`: the run layout as an unversioned contract; and
      WP-1403's addition staged in `milestones/v1.4.md`, which has none.
- [x] The `references/` file and its routing row, with the pinned header and the
      measurement tags; the row **paid for by a named cut**, named in the commit
      message. Then `rietx skill --install . --copy`.
- [x] ~~The skill body sentence~~ — moved to WP-1405, which is the WP that makes
      it true. Its `### Inherited` carries the sentence and the owed cut.
- [x] WP-1322's Task 2 recorded as discharged, dated; WP-1133's and WP-1405's
      `### Inherited` noted.
- [x] Record the two deliberate refusals — no surface flag, no seventh contract
      — where a later session will find them, which is here and in the module
      docstring, not in a commit message alone.
- [x] Skill: this WP **is** the skill task for the track.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_manual.py tests/test_skill.py tests/test_docs_consistency.py tests/test_help.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

`-W` green is not a rendered page: open the built HTML for the changed pages and
look at them, per the manual's own rule that a paragraph which printed its own
TeX passes every check a build can make.

## References

- WP-1330 — three destinations for what a session learns; a reference per task
  shape behind a situation row; a body addition paid for by a cut.
- WP-1117 — the manual's coverage partition, and the compatibility page's
  preview status.
- WP-1067 — a WP that adds physics adds its equation to Part 2. This one adds
  none, which is why Part 2 is untouched.
- WP-1037 — `_SURFACE_FLAGS`, and the derived flag that was wrong for its whole
  life.
- WP-1322 — Task 2, discharged here.

## Handover log

- **2026-09-13** — created. Placed last in the track but it is not optional
  decoration: WP-1403 changes what every `fit()` does to a user's filesystem, and
  a behaviour change nobody wrote down is the thing the few-users policy exists
  to prevent. The hardest editorial judgement is the skill body — exactly one
  sentence qualifies, and the pressure to add a second explaining the watcher
  should be refused.
