# WP-1003 — API freeze + PyPI release

Milestone: v1.0 · Status: ⬜ not started (stub — expand before starting)
Depends on: WP-1001, WP-1002, WP-1004…WP-1017 (the GUI expansion — this WP is
the milestone's last row, so the freeze covers a surface the GUI exercised)

## Scope (carried verbatim from the pre-split roadmap)

- API freeze, PyPI release (name `pxrd-refine` verified available)

## Inherited

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

## Tasks

- [ ] Expand this stub into a full WP before starting

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
