# WP-2010 — Every feature names what verifies it and what validates it

Milestone: generality · Status: ⬜
Track: The audits
Depends on: —
Priority: P3 2026-10-18 — outside the gate after 2004, so it waits on nothing; the magnetic labels move with it

## Goal

Every feature rietx refines or corrects for names what verifies its code and what validates
its physics, in DESIGN.md § Rules, 2's sense. A feature with no validating reference is
declared *not yet validated* where a caller reads it. A test holds the feature list equal to
the validation matrix and to the help vocabulary, so a new feature cannot land without
saying which state it is in. That test is the tripwire Rule 4's test for a new topic lacks.

## Context

DESIGN.md § Rules, 2, as ruled on 2026-10-18 (the generality record § Decisions).
Verification asks whether the code computes its model correctly. Validation asks whether the
model matches the specimen. In `tests/validation_matrix.py`'s tiers, `identity`,
`own_result` and `cross_code` verify; `certificate`, `spread` and `prediction` validate;
`characterisation` does neither, since it records a behaviour or the shape of a failure. A
topic without a validating reference states its equation, source and code plainly and is
declared not yet validated. That state is separate from *provisional*, which
`tests/api_surface.PROVISIONAL_MODULES` keeps for an API that may change (four modules
today, each for API churn). A feature can be either, both or neither.

**Measured at filing** (2026-10-18, darwin arm64, `[dev]`). The matrix holds 134 claims
over 17 acceptance suites. 24 carry a validating tier, and 21 more agree only with another
code. Five suites carry neither: both magnetic suites, Stephens anisotropic strain, extra
peaks and NAC. Three carry cross-code only: fluorapatite, LaB6–cBN and Powderline. Suites
are not features. Capillary absorption is validated by a prediction inside a suite named
for it, while Stephens strain has a suite and no validating claim. The matrix is keyed by
test, and nothing joins a feature to its claims.

**The magnetic case.** Both magnetic datasets are GSAS-II tutorials vendored verbatim
(`cr2wo6_hb2a`, `lamno3_bt1`), and neither tutorial quotes a moment, so every magnetic
claim is `characterisation`. Magnetic refinement is declared not yet validated unless a
published moment for one of those compounds is found and made a reference (not checked at
filing). The magnetic milestone is open (1326, 1327, 1329, 1343, 1418 and 1419 in flight)
and its WPs edit the help entries and manual chapters this WP labels. Merge main before the
label commit. 1327's `### Inherited` already carries a note from 2001 (2026-10-19) saying
what the label will say and what would lift it; update it with the label's final wording.

**Where a caller reads the state.** The matrix lives in `tests/` and is not shipped, so the
declaration has to reach a caller from the package. The seats a caller already reads are a
parameter's help entry (`rietx.help`, served to the GUI at `/api/help` and to an agent
through `help_for`), the manual chapter (each Theory equation already carries a `*Source:*`
line, held by `tests/test_manual.py`), and `capabilities()`. Choosing among them is the
first task. A field on `HelpEntry` moves the GUI's TypeScript, its vitest table and the
committed dist; 2001 § The seams kept audit fields off it for that reason. Here the caller
is meant to see the state, so that cost may be the point, and the handover argues the
choice.

**The grain.** A feature is what a user switches on or refines, so the key is the help
vocabulary: every `PARAMETER_HELP` family and every correction field in
`INSTRUMENT_FIELD_HELP` belongs to exactly one feature, and a test holds that partition
both ways. The partition is what makes a new feature fail until it has a row.

Rule 2 speaks of a *topic*, and some topics are outputs with no parameter family of their
own: quantitative phase analysis (the round-robin claims, the matrix's `spread` tier and
its strongest validation), indexing and extinction symbols (the bethanechol and known-cell
suites), the derived geometry with its esds, and the microstructure readings. A partition
over the help vocabulary alone leaves these with no row, and a new output topic could land
without a state. So the feature list also covers them, keyed on whatever names them for a
caller (a Theory section, a `capabilities()` arm, the verb); the first task argues the key.

### Inherited

(none at filing)

## Non-goals

- New validation data. Finding a published reference for an unvalidated feature is a
  follow-up per feature; this WP records the state and files the follow-ups worth doing.
- Retiering heuristics: 2002 to 2007.
- `PROVISIONAL_MODULES`: an API statement, unchanged.
- Moving a claim between tiers. A claim's tier is its suite's; this WP reads it.

## Tasks

- [ ] The feature list: each feature with its help keys, its Theory section, and the
      matrix claims that reference it (a `features` field on `Claim`, or a map from
      feature to claims; argue which).
- [ ] The state per feature, derived: what verifies it, what validates it, and *not yet
      validated* where the second is empty.
- [ ] The seat: where a caller reads the state, chosen and argued, and the declaration
      written there.
- [ ] The meta-test: the feature list partitions the help vocabulary both ways; every
      claim a feature names exists; every not-yet-validated feature carries the
      declaration at its seat; `docs/VALIDATION.md` regenerated with the feature table.
- [ ] Root CLAUDE.md § Invariants: the clause "Every physics function cites its
      reference" names the meta-test, since DESIGN.md § Rules, 4 places the mechanisms
      that enforce its tests there.
- [ ] The magnetic note in 1327's `### Inherited` updated with the label's wording.
- [ ] Follow-ups filed for features whose published reference is known and unused.
- [ ] Tests; the fast count moved by exactly the tests added.
- [ ] Skill: none. The declaration is the package's own output (DESIGN.md § Rules, 3).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_validation_matrix.py tests/test_help.py tests/test_manual.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

Plus, by hand once: add a throwaway family to `PARAMETER_HELP` on a scratch branch and
confirm the new test goes red naming it.

## References

- `docs/milestones/generality.md` § Decisions; DESIGN.md § Rules, 2 and 4.
- `tests/validation_matrix.py`, `docs/VALIDATION.md`, `tests/api_surface.py`.
- Roache, P. J. (1998). *Verification and Validation in Computational Science and
  Engineering*. Hermosa. Oberkampf, W. L. & Roy, C. J. (2010). *Verification and
  Validation in Scientific Computing*. Cambridge University Press.

## Handover log

- **2026-10-18** — created, from the cascade of DESIGN.md's rules into the generality
  milestone. No open WP owns a feature-level audit against Rule 2: 1918 and 1933 validate
  files on read, and 1464 screens batches. Filed in this milestone and outside its gate
  after 2004, because the gate tests whether rietx's decisions are warranted, and this
  WP's premise is already measured by the counts above.
