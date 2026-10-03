# WP-1510 — What the chemist knows reaches the indexing search

Milestone: unscheduled · Status: 🔄 2026-10-03 — claimed by @yue-here
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
      review, with its `help.py` entry).
- [x] `CellCandidate`: named accessors or a `to_cell()`. Check whether two
      settings of one lattice are merged as priors, and say so in the
      docstring.
- [ ] Manual Part 1 and `tests/api_surface.py`: every new public name
      documented (the partition fails until it is).
- [x] Skill: the ask-or-infer rule in the indexing reference, tagged
      `(Measured: solution case 1)`, inside `tests/skill_caps.py`'s budget.

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

- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1511 to 1517. Nothing started.
