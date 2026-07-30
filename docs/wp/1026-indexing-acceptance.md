# WP-1026 — Indexing acceptance: the bethanechol benchmark and known cells

Milestone: v1.0 · Status: 🟡 in progress
Depends on: 1024 (1025 soft)

## Goal

Measured acceptance for the indexing milestone against a **published
scoreboard** and against datasets whose cells are already known here — plus the
tests whose correct answer is *"we do not know"*.

## Context

- **The bethanechol chloride benchmark is a published benchmark with published
  scores**, which no other feature in this package has had. Bergmann *et al.*
  (2004) Table 6 gives the position sets, Table 5 gives every program's score,
  and the answer is known: monoclinic **P2₁/n, a = 8.875, b = 16.408,
  c = 7.137 Å, β = 93.84°, V = 1036.9 Å³**, with M(20) = 197 and F(20) = 1080 on
  the synchrotron set.

  **Corrected 2026-07-30 against the paper itself: there are TEN sets, not six.**
  A/B/C/D are *treatments*, and each was applied to **both** ICDD entries, so
  Table 6 has ten columns and the global score runs over twenty numbers
  (ten sets × two modes), in ±20:

  | set | data | difficulty |
  |---|---|---|
  | A^a, A^b | ICDD 43-1748 / 46-1964, raw, λ = 1.5418 | ~0.10° zeropoint claimed; 8 impurity lines among the first 26 (a), 3 among the first 35 (b) |
  | B^a, B^b | the same two, lines with I ≥ 5 % I_max | zeropoint; fewer impurities, but the 20 survivors reach further in 2θ |
  | C^a, C^b | the same two, zero-corrected (A − 0.100°) | impurities only |
  | D^a, D^b | zero-corrected **and** I ≥ 5 % (B − 0.100°) | easiest of the eight |
  | E | laboratory X-ray, λ = 1.54056 | easy |
  | F | synchrotron, λ = 0.6995 | easiest; the cell was refined from this set |

  Scoring is the paper's own: **+1** correct cell ranked first, **0** in the
  top ten, **−1** not found. The paper's "First 4" row (the best of ITO13,
  DICVOL91, TREOR90, McMaille) scores **+9**; "Best of all" scores **+12**.
  Individual globals for scale: ITO13 −14, DICVOL91 −8, TREOR90 −4,
  McMaille +5, Crysfire 2003 +6.
- **The 2θ values are transcribed from the published table**, with provenance
  in `tests/data/README.md` and the paper cited in ATTRIBUTION.md — **never
  code provenance** (CLAUDE.md fence). No program output is used.
- Because the sets are bare positions, they exercise
  `PeakList.from_positions(two_theta, wavelength=…, sigma=None)`, which must
  emit `PEAK_SIGMA_ASSUMED` stating the assumed value — never a silent default.
  These sets therefore also test that an assumed σ is treated as unmeasured.
- **A and B are the interesting sets**, because they are what defeated every
  classic program on default settings. Assert that `zero_model="auto"` finds
  the cell *and* `INDEX_SHIFT_DETECTED` reports ~0.10°, while
  `zero_model="none"` does not. The 2004 paper *hypothesises* that shift is a
  specimen displacement and had no way to test it — **this is the first test of
  that hypothesis**, so assert the finding either way: if the templates are not
  separable over 20 lines, the assertion is that
  `INDEX_SHIFT_MODEL_AMBIGUOUS` fires and no cause is claimed. A measured
  "cannot tell" is a result; a guess is not.
- **Lab-data tolerances are floored at the goniometer-radius systematic.**
  Measured (tag `guillemot-study`, `audit_tools.py` check A — see
  References): over 180-320 mm, Rwp moves 0.029 points (the data cannot identify
  R), specimen displacement absorbs it 4.6×, and **≈ ±85 ppm lands on the
  cell** — larger than the fit's own 1 σ. Asserting a lab cell tighter than
  that without a supplied radius is asserting noise. Synchrotron (NAC) and the
  certified LaB6 cell are not subject to it. Same reasoning CLAUDE.md already
  applies to `corundum.prn`, whose "absolute axes carry lab d-scale
  systematics".
- **Validation tiers**: `cross_code` for the bethanechol cell (a published
  solution whose protocol — same wavelength, same twenty lines — is adopted
  wholesale, per CLAUDE.md's rule about adopting a protocol rather than
  borrowing numbers), `certificate` for LaB6, `characterisation` for the
  shift-model and impurity behaviours. **No new tier is needed**, which is
  itself a check that the existing vocabulary holds.

### Inherited

From **WP-1024**: `best_or_none()` is the only singleton accessor and
`systems_searched` is on the result — the abstention tests below assert on
those, not on a `.cell` attribute that does not exist.

**From WP-1024 (landed 2026-07-30) — `index_pattern` exists, and the thing you own
is now a named, gated caveat rather than a loose observation.** Four things:

- **`high` confidence is currently unreachable on real lab data, by construction.**
  With no measured shift both engines widen their window by
  `DEFAULT_UNKNOWN_SHIFT_DEG` and the gate raises `shift_allowance_assumed`, which
  caps every candidate at `medium`. So **your acceptance bar cannot be "returns
  `high`" unless you also supply the evidence that clears the caveat** — a
  calibrated `sigma_sys_deg`, or reference positions to `assess_peak_list` from a
  certified cell. On the bundled corundum pattern you *have* a certified cell, so
  the honest protocol is: index with the assumed allowance (expect `medium` at
  best), then measure the shift against the certificate, then re-index with it
  declared. That sequence is itself the deliverable — it is what a user with a
  standard would do — and the caveat is what makes the two runs distinguishable.
  Do **not** close the gap by widening the constant or dropping the caveat; the
  +1400 ppm bias it protects against is measured.
- **The synthetic protocol to copy is in `tests/test_indexing_consensus.py`**, and
  one detail of it will bite: a cubic cell shows 15 lines to 100° 2θ and 23 to
  145°, so with `PEAK_MIN_USABLE_LINES = 20` a short pattern comes back
  `supports_indexing=False` and the run abstains **before any engine starts**. Two
  spikes were debugged before noticing the gate was working correctly. Check
  `quality.n_usable` first on any real dataset that returns nothing.
- **`predicted_but_absent` is the acceptance assertion worth building on**, not
  Rwp. Measured: an oversized cell scores Le Bail Rwp 0.379 against a correct
  0.216 — a gap smaller than the spread between specimens — while
  `predicted_but_absent` is 117/153 against 0/28. A real-data suite that asserts on
  Rwp is asserting on the weakest of the three detectors.
- **Validation costs ~0.6 s per candidate and ambiguity ~0.5 s**, on the top-3-plus-
  consensus subset (`consensus.checked_indices`). Budget a real-data acceptance
  accordingly and give it `@pytest.mark.slow`; the module fixture group name to
  follow is `indexing-consensus`'s.

**From WP-1025 (landed 2026-07-30) — the extinction screen exists, it has already
made two real-data claims, and neither is in the validation matrix.** Three things:

- **`tests/test_extinction_symbol.py` asserts on FAP and on NAC** (leading class
  `P 63 - -` listing {P 6₃, P 6₃/m, P 6₃22}; `I - - -` listing six groups including
  the true I 2₁3), marked `slow`, ~2 s each. The matrix guard only collects
  `test_acceptance_*.py`, so **those rows are invisible to `docs/VALIDATION.md`**.
  Decide deliberately: register them (they are `characterisation` claims — "the
  answer is a class, and the true group is inside it" — plus a `consistency` row
  against the GSAS-II tutorial's own space group), or state why a screen assertion
  is not an acceptance assertion. Do not leave it decided by which file it landed in.
- **The screen needs a *pattern*, so the bethanechol sets cannot run it.** Its
  evidence is a Le Bail fit's residual at forbidden positions, and those six sets
  are bare 2θ lists. The benchmark scores the cell; the extinction symbol is a
  separate claim that only your two profile datasets can carry.
- **Its cost model is the one to copy**: one shared profile fit (~2 s) plus ~0.1 s
  per class, so a hexagonal screen is 2.2 s and an orthorhombic-P one (71 classes)
  ~10 s. The module fixture group name is `extinction-symbol`.

From **WP-1023**: if its spike returned no-go and engine C was dropped, the
`found_by == all engines` assertions here are against two engines, not three.

From **WP-1018**: peak lists shared by more than one test module belong in
`tests/conftest.py` with a matching `@pytest.mark.xdist_group` on **every**
consumer — but **measure with `--durations` first**: a peak list is seconds, and
a module-scoped fixture is right when only one module uses it. Over-sharing
fails silently (a second worker rebuilds it).

**From WP-1023 (2026-07-30) — the real-data obstruction is measured, and it is
yours to close.** Running the two landed engines on the bundled qarr corundum
pattern (Cu Kα, certified 4.7593 / 12.9917 Å, R-3c, 32 fitted lines) recovered
**nothing** from either. The cause is not the search:

- fitted per-line σ has a median of **0.0056° 2θ**, while the pattern's lines sit a
  median **0.060°** from the certified cell's positions — a cos θ specimen
  displacement of −0.065°, i.e. an **11σ** systematic. At 3σ the certified cell
  indexes *zero* lines;
- both engines now add `engines.DEFAULT_UNKNOWN_SHIFT_DEG` = 0.05° in quadrature
  when no shift has been **measured** (the normal state at index time), report it
  with `INDEX_SHIFT_ALLOWANCE`, and consume `SearchSpec.shift_template` via
  `engines.refine_with_shift` to correct an accepted candidate;
- **at 0.05° that is still not enough**: trial-and-error finds nothing and dichotomy
  ranks a wrong 618 Å³ cell first. At 0.08° trial-and-error recovers a = 4.7659 Å
  against the certified 4.7593 (+1400 ppm — the shift absorbed into the cell, which
  is exactly why the template must be fitted afterwards).

So the acceptance suite's first job is not a benchmark score, it is this: **make a
certified pattern index, and record what it took.** Two routes are open and neither
has been tried — a shift-invariant matching criterion (Q *ratios* or differences
rather than absolute Q sidesteps the systematic entirely), or a two-pass search that
fits a shift from the best partial candidate and re-searches with it. Do not close it
by raising the constant until a second real pattern says the same number; one
dataset is not a calibration. The engines' synthetic recovery is solid (cubic
through monoclinic, truth ranked first, both engines) so a failure here is about the
data, not the search.

**RESOLVED 2026-07-30, and neither route was needed — the diagnosis above was
wrong.** The last sentence was the useful one: the failure was about the data, but
about the *peak list* rather than the tolerance. `detect_peaks` was correct (41
groups, **one seed each**, the real lines); `fit_group`'s ΔBIC re-seed pass then
returned **63** components, adding a phantom ~1 FWHM below every strong peak at
~10 % of its area, carrying a small esd so it read downstream as a well-measured
line. ΔBIC could not refuse it, and not because the threshold was wrong: it asks
whether the data prefer n+1 components to n, which is the same question as "is there
a line here" only while the n-component model is *capable of fitting*. On the
corundum 104 line χ²_red is 17.4 at n = 1 and 4.6 at n = 2 — both refuted, so any
extra component wins.

Ruled out by measurement before landing anything: axial asymmetry (declaring FCJ
apertures moves 63 → 56 components and takes χ²_red from 2.9 to 10.7), the width
bounds (Γ_G, Γ_L are nowhere near them), and the background envelope (it tracks the
quiet regions to a few counts). The defect is general, not a corundum quirk —
satellites were 4-21 % of picked lines across all eight bundled real datasets, worst
on lab Bragg-Brentano and least on synchrotron.

The fix is a `not_separable` flag in `pick.py` (`_not_separable`), which keeps the
component in the *model* — removing it displaces the real line by 0.010° — and bars
it from `usable()`. Measured after: satellites 0-7 %, and **both engines rank the
certified cell first** at `n_unindexed = 3` (dichotomy a = 4.7591 Å against the
certified 4.759355 — +5 ppm; trial-and-error a = 4.7631). The `n_unindexed` sweep is
itself a result and confirms CLAUDE.md's warning: at 2 neither engine finds it (the
list still carries one 5.17° edge artifact and two surviving satellites), at 3 both
rank it first, and at 5-6 dichotomy **loses it entirely** — raising the tolerance
manufactures better-scoring wrong cells. `DEFAULT_UNKNOWN_SHIFT_DEG` was not touched.

## Non-goals

- No new engine, no new diagnostic — this WP only measures.
- No CI cadence change beyond adding the slow rows; price them first (below).

## Tasks

- [x] `tests/data/bethanechol_indexing.json`: the **ten** 20-line sets, the known
      answer, published M(20)/F(20), Table 5's scores, and a `source` block naming
      the paper and stating the transcription. `tests/data/README.md`
      paragraph; ATTRIBUTION.md paper citation.
- [x] `tests/data/hl2_peaks.txt` — the abstention fixture: 74 measured peaks
      from a genuinely unidentified pattern. Extract it from the pinned study
      commit; **the study branch is not merged into `main` and must not be**:

      ```sh
      git show guillemot-study:studies/guillemot/out/HL2-1_peaks.txt \
          > tests/data/hl2_peaks.txt
      ```

      This is the **only** artifact the indexing WPs take from that study —
      everything else there is read in place as corroboration. Provenance for
      `tests/data/README.md`: derived from `HL2-1_2.xy` in the `examples/`
      folder of datalab-org/guillemot (MIT), which is *not* vendored here; the
      peak table is our own derived product, carried with attribution, and the
      pattern it came from is unidentified — that is the point of the fixture.
- [~] `tests/test_acceptance_indexing.py`: landed with sixteen fast rows and
      three `slow` ones. The A/B shift-model assertions are **done** and are the
      strongest thing in the file. The **global score is not reported, and that
      is a measured no-go** (see the handover log, 2026-07-30): the paper's own
      monoclinic domain does not finish inside any budget tried, and a score over
      a narrower domain is not comparable with Table 5.
- [~] Known cells: **corundum done, and done twice** (SRM 676a: nothing declared
      ⇒ trigonal R ranked first at a +101 / c +16 ppm; `shift_template` declared ⇒
      −73 / −126 ppm with the specimen displacement recovered from the pattern.
      Graded `low` both times, on four caveats that each name something real).
      **LaB6 done** (SRM 660c: cubic P ranked first at a −127 ppm as picked,
      `predicted_but_absent` **0 of 30** — the control that makes the corundum
      caveat mean what its name says; and −2 ppm at `high` with zero caveats once
      the tail components are out and the systematic is measured, the first
      `high` and the first non-`None` `best_or_none()` on real data).
      Not done: NAC (`11BM_NAC.fxye`, cubic + CaF₂ —
      asserts `INDEX_IMPURITY_LINES` and that **engine C succeeds with the
      impurity lines left in while A/B need their mitigations**, the documented
      reason C is in the panel — note engine C was a no-go, so restate this row
      against two engines); FAP (`FAP.XRA`, Cu Kα doublet — asserts fitted
      positions are **Kα1** positions against the known cell's predicted 2θ);
      the six `qarr` pure phases (R-3c, Fm-3m, P6₃mc, P-3m1, Fd-3m, I4₁/amd).
- [~] The abstention suite: **`qarr/cpd-1a.prn` done**, and the
      **geometrical-ambiguity case is done** — and it landed on real certified
      data rather than synthetically, which is stronger than planned: cubic P *a*
      and tetragonal P (a/√2, a) are **exactly** isospectral (2(h²+k²)+l² and
      h²+k²+l² represent the same integers), both engines find the rival, and
      neither partner reaches `high`. It also exposed that the enumeration cannot
      see the pair from the cubic side at all — filed to
      [1028](1028-robustness-external-data.md). Not done:
      `hl2_peaks.txt` ⇒ `best_or_none() is None` and
      the diagnostics name which systems were searched.
- [ ] The joint-criterion regression (check D): with the prior art's screen
      data, assert `predicted_seen_fraction` reorders the 390-line impostor
      (9.0 % of its own lines seen) below the 23-line truth (56.5 %).
- [x] `tests/validation_matrix.py` rows for every landed row; `docs/VALIDATION.md`
      regenerated (39 → 43 claims), plus a `bethanechol` dataset entry and a
      `SUITE_INTROS` paragraph.
- [x] **Price the CI cost before adding it** — per CLAUDE.md the budget is a
      design input (2000 free Actions minutes/month, macOS at 10×). **Done, and
      it needs no cadence change**: the rows are `slow`, so `ci.yml`'s per-push
      `-m "not slow"` never sees them and only `weekly.yml` runs them.
      `test_acceptance_indexing.py` is **3:30 serial** (cpd-1a 106 s, corundum
      52 s twice), and the weekly job's billed 45 minutes is set by the
      `stephens-brucite` and `qpa-sample1` groups, both several times longer,
      so this does not move it. Re-price if a row is added outside
      `xdist_group("indexing-acceptance")`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -q          # slow
.venv/bin/python -m pytest tests/test_validation_matrix.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"        # no regressions
.venv/bin/python -m ruff check src tests examples
```

Criteria, all measured and recorded in `docs/milestones/v1.0.md`:

1. **Bethanechol global score**, with the per-set table printed. **The bar is
   restated (2026-07-30, see the handover log):** the original "≥ +9" is Table 5's
   `first_4` row, which is an *oracle over four programs* rather than any
   program's score — no entry in Table 5 reaches +9, the individual globals being
   ITO13 −14, DICVOL91 −8, TREOR90 −4, McMaille +5 and Crysfire 2003 +6 (itself a
   suite). Grade against the individual globals; keep `first_4` and `best_of_all`
   as context. **Blocked on [1029](1029-engine-scaling-low-symmetry.md)** — the
   paper's own monoclinic domain does not finish, and adopting a protocol means
   adopting it whole.
2. Every known-cell dataset recovers its cell — lab data within the ±85 ppm
   radius floor, LaB6 within 3e-4 Å, NAC and FAP within their stated tolerances.
   **Corundum done** (2026-07-30, third session), and its numbers sit where that
   floor predicts rather than inside it: +101 / +16 ppm with nothing declared and
   −73 / −126 ppm with the shift template declared, against a ±85 ppm systematic
   the data cannot resolve. Both rows therefore assert at **150 ppm** — a bar
   above the floor, because a tighter one would be asserting noise, and the
   context paragraph on the goniometer radius is what sets it.
3. Every abstention test returns `None` rather than a ranked cell.

Quote wall clock as a **range**, never a figure (CLAUDE.md).

## References

- Bergmann, J., Le Bail, A., Shirley, R. & Zlokazov, V. (2004).
  *Z. Kristallogr.* **219**, 783-790 — Tables 5 and 6, and the scoring rules.
- Altomare, A., Cuocci, C., Moliterni, A. & Rizzi, R. (2019). IT Vol. H
  ch. 3.4, pp. 270-281.
- `tests/data/README.md`, `tests/validation_matrix.py`, `docs/VALIDATION.md`.
- Prior art at the tag `guillemot-study` (**not merged into `main`**):

  ```sh
  git show guillemot-study:studies/guillemot/out/audit_full.txt   # §A, §D
  git show guillemot-study:studies/guillemot/audit_tools.py       # the harness —
      # synth_peaks() builds a peak list from a space group + cell, which is
      # what several synthetic tests here need; best_scores() is the §C scorer
  git show guillemot-study:studies/guillemot/match_hl2.py         # the §D screen
  git show --stat guillemot-study                                 # everything else
  ```

## Handover log

- **2026-07-29** — created from the indexing plan. The bethanechol benchmark
  is the reason this milestone can be graded rather than merely demonstrated:
  it is the only published, scored benchmark available to any feature in this
  package.

- **2026-07-30** — the paper arrived, and the WP turned out to be about the peak
  fitter. Session ran on branch `worktree-indexer`.

  **Done.** The benchmark is transcribed and *verified* (`bethanechol_indexing.json`
  + `tests/test_acceptance_indexing.py`, 16 fast rows + 3 slow); the HL2-1
  abstention fixture is extracted; the certified corundum pattern indexes end to
  end and is graded honestly; the validation matrix carries 8 new rows
  (`docs/VALIDATION.md` 39 → 43 claims). Fast suite **1346 passed / 66 skipped in
  ~48-149 s**; the acceptance file alone is **~120 s**, dominated by two module
  fixtures (corundum 35 s, cpd-1a 84 s, both `xdist_group("indexing-acceptance")`).

  **Four things the next session needs, in order of how much they change the plan.**

  1. **The WP's founding fact was wrong in a way worth understanding.** Table 6
     has **ten** columns, not six: A/B/C/D are *treatments* and each was applied to
     *both* ICDD entries, so the global score runs over twenty numbers in ±20. The
     WP context section is corrected. Table 5 was reconstructed from a garbled
     conversion and checked: the two rows we are graded against sum to exactly the
     published +9 and +12, which is what makes the reconstruction trustworthy.

  2. **The real-data obstruction was never the tolerance, and WP-1023's diagnosis
     is corrected in place** (`DEFAULT_UNKNOWN_SHIFT_DEG`'s docstring keeps its
     numbers and loses its attribution). `detect_peaks` was right — 41 groups, one
     seed each; `fit_group` returned **63** components, adding a phantom ~1 FWHM
     below every strong peak at ~10 % of its area with a small esd. ΔBIC could not
     refuse it, and not because 6.0 is wrong: ΔBIC asks whether the data prefer
     n+1 components to n, which is the same question as "is there a line here" only
     while the n-component model can fit at all. On the corundum 104 line χ²_red is
     **17.4 at n = 1 and 4.6 at n = 2** — both refuted, so any extra component wins.
     Ruled out first, each by measurement: axial asymmetry (declaring apertures
     gives 63 → 56 and takes χ²_red 2.9 → 10.7), the width bounds (nowhere near
     them), the background envelope (tracks the quiet regions). General: satellites
     were **4-21 %** of picked lines on all eight bundled real datasets, now 0-7 %.
     The fix is `not_separable` (`indexing/pick.py::_not_separable`,
     `PEAK_REFUTED_SIGMA`) — three conditions, of which the third (the fit is still
     refuted) is load-bearing. The component stays in the *model*, because removing
     it displaces the real line by 0.010°.

  3. **The global score is a measured no-go, not an unfinished row**, and it should
     not be attempted again without changing the engine. The paper's manual-mode
     domain is monoclinic, V 800-1200 Å³, axes 5-20 Å; adopting a protocol means
     adopting it whole, so a score over a narrower domain is not comparable with
     Table 5. On set F — the *easiest* of the ten, M(20) = 197, every line explained
     by the published cell — dichotomy returns **0 candidates and
     `complete=False`** at 240 s for `n_unindexed` 0 and 2 and at **900 s** in
     manual mode; trial-and-error returns 12 without the truth. An incomplete
     search says nothing (`search_complete`), so this is about cost. The tolerance
     was excluded: σ 0.02 → 0.005° takes median σ(Q)/Q from 4.4e-3 to 1.1e-3 and
     changes nothing. **What to try next is engine work, not acceptance work** —
     the domain is four free metric parameters and the dichotomy explores it
     breadth-first; the paper's own successful programs on this set are index-space
     (ITO) and Monte-Carlo (McMaille), neither of which this package has, and
     WP-1023 already closed the Monte-Carlo door. Consider this a WP-1021/1022
     scaling question and give it its own row.

  4. **Two open items are decisions, not work.** (a) *WP-1025's inherited
     question, answered:* the FAP and NAC extinction-screen assertions **are**
     acceptance-grade claims and belong in the matrix; the reason they are not in
     it is purely that the guard collects `test_acceptance_*.py` and they live in
     `tests/test_extinction_symbol.py`, which also holds unit tests. The mechanism
     is to *move those two tests* into the acceptance suite, not to widen the
     collector — widening it would demand matrix rows for unit tests. Not done.
     (b) `SearchSpec.shift_template` appears not to reach the reported candidate:
     declaring `"cos_theta"` or `"constant"` on the corundum run left the rank-0
     candidate with `shift_template=None` and an unchanged +2799 ppm c-axis, even
     though `refine_with_shift` is wired into both engines. Either it declines
     silently or the ranked candidate takes a path that skips it. **Check this
     before building anything on `refine_with_shift`** — it is the mechanism the
     whole "measure the shift, then re-index" protocol rests on.

  **Also landed, and it is a second latent defect this WP found rather than
  caused:** `assess_peak_list` abstained on median σ(Q)/Q without asking where σ
  came from, so **all ten benchmark sets were refused** — including the synchrotron
  one whose published M(20) is 197 — on the strength of `PEAK_ASSUMED_ESD_DEG`, a
  number this package chose. The test is now conditioned on `source == "fitted"`.
  The figure is still computed and reported; it simply does not get a vote.

  **Not started:** LaB6/NAC/FAP/six-qarr known cells, the `hl2_peaks` and
  geometrical-ambiguity abstention rows, the check-D joint-criterion regression,
  and the CI pricing. The CI decision is *nearly* free to take now: the acceptance
  file costs ~120 s locally, so it belongs on the **weekly** job, and the two
  module fixtures must keep their `xdist_group` or a second worker rebuilds an
  84-second search.

- **2026-07-30 (second session, assessment + papers)** — no acceptance rows were
  added. The session read seven supplied papers against the tree and found three
  defects, one of which **invalidates an assertion this WP landed**. One is fixed;
  two are not. Read this before adding any row.

  **1. Open item (b) is answered, and the answer is worse than "it doesn't reach
  the candidate".** `SearchSpec.shift_template` *does* reach both engines — that
  part of the plumbing is fine. Traced on the corundum run with
  `shift_template="cos_theta"`: `refine_with_shift` was called **17 times** inside
  dichotomy and **declined 9 of them**, every decline on the `chi2_red`
  comparison. Where it is kept it works beautifully — a fitted shift of
  **−0.0606°**, against the independently measured −0.065° specimen displacement,
  puts a hexagonal/trigonal-P candidate at a = 4.75901 (−73 ppm) and c = 12.99067
  (−126 ppm) from the SRM 676a certificate. But the candidate ranked **first** is
  one of the declines (χ²_red 1.5829 → 1.5945 for a −0.017° shift) and keeps
  c **+2799 ppm** out. The reported answer is identical to five decimals with the
  template set to `None`, `"cos_theta"` or `"constant"`.

  **The cause is that χ²_red is the wrong accept test for a shift column**, and it
  is this WP's own ΔBIC lesson one rank up. A cell that has already absorbed the
  shift fits well, so the column cannot improve χ² much while always costing a
  degree of freedom — so it is refused *precisely* on the candidates that need it
  and accepted on the ones that need it least. A declared shift template is the
  caller's physics, like `Geometry.mu_t`, not a fitted hypothesis, and a fit
  statistic should not be its gatekeeper (v0.5's method result, again).

  **Consequence for this WP, and it is the uncomfortable part.**
  `test_a_certified_lab_pattern_indexes_and_is_graded_honestly` asserts
  `1e-3 < dc < 5e-3` and its docstring calls that "a characterisation of what an
  uncalibrated lab pattern costs". **It is not** — it is an artifact of the accept
  rule, and the accurate cell was in the engine's own candidate list all along.
  Do not treat that assertion as a protocol until the accept rule is decided; when
  it is, the row needs rewriting rather than retuning, and the honest version
  measures the *shift-refined* candidate against the certificate.

  **2. A latent defect in the volume envelope, found by checking Smith (1977)
  against the code — and the roadmap's premise about that paper was false.** The
  paper is **triclinic-only** and publishes **no per-system factors**, so
  WP-1019's open item ("a clean copy would let the derived factors be checked")
  closes as *there is nothing to check against*, not as *checked and agree*. Our
  two constants (0.60, 0.0052) are exactly the paper's and reproduce its printed
  13.39 / 17.24 / 21.32.

  What is wrong is the *status* we give it. Smith fits it by least squares and
  quotes an average discrepancy of **10.6 %**, deviations **−29 % to +32 %**, and
  names the low side as the ordinary case since it is what missing weak lines
  produce. We call it an "upper envelope" and a "bound" in code, manual and test,
  and the engines use it as a **hard search ceiling**. With p the detected
  fraction of possible lines, V_bound/V_true = 1.4025·p, so it **excludes the true
  cell below p = 0.713** — and 1 − 0.713 = 28.7 % is Smith's own worst case. Zero
  margin against the worst pattern in his own calibration set. Two aggravations:
  `VOLUME_ENVELOPE_SLACK = 1.5` exists but is applied only in `consensus.py` to
  *flag* a found candidate, while the fatal use (`dichotomy.py:487`,
  `trial_error.py:274,455` → `SearchSpec.volume_limit`) takes the raw envelope;
  and `test_volume_envelope_contains_the_true_volume` feeds
  `generate_reflections`, i.e. a **complete** line list at p = 1.0, the single
  most favourable regime, so it cannot see this. Also worth knowing: this WP's own
  satellite screen **tightened** the bound, because removing phantom lines shrinks
  d₂₀.

  Docstrings and the manual are corrected to say "estimate" with the numbers;
  **the behaviour is not changed** — applying the slack at the ceiling is a
  decision about search scope and is filed as [1029](1029-engine-scaling-low-symmetry.md).

  **3. Fixed: the fast suite was red, and the paper prescribed the fix exactly.**
  `test_niggli_reduction_is_unimodular_invariant` was failing (1352 passed / 1
  failed) on a hypothesis example that earlier runs had not generated — and
  `.hypothesis/` is gitignored, so CI would not have replayed it either. The
  reduced cell of (3, 3, 3, 66°, 110°, 65°) has **b = c exactly**, so Křivý–Gruber
  step A2 must break the tie on |η| ≤ |ζ|; at gemmi's default the two settings came
  back with β and γ *swapped*, and gemmi's own `is_niggli` called both True. gemmi
  defaults to an **absolute** ε = 1e-9; Grosse-Kunstleve *et al.* (2004) prescribe a
  **relative** ε = 1e-5·V^(1/3) used in the reduction *and* in the predicate, and
  report their Test 3 — which *is* this test — failing at 1e-10 and passing at
  1e-5. `NIGGLI_EPS_RELATIVE` in `reduce.py`. Suite now **1353 passed / 66 skipped**.

  **What the papers changed elsewhere**, all filed in
  [1029](1029-engine-scaling-low-symmetry.md) rather than here: the monoclinic
  benchmark score is confirmed as engine work with the cause now *measured* (the
  volume window prunes nothing until the last of four dimensions is cut; 5.7 M
  boxes, budget expiry, not the frontier cap); Louër & Louër's Table 1 is
  transcribed there; and Oishi-Tomiyasu (2013) closes two of WP-1020's four
  deferred figures of merit.

  **One correction to this WP's own acceptance criteria before anyone grades it.**
  Criterion 1 asks for a global score **≥ +9**, glossed as "the best combination of
  the four classic programs". That gloss is right and the bar is therefore
  mis-set: `first_4` is an **oracle over four programs**, not any program's score.
  The individual globals in Table 5 are ITO13 **−14**, DICVOL91 **−8**, TREOR90
  **−4**, McMaille **+5**, Crysfire 2003 **+6** — and Crysfire is itself a suite
  running several programs. So as written the criterion asks a two-engine package
  to beat a four-program oracle when the best single entry manages +6. Restate it
  against the individual globals, keep `first_4`/`best_of_all` as context, and
  grade only once 1029 lands.

  **Next:** unchanged from the previous entry (LaB6/NAC/FAP/qarr known cells, the
  two abstention rows, check-D, CI pricing), plus: decide the `refine_with_shift`
  accept rule, then rewrite the corundum assertion around it.

- **2026-07-30 (third session) — the accept rule was decided, and it was not what
  had been costing the corundum row its accuracy.** Three defects, each measured on
  the certified pattern, each now fixed; the row is rewritten around the corrected
  answer and a second row added. Branch `worktree-indexer`.

  **1. The +2799 ppm was a hash, not a shift, and the previous entry's diagnosis is
  withdrawn.** The whole trigonal-R domain on this pattern converges to **eleven
  leaves**. `_box_key` — the crude pre-filter that stops one cell being refined once
  per sibling leaf — divided A..F by `max|af|`, so a 0.1 % grid on the largest
  component was a **~1 %** grid on the smallest, and for a long axis C = 1/c\*² *is*
  the smallest. Three of the eleven hashed onto a sibling and were **skipped before
  being refined**, and one of the three held the certificate's c. The leaf refined
  in its place is the +2799 ppm answer, with a to −64 ppm because a is where the
  grid was fine. Binned per component now (log for the diagonals, partner-scaled by
  the Cauchy-Schwarz partners for the off-diagonals). Cost: 11 refinements against
  8, and the four-system corundum run 33 s → 47 s.

  **It took a leaf-by-leaf trace to find, and that is the transferable part**: a
  skipped leaf leaves no trace anywhere — no candidate, no diagnostic, nothing in
  `stats`. The probe that found it logged `_box_key` and `_accept` in one stream and
  looked for a key with no refinement after it. Three earlier probes (box prunes,
  `_accept`'s reject reasons, the assign-refine trajectory) all came back clean,
  because the box containing the truth *did* survive every prune.

  **2. The FoM panel ranked in a window the search never used.** `rank_candidates`
  and `to_cell_candidate` matched at the *fitted* σ while the engines that produced
  those candidates matched at σ ⊕ the systematic allowance — 0.0045° against
  0.0502° here. So `indexed_fraction` read **0.11-0.20** on candidates the search's
  own assignment indexed at **0.65-0.89**; every candidate on this pattern was
  refuted by `indexed_fraction_low` whatever its merit, and the Borda order was
  decided among cells that had all matched almost nothing. `fom_panel` now takes
  `q_match` separately: the three coverage members widen, M₂₀ and F_N keep the
  measured σ for their discrepancy floor (an *assumed* allowance must never become
  the resolution limit), and the default is the identity every published comparison
  uses. This is CLAUDE.md's headline indexing rule one rank up, and it had been
  broken in the ranking the whole time.

  **3. The accept rule, decided: only identifiability refuses a declared template.**
  χ²_red was the wrong test for the reason the previous entry gives, and that
  reasoning stands. What does *not* stand is that it was losing the accurate cell —
  with the hash fixed, the χ²-gated rule and the always-apply rule return the **same
  answer** on this pattern, differing only among the also-rans. So the change ships
  on principle with a measurement showing it is inert, which is the honest way round.
  It also needs `engines.scored_positions`: a candidate carrying a shift claims the
  *corrected* lines, and scoring it against the raw ones marks it down for its own
  correction — measured, applying the template everywhere with the panel left on raw
  positions dropped the certified lattice **out of the top six** while candidates
  with sub-0.03° shifts were untouched, i.e. the panel was ranking on how little a
  candidate had been corrected.

  **The corundum row now asserts a two-call protocol, and the contrast is the
  deliverable.** Step 1, nothing declared: trigonal **R** ranked first, a **+101 ppm**,
  c **+16 ppm**, 49 of 55 lines, χ²_red 0.84, M₂₀ 22.1. Step 2, `shift_template=
  "cos_theta"`: a **−73 ppm**, c **−126 ppm**, fitted shift **−0.0606 ± 0.0138°**
  against the −0.065° displacement WP-1023 measured independently against the
  certificate, M₂₀ **76.6**, F_N 15.8 → 59.5, `indexed_fraction` 0.891 → 0.927 so one
  refuting caveat clears. The row asserts the cell and the figures of merit
  *together*, because `f_n`'s stated blind spot is that a refined shift manufactures
  a figure of merit on its own — a shift that bought M₂₀ without moving the cell is
  the failure that pairing catches.

  **4. A refuting caveat fires on correct cells, and it is not a corner case.**
  Both steps carry `predicted_but_absent = 11-12`: the R-3c c-glide, counted against
  the *lattice* R-3m, which is the only model that exists before
  `determine_extinction_symbol` runs. So any phase with space-group extinctions
  refutes its own correct cell, and `high` is unreachable for a second structural
  reason on top of `shift_allowance_assumed`. It is exactly the blind spot
  `predicted_seen_fraction`'s docstring already states, promoted into a caveat that
  refutes. Filed to [1028](1028-robustness-external-data.md) with the three things
  to know first; **not** fixed here, because the fix is running WP-1025's screen
  inside the gate, which is an integration decision with a price.

  **Also measured, not landed:** the third protocol step (measure σ_sys against the
  certificate, re-index, watch `shift_allowance_assumed` clear) works — it does clear,
  and the cell holds at −73 / −130 ppm — but the σ_sys it feeds on came from a
  hand-rolled assignment whose `fit_shift_model` output is not trustworthy (all three
  templates reported r² = 1.0000 with zero stderr and a **positive** coefficient
  against a fitted −0.06). Either `fit_shift_model` mis-handles that input or the
  probe fed it garbage; it was not worth chasing to land a row that adds a third
  50-second search. **Do not quote the 0.0445° σ_sys from that run.**

  **A third load-sensitive budget, and this one was in the library.**
  `test_a_dominant_row_is_raised_from_the_engines_own_experience` failed in the full
  suite and passed serially: `trial_error`'s dominant-zone probe capped each ladder
  rung at a hard-coded `min(budget_seconds, 10.0)` against a **4.3 s serial** cost
  for all three rungs, so under `-n auto` the test asserted the *absence* of
  `INDEX_DOMINANT_ZONE` for a reason with nothing to do with the index table. Now
  `DOMINANT_ZONE_PROBE_SECONDS = 30.0`, named and measured, and CLAUDE.md's rule is
  extended: the budget a test depends on may be one rank down, in the library.

  **CI pricing, which closes that task rather than deferring it.** The acceptance
  rows carry `@pytest.mark.slow`, so they are **already** weekly-only — `ci.yml`
  runs `-m "not slow"` per push and only `weekly.yml` runs the full suite — and no
  cadence change is needed or wanted. The price: `test_acceptance_indexing.py` is
  **3:30 serial** (cpd-1a 106 s, corundum 52 s twice), up from ~120 s, all of it
  inside `xdist_group("indexing-acceptance")`. It does **not** move the weekly job's
  billed 45 minutes, because that job's wall clock is set by the longest group and
  `stephens-brucite` and `qpa-sample1` are several times longer. Full suite
  **1446 passed / 71 skipped in 8:24-9:51**, fast **1361 / 66 in 1:11-1:21**.

  **Still not started:** LaB6/NAC/FAP/six-qarr known cells, the `hl2_peaks` and
  geometrical-ambiguity abstention rows, check-D. The bethanechol global score
  remains blocked on [1029](1029-engine-scaling-low-symmetry.md). **Read the
  corundum row before adding another known-cell row** — the two-call shape it
  landed (index, then declare the systematic and index again) is what the others
  should copy, and `predicted_but_absent` will cap every one of them at `low` for
  any phase whose space group has extinctions.

- **2026-07-30 (fourth session) — the second known cell landed, and it reached
  `high`.** SRM 660c LaB6, seven rows (three `slow`), seven matrix claims.
  Branch `worktree-indexer`. Everything below was measured on that pattern.

  **1. The previous entry's advice was right and its prediction was wrong, which
  is why LaB6 was the correct next row.** It warned that `predicted_but_absent`
  would cap *every* known-cell row at `low`. LaB6 is **P m -3 m**, which
  extinguishes nothing — so it is the control that entry needed and did not have.
  Measured: `predicted_but_absent` **0 of 30**, `predicted_seen_fraction`
  **1.000**, against corundum's 11-12 and 0.86. The caveat means exactly what its
  name says and is not a proxy for cell size, so WP-1028's inherited note is now
  confirmed rather than argued. **Pick the next known-cell dataset by its space
  group, not by its convenience** — the pairing is what turned an argument into a
  measurement, and Fm-3m fluorite among the six qarr phases is the next such
  control (F-centred: absences from the *lattice*, which the candidate's centring
  already models, so it too should read 0).

  **2. As picked, the cell is −127 ppm out, and the cause is six components of
  our own peak list again — but not the same six, and not for the same reason.**
  WP-1026's earlier `not_separable` screen fixed corundum by flagging satellites
  inside a neighbour's profile. Here thirteen weak components face that screen,
  seven are flagged, and the six survivors fail **three different conditions**:
  four are *too far* (1.73-2.99 fitted FWHM against `PEAK_SATELLITE_NEAR_FWHM` =
  1.5), one fails `reseeded()` because the detection seed slid into the tail and
  the *new* component took the real line (the slot labels end up the wrong way
  round), and one sits on a group whose fit is **not refuted** (χ²_red 1.38),
  which the screen's docstring calls a deliberate keep. **So there is no knob**:
  widening 1.5 reaches four of six. The census is pinned as a table in
  `test_the_unflagged_tail_components_escape_for_three_different_reasons` so the
  fix has something to move.

  What they *are* was settled by looking rather than by arguing (a six-panel plot
  of the groups, and it is worth redoing rather than trusting this paragraph):
  **five are axial-divergence tails** — below 90° they sit on the low-2θ side, above
  it on the high side, and nothing else in a Bragg-Brentano pattern reverses sign
  there — and **one is a Kα2 residual**, sitting on a group-mate's *resolved*
  second line. That last one is its own small finding: `detect_peaks` drops 23
  Kα2 aliases correctly (`PEAK_KALPHA2_ALIAS`), and then `fit_group` re-creates
  one as a component at 3 % of the parent's area, because the group window spans
  the resolved doublet. The alias screen runs at detection; the fitter is
  downstream of it.

  **3. The mechanism that makes them fatal is the more general result, and it is
  about the allowance rather than the peaks.** `fit_shift_model` weights each line
  by its **own** fitted σ, and the tail components carry σ ≈ 0.005° against the
  real lines' ≈ 0.0005°, so they are down-weighted a hundredfold and the screen
  recovers the displacement anyway: **+0.0367 ± 0.0015°** against a
  *parameter-free* prediction of **+0.0415°** from the CIF's own −0.07877 mm at
  R = 217.5 mm. The **search** cannot, because `DEFAULT_UNKNOWN_SHIFT_DEG` = 0.05°
  is added *in quadrature to every σ* — a flat addition, which takes that 100×
  contrast to **1.005** — and its fitted shift is +0.009 ± 0.016°, consistent with
  none. **An assumed allowance is not free even when it is generous enough**: it
  buys a matching window at the price of the relative weighting the peak fitter
  measured, and if it is ever revisited the question is its *shape* (a
  multiplicative widening preserves the ordering) as much as its size.

  **4. `high` is reachable on real data, and the number is worth the row.** With
  the five off-lattice components out and the systematic measured rather than
  assumed: **a = 4.156772 Å, −2 ppm** from the certification CIF's own cell for
  this block, M₂₀ **1113**, **zero caveats**, `confidence == "high"` and
  `best_or_none()` returning a cell — both firsts. It is an *attribution probe,
  not a protocol*, and the row says so twice: the off-lattice components are
  identified **using the certificate**, which no user of an unknown phase can do.
  What it establishes is that the pipeline's arithmetic is sound to the part per
  million and that **what stands between it and a blind certified answer is a peak
  list** — which is why item 2 is the deliverable and not a footnote.

  **5. A trap worth knowing before writing any "calibrate, then index" protocol.**
  The obvious number to declare is `ShiftScreen.sigma_sys_deg` — the scatter the
  winning template *leaves*, 0.0078° here. Declare it as
  `SearchSpec.sigma_sys_deg` and the search returns **no candidate at all**,
  because it matches **uncorrected** positions: `refine_with_shift` fits the
  template only after a candidate survives, so the window still has to span the
  shift itself. What works is the shift's **amplitude** (0.037°). The two are
  4.3× apart, carry the same name, and the failure is silent. Filed to 1028 with
  the two fixes worth considering (rename one, or let a declared template correct
  the observed positions before matching).

  **6. The geometrical-ambiguity row landed, and it is exact rather than
  approximate.** Tetragonal P at (a/√2, a) gives Q = (2h²+2k²+l²)/a², and
  **2(h²+k²)+l² represents exactly the integers h²+k²+l² does** — both miss
  precisely 4ⁿ(8m+7) — so it is isospectral with cubic P *everywhere*, not within
  a tolerance. Both engines find it on the measured pattern. And
  `ambiguity_partners` reports **0 partners from the cubic side** while finding
  the cubic from the tetragonal side (index 2, **zero** discriminating
  reflections): the enumeration walks *sublattices* of index 2-4, i.e. supercells,
  so a rival of **half** the volume is not in it at all. That one-directionality
  matters because the gate refuses `high` to a candidate with a partner — so
  whichever of an isospectral pair is the larger cell can be promoted while its
  equal cannot. Filed to 1028; the assertion in
  `test_positions_alone_cannot_separate_lab6_from_a_half_volume_rival` says in
  place that the fix is to delete it.

  **Cost, re-priced.** `test_acceptance_indexing.py` is now **5-6 min serial**
  (was 3:30): cpd-1a 106-127 s, corundum 50-63 s twice, LaB6 **20-67 s** and the
  calibrated row 4-5 s. That LaB6 spread is one fixture measured three ways on one
  machine and is the CLAUDE.md rule in miniature — quote the range. All three new
  `slow` rows are inside `xdist_group("indexing-acceptance")`, so the weekly job's
  billed 45 min does not move (it is set by `stephens-brucite` and `qpa-sample1`).
  Four of the seven rows are **fast** — they need only the picked list (~1 s) or
  no data at all — and they are the ones carrying the census and the isospectral
  arithmetic, which is the right way round: the findings are cheap to re-check.
  Fast suite **1400 passed / 66 skipped in 1:52** (+39 on the previous entry: 4
  new fast rows and 7 new matrix claims × their per-claim checks).

  **Next, unchanged except for what landed:** NAC / FAP / six-qarr known cells
  (take Fm-3m fluorite next, per item 1), the `hl2_peaks` abstention row, check-D.
  The bethanechol global score remains blocked on
  [1029](1029-engine-scaling-low-symmetry.md).
