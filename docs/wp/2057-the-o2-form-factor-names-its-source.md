# WP-2057 — the O²⁻ form factor names the fit it came from

Milestone: unscheduled · Status: ⬜
Track: Coming from another code
Depends on: —
Priority: P4 2026-10-26 — provenance wording: every oxide CIF rietx writes names a paper that does not print the O²⁻ row, and no computed number changes

## Goal

Every place rietx names the source of its X-ray form factors names the right
one for the `O2-` row, including the `_atom_type_scat_source` value written into
each CIF. A test pins the per-ion source string.

## Context

**The report (issue #1039).** rietx cites Waasmaier & Kirfel (1995), *Acta
Cryst.* A51, 416-431, for every row of `src/rietx/data/f0_WaasKirf.dat`. The
reporter read the paper: its Table 1(b) (ions, p. 420) has no O²⁻ row. The
authors' April 1995 README, reprinted at `f0_WaasKirf.dat:60-65`, says one
oxygen ion was fitted instead to Table 2 of Rez, Rez & Grant (1994), *Acta
Cryst.* A50, 481-497. The README names `O1-`. The reporter found the file's
`O1-` row (line 121) equal to the paper's O¹⁻ row to the printed digits, so the
exception the README describes is most likely the `O2-` row (line 125).

**Support from this tree, checked at c0e32ab29.** `scattering.py:48-50`
(WP-1527, from the maintainer's ITC copy) says ITC Vol. C Table 6.1.1.3 has
111 ions and the file lacks exactly one, Y³⁺. The file has 113 non-neutral
`#S` rows, two of them the valence labels `Cval` and `Siva`. So one ion row is
not an ITC 6.1.1.3 ion, consistent with O²⁻ having come from elsewhere. (This
assumes ITC's 111 excludes `Cval` and `Siva`.)

**What the triage could not read.** Neither paper is in the maintainer's
Zotero library as searched on 2026-10-26 (file names and the sqlite). Before
writing the citation, read W&K 1995 Table 1(b) and RRG 1994 Table 2. A free
O²⁻ ion is unbound, so RRG's O²⁻ needs a stabilising model; the citation
should say which, if the paper says. If neither can be obtained, cite only
what the file itself states: "Waasmaier & Kirfel's fit distributed in DABAX
`f0_WaasKirf.dat`, to Rez, Rez & Grant (1994) Table 2 per its README; not in
the 1995 paper". Ask the maintainer for the papers before working around them.

**The places that cite W&K for every row** (checked at c0e32ab29):
- `src/rietx/crystallography/scattering.py:3`, module docstring;
- `src/rietx/io/cif/blocks.py:87-94`, `_XRAY_SOURCE`, and `_scat_source`
  (`:261-274`), whose one per-ion exception today is `_ITC_IONS` (Y³⁺);
- `ATTRIBUTION.md:124` (references) and `:439-441` (the data file entry);
- `docs/docs/theory/intensities.md:24-25`, which cites `waasmaier1995` for f0.
  Line 39 already names the Y³⁺ exception, so O²⁻ goes beside it.

**Constraints.** `SCAT_SOURCE_MAX = 40` (`blocks.py:98`) holds because
checkCIF's PLATON stops reading a block at a long value (113 characters left
every row empty on 2026-10-09; `tests/test_cif_structure_block.py:281`). The
reporter's "W&K fit to Rez et al. (1994)" is 29 characters. A Theory-tab
citation needs its bib entry (`docs/docs/references.bib`), and every bib entry
must be cited (`tests/test_manual.py`).

**What does not change.** The coefficients. f0 at s = 0 is 7.9997 (O),
8.9980 (O¹⁻) and 9.9984 (O²⁻) electrons, fit residuals of 0.3 to 2
thousandths of an electron. No intensity, fit or golden moves.

**Tier.** None: a citation, not a rule. No `_audit` row.

### Inherited

## Non-goals

- Replacing the O²⁻ curve with another model (Tokonami 1965, a Watson-sphere
  calculation). That changes numbers and needs its own evidence.
- Auditing every other row against the paper's printed digits. If the
  papers arrive, a spot check of the remaining ion rows is cheap and goes in
  the handover, but a full transcription check is out of scope.

## Tasks

- [ ] Read W&K 1995 Table 1(b) and RRG 1994 Table 2 (ask the maintainer for them); record what each prints for O¹⁻ and O²⁻.
- [ ] `_scat_source` gives `O2-` its own source string, beside the `_ITC_IONS` rule, ≤ `SCAT_SOURCE_MAX`.
- [ ] Name the O²⁻ source in `scattering.py`'s docstring, `ATTRIBUTION.md` (both entries) and `theory/intensities.md` (with its bib entry).
- [ ] Tests: `_scat_source("O2-", "xray")` pins the new string; `O1-` and `O` keep W&K (1995); a written oxide CIF carries it.
- [ ] Skill: none. The skill does not quote scattering-factor sources, and the CIF field is written without the agent's involvement.

## Acceptance

`_scat_source("O2-", "xray")` returns the new string, and no file in the tree
cites Waasmaier & Kirfel (1995) alone for the O²⁻ row.

```sh
.venv/bin/python -m pytest tests/test_cif_structure_block.py tests/test_manual.py -q
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python -m ruff check src tests examples
```

## References

- Waasmaier, D. & Kirfel, A. (1995). *Acta Cryst.* A51, 416-431.
- Rez, D., Rez, P. & Grant, I. (1994). *Acta Cryst.* A50, 481-497.
- *International Tables for Crystallography* Vol. C (2004), Tables 6.1.1.3 and 6.1.1.4.
- Issue #1039 (mustachefeeling, 2026-10-18).

## Handover log

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1039). Checked against the tree at c0e32ab29: `_scat_source("O2-", "xray")` returns `'Waasmaier & Kirfel (1995)'`; the README at `f0_WaasKirf.dat:60-65` names Rez, Rez & Grant (1994) for one oxygen ion; the file's 113 non-neutral rows against ITC 6.1.1.3's 111 ions less Y³⁺ leave one row ITC does not list. Neither paper could be read here. No open WP owns it: WP-1527 (Y³⁺, `_ITC_IONS`) and WP-1319 (CIF writer) are ✅, and WP-1933 (🔄) covers the pattern block and multi-block layout, not the scattering-source field. Next: obtain the two papers.
