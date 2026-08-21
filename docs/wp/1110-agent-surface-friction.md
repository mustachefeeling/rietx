# WP-1110 — the agent surface, measured against an agent that used it

Milestone: v1.1 · Status: 🔄 2026-08-21 — shaped by a real-agent round; fifteen friction items closed or answered and **all ten task lines ticked, so no code task remains**. Held open, not closed, for the maintainer: item 5 is a `SCHEMA_VERSION` release-home decision, and items 16/19/20 are round findings with no task line. Closing it is a call about milestone ordering (the speed chain 1112 → 1115 is ahead of all of it), which is why this session did not take it
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
    15× the wall clock. **Fixed 2026-08-21, and the symptom was recorded the
    wrong way round** — the inversion did not withhold esds, it invented small
    ones. § Item 14 has the mechanism and the numbers.
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
    identical Rwp to six figures and cleared it. **Fixed 2026-08-21**: the
    tolerance is now relative to the closest bound's own magnitude, quoted from
    scipy's `active_mask` rule rather than chosen. § Item 18 has the numbers,
    including why `positive()` cleared it.
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

## The cell window, measured

Item 13's fix needed two numbers the WP did not have: where the bound should
live, and how wide. Both were settled against prior art and measurement rather
than picked.

**TOPAS bounds cell parameters by default and rietx did not.** TOPAS-Academic v8
Technical Reference § 2.17, Table 2-1: `a, b, c` are held to
`Max(1.5, 0.995·Val − 0.05)` … `1.005·Val + 0.05` and the angles to `Val ± 0.2`,
with `Val` the **current** value — *"hard limits are avoided where possible;
instead, parameter values move within a range during an iteration."* It also
flags parameters that stopped near a limit (`_LIMIT_MIN_#`/`_LIMIT_MAX_#`),
which is `BOUND_HIT`/`at_bound` under another name, and it floors a cell length
at 1.5 Å where rietx floored it at 0.1. **GSAS-II is the opposite**: limits are
optional and user-supplied with no defaults (`Controls['parmMinDict']`), and a
parameter that passes one is clamped **and frozen** into `Controls['parmFrozen']`,
per histogram in a sequential run.

**A moving window is not available here**, because a stage hands
`scipy.optimize.least_squares` one fixed `bounds` pair. So it re-anchors per
*stage* — the table is rebuilt at stage compile and `apply_to_models` writes back
only `Parameter.value`, so the window never enters the stored structure and a
cell that legitimately drifts across a series re-anchors on every stage of every
pattern. That makes the fraction a stage's worth of TOPAS travel rather than an
iteration's: 0.5 %/iteration compounds to 5.1 % over ten.

**Measured for the other side of the choice**, on this tree:

| case | worst single-stage relative cell move |
|---|---|
| 11-BM NAC + SRM 660c, 51 stage transitions | 2.8e-4 (p90 8.3e-5, p50 9.2e-8) |
| synthetic LaB₆ started 1 % wrong, recovers to 3.4e-7 | 9.9e-3 — one stage closes the gap |
| started 3 % wrong | fit fails on its own (Rwp 0.96): the basin, not any bound |

So ±5 % clears the widest legitimate single-stage move by 5× and the
real-protocol one by 180×, and no fit that can converge at all is inside it.
Re-measured **after** the window landed, the recovery cases are unchanged to
every digit — 0.1 %, 0.3 % and 1 % all still reach err 3.4e-7 with the same
per-stage moves, and 3 % still fails at Rwp 0.96. The window did not narrow
what the fit can recover from.

**A window is not free, and applying it to every phase broke a real fit.** This
is the correction that shaped the final design, and it was caught by the full
suite rather than by reasoning. Windowing every cell regressed the chained IUCr
round robin at `cpd-1c`: corundum came back **9.04 wt %** against 6.30
independent and against the participant spread, failing three acceptance rows
that pass on main.

The cause is not the bound being reached — `cpd-1c`'s cell finishes at 4.75759,
a quarter of an ångström inside a ±5 % window it never touches. It is that
**scipy's TRF takes its per-coordinate trust-region scale from the distance to
the bounds**, so bounding a cell changes the step taken in it regardless. A
width sweep on that pattern:

| window | Rwp | corundum wt % | iterations |
|---|---|---|---|
| unbounded (main) | 0.1079 | 6.30 | 641 (ladder escalated to the full staged plan) |
| **±5 %** | **0.1501** | **9.04** | **400, `warm_refit` hit `max_iter`** |
| ±10 % | 0.1078 | 6.26 | 82 |
| ±25 % | 0.1078 | 6.26 | 87 |
| ±50 % | 0.1078 | 6.22 | 100 |

±5 % is a cliff, not a gradient. And the way it failed is this WP's own subject:
the collapsed warm refit exhausted its budget and stopped at Rwp 0.1501, which
is *inside* `sequential`'s reseed fence (1.25 × the 0.1519 median of the
accepted patterns), so the ladder never escalated and the pattern was accepted
rather than rescued. The fix for a silently unsound trajectory had produced one.

**So the window is spent only where the alternative is a flat direction** — the
phases `CompiledModel.phase_support` puts below 1σ, the same measurement
`PHASE_UNCONSTRAINED` reads, frozen onto the table by
`optimize.least_squares._freeze_cell_windows` at stage compile. A phase the data
can see is left unbounded, exactly as before.

**What it does and does not change.** The runaway: 5.2 → 25.6 Å unbounded (Rwp
0.0415, status `converged`), 81.9 Å with the window disabled on the same
construction, ~5.0 Å with it — and 1.8 s → 0.3 s, because a runaway cell
enumerates reflections (30 at a = 5.2 Å, 1 825 at 25.6, 93 618 at 100, refused
above ~1 000). An honest fit is **bit-identical**: on the 11-BM NAC two-phase
protocol run both ways in one process, all **44 of 44** refined values and Rwp
agree to the last bit, because neither phase (571σ and 185σ) is windowed at all.
That is the equivalence bar v1.1 asks for, and it is exact rather than a
tolerance. Indexing acceptance: 44 passed, no ranking moved. Sequential
acceptance: 13 passed.

**One finding deliberately not acted on here.** The same sweep shows ±10 % and
wider *beating* unbounded on `cpd-1c` — 82 iterations against 641, same answer —
because finite bounds precondition a badly scaled problem (cells sit at ~4.8
while scales are ~1e-5 and background coefficients ~1e2, and TRF is given
`x_scale=1.0`). That is a real v1.1 speed lead and it belongs to the harness
WPs: a correction does not ship on a timing comparison any more than on an Rwp
one, and this one's evidence is a diagnostic. Pushed to WP-1112's `### Inherited`.

**The window alone would not have saved the trigger run**, and that is why the
diagnostic is not optional. Re-anchoring means the cell walks ≤5 % per stage
instead of stopping at a wall, so it ends *inside* the final stage's window and
`BOUND_HIT` need never fire: measured, the drift falls from +393 % to −5.8 %
across the plan with nothing reporting it. Reaching 39 293 Å from ~10 Å at 5 %
a stage takes ~170 stages, which a 68-pattern series has. `PHASE_UNCONSTRAINED`
is what closes that, and `SEQUENTIAL_PERSISTENT_FINDING` is what makes it
legible across the series rather than 68 times over.

## The two plan types, and the accident underneath them

Item 15 read as an inconvenience — a request refuses a preset, so rebuild it
field by field. Reproduced on this tree it is worse than that, and the worse
half was found by testing the *other* direction.

**Both directions were broken, and only one of them said so.** Passing a
`RefinementPlan` to `refine_json` adds two validation errors over passing the
equivalent `PlanSpec` (six against four, with the same empty models) — loud,
and what both mandated agents hit. Passing a `PlanSpec` to `fit(plan=...)`,
against an annotation reading `RefinementPlan | str`, **ran**: a five-stage
`profile_only` fit on the synthetic pattern returned Rwp and all its refined
values bit-identical to the same fit driven by the dataclass. It works because
`PlanSpec`/`StageSpec` share *every* field name with the dataclasses and a plan
is only ever read. That is an accident of two types agreeing, not a contract,
and it ends the first time a stage grows a field or a consumer calls a method.

So the crossing is by `isinstance` on the real class, never by duck-typing on
`.stages` — a structural test would have certified exactly the accident above.
And it lives at the two authorities that already own the mirror rather than at
any call site: `PlanSpec`/`StageSpec` validate the dataclass inbound,
`resolve_plan` converts the spec outbound. `agent.py` dropped its own copy of
the conversion at the same time; the GUI's `_as_plan_argument` keeps its
`to_plan()`, because that call is *validating a raw JSON dict*, which is a
different job from crossing between two live objects.

**Two error messages carry the rest of item 4**, on the WP's own thesis that an
error message is the documentation an agent reads. `PLAN_PRESETS[name].stages`
said `'function' object has no attribute 'stages'`, naming neither the registry
nor the call; it now names the call and says why the entry is a builder (a plan
is a mutable dataclass, so a shared instance would carry one caller's edit to
the next). `Stage`/`RefinementPlan` are the package's only *schema-shaped*
objects that are not pydantic models — a record of fields sitting beside a
`PlanSpec` that mirrors it one for one, unlike `Refinement` or `Project`, which
are plainly machines — so `.model_dump()` is the natural next keystroke, and it
now names the mirror. The factory wrapper carries
`functools.update_wrapper`, so `help()` and `inspect.signature` still reach the
builder — round 1.0's own instrument lost an agent to the source over a wrapper
that did not.

**The other formats hold no specimen temperature** (item 17), checked rather
than assumed: `.rasx`'s `CW_Temperature1`/`CW_Temperature2` are the cooling
water and `RE_EnclosureTemp` is the cabinet, and `bruker_absorber.brml` has no
temperature field at all. The Bruker `.raw` v3 range header is the one field
here that the format itself names, so it is the one that is surfaced. Reading a
specimen coordinate off an axis named for something else would be inventing a
convention — the one repair a reader may never make.

## Item 18 — the denominator was the bug

The tolerance was right to be relative and wrong about what to. `theta` is the
*internal* vector, where a softplus width and an identity cell edge share no
scale, so an absolute tolerance means a different thing in every column — that
much of the original reasoning holds. What does not is dividing by the **span**:
the span is a statement about how generous the *far* bound was, and it grows
without limit while the value stays where it is.

**The transcript's numbers.** `Parameter(value=1.0, min=1e-14, max=1e14)` is how
an agent spells "do not constrain this". Span 1e14, times `1e-8`, is a tolerance
of 1e6 — so every value below a million read as sitting on the floor. On the
11-BM NAC rietveld fit with that one declaration changed, `phases.0.scale` was
flagged in **5 of the 5 stages** while refining to **10.25**, fourteen orders of
magnitude from either end. After: **0 of 5**. Rwp is **0.15327** both ways,
because a diagnostic never enters the solve.

**Why `Parameter.positive()` "cleared" it**, which the item recorded as a fact
without a mechanism. `positive()` builds `min=0.0, max=inf` with a softplus
transform, and `internal_bounds` maps a lower bound ≤ 1e-12 to −∞. The internal
span is then infinite, the old rule fell back to its absolute 1e-8, and nothing
fired. The escape was the *transform*, not the bounds — which is why it looked
like a fix and was a coincidence: the same wide bounds under the identity
transform every hand-built `Parameter` gets by default still misfired.

**The replacement is quoted, not chosen.** `BOUND_HIT_RTOL = 1e-10` with the
threshold `rtol × max(1, |bound|)` against the **closest** bound is
`scipy.optimize._lsq.common.find_active_constraints` — the predicate TRF itself
uses to fill `OptimizeResult.active_mask`. Two things follow that picking a
number would not have bought. The diagnostic and the solver reporting on the
same column cannot disagree, which is testable through the public `active_mask`
and is tested. And the value is calibrated to something real: how far
`make_strictly_feasible` pushes an iterate off a bound it is against, so the
rtol is not a guess about "close enough". Scipy's *nearer bound wins* clause
comes across too — on an interval narrow enough for both thresholds to cover it,
which bound is named is then decided by where the value sits rather than by
which branch was written first.

**Nothing moved on the package's own defaults**, measured rather than argued:
old and new rules agree column for column across all five stages of a defaults
NAC fit. The whole change is the removal of a false positive that only a
caller's own wide bounds could reach — and reaching it was the reasonable thing
that caller did.

`BOUND_HIT_REL_TOL` was deleted rather than aliased. It is undocumented,
unexported and not in the API surface, so an alias kept "for compatibility"
would have been a declared name with no reader, which is the shape WP-1076
exists to refuse.

## Item 14 — the esds were not missing, they were small

**The reported symptom cannot happen, and finding that out was the finding.**
`esd: None` on *every* parameter needs `stderr_internal is None`, which needs no
Jacobian at all — `compute_uncertainties` is never passed `False` anywhere in
the package, and a pattern always has more rows than columns. So the transcript
did not see esds withheld. It saw esds it could not use, and the reason is worse
than absence.

**What actually happens.** `np.linalg.pinv` discards every eigenvalue below
`rcond × |λ|max`. The cutoff is therefore set by the *largest* column and
applied to all of them, and a discarded direction is returned with **zero**
variance — not infinite. On the NAC fit measured here the column 2-norms ran
**4.8e-06 to 8.5e+06**, thirteen orders, and **4 of 17** directions were thrown
away. `phases.0.gauss_size` came back **6.1e-14 ± 9.9e-11**, a figure anyone
would quote; the equilibrated inverse says **± 4.3e+08**. `instrument.profile.y`
moved by ×2.2e+17, `lor_size` by ×3.5e+05, `lor_strain` by ×142, `profile.w` by
×51. Every well-determined parameter — cell, scale, all six background terms —
agreed to four figures across the change, which is the shape a real fix has.

**The proof needs no dataset.** An esd must not depend on another parameter's
units: Biso in Å² or in 1e-4 Å² is the same fit. Rescaling one column of a
synthetic 400×4 problem by 1e6 moved the *other three* esds by a **factor of
two** under the old inversion and by **4e-16** after. That is
`test_an_esd_does_not_depend_on_another_parameters_units`, and it is the one
test here that could not have been written by looking at the output.

**Jacobi scaling is the fix and is not a tuning choice.** van der Sluis (1969),
Numer. Math. 14, 14-23: scaling a symmetric positive definite matrix to unit
diagonal comes within a factor of its order of the best possible diagonal
conditioning. On the NAC matrix it took the discarded directions from 4 of 17
to 1 of 17.

**Then the honest empty state had to survive being propagated**, which took
three attempts and is the part worth carrying forward. A gradient-free column
has infinite variance — true, and the true value is the unusable one. Written
into `Cov_free` it meets a zero coefficient at every turn: an off-diagonal
correlation of exactly 0, a `C` row that does not use the column, a geometry
partial that is zero there. Each is `0 × inf`, a NaN, and one NaN in `Cov_free`
reaches **every** row of `C @ Cov_free` sharing any source with it. The rutile
geometry table lost all six Ti-O bond esds to `instrument.profile.y`, a
parameter no bond depends on. Two dead ends before the right shape: clamping the
variance to zero reinstates the original lie one layer up, and guarding the
multiply with `where=corr != 0` fixes only the first of the four places.

**So the column is dropped from the arithmetic and named separately**
(`ParameterTable.unmeasured_free` / `unmeasured_rows`), and **every consumer
marks rather than clamps**:

- a **tied** row inherits its source's blindness, through `C` rather than
  through a second rule — a tie whose source measured nothing measured nothing;
- a **geometry** row is `None` only when its own partials touch a blind entry,
  so an unmeasured profile term costs no bond its esd, and `_sigmas` gains a
  fifth way to have no number beside WP-1072's four;
- **QPA** drops the *whole* block, not one phase's row: W_i normalises by
  Σ S_j M_j V_j, so one unmeasured scale makes an unmeasured sum, and every
  other phase's fraction would otherwise be reported to the precision it would
  have had if this phase were known. It is the same phase `PHASE_UNCONSTRAINED`
  names — item 13's runaway and item 14's blind column are one specimen.

**It found a real defect in the peak list, which is the part I did not
predict.** `normal_covariance` has a second consumer — `indexing.peakfit`, per
its own docstring — and the equilibrated inverse promptly broke three indexing
acceptance rows. The cause was not the change: on the certified corundum
pattern two of 62 components refine to intensities of **2.1e-49** and
**5.5e-19**, so neither has any gradient on its own position (a peak reaches its
window only through intensity × profile — item 13's rule again), and their
position esds are ~1e+17 and ~1e+49 degrees. The old pseudo-inverse truncated
both to **0.06°** and the pipeline consumed them as ordinary measured lines;
`_max_index` built from them reached a trial index of **3.1e+25**, where
`trial_hkl` raised. So the phantom lines were always there and equilibration is
what made them visible.

`_prune` cannot reach them and says so: it tests only *shoulder* seeds, by
deliberate asymmetry, because a maximum-detected component already cleared a
height test on the data. One that clears detection and then refines to nothing
is never reconsidered. Hence `no_intensity`, a `PeakFlag` that **is** in
`PEAK_UNUSABLE_FLAGS` — unlike `background_extrapolated` or `axial_tail`, which
report evidence because a consumer might still judge the line real; there is
nothing left to judge here. Its test is item 18's `BOUND_HIT_RTOL`, imported
rather than restated.

**Flagged, not dropped, and the GUI is what settled that.** My first version
dropped the component, which made the peak editor's add verb silently do nothing
on a component a human had just placed — caught by `test_gui_peaks`. Flagging
also gives `not_separable`'s reason: a report must be able to say why a line
went. A human can still clear the flag, which `gui/peaks.py` already supports.
A vocabulary member is a contract change even where every prior value still
means what it did (the 1.1 precedent), so `INDEXING_THRESHOLDS_VERSION` is
**1.3**, and the GUI highlighter's meta-test failed until `rxt.ts` restated it.

**The indexing row improved.** `test_a_certified_lab_pattern_indexes_and_is_graded_honestly`
reads **50 of 52** lines where it read 51 of 55 — one fewer indexed, *two*
fewer unindexed, `indexed_fraction` **0.927 → 0.962**. The certified lattice
still ranks first with the right centring and both axes stay inside 150 ppm. A
line that was never a line cannot be indexed, so counting it in the denominator
only ever depressed that figure of merit.

**Unchanged, checked rather than assumed.** The manual's geometry-esd figure
reproduces its own printed numbers exactly — `mccusker_structural`, Rwp
**0.08177**, **88** distances, diagonal/full ratio **0.86-1.41** — so the
chapter's text and the committed figures stand. The regenerated PNGs differed by
under 0.2 % of their bytes, including `impurity-peak`, which no esd can reach;
that is rendering noise and they were restored rather than committed.

## Three items that are not code changes, and why

Reproduced and costed 2026-08-21. Two of them cannot be fixed at the API level
at all, and saying so is worth more than leaving them on a list as though they
were pending work.

**Item 5 — removing `Parameter.expr` is a data-contract break, and its release
home is the maintainer's call.** The item is already satisfied as written
("rejected at validation rather than at use" — item 5's own correction
established that). What is left is the narrower judgement that a declared field
which can only ever raise advertises a capability the package does not have,
and the trigger agent did dump `model_fields`. Measured cost, which the WP did
not have: `model_dump()` writes `"expr": null` into **every** persisted
parameter — 22 occurrences in one small LaB6 structure — so under
`extra="forbid"` a removal makes every existing `history.jsonl` and
`project.json` unreadable. It is doable safely: a `mode="before"` validator that
drops a legacy `expr` key when it is `None` and raises the current (good)
message when it is not, plus `SCHEMA_VERSION` 0.2 → 0.3. That is the same class
of change as WP-1076's two removals, which is the precedent. What is **not**
decidable here is which release carries it: 1.0.2 is written and unreleased and
already carries 0.1 → 0.2, while `pyproject` is at `1.1.0.dev0`. Two options,
both costed: remove with the migration (≈6 lines, one schema bump, one manual
row, one new test), or keep the seam — DESIGN.md holds a design for it and the
`value`/`vary`/`min`/`max`/`expr` shape is the cited lmfit convention.

**Item 3 — `fitted_structure()` is not fixable, and the alternative is worse.**
`Refinement.fitted_structure` is a one-line alias property returning
`self.structure`; the `TypeError: 'Structure' object is not callable` is raised
by python on the returned model, not by anything this package controls. It
could be intercepted by giving `Structure` a `__call__` that raises a better
message — and that would make `callable(structure)` **True**, which is a lie
any duck-typing consumer would believe. Turning the property into a method
converts the observed typo into a non-failure and creates its mirror for
whoever omits the parentheses, on a name the v1.0 freeze covers. A property is
the right shape for a zero-cost alias, so it stays. What actually cost the
transcript its 68-pattern run was not the `TypeError` but that nothing had been
persisted when it fired — which is **item 11**, and is where the fix lives.

**Item 7 — `data.two_theta.min()` is a python error about a list.** The
`AttributeError` comes from `list`, so there is no rietx hook on the path at
all. `PatternData.tt`, `.y` and `.sig` are the numpy views and are documented as
such (`using/data.md`). Nothing to do, recorded so it is not re-opened.

## Tasks

The decision above is taken, so these are now ordered. Candidates, by value:

- [x] **Yank `0.0.0` from PyPI** (item 1) — **done 2026-08-21** by the
      maintainer, the one action in this WP no session could take. Verified from
      the index: `0.0.0` is `yanked=True`, and it was the only release declaring
      `requires_python >=3.10` — 1.0.0 and 1.0.1 both declare `>=3.11`. pip
      excludes a yanked version from a range, so `pip install rietx` on 3.10
      now reaches 1.0.1 and reports its own "requires a different Python"
      rather than resolving the empty stub and succeeding.
- [x] **Make an esd mean something** (item 14) — **done 2026-08-21**. The
      normal matrix is Jacobi-equilibrated before the pseudo-inverse, so the
      rcond cutoff stops being set by the largest column, and a direction the
      data does not move reports **no** esd rather than a small one. The
      reported symptom was the wrong way round: the inversion invented tiny
      esds, it did not withhold them. § Item 14 has the numbers, the
      units-independence proof, and the three consumers that had to learn to
      mark rather than clamp. It also **found a defect in the peak list**: two
      phantom components on the certified corundum pattern that only became
      visible once the inverse stopped truncating their esds, now flagged
      `no_intensity` (`INDEXING_THRESHOLDS_VERSION` 1.3). Not on the task list
      before this session, because the list predates the round that found the
      item.
- [x] **Stop the bound diagnostic crying wolf** (item 18) — **done 2026-08-21**.
      The tolerance was a fraction of the bound *span*, so declaring a
      parameter unconstrained made it read as pinned; it is now a fraction of
      the closest bound's own magnitude, quoted from the rule TRF uses to fill
      `active_mask`. § Item 18 has the 5-of-5-to-0-of-5 measurement. Not on the
      task list before this session, for the same reason.
- [x] **Stop the zero-scale cell runaway, and name it** (item 13) — **done
      2026-08-20**. `params.vector.cell_window` is a default per-stage window on
      every cell parameter, in TOPAS's shape and at stage granularity;
      `PHASE_UNCONSTRAINED` names the phase the data cannot see. § The cell
      window has the numbers. Not on the task list before this session, because
      the list predates the round that found the item.
- [x] **Make the diagnostics unmissable in a series** (item 8) — **done
      2026-08-20**, and the design question is answered: yes, it is a
      series-level finding with its own code. `SEQUENTIAL_PERSISTENT_FINDING`
      counts each (code, path) over the entries and states the fraction once,
      above **half** the patterns — a change of subject rather than a tuned
      sensitivity, since above half a finding describes the series rather than
      some of its members. Verified to reproduce the episode's own numbers.
      It aggregates whatever fired rather than a list of codes, so a new code
      is summarised on the day it lands.
- [x] **Give a series its own coordinate** (item 17) — **done 2026-08-21**.
      `read_pattern` and `list_scans` both surface the temperature a `.raw` v3
      range records; § The two plan types' last paragraph has what the other
      formats hold. Not on the task list before this session, because the list
      predates the round that found the item.
- [x] **Add the evaluate-only path** (item 6) — **done 2026-08-21**.
      `Refinement.predict` takes a `PatternData` or a 2θ array and needs no
      fit; only the no-argument form still does, because only a fit supplies a
      grid. The zero-stage `AssertionError` is a refusal at the top of `fit`
      that names `predict`. § Three items that are not code changes has what
      the two `predict` forms do *not* share, measured.
- [x] **Fix the API sharp edges** — **done 2026-08-21**, except one item that
      turns out to be a decision rather than a task. `PLAN_PRESETS` (items 4/15,
      § The two plan types), `rietx.__version__` (item 12), and
      `RefinementResult.rwp` (item 2): the nested number is answered with its
      path, derived from the live annotations, as a **pointer and not an
      alias** — forwarding the value would promote a dozen nested names to
      frozen public API. `Parameter.expr` (item 5) is left open on purpose: it
      is a `SCHEMA_VERSION` break whose release home is the maintainer's, and
      § Three items that are not code changes carries both options costed.
- [x] **Make a guessed page name land somewhere** — **done 2026-08-21**.
      `using/constraints.md` is a signpost, not a third copy: two `{ref}`s to
      the concepts sections that carry the reference (both now explicit
      targets, so a heading rewording breaks the build rather than the link),
      plus the one distinction worth stating where someone arrives not knowing
      which word they want — a constraint removes a parameter, a restraint
      keeps one and charges for disagreeing. Any *other* guessable name is
      still open, and there is no way to enumerate them except by watching
      more agents miss.
- [x] **Decide why `refine_json` was not reached** — **done 2026-08-20**, by
      the registered six-agent round rather than by reasoning (§ The decision).
      The question's premise was false. It *is* reached once an agent is told,
      by one of two `pointed` agents; what has no consumers is the **exported
      schema** — `tool_definition()`/`request_schema()`/`response_schema()`
      called zero times in every cell across 235 traced interpreter starts,
      including both cells required to use `refine_json`. The branch this WP
      pre-registered is the one taken: **the investment belongs in the python
      surface's ergonomics and its diagnostics**, and `refine_json` is for MCP
      callers and process boundaries rather than for coding agents.

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

### 2026-08-21 (second session) — two ways a fit lied about its own reliability

A refinement can now be trusted about what it did *not* measure. Before this,
a parameter the data said nothing about came back with a small, quotable esd,
and a parameter you had deliberately left unconstrained came back reported as
pinned against its bound. Both were failures in the flattering direction: the
package looked more certain than it was, in exactly the places where a person
most needs it to say so. Neither was visible in Rwp, in a test, or in a
warning. The cost of fixing the first is that some esds are now absent where
they used to be numbers, and one figure of merit in indexing moved — upward,
because two of the lines it was scored against were never lines.

The last of that is the part worth carrying: fixing the esds **found a defect
nobody was looking for**. Two components on the certified corundum pattern had
been published as measured diffraction lines for as long as the peak fitter has
existed, and could not have been seen until the covariance stopped hiding them.

*Done.* Items **1**, **18** and **14**; all ten task lines are now ticked.

- **Item 1** (yank `0.0.0`) is the maintainer's, done by them, verified from
  the index rather than taken on trust: `0.0.0` is `yanked=True` and was the
  only release declaring `requires_python >=3.10`. `pip install rietx` on 3.10
  now reports its own "requires a different Python" instead of resolving an
  empty stub and succeeding.
- **Item 18**: `bound_findings` measured "on its bound" as a fraction of the
  bound *span*, so `Parameter(min=1e-14, max=1e14)` — how a caller spells "do
  not constrain this" — bought a tolerance of 1e6. The denominator is now the
  **closest bound's own magnitude**, quoted from
  `scipy.optimize._lsq.common.find_active_constraints`, which is the predicate
  TRF itself uses to fill `active_mask`. Quoting rather than choosing buys two
  things a number could not: the diagnostic and the solver cannot disagree
  about a column, and the rtol is calibrated to how far `make_strictly_feasible`
  pushes an iterate off a bound. § Item 18.
- **Item 14** was **recorded the wrong way round**, and finding that out was
  the finding. `esd: None` on every parameter cannot happen — it needs no
  Jacobian at all, and `compute_uncertainties` is never passed `False` anywhere
  in the package. The real failure is the opposite and worse: `pinv` cuts
  eigenvalues at `rcond × |λ|max`, so the largest column sets the cutoff for
  all of them and a discarded direction returns at **zero** variance. The
  normal matrix is now Jacobi-equilibrated first (van der Sluis 1969), a
  gradient-free column carries infinite variance, and every consumer **marks
  rather than clamps**. § Item 14.
- **The peakfit consequence** (§ Item 14's second half): `no_intensity` is a
  new `PeakFlag`, in `PEAK_UNUSABLE_FLAGS`, tested with item 18's own
  `BOUND_HIT_RTOL`. `INDEXING_THRESHOLDS_VERSION` 1.2 → **1.3**, a vocabulary
  member being a contract change on the 1.1 precedent.

*Measured.* This checkout's own venv, **`[dev]` (no jax/torch), darwin/arm64**:

- Fast selection **2573 passed, 117 skipped**, from **2558 / 117** at this
  session's start on `origin/main`. **Fifteen** tests added, fifteen new passes,
  **no new skip** — 3 (item 18, in `test_result_rows.py`) + 10 (item 14, the
  new `test_covariance_scaling.py`) + 2 (the flag, in `test_peak_picking.py`).
- Full suite, same venv and platform: **2682 passed, 126 skipped in 28:37**,
  zero failures and zero errors, against the previous session's **2667 / 126**
  — **+15**, the fast delta exactly, since none of the fifteen is `@slow`;
  skips unchanged. It fired **three** times, and only the last is the record:
  the first two were on trees that item 14's own consequences then changed.
- `tests/test_acceptance_indexing.py` alone, **44 passed**, after CLAUDE.md's
  rule about running it before closing anything near an engine. Earning that
  took two runs: the first came back 3 errors and is what led to the peak list.
- GUI: **407 vitest passed**, `svelte-check` 0 errors, dist rebuilt.
  `ruff` clean over `src tests examples`; `sphinx -W` clean.
- **Looked at, not only counted** (`tests/output/` is gitignored, so this is a
  record rather than an artefact): the corundum pattern drawn with the usable
  lines and the two `no_intensity` ones marked. Both land where there is no
  peak — **116.71°** in the valley between the 116.1 and 117.85 lines, and
  **124.91°** on the descending tail of the 124.57 line — while every usable
  line sits on one. That is the check a count cannot make, and it is what
  turns "the fit says these have no intensity" into "there is nothing there".

*Equivalence bars, both measured rather than argued.*

- **Item 18 moves nothing on the package's own defaults.** Old and new rules
  agree column for column across all five stages of a defaults NAC fit. The
  default scale is `Parameter.positive()`, whose softplus lower bound goes to
  −∞ internally and so never met the span rule — which is also the mechanism
  behind the item's note that `positive()` "cleared" the report. The escape was
  the *transform*, not the bounds, so it was a coincidence.
- **Item 14 moves nothing that was determined.** Cell, scale and all six
  background terms agree to four figures. The SRM 660c acceptance row
  reproduces **byte-for-byte** — `a = 4.156895(25)`, Rwp 8.66 %, GoF 1.87,
  BL 3.377 — which is the registry's own string. The manual's geometry-esd
  figure reproduces its printed numbers exactly (Rwp **0.08177**, **88**
  distances, ratio **0.86-1.41**), so no chapter claim moves.

*In flight.* Nothing running.

*Next.* This WP has **no code task left**. Item 5 remains the maintainer's
release-home decision for a `SCHEMA_VERSION` 0.2 → 0.3, costed both ways in
§ Three items that are not code changes. Items **16** (`refine_json` cannot
express a tie), **19** (no TOPAS `.inp` reader) and **20** (the wheel ships
`src/rietx/io/CLAUDE.md` and `indexing/CLAUDE.md`) are round findings that still
have no task line; 20 is minutes, 16 is small and low-value given § The
decision's conclusion that `refine_json` is for MCP callers, and 19 is a
feature. Items 9 and 11 are the silent-science group and § The decision's last
paragraph should be read before working them. Milestone-wise the maintainer's
ordering still puts the speed chain (1112 → 1115) ahead of all of it, so the
honest recommendation is to **close this WP and go to 1112** unless item 5 is
wanted in 1.0.2.

*Filed elsewhere.* One finding belongs to nobody's WP and is recorded here so
it is not lost: **`docs/VALIDATION.md`'s NAC row records a number the current
protocol does not produce.** It says `a = 10.251285(12) A, Rwp 9.2 %`; the
acceptance fixture produces `a = 10.251216(46), Rwp 9.3 %` — a factor of four
on the quoted precision. **This is not this session's doing**: measured
identically after `git checkout main -- src/`, and confirmed to be the fixture's
own path by printing from inside the test rather than from a reconstruction.
The `measured` strings in `tests/validation_matrix.py` are frozen prose and the
byte-identity test only compares the doc to the registry, so nothing can catch
the registry drifting from reality. Whether `measured` is meant as a current
measurement or a dated snapshot is a documentation-policy call, which is why
this session did not act on it.

*Gotchas.* (a) **An infinite variance is true and unpropagatable.** Every
`0 × inf` against a zero coefficient is a NaN — an off-diagonal correlation of
exactly 0, a `C` row that does not use the column, a geometry partial that is
zero there — and one NaN in `Cov_free` reaches every row of `C @ Cov_free`
sharing a source with it. A rutile geometry table lost all six Ti-O bond esds
to `instrument.profile.y`, which no bond depends on. Two dead ends before the
right shape: clamping the variance to zero reinstates the original lie one layer
up, and guarding the multiply with `where=corr != 0` fixes only the first of the
four places. (b) **`np.isfinite` was the wrong predicate for a phantom peak.**
Those components have intensity 2.1e-49, not 0, so their columns are
*nearly* flat rather than exactly flat and the variance is huge-but-finite. The
predicate that works is physical and needs no new constant — the component sits
at its zero intensity bound. (c) **Dropping a component broke the GUI**, which
is what settled flag-versus-drop: the peak editor's add verb silently did
nothing on a component a human had just placed. `test_gui_peaks` caught it.
(d) A new `PeakFlag` fails `test_textdoc`'s meta-test until `gui/src/lib/rxt.ts`
restates the vocabulary, and the dist must then be rebuilt. (e) **Self-review
caught an efficiency regression I had introduced**: folding `stderr_physical`'s
uncorrelated branch into `_cov_free` removed a duplicated construction but
routed a vector quantity through a dense n×n — tens of MB on a Pawley table,
in the speed milestone. The shared piece is now `_sigma_free_measured`, which
is the part actually shared. (f) `compute_uncertainties` is declared with a
`True` default on two functions and **no in-tree caller ever overrides it**;
its `False` path has no test. A WP-1076-shaped observation, not acted on.
(g) Root CLAUDE.md's cap moved 759 → 771 and `src/rietx/indexing/CLAUDE.md`'s
280 → 296, each in its own commit with the reason, per the policy in
`SIZE_CAPS`.

### 2026-08-21 — the sharp edges an agent meets in its first five minutes

Six things a caller can now do that they could not, and all six were measured
failures of a real agent rather than guesses about what might be awkward.

Ask the package what version it is, in the spelling every python package uses.
Hand a plan to any surface without knowing which of two identical-looking types
that surface wanted. Read an in-situ reel's own temperatures instead of
reaching into a reader's private parser. Find out where a number lives when you
ask the wrong object for it, in the moment you ask rather than after losing the
run. **Draw the curve a set of parameters implies without refining anything** —
the agent that triggered this WP re-refined a one-stage plan in order to redraw
a figure, because evaluating a model required a fit that had already happened.
And land on a page when you guess its name.

Two of the findings are worth more than the fixes.

**Item 15 was half a bug report.** The direction agents complained about — a
JSON request refusing a preset — is loud. The other direction is silent and
worse: a `PlanSpec` handed to `fit(plan=...)`, under an annotation reading
`RefinementPlan | str`, simply *runs*, to a bit-identical answer, because the
two types share every field name and a plan is only ever read. No fit was ever
wrong; a whole class of type confusion just could not be seen. That is why the
crossing tests the class and not the shape — a structural check would have
certified the accident.

**Three items turned out not to be code.** `fitted_structure()` (item 3) cannot
be fixed without making `callable(structure)` return True, which is a lie any
duck-typing consumer would believe; `data.two_theta.min()` (item 7) is a python
error raised by `list`, with no rietx hook on the path at all; and removing
`Parameter.expr` (item 5) is a data-contract break whose release home is the
maintainer's call, not this session's. All three are recorded with their
reasoning in § Three items that are not code changes, so they are not re-opened
as though they were pending work.

*Done.* Items **12**, **4/15**, **17**, **2**, **6**, and the guessed-page-name
task. Five of the six task lines in this WP are now ticked.

- `rietx.__version__` (item 12), re-exported from the string `refine` resolves
  once at import — not a second `importlib.metadata` lookup, which would be a
  second authority free to disagree with the version every `Provenance`,
  `TreeHeader` and `project.json` is stamped with. The test pins it as the
  *same object*. Documenting it in `using/install.md` promotes it to frozen,
  which is the freeze working: the partition refused the new name until a
  chapter took it.
- The plan mirror is **crossed at the two authorities that own it, never at a
  call site** (items 4 and 15): `PlanSpec`/`StageSpec` validate the dataclass
  inbound, `resolve_plan` converts the spec outbound, and `agent.py` dropped its
  own copy of the conversion. Two error messages carry the rest of item 4 —
  `PLAN_PRESETS[name].stages` names the call, and `Stage`/`RefinementPlan` name
  their mirror. The factory wrapper carries `functools.update_wrapper`, so
  `help()` still reaches the builder; round 1.0's own shim lost an agent to the
  source over a wrapper that did not.
- The **series coordinate** (item 17) reaches `PatternData.metadata` and
  `ScanInfo` — two surfaces because the question is asked at two times, before
  a scan is chosen and after one is read. `ScanInfo.label` carries it too, since
  every range of a reel scans the same axis over the same angles and 82 of them
  otherwise enumerate as 82 identical rows.
- **A nested number is answered with its path** (item 2), derived from the live
  annotations rather than from a list of misses already seen — so `gof`,
  `chi2`, `esd_inflation`, `backend`, `mu_r` and `soft_modes` come free, and a
  field added to an optional block is covered the day it lands. A **pointer,
  not an alias**: forwarding the value would give two spellings of one fact and
  promote a dozen nested names to frozen public API. `model_fields`, the JSON
  and `hasattr` are all unchanged.
- **`predict` needs no fit** (item 6), taking a `PatternData` or a 2θ array.
  Only the no-argument form still does, because only a fit supplies a grid, and
  it refuses by naming the other form. The zero-stage plan — what someone
  reaches for when they want evaluate-only — is refused at the *top* of `fit`
  instead of raising a bare `AssertionError` from the end of the run, and its
  message names `predict`.
- `using/constraints.md` (the guessed-page task) is a signpost, not a third
  copy: two `{ref}`s to explicit targets in `concepts.md`, plus the one
  distinction worth stating where someone arrives not knowing which word they
  want.

*Measured.* Fast selection, **this checkout's own venv, `[dev]` (no jax/torch),
darwin/arm64**: **2558 passed, 117 skipped**, from **2536 passed, 117 skipped**
measured on `origin/main` at this session's start. **Twenty-two** tests added,
twenty-two new passes, **no new skip** — passed moves by exactly the
twenty-two (1 + 5 + 2 + 2 + 8 + 4, by item). `ruff` clean over
`src tests examples`; `sphinx -W` clean.

Full suite, same venv and platform: **2667 passed, 126 skipped in 24:43**,
zero failures, against the previous session's **2645 passed, 126 skipped** —
**+22**, the fast delta exactly, since none of the twenty-two is `@slow`; skips
unchanged. It fired **twice**, once per batch of source changes, the second
batch having landed after the first run: `resolve_plan`, `PLAN_PRESETS`,
`RefinementResult` and `fit` are each on the path of *every* fit in the
package. Strictly the ladder does not require either run — no forward model,
solver, statistic or reader output changed, every preset is asserted to build
what its classmethod builds, and `predict` has no caller inside the package —
so read both as insurance bought deliberately, on this WP's own record that a
plan-adjacent change was once caught only here.

Two equivalence bars, both exact rather than to a tolerance, because both
changes either produce the same thing or do not:

- **The plan**: its three spellings — the `RefinementPlan` the registry hands
  back, the `PlanSpec` a project holds, and the preset *name* — driven through
  `refine_json` on the synthetic Le Bail case give **one** Rwp, pinned as a set
  of size one.
- **Evaluate-only**: a never-fitted `Refinement` carrying the fitted models
  returns y_calc **bit-identical** to the fitted one on the same grid. A fit is
  a way to *set* parameters, not a licence to evaluate them.

The one place `predict`'s two forms do *not* agree is measured and documented
rather than left to be found: `predict()` reuses windows sized at the values
its stage started from, a grid argument sizes them at the values it ended on,
which is **36 of 4200 channels differing by at most 8e-6 of the peak**, all in
peak tails at a window edge. That is the frozen-per-stage invariant, and
`RefinementResult.y_calc` is the first of the two — the curve the fit minimised.

*In flight.* Nothing running.

*Next.* **Item 5 is a decision, not a task** — § Three items that are not code
changes costs both options, and the blocker is which release carries a
`SCHEMA_VERSION` 0.2 → 0.3 (1.0.2 is written, unreleased and already carries
0.1 → 0.2; `pyproject` is at `1.1.0.dev0`). **Item 1** (yank `0.0.0` from PyPI)
is the other one-action item and is likewise the maintainer's, not a session's.
Of what is left on the friction list, **items 9, 10 and 11** are the
silent-science group, and the round already found that 8 and 10 **did not
reproduce** — so before working them, read § The decision's last paragraph:
what the default surface does to an agent is not what the transcript's agent
did to itself. Milestone-wise the maintainer's ordering still puts the speed
chain (1112 → 1115) ahead of all of it.

*Gotchas.* (a) **A pydantic `model_validator(mode="before")` may not return an
instance of its own class.** Returning `cls.from_plan(value)` is rejected with
`Input should be a valid dictionary or instance of PlanSpec` — naming, as the
input, the very object it just built. `.model_dump()` on the way out is what
works, and it keeps `from_plan` the one authority for the field mapping. (b)
**`__getattr__` is safe on a dataclass and on a pydantic model only while every
other name still raises `AttributeError`** — that is what leaves `hasattr`,
`getattr(..., default)`, `copy.deepcopy`, `pickle` and the JSON round trip
behaving exactly as before, all checked on both. On the pydantic side it must
also delegate to `super().__getattr__` first (that is what serves `model_extra`
and private attributes) and fast-path `_`-prefixed names, because pydantic
probes absent attributes during copy and serialization and a speed milestone is
not where you add a scan to that path. (c) **The other formats were checked,
not assumed**, for item 17: Rigaku's `CW_Temperature1`/`CW_Temperature2` are
the cooling water and `RE_EnclosureTemp` the cabinet, and the `.brml` fixture
has no temperature field at all. (d) The GUI's `_as_plan_argument` keeps its
`to_plan()` on purpose: that call validates a raw JSON dict, a different job
from crossing between two live objects, and folding it in would have made a GUI
change out of a library one. (e) Root CLAUDE.md's cap moved 752 → 759 in its
own commit, per the policy in `SIZE_CAPS`. (f) I wrote "the only two objects a
caller handles here that are not pydantic models" into a docstring and it was
false — `Refinement`, `Project` and `RefinementTree` are plain classes too. The
true claim is *schema-shaped*, and it is the one that makes the message earn
its place. Corrected in its own commit; worth the habit of checking a
superlative before writing it.

### 2026-08-20 (third session) — the zero-scale cell runaway, bounded and named

A phase that is not in your specimen can no longer wreck the run. Before this,
a phase whose scale fell to nothing left its cell free to drift with no effect
on the fit, so the fit reported success while the cell left the physical range
entirely and the job died much later with an error about reflection lists — the
failure two agents hit independently on a 68-pattern series. Now such a cell is
held near where it started, the package says which phase the data cannot see and
which of its numbers are therefore not measurements, and on a long run it says
"42 of 68" once instead of the same warning 425 times. A fit that was already
working is untouched, to the last bit.

What that cost is worth recording: the first version of the fix bounded *every*
phase's cell, and that quietly made a real refinement worse — a bound is not
free, because the solver takes its step size from how far the bounds are. It
was caught by the full test suite, not by review, and the shipped version spends
a bound only where the alternative is a parameter the data cannot constrain at
all.

*Done.* Items **13** and **8**, which the round found and which turned out to be
one failure seen at two ranks. A phase reaches the pattern only through
`scale × |F|² × profile`, so a phase at its scale floor is a flat direction: the
fit reports `converged` because those parameters genuinely do not move Rwp,
while the cell walks out of the physical range. Three pieces landed, each
measured before it was written — § The cell window carries every number.

- `params.vector.cell_window`, a **per-stage window** on the cell of a phase the
  data cannot see, in TOPAS's shape at stage granularity. Applied in
  `ParameterTable.bounds` and **not** on the `Entry`: a window is the solver's
  bound for the stage about to run, not a fact about the stored parameter, and
  on the `Entry` it would have surfaced through `ParameterRow` and the `.rxt`
  document, both of which tell a reader that bounds come from the schema.
  `bound_findings` is fed from `bounds()`, so a cell that does reach its window
  is still reported. The four sites passing a nonsense finite `min` (0.1 Å,
  1.0 Å) drop it — it *suppressed* the default, and was never a floor.
- `CompiledModel.phase_support` and
  `optimize.least_squares._freeze_cell_windows`, which decide *which* phases —
  one measurement, two consumers (the bound and the diagnostic), pinned equal by
  test rather than re-derived.
- `PHASE_UNCONSTRAINED` (`refine._phase_support_diagnostics`), off the modelled
  contribution against the observation noise rather than off `scale`.
- `SEQUENTIAL_PERSISTENT_FINDING` (`sequential._persistent_diagnostics`), item
  8: the sentence no per-pattern diagnostic can produce.

*Measured.* Fast selection, **this worktree's own venv, `[dev]` (no jax),
darwin/arm64**: **2536 passed, 117 skipped**, from **2517 passed, 117 skipped**
on the same tree before the change. Twenty tests added, nineteen in the fast
selection (one is `@slow`), **no new skip** — passed moves by exactly the
nineteen. `tests/test_acceptance_indexing.py`: **44 passed in 20:24**, run
because `indexing/workflow.py` was one of the four sites (CLAUDE.md's rule);
no ranking moved. `ruff` clean, `sphinx -W` clean.

The equivalence bar, since v1.1 asks every landed WP for one and this is **not**
an Rwp comparison: the 11-BM NAC two-phase protocol run with the window on and
disabled **in one process**, diffing all 44 refined values — **44 of 44
bit-identical**, Rwp included. Exact rather than a tolerance, and it is exact
*because* the window is restricted: neither NAC phase (571σ and 185σ of support)
is windowed at all, so the bounds handed to TRF are the ones main hands it.

Full suite, same venv and platform: **2645 passed, 126 skipped in 22:33**, zero
failures. It fired **twice**, deliberately — the ladder says once on the final
tree, and the first run's tree turned out not to be final. That run is the whole
reason this WP shipped a correct design.

The count check, both selections. Twenty tests added, all in
`tests/test_absent_phase.py`, one of them `@slow`. **Fast**: 2517 → 2536
passed, +19, and nineteen is exactly the non-slow count; skipped unchanged at
117, so **no new skip and no skip counted as a pass**. **Full**: 2645 passed
against an implied 2625 on main — +20, the fast delta plus the one `@slow` row,
which is the consistency `tests/CLAUDE.md` asks for rather than a second
hour-long baseline run; skipped unchanged at 126. The two full runs bracket it
independently: the first, on the pre-correction tree, was 2639 passed + 3 failed
= 2642 non-skipped with seventeen tests present, and 2642 + 3 later tests = 2645.

**The full suite is what made that true.** The first design windowed every
phase, and it regressed three `test_acceptance_sequential` rows that pass on
main — chained `cpd-1c` corundum 9.04 wt % against 6.30. § The cell window has
the sweep; the short version is that a window is not free, the failure was
`warm_refit` exhausting its budget and landing *inside* the reseed fence so
nothing rescued it, and the fix for a silent unsound trajectory had produced
one. Sequential acceptance now 13 passed.

*In flight.* Nothing running.

*Next.* **Item 15 (the two plan types)** and **item 17 (the VT temperature)** —
the previous session's ordering, both of which cost every agent in the round
real time, and neither of which this session touched. Item 12
(`rietx.__version__`) is a one-liner that belongs with them.

*Gotchas.* (a0) **A bound is not free, and that is the lesson to carry.** TRF
takes its trust-region scale from the distance to the bounds, so *any* new
default bound changes the step taken in that coordinate even where it is never
reached — measured here as a 5× iteration blow-up and a wrong QPA answer.
Anything proposing a default bound owes the same before/after on a chained
acceptance case, not just on a fit that was already easy. (a) The **prior art
answered a question I was about to invent a number for**, and it is worth checking first next time: TOPAS has published
default cell limits (§ 2.17 Table 2-1) and GSAS-II has a published *opposite*
policy, and between them they fixed the shape, the floor and the reporting
behaviour. The maintainer asked for this rather than accepting my ±5 % box, and
the box was the wrong shape. (b) **Two of my own new test assertions were wrong
before the code was** — the pad does not scale with the cell, and 0.95·2 − 0.05
clears the 1.5 Å floor. Both were caught only by running them; a constant's
arithmetic is worth doing on paper. (c) The window was first written onto
`Entry` and that broke four `test_compare_ui` rows, three `test_textdoc` and one
`test_gui_server` — **the failures were the design review**: each was a fixture
carrying the rendered `min 0.1`, which is exactly the parameter surface a solver
bound must not reach. Moving it to `bounds()` was the fix and the reason. (d) A
**windowed cell need never fire `BOUND_HIT`**, because it re-anchors each stage;
anyone tempted to treat the window as the whole fix should read § The cell
window's last paragraph first. (e) The `PHASE_UNCONSTRAINED` threshold is not a
knife edge — the 11-BM NAC CaF₂ impurity, a genuine trace phase, carries 185σ
against the absent phase's 0.088 — but it is **skipped entirely for a
single-phase fit**, where "the one phase is under the noise" is
`MODEL_FAR_FROM_DATA`'s statement, not this one. (f) Root CLAUDE.md's cap moved
736 → 752 in its own commit, per the policy in `tests/test_docs_consistency.py`.

### 2026-08-20 (second session) — the round run, and the premise corrected

*Done.* The decision item answered with real agents rather than by reasoning:
`tests/eval_agent_surface/PROTOCOL.md` round 1.0 — three conditions
(`bare`/`pointed`/`mandated`), N = 2, sonnet, on the trigger dataset itself,
**registered and committed before any run**. Its Results section carries every
number and § The decision above carries what it settled. Eight new friction
items (13-20) came out of watching agents work, and **two of this WP's own
claims were corrected**. Four things landed alongside, each named in its own
commit: the v3 RAW gate that the round could not start without, the round's
shim and scorer, the session-start hook's entry-date parser, and a false
positive in `test_portability`.

*Measured.* R1 = **0 of 2** — neither unaided agent reached `refine_json`,
replicating the transcript. R2 = **split, 1 of 2**, and it stays split: N = 2
was declared as a device for making a disagreement visible, not for measuring a
rate, so no branch of the decision rule is claimed as swept. The result that
decided the WP is one neither read-out asked for: `agent.tool_definition()`,
`request_schema()` and `response_schema()` were called **zero times in every
cell across 235 traced interpreter starts**, including both cells *required* to
use `refine_json`; all 25 `refine_json` calls were python function calls inside
python scripts. Test counts, **this worktree's own venv, `[dev]`,
darwin/arm64**: fast selection `-m "not slow"` **2562 passed, 72 skipped**,
from 2559 passed / 72 skipped before this session. Three tests added, three new
passes, **no new skip**: the RAW zero-pad test, and two on the hook (the real
corpus, and both entry spellings). **The full suite was not run, deliberately**
— nothing here can move a number it measures: the RAW gate only *widens*
acceptance for a zero-padded v3 file and no committed fixture is one (the two
Bruker fixtures are v4 and `.brml`), and the rest is tests, hooks and docs.
`sphinx -W` clean, `ruff` clean.

*In flight.* Nothing running. Twenty friction items are unstarted; the Tasks
list is ordered now because the decision that ordered it is taken.

*Next.* Item 13 first — the zero-scale cell runaway, hit independently by two
agents, refused several stages downstream of its cause, with a fix
(`Structure.from_cif` defaulting cell bounds to ~±5 % of the CIF's own cell)
that needs no third-party number. Then 15 (the two plan types) and 17 (the VT
temperature), both of which cost every agent real time. **Do not start with the
JSON surface**: the round says a coding agent's investment is the python one.
Milestone-wise the maintainer's own ordering still puts **WP-1111 ahead of all
of these** — it gates 1112-1115.

*Gotchas.* (a) The round's own instrument had two defects, both recorded in
PROTOCOL.md and both fixed: the shim wrapped without `functools.wraps`, so an
agent saw `rietx_surface_trace.py` and went to source; and attribution by cwd
measured almost nothing, because a subagent runs python from wherever its shell
sits and `python -c` leaves nothing in argv. Round 1.1 should give each cell its
own venv so attribution is a property of the environment. (b) **The experiment
venv had no matplotlib**, so four of six agents hand-rolled an SVG plotter. That
is a workspace defect of mine, not a finding about the package, and nothing is
concluded from it. (c) The dataset is the maintainer's; its URL and fetch date
are in PROTOCOL.md § The episode, and it is **committed nowhere in this repo**,
so re-running the round means fetching it again. (d) `pointed-1`'s abandoned
`refine_sequential` is a **speed** datum and is pushed to WP-1111's
`### Inherited`, not kept here. (e) The reader fix (`552f3e18`) is work outside
this WP's list and was unavoidable: `read_pattern` refused the trigger file, so
no round was possible without it. (f) The session-start hook fix is likewise
outside the list, and arrived through the ritual's memory sweep rather than the
task list: the hook parsed only `TEMPLATE.md`'s `- **date**` bullets while every
real log writes `### date` headings, so it flagged *every* open WP with recent
commits as `repair first` — including this one, at this session's own start. Its
synthetic tests could not see it because they built fixtures in the parser's own
spelling, so the new guard reads the real `docs/wp/` corpus and was confirmed to
fail on the old regex before being trusted.

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
