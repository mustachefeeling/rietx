# WP-1126 — Manual Part 1: the style pass the review asked for

Milestone: v1.1 · Status: ✅ 2026-08-22 — every review item landed; Part 1 rebuilt, re-measured and looked at
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

- [x] Skill first: `yue-docs-style` gains the Sentences section, the em-dash
      ban, the heading rule and the cut checklist (landed before this WP).
- [x] `index.md`: AI-authorship admonition; reflow "Who this is written for";
      plain statement of docstring precedence with a bug link; the naming
      convention without the lecture; cut the marker-announcing sentence.
- [x] `install.md`: OS/installer tabs (`sphinx-design`), uv recommended with a
      link, requirements as a table with a purpose column, extras table with a
      `Purpose` heading, the compiled-kernel section cut to what it does and
      how to turn it off, a Troubleshooting section carrying the
      `0.0.0+dev` case.
- [x] `quickstart.md`: real filenames, `plot` arguments touched not taught
      (detail moves to `exports.md`), the six recurring things named as such,
      the worked example introduced so it does not read as a wall.
- [x] `concepts.md`: the mccusker mermaid in two columns; the
      angular-signatures figure redrawn.
- [x] Figures: `nac-fit` over the whole fitted range with a phase *name* in the
      gutter; `impurity-peak` redrawn (annotation off the data, whitespace
      gone); every `-dark` figure saved on a transparent ground.
- [x] Sweep the remaining Part 1 chapters for the same failures.
- [x] Build and test.

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

### 2026-08-22 — the review applied, and the numbers under it re-measured

Part 1 now reads as a reference manual rather than as a design record, and the
four figures the review named say what they were supposed to say. The part that
will matter longest is not the prose: **every NAC number the manual quotes was
re-measured on today's tree, and several had drifted** when WP-1123 flipped the
intermediate-tolerance default. The manual had been quoting Rwp 0.0932 against
a package that returns 0.0933, 52 regions against 53, and a Le Bail trajectory
whose Layer 1 no longer speaks where the text said it did. Those are fixed
against measurements taken this session, listed below.

The general rules behind the review landed **first, in the
`yue-docs-style` skill** (`~/.claude/skills/yue-docs-style`, outside this
repo): a new *Sentences* section (cut what the reader can see, no aphorism as a
topic sentence, give the action rather than a rating of it, explain to the
section's depth, never quote the style guide in the prose), the em-dash ban,
the heading rule, and a *Cut* pass in the checklist. The skill's own files were
modelling the failures it was being asked to prevent, which is why the manual
came out that way.

*Done, against the review list.* The front matter carries an authorship
admonition naming the models and the maintainer, and says what guards the text
and what does not; docstring precedence is one plain sentence with a link to
report a disagreement. `install.md` follows scikit-learn's shape: OS/installer
tabs (`sphinx-design`, new in the `docs` extra), uv recommended with a link,
requirements and extras as tables with a `Purpose` column, the compiled-kernel
section cut to what it does and the two ways to switch it off, and a
Troubleshooting section that carries the `0.0.0+dev` case, the zsh glob and
numba's numpy ceiling. The quickstart uses the walkthrough's real filenames,
touches one `plot` argument and links the rest to a new `exports.md` §
{ref}`plotting-the-fit`, and shows the example's real output *before* its
listing, which is now three annotated slices rather than 111 lines in one
piece. Em dashes, bolded topic sentences, judgements for the reader ("worth
reading") and four oblique indexing headings are gone from all eighteen
chapters.

*Measured this session* (`[dev]` venv, darwin/arm64, 2026-08-22; the NAC
walkthrough with `phase.name` set):

| Claim | Was | Now |
|---|---|---|
| Rietveld Rwp | 0.0932 | 0.0933 |
| regions found | 52 | 53 |
| unmatched calc / obs | 84 / 54 | 85 / 53 |
| 12.3° width, mixing share | 0.46, 0.38 | 0.45, 0.39 |
| esd inflation | 9.4 | 9.3 |
| background pair | 0.0932 / 0.1106 | 0.0933 / 0.1108 |
| off-region χ²_red, d, points | 2.47, 0.41, 12 248 | 2.50, 0.40, 12 275 |
| Le Bail gap | 0.0932 / 0.0806 | 0.0933 / 0.0806 |
| geometry esd ratio, Rwp | 0.0818 | 0.86–1.41 at Rwp 0.0819 |
| restraint schedule | 1.872 Å, 4.834 Å, 148σ | 1.87 Å, 4.84 Å, 149σ |
| suggest refusals | occ pair at 7534 / 0.97 | occ 7529 at 0.973 |
| texture axes | both (2 1 0), r² 0.14 / 0.36 | (2 1 0) 0.12 and (2 0 1) 0.35 |

*The one claim that changed shape rather than digits.* report.md said the Le
Bail trajectory's third stage speaks and its fourth, with a better fit, does
not. It no longer does: the plan now abstains `unreadable` from stage three
onward. The reading it was making survives in the numbers underneath, so the
passage now quotes the accepted share falling 32 % → 27 % → 16 % as Rwp falls
0.168 → 0.159 → 0.144.

*Figures.* All six regenerated. `nac-fit` covers the whole fitted 2–24° instead
of stopping at 12°, which is what makes it read as measured data, and its first
phase is named in `examples/nac_11bm.py` so the tick row says `Na2Ca3Al2F14`
rather than the COD block number. `impurity-peak` is redrawn at the width it is
read at, annotation off the data, legend replaced by two direct labels.
`angular-signatures` likewise, with its empty upper right now carrying the
measured claim (every shape a straight line to within 0.8 % over 20°). Every
`-dark` figure is saved transparent, because furo's dark page is #131416 and an
opaque figure sat on it as a rectangle. `make_figures.py` gained `WIDTH`/`FONT`
and a shared rc context so the type is sized for the 800 px the manual is read
at.

*Looked at, not just built.* The three mermaid diagrams and the install tabs
were rendered in a headless browser (playwright-core in the scratchpad against
the cached chromium). The mccusker plan is now `flowchart LR` with `direction
TB` subgraphs, which doubles the type size; the report's layer diagram was
tried the same way, rendered worse, and stays `graph TD`. Quickstart was
checked in the dark theme.

*Suite.* Fast selection green on the final tree: **2619 passed, 117 skipped**
in 147.79 s (`-n auto --dist loadgroup -m "not slow"`, `[dev]` venv,
darwin/arm64). No full run: this WP moves documentation, one phase label in
`examples/nac_11bm.py` and one docs dependency, so it can move no measured
package number.

*Gotchas for a successor.* MyST reads a directive option beginning with `#` as
a comment, so `:start-at: "# --- Le Bail first"` needs the quotes or the anchor
silently becomes `None` and the whole file is included. `sphinx -W … | tail`
reports tail's exit status, not sphinx's; capture the build's own status.
Three em dashes remain in Part 1 and all three are inside quoted console
output (`rietx index`'s abstention line, the `--ceiling` block, `rietx
compare`'s banner) — changing those is a change to product strings and their
tests, and is not in this WP.

*Next.* Nothing in this WP is left open. If the CLI's own text should follow
the same rule, that is a small separate change to `src/rietx/cli.py` and the
tests that pin those strings.

- **2026-08-22** — created.
