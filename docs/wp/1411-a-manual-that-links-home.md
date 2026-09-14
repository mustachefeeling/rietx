# WP-1411 — a manual that links home

Milestone: unscheduled · Status: 🔄 2026-09-14 — landing copy edited and the
manual's brand forked onto furo's sidebar
Depends on: —

## Goal

The landing page's rewritten copy is typo-free and published, and every page of
the manual carries the rietx mark and wordmark at the top left, linked to
`rietx.org`.

## Context

Three things arrived together on 2026-09-14.

**The landing page's copy was rewritten** and left uncommitted in the main
checkout: the hero lede, the agent section's framing, the example and GUI
section heads, six feature bullets and the validation lead. The content is the
maintainer's and stands; this WP touches spelling, hyphenation and markup only.

**The manual is a dead end.** `grep -r "rietx.org" docs/manual/**/*.md` returns
nothing. Since WP-1331 put the landing page at `/` and the manual at
`/manual.html`, a reader arriving from a search has no route back.

**Furo's brand link is hardcoded.** `sidebar/brand.html` writes
`href="{{ pathto(master_doc) }}"`, and furo's `theme.conf` offers
`light_logo`, `dark_logo`, `sidebar_hide_name`, `announcement`, `footer_icons`
and the `source_*` keys, none of which touches the link. Furo documents
overriding the template through `templates_path`, and the shipped file points
at that page in its own comment, so the fork is the supported mechanism.

Two constraints on the brand's construction:

- **An `<img>`-embedded SVG cannot see the page's theme.** `_static/favicon.svg`
  carries its own `prefers-color-scheme` block, which answers the *system*
  theme and not furo's pinned toggle. This is the failure the committed figure
  pairs exist to avoid. So the mark is a CSS `mask-image` over that same file
  with the colour from a variable, the shape `custom.css` already uses for the
  agent admonition's icon.
- **The wordmark stays HTML text.** A webfont loaded by the page does not reach
  inside an `<img>`-embedded SVG. The landing page builds its own brand the same
  way, as an inline mark beside the word in `.brand`.

### Why furo stays

Furo was never compared against anything: WP-0604 lists it in a dependencies
bullet and once as "Tooling: Sphinx, MyST-Parser, sphinxcontrib-bibtex, furo
(all BSD-licensed)". That is the whole record. It is, however, load-bearing now,
which is a different claim and the only one that is evidence for keeping it —
five things are built on furo specifics: `body[data-theme]` for the mermaid
light/dark detection (`conf.py`, WP-1068), two dark blocks in `custom.css`, the
`only-light`/`only-dark` figure pairs in both parts, the equation-number grid
over furo's absolutely positioned `span.eqno` (WP-1408 § G3), and WP-1408's
layout measurements against furo's 736 px column. WP-1412 carries the survey
that would decide this with rendered pages rather than with a feature list.

## Non-goals

- The theme survey itself (WP-1412).
- The landing page's content. Four claims are flagged in the handover log and
  left standing.
- The two brand colours. The manual's favicon is `#6d4aff` and the landing
  page's is `#d8660c`, and both stay as they are.

## Tasks

- [x] The landing page's new copy, transplanted from the main checkout verbatim
- [ ] Typos on it: nine mechanical fixes, no sentence's meaning moved
- [ ] `tests/test_landing.py` caption assertion and `docs/landing/README.md`
- [ ] The brand: forked `sidebar/brand.html`, `conf.py`, `custom.css`
- [ ] A built-HTML guard on the brand link
- [ ] WP-1412 filed, ROADMAP rows for both
- [ ] Tests: the doc suites plus a look at the rendered pages in both themes.
      No refinement runs here, so no obs/calc/diff PNGs
- [ ] Skill: none. Nothing here changes how an agent drives rietx — no
      diagnostic code, no correction, no task shape (root CLAUDE.md § skill)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_landing.py tests/test_manual.py \
    tests/test_docs_consistency.py -n auto --dist loadgroup
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python docs/landing/build.py --site
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

Plus the part no test covers: the built manual screenshotted in both themes and
at phone width, and the built landing page in both themes.

## References

- Furo's sidebar customisation: <https://pradyunsg.me/furo/customisation/sidebar/>
- The shipped template this fork was taken from:
  `furo/theme/furo/sidebar/brand.html`

## Handover log

- **2026-09-14** — created.
