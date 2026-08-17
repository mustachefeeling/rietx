# WP-1067 — User & API manual (Part 1)

Milestone: v1.0 § Floor, then 1.0.x · Status: 🔄 2026-08-17 — floor landed (gates 1003); the McCusker set's pass landed; `using/data.md`, `using/model.md`, `using/refining.md` and `using/history.md` landed and 358 names froze with them, half the surface; three 1.0.x chapters remain, plus [1076](1076-result-row-honesty.md), now holding four unwritten fields and values a chapter found
Depends on: WP-0604 (the manual machinery), WP-1004…WP-1007, WP-1047
(the surfaces it documents). **§ Floor gates [1003](1003-api-freeze-pypi.md);
the rest ships after the release, so this WP stays open past the milestone and
its ROADMAP row sits under § Post-v1.0.**

## Goal

`docs/manual/` becomes a two-part manual built by one Sphinx tree: **Part 1 —
Using rietx**, a task-ordered guide to the library and its public API, and
**Part 2 — Theory**, the existing chapters unchanged. Part 1 is written
against a *derived* enumeration of the public call surface, which is also the
surface [1003](1003-api-freeze-pypi.md) freezes.

## Audience

Two readers, and the chapter order is the gradient between them:

- **someone with a pattern who wants a number they can defend** — install,
  quickstart, report. Assumed to know powder diffraction, not this package;
- **someone wiring the package into a program or an agent loop** — the object
  graph, projects, history, the JSON surface.

Neither is the maintainer. Neither is a GUI user (§ Non-goals).

The floor serves the first reader in three chapters and the second in one:
`using/model.md` is post-release, so at v1.0 an integrator has
`using/agents.md` and the JSON schema. That is a decision, not an oversight —
`refine_json` is self-describing through `tool_definition()`, and the protocol
it points at is the half an integrator cannot derive from a schema.

## Context

**Why the floor runs before the freeze.** Writing the user-facing reference
over the public surface is the best audit that surface will get, and 1003's
job is to freeze what the audit finds. Same argument the milestone already
made for putting the GUI ahead of the freeze (ROADMAP § v1.0). Expect the
chapters to find gaps; § Non-goals says what to do with them.

**One tree, two parts.** Part 1 lives in `docs/manual/` beside Part 2, not in
a second doc root — WP-1017's argument, which still holds: a separate root
needs its own guard set for no benefit. It also lets Part 1 link into Part 2's
*numbered* equations instead of restating physics, and inherit `index.md`'s
standing contract that **the code is authoritative** (where prose and docstring
disagree, the docstring wins and the discrepancy is a bug).

`conf.py` and `index.md` both name the whole tree "theory manual"
(`html_title`, the H1, the lede). That is Part 2's name now, not the tree's.

### Where the pages live

Part 1 goes in `docs/manual/using/`, and `tests/test_manual.py`'s `CHAPTERS`
(`MANUAL_DIR.glob("*.md")`, flat) becomes an `rglob` — a one-line edit. Doc
structure should not be shaped by a test's glob, and the reason to stay inside
`CHAPTERS` is *future* guards, this WP's included: today's are vacuous on Part
1 pages either way (the source-symbol test asserts a global non-empty set, the
labelled-equation and bib rules fire only on pages carrying equations or
citations, and `-W` applies whatever the directory). **Gotcha: `rglob` walks
`docs/manual/_build/`** — exclude it, or a stale build tree joins the
collection.

### The guard is name resolution, and coverage is a floor not a bar

Part 2's guards work because an equation names a symbol. A reference manual's
failure mode is different, and this repo has measured it: `features["indexing"]`
was `False` for its entire life because the flag's `hasattr` name (`index`) and
the real export (`index_pattern`) drifted apart while the meta-test asserted
the flag's own expression rather than the name (WP-1037; root CLAUDE.md
`_SURFACE_FLAGS`). A manual is a much larger surface of the same bug. So:

- every dotted name Part 1 spells resolves against the live package;
- every parameter dot-path resolves against a real `ParameterTable` (no
  brackets — fnmatch treats `[..]` as a character class);
- every fenced `python` block is compile-checked, and executed or exempted
  under the cost model below;
- every entry in the **derived call surface** is documented or excluded with a
  reason, asserted as a partition.

**`rietx.__all__` is the wrong denominator.** It is 71 top-level names
(measured 2026-08-14 — re-measure, do not quote), but almost nothing a user
calls lives there: `ref.fit`, `ref.report`, `ref.parameters`, `ref.set_vary`,
`result.statistics.rwp`, `result.parameter`, `history.branch`/`merge`/
`cherry_pick`, `Project.create`/`open`/`save` are methods and fields. A manual
naming `Refinement` once would satisfy an `__all__` partition and document
nothing.

**And a hand-curated list of those methods would reproduce the very bug
above.** A list nobody regenerates cannot notice a *new* public method: it
never enters the denominator, the partition stays green, and coverage silently
drops. So `tests/api_surface.py` **derives** the surface — public attributes of
the exported types, dunders and privates filtered — and its hand-written half
is only the **exclusions and the chapter assignments**, each with a reason. A
new public method then lands in the denominator by itself and fails the
partition until someone documents or excludes it. Same lesson as
`_SURFACE_FLAGS`: make the name data, derive the rest.

Two rules the derivation itself needs, both measured 2026-08-14 (re-measure,
do not quote):

- **"Public attributes" means declared, not inherited.** 34 of the 47 exported
  classes are pydantic models, so a bare `dir()` denominator is 1099 names,
  most of them `model_dump`-class BaseModel machinery. Count a member iff it is
  in the class's `model_fields` or its defining class lives in a `rietx`
  module; that lands near 147, the right order for a documentable surface.
  Excluding the machinery by hand instead would be the hand-curated list again.
- **The surface must close over reachable unexported types.** `Statistics` is
  not in `__all__`, so one level of attributes never reaches
  `result.statistics.rwp` — this WP's own motivating example. Recurse into
  rietx-defined types reachable through exported types' fields and annotations;
  exporting them instead would break § Non-goals' no-new-API rule.

(`tests/validation_matrix.py` → `docs/VALIDATION.md` is *not* the precedent to
copy here. That matrix is authoritative because its content exists nowhere
else; an API surface's authority is the code.)

**1003 freezes the same surface**, so build the derivation here and let the
freeze consume it rather than re-deriving a second enumeration.

At the floor the partition is asserted over the **whole** derived surface,
with an explicit `deferred-1.0.x` exclusion bucket; the WP closes when that
bucket is empty. What remains is then data the test reports, not a task list
nobody diffs.

**A coverage partition catches omission; it does not measure quality.** The
cheapest way to turn it green is a line reading "`SharingMap` maps sharing".
The quality bar is the executed examples and review; the partition only stops
a name from being forgotten.

### The walkthrough has one authority, and it is `examples/`

Today the same walkthrough exists twice and is guarded zero times: README
carries worked examples for quickstart, lab data, report reading, exports,
history, live monitoring and compare, and `examples/nac_11bm.py` /
`examples/srm660c_lab.py` carry the runnable versions. **Nothing in `tests/`
executes either.** Ruff lints `examples`; no test runs it. Transcribing a
third copy into the manual would be the worst available option in a repo whose
rule is one authority per fact.

Decision: **`examples/*.py` is the authority.** The manual `{literalinclude}`s
them rather than retyping, and the guard *executes the script*, so the
walkthrough is code that runs and the manual is a view of it.

Measured 2026-08-14 on a mirrored tree with this venv's sphinx: from
`docs/manual/using/`, `{literalinclude} ../../../examples/demo.py` builds
`-W`-clean and the content lands in the HTML. Get the `..` count wrong and
sphinx clamps the path into a nonexistent prefix and **warns**, which `-W`
turns into a build failure — a good failure mode, but it means the depth is
worth getting right the first time.

README is sequenced, not shrunk here: it is the GitHub landing page **and the
PyPI long description**, and until 1003 hosts the manual a reader has nowhere
else to go. So this WP declares the authority rule and adds the pointers;
**the deduplication (README keeps one headline snippet, the rest become links)
lands with 1003's hosting.** Record it in 1003's mailbox.

### Cost model for the execution guard

`tests/CLAUDE.md` is explicit that a wall-clock budget inside a test is a
runaway guard and never a timer, and that heavy work needs a `slow` mark and
an `xdist_group`. A chapter that runs a real fit would otherwise turn the docs
test into an acceptance suite. The policy:

- **every** fenced `python` block is `ast.parse`d — free, and catches the
  typo class immediately;
- a block that only constructs objects or reads fields executes in the fast
  suite against the bundled small fixtures;
- **a block that refines does not exist as inline prose.** It is a
  `{literalinclude}` of an `examples/` script, and the *script* is executed by
  `tests/test_examples.py` under `@pytest.mark.slow` with an `xdist_group`,
  priced like any other acceptance row. Separate module from the manual guard
  on purpose: one asserts prose against the package, the other runs
  refinements, and they belong on different cadences;
- every non-executed block carries a reason string. A bare exemption fails the
  test — that is how this rots.

### Do not restate AGENT_PROTOCOL, and do not move it

`docs/AGENT_PROTOCOL.md` is the *operating protocol*: what to do in what
order, what to check before believing a number, the measured findings that
change an operator's behaviour. Part 1 is the *reference and the on-ramp*.
One authority per fact — Part 1 links to the protocol for order and judgement,
the protocol keeps linking to Part 1 for the surface.

**`using/report.md` is where that line has to be stated rather than assumed**,
because it sits directly on top of §4–§6: the chapter is the **object model**
(what `FitReport` carries, field by field, and how to reach it), the protocol
is the **judgement** (what to believe, in what order, and when to disbelieve
Rwp). Unstated, that chapter drifts into paraphrase, which is the failure this
non-goal exists to prevent.

It is **load-bearing as a file**, in two places that break silently:

- `agent._TOOL_DESCRIPTION` names `docs/AGENT_PROTOCOL.md` by path, inside the
  tool description every tool-calling agent reads (`agent.tool_definition()`);
- `tests/eval_report_agent/python_arm.py` ships it **verbatim** into every
  eval worktree, and `test_python_arm.py` asserts byte equality.

No split, no move, no partial copy into a chapter.

### The manual does not ship, and one pointer already dangles

`[tool.hatch.build.targets.wheel] packages = ["src/rietx"]` — the wheel
carries the package and nothing else. A `pip install rietx` user has **neither**
`docs/manual/` **nor** `docs/AGENT_PROTOCOL.md`, while `agent.tool_definition()`
points that user's agent at the second by repo-relative path. A live defect
today, not a v1.0 nicety.

The fix is a release decision (hosted docs and a URL, `docs/` as package data,
or a CLI route) and hosting is 1003's scope. What this WP owes is the
**constraint on the record**: whatever 1003 picks, the string in
`_TOOL_DESCRIPTION` must resolve for someone who only ran `pip install`.

### Two staleness traps, both already paid for once

- **A chapter that *lists* formats, plans, backends or anodes goes stale
  between sessions.** WP-1047 landed five vendor formats on 2026-08-08/09,
  taking the total to ten, and 1017's mailbox records the lesson twice. Quote
  `capabilities()` — which carries each reader's own `title`, `sniff` and
  `sigma` prose, each plan's `title`/`description`/`when_to_use`, and each
  engine's and search preset's description — and show the *shape* of its
  output rather than transcribing its contents.
- **A test count in prose rots.** Root CLAUDE.md § Numbers is the recipe
  (measure, never quote; full-suite counts from the latest weekly `full` job
  log, with the venv **and** the platform). README currently quotes
  1197/1116; the README task re-measures rather than editing in place.
  Accuracy claims belong to `docs/VALIDATION.md`, which is generated from
  `tests/validation_matrix.py` — link it, never restate it.

### The GUI is out of scope and it is beta

[WP-1017](1017-gui-manual-onboarding.md) was deferred past the public release
on 2026-08-14 (user decision): the GUI keeps being worked on and is documented
once the panels settle. It holds the whole GUI documentation surface. Two
things land here instead: the README **declares the GUI a beta feature**, and
`using-cli` names `rietx gui` in one beta-marked line, no walkthrough, no
screenshots. Do not absorb any of 1017's mailbox — it is about panels that are
still moving, which is why it was deferred.

### Each 1.0.x chapter is a compatibility event

Folded in from WP-1003's mailbox on 2026-08-17, unchanged and still binding.
Since v1.0 shipped, `docs/manual/using/compatibility.md` promises that a name a
Part 1 chapter documents is **frozen from the release that documents it**, and
that the deferred bucket is the provisional tier. So a chapter is not only a
docs change: regenerate `api_surface_deferred.txt` in the same commit (the
partition fails otherwise), and give the promotion a line in that release's
notes — the precedent is `docs/releases/1.0.0.md`. It follows that a name a
chapter *cannot* honestly freeze is left in the bucket rather than mentioned in
passing.

## Non-goals

- **No GUI chapters** (WP-1017). One beta-marked line is the whole of it.
- **No autodoc in this WP, and the question stays open.** WP-0604 did not
  reject a rendered API reference; it deferred one, saying it "belongs with
  the WP-1003 freeze, if anywhere". 1003 is the WP beside this one, so this WP
  neither adds autodoc nor closes the question: it hands 1003 the derived
  surface list and whatever the coverage test shows is expensive to document
  by hand.
- **No hosted-docs, theme, or publishing decision** — 1003's release scope.
  This WP records the packaging requirement and the README deduplication that
  follows hosting.
- **No restating theory** (link Part 2's numbered equations) and **no
  restating the protocol** (link AGENT_PROTOCOL).
- **No new or changed public API.** A chapter that cannot be written cleanly
  has found a surface defect: file it into 1003's `### Inherited` and write
  around it. **Docstring corrections are in scope, and are recorded** —
  `index.md`'s contract makes the docstring the authority the manual is
  transcribed against, so a wrong docstring found here is fixed here. That
  follows 0604 rather than diverging from it: its rule was that gaps are
  "noted in the handover log, not *silently* patched", and the operative word
  is *silently*.

## Tasks

### Floor — gates 1003

- [x] Split the tree: `index.md` becomes the manual's front page with two
      captioned `toctree` blocks; Part 2's chapters move under it unchanged;
      `conf.py`'s `html_title` and the H1 stop naming the whole tree "theory
      manual"; `CHAPTERS` becomes `rglob` **excluding `_build/`**. Builds
      `-W`-clean; `test_manual.py` green.
- [x] `tests/api_surface.py` — **derives** the public call surface (declared
      members of the exported types and of the rietx-defined types reachable
      from them; inherited pydantic machinery, dunders and privates filtered —
      the two derivation rules in Context) and hand-writes only the exclusions
      and chapter assignments, each with a reason, plus the `deferred-1.0.x`
      bucket. This is the surface 1003 freezes; say so in its docstring.
- [x] The guard, before the prose it guards: `tests/test_manual_api.py` —
      names resolve, dot-paths resolve, blocks compile, blocks execute or
      carry a reason, and the derived surface is partitioned. **Make it fail
      on purpose twice**: rename a documented symbol, and add a public method
      to an exported type without touching the manual. The second is the one
      that matters.
- [x] `using/install.md` — extras and what each buys, the numpy-only default,
      `[gui]` as a plotly-only extra over a committed dist, running the suite,
      and a link to `docs/VALIDATION.md` for what the package is known to get
      right.
- [x] `using/quickstart.md` — one fit end to end as a `{literalinclude}` of
      `examples/nac_11bm.py`, plus `tests/test_examples.py`, which executes
      that script under `@pytest.mark.slow` with an `xdist_group`. States the
      structure-free-first order and links AGENT_PROTOCOL §2 rather than
      restating it.
- [x] `using/report.md` — **the object model, not the judgement** (see
      Context): the three layers and their four gates, abstention as a result,
      `evidence`, the stage trajectory (a converged report is routinely the
      least informative in the run), and "did that correction help?" via
      `viz.compare.run` headless plus the cumulative-Δχ² reading.
- [x] `using/agents.md` — `refine_json`, `tool_definition()`, `capabilities()`
      and the five versioned contracts, then hand off to AGENT_PROTOCOL. Push
      the packaging constraint and the README deduplication into 1003's
      `### Inherited`.
- [x] README: docs pointer becomes "the manual, in two parts"; the theory-
      manual capability row is restated; the **GUI is declared beta** with
      `rietx gui` named and 1017 recorded as deferred; quoted test counts
      re-measured per root CLAUDE.md § Numbers. Examples stay for now — the
      deduplication is 1003's, after hosting.

### After the release (1.0.x)

- [x] **The McCusker set's manual pass** (2026-08-16). Six WPs each appended to
      one section; this is the pass that reconciles the manual with what they
      shipped. Part 2 takes the four equations they added
      (`par-restraint-weight`, `est-structure-r`, `est-mind`, `est-derived`);
      `concepts.md` § Fit statistics becomes `using/results.md`; restraints get
      documented at all; three figures; and the geometry-keyed position
      templates and actions reach `report.md`.
- [x] `using/data.md` — "Patterns, structures and instruments" (2026-08-17).
      **Not what this line first asked for**, because WP-1068's `using/files.md`
      landed the file side in between: `read_pattern` with `scan=`/`block=`, the
      reader's four consequences, `Structure.from_cif` and the two CIF repairs,
      and the profile calls are all there, and a second copy would break the
      one-authority rule. So `files.md` keeps the on-disk map and this chapter
      takes what was still undocumented — the three objects field by field:
      `Parameter`, `PatternData` and where σ comes from, `Structure`/`Phase`/
      `Cell`/`Atom` with the three optional blocks, `Instrument` with its
      presets, source, geometry-by-kind, width function and backgrounds, then
      calibrate → freeze → sample stated as what each plan frees.
- [x] `using/model.md` — "The parameter table" (2026-08-17). Dot-paths,
      `parameters()` → `ParameterRow`, the three reasons a row is held,
      transforms as the physical→internal bound mapping, `set_vary` /
      `set_values` with their refusals, and the fit's own view of the same
      table (`RefinedParameter`). **Two items on this line moved elsewhere and
      one is now redundant**: the cell-tie *settings* are Part 2's
      `parameterisation.md` and `data.md`'s `Cell` section, so this chapter
      links them; the JSON round-trip is `Parameter`'s in `data.md`; and
      `ParameterTable` itself is not on the public surface, so the chapter is
      written over `Refinement.parameters` rather than over the class. It
      documents `RefinedParameter` **except** `initial` and `at_bound`, which
      nothing writes and [1076](1076-result-row-honesty.md) is fixing.
- [x] `using/refining.md` — "Running a refinement" (2026-08-17). Modes, the
      plan *registry* (`PLAN_INFO`/`PLAN_PRESETS`/`PlanInfo`) and the
      serializable twins, a stage's four solver settings, `run_stage`,
      `StageResult`, `GuardFinding`, `events=`/`cancel=` and `Provenance`.
      **`solver=` and `backend=` are not `fit` arguments** — they are
      constructor arguments on `Refinement` (and on `refine`), which is the
      chapter's opening table. Plans themselves stay `concepts.md`'s: it owns
      the seven presets, the stage diagram and the McCusker order, so this
      chapter links rather than restates. It also found the guard's fourth
      derivation rule (see the handover) and two more unwritten result fields,
      filed to [1076](1076-result-row-honesty.md).
- [x] `using/history.md` — "The refinement history" (2026-08-17). The DAG as an
      object: `HistoryNode` and why it stores state and not curves, `NodeAction`
      and why a stage records its own solver settings, the `RefinementState` a
      checkout puts back, `ReflectionState`, the as-optimised `NodeMetrics`, the
      tree's twenty queries, `checkout`/`branch`/`cherry_pick`/`merge`/
      `from_node`, `replay`, and `TreeHeader`. **`using/projects.md` was not
      written**, and the reason is measured rather than a scope cut: `files.md`
      already held the `.rex` layout, the one-authority rule, saving-as-settings,
      the data reference and nine `Project` members, so a second page would have
      been a field table plus a copy of that narrative. The remaining 25 names —
      the session object's six attributes, `ProjectDoc` field by field, four
      `DataRef` fields — went into `files.md` beside them. Between them the two
      halves froze 117 names and eleven types in full.
- [ ] `using/indexing.md` — `pick_peaks` → `index_pattern`, `quick` vs
      `full`, `best_or_none()`, the extinction symbol, and reading "no
      high-confidence entry" as a result rather than a failure.
- [ ] `using/series.md` and `using/exports.md` — sequential vs multi and
      `direction="both"`; CIF / reflection / QPA exports, plots,
      `plot_for_vlm`, `write_html`.
- [ ] `using/cli.md` — `rietx watch`, `rietx compare`, and `rietx gui` in one
      **beta**-marked line.
- [ ] **The names no remaining chapter claims** — measured 2026-08-17, when the
      bucket first became small enough to map: of the 661 left, about 276 are
      indexing's, 73 are the series and multi-histogram types, and the rest are
      **not** in any remaining task line above. Two blocks account for most of
      them, and both belong to a chapter that already exists, so this is a
      second pass rather than a new page: the agent request and response union
      (`RefineRequest`, `MultiRefineRequest`, `SequentialRefineRequest`,
      `SuggestRequest`, `IndexRequest`, `AgentSuccess`; 78 names, and
      `agents.md` documents the *call* rather than the arms), and the report's
      own evidence types (`StageReport`, `SuggestionResult`, `RegionAttribution`,
      `TextureAnalysis`, `StrainAnalysis`, `BackgroundEvidence`,
      `ParameterCandidate`, `ExchangeFinding`, `TrendAnalysis`, all reachable
      from `FitReport`'s own fields, where `report.md` describes the three
      layers without naming the types field by field). The bucket cannot empty
      without both.

## Acceptance

The floor is done when the **derived** surface is fully partitioned — every
name documented in a floor chapter, excluded with a reason, or in the
`deferred-1.0.x` bucket — and the walkthrough the manual shows is a script the
suite ran:

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_docs_consistency.py
.venv/bin/python -m pytest tests/test_examples.py -n auto --dist loadgroup   # the walkthroughs (slow)
.venv/bin/python -m ruff check src tests examples
```

The WP closes when the post-release chapters land and the `deferred-1.0.x`
bucket is empty. It therefore stays open past the milestone by design, and its
ROADMAP row sits under § Post-v1.0 rather than in the v1.0 table.

## References

- WP-0604's manual architecture (fenced constants injected from the live
  package, `*Source:*` lines, the cited-bib guard) — the machinery Part 1
  extends rather than duplicates. Its non-goals also *defer* autodoc to 1003
  rather than rejecting it.
- `tests/validation_matrix.py` → `docs/VALIDATION.md` — the nearest existing
  shape, and the one `tests/api_surface.py` deliberately does *not* copy: that
  matrix is authoritative because its content lives nowhere else, whereas an
  API surface's authority is the code, so it is derived (see Context).
- `docs/AGENT_PROTOCOL.md` — the protocol Part 1 links to and must not
  restate.
- WP-1037 / root CLAUDE.md `_SURFACE_FLAGS` — the measured precedent for why
  the guard is name resolution and not a prose rule.

## Handover log

- **2026-08-17 (`using/history.md`, and the project half of `files.md`)** — nine
  commits on `wp1067-using-history`, eight of content and one of handover. No
  `### Inherited` to prune (still none on this WP; the "Inherited" strings in
  this file are prose about *1003's* and *1076's* mailboxes).

  **The task line asked for two pages and the measurement deleted one.** Fourth
  session running, measuring which names each existing page already spells
  changed the shape of the work before a word was written — and this time it
  removed a whole planned chapter. `files.md` already held the `.rex` layout,
  the one-authority rule, saving-as-settings, the data reference, the excluded
  regions and nine `Project` members, so a `using/projects.md` would have been a
  field table plus a copy of that narrative. The 25 remaining names went into
  `files.md` beside their subject: the session object's six attributes,
  `ProjectDoc` field by field, and the four `DataRef` fields that describe the
  pattern. **`Project`, `ProjectDoc` and `DataRef` are now frozen in full.**

  **The chapter is the DAG as an object**, since `files.md` owns it as a file:
  what a node holds and why it stores state and not curves, the `NodeAction`
  (with the reason a stage records its own five solver settings —
  `cherry_pick` rebuilds a `Stage` from them), the `RefinementState` a checkout
  puts back, `ReflectionState`, the as-optimised `NodeMetrics`, twenty tree
  queries, the four branching verbs, `replay`, and `TreeHeader`.

  **Numbers** (`[dev]` venv — no jax, no torch; darwin/arm64). Fast selection
  **2402 passed / 117 skipped in 4:11**, counts identical to this session's
  starting tree: docs only, no test added. The full suite was **not** run — docs
  plus one generated file cannot move a measured number (`tests/CLAUDE.md`
  § Running, rung 3); the standing Linux figure is still **2561 passed / 88
  skipped in 1:51:56** (`[dev,jax]`, nightly 32017322140). Partition:
  **661 documented, 661 deferred** of 1322, from 544/778 — **117 names froze**,
  and the surface is now exactly halved. `sphinx -W` clean; `test_examples.py`
  4 passed; ruff clean. The new page was audited at 1100 px in both themes with
  `scrollWidth == clientWidth` on every element in `main` and no body overflow,
  and read at five crops in light and two in dark; `files.md` was re-audited the
  same way after its two new tables.

  **Measured while writing** (all from the `examples/nac_11bm.py` session, which
  the fast suite runs): the walkthrough's tree is **13 nodes**, the Le Bail node
  carries **129 extracted intensities** and the Rietveld nodes none, `replay` of
  the final node lands **1.6e-7** from the cached Rwp, and **44 paths** differ
  between the Le Bail node and the final one. On the same pattern, limits of
  2-24° leave **22 003 of 59 498** channels and excluding 7.4-7.6° as well
  leaves **21 803**.

  **In flight: nothing.** Working tree clean.

  **Next (1.0.x).** Three chapter lines, plus the fourth this session added,
  which is the one that decides when the WP can close. The bucket is now small
  enough to map, and the map is the useful part: of 661 names, **~276 are
  indexing's**, **73 are the series and multi-histogram types**, **78 are the
  agent request/response union** and the rest include the report's own evidence
  types (`StageReport`, `SuggestionResult`, `TextureAnalysis`, `StrainAnalysis`,
  `RegionAttribution`, `BackgroundEvidence`, `TrendAnalysis`,
  `ParameterCandidate`, `ExchangeFinding`), all reachable from `FitReport`'s own
  fields. The last two blocks are second passes on `agents.md` and `report.md`,
  not new pages. `using/indexing.md` is the largest single chapter left by a
  wide margin; `src/rietx/indexing/CLAUDE.md` auto-loads for it. Keep appending
  promotions to `docs/releases/1.0.2.md`, still unreleased. **`Refinement.predict`
  is still unassigned**, and the export verbs (`Refinement.write_cif`,
  `.write_reflection_table`, `.write_qpa_table`, `.reflection_table`) want
  `exports.md`.

  **Gotchas.**

  - **The `rx.` alias trap has a victim, and it had been sitting there since the
    floor.** `Project.create` and `Project.open` were spelled in `files.md` only
    inside a fenced block as `rx.Project.create(...)`, and the scanner strips
    `rietx.` and not `rx.`, so both stayed in the provisional bucket through
    three releases' worth of chapters while the page looked like it documented
    them. The previous session recorded this as a rule; this is what it looks
    like in the wild. Grep a chapter for `` `rx. `` before believing its
    coverage.
  - **`RefinementTree.head` is not "where this object is".** Measured:
    `ref.branch("lebail")` leaves `ref` at n0012 and moves the *tree's* head ref
    to n0005, because `branch` checks the new refinement out and a checkout
    writes the shared ref. Each `Refinement` carries its own `_head_id`. Read
    the tree's head as "where a reopened session resumes"; the chapter now says
    so, because a reader who assumes otherwise will branch and think the fit
    moved.
  - **A merge's `prefer` decides the model, not just the tie-break, and the
    draft had the direction backwards.** Measured on the walkthrough's tree:
    merging the Le Bail branch into the final state with `prefer="theirs"`
    returns a **one-phase** model, because the CaF₂ impurity arrived in a model
    edit that is not on the preferred side, and nothing raises. Writing the
    warning from the docstring rather than from a run is what got it wrong.
  - **Building a tree by hand needs `ref.checkout("head")` after the root node.**
    `Refinement.__init__` reads `history.head` once, so a `Refinement`
    constructed over a fresh empty tree keeps `_head_id = None` and its first
    commit is parentless. `Project.create` does exactly this checkout, which is
    how the chapter's executable example was made to produce a connected tree.
  - **Two more unwritten values, both filed to 1076, and one has consumers.**
    `NodeKind` admits `"lebail_update"` and no code path commits one — yet
    `NodeAction.api_call` renders `ref.lebail_update(n_cycles=…)`, **a method
    `Refinement` does not have**, and `gui/src/lib/history.ts` has a case
    labelling such a node. Separately, `NodeMetrics.status` declares
    `"skipped"`, which is `StageResult.status`'s spare value in a second
    container filled from the same `outcome.status`. The chapter documents both
    fields with the vocabulary as it stands and says plainly what nothing sets.
  - **Four facts in neighbouring chapters were wrong, and a table is what found
    each.** `refining.md` said a `Stage` carries four solver settings and then
    described four *besides* the one it had delegated to `concepts.md` (it is
    five); `TreeHeader.data_fingerprint` is a sha256 **truncated to 32 hex
    digits**, not a full one; `ReflectionState` is not "the state outside the
    parameter vector", since Pawley puts exactly those intensities into it. The
    fourth is the merge direction above. Transcribing a field into a table is
    what forces the check that reading the docstring does not.

- **2026-08-17 (`using/refining.md`)** — seven commits on
  `wp1067-using-refining`, six of content and one of handover. No
  `### Inherited` to prune (still none on this WP; the two "Inherited" strings
  in this file are prose about *1003's* mailbox).

  **The measure-first rule paid for the third time, and differently.** The task
  line named seven subjects; measuring which names each page already spells
  moved two of them out and revealed one was not what it said. `concepts.md`
  owns plans — the seven presets, the stage diagram, the globs, the McCusker
  order and `Stage.restraint_weight_scale` — so this chapter takes only what a
  *program* cannot get from prose: the registry and the serializable twins.
  `results.md` owns `Diagnostic` in full (7/7), so guards link there.
  **And `Refinement.fit` takes no `solver=` or `backend=`**, which the task line
  assumed: they are `Refinement.__init__` arguments, also on `refine`. That is
  a coherent design (they decide how every residual in the object is computed,
  so they are not per-fit) and it is now the chapter's opening table, because a
  reader who guesses wrong gets a `TypeError`.

  **The chapter found a fourth derivation rule, and it was worth more than the
  chapter.** `PlanInfo.modes` failed to resolve, and the cause is that **a
  dataclass field with no default is never assigned on the class** — `dir()`
  cannot see it, `getattr` returns `None`. Only *defaulted* fields were
  counted, so `Stage.max_iter` was on the surface while `Stage.name` and
  `Stage.turn_on` were not. Measured: **24 names** hidden, including all four
  fields of `GuardFinding` and of `PlanInfo`, eleven of `ReflectionRow`,
  `RefinementPlan.stages` and `SharingMap`'s two. Absent from the denominator
  with the partition green — the `_SURFACE_FLAGS` shape this module exists to
  prevent, and rule 3's failure one container over. Both halves were fixed in
  one commit because they fail apart: `declared_members` fixes the denominator,
  `_step` fixes resolution, and a name that resolves but is not counted is the
  same bug wearing the other hat. `GuardReport`'s ten fields correctly stayed
  out, being neither exported nor reachable.

  **Numbers** (`[dev]` venv — no jax, no torch; darwin/arm64). Fast selection
  **2402 passed / 117 skipped in 3:18**, counts identical to this session's
  starting tree: two test *helpers* changed, no test added. The full suite was
  **not** run — docs plus two test helpers and one generated file cannot move a
  measured number (`tests/CLAUDE.md` § Running, rung 3); the standing Linux
  figure is still **2561 passed / 88 skipped in 1:51:56** (`[dev,jax]`, nightly
  32017322140). Surface **1298 → 1322** (the 24 above). Partition:
  **544 documented, 778 deferred**, from 473/849 once the derivation was fixed,
  so **71 names froze**. `sphinx -W` clean; `test_examples.py` 4 passed; ruff
  clean. The page was audited at 1100 px in both themes with
  `scrollWidth == clientWidth` on every element in `main` and no body overflow,
  and read at both crops rather than only measured.

  **In flight: nothing.** Working tree clean.

  **Next (1.0.x).** Four chapters. `using/history.md` + `using/projects.md` is
  the natural pair to take next, and this session leaves it better set up than
  it found it: `Refinement.snapshot` is documented here as returning a
  `RefinementState`, and `RefinementCancelled.node_id` already introduces a
  node as the thing a working state stands at. Watch the same overlap the
  data.md session flagged — `files.md` owns the on-disk `.rex` layout, so those
  chapters own the *DAG* and the *document*, not the directory. Keep appending
  promotions to `docs/releases/1.0.2.md`, still unreleased. **`Refinement.suggest`
  and `Refinement.predict` are unassigned**: `suggest` plausibly belongs to
  `report.md` (Layer 2 is the same "what next" surface) rather than to any
  remaining chapter, and something must take both before the bucket empties.

  **Gotchas.**

  - **A false release-notes claim, caught the same way the data.md session
    caught its own.** The freeze paragraph named eight types as wholly frozen;
    three-eighths was false, because prose enumeration counts for a reader and
    not for the guard. `PlanInfo`'s three text fields were shown as attribute
    access on a variable (`info.title`), `Stage.name`/`turn_on` were described
    in a sentence, and — the new one — **`rx.PlanSpec.from_plan` does not
    count**, because the scanner strips `rietx.` and not the `rx.` alias every
    example uses. Write the bare qualified name in prose at least once. The
    chapter was fixed rather than the claim, and seven more names froze.
  - **`ROADMAP.md`'s cap was paid by consolidation, not the predicted raise.**
    The previous session recorded that raising was the only fix left because
    the narrative had no second copy. Two paragraphs had one: the
    `guillemot-study` prior art is in `v1.0.md` § "Indexing joined v1.0" with
    the `git show` recipe, and the vmap sizing note is in `v0.4.md` twice. Both
    deleted; the five post-2026-08-05 close narratives moved to `v1.0.md`
    § "The WP-table narratives, second pass". **400 → 355, cap unchanged.**
    Removing the prose then exposed what it was hiding: three of the four
    tables under "### v1.0 — indexing" hold no indexing WPs, and only the
    paragraphs between them made the splits look deliberate. Before assuming a
    cap must rise, grep the milestone records for the paragraph.
  - **CI's only red for a whole afternoon was GitHub's.** A `fast py3.13` job
    failed in `Set up job` at 56 s, unable to download the `setup-uv` action
    tarball during a GitHub incident with ~50 % archive-download error rates;
    `lint` hit the same 502 and recovered on retry. Nothing in the tree was
    implicated, and the rerun passed. Two operational notes: a job that fails
    in under a minute has failed before reaching any repo code, and
    `gh pr checks` reads GraphQL, which was itself 503-ing — `gh run list` goes
    through REST and kept answering.
  - **The `"skipped"` status and `correlation_warnings` are the same defect as
    `at_bound`, from the other direction.** Both filed to 1076's mailbox rather
    than documented. Worth carrying as a pattern: writing a reference chapter
    *over a type* is what finds an unwritten field, because documenting a field
    forces the question "what writes this?", and three of the four found so far
    came from that question rather than from reading the code.

- **2026-08-17 (`using/model.md`)** — six commits on `wp1067-using-model`, four
  of content and two of handover: the session's shape changed after the first
  one, when the user set the freeze aside and asked for the robust fix instead
  (first gotcha).
  No `### Inherited` to prune: yesterday's session consumed and deleted it, and
  the two `### Inherited` strings still in this file are prose about *1003's*
  mailbox, not a section here.

  **The predecessor's advice worked, and it should be followed again.** The task
  line named four subjects; measuring which names each existing page already
  spells reassigned three of them before a word was written. `data.md` documents
  `Parameter` field by field, `transform` and the softplus underflow included,
  so the transform section here is only the part it does not cover: how physical
  bounds map into the internal variable. `concepts.md` owns the tie verbs and
  `TieSpec.user`. Part 2's `parameterisation.md` owns `par-affine`, the
  cell-tie settings and the DOF bases. What was genuinely undocumented is the
  **table** between the objects and the solver, so the chapter is the dot-path
  grammar, `Refinement.parameters` → `ParameterRow`, the three hold reasons,
  the bound mapping, the two editing verbs, and the fit's own view of the same
  table. Chapter run is now install → quickstart → data → **model** →
  concepts → results → report → files → agents.

  **`ParameterTable` is not on the public surface**, which the task line assumed
  it was. It is neither exported nor reachable through an exported type's
  fields, so a chapter written over the class would have documented nothing the
  partition counts and pointed a reader at a private import. The chapter names
  it once as the mechanism and is written over `Refinement.parameters`.

  **`RefinedParameter` was homeless and is now here.** `results.md` covers
  statistics, R-factors, geometry, restraints and diagnostics but never the
  refined values; its docstring pairs it directly against `ParameterRow`
  ("unlike … which reports what a fit refined"). The two views of one table
  belong in one chapter, and `results.md` now says so in its opening.

  **Numbers** (`[dev]` venv — no jax, no torch; darwin/arm64). Fast selection
  **2402 passed / 117 skipped**, run twice at **2:40 and 3:05** on the same tree,
  which is the range rule earning its keep on one machine in one session. Counts
  identical to this session's starting tree: no test was added, no source file
  changed. The full suite was **not**
  run — docs plus one generated data file cannot move a measured number
  (`tests/CLAUDE.md` § Running, rung 3); the standing Linux figure is still
  **2561 passed / 88 skipped in 1:51:56** (`[dev,jax]`, nightly 32017322140).
  Partition: **473 documented, 825 deferred** of 1298, from 444/854 at session
  start, so **29 names froze** (31 before the two `RefinedParameter` fields went
  back to provisional; see the first gotcha). `sphinx -W` clean; `tests/test_examples.py`
  4 passed; ruff clean. The page was audited at 1100 px in both themes with
  `scrollWidth == clientWidth` on every element in `main`, and all four
  `{eq}` references plus all 22 chapter links resolve to real anchors in the
  built HTML.

  **In flight: nothing.** Working tree clean.

  **A cap note for the next session.** `docs/ROADMAP.md` sat at exactly its
  400-line cap, so adding 1076's index row failed
  `test_docs_consistency.py`. It was paid for by demoting the 1066 naming
  paragraph in § Current focus, which was triplicated: root CLAUDE.md carries
  the rule and `_about.py`'s docstring carries all of it in more detail. The file
  is now at 400 again, so **the next WP row will fail the same way** and there is
  no third copy left to trim; the honest fix then is to re-pin the cap in
  `SIZE_CAPS` with a reason, the way root CLAUDE.md's 600 → 620 was.

  **Next (1.0.x).** Five chapters. `using/refining.md` is the natural next one:
  it is the other half of what this chapter set up (a glob names parameters,
  a stage decides when to free them), and `results.md` already took its
  statistics. Keep appending promotions to `docs/releases/1.0.2.md`, which is
  still unreleased.

  **Gotchas.**

  - **`RefinedParameter.at_bound` and `.initial` are public and nothing in the
    package writes either.** The fit builds each row with `path`, `value`,
    `vary` and `stderr` only (`refine.py`, the `e.vary or e.tie is not None`
    loop), and nothing reads either field anywhere. The draft table explained
    `at_bound` as "the fit stopped against a bound, so the esd understates the
    truth" — confident, plausible and wrong twice over, since the mechanism is
    the `BOUND_HIT` diagnostic and the esd claim was unsourced. **Both names are
    left provisional and the chapter documents neither**, which is this WP's own
    rule (a name a chapter cannot honestly freeze stays in the bucket) applied
    to the first surface defect a chapter has found. The fix is
    **[1076](1076-result-row-honesty.md)**, written this session with the design
    settled by user decision: `at_bound` becomes `bool | None` populated from the
    guard's single computation, and `initial` is deleted. The reasoning is worth
    carrying, because it generalises — **the defect was never that the field is
    unpopulated, it is that its empty state lies.** `initial: null` reads as
    absent; `at_bound: false` reads as a measurement. Fixing the empty state
    makes the bug structurally unrepeatable whoever forgets a future code path,
    which a required field does not, since anyone may pass `False` for
    convenience. That is WP-1072's rule applied to a boolean.
  - **The dot-path guard truncates at a numeric component, so an indexed
    `instrument.…` path is checked as a prefix that does not exist.** `DOTTED`
    forbids a digit after a dot, so `instrument.source.lines.1.weight` reaches
    `test_parameter_dot_paths_resolve` as `instrument.source.lines`, which
    matches no real path and fails. `phases.0.cell.a` escapes only by accident:
    it truncates to `phases`, which does not start with a `PATH_ROOTS` prefix
    and is skipped. Write an indexed instrument path as a glob
    (`instrument.source.lines.*.weight`) and it both passes and stays honest.
  - **A resolving `{eq}` reference can still cite the wrong step of a
    derivation.** The draft cited `est-cov` for the propagation of a tied row's
    esd. `est-cov` is χ²_red·(JᵀJ)⁻¹, the covariance of the *free* internal
    parameters; the propagation is σ² = diag(C·Cov·Cᵀ) in
    `ParameterTable.stderr_physical`, which Part 2 does not label. The chain is
    now stated in order, and this is the same class as yesterday's
    `pos-displacement` note.
  - **The three hold flags do not sum to the held rows, and the chapter says
    so.** On the LaB6 fixture, asking for the Le Bail listing marks thirteen
    rows `mode_fixed` while the refinable count falls only 25 → 19, because
    seven of the thirteen were already locked or tied. That is the argument for
    `refinable` being one predicate rather than three, and it is measured
    rather than asserted.
  - **A coordinate DOF is a displacement; an ADP or Stephens DOF is absolute.**
    Visible for free in the tie text: `phases.0.atoms.1.x` describes itself as
    `0.19964 + 1·phases.0.atoms.1.dof.0`, the constant being the stored
    coordinate. Worth a sentence in any chapter that shows a tie, because the
    two conventions sit one line apart in the same listing.

- **2026-08-17 (`using/data.md`)** — five commits on `wp1067-using-data`, plus
  one rider that is not this WP's (`da804f3d`, recording that the repaired
  SRM 676a stationary plan held on Linux in nightly 32017322140 — yesterday's
  release session owed that measurement).

  **The mailbox is consumed and deleted.** Its one entry, WP-1003's "documenting
  a name now freezes it", was still true and governs every remaining chapter
  rather than being news, so it is Context now. One consequence it implied but
  did not spell is written down there: a name a chapter cannot honestly freeze
  stays in the bucket instead of getting a passing mention.

  **The task line was stale and the chapter is not what it asked for.** WP-1068's
  `using/files.md` landed the whole file side in between — `read_pattern` with
  `scan=`/`block=`, the reader's four consequences, `Structure.from_cif` and the
  two CIF repairs, `save_instrument_profile`/`load_instrument_profile` — so
  writing that again would have been a second authority for one fact. The seam
  now: **`files.md` is what is on disk, `data.md` is what the objects contain,
  and `using/model.md` is still the parameter table over them.** Whoever takes
  the next chapter should check the same way, by measuring which names a page
  already documents rather than reading the task line, because two later
  chapters (`history.md`/`projects.md`, `exports.md`) have the same overlap with
  `files.md`.

  **Numbers** (`[dev]` venv — no jax, no torch; darwin/arm64). Fast selection
  **2402 passed / 117 skipped in 2:44**, identical to this session's starting
  tree: no test was added. The full suite was **not** run — docs-only plus one
  generated data file cannot move a measured number (`tests/CLAUDE.md`
  § Running, rung 3); the standing Linux full-suite figure is **2561 passed /
  88 skipped in 1:51:56** (`[dev,jax]`, nightly 32017322140). Partition:
  **444 documented, 854 deferred** of 1298, from 303/995 at session start, so
  **141 names froze**. `sphinx -W` clean; the new page rendered at 1100 px in
  both themes with no element overflowing, and all 22 equation
  cross-references resolve to real anchors in the built HTML.

  **In flight: nothing.** Working tree clean.

  **Next (1.0.x).** Six chapters. `using/model.md` is the one to take next, for
  a reason this session created: `data.md` now defines the objects its table
  addresses, so it can be about paths, ties, transforms and the three reasons a
  row is held without re-introducing the fields. `docs/releases/1.0.2.md`
  exists and is unreleased — every further chapter appends its promotion there
  rather than starting a new file, and whoever cuts the release follows
  `docs/RELEASING.md`.

  **Gotchas.**

  - **The guard counts a name only where a chapter spells it *qualified*, in
    code.** "Fifteen coefficients `StephensStrain.s400` through
    `StephensStrain.s004`" documented two of fifteen and left thirteen in the
    bucket; the same trap took five `kind` discriminators, written as "each has
    a `kind` field". Prose enumeration counts for a reader and not for the
    partition, which is the point of the design — but it means a release-notes
    claim about a *type* being frozen has to be checked per name. Both of mine
    were false when written, and the chapter was fixed rather than the claim.
  - **`concepts.md` had the Lorentzian letters swapped** (`x` tan θ, `y`
    1/cos θ; the model is Γ_L = x/cosθ + y·tanθ). It is the exact letter-swap
    class every profile docstring in the package warns about, it sat in the
    table a reader consults to write a plan, and nothing could have caught it:
    the guard checks that `instrument.profile.x` resolves, not what the sentence
    claims about it. Writing the same fact into a second table is what found it,
    which is an argument for reference tables over prose wherever a convention
    is involved.
  - **`pos-displacement` is the flat-plate displacement equation, not the zero
    point.** The zero-point error is prose in `peak-positions.md` with no label,
    so there is nothing to cite for `Instrument.zero_shift`. A `{eq}` reference
    that resolves is not a reference to the right equation, and `-W` cannot tell
    the difference.
  - **A five-column reference table does not fit.** The geometry table needed
    898 px in Furo's 742 px content column, so it scrolled inside its own
    wrapper with the "Meaning" column clipped. Splitting it into shared,
    capillary and flat-plate is both narrower and better reference structure.
    Measure it rather than guessing: the check is `scrollWidth` against
    `clientWidth` per element at 1100 px, in both themes.
  - **Do not explain a bound you cannot source.** The draft said `u` and `v`
    carry negative lower bounds "because the Caglioti form is an empirical fit
    rather than a sum of variances". Nothing in the package says that. The text
    now states the bounds and what has to stay positive.

- **2026-08-16 (the McCusker set's manual pass)** — six commits on
  `wp1067-manual-mccusker-pass`. The set (1069–1074) shipped between 1068 and
  this session and each WP appended to the manual as it landed; this pass is
  what those six additions add up to, plus the three things none of them owned.
  **The mailbox is consumed and deleted** — 1069's, 1071's and 1072's entries
  all warned about the same move, § Fit statistics, and it has now happened;
  every rule they asked to keep is in `using/results.md`, and
  `test_manual_api.py` was re-run after it, which is what those entries were
  really asking for.

  **Part 2 was the real gap, and no single WP could see it.** Four of the six
  added physics or statistics that Part 1 then described in prose while Part 2
  carried nothing — which inverts the tree's own rule that Part 1 links a
  numbered equation instead of restating one. Part 2 now has
  `par-restraint-weight` (eq (7)'s c_w and the two seams it must not cross),
  `est-structure-r` (R_B and R_F, with the partition bias and the unweighted
  caveat), `est-mind` (Altomare's overlap-corrected count) and `est-derived`
  (gᵀ·Cov·g, and the four ways a derived esd is absent rather than zero), plus
  five injected constants. The standing rule went into root CLAUDE.md's manual
  bullet, since the next correction will hit it too.

  **`using/results.md` is a new chapter, not a new subject.** `concepts.md` had
  grown to 570 lines with § Fit statistics at 215 of them, covering four
  different questions because six WPs appended to whichever section was
  nearest. It splits along the seam the chapter's own opening names: concepts
  keeps how a refinement works, results takes what comes back. Chapter run is
  now install → quickstart → concepts → **results** → report → files → agents.

  **Restraints were undocumented.** 1074 documented how to *schedule* c_w in a
  manual that never said how to declare a bond restraint, which is visible only
  from outside that WP. `concepts.md` now has the three kinds, their PBC image
  selection and what a row does to the residual; `results.md` reads
  `RestraintReport` back. Together with naming every field those sections
  introduce, the deferred bucket went **1044 → 1002**.

  **Three staleness fixes outside the set's own sections**, all of the same
  shape — a WP edited the section it was about, and the sentence that had to
  move was somewhere else: `report.md` still said Layer 1 regresses position
  against the flat-plate template set (geometry-keyed since 1073, and so are
  the Layer 2 actions); `files.md` still described the CIF as structure + fit
  (it now carries R_B/R_F and the `_geom_` loops with their symop list);
  README described the old chapter run.

  **Three figures, each drawn from a case that is already asserted** —
  `make_figures.py` imports the fixtures rather than copying them, which is why
  `test_restraints.py` grew a plain `schedule_inputs()` beside its fixture.
  Measured while drawing them: the c_w pair lands Zr–O1 at **1.872 Å against
  4.834 Å** (Rwp 0.0327 against 0.0393) and the difference curves are nearly
  indistinguishable, which is the figure's whole point; the LaB6 sweep holds
  **26 reflections while the effective count falls 22.0 → 3.7**; the geometry
  esd ratio is **0.86–1.41 over 88 distances** at Rwp 0.0818.

  **Numbers** (`[dev]` venv — no jax, no torch; darwin/arm64). Fast selection
  **2395 passed, 117 skipped in 2:30**, identical to WP-1074's final tree:
  this session adds no test. The full suite was **not** run — docs-only plus
  one fixture refactor cannot move a measured number (`tests/CLAUDE.md`
  § Running, rung 3). `sphinx -W` clean; the five touched pages screenshotted
  in both themes at 1100 px with `scrollWidth == clientWidth` on every one.

  **In flight: nothing.** Working tree clean.

  **Next (1.0.x).** The seven post-release chapters, unchanged. `results.md`
  makes two of them smaller than they were: `using/refining.md` no longer owes
  the statistics, and `using/exports.md` no longer owes the CIF's contents.

  **Gotchas.**

  - **A figure caught a ratio the prose had the wrong way up.** WP-1072
    measured full/diagonal 0.713–1.152; the manual sentence built from it read
    as diagonal/full, which is 0.86–1.41. Both directions are defensible and
    only one matches the number printed beside it. Drawing it is what found it.
  - **The walkthrough's own fit cannot show that claim at all.** Under
    `mccusker_default` the only free parameter a cubic distance depends on is
    `a`, so the quadratic form has one term and full and diagonal agree to the
    last digit — the figure needs `mccusker_structural`, and "the spread
    appears only once the coordinates refine" is now a reading rule in the
    chapter rather than an accident of which plan someone ran.
  - **Cox & Papoular's weighted R_B was left uncited.** The `structure_r_factors`
    docstring names it; it is in neither `references.bib` nor the local corpus,
    and Part 2's guard is every bib entry being cited, not every claim carrying
    a key. The sentence says no weighted variant is computed here and names
    nobody.
  - The manual's figures and `tests/` are now coupled in one direction:
    `make_figures.py` imports two test modules. It runs by hand, so a rename
    breaks a regeneration rather than a build — recorded in its docstring.

- **2026-08-14 (review follow-up)** — nine review items on the landed floor,
  five commits on `wp1067-manual-followup`. **2269 passed / 108 skipped in
  4:07** (`[dev]` venv, darwin/arm64), identical to the entry below: this
  session added no test, and the two `test_gui_dist.py` failures it did cause
  were a stale dist stamp, not a regression. `npm --prefix gui test` 408/408.
  None of the 1.0.x chapters moved, so the WP stays 🔄.

  **The three that were more than editing:**

  - **`baselines` deleted**, closing 1003's item rather than deferring it
    again. Nothing named the extra but the manual paragraph apologising for
    it. `DESIGN.md` records the reversal beside the decision it reverses,
    because a design record that still promises an extra the build does not
    have is worse than one that never mentioned it.
  - **`pr` → `rx` across 63 files.** Mechanical except in three places, and
    all three are the reason a sweep like this is not "just tests":
    `NodeAction.api_call()` renders `pr.Refinement(...)` as *text a user reads
    back* in the GUI history panel, the GUI's vitest fixtures quote those
    strings, and `capabilities()` imports the package under the alias — where
    the pattern `\bpr\.` misses the bare `pr` in `hasattr(pr, name)` and leaves
    a `NameError` behind. `api_call()` is computed and never persisted, so no
    on-disk format moved and no contract version bumped. The committed dist's
    `build-info.json` did have to be rebuilt: vitest fixtures are hashed
    sources, so editing one stales the stamp while the built assets stay
    byte-identical. `test_gui_dist.py` caught it, which is the gate working.
  - **"Which document does an agent read first?" has two answers and one of
    them was unrouted.** For an agent *in the repo* it is `CLAUDE.md` — a
    contributor rulebook that, until this session, never said so, so an agent
    that arrived to *use* rietx read 600 lines of rules for a different job
    before finding out. Four-line router added at the top. For an agent
    *calling* the package it is `agent._TOOL_DESCRIPTION`, which is already
    written for that reader and already points at `AGENT_PROTOCOL.md` by a
    repository-relative path that does not resolve after `pip install`. That
    one stays 1003's (hosting is release scope); `using/agents.md` now names
    the description as the first thing a calling agent ever reads, rather than
    burying the dangling pointer in a note.

  **Editing, but load-bearing:** the manual now states who it is for and
  which surfaces are machine-first (the `FitReport`, the JSON envelope,
  `capabilities()`, the event ladder, the codes) with both halves said out
  loud — documented for humans because you cannot trust what you cannot read,
  but not shaped for human-first consumption; the naming rule (case is
  Python's convention; `RefinementResult.plot` is written under its class
  because that is what the guard resolves); the extras-install syntax, quoted
  for zsh; the measured `converged 0.0932` and the fact that **Rwp is a
  fraction, not a percentage**, which Part 1 had never said; and the
  empty-text cross-reference to the report chapter, which MyST renders as the
  target's *title*, so the sentence read "what the package hands you instead is
  Reading the report".

  **An Orwell-rules rewrite of `using/quickstart.md` was produced for review
  and deliberately not committed** — Orwell's six rules plus ASD-STE100, minus
  rule 9 (American spelling), which the house style overrides. It was measured
  by swapping it in: it passes `test_manual_api.py` and `test_manual.py`
  unchanged, which is the useful result, because the guards constrain *names*,
  not sentences. Prose style is a free variable here and a rewrite cannot
  silently drop coverage — every surface name the chapter documents has to
  survive the rewrite or the partition fails, and it did. Whoever picks
  this up decides one thing first — the manual's voice today spends em-dashes
  and appositives to carry a second clause per sentence, and the rewrite trades
  that for shorter sentences and a named actor. It is a whole-manual decision,
  not a per-chapter one.

- **2026-08-14 (execution session)** — **§ Floor landed in full; 1003 is
  unblocked.** Eleven commits on `wp1067-user-api-manual`, all eight floor
  items ticked. The 1.0.x chapters remain, so the WP stays 🔄 and the deferred
  bucket is not yet empty.

  **Done.** The tree is one Sphinx build in two parts; Part 2's twelve chapters
  and all seventy-four equation numbers were verified byte-identical before and
  after by diffing the rendered HTML, so `{eq}` cross-references and any prose
  citing "(3.2)" survived. `tests/api_surface.py` derives the surface;
  `tests/test_manual_api.py` guards Part 1 by name; `install`, `quickstart`,
  `report` and `agents` are written; `tests/test_examples.py` executes both
  `examples/` walkthroughs; README carries the two-part pointer, the beta
  declaration and re-measured counts.

  **Three predictions in this WP did not survive measurement, and the pattern
  is worth more than the corrections.** Every one was found by *using* the
  guard, never by reading code:

  - **The surface is 1235 names, not ~147** — 127 classes, 902 fields, 151
    methods, 27 instance attributes, 25 functions, 2 constants, 1 module. The
    estimate appears to have counted neither the fields nor the closure.
  - **Two derivation rules were missing from the WP's two.** The closure must
    follow **exported functions' signatures** (`Capabilities`, the return type
    of `capabilities()` and the whole subject of `using/agents.md`, was on no
    list at all), and **instance attributes must be read from source with
    `ast`** — a plain class assigns `self.history` in `__init__`, where
    `dir()` on the class cannot see it, so `Refinement.history`, `Project.doc`
    and `RefinementCancelled.node_id` were silently absent. Each gap surfaced
    as the guard *rejecting a page that was correct*, which is the strongest
    argument available that the guard works.
  - **The examples do not need the `slow` mark.** The cost model assumed a
    chapter running a real fit would turn the docs guard into an acceptance
    suite; measured, `nac_11bm.py` is 3.5 s and `srm660c_lab.py` 3.3 s ([dev],
    darwin/arm64), 4.45 s for the four tests together under `-n auto`. They run
    in the fast suite, because a broken walkthrough should fail on the push
    that broke it. One line adds the mark if either grows.

  **One deliberate divergence.** The WP planned a hand-written chapter
  assignment beside the exclusions. Documented-ness is **derived** instead — a
  name counts when a chapter spells it *qualified*, in code (a span, a python
  fence, or a `{literalinclude}`d script); prose is not scanned, because "the
  Structure schema" in a sentence is not documentation of `Structure`. A
  hand-written assignment is the same list-nobody-regenerates the derivation
  exists to avoid, and it can point at a chapter that never mentions the name.
  The cost is that a chapter writes `Statistics.rwp` rather than relying on
  `result.statistics.rwp`, which a reference chapter wants anyway.

  **Both fault injections the WP demanded, plus a third failure it did not.**
  Adding `Refinement.polish` to `src/` and touching nothing else fails the
  partition naming it. Renaming `BackgroundCapability.available` → `.usable`
  fails three ways at once (stale manual token, executed block raises, new name
  in no bucket) — and writing that injection first exposed a hole: resolution
  walked from `rietx`, so a *correct* dotted name on a reachable-but-unexported
  type failed for the wrong reason. Fixed before the injection was run.

  **Numbers ([dev] venv, darwin/arm64 — no jax, no torch).** Fast selection
  **2269 passed / 108 skipped in 2:57**. WP-1066 recorded 2257/108, this WP
  adds exactly 12 tests (8 in `test_manual_api.py`, 4 in `test_examples.py`),
  and 2257 + 12 = 2269 with **skips unchanged** — twelve passes, no new skip.
  Full selection **2375 passed / 117 skipped / 1 failed in 29:40**; the full
  delta could *not* be checked the same way, because the weekly log § Numbers
  points at is dead (below). Partition: **149 documented, 1086 deferred** of
  1235. Coverage partition, not a quality measure.

  **In flight: nothing.** Working tree clean, all eleven commits landed.

  **Next (1.0.x).** The seven post-release chapters in § Tasks, in any order;
  each one shrinks `tests/api_surface_deferred.txt`, and the WP closes when
  that file has no names left. Regenerate it with
  `python -m tests.api_surface --write-deferred` — never hand-edit it, since
  being generated is what makes a new public name fail the partition instead of
  hiding in it.

  **Gotchas.**

  - **A cross-reference lands in the commit that creates its target.** A
    MyST link to a page that does not exist yet is a `-W` build failure,
    so `install.md` and `quickstart.md` shipped with prose references that
    became links one commit later. Write the chapter, then the links back to it.
  - **Regenerate the deferred bucket in the same commit as the chapter.** A
    newly documented name sits in *two* buckets until you do, and the partition
    fails on the overlap — by design, but it looks like a regression if you
    have forgotten why.
  - **Root CLAUDE.md was at exactly its 600-line cap.** Raised to 620 with the
    reason recorded in `SIZE_CAPS`, after the operating detail went down a rank
    (the three derivation rules live in `api_surface.py`'s docstring). What
    could not go down a rank is the one clause a session that never opens
    `docs/manual/` still needs: adding a public method or field fails the
    manual's partition until it is documented or deferred.
  - **The `_build/` exclusion in `CHAPTERS` is defensive, not load-bearing
    today.** The WP predicted `rglob` would collect a stale build tree; measured,
    sphinx's html builder writes sources as `*.md.txt`, so nothing matches. It
    was still demonstrated (planting a `.md` under `_build/html/_sources` and
    re-collecting still gives 13 chapters, none from `_build`) and kept, because
    any builder that copies sources verbatim would fire it.
  - **Two things were filed to [1003](1003-api-freeze-pypi.md) rather than
    fixed**, both blocking a release and neither this WP's: a fifth
    load-sensor acceptance row (fluorite `search_complete`, fails under
    `-n auto`, passes serially in 207 s — this WP added two test modules and is
    a plausible trigger; user decision on 2026-08-14 was to file and stop), and
    the **weekly `full` CI job, which has not completed since 2026-08-02** —
    cancelled at exactly 2h00m against `timeout-minutes: 120`, so § Numbers'
    designated source for full-suite counts has been dead for twelve days and
    nobody saw it, because a cancelled run is amber rather than red. Also filed:
    the `baselines` extra installs `pybaselines`, which no module imports.

- **2026-08-14** — created, with WP-1017 deferred past the public release on
  the same decision, then revised over two critical-review rounds. Not
  started.

  Round 1 moved the acceptance denominator off `rietx.__all__` (71 names,
  almost none of them what a user calls), split the tasks into a **floor**
  that gates 1003 and a post-release remainder so a ten-chapter manual cannot
  silently slip the release, made `examples/` the single authority for
  walkthroughs (`{literalinclude}`d and *executed*, because nothing in
  `tests/` runs those scripts today and README already holds a second
  unguarded copy), and gave the block-execution guard a cost model under
  `tests/CLAUDE.md`'s budget rule.

  Round 2 caught that round 1's fix carried the same bug it was fixing: a
  **hand-curated** list of methods cannot notice a new public method, so the
  partition would stay green while coverage silently dropped —
  `_SURFACE_FLAGS` one level up. The surface is now **derived** and only the
  exclusions are written by hand. It also replaced a circular floor criterion
  ("documented iff in a floor chapter") with a full partition plus a
  `deferred-1.0.x` bucket, named the `using/report.md` ↔ AGENT_PROTOCOL split
  (object model vs judgement) before that chapter can drift into paraphrase,
  and split example execution into `tests/test_examples.py`.

  Three factual corrections across the rounds: WP-1047 landed five vendor
  formats on 2026-08-08/09 taking the total to ten (not "ten in three days");
  WP-0604 *deferred* autodoc to 1003 rather than rejecting it, so that
  question is open; and 0604's docstring rule forbids *silent* patching, not
  patching, so this WP follows it rather than diverging.

  Gotchas: the "flat filenames inherit the guards for free" argument is false
  (they are vacuous on Part 1 pages either way — the reason to stay inside
  `CHAPTERS` is future guards), `rglob` walks `_build/` unless excluded, and
  `{literalinclude} ../../../examples/…` from `docs/manual/using/` was
  measured `-W`-clean on a mirrored tree with this venv's sphinx (a wrong `..`
  count clamps to a nonexistent prefix and fails the build, which is the good
  failure mode).

- **2026-08-14** — pre-execution check (round 3). Every load-bearing claim
  verified against the repo: `CHAPTERS` is a flat glob; `agent.py` names
  `docs/AGENT_PROTOCOL.md` in `_TOOL_DESCRIPTION` and `python_arm.py` ships it
  verbatim with the byte-equality pin; nothing in `tests/` executes
  `examples/`; README quotes 1197/1116 and is the PyPI `readme`; the wheel
  packages only `src/rietx`; `[gui]` is plotly-only; `capabilities()` carries
  the reader `title`/`sniff`/`sigma` and plan `when_to_use` prose; the
  working-tree ROADMAP/1003/1017 sync passes `test_docs_consistency.py`. Two
  derivation gaps found by measurement and folded into Context (declared-not-
  inherited membership: 1099 → ~147 names; closure over reachable unexported
  types: `Statistics` holds `rwp`). Noted for `tests/test_examples.py`: the
  example scripts write their outputs next to themselves (`examples/nac_fit.png`,
  gitignored), so the runner either accepts that or copies to a tmp cwd — say
  which in the test's docstring.
