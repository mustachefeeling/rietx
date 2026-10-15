# WP-1975 — the manual rebuilt: findings brief

Milestone: unscheduled · Status: 🔄 2026-10-15 — claimed by @yue-here
Track: The repo's own process
Depends on: —
Priority: P2 2026-10-15 — a scoping WP: the maintainer's re-plan of the whole manual starts from this file

## Goal

This file holds the research a re-plan of the whole manual starts from: what the
maintainer asked for, what the repository and its guards are, what Diátaxis, Write the
Docs and the agent-docs practice say, what the chapter audit found, and the decisions
already taken. The re-plan session rewrites this Goal and the Tasks; nothing here is
approved as a design.

## Context

This brief hands one session's research to the next. **Nothing here is approved.** The
maintainer declined two drafts of the plan and will re-plan the whole manual in a new
context, bringing in new concepts of their own. Part D's designs are candidates only.

## A. What the maintainer asked for (original request, paraphrased)

1. **A mental-model part of the manual,** following best practice for software manuals.
   Part 1 ("for humans") is too dense and narrative.
   - *Project structure:* a structured overview graphic (fold, tree, or interactive) with
     minimal narrative, showing the `.rex` project layout and what each file does.
   - *Parameters:* tables of ALL parameters, grouped as a crystallographer expects: cell and
     structure together, microstructure as a group, instrument together. The maintainer
     asked where the background goes, and how it interacts with humps.
   - *Python classes and functions:* an overview grouped by how likely each is to be used.
2. **Tutorial notebooks:** more pedagogical; less python scaffolding, replaced by native
   displays that render well in Jupyter; unroll functions into atomic steps so users see how
   the pieces interact.
3. **FitReport and other feedback text** is extremely dense and "AI"-sounding, and renders
   in huge chunks in the notebooks. Make it concise for humans and agents.
4. Anything related they had not mentioned.

Answers they gave along the way, which the new plan may revisit:
- Diagnostics: split into three fields (observation / action / explanation), with the
  explanation written once per code, rustc-style.
- Background: its own group in the docs, schema paths unchanged.
- Existing chapters: regroup the sidebar now, slim later.
- File WPs for an API reference and a `vars.*` help family too.
- They liked Diátaxis and asked for deeper research (section C).
- They chose all four additions to the mental-model section: a life-of-a-fit page, a
  scope column, GSAS-II/TOPAS/FullProf names, and measured usage tiers plus a newcomer
  check.

## B. Facts about the repo (verified 2026-10-15, `main` at 54526f8, version 1.10.0.dev0)

### B1. Manual structure and its guards
- **Root and toctree.** `docs/manual/manual.md` is `root_doc`. Part 1 is one toctree at
  lines 102-131 (caption "Part 1: Using rietx"), with order prose at 92-100. Part 2
  (Theory) is a numbered toctree at 186-205.
  - Nothing parses the Part 1 toctree. `tests/test_landing.py:520` regex-reads the
    tutorials' hidden toctree in `using/quickstart.md:37-46`.
- **Part 1 size:** 25 chapters, 15 885 lines. The largest: `files.md` 1988, `series.md`
  1832, `refining.md` 1521, `data.md` 1412, `indexing.md` 1315, `results.md` 1012.
- **`conf.py` set-up.**
  - Extensions: `myst_nb` (notebooks rendered, `nb_execution_mode="off"`), `sphinx_design`
    (only an install tab-set is used today), `sphinxcontrib.bibtex`, `sphinxcontrib.mermaid`
    (client-side, light/dark at 100-107).
  - MyST extensions: dollarmath, amsmath, substitution, colon_fence, deflist.
  - Theme furo plus `_static/custom.css`. The "agent" admonition is a CSS class (9-27);
    `.using-figure` at 194 is defined but unused.
  - No autodoc or autosummary, so there is no API reference at all.
- **Generated content** goes to `docs/manual/_generated/` (gitignored, outside `using/`):
  - the glossary from `rietx.help.help_registry()` (`conf.py:304-411`, `_ARMS` list,
    `_definition`/`_detail`; parameters are one flat definition list);
  - the skill body and references, through `_write_skill()` (`conf.py:507-548`);
  - the tutorial notebooks, copied in at `conf.py:427-456`.
- **Figures** are committed light/dark PNG pairs from `docs/manual/make_figures.py`, each
  included as two `{image}` directives with `:class: only-light` / `only-dark`. GUI
  screenshots come from `make_screenshots.py`.
- **`tests/test_manual_api.py`** (Part 1; scans `using/*.md` by rglob):
  - dotted names in code spans and python fences must resolve, and the qualified
    `Class.member` form marks a name documented;
  - `rx.X` must be in `__all__` (`rx.help.`/`rx.viz.` fail; write `rietx.help.…`);
  - any `phases.`/`instrument.` token in a code span must fnmatch a path in five
    representative ParameterTables (extra-peak `center/area/eta`, `background.scale/air`,
    `texture.*` and rigid-body paths do NOT resolve there);
  - python fences execute standalone, or carry
    `<!-- api-doc: no-exec — reason of 3+ words -->` on the line before;
  - the derived API surface (`tests/api_surface.py`) must be partitioned into documented /
    excluded / deferred (`tests/api_surface_deferred.txt`, 39 names; a name both documented
    and deferred fails).
- **`tests/test_manual.py`:**
  - `sphinx -W` builds clean;
  - no unrendered `$`, backtick or `{{` in the HTML;
  - every bib entry is cited and every citation has an entry;
  - **register guard `test_the_manual_keeps_its_register` (773): no em dash and no bold
    `**` in prose.** Admonitions are not exempt; code, fences, HTML comments and directive
    options are.
- **`tests/test_gui_manual.py`:** exactly three pages named `gui-*.md`; routes and panels
  are partitioned.
- **Root `CLAUDE.md` is at 982 of its 983-line cap** (`test_docs_consistency.py:456`).
- The manual's own rules live in `manual.md:50-90`: CapWords versus lower case, a method
  written under its defining class, dot-paths never capitalised.

### B2. Parameters (`src/rietx/help.py`, the authority for "what a name is")
- **`HelpEntry`** has fields title, description, unit, default, typical, anchor and label.
  `PARAMETER_HELP` (233-1271) holds 82 globs over 69 distinct entries; shared entries are
  `_CELL_LENGTH`, `_CELL_ANGLE`, `_ATOM_COORD`, `_ATOM_ANISO_U`, `_STEPHENS_S` and
  `_BODY_ORIGIN`.
- **Grouping today:** only two comment banners, so nothing is grouped.
  `help_registry()` (2314) feeds the GUI `/api/help`, `tests/test_gui_help.py`,
  `gui/src/lib/help.ts` ARMS and the `conf.py` arm check. Changing its shape costs a GUI
  rebuild.
- **The globs**, grouped as candidate groups:
  - instrument: `zero_shift`, `polarization`, `source.lines.*.wavelength` and `.weight`,
    `profile.u/v/w/x/y`, `geometry.axial_sl/hl`;
  - specimen: `geometry.sample_displacement`, `sample_transparency`, both capillary
    offsets, `surface_roughness.a/b/c/tau`;
  - TOF: `source.difc/difa/tzero/difb`, `source.profile_tof.*` (10),
    `source.incident_spectrum.p*`;
  - background: `background.c*/scale/air`, `extra_components.*.position/height/fwhm`
    (hump) and `center/area/eta` (declared peak);
  - phase: `cell.a–gamma`, `scale`, `extinction`, lor/gauss size and strain, magnetic lor
    size and strain, `preferred_orientation.r`, `texture.*`;
  - atoms: x, y, z, `dof.*`, `occ`, `biso`, u11–u23, `adp.*`, `moment.crystalaxis_*`,
    `moment.dof*`;
  - rigid bodies: origin, `origin.dof.*`, `rotation.*`, `torsions.*.twist`;
  - microstrain: `s*`, `dof.*`.
- **Gaps.** `vars.*` (user variables) has no help family; adding one touches GUI
  `history.ts` PLACES, npm and the dist. Absorption (`mu_r`, `mu_t`) is not refinable and
  is described in `INSTRUMENT_FIELD_HELP`.
- **Background in the schema:**
  - `Instrument.background` is a `BackgroundChebyshev | BackgroundFixedPlusChebyshev |
    BackgroundPSpline` (`schemas/instrument.py:1516/1534/1604/1733`).
  - `Instrument.extra_components: list[HumpComponent | PeakComponent]` (1828, 1981, 2229,
    2271). An "expression" member is admissible by contract but not implemented.
  - Extra components are deliberately NOT nested under the background: every preset's first
    stage frees `instrument.background.*`, and fnmatch `*` crosses dots (2264-2270).
  - Humps join the background curve (`y_background`); declared peaks join ticks under
    `"(extra)"` (`model/components.py:51-73`, `COMPONENT_AGGREGATE`, `EXTRA_TICK_KEY`).
  - Only `mccusker_structural` has an `extra_components` stage (`strategy/staged.py:241`).
  - Docs: humps at `docs/manual/background.md:131-177` (Part 2) and `data.md:1160-1379`;
    peaks at `model.md:349-519`.
- **Existing parameter table:** `using/concepts.md:15-33` (by angular signature). Its plan
  mermaid at 461-474 **has drifted**: it omits the `extra_components` stage, which
  `mccusker_structural` inserts sixth of eleven.
- **Foreign names:** no central rietx↔GSAS-II/TOPAS/FullProf map exists. The vocabularies
  are spread through the readers:
  - `io/projects/gsas2.py`: `SAMPLE_PARAMETERS` 1028, `INSTPRM_*` 2247-2252;
  - `topas.py`: `_KEYWORDS_READ` 1209, `_CELL_KEYS` 2741, `_ADP_KEYS` 1909;
  - `fullprof.py`;
  - `io/projects/coverage.py`: TOPAS construct stances.

### B3. The `.rex` project (from code; no example `.rex` ships)
```
<name>.rex/
  project.json      ProjectDoc settings (plan, mode, two_theta_limits, excluded_regions, indexing, ui, DataRef…)
  <pattern file>    copied byte for byte; sha256 + parsed fingerprint checked on open
  history.jsonl     RefinementTree (header/node/annotation); the only copy of model state; Project.open appends
  peaks.json        GUI peak list (optional)
  live/<YYYYMMDD-HHMMSS-pid>/  events.jsonl meta.json status.json run.lock snapshot.json summary.txt cancel (fit.html legacy)
  live/events.jsonl GUI index/extinction runs (optional)
  exports/          refinement.cif reflections.csv qpa.csv fit.html result.json instrument_profile.json
outside: <cwd>/.rietx/runs/{.gitignore,<run id>/}; $HOME/.rietx/{recent.json,settings.json,examples/<name>.rex}
never stored: the .rxt view, CIFs (structure lives in history nodes), the parsed PatternData
```
- **Writer constants**, which a test can cross:
  - `project.PROJECT_JSON` / `HISTORY_FILE` / `LIVE_DIR` / `EXPORTS_DIR` (63-66);
  - `gui.peaks.PEAKS_FILE`;
  - `gui.session.EXPORT_DEFAULTS` (135);
  - `runs.*_FILE` (92-172) and `runs.RUN_ID_RE` (207);
  - `_about.PROJECT_SUFFIX` / `STATE_DIR_NAME` / `RUNS_DIR_NAME`.
- `rietx.examples.build_example(name, into)` (`examples.py:117`) builds `fap` or `nac`.
- The current docs: `files.md:6-31` (mermaid in/out map) and `1645-1817` (text tree at
  1650-1659), with run directories at 1819.

### B4. API surface
- `rietx.__all__` holds 115 explicit names plus every schema class. `structure_from_cif` is
  not top-level; use `rx.Structure.from_cif`.
- **Main calls:**
  - reading and models: `read_pattern`, the `Instrument` presets (`bragg_brentano`,
    `debye_scherrer`, `flat_plate_transmission`, `constant_wavelength_neutron`,
    `tof_neutron_bank`);
  - fitting: `Refinement` (`fit` 4289, `parameters` 2388, `set_vary`, `set_values`,
    `hold`/`unhold`, `tie`/`tie_equal`/`untie`, `add_variable`, `edit`, `run_stage` 5013,
    `predict` 5197, `suggest`, `checkout` 2131, `branch`, `history` (attr), `summary` 5295,
    `report` 5258, `write_cif`, `fitted_structure`) and the one-shot `rx.refine`;
  - plans: `PLAN_PRESETS`/`PLAN_INFO` (8 presets), `Stage`/`RefinementPlan`;
  - reports and helpers: `build_report`, `auto_background`, `diagnose`, `format_su`,
    `capabilities`, `help_for`;
  - projects and series: `Project.create/open/save/fit`, `refine_sequential`,
    `refine_multi`;
  - provisional: `pick_peaks`, `fit_peaks`, `index_pattern`.
- **The agent-facing grouped index is generated:** `docs/skill/rietx/references/api.md`,
  by `docs/skill/make_api_index.py` (SECTIONS at 83), pinned by `tests/test_skill.py`.

### B5. Tutorials (`examples/tutorials/`)
- Six `NN_*.py` scripts in percent format (01 quickstart Le Bail, 02 Rietveld, 03 peaks and
  indexing, 04 microstructure, 05 sequential, 06 template). `build.py` generates the
  executed `.ipynb`; `tests/test_tutorials.py` executes them and checks cells equal to the
  sources.
- **The landing page's code box and output panel are pinned to notebook 02's first cell**
  (`test_tutorials.py:108-136`).
- WP-1545 created them (PR yue-here/rietx#812, merged 2026-10-07), and its status is still
  🔄, which is stale.
- **Scaffolding found**, the kind native views could replace:
  - 01: the four `diagnose` f-string prints, the pass loop and a hand-formatted cell;
  - 02: about five print loops over params, diagnostics, stages and bonds, plus a
    `d.message.split(' — ')[0]` hack;
  - 03: a raw tuple print;
  - 04: `show_microstructure`;
  - 05: trajectory loops;
  - 01: a manual background seed, `coefficients[0].value = percentile`.
- **Views today** (`_display.py`: text is the authority, HTML a projection; a display reads
  fields and never computes):
  - designed views and/or HTML: `RefinementResult` (pre + table), `Refinement`,
    `PeakList`, `IndexingResult`, `ParameterRow` (one line), `RefinementTree`,
    `PatternData`;
  - generic tree only: `FitReport`, `Diagnostic`, `StageResult`, `PhaseMicrostructure`,
    `Trajectory`, `CellCandidate`, `GeometryTable`, `RefinedParameter`;
  - `Refinement.parameters()` returns a plain list.

### B6. Report and diagnostic text
- `Diagnostic(level, code, message, where, suggestion, value)` is at
  `schemas/common.py:907`. There are **271 distinct codes across 41 files** (`refine.py` 65
  sites, `indexing/diagnostics.py` 39, `sequential.py` 19…). A message plus its suggestion
  usually runs 250-1100 chars on one line.
- **Three line formats coexist:** results `    LEVEL CODE: msg — suggestion`
  (`schemas/results.py:1249 _diagnostic_lines`), indexing `  [warning] CODE: msg`, and
  peak-list `at:`.
- **`FitReport` has no text view.** `FitReport.summary` is a `;`-joined string
  (`report/layer0.py:242`, `report/__init__.py:285-442`). `Refinement.summary()` is built in
  `refine.py:5295-5553`. The Layer 1 abstention reason prints twice.
- **Pins that constrain a rewrite:**
  - `test_capabilities.py:597-626` (str(GuardFinding) byte for byte);
  - `test_bound_hit_at_convergence.py`, `test_high_correlation_dedup.py` (exact messages);
  - `tests/data/nac_termination_golden.txt` (slow; digits masked);
  - `test_termination_view.py` (shape);
  - `test_display.py`;
  - `test_joint_report.py:249` (summary.txt == str(result));
  - ~15 `report.summary` substring checks.
- The skill's `references/diagnostics*.md` holds one row per code, agent-facing.

### B7. Related open WPs, and process
- **Related open WPs:**
  - 1443 "Part 1 read by a newcomer" (⬜ P3; 11 passages from issues #395-#407);
  - 1133 "A diagnostic names the view that shows it";
  - 1421, 1335 (report cost);
  - 1970 (a notebook figure follows the theme; figures stored twice);
  - 1909/1910/1542 (indexing hazards the tutorials hit).
- **Next free WP numbers:** 1975 onward, in the unscheduled block. The ROADMAP tracks that
  fit: "#### The repo's own process" (516) and "#### Render what the fit already knows"
  (491).
- **Process:**
  - WP files come from `docs/wp/TEMPLATE.md`; the index is generated by
    `python3 .claude/hooks/wp_index.py`;
  - commits are prefixed `WP-NNNN:`; one WP per session; end with `/wp-handover`;
  - edits only in a worktree (`.claude/hooks/worktree_only.py`; `EnterWorktree`), and no
    bare `cd` in Bash (`no_top_level_cd.py`);
  - the designated push branch is `claude/loving-mccarthy-416vvl`.
- The release notes in flight are `docs/releases/1.10.0.md` and `docs/milestones/v1.10.md`.

## C. Research

### C1. Diátaxis, read from its source
The source was cloned to
`/tmp/claude-0/-home-user-rietx/cb8148e8-7ef8-59e5-99f7-a020002c0483/scratchpad/diataxis-src/source/`,
dated 2026-08-06; diataxis.fr itself is blocked by the proxy. The key pages are
`how-to-use-diataxis.rst`, `map.rst`, `compass.rst`, `reference.rst`, `explanation.rst`,
`how-to-guides.rst`, `tutorials.rst`, `tutorials-how-to.rst` and
`reference-explanation.rst`.
- **The compass.**

  | | acquisition (study) | application (work) |
  |---|---|---|
  | informs action | tutorial | how-to |
  | informs cognition | explanation | reference |

  The answers to "Can you teach me to…? / How do I…? / What is…? / Why…?".
  The most common failure is blur between neighbours.
- **Reference:** "Describe and only describe"; austere; "the structure of the documentation
  should mirror the structure of the product". Link to explanation and how-to, never
  include them. Auto-generation keeps reference accurate (but is not all you need). Lists
  and tables belong here. Examples are fine.
- **Explanation:** a discursive "Can you tell me about…?", readable away from the product.
  Titles take an implicit "About…". It holds context, why, design decisions, history,
  alternatives, even opinion. "Keep explanation closely bounded": it absorbs instruction and
  description.
- **Tutorials:** a lesson; what matters is what the learner does. "Ruthlessly minimise
  explanation", and link to it instead. Results early and often; repeatable; concrete, not
  abstract.
- **How-to guides:** from the user's goal, not the machinery; "How to …" titles; omit the
  unnecessary; adaptable to the real world. "A rich list of how-to guides is an
  encouragement" and shows what the product can do.
- **Workflow:** "a guide, not a plan"; "Don't worry about structure"; never create empty
  quadrant sections ("Don't do that. It's horrible."). The cycle is choose something
  small → assess it with the compass → decide the single next action → do it and commit.
  Structure emerges "from the inside", the docs "complete, not finished".

### C2. Diátaxis audit of Part 1 (section by section, every chapter read)
- **Shares by type:** reference-dominant chapters hold 86 % of lines (13 689), each with
  35-55 % non-reference content. Explanation is ~7.5 %, tutorial ~4 %, **how-to ~2 %
  (effectively absent)**.
- **The density drivers:**
  - measurement diaries: 196 "measured" lines, e.g. `refining.md:837` "venv,
    darwin/arm64, 2026-08-22, best of three", `data.md:1089`;
  - development history: WP and issue numbers, "until v1.4", "before 1.8", "schema 0.17";
  - maintainer rationale: `report.md:820`, `files.md:943`, which cites CLAUDE.md;
  - the rendered skill page adds 117 "WP-" and 244 "measured".
- **The same explanation repeated:** background bias 4× (`data.md:1050`, `report.md:349`,
  `results.md:753`, `gui-guide.md:483`); the instrument ⊕ sample split 5×; "corrections
  cannot move Rwp" 3×; "no read-only open" 3×; the λ–cell degeneracy 3×.
- **Misplacements:**
  - the tie, variable, hold and restraint verb reference sits in `concepts.md`
    (explanation), and `constraints.md` calls it "the reference";
  - 37 % of `refining.md` is magnetic;
  - `series.md` holds three topics: chain, joint and parametric.
- **Stale or contradictory statements:**
  - `compatibility.md:172` contradicts `files.md:822` on formats and writers;
  - `files.md:1710` and `compatibility.md:5` mention the agent envelope, retired in 1.3;
  - `recipe.md:172` contradicts `results.md:218` on the cell-volume esd;
  - `files.md:609` uses an undefined `ref`;
  - `gui-quickstart.md:225` calls quickstart.md a script.
- **Tutorials:**
  - Notebooks 01-05 are true tutorials, but over-explained: 01's summary legend, 04 opens
    with equations, 02 covers ten topics, 05 detours into file sorting.
  - Each ends with a how-to checklist aimed at people supervising an agent.
  - `first-refinement.md` is 55 % non-tutorial, and its first fit cannot run from shipped
    files (line 62).
  - `gui-quickstart.md` is the cleanest tutorial; `gui-power.md` and `glossary.md` are the
    cleanest reference.
- **Per chapter** (dominant type / mixing % / proposed split):

  | Chapter | Type | Mixing | Proposed split |
  |---|---|---|---|
  | install | how-to | 45 % | how-to + reference + explanation (kernels) |
  | first-refinement | tutorial | 55 % | tutorial + "why Le Bail first" + how-to (no structure / no cell) |
  | data | reference | 55 % | reference tables + explanation (λ–cell, neutron, background bias) + how-tos (blank, hump, calibrate) + validation |
  | model | reference | 45 % | reference + how-tos (holder peak, interval) |
  | concepts | explanation | 60 % | explanation (correlation, staging) + verb reference + how-tos |
  | refining | reference | 50 % | how-tos (run, stage, stop, watch) + reference + a magnetic chapter |
  | results | reference | 45 % | reference + explanation (R-factors, observations, esds) + how-to (check data first) |
  | report | reference | 40 % | reference + explanation (layers, abstention) + how-tos |
  | history | reference | 35 % | reference + how-to (tag, checkout, branch, replay) |
  | files | reference | 35 % | per-format reference + how-tos (open/export TOPAS, FullProf, GSAS-II; instrument profile) |
  | indexing | reference | 45 % | how-to "index end to end" (missing) + reference + explanation |
  | series | reference | 55 % | three chapters, each split by type |
  | qpa | explanation | 55 % | explanation + reference + how-tos |
  | exports | reference | 35 % | tables + how-tos (plot, figure, write CIF) |
  | recipe | reference | 45 % | how-to + reference |
  | cli | reference | 35 % | reference + how-tos (watch, stop) |
  | gui-quickstart | tutorial | 25 % | keep |
  | gui-guide | reference | 45 % | reference + explanation (when to branch) |
  | gui-power | reference | 15 % | keep |
  | agents | reference | 45 % | reference + how-to (wrap in a tool) |
  | compatibility | explanation | 50 % | policy explanation + version reference |
  | glossary | reference | 15 % | keep |

- **The 25 most-needed how-tos and where they live now:**
  1. hold a parameter through a plan (`concepts.md:289`);
  2. tie parameters (`concepts.md:121`);
  3. restrain a distance and relax it (`concepts.md:381`, `500`);
  4. edit a plan or add a stage (`concepts.md:483`);
  5. run one stage at a time (`refining.md:1017`);
  6. limit the range or exclude a region (scattered; `data.md:160`);
  7. add a hump (`data.md:1357`);
  8. use a measured blank (`data.md:1056`);
  9. declare a holder line (`model.md:349`);
  10. calibrate on LaB₆ and reuse it (`data.md:1381`, `files.md:601`, notebook 04);
  11. quote a cell with its esd (no single recipe);
  12. get an interval on a bound (`model.md:620`);
  13. choose the next parameter (`report.md:536`);
  14. fit a temperature series (`series.md:28`);
  15. check path dependence (`series.md:631`);
  16. fit a(T) as an equation (`series.md:1302`);
  17. a joint X-ray plus neutron fit, or refine λ (`series.md:847`);
  18. index end to end (only skill §7d);
  19. export a CIF or reflections (prose only);
  20. QPA, microabsorption, a trace phase (`qpa.md`);
  21. branch, compare, roll back (`history.md:340`);
  22. open or write TOPAS, FullProf or GSAS-II (`files.md:830`, `878`);
  23. watch or stop a fit, telemetry off (`cli.md:118`, `refining.md:1283`);
  24. magnetic moment or structure (`refining.md:302`, `609`);
  25. check a pattern before fitting (`data.md:199`).

### C3. Other precedents (web)
- **GSAS-II** scopes parameters three ways: Phase `p::` (cell, atoms); Histogram `:h:`
  (Sample DisplaceX/Y, Shift, Transparency, Absorption; Background; Instrument Lam, Zero,
  Polariz., U V W X Y SH/L); Histogram-and-Phase `p:h:` (Scale, Size, Mustrain, PO).
  Unconfirmed, from memory: background peaks live inside Background (BkPk*).
  https://gsas-ii-scripting.readthedocs.io/en/latest/objvarorg.html
- **rustc:** the headline is short and lowercase; errors never suggest a fix, which goes in
  a separate `help`; `note` adds context; each code has a long-form explanation (with an
  example and a fix) in an error index generated from source and reached by `--explain`.
  RFC 1644 is the lighter default format.
  https://rustc-dev-guide.rust-lang.org/diagnostics ,
  https://rust-lang.github.io/rfcs/1644-default-and-expanded-rustc-errors.html
- **Elm, "Compiler Errors for Humans":** show the user's own code and values; give
  specific hints; let user reports drive improvements. Rust internals readers found Elm too
  wordy and preferred concise text with detail on request.
  https://elm-lang.org/news/compiler-errors-for-humans
- **Barik et al. 2018** (ESEC/FSE, "How should compilers explain problems to developers?"):
  developers prefer a proper argument structure, but accept a weaker one when a fix is
  offered.
  https://www.microsoft.com/en-us/research/publication/how-should-compilers-explain-problems-to-developers/
- **xarray HTML repr:** text and HTML show the same sections; long sections are collapsed;
  empty ones hidden. https://github.com/pydata/xarray/pull/10785
- **Cargo "Package Layout"** and the **Django tutorial part 1** both show the project tree
  with one line per entry, which is the precedent for the project-layout page.
  https://doc.rust-lang.org/stable/cargo/guide/project-layout.html ,
  https://docs.djangoproject.com/en/5.2/intro/tutorial01
- **The worked-example effect and fading:** full worked examples, then faded steps the
  learner completes, help novices; the expertise-reversal effect is that they slow experts.
  https://en.wikipedia.org/wiki/Worked-example_effect

### C4. A unifying principle that emerged
**The headline stays in view and the evidence sits a fold away.** It applies to every
surface:
- a diagnostic shows its message and suggestion, with the detail and `explain()` folded;
- a manual page shows its statement, with measurements and history in a folded evidence
  box or a link to the WP or validation record;
- a notebook shows the step, with a link to the explanation;
- an HTML repr shows its sections, with long ones collapsed.

## D. Candidate designs from this session (not approved; reuse or discard)

1. **Parameter groups as data in `help.py`.**
   - A `ParameterGroup(key, title, effect, scope, families)` and a constant
     `PARAMETER_GROUPS`, outside `help_registry()` so the GUI is untouched.
   - Nine groups:
     - structure (cell and atoms);
     - phase in pattern (scale, PO/texture, extinction);
     - microstructure;
     - instrument (zero, λ and line weights, polarization, UVWXY, axial);
     - specimen (displacement, transparency, capillary offsets, roughness);
     - background and non-Bragg signal (background coefficients, humps, declared peaks);
     - magnetic;
     - rigid bodies;
     - TOF.
   - Meta-tests: a bijection with `PARAMETER_HELP`; a shared entry stays in one group; the
     register holds; the scope agrees with the path root.
   - Optional: `FOREIGN_NAMES` (GSAS-II/TOPAS/FullProf, each checked against its reader's
     keyword constants).
2. **Generated pages from `conf.py`:**
   - `_generated/parameter-map.md`: one list-table per group, with Path | Name | Scope |
     Elsewhere | Unit | Default | Typical;
   - a glossary sectioned by group;
   - `_generated/plan-ladder.md`, generated from `PLAN_PRESETS` (glob instance `*`→`0`,
     `fnmatchcase` against `turn_on`), replacing the drifted mermaid.
3. **A folding tree.**
   - A local extension `docs/manual/_ext/rietx_filetree.py`: a ```` ```{filetree} ```` with
     indented `name | description`, `/` for a directory, `?` for optional, `<…>` for a
     placeholder.
   - It renders nested `<details open>`, the name as a literal, the description through
     `state.inline_text`, and CSS with furo variables.
   - `tests/test_manual_layout.py` crosses the tree with `build_example("fap", tmp)` on
     disk and with the writer constants in B3.
4. **Candidate pages:**
   - explanation: "About how rietx is organised" (an object-flow mermaid plus an object
     table) and "About the life of a fit" (the plan → stage → compile → solve → node loop;
     six parameter states; Le Bail/Rietveld/Pawley; the order to judge a result);
   - reference: "The project folder", "Every parameter, grouped" and "Objects and calls at
     a glance", whose tiers come from an AST census of usage across `examples/`, the
     tutorials and the skill.
   - Acceptance: a newcomer check, in which a fresh agent limited to those pages answers
     about 8 questions.
5. **Sidebar captions** (without empty Diátaxis quadrants): Start here / How rietx is
   organised / Doing a refinement / Special jobs / GUI / Programs and agents / Reference.
6. **WP slate drafted** (numbers 1975-1981):
   - 1975, the mental-model section;
   - 1976, diagnostics one line plus a fold (the rustc model: message/suggestion/detail,
     plus a per-code `DIAGNOSTIC_HELP` arm → `explain()`, GUI popovers and a generated
     diagnostic index; one renderer; info rows folded; xarray-style HTML; a
     `FitReport.__str__`; a length ratchet; the NAC golden regenerated);
   - 1977, tutorials through native views (explanation cut to links; "predict, then run";
     `run_stage` unrolled; views for the parameter list, `RefinedParameter`, `StageResult`,
     microstructure, candidate and bonds; notebook 02 split; landing panel rebuilt);
   - 1978, Part 1 slimmed with the Diátaxis cycle (evidence folds, type splits, merged
     repeats, a size ratchet, no WP numbers in prose);
   - 1979, the how-to guides from the 25-task list;
   - 1980, an autodoc API reference;
   - 1981, a `vars.*` help family.

## F. Second investigation (2026-10-15, later): guides, agents, navigation, the switching reader

The maintainer's standing positions, taken as given for the re-plan:
- Keep Part 2's literature links, equations and `*Source:*` lines. (Mechanism: `{cite}` into
  `references.bib`, constants injected from the live package as MyST substitutions, every
  displayed equation carries a `*Source:*` symbol that must import, guarded by
  `tests/test_manual.py`.)
- Adopt the Diátaxis taxonomy and label every page with its type; today the types are mixed.
- Do NOT make the four types the only top-level tabs; prioritise by frequency of need.
- Readable by humans and easy for agents, both.
- Sunk cost disregarded; a rebuild from scratch is on the table.
- Keep the at-a-glance tables; one key audience is users of other codes deciding whether to switch.

### F1. Write the Docs guide (source cloned from writethedocs/www, `docs/guide/`, 33 pages)
The site is DNS-blocked here; the source is at
`/tmp/claude-0/-home-user-rietx/cb8148e8-7ef8-59e5-99f7-a020002c0483/scratchpad/wtd/docs/guide/`.
- **Documentation principles** (`writing/docs-principles.rst`), the useful page. Content should be:
  - *ARID* (accept some repetition; "the best documentation is hand-written");
  - *Skimmable* ("write like a newspaper instead of a novel": descriptive headings, links that
    name their target, paragraphs that open on the concept);
  - *Exemplary* (examples for the common cases; "separate examples and tutorials from more
    dense reference information to further help readers skim");
  - *Consistent*; *Current* ("incorrect documentation is worse than missing documentation";
    write version-agnostic text).
  - Sources *Nearby* (beside the code) and *Unique* (no overlap between sources: "prevent
    parallel maintenance of the same information").
  - Publications *Discoverable*, *Addressable* (deep links), *Cumulative* (prerequisites first;
    tutorials before reference), *Complete* ("cover concepts in full, or not at all": a map of
    50 of 100 hydrants is worse than none), *Beautiful*. The body *Comprehensive* (answers the
    likely questions).
- **Beginners' guide**: state what problem the project solves, a small code example, install
  in a couple of lines, support, contribute, licence; beware FAQs.
- **Docs as code**: issue tracker, VCS, plain-text markup, review, automated tests (the repo
  already does all five).
- **Testing**: build clean, link check, prose lint (Vale with the Google/Microsoft packages).
- **Style guides**: pick a public one (Google developer docs, Microsoft) and a terminology list;
  "documentation changes are cheap, code changes are expensive".
- Rules the repo breaks today: *Unique* (five repeated explanations, C2), *Current* (five stale
  statements, C2), *Skimmable* (measurement diaries inside reference), *Cumulative* partly.

### F2. beautiful-docs (matheusfelipeog)
A list, not a method. Its "Writing about docs" links are Diátaxis, Write the Docs, Jacobian's
"Writing great documentation", the Google developer style guide, TomDoc, API Blueprint. Of its
~60 exemplars the relevant shapes are:
- **Django** (Diátaxis's origin): a front page of "First steps" then *thematic* sections, with
  "How the documentation is organized" naming the four types as a second axis (verified from
  `django/docs/index.txt`).
- **xarray**: four cards (Get started / User guide / API reference / Contribute) and a hidden
  toctree Get Started, User Guide, Tutorial, Gallery, API Reference, Get Help, Development,
  Release Notes (verified from `doc/index.rst`). This is the scientific-Python norm.
- **FastAPI**: tutorial-first, then advanced, deployment, how-to, reference, about; the
  tutorial is the spine.
- **Rust book**: a narrative order with a tutorial second ("Guessing game") and reference in
  appendices.
- **Stripe, PostgreSQL, Redis commands**: reference as the product.
- **GSAS-II** by contrast documents only its modules; user docs are tutorials on a separate
  site (verified from `GSAS-II/docs/source/index.rst`). There is no Rietveld code with a
  Diátaxis-shaped manual to copy from.

### F3. How much agents read our docs (repo's own record; the Explore sweep)
**The project has never measured an agent reading the hosted manual.** Every traced run used
the skill, docstrings, `inspect.signature` and installed source.
- The one unaided agent on a 68-pattern series fetched 5 doc pages (one 404), then "gave up on
  docs" and used `inspect`/`dir()`: verdict "docs for orientation, source for the API"
  (`docs/wp/1110-agent-surface-friction.md:23-46`, 2026-08-20).
- 235 traced interpreter starts: `tool_definition`/`request_schema` called 0 times; the JSON
  surface was deleted on that evidence (WP-1303).
- An 86-run contributor campaign, 5 430 tool calls: 2 reads of the 147 kB protocol (both by
  agents editing it), 40 reads of `CLAUDE.md`, 0 of `help_for`/`capabilities()`
  (`docs/wp/1304-protocol-as-skill.md:17-40`).
- Skill placement round (18 cells): every cell loaded the skill body; no Haiku/Sonnet cell
  opened a reference file; Opus under `grep` reached 17/54 rows vs 4/54 by reading
  (`tests/eval_skill_placement/PROTOCOL.md:174-213`).
- WP-1504 round E: skill invoked 42/42 when fixed, tasks done 40/42 vs 25/42; **web tools
  were disallowed**, so the manual was never on offer.
- Cost: the skill body adds ~9 500 tokens to a session; body + api + judging ≈ 30 k tokens
  before the first fit; Claude Code keeps only the first 5 000 tokens of a skill after
  compaction (`docs/wp/1904:53-79`). Part 1 is ~139 k words raw.
- GitHub issues: 243 of 274 carry an agent signature; all 17 that cite the manual cite the
  repo path `docs/manual/...`, none rietx.org. Only the human newcomer (#395-#407) read the
  hosted site.
- `llms.txt` was set aside on outside data: Ahrefs found 97 % of published files get zero
  requests (1304:55-57).
- Stated position: "Part 1 is written for a person"; agents read the skill first and return
  for the object model (`manual.md:39-48`); rules for agents go in the skill, cheapest place
  first (`CONTRIBUTING.md:67-100`).
- Mechanisms for agents today: the skill (SKILL.md 17.9 kB + 18 references, 442 kB tree;
  caps in `tests/skill_caps.py`: body 17 000 B = the agentskills.io 5 000-token budget, each
  reference ≤ 36.6 kB because Bash output over 40 kB is cut), `capabilities()`, `help_for`
  (anchors `page.html#id`), 19 `agent` admonitions in 14 files, four registered agent evals
  (`tests/eval_*`), the skill copied verbatim to `rietx.org/skill/rietx/`.
- Gaps: no eval with the manual available; no `llms.txt`, sitemap or deliberate markdown
  mirror (Sphinx's default `html_copy_source=True` probably publishes `_sources/*.md.txt`
  unintentionally; unverified, rietx.org is blocked here); no traffic data at all.

**Reading:** the agent audience is real and dominant (243 of 274 issues), but it is served by
the *skill*, not the manual, and by *code* (source, signatures) not prose. Under the n8n/WTD
rules below, the manual's job for an agent is orientation and the object model, reached by
grep and deep link, in self-contained sections. The one thing never measured is whether a
manual built that way would be read; an eval that allows the manual is the missing experiment.

### F4. Current practice for docs read by humans and agents
Sources that resolved: the llms.txt proposal (AnswerDotAI, source), n8n's agent-friendly
docs contribution guide, the llms-txt hub, Fern/Mintlify "agent score" reports, Diátaxis.
Blocked: agentdocsspec.com, jamdesk, vercel, logrocket, pingidentity.
- **The llms.txt format** (spec): one H1, a blockquote summary, prose, then H2 sections of
  `name`, link and note triples, and an `## Optional` section an agent may skip; markdown twins of
  pages at `page.html.md`, discoverable by `<link rel="alternate" type="text/markdown">`.
  Adopters: OpenAI, Anthropic, Google, FastHTML, Mintlify, GitBook; Chrome Lighthouse audits it.
  Guidance converges on a *curated* 20-50 links, never a sitemap dump; stale is worse than none.
- **n8n's rules** (the most concrete, and they serve both audiences): publish every page as
  clean markdown; one term per concept site-wide; stable URLs with redirects; scope version
  facts to where they apply; keep pages focused, neither tiny (merged with unrelated chunks)
  nor huge; **make each section self-contained** (no "as mentioned above": agents get a
  chunk); **open each page with a one-sentence plain answer after the H1**; link
  prerequisites and next steps; instructions in text, never in images; worked examples for
  the common case *and* the breaking case ("agents copy examples directly and can't infer what
  isn't shown"); keep tabbed content sparse ("a person sees one tab, an agent reads every
  one"). Its thesis: "what each user type needs overlaps more than it diverges".
- **Agent-score checks** (Fern/Mintlify, built on the agentdocsspec): content discoverability
  (llms.txt present and well-formed), markdown availability, page size (pages over 100 k
  chars fail; the spec says ≤ 50 k), URL stability.
- **Progressive disclosure** is contested: an index that links deeper is good for agents;
  content hidden behind tabs/dropdowns is bad (they read all of it, or none).
- **Anthropic's own skill guidance** (via the repo's skill_caps): a body under 5 000 tokens,
  detail in files read on demand; the repo already measured that placement matters more than
  prose (grep beats reading, F3).
- Implications for a rebuild:
  - one source renders to HTML *and* a markdown twin (`.md` beside each page) plus a curated
    `llms.txt`: cheap in Sphinx (MyST sources are already markdown; a small builder step);
  - the n8n page rules double as the human rules (skimmable, self-contained, one answer first);
  - evidence folds (`<details>`) are *fine* for agents in markdown (they read it all) and good
    for humans; tabs are not;
  - every page ≤ 50 k chars, which also forces the slimming;
  - the skill stays the agent's entry, and its routing table is the de-facto llms.txt today
    (`SKILL.md` § Routing); a manual llms.txt should route *to* the skill for "how", and the
    skill to the manual for "what"/"why".

### F5. Navigation: prioritised top level vs the four types
- Diátaxis itself says structure should emerge and never to create empty quadrants
  (`how-to-use-diataxis.rst`); Django keeps the four types as a *second* axis under a
  thematic/first-steps front page; xarray/astropy use Get started / User guide / API /
  Contribute. The maintainer's position (frequency first, types labelled) matches all three.
- **Theme constraint** (WP-1412, closed): furo stays. pydata-sphinx-theme's navbar truncates at
  five entries and its sidebar is empty on a flat tree. So a prioritised top level is either
  (a) furo captions over a *nested* tree, or (b) a curated front page (cards, "First steps"),
  with the type carried as a badge/subtitle on each page rather than as a tab. A nested tree
  is what a rebuild produces anyway and would also unlock pydata if ever wanted.
- Candidate front page, by frequency of need (to be decided in the re-plan): Start here
  (install, 10-minute fit, notebooks) → Doing a refinement (how-tos, most-used first) →
  Understanding (explanation: how a fit works, parameters, the report, correlations) →
  Reference (API, parameters map, files/formats, CLI, GUI) → Theory (Part 2) → For agents →
  Project (compatibility, contributing, changelog). Types labelled per page, with "How to …"
  and "About …" titles doing the labelling for free.

### F6. The switching reader (users of other codes)
- Precedent: Polars "Coming from pandas" (verified from source): H2 "Differences in concepts"
  (why it behaves differently) then H2 "Key syntax differences" with *paired code blocks*
  (pandas first, Polars second); chDB's migration guide adds "What works unchanged / Key
  differences / Gradual migration". No Rietveld code publishes a comparison matrix; the only
  survey data is a 140-respondent DANSE poll (GSAS 75 %, FullProf 39 %).
- What rietx already has to draw on, and nowhere states as a comparison:
  - the README feature list (modes, data types, corrections, readers/writers for TOPAS,
    FullProf, GSAS, GSAS-II, magnetic in progress);
  - `docs/VALIDATION.md`'s tiers, in particular `cross_code` rows "with its protocol adopted"
    (FAP vs GSAS-II; LaB6+cBN vs TOPAS to < 50 ppm; TOPAS Y_calc at zero cycles for seven
    exported models; GSAS-II SH texture golden), the strongest honest material for "does it
    agree with my code";
  - the readers that already know the other programs' vocabularies (`io/projects/*`), so a
    name-equivalence table can be *checked* against them;
  - the maintainer's essay `why.html` (agents, openness, ethos) as the explanation of *why* it
    differs.
- Candidate pages: "rietx for TOPAS / GSAS-II / FullProf users" (concepts that differ, then
  paired snippets: `.inp` line → rietx call; `p:h:Scale` → `phases.0.scale`), one
  "At a glance" page (features × modes × data types, every cell linked to its chapter and its
  validation row, no cell without evidence), and the parameter map's "elsewhere" column. The
  honest comparison must say what rietx does *not* do (TOF? FPA fenced to v2, stacking faults
  refused, rigid bodies deferred) as plainly as what it does; WTD's *Complete* and the repo's
  "never a confident singleton" both demand it.

### F7. What this changes in the candidate slate (D6)
- A rebuild rather than a slimming: a new tree, nested, with every page typed; the existing
  chapters mined for content, not edited in place.
- Add to the slate: a markdown twin + `llms.txt` build step; an agent eval *with* the manual
  allowed (the missing experiment); "coming from X" pages and an at-a-glance matrix backed by
  VALIDATION rows; a terminology list / Vale lint in the style-guide sense; the front page as
  the priority surface.
- Keep from the slate: parameter map and plan ladder generated from code; the folding project
  tree; one-line diagnostics with per-code explanations; tutorials with explanation cut to
  links; the API reference.

### F8. Decisions the maintainer took on F (2026-10-15)
- **Agent eval with the manual: later, as the rebuilt manual's acceptance test.** Rebuild on
  best practice now (F4's rules, markdown twin, llms.txt); then run the eval harness with the
  manual allowed and let it grade the result.
- **Front-page audiences, in this order:** (1) the newcomer who knows Rietveld from another
  code; (2) the switcher assessing rietx; (3) the person supervising an agent. The agent
  itself is served by the skill and the markdown twin, not by front-page prose.
- **No "what rietx does not do" page.** In its place a **high-level roadmap**: features in
  development and features planned, drawn from the open milestones (`docs/ROADMAP.md`'s
  table and `docs/milestones/<name>.md`), so the switcher reads direction rather than absence.
  It should be generated or at least cross-checked against the milestone records, so it
  cannot go stale the way `compatibility.md:172` did.
- **Not wedded to furo; use the best tool for the job.** WP-1412's "stay" verdict was taken
  against a flat 34-chapter tree and a ~45-line CSS cost; a rebuild with a nested tree removes
  the first reason, and the second is small. The re-plan should weigh the theme (furo,
  pydata-sphinx-theme, sphinx-book-theme, shibuya) and the toolchain (Sphinx+MyST versus
  MkDocs Material, Docusaurus, VitePress) on what the new manual needs: a top-level nav with a
  prioritised front page, light/dark figure pairs, mermaid, bibtex citations and numbered
  equations (Part 2, non-negotiable), the executed notebooks, a markdown twin and llms.txt,
  and the test guards in `tests/test_manual*.py` (which parse MyST sources, so a toolchain
  change costs a test rewrite). WP-1412's measured couplings (`docs/wp/1412-*`) are the
  starting cost table.

### F9. Hand-off
The brief is to be copied into the repo as `docs/wp/1975-manual-rebuild-findings.md` with the
template's header lines (Milestone: unscheduled, Status ⬜, Track: The repo's own process,
Priority P2 with the date), the index regenerated by `python3 .claude/hooks/wp_index.py`, and
nothing else changed, on branch `claude/loving-mccarthy-416vvl` from a worktree. The re-plan
session starts from that file.

## G. Groundwork checked before the re-plan (2026-10-15, third session)

Facts the re-plan needs whatever the maintainer's new concepts turn out to be. Each closes a
claim § B, C or F left open or unverified.

### G1. § B still holds
`main` moved by one merge since 54526f8 (PR #942, WP-1908, now at 67af0b4). It touched
`refine.py` past every line § B4 and § B6 cite, and nothing under `docs/manual/`,
`examples/tutorials/`, `help.py`, `_display.py` or the manual's tests. The cited line numbers
were re-read and match. Root `CLAUDE.md` is still 982 lines.

### G2. The manual already publishes a markdown copy of every page, and it is not clean
This settles § F3's "probably publishes `_sources/*.md.txt`; unverified".
- `conf.py` never sets `html_copy_source`, so Sphinx's default (on) applies, and
  `.github/workflows/pages.yml:60` deploys `sphinx -W -b html docs/manual site` as built.
- A local build (28.8 s cold) wrote 46 files under `_sources/` for 48 pages, 3.3 MB, and furo
  links each page to its copy (`using/concepts.html` → `../_sources/using/concepts.md.txt`).
- The copies are the MyST *sources*, not rendered markdown:
  - 21 carry unexpanded `{{ NAME }}` substitutions, so an agent reads a placeholder where
    the page shows a live constant;
  - 2 carry a `{literalinclude}` directive in place of the example code;
  - the five tutorials publish as raw `.ipynb` JSON.
- So a twin built for agents (§ F4) has to expand substitutions, resolve includes and render
  notebooks to markdown. The copy that ships today is either switched off or replaced by it;
  left as is, it is the stale twin § F4 warns is worse than none.

### G3. GSAS-II keeps humps and background peaks inside its Background
This settles § C3's "unconfirmed, from memory", and it bears on the maintainer's question of
where the background goes and how humps interact with it (§ A1).
- `GSASIIpwd.getBackground` (lines 978-1147 of `GSASII/GSASIIpwd.py`, AdvancedPhotonSource/
  GSAS-II `main`, fetched 2026-10-15) builds one curve per histogram from three parts: the
  polynomial or interpolated terms (`Back;i`), Debye diffuse terms (`DebyeA/R/U;i`) and
  background peaks (`BkPkpos/int/sig/gam;i`). All three carry the histogram prefix, so all
  sit in the `:h:` scope of § C3.
- rietx splits the same signal in two. Humps join the background *curve*, declared peaks join
  the *ticks*, and both live in `instrument.extra_components`, a sibling of
  `instrument.background` kept apart so that a plan's `instrument.background.*` glob cannot
  free them (§ B2).
- So a GSAS-II user looks for humps under Background and will not find them there. Whatever
  the parameter map's grouping, it needs that one sentence, and the "elsewhere" column of
  § D2 needs the `BkPk*` and `Debye*` names.

## E. Open questions for the re-plan
- Does Part 2 (Theory) count as Diátaxis explanation, and do some Part 1 explanations
  move there?
- Where does agent-facing material sit? Today it is the skill page (rendered whole), plus
  "agent" admonitions and checklists in the notebooks. Is it a separate audience track?
- Evidence folds (sphinx-design `dropdown`) or links out to milestone records? And who
  reads measurements?
- How far to generate the content (parameter map, plan ladder, API reference, diagnostic
  index) versus authoring it, given the repo's one-authority rule?
- Order: the report text (1976) is paid by every user on every fit, so does it come
  before the docs work?
- The maintainer's new concepts, still to be stated.

## Tasks

- [ ] Re-plan the manual from this brief, in a session of its own, bringing in the
  maintainer's new concepts; then rewrite Goal and Tasks here or file the WPs the plan
  names and close this one into them.

## Acceptance

```sh
python3 .claude/hooks/wp_index.py        # the index is unchanged afterwards
.venv/bin/python -m pytest tests/test_docs_consistency.py -n auto --dist loadgroup
```

## References

- Procida, D. Diátaxis. https://diataxis.fr (source: github.com/evildmp/diataxis-documentation-framework)
- Write the Docs guide. https://www.writethedocs.org/guide/ (source: github.com/writethedocs/www)
- llms.txt proposal. https://llmstxt.org (source: github.com/AnswerDotAI/llms-txt)
- Barik, T., Ford, D., Murphy-Hill, E., Parnin, C. (2018). How should compilers explain
  problems to developers? ESEC/FSE.

## Handover log

### 2026-10-15 — the brief, from two research sessions

What this means: the maintainer wants a manual a newcomer, a switcher from another
Rietveld code and a person supervising an agent can each use, typed by Diátaxis, prioritised
by frequency of need, readable by humans and reachable by agents; and is willing to rebuild
it. This file is the evidence that re-plan starts from, consolidated so the next session
loads one file instead of re-running the search.

**Done.** Two planning sessions (Claude Code, 2026-10-15) read all 25 Part 1 chapters
against Diátaxis, inventoried the parameter registry, the project layout, the API surface,
the tutorials and the report text, swept the repository's own record of agent reads, and
read the Diátaxis and Write the Docs sources from GitHub (their sites are blocked from the
cloud sandbox). Two drafts of an implementation plan were declined in favour of a re-plan;
their designs are kept in § D as candidates. Nothing in `src/`, `docs/manual/` or `tests/`
was changed.

**Not done.** The re-plan itself. The scratch clones of the Diátaxis and Write the Docs
sources lived in the sandbox's scratchpad and are gone with it; re-clone from the
repositories named in § References.

**Next.** `/wp-start` on this WP in a fresh context, read § F8 (the decisions) and § E (the
open questions) first, then plan.
