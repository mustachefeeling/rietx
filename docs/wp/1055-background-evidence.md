# WP-1055 — Background evidence in the FitReport

Milestone: v1.0 · Status: ⬜
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

## Non-goals

- No change to background *models* or their defaults; no auto-tuning of Chebyshev
  order or P-spline λ. The actions stay advice-kind (`how="advice"`) — the recipe
  notes explain why a one-click flexibility change is a button whose own report
  cannot see what it did.
- No correlation matrix / soft modes — WP-1056 (shared carrier only).
- No purpose/stopping-criteria protocol text — WP-1057.

## Tasks

- [ ] Carrier: persist the screened `background_absorption` values (path → R²)
      from fit time onto the result as an additive defaulted field; document the
      SCHEMA_VERSION reasoning in the schema docstring.
- [ ] `FitReport.background` (additive, defaulted): rwp / rwp_background_subtracted
      pair, background share of total intensity, off-region χ² share, off-region
      Durbin–Watson, and the absorption table. Rendered into `summary` as one
      clause when any component crosses its comment-threshold (thresholds as
      *context*, not publish/withhold switches).
- [ ] Emit `decrease_background_flexibility` when absorption evidence is strong,
      `increase_background_flexibility` when off-region misfit + low off-region d
      say the background shape is fighting the data — both as hypotheses carrying
      the numbers, confidence built the Layer-2 way (importance × quality), veto
      rules unchanged. An amorphous hump / un-modelled broad phase is the designed
      confound for the increase direction — the rationale names it, and the kind
      stays `how="advice"`. New emitters for existing kinds are the same
      `THRESHOLDS_VERSION` question WP-1054 carries: decide it once, coordinated
      (whichever WP lands second inherits the decision via `### Inherited`).
- [ ] `docs/AGENT_PROTOCOL.md`: extend §4's judging order and the §7 diagnostics
      table with the background section's rows; note the Rwp-flattering measured
      fact.
- [ ] Tests: over-flexible fixture (high absorption R², report says so;
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

- **2026-08-11** — created, from the FitReport design review (background named
  the important agentic failure mode). Not started.
