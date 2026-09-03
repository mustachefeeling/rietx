# WP-1331 — The landing page enters the repository, and the data comes redacted

Milestone: unscheduled · Status: ✅ 2026-09-03 — page and payload both in the
repository; the payload is decimated to the unrefinable side of rietx's own
guideline, which is what let it in
Depends on: — (1003 soft: `DOCS_URL` and the Pages workflow are its)

## Goal

`rietx.org/` serves a landing page built from `docs/landing/` by the same Pages
workflow that builds the manual, and the manual moves to `rietx.org/manual.html`.
The page's source is version-controlled, and so is the data it animates — but only
as a figure of the contributor's series: decimated below what rietx will refine,
with the reacting phases named and the support formulation not.

## Context

The page was written 2026-09-02 with Claude Code and lives, untracked and outside
any repository, at `~/rietx-agent-runs/landing-page`. Its own README carries the
plan this WP executes. One 734-line `src/index.html` (markup, CSS and JS in one
file, `%%…%%` placeholders), a 90-line `build.py`, `build_demo.py`, four PNGs
(~900 kB), the fluorapatite example, and `tools/` for screenshots and the leak
check.

**The fence is the reason this WP is not a `git mv`.** `data/demo.json` was 1.9 MB
of a contributor's observed in-situ series and `data/transcript.json` is their
agent run. Root CLAUDE.md § Licensing states the rule this specialises: **data
carries its own fence, per file**, and a PyPI upload publishes harder than a
repository does. Identifiers were never the hard part — `build_demo.py` already
refuses any filename, scan index or specimen token, `build.py`'s `leaks()` scans
the assembled page and `tools/check_transcript.py` the transcript, all
case-insensitively. The hard part was *fidelity*: a full-resolution copy of an
unpublished in-situ series is the measurement.

**So the payload is redacted by resolution and committed.** Decimated to every
second channel it sits at 2.38 steps across a peak, against the 5-to-10 rietx
itself asks for (`optimize.statistics`, `PATTERN_UNDERSAMPLED`) — a figure of the
series rather than the series, asserted by `tests/test_landing.py` rather than
trusted. **Decimated, not averaged**: a mean of k channels divides the counting
noise by √k, so the observed cloud tightens onto the calculated curve and the
difference curve flattens, and the panel then shows a better fit than the Rwp
printed beside it. Measured at k = 2 and k = 3 by rendering both. No private
repository, no secret, no fetch; a fork builds the whole site.

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

- **Publishing the series at acquisition resolution.** What ships is decimated to
  the unrefinable side of the package's own guideline; the bundle's own files
  (`curves.npz`, `metadata.csv`, plots, logs, `agent_transcripts/`) stay out
  entirely.
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
- [x] `pages.yml`: run `build.py --site`, then sphinx. Three links in the page
      that meant "the manual" and pointed at the site root now point at
      `manual.html`.
- [x] The payload joins the repository, decimated ×2 by `build_demo.py`, with the
      factor and the resulting steps-per-FWHM recorded in the file and asserted by
      a test.
- [x] `README.md` and `pyproject.toml`: the manual is `rietx.org/manual.html`.
- [x] The page copy the maintainer asked for: the rig's caption is the
      contributor's credit and nothing else, the transcript pane's label is
      `Prompt`, and the support phases ship as `support 1`–`3` in two shades with
      a legend entry each. The names are gone from the branch's history too.
- [x] `examples/fap_lab.py` + `tests/data/fluorapatite.cif`, so
      `tests/test_examples.py` runs the script the page quotes.
- [x] `tests/test_landing.py`: the ignore rules (both directions), the
      placeholders, the leak tokens, every relative link resolves against what
      the build writes, the document skeleton, the fetch, and every `rx.*` name
      the page prints. Plus the manual's TeX guard, which began policing the
      page copied in beside it.
- [x] Skill: none. The landing page is not a refinement surface and nothing an
      agent driving rietx does reaches it.

Nothing is left for the maintainer but review: page, payload and workflow are all
in the repository and a fork builds the whole site with no secret.

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

### 2026-09-03 (3rd session) — the page stops naming the sample

The animation now credits the contributor and says nothing else about the
specimen. Its caption is one line, the transcript pane is labelled `Prompt`
rather than "The brief", and the three support phases are `support 1`–`3` — two
of them drawn in their own shade with a legend entry each, the third flat on the
axis at 0 wt % and left unlabelled. The names are out of the branch's fifteen
commits as well as its tip, so the merge cannot carry them into main.

**Done.** The caption trimmed to the credit; `.brief`/`#brief`/`renderBrief` and
the pane's label renamed to prompt; `--support-2`/`--support-3` tokens in all
three theme blocks; `PC`/`LEGEND_IDX` in the page assign a shade per support
phase in payload order and label the first two. `build_demo.PHASES` became
`REACTING` plus `phase_columns`, which reads every other `wtpct_` column off the
bundle's own `metadata.csv` header — so the builder no longer knows the names
either. `data/demo.json` renamed in place (no bundle here to rebuild from) and
its dead `determined` flag dropped, since the caption that used it is gone.
`data/transcript.json`: the prompt's phase list and the `PHASE_UNCONSTRAINED`
line genericised. Two tests replace the `decimationNote` assertion:
`test_the_animation_caption_is_the_credit_and_nothing_else` and
`test_the_support_phases_ship_unnamed`.

**The decision worth keeping: the fence is not knowing, not a denylist.** The
first cut of this added the three names to `build.LEAK` so a rebuild could not
reintroduce one — which writes them into the repository in the act of refusing
them. A denylist publishes what it denies. Taking the support columns positionally
off the bundle's header removes the name from the pipeline instead, and is the
stronger fence for costing nothing to state. `build.py` now says so where the
tokens would have gone.

**Gotchas.** One of the removed words also occurs, by coincidence, as a made-up
phase name in a strain-cap fixture that has been on `main` for months. It is not
the contributor's data and rewriting it would rewrite `main`, so it stays; a
successor who greps and gets a hit there has not found a leak. And the page
no longer says it is showing decimated channels; `decimation` and
`steps_per_fwhm` in the payload plus `docs/landing/README.md` § The payload are
where that is on the record now. Flagged to the maintainer as the one line they
may want back.

**Measured** (`[dev]` venv, darwin/arm64): `tests/test_landing.py` 14 → 16,
`test_landing.py` + `test_manual.py` + `test_docs_consistency.py` 45 passed.
Legend and both support shades checked by rendering the served site in light and
dark at 2× and looking, not by reading the CSS.

**Next:** nothing in this WP. Review and merge are the maintainer's.

### 2026-09-03 (2nd session) — the payload comes in too, redacted by resolution

The private-repo plan is gone. The maintainer asked for the payload to be cut
down to what actually drives the panel and committed, and it is: page, data and
workflow are all in the repository, a fork builds the whole site with no secret,
and there is nothing left owed to anyone.

What made it committable is *resolution*, not identifiers — those were already
stripped. Decimated to every second measured channel the file sits at 2.38 steps
across a peak against the 5-to-10 rietx itself asks for, so it is a figure of the
contributor's series and not the series. `tests/test_landing.py` asserts that
rather than trusting it.

**The measurement worth keeping.** Averaging k channels is the obvious reduction
and it is the wrong one. It divides the counting noise by √k, so the observed
cloud tightens onto the calculated curve and the difference curve flattens — the
panel then shows a *better* fit than the Rwp printed beside it. Rendered at k = 2
and k = 3 and looked at: the scatter visibly collapses while the header still
reads 13.3 %. Decimation keeps every point it keeps a real measured channel,
noise and all; what it costs is peak shape, the calculated line growing spikier
as apexes fall between retained channels. That trade is the right way round for a
panel whose whole job is to show what a real fit looks like.

*Measured*: 1.95 MB → 0.99 MB, 1297 → 649 channels, 4.87 → 2.38 steps per FWHM
(the native data was already marginal at 4.87, just under the guideline). Peak
widths read off the **calculated** curve, not the observed one: any peak finder
reads counting noise as peaks and drags the median to about one channel, which is
how the first measurement of this came out at 1.75 and would have justified a far
harsher cut. Fast selection **4084 passed, 122 skipped**, 2:22 (`[dev]`,
darwin/arm64, nothing else mid-suite), run from a state with no
`docs/landing/site`. `tests/test_landing.py` is 14 tests now, +1 on the entry
below; the new one fails on a full-resolution rebuild with the message that says
how to fix it, checked. **CI now reads the same figures**, where the entry below
had to predict 4082/123 — with the payload committed there is no
payload-conditional skip left.

*Gotcha for a successor*: `build_demo.py`'s decimation factor **defaults to 1**,
so a rebuild that forgets the argument silently restores full resolution. That is
what the test is for, and why the factor is recorded in the payload rather than
only in a command someone has to remember.

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

- Fast selection on the merged tree (`origin/main` had not moved, so the branch
  *is* the merged tree): **4083 passed, 122 skipped**, 2:06, run from a state with
  no `docs/landing/site`. The WP adds **15** tests: `tests/test_landing.py` 13 and
  `tests/test_examples.py` 4 → 6. This checkout has the payload; **CI does not**,
  and there it is **14 passes and 1 skip** — `test_the_inline_build_stays_a_fragment`
  needs a payload to have an inline build to check, so CI should read 4082 passed
  and 123 skipped. Measured both ways by moving `data/` aside: 19 passed with it,
  18 passed + 1 skipped without. A new skip is not a new pass.
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

**The review pass** (`/code-review medium --fix`) found eight and all were
applied; two would have gone red on CI and both were reproduced here before being
accepted. `test_manual`'s exclusion set was frozen at import while
`tests/test_landing.py` *creates* `docs/landing/site` during the run, so on a
checkout with no prior landing build the set is empty, sphinx picks the page up
anyway, and the TeX guard fails on the page's own shell prompt — reproduced by
deleting `site/` and restoring the frozen form (1 failed, 19 passed, that exact
message). And the two modules sat in different `xdist_group`s, so `--site`'s
`rmtree` could run while sphinx copied the same directory. The leak guard is now
case-insensitive (half of what it guards is prose cut by hand: `sio2` in a
filename, `SiO2` in a sentence) with inlined base64 stripped first, since a
four-character token turns up in a 200 kB PNG by chance. And the skill's "the
manual: `https://rietx.org`" now resolved to the landing page — the same bug the
new test guards *inside* the page, missed outside it, fixed in all three copies.
Three findings were declined: the skill frontmatter's "hosted at" the site root
(defensible, and pinned by `test_skill.py`), `assert`-for-validation in the
landing scripts (maintainer scripts, never run under `-O`), and canvas edge cases
unreachable with the real payload.

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
