# WP-1437 — a formula the code does not compute

Milestone: unscheduled · Status: ✅ 2026-09-17 — three entries corrected, 41
audited, the thresholds pinned and the formulas given a review rule
Depends on: —

## Goal

`help.py`'s parameter descriptions agree with the code they describe. The
`instrument.polarization` entry stops telling users a formula that diverges
from the package's own by up to 2×, the other fourteen equation-bearing
descriptions are checked once and the result recorded, and the numeric
thresholds are pinned so they cannot drift again.

## Context

`src/rietx/help.py` is the declared one authority for what a name *is*
(WP-1202, root CLAUDE.md § Conventions). Its `unit` and `default` fields are
the schema's own through `UNIT_DISPLAY`. Its `description` and `typical` are
**authored**, so any formula in a description is a copy with nothing holding it
to the code. One of them is wrong.

### The defect

| | `help.py` says | the package computes |
|---|---|---|
| the Lp factor | `(1 + K·cos²2θ)/(1 + K)` (`help.py:209`) | `K + (1 − K)·cos²2θ` (`corrections.py:24`) |
| monochromated | "`cos²2θ_M` for a monochromated one" (`help.py:211`) | `K = 1/(1 + cos²2θ_m)` (`schemas/instrument.py:1879`, code at `:1901`) |

Measured 2026-09-17 by running both forms through `lorentz_polarization`. The
ratio of the help-text Lp to the computed Lp:

| K | 2θ=30° | 2θ=90° | 2θ=150° |
|---|---|---|---|
| 0.5 (unpolarised lab) | 1.048 | 1.333 | 1.048 |
| 0.556 (graphite 002, Cu) | 1.024 | 1.156 | 1.024 |
| 0.799 | 0.936 | 0.696 | 0.936 |
| 0.99 (synchrotron) | 0.878 | **0.508** | 0.878 |

Worst at K = 0.99, the value the entry itself quotes for 11-BM. **The ratio
varies with angle**, so a phase scale cannot absorb it; it biases ADPs and
phase fractions. The monochromator prescription is wrong separately: for
graphite (002) at Cu the entry's wording gives K = 0.799 where the schema gives
0.556.

### The root cause, and why it belongs beside WP-1436

Neither formula is wrong in isolation. help.py prints the *monochromator*
expression, which is exactly right when its `K` means `cos²2θ_m`. The entry
binds that letter to the package's own `K`, a different quantity. This is a
symbol collision that reached a user-facing number, so it is the expensive end
of the same story WP-1436 covers.

`help.py:1346` repeats the second error for `monochromator_two_theta`.

### Reach

Three surfaces carry it: `GET /api/help` in the GUI (`src/rietx/gui/server.py:197`),
the generated glossary (`docs/manual/conf.py:271`, body at
`docs/manual/_generated/glossary-body.md`), and `rietx.help` imported directly.

### The class, sized

Parsed 2026-09-17: **116** `description=` blocks, of which **15** carry an
equation and **6** carry a number with a unit. The defect above is one of the
15. The other fourteen have never been checked against their code.

Those six sentences quote **three** live constants between them, and all three
currently agree, so they carry drift risk only. Re-derive the six from
`help.py` before pinning: the count below is of constants, not of sentences,
and a sentence quoting a fourth constant would not appear here.

| description says | live constant |
|---|---|
| "2 nm" (`help.py:659`, `:696`) | `SIZE_CAP_MIN_SIZE_A = 20.0`, `params/vector.py:635` |
| "5 nm" (`help.py:662`) | `SIZE_FLAG_SIZE_A = 50.0`, `refine.py:4875` |
| "1.5 deg" (`help.py:681`) | `STRAIN_FLAG_WIDTH = 1.5`, `refine.py:4773` |

The manual injects these as MyST substitutions from the live package.
`help.py` imports nothing but `dataclasses` and `fnmatch`, so it has no such
mechanism and gains none here.

### The seam to extend

`tests/test_help.py` already owns this shape of check, and a new one is a
sibling rather than an invention:

- `test_units_are_the_schemas_own` (`:490`)
- `test_defaults_are_the_schemas_own` (`:524`)
- `test_search_control_defaults_are_the_schemas_own` (`:391`)

`test_every_entry_has_a_title_and_a_description` (`:633`) checks presence only,
which is why this class was unguarded.

## Non-goals

- The `k` = sinθ/λ rename and the notation table. That is WP-1436, which
  rebases onto this one because both edit `docs/manual/intensities.md`.
- Deriving descriptions from the code generally. Prose is authored on purpose,
  and a templating layer over 116 entries would cost more than it saves. The
  answer here is one audit plus a pin on the numbers.
- The other fifteen symbol findings of the 2026-09-17 audit. They are WP-1436's
  or explicitly not generalised there.

## Tasks

- [x] Correct `help.py:205-217` (`instrument.polarization`): the factor becomes
      `K + (1 − K)·cos²2θ`, the monochromator prescription becomes
      `K = 1/(1 + cos²2θ_m)` quoting 0.556 for graphite (002) at Cu. Reuse the
      wording already correct at `schemas/instrument.py:1762-1766` and
      `docs/manual/corrections.md:30`.
- [x] Correct `help.py:1342-1352` (`monochromator_two_theta`), same root cause.
- [x] `docs/manual/intensities.md:104` — the third site of the same `K`
      confusion. It says "an unpolarised neutron beam sets $K = 1$", where
      `corrections.py:17` defines K as the σ-polarised *fraction* with K = 0.5
      unpolarised. The arithmetic is right, since K = 1 gives the bare Lorentz
      factor a neutron pattern wants, but the word is attached to the wrong
      value and the same chapter's `corr-lp` defines K the other way. The skill
      is clean here: `diagnostics-gsas.md:61` states the value without
      labelling it.
- [x] Audit the remaining fourteen equation-bearing descriptions against the
      code each describes. Record every one in the handover, checked or
      corrected. **This is the deliverable**; the two fixes above are its first
      finding.
      *Done 2026-09-17, over a wider class than the WP sized: **41 entries**
      carrying a checkable claim, not 15. A shape claim ("shifts as sin 2θ"),
      an identity claim ("r = 1 is exactly no correction") and a frozen
      constant ("3.5 FWHM") are each as checkable as a formula and drift the
      same way, so restricting the audit to written equations would have
      missed the third defect. Three entries were wrong; the other 38 held.
      The full table is in the handover entry.*
- [x] Pin the three numeric thresholds against their live constants, as a
      fourth `*_are_the_schemas_own` member in `tests/test_help.py`.
- [x] A review rule in `help.py`'s module docstring: a description that states
      a formula or a threshold names where the real one lives.
- [x] Check whether the agent skill restates the polarisation factor; re-sync
      the two committed copies with `rietx skill --install . --copy` if it does.
      *It does not, so no re-sync. The skill's only Lp-adjacent statement is
      `diagnostics-gsas.md:61`, "`NeutronSource` pins K = 1", which agrees with
      `schemas/instrument.py:277`. Its other `K` (`judging.md:338-341`) is the
      **Scherrer** constant, named as such in the preceding sentence and
      correct at 0.9 (`profiles/caglioti.SCHERRER_K`).*
- [x] Skill: a row only if the skill carries the wrong formula. An agent
      driving rietx reads `polarization` as a value to set, not a formula to
      evaluate, so the body needs nothing. *No row added.*

### Found by the audit, beyond the WP's two

- [x] `help.py:420-430` (`instrument.profile.v`) made two wrong claims. "The
      only Caglioti term allowed to be negative" — `ProfileTCHZ.u`'s default
      `min` is −0.05, so U may go negative too; only W, X and Y are
      softplus-floored at zero. And "the minimum of the width curve sits where
      it cancels against U" — the minimum is at tanθ = −V/(2U), where the V
      term is −2× the U term rather than cancelling it (measured: numeric
      argmin at tanθ = 0.750000 against the predicted 0.750000, rel. 2.4e-7,
      on U = 0.02, V = −0.03, W = 0.05, chosen so V² − 4UW < 0 keeps the
      variance off `_MIN_GAMMA_G2`). Both corrected, and the entry now names
      `gaussian_fwhm` under the new review rule.

## Acceptance

The corrected entry matches the code at every K the entry names, checked by
evaluating rather than by reading.

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_manual_api.py
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

Then read the entry back out of the two surfaces that ship it, because neither
is exercised by the command above: `GET /api/help` from a running
`rietx gui`, and the glossary page in the built HTML.

## References

- International Tables for Crystallography Vol. C §6.2; Azároff (1955), for the
  monochromator polarisation factor. Both already cited at
  `schemas/instrument.py:1765`.
- The correct forms in-tree: `model/corrections.py:11-19`,
  `schemas/instrument.py:1875-1880`, `docs/manual/corrections.md:26-30`.

## Handover log

### 2026-09-17 (2nd session) — the class audited, three entries were wrong

The package's built-in help was telling people a polarisation formula that
disagrees with the one the package computes, by up to a factor of two at the
very setting its own sentence quoted as an example. Nobody's fit was affected,
because no code reads that prose — but anyone who took the formula and worked
a number out by hand got a wrong one, and the error varies with angle, so it
is not the kind a scale factor quietly absorbs. Auditing every other entry that
states something checkable found one further wrong description and confirmed
the other thirty-eight. The class is now half closed rather than closed: the
numbers a description quotes are pinned to their live constants by a test, and
the formulas carry a review rule instead, because prose has no authority a test
can read.

**Done.** Three entries corrected, plus the two guards.

- `instrument.polarization` said the factor was `(1 + K·cos²2θ)/(1 + K)`; the
  package computes `K + (1 − K)·cos²2θ`. Neither form is wrong in isolation.
  The entry printed the *monochromator* expression, which is right when its `K`
  means `cos²2θ_m`, and bound that letter to the package's own `K`. The same
  sentence then said a monochromated source takes `K = cos²2θ_M`, where
  `Instrument.bragg_brentano` computes `1/(1 + cos²2θ_m)`.
- `monochromator_two_theta` repeated the second half.
- `docs/manual/intensities.md` called `K = 1` "an unpolarised neutron beam",
  where the chapter's own `K` is the σ-polarised fraction and unpolarised is
  0.5. The arithmetic was right and the label was not. `NeutronSource`'s
  docstring already carried the honest reason (neutrons are not polarised the
  way the Thomson cross-section polarises X-rays, so there is no polarisation
  term at all), so the paragraph now quotes it rather than inventing a second
  explanation.
- `tests/test_help.py::test_quoted_thresholds_are_the_codes_own` — the fourth
  `*_are_the_schemas_own` member, and the first to reach into `description`.
- `help.py`'s module docstring takes a third rule: a description stating a
  formula or a threshold names where the real one lives.

**Measured.**

- The divergence, by running both forms through `lorentz_polarization` rather
  than reading them. Ratio of the help-text Lp to the computed Lp:

  | K | 2θ=30° | 2θ=90° | 2θ=150° |
  |---|---|---|---|
  | 0.5 (unpolarised lab) | 1.048 | 1.333 | 1.048 |
  | 0.5557 (graphite 002, Cu) | 1.024 | 1.157 | 1.024 |
  | 0.799 | 0.936 | 0.696 | 0.936 |
  | 0.99 (11-BM, the entry's own example) | 0.878 | **0.508** | 0.878 |

  Reproduces the WP's Context table exactly. **The ratio varies with angle**, so
  a phase scale cannot absorb it.
- Graphite (002) at Cu, 2θ_m = 26.6°: the schema gives K = 0.5557, the entry's
  wording gave 0.7995.
- Fast suite **5312 passed, 133 skipped**, `[dev]`, darwin/arm64, ~84 s,
  nothing else mid-suite (`ps aux | grep -c '[p]ython -m pytest'` → 0). One test
  added, and `test_help.py` went 22 → 23 `def test_` with no `parametrize` in
  the file, so the +1 is a new pass and not a new skip. The full suite did not
  run: nothing here can move a measured number, since every edit is a docstring,
  a prose sentence or a new test.
- The new guard was made to fail on purpose in **both** directions
  (`tests/CLAUDE.md` § Guards that go quiet). Retuning `SIZE_CAP_MIN_SIZE_A` to
  30.0 gives "SIZE_CAP_MIN_SIZE_A is 3 in the sentence's units, which spells
  '3 nm', but the row claims '2 nm'"; drifting the sentence to "4 nm" with the
  constant held names the stale path. Both reverted, verified by `git diff`.
- Both shipping surfaces read back, neither being exercised by the acceptance
  command: the built glossary HTML, and `GET /api/help` off a server on port
  8749. Both carry the corrected text, and neither wrong form (`(1 +
  K·cos²2θ)/(1 + K)`, `cos²2θ_M`) survives anywhere in either payload.
- Re-measured after the review pass landed its fixes: **5312 / 133 again**, on
  a branch `git fetch origin main` showed was not behind, so this is the tree
  that merges.

**The review pass changed five things, two of them in this WP's own guard.**
`/code-review high --fix`, all five accepted, nothing declined.

- The new review rule cited `test_size_and_strain_thresholds_are_the_code's_own`,
  which does not exist. A rule whose entire mechanism is "a reader can reach the
  real authority by grep" shipped with a reference that finds nothing. This is
  the WP's own failure mode, one rank in.
- **The guard's substring test was unanchored.** A sentence drifting from
  "5 nm" to "15 nm" still *contains* "5 nm", so it passed on exactly the drift
  its docstring claims to catch. Now a digit-boundary lookbehind, re-verified
  both ways: "below 15 nm" no longer matches "5 nm", "at 12 nm" no longer
  matches "2 nm", "past 11.5 deg" no longer matches "1.5 deg".
- The `typical` band written for `instrument.polarization`, 0.51-0.56, covered
  three of the six anodes the package ships. Through
  `Instrument.bragg_brentano` with graphite (002): Ag 0.507, Mo 0.511, Cu 0.556,
  Co 0.576, Fe 0.590, Cr 0.630. A Cr-anode user would have read a correct K as
  out of range, in the one field whose stated job is a sanity-check range.
  Widened to 0.51-0.63 with the span named; `monochromator_two_theta` likewise
  (2θ_m 9.6-39.9°).
- "Declared and never refined" was a structural claim the code does not make.
  `ParameterTable._add` force-fixes the path only when the source is not
  `xray_cw`, so `set_vary` frees it on an X-ray source and nothing objects. Now
  "declared rather than refined, and no plan frees it", checked against all
  seven `PLAN_PRESETS` — no glob in any of them reaches the path — with the
  force-fix stated where it is true, on the neutron source.
- Flagged and deliberately skipped, by the review and on review: the V entry
  writes the Gaussian law instrument-only, without the `gauss_size` term
  `gaussian_fwhm` also carries. The adjacent `instrument.profile.u` entry has
  spelled it that way since before this diff, so changing one would split the
  pair. Worth a future entry-pair fix, not this one.

**The audit — 41 entries, the deliverable.** The WP sized the class at 15
equation-bearing descriptions. That is the count of written *equations*; the
checkable class is wider, because a shape claim ("shifts as sin 2θ"), an
identity claim ("r = 1 is exactly no correction") and a frozen constant
("3.5 FWHM") each drift exactly the same way and each has a code authority.
Restricting the audit to equations would have missed the third defect. Every
entry below was checked against the function that computes it, by evaluation
wherever evaluation was possible.

| Entry | Claim checked | Against | |
|---|---|---|---|
| `instrument.polarization` | `(1 + K·cos²2θ)/(1 + K)` | `corrections.lorentz_polarization` | ✗ **fixed** |
| `instrument.polarization` | monochromated K = `cos²2θ_M` | `Instrument.bragg_brentano` | ✗ **fixed** |
| `monochromator_two_theta` | K = `cos²2θ_M` | same | ✗ **fixed** |
| `instrument.profile.v` | "only Caglioti term allowed to be negative" | `ProfileTCHZ.u.min = −0.05` | ✗ **fixed** |
| `instrument.profile.v` | minimum "where it cancels against U" | minimum is at tanθ = −V/(2U) | ✗ **fixed** |
| `polarization` (preset field) | BB derives K from the mono angle; transmission K = 0.5 | `bragg_brentano`, `Geometry` | ✓ |
| `mu_r` | ΔB = c(µR)·λ²/2; µR = 0 is the off state | `absorption.py:52` | ✓ |
| `mu_t` | off state is the geometry's; µt = 0 refused on BB; sec θ footprint in transmission | `absorption.py:100-102`, `Geometry` validator | ✓ |
| `…geometry.sample_displacement` | −2s·cosθ/R | `displacement_shift_deg` | ✓ |
| `…geometry.sample_transparency` | sin 2θ shift | `transparency_shift_deg` | ✓ |
| `…capillary_offset_along_beam` | sin 2θ | `capillary_displacement_shift_deg` | ✓ |
| `…capillary_offset_across_beam` | cos 2θ | same | ✓ |
| `…surface_roughness.a` | R = [a+(1−a)e^(−b/sinθ)]/[a+(1−a)e^(−b)]; b = 0 the identity | `surface_roughness_suortti`, evaluated | ✓ |
| `…surface_roughness.b` | both limits return the identity | evaluated at b = 0 and b = 1e3 | ✓ |
| `…surface_roughness.c` | R = 1 − c·u·(1−u), u = τ/sinθ; c = 0 no correction | `surface_roughness_pitschke`, evaluated | ✓ |
| `…surface_roughness.tau` | τ = t₀/β; monotone while sinθ ≥ 2τ; amplifies past sinθ = τ | same docstring, Eq (18) | ✓ |
| `instrument.profile.u` | Γ_G² = U·tan²θ + V·tanθ + W; `gauss_strain` adds to it | `gaussian_fwhm`, evaluated | ✓ |
| `instrument.profile.v` | nothing in the specimen reaches V | evaluated | ✓ |
| `instrument.profile.x` | Γ_L = X/cosθ + Y·tanθ | `lorentzian_fwhm` | ✓ |
| `instrument.profile.y` | tanθ; `lor_strain` adds | same | ✓ |
| `instrument.background.c*` | y_bkg = Σ c_n T_n(x), x on [−1, 1] | `chebyshev_design_matrix` | ✓ |
| `instrument.background.scale` | + s·f(2θ) | `forward.py:3001` | ✓ |
| `instrument.background.air` | additive 1/(2θ), beside the spline rows | `forward.py:3020` | ✓ |
| `…extra_components.*.position` | unbounded; inert until freed | `HumpComponent` | ✓ |
| `…extra_components.*.height` | h = 0 makes the term identically zero | softplus min 0, linear in h | ✓ |
| `…extra_components.*.center` | must carry finite min/max (frozen window) | `compile_model` | ✓ |
| `…extra_components.*.eta` | window ≈1 FWHM at η = 0, ≈16 at η = 1 | `window_fwhm_mult`: 0.988, 15.91 | ✓ |
| `phases.*.lor_size` | 1/cosθ; adds to instrumental X | `caglioti.py:63` | ✓ |
| `phases.*.lor_strain` | tanθ; adds to Y; Stephens block locks it | `lorentzian_fwhm`, `stephens.py` | ✓ |
| `phases.*.gauss_size` | 1/cos²θ variance | evaluated | ✓ |
| `phases.*.gauss_strain` | tan²θ variance, stacks on U | evaluated | ✓ |
| `…preferred_orientation.r` | r = 1 exactly no correction; bound 0.15 as March divides by r | `march_term`, `MARCH_R_MIN` | ✓ |
| `phases.*.atoms.*.biso` | B = 8π²·Uiso; damps as exp(−B·sin²θ/λ²) | `EIGHT_PI_SQ`; `structure_factor.py:276` | ✓ |
| `phases.*.atoms.*.u11…u23` | tied, not free; outside the subspace refused | `params/vector.py:1037-1056` | ✓ |
| `phases.*.atoms.*.adp.*` | U = Σ θ_k·B_k, absolute | affine ties off `adp_basis` | ✓ |
| `phases.*.microstrain.s*` | literal monomial h^H k^K l^L; 10⁻¹² Å⁻⁴ | `stephens.py:14,36` | ✓ |
| `phases.*.microstrain.dof.*` | S = 0 has unbounded slope; cone, not a box | `stephens.py`, `STEPHENS_STRAIN_NOT_POSITIVE` | ✓ |
| `kalpha2_residual` | δ(2θ) = 2·(λ₂/λ₁ − 1)·tanθ | `pick.py:473` | ✓ |
| `axial_tail`, `PEAK_AXIAL_TAIL` | 3.5 FWHM | `PEAK_AXIAL_TAIL_MAX_FWHM = 3.5` | ✓ |
| `unresolved_shoulder`, `PEAK_UNRESOLVED_SHOULDER` | half a FWHM | `PAWLEY_OVERLAP_FWHM_FRAC = 0.5` | ✓ |
| `ftol` | the last stage at the solver's 1e-9 | `least_squares.py:1206` | ✓ |
| `strain_seed` | microstrain in ppm | `plan.py:89` | ✓ |
| `restraint_weight_scale` | S = S_y + c_w·S_G; 1.0 the identity | `plan.py:92` | ✓ |
| `max_candidates` | each engine hands the merge 5× | `ENGINE_POOL_MULTIPLE = 5` | ✓ |

**Gotchas for whoever touches this corpus next.**

- **The numbers are pinned; the formulas are not, and cannot be.** Four
  sentences quoting three constants are now held by a test. A formula has no
  such authority — the only guard is the review rule, which works by making the
  computing function reachable from the sentence.
- **A fourth number with a unit stays deliberately unpinned**: `biso`'s "about
  5 Å² for a heavy atom" is a rule of thumb with no live constant behind it. The
  WP asked for the three to be re-derived rather than trusted, and they hold at
  three. A new sentence quoting a fourth constant would not have shown up in the
  WP's table, so it will not show up in the test either — adding a row is manual.
- **`_QUOTED_THRESHOLDS` converts into the sentence's units**, Å to nm, because
  the code stores a crystallite floor in Å and people read it in nm. The row
  derives the spelling rather than asserting it, so a wrong converter fails
  rather than certifying its own arithmetic.
- **Testing the Caglioti minimum needs V² − 4UW < 0.** Otherwise the variance
  goes negative, `gaussian_fwhm` clamps it at `_MIN_GAMMA_G2`, and `argmin`
  lands on the edge of a flat plateau rather than at the minimum. The first
  attempt did exactly that and reported tanθ = 0.191 against the predicted
  0.750.
- **The `parameters` arm of `GET /api/help` is a list, not a mapping**, because
  several globs share one entry. Probing it as a dict answers "absent" for
  everything and looks like a missing entry.
- **The skill needed nothing.** Its only Lp-adjacent line is "`NeutronSource`
  pins K = 1", which agrees with the schema. Its other `K` is the **Scherrer**
  constant (`judging.md:338-341`), named as such and correct at 0.9. No row, no
  re-sync.

**Next.** [1436](1436-k-is-the-wavevector-everywhere-else.md) is the rest of
this audit's parent and rebases onto this branch, both editing
`docs/manual/intensities.md`. Two things this session learned change it, and
both are in its `### Inherited`: the `K`/`k` collision has a *third* live site
in that chapter, already corrected here, and the collision is now known to have
reached a user-facing number rather than only the notation. Nothing else is
blocked.

- **2026-09-17 (arrival)** — every anchor in this file re-checked against the
  tree before starting (`/wp-start` step 5). Content and physics all held; six
  line numbers did not: `schemas/instrument.py`'s docstring formula and code
  (cited 1765/1787, actually 1879/1901 — a consistent 114-line offset, the
  file itself untouched since WP-1309, so the audit's own count was off from
  the start rather than drifted), the `monochromator_two_theta` HelpEntry
  (cited 1320-1330/1324, actually 1342-1352/1346), the three threshold
  citations in `help.py`/`params/vector.py`/`refine.py`, and all four
  `test_help.py` anchors (each off by 9-22 lines, file-by-file consistent).
  `docs/manual/intensities.md:104` and the two `help.py:205-217` /
  `corrections.py:24` anchors were exact. Corrected in place above; no claim
  changed, only where to find it.
- **2026-09-17** — created, out of the notation audit that also opened
  [1436](1436-k-is-the-wavevector-everywhere-else.md). A comment on a LinkedIn
  post about the package questioned one symbol; auditing the tree for its
  siblings found this, which is worse, because a symbol bound to the wrong
  quantity here reaches a number a user acts on. The divergence table in
  Context was measured by running both forms, after a first pass that read them
  and understated the effect by half. The class is sized and the guard's family
  is named, so the work needs no further investigation. Next: the two
  corrections, then the fourteen-entry audit.
