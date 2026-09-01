# WP-1324 — symmetry silences: an orbit that is not a multiplicity, and a setting nobody chose

Milestone: unscheduled · Status: ⬜
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
