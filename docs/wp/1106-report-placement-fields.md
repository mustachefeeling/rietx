# WP-1106 — Report placement fields: structured where prose was load-bearing

Milestone: v1.1 · Status: ✅ 2026-08-19 — all four fields/writers landed by
measurement; thresholds 1.2
Depends on: —

## Goal

Three things an agent today must infer from prose or cannot see at all become
typed fields with named writers: a suggested action says how it is carried out
(stage / index / advice), the result reports McCusker §7's convergence
quantity (max shift/esd), and the two `ActionKind` members that no code emits
are resolved — a writer or removal, decided by measurement.

## Context

- **The governing finding is about placement, not wording** (WP-1065, protocol
  2.1, 12 cells): agents pipe the JSON response to a file and grep statistics
  back, so the decisive-swap license sentence — reworded correctly in the
  generated summary — reached agent context in **2 of 12 cells**. Typed
  fields beside the numbers survive that pipeline; prose does not. This WP
  ships the fields whose honesty case stands on its own; whether they *move
  decisions* is [1107](1107-eval-placement-round.md)'s measurement, and no
  claim of that kind is made here.
- **`SuggestedAction` has no execution-class field.** `Recipe.how ∈
  {stage, index, advice}` is computed in `report/apply.py` (RECIPES, pinned
  complete by `missing_kinds()`) and served only to the GUI
  (`gui/session.py:2037`). Over `refine_json`, `decrease_background_flexibility`
  arrives with `parameter_paths: []` (deliberate — `layer2.py:399-403`) and
  nothing distinguishes that from a bug. Add
  `SuggestedAction.execution: Literal["stage", "index", "advice"] | None = None`,
  stamped by `build_report` **from RECIPES** (import it; apply.py stays the
  one authority — do not restate the mapping). Additive defaulted field:
  no `SCHEMA_VERSION` bump (the 1069/1071/1072 precedent); the
  `report/schemas.py` version-history comment block gets its entry, and
  `THRESHOLDS_VERSION` moves only if a threshold does.
- **Max shift/esd** (McCusker 1999 §7: converged when max |Δθᵢ|/esdᵢ ≤ 0.1).
  The 1068 compliance audit noted it is satisfied a fortiori by scipy TRF at
  ftol 1e-9 "but the quantity itself is not reported" — an audit note that
  never became a WP. Compute it at solver close in
  `optimize/least_squares.py` from the final accepted step and the esds,
  **in external parameter units on both sides** (the transform chain makes
  internal-space ratios meaningless), and carry it on `Statistics` per the
  final stage. The 0.1 band is quoted from the paper, never tuned, and it
  gates nothing (the 1071 pattern: level-setting only) — its one consumer is
  a §4 step-1 sentence and, where a stage stops on `STAGE_MAX_ITER`, the
  magnitude that says how unconverged. Writer named per the WP-1076
  invariant: `run_least_squares` computes, `refine` copies, nothing else
  derives it.
- **Two `ActionKind` members have no emitter** — the exact WP-1076 shape ("a
  Literal member no code produces"): `refine_profile_widths` (the absence is
  documented, with its cost measured, in `test_e3_width_error_loop`'s
  docstring) and `collect_better_data` (whose whole recipe is "there is no
  verb"). Worse, the eval scorer
  (`tests/eval_report_agent/scorer.py:65`) includes `collect_better_data` in
  its answer vocabulary, so agents are scored on an action the report can
  never suggest. Resolution, decided in-WP by measurement and never by
  plausibility:
  - `refine_profile_widths`: the measurement already exists and it argues
    for a **writer, not a drop**. `test_e3_width_error_loop`
    (`tests/test_report_loop.py`) documents the gap: `_WIDTH_ACTIONS`
    (`report/layer2.py`) maps width trends only onto `phases.*.lor_size` /
    `phases.*.lor_strain`, so a pure instrument-Gaussian width error (E3:
    `w` planted at 2e-3 against a truth of 4e-3) is corrected *by proxy* —
    the accepted `refine_sample_size_broadening` adds Lorentzian sample
    broadening (Voigt compensation), taking χ²_red from ≈15.1 only to ≈4.3,
    well short of ≈1.0, and the planted parameter is never freed. Candidate
    writer: a width trend with no phase to attribute it to emits
    `refine_profile_widths` over `instrument.profile.*`; E3 is the
    ready-made acceptance fixture (the loop should now free `w` and reach
    the noise floor). If the emitter measures out worse than the proxy,
    drop the member instead — removal is free while there are no users
    (maintainer's standing ruling), recorded as a vocabulary event per the
    `report/schemas.py` version-history comment's precedent, with a
    release-notes line.
  - `collect_better_data`: either name its one honest writer — candidate:
    the resolution-limited abstention branch and/or a
    `PATTERN_UNDERSAMPLED`-conditioned emission, **measured to fire on a
    bundled or constructed fixture** before it ships (WP-1071 found no
    bundled protocol trips `DATA_SUPPORT_LOW`, so expect to construct one) —
    or drop it too. If it stays, the scorer keeps it; if it goes, the scorer
    vocabulary and `RECIPES`/`missing_kinds()` shrink with it, in the same
    commit.
- **Declined here, on the record**: `RivalComparison.decisive` — the
  no-verdict-token stance is a recorded design decision
  (`report/schemas.py:73-112`: "the reasoner gets the numbers"; the license
  is stated, the verdict is not) and stands; a FitReport structure-R
  statement — WP-1069's bar ("a threshold and a measured reason, not a
  field") is still unmet; re-folding the trajectory into the default
  payload — WP-1064's pre-registered kill stands. Moving the *license's
  placement* is 1107's question, not this WP's change.
- **Protocol coverage is enforced, and this WP works inside it** (from 1105,
  merged 2026-08-19): the protocol's §5 `ActionKind` table marks
  `refine_profile_widths` and `collect_better_data` **"no emitter —
  resolution in WP-1106"**; resolving them means updating those two rows in
  the same change. `tests/test_docs_consistency.py` fails when any
  `ActionKind`/`GateCode` member is absent from the protocol (a), or when an
  emitted engine `code="…"` literal has no row (b) — a code built
  dynamically goes in its `STATIC_INVISIBLE_CODES` dict with the emitter
  named. So a new member or emitter this WP adds is red until its protocol
  row lands, which is the intended workflow, not an obstacle. 1105 is
  merged, so the `execution` field's protocol row lands here as a one-row
  amendment.
- **For the `execution` field's docs** (from 1104): Toby (2024) §4's caveat —
  the largest-derivative parameter is not always appropriate to vary, his
  example being an instrument width out-deriving the sample term — is the
  literature's own statement of the leverage-vs-veto split, and WP-1050's
  handover records the identical U/V/W example.

## Non-goals

- Any change to what the report *says* — Layers 0–2 content is closed
  (1055–1057 measured it); this WP only types what already exists.
- The license sentence's placement (1107 measures the arms first).
- Per-action `expected_delta_chi2` (today one number per report, documented
  as such in its docstring) — a real computation change, out of scope.
- Protocol tables (1105); the `execution` field's protocol row lands as a
  one-row amendment here (1105 merged 2026-08-19).

## Tasks

- [x] `SuggestedAction.execution` stamped from RECIPES in `build_report`;
      serialization pin + a test that every emitted action carries it;
      version-history comment entry; `using/report.md` and the protocol
      ActionKind table updated.
- [x] `max_shift_over_esd` on `Statistics`: computed in
      `run_least_squares` (external units), copied by `refine`; unit test on
      a converged fit (≪ 0.1) and a `STAGE_MAX_ITER`-stopped fit (large);
      manual Part 2 gets the §7 criterion with its *Source:* line (the "a WP
      that adds physics adds its equation there" rule); §4 step 1 sentence.
- [x] Resolve `refine_profile_widths`: build the unattributed-width-trend
      emitter and measure it on E3 (the loop frees `w` and reaches the noise
      floor where the proxy stopped at χ²_red ≈4.3) — or drop the member if
      the emitter measures out worse; RECIPES/`missing_kinds()`/tests synced
      either way.
- [x] Resolve `collect_better_data`: build the firing measurement, then
      writer-or-drop; scorer vocabulary synced in the same commit.
- [x] Tests wrap-up: fast-suite delta stated; ruff; sphinx `-W` (manual
      touched).

## Acceptance

Every `ActionKind` member either has a demonstrated emitter (a test
constructs a state where it fires) or is gone; `execution` appears on every
action in a real report; the two new numbers ship with their writers named.

```sh
.venv/bin/python -m pytest tests/test_report_apply.py tests/test_report_loop.py tests/test_agent_surface.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

## References

- McCusker et al. (1999), J. Appl. Cryst. 32, 36 — §7, the convergence
  criterion (max shift/esd ≤ 0.1).
- WP-1065 (the 2-of-12 placement finding), WP-1076 (a declared name is a
  claim; an absent writer fails no test), WP-1064 (the trajectory kill),
  WP-1069 (the structure-R bar).

## Handover log

- **2026-08-19** — **closed ✅.** All five checklist items landed, one commit
  each; numbers with their fixtures in `milestones/v1.1.md` § Appendix
  (WP-1106). For a successor:
  - **Done**: `SuggestedAction.execution` (stamped in `build_report._stamped`
    from RECIPES on both exits; `How` now lives in `report/schemas.py`,
    apply.py imports it); `Statistics.max_shift_over_esd` (computed in
    `run_least_squares` via `_StepTracker` + `_final_shift_over_esd`,
    external units both sides, copied by `_build_result`/`_record` — the
    joint multi residual and `replay` carry the declared `None`);
    `refine_profile_widths` kept with the instrument-side-peer emitter
    (`_instrument_width_action`, Gaussian u/v/w only — E3 loop now reaches
    the 1.01 noise floor where the proxy stalled at 4.3);
    `collect_better_data` kept with the `resolution_limited`-abstention
    writer (`resolution_limited_action`, `COLLECT_DATA_CONFIDENCE = 0.5`) —
    the `PATTERN_UNDERSAMPLED` arm measured and rejected (both bundled
    synthetic fixtures trip it beside converged fits). Protocol §5 rows,
    §4 step-1 sentence, `using/report.md`, `using/results.md`, manual
    Part 2 § Convergence (`est-convergence`, `MAX_SHIFT_CONVERGED`
    substitution) all synced.
  - **One deviation from this WP's text, on the record**:
    `THRESHOLDS_VERSION` moved 1.1 → 1.2 although the Context bullet said it
    "moves only if a threshold does". The version-history block's own
    precedent governs: 0.5/0.6/0.7 bumped for additive fields and 1.0/1.1
    for emission-only changes ("no threshold moved" written in both), and
    this WP does both plus adds a level constant. Everything quotes the
    constant, so nothing else moved.
  - **Numbers** (`.venv` `[dev]`, jax and torch absent, darwin/arm64): fast
    suite 2424 passed + 117 skipped (~2:40) — exactly +4 over 1105's
    2420 + 117, the four tests added, no new skips; the acceptance trio
    64 passed; the two slow SRM 660c report-loop episodes 2 passed against
    the new emitters; ruff clean; sphinx `-W` green. Full suite left to
    nightly: the solver tracker is observation-only (residual values
    untouched) and the emission changes' real-data exposure is the two SRM
    episodes, which were run.
  - **Gotcha for anyone touching the tracker**: TRF acceptance is
    reconstructed from strictly-decreasing cost in the solver-facing
    residual closure — valid because TRF accepts exactly on cost decrease
    and the jacobian closure never routes through that residual. A new
    solver must either have an accepted-point callback (feed
    `_StepTracker.accept`) or that property.
  - **Next**: 1107 (the placement round) — its `### Inherited` names what
    this WP changed under its feet.
- **2026-08-19** — session start: branched `wp1106-report-placement-fields`
  from main at d67370b6 (1105's merge). Inherited pruned: the 1105 entry
  (protocol-row enforcement + the two "no emitter" rows) folded into Context
  because it governs tasks 3-4 and the row-amendment workflow; the 1104
  entry kept only its still-operational half (the Toby §4 pointer for the
  `execution` docs) — its "nothing surfaced that needs a schema field"
  arrival note was context for creating this WP, already reflected in the
  task list, so deleted. Non-goals' conditional on 1105 being open resolved
  (it merged).
- **2026-08-18** — created from the agentic-report planning session, with
  [1104](1104-agent-protocol-literature-audit.md)/[1105](1105-agent-protocol-hygiene.md)/[1107](1107-eval-placement-round.md).
