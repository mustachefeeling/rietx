# rietx — Roadmap

Canonical milestone **index**. The content that used to live here is split so
a work session loads only what it needs:

- **[skill/rietx/](skill/rietx/SKILL.md)** — the agent skill: how to *use* the package as an
  automated operator: turn-on order, degeneracies, abstention handling,
  diagnostic-code semantics, and the measured findings that change agent
  behaviour. Written for consumers, not maintainers; a WP that adds a
  diagnostic code or a correction should add its row there.
- **[DESIGN.md](DESIGN.md)** — the design record (rationale, locked decisions,
  invariants). Stable; read the specific section a work package links.
- **[milestones/](milestones/)** — shipped-milestone records with the measured
  acceptance blocks (`v0.1.md`, `v0.2.md`, …).
- **[wp/](wp/)** — one self-contained **work package (WP)** per task. Each has
  its own context, commit-sized checklist, acceptance command, and handover
  log. `wp/TEMPLATE.md` defines the format.
- **[RELEASING.md](RELEASING.md)** — how a version reaches PyPI, and the rule
  that it never goes by hand. Supersedes WP-1003's by-hand upload checklist.

## Session protocol

1. **Start** from "Current focus" below (or the WP the user names). Read that
   one WP file — self-contained on top of CLAUDE.md. Open DESIGN.md only at
   sections the WP links; do not read other WP files. `/wp-start` encodes
   this.
   **On arrival at a WP, prune its `### Inherited` first**: fold still-true
   entries into Context or Tasks, delete stale ones (say why in your handover
   entry). The section is a mailbox, emptied on every visit and deleted —
   fully consumed — when the WP closes.
2. **During**: land tasks as small commits prefixed `WP-NNNN:`; check items
   off in the WP file as they land.
3. **End** — or whenever interruption threatens — run `/wp-handover`. The
   checklist it carries: dated handover entry prepended (newest first, in one
   of `wp/TEMPLATE.md`'s two forms, opening with a plain-language paragraph on
   what the work *means* and closing on the next actions, working detail
   between), Status line and the index-row glyph below synced, forward
   references pushed into the `### Inherited` of any affected WP that is not
   closed and not yours (a handover log reaches only your own successor on the
   same WP), rule 4 applied to anything this session wrote into a CLAUDE.md,
   working tree clean and pushed, and the branch's pull request opened or
   updated — a session is not handed over until its work is reviewable, and
   merging stays the maintainer's. A missed handover is detected at the next
   session start (`.claude/hooks/session_start.py`, two rules: the WP file
   older than the work, or the log older than the commits) and repaired first.
4. **A CLAUDE.md takes rules, not findings.** A line enters a CLAUDE.md
   (root, `gui/`, `tests/`, `src/rietx/indexing/`) only as a standing rule
   a stranger needs in six months — a few lines, evidence compressed to one
   clause plus a pointer to the WP or milestone record that holds the
   measurement. Counts and timings a session measures go in its WP handover
   entry (root CLAUDE.md § Numbers holds the *recipe*; the dated history is
   the v1.0 appendix diary).
5. **WP closes** (✅/🛑): rewrite "Current focus" for the successor and MOVE
   the outgoing narrative to the in-flight milestone record
   (`milestones/v1.0.md` § "How v1.0 is getting here"). Current focus stays
   within `CURRENT_FOCUS_CAP` (tests/test_docs_consistency.py) and repeats
   nothing a closed WP's own file already says.
6. **Milestone ships**: finish `milestones/vX.Y.md` with the measured
   acceptance block, flip the milestone row here, check README's claims.

`tests/test_docs_consistency.py` enforces the mechanical parts: status
vocabulary and glyph sync, Inherited placement, link resolution, and the
size caps on this file and CLAUDE.md.

## Current focus

**v1.2 shipped 2026-08-28** ([record](milestones/v1.2.md), [notes](releases/1.2.0.md)): the GUI is documented, out of beta and no longer a thing a first-time crystallographer has to be taught around; all six acceptance rows are met and the eighteen WPs are the maintainer's own use notes, 1201-1217 plus [1017](wp/1017-gui-manual-onboarding.md), the manual, last. Four rules outlived their panels. **A vocabulary a document is *about* can be partitioned even when its prose cannot be checked**: the GUI's 77 routes and its nine panels are documented-or-excluded the way `tests/api_surface.py` partitions the call surface, tightening both ways — a chapter naming a route the server does not serve is WP-1037's bug pointed at the reader. **Where no python object knows the fact, the authorities swap**: nothing in the package knows the panels exist, so the tab strip is data in `gui/src/lib/tabs.ts`, vitest writes the corpus and pytest reads it. **A screenshot is generated or it is a lie with a timestamp.** And **a count in prose rots exactly like a retuned threshold**, so a count is injected rather than typed. The release carries what landed beside the milestone as well — constant-wavelength neutrons, declared background peaks, the two-tier strain/size caps and three GSAS reader repairs — and `releases/1.2.0.md` § Upgrading is the authority for all of it. What v1.2 does not cover, unchanged: 47 authored tooltips in eleven files, each owed a corpus arm; the residual subplot's empty quarter (1212 measured it and decided against collapsing); and the phase's corrections, which no form offers because offering one is offering to declare it.
**v1.3 — agents and programs** is in flight ([record](milestones/v1.3.md), 1301-1307 filed 2026-08-28): the agent surface refactored against two measured runs rather than intuition. Six shipped, each with its own narrative in the record. [1301](wp/1301-hold-unsupported-phase.md) holds an unsupported phase's structural parameters for the stage rather than bounding them, its scale left free so it can still appear. [1302](wp/1302-error-is-documentation.md) makes the error the documentation — a wrong name answers with the right one — and gives a result a termination view answering "done or not, and why" in one call. [1303](wp/1303-retire-refine-json.md) deletes `rietx.agent`, so there is **one** integration surface and it is the python API: four traced rounds recorded zero calls of the JSON envelope from any agent with a choice. [1304](wp/1304-protocol-as-skill.md) makes the protocol a **skill** in the open agentskills.io format, on the rule its own cap taught — **a lookup leaves the body, a rule and its decisive number stay**. [1305](wp/1305-series-deliverable.md) (2026-08-29) fills §4b's hole with the deliverable the ramp run actually had, **a parameter against a series axis**: four `SEQUENTIAL_*` and `PHASE_UNCONSTRAINED` rows named as stopping criteria for the first time and printed by `SeriesResult.summary(deliverable="series")`, plus the two no diagnostic can supply — a stated 2θ-scale anchor and the precision/accuracy split. With it, `suggest` says whether a parameter *pays* for itself (`CandidateGroup.delta_bic`, and `Refinement.summary()`'s `next:` line is that number) and a flagged step checks itself against an independent cold pair at +5 % of a 68-pattern chain. [1306](wp/1306-powderline-recipe.md) (2026-08-29) makes this package an engine a **PowderLine** pipeline can dispatch to — `read_recipe` / `write_recipe_tables`, every unit measured against the reference output before the reader was written and the one row the format states two ways refused rather than picked. Its fixtures were worth more than its format: each carries **two** reference engines, they differ by 2665 ppm on a cell where the FAP band is 300, and the rule that follows is **two references are an envelope, not a second tolerance** — across engines the cells are comparable and the broadening coefficients are not. rietx lands 11-93 ppm from TOPAS on all five free cell parameters. `SCHEMA_VERSION` walked 0.10 → 0.14 over the six and `capabilities().features` gained two keys; `docs/releases/1.3.0.md` § Upgrading is the authority for every step. [1307](wp/1307-recapture-round-1-1.md) (2026-08-29) closed the block by measuring it: round 1.1, eight cells over two episodes and two models, $38.39. **Seven of eight runs stopped on a §4b deliverable row**, against zero in the 86-run campaign, and every reel cell made WP-1305's three checks as calls where the baseline agent made them by hand. Three results outlive the round. **A surface can look unreached because no episode posed its question** — `help_for` went 0 of 4 on the synthetic ramp and 4 of 4 on the reel, which is the episode that hands an agent a foreign model file. **`read_recipe` was reached by nothing and named by nothing** in the one episode shipping a `.inp` — and re-reading the skill says why: it appears in one file, inside the `RECIPE_*` diagnostic rows, behind a diagnostic that cannot fire until it has been called, and in neither `SKILL.md` nor `references/api.md`. A **coverage** failure of 1304's artefact, not a discovery failure by four agents, and the round's clearest action item. And both `opus-5` cells independently found that `background.worst_absorption` is the only report row separating a good fit from one handing 40-96 wt % to an absent phase at equal Rwp — the background-flexibility invariant rediscovered from data by agents told none of it — a row §4b carries under **QPA** and omits from **Trajectory**, which is the deliverable a series task names — and `references/series.md` never says "background" at all — so three of four found it by leaving their own deliverable for the QPA one. **Next: ship v1.3** — all seven WPs are done; the release notes and the milestone's acceptance block are what remain. Round 1.2 owes a sealed workspace before any `bare` cell is read as an access claim. Free-standing peaks (1101-1103) stay at **v1.4**.

**v1.1 shipped 2026-08-23** ([record](milestones/v1.1.md), [notes](releases/1.1.0.md)): the trigger-shaped cold fit 50.11-50.43 → 5.69-5.72 s and the 10-pattern warm series 266.78-269.61 → 49.24-49.30 s, each WP with its own equivalence bar and none an Rwp comparison. Three consumer-visible changes rode with it: numba as a core dependency (`RIETX_COMPILED=0` is the way out), intermediate stages at `ftol=1e-6` (`intermediate_ftol=None` is bit-identical), and the ladder's first rung bounded at `first_rung_factor=3.0`. **1.0.2 was folded in and never published**, so an upgrade from 1.0.1 crosses both and 1.1.0's § Upgrading is the authority. Two speed fronts stay unowned and recorded: the per-reflection 19.4 % and the `refit=` choice (50 % of the trigger series wall is still discarded ladder rungs).

**The promise is a preview** ([1117](wp/1117-compatibility-promise.md), `docs/manual/using/compatibility.md`): anything may change in any release; a consumer-observable change bumps its contract's last component by one, the reason beside the constant. Documenting a name gates arrival (the partition, [1076](wp/1076-result-row-honesty.md), [1078](wp/1078-indexing-provisional.md)); it no longer freezes it.

Parked, none of it blocking: the 1.0.0-release-notes promises (`.rex` zip transport, and `RefinementState.excluded_regions` with `replay` honouring them, 1003 §B); the post-1003 indexing work (narrow the acceptance fixtures' search, and the `grade` prior-counting change, 1046 §4); the model-cost estimate (1110's ask, priced in 1113 § Findings); [1118](wp/1118-foreign-model-files.md), [1119](wp/1119-named-variables.md), [1130](wp/1130-background-reference.md), [1131](wp/1131-sample-broadening-is-a-specimen-property.md) and [1133](wp/1133-diagnostic-names-its-view.md), unscheduled — 1130 reviewed 2026-08-27 and restructured behind 1131; and the LaB6+cBN correlation test's **Linux-only red**, which has never had a green run there and is a disagreement about which parameters a degenerate fit's guard names ([v1.2 record](milestones/v1.2.md) § Appendix — acceptance at ship).

## Milestones

| Milestone | Scope | Status | Acceptance |
|---|---|---|---|
| v0.1 | Vertical slice: synchrotron CW, Rietveld + Le Bail | ✅ **shipped** ([record](milestones/v0.1.md)) | 11-BM NAC: a = 10.251285(12) Å, Rwp 9.2%, CaF₂ impurity auto-flagged |
| v0.2 | Lab diffractometer + FitReport attribution + viz | ✅ **shipped 2026-07-22** ([record](milestones/v0.2.md)) | SRM 660c LaB6: a = 4.156895(25) Å (+28 ppm vs NIST value for this dataset, Bérar-Lelann-inflated esd), Rwp 8.7%; GSAS-II FAP tutorial: Rwp 9.73% vs GSAS's 10.05% on identical channels, cell +116 ppm (uniform d-scale convention offset) |
| v0.3 | Multi-phase QPA, Pawley, aniso ADPs, multi-histogram | ✅ **shipped 2026-07-24** ([record](milestones/v0.3.md)) | SRM 676a corundum: c/a +30 ppm vs certificate (absolute axes −313/−283 ppm, uniform d-scale); IUCr round robin: sample-1 worst 5.1 wt% (traces ≤1.3), sample 2 worst 2.9 wt% with brucite March-Dollase r=0.67, sample 4 characterised as the designed Brindley failure (µR fence fires) |
| v0.4 | Differentiable backends: JAX jacfwd, mixed precision, torch-MPS; true Voigt; restraints | ✅ **shipped 2026-07-27** ([record](milestones/v0.4.md)) | Cross-backend Jacobian agreement (analytic/FD/jax/torch × 8 configs + multi-histogram + stage boundaries) inside the 5e-3 rel-L2 fp64 bar; an all-fp32 Apple-GPU refinement of SRM 676a lands Δa = −3.5e-8 Å from numpy fp64 (bar 3e-5); wall-clock reported, not gated — and it is a *finding*: MPS is 46-182× slower (launch-latency-bound) and jit'd jacfwd is within 2.1× of the analytic assembly at best, so the batched peak loop is a numpy-path win (WP-0605), not GPU enablement |
| v0.5 | Corrections & microstructure (absorption, Stephens, f′f″) | ✅ **shipped 2026-07-28** ([record](milestones/v0.5.md)) | capillary absorption validated at **both** levels: the Rouse (1970) cylinder factor against a quadrature of the exact ITC eq. (6.3.3.4) integral across 0 ≤ µR ≤ 1 *and* 0 ≤ sin²θ ≤ 1 (0.0035, the paper's own bound), and on real 11-BM SRM 660a LaB₆ data in a documented 0.81 mm bore — Rwp moves 3e-8, the cell 8e-12 Å, and *both* Biso move by the predicted 0.0166542 Å². Plus the two accuracy wins no fit statistic shows: dispersion takes the round-robin QPA error from RMS 2.26 → 0.69 wt %, and a mis-declared flat-plate thickness biases Biso by up to −1.5 Å² |
| v0.6 | TOPAS-style bounded LM, agent surface, batched peak loop, theory manual | ✅ **shipped 2026-07-29** ([record](milestones/v0.6.md)) | bounded LM 0.74–1.04× vs scipy TRF (CPU — the expected Amdahl tie), identical minima on 2/3 protocols, ΔBIC −13 on the third, and the Stephens cone enforced as a linear inequality (brucite 12/43 → 0/43 outside, at higher Rwp); FCJ node memo 1.23× bit-identical; agent schema generated from live registries with a registry-membership meta-test; theory manual builds `-W`-clean with every fenced constant injected from the live package and five anti-divergence guards in the fast suite |
| v1.0 | Hardening, human GUI, indexing, API freeze, PyPI | ✅ **shipped 2026-08-16** ([record](milestones/v1.0.md)) | full suite green at ship: 2509 passed / 126 skipped locally (`[dev]`, macOS) and CI-green on Linux `[dev,jax]` (run 31966606174, full job 1h57); GUI end-to-end and the bethanechol individual-program grading landed by their WPs (record § Acceptance); repo public with six required checks gating `main`; manual + AGENT_PROTOCOL at yue-here.github.io/rietx, all URLs verified; `rietx` 1.0.0 on PyPI, fresh-venv install + `capabilities()` verified from the index; Windows fast suite green as the classifier's pre-upload gate — a gate that caught three real defects (CRLF-unstable checkouts, an SO_REUSEADDR double-bind in the GUI server, cp1252 example pipes) before the irreversible step |
| v1.1 | Refinement speed: seconds not minutes | ✅ **shipped 2026-08-23** ([record](milestones/v1.1.md)) | trigger-shaped cold fit **5.69-5.72 s** against the milestone's opening **50.11-50.43 s** (8.8×) and the 10-pattern warm series **49.24-49.30 s** against **266.78-269.61** (5.4×), best-of-3 idle, darwin/arm64 `[dev]`; seven of nine warm patterns at 0.88-2.33 s (median 2.02) with two at 10.53/20.26 — the ~1 s band **met on the maintainer's judgement and recorded mis-specified**, judged on the per-pattern table as WP-1124 required; stretch (cold < 1 s) **measured unreachable** and recorded as such; every landed WP with its equivalence bar, never an Rwp comparison |
| v1.2 | The GUI for a crystallographer: house style, one help mechanism, onboarding, the panels a first-time user meets | ✅ **shipped 2026-08-28** ([record](milestones/v1.2.md)) | all six rows met on the release tree: one token layer and nine control registers with no size at a call site; one help mechanism over a 119-entry corpus crossed against the live vocabularies both ways, its 47 remaining authored titles a per-file budget that fails both ways; a project created from a blank state four ways in a real browser (a shipped example, browse, a typed cell, no structure at all); zero axis movement on hover, tab change and a whole exclude drag, 4 → 1 reacts per drag; refine flags, typed coordinates and a saved instrument profile in the Model panel; and the manual guarded by two partitions (77 routes, nine panels), 18 generated screenshots and a generated glossary — suite counts in the record's ship appendix |
| v1.3 | Agents and programs: the termination view, the hold, the skill, the interchange format | 🔄 **in flight** ([record](milestones/v1.3.md), opened 2026-08-28) | — |
| v1.4 | Free-standing peaks: fit_peaks + the extra-components seam | ⬜ queued | — |
| v2+ | FPA (**with** the peaks buffer — [1122](wp/1122-compiled-peaks-buffer.md) measured it below break-even without one), neutron **TOF** (CW landed, WP-1134), texture, MCP server | ⬜ fenced | — |

## Work packages

WP numbers are milestone-blocked (MMNN): a new WP takes the next number in
the block of the milestone it targets — v1.1 → 11xx. The v1.0 block ran past
its milestone (1069–1078 are post-1.0 work); rule written down 2026-08-18.
A retired number is never recycled.

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

(0603 — the torch/MPS backend — moved to v0.4 as [0408](wp/0408-torch-mps-backend.md)
on 2026-07-24; the number is left unused so the history stays readable.)

### v1.0 — hardening, human GUI & release (GUI WPs added 2026-07-29)

Order: backend API first (1004–1007, each independently useful without the
GUI), then server (1008–1009), then frontend (1010–1016); the freeze (1003)
is the milestone's last row so it covers a surface the GUI has exercised.
Both docs WPs (1017, 1067) are post-v1.0 — see that section below.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1001](wp/1001-validation-matrix.md) | Validation matrix + tolerance policy | ✅ 2026-07-29 | — |
| [1002](wp/1002-ci-matrix.md) | CI matrix | ✅ 2026-07-29 | — |
| [1004](wp/1004-parameter-plan-api.md) | Parameter & plan API surface | ✅ 2026-07-30 | — |
| [1005](wp/1005-project-container.md) | Project container (`.rex/`) | ✅ 2026-07-30 | 1004 |
| [1006](wp/1006-run-control.md) | Run control: streaming, progress, cancellation | ✅ 2026-07-30 | — |
| [1007](wp/1007-capabilities-guards.md) | Capabilities, structured guards, background export | ✅ 2026-07-30 | 1004 |
| [1008](wp/1008-gui-server.md) | GUI server, session model, `rietx gui` | ✅ 2026-07-30 | 1004–1007 |
| [1009](wp/1009-textdoc-format.md) | Project text document (`.rxt`): format + parser | ✅ 2026-07-30 | 1004, 1005 |
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
| [1031](wp/1031-docs-consolidation.md) | Planning-doc consolidation + handoff mechanization | ✅ 2026-07-31 | — |
| [1003](wp/1003-api-freeze-pypi.md) | API freeze + PyPI | ✅ 2026-08-16 — two-strength freeze written and bound; repo public + CI gating + un-shaping as one change; Pages hosting; 1.0.0 uploaded after the Windows gate caught three real portability defects | 1001, 1002, 1004–1036 **except 1017** (deferred), 1067 § Floor |

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
| [1026](wp/1026-indexing-acceptance.md) | Acceptance: bethanechol benchmark + known cells | ✅ 2026-08-08 — criterion 1 generated: global **−8** of ±20 (ties DICVOL91), runner beside the gallery | 1024 (1025 soft) |
| [1027](wp/1027-gui-peak-picker.md) | GUI peak picker + indexing panel | ✅ 2026-08-01 | 1010, 1011, 1018–1024 |
| [1030](wp/1030-engine-scaling-low-symmetry.md) | Engine cost at low symmetry + the two missing figures of merit | ✅ 2026-07-31 | 1020–1022 (1026 soft) |
| [1037](wp/1037-indexing-time-ceiling.md) | Indexing: a stated time ceiling and honest progress | ✅ 2026-08-04 | 1024 (1021, 1022 soft) |
| [1038](wp/1038-shift-reflection-pairs.md) | Pre-indexing 2θ shift from reflection pairs | ✅ 2026-08-04 | 1019, 1024 |
| [1039](wp/1039-search-line-count.md) | Which lines a search is driven by (was: how many) | ✅ 2026-08-05 | 1037 (1038 soft) |
| [1040](wp/1040-engine-svd-index.md) | Engine C (second attempt): SVD-Index | ✅ 2026-08-05 — landed with the zero-error column; scoreboard re-measured in 1041 | 1020, 1024 (1038 soft) |
| [1041](wp/1041-indexing-benchmark-gallery.md) | The indexing benchmark gallery | ✅ 2026-08-05 — PNGs on every row, scoreboard generated (9: 6/2/1/0), contamination curve, aggregate refuted | 1026 |
| [1042](wp/1042-anytime-results-quick-default.md) | Anytime results, and `quick` as the default | ✅ 2026-08-07 | 1037 |
| [1043](wp/1043-agent-and-human-indexing.md) | Indexing for an agent and for a human: report, don't refuse | ✅ 2026-08-07 | 1041, 1026 (1028 soft) |
| [1045](wp/1045-indexing-search-controls.md) | Indexing search controls: one surface for the GUI and the agent | ✅ | 1027, 1042 (1043 soft) |
| [1046](wp/1046-candidate-cap-before-ranking.md) | The per-engine candidate cap decides the ranking | ✅ 2026-08-09 — reported cap applied once by consensus, `corroborated` the first ranking key | 1024 (1026 soft) |

### v1.0 — cross-cutting, found by use

Neither indexing nor GUI: gaps that surfaced from driving the package over
files, CIFs and figure conventions we did not author. Close narratives, and
the `guillemot-study` prior art 1028 rests on, are in the
[v1.0 record](milestones/v1.0.md).

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1028](wp/1028-robustness-external-data.md) | Robustness on data and CIFs we did not author | ✅ 2026-08-07 | — (1007 soft) |
| [1036](wp/1036-crystal-system-settings.md) | Crystal-system cell ties: the settings the tables do not check | ✅ 2026-08-04 | — |
| [1047](wp/1047-vendor-pattern-formats.md) | Vendor pattern formats: read the files labs actually have | ✅ | 1005, 1007, 1014 (1009, 1028 soft) — before 1003 |
| [1075](wp/1075-static-panel-conventions.md) | The static panel takes the house figure conventions | ✅ 2026-08-16 — layout, palette, axes and scales; the raw difference is the default and the rows moved below it | — (before 1003: four new `plot_result` keywords) |

### v1.0 — report evidence, agent evals, and the rename

What a report has to say for a caller to act on it, measured against real
agents rather than asserted — then the two renames, which ran early because
the freeze covers names that embed the brand.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1050](wp/1050-suggest-next-parameter.md) | `Refinement.suggest()`: which parameter to free next | ✅ | — (before 1003 if frozen) |
| [1051](wp/1051-sequential-escalation.md) | Sequential escalation ladder + chain hygiene | ✅ 2026-08-09 — three rungs, keep-best; a diverged pattern seeds nothing and joins no median | — |
| [1052](wp/1052-report-loop-eval.md) | Closed-loop FitReport usefulness eval (mechanical) | ✅ 2026-08-11 — the §9 loop runs closed in CI; recovers what separates, refuses what does not, `src/` untouched | — |
| [1053](wp/1053-agent-in-the-loop-eval.md) | Agent-in-the-loop report eval (refine_json) | ✅ 2026-08-11 — 48/48-run pilot: A/B null on outcomes; the bottleneck is when the report is read, not what it says | 1052 |
| [1054](wp/1054-abstained-branch-honesty.md) | Layer-2 honesty on the abstained branch (phantom-phase invitation) | ✅ 2026-08-12 | — |
| [1055](wp/1055-background-evidence.md) | Background evidence in the FitReport | ✅ 2026-08-12 — both failure modes in `FitReport.background`; the over-flexible fixture wins on Rwp and GoF and lands 2.6× further from truth | — |
| [1056](wp/1056-identifiability-layer.md) | Identifiability layer: correlations, soft modes, held-parameter exchangeability | ✅ 2026-08-12 — a converged report names the zero↔displacement exchange; R² is design-matrix-identical on the clean control, the partner's 128σ-vs-1.6σ discriminates | — |
| [1057](wp/1057-purpose-grade-evidence.md) | Purpose-grade evidence: Le Bail gap + protocol stopping criteria | ✅ 2026-08-12 | — |
| [1058](wp/1058-report-delivery.md) | Report delivery: the per-stage report trajectory | ✅ 2026-08-13 | — |
| [1059](wp/1059-eval-round-two.md) | Agent eval round 2: protocol v1.1 re-A/B | ✅ 2026-08-13 | 1054, 1056, 1057, 1058 |
| [1062](wp/1062-rename.md) | Rename the project to `anatase` (superseded by 1066) | ✅ 2026-08-12 — ~300 files; formats decoupled from the brand (`.rex`/`.rxt`), audit test greps the old token | — (blocked 1003) |
| [1063](wp/1063-exchange-clause-and-rivals.md) | Fit-level exchange clause + `compare_rivals`: name the swap, ship the experiment | ✅ 2026-08-13 — THRESHOLDS_VERSION 0.8; the miner puts the clause in context before the ridge in 6 of the 7 cells | 1056, 1059 (before 1003) |
| [1064](wp/1064-eval-round-three.md) | Agent eval round 3: measured epistemic truth, decision-grade scorer, python arm | ✅ | 1063 |
| [1065](wp/1065-decisive-swap-license.md) | What a decisive swap licenses: the follow-through sentence, measured on the row it failed | ✅ | 1063, 1064 (before 1003) |
| [1066](wp/1066-rename.md) | Rename the project to `rietx` | ✅ 2026-08-14 — 363 files, zero numbers moved; format tokens survived a second rename; no WP filename may carry a brand token | 1062 (blocked 1003) |

### v1.0 — the repo's own process (added 2026-08-06)

From a measured review of how this repo works, not of what it computes: the
docs were ballooning, CI paid twice per merged PR, and the handover was
*remembered* rather than enforced.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1060](wp/1060-docs-ci-consolidation.md) | Docs/CI consolidation: trim what the evidence indicts | ✅ 2026-08-06 | — |
| [1061](wp/1061-workflow-robustness.md) | Session-workflow robustness: detect the missed handover | ✅ 2026-08-06 | — |

### Post-v1.0 — the docs WPs (1067 spans the release), and what they found

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1067](wp/1067-user-api-manual.md) | User & API manual (Part 1), beside the theory manual (Part 2) | ✅ 2026-08-18 — § Floor landed and unblocked 1003; the McCusker set's pass landed (Part 2 took its four equations, `using/results.md` split off, restraints documented, three figures); ten 1.0.x chapters landed (`data`, `model`, `refining`, `history`, `indexing`, `series`, `qpa`, `exports`, `cli`, plus second passes on `agents` and `report`), two planned chapters were deleted by measurement and one line grew from three commands to five; closed when [1076](wp/1076-result-row-honesty.md) emptied the `deferred-1.0.x` bucket — the derived surface is documented-or-excluded end to end, **1322 of 1322** | 0604, 1004–1007, 1047 |
| [1068](wp/1068-manual-second-pass.md) | Part 1 second pass: voice, figures, structure | ✅ 2026-08-15 — voice, sectioning, `concepts.md` + `files.md`, four diagrams, three figure pairs; the McCusker read fixed a false attribution and produced the compliance audit | 1067 |
| [1076](wp/1076-result-row-honesty.md) | A result row's unwritten fields: `at_bound` and `initial` | ✅ 2026-08-18 — the whole class, in four groups: `at_bound` three-valued and projected from one bound test, `initial`/`correlation_warnings` deleted, `TieSpec.from_tie` privatised, `"skipped"` and `"lebail_update"` off their vocabularies, `BACKEND_UNAVAILABLE` repaired in both directions it was wrong in, and `SeriesResult` given one `index` column and a reachable `backward`; SCHEMA_VERSION 0.1 → 0.2 and 1.0.2 gains 1.0.x's first breaking entry | 1067 |
| [1077](wp/1077-extinction-refutes-certified-class.md) | The extinction screen refutes a certified class (corundum R -3 c), and no row covers the shape | ✅ 2026-08-18 — the evidence was wrong: both refuting positions sit on a strong line's low-angle flank, where *sham* positions carrying no reflection clear the same 3σ test on 40-50 % of probes (24.7σ max, that flank only — the axial tail), and freeing the FCJ asymmetry improves Rwp without removing the refutation. `n_testable` gains a third clause — the class's **own** fit must leave the window below the test's own threshold — so a total tail failure cannot refute; the screen returns `R - c -` = {R 3 c, R -3 c} at ΔBIC −218, five testable positions all absent. `n_testable` is `int \| None`. The badly-fitted whole-range arm still refutes, which is `profile_rwp`'s job and is now measured as such | — |
| [1078](wp/1078-indexing-provisional.md) | Indexing is provisional, and every surface says so — 257 names declared, derived by defining module; **unblocks 1.0.2** | ✅ | 1067 |

The GUI **stopped being beta** when [1017](wp/1017-gui-manual-onboarding.md)
landed (2026-08-28); its routes stay provisional by declaration. 1067 declared
the original status; its **§ Floor gates [1003](wp/1003-api-freeze-pypi.md)**
and the rest lands in 1.0.x, so it stays open past the milestone by design.

### The McCusker compliance set (added 2026-08-15)

The WP-1068 audit (`milestones/v1.0.md` § Appendix): no correctness defect,
nine gaps — six WPs below, difference Fourier fenced to v2+, the
divergence-slit correction declined in the audit itself. Ordering
recommendations are the Depends cells, grounds in 1003's `### Inherited`;
the freeze decides.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1069](wp/1069-structure-r-factors.md) | R_Bragg and R_F, and the stated esd method | ✅ | — (before 1003 recommended) |
| [1070](wp/1070-user-facing-constraints.md) | User-facing constraints: ties on the Refinement surface | ✅ | 1004 (before 1003 recommended) |
| [1071](wp/1071-data-support-checks.md) | Effective observations and steps per FWHM | ✅ | — (before 1003 recommended) |
| [1072](wp/1072-geometry-table.md) | Interatomic geometry, esds from the full covariance | ✅ 2026-08-15 — distances and angles over the frozen orbits, J·Cov·Jᵀ with the diagonal-only twin beside it, `_geom_` CIF loops | — (landed before 1003) |
| [1073](wp/1073-capillary-displacement.md) | Capillary sample displacement, eq (4) | ✅ 2026-08-15 — eq (4) with derived signs, position templates and actions keyed by geometry (THRESHOLDS 1.0); measured: 11-BM is where it must *not* be refined | — (1.0.x) |
| [1074](wp/1074-restraint-weight-schedule.md) | Restraint weight schedule (c_w) | ✅ 2026-08-16 — eq (7)'s c_w per stage, identity default bit-identical; measured: a flat c_w = 1 converges to a 4.834 Å bond at Rwp 0.0393, the schedule to 1.872 Å at 0.0327 | 0406 (1.0.x) |

### v1.2 — the GUI for a crystallographer (added 2026-08-25)

The maintainer's use notes, triaged: the style system first, the manual last,
and between them one WP per cause found in the code. Order is the table's;
Depends cells are hard unless marked soft. The per-note assessment and the
decisions are the [v1.2 record](milestones/v1.2.md) § Scope.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1201](wp/1201-gui-house-style.md) | GUI house style: tokens and registers | ✅ 2026-08-25 | — (first) |
| [1204](wp/1204-developer-mode-example-projects.md) | Developer mode and example projects | ✅ 2026-08-25 | — (1201 soft) |
| [1202](wp/1202-help-corpus.md) | The help corpus, served and meta-tested | ✅ 2026-08-25 | — |
| [1203](wp/1203-help-popover.md) | The help popover: one mechanism across the panels | ✅ 2026-08-26 | 1201, 1202 |
| [1205](wp/1205-new-project-open-browse-defaults.md) | New project: open any project, browse, sensible defaults, the wizard bug | ✅ 2026-08-26 | 1201, 1203, 1204 |
| [1206](wp/1206-typed-cell-project.md) | A project without a CIF, part 1: a typed cell | ✅ | 1205 |
| [1207](wp/1207-pattern-only-project.md) | A project without a CIF, part 2: pattern-only projects | ✅ | 1206 |
| [1208](wp/1208-plan-introduction.md) | Plan panel: the gentle introduction | ✅ | 1203 |
| [1209](wp/1209-peaks-table-numbers-flags.md) | Peaks table: numbers, columns, flags | ✅ 2026-08-27 | 1201, 1203 |
| [1210](wp/1210-peak-layer-identity.md) | The peak layer: hide it, tell it apart, data-only | ✅ | 1201 |
| [1211](wp/1211-candidate-overlay.md) | Indexing candidates on the plot | ✅ 2026-08-27 | 1210 |
| [1212](wp/1212-redraw-never-moves-axes.md) | A redraw never moves the axes | ✅ 2026-08-27 | 1210 |
| [1213](wp/1213-hover-readout.md) | The hover readout | ✅ 2026-08-27 | 1212 |
| [1214](wp/1214-model-vary-and-profile-save.md) | Model: vary in the editor, and save instrument profile | ✅ 2026-08-28 | 1201 |
| [1215](wp/1215-structure-table.md) | Model: the structure table | ✅ 2026-08-28 | 1214 |
| [1216](wp/1216-instrument-form.md) | Model: the instrument form | ✅ 2026-08-28 | 1214 |
| [1217](wp/1217-history-graph-compare.md) | History: the graph and the compare table | ✅ 2026-08-28 | 1201 |
| [1017](wp/1017-gui-manual-onboarding.md) | GUI manual, in-app help anchors, and the sync mechanism (re-scoped 2026-08-25) | ✅ 2026-08-28 — three chapters in Part 1 (quickstart, panel guide, the `.rxt`/keyboard/wire chapter); the 77 routes and the nine panels partitioned like the call surface, tightening both ways; `make_screenshots.py` driving the real server over the `fap` example for 18 committed light/dark pictures, with a guard tying every reference to a declared shot; a first-run checklist whose steps are derived and whose dismissal alone persists; beta lifted, the routes still provisional | 1201–1217 (last) |

### v1.3 — agents and programs (queued 2026-08-28)

The agent-facing surface refactored against evidence: a simulated in-situ ramp run
(90 API calls, 14.6 M cache-read tokens, 34.7 min for 34 s of refinement) and a
contributor's campaign of 86 subagent runs (5,430 tool calls). Both say the only agents
are shell-equipped Claude sessions that use the notebook API and read source; none of
the surfaces built for them (`refine_json`, `capabilities()`, `help_for`, the protocol as
a document) had a reader, and none of six refining runs stopped on a package criterion.
Each WP carries its measured baseline; opens with the version bump when v1.2 ships.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1301](wp/1301-hold-unsupported-phase.md) | An unsupported phase is held for the stage, never bounded | ✅ 2026-08-28 — the structural parameters of a phase under 1σ held for the stage, its scale left free; support re-measured at the answer, so a phase that appeared is released and the stage re-solved and one that collapsed is put back where the stage found it; the ramp's 13 sub-onset patterns 2164 → 1669 iterations with no user bound and no CaF₂ cell reported at all | — (first) |
| [1302](wp/1302-error-is-documentation.md) | The error is the documentation; the output is bounded; the result is a termination view | ✅ 2026-08-29 — a wrong name answers with the right one across every schema, dataclass and the package itself; `HIGH_CORRELATION` deduplicates across stages and caps at 10 per fit; `progress=` writes one line per stage boundary; `str(result)`/`Refinement.summary()`/`SeriesResult.summary()` are the termination view — the ramp's 35.2 kB diagnostics dump is 3.5 kB on the same fit, `print(result)` smaller still | — (1305 b soft) |
| [1303](wp/1303-retire-refine-json.md) | Retire `refine_json` and the schema export | ✅ 2026-08-29 — `rietx.agent` deleted with its test, its chapter's envelope half and its four contracts on the tracer; `SCHEMA_VERSION` 0.11 → 0.12, the ladder's first removal; the eval shim runs the request itself, which is where the envelope was always owned; fast selection 3431 → 3378, every one of the 53 accounted for | — |
| [1304](wp/1304-protocol-as-skill.md) | The protocol is a skill | ✅ 2026-08-29 | 1303 |
| [1305](wp/1305-series-deliverable.md) | The series deliverable, and the checks the agent ran by hand | ✅ 2026-08-29 — §4b's fourth deliverable, a parameter against the series axis, printed by `SeriesResult.summary(deliverable="series")`; `CandidateGroup.delta_bic` (`SCHEMA_VERSION` 0.13 → 0.14) so `suggest` says whether the leverage pays for the parameter, and `Refinement.summary()`'s `next:` line is that number; `verify_discontinuities=True` refits a flagged step's two patterns cold — +5 % of a 68-pattern chain, every step reproducing at 1.00 | 1304 |
| [1306](wp/1306-powderline-recipe.md) | PowderLine recipe: the interchange format rietx did not have to invent | ✅ 2026-08-29 | — (1303 soft) |
| [1307](wp/1307-recapture-round-1-1.md) | Re-capture: surface round protocol 1.1 | ✅ | 1301-1305 (last) |

### v1.4 — free-standing peaks (shifted 2026-08-20, 2026-08-25 and 2026-08-28)

Peaks without a structure, at three ranks: fitted standalone (1101), and the
`Instrument.extra_components` union seam — the serializable answer to TOPAS's
fit_obj — with broad humps (1102) and sharp peaks (1103) as its first members.
Shifted from v1.1 when the refinement-speed milestone took that slot
(2026-08-20), from v1.2 when the GUI milestone took that one (2026-08-25),
and from v1.3 when the agent-surface work did (2026-08-28); the WPs keep
their 11xx numbers per the block rule's ran-past precedent above.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1101](wp/1101-standalone-peak-fitting.md) | fit_peaks: standalone peak fitting at named positions | ⬜ | — |
| [1102](wp/1102-component-seam-humps.md) | The additive component seam + broad humps | ⬜ | — |
| [1103](wp/1103-peak-components.md) | Sharp extra peaks: the second component member | ⬜ | 1102 (the seam) |

### v1.1 — the agentic report (added 2026-08-18)

What the McCusker set left on the agent surface: the protocol grounded in
read literature rather than inference (Toby 2024 unread until 1104), factually
current with its three branchable vocabularies covered (1105), the
load-bearing prose typed into fields agents' grep pipelines actually deliver
(1106) — and the eval programme's three recorded-but-unowned questions
answered by a pre-registered round before any placement ships (1107).

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1104](wp/1104-agent-protocol-literature-audit.md) | Literature-grounding audit of AGENT_PROTOCOL.md | ✅ 2026-08-18 | — |
| [1105](wp/1105-agent-protocol-hygiene.md) | AGENT_PROTOCOL hygiene: stale claims out, vocabularies covered | ✅ | 1104 |
| [1106](wp/1106-report-placement-fields.md) | Report placement fields: structured where prose was load-bearing | ✅ | — |
| [1107](wp/1107-eval-placement-round.md) | Eval protocol 2.2: the placement round | ✅ 2026-08-19 | 1105, 1106 |
| [1108](wp/1108-license-statistics-placement.md) | The license beside the numbers: shipping the statistics placement | ✅ 2026-08-19 | 1107 |
| [1110](wp/1110-agent-surface-friction.md) | The agent surface, measured against an agent that used it | ✅ 2026-08-21 — the premise was false (`refine_json` is reached once an agent is told; the *schema export* has no consumers), so the investment went to the python surface: an equilibrated covariance, a bound diagnostic that quotes `active_mask`, a cell window for a phase the data cannot see, `predict` without a fit, the plan mirror crossed at its two authorities, and a wheel that no longer ships the maintainer's rulebooks. Items 3/5/7 answered as findings; 19 left as [1118](wp/1118-foreign-model-files.md) | — |

### v1.1 — refinement speed (added 2026-08-20)

The milestone's own series, opened by the 2026-08-20 review of 1109 against
the two Coelho (2018) papers: measure first (1111), then the exact wins
(1109), the batched Jacobian path (1112), the evaluation-count front (1113),
the algorithmic tier (1114, spike-then-decide), and a gated compiled tier
(1115). Targets and the opening baseline: `milestones/v1.1.md` § Acceptance.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1109](wp/1109-refinement-speed.md) | Refinement speed: where the time actually goes | ✅ 2026-08-20 | — |
| [1111](wp/1111-benchmark-harness.md) | The refinement benchmark harness, and the trigger-shaped case | ✅ | — |
| [1112](wp/1112-batched-derivative-bases.md) | The batched derivative side, and η-aware windows | ✅ 2026-08-21 | 1111 |
| [1113](wp/1113-evaluation-count.md) | Evaluation count: name the mechanism, then attack it | ✅ 2026-08-21 | 1111 (soft) |
| [1114](wp/1114-peaks-buffer-spike.md) | Peaks-buffer spike: shape reuse across 2θ | ✅ 2026-08-21 | 1112 |
| [1115](wp/1115-compiled-kernel-spike.md) | Compiled-kernel spike (gated) | ✅ 2026-08-22 | 1112, 1114 |
| [1120](wp/1120-batched-residual.md) | Batch the residual: the forward's un-taken WP-1112 win | ✅ 2026-08-22 | 1112 |
| [1121](wp/1121-per-reflection-cost.md) | The per-reflection front: what a compiled tier does not reach | ✅ 2026-08-22 | 1115 |
| [1122](wp/1122-compiled-peaks-buffer.md) | Compiled peaks buffer: the declared-tolerance tier | 🛑 2026-08-22 | 1115, 1121 (gate) |
| [1123](wp/1123-fast-tolerance-default.md) | The fast tolerance schedule, on by default | ✅ 2026-08-22 | 1113 |
| [1116](wp/1116-session-protocol-hygiene.md) | Session-protocol hygiene: the scan that cried wolf | ✅ 2026-08-20 | — |
| [1117](wp/1117-compatibility-promise.md) | The compatibility promise, rewritten for the users there are | ✅ 2026-08-21 | — |
| [1124](wp/1124-warm-series-continuation.md) | Warm-series continuation probe: seed the chain along its tangent | ✅ 2026-08-22 — negative; the band is discarded ladder rungs | 1111, 1123 |
| [1125](wp/1125-varpro-probe.md) | Variable-projection probe: profile the background, measure the tail | ✅ | 1113 |
| [1126](wp/1126-manual-style-pass.md) | Manual Part 1: the style pass the review asked for | ✅ 2026-08-22 — and every NAC number in it re-measured | 1067, 1068 |
| [1127](wp/1127-ladder-first-rung.md) | The ladder's first rung: which one a warm pattern starts on | ✅ 2026-08-23 — bounded, not chosen; 1603 → 1395 evaluations with bit-identical answers | 1111, 1124, 1051 |
| [1128](wp/1128-prior-seed-before-the-gate.md) | The prior's deliberate trial runs before the ladder's gate | ✅ 2026-08-23 — the red Linux nightlies were a load sensor, not a regression: setup before the first budget check 2.01–9.28 ms → 0.05–0.24 ms (margin 5.4× → 207×), and the test starves the ladder structurally | — |
| [1129](wp/1129-absent-phase-support-is-a-flat-direction.md) | The absent phase's support is a flat direction, not a number | ✅ 2026-08-23 — the Windows nightly's new red: a fixed `< 1.0` bound on a quantity spanning six orders (9.1e-07 / 0.088 / 0.548 / 1.64), re-asserted as the ordering its own docstring claimed | 1110, 1123 |

### Unscheduled — coming from another code (added 2026-08-21)

Two things 1110's round found that no milestone owns. **1118**: reading a
TOPAS/GSAS/FullProf control file and writing one back, for the **refine flags**
as much as the model — all six agents named hand-transcribing a `.inp` as the
hardest part of the work. **1119**: the named variable a `.inp` equation refers
to. Its linear half already works through `tie`/`tie_equal`, so what is missing
is a variable with its own name and bounds, multi-term ties and persistence;
nonlinear stays fenced behind `Parameter.expr`. 1119 lands first if both run.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1118](wp/1118-foreign-model-files.md) | Foreign model files: read a refinement in, write one back | ⬜ | — |
| [1119](wp/1119-named-variables.md) | Named variables and equations: a `prm` of one's own | ⬜ | — |

### Unscheduled — the fit has no reference (added 2026-08-23)

Every background rietx fitted to the ZrMo₂O₈ 492 K scan sat at **0.50–0.71 of
TOPAS's** while `Rwp`/`GoF` matched TOPAS's to two decimals; a hand heuristic
landed at 0.82–1.20. The gap is a **reference**: a quantity derived sharing no
assumption with the fit, so disagreement is diagnostic rather than tautological.
The suite has them for four known specimens; a user's own sample gets none.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1130](wp/1130-background-reference.md) | The fit has no reference: a background level it cannot argue with | ⬜ | 1131 |

### Unscheduled — the specimen is not an angle (added 2026-08-23)

Sample broadening is stored as a deg-2θ coefficient and shared across histograms
as though it were a specimen property. For strain it is one (λ-free, measured
bit-clean). For **size it is not**: the same crystallite broadens by a different
angle at a different wavelength, so one shared column serves the fixture's two
histograms values **1.717× apart** and lands +12.5 % / −34.5 % from truth at
Rwp 0.0850 → 0.2179, reporting `converged`. Under it, the package has never
converted any of these coefficients to a size or a strain at all.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1131](wp/1131-sample-broadening-is-a-specimen-property.md) | Sample broadening is a specimen property, not an angular coefficient | ⬜ | — |
| [1133](wp/1133-diagnostic-names-its-view.md) | A diagnostic names the view that shows it | ⬜ | 1130 |
| [1134](wp/1134-constant-wavelength-neutron.md) | Constant-wavelength neutron: b, lambda/n harmonics, a refinable wavelength | ✅ 2026-08-25 | — |
| [1132](wp/1132-neutron-specimen-absorption.md) | A neutron µR, from the table this package already ships | ⬜ | #108 |

## v2+ (seams pre-built, implementations fenced out)

Fundamental Parameters Approach as a differentiable convolution stack
(Cheary-Coelho 1992); TOF (new Source/Profile implementations
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

Added to this fence 2026-08-06 (user: v1 wants a robust engine, not a headline —
push further testing post-v1): the **low-symmetry real-data corpus** — NBS
Monograph 25, public domain, 16 orthorhombic + 29 triclinic peak-list patterns,
DICVOL04's own test corpus (sourcing notes in WP-1043 § corpus; until it lands,
every indexing-scoreboard summary says "high-symmetry" out loud), plus the
SDPDRR-2/CONOGRAPH profile acquisitions; and **Boultif-Louër volume tightening**
(the gated design is recorded in WP-1042 § Deferred).

Added 2026-08-15 (the McCusker audit): **difference Fourier / maximum-entropy
maps** (§6) — the partition input exists (`lebail_update`); the consumer is
structure completion, fenced beside structure solution, and the debugging
half the paper uses maps for is Layer 0/2's job here.

No WP files for v2+ on purpose — the fence is a scope-discipline decision
([DESIGN.md](DESIGN.md#locked-decisions)), and pre-writing packages invites
scope creep.

One note against the day that fence is revisited: **`vmap`-batched in-situ series
is the only accelerator story this package's hardware supports**, and WP-0408
measured its size — break-even ≈50-65 k elements per kernel, ceiling ≈2.5-3×
because the work is memory-bound, so a single pattern is below break-even even
after batching ([v0.4 record](milestones/v0.4.md), [WP-0408](wp/0408-torch-mps-backend.md)).
