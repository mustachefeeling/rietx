# WP-1003 — API freeze + PyPI release

Milestone: v1.0 · Status: 🔄 2026-08-16 — Phases 1–3 complete and locally
verified; weekly CI run 31966606174 in flight; Phase 4 (the staged flip) next
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
- Flat-plate-transmission position rows (1073's ratify item): **keep the
  diagnosis, drop the advice** (sharpened by the 2026-08-16 review — "narrow
  the rows" would have removed evidence). Layer 1's `cos_theta`/`sin_2theta`
  templates stay: the shape is *right* on a flat plate (a flat specimen off
  the axis). Layer 2's two actions go, because they name parameters
  `ParameterTable` force-fixes there — the defect class 1073 fixed for
  capillaries — so the geometry reports the shape with no action. Extend
  `test_position_templates_and_actions_agree_geometry_by_geometry` to all
  three geometries; emission conditions change, so `THRESHOLDS_VERSION`
  1.0 → 1.1.
- Dual-meaning flags **blessed as-is, documented**: geometry's `stderr = None`
  (no covariance vs symmetry-fixed; a row field is the additive fix if ever
  needed) and `DataRef.has_sigma` covering reader-derived σ (the flag means
  "σ not Poisson-fallback").
- `Atom.species` (1014): the GUI-stricter asymmetry is **documented as
  deliberate** (earlier error on the human path; the compile error is the
  authoritative one). Schema validation declined — and note it is *not* cheap
  later: refusing previously-storable values is breaking under the hybrid
  rule, so any future tightening is a read-time diagnostic or a better
  compile error, never schema refusal.
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
- `INDEXING_THRESHOLDS_VERSION` (`schemas/indexing.py`, "1.2") is a *sixth*
  versioned contract the `capabilities()` arm does not quote — found by the
  2026-08-16 review. It **joins the contracts arm** (additive; the meta-test
  extends), for the same reason report-thresholds is there despite also
  riding on every report.

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
  URL, **and** `AGENT_PROTOCOL.md` (one small file) ships as package data with
  the description naming the installed copy too — an agent in a sandbox may
  have no network, and the constraint is that the pointer resolves for a
  pip-only user. No autodoc API reference at 1.0 — the
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
`ReaderCapability` without a `scans` field (1047 §5); a project's
`backend`/`solver` staying *arguments* to `Project.open`, never `ProjectDoc`
fields (1005 — persisting them needs a fallback policy nobody has written);
the §9 loop contract exactly as `tests/test_report_loop.py` pins it, with
`VerificationOutcome` carrying no node id confirmed deliberate (1052);
`series_cold` kept beside `series_rung` on the wire (1051 §4 — dropping it is
a priced version bump this WP does not take).

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

Parallel track — CI health (start beside Phase 1; `weekly.yml` has
`workflow_dispatch`, so the hang reproduces on demand, and any fix must be in
before the one full-suite run on the final tree):

- [ ] Diagnose and fix the weekly `full` hang; suite green in CI
- [x] Fix the fluorite completion assertion

Phase 1 — streamline and settled code changes (each its own commit; measured
blast radii from the 2026-08-16 review):

- [x] Expand the stub into this register and plan; consume `### Inherited`
- [x] Delete `RefinementResult.history` + `IterationRecord`; update the eval
      miner's field-collision rule (`mine_transcripts.py` + its test lean on
      `stage` being an `IterationRecord` field); no stored fixture carries the
      key (verified)
- [x] Delete the moved-house re-exports: `schemas.history`'s
      `StageSpec`/`PlanSpec` (one importer, `test_extinction.py:155`) and
      `agent`'s plan *and* WP-1045 indexing blocks (zero in-tree importers,
      verified); drop `PRIOR_FINDER` from `priors.__all__` only — priors.py
      uses it internally at three sites and keeps its import
- [x] Make `log_sum_scores` (+ its two constants) private: underscore-prefix,
      drop from `fom.__all__` and `indexing/__init__`, fix the `consensus.py`
      docstring crossref and the `indexing/CLAUDE.md` mention; tests stay
- [x] Flip `RefineRequest.report_trajectory` to `False`; CLAUDE.md's
      "default-on there" sentence moves in the same commit
- [x] Add `Diagnostic.value`; restructure `gate_failures` to carry gate codes —
      the *package* string-matches gate names in five places (layer1 ×3,
      layer2 ×2), so internal consumers switch to codes too; retire the
      frontend `gateName` parse (`App.test.ts` fixtures, vitest +
      svelte-check, committed dist rebuilt)
- [x] Drop the two flat-plate-transmission **Layer 2 actions** (Layer 1
      templates stay — see the register); extend the geometry meta-test to all
      three geometries; `THRESHOLDS_VERSION` → 1.1
- [x] File the internals (backend, compiled model, geometry, crystallography
      helpers) in the api-surface exclusions with the internal sentence;
      regenerate `api_surface_deferred.txt` after the deletions
- [x] `INDEXING_THRESHOLDS_VERSION` joins the `capabilities()` contracts arm;
      extend the contracts meta-test
- [x] Docs-sentence batch: vary-or-tie contract + `initial`; `stderr=None`;
      `has_sigma`; species asymmetry; single-phase CIF claim; `q_match`
      warning; `expected_delta_chi2`; the prior-corroborates rule;
      `best_axis` always-populated semantics (1054); absent-for-cause `None`
      conventions (`lebail_gap`, `abstained_kind`; 1057); a stored result
      cannot recompute `identifiability` (1055); `ParameterRow` pins
      `params.vector.Entry` by proxy (1004 c)

Phase 2 — the promise in writing:

- [x] Compatibility page in manual Part 1: the two tiers, the hybrid rule with
      both clauses, the provisional list, the internal sentence, the JSON
      dialect, the raw-bytes upload note, the brand/format two-promises split
      (1062/1066), and 1058's stated principle (a library primitive is cheap,
      a delivery surface is complete)
- [x] Label the deferred bucket provisional in the partition and the manual
- [x] 1.0.0 release notes: dispersion default flip + exact escape hatch and
      edge-refusal first; beta GUI; provisional wire/`.rxt`; default flips
      (`weighted`, `dpi`, `report_trajectory`); series is session-scoped; zip
      transport promised; `PlanSpec.stages` permissiveness (1004 d); the 1065
      placement note

Phase 3 — packaging metadata:

- [x] `authors`, classifiers (3.11–3.14, OS rows), `requires-python` check
- [x] Exclude `tests/` + `gui/` from the sdist; bundle third-party licence
      texts; verify with `uv build` + `tests/test_gui_dist.py`
- [x] `CITATION.cff` + `@software` bib entry (via `_about.py`)
- [x] `CONTRIBUTING.md` + `AGENTS.md` + in-repo style essentials;
      maintainer-only split stated

Phase 4 — the staged flip (parallel track green first):

- [ ] Pre-flip sweep: move `LITERATURE.md` out + edit its references; CLAUDE.md
      private-path sweep; user skims the candid files
- [ ] Flip: public + branch protection/required checks + CI un-shaping
      (nightly consolidation, matrix regrowth, Windows job, drop the free-tier
      conditionals) as one change
- [ ] Host the manual + AGENT_PROTOCOL on Pages; point
      `agent._TOOL_DESCRIPTION` at the URL; protocol file into package data
- [ ] Rewrite README against the hosted manual
- [ ] `pyproject.version` → 1.0.0; build; twine check; upload; fresh-venv
      `pip install rietx==1.0.0` smoke test. **Windows job green is a
      pre-upload gate** — the classifier claim ships only verified
- [ ] Close: measured acceptance into `milestones/v1.0.md`, ROADMAP rows
      flipped, README claims checked

## Acceptance

```sh
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest -n auto --dist loadgroup   # full suite, green
uv build && uvx twine check dist/*                     # twine is not a dev extra
# fresh venv: pip install dist/*.whl && python -c "import rietx as rx; print(rx.capabilities().schema_version)"
# after the flip: CI green and *gating* on the public repo; the manual URL
# resolves; pip install rietx==1.0.0 works from a clean environment
```

## Handover log

- **2026-08-16 (execution, Phases 2 + 3 complete; Phase 1 verified; CI track
  re-verifying)** — nine commits on `wp1003-api-freeze-pypi`, all pushed:
  - **Phase 1 verification closed locally**: the full suite ran once on the
    final Phase 1 tree — **2509 passed, 126 skipped, 0 failed** in 26:49
    (`[dev]`, no jax/torch, macOS, main checkout, `-n auto --dist
    loadgroup`).
  - **The weekly verification run 31960416982 failed with exactly one new
    failure, and it taught something**: no hang (1:59:10 under the 150-min
    ceiling — the growth diagnosis stands), fluorite fix held, fast
    3.11/3.14 green, but `test_acceptance_srm676a.py`'s R-lattice
    equivalence failed at rel 2.5e-6 against its 1e-6 tolerance. Measured
    before touching anything: darwin reproduces 2026-08-04's margins to the
    digit on today's tree (1.4e-9 / 1.2e-8), and in the CI failure the
    *hexagonal* arm agreed with darwin to 7e-10 — only the rhombohedral
    arm's TRF stopping point moved. So the tolerance was sensing solver
    termination, not the lattice; widened to 1e-5 with both measurements in
    the test comment (the mis-tie it guards is ~3e-3, 300× away), and the
    rule is now in `tests/CLAUDE.md` § Budgets as the load-sensor's numeric
    twin. **Verifying run 31966606174 dispatched** against the branch head
    (the full Phases 1–3 tree + fix); the CI-track task closes when it is
    green — `gh run watch 31966606174`.
  - **Phase 2 landed**: `docs/manual/using/compatibility.md` closes Part 1
    (two tiers, hybrid rule with both clauses, provisional declarations,
    internal sentence, JSON dialect + raw-bytes note, brand/format split,
    the 1058 defaults principle) — every name it spells was already
    documented, so the deferred bucket's 995 names are unmoved; the
    deferred header and partition docstring now say "provisional tier";
    `docs/releases/1.0.0.md` holds the release notes with repo-relative
    links (Phase 4's hosting step swaps them for hosted URLs before the
    release is cut).
  - **Phase 3 landed**: authors/classifiers/OS rows (Development Status
    flipped 2 → 5 in-session — Pre-Alpha on a 1.0.0 upload contradicts the
    release; revisit if disagreed); sdist excludes `tests` + `gui` **and
    `gui/index.html` by name** (the `.gitignore` `!gui/index.html`
    negation outranks hatchling's directory exclude — the `!`-rule family
    `tests/CLAUDE.md` warns about); wheel + sdist carry
    `LICENSE-3RD-PARTY.md` via `license-files` (`@lezer/common` was
    bundled but unlisted — verified by `topNode` literals in
    `vendor-cm.js`; ATTRIBUTION row corrected); `CITATION.cff` +
    `@software{rietx2026}` + a Citing section in the manual index, pinned
    to `_about.DIST_NAME` by a new guard in `test_no_stale_name.py`;
    `CONTRIBUTING.md` + `AGENTS.md` with the maintainer-only split stated.
  - **Counts**: fast selection 2402 passed / 117 skipped, 3:37 (`[dev]`,
    no jax/torch, macOS, main checkout, `-n auto --dist loadgroup`) —
    passed+skipped moved by exactly +1, the citation-records guard, a pass
    (not slow-marked, so both selections move by the same 1). ruff clean;
    `-W` manual build clean; `uv build` + `uvx twine check` pass on
    1.0.0.dev0; sdist verified to carry zero `tests/` or `gui/` paths;
    `test_gui_dist` green; vitest untouched.
  - **Forward reference pushed**: WP-1067 gained an `### Inherited` note —
    documenting a name now freezes it, so each 1.0.x chapter regenerates
    the deferred file and earns a release-notes line.
  - **Next — Phase 4, in order, once 31966606174 is green**: (1) pre-flip
    sweep (move `LITERATURE.md` out + edit its references in
    ROADMAP/CLAUDE.md/WP-1056/1037; CLAUDE.md private-path sweep; **user
    skims the candid files** — a user step); (2) the flip as one change
    (public + branch protection + CI un-shaping incl. the Windows job);
    (3) Pages hosting + `agent._TOOL_DESCRIPTION` URL + protocol file into
    package data; (4) README rewrite; (5) version → 1.0.0, build, upload
    (Windows green is the pre-upload gate); (6) close.
  - **Gotchas**: nothing scans `docs/releases/` (link-checking covers
    `docs/*.md`, `docs/wp`, `docs/milestones` only), so the release notes'
    cross-links are checked by eye. `license-files` in `[project]` needs
    the PEP 639-capable hatchling that uv fetches; an environment pinning
    an old hatchling rejects the field. The citation guard means any
    future rename must touch `CITATION.cff` + `references.bib` in the same
    change. The full suite need not run again for this session's tree: the
    only post-verification changes are docs, tests and packaging metadata.
- **2026-08-16 (execution, Phase 1 complete)** — the remaining four Phase 1
  tasks landed, one commit each, on `wp1003-api-freeze-pypi`:
  - **Landed**: `Diagnostic.value` (populated from `GuardFinding.value` in
    all six `_guard_diagnostics` loops) + `gate_failures` restructured to
    `GateFailure(code, message)` — codes are a `Literal` of the four gates,
    messages byte-identical, the five in-package prefix-matches switched to
    code equality, the GUI's `gateName` parse retired and the dist rebuilt.
    Flat-plate Layer 2 narrowed (`THRESHOLDS_VERSION` → 1.1 with a history
    entry; the geometry meta-test now asserts the exact template/action gap
    and proves every action freeable against a real table in all three
    geometries). Internals filed as prose in `tests/api_surface.py` (none
    reaches the unfiltered surface, so table entries would fail the live-
    exclusion meta-test; the note says so); `set_backend` documents its
    process-wide state. `indexing_thresholds_version` joined the
    `capabilities()` arm (six contracts; meta-test, manual table, root
    CLAUDE.md all moved). Docs-sentence batch: seven written, five verified
    already present (details in the commit `90cba00`); the prior-corroborates
    mechanism was *measured* before documenting (prior + one engine grades
    `medium` today — the counting fix stays deferred to post-1003 indexing
    work, on the record in `consensus.grade`).
  - **Counts**: fast selection 2401 passed / 117 skipped (`[dev]`, no
    jax/torch, macOS, main checkout, `-n auto --dist loadgroup`, 2:57 —
    passed+skipped moved by exactly 0: no pytest test added or removed).
    vitest 407 passed / 19 files (−1: the `gateName` test went with the
    parse), svelte-check clean, ruff clean, `-W` manual build clean,
    `uv build` + `uvx twine check` both pass on 1.0.0.dev0.
  - **Outstanding, both verification**: (1) the full suite on this final
    Phase 1 tree — two background runs were killed externally at ~13 % and
    ~22 %, all green to that point; run it before Phase 2 lands anything, or
    let the branch push's CI stand in until then. (2) The weekly `full`
    verification run 31960416982 (`gh run watch 31960416982`), dispatched
    17:02 UTC against `eb18f77` — it verifies the CI track (150-min ceiling
    + fluorite fix), *not* this session's tree.
  - **Gotchas**: root CLAUDE.md and `src/rietx/indexing/CLAUDE.md` both sit
    exactly at their caps (700, 280) — an addition must be paid for.  Adding
    a per-region gate is now a `THRESHOLDS_VERSION` minor event (the
    `GateCode` Literal).  `test_imports_shown_in_part_one_exist` no longer
    depends on xdist placement (submodule imports probe via
    `importlib.import_module`, not `hasattr` alone).  `grade`'s
    prior-counting is documented, deliberate, and deferred — do not "fix" it
    in passing.
- **2026-08-16 (execution, Phase 1 first half)** — five of Phase 1's nine
  tasks landed plus the CI parallel track's diagnosis, all committed on
  `wp1003-api-freeze-pypi`:
  - **The weekly "hang" is growth, measured.** The 2026-08-16 scheduled run
    *completed* at 1h57 (so no hang) with exactly one failure — the fluorite
    load sensor — and its top four `--durations` rows are indexing-acceptance
    fixture *setups* totalling ~77 min on the 2-core runner. Fluorite row
    fixed (asserts the report, not the completion; machine-state
    `search_incomplete` excluded from the caveat equality; 1 passed serially
    in 220 s). `timeout-minutes` recalibrated 120 → 150 with the measurement
    in the workflow comment; the narrowing lever is assigned to post-1003
    indexing work. **Outstanding**: one verifying run —
    `gh workflow run weekly.yml --ref wp1003-api-freeze-pypi` (~135 billed
    min) or Saturday's schedule after merge.
  - **Landed**: `RefinementResult.history` + `IterationRecord` deleted (the
    eval miner's `stage` marker flipped to rung-only by its own derivation;
    deferred surface 1002 → 995); the moved-house re-exports deleted
    (`StageSpec` off `schemas.history` and `agent`, `IndexingControls` off
    `agent`, `PRIOR_FINDER` off `priors.__all__` — the one-class guards now
    assert the *absence*); `_log_sum_scores` private with its two constants;
    `report_trajectory` default False (agent field text, `using/agents.md`,
    root CLAUDE.md all follow; the E2 one-call acceptance asks explicitly).
  - **Counts**: fast selection 2401 passed / 117 skipped (`[dev]`, no
    jax/torch, macOS, main checkout, `-n auto --dist loadgroup`, 3:22–3:49
    across two runs). Zero tests added or removed: the three guard rewrites
    moved 3 failed → 3 passed and nothing else moved. Full suite not run —
    the ladder fires it once on the final Phase 1 tree.
  - **Next**: `gate_failures` + `Diagnostic.value` (largest remaining; GUI
    dist rebuild + vitest ride along), flat-plate Layer 2 narrowing
    (`THRESHOLDS_VERSION` → 1.1), internals filing + deferred regen,
    `INDEXING_THRESHOLDS_VERSION` into the contracts arm, the docs-sentence
    batch. Then the full suite once, and the weekly dispatch.
  - **Gotchas**: `.pytest_cache/v/cache/lastfailed` is cumulative — read it
    for failure names instead of rerunning a suite. Root CLAUDE.md sits
    exactly at its 700-line cap; an addition must be paid for by a removal.
    The fluorite/E2/one-class docstrings now carry WP-1003 rationale, so
    reverting any of those decisions must touch them too.
- **2026-08-16 (review)** — critical review before execution, verified
  against the tree. Found and fixed in the plan: the flat-plate task would
  have removed Layer 1's correct diagnosis along with Layer 2's bad advice
  (register sharpened to keep-the-shape/drop-the-action); three consumed
  mailbox rulings had been dropped and are restored to §G (backend/solver as
  `Project.open` arguments, the 1052 loop-contract confirmation,
  `series_cold` kept); `INDEXING_THRESHOLDS_VERSION` is a sixth contract
  absent from the `capabilities()` arm — it joins (§E, new Phase 1 task).
  Task texts now carry the measured blast radii: the package itself
  string-matches gate names in five places, the eval miner leans on
  `IterationRecord`'s field set, CLAUDE.md states the trajectory default,
  `agent.py` has a second (indexing) moved-house re-export block with zero
  importers, `priors.py` uses `PRIOR_FINDER` internally. CI health moved to a
  parallel track (`workflow_dispatch` confirmed on `weekly.yml`); Windows-
  green made a pre-upload gate; acceptance block corrected (twine is not a
  dev extra; ruff + the `-W` manual build added).
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
