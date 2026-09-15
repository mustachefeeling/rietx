# WP-1416 — `read_xy` reads the file's shape

Milestone: unscheduled · Status: ⬜
Depends on: —

## Goal

The positional ASCII reader checks the shape of what it reads. A row whose
token count disagrees with the file's is not a data point, and a third column
that is constant on every point is reported before it becomes σ. Both land
on the `diagnostics=` channel, so a caller knows what the reader decided.

## Context

Issue #266 (2026-09-04), rietx 1.3.0, code unchanged at `origin/main`
`4a0df3d1` and on this tree. Two silent defects in
`io/formats/xy.py::read_xy`, reproduced with two inline files and no solver.

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

## Non-goals

- Teaching `read_xy` any format. A file with a known header has, or gets,
  its own reader (`src/rietx/io/CLAUDE.md` says how).
- Refusing a uniform σ.
- Reading S(Q) or G(r) as a pattern.

## Tasks

- [ ] Per-line arity kept; rows disagreeing with the modal arity dropped and
      reported by line number with the tokens seen, one diagnostic per file.
- [ ] A constant adopted σ reported, naming the column and the value; the σ
      is kept.
- [ ] `help.py` entries for both codes; the format's row in
      `src/rietx/io/CLAUDE.md` says what the reader now checks.
- [ ] Tests: the issue's two inline files, asserting the point count and the
      codes, in `tests/test_readers_robust.py`.
- [ ] Skill: a `references/diagnostics.md` row per code; none in the body.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_readers.py tests/test_readers_robust.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #266 (2026-09-04), with its `repro.py`.
- WP-1047 (a reader repairs only where it says so); WP-1029 (`sig()`).

## Handover log

- **2026-09-15** — created, from the 2026-09-15 issue triage (issue #266).
  Checked against the tree: the reader is as the issue quotes it; the
  ascending check cannot see a point below x₁.
