# WP-1527 — foreign files spell a species as the other program does

Milestone: unscheduled · Status: 🔄 2026-10-02 — all four fix PRs landed (#569, #570, #572, and #568 for `.pcr`); the fallback-ion decision is open
Track: Coming from another code
Depends on: — (WP-1118 closed 2026-09-16; its writers and readers are what this corrects)
Priority: P2 2026-09-30 — a silent wrong structure in another program's refinement (GSAS-II turns `7Li` into H), on a path few fits run; the fix PRs are open

## Goal

A species written to a FullProf `.pcr`, a GSAS `.EXP` or a GSAS-II phase CIF is
spelled the way that program reads it, or refused by name. A species read back
from a GSAS `.EXP` or a GSAS-II `.gpx` carries the isotope the file chose. No
foreign writer makes a site into another element without saying so.

## Context

rietx's own round trip passes on every case below, because each reader accepts
the spelling its own writer used. That is why no test saw them. Every outcome
was measured by the reporter against the real program: FullProf.2k 8.20
(Feb 2025, macOS), GSAS-II 5.6.3. GSAS (EXPEDT/GENLES) was not run.

Five issues, one mechanism, each with a fix PR from the same contributor:

- **#553, PR #569 — GSAS-II phase CIF.** `write_gsas2_phase_cif` copies
  `Atom.species` into `_atom_site_type_symbol`. GSAS-II turns `7Li`, `2H` and
  `60Ni` into H (b −3.74 fm), and the digitless ion `Cu+` into C. Charges are
  fine (`Zr4+` → `Zr+4`). An isotope is a per-type choice in the phase's
  `General["Isotope"]`, with no CIF tag.
- **#554, PR #570 — GSAS-II `.gpx` reader.** `gsas2.to_structure` never reads
  `General["Isotope"]`, so a deuterated project reads back as natural H
  (b +6.68 → −3.74 fm).
- **#555, PR #572 — GSAS `.EXP`.** The reader turns `NI+2_58` into `Ni258+`
  (natural Ni, a +258 ion) because `fullprof.normalize_species` strips the
  underscore. The writer's `ZR4+`/`7Li` spellings do not match the manual's
  `aasv_nnn` grammar (Larson & Von Dreele, LAUR 86-748).
- **#557, #558, PR #568 — FullProf `.pcr`.** The writer puts U = V = W = 0 with
  no resolution file, and FullProf stops before it reads a species. Past that,
  `Zr4+`/`O2-` are NOT FOUND (FullProf's key is `ZR+4`), and an isotope has no
  spelling except a LINE-12 user b. The reader refuses `Nsc = 1`.

**The X-ray side is the coupling.** An isotope label had no X-ray f₀ until PR
#556 (#552) made every X-ray lookup take the element. That landed 2026-09-30,
so a reader may now hand back `2H` for a deuterated project that has an X-ray
histogram. Neutron keys on `neutron.normalize_species`, which already reduces
an ion to its isotope.

**Two decisions the fix PRs take and a reviewer should see stated:**

1. An isotope with no place in the file is **refused by name**, not written as
   the element with a warning (the file would refine natural abundance until
   someone acts).
2. A digitless ion (`Cu+`) is refused, because rietx computes the neutral atom
   for it (#202's fallback) and GSAS-II reads carbon.

## Non-goals

- `Phase.propagation_vector` dropped by the same writers: #567, PR #571, which
  is WP-1328's.
- A `.gpx` writer. This build writes the `.instprm` + phase CIF pair.
- Running GSAS EXPEDT: no install. The writer half of #555 stays
  "unknown whether accepted" until someone does.

## Tasks

- [ ] Review and land PRs #568 (.pcr), #569 (GSAS-II CIF), #570 (.gpx reader),
  #572 (.EXP) through `/pr-review`, each against its issue's reproduction
- [ ] A test per writer that reads the written species through the *other*
  program's rule (the reporter's table), not through rietx's own reader
- [ ] Decide the reader's X-ray arm for an isotope from a foreign file
  (#554's note: land with #552 or refuse on the X-ray histogram)
- [ ] Skill: a reference row for the refusal codes the PRs add, or "none" and why

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_species_fallback.py tests/test_projects_fullprof.py tests/test_projects_gsas.py tests/test_projects_gsas2.py -q
.venv/bin/python -m ruff check src tests examples
```

Plus the four reproductions in issues #553, #554, #555 and #557/#558 giving
the spelling the issue's "fix direction" names.

## References

- Larson & Von Dreele (2004), *GSAS*, LAUR 86-748, `EXPR ATYP`/`AFAC` records.
- Sears (1992), *Neutron News* 3, 26: the b table behind `neutron.b_coh`.
- Issues #553, #554, #555, #557, #558; PRs #568-#570, #572; PR #556 (#552).

## Handover log

- **2026-10-02** — The FullProf half is on `main`. A `.pcr` now states what
  FullProf needs to run it: non-zero widths, the radiation, FullProf's own
  species spelling (`ZR+4`), and rietx's own f′/f″ as one LINE-12
  `nam f′ f″ 2` per X-ray `Typ`. *Done:* PR #568 (`a1861ddd`), merged as
  `430d7b52` by `/pr-review` after four rounds, closing #557 and #558. The
  reader reads LINE 12 back into `FullProfModel.dispersion`. It refuses a pair
  more than 0.01 e from plain Cromer-Liberman at the file's primary wavelength,
  because a `Structure` carries no dispersion. One function,
  `_dispersion_disagreement`, is that test for the reader and the writer
  alike, so the writer refuses at write what its reader would refuse
  (`io/CLAUDE.md` § Project writers). *Decision, the maintainer's, 2026-10-01:*
  an X-ray export under `source.dispersion = None` is refused. Nothing can
  state "dispersion declined" in a form the reader accepts, and a file that
  states numbers the fit then ignores would be worse. A carrier for the pair
  on the structure or instrument would lift both refusals. That is a new
  change, not filed yet. The same goes for a measured `Dispersion.overrides`
  pair beyond the tolerance. *Gotchas:* with no instrument the dispersion is
  resolved at the placeholder Cu Kα lines, so Eu and Ho (an edge between
  them) are refused, with a message naming `instrument=`. The `_anomalous`
  docstring has a stray "With" before "A pair the reader would refuse"
  (follow-up in the review). *Next:* the `Y3+` fallback-ion decision, which
  now applies to all four writers.

- **2026-10-01** — Three of the four species fixes are on `main`. A GSAS-II
  phase CIF now spells each species the way GSAS-II's importer reads it, or
  refuses it by name. A `.gpx` keeps the isotope its phase chose. A GSAS `.EXP`
  reads and writes the manual's `aasv_nnn` type. The FullProf half, #568, is
  held on review. *Done:* PR #569 (`6afa5fdb`, merged as `ecd5e96d`, closes
  #553), PR #570 (`cb1f0ca1`, `d8350249`, closes #554) and PR #572
  (`81e15696`, `cec8a8f2`, closes #555). Task 2 is met for these three: the
  tests pin the written spelling to the reporter's measured GSAS-II table
  (#569) and to the manual's grammar (#572), not to rietx's own reader. Task 3
  is settled by #556: an isotope species takes its element's f₀ on an X-ray
  histogram, so #570's `2H` and `58Ni2+` compile for both radiations. Task 4:
  no new diagnostic code; #570 and #572 extend the messages of
  `GSAS2_GPX_SPECIES_NORMALISED` and `GSAS_EXP_SPECIES_NORMALISED`, and the
  three skill copies agree. *Held:* #568 (review of 2026-10-01, three items).
  Its new radiation and width values pass no non-finite guard, a first-line
  weight of 0 raises a bare `ZeroDivisionError`, and a negative ratio
  desynchronises the file. A partly occupied site is written fully occupied
  (older than the PR). The "does not travel" list omits zero shift,
  displacement, absorption and anomalous dispersion. *Open, one decision for
  all four writers:* a species rietx computes as neutral by fallback (`Y3+`,
  per `scattering.detect_fallback`) is written as the ion by the GSAS-II, GSAS
  and FullProf writers, so the other program refines a different atom. That
  is the `Cu+` refusal's reason without its refusal. *Gotchas:* #572's writer
  half is still from the manual only, with no EXPEDT run. It now refuses the
  valence-labelled `Cval` and `Siva`, with a message calling them "not an
  element, an ion or an isotope". *Next:* #568's second round, then the
  `Y3+` decision.

- **2026-09-30** — created, from the 2026-09-30 issue triage (issues #553, #554,
  #555, #557, #558). Checked against the tree at `e3e6486a`: `write_fullprof_pcr`
  still writes `Zr4+`, `O2-`, `7Li` verbatim and the zero-width line;
  `write_gsas2_phase_cif` still writes `7Li`; the #555 reader snippet still
  gives `Ni258+`, `Li17+` and a `KeyError` for `NI_58`. The FullProf and
  GSAS-II outcomes are the reporter's, not reproduced here (neither program is
  installed). No open WP owns it: WP-1118, which wrote these formats, is ✅, and
  WP-1328 is magnetic interchange. The PRs cite the issues and no WP, so this
  file is where `/pr-review` finds the set.
