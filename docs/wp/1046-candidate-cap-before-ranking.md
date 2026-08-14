# WP-1046 — The per-engine candidate cap decides the ranking

Milestone: v1.0 · Status: ✅ 2026-08-09
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

**Raising it is measured, and it is not the fix.** WP-1026 ran the benchmark's
whole manual half both ways at the package's 30 s budget — ten sets, the paper's
±1 rule:

| set | cap 12 | cap 60 |
|---|---|---|
| Bb | rank 1 (+1) | rank 1 (+1) |
| Db | rank 1 (+1) | **rank 2 (0)** |
| E | rank 1 (+1) | rank 1 (+1) |
| F | **absent (−1)** | **rank 3 (0)** |
| global | **−4** | **−4** |

Net zero, and the composition is the finding: F enters the reported list, and Db
is **displaced from first** by rivals that were admitted alongside it. So this WP
has two halves and only the first was visible from set F alone — the cap hides a
candidate the panel rates highly, *and* the merged ranking cannot hold the truth
at rank 1 once the pool grows. Fixing only the cap trades one dataset's +1 for
another's. That is the same shape as WP-1041's refuted aggregates: a margin is
comparable within a panel member, not across a pool that changed size.

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

- [x] Reproduce the budget table on one **known-cell** dataset, so the claim is
      not benchmark-specific — WP-1041 already records two datasets where the
      truth is found but does not lead (NAC rank 2, FAP rank 4), and whether
      either is the cap is unmeasured. **Measured, and the answer to the
      question as asked is no**: on both datasets under their declared system
      restrictions the cap never binds (NAC returns *two* candidates at every
      budget from 5 s to 300 s and at cap 60; FAP's units harvest 2-10 against a
      cap of 12), so neither rank is the cap and neither is a reason to retune
      `fom.py`. The cap does bind on real data, in the **low-symmetry** units —
      FAP over all seven systems: monoclinic `trial_error` 1890 → 12,
      orthorhombic 252 → 12, 86 lattices merged, 12 reported. That is why nine
      high-symmetry datasets never saw it.
- [x] Decide the *reporting* half: raise the per-engine cap, apply it after
      consensus ranks, or keep it and emit a diagnostic naming how many
      candidates were dropped. Whichever it is,
      `DEFAULT_MAX_CANDIDATES`'s docstring stops claiming it is not a ranking.
      **All three, because they are one decision**: `max_candidates` is the
      reported cap and consensus applies it; a unit hands the merge
      `ENGINE_POOL_MULTIPLE ×` that (`SearchSpec.engine_pool`); consensus scores
      the *whole* merge (`shortlist=None` — the multiplier was the same defect
      in a cheaper disguise, and on its own the pool fix left set F absent);
      and `INDEX_CANDIDATES_TRUNCATED` says what the list left out.
- [x] Then the *ranking* half, which the measurement above says cannot be
      skipped: with a larger pool the merged Borda demotes a truth it used to
      lead with (Db, rank 1 → 2). Note WP-1041 measured and **refuted** the
      obvious aggregates; this needs a panel member that separates, not another
      weighting sweep. **Measured: it is not an aggregation artefact** — on Db
      the `svd`-only candidate that displaces the truth beats it on the panel 3
      members to 2, so no re-weighting reaches it. What separates is the
      quantity the *gate* already uses and the *order* ignored: whether
      `MIN_AGREEMENT` engines found the lattice (`engines.corroborated`), as the
      ranking's primary key — **binary**, because a finder *count* is not
      comparable across systems and scores the cheap domain instead of the
      answer (task 4's default half measured that, at the cost of three rank-1
      truths, before the key was narrowed).
- [x] Re-measure the bethanechol global with both decisions in place
      (`python -m tests.bethanechol_benchmark`, ~1 h, run it alone) and the
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

**Met 2026-08-09.** Bethanechol, package defaults, `preset="full"`, 30 s per
(engine × system), darwin/arm64, `[dev,jax,torch]`:

| set | manual, before (1026) | manual, after | default, before (1026) | default, after |
|---|---|---|---|---|
| Bb | r1 (+1) | r1 (+1) | r1 (+1) | r1 (+1) |
| Db | r1 (+1) | r1 (+1) | r1 (+1) | r1 (+1) |
| E | r1 (+1) | r1 (+1) | r1 (+1) | r1 (+1) |
| F | **absent (−1)** | **r1 (+1)** | **absent (−1)** | **r5 (0)** |
| half | **−4** | **−2** | **−4** | **−3** |

**Global −8 → −5** — past DICVOL91's published −8, short of TREOR90's −4. The
composition matters more than the number: F is the one winnable set the package
did not find, in *either* mode, and it is now found in both. The six remaining
sets are −1 in both modes and in every run: unfound in manual, and in default
mode `reachable = false` (their truth leaves more lines unindexed than
`n_unindexed = 2` tolerates, which no search can fix). Only the four winnable
sets were re-run in default mode, for exactly that reason; the other six carry
WP-1026's and this session's earlier full-half runs, which agree on them.

The known-cell scoreboard (`tests/indexing_gallery.py`, regenerated from the
acceptance run): **7 first / 2 present → 8 first / 1 present**, 0 absent, 0
refused over 9.

`tests/test_acceptance_indexing.py`: **44 passed in 21:17**, darwin/arm64,
`[dev,jax,torch]` (the run *before* the fap row was rewritten was 43 passed /
1 failed in 19:12 — and that failure is what found the scoreboard move). Fast
suite **2234 passed / 5 skipped**, 3:01-3:57 across two runs, +7 tests and no
new skip. `ruff` clean; `npm --prefix gui test` 405 passed, `run check` 0
errors.

## References

- `src/rietx/indexing/engines.py` — `DEFAULT_MAX_CANDIDATES`, `rank_candidates`.
- `src/rietx/indexing/consensus.py` — the merge that re-ranks the survivors.
- WP-1026 handover, 2026-08-08 — the measurement and the sweep it came from.

## Handover log

- **2026-08-09 — closed. The cap stopped being a ranking, and agreement became
  one.** Branch `wp1046-candidate-cap`. No `### Inherited` section existed on
  arrival, so the prune was a no-op — this WP was written by 1026's reopen and
  never received a mailbox entry.

  **1. Task 1's answer is a negative, and it is worth as much as a positive.**
  Neither dataset the WP named is the cap. NAC returns exactly **two**
  candidates — the primitive description and the body-centred truth — at every
  per-unit budget from 5 s to 300 s and at cap 60 alike, so the cap cannot be
  what puts its truth second. FAP under its declared hexagonal+trigonal
  restriction harvests 2-10 per unit against a cap of 12, merges 18, reports 12
  with the truth at 4. So **no `fom.py` retuning is owed to the cap**, which is
  exactly what the WP asked before anything was touched. Where the cap does bind
  is **low symmetry**: the same FAP pattern over all seven systems at 20 s/unit
  gives monoclinic `trial_error` **1890 → 12**, orthorhombic 252 → 12,
  `dichotomy` 184 → 12 — against the hexagonal unit carrying the truth, which
  finds 10. Nine high-symmetry datasets could not have seen this; it is the same
  shape as the Rᵀ trap and the monoclinic-setting trap one rank down.

  **2. There were two truncations, and the WP could only see one.** Giving each
  unit a pool of 60 (`ENGINE_POOL_MULTIPLE = 5`) left set F **still absent**.
  The second is `rank_candidates`'s own cheap pre-rank, which keeps
  `4 × max_candidates` for the panel: at 12 that scored 48 of a 260-lattice
  merge, and F's truth was not among them. Its stated conservatism does not
  transfer to the merge layer either — it is safe against a candidate's *own*
  supercell, not against a hundred unrelated low-symmetry cells that index more
  lines than the truth. `shortlist=None` at consensus is the fix, affordable
  because what reaches consensus is already bounded by the pools. With both,
  F entered at rank 3 — exactly where WP-1026's `--max-candidates 60` sweep put
  it — and Db was displaced 1 → 2, also exactly as that sweep measured. Net
  zero, as recorded.

  **3. The ranking half needed no new figure of merit, and the measurement is
  why.** On Db the `svd`-only candidate that takes first place *beats* the truth
  on the panel — M₂₀ 10.897 vs 10.051, F_N 19.991 vs 18.868,
  `predicted_seen_fraction` 0.574 vs 0.537, against `m_rev` 2.05 vs 2.44 and
  `m_sym` 19.733 vs 21.413, both coverage fractions tied at 1.0. Three members
  to two: no re-weighting of the panel reaches it, so WP-1041's refuted
  aggregates were never the road. What separates the two is **who found the
  lattice** — the quantity the gate already treats as categorical, since `grade`
  floors fewer than two finders at `low` before a caveat is read. The list was
  ordering candidates the gate refuses to promote above the one it could: on
  seven-system FAP the six above the truth were `trial_error`-only where the
  truth was all three engines'. The key sits in the pre-rank *and* the final
  sort, because a candidate the pre-rank cuts never reaches the panel.

  **4. The key is binary, and the benchmark's other half is what proved it had
  to be.** A *count* of finders was the first implementation, and it looked like
  the graded version of the same statement. The paper's **default** mode refuted
  it in one run: with all seven systems searched, every winnable set's leader
  became an orthorhombic cell found by all three engines (V ≈ 1268-1284 Å³, 19
  of 20 lines) while the published monoclinic truth, found by `svd` +
  `trial_error`, sat at ranks **5, 3, 9 and 8** — Bb, Db and E had all been rank
  1, and only F (which WP-1026's run did not find) gained. A default half of −6
  against WP-1026's −4, and a global unchanged at −8.
  The cause is not the panel: `dichotomy` reaches the cheap orthorhombic domain
  inside its budget and never reaches the monoclinic one, so **a finder count is
  not comparable across systems** — it scores the domain, not the answer. The
  manual half, monoclinic-only, cannot see this at all, because there every
  candidate competes under the same engine coverage. The comparable statement is
  the gate's own boundary, so `engines.corroborated` is binary at
  `MIN_AGREEMENT` and `consensus.grade` now reads the same constant.

  **5. Measured, with the binary key** (package defaults, 30 s/unit,
  `preset="full"`, darwin/arm64, `[dev,jax,torch]`) — see § Acceptance below for
  the table. The six unwinnable default sets were **not** re-run: `reachable` is
  false for each (their truth leaves more lines unindexed than `n_unindexed = 2`
  tolerates), which is a property of the data and the protocol that no ranking
  change can touch, and both earlier runs scored them −1 apiece.

  **6. The known-cell scoreboard moved, and `test_acceptance_indexing.py`
  is what noticed** — the rule that says run it before closing anything that
  touches an engine, paid again. `test_the_cross_code_cell_is_found_but_not_
  ranked_first` **failed**: FAP's in-band cross-code cell is now
  `candidates[0]`, because the three cells 966-1396 ppm out that led it are one
  engine's and it is every engine's. Board: **7 first / 2 present → 8 first / 1
  present**. NAC stays second, its two candidates tying on corroboration — the
  same answer task 1 got from the other direction. The row is rewritten rather
  than relaxed, and keeps its content: the panel is untouched and still prefers
  a wrong cell, so the assertion pins *that* instead, and the refusal it was
  written about did not move (`best_or_none()` is still `None`).

  **7. One measurement trap worth carrying.** A 62-minute set-Bb run sent me
  hunting a cost regression in the ambiguity enumeration that does not exist:
  phase timing on the same set gives 39.6 + 14.7 + 43.1 s of search, 0.1 s of
  consensus and 0.2 s per ambiguity sweep. The cause was a killed foreground run
  whose python child survived the tool's SIGTERM and competed for the CPU — and
  every engine budget here is **wall-clock**, so a stray process does not slow a
  run, it *changes the answer*. Check `pgrep` before quoting an indexing timing.

- **2026-08-08** — created by WP-1026's reopen, which found it while generating
  the bethanechol score. Nothing changed in `src/`: 1026's non-goals are "no new
  engine, no new diagnostic — this WP only measures", and the fix is a design
  decision with a downstream price (validation is per candidate). The graded
  score that session reports was run at the package defaults, cap included, so
  it is a score for the package as shipped and this WP is what would move it.
