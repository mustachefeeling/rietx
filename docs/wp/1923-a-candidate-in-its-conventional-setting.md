# WP-1923 — A candidate is reported as a lattice in its conventional setting, and the reduction is an exact change of basis

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1915 soft, the same file's covariance map)
Priority: P2 2026-10-08 — a monoclinic candidate read by a user or an agent as an unrelated cell (β = 81.8° for a lattice whose conventional β is 98.2°), nothing flagged, and the workaround is calling `reduce_cell` + `conventional_cell` by hand; the 797 half is a 1.2e-5 drift on one cell that `same_lattice` could read as a σ

## Goal

`index_pattern` reports each candidate in the IUCr conventional setting for its system (monoclinic: b unique, β obtuse and closest to 90°), keeps the engine's own setting and the change of basis in the record, and the Niggli-reduced form `reduction` returns is an exact change of basis of its input.

## Context

Two issues, one seam (`src/rietx/indexing/reduce.py` and how its output reaches `CellCandidate`).

**Issue #779 (mustachefeeling, 2026-10-06).** Candidates keep the engine's setting. `dedup_groups` compares on the Niggli-reduced metric, but the reported member is whichever setting the engine arrived at. The reporter saw β = 148.86°, 167.62°, 59.27° and 45.29° for one V = 224 Å³ lattice, whose conventional cell is a = 4.541, b = 4.884, c = 10.198 Å, β = 98.22°. Grades and Le Bail fits are setting-invariant. The harm is to a reader comparing against a database or `SearchSpec.prior_cells`, and to code assuming β in 90-120°. Whether the change belongs in the engines, in `consensus` or only in the report is open. The reporter proposes the report.

**Issue #797 (maintainer, 2026-10-06).** For the triclinic cell (3.0, 11.0, 14.197202585325392, 65, 65, 65), `reduction(af)` returns `(red, t)` with `t @ af` differing from `red` by (−4.0e-8, −4.0e-8, −4.0e-8, −2.5e-7, −1.2e-5, −1.0e-6) relative. `t` is an integer map, so `t @ af` is exact. `tests/test_indexing_reduce.py::test_the_reduction_map_takes_a_to_f_where_the_reduction_does` draws it from a local hypothesis database. CI draws it only by chance. `@example(3.0, 11.0, 14.197202585325392, 65.0, 65.0, 65.0)` would make CI see it.

**Traced on 2026-10-08** (gemmi, `[dev]`, macOS arm64, `scratchpad` script `trace-797.py`). Direct-space parameters out of `niggli_reduce` + `normalize` equal the exact image of the input G6 under the recorded triplet to 4e-16 at ε = 1e-12. At ε = 7.2e-5 (`NIGGLI_EPS_RELATIVE` · V^(1/3)) every parameter still equals that image except E, which has the opposite sign, with |E| = 1.75e-5 inside ε. So the drift is `normalize` choosing a sign for a parameter it treats as zero. Flipping one sign is not a change of basis. `reduction`'s existing row flip makes `t @ af` agree with `red` in that sign and leaves the metric one ε away from the input's. The fix is not yet chosen.

### Inherited

(empty)

## Non-goals

- Changing what the engines search or how `dedup_groups` groups. The reduced metric stays the identity.
- Choosing the monoclinic convention for the other crystal systems beyond what `conventional_cell` already does. Triclinic stays Niggli-reduced.
- Loosening `NIGGLI_EPS_RELATIVE`. Its value is the paper's (Grosse-Kunstleve, Sauter & Adams 2004) and its measurement is in the constant's comment.

## Tasks

- [ ] Add the `@example` to the existing test so CI draws the 797 cell, and confirm it fails on 5d1f5f67.
- [ ] Make the near-zero sign step an exact image: either decide the sign from the exact image of the input, or carry the ε-sized difference as a stated tolerance of `reduction` and have `same_lattice` count it. Measure how often an indexing run meets such a cell first (the 797 text says it is unmeasured).
- [ ] Decide where the conventional setting is applied (report only, per #779's proposal, or consensus). Record the engine's cell and the change of basis on `CellCandidate`, quoting the new fields from one place (WP-1076: a field's default needs its writer named).
- [ ] Report monoclinic candidates with b unique and β obtuse, closest to 90°. Cross-check against `conventional_cell` and `ambiguity.py`, which reduce independently.
- [ ] Check every reader of a candidate's `cell`: the GUI indexing panel, `evidence()`, `prior_cells` matching, `rank_of_lattice` in `tests/indexing_gallery.py`, the skill's indexing reference.
- [ ] Tests (unit/property; acceptance if this WP carries it). Run `tests/test_acceptance_indexing.py`, since the change touches consensus output.
- [ ] Skill: the indexing reference row saying which setting a reported cell is in, and where the engine's lives.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_reduce.py tests/test_indexing_consensus.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

On the 797 cell, `max(abs((t @ af - red) / red))` is under 1e-9. A synthetic P 1 2/m 1 cell of 4.541, 4.884, 10.198 Å, β = 98.22° indexed through `index_pattern` is reported with β in 90-120° (on 5d1f5f67 candidate 0 comes back as β = 81.78°).

## References

- Grosse-Kunstleve, Sauter & Adams (2004), *Acta Cryst.* A60, 1-6 (the relative ε).
- Mighell & Santoro (1975) for the setting ambiguity already named in `indexing/CLAUDE.md`.
- International Tables for Crystallography A, § 9.3 (reduced and conventional cells).

## Handover log

- **2026-10-08** — created, from the 2026-10-08 issue triage (issues #779, #797). Checked against the tree at 5d1f5f67: #797 reproduces (drift −1.15e-5 on E, −4.0e-8 on A, B, C); #779 reproduces on a synthetic P 1 2/m 1 cell of 4.541, 4.884, 10.198 Å, β = 98.22° (candidate 0 comes back as 4.541, 4.884, 10.198 Å, β = 81.78°); `git log --since=2026-10-06 -- src/rietx/indexing/reduce.py` is empty and no PR cites either issue. No open WP owns it: 1915 owns the NaN esd through `reduced_covariance` and says nothing about the reported setting or the exactness of the map, 1520 and 1510 are search cost and priors, and 1518 (closed) built `reduction`'s map and did not check it against a near-zero parameter.
