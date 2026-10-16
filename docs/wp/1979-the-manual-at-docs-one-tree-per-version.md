# WP-1979 — The manual at rietx.org/docs/, one tree per version

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1978 (the new tree)
Priority: P2 2026-10-16 — back to P2: WP-1978's tree is built (PR #1004)

## Goal

`rietx.org/docs/stable/` serves the manual of the latest tag, `/docs/dev/` serves `main` under
a "not yet released" banner, and the last few minor releases stay reachable. A version
switcher moves between them on the same page. The installed package links to its own
version's docs.

## Context

Decided in WP-1975 (§ F8, 2026-10-15):
- `/docs/stable/` is the latest tag, and `/docs/` redirects there.
- `/docs/dev/` is `main`, under a banner.
- The last few minor releases are kept; older ones are pruned to stay inside GitHub Pages'
  1 GB cap.
- Old chapters keep their URLs until each is retired, then get an HTML redirect stub. GitHub
  Pages has no server-side redirects.

Why it matters: issue #407 hit a verb on the hosted manual (built from `main`) that the PyPI
release lacked, and `docs/manual/using/compatibility.md` tells users to pin.

**What the spike showed** (WP-1975 § I; `docs/wp/1975-spike/tools/build_sphinx.sh` and
`switcher.py`). pydata-sphinx-theme 0.23.0 does all of the following, checked in chromium:
- reads a `switcher.json` at a fixed URL;
- keeps the reader on the same page when they switch;
- shows its own version-warning banner on `dev` only.
A meta-refresh `index.html` at `/docs/` redirects to `stable/`. One built version of the
spike's nine pages was 6.3 MB. The spike's build then wrote Sphinx's `.doctrees` pickles into
the site, so that figure includes them. Measure the real manual without them, before
choosing how many minors to keep.

**Today's deploy** (`.github/workflows/pages.yml`) builds once and deploys one fresh site, so
nothing from an earlier build survives. Keeping versions needs an accumulating deploy. Two
options to weigh at the start: a `gh-pages` branch that each release adds a directory to, or a
workflow that rebuilds every kept tag. The landing page stays at `/`.

**The package's links.** `rietx._about.DOCS_URL` is `"https://rietx.org"` today. Each
`HelpEntry.anchor` is a `page.html#id` relative to the old tree's root (`help.py:84`), and
the GUI joins the two (`gui/session.py:265`, `gui/src/lib/help.ts`). Under this WP they point
into the installed version's tree: `dev` for a `.dev0` build, the `major.minor` otherwise.
Three things follow:
- Every anchor today names an old-tree page (`profiles.html`, `background.html`,
  `using/data.html` and six more). None of those paths exists under `/docs/<version>/` until
  WP-1986 moves Theory. So the repoint waits for the anchors' pages, or the anchors move with
  it. `tests/test_help.py::test_every_anchor_resolves_in_the_built_manual` checks the old
  tree's build, so it stays green while every popover link 404s. Point it at the new tree in
  the same change.
- `DOCS_URL` is also quoted by the README, `pyproject.urls` and the skill's frontmatter, which
  cannot follow the installed version. Keep it as the site root and add the versioned base
  beside it.
- The `{source}` role links `blob/main` (`docs/manual/conf.py` `_SOURCE_REF`). A tagged build
  must link its tag, or its line numbers drift.

### Inherited

- **2026-10-16, from WP-1981.** The Reference tab's generated pages carry two facts a
  versioned build must set. The diagnostic index links each source file at
  `REPO_URL/blob/main/src/...` (`docs/reference_pages.py`, `diagnostic_page`), so a
  per-version tree should link the tag it was built from. The roadmap page opens with the
  build's own `rietx.__version__` and reads `docs/ROADMAP.md` at build time, so each version
  shows the roadmap of its own day. `conf.py` writes the bodies into an ignored
  `docs/docs/_generated/` on every build.
- **2026-10-16, from WP-1978.** The new tree is `docs/docs/` (PR #1004). Its `conf.py` takes
  the fenced constants, the citation style, the mermaid theme and the `{source}` role from
  `docs/sphinx_shared.py`, which the old `conf.py` imports too. `tests/test_manual.py` builds
  it as the `built_docs_tree` fixture (xdist group `manual-build`), reads its pages as
  `DOCS_PAGES`, and holds each to the page contract (`_contract_breaches`). Nothing about
  versions is configured yet: no `DOCS_VERSION`, no `html_baseurl`, no switcher, no
  `show_version_warning_banner`, and `navbar_end` lacks `version-switcher`. The spike's
  `conf.py` has all four. `pages.yml` still builds only `docs/manual/`. The favicon is the old
  tree's file, read through `../manual/_static/favicon.svg`.

## Non-goals

- The new tree itself (WP-1978). Retiring chapters and writing their stubs (WP-1986; this WP
  provides the stub mechanism).

## Tasks

- [ ] Measure one version of the real new tree, and choose how many minors to keep.
- [ ] The accumulating deploy: `stable`, `dev` and the kept minors, plus `switcher.json` and
      the `/docs/` redirect, with the landing page untouched.
- [ ] Redirect stubs: a generator for a retired chapter's old URL (meta-refresh plus
      `rel=canonical`), and a test that every retired path has one.
- [ ] A versioned docs base beside `DOCS_URL`, and `help.py`'s anchors on it once their
      pages exist in the new tree; a test pins the mapping from `rietx.__version__` to the
      URL, and the anchor test builds the new tree.
- [ ] The `{source}` role links the build's tag rather than `main`.
- [ ] `docs/RELEASING.md` gains the step that adds a version, and the step that prunes one.
- [ ] Skill: none; the skill links the docs through `DOCS_URL`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_landing.py -n auto --dist loadgroup
gh run list --workflow pages.yml --limit 1     # the deploy that published /docs/stable/ and /docs/dev/
```

## References

- pydata-sphinx-theme: "Version switcher dropdowns" and `show_version_warning_banner`.

## Handover log

- **2026-10-16** — filed from WP-1975's slate. No open WP owns docs hosting or versions.
