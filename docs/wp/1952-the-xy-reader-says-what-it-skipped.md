# WP-1952 — the xy reader says what it skipped

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-11 — a decimal-comma file reads as a different pattern with no word, and a dropped mid-file row goes unreported; a fine step usually trips the duplicate-2θ refusal, and the reporter keeps their own reader

## Goal

`read_xy` reports every line it did not read as data after the first data
row, names the cause when it finds no data at all, and refuses a
decimal-comma file instead of reading it as a different pattern.

## Context

**The report (issue #897).** An application reads instrument formats
through rietx but keeps its own two-column reader, because "real `.xy`
files often have header lines, comment lines or comma separators that
rietx's reader rejects". It asks the reader to skip non-numeric headers and
comments, accept commas and an optional esd column, and say what it
skipped.

**Most of the ask is already there, checked at `d80ca5f4`.** `read_xy`
(`io/formats/xy.py`), the last entry in `PATTERN_FORMATS`:
- skips lines starting `#`, `!`, `'` or `/` (`:44`);
- reads commas as whitespace (`:46`);
- skips any line that does not parse as numbers (`:47-50`);
- adopts a third column as σ when any value is positive (`:79`), with
  `PATTERN_SIGMA_CONSTANT` for a constant one;
- reports numeric rows of another column count as `PATTERN_ROWS_DROPPED`.

On 24 test files a text header, a `2theta intensity` header, metadata
lines, `#` and `!` comments, commas, tabs, a trailing comma, UTF-16 with a
BOM, and an esd column space- or comma-separated all read correctly.

**What is missing, ran at `d80ca5f4`:**
1. **A decimal comma reads as another pattern, silently.** Rows
   `10,0<TAB>100` with a 1° step read as 2θ = 10, 11, 12…, intensity 0
   throughout, σ = 100, 110…, and no diagnostic. At a 0.02° step the
   duplicate-2θ refusal catches it by luck.
2. **A dropped mid-file row is silent.** `10.2 n/a` between data rows is
   skipped and the pattern has three points of four, no diagnostic.
   (`10.1 nan` reads as `y = nan`, also silently.)
3. **An inline trailing comment loses the file.** `10.0 100 # c` on every
   row raises "no numeric data found". The reader parses the first three
   tokens, and the third is the `#`.
4. **`;` separators and quoted CSV** (`"10.0","100"`) raise the same bare
   "no numeric data found", naming neither cause.

**Census.** Of the 55 repository files `identify_format` sends to `xy`, 22
have non-numeric lines before the first data row and none after it (some
of the 55 are not patterns, so the counts are approximate). A report for
lines *above* the first data row would fire on those 22 and break
`tests/test_readers_robust.py::test_a_numeric_header_row_is_dropped_and_reported_by_line`,
which pins `PATTERN_ROWS_DROPPED` alone. A report for lines *after* it
fires on none of them. A header above the data is normal. A text line
inside the data is a lost measurement.

**Rules this meets.** A reader may repair a file only where it can say that
it did (`src/rietx/io/CLAUDE.md` § What a reader may repair, WP-1047). A
reader raises naming the file, never its parser's exception. WP-1332 (✅)
fenced "teaching `read_xy` any format": a file with a known header gets
its own reader. So reading `;` or quoted CSV in `xy` against refusing it by
name is a decision, and the fence leans towards refusing.

**Prior art.** GSAS-II keeps `G2pwd_xye` (two or three columns, comments
and headers) apart from a separate CSV importer for comma, tab and
semicolon data (GSAS-II documentation, *Importers*). Read from its
documentation only.

## Non-goals

- A CSV reader (a new format entry, if the decision below wants one).
- Reporting header lines above the first data row.
- Widening `identify_format`'s dispatch (WP-1332's fence).
- Carrying reader diagnostics into the GUI (WP-1522).

## Tasks

- [ ] Report non-numeric lines after the first data row, by line number:
      `PATTERN_ROWS_DROPPED` widened, or a sibling code (record which).
      Decide whether a `nan` or `inf` value is such a row.
- [ ] Refuse a decimal-comma file by name. Detect it where a comma sits
      between digits with no space, and every row has the same comma count.
      Test on the 1° and 0.02° steps.
- [ ] The "no numeric data found" refusal names what it saw: an inline
      comment after the numbers, a `;` separator, quoted fields.
- [ ] Decide, and record as `Decided YYYY-MM-DD:`, whether an inline
      trailing comment is stripped (a report) or refused, and whether `;`
      and quoted CSV are refused by name or read by a separate format
      entry.
- [ ] Tests in `tests/test_readers_robust.py`; every existing xy fixture
      reads unchanged with no new diagnostic.
- [ ] Skill: the diagnostics reference row for any new code. Nothing else
      expected.

## Acceptance

A decimal-comma file raises naming the separator. A text row inside the
data is reported by line. The 55 existing xy-dispatched files read with the
same arrays and no new diagnostic.

```sh
.venv/bin/python -m pytest tests/test_readers_robust.py tests/test_readers.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #897.

## Handover log

- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #897).
  Checked against the tree at `d80ca5f4`: headers, comments, commas and an
  esd column already read, and the decimal-comma misread, the silent
  mid-file drop and the bare refusal reproduce. No open WP owns it: WP-1332
  (the arity gate) is closed, WP-1522 carries reader diagnostics to the
  GUI and not their content, and WP-1315 and WP-1316 are containers.
  *Next:* task 1.
