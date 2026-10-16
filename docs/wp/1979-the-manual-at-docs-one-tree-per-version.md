# WP-1979 — The manual at rietx.org/docs/, one tree per version

Milestone: unscheduled · Status: ✅ 2026-10-16 — PR #1023; the first deploy runs on merge,
and the first stable tree is v1.10.0's
Track: The repo's own process
Depends on: 1978 (the new tree)

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
nothing from an earlier build survives. Keeping versions needs an accumulating deploy. The
landing page stays at `/`.

**Decided 2026-10-16: each release stores its own tree as a release asset.** Three stores
were weighed:
- a storage branch (`gh-pages`, as mike and NumPy do);
- rebuilding every kept tag on each deploy;
- a tarball attached to each GitHub release.

Rebuilding fails here. Every conf.py imports the live package, and sphinx-multiversion builds
each tag against the one installed package. Read the Docs was weighed too and declined for
now: it would serve `docs.rietx.org`, and moving later only needs the stubs this WP builds.

**Measured 2026-10-16** (`sphinx -b html -d <elsewhere>`, doctrees excluded). One version of
the new tree is 7.4 MB. The old tree, which WP-1986 moves in, adds about 14 MB, so a full
version is about 21 MB. Six minors, stable and dev come to about 170 MB. Today's whole Pages
artifact is 24 MB compressed. Size does not bind against the 1 GB cap, so the last **6** minors
are kept. The first release whose tag holds `docs/docs/` is v1.10.0. Until it ships, `/docs/`
sends readers to `dev/`.

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

**The new tree** (WP-1978, PR #1004; checked against the tree 2026-10-16) is `docs/docs/`. Its
`conf.py` takes the fenced constants, the citation style, the mermaid theme and the `{source}`
role from `docs/sphinx_shared.py`, which the old `conf.py` imports too. `tests/test_manual.py`
builds it as the `built_docs_tree` fixture (xdist group `manual-build`), reads its pages as
`DOCS_PAGES`, and holds each to the page contract (`_contract_breaches`). Nothing about
versions is configured yet: no `DOCS_VERSION`, no `html_baseurl`, no switcher, no
`show_version_warning_banner`, and `navbar_end` lacks `version-switcher`. The spike's `conf.py`
has all four. `pages.yml` still builds only `docs/manual/`. The favicon is the old tree's file,
read through `../manual/_static/favicon.svg`.

**Two more `blob/main` links** (WP-1981). The Reference tab's diagnostic index links each
source file at `REPO_URL/blob/main/src/...` (`docs/reference_pages.py:427`), and the roadmap
page links each milestone record the same way (`:604`). A tagged build links its tag in both.
The roadmap page opens with the build's own `rietx.__version__` and reads `docs/ROADMAP.md` at
build time, so each version shows the roadmap of its own day. `conf.py` writes the generated
bodies into an ignored `docs/docs/_generated/` on every build.

## Non-goals

- The new tree itself (WP-1978). Retiring chapters and writing their stubs (WP-1986; this WP
  provides the stub mechanism).

## Tasks

- [x] Measure one version of the real new tree, and choose how many minors to keep.
- [x] The accumulating deploy: `stable`, `dev` and the kept minors, plus `switcher.json` and
      the `/docs/` redirect, with the landing page untouched. `release.yml`'s `docs` job
      attaches the tree after `publish` and dispatches `pages.yml`, which builds `dev` and runs
      `docs/docs_versions.py`.
- [x] Redirect stubs: a generator for a retired chapter's old URL (meta-refresh plus
      `rel=canonical`), and a test that every retired path has one. `OLD_PAGES` freezes the
      48 pages the old tree published, and WP-1986 fills `RETIRED`.
- [x] The mapping from a version to its hosted directory, `docs_versions.docs_version`, pinned by a
      test. The rest moves to WP-1986: the versioned base beside `DOCS_URL`, `help.py`'s
      anchors on it, and the anchor test on the new tree. None of the 13 pages the anchors name
      exists in the new tree yet, so a base built now would have no reader.
- [x] The `{source}` role links the build's tag rather than `main`. So do the Reference tab's
      two file links. `sphinx_shared.DOCS_VERSION` says which hosted version a build is, and
      `SOURCE_REF` follows it.
- [x] `docs/RELEASING.md` gains the step that adds a version, and the step that prunes one.
      Adding is step 8's check. Pruning is automatic, so its section says how to change it.
- [x] Skill: none; the skill links the docs through `DOCS_URL`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_landing.py -n auto --dist loadgroup
gh run list --workflow pages.yml --limit 1     # the deploy that published /docs/stable/ and /docs/dev/
```

## References

- pydata-sphinx-theme: "Version switcher dropdowns" and `show_version_warning_banner`.

## Handover log

- **2026-10-16** — The manual can now be hosted per release. Each release keeps its built
  manual on its GitHub release, and every Pages deploy lays out `dev`, `stable` and the last
  six minors under `rietx.org/docs/`, with a version menu on each page. Dev and older releases
  show a banner. A release's pages link the code at its own tag. Old-tree pages get redirect
  stubs as they retire, and a test fails if one is lost. Nothing is live until this merges, and
  the first stable tree will be v1.10.0's. Read the Docs was weighed with the user and set aside
  for now; it would serve `docs.rietx.org`.

  *Done.* `docs/docs_versions.py` chooses, fetches and lays out the kept trees, writes
  `switcher.json`, `/docs/index.html` and the stubs. release.yml's new `docs` job builds at
  the tag after `publish`, attaches `rietx-docs-X.Y.Z.tar.gz` and dispatches pages.yml.
  pages.yml builds `main`'s tree at `/docs/dev/` and runs the script. The new tree's conf has
  the switcher (`check_switcher: False`, since the file is written after the build), the
  banner, and a canonical URL at `stable/` for releases. `sphinx_shared.DOCS_VERSION` is `dev`
  unless release.yml sets the minor, and `SOURCE_REF` follows it. RELEASING.md gains step 8
  and a section on versions. Task 4's package half moved to WP-1986 (its `### Inherited`).

  *Measured* (`[dev]` venv, darwin/arm64). One version of the new tree is 7.4 MB without
  doctrees. Today's Pages artifact is 24 MB compressed. In chromium, against a site assembled
  from a dev build and a faked 1.9 tarball: `/docs/` and a stub redirect, the banner shows on
  dev only, and switching keeps the reader's page. Fast suite on the final tree: 10838 passed,
  185 skipped, 2 xfailed, 2 failed. The two failures were the stale WP index and a false
  positive on `tarfile.open(path, "w:gz")` in `test_portability.py`, both fixed after the run,
  and those files then passed 61 of 61. This session added 22 cases (14 functions, 0.23 s in
  all). The full suite did not run, because nothing here moves a measured number.

  *Review* (`/code-review high`). Applied five:
  - the old manual's step builds as `dev` too;
  - a stub points into `dev/` until a release holds its page;
  - `assemble` can run twice over one site;
  - an unset `DOCS_VERSION` now means `main`'s build;
  - the mapping moved out of `_about.py`, which imports nothing by design.

  Tests now pin the ref each build links and the refusal of a mismatched version. Declined
  three: a `.post` release (none is cut here); the `sys.path` line in
  `reference_pages._source_ref` (the conf adds the same path); and a failed asset download
  failing the whole deploy. That last one is a choice for the maintainer. Today the deploy
  stops loudly rather than dropping a version.

  *Gotchas.* pydata's switcher navigates only after checking the target page exists, so a
  probe must wait for the URL to change. The Pages upload skips hidden files, so the old
  tree's `.doctrees` never reached the site, but a tarball would carry them without `-d`.

  *Next.* Merge, then read `gh run list --workflow pages.yml --limit 1` and open
  `rietx.org/docs/` (it should land on `dev/`). Cutting v1.10.0 exercises the `docs` job; check
  it with RELEASING.md step 8. WP-1986 is unblocked and holds the rest.
- **2026-10-16** — filed from WP-1975's slate. No open WP owns docs hosting or versions.
