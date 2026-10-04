# WP-1527 — foreign files spell a species as the other program does

Milestone: unscheduled · Status: ✅ 2026-10-04 — every writer states the atom rietx computed, checked by the other program's reading rule; one-charge ions and Y³⁺ are tabulated, Y³⁺ handing over to neutral Y past 2.149 Å⁻¹
Track: Coming from another code
Depends on: — (WP-1118 closed 2026-09-16; its writers and readers are what this corrects)

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
   for it (#202's fallback) and GSAS-II reads carbon. *Superseded 2026-10-03
   by the maintainer's rule below: no writer refuses a species.*

**The maintainer's rule, 2026-10-03.** A writer neither refuses a species
nor writes an atom rietx did not compute. It writes the species rietx
computed, in the other program's spelling. Where rietx substituted the
neutral atom, the writer writes the neutral element and reports the
substitution. The rule holds for every writer. Decision 1 is untouched: an
isotope with no place in the file has no spelling that states what rietx
computed.

**Measured 2026-10-03: most substitutions are rietx's own lookup miss.**
`scattering.normalize_species` (`:117-123`) tries `Cu+` and then `Cu`, never
`Cu1+`. So `Na+`, `K+`, `Li+`, `Ag+`, `Cu+`, `Cl-` and `F-` all compute as
the neutral atom, though the Waasmaier-Kirfel table carries each ion as
`Na1+`, `Cl1-` and so on. A CIF with those labels reads with no diagnostic,
and at fit time `SPECIES_FALLBACK_NEUTRAL` says the ion is not tabulated,
which is false. pymatgen writes this spelling. Of the 111 ions in
*International Tables* Vol. C Table 6.1.1.3, the table lacks exactly one,
Y³⁺, and Table 6.1.1.4 gives its coefficients (4 Gaussians + c, fitted to
sinθ/λ ≤ 2 Å⁻¹). Ions in no table remain (`Fe+`, `S2-`, `Se2-` on this
table), and the writer rule is for those.

## Non-goals

- `Phase.propagation_vector` dropped by the same writers: #567, PR #571, which
  is WP-1328's.
- A `.gpx` writer. This build writes the `.instprm` + phase CIF pair.
- Running GSAS EXPEDT: no install. The writer half of #555 stays
  "unknown whether accepted" until someone does.

## Tasks

- [x] Review and land PRs #568 (.pcr), #569 (GSAS-II CIF), #570 (.gpx reader),
  #572 (.EXP) through `/pr-review`, each against its issue's reproduction
  (all four merged by 2026-10-02; handover log)
- [x] A test per writer that reads the written species through the *other*
  program's rule (the reporter's table), not through rietx's own reader
  (met for #569 and #572 first; for the `.pcr` on 2026-10-04, the file read
  by #558's measured FullProf lookup, both radiations)
- [x] Decide the reader's X-ray arm for an isotope from a foreign file
  (#554's note: land with #552 or refuse on the X-ray histogram) (settled by
  #556: an isotope takes its element's f₀ on an X-ray histogram)
- [x] Skill: a reference row for the refusal codes the PRs add, or "none" and why
  (none: no new code; #570 and #572 extend two messages, three copies agree)
- [x] A digitless one-charge ion reads as the tabulated ion: `normalize_species`
  tries `Na1+` between `Na+` and `Na`. It moves every fit that used the
  spelling, so it states what it changed (a diagnostic or a record field), and
  `SPECIES_FALLBACK_NEUTRAL` stops firing on those labels
- [x] Y³⁺ in the X-ray table, from *International Tables* Vol. C Table 6.1.1.4,
  with its source and its sinθ/λ ≤ 2 Å⁻¹ range beside the row
  (`scattering._ITC_IONS`; the DABAX file stays byte-identical) and in the
  manual Part 2's f₀ section (2026-10-04: checked against Table 6.1.1.3,
  0.0049 e at worst over s ≤ 2 Å⁻¹, and against cctbx `it1992` and GSAS-II
  `atmdata.py`, digit for digit)
- [x] Decide what Y³⁺ does past s = 2 Å⁻¹, where the fit leaves the free atom
  (−0.11 e at 2.5, −0.57 e at 3.0, negative beyond 3.85) and ITC sends the
  reader to the free-atom curve. Today rietx evaluates the fit everywhere, as
  cctbx and GSAS-II do. A switch at s = 2 would put a step in f₀ that a
  reflection crossing it during a stage would feel. (2026-10-04, the
  maintainer: neutral Y from 2.149 Å⁻¹, where the two curves meet, so no step.)
- [x] The maintainer's rule in every writer (GSAS-II CIF, GSAS `.EXP`, FullProf
  `.pcr`, TOPAS `.inp`): write the species rietx computed; where it
  substituted, write the neutral element and report it. The three
  digitless-ion refusals go (`topas.py:1568`, `fullprof.py:803`,
  `gsas2.py:1827`) (2026-10-04: `scattering.written_species` and
  `written_neutral_diagnostics`; one `*_SPECIES_WRITTEN_NEUTRAL` code per
  format)

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

### 2026-10-04 (3rd session) — Y³⁺ hands over to neutral Y; closed

**Closed.** The maintainer chose option (b) of the previous entry: past the
range its *International Tables* fit covers, Y³⁺ now scatters as neutral Y,
which is what the book advises and what every other ion in the table already
does out there. The switch sits where the two curves meet, so nothing jumps.
Only a pattern at a wavelength under 0.5 Å reaches it.

*Done*: `scattering._itc_handover` finds, once per ion, the first s past
2 Å⁻¹ where the ITC fit equals the neutral atom's Waasmaier-Kirfel curve
(Y³⁺: 2.1489 Å⁻¹, 5.107 e; the curves differ there by 2e-15 e). `f0` evaluates
both rows and picks with `xp.where` on s², so every backend takes the same
path; the Gaussian sum moved into `_gaussians` unchanged, so every other
species computes the same arithmetic. The module, `_ITC_IONS` and `f0`
docstrings, the manual's f₀ paragraph and the 1.7.0 note say so.
`test_y3plus_hands_over_to_neutral_y_where_the_two_curves_meet` fails without
the switch (14.2 e at s = 6); `test_the_hand_over_puts_no_step_in_f0`;
`test_y3plus_hands_over_to_neutral_y_under_jax_as_under_numpy` in
`test_backend_jax.py`, which skips on `[dev]` and passed in a throwaway
`[dev,jax]` venv (macOS arm64).

*Deliberately not generalised*: the writers still write `Y+3`/`Y3+`. No
format can state a curve that switches partway, and below 2 Å⁻¹ the fit and
the tabulated ion agree to 0.005 e; GSAS-II and cctbx evaluate the same fit
at every s, so past 2.149 Å⁻¹ they and rietx now differ by up to 0.57 e at
3 Å⁻¹.

*Review* (`/code-review high --fix` on this commit, ten findings). Fixed: the
manual takes the hand-over from the package (`Y3_HANDOVER_STOL` in
`conf.py`, rendering 2.149); `_itc_handover` brackets the *first* sign change
on a 1001-point grid before `brentq`, as its docstring promises (Y³⁺ moves in
the last bits only); the jax test runs under `backend.traced.active`; a
slope in a docstring (about 2 e per Å⁻¹, not 4); 3.86 → 3.85 above.
Declined, each for a reason:
- *Frozen-per-stage discreteness.* The switch is an elementwise `xp.where`,
  traceable and continuous; the residual keeps a kink, a slope change of
  0.15 e per Å⁻¹ at one s, as at FCJ's quadrature split. Freezing the choice
  per reflection at stage compile would trade the kink for a small step at
  each stage boundary.
- *A diagnostic per fit.* That was option (c), which the maintainer did not
  choose; the value is the table's, as every other ion's is, and the 1.7.0
  note states it.
- *The writers.* Named above as deliberately not generalised.
- *A Y³⁺ row in `test_cross_backend.py`.* No derivative path is new: nothing
  differentiates f₀ analytically, and `where` is in every backend's
  conformance suite.
- *Caching the neutral row.* A regex and a second Gaussian sum per Y³⁺ site
  per evaluation, microseconds.

### 2026-10-04 (2nd session) — the `.pcr` read by FullProf's rule; Y³⁺'s decision measured

Every foreign writer's species is now checked the way the other program reads
it. The FullProf file was the one still unchecked: a test now reads its atom
type the way FullProf.2k was measured to, on X-ray and neutron files alike,
and gets back the atom rietx computed in every case tried. No writer bug
turned up. One limit stays: #558 measured three X-ray ions in FullProf's
table, `ZR+4`, `O-2` and `CU+1`. So `NA+1`, `CL-1` and `Y+3` are checked for
their spelling, not for being in the table. The WP's last task, what Y³⁺ does past sinθ/λ = 2 Å⁻¹, is measured
below and waits on the maintainer.

*Done* (a lane, checked and re-run here, `0efea364`). In
`tests/test_projects_fullprof.py`, an oracle implements issue #558's measured
lookup: X-ray, element + sign + magnitude, case-free; neutron, b on the
type's first two characters unless a LINE-12 `NAM` names it.
`test_the_fullprof_oracle_reproduces_the_measured_lookup` holds the oracle to
every row of #558's table (16 X-ray, 17 neutron, the two LINE-12 rows) before
it judges anything. `test_fullprofs_own_lookup_reads_the_written_typ_as_rietxs_species`
writes a one-site file per label and resolves its type with the oracle, never
the module's reader: X-ray `Zr4+ O2- Cu+ Cu1+ Na+ Cl- Y3+ Mn Fe+`, each
with a LINE-12 dispersion row named as its type (added in review), neutron
the same nine plus `D 2H 7Li 7Li1+`. `Fe+` resolves to neutral Fe and carries
`FULLPROF_SPECIES_WRITTEN_NEUTRAL` on X-ray only. Pointing the oracle at the
IUCr `Zr4+` spelling fails 7 X-ray cases with the expected message. #558's
`NI60 0.28` → 2.807 fm row is left out of the self-test (0.28 × 10 is 2.8,
and the issue does not say where the 0.007 comes from).

*Measured* (`[dev]`, macOS arm64): `test_projects_fullprof.py` 218 → 241
passed (+23); the acceptance files with `test_portability`, 505 passed. The
fast selection after review, nothing else running: 8232 passed, 159 skipped,
in 2:32. The two added tests take 0.07 s together
(`tests.added_test_times`), so neither joins the slow tail. The tree is
current with `origin/main`; the full suite was not run, the change being a
test.

*Review* (`/code-review high --fix`, seven findings, no writer bug). Fixed:
the X-ray arm now checks the f′/f″ row is named as the written type (renaming
it fails the test); the entry's claim is narrowed to spelling for the three
ions #558 never measured; two docstrings; this block's counts. Declined: the
test's own parse of rietx's ion label repeats `scattering`'s regex, kept so
the oracle shares nothing with the module. The session's lane row has moved
since (+$39.29, 42 %); the record keeps the figure measured at handover.

**Y³⁺ past 2 Å⁻¹, for the maintainer's decision.** Computed from
`_ITC_IONS`'s coefficients against rietx's neutral Y (Waasmaier-Kirfel,
fitted to 6 Å⁻¹). The ITC fit minus neutral Y, in electrons: +0.013 at s = 2,
−0.11 at 2.5, −0.57 at 3, −2.86 at 4, −7.3 at 5, −14.2 at 6; the fit itself
crosses zero at s = 3.85. Over 0.6-2 Å⁻¹ the two differ by at most 0.061 e,
and the neighbouring ions the DABAX table fits to 6 Å⁻¹ stay close to their
neutral atoms over 1-6 Å⁻¹ (Rb⁺ 0.006 e, Sr²⁺ 0.013, Nb³⁺ 0.046, Zr⁴⁺ 0.155).
So past ~1 Å⁻¹ an ion scatters as its neutral atom, which is why ITC sends
the reader to the free-atom curve. **The two curves meet at s = 2.149 Å⁻¹**
(f = 5.107 e). Switching there to neutral Y puts no step in f₀, only a kink,
which the residual already tolerates elsewhere (FCJ's trapezoid). Where it
matters: s > 2 needs λ under 0.5 Å at high angle (λ = 0.1 Å reaches 2.6 at
30° 2θ); a Cu or Mo lab pattern stops at 0.63 or 1.36, and 11-BM's range at
0.92. Three options: (a) keep the fit everywhere, as cctbx and GSAS-II do;
(b) switch to neutral Y at 2.149 Å⁻¹, as ITC advises; (c) keep the fit and
report when a Y³⁺ reflection lies past 2. The session's recommendation is (b).

*Lanes* (`/wp-lanes` trial; `session_usage.py lanes`, whole session, five
lanes): `pcr-fullprof-rule` estimated 20, took 16 lane requests at 301K main
context, saved $0.34. `lamno3-acceptance` (WP-1327) estimated 40, took 89 at
235K, saved $3.15. The session's trial row in `docs/milestones/process.md` is
updated from three lanes to five: actual/estimated 1.91, saved $38.56, 41 %.
The replay's selective policy with this session's numbers (u = 0K, mo = 10,
d = 16K): −21 % over 423 sessions. At 300K main context and an 80K lane base,
a lane pays from about 28 requests, so a 20-request estimate sits under the
line and `pcr-fullprof-rule` was a near-miss.

*Next*: the maintainer's choice on Y³⁺; (b) is a few lines in
`scattering.f0` plus a manual sentence and a test at the crossing.

- **2026-10-04** — **The rule is in the code.** A structure labelled with
  `Na+` or `Cl-` now scatters as the ions it names, and Y³⁺ is tabulated. A
  file written for GSAS-II, GSAS, FullProf or TOPAS now states the atom rietx
  computed in that program's spelling. No writer refuses an ion label any
  more. Where rietx computes an ion as its neutral atom, the file says neutral
  and the writer reports it. An isotope a file has no place for still refuses.

  *Done*, as two lanes from a cleanup session, each checked and re-run here.
  `e24980d9`: `normalize_species` tries `Na1+` between `Na+` and `Na`, and
  `_ITC_IONS` carries Y³⁺ (a = 17.9268, 9.15310, 1.76795, −33.108; b =
  1.35417, 11.2145, 22.6599, −0.01319; c = 40.2602), checked against Table
  6.1.1.3's own Y³⁺ column (0.0049 e at worst over s ≤ 2 Å⁻¹, f(0) =
  36.00005) and against cctbx `it1992` and GSAS-II `atmdata.py`. The OCR'd
  copy dropped the minus signs on a4 and b4; only the negative values give 36
  electrons at s = 0. The DABAX file is byte-identical. The writers:
  `scattering.written_species` gives each label the species rietx computes,
  the four spelling functions call it, the three digitless-ion refusals are
  gone, and `write_topas_inp`/`write_fullprof_pcr` take `diagnostics=`.
  `Cu+` writes `Cu+1` (TOPAS), `CU+1` (FullProf X-ray, GSAS), `Cu1+` (GSAS-II
  CIF), and reads back as `Cu1+` through all four. Staged in the 1.7.0 notes.

  *Caps raised*, each with its reason beside it: `API_INDEX_MAX_BYTES`
  39 600 → 39 700 (`api.md` is 39 642 B with the two new keywords), and
  `src/rietx/io/CLAUDE.md`'s line cap 498 → 501 for the species exception to
  § Project writers' first rule. PR #690 (WP-1510) also sets
  `API_INDEX_MAX_BYTES` to 39 700, so whichever merges second resolves a
  one-line conflict in `tests/skill_caps.py`.

  *Measured* (`[dev]`, macOS arm64): `test_species_fallback.py` 72 passed
  (48 before); the four writer files 890 (872 before); with the registry,
  manual API, skill, docs and portability files, 1189 passed. Pinned numbers
  that moved: the fallback fixture is now As³⁺ (its value 0.0828 → 0.0996),
  and the skill row reads 11 of 111.

  *Final tree* (after the review's fixes; `[dev]`, macOS arm64, nothing
  else running): the fast selection 8165 passed, 159 skipped, in 2:36; with
  current `main` merged in (WP-1510's PR among it), 8200 passed, 159 skipped,
  in 3:23, the figure this branch merges at. The
  session's 20 added tests cost 0.22 s together (`tests.added_test_times`), so
  none joins the slow tail. The full selection was not run: no acceptance
  fixture carries a digitless ion label or Y³⁺ (a grep of `tests/data/*.cif`),
  and the writers touch no measured number, so none can move.

  *Lane trial* (`session_usage.py lanes 0433c291`; the session's three lanes,
  both of this WP's and WP-1504's round E, are measured here):

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | lane $ | in-session $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | 1504-option-E | 40 | 51 | 214K | 69K | 0K of 1061K | 15 | 20K | 4 | 0 | 2.42 | 8.65 | +4.55 |
  | 1527-lookup-and-Y3 | 35 | 84 | 411K | 70K | 0K of 3K | 6 | 15K | 0 | 0 | 3.83 | 10.49 | +5.86 |
  | 1527-writers-rule | 35 | 108 | 429K | 69K | 0K of 8K | 10 | 16K | 1 | 0 | 5.36 | 14.12 | +7.56 |

  One item kept: 1902-poor-reads-usable, est 10, 16 requests, at 322K. The
  session: main 243 requests, peak 461K, $21.32; lanes $11.61. Estimates ran
  2.00× short. The 1504 lane's window is not clean: it ran 68 minutes while
  this session worked other WPs, so its 15 main requests and 4 main edits
  include unrelated work (the edits were WP-1504's own file, the 1505 note
  and a docstring the lane suggested, none of them fixes to the lane's runs).
  The selective policy at these figures (`baseline --u 0 --mo 10 --d 16489`):
  −21 % over the 194 replayed sessions, −13 % with the lane assumptions
  doubled, and −29 % in the band above 450K that this session reached. Row
  added to `docs/milestones/process.md` § Lanes within a WP.

  *Review* (`/code-review high --fix`, `8aa52925`). Fixed: the TOPAS writer
  had neutralised a magnetic site's species (`Fe4+` → `Fe`), though TOPAS
  reads the magnetic form factor from it and rietx computes the moment from
  that ion, so a site with a moment keeps its ion (Fe⁴⁺ and Mn⁺ tested); the
  written-neutral warning names the label written (`D`, `57Fe`); the rule in
  `io/CLAUDE.md` names the valence labels GSAS still refuses. Declined: a
  warning for Y³⁺ past s = 2 (a task above, since it needs plumbing in the
  fit); writing the element in the case it was typed (`fe+` → `fe`, the
  writers' existing pattern); resolving each species twice per export
  (negligible).

  *Not done.* The GSAS writer still refuses valence labels (`Cval`, `Siva`,
  `gsas.py:1405`): no GSAS spelling states what rietx computes. No real
  program has read `NA+1` or `Na1+`; only `Cu1+`/`CU+1` were measured. `S2-`
  written as `S` was never run in a target program.

  *Next:* the `.pcr` writer's test through FullProf's own rule (task 2), then
  the Y³⁺ range decision.

- **2026-10-03** — **The open question is decided, and most of it turned out
  to be a lookup bug.** The maintainer's rule: a writer never refuses a
  species and never writes an atom rietx did not compute. While checking it,
  `Na+`, `Cl-`, `Cu+` and the other one-charge spellings turned out to compute
  as neutral atoms, though rietx's table holds each ion. Fixing the lookup
  removes most substitutions before any writer meets them. Y³⁺ is the only
  ion *International Tables* Vol. C carries and rietx's table does not.

  *Done* (a cleanup session over unowned in-flight WPs; docs only). Tasks 1,
  3 and 4 ticked from the earlier entries. The rule and the measurement are
  in Context. Three tasks added. *Measured* by calling
  `normalize_species`/`detect_fallback` on 15 labels, and by reading a
  two-site NaCl CIF labelled `Na+`/`Cl-`: no read diagnostic, both neutral.
  The ITC count compares Table 6.1.1.3's 111 ion headers, from `pdftotext` of
  the maintainer's copy, with the table's `#S` lines.

  *Next:* the lookup fix first, since it shrinks what the writer rule has to
  cover. Then Y³⁺, then the writers.

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
