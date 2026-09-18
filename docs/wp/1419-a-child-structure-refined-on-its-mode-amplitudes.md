# WP-1419 — a child structure refined on its mode amplitudes

Milestone: v1.6 · Status: ⬜
Depends on: 1418 (the mode vectors: irreps, projection, isotropy subgroups);
1327 soft (the operator-list phase both would share)

## Goal

A commensurate superstructure at a zone-boundary k is refined as its parent
plus symmetry-adapted displacement amplitudes, one refinable amplitude per
free mode, with the child's coordinates derived when parameters are applied.
A child whose group no Hermann–Mauguin symbol names in its own cell is stated
by its operator list and labelled honestly, and a child cell whose metric
constraints are not ties or fixed angles is refined on the coordinates of
its invariant metric subspace. Every tabulated setting is bit-identical.

## Context

Issues #286 (2026-09-08, with its comment on unnamed child groups) and #293
(2026-09-09), and #256's rung M-10. Every number was measured on the
reporter's fork (`distortion-modes`, then `operator-list-phase` and
`operator-list-basis`), on a tree carrying working 1326–1329 and isotropy
machinery. Nothing below is on `main`, and both issues ask for a design
decision before any PR. This WP records the shape and the triage's answers;
the maintainer's decisions are the ones that count.

### The problem (#286)

A commensurate *nuclear* superstructure has no refinable home. The only
route is a child restatement with free coordinates, and that fails in a way
Rwp does not show. Ba₂FeSbSe₅ (Pnma, k = (½, 0, ½), a 71.9° superstructure
peak that appears below T_s ≈ 240 K and is not magnetic): the P2₁/m child
with 90 added free coordinates at 100 K reaches Rwp 0.0733 → 0.0661 at
ΔBIC −444. At 1.5 K the same freedom moves one Fe by 2.8 Å at 3.2σ and
reports `converged`. And 28 free child Biso *alone*, with no superstructure
and no moment in the model, take Rwp 0.118 → 0.076: they manufacture the
intensity the model is being tested for.

### The proposal, and three choices in it

Child coordinates as parent-derived base plus Σ A_ν e_νj, one refinable
amplitude per symmetry-adapted mode, the mode vectors from the isotropy
machinery (1418's M-6/M-7 with Γ_V). A `DistortionMode` block on
`Phase.distortion_modes` (irrep label, direction, k, per-atom mode vectors,
`amplitude: Parameter`) and a `displacive_statement(parent, k, irrep=,
direction=)` builder returning the child with its cell held, the isotropy
subgroup's symbol, one mode per free amplitude of the direction, and the
per-parent-site Biso tie list.

1. **The engine hook is the affine constraint block, not the forward
   model.** x = x⁰ + Σ A_ν e_νj is affine, and so is `ParameterTable`'s C,
   so an amplitude is a synthetic entry like a Wyckoff DOF and
   `model/forward.py` does not change. Exact. The cost is where the column
   lands: `_STRUCTURAL_PATH` matches one atom and an amplitude reaches many,
   so it falls to `_peak_chain_column`, 22 extra `phase_peaks` per Jacobian
   for 22 amplitudes. Measured: 1600 s for 4000 iterations on an 800-point
   pattern, stopping at `max_iter`. The fix is a `d_f2_d_xyz` contraction
   over a mode's per-atom coefficients, an analytic branch with its reach
   declared in `_column_extras` (root CLAUDE.md § Invariants).
2. **The amplitude's unit.** An irrep fixes a mode up to scale. The fork
   normalises each mode so unit amplitude moves the furthest atom by 1 Å,
   reports the normalisation on the evidence row, and bounds the amplitude
   at ±0.5 Å. The alternative, the irrep's own normalisation and a
   dimensionless amplitude, makes every reported number uninterpretable
   without the cell and the basis. AMPLIMODES (Perez-Mato, Orobengoa &
   Aroyo 2010) is the convention to compare against before choosing.
3. **"One amplitude per irrep direction" is not available.** Per Wyckoff
   orbit one direction carries several free amplitudes (6 on a general 8d
   site, 4 on each 4c site for S2(a,b) at this k; 32 across the seven Pnma
   orbits), and one orbit's free-index numbering has no relation to
   another's. The refinable object is the *basis* of a direction. The
   single-parameter statement is "one named mode", a weaker claim.

**The 65 K acceptance.** For each of the four common directions, the full
basis and then every single amplitude alone, against a parent reference
sharing its free set (N = 779):

| direction | child | modes | ΔBIC (basis) | χ²/pt at 71.9° | best single amplitude |
|---|---|---|---|---|---|
| reference | Pnma | — | 0 | 180.14 | — |
| S1(a,b) | P2₁ | 22 | +33.9 | 56.68 | ΔBIC +1.4, 168.05 |
| S2(a,b) | P2₁/m | 32 | −47.8 | 54.69 | ΔBIC −1.8, 173.65 |
| S3(a,b) | Pm | — | *refused* | — | — |
| S4(a,b) | P-1 | 22 | +50.9 | 42.93 | ΔBIC +29.4, 151.41, A = 0.311 ± 0.083 Å |

The 22-amplitude basis beats the 84-coordinate child on the window figure
(42.9 against 62.6) and on BIC (+50.9 against −444), which is the case for
the feature. It also shows the limits: no amplitude is individually
supported inside a full-basis fit (0/22, 0/32, 0/22) though six of S4's are
when refined alone, so the gain is collinear and
`DISTORTION_MODE_UNSUPPORTED` fires on all; ΔBIC is in the tens; and 42.9 is
3.5× the pattern's own GoF² of 12.2. The nuclear part of the magnetic group
(P2₁/m) is the worst of the three testable directions: the superstructure and
the magnetic order share the k and nothing else. (1417's caveat on ΔBIC at
N = 779 is mild; note it anyway.)

### The unnamed child group (#286's comment)

A superstructure at a zone-boundary k routinely lands in a group no
Hermann–Mauguin symbol names in the child cell (a parent glide's ½ along a
doubled axis is a ¼ in the child). The fork's `magnetic_supercell` symbol
check refused every such child, which removed S3(a,b) above and every P2₁
isotropy subgroup in a doubled cell: about a quarter of the candidate space.
The proposal: a phase may carry `symmetry_operations` (xyz triplets), and
`space_group` then becomes a **label** with a bracket as the marker,
`"Pm [unnamed in 2a,b,a+c]"`: the closest standard type, the cell that makes
the symbol wrong, and the fact that the symbol does not generate the group.
A plain symbol beside a list must generate it exactly, so a caller who states
the symmetry twice is told when the two differ instead of having one
silently preferred. No Wyckoff letter and no setting-assumed warning, both
withheld rather than empty. A `CHILD_GROUP_UNNAMED` diagnostic says which
operations the symbol got wrong and what is unavailable in consequence.

On `main`, every phase resolves its symbol through gemmi
(`crystallography/symmetry.py`), and 1327's `Phase.magnetic_symmetry` is the
one operator-list mechanism planned. One mechanism should serve both. This
is a `SCHEMA_VERSION` bump and the maintainer's decision.

### The metric subspace (#293)

`cell_constraints(sg)` states what a setting leaves free as `ties` and
`fixed_angles`, and is the one authority (root CLAUDE.md § Invariants). For
an operator-list phase the fork derives them from the rotation set: the
invariant subspace of the direct metric under Rᵀ·G·R = G, read off into the
same two dictionaries. Measured: the derivation reproduces the tabulated
constraints on ten named settings (cubic, tetragonal, hexagonal, both
trigonal axis choices, all three monoclinic unique axes, triclinic, P- and
C-orthorhombic) and lets 37 of the 39 unnamed children of an all-space-group
k-sweep build.

The two that refuse are the point. A doubling along two axes of a primitive
parent (Pnma at k = (0, ½, ½), Ba₂FeSbSe₅, Maier, Gaultois et al. 2021)
gives a child lattice that is centred; its primitive cell a, 2b, b+c is
oblique because b ≠ c, and no primitive basis of that lattice is
rectangular. The invariant subspace has dimension 4 (monoclinic), but two of
its relations have the form G₂₃ = G₂₂/2, c′·cos β′ = b′/2: linear in the
metric, a length times a cosine in (a, b, c, α, β, γ). The read-off returns
six free against a subspace of dimension four, and the fork refuses by name
rather than under-constraining. P6mm at k = (0, 0, ½) is the other case.

The proposal: for such a phase, refine the m coordinates of the invariant
subspace, G = Σ gᵢ·Bᵢ, and derive a, b, c, α, β, γ at parameter-apply time,
with esds propagated through the same map. `Cell` keeps its six `Parameter`s
as the visible quantities; a `MetricConstraints` (basis, m, the initial gᵢ)
sits beside `CellConstraints`, produced by the same derivation, reached only
when the two-dictionary read-off misses a relation (2 of 39 children, 0 of
the tabulated settings). The alternative, a centred child cell with a
centring vector so ordinary ties apply, needs centring support in orbit
generation and the reflection list for a case the primitive description
already handles everywhere but the metric. The metric form is also what a
superspace cell will want (#258).

**Triage answers (2026-09-15) to #293's three questions.** (1) Yes, as an
extension in the pattern 1419's amplitudes already use. (2) Beside
`CellConstraints`, since `ParameterTable` is its only caller. (3) Fallback
only, so every named setting is unchanged. One rule to carry from root
CLAUDE.md: the acceptance is that the true metric of each child *lies in
the span* of the derived subspace, never that the dimension is right, since
the transposed rotation set is a group too and passes any dimension count.

### Inherited

**2026-09-18 — the four rulings #286 asked for before the PRs are cut**, made
on `main` at `84eddb17` against a fork integration branch measured at
`b130bfd4`. Every number below is `main`'s own; the fork's were not reproduced.

- **Milestone: v1.6, opened today.** The seven magnetic WPs are § v1.6 and
  their `Milestone:` lines say so. The order stands as set on 2026-09-16:
  1418's M-6 and M-7 first, then 1327's verb with M-9, then this WP alone. The
  record's § Acceptance carries two rows belonging to this WP — the two lists,
  and the absolute amplitude with its seed — written at the open so they can
  fail.
- **The TOF half splits out of the chain, and #193 is the next fence decision
  rather than a refusal.** `main`'s v2+ fence holds neutron TOF behind #193,
  and 1418's § Non-goals already excludes it, so the two halves cannot ride
  into review in one chain. The magnetic half has a milestone and goes first.
  Three of #286's four questions are consequences of the merge and lapse with
  the split: the `read_gsas2_instprm` collision, `src/rietx/io/CLAUDE.md`'s 58
  lines of TOF rules, and where the TOF evidence lives. **The fence has been
  built through**, which is the case for reopening it: #193's public record
  stops at a 2026-09-05 scoping comment saying "no code and no request for a
  date", while the fork carries a working implementation reaching at least T-1
  and T-2 (`CompiledTOFModel`, `io/instrument_tof.py`, measured Δd/d and a
  GSAS-I PRCF1 corroboration). None of it is visible: the fork's public
  branches carry no TOF branch and the integration branch was not pushed. The
  ask returned on 2026-09-18 is that the TOF half be pushed as its own branch
  with the rungs it reaches named, and the milestone decision is then taken on
  the code.
- **`references/api.md` is split, not re-capped.** `API_INDEX_MAX_BYTES` is
  39 000 against a **40 kB** physical wall — Bash truncates above it to a 2 kB
  preview, which is the whole derivation — so a raise buys a few hundred bytes
  in front of a bar that cannot move. On `main` today the file is 36 280 B, up
  191 B since `b130bfd4`, so the chain's +3 374 B lands at roughly 39 650 B and
  654 B over. The seam is measured and it is § In (8 840 B) plus § Out
  (2 379 B), 31 % of the file and the two sections every reader and writer
  since WP-1118 has grown: `references/api-io.md` leaves `api.md` near 25 kB
  with 14 kB of room. It costs nothing in routing, because `SKILL.md`'s table
  already routes two of its three `api.md` rows to `§ In` and `§ Out` by name;
  those cells get shorter. The generator's `SECTIONS` table and `test_skill.py`'s
  `API_INDEX` single-file assumption are the two edits. Not the chain's to
  carry: it lands as a maintainer commit and the PRs rebase onto it.
- **`src/rietx/io/CLAUDE.md` gets a cap bump, not a second file.** A second
  always-loaded file under `io/` auto-loads only with a subtree, and the TOF
  readers sit beside the CW ones rather than under one, so the file would be
  loaded by nothing. `main` is at 484 lines against 485, so *any* io rule needs
  a bump — 1328's magCIF reader included, and that one is in this milestone.
  The bump is ordinary: make it in the commit that says so, with its paragraph
  in `docs/milestones/process.md` § The caps diary, as this session's own
  ROADMAP bump did.
- **Measured evidence does not go in a shipped milestone record.** Protocol
  rule 4 sends counts and timings to the WP handover entry; rule 5's milestone
  destination is the **in-flight** record's narrative, and § "Additions this
  milestone makes" is for release notes. v1.4 is shipped. So the Δd/d numbers,
  the GSAS-I PRCF1 corroboration and the Mantid GEM bin-width check belong to
  the TOF WP, which does not exist because TOF is fenced — they stay on the
  fork until it does.
- **`read_gsas2_instprm`, for when the fence moves: one reader on `Type`.**
  `.instprm` is one suffix under one program, and the file states which
  quantity it holds. `io/instrument_profile.py` already reads `Type`, already
  keys `CW_TYPES`/`HISTOGRAM_TYPES` as shared data, and already refuses a
  flight-time bank *by name* saying it "puts a different quantity on the x axis
  than PatternData holds". That refusal is the branch. A `_tof` suffix makes
  the caller choose from a suffix that is identical either way, which is the
  one thing § Dispatch says this subtree never does. If the two halves return
  different types the dispatch moves one level up and the answer discriminates
  on `kind`, never on shape (WP-1110); if a TOF profile and source can be union
  members, there is one return type and no question.

From the 2026-09-16 `/pr-review` round on issues #286 and #293, measured on
`main` at `f1d89cb0` and posted to both threads. Nothing here was measured on
the reporter's fork.

- **An amplitude's Jacobian column is exactly zero at A = 0, and so is the
  whole block.** The lost parent translation carries the mode field to its
  negative, so the pattern is an even function of the amplitude vector and its
  gradient at the origin vanishes for every mode at once. Measured on a toy
  zone-boundary superstructure (P1, a = b = 4 Å, c = 8 Å, an antiphase Sr pair
  at ¼ and ¾): dχ²/du is −2.9e-8 at u = 0 against −1.57e7 at u = 0.005, and
  χ²(u) is symmetric in u to 2.4e-15. Three consequences for the tasks below.
  A = 0 is a local *maximum* of fit quality along the mode, so an amplitude
  needs a seed rule of its own, in the shape `Stage.strain_seed` has for
  Stephens coefficients (`Stage.seed` reaches softplus entries only, and an
  amplitude is signed). The `d_f2_d_xyz` contraction is then a correctness
  question as well as a speed one: the toy escaped A = 0 only because the
  peak-chain column is a finite difference, so an exact analytic column would
  remove the ability to start from the parent. And the acceptance needs a case
  that *starts* at the parent, which the A = 0 control does not cover.
- **A single amplitude's sign is a domain label, not a measurement.** Two runs
  seeded at ±0.005 converged to ±0.01251 with Rwp agreeing to fifteen digits.
  Perez-Mato, Orobengoa & Aroyo (2010) §7 says the same from the other end: the
  lost translation maps the structure to its antiphase domain and flips the
  primary mode's sign alone. Only relative signs inside a basis are measured.
  Anything printing an amplitude states the convention, or it is the confident
  wrong singleton the FitReport rule forbids.
- **A mode cannot drive coordinates, and the DOFs it must drive re-base under
  it.** `tie` on `phases.0.atoms.0.z` is refused (*symmetry outranks a user
  tie*), so the expansion has to be written on `…dof.k`. A coordinate DOF is a
  displacement from the stored coordinate and returns to zero on every table
  build, while a variable keeps its value, so a variable driving one re-applies
  itself at every write-through verb: z ran 0.26 → 0.27 → 0.28 → 0.29 → 0.30
  over four unrelated `set_values` calls with `vars.A` fixed at 0.01. Seeded at
  0.005, an antiphase pair ended at +0.02251 and −0.01751, so the child stops
  being the symmetry-adapted structure the amplitude names. A second `fit()` on
  the same `Refinement` reported **A = 0.0** while the structure still carried
  u = 0.0200. **So an amplitude has to be absolute**, in the `Atom.aniso` and
  Stephens pattern, or the parent base has to be pinned in the mode record.
  The underlying defect is WP-1432's and is not this WP's to fix.
- **The reported quantity is the per-irrep amplitude, not the basis
  components.** AMPLIMODES normalises each mode within a primitive cell of the
  child lattice in absolute units (eq 3) *and* orthonormalises the basis
  (eq 4), the second of which is free across irreps and across parent orbits
  and needs an explicit orthogonalisation within one orbit's several free
  amplitudes. Eq (6)–(7) then give A_τ = (Σ_m A²_{τ,m})^½ with a unit direction
  {a_{τ,m}}. A_τ is basis-independent and the individual A_{τ,m} are not, which
  reframes § The 65 K acceptance's "0 of 22 individually supported": that test
  asked a question the arbitrary basis chose. Gate `DISTORTION_MODE_UNSUPPORTED`
  on A_τ, with its esd through the block covariance in `model/geometry.py`'s
  J·Cov·Jᵀ pattern.
- **§ The 65 K acceptance's S3(a,b) row is superseded.** #286's 2026-09-15
  23:53 comment retracts the refusal after fixing the ε bookkeeping, and the
  02:42 comment qualifies what replaced it: ΔBIC −179.1 → +21.0 → +57.0 at a
  4× cap, Rwp 0.0622 → 0.0547 → 0.0535, the 71.9° window 182.4 → 23.8 → 19.0,
  still 0/32 individually supported, still stopping on the iteration cap, and
  the 46.7° window getting *worse* (25.3 → 48.8 against 40.1 for the parent)
  while 57 ordinary Bragg positions lose more than 20 % of the 71.9° peak
  height. Neither "rejected" nor "supported" is safe for S3(a,b). Fold the row
  in rather than quoting the old one.
- **The declared operator list and the group are two different objects.** The ε
  fix reduces a displacive child's declared list to the sign-consistent
  stabiliser of its mode field, a strict subgroup. The full child group still
  has to drive reflection generation, multiplicities and the metric derivation
  of § The metric subspace, since reading `cell_constraints` off the reduced
  list refines the cell with more freedom than the crystal has. Whatever shape
  the operator-list phase takes with 1327, it carries both.
- **The bracketed label costs an audit.** `Phase.space_group` is read at 80
  sites in 23 modules, including five foreign-format writers (fullprof, gsas,
  gsas2, topas, recipe) and four GUI modules. gemmi raises on the label
  (`ValueError: Unknown space-group name: Pm [unnamed in 2a,b,a+c]`), so the
  bracket fails loudly, which is the safety property working. WP-1103's
  third-member rule applies: audit the readers before the field lands, and the
  exporters refuse rather than write a symbol they cannot honour.
- **The metric fallback is measured unreachable from any tabulated setting, and
  its trigger is a count comparison.** Over all 564 gemmi settings the
  two-dictionary read-off agrees with the invariant-subspace dimension 564/564,
  every span test passes (worst residual 7.5e-16) and `cell_constraints` refuses
  none. On the refusing side, a Pnma doubling at k = (0,½,½) rebuilt from the
  transform alone (a′ = a, b′ = 2b, c′ = b + c) gives G₂₃/G₂₂ = 0.5 exactly, and
  the read-off's shortfall depends on which parent operation survives: 4, 5 or
  6 free against a 4-dimensional subspace. A fallback keyed on "the read-off
  found nothing" misses the middle case. Detail and the three answers are in
  #293's thread.

## Non-goals

- Moment modes (SARAh-style basis-vector amplitudes): 1327 owns
  `Atom.moment`, and the projection engine is 1418's.
- Superspace and incommensurate k (#258, fenced).
- Deciding the schema of an operator-list phase apart from 1327.

## Tasks

- [ ] Decide, with the maintainer: the amplitude unit (Å-normalised against
      AMPLIMODES' convention), the engine hook (affine block first, analytic
      contraction when measured slow), and the operator-list phase shared
      with 1327.
- [ ] `Phase.distortion_modes` and `displacive_statement`; the child's
      coordinates derived through C; the Biso ties per parent site.
- [ ] `DISTORTION_MODE_UNSUPPORTED` and `CHILD_GROUP_UNNAMED` as
      `GuardFinding`s with `help.py` entries; their skill rows in
      `references/diagnostics.md` § 7 per #287's ruling.
- [ ] The metric subspace: `MetricConstraints` as the fallback, esds
      propagated, the span test on all 39 children and the ten settings
      bit-identical.
- [ ] The analytic column with declared reach, if the affine route is
      measured too slow; cross-backend rows.
- [ ] Manual Part 2: the mode expansion and the metric parameterisation with
      *Source* lines; Part 1 chapter.
- [ ] Tests, including a synthetic zone-boundary superstructure whose
      published amplitude is recovered, with PNGs to `tests/output/`.

## Acceptance

Ba₂FeSbSe₅'s S4(a,b) basis refines to the fork's figures within its esds;
every A = 0 control equals |det P|² × parent; the ten named settings and
every shipped fixture are bit-identical.

```sh
.venv/bin/python -m pytest tests/test_params.py tests/test_params_surface.py tests/test_distortion_modes.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issues #286 (and its comment), #293, #256 § M-10.
- Perez-Mato, J. M., Orobengoa, D. & Aroyo, M. I. (2010), *Acta Cryst.*
  A**66**, 558 (AMPLIMODES); Campbell, B. J., Stokes, H. T., Tanner, D. E. &
  Hatch, D. M. (2006), *J. Appl. Cryst.* **39**, 607; Kerman, S. et al.
  (2012), *Acta Cryst.* A**68**, 222.
- Maier, S., Gaultois, M. W. et al. (2021), *Phys. Rev. B* **103**, 054115
  (Ba₂FeSbSe₅).
- The fork: `mustachefeeling/rietx` at `distortion-modes` (31 tests) and
  `operator-list-basis`, as a reference implementation only.

## Handover log

- **2026-09-16** — a `/pr-review` round answered #286's three
  decide-with-the-maintainer items and #293's three questions, and posted both
  to their threads. The decisions are in § Inherited above, along with five
  findings measured on `main` that change how this WP is built: the amplitude
  block's Jacobian is identically zero at A = 0, a single amplitude's sign is a
  domain label, an amplitude must be absolute rather than a coordinate-DOF
  offset, the reportable quantity is AMPLIMODES' per-irrep A_τ, and the 65 K
  table's S3(a,b) row is superseded by the reporter's own retraction. The
  re-basing defect underneath the third one is WP-1432. Next: the session that
  picks this WP up prunes § Inherited into Context and Tasks, which is where
  the seed rule and the A_τ gate become checklist items.
- **2026-09-15** — created, from the 2026-09-15 issue triage (issues #286,
  #293). Checked against the tree: none of the named symbols
  (`propagation_vector`, `magnetic_supercell`, `distortion_modes`,
  `MetricConstraints`) exist on `main`; `cell_constraints` is the one
  authority as stated. Grouped because #293 is #286's cell one object over,
  and both consume 1418's engine.
