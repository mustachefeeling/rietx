# WP-1405 — the human stops the run

Milestone: unscheduled · Status: ⬜
Depends on: 1403 (the recorder that polls); 1401 (the page the button is on)

## Goal

A human watching a run an agent is driving can stop it, from the browser, in
another process, without corrupting anything: the in-flight stage is abandoned,
the models are restored, the completed stages are kept, and the agent's process
raises the `RefinementCancelled` it already knows how to handle.

## Context

### The seam is a file

The watcher writes `<run>/cancel`; the recorder notices and sets a `CancelToken`.
That is the whole mechanism, and it is a file rather than a socket because the
two processes already share exactly one thing — a directory — and adding a second
channel would mean the watcher could reach a fit it cannot see.

`optimize/cancel.py` is unchanged: `CancelToken` wraps a `threading.Event`
(`cancel()`, `is_set()`, `reset()`, `__bool__`), and `RefinementCancelled`
carries `.stage`, `.completed_stages` and `.node_id`. The token is read in a
residual wrapper installed **before** the event wrapper, so cancellation stays
cooperative, read between residual evaluations, and never an interrupt — which is
what keeps frozen-per-stage discreteness true.

### Composition, and the cost it ends

**If the caller passed a token, the recorder sets theirs** and never makes a
second: one authority per run for "stop". If the caller passed none, `fit`
creates one, and only when the recorder is active.

That last clause has a price, and it is this WP's alone.
`refine.py:1543-1546` short-circuits on `cancel is None` and says so in the
docstring: *"the copies are taken only when a token is present, so an ordinary
fit pays nothing."* Attaching a token so this button works ends that guarantee —
two `model_copy(deep=True)` a stage, scaling with atom count. It is configuration
3 of WP-1404's matrix, and if that row is expensive, the answer is to attach the
token lazily (only once a `cancel` file has been seen) rather than to drop the
feature. Measure before choosing.

### Polling cadence

A `stat` per residual evaluation is the same syscall problem WP-1403's buffered
flush exists to avoid, so the cancel probe **shares the flush clock**: at most
one probe per cadence. Latency is then the cadence plus the residual evaluation
in flight, which on a large pattern is the dominant term anyway. The page says so
rather than appearing to hang.

The coupling that clock hides: the recorder only gets control when something
calls it, so a probe "per cadence" is really *per cadence, at an event*. With
the shipping eval stream that is every residual evaluation and the distinction
is invisible — but WP-1403's mitigation 3 (thinning) and WP-1404's configuration
1 (stage boundaries only) both take the eval events away, and the probe would
then fire once a **stage**. On the long runs this button exists for that is
minutes, not the cadence. So the probe is hung on the *unthinned* evaluation
boundary, not on the emitted event: it is a wall-clock test in the residual
wrapper that already reads the token, and it survives whatever WP-1404 decides
about what gets written. Assert it: a test with eval events off must still
cancel within a cadence.

### What the agent's process sees, and why that is the point

Nothing new. Routing through the shipped token means a human's cancel and an
agent's own `token.cancel()` are indistinguishable downstream: the in-flight
stage is abandoned, no history node is written, no table is committed, the
structure and instrument are restored from the copies above, and
`RefinementCancelled` carries what completed. A cancelled `fit_end` carries
`status="cancelled"` and **omits** `rwp`/`gof`, because there is no fitted result
to report — which is the same open-dict rule seen from the reader's side.

The recorder additionally writes a terminal status naming the run cancelled and
**who asked**, so the watcher can distinguish a human's stop from an agent's own
in the record even though the fit cannot.

### What the confirm dialog must say

An agent that does not catch `RefinementCancelled` sees a traceback. So a human
clicking a browser button can put a traceback into an agent's session. That is
the sharpest consequence of this whole track and it belongs in the dialog, not in
a docs footnote:

- name the run and the stage in flight;
- say it raises in the process running the fit;
- say the completed stages are kept.

Two clicks, and no keyboard shortcut. WP-1406 puts the same fact in the skill
body, because an agent needs to know a `RefinementCancelled` it did not request
is not a bug in its own call.

### Three hygiene rules

- **The recorder deletes a stale `cancel` at start.** Impossible in the run-id
  layout, possible in the flat legacy one, where a leftover file would cancel the
  next fit instantly.
- **Cancel is POST only.** A GET that cancels is one prefetching browser away
  from a bad day.
- **The route resolves the run against the served root and refuses anything
  outside it.** `SimpleHTTPRequestHandler` handles traversal for static files; a
  hand-written JSON route does not get that for free, and `watch` has a verb now.

### Written so intervention can follow

The file is **request-shaped, not a flag**. A later vocabulary — pause, edit a
parameter, re-run a stage — is the same seam with more words in it, and the
recorder declines by name anything it does not know. Nothing here forecloses the
human-in-the-loop work; it is the first member of a set.

The wider seam stays where WP-1401 put it: intervention belongs in the GUI, which
already owns editing and its 409 contract, reached from the watcher's "open in
the GUI" link. This button is the exception that proves it — one verb, because
stopping a runaway is the one thing a reader cannot do from the other side.

### One question left open on purpose

Cancel ships **enabled**, with a flag to serve strictly read-only, for a reader
who is not the person who should be stopping things. The argument for the reverse
default — a flag to *enable* it — is that the button can put a traceback into an
agent's session, and making that a deliberate act is cheap. Decide it in this WP
with the dialog in front of you, and record which way and why.

### Inherited

From **WP-1406** (2026-09-15), which documented the track and found this WP's
feature missing from it:

- **WP-1406's skill body sentence is yours, and so is the cut that pays for
  it.** 1406 was chartered to add exactly one sentence to the skill body:

  > A human may be watching, and may stop you. A `RefinementCancelled` you did
  > not request is not a bug in your call: the completed stages are kept, and
  > `.completed_stages` and `.node_id` say where the work stands.

  It was **not written**, because it is not true yet. A fit raises
  `RefinementCancelled` only when its own caller passed `cancel=`; there is no
  cancel file in `runs.py`, no poll in `RunRecorder`, and `fit` creates no token
  of its own. The package's only `CancelToken()` is `gui/session.py`'s, for the
  GUI's own fits. Write it when this WP lands, and pay for it with a named cut
  per WP-1330 — 1406 paid for its routing row by cutting §6 item 23, which was
  duplicated whole in `references/abstention.md`, so that trick is spent.
- **Two manual items are yours for the same reason.** 1406's charter asked
  `using/cli.md` to describe "the cancel button and what it does to the other
  process, the read-only serving flag". Neither exists, so neither was written.
  The chapter now states reading-only as a property of how the watcher is built;
  when the flag lands it needs a row, and the cancel button needs a subsection
  saying plainly what it does to a process the reader cannot see.
- **`references/watching.md` is the file the cancel story belongs in**, not a
  new one. It is §9d, routed on "a human may be watching this fit". Row 9d.5
  already covers `abandoned`, and a cancel row sits naturally beside it. Every
  row closes with a `(Measured: …)` or `(Hypothesis: …)` tag, and the gate
  refuses a `Measured` tag that names neither a WP nor a declared corpus.

From **WP-1403** (2026-09-15), which built the run directory this WP stops:

- **The cancel path already records itself correctly.** `fit` emits `fit_end`
  with `status="cancelled"` before re-raising, the recorder projects that to a
  `cancelled` state, and `RunRecorder.close` applies a caller's state *only*
  when nothing has claimed one — so the `close("failed")` in `fit`'s exception
  path cannot overwrite it. Keep that ordering if you touch either.
- **The lock is held for the process's life and released by the kernel**,
  however the writer dies. That is what makes `abandoned` a distinct answer from
  `done`, verified end to end: a child holding it reads `running`, and after
  `kill -9` the same directory reads `abandoned` off a free lock under a
  `running` status.
- **`_abandon_on_cancel`'s short circuit still holds** (`refine.py:1560`): no
  token is attached for the watcher's sake, so an ordinary fit still pays
  nothing. Attaching one ends that guarantee at two `model_copy(deep=True)` a
  stage, scaling with atom count. **That cost belongs to this WP and is not in
  1403's numbers.**
- **A cancelled run gets no `summary.txt`**, because there is no result to write
  one from, and that absence is not an error. If this WP gives a cancelled run
  something to say, it is a new file or a status field, never a half-written
  summary.
- A cross-process stop has to find the run first. `runs.discover` plus
  `liveness_of` is that half, and `status.json` now carries `pid` and `host` —
  `host` is written, so the foreign-host rung fires rather than guessing.

From **WP-1401** (2026-09-14), which landed the reader and the app this WP adds
a verb to:

- **The watcher has no verbs at all, by construction.** `watch.py` serves GET
  only, and the page has no POST path of any kind. Cancel is therefore the first
  verb rather than one more, and the design note in WP-1401 rests on that: a
  user cannot click what is not there. Adding a second verb reopens an argument
  that was settled on the strength of there being exactly one.
- **A run id is never decoded into a path.** `runs.run_id_for` digests the
  resolved path, and `watch.py` looks an id up in what `discover` returned. A
  cancel route inherits that property for free, and must keep it: a request can
  then only ever name a directory the walk chose to offer.
- **Liveness is already a reader-side answer**, so a cancel verb has somewhere
  to report into. `runs.liveness_of` returns `running` only on a held flock or a
  live pid, and `abandoned` where the status claims `running` and the lock is
  free. A cancelled run should reach `cancelled` through `RunStatus.state`,
  which is already a terminal state the reader honours above every other rung.
- **Still true from 2026-09-13, and re-verified:** `refine._abandon_on_cancel`
  short-circuits on `cancel is None` and says so in its docstring, so attaching
  a token universally ends a guarantee the code currently makes. It now sits at
  `refine.py:1537`, with call sites at 1968 and 2079.

## Decisions taken

### Eager attachment, measured (2026-09-15)

The WP left this to WP-1404's configuration 3, which nobody has run. Measured
here instead, on this worktree's `[dev]` venv, macOS/arm64, because the question
is narrower than 1404's: what does *attaching a token* cost, not what does
recording cost.

Two components, and neither is the fit:

| what | cost |
| --- | --- |
| `_abandon_on_cancel`'s two `model_copy(deep=True)`, per stage | 132 µs at 2 atoms, 226 µs at 8, 350 µs at 16, 1.12 ms at 64, 4.44 ms at 256, 19.3 ms at 1024 |
| the solver's extra residual wrapper, per evaluation | 37 ns |

End to end on the three-stage synthetic LaB6 fit (47 evaluations, 2 atoms),
interleaved arms, n=9 each: **1.0036× median, 1.0019× on the minima**, and the
answer is bit-identical (`rwp equal: True`). The worst case the copy table
bounds — 1024 atoms over ten stages — is 0.19 s, against a fit whose residual
evaluations alone run to minutes.

So: **attach eagerly**, and `_abandon_on_cancel`'s docstring promise is
withdrawn rather than defended. Lazy attachment was the alternative the WP
named and it is worse than it looks: a token cannot be attached mid-stage —
`cancel` is bound when the stage starts — so "lazy" would mean the *first*
request after a run starts is honoured only at the next stage boundary, which
is the latency this WP exists to avoid. It buys a fraction of a percent.

This is a bound for the *token*, not for recording. WP-1404's own question is
untouched.

## Non-goals

- **No second intervention verb.** No pause, no parameter edit, no re-run. The
  request shape is prepared; nothing else is built.
- **No timeout.** `threading.Timer(30, token.cancel)` composes, and
  `optimize/cancel.py` declines to provide one on purpose.
- **No change to `optimize/cancel.py`**, to `RefinementCancelled`'s fields, or to
  the residual wrapper's order.
- **No cancel for a run the watcher did not find**, and none across hosts: a run
  on another machine reads `unknown` and offers no button.

## Tasks

- [x] The recorder's cancel poll, on the flush clock, with the stale-file
      deletion at start.
- [x] Token composition: set the caller's if there is one, else create one, and
      only when the recorder is active. Decide lazy-versus-eager attachment
      against WP-1404's configuration 3 and record the choice.
- [x] The terminal status naming the run cancelled and who asked.
- [ ] The POST route, the run-id resolution against the served root, the
      traversal refusal, and the read-only serving flag.
- [ ] The confirm dialog, with the three sentences above. Looked at, not only
      asserted.
- [ ] Tests: the cancel file sets a caller's own token rather than a second one;
      a recorded fit with no caller token still cancels; a fit with eval events
      off cancels within a cadence, not a stage; `RefinementCancelled`'s
      three fields are unchanged; a GET does not cancel; the read-only flag
      refuses; traversal is refused. Plus a `slow`-marked two-process test — a
      subprocess runs a long fit, the parent writes the file, and the child's
      exit and terminal status are asserted.
- [ ] Skill: **none here**, but this WP is what makes WP-1406's body sentence
      true. Note it in 1406's `### Inherited` when this lands.

## Acceptance

Two terminals: a long fit in one, `rietx watch` in the other. The button stops
it, the script prints its completed stages rather than a traceback from the
telemetry, and the run reads cancelled afterwards.

```sh
.venv/bin/python -m pytest tests/test_run_control.py tests/test_telemetry.py tests/test_watch_app.py
.venv/bin/python -m pytest -m slow tests/test_run_control.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1006 — cooperative cancellation, read between residual evaluations;
  `RefinementCancelled.completed_stages`; why there is no timeout.
- WP-1207 — a run started is a 200 whose failure only ever reaches the event
  stream; the precedent for what a route refuses up front against what it lets
  the worker report.
- The root CLAUDE.md § Telemetry/cancel — the in-flight stage is abandoned, no
  node, no commit, models restored.

## Handover log

- **2026-09-13** — created. The seam is a file because the two processes already
  share a directory and nothing else. The sharpest fact in the whole track lives
  here: a human's click can raise in an agent's process, so the dialog says so
  and WP-1406 puts it in the skill body. Left open on purpose: whether cancel
  should be opt-in rather than opt-out — decide it with the dialog in front of
  you.
