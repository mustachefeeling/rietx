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

**From [1061](1061-workflow-robustness.md), 2026-08-06 — this WP's handover log
is missing, and the session-start hook now flags it.** The two 2026-08-06
sessions that landed `WP-1043:` commits on `main` (the gallery review's three
findings; the full bethanechol run) left no handover entries — this file has no
`## Handover log` section at all — so `.claude/hooks/session_start.py` fires
`⚠ WP-1043 … repair first (/wp-handover, repair mode)` from every checkout.
First act of the next session here (or of whichever session sees the flag
first): reconstruct the entries per repair mode from `git log --stat`, dated
with the commits' own date and marked "(reconstructed post hoc)", adding the
missing `## Handover log` section in the process.

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
modes and absent on the other eighteen runs. The published bar is **+9** (best of
ITO13, DICVOL91, TREOR90, McMaille) and **+12** (best of all); ITO13 alone scored
−14, so this is **below the worst single program in the table**.

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

Two things follow for this WP. The score is a **benchmark**, not an acceptance
assertion — a full run is ~20 min of search — so it needs a runner like
`tests/indexing_gallery.py`, generated rather than typed, or it will rot exactly as
the claim above did. And bethanechol is the sharpest case for the evidence view:
on set F the package holds the published cell at **rank 1** and, with no profile to
validate against, still cannot promote it past `low`.

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
      than assumed. Start from **NBS Monograph 25** (public domain, 16 O and 29
      Tric, and DICVOL04's own test corpus — see above). Until then, every summary
      that quotes the scoreboard says "high-symmetry" out loud.
- [ ] **Make the bethanechol score generated, then move it.** It is −16 against a
      +9 bar and it is currently typed into a WP, which is precisely how the claim
      it replaced went stale. A runner beside `tests/indexing_gallery.py`,
      re-measured by running it, `slow`-marked; the acceptance suite keeps the
      transcription checks and asserts no score.
- [ ] `docs/AGENT_PROTOCOL.md` gains the split: what an unattended operator should
      read (the gate) and what a reasoning consumer should read (the evidence),
      with the fluorite case as the worked example of why they differ — and
      bethanechol set F as the case where the truth is *already* at rank 1.

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
