# WP-1036 — Crystal-system cell ties: the settings the tables do not check

Milestone: v1.0 · Status: ⬜
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

### The measurement that decides the priority — and it has not been made

`structure_from_cif` stores gemmi's canonical `sg.xhm()`
(`crystallography/cif.py:81`), and gemmi resolves a bare `R -3 c` to the **`:H`**
setting. So it is entirely possible that **no input this package has ever read
reaches the broken branches**, in which case this is a latent trap to fence
rather than a live bug to chase.

Nobody has checked. Saying "reachable from any CIF" without that sweep is the
mistake this project has a name for — a status claim asserted rather than
measured, which is what the WP-1019 volume-envelope audit caught (a
least-squares *mean line* described as an upper envelope, used as a hard search
ceiling). **Task 1 is the sweep, and the rest of the WP is scoped by its
answer.**

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

- [ ] **Measure the reach.** Sweep every CIF in `tests/data` and the COD entries
      the WP-1028 benchmark used (branch `wpem-benchmark`), recording what each
      resolves to via `structure_from_cif` → `sg.xhm()` /
      `crystal_system_str()` / `monoclinic_unique_axis()` /
      `is_reference_setting()`. Report how many reach a c-unique monoclinic or a
      rhombohedral-axes setting. **Write the answer into this file** — if it is
      zero, say zero; that is a finding, not a non-result.
- [ ] **`_FIXED_ANGLES` reads `monoclinic_unique_axis()`** instead of assuming
      b, with a test per axis choice asserting *which* angle is held.
- [ ] **`_CELL_TIES` distinguishes the rhombohedral setting** from the
      hexagonal one, with a test asserting a = b = c and α = β = γ under `:R`.
- [ ] **Settle the locked-at-current-value question**: either a symmetry-fixed
      angle is normalised to its symmetry value as a visible model edit, or the
      table refuses a cell whose fixed angle disagrees with its symmetry and
      says by how much. Silence is not an option — that is the state today.
- [ ] **Refuse what is not served**, in the raise's own words, naming the symbol
      and the setting rather than the table it fell out of.
- [ ] **Re-read `docs/manual/parameterisation.md`** in the same change: its line
      20 states the ties as a settled fact (*"Crystal-system cell ties
      (b ← a, fixed angles)"*) with no mention of a setting, which is the prose
      form of the same assumption. `tests/test_manual.py` enforces the fenced
      constants, not sentences, so this one is read by hand.
- [ ] Tests in `tests/test_params.py` / `tests/test_wyckoff.py` naming each
      setting covered; plus a refinement that would have been mis-tied, with its
      obs/calc/diff PNG in `tests/output/`.

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
