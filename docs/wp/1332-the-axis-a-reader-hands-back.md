# WP-1332 — what a reader hands back: the axis, the rows, the σ column

Milestone: unscheduled · Status: ⬜
Depends on: —
Priority: P2 2026-09-24 — a GSAS axis 100× too large, a phantom point at 0° and a constant column adopted as σ, each in silence; WP-1416 folded in

## Goal

A pattern reader that misses the header establishing its unit says so. A GSAS
file whose `BANK` record is commented out no longer comes back as a 2θ axis
100× too large in silence: the axis is checked for plausibility wherever a
reader hands one back, and the finding travels on the `diagnostics=` channel
`read_pattern` already carries.

The positional ASCII reader checks the shape of what it reads, on the same
channel. A row whose token count disagrees with the file's is not a data
point. A third column that is constant on every point is reported before it
becomes σ.

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

### The same class in `read_xy` (issue #266, from WP-1416)

WP-1416 was filed from the 2026-09-15 triage and folded in here on
2026-09-24. Its evidence follows unchanged. Issue #266 (2026-09-04), rietx
1.3.0, code unchanged at `origin/main` `4a0df3d1` and at `d02e3872`. Two
silent defects in `io/formats/xy.py::read_xy`, reproduced with two inline
files and no solver.

**1. A numeric header row becomes a data point.** The reader skips a line
only when it starts with `#`, `!`, `'` or `/`, then parses `parts[:3]` and
keeps any row with two floats. A header line that begins with a digit (a
detector table, an integration-limits row, a channel count) is accepted on
the strength of its first three tokens. The row's arity is discarded, and no
comparison is made against the data block below it.

```
data rows in the file : 4
points read           : 5
x                     : [0.0, 10.0, 10.1, 10.2, 10.3]
diagnostics           : NONE
```

The phantom point lands at x = 0, the worst place in a 2θ pattern: inside no
sensible range, anchoring a background polynomial at an angle nothing
measured, and below x₁, so `ascending()` (`io/formats/base.py`) has no say.
Every PDFgetX2 reduction the reporter has reads this way: four files, all
accepted as `xy` with zero diagnostics, each gaining (0.0, 1.0) from the
header's detector table (2000 points where the table holds 1999).

**2. A constant third column is adopted as σ.** The test is
`np.any(arr[:, 2] > 0)`, so a placeholder or flag column that sits third
becomes the uncertainty. An esd identical on every point is not an esd. It
gives every point equal weight, which turns a weighted refinement into an
unweighted one while the result still divides by `sig()` (WP-1029) and
reports a χ² that means nothing. Unlike a missing σ, which falls back to the
documented Poisson estimate, this one looks like data. A PDFgetX2 `.sq` has
columns `Q S(Q) d_Q d_S(Q)` with `d_Q` the constant 1.0 and the uncertainty
in column four; the reader adopts the placeholder.

**One cause.** `read_xy` is a positional reader with no notion of what a
column is. That is the right design for a two-column file and stops being
right the moment a file carries a header table or more than three columns.
Both fixes are checks on shape and need no format knowledge, and both are
reports in `src/rietx/io/CLAUDE.md`'s sense: a reader may repair a file only
where it can say that it did (WP-1047).

**The shape.** Count tokens per accepted line. A row whose arity disagrees
with the file's modal arity is dropped and reported by line number, since a
header row of six tokens above a block of two is a header and not a point.
An adopted σ that is constant across every point is reported, never refused,
because a uniform σ is legal and the caller decides whether it is a real
weighting or the wrong column. Both are `Diagnostic`s on the channel
`read_pattern` already carries.

**A note the issue does not make.** An `.sq` file's x axis is Q, and the
reader cannot tell. WP-1047's clause (4), that the scanned axis is never
trusted, cannot reach a bare two-column file, and PDF analysis is fenced
(#192). The two defects stand on any `.xy` regardless, and that use of the
reader is outside this WP.

### Why one WP

The fold was decided 2026-09-24, on a review of the open WPs for overlap.
Both halves check what `read_pattern` hands back and report it through
`diagnostics=`. They share `io/CLAUDE.md`'s repair rule, the
`test_readers_robust.py` arm and the skill's §7i. Both were P2 with no
dependency, and split they would cost two sessions for one seam.

They do not share a fixture. #236's `bad.fxye` comments out only its `BANK`
line. Its title is not numeric, and its data rows have three columns with a
varying third. So neither `read_xy` check fires on it: re-run at `d02e3872`,
it reads four points at 5000–8000° with no diagnostic. Each half keeps its own
reproduction.

Where each check lives is part of the work. The arity check can only live in
`read_xy`, since only the reader sees lines. The axis check belongs on the
post-dispatch hook below, since it is a property of the answer. The
constant-σ check could live in either place. On the hook it would reach
every format that reads a σ column, and that is the question the
generalisation task asks.

### Inherited

- **From WP-1415, 2026-09-21: a new reader diagnostic's row goes in §7i, not
  §7.** The skill's `references/diagnostics.md` was 38 B under its cap, so the
  eleven reader rows moved to `references/diagnostics-reading.md` (§7i) on the
  maintainer's criterion: the main table carries what a fit is likely to say,
  and a code conditional on a file quirk goes to a secondary doc. A reader code
  this WP adds belongs there, and `test_every_engine_diagnostic_code_has_a_protocol_row`
  accepts a row anywhere in the skill tree.
- **`read_pattern` now has a post-dispatch hook** (`_dead_channel_diagnostics`,
  `io/readers.py`), which runs after `fmt.read` and only when the caller passed
  a `diagnostics=` list. A check that belongs to every format rather than to
  one reader can hang there, which may suit this WP's axis-plausibility test.

## Non-goals

- New pattern formats, and the container work (`.zip`, HDF5) — 1315, 1316.
- The GSAS **model** file family (`.EXP`/`.PRM`/`.gpx`) — WP-1118.
- Widening `identify_format`'s dispatch beyond the commented-header case.
- Teaching `read_xy` any format. A file with a known header has, or gets,
  its own reader (`src/rietx/io/CLAUDE.md` says how).
- Refusing a uniform σ.
- Reading S(Q) or G(r) as a pattern.

## Tasks

- [ ] A commented `BANK` record is still a `BANK` record: `_SNIFF_BANK_RE`
      admits a leading comment marker, with a test on the two-byte-difference
      pair from #236.
- [ ] `read_pattern` checks the axis it is about to return and reports an
      implausible one by name, through `diagnostics=`; decide and record in
      the docstring which ranges refuse and which report.
- [ ] The check runs for **every** format, not only GSAS — it is a property of
      the answer, not of one reader.
- [ ] `read_xy` keeps per-line arity; rows disagreeing with the modal arity
      are dropped and reported by line number with the tokens seen, one
      diagnostic per file.
- [ ] A constant adopted σ is reported, naming the column and the value; the
      σ is kept. Decide whether the check runs in `read_xy` or on the
      post-dispatch hook for every format, and record the reason where it
      lands.
- [ ] `help.py` entries for every new code; the format rows in
      `src/rietx/io/CLAUDE.md` say what the readers now check.
- [ ] Tests: the synthetic `good`/`bad` pair from #236 verbatim (no data file
      needed), plus one per-format smoke that the guard does not fire on the
      suite's real patterns; #266's two inline files, asserting the point
      count and the codes. All in `tests/test_readers_robust.py`.
- [ ] Skill: one row per new code in `references/diagnostics-reading.md`
      (§7i), none in the body. PR #233 merged 2026-09-07, and its clause now
      sits in `references/batch-operating.md`: *"Assert a sanity bound on
      every parsed 2θ axis"*, beside the FXYE case this WP fixes. Once the
      axis check lands, that clause describes something the package does.
      Revise it in the same change, all committed copies via
      `rietx skill --install . --copy`.

## Acceptance

The synthetic pair from #236 reads the same axis from both files, or reports
by name on the one it cannot establish; no suite pattern gains a diagnostic.
#266's two files read the data rows only, and the constant σ column is
reported.

```sh
.venv/bin/python -m pytest tests/test_readers.py tests/test_readers_robust.py tests/test_skill.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #230 (archive copy pair, 2013 GSAS archive), issue #236 (synthetic
  reproduction on `main` at `754e486d`).
- Issue #266 (2026-09-04), with its `repro.py`.
- WP-1047 (a reader repairs only where it says so); WP-1029 (`sig()`).
- `src/rietx/io/CLAUDE.md` — dispatch, repairs, how to add a format.

## Handover log

- **2026-09-24** — WP-1416 folded in, from a review of the open WPs for
  overlap. Its Goal, Context, Non-goals, Tasks, Acceptance and References now
  live here, and its file is closed 🛑 pointing at this one. The skill task
  now names §7i and the `batch-operating.md` clause, since PR #233 merged
  2026-09-07. Re-checked at `d02e3872`: `_SNIFF_BANK_RE` and both `read_xy`
  lines are as quoted, and #236's pair still reads `[50, 80]` and
  `[5000, 8000]` with no diagnostic. Next: the first task, when a session
  takes this WP.
- **2026-09-03** — created, from the 2026-09-03 issue triage (issues #230,
  #236 — the same defect reported twice, once from an archive and once from
  review of #233). Re-checked the same day against the tree: the sniff is
  `looks_gsas`'s `_SNIFF_BANK_RE`, the fallback is `read_xy`, and the skill
  row this file first told a session to revise (9c.14) exists only in the
  open PR #233.
