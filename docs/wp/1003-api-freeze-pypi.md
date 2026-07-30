# WP-1003 — API freeze + PyPI release

Milestone: v1.0 · Status: ⬜ not started (stub — expand before starting)
Depends on: WP-1001, WP-1002, WP-1004…WP-1017 (the GUI expansion — this WP is
the milestone's last row, so the freeze covers a surface the GUI exercised)

## Scope (carried verbatim from the pre-split roadmap)

- API freeze, PyPI release (name `pxrd-refine` verified available)

## Inherited

From **WP-1014** (import & in-GUI editing, landed 2026-07-30) — **one question,
and some new public surface.**

The question: **should `Atom.species` validate?** A `Structure` carrying a species
no form-factor table knows (`"D"`, `"Xx"`, a CIF's `"Wat"`) validates fine today
and fails at *stage compile*, a long way from where it was typed.
`GuiSession._as_structure` now refuses it at the GUI boundary, naming the atom —
which means the GUI is stricter than the API it fronts. That asymmetry is
defensible (an earlier, better message on the path a human takes) and it is
exactly the kind of thing a freeze should make a decision about rather than
inherit: either the schema validates and the two agree, or the difference is
documented as deliberate.

The surface, all new here and all inside `pxrdref.gui`: the module
`pxrdref.gui.imports` (`UploadStore`, `MAX_UPLOAD_BYTES`, `UPLOAD_KINDS`,
`INSTRUMENT_PRESETS`, the `preview_*` functions), `UPLOAD_ROUTES` in `server.py`,
`GuiSession.upload`, `GuiSession.structure_aniso`, and two additive route
changes — `GET /api/structure` gained a `sites` arm, and `POST
/api/structure/aniso` is new. The upload routes are also **the only ones in the
wire surface whose body is not JSON** (raw bytes; filename and reader options in
the query string), which any statement of the HTTP contract has to say out loud.


From **WP-1013** (landed 2026-07-30) — **the wheel redistributes third-party
JavaScript, and until now nothing said so.** The committed dist ships inside the
wheel by design, so `assets/app.js` carries Svelte's runtime (true since WP-1010,
never written down) and `assets/vendor-cm.js` carries CodeMirror 6 — ~330 kB of
it. Both are MIT and unmodified; `ATTRIBUTION.md` now has a *Bundled frontend
code* section stating it, with `gui/package-lock.json` as the version statement.
What this WP owes at publication is the packaging half rather than the prose: a
wheel that redistributes MIT code should carry those licenses, and the sdist/wheel
metadata currently names only pxrd-refine's own. Worth deciding at the same time
whether the `[gui]` extra's description should mention the bundle size, since
`pip install pxrd-refine[gui]` now pulls ~460 kB of committed assets whether or
not anyone opens the text pane. `tests/test_gui_dist.py` already asserts every
chunk is *in* the wheel and that none of them names a remote host.

From **WP-1011** (landed 2026-07-30) — **the HTTP wire has a JSON dialect, and
it should be stated rather than inherited.** `json.dumps` writes bare
`Infinity`/`NaN` tokens, which are a Python extension that `JSON.parse` rejects
outright; `gui/server.py` therefore spells a non-finite float as the *string*
`"Infinity"`/`"-Infinity"`/`"NaN"`, matching the schemas' own
`ser_json_inf_nan="strings"`. Nearly every `ParameterRow` has an unbounded side,
so this is the common case, not an edge one. Two consequences for the freeze:
any non-Python client must be told (a `"lo": "Infinity"` that a naive consumer
coerces to `NaN` is a silent wrong bound), and the rule belongs with whatever
statement WP-1017's `gui-power.md` makes about the routes being provisional. A
third option exists and was *not* taken — `null` for non-finite — because it
cannot distinguish +∞ from −∞.

From the **v1.0 GUI expansion** (un-fencing commit, 2026-07-29) — new surface
the freeze must cover, and four decisions parked here deliberately:

- **New freeze surface**: `schemas/params.py` (`ParameterRow`),
  `schemas/plan.py` (the unified `StageSpec`/`PlanSpec` — the unification
  retires the `schemas/history.py` and `agent.py` twins; decide whether the
  re-export aliases are frozen API or a deprecation), `schemas/project.py`
  (`DataRef`/`ProjectDoc`), `capabilities()`, the new `Refinement` verbs
  (`parameters()`, `set_vary`, the set-value verb — WP-1004 settles its
  name against `NodeAction.api_call`'s rendering), and
  `CancelToken`/`RefinementCancelled` (WP-1006).

  *Updated 2026-07-30, WP-1004 + WP-1006 landed.* Now concrete, and the
  top-level exports are already added: `ParameterRow`, `TieSpec`, `PlanSpec`,
  `StageSpec`, `PlanInfo`, `PLAN_INFO`, `PLAN_PRESETS`, `CancelToken`,
  `RefinementCancelled`; the verbs are `parameters()`, `set_vary(globs, vary)`
  and **`set_values({path: value})`** (plural — decided in favour of what
  `api_call` had always rendered, so the persisted `"set_value"` NodeKind
  literal is untouched). Four freeze decisions this leaves:
  (a) the `schemas.history` / `agent` re-export aliases — frozen path or
  deprecation, as above, now that both are one-line `# noqa: F401` imports;
  (b) `NodeAction` gained `seed`/`strain_seed` (WP-1004) and event `data` is an
  open dict (WP-1006) — **the freeze should say explicitly that additive fields
  on these two are not breaking changes**, or every later correction is stuck;
  (c) `ParameterRow`'s field set is pinned to `params.vector.Entry` by test, so
  freezing the row freezes the *internal* dataclass by proxy — say so
  deliberately or the coupling will be discovered the hard way;
  (d) `PlanSpec.stages` is permissive (no `min_length`) because it must read
  pre-v1.0 history headers, with the non-empty check living in the agent
  request validator — that asymmetry is intentional and worth a release note.
- **The HTTP routes and the `.pxt` text format are declared *provisional* at
  v1.0** — schemas frozen, wire/text surfaces not. State this in the release
  notes (WP-1017's `gui-power.md` states it user-facing; this WP states it
  normatively).

From **WP-1007** (capabilities + guard findings, landed 2026-07-30) — new surface
and one open question:

- **New freeze surface**: `capabilities()` and its five models
  (`Capabilities`, `BackendCapability`, `PlanCapability`, `AnodeCapability`,
  `ReaderCapability`), `GuardFinding` (frozen dataclass, its seven constructors,
  and `str(finding)` — a *published* rendering pinned by literals in
  `tests/test_capabilities.py`, because the diagnostics' messages are built from
  it), `GuardReport.findings()`, and the newly exported `auto_background`,
  `diagnose`, `PreferredOrientation`, `capabilities`, `GuardFinding`.
- **`Capabilities` reports four contract versions** — schema, report thresholds,
  event schema, project format. The freeze should state what each promises and,
  in particular, that `features` keys are **additive** (a client must tolerate an
  unknown flag) while removing one is breaking. The flags are derived predicates,
  so `features["indexing"]` flips when `index()` lands with no code change here.
- **Open: should `Diagnostic` grow an optional numeric `value`?** WP-1007 fenced
  it out on purpose (no second diagnostic vocabulary), so a guard's *number* — ρ,
  a block R², a min eigenvalue — reaches a client only inside the message text.
  `GuardFinding` has it as `.value`, but `GuardReport` is transient and never
  serialized, so nothing exposes it. A GUI that wants to sort by ρ has to parse
  prose, which is the failure WP-1007 existed to end, one field short of finished.
  Additive and cheap; decide it here rather than leaving each client to regex.
- `GuardFinding.code` is deliberately an open `str`, not a `Literal` — WP-1028
  adds codes. Say in the release notes that guard/diagnostic codes are an
  extensible vocabulary and that clients must not exhaustively match on them.

From **WP-1005** (project container, landed 2026-07-30) — three freeze
decisions and one new surface:

- **New freeze surface, now concrete**: `schemas/project.py`
  (`DataRef`/`ProjectDoc`, both top-level exports along with `Project`),
  `PROJECT_FORMAT_VERSION` (currently `"1"`, and `Project.open` refuses a
  different *major* by name rather than letting `extra="forbid"` report an
  unknown field), and `io.readers.PATTERN_FORMATS` / `identify_format` — the
  reader dispatch is now a registry two other things quote, so freezing
  `capabilities()`'s reader arm freezes the registry's field names by proxy.
  `read_pattern` also gained a `block=` keyword (additive).
- **Decide whether `RefinementState` grows `excluded_regions`.** It does not
  carry them today, so **a history node cannot say what was excluded when it
  ran** — and excluding a region does not change the pattern fingerprint, so
  nothing refuses a replay against a differently-masked residual. WP-1005 works
  around it by recording the regions in `project.json`, which covers a project
  and covers nothing else (a bare `Refinement` + `PatternData` still has no
  record). The field is additive with an empty default; what is *not* free is
  deciding whether `replay` then honours the node's regions over the caller's
  data. Excluded regions are protocol (CLAUDE.md: mirror them or do not compare
  Rwp), which is the argument for settling this before the freeze rather than
  after.
- **A project's `backend`/`solver` are arguments to `Project.open`, not fields of
  `ProjectDoc`** — deliberately, because a project saved with `backend="jax"`
  would otherwise be unopenable where jax is absent (`Refinement.__init__` fails
  fast by design). If the freeze wants them persisted, it needs a stated
  fallback policy, not just a field.
- **`RefinementResult.history` is a dead field** — declared at
  `schemas/results.py:291` (`list[IterationRecord]`), never populated by any
  writer (verified 2026-07-29; `IterationRecord` has no other consumer).
  Delete or fill; **recommend delete** — the GUI reads the event stream, and
  per-iteration curves in every result would violate the state-not-curves
  rule the history nodes follow.
- **`[gui]` extra + committed-static wheel audit**: `src/pxrdref/gui/static/`
  ships in the wheel (hatchling packages `src/pxrdref` wholesale) — audit
  wheel *and* sdist contents for the static assets, `help.json`, and
  `build-info.json`, and decide whether the `gui/` TS workspace is excluded
  from the sdist the same way the tests question above is decided.
- **Going public zeroes the `gui.yml` CI line** (~3 billed min per
  gui-touching push today) — a fourth entry for WP-1002's "public is the
  same change as three other things" finding below.

From **WP-1002** (CI matrix, landed 2026-07-29) — **going public is not just a
licence decision: three separate limitations here are consequences of the repo
being a private free-plan repo, and they all lift at once.**

- **CI cannot gate anything today.** `repos/…/branches/main/protection`
  returns 403 *"Upgrade to GitHub Pro or make this repository public"*, so the
  per-push matrix **reports** — nothing stops a red push landing on `main`.
  Making the repo public is therefore also the moment to require the `fast`
  jobs as status checks; do both in one change or the freeze rests on a badge.
- **The whole CI cadence is shaped by a budget that publishing removes.**
  There is no CI budget: this repo is private on the free plan (2000
  minutes/month, billed per job rounded up, default spending limit $0 — so
  over-budget means a month with *no* CI rather than a bill). That is why the
  per-push gate runs one Python instead of four, why the full suite is weekly
  rather than nightly, and why macOS + `[torch]` are monthly — macOS bills at a
  **10× multiplier**, so 5 wall-clock minutes there costs 50. Current spend:
  5 per push, 237/month weekly, 66/month monthly. **Publishing makes standard
  runners free**, at which point the three workflows can collapse into one
  nightly and the per-push matrix can carry the full Python range again. Do
  that in the same change as going public, or the coverage stays artificially
  thin for no reason.
- **The supported-Python claim is now measured, and `pyproject` under-states
  it.** 3.11, 3.12, 3.13 *and* 3.14 all install `[dev]` and pass the fast
  suite; `requires-python = ">=3.11"` is right, but `classifiers` names only
  `Programming Language :: Python :: 3` — add the per-version rows for PyPI's
  filters, and decide whether 3.14 is claimed or left allow-fail in CI.
- **Windows passes but is not a supported platform, and the difference is a
  decision this WP has to take.** Probed 2026-07-29: `982 passed / 115
  skipped / 0 failed` on `windows-latest` + Python 3.13 — but only after
  fixing a real bug (`write_qpa_table` wrote `\r\r\n` rows, i.e. corrupt CSV,
  because `csv.writer` output went through text mode) and naming
  `encoding="utf-8"` at every text-I/O site, since the default is cp1252
  there. `tests/test_portability.py` guards both by AST. **No scheduled job
  runs Windows**, so a claim would be a point measurement dressed as support.
  Either add a Windows job — a fast-suite run is ~3 min at a **2×** multiplier,
  so 6 billed minutes: 6/month folded into `monthly.yml`, 26/month if weekly,
  and free once the repo is public — and then
  claim `Operating System :: Microsoft :: Windows`, or claim
  `POSIX`/`MacOS` only and say Windows is untested. Do not claim it on the
  strength of the one green run — that is precisely the drift this milestone
  exists to stop.
- **The QARR licence blocker below now has a concrete mechanism.** Nothing is
  fetched today: all 18 MB of `tests/data/` is vendored, which is why
  `weekly.yml` has no network step. If 1003 un-vendors the round-robin
  patterns, the fetch route is the Internet Archive (`web.archive.org/web/
  2020id_/…/QARR/col/<name>.prn`), the weekly grows a network dependency it
  currently does not have, and nine acceptance suites become
  network-conditional. Excluding `tests/` from the sdist is the cheaper answer
  if the goal is only "do not redistribute in the wheel" — CI checks out the
  repo and is unaffected either way.
- **`tests/data/backend_goldens/*.npz` are pinned to `darwin/arm64` and skip
  elsewhere** (`GOLDEN_PLATFORM` in `tests/test_backend_shim.py`), measured:
  Linux x86-64 diverges by 1 ulp to 1.7e-13 relative, a libm/summation-order
  difference, on *every* state. Two consequences for a release: a user or
  contributor on Linux sees 8 skips, not 8 failures, which is the intended
  first experience — and the 7.3 MB of npz is pure CI weight in an sdist, so
  the "do the tests ship?" question is now a size question as well as a
  licence one.

From **WP-1001** (validation matrix, landed 2026-07-29) — **one deliberate
behaviour change to put in the release notes, and two smaller freeze items.**

- **`Source.dispersion` now defaults to `Dispersion()` instead of `None`.**
  This is the single breaking behaviour change between v0.6 and v1.0 and it
  changes every computed intensity: anomalous scattering was opt-in through
  v0.6, so **every number in `docs/milestones/` up to and including v0.6 was
  measured without it**. The release notes need the exact escape hatch —
  `source.dispersion = None` reproduces the pre-v1.0 model bit-identically —
  and the one new failure mode: a wavelength inside an absorption-edge
  interval now **raises** where the model previously ran uncorrected (12 of
  1176 element × shipped-anode combinations, including Eu and Ho at Cu Kα;
  0.0–1.2 % of arbitrary synchrotron wavelengths depending on specimen). That
  refusal is deliberate — a selective fallback would leave some species
  corrected and others not, which is the unequal cross-phase bias the
  correction exists to remove — but it is exactly the kind of thing a user
  upgrading from v0.6 hits without warning. Grounds and the full measured
  trade are in `tests/validation_matrix.DISPERSION_DEFAULT_ON` and
  [../VALIDATION.md](../VALIDATION.md).
- **The `DISPERSION_NEGLECTED` diagnostic's `suggestion` text changed** (it
  now addresses a caller who *declined* the block rather than one who never
  enabled it). If the freeze makes any promise about diagnostic message
  stability, note that the `code` is the contract and the prose is not — same
  rule the three `ERROR_CODES` follow.
- **`docs/VALIDATION.md` is generated, not written.** It is the natural
  document to point a PyPI long-description or a "what is validated" section
  at, but it is regenerated by `python -m tests.validation_matrix` from a
  module that lives in `tests/` — so it ships only if `docs/` does, and the
  generator is *not* package API. Decide whether the sdist carries it; do not
  move the registry into `src/` just to make it importable, because its
  content is per-test bookkeeping, not runtime behaviour.

From **WP-0604** (theory manual, landed 2026-07-29) — two facts for the
freeze:

- **`tests/test_manual.py::test_every_source_symbol_imports` is a live list
  of symbols the manual quotes** (every `*Source:*` line in
  `docs/manual/*.md`). A rename during the freeze fails that test — treat it
  as the manual's stake in the API discussion, not as an obstacle; if a
  symbol is deliberately renamed/hidden, the manual page is the other half
  of the edit.
- **An autodoc API reference was deliberately not built** (0604 design
  decision: the docstrings' unicode-math prose would mangle under reST
  rendering with `-W`). If a rendered API reference is wanted for release,
  it is a new document with its own failure modes — budget it here, don't
  bolt it onto `docs/manual/`.

From **WP-0602** (agent JSON surface, landed 2026-07-29): **`pxrdref.agent` is
deliberate public API to freeze** — `refine_json`, `request_schema`,
`response_schema`, `tool_definition`, the request/response envelope models and
`ERROR_CODES`.  Two contracts inside it are load-bearing for external
consumers: the three error codes are a **closed set** (agents branch on them),
and the success envelope sets exactly one of `result`/`series`.  The
backend/solver/plan schema descriptions are generated from the live registries
at import — the freeze should pin the *mechanism* (the meta-test in
`tests/test_agent_surface.py`), not the name lists.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — **a release blocker,
flagged deliberately for this WP.** The 16 vendored IUCr CPD QPA round-robin
patterns in `tests/data/qarr/` were freely released for re-analysis but carry
**no explicit open licence**. Confirm vendoring is acceptable before
publishing, or exclude them from the sdist/wheel and fetch on demand. Noted in
the README; unresolved.

From **WP-0401** (op shim, landed 2026-07-24) — public signatures that changed
during v0.4 and need an explicit freeze-or-hide decision:
`pawley_restraint_residual(vec)` now takes the intensity vector; new
`CompiledModel.split_pawley_intensities`; `set_pawley_intensities` is the
single post-solve commit; `evaluate` / `phase_peaks` / `derivative_bases` grew
optional intensity arguments; `cell_volume` returns a 0-d fp64 scalar
(`np.float64` subclasses `float`, so QPA and pydantic are unaffected). Plus the
whole new `backend/` surface — `Backend`, `get_backend`, `set_backend`,
`resolve_backend`, and WP-0403's `MixedPrecisionPolicy` / `precision_policy` /
`to_host_fp64` in `backend/linalg64.py`. Most of these are internals that
happen to be importable; decide which are API.

From the **indexing plan** (WP-1018…1027, added 2026-07-29) — a second block of
new freeze surface, and one API-shape decision that must survive the freeze
intact:

- **New freeze surface**: five entry points that are peers of `refine()` —
  `pick_peaks`, `index_pattern`, `determine_extinction_symbol`,
  `structure_from_candidate`, `validate_by_lebail`; the whole of
  `schemas/indexing.py` (`ObservedPeak`, `PeakFlag`, `PeakList`,
  `DataQualityReport`, `FigureOfMerit`, `AmbiguityPartner`, `CellCandidate`,
  `LeBailValidation`, `IndexingResult`, `ExtinctionCandidate`,
  `ExtinctionScreen`, plus `INDEXING_THRESHOLDS_VERSION` and its pinned
  constants); the `PEAK_*` / `INDEX_*` / `EXTINCTION_*` diagnostic codes; the
  `agent.py` `index` task; and `pxrdref index` in the CLI.
- **`IndexingResult` must keep having no unconditional singleton accessor.**
  There is deliberately no `.cell`, `.best` or `.solution`; `candidates` is
  always a list and `best_or_none()` is gated. This is the same species of
  guard as `Geometry.mu_r` being a plain `float` — the *type* is what forbids
  the mistake. A freeze is exactly the moment someone adds a convenience
  property "since everyone writes `candidates[0]` anyway"; the answer is no,
  and the reason is that the module exists to be able to say "the data cannot
  distinguish these". WP-1026 ships an API-shape test asserting this; keep it.
- **`report/schemas.py`'s `ActionKind` does not change** — indexing gives the
  already-declared `reindex_or_recheck_cell` something to call, nothing more —
  so `THRESHOLDS_VERSION` should **not** bump for it. Check this before
  bumping anything reflexively at freeze time.
- **`crystallography.lattice.inv_d_squared`** is new (WP-1018, extracted from
  `d_spacings`) — decide whether it is API or an internal that happens to be
  importable, alongside the other `crystallography/` calls.
- **This WP's `Depends on` becomes `1001, 1002, 1004-1027`**, and the freeze is
  still the milestone's last row: the point of landing indexing before it is
  that the frozen surface has been exercised.

From **WP-0309** (exporters, landed 2026-07-24): `write_refinement_cif`'s
round-trip is validated for **single-phase only** — a full multi-phase
structure re-read was never a v0.3 commitment. Whatever guarantee the frozen
API states about CIF round-tripping has to say that, or narrow the claim.

From **WP-1008** (GUI server, landed 2026-07-30): three additions to the public
surface, and one thing that is explicitly *not* frozen.

- New top-level module `pxrdref.gui` exporting `GuiSession`, `GuiError`,
  `serve`, `build_server`, `main`, `ROUTES`, `RESERVED_ROUTES`, `DEFAULT_PORT`,
  `EVENT_RING`, `RunState`. `GuiSession`'s **methods** are the surface a Tauri or
  notebook driver would use, so they are worth freezing; `gui.server` is
  transport and can be replaced wholesale.
- Two helpers were promoted from private to public because a fourth and a second
  consumer arrived: `strategy.staged.resolve_plan` (preset name + mode → plan;
  was inline in `Refinement.fit` *and* duplicated as `sequential._resolve_plan`)
  and `viz.compare.decimation_index`. Both are freeze-worthy and neither is
  re-exported from the package root — decide whether they should be.
- **The HTTP wire surface stays provisional at v1.0**, as the note above from the
  GUI plan already says. The freeze covers the schemas the routes carry (all
  existing pydantic models) and `GuiSession`'s method names, not the paths.
- New CLI subcommand `pxrdref gui`, and a new env var `PXRDREF_STATE_DIR`
  (recent-projects store, default `~/.pxrdref`) — the first user-level state this
  package has ever written outside a project directory. Worth a README line and a
  decision on whether it should be XDG-aware before it is frozen.

From **WP-1009** (text document, landed 2026-07-30): more surface to weigh, and
one signature change.

- `pxrdref.gui.textdoc` — `FORMAT_VERSION` (`pxt 1`, its own versioned contract,
  making **five** in the build rather than the four `capabilities()` reports),
  `VALUE_DIGITS`, `RESERVED_BLOCKS`, `render`, `parse`, `changes`, `apply`,
  `revision`, and the `TextError`/`Row`/`ParsedDocument`/`Delta` dataclasses.
  Decide whether `FORMAT_VERSION` joins the `capabilities()` contract arm — an
  editor pane needs it, and it is currently only reachable through
  `GET /api/textdoc`.
- **`Refinement.parameters()` gained a keyword-only `mode=`**, and
  `Project.parameters()` is new. Both are corrections rather than additions: a Le
  Bail project's rows were answered for the wrong mode. Freeze the pair together.
- `PlanSpec.preset_name()` is a new schema method (derived, never stored).

From **WP-1010** (frontend scaffold, landed 2026-07-30) — packaging facts the
freeze has to decide about, all measured:

- **The built frontend ships in the wheel** (`pxrdref/gui/static/{index.html,
  build-info.json,assets/app.js,assets/app.css}`, verified by `uv build --wheel`
  in `tests/test_gui_dist.py`). Hatchling includes it because it is a non-ignored
  file under the package — and the repo-wide `*.html` ignore rule matched
  `static/index.html` until this WP un-ignored it, which is a trap worth
  re-checking before the first real publish.
- **`gui/` itself must not ship** (it is outside `src/`, so it does not today),
  and `gui/node_modules` is gitignored. An sdist that carried the workspace would
  be harmless but confusing; decide explicitly.
- The `[gui]` extra stays **plotly-only**: plotly.js is served from the installed
  package at runtime rather than vendored into the dist, which is what keeps the
  dist at 48.7 kB and the page offline-safe.
- `.github/workflows/gui.yml` is a fourth workflow, priced at ~3 billed minutes
  per GUI-touching push (~120/month at 40 such pushes). It joins the list of
  things that go to zero when the repo goes public.

From **WP-1012** (history/report panels, landed 2026-07-30) — one new module to
freeze and **three additive-field decisions** that only exist because something
finally consumed the report mechanically:

- **`pxrdref.report.apply` is new public surface**: `RECIPES` (a
  `dict[ActionKind, Recipe]` classifying every member of the closed vocabulary as
  `stage` / `index` / `advice`), `recipe`, `stage_for`, `api_call`, `unreachable`,
  `refusal`, `describe_action`, `missing_kinds`. Re-exported from `pxrdref.report`.
  Freeze question: is the *classification* part of the contract, or an
  implementation detail of the GUI? It is the second half of `ActionKind` — a
  vocabulary member whose `how` nobody can read is not actionable — so it probably
  belongs in the frozen surface, and then moving a kind from `advice` to `stage`
  becomes a minor-version change the way adding an `ActionKind` member is.
- **`RegionAttribution.gate_failures` has no code field.** It is a list of
  formatted strings (`local_r2=0.31<0.5`,
  `outside_validity_radius(|Δ2θ|=0.030°>…)`), so a client that wants to group
  fifteen regions by *which* gate refused has to read the prefix —
  `gui/src/lib/report.ts`'s `gateName` is that parse, and it is the only message
  parsing left in the frontend. This is exactly the gap WP-1007 closed for
  `Diagnostic.where`, one layer up. An additive `gate: str` (or a
  `list[GateFailure]` with `code`/`value`/`message`) would remove it; deciding
  before the freeze is cheaper than after.
- **`Diagnostic` still has no numeric field**, which WP-1007 fenced out of scope
  and WP-1012 confirmed matters: the history panel renders each node's guard
  diagnostics and cannot sort or threshold on ρ / a block R² / a min eigenvalue,
  because the number is only in the message. `GuardFinding.value` has it and
  `GuardReport` is transient. Additive optional `value: float | None`.
- **`SuggestedAction.expected_delta_chi2` is one number per report**, stamped on
  every Layer-1-derived action by `build_report`, and not a bound on what applying
  one achieves (measured: 16.19 predicted, 16.33 observed). The docstrings now say
  so. If the freeze wants it to *mean* "what this action will buy", that is a
  Layer-2 change (per-action estimation) and a `THRESHOLDS_VERSION` bump — decide
  which of the two the field is before it is frozen.
- **Layer 2 emits actions for corrections the instrument does not have.** Measured
  on a Debye-Scherrer fit: the highest-confidence suggestion (1.000,
  `refine_sample_transparency`) names a path `params/vector.py` force-fixes off
  `bragg_brentano`. WP-1012 reports it as unreachable rather than suppressing it
  (its non-goals forbade changing what the report emits). Whether a *frozen* report
  may propose a structurally impossible action is a contract question, not a
  rendering one.

From **WP-1015** (structure viewer, landed 2026-07-30) — one new public
crystallography function and one route promoted.

- **`crystallography.symmetry.expand_orbit(sg, xyz, *, tol)`** is new and public:
  the orbit as `(position, rotation)` pairs, with `expand_positions` now a
  one-liner over it. It exists because a displacement ellipsoid *transforms*
  (U\* → R·U\*·Rᵀ) rather than merely moving, so any caller drawing or comparing a
  per-image tensor needs the operation and not only the site. Freeze it alongside
  `expand_positions` — it is the more general of the two and the other is derived
  from it.
- **`GET /api/structure3d` is live**, so `RESERVED_ROUTES` is down to the ten
  WP-1024/1027 paths. Its two query parameters (`probability`, `bond_tolerance`)
  are *drawing thresholds* and deliberately not in `ProjectDoc`; if the freeze
  covers the HTTP surface, that distinction is the thing to state, not the
  numbers.
- **The GUI now redistributes nothing new.** plotly.js is still served from the
  installed Python package rather than bundled, and the element colours are this
  repo's own values (see `ATTRIBUTION.md` → Data tables), so the publication
  checklist gains no row from this WP.

From **WP-1029** (GUI usability, landed 2026-07-30):

- **A freeze question, measured and deliberately not settled there.** Changing a
  `ProjectDoc.ui` key while a run is in flight is **refused with a 409**, because
  WP-1008 made every mutating verb refuse and `POST /api/project` is one. Two
  things are wrong with that for a `ui` key and neither was WP-1029's to decide
  unilaterally: **a `ui` key is not model state** — no compiled stage was built
  from the theme — and the refusal the client shows is the generic one, *"this
  verb would change the model a compiled stage was built from
  (frozen-per-stage discreteness)"*, which is simply untrue of a theme or a pane
  width. Measured in Chrome: the theme applies locally, the POST 409s, and the
  console prints that sentence. If the freeze covers the HTTP surface, the rule
  worth writing is **a `ui`-only patch is not a mutating verb** — which is a
  change to what a settled route refuses, hence a freeze decision rather than a
  usability repair.
- **Two more contracts are now quoted rather than copied, and both are cheap to
  freeze.** `GET /api/result` carries a `maturity` arm whose `max_rwp` is
  `report.schemas.MATURITY_MAX_RWP` verbatim, and `GET /api/result/window`
  carries `weighted` plus three residual curves — the point in both cases being
  that a client must not re-derive a number the package owns. They are the same
  shape as `capabilities()`'s registry-quoting arms, so the meta-test style
  there applies.
- **`ProjectDoc.ui` gained four keys** (`theme`, `side_width`, `model_columns`,
  on top of `simple`/`console_height`). It is an open dict on purpose; if the
  freeze wants to say anything about it, the sentence is that the *frontend*
  owns those keys and the schema deliberately does not enumerate them.

## Tasks

- [ ] Expand this stub into a full WP before starting

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
