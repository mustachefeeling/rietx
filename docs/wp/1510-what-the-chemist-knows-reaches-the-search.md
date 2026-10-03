# WP-1510 — What the chemist knows reaches the indexing search

Milestone: unscheduled · Status: 🔄 2026-10-03 — five of seven tasks landed; four acceptance rows red, the volume task waits on two papers
Track: Data and metadata in, a structure out
Depends on: — (1449 soft, the ranking this feeds; 1508 soft, the search that ran out of time)
Priority: P2 2026-09-28 — a defect that fires wrongly: sixty false impurity lines and a refused gate cost a collaborator's agent one whole earlier session, and each fix is small

## Goal

An agent starting an indexing job asks the person what cell range they
expect, or derives one from the chemistry the person already gave, and the
package carries that range into the search. The four places where the run
below lost time each tell the caller what to do next.

## Context

**Source.** `solution case 1` in the private `yue-here/rietx-corpus-map`
§ 5: an agent session of 2026-09-23/25 on rietx 1.4.0, driving a lab
capillary pattern of an unpublished layered coordination polymer. A session
six days earlier on the same pattern had ended with no reliable cell. This
file quotes what the runs did (counts, wall clock, ratios) and nothing about
the specimen (WP-1450's rule). Every count below was re-read from the
session transcript on 2026-09-28, and every code site checked on `c1bd21dd`.

**The blind search never found the cell.** With `max_d_axis=32` the engines
merged 399 lattices and abstained. The accepted cell appears only as a
declared prior, "entered unconfirmed (prior-only, after the ranked
candidates)". The person had it from electron diffraction and a hand Pawley
fit. The best blind candidate had about a third of its volume. So the
person's knowledge was the answer, and the first two messages of the session
held all of it: the formula, "no solvent by TGA and elemental analysis", two
candidate cells, and the CIF of an isostructural analogue.

**1. Ask, or infer.** The skill tells an agent how to read an indexing
answer and never tells it to ask for an expected cell range first. The rule
to add (the maintainer's, 2026-09-28): before the first search, ask the
person for a cell range or candidate cells; when they have supplied the
chemistry (formula, Z or density, solvent content), infer a volume window
from it and say so rather than asking.

**2. A volume window from the formula.** `SearchSpec.min_volume` and
`max_volume` exist (`src/rietx/schemas/indexing.py`) and nothing fills them
from chemistry. Two candidate sources, to read before citing: Kempster &
Lipson (1972), about 18 Å³ per non-hydrogen atom for organics; Hofmann
(2002), per-element volumes, which a heavy-atom compound needs. On this run
the 18 Å³ figure lands 8 % under the accepted volume per formula unit. The
window also gives a Z check. The best blind candidate implied Z ≈ 2.8, and a
candidate with a non-integer Z is flagged with that number and never removed
(the agent-first rule: report evidence, do not refuse).

**3. A prior refused at the box.** `max_d_axis` defaults to 25 Å
(`schemas/indexing.py:1198`). One axis of the person's cells was longer.
`INDEX_PRIOR_USED` (`src/rietx/indexing/priors.py:349`, level `info`)
reported "outside the declared axis range 2-25 Å — a prior never widens the
box" inside a longer message. The agent read it, raised the box by hand and
reran: 24 minutes. WP-1045 decided that a prior never widens the box. Either
keep that and make the refusal a `warning` whose suggestion names the value
to pass, or reopen 1045's decision now that a person-supplied cell has been
refused on real data. Record which, with the reason.

**4. The quality gate names the instrument last, or never.**
`INDEX_DATA_INSUFFICIENT` refused at median σ(Q)/Q = 1.05e-3 against its
1e-3 bar. Declaring the capillary's axial divergence and a realistic
starting width *before* picking brought it to 6.9e-4, and the gate passed.
The suggestion (`src/rietx/indexing/diagnostics.py:255`) names the 2θ range,
the counting time and `PEAK_MIN_HEIGHT_SIGMA`. When the instrument passed to
`pick_peaks` still has default axial divergence or an unseeded profile, the
suggestion should say that first.

**5. One line per physical peak.** `pick_peaks(...).usable()` returned 129
lines for about 50 physical ones, with three copies within 0.003° of each
other at one line. `INDEX_IMPURITY_LINES` then reported 60 observed lines no
candidate explained, most of them copies. The agent kept the best copy per
`detect_peaks` group seed. A review subagent traced the copies to shoulder
seeding (`src/rietx/indexing/peaks.py:221`, `_shoulder_seeds`); that is
**unverified**, so the first task measures the mechanism.

**6. `CellCandidate.cell` is a bare 6-tuple** (`schemas/indexing.py:936`).
The run's first indexing script called `.a` on it and raised
`AttributeError`.

**7. Two settings of one lattice.** The agent declared the electron
diffraction cell twice, once with an acute and once with an obtuse
monoclinic angle. Whether priors are reduced to one setting before they are
checked is **unverified**.

**Adjacent, not here.** Which of several cells a pattern supports is WP-1511.
The quick preset's 30 s per system ran out on the monoclinic and
orthorhombic searches here (`INDEX_SEARCH_INCOMPLETE`, then
`INDEX_BUDGET_EXHAUSTED` at 120 s); search speed is 1508 and 1509 (PR #514).

**Ranking is settled** (WP-1449, closed 2026-09-29): a reported supercell the
pattern does not support ranks directly below its parent (`supercell_refuted`).
A prior that changes the reported list changes which pairs get asked, never the
rule.

**Sites re-checked 2026-10-03 on `0303da12`**: all still hold, with line drift
(`schemas/indexing.py` `max_d_axis` now :1204 and `CellCandidate` :932,
`diagnostics.py` `INDEX_DATA_INSUFFICIENT` :327, `priors.py` refusal :237).

## Non-goals

- Widening the default box for everyone.
- Changing how candidates rank (1449).
- Any engine change. The peak list feeds every engine, so
  `tests/test_acceptance_indexing.py` still runs before close.

## Tasks

- [x] Measure where the duplicate lines come from, on a public fixture that
      reproduces them or a synthetic one built to. Then collapse to one line
      per physical peak on the path into `index_pattern`, pinned by a test
      that counts lines.
- [x] `INDEX_DATA_INSUFFICIENT`: the suggestion names an undeclared
      instrument first. Test both branches.
- [x] `INDEX_PRIOR_USED`: a prior refused at the box is reported at
      `warning` with the `max_d_axis` value to pass, or 1045's decision is
      reopened. Either way the handover records the reason.
- [ ] A volume window and a Z check from a formula: a `SearchSpec` helper,
      its volume source read and cited in the docstring, and a diagnostic
      for a candidate whose volume implies a non-integer Z (code named at
      review, with its `help.py` entry). **Blocked 2026-10-03**: neither
      paper is in the local corpus (zotero-linker, ~/Zotero, rietx-refs-misc
      checked); ask for both. No `INDEX_*` code has a `help.py` arm today, so
      "its `help.py` entry" needs a decision too.
- [x] `CellCandidate`: named accessors or a `to_cell()`. Check whether two
      settings of one lattice are merged as priors, and say so in the
      docstring.
- [ ] Manual Part 1 and `tests/api_surface.py`: every new public name
      documented (the partition fails until it is).
- [x] Skill: the ask-or-infer rule in the indexing reference, tagged
      `(Measured: solution case 1)`, inside `tests/skill_caps.py`'s budget.
- [ ] The four acceptance rows the de-duplicated line list moved
      (handover 2026-10-03): corundum indexes at c/2, its declared-shift row
      reads −0.090°, cpd-1a's shift reads −0.009°, and zircon's primitive
      twin indexes one line fewer than the centred cell. Decide each before
      this WP closes.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing*.py -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

And, recorded in the handover with counts only: `solution case 1`'s first
indexing call replayed on the new tree. The line count is within a few of
the physical lines, the refused prior's warning names the value, and an agent
given the skill asks for or infers the range before its first search.

## References

- Kempster, C. J. E. & Lipson, H. (1972). *Acta Cryst.* B28, 3674. The
  18 Å³ rule. Read before citing.
- Hofmann, D. W. M. (2002). *Acta Cryst.* B58, 489–493. Per-element
  volumes. Read before citing.

## Handover log

- **2026-10-03** — A peak list no longer offers one line twice. About a
  quarter of the lines a re-seed pass adds turned out to be a neighbouring
  group's line fitted again, so a crowded lab pattern listed up to a third of
  its lines twice, and the indexer counted the copies as impurities. They are
  now flagged and kept out of what the engines see. The cleaner list broke
  four indexing acceptance rows, because the old answers leant on the copies.
  The lane that traced them found no wrong copy kept. It found the corundum
  answer resting on one engine's random seed, and two pinned shift values that
  were artefacts of the copies. Three smaller defects from the source run are
  fixed. A refused prior now names the value to pass, a refused quality gate
  names the undeclared instrument first, and a candidate's cell reads by name.
  The volume window waits on two papers.

  *Done.* (1) `duplicate_line`: a `PeakFlag` in `PEAK_UNUSABLE_FLAGS`, set by
  `pick.flag_duplicate_lines` in `pick_peaks_with_state` and in the GUI
  editor's `_spliced` (`only=`). It marks a component of one group within
  `PAWLEY_OVERLAP_FWHM_FRAC`·FWHM of a better-measured, usable component of
  another group, and keeps it in `peaks`. `INDEXING_THRESHOLDS_VERSION` is now
  1.7. Mirrors: `help.py`, `help_keys.json`, `gui/src/lib/rxt.ts` and the
  rebuilt dist, the manual's flag table, and the regenerated skill `api.md`.
  The review subagent's shoulder-seeding guess is **refuted**: 0-1 shoulder
  seeds on every pattern. (2) `INDEX_DATA_INSUFFICIENT` leads with
  `diagnostics.undeclared_instrument` when `assess_peak_list(instrument=)`
  sees zero axial apertures or the default `ProfileTCHZ`. `index_pattern`
  passes its instrument through. (3) **WP-1045's never-widen rule is kept.**
  The box is the search the caller declared, so a prior that widened it would
  make that search depend on a guess. A refusal at the box is now a `warning`
  whose suggestion is `SearchSpec(max_d_axis=N)`, with N one ångström past the
  prior's longest axis (`PriorReport.box`). (5) `CellCandidate.a` … `.gamma`
  and `.to_cell()`. Measured: a monoclinic prior declared with β and with
  180° − β comes back as one candidate, and `INDEX_PRIOR_USED` names both
  priors. (7) The skill's §7d asks for the cell, or infers it, before the
  first search. Its 520 B was paid for by cuts in the same file.

  *Measured* (`[dev]` venv, macOS). Duplicates: on the 16 IUCr round-robin
  lab patterns, 4-35 components are flagged where any are, and `cpd-4` went
  from 113 usable lines to 78. Close pairs (< 0.02°) among usable lines fell
  from 2-26 per pattern to 0, while LaB6 and fluorite were untouched. 11-BM
  NAC keeps 10 close pairs, and they lie inside groups. Corundum's 5 flagged
  lines each sit on exactly one calculated reflection and have a twin in the
  neighbouring group, three of them at equal intensity.
  `test_acceptance_indexing.py`: 39 passed and 5 failed in 15 min. Row 5's
  usable floor counted copies and moved from 50 to 45. Rows 1-4 are still red.
  What the lane established, in its own words where unverified:
  - **Corundum c/2, and the declared-shift row.** Which copy is kept is not
    the cause: the kept copy is as close to the certificate or closer in all
    5 pairs. The lane reports that svd's seed 0 no longer finds the true cell
    while seeds 1-11 do, so dichotomy is its only finder. The c/2 cell that
    all three engines find then ranks first. My own check, svd only and
    hexagonal only, showed c/2 in the top four with and without the flag, so
    the seed claim is the lane's and not verified here.
  - **cpd-1a's shift.** Two of the five pairs behind the old −0.038° were
    copies. A separate fit of the 16 fluorite lines gives −0.0095 ± 0.0023,
    so the pinned −0.038 was the artefact.
  - **Zircon.** The centred and primitive cells are refined separately, so
    the "primitive indexes at least as many" direction can flip by one line,
    here 45 against 46.

  Lanes (trial, `/wp-lanes`):

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | model | lane $ | main $ | in-session $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | duplicate_line surface sync | 25 | 19 | 177K | 69K | 0K of 0K | 5 | 38K | 2 | 0 | sonnet-5-5 | 0.52 | 1.72 | 1.19 | -1.65 |
  | formula volume window and Z check | 35 | 22 | 250K | 70K | 0K of 0K | 19 | 21K | 2 | 0 | opus-5-5 | 0.83 | 1.33 | 1.50 | -0.77 |
  | corundum c/2 regression | 25 | 2 | 287K | 70K | 0K of 18K | 5 | 5K | 0 | 0 | opus-5-5 | 0.38 | 0.30 | 0.14 | -0.54 |
  | corundum c/2 regression | 25 | 91 | 293K | 70K | 0K of 52K | 4 | 8K | 1 | 1 | opus-5-5 | 4.99 | 0.37 | 9.39 | +4.04 |

  Kept: instrument-first gate suggestion, est 18 and took 15. Skill
  ask-or-infer rule, est 8 and took 6. Trial row: 4 lanes, 2 kept, saved
  +1.08 (+6 %). The volume lane stopped by design at the missing papers. The
  first corundum lane died on the 600 s stream watchdog during a long test
  run, so its re-dispatch was told to keep commands under 8 min. Baseline
  replay at these parameters: the selective policy (> 150K and ≥ 20 requests)
  saves 25 %.

  *Not done.* `solution case 1`'s replay: the pattern is a collaborator's
  unpublished dataset and is not in this tree. The full suite was not run,
  because the acceptance file is already known red. Main's
  `test_skill.py::…[api.md]` cap row fails at `origin/main` too, with
  `api.md` at 39 519 B against a cap of 39 500 B, and nothing here grew it.

  *Next.* (a) Decide rows 1-4. Rows 3 and 4 are assertion changes: cpd-1a's
  shift to about −0.009° with its corundum-agreement clause dropped, and the
  zircon direction check. Rows 1-2 need either an svd seed or agreement fix,
  which is an engine change and a non-goal here, or reverting `duplicate_line`
  from `PEAK_UNUSABLE_FLAGS` to a reported-only flag until that fix lands.
  That choice is the maintainer's. (b) Ask for Kempster & Lipson (1972) and
  Hofmann (2002), then do task 4 and task 6.

- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1511 to 1517. Nothing started.
