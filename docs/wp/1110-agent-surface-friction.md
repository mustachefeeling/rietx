# WP-1110 — the agent surface, measured against an agent that used it

Milestone: v1.1 · Status: ⬜
Depends on: —

## Goal

An agent driving a real refinement reaches the intended surface — the JSON task
API, the plans, the diagnostics — instead of rediscovering the package by
reading its source, and cannot silently ship a trajectory the package already
knew was unsound.

## Context

The evidence is one 3 h 20 min transcript: a capable agent, unaided, refining a
68-pattern in-situ ZrMo₂O₈ series (4 phases, Cu Kα) it had transcribed from a
TOPAS `.inp`. It is the only observation of this package being used by an agent
that did not write it, so its failures are data, not anecdotes. Nothing in it is
a bug report from a person; every item below is something the agent did, or
could not do.

**What it never touched.** Zero calls to `agent.refine_json` or
`agent.tool_definition` — the entire tool-calling surface WP-0602 exists to
provide. It never opened `docs/AGENT_PROTOCOL.md`, and never found
`docs/manual/using/agents.md`, which is the page written for it. It fetched five
doc pages (index, install, README, series, and `using/constraints.html`, **which
404s — there is no `constraints.md`**), then gave up on docs and discovered the
API by `inspect.signature`, `dir()`, `model_fields` dumps, and reading installed
source (`io/formats/bruker_raw.py`, `strategy/staged.py`, `schemas/common.py`,
`sequential.py`, `schemas/structure.py`). It ran everything as hand-written
scripts through 129 Bash calls.

The blunt read: **docs for orientation, source for the API**. A tool surface
nobody calls is not a tool surface.

### Friction, each verified against the current tree

1. **`pip install rietx` on Python 3.10 silently installs nothing.** The PyPI
   `0.0.0` placeholder declares `requires_python >=3.10`; every real release
   declares `>=3.11` (`pyproject.toml:29`). So on 3.10 pip resolves to the
   empty stub **and succeeds**. The agent lost ~5 min and three fetches before
   inferring `pip install git+…`. Yanking `0.0.0` turns a silent stub into
   pip's own "requires a different Python" error.
2. **`RefinementResult.rwp` does not exist** — it is `result.statistics.rwp`.
   The `AttributeError` fired *after* a 105 s refinement had completed, losing
   it. Verified: `rwp` is not in `RefinementResult.model_fields`.
3. **`Refinement.fitted_structure` is a property**, and calling it
   `fitted_structure()` raises `TypeError: 'Structure' object is not callable`.
   This killed an already-launched 68-pattern run and forced a `sed` patch and
   relaunch. Verified.
4. **`PLAN_PRESETS` values are factory methods, not plans**, so
   `PLAN_PRESETS[name].stages` raises `'function' object has no attribute
   'stages'`; then `Stage` is a dataclass, so `.model_dump()` raises too, in a
   package where everything else is pydantic. Verified.
5. **`Parameter.expr` is an accepted schema field that always raises.**
   `schemas/common.py:91` refuses it as "not implemented". An agent sets it,
   validation passes, and the failure arrives later. Verified.
6. **There is no evaluate-only path.** The agent wanted y_calc at known
   parameters to redraw a fit. A zero-stage plan raised a bare `AssertionError`;
   `Refinement.predict` raised `RuntimeError: call fit() first`. Its workaround
   was `set_values(...)` plus a one-stage `scale_bkg` **refit** used as a
   "replot" — i.e. it re-refined to draw a picture.
7. **`PatternData.two_theta` is a list**, so `data.two_theta.min()` raises.
   Every numeric consumer must remember `np.asarray` first.

### The silent-science failures, which matter more

8. **425 `BOUND_HIT` diagnostics went unread for two hours.** The agent invented
   its own bounds (±0.15 Å cells, `lor_size/strain max=1.0`) rather than taking
   package defaults; `phases.3.cell.c` was pinned in **42 of 68** patterns and
   `phases.3.lor_size` in **44 of 68**. The package said so from pattern 1, in
   `entry.diagnostics`, and nothing made it unmissable — the per-pattern progress
   line the agent had written showed Rwp and GoF. It inspected diagnostics only
   after two complete runs.
9. **Rwp was the running evidence channel**, exactly against CLAUDE.md's fence.
   Every mid-run judgement in the transcript is an Rwp or QPA delta. Statistics
   that were computed and never remarked on: `max_shift_over_esd = 30.4`,
   `esd_inflation = 2.77`, `rwp_background_subtracted = 0.215` against
   `rwp = 0.085`.
10. **The chain was hand-rolled, discarding the safety net.** Run 2 replaced
    `SequentialRefinement` with `for i, data in enumerate(patterns): ref =
    rx.Refinement(...)`, carrying `fitted_structure` forward by hand — *after*
    reading the docstring that describes rung escalation, quarantine and the
    `SEQUENTIAL_*` flags. It also never used `direction="both"`, on a
    temperature trajectory, where `SEQUENTIAL_PATH_DEPENDENT` is the only check
    separating a measured trajectory from an ordering artefact — and the
    observed symptoms (a precursor phase *reappearing* at 2-4.5 % at 800-830 K,
    22 % LT phase at 991 K) are what it screens for.
11. **Persistence was `pickle.dump(SeriesResult)`**, with `history=False`
    everywhere and no `Project`. The history DAG, the thing that makes a run
    restorable, was switched off for the whole 3 h.

## Tasks

Not yet ordered into commits — this WP is the finding, and its shape is a
decision the maintainer should take first. Candidates, roughly by value:

- [ ] **Yank `0.0.0` from PyPI** (item 1). One action, removes a silent-failure
      mode for every new user on an older Python. Note `docs/RELEASING.md`'s rule:
      never `twine upload` by hand.
- [ ] **Make the diagnostics unmissable in a series** (item 8). A `SeriesResult`
      that carries 425 `BOUND_HIT`s should say so where a caller cannot miss it —
      a summary on the result, not only per-entry. The design question is whether
      a bound pinned in >N % of patterns is a *series-level* finding with its own
      code, since no single entry's diagnostic conveys "42 of 68".
- [ ] **Add the evaluate-only path** (item 6). `Refinement.predict` before a fit,
      or a documented `evaluate(values)`, so redrawing a fit is not a refit.
      Retiring the `AssertionError` on a zero-stage plan belongs here.
- [ ] **Fix the API sharp edges**: `rwp` on the result (or a clear error naming
      `statistics.rwp`), `PLAN_PRESETS` values that behave like plans or are
      documented as factories, and `Parameter.expr` either implemented or
      rejected at validation rather than at use.
- [ ] **Write `docs/manual/using/constraints.md`** — a page the agent went
      looking for and that 404s. Its absence sent the agent into the source.
- [ ] **Decide why `refine_json` was not reached.** The honest possibilities are
      that it is not discoverable from the docs entry points, that a
      shell-driving agent prefers python it can compose, or that it does not
      cover the series case well enough. This is worth answering before building
      more of it: `docs/manual/using/agents.md` exists and was never found.

## Acceptance

An agent-usefulness question needs a real agent, not a deterministic proxy —
enforce the conditions in a shim rather than in the prompt. The honest test of
this WP is a fresh agent, given the same data and no help, reaching a defensible
sequential refinement without reading `src/`, and being unable to finish while
ignoring a bound pinned in most patterns.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

## Handover log

### 2026-08-20 — the transcript, read

*Done.* The transcript distilled and analysed; every friction item in the
Context section re-verified against the current tree rather than taken from the
reading (the PyPI trap in item 1 was diagnosed here, not in the log — the agent
only saw that it got an empty package).

*In flight.* Nothing.

*Next.* The task list is unordered on purpose; the last item is the one that
should be answered first, because it decides whether the others are worth doing
on the JSON surface or on the python one.

*Gotchas.* The transcript is one agent on one dataset. Everything here is a real
failure, but the *frequency* of each is unknown, and the last task's question —
why `refine_json` was never reached — cannot be answered from this sample alone.
