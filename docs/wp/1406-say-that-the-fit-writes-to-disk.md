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
  is a third answer rather than a rounding, the cancel button and what it does
  to the other process, the read-only serving flag. The `rietx --help` block near
  line 16 is a hand-kept copy of `cli.py`'s string: update it too. Nothing
  crosses those two today; a one-line guard would be cheap, but it is not this
  WP's job — note it and move on.
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
- Part 2 is untouched: this track adds no physics, so no equation and no fenced
  constant moves.

### The skill

Its body takes only what holds for **every** fit, and it is capped. Exactly one
new fact qualifies:

> A human may be watching, and may stop you. A `RefinementCancelled` you did not
> request is not a bug in your call: the completed stages are kept, and
> `.completed_stages` and `.node_id` say where the work stands.

That changes error handling in every fit, which is the test for a body line. Per
WP-1330 a body addition is **paid for by a named cut**, and the cap moves only in
a commit that says so — so name the cut in the commit message, not in a comment.

Everything else is a reference behind one routing row, keyed by the situation
rather than the feature: *a human is watching this session, or you need to hand
one a window onto a long run*. It covers how to point a human at the watcher,
what a run directory holds, and how to read a run back afterwards. Every row
carries its `(Measured: …)` or `(Hypothesis: …)` tag, and the file opens with the
header `tests/test_skill.py` pins. A routing row is likewise paid for by a cut.

Then `rietx skill --install . --copy` re-syncs the two committed copies, or they
drift.

### What deliberately does not happen

- **No `capabilities()` surface flag.** "Can this build record runs?" always
  answers yes — there is no optional dependency behind it — so a flag would be a
  literal `True` in disguise, which `_features()` forbids by construction, and
  `_SURFACE_FLAGS` exists because a derived flag rots silently
  (`features["indexing"]` was `False` for its whole life). Write the refusal
  down; adding one is the reflex.
- **No seventh versioned contract.** The run layout is a second process's
  contract, which argues for an arm; nothing negotiates over it and WP-1006's
  own precedent is that a contract nothing has exercised is an untested guess,
  which argues against. Defer until the layout has survived a release, and say so
  here rather than leaving it unasked.

### Two WPs to close out

- **WP-1322's Task 2** — the `history` defaults asymmetry decision — is
  discharged by WP-1403, which removed its premise. Record that in 1322, dated,
  and leave its Task 1 (the terminal-shaped post-hoc aggregator over an event
  log) untouched: it is a different surface for a different moment, and it is a
  contributor's offered PR.
- **WP-1133** (a diagnostic names the rendered view that shows it) now has a
  rendered view to name. Note it in that WP's `### Inherited` rather than
  claiming it here.

### Inherited

From **WP-1403** (2026-09-15), whose feature is not shippable without this WP:

- **This is now the blocking item, not a follow-up.** Every fit writes to a
  user's disk and no sentence anywhere in the manual or the skill says so. 1403
  shipped its code with that stated as a deliberate non-goal; the gap is real
  and it is this WP's.
- **What a run directory contains**, so the page can say it plainly: the event
  log, `meta.json` (label, created, package version, the working directory, the
  command line), `status.json` (state, pid, host, heartbeat, stage, Rwp, gof),
  `snapshot.json` (the stage's curves), `summary.txt` (the termination view),
  and `run.lock`. 204 kB in total on a five-stage synthetic fit.
- **Three consequences a user will meet, and all three want a sentence.** A run
  directory holds every free parameter's value at every recorded evaluation, so
  on a shared filesystem that is a disclosure nobody opted into; no pattern
  bytes are ever copied. A fit run inside somebody else's package leaves
  `.rietx/` in *their* working directory, and this will be reported as a bug at
  least once. And a `.gitignore` of `*` is written into the runs root, so it
  does not turn up in `git status`.
- **The switches, in the order a page should give them:**
  `RIETX_TELEMETRY=0` for the whole process and everything under it,
  `telemetry=False` for one call, `telemetry=<path>` to put runs somewhere else,
  and `runs.set_enabled` inside a process. The environment outranks the keyword
  and there is deliberately no value that argues back.
- **Two locations, one spelling.** `$HOME/.rietx` is the GUI's per-user state
  and `RIETX_STATE_DIR` moves that one alone; the working directory's `.rietx/`
  is the runs root and no variable moves it. The page has to keep these apart or
  it teaches the wrong knob.
- **A project's `live/` holds one directory per run now**, so a GUI project and
  an agent fitting the same project no longer interleave one log. `files.md` was
  corrected in four words; the chapter is this WP's.
- **Retention deletes by age and size** (a 1 GiB ceiling, a week's floor, oldest
  terminal run first) and warns rather than deleting when nothing is old enough.
  A user who wants their evidence kept should be told that nothing inside the
  floor is ever removed.

From **WP-1402** (2026-09-15), whose break this WP carries:

- **`LiveSession` no longer writes `fit.html`.** It writes `snapshot.json`, and
  the break is staged in `docs/milestones/v1.4.md` § Breaks as it landed. What
  does *not* break: a `fit.html` already on disk still opens, `rietx watch`
  serves it at `/api/run/<id>/legacy` and by its bare name, and `rietx html` /
  `viz.html.write_html` are untouched — the emailable page is still a
  capability, what stopped is producing it unasked.
- **New names a chapter has to cover**: `runs.SNAPSHOT_FILE` is now
  `snapshot.json`, `runs.LEGACY_SNAPSHOT_FILE` is `fit.html`,
  `Run.has_legacy_snapshot` sits beside `has_snapshot`, and `watch.py` serves
  `/plotly.js`, `/api/run/<id>/snapshot` (JSON now, not a page) and
  `/api/run/<id>/legacy`.
- **One sentence in `using/cli.md` was corrected in place** rather than left
  false: the plot "redraws in place … keeping whatever you have zoomed into",
  where it used to say it reloads. Nothing else in the manual was touched, so
  the fuller account is still entirely this WP's.
- **What a reader can now do that they could not**: zoom into a region and watch
  that region improve across stages. Measured in chromium — the axis range is
  identical before and after a forced redraw.

From **WP-1401** (2026-09-14):

- **`using/cli.md` § `rietx watch` was rewritten already, and it is the floor
  rather than the chapter.** WP-1401 declared no manual changes and then made
  two, both for the same reason: the old text stated things the command had
  stopped doing. The usage block (mirrored in `src/rietx/cli.py`) now reads
  `watch [dir]`, and the section describes the run list, the per-run open, and
  the reading-only promise. What is still missing there is everything a reader
  needs rather than everything that was false: the liveness column and what
  `abandoned` and `unknown` mean, the four JSON routes, and how a run comes to
  exist at all. That last one is this WP's subject.
- **The routes are provisional by declaration, like the GUI's.** `watch.py`
  serves `/api/runs`, `/api/run/<id>`, `/api/run/<id>/events?offset=` and
  `/api/run/<id>/snapshot`. Nothing pins them yet, so a chapter naming them
  should say what `using/gui-quickstart.md` says about the GUI's.
- **The skill still has no row from this track, and one of WP-1401's reasons
  for that has since weakened.** It declared "none" on the grounds that the
  reader only reads what a writer already wrote, which is true of the reader.
  It is not the whole picture. `rietx watch` is useless for an agent's run
  unless the agent passed `events=`, and WP-1322 measured three subagents all
  switching telemetry off. WP-1401 then measured the cost at 1-3 % of a fit,
  which refutes the only good reason to switch it off. So there is a live skill
  rule in the gap — pass `events=`, it is nearly free — and it stays unwritten
  only because WP-1403 is expected to make it moot by recording anyway. If 1403
  slips, this row is worth writing before it.

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

- [ ] The root CLAUDE.md clause, edited to keep the rule and drop the false half.
- [ ] `using/cli.md` (both the section and the `--help` block) and
      `using/files.md`.
- [ ] `using/refining.md`, with the writes-to-disk sentence early and the sizes
      quoted from WP-1404.
- [ ] `using/compatibility.md`: the `fit.html` break and the `live/` change.
- [ ] The skill body sentence, **with its cut named in the commit message**.
- [ ] The `references/` file and its routing row, with the pinned header and the
      measurement tags; then `rietx skill --install . --copy`.
- [ ] WP-1322's Task 2 recorded as discharged, dated; WP-1133's `### Inherited`
      noted.
- [ ] Record the two deliberate refusals — no surface flag, no seventh contract
      — where a later session will find them, which is here and in the module
      docstring, not in a commit message alone.
- [ ] Skill: this WP **is** the skill task for the track.

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
