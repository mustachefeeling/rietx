# WP-1324 — symmetry silences: an orbit that is not a multiplicity, and a setting nobody chose

Milestone: unscheduled · Status: ✅ 2026-09-02
Depends on: —

## Goal

Two silent wrong answers in `crystallography/symmetry.py` are closed. An
orbit's length is a multiplicity — |G| divided by the stabiliser order, which
divides |G| — or the expansion raises, never a count that depends on the order
gemmi yields operations in. And a Hermann-Mauguin symbol that arrives without
a setting suffix where the tables hold more than one setting is resolved *and
reported*, at every construction site that resolves a symbol without a file to
take the setting from — the hand-built `Phase` above all.

## Context

Two issues filed 2026-09-01, one module, one consequence: a wrong site
multiplicity is frozen onto the compiled model and reaches ZMV and every
`weight_percent`, while the fit converges.

**Issue #215 — the orbit.** `expand_orbit` deduplicates images with a greedy,
first-fit comparison at `tol = 1e-4` per fractional axis. Greedy is not
transitive (a≈b and b≈c do not give a≈c), so the partition depends on operation
order, and nothing checks the invariant. An 18h-type site of `R -3 m:H`
(|G| = 36) obeys y = 2x; perturbing that relation by ±1.0e-4 returns orbits of
**22 and 30**, neither a divisor of 36, where 18 and 36 are the only possible
answers. It bites a published CIF: ICSD 18318 (β-rhombohedral boron, 16 B
sites, coordinates to five decimals) puts several y = 2x relations off by
exactly 1e-4, and site B11 lands at `+1.0000000000000286e-04` — over `tol` by
ULPs — and expands to **30** against the CIF's own
`_atom_site_symmetry_multiplicity` of 18.

**Issue #217 — the setting.** For the 40 H-M symbols with two settings, gemmi
resolves the bare symbol to the first (`F d -3 m` → `:1`). Spinel at origin
choice 2's coordinates under `:1` **swaps** the 8a and 16d multiplicities
(A at (⅛,⅛,⅛): 16 under `:1`, 8 under `:2`; B at (½,½,½): 8 against 16), so a
phase built by hand with the symbol a paper prints and the coordinates it
lists gives A₂BO₄ where AB₂O₄ was meant — wrong `element_counts`, wrong ZMV,
wrong fractions, nothing reported. Two routes already do this right and are
the pattern to follow: `crystallography/cif.py` prefers gemmi's own reading of
the file and raises on the fallback; the TOPAS reader maps the trailing `Z` to
`:2` (WP-1118). The exposure is the object API.

**Rules that bind.** Every symmetry refusal is raised in
`ParameterTable.__init__` and a silent correction is a *reader's* to make,
never a table's — so a snapped coordinate is reported through a reader's
diagnostics channel (`CIF_SPECIES_NORMALISED` is the precedent) and a
hand-built phase gets its own channel or a refusal. Cell ties follow the
space-group *setting* (WP-1036; `read_small_structure` already picks the R
setting from the cell), which is the precedent for choosing a setting from
evidence and saying so. Multiplicities feed `phase_zmv`
(`optimize/qpa.py`), whose `element_counts` are occupancy-weighted per site.

**Prior art, concepts only.** cctbx derives a site's symmetry from the
stabiliser and snaps the coordinate to the exact special position within a
tolerance, so the multiplicity is a group-theoretic fact rather than a count;
GSAS-II does the same at atom entry and shows the site symmetry beside the
multiplicity.

## Non-goals

- Choosing the setting for the user. The bare symbol keeps gemmi's resolution;
  what changes is that the choice is visible and the alternatives named.
- Re-deriving Wyckoff constraints (`wyckoff.py` owns those and already reads
  the stabiliser).

## Tasks

- [x] `expand_orbit` by stabiliser: orbit = |G| / |stabiliser|, images generated
      once per coset, the coordinate snapped to the special position it is
      within `tol` of; raise `ORBIT_NOT_A_MULTIPLICITY` if a count ever fails
      to divide |G| (a guard that should become unreachable, kept as the
      invariant).
- [x] The snap is reported: `SITE_SNAPPED_TO_SPECIAL_POSITION` with the site,
      the shift, and the multiplicity, on `structure_from_cif`'s channel and
      on the `Phase`/`Structure` construction path.
- [x] `SPACE_GROUP_SETTING_ASSUMED` on every bare-symbol resolution where the
      tables hold more than one setting, naming the setting taken and the
      others; `Phase.space_group` validation is the one place for it, so the
      CIF and TOPAS routes (which carry a setting) stay silent.
- [x] The issue's two reproductions as tests: the ±1.2e-4 sweep on `R -3 m:H`
      prints only 18 or 36; ICSD 18318's sixteen sites match the CIF's
      multiplicities; the spinel table under `:1` and `:2`.
- [x] Skill and manual rows for the two codes; a Part 2 note that a
      multiplicity is |G|/|stabiliser|.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_wyckoff.py tests/test_symmetry_orbits.py
.venv/bin/python -m ruff check src tests examples
```

No fitted number may move for a structure whose orbits were already right;
the validation matrix's real-data suites are the check.

## References

- Issues #215 and #217 — the reproductions and the measured tables.
- International Tables Vol. A — site multiplicity as |G|/|stabiliser|.
- WP-1036 (settings decide the ties), WP-0301 (the Wyckoff derivation),
  WP-1028 (reader-side repairs are reported).

## Handover log

- **2026-09-01** — created from issues #215 and #217 during the roadmap
  reorder; no code touched.

- **2026-09-02** — **done.** All five tasks; four commits. No `### Inherited`
  section existed, so nothing to prune.

  **The orbit (#215).** `symmetry.site_orbit` is the one authority:
  candidates fixing the site within `tol`, their Reynolds average as the snap,
  then the *snapped* point's own stabiliser and one operation per left coset.
  Recomputing the stabiliser after the snap is what makes
  `ORBIT_NOT_A_MULTIPLICITY` unreachable rather than merely rare — step 1's
  set need not be a subgroup, and a first cut that trusted it raised on **157
  of 16 920** fuzzed sites, all jittered cubic ¼¼¼ and ⅛⅛⅛ positions where a
  tolerance admits some members of the site symmetry and misses others. Steps
  3 and 4 measure one point's own stabiliser and one point's own orbit, so
  orbit-stabiliser settles it: 0 non-divisors and 0 raises over all 564 gemmi
  settings × 30 positions. The guard is kept as the invariant and provoked in
  the test by monkeypatching the coincidence tolerance.

  The tolerance comparison is now **inclusive to a relative 1e-9**, which is
  what makes the boron case come out at 18 rather than 36. A five-decimal file
  lands on the boundary exactly (`1.0000000000000286e-04` against
  `9.999999999998899e-05` for the same nominal 1e-4), so a strict `<` let
  binary rounding decide which side of a crystallographic threshold a
  coordinate fell on.

  Three implementations became one reader: `select_orbit_ops` (the subset
  frozen onto the compiled model, and what `phase_zmv` counts atoms with),
  `stabilizer_rotations` (the constraint bases) and `site_constraints` (one
  expansion, not two). That was the second half of the bug — taken separately,
  the allowed directions and the orbit length answer different questions
  whenever the tolerance admits a non-subgroup, and only the second was
  reported.

  **Acceptance clause, measured directly.** "No fitted number may move for a
  structure whose orbits were already right" was checked against the old
  greedy implementation rather than inferred from a green suite: **28 of 28**
  site op-subsets bit-identical over the standards the acceptance suites fit
  (LaB6, spinel both settings, FAP, corundum, brucite, cBN/Si, NaCl/CaF2,
  rutile) and both bundled CIFs. The forward model reads exactly that subset,
  so bit-identity of it is the whole claim.

  **The setting (#217).** `setting_alternatives` reads the ambiguous set off
  gemmi — **40** H-M symbols, the `:1`/`:2` origin choices plus the
  rhombohedral `:H`/`:R` axes, so it cannot drift. Two departures from the WP
  as written, both deliberate:

  1. **Not in `Phase.space_group` validation.** A pydantic validator has no
     diagnostics channel, which is the same reason `ParameterTable` refuses a
     bad cell angle instead of correcting it, so the report is built at fit
     time in `refine._symmetry_silence_diagnostics` and lands on
     `result.diagnostics`. The *silence* the WP asked for falls out anyway: a
     symbol carrying its setting returns `("", ())`, so the CIF and TOPAS
     routes never fire it. Issue #217's tail ask — assert the symbol resolved
     and name the string that failed — is already `get_spacegroup`'s
     behaviour, and this gemmi resolves `P42/mnm` fine, so nothing was owed.
  2. **The message quotes the composition each setting implies**, not the
     symbols. That was the issue's "stronger version" and it is the part a
     caller can recognise: spinel's origin-2 coordinates print
     `F d -3 m:1 → Al8 Mg16 O32` against `F d -3 m:2 → Al16 Mg8 O32`, and one
     of those is obviously not the compound. "Ambiguous symbol" is a warning
     nobody reads.

  **The boron file is not in the tree.** The WP asked for ICSD 18318's sixteen
  sites as a test; ICSD is licensed data and the root CLAUDE.md fences it, so
  the reproduction is pinned to the *arithmetic* that bit — a five-decimal
  x/y pair whose `y − 2x` lands at `1.0000000000000286e-04`, asserted to be
  that float and to be over a strict `1e-4`. The mechanism is the coordinates,
  not the file, and `test_b11_shape_is_the_float_that_bit` says so.

  **The snap is reported, not applied.** `SITE_SNAPPED_TO_SPECIAL_POSITION`
  names the site, the shift and the multiplicity; the stored coordinate is
  left alone. Rewriting it would change a refinement's start values, and the
  deviation may be real — the coordinate DOF anchor keeps it either way
  (`x = x₀ + Σ Bₖθₖ`), so the site refines from where the file put it while
  counting the atoms symmetry says are there. `shift` reports 0.0 below 1e-12,
  because a site already on its position averages to itself only to within an
  ulp (h·x/h is not exactly x unless h is a power of two) and reporting that
  is reporting arithmetic.

  **One thing not done, and it is a judgement call for the maintainer.**
  `SKILL.md` got a pointer (`no unresolved scale- or ZMV-family diagnostic`,
  +8 B) rather than the two rows: the body is **31 968 B against its 32 000
  cap**, and `tests/test_skill.py`'s docstring says the fix for a full body is
  to move a lookup into a reference file, never to raise the cap for one. The
  rows are in `references/diagnostics.md`, which is where the root CLAUDE.md
  rule points. If the QPA row should name both codes outright, something else
  in the body has to go — that is a call about every future session's fixed
  cost, not one to make in passing.

  **Numbers**, `[dev]` venv (no jax/torch), darwin/arm64, this worktree:
  acceptance `tests/test_wyckoff.py tests/test_symmetry_orbits.py` **104
  passed**; ruff clean over `src tests examples`; sphinx `-W` clean; fast
  selection green before the docs commit at **3920 passed, 122 skipped**
  (+31 from the new file after it, re-measured on the final tree below).

  **Next.** Nothing blocks on this. The two issues can close on the PR.
