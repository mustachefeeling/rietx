# WP-2006 — Readers, crystallography and GUI codes, and the dead surface

Milestone: generality · Status: ⬜
Track: The audits
Depends on: 2001
Priority: P3 2026-10-19 — 2001 closed, so nothing blocks it; expected mostly tier 1 (records of what was done to a file); the fast one

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

- **2026-10-20, from [1986](1986-guides-and-theory-move-over-and-the-old-tree-retires.md), found while moving the manual's reference pages: declared names with no writer.** `PhaseMicrostructure.separable` and `.size_strain_collinearity` are `None` on every `RefinementResult.microstructure`; only the report's deep copy writes them (`report/__init__.py:190-212,273-274`). `ProjectFormat.refuses` is set by no registry member, and no member produces `reports_at="read"` (`io/projects/registry.py:107,128-132`). `SuggestedAction.vetoed_by`'s docstring adds "or a guard forbids it", which no code writes (`report/schemas.py:1150`; `layer2.py:1059-1062` sets it from the plan and already-free paths only). Each Reference page states what the code does today (`derived.md`, `foreign-files.md`, `report.md`); the surface walk is where write, retire or document gets decided.

- **From WP-2001 (2026-10-19, PR #1047).** The table is `src/rietx/_audit.py`; this WP's rows are the ones `_audit.WALKED` and `_audit.DEFAULT_SEATS` map to 2006, plus the codes and suggestion rows of its subsystem. Auditing a row means giving it a tier and evidence in place and deleting its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py` fails until both are done. The walk sees module-level numbers and tuples of numbers only, so a number held in a dict, list or array is audited here by hand, in `crystallography/` and the two `io/` files alike; nobody has looked yet. The GUI keeps its own copy of the correlation guard, `let guard = $state(0.98)` in `gui/src/panels/Plan.svelte` (about line 93), pinned again in `App.test.ts` and `rxt.test.ts`; the python side is now one constant, `rietx.schemas.plan.CORRELATION_GUARD`, and the GUI copy needs the dist rebuilt (`gui/CLAUDE.md`).
- **From WP-2001's generality judge (2026-10-19).** Five reader decisions sit outside the walk, which keeps the third review's exclusion of reader byte offsets: `io/formats/dif.py` `_MIN_ROWS = 3` (three hkl rows make a peak list, refused); `io/formats/peaklist.py` `_MIN_ROWS = 8`; `io/formats/gsas.py`'s 64 kB sniff bound (a larger `TIME_MAP` table falls to the `xy` reader, refused for the wrong cause); `io/formats/bruker_raw.py`'s `atol=1e-6` drive pick and its counting-time windows, which decide whether σ can be derived; and `io/formats/pdcif.py`, which drops a whole weight column on one zero weight and falls back to Poisson with no diagnostic, while `xy.py` and `chi.py` adopt any positive third column as σ. Audit them by hand, or widen `WALKED` with a reason.

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
