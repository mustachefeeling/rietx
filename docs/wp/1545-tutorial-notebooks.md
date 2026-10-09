# WP-1545 — tutorial notebooks

Milestone: unscheduled · Status: 🔄 2026-10-07 — in the maintainer's review rounds (two done); every task done, PR #812 open
Track: Render what the fit already knows
Depends on: 1544 (readable objects in a notebook)

## Goal

A short suite of executed tutorial notebooks lets a person build a working
mental model of rietx. Each notebook runs from `pip install "rietx[viz]"`.
Adding a notebook needs no test edit.

## Context

**Who it is for.** Humans who may only ever drive rietx through an agent, and
who need a model of what the agent is doing in order to judge its work. The
trigger is a friend's demo notebook (LLongley94/rietx_demo), which WP-1544
made readable.

**Layout and authority.** Root CLAUDE.md says a walkthrough has one authority,
and it is `examples/`. So the source of each tutorial is a `# %%` percent-format
script in `examples/tutorials/NN_slug.py`. Its `.ipynb` is generated from it,
executed, and committed beside it. A test holds the two equal. The CLAUDE.md
clause gains one sentence naming the notebooks as a generated projection.

- `examples/tutorials/README.md` is the index. Each row gives the notebook,
  what it teaches, its data and licence, and its runtime. The README also says
  how to add one.
- `examples/tutorials/build.py` builds with nbformat and nbclient directly.
  - It sets `TELEMETRY_ENV` from `_about.py` (never the spelled name).
  - It records no timing, strips timestamps and renumbers execution counts,
    so a rebuild of unchanged code changes nothing.
  - **It fails on any stderr output.** Warnings print absolute source paths.
  - It names its encoding and newline, because `test_portability` scans
    `examples/`.
  - It stamps `rietx.__version__` into the notebook metadata.

**Tests** find notebooks by glob.
- Each notebook executes through nbclient in the fast tier. A plain script run
  would exercise none of the display. `test_examples.py` says per-push
  execution is the whole value, so each notebook is sized to fit that tier.
- The `.ipynb` code and markdown cells equal the `.py` cells.
- The stamped major.minor equals the package's.
- No output contains a home directory path.
- The README lists every notebook.

`docs/RELEASING.md` gains "rebuild the tutorials" as a cut step. Prose never
restates a number that sits in an output, or the two drift apart.

**Notebooks.** Five, matching the topics asked for. Real data comes from
`rietx.examples.examples_dir()`: `FAP.XRA`, `FAP.EXP`, `11BM_NAC.fxye` and
`cod_1000236.cif`, licences in `tests/data/README.md`. Synthetic data is built
in a visible cell with `Refinement.predict` plus Poisson noise. That cell
states the true values, so the notebook grades the fit against them.

| # | Notebook | Data | What it teaches |
|---|---|---|---|
| 01 | Quickstart: look, then Le Bail | FAP | `data.plot()`, `diagnose` (the trustworthy fields only), pre-fit ticks, the fitted range, Le Bail, `print(result)`, the plot |
| 02 | Simple Rietveld | FAP, structural | Plans and stages, the parameter table, hold and tie, diagnostics, history, SKILL §4's judging order |
| 03 | Peaks, indexing, Le Bail | Synthetic orthorhombic phase from a COD CIF, with `systems=` narrowed | `pick_peaks`, the peak list, editing it in code with `fit_peaks`, `index_pattern`, the candidate table, `best_or_none()`, `structure_from_candidate`, Le Bail. Points to the GUI Peaks panel for drag-editing. |
| 04 | Peak shape and microstructure | Synthetic standard, and a sample with known size and strain | The Gaussian-variance and Lorentzian-FWHM sum rules, `lab_calibrate`, `save_instrument_profile` and `load_instrument_profile`, `lab_sample_refine`, `result.microstructure` against the truth |
| 05 | Sequential fits | Synthetic ramp, after `tests/test_sequential.py:66` | `refine_sequential`, carry, `SeriesResult`, `direction="both"`, quarantine |

**02 replaces `examples/fap_lab.py`.** Keeping both would be a second copy of
one walkthrough. The landing page (`docs/landing/README.md:49`) and
`tests/test_examples.py` repoint to the notebook source.

**03 cannot use FAP.** FAP's right cell ranks first but the gate abstains, and
the run takes about 95 s. Indexing also runs under a wall-clock budget
(`SearchSpec.budget_seconds`), so FAP's committed output would depend on the
machine that built it. A synthetic phase with narrowed systems is reproducible.
Mind the open hazards: WP-1909 (false lines on a falling flank), WP-1910 (the
extinction screen on an unrefined cell; run Le Bail first) and WP-1542 (seed a
Le Bail background).

**How each notebook reads** (`yue-docs-style`, tutorial type, and `yue-prose`;
British spelling):
- The top cell gives the goal, prerequisites, data provenance and runtime.
- Each cell holds one idea. Markdown before it says what to look at, and
  markdown after it says what the output showed.
- Each notebook ends with a "checking an agent's work" box mapped to SKILL §4.
- Load the `rietx` skill before writing any fit.

**Measured while building WP-1544** (2026-10-07, macOS arm64, `[dev,notebooks]`):
- Synthetic silicon (`tests/_synthetic_silicon.py`, cubic F) searched over
  cubic and tetragonal ranks a tetragonal I sub-cell first, with cubic F third,
  and the result abstains with `bravais_ambiguous`. Notebook 03's synthetic
  phase must be measured the same way before it is chosen, and the abstention
  may itself be the lesson.
- A rietx figure in a notebook is encoded for a screen since WP-1544's
  follow-up: 69 kB of base64 for the FAP fit figure, where it was 259 kB. Five
  notebooks of about five figures each commit about 1.7 MB per rebuild. Pass no
  `dpi=` for this; it would change only files.
- In a kernel, `result.plot()` as a cell's last line shows the figure once. A
  trailing `;` or an assignment shows nothing (WP-1544).
- `SeriesResult` prints its `summary()` and has no HTML table. `FitReport`,
  `ExtinctionScreen` and `Capabilities` print the generic tree. Build a view
  only where a notebook needs one.

### Inherited

- **2026-10-09, from WP-1547.** CI now executes the notebooks on the py3.14
  leg alone. The other legs set `RIETX_TUTORIALS=skip`, which skips
  `test_tutorial_executes_clean` and nothing else. `test_tutorials.py`'s
  docstring states the trade: a stdlib name newer than 3.11 in a tutorial's
  own cells passes every check. The nightly still executes them on 3.13 on
  three operating systems. A local run executes them as before. If PR #812
  rewrites that docstring, keep the paragraph.

## Non-goals

- Rendering the notebooks in the manual (myst-nb or nbsphinx). That is a
  follow-up if the committed notebooks are not enough.
- Widgets of any kind (`DESIGN.md` fence).
- The later rows below.

**Later rows**, listed in the README as gaps: background and amorphous humps,
and Kβ lines (both asked in the demo repository's readme); NAC's CaF₂ impurity
and what the difference curve shows; QPA.

## Tasks

- [x] `build.py`, the README and the test harness, with notebook 01.
- [x] 02 Simple Rietveld, replacing `examples/fap_lab.py`, with the landing
  page and `test_examples.py` repointed.
- [x] 03 Peaks, indexing, Le Bail.
- [x] 04 Peak shape and microstructure.
- [x] 05 Sequential fits.
- [x] The designed views WP-1544 deferred, built only where a notebook needs
  one (`FitReport`, `ExtinctionScreen`). Notebook 03 needed one for
  `PeakList` (fourteen lines a peak in the generic tree); no notebook prints a
  `FitReport` or an `ExtinctionScreen`, so neither was built.
- [x] `docs/RELEASING.md` step and the root CLAUDE.md sentence.
- [x] Skill: a pointer to the tutorials in `references/`, or "none" and why.
  None (2026-10-07): the notebooks teach a person to check an agent, and each
  checklist is drawn from `SKILL.md` §4 and §4b, so an agent would read them
  for no rule it lacks. They also ship in the repository, not the wheel.

**The maintainer's review round (2026-10-07):**

- [x] Authorship at the top of each notebook and the README.
- [x] The install as a `%pip` cell, never executed by a build.
- [x] 01 explains `ftol` in the stage lines.
- [x] A history summary that does not run off the screen (`HistoryTree.summary`).
- [x] The `.rex` project layout, in 02.
- [x] 03 names the GUI's Peaks tab and its gestures.
- [x] matplotlib a dependency, `viz` kept as an empty extra, the docs swept.
- [x] 05: a series is a list; loading one from files under two naming conventions.
- [x] 05: `carry` written out and explained.

**The second round (2026-10-07):**

- [x] The landing page's code box is notebook 02's first cell, its output panel
  is that cell's committed output, and a test holds both there.
- [x] Can uPlot replace matplotlib in the library? Answered no, with the
  measurements in the handover entry; nothing changed.

## Acceptance

Every notebook executes in the fast tier. The committed `.ipynb` cells equal
their sources. No output carries a home path.

```sh
.venv/bin/python -m pytest tests/test_tutorials.py -q
.venv/bin/python examples/tutorials/build.py --check
.venv/bin/python -m ruff check src tests examples
```

## References

- Procida, D. (2017). Diátaxis: the tutorial type.
- Data provenance and licences: `tests/data/README.md`.

## Handover log

### 2026-10-07 (4th entry) — the second review round: the landing box, and uPlot

The landing page's example now shows exactly what notebook 02 runs and
prints. Before, its code had three lines the notebook never ran, and its
output had numbers from before this WP. A test now compares the whole box with
the committed notebook. So a rebuild that changes a number fails until the
page is refreshed. The maintainer also asked whether uPlot could replace
matplotlib in the library. It cannot, because uPlot needs a browser to draw
anything. So matplotlib stays a dependency for figures and nothing changed.

**Done.**
- `docs/landing/src/index.html`: the box is notebook 02's first cell with bare
  file names, without `build_report`, `report.summary` or `plot(path=)`. The
  panel is that cell's committed output: esds 0.00008 (was 0.00010), 4.6 steps
  over 76 peaks (was 4.7 over 175), and `RESOLUTION_UNCONSTRAINED` added. The
  report-summary block is gone.
- Notebook 02 gained the box's `# GSAS raw format` comment, and its `fit` call
  is wrapped as the box wraps it. Its outputs did not move on rebuild.
- `tests/test_tutorials.py`: `QUOTED` (four strings, a second copy) is gone.
  `test_the_landing_box_is_the_tutorial` reads both `<pre>` blocks from the
  page. Every code line must be a line of the cell, with `examples_dir() / `
  dropped. Every stretch of the panel between `…` cuts must be in the cell's
  committed output. It reads committed output, not a live run, because the
  panel quotes counts such as "4786 of 5751" that another platform could move.
  The live execute test now takes its codes from the panel itself. Both halves
  were made to fail once (the unwrapped `fit` line; an esd set back to
  0.00010).
- `docs/landing/README.md` says what the test holds.
- The figure was redrawn from the notebook's first fit in both styles. It was
  pixel-identical to the committed PNGs, so `img/` is untouched.

**Measured, for the uPlot answer** (macOS arm64, `[dev]` venv):
- matplotlib 28 MB, Pillow 13 MB, fontTools 14 MB, the rest of its
  dependencies about 3 MB: about 58 MB. llvmlite alone is 126 MB.
- `[viz]` held matplotlib and plotly until WP-1461 put the vendored uPlot
  under `write_html`. So `rx.viz.write_html` already needs no Python package.
  Its inlined scripts are about 170 kB (uPlot 51, svgcanvas 61, rxplot 59)
  before data, against a 69 kB PNG for the FAP fit.
- A uPlot figure cannot be a PNG without a browser, so `plot_for_vlm` and
  `path=` need matplotlib. In a committed notebook it would show nothing on
  GitHub, or in Jupyter until the notebook is trusted. `uplot-python` on
  conda-forge is a browser wrapper too. The only matplotlib-free raster route
  is Pillow drawing by hand, a rewrite of `viz/plots.py`'s 1233 lines.
- Asked again for a lighter package, measured on PyPI and in a scratch venv.
  lets-plot 4.11 is the one that writes a PNG with no browser and no system
  library: 6.9 MB wheel, 36 MB installed with Pillow, 1.5 s for a 5751-point
  figure. Against it: the rewrite, two `SyntaxWarning`s and a `Fontconfig
  error` on stderr (the builder refuses stderr), and a 19 MB Kotlin binary
  whose platform coverage was not checked. vl-convert is 29.7 MB; plotly's
  kaleido and bokeh need a browser; cairosvg needs system cairo.
  **The maintainer decided: matplotlib stays.**

**Review.** `/code-review high --fix` on `d4cd2217` found eight. Five fixed in
`2a69fb65`: the box is compared in order (imports aside), output stretches in
order and an uncut panel must end where the output does, the live check
carries the status word and fails on a panel with no codes, and
`_landing_box` names the page when its shape changes. Declined: deriving
`LANDING_TUTORIAL` from the box label (`test_landing.py` names it too, so one
change removes no copy), and `test_landing.py`'s docstring, incomplete rather
than wrong.

**Suite.** Fast selection on the final tree, `[dev]`, macOS arm64, alone on the
machine, `main` not moved since `57aa2c1f`: 8722 passed, 167 skipped, 1 failed
(`toy_anomalous`, bare `main`'s) in 3:48. Total 8889 to 8890, this session's
one added test; it costs under 0.01 s.

**CI's py3.14 failure, after the merge of `main`.** Notebook 03's index cell
wrote `qspace.py:404: RuntimeWarning: invalid value encountered in matmul` to
stderr, with the runner's home path, so the build's guard refused it. An
orthorhombic candidate whose lines leave one axis unconstrained has a zero
A..F term and an infinite variance. `refine_candidate` propagated that as 0·inf
before `cell_from_af` rejected the metric. OpenBLAS raises the flag and
Accelerate does not (a 3×3 product with one inf: 8 NaNs, no warning, on this
Mac). A probe reading the values found 15 such fits in the notebook's search,
every one rejected. Fixed in `refine_candidate` by checking the metric first.
Unit replay (`tests.unit_replay`, corundum and `synthmono_ip`, 15 units): every
digest identical before and after. Indexing core, engines, consensus and
tutorial tests: 175 passed, 1 skipped. Deliberately not generalised: a
*surviving* candidate with a dead cross term still gets NaN for every esd
(triclinic, eleven `h0l`/`0k0` lines: all six), and its fix changes the Bravais
screen's tolerance and the dedup, so it is filed as WP-1915.

**Gotchas.**
- The earlier entry's "`QUOTED` in `tests/test_tutorials.py`" gotcha is now:
  any change to notebook 02's first cell or its output fails
  `test_the_landing_box_is_the_tutorial`. Copy the cell and the output into
  `docs/landing/src/index.html` (wrap at about 56 columns, cut with `…`).
- `build.py` prints `[IPKernelApp] WARNING | Kernel is running over TCP` on
  this machine. That is the kernel's own stderr, not a cell's, and the build
  succeeds.

**Next:** the maintainer's next round, if any. Otherwise close the WP with
the closed entry's narrative and merge #812.

### 2026-10-07 (3rd entry) — paused for /clear; resume here

The maintainer is reviewing the notebooks in rounds and will send more
changes. Everything asked so far is done, pushed and in PR #812, and the fast
suite is green apart from bare `main`'s `toy_anomalous`. The WP is reopened
(🔄) only so the next session finds it in flight. Close it again, with the
same narrative, when the maintainer says the review is over.

**Resume.**
- Worktree `.claude/worktrees/wp1545-tutorial-notebooks`, branch
  `wp1545-tutorial-notebooks`, `[dev]` venv built (carries `notebooks`). From
  the main checkout, `EnterWorktree path:` to it. The branch is up to date with
  `origin/main` as of `5520f4a6`'s merge; `git fetch` and merge before testing.
- PR #812 is ready, not draft, base `main`. Edit its body for each round
  (`gh pr edit 812 --body-file …`); the body keeps a "Review round" section.
- Edit `examples/tutorials/NN_*.py`, never the `.ipynb`. Rebuild with
  `.venv/bin/python examples/tutorials/build.py [NN_slug]` (5 notebooks about
  60 s), then `build.py --check` and `pytest tests/test_tutorials.py`. Read a
  built notebook's outputs with `nbformat` (every text output, and decode each
  `image/png` to look at it); no helper for this is committed.
- Each review round so far: edit, rebuild, read every changed output against
  its prose, commit per change, update the handover entry and the PR body,
  fast suite once at the end (`-m "not slow"`, 3-4 min).

**Waiting on the maintainer.**
- The landing page's code box is labelled `02_simple_rietveld.py` but shows
  `build_report`, `print(report.summary)` and `plot(path="fap_fit.png")`,
  which notebook 02 does not run. Its output panel predates this WP (esd
  0.00010 against today's 0.00008, "4.7 steps … 175 fitted peaks" against
  4.6 and 76). It is public copy: trim the box to the notebook's first cell
  and refresh the panel, or leave it as an excerpt.

**Gotchas for a round.**
- An import added to a notebook goes in its first code cell (ruff E402).
- A new text I/O call in `examples/` names `encoding=` (`test_portability`).
- The first code cell of every notebook must stay the `%pip install` cell
  (`test_a_notebook_opens_by_installing_and_never_ran_it`).
- Notebook 02 must keep printing what the landing page quotes (`QUOTED` in
  `tests/test_tutorials.py`; superseded by the 4th entry, which made the
  whole landing box a test).
- The README must list every notebook; `tests/test_example_projects.py`
  must find each `TUTORIAL_ONLY` file named in some tutorial.

### 2026-10-07 (2nd entry) — the maintainer's review round

The maintainer read the notebooks and asked for nine changes, all made on
this branch. Two reach beyond the notebooks. `pip install rietx` now installs
matplotlib, because every tutorial and the landing page draw figures, and a
base install that could not draw them was the one people met. And a
refinement's history prints as a graph whose straight runs stay in one column,
because indenting every stage put notebook 02's 51 nodes far off the right of
the screen; agents read that same text.

**Done.**
- `HistoryTree.summary` indents a fork, never a step, with a loop for a chain
  (a 1000-node chain no longer recurses 1000 deep). Test pins both halves; the
  quickstart's quoted tree was re-captured from `nac_11bm.py` (same numbers),
  and `using/history.md` describes the new shape.
- matplotlib ≥ 3.10.5 is a dependency: the first release whose wheels cover
  cp314 (3.10.0-3.10.4 have none, measured on PyPI), the rule numba's floor
  follows. `viz = []` stays, as `gui = []` did. The import is still lazy and the
  `--no-deps` guard names matplotlib itself. README, `using/install.md`
  (dependency table, extras table with the missing `notebooks` row),
  `exports.md`, `files.md`, `quickstart.md`, ATTRIBUTION and the staged notes
  follow; the landing page already said `pip install rietx`. Historical WP
  files and `releases/1.6.0.md` keep their `[viz]`.
- `build.py`: a `# %pip …` line becomes a `%pip` magic, and a cell of nothing
  else is never executed. Tested both ways.
- Notebooks: authorship under each title; a version note (1.7 is not on PyPI
  yet, so the GitHub install is given); 01 explains `ftol` and max shift/esd;
  02 reads the history and saves a `.rex` project (one line per entry, what it
  holds); 03's GUI section with the four gestures and a checked link to
  `using/gui-guide.html#peaks`; 05 writes the series as `scan8`-`scan14` with a
  CSV log, shows lexical sort putting `scan10` first, sorts by number, parses a
  temperature from a name, fits the loaded list (identical to the in-memory
  one), and passes `carry=["*"]` with its meaning from `_carry_into`.

**Measured** (macOS arm64, `[dev]`): matplotlib and its dependencies install
to about 58 MB against about 265 MB for the rest of rietx (llvmlite alone is
126 MB). Fast selection on the final tree, alone on the machine: 8721 passed,
167 skipped, 1 failed (`toy_anomalous`, bare `main`'s), in 3:36. The total
moved 8882 → 8889, exactly this round's 7 added cases.

**Next:** as below, plus the same landing-box decision.

### 2026-10-07 — closed

Someone who drives rietx through an agent can now work through five short
notebooks and come away able to check that agent's fit: a Le Bail quickstart, a
staged Rietveld refinement, peaks and indexing, peak shape and microstructure,
and sequential fits. Three of them grade the fit against a synthetic truth the
reader can see. The rest run on the real FAP pattern. Each notebook is generated
from a script, runs in a kernel on every push, and ends with checks drawn from
the agent skill. Building them found one unowned defect (a size read off a
coefficient at its floor, filed as WP-1914) and gave evidence to three open WPs.

**Done.**
- `examples/tutorials/build.py`: percent-format source to executed notebook,
  byte-identical across rebuilds on one machine (cell ids positional, no timing,
  `language_info.version` dropped, `TELEMETRY_ENV` from `_about`). Refuses
  stderr, an error or the home path. `--check` compares cells and the
  major.minor stamp, never outputs.
- `tests/test_tutorials.py`: by glob; executes each notebook; a cell ending on
  `.plot(` must show a PNG; committed cells equal source; committed outputs
  publishable; README lists every notebook; three guard-can-fail tests.
- Notebooks 01-05 and their README rows. 02 replaces `examples/fap_lab.py`
  (decided with the user): its first fit is the landing page's code, the
  landing box is relabelled, `fluorapatite.cif` ships in the wheel, and
  `tests/test_example_projects.py` exempts it from the standards bijection as
  `TUTORIAL_ONLY` (no standard's build reads it) with a test that a tutorial
  does.
- `PeakList.__str__`/`_repr_html_` (notebook 03 needed it; the tree spent 14
  lines a peak). No `FitReport` or `ExtinctionScreen` view: no notebook prints
  one.
- `docs/RELEASING.md` step 1, the root CLAUDE.md sentence, staged notes in
  `docs/releases/1.7.0.md`, narrative in `docs/milestones/v1.7.md`.
- No skill pointer (item 8 says why). WP-1914 filed.
- The skill's `INDEX_PREDICTED_BUT_ABSENT` row said to prefer a smaller cell;
  it now allows a glide or screw axis in a correct one, tagged with this WP's
  aragonite measurement (net zero bytes: the file is over its budget).
- `/code-review high --fix` found seven. Five fixed by the pass: the build
  runs this interpreter's kernel (a user-level `python3` spec can name another
  venv), `parse` refuses an unknown `# %%` marker, a `PeakList` diagnostic
  prints its `where`, `test_tutorials` guards the strings the landing page
  quotes (`QUOTED`), notebook 01 prints `+/-` esds. One fixed by hand:
  notebook 02's tie was compared against a fit from a different start, so it
  now comes before the hold. One declined, for the maintainer: the landing
  page's code box is labelled `02_simple_rietveld.py` but shows lines the
  notebook does not run (`build_report`, `plot(path=)`), and its output panel
  predates this WP (esd 0.00010 against today's 0.00008, "175 fitted peaks"
  against 76). It is public copy.

**Measured** (macOS arm64, `[dev]`, which carries `notebooks`):
- Build wall clock, kernel start included: 01 about 8 s, 01+02 about 12 s,
  03 about 21 s (16-17 s of it the index search), 04 and 05 under 10 s each.
- 01: `auto_background` on FAP Le Bail gives 832 `HIGH_CORRELATION` rows (770
  with limits) against 0 for a 6-term Chebyshev; Le Bail passes 0.0982, 0.0875,
  0.0882, so pass 2 is kept via `checkout(result.node_id)`. `history.best`
  ranks by frozen-compile figures, which differed from a result's own by 11 %
  in χ² on one fit of this pattern, so the notebook ranks results instead.
- 02: `lab_bragg_brentano` from the converged fit puts zero~displacement at
  ρ = +1.000 and the cell esd ×12; zero held at 0 (GSAS's protocol) gives
  displacement 0.0632(15) mm and `HOLD_BLOCKED_PLAN`. The phosphate-O Biso tie,
  refit under the same plan from the first fit, takes 0.264(149), 0.467(157),
  0.385(109) to 0.377(76) Å², 35 to 33 free parameters, Rwp 0.0893 to 0.0894.
  P-O 1.526-1.574 Å.
- 03: aragonite (COD 9000229), orthorhombic only, V 200-250 Å³, d ≤ 8.5 Å: 105
  picks, 59 usable, truth first from all three engines, `low` for
  `predicted_but_absent` and `indexed_fraction_low`, abstains; two builds
  byte-identical. YBCO (COD 9007744) was ruled out: 69-116 s and
  budget-truncated even narrowed. A background agent's survey of aragonite,
  cerussite and forsterite found every glide-extinction phase capped at `low`
  the same way. Le Bail of the candidate: Rwp 0.071 then 0.061, cell within
  1.4 esd of the truth.
- 04: calibration recovers U, V, W, X, Y within about an esd; sample
  298.9(12) Å against 300, 9.65(24)e-4 against 1e-3. Uncalibrated: same Rwp
  0.0464, size 284 Å, strain 1.15e-3, Gaussian size 2186(431) Å.
- 05: expansion 4.998e-6 against 5.000e-6 per K, each point within 1.5 esd;
  a 2 % jump recovered and flagged `SEQUENTIAL_DISCONTINUITY`; a 5 % jump
  fails every rung (`SEQUENTIAL_RWP_OUTLIER`, Rwp 0.97) and its successor is
  reseeded.

- Fast selection on this branch with `main` merged at `57aa2c1f` (1544's
  merge), `[dev]`, macOS arm64, alone on the machine: 8713 passed, 167
  skipped, 2 failed in 4:06. One failure was this branch's: the stale-name
  guard matched an old three-letter token inside base64 figures, fixed by
  skipping `.ipynb` image lines. The other,
  `test_backend_shim[toy_anomalous]` (1.6e-11 off its golden), fails on bare
  `main` too and in 1544's tree; WP-1905's log and #760 own it. Added: 18
  cases in 10 functions, minus `test_examples.py`'s two FAP cases, so +16 by
  count; `main` was not re-measured. `test_tutorial_executes_clean` costs
  65.3 s over 5 cases in one run: 03 at 25.3 s and 02 at 20.7 s are the fast
  tier's 9th and 10th slowest. They stay unmarked because per-push execution
  is the guard's value (`test_examples.py`'s reason), and both sit under the
  tier's 57 s top.

**Gotchas.**
- `fit_peaks` on a whole picked list is no way to edit it: naming 97 of 105
  picks left 27 usable (unnamed neighbours flag their windows) and the index
  took 39 s. Notebook 03 sends editing to the GUI's Peaks panel.
- A rietx figure shows through its own display hook under any backend, so
  `MPLBACKEND=Agg` in the suite does not hide one; a trailing `;` does.
- The 5 % frame converged to Rwp 0.97 and still seeded its successor (which
  was then reseeded). Only a diverged frame is quarantined. Left as is; it is
  `sequential.py`'s design.
- `read_project_model(FAP.EXP)`'s `GSAS_EXP_BACKGROUND_NOT_CARRIED` message
  prints the file's absolute path. Seen, not filed: no owner, and minor.
- `worktree_create.py` run by hand on an existing branch still prints "from
  origin/main".

**Forward references:** 1460 (the tutorials' Chebyshev workaround; rewrite
01's paragraph when it lands), 1542 (the indexer's validation Le Bail at Rwp
0.257 calls 96 of 105 peaks impurities), 1909 (a reproducible synthetic
fixture with 5 false picks in 59).

**Next:** merge #810 (1544) first, then this PR, whose diff shows 1544's
commits until then. Decide the landing page's code box: trim it to notebook
02's first cell and refresh its output panel, or leave it as an excerpt. Then WP-1914, the one defect this found, P3. The tutorials
listed as gaps in the README (backgrounds and humps, Kβ, a second phase, QPA)
are not filed; file them if the notebooks earn readers.

- **2026-10-07** — created alongside WP-1544. No open WP owns tutorials or
  notebooks.
