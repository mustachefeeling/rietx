# WP-1331 — The landing page enters the repository, and the data does not

Milestone: unscheduled · Status: 🔄 2026-09-03
Depends on: — (1003 soft: `DOCS_URL` and the Pages workflow are its)

## Goal

`rietx.org/` serves a landing page built from `docs/landing/` by the same Pages
workflow that builds the manual, and the manual moves to `rietx.org/manual.html`.
The page's source is version-controlled; the contributor's observed data that the
page animates is not, and cannot become so by accident.

## Context

The page was written 2026-09-02 with Claude Code and lives, untracked and outside
any repository, at `~/rietx-agent-runs/landing-page`. Its own README carries the
plan this WP executes. One 734-line `src/index.html` (markup, CSS and JS in one
file, `%%…%%` placeholders), a 90-line `build.py`, `build_demo.py`, four PNGs
(~900 kB), the fluorapatite example, and `tools/` for screenshots and the leak
check.

**The fence is the reason this WP is not a `git mv`.** `data/demo.json` is 1.9 MB
of a contributor's observed in-situ series and `data/transcript.json` is their
agent run; neither may enter the repository, and a public release asset would not
do either, because release assets are public. Root CLAUDE.md § Licensing states
the rule this specialises: **data carries its own fence, per file**, and a PyPI
upload publishes harder than a repository does. `build.py` already enforces it at
build time with a token list (`LEAK`, `LEAK_RE`) over the whole assembled page,
and `tools/check_transcript.py` over the transcript; this WP adds the second line
of defence, which is `.gitignore` plus a test that asserts the ignore rules.

**The move breaks three `.gitignore` rules, two of them in the dangerous
direction.** Measured 2026-09-03 with `git check-ignore -v --no-index`, one path
at a time, reading the exit code:

| path | rule that matched | outcome |
|---|---|---|
| `docs/landing/src/index.html` | `!docs/**/*.html` | committed — wanted |
| `docs/landing/build.py` | none | committed — wanted |
| `docs/landing/dist/index.html` | `dist/` | ignored — wanted |
| `docs/landing/preview.html` | `!docs/**/*.html` | **committed**, and it is the built page with `demo.json` inlined |
| `docs/landing/img/*.png` | `*.png` | **ignored**, the images vanish silently |
| `docs/landing/data/*.json` | none | **committed** |

The `*.png` line is the fourth directory of committed images that rule has
swallowed; its own comments record the first three (Part 1 figures, the GUI
screenshots, and `src/rietx/gui/static`), and `tests/test_gui_dist.py:167` and
`tests/test_gui_manual.py:245` are the precedent for asking `git check-ignore`
in a test rather than trusting the file to be read correctly. The two leaks fail
in the direction no test currently covers: a rule that publishes rather than one
that hides.

**Serving the page at `/` means the manual gives up `index.html`.** `pages.yml`
builds `docs/manual` into `site` and uploads it; `conf.py` gets
`root_doc = "manual"` and `html_extra_path`, and `docs/manual/index.md` is renamed
`manual.md`. Measured 2026-09-03: **no** page in `docs/manual` cross-references
the root document (no `index.md`, no `` :doc:`index` ``, no `<index>` in a
toctree), and only two lines in the repository point at the site root as the
manual — `README.md:86` and `pyproject.toml:124`. Every other `rietx.org/…` link
is `page.html` and is unaffected, `help.py`'s anchors are `page.html#id`, and
`_about.DOCS_URL` is the site root and stays exactly as it is. The rename was
probed in 2026-08 (the landing page's README records it): clean `-W` build,
`manual.html` emitted, furo's sidebar retargets itself.

**`html_extra_path` is conditional, because `-W` makes a missing entry an
error.** The landing page's `site/` is a build product of
`docs/landing/build.py --site`, and it needs `data/` to be complete. A source
checkout has neither, and `tests/test_manual.py` builds the manual on every run,
so `conf.py` adds the entry only when the directory exists. A build without it is
the manual alone, which is the correct answer for a fork.

## Non-goals

- **Creating the private data repository and pushing the contributor's data.**
  That is an outward-facing action on the maintainer's account with someone
  else's data; this WP wires `pages.yml` to fetch from it and stops there.
- Rewriting any of the page's copy, or filling in the model name the rig header
  still shows as "model to confirm" (the landing page README § What is still
  missing).
- A custom domain, analytics, or a social preview image.

## Tasks

- [x] Open the WP: this file, the ROADMAP row under § Unscheduled, Current focus.
- [x] `docs/landing/`: `src/`, `build.py`, `build_demo.py`, `img/`, `tools/`,
      `README.md` — thirteen files. `dist/`, `preview.html`, `data/`, `site/`
      and `__pycache__` stay out.
- [x] `.gitignore`: un-ignore `docs/landing/img/*.png`, ignore
      `docs/landing/preview.html`, `docs/landing/data/` and `docs/landing/site/`,
      each with the comment saying which direction it fails in.
- [x] `conf.py`: `root_doc = "manual"`, conditional `html_extra_path`;
      `git mv docs/manual/index.md docs/manual/manual.md`.
- [x] The `--site` build renders: a document skeleton (the source is an artifact
      *fragment*, so a web server got mojibake) and the payload fetch its own
      comments promised but did not have. **Not planned — found by serving the
      output and looking**, which nobody had done.
- [x] `pages.yml`: fetch the payload from the private repo with a secret, run
      `build.py --site`, then sphinx. The fetch is best-effort so a fork's build
      still passes. Three links in the page that meant "the manual" and pointed
      at the site root now point at `manual.html`.
- [x] `README.md` and `pyproject.toml`: the manual is `rietx.org/manual.html`.
- [x] `examples/fap_lab.py` + `tests/data/fluorapatite.cif`, so
      `tests/test_examples.py` runs the script the page quotes.
- [x] `tests/test_landing.py`: the ignore rules (both directions), the
      placeholders, the leak tokens, every relative link resolves against what
      the build writes, the document skeleton, the fetch, and every `rx.*` name
      the page prints. Plus the manual's TeX guard, which began policing the
      page copied in beside it.
- [x] Skill: none. The landing page is not a refinement surface and nothing an
      agent driving rietx does reaches it.

**Left for the maintainer, and only they can do it** (§ Non-goals): create the
private payload repository `yue-here/rietx-site-data` holding `demo.json` and
`transcript.json`, and add a fine-grained read-only token as the repository
secret `SITE_DATA_TOKEN`. Until then every push publishes the page with no
animation — the workflow skips the fetch rather than failing.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_landing.py tests/test_manual.py tests/test_manual_api.py tests/test_docs_consistency.py -q
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m ruff check src tests examples
```

The manual builds warning-free with `manual.html` as its root, `index.html` is
absent from that build (the landing page supplies it), and `git check-ignore`
answers as the table above says for all six paths.

## References

- The landing page's own `README.md`, moved to `docs/landing/README.md`: the
  file map, what is still missing, and the sources behind the page's numbers.
- Root CLAUDE.md § Licensing (data carries its own fence, per file) and
  § Conventions (`_about.py` owns every brand spelling).
- `tests/test_gui_dist.py` § the `*.html` rule, for the `check-ignore`-in-a-test
  pattern and the three earlier times a repo-wide rule swallowed a committed
  asset.

## Handover log

- **2026-09-03** — created.
