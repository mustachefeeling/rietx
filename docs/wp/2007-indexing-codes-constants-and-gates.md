# WP-2007 — Indexing: its codes, constants and gates

Milestone: generality · Status: ⬜
Track: The audits
Depends on: 2001
Priority: P3 2026-10-18 — provisional by declaration, so a verdict here already carries a caveat; several sessions

## Goal

Indexing's 48 diagnostic codes and 76 module-level constants are in the audit table with
a tier, its grading and gating rules sorted by the same rule, and the graded benchmark
run once on the final tree with its ranking unchanged or improved.

## Context

The rule is `../milestones/generality.md` § The rule. `src/rietx/indexing/CLAUDE.md`
(340 lines) auto-loads with the subtree and is the dossier; this file does not restate it.

**Why its own WP.** 16 000 lines, 48 codes, 76 constants the open's count had not
included, an hour-long benchmark (`python -m tests.bethanechol_benchmark`, run alone) and
a rule in root CLAUDE.md: run `tests/test_acceptance_indexing.py` before closing anything
that touches an engine, because a ranking regression once sat under 115 green fast tests
(WP-1030).

**What the ethos already says here.** "Never a confident singleton": `IndexingResult` has
no `.cell`, only a gated `best_or_none()`; the extinction symbol is what a powder
measures, and `determine_extinction_symbol` returns ranked classes each carrying a list.
Memory `agent-first-design-thesis`: gates report evidence, never refuse (fluorite indexed
at −5 ppm after a refusal). DESIGN.md § Rules, 1 names indexing and extinction symbols as
its examples of the second kind: the package enumerates the hypotheses, scores each with
its evidence and presents the ranking. So the questions this WP asks are narrower than
the others': which of the grading thresholds (the figure of merit bands, the `quick` preset's budgets,
the shortlist's cut) are de Wolff's and Smith–Snyder's, which are the engines' own
published defaults, and which are rietx's; and whether any gate still *refuses* rather
than reports.

**Families.** The acceptance suite's datasets and `tests/indexing_gallery.py`'s `DATASETS`
/ `TRUTHS` are the families; count by lab, instrument and material. The benchmark is a
ranking over one population and is the regression gate, not a family.

### Inherited

- **From WP-2001 (2026-10-19, PR #1047).** The table is `src/rietx/_audit.py`; this WP's rows are the ones `_audit.WALKED` and `_audit.DEFAULT_SEATS` map to 2007, plus the codes and suggestion rows of its subsystem. Auditing a row means giving it a tier and evidence in place and deleting its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py` fails until both are done. The walk sees module-level numbers and tuples of numbers only, so a number held in a dict, list or array is audited here by hand: `indexing.engines.SEARCH_PRESETS` holds the `quick` 120 s budget that way.

## Non-goals

- Engine changes, a new engine, the narrowing and prior-counting items parked in ROADMAP
  (1046 § 4).
- `IndexingEvidence` and the two unreached companions: 2006's table rules on them.
- The extinction screen's use of `_run_stage`: 2002.

## Tasks

- [ ] Inventory: 48 codes and 76 constants with raise site, condition, what it grades or
      gates, and the dataset it was measured on (the dossier names most).
- [ ] Tier each per part; de Wolff (1968) M₂₀, Smith & Snyder (1979) F_N and each engine's
      published defaults are tier 2; the rest on evidence. The `quick` preset is a
      default, and its budgets (`QUICK_TOTAL_BUDGET_SECONDS`, `DEFAULT_BUDGET_SECONDS`)
      decide what the shortlist can contain, so they are not answer-invariant: state the
      preset's kind under DESIGN.md § Rules, 1 and tier the budgets like any constant.
      Rule 1's token clause is the case for a bounded first search; the case against is a
      cell the bound leaves off the list.
- [ ] `best_or_none()`: a first-kind pick on a second-kind ranking (the record § A pick
      on top of a ranking). Confirm no default path calls it, and tier its gate as the
      margin that makes the top candidate unanimous.
- [ ] The clash table: grading × gating × the `best_or_none` gate.
- [ ] The batch to the maintainer; rulings dated into the table.
- [ ] Approved demotions; a gate that refused now reports.
- [ ] `tests/test_acceptance_indexing.py` green and the benchmark run once alone on the
      final tree, its ranking recorded against the last nightly's.
- [ ] Tests; the fast count moved by exactly the tests added.
- [ ] Skill: `references/diagnostics-indexing.md` (4 277 words) rows re-tagged per the
      table.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py -q          # no indexing/ row at unaudited
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -q
.venv/bin/python -m tests.bethanechol_benchmark                  # alone; ranking vs the nightly
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- `docs/milestones/generality.md`; `src/rietx/indexing/CLAUDE.md`; WP-1030, 1037–1042,
  1046.
- de Wolff, P. M. (1968). J. Appl. Cryst. 1, 108–113; Smith, G. S. & Snyder, R. L. (1979).
  J. Appl. Cryst. 12, 60–65.

## Handover log

- **2026-10-18** — created, from the milestone's opening session, split out of the
  readers' WP on the second review's sizing.
