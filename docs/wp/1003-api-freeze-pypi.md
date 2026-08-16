# WP-1003 — API freeze + PyPI release

Milestone: v1.0 · Status: 🔄 2026-08-16 — expanded from the stub; levers ruled,
execution starting
Depends on: every other v1.0 row, all closed. The release-gating half of the
manual is [1067](1067-user-api-manual.md) § Floor (landed); 1067's remaining
chapters, the GUI and indexing continue *after* this WP ships, and the freeze
is designed to leave all three room to move.

## Context

**What ships**: rietx 1.0.0 on PyPI, the repo public with CI gating `main`,
the manual hosted, and a written compatibility promise. The stub's ~1600-line
`### Inherited` mailbox was consumed 2026-08-16 into the register below; each
item's grounds stay in its source WP, which is self-contained.

**Who the release is for** (user ruling 2026-08-16, and it shaped every lever):
the first users are befriended academics who will test interactively and are
unlikely to build on the package; the later audience that would depend on it —
automated refinement in robotic labs — depends on the machine-facing surfaces
(`refine_json`, the result schemas, the event stream, saved projects), not on
call-signature stability. Development continues hard after release on the
manual, the GUI and indexing.

### The promise — three levers, ruled 2026-08-16

**Lever 1 — a two-strength freeze.**
- *Hard tier — the data contracts*: everything in `schemas/`, the agent
  envelope and its closed `ERROR_CODES`, the five versioned contracts
  `capabilities()` quotes, the `.rex/` project format, the event stream, and
  the diagnostic/guard code vocabularies (open by design). A break here
  corrupts accumulated work or an unattended pipeline; these freeze at 1.0.
- *Documented tier — the Python call surface*: an item the manual documents is
  frozen; the generated deferred bucket (`tests/api_surface_deferred.txt`,
  1086 of 1235 items at the floor) is labelled **provisional**, and each 1.0.x
  manual chapter that lands promotes its items to frozen. The boundary is the
  derived surface in `tests/api_surface.py`, so it cannot rot: a new public
  item fails the partition until filed.
- *Internal*: anything importable outside the derived surface is internal and
  may change without notice — said once, normatively.
- *Provisional by declaration*: the HTTP routes, the `.rxt` text document
  (user ruling: it stays free for continued work; it is rendered in-session
  and never persisted, and the recorded sentence stands that if it ever
  becomes a saveable file its `FORMAT_VERSION` starts moving), and the GUI as
  a whole, which ships **beta**, said in README and release notes.

**Lever 2 — the change-classification rule (hybrid).** Additive defaulted
fields on schemas, `NodeAction`, event `data` and `features` keys are safe and
move no contract version — the events precedent, now written down. Closed-
vocabulary additions (`ActionKind`, `IndexCaveat`, `NodeKind`,
`abstained_kind`, a new `EventKind`) are minor events in their own contract's
version; renames, removals and threshold moves are breaking ones. The package
version plus release notes carry the safe additions. Two clauses complete it:
a change to what an existing value *means*, even with no shape change, is
always a documented event (the `best_axis` lesson); and consumers must
tolerate unknown fields/flags — validating responses against a pinned schema
copy is unsupported.

**Lever 3 — staged publishing, in dependency order.** Step 1: repo public +
branch protection with required checks + CI un-shaping, as *one* change
(public-without-protection is the combination the record warns against).
Verify CI green and gating. Step 2: host the docs. Step 3: PyPI upload last,
once every link it embeds resolves. The PyPI upload is the only permanently
irreversible step, so it goes on a verified base.

### Decision register

Rulings 2026-08-16 unless noted; grounds in each item's source WP.

**A. Surface scope**
- The `schemas.history`/`agent` re-exports of `StageSpec`/`PlanSpec`:
  **delete**, not deprecate — no external users yet, deprecation protects
  nobody (streamline ruling). Same for `priors.PRIOR_FINDER` (keep the
  `engines` home) and `RefinementResult.history` + `IterationRecord` (dead,
  never populated — 1005's entry).
- `log_sum_scores` + `AGGREGATE_EXCLUDES`/`AGGREGATE_FLOOR_RTOL` (1041):
  **make private**; it is the instrument that refuted a design, not a ranking
  API. Tests stay.
- WP-0401's backend internals (`Backend`, `get_backend`, `set_backend`,
  `resolve_backend`, `MixedPrecisionPolicy`, …) and the compiled-model /
  `model.geometry` / `crystallography` helpers (1071, 1072, 1018):
  **internal** — filed in the api-surface exclusions, no code change.
  `set_backend` documented as process-wide state.
- `suggest_instrument` (1047): wire-field only; it sits in the provisional
  tier by construction. `peaks.json`'s internal `format_version` (1027):
  stays a GUI internal, not a sixth contract — the GUI is beta.
- State dir: **keep** `RIETX_STATE_DIR`/`~/.rietx`, no XDG (simple, common;
  cheap to revisit before any 2.0).

**B. Results and schemas**
- Curve fields stay `list[float]` in the frozen JSON contract (1029's
  measurement noted: 9.6 MB vs 2.38 MB on 59k points; arrays declined for 1.0
  as churn without a consumer).
- The vary-or-tie filter on `RefinementResult.parameters` **is the contract**
  (1053): a fixed parameter is absent; the full table is
  `Refinement.parameters()`. Document it, and say in
  `RefinedParameter.initial`'s docstring who populates it (not the fit path).
- `Diagnostic` gains `value: float | None` (additive; 1007 fenced, 1012
  measured the cost of its absence). `RegionAttribution.gate_failures` is
  restructured to carry a gate code per entry — pre-freeze, so the type change
  is free; `gui/src/lib/report.ts`'s `gateName` parse is retired.
- Flat-plate-transmission position rows (1073's ratify item): **narrow** — the
  `cos_theta`/`sin_2theta` rows name parameters `ParameterTable` force-fixes
  there, the defect class 1073 fixed for capillaries. Extend
  `test_position_templates_and_actions_agree_geometry_by_geometry` to all
  three geometries; emission conditions change, so `THRESHOLDS_VERSION`
  1.0 → 1.1.
- Dual-meaning flags **blessed as-is, documented**: geometry's `stderr = None`
  (no covariance vs symmetry-fixed; a row field is the additive fix if ever
  needed) and `DataRef.has_sigma` covering reader-derived σ (the flag means
  "σ not Poisson-fallback").
- `Atom.species` (1014): the GUI-stricter asymmetry is **documented as
  deliberate** (earlier error on the human path); schema validation declined
  for now, cheap to revisit.
- Declined knobs (1071, 1072): no `fit(geometry=False)`, no per-histogram
  `data_support` — nothing needs either; both additive later.
- `report.apply.RECIPES` classification **is** part of the report contract
  (the second half of `ActionKind`); moving a kind between classes is a minor
  event. `SuggestedAction.expected_delta_chi2` keeps its documented meaning
  (one number per report, not per action).
- `RefinementState.excluded_regions`: **decided now, built in 1.0.x** —
  additive field, and `replay` will honour the node's regions over the
  caller's data. Recorded here so the freeze does not re-open it.

**C. Agent surface**
- `RefineRequest.report_trajectory` flips to `False` (1064's pre-registered
  kill criterion fired). `evidence` stays default-on.
- The parity set is **declined on the record** (1063/1064/1070/1025): no tie
  arm, no extinction arm, no `compare_exchanges`, no `capabilities()` flags
  for `Refinement` methods. `refine_json` is documented as the constrained
  one-call surface that held up; the python surface is primary for pull
  experiments. All additive later.
- 1065's placement finding (the licence sentence reached agent context in
  2/12 cells) is recorded in the release notes as the open question:
  placement, not wording.

**D. GUI and wire**
- The routes are provisional, which retires the freeze-scope halves of the
  ui-409 question (1029/1044 — the four keys still riding `POST
  /api/project`), the route-inventory notes, and the run-kind pin as *freeze*
  items; they become ordinary GUI work post-1003. What the freeze states
  normatively: routes provisional, the JSON dialect (non-finite floats as the
  strings `"Infinity"`/`"-Infinity"`/`"NaN"`), and that the upload routes
  carry raw bytes, not JSON.
- A series stays session-scoped at 1.0 (1016); the durable series document and
  the multi-histogram project seam are **fenced together** to post-1.0, and
  the release notes say a series does not persist.

**E. Indexing**
- The prior/grade rule (1046 §4): the rule is written down now — *a prior
  corroborates but does not confirm* — and the `grade` change (count engines
  the way `agreement` does) is **deferred into the post-1003 indexing work**,
  where the acceptance suite runs anyway. Not silently frozen: the register
  entry is the statement.
- `match_window` freezes as the one authority for the matched σ(Q).
  `plot_candidates` keeps `q_match=` with the documented "always pass
  `match_window`" warning (narrowing the signature declined as churn).
- `IndexingResult` keeps **no** unconditional singleton accessor; the
  API-shape tests stay (1024).

**F. Packaging and publication**
- sdist/wheel: **exclude `tests/`** (settles the QARR licence blocker — no
  redistribution — and drops 18 MB of data + 7.3 MB of darwin-only goldens)
  and the `gui/` TS workspace; wheel keeps the committed static dist. The
  wheel/sdist metadata gains the bundled Svelte + CodeMirror MIT licence
  texts (1013).
- Metadata: `authors` becomes Yue Wu + email (reconciling LICENSE);
  `requires-python >=3.11` (the 0.0.0 placeholder's `>=3.10` is superseded at
  upload); classifiers gain per-version rows 3.11–3.14 and OS rows including
  Windows — **Windows is claimed**, backed by a scheduled fast-suite job that
  lands with the CI un-shaping (free once public; 1002's probe measured green
  after real fixes, guarded by `tests/test_portability.py`).
- Docs hosting: **GitHub Pages** off the existing Sphinx `-W` build, manual +
  `AGENT_PROTOCOL.md`; `agent._TOOL_DESCRIPTION`'s pointer becomes the hosted
  URL (resolves for a pip-only user). No autodoc API reference at 1.0 — the
  provisional bucket needs no docs by design, and the 1.0.x chapters are the
  documentation road (0604's deferral answered).
- README: rewritten against the hosted manual — one headline snippet plus
  links (448 lines today; the seven worked examples become links to
  `examples/`, whose authority rule stands).
- `LITERATURE.md`: moved out of the tree before the visibility flip (content
  to the private corpus dir; references in ROADMAP, CLAUDE.md, WP-1056/1037
  edited). **No history surgery** (user ruling: the file must not be easily
  surfaced; past-commit archaeology is acceptable). The same pre-flip sweep
  removes private-machine paths from CLAUDE.md's public text.
- Contributor surface: `CONTRIBUTING.md` + `AGENTS.md` (vendor-neutral agent
  entry point pointing at the CLAUDE.md rulebooks), carrying the enforceable
  style essentials in-repo (the two style files were superseded by private
  skills and deleted 2026-08-16) and saying which parts of CLAUDE.md are
  maintainer-only (WP protocol, memory, the paper corpus).
- `.rex/` transport: an `export as zip` / `open zip` pair is **promised in the
  release notes and built in 1.0.x** — defined as "the directory, zipped", so
  it is transport, not a second format. A troubleshooting entry names the
  cloud-sync torn-state symptom (the `DataRef` fingerprints already detect
  it).
- `CITATION.cff` + a `@software` entry in `references.bib` — both new, both
  carry the name, so both import from `_about.py` where a string is code.

**G. Ratified as they stand** (the mailbox's "confirm rather than re-derive"
items): `SCHEMA_VERSION` 0.1 under the now-written additive rule;
`EVENT_SCHEMA_VERSION` "2"; `PROJECT_FORMAT_VERSION` "1.1"; textdoc
`FORMAT_VERSION` "1" (free, above); the five-contract `capabilities()` arm
(1009's question answered); `ERROR_CODES` closed; the CIF round-trip claim
narrowed to single-phase (0309); `max_candidates` = the reported cap, applied
once by consensus (1046, superseding 1026's entry); `STAGE_KEYS` derived from
`StageSpec` (additive stage fields flow into `.rxt` automatically, so keeping
it free costs the frozen schemas nothing); the 1068/1075 plot surface with its
three behaviour changes (`two_theta_range` a window, `weighted=False`,
`dpi=300`); the series `rung` column position (1051); emission-line weight
locking; `METADATA_KEYS["wavelength_alpha2"]`'s load-bearing zero (documented);
the three attenuator diagnostic codes staying three (1047 §8);
`ReaderCapability` without a `scans` field (1047 §5).

**H. Blockers — work, not decisions**
- **The weekly `full` CI job is dead**: cancelled at exactly 2h00 on
  2026-08-09 against `timeout-minutes: 120`; last success 1h17:57 on
  2026-08-02; local full runs 28:32 / 29:55 (`[dev]`, macOS). So: a hang or
  runner cliff on the Linux `[dev,jax]` leg, not suite growth. Start by
  finding what the cancelled run was doing; do not raise the ceiling first.
- **The fluorite load-sensor row**:
  `test_acceptance_indexing.py::test_a_short_clean_list_is_searched_ranked_and_reported_unscored`
  fails under `-n auto --dist loadgroup`, passes serially (207 s). Rewrite the
  completion assertion to the shape `tests/CLAUDE.md` names ("every system
  searched reports whether its domain was exhausted"), not the budget.
- Any name-bearing string this WP adds must import from `_about.py`
  (`tests/test_no_stale_name.py` can only catch the old name).

## Tasks

Phase 1 — streamline and settled code changes (each its own commit):

- [x] Expand the stub into this register and plan; consume `### Inherited`
- [ ] Delete `RefinementResult.history` + `IterationRecord`
- [ ] Delete the `StageSpec`/`PlanSpec` re-exports and `priors.PRIOR_FINDER`;
      sweep importers
- [ ] Make `log_sum_scores` (+ its two constants) private; keep its tests
- [ ] Flip `RefineRequest.report_trajectory` to `False`
- [ ] Add `Diagnostic.value`; restructure `gate_failures` with gate codes;
      retire the frontend `gateName` parse
- [ ] Narrow the flat-plate-transmission position rows; extend the geometry
      meta-test to all three geometries; `THRESHOLDS_VERSION` → 1.1
- [ ] File the internals (backend, compiled model, geometry, crystallography
      helpers) in the api-surface exclusions with the internal sentence
- [ ] Docs-sentence batch: vary-or-tie contract + `initial`; `stderr=None`;
      `has_sigma`; species asymmetry; single-phase CIF claim; `q_match`
      warning; `expected_delta_chi2`; the prior-corroborates rule

Phase 2 — the promise in writing:

- [ ] Compatibility page in manual Part 1: the two tiers, the hybrid rule with
      both clauses, the provisional list, the internal sentence, the JSON
      dialect, the raw-bytes upload note
- [ ] Label the deferred bucket provisional in the partition and the manual
- [ ] 1.0.0 release notes: dispersion default flip + exact escape hatch and
      edge-refusal first; beta GUI; provisional wire/`.rxt`; default flips
      (`weighted`, `dpi`, `report_trajectory`); series is session-scoped; zip
      transport promised; the 1065 placement note

Phase 3 — packaging metadata:

- [ ] `authors`, classifiers (3.11–3.14, OS rows), `requires-python` check
- [ ] Exclude `tests/` + `gui/` from the sdist; bundle third-party licence
      texts; verify with `uv build` + `tests/test_gui_dist.py`
- [ ] `CITATION.cff` + `@software` bib entry (via `_about.py`)
- [ ] `CONTRIBUTING.md` + `AGENTS.md` + in-repo style essentials;
      maintainer-only split stated

Phase 4 — CI health, then the staged flip:

- [ ] Diagnose and fix the weekly `full` hang; suite green in CI
- [ ] Fix the fluorite completion assertion
- [ ] Pre-flip sweep: move `LITERATURE.md` out + edit its references; CLAUDE.md
      private-path sweep; user skims the candid files
- [ ] Flip: public + branch protection/required checks + CI un-shaping
      (nightly consolidation, matrix regrowth, Windows job, drop the free-tier
      conditionals) as one change
- [ ] Host the manual + AGENT_PROTOCOL on Pages; point
      `agent._TOOL_DESCRIPTION` at the URL
- [ ] Rewrite README against the hosted manual
- [ ] `pyproject.version` → 1.0.0; build; `twine check`; upload; fresh-venv
      `pip install rietx==1.0.0` smoke test
- [ ] Close: measured acceptance into `milestones/v1.0.md`, ROADMAP rows
      flipped, README claims checked

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup   # full suite, green
uv build && .venv/bin/python -m twine check dist/*
# fresh venv: pip install dist/*.whl && python -c "import rietx as rx; print(rx.capabilities().schema_version)"
# after the flip: CI green and *gating* on the public repo; the manual URL
# resolves; pip install rietx==1.0.0 works from a clean environment
```

## Handover log

- **2026-08-16** — expanded from the stub. The ~1600-line `### Inherited`
  mailbox is fully consumed into the Context register: levers ruled with the
  user (two-strength freeze / hybrid change rule / staged publishing, grounds
  in the register), every fork resolved or explicitly deferred with its
  ruling recorded. Stale entries dropped on consumption: the 1030 "do not
  freeze `SearchSpec`" hold (1030 closed), 1026's `max_candidates` entry
  (superseded by 1046), the 1009 five-contracts question (answered by
  `capabilities()` as shipped), the struck `baselines` entry (done 2026-08-14).
  Also this session: the user deleted `docs/DOCS_STYLE.md` and
  `docs/FIGURE_STYLE.md` (superseded by private skills; only remaining mention
  is backticked prose in closed WP-1075, `test_docs_consistency` green) —
  committed here, with the in-repo style essentials rehomed to the
  CONTRIBUTING/AGENTS task. Next: Phase 1, top to bottom.
- **2026-07-22** — created as a stub from the ROADMAP split.
