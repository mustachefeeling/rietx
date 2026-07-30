# WP-1026 — Indexing acceptance: the bethanechol benchmark and known cells

Milestone: v1.0 · Status: ⬜ not started
Depends on: 1024 (1025 soft)

## Goal

Measured acceptance for the indexing milestone against a **published
scoreboard** and against datasets whose cells are already known here — plus the
tests whose correct answer is *"we do not know"*.

## Context

- **The bethanechol chloride benchmark is a published benchmark with published
  scores**, which no other feature in this package has had. Bergmann *et al.*
  (2004) Table 6 gives six sets of twenty 2θ values, Table 5 gives every
  program's score, and the answer is known: monoclinic **P2₁/n, a = 8.875,
  b = 16.408, c = 7.137 Å, β = 93.84°, V = 1036.9 Å³**, with M(20) = 197 and
  F(20) = 1080 on the synchrotron set.

  | set | data | difficulty |
  |---|---|---|
  | A | ICDD 43-1748 raw, λ = 1.5418 | ~0.10° zeropoint; 8 impurity lines among the first 26 |
  | B | ICDD 46-1964 raw, λ = 1.5418 | ~0.10° zeropoint; 3 impurity lines among the first 35 |
  | C, D | the same two, zero-corrected | impurities only |
  | E | laboratory X-ray, λ = 1.54056 | easy |
  | F | synchrotron, λ = 0.6995 | easiest |

  Scoring is the paper's own: **+1** correct cell ranked first, **0** in the
  top ten, **−1** not found. The paper's "First 4" row (the best of ITO,
  DICVOL91, TREOR90, McMaille) scores **+9**; "Best of all" scores **+12**.
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

## Non-goals

- No new engine, no new diagnostic — this WP only measures.
- No CI cadence change beyond adding the slow rows; price them first (below).

## Tasks

- [ ] `tests/data/bethanechol_indexing.json`: the six 20-line sets, the known
      answer, published M(20)/F(20), and a `source`/`provenance` block naming
      the paper and stating the transcription. `tests/data/README.md`
      paragraph; ATTRIBUTION.md paper citation.
- [ ] `tests/data/hl2_peaks.txt` — the abstention fixture: 74 measured peaks
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
- [ ] `tests/test_acceptance_indexing.py` (`@pytest.mark.slow`): the six
      bethanechol sets scored the paper's way, with the **global score printed
      and asserted ≥ +9** (the "First 4" bar); the A/B shift-model assertions.
- [ ] Known cells: LaB6 (`nist_srm660c_100a.cif`, certified a = 4.156780,
      all engines, `high` confidence); NAC (`11BM_NAC.fxye`, cubic + CaF₂ —
      asserts `INDEX_IMPURITY_LINES` and that **engine C succeeds with the
      impurity lines left in while A/B need their mitigations**, the documented
      reason C is in the panel); FAP (`FAP.XRA`, Cu Kα doublet — asserts fitted
      positions are **Kα1** positions against the known cell's predicted 2θ);
      the six `qarr` pure phases (R-3c, Fm-3m, P6₃mc, P-3m1, Fd-3m, I4₁/amd).
- [ ] The abstention suite: `qarr/cpd-1a.prn` (3-phase mixture) ⇒
      `best_or_none() is None`; `hl2_peaks.txt` ⇒ `best_or_none() is None` and
      the diagnostics name which systems were searched; a geometrical-ambiguity
      case where **neither** partner reaches `high`.
- [ ] The joint-criterion regression (check D): with the prior art's screen
      data, assert `predicted_seen_fraction` reorders the 390-line impostor
      (9.0 % of its own lines seen) below the 23-line truth (56.5 %).
- [ ] `tests/validation_matrix.py` rows for every new diagnostic; regenerate
      `docs/VALIDATION.md`.
- [ ] **Price the CI cost before adding it** — per CLAUDE.md the budget is a
      design input (2000 free Actions minutes/month, macOS at 10×). Record the
      measured wall clock here and put the acceptance rows on the weekly job,
      not per push.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -q          # slow
.venv/bin/python -m pytest tests/test_validation_matrix.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"        # no regressions
.venv/bin/python -m ruff check src tests examples
```

Criteria, all measured and recorded in `docs/milestones/v1.0.md`:

1. **Bethanechol global score ≥ +9**, i.e. at least the best combination of the
   four classic programs in the 2004 paper, with the per-set table printed.
2. Every known-cell dataset recovers its cell — lab data within the ±85 ppm
   radius floor, LaB6 within 3e-4 Å, NAC and FAP within their stated tolerances.
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
