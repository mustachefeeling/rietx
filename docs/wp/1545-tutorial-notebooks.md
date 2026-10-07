# WP-1545 — tutorial notebooks

Milestone: unscheduled · Status: ✅ 2026-10-07 — closed; five notebooks, one session, stacked on 1544's PR
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
126 MB).

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
