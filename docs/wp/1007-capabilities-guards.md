# WP-1007 — Capabilities, structured guards, background export

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1004

## Goal

A client can ask the package what it can do (`capabilities()`), read guard
findings as typed data instead of regexing prose, and reach the background
estimator from the top level — the three "the GUI must not guess" gaps.

## Context

- `src/pxrdref/capabilities.py`: `capabilities()` → version, backends
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
  in `background.__init__.__all__` — but `pxrdref/__init__.py` never imports
  `background` at all. The GUI's "estimate background" button (and any
  scripting user) wants `pxrdref.auto_background`. Remember the invariant:
  the estimate is held additively or co-refined under a penalty — never
  subtracted.

### Inherited

From **WP-1004**: `PLAN_INFO` is the source for the plans arm of
`capabilities()` — do not restate titles here.

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
`pxrdref/__init__.py` — the same top-level export gap this WP records for
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

- [ ] `src/pxrdref/capabilities.py` + registry meta-test
      (`tests/test_capabilities.py`).
- [ ] `GuardFinding` (code, paths, value, message); `GuardReport`'s six
      fields → `list[GuardFinding]` with `__str__` preserving today's text —
      test pins the rendered strings against the current output on a
      known-degenerate synthetic fit, so consumers provably see no change.
- [ ] Export `auto_background` and `diagnose` from `pxrdref.__init__`
      (+ `__all__`), with a smoke test importing them from the top level.
- [ ] Reader-formats arm of `capabilities()` states what `read_pattern`
      actually sniffs (xy/xye, GSAS `BANK` incl. FXYE/STD, pdCIF) — sourced
      from `io/readers.py`, not restated by hand.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_capabilities.py tests/test_refine_synthetic.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-0602 registry meta-test pattern (`tests/test_agent_surface.py`).
- CLAUDE.md background invariant (flexibility is a correctness question).

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan. GuardReport field names
  and the missing top-level background exports verified against the tree the
  same day.
