# WP-1412 — the theme survey's pictures

Evidence behind the recommendation in `../1412-the-theme-nobody-chose.md`.
Taken 2026-09-14 on macOS 15 (arm64), chromium 1223, against the manual at
`1.4.0`.

Versions compared: furo 2025.12.19, pydata-sphinx-theme 0.21.0,
sphinx-book-theme 1.1.3, shibuya 2026.7.12, all under sphinx 9.1.0 and
sphinxcontrib-mermaid 2.1.1.

## How they were taken

Each theme got a full `sphinx -W -q -E` build of `docs/manual` with
`html_theme` overridden and nothing else changed. The builds were served over
`http://127.0.0.1`, because a `file://` page drops a CSS `mask-image` as
cross-origin and mermaid comes from a CDN. Playwright then loaded four pages in
a context with `color_scheme` emulated, scrolled to the subject, and shot the
viewport.

Light and dark are the **system** preference, which is what all four themes
answer by default. The reader-picks-dark case behaves differently, and it is
measured in the WP's handover rather than shown here.

The probe scripts were not kept. They hardcoded scratch paths, and a later
comparison wants a fresh build against whatever the versions are then.

## The sixteen sheets

`<page>-<mode>-<width>.png`, four themes across in the order furo, pydata,
book, shibuya. The 1440 px sheets are scaled by half; the 390 px ones are at
their own size. All are quantised to 256 colours.

| page | what it is | what to look at |
|---|---|---|
| `front` | `manual.html` | where the 34 chapters are reachable from |
| `equation` | `profiles.html`, scrolled to the widest numbered equation | whether the equation clears its own number |
| `figures` | `using/concepts.html` | whether one of the committed light/dark pair shows, or both |
| `mermaid` | `using/files.html` | whether the diagram follows the page |

## The two pydata sheets

`pydata-configured-front.png` and `pydata-configured-chapter.png` show three
states across: the theme as shipped, the theme with the migration's config and
CSS, and the same with a fork of `components/sidebar-nav-bs.html`. The middle
state is what `html_theme_options` alone buys. The third is what it takes to
put the chapter list back on the page.
