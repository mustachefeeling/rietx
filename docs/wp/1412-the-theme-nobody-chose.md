# WP-1412 — the theme nobody chose

Milestone: v1.5 · Status: ✅ 2026-09-14
Depends on: 1411

## Goal

A decision on the manual's Sphinx theme made from rendered pages and a costed
migration, replacing a choice that was never compared against anything.

## Context

Furo entered in WP-0604 as one of four names in a dependencies bullet, and the
only reason on record is the closing line "Tooling: Sphinx, MyST-Parser,
sphinxcontrib-bibtex, furo (all BSD-licensed)". No alternative was rendered, no
criterion was written down.

That is not an argument for moving. Furo is load-bearing now, and **a migration
pays for all five of these before it renders a single page**:

| coupling | where | what breaks |
|---|---|---|
| `body[data-theme]` | `conf.py` mermaid light/dark (WP-1068) | pydata writes `html[data-theme]` |
| `body[data-theme="dark"]` | `_static/custom.css`, two blocks | dark colours stop switching |
| `only-light` / `only-dark` | every committed figure pair, `make_figures.py`, `make_screenshots.py` | figures show the wrong theme, or both |
| `span.eqno` pinned `position: absolute` | `custom.css`'s equation grid (WP-1408 § G3) | the grid is a fix for a problem another theme may not have |
| a 736 px content column | WP-1408's layout pass, `check_equations.py` | every width measurement is re-taken |

WP-1411 added a sixth, deliberately small: `docs/manual/_templates/sidebar/brand.html`
is a fork of furo's own template, because furo has no brand-link option. It is
about twenty lines and is meant to be thrown away if the theme moves.

**The case for looking.** pydata-sphinx-theme has `logo.link` as configuration
alongside `image_light` / `image_dark` / `text`, so the brand fork would not
exist there. Its gallery carries NumPy, SciPy, pandas, scikit-learn, NetworkX
and the Jupyter projects, which is the existing practice for a scientific Python
package (root CLAUDE.md: a supported mechanism beats a clever one). A top navbar
is also where a "rietx.org" link belongs, rather than above the table of
contents.

**What this WP must not do** is decide from that paragraph. It is a feature list
and a gallery; the five rows above are measured facts about this tree. The
asymmetry is the whole reason the WP exists.

## Non-goals

- Migrating. This WP ends in a recommendation with pictures behind it. If the
  answer is "move", that is its own WP with the five couplings as its checklist.
- The landing page, which is hand-written HTML and shares no theme with the
  manual.

## Tasks

- [x] Build the manual under furo, pydata-sphinx-theme, sphinx-book-theme and
      shibuya. Record what each build costs to get `-W` clean, because that cost
      *is* part of the answer
- [x] Screenshot each in both themes at 1440 px and 390 px: the front page, a
      theory chapter with a numbered equation, a Part 1 chapter with a figure
      pair, and a page with a mermaid diagram
- [x] Measure the content column each gives, against the 736 px WP-1408's
      layout pass assumed
- [x] Cost the migration row by row against the table above, with the brand fork
      counted as a saving rather than a cost
- [x] Recommend, in the handover, with the screenshots named
- [x] Skill: none expected. The manual's theme does not reach an agent driving
      rietx

## Acceptance

A recommendation supported by sixteen screenshots and a filled-in version of the
coupling table, in this file's handover log. No package code changes.

## References

- pydata-sphinx-theme branding and gallery:
  <https://pydata-sphinx-theme.readthedocs.io/en/stable/user_guide/branding.html>
- WP-0604 § Design decisions (the original bullet), WP-1068 (the mermaid theme
  story), WP-1408 § G3 (the equation-number grid and the column measurements)
- The sixteen sheets, the two pydata sheets, and the method behind them:
  [1412-theme-survey/README.md](1412-theme-survey/README.md)

## Handover log

### 2026-09-14 — the manual stays on furo, and the toctree is the reason

The manual keeps furo, and the question is closed rather than left open. Three
alternatives were built and photographed, and the one with a real case behind
it is pydata-sphinx-theme. It would delete WP-1411's twenty-line brand fork and
replace it with two lines of configuration. It would then need a fourteen-line
fork of its own sidebar template to put the chapter list back on the page,
because its navigation assumes a nested document tree and this manual is flat:
34 chapters at the top level under two captions. Left alone, pydata's sidebar
renders empty on every page and the chapters live in a navbar that truncates at
five behind a "More" dropdown. The trade is one fork for another, and the one
being bought is larger.

The five couplings in Context were the wrong five. One of them does not exist,
two cost about ten lines between them, and the expensive one is absent from the
table.

**The table, filled in.** Costs are lines of CSS or config a migration writes,
measured by writing them.

| coupling | measured |
|---|---|
| `body[data-theme]` in `conf.py`'s mermaid config | **No coupling.** sphinxcontrib-mermaid 2.1.1 reads a `dark`/`light` class or `data-theme` on either `html` or `body` and falls back to `prefers-color-scheme`, and its MutationObserver watches both elements. All three alternatives drove the diagram correctly, shibuya's `html.dark` included. The comment was corrected in 5c15f50a. Cost: 0. |
| `body[data-theme="dark"]` in `custom.css`, two blocks | **Real, and silent.** A reader who picks dark from the toggle gets `--color-rietx-ink` at the light hex `#6d4aff` on a dark page under all three. The system-preference path still works, so the fault hides from anyone who never touches the toggle. This is WP-1411's own bug returning in a second spelling. Cost: one selector added per block, 4 lines. |
| `only-light` / `only-dark` on the committed figure pairs | **False for pydata and sphinx-book**, which ship the same two classes and also hide a trailing `figcaption`. **True for shibuya**, which ships neither: both halves of all 14 pairs render, the dark one ghosted under the light one (`1412-theme-survey/figures-light-1440.png`, fourth column). Cost: 0, or about 6 lines for shibuya. |
| `span.eqno` pinned `position: absolute` | **Real and harmless.** Only furo pins it, so the un-pinning rule is inert elsewhere rather than wrong. The grid itself is theme-blind and carried over untouched: all 16 numbered equations on `profiles.html` cleared their numbers in every build at 1440 px. Cost: 0, plus a comment that would then explain a fix for a problem the theme does not have. |
| a 736 px content column | **Real and cheap.** furo 736, pydata 720 on a chapter page, sphinx-book 790, shibuya 800. The widest typeset equation is 614 px under the first three and 638 px under shibuya, against equation cells of 651 px to 739 px, so it fits everywhere. Cost: re-run `check_equations.py`, which measures rather than asserting a width. |
| the brand fork (the sixth, added by 1411) | **A saving, and a partial one.** pydata's `logo` and `logo_link` replace the template. They do not replace the release line under the wordmark, and the mark has to become two committed files: an `<img>`-embedded SVG reads no CSS variable, so `image_light` / `image_dark` is the only way it follows the toggle. Saving: 20 lines of template and 5 CSS rules. Cost: 2 SVG files that do not exist. |
| **the sidebar**, absent from the table | pydata renders the toctree *below* the active top-level entry. `startdepth=1` is hardcoded in `components/sidebar-nav-bs.html` and no `html_theme_options` key reaches it, so a flat tree yields an empty sidebar. Cost: a 14-line template fork, or restructuring the manual's two toctrees into nested sections. |
| **`custom.css`'s furo vocabulary**, absent from the table | Five furo CSS variables, none defined by any of the three. The worst is `--icon-abstract`: undefined, the mask on the agent admonition's `::before` is dropped and the pseudo-element renders as a solid purple block across the whole title bar (`1412-theme-survey/pydata-configured-front.png`, left panel). Cost: about 45 lines of CSS, written and measured. |

**Measured**

- **Build cost to `-W` clean: zero for all four.** Every theme built the manual
  with `html_theme` overridden and nothing else changed. Wall clock 3.8–4.2 s
  warm across five builds against 23 s cold, so the spread between themes is a
  fifth of the cold-to-warm gap and settles nothing.
- **Content column** at 1440 px: furo 736 px on every page; pydata 720 px on a
  chapter and 896 px on the front page, which has no sidebar; sphinx-book
  790 px; shibuya 800 px. At 390 px: 358 px for the first three, 342 px for
  shibuya.
- **Equations** at 1440 px on `profiles.html`: 16 numbered, none overflowing its
  cell under any theme. Minimum clearance to the number 48 px under furo, 29 px
  under pydata, 65 px under sphinx-book, 62 px under shibuya.
- **Three spellings of dark**: furo `body[data-theme="dark"]`, pydata and
  sphinx-book `html[data-theme="dark"]`, shibuya `html.dark` plus
  `html[data-color-mode="dark"]`. All four also answer `prefers-color-scheme`
  when the reader has chosen nothing.
- **Mermaid edge labels**: `custom.css` gives them the page's ground through
  `--color-background-primary`, and under all three alternatives the declaration
  is invalid at computed-value time and the ground falls back to transparent.
  No mermaid edge in the manual carries a label, so the rule is defensive today
  and its breakage is latent.
- **Versions**: furo 2025.12.19, pydata-sphinx-theme 0.21.0, sphinx-book-theme
  1.1.3, shibuya 2026.7.12, sphinx 9.1.0, sphinxcontrib-mermaid 2.1.1, chromium
  1223, macOS 15 arm64.

**What the pictures show.** `1412-theme-survey/front-light-1440.png` is the
decision in one frame: furo and shibuya put all 34 chapters in the sidebar,
sphinx-book does too, and pydata puts five in the navbar with the rest behind
"More". `figures-light-1440.png` has shibuya's doubled figure pair.
`pydata-configured-front.png` and `-chapter.png` carry the three states of the
pydata migration across, and the middle panel is what configuration alone buys.

**On the other two.** sphinx-book-theme is pydata with a different skin, so it
inherits the same flat-tree problem; it happens to ship `html_sidebars`
defaults that show the chapter list, and it adds a header of Jupyter launch
buttons this manual has no use for. shibuya renders well and is the closest to
furo in shape. It fails on the figure pairs, the one coupling that touches 14
committed files.

**Gotchas for whoever comes next**

- `check_equations.py` measures at 1440 px and 1100 px. Adding a 390 px
  viewport would report 13 or 14 failures that are not failures: at that width
  14 of 16 equations overflow their own cell, and `clear` is computed from the
  unclipped `mjx-math` box. Under furo the cell clips at x=316 and the number
  starts at x=332, so the overflow cannot reach it. Skipping `clear` is not
  enough: the test's condition is `clear < MIN_CLEARANCE_PX or over > 0`, so
  `over > 0` fails those 14 rows on its own. A 390 px viewport needs a rule
  saying what overflow means at that width, not a clearance exemption.
- pydata appends its own `components/` directory to `templates_path` at setup,
  so an override of one of its templates goes at the *root* of your own
  templates directory. Placed under `components/` it is silently never found,
  and the build stays green.
- The survey's probe scripts were not kept, by decision. The README in
  `1412-theme-survey/` records the method, the versions and the machine.
- **All eighteen sheets were committed and none of them landed.**
  `.gitignore`'s blanket `*.png` took them, `git add <dir>` reported nothing,
  and the commit carried the README alone. That is the fifth occurrence in this
  repo and the first outside `docs/manual/`, which is why the guard written
  after the third saw nothing: it names two directories. Fixed in 330dc401 with
  an un-ignore and a general guard, `git check-ignore` over every target a
  planning doc links, `_planning_docs()` widened to reach a WP's own evidence
  README. The guard was checked red as well as green.

**The review pass** (`/code-review high --fix`) found three and all three were
taken. Two were in the guard this session had just written: it never read
`git check-ignore`'s exit code, so a 128 with an empty stdout would have read as
a pass, and it asked the ignore rules without asking the index, which is half of
the failure it exists for. The third was in this entry, where the
`check_equations.py` gotcha prescribed a fix that does nothing. Nothing was
declined. Landed in 3963567d.

**Next.** Nothing. The WP closes with the recommendation to stay, and no
migration WP is opened. Reopen the question if the manual's two toctrees are
ever restructured into nested sections. That one fact is the whole of pydata's
cost here.

- **2026-09-14** — created by WP-1411, which found the empty record while
  forking furo's brand template. Not started.
