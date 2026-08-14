# WP-1068 — Part 1 second pass: voice, figures, structure

Milestone: v1.0 § Floor · Status: 🔄 2026-08-14 — voice, sectioning, two new
chapters, four diagrams and three figures landed; the McCusker section waits on
the paper
Depends on: WP-1067 (the chapters and their guards)

## Goal

Part 1 reads like a manual a person uses rather than like a design record:
scannable reference headings, prose under the Orwell/ASD-STE100 rules, agent-only
material marked instead of described, figures where a picture is the explanation,
and the three subjects a user needs that the floor chapters left out — the fit
statistics, the parameter groups and their correlations, and the files the
package reads and writes.

## Context

The review that opened this WP is in the session that landed WP-1067's
follow-up. Its fourteen items, and what each became:

| Review item | Where it landed |
|---|---|
| "consider the heading" | `index.md` H1 is `rietx manual`; every chapter and section retitled as a reference entry |
| rewrite under the Orwell/STE skill | all six Part 1 chapters and `index.md` |
| "they repay reading" is patronising | deleted, with the four other judgement-on-the-reader's-behalf sentences |
| "and a chapter that describes one says so" is tortuous | replaced by the `agent` admonition |
| explain the file structure | new `using/files.md` |
| figures, light/dark aware | three, committed in pairs, `docs/manual/make_figures.py` |
| mermaid diagrams, light/dark aware | four, `sphinxcontrib-mermaid` |
| five unnecessary sentences | deleted verbatim |
| "use the object form below" unexplained | its own section in `using/quickstart.md` |
| agent-specific phrasing sounds patronising | every such note now carries `:class: agent` |
| elaborate on the McCusker plans and the parameter groups | new `using/concepts.md` |
| explain Rwp, GoF, χ² | `using/concepts.md` § Fit statistics |
| the broken equation in Part 2 | `forward-model.md`, plus a guard that would have caught it |
| the sectioning is not useful as reference | the chapter map below |

### The chapter map

`install` → `quickstart` → `concepts` → `report` → `files` → `agents`.
Install it, get one fit to the end, learn what the fit did, read what came back,
find out what is on disk, then wire it into something.

### Three things a successor should not re-derive

- **The theme story needs no custom JS.** `sphinxcontrib-mermaid` ≥ 2.1 already
  reads `body[data-theme]`, which is what furo writes, and re-renders from a
  `MutationObserver` on the toggle. What *did* need fixing was mermaid's dark
  theme drawing edge labels as light text on a light chip, and a subgraph title
  colliding with the first node — both in `_static/custom.css` and `conf.py`.
- **`-W` cannot see a rendering bug.** `forward-model.md`'s data-row expression
  printed its own TeX for months, and five `references.bib` titles printed
  theirs on seven pages. Both were found by scanning the *built* HTML, which is
  now `test_no_unrendered_math_survives_the_build`.
- **Figures are committed, not built.** `docs/manual/make_figures.py` is the one
  authority for how each was drawn, and `.gitignore` carries an explicit
  negation because `*.png` would otherwise drop all six.

### Blocked: the McCusker paper

`concepts.md` § "The order the presets encode" states the three ordering rules
from the repository's own measured record (`AGENT_PROTOCOL.md` §2) and cites
`mccusker1999` for the order itself. Deepening that section needs the paper, and
it cannot be fetched here: `doi.org/10.1107/S0021889898009856` redirects to
`journals.iucr.org`, which returns 403 to an automated fetch, and it is not in
the local Zotero corpus. **Ask the user for the PDF before writing more of that
section.**

## Non-goals

- **Part 2's prose.** Only its two rendering bugs are in scope. Rewriting the
  theory chapters under the same rules is its own pass.
- **The 1.0.x chapters.** `using/data.md`, `using/model.md`, `using/refining.md`,
  `using/history.md`, `using/projects.md`, `using/indexing.md`, `using/series.md`,
  `using/exports.md`, `using/cli.md` stay in WP-1067's post-release list.
  `files.md` is the *map* of what is on disk, not the projects chapter.
- **The GUI.** Still out of scope and still beta (WP-1067 § Non-goals).

## Tasks

- [x] Part 2's two rendering bugs, and the guard that sees them:
      `test_no_unrendered_math_survives_the_build` plus
      `test_every_figure_reference_exists`.
- [x] `index.md`, `install.md`, `agents.md`: voice, headings, the `agent`
      admonition and its CSS, `html_static_path`.
- [x] `quickstart.md` trimmed to one fit end to end; `concepts.md` written.
- [x] `report.md` retitled; `files.md` written.
- [x] `sphinxcontrib-mermaid` and four diagrams.
- [x] Three figures, `make_figures.py`, `plot_result(style=)`, the
      `examples/nac_11bm.py` refactor.
- [x] A pass over every built page in both themes: headings, image switching,
      no sideways scroll, no unrendered diagram, no text the colour of its own
      background. Driven with playwright-core out of the scratchpad against the
      chromium in the playwright cache (never installed into `gui/`).
- [ ] The McCusker section, once the paper is to hand.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_docs_consistency.py
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python docs/manual/make_figures.py
.venv/bin/python -m ruff check src tests examples docs
```

## References

- McCusker, Von Dreele, Cox, Louër & Scardi (1999), *J. Appl. Cryst.* **32**,
  36–50, "Rietveld refinement guidelines", `10.1107/S0021889898009856`. Open
  access, not fetchable from here — see § Blocked.
- Toby (2006), *Powder Diffraction* **21**, 67, for the agreement indices.
- Orwell's six rules and ASD-STE100, via the skill the review named:
  `github.com/tamdogood/builder-essential-skills/blob/main/skills/orwell-writing/SKILL.md`.
  House exceptions: British spelling stays, and code, identifiers and dot-paths
  are never reworded.

## Handover log

- **2026-08-14** — created, and six of eight tasks landed in the same session.
  Done: the two Part 2 bugs and their guard; all six Part 1 chapters rewritten,
  with `concepts.md` and `files.md` new; four mermaid diagrams; three
  light/dark figure pairs; `plot_result(style=)`; the `nac_11bm.py` refactor.
  Counts, `[dev]` venv, darwin/arm64: fast selection **2272 passed, 108
  skipped** (2:42), against 2269/108 at 1067's close — three new tests, three
  new passes, no new skip. The dot-path guard grew a third fixture model with
  the optional blocks declared, and 50 names moved from the deferred bucket to
  documented (1094 → 1044).
  In flight: nothing.
  Next: the McCusker section (blocked, see § Blocked), then a fresh-eyes read of
  the built pages in both themes.
  Gotchas: three drawn artefacts were cut *after* looking at them — a
  degeneracy-group diagram that repeated the table above it, a
  Le-Bail-vs-Rietveld pair whose panels were indistinguishable at full scale,
  and `plot_for_vlm`'s montage, which is drawn for a vision model and has no
  dark twin. Render before deciding a figure earns its place.
