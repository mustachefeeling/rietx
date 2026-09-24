# WP-1421 — the result reproduces its own number

Milestone: unscheduled · Status: ⬜ — tasks 1 and 3-5 landed from outside under shape (a) (PR #432); tasks 2 and 6 open in part
Depends on: — (1310 soft: it owns which vector reaches the final diagnostics)
Priority: P3 2026-09-23 — a number a reader cannot reproduce by a margin the record already calls staleness

## Goal

A `RefinementResult`'s statistics and curves can be reproduced from its own
parameters. Either they come from a compile at the returned values, or the
result says they were measured on the last stage's frozen compile and how far
a fresh compile sits from them. A reader can then check the number a report
quotes.

## Context

Issue #272 (2026-09-06), measured read-only on `origin/main` `2ba7a9a3` on
the two shipped acceptance fixtures, driven exactly as their tests drive them.

**What happens.** `_build_result` (`refine.py`) evaluates the model the last
stage compiled, at the values that stage ended on. That compile froze its
peak windows and FCJ node counts at the stage's *start* (root CLAUDE.md
§ Invariants, frozen-per-stage discreteness). When the last stage moves the
parameters that sized them, a fresh compile at `result.parameters` draws a
different curve and reports a different χ².

| fixture | χ² reported | χ² from a fresh compile at θ\* | Δ | Rwp reported → recompiled |
|---|---|---|---|---|
| Si SRM 640c, 11-BM (`test_acceptance_si640c.py::_fit`) | 88 284.16 | 89 501.76 | −1217.6 (1.38 %) | 0.08263 → 0.08319 |
| FAP, lab Cu Kα (`test_acceptance_fap.py`) | 17 180.94 | 17 177.56 | +3.4 (0.02 %) | — |

χ² here is Σ w(y−y_c)², with the P-spline penalty rows excluded because they
cancel between the two compiles. `y_calc` differs at 9 621 of 47 999 points
on Si (max |Δy| 175 counts on a 198 744-count peak) and at 1 131 of 5 750 on
FAP. `y_background` is bit-identical. Every parameter value matches the
objects the fresh compile was built from.

**Why.** Si's last stage moved λ, zero, `axial_sl`, `axial_hl`, `u`,
`lor_size` and `lor_strain`. Its windows shrank from a mean of 1001 points
(max 1420) to 846 (max 939), and its FCJ nodes fell from 1984 to 403. The
reflection list stayed at 50, so this is window width and node count and not
membership. A `window_slack_deg` sweep at θ\* puts about 1 600 χ² units on
window width alone (89 502 at 0.3°, 87 905 at 0.6°, 87 633 at 1.0°). The
node share was not separated out.

**What it does not do.** The minimum is not biased. A scan of χ² against the
cell with windows frozen at θ\* against recompiled at each point moves the
minimum by ≤ 0.0014 esd(a) on FAP and by 1e-4 of the λ-equivalent esd on
Si. A stage started 0.5 % off in the cell returns an `a` within 0.013 esd of
the next round's re-cut answer. The fit is right. The reported number is the
one the returned model does not give back.

**The package already knows this shape, one rank over.** `schemas/history.py`
documents a node's cached metrics as *as-optimised*, "the agreement the
least squares actually reached", and `docs/manual/using/history.md` calls the
difference `replay` shows a staleness signal. Root CLAUDE.md § Conventions
says the same. That convention was written for history nodes, where the
frozen number is the honest record of what the solver saw. #272 is about the
*result*, the number a reader quotes. WP-1076's rule applies: a reported Rwp
the returned model does not reproduce is a number nobody can check.

**Two shapes.** (a) One final compile at θ\* before `_build_result`, with the
curves and statistics taken from it. It costs one model build per fit. Every
pinned number whose last stage frees a window-sizing parameter then moves,
by 0.7 % relative in Rwp on Si. The history node keeps its as-optimised
metrics, so result and node differ by the amount `replay` already shows.
(b) State it. The statistics block carries which compile produced it, and
the fresh-compile χ² beside it. No number moves, and a reader sees the size.

**Triage recommendation (2026-09-15):** (b) first. It is the honest state
1076 asks for and it moves nothing. Then decide (a) on the spread task 1
measures across every acceptance fixture and golden. A `stage_reports=True`
caller (WP-1058) sees the same effect at every stage boundary, so whatever
lands applies to the stage trajectory too.

Le Bail and Pawley intensities are frozen per stage as well
(`ReflectionState`). A fresh compile must carry them, never re-partition.

### Inherited

**2026-09-23, from the issue triage (issue #272).** The reporter claimed this
on the thread on 2026-09-23: a fix is in progress on their fork, off
`ff56d956`, one PR per issue. No PR existed when this was written, so
`wp_claim.py status` cannot see the claim yet. A session picking this WP
checks the thread and `gh pr list` first.

**From WP-1342 (2026-09-19).** `StageResult` gained `held_reach`, a
`dict[str, list[str]]` written on every stage beside `held`. It is state a
replay has to reproduce, and it is the first *mapping* on that record rather
than a list, so a comparison written for the list fields will pass over it in
silence. It is also readable only while the held column is still in θ — the
runner captures it before `set_vary` and carries it on `_StageHold` — so a
rebuild that tries to re-derive it from the finished table gets nothing back.
That is this WP's own thesis in miniature: what a state *records* and what
rebuilding from that state *produces* are two objects.

**From WP-1432 (2026-09-19).** One measured instance of this WP's
class, found and fixed. `replay` rebuilt its table from the node's own
structure and re-declared the recorded ties on it, and a user tie onto a
coordinate DOF was applied a second time in doing so. A replayed node therefore
answered for a model one displacement past the one recorded: x = 0.2174294764
against the node's 0.2083647382, Rwp 10.711190685 against 10.708626649, with
nothing in the answer saying which model it had measured. The repair is
`ParameterTable.rebase_anchored_dofs`, called by both consumers of the tie
register. The shape is worth carrying into this WP: what a state *records* and
what rebuilding from that state *produces* are two objects, and only a test
comparing them can say they agree.

## Non-goals

- Window sizing (`WINDOW_AREA_TOL`, `WINDOW_MIN_DEG`) and the frozen-per-stage
  invariant. Both stay.
- History node metrics. They stay as-optimised.
- The time-of-flight arm the issue mentions, where an asymmetric profile makes
  the truncation shape-dependent and the minimum does move. Fenced.

## Tasks

- [x] Measure: for every acceptance fixture and every golden, χ² and Rwp on
      the last stage's compile against a fresh compile at θ\*. The table
      goes in the handover and decides (a).
- [ ] The statistics block says which compile produced it, and carries the
      fresh-compile χ² when one was measured. The writer is named at review
      (1076).
- [x] Decide (a) from the table. If taken, one compile after the last stage,
      and the goldens regenerated in the same commit with the diff quoted.
- [x] `using/history.md`'s staleness sentence and the results chapter say
      which compile a result's statistics come from.
- [x] Tests: a fixture whose last stage moves a window-sizing parameter
      asserts the statement; under (b) every golden stays bit-identical.
- [ ] Skill: a `references/judging.md` row saying which compile a reported
      Rwp comes from, and that the difference is not a fit defect.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_si640c.py tests/test_acceptance_fap.py tests/test_fitreport_layers.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #272 (2026-09-06; rietx on `origin/main` `2ba7a9a3`).
- WP-1076 (a declared name is a claim); WP-1058 (the stage trajectory).
- `schemas/history.py`'s as-optimised docstring; `docs/manual/using/history.md`.

## Handover log

### 2026-09-24 — landed from outside under shape (a); a result is measured on a compile at its own values

`Refinement.fit` and `run_stage` now end with one more compile at the values
the result returns (`Refinement._final_compile`). It is built with the last
stage's own discrete settings (the moving set, c_w and the window slack), so
only the values differ. This is issue #272's fix, live since PR #432 merged
(`09ce2cd1`, closing #272). It came from an outside contributor with no
`WP-NNNN:` prefix and no touch of this file, so this entry is written at the
merge. The WP stays `⬜`: two tasks are open in part, and no session owns it.

**The measurement, and why it took (a) rather than the recommended (b).** The
relative χ² gap between the frozen and the fresh compile was logged on 358
fits, across the acceptance files and the synthetic chains.

- Single-pattern acceptance, maximum per file: si640c 8.4e-5, fap 2.0e-4,
  capillary 6.1e-5, nac 1.6e-4, srm676a 5.2e-4, lab6_cbn 5.5e-4, extra_peaks
  6.4e-4, dispersion 1.1e-3, powderline 1.1e-3, qpa_roundrobin 1.1e-3,
  stephens 2.5e-3, fitreport_layers 2.4e-3.
- Synthetic chains: held_phase 5.2e-3, test_sequential 2.0e-3.
- The QPA sample-1 chain: 1.3-2.1e-2.

(a) costs one compile, 0.055 s on the Si 640c fit (3.7 s) and 0.024 s on FAP.
(b) would have needed the sizing decision to be observable. **No golden
moved.** On Si 640c the fresh compile gives χ² 88 283.25 against the frozen
88 284.16, so the reported Rwp 0.08263 stands. The issue's 89 501.76 is
reproduced exactly by `compile_model(..., moving_paths=None)`. Its 1.38 %
therefore comes from the moving-set sizing claim, not from the
start-of-stage freeze. `results.md` says how to reproduce a result's number.

**What the merge makes possible.** A result's `y_calc`, statistics and
per-point residuals reproduce from a rebuild at `result.parameters`. The
history node keeps its as-optimised metrics. The info finding
`FROZEN_COMPILE_STALE` quotes both χ² when they differ by more than
`FROZEN_COMPILE_CHI2_REL` = 1e-2. At 1e-3 it fired on 74 of the 358 fits; at
1e-2 it fires on 6, all of them in the sample-1 chain.
`sequential.NOT_A_SERIES_FINDING` keeps it out of
`SEQUENTIAL_PERSISTENT_FINDING`.

**What it deliberately does not do.**

- The solve, the covariance and every esd stay the last solve's.
- **The weights stay the solve's.** `result.sigma` is still a lookup of the σ
  the model used (WP-1309), because a measured background widens σ at the
  scale a compile sees. A test pins this on a fit whose last stage moves the
  background scale.
- A **Pawley** result and a **joint** fit (`multi.py` builds its own) get no
  fresh compile. Both report the frozen figures and never carry the row.
  `results.md` and the diagnostics row say so, because round 1 of the review
  asked for it.
- The statistics block has no field naming its compile. The fresh χ² appears
  only in the finding's message, past the threshold. That is task 2 in part.
- There is no `judging.md` row (task 6); the `diagnostics.md` row stands in
  for it.

**Measured on the merged tree** (`origin/main` `2d42303a`
plus #430, #432 and #431; Linux x86_64, 4 cores, python 3.12, `[dev,jax]`):

- Fast suite: 1 failed, 5944 passed, 96 skipped. The failure is
  `test_telemetry.py`'s unwritable-directory case, which fails on main alone
  because the bench runs as root.
- Fast collect with #432 alone on main: 6015 → 6022, +7.
- Full `-m slow`: 2 failed, 188 passed, 9 skipped in 1:32:45. Neither failure
  is #432's. The brucite XPASS(strict) is red on main's own nightly (run 51).
  The held-phase ramp tripped its 60 s runaway guard at 147 s under load. Run
  alone it passes, in 21.4 s on this tree against 20.3 s on main, the difference being the one extra
  compile per pattern.
- `ruff`: clean.

**Next.** Decide whether task 2's "says which compile produced it" still
wants a field now that every non-Pawley, single-histogram result is
fresh-compiled. Then decide whether task 6's `judging.md` row adds anything
the diagnostics row does not already say.

- **2026-09-15** — created, from the 2026-09-15 issue triage (issue #272).
  Checked against the tree: `_build_result` evaluates the stage's own model;
  the as-optimised convention lives in `schemas/history.py` and
  `using/history.md` and was written for nodes, not results. Recommendation
  recorded: state before move.
