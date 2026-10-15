# WP-1979 — The manual at rietx.org/docs/, one tree per version

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1978 (the new tree)
Priority: P3 2026-10-16 — down a rung from P2: nothing can start until 1978's tree exists

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
spike's nine pages was 6.3 MB; measure the real manual before choosing how many minors to keep.

**Today's deploy** (`.github/workflows/pages.yml`) builds once and deploys one fresh site, so
nothing from an earlier build survives. Keeping versions needs an accumulating deploy. Two
options to weigh at the start: a `gh-pages` branch that each release adds a directory to, or a
workflow that rebuilds every kept tag. The landing page stays at `/`.

**The package's links.** `rietx._about.DOCS_URL` is `"https://rietx.org"` today, and
`rietx.help` builds per-entry anchors on it (`help.py:84`). Under this WP they point into the
installed version's tree: `dev` for a `.dev0` build, the `major.minor` otherwise.

## Non-goals

- The new tree itself (WP-1978). Retiring chapters and writing their stubs (WP-1986; this WP
  provides the stub mechanism).

## Tasks

- [ ] Measure one version of the real new tree, and choose how many minors to keep.
- [ ] The accumulating deploy: `stable`, `dev` and the kept minors, plus `switcher.json` and
      the `/docs/` redirect, with the landing page untouched.
- [ ] Redirect stubs: a generator for a retired chapter's old URL (meta-refresh plus
      `rel=canonical`), and a test that every retired path has one.
- [ ] `DOCS_URL` and `help.py`'s anchors point at the installed version; a test pins the
      mapping from `rietx.__version__` to the URL.
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
