# WP-1545 — tutorial notebooks

Milestone: unscheduled · Status: 🔄 2026-10-07 — claimed by @yue-here
Track: Render what the fit already knows
Depends on: 1544 (readable objects in a notebook)
Priority: P2 2026-10-07 — was P3: 1544, its one blocker, closed; the teaching path for people who will drive rietx through an agent

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
- [ ] 03 Peaks, indexing, Le Bail.
- [ ] 04 Peak shape and microstructure.
- [ ] 05 Sequential fits.
- [ ] The designed views WP-1544 deferred, built only where a notebook needs
  one (`FitReport`, `ExtinctionScreen`).
- [ ] `docs/RELEASING.md` step and the root CLAUDE.md sentence.
- [ ] Skill: a pointer to the tutorials in `references/`, or "none" and why.

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

- **2026-10-07** — created alongside WP-1544. No open WP owns tutorials or
  notebooks.
