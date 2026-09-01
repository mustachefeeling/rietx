# WP-1319 — structure interchange: checkCIF conformance, and a bare XYZ importer

Milestone: unscheduled · Status: ⬜
Depends on: —

## Goal

Two sharp slices of the interchange cluster land: the existing CIF writer's
output passes IUCr checkCIF (with a structure-only CIF decided alongside),
and a bare molecular XYZ file can be read — the lowest-common-denominator
export of every modelling tool — with its landing type decided honestly
first.

## Context

From issue #195, which corrected its own dictation in two places this WP
inherits.

**checkCIF is hardening, not a new exporter.** A CIF writer already ships:
`io/exporters.py`'s `write_refinement_cif` / `refinement_cif_doc` — refined
values with esds, R-factors, wavelength, profile/background description,
obs/calc pattern as a pdCIF loop, tags checked against the COMCIFS core
dictionary, cited to Hall (1991) and Toby (2003/2006). The ask is
conformance against the named external service (https://checkcif.iucr.org/)
— syntax, cell/geometry/symmetry consistency, ADPs, publication items —
plus a decision on a *structure-only* CIF (the current one is a refinement
CIF). Fetch the dictionaries the way the standing memory says (COMCIFS via
`gh api`; iucr.org 403s to plain fetches). checkCIF runs are manual and
recorded — the acceptance cannot script a third-party web service, so the
deliverable includes the checked report's findings and which were fixed
versus argued.

**The XYZ importer's first task is its landing type, decided before any
parsing.** Bare XYZ is element symbols plus Cartesian coordinates — no
cell, no bond order, no aromaticity. A crystal `Structure` needs a cell and
symmetry, so an XYZ file cannot become one alone; and the issue's own
maintainer clarification warns that a chemically sound rigid body needs
bond information geometry does not carry reliably (a benzene ring read from
coordinates alone is an inference problem, not an input). So the honest
options, decided first: a molecular-fragment type whose consumer is
placement into an existing model, or an XYZ-plus-declared-cell path — and
if the only real consumer turns out to be the fenced rigid-body machinery,
the slice waits and this file says so. Verified in-issue: no naming
collision with the `xy`/`.xye` *pattern* reader — molecular XYZ is a
different thing under a similar extension — and no XYZ structure reader
exists today.

**What this deliberately is not** (the rest of #195): VESTA native parsing
— VESTA speaks CIF, which rietx already reads, so native `.vesta` support
waits for evidence of need; Z-matrix generation and rigid bodies — on the
v2+ fence (named there 2026-09-01 with the rest of the feature-request
review); programmatic geometry generation (SMILES → RDKit/ASE/OpenBabel) —
recorded as a complementary future direction, undecided. Coordinate-only
formats are explicitly untrusted for aromatic/multiple-bond rigid bodies,
stated here so no later WP builds bond perception on geometry alone.

## Non-goals

- **Not model exporters to other Rietveld codes** —
  [1118](1118-foreign-model-files.md)'s writers task (issue #148).
- **Not VESTA in/out, not Z-matrices, not rigid bodies, not geometry
  generation** — fenced or deferred as above.
- **Not a bonded-format (MOL/SDF/SMILES) reader** — the correct source for
  rigid bodies, and therefore fenced with them.

## Tasks

- [ ] checkCIF pass: run the current writer's output through the service on
      two real refinements (one lab, one synchrotron), record every
      finding, fix the conformance class, argue the rest in the docstring.
- [ ] The structure-only CIF decision (and, if yes, the writer — a
      projection of the existing doc builder, not a second tag authority).
- [ ] The XYZ landing-type decision, written into this file with its
      grounds; then, if it stands, the parser (count line, comment line,
      element + Cartesian rows; refusals naming the file) and its
      `capabilities()`/`help.py`/manual/skill coverage.
- [ ] Fixtures with licence rows; `test_readers_robust.py` arm for the
      parser; tests for every checkCIF fix.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_exporters.py tests/test_readers_robust.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: the two recorded checkCIF reports show no syntax or consistency
errors in the classes this WP claims (residual findings each carry a
written reason); the XYZ path either reads its fixtures into the decided
type with refusals-by-name, or the file records why the slice waits.

The shipping PR comments on issue #195 saying its checkCIF and XYZ slices
landed — #195 stays open for the fenced VESTA/Z-matrix/rigid-body parts.

## References

- Issue #195 — the cluster, its corrections, and the maintainer's
  rigid-body clarification.
- Hall, S. R. (1991); Toby, B. H. (2003, 2006) — the writer's standing
  citations; the COMCIFS core and pd dictionaries.
- https://checkcif.iucr.org/ — the conformance target.

## Handover log

- **2026-09-01** — created, from issue #195's small slices (2026-09-01
  triage). Settled: checkCIF is hardening of an existing writer; first open
  decision is the XYZ landing type, and "waits" is an acceptable answer.
