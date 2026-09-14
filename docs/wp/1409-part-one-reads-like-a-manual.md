# WP-1409 — Part 1 reads like a manual

Milestone: unscheduled · Status: ✅ 2026-09-14 — all 24 chapters swept, 363 em
dashes and 400 bold marks to 0, the register guard extended to both parts, and
three reader-visible defects fixed with the guard that closes each class
Depends on: 1408 (Part 2; the guard this extends)

## Goal

Part 1 reads as prose a stranger works from: one clause per sentence, the
heading carrying the claim instead of a bold lead-in under it, and no aside
welded on with an em dash. The guard 1408 left on Part 2 covers the whole
manual when this closes, including the two zones it cannot currently see.

## Context

WP-1408 rewrote Part 2 (`docs/manual/*.md`, 19,942 words) out of the
maintainer register and left `test_part_two_keeps_the_manual_register` behind
it. Its closing entry names Part 1 as where the same leakage would be found
next, and Part 1 had never been measured.

The leakage is not a lapse anyone chose. A `CLAUDE.md` may compress, and the
corpus measures ~15.5 em dashes per 1000 words with that register working. The
rulebook sits in the same tree as the manual and gets read first, so its voice
arrives in the manual by default (`yue-prose` § Where compression is right).

### Measured before the work, on 10270192

Part 1 is `docs/manual/using/`, 24 files, 73,699 prose words. Prose here is
`_prose_lines`' definition widened: lines outside fenced blocks, code spans
stripped, with `:::` admonition bodies and table rows kept, because both are
read.

| mark | budget | Part 1 | Part 2 after 1408 |
|---|---|---|---|
| em dash | 0 | 363 (4.9 per 1000) | 0 |
| bold or italic maxim | 0 | 400 (5.4) | 0 |
| negation | 3 | 517 (7.0) | 3.6 |
| trailing `which` | judge | 205 (2.8) | — |
| colon-definition | judge | 185 (2.5) | — |
| generic tics | 0 | 0 | 0 |

By zone, which is what the guard has to be written against:

| zone | em dash | bold |
|---|---|---|
| prose | 318 | 270 |
| `:::` admonition body | 17 | 12 |
| table row | 28 | 65 |

Of the 65 bold in table rows, 13 are a whole cell (a label column, nine of
them the GUI's panel names in `gui-quickstart.md`) and 52 are emphasis inside
running text in a cell.

Worst first by em-dash density: `recipe.md` 12.8 per 1000, `skill.md` 12.6,
`gui-quickstart.md` 12.3, `gui-guide.md` 9.8, `gui-power.md` 9.2, `agents.md`
8.4. `indexing.md`, `report.md`, `cli.md`, `qpa.md`, `exports.md` and
`compatibility.md` are already under 1.0 and carry their weight in bold
instead.

### The guard has two holes and Part 2 pays nothing to close them

`_prose_lines` skips every `:::` block, so an admonition body is invisible to
the register guard today. Part 2 measures 0 em dashes and 0 bold in
admonitions and tables both, so widening the zones and extending the test to
Part 1 leaves Part 2 green without an edit.

### What the manual already fixes and this must not undo

- `manual.md` § How to read this manual states the split between the parts:
  Part 1 writes Rwp, χ² and GoF as plain text, Part 2 as mathematics. Part 1
  keeps plain text (1408 decided it; `test_part_two_sets_a_statistic_as_
  mathematics` covers Part 2 only).
- Every dotted name and parameter dot-path in Part 1 resolves against the live
  package (`tests/test_manual_api.py`), every anchor resolves in the built HTML,
  and `help.py` deep-links some of those anchors. A renamed heading moves an
  anchor, and the full fast selection is where that surfaces (1408's gotcha).
- `using/glossary.md`'s body is generated from `rietx.help` in `conf.py`. Only
  its prose header is editable here.
- Part 1's walkthroughs are `examples/` scripts included verbatim. Fenced
  blocks are not this pass's to touch.

## Non-goals

- No reorganisation: no chapter moves, no section order changes, no new
  material. A heading is renamed only where it carries a claim the prose under
  it repeats.
- No change to any number, name, dot-path, cross-reference, admonition class,
  figure or fenced block.
- The GUI chapters' route and panel vocabularies are pinned by
  `test_gui_manual.py`; a panel's name is not this pass's to change.
- `docs/skill/`, `README.md` and the landing page are outside Part 1.

## Tasks

Each file or pair of files is one commit. Order is worst-first by density, so
the register is set on the pages carrying most of it before the long ones.

- [x] `recipe.md`, `skill.md`
- [x] `gui-quickstart.md`
- [x] `gui-guide.md`
- [x] `gui-power.md`, `agents.md`
- [x] `results.md`
- [x] `files.md`
- [x] `data.md`
- [x] `series.md`
- [x] `quickstart.md`, `install.md`
- [x] `refining.md`
- [x] `history.md`, `concepts.md`
- [x] `model.md`, `constraints.md`
- [x] `indexing.md`
- [x] `report.md`
- [x] `cli.md`, `qpa.md`, `exports.md`, `compatibility.md`, `glossary.md`
- [x] The guard: `_prose_lines` gains the two zones, the register test covers
      both parts and names the fix
- [x] Skill: none. This WP's product is an editorial register and three
      guards over the manual's own source, and an agent driving rietx reads
      the skill rather than the manual. Nothing it learned changes what to
      free, what to check or how to read an abstention.

## Acceptance

Every mark with a budget sits at its budget, no name or number moved, and the
guard fails on either mark in either part.

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_gui_manual.py tests/test_docs_consistency.py -q
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

`yue-prose` (the eight constructions, the budgets, `measure.md`'s grep pass)
and `yue-docs-style` (register by document type, the Always/Never list).
WP-1408 is the same pass on Part 2.

## Measured at the close

Same recipe as the opening table, on the same definition of prose. The three
uncounted zones are the ones the widened guard now covers.

| mark | budget | before | after |
|---|---|---|---|
| em dash | 0 | 363 (4.9 per 1000) | 0 in prose |
| bold or italic maxim | 0 | 400 (5.4) | 0 |
| negation | 3 | 517 (7.0) | 429 (5.9) |
| trailing `which` | judge | 205 (2.8) | 151 (2.1) |
| colon-definition | judge | 185 (2.5) | 151 (2.1) |
| reframing tail | judge | 60 (0.8) | 0 |
| generic tics | 0 | 0 | 0 |

The 66 em dashes the grep still finds are all in `api-doc` HTML comments, in
captured `console`/`text` blocks, or inside the one code span that quotes the
readout strip's own `—` placeholder. None of the three renders as prose, and
each is exempt in the guard for its own reason.

Negation at 5.9 against a budget of 3 is the residue and it is deliberate.
`yue-prose` keeps the negative half where a reader really would arrive with the
wrong belief, which over this corpus is most of them: `indexing.md` at 8.0 is
every statement about what a number is evidence for, `files.md` at 7.0 is a page
of design decisions each of which a neighbouring tool takes the other way, and
`results.md` at 6.3 is a chapter about statistics that flatter the model.
Twenty stacked pairs were varied or cut; the rest stand.

## Handover log

- **2026-09-14** — created, straight off 1408's closing measurement. Part 1 is
  73,699 prose words carrying 363 em dashes against a budget of 0, 400 bold or
  italic maxims against 0, and negation at 7.0 per 1000 against 3 — the same
  leakage 1408 found and fixed one part over, at nearly four times the length.
  The guard is the part that generalises: `_prose_lines` skips `:::` bodies, so
  17 em dashes and 12 bold in Part 1's admonitions are invisible to it today,
  and Part 2 measures 0 in that zone and in tables, so widening it costs Part 2
  no edit. Next: work the files worst-first, then the guard.
