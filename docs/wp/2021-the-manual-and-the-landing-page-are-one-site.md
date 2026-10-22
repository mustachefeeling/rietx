# WP-2021 — The manual and the landing page are one site

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1986 soft (its last two guides land in the same tree; either order works)
Priority: P3 2026-10-22 — the public face of the docs, asked for by the maintainer; nothing in it changes a number or a decision, so not P2

## Goal

The manual at `/docs/` and the landing page at `/` read as one site. They share one palette
and one pair of typefaces from one token file, one logo that goes home and one footer. The
manual carries none of pydata-sphinx-theme's chrome that has no job here: the footer credit,
the collapse rail, "Section Navigation", "Show Source", and a breadcrumb that repeats the
title. The landing page's unwritten rules are written down, and both pages are held to them.

## Context

### What there is

- **The manual** is pydata-sphinx-theme 0.23 defaults plus three things of ours:
  `docs/docs/_static/custom.css` (the bibliography label, the numbered-equation grid, the
  brand's two colours, the drawer's wrap), the two header templates
  `docs/docs/_templates/rietx-brand.html` (mark + wordmark → the manual's front page) and
  `rietx-landing.html` (an orange mark → `rietx.org`), and `html_theme_options` in
  `docs/docs/conf.py`. WP-1986 made the split deliberate (c06871a, "teal brand to the front
  page, orange mark to the landing page"); this WP reverses it.
- **The landing page** is `docs/landing/src/shell.html` (tokens, top bar, theme toggle,
  footer) and `index.html` / `why.html`, built by `docs/landing/build.py`;
  `docs/landing/README.md` is its rulebook. Its tokens are a `:root` block, written three
  times (light, dark by system preference, dark pinned): warm neutrals (`--bg #fbfaf8` /
  `#15110d`, `--surface`, `--surface-2`, `--ink`, `--ink-2`, `--muted`, `--faint`, `--rule`,
  `--rule-strong`), one accent (`--accent #c65d0a` / `#ff9d4d`, `--accent-ink #a34c06` /
  `#ffb679`, `--accent-soft`), `--ok`/`--warn`, and `--sans` Instrument Sans, `--mono` IBM
  Plex Mono.
- **There is no style guide document.** Searched 2026-10-22: the repo, its history, and the
  maintainer's artifacts. "rietx" and "rietx landing preview" are builds of the page, with
  tokens byte-identical to `shell.html`. "House Style Plates" is the matplotlib figure style,
  and "Yue Wu Style Guide" is the voice of a blog. The rules exist only as CSS comments:
  - every bordered box is a button or a link (`index.html:4`, `shell.html:133`);
  - a command is drawn as code, flat and tinted with no border, so it never passes for a
    button, and its copy icon is the one control in it;
  - three layers, two type sizes in a disclosure;
  - hover styles only where the device hovers (a touch screen keeps `:hover` on the last
    button tapped);
  - the top bar's `gap` is a minimum, and at phone widths the gaps give way before the words;
  - the theme is the system's until a click pins one, with no third state, and the glyph
    comes from `only-light`/`only-dark` rather than script.

  The de-facto scales are in the CSS and nowhere stated:
  - **Type:** body 16px/1.55; h1 `clamp(1.9rem,4.2vw,2.8rem)`; h2 1.5rem; headings weight 600
    at −.01em; small labels .72–.75rem, uppercase, .05–.06em tracking, `--faint`.
  - **Radii:** 8px for buttons and the command chip, 10px for code boxes and figures, 12px for
    the animation rig, 999px for the theme button.
  - **Layout:** `.wrap` 1080px with a 24px gutter (16px under 360px); controls 40px tall with a
    `--rule-strong` border that turns `--accent` on hover.

### Measured 2026-10-22

Built from `main` 2330afc. Read in headless Chromium at 1440, 900 and 390 px, in both
themes, through computed styles.

| where | what the reader sees | what it is |
|---|---|---|
| everywhere | cool slate ground (`#14181e` dark) against the landing page's warm `#15110d` | pydata's `--pst-color-background` |
| everywhere | four accent hues: teal links and current items (`#3fb1c5`), violet on every link hover (`#9c5ffd`), pink inline code (`#f3c7ee`, magenta in light), and the orange landing mark | `--pst-color-primary`, `-secondary`/`-link-hover`, `-inline-code`, `--rietx-landing` |
| everywhere | body and headings in `system-ui`, code in `ui-monospace`; only the five letters of the wordmark load Instrument Sans (a Google Fonts `text=` subset) | `--pst-font-family-base`, `-monospace`; `conf.py` `html_css_files` |
| header | five controls, three looks: a 42px rounded search box, a 34px bordered "dev" box, a theme dropdown with a caret, then two bare icons | `navbar_end`, `navbar_persistent` |
| header | the theme control has three states (light, dark, auto) where the landing page's has two, and the two pages store the choice under different keys on one origin (`rietx-theme` against pydata's `theme` and `mode`), so a theme pinned on one page is not the other's | pydata `theme-switcher`; `shell.html:341` |
| drawer, < 960 px | the version, theme and two icon controls sit directly under the last tab at mismatched heights; the current tab is not marked; hovering a tab turns it violet | `.sidebar-header-items` |
| left sidebar | 25 % of the width: 368 px at 1440 for five entries. "Collapse Sidebar" is an underlined link-coloured text button; collapsed, it leaves an 80 px rail with a full-height rule for one 20 px icon. The heading "Section Navigation" is 19.2 px weight 600 and adds nothing to the tab already marked | `--pst-sidebar-primary-width`; `sidebar-collapse` and `sidebar-nav-bs` components |
| right sidebar | "On this page" is 14.4 px weight 400 with a list icon, unlike the left heading. The current entry turns weight 600 (re-wrapping its text) and teal, its bar not on the column's rule. "Show Source" is an underlined teal link with a file icon | `page-toc`, `sourcelink` |
| article head | the breadcrumb is 0.8rem with **every** item bold, and its last item is the page's own title, so on a tab's front page it reads "⌂ › Concepts" directly over an H1 "Concepts" | pydata `components/breadcrumbs.html`, `_breadcrumbs.scss` |
| article | tab sets (macOS, Linux, Windows) draw an accent-coloured border round the whole panel, a bordered box that is not a control | sphinx-design `--sd-color-tabs-*` |
| article | Previous/Next titles are 17.6 px bold and underlined | `.prev-next-title` |
| front page | the H1 "rietx" repeats the logo; the right column holds only "Show Source" | `index.md`; `secondary_sidebar_items` |
| footer | "Created using Sphinx 9.1.1." and "Built with the PyData Sphinx Theme 0.23.0.", a 59 px bar with nothing of ours | `footer_start`, `footer_end` |
| dev banner | deep red bar with a pink button, on every dev page and so on every preview | `show_version_warning_banner` |
| figures | the light twins are opaque white (`make_figures.py:82` saves only the dark twin transparent), so on a warm ground each light figure is a white box | `docs/docs/make_figures.py` |
| diagrams | mermaid's stock `default`/`dark` themes, lilac nodes | `sphinx_shared.MERMAID_*_THEME` |

### The title prefixes

Seven Concepts pages are titled "About …" and 24 Guides "How to …". The rule is stated on
each tab's front page (`concepts/index.md:3`, `guides/index.md:3`). It came from WP-1975 F5,
which read Diátaxis as giving explanation an *implicit* "About" and how-to guides a literal
"How to". It was written for a nested tree in which each page would carry its type as a
badge (WP-1975 lines 625-632, "titles doing the labelling for free"). WP-1978 then chose six
tabs, so the tab already says the type. No test enforces the prefix. 173 hand-written link
texts in 61 files quote a title, so renaming a title means editing its link texts too.

### Seams

- **pydata 0.23 options:** `logo`/`logo_link`, `navbar_start`/`navbar_end`/`navbar_persistent`,
  `html_sidebars` (the default `sidebar-collapse, sidebar-nav-bs`), `secondary_sidebar_items`
  (default `page-toc, edit-this-page, sourcelink`; a dict keys it per page),
  `article_header_start` (`breadcrumbs`), `footer_start`/`footer_center`/`footer_end`,
  `show_version_warning_banner`, `pygments_light_style`/`pygments_dark_style`.
- **CSS variables:** `--pst-color-*` and `--pst-font-family-*`, on `html[data-theme]`. pydata
  always resolves `auto` to `light` or `dark` on that attribute, so the landing page's
  `:root[data-theme="dark"]` selectors work unchanged on the manual.
- **A component is a template:** one named in `_templates/` shadows the theme's of the same
  name, as `rietx-brand.html` already does for the brand.

### Tests that pin today's choices

These are the tests whose assertions change on purpose:
- `tests/test_manual.py::test_the_new_trees_marks_are_the_favicons` pins `rietx-landing.html`
  and the `--rietx-ink` hexes to the favicon.
- `::test_every_new_tree_page_brands_its_header_and_links_the_landing_page` pins the brand's
  href to the manual's front page, and the orange mark's to `DOCS_URL`.
- The front-page test pins the three card titles and the six tabs, which do not move.

`docs/docs/check_equations.py` measures whether each numbered equation fits its column, so a
change of face or of column width re-runs it.

### The tier of each rule this WP adds

None is a heuristic in the generality sense. The WP changes no diagnostic, threshold, default
or automatic action in the package, so `rietx._audit` gains no row. The contrast bar it adds
is named practice: WCAG 2.2 AA, 4.5:1 for body text and 3:1 for large text and UI parts.

### Decisions

Taken by the maintainer on 2026-10-22, in the session that filed this WP:
1. The logo goes to the landing page, and the orange mark goes.
2. The footer credit goes.
3. The collapsed rail is too big.
4. The title prefixes and the breadcrumb are to be looked at.

Open, settled at the start of the first session with the maintainer:
- **A. Which way the palette moves.** Recommended: the manual takes the landing page's warm
  grounds and orange accent, because the landing page is the designed one and the manual's
  teal is pydata's default primary at 0.23. The cost is to re-choose the semantic colours
  (note, warning, danger, the dev banner) so that none is the accent. The landing page's own
  `--warn` (`#b5561b` / `#ffa25c`) is within a few degrees of `--accent`.
- **B. The titles.** See the Titles task.

## Non-goals

- The GUI, `rietx watch` and `rietx compare` keep their palette (`viz/theme.py`, WP-1429).
  They are an application, not this site.
- The figure palette (`viz/plots.PALETTES`). Only the light twins' *ground* changes.
- New content, and the guides WP-1986 still owes.
- Replacing pydata-sphinx-theme. Everything above is an option, a CSS variable or a
  one-component template.

## Tasks

- [ ] **Write the house style down**, as `docs/landing/README.md` § House style covering both
      pages: the rules now in CSS comments, the scales above, the label style, and which
      colour does which job.
- [ ] **One token file.** Move the landing page's `:root` blocks to `docs/landing/src/tokens.css`,
      inlined by `build.py` and copied into the manual's static files by `conf.py`.
      `custom.css` then *maps* `--pst-color-*` onto those names and spells no hex of its own.
      Decide the semantic colours here.
      A test computes the WCAG contrast of every text-on-ground pair in both themes.
- [ ] **Two typefaces, self-hosted.** Ship Instrument Sans and IBM Plex Mono as woff2 under the
      manual's `_static/fonts/`, with their OFL licence beside them, for body, headings and
      code; drop the Google Fonts subset link. A versioned tree is read for years, so it must
      not depend on an outside URL. Re-run `check_equations.py`.
- [ ] **Header.** The brand links to `rietx_home`; `rietx-landing.html` and its CSS are
      deleted. The theme control becomes the landing page's two-state toggle as a component,
      and both pages read and write one storage key. The version switcher loses its box. In
      the drawer: spacing above the controls, and the current tab marked.
- [ ] **Sidebars.** Fix the left column's width, and drop the `sidebar-collapse` component
      from `html_sidebars`; with the column narrowed there is nothing to collapse. Replace
      "Section Navigation" with the tab's name in the label style, or nothing. Give both
      sidebar headings that one label style, with no icons. Mark the current entry by colour
      and bar only, with the bar on the rule. Replace "Show Source" with a quiet link to the
      page's markdown twin (WP-1980), or drop it.
- [ ] **Breadcrumb.** Parents only, never the current page; none on a tab's front page;
      regular weight in `--muted`, so the H1 is the only heavy thing at the top of the article.
- [ ] **Footer.** The landing page's line (licence, GitHub, Cite, Sources), with the
      manual's version, in place of the theme's credit.
- [ ] **Inside the article.**
      - Inline code is ink on a tint.
      - Links are `--accent-ink` with a tinted underline, and the violet hover goes.
      - Tab sets draw no border round the panel, only a rule under the tabs.
      - Previous/Next lose the underline.
      - The front page gets a real lede and no right column.
      - The dev banner takes a semantic colour, not deep red.
      - Mermaid uses `base` with theme variables from the tokens.
      - The light figure twins are saved on a transparent ground; regenerate the 16 figures.
- [ ] **Titles** (decision B). Recommended: drop "About" from the seven Concepts H1s, nav
      labels and link texts, since Diátaxis itself treats it as implicit. For Guides, the
      sidebar shows a short label with no "How to" (a toctree entry's explicit title), while
      the H1 and the HTML title keep "How to …" for search results, `llms.txt` and prose
      links read out of the tab. Update both front pages' sentence.
- [ ] **Tests.** Change the two brand tests above. Add:
      - the token-file test, and the contrast test;
      - every built page's breadcrumb omits its own title;
      - no page names a hex outside the token file;
      - every page is free of the theme credit and of the collapse control.

      Extend `docs/landing/tools/page_shots.js` to shoot the manual's front page, a Concepts
      page and a Theory page at 1440, 900 and 390 px in both themes, beside the landing page.
- [ ] Skill: none expected. The skill links `/docs/` and quotes no page title (grep
      2026-10-22: no `[How to` or `[About` link in `docs/skill/`). Re-check at the end.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_landing.py tests/test_docs_versions.py -n auto --dist loadgroup
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python docs/docs/check_equations.py
```

Plus a look: the page shots at three widths in both themes, put beside the landing page's,
with no hue in the manual that the token file does not name.

## References

- pydata-sphinx-theme 0.23 user guide: branding, layout, theme variables.
  <https://pydata-sphinx-theme.readthedocs.io/en/stable/user_guide/index.html>
- Diátaxis, the how-to and explanation pages. <https://diataxis.fr/how-to-guides/>,
  <https://diataxis.fr/explanation/>
- WCAG 2.2, success criteria 1.4.3 and 1.4.11. <https://www.w3.org/TR/WCAG22/>
- Instrument Sans and IBM Plex Mono, SIL Open Font License 1.1.

## Handover log

- **2026-10-22** — filed from the maintainer's review of the manual's look. No open WP owns
  it: WP-1986 is the guides and the old tree's retirement; WP-1443 is prose read by a
  newcomer; WP-1812 is the manual for rigid bodies. The measurements above are from that
  session's screenshots of `main` 2330afc. Next: settle decisions A and B with the
  maintainer, then start at the house-style task, since every later task cites it.
