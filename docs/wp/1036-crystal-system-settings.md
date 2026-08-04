# WP-1036 — Crystal-system cell ties: the settings the tables do not check

Milestone: v1.0 · Status: ✅ 2026-08-04 — the three defects fixed, the reach
measured (zero live inputs, all three CIF-reachable), and the cell ties now
derive from the *setting*; 1035 is unblocked
Depends on: — · **blocks** 1035

## Goal

The cell ties and symmetry-fixed angles a `ParameterTable` builds are correct
for every setting a space-group symbol can name, or the table refuses the symbol
and says why — and it is known, by measurement, whether any real input has ever
reached the branches that are wrong today.

## Context

**This is not a GUI work package.** It came out of the GUI session that asked
where the space group is displayed, but it is about the code that decides which
cell parameters are refinable, and a wrong answer there is a quietly wrong cell —
the class of defect the validation matrix exists to catch and the one thing that
can invalidate a published number.

### What the tables say (read at `660c950`)

`params/vector.py:97-116` declares two module-level dictionaries, consumed by
`ParameterTable._collect` (`:140-152`) after `sg.crystal_system_str()`:

```python
_CELL_TIES = {..., "trigonal": {"b": "a"},  # hexagonal-axes setting (gemmi default for R groups)
              "monoclinic": {}, ...}
_FIXED_ANGLES = {..., "monoclinic": ("alpha", "gamma"), ...}
```

Three things follow, and each is a defect of a different kind:

1. **`_FIXED_ANGLES["monoclinic"]` hard-codes the b-unique setting.** gemmi
   knows the difference — `monoclinic_unique_axis()` returns `'b'` or `'c'`, and
   `P 1 1 2/m` resolves and reports `'c'` — but the table never asks. On a
   c-unique symbol the free angle **γ** would be locked and the
   symmetry-fixed **β** left refinable: exactly inverted.
2. **`_CELL_TIES["trigonal"]` assumes hexagonal axes**, and its own comment says
   so. A rhombohedral-axes R setting (`R -3 c:R`, which resolves, crystal system
   "trigonal") needs a = b = c and α = β = γ; it would instead get `b ← a`, `c`
   wrongly free, and all three angles wrongly locked.
3. **A symmetry-fixed angle is locked at its stored value, never at its
   symmetry value.** `_add(..., force_fixed=True)` (`vector.py:150-151, 130-138`)
   holds whatever the `Parameter` currently carries. Nothing in this package
   knows that a hexagonal γ "should be" 120° — that number exists nowhere
   outside imported CIFs. So a monoclinic β = 93.2° survives, *locked*, under an
   orthorhombic symbol, and every d-spacing is computed from it
   (`forward.py:1129`).

There is also **no schema validator on the symbol**: `Phase.space_group` is a
bare `str` (`schemas/structure.py:310`), so nothing refuses an unresolvable or
unsupported setting until something calls `get_spacegroup`.

### The measurement that decides the priority — MADE 2026-08-04

Two questions, and they have **different answers**. That is the finding.

**Q1: does any input this package has ever read reach the broken branches? No —
zero, of 28.** Swept: the 3 CIFs in `tests/data`, the 14 COD entries the WP-1028
benchmark fetched (re-fetched for this sweep; the branch gitignores them), and
every `space_group="…"` literal in `src`/`tests`/`examples`/`gui` (12 distinct
symbols). Every monoclinic entry is b-unique (`C 1 2/c 1`, `I 1 2/c 1`,
`P 1 21/c 1`, `P 21/n`); the one R symbol, `R -3 c`, resolves to **`R -3 c:H`**;
no fixed angle disagrees with its symmetry anywhere. Several *are* non-reference
settings (`P m c n`, `P b n m`, `P c m n`, `I 1 2/c 1`), but orthorhombic axis
permutations do not touch the cell tables. `nist_srm660c_100a.cif` is pattern
data, not a structure — 8 blocks, `read_small_structure` refuses it, unrelated.

**Q2: can a CIF reach them? Yes — all three, and one is worse than described
above.** Probed by writing minimal CIFs and reading them back through
`structure_from_cif`:

| CIF declares | reader resolves | table does | correct |
|---|---|---|---|
| `R -3 c` + rhombohedral cell | **`R -3 c:R`** | `b←a`, **c free**, α β γ all locked | `b←a`, `c←a`, α β γ *tied equal and free* |
| `P 1 1 2/m` + γ=98.3 | `P 1 1 2/m`, ua=`'c'` | locks α **and γ**, frees **β** | lock α β, free γ |
| `P 2/m 1 1` + α=98.3 | `P 2/m 1 1`, ua=`'a'` | locks α and γ, frees β | lock β γ, free α |
| `P m m m` + β=93.2 | `P m m m` | β **locked at 93.2** | refuse, or normalise visibly |

The premise in the paragraph this replaces was **wrong**: gemmi does not default
a bare `R -3 c` to `:H`. `read_small_structure` picks the setting **from the
cell** — a rhombohedral cell under a bare `R -3 c` comes back `:R`, `ext='R'`.
So defect 2 needs no non-standard symbol in the file at all, only rhombohedral
axes, which is how a good fraction of the R-lattice literature is written.

**And the degrees-of-freedom count is right in every one of these cases.** `:R`
tabulated gives {a, c} free = 2, correct is {a, α} = 2. c-unique monoclinic
tabulated gives {a,b,c,β} = 4, correct is {a,b,c,γ} = 4. This is WP-1020's
transposed-rotation lesson landing exactly where the plan predicted it would:
`tests/test_indexing_core.py::test_metric_subspace_dimensions_match_the_tabulated_cell_dof`
compares `6 − len(ties) − len(fixed)` against `METRIC_DOF` and **passes on the
wrong subspace**. A DOF test cannot see any of this.

Cost, measured (`d_spacings`, a=5 b=6 c=7): a fixed angle wrong by δ biases
d-spacings by **8.3 ppm per 1e-3°** (825 ppm at 0.1°). For defect 3's β=93.2°
under `P m m m`, (101) and (10-1) move −0.56° and +0.61° 2θ in opposite
directions while the orbit merge — which reads the *symbol*, not the cell —
still folds them into one peak.

**Verdict: a fence, not a fire.** No published number from this package is
affected, and the full suite must not move. But it is a fence against the next
rhombohedral CIF someone opens, not against a hypothetical, so it keeps its
place at the head of the queue.

### Where a fix has to hold

- `ParameterTable._collect` is the one place both tables are read, so the fix is
  local — but the table is rebuilt on **every** `parameters()`, `set_vary`,
  `set_values` and stage compile (`refine.py:269-279, 494-495`), so a symbol the
  new logic refuses becomes a refusal on a very hot path. Decide deliberately
  whether an unsupported setting raises at table build or is normalised earlier.
- Angle normalisation, if it lands, is **new physics knowledge in this
  codebase** — the 90/120/rhombohedral targets exist nowhere today. It belongs
  beside `_CELL_TIES`/`_FIXED_ANGLES` as one authority, never open-coded at a
  call site, and it must not silently rewrite a user's cell: a normalisation
  that moves a stored value is a model edit and has to be visible as one.
- **A test that only counts degrees of freedom will pass while the answer is
  wrong.** This is WP-1020's recorded lesson in a new place: the metric subspace
  was built from transposed rotations and reproduced the expected dimensions
  1/2/2/2/3/4/6 exactly, because the transposed set is a group too — only
  asserting that the *true* metric lies in the span caught it. Here the
  equivalent is asserting **which** angle is fixed and **which** length follows
  which, per setting, not how many of each there are.

## Non-goals

- **Not the GUI.** Displaying and editing the symbol is
  [1035](1035-symmetry-surfaced.md), which depends on this one because a
  "what would this change invalidate?" preview built on these tables would
  encode their two wrong settings.
- **Not a re-derivation of the site-symmetry machinery.**
  `wyckoff.coordinate_basis` / `adp_basis` and `stephens.strain_basis` derive
  their subspaces from the operators and are not implicated; this is only the
  cell.
- **Not a setting *converter*.** Transforming a structure from `:R` to `:H` axes
  is a different feature; refusing a setting the tables cannot serve is enough.

## Tasks

- [x] **Measure the reach.** Sweep every CIF in `tests/data` and the COD entries
      the WP-1028 benchmark used (branch `wpem-benchmark`), recording what each
      resolves to via `structure_from_cif` → `sg.xhm()` /
      `crystal_system_str()` / `monoclinic_unique_axis()` /
      `is_reference_setting()`. Report how many reach a c-unique monoclinic or a
      rhombohedral-axes setting. **Write the answer into this file** — if it is
      zero, say zero; that is a finding, not a non-result.
      → **zero of 28 existing inputs; all three reachable from a plain CIF**, and
      the `:H`-by-default premise was wrong. § *The measurement* above.
- [x] **`_FIXED_ANGLES` reads `monoclinic_unique_axis()`** instead of assuming
      b, with a test per axis choice asserting *which* angle is held.
      → all three axes covered, plus a fourth row (`P 1 1 21/b`) so the c-unique
      case is not a single symbol's quirk.
- [x] **`_CELL_TIES` distinguishes the rhombohedral setting** from the
      hexagonal one, with a test asserting a = b = c and α = β = γ under `:R`.
      → `sg.ext == "R"` is the discriminator, the same one `indexing/extinction.py`
      already used. The `:1`/`:2` extensions are origin choices and provably do
      not move the metric, so only `'R'` is tested for.
- [x] **Settle the locked-at-current-value question** → **refuse**, with the
      deviation in the message. `ParameterTable` has no diagnostics channel, so
      a normalisation there could not be made visible, and an invisible edit to a
      stored cell is worse than a refusal. `SYMMETRY_ANGLE_TOL_DEG = 1e-3`,
      chosen by consequence (8.3 ppm of d-spacing bias, against the 48 ppm of the
      tightest acceptance assertion), not by float noise.
- [x] **Refuse what is not served**, in the raise's own words, naming the symbol
      and the setting rather than the table it fell out of.
      → and the measured answer is that **nothing gemmi can produce is unserved**:
      the exhaustive test calls `cell_constraints` on all ~550 settings and none
      raises. The two raise branches are there to fail loudly rather than
      silently mis-tie if gemmi's table ever grows a case.
- [x] **Re-read `docs/manual/parameterisation.md`** in the same change: its line
      20 states the ties as a settled fact (*"Crystal-system cell ties
      (b ← a, fixed angles)"*) with no mention of a setting, which is the prose
      form of the same assumption. `tests/test_manual.py` enforces the fenced
      constants, not sentences, so this one is read by hand.
      → rewritten; the tolerance is a MyST substitution injected from the live
      constant, so retuning it fails the `-W` build.
- [x] Tests in `tests/test_params.py` / `tests/test_wyckoff.py` naming each
      setting covered; plus a refinement that would have been mis-tied, with its
      obs/calc/diff PNG in `tests/output/`.
      → 12 rows in `test_params.py`, 2 in `test_wyckoff.py` (one of them
      exhaustive over gemmi's table, in **both** directions — everything the
      constraints claim must hold, nothing they omit may hold), and the real-data
      arm in `test_acceptance_srm676a.py`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_params.py tests/test_params_surface.py tests/test_wyckoff.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

The bar is a test that **fails before the fix** for each of the three defects —
a c-unique monoclinic symbol whose held angle is asserted by name, a `:R`
trigonal symbol whose ties are asserted by name, and a fixed angle that
disagrees with its symmetry — verified red first, because a symmetry test that
counts degrees of freedom passes on the wrong subspace.

The full suite must not move: the whole point of the reach measurement is to
know whether any existing fixture is affected, and a changed acceptance number
would mean one is.

## References

- International Tables for Crystallography Vol. A — settings, unique axes, and
  the rhombohedral/hexagonal description of R lattices.
- `docs/wp/1020-indexing-core.md` — the transposed-rotation lesson: a
  dimension-counting test passes on the wrong subspace.
- `docs/wp/1019-indexing-data-quality.md` — the volume-envelope audit, the
  precedent for measuring a status claim before repeating it.

## Handover log

- **2026-08-04 (close)** — all seven tasks done, in one session. The measurement
  came first and reshaped the rest, exactly as the plan intended.

  **Read this before anything else: `main` moved under this branch.** It went
  c71d6e0 → 22d7d8c mid-session when WP-1030 merged (PR #24), so `worktree-gui`
  is **not** a fast-forward and a trial `git merge-tree` reports **two
  conflicts, both pure bookkeeping**: CLAUDE.md's `### Current numbers` block
  and ROADMAP's `## Current focus` + WP table row — the two places every
  close-session writes. No code conflicts. `tests/test_indexing_core.py` merges
  clean and is *semantically* clean too: 1030 only added tests elsewhere in the
  file, while this WP replaced
  `test_metric_subspace_dimensions_match_the_tabulated_cell_dof` (which imported
  the now-deleted `_CELL_TIES`/`_FIXED_ANGLES`) — so whoever merges must keep
  **this branch's** version of that test, or the import fails. `docs/manual/conf.py`
  merges clean (each side added one substitution).

  **And the numbers below are this branch's, not the merged tree's.** Both
  branches added tests, so `1596 / 1683` cannot simply be added to 1030's
  figures — the merged tree has to be re-measured, and the count check
  (passed+skipped moves by exactly the rows added) has to be redone against the
  merge, not against either parent. Quoting the tree is the same discipline as
  quoting the venv.

  **The sweep's two answers point opposite ways, and both are load-bearing.**
  Zero of 28 existing inputs reach any broken branch, so no published number
  from this package is affected and the full suite did not move. But all three
  branches are reachable from a plain CIF, and the plan's own premise was wrong
  about how: gemmi does *not* default a bare `R -3 c` to `:H`.
  `read_small_structure` picks the setting **from the cell**, so a rhombohedral
  cell under a bare `R -3 c` arrives as `R -3 c:R` with `ext='R'`. No
  non-standard symbol, no unusual file — just the axis convention a good part of
  the R-lattice literature is written in. That is why this closed as a real fix
  rather than as a fence, and why the `:H`-by-default sentence was deleted from
  the context section rather than left standing with a correction beside it.

  **The design decision that took the longest was defect 3, and the argument
  that settled it was not about friendliness.** `ParameterTable` is constructed
  with no diagnostics channel — deep on a hot path, rebuilt at every stage
  boundary and on every `set_vary`/`set_values` — so a normalisation there could
  not have been *made* visible, and the WP's own constraint ("a normalisation
  that moves a stored value is a model edit and has to be visible as one") rules
  it out on those grounds alone. Hence `check_cell_angles` refuses. The reason
  it is safe to refuse on that hot path is worth keeping: a symmetry-fixed angle
  is **locked**, so it cannot drift while a fit runs, and the answer is
  identical at every rebuild — a refinement that starts can never fail this
  mid-flight. `SYMMETRY_ANGLE_TOL_DEG = 1e-3` is chosen by consequence (8.3 ppm
  of d-spacing bias, an order of magnitude under the 48 ppm of SRM 660c's cell
  assertion), not by float noise, and comfortably above the round-off an
  indexing candidate's A..F → cell conversion arrives with.

  **WP-1020's lesson repeated itself in the strongest possible form.** The free
  cell-parameter *count* is right in every one of the three broken cases — 2 for
  both R settings, 4 for both monoclinic ones — so
  `test_metric_subspace_dimensions_match_the_tabulated_cell_dof` was passing on
  the wrong subspace the whole time. It has been rewritten to assert that a cell
  obeying the constraints lies inside the derived span **and** that breaking any
  one constraint leaves it, with the dimension checked last and explicitly
  labelled as worthless alone.

  **The test to keep is the exhaustive one**, and it is exhaustive because it
  needed no case table: `G = ⟨Rᵀ·G₀·R⟩` over a group's own operators is a
  symmetry-compatible metric for whatever setting those operators are in — the
  device `wyckoff._compatible_lattice` already used for spglib. So all ~550
  gemmi settings are checked in **both** directions: everything the constraints
  claim must hold, and nothing they omit may hold. The second direction is the
  one that catches an *under*-constrained table, which is what the original
  trigonal bug was. Verified by sabotage: removing the `:R` branch fails it on
  `R 3:R`, restoring the b-unique assumption fails it on `P 1 1 2`.

  **How much of the symbol space was served wrong: 79 of gemmi's 564 settings,
  14 %.** The census (`cell_constraints` over the whole table, 0 raises, 9
  distinct constraint shapes) breaks down as 247 orthorhombic / 88 tetragonal /
  52 hexagonal+trigonal-P+`:H` / 43 monoclinic b-unique / 43 cubic / 12
  triclinic — all correct before — against **37 monoclinic c-unique + 35
  monoclinic a-unique** (the held angle inverted) and **7 trigonal `:R`** (the
  tie set absent). Worth recording because "three defects" undersells it: the
  a-unique monoclinic case was not in the plan at all, and it is the second
  largest of the three.

  **Measured, `[dev]` numpy-only worktree venv, darwin/arm64 M4:**

  - fast suite **1596 passed / 108 skipped**, 48 s quiet (1:41 with the full
    suite running alongside — same tree, twice). +19 on the 1577/108 baseline:
    14 new rows (12 `test_params`, 2 `test_wyckoff`) plus **5 from one new
    `validation_matrix` Claim**, which five parametrised tests each expand. No
    new skips.
  - full suite **1683 passed / 117 skipped**, 11:59 — +20 on 1663/117, the
    fast selection's +19 plus the one slow-marked acceptance row. The first
    full run failed two bookkeeping guards and both were doing their job: the
    ROADMAP-glyph mirror (fixed by the close commit that run predated) and
    `test_every_acceptance_test_has_a_matrix_row`, which refused the new
    corundum test until it was registered with what its tolerance is
    referenced to.
  - the real-data arm: corundum's two descriptions refined independently from
    the identical physical lattice land on the same answer to **1.4e-9 / 1.2e-8**
    relative with Rwp equal to five decimals; α walks 54.987 → 55.292 against a
    certificate of 55.287. 2.35 s, Rwp 0.150, GoF 1.67.

  **What is *not* done, deliberately.** `Phase.space_group` is still a bare
  `str` with no schema validator — the WP's context notes it, no task asked for
  it, and adding pydantic validation right before the API freeze would change
  the error type at every construction site including history-node
  deserialization. An unresolvable symbol already raises from `get_spacegroup`
  naming itself, so the gap is *where* the failure lands, not whether it
  happens. Worth a line in the freeze WP (1003) rather than a late change here.

  **1035 is unblocked**, and it inherits a real asset: `cell_constraints(sg)` is
  exactly the "what would changing this symbol invalidate?" oracle that WP wants
  a preview built on, and it is now right for every setting rather than for two
  of them.

- **2026-08-04** — created out of the GUI planning session that asked where the
  space group is shown, alongside [1032](1032-gui-repairs.md),
  [1033](1033-plot-range-regions.md), [1034](1034-panel-layout.md) and
  [1035](1035-symmetry-surfaced.md). Nothing is started.

  **The three defects were read, not measured**, and the distinction is the
  whole of task 1. The tables are wrong for the settings named above — that much
  is plain in the source. Whether any real input reaches them is **unknown**, and
  a first draft of this plan claimed "reachable from any CIF" before that was
  caught. If the sweep finds live inputs, this outranks every GUI item in the
  1032-1035 set and probably belongs ahead of the milestone's queue; if it finds
  none, it is a fence and can be sized accordingly.

  **It is placed first in the queue anyway**, because the sweep is cheap and its
  answer changes the ordering of everything else.
