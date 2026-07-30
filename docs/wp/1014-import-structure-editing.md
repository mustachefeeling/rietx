# WP-1014 — Import & in-GUI structure/instrument editing

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1008, WP-1010

## Goal

Data gets *into* a project from the browser: upload endpoints with
content-sniffed validated previews, an import wizard, atom-level structure
editing through the Wyckoff DOFs, and instrument forms.

## Context

- `POST /api/upload/pattern|cif|instrument` — bytes + filename →
  content-sniff via the existing readers → validated preview (echo back
  n_points/range/phases/λ before committing to the project):
  - `read_pattern` (`io/readers.py:21`) dispatches content-first: `.cif`
    suffix → pdCIF; `_looks_gsas` (regex `^BANK\s+\d+`, `:106`) → GSAS
    FXYE/STD incl. esd column; else 2-3 column ASCII. **`.XRA` has no
    dedicated parser** — GSAS-format files read via the `BANK` sniff; name
    the supported formats as xy/xye, GSAS (FXYE/STD), pdCIF, not by
    extension folklore.
  - `structure_from_cif` (`crystallography/cif.py:20`) with its
    `aniso: bool = False` keyword — the wizard's aniso opt-in checkbox
    mirrors the invariant that **reading a file must not silently change
    what a plan frees** (several test CIFs carry aniso loops).
  - `load_instrument_profile` (`io/instrument_profile.py:63`, top-level
    export) — everything arrives `vary=False`, per the calibrate → freeze →
    refine workflow.
- Import wizard: anode picker from `capabilities()` (WP-1007), wavelength /
  geometry forms, the aniso checkbox above.
- Structure editor: atoms add/remove/species/occupancy/Biso; **coordinates
  edited through the Wyckoff DOFs** (`phases.i.atoms.j.dof.k`,
  `crystallography/wyckoff.py`) so site-symmetry violations are
  *unrepresentable* rather than merely refused — the GUI edits the DOF
  values, and fully-fixed special positions render read-only (the table
  already raises on `vary=True` there). ADP editing follows the same shape
  one rank up (`adp.k` from `wyckoff.adp_basis`, absolute DOFs,
  out-of-subspace tensors raise).
- Instrument forms: profile (U V W X Y, S/L H/L), zero/displacement,
  background family, geometry block — all `PATCH /api/instrument` over the
  WP-1008 routes, one history node per edit.

### Inherited

From **WP-1013** (landed 2026-07-30): a structure or instrument edit commits an
`edit_model` node, which **moves the head**, which is the text pane's reload signal
— so an open text buffer will go *stale* the moment this WP's import or model
editor lands a change, and correctly so. Nothing to build: `lib/sync.ts` already
holds the edit and offers a re-read. What is worth knowing is that the head is now
load-bearing for three panels (parameters, report, text), so **a verb that changes
the model and does not commit a node leaves all three showing the previous state**.

Also: `panels/Stubs.svelte`'s "panels still owed" list is where this WP's row lives
(`Import / editing — WP-1014`); delete it when the panel lands, as 1013 did.

From **WP-1011** (landed 2026-07-30): the shell's empty state already points at
this WP by name ("Creating a project in the browser needs the import flow
(WP-1014)"), so that copy is what this panel replaces. Three carried facts:
**`ProjectDoc.ui` is live** and the frontend owns its keys — `{"simple": bool}`
is taken, set through `POST /api/project {ui: …}`, which persists on the verb, so
an import wizard's own state can join it the same way. **A model patch is a whole
validated model** (`PATCH /api/structure`), and a state refusal outranks body
validation — disable the form off the `state` frame rather than letting a user
retype a structure into a 409. And **non-finite floats cross the wire as strings**
(`"Infinity"`), since `JSON.parse` rejects Python's bare token — a `Parameter`'s
`min`/`max` in a structure payload will arrive as strings, so `lib/table.ts`'s
`num()` is what to read them with.

From **WP-1012** (landed 2026-07-30): **`add_impurity_phase` is this WP's
button.** It is one of the four `ActionKind`s `report/apply.py` classifies as
`advice`, and the note says why — "no phase is named yet, so there is nothing to
free … that is an `edit_model` move, and the search for a candidate is not
something this report can do for you". The report already hands over everything the
flow needs (the unindexed peaks' 2θ and height/σ, `two_theta_range` on the action,
and a plot the panel can already zoom to it), so wiring "identify this, then add
it" is an import-flow question rather than a report one. If this WP gives it a verb,
move the kind from `advice` to a new `how` in `RECIPES` — the split is a table with
a meta-test, not scattered conditionals.

One measured trap for the instrument form: **Layer 2 proposes Bragg-Brentano
aberrations whatever geometry is declared** — on a Debye-Scherrer instrument the
highest-confidence suggestion named `instrument.geometry.sample_transparency`,
which `params/vector.py` force-fixes off `bragg_brentano`. So a geometry change in
this editor silently changes which report suggestions are reachable, and the
`held_because` on those rows is what says so.

From the **v1.0 GUI plan** (2026-07-29): the FCJ corner at S/L = H/L with
both apertures started equal is a real parameterisation trap (identical
Jacobian columns, ρ = +1.000 — measured in WP-0601). The instrument form
should not *default* new instruments into S/L == H/L silently; keep the
shipped defaults but surface the correlation guard when it fires.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): **adopting an
indexed cell is a structure edit**, so it reuses this WP's editor and
`Refinement.edit(structure=…)` rather than inventing a path.
`indexing.structure_from_candidate` (WP-1024) produces a phase carrying a
**dummy atom** — required because `Phase._nonempty` raises on an empty atom
list, and inert because `_run_stage` force-fixes `.atoms.` in lebail mode. The
structure editor should make that atom's status legible (it is a placeholder,
not a site), which is the same note left in WP-1004 for the parameter surface.

From **WP-1008** (GUI server, landed 2026-07-30):

- `POST /api/upload/{pattern,cif,instrument}` are **reserved** and 404 naming
  this WP; adding them is entries in `gui.server.ROUTES` plus methods on
  `GuiSession`. Note they are the only routes in the surface that will not take
  JSON, so the body-reading helper (`Handler._body`) needs a sibling for
  multipart or raw bytes.
- `GuiSession.project_new` already takes **server-side paths** — `pattern` a
  path, `structure` either an inline dict or `{"cif": path, "aniso": …,
  "phase_name": …}`, `instrument` an inline dict. `_as_structure` /
  `_as_instrument` are the two places sniffing plugs into.
- **`instrument` is required and refusing it is deliberate**: `Instrument()` does
  not validate (no default `source`), and defaulting an anode would put a
  wavelength nobody chose into every refined cell. An import flow must ask.
  Reading a CIF passes `aniso=False` unless asked, for the CLAUDE.md reason —
  reading a file must not silently change what a plan frees.
- Whole-model `PATCH /api/structure` / `PATCH /api/instrument` already exist and
  record an `edit_model` node with an optional `label`; they replace a validated
  model rather than merging fields, so in-GUI editing can build on them without
  a field-patch protocol.

## Non-goals

- **Space-group editing — hard fence.** Re-import a CIF instead.
  `structure_from_cif` is the only symmetry-derivation path and symmetry UI
  is bottomless. Wyckoff DOFs and typed atom fields only.
- No CIF writing from the editor (export routes already exist).
- No occupancy constraint editor (site-fraction ties across atoms) — v2
  with rigid bodies.

## Tasks

- [ ] Upload endpoints: bytes → sniff → validated preview → commit-to-
      project step (two-phase, so a bad file never half-lands).
- [ ] Import wizard: pattern → structure → instrument flow; anode picker
      from capabilities; aniso opt-in checkbox wired to
      `structure_from_cif(aniso=)`.
- [ ] Structure editor: atom table (add/remove/species/occupancy/Biso),
      coordinate editing via DOFs, locked positions read-only, aniso ADP
      editing via `adp_basis` patterns.
- [ ] Instrument forms + PATCH wiring; each edit a history node.
- [ ] `tests/test_gui_server.py`: upload-sniffing rows for `.xye`, FXYE,
      pdCIF and an aniso-loop CIF asserting the opt-in (aniso absent unless
      checked).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- CLAUDE.md: site-symmetry DOF and ADP conventions; instrument ⊕ sample
  split (calibrate/freeze/refine).

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan. Reader dispatch and the
  `aniso=` keyword verified against the tree the same day.
