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
