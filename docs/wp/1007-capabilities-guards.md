# WP-1007 — Capabilities, structured guards, background export

Milestone: v1.0 · Status: ✅ 2026-07-30
Depends on: WP-1004

## Goal

A client can ask the package what it can do (`capabilities()`), read guard
findings as typed data instead of regexing prose, and reach the background
estimator from the top level — the three "the GUI must not guess" gaps.

## Context

- `src/anatase/capabilities.py`: `capabilities()` → version, backends
  (with available/experimental flags), solvers, plans (from `PLAN_PRESETS` +
  WP-1004's `PLAN_INFO`), modes, anodes, reader formats, feature flags —
  **quoted from the live registries** (`backend.api.BACKEND_NAMES`,
  `optimize.least_squares.SOLVERS`, `strategy.staged.PLAN_PRESETS`, the
  anode table), with a WP-0602-style meta-test asserting every registry
  member appears. The lesson is measured: the fourth backend name arrived
  two days after the third.
- **`GuardReport` is prose a GUI would have to regex.** It is a dataclass at
  `strategy/staged.py:246-261` with exactly six `list[str]` fields:
  `high_correlations`, `at_bounds`, `background_correlations`,
  `nonpositive_adps`, `nonpositive_strain`, `roughness_correlations` — each
  entry formatted text like `"phases.0.cell.a ~ instrument.zero_shift
  (ρ=+0.994)"`. Convert to `list[GuardFinding]` (code, paths, value,
  message), with `__str__` preserving today's formatted text so
  `_guard_diagnostics` (`refine.py:672`, called at `refine.py:479`, `:544`,
  `multi.py:246`, `:357`) and every other consumer keeps working
  byte-for-byte. A clickable correlation panel then reads `.paths` and
  `.value`, never a regex.
- **`auto_background` and `diagnose` are unexported at the top level.**
  `background/auto.py:28` and `background/diagnostics.py:129` exist and are
  in `background.__init__.__all__` — but `anatase/__init__.py` never imports
  `background` at all. The GUI's "estimate background" button (and any
  scripting user) wants `anatase.auto_background`. Remember the invariant:
  the estimate is held additively or co-refined under a penalty — never
  subtracted.

### Inherited

From **WP-1004**: `PLAN_INFO` is the source for the plans arm of
`capabilities()` — do not restate titles here. As landed (2026-07-30) it is
`dict[str, PlanInfo]` in `strategy/staged.py`, a frozen dataclass of
`title / description / modes / when_to_use`, exported as `anatase.PLAN_INFO`
alongside `PLAN_PRESETS`; its membership meta-test lives in
`tests/test_params_surface.py`, so `capabilities()`'s own registry test should
assert the *arm* is complete rather than re-assert the bijection. Note `modes`
is a **tuple** (plural): `profile_only` is legitimately both the Le Bail plan
and a no-structure Rietveld plan, so a modes-arm keyed one-plan-one-mode would
be wrong. Also already exported by 1004 and worth a `capabilities()` feature
flag rather than a re-derivation: `refine.mode_fixed_path(path, mode)`, the
single definition of which paths lebail/pawley force-fix.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): `capabilities()`
gains an **indexing engines** arm, and it must be quoted from the **live
registry** in `indexing/`, never from a hardcoded list. Same rule and same
reason as the backend/solver/plan arms: `agent.tool_definition()` already has a
meta-test that fails when a registered member is missing from the exported
schema, and WP-1024 extends it to engines. A hardcoded list would pass that
test while lying.

From **WP-1028** (2026-07-29): that WP adds guards this one will have to carry
codes for — `MODEL_FAR_FROM_DATA` (a stage returning `status="converged"` at
Rwp = 7 225 %), a `max_iter` stage outcome surfaced as a finding, an hkl-range
refusal, and a non-positive-ΣS·ZMV QPA finding that currently *raises* from
inside `_build_result`. This WP's "no new guards" fence still holds — but design
`GuardFinding`'s code field as an open vocabulary rather than a `Literal` closed
over today's six list names, or 1028 will have to reopen it.

Also from **WP-1028**: `PreferredOrientation` is missing from
`anatase/__init__.py` — the same top-level export gap this WP records for
`auto_background` and `diagnose`. It is user-constructed (you cannot enable
texture without it) and every comparable schema is re-exported, so fold it into
the same commit.

## Non-goals

- No HTTP (`/api/capabilities` is WP-1008's one-line wrapper over this).
- No new guards and no threshold changes — this WP restructures reporting,
  it does not touch what fires.
- No change to `Diagnostic` — `GuardFinding` is the pre-diagnostic layer
  that `_guard_diagnostics` consumes, not a second diagnostic vocabulary.

## Tasks

- [x] `src/anatase/capabilities.py` + registry meta-test
      (`tests/test_capabilities.py`).
- [x] `GuardFinding` (code, paths, value, message); `GuardReport`'s six
      fields → `list[GuardFinding]` with `__str__` preserving today's text —
      test pins the rendered strings against the current output on a
      known-degenerate synthetic fit, so consumers provably see no change.
      (Pinned as *literals captured from the pre-change output* — see the
      handover; re-deriving them from the constructors would test nothing.)
- [x] Export `auto_background` and `diagnose` from `anatase.__init__`
      (+ `__all__`), with a smoke test importing them from the top level.
      `PreferredOrientation` (the WP-1028 note), `capabilities` and
      `GuardFinding` went with them.
- [x] Reader-formats arm of `capabilities()` states what `read_pattern`
      actually sniffs (xy/xye, GSAS `BANK` incl. FXYE/STD, pdCIF) — sourced
      from `io/readers.py`, not restated by hand. The registry it quotes
      (`PATTERN_FORMATS`) landed in WP-1005, which needed the same facts.
- [x] Extra: the **four** versioned contracts in one place — schema, report
      thresholds, **event schema** (an SSE consumer needs it) and project
      format.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_capabilities.py tests/test_refine_synthetic.py -q
.venv/bin/python -m ruff check src tests examples
```

Measured 2026-07-30: `tests/test_capabilities.py` 19 passed, fast suite 1067
passed / 107 skipped in 15-33 s (the skips are the jax/torch rows — this
worktree's venv is `[dev]` only), ruff clean. The guard change was verified by
capturing `GuardReport` + `_guard_diagnostics` output on the collinear
zero-shift/sample-displacement fit **before and after**: every rendered string
and every diagnostic message byte-identical, the single difference being
`HIGH_CORRELATION`'s `where` going from `[]` to its two paths.

## References

- WP-0602 registry meta-test pattern (`tests/test_agent_surface.py`).
- CLAUDE.md background invariant (flexibility is a correctness question).

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan. GuardReport field names
  and the missing top-level background exports verified against the tree the
  same day.
- **2026-07-30** — **complete.** All four tasks plus one addition; 19 tests.

  *Done / decided:*

  - **`capabilities()` returns a pydantic `Capabilities`, not a dict**, so
    WP-1008 can serve it verbatim and a client gets a schema. Arms: backends
    (name / available / experimental / requires / dtype), solvers, plans (the
    four `PLAN_INFO` facts), modes, anodes, reader formats, features, and the
    four contract versions.
  - **`available` is the arm the registry cannot supply**, and it is the point of
    the backends arm: `BACKEND_NAMES` says jax *exists*, `find_spec` says whether
    it imports **here**. A backend menu needs the second.
  - The plans arm iterates **`PLAN_INFO`**, not `PLAN_PRESETS` — following this
    WP's inherited note from 1004: the bijection is already tested elsewhere, so
    quoting the side that carries the chooser's four facts keeps the arm complete
    without a second assertion about the same pair.
  - `features` are **derived predicates**, not literal booleans: schema-field
    presence for the corrections, top-level-export presence for the entry points.
    The rule earns its keep immediately — `features["indexing"]` is False today
    and flips on its own when `anatase.index` lands, so nobody has to remember.
  - **Four versioned contracts, not three.** `event_schema_version` was not in
    the charter and belongs: an SSE consumer is exactly the client that must know
    whether a new event *kind* has appeared (a field is additive, a kind is a
    bump — WP-1006's rule).
  - `GuardFinding` is a **frozen** dataclass (hashable, so findings dedupe) with
    an **open** `code` vocabulary, per the WP-1028 note. It is the same vocabulary
    as `Diagnostic.code` rather than a second one, which turned six hand-written
    loops into a mapping the finding carries itself.

  *The finding, and it is the reason this WP existed:* the prose really was being
  regexed — by *us*. `_guard_diagnostics` recovered a parameter path with
  `msg.split(" ")[0]`, which happens to work for the five single-path findings and
  yields **nothing usable for a correlation**, whose rendered form is
  `"a ~ b (ρ=+0.994)"`. So `Diagnostic.where` was **empty on exactly the finding a
  client most wants to make clickable**, and a GUI would have had to parse the
  message to learn which two parameters were degenerate. Measured before/after on
  the collinear zero-shift/sample-displacement fit: every message byte-identical,
  `where` `[]` → `["instrument.zero_shift",
  "instrument.geometry.sample_displacement"]`. AGENT_PROTOCOL §7 now says to read
  `where` and never split the message.

  *Gotchas for whoever touches this next:*

  - **The rendered-string pin is a table of literals**, captured from the
    pre-change output by running the degenerate fit. If you regenerate them from
    the constructors the test becomes a tautology — the whole point is that
    `str(finding)` is a *published* surface, since the diagnostics' messages are
    built from it.
  - Every format string that used to live at three call sites (`staged.py` twice,
    `multi.py` once) is now one constructor. `multi.py`'s `hist.{h}.{path}`
    prefix is kept deliberately: it is this surface's own addressing, the same one
    `RefinedParameter.path` uses per histogram, so a finding's paths stay
    resolvable against the result a client is holding.
  - The anode/Kβ tables (`_RADIATIONS`, `_KA_DOUBLETS`, `_KBETA`) are imported
    under their private names rather than being re-exported. Deliberate: the
    meta-test fails loudly if a name moves, and this late in the milestone a new
    public alias is new surface for WP-1003 to freeze for no gain.
  - **Solvers are a bare `list[str]`.** There are two and the answer is almost
    always `"trf"`, so there is no `SOLVER_INFO` to quote. If the GUI wants a
    per-solver description, add it *beside `SOLVERS`* and have `agent.py`'s
    `_SOLVER_DESC` quote it too — do not write a second copy in the frontend.
  - No new guards and no threshold changes, as fenced. `GuardReport.findings()`
    exists for a consumer that wants them all in emission order.

  *Not done, deliberately:* the **indexing engines arm**. There is no engine
  registry yet (`indexing/` holds peak picking only), and guessing its name would
  produce an arm that passes its own meta-test while lying — precisely what this
  WP's inherited note warns against. Told WP-1024 what to add.
