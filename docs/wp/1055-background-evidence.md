# WP-1055 — Background evidence in the FitReport

Milestone: v1.0 · Status: ✅ 2026-08-12 — `FitReport.background` carries both
failure modes; the two flexibility actions finally have an emitter; the
over-flexible fixture wins on Rwp *and* GoF and lands 2.6× further from truth
Depends on: —

## Goal

A `FitReport.background` section that makes the two background failure modes
visible in the report itself — the over-flexible background that *improves* every
statistic an agent reads while biasing ADPs and QPA fractions, and the too-stiff
background whose misfit today falls invisibly between the Layer-0 regions — plus
the two background action kinds finally emitted, as evidence-bearing hypotheses.

## Context

**Why this is the agentic failure mode to fear.** An over-flexible background
lowers Rwp while biasing ADPs up and scales (hence QPA fractions) down — the one
failure that makes every number an agent currently reads look *better*. The
detecting statistic exists (`optimize.statistics.background_absorption`: block
projection R² of a structural Jacobian column onto the background column span;
measured ~46 % block absorption where every pairwise ρ sat at ~0.2, and the
P-spline penalty rows matter 5× — R² 0.46 → 0.08 at λ = 10⁴, so the *full*
Jacobian with penalty rows is mandatory). Today it reaches a caller only as the
`BACKGROUND_ABSORPTION` guard diagnostic — fired-or-silent, and absent from the
FitReport entirely (`report/apply.py`'s recipe notes say exactly this).

**The stiff/wavy direction is structurally invisible.** Layer-0 regions are peak
clusters cut from ticks ∪ residual peaks (`report/layer0.py`), so smooth
between-peak misfit lands in no region; its only trace is the unexplained
remainder in "top 15 regions carry X % of χ²". Measured corollary (2026-08-11,
broad-peak LaB₆ scenario): raw Rwp is flattered by background — a
heavily-broadened pattern and a sharp one both report Rwp 0.0137 despite entirely
different information content. `Statistics` already carries the honest pair
(`rwp_background_subtracted` — the Toby-recommended variant — plus
`durbin_watson` and `esd_inflation`); the report quotes none of them.

**Emission gap, verified 2026-08-11 by reading `report/layer2.py`:**
`increase_background_flexibility` / `decrease_background_flexibility` are emitted
**nowhere** — they exist only as `RECIPES` advice entries and as an `alternatives`
member on `refine_biso`. The recipe notes (which are good: they name the
ADP/QPA-bias trap and the diagnostic to read) render only if an action exists to
carry them.

**Data plumbing is the design decision.** `background_absorption` needs the final
Jacobian, available at fit time (where `check_guards` already computes it) and not
from a bare `RefinementResult`. Choose the carrier: an additive defaulted field on
`RefinementResult` (or `Statistics`) holding the *screened values* — every
(path, R²) pair, not just >threshold firings; a fired/not-fired bit is a verdict,
0.46-vs-0.08 is evidence. Additive-defaulted keeps `SCHEMA_VERSION` still (the
WP-1043 events-rule precedent: new field, not a new kind); history nodes store
state not curves, and a dozen floats is state. WP-1056 needs the same carrier
seam for its correlation/soft-mode summary — whichever WP lands first builds it,
the other imports it (coordinate via `### Inherited`).

**New, cheap statistics** (arrays already in the result): off-region χ² share
(1 − Σ region shares, made explicit) and a Durbin–Watson d computed over the
off-region channels only — low d off-peak is the wavy/stiff-background signature
(Schwarzenbach et al. 1989: under serial correlation the covariances are
"grossly in error"; Hill & Flack 1987 is the powder citation, already in
`optimize/statistics.py`).

**The protocol home already exists** (from WP-1057, closed 2026-08-12).
AGENT_PROTOCOL §4b ("Declare the deliverable") has a QPA profile that already
names this WP's evidence in prose — the scale↔Biso↔background degeneracy, the
measured block-absorption R² ≈ 46 %, `background_absorption` — as the rows
that decide a QPA deliverable. The protocol task hangs off that paragraph and
replaces its prose pointers with the new rows rather than opening a second
home. `FitReport.lebail_gap` is available beside them (a large ratio means the
intensity model is wrong, and wrong intensities are wrong fractions — §4b
already states that reading for QPA), and `THRESHOLDS_VERSION` is 0.5 as of
1057, so a further bump is a fresh decision this WP makes.

## Non-goals

- No change to background *models* or their defaults; no auto-tuning of Chebyshev
  order or P-spline λ. The actions stay advice-kind (`how="advice"`) — the recipe
  notes explain why a one-click flexibility change is a button whose own report
  cannot see what it did.
- No correlation matrix / soft modes — WP-1056 (shared carrier only).
- No purpose/stopping-criteria protocol text — WP-1057.

## Tasks

- [x] Carrier: persist the screened `background_absorption` values (path → R²)
      from fit time onto the result as an additive defaulted field; document the
      SCHEMA_VERSION reasoning in the schema docstring.
- [x] `FitReport.background` (additive, defaulted): rwp / rwp_background_subtracted
      pair, background share of total intensity, off-region χ² share, off-region
      Durbin–Watson, and the absorption table. Rendered into `summary` as one
      clause when any component crosses its comment-threshold (thresholds as
      *context*, not publish/withhold switches).
- [x] Emit `decrease_background_flexibility` when absorption evidence is strong,
      `increase_background_flexibility` when off-region misfit + low off-region d
      say the background shape is fighting the data — both as hypotheses carrying
      the numbers, confidence built the Layer-2 way (importance × quality), veto
      rules unchanged. An amorphous hump / un-modelled broad phase is the designed
      confound for the increase direction — the rationale names it, and the kind
      stays `how="advice"`. New emitters for existing kinds are the same
      `THRESHOLDS_VERSION` question WP-1054 carries: decide it once, coordinated
      (whichever WP lands second inherits the decision via `### Inherited`).
- [x] `docs/AGENT_PROTOCOL.md`: extend §4's judging order and the §7 diagnostics
      table with the background section's rows; note the Rwp-flattering measured
      fact.
- [x] Tests: over-flexible fixture (high absorption R², report says so;
      Rwp *improves* while the section flags it — the pinned inversion),
      too-stiff fixture (off-region d), converged clean fixture stays quiet +
      obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_fitreport_layers.py tests/test_background_auto.py -q
.venv/bin/python -m ruff check src tests examples
```

The over-flexible fixture's report carries the absorption evidence and emits
`decrease_background_flexibility` while its Rwp is *better* than the reference —
the statistic-inversion case is the acceptance, per the v0.5 rule that a
correction's evidence is never an Rwp comparison.

## References

- `optimize/statistics.py::background_absorption` docstring (measured 46 %/0.2
  and the 5× penalty-row effect); Toby (2006) Powder Diffr. 21 (the
  background-subtracted Rwp); Hill & Flack (1987) J. Appl. Cryst. 20 (DW);
  Schwarzenbach et al. (1989) Acta Cryst. A45 — local corpus
  `derived/A7LFQSXQ/`.
- `report/apply.py` background recipe notes (the advice text this WP gives an
  emitter to).

## Handover log

- **2026-08-12** — **closed.** All five checklist items landed in six commits.
  What a successor needs:

  **The carrier is general, and WP-1056 should extend it rather than add one.**
  `RefinementResult.identifiability: Identifiability | None` exists because the
  Jacobian is never serialized, so a statistic read off it is screened at fit
  time or lost. Today it holds one field (`background_absorption: dict[path,
  R²]`); 1056's correlation/soft-mode summary belongs beside it. It is filled
  from `GuardReport.measured_background_absorption`, a deliberately-not-findings
  seventh field on `GuardReport` — `check_guards` measures **once**, the
  threshold decides only which rows become `GuardFinding`s, and both the report
  and the `BACKGROUND_ABSORPTION` diagnostic quote that one table. `_run_plan`
  now returns the **last stage's** guard (the answer-producing one, the rule
  `_constraint_diagnostics` already followed); `replay` and joint multi-histogram
  fits leave it `None`, which the schema says to read as "not measured here",
  never "no absorption".

  **Three measurements shaped the design, and two of them contradicted the WP's
  own plan.** (i) The off-region χ² *share* is not a detector — it tracks the
  off-region channel count (0.89 on a converged clean fit, 0.24 on the worst
  too-stiff background, where the peaks are misfitted too). It is published as
  the WP asked, and `off_region_chi2_reduced` was added beside it as the
  magnitude question. (ii) The Rwp pair cannot be a summary trigger: a sharp
  LaB₆ fit and one under 0.6° of broadening both report Rwp 0.0137 and read
  0.0490/0.0766 background-subtracted (so the subtracted number is the
  informative one — the WP's premise held), but both *converged* controls sit at
  ratio 3.6 and 5.6, and every background-dominated pattern crosses any useful
  threshold. Published, never quoted in `summary`, and AGENT_PROTOCOL §4 step 7
  is where a consumer is told to read it. (iii) The stiff gate needs magnitude
  **and** Durbin-Watson, because χ²_red is σ-scaled and d is not — mis-scaled
  esds alone must not fire it.

  **Measured separations** (LaB₆, `tests/test_background_auto.py`, 2026-08-12) —
  worst block-R² / off-region χ²_red / off-region d: 1°-knot spline λ=0 →
  0.46/1.02/2.03; Chebyshev-6 correct → 0.01/0.97/2.00; Chebyshev-2 over a hump
  → 0.02/12.55/0.19; -3 → 0.02/12.16/0.18; -8 → 0.02/4.56/0.44. Neither gate can
  fire on the other's failure and the clean control fires neither.

  **The acceptance inversion, measured** (same data, 15-70°, broad peaks; truth
  Biso 0.5/0.5): the 1°-knot unpenalized spline gives Rwp 0.08852 / GoF 1.022 and
  Biso 0.958/0.000 (one on its bound), the correct Chebyshev-6 gives 0.08969 /
  1.025 and 0.691/0.327 — the wrong background wins every agreement index and is
  2.6× further from truth. `tests/output/wp1055_over_flexible_zoom.png` is the
  argument for the whole section: white-noise residuals inside ±3σ, peaks tracked
  exactly, only a faint waviness in the background curve. Nothing a human or a
  VLM would flag.

  **Gotchas.**
  - `THRESHOLDS_VERSION` is **0.6**. Two kinds that had never been emitted
    anywhere now are, so a consumer enumerating what it can receive sees more.
  - Both emitters carry **empty `parameter_paths`** on purpose. The obvious glob
    `instrument.background.*` would read as "free the background", which every
    plan already does, so `apply_strategy_veto` would grey the suggestion out
    for entirely the wrong reason.
  - `report/apply.py`'s notes argued advice-kind from "a button whose own report
    cannot see what it did". That reason **expired** with this WP and the note
    saying "not in this report" had become false. The kinds stay advice on the
    structural reason that was always the real one: a Chebyshev term is a
    property of the model, not a member of `turn_on`. A test now pins the
    retired sentence out.
  - `increase_background_flexibility` is capped at 0.60 (`BACKGROUND_INCREASE_CAP`
    in `layer2.py`) — a stiff background, an amorphous hump and an un-modelled
    broad phase share the signature, and bending the background over either of
    the last two hides it.
  - **Left undone, deliberately.** On the too-stiff fixture the residual runs 12σ
    over hundreds of channels and noise on top clears the 5σ peak floor in **146**
    places, so `add_impurity_phase` is emitted at 0.90 on a specimen with no
    impurity — outranking the background call. `note_background_crosstalk` makes
    each action name the other but does **not** cap, because the two findings are
    about disjoint channels by construction (Layer 0 segments a region around
    every residual peak, so an unmatched peak is never off-region) and both can
    be true. Whether the *ranking* is right is a WP-1054-family question this WP
    had no measurement to settle; it is in 1058's and 1059's `### Inherited`.
  - `multi.py` screens per histogram with `hist.h.` path prefixes and was left
    alone: a pooled `Identifiability` would reach `for_histogram(h)` with paths
    that do not match that histogram's own.

  **Counts** (`[dev,jax,torch]`, darwin/arm64, this checkout's `.venv`): fast
  selection **2288 passed, 5 skipped**, from 2282+5 at WP-1057's close — exactly
  the six tests added, no new skip. Per file: `test_background_auto` 24 → 29,
  `test_fitreport_layers` 31 → 32. Wall clock 3:06 and 3:13 on two runs of the
  same tree. Full suite not run this session (nothing here touches an acceptance
  protocol or an indexing engine).

  **CLAUDE.md** sat one line under its 600-line cap, so the background invariant's
  new clause was paid for by re-wrapping the `sig()` bullet beside it and folding
  its WP-1029 narrative into the parenthetical that already points at that WP's
  file (protocol rule 4). No rule or fact dropped — the diff is a re-wrap.

- **2026-08-11** — created, from the FitReport design review (background named
  the important agentic failure mode). Not started.
