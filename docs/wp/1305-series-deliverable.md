# WP-1305 — The series deliverable, and the checks the agent ran by hand

Milestone: v1.3 · Status: ✅ 2026-08-29 — §4b's fourth deliverable and the rows it
prints; `suggest` answers in ΔBIC as well as Δχ²; a flagged step checks itself
against an independent cold pair at +5 % of a 68-pattern chain
Depends on: 1304 (the text lands in `SKILL.md`)

## Goal

§4b names the fourth deliverable and its stopping rows; `suggest` answers the question
the agent actually had (ΔBIC per candidate, not only Δχ²); whether a
`SEQUENTIAL_DISCONTINUITY` can verify itself is measured and decided.

## Context

- **The hole in §4b.** It answers "good enough" for three deliverables (phase ID, QPA,
  structure). The ramp run's deliverable was none of them: "what does the cell do with
  temperature" is a parameter against a series variable. The agent built its own stopping
  rules, and they were the right ones: model selection by ΔBIC and the rival χ² ratio,
  never by Rwp; the step verified by an independent **cold** refit at 430 and 440 °C;
  tan θ vs cos θ to separate a cell change from a specimen-height jump; CaF₂ as an
  internal standard bounding 2θ drift to ±27 ppm over 280 K; and the explicit split,
  precision on the shape of a(T) at ±0.00015 Å, no accuracy claim on the absolute beyond
  ~100 ppm, because nothing pinned the 2θ scale. ~34 of its 90 calls went to these
  checks. `suggest` was called 5× and the agent still did fit-with/without by hand, so
  Δχ² ranking did not answer its question; in the 86-run campaign `suggest` was called 0
  times.
- **Stop rules arrive in the brief.** In that campaign the stop criterion came from the
  coordinator's brief every time; one worker in four judged itself by a fit statistic,
  the others by a script exiting or a comparison table matching, which is what an
  orchestrator with no better sentence to copy will ask for. So (a) is written as
  sentences a brief can copy (WP-1304's two-readers rule).

### (a) `SKILL.md` §4b, fourth deliverable: a parameter as a function of a series variable

Deciding rows: `SEQUENTIAL_PATH_DEPENDENT` (an ordering artefact; `direction="both"` is
the only way to have it), `SEQUENTIAL_PERSISTENT_FINDING` (is the phase there at all),
`SEQUENTIAL_DISCONTINUITY` (a real step or a wander: check that pattern's own fit),
`PHASE_UNCONSTRAINED` (held, after WP-1301), plus two things no diagnostic can say and the
agent must: a stated 2θ-scale anchor (an internal standard, a calibrant, or none) and the
precision/accuracy split (esds are precision on the shape of a(T); nothing pins the
absolute without an anchor). The operational definition, written once: *good enough is
reached when every quoted number names the one thing that would have to be wrong for it
to be wrong, and that thing has been checked.*

**The row is paid for, not appended.** `docs/skill/rietx/SKILL.md` is capped at
32 000 B / 500 lines by `tests/test_skill.py` and measured 31 593 B / 470 lines on
arrival — 407 B and 30 lines of headroom against a row worth ~700 B. WP-1304's rule
decides where the difference comes from: **a lookup leaves the body, a rule and its
decisive number stay**, so the long-form evidence goes to `references/judging.md` (which
already holds §4/§4b's measurements under per-deliverable headings) and the cap is not
raised — raising it is the decision the cap exists to make visible.

**Which call prints the rows.** The body points a reader at `ref.summary(deliverable=…)`,
so the name has to be one that call accepts, and the §4b row names the rows it prints.
`Refinement._deliverable_lines()` already routes `deliverable="series"` to a branch
printing `"series deliverable rows: pending WP-1305 a"`. But a caller of
`refine_sequential` holds no `Refinement` at all, and no single pattern carries a
`SEQUENTIAL_*` row, so `SeriesResult.summary()` — the series' own termination view —
is where the deciding rows have to live; `Refinement.summary(deliverable="series")` says
what one pattern of a series can answer and names the other call.

### (b) `delta_bic` on `CandidateGroup`

`schemas/suggest.py:82-94` (79e5ae82): `gain − len(members)·ln(N)` with N the residual
length the probe used, from `report/layer2.delta_bic`'s form (Schwarz 1978) under the
Gauss-Newton prediction (the first-order equivalent of N·ln(χ²_r/χ²_f); stated as such in
the field doc and the manual). `_summary` (`strategy/suggest.py:183-202`) quotes it;
WP-1302's termination view prints it as its condition (c). `SCHEMA_VERSION` bump. Test:
on a fit where freeing a parameter is refused by ΔBIC in a full refit, the predicted sign
agrees (the ramp's `sample_displacement` at 25 °C, ΔBIC +6.7 measured by the agent;
synthetic). WP-1302 left the consumer stubbed: `Refinement.summary()` prints
`"next: run suggest"` unconditionally for stop condition (c), and
`docs/manual/using/results.md` § Printing a result documents that placeholder by name —
both take the real ΔBIC line here.

### (c) Discontinuity verification, measure first

`SequentialRefinement.fit(..., verify_discontinuities=False)`: after
`_discontinuity_diagnostics`, for each hit cold-fit patterns k and k+1 through
`_fit_one(..., previous=None)` (history suffix `.verify`), attach `value` = cold step /
chain step and a message clause. The module docstring (`sequential.py:55-68`) stays true:
this is a post-walk check, never a ladder trigger. **Decision rule, fixed before
measuring:** on the ramp it must separate the real step (430→440 °C, ratio ≈ 1) from the
CaF₂ wander (284→295 °C; after 1301 there should be no such diagnostic at all, and the
value is then the step's reproduction) and cost ≤ 10 % of the chain's wall clock. Ship
default-off if the cost bar fails; do not ship if the separation fails; record either
outcome here.

**Measured 2026-08-29, darwin/arm64 `[dev]`, no other session running — it ships,
default-off as declared.** Reproducing the 2026-08-26 run's *own* protocol
(`agent_call.txt` verbatim, forward only) on its 68 recorded patterns: the chain
**11.6-12.0 s** over three runs against **12.1-12.2 s** with the check, **+5 %**
best-of-3, inside the ≤ 10 % bar. On the reference protocol of `ramp.py` (a
narrower plan, 3.8-4.3 s) the same four steps cost **+9 %** — the cost is 2 cold
refits per flagged *pattern*, so it scales with what is flagged and not with the
series, and both chains flagged 4 steps over 4 patterns.

The separation resolved as the rule anticipated it might: **the CaF₂ wander is
gone**. Under WP-1301 `PHASE_UNCONSTRAINED` fires on `phases.1.cell.a` in 40 of
68 patterns (the audit's own count) and the cell is *held* rather than walked, so
no discontinuity is raised on it at 284→295 °C at all. What remains is the real
transition — `phases.0.cell.{a,b,c}`, one step through three tied edges, 0.01757 Å
at 430→440 °C — and the CaF₂ scale's onset at 481→492 °C; **all four reproduce at
1.00** under an independent cold pair. So the criterion's fallback clause is what
was measured: the value is the step's reproduction.

The other direction (a chain-made step, ratio ≪ 1) therefore has no case left on
this dataset and is **not claimed as measured**; it is pinned in
`tests/test_sequential.py` on canned cold fits instead, where the arithmetic is
what is under test.

## Non-goals

A general model-selection engine; Hamilton's R-ratio (ΔBIC is the protocol's choice, §8).
Any change to the ladder or `_reseed_needed`.

## Tasks

- [x] (a) the §4b text in `SKILL.md`, as copyable sentences, plus the rows it names:
      `SeriesResult.summary(deliverable="series")`, and `Refinement.summary
      (deliverable="series")` answering with where a trajectory is decided.
- [x] (b) `delta_bic` + `_summary` + `SCHEMA_VERSION` bump + docs (`using/report.md` §
      Which parameter to free next — where `suggest` is actually documented; `refining.md`
      only mentions it — plus `results.md` § Printing a result and the release notes) +
      the sign test.
- [x] (c) the verify flag behind the decision rule; the measurement in the handover
      with wall-clock ranges; the decision recorded (above).
- [x] Tests + obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_suggest*.py tests/test_sequential*.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The decision-rule measurement quoted in the handover with wall-clock ranges, never a
single figure.

## References

- Schwarz (1978), *Ann. Statist.* **6**, 461-464 (BIC).
- WP-1016 (series events), WP-1051 (quarantine), WP-1127 (first-rung budget); the ramp
  audit (maintainer memory `agent-surface-audit-insitu-ramp`).

## Handover log

- **2026-08-29** — shipped. Someone refining a temperature ramp can now ask the
  package whether they are finished, and get an answer about *their* question
  rather than about one fit: which parameters the refinement order might have
  invented, whether a step in the curve survives two fits that never saw each
  other, which phases were never really there, and — printed as instructions
  because no file records them — that they must say what pinned their 2θ scale
  and that their esds are precision on the *shape* of the curve, not accuracy on
  its absolute. `suggest` now answers the question an agent actually asks before
  freeing a parameter: not "which has the most leverage" but "does the leverage
  pay for the parameter", which at 22 000 channels is a different question.
  What it cost: a required field that a stored 1.2 suggestion will not validate
  against, and 283 bytes of a body that had 407 left.

  **Done.** (a) A fourth row in `SKILL.md` §4b, *Trajectory — a parameter against
  T, t, p or composition*, naming four diagnostics as stopping criteria for the
  first time and the two statements no diagnostic can make. It prints from
  **`SeriesResult.summary(deliverable="series")`** — decided here, against the
  Inherited note's assumption that `ref.summary(deliverable=…)` would carry it: a
  caller of `refine_sequential` holds no `Refinement`, and no single pattern
  carries a `SEQUENTIAL_*` row. `Refinement.summary(deliverable="series")` answers
  with where it is decided and the two caller-supplied statements, and
  `schemas.results.DELIVERABLES` is the one vocabulary both read.
  (b) `CandidateGroup.delta_bic`, `SCHEMA_VERSION` 0.13 → 0.14, and WP-1302's
  `"next: run suggest"` placeholder replaced by the number.
  (c) `SequentialRefinement.fit(verify_discontinuities=False)`.

  **Measured** (darwin/arm64, `[dev]` — no jax, no torch — python 3.12.12,
  nothing else running):
  - **Full suite on the final tree, in two selections, nothing else running:
    3432 passed / 122 skipped (1:55) fast and 150 passed / 11 skipped (20:17)
    slow — 3582 / 133.** `origin/main` had not moved since the branch was cut
    (`fe677a62`), so this *is* the merged tree. 22 tests added over the WP (19
    fast, 3 slow), no new skip; the fast selection's own arithmetic is exact
    across the review round (3428 → 3432 for the four tests added after it).
    The WP-level baseline was not re-measured locally — CI's job
    (`tests/CLAUDE.md` § Running) — and WP-1304's quoted 3558/131 was taken
    *before* its own review round, so the difference against it is not an
    accounting of this WP's additions.
  - The ramp, twice, both forward on the 68 recorded patterns of the 2026-08-26
    run. Its **own protocol** (`agent_call.txt`): chain 11.6-12.0 s, with the
    check 12.1-12.2 s, **+5 %**. `ramp.py`'s narrower reference plan: 3.8-4.3 s
    against 4.2 s, **+9 %**. Four flagged steps over four patterns either way, and
    the cost is two cold refits per flagged *pattern*.
  - Every flagged step reproduces at **1.00** under an independent cold pair —
    including the real transition, `phases.0.cell.{a,b,c}` stepping 0.01757 Å at
    430 → 440 °C. The CaF₂ cell wander the decision rule named as the *false* step
    no longer exists: under WP-1301 `PHASE_UNCONSTRAINED` fires on it in 40 of 68
    patterns and the cell is held rather than walked.
  - `Refinement.summary()` on 11-BM NAC: **0.71 s** for the whole view, the
    `suggest` probe included (one Jacobian build, no solve); 0.03-0.04 s on the
    synthetic LaB₆ in Le Bail and Pawley.
  - `SKILL.md` 31 593 → **31 876 B** of 32 000, 470 → **465** lines.

  **Decisions worth carrying.** The WP prescribed `gain − k·ln N` for ΔBIC; what
  shipped is `report.layer2.delta_bic` evaluated at the Gauss-Newton prediction
  (χ²_full = SSR − gain), because the prescribed form is that expression only
  where the probe's χ²/N is 1 — and the noise floor one gate over already refuses
  that assumption with `max(chi2_red, 1)`. It is imported *inside*
  `build_suggestion`, the way `indexing/extinction.py` reaches the same function,
  so there is one BIC formula rather than a copy pinned by a test;
  `strategy/suggest.py`'s docstring now says that is the single edge to `report`.
  The field is **required**: a defaulted 0.0 on a model-selection field reads as
  "worth exactly its cost", WP-1076's lie. Bytes for the §4b row came from
  compressing the QPA and resolution-limited evidence to its decisive numbers
  (both already in `references/judging.md` in full) and moving the `rietx compare`
  pointer to `references/surprises.md` beside the §8.1 rule it cites — the cap was
  not raised.

  **The review round** (`/code-review medium --fix`) found seven and applied
  five, all real. Three were the same shape — a line claiming more than it had
  tested: the ordering row read `direction="both"` as *measured* when a cancel
  can leave the reverse chain unrun, so a cancelled series printed "0 parameters
  disagree" for a comparison that never happened; `"nothing ΔBIC admits"` was a
  claim about the whole ranked list from testing only its leader, and since
  groups rank by Δχ² while ΔBIC charges `k·ln N`, a lower group can be admitted
  while the leader is refused; and the steps verdict read an absent `value` as
  "not verified" when it equally means "verified, and the cold pair determined
  nothing". It also caught the verification pass ignoring the chain's `cancel`
  token, and a docstring quoting numbers the handover contradicts. Two it left
  open I took: the ratio is now **signed**, because a cold pair stepping as far
  the *other* way was reported as 1.00 — the one reading the check exists to
  rule out — and `_discontinuity_diagnostics` is deleted, a second name for
  `_discontinuity_steps` with no production caller left.

  **Gotchas.** `Diagnostic.value` is the verification ratio and stays `None` when
  the flag is off or when a cold fit does not determine the path — an absent
  ratio, never a zero. The "the chain made it" direction (ratio ≪ 1) is **not
  measured on real data**: after 1301 the ramp has no false step left to catch, so
  it is pinned on canned cold fits in `tests/test_sequential.py`, where the
  arithmetic is what is under test. And the cost bar is data-dependent: +5 % here
  is four flagged patterns of 68, so a chain flagging thirty would pay far more.

  Next: **[1306](1306-powderline-recipe.md)**, the PowderLine recipe — unaffected
  by this WP, which is why it takes no `### Inherited` note. Then
  **[1307](1307-recapture-round-1-1.md)** last, which now has three things to look
  for in a re-capture and a re-runnable ramp harness; its `### Inherited` says
  where.

- **2026-08-28** — created, from the parked v1.3 plan.
