# WP-1110 — the agent surface, measured against an agent that used it

Milestone: v1.1 · Status: 🔄 2026-08-20
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
provide. It never opened `docs/AGENT_PROTOCOL.md`, and never reached
`docs/manual/using/agents.md`, which is the page written for it.

**That page is not missing, which is the uncomfortable part.** It sits in the
toctree at `docs/manual/index.md:110`, the manual's front page carries a "For
agents" admonition (`index.md:30`), and the chapter opens on exactly the two
calls this agent needed: "Two calls carry the whole integration surface.
`capabilities()` says what this build can do; `agent.refine_json` does it." The
agent *did* call `capabilities()`, and still never called `refine_json`. So the
fix is not more documentation. The candidates are that the chapter's title —
"Calling rietx from a program" — does not read as the machine-facing entry
point to something scanning an index; that an agent driving a shell prefers
python it can compose over a JSON envelope it cannot inspect midway; or that
`refine_json` does not cover the series case it needed. It fetched five
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
5. **`Parameter.expr` is a declared field that always raises.**
   `schemas/common.py`'s `_check_bounds` refuses it as "not implemented".
   **Corrected 2026-08-20**: the refusal is a `model_validator(mode="after")`,
   so it fires *at construction*, not later at use — the first reading of this
   item was wrong, and the message it raises is a good one, naming the affine
   tie block as the alternative. What survives is narrower and still real: a
   declared field that can only ever raise advertises a capability the package
   does not have.
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

12. **`rietx.__version__` does not exist.** The universal python convention
    for "what am I running" raises `AttributeError`. The answer is
    `capabilities().package_version`, which a caller can only reach by already
    knowing about `capabilities()`. Found by this session's own first move,
    not by the transcript — which is the point: it is the first thing anyone
    types. Verified.

## The decision, taken 2026-08-20 by a real-agent round

The last task below was the one the others depended on, and it is answered:
six Sonnet agents on this dataset, `tests/eval_agent_surface/PROTOCOL.md`
round 1.0, registered before any run. Headlines, with the full record there:

- **Neither unaided agent reached `refine_json`** (R1 = 0 of 2), and both
  called `capabilities()` first. The transcript is not one agent's bad day.
- **Told about it, one agent adopted it and one declined** (R2 split 1 of 2).
  N = 2 makes the disagreement visible; it does not resolve it, and nothing
  here pretends otherwise.
- **The tool-calling half has no consumers.** `agent.tool_definition()`,
  `request_schema()` and `response_schema()` were called **zero times in every
  cell across 235 traced interpreter starts**, including both cells *required*
  to drive the fit through `refine_json`. All 25 `refine_json` calls came from
  agents calling it as an ordinary python function inside a python script,
  having read its contract from the manual or from source.

So the question "why was `refine_json` not reached" had a false premise. It is
reachable, it is sometimes chosen, and it works when chosen — `mandated-1` fixed
a real ρ≈1.000 degeneracy off its diagnostics and got its esds back. What no
coding agent in this round wanted is the **JSON Schema export**: an agent with a
shell writes python, and a caller in python already holds the objects.

**Two of this WP's own claims were wrong and are corrected**, which is the
reason to trust the rest. `refine_json` does **not** cost a serialisation round
trip — it accepts live `Structure`/`Instrument`/`PatternData` objects in the
dict. And item 5's "validation passes, the failure arrives later" is false;
`Parameter.expr` raises at construction.

What survives, stated by `mandated-2`: driving a fit through `refine_json`
"still required importing `rietx` itself for the plan object model, not just the
JSON surface." **Everything expensive is upstream of the call** — no `.inp`
reader, no path to a CIF, a `Structure` built by hand, a `PlanSpec` built in
python to patch one stage of a preset. Paying that puts you in python.

**Therefore the investment belongs in the python surface's ergonomics and its
diagnostics**, and `refine_json` is for MCP callers and process boundaries
rather than for coding agents — the branch this WP pre-registered, reached on a
split rather than a sweep, and reported as such.

### Found by the round, and not in the list above

Each is a real failure of an agent doing real work on the trigger dataset.

13. **A phase at zero scale has its cell freed, and the cell runs away.** Two
    agents independently: a ≈ 39 293 Å and a ≈ 40 000 Å, refused several stages
    downstream by `generate_reflections`. `Structure.from_cif` gives cell bounds
    `(0.1, ∞)`; a phase with no intensity has no gradient there, so TRF steps
    freely in a near-null direction. The scale is already at its floor when the
    cell stage turns the cell on. A default cell bound of ~±5 % taken from the
    CIF's own starting cell needs no third-party number.
14. **A good fit can return `esd: None` for every parameter.** Rwp 0.081,
    GoF 1.13, visually clean, not one usable esd: two parameters legitimately at
    their softplus zero contribute zero-gradient columns that poison the single
    whole-vector covariance inversion. Dropping them broke convergence and cost
    15× the wall clock.
15. **The plan types are two.** `PLAN_PRESETS` and `capabilities().plans` hand
    back `strategy.staged.RefinementPlan`/`Stage` (dataclasses); a request wants
    `schemas.plan.PlanSpec`/`StageSpec` (pydantic). Same field names. Passing a
    preset straight in returns `INVALID_REQUEST`, and both mandated agents had
    to rebuild it field by field. This is item 4 with teeth.
16. **`refine_json` cannot express a tie.** WP-1070's `tie`/`tie_equal` has no
    counterpart in a request, so the `.inp`'s shared `boverall` across 15 atoms
    was inexpressible through the JSON surface.
17. **A VT reel's temperature is not public.** `read_pattern` does not surface
    it, so an agent read `_Range.temperature_k` off the private
    `bruker_raw._parse()` to recover 318/323/333 K. On an in-situ series the
    series coordinate is the point of the experiment.
18. **`bound_findings`' relative tolerance misfires on wide bounds.** With scale
    bounds `[1e-14, 1e14]` the `1e-8 × span` tolerance is enormous, so the scale
    read as "at its bound" at every stage. `Parameter.positive()` reproduced an
    identical Rwp to six figures and cleared it.
19. **There is no TOPAS `.inp` reader**, so every agent transcribed the model by
    hand — including inferring that a missing backtick means "fixed". All six
    named this as the hardest part. A mistyped coordinate stays symmetry-valid
    and fails silently.
20. **The wheel ships the maintainer's rulebooks.** An agent read
    `rietx/io/CLAUDE.md` "shipped inside the package tree, not just the repo".
    `src/rietx/io/CLAUDE.md` sits under the package directory, so it is packaged.

**Item 8 and item 10 did not reproduce.** Every agent that met a `BOUND_HIT` or
a `HIGH_CORRELATION` read it and either acted or said why not, and two reached
for `refine_sequential` unprompted rather than hand-rolling a chain. The
transcript's silent-science failures are not what this surface does to an agent
by default — which is worth as much as any of the items above.

## Tasks

The decision above is taken, so these are now ordered. Candidates, by value:

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
- [ ] **Make a guessed page name land somewhere.** The agent fetched
      `using/constraints.html` and got a 404 — but constraints *are* documented,
      in `using/concepts.md:137` (`tie`/`tie_equal`/`untie`, the affine form,
      the fnmatch globs). Nothing is missing; a plausible guess simply misses,
      and this one sent the agent into `schemas/common.py`. The cheap fix is a
      `constraints.md` that is one `{ref}` to the concepts section, and the same
      for any other name a caller would guess. Same class as the item above:
      the content exists and is not being reached.
- [ ] **Decide why `refine_json` was not reached** — the question the others
      depend on. The chapter exists, is linked from the front page, and names
      the call in its first two sentences (Context above), so "write more docs"
      is already refuted. Answer it with a real agent, not by reasoning: give
      one the same data and watch where it goes. If the answer is that a
      shell-driving agent will always prefer composable python, then the
      investment belongs in the python surface's ergonomics and its diagnostics,
      and `refine_json` is for MCP callers rather than for coding agents.

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

### 2026-08-20 (second session) — the round run, and the premise corrected

*Done.* The decision item answered with real agents, not by reasoning:
`tests/eval_agent_surface/PROTOCOL.md` round 1.0 — three conditions, N = 2,
sonnet, on the trigger dataset itself, registered and committed **before any
run**. The Results section carries every number; § The decision in Context
carries what it settled. Also: eight new friction items (13-20), all found by
an agent doing real work, and two of this WP's own claims corrected.

*Measured.* R1 = **0 of 2** — neither unaided agent reached `refine_json`,
replicating the transcript. R2 = **split, 1 of 2**, and it stays split: N = 2
was declared as a device for making a disagreement visible, not for measuring
a rate, so no branch of the decision rule is claimed as swept. The result that
decided the WP is one neither read-out asked for: `agent.tool_definition()` /
`request_schema()` / `response_schema()` were called **zero times in every
cell across 235 traced interpreter starts**, including both cells *required*
to use `refine_json`. All 25 `refine_json` calls were python function calls
inside python scripts. Test counts: this session ran the fast selection on
`[dev]` in this worktree; the numbers are in the closing block below.

*In flight.* Nothing running. The eight new items and the six original ones
are unstarted; the Tasks list is now ordered because the decision that ordered
it is taken.

*Next.* Item 13 first — the zero-scale cell runaway, hit independently by two
agents, refused several stages downstream of its cause, with a fix
(`Structure.from_cif` defaulting cell bounds to ~±5 % of the CIF's own cell)
that needs no third-party number. Then 15 (the two plan types) and 17 (the VT
temperature), both of which cost every agent real time. **Do not start with the
JSON surface**: the round says a coding agent's investment is the python one.

*Gotchas.* (a) The round's own instrument had two defects, both now recorded
in PROTOCOL.md and one fixed: the shim wrapped without `functools.wraps`, so
an agent saw `rietx_surface_trace.py` and went to source (fixed); attribution
by cwd measured almost nothing and was replaced by binding a pid through the
data-file path (fixed in `score_round.py`, and round 1.1 should give each cell
its own venv instead). (b) **The experiment venv had no matplotlib**, so four
of six agents hand-rolled an SVG plotter. That is a workspace defect of mine,
not a finding about the package, and nothing is concluded from it. (c) The
dataset is the maintainer's, fetched from a Durham URL, and is **not committed
anywhere in this repo** — re-running the round means fetching it again. (d)
`pointed-1`'s abandoned `refine_sequential` (pattern 2's `refit="single"`
collapse past 150 s unfinished, `cell` stage 22 s on 4 phases) is a **speed**
datum on a trigger-shaped model; it is pushed to WP-1111 and does not belong
here. (e) The reader fix that opened the dataset (`552f3e18`) is real work
outside this WP's list — the trigger file was refused by `read_pattern` before
it, so no round was possible without it.

### 2026-08-20 — the transcript, read

*Done.* The transcript distilled and analysed, and every friction item in
Context re-verified against this tree rather than carried over from the reading.
Two of those checks **changed the WP's conclusion**, which is the main reason to
trust the rest of it:

- `using/agents.md` is not missing and not unlinked. It is in the toctree at
  `docs/manual/index.md:110`, the front page carries a "For agents" admonition,
  and the chapter's first two sentences name `capabilities()` and
  `agent.refine_json`. The agent called `capabilities()` and still never called
  `refine_json` — so "write more docs" was refuted before any work started.
- Constraints are documented too, in `using/concepts.md:137`. The 404 was a
  *guessed* page name missing content that exists.

The PyPI trap (item 1) was diagnosed here, not in the log: the agent only saw
that it got an empty package. `curl`ing the JSON index showed `0.0.0` declaring
`requires_python >=3.10` against `>=3.11` on every real release, which is why
pip resolves to the stub on 3.10 and *succeeds*.

*Measured.* Nothing — this WP landed no code. The session's counts belong to
WP-1109 and are in that WP's entry.

*In flight.* Nothing.

*Next.* The task list is unordered on purpose, and the **last** item should be
answered first: it decides whether the rest is work on the JSON surface or on
the python one. Answer it with a real agent given the same data and no help —
`agent-usefulness means real agents`, and a deterministic proxy cannot see the
choice this WP is about.

*Gotchas.* (a) The transcript is **one agent on one dataset**. Every item is a
real failure, but the *frequency* of each is unknown and nothing here should be
quoted as a rate. (b) Do not act on the friction list by adding documentation
without reading the two corrections above first — that is the conclusion this
session started with and had to abandon. (c) The evidence transcript is the
maintainer's local file, outside this repo; the distilled form was scratch and
is not preserved, so re-deriving any claim means re-reading the original.
