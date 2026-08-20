# WP-1101 — fit_peaks: standalone peak fitting at named positions

Milestone: v1.2 · Status: ⬜
Depends on: — (first of the free-standing peaks set; opens the 11xx block)

## Goal

A caller can profile-fit peaks in a pattern — including exactly the positions
they name, with no structure, no space group and no refinement — through one
documented top-level call, `fit_peaks(data, instrument, positions) →
PeakList`, and through `agent.refine_json` (`task="fit_peaks"`). Peak-width
analysis (Williamson-Hall), quick d-spacings and general lab use become
first-class, served by machinery that already exists.

## Context

- **Almost everything exists; this WP is exposure, not construction.**
  `pick_peaks` is exported and documented; the per-group fitter
  (`indexing/peakfit.py`) fits the Kα doublet as a Bragg-law-constrained pair
  with the Kα2/Kα1 ratio held at weight × the two lines' Lp ratio (holding the
  bare weight biased the fitted Kα1 by −2e-4° and −0.26 mean σ pull —
  measured, that module's docstring), shares Γ_G/Γ_L per group, applies FCJ
  at the declared apertures, and inflates esds by √max(χ²_red, 1).
  `fit_group_at` (`indexing/peakfit.py`, "One solve with **exactly** these
  components — the editing entry point") is the engine; it is unexported.
- **API shape: one convenience function, not a power-surface export.**
  `fit_peaks(data, instrument, positions, *, two_theta_range=None) →
  PeakList`, defined in `rietx.indexing`, re-exported at top level. Defining
  it there puts it at provisional tier automatically ([1078](1078-indexing-provisional.md):
  the tier derives from the *defining* module and is reached through the
  re-export). Exporting `fit_group_at`/`GroupFit`/`Detection`/`PeakGroup`
  instead would drag four more names onto a surface where provisional names
  must still all be documented ("a weaker *promise*, never thinner
  *coverage*" — `tests/api_surface.py`); `PeakList` is already the
  serializable, documented projection, and `ObservedPeak` already carries
  `fwhm`/`eta`/`q`/`q_esd` — everything W-H and d-spacing use needs.
- **Semantics: exactly the named components.** Run `detect_peaks` for the
  envelope and windows; a position inside a detected group reuses that frozen
  window; positions sharing a window are fitted together as one group; the
  fitted component set per window is exactly the caller's positions
  (`fit_group_at`'s contract — the caller has already said where the
  components are). Result peaks carry `origin="manual"`.
- **The silent trap, and its flag.** When detection saw components in a
  window the caller did not name, fitting the caller's model alone biases the
  named position and the only numeric trace is χ²_red. Affected peaks carry a
  new `PeakFlag` member (`"unnamed_neighbour"`; the Literal lives in
  provisional `schemas/indexing.py`, so the addition is cheap) and the esd
  inflation carries the numeric honesty. Evidence, not refusal.
- **The load-bearing lift.** Fresh-window sizing for a position where
  detection found nothing lives in `gui/peaks.py` (`PeakEditor._new_group`):
  predicted FWHM × width_scale × `PEAK_WINDOW_FWHM_MULT` + FCJ extent, with
  refusals naming an out-of-range position and a gap (`_MIN_GROUP_POINTS`).
  Move it down into `indexing/` and have gui import it back — gui is never
  imported by indexing. Pin: `tests/test_gui_peaks.py` stays green, plus a
  direct window-equality test.
- **Agent surface — the set's one contract-version event.** `task="fit_peaks"`
  with `positions: list[float] | None`: positions given → `fit_peaks`; absent
  → `pick_peaks` (one tag, one answer shape). Request modeled on
  `IndexRequest` (`agent.py` — extends `Base` directly: no backend, solver or
  plan). New `AgentSuccess.peaks: PeakList | None` arm — a different *shape*,
  so its own arm ([1043](1043-agent-and-human-indexing.md)'s rule). A new
  task tag and answer arm are closed-vocabulary additions to the agent
  envelope, so `SCHEMA_VERSION` moves as a minor event. Release ordering is
  the maintainer's: if 1.0.2 ships first (recommended — nothing gates it),
  this takes its own 0.2 → 0.3 inside 1.1.0.dev; if 1.0.2 is held, it rides
  that bump. `tool_definition()`'s registry meta-tests must stay green.
- `pick_peaks` gets re-documented as a general-purpose tool: a short
  subsection in `../manual/using/indexing.md` with an executed example —
  d-spacings from `q`, widths from `fwhm`, a Williamson-Hall computation done
  *in the example*, not shipped as a helper.
- capabilities: `"peak_fitting": "fit_peaks"` joins `_SURFACE_FLAGS`
  (`capabilities.py`) beside `"peak_picking"`; the hand-written expected-key
  set in `tests/test_capabilities.py` grows by one.

### Inherited

**From WP-1109 (2026-08-20), measured on this worktree's `[dev]` venv,
darwin/arm64 — the cost model for window sizing is not the intuitive one.**

The profile kernel is **dispatch-bound, not point-bound**:
`model/profiles/pseudovoigt.py:64` `pseudo_voigt_derivs` costs **11.8 µs at a
25-point window and 13.6 µs at 194 points** — about 11 µs of fixed python/ufunc
dispatch and ~0.01 µs per point. So a fitter's cost tracks the *number* of
windows it evaluates, essentially not their width. Two consequences for the
fresh-window sizing task here: widening a window to be safe is close to free,
and shaving points off one to be fast buys almost nothing (measured ~13 % on the
refinement path). Optimise the count, not the width.

For calibration on what the refinement path currently does — this is context,
not a rule to copy: `model/forward.py:110-111` sets `WINDOW_FWHM_MULT = 30.0`
and `WINDOW_MIN_DEG = 0.3`, which on the `qarr/cpd-2` protocol gives a median
window of 185 points against a median FWHM of 3 points (**~69× FWHM**), and
summed window points of **8.1 × n_points** per residual. That margin is sized
for a pure Lorentzian and applied unconditionally: truncation at 8 FWHM is
2.0e-3 of peak height at η = 0.6, and at 4 FWHM 7.8e-3 — though the 1109
review re-judged truncation by *area* (a ±8 FWHM cut at η = 0.6 loses ≈2.4 %
of intensity), and the η-aware sizing task moved to WP-1112 with that
corrected criterion. If `PEAK_WINDOW_FWHM_MULT` here ends up deriving from
`WINDOW_FWHM_MULT`, expect that constant to move under 1112.

## Non-goals

- Exporting `fit_group_at`, `GroupFit`, `Detection`, `PeakGroup`,
  `pick_peaks_with_state` — case-by-case later; `PeakList` stays the one
  public projection.
- Promoting `PeakEditor` out of `gui/`; `peaks.json` outside projects.
- A shipped Williamson-Hall / size-strain analyzer — the manual example shows
  the computation from a `PeakList`; the package fits the peaks.
- Peaks inside the refinement residual ([1103](1103-peak-components.md)) or
  the background ([1102](1102-component-seam-humps.md)).

## Tasks

- [ ] Lift fresh-window sizing from `gui/peaks.py` (`_new_group`) into
      `indexing/` (shared helper; gui imports it back); behavior pinned —
      `tests/test_gui_peaks.py` unchanged-green plus a window-equality test.
- [ ] `fit_peaks()` in `rietx.indexing` + the `"unnamed_neighbour"` flag;
      unit tests: a position where detection found nothing, two positions in
      one window, a position in a data gap (refusal names the gap), a named
      position beside an unnamed detected neighbour (flag fires).
- [ ] Top-level re-export + `"peak_fitting"` in `_SURFACE_FLAGS` + the
      capabilities expected-key set.
- [ ] Manual: `using/indexing.md` — `fit_peaks` section + `pick_peaks`
      general-use subsection with executed d-spacing/W-H example; api-surface
      partition satisfied (documents `fit_peaks` at provisional tier).
- [ ] Agent: `task="fit_peaks"` request + `peaks` answer arm;
      `SCHEMA_VERSION` event per its rule; `tool_definition` + envelope
      tests + `using/agents.md` row.
- [ ] Tests wrap-up (fast-suite delta stated in the handover) + ruff +
      sphinx `-W` + obs/calc/diff-style PNGs of fitted groups to
      `tests/output/`.

## Acceptance

`capabilities()["features"]["peak_fitting"]` is derived-True, and the manual's
W-H numbers come from an executed block.

```sh
.venv/bin/python -m pytest tests/test_peak_picking.py tests/test_gui_peaks.py tests/test_agent_surface.py tests/test_capabilities.py tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

## References

- Rachinger (1948), J. Sci. Instrum. 25, 254 — why the doublet is fitted as a
  constrained pair, never stripped (restated from `indexing/peakfit.py`).
- Williamson & Hall (1953), Acta Metall. 1, 22 — the motivating analysis;
  manual example only.
- [1027](1027-gui-peak-picker.md) (the peak editor whose window sizing this
  lifts), [1078](1078-indexing-provisional.md) (the provisional tier).

## Handover log

- **2026-08-18** — created from the single-peak planning session; numbering
  opens the 11xx block (v1.1). Designed alongside
  [1102](1102-component-seam-humps.md)/[1103](1103-peak-components.md); this
  one is independently landable and carries the set's one contract-version
  event (the agent task tag + answer arm).
