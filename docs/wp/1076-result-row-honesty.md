# WP-1076 — A result row's unwritten fields

Milestone: v1.0.x · Status: ✅ 2026-08-18 — every task line ticked across all four groups: `at_bound` is three-valued and projected from the one bound test (`staged.bound_findings`, now shared with `multi.py`), `initial` and `RefinementResult.correlation_warnings` deleted, `TieSpec.from_tie` made private, `"skipped"` off both status `Literal`s and `"lebail_update"` off `NodeKind` with its two consumers, `BACKEND_UNAVAILABLE` repaired in **both** directions it was wrong in, and `SeriesResult` given a single `index` column and a reachable `backward` chain; `SCHEMA_VERSION` 0.1 → 0.2, once, for the removals, and 1.0.2 gains the first breaking entry 1.0.x has had. **The `deferred-1.0.x` bucket is empty**, which closes [1067](1067-user-api-manual.md)
Depends on: WP-1067 (which found it, and left both names provisional)

## Goal

**No declared name asserts something the package never does.** Two shapes, one
rule. A *field* whose empty state reads as an answer — `at_bound: false` on a
parameter nobody checked — and a *vocabulary member* whose presence names a
mechanism that does not exist — a `"skipped"` status no code path produces.
Both tell a reader something untrue, and neither fails a test, because an
absent writer is invisible to every guard in the tree.

The head case is `RefinedParameter`: `at_bound` becomes a real answer, sourced
from the one place that already computes it, with `None` for its unmeasured
state; `initial` goes, because the start of a fit has an authority already and
it is not the result. Seven more of the same class arrived from WP-1067's
chapters and are settled here (§ The same shape, elsewhere) — including the two
that, with these, are the last four names in the `deferred-1.0.x` bucket and so
gate [1067](1067-user-api-manual.md)'s ✅.

## Context

`RefinedParameter` (`src/rietx/schemas/results.py:13`) is the row type of
`RefinementResult.parameters`. It declares six fields. The fit populates four:

```python
# src/rietx/refine.py:1822 — the single-histogram builder.  It is NOT the only
# one: multi.py:338 and :347 build rows of their own, and this file said "the
# only place" until the WP was picked up and the constructions were counted.
for e in table.entries:
    if e.vary or e.tie is not None:
        params.append(RefinedParameter(
            path=e.path, value=e.value, vary=e.vary,
            stderr=stderr_phys.get(e.path)))
```

`initial` and `at_bound` are never written, and **nothing in the package reads
either** (verified 2026-08-17 across `report/`, `viz/`, `agent.py`,
`textdoc.py`, `project.py`, and the GUI; every other `at_bound` in the tree is
either `indexing/peakfit.py`'s per-peak array or `GuardFinding.at_bound`, both
of which work and are unrelated). No test asserts on either field, and no
on-disk fixture carries them.

**The defect is the empty state, not the absence of a writer.** Both fields
serialize, so every consumer of a result sees:

```json
{"path":"phases.0.cell.a","value":10.2512,"stderr":0.0000627,
 "initial":null,"vary":true,"at_bound":false}
```

`initial: null` reads correctly as "absent". `at_bound: false` reads as **an
answer** — "this parameter is not against a bound" — and it is not one. It says
nothing, always, including for a parameter that refined hard onto its bound.
A tool-calling agent reading the envelope cannot tell the difference, and
`docs/AGENT_PROTOCOL.md`'s table tells that agent not to quote a bound-sitting
parameter as a measurement.

That is this repo's own most-quoted rule one rank down: **a quantity that cannot
be measured is absent rather than zero** (WP-1072, McCusker §10, root CLAUDE.md).
`False` is the boolean zero and it is being used as "no information".

**The fact is already computed, once, and correctly.** `strategy/staged.py:688`
tests every free path against its internal bounds with a span-relative tolerance
and appends a `GuardFinding`, which becomes the `BOUND_HIT` diagnostic:

```python
lo, hi = table.bounds()
for k, path in enumerate(free):
    t = outcome.theta[k]
    span = hi[k] - lo[k]
    tol = 1e-8 * (span if np.isfinite(span) else 1.0)
    if (np.isfinite(lo[k]) and t - lo[k] <= tol) or (np.isfinite(hi[k]) and hi[k] - t <= tol):
        report.at_bounds.append(GuardFinding.at_bound(path))
```

So the row's flag must be a **projection of that one computation, never a second
one**. `_build_result` already receives the guard report at three of its four
call sites (`refine.py:1219`, `:1309`, `:1379`); the fourth (`:2485`) does not,
which is exactly why the flag needs a third state rather than a default.

This follows the `evidence`/`trajectory` precedent (root CLAUDE.md): a derived
view rides *beside* the answer, computed once. It is not a second authority for
the bound fact, and `BOUND_HIT` stays the reported diagnostic.

### The design decision, already taken (2026-08-17, user)

Taken with the freeze explicitly set aside: the package has no users yet, so
breaking changes and extra work were declared acceptable and the choice was made
on robustness alone.

- **`at_bound: bool | None = None`**, populated from the guard report. The
  reason for `None` over a required `bool` is that it cannot regress into a lie:
  a future `_build_result` path that forgets to populate it yields "no
  information", which is true, rather than "not at a bound", which may not be.
  Forcing every call site to pass the flag is the weaker fix, because the field
  can be made to lie again by anyone who passes `False` for convenience.
- **`initial` is deleted.** Never written, never read, and its own docstring
  names its replacement: "the start lives one node up in the history tree". One
  authority per fact, and the history tree is it. A caller assembling a result
  by hand can still record a start state; it just does not belong on this row.

### What this costs elsewhere

- `RefinedParameter` is on the **frozen** surface as of WP-1067's chapter,
  except for these two names, which that chapter deliberately left provisional
  so this WP would be free (`docs/manual/using/model.md`, and the 1.0.2 notes
  say why). So neither change is a freeze violation.
- Under `docs/manual/using/compatibility.md`, deleting a field is a **breaking
  event** that moves the schema contract version, and changing what `at_bound`
  answers is a **documented event** even though its shape barely moves. Both
  need release notes; check whether `SCHEMA_VERSION` moves once, for the pair.
- Eight `RefinedParameter(...)` constructions in `tests/` pass neither field, so
  the default keeps them compiling; deleting `initial` breaks nothing there.

### The same shape, elsewhere in the package

WP-1067 wrote a manual chapter over each of these types, and **writing over a
type is what found them** — seven, across five chapters, none visible from the
code alone. Every one is measured rather than inferred, and every one is left
as it stands in the manual with a written warning, because the decision is
this WP's. Three are fields; four are vocabulary members. Two of them —
`correlation_warnings` and `TieSpec.from_tie` — are, with `initial` and
`at_bound`, the four names in the `deferred-1.0.x` bucket, so settling them is
what lets 1067 tick ✅.

#### The fields

- **`RefinementResult.correlation_warnings`** (`schemas/results.py:633`,
  `list[str]`) — measured: `correlation_warnings` appears in `src/`, `tests/`
  and `gui/src` in exactly **one** place, its own declaration. Nothing writes
  it and nothing reads it, so it serializes as `[]` on every result. That is
  the `at_bound: false` argument word for word: an empty list reads as "no
  correlations were flagged" when the truth is "this field is not filled in",
  and the correlations *are* computed and reported (as `HIGH_CORRELATION`
  diagnostics, and on `Identifiability`). So the honest options are the same
  pair as `initial`'s: delete it, or populate it from the guard that already
  has the findings — and if it is populated, from `GuardFinding` rather than a
  second rendering, since `str(finding)` is the published text.

- **Two on `SeriesResult`, and the second is a gap rather than a dishonest
  field.** Both were found by running the eight-mixture round-robin series and
  reading what came back. Neither is in the provisional bucket any more — that
  chapter froze `SeriesResult` in full — so a change to either is a
  compatibility event under `using/compatibility.md`, which is why they are
  decisions here rather than fixes in passing.
  - **`SeriesResult.to_table` emits two columns called `index`.** The header is
    `index, label, <x_label>, status, rung, rwp, gof, …` and `x_label` defaults
    to `"index"`, so a series run without a coordinate — the default — produces
    a duplicate column name. Measured: `['index', 'label', 'index', 'status',
    …]`. Anything keying by name collides (pandas silently renames the second to
    `index.1`); anything keying by position is fine. The chapter states it as a
    warning rather than working around it, because the fix changes a written
    file's header and `write_csv` is the same header.
  - **`SeriesResult.n_iterations` does not count what `direction="both"`
    cost.** It sums over `entries`, and with `direction="both"` the entries are
    the forward chain only — measured 816 for both a forward run and a `"both"`
    run whose wall clock was 83.7 s against 33.7 s. The docstring says "Total
    least-squares iterations over the whole series", which is true of a
    one-directional run and false of this one. **The related gap:** the backward
    `SeriesResult` exists only as `SequentialRefinement.backward_`, so a caller
    using `refine_sequential` — the one-shot API the chapter recommends —
    receives the `SEQUENTIAL_PATH_DEPENDENT` diagnostics and has no way to reach
    the trajectory they are about. Either the count is documented as
    forward-only, or the functional API grows a way to return both; the two are
    different decisions.

- **`TieSpec.from_tie` is public by accident, and there is nothing honest to
  say about it.** It is a classmethod converting a `params.vector.AffineTie`,
  which is **not itself on the public surface**, so documenting it would either
  name a private type in a frozen chapter or describe a converter without
  saying what it converts. Three shapes: delete it, make the source type
  public, or keep it and exclude it in `tests/api_surface.py` with the reason —
  an exclusion is not a freeze, and the exclusion list is the honest home for
  "public by accident of being a classmethod". 1067's acceptance counts an
  exclusion as settled, so any of the three empties the bucket.

#### The vocabulary members

Here the defect runs the other way: nothing is missing from an instance, and a
*declared value* is what asserts the mechanism. It costs a reader of the type,
who infers a mechanism that does not exist, and a consumer writing an
exhaustive match, who handles a branch that cannot occur. Removing a value no
writer produces cannot break a producer — only a consumer that matched on it.

- **`StageResult.status`'s fourth value.** The `Literal` admits `"skipped"`,
  and the solver produces only `converged`, `max_iter` and `diverged`
  (`optimize/least_squares.py:639` and `:785` are the two constructions, both
  three-way). Grepped across `src/`: nothing anywhere sets it. This one is a
  *value* rather than a field, so it costs a reader differently — a consumer
  writing an exhaustive match handles a branch that cannot occur, and a reader
  of the type infers a skip mechanism that does not exist. It is also the
  cheaper fix, since removing a value from a `Literal` no writer produces
  cannot break a producer, only a consumer that matched on it.
  **It is declared twice** (found while writing `using/history.md`):
  `NodeMetrics.status` (`schemas/history.py:195`) carries the same four-value
  `Literal`, filled from the same `outcome.status`, so whatever this WP decides
  has to be decided for both. `NodeMetrics.status` is already `| None`, and
  `None` is what a node that ran no fit carries, so the spare value has no
  meaning left to take there either.

- **`NodeKind`'s `"lebail_update"`, and this one already has consumers.**
  `NodeKind` (`schemas/history.py:40`) admits it, and **no code path commits
  such a node**: grepped across `src/`, every `NodeAction(kind=…)` construction
  is one of the other seven (`root`, `stage`, `set_vary`, `set_value`,
  `set_tie`, `edit_model`, `merge`). A Le Bail stage refreshes its intensities
  inside itself, and the refreshed values are part of the `stage` node's
  `ReflectionState`, so there is nothing left for a node of this kind to record.
  It differs from `"skipped"` in the direction that costs more: two consumers
  are already written against it. `NodeAction.api_call` renders
  `ref.lebail_update(n_cycles=…)`, **a call that does not exist on
  `Refinement`** — the log's "this is the API call that would repeat it" promise
  is false for that branch — and `gui/src/lib/history.ts:133` has a `case
  "lebail_update"` labelling the node `Le Bail ×N` in the history panel.
  Removing the value is therefore a three-file change rather than a one-line
  one. `using/history.md` documents the field with the vocabulary as it stands
  and says plainly that no verb commits this kind, which is the honest reading
  until this WP decides.

- **`AgentError.code`'s `BACKEND_UNAVAILABLE` cannot fire, and unlike the two
  above the mechanism it names is real.**
  `AgentError.code` (`agent.py:461`) is a three-value `Literal`, and
  `BACKEND_UNAVAILABLE` is documented — in the module docstring, in the tool
  description and in the chapter's table — as "a valid backend name whose
  optional dependency is not installed". **Measured on a `[dev]` venv with no
  jax**: a valid `task="refine"` request with `backend="jax"` comes back
  `REFINEMENT_FAILED`. `refine_json` maps `NotImplementedError` to
  `BACKEND_UNAVAILABLE` (`agent.py:635`), while `backend.api.resolve_backend`
  raises **`ImportError`** for both jax and the two torch devices
  (`backend/api.py:660` and `:670`), so the request falls through to the
  generic `except Exception`. The install hint survives in
  `AgentError.message`, but `AgentError.suggestion` is the generic
  engine-raised one, and a consumer branching on the code — which is what the
  code is for — cannot tell a missing extra from a model the physics refused.
  This is the `"skipped"` shape with the sign flipped: there the value has no
  mechanism, here the mechanism exists and the mapping misses it, so the fix is
  a repair rather than a deletion. **The only test that covers the code asserts
  the mapping and never the condition** —
  `test_backend_unavailable_is_its_own_code` monkeypatches `Refinement.__init__`
  to raise `NotImplementedError` and says so in its own docstring ("Forced via
  the constructor's fail-fast path rather than uninstalling jax"), which is the
  `_SURFACE_FLAGS` shape again, in a test rather than in a predicate. And the
  repair is a decision: catching bare `ImportError` around the dispatch would
  also swallow an unrelated missing import, so the honest options are to narrow
  the raise (`resolve_backend` raising `NotImplementedError`, which changes what
  the *library* raises), to catch the error where the backend is resolved, or to
  answer the question before dispatch from `BackendCapability.available`.
  `AgentError.code` is frozen as a vocabulary and all three options keep it;
  what moves is which value a real missing extra produces.

## Non-goals

- **No new bound-related diagnostic, and no change to `BOUND_HIT`.** The guard
  is correct and stays the reported channel; this WP only projects it.
- **No second bound computation.** If the flag cannot be sourced from the guard
  report at a given call site, it is `None` there. Recomputing it locally is the
  bug this WP exists to avoid.
- **No audit of other schemas' defaults.** Whether any *other* field's empty
  state asserts a measurement is a real question and a separate one; if this WP
  notices candidates it lists them in its handover rather than fixing them.

## Tasks

**A. The head case — `RefinedParameter`.**

- [x] `at_bound: bool | None = None` on `RefinedParameter`, with the docstring
      saying what each of the three states means and that the source is the
      guard, never a local recomputation.
- [x] Populate it in `_build_result` from `guard.at_bounds` (one set of paths,
      built once), leaving `None` when no guard was passed. Check all four call
      sites and say in the commit message which ones can supply it. **`multi.py`
      builds its rows itself** (`:338` and `:347`), which is a fifth and sixth
      construction the WP's original count missed, and it already runs its own
      copy of the bound test (`:365-372`, a duplicate of `staged.py:688`) — so
      the single-source rule bites there first.
- [x] Delete `initial`, and grep for readers before and after rather than
      trusting this file's claim that there are none.
- [x] Tests: a real fit's rows carry `True`/`False` and not `None`; a fit with a
      parameter driven onto a deliberately tight bound reports `True` on
      **exactly** the paths `BOUND_HIT` names, which is what pins the projection
      to its single source; a hand-built result with no guard reports `None`.

**B. The three remaining bucket names — what lets 1067 close.**

- [x] **Settle `RefinementResult.correlation_warnings`** — delete, or populate
      from `guard.high_correlations` via `str(finding)`.
- [x] **Settle `TieSpec.from_tie`** — delete, export `AffineTie`, or exclude it
      in `tests/api_surface.py` with the reason.
- [x] `docs/manual/using/model.md` documents `at_bound`'s three states, and
      every settled name leaves the provisional bucket (regenerate
      `tests/api_surface_deferred.txt` in the same commit; the acceptance is an
      **empty** bucket, header only). **Two existing passages point here and
      must be rewritten, not appended to**: that chapter's § "What a fit reports
      back" carries a paragraph naming this WP by URL and telling the reader to
      use `BOUND_HIT` instead, and `docs/releases/1.0.2.md` § "The freeze"
      carries a paragraph explaining why these names were left provisional.
      Deleting a field also means the notes gain a **breaking** entry, the first
      1.0.2 has had — check whether `SCHEMA_VERSION` moves, once, for the set.
- [x] `docs/AGENT_PROTOCOL.md`: the `BOUND_HIT` row gains the machine-readable
      form of the same rule, since an agent iterating parameters now has a
      per-row flag rather than a path cross-reference.

**C. The vocabulary members.** Each is a decision this WP was asked to take;
each carries a written warning in a manual chapter that has to be rewritten
with it, and `EVENT_SCHEMA_VERSION` is untouched (no `EventKind` moves).

- [x] **`"skipped"` on `StageResult.status` and `NodeMetrics.status`** — both,
      or neither.
- [x] **`"lebail_update"` on `NodeKind`** — with `NodeAction.api_call` and
      `gui/src/lib/history.ts` if it goes.
- [x] **`BACKEND_UNAVAILABLE` in `agent.refine_json`** — a repair, not a
      deletion, plus a test that asserts the *condition* and not the mapping.

**D. `SeriesResult`.** Both are frozen-surface changes; take the decision and
say which classification it is.

- [x] **`to_table`'s duplicate `index` column** — rename or document.
- [x] **`n_iterations` under `direction="both"`** — document as forward-only, or
      give the functional API a way to return the backward chain.

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -n auto --dist loadgroup        # full: schemas/results.py is source
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_docs_consistency.py
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m ruff check src tests examples
```

The full suite is not optional here: this WP edits `schemas/results.py` and
`refine.py`, so it can move a measured number, and `--durations` plus the
passed/skipped delta are what show it did not.

## Handover log

- **2026-08-18 (the whole WP, one session)** — thirteen task lines across four
  groups, on `wp1076-result-row-honesty`. **`### Inherited` pruned on arrival**
  and every one of its seven claims re-verified against the tree before folding,
  so nothing was deleted as stale; the mailbox became § "The same shape,
  elsewhere in the package", split into the fields and the vocabulary members,
  and the "arrived from chapter X" framing dropped. Two defects in the WP file
  itself came out of that read: **`## Non-goals` had lost its heading** and its
  three bullets were sitting inside `### Inherited` (the file cites its own
  § Non-goals two hundred lines up), and the Context code block called
  `refine.py:1822` "the only place these rows are built" when `multi.py:338`
  and `:347` build them too.

  **Done.** *A* — `at_bound` is `bool | None`, projected from `guard.at_bounds`
  at both row builders; `staged.bound_findings` is now the one bound test, with
  `multi.py`'s duplicate copy of the loop deleted. *B* — `initial` and
  `RefinementResult.correlation_warnings` deleted, `TieSpec.from_tie` →
  `_from_tie`, `using/model.md` documents the three states, and **the
  `deferred-1.0.x` bucket is empty**, which closed
  [1067](1067-user-api-manual.md). *C* — `"skipped"` off `StageResult.status`
  and `NodeMetrics.status`, `"lebail_update"` off `NodeKind` with both its
  consumers and a GUI dist rebuild, and `BACKEND_UNAVAILABLE` repaired. *D* —
  `SeriesResult.to_table` emits one `index`, and `SeriesResult.backward` makes
  the reverse chain reachable from `refine_sequential`.

  **The scope grew on arrival and that was the right call.** § Goal was written
  about two fields on `RefinedParameter`; the mailbox had collected seven more
  findings, from five Part 1 chapters, all the same defect in one of two
  directions. Settling four and leaving five would have left the WP's own rule
  half-applied. Nine defects, and **every one was found by writing a manual
  chapter over the type** — none by reading the code, which is now the standing
  rule in root CLAUDE.md (cap 700 → 720, with the reason at the cap entry).

  **Numbers** (`[dev]` venv — no jax, no torch; darwin/arm64, Python 3.12.12).
  Fast selection **2408 passed / 117 skipped**, against a **2402 / 117**
  baseline measured on this session's starting tree — +6, exactly the six tests
  added at that point, and passed+skipped moved by 6 with no new skip. Three
  more landed after that measurement (two agent, one series), and one existing
  test was rewritten rather than added. Wall clock is not comparable run to run:
  the same 2402/117 baseline took 3:46 here and 2:27 in the previous session.
  Full-suite figures are in the closing measurement below. vitest **407 passed**
  (19 files), `svelte-check` 372 files 0 errors, `sphinx -W` clean, `ruff`
  clean.

  **Measured while working**, all on real data unless said otherwise.
  11-BM NAC Le Bail 2–24°: 31 rows, 13 measured `False`, 18 `None`, and the 18
  are exactly the symmetry-tied rows (`cell.b`, `cell.c`, 16 coordinates).
  Same protocol in Rietveld: 72 table rows / 32 result rows, 14 free + 18 tied,
  Rwp 0.1403. Capping `cell.a` at 10.2500 against a free optimum of 10.2513:
  one `True`, set-equal to `BOUND_HIT`, Rwp 0.2068 Rietveld and 0.2194 Le Bail.
  `replay` of the same node: 31 rows, all `None`. Joint two-histogram: 45 rows,
  27 measured, 18 `None`. Agent envelope on this `[dev]` venv, before the
  repair: `backend="jax"` and `backend="torch"` both `REFINEMENT_FAILED`; a
  soft-restrained `refine_multi` on `backend="numpy"` `BACKEND_UNAVAILABLE`
  advising `pip install 'rietx[jax]'`. After: `BACKEND_UNAVAILABLE` with the
  right extra, and `REFINEMENT_FAILED` naming soft restraints.

  **In flight: nothing.** Working tree clean.

  **Next.** Nothing on this WP. It carried no forward references into another
  WP's `### Inherited`, because it emptied its own mailbox rather than filling
  someone else's, and § Non-goals' "no audit of other schemas' defaults" was
  not attempted — the nine settled here all arrived by measurement from a
  chapter, and a systematic sweep for the same shape in the ~90 remaining
  schema types is a separate WP if anyone wants it. The one thing a successor
  should know is that **[1078](1078-indexing-provisional.md) will un-freeze
  part of what 1067 froze**, which is a decision and not a regression against
  this WP's empty bucket: names will re-enter the provisional tier by
  declaration.

  **Gotchas.**

  - **The third state has two causes, and the WP's own analysis had one.** The
    file argued `None` from `replay` having no guard. The other is a **tied**
    row: `ParameterTable._free_idx` is `e.vary and e.tie is None` while the row
    filter is `e.vary or e.tie is not None`, so a tied row is in `parameters`
    and was never in the free vector the guard tested. Its value follows its
    sources and can sit on its own declared bound while every source is
    interior. Reporting `False` there would have been the original defect with
    a new cause, and it is the *common* case — 18 of 31 rows on the walkthrough
    fit, against 0 for `replay` in an ordinary session.
  - **The WP said "all four call sites" and there are six.** `_build_result`
    has four; `multi.py` builds `RefinedParameter` rows itself at `:338` and
    `:347`, and carried its own copy of the bound-test loop. A count in a WP's
    Context is a claim someone made once — re-grep it. Same lesson as the
    `initial` task line, which explicitly says to grep for readers rather than
    trust the file, and that one was written by the author who had already got
    the sibling count wrong.
  - **`BACKEND_UNAVAILABLE` was wrong in the direction nobody was looking.**
    The inherited finding was that the code could not fire. Measuring it found
    the arm *also* firing on the wrong thing: `NotImplementedError` is raised
    by unsupported feature paths, so a soft-restrained joint fit — no optional
    dependency anywhere near it — was told to install jax. The inherited half
    would have been fixed by narrowing the raise; only measuring what the arm
    actually catches finds the other half.
  - **A test can pin a mapping and never the claim, and stay green for the
    code's whole life.** `test_backend_unavailable_is_its_own_code`
    monkeypatched `Refinement.__init__` to raise `NotImplementedError` and said
    so in its own docstring. It asserted the arm, the arm was wrong, and no
    real request could ever produce the code. That is `_SURFACE_FLAGS` one rank
    over (WP-1037), in a test rather than in a predicate. The rewrite makes a
    real request on whichever backend the venv genuinely lacks, and **skips**
    on `[dev,jax,torch]` — a skip is the honest outcome when the condition does
    not exist locally, and a monkeypatch is how that skip gets hidden.
  - **The obvious assertion would have passed against the bug.** "The flagged
    parameter really is at its bound" is true of a *second* bound test in
    `_build_result` — the exact thing the WP forbids. Only set equality against
    the `BOUND_HIT` diagnostics pins the flag to its single source.
  - **A CSV header is a set of keys and `x_label` is a label.** `to_table`
    named its axis column after `x_label`, which defaults to `"index"` — the
    name column 1 already had. The tempting fix, renaming the default to `"x"`,
    pays for a header collision with a worse plot axis title. The column falls
    back to `x` only when its label is already taken.
  - **The full suite was launched once on a tree that was not final, and
    killed.** A diff review afterwards found a provably dead ternary in
    `_missing_backend` and a rule that belonged in CLAUDE.md. Restarting cost
    ~5 minutes of machine time; finishing would have produced a number about a
    tree that no longer existed. `tests/CLAUDE.md` § Running names this exact
    failure as the whole of one session's ~80-minute overspend, and the trap is
    that "the tree is final" feels true before the diff has been read.

## References

- WP-1067's 2026-08-17 (`using/model.md`) handover entry — where this was found,
  and why the draft chapter's description of `at_bound` was wrong twice over
  (the mechanism *and* an unsourced interpretation of the esd).
- Root CLAUDE.md, WP-1072's bullet — "a quantity that cannot be measured is
  absent rather than zero", the rule this WP applies to a boolean.
- `docs/manual/using/compatibility.md` § How a change is classified — a change
  to what an existing value means is never silent.
