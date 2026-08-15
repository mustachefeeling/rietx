# WP-1070 — User-facing constraints: ties on the Refinement surface

Milestone: v1.0 · Status: ✅ 2026-08-15 — `tie`/`tie_equal`/`untie` on the
`Refinement` surface, recorded as a `set_tie` node and restored by checkout and
`Project.open`; the analytic Jacobian gated on the reach each branch covers
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

- [x] The verbs on `Refinement` (equality group, affine pair, untie), each
      auto-committing its history node; the `NodeKind` member; checkout/
      replay restores tie state (round-trip test through JSONL and
      `Project.open`).
- [x] Refusal semantics: locked/mode_fixed/tied targets, chains, and the
      symmetry-outranks-user rule, each with the holder named in the
      message and a test quoting it.
- [x] esd propagation on tied rows, pinned against the cell-tie behaviour.
- [x] The measured equal-Biso story on a real protocol, in the handover and
      as an acceptance-grade test.
- [x] Surfaces: `parameters()` rows, `.rxt` rendering, manual
      (`using/concepts.md` § parameter groups), `AGENT_PROTOCOL.md` row.
- [x] Tests + obs/calc/diff PNGs to `tests/output/`.
- [x] **Added in flight**: gate the analytic Jacobian on the reach each
      branch covers, and a `families_tied` cross-backend row — a tie is a
      new derivative path and the numpy assembly dispatches on the free
      path's own *name*.

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

- **2026-08-15** — **closed.** `Refinement.tie` / `tie_equal` / `untie` land,
  recorded as a new `set_tie` `NodeKind` and restored by checkout, replay,
  `branch` and `Project.open`.

  **Done.** All six planned tasks, plus one the plan did not have (below).
  `_ties` on the `Refinement` is the one authority for *which* ties are the
  user's — the symmetry ties are rederived by every `ParameterTable` build and
  are absent from it, which is what `untie` and the new `TieSpec.user` read.
  `_apply_ties` re-declares them on every table build and is the one place
  "symmetry outranks a user tie" can be violated (a tie declared while a path
  was free, then an `edit` that makes that path symmetry-tied); it skips rather
  than overwrites, and `edit` — the recorded verb that can create the collision
  — prunes the register against the model it accepts, so the node carries the
  reconciled state and the warning is said once.

  **The task the plan did not have, and the reason it mattered.** The analytic
  Jacobian dispatches on the free path's own *name* (`_make_jacobian`'s if/elif
  chain), and each branch computes only the rows it was written for: the
  background branch writes one design row, `_structural_column` reads one
  atom's x/y/z off C, `_peak_chain_column` picks the phases to re-derive out of
  the path's `phases.N.` prefix. That was exact while the only ties were the
  derived ones, which never reach outside their own branch. A user tie does,
  and the failure is silent — the column comes back short. So `_column_extras`
  reads off C what each free column also moves, and each branch declares the
  reach it covers; beyond it the column falls to the whole-model FD fallback,
  which is exact because it decodes through C. `_peak_chain_column` is widened
  rather than gated (it takes the union of phases C touches), so a cross-phase
  tie keeps an analytic column. **Untied columns have empty extras, so every
  existing model dispatches exactly as before** — the bit-identity goldens are
  unchanged.

  **Measured, `[dev]` on darwin/arm64** (fits are deterministic; only wall
  clock is machine state):

  - Jacobian: with `atoms.1.biso` tied to `atoms.0.biso` the biso column moves
    by 111.8 against its own scale of 1366 (8 %) and still matches a
    central-difference reference to 2.2e-7 relative. With `background.c1` tied
    to `c0` the **un-gated** background branch would have been wrong by 0.211
    against a column scale of 0.435 — 49 % — while the gated FD column agrees
    to 1.5e-5. The tests assert *additivity* rather than FD agreement: an FD
    reference cannot separate a gated column from an un-gated one where the
    gate's answer **is** that finite difference.
  - `families_tied` cross-backend row green on all seven methods (analytic vs
    fd / jax / torch / numpy+fp32 / jax+fp32 / torch+fp32), 12.5 s, measured in
    a **throwaway `[dev,jax,torch]` venv** outside the checkout — the
    checkout's own `[dev]` venv runs three and skips four.
  - The §7 story, FAP, GSAS protocol, 5750 channels both runs: free parameters
    20 → 18, observations/parameter 287.5 → 319.4, Rwp 0.097307 → 0.097355,
    B(O5/O6/O7) 0.2763(1810) / 0.5279(1911) / 0.4149(1282) free against
    0.4138(899) tied. The tied esd beats the best free one (0.1282) **and**
    their inverse-variance combination (0.0917) — the second comparison is the
    one worth keeping, because beating only the first is consistent with
    dividing by √N.
  - Counts, `[dev]`, macOS, this branch: fast suite **2315 passed, 112
    skipped** in 2:54–3:30 against main's 2285/108 — +34 = 30 passes and 4
    skips, the skips being `families_tied`'s jax/torch rows on a numpy-only
    venv. Full suite: see the entry's end.

  **Two decisions made out loud.**

  1. **`.rxt` gets no tie line, and `FORMAT_VERSION` does not move.** A user
     tie already renders as the `= …` annotation the derived ones use, and it
     is read-only there. A tie *declaration* would need an edit the delta
     cannot see: annotations are regenerated from state on every render and
     omission means "no opinion", so a deleted `= …` and an untouched document
     are the same text — "release this tie" and "I did not type here" would be
     one edit. The verbs stay the only way in.
  2. **No `capabilities()` flag and no `refine_json` arm.** `_SURFACE_FLAGS`
     maps a flag to a top-level export in `__all__` and these are methods, so
     there is no honest derived predicate to add; the agent arm was already a
     stated non-goal. Filed into 1003's mailbox as the asymmetry it is.

  **Gotchas for whoever is next.**

  - `documented_names()` in `tests/test_manual_api.py` scans code spans with a
    newline-free regex, so a span broken across a line feed mispairs every
    backtick after it and the names inside are silently **not** documented.
    `Refinement.untie` reached the deferred file that way before the line was
    rewrapped. Rewrap, do not fight the partition.
  - A tie **changes the dependent's value immediately** (`refresh_ties` +
    `apply_to_models`), so `result_` is invalidated. That is deliberate: the
    alternative leaves the models describing a pre-tie state until the next
    stage recompiles.
  - An untied parameter comes back **held**, not free. Releasing a constraint
    is not a decision to refine.
  - `test_acceptance_fap.py` now has a module-scoped `fap_fit` fixture and an
    `xdist_group("fap")`; a new row there must not mutate the returned
    `Refinement`.

- **2026-08-15** — created from the McCusker audit (WP-1068); gap 2, the
  largest.
