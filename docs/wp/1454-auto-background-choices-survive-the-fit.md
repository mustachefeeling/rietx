# WP-1454 — `auto_background`'s choices survive the fit

Milestone: unscheduled · Status: ✅ 2026-09-24 — all three choices hold through the fit; the flood a declared air term still raises is WP-1460
Depends on: —

## Goal

`auto_background` makes three choices, and each one holds through the fit.
The smoothness penalty is equally stiff whatever unit the intensities are
in. The knots span the range the fit uses. An air-scatter term it left off
stays off.

## Context

**The evidence.** A 2026-09-24 transcript review read an agent session that
drove rietx at `644dff84` through the skill. The data were a private
synchrotron in-situ series of 48 patterns: `in-situ series 1` in the private
`yue-here/rietx-corpus-map`, which says where the data, the scripts and the
transcript live. Quote only what the runs did (CONTRIBUTING, WP-1450). All
three choices below failed there, and the first and third are measured
again here on public data.

### 1. The penalty's units

`BackgroundPSpline`'s penalty rows are √λ·D₂c
(`src/rietx/model/forward.py:3022-3025`). The coefficients c are in
intensity units, while every data row is divided by σ. Multiply y and σ by
k: the data rows do not change, the penalty rows scale by k, and the
effective λ scales by k². With Poisson σ the relative stiffness grows with
the count level instead. The default is `lambda_smooth = 1.0`
(`src/rietx/schemas/instrument.py:1077`), and `auto_background` passes 1.0
(`src/rietx/background/auto.py:49`).

Measured 2026-09-24 on 11-BM NAC (`tests/data/11BM_NAC.fxye`), starting from
the walkthrough's converged model. Intensity, σ and every phase scale are
multiplied by k, and the default Rietveld plan runs over 2-24°:

```python
base, ref0, _, _ = nac_11bm.run()            # examples/nac_11bm.py
for k in (1e-4, 1e-2, 1.0, 1e2):
    data = base.model_copy(update={"intensity": list(np.asarray(base.intensity) * k),
                                   "sigma": list(np.asarray(base.sig()) * k)})
    structure = ref0.fitted_structure.model_copy(deep=True)
    for p in structure.phases:
        p.scale.value *= k
    ins = ref0.fitted_instrument.model_copy(deep=True)
    ins.background = bk = rx.auto_background(data)       # 8 knots, λ = 1
    for c in bk.coefficients:
        c.value = float(np.percentile(data.intensity, 5))
    ref = rx.Refinement(structure, ins, history=False)
    r = ref.fit(data, two_theta_limits=(2.0, 24.0), telemetry=False)
    c = [p.value for p in ref.fitted_instrument.background.coefficients]
    print(k, r.statistics.rwp, np.abs(np.diff(c, 2)).max() / k)
```

| k | max \|D₂c\| / k | Rwp |
|---|---|---|
| 10⁻⁴ | 184 | 0.09335 |
| 10⁻² | 171 | 0.09335 |
| 1 | 25.9 | 0.09370 |
| 10² | 0.0046 | 0.09404 |

A unit change alone takes the background from unpenalised to a straight
line. NAC's own count level sits in the transition. The weight fractions
agree to 0.01 wt % at every k, because NAC's background is smooth and 8°
knots cannot reach a reflection. So this pattern shows the mechanism and not
its cost.

On the private series the default gave a straight line across the fitted
4-40°, at Rwp 0.18. Lowering λ by 10⁴, refining the knots to 0.75° and
confining them to the fitted range gave Rwp 0.028. The agent worked out
λ ≈ 1/σ² for itself and wrote it into its own helper.

The other direction is derived, not measured. Data in small units
(normalised, or a rate with an esd column) make the penalty vanish. A fine
spline can then absorb broad Bragg intensity. That is the failure
`BackgroundPSpline` exists to prevent (its docstring). Root CLAUDE.md
§ background flexibility says what it costs: ADPs biased up and scales, and
so fractions, biased down, while Rwp improves.

### 2. The fitted range

`auto_background` takes its knot range from `diagnose(data)`, which is the
whole file (`auto.py:47-49`). The function takes no limits argument. On the
private series the fit stopped at 40° while the knots ran to 92°, so the
coefficients past 40° were held by the penalty alone. They extended the
straight line to negative values at about 75-92°, where there were no data.
Inside the fitted range the background stayed positive.

### 3. The air term

The air-scatter term defaults to off: `Parameter(value=0.0, min=0.0,
transform="softplus")`, with `vary` False
(`src/rietx/schemas/instrument.py:1078`). `auto_background` turns it on only
when `diag.air_scatter_gain > AIR_SCATTER_TRIGGER`. But all seven presets
free `instrument.background.*` (`src/rietx/strategy/staged.py:284-431`),
and that glob includes `.air`. A plan replaces the vary flags (WP-1208), so
the declined term is freed on every fit. This is issue #211's shape, which
WP-1435 fixed for a caller's own holds.

The cost shows in the diagnostics. `check_guards` appends a
`HIGH_CORRELATION` finding for every pair above `correlation_guard` (0.98),
and a `FLAT_DIRECTION` finding as well at or above `FLAT_DIRECTION_RHO`
(1 − 5·10⁻⁴) (`staged.py:1544-1561`). One flat direction across n columns
can therefore produce n(n−1) rows. Measured 2026-09-24 on NAC, from the same
walkthrough model, with `BackgroundPSpline.for_range(1.9, 24.1, …)` seeded at
the 5th percentile:

| knots | λ | coefficients | rows | background-only rows | Rwp |
|---|---|---|---|---|---|
| 8° | 1 | 6 | 2 | 1 | 0.09366 |
| 2° | 10⁻⁴ | 14 | 1 | 0 | 0.08628 |
| 0.75° | 10⁻⁴ | 33 | 1075 | 1074 | 0.08484 |

At 0.75° the 1074 rows are 561 `HIGH_CORRELATION` and 513 `FLAT_DIRECTION`.
561 is every pair among the 34 background parameters. The same fit with
`ref.hold("instrument.background.air")` gives **zero** correlation rows, at
Rwp 0.08484 both ways. So the whole flood is one direction: the 1/(2θ)
column inside the span of a fine spline.

On the private series, 1643 of 1644 rows on one fit were about background
coefficients alone. The agent's first completed fit printed about 8 kB,
most of it these rows, and the agent then dropped every background-only
row. With them it lost sight of `CAPILLARY_OFFSET_UNAVAILABLE`, which asked
for a goniometer radius on 48 of 48 patterns of each final chain. The
instrument file states a secondary radius (TOPAS `Rs`), which is probably
that number (WP-1455).

### The skill

`SKILL.md:77-78` says `rx.auto_background(data)` "does the right thing".
`references/judging.md` and `references/batch.md` quote `worst_absorption`
only as 0.46 against 0.08. The guard is `BACKGROUND_ABSORPTION_GUARD = 0.25`
(`staged.py:878`), and no skill file names it.

### What a fix moves

A new penalty scale moves every converged P-spline fit. Holding a declined
air term moves every fit whose plan freed it, even where Rwp does not
change. Which goldens declare a P-spline, and what each one does, is a
decision to take here (tests/CLAUDE.md).

**Prior art, not yet read.** Eilers & Marx (1996) choose λ against the data
by cross-validation or AIC. Check how GSAS-II and TOPAS scale a smoothness
penalty on a background before choosing.

## Non-goals

- Choosing λ per pattern by cross-validation. That is a selector, and WP-1130
  closed on a background selector's gate.
- The background level (WP-1130).
- Changing `correlation_guard` or `FLAT_DIRECTION_RHO`.

## Tasks

- [x] The air term. Decide how a declined term stays off, and write the
      decision here. The candidates: presets free `instrument.background.c*`,
      plus the air term only where the model turned it on; or the declined
      term is held the way a caller's hold is, which needs a seam because a
      model carries no holds. Land it, and measure NAC at 0.75° again.
      **Decided 2026-09-24: a declined term is absent**, which is neither
      candidate. `BackgroundPSpline.air_scatter` is `Parameter | None` and
      defaults to `None`, so a declined term has no design row and no path,
      and no glob can reach it. The first candidate still needed the model to
      say "on" through a plan that replaces the vary flags. The second needed
      a hold the model cannot carry. Absence is how the package already spells
      an optional term (`Geometry.mu_t`, `Phase.microstrain`, `Atom.aniso`,
      `Source.dispersion`), and it needs no seam. `for_range` builds no air
      term, and `auto_background` declares one on its trigger as before.
      `SCHEMA_VERSION` 0.27 → 0.28, not additive. A document saved before this
      carries the old default, a `Parameter` at 0, and refines as it did.
      **Re-measured** on the § 3 protocol (`[dev]` venv, Linux x86-64):
      background-only correlation rows at 8°, 2° and 0.75° knots went from
      1 / 0 / 1074 to 0 / 0 / 0. Rwp moved 0.09366 → 0.09367 at 8° and not at
      all at 2° or 0.75°. Declaring a zero air term explicitly at 0.75° gives
      back all 1074 rows (561 `HIGH_CORRELATION`, 513 `FLAT_DIRECTION`). Only
      65 of them name the air term, so the other 1009 are the spline's own
      pairs, pulled in by that one flat direction.
- [x] If any fit in the fast selection still reports one degeneracy as many
      pair rows after that, file a WP to group them into one finding. The
      candidates are connected components of the thresholded pairs, or the
      flat eigen-directions of the Jacobi-scaled normal matrix, and every
      reader of the rows is audited first (WP-1103). If none does, record
      the zero here. **Filed 2026-09-24 as WP-1460**: not zero. `check_guards`
      was wrapped over the whole fast selection on this branch's final tree,
      443 calls in 186 tests. Its largest component is 35 parameters reported
      as 569 rows, in `test_pspline_refines_a_curved_background`, where
      `auto_background` itself declared the air term beside 3° knots. A
      declared air term floods the way a declined one did whenever the spline
      can already draw 1/(2θ), so that question went to 1460 with the
      grouping. The first pass of the audit saw only 7 calls, because
      `import rietx.refine` binds the package's `refine` *function*, so the
      wrapper patched an attribute on a function. The module is reached
      through `sys.modules["rietx.refine"]`. Any instrument that patches
      `refine` needs that.
- [x] Measure the flexible side of the penalty. Take a public pattern with
      broad reflections, scale it down and fit with fine knots. Record
      whether a Biso or a fraction moves, and whether `background_absorption`
      or any guard fires. This sets the priority.
      **Measured 2026-09-24**, on IUCr CPD round-robin sample 2
      (`tests/data/qarr/cpd-2.prn`: corundum, zincite, fluorite and platy,
      broad-lined brucite). The model is `test_acceptance_qpa_roundrobin`'s,
      and so is the plan, including the March-Dollase stage. The reference is
      a fit under its Chebyshev(6). From that model, the background becomes a
      P-spline at the old λ = 1 in intensity units. Intensity, σ and the
      phase scales are then multiplied by k and the plan runs again.
      k ≤ 10⁻² is the unpenalised limit, and the two k rows there agree to four
      figures. `[dev]` venv, Linux x86-64.

      | knots | k | Rwp | wt % cor/zin/flu/bru | B Al | B Mg | B O (bru) | R² | background code |
      |---|---|---|---|---|---|---|---|---|
      | Cheb 6 | 1 | 0.1328 | 22.05/17.08/22.43/38.43 | 0.356 | 0.794 | 1.087 | 0.14 | — |
      | 2° | 10⁻³ | 0.1193 | 21.46/16.84/22.19/39.52 | 0.217 | 1.048 | 1.457 | 0.43 | `BACKGROUND_ABSORPTION` |
      | 2° | 1 | 0.1226 | 21.91/17.06/22.40/38.63 | 0.333 | 0.838 | 1.097 | 0.21 | — |
      | 2° | 10² | 0.1529 | 21.46/17.16/22.54/38.84 | 0.176 | 0.826 | 0.948 | 0.16 | `LOW_ANGLE_UNMODELLED` |
      | 1° | 10⁻³ | 0.1153 | 21.87/16.26/21.97/39.90 | 0.285 | 1.162 | 1.864 | 0.63 | `BACKGROUND_ABSORPTION` |
      | 1° | 1 | 0.1211 | 21.71/16.99/22.29/39.02 | 0.274 | 0.983 | 1.171 | 0.32 | `BACKGROUND_ABSORPTION` |
      | 1° | 10² | 0.1412 | 21.69/17.14/22.46/38.71 | 0.255 | 0.807 | 1.004 | 0.16 | **none** |

      The flexible side is not silent. Every arm whose Biso moved by 20 % or
      more fired `BACKGROUND_ABSORPTION`, and the 0.25 guard sat between the
      firing rows (0.32 and up) and the quiet ones (0.21 and down). The
      **stiff** side is the silent one. At 1° knots and k = 10², which is
      counts at a hundred times this lab scan's and ordinary for a synchrotron
      or a long count, corundum's Al Biso moved 28 % and no background code
      fired. The codes on that row are the reference fit's own. At 2° the only
      flag was `LOW_ANGLE_UNMODELLED`, which names a region rather than a
      stiffness. Fractions moved 1.1 wt % at most, inside the participant
      spread. That is the private series' failure, a straight line at high
      counts, reproduced on public data. It meets this WP's own P1 condition,
      a structural answer moving with nothing fired, on the side the WP had
      not suspected. The penalty scale below is what removes it.
- [x] Decide the penalty's scale, and write the decision here. Either divide
      the penalty rows by one σ frozen at compile (the median over the fitted
      channels), which makes λ dimensionless for every caller; or keep the
      units and derive λ in `auto_background` from the counts, which fixes
      only the helper. Land it, with the goldens' decision recorded.
      **Decided 2026-09-24: the first, with a second factor.** The rows are
      √(λ·m)·D₂c/σ̄, with σ̄ the median σ over the fitted channels and m the
      fitted channels per coefficient, both frozen at compile
      (`background.models.pspline_penalty_scale`, baked into
      `CompiledModel.bkg_penalty`, which every backend reaches through
      `penalty_residual`). σ̄ alone removes the unit, and m is needed as well
      because the data's weight on one coefficient grows as m/σ̄². Without m,
      a 0.001° scan and a 0.02° scan of one curve would disagree by 20× at
      one λ. Derived, not measured: a feature of width W costs about
      λ·(h/W)⁴ of what it buys, so λ = 1 suppresses features narrower than
      about one knot spacing h. The second candidate would have fixed only
      the helper, and the private series was fitted through the helper and
      then by hand. **The default stays 1.0, now a pure number.** On NAC the
      old default measures between 0.01 and 0.1 in the new units (max|D₂c|
      37.6, against 69.5 and 34.3 there), close to the predicted σ̄²/m =
      0.078. On sample 2 at `auto_background`'s own 3° knots, which also
      declares the air term there, the old default measures near the new
      1.0, and the structure is flat from 0.1 to 100:
      | λ (dimensionless) | Rwp | B Al | B Mg | R² | background code |
      |---|---|---|---|---|---|
      | old λ = 1, intensity units | 0.12302 | 0.352 | 0.802 | 0.17 | — |
      | 0.01 | 0.12205 | 0.346 | 0.820 | 0.28 | `BACKGROUND_ABSORPTION` |
      | 0.1 | 0.12267 | 0.351 | 0.803 | 0.19 | — |
      | 1 | 0.12326 | 0.352 | 0.801 | 0.16 | — |
      | 10 | 0.12366 | 0.352 | 0.800 | 0.15 | — |
      | 100 | 0.12412 | 0.353 | 0.799 | 0.15 | — |
      So 1.0 sits a decade inside the flexible edge and at least two decades
      from anything the stiff side moved here, and it reproduces the old
      default at both public count levels. The private series, at high
      counts, was 10⁴-fold stiffer than that. **The way back** is
      `BackgroundPSpline.lambda_units = "intensity"`, the old rows exactly,
      following the `dispersion = None` and `intermediate_ftol = None`
      precedents. **Goldens:** `test_backend_shim`'s `toy_lebail` declares
      the old air term and `"intensity"`, so its darwin npz stays
      bit-identical. That cannot be checked from Linux, where the goldens
      skip, so the nightly macOS job is the first to run it.
      `test_acceptance_si640c` declares `"intensity"`, because every number
      it quotes was measured that way; its plan never freed the air term.
      No other test pins a P-spline number. A stored document has no
      `lambda_units`, so its λ opens as the pure number and its penalty
      changes. That is deliberate: the stored value never said which unit it
      was chosen in (`SCHEMA_VERSION` 0.28's note). Prior art: GSAS-II's
      eight background functions carry no smoothness penalty, so there is no
      scaling convention to adopt (GSASIIpwd docs, 2026-09-24). TOPAS was
      not checked. The WP § 1 table, rerun with its own code, is now one row
      four times: max|D₂c|/k = 4.5707 and Rwp 0.0939775 at k = 10⁻⁴, 10⁻²,
      1 and 10², to 13 digits.
- [x] `auto_background` spans the fitted range: take `two_theta_limits`, or
      read the range the fit will use. **Landed 2026-09-24** as a
      `two_theta_limits` keyword, the tuple `fit` takes. The diagnostics, the
      Chebyshev order selection and the knots are all taken over it. The
      channel count asks `project.fitted_mask`, the WP-1033 authority,
      through a function-level import, since `project` sits above
      `background/`. Caller-supplied `diagnostics` are used as given, with the
      knots still clamped to the limits. An inverted interval is refused
      with `check_interval`'s sentence. Limits holding fewer than ten
      channels, `compile_model`'s own floor, are refused by count, and so are
      diagnostics that miss the limits (both added by the handover's review).
- [x] Tests. Unit invariance: at k ∈ {10⁻³, 1, 10³} the fitted background
      divided by k agrees within the spread the same fit shows when
      restarted, measured first and never chosen (tests/CLAUDE.md § Budgets
      in tests). And NAC at 0.75° knots: no correlation row names a declined
      air term. **Landed 2026-09-24**, both in `tests/test_background_auto.py`.
      `test_the_penalty_is_equally_stiff_in_any_intensity_unit` measures its
      own restart spread each run and asserts k = 10⁻³ and 10³ inside it,
      with the old intensity-unit rows as the arm that must fail it.
      Measured first under `profile_only`: spread 4.9e-3 of the curve's
      maximum; 2.7e-4 and 3.1e-9 for the two k; the old rows 7.4e-2 and 0.56.
      A scale-and-background plan was tried and dropped. It is linear, so
      spread and invariance both sit at 1e-16 and the comparison would be
      noise. `test_an_undeclared_air_term_raises_no_background_correlation_rows`
      stands in for NAC, whose walkthrough fit is too slow for the fast
      selection. The same flood appears on the synthetic LaB₆ pattern at 2°
      knots: none without a term, and more rows than coefficients (554) with a
      zero term declared. That arm is the failure reproduced.
- [x] Skill: the `SKILL.md:77` sentence; the 0.25 threshold beside the 0.46
      example; and the seed note in `references/judging.md`, if the new scale
      changes what a seed means. **Landed 2026-09-24.** `SKILL.md` §1 names
      `two_theta_limits` in place of "does the right thing", at +32 B
      (32 964 of 33 000). `references/judging.md` and `references/batch.md`
      put the 0.25 guard beside 0.46 against 0.08. `judging.md` gains the
      stiff side: no guard of its own, the sample-2 measurement, and that a λ
      tuned by hand before 1.5.1 does not carry over. The seed note is
      unchanged: a seed is a coefficient value, in intensity units under
      either penalty.

## Acceptance

The table in § 1, rerun, shows one row four times. NAC at 0.75° knots
reports no air-term correlation rows.

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_background_measured.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Eilers, P. H. C. & Marx, B. D. (1996). *Statistical Science* **11**, 89.
- WP-1055 (background evidence), WP-1130 (the background level, closed),
  WP-1309 (a measured background's σ), WP-1208 and WP-1435 (a plan replaces
  vary flags; a hold outranks a glob), issue #211, WP-1103 (the reader
  audit).

## Handover log

- **2026-09-24** — `auto_background`'s three choices now hold through the fit.
  Its smoothness penalty is equally stiff in any intensity unit, at any count
  level and at any step size. Its knots cover only the range being fitted. An
  air-scatter term it decided against is no longer refined anyway. The unit
  problem was the reverse of what this WP expected. On public round-robin data
  the over-flexible side always fired its guard, while a penalty stiffened by
  high counts moved a displacement parameter 28 % with no warning at all. The
  default weight is still 1, now a pure number, so ordinary fits land about
  where they did, and old ones reproduce by declaring the old units. The
  correlation flood this WP started from is gone for a declined air term but
  not for one the helper declares beside a fine spline, and WP-1460 has that.
  - *Done*, one commit per task: the air term absent when declined (`0ef9a39`),
    `two_theta_limits` on `auto_background` (`764c3ad`), the stiff side
    measured (`9d73a84`), λ a pure number with `lambda_units` as the way back
    (`4554e1a`), the invariance test (`4ba5b94`), the skill (`810d3ba`), and
    task 2's audit filing WP-1460 (`3920f3f`). Review fixes followed in
    `1373f86`. `SCHEMA_VERSION` 0.27 → 0.28, once for both field changes. The
    manual's `bg-penalty` equation, Part 1's background paragraph, root
    CLAUDE.md's background clause and `releases/1.5.1.md`'s three sections
    all moved in the same commits.
  - *Measured*, `[dev]` venv, Linux x86-64, alone on the machine unless
    stated. The numbers sit under each task above. The fast selection on the
    final tree gave 5886 passed, 147 skipped and 1 failed (6034), against 6030
    on this session's first run. The +4 is the four tests added, all passes,
    no new skip. The failure is the `unwritable-directory` case of
    `test_telemetry.py`, which fails because this container runs as uid 0
    (`chmod 0o500` binds nobody). It fails on the first run too, and it is
    queued as its own task, not fixed here. The full suite ran once, at
    `016d06c`, which was current main plus this branch: 6068 passed, 158
    skipped and 3 failed, in about 1 h 37 min at `-n auto` with nothing else
    running. Besides the uid-0 case, two failures come from load and not from
    this diff. The held-phase ramp's 60 s runaway guard took 76.5 s under the
    suite's load and 16.9 s alone, a 3.5× margin, which makes it a load
    sensor; its background is a Chebyshev. The brucite strict xfail passed
    under load and xfailed alone. Indexing builds no P-spline, and the flip is
    written into WP-1449's Inherited. Main then moved to `54a049d` with docs
    only: the issue batch's WPs 1457-1459, which took this WP's filing
    number and made it 1460, and a cap comment in `test_docs_consistency.py`.
    It was merged in, and the fast selection on the merged tree gave the same
    5886 passed, 147 skipped and 1 failed. The full suite was not re-run,
    because the merge changed no code and no test count. There is no baseline
    full count on this machine, per tests/CLAUDE.md, so only the fast delta is
    exact.
  - *Review* (`/code-review high --fix`): 8 candidates, 3 fixed in `1373f86`.
    Those are a 10-channel floor on the limits, named refusal of diagnostics
    that miss them, and three comments still spelling the rows √λ·D₂c. The
    other 5 were declined. Whole-file diagnostics can declare an air term
    from a rise outside the limits; "used as given" is the contract, so that
    went to WP-1460's air-term task. A stored λ reopens as the pure number,
    and a stored zero air term reopens declared: both deliberate and written
    into the schema note and the release notes, since nothing stored says
    which unit an old λ was chosen in. m counts every coefficient even where
    the knots overrun the fitted range: now stated in
    `pspline_penalty_scale`'s docstring rather than changed, because
    `auto_background` no longer builds that case. `rietx compare`'s `pspline`
    variant moved with the default, and nothing pins its numbers.
  - *Gotchas.* `import rietx.refine` binds the package's `refine` function,
    not the module. An instrument that patches it goes through
    `sys.modules["rietx.refine"]`, or it sees only direct `staged` calls
    (task 2's first audit saw 7 of 443). `test_backend_shim`'s `toy_lebail`
    golden declares the old air term and `"intensity"` so its npz stays
    bit-identical. The goldens skip on Linux, so the nightly macOS job is the
    first check of that.
  - Next: nothing in this WP. PR #446 carries it, and it should merge before
    1.5.1 is cut, since the release notes describe it. Then WP-1460, starting
    with its reader audit, which decides whether grouping replaces the pair
    rows or rides beside them.

- **2026-09-24** — created from the review of an agent session on a private
  series. Both NAC tables were measured the same day, at `2d42303a`. The
  private-series numbers were re-read from that session's saved results.
  Next: the air term, then the flexible-side measurement.
