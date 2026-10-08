# WP-1917 — a Jupyter quickstart on the landing page, opened in Colab at the release

Milestone: unscheduled · Status: 🔄 2026-10-09 — claimed by @yue-here
Track: Render what the fit already knows
Depends on: 1916 (the manual pages it links; ✅ 2026-10-08, PR #826)
Priority: P3 2026-10-09 — rietx 1.7.0 is on PyPI and tagged, so the Colab links can go live

## Goal

The landing page's hero carries a "Jupyter quickstart" button beside "Agent
quickstart". It opens to the five tutorial notebooks. Each row reads it in the
manual, opens it in Colab, or downloads the `.ipynb`. Every Colab link opens
the notebook as tagged at the latest release, so its `%pip install rietx`
installs the version it was built with.

## Context

**Why it waited** (superseded 2026-10-09: v1.7.0 is tagged at a9eaebb4 and
on PyPI, so the gate is open). Every notebook needs rietx 1.7 or later (WP-1545). PyPI
served 1.6.0 on 2026-10-07. `pages.yml` deploys on every push to `main`, so a
Colab link merged before the 1.7 release would install 1.6 in its first cell
and fail on the next one. Read and download links work today. The button ships
whole, so this WP waits for 1.7 rather than shipping a button with a dead
column.

**Why a tag and not `main`.** `main`'s notebooks are built against the next
`.dev0` and may call API that PyPI does not have yet. The tagged tree's
notebooks are rebuilt by the release itself (`docs/RELEASING.md` step 1, last
sentence), so `blob/vX.Y.Z/examples/tutorials/NN_slug.ipynb` and
`pip install rietx` at that release agree. The URL form is
`https://colab.research.google.com/github/<owner>/<repo>/blob/<tag>/<path>`,
with `<owner>/<repo>` read from `_about.REPO_URL`, never spelled.

The manual's own source links chose `main` over a tag (`docs/manual/conf.py`,
the note above `_SOURCE_REF`). That choice derived the tag from
`pyproject.version`, which named an untagged release on 2026-09-14 and would
have 404'd. This WP reads the newest `v*` tag from git itself, so that failure
does not apply. Two consequences:
- `pages.yml`'s `actions/checkout` must fetch tags (`fetch-tags: true`, or
  `fetch-depth: 0`). The default shallow checkout has none.
- `docs/landing/build.py` refuses to build when it finds no tag. A silent
  fallback to `main` is the failure this WP exists to avoid.

**The rows are derived.** `examples/tutorials/README.md` already holds a
hand-written table of the five. A third copy on the landing page would drift.
So `build.py` reads each notebook's title off its first markdown cell's `# `
heading and finds the notebooks by `examples/tutorials/build.py`'s `SOURCES`
glob. A sixth tutorial then appears with no edit here. Keep the row to its
title and three links; the landing register is few words (memory:
landing-page-register).

**The hero.** It holds one `<details class="qs" id="quickstart">` today, with
its JS in `src/index.html` (any `#quickstart` link opens it; the copy button
serialises the prompt). The second disclosure gets its own id. Give both the
same `name` attribute so opening one closes the other (exclusive `<details>`,
Chrome 120, Safari 17.2, Firefox 130). Check the pair at 320 px, the narrowest
width the top bar is designed for.

**What other parts of the page already say.**
- The Python API section's "Get started here" links `using/quickstart.html`.
  After WP-1916 that URL is the tutorials index, so it needs no edit.
- That section's code box is notebook 02's first cell, held equal to the
  committed notebook by a test (WP-1545's second review round). Its bar may
  gain an "Open in Colab" link to 02. Leave the code itself alone.

**Unmeasured, and only the maintainer can measure it.** Whether Colab's
preinstalled numpy or matplotlib makes `%pip install rietx` ask for a runtime
restart. It needs a Google sign-in, so the maintainer runs each notebook once
from its tagged Colab URL. If a restart is needed, the notebook's opening
markdown says so in one line.

**The "until 1.7" lines.** Each notebook's opening cell and
`examples/tutorials/README.md` say "Until rietx 1.7 is on PyPI, install it from
GitHub instead". They were meant to go before the 1.7 cut. Superseded in part
2026-10-09: the cut came first, so the v1.7.0 notebooks carry the line into
Colab until the next release's tag. The line is stale but harmless there,
since its condition is now false and `%pip install rietx` installs 1.7.0.
`main` drops it now.

**The manual's tutorials index** (from WP-1916, PR #826).
`using/quickstart.html` is a table of the five notebooks with a `{download}`
link each (`docs/manual/using/quickstart.md`). A Colab column in that table is
the manual's place for Colab links.
`tests/test_manual.py::test_every_tutorial_renders_with_its_outputs_and_the_quickstart_links_it`
reads that page's article body, and needs widening if the column becomes
required. The manual copies notebooks from `examples/tutorials/` on every build,
so dropping the "until 1.7" lines needs no manual edit.

## Non-goals

- The manual's tutorial chapter and the quickstart rename (WP-1916).
- Binder (minutes to start) and JupyterLite (no numba in Pyodide).
- A Colab badge inside the notebooks themselves.

## Tasks

- [x] Drop the "until 1.7" lines from the five `.py`
  sources and the README, then rebuild the notebooks.
- [x] `build.py`: the newest `v*` tag, a refusal when there is none, and the
  rows derived from the notebooks; `pages.yml` fetches tags.
- [x] The "Jupyter quickstart" disclosure in the hero, exclusive with the agent
  one; checked at 320 px in light and dark.
- [x] Tests in `tests/test_landing.py`: the built page has one row per notebook
  by glob; every Colab URL names the tag `build.py` found; every Read link
  resolves to a page the manual builds.
- [ ] The maintainer's Colab run of each notebook at the tag, its result
  recorded in the handover.
- [x] Skill: none. The page is for people, and the agent quickstart is unchanged.

## Acceptance

After 1.7 is on PyPI, every Colab link on the deployed page opens a notebook
that runs top to bottom on a fresh Colab runtime.

```sh
.venv/bin/python docs/landing/build.py --site
.venv/bin/python -m pytest tests/test_landing.py tests/test_tutorials.py -q
.venv/bin/python -m ruff check src tests examples docs/landing
```

## References

- Colab's GitHub URL form: https://colab.research.google.com/github/
- `docs/landing/README.md`, the landing page's rulebook.

## Handover log

- **2026-10-07** — created. No open WP owns this: WP-1545 (🔄, in review)
  covers the notebooks and not their exposure, and WP-1331 and 1411, which
  built the landing page and its links home, are closed. Split from WP-1916
  because its gate is the 1.7 release and 1916's is none. Next: the "until 1.7"
  task, before the cut.
