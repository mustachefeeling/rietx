# WP-1451 — the extinction a powder has

Milestone: unscheduled · Status: ⬜
Depends on: —
Priority: P4 2026-09-23 — a label that contradicts its cited paper; the physics is right and no number moves

## Goal

The Sabine powder correction is called what its source calls it, primary
extinction, everywhere a reader meets the name. One sentence says why a
powder has no secondary extinction, so nobody "corrects" it back.

## Context

Issue #419 (2026-09-22). `model/extinction.py` opens "Secondary extinction —
the Sabine polycrystalline model", and the manual's heading says the same.
The reporter read Sabine, Von Dreele & Jørgensen (1988), *Acta Cryst.*
A**44**, 374, § 3 p. 375: "The only extinction mechanism which can operate
in a powder is primary extinction". The same paragraph calls multiple
scattering the powder analogue of secondary extinction. The fitted quantity
in its Table 1 is in µm², a squared block size, which is a primary-extinction
parameter.

**The tree agrees with the reporter in its own words.** Both the module
docstring and the manual describe the mechanism as the diffracted beam
re-diffracting "inside a coherently scattering domain". That is the
definition of primary extinction. Secondary extinction is attenuation of the
incident beam by other, upstream mosaic blocks. **Nobody in this session read
the paper.** The quote is the reporter's, and the local paper corpus has been
unavailable since 2026-09-22. Ask the maintainer for the paper before editing
(memory: ask for papers, don't work around them).

**Sites**, checked against the tree at `644dff84` with
`git grep -n -i 'secondary extinction\|secondary-extinction'`:

- `src/rietx/model/extinction.py:1`, the module title.
- `docs/manual/corrections.md:213`, the heading. **Renaming it moves the
  anchor**, and `src/rietx/help.py:682` quotes
  `corrections.html#secondary-extinction`. `tests/test_help.py` checks every
  anchor against the built HTML, so the heading and the anchor move in one
  commit. `docs/manual/using/glossary.md` is generated from `help.py`.
- `src/rietx/help.py:672-674`, the entry's title and text.
- `docs/manual/using/data.md:144`, the `Phase.extinction` row.
- `src/rietx/viz/compare.py:842`, the `rietx compare` variant label a user
  sees. Check `tests/test_compare_ui.py` for a pinned label.
- `src/rietx/io/projects/gsas2.py:1776`, a reader's description string.
- Comments: `src/rietx/schemas/structure.py:533`,
  `src/rietx/model/forward.py:531` and `:1366`,
  `src/rietx/strategy/staged.py:321`.
- Tests: `tests/test_extinction.py:1`, `tests/test_acceptance_srm660c.py:168`,
  and `tests/validation_matrix.py:418`, whose claim text also appears in
  `docs/VALIDATION.md:263`. Find out whether that file is generated before
  editing it by hand.

**The Laue coefficients' provenance.** The reporter matched c₁-c₄ to the
paper's eq. 3 digit for digit. Eq. 3 stops at x⁴, so c₅ and c₆ are not in
A**44**, 374. The module already says the six values are GSAS-II
`GetPwdrExt`'s. The ask is to say whether c₅ and c₆ come from Sabine's
companion paper (A**44**, 368) or from GSAS-II alone. Only the paper can
answer that.

## Non-goals

- Any change to the model, its coefficients or its numbers.
- The historical record: WP-0506's title and file, the milestone records and
  ROADMAP's 0506 row describe what was done under that name and stay.
- WP-0506's non-goal naming "primary extinction" as a separate model. Say in
  this WP's handover that the premise was wrong, rather than editing a
  closed WP.

## Tasks

- [ ] Read Sabine, Von Dreele & Jørgensen (1988) § 3, and Sabine (1988)
      A**44**, 368 for c₅/c₆, from the maintainer's copy.
- [ ] Rename across the sites above, with heading and anchor in one commit,
      and add the sentence on why a powder has only primary extinction.
- [ ] State c₅/c₆'s source in the module docstring.
- [ ] Tests: `tests/test_help.py`, `tests/test_manual.py` and
      `tests/test_compare_ui.py` pass; the manual builds under `-W`.
- [ ] Skill: grep `docs/skill/` for the name. None at `644dff84`, so "none"
      unless a row appears before this lands.

## Acceptance

```sh
git grep -n -i 'secondary extinction' -- src docs/manual tests   # no hits
.venv/bin/python -m pytest tests/test_help.py tests/test_manual.py tests/test_compare_ui.py tests/test_extinction.py
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

## References

- Sabine, T. M., Von Dreele, R. B. & Jørgensen, J.-E. (1988). *Acta Cryst.*
  A44, 374-379.
- Sabine, T. M. (1988). *Acta Cryst.* A44, 368-373.
- Issue #419.

## Handover log

- **2026-09-23** — created, from the 2026-09-23 issue triage (issue #419).
  Checked against the tree at `644dff84`: both labels read as the issue
  quotes, and a grep finds a dozen more sites, listed in Context. Next: get
  the two papers from the maintainer.
