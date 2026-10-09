# WP-1319 — the CIF writer on one registry: tags, numbers and the structure block, checked by checkCIF

Milestone: unscheduled · Status: 🔄 2026-10-09 — claimed by @yue-here
Track: Coming from another code
Depends on: —
Priority: P2 2026-10-08 — was P3: #756 measured the writer raising gemmi's bare error on two phase names and writing a file gemmi cannot read

## Goal

A new package `rietx/io/cif/` holds a tag registry checked against the vendored
COMCIFS dictionaries, one number rule, and the structure block. `Structure.to_cif`
and the structure part of `write_refinement_cif` write through it. checkCIF's
computed-against-reported alerts that fire on today's output are gone from the
structure-only files, with a recorded report before and after.

## Context

This WP is chunks C-a, C-b and C-c of issue #756, the reporter's design for one CIF
writer module. The design is the issue body (§ 1 boundary, § 2.1 the structure-only
kind, § 2.5 checkCIF as the oracle, § 3 names and `_audit_conform`, § 7 decisions)
and the reporter's comment of 2026-10-06, which cuts § 4's C-W1 into C-a, C-b and
C-c. Read those sections before starting a chunk. They carry `file:line` facts
checked at `50777a95`/`65a78ab7`.

**Decisions, taken 2026-10-09 by the maintainer** (#756 § 7 numbering):

- **Scope.** This WP takes the checkCIF baseline and C-a, C-b, C-c. C-d (pdCIF
  pattern block), C-e (multi-block layout, `structure_from_cif(block=)`, su on read)
  and C-g (validation hook, VRF template, GSAS-II profile) went to
  [1933](1933-the-cif-module-beyond-the-structure-block.md). C-f (magCIF parent
  record) went to [1911](1911-the-foreign-writers-state-what-the-other-program-reads.md),
  whose Part D already writes `_parent_space_group.name_H-M_alt`.
- **The XYZ importer left this WP.** Its landing type is the `Fragment` of
  [1802](1802-the-fragment-type.md), and [1813](1813-fragment-io.md) (fragment I/O,
  rigid-bodies milestone) already lists the XYZ read. Bonds are declared and never
  perceived from geometry. That rule moved with it.
- **Decision 9, dictionaries vendored whole** into `tests/data/`, never the wheel:
  `cif_core.dic` v3.3.0 (930 KB, released 2026-10-01), `cif_pd.dic` 2.5.0 (522 KB),
  `cif_mag.dic` 0.9.9 (199 KB), plus `ddl.dic`, `templ_attr.cif`, `templ_enum.cif`.
  CC BY 4.0, each with an `ATTRIBUTION.md` row and a `tests/data/README.md` row
  naming the COMCIFS tag or commit. Fetch through `gh api` (iucr.org refuses plain
  fetches). The existing magCIF row says "nothing vendored"; amend it.
- **Decisions 11 and § 2.5, checkCIF.** The session drives checkCIF's web form in a
  headed browser, "CIF only" mode, public or synthetic files only, at most 30
  submissions a day, stopping at any CAPTCHA or terms page. Each report is recorded
  as a dated alert list in this file's handover. The baseline report is drafted as
  a comment on #756 for the maintainer's approval before C-c starts.
- **Decision 3, the deprecated `_symmetry_space_group_name_H-M`: dropped, no flag.**
  Measured 2026-10-09 in `cif_core.dic` v3.3.0 (line 12724) and 3.4.0-dev: the tag
  is an alias of `_space_group.name_H-M_full`, deprecated 2003-10-04. The writer
  puts the short symbol there, so the tag is mislabelled as well as deprecated. The
  structure block writes `_space_group_name_H-M_alt` from `xhm()`, the Hall symbol,
  the IT number, the crystal system and the full `_space_group_symop` loop with ids.
  The dictionary's `name_H-M_alt` text says an H-M symbol cannot fix the origin and
  only the Hall symbol or the operations can. The drop is confirmed by the baseline
  report showing SYMMG01 and the prefilter reading `_alt`. If checkCIF needs the old
  tag, the question returns to the maintainer with the report. gemmi prefers `_alt`
  when both are present, and GSAS-II reads `_alt` second (ATTRIBUTION.md's GSAS-II
  row), so this build's readers and GSAS-II's still read the file.
- **The other § 7 defaults stand**: 1 (`rietx/io/cif/`, readers stay in
  `crystallography/`), 2 (CIF 1.1 with flat names, dotted only where no alias
  exists), 4 (`format_su`'s two significant figures, `SU_REFERENCE` unchanged;
  values with no su as the shortest round-tripping `repr`), 5 (U not B), 6 (no σ(V)
  in a structure-only CIF). Decision 10 (registering the `rietx` prefix) is the
  maintainer's act, outside this WP. The private moment tags stay.

**The writer as it stands**, checked at `5d1f5f67` and unchanged at `29377b8f`
(no commit since touches `crystallography/cif.py`, `io/exporters.py`,
`io/formats/pdcif.py` or `crystallography/symmetry.py`):

- `write_structure_block` (`cif.py:1172`) writes the stored symbol under the
  deprecated tag (`:1198`). It writes no `_alt`, Hall or IT number, no `_atom_type`
  loop, no `_cell_volume`, no `_audit_conform`, and B rather than U. A symop loop
  appears only for an operator-list phase. Angles and occupancies carry four
  decimals, so 90.00004 is written `90.0000`.
- `Structure.to_cif` on two phases named `ph 1` and `ph-1` raises
  `RuntimeError: Block with such name already exists: ph_1`. A label `La 1` writes
  a file gemmi cannot parse.
- `io/exporters.py` writes `_pd_proc_2theta_corrected` (`:514`) and the undefined
  `_pd_proc_intensity_total_su` (`:516`). Both are C-d's (1933). C-a carries the
  second on its allow-list.
- `scattering.written_species` serves the GSAS, GSAS-II and FullProf writers and
  not `crystallography/cif.py`.
- No dictionary file is in `tests/data/`. `magcif.py`'s tag lists were hand-copied
  from `cif_mag.dic` (1328).

**The setting a written file names** (from [1324](1324-symmetry-silences.md) and
[1118](1118-foreign-model-files.md), 2026-09-02 and 2026-09-16). 40 H-M symbols
are held in more than one setting (`:1`/`:2` origin choices, `:H`/`:R` axes), and
site multiplicities differ between them. A bare `F d -3 m` over spinel's origin-2
coordinates describes a different compound. A hand-built `Phase` may carry a bare
symbol, which is what `SPACE_GROUP_SETTING_ASSUMED` reports, and
`crystallography.symmetry.setting_alternatives` says whether a symbol is bare. So
C-c writes the resolved setting (`get_spacegroup(...).xhm()`, Hall symbol, the
operator loop) and never the stored string. checkCIF cannot catch this: a bare
symbol is valid CIF that means something else. The reader half (gemmi ignores the
operator loop; two resolver paths give `F d -3 m:2` and `:1`) is 1933's.

### Inherited

## Non-goals

- **Not C-d, C-e or C-g**: [1933](1933-the-cif-module-beyond-the-structure-block.md).
  **Not C-f**: [1911](1911-the-foreign-writers-state-what-the-other-program-reads.md).
- **Not the XYZ importer**: [1813](1813-fragment-io.md).
- **Not model exporters to other Rietveld codes**:
  [1118](1118-foreign-model-files.md), [1911](1911-the-foreign-writers-state-what-the-other-program-reads.md).
- **Not CIF 2.0 or dotted names** beyond magCIF (#756 § 3), msCIF (#678), torsions
  or the ionic bond criterion (#759), VESTA, Z-matrices or geometry generation
  (#195's fenced parts).

## Tasks

- [x] Vendor the six COMCIFS files into `tests/data/cif_dictionaries/` with
      `ATTRIBUTION.md` and `tests/data/README.md` rows; amend the magCIF row.
- [ ] **C-a, the tag registry** (`io/cif/registry.py`): flat name, DDLm
      `_definition.id`, category and key, purpose, units, deprecation, output
      kinds. A meta-test: written ⊆ registry ⊆ dictionary, nothing deprecated.
      Today's two violations (`_pd_proc_intensity_total_su`,
      `_symmetry_space_group_name_H-M`) sit on an allow-list a test holds to
      shrinking. A planted undefined tag fails. No written byte changes.
- [ ] **C-b, one number rule** (`io/cif/numbers.py`): esd values through
      `format_su`; values without one as the shortest round-tripping `repr`;
      moments keep `repr` + `_su`; non-finite values and whitespace refused by tag.
      The five formatters routed through it. A 90.00004 angle and a 0.33333
      occupancy round-trip bit-identically (both fail on `main`). `SU_REFERENCE`
      and every CIF test stay green.
- [ ] **checkCIF baseline**: the FAP refinement CIF (`tests/data/FAP.XRA` +
      `fluorapatite.cif`) and the NAC + CaF₂ one (`examples/nac_11bm.py`), as
      `main` writes them, plus `to_cif` of LaB₆ (`cod_1000055.cif`) and
      fluorapatite. Record the alerts here; draft the #756 comment for approval.
- [ ] **C-c, the structure block** (`io/cif/blocks.py`): the symmetry items above,
      `_atom_type` loop through `written_species`, U not B,
      `_atom_site_site_symmetry_multiplicity`, formula/Z/Mr/Dx/V, `_audit_*` with
      `_audit_conform`, unique block names, the magic line. `Structure.to_cif` and
      `write_refinement_cif`'s structure part move onto it; the deprecated tag
      leaves the allow-list. A space in a label, duplicate block names and a
      digitless ion are each refused or respelled by name. G1-G3 (#756 § 2) on
      LaB₆, NAC, fluorapatite and an operator-list phase.
- [ ] **checkCIF after C-c** on the same four files. CELLZ01, CHEMW03, DENSD01,
      SYMMG01 and PLAT123 gone from the `to_cif` files; every residual alert carries
      a written reason.
- [ ] Manual (`using/` export page and Part 2 if a convention is stated), `help.py`
      if a name is added, and the skill row or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_exporters.py tests/test_magcif.py tests/test_projects_gsas2.py tests/test_operator_list_phase.py tests/test_cif_registry.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: the registry test fails on a planted undefined or deprecated tag; the
recorded checkCIF reports show the five computed-against-reported alerts above gone
from the structure-only files, each residual alert with a written reason.

The shipping PR comments on #756 (C-a to C-c landed, report attached) and on #195
(its checkCIF slice landed; XYZ moved to 1813). #195 stays open for the fenced
VESTA, Z-matrix and rigid-body parts.

## References

- Issue #756 and its comment of 2026-10-06 — the design and the cut. Issue #195 —
  the original cluster.
- Hall, S. R. (1991); Toby, B. H. (2003, 2006) — the writer's standing citations.
  ITC Vol. G (2006) ch. 3.1 (McMahon), 3.8 (Brown), 4.1 (Hall et al.) as #756 § 3
  cites them.
- COMCIFS `cif_core` v3.3.0 (doi:10.1107/cifdic_core_3.3.0), `Powder_Dictionary`
  2.5.0, `magnetic_dic` 0.9.9.
- https://checkcif.iucr.org/ — the conformance oracle.

## Handover log

- **2026-10-09** — claimed (PR #851), and the scope decided with the maintainer.
  The WP now holds #756's C-a, C-b and C-c with the checkCIF baseline. The
  `### Inherited` mailbox was emptied: the #756 entry and the two setting entries
  (1324, 1118) became Context and Tasks; the #752 label entry and the reader halves
  of the 1118 entries went to the new 1933 with C-d, C-e and C-g, which no open WP
  owned (1911 owns foreign-program writers, and the CIF module is this package's
  own format); the XYZ entry went to 1813, which already owned the XYZ read; the
  1328 magCIF entry was superseded by C-f's move to 1911; the #711/#712 entry was
  consumed by PR #717's merge, its "writers not covered" half being C-c's U and
  multiplicity items. No commit since `5d1f5f67` touches the CIF writer or reader,
  so every inherited measurement still holds.

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
