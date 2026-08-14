# WP-0309 — Exporters: reflection table, CIF with esds, QPA table

Milestone: v0.3 · Status: ✅ 2026-07-24
Depends on: WP-0304

## Goal

Export a refinement's results in the forms other people and other codes
actually consume: a reflection table (hkl, d, 2θ, F², I), a CIF carrying
refined values *with* esds, and a QPA table.

## Context

Everything needed is already computed and thrown away. The compiled model in
[`model/forward.py`](../../src/rietx/model/forward.py) holds the frozen
reflection list, per-line positions and structure factors;
`RefinementResult.ticks` already carries **every emission line's** positions
(not just the primary — that was a real bug, caught by the misfit-injection
suite, because Layer 0 flagged each Kα2 peak as an impurity). A reflection
table exporter must be equally careful about which line each row belongs to:
one row per (emission line, reflection), or a primary-line table with the line
explicitly named. Do not silently emit only λ₁ rows.

CIF export already exists for structures
([`crystallography/cif.py`](../../src/rietx/crystallography/cif.py), gemmi).
What is missing is the *refinement* half: refined values with esds in the
standard `1.2345(6)` notation, R-factors, wavelength, and the profile/
background description. Use the pdCIF tags that match what
[`io/readers.py`](../../src/rietx/io/readers.py) already reads
(`read_pdcif` handles `_pd_proc`/`_pd_meas`), so the package round-trips
against itself — export then re-read is the cheapest correctness test.

esd formatting is a genuine trap: `1.2345(6)` truncation rules (esd digits,
rounding of the value to the esd's precision) are conventional and easy to get
subtly wrong. Write it once, unit test it against a table of tricky cases
(esd ≥ 1, esd spanning a decade boundary, value negative, esd `None` for a
fixed parameter).

The QPA table exports the `QuantitativePhaseAnalysis` object from WP-0304
(with the WP-0305 corrected/uncorrected pair when present) — it must carry the
"crystalline modelled content only" caveat into the exported artefact, not
just the API docstring.

## Non-goals

- A GSAS/TOPAS/FullProf *input-file* writer (not a v0.3 commitment).
- Plot exports — `viz/` already covers PNG/HTML.

## Tasks

- [x] Reflection table exporter (hkl, d, 2θ, |F|², I, multiplicity, phase,
      emission line) to CSV/TSV + a typed in-memory object
- [x] esd string formatter `value(esd)` with a unit test over edge cases
- [x] CIF refinement export: refined parameters with esds, R-factors,
      wavelength, profile + background description, using pdCIF tags
      compatible with `read_pdcif`
- [x] Export→re-read round-trip test (our own reader consumes our own CIF)
- [x] QPA table export carrying the modelled-crystalline-content caveat
- [x] Doc snippet in README showing the three exports

## Acceptance

Exported CIF re-reads through `read_pdcif`/`Structure.from_cif` without loss;
esd formatting matches the reference table exactly; the reflection table
accounts for every emission line.

```sh
.venv/bin/python -m pytest tests/test_exporters.py -q
```

## References

- Hall, Allen & Brown (1991) Acta Cryst. A47, 655 — CIF.
- IUCr pdCIF dictionary — powder diffraction tags.
- Toby (2006) J. Appl. Cryst. 39, 1 — R-factor definitions to export.

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
- **2026-07-24** — **complete.** All six tasks landed; `tests/test_exporters.py`
  (20 tests) green, ruff clean, full fast + slow suites unaffected.
  - **esd formatter**: `crystallography/cif.py::format_su(value, esd, *,
    decimals=6)` is the single canonical writer — `cif.py::_fmt(Parameter, …)`
    now delegates to it. Fixes the decade-boundary trap the old `_fmt` had
    (esd 0.0999 → `1.23(10)`, never the spurious three-figure `(100)`), and
    handles esd ≥ 1 / esd ≥ 10 (value loses decimals, su keeps magnitude:
    `12340(250)`). Reference table locked in `test_format_su_reference_table`.
  - **exporters** live in `io/exporters.py` (io → crystallography/model is the
    clean import direction; neither imports io). Public: `reflection_table`,
    `write_reflection_table`, `ReflectionRow`, `write_refinement_cif`,
    `refinement_cif_doc`, `qpa_table_csv`, `write_qpa_table`, plus `format_su` —
    all re-exported from the package root. `Refinement` gained
    `reflection_table()`, `write_reflection_table()`, `write_cif()`,
    `write_qpa_table()`.
  - **reflection table** reuses `model.phase_peaks(ip, values)` (positions +
    integrated intensity, both already per-emission-line) and calls
    `structure_factors_squared` via `model._site_values` for |F|²; one row per
    (line, reflection), Kα2 rows included (asserted). |F|² is `None` in Le
    Bail/Pawley (intensity is extracted/refined, not from the structure).
  - **refinement CIF** writes one block per phase (`write_structure_block`,
    extracted from `structure_to_cif` so the su/ADP conventions are shared) and
    appends refinement scalars + the obs/calc pattern loop to block 0. Pattern
    loop tags (`_pd_proc_2theta_corrected`, `_pd_proc_intensity_total`,
    `_pd_proc_intensity_total_su`, `_pd_calc_intensity_total`,
    `_pd_proc_intensity_bkg_calc`) are exactly what `read_pdcif` reads → the
    round-trip test re-reads both pattern (`read_pdcif`) and structure
    (`Structure.from_cif`) from the one file. Gotcha for multi-phase: the
    single-block round-trip is validated for single-phase only (the WP's
    acceptance case); multi-phase writes per-phase blocks + pattern on block 0
    but `Structure.from_cif` returns one phase, so a full multi-phase structure
    re-read is out of scope (was never a v0.3 commitment).
  - **QPA table** carries the crystalline-only scope + microabsorption status
    as leading `#` comment lines, not just the docstring.
