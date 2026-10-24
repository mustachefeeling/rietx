# WP-2003 batch: the reseed fence on, status-only and off

Task 2's measurement half: "the `RESEED_FACTOR` question measured on three chain families
with the fence on, off and status-only: patterns reseeded, accepted values that differ, and
the cost in evaluations", with the per-pattern table (WP-1124's rule). **Measurements only;
no tier and no ruling.** Every table below is printed by
`.venv/bin/python docs/wp/2003-batch/measure_reseed.py --table` from the JSONs in
`docs/wp/2003-batch/reseed/`; the prose sections around them quote the same JSONs.

## How it was run

- **Script**: `docs/wp/2003-batch/measure_reseed.py` (its docstring has the commands), one
  process per family and arm, `RIETX_TELEMETRY=0`. Run on 2026-10-24 against this worktree's
  tree (`rietx 1.10.0.dev0`, `src/rietx/sequential.py` unmodified while the runs were in flight).
- **venv** `[dev]` (the worktree's `.venv`), Python 3.12.3, Linux 6.18.44 x86_64 (glibc 2.39),
  4 CPUs.
- **Not alone.** Another session's `pytest tests/test_acceptance_sequential.py -k
  first_rung_bound_moves -s` ran through most of the measurement (until about 18:00 UTC), and
  `pytest tests/test_answer_invariant_defaults.py -k series` at the start; load average
  3.8-11.9 on 4 cores, and up to four of this script's own processes ran at once. Wall clock
  is therefore context only and is never the comparison; evaluations are.
- **BLAS threads.** Every JSON here was written with
  `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1` (`environment.blas_threads_env`), by
  the final script except `cpd_on.json`, written by an earlier revision whose measurement path
  is the same and which lacked only `anchored_dof_paths` (added by `--annotate`). One thread
  was chosen after `numpy.polynomial.legendre.leggauss(444)` was measured at 5.4-6.0 s with default
  threading on this loaded machine against 0.014 s with one thread (the closing stage's FCJ
  quadrature calls it on every cache miss; § Unresolved). `planted`, `planted-null` and
  `trigger` had first run under default threading: every rerun file is bit-identical to its
  first run (`values_sha` at every pattern, same rungs, same evaluations) except
  `planted-null_ref`, within 1.6e-7 esd. The compiled-kernel thread count is the default (4)
  everywhere; the compiled tier is each family's own protocol setting (off for `planted`,
  `planted-null` and the `cr2wo6` series, on elsewhere).

## The arms

| arm | `SequentialRefinement.fit` kwargs | what it means here |
|---|---|---|
| `on` | `reseed=True, reseed_factor=1.25` (`RESEED_FACTOR`) | the default |
| `status` | `reseed=True, reseed_factor=float("inf")` | escalates on a diverged or raised rung only, never on Rwp. `fit` does not validate the factor (`sequential.py:1028`, no check in the validation block), so `inf` is accepted as given; every `rwp_fence` is then `inf`, no entry is `above_fence`, and `SEQUENTIAL_RWP_OUTLIER` cannot fire. |
| `off` | `reseed=False` | no fence- or status-driven escalation. The fence is still recorded (`sequential.py:1677`), so `above_fence` and `SEQUENTIAL_RWP_OUTLIER` still fire. **Not "no ladder"**: a first rung that WP-1127's budget truncated still escalates one rung, because `forced` (`sequential.py:1561`) bypasses `reseed` (`sequential.py:1569-1571`) — seen at `planted` pattern 87 in all three arms. This contradicts `2003-batch/README.md` § Quarantine's record (b), "Under `reseed=False`, `rungs_tried` is `["warm"]`", for that case. |
| `ref` | every pattern alone, cold, from the chain's own initial models (`SequentialRefinement(...).fit([pattern])`) | what the chain's cold rung computes; the reference for real data |
| `ref_seeded` | cpd only: the acceptance suite's independent protocol (`seed_scales` on each mixture, as `conftest.sample1_results`) | the reference the acceptance suite compares chains against |

For the synthetic families the reference is also the simulated truth (`truth` in the JSON,
compared on each family's key paths only, since a protocol that holds a parameter away from
the truth would otherwise name that parameter everywhere: the trigger plan holds the axial
H/L at its 0.020 start against a true 0.030, so S/L absorbs it).

**Comparisons.** Of a row against a baseline row: the worst |Δ|/esd over every path both
carry, plus the weight fractions, with the **baseline's** esd (`on`'s for an arm against `on`,
the reference's for an arm against a reference; the row's own only where the baseline has
none). Not the larger of the two: a fit that lands far off carries inflated esds and would hide
the difference. At cpd-1b, `status` against `on` is 2.6 esd by the larger esd and 1 220 by
`on`'s. An esd-less path counts as moved past 1e-6 relative
(`≠n no-esd`); the anchored coordinate DOFs (`ParameterTable.anchored_dof_paths`, recorded per
run) are skipped and the absolute x/y/z rows compared instead, because a coordinate DOF is a
displacement from where its own fit began (root CLAUDE.md, WP-1333; compared naively, cr2wo6's
150 K pattern read 5.7 esd from its cold fit on `phases.0.atoms.3.dof.1` and 0.087 esd on the
coordinates). "Differ" = > 0.1 esd, or an esd-less move, or a path only one row carries.
"Bit-identical" compares a hash of the full-precision values and esds (`values_sha`; stored
values carry 12 significant figures). Evaluations: `SeriesEntry.n_iterations` (scipy's `nfev`
convention, summed over every returned rung) and, beside it, every solve's `nfev`/`njev`
counted at `rietx.optimize.lm.minimize` and scipy's `least_squares`, which also sees the
automatic profile-interval refits the entry does not count.

## Families: what ran in full and what was cut

| family | patterns | status |
|---|---|---|
| `cpd` (the protocol: `qpa_plan()`, closing stage on) | 8 | `on`, `ref`, `ref_seeded` full; **`status` and `off` cut to the first 2** (§ The CPD protocol run) |
| `cpd-noclose` (declared variant: the one change `plan.closing_window_tol = None`) | 8 | full, all five arms |
| `planted` | 248 | full (no cut needed: under 2.5 min an arm) |
| `planted-null` | 248 | full |
| `trigger` | 10 | full |
| `cr2wo6` (the optional fourth) | 2 | full |
| `tut05-jump`, `tut05-broken` | 7 each | full; added because no arm escalates anywhere on `trigger`, so it cannot separate the arms |

`tests/data/mg090*` (the held-out family) was not used.

## The CPD protocol run

`cpd` is the family's own protocol, closing stage included. The `on` arm ran all eight
patterns in 2 640 s, 2 617 s of it at cpd-1b; `ref` and `ref_seeded` ran all eight in under
50 s each. **`status` and `off` are cut to the first two patterns** (`--first 2`; each JSON says
`cut`). At cpd-1b both keep the warm rung, which ends `max_iter` at Rwp 0.7652 after its
closing stage runs to the 400-evaluation cap, 2 337 s of single-BLAS-thread compute. A full run
of each was started first. Both spent about 11 min on cpd-1c, its closing stage at 56 of 400
evaluations when stopped, with that 0.7652 already in the median the fence is taken over
(`accepted_rwp = [0.16307, 0.76520]`, read off the live process). They were stopped at 19:02 UTC
and rerun on the first two patterns. Their patterns 2-7 are therefore not measured; `on`'s are
in § Past the cut. `cpd-noclose` is the same chain with the closing stage off, all arms in
full. It is kept beside `cpd` because the two part exactly at cpd-1b.

## IUCr CPD sample-1 chain 1a-1h (real, lab Cu Kα)

Protocol: tests/test_acceptance_sequential.py chained_all: SequentialRefinement(structure, qarr_instrument()) with seed_scales on 1a, carry=('*',), plan=qpa_plan(), refit='single', dispersion declined, compiled tier default.  Cut: `status` first 2 of 8 patterns; `off` first 2 of 8 patterns, so the tables comparing arms carry patterns 0-1 and the patterns past the cut follow them for the arms that ran them.  Arms: on, status, off; reference `ref_seeded`.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | cpd-1a | c [c] | 0.1631 | — | 167 | c [c] | 0.1631 | — | 167 | c [c] | 0.1631 | — | 167 |
| 1 | cpd-1b | w→ws [ws] | 0.7652→0.1378 | 0.2038 | 629 | w [w] | 0.7652 (max_iter) | inf | 536 | w [w] | 0.7652 (max_iter) | 0.2038* | 536 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off |
|---|---|---|---|
| 0 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 1 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, CELL_RUNAWAY, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED, STAGE_MAX_ITER | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, CELL_RUNAWAY, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, S_RWP_OUTLIER, SPACE_GROUP_SETTING_ASSUMED, STAGE_MAX_ITER |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | on vs ref_seeded | status vs ref_seeded | off vs ref_seeded |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 |
| 1 | 1.22e+03 (instrument.geometry.axial_sl) | 1.22e+03 (instrument.geometry.axial_sl) | 9.49 (phases.0.lor_strain) | 1.19e+03 (instrument.source.lines.1.weight) | 1.19e+03 (instrument.source.lines.1.weight) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref_seeded` the reference.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | ref_seeded |
|---|---|---|---|---|---|
| 0 | `phases.0.cell.a` | 4.7585(32) | 4.7585(32) | 4.7585(32) | 4.7585(32) |
| 0 | `phases.0.cell.c` | 12.990(13) | 12.990(13) | 12.990(13) | 12.990(13) |
| 0 | `phases.1.cell.a` | 3.24861(64) | 3.24861(64) | 3.24861(64) | 3.24861(64) |
| 0 | `phases.2.cell.a` | 5.46281(98) | 5.46281(98) | 5.46281(98) | 5.46281(98) |
| 0 | `instrument.zero_shift` | -0.049(67) | -0.049(67) | -0.049(67) | -0.049(67) |
| 0 | `instrument.geometry.sample_displacement` | -0.086(97) | -0.086(97) | -0.086(97) | -0.086(97) |
| 1 | `phases.0.cell.a` | 4.75804(38) | 4.987(88) | 4.987(88) | 4.75809(38) |
| 1 | `phases.0.cell.c` | 12.9894(11) | 13.56(24) | 13.56(24) | 12.9895(10) |
| 1 | `phases.1.cell.a` | 3.24896(50) | 3.415(75) | 3.415(75) | 3.24906(54) |
| 1 | `phases.2.cell.a` | 5.46280(52) | 5.72(10) | 5.72(10) | 5.46287(52) |
| 1 | `instrument.zero_shift` | -0.045(35) | 18.0(74) | 18.0(74) | -0.040(35) |
| 1 | `instrument.geometry.sample_displacement` | 0.019(55) | 26(11) | 26(11) | 0.026(54) |

### Weight fractions, per pattern (wt %)

W(σ(W)) per arm; weighed = the composition as weighed, the QPA truth.

| k | phase | on | status | off | ref_seeded | weighed |
|---|---|---|---|---|---|---|
| 0 | corundum | 1.72(0.64) | 1.72(0.64) | 1.72(0.64) | 1.72(0.64) | 1.15 |
| 0 | zincite | 3.35(0.21) | 3.35(0.21) | 3.35(0.21) | 3.35(0.21) | 4.04 |
| 0 | fluorite | 94.93(0.65) | 94.93(0.65) | 94.93(0.65) | 94.93(0.65) | 94.81 |
| 1 | corundum | 94.24(0.23) | 86.68(12.90) | 86.68(12.90) | 94.29(0.23) | 94.31 |
| 1 | zincite | 1.34(0.12) | 2.28(7.14) | 2.28(7.14) | 1.28(0.12) | 1.36 |
| 1 | fluorite | 4.42(0.19) | 11.04(9.85) | 11.04(9.85) | 4.43(0.19) | 4.33 |

### Past the cut: patterns 2-7, `on` only

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | on vs ref_seeded | on: codes |
|---|---|---|---|---|---|---|---|
| 2 | cpd-1c | w [w] | 0.1057 | 0.1880 | 64 | 14.2 (phases.1.lor_strain) | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED |
| 3 | cpd-1d | w [w] | 0.1247 | 0.1722 | 30 | 8.8 (phases.2.lor_strain) | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED |
| 4 | cpd-1e | w [w] | 0.1244 | 0.1641 | 25 | 7.45 (phases.0.lor_strain) | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED |
| 5 | cpd-1f | w [w] | 0.1102 | 0.1559 | 25 | 11.9 (phases.1.lor_strain) | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED |
| 6 | cpd-1g | w [w] | 0.1182 | 0.1557 | 22 | 9.06 (phases.1.lor_strain) | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED |
| 7 | cpd-1h | w [w] | 0.1211 | 0.1555 | 25 | 7.05 (phases.2.lor_strain) | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE, SPACE_GROUP_SETTING_ASSUMED |

| k | path | on | ref_seeded | weighed |
|---|---|---|---|---|
| 2 | `phases.0.cell.a` | 4.75760(88) | 4.75753(88) |  |
| 2 | `phases.0.cell.c` | 12.9884(37) | 12.9880(38) |  |
| 2 | `phases.1.cell.a` | 3.24892(23) | 3.24886(23) |  |
| 2 | `phases.2.cell.a` | 5.46224(87) | 5.46211(89) |  |
| 2 | `instrument.zero_shift` | -0.073(29) | -0.088(29) |  |
| 2 | `instrument.geometry.sample_displacement` | -0.114(45) | -0.140(44) |  |
| 2 | W corundum (wt %) | 6.26(0.61) | 6.30(0.62) | 5.04 |
| 2 | W zincite (wt %) | 91.93(0.65) | 91.92(0.66) | 93.59 |
| 2 | W fluorite (wt %) | 1.80(0.22) | 1.78(0.22) | 1.36 |
| 3 | `phases.0.cell.a` | 4.75824(47) | 4.75828(51) |  |
| 3 | `phases.0.cell.c` | 12.9902(15) | 12.9901(17) |  |
| 3 | `phases.1.cell.a` | 3.24917(29) | 3.24919(32) |  |
| 3 | `phases.2.cell.a` | 5.46308(49) | 5.46312(54) |  |
| 3 | `instrument.zero_shift` | -0.044(34) | -0.039(37) |  |
| 3 | `instrument.geometry.sample_displacement` | -0.097(50) | -0.088(55) |  |
| 3 | W corundum (wt %) | 15.42(0.50) | 15.34(0.52) | 13.53 |
| 3 | W zincite (wt %) | 28.97(0.33) | 28.85(0.35) | 32.89 |
| 3 | W fluorite (wt %) | 55.62(0.45) | 55.80(0.46) | 53.58 |
| 4 | `phases.0.cell.a` | 4.75821(37) | 4.75823(37) |  |
| 4 | `phases.0.cell.c` | 12.9896(10) | 12.9896(11) |  |
| 4 | `phases.1.cell.a` | 3.24916(26) | 3.24917(27) |  |
| 4 | `phases.2.cell.a` | 5.46306(44) | 5.46309(45) |  |
| 4 | `instrument.zero_shift` | -0.041(32) | -0.042(32) |  |
| 4 | `instrument.geometry.sample_displacement` | -0.056(47) | -0.058(48) |  |
| 4 | W corundum (wt %) | 57.35(0.41) | 57.34(0.42) | 55.12 |
| 4 | W zincite (wt %) | 12.88(0.21) | 12.82(0.21) | 15.25 |
| 4 | W fluorite (wt %) | 29.77(0.36) | 29.84(0.36) | 29.62 |
| 5 | `phases.0.cell.a` | 4.75811(35) | 4.75808(36) |  |
| 5 | `phases.0.cell.c` | 12.9894(11) | 12.9893(11) |  |
| 5 | `phases.1.cell.a` | 3.24906(23) | 3.24905(24) |  |
| 5 | `phases.2.cell.a` | 5.46282(40) | 5.46279(41) |  |
| 5 | `instrument.zero_shift` | -0.050(28) | -0.054(29) |  |
| 5 | `instrument.geometry.sample_displacement` | -0.098(42) | -0.107(43) |  |
| 5 | W corundum (wt %) | 30.22(0.50) | 30.20(0.50) | 27.06 |
| 5 | W zincite (wt %) | 50.11(0.43) | 50.12(0.44) | 55.22 |
| 5 | W fluorite (wt %) | 19.66(0.32) | 19.68(0.32) | 17.72 |
| 6 | `phases.0.cell.a` | 4.75810(33) | 4.75809(34) |  |
| 6 | `phases.0.cell.c` | 12.9893(10) | 12.9892(10) |  |
| 6 | `phases.1.cell.a` | 3.24902(23) | 3.24902(23) |  |
| 6 | `phases.2.cell.a` | 5.46274(39) | 5.46274(40) |  |
| 6 | `instrument.zero_shift` | -0.046(28) | -0.050(28) |  |
| 6 | `instrument.geometry.sample_displacement` | -0.075(41) | -0.082(42) |  |
| 6 | W corundum (wt %) | 33.74(0.43) | 33.73(0.44) | 31.37 |
| 6 | W zincite (wt %) | 30.30(0.29) | 30.22(0.30) | 34.21 |
| 6 | W fluorite (wt %) | 35.96(0.34) | 36.05(0.35) | 34.42 |
| 7 | `phases.0.cell.a` | 4.75820(43) | 4.75822(43) |  |
| 7 | `phases.0.cell.c` | 12.9895(13) | 12.9896(13) |  |
| 7 | `phases.1.cell.a` | 3.24910(29) | 3.24911(30) |  |
| 7 | `phases.2.cell.a` | 5.46305(50) | 5.46308(51) |  |
| 7 | `instrument.zero_shift` | -0.052(35) | -0.050(36) |  |
| 7 | `instrument.geometry.sample_displacement` | -0.134(52) | -0.133(53) |  |
| 7 | W corundum (wt %) | 37.28(0.52) | 37.31(0.53) | 35.12 |
| 7 | W zincite (wt %) | 26.44(0.34) | 26.34(0.34) | 30.19 |
| 7 | W fluorite (wt %) | 36.28(0.43) | 36.35(0.43) | 34.69 |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`.  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | differ from ref_seeded | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 8 | 1 | 0 | 0 | 0 | 8 | — | 7 (1, 2, 3, 4, 5, 6, 7) | 987 | 451 | 987 / 915 | 2.2-2616.6 | 2640 |
| status | 2 | 0 | 0 | 0 | 0 | 1 | 1 (1) | 1 (1) | 703 | 703 | 703 / 635 | 6.2-2310.8 | 2317 |
| off | 2 | 0 | 0 | 0 | 1 (1) | 1 | 1 (1) | 1 (1) | 703 | 703 | 703 / 635 | 6.0-2310.2 | 2316 |
| ref_seeded | 8 | 0 | 0 | 0 | 0 | 1 | 7 (1, 2, 3, 4, 5, 6, 7) | — | 1218 | 1218 | 1218 / 1183 | 4.8-6.8 | 46 |

### Series-level codes

| code | on | status | off |
|---|---|---|---|
| `SEQUENTIAL_PERSISTENT_FINDING` | 26 | 0 | 0 |
| `SEQUENTIAL_RWP_OUTLIER` | 0 | 0 | 1 |

Failures (`SeriesFailure`): on 0, status 0, off 0.

## IUCr CPD sample-1 chain 1a-1h (real, lab Cu Kα), closing stage off (declared variant)

Protocol: tests/test_acceptance_sequential.py chained_all: SequentialRefinement(structure, qarr_instrument()) with seed_scales on 1a, carry=('*',), plan=qpa_plan(), refit='single', dispersion declined, compiled tier default; the one change: plan.closing_window_tol = None.  Arms: on, status, off; reference `ref_seeded`.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | cpd-1a | c [c] | 0.1676 | — | 162 | c [c] | 0.1676 | — | 162 | c [c] | 0.1676 | — | 162 |
| 1 | cpd-1b | w [w] | 0.1633 | 0.2095 | 410 | w [w] | 0.1633 | inf | 410 | w [w] | 0.1633 | 0.2095 | 410 |
| 2 | cpd-1c | w [w] | 0.1135 | 0.2068 | 52 | w [w] | 0.1135 | inf | 52 | w [w] | 0.1135 | 0.2068 | 52 |
| 3 | cpd-1d | w [w] | 0.1303 | 0.2042 | 21 | w [w] | 0.1303 | inf | 21 | w [w] | 0.1303 | 0.2042 | 21 |
| 4 | cpd-1e | w [w] | 0.1287 | 0.1835 | 16 | w [w] | 0.1287 | inf | 16 | w [w] | 0.1287 | 0.1835 | 16 |
| 5 | cpd-1f | w [w] | 0.1161 | 0.1629 | 18 | w [w] | 0.1161 | inf | 18 | w [w] | 0.1161 | 0.1629 | 18 |
| 6 | cpd-1g | w [w] | 0.1236 | 0.1619 | 13 | w [w] | 0.1236 | inf | 13 | w [w] | 0.1236 | 0.1619 | 13 |
| 7 | cpd-1h | w [w] | 0.1262 | 0.1609 | 16 | w [w] | 0.1262 | inf | 16 | w [w] | 0.1262 | 0.1609 | 16 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off |
|---|---|---|---|
| 0 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 1 | CELL_RUNAWAY, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLOOR_HIT, HIGH_CORRELATION, P_UNC, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLOOR_HIT, HIGH_CORRELATION, P_UNC, SPACE_GROUP_SETTING_ASSUMED | CELL_RUNAWAY, CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLOOR_HIT, HIGH_CORRELATION, P_UNC, SPACE_GROUP_SETTING_ASSUMED |
| 2 | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, FROZEN_COMPILE_STALE, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, FROZEN_COMPILE_STALE, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, FROZEN_COMPILE_STALE, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 3 | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | CONSTRAINT_ACTIVE, DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 4 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 5 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 6 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |
| 7 | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED | DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | on vs ref_seeded | status vs ref_seeded | off vs ref_seeded |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 |
| 1 | 0 | 0 | 10 (phases.0.scale) +8 | 10 (phases.0.scale) +8 | 10 (phases.0.scale) +8 |
| 2 | 0 | 0 | 4.95 (instrument.profile.v) | 4.95 (instrument.profile.v) | 4.95 (instrument.profile.v) |
| 3 | 0 | 0 | 2.42 (instrument.profile.v) | 2.42 (instrument.profile.v) | 2.42 (instrument.profile.v) |
| 4 | 0 | 0 | 3.68 (instrument.profile.v) | 3.68 (instrument.profile.v) | 3.68 (instrument.profile.v) |
| 5 | 0 | 0 | 3.82 (instrument.profile.v) | 3.82 (instrument.profile.v) | 3.82 (instrument.profile.v) |
| 6 | 0 | 0 | 5.19 (instrument.profile.v) | 5.19 (instrument.profile.v) | 5.19 (instrument.profile.v) |
| 7 | 0 | 0 | 3.36 (instrument.profile.v) | 3.36 (instrument.profile.v) | 3.36 (instrument.profile.v) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref_seeded` the reference.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | ref_seeded |
|---|---|---|---|---|---|
| 0 | `phases.0.cell.a` | 4.7584(33) | 4.7584(33) | 4.7584(33) | 4.7584(33) |
| 0 | `phases.0.cell.c` | 12.991(13) | 12.991(13) | 12.991(13) | 12.991(13) |
| 0 | `phases.1.cell.a` | 3.24862(70) | 3.24862(70) | 3.24862(70) | 3.24862(70) |
| 0 | `phases.2.cell.a` | 5.4628(11) | 5.4628(11) | 5.4628(11) | 5.4628(11) |
| 0 | `instrument.zero_shift` | -0.050(73) | -0.050(73) | -0.050(73) | -0.050(73) |
| 0 | `instrument.geometry.sample_displacement` | -0.09(11) | -0.09(11) | -0.09(11) | -0.09(11) |
| 1 | `phases.0.cell.a` | — | — | — | 4.75809(39) |
| 1 | `phases.0.cell.c` | — | — | — | 12.9896(11) |
| 1 | `phases.1.cell.a` | 3.24913(60) | 3.24913(60) | 3.24913(60) | 3.24909(55) |
| 1 | `phases.2.cell.a` | 5.46325(38) | 5.46325(38) | 5.46325(38) | 5.46290(53) |
| 1 | `instrument.zero_shift` | -0.012(14) | -0.012(14) | -0.012(14) | -0.040(36) |
| 1 | `instrument.geometry.sample_displacement` | 0.062(29) | 0.062(29) | 0.062(29) | 0.026(56) |
| 2 | `phases.0.cell.a` | 4.7575(11) | 4.7575(11) | 4.7575(11) | 4.7572(10) |
| 2 | `phases.0.cell.c` | 12.9893(44) | 12.9893(44) | 12.9893(44) | 12.9889(43) |
| 2 | `phases.1.cell.a` | 3.24901(32) | 3.24901(32) | 3.24901(32) | 3.24884(26) |
| 2 | `phases.2.cell.a` | 5.4624(11) | 5.4624(11) | 5.4624(11) | 5.4621(10) |
| 2 | `instrument.zero_shift` | -0.053(39) | -0.053(39) | -0.053(39) | -0.090(33) |
| 2 | `instrument.geometry.sample_displacement` | -0.079(59) | -0.079(59) | -0.079(59) | -0.145(50) |
| 3 | `phases.0.cell.a` | 4.75829(66) | 4.75829(66) | 4.75829(66) | 4.75826(61) |
| 3 | `phases.0.cell.c` | 12.9902(21) | 12.9902(21) | 12.9902(21) | 12.9902(20) |
| 3 | `phases.1.cell.a` | 3.24921(41) | 3.24921(41) | 3.24921(41) | 3.24919(38) |
| 3 | `phases.2.cell.a` | 5.46314(70) | 5.46314(70) | 5.46314(70) | 5.46311(64) |
| 3 | `instrument.zero_shift` | -0.030(48) | -0.030(48) | -0.030(48) | -0.041(45) |
| 3 | `instrument.geometry.sample_displacement` | -0.070(70) | -0.070(70) | -0.070(70) | -0.091(65) |
| 4 | `phases.0.cell.a` | 4.75827(44) | 4.75827(44) | 4.75827(44) | 4.75823(39) |
| 4 | `phases.0.cell.c` | 12.9897(12) | 12.9897(12) | 12.9897(12) | 12.9897(11) |
| 4 | `phases.1.cell.a` | 3.24920(31) | 3.24920(31) | 3.24920(31) | 3.24917(28) |
| 4 | `phases.2.cell.a` | 5.46314(52) | 5.46314(52) | 5.46314(52) | 5.46309(47) |
| 4 | `instrument.zero_shift` | -0.031(37) | -0.031(37) | -0.031(37) | -0.042(34) |
| 4 | `instrument.geometry.sample_displacement` | -0.037(55) | -0.037(55) | -0.037(55) | -0.059(50) |
| 5 | `phases.0.cell.a` | 4.75820(53) | 4.75820(53) | 4.75820(53) | 4.75806(44) |
| 5 | `phases.0.cell.c` | 12.9897(16) | 12.9897(16) | 12.9897(16) | 12.9894(14) |
| 5 | `phases.1.cell.a` | 3.24913(35) | 3.24913(35) | 3.24913(35) | 3.24904(29) |
| 5 | `phases.2.cell.a` | 5.46294(61) | 5.46294(61) | 5.46294(61) | 5.46278(51) |
| 5 | `instrument.zero_shift` | -0.033(42) | -0.033(42) | -0.033(42) | -0.056(36) |
| 5 | `instrument.geometry.sample_displacement` | -0.069(63) | -0.069(63) | -0.069(63) | -0.110(54) |
| 6 | `phases.0.cell.a` | 4.75816(43) | 4.75816(43) | 4.75816(43) | 4.75808(36) |
| 6 | `phases.0.cell.c` | 12.9895(13) | 12.9895(13) | 12.9895(13) | 12.9893(11) |
| 6 | `phases.1.cell.a` | 3.24907(29) | 3.24907(29) | 3.24907(29) | 3.24902(25) |
| 6 | `phases.2.cell.a` | 5.46283(50) | 5.46283(50) | 5.46283(50) | 5.46274(42) |
| 6 | `instrument.zero_shift` | -0.034(35) | -0.034(35) | -0.034(35) | -0.050(30) |
| 6 | `instrument.geometry.sample_displacement` | -0.052(51) | -0.052(51) | -0.052(51) | -0.083(45) |
| 7 | `phases.0.cell.a` | 4.75831(53) | 4.75831(53) | 4.75831(53) | 4.75821(46) |
| 7 | `phases.0.cell.c` | 12.9898(15) | 12.9898(15) | 12.9898(15) | 12.9896(14) |
| 7 | `phases.1.cell.a` | 3.24918(37) | 3.24918(37) | 3.24918(37) | 3.24911(32) |
| 7 | `phases.2.cell.a` | 5.46319(62) | 5.46319(62) | 5.46319(62) | 5.46308(55) |
| 7 | `instrument.zero_shift` | -0.033(43) | -0.033(43) | -0.033(43) | -0.052(38) |
| 7 | `instrument.geometry.sample_displacement` | -0.100(64) | -0.100(64) | -0.100(64) | -0.136(57) |

### Weight fractions, per pattern (wt %)

W(σ(W)) per arm; weighed = the composition as weighed, the QPA truth.

| k | phase | on | status | off | ref_seeded | weighed |
|---|---|---|---|---|---|---|
| 0 | corundum | 1.59(0.64) | 1.59(0.64) | 1.59(0.64) | 1.59(0.64) | 1.15 |
| 0 | zincite | 3.31(0.23) | 3.31(0.23) | 3.31(0.23) | 3.31(0.23) | 4.04 |
| 0 | fluorite | 95.09(0.65) | 95.09(0.65) | 95.09(0.65) | 95.09(0.65) | 94.81 |
| 1 | corundum | 94.84(0.27) | 94.84(0.27) | 94.84(0.27) | 94.29(0.23) | 94.31 |
| 1 | zincite | 1.08(0.13) | 1.08(0.13) | 1.08(0.13) | 1.28(0.12) | 1.36 |
| 1 | fluorite | 4.08(0.24) | 4.08(0.24) | 4.08(0.24) | 4.43(0.20) | 4.33 |
| 2 | corundum | 6.25(0.75) | 6.25(0.75) | 6.25(0.75) | 6.16(0.72) | 5.04 |
| 2 | zincite | 92.01(0.80) | 92.01(0.80) | 92.01(0.80) | 92.09(0.76) | 93.59 |
| 2 | fluorite | 1.73(0.27) | 1.73(0.27) | 1.73(0.27) | 1.75(0.25) | 1.36 |
| 3 | corundum | 15.26(0.62) | 15.26(0.62) | 15.26(0.62) | 15.32(0.62) | 13.53 |
| 3 | zincite | 28.89(0.42) | 28.89(0.42) | 28.89(0.42) | 28.90(0.42) | 32.89 |
| 3 | fluorite | 55.84(0.56) | 55.84(0.56) | 55.84(0.56) | 55.78(0.56) | 53.58 |
| 4 | corundum | 57.29(0.45) | 57.29(0.45) | 57.29(0.45) | 57.31(0.44) | 55.12 |
| 4 | zincite | 12.80(0.23) | 12.80(0.23) | 12.80(0.23) | 12.84(0.22) | 15.25 |
| 4 | fluorite | 29.90(0.39) | 29.90(0.39) | 29.90(0.39) | 29.85(0.38) | 29.62 |
| 5 | corundum | 30.07(0.67) | 30.07(0.67) | 30.07(0.67) | 30.11(0.63) | 27.06 |
| 5 | zincite | 50.30(0.58) | 50.30(0.58) | 50.30(0.58) | 50.25(0.55) | 55.22 |
| 5 | fluorite | 19.63(0.43) | 19.63(0.43) | 19.63(0.43) | 19.64(0.40) | 17.72 |
| 6 | corundum | 33.61(0.49) | 33.61(0.49) | 33.61(0.49) | 33.68(0.47) | 31.37 |
| 6 | zincite | 30.31(0.33) | 30.31(0.33) | 30.31(0.33) | 30.29(0.32) | 34.21 |
| 6 | fluorite | 36.08(0.39) | 36.08(0.39) | 36.08(0.39) | 36.03(0.38) | 34.42 |
| 7 | corundum | 37.20(0.59) | 37.20(0.59) | 37.20(0.59) | 37.24(0.57) | 35.12 |
| 7 | zincite | 26.40(0.38) | 26.40(0.38) | 26.40(0.38) | 26.41(0.36) | 30.19 |
| 7 | fluorite | 36.40(0.48) | 36.40(0.48) | 36.40(0.48) | 36.35(0.47) | 34.69 |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`.  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | differ from ref_seeded | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 8 | 0 | 0 | 0 | 0 | 8 | — | 7 (1, 2, 3, 4, 5, 6, 7) | 708 | 708 | 708 / 669 | 0.9-18.2 | 29 |
| status | 8 | 0 | 0 | 0 | 0 | 8 | 0 | 7 (1, 2, 3, 4, 5, 6, 7) | 708 | 708 | 708 / 669 | 0.9-18.2 | 29 |
| off | 8 | 0 | 0 | 0 | 0 | 8 | 0 | 7 (1, 2, 3, 4, 5, 6, 7) | 708 | 708 | 708 / 669 | 0.8-17.3 | 27 |
| ref_seeded | 8 | 0 | 0 | 0 | 0 | 1 | 7 (1, 2, 3, 4, 5, 6, 7) | — | 1164 | 1164 | 1164 / 1138 | 2.5-3.3 | 23 |

### Series-level codes

| code | on | status | off |
|---|---|---|---|
| `SEQUENTIAL_DISCONTINUITY` | 1: phases.0.scale 0→1 | 1: phases.0.scale 0→1 | 1: phases.0.scale 0→1 |
| `SEQUENTIAL_PERSISTENT_FINDING` | 25 | 25 | 25 |

Failures (`SeriesFailure`): on 0, status 0, off 0.

## planted perovskite cooling ramp, 248 patterns (synthetic), events: background step 50, blank frame 87, unmodelled phase from 124, cubic → tetragonal 186

Protocol: tests/planted_series.py refine(): cubic_model(T0), plan='mccusker_default', refit='single', forward, x=T (K), carry=('*',), compiled tier OFF (numpy_path).  Arms: on, status, off; reference `ref`; truth: the simulation.

248 patterns.  The ladder, codes and accepted-value tables carry the 129 where any two arms differ (rungs tried or kept, status, fence verdict, entry codes, or a value by > 0.1 esd) or an arm differs from `ref` by > 0.1 esd, plus every event pattern ±2; the key-value tables carry only the 20 of those where a value differs, plus the events ±2.  Every other pattern has the same rungs, status, verdict and codes in every arm and values within 0.1 esd of each other and of `ref`; all of them are in the JSON.  Distance from truth selects no row (every pattern is some esd from it).

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 48 | T048 | w [w] | 0.0501 | 0.0613 | 9 | w [w] | 0.0501 | inf | 9 | w [w] | 0.0501 | 0.0613 | 9 |
| 49 | T049 | w [w] | 0.0488 | 0.0614 | 8 | w [w] | 0.0488 | inf | 8 | w [w] | 0.0488 | 0.0614 | 8 |
| 50 | T050 | w [w] | 0.0413 | 0.0613 | 7 | w [w] | 0.0413 | inf | 7 | w [w] | 0.0413 | 0.0613 | 7 |
| 51 | T051 | w [w] | 0.0420 | 0.0613 | 9 | w [w] | 0.0420 | inf | 9 | w [w] | 0.0420 | 0.0613 | 9 |
| 52 | T052 | w [w] | 0.0429 | 0.0613 | 9 | w [w] | 0.0429 | inf | 9 | w [w] | 0.0429 | 0.0613 | 9 |
| 85 | T085 | w [w] | 0.0415 | 0.0605 | 9 | w [w] | 0.0415 | inf | 9 | w [w] | 0.0415 | 0.0605 | 9 |
| 86 | T086 | w [w] | 0.0420 | 0.0605 | 9 | w [w] | 0.0420 | inf | 9 | w [w] | 0.0420 | 0.0605 | 9 |
| 87 | T087 | w→ws [ws] | 0.0480→0.0481 | 0.0605 | 63 | w→ws [ws] | 0.0480→0.0481 | inf | 63 | w→ws [ws] | 0.0480→0.0481 | 0.0605 | 63 |
| 88 | T088 | w [w] | 0.0415 | 0.0605 | 16 | w [w] | 0.0415 | inf | 16 | w [w] | 0.0415 | 0.0605 | 16 |
| 89 | T089 | w [w] | 0.0419 | 0.0604 | 7 | w [w] | 0.0419 | inf | 7 | w [w] | 0.0419 | 0.0604 | 7 |
| 122 | T122 | w [w] | 0.0415 | 0.0534 | 8 | w [w] | 0.0415 | inf | 8 | w [w] | 0.0415 | 0.0534 | 8 |
| 123 | T123 | w [w] | 0.0420 | 0.0534 | 7 | w [w] | 0.0420 | inf | 7 | w [w] | 0.0420 | 0.0534 | 7 |
| 124 | T124 | w [w] | 0.0427 | 0.0534 | 9 | w [w] | 0.0427 | inf | 9 | w [w] | 0.0427 | 0.0534 | 9 |
| 125 | T125 | w [w] | 0.0430 | 0.0533 | 9 | w [w] | 0.0430 | inf | 9 | w [w] | 0.0430 | 0.0533 | 9 |
| 126 | T126 | w [w] | 0.0426 | 0.0534 | 7 | w [w] | 0.0426 | inf | 7 | w [w] | 0.0426 | 0.0534 | 7 |
| 134 | T134 | w→ws→c [w] | 0.0553→0.0553 | 0.0536* | 66 | w [w] | 0.0553 | inf | 7 | w [w] | 0.0553 | 0.0536* | 7 |
| 135 | T135 | w→ws→c [c] | 0.0561→0.0561 | 0.0536* | 69 | w [w] | 0.0561 | inf | 9 | w [w] | 0.0561 | 0.0536* | 9 |
| 136 | T136 | w→ws→c [ws] | 0.0573→0.0573 | 0.0536* | 70 | w [w] | 0.0573 | inf | 9 | w [w] | 0.0573 | 0.0536* | 9 |
| 137 | T137 | w→ws→c [c] | 0.0590→0.0590 | 0.0536* | 69 | w [w] | 0.0590 | inf | 9 | w [w] | 0.0590 | 0.0536* | 9 |
| 138 | T138 | w→ws→c [ws] | 0.0605→0.0605 | 0.0536* | 64 | w [w] | 0.0605 | inf | 7 | w [w] | 0.0605 | 0.0536* | 7 |
| 139 | T139 | w→ws→c [ws] | 0.0621→0.0621 | 0.0536* | 70 | w [w] | 0.0621 | inf | 8 | w [w] | 0.0621 | 0.0536* | 8 |
| 140 | T140 | w→ws→c [c] | 0.0638→0.0638 | 0.0536* | 69 | w [w] | 0.0638 | inf | 9 | w [w] | 0.0638 | 0.0536* | 9 |
| 141 | T141 | w→ws→c [ws] | 0.0647→0.0647 | 0.0536* | 66 | w [w] | 0.0647 | inf | 8 | w [w] | 0.0647 | 0.0536* | 8 |
| 142 | T142 | w→ws→c [c] | 0.0671→0.0671 | 0.0537* | 66 | w [w] | 0.0671 | inf | 7 | w [w] | 0.0671 | 0.0537* | 7 |
| 143 | T143 | w→ws→c [c] | 0.0676→0.0676 | 0.0537* | 64 | w [w] | 0.0676 | inf | 7 | w [w] | 0.0676 | 0.0537* | 7 |
| 144 | T144 | w→ws→c [w] | 0.0699→0.0699 | 0.0537* | 64 | w [w] | 0.0699 | inf | 7 | w [w] | 0.0699 | 0.0537* | 7 |
| 145 | T145 | w→ws→c [ws] | 0.0712→0.0712 | 0.0537* | 67 | w [w] | 0.0712 | inf | 7 | w [w] | 0.0712 | 0.0537* | 7 |
| 146 | T146 | w→ws→c [c] | 0.0729→0.0729 | 0.0537* | 67 | w [w] | 0.0729 | inf | 7 | w [w] | 0.0729 | 0.0537* | 7 |
| 147 | T147 | w→ws→c [c] | 0.0743→0.0743 | 0.0537* | 67 | w [w] | 0.0743 | inf | 7 | w [w] | 0.0743 | 0.0537* | 7 |
| 148 | T148 | w→ws→c [c] | 0.0761→0.0761 | 0.0537* | 64 | w [w] | 0.0761 | inf | 7 | w [w] | 0.0761 | 0.0537* | 7 |
| 149 | T149 | w→ws→c [c] | 0.0787→0.0787 | 0.0537* | 67 | w [w] | 0.0787 | inf | 8 | w [w] | 0.0787 | 0.0537* | 8 |
| 150 | T150 | w→ws→c [c] | 0.0789→0.0789 | 0.0538* | 65 | w [w] | 0.0789 | inf | 8 | w [w] | 0.0789 | 0.0538* | 8 |
| 151 | T151 | w→ws→c [c] | 0.0802→0.0802 | 0.0539* | 70 | w [w] | 0.0802 | inf | 9 | w [w] | 0.0802 | 0.0539* | 9 |
| 152 | T152 | w→ws→c [c] | 0.0819→0.0819 | 0.0546* | 66 | w [w] | 0.0819 | inf | 7 | w [w] | 0.0819 | 0.0546* | 7 |
| 153 | T153 | w→ws→c [w] | 0.0834→0.0834 | 0.0554* | 64 | w [w] | 0.0834 | inf | 7 | w [w] | 0.0834 | 0.0554* | 7 |
| 154 | T154 | w→ws→c [c] | 0.0848→0.0848 | 0.0566* | 66 | w [w] | 0.0848 | inf | 9 | w [w] | 0.0848 | 0.0566* | 9 |
| 155 | T155 | w→ws→c [c] | 0.0868→0.0868 | 0.0579* | 66 | w [w] | 0.0868 | inf | 7 | w [w] | 0.0868 | 0.0579* | 7 |
| 156 | T156 | w→ws→c [ws] | 0.0882→0.0882 | 0.0587* | 67 | w [w] | 0.0882 | inf | 9 | w [w] | 0.0882 | 0.0587* | 9 |
| 157 | T157 | w→ws→c [c] | 0.0882→0.0882 | 0.0595* | 65 | w [w] | 0.0882 | inf | 7 | w [w] | 0.0882 | 0.0595* | 7 |
| 158 | T158 | w→ws→c [w] | 0.0905→0.0905 | 0.0595* | 63 | w [w] | 0.0905 | inf | 7 | w [w] | 0.0905 | 0.0595* | 7 |
| 159 | T159 | w→ws→c [w] | 0.0921→0.0921 | 0.0596* | 70 | w [w] | 0.0921 | inf | 8 | w [w] | 0.0921 | 0.0596* | 8 |
| 160 | T160 | w→ws→c [w] | 0.0922→0.0922 | 0.0597* | 66 | w [w] | 0.0922 | inf | 7 | w [w] | 0.0922 | 0.0597* | 7 |
| 161 | T161 | w→ws→c [ws] | 0.0934→0.0934 | 0.0598* | 63 | w [w] | 0.0934 | inf | 7 | w [w] | 0.0934 | 0.0598* | 7 |
| 162 | T162 | w→ws→c [ws] | 0.0951→0.0951 | 0.0598* | 66 | w [w] | 0.0951 | inf | 7 | w [w] | 0.0951 | 0.0598* | 7 |
| 163 | T163 | w→ws→c [w] | 0.0968→0.0968 | 0.0599* | 69 | w [w] | 0.0968 | inf | 8 | w [w] | 0.0968 | 0.0599* | 8 |
| 164 | T164 | w→ws→c [c] | 0.0976→0.0976 | 0.0600* | 66 | w [w] | 0.0976 | inf | 8 | w [w] | 0.0976 | 0.0600* | 8 |
| 165 | T165 | w→ws→c [ws] | 0.0991→0.0991 | 0.0601* | 67 | w [w] | 0.0991 | inf | 8 | w [w] | 0.0991 | 0.0601* | 8 |
| 166 | T166 | w→ws→c [ws] | 0.1002→0.1002 | 0.0601* | 68 | w [w] | 0.1002 | inf | 8 | w [w] | 0.1002 | 0.0601* | 8 |
| 167 | T167 | w→ws→c [w] | 0.1014→0.1014 | 0.0601* | 70 | w [w] | 0.1014 | inf | 9 | w [w] | 0.1014 | 0.0601* | 9 |
| 168 | T168 | w→ws→c [ws] | 0.1020→0.1020 | 0.0601* | 71 | w [w] | 0.1020 | inf | 8 | w [w] | 0.1020 | 0.0601* | 8 |
| 169 | T169 | w→ws→c [c] | 0.1051→0.1051 | 0.0602* | 65 | w [w] | 0.1051 | inf | 8 | w [w] | 0.1051 | 0.0602* | 8 |
| 170 | T170 | w→ws→c [ws] | 0.1046→0.1046 | 0.0603* | 72 | w [w] | 0.1046 | inf | 9 | w [w] | 0.1046 | 0.0603* | 9 |
| 171 | T171 | w→ws→c [w] | 0.1068→0.1068 | 0.0604* | 67 | w [w] | 0.1068 | inf | 9 | w [w] | 0.1068 | 0.0604* | 9 |
| 172 | T172 | w→ws→c [ws] | 0.1069→0.1069 | 0.0605* | 65 | w [w] | 0.1069 | inf | 7 | w [w] | 0.1069 | 0.0605* | 7 |
| 173 | T173 | w→ws→c [w] | 0.1092→0.1092 | 0.0605* | 70 | w [w] | 0.1092 | inf | 9 | w [w] | 0.1092 | 0.0605* | 9 |
| 174 | T174 | w→ws→c [w] | 0.1105→0.1105 | 0.0605* | 66 | w [w] | 0.1105 | inf | 7 | w [w] | 0.1105 | 0.0605* | 7 |
| 175 | T175 | w→ws→c [c] | 0.1108→0.1108 | 0.0605* | 66 | w [w] | 0.1108 | inf | 7 | w [w] | 0.1108 | 0.0605* | 7 |
| 176 | T176 | w→ws→c [w] | 0.1125→0.1125 | 0.0605* | 72 | w [w] | 0.1125 | inf | 9 | w [w] | 0.1125 | 0.0605* | 9 |
| 177 | T177 | w→ws→c [c] | 0.1137→0.1137 | 0.0605* | 65 | w [w] | 0.1137 | inf | 7 | w [w] | 0.1137 | 0.0605* | 7 |
| 178 | T178 | w→ws→c [ws] | 0.1145→0.1145 | 0.0606* | 65 | w [w] | 0.1145 | inf | 7 | w [w] | 0.1145 | 0.0606* | 7 |
| 179 | T179 | w→ws→c [w] | 0.1155→0.1155 | 0.0606* | 67 | w [w] | 0.1155 | inf | 7 | w [w] | 0.1155 | 0.0606* | 7 |
| 180 | T180 | w→ws→c [c] | 0.1173→0.1173 | 0.0606* | 66 | w [w] | 0.1173 | inf | 8 | w [w] | 0.1173 | 0.0606* | 8 |
| 181 | T181 | w→ws→c [w] | 0.1178→0.1178 | 0.0606* | 63 | w [w] | 0.1178 | inf | 7 | w [w] | 0.1178 | 0.0606* | 7 |
| 182 | T182 | w→ws→c [c] | 0.1190→0.1190 | 0.0607* | 64 | w [w] | 0.1190 | inf | 8 | w [w] | 0.1190 | 0.0607* | 8 |
| 183 | T183 | w→ws→c [c] | 0.1207→0.1207 | 0.0608* | 64 | w [w] | 0.1207 | inf | 8 | w [w] | 0.1207 | 0.0608* | 8 |
| 184 | T184 | w→ws→c [c] | 0.1212→0.1212 | 0.0608* | 64 | w [w] | 0.1212 | inf | 7 | w [w] | 0.1212 | 0.0608* | 7 |
| 185 | T185 | w→ws→c [w] | 0.1228→0.1228 | 0.0608* | 65 | w [w] | 0.1228 | inf | 7 | w [w] | 0.1228 | 0.0608* | 7 |
| 186 | T186 | w→ws→c [c] | 0.2288→0.2288 | 0.0609* | 164 | w [w] | 0.2288 | inf | 29 | w [w] | 0.2288 | 0.0609* | 29 |
| 187 | T187 | w→ws→c [ws] | 0.2298→0.2298 | 0.0609* | 111 | w [w] | 0.2298 | inf | 18 | w [w] | 0.2298 | 0.0609* | 18 |
| 188 | T188 | w→ws→c [c] | 0.2306→0.2306 | 0.0609* | 120 | w [w] | 0.2306 | inf | 20 | w [w] | 0.2306 | 0.0609* | 20 |
| 189 | T189 | w→ws→c [ws] | 0.2303→0.2303 | 0.0610* | 118 | w [w] | 0.2303 | inf | 18 | w [w] | 0.2303 | 0.0610* | 18 |
| 190 | T190 | w→ws→c [w] | 0.2302→0.2302 | 0.0610* | 108 | w [w] | 0.2302 | inf | 15 | w [w] | 0.2302 | 0.0610* | 15 |
| 191 | T191 | w→ws→c [ws] | 0.2314→0.2314 | 0.0610* | 115 | w [w] | 0.2314 | inf | 18 | w [w] | 0.2314 | 0.0610* | 18 |
| 192 | T192 | w→ws→c [c] | 0.2305→0.2305 | 0.0610* | 112 | w [w] | 0.2305 | inf | 19 | w [w] | 0.2305 | 0.0610* | 19 |
| 193 | T193 | w→ws→c [c] | 0.2332→0.2332 | 0.0610* | 121 | w [w] | 0.2332 | inf | 19 | w [w] | 0.2332 | 0.0610* | 19 |
| 194 | T194 | w→ws→c [w] | 0.2327→0.2327 | 0.0610* | 108 | w [w] | 0.2327 | inf | 17 | w [w] | 0.2327 | 0.0610* | 17 |
| 195 | T195 | w→ws→c [c] | 0.2351→0.2351 | 0.0610* | 118 | w [w] | 0.2351 | inf | 20 | w [w] | 0.2351 | 0.0610* | 20 |
| 196 | T196 | w→ws→c [ws] | 0.2341→0.2341 | 0.0610* | 119 | w [w] | 0.2341 | inf | 18 | w [w] | 0.2341 | 0.0610* | 18 |
| 197 | T197 | w→ws→c [ws] | 0.2348→0.2348 | 0.0610* | 117 | w [w] | 0.2348 | inf | 18 | w [w] | 0.2348 | 0.0610* | 18 |
| 198 | T198 | w→ws→c [w] | 0.2367→0.2367 | 0.0611* | 113 | w [w] | 0.2367 | inf | 18 | w [w] | 0.2367 | 0.0611* | 18 |
| 199 | T199 | w→ws→c [c] | 0.2366→0.2366 | 0.0612* | 115 | w [w] | 0.2366 | inf | 18 | w [w] | 0.2366 | 0.0612* | 18 |
| 200 | T200 | w→ws→c [c] | 0.2364→0.2364 | 0.0612* | 112 | w [w] | 0.2364 | inf | 16 | w [w] | 0.2364 | 0.0612* | 16 |
| 201 | T201 | w→ws→c [ws] | 0.2378→0.2378 | 0.0612* | 119 | w [w] | 0.2378 | inf | 19 | w [w] | 0.2378 | 0.0612* | 19 |
| 202 | T202 | w→ws→c [w] | 0.2370→0.2370 | 0.0612* | 119 | w [w] | 0.2370 | inf | 17 | w [w] | 0.2370 | 0.0612* | 17 |
| 203 | T203 | w→ws→c [w] | 0.2391→0.2391 | 0.0613* | 118 | w [w] | 0.2391 | inf | 17 | w [w] | 0.2391 | 0.0613* | 17 |
| 204 | T204 | w→ws→c [ws] | 0.2388→0.2388 | 0.0613* | 117 | w [w] | 0.2388 | inf | 19 | w [w] | 0.2388 | 0.0613* | 19 |
| 205 | T205 | w→ws→c [c] | 0.2374→0.2374 | 0.0613* | 117 | w [w] | 0.2374 | inf | 19 | w [w] | 0.2374 | 0.0613* | 19 |
| 206 | T206 | w→ws→c [ws] | 0.2392→0.2392 | 0.0613* | 118 | w [w] | 0.2392 | inf | 19 | w [w] | 0.2392 | 0.0613* | 19 |
| 207 | T207 | w→ws→c [w] | 0.2414→0.2414 | 0.0613* | 121 | w [w] | 0.2414 | inf | 21 | w [w] | 0.2414 | 0.0613* | 21 |
| 208 | T208 | w→ws→c [ws] | 0.2406→0.2406 | 0.0613* | 114 | w [w] | 0.2406 | inf | 19 | w [w] | 0.2406 | 0.0613* | 19 |
| 209 | T209 | w→ws→c [ws] | 0.2397→0.2397 | 0.0613* | 111 | w [w] | 0.2397 | inf | 17 | w [w] | 0.2397 | 0.0613* | 17 |
| 210 | T210 | w→ws→c [c] | 0.2417→0.2417 | 0.0613* | 111 | w [w] | 0.2417 | inf | 18 | w [w] | 0.2417 | 0.0613* | 18 |
| 211 | T211 | w→ws→c [c] | 0.2419→0.2419 | 0.0613* | 116 | w [w] | 0.2419 | inf | 18 | w [w] | 0.2419 | 0.0613* | 18 |
| 212 | T212 | w→ws→c [c] | 0.2413→0.2413 | 0.0613* | 115 | w [w] | 0.2413 | inf | 20 | w [w] | 0.2413 | 0.0613* | 20 |
| 213 | T213 | w→ws→c [ws] | 0.2430→0.2430 | 0.0614* | 110 | w [w] | 0.2430 | inf | 16 | w [w] | 0.2430 | 0.0614* | 16 |
| 214 | T214 | w→ws→c [ws] | 0.2425→0.2425 | 0.0614* | 120 | w [w] | 0.2425 | inf | 19 | w [w] | 0.2425 | 0.0614* | 19 |
| 215 | T215 | w→ws→c [w] | 0.2449→0.2449 | 0.0614* | 119 | w [w] | 0.2449 | inf | 19 | w [w] | 0.2449 | 0.0614* | 19 |
| 216 | T216 | w→ws→c [ws] | 0.2445→0.2445 | 0.0614* | 114 | w [w] | 0.2445 | inf | 16 | w [w] | 0.2445 | 0.0614* | 16 |
| 217 | T217 | w→ws→c [ws] | 0.2450→0.2450 | 0.0614* | 110 | w [w] | 0.2450 | inf | 16 | w [w] | 0.2450 | 0.0614* | 16 |
| 218 | T218 | w→ws→c [c] | 0.2468→0.2468 | 0.0615* | 117 | w [w] | 0.2468 | inf | 20 | w [w] | 0.2468 | 0.0615* | 20 |
| 219 | T219 | w→ws→c [c] | 0.2466→0.2466 | 0.0615* | 118 | w [w] | 0.2466 | inf | 18 | w [w] | 0.2466 | 0.0615* | 18 |
| 220 | T220 | w→ws→c [c] | 0.2480→0.2480 | 0.0615* | 118 | w [w] | 0.2480 | inf | 17 | w [w] | 0.2480 | 0.0615* | 17 |
| 221 | T221 | w→ws→c [c] | 0.2461→0.2461 | 0.0616* | 113 | w [w] | 0.2461 | inf | 17 | w [w] | 0.2461 | 0.0616* | 17 |
| 222 | T222 | w→ws→c [c] | 0.2474→0.2474 | 0.0616* | 113 | w [w] | 0.2474 | inf | 18 | w [w] | 0.2474 | 0.0616* | 18 |
| 223 | T223 | w→ws→c [c] | 0.2474→0.2474 | 0.0616* | 117 | w [w] | 0.2474 | inf | 19 | w [w] | 0.2474 | 0.0616* | 19 |
| 224 | T224 | w→ws→c [ws] | 0.2481→0.2481 | 0.0616* | 110 | w [w] | 0.2481 | inf | 17 | w [w] | 0.2481 | 0.0616* | 17 |
| 225 | T225 | w→ws→c [w] | 0.2501→0.2501 | 0.0616* | 111 | w [w] | 0.2501 | inf | 16 | w [w] | 0.2501 | 0.0616* | 16 |
| 226 | T226 | w→ws→c [ws] | 0.2505→0.2505 | 0.0616* | 109 | w [w] | 0.2505 | inf | 16 | w [w] | 0.2505 | 0.0616* | 16 |
| 227 | T227 | w→ws→c [w] | 0.2495→0.2495 | 0.0616* | 115 | w [w] | 0.2495 | inf | 19 | w [w] | 0.2495 | 0.0616* | 19 |
| 228 | T228 | w→ws→c [c] | 0.2513→0.2513 | 0.0616* | 118 | w [w] | 0.2513 | inf | 19 | w [w] | 0.2513 | 0.0616* | 19 |
| 229 | T229 | w→ws→c [c] | 0.2501→0.2501 | 0.0617* | 113 | w [w] | 0.2501 | inf | 19 | w [w] | 0.2501 | 0.0617* | 19 |
| 230 | T230 | w→ws→c [ws] | 0.2515→0.2515 | 0.0617* | 107 | w [w] | 0.2515 | inf | 16 | w [w] | 0.2515 | 0.0617* | 16 |
| 231 | T231 | w→ws→c [c] | 0.2533→0.2533 | 0.0617* | 114 | w [w] | 0.2533 | inf | 19 | w [w] | 0.2533 | 0.0617* | 19 |
| 232 | T232 | w→ws→c [w] | 0.2530→0.2530 | 0.0617* | 117 | w [w] | 0.2530 | inf | 20 | w [w] | 0.2530 | 0.0617* | 20 |
| 233 | T233 | w→ws→c [ws] | 0.2531→0.2531 | 0.0617* | 111 | w [w] | 0.2531 | inf | 17 | w [w] | 0.2531 | 0.0617* | 17 |
| 234 | T234 | w→ws→c [c] | 0.2542→0.2542 | 0.0617* | 118 | w [w] | 0.2542 | inf | 20 | w [w] | 0.2542 | 0.0617* | 20 |
| 235 | T235 | w→ws→c [c] | 0.2537→0.2537 | 0.0617* | 115 | w [w] | 0.2537 | inf | 18 | w [w] | 0.2537 | 0.0617* | 18 |
| 236 | T236 | w→ws→c [ws] | 0.2551→0.2551 | 0.0618* | 112 | w [w] | 0.2551 | inf | 17 | w [w] | 0.2551 | 0.0618* | 17 |
| 237 | T237 | w→ws→c [c] | 0.2567→0.2567 | 0.0618* | 111 | w [w] | 0.2567 | inf | 19 | w [w] | 0.2567 | 0.0618* | 19 |
| 238 | T238 | w→ws→c [ws] | 0.2559→0.2559 | 0.0618* | 111 | w [w] | 0.2559 | inf | 18 | w [w] | 0.2559 | 0.0618* | 18 |
| 239 | T239 | w→ws→c [w] | 0.2567→0.2567 | 0.0618* | 107 | w [w] | 0.2567 | inf | 16 | w [w] | 0.2567 | 0.0618* | 16 |
| 240 | T240 | w→ws→c [ws] | 0.2571→0.2571 | 0.0619* | 114 | w [w] | 0.2571 | inf | 19 | w [w] | 0.2571 | 0.0619* | 19 |
| 241 | T241 | w→ws→c [c] | 0.2573→0.2573 | 0.0619* | 116 | w [w] | 0.2573 | inf | 18 | w [w] | 0.2573 | 0.0619* | 18 |
| 242 | T242 | w→ws→c [ws] | 0.2583→0.2583 | 0.0620* | 112 | w [w] | 0.2583 | inf | 19 | w [w] | 0.2583 | 0.0620* | 19 |
| 243 | T243 | w→ws→c [ws] | 0.2591→0.2591 | 0.0620* | 112 | w [w] | 0.2591 | inf | 18 | w [w] | 0.2591 | 0.0620* | 18 |
| 244 | T244 | w→ws→c [c] | 0.2599→0.2599 | 0.0620* | 116 | w [w] | 0.2599 | inf | 20 | w [w] | 0.2599 | 0.0620* | 20 |
| 245 | T245 | w→ws→c [c] | 0.2593→0.2593 | 0.0621* | 112 | w [w] | 0.2593 | inf | 17 | w [w] | 0.2593 | 0.0621* | 17 |
| 246 | T246 | w→ws→c [w] | 0.2591→0.2591 | 0.0621* | 115 | w [w] | 0.2591 | inf | 19 | w [w] | 0.2591 | 0.0621* | 19 |
| 247 | T247 | w→ws→c [w] | 0.2597→0.2597 | 0.0621* | 114 | w [w] | 0.2597 | inf | 18 | w [w] | 0.2597 | 0.0621* | 18 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off |
|---|---|---|---|
| 48 | — | — | — |
| 49 | — | — | — |
| 50 | — | — | — |
| 51 | — | — | — |
| 52 | — | — | — |
| 85 | — | — | — |
| 86 | — | — | — |
| 87 | FLOOR_HIT, P_UNC | FLOOR_HIT, P_UNC | FLOOR_HIT, P_UNC |
| 88 | — | — | — |
| 89 | — | — | — |
| 122 | — | — | — |
| 123 | — | — | — |
| 124 | — | — | — |
| 125 | — | — | — |
| 126 | — | — | — |
| 134 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 135 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 136 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 137 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 138 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 139 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 140 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 141 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 142 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 143 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 144 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 145 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 146 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 147 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 148 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 149 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 150 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 151 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 152 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 153 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 154 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 155 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 156 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 157 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 158 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 159 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 160 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 161 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 162 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 163 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 164 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 165 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 166 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 167 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 168 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 169 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 170 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 171 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 172 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 173 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 174 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 175 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 176 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 177 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 178 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 179 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 180 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 181 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 182 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 183 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 184 | S_RESEED, S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 185 | S_RWP_OUTLIER | — | S_RWP_OUTLIER |
| 186 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 187 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 188 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 189 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 190 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 191 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 192 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 193 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 194 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 195 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 196 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 197 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 198 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 199 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 200 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 201 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 202 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 203 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 204 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 205 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 206 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 207 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 208 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 209 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 210 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 211 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 212 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 213 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 214 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 215 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 216 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 217 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 218 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 219 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 220 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 221 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 222 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 223 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 224 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 225 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 226 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 227 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 228 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 229 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 230 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 231 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 232 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 233 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 234 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 235 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 236 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 237 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 238 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 239 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 240 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 241 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 242 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 243 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 244 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 245 | FLOOR_HIT, S_RESEED, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 246 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |
| 247 | FLOOR_HIT, S_RWP_OUTLIER | FLOOR_HIT | FLOOR_HIT, S_RWP_OUTLIER |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | on vs ref | status vs ref | off vs ref | on vs truth | status vs truth | off vs truth |
|---|---|---|---|---|---|---|---|---|
| 48 | 0 | 0 | 0.000475 (instrument.background.c3) | 0.000475 (instrument.background.c3) | 0.000475 (instrument.background.c3) | 2.7 (instrument.background.c0) | 2.7 (instrument.background.c0) | 2.7 (instrument.background.c0) |
| 49 | 0 | 0 | 0.000124 (instrument.background.c2) | 0.000124 (instrument.background.c2) | 0.000124 (instrument.background.c2) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) | 2.2 (instrument.background.c0) |
| 50 | 0 | 0 | 7.66e-05 (instrument.profile.y) | 7.66e-05 (instrument.profile.y) | 7.66e-05 (instrument.profile.y) | 0.971 (instrument.background.c0) | 0.971 (instrument.background.c0) | 0.971 (instrument.background.c0) |
| 51 | 0 | 0 | 0.000772 (instrument.profile.x) | 0.000772 (instrument.profile.x) | 0.000772 (instrument.profile.x) | 1.98 (instrument.background.c0) | 1.98 (instrument.background.c0) | 1.98 (instrument.background.c0) |
| 52 | 0 | 0 | 0.000237 (instrument.background.c2) | 0.000237 (instrument.background.c2) | 0.000237 (instrument.background.c2) | 2.63 (instrument.background.c0) | 2.63 (instrument.background.c0) | 2.63 (instrument.background.c0) |
| 85 | 0 | 0 | 0.000425 (instrument.profile.y) | 0.000425 (instrument.profile.y) | 0.000425 (instrument.profile.y) | 1.14 (instrument.zero_shift) | 1.14 (instrument.zero_shift) | 1.14 (instrument.zero_shift) |
| 86 | 0 | 0 | 0.000201 (instrument.profile.y) | 0.000201 (instrument.profile.y) | 0.000201 (instrument.profile.y) | 0.882 (phases.0.scale) | 0.882 (phases.0.scale) | 0.882 (phases.0.scale) |
| 87 | 0 | 0 | 2.13 (instrument.zero_shift) ≠2 no-esd (phases.0.cell.b, phases.0.cell.c) | 2.13 (instrument.zero_shift) ≠2 no-esd (phases.0.cell.b, phases.0.cell.c) | 2.13 (instrument.zero_shift) ≠2 no-esd (phases.0.cell.b, phases.0.cell.c) | 1.54 (instrument.background.c0) | 1.54 (instrument.background.c0) | 1.54 (instrument.background.c0) |
| 88 | 0 | 0 | 0.000165 (instrument.background.c2) | 0.000165 (instrument.background.c2) | 0.000165 (instrument.background.c2) | 0.828 (instrument.background.c0) | 0.828 (instrument.background.c0) | 0.828 (instrument.background.c0) |
| 89 | 0 | 0 | 0.000197 (instrument.background.c0) | 0.000197 (instrument.background.c0) | 0.000197 (instrument.background.c0) | 3.47 (instrument.background.c0) | 3.47 (instrument.background.c0) | 3.47 (instrument.background.c0) |
| 122 | 0 | 0 | 9.66e-05 (instrument.profile.y) | 9.66e-05 (instrument.profile.y) | 9.66e-05 (instrument.profile.y) | 1.87 (instrument.background.c0) | 1.87 (instrument.background.c0) | 1.87 (instrument.background.c0) |
| 123 | 0 | 0 | 0.00025 (instrument.profile.y) | 0.00025 (instrument.profile.y) | 0.00025 (instrument.profile.y) | 1.64 (instrument.background.c0) | 1.64 (instrument.background.c0) | 1.64 (instrument.background.c0) |
| 124 | 0 | 0 | 2.5e-07 (instrument.profile.u) | 2.5e-07 (instrument.profile.u) | 2.5e-07 (instrument.profile.u) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) |
| 125 | 0 | 0 | 0.000217 (instrument.profile.y) | 0.000217 (instrument.profile.y) | 0.000217 (instrument.profile.y) | 1.85 (instrument.background.c0) | 1.85 (instrument.background.c0) | 1.85 (instrument.background.c0) |
| 126 | 0 | 0 | 0.000137 (instrument.profile.y) | 0.000137 (instrument.profile.y) | 0.000137 (instrument.profile.y) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) | 2.12 (instrument.background.c0) |
| 134 | 0 | 0 | 5.86e-07 (instrument.profile.w) | 5.86e-07 (instrument.profile.w) | 5.86e-07 (instrument.profile.w) | 0.614 (instrument.profile.w) | 0.614 (instrument.profile.w) | 0.614 (instrument.profile.w) |
| 135 | 0.000238 (instrument.profile.y) | 0.000238 (instrument.profile.y) | 0 | 0.000238 (instrument.profile.y) | 0.000238 (instrument.profile.y) | 0.621 (phases.0.cell.a) | 0.621 (phases.0.cell.a) | 0.621 (phases.0.cell.a) |
| 136 | 1.34e-07 (instrument.profile.y) | 1.34e-07 (instrument.profile.y) | 1.62e-05 (instrument.background.c3) | 1.62e-05 (instrument.background.c3) | 1.62e-05 (instrument.background.c3) | 0.422 (instrument.background.c0) | 0.422 (instrument.background.c0) | 0.422 (instrument.background.c0) |
| 137 | 0.000129 (instrument.profile.y) | 0.000129 (instrument.profile.y) | 0 | 0.000129 (instrument.profile.y) | 0.000129 (instrument.profile.y) | 1.06 (phases.0.scale) | 1.06 (phases.0.scale) | 1.06 (phases.0.scale) |
| 138 | 2.31e-06 (instrument.background.c2) | 2.31e-06 (instrument.background.c2) | 0.00013 (instrument.profile.y) | 0.000131 (instrument.profile.y) | 0.000131 (instrument.profile.y) | 1.11 (instrument.background.c0) | 1.11 (instrument.background.c0) | 1.11 (instrument.background.c0) |
| 139 | 0.00026 (instrument.profile.x) | 0.00026 (instrument.profile.x) | 0.000268 (instrument.profile.x) | 4.32e-05 (instrument.background.c0) | 4.32e-05 (instrument.background.c0) | 0.371 (instrument.profile.w) | 0.371 (instrument.profile.w) | 0.371 (instrument.profile.w) |
| 140 | 0.000718 (instrument.profile.y) | 0.000718 (instrument.profile.y) | 0 | 0.000718 (instrument.profile.y) | 0.000718 (instrument.profile.y) | 0.989 (instrument.background.c0) | 0.989 (instrument.background.c0) | 0.989 (instrument.background.c0) |
| 141 | 1.04e-08 (instrument.profile.w) | 1.04e-08 (instrument.profile.w) | 0.000296 (instrument.profile.x) | 0.000296 (instrument.profile.x) | 0.000296 (instrument.profile.x) | 0.669 (instrument.background.c0) | 0.669 (instrument.background.c0) | 0.669 (instrument.background.c0) |
| 142 | 0.00067 (instrument.profile.y) | 0.00067 (instrument.profile.y) | 0 | 0.00067 (instrument.profile.y) | 0.00067 (instrument.profile.y) | 0.596 (instrument.background.c0) | 0.596 (instrument.background.c0) | 0.596 (instrument.background.c0) |
| 143 | 0.000118 (instrument.profile.y) | 0.000118 (instrument.profile.y) | 0 | 0.000118 (instrument.profile.y) | 0.000118 (instrument.profile.y) | 0.658 (phases.0.scale) | 0.658 (phases.0.scale) | 0.658 (phases.0.scale) |
| 144 | 6.95e-08 (instrument.profile.y) | 6.95e-08 (instrument.profile.y) | 6.56e-05 (instrument.profile.y) | 6.55e-05 (instrument.profile.y) | 6.55e-05 (instrument.profile.y) | 0.865 (instrument.background.c0) | 0.865 (instrument.background.c0) | 0.865 (instrument.background.c0) |
| 145 | 2.5e-06 (instrument.profile.w) | 2.5e-06 (instrument.profile.w) | 0.000794 (instrument.profile.y) | 0.000793 (instrument.profile.y) | 0.000793 (instrument.profile.y) | 0.413 (phases.0.scale) | 0.413 (phases.0.scale) | 0.413 (phases.0.scale) |
| 146 | 4.24e-05 (instrument.background.c2) | 4.24e-05 (instrument.background.c2) | 0 | 4.24e-05 (instrument.background.c2) | 4.24e-05 (instrument.background.c2) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) |
| 147 | 0.000346 (instrument.profile.y) | 0.000346 (instrument.profile.y) | 0 | 0.000346 (instrument.profile.y) | 0.000346 (instrument.profile.y) | 0.636 (phases.0.scale) | 0.636 (phases.0.scale) | 0.636 (phases.0.scale) |
| 148 | 1.56e-05 (instrument.background.c3) | 1.56e-05 (instrument.background.c3) | 0 | 1.56e-05 (instrument.background.c3) | 1.56e-05 (instrument.background.c3) | 0.671 (instrument.background.c0) | 0.671 (instrument.background.c0) | 0.671 (instrument.background.c0) |
| 149 | 0.00017 (instrument.profile.x) | 0.00017 (instrument.profile.x) | 0 | 0.00017 (instrument.profile.x) | 0.00017 (instrument.profile.x) | 0.321 (instrument.background.c0) | 0.321 (instrument.background.c0) | 0.321 (instrument.background.c0) |
| 150 | 2.42e-05 (instrument.background.c0) | 2.42e-05 (instrument.background.c0) | 0 | 2.42e-05 (instrument.background.c0) | 2.42e-05 (instrument.background.c0) | 0.822 (instrument.background.c0) | 0.822 (instrument.background.c0) | 0.822 (instrument.background.c0) |
| 151 | 6.35e-05 (instrument.profile.x) | 6.35e-05 (instrument.profile.x) | 0 | 6.35e-05 (instrument.profile.x) | 6.35e-05 (instrument.profile.x) | 0.793 (instrument.background.c0) | 0.793 (instrument.background.c0) | 0.793 (instrument.background.c0) |
| 152 | 8.99e-05 (instrument.profile.y) | 8.99e-05 (instrument.profile.y) | 0 | 8.99e-05 (instrument.profile.y) | 8.99e-05 (instrument.profile.y) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) |
| 153 | 1.17e-08 (instrument.profile.w) | 1.17e-08 (instrument.profile.w) | 4.67e-05 (instrument.profile.x) | 4.67e-05 (instrument.profile.x) | 4.67e-05 (instrument.profile.x) | 0.778 (instrument.background.c0) | 0.778 (instrument.background.c0) | 0.778 (instrument.background.c0) |
| 154 | 9.65e-08 (instrument.profile.w) | 9.65e-08 (instrument.profile.w) | 0 | 9.65e-08 (instrument.profile.w) | 9.65e-08 (instrument.profile.w) | 0.962 (instrument.background.c0) | 0.962 (instrument.background.c0) | 0.962 (instrument.background.c0) |
| 155 | 0.000643 (instrument.profile.y) | 0.000643 (instrument.profile.y) | 0 | 0.000643 (instrument.profile.y) | 0.000643 (instrument.profile.y) | 0.766 (instrument.background.c0) | 0.766 (instrument.background.c0) | 0.766 (instrument.background.c0) |
| 156 | 1.25e-08 (instrument.profile.w) | 1.25e-08 (instrument.profile.w) | 3.46e-05 (instrument.background.c2) | 3.46e-05 (instrument.background.c2) | 3.46e-05 (instrument.background.c2) | 0.593 (instrument.background.c0) | 0.593 (instrument.background.c0) | 0.593 (instrument.background.c0) |
| 157 | 5.68e-05 (instrument.background.c2) | 5.68e-05 (instrument.background.c2) | 0 | 5.68e-05 (instrument.background.c2) | 5.68e-05 (instrument.background.c2) | 0.935 (instrument.background.c0) | 0.935 (instrument.background.c0) | 0.935 (instrument.background.c0) |
| 158 | 7.8e-09 (instrument.profile.y) | 7.8e-09 (instrument.profile.y) | 6.82e-05 (instrument.profile.y) | 6.82e-05 (instrument.profile.y) | 6.82e-05 (instrument.profile.y) | 0.615 (phases.0.scale) | 0.615 (phases.0.scale) | 0.615 (phases.0.scale) |
| 159 | 7.28e-08 (instrument.profile.u) | 7.28e-08 (instrument.profile.u) | 1.65e-06 (instrument.background.c0) | 1.65e-06 (instrument.background.c0) | 1.65e-06 (instrument.background.c0) | 0.595 (instrument.background.c0) | 0.595 (instrument.background.c0) | 0.595 (instrument.background.c0) |
| 160 | 6.54e-08 (instrument.profile.v) | 6.54e-08 (instrument.profile.v) | 3.12e-05 (instrument.background.c3) | 3.12e-05 (instrument.background.c3) | 3.12e-05 (instrument.background.c3) | 0.747 (instrument.background.c0) | 0.747 (instrument.background.c0) | 0.747 (instrument.background.c0) |
| 161 | 1.63e-08 (instrument.profile.w) | 1.63e-08 (instrument.profile.w) | 3.02e-05 (instrument.profile.y) | 3.02e-05 (instrument.profile.y) | 3.02e-05 (instrument.profile.y) | 0.816 (instrument.background.c0) | 0.816 (instrument.background.c0) | 0.816 (instrument.background.c0) |
| 162 | 1.75e-08 (instrument.profile.x) | 1.75e-08 (instrument.profile.x) | 6.05e-05 (instrument.profile.x) | 6.06e-05 (instrument.profile.x) | 6.06e-05 (instrument.profile.x) | 0.726 (instrument.background.c0) | 0.726 (instrument.background.c0) | 0.726 (instrument.background.c0) |
| 163 | 1.16e-08 (instrument.profile.y) | 1.16e-08 (instrument.profile.y) | 0.000125 (instrument.profile.y) | 0.000125 (instrument.profile.y) | 0.000125 (instrument.profile.y) | 0.473 (instrument.background.c0) | 0.473 (instrument.background.c0) | 0.473 (instrument.background.c0) |
| 164 | 3.97e-06 (instrument.profile.y) | 3.97e-06 (instrument.profile.y) | 0 | 3.97e-06 (instrument.profile.y) | 3.97e-06 (instrument.profile.y) | 0.832 (instrument.background.c0) | 0.832 (instrument.background.c0) | 0.832 (instrument.background.c0) |
| 165 | 7.17e-07 (instrument.profile.v) | 7.17e-07 (instrument.profile.v) | 7.96e-05 (instrument.profile.y) | 7.94e-05 (instrument.profile.y) | 7.94e-05 (instrument.profile.y) | 0.805 (instrument.background.c0) | 0.805 (instrument.background.c0) | 0.805 (instrument.background.c0) |
| 166 | 1.91e-08 (instrument.profile.w) | 1.91e-08 (instrument.profile.w) | 6.53e-05 (instrument.profile.y) | 6.53e-05 (instrument.profile.y) | 6.53e-05 (instrument.profile.y) | 0.808 (instrument.background.c0) | 0.808 (instrument.background.c0) | 0.808 (instrument.background.c0) |
| 167 | 9.13e-09 (instrument.profile.v) | 9.13e-09 (instrument.profile.v) | 0.000539 (instrument.profile.y) | 0.000539 (instrument.profile.y) | 0.000539 (instrument.profile.y) | 0.771 (instrument.background.c0) | 0.771 (instrument.background.c0) | 0.771 (instrument.background.c0) |
| 168 | 1.32e-08 (instrument.profile.y) | 1.32e-08 (instrument.profile.y) | 0.000128 (instrument.profile.x) | 0.000128 (instrument.profile.x) | 0.000128 (instrument.profile.x) | 1.03 (instrument.background.c0) | 1.03 (instrument.background.c0) | 1.03 (instrument.background.c0) |
| 169 | 8.36e-05 (instrument.profile.y) | 8.36e-05 (instrument.profile.y) | 0 | 8.36e-05 (instrument.profile.y) | 8.36e-05 (instrument.profile.y) | 0.429 (instrument.background.c0) | 0.429 (instrument.background.c0) | 0.429 (instrument.background.c0) |
| 170 | 8.52e-09 (instrument.profile.v) | 8.52e-09 (instrument.profile.v) | 5.95e-05 (instrument.background.c0) | 5.95e-05 (instrument.background.c0) | 5.95e-05 (instrument.background.c0) | 0.848 (instrument.background.c0) | 0.848 (instrument.background.c0) | 0.848 (instrument.background.c0) |
| 171 | 7.4e-09 (instrument.profile.v) | 7.4e-09 (instrument.profile.v) | 3.85e-05 (instrument.profile.y) | 3.85e-05 (instrument.profile.y) | 3.85e-05 (instrument.profile.y) | 0.697 (instrument.background.c0) | 0.697 (instrument.background.c0) | 0.697 (instrument.background.c0) |
| 172 | 1.89e-07 (instrument.profile.w) | 1.89e-07 (instrument.profile.w) | 0.000391 (instrument.profile.x) | 0.000391 (instrument.profile.x) | 0.000391 (instrument.profile.x) | 0.633 (instrument.background.c0) | 0.633 (instrument.background.c0) | 0.633 (instrument.background.c0) |
| 173 | 2.69e-09 (instrument.profile.u) | 2.69e-09 (instrument.profile.u) | 0.00073 (instrument.profile.y) | 0.00073 (instrument.profile.y) | 0.00073 (instrument.profile.y) | 0.597 (instrument.background.c0) | 0.597 (instrument.background.c0) | 0.597 (instrument.background.c0) |
| 174 | 3.93e-09 (instrument.profile.y) | 3.93e-09 (instrument.profile.y) | 2.33e-05 (instrument.profile.y) | 2.33e-05 (instrument.profile.y) | 2.33e-05 (instrument.profile.y) | 1.04 (instrument.background.c0) | 1.04 (instrument.background.c0) | 1.04 (instrument.background.c0) |
| 175 | 0.000302 (instrument.profile.y) | 0.000302 (instrument.profile.y) | 0 | 0.000302 (instrument.profile.y) | 0.000302 (instrument.profile.y) | 0.81 (instrument.background.c0) | 0.809 (instrument.background.c0) | 0.809 (instrument.background.c0) |
| 176 | 3.37e-09 (instrument.profile.y) | 3.37e-09 (instrument.profile.y) | 1.46e-05 (instrument.background.c2) | 1.46e-05 (instrument.background.c2) | 1.46e-05 (instrument.background.c2) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) |
| 177 | 2.46e-05 (instrument.profile.y) | 2.46e-05 (instrument.profile.y) | 0 | 2.46e-05 (instrument.profile.y) | 2.46e-05 (instrument.profile.y) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) | 0.772 (instrument.background.c0) |
| 178 | 3.37e-09 (instrument.profile.u) | 3.37e-09 (instrument.profile.u) | 0.000121 (instrument.profile.x) | 0.000121 (instrument.profile.x) | 0.000121 (instrument.profile.x) | 0.795 (instrument.background.c0) | 0.795 (instrument.background.c0) | 0.795 (instrument.background.c0) |
| 179 | 1.14e-08 (instrument.profile.y) | 1.14e-08 (instrument.profile.y) | 0.000525 (instrument.profile.y) | 0.000525 (instrument.profile.y) | 0.000525 (instrument.profile.y) | 0.886 (instrument.background.c0) | 0.886 (instrument.background.c0) | 0.886 (instrument.background.c0) |
| 180 | 2.24e-08 (instrument.profile.y) | 2.24e-08 (instrument.profile.y) | 0 | 2.24e-08 (instrument.profile.y) | 2.24e-08 (instrument.profile.y) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) | 0.707 (instrument.background.c0) |
| 181 | 3.83e-08 (instrument.profile.v) | 3.83e-08 (instrument.profile.v) | 0.000566 (instrument.profile.y) | 0.000566 (instrument.profile.y) | 0.000566 (instrument.profile.y) | 0.713 (instrument.background.c0) | 0.713 (instrument.background.c0) | 0.713 (instrument.background.c0) |
| 182 | 3.03e-06 (instrument.profile.y) | 3.03e-06 (instrument.profile.y) | 0 | 3.03e-06 (instrument.profile.y) | 3.03e-06 (instrument.profile.y) | 0.878 (instrument.background.c0) | 0.878 (instrument.background.c0) | 0.878 (instrument.background.c0) |
| 183 | 0.00012 (instrument.profile.x) | 0.00012 (instrument.profile.x) | 0 | 0.00012 (instrument.profile.x) | 0.00012 (instrument.profile.x) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) | 0.692 (instrument.background.c0) |
| 184 | 1.06e-05 (instrument.profile.y) | 1.06e-05 (instrument.profile.y) | 0 | 1.06e-05 (instrument.profile.y) | 1.06e-05 (instrument.profile.y) | 0.786 (instrument.background.c0) | 0.786 (instrument.background.c0) | 0.786 (instrument.background.c0) |
| 185 | 4.32e-09 (instrument.profile.y) | 4.32e-09 (instrument.profile.y) | 3.21e-05 (instrument.background.c0) | 3.21e-05 (instrument.background.c0) | 3.21e-05 (instrument.background.c0) | 0.807 (instrument.background.c0) | 0.807 (instrument.background.c0) | 0.807 (instrument.background.c0) |
| 186 | 7.44e-05 (phases.0.scale) | 7.44e-05 (phases.0.scale) | 0 | 7.44e-05 (phases.0.scale) | 7.44e-05 (phases.0.scale) | 5.4 (phases.0.scale) | 5.4 (phases.0.scale) | 5.4 (phases.0.scale) |
| 187 | 9.23e-05 (phases.0.scale) | 9.23e-05 (phases.0.scale) | 9.31e-05 (phases.0.scale) | 9.33e-07 (instrument.profile.u) | 9.33e-07 (instrument.profile.u) | 5.35 (phases.0.scale) | 5.35 (phases.0.scale) | 5.35 (phases.0.scale) |
| 188 | 0.000246 (phases.0.scale) | 0.000246 (phases.0.scale) | 0 | 0.000246 (phases.0.scale) | 0.000246 (phases.0.scale) | 5.3 (phases.0.scale) | 5.3 (phases.0.scale) | 5.3 (phases.0.scale) |
| 189 | 0.000153 (phases.0.scale) | 0.000153 (phases.0.scale) | 0.000181 (phases.0.scale) | 3.76e-05 (instrument.background.c0) | 3.76e-05 (instrument.background.c0) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) |
| 190 | 1.1e-07 (phases.0.cell.a) | 1.1e-07 (phases.0.cell.a) | 5.56e-05 (phases.0.scale) | 5.56e-05 (phases.0.scale) | 5.56e-05 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) |
| 191 | 3.49e-05 (phases.0.cell.a) | 3.49e-05 (phases.0.cell.a) | 5.79e-05 (phases.0.cell.a) | 5.15e-05 (phases.0.scale) | 5.15e-05 (phases.0.scale) | 5.24 (phases.0.scale) | 5.24 (phases.0.scale) | 5.24 (phases.0.scale) |
| 192 | 6.92e-05 (phases.0.scale) | 6.92e-05 (phases.0.scale) | 0 | 6.92e-05 (phases.0.scale) | 6.92e-05 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) |
| 193 | 6.11e-05 (phases.0.scale) | 6.11e-05 (phases.0.scale) | 0 | 6.11e-05 (phases.0.scale) | 6.11e-05 (phases.0.scale) | 5.39 (phases.0.scale) | 5.39 (phases.0.scale) | 5.39 (phases.0.scale) |
| 194 | 2.97e-08 (phases.0.cell.a) | 2.97e-08 (phases.0.cell.a) | 4.51e-05 (instrument.background.c0) | 4.51e-05 (instrument.background.c0) | 4.51e-05 (instrument.background.c0) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) | 5.29 (phases.0.scale) |
| 195 | 0.000239 (phases.0.scale) | 0.000239 (phases.0.scale) | 0 | 0.000239 (phases.0.scale) | 0.000239 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) |
| 196 | 4.17e-06 (instrument.background.c0) | 4.17e-06 (instrument.background.c0) | 0.000323 (phases.0.scale) | 0.000321 (phases.0.scale) | 0.000321 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) |
| 197 | 0.000241 (phases.0.scale) | 0.000241 (phases.0.scale) | 0.000255 (phases.0.scale) | 1.35e-05 (phases.0.scale) | 1.35e-05 (phases.0.scale) | 5.23 (phases.0.scale) | 5.23 (phases.0.scale) | 5.23 (phases.0.scale) |
| 198 | 2.93e-08 (phases.0.cell.a) | 2.93e-08 (phases.0.cell.a) | 4.28e-05 (phases.0.scale) | 4.28e-05 (phases.0.scale) | 4.28e-05 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) | 5.22 (phases.0.scale) |
| 199 | 3.51e-05 (phases.0.scale) | 3.51e-05 (phases.0.scale) | 0 | 3.51e-05 (phases.0.scale) | 3.51e-05 (phases.0.scale) | 5.28 (phases.0.scale) | 5.28 (phases.0.scale) | 5.28 (phases.0.scale) |
| 200 | 7.11e-05 (phases.0.cell.a) | 7.11e-05 (phases.0.cell.a) | 0 | 7.11e-05 (phases.0.cell.a) | 7.11e-05 (phases.0.cell.a) | 5.05 (phases.0.scale) | 5.05 (phases.0.scale) | 5.05 (phases.0.scale) |
| 201 | 6.07e-05 (phases.0.scale) | 6.07e-05 (phases.0.scale) | 3.38e-05 (phases.0.cell.a) | 5.49e-05 (phases.0.scale) | 5.49e-05 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) | 5.2 (phases.0.scale) |
| 202 | 3.88e-05 (phases.0.scale) | 3.88e-05 (phases.0.scale) | 0.000164 (phases.0.scale) | 0.000125 (phases.0.scale) | 0.000125 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) |
| 203 | 1.16e-08 (phases.0.scale) | 1.16e-08 (phases.0.scale) | 8.98e-05 (phases.0.cell.a) | 8.98e-05 (phases.0.cell.a) | 8.98e-05 (phases.0.cell.a) | 5.17 (phases.0.scale) | 5.17 (phases.0.scale) | 5.17 (phases.0.scale) |
| 204 | 4.58e-06 (phases.0.cell.a) | 4.58e-06 (phases.0.cell.a) | 6.59e-05 (phases.0.scale) | 6.42e-05 (phases.0.scale) | 6.42e-05 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) | 5.04 (phases.0.scale) |
| 205 | 4.88e-05 (instrument.background.c0) | 4.88e-05 (instrument.background.c0) | 0 | 4.88e-05 (instrument.background.c0) | 4.88e-05 (instrument.background.c0) | 4.95 (phases.0.scale) | 4.95 (phases.0.scale) | 4.95 (phases.0.scale) |
| 206 | 3.07e-05 (phases.0.scale) | 3.07e-05 (phases.0.scale) | 5.99e-05 (phases.0.cell.a) | 5.32e-05 (phases.0.cell.a) | 5.32e-05 (phases.0.cell.a) | 4.92 (phases.0.scale) | 4.92 (phases.0.scale) | 4.92 (phases.0.scale) |
| 207 | 4.65e-09 (instrument.profile.u) | 4.65e-09 (instrument.profile.u) | 7.14e-05 (phases.0.scale) | 7.14e-05 (phases.0.scale) | 7.14e-05 (phases.0.scale) | 4.96 (phases.0.scale) | 4.96 (phases.0.scale) | 4.96 (phases.0.scale) |
| 208 | 1.25e-05 (phases.0.scale) | 1.25e-05 (phases.0.scale) | 6.89e-06 (phases.0.cell.a) | 1.32e-05 (phases.0.cell.a) | 1.32e-05 (phases.0.cell.a) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) | 4.93 (phases.0.scale) |
| 209 | 1.48e-05 (instrument.background.c0) | 1.48e-05 (instrument.background.c0) | 2.17e-05 (instrument.background.c0) | 1.12e-05 (phases.0.cell.a) | 1.12e-05 (phases.0.cell.a) | 4.86 (phases.0.scale) | 4.86 (phases.0.scale) | 4.86 (phases.0.scale) |
| 210 | 0.000101 (phases.0.scale) | 0.000101 (phases.0.scale) | 0 | 0.000101 (phases.0.scale) | 0.000101 (phases.0.scale) | 4.83 (phases.0.scale) | 4.83 (phases.0.scale) | 4.83 (phases.0.scale) |
| 211 | 3.94e-05 (phases.0.cell.a) | 3.94e-05 (phases.0.cell.a) | 0 | 3.94e-05 (phases.0.cell.a) | 3.94e-05 (phases.0.cell.a) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) |
| 212 | 7.4e-05 (phases.0.scale) | 7.4e-05 (phases.0.scale) | 0 | 7.4e-05 (phases.0.scale) | 7.4e-05 (phases.0.scale) | 5.02 (phases.0.scale) | 5.02 (phases.0.scale) | 5.02 (phases.0.scale) |
| 213 | 5.76e-05 (phases.0.scale) | 5.76e-05 (phases.0.scale) | 6.19e-05 (phases.0.cell.a) | 7.09e-05 (phases.0.cell.a) | 7.09e-05 (phases.0.cell.a) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) | 4.87 (phases.0.scale) |
| 214 | 8.39e-06 (phases.0.cell.a) | 8.39e-06 (phases.0.cell.a) | 1.57e-05 (phases.0.cell.a) | 2.41e-05 (phases.0.cell.a) | 2.41e-05 (phases.0.cell.a) | 4.8 (phases.0.scale) | 4.8 (phases.0.scale) | 4.8 (phases.0.scale) |
| 215 | 2.07e-08 (phases.0.scale) | 2.07e-08 (phases.0.scale) | 5.05e-05 (phases.0.cell.a) | 5.05e-05 (phases.0.cell.a) | 5.05e-05 (phases.0.cell.a) | 4.89 (phases.0.scale) | 4.89 (phases.0.scale) | 4.89 (phases.0.scale) |
| 216 | 1.94e-05 (phases.0.cell.a) | 1.94e-05 (phases.0.cell.a) | 6.89e-05 (phases.0.scale) | 7.23e-05 (phases.0.scale) | 7.23e-05 (phases.0.scale) | 4.88 (phases.0.scale) | 4.88 (phases.0.scale) | 4.88 (phases.0.scale) |
| 217 | 2.18e-07 (phases.0.cell.a) | 2.18e-07 (phases.0.cell.a) | 5.17e-05 (phases.0.cell.a) | 5.15e-05 (phases.0.cell.a) | 5.15e-05 (phases.0.cell.a) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) |
| 218 | 0.000114 (phases.0.scale) | 0.000114 (phases.0.scale) | 0 | 0.000114 (phases.0.scale) | 0.000114 (phases.0.scale) | 4.79 (phases.0.scale) | 4.79 (phases.0.scale) | 4.79 (phases.0.scale) |
| 219 | 5.36e-05 (phases.0.scale) | 5.36e-05 (phases.0.scale) | 0 | 5.36e-05 (phases.0.scale) | 5.36e-05 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) | 4.76 (phases.0.scale) |
| 220 | 9.98e-06 (phases.0.cell.a) | 9.98e-06 (phases.0.cell.a) | 0 | 9.98e-06 (phases.0.cell.a) | 9.98e-06 (phases.0.cell.a) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) |
| 221 | 6.98e-05 (instrument.background.c0) | 6.98e-05 (instrument.background.c0) | 0 | 6.98e-05 (instrument.background.c0) | 6.98e-05 (instrument.background.c0) | 4.84 (phases.0.scale) | 4.84 (phases.0.scale) | 4.84 (phases.0.scale) |
| 222 | 2.05e-05 (instrument.background.c2) | 2.05e-05 (instrument.background.c2) | 0 | 2.05e-05 (instrument.background.c2) | 2.05e-05 (instrument.background.c2) | 4.71 (phases.0.scale) | 4.71 (phases.0.scale) | 4.71 (phases.0.scale) |
| 223 | 3.38e-05 (instrument.background.c2) | 3.38e-05 (instrument.background.c2) | 0 | 3.38e-05 (instrument.background.c2) | 3.38e-05 (instrument.background.c2) | 4.61 (phases.0.scale) | 4.61 (phases.0.scale) | 4.61 (phases.0.scale) |
| 224 | 7.32e-05 (phases.0.scale) | 7.32e-05 (phases.0.scale) | 8.2e-05 (phases.0.scale) | 8.84e-06 (phases.0.scale) | 8.84e-06 (phases.0.scale) | 4.67 (phases.0.scale) | 4.67 (phases.0.scale) | 4.67 (phases.0.scale) |
| 225 | 4.21e-05 (phases.0.scale) | 4.21e-05 (phases.0.scale) | 4.14e-05 (phases.0.scale) | 8.35e-06 (phases.0.cell.a) | 8.35e-06 (phases.0.cell.a) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) |
| 226 | 8.02e-06 (phases.0.scale) | 8.02e-06 (phases.0.scale) | 5.25e-06 (phases.0.cell.a) | 7.02e-06 (phases.0.scale) | 7.02e-06 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) | 4.77 (phases.0.scale) |
| 227 | 8.93e-09 (phases.0.cell.a) | 8.93e-09 (phases.0.cell.a) | 2.25e-05 (phases.0.cell.a) | 2.25e-05 (phases.0.cell.a) | 2.25e-05 (phases.0.cell.a) | 4.65 (phases.0.scale) | 4.65 (phases.0.scale) | 4.65 (phases.0.scale) |
| 228 | 6.95e-05 (phases.0.scale) | 6.95e-05 (phases.0.scale) | 0 | 6.95e-05 (phases.0.scale) | 6.95e-05 (phases.0.scale) | 4.78 (phases.0.scale) | 4.78 (phases.0.scale) | 4.78 (phases.0.scale) |
| 229 | 3.56e-06 (phases.0.cell.a) | 3.56e-06 (phases.0.cell.a) | 0 | 3.56e-06 (phases.0.cell.a) | 3.56e-06 (phases.0.cell.a) | 4.62 (phases.0.scale) | 4.62 (phases.0.scale) | 4.62 (phases.0.scale) |
| 230 | 1.08e-05 (phases.0.scale) | 1.08e-05 (phases.0.scale) | 1.91e-05 (phases.0.cell.a) | 1.41e-05 (phases.0.cell.a) | 1.41e-05 (phases.0.cell.a) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) |
| 231 | 4.6e-05 (phases.0.cell.a) | 4.6e-05 (phases.0.cell.a) | 0 | 4.6e-05 (phases.0.cell.a) | 4.6e-05 (phases.0.cell.a) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) |
| 232 | 8.73e-09 (phases.0.cell.a) | 8.73e-09 (phases.0.cell.a) | 3.44e-05 (phases.0.cell.a) | 3.44e-05 (phases.0.cell.a) | 3.44e-05 (phases.0.cell.a) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) |
| 233 | 0.000161 (phases.0.scale) | 0.000161 (phases.0.scale) | 9.02e-05 (phases.0.scale) | 7.04e-05 (phases.0.scale) | 7.04e-05 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) |
| 234 | 7.34e-05 (phases.0.cell.a) | 7.34e-05 (phases.0.cell.a) | 0 | 7.34e-05 (phases.0.cell.a) | 7.34e-05 (phases.0.cell.a) | 4.56 (phases.0.scale) | 4.56 (phases.0.scale) | 4.56 (phases.0.scale) |
| 235 | 7.95e-05 (phases.0.scale) | 7.95e-05 (phases.0.scale) | 0 | 7.95e-05 (phases.0.scale) | 7.95e-05 (phases.0.scale) | 4.64 (phases.0.scale) | 4.64 (phases.0.scale) | 4.64 (phases.0.scale) |
| 236 | 0.000132 (phases.0.scale) | 0.000132 (phases.0.scale) | 0.000165 (phases.0.scale) | 6.13e-05 (phases.0.cell.a) | 6.13e-05 (phases.0.cell.a) | 4.54 (phases.0.scale) | 4.54 (phases.0.scale) | 4.54 (phases.0.scale) |
| 237 | 5.76e-05 (phases.0.scale) | 5.76e-05 (phases.0.scale) | 0 | 5.76e-05 (phases.0.scale) | 5.76e-05 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) | 4.53 (phases.0.scale) |
| 238 | 5.16e-05 (phases.0.scale) | 5.16e-05 (phases.0.scale) | 5.03e-05 (instrument.background.c0) | 7.41e-05 (phases.0.cell.a) | 7.41e-05 (phases.0.cell.a) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) | 4.63 (phases.0.scale) |
| 239 | 2.17e-08 (phases.0.scale) | 2.17e-08 (phases.0.scale) | 0.000132 (phases.0.scale) | 0.000132 (phases.0.scale) | 0.000132 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) | 4.55 (phases.0.scale) |
| 240 | 3.15e-05 (instrument.background.c2) | 3.15e-05 (instrument.background.c2) | 3.62e-05 (instrument.background.c2) | 4.56e-05 (phases.0.cell.a) | 4.56e-05 (phases.0.cell.a) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) |
| 241 | 4.34e-05 (phases.0.scale) | 4.34e-05 (phases.0.scale) | 0 | 4.34e-05 (phases.0.scale) | 4.34e-05 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) |
| 242 | 0.000123 (phases.0.scale) | 0.000123 (phases.0.scale) | 5.61e-05 (phases.0.scale) | 6.85e-05 (phases.0.cell.a) | 6.85e-05 (phases.0.cell.a) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) |
| 243 | 3e-05 (phases.0.cell.a) | 3e-05 (phases.0.cell.a) | 1.02e-05 (phases.0.cell.a) | 4.02e-05 (phases.0.cell.a) | 4.02e-05 (phases.0.cell.a) | 4.49 (phases.0.scale) | 4.49 (phases.0.scale) | 4.49 (phases.0.scale) |
| 244 | 7.85e-05 (phases.0.scale) | 7.85e-05 (phases.0.scale) | 0 | 7.85e-05 (phases.0.scale) | 7.85e-05 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) | 4.43 (phases.0.scale) |
| 245 | 4.94e-05 (phases.0.scale) | 4.94e-05 (phases.0.scale) | 0 | 4.94e-05 (phases.0.scale) | 4.94e-05 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) | 4.5 (phases.0.scale) |
| 246 | 8.54e-09 (phases.0.scale) | 8.54e-09 (phases.0.scale) | 4.66e-05 (phases.0.scale) | 4.65e-05 (phases.0.scale) | 4.65e-05 (phases.0.scale) | 4.18 (phases.0.scale) | 4.18 (phases.0.scale) | 4.18 (phases.0.scale) |
| 247 | 3.73e-09 (instrument.zero_shift) | 3.73e-09 (instrument.zero_shift) | 0.000164 (phases.0.scale) | 0.000164 (phases.0.scale) | 0.000164 (phases.0.scale) | 4.37 (phases.0.scale) | 4.37 (phases.0.scale) | 4.37 (phases.0.scale) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference; truth the simulation.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | ref | truth |
|---|---|---|---|---|---|---|
| 48 | `phases.0.cell.a` | 3.969078(33) | 3.969078(33) | 3.969078(33) | 3.969078(33) | 3.96909 |
| 48 | `phases.0.scale` | 0.00020045(45) | 0.00020045(45) | 0.00020045(45) | 0.00020045(45) | 0.0002 |
| 48 | `instrument.zero_shift` | 0.00592(10) | 0.00592(10) | 0.00592(10) | 0.00592(10) | 0.006 |
| 48 | `instrument.profile.w` | 0.000951(57) | 0.000951(57) | 0.000951(57) | 0.000951(57) | 0.001 |
| 48 | `instrument.background.c0` | 298.81(44) | 298.81(44) | 298.81(44) | 298.81(44) | 300 |
| 49 | `phases.0.cell.a` | 3.968987(33) | 3.968987(33) | 3.968987(33) | 3.968987(33) | 3.969 |
| 49 | `phases.0.scale` | 0.00019987(45) | 0.00019987(45) | 0.00019987(45) | 0.00019987(45) | 0.0002 |
| 49 | `instrument.zero_shift` | 0.00599(11) | 0.00599(11) | 0.00599(11) | 0.00599(11) | 0.006 |
| 49 | `instrument.profile.w` | 0.001005(58) | 0.001005(58) | 0.001005(58) | 0.001005(58) | 0.001 |
| 49 | `instrument.background.c0` | 299.02(44) | 299.02(44) | 299.02(44) | 299.02(44) | 300 |
| 50 | `phases.0.cell.a` | 3.968872(34) | 3.968872(34) | 3.968872(34) | 3.968872(34) | 3.9689 |
| 50 | `phases.0.scale` | 0.00019995(47) | 0.00019995(47) | 0.00019995(47) | 0.00019995(47) | 0.0002 |
| 50 | `instrument.zero_shift` | 0.00592(11) | 0.00592(11) | 0.00592(11) | 0.00592(11) | 0.006 |
| 50 | `instrument.profile.w` | 0.000953(60) | 0.000953(60) | 0.000953(60) | 0.000953(60) | 0.001 |
| 50 | `instrument.background.c0` | 449.48(53) | 449.48(53) | 449.48(53) | 449.48(53) | 450 |
| 51 | `phases.0.cell.a` | 3.968777(35) | 3.968777(35) | 3.968777(35) | 3.968777(35) | 3.96881 |
| 51 | `phases.0.scale` | 0.00020017(49) | 0.00020017(49) | 0.00020017(49) | 0.00020017(49) | 0.0002 |
| 51 | `instrument.zero_shift` | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.00587(11) | 0.006 |
| 51 | `instrument.profile.w` | 0.001022(62) | 0.001022(62) | 0.001022(62) | 0.001022(62) | 0.001 |
| 51 | `instrument.background.c0` | 448.91(55) | 448.91(55) | 448.91(55) | 448.91(55) | 450 |
| 52 | `phases.0.cell.a` | 3.968736(35) | 3.968736(35) | 3.968736(35) | 3.968736(35) | 3.96871 |
| 52 | `phases.0.scale` | 0.00020009(48) | 0.00020009(48) | 0.00020009(48) | 0.00020009(48) | 0.0002 |
| 52 | `instrument.zero_shift` | 0.00608(11) | 0.00608(11) | 0.00608(11) | 0.00608(11) | 0.006 |
| 52 | `instrument.profile.w` | 0.001065(61) | 0.001065(61) | 0.001065(61) | 0.001065(61) | 0.001 |
| 52 | `instrument.background.c0` | 448.57(54) | 448.57(54) | 448.57(54) | 448.57(54) | 450 |
| 85 | `phases.0.cell.a` | 3.965517(34) | 3.965517(34) | 3.965517(34) | 3.965517(34) | 3.96554 |
| 85 | `phases.0.scale` | 0.00020008(47) | 0.00020008(47) | 0.00020008(47) | 0.00020008(47) | 0.0002 |
| 85 | `instrument.zero_shift` | 0.00588(11) | 0.00588(11) | 0.00588(11) | 0.00588(11) | 0.006 |
| 85 | `instrument.profile.w` | 0.000989(59) | 0.000989(59) | 0.000989(59) | 0.000989(59) | 0.001 |
| 85 | `instrument.background.c0` | 449.47(53) | 449.47(53) | 449.47(53) | 449.47(53) | 450 |
| 86 | `phases.0.cell.a` | 3.965447(34) | 3.965447(34) | 3.965447(34) | 3.965447(34) | 3.96545 |
| 86 | `phases.0.scale` | 0.00020042(48) | 0.00020042(48) | 0.00020042(48) | 0.00020042(48) | 0.0002 |
| 86 | `instrument.zero_shift` | 0.00597(11) | 0.00597(11) | 0.00597(11) | 0.00597(11) | 0.006 |
| 86 | `instrument.profile.w` | 0.000960(60) | 0.000960(60) | 0.000960(60) | 0.000960(60) | 0.001 |
| 86 | `instrument.background.c0` | 449.58(54) | 449.58(54) | 449.58(54) | 449.58(54) | 450 |
| 87 | `phases.0.cell.a` | — | — | — | — | 3.96535 |
| 87 | `phases.0.scale` | 0.000000000(93) | 0.000000000(93) | 0.000000000(93) | 0.000000047(91) | 0 |
| 87 | `instrument.zero_shift` | 0.00597089 | 0.00597089 | 0.00597089 | 0.0117(27) | 0.006 |
| 87 | `instrument.profile.w` | 0.000960163 | 0.000960163 | 0.000960163 | 0.0014(63) | 0.001 |
| 87 | `instrument.background.c0` | 449.17(53) | 449.17(53) | 449.17(53) | 449.15(53) | 450 |
| 88 | `phases.0.cell.a` | 3.965228(35) | 3.965228(35) | 3.965228(35) | 3.965228(35) | 3.96526 |
| 88 | `phases.0.scale` | 0.00019975(48) | 0.00019975(48) | 0.00019975(48) | 0.00019975(48) | 0.0002 |
| 88 | `instrument.zero_shift` | 0.00594(11) | 0.00594(11) | 0.00594(11) | 0.00594(11) | 0.006 |
| 88 | `instrument.profile.w` | 0.000956(61) | 0.000956(61) | 0.000956(61) | 0.000956(61) | 0.001 |
| 88 | `instrument.background.c0` | 449.55(54) | 449.55(54) | 449.55(54) | 449.55(54) | 450 |
| 89 | `phases.0.cell.a` | 3.965185(34) | 3.965185(34) | 3.965185(34) | 3.965185(34) | 3.96516 |
| 89 | `phases.0.scale` | 0.00020012(48) | 0.00020012(48) | 0.00020012(48) | 0.00020012(48) | 0.0002 |
| 89 | `instrument.zero_shift` | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.006 |
| 89 | `instrument.profile.w` | 0.000939(60) | 0.000939(60) | 0.000939(60) | 0.000939(60) | 0.001 |
| 89 | `instrument.background.c0` | 448.15(53) | 448.15(53) | 448.15(53) | 448.15(53) | 450 |
| 122 | `phases.0.cell.a` | 3.962006(34) | 3.962006(34) | 3.962006(34) | 3.962006(34) | 3.96199 |
| 122 | `phases.0.scale` | 0.00019989(47) | 0.00019989(47) | 0.00019989(47) | 0.00019989(47) | 0.0002 |
| 122 | `instrument.zero_shift` | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.00604(11) | 0.006 |
| 122 | `instrument.profile.w` | 0.000978(59) | 0.000978(59) | 0.000978(59) | 0.000978(59) | 0.001 |
| 122 | `instrument.background.c0` | 449.01(53) | 449.01(53) | 449.01(53) | 449.01(53) | 450 |
| 123 | `phases.0.cell.a` | 3.961940(34) | 3.961940(34) | 3.961940(34) | 3.961940(34) | 3.9619 |
| 123 | `phases.0.scale` | 0.00019990(47) | 0.00019990(47) | 0.00019990(47) | 0.00019990(47) | 0.0002 |
| 123 | `instrument.zero_shift` | 0.00612(11) | 0.00612(11) | 0.00612(11) | 0.00612(11) | 0.006 |
| 123 | `instrument.profile.w` | 0.000903(60) | 0.000903(60) | 0.000903(60) | 0.000903(60) | 0.001 |
| 123 | `instrument.background.c0` | 449.13(53) | 449.13(53) | 449.13(53) | 449.13(53) | 450 |
| 124 | `phases.0.cell.a` | 3.961830(35) | 3.961830(35) | 3.961830(35) | 3.961830(35) | 3.9618 |
| 124 | `phases.0.scale` | 0.00020070(49) | 0.00020070(49) | 0.00020070(49) | 0.00020070(49) | 0.0002 |
| 124 | `instrument.zero_shift` | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.00610(11) | 0.006 |
| 124 | `instrument.profile.w` | 0.001104(62) | 0.001104(62) | 0.001104(62) | 0.001104(62) | 0.001 |
| 124 | `instrument.background.c0` | 448.84(55) | 448.84(55) | 448.84(55) | 448.84(55) | 450 |
| 125 | `phases.0.cell.a` | 3.961669(37) | 3.961669(37) | 3.961669(37) | 3.961669(37) | 3.96171 |
| 125 | `phases.0.scale` | 0.00019989(52) | 0.00019989(52) | 0.00019989(52) | 0.00019989(52) | 0.0002 |
| 125 | `instrument.zero_shift` | 0.00591(12) | 0.00591(12) | 0.00591(12) | 0.00591(12) | 0.006 |
| 125 | `instrument.profile.w` | 0.001098(66) | 0.001098(66) | 0.001098(66) | 0.001098(66) | 0.001 |
| 125 | `instrument.background.c0` | 448.92(58) | 448.92(58) | 448.92(58) | 448.92(58) | 450 |
| 126 | `phases.0.cell.a` | 3.961629(39) | 3.961629(39) | 3.961629(39) | 3.961629(39) | 3.96161 |
| 126 | `phases.0.scale` | 0.00020039(54) | 0.00020039(54) | 0.00020039(54) | 0.00020039(54) | 0.0002 |
| 126 | `instrument.zero_shift` | 0.00602(12) | 0.00602(12) | 0.00602(12) | 0.00602(12) | 0.006 |
| 126 | `instrument.profile.w` | 0.001000(69) | 0.001000(69) | 0.001000(69) | 0.001000(69) | 0.001 |
| 126 | `instrument.background.c0` | 448.72(61) | 448.72(61) | 448.72(61) | 448.72(61) | 450 |
| 184 | `phases.0.cell.a` | 3.95605(26) | 3.95605(26) | 3.95605(26) | 3.95605(26) | 3.95604 |
| 184 | `phases.0.scale` | 0.0001984(36) | 0.0001984(36) | 0.0001984(36) | 0.0001984(36) | 0.0002 |
| 184 | `instrument.zero_shift` | 0.00597(81) | 0.00597(81) | 0.00597(81) | 0.00597(81) | 0.006 |
| 184 | `instrument.profile.w` | 0.00100(45) | 0.00100(45) | 0.00100(45) | 0.00100(45) | 0.001 |
| 184 | `instrument.background.c0` | 453.1(40) | 453.1(40) | 453.1(40) | 453.1(40) | 450 |
| 185 | `phases.0.cell.a` | 3.95590(27) | 3.95590(27) | 3.95590(27) | 3.95590(27) | 3.95595 |
| 185 | `phases.0.scale` | 0.0001990(37) | 0.0001990(37) | 0.0001990(37) | 0.0001990(37) | 0.0002 |
| 185 | `instrument.zero_shift` | 0.00583(84) | 0.00583(84) | 0.00583(84) | 0.00583(84) | 0.006 |
| 185 | `instrument.profile.w` | 0.00089(47) | 0.00089(47) | 0.00089(47) | 0.00089(47) | 0.001 |
| 185 | `instrument.background.c0` | 453.3(41) | 453.3(41) | 453.3(41) | 453.3(41) | 450 |
| 186 | `phases.0.cell.a` | 3.95296(98) | 3.95296(98) | 3.95296(98) | 3.95296(98) | — |
| 186 | `phases.0.scale` | 0.0001653(64) | 0.0001653(64) | 0.0001653(64) | 0.0001653(64) | 0.0002 |
| 186 | `instrument.zero_shift` | 0.0003(27) | 0.0003(27) | 0.0003(27) | 0.0003(27) | 0.006 |
| 186 | `instrument.profile.w` | 0.0000(23) | 0.0000(23) | 0.0000(23) | 0.0000(23) | 0.001 |
| 186 | `instrument.background.c0` | 451.0(68) | 451.0(68) | 451.0(68) | 451.0(68) | 450 |
| 187 | `phases.0.cell.a` | 3.95282(99) | 3.95282(99) | 3.95282(99) | 3.95282(99) | — |
| 187 | `phases.0.scale` | 0.0001653(65) | 0.0001653(65) | 0.0001653(65) | 0.0001653(65) | 0.0002 |
| 187 | `instrument.zero_shift` | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.006 |
| 187 | `instrument.profile.w` | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.001 |
| 187 | `instrument.background.c0` | 451.9(69) | 451.9(69) | 451.9(69) | 451.9(69) | 450 |
| 188 | `phases.0.cell.a` | 3.95268(99) | 3.95268(99) | 3.95268(99) | 3.95268(99) | — |
| 188 | `phases.0.scale` | 0.0001654(65) | 0.0001654(65) | 0.0001654(65) | 0.0001654(65) | 0.0002 |
| 188 | `instrument.zero_shift` | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.0002(27) | 0.006 |
| 188 | `instrument.profile.w` | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.0000(24) | 0.001 |
| 188 | `instrument.background.c0` | 450.8(70) | 450.8(70) | 450.8(70) | 450.8(70) | 450 |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`.  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 248 | 115 | 49 (135, 137, 140, 142, 143, 146, 147, 148, 149, 150, 151, 152, …) | 0 | 114 (134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, …) | 248 | — | 1 (87) | 11790 | 5054 | 11790 / 12726 | 0.1-1.0 | 95 |
| status | 248 | 1 | 0 | 0 | 0 | 135 | 0 | 1 (87) | 2716 | 2660 | 2716 / 3014 | 0.1-0.5 | 33 |
| off | 248 | 1 | 0 | 0 | 114 (134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, …) | 135 | 0 | 1 (87) | 2716 | 2660 | 2716 / 3014 | 0.1-0.5 | 33 |
| ref | 248 | 0 | 0 | 0 | 0 | 50 | 1 (87) | — | 11907 | 11907 | 11907 / 12210 | 0.2-1.2 | 66 |

### Series-level codes

| code | on | status | off |
|---|---|---|---|
| `SEQUENTIAL_DISCONTINUITY` | 2: phases.0.scale 86→87; instrument.background.c0 49→50 | 2: phases.0.scale 86→87; instrument.background.c0 49→50 | 2: phases.0.scale 86→87; instrument.background.c0 49→50 |
| `SEQUENTIAL_RESEED` | 49 | 0 | 0 |
| `SEQUENTIAL_RWP_OUTLIER` | 114 | 0 | 114 |

Failures (`SeriesFailure`): on 0, status 0, off 0.

## planted perovskite cooling ramp, 248 patterns (synthetic), its null twin (same ramp, no event)

Protocol: tests/planted_series.py refine(): cubic_model(T0), plan='mccusker_default', refit='single', forward, x=T (K), carry=('*',), compiled tier OFF (numpy_path).  Arms: on, status, off; reference `ref`; truth: the simulation.

248 patterns.  The ladder, codes and accepted-value tables carry the 0 where any two arms differ (rungs tried or kept, status, fence verdict, entry codes, or a value by > 0.1 esd) or an arm differs from `ref` by > 0.1 esd, plus every event pattern ±2; the key-value tables carry only the 0 of those where a value differs, plus the events ±2.  Every other pattern has the same rungs, status, verdict and codes in every arm and values within 0.1 esd of each other and of `ref`; all of them are in the JSON.  Distance from truth selects no row (every pattern is some esd from it).

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off |
|---|---|---|---|

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | on vs ref | status vs ref | off vs ref | on vs truth | status vs truth | off vs truth |
|---|---|---|---|---|---|---|---|---|

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference; truth the simulation.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | ref | truth |
|---|---|---|---|---|---|---|

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`.  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 248 | 0 | 0 | 0 | 0 | 248 | — | 0 | 2080 | 2080 | 2080 / 2447 | 0.1-0.3 | 29 |
| status | 248 | 0 | 0 | 0 | 0 | 248 | 0 | 0 | 2080 | 2080 | 2080 / 2447 | 0.1-0.4 | 31 |
| off | 248 | 0 | 0 | 0 | 0 | 248 | 0 | 0 | 2080 | 2080 | 2080 / 2447 | 0.1-0.3 | 30 |
| ref | 248 | 0 | 0 | 0 | 0 | 1 | 0 | — | 9885 | 9885 | 9885 / 10389 | 0.2-0.3 | 54 |

### Series-level codes

No series-level code in any arm.

Failures (`SeriesFailure`): on 0, status 0, off 0.

## simulated trigger series: ten ZrMo₂O₈-shaped 4 165-point patterns, four phases, 100 ppm/step cell ramp (synthetic)

Protocol: examples/bench_refinement.py _trigger_series(): refine_sequential(plan=qpa_plan(), refit='single', first_rung_factor=FIRST_RUNG_FACTOR), carry=('*',), dispersion declined, compiled tier default.  Arms: on, status, off; reference `ref`; truth: the simulation.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | p000 | c [c] | 0.0274 | — | 77 | c [c] | 0.0274 | — | 77 | c [c] | 0.0274 | — | 77 |
| 1 | p001 | w [w] | 0.0270 | 0.0343 | 21 | w [w] | 0.0270 | inf | 21 | w [w] | 0.0270 | 0.0343 | 21 |
| 2 | p002 | w [w] | 0.0272 | 0.0340 | 22 | w [w] | 0.0272 | inf | 22 | w [w] | 0.0272 | 0.0340 | 22 |
| 3 | p003 | w [w] | 0.0272 | 0.0340 | 21 | w [w] | 0.0272 | inf | 21 | w [w] | 0.0272 | 0.0340 | 21 |
| 4 | p004 | w [w] | 0.0266 | 0.0340 | 21 | w [w] | 0.0266 | inf | 21 | w [w] | 0.0266 | 0.0340 | 21 |
| 5 | p005 | w [w] | 0.0272 | 0.0340 | 19 | w [w] | 0.0272 | inf | 19 | w [w] | 0.0272 | 0.0340 | 19 |
| 6 | p006 | w [w] | 0.0271 | 0.0340 | 22 | w [w] | 0.0271 | inf | 22 | w [w] | 0.0271 | 0.0340 | 22 |
| 7 | p007 | w [w] | 0.0270 | 0.0340 | 22 | w [w] | 0.0270 | inf | 22 | w [w] | 0.0270 | 0.0340 | 22 |
| 8 | p008 | w [w] | 0.0272 | 0.0339 | 22 | w [w] | 0.0272 | inf | 22 | w [w] | 0.0272 | 0.0339 | 22 |
| 9 | p009 | w [w] | 0.0270 | 0.0339 | 22 | w [w] | 0.0270 | inf | 22 | w [w] | 0.0270 | 0.0339 | 22 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off |
|---|---|---|---|
| 0 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 1 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 2 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 3 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 4 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 5 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 6 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 7 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 8 | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |
| 9 | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION | BACKGROUND_ABSORPTION, BISO_UNUSUALLY_LARGE, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | on vs ref | status vs ref | off vs ref | on vs truth | status vs truth | off vs truth |
|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 6.05 (phases.1.cell.a) | 6.05 (phases.1.cell.a) | 6.05 (phases.1.cell.a) |
| 1 | 0 | 0 | 0.508 (phases.1.lor_size) | 0.508 (phases.1.lor_size) | 0.508 (phases.1.lor_size) | 6.54 (phases.0.cell.a) | 6.54 (phases.0.cell.a) | 6.54 (phases.0.cell.a) |
| 2 | 0 | 0 | 0.646 (phases.1.lor_size) | 0.646 (phases.1.lor_size) | 0.646 (phases.1.lor_size) | 6.9 (phases.1.cell.a) | 6.9 (phases.1.cell.a) | 6.9 (phases.1.cell.a) |
| 3 | 0 | 0 | 0.457 (instrument.profile.v) | 0.457 (instrument.profile.v) | 0.457 (instrument.profile.v) | 6.19 (phases.1.cell.a) | 6.19 (phases.1.cell.a) | 6.19 (phases.1.cell.a) |
| 4 | 0 | 0 | 0.633 (phases.1.lor_size) | 0.633 (phases.1.lor_size) | 0.633 (phases.1.lor_size) | 6.25 (phases.1.cell.a) | 6.25 (phases.1.cell.a) | 6.25 (phases.1.cell.a) |
| 5 | 0 | 0 | 0.629 (phases.1.lor_strain) | 0.629 (phases.1.lor_strain) | 0.629 (phases.1.lor_strain) | 7.41 (phases.1.cell.a) | 7.41 (phases.1.cell.a) | 7.41 (phases.1.cell.a) |
| 6 | 0 | 0 | 0.354 (phases.1.lor_size) | 0.354 (phases.1.lor_size) | 0.354 (phases.1.lor_size) | 7.42 (phases.1.cell.a) | 7.42 (phases.1.cell.a) | 7.42 (phases.1.cell.a) |
| 7 | 0 | 0 | 0.593 (phases.1.lor_size) | 0.593 (phases.1.lor_size) | 0.593 (phases.1.lor_size) | 6.49 (phases.1.cell.a) | 6.49 (phases.1.cell.a) | 6.49 (phases.1.cell.a) |
| 8 | 0 | 0 | 0.262 (phases.1.lor_size) | 0.262 (phases.1.lor_size) | 0.262 (phases.1.lor_size) | 6.97 (phases.0.cell.a) | 6.97 (phases.0.cell.a) | 6.97 (phases.0.cell.a) |
| 9 | 0 | 0 | 0.494 (phases.1.lor_strain) | 0.494 (phases.1.lor_strain) | 0.494 (phases.1.lor_strain) | 5.95 (phases.1.cell.a) | 5.95 (phases.1.cell.a) | 5.95 (phases.1.cell.a) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference; truth the simulation.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | ref | truth |
|---|---|---|---|---|---|---|
| 0 | `phases.0.cell.a` | 9.13252(35) | 9.13252(35) | 9.13252(35) | 9.13252(35) | 9.1304 |
| 0 | `phases.1.cell.a` | 10.14149(40) | 10.14149(40) | 10.14149(40) | 10.14149(40) | 10.1391 |
| 0 | `phases.1.cell.c` | 11.71168(47) | 11.71168(47) | 11.71168(47) | 11.71168(47) | 11.7091 |
| 0 | `phases.2.cell.b` | 5.2119(12) | 5.2119(12) | 5.2119(12) | 5.2119(12) | 5.2116 |
| 0 | `phases.3.cell.b` | 13.8572(19) | 13.8572(19) | 13.8572(19) | 13.8572(19) | 13.855 |
| 0 | `phases.0.scale` | 0.0003980(13) | 0.0003980(13) | 0.0003980(13) | 0.0003980(13) | 0.0004 |
| 0 | `instrument.zero_shift` | 0.075(14) | 0.075(14) | 0.075(14) | 0.075(14) | 0 |
| 1 | `phases.0.cell.a` | 9.13357(34) | 9.13357(34) | 9.13357(34) | 9.13357(35) | 9.13131 |
| 1 | `phases.1.cell.a` | 10.14263(39) | 10.14263(39) | 10.14263(39) | 10.14263(39) | 10.1401 |
| 1 | `phases.1.cell.c` | 11.71304(46) | 11.71304(46) | 11.71304(46) | 11.71304(46) | 11.7103 |
| 1 | `phases.2.cell.b` | 5.2133(11) | 5.2133(11) | 5.2133(11) | 5.2133(11) | 5.21212 |
| 1 | `phases.3.cell.b` | 13.8569(17) | 13.8569(17) | 13.8569(17) | 13.8569(17) | 13.8564 |
| 1 | `phases.0.scale` | 0.0003986(13) | 0.0003986(13) | 0.0003986(13) | 0.0003986(13) | 0.0004 |
| 1 | `instrument.zero_shift` | 0.081(14) | 0.081(14) | 0.081(14) | 0.081(14) | 0 |
| 2 | `phases.0.cell.a` | 9.13455(35) | 9.13455(35) | 9.13455(35) | 9.13455(35) | 9.13223 |
| 2 | `phases.1.cell.a` | 10.14382(39) | 10.14382(39) | 10.14382(39) | 10.14381(39) | 10.1411 |
| 2 | `phases.1.cell.c` | 11.71430(47) | 11.71430(47) | 11.71430(47) | 11.71429(47) | 11.7114 |
| 2 | `phases.2.cell.b` | 5.2128(12) | 5.2128(12) | 5.2128(12) | 5.2128(12) | 5.21264 |
| 2 | `phases.3.cell.b` | 13.8571(17) | 13.8571(17) | 13.8571(17) | 13.8571(17) | 13.8578 |
| 2 | `phases.0.scale` | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0004 |
| 2 | `instrument.zero_shift` | 0.085(14) | 0.085(14) | 0.085(14) | 0.085(14) | 0 |
| 3 | `phases.0.cell.a` | 9.13527(35) | 9.13527(35) | 9.13527(35) | 9.13526(36) | 9.13314 |
| 3 | `phases.1.cell.a` | 10.14457(39) | 10.14457(39) | 10.14457(39) | 10.14456(40) | 10.1421 |
| 3 | `phases.1.cell.c` | 11.71520(47) | 11.71520(47) | 11.71520(47) | 11.71518(47) | 11.7126 |
| 3 | `phases.2.cell.b` | 5.2139(12) | 5.2139(12) | 5.2139(12) | 5.2139(12) | 5.21316 |
| 3 | `phases.3.cell.b` | 13.8601(18) | 13.8601(18) | 13.8601(18) | 13.8601(18) | 13.8592 |
| 3 | `phases.0.scale` | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0003982(13) | 0.0004 |
| 3 | `instrument.zero_shift` | 0.074(14) | 0.074(14) | 0.074(14) | 0.074(14) | 0 |
| 4 | `phases.0.cell.a` | 9.13619(34) | 9.13619(34) | 9.13619(34) | 9.13617(35) | 9.13405 |
| 4 | `phases.1.cell.a` | 10.14556(39) | 10.14556(39) | 10.14556(39) | 10.14555(39) | 10.1432 |
| 4 | `phases.1.cell.c` | 11.71653(46) | 11.71653(46) | 11.71653(46) | 11.71651(47) | 11.7138 |
| 4 | `phases.2.cell.b` | 5.2141(11) | 5.2141(11) | 5.2141(11) | 5.2141(11) | 5.21368 |
| 4 | `phases.3.cell.b` | 13.8612(17) | 13.8612(17) | 13.8612(17) | 13.8611(17) | 13.8605 |
| 4 | `phases.0.scale` | 0.0003978(13) | 0.0003978(13) | 0.0003978(13) | 0.0003977(13) | 0.0004 |
| 4 | `instrument.zero_shift` | 0.078(14) | 0.078(14) | 0.078(14) | 0.077(14) | 0 |
| 5 | `phases.0.cell.a` | 9.13743(34) | 9.13743(34) | 9.13743(34) | 9.13743(35) | 9.13497 |
| 5 | `phases.1.cell.a` | 10.14702(39) | 10.14702(39) | 10.14702(39) | 10.14702(39) | 10.1442 |
| 5 | `phases.1.cell.c` | 11.71797(46) | 11.71797(46) | 11.71797(46) | 11.71796(46) | 11.715 |
| 5 | `phases.2.cell.b` | 5.2161(11) | 5.2161(11) | 5.2161(11) | 5.2161(11) | 5.21421 |
| 5 | `phases.3.cell.b` | 13.8646(18) | 13.8646(18) | 13.8646(18) | 13.8646(18) | 13.8619 |
| 5 | `phases.0.scale` | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003976(13) | 0.0004 |
| 5 | `instrument.zero_shift` | 0.090(14) | 0.090(14) | 0.090(14) | 0.089(14) | 0 |
| 6 | `phases.0.cell.a` | 9.13835(34) | 9.13835(34) | 9.13835(34) | 9.13835(34) | 9.13588 |
| 6 | `phases.1.cell.a` | 10.14803(38) | 10.14803(38) | 10.14803(38) | 10.14803(38) | 10.1452 |
| 6 | `phases.1.cell.c` | 11.71916(46) | 11.71916(46) | 11.71916(46) | 11.71915(46) | 11.7161 |
| 6 | `phases.2.cell.b` | 5.2159(12) | 5.2159(12) | 5.2159(12) | 5.2159(12) | 5.21473 |
| 6 | `phases.3.cell.b` | 13.8647(17) | 13.8647(17) | 13.8647(17) | 13.8646(17) | 13.8633 |
| 6 | `phases.0.scale` | 0.0003979(13) | 0.0003979(13) | 0.0003979(13) | 0.0003979(13) | 0.0004 |
| 6 | `instrument.zero_shift` | 0.090(14) | 0.090(14) | 0.090(14) | 0.090(14) | 0 |
| 7 | `phases.0.cell.a` | 9.13899(34) | 9.13899(34) | 9.13899(34) | 9.13899(34) | 9.13679 |
| 7 | `phases.1.cell.a` | 10.14868(38) | 10.14868(38) | 10.14868(38) | 10.14869(38) | 10.1462 |
| 7 | `phases.1.cell.c` | 11.72007(46) | 11.72007(46) | 11.72007(46) | 11.72008(45) | 11.7173 |
| 7 | `phases.2.cell.b` | 5.2164(12) | 5.2164(12) | 5.2164(12) | 5.2164(12) | 5.21525 |
| 7 | `phases.3.cell.b` | 13.8666(17) | 13.8666(17) | 13.8666(17) | 13.8666(17) | 13.8647 |
| 7 | `phases.0.scale` | 0.0003974(13) | 0.0003974(13) | 0.0003974(13) | 0.0003974(13) | 0.0004 |
| 7 | `instrument.zero_shift` | 0.079(14) | 0.079(14) | 0.079(14) | 0.080(14) | 0 |
| 8 | `phases.0.cell.a` | 9.14014(35) | 9.14014(35) | 9.14014(35) | 9.14014(35) | 9.1377 |
| 8 | `phases.1.cell.a` | 10.14992(39) | 10.14992(39) | 10.14992(39) | 10.14992(39) | 10.1472 |
| 8 | `phases.1.cell.c` | 11.72156(47) | 11.72156(47) | 11.72156(47) | 11.72156(47) | 11.7185 |
| 8 | `phases.2.cell.b` | 5.2174(11) | 5.2174(11) | 5.2174(11) | 5.2174(11) | 5.21577 |
| 8 | `phases.3.cell.b` | 13.8680(18) | 13.8680(18) | 13.8680(18) | 13.8681(18) | 13.8661 |
| 8 | `phases.0.scale` | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0004 |
| 8 | `instrument.zero_shift` | 0.087(14) | 0.087(14) | 0.087(14) | 0.087(14) | 0 |
| 9 | `phases.0.cell.a` | 9.14066(35) | 9.14066(35) | 9.14066(35) | 9.14066(34) | 9.13862 |
| 9 | `phases.1.cell.a` | 10.15053(39) | 10.15053(39) | 10.15053(39) | 10.15054(38) | 10.1482 |
| 9 | `phases.1.cell.c` | 11.72223(46) | 11.72223(46) | 11.72223(46) | 11.72224(46) | 11.7196 |
| 9 | `phases.2.cell.b` | 5.2168(12) | 5.2168(12) | 5.2168(12) | 5.2168(12) | 5.21629 |
| 9 | `phases.3.cell.b` | 13.8677(17) | 13.8677(17) | 13.8677(17) | 13.8678(17) | 13.8675 |
| 9 | `phases.0.scale` | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0003977(13) | 0.0004 |
| 9 | `instrument.zero_shift` | 0.073(14) | 0.073(14) | 0.073(14) | 0.073(14) | 0 |

### Weight fractions, per pattern (wt %)

W(σ(W)) per arm.

| k | phase | on | status | off | ref |
|---|---|---|---|---|---|
| 0 | sim-ZrMo2O8-cubic | 42.07(0.10) | 42.07(0.10) | 42.07(0.10) | 42.07(0.10) |
| 0 | sim-ZrMo2O8-trigonal | 54.91(0.12) | 54.91(0.12) | 54.91(0.12) | 54.91(0.12) |
| 0 | sim-ZrO2-baddeleyite | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) |
| 0 | sim-MoO3 | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) |
| 1 | sim-ZrMo2O8-cubic | 42.06(0.09) | 42.06(0.09) | 42.06(0.09) | 42.06(0.10) |
| 1 | sim-ZrMo2O8-trigonal | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) |
| 1 | sim-ZrO2-baddeleyite | 1.11(0.09) | 1.11(0.09) | 1.11(0.09) | 1.11(0.09) |
| 1 | sim-MoO3 | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) |
| 2 | sim-ZrMo2O8-cubic | 42.06(0.10) | 42.06(0.10) | 42.06(0.10) | 42.06(0.10) |
| 2 | sim-ZrMo2O8-trigonal | 54.87(0.12) | 54.87(0.12) | 54.87(0.12) | 54.87(0.12) |
| 2 | sim-ZrO2-baddeleyite | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.16(0.09) |
| 2 | sim-MoO3 | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.08) |
| 3 | sim-ZrMo2O8-cubic | 42.03(0.10) | 42.03(0.10) | 42.03(0.10) | 42.03(0.10) |
| 3 | sim-ZrMo2O8-trigonal | 54.88(0.12) | 54.88(0.12) | 54.88(0.12) | 54.88(0.12) |
| 3 | sim-ZrO2-baddeleyite | 1.16(0.09) | 1.16(0.09) | 1.16(0.09) | 1.16(0.09) |
| 3 | sim-MoO3 | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.93(0.07) |
| 4 | sim-ZrMo2O8-cubic | 42.01(0.09) | 42.01(0.09) | 42.01(0.09) | 42.01(0.10) |
| 4 | sim-ZrMo2O8-trigonal | 54.94(0.11) | 54.94(0.11) | 54.94(0.11) | 54.94(0.12) |
| 4 | sim-ZrO2-baddeleyite | 1.13(0.09) | 1.13(0.09) | 1.13(0.09) | 1.13(0.09) |
| 4 | sim-MoO3 | 1.92(0.07) | 1.92(0.07) | 1.92(0.07) | 1.91(0.07) |
| 5 | sim-ZrMo2O8-cubic | 42.02(0.10) | 42.02(0.10) | 42.02(0.10) | 42.02(0.10) |
| 5 | sim-ZrMo2O8-trigonal | 54.90(0.12) | 54.90(0.12) | 54.90(0.12) | 54.90(0.12) |
| 5 | sim-ZrO2-baddeleyite | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) |
| 5 | sim-MoO3 | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) | 1.94(0.07) |
| 6 | sim-ZrMo2O8-cubic | 42.02(0.09) | 42.02(0.09) | 42.02(0.09) | 42.02(0.10) |
| 6 | sim-ZrMo2O8-trigonal | 54.93(0.11) | 54.93(0.11) | 54.93(0.11) | 54.93(0.11) |
| 6 | sim-ZrO2-baddeleyite | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) | 1.14(0.09) |
| 6 | sim-MoO3 | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) |
| 7 | sim-ZrMo2O8-cubic | 41.98(0.09) | 41.98(0.09) | 41.98(0.09) | 41.98(0.09) |
| 7 | sim-ZrMo2O8-trigonal | 54.96(0.11) | 54.96(0.11) | 54.96(0.11) | 54.96(0.11) |
| 7 | sim-ZrO2-baddeleyite | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) |
| 7 | sim-MoO3 | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) |
| 8 | sim-ZrMo2O8-cubic | 42.01(0.10) | 42.01(0.10) | 42.01(0.10) | 42.01(0.10) |
| 8 | sim-ZrMo2O8-trigonal | 54.94(0.12) | 54.94(0.12) | 54.94(0.12) | 54.93(0.12) |
| 8 | sim-ZrO2-baddeleyite | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) | 1.15(0.09) |
| 8 | sim-MoO3 | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) | 1.91(0.07) |
| 9 | sim-ZrMo2O8-cubic | 41.94(0.10) | 41.94(0.10) | 41.94(0.10) | 41.95(0.10) |
| 9 | sim-ZrMo2O8-trigonal | 55.00(0.12) | 55.00(0.12) | 55.00(0.12) | 55.00(0.12) |
| 9 | sim-ZrO2-baddeleyite | 1.17(0.09) | 1.17(0.09) | 1.17(0.09) | 1.17(0.09) |
| 9 | sim-MoO3 | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) | 1.89(0.07) |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`.  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 10 | 0 | 0 | 0 | 0 | 10 | — | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | 269 | 269 | 269 / 275 | 8.3-11.9 | 92 |
| status | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | 269 | 269 | 269 / 275 | 8.0-12.5 | 90 |
| off | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | 269 | 269 | 269 / 275 | 8.1-14.8 | 94 |
| ref | 10 | 0 | 0 | 0 | 0 | 1 | 9 (1, 2, 3, 4, 5, 6, 7, 8, 9) | — | 768 | 768 | 768 / 777 | 11.0-12.6 | 120 |

### Series-level codes

| code | on | status | off |
|---|---|---|---|
| `SEQUENTIAL_PERSISTENT_FINDING` | 34 | 34 | 34 |

Failures (`SeriesFailure`): on 0, status 0, off 0.

## Cr₂WO₆ HB-2A pair, 4 K then 150 K (real, constant-wavelength neutron, λ 2.4067 Å)

Protocol: tests/test_magnetic_series.py::test_the_cr2wo6_pair_as_a_series_gives_the_single_pattern_verdicts: start = the 4 K nuclear fit of conftest.cr2wo6_nuclear with a 2 μB Cr moment (58.395), refine_sequential(plan=_plan(MAGNETIC_STAGES), x=[4, 150]), carry=('*',), refit='single', compiled tier OFF for the series (the nuclear setup fits run on the default path, as the fixture's do).  Arms: on, status, off; reference `ref`.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 4K | c [c] | 0.1047 | — | 49 | c [c] | 0.1047 | — | 49 | c [c] | 0.1047 | — | 49 |
| 1 | 150K | w [w] | 0.0992 (max_iter) | 0.1309 | 824 | w [w] | 0.0992 (max_iter) | inf | 824 | w [w] | 0.0992 (max_iter) | 0.1309 | 824 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off |
|---|---|---|---|
| 0 | CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, MOMENT_ANGLE_STATIONARY | CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, MOMENT_ANGLE_STATIONARY | CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, MOMENT_ANGLE_STATIONARY |
| 1 | CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, HIGH_CORRELATION, MOMENT_ANGLE_STATIONARY, STAGE_MAX_ITER | CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, HIGH_CORRELATION, MOMENT_ANGLE_STATIONARY, STAGE_MAX_ITER | CAPILLARY_OFFSET_UNAVAILABLE, DATA_SUPPORT_LOW, HIGH_CORRELATION, MOMENT_ANGLE_STATIONARY, STAGE_MAX_ITER |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | on vs ref | status vs ref | off vs ref |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 |
| 1 | 0 | 0 | 0.087 (phases.0.atoms.2.x) ≠1 no-esd (phases.0.atoms.1.moment.dof1) | 0.087 (phases.0.atoms.2.x) ≠1 no-esd (phases.0.atoms.1.moment.dof1) | 0.087 (phases.0.atoms.2.x) ≠1 no-esd (phases.0.atoms.1.moment.dof1) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | ref |
|---|---|---|---|---|---|
| 0 | `phases.0.atoms.1.moment.dof0` | 2.125(45) | 2.125(45) | 2.125(45) | 2.125(45) |
| 0 | `phases.0.cell.a` | 4.57750(18) | 4.57750(18) | 4.57750(18) | 4.57750(18) |
| 0 | `phases.0.cell.c` | 8.84169(44) | 8.84169(44) | 8.84169(44) | 8.84169(44) |
| 0 | `phases.0.scale` | 0.00848(21) | 0.00848(21) | 0.00848(21) | 0.00848(21) |
| 0 | `instrument.zero_shift` | 0.2011(38) | 0.2011(38) | 0.2011(38) | 0.2011(38) |
| 1 | `phases.0.atoms.1.moment.dof0` | 0.05(49) | 0.05(49) | 0.05(49) | 0.05(46) |
| 1 | `phases.0.cell.a` | 4.57531(16) | 4.57531(16) | 4.57531(16) | 4.57531(16) |
| 1 | `phases.0.cell.c` | 8.85370(38) | 8.85370(38) | 8.85370(38) | 8.85370(38) |
| 1 | `phases.0.scale` | 0.00838(19) | 0.00838(19) | 0.00838(19) | 0.00838(19) |
| 1 | `instrument.zero_shift` | 0.2094(34) | 0.2094(34) | 0.2094(34) | 0.2094(34) |

### Moment evidence, per pattern (`SeriesEntry.magnetic`)

|μ| (esd) μB and `supported`, per site.

| k | site | on | status | off | ref |
|---|---|---|---|---|---|
| 0 | Cr1 | 2.125(0.045) True | 2.125(0.045) True | 2.125(0.045) True | 2.125(0.045) True |
| 1 | Cr1 | 0.046(0.492) False | 0.046(0.492) False | 0.046(0.492) False | 0.048(0.465) False |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`.  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 2 | 0 | 0 | 0 | 0 | 2 | — | 1 (1) | 873 | 873 | 1146 / 934 | 8.4-13.7 | 22 |
| status | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 1 (1) | 873 | 873 | 1146 / 934 | 8.3-14.1 | 22 |
| off | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 1 (1) | 873 | 873 | 1146 / 934 | 11.0-14.7 | 26 |
| ref | 2 | 0 | 0 | 0 | 0 | 1 | 1 (1) | — | 898 | 898 | 1167 / 952 | 8.8-14.6 | 23 |

### Series-level codes

| code | on | status | off |
|---|---|---|---|
| `SEQUENTIAL_MOMENT_HOLD` | 1 | 1 | 1 |
| `SEQUENTIAL_MOMENT_ONSET` | 1 | 1 | 1 |

Failures (`SeriesFailure`): on 0, status 0, off 0.

## tutorial 05's LaB6 ramp, 7 patterns 300-900 K (synthetic), the 700 K cell × 1.02

Protocol: examples/tutorials/05_sequential_fits.py series_jump / series_broken: refine_sequential(plan='mccusker_default', x=T, labels=scans), carry=('*',), refit='single', compiled tier default.  Arms: on, status, off; reference `ref`; truth: the simulation.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | scan8 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 |
| 1 | scan9 | w [w] | 0.0409 | 0.0511 | 15 | w [w] | 0.0409 | inf | 15 | w [w] | 0.0409 | 0.0511 | 15 |
| 2 | scan10 | w [w] | 0.0399 | 0.0511 | 15 | w [w] | 0.0399 | inf | 15 | w [w] | 0.0399 | 0.0511 | 15 |
| 3 | scan11 | w [w] | 0.0405 | 0.0511 | 15 | w [w] | 0.0405 | inf | 15 | w [w] | 0.0405 | 0.0511 | 15 |
| 4 | scan12 | w [w] | 0.0390 | 0.0508 | 69 | w [w] | 0.0390 | inf | 69 | w [w] | 0.0390 | 0.0508 | 69 |
| 5 | scan13 | w [w] | 0.0402 | 0.0506 | 384 | w [w] | 0.0402 | inf | 384 | w [w] | 0.0402 | 0.0506 | 384 |
| 6 | scan14 | w [w] | 0.0404 | 0.0504 | 15 | w [w] | 0.0404 | inf | 15 | w [w] | 0.0404 | 0.0504 | 15 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off |
|---|---|---|---|
| 0 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 1 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 2 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 3 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 4 | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED |
| 5 | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, PATTERN_UNDERSAMPLED |
| 6 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | on vs ref | status vs ref | off vs ref | on vs truth | status vs truth | off vs truth |
|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) |
| 1 | 0 | 0 | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) |
| 2 | 0 | 0 | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) |
| 3 | 0 | 0 | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) |
| 4 | 0 | 0 | 2.1 (instrument.background.c0) | 2.1 (instrument.background.c0) | 2.1 (instrument.background.c0) | 8.86 (instrument.background.c0) | 8.86 (instrument.background.c0) | 8.86 (instrument.background.c0) |
| 5 | 0 | 0 | 2.03 (instrument.background.c0) | 2.03 (instrument.background.c0) | 2.03 (instrument.background.c0) | 10.3 (instrument.background.c0) | 10.3 (instrument.background.c0) | 10.3 (instrument.background.c0) |
| 6 | 0 | 0 | 2.38e-07 (instrument.profile.u) | 2.38e-07 (instrument.profile.u) | 2.38e-07 (instrument.profile.u) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference; truth the simulation.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | ref | truth |
|---|---|---|---|---|---|---|
| 0 | `phases.0.cell.a` | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1566 |
| 0 | `phases.0.scale` | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.0005 |
| 0 | `instrument.zero_shift` | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.008 |
| 0 | `instrument.profile.w` | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.00025 |
| 0 | `instrument.background.c0` | 38.76(14) | 38.76(14) | 38.76(14) | 38.76(14) | 40 |
| 1 | `phases.0.cell.a` | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.15868 |
| 1 | `phases.0.scale` | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.0005 |
| 1 | `instrument.zero_shift` | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.008 |
| 1 | `instrument.profile.w` | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.00025 |
| 1 | `instrument.background.c0` | 39.06(14) | 39.06(14) | 39.06(14) | 39.06(14) | 40 |
| 2 | `phases.0.cell.a` | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.16076 |
| 2 | `phases.0.scale` | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.0005 |
| 2 | `instrument.zero_shift` | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008 |
| 2 | `instrument.profile.w` | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.00025 |
| 2 | `instrument.background.c0` | 39.10(14) | 39.10(14) | 39.10(14) | 39.10(14) | 40 |
| 3 | `phases.0.cell.a` | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.16283 |
| 3 | `phases.0.scale` | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.0005 |
| 3 | `instrument.zero_shift` | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008 |
| 3 | `instrument.profile.w` | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.00025 |
| 3 | `instrument.background.c0` | 38.99(14) | 38.99(14) | 38.99(14) | 38.99(14) | 40 |
| 4 | `phases.0.cell.a` | 4.2482085(41) | 4.2482085(41) | 4.2482085(41) | 4.2482085(40) | 4.24821 |
| 4 | `phases.0.scale` | 0.00049975(36) | 0.00049975(36) | 0.00049975(36) | 0.00049974(36) | 0.0005 |
| 4 | `instrument.zero_shift` | 0.007983(13) | 0.007983(13) | 0.007983(13) | 0.007983(13) | 0.008 |
| 4 | `instrument.profile.w` | 0.0002477(20) | 0.0002477(20) | 0.0002477(20) | 0.0002478(20) | 0.00025 |
| 4 | `instrument.background.c0` | 38.74(14) | 38.74(14) | 38.74(14) | 39.04(14) | 40 |
| 5 | `phases.0.cell.a` | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.16699 |
| 5 | `phases.0.scale` | 0.00050002(37) | 0.00050002(37) | 0.00050002(37) | 0.00050001(37) | 0.0005 |
| 5 | `instrument.zero_shift` | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.008 |
| 5 | `instrument.profile.w` | 0.0002494(22) | 0.0002494(22) | 0.0002494(22) | 0.0002495(22) | 0.00025 |
| 5 | `instrument.background.c0` | 38.56(14) | 38.56(14) | 38.56(14) | 38.85(14) | 40 |
| 6 | `phases.0.cell.a` | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.16907 |
| 6 | `phases.0.scale` | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.0005 |
| 6 | `instrument.zero_shift` | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.008 |
| 6 | `instrument.profile.w` | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.00025 |
| 6 | `instrument.background.c0` | 38.87(14) | 38.87(14) | 38.87(14) | 38.87(14) | 40 |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`.  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 7 | 0 | 0 | 0 | 0 | 7 | — | 2 (4, 5) | 551 | 551 | 551 / 472 | 0.1-2.3 | 4 |
| status | 7 | 0 | 0 | 0 | 0 | 7 | 0 | 2 (4, 5) | 551 | 551 | 551 / 472 | 0.1-2.4 | 4 |
| off | 7 | 0 | 0 | 0 | 0 | 7 | 0 | 2 (4, 5) | 551 | 551 | 551 / 472 | 0.1-2.1 | 3 |
| ref | 7 | 0 | 0 | 0 | 0 | 1 | 2 (4, 5) | — | 258 | 258 | 258 / 280 | 0.2-0.3 | 2 |

### Series-level codes

| code | on | status | off |
|---|---|---|---|
| `SEQUENTIAL_DISCONTINUITY` | 3: phases.0.cell.a 3→4; phases.0.cell.b 3→4; phases.0.cell.c 3→4 | 3: phases.0.cell.a 3→4; phases.0.cell.b 3→4; phases.0.cell.c 3→4 | 3: phases.0.cell.a 3→4; phases.0.cell.b 3→4; phases.0.cell.c 3→4 |
| `SEQUENTIAL_PERSISTENT_FINDING` | 2 | 2 | 2 |

Failures (`SeriesFailure`): on 0, status 0, off 0.

## tutorial 05's LaB6 ramp, 7 patterns 300-900 K (synthetic), the 700 K cell × 1.05

Protocol: examples/tutorials/05_sequential_fits.py series_jump / series_broken: refine_sequential(plan='mccusker_default', x=T, labels=scans), carry=('*',), refit='single', compiled tier default.  Arms: on, status, off; reference `ref`; truth: the simulation.

### Ladder, per pattern

Rungs: w = collapsed warm, ws = staged from warm, c = cold; [kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` (residual evaluations over every returned rung).  Fence = `rwp_fence`; `*` marks `above_fence`.

| k | label | on: rungs [kept] | on: Rwp warm→kept | on: fence | on: nfev | status: rungs [kept] | status: Rwp warm→kept | status: fence | status: nfev | off: rungs [kept] | off: Rwp warm→kept | off: fence | off: nfev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | scan8 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 | c [c] | 0.0409 | — | 38 |
| 1 | scan9 | w [w] | 0.0409 | 0.0511 | 15 | w [w] | 0.0409 | inf | 15 | w [w] | 0.0409 | 0.0511 | 15 |
| 2 | scan10 | w [w] | 0.0399 | 0.0511 | 15 | w [w] | 0.0399 | inf | 15 | w [w] | 0.0399 | 0.0511 | 15 |
| 3 | scan11 | w [w] | 0.0405 | 0.0511 | 15 | w [w] | 0.0405 | inf | 15 | w [w] | 0.0405 | 0.0511 | 15 |
| 4 | scan12 | w→ws→c [c] | 0.9687→0.9687 | 0.0508* | 19 | w [w] | 0.9687 | inf | 5 | w [w] | 0.9687 | 0.0508* | 5 |
| 5 | scan13 | w [w] | 0.0402 | 0.0511 | 40 | w [w] | 0.0402 | inf | 32 | w [w] | 0.0402 | 0.0511 | 32 |
| 6 | scan14 | w [w] | 0.0404 | 0.0508 | 15 | w [w] | 0.0404 | inf | 15 | w [w] | 0.0404 | 0.0508 | 15 |

### Codes, per pattern

Entry codes and the series-level codes naming the pattern (`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a discontinuity names a path and is listed under the series codes below.

| k | on | status | off |
|---|---|---|---|
| 0 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 1 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 2 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 3 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 4 | CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT, MODEL_FAR_FROM_DATA, PATTERN_UNDERSAMPLED, P_UNC, S_RESEED, S_RWP_OUTLIER | CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT, MODEL_FAR_FROM_DATA, PATTERN_UNDERSAMPLED, P_UNC | CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT, MODEL_FAR_FROM_DATA, PATTERN_UNDERSAMPLED, P_UNC, S_RWP_OUTLIER |
| 5 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |
| 6 | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED | CAPILLARY_OFFSET_UNAVAILABLE, PATTERN_UNDERSAMPLED |

### Accepted values, per pattern

Worst |Δ|/esd over every refined path both rows carry, and the weight fractions (`W.<phase>`), with the esd of the row compared against (`on`, or the reference); against truth, |Δ|/esd with the arm's own esd over the key paths of the key-value table only.  `0` = equal to the stored precision; `≠n no-esd` = esd-less paths that moved; `+n` = paths only one row carries.

| k | status vs on: worst |Δ|/esd (path) | off vs on: worst |Δ|/esd (path) | on vs ref | status vs ref | off vs ref | on vs truth | status vs truth | off vs truth |
|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) | 8.94 (instrument.background.c0) |
| 1 | 0 | 0 | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 8.01e-07 (instrument.profile.u) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) | 6.68 (instrument.background.c0) |
| 2 | 0 | 0 | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 2.97e-07 (instrument.profile.v) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) | 6.66 (instrument.background.c0) |
| 3 | 0 | 0 | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 6.51e-08 (instrument.profile.w) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) | 7.42 (instrument.background.c0) |
| 4 | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 0 | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 1.65e-10 (instrument.background.c0) ≠8 no-esd (instrument.profile.u, instrument.profile.v, instrument.profile.w, …) | 614 (phases.0.scale) | 668 (phases.0.scale) | 668 (phases.0.scale) |
| 5 | 2.78e-07 (instrument.profile.u) | 2.78e-07 (instrument.profile.u) | 4.72e-07 (instrument.profile.u) | 1.99e-07 (instrument.profile.w) | 1.99e-07 (instrument.profile.w) | 8.3 (instrument.background.c0) | 8.3 (instrument.background.c0) | 8.3 (instrument.background.c0) |
| 6 | 1.39e-07 (instrument.profile.v) | 1.39e-07 (instrument.profile.v) | 9.87e-08 (instrument.profile.w) | 4.18e-08 (instrument.profile.u) | 4.18e-08 (instrument.profile.u) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) | 8.28 (instrument.background.c0) |

### Key values, per pattern

value(esd in the last digits shown) per arm; `ref` the reference; truth the simulation.  `—`: the path is not refined in that row (held, or no true value).

| k | path | on | status | off | ref | truth |
|---|---|---|---|---|---|---|
| 0 | `phases.0.cell.a` | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1565938(43) | 4.1566 |
| 0 | `phases.0.scale` | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.00049984(37) | 0.0005 |
| 0 | `instrument.zero_shift` | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.007987(14) | 0.008 |
| 0 | `instrument.profile.w` | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.0002507(22) | 0.00025 |
| 0 | `instrument.background.c0` | 38.76(14) | 38.76(14) | 38.76(14) | 38.76(14) | 40 |
| 1 | `phases.0.cell.a` | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.1586732(43) | 4.15868 |
| 1 | `phases.0.scale` | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.00049969(38) | 0.0005 |
| 1 | `instrument.zero_shift` | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.007986(14) | 0.008 |
| 1 | `instrument.profile.w` | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.0002511(22) | 0.00025 |
| 1 | `instrument.background.c0` | 39.06(14) | 39.06(14) | 39.06(14) | 39.06(14) | 40 |
| 2 | `phases.0.cell.a` | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.1607616(41) | 4.16076 |
| 2 | `phases.0.scale` | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.00049970(36) | 0.0005 |
| 2 | `instrument.zero_shift` | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008015(14) | 0.008 |
| 2 | `instrument.profile.w` | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.0002493(21) | 0.00025 |
| 2 | `instrument.background.c0` | 39.10(14) | 39.10(14) | 39.10(14) | 39.10(14) | 40 |
| 3 | `phases.0.cell.a` | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.1628387(42) | 4.16283 |
| 3 | `phases.0.scale` | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.00049963(36) | 0.0005 |
| 3 | `instrument.zero_shift` | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008018(14) | 0.008 |
| 3 | `instrument.profile.w` | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.0002521(21) | 0.00025 |
| 3 | `instrument.background.c0` | 38.99(14) | 38.99(14) | 38.99(14) | 38.99(14) | 40 |
| 4 | `phases.0.cell.a` | — | — | — | — | 4.37316 |
| 4 | `phases.0.scale` | 0.00000000(81) | 0.00000000(75) | 0.00000000(75) | 0.00000000(81) | 0.0005 |
| 4 | `instrument.zero_shift` | 0 | 0.00801768 | 0.00801768 | 0 | 0.008 |
| 4 | `instrument.profile.w` | 0.000375 | 0.000252163 | 0.000252163 | 0.000375 | 0.00025 |
| 4 | `instrument.background.c0` | 45.3(97) | 45.3(97) | 45.3(97) | 45.3(97) | 40 |
| 5 | `phases.0.cell.a` | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.1669853(43) | 4.16699 |
| 5 | `phases.0.scale` | 0.00050001(37) | 0.00050001(37) | 0.00050001(37) | 0.00050001(37) | 0.0005 |
| 5 | `instrument.zero_shift` | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.007977(14) | 0.008 |
| 5 | `instrument.profile.w` | 0.0002495(22) | 0.0002495(22) | 0.0002495(22) | 0.0002495(22) | 0.00025 |
| 5 | `instrument.background.c0` | 38.85(14) | 38.85(14) | 38.85(14) | 38.85(14) | 40 |
| 6 | `phases.0.cell.a` | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.1690659(42) | 4.16907 |
| 6 | `phases.0.scale` | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.00049989(36) | 0.0005 |
| 6 | `instrument.zero_shift` | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.007981(14) | 0.008 |
| 6 | `instrument.profile.w` | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.0002526(22) | 0.00025 |
| 6 | `instrument.background.c0` | 38.87(14) | 38.87(14) | 38.87(14) | 38.87(14) | 40 |

### Totals

"Differ" = a value apart by > 0.1 esd (the esd of the row compared against: `on`, or the reference), an esd-less value moved by > 1e-06 relative, or a path only one row carries (the script's `differ`).  "bit-identical" compares `values_sha`.  nfev (entries) is `SeriesEntry.n_iterations`; solver nfev / njev count every solve, the automatic profile-interval refits included.  Counts are over each arm's own patterns; comparisons over the patterns both rows have.

| arm | patterns | escalated | reseeded (kept cold) | quarantined | above fence | bit-identical to on | differ from on | differ from ref | nfev (entries) | kept-rung nfev | solver nfev / njev | wall per pattern (s) | wall total (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| on | 7 | 1 | 1 (4) | 0 | 1 (4) | 7 | — | 0 | 157 | 145 | 157 / 184 | 0.1-0.3 | 1 |
| status | 7 | 0 | 0 | 0 | 0 | 4 | 1 (4) | 1 (4) | 135 | 135 | 135 / 149 | 0.1-0.2 | 1 |
| off | 7 | 0 | 0 | 0 | 1 (4) | 4 | 1 (4) | 1 (4) | 135 | 135 | 135 / 149 | 0.1-0.3 | 1 |
| ref | 7 | 0 | 0 | 0 | 0 | 2 | 0 | — | 212 | 212 | 212 / 239 | 0.2-0.2 | 2 |

### Series-level codes

| code | on | status | off |
|---|---|---|---|
| `SEQUENTIAL_DISCONTINUITY` | 0 | 1: phases.0.scale 4→5 | 0 |
| `SEQUENTIAL_PERSISTENT_FINDING` | 2 | 2 | 2 |
| `SEQUENTIAL_RESEED` | 1 | 0 | 0 |
| `SEQUENTIAL_RWP_OUTLIER` | 1 | 0 | 1 |

Failures (`SeriesFailure`): on 0, status 0, off 0.

## What the table shows

Facts read off the tables above, family by family. No tier and no ruling.

**Across every family.** No arm quarantines anything: no kept attempt is `diverged` in any
arm of any family, so `SEQUENTIAL_UNRECOVERED` never fires and the quarantine is not
exercised. No `SeriesFailure` anywhere.

**`cpd`** (real, 8 patterns, the protocol; `status` and `off` on the first 2).
- cpd-1a, cold in every arm, is bit-identical across arms and references.
- cpd-1b: the warm rung ends at Rwp 0.7652 (`max_iter`), 3.75× its fence 0.2038, in every
  arm. `on` escalates (`w→ws`) and keeps `warm_staged` at 0.13779, against 0.13732 for the
  independent fits, spending 629 evaluations there (536 of them in the discarded warm rung).
  `status` and `off` keep the warm rung (`max_iter`, `STAGE_MAX_ITER`, 536 evaluations),
  bit-identical to each other. Its values are 1 220 esd from `on` (`on`'s esd; worst path
  `instrument.geometry.axial_sl`) and 1 190 from `ref_seeded`. Corundum a 4.987(88) Å against
  `on`'s 4.75804(38) and the independent 4.75809(38); zero shift 18.0(74)° against
  −0.045(35)°; sample displacement 26(11) against 0.019(55); W corundum 86.68(12.90) wt %
  against 94.24(0.23), weighed 94.31; GoF 8.37 against 1.51. The entry carries
  `CELL_RUNAWAY`, `BISO_UNUSUALLY_LARGE`, `BACKGROUND_ABSORPTION` and `STAGE_MAX_ITER`;
  under `off` it is `above_fence` (`SEQUENTIAL_RWP_OUTLIER`), under `status` nothing marks it
  at the series level. No arm quarantines it, since `max_iter` is not `diverged`.
- `on` past the cut (1c-1h): no further escalation; every kept rung is inside its fence. It
  sits 7.05-14.2 esd from `ref_seeded` at 1b-1h, the worst path a `lor_strain` at each.
- The cut arms' series-level codes are those of their own two-pattern chains, not comparable
  with `on`'s eight (`SEQUENTIAL_PERSISTENT_FINDING`: 26 under `on`, 0 under `status`/`off`).
- `on` totals 987 evaluations against the independent fits' 1 218. The WP's Context quotes
  388 chain evaluations for this chain (WP-2002), and here 629 are spent at cpd-1b alone.
  Mean Rwp is 0.12565 for `on` and 0.12580 independent, which is the Context's 0.1256 and
  0.1258. QPA against the weighed composition: RMS |ΔW| 2.268 wt % for `on` and 2.301 wt %
  independent.

**`cpd-noclose`** (real, 8 patterns).
- No arm escalates at any pattern; `on`, `status` and `off` are bit-identical at all 8, at 708
  evaluations each.
- At cpd-1b (k = 1, 94 wt % corundum) the warm rung reaches Rwp 0.16333 (GoF 1.79), under its
  fence 0.2095 (1.25 × cpd-1a's 0.16761). The independent fits reach 0.13932 (GoF 1.52). The
  chain's entry carries `CELL_RUNAWAY` and `PHASE_UNCONSTRAINED`, corundum's cell is held
  (absent from its parameters), and its corundum scale is 10.0 esd from `ref_seeded`
  (W 94.84(0.27) against 94.29(0.23); weighed 94.31).
- The chain's kept Rwp is above the independent fits' at all 7 warm patterns (1.172× at
  cpd-1b, 1.015-1.041× at 1c-1h), and every one is inside its fence. At 1c-1h the chain sits
  2.42-5.19 esd from `ref_seeded`, worst path `instrument.profile.v` at each.
- QPA against the weighed composition: RMS |ΔW| 2.252 wt % for the chain and 2.251 wt % for the
  independent fits; worst single |ΔW| 4.92 and 4.97 wt %.
- `ref` (cold from the chain's start) and `ref_seeded` (seeded per mixture) agree to
  ≤ 3.3e-6 esd at every pattern.
- Series codes are the same in all three arms: one `SEQUENTIAL_DISCONTINUITY`
  (`phases.0.scale` 0→1, corundum 1.15 → 94.31 wt % as weighed) and
  `SEQUENTIAL_PERSISTENT_FINDING` 25 times.

**`planted`** (synthetic, 248 patterns).
- `on` escalates 115 patterns: 87 (`w→ws`) and every pattern 134-247 (`w→ws→c`, all 114 above
  the fence, Rwp 1.03-4.19× it). It keeps the cold rung on 49 of them (`SEQUENTIAL_RESEED`
  49), `warm_staged` on 38 and `warm` on 28. `status` and `off` escalate pattern 87 only, the
  WP-1127 budget-forced escalation, and keep `warm_staged` there as `on` does.
- Accepted values: no pattern differs from `on` by more than 0.1 esd in `status` or `off`; the
  largest difference anywhere is 0.0007 esd (`instrument.profile.y`, k = 140). 135 of 248 rows
  are bit-identical to `on`.
- The 49 kept cold rungs are bit-identical to `ref`, the independent cold fits, and each one's
  warm and cold Rwp agree to 7.6e-7 relative.
- Evaluations: 11 790 under `on` against 2 716 under `status` and `off` (4.34×); 6 736 of
  `on`'s are in rungs it discarded.
- Codes: `SEQUENTIAL_RWP_OUTLIER` 114 under `on` and `off`, 0 under `status`;
  `SEQUENTIAL_RESEED` 49 under `on` only; the same two `SEQUENTIAL_DISCONTINUITY` steps in all
  three arms (`phases.0.scale` 86→87, `instrument.background.c0` 49→50), and no step at the
  transition (186) in any arm.
- Against `ref`, all three arms differ at pattern 87 (the blank frame) only: 2.13 esd on
  `instrument.zero_shift`, and the held cell's esd-less `b`/`c` rows.
- Distance from the simulated truth differs between the three arms by at most 0.0007 esd at
  any pattern.

**`planted-null`** (synthetic, 248 patterns, no event). No escalation, no series code, all three
arms bit-identical at 2 080 evaluations each.

**`trigger`** (synthetic, 10 patterns). No arm escalates; the three arms are bit-identical at
269 evaluations each. The chain differs from `ref` at 9 of 10 patterns, by 0.26-0.65 esd, the
worst path each time one of `phases.1.lor_size`, `phases.1.lor_strain` or
`instrument.profile.v`. `SEQUENTIAL_PERSISTENT_FINDING` 34 times in each arm.

**`cr2wo6`** (real neutron, 2 patterns). No arm escalates: 150 K's warm Rwp 0.0992 is inside
its fence 0.1309. The three arms are bit-identical; the 150 K warm rung ends `max_iter`
(`STAGE_MAX_ITER`, 824 evaluations) in all three. Against `ref`: 0.087 esd on
`phases.0.atoms.2.x`, plus the esd-less `moment.dof1` moved; the moment verdicts agree
(4 K supported, 150 K not), and `SEQUENTIAL_MOMENT_HOLD` and `SEQUENTIAL_MOMENT_ONSET` fire
once each in every arm. `SeriesEntry.n_iterations` totals 873 while the solver ran 1 146
evaluations, the difference being the automatic moment-angle profile-interval refits.

**`tut05-jump`** (synthetic, 7 patterns, 700 K cell × 1.02). No arm escalates; the three arms
are bit-identical at 551 evaluations each, with the same three `SEQUENTIAL_DISCONTINUITY`
steps (`phases.0.cell.a/b/c` 3→4). Against `ref` they differ at the jump and the pattern after
it (k = 4, 5) by 2.10 and 2.03 esd, on `instrument.background.c0` both times.

**`tut05-broken`** (synthetic, 7 patterns, 700 K cell × 1.05).
- `on` escalates pattern 4 (`w→ws→c`) and keeps the cold rung (`SEQUENTIAL_RESEED`; Rwp
  0.9687, 19.05× its fence 0.0508); `status` and `off` keep the warm rung there.
- At pattern 4 every esd-carrying value agrees across arms to 2e-10 esd, while eight esd-less
  rows differ (`instrument.zero_shift`, `instrument.profile.u/v/w/x/y`, `phases.0.cell.b/c`):
  `on` and `ref` carry the cold start's values (zero shift 0, W 0.000375), `status` and `off`
  the warm-carried ones (0.00802, 0.000252). The scale sits on its floor (`FLOOR_HIT`,
  `MODEL_FAR_FROM_DATA`, `PHASE_UNCONSTRAINED`) in every arm. Patterns 5-6 agree to 3e-7 esd;
  0-3 are bit-identical.
- Evaluations: 157 under `on`, 135 under `status` and `off`.
- Codes: `SEQUENTIAL_RWP_OUTLIER` on pattern 4 under `on` and `off`, not under `status`;
  `SEQUENTIAL_DISCONTINUITY` (`phases.0.scale` 4→5) under `status` only, because the
  discontinuity scan drops above-fence patterns from its steps (`sequential.py:2389-2390`) and
  under an infinite fence none is above it.

## Unresolved

- **`cpd`'s `status` and `off` past cpd-1b** are not measured (§ The CPD protocol run): each
  warm pattern after cpd-1b starts from the 0.7652 state, and cpd-1c's closing stage alone was
  running at about 5 evaluations a minute toward its 400 cap when the full runs were stopped.
- **The closing stage on a warm CPD pattern** (§ The CPD protocol run). The cost is the
  closing stage's FCJ quadrature: `refine._hold_unsupported_phases` (`refine.py:1548`) →
  `forward.phase_support` (`forward.py:2212`) → `fcj.fcj_offsets_weights_batch`
  (`fcj.py:241`) → `fcj._gauss_legendre_01` (`fcj.py:88-92`). On cpd-1b the node count passed
  to it climbed through 128 distinct values to the 512 cap (`CLOSING_MAX_NODES // 2`), every one
  a cache miss and a fresh `leggauss`; once at the cap, the time goes into the compiled FCJ
  kernels (65 % `compiled.bases_fcj`, 28 % `compiled.omega_fcj` in a 30 s py-spy sample). The
  same chain without the closing stage runs in 28 s an arm. WP-2003's clash table lists
  "the closing stage × path dependence"; this is its cost side, measured on one pattern only.
- `RuntimeWarning: invalid value encountered in power` at
  `src/rietx/model/profiles/pseudovoigt.py:45` (`gamma5 ** 0.2` on a negative `gamma5`;
  per-pattern counts in each row's `warnings`): on `planted` pattern 87 (the blank frame) in
  every arm and in `ref`; on `cpd` under `on` at every pattern from cpd-1b to 1h, and under
  `status`/`off` not at all, so it comes from `on`'s escalated `warm_staged` rung at cpd-1b and
  the state that rung hands on, not from the warm rung all three share. Not traced further.
- `SeriesEntry.n_iterations` is documented as "total residual evaluations over every attempt"
  (`src/rietx/schemas/sequential.py:125`) but leaves out the automatic profile-interval
  refits (`cr2wo6`: 873 against 1 146).
- `tests/data/planted_series/signals.json` lists 20 reseeded patterns; this tree reseeds 49 under
  the same protocol. The reseed list is the one signal
  `test_the_full_length_series_reproduces_its_committed_signals` does not pin, so nothing fails.
