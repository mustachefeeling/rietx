# pxrd-refine — Roadmap

Canonical milestone **index**. The content that used to live here is split so
a work session loads only what it needs:

- **[AGENT_PROTOCOL.md](AGENT_PROTOCOL.md)** — how to *use* the package as an
  automated operator: turn-on order, degeneracies, abstention handling,
  diagnostic-code semantics, and the measured findings that change agent
  behaviour. Written for consumers, not maintainers; a WP that adds a
  diagnostic code or a correction should add its row there.
- **[DESIGN.md](DESIGN.md)** — the design record (rationale, locked decisions,
  invariants). Stable; read the specific section a work package links.
- **[LITERATURE.md](LITERATURE.md)** — the local paper corpus and how to search
  it, plus which papers back which module and which are still unread. Check it
  before requesting a paper or re-deriving a published constant.
- **[milestones/](milestones/)** — shipped-milestone records with the measured
  acceptance blocks (`v0.1.md`, `v0.2.md`, …).
- **[wp/](wp/)** — one self-contained **work package (WP)** per task. Each has
  its own context, commit-sized checklist, acceptance command, and handover
  log. `wp/TEMPLATE.md` defines the format.

## Session protocol

1. **Start** from "Current focus" below (or the WP the user names). Read that
   one WP file — self-contained on top of CLAUDE.md. Open DESIGN.md only at
   sections the WP links; do not read other WP files.
   **On arrival at a WP, prune its `### Inherited` first**: fold still-true
   entries into Context or Tasks, delete stale ones (say why in your handover
   entry). The section is a mailbox, emptied on every visit and deleted —
   fully consumed — when the WP closes.
2. **During**: land tasks as small commits prefixed `WP-NNNN:`; check items
   off in the WP file as they land.
3. **End** — or whenever interruption threatens — run `/wp-handover`. The
   checklist it carries: dated handover entry prepended (newest first: done /
   in flight / next / gotchas), Status line and the index-row glyph below
   synced, forward references pushed into the `### Inherited` of any affected
   WP that is not closed and not yours (a handover log reaches only your own
   successor on the same WP), rule 4 applied to anything this session wrote
   into a CLAUDE.md, working tree clean and pushed.
4. **A CLAUDE.md takes rules, not findings.** A line enters a CLAUDE.md
   (root, `gui/`, `tests/`) only as a standing rule a stranger needs in six
   months — a few lines, evidence compressed to one clause plus a pointer to
   the WP or milestone record that holds the measurement. Counts and timings
   go only in Commands → "Current numbers", **replaced, never appended**.
5. **WP closes** (✅/🛑): rewrite "Current focus" for the successor and MOVE
   the outgoing narrative to the in-flight milestone record
   (`milestones/v1.0.md` § "How v1.0 is getting here"). Current focus stays
   under ~40 lines and repeats nothing a closed WP's own file already says.
6. **Milestone ships**: finish `milestones/vX.Y.md` with the measured
   acceptance block, flip the milestone row here, check README's claims.

`tests/test_docs_consistency.py` enforces the mechanical parts: status
vocabulary and glyph sync, Inherited placement, link resolution, and the
size caps on this file and CLAUDE.md.

## Current focus

**Last closed: [1044](wp/1044-gui-view-cursor-theme.md), 2026-08-06** — four
defects reported from use, of which the two that read as unrelated were one
sentence of plotly's autorange: a redraw carried no `range`, so it re-autoranged
over the peak markers and the mask shapes, which span the *whole pattern*. Hence
**the view is handed back on every draw** (WP-1015's camera rule, one panel over)
and a `ui` key belongs to whatever it is *about* — the theme is the person's and
moved to `/api/settings`, out of the mutating-verb 409 with it. Before it,
**[1016](wp/1016-sequential-series-panel.md), 2026-08-05**: an in-situ ramp is
drivable from the GUI, built on **a smooth curve is exactly what a poisoned chain
produces**; the series lives *beside* the project, persistence deferred to
**1003**. The GUI is complete but for [1017](wp/1017-gui-manual-onboarding.md),
whose `### Inherited` now carries three sentences 1044 made wrong.

**In flight: [1041](wp/1041-indexing-benchmark-gallery.md)** — the gallery, opened
by clearing its inherited defects (one shared `engines.solution_key`, an opt-in
Le Bail result, `viz/indexing.py`'s three renderers). Two rows turned over, and
**its recorded design for the panel aggregate is refuted** — a log-sum scores 5 of
6, exactly Borda's, because summing raw logs weights each member by its dynamic
range; `fom.log_sum_scores` ships tested and unwired. Open: tasks 5-9.
**[1040](wp/1040-engine-svd-index.md) stays 🔄**, its one open item being 1041's
scoreboard.

Narratives: [milestones/v1.0.md](milestones/v1.0.md). Twelve sessions running
(1030 → … → 1041, 1016, 1044): **instrument before ranking, and let the by-hand
run judge** — 1041 is the sharpest case, two green tests asserting what a filter's
own artefacts produced. **A prediction is not a measurement**, 1016 adds the
inverse (**nor is an inherited claim**), and 1044 adds the third: **nor is a
reported cause** — three of its four defects named one, and only one was right.

**Queue** (ordering arguments in the v1.0 tables below):

1. [1028](wp/1028-robustness-external-data.md) — robustness on data and CIFs
   we did not author; every item was hit by a real external benchmark.
2. [1042](wp/1042-anytime-results-quick-default.md) — from the source literature;
   its `### Inherited` carries 1037's streaming argument and 1016's third writer
   of the run record's progress fields. (1041 is in flight above.)
3. [1026](wp/1026-indexing-acceptance.md) — **reopen for criterion 1 only**: the
   bethanechol global score. 1040 measured there is no pending fix to wait for.
4. [1017](wp/1017-gui-manual-onboarding.md) — the GUI's last WP; nine tabs now.
5. [1003](wp/1003-api-freeze-pypi.md) — freeze + PyPI, deliberately last so the
   freeze covers an exercised surface. Both carry an `### Inherited` this
   session filled; read it first.

**The bar** (milestone row below): full validation matrix green; GUI end-to-end on
11-BM NAC matching the API-driven acceptance; indexing graded against the
**individual** program globals in Bergmann et al. 2004 (McMaille +5, Crysfire +6
to beat — "≥ +9" was Table 5's `first_4` oracle, which no entry reaches), and
abstaining on the mixture fixtures.

## Milestones

| Milestone | Scope | Status | Acceptance |
|---|---|---|---|
| v0.1 | Vertical slice: synchrotron CW, Rietveld + Le Bail | ✅ **shipped** ([record](milestones/v0.1.md)) | 11-BM NAC: a = 10.251285(12) Å, Rwp 9.2%, CaF₂ impurity auto-flagged |
| v0.2 | Lab diffractometer + FitReport attribution + viz | ✅ **shipped 2026-07-22** ([record](milestones/v0.2.md)) | SRM 660c LaB6: a = 4.156895(25) Å (+28 ppm vs NIST value for this dataset, Bérar-Lelann-inflated esd), Rwp 8.7%; GSAS-II FAP tutorial: Rwp 9.73% vs GSAS's 10.05% on identical channels, cell +116 ppm (uniform d-scale convention offset) |
| v0.3 | Multi-phase QPA, Pawley, aniso ADPs, multi-histogram | ✅ **shipped 2026-07-24** ([record](milestones/v0.3.md)) | SRM 676a corundum: c/a +30 ppm vs certificate (absolute axes −313/−283 ppm, uniform d-scale); IUCr round robin: sample-1 worst 5.1 wt% (traces ≤1.3), sample 2 worst 2.9 wt% with brucite March-Dollase r=0.67, sample 4 characterised as the designed Brindley failure (µR fence fires) |
| v0.4 | Differentiable backends: JAX jacfwd, mixed precision, torch-MPS; true Voigt; restraints | ✅ **shipped 2026-07-27** ([record](milestones/v0.4.md)) | Cross-backend Jacobian agreement (analytic/FD/jax/torch × 8 configs + multi-histogram + stage boundaries) inside the 5e-3 rel-L2 fp64 bar; an all-fp32 Apple-GPU refinement of SRM 676a lands Δa = −3.5e-8 Å from numpy fp64 (bar 3e-5); wall-clock reported, not gated — and it is a *finding*: MPS is 46-182× slower (launch-latency-bound) and jit'd jacfwd is within 2.1× of the analytic assembly at best, so the batched peak loop is a numpy-path win (WP-0605), not GPU enablement |
| v0.5 | Corrections & microstructure (absorption, Stephens, f′f″) | ✅ **shipped 2026-07-28** ([record](milestones/v0.5.md)) | capillary absorption validated at **both** levels: the Rouse (1970) cylinder factor against a quadrature of the exact ITC eq. (6.3.3.4) integral across 0 ≤ µR ≤ 1 *and* 0 ≤ sin²θ ≤ 1 (0.0035, the paper's own bound), and on real 11-BM SRM 660a LaB₆ data in a documented 0.81 mm bore — Rwp moves 3e-8, the cell 8e-12 Å, and *both* Biso move by the predicted 0.0166542 Å². Plus the two accuracy wins no fit statistic shows: dispersion takes the round-robin QPA error from RMS 2.26 → 0.69 wt %, and a mis-declared flat-plate thickness biases Biso by up to −1.5 Å² |
| v0.6 | TOPAS-style bounded LM, agent surface, batched peak loop, theory manual | ✅ **shipped 2026-07-29** ([record](milestones/v0.6.md)) | bounded LM 0.74–1.04× vs scipy TRF (CPU — the expected Amdahl tie), identical minima on 2/3 protocols, ΔBIC −13 on the third, and the Stephens cone enforced as a linear inequality (brucite 12/43 → 0/43 outside, at higher Rwp); FCJ node memo 1.23× bit-identical; agent schema generated from live registries with a registry-membership meta-test; theory manual builds `-W`-clean with every fenced constant injected from the live package and five anti-divergence guards in the fast suite |
| v1.0 | Hardening, human GUI, indexing, API freeze, PyPI | ⬜ | full validation matrix green; GUI end-to-end: `pxrdref gui` covers import → edit → refine → inspect → branch → export on 11-BM NAC, with Rwp matching the API-driven acceptance for the same protocol (the GUI is a view, not a second implementation); **indexing is graded against the individual program globals of the published bethanechol benchmark** (Bergmann et al. 2004 Table 5: ITO13 −14, DICVOL91 −8, TREOR90 −4, McMaille +5, Crysfire +6 — the former "≥ +9" was that table's `first_4` oracle over four programs, which no single entry reaches; restated by WP-1026) and abstains rather than ranking a cell on the mixture and unidentified-pattern fixtures |
| v2+ | FPA, neutron/TOF, texture, MCP server | ⬜ fenced | — |

## Work packages

### v0.3 — multi-phase workflows (detailed, ready to start)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0301](wp/0301-wyckoff-constraints.md) | Wyckoff/site-symmetry constraints (affine p = C·θ + d) | ✅ 2026-07-22 | — |
| [0302](wp/0302-atomic-coordinates.md) | Atomic-coordinate refinement | ✅ 2026-07-23 | 0301 |
| [0303](wp/0303-anisotropic-adps.md) | Anisotropic ADPs | ✅ 2026-07-23 | 0301 |
| [0304](wp/0304-qpa-hill-howard.md) | QPA: Hill-Howard ZMV mass fractions | ✅ 2026-07-23 | — |
| [0305](wp/0305-brindley-microabsorption.md) | Brindley microabsorption | ✅ 2026-07-23 | 0304 |
| [0306](wp/0306-pawley-mode.md) | Pawley mode | ✅ 2026-07-23 | — |
| [0307](wp/0307-march-dollase.md) | March-Dollase preferred orientation | ✅ 2026-07-23 | — |
| [0308](wp/0308-multi-histogram.md) | Multi-histogram stacked residuals | ✅ 2026-07-24 | — |
| [0309](wp/0309-exporters.md) | Exporters: reflection table, CIF+esds (structure side landed in 0303), QPA table | ✅ 2026-07-24 | 0304 |
| [0310](wp/0310-acceptance-srm676a-qpa.md) | Acceptance: SRM 676a + IUCr QPA round robin | ✅ 2026-07-24 | 0304, 0305 |

### v0.4 — differentiable backends (expanded 2026-07-24; ready to start)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0401](wp/0401-backend-op-shim.md) | Backend op shim (34 named ops + `window_add`/`segment_sum`; the WP was scoped at "~41" before the survey) + residual purity refactors | ✅ 2026-07-24 | — |
| [0402](wp/0402-jax-backend.md) | JAX backend: chunked jacfwd | ✅ 2026-07-24 | 0401 |
| [0403](wp/0403-cuda-mixed-precision.md) | Mixed-precision policy (CUDA-deferred, CPU-testable) | ✅ 2026-07-24 | 0402 |
| [0404](wp/0404-cross-backend-jacobian-ci.md) | Cross-backend Jacobian CI | ✅ 2026-07-24 | 0402 |
| [0405](wp/0405-faddeeva-voigt.md) | True Voigt via shared Faddeeva w(z) | ✅ 2026-07-24 | 0401 |
| [0406](wp/0406-restraint-penalty-rows.md) | Restraint penalty rows | ✅ 2026-07-24 | — |
| [0407](wp/0407-esd-reconciliation.md) | esd reconciliation (Bérar-Lelann placement) | ✅ 2026-07-24 | — |
| [0408](wp/0408-torch-mps-backend.md) | torch backend (MPS fp32 forward) — moved from v0.6 | ✅ 2026-07-27 | 0401, 0402, 0404 |

### v0.5 — corrections & microstructure (stubs)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0501](wp/0501-absorption-corrections.md) | Capillary (cylindrical) absorption | ✅ 2026-07-27 | — |
| [0502](wp/0502-surface-roughness.md) | Surface roughness (Suortti + Pitschke) | ✅ 2026-07-27 | — |
| [0503](wp/0503-stephens-anisotropic-strain.md) | Stephens anisotropic strain | ✅ 2026-07-27 | — |
| [0504](wp/0504-anomalous-scattering-xraydb.md) | Anomalous f′,f″ (bundled Cromer-Liberman, not xraydb) | ✅ 2026-07-27 | — |
| [0505](wp/0505-sequential-refinement.md) | SequentialRefinement warm start | ✅ 2026-07-28 | — |
| [0506](wp/0506-secondary-extinction.md) | Secondary extinction (Sabine) | ✅ 2026-07-23 | — |
| [0507](wp/0507-anode-wavelengths.md) | Additional anode wavelengths (Co/Cr/Fe/Mo/Ag) | ✅ 2026-07-28 | — |
| [0508](wp/0508-flat-plate-absorption.md) | Flat-plate absorption + real-data capillary acceptance | ✅ 2026-07-28 | 0501 |

### v0.6 — solver, performance & agents (stubs)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0601](wp/0601-bounded-lm-solver.md) | TOPAS-style bounded LM | ✅ 2026-07-28 | — |
| [0602](wp/0602-agent-json-surface.md) | Agent JSON surface hardened | ✅ 2026-07-29 | — |
| [0604](wp/0604-theory-manual.md) | Sphinx + MyST theory manual | ✅ 2026-07-29 | — |
| [0605](wp/0605-batched-peak-loop.md) | Batched peak loop (spike, then decide) | ✅ 2026-07-28 | — |

(0603 — the torch/MPS backend — moved to v0.4 as
[0408](wp/0408-torch-mps-backend.md) on 2026-07-24; the number is left unused so
the history stays readable.)

0605 closed 2026-07-28 with a measured **no-go on the batched rewrite** and its
task-0 cache graduated to production (1.23× on the SRM 660c protocol,
bit-identical): the 2.4×-at-fixed-work figure was a microbenchmark fact, not a
fit fact — the FCJ padded plane is a 0.58× *regression*, and the win that
survives (symmetric rows, exactly bit-equal) is the starting point for the
v2-fenced `vmap` series, not for a single-pattern rewrite. Grounds and the
reopening conditions are in the WP's answers/handover.

### v1.0 — hardening, human GUI & release (GUI WPs added 2026-07-29)

Order: backend API first (1004–1007, each independently useful without the
GUI), then server (1008–1009), then frontend (1010–1017); the freeze (1003)
is the milestone's last row so it covers a surface the GUI has exercised.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1001](wp/1001-validation-matrix.md) | Validation matrix + tolerance policy | ✅ 2026-07-29 | — |
| [1002](wp/1002-ci-matrix.md) | CI matrix | ✅ 2026-07-29 | — |
| [1004](wp/1004-parameter-plan-api.md) | Parameter & plan API surface | ✅ 2026-07-30 | — |
| [1005](wp/1005-project-container.md) | Project container (`.pxrd/`) | ✅ 2026-07-30 | 1004 |
| [1006](wp/1006-run-control.md) | Run control: streaming, progress, cancellation | ✅ 2026-07-30 | — |
| [1007](wp/1007-capabilities-guards.md) | Capabilities, structured guards, background export | ✅ 2026-07-30 | 1004 |
| [1008](wp/1008-gui-server.md) | GUI server, session model, `pxrdref gui` | ✅ 2026-07-30 | 1004–1007 |
| [1009](wp/1009-textdoc-format.md) | Project text document (`.pxt`): format + parser | ✅ 2026-07-30 | 1004, 1005 |
| [1010](wp/1010-frontend-scaffold.md) | Frontend scaffold: build, committed dist, shell, plot, console | ✅ 2026-07-30 | 1008 |
| [1011](wp/1011-parameter-plan-editors.md) | Parameter editor, plan editor, run controls, disclosure | ✅ 2026-07-30 | 1010 |
| [1012](wp/1012-history-report-panel.md) | History worktree, report panel, one-click suggestions | ✅ 2026-07-30 | 1010 |
| [1013](wp/1013-text-pane-sync.md) | Text pane (CodeMirror 6) + two-way sync | ✅ 2026-07-30 | 1009, 1010 |
| [1014](wp/1014-import-structure-editing.md) | Import & in-GUI structure/instrument editing | ✅ 2026-07-30 | 1008, 1010 |
| [1015](wp/1015-structure-viewer.md) | Structure viewer, zero new dependencies | ✅ 2026-07-30 (+ scene pass same day) | 1010 (1014 soft) |
| [1016](wp/1016-sequential-series-panel.md) | Sequential series panel | ✅ 2026-08-05 | 1008, 1010, 1011 |
| [1029](wp/1029-gui-usability.md) | GUI usability: legibility, layout, colour, theming | ✅ 2026-07-30, second pass 2026-07-31 | 1010–1015 |
| [1032](wp/1032-gui-repairs.md) | GUI repairs found by use (tooltips, ticks, curves, gestures, field help) | ✅ 2026-08-05 | 1010–1015, 1027, 1029 |
| [1033](wp/1033-plot-range-regions.md) | 2θ limits and excluded regions, visible and selectable | ✅ 2026-08-05 | **1032** (same file), 1005, 1009 |
| [1034](wp/1034-panel-layout.md) | Model and Text in the right panel | ✅ 2026-08-05 | 1013, 1014, 1029 (1032 soft) |
| [1035](wp/1035-symmetry-surfaced.md) | Symmetry, surfaced and editable | ✅ 2026-08-05 | ~~1036~~ ✅, 1014 (1004 soft) |
| [1044](wp/1044-gui-view-cursor-theme.md) | GUI defects found by use: the view, the armed cursor, the theme | ✅ 2026-08-06 | 1029, 1032–1033, 1027 |
| [1017](wp/1017-gui-manual-onboarding.md) | GUI manual, in-app help, onboarding | ⬜ | 1011–1016, 1029, 1032–1035 (soft) |
| [1031](wp/1031-docs-consolidation.md) | Planning-doc consolidation + handoff mechanization | ✅ 2026-07-31 | — |
| [1003](wp/1003-api-freeze-pypi.md) | API freeze + PyPI | ⬜ | 1001, 1002, 1004–1036 |

**1032–1035 came from a use session** (2026-08-04, eleven observations plus one
question), the same provenance as 1029 and cut by *size* rather than by screen
region: 1032 is nine hour-sized repairs, 1034 is the one redesign, and neither
is allowed to hold the other hostage. **1032 and 1033 are strictly sequential
because both edit `Plot.svelte`** — the dependency column says so even though
the features are independent, for the reason the 1018 interleaving already
taught (one worktree per concurrent session, or only one session commits). The
question that started 1035 turned up [1036](wp/1036-crystal-system-settings.md),
which is not a GUI WP at all — and 1035 then found that the same question had a
*second* answer nobody had asked for: `PATCH /api/structure` accepted a model
whose parameter table cannot be built, because `Refinement.edit` snapshots
without ever building one. All four are closed; the set is complete.

### v1.0 — indexing (added 2026-07-29)

Unit-cell determination from a pattern, and the peak picking it needs. Added
into v1.0 on the same argument that un-fenced the GUI: `index()` is a
top-level entry point, a peer of `refine()`, and the freeze (1003) should
cover a surface that has been exercised. It also closes a seam the package
declared long ago — `report/layer2.py` has emitted the
`reindex_or_recheck_cell` action since v0.2 with nothing behind it.

Order: peaks and quality first (1018–1019, useful on their own), then the
shared core (1020), then the three engines (1021–1023, independent of each
other), then consensus (1024), space groups (1025), acceptance (1026), GUI
(1027). [1030](wp/1030-engine-scaling-low-symmetry.md) was added 2026-07-30 and
sits between 1026 and its own grade: the benchmark cannot be scored until a
monoclinic search finishes.

**[1018](wp/1018-peak-picking.md) closed 2026-07-30**, and the row that had
carried the 🔄 glyph ("landed but not finished") is the only one that ever has.
What closed it is the **σ pull calibration** — the gate the whole downstream
tolerance model rests on, because every indexing tolerance is a multiple of the
σ(2θ) `pick_peaks` reports, and Rwp, χ² and eyeball overlays cannot see a σ that
is uniformly 40 % too small. Measured over ~1300 fitted lines per configuration,
from 100 fixed-seed Poisson realisations of a forward-model LaB₆ pattern:
`(2θ_fit − 2θ_true)/σ_fit` has **mean +0.032 / std 0.971** on a synchrotron
single line and **−0.083 / 0.980** on a lab Cu Kα doublet, against `|mean| <
0.15` and `std ∈ [0.85, 1.20]` written before the measurement. So the reported σ
is the right scale, and 1019/1020 may now tune against it.

The gate found **two more defects** — six in total for this WP, and *not one of
the six was visible by reading the code*. Both new ones are doublet physics. A
marginally resolved Kα2 has **no maximum**, so the alias filter cannot see it,
but it does have a curvature shoulder: it cleared the 5σ seeder, sat outside the
half-FWHM grouping gap, formed a **singleton group**, and came back as a line
with an esd — and the ΔBIC prune cannot refuse it, because a singleton is judged
against "no peak at all" and there genuinely is intensity there. That was one
spurious line per pattern and a **−21 mean σ pull** on the LaB₆ 110 reflection.
And the doublet amplitude ratio is not `weight`: each line diffracts at its own
Bragg angle, so it carries its own **Lorentz-polarisation** factor, and holding
the bare weight dragged the fitted Kα1 position down by 2e-4° (mean pull −0.26 →
−0.19).

Two results outlast the WP. **Sizing rule: 200 groups is enough for a `std` bar
and not for a `mean` bar** — at pull std 1 the standard error of the mean over
200 groups is 0.07, half the 0.15 bar, and a 200-group subsample of this very
ensemble read −0.15 where the converged value is −0.08; the test now asserts
`3·SE < bar` before asserting the bar, so an undersized ensemble fails loudly
instead of passing by luck. And **the remaining −0.08σ doublet bias is a
measurement, not a to-do**: 2e-5°, a fortieth of a channel, with four candidate
mechanisms excluded by substitution (exact background, isolated reflection,
per-line widths, model-σ weights) and the estimator shown unbiased to ±0.02 in
isolation — so what is left is in the detection-seeded window, two orders below
the systematic-error scale 1019 exists to model.

**[1019](wp/1019-indexing-data-quality.md) closed the same day**, and its
deliverable is a *gate*: `assess_peak_list` judges a peak list fit to index or
**abstains with a reason**, and `fit_shift_model` attributes a systematic 2θ shift
to a zero-point error, a displaced specimen or a transparent one — or declines to,
which is the half that matters, since every program the 2004 benchmark paper
surveys fits one constant "zeropoint" instead.

Its founding question was one the plan had not resolved: **what is knowable from a
peak list alone.** Everything except the shift is a property of the list. The
shift is not — with no cell there is nothing to deviate from — so the screen is
*conditional* on reference positions, and with none the report says
`shift.source == "unavailable"` rather than reporting a zero shift it never
measured. What *is* computable with no data at all is the separability geometry of
the three templates over the angles sampled: a statement about the experiment
rather than the specimen, readable before a specimen is loaded.

Four measurements, and two of them overturned something:

- **"The cell stands when the cause is ambiguous" is true only with the word
  *competitive* in it.** Over 10-25° 2θ with a 0.10° cos θ displacement, all three
  templates' predicted corrections differ by 0.046° — nearly half the shift, a
  0.2 % cell error if the wrong one is applied. But the template that disagrees is
  the one the data *rejects*, and over the two that fit comparably the spread is
  0.0011°. The plan's conclusion survives; its reasoning is narrowed, and
  `prediction_spread_deg` now reports the number instead of a docstring asserting
  the claim.
- **A measured no-go: dominant zone and dominant row are not detectable from a
  census.** Neither is a summary statistic — a dominant zone is the statement that
  the low-angle lines satisfy a *two-dimensional* quadratic form, a dominant row an
  arithmetic progression k²B among the low Q values. Each is a search. The obvious
  census (Ito's most-repeated Q difference) was written, measured and removed: it
  scores dominant-zone cells at +0.9σ and +0.8σ against a permutation null while
  scoring a *general* monoclinic cell at +3.3σ, and against a uniform null a
  **cubic** list scores +15.6σ — it detects commensurability, not zones. A test
  asserts the diagnostic code's absence so it cannot creep back, and the engines
  (1021/1022) have been told they own the detection.
- **Smith's volume envelope needed two scalings, and the second was found by the
  envelope excluding the right answer**: with the Laue orbit factor alone,
  corundum's bound came out at 125 Å³ against a true 255 Å³, because R-centring
  extinguishes two thirds of hkl. Centring is part of the answer (1025's extinction
  symbol), so the default is the worst case each system allows — the one failure a
  search bound may not have is excluding the true cell — and the envelope is
  reported per system, since they span 96×.
- **`constant` and `cos θ` stay 0.96 collinear even over 10-140°**, so
  separability is decided on the residual-SS ratio against real data and never on
  the geometry alone.

One item was left open for the user rather than a session: the per-system envelope
scaling is *derived* here, not published, and a clean copy of Smith (1977) would
let the derived factors be checked against the paper's — the WP-0501 b₂
transposition being the precedent for why that check is worth asking for.

**Closed 2026-07-30, and the answer was that the question had a false premise.**
The paper arrived and is **triclinic-only**: it publishes *no* per-system factors,
so there is nothing to check the derived scalings against, and its own closing
paragraph names systematic absences as the obstacle to extending the method to
monoclinic and orthorhombic and leaves it unsolved. Our two constants (0.60,
0.0052) are exactly the paper's and reproduce its printed 13.39/17.24/21.32. What
the check *did* find is a defect nobody was looking for — the relation is a
least-squares **mean line** (−29 % to +32 % about a 10.6 % average), not the
upper envelope this package calls it, and used as a hard search ceiling it
excludes the true cell below a detection fraction of 0.713, which is that same
−29 %. See "Current focus" and [1030](wp/1030-engine-scaling-low-symmetry.md).
The precedent held, in other words, but not in the direction it was invoked for:
asking for the paper was right, and the thing it caught was a status claim rather
than a transposed coefficient.

**[1020](wp/1020-indexing-core.md) closed the same day** — five modules, 40
tests, an eleventh manual chapter, and **no engine**: the Q-space quadratic form
and its symmetry-allowed subspaces, weighted candidate refinement with an optional
shift column, Niggli/Delaunay reduction with two-opinion Bravais determination over
a tolerance sweep, the figure-of-merit **panel** scored in both directions, and
HNF derivative-lattice ambiguity with the reflections that would break each tie.
1021-1023 now have everything they share.  Full suite after all three WPs: 1251
passed / 70 skipped / 0 failed, including the `slow` real-data acceptance.

**Its lesson is about tests, not about crystallography: three of its four defects
passed the test that should have caught them.**

- The metric subspace was derived from the **transposed** rotations, and the
  dimension test passed. CLAUDE.md's "reciprocal-space action is Rᵀ" is about
  *hkl*; a tensor contracting with h twice is invariant under U → R·U·Rᵀ, and G\*
  is one. The transposed call returns the *direct* metric's invariants — the same
  dimension in every system, because the transposed set is a group too, so the
  WP's own acceptance criterion (1/2/2/2/3/4/6) was satisfied by the wrong
  subspace, with F = −A for hexagonal where the reciprocal metric has F = +A. What
  catches it is asserting the **true** metric lies in the span.
- A Gauss-Newton sign error that is locally correct: flipping only the θ block
  still solves for θ, and leaves the shift column with the wrong relative sign —
  s = −11.65 for an injected +0.05°.
- **M₂₀ was not invariant under a unimodular setting change, by 5 %**, because
  N_poss counts predictions up to the N-th observed line and that line *is* a
  prediction, so a strict comparison depends on fp rounding (N_poss 20 vs 19,
  M₂₀ 76.43 vs 80.45).
- And a perfect cell scored **M₂₀ = 0**: the figure divides by ⟨ΔQ⟩, which → 0 when
  a candidate fits within fp noise, so the obvious zero-guard ranked the right
  answer last. The mean is now floored at the median σ — a meaning rather than an
  epsilon, since a discrepancy below the measurement precision is not knowable, and
  per-line σ is what this package has and 1968 did not.

Two things it declined to do. **Four published figures of merit are not
implemented** — the Oishi-Tomiyasu reversed/symmetric de Wolff pair, WRIP20 and
McM₂₀ — because their formulas cannot be written from memory with correct
attribution, and guessing one while citing its paper is the WP-0501 b₂ failure in a
new costume; the panel's *argument* (coverage in both directions) is fully
implemented, which is what the measured §D result demands. And **1020 emits no
diagnostics at all**, deliberately: it has no answer to qualify, so
`INDEX_BRAVAIS_AMBIGUOUS` belongs to 1024 where a `CellCandidate` exists to carry
it.

1018's earlier value was already banked, and it is the v0.5 method result in
a new costume: **four defects, none of them visible by reading the code.** A
resolved Kα1/Kα2 doublet manufactured one spurious line per reflection (each
group is fitted independently *with its own full doublet*, so the Kα2 maximum
comes back as a real line — structural to per-group fitting, and any future
change to grouping must keep the alias filter); the first curvature seeder was
useless because differentiating twice amplifies noise by ~1/step², so a
per-channel-σ threshold passed essentially every noise dip; a shoulder seed
landing alone formed a *singleton* group that the ΔBIC gate never judged, so a
false positive became a line with an esd and no evidence; and
`background_envelope` is a rolling *low* quantile, ≈1.28σ below the true
background, which quietly turned a nominal 5σ detection threshold into ≈3.7σ.
Against that, the thing that *was* verified by reading — the analytic group
Jacobian — agreed with central differences to 2.5e-07 on every column first
time. Reading finds the algebra; only running finds the four above.

**A process note that outlasts the WP.** 1018, [1004](wp/1004-parameter-plan-api.md)
and [1006](wp/1006-run-control.md) were developed *concurrently in one working
directory*, and both other WPs' commits ran `git add -A` while 1018's files were
uncommitted — so `indexing/peaks.py`, `peakfit.py`, `pick.py`, `diagnostics.py`
and most of `schemas/indexing.py` are committed inside `f63556c`, `e46ead2` and
`62d6a76`, whose messages say WP-1004 / WP-1006. Nothing was lost and the tree
is green; the history was left interleaved deliberately, because the swept files
sit *inside* those commits, so untangling means surgery on three already-closed
WPs' commits to fix a comment in `git log`. **`git log -- src/pxrdref/indexing/`
will mislead you — start from `068149e`.** The rule this buys: one `git worktree`
per concurrent session, or only one session commits.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1018](wp/1018-peak-picking.md) | Peak picking: detection + full per-peak profile fitting | ✅ 2026-07-30 | — |
| [1019](wp/1019-indexing-data-quality.md) | Data-quality gate and the systematic-error model | ✅ 2026-07-30 | 1018 |
| [1020](wp/1020-indexing-core.md) | Indexing core: Q-space, reduction, Bravais, FoM panel, ambiguity | ✅ 2026-07-30 | 1018 (1019 soft) |
| [1021](wp/1021-engine-dichotomy.md) | Engine A — successive dichotomy | ✅ 2026-07-30 | — |
| [1022](wp/1022-engine-trial-error.md) | Engine B — index-heuristic trial and error | ✅ 2026-07-30 | — |
| [1023](wp/1023-engine-montecarlo.md) | Engine C — whole-profile Monte Carlo (spike, then decide) | 🛑 no-go 2026-07-30 | — |
| [1024](wp/1024-indexing-consensus.md) | Consensus, `index_pattern`, Le Bail validation, agent & CLI | ✅ 2026-07-30 | 1021–1023 |
| [1025](wp/1025-extinction-symbol.md) | Extinction symbol / space-group determination | ✅ 2026-07-30 | 1024 |
| [1026](wp/1026-indexing-acceptance.md) | Acceptance: bethanechol benchmark + known cells | ✅ | 1024 (1025 soft) |
| [1027](wp/1027-gui-peak-picker.md) | GUI peak picker + indexing panel | ✅ 2026-08-01 | 1010, 1011, 1018–1024 |
| [1030](wp/1030-engine-scaling-low-symmetry.md) | Engine cost at low symmetry + the two missing figures of merit | ✅ 2026-07-31 | 1020–1022 (1026 soft) |
| [1037](wp/1037-indexing-time-ceiling.md) | Indexing: a stated time ceiling and honest progress | ✅ 2026-08-04 | 1024 (1021, 1022 soft) |
| [1038](wp/1038-shift-reflection-pairs.md) | Pre-indexing 2θ shift from reflection pairs | ✅ 2026-08-04 | 1019, 1024 |
| [1039](wp/1039-search-line-count.md) | Which lines a search is driven by (was: how many) | ✅ 2026-08-05 | 1037 (1038 soft) |
| [1040](wp/1040-engine-svd-index.md) | Engine C (second attempt): SVD-Index | 🔄 2026-08-05 — landed; zero-error column + scoreboard open | 1020, 1024 (1038 soft) |
| [1041](wp/1041-indexing-benchmark-gallery.md) | The indexing benchmark gallery | 🔄 2026-08-05 — dedup key + renderers landed; aggregate and benchmark open | 1026 |
| [1042](wp/1042-anytime-results-quick-default.md) | Anytime results, and `quick` as the default | ⬜ | 1037 |

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1028](wp/1028-robustness-external-data.md) | Robustness on data and CIFs we did not author | ⬜ | — (1007 soft) |
| [1036](wp/1036-crystal-system-settings.md) | Crystal-system cell ties: the settings the tables do not check | ✅ 2026-08-04 | — |

**1036 came from a GUI question and was not a GUI WP.** The cell ties assumed
b-unique monoclinic and hexagonal axes for R groups, and held a symmetry-fixed
angle at its *stored* value rather than at 90°/120°. Its task 1 was the sweep
that decided how much that mattered, and **the answer went both ways**: zero of
28 existing inputs reach a broken branch, so nothing shipped moved — but all
three are reachable from a plain CIF, because `read_small_structure` picks the R
setting from the **cell**, not from the symbol. The draft premise that a bare
`R -3 c` always resolves to `:H` was wrong, and measuring it is what caught
that. The lesson to carry: the free-parameter *count* was correct in every
broken case, so the degrees-of-freedom test guarding this had been passing on
the wrong subspace — WP-1020's transposed-rotation trap, one rank down.

**1028 came from outside.** Every item in it was hit by driving the package
end-to-end over nine unfamiliar refinement targets from a third-party paper
(branch `wpem-benchmark`, pushed and deliberately **not** merged), and none of
it was found by reading the code: a species-string syntax that rejects 6 of 11
COD entries, a 2.35 PiB allocation in `generate_reflections`, `status =
"converged"` at Rwp = 7 225 %, a stage that burns 4 600 solver evaluations and
still reports success, March-Dollase returning inf/NaN when `r` underflows past
a bound meant to prevent exactly that, and `compute_qpa` raising where it should
diagnose. The first was filed as a **reach regression from WP-1001** and, as
measured on 2026-07-30, is not one: `scattering.normalize_species` carries the
same regex, has been on the compile path since v0.1, and rejects the same two
forms — so those CIFs never loaded. Making dispersion the default moved the
raise up one line and changed its wording; the fix has to satisfy both lookups
(WP-1028 §(a)). Robustness against strangers' files is not a feature the
existing suites can test, because they only ever read files we chose — and the
benchmark that found these measured every *failure* but reasoned one *cause*,
which is its own lesson about reading a diff for an attribution.

Three decisions worth keeping visible, because each is a place the obvious
implementation is wrong:

- **Three engines, and the confidence is their agreement.** Both source papers
  conclude that no single indexing program wins and that running several is
  what raises the success rate — which is the device this package already uses
  for correctness elsewhere (`direction="both"` flagging
  `SEQUENTIAL_PATH_DEPENDENT`, the per-column cross-backend Jacobian matrix).
  The engines share only the Q form and the tolerance model.
- **Coverage is scored in both directions, and that is measured, not
  aesthetic.** On the guiLLeMot MnSb_34 screen, ranking on share-of-observed-
  intensity alone puts a 390-line phase first with 9 % of its own lines
  present, above the truth at 56.5 %. A cell that indexes everything and
  predicts a forest is the classic false positive and one number cannot see it.
- **A restricted search is never a verdict about the sample.** Measured on the
  same branch: a two-parameter engine scores 47–60 % on single-phase
  orthorhombic/monoclinic patterns and 82–100 % on genuinely
  tetragonal/hexagonal ones, so a real mixture at 69 % sits in the overlap —
  and a "at least two phases" claim built on that ambiguity was **withdrawn**.
  Hence `systems_searched` on the result, and `INDEX_SYSTEMS_NOT_COVERED`.

Prior art lives at the annotated tag **`guillemot-study`** (commit 97ba88d, also
on branch `guillemot-example-refinements`): `studies/guillemot/index_hl2.py` is
engine B in miniature, `audit_tools.py` measured the findings above, and
`out/HL2-1_peaks.txt` is 74 peaks from a genuinely unidentified pattern — the
acceptance fixture whose correct answer is "we do not know".

**It is not merged into `main` and does not need to be** — `git show
guillemot-study:studies/guillemot/<file>` reads any of it without a checkout.
The tag is what guarantees that stays true if the branch is ever pruned.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1050](wp/1050-suggest-next-parameter.md) | `Refinement.suggest()`: which parameter to free next | ⬜ | — (before 1003 if frozen) |
| [1051](wp/1051-sequential-escalation.md) | Sequential escalation ladder + chain hygiene | ⬜ | — |
| [1052](wp/1052-report-loop-eval.md) | Closed-loop FitReport usefulness eval (mechanical) | ⬜ | — |
| [1053](wp/1053-agent-in-the-loop-eval.md) | Agent-in-the-loop report eval (refine_json) | ⬜ | 1052 |

**1050/1051 came from a literature review** (2026-07-30, Toby 2024 *J. Appl.
Cryst.* **57**, 175 and Tian 2013 *J. Appl. Cryst.* **46**, 255 — SrRietveld).
1050 is Toby's worst-fit-parameter mechanism made strictly stronger by what
this package has and GSAS-II lacks: reusable analytic Jacobian columns (his ±δ
FD, per-type δ heuristics and sign test all collapse into one Gauss-Newton
score gain), plus collinearity gates so his own stated failure mode comes back
as an unresolved group, never a confident singleton. 1051 is the one part of
SrRietveld not already superseded here: its diverge-then-escalate scheme,
which our chain has only two leaky rungs of — including a measured hygiene
defect where a doubly-diverged pattern still seeds its successor. The review's
third adoption, weighted Δ/σ difference curves as the default Rietveld panel,
was small enough to land directly (commit `732535d`).

**1052/1053 (2026-08-05) measure the other half of 1050's bargain**: if the report
and `suggest()` only *inform* a caller (the no-autopilot fence), then whether
following them actually converges a fit is a measurable claim — 1052 runs the
AGENT_PROTOCOL §9 loop mechanically in CI, 1053 puts real models behind the shipped
`refine_json` surface and scores them on the same planted-cause episodes.

## v2+ (seams pre-built, implementations fenced out)

Fundamental Parameters Approach as a differentiable convolution stack
(Cheary-Coelho 1992); neutron CW; TOF (new Source/Profile implementations
behind the frozen seams); spherical-harmonics texture (Von Dreele 1997);
rigid bodies; MCP server wrapping `refine_json`; internal-standard/amorphous
QPA; `vmap`-batched in-situ series; notebook widgets. *(The human GUI was
un-fenced from this list into v1.0 on 2026-07-29 — WP-1004…1017; grounds in
[DESIGN.md](DESIGN.md#locked-decisions).)*

Fenced **by** the v1.0 indexing WPs (1018…1027, 2026-07-29), i.e. deliberately
left undone by work that could plausibly have grown to include them:
multi-phase indexing (index the residual after subtracting a solved phase);
search-match phase identification, whose prior art is the 36-cell screen at
`guillemot-study:studies/guillemot/match_hl2.py`;
the full Bayesian extinction-symbol posterior (Markvardsen et al. 2001 — the
ΔBIC/Hamilton nested comparison is the v1.0 form); a fourth engine in the
Conograph topograph lineage (Oishi-Tomiyasu's reversed/symmetric M_N *is* in
scope, as a figure of merit); derivative-lattice ambiguity above index 4; and
structure solution from an indexed cell.

No WP files for v2+ on purpose — the fence is a scope-discipline decision
([DESIGN.md](DESIGN.md#locked-decisions)), and pre-writing packages invites
scope creep.

One note against the day that fence is revisited: **`vmap`-batched in-situ series
is the only accelerator story this package's hardware supports**, and WP-0408
measured its size. A device breaks even at ≈50-65 k elements per kernel and tops
out at **≈2.5-3×** — the work is memory-bound, so that ceiling is not a tuning
problem. One batched pattern is 17-121 k elements, so the plateau needs ≈10
(synchrotron) to ≈60 (lab) patterns processed together. Worth having for a
series; worth nobody's time for a single pattern, which is below break-even even
after batching.
