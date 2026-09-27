# WP-1505 — rietview: the figure leaves the package

Milestone: v1.7 · Status: ⬜
Depends on: 1504
Priority: P4 2026-09-27 — waits on a trigger nobody has pulled; P3 the day one fires

## Goal

`rietview` on PyPI: `build`, the masks, `render_structure`, the scene rules
and their corpus, adapters for a rietx `Structure`, pymatgen and ASE, and
its own `SKILL.md`. It needs numpy and gemmi, numba optional. rietx depends
on it and re-exports `rx.viz.render_structure`, and the GUI's structure
route calls it. Nothing on rietx's surface moves.

## Context

### The name, decided 2026-09-27

The maintainer chose `rietview`. It was free on PyPI, conda-forge and
GitHub repository search that day, as were `rietfig` and `rietviz`. The
naming survey behind the choice:

- PyPI normalises `-`, `_` and `.` to one project name, so only the import
  name differs between `rietx-view` and `rietx.view`.
- `rietx.view` as a second distribution needs `rietx` to be a namespace
  package with an empty `__init__`, and rietx's `__init__` carries the
  surface. pymatgen's add-ons and diffpy's dotted names work that way and
  carry the install-order bugs.
- `rietx-view` follows `pytest-cov`: a plugin that depends on the brand.
  Here the brand depends on the package, the other direction.
- `rietx-core` and `jaxlib` name a package nobody imports directly.
- An independent name is the honest signal for a package others install on
  its own. `rietview` keeps the brand and says the field; `view` promises
  interaction the package does not have, and the maintainer accepted that.

The import name equals the distribution name.

### The trigger

Either of two facts, recorded in this file when it lands:

- A user, or an agent task, wants the figure without the refinement.
- WP-1504's two rounds show the surface unchanged between them.

Until then the code stays in rietx, where the eval harness, the 21-phase
corpus, the browser parity row and the compiled-tier switch already live.

### The measured cost of the split

WP-1501's import-boundary pin names what `viz/figure3d` and
`gui/structure3d` take from rietx: `_about` (the data package name),
`viz.theme` (the colour tokens), `model.compiled` (the numba pool and the
switch), `crystallography.adp` and `crystallography.symmetry` (the basis,
U* and orbit expansion, both gemmi over numpy). `build()` also reads the
pydantic `Structure` field by field in `_expand`, and writes each site's
parameter dot-path (`"path": "phases.0.atoms.3"`) so a GUI click reaches
the parameter table. The dot-path belongs to the adapter. Nothing else in
the list is rietx's by nature.

### Design

- **Plain-data input.** `build()` takes cell, symmetry operations and
  sites as fractional position, species, occupancy, Uiso and optional
  Uij. `rietview.adapters.rietx(structure, phase)` builds it and adds the
  dot-path as an extra field the renderer ignores; `pymatgen` and `ase`
  adapters are ten lines each.
- **Theme.** `render_structure(tokens=)`, with rietview's own light and
  dark pair as the default and rietx passing its own. Two products, two
  palettes. rietx's rule that its three browser surfaces share one set of
  values is unchanged.
- **Compiled tier.** A small numba shim with the same soft import and
  fallback, and `RIETVIEW_COMPILED=0`.
- **The scene corpus ships in rietview's wheel**, and rietx's vitest reads
  it from the installed package, so the GUI's `buildScene` stays held
  equal to the renderer.
- **The Svelte viewer stays in rietx.** It is a panel of the GUI.
- **History.** `git filter-repo` scoped to `src/rietx/viz/figure3d`,
  `src/rietx/gui/structure3d.py`, their tests and data, so the new repo
  carries the commits that made it. The rewrite is scoped to those paths
  and never touches rietx's main.
- **Release.** Built from the tag by a workflow, never by hand
  (`docs/RELEASING.md`'s one rule). rietx pins a floor and re-exports.
- **The skill.** rietview's own `SKILL.md` carries the figure checklist;
  rietx's `api-figure.md` becomes a pointer to it.

## Non-goals

- Moving the Svelte viewer or any GUI code.
- A GUI or a CLI in rietview.
- Renaming `rx.viz.render_structure`.

## Tasks

- [ ] The trigger recorded here with its date and evidence.
- [ ] The repository, the name on PyPI, the workflow from `RELEASING.md`.
- [ ] Plain-data `build()` and the three adapters, with the dot-path in
  the rietx adapter.
- [ ] Theme and compiled-tier injection; the corpus in the wheel.
- [ ] `git filter-repo` over the named paths; the tests moved; rietx
  depending and re-exporting; the GUI route calling through.
- [ ] rietview's `SKILL.md`; rietx's `api-figure.md` pointing at it.
- [ ] The break staged in the open milestone's record and the release
  notes.

## Acceptance

- `pip install rietview` in a fresh venv draws NAC from a CIF with no
  rietx present.
- rietx's fast suite and `npm --prefix gui test` are green with rietview
  installed and the corpus read from the wheel.
- `rx.viz.render_structure(structure)` is bit-identical before and after.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
npm --prefix gui test && npm --prefix gui run check
```

## References

- PyPA packaging guide, *Packaging namespace packages*.
- PEP 503, name normalisation.
- `docs/RELEASING.md`.

## Handover log

- **2026-09-27** — filed from the session that closed WP-1470, the day the
  name was chosen. Next: nothing until the trigger; re-check the name is
  still free when it fires.
