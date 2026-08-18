# WP-1078 — Indexing is provisional, and every surface says so

Milestone: 1.0.x · Status: ✅ 2026-08-18 — **257 names declared provisional,
derived from the module that defines each one.** Five guards over the tier,
each failed on purpose once; the promise is one `{ref}` target the manual, the
protocol, the release notes and the README all point at rather than restate.
1.0.2 is unblocked.
Depends on: WP-1067 (whose chapter froze the surface this WP un-freezes)

## Goal

A reader of the indexing chapter, of the compatibility chapter or of the agent
protocol can tell that the indexing surface may change in a 1.x release. The
tier is **derived from the defining module** rather than written in prose, so a
new indexing type inherits it instead of being silently frozen by the first
chapter that documents it.

## Context

**The decision (2026-08-18, user).** Indexing is still under active development
and things are expected to change; that has to be clear to users.

**Why this is a WP and not a sentence.** `docs/manual/using/compatibility.md`
§ "The Python surface freezes as it is documented" promises that a name Part 1
documents is **frozen from the release that documents it**. WP-1067's
`using/indexing.md` (2026-08-17) documented **266** indexing names, so under
that rule the whole indexing surface is now frozen — the opposite of the
decision above. Un-documenting it is not the alternative: a subsystem under
active development is exactly the one a user needs a reference for.

**The seam already exists.** That chapter's next section, § "Provisional by
declaration", already carries three entries by declaration rather than by
bucket: the GUI as a whole (beta, routes included), the `.rxt` text document,
and session-scoped series. Indexing joins them as a fourth.

**Cover the subsystem, not the documented half — it resolves a second finding
at the same time.** WP-1067 measured that five names `docs/AGENT_PROTOCOL.md`
§7d tells an operator to call are not on the derived surface at all, so they are
in none of the three buckets and are "internal, may change without notice" by
`tests/api_surface.py`'s own internal sentence:

`rietx.indexing.assess_peak_list` · `rietx.indexing.structure_from_candidate` ·
`rietx.indexing.engines.SearchSpec` · `rietx.indexing.engines.estimate_ceiling`
· `rietx.viz.plot_indexing`

Two of those matter more than the others. `SearchSpec` is the type of
`index_pattern(spec=…)`, so a frozen function's main configuration argument is
an unfrozen type (the pydantic twin `SearchSpecSpec` is on the surface, is
documented, and converts with `SearchSpecSpec.to_spec`). And
`structure_from_candidate` has **no** frozen equivalent: building that phase by
hand means reproducing the two footguns its docstring exists to prevent — the
mandatory dummy atom, and defaulting the space group to the absence-free lattice
group rather than to a plausible one. Declaring the *subsystem* provisional
covers all five without exporting anything.

The precedent for naming an off-surface helper in a chapter is
`rietx.viz.compare.run`, which `using/report.md` has spelled fully qualified
since the floor.

**The case, worked, from WP-1077.** `determine_extinction_symbol` is frozen by
1067's chapter, and its *answer* changed in a patch release — the absence test
was refuting a class on a neighbouring peak's tail, so on certified corundum the
screen returned a class not containing the specimen's own `R -3 c`. The repair
narrows `n_testable` and widens its type to `int | None`. Nothing about that was
avoidable by being more careful at the freeze: the defect was found by writing a
manual chapter over the call, which is the same route all nine of 1076's took.

**Make the tier data.** This repo has measured what a hand-written stability
list costs (`_SURFACE_FLAGS`, WP-1037: the flag and the export drifted apart
while the test asserted the flag's own expression). So the entry is a table of
**module prefixes** with a reason, and the provisional set is derived from each
name's **defining** module — `rietx.indexing.*` and `rietx.schemas.indexing`. A
new indexing type then arrives provisional by construction. Defining, not
exporting: `determine_extinction_symbol` is re-exported at top level and
documented in `using/indexing.md`, so a table keyed by module has to reach a
*name* through the module that defines it, not only through `rietx.indexing`.

**What stays frozen, and it is the exchange.** `capabilities()`'s indexing arms
(`Capabilities.indexing_thresholds_version`, the engine and preset capability
types) and the agent envelope's `indexing` arm are **data contracts** with their
own version strings, so the declaration must not reach them: a consumer that
parses an answer keeps its hard freeze, and a caller that imports a type is the
one taking the risk.

**The same shape one subsystem over — `rietx.viz`, and this WP decides it.**
WP-1067 measured that `rietx.viz` is not on the derived surface at all (`agent`
is the only module on it), so `plot_for_vlm`, `plot_result`, `plot_trajectory`,
`plot_candidates` and `viz.html.write_html` are in none of the three buckets and
are "internal, may change without notice" by `tests/api_surface.py`'s own
sentence — while `using/files.md` points a reader at `viz.html.write_html`,
`using/report.md` has spelled `rietx.viz.compare.run` fully qualified since the
floor, and `RefinementResult.plot`, which *is* frozen, routes into that module.
The decision is to leave it internal, because the mechanism this WP builds
refuses it: an entry that matches no surface name fails, and `rietx.viz` matches
none. Internal is the stronger statement, not a weaker one. What is missing is a
sentence saying that a chapter naming an internal helper fully qualified is a
pointer rather than a promotion — that goes in the same § as this WP's
declaration.

**Sequencing constraint.** `docs/releases/1.0.2.md` § The freeze currently says
"The indexing chapter freezes 266 more, and every indexing type is now frozen in
full". That is true under today's rule and false under this one, so the rewrite
lands here and **this WP gates the 1.0.2 release** (`docs/RELEASING.md`).

## Non-goals

- **No new exports.** Adding the five helpers to `rietx.__all__` is a separate
  decision with its own consequence (they would enter the derived surface, need
  documenting, and then be frozen-but-provisional under this WP's own tier). If
  a later session wants them exported, it reopens that on purpose.
- **No change to indexing behaviour, gates or schemas.** This is a promise, not
  a refactor.
- **No general stability-tier system.** One declared-provisional subsystem plus
  the three declarations already in that section is what the evidence asks for;
  a tier vocabulary for surfaces nobody has asked about is speculative.
- **Not the extinction defect** — that is
  [1077](1077-extinction-refutes-certified-class.md).

## Tasks

- [x] `tests/api_surface.py`: a `PROVISIONAL_MODULES` table (module prefix →
      written reason) and a `provisional_names()` derivation over the defining
      module of each surface entry. Same shape as `EXCLUDED_TYPES`: an entry
      that matches nothing fails, so a rename cannot leave a dead declaration.
- [x] `tests/test_manual_api.py`: the partition is unchanged (a provisional name
      is still *documented* — coverage must not drop), plus a meta-test that
      every name in `provisional_names()` is documented, that the set is
      non-empty, and that both `using/compatibility.md` and `using/indexing.md`
      carry the marker. Make it fail on purpose once by deleting the banner.
- [x] `docs/manual/using/compatibility.md`: a fourth bullet in § Provisional by
      declaration, and a sentence in § "The Python surface freezes as it is
      documented" so a reader of the three buckets learns that a declaration can
      override the documented tier. State what a user gets in exchange: the
      changes are announced in the release notes, and the data contracts
      (`Capabilities.indexing_thresholds_version`, the agent envelope's
      `indexing` arm) keep their own hard freeze. Second sentence, from the
      `rietx.viz` decision above: the freeze covers names **on the derived
      surface**, so a chapter naming an internal helper fully qualified is a
      pointer and not a promotion.
- [x] `docs/manual/using/indexing.md`: an admonition at the top pointing at that
      section, in one or two sentences, naming what it covers (the three entry
      points, the schema types, and the `rietx.indexing` helpers the protocol
      calls).
- [x] `docs/AGENT_PROTOCOL.md` §7: one clause, because that file ships inside
      the wheel and is what a calling agent actually reads. Its §7d worked loop
      is where the off-surface helpers appear.
- [x] `docs/releases/1.0.2.md`: rewrite the indexing freeze paragraph —
      documented, and provisional by declaration — and give the count its honest
      name. Check the closing count with a third state in it (it reads "1322
      names, 1318 frozen and 4 provisional" today, which 1076 already left
      stale). The declaration also has to read consistently beside 1077's
      entries: this release is **no longer answer-identical to 1.0.1**, and its
      § What changed and § Upgrading now say the extinction screen's answer
      moved — which is the case for the declaration, not an embarrassment beside
      it.
- [x] README: § Documentation ends "undocumented public items stay provisional
      until their chapter lands", which is now not the whole rule.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_docs_consistency.py
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

Docs plus test helpers, so the full suite is not required (`tests/CLAUDE.md`
§ Running, rung 3) unless a source file is touched. The measurable criterion:
`provisional_names()` is non-empty, every name in it is documented, and the
partition still covers the whole surface.

## References

- WP-1067's 2026-08-17 handover entry — the measurement behind both halves: the
  266 names the chapter froze, and the five off-surface helpers.
- `tests/api_surface.py` docstring — why the surface is derived, and the
  internal sentence this WP qualifies for one subsystem.
- WP-1037 / root CLAUDE.md `_SURFACE_FLAGS` — why the tier is data.
- `docs/RELEASING.md` — the release this WP gates.

## Handover log

- **2026-08-18** — **closed.** All seven tasks ticked. The `### Inherited`
  mailbox was consumed on arrival: 1077's entry became the worked case in
  Context plus two constraints it only implied (derive from the *defining*
  module, and the release notes have to read consistently beside 1077's own
  entries), and 1067's `rietx.viz` entry was a decision handed here, so it was
  made rather than carried. Venv `[dev]` only (no jax/torch), Python 3.12.12,
  macOS/arm64 — every count below is from that.

  **What the tier measures.** 1320 names on the derived surface, of which
  **257 are provisional by declaration**: 3 under `rietx.indexing`
  (`pick_peaks`, `index_pattern`, `determine_extinction_symbol` — attributed
  through the modules that define them, not the top level that re-exports
  them) and 254 in `rietx.schemas.indexing`. 1063 frozen, deferred bucket 0.
  The indexing chapter spells 272 surface names: the 257, plus 15 it borrows —
  the engine and search-preset capability types, `Capabilities.search_presets`,
  and `Structure` / `Diagnostic` / `capabilities` / `agent.refine_json` /
  `ProfileTCHZ.shape`, which other chapters own.

  **Two numbers in `docs/releases/1.0.2.md` were stale and are re-measured.**
  It closed "The surface is 1322 names, of which 1318 are now frozen and 4
  remain provisional", which contradicted the paragraph above it (that one
  already said the tier was empty). The surface measures 1320 **at the 1076
  merge as well as today**, so 1322 was never a measurement of that tree; and
  "4 remain provisional" described the state before that release's own
  resolutions. The closing line is now 1320 / 1063 / 257.

  **Every guard was failed on purpose, and the messages are the ones intended.**
  Deleting the banner from `using/indexing.md`: "257 provisional name(s)
  documented only on pages that never link `provisional-by-declaration`".
  Renaming the target in the compatibility chapter: sphinx `-W` fails with
  "undefined label: 'provisional-by-declaration'" — so the two halves are
  cross-checked by the build as well as by the test. A dead prefix
  (`rietx.schemas.indexing_gone`): "declared provisional but defines nothing on
  the surface". An empty `PROVISIONAL_MODULES`: "no name is provisional".
  Blanking a class's `module`: 133 names named.

  **The one that earns its keep is `test_provisional_names_are_documented`.**
  Deleting a name from the chapter fails the coverage partition too — but
  delete it *and* regenerate the deferred bucket, which is what a session
  under time pressure would do, and the partition goes green while this one
  fires alone: "1 provisional name(s) no chapter documents". Measured, on
  `AmbiguityPartner.discriminating_two_theta`.

  **Two decisions, both recorded in Context rather than left implied.**
  `rietx.capabilities` and `rietx.agent` are deliberately *not* declared: the
  indexing thresholds version, the capability types and the envelope's
  `indexing` arm are data contracts with their own version strings, so parsing
  an answer keeps its hard freeze and only importing a type carries the risk.
  That is the exchange the promise states. And `rietx.viz` — 1067's second
  subsystem with the same shape — **stays internal**, because the mechanism
  refuses it: an entry matching no surface name fails, and `rietx.viz` is not
  on the surface at all. Internal is the stronger statement. What was missing
  was one sentence, now in the compatibility chapter: the freeze covers the
  *derived* surface, so a chapter spelling `rietx.viz.compare.run` or
  `rietx.viz.html.write_html` fully qualified is pointing, not promoting.

  **Counts.** `tests/test_manual_api.py` 9 → **13 passed**, all four new, no new
  skips — measured on both trees in this session, and it is the only test file
  whose count moved, so the fast selection's passed+skipped moves by exactly 4
  and every one is a pass. Fast suite `-m "not slow"`: **2417 passed / 117
  skipped**, 3:00 and 4:47 on two runs of the same tree minutes apart (quote
  the range, not either figure). `ruff` clean, sphinx `-W` clean. No source
  file was touched, so the full suite was not run (`tests/CLAUDE.md` § Running,
  rung 3) and `main` was not re-measured for a baseline (rung 4).

  **Gotchas for the next session.** Both CLAUDE.md files this touched are at
  their caps with zero headroom: root is 720/720 after paying for its new
  clause by tightening the sentences around it, and
  `src/rietx/indexing/CLAUDE.md` is 280/280, which is why the subtree copy of
  this rule was drafted and dropped — root always loads and already carries
  both halves, so a second copy would have been a restatement. Anything either
  file gains next has to be paid for the same way.

  **What is left.** 1.0.2 is unblocked and unreleased; `docs/RELEASING.md` is
  the whole of it, and the tag builds the wheel. The five off-surface helpers
  (`assess_peak_list`, `structure_from_candidate`, `engines.SearchSpec`,
  `engines.estimate_ceiling`, `viz.plot_indexing`) are still unexported, which
  was this WP's Non-goal and is unchanged by it — the declaration covers them
  as prose, and exporting any of them is a separate decision that would put
  them on the surface and require chapters.

- **2026-08-18** — created, from the user's decision that indexing is still
  under active development. Nothing landed yet; the design above (declare the
  subsystem, derive the tier from the defining module, cover the off-surface
  helpers by the same declaration) is the recommendation, not a measurement.
