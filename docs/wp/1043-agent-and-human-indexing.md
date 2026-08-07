# WP-1043 — Indexing for an agent and for a human: report, don't refuse

Milestone: v1.0 · Status: 🔄 2026-08-07
Depends on: 1041 (closed), 1026 (closed) · 1028 soft (peak-picking edge artifact)

## Goal

`index_pattern` stops refusing to search, and stops reporting one verdict for two
different consumers. It computes what it can, says what it could not compute and
why, and leaves the judgement to whoever asked — a gate for unattended use, and
**structured evidence** for an agent or a human who can reason.

## Context

### Decided by the user, 2026-08-06 — one output, not two

The WP as first written proposed a **gate for unattended use and an evidence view
beside it**. The user's answer collapses that into one thing, and it is the
governing sentence here:

> What humans would work best with is a list of **all** given results, and
> stats/FoMs for each one, along with a **visual check against the diffraction
> data**. This would also work best for LLM reasoning — give them all the
> information, and let the user, human or machine, be the judge.

So the ranked list with per-candidate evidence is the **primary** answer, and the
grade is one field on it rather than a filter in front of it. Three consequences:

- `best_or_none()` stays, and stays as strict as it is — but it is a convenience
  for a caller that has *declared* it wants one cell, never the shape of the answer.
- Every candidate that was computed is reported, with what was computable about it
  and what was not. A candidate is not dropped for scoring badly.
- **The visual check is part of the deliverable, not documentation of it.** The
  gallery's per-candidate tick rows and Le Bail panel are the shape; the work is
  making one reachable from a result rather than only from the acceptance suite.
  It has its own task below.

A second user call the same day scopes the whole queue: **v1 wants a functional
and robust engine, not a headline feature, and further testing beyond the
existing corpus is post-v1** — the NBS Monograph 25 harvest moved to the ROADMAP
fence (§ corpus below keeps the finding). This WP is the output half of that
call; the input half — search controls and analogue priors, GUI and agent alike
— is [WP-1045](1045-indexing-search-controls.md).

### The thesis this WP serves

The package's premise is that a well-designed *output* plus LLM reasoning beats a
mechanical rule, because the reasoner can weigh evidence a threshold has to
collapse into a boolean. Indexing is currently the part of the package that least
reflects that: the gate is a boolean, the quality screen is a boolean, and both
are tuned for an unattended agent that must never be wrong. The measured cost is
below, and it is not small.

### Measured: the package refuses a question it answers perfectly

**Fluorite.** 18 usable lines, cubic F, certified a = 5.4631 Å. `assess_peak_list`
refuses it — *"18 usable lines, below the 20 that M20, F20 and Smith's volume
envelope are defined on"* — and no engine starts. Bypass the gate and hand the
same list to the engines directly:

| engine | wall clock | candidates | result |
|---|---|---|---|
| dichotomy | 0.1 s | 2 | **truth at rank 1**, a = 5.46308 Å, **−5 ppm**, centring F |
| trial_error | 0.1 s | 2 | **truth at rank 1**, a = 5.46308 Å, −5 ppm, F |
| svd | 0.6 s | 2 | **truth at rank 1**, a = 5.46308 Å, −5 ppm, F |

Three-way agreement, five parts per million, under a second. The package declines
to report it.

**The bar is real and it is about the wrong thing.** Twenty lines is where M₂₀,
F₂₀ and Smith's volume envelope are *defined*, so it is a precondition for
**scoring**. It is not a precondition for **searching**: a search needs enough
lines to over-determine the metric — 1 free parameter for cubic up to 6 for
triclinic. Eighteen lines against one free parameter is eighteen-fold
over-determined. Conflating the two preconditions is the defect — and the
searchability half **already has its authority**: `MIN_LINES_PER_DOF` (5 lines
per free metric parameter) and the per-system `supported` computation in
`quality.py` exist today; the flat `n < PEAK_MIN_USABLE_LINES` abstention just
short-circuits them. The fix reuses that authority; it must not add a second
searchability criterion beside it.

**Ranking below the scoring bar is well-defined, and here is why.** Whether a
figure of merit is computable is a property of the *peak list* (its line count),
not of any candidate — so below twenty lines the FoM panel shrinks by the same
members for every candidate, uniformly, and Borda still ranks over the members
that remain. The evidence view records which members ranked; each absent figure
is reported absent with its reason, never silently zero.

### Measured: the corpus tests the easy half of the problem

Difficulty scales with free metric parameters. The real-data acceptance corpus:

| system | free params | datasets |
|---|---|---|
| cubic | 1 | **4** |
| tetragonal | 2 | 1 |
| hexagonal | 2 | 2 |
| trigonal | 2 | 2 |
| orthorhombic | 3 | **0** |
| monoclinic | 4 | **1** (bethanechol — the one we decline to score) |
| triclinic | 6 | **0** |

**Nine of ten datasets sit at ≤ 2 free metric parameters.** Centrings are better
spread (5 P, 2 I, 2 F, 1 R) but that is the easy axis. Coelho (2003) Table 6
publishes contamination rates for orthorhombic / monoclinic / triclinic, and we
hold **0 / 1 / 0** datasets in those systems — the engines are exercised on low
symmetry only synthetically. So a claim like "never wrong, and silent more often
than right" is currently a statement about high-symmetry lattices, and every
summary must say so until the corpus moves.

**Where the missing data is — recorded for post-v1** (corpus search, 2026-08-06;
harvest deferred to the ROADMAP fence by the user's scope call). **NBS Monograph
25** is the answer for the peak-list axis: §20 alone carries 16 orthorhombic and
18 monoclinic patterns, its 21 sections hold **29 triclinic** ones, it is public
domain, from the same institution as the SRM standards already in `tests/data/`,
and it is *DICVOL04's own test corpus* — taking it means adopting a published
protocol and inheriting Boultif & Louër (2004) §5's per-pattern times. The catch:
a Monograph entry is a **peak list, not a profile**, so those rows would report
`not_validated` and never exercise `validate_by_lebail`. For profiles the corpus
is thinner than it looks: CONOGRAPH's benchmark (Oishi-Tomiyasu 2014, Table 2)
spans 25 patterns, but the only publicly released members are the SDPDRR-2
samples — monoclinic and cubic — so profiles are a second acquisition, and the
Monograph is the one to do first when the fence lifts.

### Measured: bethanechol, and a stale claim of silence

The user asked why this package does badly on its one monoclinic real-data
benchmark. Re-measured 2026-08-06 on the merged tree, and **the first thing found
was that the repo's own answer was false**. The gallery note and the acceptance
suite said, from a WP-1026 measurement dated 2026-07-30 and carried forward
verbatim through four WPs that all touched the engines: *"every engine exhausts
its budget without finishing that domain (0 candidates at 240 s, still 0 in manual
mode at 900 s) … the honest report is silence."*

There is no silence. **Every run returns 12 candidates**, and on set F under the
paper's own manual-mode conditions `search_trial_error` returns the **published
cell at rank 1 in 76 s** — reduced `7.1346, 8.8755, 16.4091, 90, 90, 93.828`
against the published `7.137, 8.875, 16.408, 90, 90, 93.84`, so −340 / +56 / +67
ppm and β out by 0.012°. `dichotomy` and `svd` return 12 candidates without it.

Scored over the paper's whole protocol: **−16**, the truth first on set F in *both*
modes and absent on the other eighteen runs. The bar is the **individual program
globals** of Bergmann et al. 2004 Table 5 — ITO13 −14, DICVOL91 −8, TREOR90 −4,
McMaille +5, Crysfire +6 (the "+9" this WP first quoted was that table's
`first_4` oracle over four programs, which no single entry reaches; the
milestone criterion was restated by WP-1026 and the ROADMAP carries it). −16
sits below ITO13's −14, the worst entry in the table.

**Read that −16 as a floor, not as the package's score**, and the distinction is
the reason the number has to be generated before it is quoted anywhere else. It
was measured with **`trial_error` only, at 30 s per engine × system** — not the
three-engine consensus a real call runs, and at a budget the paper's own programs
were not held to. A full run moves it in **both** directions and neither is
predictable: another engine can rank the truth first where this one did not, and
consensus re-ranks the merged panel by Borda, so a rival that *all three* engines
found can displace a truth only one of them did. Which is why the score has to be
run, not reasoned. What the qualified figure *does* support is the shape: **one
set of ten, and it is the set the cell was fitted to.** Every run also reported
`search_complete = False`, so the mandated monoclinic domain was never covered.

**The diagnosis, which is what to act on.** It is not the impurities and not the
matching window. Median |ΔQ| between each set's lines and the published cell,
against the median window the search used:

| set | λ | med window (Q) | med \|ΔQ\| to truth | ratio | lines inside window |
|---|---|---|---|---|---|
| F | 0.6995 | 6.11e-4 | **6.45e-6** | **0.01** | 20/20 |
| E | 1.5406 | 2.76e-4 | 9.23e-5 | 0.33 | 20/20 |
| Db | 1.5418 | 3.06e-4 | 1.93e-4 | 0.63 | 20/20 |
| Aa | 1.5418 | 2.44e-4 | 5.47e-4 | 2.24 | 12/20 |

F is the set the published cell was **refined against**, so it reproduces it to 1 %
of the window — and F is the only one of the ten we solve, which makes that single
success partly circular. E is the same compound, also impurity-free, with **all
twenty lines inside the window**, and we miss it at 33 %. So the engine that
carries this benchmark is the one CLAUDE.md already describes as poisoned by a bad
base line: `trial_error` solves the metric *exactly* from a few assumed indices, so
its accuracy is set by those few lines rather than by an average over twenty. A
14× worse base line is enough.

Two things follow. **Making the score generated is the WP-1026 reopen's task**
(ROADMAP queue), with one constraint decided here: the runner is a manual module
beside `tests/indexing_gallery.py` (a full run is ~20 min of search — a
slow-marked pytest row that size would double the full suite), and the
acceptance suite keeps only the transcription checks and asserts no score. And
bethanechol is the sharpest case for the evidence view: on set F the package
holds the published cell at **rank 1** and, with no profile to validate against,
still cannot promote it past `low`.

### Folded from 1028 (closed 2026-08-07): the peak list is the last gatekeeper

Measured 2026-07-30 on SRM 660c LaB6 — 1028 § (k) has the full text; the two
search-bound entries went to [1045](1045-indexing-search-controls.md).
`pick.py`'s `not_separable` screen misses six components on that pattern, and
**no one knob reaches them** — they fail three different conditions: four are
simply too far (1.73-2.99 fitted FWHM against `PEAK_SATELLITE_NEAR_FWHM` =
1.5), one fails `reseeded()` because the detection seed slid into the tail and
the new component took the real line (slot labels swapped), and one sits on a
group whose fit is not refuted (χ²_red 1.38), which the screen's own docstring
calls a deliberate keep. What they *are* is settled: five are axial-divergence
tails (the sign flips at 90° 2θ, which nothing else in a Bragg-Brentano
pattern does) and one is a Kα2 residual that `detect_peaks` dropped and
`fit_group` re-created at 3 % of the parent's area. The cost is on the answer
— 125 ppm on a certified cell (−127 with them in, −2 with them out), and a
shift fit consistent with zero where the truth is +0.037° — and the prize is
this WP's own subject: with them removed and the systematic measured rather
than assumed, the gate reached **`high` at −2 ppm**, M₂₀ = 1120, zero caveats,
the first time `high` has been reached on real data. The census is pinned by
`test_the_unflagged_tail_components_escape_for_three_different_reasons`, so a
fix has a table to move rather than a threshold to guess at.

### What an agent needs that a gate cannot give

The gate returns `low`/`medium`/`high` and `best_or_none()`. An agent that can
reason wants the *inputs* to that judgement, and several already exist but are
either collapsed or withheld:

* which caveats fired, and whether each is refuting or capping — present, but the
  distinction is not in the serialized answer;
* **the validation's Rwp and both detector counts together** — on magnetite the
  detector is backwards (`predicted_but_absent` reads 2 on the correct cell and
  **0** on its wrong rival) while Rwp reads 0.2545 against 0.7884. A reasoner
  given both can see the detector has failed here; the gate, reading one number,
  cannot. That is an argument for *surfacing* Rwp, not for scoring on it —
  see the retraction below;
* which figures of merit were computable and which were not, rather than a refusal
  to compute any;
* what the search covered — `systems_searched` and `search_complete` exist and are
  the model for the rest.

Two 1041 measurements to carry into any caveat wording this WP writes:
contamination breaks the **grade**, not the answer (the truth indexes exactly
its own 25 lines at every injected k, so `indexed_fraction` = 25/(25+k) and the
0.9 bar falls between k = 2 and 3 — the caveat names the symptom, not the
cause), and `n_unindexed` is an **absolute budget**, not a tolerance (told it
may leave 3 unindexed on a list carrying 12 impurities, the search returns the
truth **nowhere**: first-rank 8/8 at k = 6, 0/8 at 18).

### The visual check: two plotting facts that constrain it

(folded from `### Inherited` — measured by 1041 against the bundled **plotly
3.7.0**; neither transfers to matplotlib unchecked, but the reasoning does)

- **A `null` in `error_y.array` does not leave a gap.** plotly draws the bar's two
  caps at the point with zero height between them — byte-identical to a `0` — so a
  quantity with no esd renders as one measured exactly, a confident-wrong
  singleton in picture form. The fix is a second, invisible trace carrying bars
  only over the points that *have* an esd. Directly relevant here: some candidates
  carry `cov_af` and some do not, so any evidence view that plots a fitted cell
  parameter with its esd has exactly this problem.
- **An esd smaller than a pixel must be left invisible.** Measured: σ(a) = 6.5e-6 Å
  against a 4.8e-3 Å axis over 189 px is a 0.5 px bar, and 0.5 px is what was
  drawn. Scaling it to be seen would be WP-1029's *an exaggeration is not a
  probability*.

## Non-goals

- Loosening the **gate**. `high` should stay as strict as it is; unattended use is
  what it is for, and WP-1041 measured that a broken filter once produced the
  right answer for no reason. This WP adds a road around the gate, not through it.
- Retuning `borda_scores`, or landing an aggregate. WP-1041 measured and refuted
  the candidates; that question needs a new panel member, not another sweep.
- New engines.
- The corpus harvest (NBS Monograph 25, SDPDRR-2 profiles) — post-v1, ROADMAP
  fence.
- The bethanechol runner — the WP-1026 reopen's task (constraint recorded above).
- Search controls and priors — [WP-1045](1045-indexing-search-controls.md).

## Tasks

- [x] **Separate "can this be searched" from "can this be scored" — by reusing
      the existing authority.** `MIN_LINES_PER_DOF` and the per-system
      `supported` computation in `quality.py` decide searchability, per system;
      twenty (`PEAK_MIN_USABLE_LINES`) remains the bar for the figures of merit
      only. Below twenty the search runs over the supported systems and every
      figure that is undefined is reported **absent with its reason**, never
      silently zero or quietly omitted. No second searchability criterion.
- [x] `IndexingResult` gains a machine-readable **evidence** view: per candidate,
      each caveat with its `refuting`/`capping` kind, the Le Bail Rwp and both
      detector counts, which figures were computable (and which panel members
      ranked, when the panel is reduced), and what the search covered. No new
      physics — this is surfacing what the pipeline already knows.
- [x] **The evidence reaches the agent.** The view is serialized through
      `agent.refine_json`'s indexing arm and `agent.tool_definition()` (the arm
      still carries no `cell` key); whether the schema change is additive or a
      version bump is decided here, deliberately, before WP-1003 freezes the
      contract. **Decided: additive, `SCHEMA_VERSION` stays 0.1** — a defaulted
      field plus one new *capping* caveat is the events rule's "new field, not
      a new kind"; the one deployed consumer (the GUI) derives caveat kinds
      from the live constant, so a capping addition costs it nothing; grounds
      recorded on `AgentSuccess.evidence`.
- [x] **The visual check, reachable from a result.** Lift the gallery's
      per-candidate rendering — tick rows against the pattern, the Le Bail
      panel — into `viz/` as a function of (result, pattern);
      `python -m tests.indexing_gallery` becomes a consumer of it, not the
      owner. matplotlib at the API like `plot()`; the GUI panel (WP-1045)
      consumes the same per-candidate data, where the two plotly esd facts
      above apply.
- [x] **Find why the detector is blind on magnetite's rival, and do not reach for
      Rwp instead.** `predicted_but_absent` reads **0 of 163** on a cell whose
      reflections mostly fall where the pattern is flat; that number should be
      large, so the detector — not the fit statistic — is what is broken here.
      The unmeasured suspects are in the fit the detector reads: `validation_plan`
      frees the background and all five width terms, so a rival needing 163
      reflections can pay for them with a raised background or inflated widths,
      and every predicted position then sits on "intensity". Measure the fitted
      background and FWHM of both members of the pair before changing anything.
      **Wiring an Rwp ratio into the gate is the wrong fix** and is ruled out
      here: WP-1020 kept `lebail_rwp` off the FoM panel because it *rewards
      flexibility*, and CLAUDE.md forbids an Rwp comparison as a correction's
      evidence. Surfacing it to a reasoner (above) is a different act from
      scoring on it.
      **Measured 2026-08-07, and the sign is the finding**: the rival's own
      fit drives the co-refined background **negative** (mean −11.4 counts,
      min −27.3, on a pattern whose 5th percentile is 9; nothing floors it at
      the physical zero) — a *raised* background would have made **more**
      absences, not fewer.  Net > 3σ at 100 % of channels, so the detector
      cannot fire.  The 2×2 swap: truth's background under the rival's
      positions restores 8 (fit widths) / 14 (measured 0.54° width) of 163;
      swapping widths alone (both fits inflate 2-3×, terms pegged at bounds)
      restores none.  The Rwp separation (0.25/0.79) is the same corrupted
      fit read by a different instrument — surfaced, never ranked on.  A
      repaired detector reads **14 of 163** here, not "most of 163" — a bound
      to know before redesigning around this row.  The acceptance row
      regenerates the negative background; the fix (candidate-independent
      inputs: a floored or pattern-owned background, the peak list's measured
      width) is recorded, not landed — it re-measures every
      `predicted_but_absent` count in the tree and is follow-on work.
- [x] Re-measure the fluorite row: it currently asserts an abstention that this WP
      makes wrong. It should assert that a short clean list is **searched, ranked
      by the reduced panel and reported unscored**, and that the certified cell
      comes back at rank 1.
- [ ] **Act on 1028's escapee census** (Context § the peak list is the last
      gatekeeper): make the six unflagged tail components reachable — five
      axial-divergence tails and a re-created Kα2 residual, each with a settled
      cause — so the 125 ppm they cost a certified cell is removable without
      hand-editing the peak list. The pinned census test is the table the fix
      has to move, not a threshold to guess at.
- [x] **Say "high-symmetry" out loud**: every summary that quotes the scoreboard
      (gallery header, VALIDATION.md, AGENT_PROTOCOL) carries the qualifier
      until the corpus moves — which is post-v1.
- [x] `docs/AGENT_PROTOCOL.md` gains the split: what an unattended operator should
      read (the gate) and what a reasoning consumer should read (the evidence),
      with the fluorite case as the worked example of why they differ — and
      bethanechol set F as the case where the truth is *already* at rank 1.

## Acceptance

A clean 18-line cubic pattern is searched over its supported systems, ranked by
the reduced panel and reported with its figures marked uncomputable — no
abstention — and a per-candidate visual check is producible from the result plus
its pattern. The gate's own verdicts are unchanged on every existing acceptance
row. `docs/VALIDATION.md` regenerates.

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1041's handover — the gallery, the scoreboard, and the contamination curve
  that exposed the `n_unindexed` limit.
- `PEAK_MIN_USABLE_LINES`, `METRIC_DOF` and `MIN_LINES_PER_DOF` in
  `schemas/indexing.py` — the preconditions this WP separates, and the
  searchability authority it reuses.
- `indexing/workflow.py` — `validate_by_lebail`'s docstring says what the
  structure-free fit is for: the two discrete counts, not its Rwp.
- WP-1020 — `lebail_rwp` is not a FoM panel member, because it rewards
  flexibility. The same sentence is why the retraction below was needed.

## Retracted, 2026-08-06 — "a validator has to be constrained to be a validator"

Commit `6a49034` recorded, in `validate_by_lebail`'s docstring and its own
message, that Le Bail is preferred to Pawley **because it is the constrained
fit**: Le Bail re-partitions observed intensity, so a phantom reflection can only
take intensity the pattern contains, while Pawley's free parameters manufacture
whatever a phantom needs. The evidence was one measured pair (magnetite's cubic F
truth and its primitive rival): Le Bail 0.2545 against 0.7884, Pawley 0.1799
against 0.1784.

**The measurements stand; the mechanism was wrong, and it contradicted three
things this repo had already written down.**

- **Le Bail's intensities are as arbitrary as Pawley's.** The partition gives
  overlapping reflections whatever share of `max(y_obs − y_bkg, 0)` the current
  profile ratio asks for — one free intensity per reflection, unconstrained by
  any structure. `tests/test_acceptance_indexing.py` says so in the same breath
  it quotes these numbers: *"a Le Bail extraction with seven free intensities per
  observed line can put intensity wherever it is asked to."*
- **The story predicts the opposite of the measurement.** If a phantom can only
  take intensity that exists, phantoms cost ~nothing and Le Bail Rwp should
  *not* separate the pair — which is exactly CLAUDE.md's reason that Layer 0's
  `unmatched_calc` cannot serve as the absent-reflection detector ("Le Bail
  extraction assigns ~nothing to a phantom reflection"). The 0.79 is therefore
  unexplained, not explained, and the open task above is to explain it.
- **It was an Rwp comparison used as a correction's evidence**, which is the one
  form of argument CLAUDE.md names and forbids, and WP-1020 had already declined
  to rank on this very statistic.

What replaces it: the structure-free fit is the right validator because a cell is
a hypothesis about **positions**, and the fit lets that hypothesis be checked
against the whole profile as two discrete counts. Le Bail over Pawley is then a
cost choice — no extra θ block per candidate — not a claim about discrimination.

## Handover log

- **2026-08-06 (second entry)** — plan revised in the user review session (no
  code touched), on two user calls: **one output** already governed the WP;
  **post-v1 testing** now scopes it — the NBS Monograph 25 harvest moved to the
  ROADMAP fence (the corpus-search finding stays recorded in Context), and the
  bethanechol runner moved to the WP-1026 reopen with its shape pinned (manual
  module, not a slow pytest row). Fixes from the review: the "+9 bar" framing
  replaced by the restated milestone bar (individual program globals; −16 is
  below ITO13's −14); searchability now explicitly reuses `MIN_LINES_PER_DOF`
  and `quality.py`'s per-system `supported` rather than inventing a second
  criterion; the below-20 ranking rule stated (the panel shrinks uniformly, so
  Borda holds); the visual check promoted from a Context clause to a task, with
  1041's two plotly esd facts folded in from `### Inherited` (now deleted); and
  the evidence view gained its agent-surface task (`refine_json` arm + the
  schema-contract decision, before the WP-1003 freeze). Input-side controls and
  analogue priors split to WP-1045.
- **2026-08-06 (reconstructed post hoc)** — written by the repair session that
  1061's session-start hook sent here: this section did not exist, so the hook
  fired `repair first` from every checkout. Reconstructed from `git log --stat`
  over this WP's commits and the checklist's current state; dated with the
  commits' own date. The prefix trap from 1061's note, preserved:
  `913b694`…`6e5be4b` also say `WP-1043:` but are **WP-1044's work**,
  renumbered in `cb314ae` — not recorded here. What the three commits show:
  - **`6a49034` — the WP opened.** This file (the fluorite refusal
    measurement, the corpus-skew table, the user's one-output design call, the
    bethanechol re-measurement), its ROADMAP queue row and Current-focus note —
    plus 28 docstring lines on `validate_by_lebail` recording the magnetite
    Le Bail-vs-Pawley table under the mechanism *"a validator has to be
    constrained to be a validator"*, retracted the same day (below).
  - **`da99a45` — the −16 requalified as a floor.** This file only: the
    bethanechol score was measured `trial_error`-only at 30 s per
    engine×system, so a full three-engine consensus run moves it in both
    directions and the number must be generated before it is quoted
    (§ Measured: bethanechol).
  - **`37c9989` (PR #38, merged `560cb4e`) — the retraction.**
    `validate_by_lebail`'s docstring rewritten (the evidence is the two
    discrete counts; structure-free because at indexing time there is no
    structure; Le Bail over Pawley is a cost choice), the gallery glossary and
    the magnetite acceptance row's docstring and assertion message aligned
    with it, task 3 rewritten to "find why the detector is blind — an Rwp
    ratio in the gate is ruled out", and § Retracted appended with the three
    grounds. The measurements stand; only the mechanism was withdrawn. Why the
    mechanism was believed for part of a day the diffs do not say.

  **Checklist**: nothing ticked, and that is correct — all seven tasks are
  open. The commits authored and corrected this WP's record (plus one
  docstring); no task landed, so Status stays ⬜. **Next**: the task list from
  the top; task 3's magnetite measurement (fitted background and FWHM of both
  members of the pair) is the open question the retraction left behind.
  **Gotchas**: this repair consumed 1061's `### Inherited` entry, which asked
  for exactly this reconstruction; the plotly esd entry above it still applies
  to the evidence view and stays.
