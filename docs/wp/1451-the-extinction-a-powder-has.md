# WP-1451 — the extinction a powder has

Milestone: unscheduled · Status: ✅ 2026-10-04 — the rename landed (PR #533); `ext` is declared in µm² and its `typical` range is measured
Track: The repo's own process
Depends on: —

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

- [x] Read Sabine, Von Dreele & Jørgensen (1988) § 3, and Sabine (1988)
      A**44**, 368 for c₅/c₆, from the maintainer's copy.
- [x] Rename across the sites above, with heading and anchor in one commit,
      and add the sentence on why a powder has only primary extinction.
- [x] State c₅/c₆'s source in the module docstring.
- [x] Tests: `tests/test_help.py`, `tests/test_manual.py` and
      `tests/test_compare_ui.py` pass; the manual builds under `-W`.
- [x] Skill: grep `docs/skill/` for the name. None at `644dff84`, so "none"
      unless a row appears before this lands.
- [x] Declare `Phase.extinction`'s unit (D² in µm²): a schema unit and a
      `UNIT_DISPLAY` row, since `help.py`'s `unit` is pinned to the live
      `Parameter`. Then restate `typical` from D. From PR #533's review.
      (2026-10-04: `unit="um^2"`, shown as µm²; `typical` measured.)

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

- **2026-10-04** — **Closed.** The extinction coefficient now says what it
  is measured in, µm², in its help entry, which the glossary and the GUI's
  help card both read. Its help text gave a
  "typical" value a thousand times too small to dim any reflection. It now
  gives the range where extinction is visible, measured on five structures.
  No fit's numbers move.
  - **Done.** `Phase.extinction`'s default declares `unit="um^2"`;
    `help.UNIT_DISPLAY` spells it `µm²` (U+00B5, the repo's only micro
    sign); the help entry's `unit` follows, as `test_help.py` pins. The
    `using/data.md` row puts µm² in its Default column like its siblings,
    and the theory chapter says after the Sabine equations why 0.079411 makes
    `ext` a D² in µm². A document saved before this keeps `unit: null` on
    that parameter, whatever its schema.
  - **Measured** (`sabine_extinction` on the strongest reflection, Cu Kα,
    10-120° 2θ, the scratch script's five structures: the suite's LaB6,
    fluorapatite and COD 1000055, 9007744 and 4002052): a 1 % loss needs
    ext = 0.12-8.4 µm² (D = 0.35-2.9 µm) and a 10 % loss 1.4-93 µm²
    (D = 1.2-9.6 µm). The old `typical` of 1e-4 costs at most 8e-6. The new
    text is "0 for a ground powder; 0.1 to 100 (blocks of 0.3 to 10 µm)
    where a strong reflection loses a visible share". `Stage.seed`'s
    "1e-4 to 1e-3" stays: it describes the seed the extinction stage uses
    (1e-3), chosen for the gradient, not as a size.
  - **Tests** (`[dev]`, macOS arm64, another session's pytest running, so
    no time is quoted): fast selection before the review 8164 passed, 159
    skipped, no test added; the review's fix adds one. The final tree
    (current with `origin/main`, nothing else running): 8165 passed,
    159 skipped (+1), in 2:33. The added test takes
    0.03 s. The acceptance files, `test_schemas` and `test_magnetic_width`:
    411 passed. `sphinx -W` builds; the glossary shows µm². The acceptance
    grep still finds the two intended lines the 2026-09-30 entry names.
  - **Review** (`/code-review high --fix`, six findings). Fixed: the
    data.md row's unit column, a reflowed schema comment, and the theory
    sentence above. **One was a real defect in this change**: a project saved
    before schema 0.35 stores extinction with its range and no unit, and the
    declared-range repair read the missing unit as issue #204's signature. It
    filled `um^2` and emitted an info `DECLARED_RANGE_RESTORED` note per phase
    blaming #204. `migrate._candidate` now needs a range or transform to
    restore, so a unit alone rides only with one;
    `test_a_unit_declared_later_is_no_range_to_restore` fails without the fix.
    Any later unit declared on a pre-0.35 field takes the same path. Declined:
    `gui/src/lib/history.ts:361` says an extinction coefficient reaches 1e-6.
    It does, in µm² too: the LaB6 acceptance refines it to about 2e-10.
- **2026-09-30** — The rename landed from outside: PR #533
  (`mustachefeeling`), merged as `4de25284` in a `/pr-review` run, closing
  #419. The Sabine correction is now called primary extinction everywhere a
  user meets it, and one sentence says why a powder has no secondary
  extinction. Both papers were read in full, so c₁…c₆ each have a stated
  source. No number moved. One follow-up remains, a new task below: the
  parameter's unit is undeclared, and its `typical` range describes a block
  too small to extinguish anything.
  - **Done** (all five original tasks, ticked). The help entry's title, text
    and anchor (`corrections.html#primary-extinction`) moved in one commit
    with the manual heading. `using/data.md`, the `rietx compare` variant
    label, the GSAS-II reader's description, the module title, four
    comments, the test docstrings and the `validation_matrix` claim with its
    regenerated `docs/VALIDATION.md` were renamed too. The review found one
    more site, which the WP's grep missed because it is spelt with an
    underscore: `capabilities()["features"]["secondary_extinction"]` is now
    `primary_extinction`. A client matching the old key stops seeing it,
    which the compatibility page's preview promise covers. Skill: no
    `docs/skill/` row names the mechanism, so there was nothing to change.
  - **Where c₁…c₆ come from**, now in the module docstring. c₁…c₃ are
    Sabine (1988) A44, 368 eq. 6, and c₄ is SVJ (1988) A44, 374 eq. 3.
    **c₅ and c₆ are in neither paper**, so they stay attributed to GSAS-II.
    The review derived the Taylor series of E_L = e^{−x}[I₀(x) + I₁(x)]
    independently: −1/2, 1/4, −5/48, 7/192, −7/640, 11/3840. The tree's c₅
    is exact. **Its c₆ = 2.8497409e-3 is 11/3860, 0.5 % below 11/3840**, at
    most 1.5e-5 in E_L on x ≤ 1. It stays as it is, because the cross-code
    golden's target is GSAS-II's function, and the docstring says so. The
    x = 1 switch and the four-term asymptote are GSAS-II's too: eq. 16
    prints four terms and names no switch.
  - **`ext` is D² in µm²**, not (K·D)². `_XPOL` = 0.079411 = r_e²·10⁸
    (r_e² = 7.9408e-10 Å², 4e-5 relative), as SVJ's Table 1 has it. The
    module docstring now says "a squared block size D², in µm²", without
    the undefined K.
  - **WP-0506's premise was wrong, as this WP asked to be recorded here.**
    Its non-goal set primary extinction aside as a separate model outside
    the powder correction. But the Sabine powder correction WP-0506 shipped
    *is* primary extinction, and SVJ p. 375 says it is the only mechanism a
    powder has. WP-0506 is closed and stays as written.
  - **Gotcha: the acceptance grep is no longer "no hits".** It finds three
    intended lines: `help.py`'s "a powder has no secondary extinction",
    and two in the module docstring (the powder counterpart of secondary
    extinction, and "not a secondary-extinction (mosaic-spread)
    coefficient").
  - **Next: the new task.** With `ext` = D² in µm², `help.py`'s
    `typical` for `phases.*.extinction` ("up to 1e-4 for large
    crystallites") is a 10 nm block, which gives no extinction at all. The
    suite's own injection test uses `ext = 2.0`
    (`tests/test_extinction.py:247`). Declaring the unit needs a schema unit
    on `Phase.extinction` and a `UNIT_DISPLAY` row, because `help.py`'s
    `unit` is pinned to the live `Parameter`. `typical` should then be
    restated from D. It is a change of its own and moves no number.
  - **Measured on the merged tree** (Linux x86_64, 4 cores, py3.12.3,
    `[dev,jax]`, run as root). Gated in one stack with #551, which shares no
    file with it: `origin/main` `aae433c` + #551 + #533, full suite with
    slow tests included (`-n auto --dist loadgroup`): 7084 passed, 120 skipped, and 1 failed, in 1:12:55. The failure is
    `test_held_phase`'s ramp runaway guard, at 77.7 s against its 60 s bar,
    the load sensor WP-1420 records. `ruff` clean.
    `git diff` between the stack and `origin/main` after both merges:
    empty. An earlier stack on `d4ff816` (+ #551 + #556) gave 1 failed,
    7104 passed, 118 skipped in 1:14:01, with the same single failure.
    Area selection at round 1 (`test_acceptance_srm660c`, `test_extinction`,
    the compare, help, manual and docs tests, `test_capabilities`): 860
    passed, 1 skipped. `sphinx -W` builds, and `corrections.html` carries
    `#primary-extinction`.
- **2026-09-23** — created, from the 2026-09-23 issue triage (issue #419).
  Checked against the tree at `644dff84`: both labels read as the issue
  quotes, and a grep finds a dozen more sites, listed in Context. Next: get
  the two papers from the maintainer.
