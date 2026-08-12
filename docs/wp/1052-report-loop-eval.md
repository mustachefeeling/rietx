# WP-1052 — Closed-loop FitReport usefulness eval (mechanical)

Milestone: v1.0 · Status: ✅ 2026-08-11 — 14 tests close the §9 loop, `src/` untouched
Depends on: —

## Goal

`tests/test_report_loop.py` exists and is green: a deterministic closed loop that
starts from each of eight planted-cause states, repeatedly follows the FitReport's
top surviving suggestion through the history DAG (`predict_then_verify`: branch →
verify stage → keep on >1 % χ² improvement → checkout winner / structural rollback),
and measures planted-parameter recovery, stopping behaviour and rollback counts
against the `mccusker_default` preset run on the same starts. It is the first
executable version of AGENT_PROTOCOL §9's "canonical agent loop", and it touches no
`src/` code.

## Context

**Why.** The misfit-injection suite (`tests/test_fitreport_layers.py`) measures
whether the report *tells the truth* — plants one cause, asserts recovery, ranking,
and abstention under collinearity. Nothing measures whether *following* the report
converges anything: `predict_then_verify` (`report/layer2.py:365`) has zero callers
outside two tests, the only code acting on a report statement is the GUI's
`report_apply` button, and no test runs report → act → refit → report over rounds.
The WP-1003 freeze covers an exercised surface; this WP makes §9's loop exercised.
The agent-in-the-loop half — real models driving `refine_json` — is WP-1053's, which
reuses this WP's episodes and metrics.

**Driver.** An underscore-private `_run_report_loop()` + `EpisodeResult` dataclass in
the test module — a measurement instrument, not product. WP-1050's fence holds
verbatim: *"No automatic stage insertion: the staged runner stays preset; suggest()
informs a caller (human, GUI, or the agent loop), it does not drive."* Nothing
importable from `anatase` may become an autopilot. Reuse `_truth()` from
`tests/test_fitreport_layers.py` (cross-module test imports are house pattern —
`test_report_apply.py` imports from three sibling modules); import
`Stage`/`RefinementPlan` from `anatase.strategy.staged` as `layer2.py` does.

**Loop mechanics, verified against the code (2026-08-04):**

- `predict_then_verify(ref, data, action)` requires `ref.result_`, branches when
  history exists, runs `Stage(f"verify:{action.kind}", action.parameter_paths)`,
  accepts iff `observed > 0.01 * abs(before)`; a failed solve is a rejection, never a
  crash (`report/layer2.py:376-402`). The rejected trial leaves a dead leaf in the
  DAG and the parent's working state untouched.
- After an *accepted* outcome, `history.head` **is** the verify node —
  `RefinementTree.add` advances the shared tree's HEAD (`history/tree.py:124`) while
  the parent's private `_head_id` stays put. `VerificationOutcome` carries no node id,
  so the driver checks out `history.head` and sanity-asserts
  `ref.history[node].action.name == f"verify:{kind}"`.
- `checkout` nulls `_model`/`result_` and restores `_free_paths` from the node
  (`refine.py:219-223`), so after checkout the driver runs one **empty-`turn_on`
  refit stage** (`Stage(f"refit:{kind}", [])`) to re-establish them — legal because
  `set_vary([], True)` frees nothing (`refine.py:555`) and
  `_prepare_table(restore=True)` (`refine.py:765`) restores the node's free set,
  which is non-empty after a verify node.
- **Selection**: first suggested action (report order = confidence desc) that is
  (i) active — `Refinement.report()` passes `self._free_paths` (`refine.py:849`), so
  every previously-accepted action is auto-vetoed "already free", the built-in
  anti-thrash; (ii) `report.apply.recipe(kind).how == "stage"` — filters the 1 index
  + 4 advice kinds, which is what makes the stopping episodes meaningful;
  (iii) `confidence > 0.3` — the floor equals the collinearity cap by construction
  (`confidence = min(confidence, 0.3)` on non-separable trends, `layer2.py:138`), so
  a strict `>` is exactly "never act on an attribution the report itself flagged
  non-separable"; (iv) not previously rejected this episode (loop-local set; correct
  for single-cause episodes only — a multi-cause variant would need different memory
  and is fenced out).
- **Stopping**: no action survives selection (record the top *blocked* advice/index
  kind), two consecutive rejections, or a round cap of 4 (a runaway guard per
  `tests/CLAUDE.md`, never a timer).
- **Bootstrap**: `predict_then_verify` needs a prior fit and a zero-free-parameter
  solve won't run, so each episode opens with a background-only stage. Background can
  partially absorb planted misfit (the background-absorption invariant), so the loop's
  starting report is *not* the layers suite's `_report_for` state — therefore each
  episode asserts, pre-loop, the episode-appropriate report statement (below) to
  *establish* the calibration transfer rather than assume it.

**Baseline**: the same perturbed start run through `fit(plan="mccusker_default")`
(`strategy/staged.py:79-88`: scale+bkg, zero, cell, profile_w, profile). Chosen
because it structurally cannot free `instrument.geometry.sample_displacement` (only
the `lab_*` plans do), giving one episode where the preset cannot reach the cause the
report names. Honest framing: on synthetic single-cause starts every other parameter
is already at truth, so "the loop freed fewer parameters" means **the report
localised the cause**, never "report-driven refinement is cheaper".

**Episodes** — injections identical to the layers suite (fixed seeds; family
definitions as in its calibration test). "Recovery" = the planted *parameter* lands
at truth, never Rwp alone. Pre-loop bootstrap asserts per episode: E1–E4 planted
family top-ranked; E5 `add_impurity_phase` *present*; E6 no gated position action
(the +0.4 % cell must trip the validity radius); E7 `abstained_reason` set; E8 every
position action capped ≤ 0.3.

| # | Start (injection) | Loop asserts | Baseline asserts |
|---|---|---|---|
| E1 | zero_shift = 0.008° | accepted == [`refine_zero_shift`] (one accepted round); zero → 0 ± 0.002; wrong-kept = 0; χ²(final) ≤ 1.01 × min over all leaves | recovers too; localisation framing only |
| E2 | sample_displacement = −0.02 mm | `refine_sample_displacement` accepted; disp → 0 ± 0.005 mm | **structural miss**: baseline disp stays −0.02 exactly |
| E3 | profile.w halved | width-family action accepted (Voigt compensation); χ² improves vs bootstrap (measure, then pin); **documents the emitter gap** — `_WIDTH_ACTIONS` (`layer2.py:54-57`) maps width trends only onto `lor_size`/`lor_strain`, no `refine_profile_widths` emitter exists, so the planted w is never freed | **baseline wins recovery** (w → 4e-3 ± 20 %) — the honest counter-finding, stated in the test docstring |
| E4 | scale ×0.90 | `refine_scale` accepted; scale → truth ± 2 %; wrong-kept = 0 | recovers too |
| E5 | Gaussian impurity spike | stops; accepted = 0; top blocked kind = `add_impurity_phase`; final report still lists the unmatched peak | — |
| E6 | cell +0.4 % | no position kind ever applied; `reindex_or_recheck_cell` present-but-skipped (`how == "index"`); rejected trials allowed | recorded, not asserted (the blunt cell stage may fix it — that contrast is the point) |
| E7 | hopeless (cell 4.60 Å, scale ÷10) | abstained; zero stages applied after bootstrap | — |
| E8 | collinear zero+displacement window | no position kind applied; stop reason recorded | — |

**Cross-cutting**: rollback count = rejected `verify:` leaves, each with parent χ²
bit-unchanged **and** a `history.compare` row showing the dead leaf improved < 1 %
over its parent (the DAG as audit trail, not scenery); predicted/observed band
(re-measure, then pin ~0.3–3×) asserted on the **first** accepted action only —
`expected_delta_chi2` is one number per report — and skipped when `None`; obs/calc/
diff PNGs to `tests/output/` per house convention.

**Placement**: fast suite (synthetic ×60-count LaB6), **no `xdist_group`** —
`_truth()` is synthesis-only and cheap, so grouping the ~8 episodes would create a
serial group rivalling the whole current fast-suite wall; let xdist spread them.
Re-read `--durations` after implementation and quote wall as a range with the venv;
if the module dominates, slow-mark the baseline arms first (narrow the scope, never
the budget).

**Known risks**: the 1 % keep-threshold doubles as the convergence detector — if a
true first-round cause is ever rejected, that is a report calibration bug and must be
recorded, not tuned away. Oscillation is prevented four ways (free-path auto-veto,
rejected-kinds memory, two-rejection stop, round cap). E5/E6/E8 may surface
incidental sub-cause actions above the floor; assertions are scoped to what matters
(no *position* kind applied), and rejections are budgeted, not forbidden.

**From WP-1050 (closed 2026-08-08), verified still true on arrival:**
`tests/test_suggest.py` already exercises single-cause states built from the
layers suite's `_truth()` (zero shift, W error, X error, absorbed-candidate,
converged control) — reuse those alongside this WP's episodes. Two measured
facts belong in any scoring rule: a planted single cause does **not**
generally yield a resolved singleton — the truth fixture's zero shift
honestly returns the unresolved {zero_shift, sample_displacement} pair, and
the exact-identity width pairs ({profile.x, lor_size}, {profile.u,
gauss_strain}, {profile.y, lor_strain}) tie by construction — so "the top
group *contains* the planted cause" is success, not a miss. And the E3
`refine_profile_widths` emitter gap has its measured counterpart: `suggest()`
*does* rank U/V/W (a W error returns `instrument.profile.w` resolved), so the
two methods' disagreement on instrument widths is real and expected, not a
bug in either.

## Non-goals

- No autopilot API anywhere in `src/` (the WP-1050 fence, restated above).
- No tuning of `min_improvement`, confidence formulas or thresholds to make an
  episode pass — a failing episode is a finding, recorded in the handover log.
- No fix for the `refine_profile_widths` emitter gap (document only; a fix is its
  own decision).
- No rival-panel variant (top-2 branches compared) and no multi-cause episodes —
  both named future work, not this WP.
- No GUI work. The agent-in-the-loop eval is WP-1053's.

## Tasks

- [x] `tests/test_report_loop.py`: `_run_report_loop()` + `EpisodeResult`, `_truth()`
      import, truth-model-Rwp helper, E1 green end-to-end — per-episode bootstrap
      assert, DAG assertions (verify-node name check, parent untouched, χ²(final) ≤
      1.01 × best leaf, compare rows), empty-`turn_on` refit verified, PNGs to
      `tests/output/`.
- [x] E2 + the `mccusker_default` baseline arm + structural-miss assertion.
- [x] E3 + E4 with baseline; measure then pin the predicted/observed band and the E3
      improvement factor; the two honest counter-findings in docstrings.
- [x] Stopping episodes E5–E8 with the no-position-action assertions.
- [ ] Optional, flagged in the handover if taken: `VerificationOutcome.node_id` as
      one additive schema field + its test, only if `history.head` navigation proves
      fragile in practice. Otherwise the `src/` diff stays empty. — **Not taken**:
      HEAD navigation with the name/parent sanity asserts never misfired across all
      14 tests; the `src/` diff is empty.
- [x] Stretch (`slow` mark, `xdist_group("srm660c")`): one SRM 660c degraded-start
      episode beside the existing session fixture. — Taken as a **pair** (refusal +
      recovery); grounds in the handover entry.
- [x] Docs: one sentence in AGENT_PROTOCOL §9 pointing at this test as the
      executable version of the canonical loop; re-read `--durations`; handover
      quotes which numbers moved (passed+skipped by exactly N, both selections).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_report_loop.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

E1/E2/E4 recover the planted parameter within tolerance with zero wrong-kept
actions; E5–E8 stop without applying a position action; every rejection leaves the
parent χ² bit-unchanged and a dead leaf whose compare row shows < 1 % improvement;
`src/` diff empty (or exactly the one flagged additive field + test).

## References

- `docs/AGENT_PROTOCOL.md` §9 (the canonical loop this executes), §5–6.
- `docs/DESIGN.md` — FitReport validation policy ("without this the confidence
  numbers are decorative").
- `tests/test_report_apply.py` (the existing one-action loop closure, over HTTP).
- `docs/wp/1050-suggest-next-parameter.md` (the no-autopilot fence; `suggest()` as
  the planned cross-check of Layer 2).

## Handover log

- **2026-08-11** — **closed.** All tasks landed on `wp1052-report-loop-eval`
  (eight commits), acceptance green, `src/` diff **empty** — the optional
  `VerificationOutcome.node_id` was not needed: HEAD navigation plus the
  name/parent sanity asserts never misfired across 14 tests. On arrival the
  `### Inherited` from WP-1050 was verified live (both facts) and folded into
  Context.

  **Counts** (main checkout `.venv`, `[dev,jax,torch]`, darwin/arm64):
  module **14 passed** in ~8 s serial (12 fast + the two slow SRM 660c rows).
  Fast suite `-m "not slow"`: **2256 passed, 5 skipped** in ~2:56 (one run)
  against 1051's 2244 + 5 — **+12, all passes, no new skips**; the full
  selection gains **+14** (the slow pair joins the `srm660c` xdist group).
  The module appears nowhere in the fast suite's `--durations` top 25, so no
  baseline arm was slow-marked and the no-`xdist_group` placement stands.

  **Loop character, measured**: E1/E2/E4 recover the planted parameter to the
  truth-model noise floor in one accepted round each and stop clean;
  predicted/observed Δχ² on first accepted actions measured 0.79 / 0.85 /
  1.16 / 0.79 (E1–E4), 1.42 (E8), 1.03 (SRM scale) — band pinned 0.3–3×.
  The keep-threshold **never rejected a true first-round cause** — the
  calibration bug the WP said to record did not occur.

  **Findings** (each pinned in a docstring or assertion in the module):
  1. **E6, the sharpest**: after the bootstrap the wrong-cell state *abstains*
     (Rwp 0.716 — abstention outranks the validity gate), and the abstained
     branch never emits `reindex_or_recheck_cell` (it is mature-branch-only:
     `far and rwp > 0.2` in `layer2.suggest_actions`) — instead the state
     hands out `add_impurity_phase` at confidence **0.9**. The absence is
     pinned; a fix should flip the pin and cite this finding.
  2. **E8**: every position action capped at exactly 0.3 and refused by the
     strict floor — but `refine_axial_asymmetry` (hard-coded 0.5, a different
     observable, invisible to the collinearity cap) is **accepted** at χ²_red
     170.8 → 51.3. An incidental proxy the 1 % keep-threshold legitimately
     keeps; no *position* kind is ever applied, which is the line held.
  3. **E3, the emitter gap with numbers**: the `lor_size` proxy takes χ²_red
     15.1 → 4.3 and provably cannot reach the ≈1.01 truth floor (Lorentzian
     FWHM vs Gaussian variance); the baseline recovers `w` to −0.7 %. Fix is
     its own decision, per Non-goals.
  4. **Real data**: SRM 660c + 0.01° zero → the whole position family comes
     back capped ≤ 0.3 (genuinely non-separable from the protocol's fitted
     −0.08 mm displacement, unlike the synthetic 18–125° fixture) — the loop
     refuses and χ²_red stays at the degraded 16.1: **safe, not complete**.
     Scale ×0.90 → closed loop: accepted at 0.85, recovered to **7.7 ppm** of
     the converged value. On real data `add_impurity_phase` (0.4) outranks
     the capped family — the shift's derivative residuals read as unindexed
     lines; on synthetic it never does.
  5. **E2's baseline**, the Rwp-blindness exhibit: the preset compensates the
     displacement it cannot free with zero ≈ −0.011° at χ²_red 1.012 —
     indistinguishable from the loop's honest fit by any fit statistic,
     distinguishable by the parameter values.

  **Next**: nothing here. WP-1053 is unblocked; its `### Inherited` now
  carries the findings that change its scoring (written at this close).
  Gotcha for a successor touching the module: the episode numbers are
  seeded-rng deterministic, but every pin was chosen with headroom after
  probing — re-measure before tightening any of them.

- **2026-08-05** — created; not started. The design survived two adversarial
  review rounds and every load-bearing mechanic in Context carries the file:line
  it was verified at — trust those over re-derivation, but re-verify if the named
  lines have moved. Next: the first task (driver + E1). Gotchas for the
  implementer: the 1 % keep-threshold is also the loop's convergence detector, so
  a true first-round cause being rejected is a report calibration bug to record,
  never a threshold to tune; the module deliberately has **no** `xdist_group`
  (grouping the episodes would create the suite's longest group — the shared
  `_truth()` is cheap synthesis, not a fitted fixture).
