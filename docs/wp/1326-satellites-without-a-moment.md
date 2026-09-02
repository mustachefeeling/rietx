# WP-1326 — satellites at G ± k, with no moment model: is it magnetic?

Milestone: unscheduled · Status: ⬜
Depends on: — (first rung of the magnetic scattering track; 1327 builds on
its reflection list)

## Goal

A phase can declare a commensurate propagation vector k, and the compiled
model then carries reflections at G ± k beside the nuclear list: Le Bail and
Pawley extract intensity on them, a Rietveld stage contributes zero nuclear
intensity there, and the unexplained-intensity report gains an arm that says
whether the residual peaks index as satellites of a small candidate set of k.
A user with unindexed low-angle intensity in a neutron pattern can test the
magnetic hypothesis without stating a single moment.

## Context

This is the first of four WPs that take magnetic scattering out of the v2
fence (ROADMAP § Unscheduled, the magnetic scattering track; the grounds are
recorded in DESIGN.md under *Scope discipline*). It is deliberately the rung
that needs no form factor, no magnetic symmetry and no neutron-only physics:
a satellite is a position, and positions are what the package already
freezes per stage.

**The asymmetry this rung closes.** `refine.py`'s unexplained-intensity
report names *a magnetic contribution* among the causes of intensity the
model puts nowhere (`refine.py` ≈ line 3067 and 3156, the same sentence the
manual repeats in `using/refining.md`). The package can therefore tell a
user their residual might be magnetic and offers no way to test it. The
readers refuse the same construct in three places (`io/projects/coverage.py`
`Stance.REFUSED` over `mag_space_group`, `mlx`, `mly`, `mlz`, …; the TOPAS
reader's raise at ≈ line 1915; WP-1314's refusal list). Those refusals stay
until WP-1328.

**What a propagation vector does to the reflection list.** For a commensurate
k, magnetic intensity sits at Q = H ± k for every reciprocal-lattice vector H
of the nuclear cell. Two rules from the FullProf manual (Rodríguez-Carvajal,
*FullProf Manual*, § Propagation vectors; in the maintainer's corpus) that a
naive generator gets wrong:

- k and −k are one vector when 2k is a reciprocal-lattice vector, and that
  test respects centring: on a C lattice (½, 0, 0) and (−½, 0, 0) are
  distinct, because (1, 0, 0) violates h + k = 2n; (0, 0, ½) is single
  because (0, 0, 1) is a lattice point.
- H runs over the reciprocal *lattice*. Centring conditions define which H
  exist and are kept; glide and screw absences are conditions on the nuclear
  structure factor, not on the lattice, and are not applied to a satellite.

The satellite multiplicity is the number of distinct Q in the union over the
Laue orbit of H and the star of k, found by enumeration and checked by orbit
counting, never by a formula (root CLAUDE.md's rule for a neighbour search
applies to a reflection orbit for the same reason). `generate_reflections`
merges ±h under the nuclear Laue group; satellites join that machinery as a
second `ReflectionSet` on the compiled phase, frozen at stage compile with
the nuclear one.

**What this rung cannot say, stated in the output.** With k = 0 the satellites
coincide with the nuclear lines, so a Le Bail extraction absorbs the magnetic
intensity into the nuclear intensities and the hypothesis is untestable by
this route. The report arm says so: "the excess sits on nuclear lines; a k = 0
structure and a nuclear misfit look alike here, and a pattern of the same
specimen above its ordering temperature separates them". WP-1329 makes that
comparison a series measurement. On an X-ray histogram a satellite is a
superstructure reflection, not magnetism, and the arm says that too.

**The candidate set is enumerated, not searched.** The arm scores the
zone-boundary vectors {0, ½}³ minus the origin (seven on a primitive
lattice, fewer distinct ones under centring) plus the third-order points
(⅓, ⅓, 0) and (⅓, ⅓, ½) on hexagonal and trigonal lattices, by how many
unexplained peaks fall inside the report's own 0.4·FWHM validity radius of a
satellite. It returns a ranked list and never a singleton (the indexing
rule); an incommensurate k is outside the set by construction and the arm's
sentence names that as the reason a good pattern can score nothing.

**Seams.** `crystallography/symmetry.py` (`generate_reflections`,
`reflection_orbits`, the transposed-rotation action on hkl), `model/forward.py`
(the per-phase reflection list frozen at compile; `lebail_update` and the
Pawley block take the satellites as more rows), `optimize/statistics.py`
(`count_unique_reflections` and `effective_observations` count satellites:
the observation count is reflections, and a satellite is one),
`schemas/structure.py` (`Phase.propagation_vector`), the report's
unexplained-intensity section, and `help.py` (a new parameter family fails
`tests/test_help.py` until it has an entry).

**Prior art, concepts only.** FullProf generates satellites from a list of up
to 24 k vectors and refines k in reciprocal-lattice units (an incommensurate
capability this WP fences). GSAS-II describes a commensurate structure in
its magnetic supercell instead, which is the shape WP-1327 adopts for the
moment model; the k-vector form here is the hypothesis tool and the two must
not both be declared on one phase.

## Non-goals

- Any moment, form factor, or magnetic symmetry: WP-1327.
- An incommensurate or refinable k. Rational components only; a k that is
  not a fraction with a small denominator is refused by name.
- More than one k on a phase.
- Multi-phase indexing of the residual (fenced by 1018–1027). The arm tests a
  fixed candidate set against a cell the user has; it does not index.

## Tasks

- [ ] `Phase.propagation_vector`: rational components over the conventional
      reciprocal basis, validated commensurate, with the ±k equivalence test
      and the centring rule above; refused together with a magnetic operator
      list once 1327 adds one.
- [ ] Satellite generation as a second `ReflectionSet` per phase: enumeration
      over the lattice, multiplicity by orbit counting, an equivalence test on
      a C-centred cell against the manual's two examples.
- [ ] The compiled model carries satellites through every mode: Le Bail and
      Pawley rows, zero nuclear contribution under Rietveld, ticks for every
      emission line, the observation count.
- [ ] The report arm: the enumerated candidate set, the ranked list, the k = 0
      sentence, the X-ray sentence.
- [ ] `help.py` entry, skill row, manual Part 1 (`using/refining.md`, the
      unexplained-intensity section) and Part 2 (the satellite condition as
      an equation with its *Source* line).
- [ ] Vendor the Cr₂WO₆ 4 K and 150 K HB-2A patterns from the GSAS-II
      tutorial repository (`Magnetic-II/data`, ORNL data distributed by
      Argonne; licence checked per file, a `tests/data/README.md` row each);
      they serve 1327's acceptance as well.
- [ ] Source a public constant-wavelength neutron pattern with a published
      k ≠ 0 structure (search the maintainer's corpus first, then ask; the
      GSAS-II `Magnetic-III` … `-V` folders are the first place to look).
- [ ] Tests, including the acceptance below, with obs/calc/diff PNGs to
      `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_satellites.py -q
.venv/bin/python -m ruff check src tests examples
```

- A synthetic pattern with peaks at G ± (0, 0, ½) on a known cell: the Le
  Bail extraction puts intensity on the satellites and the report arm ranks
  (0, 0, ½) first, by generated positions rather than by eye.
- The satellite count on a C-centred cell matches the manual's equivalence
  rule for both worked examples.
- The Cr₂WO₆ 4 K pattern against its 150 K nuclear model: the arm reports the
  excess on nuclear lines and names the k = 0 ambiguity; no candidate scores.
- Every number a shipped fixture pins is bit-identical with
  `propagation_vector=None`.

## References

- Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55 — FullProf; the
  manual's § Propagation vectors and eqs 3.47–3.54 are in the maintainer's
  corpus.
- GSAS-II tutorials, `Magnetic-II` (Cr₂WO₆, HB-2A at HFIR, 4 K and 150 K,
  λ = 2.4067 Å) — github.com/AdvancedPhotonSource/GSAS-II-tutorials.
- [1327](1327-magnetic-structure.md) the moment model; [1328](1328-magnetic-interchange.md)
  the readers; [1329](1329-moment-in-a-series.md) the series;
  [1134](1134-constant-wavelength-neutron.md) the CW-neutron instrument and
  the fence this track opens.

## Handover log

- **2026-09-02** — created, from the assessment of PR #221 (an outside
  proposal for a single magnetic WP, which conflicted with main and left the
  design open). Split off as the rung that needs no moment: a satellite is a
  position. No code touched. First task is the schema field and the
  equivalence test.
