# WP-1126 — Manual Part 1: the style pass the review asked for

Milestone: v1.1 · Status: 🔄 2026-08-22 — opened, from the maintainer's review of Part 1
Depends on: WP-1067 (Part 1 exists), WP-1068 (the committed figures)

## Goal

Part 1 of the manual reads as a reference manual rather than as a design
record: shorter, no aphoristic topic sentences, no em dashes, headings that
name the ordinary category, and an installation chapter shaped like a real
one. The figures it leans on show real data honestly, and the dark ones sit on
the page rather than on a black rectangle.

## Context

The review was of Part 1 as shipped by WP-1067. Every item below is the
maintainer's, either verbatim or compressed; the general rules behind them
landed first in `~/.claude/skills/yue-docs-style` (new **Sentences** section,
em-dash ban, heading rule, "explain to the section's depth"), because the
failures were the skill's gaps rather than one-off slips.

Files: `docs/manual/index.md`, `docs/manual/using/*.md`,
`docs/manual/make_figures.py`, `examples/nac_11bm.py`, `docs/manual/conf.py`.

Guards that must stay green (`tests/test_manual_api.py`): every dotted name
resolves, every dot-path matches a real `ParameterTable`, every fenced python
block parses and runs or carries a written reason, every referenced figure
exists, and the public surface stays partitioned into documented / excluded /
deferred. Moving prose between chapters is free; deleting the last mention of
a public name is not.

`examples/` is the one authority for a walkthrough (root CLAUDE.md), and
`make_figures.py` is the one authority for how each figure was drawn. A figure
that shows a fit is drawn from a case something already asserts.

## Non-goals

- Part 2 (theory). Untouched.
- `docs/AGENT_PROTOCOL.md`, README, GUI docs.
- Any change to package behaviour. The one code edit in scope is the phase
  `name` in `examples/nac_11bm.py`, which is what the figure legend prints.

## Tasks

- [ ] Skill first: `yue-docs-style` gains the Sentences section, the em-dash
      ban, the heading rule and the cut checklist (landed before this WP).
- [ ] `index.md`: AI-authorship admonition; reflow "Who this is written for";
      plain statement of docstring precedence with a bug link; the naming
      convention without the lecture; cut the marker-announcing sentence.
- [ ] `install.md`: OS/installer tabs (`sphinx-design`), uv recommended with a
      link, requirements as a table with a purpose column, extras table with a
      `Purpose` heading, the compiled-kernel section cut to what it does and
      how to turn it off, a Troubleshooting section carrying the
      `0.0.0+dev` case.
- [ ] `quickstart.md`: real filenames, `plot` arguments touched not taught
      (detail moves to `exports.md`), the six recurring things named as such,
      the worked example introduced so it does not read as a wall.
- [ ] `concepts.md`: the mccusker mermaid in two columns; the
      angular-signatures figure redrawn.
- [ ] Figures: `nac-fit` over the whole fitted range with a phase *name* in the
      gutter; `impurity-peak` redrawn (annotation off the data, whitespace
      gone); every `-dark` figure saved on a transparent ground.
- [ ] Sweep the remaining Part 1 chapters for the same failures.
- [ ] Build and test.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_manual.py \
    tests/test_examples.py tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
```

Plus the figures looked at, light and dark, because a rendered page is not a
green build.

## References

- scikit-learn's installation page, read 2026-08-22, for the shape of an
  install chapter: OS/installer tabs, dependencies as a table with a purpose
  column, virtual environment recommended in the main path, source install
  linked out, troubleshooting last.
- McCusker et al. (1999), *J. Appl. Cryst.* **32**, 36, already cited by the
  chapters this WP edits.

## Handover log

- **2026-08-22** — created.
