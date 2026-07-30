# pxrd-refine — Roadmap

Canonical milestone **index**. The content that used to live here is split so
a work session loads only what it needs:

- **[AGENT_PROTOCOL.md](AGENT_PROTOCOL.md)** — how to *use* the package as an
  automated operator: turn-on order, degeneracies, abstention handling,
  diagnostic-code semantics, and the measured findings that change agent
  behaviour. Written for consumers, not maintainers; a WP that adds a
  diagnostic code or a correction should add its row there.
- **[DESIGN.md](DESIGN.md)** — the design record (rationale, locked decisions,
  invariants). Stable; read the specific section a work package links.
- **[milestones/](milestones/)** — shipped-milestone records with the measured
  acceptance blocks (`v0.1.md`, `v0.2.md`, …).
- **[wp/](wp/)** — one self-contained **work package (WP)** per task. Each has
  its own context, commit-sized checklist, acceptance command, and handover
  log. `wp/TEMPLATE.md` defines the format.

## Session protocol

1. **Start** from "Current focus" below (or the WP the user names). Read that
   one WP file — it is self-contained on top of CLAUDE.md. Open DESIGN.md only
   at sections the WP links; do not read other WP files.
2. **During**: land tasks as small commits prefixed with the WP id
   (`WP-0301: …`); check items off in the WP file as they land.
3. **End** — or whenever interruption is a risk: append a dated entry to the
   WP's handover log (done / in flight / next / gotchas), update its Status
   line, and mirror the glyph in the WP index row below.
3b. **Push forward-references downstream.** If this session learned anything
   that changes work in a *not-yet-started* WP — a constant now exported for
   reuse, a design bullet there that has gone stale, a deferral into it, a
   gotcha that would mislead it — edit **that WP's `### Inherited` section**
   (see `wp/TEMPLATE.md`) and name this WP as the source. Step 1 forbids
   reading other WP files, so **a handover log is not a channel to anyone but
   your own successor on the same WP**: a "next WP should…" note left only in
   your own log, or only in "Current focus" below, will never be read. Current
   focus is a rolling narrative and gets rewritten when the next WP lands.
4. **Milestone ships**: record the measured acceptance block in
   `milestones/vX.Y.md`, flip the milestone row here, and check the roadmap
   claims in README.md.

*Step 3b was added 2026-07-24 and applied retroactively the same day: the
handover logs of all 14 then-landed WPs were swept for forward-references and
the results written into 16 downstream WPs' `### Inherited` sections. That
backlog is cleared — new sessions only need to keep up with their own.*

## Current focus

**Indexing: 1018, 1019 and 1020 are done (2026-07-30); the three engines are
next, and they are independent of each other.** Everything an engine shares now
exists and is tested — a fitted peak list with *calibrated* per-line σ (1018), a
gate that abstains rather than searching data that cannot support a search
(1019), and the Q-space core: the quadratic form, the derived metric subspaces,
weighted candidate refinement, reduction, two-opinion Bravais, the figure-of-merit
panel and geometrical ambiguity (1020). [1021](wp/1021-engine-dichotomy.md),
[1022](wp/1022-engine-trial-error.md) and [1023](wp/1023-engine-montecarlo.md) can
be taken in any order or in parallel; each has a fresh `### Inherited` note naming
the five things about the shared surface that are not obvious from the names. The
per-WP narratives are in the indexing sub-table below.

**v0.6 shipped 2026-07-29** — all four rows (0605, 0601, 0602, 0604) landed;
measured acceptance in [milestones/v0.6.md](milestones/v0.6.md). The
milestone's headline is that three of its four deliverables are *decisions
and vocabulary*, not speed: a measured **no-go** on the batched peak-loop
rewrite (its cheap alternative shipped at 1.23×, bit-identical), a bounded LM
that ties scipy TRF as the Amdahl bound predicted but adds **constraint
vocabulary** (the Stephens cone as a linear inequality — brucite 12/43
reflections outside the cone → 0/43, at *higher* Rwp), and an agent JSON
surface whose schema is generated from the live registries. The fourth,
[0604](wp/0604-theory-manual.md), closed the milestone with the Sphinx + MyST
theory manual under `docs/manual/`: ten chapters, ~50 numbered equations
transcribed from the physics docstrings, a 62-entry verified bibliography,
and an anti-divergence design that is *executable* — fenced constants are
injected from the live package at build time, every equation carries a
`*Source:*` line naming the docstring it transcribes, and
`tests/test_manual.py` fails the suite on an uncited bib entry, a
non-importing source symbol, or any `-W` build warning.

**Now: v1.0 — hardening, human GUI, API freeze, PyPI.** The milestone was
**expanded 2026-07-29** rather than a v0.7 inserted (`pyproject.version =
"1.0.0.dev0"` is stamped into every result's provenance and history node, so
an insert would send provenance ordering backwards; precedent: 0603→0408).
The "GUI/notebook widgets" v2+ line is half un-fenced — the **human GUI**
moves into v1.0 as fourteen WPs
([1004](wp/1004-parameter-plan-api.md)…[1017](wp/1017-gui-manual-onboarding.md));
notebook widgets stay fenced. Grounds recorded in
[DESIGN.md](DESIGN.md#locked-decisions): API-first paid off, but the package
is currently unusable by the audience it is for, and the GUI **forces the
missing API into existence** — parameters-as-data, `set_vary`/`set_value`
verbs (their NodeKinds reserved since v0.2, still unused), a project
container, cancellation, exactly one `StageSpec` — so it lands *before*
[1003](wp/1003-api-freeze-pypi.md) (API freeze + PyPI), which becomes the
milestone's last row and freezes a surface that has actually been exercised.
Sequencing: backend API (1004–1007) → server (1008–1009) → frontend
(1010–1017); the stack decision (local web app, stdlib `http.server`,
Svelte 5 + TypeScript with **committed** build assets shipping in the wheel,
plotly served from the installed package, `[gui]` extra = plotly only) is in
DESIGN.md §Outputs' 2026-07-29 amendment. Verifying the plan against the tree
turned up two measured facts, both recorded in 1004: `NodeAction.api_call`
renders `ref.set_values(...)` (plural) for the singular kind `"set_value"`,
and the history `StageSpec` silently drops `Stage.strain_seed` on round-trip —
the spec twins are not merely duplicated, one of them loses data.

**Indexing joined v1.0 on 2026-07-29** as WP-1018…1027, on the same argument
and ahead of the same freeze. The package could refine a structure against a
pattern but could not find the unit cell, so it could not touch an unknown
phase at all — and `index()` is a top-level entry point, a peer of `refine()`,
which the freeze ought to cover after it has been exercised rather than before.
The design is in those ten WP files; the three things that shaped it are in the
indexing sub-table below. Its prior art is real and measured: branch
`guillemot-example-refinements`, pinned as the tag `guillemot-study`
(97ba88d), carries a working two-parameter
autoindexer, a phase screen, and an **audit harness that measured its own
scaffolding** — including the finding that a coverage score cannot tell a
multiphase pattern from a single-phase one of lower symmetry than the engine
reaches, which retracted a claim in that study's own report. That retraction is
this project having already met, on its own data, the failure the confidence
gate exists to prevent.

**That study stays out of `main`, and nothing needs it to come in.** It is an
external-data exercise on another project's examples — not part of the package,
not run by CI, not a WP — so it is pinned by the annotated tag
**`guillemot-study`** and read in place:

```sh
git show --stat guillemot-study                          # what is in it
git show guillemot-study:studies/guillemot/index_hl2.py  # any file
```

Every measured number the indexing design rests on is restated inside the WP
files, so the study is corroboration rather than a dependency; the one artifact
that is genuinely needed (`out/HL2-1_peaks.txt`, the abstention fixture) is
extracted into `tests/data/` by WP-1026 with its provenance. The tag exists so
that deleting or renaming the branch cannot silently strand ten WPs' citations.

**[1004](wp/1004-parameter-plan-api.md) and [1006](wp/1006-run-control.md)
landed 2026-07-30** on branch `v1-gui-backend-api` — the two zero-dependency
rows of the backend-API group, which unblocks 1005 and 1007. Both were framed as
plumbing and both turned up a latent defect the framing had hidden.

1004's charter was "the spec twins are duplicated and one of them loses data",
and the fix (one `StageSpec`/`PlanSpec` in `schemas/plan.py`) was the easy half.
The **third** copy of a stage's arguments is `NodeAction` — the one
`cherry_pick` actually replays from — and it carried neither `seed` nor
`strain_seed`, so a cherry-picked extinction stage started on the softplus
dead-gradient floor and a Stephens stage from the all-zero block: precisely the
two pathologies the seeds exist to prevent, silently, on the verb whose entire
purpose is to reproduce a stage elsewhere. Both are now recorded (additively, so
old nodes replay unchanged), and `StageSpec`'s field set is pinned against
`dataclasses.fields(Stage)` so the next added field cannot repeat it. The
parameter surface itself is `Refinement.parameters()` → the *whole* table with
each held row saying which of three reasons holds it, plus `set_vary` /
`set_values` recording the NodeKinds reserved since v0.2. Its own latent bug:
`ParameterTable` only ever recomputed tied entries while decoding a θ, so a
direct edit of `a` on a cubic cell would have left `b` and `c` behind —
`refresh_ties()` is the missing verb.

1006 has the sharper method result. "No history node, table not committed" is
**not** the whole of *abandoned*: `_run_stage` writes to the models before
solving, so a seeding stage has already put a value nobody chose into the
structure by the time the first residual runs. Cancelling now restores a
pre-stage copy (taken only when a token is present, so an ordinary fit pays
nothing). The other decision went against the WP's own plan on measurement: the
cancel check belongs in the residual wrapper on **both** drivers, not in the LM
callback, which fires only on *accepted* points — an inner loop that never
accepts would never see the token. Measured, zero further evaluations run after
the flag trips, against a ≤2 bar. And the `"index"` run kind the indexing plan
asked for was deliberately **not** added: `EventKind` is closed, a kind nothing
emits is an untested guess, and everything the guess protected is already true
(the token needs no stages/Rwp/node; the event payload is an open dict, so
"engine 2 of 3, orthorhombic" is expressible today). WP-1024 has been told, in
its `### Inherited`, that adding it is its commit — and that a new kind *is* a
version bump where an added field is not.

Landed before that: [1001](wp/1001-validation-matrix.md) (validation matrix) and
[1002](wp/1002-ci-matrix.md) (CI matrix), both **2026-07-29** — see below.
[1003](wp/1003-api-freeze-pypi.md) is not started and now depends on
everything else in the milestone; its `### Inherited` section has been curated
by every shipped WP, and 1002 added the discovery that **"make the repo
public" is the same change as three other things** — it is what makes CI
enforceable, what makes macOS affordable, and what settles the vendored-QARR
question (the GUI adds a fourth: it zeroes the `gui.yml` CI line).

**[1002](wp/1002-ci-matrix.md) (CI matrix) landed 2026-07-29**, every workflow
verified by a real run rather than by review: the fast suite is green on Python
3.11-3.14 on Linux; the full suite including the `slow` real-data acceptance is
**1103 passed / 81 skipped in 43:56**, the first time those suites have run
anywhere but the maintainer's machine, and they passed unchanged; macOS and the
`[torch]` agreement rows are green too.

**Then it was re-sized, because nobody had priced it.** The shipped matrix
billed **21 minutes per push** and **1350 a month** for a nightly full suite —
about 1634 of a free-tier private repo's 2000 minutes gone before anyone
pushed, against eight pushes on the day it shipped. There is no CI budget, and
GitHub's default $0 spending limit means an over-budget matrix does not bill,
it just stops running: the first symptom would have been a month with no CI.
Now three cadences, each priced in its own workflow file — **per push** lint +
the fast suite on 3.13 (5 billed minutes, and *nothing* for a docs-only push,
since `paths-ignore` covers the ROADMAP/WP/DESIGN churn a roadmap session is
mostly made of); **weekly** the full suite plus 3.11/3.12/3.14 (55); **monthly**
macOS + torch (66, because macOS bills at 10×). Scheduled spend 1634 → 303.
The lesson is the one this milestone keeps re-learning in a new costume: a CI
matrix is a recurring-cost decision, and this one had been taken on coverage
grounds alone. The nightly/weekly split is not taste — the first design ran
the full suite on macOS nightly, which at a **10× billing multiplier** is ~400
charged minutes a night against a 2000/month private-repo quota, six times the
whole budget for one job. It was caught by arithmetic before it ran once, and
the fix was to give macOS only the coverage no other platform provides.

The WP's real deliverable is that **the bit-identity goldens' pinning stopped
being a caveat and became a measurement.** `tests/data/README.md` had warned
since WP-0401 that "a different BLAS/numpy build may legitimately differ"; the
matrix showed that sentence is half wrong. A *numpy* change does not move them
— 2.4.6 and 2.5.1, Pythons 3.11 through 3.14, all reproduce every state
bit-for-bit. A *platform* change does, on every state at once, and **nothing
else in the suite fails on Linux at all** (976 passed, 8 failed, all of them
the golden gate). What decided the design is the *shape* of the divergence:
1 ulp on quantities that are a single arithmetic chain (`theta`,
`lebail_intensity`, `pawley_x0`) and up to ~1100 ulp — 1.7e-13 relative — on
`y_calc`, which accumulates ~130 windows of transcendental evaluations. A
divergence that grows *with chain length* is a different libm and summation
order, not different code. So the gate is pinned to `darwin/arm64` and skips
elsewhere with that measurement in the skip reason, rather than being relaxed
to a tolerance: any tolerance wide enough to absorb a libm difference is wide
enough to absorb a real one, and the gate's entire content is "no refactor
changed a single computed number". The general rule is in
[DESIGN.md](DESIGN.md#testing--validation-policy).

Then the weekly run narrowed it once more, and this is the part worth carrying:
a **hosted** macOS/arm64 runner reporting the *same* numpy, scipy and
Accelerate as the capture machine reproduced 7 of 8 states and missed one by
**exactly one ulp** — with local runs bit-stable at 1/2/4/8 BLAS threads, so
not reduction ordering. The pin is to a *machine image*, which nothing visible
from Python can fingerprint. So `("darwin", "arm64")` is the right predicate
for *worth attempting* (7/8 at one ulp against 8/8 at ~1100) but not a promise,
and **no CI environment asserts these bits at all**: the weekly job reports the
comparison and fails only if the goldens *skip*. The gate is maintainer-machine
evidence, exactly the shape of the Apple-GPU gap — and is now recorded as one
rather than implied away by a green badge.

**A Windows probe was run after the scope was met, and it found a real bug.**
Not in the WP's scope (Linux + macOS) but cheap to answer by running it: the
fast suite went **7 failed → 982 passed / 115 skipped / 0 failed** on
`windows-latest`. Six of the seven failures were `'charmap' codec` decode
errors in `tests/` — the suite was less portable than the code it tests — but
the seventh was ours and user-facing: `write_qpa_table` handed `csv.writer`
output, which already ends `\r\n`, to `write_text`, so text mode translated
each `\n` again and **every row of an exported QPA table ended `\r\r\n`**.
Invisible on POSIX, which is why four milestones of acceptance runs never saw
it; its sibling `write_reflection_table` had the `newline=""` idiom right all
along. Every text read and write in the tree now names `encoding="utf-8"`
(the default is cp1252 on Windows, UTF-8 here), guarded by AST rather than
grep in `tests/test_portability.py` — a line search misses the multi-line call
that survived the first sweep. **Nothing runs Windows on a schedule**, so it is
a measurement, not a supported platform; the claim-or-don't decision is in
[1003](wp/1003-api-freeze-pypi.md).

Two smaller results outlast the WP. **CI reports; it does not gate** —
branch protection returns 403 on a private free-plan repo, so nothing stops a
red push landing on `main`, and that is registered as a validation gap rather
than left implied by a green badge. And **the jax rows are compile-bound in a
way a cache cannot fix**: the `[dev,jax]` job costs ~8 min against ~3 for the
numpy-only ones, and deleting `tests/.jax_cache` locally reproduces the shape
(12 s warm → 107 s cold for the two jax files) — but an `actions/cache` of that
directory restored cleanly on its primary key and changed nothing, 8:18 warm
against 8:12 cold. jax's persistent cache holds only XLA compilations above a
time threshold; per-process tracing and lowering are paid every run. The cache
steps came back out rather than staying in as decoration, and the two
alternatives (run the jax rows in one process, or make jax nightly-only) are
left to be measured rather than guessed.

**[1001](wp/1001-validation-matrix.md) (validation matrix) landed 2026-07-29**
(1195 passed / 5 skipped in 7:37). [VALIDATION.md](VALIDATION.md) is now the
per-assertion record of what this package has been shown to do: all 33
acceptance tests registered against a **closed eight-name vocabulary** of what
a bar can be referenced to, generated from `tests/validation_matrix.py`, and
held in bijection with the tree by an AST-collecting guard that costs ~1 s in
the fast suite. The WP's founding scope asked for three tolerance tiers; seven
referents are actually in use, and **the two the scope had no room for carry
the strongest evidence in the repo** — `characterisation` (a row asserting a
model is *inadmissible*, or that a disagreement has a particular shape) and
`prediction` (a parameter-free claim written down before the measurement).
Judged by agreement indices alone, v0.5's eight corrections would score as
having delivered nothing, so `ceiling` (`rwp < 0.20`, `gof < 2.0`) is named
explicitly as a **non**-tier. Three guards encode judgements rather than
bookkeeping: a dataset marked `consistency` may never carry a `certificate`
row (the 11-BM wavelength circularity, made executable), every acceptance
suite must *name* its dispersion setting, and the recorded default must match
the live schema.

Its second half was the one default v1.0 would freeze in the wrong position.
**`Source.dispersion` is now ON by default**, decided on measurement rather
than on WP-0504's recommendation: it is the only correction in the package
needing *no information the caller does not already have* (µR, a habit, a
strain model, a surface — dispersion wants species and λ, both already in the
model), it takes round-robin QPA from RMS 2.26 to 0.69 wt %, and the anchors
survive — SRM 660c's cell does not move at all and SRM 676a's
certificate-grade c/a goes +29.8 → +30.2 ppm against a 100 ppm bar (measured
here; 0504 never checked it) **while Rwp gets *worse*, 14.374 → 14.531 %**.
Against it, and kept: a wavelength inside an absorption-edge interval now
*raises*, because a selective fallback would leave some species corrected and
others not — manufacturing exactly the unequal cross-phase bias the correction
exists to remove.

The lasting result is not the flip but what absorbing it exposed. **21 tests
moved, and nine were bit-identity goldens with no opinion about dispersion at
all — they simply inherited it**, and the failure list could not distinguish
"this protocol deliberately excludes the correction" from "nobody thought
about it". Making every pinning test *declare* its physics fixed all nine
**without regenerating a single golden**, which is itself the evidence the
flip touched physics and not plumbing. That rule — a test that pins a number
declares its physics rather than inheriting a default — is the v0.2
protocol-adoption lesson one level up, and it is now in
[DESIGN.md](DESIGN.md#testing--validation-policy) and guarded. Two knock-ons
are recorded rather than tuned away: light-atom ADPs come back *less precise*
even as they come back *less biased* (rutile U11/U33 separate at 1.9σ with the
block on against 2.2σ without, because f″ raises the heavy atom's share), and
the calibrate→freeze→refine size/strain recovery degrades from 27 % low to
39 % — measuring it both ways showed that bar had always been marginal on a
degenerate direction.

<details>
<summary>How v0.6 got here — the per-WP narrative (superseded by the record)</summary>

**v0.5 shipped 2026-07-28** — all eight WPs (0501–0508) landed; measured
acceptance in [milestones/v0.5.md](milestones/v0.5.md). The headline is the
milestone's own method result rather than any single correction: **not one of
the eight is well judged by Δ Rwp.** Two provably cannot move it (capillary
absorption moves Rwp by 3e-8 on real data while shifting every Biso by exactly
the predicted 0.0166542 Å²), one moves it the *wrong way* when it is right (a
flat-plate thickness declared on a thick specimen — which is how you learn the
specimen was not thin), three move it while changing nothing quotable, and the
two largest accuracy wins — dispersion taking round-robin QPA from RMS 2.26 to
0.69 wt %, and absorption unbiasing ADPs by up to 1.5 Å² — are invisible in it.
That is why each correction ships with a record field or a diagnostic that says
what it did, and why AGENT_PROTOCOL leads with it.

WP-0508 closed the milestone by answering the two questions it was blocked on
with measurements rather than assumptions: the capillary dataset exists (11-BM's
SRM 660a LaB₆, in the beamline's documented 0.81 mm Kapton bore, µR ≈ 0.5–0.7),
and flat-plate µt is *not* the exactly-singular direction µR is — it keeps
3–47 % of its signature — so it is held fixed on stated grounds rather than on
an identity, with the number reported so a caller can disagree.

**v0.6 — solver, performance & agents.**
[0605](wp/0605-batched-peak-loop.md) closed 2026-07-28, first row of the
milestone, and its deliverable was the *decision*: **no-go on the batched
peak-loop rewrite**, with the cheap alternative graduated to production
instead. The measured story inverts the WP's founding figure — the 2.4× was a
fixed-work microbenchmark, and on the real fits the FCJ padded plane is a
0.58× regression (node-axis padding waste ~2.5×), while the symmetric-row
batch is 1.6× *and exactly bit-equal* (evidence banked for the v2 `vmap`
series). What shipped: an FCJ node memo on exact input equality plus an
`axial_derivs` skip in `derivative_bases` — 1.23× on the SRM 660c protocol,
bit-identical to the last parameter bit, after the WP's own dirty-flag design
measured ≈1.0× because the staged plans free cumulatively and no late stage is
ever position-static. Two profile facts worth remembering: `derivative_bases`
costs ~2× the forward (so forward-only optimisations touch a minority), and
`generate_reflections` re-derives a bit-identical list in six of seven stage
compiles — 12 % of the fit, the cheapest win now on the page, compile-side.

[0601](wp/0601-bounded-lm-solver.md) closed 2026-07-28, the second row of the
milestone, and it landed the way the Amdahl bound said it would: the bounded LM
is **0.74-1.04× against scipy TRF**, reaching an identical minimum on two of
three protocols and ΔBIC −13 on the third. That tie is the *expected* result,
not a disappointment — solver work can buy ≈1.25× at most here, and Coelho's
own λ_new gains with a full A matrix are R_ν 0.96-1.19. What the driver earns
its place with is **constraint vocabulary scipy does not have**: the Stephens
positivity cone σ²(M) = T·θ ≥ 0 is a linear inequality on *functionals* of θ,
and enforcing it takes round-robin brucite from 12 of 43 reflections outside
the cone to 0 of 43 — at a **higher** Rwp, the v0.5 method result once more.

Two things came out of it that outlast the WP. First, **three claims this repo
recorded as measured were wrong and are corrected in place**: the cone guard
tested σ² ≤ 0 and so reported the inert all-zero block as unphysical, which in
turn manufactured the "it fires on isotropic and anisotropic specimens alike"
reading (corundum never leaves the cone at all); and Coelho 2005's printed
damping factor is a no-op only until parameter removal shrinks N_k, after which
it actively degrades the step. Second, chasing an LM stall found that **the FCJ
profile has a genuine corner at S/L = H/L and the default instrument starts
both apertures equal** — identical Jacobian columns, ρ = +1.000 already
reported by the correlation guard, ~2 % error in the analytic axial columns
where every other column agrees to 1e-5, and two drivers escaping it in two
unprincipled directions. That is a parameterisation problem nobody owns;
it is written up in [0604](wp/0604-theory-manual.md)'s Inherited section.

[0602](wp/0602-agent-json-surface.md) closed 2026-07-29, the third row: the
agent JSON surface is one module — `agent.refine_json(dict) → dict` behind a
strict three-task union (refine / refine_multi / refine_sequential), a
three-code error envelope (`INVALID_REQUEST` with per-field dot-paths,
`BACKEND_UNAVAILABLE`, `REFINEMENT_FAILED`) sharing `Diagnostic`'s grammar, and
`tool_definition()` whose schema quotes backends/solvers/plans from the live
registries, with a meta-test that fails when a registry member is missing —
the WP-0408 "fourth name arrived two days after the third" lesson made
executable. The 0308/0505 asymmetries are answered by shape rather than
accident: a joint fit returns null history ids by declaration, a series comes
back in a separate `series` arm with per-entry ids. The WP also closed its
inherited debts: `Provenance.solver` and `StageResult.n_constraint_truncations`
now reach every result, a new `CONSTRAINT_ACTIVE` info diagnostic marks an
answer that pressed the Stephens cone (the only signal a constraint was
*active* rather than merely declared), and the WP-0307 texture orphan is
claimed — `refine_preferred_orientation` joined the Layer-2 vocabulary
(THRESHOLDS_VERSION 0.3), emitted even when Layer 1 abstains because
uncorrected texture is a common *cause* of immaturity.

[0604](wp/0604-theory-manual.md) closed 2026-07-29, the last row — the theory
manual, whose per-WP story is the milestone summary above.

</details>

<details>
<summary>How v0.5 got here — the per-WP narrative (superseded by the record)</summary>

**v0.4 shipped 2026-07-27** — all eight WPs (0401–0408) landed; measured
acceptance in [milestones/v0.4.md](milestones/v0.4.md). The headline is
deliberately two-sided: every backend computes the same Jacobian (and an
all-fp32 Apple-GPU refinement lands 3.5e-8 Å from numpy fp64, confirming the
fp64-host-boundary invariant on real hardware), while device *acceleration* was
measured not to exist at this problem size.

Signed off with the duplication closed rather than documented: the residual row
layout now lives once in `model/rows.py`, the traced residual once in
`backend/traced.py`, and `tests/test_backend_conformance.py` is driven by the
backend **registry**, so a new backend inherits every rule and cannot ship
without its agreement rows. `[torch]` is marked **experimental** — an
independent opinion in the matrix and a route to differentiable-layer use, not
a faster path. What being differentiable could buy later (posterior sampling,
Poisson likelihoods, exact Hessians, the model as a torch layer) is recorded in
[DESIGN.md](DESIGN.md#what-the-differentiable-core-unlocks-deferred-not-planned)
— deferred, not planned.

**Now: v0.5 — corrections & microstructure.** Four rows landed 2026-07-27 in
parallel and were merged: [0501](wp/0501-absorption-corrections.md) (capillary
absorption), [0502](wp/0502-surface-roughness.md) (surface roughness),
[0503](wp/0503-stephens-anisotropic-strain.md) (Stephens anisotropic strain) and
[0504](wp/0504-anomalous-scattering-xraydb.md) (anomalous f′/f″) — the last two
taken out of order; each has its own note below. They are orthogonal in the peak
chain — 0501 and 0502 act on intensity in geometries that exclude each other
(capillary vs flat-plate), 0504 on |F|², 0503 on widths — which is why the
merges were clean. [0505](wp/0505-sequential-refinement.md) (sequential warm
start) landed 2026-07-28 — see its note below.
[0507](wp/0507-anode-wavelengths.md) (anode wavelengths) landed 2026-07-28 —
see its note below. [0508](wp/0508-flat-plate-absorption.md) closed the
milestone the same day: it was a stub needing a capillary dataset the repo did
not have, and the dataset turned out to exist (11-BM's SRM 660a LaB₆, in the
beamline's documented 0.81 mm bore).

**[0507](wp/0507-anode-wavelengths.md) (anode wavelengths) landed 2026-07-28.**
Five anodes joined `CuKa` — Cr, Fe, Co, Mo, Ag, each also as a Kα1-only variant
for an incident-side-monochromated beam. Nominally a data-table extension, and
the table itself is four lines; the work was in the two questions around it.

*Which scale.* All six come from one column of one evaluation — the NIST X-ray
Transition Energies Database (SRD 128), direct-experimental KL3/KL2 — and the
argument for trusting it is internal rather than bibliographic: **that column's
Cu pair is bit-identical to the `CuKa` values shipped since v0.2**, so the
existing entry is unchanged and doubles as the proof the new rows share its
scale. A test asserts it, including the negative half (≠ Bearden's 1.540562).
The textbook alternative, Bearden 1967, differs by 24–26 ppm at Mo/Ag; taking
one anode from it while Cu stays Hölzer is exactly the ~100 ppm cell error the
WP existed to avoid, so "correcting" a row toward the familiar numbers is a
regression, not a fix.

*What silently assumed Cu.* Two things, both found by scoping rather than by a
test failing:

- `background.diagnostics._contamination_flags` returned `[]` for any wavelength
  more than 0.01 Å from Cu Kα1 — so every anode this WP enables would have
  reported `contamination == []`, which reads as *clean* rather than *not
  checked*. It is now per anode (`identify_anode`, exported), with Kβ from the
  same database column. The two ghosts are looked up differently because they
  are different physics: Kβ comes off the target, W Lα1 off the **filament**,
  so W is checked for every anode and Kβ only for a recognised one.
- The `26.6°` graphite monochromator angle in the `bragg_brentano` docstring is
  a *Cu* number, not a property of the crystal — the same graphite sits at 12.1°
  at Mo Kα, where the polarization constant K is 0.511 rather than 0.500.

One finding worth carrying forward: **the one-|F|²-per-source assumption is
weaker off Cu, and measurably so.** The Kα1/Kα2 gap grows from 20 eV at Cu to
173 eV at Ag, and a census over Z = 3–98 × six anodes finds `dispersion.resolve`
refusing 7 of 576 combinations — nothing at all at Cr and Fe Kα (9 and 13 eV
apart, no edge fits between the lines), and at Ag one specimen someone will
actually mount: **Ru, K edge 22.14 keV, right between the lines**. The census is
pinned as a test so a table or tolerance change has to restate it. Relatedly,
`DISPERSION_NEGLECTED`'s severity is anode-dependent — hematite is a `warning`
at Co Kα (180 eV below the Fe K edge, f′ = −3.3 e) and an `info` at Mo Kα
(f′ = +0.3 e). Both are now in AGENT_PROTOCOL §8.11.

**[0505](wp/0505-sequential-refinement.md) (sequential series) landed
2026-07-28** (890 tests green). `SequentialRefinement` / `refine_sequential`
chains N refinements over an ordered series, each warm-started from its
predecessor, and returns a `SeriesResult` of per-pattern summaries plus
parameter *trajectories* — state, not curves, the same rule the history nodes
follow. Distinct from `multi.py` throughout: nothing is shared, only the
starting point crosses a pattern boundary. One history tree per pattern (a tree
is pinned to its pattern by `TreeHeader.data_fingerprint`, and that check is
what stops a node being replayed against the wrong data), chained by annotation
notes rather than parent edges.

The measured results changed two defaults and refuted one design assumption.
On the eight round-robin sample-1 mixtures, under the v0.3 QPA protocol
imported wholesale so only the *chaining* differs: **2863 iterations unchained,
1623 re-walking the staged plan warm, 904 with the plan collapsed into one
stage** — at identical mean Rwp (0.1278) and QPA accuracy identical to the v0.3
independent-fit record (RMS |ΔW| 2.26 wt %, worst 5.13). So `refit="single"` is
the default: the staged turn-on order exists to keep early stages conditioned
from a *poor* starting model, and a converged neighbour is not one. And the
`carry`-glob hypothesis — that chaining a phase scale across a 1 → 94 wt % swing
would be worse than starting cold — **is false**: carrying everything costs 838
iterations against 904 for a carry that excludes the scales and re-seeds them
per pattern. `carry` stays as a control for parameters that must provably not
be chained, not as tuning; the docstring says so rather than the reverse.

Three findings worth carrying forward:

- **A sequential trajectory is path-dependent by construction, and a smooth
  curve is exactly what a poisoned chain produces.** `direction="both"` runs
  the series each way and reports `SEQUENTIAL_PATH_DEPENDENT` per parameter —
  the only check that separates a measured trajectory from an ordering
  artefact, and the one to run on anything publishable.
- **Ratio-based fences need a noise floor, and the σ leg cannot supply it.** A
  softplus coefficient dying on its floor has dp/du → 0, so its esd collapses
  *alongside* its value and the significance test inverts instead of
  protecting: an unrefinable `instrument.profile.y` came back with a median
  step of 4e-16, one step of 1.3e-11 (29 000× the median) and σ ≈ 4e-55, and
  the two chains "disagreed" at 1e16 σ over 1e-60 vs 1e-74. Both fences now
  also require the step to be 1e-9 of the parameter's own magnitude. Any future
  trajectory- or ratio-shaped statistic wants the same guard.
- **The reseed fence never fired on the hostile series.** The collapsed refit
  recovers a bad warm start *within* the fit, so the cold restart is insurance
  rather than a routine mechanism — which is why its mechanics are pinned by
  unit tests rather than by the acceptance suite.

**0502 (surface roughness)** is the flat-plate counterpart to 0501, and lands
the same shape: an opt-in `Geometry.surface_roughness` block with two published
models behind a `kind` seam (Suortti 1972, Pitschke 1993), exactly the identity
when off, folded into all three intensity assemblies so the analytic
dof/adp/March columns cannot drift from FD. Both models were verified against
primary sources *before* coding, which killed two of the WP's own draft claims:
Pitschke's P₀ is dropped (angle-independent ⇒ exactly degenerate with the phase
scale, and the paper never resolved it either), and Suortti's `b` turned out to
be **bimodal** — both b → 0 and b → ∞ are the identity — so its bound, stage
seed and fence come from measured sensitivity rather than convention.

Three findings worth carrying forward:

- **A multiplicative correction is trivially ~0.96 "scale-like".** The first
  roughness↔ADP guard scored that regardless of the data — a guard that always
  fires. `optimize.statistics.block_projection_r2` therefore takes a
  **nuisance** argument: project the scale and background out of the whole
  Jacobian first and read the *partial* R². Measured, that tracks
  identifiability properly (R²(b) = 0.06 → 0.95 as the low-angle reflections
  leave the fitted range), and `ROUGHNESS_ABSORPTION_GUARD = 0.9` sits in the
  gap. Any future intensity correction wants the same treatment.
- **Judge a correction at the reflections, not on the fitted grid.** Real data
  forced this: the IUCr round-robin patterns start at 5° 2θ but their first
  reflections are at 25–32°, and a grid-based fence cheerfully reported a 27 %
  depression no modelled peak ever saw.
- **No dataset in the repo can constrain a low-angle intensity correction** —
  qarr phases first reflect at 25.6/28.3/31.8°, SRM 660c at 21.4°. So 0502's
  real-data result is a *negative* one and it is the fences that are accepted:
  two of three qarr phases collapse to the identity and raise
  `ROUGHNESS_UNCONSTRAINED`, the third slides along the roughness↔Biso
  degenerate direction for 0.0001 in Rwp with ρ(a,b) = +1.000. Roughness is
  therefore **not** a competing explanation for the sample-1 QPA bias, and 0502
  left that shape test alone. WP-0504 later found what *is* the explanation
  (neglected anomalous scattering) and renamed it
  `test_sample1_bias_has_the_dispersion_shape` — 0502's negative result is what
  makes that attribution clean instead of one of two candidates.

0501 narrowed its own scope on evidence. Cylindrical only: flat-plate reflection
off a thick specimen is *exactly* angle-independent (ITC Table 6.3.3.1(1a),
A = 1/2µ) and hence not degenerate with the phase scale but **identical** to it,
so the transmission cases and a real-data capillary acceptance both went to a new
[0508](wp/0508-flat-plate-absorption.md). It implements Rouse et al. (1970) A26
682 eq. (2) rather than the Lobanov fit GSAS-II and TOPAS use, because Lobanov's
coefficients trace only to a conference abstract nobody can obtain.

Two findings worth carrying forward:

- **The correction cannot improve the fit, and that is the point.** Rouse's
  expression factors *exactly* into a constant × exp(c·sin²θ) — a Debye-Waller
  shape — so applying it is an exact reparameterisation of the phase scale and
  the displacement parameters. Rwp is provably unchanged (measured: identical to
  1e-5 percentage points). Its entire content is that a Biso refined without it
  comes back low by **0.489 Å² at µR = 1** (Cu Kα), recovered to four decimals at
  18.8σ. So µR is computed and held fixed, never refined — it is an *exactly
  singular* direction, not a correlated one — and `RefinementResult.absorption`
  reports the bias, because no fit statistic can. That is the WP-0310
  transparency lesson applied before the fact rather than after.
- **Validate a two-argument fit across both arguments.** The available scan of
  Rouse prints b₂ as "−0·0375" when it is −0·3750. That error passes a check
  against the paper's *own* four-decimal table at 0.0015, because the slice used
  (sin²θ = 0) constrains only a₁ and a₂ — and it is 0.0821 wrong at µR = 1. What
  caught it was a quadrature of the exact ITC eq. (6.3.3.4) integral, which
  shares no constant with any published fit. The general form of the lesson is
  in [DESIGN.md](DESIGN.md#absorption-a-correction-that-cannot-improve-the-fit):
  the strongest anchor is the integral a fit approximates, not another code's
  transcription of the same fit.

### Repo-wide audit, 2026-07-28

Not a WP — a sweep for doc/code drift and physics errors across the whole tree,
run at the user's request alongside two new deliverables. What it changed:

- **A real bug, root-caused and fixed.** `np.linalg.pinv` was taking its general
  SVD path on JᵀJ, losing symmetry on the cond ≈ 10²⁰ normal matrices this
  package routinely forms and emitting |ρ| up to 1.6 × 10³ (WP-0502 had logged
  the symptom on the fluorite fit as "worth its own fix"). `hermitian=True` on a
  symmetrised matrix caps it at 1 + 4 ulp. Correlation reporting — and therefore
  the 0.98 guard both 0501 and 0502 lean on — is trustworthy again.
- **WP-0501's b₂ question is settled**, without needing a clean copy of the
  paper: an independently written quadrature of ITC (6.3.3.4) reproduces
  Rouse's own 0.0035 bound with −0.3750 (0.0820 with −0.0375), and the sphere
  coefficients from the same table make the transposition visible without any
  computation (see that WP's "Open for review"). One of the three open items is
  therefore closed; the other two remain judgement calls.
- **Two new deliverables.** [AGENT_PROTOCOL.md](AGENT_PROTOCOL.md) — the
  consumer-facing protocol for driving this package from an agent — and
  `pxrdref compare`, a browser UI comparing refinement settings on the bundled
  standards (`viz/compare.py` + `compare_app.py`, tested in
  `tests/test_compare_ui.py`, whose anti-drift test pins its protocols to the
  acceptance suites').
- **Stale docs corrected**: test counts (835 / 775, ~17 min / ~2.5 min),
  `pyproject.version` 0.2.0.dev0 → 0.5.0.dev0 (it is stamped into every result's
  provenance), README's status header and its missing roughness/extinction rows,
  `symmetry.py`'s now-wrong claim that Friedel merging depends on there being no
  anomalous scattering, and WP-0501's "µR > 1 … not extrapolated" bullet, which
  contradicted both the code and its own "Open for review" item.

The physics itself was checked module by module against its cited sources and
**no errors were found**: FCJ's cos 2φ relation and ξ_max cap, the TCH and Voigt
closed-form partials, the Friedel-average ⟨|F|²⟩ = |A|² + |B|² identity, the
Stephens Λ = (180/π)·10⁻⁶·d²√(ΣS·mono) chain, Sabine's branches, Brindley's τ
series, and the Rouse ΔB = c·λ²/2 bias all reproduce independently.

**0501 left three things open for review** (one now closed above), listed with
what would settle each in
[its "Open for review" section](wp/0501-absorption-corrections.md#open-for-review):
the b₂ coefficient contradicts the printed source (a clean copy of the paper
settles it); µR > 1 is used-but-warned rather than refused, which is a judgement
call and not an obvious one, since LaB6 at Cu Kα in a 0.5 mm capillary is µR ≈ 34;
and the milestone criterion above was weakened on purpose because no capillary
dataset exists in the repo. None blocks further work.

Two live forward notes survive v0.4:

- **[0605](wp/0605-batched-peak-loop.md) is a v0.6 row that behaves like a v0.5
  one.** Its ≈2.4× lands on the **default numpy path** and needs no optional
  dependency; it was found in 0408 rather than belonging where it sits. Pulling
  it forward the way 0408 was pulled forward is the obvious move if anyone wants
  a broad win before more physics.
- **Device acceleration is a scale story, not a backend story** (see the v2+
  note at the bottom): break-even ≈50-65 k elements per kernel, ceiling ≈2.5-3×,
  and one pattern is below break-even even after batching. Do not re-open it as
  a backend question.

<details>
<summary>How v0.4 got here — the per-WP narrative (superseded by the record)</summary>

The backend op shim [0401](wp/0401-backend-op-shim.md) **landed 2026-07-24**
(363 tests green, bit-identity goldens in `tests/test_backend_shim.py`): the
hot path speaks `xp.*` and the residual purity refactors (functional
intensity threading, unconditional off-value evaluation, `where`-masked
guards) are in.  The jax backend [0402](wp/0402-jax-backend.md) **landed
2026-07-24**: `backend="jax"` dispatches a scoped-x64, jit-compiled chunked
jacfwd Jacobian (numpy residual/solve untouched); jacfwd matches
analytic/FD on every family and SRM 660c end-to-end matches the numpy `a`
within 1e-6 Å.  The mixed-precision policy
[0403](wp/0403-cuda-mixed-precision.md) **landed 2026-07-24** (388 tests
green): `backend/linalg64.py` is now the single fp64 host boundary —
`MixedPrecisionPolicy` makes an fp32 residual or solve *unspellable*, and
`cast_columns` hooks in at `_jacobian_for`, the exit point every backend
shares.  SRM 660c under simulated fp32 columns moves `a` by 2.6e-11 Å and Rwp
by 1.1e-13; read that margin as proof of *plumbing*, not of device numerics
(the CPU round-trip captures fp32 representation loss only).  The agreement CI
[0404](wp/0404-cross-backend-jacobian-ci.md) **landed 2026-07-24** (434 tests
green):
`tests/test_cross_backend.py` runs (analytic | central FD | jax | torch |
fp32-policy) × (18 analytic families, Le Bail, Pawley, aniso/PO/extinction,
srm660c, nac) plus the stacked multi-histogram layout and three stage-boundary
plans — every fp64 method inside 8.8e-4 off the documented FCJ S/L == H/L kink,
and the frozen state proved bit-identical across each solve.  Every backend row
self-skips without its package, so the same command is green on a numpy-only
checkout.

Three backend-independent WPs landed 2026-07-24.  Restraint penalty rows
[0406](wp/0406-restraint-penalty-rows.md): bond/angle/value soft restraints as
√w·(computed−target)/σ rows below the data (in JᵀJ, out of Rwp/DW/Bérar-Lelann),
with the analytic nonlinear row-Jacobian chained through the affine constraint
block, a `RestraintReport` + `RESTRAINT_TENSION` diagnostic, and a 6th backend
golden (`toy_restraints`); Rietveld- and single-histogram-only (multi-histogram
deferred — see WP-0308 `### Inherited`).  True Voigt
[0405](wp/0405-faddeeva-voigt.md): `Instrument.profile.shape="voigt"` selects an
opt-in Gaussian⊗Lorentzian peak built on one backend-agnostic Weideman-N=32
Faddeeva `w(z)` (no per-backend `wofz`); TCHZ stays the default, the U,V,W,X,Y
widths and FCJ are shared, and numpy↔jax agree to 1e-16 on `w(z)`.  esd
reconciliation [0407](wp/0407-esd-reconciliation.md): the Bérar-Lelann placement
bug is fixed — reported physical esds now genuinely carry the inflation the
docstrings claim (SRM 660c `a`-esd 2.49e-5 = raw 7.4e-6 × BL 3.38), the returned
correlation matrix is a true Pearson matrix (unit diagonal), and the 0.98
high-correlation guard is live again (it fires on collinear zero-shift ~
sample-displacement); it un-masked two unit tests that had ridden the bug
(extinction↔scale is a genuine ρ≈0.97 degeneracy, not separable; aniso U11/U33
separate at ≈2.2σ against honest esds) — reconciled to the true physics, not
silenced.

The torch backend [0408](wp/0408-torch-mps-backend.md) **landed 2026-07-27**,
and it split into a win and a finding.  *Win:* `backend="torch"` is an
independent fp64 row of the agreement matrix on every config, and
`backend="torch-mps"` gives the **first real-hardware confirmation of WP-0403's
fp32-column policy** — an SRM 676a refinement with the whole peak chain and every
column computed in fp32 on the Apple GPU lands 3.5e-8 Å from the numpy fp64
cell, because the trust region re-measures each step against an fp64 cost.
*Finding:* **MPS is 60-125× slower than numpy** (re-measured for the milestone
record at 46-182×, depending on pattern and quantity)
(`examples/bench_torch_mps.py`), and not for a precision or backend-quality
reason — the residual walks ~130 frozen windows of 200-900 points one at a time
in python, and MPS per-op cost is flat at 110-165 µs from 64 to 65 536 elements,
i.e. pure launch latency.  The obvious remedy was then measured rather than
assumed: batching the peak loop collapses MPS from 10.6 ms to ~0.4 ms at fixed
work — *and numpy from 1.36 to ~0.55 ms*.  A size sweep pins the two numbers that
settle it: **break-even ≈ 50-65 k elements per kernel, ceiling ≈2.5-3×** (the
peak chain is memory-bound, so GPU arithmetic throughput never participates).  So
the batched loop is a **numpy-path win** (≈2.4×, every user, no optional
dependency), scoped as a measure-then-decide spike in
[0605](wp/0605-batched-peak-loop.md); Apple-GPU *acceleration* needs ≈10
synchrotron or ≈60 lab patterns batched together to reach that ≈3× — the
v2-fenced in-situ series — and a single lab pattern is below break-even even
after batching.  `torch.compile` does not help either (2.5× slower on CPU;
per-window recompile failure on MPS).
The two hot-path rules that bind *all* future work are in CLAUDE.md's Conventions
(no frozen numpy constant on the left of an operator against a traced value; a
new op must land on every backend); the torch-specific traps are in 0408's
handover log.

0405/0406/0407 and 0408 were developed in parallel and **integrated 2026-07-27**:
the torch traced residual grew the soft-restraint rows (0406's row layout is
written out in three places — numpy, jax, torch), the agreement matrix gained the
`toy_restraints` and true-Voigt configs so the new derivative paths are covered
on every backend row, and four 1-D·1-D dot products in the restraint geometry
were routed through `xp.matmul` (MPS cannot batch `aten::dot`).

</details>

**Out of order: Stephens anisotropic strain
[0503](wp/0503-stephens-anisotropic-strain.md) landed 2026-07-27** (v0.5,
pulled forward on request; 525 tests green). `Phase.microstrain` is an optional
block of the fifteen S_HKL invariants, with the Laue-allowed subspace *derived*
from the gemmi operators by exact rational algebra rather than tabulated (the
DOF counts reproduce Stephens' Table 1 for all eleven Laue classes, checked
twice — against the published table and against the character count of the
degree-4 symmetric power). It brings the first genuinely hkl-dependent peak
width, a `report/strain.py` Layer-1 diagnostic that recovers an injected 3.46×
directional contrast as 3.45×, and a `toy_stephens` backend golden that jacfwd
traces. The acceptance is a *characterisation*, not a win: on round-robin
brucite the three added patterns improve Rwp 18.55 → 17.90 % with ΔBIC +488 and
still leave the physical cone, so `STEPHENS_STRAIN_NOT_POSITIVE` fires and the
coefficients are not quotable. Two findings were pushed downstream: the cone is
a *linear* inequality a constrained solver could enforce
([0601](wp/0601-bounded-lm-solver.md) `### Inherited`), and Hamilton's R-ratio
test is useless at 7251 channels — it blesses an inert 0.13 % χ² improvement —
so ΔBIC is the statistic to quote ([1001](wp/1001-validation-matrix.md)
`### Inherited`).

**Out of order: anomalous scattering
[0504](wp/0504-anomalous-scattering-xraydb.md) landed 2026-07-27** (v0.5, same
session as 0503; and it supplies the explanation 0502 went looking for and
correctly declined to claim). `Source.dispersion` is an opt-in block applying f′ + i·f″ from
a bundled Cromer-Liberman table (`data/f1f2_CromerLiberman.dat`, DABAX/MIT,
Kissel-Pratt-corrected — **not** xraydb, which needs sqlalchemy, and **not**
Chantler, whose DABAX file carries an ESRF-only restriction over a live NIST SRD
copyright). The load-bearing piece is not that f goes complex — F was already
complex — but that a powder measures the **Friedel average**: `generate_reflections`
merges ±h into one orbit and evaluates one representative, which is exact only
while f is real. The closed form ⟨|F|²⟩ = |A|² + |B|² (A carrying f₀+f′, B
carrying f″, over the *same* orbit sums) is exact, needs no second orbit pass and
no centro/non-centro split, and reduces bit-identically when the block is absent.
The acceptance **re-derives a v0.3 conclusion**: refitting the eight IUCr
round-robin sample-1 mixtures under the identical protocol takes the QPA error
from RMS 2.26 → **0.69 wt %** and worst |ΔW| 5.13 → **1.39**, so the signed bias
v0.3 attributed to microabsorption is mostly neglected dispersion (the giveaway
was fluorite coming back *high*, which microabsorption could not explain). Its
sharpest single result is elsewhere: on pure ZnO, Rwp barely moves but B(O) goes
from 0.022 to 0.429 Å² — a displacement parameter that had been spent absorbing
Zn's missing f′. The default stays **off** so every shipped acceptance number
remains valid; flipping it is a re-measurement of the validation matrix
([1001](wp/1001-validation-matrix.md) `### Inherited`), and per-anode dispersion
checks are written into [0507](wp/0507-anode-wavelengths.md).

**Out of order, landed 2026-07-27: v0.5 surface roughness
[0502](wp/0502-surface-roughness.md)** — backend-independent, so it neither
blocks nor depends on the 0404 → 0408 chain. `Geometry.surface_roughness` is an
opt-in, Bragg-Brentano-only, Rietveld-only intensity multiplier with two
published models behind a `kind` seam (Suortti 1972, Pitschke 1993), exactly the
identity when off, folded into all three intensity assemblies so the analytic
dof/adp/March columns cannot drift from FD, and a 7th backend golden.

Both models were verified against primary sources *before* coding: Suortti via
GSAS-II `SurfaceRough` **and** Pitschke's independent quotation of it; Pitschke
by numerically rederiving its equations from the (OCR'd) paper — Eqs 7/9/10 are
exact identities and Eq 12 reproduces its Table I to ≤1.6 %. Two design
decisions fell out: P₀ is dropped (angle-independent ⇒ exactly degenerate with
the phase scale, and the paper itself never resolved it) and τ is refined
directly rather than t₀.

The measured outcome is a **negative** one, and it is the fences that are
accepted rather than the correction. Roughness is constrained by low-angle
*reflections*, not grid points, and no dataset here has any — qarr corundum /
fluorite / zincite first reflect at 25.6 / 28.3 / 31.8°, SRM 660c at 21.4°. Two
of three qarr phases drive the correction back to the identity and raise
`ROUGHNESS_UNCONSTRAINED`; the third slides along the roughness↔Biso degenerate
direction for 0.0001 in Rwp, with ρ(a,b) = +1.000 and esds 350× the values. So
roughness is **not** a competing explanation for the sample-1 QPA bias, and
0502 left that shape test alone. **0504 then found what is** — neglected
anomalous scattering — and renamed it
`test_sample1_bias_has_the_dispersion_shape`; 0502's negative result is what
makes that attribution clean rather than one of two candidates.

Three things this WP exports downstream (all written into WP-0501's
`### Inherited`): `optimize.statistics.block_projection_r2` with its
**nuisance** argument — any multiplicative correction is trivially ~0.96
"scale-like", so only the *partial* R² carries signal; the rule that a
correction is judged at reflection positions, not on the fitted grid (real data
forced that fix); and a pre-existing `|ρ| > 1` in the reported correlation
matrix under poor conditioning, which undermines the correlation guard that both
0501 and 0502 lean on. **That third one was fixed 2026-07-28** in a repo-wide
audit rather than a WP: `np.linalg.pinv`'s default general-SVD path loses
symmetry on the cond ≈ 10²⁰ normal matrices this package routinely forms
(reproduced at |ρ| ≈ 1.6 × 10³), and `covariance_estimates` now symmetrises JᵀJ
and passes `hermitian=True`. Every reported correlation is a valid Pearson
correlation again, so the 0.98 guard measures the data's degeneracies and not
the linear algebra's.

</details>

## Milestones

| Milestone | Scope | Status | Acceptance |
|---|---|---|---|
| v0.1 | Vertical slice: synchrotron CW, Rietveld + Le Bail | ✅ **shipped** ([record](milestones/v0.1.md)) | 11-BM NAC: a = 10.251285(12) Å, Rwp 9.2%, CaF₂ impurity auto-flagged |
| v0.2 | Lab diffractometer + FitReport attribution + viz | ✅ **shipped 2026-07-22** ([record](milestones/v0.2.md)) | SRM 660c LaB6: a = 4.156895(25) Å (+28 ppm vs NIST value for this dataset, Bérar-Lelann-inflated esd), Rwp 8.7%; GSAS-II FAP tutorial: Rwp 9.73% vs GSAS's 10.05% on identical channels, cell +116 ppm (uniform d-scale convention offset) |
| v0.3 | Multi-phase QPA, Pawley, aniso ADPs, multi-histogram | ✅ **shipped 2026-07-24** ([record](milestones/v0.3.md)) | SRM 676a corundum: c/a +30 ppm vs certificate (absolute axes −313/−283 ppm, uniform d-scale); IUCr round robin: sample-1 worst 5.1 wt% (traces ≤1.3), sample 2 worst 2.9 wt% with brucite March-Dollase r=0.67, sample 4 characterised as the designed Brindley failure (µR fence fires) |
| v0.4 | Differentiable backends: JAX jacfwd, mixed precision, torch-MPS; true Voigt; restraints | ✅ **shipped 2026-07-27** ([record](milestones/v0.4.md)) | Cross-backend Jacobian agreement (analytic/FD/jax/torch × 8 configs + multi-histogram + stage boundaries) inside the 5e-3 rel-L2 fp64 bar; an all-fp32 Apple-GPU refinement of SRM 676a lands Δa = −3.5e-8 Å from numpy fp64 (bar 3e-5); wall-clock reported, not gated — and it is a *finding*: MPS is 46-182× slower (launch-latency-bound) and jit'd jacfwd is within 2.1× of the analytic assembly at best, so the batched peak loop is a numpy-path win (WP-0605), not GPU enablement |
| v0.5 | Corrections & microstructure (absorption, Stephens, f′f″) | ✅ **shipped 2026-07-28** ([record](milestones/v0.5.md)) | capillary absorption validated at **both** levels: the Rouse (1970) cylinder factor against a quadrature of the exact ITC eq. (6.3.3.4) integral across 0 ≤ µR ≤ 1 *and* 0 ≤ sin²θ ≤ 1 (0.0035, the paper's own bound), and on real 11-BM SRM 660a LaB₆ data in a documented 0.81 mm bore — Rwp moves 3e-8, the cell 8e-12 Å, and *both* Biso move by the predicted 0.0166542 Å². Plus the two accuracy wins no fit statistic shows: dispersion takes the round-robin QPA error from RMS 2.26 → 0.69 wt %, and a mis-declared flat-plate thickness biases Biso by up to −1.5 Å² |
| v0.6 | TOPAS-style bounded LM, agent surface, batched peak loop, theory manual | ✅ **shipped 2026-07-29** ([record](milestones/v0.6.md)) | bounded LM 0.74–1.04× vs scipy TRF (CPU — the expected Amdahl tie), identical minima on 2/3 protocols, ΔBIC −13 on the third, and the Stephens cone enforced as a linear inequality (brucite 12/43 → 0/43 outside, at higher Rwp); FCJ node memo 1.23× bit-identical; agent schema generated from live registries with a registry-membership meta-test; theory manual builds `-W`-clean with every fenced constant injected from the live package and five anti-divergence guards in the fast suite |
| v1.0 | Hardening, human GUI, indexing, API freeze, PyPI | ⬜ | full validation matrix green; GUI end-to-end: `pxrdref gui` covers import → edit → refine → inspect → branch → export on 11-BM NAC, with Rwp matching the API-driven acceptance for the same protocol (the GUI is a view, not a second implementation); **indexing scores ≥ +9 on the published bethanechol benchmark** (the best combination of the four classic programs in Bergmann et al. 2004) and abstains rather than ranking a cell on the mixture and unidentified-pattern fixtures |
| v2+ | FPA, neutron/TOF, texture, MCP server | ⬜ fenced | — |

## Work packages

### v0.3 — multi-phase workflows (detailed, ready to start)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0301](wp/0301-wyckoff-constraints.md) | Wyckoff/site-symmetry constraints (affine p = C·θ + d) | ✅ 2026-07-22 | — |
| [0302](wp/0302-atomic-coordinates.md) | Atomic-coordinate refinement | ✅ 2026-07-23 | 0301 |
| [0303](wp/0303-anisotropic-adps.md) | Anisotropic ADPs | ✅ 2026-07-23 | 0301 |
| [0304](wp/0304-qpa-hill-howard.md) | QPA: Hill-Howard ZMV mass fractions | ✅ 2026-07-23 | — |
| [0305](wp/0305-brindley-microabsorption.md) | Brindley microabsorption | ✅ 2026-07-23 | 0304 |
| [0306](wp/0306-pawley-mode.md) | Pawley mode | ✅ 2026-07-23 | — |
| [0307](wp/0307-march-dollase.md) | March-Dollase preferred orientation | ✅ 2026-07-23 | — |
| [0308](wp/0308-multi-histogram.md) | Multi-histogram stacked residuals | ✅ 2026-07-24 | — |
| [0309](wp/0309-exporters.md) | Exporters: reflection table, CIF+esds (structure side landed in 0303), QPA table | ✅ 2026-07-24 | 0304 |
| [0310](wp/0310-acceptance-srm676a-qpa.md) | Acceptance: SRM 676a + IUCr QPA round robin | ✅ 2026-07-24 | 0304, 0305 |

### v0.4 — differentiable backends (expanded 2026-07-24; ready to start)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0401](wp/0401-backend-op-shim.md) | Backend op shim (34 named ops + `window_add`/`segment_sum`; the WP was scoped at "~41" before the survey) + residual purity refactors | ✅ 2026-07-24 | — |
| [0402](wp/0402-jax-backend.md) | JAX backend: chunked jacfwd | ✅ 2026-07-24 | 0401 |
| [0403](wp/0403-cuda-mixed-precision.md) | Mixed-precision policy (CUDA-deferred, CPU-testable) | ✅ 2026-07-24 | 0402 |
| [0404](wp/0404-cross-backend-jacobian-ci.md) | Cross-backend Jacobian CI | ✅ 2026-07-24 | 0402 |
| [0405](wp/0405-faddeeva-voigt.md) | True Voigt via shared Faddeeva w(z) | ✅ 2026-07-24 | 0401 |
| [0406](wp/0406-restraint-penalty-rows.md) | Restraint penalty rows | ✅ 2026-07-24 | — |
| [0407](wp/0407-esd-reconciliation.md) | esd reconciliation (Bérar-Lelann placement) | ✅ 2026-07-24 | — |
| [0408](wp/0408-torch-mps-backend.md) | torch backend (MPS fp32 forward) — moved from v0.6 | ✅ 2026-07-27 | 0401, 0402, 0404 |

### v0.5 — corrections & microstructure (stubs)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0501](wp/0501-absorption-corrections.md) | Capillary (cylindrical) absorption | ✅ 2026-07-27 | — |
| [0502](wp/0502-surface-roughness.md) | Surface roughness (Suortti + Pitschke) | ✅ 2026-07-27 | — |
| [0503](wp/0503-stephens-anisotropic-strain.md) | Stephens anisotropic strain | ✅ 2026-07-27 | — |
| [0504](wp/0504-anomalous-scattering-xraydb.md) | Anomalous f′,f″ (bundled Cromer-Liberman, not xraydb) | ✅ 2026-07-27 | — |
| [0505](wp/0505-sequential-refinement.md) | SequentialRefinement warm start | ✅ 2026-07-28 | — |
| [0506](wp/0506-secondary-extinction.md) | Secondary extinction (Sabine) | ✅ 2026-07-23 | — |
| [0507](wp/0507-anode-wavelengths.md) | Additional anode wavelengths (Co/Cr/Fe/Mo/Ag) | ✅ 2026-07-28 | — |
| [0508](wp/0508-flat-plate-absorption.md) | Flat-plate absorption + real-data capillary acceptance | ✅ 2026-07-28 | 0501 |

### v0.6 — solver, performance & agents (stubs)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0601](wp/0601-bounded-lm-solver.md) | TOPAS-style bounded LM | ✅ 2026-07-28 | — |
| [0602](wp/0602-agent-json-surface.md) | Agent JSON surface hardened | ✅ 2026-07-29 | — |
| [0604](wp/0604-theory-manual.md) | Sphinx + MyST theory manual | ✅ 2026-07-29 | — |
| [0605](wp/0605-batched-peak-loop.md) | Batched peak loop (spike, then decide) | ✅ 2026-07-28 | — |

(0603 — the torch/MPS backend — moved to v0.4 as
[0408](wp/0408-torch-mps-backend.md) on 2026-07-24; the number is left unused so
the history stays readable.)

0605 closed 2026-07-28 with a measured **no-go on the batched rewrite** and its
task-0 cache graduated to production (1.23× on the SRM 660c protocol,
bit-identical): the 2.4×-at-fixed-work figure was a microbenchmark fact, not a
fit fact — the FCJ padded plane is a 0.58× *regression*, and the win that
survives (symmetric rows, exactly bit-equal) is the starting point for the
v2-fenced `vmap` series, not for a single-pattern rewrite. Grounds and the
reopening conditions are in the WP's answers/handover.

### v1.0 — hardening, human GUI & release (GUI WPs added 2026-07-29)

Order: backend API first (1004–1007, each independently useful without the
GUI), then server (1008–1009), then frontend (1010–1017); the freeze (1003)
is the milestone's last row so it covers a surface the GUI has exercised.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1001](wp/1001-validation-matrix.md) | Validation matrix + tolerance policy | ✅ 2026-07-29 | — |
| [1002](wp/1002-ci-matrix.md) | CI matrix | ✅ 2026-07-29 | — |
| [1004](wp/1004-parameter-plan-api.md) | Parameter & plan API surface | ✅ 2026-07-30 | — |
| [1005](wp/1005-project-container.md) | Project container (`.pxrd/`) | ⬜ | 1004 |
| [1006](wp/1006-run-control.md) | Run control: streaming, progress, cancellation | ✅ 2026-07-30 | — |
| [1007](wp/1007-capabilities-guards.md) | Capabilities, structured guards, background export | ⬜ | 1004 |
| [1008](wp/1008-gui-server.md) | GUI server, session model, `pxrdref gui` | ⬜ | 1004–1007 |
| [1009](wp/1009-textdoc-format.md) | Project text document (`.pxt`): format + parser | ⬜ | 1004, 1005 |
| [1010](wp/1010-frontend-scaffold.md) | Frontend scaffold: build, committed dist, shell, plot, console | ⬜ | 1008 |
| [1011](wp/1011-parameter-plan-editors.md) | Parameter editor, plan editor, run controls, disclosure | ⬜ | 1010 |
| [1012](wp/1012-history-report-panel.md) | History worktree, report panel, one-click suggestions | ⬜ | 1010 |
| [1013](wp/1013-text-pane-sync.md) | Text pane (CodeMirror 6) + two-way sync | ⬜ | 1009, 1010 |
| [1014](wp/1014-import-structure-editing.md) | Import & in-GUI structure/instrument editing | ⬜ | 1008, 1010 |
| [1015](wp/1015-structure-viewer.md) | Structure viewer, zero new dependencies | ⬜ | 1010 (1014 soft) |
| [1016](wp/1016-sequential-series-panel.md) | Sequential series panel | ⬜ | 1008, 1010, 1011 |
| [1017](wp/1017-gui-manual-onboarding.md) | GUI manual, in-app help, onboarding | ⬜ | 1011–1016 (soft) |
| [1003](wp/1003-api-freeze-pypi.md) | API freeze + PyPI | ⬜ | 1001, 1002, 1004–1027 |

### v1.0 — indexing (added 2026-07-29)

Unit-cell determination from a pattern, and the peak picking it needs. Added
into v1.0 on the same argument that un-fenced the GUI: `index()` is a
top-level entry point, a peer of `refine()`, and the freeze (1003) should
cover a surface that has been exercised. It also closes a seam the package
declared long ago — `report/layer2.py` has emitted the
`reindex_or_recheck_cell` action since v0.2 with nothing behind it.

Order: peaks and quality first (1018–1019, useful on their own), then the
shared core (1020), then the three engines (1021–1023, independent of each
other), then consensus (1024), space groups (1025), acceptance (1026), GUI
(1027).

**[1018](wp/1018-peak-picking.md) closed 2026-07-30**, and the row that had
carried the 🔄 glyph ("landed but not finished") is the only one that ever has.
What closed it is the **σ pull calibration** — the gate the whole downstream
tolerance model rests on, because every indexing tolerance is a multiple of the
σ(2θ) `pick_peaks` reports, and Rwp, χ² and eyeball overlays cannot see a σ that
is uniformly 40 % too small. Measured over ~1300 fitted lines per configuration,
from 100 fixed-seed Poisson realisations of a forward-model LaB₆ pattern:
`(2θ_fit − 2θ_true)/σ_fit` has **mean +0.032 / std 0.971** on a synchrotron
single line and **−0.083 / 0.980** on a lab Cu Kα doublet, against `|mean| <
0.15` and `std ∈ [0.85, 1.20]` written before the measurement. So the reported σ
is the right scale, and 1019/1020 may now tune against it.

The gate found **two more defects** — six in total for this WP, and *not one of
the six was visible by reading the code*. Both new ones are doublet physics. A
marginally resolved Kα2 has **no maximum**, so the alias filter cannot see it,
but it does have a curvature shoulder: it cleared the 5σ seeder, sat outside the
half-FWHM grouping gap, formed a **singleton group**, and came back as a line
with an esd — and the ΔBIC prune cannot refuse it, because a singleton is judged
against "no peak at all" and there genuinely is intensity there. That was one
spurious line per pattern and a **−21 mean σ pull** on the LaB₆ 110 reflection.
And the doublet amplitude ratio is not `weight`: each line diffracts at its own
Bragg angle, so it carries its own **Lorentz-polarisation** factor, and holding
the bare weight dragged the fitted Kα1 position down by 2e-4° (mean pull −0.26 →
−0.19).

Two results outlast the WP. **Sizing rule: 200 groups is enough for a `std` bar
and not for a `mean` bar** — at pull std 1 the standard error of the mean over
200 groups is 0.07, half the 0.15 bar, and a 200-group subsample of this very
ensemble read −0.15 where the converged value is −0.08; the test now asserts
`3·SE < bar` before asserting the bar, so an undersized ensemble fails loudly
instead of passing by luck. And **the remaining −0.08σ doublet bias is a
measurement, not a to-do**: 2e-5°, a fortieth of a channel, with four candidate
mechanisms excluded by substitution (exact background, isolated reflection,
per-line widths, model-σ weights) and the estimator shown unbiased to ±0.02 in
isolation — so what is left is in the detection-seeded window, two orders below
the systematic-error scale 1019 exists to model.

**[1019](wp/1019-indexing-data-quality.md) closed the same day**, and its
deliverable is a *gate*: `assess_peak_list` judges a peak list fit to index or
**abstains with a reason**, and `fit_shift_model` attributes a systematic 2θ shift
to a zero-point error, a displaced specimen or a transparent one — or declines to,
which is the half that matters, since every program the 2004 benchmark paper
surveys fits one constant "zeropoint" instead.

Its founding question was one the plan had not resolved: **what is knowable from a
peak list alone.** Everything except the shift is a property of the list. The
shift is not — with no cell there is nothing to deviate from — so the screen is
*conditional* on reference positions, and with none the report says
`shift.source == "unavailable"` rather than reporting a zero shift it never
measured. What *is* computable with no data at all is the separability geometry of
the three templates over the angles sampled: a statement about the experiment
rather than the specimen, readable before a specimen is loaded.

Four measurements, and two of them overturned something:

- **"The cell stands when the cause is ambiguous" is true only with the word
  *competitive* in it.** Over 10-25° 2θ with a 0.10° cos θ displacement, all three
  templates' predicted corrections differ by 0.046° — nearly half the shift, a
  0.2 % cell error if the wrong one is applied. But the template that disagrees is
  the one the data *rejects*, and over the two that fit comparably the spread is
  0.0011°. The plan's conclusion survives; its reasoning is narrowed, and
  `prediction_spread_deg` now reports the number instead of a docstring asserting
  the claim.
- **A measured no-go: dominant zone and dominant row are not detectable from a
  census.** Neither is a summary statistic — a dominant zone is the statement that
  the low-angle lines satisfy a *two-dimensional* quadratic form, a dominant row an
  arithmetic progression k²B among the low Q values. Each is a search. The obvious
  census (Ito's most-repeated Q difference) was written, measured and removed: it
  scores dominant-zone cells at +0.9σ and +0.8σ against a permutation null while
  scoring a *general* monoclinic cell at +3.3σ, and against a uniform null a
  **cubic** list scores +15.6σ — it detects commensurability, not zones. A test
  asserts the diagnostic code's absence so it cannot creep back, and the engines
  (1021/1022) have been told they own the detection.
- **Smith's volume envelope needed two scalings, and the second was found by the
  envelope excluding the right answer**: with the Laue orbit factor alone,
  corundum's bound came out at 125 Å³ against a true 255 Å³, because R-centring
  extinguishes two thirds of hkl. Centring is part of the answer (1025's extinction
  symbol), so the default is the worst case each system allows — the one failure a
  search bound may not have is excluding the true cell — and the envelope is
  reported per system, since they span 96×.
- **`constant` and `cos θ` stay 0.96 collinear even over 10-140°**, so
  separability is decided on the residual-SS ratio against real data and never on
  the geometry alone.

One item is left open for the user rather than a session: the per-system envelope
scaling is *derived* here, not published, and a clean copy of Smith (1977) would
let the derived factors be checked against the paper's — the WP-0501 b₂
transposition being the precedent for why that check is worth asking for.

**[1020](wp/1020-indexing-core.md) closed the same day** — five modules, 40
tests, an eleventh manual chapter, and **no engine**: the Q-space quadratic form
and its symmetry-allowed subspaces, weighted candidate refinement with an optional
shift column, Niggli/Delaunay reduction with two-opinion Bravais determination over
a tolerance sweep, the figure-of-merit **panel** scored in both directions, and
HNF derivative-lattice ambiguity with the reflections that would break each tie.
1021-1023 now have everything they share.  Full suite after all three WPs: 1251
passed / 70 skipped / 0 failed, including the `slow` real-data acceptance.

**Its lesson is about tests, not about crystallography: three of its four defects
passed the test that should have caught them.**

- The metric subspace was derived from the **transposed** rotations, and the
  dimension test passed. CLAUDE.md's "reciprocal-space action is Rᵀ" is about
  *hkl*; a tensor contracting with h twice is invariant under U → R·U·Rᵀ, and G\*
  is one. The transposed call returns the *direct* metric's invariants — the same
  dimension in every system, because the transposed set is a group too, so the
  WP's own acceptance criterion (1/2/2/2/3/4/6) was satisfied by the wrong
  subspace, with F = −A for hexagonal where the reciprocal metric has F = +A. What
  catches it is asserting the **true** metric lies in the span.
- A Gauss-Newton sign error that is locally correct: flipping only the θ block
  still solves for θ, and leaves the shift column with the wrong relative sign —
  s = −11.65 for an injected +0.05°.
- **M₂₀ was not invariant under a unimodular setting change, by 5 %**, because
  N_poss counts predictions up to the N-th observed line and that line *is* a
  prediction, so a strict comparison depends on fp rounding (N_poss 20 vs 19,
  M₂₀ 76.43 vs 80.45).
- And a perfect cell scored **M₂₀ = 0**: the figure divides by ⟨ΔQ⟩, which → 0 when
  a candidate fits within fp noise, so the obvious zero-guard ranked the right
  answer last. The mean is now floored at the median σ — a meaning rather than an
  epsilon, since a discrepancy below the measurement precision is not knowable, and
  per-line σ is what this package has and 1968 did not.

Two things it declined to do. **Four published figures of merit are not
implemented** — the Oishi-Tomiyasu reversed/symmetric de Wolff pair, WRIP20 and
McM₂₀ — because their formulas cannot be written from memory with correct
attribution, and guessing one while citing its paper is the WP-0501 b₂ failure in a
new costume; the panel's *argument* (coverage in both directions) is fully
implemented, which is what the measured §D result demands. And **1020 emits no
diagnostics at all**, deliberately: it has no answer to qualify, so
`INDEX_BRAVAIS_AMBIGUOUS` belongs to 1024 where a `CellCandidate` exists to carry
it.

1018's earlier value was already banked, and it is the v0.5 method result in
a new costume: **four defects, none of them visible by reading the code.** A
resolved Kα1/Kα2 doublet manufactured one spurious line per reflection (each
group is fitted independently *with its own full doublet*, so the Kα2 maximum
comes back as a real line — structural to per-group fitting, and any future
change to grouping must keep the alias filter); the first curvature seeder was
useless because differentiating twice amplifies noise by ~1/step², so a
per-channel-σ threshold passed essentially every noise dip; a shoulder seed
landing alone formed a *singleton* group that the ΔBIC gate never judged, so a
false positive became a line with an esd and no evidence; and
`background_envelope` is a rolling *low* quantile, ≈1.28σ below the true
background, which quietly turned a nominal 5σ detection threshold into ≈3.7σ.
Against that, the thing that *was* verified by reading — the analytic group
Jacobian — agreed with central differences to 2.5e-07 on every column first
time. Reading finds the algebra; only running finds the four above.

**A process note that outlasts the WP.** 1018, [1004](wp/1004-parameter-plan-api.md)
and [1006](wp/1006-run-control.md) were developed *concurrently in one working
directory*, and both other WPs' commits ran `git add -A` while 1018's files were
uncommitted — so `indexing/peaks.py`, `peakfit.py`, `pick.py`, `diagnostics.py`
and most of `schemas/indexing.py` are committed inside `f63556c`, `e46ead2` and
`62d6a76`, whose messages say WP-1004 / WP-1006. Nothing was lost and the tree
is green; the history was left interleaved deliberately, because the swept files
sit *inside* those commits, so untangling means surgery on three already-closed
WPs' commits to fix a comment in `git log`. **`git log -- src/pxrdref/indexing/`
will mislead you — start from `068149e`.** The rule this buys: one `git worktree`
per concurrent session, or only one session commits.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1018](wp/1018-peak-picking.md) | Peak picking: detection + full per-peak profile fitting | ✅ 2026-07-30 | — |
| [1019](wp/1019-indexing-data-quality.md) | Data-quality gate and the systematic-error model | ✅ 2026-07-30 | 1018 |
| [1020](wp/1020-indexing-core.md) | Indexing core: Q-space, reduction, Bravais, FoM panel, ambiguity | ✅ 2026-07-30 | 1018 (1019 soft) |
| [1021](wp/1021-engine-dichotomy.md) | Engine A — successive dichotomy | ✅ 2026-07-30 | — |
| [1022](wp/1022-engine-trial-error.md) | Engine B — index-heuristic trial and error | ✅ 2026-07-30 | — |
| [1023](wp/1023-engine-montecarlo.md) | Engine C — whole-profile Monte Carlo (spike, then decide) | 🛑 no-go 2026-07-30 | — |
| [1024](wp/1024-indexing-consensus.md) | Consensus, `index_pattern`, Le Bail validation, agent & CLI | ⬜ | 1021–1023 |
| [1025](wp/1025-extinction-symbol.md) | Extinction symbol / space-group determination | ⬜ | 1024 |
| [1026](wp/1026-indexing-acceptance.md) | Acceptance: bethanechol benchmark + known cells | ⬜ | 1024 (1025 soft) |
| [1027](wp/1027-gui-peak-picker.md) | GUI peak picker + indexing panel | ⬜ | 1010, 1011, 1018–1024 |

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1028](wp/1028-robustness-external-data.md) | Robustness on data and CIFs we did not author | ⬜ | — (1007 soft) |

**1028 came from outside.** Every item in it was hit by driving the package
end-to-end over nine unfamiliar refinement targets from a third-party paper
(branch `wpem-benchmark`, pushed and deliberately **not** merged), and none of
it was found by reading the code: a species-string syntax that rejects 6 of 11
COD entries, a 2.35 PiB allocation in `generate_reflections`, `status =
"converged"` at Rwp = 7 225 %, a stage that burns 4 600 solver evaluations and
still reports success, March-Dollase returning inf/NaN when `r` underflows past
a bound meant to prevent exactly that, and `compute_qpa` raising where it should
diagnose. The first was filed as a **reach regression from WP-1001** and, as
measured on 2026-07-30, is not one: `scattering.normalize_species` carries the
same regex, has been on the compile path since v0.1, and rejects the same two
forms — so those CIFs never loaded. Making dispersion the default moved the
raise up one line and changed its wording; the fix has to satisfy both lookups
(WP-1028 §(a)). Robustness against strangers' files is not a feature the
existing suites can test, because they only ever read files we chose — and the
benchmark that found these measured every *failure* but reasoned one *cause*,
which is its own lesson about reading a diff for an attribution.

Three decisions worth keeping visible, because each is a place the obvious
implementation is wrong:

- **Three engines, and the confidence is their agreement.** Both source papers
  conclude that no single indexing program wins and that running several is
  what raises the success rate — which is the device this package already uses
  for correctness elsewhere (`direction="both"` flagging
  `SEQUENTIAL_PATH_DEPENDENT`, the per-column cross-backend Jacobian matrix).
  The engines share only the Q form and the tolerance model.
- **Coverage is scored in both directions, and that is measured, not
  aesthetic.** On the guiLLeMot MnSb_34 screen, ranking on share-of-observed-
  intensity alone puts a 390-line phase first with 9 % of its own lines
  present, above the truth at 56.5 %. A cell that indexes everything and
  predicts a forest is the classic false positive and one number cannot see it.
- **A restricted search is never a verdict about the sample.** Measured on the
  same branch: a two-parameter engine scores 47–60 % on single-phase
  orthorhombic/monoclinic patterns and 82–100 % on genuinely
  tetragonal/hexagonal ones, so a real mixture at 69 % sits in the overlap —
  and a "at least two phases" claim built on that ambiguity was **withdrawn**.
  Hence `systems_searched` on the result, and `INDEX_SYSTEMS_NOT_COVERED`.

Prior art lives at the annotated tag **`guillemot-study`** (commit 97ba88d, also
on branch `guillemot-example-refinements`): `studies/guillemot/index_hl2.py` is
engine B in miniature, `audit_tools.py` measured the findings above, and
`out/HL2-1_peaks.txt` is 74 peaks from a genuinely unidentified pattern — the
acceptance fixture whose correct answer is "we do not know".

**It is not merged into `main` and does not need to be** — `git show
guillemot-study:studies/guillemot/<file>` reads any of it without a checkout.
The tag is what guarantees that stays true if the branch is ever pruned.

## v2+ (seams pre-built, implementations fenced out)

Fundamental Parameters Approach as a differentiable convolution stack
(Cheary-Coelho 1992); neutron CW; TOF (new Source/Profile implementations
behind the frozen seams); spherical-harmonics texture (Von Dreele 1997);
rigid bodies; MCP server wrapping `refine_json`; internal-standard/amorphous
QPA; `vmap`-batched in-situ series; notebook widgets. *(The human GUI was
un-fenced from this list into v1.0 on 2026-07-29 — WP-1004…1017; grounds in
[DESIGN.md](DESIGN.md#locked-decisions).)*

Fenced **by** the v1.0 indexing WPs (1018…1027, 2026-07-29), i.e. deliberately
left undone by work that could plausibly have grown to include them:
multi-phase indexing (index the residual after subtracting a solved phase);
search-match phase identification, whose prior art is the 36-cell screen at
`guillemot-study:studies/guillemot/match_hl2.py`;
the full Bayesian extinction-symbol posterior (Markvardsen et al. 2001 — the
ΔBIC/Hamilton nested comparison is the v1.0 form); a fourth engine in the
Conograph topograph lineage (Oishi-Tomiyasu's reversed/symmetric M_N *is* in
scope, as a figure of merit); derivative-lattice ambiguity above index 4; and
structure solution from an indexed cell.

No WP files for v2+ on purpose — the fence is a scope-discipline decision
([DESIGN.md](DESIGN.md#locked-decisions)), and pre-writing packages invites
scope creep.

One note against the day that fence is revisited: **`vmap`-batched in-situ series
is the only accelerator story this package's hardware supports**, and WP-0408
measured its size. A device breaks even at ≈50-65 k elements per kernel and tops
out at **≈2.5-3×** — the work is memory-bound, so that ceiling is not a tuning
problem. One batched pattern is 17-121 k elements, so the plateau needs ≈10
(synchrotron) to ≈60 (lab) patterns processed together. Worth having for a
series; worth nobody's time for a single pattern, which is below break-even even
after batching.
