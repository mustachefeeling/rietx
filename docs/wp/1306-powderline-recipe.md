# WP-1306 — PowderLine recipe: the interchange format rietx did not have to invent

Milestone: v1.3 · Status: ⬜
Depends on: 1303 (soft: it is the replacement for the JSON surface, not a dependency)

## Goal

`rietx.io.recipe.read_recipe(dict | path) → Recipe` (structure, instrument, pattern,
plan, limits, diagnostics) and `write_recipe_tables(result, out_dir)` (their four tables
with their exact headers, engine-native `parameter_name`, their `descriptive_name` and
`category` vocabularies), so that a `src/powderline/rietx/` engine branch upstream is a
50-line call; their LaB₆ and DRX_33 recipes refined by rietx and compared to *both*
their GSAS-II and TOPAS tables.

## Context

- **What PowderLine is** (fetched 2026-08-27 from github.com/NSLS2/PowderLine,
  BSD-3-Clause, author Daniel Olds, NSLS-II PDF beamline 28-ID-1; pushed 2026-08-24). A
  file-less JSON recipe (`schema_name` ∈ {`GSASII_Rietveld`, `GSASII_SPF`},
  `schema_version` `0.26.0`, `payload`): `xrd_data` (inline `tth`/`Itth`/`Itth_weights`),
  `instrument` (a GSAS-II `.prm`-style `initialization` dict: `Lam`, `U V W X Y Z`,
  `SH/L`, `Zero`, `Polariz.`, `Type: PXC`; plus a `parameterization` of
  `[value, refine_flag, min, max]` 4-tuples), `fit_range`, `background` (Chebyshev +
  optional background peaks), `phases` keyed by name with `structure` (space group, cell,
  atoms with `Uiso`/`Uaniso`, occupancy) and `parameterization` (scale, cell, atoms,
  isotropic size/strain with `LG_eta`; uniaxial/ellipsoidal/Stephens declared). Pydantic
  models in `src/powderline/schema.py`, `extra='allow'` except the 4-tuple. Three engines
  behind one dispatcher (`src/powderline/engine.py`: `_ENGINES = ("gsasii", "topas",
  "easydiffraction")`); adding one is a documented contract (`docs/DEVELOPMENT.md` §
  Adding a Refinement Engine): a subpackage with `run_<engine>_recipe(recipe,
  output_dir, ...)` returning the locked result dict (`success`, `rwp`, `elapsed_time`,
  `method`, `fit_profile`, `unit_cell_data`, `peak_list_data`, `refined_parameters` with
  9 columns, `spf_*`, `output_files`, `error`, `traceback`); no schema changes; reject
  unsupported features loudly; import zero GSAS-II. Committed cross-engine fixtures: real
  synchrotron data (λ = 0.1665 Å) with GSAS-II *and* TOPAS reference outputs for LaB₆
  (SRM 660c, GSAS-II Rwp 6.53 %) and a two-phase battery cathode (DRX Fm-3m + Li₄MgWO₆
  C2/m, Rwp 10.83 %; variants: aniso ADP, atom refine, strain-only). Their tolerance
  policy (`docs/regression-tolerance.md`): cell `rtol 1e-4`, other parameters `1e-3`,
  size/strain `1e-2`, "compare lattice parameters, not Rwp, across engines".
- **Assessment.** The recipe is the JSON contract worth speaking; `refine_json`'s
  request schema had no second speaker. So: do not adapt `refine_json` to it; add the
  adapter here, which is what their engine branch would call, keeping their rule 3 (no
  schema changes) and putting the translation where rietx's conventions are tested. The
  fixtures are worth more than the interface: two real datasets with two reference
  engines' outputs under BSD-3 are a cross-code consistency check of the FAP.EXP kind,
  exercising exactly the conventions CLAUDE.md warns about (GSAS X/Y labels, centidegree
  units, `SH/L` against `axial_sl`/`axial_hl`, `LG_eta`, `Uaniso`). It is not an agent
  surface: it serves pipelines, and is not part of the milestone's agent acceptance.
- **Convention table** (each row measured against their LaB₆ GSAS-II output, never
  assumed; the FAP.EXP acceptance is the precedent for adopting a GSAS protocol): `Lam`
  → Å; `Type` `PXC` only, else refuse by name; `U,V,W` centideg² → deg²; `X,Y` centideg →
  deg (label conventions per `schemas/instrument.py` and CLAUDE.md's X/Y note); `Z` (a
  constant Lorentzian term rietx lacks): fixed 0 → dropped with `RECIPE_FIELD_DROPPED`
  (info), otherwise refuse; `SH/L` → `axial_sl`/`axial_hl` (measured split); `Zero` →
  `zero_shift` (unit measured); `Polariz.` → the source's polarization; `fit_range` →
  `two_theta_limits`; `Itth_weights` → σ = 1/√w; Chebyshev: count and `refine_flag`
  carried, coefficients re-seeded (different domain scaling; say so); `[value, refine,
  min, max]` → `Parameter(value, vary, min, max)` (their `min/max` are documented "not
  implemented in GSAS-II": honouring them is a recorded difference, not a bug); atoms
  `Uiso` → Biso = 8π²U, `Uaniso` → `Atom.aniso`, occupancy, `element` → species;
  `isotropic_size`/`isotropic_strain` + `LG_eta` → gauss/lor size/strain (the Scherrer
  form, measured); `stephens_parameters` → `Phase.microstrain`; `single_peaks`
  background, `GSASII_SPF`, uniaxial/ellipsoidal → refuse by name (their rule 4;
  `fit_peaks` is v1.4's). Plan: one stage freeing every flagged path (their semantics: N
  cycles of everything flagged); `refinement_cycles` ignored with a note. The recipe has
  no series form (they removed sequential in 0.25), no Le Bail/Pawley, no indexing.
- **Fixtures.** `tests/data/powderline/` holds the two `input.json` recipes and the four
  reference tables from each engine, with a `README.md` row per file (source URL, commit,
  BSD-3-Clause, author) before anything is committed; nothing enters the wheel
  (CLAUDE.md § Licensing: data carries its own fence, per file).
- **Risk.** Two stars on the repository; offset by the author being a beamline scientist
  in the maintainer's own field, and by the fixtures' value being independent of adoption.

- **This format is inline-payload by construction, and that is not this
  package's call to make.** WP-1303's rule — an integration surface across a
  process boundary takes paths, never inline payloads — is a rule for a surface
  *this package designs*. Here rietx is a consumer of someone else's format, and
  their rule 3 (no schema changes) governs: `payload.xrd_data` carries `tth`,
  `Itth` and `Itth_weights` inline, which is why an `input.json` is 0.4 MB, and
  `read_recipe` takes a **path** to that file so the payload never crosses a
  prompt. (WP-1304's skill note is folded out as not applicable: the recipe
  serves pipelines, not agents, so nothing here restates the protocol.)

## Non-goals

The upstream PR (a v1.3 follow-up row: "offer `src/powderline/rietx/` once 1306 is
green"); series, Le Bail, Pawley, indexing through the recipe; pandas as a dependency
(return lists; their branch converts).

## Tasks

- [x] Fixtures + `README.md` provenance rows.
- [x] `read_recipe`: instrument block with the convention table, each row's unit measured
      against the LaB₆ output; refusals by name.
- [x] `read_recipe`: phases, atoms, parameterization, plan.
- [x] `write_recipe_tables`: the four tables, headers byte for byte.
- [x] Acceptance (slow): DRX_33 and LaB₆ against both engines.
- [x] Docs: `using/recipe.md`, `io/CLAUDE.md` section for the format (and why it is not
      a *pattern* format), the fifteen `RECIPE_*` rows in the skill's diagnostics
      reference. No `help.py` entry is owed: `read_recipe` takes no format option, so
      `READER_OPTIONS` is unchanged.
- [x] Tests + obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_recipe.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_powderline.py -n auto --dist loadgroup   # slow
.venv/bin/python -m ruff check src tests examples
```

**The ±300 ppm bar was measured impossible and is replaced by an envelope**
(2026-08-29; the numbers are `tests/data/README.md` § v1.3 PowderLine recipe
fixtures). The two reference engines disagree by **2 665 ppm** on DRX_33's cubic
`a` and 386-1 770 ppm on Li₄MgWO₆'s four free cell parameters, so no answer can
sit within ±300 ppm of both. The cause is documented upstream: GSAS-II reports
two SVD singularities and a 100 % `Mustrain;mx`/`;i` correlation on this recipe,
and the two engines settle in different minima of that valley (GSAS-II returns a
**negative** crystallite size for phase 1; TOPAS returns 5×10⁸ µm, i.e. none).

Slow, revised: DRX_33, each free cell parameter inside the **envelope** the two
engines span, widened by the FAP cross-code allowance of ±300 ppm at each end —
so the check still fails on a translation error, which is what it is for, while
not asserting agreement neither reference achieves. The spread itself is
reported, never gated. Rwp beside their 10.83 % / 7.33 % and never gated.
LaB₆: the cell is held in their recipe, so the check is the *drawn* profile —
rietx's fitted FWHM per reflection against the width GSAS-II's own
`y_calc` shows — within their `1e-2` size/strain class bar, and Rwp beside
6.53 % / 8.52 %. The refined broadening **coefficients** are not comparable and
the record says why: GSAS-II's background peak ran to 8.77e10 °2θ at esd 0 while
TOPAS placed a real 12.3°-wide hump at 1.628°.

Fast: both recipes parse, every refusal names its field, a round trip of flags is
exact, the tables' headers match theirs byte for byte. Add a `compare.py`
standard row if a correction is added (none planned).

## References

- NSLS2/PowderLine (BSD-3-Clause), schema 0.26.0, `docs/DEVELOPMENT.md`,
  `docs/regression-tolerance.md`, fixtures `LaB6` and `DRX_33`.
- GSAS-II parameter conventions (Toby & Von Dreele 2013, *J. Appl. Cryst.* **46**,
  544-549); the FAP.EXP cross-code precedent (`tests/data/README.md`).

## Handover log

- **2026-08-28** — created, from the parked v1.3 plan.
