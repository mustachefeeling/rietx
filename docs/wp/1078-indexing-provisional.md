# WP-1078 — Indexing is provisional, and every surface says so

Milestone: 1.0.x · Status: ⬜
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

**Make the tier data.** This repo has measured what a hand-written stability
list costs (`_SURFACE_FLAGS`, WP-1037: the flag and the export drifted apart
while the test asserted the flag's own expression). So the entry is a table of
**module prefixes** with a reason, and the provisional set is derived from each
name's defining module — `rietx.indexing.*`, `rietx.schemas.indexing`, and
whatever `capabilities()` exposes purely to describe them. A new indexing type
then arrives provisional by construction.

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

- [ ] `tests/api_surface.py`: a `PROVISIONAL_MODULES` table (module prefix →
      written reason) and a `provisional_names()` derivation over the defining
      module of each surface entry. Same shape as `EXCLUDED_TYPES`: an entry
      that matches nothing fails, so a rename cannot leave a dead declaration.
- [ ] `tests/test_manual_api.py`: the partition is unchanged (a provisional name
      is still *documented* — coverage must not drop), plus a meta-test that
      every name in `provisional_names()` is documented, that the set is
      non-empty, and that both `using/compatibility.md` and `using/indexing.md`
      carry the marker. Make it fail on purpose once by deleting the banner.
- [ ] `docs/manual/using/compatibility.md`: a fourth bullet in § Provisional by
      declaration, and a sentence in § "The Python surface freezes as it is
      documented" so a reader of the three buckets learns that a declaration can
      override the documented tier. State what a user gets in exchange: the
      changes are announced in the release notes, and the data contracts
      (`Capabilities.indexing_thresholds_version`, the agent envelope's
      `indexing` arm) keep their own hard freeze.
- [ ] `docs/manual/using/indexing.md`: an admonition at the top pointing at that
      section, in one or two sentences, naming what it covers (the three entry
      points, the schema types, and the `rietx.indexing` helpers the protocol
      calls).
- [ ] `docs/AGENT_PROTOCOL.md` §7: one clause, because that file ships inside
      the wheel and is what a calling agent actually reads. Its §7d worked loop
      is where the off-surface helpers appear.
- [ ] `docs/releases/1.0.2.md`: rewrite the indexing freeze paragraph —
      documented, and provisional by declaration — and give the count its honest
      name. Check whether the release's headline number ("927 frozen, 395
      provisional") still reads correctly with a third state in it.
- [ ] README: § Documentation ends "undocumented public items stay provisional
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

- **2026-08-18** — created, from the user's decision that indexing is still
  under active development. Nothing landed yet; the design above (declare the
  subsystem, derive the tier from the defining module, cover the off-surface
  helpers by the same declaration) is the recommendation, not a measurement.
