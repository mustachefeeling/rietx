# WP-1411 — a manual that links home

Milestone: v1.5 · Status: ✅ 2026-09-14 — landing copy published, and
every manual page carries a brand linked to rietx.org
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
  pairs exist to avoid. The mark is therefore inline SVG taking its `fill` from
  a variable. Wearing that same file as a CSS `mask-image` was written first,
  since `custom.css` already draws the agent admonition's icon that way and it
  keeps the geometry in one file; it is dropped on a `file://` build and was
  replaced (see the handover log). The inlined paths are pinned equal to the
  favicon's by a test.
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
- [x] Typos on it: ten mechanical fixes, no sentence's meaning moved
- [x] `tests/test_landing.py` caption assertion and `docs/landing/README.md`
- [x] The brand: forked `sidebar/brand.html`, `conf.py`, `custom.css`
- [x] Two built-HTML guards: the brand link, and the mark against the favicon
- [x] WP-1412 filed, ROADMAP rows for both
- [x] Tests: the doc suites plus a look at the rendered pages in both themes.
      No refinement runs here, so no obs/calc/diff PNGs
- [x] Skill: none. Nothing here changes how an agent drives rietx — no
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

### 2026-09-14 — the manual stopped being a dead end

The published site is now two pages that know about each other. Every page of
the manual carries the rietx mark and wordmark at the sidebar's top left, over
the release, and clicking it goes to the landing page — which nothing under
`docs/manual/` linked to at all before today, because WP-1331 moved the manual
to `/manual.html` and left furo's brand pointing at the manual's own front page.
The landing page's rewritten copy is published with ten spelling and markup
fixes and no sentence's meaning touched.

The session also found what the theme choice rests on, which is nothing. Furo
appears in WP-0604 as a name in a dependencies bullet and once as "all
BSD-licensed", with no alternative rendered and no criterion written down. That
is a reason to look, not a reason to move, and WP-1412 is filed to look
properly: five things are built on furo specifics now, so the cost of a swap is
real and measurable in a way the case for pydata is not.

**Done.**

- The maintainer's uncommitted rewrite of `docs/landing/src/index.html`,
  transplanted from the main checkout and committed verbatim first, so the typo
  pass reads as its own diff.
- Ten fixes: *quantative*, "alongside number", "full differentiable", the
  hyphen in "low-signal", `python` → `Python` twice, a stray space inside the
  caption, an empty `<figcaption>` left behind when the GUI caption went, the
  link text *Powderline* → *PowderLine* which the same sentence already spelled
  correctly, and `<code>JAX</code>`/`<code>pytorch</code>` → plain JAX and
  PyTorch, because a code span promises a token and `backend=` takes `"jax"`
  and `"torch"`.
- `docs/manual/_templates/sidebar/brand.html`, a fork of furo's own, plus
  `templates_path` and an `html_context` carrying `_about.DOCS_URL` and
  `_about.DIST_NAME` in `conf.py`, and the brand's rules in
  `_static/custom.css`.
- Two guards in `tests/test_manual.py`, and a third rewritten in
  `tests/test_landing.py`.
- `docs/wp/1412-the-theme-nobody-chose.md` and both ROADMAP rows.

**Measured.**

- Fast suite **4730 passed, 132 skipped in 2:09-2:16**, `[dev]`, darwin/arm64, this
  worktree's own venv, nothing else mid-suite (`pgrep` checked). The full
  selection did not run and should not: docs and tests only, nothing that can
  move a measured number (`tests/CLAUDE.md` § Running, rung 3).
- **+2 tests, both passes, no new skip.** `tests/test_manual.py` went 19 → 20
  on the brand-link guard and 20 → 21 on the favicon guard; the caption test in
  `tests/test_landing.py` was rewritten, not added, and that file stays at 16.
- The brand-link guard was made to fail on purpose: with the fork moved aside,
  **39 of 39 built pages** report furo's own `manual.html`.
- Four theme states in chromium at 1440 px, with the mark's computed fill read
  off the page: system light `#6d4aff`, system dark `#a48cff`, and both
  **pinned** states that disagree with their system giving the pinned colour
  rather than the system's. Plus the drawer at 390 px in both themes. The two
  pinned states are what an `<img>` logo would have got wrong.
- The landing page built with `build.py --site` and read in both themes. Its
  only console error is the browser's own `GET /favicon.ico` 404, a fallback
  request the page never makes, and it predates this work.

**Gotchas.**

- **A CSS `mask-image` is dropped on a `file://` page.** The mark was first
  written as `_static/favicon.svg` worn as a mask, which is how `custom.css`
  already draws the agent admonition's icon and which keeps the geometry in one
  file. It renders over http and **silently disappears** from a local build,
  chromium treating a `file://` mask source as cross-origin — so a reviewer
  opening `_build/html/` sees no mark and no error. Measured both ways before
  switching to inline SVG. Nothing in the suite would have caught it: the guards
  read HTML, and the HTML was correct.
- **Furo's `.sidebar-brand` is `flex-direction: column`, and a custom rule has
  to say `row` out loud.** Leaving it unset while setting `flex-wrap: wrap` put
  `flex-basis: 100%` on the release against the *height*, which wrapped it into
  a second column and printed the version to the right of the mark.
- **A `var()` inside a custom property is substituted where it is *declared*.**
  `--color-agent-accent: var(--color-rietx-ink)` on `:root` froze at the light
  hex and inherited that frozen value down, while the two dark blocks redefine
  `--color-rietx-ink` on `body`, which a `:root` alias never sees. Every agent
  admonition in the manual took a light purple border on a dark page, against a
  chip that did switch — the failure `custom.css`'s own header says the file
  exists to avoid, introduced by this branch and caught by the review pass. The
  alias is declared on `body` now. The lesson generalises past this file: an
  alias must be declared on the same element the thing it aliases is.
- The `worktree_only` gate refuses a `-C` at the main checkout from inside a
  worktree, so the uncommitted edit came across as a plain file copy, after
  checking the file was unchanged between the two trees' base commits. **The
  main checkout's copy is still dirty**, and restoring it is the maintainer's
  once this merges.

**The review pass** (`/code-review high --fix`) found the `:root` alias above
and two smaller things, all three applied: the wordmark and the test's expected
text now come from `_about.DIST_NAME` rather than spelling the brand, and the
favicon guard asserts the build succeeded so a failed build is reported by the
test named for it. Three declined, each for a reason: the site's two brand
colours are a decision the maintainer took this session (purple manual, orange
landing, both left as they are); the now-dead `.shot figcaption` rule documents
what a restored caption would want; and the absolute brand href is the point of
the WP. It also cleared several things independently — every link the rewritten
copy adds resolves in the built manual, `read_recipe` exists so the PowderLine
claim is true, and the `SVG_SHAPES` comparison is not vacuous.

**Left standing, deliberately.** Four content claims on the landing page, none
of them typos and all the maintainer's to keep or change: "GSAS, Rietica, XND,
etc. in progress", where the registry has `topas` and `fullprof` and neither
Rietica nor XND appears anywhere in this tree; "Opens TOPAS, FullProf and
PowderLine formats", where `io/recipe.py` also *writes* PowderLine and the
previous wording said so; "automatically updated test matrix", where
`docs/VALIDATION.md` is generated and byte-asserted but regenerated by a command
someone runs; and "Data is fluorapatite from the GSAS-II tutorial", whose
predecessor carried the 60 ppm wavelength explanation that is now nowhere on the
page.

**Next:** nothing on this WP. [1412](1412-the-theme-nobody-chose.md) is the
successor and needs nothing from here beyond its own Context, which carries the
five couplings and the twenty-line fork a move would throw away.

- **2026-09-14** — created.
