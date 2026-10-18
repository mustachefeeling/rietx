# WP-2005 — `refine.py`'s codes and its inline literals

Milestone: generality · Status: ⬜
Track: The audits
Depends on: 2002
Priority: P3 2026-10-18 — codes, not actions; a verdict here is a flag the caller reads, and the workaround is to read past it

## Goal

Each of the 61 diagnostic codes raised in `src/rietx/refine.py` is in the audit table with
a tier, and each inline literal that gates one (about 30) is either a named constant in the
table or recorded as tier 1. Tier-3 verdicts are demoted to `info` or removed where the
threshold was the trigger.

## Context

The rule is `../milestones/generality.md` § The rule. 2002 owns the *actions* in this file
and lands first; this WP owns the codes, which are what an agent reads.

`refine.py` is 9 587 lines and raises 61 codes (`grep -o 'code="[A-Z0-9_]*"'`, 2026-10-18).
Each has an explanation in `rietx.help.DIAGNOSTIC_HELP` (WP-1985) and a `level`. The
open's count found about 30 inline numeric literals in comparisons, two named by the
second review: `< 0.7` in the flat-plate thickness test (`ABSORPTION_PLATE_THICKNESS`,
~line 6819) and `>= 2.0` further down (~line 8467). An inline literal is invisible to
2001's tripwire, which walks module-level constants, so this WP lifts each that gates a
verdict into a named constant with its value in the table, or records why it is tier 1 (a
count, a dimension, a physical limit).

**Five codes no seam names come here too**, since each is raised beside a fit rather than
in a reader or a report: `BACKGROUND_ORDER_AT_CAP` (`background/select.py`),
`BRINDLEY_OUTSIDE_REGIME` and `MICROABSORPTION_SKIPPED` (`optimize/qpa.py`),
`DECLARED_RANGE_RESTORED` and `DECLARED_RANGE_NOT_RESTORED` (`schemas/migrate.py`). The
four in `strategy/` are 2002's.

**Families.** The size-flag thresholds are calibrated on one 1 213-record archive (~line
9069): many files, one population, one family. Count by lab, instrument and material.

**What the caller reads.** 70 of the tree's codes are not mentioned in the agent skill;
this WP's share of those is the list of codes an agent meets with no guidance. A code the
skill does not route and the explanation does not resolve is a candidate for `info`.

### Inherited

(none at filing)

## Non-goals

- The holds, releases, seeds and bound tests: 2002.
- Codes raised elsewhere: `report/` 2004; `io/`, `crystallography/`, `gui/` 2006;
  `indexing/` 2007; `sequential.py` and `multi.py` 2003; `strategy/` 2002. The five
  named above are the whole remainder.
- Rewriting an explanation's text (1985's voice stays); only `level`, the threshold and
  whether the code exists.

## Tasks

- [ ] Inventory: the 61 codes with raise site, `level`, the threshold or condition, the
      explanation's claim, whether the skill routes it, and how many tests touch it.
- [ ] The inline literals: each lifted to a named constant (table row with value) or
      recorded tier 1 with the reason.
- [ ] Tier each code per part, with evidence and families.
- [ ] The batch to the maintainer; rulings dated into the table.
- [ ] Approved demotions: `level` to `info`, or the code removed and its number kept in a
      record field; the explanation's observation sentence updated where the verdict went;
      the release notes staged for every removed code.
- [ ] Goldens re-pinned only if no further from reference (a code change moves no number;
      a lifted literal must not either, pinned by a bit-identity check before and after).
- [ ] Tests; the fast count moved by exactly the tests added.
- [ ] Skill: a row for each code that keeps a verdict and had none; the demoted ones'
      rows re-worded to the number; `diagnostics.md` kept under its cap
      (`tests/skill_caps.py`).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- `docs/milestones/generality.md`; WP-1985; WP-1076 (a declared name is a claim).

## Handover log

- **2026-10-18** — created, from the milestone's opening session, split out of 2002 on the
  second review's finding that one WP over 9 587 lines of actions *and* codes is too big
  for one session.
