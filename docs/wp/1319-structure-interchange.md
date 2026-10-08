# WP-1319 — structure interchange: checkCIF conformance, and a bare XYZ importer

Milestone: unscheduled · Status: ⬜
Track: Coming from another code
Depends on: —
Priority: P2 2026-10-08 — was P3: #756 measured the writer raising gemmi's bare error on two phase names and writing a file gemmi cannot read

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

### Inherited

- **2026-10-08, from the issue triage (issue #752): a COD CIF with no
  type-symbol column reads, then fails at compile on a label like `O-h3`.**
  The reporter's file is COD 9001547 (spangolite, an AMCSD entry). It has
  `_atom_site_label` and no `_atom_site_type_symbol`, so `Structure.from_cif`
  takes the species from the label. A plain label (`Cu1`, `O2`, `H3`) is
  rewritten to its element with a `CIF_SPECIES_NORMALISED` note. A label that
  carries a separator or a suffix after the element (`O-h3`, `O-H7A`) is left
  as the species, and the refusal comes later, at the first evaluation
  (`ValueError: phase '9001547' atom 7 ('O-h3'): cannot read an element symbol
  from species 'O-h3'`), because the compile boundary has no diagnostics
  channel. The class is the labels `cif._SITE_LABEL` (`^[A-Za-z]{1,2}\d+$`)
  does not match: `O1A`, `Cu1A`, `O-h3`, `Ow1`, `Fe(1)`, `C1_2` all come back
  untouched from `normalize_cif_species`. The decision that belongs here: how
  far a label may be read when the file states no type symbol. A hydrate's
  `Ho1` (hydroxyl hydrogen) already reads as holmium under today's rule, so a
  wider rule needs the formula sum (`_chemical_formula_sum`) as a check on the
  elements it may produce. Whatever is chosen is a repair at read with a
  `Diagnostic`, per `io/CLAUDE.md`, and the unreadable remainder should
  refuse at read with the label named, not at predict.
  Checked against the tree at 5d1f5f67: reproduced. `Structure.from_cif` on
  the file returns 17 atoms with 8 `CIF_SPECIES_NORMALISED` notes and a
  `SITE_SNAPPED_TO_SPECIAL_POSITION` warning for Cl and Al; `Refinement(...)
  .predict` then raises as quoted. No count of COD files in this class was
  measured.

- **2026-10-08, from the issue triage (issue #756): the checkCIF task, proposed
  as a CIF module.** #756 replaces #195 item 3 with a design. A new package
  `rietx/io/cif/` would hold four things: a tag registry, one number rule,
  one block assembler and a validation hook. The registry is checked against
  vendored COMCIFS DDLm dictionaries (`cif_core.dic` 3.3.0, `cif_pd.dic` 2.5,
  `cif_mag.dic` 0.9.9; CC BY 4.0, into `tests/data/` with `ATTRIBUTION.md`
  rows). The writers `Structure.to_cif`, `write_refinement_cif` and the
  GSAS-II phase CIF move onto it. The GSAS-II one becomes a declared profile
  over the registry. checkCIF is the oracle for the core and pd blocks, run
  by hand on public or synthetic files only. `cif_mag.dic` is the oracle for
  the magnetic block, since checkCIF has no magnetic arm. The reporter's
  comment of 2026-10-06 cuts it into seven PRs off `main`: C-a registry, C-b
  number rule, C-c structure block, C-d pdCIF pattern block, C-e multi-block
  layout with `structure_from_cif(block=)` and su on read, C-f magCIF parent
  record, C-g validation hook with the VRF template and the GSAS-II profile.
  A checkCIF baseline on today's two refinement CIFs (FAP, NAC + CaF₂) goes
  before C-c.
  Checked against the tree at `5d1f5f67`:
  - The writer is as described. `write_structure_block` (`cif.py:1172`)
    writes the stored symbol under the deprecated
    `_symmetry_space_group_name_H-M` (`:1198`). It writes no `_alt`, Hall or
    IT number, no `_atom_type` loop, no `_cell_volume` and no
    `_audit_conform`. It writes B, not U. A symop loop appears only for an
    operator-list phase. Angles and occupancies carry four decimals, so
    90.00004 is written `90.0000`.
  - Measured with `Structure.to_cif` on `cod_1000055.cif`: two phases named
    `ph 1` and `ph-1` raise `RuntimeError: Block with such name already
    exists: ph_1`. A label `La 1` writes a file gemmi cannot parse.
  - `io/exporters.py` writes `_pd_proc_2theta_corrected` (`:514`) and
    `_pd_proc_intensity_total_su` (`:516`).
  - `scattering.written_species` is used by the GSAS, GSAS-II and FullProf
    writers and not by `crystallography/cif.py`.
  - `test_magcif.py:997` pins that the parent k is lost on a round trip.
    `cif.py:1240` says so in a comment.
  - The two citations: `pdcif.py:3-4` cites Toby (2003) 36, 1240, and
    `exporters.py:22` cites 36, 1285. Neither page was re-read here.
  - No dictionary file is in `tests/data/`. 1328's handover says the magCIF
    tag list is hand-copied from `cif_mag.dic`.
  Decisions the session needs, all the maintainer's (#756 § 7 lists twelve
  with defaults; these are the ones that change this file's scope):
  1. Whether this WP takes the whole module or only C-a to C-c, with C-d,
     C-e and C-g filed after. The XYZ half shares no seam with it, so
     whether the XYZ task leaves for its own WP is the same question.
  2. C-f overlaps two other owners. WP-1911 Part D's first task already
     offers "`to_cif` writes `_parent_space_group.name_H-M_alt`", and the
     parent record it writes is what #757's I-b reads. The 2026-09-02 entry
     below says magCIF is 1328's, and 1328 closed on 2026-10-03. So which WP
     owns C-f is open.
  3. Vendoring the dictionaries whole (about 2 MB) or a generated extract of
     names, aliases and deprecation flags with a regenerating script.
  4. The su rule. The default keeps `format_su`'s two significant figures and
     `SU_REFERENCE`. Values with no su become the shortest round-tripping
     `repr`.
  5. The deprecated `_symmetry_space_group_name_H-M`: written beside `_alt`
     for one release behind a flag, or dropped. The 2026-09-02 entry below
     already asks for `xhm()` in place of the stored string.
  6. Who runs checkCIF, and whether the first report is posted on #756
     before C-c starts.
  7. Registering the `rietx` CIF prefix for `_rietx_atom_site_moment.*`.
  Out of this WP: the ionic bond criterion and torsions (#759, the rigid-body
  track), msCIF (#678, v2+), and the superspace-group number the reporter's
  third comment asks never to be written unchecked.

- **2026-10-05, from the issue triage (issues #711, #712):
  `structure_from_cif` reads two things a CIF row states as if it had not
  stated them.** #711: a special position quoted to four decimals, each
  coordinate rounded on its own, can miss by 2e-4 (6e of `R -3 c :R`,
  x + y = 0.6870 + 0.8132 = 1.5002), outside `SITE_TOL` = 1e-4
  (`symmetry.py:677`, WP-1324's snap), so it expands as general at twice the
  multiplicity while the row's `_atom_site_symmetry_multiplicity` says
  otherwise; nothing in `src/` reads that column. #712: `if not u_iso:`
  (`cif.py:395`) and `site.occ if site.occ else 1.0` (`:413`) treat a stated
  zero as absent, gemmi giving 0.0 for both. *Checked at `32ef5a6`* with the
  issues' CIFs: O1 reads multiplicity 12 against the stated 6, with no
  diagnostic; `B_iso_or_equiv 0.000(75)` reads 0.5 Å² and occupancy 0 reads
  1.0; a B of 0.0 written by `Structure.to_cif` (`0.0000 Biso`) reads back
  0.5. **PR #717, from a fork, open**, fixes both: per-site statements read
  from the block (a null is not one), a stated multiplicity reached by a move
  ≤ 1e-3 **moves the stored coordinates** with
  `SITE_SNAPPED_TO_SPECIAL_POSITION`, else a new warning
  `CIF_SITE_MULTIPLICITY_DISAGREES`. Not covered: the writers, and a magCIF
  with a multiplicity column. The coordinate move is the maintainer's call.

- **2026-09-28, from the review of `solution case 1` (WP-1510 has the
  source): the XYZ slice has its consumer.** This file's Context says the
  XYZ importer waits if its only consumer is the fenced rigid-body
  machinery. Rigid bodies left the v2+ fence that day, and
  [1514](1514-scoping-rigid-bodies.md) scopes their milestone. The run
  needed an ideal aromatic ring as a template and built it by hand, and
  wrote its CIFs with hydrogens by hand too. Decide the fragment type with
  that milestone's design, not before it.
- **2026-09-16 (2nd), from [1118](1118-foreign-model-files.md): a CIF can
  state its setting in three places, and this build's own reader uses only one
  of them.** Measured while writing the GSAS-II phase CIF: gemmi's
  small-structure reader prefers `_space_group_name_H-M_alt` over
  `_symmetry_space_group_name_H-M` when both are present, ignores
  `_space_group_IT_coordinate_system_code` (the core dictionary says outright
  that item "cannot be used to define the coordinate system"), and ignores a
  `_space_group_symop_operation_xyz` loop entirely. So a CIF whose symbol is a
  bare `F d -3 m` and whose operations are origin choice 2 reads here as choice
  1, while GSAS-II reads the same file correctly, because it checks the
  operations. `crystallography.symmetry.setting_from_operators` already does
  that comparison for the `.gpx` reader and would close the gap in
  `structure_from_cif` with no new authority. 1118 left it alone as a change to
  the core reader rather than to a foreign-format one; it belongs with the
  writer obligation this WP already inherits. `write_structure_block` writes no
  operator loop at all today, which is the other half.
- **2026-09-16, from [1118](1118-foreign-model-files.md): `structure_from_cif`
  resolves a bare multi-setting symbol two different ways, depending on which
  of its two paths ran.** The primary path takes `gemmi.read_small_structure`'s
  own `spacegroup`, and the fallback for a file that resolver cannot read calls
  `find_spacegroup_by_name` on the raw H-M string. Measured 2026-09-16 on
  `F d -3 m`: the first gives `F d -3 m:2`, the second `F d -3 m:1` — the two
  settings whose 8a and 16d multiplicities swap, so the same file could import
  as AB₂O₄ or as A₂BO₄ according to a branch the caller cannot see. Only the
  resolvers were measured; no file was constructed that takes the fallback, so
  how reachable it is in practice is open. 1118 left this alone deliberately:
  its scope was the four foreign *project* formats, and the CIF route already
  pins a setting into the symbol it returns, so the choice is at least visible
  on the answer. A writer that round-trips through CIF is where it bites, which
  is this WP.
- **2026-09-02, from the magnetic scattering track
  ([1328](1328-magnetic-interchange.md)): magCIF is not this WP's.** The
  operator list with time-reversal signs, the site moments and the parent
  propagation vector go through `structure_from_cif` and
  `write_refinement_cif` in 1328, guarded by the COMCIFS `cif_mag.dic`
  rather than by checkCIF, which has no magCIF arm. The checkCIF conformance
  work here should leave the writer's tag check extensible to a second
  dictionary, and nothing more.

- **2026-09-02, from [1324](1324-symmetry-silences.md): a CIF the writer emits
  must name its space-group *setting*, not the symbol it was handed.** 40 H-M
  symbols are held in more than one setting (the `:1`/`:2` origin choices and
  the rhombohedral `:H`/`:R` axes), and the site multiplicities differ between
  them — spinel's origin-2 coordinates under a bare `F d -3 m` describe a
  different compound. `crystallography.symmetry.setting_alternatives` is the one
  authority for whether a symbol is bare, and a hand-built `Phase` may well
  carry one, because that is the exposure `SPACE_GROUP_SETTING_ASSUMED` exists
  to report. So `write_refinement_cif` should write `get_spacegroup(...).xhm()`
  rather than `phase.space_group`; checkCIF will not catch the difference, since
  a bare symbol is perfectly valid CIF and merely means something else. The
  **XYZ** half inherits the sharper form of it: a bare molecular file carries no
  symmetry at all, so whatever symbol the landing type takes is the caller's
  claim and arrives bare by construction — deciding whether to resolve it, or to
  keep `P 1` and say so, is part of "the landing type decided honestly first".

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

- **2026-10-07** — PR #765 (#764) merged from outside as `a65dca1a`. Gated
  together on a nine-PR stack replayed onto `main` at `f99fab05` (stack
  `16a95cef`, macOS arm64, `[dev,jax]`). The whole suite gave 8912 passed, 113
  skipped and 2 failed. Both failures fail identically on bare `main`: the
  `toy_anomalous` golden (#760) and
  `test_the_reduction_map_takes_a_to_f_where_the_reduction_does`. After the
  last merge, `main` at `a65dca1a` is content-identical to the gated tree.
  - `structure_from_cif` never counts one atom twice. Twin images of a site
    printed off a special position merge into one site
    (`CIF_SITE_TWINS_MERGED`). A site listed twice is dropped
    (`CIF_SITE_LISTED_TWICE`), and a copy differing in B, U^ij or disorder is
    refused. Diagnostics carry labels until the site list is final, then
    `_locate` rewrites only this call's rows, and a dropped label points at
    the site it repeats.
  - The rebase over #717 orders the two repairs. A stated multiplicity snaps
    first, under its own diagnostic. The twin merge takes the sites no
    statement covers. So #717's negative arm changed: a site 2e-4 off 6e with
    no multiplicity column now merges to multiplicity 6 and says so, where it
    stayed general (12) before. The review kept that reading, since twelve
    atoms 1e-3 Å apart is the double count #764 reports.
  - This WP's own tasks, checkCIF conformance and the XYZ importer, are
    untouched.

- **2026-10-06** — PR #717 (#711, #712) merged from outside as
  `0cbb1b70`. `Structure.from_cif` moves a site onto the special position
  its stated multiplicity names when the site lies within 1e-3 of it, and
  `SITE_SNAPPED_TO_SPECIAL_POSITION` names the move.
  `CIF_SITE_MULTIPLICITY_DISAGREES` reports a stated multiplicity the site
  cannot reach. A stated zero B or occupancy now reads as zero. Gated together on a seven-PR stack replayed onto `main` at `7c8a0316` (stack `ee39adb9`, macOS arm64, `[dev,jax]`). The fast suite gave 8523 passed, 103 skipped and 2 failed. Both failures fail identically on bare `main`: the `toy_anomalous` golden (#760) and a hypothesis case in `test_indexing_reduce.py`. The whole slow tier gave 291 passed and 12 skipped. After the last merge, `main` at `0cbb1b70` is content-identical to the gated tree.
  This WP's own tasks, checkCIF conformance and the XYZ importer, are
  untouched. Still open from the same fork: PR #765 (#764, never count one
  atom twice) is reviewed at round 2. It needs `_locate` limited to the
  call's own diagnostics, and a rebase over #717.

- **2026-09-01** — created, from issue #195's small slices (2026-09-01
  triage). Settled: checkCIF is hardening of an existing writer; first open
  decision is the XYZ landing type, and "waits" is an acceptable answer.
