# WP-1102 — The additive component seam, and broad humps as its first member

Milestone: v1.4 · Status: ✅ 2026-09-13 — `ExtraComponent` is a union
discriminated on `kind` with `HumpComponent` its first member and a six-clause
member contract admitting an expression member; `background_peaks` renamed with
a read-side migration for values *and* stored globs; `capabilities()` carries
the flag and the kind vocabulary
Depends on: — (independent of 1101; [1103](1103-peak-components.md) lands its
second member in this seam)

## Goal

`Instrument.extra_components` — a discriminated union of declared parametric
components added to the calculated pattern, this package's serializable,
differentiable, agent-visible answer to TOPAS's `fit_obj` — with
`HumpComponent` (a broad pseudo-Voigt: amorphous humps, very broad
impurities) as its first member. A hump refines center/fwhm/area/eta with
esds and reports an **area, never a weight fraction**.

## Context

**Audited at this WP's open (2026-09-13): eight of the ten tasks below already
shipped, in v1.2, under a different name.** PR #115 — the one the 2026-08-26
handover entry describes as open — merged 2026-08-27 as
`Instrument.background_peaks: list[BackgroundPeak]`, a concrete list rather
than the `ExtraComponent` union this WP specifies. It is not a sketch: 33 tests
in `tests/test_background_peaks.py` (778 lines), a cross-backend `CONFIGS` row,
a `viz/compare.py` variant with its `test_compare_ui.py` row, `help.py` entries,
a manual equation with its `*Source:*` line, three skill `references/` rows, and
a released compatibility note. What landed, task by task, is marked in the list
below. What did **not** land:

- the `ExtraComponent` **union** itself — the seam is the WP's headline and the
  only part [1103](1103-peak-components.md) is gated on;
- a `capabilities()` arm for it (`features` has no `background_peaks` key, so a
  client cannot ask whether this build has the seam);
- `BACKGROUND_PEAK_MIN_WIDTH_MULT`, the width guard's multiple, is calibrated
  against **one** measured case (20.8×, inside a 3-5 band) with no paper behind
  it — which this WP's own rule forbids, thresholds being quoted or measured,
  never tuned.

Two of the WP's specified fields were deliberately **declined** in what shipped,
with grounds stated in the `BackgroundPeak` docstring: `eta` (a broad feature
sits on a polynomial that already absorbs the Gaussian/pseudo-Voigt difference,
so η is a third number the data cannot separate) and `area` as a stored
parameter (shipped as `height`, TOPAS's `xo_Is`, so a published TOPAS fit
compares term by term; area remains a projection of the three, not a fourth).
Both readings are better than this WP's, and neither is reopened here.

- **Why a union seam and not two ad-hoc features.** A hump and a sharp extra
  peak ([1103](1103-peak-components.md)) are the same mathematical object —
  `area · pseudo_voigt(tt − center, fwhm, eta)`
  (`model/profiles/pseudovoigt.py`, unit-area, xp ops) — differing only in
  which aggregates they join. One extensible seam (the `Background`-union /
  backend-registry pattern) means a future shape (exponential tail, Debye
  amorphous term, split-pV) is one member + one evaluator + one cross-backend
  row. TOPAS prior art, concepts only (closed source): `fit_obj` is the
  capability; its *textual* form is not portable here — see the fence below.
- **The seam.** `ExtraComponent = HumpComponent` union alias (bare PEP-604 +
  `kind` Literals, the `Background` precedent in `schemas/instrument.py`);
  `Instrument.extra_components: list[ExtraComponent] = []`. An additive
  defaulted field — no `SCHEMA_VERSION` event (the events precedent) — and it
  rides `RefinementState` (which stores the full `Instrument`) into history,
  checkout and replay with nothing to add. Paths
  `instrument.extra_components.{i}.{field}`: matched by **no** preset glob
  (presets free `instrument.background.*`, the profile letters, zero,
  geometry singletons, line weights), so freeing is always the caller's
  explicit act — the microstrain "declared block, freed deliberately"
  precedent, pinned by test.
- **Freeing recipe — stages are cumulative** (`refine.py`: "stages are
  cumulative: start from everything the user left vary=True"). A
  `set_vary("instrument.extra_components.*", True)` before a preset run
  survives the plan — but the components are then free from stage 1
  (scale_bkg) onward, the unseeded-early-freeing failure mode. The
  recommended route, documented in the manual, is a custom plan appending a
  late `Stage("humps", ["instrument.extra_components.*"])`;
  `Stage.seed`/`seed_softplus` already exist to lift a softplus `area` off
  the zero floor in that stage. State both facts in the manual.
- **The member contract** (goes in the union's docstring; every future member
  obeys it): (1) an xp-ops evaluator, whole-grid or frozen-window; (2) every
  member's curve is subtracted from the Le Bail partition net
  (`CompiledModel.lebail_update` and `structure_intensity_partition` — else
  phases are handed shares of component counts); (3) each member declares its
  aggregate memberships — a hump joins the *reported background*
  (`result.y_background`, `BackgroundEvidence`, the absorption span); a peak
  ([1103](1103-peak-components.md)) joins ticks instead; (4) a new member is
  an evaluator + a cross-backend CONFIGS row + a manual equation with
  `*Source:*`, **and is itself a schema closed-vocabulary event** (moot for
  1103 while both land inside the same 1.1.0 release, but stated so a third
  member is not assumed free).
- **The fence, with grounds**: arbitrary callables or an expression DSL
  (`fit_obj` proper) violate three invariants at once — history stores state,
  not code; the traced twin must differentiate the same expression on
  jax/torch; the agent surface is JSON schemas under `extra="forbid"`. TOPAS
  can do textual fit_obj because its equation text *is* its serialization
  format. An expression-DSL member is v2+ material if ever. Not a phase kind
  (TOPAS `xo_Is`) either: `Phase` is crystallographic through and through
  (cell ties, Wyckoff, QPA) and a cell-less phase breaks every consumer.
- **`HumpComponent` fields**: `kind: Literal["hump"]`; `label: str | None`;
  `center` (Parameter, deg 2θ, apparent, required); `area` (Parameter,
  counts·deg, softplus min=0 is safe — zero is the off state); `fwhm`
  (Parameter, deg, default value=5.0, **hard floor `HUMP_FWHM_MIN = 0.1`** +
  reachability validator — the `MARCH_R_MIN` pattern, and for the same
  reason: the profile divides by Γ and a stored `min: 0.0` outlives the
  default); `eta` ([0, 1], default 0.5). All `vary=False` by default.
  Whole-grid evaluation, no windows — broad by declaration, O(n_points) per
  hump.
- **Never in the linear stack.** `bkg_paths` is hand-built at compile
  (`model/forward.py`) and a nonlinear path there gets a silently wrong exact
  Jacobian column (the background branch fires first on `path in bkg_cols`).
  Guard test: `set(bkg_paths) ∩ component paths == ∅` — `area` stays out too,
  one membership rule, no conditional. Jacobian: unknown paths fall to the
  whole-model FD column (data rows only — correct, components own no penalty
  rows; exact, FD decodes through C like the residual). Analytic columns via
  `pseudo_voigt_derivs` are deliberately out of scope: with ≤ ~10 such
  parameters the FD cost is ~10 residual evaluations per Jacobian, and the
  cross-backend agreement matrix is the correctness check.
- **Table wiring**: one authority helper `extra_component_parameters(comp)`
  (`model_fields` minus `kind`/`label` — the `roughness_parameters`
  precedent, `params/vector.py`) feeding **both** `_collect_instrument` and
  `apply_to_models` — a parameter registered in one and forgotten in the
  other silently loses its refined value at the next stage's recompile.
  Test exactly that.
- **Background-aggregate membership**: `result.y_background` gains hump
  curves (one authority — a model method consumed by `_build_result`, every
  renderer through it); `background_absorption`'s column selection
  generalizes from the hard `instrument.background.` prefix
  (`optimize/statistics.py`) to a model-declared background-block set that
  includes hump paths — the R² then measures what the *whole declared
  background* can imitate. Guard/diagnostic chain follows unchanged.
- **Evidence** (a new correction ships with a record field or a diagnostic,
  never an Rwp comparison): the hump rows in `result.parameters` — declared,
  refined, esds — are the record. New diagnostic `BACKGROUND_HUMP_SHARP`: a
  fitted fwhm approaching the instrumental predicted FWHM at its center is a
  crystalline peak being eaten, not a hump. Evidence, never refusal — and
  the width-ratio constant is **not invented up front**: thresholds are
  quoted from a paper or a measurement, never tuned, so the acceptance
  task's width-ladder measurement fixes it, provenance recorded beside it.
- `save_instrument_profile` strips `extra_components` (mount/specimen state,
  not goniometer constants — the roughness/µt precedent in
  `io/instrument_profile.py`).
- Untouched: the `Background` union and all its consumers,
  `background/auto.py`, `gui/imports.py`. GUI: the parameter panel and the
  `.rxt` instrument block render component rows for free (whole-table rule);
  no model editor (the P-spline precedent — it has none either).

- **Three seams WP-1101 left, verified present 2026-09-13** (folded from this
  WP's `### Inherited`, which is now consumed). `indexing.peaks.window_indices`
  and `group_at` are the **one** window sizing — detection, the GUI peak editor
  and `fit_peaks` all go through them, and `group_at` carries the refusals a
  *given* position needs (off the end of the pattern, in a gap).
  `indexing.peakfit.reseed_candidate` is the one authority for "does this window
  hold a component that is not declared?" — the residual proposes a position and
  ΔBIC decides; it is what a component seam should ask rather than measuring seed
  distances, which 1101 tried first and which stayed silent on a 26-esd bias.
  `rx.fit_peaks(data, instrument, positions)` fits named peaks with no model at
  all, so a declared component's position can be checked against a free fit of
  the same window without building a refinement.
- **If this WP adds a `PeakFlag` member** (1101's warning, still standing) it is a
  four-surface edit — the schema `Literal`, `help.py`, `gui/src/lib/rxt.ts`'s
  `PEAK_FLAGS` and the committed `tests/data/gui/help_keys.json` — and touching
  `gui/src` means `npm --prefix gui ci && npm --prefix gui run build`, because the
  dist digest covers it.
- **The v1.4 acceptance row for this WP is deliberately unfinished** and is
  sharpened at this open, before the work ([`../milestones/v1.4.md`](../milestones/v1.4.md)
  § Acceptance) — a bar written by a session that had not read this WP is a bar
  set too low.

**The seam decision, taken 2026-09-13, and what it rests on.** Three codes were
surveyed from the maintainer-local corpus rather than from memory, concepts only
(TOPAS and FullProf are closed):

- **TOPAS** (Coelho, 2018, *J. Appl. Cryst.* **51**, 210, corpus `QMXU7X5Z`) is a
  typed object tree — the "main-tree", described by what the paper calls a
  *pseudo-schema*, with complex types and inheritance — carrying a **computer
  algebra layer** over it. Any node may be written as an equation of other nodes,
  and parameter dependencies are tracked in dependency trees so the derivatives
  follow automatically. Its "arbitrary functions" are **not callables**: they are
  expression text over typed nodes, stored in the INP file, with equation states
  held at the node level so a derivative does not re-evaluate the whole function.
  Beside that it carries a cell-less peaks phase (`xo_Is`) and `fit_obj`.
- **GSAS-II** (Toby & Von Dreele, 2013): a background function **plus Debye
  diffuse terms plus background peaks**, three additive kinds at once.
- **FullProf** (manual, corpus `Z9LBTH6U`, eq. 3.4): `Nba` selects polynomial,
  **Debye-like plus polynomial**, Fourier filtering, or a user table. The
  Debye-like arm is `Σⱼ B_Cⱼ·sin(Q rⱼ)/(Q rⱼ)`, six amplitudes and six distances.

Two conclusions, and the second is a correction to this WP's own text.

1. **Every one of the three carries several kinds of additive non-Bragg term.** A
   list of one concrete type is the shape none of them chose, and the reason is
   not 1103: it is that a localised empirical bump and a physically-derived
   diffuse term are both wanted, by every code that has been asked. So the union
   is built now, with `HumpComponent` as its first member.
2. **This WP's fence against arbitrary functions was wrong as written.** It read:
   history stores state and not code; the traced twin must differentiate the same
   expression on jax/torch; the agent surface is JSON schemas under
   `extra="forbid"`. All three hold against a **Python callable** and none against
   an **expression**. An expression string *is* state; jax and torch differentiate
   an expression tree natively, that being the easy case rather than the hard one;
   and a `str` field is legal under `extra="forbid"`. TOPAS is the existence proof,
   and this package already has both halves it pairs — a typed tree with dot-paths,
   and a tie layer where a node is written in terms of other nodes, affine so far.
   **The member contract is therefore written to admit an expression member** and
   fences only the callable. Building one is not this WP's work.

**No second member here.** The contract has two axes and no single member tests
both: an evaluator's *shape* (a local bump in 2θ against a whole-pattern
oscillation in Q) and *where the member lands* (the reported background against
the tick list). `HumpComponent` is a local bump reported as background. A Debye
member would test the first axis, [1103](1103-peak-components.md)'s sharp peak
tests the second, and the second is the harder one to get right, so 1103 is the
proving case and Debye is named in the contract rather than built. Recorded
plainly: **until 1103 lands, the union holds one member and the evaluator-shape
axis of its contract is unproven.**

**Migration: old files open, old code does not.** `instrument.background_peaks.i.…`
is spelled into three kinds of saved file — history JSONL, a `.rex` project's
stage globs, and `.rxt` documents — and the two fail differently. A stored
*value* under the old name fails loudly, which is safe. A stored *plan glob*
loads clean and then matches nothing, which silently stops refining a declared
peak and returns a plausible wrong answer. So the read side migrates both, and a
`background_peaks` attribute in *code* raises. `SCHEMA_VERSION` 0.17 → 0.18.


## Non-goals

- Arbitrary **callables** (fenced above, with grounds). An **expression**
  member is admitted by the contract and built by neither this WP nor 1103.
- A fourth `Background` union kind — humps compose with any base background
  from outside it.
- Amorphous / internal-standard QPA (v2 fence): a hump's quotable number is
  its area (counts·deg) with esd, never a fraction.
- Analytic Jacobian columns for component parameters.
- Preset stages that free components — freeing stays the caller's declared act.
- A GUI component editor.
- Sharp peaks ([1103](1103-peak-components.md)).

## Tasks

Marked against the tree as audited 2026-09-13. `✅ v1.2` means the task's
*content* shipped under `background_peaks`; it does not mean the seam this WP
specifies exists. **The union decision is the open one and it gates the rest** —
until it is taken, none of the three remaining items has a settled shape.

- [x] **The seam decision, taken 2026-09-13** (grounds in Context § The seam
      decision). Build the union; `background_peaks` becomes `extra_components`
      with a read-side migration; no second member in this WP.
- [x] **The union, and the member contract.** `ExtraComponent` discriminated on
      `kind`; `HumpComponent` its one member. Six clauses in the union's
      docstring, clause 6 written to admit an **expression** member and to fence
      only the callable — the correction to this WP's own three grounds, none of
      which survives contact with TOPAS's architecture. What the union has not
      proved is stated beside it rather than left implied.
- [x] **The rename and its read-side migration.** `schemas/migrate.py`, one
      textual authority applied at three named read points (`READ_POINTS`, a
      claim with a test). Seven tests; the load-bearing one is the stored plan
      glob, the half that fails in silence. `SCHEMA_VERSION` 0.17 → 0.18, the
      break recorded in the v1.4 record for the release notes.
- [x] ✅ v1.2 Schema: `BackgroundPeak` + `BACKGROUND_PEAK_FWHM_MIN` +
      reachability validator (the `MARCH_R_MIN` pattern); JSON round-trip;
      release-notes line (`../releases/1.2.0.md`). `eta` and a stored `area`
      declined with grounds — see the Context note.
- [x] ✅ v1.2 Table wiring via `params.vector.background_peak_parameters`
      feeding both collect and apply;
      `test_a_refined_peak_survives_a_stage_boundary` is the recompile test this
      WP asked for.
- [x] ✅ v1.2 Forward model: `CompiledModel.background()` is the one authority,
      so the Le Bail/Pawley partition net subtracts declared peaks with no
      second seam; `test_peak_paths_never_join_the_linear_background_block` is
      the `bkg_paths` disjointness guard.
- [x] ✅ v1.2 Jacobian: FD fallback asserted
      (`test_no_analytic_branch_claims_a_peak_path`,
      `test_the_fd_column_matches_a_hand_written_derivative`) + the
      `background_peaks` `CONFIGS` row in `tests/test_cross_backend.py`.
- [x] ✅ v1.2 Background-aggregate membership: `y_background` through the same
      authority; `background_absorption`'s block selection takes the peak
      prefix, **including** the zero-norm-column span fix the 2026-08-26 entry
      names as a precondition (`test_a_zero_column_is_dropped_from_a_projection_span`).
- [x] ✅ v1.2 The width fence, as `BACKGROUND_PEAK_TOO_NARROW` +
      `BACKGROUND_PEAK_MIN_WIDTH_MULT` measured against the instrument alone —
      **but see the open item below on its constant.**
- [x] **`capabilities()` gained two things, not one.** A schema-shaped
      `features["extra_components"]` saying the seam exists, and
      `Capabilities.extra_component_kinds` read off the union saying which
      members this build has — the `radiations` split one vocabulary over, so
      1103's peak joins the arm by existing. Not a `_SURFACE_FLAGS` entry: the
      seam is a *field*, not an export, so the flag is schema-shaped.
- [x] **`HUMP_MIN_WIDTH_MULT` says so now.** Read in full, its docstring was
      better than the finding claimed: the number is reasoned from a measured
      case (NIST BT-1, 5.81° FWHM at 14.4° against 0.25-0.30° instrumental,
      ~20×) plus a physical argument against 1.5, so it is *measured*, not
      *tuned*, and the repo's rule is met. What it did not say is that the
      sample is one specimen. It now states that, what would move it (a width
      ladder over several specimens, not run; a published ratio, which does not
      appear to exist), and how to read a firing near the edge — the diagnostic
      already carries the measured multiple as `value`.
- [x] ✅ v1.2 Surfaces: `io/exporters._background_description` says
      "+ N explicit Gaussian background peaks";
      `save_instrument_profile` strips them
      (`test_save_instrument_profile_strips_the_peaks`).
- [x] ✅ v1.2 Manual: `using/data.md` subsection and the
      `../manual/background.md` equation with its `*Source:*`; api-surface
      documented.
- [x] ✅ v1.2 Compare: `_with_background_peak` beside `_with_pspline` +
      its `tests/test_compare_ui.py` row.
- [x] ✅ v1.2 Acceptance measurement: 11-BM Si640c in Kapton, the four-row
      background table in the `BackgroundPeak` docstring, and
      `test_a_known_hump_comes_back_within_its_esds`. The evidence is the
      esd fall (6×) and the independently-fitted blank, not the Rwp.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_capabilities.py tests/test_compare_ui.py tests/test_manual.py tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

Full suite once on the final tree: the `background_absorption` selection
change touches guard evidence on every state.

## References

- Thompson, Cox & Hastings (1987), J. Appl. Cryst. 20, 79 — the pseudo-Voigt;
  already cited in `../manual/profiles.md`.
- [1055](1055-background-evidence.md) and the v0.5 milestone record — the
  measured background-bias failure this parameterisation answers.
- [1028](1028-robustness-external-data.md) §(e) — `MARCH_R_MIN`, the
  softplus-pole precedent the fwhm floor copies.
- TOPAS `fit_obj` as prior art — concepts only (closed source; papers and
  manual concepts). If the hump parameterisation should cite prior practice,
  the citation comes from the maintainer-local paper corpus, not memory.

## Handover log

### 2026-09-13 — the seam exists, and the fence it was given was wrong

Declaring a broad hump on the background was already possible; what changes is
that it is now the *first member of a seam* rather than a feature with its own
field. A second kind of added term — a sharp peak, a Debye diffuse term — costs
an evaluator and a row instead of a duplicate of the whole wiring, and a client
can ask a build which kinds it has rather than assuming. The other half of the
session was a correction: this WP had fenced "arbitrary functions" out of the
package on three grounds, and all three turn out to hold against a Python
callable and none against an *expression*, which is what TOPAS's arbitrary
functions actually are. So the contract now admits an expression member, and
building one is a WP rather than a redesign. The cost was a rename of a shipped
public field, paid with a migration so that no saved project loses what it had.

**The audit came first, and it removed most of the work.** The 2026-08-26 entry
below describes PR #115 as open; it merged 2026-08-27 and shipped in v1.2, so
eight of this WP's ten tasks were already done under the name
`background_peaks`. Read as a live premise it would have sent this session to
rebuild a shipped feature. Two of the fields this WP specified had also been
deliberately declined there with better reasoning than this WP's own (`eta`,
and `area` as a stored parameter); neither was reopened.

*Done.*

- **The seam decision**, taken from the corpus rather than from memory, concepts
  only: TOPAS (Coelho 2018, `QMXU7X5Z`) is a typed object tree under a
  pseudo-schema with a computer-algebra layer over it; GSAS-II carries a
  background function plus Debye terms plus background peaks; FullProf's `Nba`
  selects polynomial, Debye-like plus polynomial, Fourier filtering or a table.
  **Every one of the three carries several kinds of additive non-Bragg term**,
  so a list of one concrete type is the shape none of them chose — which is the
  argument for the union, and it does not depend on 1103.
- **`ExtraComponent`**, discriminated on `kind`, with the six-clause member
  contract in its docstring and `HumpComponent` as its one member.
- **The rename**, `background_peaks` → `extra_components` and the names around
  it, across 18 files in `src/`, with `SCHEMA_VERSION` 0.17 → 0.18 and the break
  recorded in [the v1.4 record](../milestones/v1.4.md) § Breaks for the release
  notes.
- **The migration**: `schemas/migrate.py`, one textual rule applied at three
  named read points. Old files open, old code raises.
- **`capabilities()`** gained two arms, not one — a schema-shaped
  `features["extra_components"]` for "is the seam here" and
  `extra_component_kinds`, read off the union, for "what goes in it".
- **`HUMP_MIN_WIDTH_MULT` now admits its sample size.** Read in full its
  docstring was better than the audit claimed — the number is reasoned from a
  measured case plus a physical argument against 1.5, so measured and not tuned
  — but it did not say the sample is one specimen. It does now, with what would
  move it.

*Measured* (macOS, this worktree's own `[dev]` venv — no jax, no torch; machine
otherwise idle, checked with `pgrep`):

- Fast selection **4503 passed, 127 skipped** (2:24), against 4614 items before
  the work: **+16, and +16 is exactly what was added** — 15 in
  `test_extra_components.py` (34 → 49) and 1 in `test_capabilities.py`. No new
  skip.
- Full suite **4666 passed, 136 skipped** (23:43), once, on the final tree.
- vitest 591 passed / 22 files; `svelte-check` 0 errors over 381 files; manual
  builds under `-W`; ruff clean.
- The rename's own size, for anyone costing a similar one: 81 lines in `src/`
  across 18 files, 99 in `tests/`, 18 in the manual, 4 in the skill, 3 in
  `gui/src`, 10 in dot-path fixtures.

*Gotchas.*

- **The `.rxt` carries no `instrument.` prefix.** `textdoc._render_block`
  strips each block's prefix, so a v1.2 row is `background_peaks.0.fwhm`. The
  first migration anchored on the prefix and silently missed the text document —
  the same class of gap the module exists to close, reintroduced inside it. The
  rule now matches the bare name on a word boundary, which also catches a glob
  written `instrument.background_peaks*` with no dot.
- **A stored value and a stored glob fail differently, and only one is loud.**
  This is the reason the migration is textual and not a field validator, and it
  is what the end-to-end test asserts: the project opens either way, so a test
  checking only that would pass against a build that freed nothing.
- **Three vocabularies were held still deliberately**: GSAS-II's own CSV column
  name in `tests/data/powderline`, `RECIPE_BACKGROUND_PEAK_DEGENERATE` (the
  `RECIPE_` prefix marks it as a statement about a foreign document), and the
  shipped release notes and milestone records, which describe what a past
  release did and are accurate as written.
- The recipe's stage and group names went to `extra_component`, not to `hump`:
  the glob they carry frees the whole seam, so a stage named for one member
  would be wrong the day 1103 lands.

*Next*, and it is [1103](1103-peak-components.md)'s: land the sharp peak as the
second member. It is the proving case for the contract axis this WP could not
test — a member that lands somewhere other than the reported background — and
until it does, the union has one member and says so in its own docstring. A
Debye term (`Σⱼ Bⱼ·sin(Q rⱼ)/(Q rⱼ)`, which GSAS-II and FullProf both ship and
this package does not) is the proving case for the *other* axis, an evaluator of
a different shape, and is named in the contract rather than built. An expression
member is now admissible and wants its own WP; nothing is gated on it.

- **2026-08-26** — **a proposed `BackgroundPeak` implements the humps half
  under a different shape**, from a different starting point. *(Superseded in
  part, 2026-09-13: PR #115 **merged** 2026-08-27 and shipped in v1.2. Every
  "proposed"/"would" below is now a description of the tree; the four
  differences it names are all in `src/`. See the Context note at this WP's
  open for what that leaves.)* Transcribed from
  PR #115 (open at the time of writing — three review findings outstanding), whose own
  handover draft is not taken verbatim: one of its bullets asserts a claim that
  PR withdraws, corrected below. A data-owner request for "a small number of
  explicit broad peaks summed on top of whatever background model is in use" is
  implemented there as `Instrument.background_peaks: list[BackgroundPeak]`
  (Gaussian; `position`, `height`, `fwhm`), *not* as `extra_components` with a
  `HumpComponent`. Four differences worth knowing before this WP is resumed,
  because three of them are constraints the seam design did not have:
  - **`height`, not `area`.** The parameterisation is TOPAS's `xo_Is`
    (`I` + `gauss_fwhm`), because the motivating case is a published TOPAS fit
    whose numbers had to be comparable term by term. `area` remains the right
    quotable number and is a projection of the three, not a fourth parameter.
  - **The name fences the glob.** `background_peaks` sits outside
    `instrument.background.*` because fnmatch's `*` crosses dots — the same
    reasoning this WP's own log used to prefer `extra_components`, so an
    `extra_components` seam inherits it unchanged.
  - **The width bound is the feature, not a floor.** `HUMP_FWHM_MIN = 0.1` as
    specified here is only a `MARCH_R_MIN` pole floor and does **not** stop a
    free position/height/width from being a Bragg peak with no cell behind it.
    What does is `fwhm ≥ BACKGROUND_PEAK_MIN_WIDTH_MULT · Γ_instrument(2θ₀)`,
    which depends on U,V,W and on the peak's own position and is therefore a
    reported guard (`BACKGROUND_PEAK_TOO_NARROW`), not a bound. Any member of
    the seam that is a *peak* needs this; a `BACKGROUND_HUMP_SHARP` sized from
    a width ladder would not have caught the failure, because the failure is
    not gradual. The multiple itself is calibrated against **one** measured
    case (20.8×, inside a 3–5 band) and no paper backs it — treat it as the
    weakest joint in that design, not as a quoted constant.
  - **`background_absorption` needs a span fix first.** Generalising the block
    to include peak columns saturates every R² at 1.00 unless `_span_basis`
    drops zero-norm columns — LAPACK returns an orthonormal Q whatever the rank
    of A. That defect is real and pre-existing. It does **not**, however, reach
    `BackgroundPSpline.air_scatter` at its off state: `to_internal` clamps, so
    dp/du is 1e-12 rather than 0 and no design row is exactly zero. An earlier
    commit on #115 claimed it did and withdrew the claim; the only exactly-zero
    column comes from the product h·(…) at zero height, which is why the fix is
    a provable no-op on everything shipped so far.
  A `BackgroundPeak` of that shape does not provide the `ExtraComponent` union
  itself, the member contract, `label`-keyed aggregate memberships, a sharp-peak
  member ([1103](1103-peak-components.md)), or `capabilities()`' schema-shaped
  key. A future seam should absorb it rather than sit beside it.
- **2026-08-18** — created from the single-peak planning session; numbering
  opens the 11xx block (v1.1). The seam design replaced an earlier
  humps-inside-`Background` draft: unifying with
  [1103](1103-peak-components.md) under one union deleted that draft's
  riskiest task (retightening `instrument.background.*` in every preset,
  which fnmatch's dot-crossing `*` made necessary there and the
  `extra_components` prefix makes unnecessary here).
