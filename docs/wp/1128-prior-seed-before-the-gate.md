# WP-1128 — the prior's deliberate trial runs before the ladder's gate

Milestone: v1.1 · Status: ✅ 2026-08-23 — the two red Linux nightlies diagnosed
as a load sensor, not a regression: `volume_window`'s κ probes sat between the
budget's start and its first check, so a loaded worker spent the whole budget
before the caller's stated cell got its one call. Reordered (bit-identical),
and the test that caught it stops using the clock as its starvation mechanism.
Depends on: —

## Goal

`search_svd` gives a stated prior its single deliberate trial before it spends
any of the budget on the random ladder's volume gate, and
`test_the_prior_seeds_svds_starting_basin` proves the seeding property without
a wall clock in it.

## Context

The nightly `full` job (Linux, `[dev,jax]`) went red on 2026-08-21 (8f4a5bea)
and 2026-08-22 (99226520) on one test:

```
tests/test_indexing_priors.py::test_the_prior_seeds_svds_starting_basin
AssertionError: the seeded start did not reach the stated basin — monoclinic
needs ~15k random calls (WP-1040's table), so the seed is the only way this
budget finds anything
```

Windows, macOS and the torch job were green throughout, and the full suite
passed the test locally on every run. The last green nightly was 2026-08-20
(3e1146c1), so the boundary contains the WP-1109/1111/1112/1116 merges — none
of which touches `indexing/`.

**The test's own premise was the bug.** Its docstring claimed "the first budget
check happens at zero elapsed, so the seed trial always runs". It does not.
`search_svd` starts the `Budget` before calling `_search_system`, and
`_search_system` then ran `volume_window` — `KAPPA_PROBES` probe cells, each
enumerating a reciprocal lattice to `q_max` — at the top of the centring loop,
*before* the `budget.expired()` guarding the prior loop. That window gates the
**random ladder** and is no part of a prior's trial, so the prior was paying
for it.

Measured on this machine (10-core, macOS, `[dev]`), elapsed on the budget clock
at the moment of the first `expired()` call, 30 runs:

| machine state | min | median | max | margin vs the 50 ms budget |
|---|---|---|---|---|
| idle | 2.01 ms | 2.72 ms | 9.28 ms | 5.4× |
| 40 spinners on 10 cores | 2.00 ms | 3.38 ms | **62.82 ms** | **0.8×** |

At 62.8 ms the budget is already spent: `_search_system` returns with
`calls = 0`, nothing in `found`, and the assertion above. A sweep of budgets
confirms the cliff and shows it has nothing to do with the ladder — 0.0001 to
0.002 s give `calls = 0`, 0.003 s gives `calls = 1` (the prior, and the truth),
0.005 s and up give `calls = 201` (the prior plus one ladder round).

So: a **load sensor**, exactly the shape `tests/CLAUDE.md` warns about — "a
wall-clock budget in a test is a runaway guard, never a timer". This one was a
timer, and what it timed was how busy the CI worker was. A 4-core GitHub runner
running the full acceptance suite under `-n auto --dist loadgroup` is more
oversubscribed than the reproduction above.

Two files:
- `src/rietx/indexing/svd.py` — `_search_system`, the centring loop.
- `tests/test_indexing_priors.py` — the test and its docstring.

## Non-goals

- Widening the budget, or any change to `Budget`, `estimate_ceiling` or the
  per-system ceiling contract. The ceiling is a hard ceiling and stays one.
- The nightly's ~77 min of indexing-acceptance setup (ROADMAP § Parked).

## Tasks

- [x] Hoist the prior loop above `volume_window` in `_search_system`; comment
      why the ordering is load-bearing and why it is a pure reordering.
- [x] Rewrite the test to starve the ladder **structurally**
      (`monkeypatch.setitem(CONTROL, "monoclinic", (0, 1))`), with the budget
      demoted to a 30 s runaway guard, and assert the call count so the
      starvation itself cannot rot silently.
- [x] Verify bit-identity on the indexing suites and re-measure the margin.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py \
    tests/test_acceptance_indexing.py tests/test_indexing_priors.py \
    -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

Plus the margin measurement above, re-run on the fixed tree.

## References

- Coelho, A. A. (2003). *J. Appl. Cryst.* **36**, 86–95 — the SVD search and
  the N_c/N_o gate `volume_window` implements (Table 2).
- WP-1040's corpus table — the ~15k random calls a monoclinic cell needs.
- WP-1045 — the analogue-prior rules the reordered loop keeps.

## Handover log

- **2026-08-23** — **The red nightly was never a regression; it was the test
  measuring the machine.** Anyone reading two red Linux `full` jobs before a
  release tag can now stop treating them as a blocker: the failure is fully
  explained, reproduced on demand, and fixed on both sides.
  *Done*: `volume_window` moved below the prior loop in `_search_system` — a
  pure reordering, since it draws from its own `default_rng(seed)` and its
  result feeds only `v_lo`/`v_hi`; the test starves the ladder with
  `CONTROL["monoclinic"] = (0, 1)` and keeps a 30 s runaway guard, and now
  asserts `calls == len(centrings)` so a future change that un-starves it fails
  loudly instead of quietly re-testing the random search.
  *Measured*: setup before the first budget check 2.01–9.28 ms → **0.05–0.24
  ms**, margin against the 50 ms budget 5.4× → **207×**; the load reproduction
  (40 spinners on 10 cores) reached 62.8 ms before the fix and 0.24 ms after.
  Bit-identity: the indexing engine + acceptance + priors suites, unchanged.
  *Gotchas*: the prior loop already ran ahead of the `v_lo < v_hi` `continue`,
  so nothing about which centrings get a seeded trial moved — only when the κ
  probes are paid for.
  *Next*: none; closed.  The v1.1.0 release itself is protocol step 6
  (`docs/ROADMAP.md` § Session protocol) and `docs/RELEASING.md`, not a WP —
  the 1.0.1 precedent is a plain `Version X.Y.Z — …` commit.
