# WP-1419 — a child structure refined on its mode amplitudes

Milestone: unscheduled · Status: ⬜
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

- **2026-09-15** — created, from the 2026-09-15 issue triage (issues #286,
  #293). Checked against the tree: none of the named symbols
  (`propagation_vector`, `magnetic_supercell`, `distortion_modes`,
  `MetricConstraints`) exist on `main`; `cell_constraints` is the one
  authority as stated. Grouped because #293 is #286's cell one object over,
  and both consume 1418's engine.
