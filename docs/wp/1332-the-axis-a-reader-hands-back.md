# WP-1332 — the axis a reader hands back

Milestone: unscheduled · Status: ⬜
Depends on: —

## Goal

A pattern reader that misses the header establishing its unit says so. A GSAS
file whose `BANK` record is commented out no longer comes back as a 2θ axis
100× too large in silence: the axis is checked for plausibility wherever a
reader hands one back, and the finding travels on the `diagnostics=` channel
`read_pattern` already carries.

## Context

Two reports of the same defect, one from a real archive and one from review
(issues #230, #236). A GSAS `FXYE` carries 2θ in **centidegrees**, and
dispatch goes by content rather than suffix — `identify_format`
(`io/readers.py`) asks each `PATTERN_FORMATS` entry whether it `matches`, and
the GSAS sniff is `looks_gsas` (`io/formats/gsas.py`), which tests
`_SNIFF_BANK_RE = r"^BANK\s+\d+"` in multiline mode. That is right, and
documented as such in `src/rietx/io/CLAUDE.md`. The gap is what happens when
the sniff misses: a `#`-prefixed `BANK` line fails `^BANK`, the file falls
through to the last-resort two/three-column reader `read_xy`
(`io/formats/xy.py`), the same numbers are read as degrees, and nothing
downstream doubts a pattern running to 4399.6°.

Reproduced on `main` at `754e486d`, two files differing only by a leading `#`:

```
good.fxye  [50.0, 80.0]        diagnostics []
bad.fxye   [5000.0, 8000.0]    diagnostics []
```

`provenance` is `None` in both cases. This is not hypothetical: #230 found it
as a **two-byte difference between two on-disk copies of the same
measurement** in a 2013 archive — the copy used in the published refinement
has bare header lines, its sibling in `RawData/` has `#` prepended to the
title and `BANK` lines by whatever tool wrote it out. Same point count, same
intensities; one reads 0.5–43.996°, the other 50–4399.6°.

**The io invariant this sits against** (root CLAUDE.md, `io/CLAUDE.md`): *"The
scanned axis is never trusted — most vendor files are not powder scans, so a
non-2θ one is refused by name and an unknown one says so."* Here it is
neither refused nor said. The neighbouring rule fixes the shape of the fix: a
reader may repair a stranger's file **only where it can say that it did**, and
the precedent is `CIF_SPECIES_NORMALISED` / `CIF_CELL_ANGLE_CORRECTED` — the
repair is the reader's to make, recorded as a `Diagnostic`, never a table's.

Two candidate fixes, and they are complementary rather than alternative:

1. **Treat a commented `BANK` line as a header.** `#` is a comment marker in
   most of the formats around it, and the line is still the header. Cheap,
   and closes this file's case exactly.
2. **A plausibility bound on the parsed axis, wherever a reader hands one
   back.** A 2θ column outside `[0, 180]` is not a diffraction pattern in any
   geometry. This one has value independent of the GSAS bug, and catches the
   class rather than the instance.

**Refusing outright is probably wrong** for (2): an exotic-but-real range
should still open, so the honest surface is a `Diagnostic` naming the range
*and the reader that claimed the file*, composing with `diagnostics=[]`
rather than adding a second channel. Whether a range that is arithmetically
impossible (negative, or past 180°) should refuse while a merely surprising
one reports is the one design call this WP has to take rather than reach for.

## Non-goals

- New pattern formats, and the container work (`.zip`, HDF5) — 1315, 1316.
- The GSAS **model** file family (`.EXP`/`.PRM`/`.gpx`) — WP-1118.
- Widening `identify_format`'s dispatch beyond the commented-header case.

## Tasks

- [ ] A commented `BANK` record is still a `BANK` record: `_SNIFF_BANK_RE`
      admits a leading comment marker, with a test on the two-byte-difference
      pair from #236.
- [ ] `read_pattern` checks the axis it is about to return and reports an
      implausible one by name, through `diagnostics=`; decide and record in
      the docstring which ranges refuse and which report.
- [ ] The check runs for **every** format, not only GSAS — it is a property of
      the answer, not of one reader.
- [ ] Tests: the synthetic `good`/`bad` pair from #236 verbatim (no data file
      needed), plus one per-format smoke that the guard does not fire on the
      suite's real patterns.
- [ ] Skill: the diagnostic's row in `references/diagnostics.md` (room
      enough since PR #111's split; see 1338). On this tree `references/batch.md` holds
      rows 9c.1–9c.4 only; **PR #233 (open, unmerged on 2026-09-03)** adds a
      9c.14 telling an operator to *"assert a sanity bound on every parsed 2θ
      axis"* because the package does not. If #233 has merged when this lands,
      that clause describes something the package now does — revise the row in
      the same change, all three copies via `rietx skill --install . --copy`.

## Acceptance

The synthetic pair from #236 reads the same axis from both files, or reports
by name on the one it cannot establish; no suite pattern gains a diagnostic.

```sh
.venv/bin/python -m pytest tests/test_readers.py tests/test_readers_robust.py tests/test_skill.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #230 (archive copy pair, 2013 GSAS archive), issue #236 (synthetic
  reproduction on `main` at `754e486d`).
- `src/rietx/io/CLAUDE.md` — dispatch, repairs, how to add a format.

## Handover log

- **2026-09-03** — created, from the 2026-09-03 issue triage (issues #230,
  #236 — the same defect reported twice, once from an archive and once from
  review of #233). Re-checked the same day against the tree: the sniff is
  `looks_gsas`'s `_SNIFF_BANK_RE`, the fallback is `read_xy`, and the skill
  row this file first told a session to revise (9c.14) exists only in the
  open PR #233.
