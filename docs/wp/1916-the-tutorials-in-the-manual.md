# WP-1916 — the tutorials in the manual, and the quickstart is a notebook

Milestone: unscheduled · Status: 🔄 2026-10-08 — claimed by @yue-here
Track: Render what the fit already knows
Depends on: 1545 (the notebooks)
Priority: P3 2026-10-07 — the notebooks are readable on GitHub today, so a workaround covers it; nothing waits on it but WP-1917

## Goal

The manual renders the five tutorial notebooks, outputs included, as a Part 1
chapter that comes right after Install. That chapter is the manual's
quickstart, at the URL `using/quickstart.html`. The page that held that URL
moves to a name that says what it is, and every link to it follows.

## Context

**Why.** WP-1545 committed five executed notebooks in `examples/tutorials/`
and fenced their rendering out as a follow-up. The maintainer decided on
2026-10-07 that the Jupyter notebooks are now the human quickstart. The
manual's current `using/quickstart.md` (title "A first refinement", built on
`examples/nac_11bm.py`) is downgraded to an ordinary chapter.

**Measured 2026-10-07** (macOS arm64, worktree venv `[dev]`, a throwaway patch
reverted afterwards):

- `uv pip install myst-nb` adds seven packages (myst-nb 1.4.0, jupyter-cache,
  sqlalchemy, click, tabulate, importlib-metadata, zipp) and moves nothing
  already installed. myst-parser stays at 5.1.0, Sphinx at 9.1.0.
- With `"myst_parser"` replaced by `"myst_nb"` in `conf.py`'s `extensions`,
  `nb_execution_mode = "off"`, the five `.ipynb` copied under
  `docs/manual/using/tutorials/` and a toctree page for them, the whole manual
  builds under `-W --keep-going` with **zero** warnings. Every `myst_*` setting
  in `conf.py` is still honoured, because myst-nb runs myst-parser underneath.
- All nine PNG outputs and all four HTML outputs render. The tutorial pages are
  48 to 80 kB each, and the build output grows from 9.4 MB to 11 MB.
- The HTML reprs (WP-1544) hard-code no colour, so their tables take furo's
  light and dark themes. The figures are light PNGs and show as light panels
  in dark mode. That is what Jupyter shows, so accept it. A dark pair would
  need a second build of each notebook, and the notebook is the authority.

**Design.**

- **Execution off.** `build.py` commits the outputs and `tests/test_tutorials.py`
  executes every notebook on every push. The manual shows the committed
  outputs, so it shows exactly what the tests ran. Executing again at docs
  build would make the manual's numbers a second run's.
- **The notebooks stay in `examples/tutorials/`.** Sphinx reads only its source
  tree, so `conf.py` copies the `.ipynb` files into a gitignored directory under
  `docs/manual/using/` at build. That follows the glossary's precedent
  (`_write_glossary`). It cannot reuse `_generated/`, which `exclude_patterns`
  keeps out of the sources. Never commit the copies. The copy step finds the
  notebooks by `build.SOURCES`'s glob, so a sixth tutorial needs no edit here.
- **The URL.** `using/quickstart.md` becomes the tutorials index page, titled
  as the quickstart, with a toctree of the five notebooks and a `{download}`
  link for each `.ipynb`. The current page moves to `using/first-refinement.md`.
  Keeping the quickstart URL avoids a dead link. The landing page's "Get started
  here" (`docs/landing/src/index.html:80`) and any stranger's bookmark land on
  the notebooks, which is what the maintainer wants a newcomer to find.
- **The links to repoint**, every empty-text link to `quickstart.md` that means the NAC
  walkthrough (measured with `git grep`, 2026-10-07): `cli.md:33`,
  `data.md:145`, `exports.md:86`, `files.md:1580`, `history.md:183`,
  `install.md:81`, `report.md:79`. Each one names "the 11-BM pattern" or "the
  walkthrough", so it follows the page to `first-refinement.md`. `install.md:81`
  ("is the first refinement") should point to the new quickstart instead.
  Also `conf.py:187`'s comment and `tests/test_examples.py:5`'s docstring.
- **Toctree order** in `manual.md`: install, quickstart (the tutorials), then
  first-refinement where quickstart was. Part 1's intro paragraph names the
  chapters in order and changes with it.
- **The docs extra** gains `myst-nb`. `pages.yml` installs `.[docs]` and `dev`
  includes `docs`, so CI and the suite's `tests/test_manual.py` build pick it up
  with no workflow edit. Check that `myst-parser>=3` is still needed as a
  direct pin or is myst-nb's to carry.

**What the guards do not see.** `tests/test_manual_api.py` scans
`USING_DIR.rglob("*.md")`. It will scan the new index page and never the
notebooks, so a rietx name in a notebook's markdown cell goes unchecked. Their
code is covered, because `test_tutorials.py` executes it. Accept that gap and
say so in the index page's guard note. Do not widen the API guard to `.ipynb`
in this WP.

**Not generalised.** `using/gui-quickstart.md` keeps its name. It is the GUI's
own first session, and the landing page links it from the GUI section. The
landing's "Agent quickstart" is WP-1917's neighbour and untouched here.

### Inherited

## Non-goals

- The landing page and Colab links (WP-1917, gated on rietx 1.7 on PyPI).
- Executing notebooks at docs build, or any change to `examples/tutorials/build.py`.
- Dark-mode figures for the notebooks.
- New tutorials (WP-1545's README lists the gaps).

## Tasks

- [x] `docs` extra gains `myst-nb`; `conf.py` swaps the extension, sets
  `nb_execution_mode = "off"`, and copies the notebooks into a gitignored
  `using/tutorials/` at build.
- [x] `using/quickstart.md` → `using/first-refinement.md`, every link repointed,
  and a new `using/quickstart.md` index over the five notebooks with download
  links; `manual.md` toctree and Part 1 intro updated.
- [x] Tests: the manual builds with the five notebook pages present; a test
  holds the copied set equal to `examples/tutorials/` by glob; the rendered
  index links all five. Look at one rendered page in light and dark.
- [ ] Skill: none. The notebooks teach a person to check an agent, and WP-1545
  already decided the skill gains no pointer.

## Acceptance

The manual builds under `-W` with all five tutorials rendered, and
`using/quickstart.html` is the tutorials index.

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_examples.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- myst-nb: https://myst-nb.readthedocs.io (`nb_execution_mode`).
- Procida, D. (2017). Diátaxis: the tutorial type.

## Handover log

- **2026-10-07** — created. No open WP owns this: WP-1545 fences rendering the
  notebooks in the manual out as a follow-up, and WP-1331, 1409 and 1411 are
  closed. The myst-nb measurement above was taken this day on a reverted patch.
  Next: the first task.
