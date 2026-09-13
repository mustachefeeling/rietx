# WP-1103 — Sharp extra peaks: the second component member

Milestone: v1.4 · Status: ✅ 2026-09-13 — `PeakComponent` shipped; the member contract's clause 2 is a tested claim
Depends on: WP-1102 (the component seam this member lands in)

## Goal

`PeakComponent` — user-declared sharp pseudo-Voigt peaks the phases cannot
model (a sample holder at a different specimen distance, an unidentified
sharp impurity) — so overlapping channels stay in the fit instead of being
excluded along with the sample peaks under them. The package recommends
through evidence and never refuses or gates; the operando good-unit-cells
use is the design case.

## Context

- **The design case.** An operando series where the user wants unit-cell
  trajectories to demonstrate a phenomenon: strong holder reflections from a
  mount at its own specimen distance overlap sample peaks, no phase at the
  right geometry can model them, and `excluded_regions` would also mask the
  sample peaks underneath. The user knows what they are doing; the package's
  job is honest evidence, not a gate ("agent-first" thesis: report evidence,
  never refuse).
- **`PeakComponent` joins the `ExtraComponent` union** — a closed-vocabulary
  member addition per [1102](1102-component-seam-humps.md)'s contract, moot
  while both land inside the same 1.4.0 release. Not a phase kind (TOPAS
  `xo_Is`): `Phase` is crystallographic through and through, and a cell-less
  phase breaks every consumer; the seam gives the power without the schema
  violence.
- **This WP is what makes the contract's clause 2 a *tested* claim.** The
  six-clause member contract lives in the union's docstring in
  `schemas/instrument.py`, and clause 2 — a member's aggregate membership is
  held as **data**, never read off the class name — is the one this member is
  for: a hump joins the reported background, a peak joins the tick list. With
  `HumpComponent` alone the clause is a design intention that nothing
  exercises, and 1102 says so in its own docstring rather than leaving it
  implied. **If the clause cannot be honoured as written, changing it is in
  scope; leaving it stated and unhonoured is not.** A fourth reader of stored
  dot-paths, should this member need one, belongs in `migrate.READ_POINTS`
  (a test pins the tuple) and never in a second migration entry point.
- **Fields**: `kind: Literal["peak"]`; `label: str | None` (rendered in
  diagnostics, not a Parameter); `center` (Parameter, deg 2θ — the
  **apparent** primary-line position: no zero_shift, no displacement
  corrections, because the holder sits at its own distance and its
  aberrations are its own, absorbed into the free center; the docstring says
  so); `area` (Parameter, counts·deg — **never named `scale`**:
  `refine.mode_fixed_path` force-fixes `*.scale` under lebail/pawley and
  peak components must stay refinable there); `fwhm` (Parameter, deg);
  `eta` ([0, 1], default 0.5); `all_lines: bool = True`. Validators:
  `center` and `fwhm` must carry finite min/max — they size the frozen
  window, and the refusal message suggests a default — and
  `fwhm.min ≥ EXTRA_PEAK_FWHM_MIN = 0.005` (pole guard only; sharp is the
  point here). All `vary=False` by default.
- **Emission lines: all of them by default.** The holder diffracts the same
  source, so its Kα2 is physically present: Bragg-law splitting from the
  apparent center, per-line weight × Lp intensity ratios — `peakfit`'s
  measured precedent (holding the bare weight biased the fitted Kα1 by
  −2e-4° and −0.26 mean σ pull), and `CompiledModel.phase_peaks` already has
  the machinery (`tt_bragg_lines` × `w_line` × `lp_lines`). `all_lines=False`
  covers non-diffraction artifacts
  (fluorescence, detector). No FCJ: the holder's axial geometry is not the
  specimen's; the symmetric pV is the honest simple model.
- **Frozen windows sized from bounds, not values.** Per (line, peak), the
  window spans the line's Bragg image of `[center.min, center.max]` widened
  by `window_fwhm_mult(η)·fwhm.max + WINDOW_MIN_DEG` — the phase-window rule
  with the bound in place of the compile-time width — so a free center stays
  inside its frozen window by construction, and the frozen-per-stage
  invariant ([../DESIGN.md](../DESIGN.md#architecture-invariants)) holds with
  no `free_paths=` plumbing. **η is a bound here too**: `k(η)` is what makes
  the discarded area a *stated* bound instead of an accident of the margin,
  so a free `eta` sizes its window at `k` of its own upper bound, never of
  its value. A window containing zero fitted channels is refused at compile,
  naming the peak: a dead-column refusal (the `check_interval` sentence
  shape), not an expertise gate.
- **Le Bail / Pawley: subtraction side, never the denominator.** The
  component curve joins the background subtraction at both seams
  (`lebail_update`, `structure_intensity_partition`) per 1102's member
  contract — denominator membership would hand phases shares of holder
  counts. Peak components stay refinable under lebail (`mode_fixed_path`
  matches `.atoms.`, `*.scale`, `.source.lines.` only).
- **Two window sizings exist and this member uses the model's, not
  detection's.** [1101](1101-standalone-peak-fitting.md) made
  `indexing.peaks.window_indices` / `group_at` the one sizing for *detection*,
  the GUI peak editor and `fit_peaks` — windows cut over raw data, carrying
  the refusals a given position needs (off the end, in a gap). A compiled
  component window is the other thing entirely: frozen per stage, sized from
  bounds, and built beside the phase windows in `model/forward.py`. Reuse the
  refusal *wording*, never the helper.
- **Jacobian**: unknown paths fall to the whole-model FD column (data rows
  only — exact, no penalty rows); analytic columns out of scope (1102's
  stance). `tests/test_cross_backend.py` gains a peak-component CONFIGS row.
- **Ticks.** The sole builder (`refine._build_result`) gains one reserved
  key `"(extra)"` carrying every line's positions for every peak component,
  so Layer 0's `unmatched_obs` stops flagging declared peaks as unindexed
  impurities — the Kα2-ticks lesson one rank over. A phase actually named
  `"(extra)"` is refused at fit build (parenthesized names are no CIF's).
  Accepted wrinkle, recorded here: Layer 0's `Region.n_reflections` counts
  ticks, so `"(extra)"` ticks inflate that count in their regions — right
  for segmentation and unmatched logic, mislabeled as a count; noted rather
  than special-cased.
- **One preset frees them, the rest do not** — *corrected 2026-09-13; this
  WP said "presets never free them" and the tree disagrees.*
  `mccusker_structural` carries an `extra_components` stage (sixth of eleven,
  after profile and before coordinates) whose glob is
  `instrument.extra_components.*`, pinned by
  `test_the_structural_plan_can_free_a_declared_peak_and_nothing_else`. The
  safety property is the real one and is unaffected: nothing *adds* a
  component, so one exists only because a caller declared it. Under every other
  preset freeing is the caller's explicit act; the cumulative-stages
  recipe and its stage-1 caveat are 1102's Context, restated in this WP's
  manual section. Adding or removing a component is a model edit →
  `Refinement.edit` ([1035](1035-symmetry-surfaced.md): builds the proposed
  table, refuses rather than records); the schema validators carry the
  refusals; overlapping windows are fine by design.
- **Statistics and evidence** (recommend, never refuse): `n_free` is
  automatic (table paths); `effective_observations` counts reflections —
  peak components add none, stated in the manual. `EXTRA_PEAK_ON_REFLECTION`
  fires when a component sits within Layer 0's match tolerance (0.08°, the
  same constant) of a phase's predicted position: it may be absorbing model
  misfit — the honest warning for the impurity-shortcut use.
  `extra_peak_absorption`: block projection R² of structural columns onto
  the component span (reusing `block_projection_r2`), carried as a defaulted
  FitReport field **evidence-only at first** — the 0.25 background threshold
  was measured for background blocks (0.01–0.03 vs 0.46 separation) and
  nothing has measured component blocks, so no firing threshold ships until
  this WP's acceptance measurement supplies one (record the measured
  separation either way). `at_bound`/`HIGH_CORRELATION` guards work
  unchanged. The agent-facing rows go to the **skill**, not
  `../AGENT_PROTOCOL.md` — v1.3 reduced that file to a pointer and this
  milestone deletes it — but the section numbers the skill kept are the same
  ones: a row per code in
  [`references/diagnostics.md`](../skill/rietx/references/diagnostics.md)
  (§ 7), and the degeneracy line ("an extra peak on a reflection is a
  scale/intensity degeneracy by construction") in `SKILL.md` § 3.
  `rietx skill --install . --copy` re-syncs the two committed copies.
- **A component that is not in the specimen has no position, and that is now
  the honest evidence** ([1110](1110-agent-surface-friction.md) item 14): a
  peak reaches the pattern only through `area × profile`, so at zero area
  nothing constrains its centre either — the zero-scale phase one rank down.
  The covariance is equilibrated now, so such a parameter reports **no** esd
  rather than the small one `pinv` used to invent, and an absent esd on a
  centre is the evidence for "this component is not needed" — never an Rwp
  comparison. Say it in the vocabulary the peak-list side already chose,
  `no_intensity` (in `PEAK_UNUSABLE_FLAGS` since 1.3, so **this WP adds no
  `PeakFlag` member and pays none of that four-surface cost**), and test "at
  its zero bound" with `strategy.staged.BOUND_HIT_RTOL`, the one place that
  question is answered. `rx.fit_peaks` is the measurement half of the same
  question: a declared centre can be checked against a free fit of the same
  window with no refinement built at all, which is what the acceptance
  measurement does rather than comparing seed distances —
  `peakfit.reseed_candidate` is the precedent for asking the residual instead
  (1101 tried distances first and stayed silent on a 26-esd bias).
- **Sequential / operando recipe** (document in the manual, beside
  `using/series.md`): `carry=["*"]` warm-starts components per pattern —
  holder area/position trajectories come free; excluding
  `instrument.extra_components.*` from carry pins them to the initial model,
  a fixed holder ([1051](1051-sequential-escalation.md)/[1016](1016-sequential-series-panel.md)
  carry semantics). Esd honesty, stated once: the package reports what it
  measured; the writeup owns the claim.
- GUI: parameter rows and the `.rxt` instrument block render for free
  (whole-table rule); no model editor (Non-goal) — a python/agent feature
  first. Manual: Part 1 in `using/model.md` (declaration, freeing, lebail
  behavior, the operando recipe); Part 2 equation in
  `../manual/profiles.md` (peak-shaped, beside the TCHZ equations; 1102's
  hump equation lives in `background.md`) with a `*Source:*` line.
  Capabilities: the seam key landed in 1102; no second key. Release-notes
  line.

## Non-goals

- Auto-detection of extra peaks, or any refusal/approval gate on declaring
  them — evidence only.
- FCJ asymmetry, per-component profile shapes beyond pV, restraints between
  components.
- The contract's **other** axis — evaluator *shape*, a local bump in 2θ
  against a whole-pattern oscillation in Q. That needs a member like a Debye
  term, which GSAS-II and FullProf both ship and this package does not. It is
  named in the contract, not built, and stays untested after this WP.
- A compare variant: no standard carries holder peaks, so a variant row
  would measure nothing on every standard — a justified skip of the "add a
  row" rule, recorded here.
- A GUI editor; `.rxt` model-item addition.
- d-spacing / phase-ID interpretation of component positions
  ([1101](1101-standalone-peak-fitting.md) and indexing territory).

## Tasks

- [x] Schema: `PeakComponent` + validators (finite center/fwhm bounds with a
      suggesting refusal, `EXTRA_PEAK_FWHM_MIN`); JSON round-trip;
      `SCHEMA_VERSION` 0.18 → 0.19; `help.py` entries for every new field
      (`tests/test_help.py` crosses the vocabulary both ways, so the member
      lands red without them); release-notes line.
- [x] Forward model: windows-from-bounds + all-lines evaluation
      (weight × Lp) + empty-window refusal; frozen-window test — a center
      freed to its bound stays inside its window.
- [x] Le Bail/Pawley: unbiased-extraction test (a declared synthetic holder
      line leaves extracted phase intensities unbiased) + lebail-refinable
      test. *The multi-histogram `SharingMap` row is dropped: sharing is a
      question about a quantity two histograms have in common, and a declared
      peak is a fact about one specimen's mount at one geometry — there is no
      quantity to share. Said here rather than left as an unticked box.*
- [x] Jacobian: FD assertion + cross-backend CONFIGS row.
- [x] Ticks `"(extra)"` + the phase-name collision refusal + the Layer 0
      unmatched-obs test.
- [x] Evidence: `EXTRA_PEAK_ON_REFLECTION` + `EXTRA_PEAK_NO_INTENSITY` +
      `extra_peak_absorption` (evidence-only; **no threshold ships** — the
      measurement is in the handover) + result carry + the skill's § 7 rows
      and § 3 degeneracy line, re-synced with `rietx skill --install . --copy`.
- [x] Manual (`using/model.md` + operando recipe + `profiles.md` equation
      with `*Source:*`) + api-surface documentation + the preset-non-freeing
      pin extended to this member.
- [x] Acceptance measurement + tests: inject two overlapping holder pV
      doublet lines into a standard fixture — the refined cell with declared
      components lands within tolerance of the clean-pattern cell; quote
      (not gate) the excluded-regions alternative's cell and lost-channel
      count; measure the component-block absorption separation; obs/calc/diff
      PNGs to `tests/output/`. *`tests/test_acceptance_extra_peaks.py`; the
      measured table is in that module's docstring, and it does not say what
      this WP assumed — see the handover.*

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extra_components.py tests/test_cross_backend.py tests/test_sequential.py tests/test_capabilities.py tests/test_manual.py tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

## References

- McCusker, Von Dreele, Cox, Louër & Scardi (1999), J. Appl. Cryst. 32, 36 —
  the impurity-handling guidance this WP deliberately extends past, with
  evidence in place of refusal.
- `indexing/peakfit.py`'s measured Lp-weight bias (restated in Context).
- TOPAS `xo_Is` as prior art — concept only (closed source).
- [1035](1035-symmetry-surfaced.md) (edit refuses, never records),
  [1051](1051-sequential-escalation.md) / [1016](1016-sequential-series-panel.md)
  (sequential carry semantics).

## Handover log

### 2026-09-13 — the seam's second member, and what measuring it actually showed

A user can now tell rietx about a sharp peak their phases cannot account for —
a sample holder diffracting at its own distance, a mount, an unidentified
impurity line — and keep fitting the channels it sits on instead of excluding
them along with the sample peaks underneath. The package fits what is declared,
never detects one and never refuses one, and reports two findings about what
happened afterwards.

**The measurement is more nuanced than this WP assumed, and that is the main
thing to carry forward.** On the SRM 660c protocol with two holder lines
injected onto LaB6 reflections, declaring them recovers the clean-pattern cell
to −1.0 ppm where ignoring them costs +7.6 ppm and inflates the cell esd 7.5×.
But **excluding the regions also recovers it**, to +0.6 ppm, for 4.8 % of the
channels. So on a pattern as reflection-rich as LaB6 the case for this feature
is not cell accuracy over `excluded_regions`; it is the retained channels and
the fact that the intruder is *measured* rather than masked. The gain grows as
the reflection count falls, which is the operando case the WP was written for
and which this fixture is not. That sentence is in the acceptance module's
docstring and in the release-notes entry, so nobody reads the table as a win it
is not.

The other thing this WP was for is done: the component seam's member contract
had two axes and neither was tested against a second case. One of them now is.

**Done.** All eight checklist items.

* `PeakComponent` joins `ExtraComponent` (centre, area, FWHM, mixing, plus
  `all_lines` and a label). `SCHEMA_VERSION` 0.18 → 0.19; no break, since an
  absent component is exactly off.
* **Clause 2 is a tested claim now.** `compile_model` partitions
  `extra_components` by `COMPONENT_AGGREGATE` — read, never inferred — so a
  hump goes to `component_paths` and into `background()`, and a peak goes to
  `peak_components`, into `extra_peak_curve`, and onto `result.ticks` under the
  reserved key `"(extra)"`. Both Le Bail/Pawley nets subtract it explicitly,
  which is the whole of clause 3 for a peak-landing member and the one thing it
  costs that a hump does not.
* **`rietx.model.components` now exists.** Clause 1 named it "the one
  authority" and nothing in the repository had ever defined it — the union's
  docstring cited a module that was never written. Built rather than deleted,
  because clause 2's declared membership needed exactly that home.
* Windows sized from **bounds**, not values: the Bragg image of
  `[center.min, center.max]` widened by `window_fwhm_mult(eta.max)·fwhm.max +
  WINDOW_MIN_DEG`. Every legally reachable state is inside the window frozen
  for it, with no `free_paths` plumbed into the compile.
* Every emission line gets an image at its own Bragg angle, scaled by
  `w_l · Lp(2θ_l)/Lp(2θ_0)` — the measured form, not the bare weight.
* Two diagnostics, both advice: `EXTRA_PEAK_ON_REFLECTION` and
  `EXTRA_PEAK_NO_INTENSITY`. `Identifiability.extra_peak_absorption` beside
  them, reported and deliberately **not** thresholded.
* Manual Part 1 (`using/model.md`) and Part 2 (`profiles.md`, with its
  `*Source:*` line); skill § 7 rows and a § 3 degeneracy line; a cross-backend
  `extra_peak` config; `help.py` entries; the GUI's `PLACES` formats.

**Measured** (this session, macOS darwin 25.5.0, worktree `.venv`, `[dev]`
only — no jax, no torch; both counts on the final tree `78f613a6`, nothing else
mid-suite):

* Fast selection: **4571 passed, 132 skipped**, 4:04.
* Full selection: **4739 passed, 141 skipped**, 30:52.
* GUI: `npm test` **591 passed** across 22 files; `npm run check` 0 errors.
* Tests added, counted per file against `origin/main` rather than against a
  re-measured main (which is CI's job): `test_extra_components.py` 50 → 89
  (**+39**, all passes), `test_cross_backend.py` 103 → 110 (**+7**: 2 passes
  and **5 new skips** on this `[dev]` venv — the jax/torch `extra_peak` rows,
  which are skips and not passes), `test_acceptance_extra_peaks.py` 0 → 5
  (**+5**, all `slow`). So the fast selection moved by **+46** items (+41
  passed, +5 skipped) and the full by **+51** (+46 passed, +5 skipped).
* Acceptance, SRM 660c + two injected holder lines (area 120 counts·deg, FWHM
  0.16°, at 37.4418° and 43.6205°):

      arm       a (Å)      esd        ppm     Rwp      channels
      clean     4.156895   2.49e-05    0.0    0.08671      5332
      ignore    4.156927   1.88e-04   +7.6    0.31714      5332
      declare   4.156891   2.46e-05   −1.0    0.07701      5332
      exclude   4.156898   2.49e-05   +0.6    0.08625      5076

  Recovered component values: centres within 0.005° of truth, areas 123.4(43)
  and 124.5(24) against 120, both ~1-2σ high — which is the on-reflection
  degeneracy being real, not the fit being wrong.
* Le Bail: declaring the intruder recovers the clean extraction to machine
  precision (the injected curve is the model's own, so the net is restored bit
  for bit); ignoring it inflates the worst reflection 160.9 → 547.2.
* `extra_peak_absorption` separation, three arms on one synthetic fixture:
  healthy 0.0000, design case 0.0004, parasitic 0.2099. **No threshold ships.**
  Three arms of one fixture is thin, and the background guard's own 0.25 would
  not have fired on the parasitic arm — which is the concrete argument against
  borrowing a number across a seam because the statistic is the same.
* Default window cost: ±8.3° (1691 of 8000 channels on a 0.01° grid); 525 with
  caller-stated tight bounds. `EXTRA_PEAK_FWHM_MAX = 0.5` exists because at the
  2.0 a `Parameter` would otherwise carry, `k(η=1) ≈ 16` makes the window ±32°
  and the member costs what windowing was for.

**Gotchas** — five things the tree disagreed with, four of them this WP's own
text.

1. **`CompiledModel._peak_terms` has never existed.** Cited in Context as
   "already has the machinery"; `git log -S` finds no definition anywhere in
   the history. The real builder is `phase_peaks`. Two prose references in
   `indexing/peakfit.py` cited the phantom name too, and are corrected.
2. **The window rule `30·fwhm.max + 0.3°` is the pre-WP-1112 rule**, retired
   because a fixed ±30 FWHM carries an η-dependent intensity bias it never
   states. It matters more here than for a phase, because `eta` is a *free*
   parameter of this member.
3. **`../AGENT_PROTOCOL.md` is a pointer** this milestone deletes; the rows go
   to the skill, which kept the section numbers.
4. **"Presets never free them" is false.** `mccusker_structural` has an
   `extra_components` stage, sixth of eleven, pinned by a test since 1102. The
   safety property is the real one and is untouched — nothing *adds* a
   component — so the behaviour stands and the claim is corrected.
5. **A count quietly became a different count.** Partitioning
   `component_paths` left `n_extra_components` counting humps alone, so a
   result declaring two peaks and no hump would have reported zero, and
   `BackgroundEvidence.n_peaks` carried that number. Nothing caught it: every
   existing test declares humps only, where the two agree. Split into
   `n_extra_components` (the list) and `n_background_components` (the humps,
   which is what the background section's question actually is).

Two guards that were quiet rather than red, both now fixed in place:

* `tests/test_cross_backend.py`'s meta-test for "a config registered and never
  run" checked a **hand-written literal set**, so the `extra_peak` row I added
  collected zero tests and passed — which is exactly the failure that test
  exists to catch, one rank up. The set is now derived from the builders the
  module defines.
* The GUI's `PLACES` cross-check lives on the TypeScript side, so the python
  suite is green whether or not a new parameter family has a display format.
  Only `npm test` says.

**The review pass, honestly.** `/code-review medium --fix` was launched at
handover as step 9 requires. It ran for over an hour without returning and
without touching the working tree, so **this entry records no findings from it
— not "it found nothing", which would be a different claim.** The verification
this handover does rest on is the rest of step 10: the fast and full suites,
ruff, the GUI suite, the docs-consistency gate and the session-start scan, all
named above with their numbers. A reviewer picking the PR up should treat the
diff as unreviewed by that pass.

**Next.** 1103 closes; nothing in it is left owed. For whoever picks up v1.4:

1. The contract's **first** axis is still untested — evaluator *shape*, a
   whole-pattern oscillation in Q against a local feature in 2θ. A Debye term
   is its proving case; GSAS-II and FullProf both ship one and this package
   does not. Named in the contract, not built, and not blocking anything.
2. **Deleting the `docs/AGENT_PROTOCOL.md` pointer** is still owed to this
   milestone and is still nobody's WP. It is now *more* owed: this WP's rows
   went to the skill on the strength of that deletion happening.
3. `extra_peak_absorption` ships without a threshold. Supplying one needs arms
   across real cases, not more arms on one synthetic fixture — and the honest
   default meanwhile is the positional test, which is what carries the verdict.


- **2026-09-13 (prune)** — mailbox consumed and four stale findings repaired
  in place before any work, per the session protocol's step 1. The WP was
  written 2026-08-18 and the tree moved under three of its claims.
  **`CompiledModel._peak_terms`, cited as "already has the machinery", has
  never existed** anywhere in the repository's history (`git log -S` finds no
  definition); the real per-line builder is `CompiledModel.phase_peaks`, and
  two prose references in `indexing/peakfit.py` cite the phantom name too.
  **The window rule `30·fwhm.max + 0.3°` is the pre-WP-1112 rule**, retired
  because a fixed ±30 FWHM carries an η-dependent intensity bias it never
  states (≈ 0.64 % at η = 0.6); `window_fwhm_mult(η)` replaced it, which
  matters more here than for a phase because `eta` is a *free* parameter of
  this member — hence the new clause sizing the window at `k` of η's upper
  bound. **`../AGENT_PROTOCOL.md` is a pointer**, reduced by 1304 in v1.3 and
  deleted by this very milestone, so the two diagnostic rows and the § 3
  degeneracy line go to the skill; the section numbers survived the move, so
  only the destination changed. And the mailbox's PeakFlag warning was
  **already discharged** — `no_intensity` landed in `PEAK_UNUSABLE_FLAGS` in
  1.3, so this WP adds no flag and pays none of that four-surface cost. Two
  mechanical costs the mailbox named were not in the task list and now are:
  the `SCHEMA_VERSION` bump and the `help.py` entries.
- **2026-08-18** — created from the single-peak planning session; numbering
  opens the 11xx block (v1.1). Second member of
  [1102](1102-component-seam-humps.md)'s seam; the two were designed
  together and the member contract is stated there.
