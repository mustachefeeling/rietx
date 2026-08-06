# WP-1043 — Indexing for an agent and for a human: report, don't refuse

Milestone: v1.0 · Status: ⬜
Depends on: 1041 (closed), 1026 (closed) · 1028 soft (peak-picking edge artifact)

## Goal

`index_pattern` stops refusing to search, and stops reporting one verdict for two
different consumers. It computes what it can, says what it could not compute and
why, and leaves the judgement to whoever asked — a gate for unattended use, and
**structured evidence** for an agent or a human who can reason.

## Context

### Inherited

**From [1016](1016-sequential-series-panel.md) via the closed
[1041](1041-indexing-benchmark-gallery.md), 2026-08-05 — two measured facts about
drawing an esd, inherited here because this WP is the one that will surface
per-candidate quantities.** Both were measured against the bundled **plotly
3.7.0** and neither transfers to matplotlib unchecked — but the reasoning does.

- **A `null` in `error_y.array` does not leave a gap.** plotly draws the bar's two
  caps at the point with zero height between them — byte-identical to a `0` — so a
  quantity with no esd renders as one measured exactly, which is a confident-wrong
  singleton in picture form. The fix is a second, invisible trace carrying bars
  only over the points that *have* an esd. Directly relevant here: some candidates
  carry `cov_af` and some do not, so any evidence view that plots a fitted cell
  parameter with its esd has exactly this problem.
- **An esd smaller than a pixel must be left invisible.** Measured: σ(a) = 6.5e-6 Å
  against a 4.8e-3 Å axis over 189 px is a 0.5 px bar, and 0.5 px is what was
  drawn. Scaling it to be seen would be WP-1029's *an exaggeration is not a
  probability*.

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
lines to over-determine the metric, which is 1 free parameter for cubic, 2 for
tetragonal/hexagonal/trigonal, 3 for orthorhombic, 4 for monoclinic, 6 for
triclinic (`METRIC_DOF`, already in `schemas/indexing.py` and already consulted
for a *different* check). Eighteen lines against one free parameter is
eighteen-fold over-determined. Conflating the two preconditions is the defect.

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
spread (5 P, 2 I, 2 F, 1 R) but that is the easy axis.

This has a sharp consequence already recorded in the contamination row: Coelho
(2003) Table 6 publishes rates for orthorhombic / monoclinic / triclinic, and we
hold **0 / 1 / 0** datasets in those systems. The WP-1041 row says the rates are
"not comparable" because one cubic lattice is not an ensemble of structures —
true, and the deeper reason is that *we have no real data in any system that
table covers*. The engines are exercised on low symmetry only synthetically.

So a claim like "never wrong, and silent more often than right" is currently a
statement about high-symmetry lattices, and should say so until the corpus moves.

**Where the missing data is** (corpus search, 2026-08-06 — the user asked for the
literature to be checked before anything is requested). **NBS Monograph 25** is the
answer for the peak-list axis: §20 alone carries 16 orthorhombic and 18 monoclinic
patterns, and its 21 sections hold **29 triclinic** ones. US Government publication,
so public domain; same institution as the SRM standards already in `tests/data/`;
and it is *DICVOL04's own test corpus*, so taking it means adopting a published
protocol and inheriting a comparison baseline — Boultif & Louër (2004) §5 print the
per-pattern times this package is already quoted against (ten triclinic sets under
2 s, ten at 60-360 s, three at 1215 / 3307 / 3770 s). The catch is that a Monograph
entry is a **peak list, not a profile**, so those rows report `not_validated` and
exercise the engines without exercising `validate_by_lebail`.

For profiles the corpus is thinner than it looks. CONOGRAPH's benchmark
(Oishi-Tomiyasu 2014, Table 2) spans 25 patterns including 3 orthorhombic and 5
triclinic — but every one is credited to a named individual, and the only publicly
released members are the **SDPDRR-2** samples, which are monoclinic and cubic. So
this is two acquisitions, not one, and the Monograph is the one to do first.

### What an agent needs that a gate cannot give

The gate returns `low`/`medium`/`high` and `best_or_none()`. An agent that can
reason wants the *inputs* to that judgement, and several already exist but are
either collapsed or withheld:

* which caveats fired, and whether each is refuting or capping — present, but the
  distinction is not in the serialized answer;
* **Le Bail Rwp**, which on magnetite separates the correct cell from its wrong
  rival 3.1× (0.2545 against 0.7884) *while* `predicted_but_absent` reads 2 and
  **0** — i.e. the fit statistic is decisive exactly where the gated detector is
  blind. The gate reads the detector and not the Rwp;
* which figures of merit were computable and which were not, rather than a refusal
  to compute any;
* what the search covered — `systems_searched` and `search_complete` exist and are
  the model for the rest.

## Non-goals

- Loosening the **gate**. `high` should stay as strict as it is; unattended use is
  what it is for, and WP-1041 measured that a broken filter once produced the
  right answer for no reason. This WP adds a road around the gate, not through it.
- Retuning `borda_scores`, or landing an aggregate. WP-1041 measured and refuted
  the candidates; that question needs a new panel member, not another sweep.
- New engines.

## Tasks

- [ ] **Separate "can this be searched" from "can this be scored".** A list with
      at least `METRIC_DOF[system] + margin` usable lines is searchable; twenty
      remains the bar for the figures of merit. Below twenty the search runs and
      every figure that is undefined is reported **absent with its reason**, never
      silently zero or quietly omitted.
- [ ] `IndexingResult` gains a machine-readable **evidence** view: per candidate,
      each caveat with its `refuting`/`capping` kind, the Le Bail Rwp and both
      detector counts, which figures were computable, and what the search covered.
      No new physics — this is surfacing what the pipeline already knows.
- [ ] **The gate reads Rwp.** Measured on magnetite: `predicted_but_absent` is 0
      on the wrong cell and 2 on the right one, while Le Bail Rwp is 0.79 against
      0.25. Decide whether a Rwp ratio between rival candidates becomes a caveat,
      and measure it across the corpus before wiring it (WP-1041's lesson: a
      margin is comparable within a member, not across members).
- [ ] Re-measure the fluorite row: it currently asserts an abstention that this WP
      makes wrong. It should assert that a short clean list is **searched, ranked
      and reported unscored**, and that the certified cell comes back at rank 1.
- [ ] **Corpus coverage**: add at least one orthorhombic and one triclinic
      real-data set, so the low-symmetry half of the problem is measured rather
      than assumed. Until then, every summary that quotes the scoreboard says
      "high-symmetry" out loud.
- [ ] `docs/AGENT_PROTOCOL.md` gains the split: what an unattended operator should
      read (the gate) and what a reasoning consumer should read (the evidence),
      with the fluorite case as the worked example of why they differ.

## Acceptance

A clean 18-line cubic pattern is indexed, ranked and reported with its figures
marked uncomputable — no abstention. The gate's own verdicts are unchanged on
every existing acceptance row. `docs/VALIDATION.md` regenerates.

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1041's handover — the gallery, the scoreboard, and the contamination curve
  that exposed the `n_unindexed` limit.
- `PEAK_MIN_USABLE_LINES` and `METRIC_DOF` in `schemas/indexing.py` — the two
  preconditions this WP separates.
- `indexing/workflow.py` — `validate_by_lebail`'s docstring carries the measured
  Le Bail-vs-Pawley table that says why the validator must stay constrained.
