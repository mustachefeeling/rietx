# WP-1005 — Project container

Milestone: v1.0 · Status: ✅ 2026-07-30
Depends on: WP-1004

## Goal

A `.pxrd/` project directory that holds everything a refinement session is —
model, pattern bytes, history, UI state — creatable, openable and savable
through `Project.create/open/save`, so the GUI (and anyone else) has one
durable thing to point at instead of four loose files.

## Context

- **A directory, not a zip.** The history JSONL's crash-safety story is
  append-only writes by one writer; zipping would force rewrite-on-save and
  lose it. Layout: `project.json`, a **verbatim copy of the pattern file**
  (original bytes — the readers' esd-column semantics must survive, and
  `io/readers.py:6` says the esd column is never overridden, so the bytes are
  the contract), `history.jsonl`, `live/`, `exports/`.
- `schemas/project.py`: `DataRef` (relative filename, sha256, format,
  n_points, range); `ProjectDoc` (structure, instrument, mode, plan, limits,
  `patterns: list[DataRef]` — **length 1 in v1**, the designed-for
  multi-histogram seam — `history_file`, `ui: dict`). Schema conventions
  apply: `extra="forbid"`, `ser_json_inf_nan="strings"` — ±inf bounds must
  survive the JSON round-trip and are tested.
- `src/pxrdref/project.py`: `Project.create/open/save`. `open()` re-reads the
  pattern via `io.readers.read_pattern` (`io/readers.py:21`), checks the file
  sha256 against `DataRef.sha256`, and cross-checks
  `TreeHeader.data_fingerprint` (`schemas/history.py:213` — sha256 over
  two_theta + intensity bytes, set at `history/tree.py:60`). A mismatch is a
  **hard error**: `replay` already enforces exactly this rule at
  `refine.py:1380`, and a project that silently rebound a history tree to
  different data would be the confident-wrong-singleton failure one level up.
- `ui: dict` is deliberately untyped at this layer — the GUI owns its keys
  (Simple/Advanced toggle, panel layout); the container just persists them.

### Inherited

From **WP-1004**: `ParameterRow` and the unified `PlanSpec` in
`schemas/plan.py` are what `ProjectDoc.plan` stores — do not re-declare a
plan shape here.

Also from **WP-1004** (landed 2026-07-30): the history tree is created on the
**first `fit`/`run_stage`**, because it is pinned to its pattern by a
fingerprint — so `set_vary`/`set_values` before that change the working state
without recording a node. A project that is opened, edited and saved *without
running anything* therefore has parameter state in `project.json` that no
history node describes. Decide that deliberately: either `Project.open` forces
the tree (it has the pattern, so it can) and every edit is logged, or
`ProjectDoc` is documented as the authority for un-run edits. Note the second
half of the same asymmetry: `Refinement.parameters()` reads the models' `vary`
flags before the first stage and the recorded free set after one, so it is not a
pure function of the history head.

## Non-goals

- No multi-pattern projects (the `list[DataRef]` seam exists; length > 1 is
  a later milestone's work, alongside multi-histogram GUI).
- No server, no locking across processes — one project per process is
  WP-1008's session rule, not this container's.
- No migration tooling for foreign formats (GSAS `.gpx` import etc.).

## Tasks

- [x] `schemas/project.py`: `DataRef` + `ProjectDoc`, with the ±inf
      round-trip test alongside the existing schema tests.
- [x] `src/pxrdref/project.py`: `Project.create` (copies pattern bytes,
      computes sha256, writes `project.json`, initialises `history.jsonl`,
      `live/`, `exports/`).
- [x] `Project.open`: re-read via `read_pattern`, sha256 check,
      `data_fingerprint` cross-check — mismatch raises; re-open mid-history
      resumes at head.
- [x] `Project.save`: persists `ProjectDoc` (**settings** + ui — not model
      state, see the handover), never rewrites the pattern bytes or the JSONL.
- [x] `tests/test_project.py`: round-trip incl. ±inf bounds, fingerprint
      mismatch raises, re-open mid-history resumes at head, esd column
      survives the copy (read the copy, compare weights).
- [x] Extra, and load-bearing for the third of those: `RefinementTree.load`
      now replays records in **file order**, so a reloaded tree stands where
      the session left it (see the handover — HEAD did not survive a reload at
      all before this).
- [x] Extra: `io.readers.PATTERN_FORMATS` — the dispatch as a registry, so
      `DataRef.reader` and WP-1007's `capabilities()` arm quote it instead of
      restating it.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_project.py -q
.venv/bin/python -m ruff check src tests examples
```

Measured 2026-07-30: `tests/test_project.py` 21 passed (~1 s, one shared fit at
Rwp 0.0415 / GoF 0.79 whose PNG is in `tests/output/project_container.png`),
ruff clean, fast suite 1048 passed / 107 skipped in 33 s (the skips are the
jax/torch rows — this worktree's venv is `[dev]` only), bit-identity goldens
green, so nothing in the reader or history change moved a computed number.

## References

- `refine.py:1380` — the fingerprint-mismatch rule this container extends
  from replay to open.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.
- **2026-07-30** — **complete.** `Project.create/open/save` over a `.pxrd/`
  directory, `schemas/project.py`, 21 tests, and two things the charter did not
  ask for but the charter's own third task needed.

  *Done / decided:*

  - **The Inherited question is answered by deleting the second authority, not
    by choosing between two.** `project.json` holds the **settings**;
    `history.jsonl` holds the **model state**, and its head *is* the working
    state. So the tree is created by `Project.create` (with a root node — "undo
    everything" needs a target from the first click, and it is built from
    `snapshot()` so it records exactly what a plain `Refinement.fit` would, µR
    resolution included), every `set_vary`/`set_values` commits a node, and
    **not one parameter value is duplicated between the two files.** The
    consequence is worth repeating to a GUI author: *saving is about settings,
    not durability* — work is on disk the moment its node is appended.
  - The document therefore holds only what nothing else owns: `patterns`
    (`DataRef`), the *next run's* plan/mode/limits, `excluded_regions`,
    `history_file`, `ui`. Mode and limits are also in a node, and that is not
    the same fact — a node says what a past run used, the document says what the
    next one will, and before any run there is no node to ask. That is precisely
    why `Project.run_stage` passes `mode` **explicitly**: `Refinement.run_stage`
    defaults it to the value it carries, which before the first run is
    `"rietveld"`, so a Le Bail project driven one stage at a time would silently
    start in the wrong intensity model. There is a test named for it.
  - **`backend`/`solver` are deliberately *not* project state**, and this is a
    judgement call worth re-opening if the GUI disagrees: a project saved with
    `backend="jax"` would otherwise be unopenable on a machine without jax
    (`Refinement.__init__` fails fast by design). They are arguments to
    `Project.open`, and a GUI preference belongs in `ui`.
  - `create` takes a pattern **path**, never a `PatternData`: the bytes are the
    contract, and a caller with data in memory must write it out and thereby
    choose the format its esds live in.

  *The latent defect, and it is in the history layer:* **HEAD did not survive a
  reload**, in two independent ways, so "re-open mid-history resumes at head"
  was not implementable as written. `add()` advances HEAD in memory but appends
  no ref record, so a log written by an ordinary `fit` reloaded with `refs == {}`
  — `tree.head` None, `tree["head"]` a KeyError. And `load()` applied every node
  before every annotation, so an old `checkout` overrode the three stages
  committed after it and HEAD came back **stale** (measured: n0001 where the
  live tree stood at n0003). Records now replay in file order, which is the
  in-memory semantics of an append-only log rather than a re-reading of it. Two
  more consumers were already exposed to this — `pr.replay(tree, "head", …)` on
  a loaded tree, and anything reading `RefinementTree.load(...).head`.

  *Two findings for whoever touches the pattern seam:*

  - **The reader *call* is part of the data reference, not just the path.** A
    pdCIF holding both a `_meas` and a `_calc` block reads as a different
    pattern depending on `block`, and `read_pattern` picks the first block that
    parses. Recording only the filename made an SRM-660c-shaped project
    *unopenable* (the fingerprint check fires, correctly) rather than wrong.
    `DataRef.reader`/`.options` fix it, `read_pattern` grew a `block=`
    passthrough, and `PATTERN_FORMATS` is where the dispatch now lives.
  - **Two digests answer different questions.** sha256 of the bytes catches an
    edit in place; the parsed-array fingerprint catches a *reader* change — same
    bytes, different numbers — and their disagreement is diagnostic rather than
    corruption. Each failure raises with its own message and its own test.

  *Gotchas:*

  - `tests/test_portability.py` flags **any** `.open()` by attribute name, so
    `Project.open` tripped the encoding guard. Fixed by adding the receiver to
    `_NOT_FILE_IO` — a name list that goes stale in the safe direction (a new
    non-file `.open` fails loudly until someone adds the row).
  - The shared fixture runs the real `mccusker_default` preset, not a two-stage
    stub. A partial plan converges to a *bad* fit by construction (dropping the
    zero-shift stage alone leaves a derivative-shaped residual on every peak),
    and a PNG that always looks wrong cannot show that something *is* wrong.
    It costs 0.5 s.
  - `excluded_regions` are in the document because they are in neither the
    pattern file nor `RefinementState`. Excluding a region does **not** rebind
    the history (the fingerprint is over the measured arrays), which is
    convenient and also means a node cannot say what was excluded when it ran —
    pushed forward to 1003 (freeze: does `RefinementState` grow the field?) and
    1009 (the text document must print them).
