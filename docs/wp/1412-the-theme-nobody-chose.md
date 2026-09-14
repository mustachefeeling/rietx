# WP-1412 — the theme nobody chose

Milestone: unscheduled · Status: ⬜
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

- [ ] Build the manual under furo, pydata-sphinx-theme, sphinx-book-theme and
      shibuya. Record what each build costs to get `-W` clean, because that cost
      *is* part of the answer
- [ ] Screenshot each in both themes at 1440 px and 390 px: the front page, a
      theory chapter with a numbered equation, a Part 1 chapter with a figure
      pair, and a page with a mermaid diagram
- [ ] Measure the content column each gives, against the 736 px WP-1408's
      layout pass assumed
- [ ] Cost the migration row by row against the table above, with the brand fork
      counted as a saving rather than a cost
- [ ] Recommend, in the handover, with the screenshots named
- [ ] Skill: none expected. The manual's theme does not reach an agent driving
      rietx

## Acceptance

A recommendation supported by sixteen screenshots and a filled-in version of the
coupling table, in this file's handover log. No package code changes.

## References

- pydata-sphinx-theme branding and gallery:
  <https://pydata-sphinx-theme.readthedocs.io/en/stable/user_guide/branding.html>
- WP-0604 § Design decisions (the original bullet), WP-1068 (the mermaid theme
  story), WP-1408 § G3 (the equation-number grid and the column measurements)

## Handover log

- **2026-09-14** — created by WP-1411, which found the empty record while
  forking furo's brand template. Not started.
