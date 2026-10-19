# WP-2006 — Readers, crystallography and GUI codes, and the dead surface

Milestone: generality · Status: ⬜
Track: The audits
Depends on: 2001
Priority: P3 2026-10-18 — expected mostly tier 1 (records of what was done to a file); the fast one

## Goal

The codes raised in `src/rietx/io/` (90 `code="…"` literals, plus five the GSAS instrument
readers raise through a name), `crystallography/` (20) and `gui/` (27) are in the audit
table with a tier, and the public surface's 2 238 entries have been walked for
reachability, with the unreached ones listed for the maintainer. Inventory from
`docs/reference_pages.diagnostic_index()`, never from the literal grep (2001).

## Context

The rule is `../milestones/generality.md` § The rule. The record § Scope says the reader
codes were measured and not pruned at the open, being *records of a repair*: "I applied the
attenuator", "I snapped β to 90", "σ withheld because the scale is unknown". A record is
tier 1 by construction. This WP confirms that row by row rather than assuming it, because
"nothing wrong here" is weaker than a finding (memory `a-clear-is-weaker-than-a-finding`),
and because `io/CLAUDE.md`'s rule "a reader may repair a file only where it can say that it
did" has thresholds of its own: `CIF_ANGLE_CORRECT_MAX_DEG` (0.1°, in
`src/rietx/crystallography/cif.py`, not under `io/`) decides whether a fixed angle is
snapped or refused (WP-1028, ≤ 830 ppm in d), and that number is a tier-3 threshold under
a tier-1 action.

The GUI's 27 are HTTP error names (`NOT_RUNNING`, `PROJECT_ERROR`), not `Diagnostic`s;
they are in the 276 literals and not the 256 codes. The table's code rows are held equal
to `DIAGNOSTIC_HELP`'s keys (2001), so these get no row; the handover lists them as not
heuristics.

**The dead surface** is the API half of DESIGN.md's purpose (§ Why this package
exists: the API follows current Python practice), not the heuristics half this milestone
mostly audits; it rides here
because the walk is cheap and the seam is the same session's. 3 of 193 top-level exports are used by nothing in `src`, `examples`
or `gui`: `IndexingEvidence` (named in the skill), `CaveatEvidence`, `CandidateEvidence`
(tests only). The derived surface (`tests/api_surface.py`, `derive_surface()`) is 2 238
entries; reachability over those has not been run. This is a mechanical job for a cheap
model: for each entry, is it reached from an example, the skill, the GUI, the manual's
Part 1, or another public entry? An entry reached by tests alone is a candidate the
maintainer rules on. **The maintainer rules; this WP removes nothing** (a removed entry
fails `test_manual_api.py`'s partition until documented as removed, and the compatibility
promise stages every break).

### Inherited

(none at filing)

## Non-goals

- `indexing/`: 2007 (its own rulebook, 48 codes, 76 constants, the benchmark).
- Changing a reader's repair (the action) or `io/CLAUDE.md`'s dispatch rules.
- Removing any public entry: a follow-up WP per batch of removals, with the break staged.

## Tasks

- [ ] Inventory the 142 codes (io 90 literals plus five by name, crystallography 20, gui
      27): raise site, `level`, condition, whether it records an act or asserts a
      judgement. `LANDE_G_ASSUMED` and `MAGNETIC_ION_ASSUMED` are raised here and in
      `strategy/magnetic.py`; 2002 tiers them on both sites and this WP reads the row.
- [ ] The constants of `io/` (~30) and `crystallography/` (66 by AST), entered by 2001's
      walk: tier each, expected mostly tier 1 (byte offsets, physical limits) with the
      few thresholds named above.
- [ ] Tier each; for the few thresholds (`CIF_ANGLE_CORRECT_MAX_DEG`, the attenuator
      conventions measured per format, the axis refusal), evidence and families.
- [ ] The reachability walk over `derive_surface()`'s 2 238 entries, as a script in
      `tests/` run by hand (a Haiku-grade task: collate, do not judge), its output a table
      with one row per unreached entry and where it *is* referenced.
- [ ] The batch to the maintainer: tier-3 rows with grounds, plus the unreached-entry
      table with a recommendation per row.
- [ ] Approved demotions (expected few); rulings dated into the table.
- [ ] Tests; the fast count moved by exactly the tests added.
- [ ] Skill: `references/diagnostics-projects.md` and the io rows of `diagnostics.md`
      checked against the table; none expected to move.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py -q          # no io/crystallography/gui row at unaudited
.venv/bin/python -m pytest tests/test_readers*.py tests/test_cif*.py tests/test_gui*.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- `docs/milestones/generality.md`; `src/rietx/io/CLAUDE.md`; WP-1028, 1047, 1117 (the
  derived surface).

## Handover log

- **2026-10-18** — created, from the milestone's opening session.
