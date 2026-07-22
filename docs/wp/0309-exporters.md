# WP-0309 — Exporters: reflection table, CIF with esds, QPA table

Milestone: v0.3 · Status: ⬜ not started
Depends on: WP-0304

## Goal

Export a refinement's results in the forms other people and other codes
actually consume: a reflection table (hkl, d, 2θ, F², I), a CIF carrying
refined values *with* esds, and a QPA table.

## Context

Everything needed is already computed and thrown away. The compiled model in
[`model/forward.py`](../../src/pxrdref/model/forward.py) holds the frozen
reflection list, per-line positions and structure factors;
`RefinementResult.ticks` already carries **every emission line's** positions
(not just the primary — that was a real bug, caught by the misfit-injection
suite, because Layer 0 flagged each Kα2 peak as an impurity). A reflection
table exporter must be equally careful about which line each row belongs to:
one row per (emission line, reflection), or a primary-line table with the line
explicitly named. Do not silently emit only λ₁ rows.

CIF export already exists for structures
([`crystallography/cif.py`](../../src/pxrdref/crystallography/cif.py), gemmi).
What is missing is the *refinement* half: refined values with esds in the
standard `1.2345(6)` notation, R-factors, wavelength, and the profile/
background description. Use the pdCIF tags that match what
[`io/readers.py`](../../src/pxrdref/io/readers.py) already reads
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

- [ ] Reflection table exporter (hkl, d, 2θ, |F|², I, multiplicity, phase,
      emission line) to CSV/TSV + a typed in-memory object
- [ ] esd string formatter `value(esd)` with a unit test over edge cases
- [ ] CIF refinement export: refined parameters with esds, R-factors,
      wavelength, profile + background description, using pdCIF tags
      compatible with `read_pdcif`
- [ ] Export→re-read round-trip test (our own reader consumes our own CIF)
- [ ] QPA table export carrying the modelled-crystalline-content caveat
- [ ] Doc snippet in README showing the three exports

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
