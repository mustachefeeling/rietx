# WP-1912 — a polar axis has no origin, and the fit walks along it

Milestone: unscheduled · Status: 🔄 2026-10-13 — the hold lives in the table behind `Phase.floating_origin`, off by default; whether to turn it on is the maintainer's call on #727
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-05 — the default structural preset reaches it on every polar space group with a free coordinate, and the CIF it writes carries an absolute coordinate hundreds of cells out with an esd; flagged only by `FLAT_DIRECTION` on the result, so not P1

## Goal

In a space group whose origin is free along one or more directions (a polar
axis, or P1's three), a refinement that frees atomic coordinates fixes the
origin itself, says so by name, and returns coordinates inside the range they
started in, with esds that measure what the data measures. A caller can lift
the fix.

## Context

Issue #727 (mustachefeeling, 2026-10-05). In P 6₃ m c (ZnO) each site has one
free DOF along c, and the common shift of all of them changes no intensity.
Nothing in the package fixes that origin. `ParameterTable._collect_atom_coords`
(`params/vector.py:1213`) builds each atom's DOFs from its *own* stabilizer
(`wyckoff.coordinate_basis(stabilizer_rotations(sg, xyz))`), and no code under
`src/` derives a group-level origin constraint.

**Measured at `32ef5a6`** (synthetic Cu Kα ZnO, a = 3.2499, c = 5.2066,
z(O) = 0.3826, Biso 0.55, `Dispersion()` declared, 20-140° in 0.02°, Poisson
seed 3; scripts in the 2026-10-05 triage scratch, rebuilt in a minute):

- The issue's snippet lists `phases.0.atoms.0.dof.0` and `.1.dof.0`, both
  refinable.
- Both z shifted by +0.05 change the calculated pattern by 6.2e-16 of its
  maximum. The direction is exactly flat.
- A plan freeing scale, background, cell and `phases.*.atoms.*.dof.*` from
  z(O) + 0.02 ends `converged`, Rwp 0.098616, with z(Zn) = 634.1318 and
  z(O) = 634.5125. The difference, 0.38069, is the measurement. Each z is
  quoted at ±0.00111 and `structure_to_cif` writes `634.1318(11)`.
  `HIGH_CORRELATION` and `FLAT_DIRECTION` (ρ = −1.000) fire on the result. The
  CIF carries no flag.
- `plan="mccusker_structural"` walks the same pair to 147.837 / 148.218.
- `ref.hold(["phases.0.atoms.0.dof.0"])` gives the same Rwp, z(O) =
  0.3807(22), no flat-direction rows, and `HOLD_BLOCKED_PLAN` (info). The
  ±0.0011 on each free z was half of the honest 0.0022 on the difference.

*Superseded in part, 2026-10-12 (at `e1d19359`).* The walk now depends on
the driver. On the same fixture under `mccusker_structural` the default LM
driver moves the pair together by 0.010 (z(Zn) = 0.0101, z(O) = 0.3925),
while TRF still walks it to z ≈ 150. Both quote ±0.00029 on each z and fire
`FLAT_DIRECTION`. The half-the-honest-esd finding holds on both drivers.

**The floating-origin directions are already computable.** The same
`wyckoff.coordinate_basis`, given the rotation parts of *every* operation of
the group instead of a site's stabilizer, returns the subspace of translations
that commute with the point group, which is the continuous part of the
Euclidean normalizer. Measured: [001] for P6₃mc, Pna2₁, P4mm and R3m:H;
[010] for P2₁; [100] and [001] for Cc; all three axes for P1; none for
P2₁2₁2₁, Pnma and Fd-3m:1. No ITA table is needed. Cell setting does not matter,
because the rotations are read in the setting the phase states.

**Two shapes of fix, and the choice is the maintainer's (task 1):**

1. **A hold on one coordinate** per free origin direction (the issue). The
   cheapest form. The held atom then has no esd, and the others carry the
   relative uncertainty. The issue takes "the first atom with a free polar
   DOF"; the conventional choice is the heaviest scatterer, which conditions
   the rest best. Careful: `Refinement._user_holds` is the *caller's*
   authority (WP-1435) and `unhold` lifts it; a table-derived fix is a
   different population. `ParameterRow.needs_held_cell` (the flat
   wavelength-against-cell direction) is the precedent: a dynamic,
   table-derived held-reason with its own `held_because` text.
2. **A floating-origin constraint on a weighted centroid**: Σᵢ wᵢ·δᵢ = 0 along
   each free direction, wᵢ ∝ the atom's scattering power × multiplicity. This
   is what SHELXL does with a restraint (Flack & Schwarzenbach 1988); here it
   can be exact, because the condition is affine and C already carries affine
   rows. One DOF becomes a tie on the others, every atom keeps an esd, and no
   atom is singled out. It touches the Jacobian gate: the tied DOF's column
   reaches every atom on that axis, so `_column_extras` must see it (root
   CLAUDE.md, "An analytic Jacobian branch claims what one parameter *name*
   reaches").

Either way the rules that already govern coordinate DOFs apply. A DOF is
*relative* and anchored (WP-1432): `rebase_anchored_dofs` and
`anchored_dof_paths` must cover whatever this adds. A user tie onto a
coordinate DOF, or a named variable driving one, can already fix the origin.
The derivation must then add nothing, or it over-constrains.
`moving_paths` / `column_reach` (WP-1342), not names, decide what is free.
A phase with no free polar DOF needs nothing, and a phase with one such atom
has exactly one flat direction, so the same rule holds it.

**What moves:** the free-parameter count of every fit that frees coordinates
on a polar phase, so N − P, GoF and ΔBIC shift by one per direction. Zincite
appears in `tests/test_acceptance_qpa_roundrobin.py`, `tests/test_scale_b_ridge.py`
and the dispersion suites. Check which free its DOFs before claiming
bit-identity anywhere.

Licensing: SHELXL is closed. Use the paper only.

### Inherited

- **2026-10-13, from the issue triage (#727): the reporter withdrew the
  hold-one default and prefers the floating-origin restraint.** Posted
  2026-10-12: a restraint on a weighted centroid (Flack & Schwarzenbach 1988,
  *Acta Cryst.* A44, 499-506) chooses no atom, does not depend on atom
  order, leaves every atom an esd, and is one rule for every case
  `floating_origin_basis` returns (one axis, Cc's a-c plane, P1's three).
  They leave the weights, and restraint against exact constraint, to this WP.
  Draft PR #929 (2026-10-13) moves the existing opt-in hold into the table as
  `Phase.floating_origin: Literal["hold"] | None = None` and does not mention
  the withdrawal; a `"centroid"` value can join that `Literal`. Which mode is
  the default, if any, is still the maintainer's call. *Decided 2026-10-13
  (the maintainer, through the issue triage): the hold is the default now,
  and the centroid comes later as a second value.* `Phase.floating_origin`
  defaults to `"hold"` (#929 flips its `None`), so polar-group fits stop
  walking in the next release, `ORIGIN_FIXED_ON_POLAR_AXIS` names the held
  atom, and `unhold` lifts it. Once WP-1942's linear restraint item lands,
  `"centroid"` joins the `Literal` as an opt-in mode (Flack & Schwarzenbach
  1988, weights from the paper, not from memory), and both modes are
  measured on the ZnO, Cc and P1 fixtures before the default is revisited. A
  second default change, if one comes, moves the reported origin, never the
  structure, Rwp or any interatomic distance; each change goes in the
  release notes.

## Non-goals

- Discrete origin choices of non-polar groups (`:1`/`:2`); nothing floats.
- Choosing the origin for a *structure solution* search (1515's scope).
- The magnetic moment: an axial vector, not a position, so it has no origin.
- Changing `FLAT_DIRECTION` or `HIGH_CORRELATION` (1460 owns their dedup).

## Tasks

- [x] Decide with the maintainer: hold (and which atom) or centroid
      constraint; whether a caller lifts it with `unhold` or a new verb;
      the diagnostic's name (`ORIGIN_FIXED_ON_POLAR_AXIS` proposed) and level.
      *Decided 2026-10-06, through draft PR #749: a hold, on the first atom
      whose free DOF runs along the direction, lifted with `unhold`, and
      reported as `ORIGIN_FIXED_ON_POLAR_AXIS` (info), with
      `ORIGIN_NOT_FIXED` (warning) where no atom's DOF runs along it. For
      now it is an option the caller invokes
      (`Refinement.hold_floating_origin()`). Applying it by default in the
      table is not decided. The centroid restraint (Flack & Schwarzenbach
      1988, SHELXL's default) may come later as a second mode, because it
      keeps an esd on every atom and does not depend on which atom is held.*
- [x] `crystallography.wyckoff`: the group-level free-origin basis, tested on
      the ten groups above and on every gemmi setting, asserting **which**
      directions, not how many (root CLAUDE.md, the cell-ties rule).
      *Done 2026-10-12: `floating_origin_basis` landed with #749; the tests
      now name all ten groups, and every one of gemmi's 564 settings is held
      to a physics oracle (a site moved along each row and re-expanded leaves
      40 intensities unchanged, a shift off the span changes them, and the
      dimension matches the point-group symbol's polar class). A basis with
      its axes permuted fails at `P 1 2 1`. A basis built from transposed
      rotations gives the same answer on all 564, so the Rᵀ trap does not
      bite here.*
- [x] `ParameterTable`: the fix applied in the table, never at call sites;
      skipped where user ties or variables already fix the origin; the
      `ParameterRow` held-reason or tie, with its `held_because` text and its
      writer named (WP-1076).
      *Done 2026-10-12, behind a switch that is off by default:
      `Phase.floating_origin = "hold"` (schema 0.52). `ParameterTable`
      holds the first DOF running exactly along each floating direction
      through `Entry.held`, re-decided at every build, tie and hold. It adds
      nothing where an exact solve on the affine block finds the caller's
      ties or holds have fixed the origin already
      (`ParameterTable._origin_floats`). `ParameterRow.origin_axis`, written
      by `Refinement.parameters` from `ParameterTable.origin_holds`, gives
      the row its own `held_because`. `hold_floating_origin()` now sets the
      field, and `unhold` on a held DOF sets it back to `None`. A joint
      fit's per-histogram tables hold the same atom.*
- [x] The diagnostic naming the phase, the direction and the atom(s), and
      the ZnO regression: coordinates stay in [0, 1), CIF quotes an honest
      esd, no `FLAT_DIRECTION` on the coordinate pair.
      *Done 2026-10-12: `refine._origin_diagnostics` words what the table
      holds, on `fit` and `run_stage` results. `ORIGIN_FIXED_ON_POLAR_AXIS`
      (info) fires only where a stage's glob met the hold, and names the
      phase, the space group, the direction and the atom label.
      `ORIGIN_NOT_FIXED` (warning) fires only where a stage freed a DOF of a
      phase with an unfixed direction. `HOLD_BLOCKED_PLAN` leaves the origin
      hold out, so one fact gets one diagnostic. On the zincite fixture under
      `mccusker_structural` (LM and TRF), Zn stays at 0 with no esd and O
      refines to 0.38231(57), while the unheld pair quotes ±0.00029 on each
      z.*
- [x] `help.py` entry for any new field; Manual Part 2 (the constraint with a
      *Source* line beside the Wyckoff DOFs) and Part 1 (one paragraph).
      *Done 2026-10-12: `help.py` has no arm for a `Phase` field or a row
      extra, so the coordinate-DOF entry gained one sentence naming the hold.
      Part 2 carries `par-origin-floats` and `par-origin-hold` beside
      `par-origin`. Part 1 rewrites the `concepts.md` paragraph around the
      field and adds the origin hold to `model.md`'s held-reasons table. The
      1.9.0 staged notes carry the addition.*
- [x] Tests + obs/calc/diff PNGs to `tests/output/` for the ZnO case.
      *Done 2026-10-12: `tests/test_floating_origin.py` writes the three
      zincite fits (LM unheld, LM and TRF held), whole range and 30-40°, and
      checked by eye they are the same picture at Rwp 0.0993. A P 2₁2₁2₁
      and a Pnma fixture fit to the same free set and the same values bit
      for bit, declared or not, and raise no origin code.*
- [x] Skill: a row keyed by the new code. `references/diagnostics.md` is closed
      to growth (`tests/skill_caps.py`), so pay for it with a cut, or let
      the diagnostic's own `suggestion` carry it.
      *Done 2026-10-12, without a `diagnostics.md` row: it has 7 B left under
      its budget, and both codes now carry a `suggestion` saying what to do.
      The `references/numbers.md` paragraph #749 wrote, which names both
      codes, now describes the field, the quote rule for the held atom and
      the measured esds (+315 B, 23 766 B left). `api.md` regenerated for
      the two new fields, and the two committed copies re-synced.*

## Acceptance

On the ZnO fixture above, freeing every coordinate DOF under
`mccusker_structural` returns z(Zn) and z(O) within [0, 1), their difference
within 2σ of 0.3826, an esd on every coordinate the fix leaves free, no
`FLAT_DIRECTION` on the pair, and the new diagnostic once. A P2₁2₁2₁ and a
Pnma fixture are unchanged, asserted on the free set. The fast suite is green,
with each moved number named.

```sh
.venv/bin/python -m pytest tests/test_wyckoff.py tests/test_params.py tests/test_params_surface.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #727.
- Flack, H. D. & Schwarzenbach, D. (1988). *Acta Cryst.* A**44**, 499–506.
  Least-squares restraints for origin fixing in polar space groups. **Check
  the paper before quoting a weight scheme**; it is cited here from memory.
- Hahn, T., ed. (2005). *International Tables for Crystallography, Vol. A*,
  Part 15 (normalizers of space groups) for the continuous translations.
- `crystallography/wyckoff.py` (`coordinate_basis`, `_nullspace_int`); WP-0301,
  WP-0302, WP-1432, WP-1435; `schemas/params.py` (`needs_held_cell`).

## Handover log

### 2026-10-13 — the hold moves into the table, and the default is measured

The floating-origin hold is now something the parameter table does, behind a
switch on the phase. With it set, every fit, series pattern, joint histogram
and history replay holds the same atom. A tie or hold of the caller's that
already fixes the origin gets no second one. The switch is off by default, so
nothing moves for a caller who does not set it. Whether to turn it on is the
maintainer's decision on #727, and the numbers for that decision are below.

*Done.* Tasks 2-7, one commit each, on PR #929. Schema 0.52 adds
`Phase.floating_origin` and `ParameterRow.origin_axis`.
`ParameterTable._fix_origin` holds the first DOF that runs exactly along each
floating direction, through `Entry.held`, and re-decides at every build, tie
and hold. `_origin_floats` decides "already fixed" by an exact solve on the
affine block. `hold_floating_origin()` is now a wrapper that sets the field,
and `unhold` on a held DOF sets it back to `None`. `ORIGIN_FIXED_ON_POLAR_AXIS`
joins `fit` and `run_stage` results where a stage's glob met the hold, and
`HOLD_BLOCKED_PLAN` leaves that DOF out. `refine.py` was touched only in
`parameters`, `hold_floating_origin`, `unhold`, `_prepare_table`'s restore, the
two diagnostic call sites and `_hold_diagnostics`.

*Review.* My own pass found the free-set restore warning "no longer exists"
for a DOF the table held. `/code-review high --fix` found eight things and
fixed three: `unhold` asks the table again after removing a caller's hold, and
`set_tie`/`set_held` rebuild once. It left five, and so do I. A cross-phase tie
between two declaring phases makes the solve report "fixed" while the joint
shift is flat; no shipped fixture has one. One `unhold` matching both a user
hold and the origin hold records two nodes. A taken-back origin hold keeps
`vary=False`, as documented. A joint fit raises neither origin code
(`multi.DIAGNOSTIC_SCOPES`). `edit(floating_origin=None)` restores a DOF that
was free before, where `unhold` leaves it fixed.

*Measured* (`[dev]` venv, darwin arm64; the machine ran 5-6 other sessions'
suites at load 100-150 throughout). Fast selection on `f691115a`, this branch
with main merged after the review: 9 364 passed, 181 skipped, 1 xfailed and 1
failed, in 19 min 43 s. The failure was
`test_structure_extent.py::test_three_cells_a_side_build_in_no_more_than_a_moment`,
a wall-clock test, and it passed alone. The branch adds 24 test cases, all in
`test_floating_origin.py` (15 to 39). They cost 20.2 s in that run, 8.9 s of it
the module fixture's three zincite fits, which is the WP's acceptance fixture
and so stays in the fast tier. With the default off,
every golden is bit-identical:
`test_numpy_path_bit_identical_to_golden` on all ten states (`srm660c` and
`nac` included) and `test_the_compiled_path_holds_the_goldens_to_its_own_bar`
on its three. The full selection did not run, because the default moves no
number. With the default flipped to `"hold"` in a snapshot of `cc7ad7fc`, the
fast selection moves four tests: the `toy_anomalous` golden (zincite with
`phases.0.atoms.*.dof.*` free), two tests in `test_floating_origin.py` that pin
the default, and the generated `api.md`, which prints the default. Eleven
other failures and 16 errors there fail identically on an unflipped snapshot,
because a `git archive` tree is not a repository. No slow test frees a
coordinate on a polar phase. No shipped CIF is in a polar group. The shipped
polar fixtures are `compare.py`'s zincite and test-built phases.

Real data, the IUCr CPD round-robin `qarr/zincite.prn` with `compare.py`'s
zincite standard:

| protocol | off | `"hold"` |
|---|---|---|
| QPA (the acceptance protocol, frees no coordinate) | Rwp 0.109274 | bit-identical values |
| `mccusker_structural`, LM | Zn −0.00011(76), O 0.38271(76); `FLAT_DIRECTION`, `HIGH_CORRELATION`; 20 free | Zn 0, O 0.38283(152); neither code; 19 free |
| `mccusker_structural`, TRF | Zn 140.12849(76), O 140.51132(76) | as LM |
| QPA + a coordinate stage, LM | each z ±0.0092; the pair in `COVARIANCE_DIRECTION_DISCARDED` | O 0.38213(136); the pair out of it |

Rwp agrees to six figures in every pair. Coordinate rows in
`RefinementResult.parameters` go from 4 to 3 (Zn's DOF leaves, its z stays
with no esd), and rows with an esd from 4 to 2. On the WP's synthetic fixture
O comes to 0.38231(57) held, against ±0.00029 on each z unheld.

*Decision menu for #727.*

1. Keep the default off. Nothing moves. A polar fit that frees coordinates
   keeps `FLAT_DIRECTION` and esds half the honest size, and walks under TRF.
2. Default `"hold"` with a read-time pin. Documents written before 0.52 read
   as `None`, so old projects and histories replay unchanged. Moves the
   `toy_anomalous` golden (declare `None` in its state or re-capture it), the
   two default-pinning tests and `api.md`, plus the real-data rows above.
3. Default `"hold"` with no pin. As 2, and every older document reopens holding
   its first atom, so a replayed history node refits with one fewer free
   parameter.
4. A centroid mode (`"centroid"`), which @mustachefeeling asked for on #727 on
   2026-10-12 in place of the hold default. Not built. It needs the weights
   from Flack & Schwarzenbach (1988) and an affine tie over every atom along
   the axis, which widens one column's reach through `_column_extras`. It could
   become the default instead of `"hold"`.

*Not generalised.* No `diagnostics.md` row: it is 7 B under its budget, both
codes carry a `suggestion`, and `numbers.md` names them. A rigid body's origin
is a candidate after the atoms, untested on a fixture.

*Next.* The maintainer picks from the menu on #727. Option 2 is a small change:
the default, a `mode="before"` pin on `Phase` for documents older than 0.52, and
`toy_anomalous` declaring `None`. Option 4 is its own task on this WP.

*Handoff, 2026-10-13* (head `15d0b646`, main merged at `557df56b` before it). PR #929
was held at the merge gate by a `/code-review medium` pass with twelve findings.
Item 7 came first. Design: `ParameterTable.held_by(path)` returns `"caller"`,
`"origin"` or `None` from the table's own two sets (`_caller_held`,
`_origin_held`), and `Refinement.set_vary`, `_prepare_table`'s restore and
`unhold` now read it in place of `_user_holds` or `origin_holds`. The twelve,
verbatim, with status:

7. `refine.py:2374` the table's origin hold is a second writer of `Entry.held`, special-cased by hand at `_prepare_table`, `unhold` and `_hold_diagnostics` and missed at `set_vary`. Root CLAUDE.md's rule is that a hold is honoured in the table, never at call sites: give the table one answer, e.g. `ParameterTable.held_by(path) -> 'caller' | 'origin' | None` (or `set_vary` returning the declined held paths), and make every verb read it. **Fixed.** (`_hold_diagnostics` still takes `table.origin_holds`, which is the same set.)
1. `refine.py:2389` `set_vary` refuses a held literal only when the path is in `_user_holds`; on zincite with `floating_origin='hold'`, `set_vary('phases.0.atoms.0.dof.0')` returns `[]` silently, where a user hold raises; through the GUI the checkbox is a 200 that changes nothing. **Fixed**: refused with a message naming `Phase.floating_origin`; test `test_a_literal_set_vary_on_the_origin_hold_is_refused`. The GUI path is not re-tested.
2. `refine.py:6115` ORIGIN_NOT_FIXED is gated on a stage freeing a DOF of the phase by name, so the one unfixed case the docstring names (every candidate tied to a variable, plan frees `vars.*`) is never reported and the flat direction is walked in silence. Test the freed set against the columns that reach the phase's coordinate rows (`entry_reach`/`column_reach`), never DOF names (root CLAUDE.md, "a freeze resting on flatness needs the other reading of C"). **Fixed** in `_origin_diagnostics` (reach of each freed path through `entry_reach`). **Pending: a test** with both DOFs tied to a freed variable.
3. `params/vector.py:2547` when the origin fix moves off an entry, the take-back resets `held` but leaves `vary=False`: Zn declared free ends `vary=False, held=False, held_because ''`, `_free_paths == []`, nothing says so. Restore the entry's pre-hold `vary`, or report the take-back. **Fixed**: `_origin_wanted` keeps the vary the caller last asked for (at the hold, then from any glob reaching the row) and the take-back restores it; test `test_a_take_back_restores_the_vary_a_glob_asked_for`.
4. `refine.py:3102` `unhold` re-asks `origin_matches` after releasing the caller's own hold, so `unhold('phases.0.atoms.*.dof.*')` after `hold('…atoms.1.dof.0')` also sets `Phase.floating_origin` to None; a redundant hold()+unhold() on the origin DOF deletes the declaration (the test `test_unholding_a_callers_hold_on_the_origin_dof_leaves_it_free` pins the wrong behaviour). Lift only what the caller held; withdraw the declaration only when the released path was the table's own origin hold and nothing else. **Fixed**; the test is now `test_unholding_a_callers_hold_leaves_the_declaration_standing`.
5. `crystallography/magnetic/supercell.py:1427` the magnetic supercell builder builds the child Phase from named fields and never copies `floating_origin` (it copies `scale` and `magnetic_symmetry`); copy it, with a test on a polar parent. **Pending.** Also grep the other `Phase(...)` builders that copy a parent field by field.
6. `params/vector.py:1416` a candidate must have a basis row exactly ±f, so rhombohedral-axes polar settings (R 3:R, R 3 m:R, R 3 c:R, f = [1,1,1]) with general-position atoms get ORIGIN_NOT_FIXED although holding one coordinate DOF fixes the slide. Accept a DOF whose row has a nonzero component along f, or document the limitation in the suggestion; add the :R settings to the test matrix either way. **Fixed** by the first option: a site states the shift in its own basis as Bᵀa = f, and any DOF with aₖ ≠ 0 is a candidate (a general site on R 3 m:R holds its x). Part 2's `par-origin-hold` says so. The three `:R` settings are in the basis matrix and R 3 m:R in the table matrix.
8. `multi.py:272` a joint fit applies the hold but emits neither ORIGIN_FIXED_ON_POLAR_AXIS nor HOLD_BLOCKED_PLAN; add the diagnostic (root CLAUDE.md: a new correction ships with a diagnostic stating what it changed). **Pending.** Read how `multi.py` builds its `StageResult`s first; `DIAGNOSTIC_SCOPES` then moves the entry from ABSENT.
9. `refine.py:6097` ORIGIN_FIXED_ON_POLAR_AXIS fires in a Le Bail/Pawley fit whose glob matched the DOF although every coordinate was mode-fixed; gate on another DOF of the phase actually freed, as the NOT_FIXED arm does. **Fixed** with item 2's reach gate (the mode drops coordinates from `freed`). **Pending: a Le Bail test.**
10. `params/vector.py:282` `Entry.held`'s docstring says only `_apply_holds` writes it and "nothing the table derives from a structure could rebuild it"; now false. Rewrite it around item 7's answer. **Fixed.**
11. `refine.py:3106` a phase with `floating_origin` set but no holdable candidate cannot be released through `unhold` (no held path to name); give the verb a way to withdraw the declaration, or make `hold_floating_origin()` decline to set it when nothing can be held. **Fixed** by the second option: the verb probes the table (`Refinement._table_for`) and leaves a phase undeclared where nothing would be held; a declaration set by hand is withdrawn with `edit`. **Pending: a test.**
12. `refine.py:3082` `unhold` builds the working table up to four times; build one, read `origin_holds` off it, pass it to `_commit_hold_edit`. **Fixed** (one working table; `edit` still builds its own when a declaration is withdrawn).

Also pending: `docs/manual/using/concepts.md` still says "runs exactly along" for `ORIGIN_NOT_FIXED`; the 1.9.0 note and the skill paragraph need the same check. The fast selection has not run on `15d0b646`; the touched tests (252) and all fifteen golden tests passed there (`[dev]`, darwin arm64). The D1 default menu above is unchanged.

Next command: `.venv/bin/python -m pytest tests/test_floating_origin.py -n 4 --dist loadgroup`, then fix item 5 at `src/rietx/crystallography/magnetic/supercell.py:1427`.

- **2026-10-08** — a caller can now hold a polar group's floating origin in one
  call, and the fit then stops walking the structure along the polar axis. Nothing
  changes for a caller who does not ask. PR #749 (#727, head `f9f3c27e`) merged as
  `9465d2cf` after four rounds, behind an opt-in decided on the PR.
  *Done.* `wyckoff.floating_origin_basis(space_group)` returns the translations
  that commute with every rotation of the group (ITA Part 15).
  `Refinement.hold_floating_origin()` holds, per direction, the first atom whose
  free site DOF runs exactly along it, through `hold`, so `unhold` lifts it. It
  returns `ORIGIN_FIXED_ON_POLAR_AXIS` (info), or `ORIGIN_NOT_FIXED` where no DOF
  runs exactly along a direction. Part 2 has the equation, Part 1 a paragraph in
  `concepts.md`, and the skill a paragraph in `references/numbers.md`. On
  synthetic ZnO the held fit keeps Zn where it started and loses `FLAT_DIRECTION`.
  *Gate:* stacked with the run's other merges (#829, #825, #809, #754, #749, #815)
  on `main` `a3f9140a` as `166d362e`, macOS 26.6.2 arm64, `[dev,jax]`. The full
  suite, fast and slow together, gave 9231 passed, 116 skipped, 1 xfailed and 2
  failed. Both failures also fail on `main` alone on that machine: `toy_anomalous`
  (#760, which open PR #828 fixes) and a hypothesis counterexample in
  `test_indexing_reduce.py`. `main` after the merges is content-identical to that
  tree.
  *Not done here.* The tasks above assume the fix lives in `ParameterTable` by
  default. What landed is a `Refinement` verb nobody runs by accident, and the
  hold-or-centroid choice (Flack & Schwarzenbach 1988) is still open.
  *Next:* the maintainer decides #727's default; the remaining tasks follow from
  it.

- **2026-10-06** — Maintainer decision on #727, through draft PR #749,
  recorded on the decision task above. Holding one coordinate is the common
  powder practice, and the abstract of Flack & Schwarzenbach (1988)
  describes it as the common definition. SHELXL instead restrains the
  centroid automatically. GSAS-II computes each group's polar axes
  (`GSASIIspc.SGpolar`). GitHub's code search finds them used nowhere in
  refinement, and its solver drops a parameter when the normal matrix goes
  singular. What TOPAS and FullProf do was not confirmed.
  *Recovered 2026-10-10: committed after PR #796 merged, so it reached main
  only now.* The 2026-10-08 entry's "hold-or-centroid choice is still open"
  was written without this decision. The default is still open.

- **2026-10-05** — created, from the 2026-10-05 issue triage (issue #727).
  Checked against the tree at 32ef5a6: the issue's snippet lists both ZnO z
  DOFs as refinable, a free fit walked them to z = 634.13 / 634.51
  (`converged`, CIF `634.1318(11)`, `FLAT_DIRECTION` on the result) and
  `mccusker_structural` to ≈148, and a hand hold restored z(O) = 0.3807(22)
  at the same Rwp; `wyckoff.coordinate_basis` over the whole group's
  rotations gives the free-origin directions. No open WP owns it: 1460 only
  deduplicates the correlation rows, 1528 is a `Cell` docstring, 1514 and
  1803 are rigid bodies, and the WPs this extends (0301, 0302, 1311, 1432,
  1435, 1535) are closed. Next: task 1, the maintainer's choice of shape.
