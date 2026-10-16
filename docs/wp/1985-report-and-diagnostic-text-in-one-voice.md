# WP-1985 — Report and diagnostic text, rewritten in one voice

Milestone: unscheduled · Status: ✅ 2026-10-16 — 253 codes explained once, every message rewritten, Vale reads the generated pages
Track: Render what the fit already knows
Depends on: — (1133 soft: it adds a field to the same `Diagnostic`)

## Goal

A diagnostic says what was observed and what to do in a sentence each. Its explanation is
written once per code and folded away. `FitReport` and `Refinement.summary()` read as short
text a person can scan in a notebook. The voice matches the manual's: Microsoft's style, with
the repo's rules winning.

## Context

The maintainer found the report and feedback text "extremely dense and AI-sounding". It
renders in huge chunks in the notebooks. They asked for it concise for humans and agents
(WP-1975 § A). Answers they gave:
- **Split a diagnostic into three fields**: observation, action, explanation.
- **The explanation is written once per code**, rustc-style, never repeated per finding.
  rustc keeps the headline short, puts the fix in a separate `help`, and holds a long-form
  explanation per code (an example and a fix) in an index generated from source and reached
  by `--explain`. Barik et al. (2018) report that developers prefer a message with a proper
  argument structure, but accept a weaker one when a fix is offered (as summarised in
  WP-1975 § C3).
- **The headline stays in view and the evidence sits a fold away** (WP-1975 § C4): a
  notebook shows message and suggestion, with the detail and the explanation collapsed.
- **Microsoft's Writing Style Guide** is the base, as for the manual (WP-1982), so the
  package's output and the manual speak in one voice.

**Facts measured 2026-10-15** (WP-1975 § B6):
- `Diagnostic(level, code, message, where, suggestion, value)` is in `schemas/common.py`.
  There are 271 distinct codes across 41 files (`refine.py` 65 sites,
  `indexing/diagnostics.py` 39, `sequential.py` 19). A message plus its suggestion usually
  runs 250-1100 characters on one line.
- Three line formats coexist. Results print `    LEVEL CODE: msg — suggestion`
  (`schemas/results.py` `_diagnostic_lines`), indexing prints `  [warning] CODE: msg`, and the
  peak list uses `at:`.
- `FitReport` has no text view; `FitReport.summary` is a `;`-joined string
  (`report/layer0.py`, `report/__init__.py`). `Refinement.summary()` is built in `refine.py`.
  The Layer 1 abstention reason prints twice.
- **Pins a rewrite must move on purpose:**
  - `str(GuardFinding)` is pinned byte for byte to the pre-v1.0 text
    (`test_capabilities.py`), and root CLAUDE.md § Guards states that rule. Changing it
    changes the CLAUDE.md clause in the same commit;
  - exact messages in `test_bound_hit_at_convergence.py` and
    `test_high_correlation_dedup.py`;
  - `tests/data/nac_termination_golden.txt` (slow, digits masked);
  - the shape pinned by `test_termination_view.py` and `test_display.py`;
  - `summary.txt == str(result)` in `test_joint_report.py`;
  - about fifteen `report.summary` substring checks.
- The skill's `references/diagnostics*.md` holds one agent-facing row per code. A code's
  explanation and that row must not say two different things. Decide which one is the
  authority at the start.
- A display reads fields and never computes; a designed view is a `__str__` override
  (`_display.py`, root CLAUDE.md § Conventions).
- **The style rules are WP-1982's Context**: Microsoft's guide as the base, the repo's rules
  winning, British spelling, and Vale enforcing them on `docs/docs/`. Vale reads the new
  tree's committed pages and leaves the generated Reference bodies out until this WP. Over
  their 20 915 words the house configuration finds 107 errors, all in the package's strings:
  55 spellings and 46 em dashes. The spellings are American forms such as "Polarization
  factor" and "Penalized", and identifiers outside backticks such as `lor_size` and
  `mccusker_default`. There are also 57 notation warnings (`y_calc`, `c_n`). To read them,
  build the tree and widen `.vale.ini`'s section `[docs/docs/[!_]*.md]` to take
  `_generated/`. The term list's generator skips a help title's American spelling, so fixing
  "Polarization" in `rietx.help` needs no term-list change (from WP-1982, 2026-10-16).
- **The `rietx.help` corpus is in scope**, folded at the maintainer's ask (from WP-1981,
  2026-10-16). It is the other text a reader meets in the manual and the GUI, and it has the
  same voice problem. Its 159 entries feed the parameter map, the glossary and every GUI
  popover. The maintainer's review found three samples. "Cell edge" and "Cell angle" became
  "Lattice parameter a, b, c" and "α, β, γ" in WP-1981. "Site-symmetry coordinate degree of
  freedom" names a rietx construct no other code exposes. It needs a plainer title and a
  sentence on how GSAS-II and FullProf treat a special position. The extra-peak `eta`
  description reads "A caller who knows the intruder is near-Gaussian can say so with
  eta.max and buy a much smaller window". Measured over the corpus: "caller" 3, "glob" 3,
  "fnmatch" 1, "column" 6, "degree of freedom" 7, code spans in 51 entries. A title change
  reaches the GUI too. It costs `tests/data/gui/help_keys.json` nothing, because keys are
  globs, but the `label` chips need a check.
- **The person-facing diagnostic index exists** (from WP-1981, 2026-10-16):
  `docs/docs/reference/diagnostics.md`, generated by `docs/reference_pages.py`
  (`diagnostic_index`, `diagnostic_page`). It lists 246 codes with their literal levels and
  the files that raise them, and has no explanation column yet. The per-code explanation
  this WP adds belongs in that table. No registry of codes exists, so the walk reads three
  shapes: a `code=` keyword, a `GuardFinding` constructor and a module-level `*_CODES`
  table. A registry built here would let the index read it instead of walking source.

- **Decided 2026-10-16 with the maintainer.** The field names stay: `message` is the
  observation and `suggestion` the action, so no stored history, result or peak file needs
  a migration. The authority for what a code means is `rietx.help.DIAGNOSTIC_HELP`, which
  grows from the 15 `PEAK_*` entries to every code (the GUI arm is `diagnostics`). The
  skill's rows are then trimmed to agent policy and routing, and must not restate an
  explanation. `docs/reference_pages.diagnostic_index` is the one walk deciding which codes
  are raised; it reads the `_note(level, CODE)` helper shape too, so it finds 253 codes.

## Non-goals

- 1133's view pointer (a field naming the rendered view). Coordinate the schema change, since
  both add a field to `Diagnostic`.
- The tutorials (WP-1545) and Guides (WP-1986), which wait for this.

## Tasks

- [x] Schema: observation, action, and an explanation looked up by code. Decided
      2026-10-16 with the maintainer: `message` and `suggestion` keep their names as the
      observation and the action, so no stored file needs a migration.
      `Diagnostic.explanation` reads `rietx.help.DIAGNOSTIC_HELP` (the `PEAK_*` arm grown
      to every code) and is never stored.
- [x] The per-code explanations, with a meta-test that every code raised has one: 253
      entries, held equal to `diagnostic_index()` both ways (`test_help.py`). 238 were
      written in five subagent lanes against one spec, each read off its raise site.
- [x] One line format for results, indexing and peak lists: `Diagnostic.__str__`, after
      rustc (`warning[CODE]: message`, then `at:` and `help:` lines). The CLI's reader
      notes, the background warning and the two NAC/SRM examples use it too. The slow NAC
      golden is regenerated once, after the summary and the messages move.
- [x] A text view for `FitReport`, and `Refinement.summary()` cut to what a person scans; the
      abstention reason printed once. `FitReport.summary` is one sentence a line (was
      `; `-joined), `FitReport.__str__` prints it under the agreement (FAP: 7 lines, was a
      168-line field tree), and the summary's `report:` block prints it with the abstention
      naming its kind. The clauses' own wording is the message rewrite's.
- [x] Rewrite the messages in the new voice, by module, moving each pin on purpose: six
      subagent lanes over disjoint file sets (refine and the guards, foreign projects,
      indexing, file readers, the rest, the report's clauses). The message is the
      observation with its numbers, the suggestion one action, the explanation gone to
      the registry. About 300 constructions in 41 files; about 150 assertions moved in
      about 45 test files. `str(GuardFinding)` is untouched, so its byte pin and root
      CLAUDE.md § Guards still hold. FAP's `Refinement.summary()` falls from 4778 to 3606
      characters.
- [x] Notebook HTML: headline shown, detail and explanation folded
      (`_display.diagnostics_html`, one `<details>` a finding) in the result, the
      indexing result and the peak list.
- [x] The per-code explanation reaches the Reference tab: `diagnostics.md` is a table of
      code, name and page, and six subsystem pages carry a section per code. One page
      broke the page contract's 50 000-character cap at 139 267.
- [x] The `rietx.help` corpus rewritten in the same voice, the GUI `label` chips checked:
      all 136 entries (two JSON lanes applied by an AST editor, verified field for field),
      no `label` changed, the three pinned threshold spellings kept. The coordinate entry
      is "Atom position shift" and says how GSAS-II and FullProf hold a special position.
      `PLAN_INFO` and the docstring summaries the API pages quote were rewritten too.
- [x] `.vale.ini` widened to `_generated/`, and the generated pages clean under it: CI
      writes the bodies before Vale reads them. 0 errors over 38 pages (was 96 once
      widened); 9 warnings remain (adverbs, the API pages' acronym headings).
- [x] Skill: the diagnostics references re-synced to the new fields
      (`rietx skill --install . --copy`). Every code row in the five `diagnostics*.md`
      files, `abstention.md`, `series.md` and `magnetic.md` keeps only agent policy,
      routing and tagged measurements (about 49 KB cut over the eight files), and the
      code-against-skill disagreements this WP's audit found are fixed in the rows.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_termination_view.py tests/test_display.py tests/test_capabilities.py -n auto --dist loadgroup
```

## References

- Barik, T., Ford, D., Murphy-Hill, E., Parnin, C. (2018). How should compilers explain
  problems to developers? ESEC/FSE.

## Handover log

### 2026-10-16 (2nd session) — closed: one explanation per code, every message rewritten

Every diagnostic rietx raises now reads as one observation and one action, and what the
code means is written once and folded away. A notebook shows the headline and hides the
detail. A printed result shows `warning[CODE]: message` with `at:` and `help:` lines under
it. The fit report reads one sentence a line instead of one 1100-character line, and its
abstention is said once. The parameter help, the plan text and the API summaries were
rewritten in the same voice, and Vale now gates the generated Reference pages as well as
the written ones. Nothing about a fit's numbers moved. The cost was about 3.8 M subagent
tokens over 18 agents (one survey, 17 Sonnet lanes over disjoint files), summed from
their own usage reports.

*Done* (decisions with the maintainer, 2026-10-16, are in Context): `message`/`suggestion`
keep their names, so no stored file needs a migration. `rietx.help.DIAGNOSTIC_HELP`
holds 253 entries, held equal both ways to `docs/reference_pages.diagnostic_index()`,
which now also reads the `_note(level, CODE)` helper shape. `Diagnostic.explanation` and
`help.explain` look it up. `Diagnostic.__str__` is the one text form; results, indexing,
the peak list, the CLI's reader notes and `auto_background`'s warning call it.
`_display.diagnostics_html` folds each finding in a `<details>`. `FitReport.summary` is
one sentence a line and `FitReport.__str__` prints it (FAP: 7 lines, was a 168-line field
tree). The Reference tab's diagnostic page splits into a table plus six subsystem pages.
The skill's rows keep agent policy and routing only. The GUI's help arm is `diagnostics`
(was `peak_diagnostics`); Report keeps the summary's line breaks.

*Measured* (`[dev]` venv, darwin arm64, `.venv/bin/python -m pytest -n auto --dist
loadgroup -m "not slow"`): 10677 passed, 191 skipped, 2 xfailed on the final source tree,
from 10676/191/2 before the one added test
(`test_display.py::test_a_diagnostic_prints_its_headline_and_folds_the_rest`); GUI vitest
586 passed. FAP's `Refinement.summary()` went from 4778 to 3606 characters. Vale over the
widened tree: 0 errors, 9 warnings in 38 files (96 errors when first widened). The full
selection was not run: the change moves text, never a fitted number, and the one slow
text pin (`tests/data/nac_termination_golden.txt`) was regenerated and run.

*Gotchas*: `ast` column offsets are UTF-8 bytes, so a source editor indexing characters
eats a comma on any line holding β or μ (the scratch editor that applied the help corpus
hit it once). A per-code explanation must not quote a threshold number: no test can hold
a sentence to a retuned constant (`help.py` rule 3). The report-agent eval shim excises
the identifiability clause as the exact substring `"\n" + clause`, so that clause stays one
line.

*Not done, on purpose*: the tutorial scripts and notebooks still print the old forms
(WP-1545's, pushed to its Inherited). Two comments in `refine.py` (near
`STRAIN_FLAG_WIDTH` and `SIZE_FLAG_SIZE_A`) still quote private-archive counts; they
predate this WP and are raised with the maintainer rather than edited. Four Vale
warnings on the parameter map (adverbs) and the API pages' acronym headings stay.

Next: WP-1545 regenerates the tutorials over the new text, then WP-1986 moves the Guides
once WP-1979 lands.

- **2026-10-16** — filed from WP-1975's slate, where it was drafted as "1976" before that
  number went to another WP. No open WP owns the text: 1133 adds a view pointer to the same
  `Diagnostic`, and 1335 and 1421 are about the report's cost and its numbers.
