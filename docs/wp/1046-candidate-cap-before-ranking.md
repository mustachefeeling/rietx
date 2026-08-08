# WP-1046 — The per-engine candidate cap decides the ranking

Milestone: v1.0 · Status: ⬜
Depends on: — (found by 1026's reopen; 1024 owns the consensus it feeds)

## Goal

`SearchSpec.max_candidates` stops discarding candidates the consensus panel then
rates highly — or, if the cap is kept where it is, it stops being described as
"a cap, not a ranking" and reports what it dropped.

## Context

**Measured on the bethanechol benchmark, 2026-08-08 (WP-1026's reopen), set F in
the paper's manual mode.** The published lattice is found by **both** `svd` and
`trial_error`, and when the per-engine cap is raised from 12 to 60 the consensus
panel ranks it **3rd of the merged list**. At the package default of
`DEFAULT_MAX_CANDIDATES = 12` it is **absent from the result entirely**.

| budget | 5 s | 15 s | 30 s | 60 s |
|---|---|---|---|---|
| truth's rank, cap 12 | **1** | **1** | — | — |
| truth's rank, cap 60 | — | — | **3** | **3** |

Repeat runs at one budget agree exactly, so this is not load truncation. The
score is **non-monotonic in the search budget**: more search time loses an answer
that less search time returns first, and the whole of that is the cap.

**The mechanism, from `engines.rank_candidates`.** Each engine runs the FoM panel
and Borda over *its own harvest*, then truncates to `max_candidates`; consensus
merges the survivors and ranks again. Borda is a rank-sum over the pool being
ranked, so an engine's ordering is a function of what else that engine found. A
longer search enlarges the pool, the truth falls below twelfth in **both**
engines' own orderings, and the consensus ranking — the one the package actually
reports, and the one that puts it 3rd — never sees it.

So the constant's docstring, "*a cap, not a ranking: the panel ranks, and 1024
consensus-merges*", is the thing to fix or the thing to honour. As it stands the
cap **is** a ranking, applied by the layer whose ordering the design says is not
authoritative.

Two things to know before choosing a fix:

- **Raising it is not free but is not expensive either**: at cap 200 the same set
  F run took 91.6 s against 90.7 s at cap 12 (the searches are budget-bound, and
  the panel is only computed for `shortlist × max_candidates` pre-ranked
  candidates). The costs that *do* scale with the reported list are downstream —
  Le Bail validation is priced per candidate (`consensus.checked_indices`,
  ~0.6-8.5 s each), so a bigger reported list must not become a bigger *validated*
  list.
- **This may reach the known-cell scoreboard too.** WP-1041 recorded two datasets
  where the truth is found but does not lead (NAC rank 2, FAP rank 4) and
  WP-1026's own FAP row asserts membership-and-refusal rather than rank. Whether
  any of those is the cap rather than the panel is unmeasured — check before
  re-tuning anything in `fom.py`.

## Non-goals

- Re-tuning `borda_scores` or adding a panel member. WP-1041 measured and refuted
  the aggregate candidates; this is about what the aggregate is *allowed to see*.
- Widening the validated shortlist to match. That is a cost decision of its own.

## Tasks

- [ ] Reproduce the table above from the runner
      (`python -m tests.bethanechol_benchmark --sets F --modes manual
      --budget 30 --max-candidates 60`) and on one known-cell dataset, so the
      claim is not benchmark-specific.
- [ ] Decide: raise the per-engine cap, apply it after consensus ranks, or keep
      it and emit a diagnostic naming how many candidates were dropped. Whichever
      it is, `DEFAULT_MAX_CANDIDATES`'s docstring stops claiming it is not a
      ranking.
- [ ] Re-measure the bethanechol global with the decision in place, and the
      known-cell scoreboard (`tests/indexing_gallery.py` regenerates it).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -q
.venv/bin/python -m tests.bethanechol_benchmark --modes manual
.venv/bin/python -m ruff check src tests examples
```

The truth's rank on a dataset must not *fall out of the reported list* as the
budget rises. A rank that moves is a ranking question; a rank that vanishes is
this one.

## References

- `src/pxrdref/indexing/engines.py` — `DEFAULT_MAX_CANDIDATES`, `rank_candidates`.
- `src/pxrdref/indexing/consensus.py` — the merge that re-ranks the survivors.
- WP-1026 handover, 2026-08-08 — the measurement and the sweep it came from.

## Handover log

- **2026-08-08** — created by WP-1026's reopen, which found it while generating
  the bethanechol score. Nothing changed in `src/`: 1026's non-goals are "no new
  engine, no new diagnostic — this WP only measures", and the fix is a design
  decision with a downstream price (validation is per candidate). The graded
  score that session reports was run at the package defaults, cap included, so
  it is a score for the package as shipped and this WP is what would move it.
