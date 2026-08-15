# WP-1070 — User-facing constraints: ties on the Refinement surface

Milestone: v1.0 · Status: ⬜
Depends on: WP-1004 (the parameter surface this extends) — recommended
**before 1003**: recording a tie edit adds a member to the closed `NodeKind`
literal, which is free before the freeze and a versioned history-format
decision after it (the grounds are in 1003's Inherited)

## Goal

A user can constrain one parameter to another through `Refinement` — equal
displacement parameters across similar atoms, complementary occupancies, a
generic affine tie — with the tie recorded in history, surviving a project
round-trip, and visible in `parameters()`. Gap 2 of the McCusker audit
(`../milestones/v1.0.md` § Appendix), the audit's largest.

## Context

- **The paper recommends it four separate times** (§7: constrain thermal
  parameters of similar atoms to be equal, apply chemical constraints to
  occupancies; §12.7 ix and §12.8 v repeat both) — restraints *add*
  observations, constraints *reduce* parameters, and this package has only
  the former.
- **The machinery exists one rank down.** `params.vector.AffineTie`
  (`params/vector.py:74`) and `ParameterTable.set_tie` (`:423`) already
  carry the crystal-system cell ties and the Wyckoff coordinate ties, so the
  analytic Jacobian chain, the locked/tied display and the tied-row-refuses-
  an-edit semantics (WP-1004: a tied path names its sources) all exist. What
  is missing is a verb on `Refinement` and persistence.
- **Verb shape is the design question.** The common case is an equality
  group ("these three Bisos are one parameter"), which is N−1 ties to one
  source; the general form is affine (occ_j = 1 − occ_i is scale −1, offset
  1). Design the surface for the reader: an equality verb first, the affine
  form as the general case, and an untie verb — every one recorded.
- **Persistence is the sequencing argument.** `NodeKind`
  (`schemas/history.py:39`) is a closed `Literal["root", "stage",
  "set_vary", "set_value", "edit_model", "lebail_update", "merge"]`; a tie
  edit needs its own kind (the `set_vary`/`set_value` precedent: an
  auto-committed, restorable node). Adding the member before the freeze is
  free; after, it is a history-format version decision. Checkout/replay of a
  node must restore the tie state exactly.
- **Refusal semantics extend, not change.** A tie may not target a locked
  entry, a `mode_fixed` entry, an already-tied entry, or create a chain
  (a source must be a free entry) — refuse naming the holder, the existing
  sentence. A symmetry tie always outranks a user tie.
- **esds on tied entries**: derived, |scale|·esd(source) — check what the
  table already does for cell ties and make user ties identical; the
  `ParameterRow` mirror rule (pinned by `dataclasses.fields`) governs any
  new row field.
- **The measured story to ship with it** (the invariant: a record, never an
  Rwp comparison): on a real protocol (FAP or corundum), tie the similar
  atoms' Bisos and show the esds contract and the observation/parameter
  ratio rise while the fitted values stay within their esds — §7's own
  argument, measured.
- The GUI displays rows through `parameters()`, so tied rows render without
  GUI work; GUI *editing* of ties is out of scope. The `.rxt` textdoc
  renders the table — verify a tied row reads correctly, and whether the
  textdoc format needs a tie line is a decision to make out loud
  (`FORMAT_VERSION` is quoted by `capabilities()`).

## Non-goals

- Rigid bodies (§8's parameter-reduction alternative) — already on the v2+
  fence.
- Nonlinear constraints (a positive-definiteness cone, a sum over more than
  an affine pair with bounds) — refuse with a message, do not approximate.
- A `refine_json` arm for ties: record the asymmetry in 1003's Inherited
  when this closes; the agent surface decision is the freeze's.
- GUI tie editing.

## Tasks

- [ ] The verbs on `Refinement` (equality group, affine pair, untie), each
      auto-committing its history node; the `NodeKind` member; checkout/
      replay restores tie state (round-trip test through JSONL and
      `Project.open`).
- [ ] Refusal semantics: locked/mode_fixed/tied targets, chains, and the
      symmetry-outranks-user rule, each with the holder named in the
      message and a test quoting it.
- [ ] esd propagation on tied rows, pinned against the cell-tie behaviour.
- [ ] The measured equal-Biso story on a real protocol, in the handover and
      as an acceptance-grade test.
- [ ] Surfaces: `parameters()` rows, `.rxt` rendering, manual
      (`using/concepts.md` § parameter groups), `AGENT_PROTOCOL.md` row.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_params_surface.py tests/test_history.py tests/test_project.py -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- McCusker et al. (1999), §7, §8, §12.7 (viii)/(ix), §12.8 (v). Local copy at
  `~/zotero-linker/derived/YWSBLSIS/`.
- WP-0301 (the affine p = C·θ + d machinery this reuses), WP-1004 (the
  surface contract this extends).

## Handover log

- **2026-08-15** — created from the McCusker audit (WP-1068); gap 2, the
  largest.
