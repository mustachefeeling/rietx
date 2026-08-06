# WP-1042 — Anytime results, and `quick` as the default

Milestone: v1.0 · Status: ⬜
Depends on: WP-1037

## Goal

`index_pattern()` produces a usable ranked shortlist early instead of only at the
end: (engine × system) units scheduled cheapest-system first, progress and
provisional candidates streamed, and a `quick` preset as the default. This is the
behaviour-changing half of the UX work, and it carries the acceptance re-measure
that forces.

**Scope call, 2026-08-06 (user):** v1 wants a functional and robust engine, not a
headline feature. Volume tightening — the speed play with a measured danger —
moved to the post-v1 fence (§ Deferred below); this WP keeps what makes the
default honest and responsive.

## Context

### The target, and what it actually is

The stated design target is TOPAS's indexing module — *a rapid, sufficient, ranked
list*. WP-1037's measurement establishes the honest framing: our 30–150 s per real
dataset is normal for the field (DICVOL04 reaches 3770 s on hard triclinic patterns;
McMaille needs "hours, if not a night" for a full-symmetry search; Conograph's
exhaustive quick search is ≤5 min). So responsiveness has to come from **ordering
and reporting**, not from a smaller search box: the hard cases are irreducibly slow
and pretending otherwise would be an unmeasured cost model, which is what WP-1030's
method lesson forbids.

### What WP-1037 landed, and the baseline it measured

(folded from `### Inherited`, 2026-08-06)

- `Progress` (one flat revisable ladder on `stage_start`/`stage_end` — do not add
  a second ladder on the same kinds), `Deadline` (the whole-run clock as a cancel
  token; `remaining` is what the scheduler below consults), and `estimate_ceiling`
  whose `MEASURED_TYPICAL_SECONDS`/`MEASURED_VALIDATION_SECONDS` constants must be
  re-measured when `quick` changes the default protocol.
- The baseline, measured on the corpus as it stood (8 datasets; full table in
  WP-1037's handover log): *time to first visible candidate* is today the end of
  the last engine's last system, since nothing streams — zincite **165.8 s of a
  177.3 s run**, corundum 31.4 of 49.7, hl2 33.4 of 43.2, fap 1.1 of 83.7. On fap
  the tail is validation: 74 of 84 s over eight unbudgeted Le Bail fits.
- A trap measured, not guessed: post-search consensus is the uninterruptible
  block — the geometric-ambiguity enumeration cost 45 s of a 105 s ceiling-bound
  corundum run (12 candidates × 3.75 s) until `consensus(..., cancel=)` learned
  to skip and report `ambiguity_checked`. Anything streamed mid-run sits *before*
  that block; keep new work token-aware from the start.
- The GUI run record's three progress fields (`_run["stage"]`/`["stage_index"]`/
  `["n_stages"]`) have **three** writers since WP-1016 — `stage_start` for a fit
  and for an indexing run, `fit_start` for a series, gated on `series_index`
  being present in `data`. Two consequences for streaming: a new run kind that
  stamps `series_index` would inherit the series framing by accident, and richer
  progress means three writers to keep honest, not two. The additivity rule held
  throughout — no new `EventKind` was added for any of it.

### The scheduler is the work: the order exists, the loop ignores it

`SYSTEM_ORDER` (`indexing/engines.py`) is already cubic → hexagonal → trigonal →
tetragonal → orthorhombic → monoclinic → triclinic, already documented as "the
order every engine searches in", already overridable via `SearchSpec.systems` —
the *ordering* landed with WP-1037. What did not change is the run loop:
`index_pattern` iterates **engine-major** — each engine finishes all seven
systems before the next engine starts — so a binding deadline truncates whole
*engines* (`engines_not_run` in the budget diagnostic exists because of this),
and which candidates keep their finders depends on which engine the clock
happened to catch. A candidate found only by the engine that ran first grades
`low` structurally (fewer than two finders), so the deadline as shipped degrades
*confidence*, arbitrarily, rather than *coverage*, predictably. That is a
robustness defect dressed as a budget.

So the task is the **scheduler**: run (engine × system) units system-major — all
engines finish cubic before any starts hexagonal — consulting
`Deadline.remaining`. A deadline then sacrifices trailing systems for every
engine equally, a completed system holds all engines' answers (which is what
consensus and streaming need), and `search_complete` / not-reached stay clean
per-system states. `consensus()` runs once, post-search, today; streaming
graded candidates for early systems needs it callable per completed system (or
incrementally). Keep `SYSTEM_ORDER` the one authority for the order — do not
derive a second ordering from metric DOF (hexagonal, trigonal and tetragonal are
all 2 DOF, so DOF alone cannot even reproduce the order; the tiebreak is
Conograph's measured per-system gradient, cited below).

### Why the first design — "drop the slow engine" — is wrong

It was the obvious way to make a fast default and it fails twice, silently:

- `consensus.grade` returns `low` when `len(set(found_by)) < 2`. A one-engine
  default grades **every** candidate `low`, and `low` stops meaning "refuted"
  and starts meaning "you ran the default".
- `trial_error` sets `search_complete = True` when it finishes its trial set.
  That means "I covered my table", not "no cell of this symmetry exists". A
  one-engine run therefore carries **no** `search_incomplete` caveat and reads
  as *more* complete than a full-consensus one.

So `quick` keeps all three engines (dichotomy, trial_error, svd — the third
landed with WP-1040) and the consensus gate. A single-engine run stays available
via `engines=` and gains an `INDEX_SINGLE_ENGINE` **diagnostic** — not a caveat,
because a *capping* caveat cannot explain a `low` that `grade` produces
structurally. **Open question, not answered here:** whether the three-level
confidence vocabulary needs a fourth value once fast single-engine runs are a
legitimate mode.

### What `quick` is

All three engines, all seven systems in `SYSTEM_ORDER`, a default
`total_budget_seconds` chosen from the re-measured typicals
(`estimate_ceiling`'s arithmetic, re-measured under the new scheduler), and
**budgeted validation** — the fap profile shows unbudgeted Le Bail fits are the
tail, so validation draws on the same `Deadline` per candidate rather than
running open-ended. Nothing else is narrowed: no engine dropped, no system
dropped, no search box shrunk. A `quick` run that hits its ceiling *reports*
what was not reached (WP-1037's states) rather than having silently searched
less. The slower preset is today's behaviour (no ceiling); the preset that ran
is recorded on the result.

### The honest cost of cost-ordering

With a binding total deadline, system-major scheduling means the systems that get
sacrificed are the **low-symmetry ones** — exactly where indexing is hard and
where a user most needs the answer. That is acceptable only if WP-1037's *not
reached* state is loud in the result, the CLI and the GUI. The default
`total_budget_seconds` must be chosen knowing triclinic is what gets cut.

### Streaming

The trap is that streaming raw candidates may be *worse* than waiting. Rank
comes from Borda over the FoM panel **after** cross-engine merge, dedup, the
Bravais screen and the gate; a freshly found engine candidate has none of those,
so a streamed list would reorder and shrink as the run proceeds. Stream
**progress facts** (units done, elapsed/remaining, count so far, best M₂₀ so
far) always; stream cells only as explicitly *provisional*, never carrying a
`confidence` — except that a system the scheduler has *completed* has been
through consensus and can stream graded. Decide this in the design, do not
discover it in the GUI.

Event mechanics are decided here too: progress facts and provisional candidates
ride as `data` fields on the **existing** ladder kinds — an open dict, no
`EVENT_SCHEMA_VERSION` bump. If implementation finds a new kind necessary, that
is a version bump and a deliberate decision, not a detail (`history/events.py`
has the rule and both halves of its test). The shape a candidate takes once
consensus has run is WP-1043's evidence view — the two WPs share that schema;
do not fork it.

### The dominant cost of this WP

Flipping the default is not a tail item. Acceptance rows assert specific ranks,
M₂₀ values and confidences, so many will move; `docs/VALIDATION.md` regenerates;
`validation_matrix.py` Claims move; and the scoreboard — **generated** since
WP-1041 (`python -m tests.indexing_gallery` from the sidecars; 9 datasets:
6 first / 2 below first / 1 refused / 0 promoted) — re-runs rather than being
retyped. Budget the re-measure as the bulk of the work, not the finish. Queue
order puts WP-1043 first, and its fluorite change moves the "1 refused" row —
so the re-measure here is the one that counts; do not hand-patch numbers in
between.

### Licensing

Concepts from DICVOL04/TOPAS/McMaille/Conograph via their published papers; no code
ported from any of them.

## Non-goals

- The ceiling, the deadline, the progress ladder — WP-1037, landed.
- Changing what any engine searches *within* a system.
- Volume tightening (§ Deferred below).
- The search-control surface — engines/systems/ranges/priors in the GUI and the
  agent schema — [WP-1045](1045-indexing-search-controls.md).

## Deferred post-v1 — volume tightening

Boultif & Louër §4.1: each system is explored to the input volume limit *"unless
a solution has been found with a higher symmetry. If so, the maximum value is
replaced by the volume of the unit cell found and the search continues."*
DICVOL04 can do this because its dichotomy is exhaustive by volume shell and it
explicitly seeks the smallest cell. Our panel has two datasets where a
*supercell* ranks first, and SRM 660c where a **smaller**-volume tetragonal-P
rival is exactly isospectral with the cubic-P truth — so an ungated tightening
silently truncates the remaining search, against the standing **no silent caps**
rule. The gate it needs (a trigger that survived Le Bail validation on a
*completed* system, an `INDEX_VOLUME_TIGHTENED` diagnostic naming the trigger
and the new limit, and the SRM 660c isospectral case as an explicit test that
the rival cannot truncate the cubic search) is designed but unbuilt, and only
becomes cheap once the system-major scheduler exists. Deferred 2026-08-06 on the
v1 robustness-over-speed call; the design above is the record for whoever picks
it up.

## Tasks

- [ ] **Task 0 — does the system-major schedule actually deliver a shortlist in
      seconds?** Using WP-1037's instrumentation, record time to first
      *completed cheap system* (all engines done, consensus over it) and time to
      final ranked list per dataset, against the baseline above. If the answer
      is "no for low symmetry", that is the finding — report it, do not tune
      around it.
- [ ] **The scheduler**: (engine × system) units run system-major over
      `SYSTEM_ORDER`, consulting `Deadline.remaining`; a deadline truncates
      trailing *systems* for every engine equally, never whole engines, so
      consensus never loses a finder to the clock. `consensus()` callable per
      completed system.
- [ ] Progress facts streamed on WP-1037's ladder; provisional candidates
      streamed as `data` fields on existing kinds, **without** a confidence
      field and labelled provisional in the schema; completed-system candidates
      stream graded.
- [ ] `SEARCH_PRESETS` / `SEARCH_PRESET_INFO` in bijection (mirroring
      `PLAN_PRESETS`/`PLAN_INFO` and its meta-test), each carrying worst case
      **and** the measured typical range; `capabilities()` gains a
      `search_presets` arm quoted from the live registry.
- [ ] `quick` becomes the default; `IndexingResult` records which preset ran;
      `INDEX_SINGLE_ENGINE` for explicit one-engine runs;
      `estimate_ceiling`'s measured constants re-measured under the new
      default.
- [ ] **The re-measure**: every acceptance row, `validation_matrix.py`,
      `docs/VALIDATION.md`, and the generated scoreboard re-run from its
      sidecars. Measured time-to-shortlist goes in this WP's handover and the
      v1.0 appendix diary as a **range**, never as a timed test — a wall-clock
      budget in a test is a runaway guard, not a timer.

## Acceptance

A shortlist arrives materially sooner on the high-symmetry datasets — evidenced
by measured ranges in the handover and the diary, not by a timing assertion —
nothing regresses on the low-symmetry rows, truncation is always visible, and
the scoreboard is re-generated rather than restated. (The low-symmetry half of
that sentence is currently measured on synthetic patterns only; the real-data
corpus expansion is post-v1 — see WP-1043 § corpus and the ROADMAP fence.)

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py tests/test_indexing_consensus.py \
    tests/test_capabilities.py tests/test_run_control.py -n auto
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Boultif & Louër (2004), *J. Appl. Cryst.* **37**, 724 — §4.1 the volume-tightening
  strategy and per-system exploration. `/Users/yue/zotero-linker/derived/I2VA3ZAB/`
- Coelho (2003), *J. Appl. Cryst.* **36**, 86 — Tables 3 and 5, the per-system cost
  gradient. `/Users/yue/zotero-linker/derived/5RI7CB42/`
- Le Bail (2004), *Powder Diffr.* **19**, 249 — §IV, on-screen progress and
  save-on-cancel. `/Users/yue/zotero-linker/derived/7AEVVGH6/`
- Oishi-Tomiyasu (2014), *J. Appl. Cryst.* **47**, 593 — quick vs regular search as
  a user-facing mode. `/Users/yue/zotero-linker/derived/NWFJ8YEB/`

## Handover log

- **2026-08-06** — plan revised against the merged tree (user review session;
  no code touched). `### Inherited` folded into Context and deleted. Stale
  claims corrected: the scoreboard defects this WP planned to fix (arithmetic
  not closing, brucite/magnetite prose-only) were fixed at WP-1041's close —
  the scoreboard is generated now — and "both engines" predated svd (WP-1040).
  The cost-ordering task was rewritten: `SYSTEM_ORDER` already *is* every
  engine's search order, so the real gap is the engine-major run loop, under
  which a deadline cuts whole engines and with them consensus; the task is now
  the system-major scheduler. `quick` got a definition (§ What `quick` is).
  Volume tightening deferred post-v1 on the user's robustness-over-speed call,
  with its gate design recorded in § Deferred. The control surface
  (engines/systems/ranges + analogue priors, GUI and agent alike) split to
  WP-1045. Acceptance rephrased so "sooner" is a diary measurement, not a
  timed test.
- **2026-08-04** — created by splitting WP-1037, whose first draft was twelve
  commits across ~18 files and carried a full acceptance re-measure — not one
  session. Everything that changes an answer lives here; WP-1037 keeps only what
  changes none. The volume-tightening danger and the streaming-rank problem were
  found by reviewing that draft against `consensus.py` and the SRM 660c row, not by
  measurement.
