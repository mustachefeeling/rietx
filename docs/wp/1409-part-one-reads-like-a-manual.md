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

### 2026-09-14 (2nd session) — Part 1 now reads the way Part 2 does

Someone opening the manual gets the same voice on every page. Before this, the
twenty-four chapters of Part 1 were written in the maintainer's compressed
register — an aside welded on with an em dash, a bold claim in front of a
sentence that already made it — and Part 2, swept one WP earlier, was not. That
difference was nobody's choice. The rulebook sits in the same tree and gets read
first, so its voice arrives in the manual by default.

Three reader-visible defects turned up on the way and are fixed. `indexing.md`'s
"Further reading" had lost the `{doc}` prefix off a role and had been shipping
`the [agent skill <skill>`,` as literal text. The same chapter said "Five of the
twelve" peak flags are unusable against a vocabulary of fourteen with six
unusable. And the agent skill's own `abstention.md` put a code span inside a
Markdown table cell, where the first pipe ends the cell, so the span never closed
and its backticks rendered. None of the three is a build warning, and each now
has the guard that closes its class.

*Done*, one or two chapters per commit, worst-first by density:

- All 24 chapters rewritten. Eighteen headings that carried a claim became the
  noun a reader looks up, with the claim in the first sentence. Roughly 120 bold
  lead-ins became the sentences they already were, and every GUI label went to
  backticks, which is what the majority of them already used.
- Two counts that were wrong are right, and one is now guarded: the peak-flag
  vocabulary, and `series.md`'s "The four fences" above a table of five. The
  second is fixed by moving the count out of the heading into the prose that
  sits against the table, so the two cannot drift apart.
- One typo: `results.md`'s coverage warning read "And v also rises", where `v`
  is a leftover for the σ²/max(y, 1) ratio the paragraph is about.
- Three guards, each failed on purpose before landing (six deliberate
  failures in all). `test_the_manual_keeps_its_register` covers both parts, and
  `_prose_lines` now sees an admonition's body, which it skipped whole.
  `test_no_unrendered_markup_survives_the_build` scans the built HTML for a
  backtick in the prose, which is what a code span or role leaves when it does
  not close; it caught the skill's table cell on its first run.
  `test_every_closed_vocabulary_member_is_named_where_its_table_is` and
  `test_the_peak_flag_table_marks_exactly_the_unusable_flags` hold
  `indexing.md`'s tables against the live `Literal`s.

*Measured*: the table above. Em dashes 363 to 0, bold 400 to 0, reframing tails
60 to 0, negation 7.0 to 5.9 per 1000 against a budget of 3. Fast selection
**4660 passed / 132 skipped** in 2:10 on darwin/arm64, `[dev]` plus the
worktree's playwright, **+3** over 4657 and those three the new tests; the
register test was renamed rather than added. Build `-W` clean, ruff clean.

*Gotchas*

- The register guard's page list had to exclude `_generated/`. Both files there
  are rendered into the manual and neither is its prose to hold: the glossary
  body is written from `rietx.help` by `conf.py`, and the skill body is an
  agent's rulebook, which the corpus explicitly allows to compress.
- Removing bold from a table row can move a test key. `test_the_hump_table_
  agrees_with_the_refinement_that_produced_it` keys the Si640c evidence rows on
  their literal labels, so `| Chebyshev-3 **+ one hump** |` was a key. The Rwp
  numbers it guards did not move; the key did.
- `tests/test_manual_api.py` alone is not enough while doing this. It passed on
  every chapter and the hump-table key failure only surfaced in
  `tests/test_manual.py`. Run the fast selection between chapters, not at the
  end.
- Scope a `git checkout` to the file you patched. Failing a guard on purpose and
  reverting with `git checkout docs/manual/` took four sibling files' uncommitted
  edits with it, and the measurement is what noticed. It happened twice: the
  second time the reverted file held the review's own uncommitted re-wrapping.
  Commit before the experiment, or name the single path.

*Review*: `/code-review high --fix` accepted nine findings, all applied,
nothing declined. Four were **meaning changes this pass introduced** while
removing em dashes, which is the risk of an editorial sweep and the reason the
review belongs before the PR: `files.md`'s "but only where it can say that it
did" became "and only where", dropping the restrictive force of the
reader-repair invariant; the same page promoted an aside into a universal claim;
`gui-power.md` narrowed an open settings dict to "which is the theme"; and
`gui-guide.md` turned an italic paraphrase of a GUI message into a
double-quoted verbatim one the app does not emit (`Plot.svelte:1409` carries an
em dash where the quotation had a comma, checked against the Svelte source
rather than taken on the review's word). Three more were **holes in this
session's own guards**, each in the shape the guard was written to catch: the
vocabulary guard did not read the counts its docstring names, the flag-table
row pattern dropped any row carrying an escaped pipe (the convention this same
branch introduced), and `_prose_lines` swallowed an admonition's *title* line
and saw only the first line of a multi-line HTML comment. The remaining two are
presentation: one table label written two ways, and edited-in-place lines
running to 136 characters. Counts after: **4661 passed / 132 skipped**, +4 on
the 4657 baseline, which is this WP's three guards plus the review's count
guard.

*Next*: nothing on Part 1's prose. Two things the next session could take, in
order of cheapness. The dead-anchor guard 1408 named is now cheaper, since the
five Part 1 anchors it listed are still unlinked and the ten inert Part 2 ones
are unchanged. And negation sits at 5.9 against a budget of 3; the residue is
argued for per chapter in the table above, and a reader who disagrees with that
argument has the per-chapter numbers to point at.

- **2026-09-14** — created, straight off 1408's closing measurement. Part 1 is
  73,699 prose words carrying 363 em dashes against a budget of 0, 400 bold or
  italic maxims against 0, and negation at 7.0 per 1000 against 3 — the same
  leakage 1408 found and fixed one part over, at nearly four times the length.
  The guard is the part that generalises: `_prose_lines` skips `:::` bodies, so
  17 em dashes and 12 bold in Part 1's admonitions are invisible to it today,
  and Part 2 measures 0 in that zone and in tables, so widening it costs Part 2
  no edit. Next: work the files worst-first, then the guard.
