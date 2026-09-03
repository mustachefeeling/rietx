# WP-1331 — The landing page enters the repository, and the data does not

Milestone: unscheduled · Status: ✅ 2026-09-03 — the private payload repository
and its `SITE_DATA_TOKEN` secret are the maintainer's; the page publishes without
them, animation panel dead
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

### 2026-09-03 — the page is in the repository, and it works served

The landing page written the day before now lives in `docs/landing/` and is
published by the same workflow that publishes the manual: `rietx.org/` is the
page, `rietx.org/manual.html` is the manual, and nothing else moved. It was in no
repository at all before this, and the contributor's observed series it animates
still is not — that stays in a private repository the workflow fetches, behind
ignore rules a test asserts in both directions.

The part that was not planned is the part worth knowing. The page was authored as
an Artifact *fragment*, and nobody had ever served `build.py --site`'s output: it
had no charset, so every `·` and `°C` rendered as mojibake, and the payload fetch
its own source comments described did not exist, so the animation never ran
outside the artifact. Both were found by serving the built site and looking at it,
not by reading the diff. A move that had been treated as a `git mv` was in fact
three defects deep.

**Done.** Thirteen files into `docs/landing/`, `data/` and the built pages left
out. Four `.gitignore` rules, two of which stop the payload being published and
one of which stops the four figures being hidden. `root_doc = "manual"`,
`index.md` → `manual.md`, conditional `html_extra_path`. `pages.yml` fetches the
payload, builds the page, then builds the manual. The `--site` build gained a
document skeleton and a real fetch. Three links in the page that meant "the
manual" and pointed at the site root. `examples/fap_lab.py` and
`tests/data/fluorapatite.cif`. `tests/test_landing.py`, thirteen tests. The
manual's TeX guard stopped policing the page copied in beside it.

**Measured** (`[dev]` venv, darwin/arm64, no other suite running — `pgrep`
checked):

- Fast selection on the merged tree: **4083 passed, 122 skipped**, 2:13. The WP
  adds **15** tests: `tests/test_landing.py` 13 and `tests/test_examples.py`
  4 → 6. On a checkout **without** the payload — which is CI, and a fork — that is
  **14 passes and 1 skip**, not 15 passes: `test_the_inline_build_stays_a_fragment`
  needs a payload to have an inline build to check. Measured both ways by moving
  `data/` aside: 19 passed with it, 18 passed + 1 skipped without.
- The full selection did **not** run, and should not: no `src/` file changed, so
  nothing here can move a measured number (`tests/CLAUDE.md` § Running, rung 3).
- `git check-ignore --no-index`, one path at a time: the six paths answer as the
  Context table says. The guard was broken on purpose once — deleting the
  `docs/landing/preview.html` rule turns the test red with "git tracks it,
  expected ignored".
- `examples/fap_lab.py`: converged, Rwp = 0.0893, GoF = 1.60, a = 9.37228(10) Å,
  c = 6.88626(9) Å, 3.7 s. The numbers the page prints, now from a script the
  suite runs rather than from beside it.
- The built site served over http: `/` is the page with the animation running
  (readout `24/275 · 28 min · 300 °C · 0.2 % H₂ in N₂`, four legend entries),
  `/manual.html` is the manual, no console errors but the browser's own
  `/favicon.ico` probe.

**Gotchas.**

- `html_extra_path` must stay conditional. `-W` turns a missing entry into an
  error and `tests/test_manual.py` builds the manual on every run, so an
  unconditional entry breaks the suite on any checkout that has not built the
  page.
- The two builds are not interchangeable. `build.py` must keep emitting a
  *fragment* (the Artifact runtime refuses a file with its own `<html>`) and
  `--site` must keep emitting a document. `tests/test_landing.py` pins both.
- Anything that walks the manual's build output now sees pages Sphinx never
  rendered. One guard already had to learn that; a new one should exclude
  `COPIED_IN` rather than widen what it treats as markup.
- The page's own README is the file map and the source of its numbers. It is a
  record now, not a plan.

**Next**, and only the maintainer can do the first: create the private payload
repository `yue-here/rietx-site-data` with `demo.json` and `transcript.json` in
it, and add a fine-grained read-only token as the repository secret
`SITE_DATA_TOKEN`. Until then every push publishes the page with a dead animation
panel — the workflow skips the fetch rather than failing, so nothing goes red to
say so. Then: point the `rietx.org` DNS/Pages config at the built site if it is
not already, and decide whether the rig header's "model to confirm" should read
Claude Sonnet 5, which `data/transcript.json` already supplies.

- **2026-09-03** — created.
