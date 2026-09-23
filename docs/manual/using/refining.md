# Running a refinement

[](model.md) is the table of parameters a fit can move. This chapter is the
run itself: which call to make, what the intensities are allowed to do, how the
stages are chosen and settled, and how to watch a run or stop one that is going
nowhere.

[](concepts.md) explains why a refinement is staged and what order the presets
encode. Nothing here repeats that argument. What follows is the machinery around
it: the settings a caller chooses, and the record a run leaves behind.

## Two entry points, and where the settings live

`refine` runs one refinement and returns a `RefinementResult`:

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
import rietx as rx

result = rx.refine(data, structure, instrument, plan="mccusker_default")
```

`Refinement` is the same machinery kept open, so the model survives the fit and
can be edited, inspected and re-fitted:

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
ref = rx.Refinement(structure, instrument)
result = ref.fit(data)
```

The two take different arguments, and what goes where follows one rule. A
setting that decides how every fit in the object is computed belongs to the
constructor; a question asked of one pattern belongs to the call.

| Setting | Where it goes | Why there |
|---|---|---|
| `backend`, `solver` | the `Refinement` constructor (and `refine`) | they decide how every residual and Jacobian in that object is computed, so they belong to the object rather than to one fit |
| `history` | the `Refinement` constructor (and `refine`) | a tree spans many fits ([](history.md)) |
| `mode`, `plan`, `two_theta_limits` | `Refinement.fit` | one question asked of one pattern |
| `events`, `cancel` | `Refinement.fit` | they belong to a single run in flight |

So `Refinement.fit` takes no `backend=` or `solver=`. Choose those when you
build the object:

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
ref = rx.Refinement(structure, instrument, backend="numpy", solver="trf")
```

`backend` selects how the arrays are computed and `solver` selects the
least-squares driver. `numpy` and `trf` are the defaults and the answer for
almost every caller; [](install.md) covers what the optional backends buy and
what they cost, and `Capabilities.backends` and `Capabilities.solvers` report
what the build in front of you actually has.

`Refinement.result_` holds the most recent result, so a caller that fitted in
one place can read it in another without threading the return value through:

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
ref.fit(data)
print(ref.result_.statistics.rwp)
```

## Modes: what the intensities are allowed to do

`mode` decides where a reflection's intensity comes from.

| Mode | Intensities | Use it when |
|---|---|---|
| `"rietveld"` | computed from the structure | you have a structural model and want to refine it |
| `"lebail"` | extracted from the data, iteratively | you want the best profile fit a cell and symmetry can give, with no structure |
| `"pawley"` | refined, one per reflection | as Le Bail, but with the intensities as real parameters carrying esds |

The mode is more than a detail of the plan. It changes which rows of the
parameter table can move at all. Le Bail and Pawley force-fix every atom
parameter, every phase scale and every emission-line intensity, because in
those modes the data
does not constrain them. [](model.md) shows that as the `mode_fixed` hold
reason, and explains why it is kept distinct from a lock.

`RefinementResult.mode` echoes the mode a result was produced under, so a
stored result cannot be misread later:

<!-- api-doc: no-exec — it needs a result from the reader's own data -->
```python
result = ref.fit(data, mode="lebail")
assert result.mode == "lebail"
```

`Capabilities.modes` lists them, for a program that offers the choice.

## Choosing a plan at run time

[](concepts.md) introduces the seven presets and the order they encode. What
that section does not give a program is a way to offer the choice without
hard-coding a list that will rot the next time a preset lands.

`PLAN_PRESETS` maps each preset name to the function that builds it, and
`PLAN_INFO` maps the same names to a `PlanInfo` describing what the preset is
for. The entry is the builder rather than the plan: call it, then edit what
comes back. Each call returns a fresh `RefinementPlan`, so one caller's edit never
reaches another:

```python
import rietx as rx

assert set(rx.PLAN_INFO) == set(rx.PLAN_PRESETS)

info = rx.PLAN_INFO["lab_calibrate"]
print(info.title, info.description, info.modes, info.when_to_use)
```

| Field | Holds |
|---|---|
| `PlanInfo.title` | a short label, for a menu |
| `PlanInfo.description` | what the stages do, in order |
| `PlanInfo.modes` | the modes the plan is meaningful in |
| `PlanInfo.when_to_use` | the condition that should select it |

`PlanInfo.modes` is a tuple rather than a single mode because a plan can be
meaningful in more than one. `profile_only` is both the Le Bail plan and the way
to fit a profile in Rietveld mode without touching the structure.

The two registries are held in bijection by a meta-test, so a preset added
without a `PlanInfo` fails the suite rather than shipping as a preset nobody
can be told when to use. `Capabilities.plans` carries the same four facts
through the JSON surface as `PlanCapability`, keyed by `PlanCapability.name`;
[](agents.md) reads that side.

A plan also carries two settings of its own. `RefinementPlan.correlation_guard`
is the |ρ| above which a stage reports a correlated pair, default 0.98:

```python
import rietx as rx

plan = rx.RefinementPlan.mccusker_default()
assert plan.correlation_guard == 0.98

strict = rx.RefinementPlan(stages=plan.stages, correlation_guard=0.9)
```

Lowering it reports more pairs. It does not change the fit, because the guard
measures the fit rather than constraining it.

(strategy-harmonics)=
### Checking for monochromator harmonic contamination

No shipped preset frees an emission-line weight, so a declared λ/n harmonic
{eq}`pos-harmonic-d` needs a stage of your own ([](data.md)). Where to put it is
a strategy question:

```python
import rietx as rx

base = rx.RefinementPlan.mccusker_structural()
plan = rx.RefinementPlan(stages=[
    *base.stages,
    rx.Stage("harmonic", ["instrument.source.lines.*.weight"]),
])
assert plan.stages[-1].name == "harmonic"
```

Check for it whenever a monochromator's order is not filtered. The signature is
extra intensity at 2θ below the fundamental's peaks, because the harmonic
diffracts the same hkl from a smaller d, together with a GoF worse than a clean
histogram of the same specimen while Rwp may well look better. That asymmetry is
the whole diagnosis. Rwp is dominated by the strong peaks, and the harmonic's
are weak peaks sitting where the model has nothing, so GoF measures the misfit
against σ and Rwp mostly does not. A fit whose Rwp is respectable and whose GoF
is far from 1 is the case to suspect.

Free the weight last. It is a small fraction, it correlates with the background,
and both the scale and the displacement parameters can imitate part of it. Freed
early it takes intensity that belongs to the profile, and the record does not
show that it did. Freed after the profile and the scale have settled, it has
only the intensity nothing else claimed.

Read the fitted fraction as a property of the beam, or not at all. The
`HARMONIC_FRACTION` diagnostic reports it as a per cent of the fundamental with
its esd, because that is the number worth judging. A value far from a few per
cent is evidence that the model is absorbing something else through the line, an
unindexed impurity or a magnetic contribution or a background too stiff to
follow, rather than a measurement of the monochromator. Past 15 % the diagnostic
says so at `warning` level. A fraction that refines to nothing is a result too:
`HARMONIC_ABSENT` means the beam carries no measurable order-n component, as a
monochromator whose nth order is extinct must give, and the declaration can then
be dropped for one parameter fewer. A weight that was never
freed reports `HARMONIC_HELD` and must not be quoted at all.

Two related checks are model-free and run before any fit, and neither
substitutes for this one. `diagnose(data)` asks whether several of the strongest
reflections all carry a line at their Kβ or W Lα position at one common ratio,
and returns `ContaminationFlag`s, needing no structure. It answers "is the beam
leaking a known line?", and reports nothing below about 10 % of the parent. This
one needs a converged model and answers "how much intensity did the model
attribute to the harmonic once everything else had its chance?". It is the only
way to see a contamination whose peaks overlap the fundamental's too closely for
a peak search to separate.

## Is the unexplained intensity magnetic?

The sentence above ("an unindexed impurity, a magnetic contribution, a
background too stiff to follow") names magnetism as a cause of intensity the
model puts nowhere. `FitReport.satellites` is how you test it, and it needs
nothing you do not already have: a cell, a symmetry and a wavelength. A
satellite is a position. No moment, no magnetic form factor and no magnetic
symmetry enters, which is what makes this worth running *before* deciding
whether a magnetic model is worth building.

For each phase the arm sorts the positive residual peaks into the three places
one can be, and only the third is scored:

1. on a calculated line: a nuclear misfit, or a k = 0 structure whose
   intensity coincides with the nuclear reflections. This route cannot tell
   those apart;
2. on a reciprocal-lattice point the nuclear structure factor forbids: the
   k = 0 signature, and a *positive* result rather than an ambiguity, because
   no nuclear model right or wrong can put intensity at a systematic absence;
3. neither: the only peaks a satellite is needed to explain.

For those it generates the satellite positions Q = H ± k for a small,
enumerated set of candidate propagation vectors and counts how many land
inside the report's own validity radius of one. It publishes the whole ranked
list (never a singleton, the same rule indexing follows), because a k at the
top of it is a hypothesis worth testing and not an answer.

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
report = ref.report()
arm = report.satellites[0]
print(arm.note)
for c in arm.candidates[:3]:
    print(c.vector, c.matched, "of", arm.n_unexplained)
```

| Field | Is | Reads as |
|---|---|---|
| `SatelliteEvidence.phase_index` | which phase | position in `Structure.phases` |
| `SatelliteEvidence.radiation` | `"neutron"` or `"xray"` | read off the phase's own scattering amplitude, never assumed |
| `SatelliteEvidence.n_residual_peaks` | positive residual peaks before the sort | |
| `SatelliteEvidence.n_unexplained` | peaks at neither of the next two, i.e. the ones the ranking was scored against | zero means nothing needed a satellite, which is not a result about the specimen |
| `SatelliteEvidence.excess_on_nuclear_lines` | residual peaks that sit on a calculated reflection | a nuclear misfit or a k = 0 structure, and this route cannot separate them |
| `SatelliteEvidence.excess_on_absent_lattice_lines` | residual peaks on a reciprocal-lattice point the structure factor forbids | the k = 0 signature stated positively (see below) |
| `SatelliteEvidence.declared_k` | the k this phase already declares, or null | the arm still scores: "does another k explain the rest" is a question a declared one does not answer |
| `SatelliteEvidence.generator` | which candidate set was used | the default is the zone-boundary set; a caller may supply another |
| `SatelliteEvidence.candidates` | the ranked list, one `SatelliteCandidate` each | |
| `SatelliteEvidence.note` | the sentences above, rendered | always non-empty |
| `SatelliteCandidate.vector` | the plain spelling, `(0, 0, 1/2)` | what to type into `Phase.propagation_vector` |
| `SatelliteCandidate.name` | a positional label, `k1`, `k2`, … | stable within one generator, and nothing else |
| `SatelliteCandidate.cdml` | the CDML k-label | `None` today: those tables are a data source this package has not sourced, and a made-up label would look like CDML and disagree with it |
| `SatelliteCandidate.k` | the three exact rationals | |
| `SatelliteCandidate.matched`, `SatelliteCandidate.matched_fraction` | how many unexplained peaks this k accounts for | the ranking key |
| `SatelliteCandidate.worst_offset_deg` | the largest Δ2θ among those | null when none matched |
| `SatelliteCandidate.n_satellites` | satellite positions this k puts in range | a k that floods the pattern explains peaks by having a line everywhere |
| `SatelliteCandidate.star_size` | arms of the star of k | |
| `SatelliteCandidate.minus_k_distinct` | whether −k is a second vector | false when 2k is a reciprocal-lattice vector; the test respects centring, so on a C lattice (½ 0 0) is distinct from its negative and (0 0 ½) is not |

## A moment, stated and refined

When the answer to the previous section is "yes, and I know the structure",
state it. A moment is a site attribute (`Atom.moment`, a `Moment` block)
under a `MagneticSymmetry` declared on the phase as `Phase.magnetic_symmetry`. That shape is
deliberate: `qpa.weight_fractions` reads species, occupancy and multiplicity
and never sees a moment, so the classic trap of a separate magnetic phase
doubling the specimen's mass is unreachable here, and the nuclear and magnetic
contributions share the phase's one `Phase.scale`. A second magnetic scale is
the easiest route to a plausible fit and a wrong moment; it is not offered.

<!-- api-doc: no-exec — it needs a magnetic structure and a neutron pattern -->
```python
from rietx import Atom, Moment, Parameter, Phase

mn = Atom(label="Mn", species="Mn",
          x=Parameter(value=0.0), y=Parameter(value=0.0), z=Parameter(value=0.0),
          moment=Moment.from_values((0.0, 0.0, 4.6), "Mn2+", vary=True))
phase = Phase(name="MnF2", space_group="P 42/m n m", cell=cell,
              atoms=[mn, f_site], magnetic_symmetry="136.499")
```

The symmetry is an operator list, and the number is a way of getting one.
`MagneticSymmetry.operations` is the magCIF `_space_group_symop_magn_operation.xyz`
loop (xyz strings each carrying a time-reversal sign, `"-x,-y,z,-1"`) and
`MagneticSymmetry.centerings` the `_space_group_symop_magn_centering.xyz` loop.
That list is the model. A UNI, BNS or OG number in its place, as above, is
resolved through spglib's database and fills `MagneticSymmetry.bns_number`,
`MagneticSymmetry.og_number`, `MagneticSymmetry.uni_number` and
`MagneticSymmetry.setting` beside it; `MagneticSymmetry.symbol` and
`MagneticSymmetry.propagation_vector_parent` are records you may set yourself.
A Shubnikov *symbol* is not accepted: no dependency here parses one, and
guessing is how a fit lands under the wrong group. `MagneticSymmetry.group`
hands back the operator algebra if you want to inspect it.

The components are stated, the modulus is refined. `Moment.crystalaxis_x`,
`Moment.crystalaxis_y` and `Moment.crystalaxis_z` are the magCIF
`_atom_site_moment.crystalaxis_*` convention: components along a right-handed
basis of unit vectors parallel to the cell edges, in μ_B. That basis is
oblique whenever the cell is, so on hexagonal axes the moment (1, 1, 0) is
1 μ_B and not √2; `Moment.values` returns the three, and `Moment.vary` says
whether the block asks to refine. What actually enters the least-squares
problem is `phases.*.atoms.*.moment.dof*`: a modulus in μ_B, then one or two
angles inside the subspace the site symmetry allows;
{ref}`sec-moment-dofs` says why.

`Moment.ion` is the magnetic form-factor key (`"Cr3+"`, `"Ho3+"`), and it is
not `Atom.species`: the neutron scattering length is keyed by nuclide and
the form factor by oxidation state. An ion the table does not carry is refused
by name rather than mapped to a neighbour. `Moment.g` is the Landé factor;
leave it `None` for a 3d or 4d ion, where the spin-only g = 2 makes the ⟨j₂⟩
term of the dipole approximation vanish exactly, and set it for a 4f or 5f
one, where it does not: an absent g there is refused rather than defaulted,
because defaulting it silently drops a term worth tens of percent at high
angle.

Four declarations are refused where they are made, each because nothing later
can rescue them: a moment with no `Phase.magnetic_symmetry` (there is no
allowed subspace to refine in), a moment outside that subspace (the structure
and the group disagree), a moment on a site that also carries `Atom.aniso`,
and a moment that is free and exactly zero: |F_m|² is proportional to m²,
so its Jacobian column vanishes at the origin and the parameter cannot move.
Seed a physical estimate: 1-5 μ_B for a 3d ion.

The term reaches a `neutron_cw` histogram and nothing else. On an X-ray
histogram of a joint fit it is not computed at all, so the moment has no
gradient anywhere and the report says it was never observed; any other
radiation is refused by name.

## What the fit says about the moment

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
report = ref.report()
row = report.magnetic[0]
print(row.magnitude, row.approximation, row.unmeasured_directions)
```

| Field | Is | Reads as |
|---|---|---|
| `MomentEvidence.phase`, `MomentEvidence.atom` | which site | the names you gave them |
| `MomentEvidence.ion` | the form-factor key in force | |
| `MomentEvidence.magnitude` | the refined modulus, μ_B | its esd is on the `moment.dof0` row of `RefinementResult.parameters`: one writer per number |
| `MomentEvidence.magnitude_esd` | that modulus's esd, μ_B | copied from the same row, never recomputed; Bérar-Lelann-inflated like every esd here |
| `MomentEvidence.magnitude_from_components` | \|m\| recomputed from the components with the cosine metric | agrees with the line above to roundoff; disagreeing by 41 % on a hexagonal cell is what a Euclidean norm looks like |
| `MomentEvidence.crystalaxis` | the three components the DOFs imply | derived, so they carry no esd |
| `MomentEvidence.approximation` | which f(s) was used, named | ⟨j₀⟩ alone, or ⟨j₀⟩ + (2/g − 1)⟨j₂⟩ with g |
| `MomentEvidence.free_directions` | every direction DOF the site symmetry leaves free | `"polar"`, `"azimuth"` |
| `MomentEvidence.unmeasured_directions` | those of them the powder average did not determine | they are held, so they carry no esd at all |
| `MomentEvidence.supported` | whether |m| is above its floor and above three of its own esds | false means the data does not support a moment here (not a small one) |
| `MomentEvidence.note` | the sentence for whichever of those applies | |

A direction a powder cannot see is held, not fitted. After the orbit
average a cubic collinear structure's intensity does not depend on the moment
direction at all, and a uniaxial one measures only the angle to its unique
axis. Those are flat directions of the least-squares problem, and this rung
takes the rule WP-1301 takes for a phase the data cannot see: hold them, name
them in `StageResult.held`, and report what could not be measured rather than
a number nobody measured.

A moment the data does not support comes back unsupported, and the test is a
ratio. Refine the same model against a pattern above the ordering
temperature and the modulus goes to nothing, because |F_m|² ∝ m² and the only
way to reduce χ² is to remove the magnetic intensity. On real data it does not
land at exactly zero: on the Cr₂WO₆ tutorial pattern at 150 K it lands at
0.067 μ_B with an esd of 0.395, six times larger. So `MomentEvidence.supported`
is false when the modulus is below its floor or below three of its own
esds, and the note quotes which. At 4 K the same model gives 2.010 ± 0.046, a
ratio of 44, and the answer flips. That is the deliverable; a small moment with
a small esd would not be.

A peak on a forbidden lattice point is the k = 0 result, not an ambiguity.
A magnetic space group generally does not carry the parent's glide and screw
operations, so a k = 0 magnetic structure puts intensity at reciprocal-lattice
points where the nuclear structure factor is identically zero. No nuclear model
(right, wrong or badly refined) can put anything there, which makes
`excess_on_absent_lattice_lines` a positive statement about the specimen rather
than a caveat. Measured on the Cr₂WO₆ 4 K neutron pattern against a converged
150 K nuclear model of the same phase: the four strongest residual peaks are
the forbidden (0 0 1), (1 0 2) and two more, none of them carrying a tick, and
the same arm on the 150 K pattern counts zero.

Two cases where the ranking means nothing, and the arm says so.

*The excess sits on nuclear lines.* With k = 0 the satellites coincide with the
nuclear reflections, so a Le Bail extraction absorbs the magnetic intensity into
the nuclear intensities: a k = 0 structure and a nuclear misfit look alike by
this route, and no ranking can separate them. What does is a pattern of the
same specimen above its ordering temperature. `excess_on_nuclear_lines` counts
the residual peaks in that state; they are deliberately not scored.

*The histogram is X-ray.* Intensity at G ± k is then a superstructure
reflection. The positions are the same and the inference is not.

A good pattern can also score nothing, and that is a property of the candidate
set rather than of the data. The set is enumerated, not searched: the
zone-boundary vectors {0, ½}³ minus the origin, plus (⅓ ⅓ 0) and (⅓ ⅓ ½) on a
hexagonal or trigonal lattice, one representative per star. An incommensurate k
is outside it by construction, and so is any commensurate k it does not list.

Once a candidate looks worth testing, declare it (`Phase.propagation_vector`,
[](data.md)) and refine in Le Bail or Pawley mode: the satellites become rows
the extraction can put intensity on, and whether it does is the measurement.

## A displacive superstructure, stated as mode amplitudes

A superstructure at a zone-boundary k doubles (or quadruples) the cell, and
the child's asymmetric unit is that much larger. Refining its coordinates
freely is the trap: those parameters are not independent of each other, and
between them they can manufacture superstructure intensity out of nothing.
Measured on a Pnma selenide at 100 K, 90 added free child coordinates bought
ΔBIC −444 (they cost 444 BIC and were still preferred by Rwp), and one atom
moved 2.8 Å at 3.2σ while the fit reported `converged`.

The alternative is to refine the amplitudes of the symmetry-adapted modes
instead: child coordinates are the parent-derived base plus Σ A_ν e_ν, with one
refinable amplitude per irrep mode. `Phase.distortion_modes` is a list of
`DistortionMode` blocks (empty by default, and exactly off when empty): a phase
declaring none reaches the same arithmetic it always did, and one whose modes
are all at zero predicts the undistorted pattern bit for bit. The whole
statement is built for you:

<!-- api-doc: no-exec — it needs a parent phase that has been refined -->
```python
from rietx.crystallography.magnetic.supercell import (
    displacive_statement, seed_distortion_amplitudes)

statement = displacive_statement(parent, ("1/2", "0", "1/2"),
                                 irrep="S2", direction="(a,b)")
phase = seed_distortion_amplitudes(statement.phase, {"S2(a,b)-Fe1-0": 0.03})
ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
for target, source, scale, offset in statement.biso_ties:
    ref.tie(target, source, scale=scale, offset=offset)
```

The mode vectors come from
`rietx.crystallography.magnetic.isotropy.candidates` with
`kind="displacive"`, which enumerates the order-parameter directions of the
parent + k and, per direction, the family of displacement patterns its
isotropy subgroup allows: the parent + irrep + direction → structure
construction. `displacive_statement` refuses by name when a direction is not
carried by *every* orbit of the parent, and quotes the directions that orbit
does carry: a mode an orbit's representation does not contain does not exist,
and giving it a zero field would state a rigid sublattice nobody claimed.

| Field | Is | Reads as |
|---|---|---|
| `DistortionMode.name` | the mode's name, unique in the phase | what the report row and the diagnostic call it; a direction with several free amplitudes gives several modes and the name is what tells them apart |
| `DistortionMode.irrep_label`, `DistortionMode.direction` | the small irrep and the order-parameter direction | `"S2"`, `"(a,b)"` |
| `DistortionMode.k` | the parent propagation vector | three rational strings, exact, like `Phase.propagation_vector` |
| `DistortionMode.parent_site` | the parent site label the orbit came from | metadata; nothing derives from it |
| `DistortionMode.vectors` | e_ν: one fractional three-vector per atom of the phase | in the phase's own cell, in atom order |
| `DistortionMode.amplitude` | the refinable A, in Å | the free column, at `phases.*.distortion_modes.*.amplitude`; ±0.5 Å bounds, held at 0 by default |
| `DistortionMode.unit_displacement_a` | max‖L·e_ν‖ in Å, given a cell | 1.0 for a mode the builder made, which is what makes the amplitude an ångström |

The amplitude is in ångström by a stated convention, because an irrep fixes
a mode only up to a scale: the builder normalises each mode so unit amplitude
moves the furthest atom of that mode by exactly 1 Å. So A = 0.05 means the
furthest-moved atom moves 0.05 Å, and `DistortionMode.unit_displacement_a`
measures the convention back for a block that came from anywhere else.

Three things a mode statement will not let you do, each because nothing later
can rescue it:

- Free the child cell. Its parameters are non-linear functions of the
  parent's (c′ = √(a²+c²) and β′ = f(a, c) for 2a, b, a+c), so no affine tie
  can hold the relation, and a freed child cell walks away from the parent
  metric with nothing to say so. The rows are *locked*, so a broad
  `phases.*.cell.*` glob skips them, and a declared `vary=True` is refused.
  Refine the parent cell and rebuild the statement.
- Free an amplitude while every mode of the phase is at zero. Sending the
  whole amplitude vector to −A maps the child onto its own image under the
  translation the k-doubling lost, so |F|² is an *even* function of it and χ²
  is stationary at the origin: every column vanishes there at once. Seed one
  off zero with `seed_distortion_amplitudes`, which moves the amplitudes and
  the coordinates together: setting an amplitude alone changes nothing at
  all, because the base a mode is measured from is the stored coordinate with
  the current amplitude taken back out.
- Free an amplitude beside the coordinate DOFs of every atom it moves. A
  mode vector lies in the span of its atoms' allowed displacement directions,
  so the two are exactly degenerate: a rank-deficient Jacobian, not a
  correlation. One amplitude *instead of* the coordinates is the point.

And one thing to do rather than not do: tie the child's displacement
parameters per parent site. `DisplaciveStatement.biso_ties` is that tie list,
returned rather than applied because a tie is refinement state. On the same
selenide, 28 free child Biso alone took Rwp from 0.118 to 0.076 with no
superstructure and no moment anywhere in the model: they manufacture exactly
the intensity the mode is being tested for.

### More than one order parameter at once

A phase's modes are not limited to one (k, irrep, direction): a superstructure
whose 71.9° line does not fit under any single irrep at one k may need a
second irrep at the *same* k (a common-subgroup child) sharing the child cell.
`Phase.distortion_components` is a read-only view that groups
`Phase.distortion_modes` back into its components, one entry per distinct
(k, irrep_label, direction), computed rather than stored, so it costs no schema
field and groups a single-component phase into exactly one entry:

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
for component in phase.distortion_components:
    print(component.irrep_label, component.direction, component.k,
         len(component.modes))
```

`displacive_statement(parent, components=[(k, irrep, direction), …])` builds
the common-subgroup child directly: the intersection of every named
component's own isotropy subgroup, named the same way a single component's is
(a Hermann-Mauguin symbol when one reproduces it, else the bracketed
`Phase.symmetry_operations` label). One element behaves exactly like the
single-component call. It refuses more than it builds, and by name: a
zone-boundary little group is generally *grey* (the same spatial operation
carries both little-group characters ε = ±1), and when the shared
intersection is a strict subgroup of one component's own group, propagating
that component's mode through the smaller group can flip its sign on some of
its own atoms (measured, not hypothetical, on a real case). The builder
checks for exactly this and refuses instead of shipping it; pass components
whose own groups nest cleanly (or share nothing beyond the identity) instead.
Several k's sharing the parent cell (the incommensurate/Fourier route) has
no intensity path in this version; `fourier_statement` builds its schema and
reflection list only (see its docstring for the boundary).

## What the fit says about a mode amplitude

`FitReport.distortion` carries one `DistortionEvidence` per declared mode. The
arm needs no compiled model and no particular abscissa: every number in it is
a function of the declared modes, the phase cell and the parameter rows.

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
row = ref.report().distortion[0]
print(row.mode, row.amplitude, row.amplitude_esd, row.supported)
```

| Field | Is | Reads as |
|---|---|---|
| `DistortionEvidence.phase`, `DistortionEvidence.mode` | which mode | the names you gave them |
| `DistortionEvidence.path` | the amplitude's dot-path | the key that reaches the same number in `RefinementResult.parameters` or `SeriesResult.trajectory` |
| `DistortionEvidence.irrep_label`, `DistortionEvidence.direction`, `DistortionEvidence.k`, `DistortionEvidence.parent_site` | the order parameter the mode belongs to | copied from the block |
| `DistortionEvidence.amplitude` | the refined A, in Å | signed as refined, read as \|A\| (see below) |
| `DistortionEvidence.amplitude_esd` | its esd | copied from `RefinementResult.parameters`, never recomputed; Bérar-Lelann-inflated like every esd here |
| `DistortionEvidence.max_displacement_a` | Å moved by the furthest atom at unit amplitude | 1.0 by the builder's convention; anything else says the block was normalised elsewhere |
| `DistortionEvidence.displacement_a` | \|A\| × the line above | the largest atomic displacement the mode currently states, the number a crystallographer judges plausibility with |
| `DistortionEvidence.n_atoms_moved` | how many atoms of the phase the mode moves at all | |
| `DistortionEvidence.supported` | whether \|A\| is above two of its own esds | information about the basis, not the verdict (see the next section) |
| `DistortionEvidence.note` | the sentence for whichever of those applies | |

(sec-distortion-totals)=
## The verdict is the order parameter, not one amplitude

An irrep fixes its modes only up to an orthogonal basis of the direction:
AMPLIMODES (Perez-Mato, Orobengoa & Aroyo 2010, *Acta Cryst.* A66, 558)
normalises each mode in absolute units (eq 3) *and* orthonormalises the basis
(eq 4), and the second of those is free. So a single `DistortionEvidence`
amplitude is a number about a basis somebody chose: rotate the basis and it
moves, without the structure moving at all. What survives that rotation is
their eq (6)–(7) total,

$$A_\tau = \Bigl(\sum_m A_{\tau,m}^2\Bigr)^{1/2},\qquad
  a_{\tau,m} = A_{\tau,m}/A_\tau$$

and `FitReport.distortion_totals` carries one `DistortionTotal` per
(k, irrep, direction) component with it.

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
total = ref.report().distortion_totals[0]
print(total.irrep_label, total.direction, total.amplitude, total.amplitude_esd,
      total.supported, total.primary_mode, total.unit_direction)
```

| Field | Is | Reads as |
|---|---|---|
| `DistortionTotal.phase`, `DistortionTotal.irrep_label`, `DistortionTotal.direction`, `DistortionTotal.k` | which order parameter | |
| `DistortionTotal.modes`, `DistortionTotal.paths`, `DistortionTotal.n_modes` | the component's modes, in the phase's own list order | `paths` are the keys that reach the same numbers in `RefinementResult.parameters` |
| `DistortionTotal.amplitude` | A_τ, in Å | basis-independent, and non-negative by construction |
| `DistortionTotal.amplitude_esd` | σ(A_τ) through the block covariance, aᵀ·Cov(A)·a | `None` on a held component, on a loaded or replayed result, and where A_τ = 0 |
| `DistortionTotal.amplitude_esd_independent` | the same from the covariance diagonal alone | quoted beside it so the difference McCusker *et al.* § 10 warns about is visible; it is itself basis-dependent, and the block one is not |
| `DistortionTotal.unit_direction` | {a_{τ,m}}, in the sign convention below | where in *this* basis the order parameter points; empty when A_τ = 0, where it is undefined |
| `DistortionTotal.primary_mode` | the mode carrying the largest \|A\| | the one the sign convention fixes positive |
| `DistortionTotal.domain_sign` | +1, or −1 when the whole vector was negated to reach the convention | multiply `unit_direction` by it to recover the refined signs |
| `DistortionTotal.max_displacement_a` | Å moved by the furthest atom at unit amplitude | |
| `DistortionTotal.supported` | whether A_τ is above two of its own esds | the verdict, and what `DISTORTION_MODE_UNSUPPORTED` fires on |
| `DistortionTotal.note` | the sentence for whichever of those applies | |

Every A_{τ,m} exactly zero is the one degenerate case: A_τ = 0, the unit
direction is 0/0, and ‖A‖ has no derivative at the origin, so no esd can be
propagated through it. The row says so and carries no esd rather than a zero.

The sign of an amplitude is a domain convention, not a measurement. A
zone-boundary displacive mode enters a superstructure reflection with a
structure factor odd in A and the intensity is |F|², so negating the *whole*
amplitude vector gives the identical pattern: the parent translation the
k-doubling lost maps the structure onto its other antiphase domain. The
*relative* signs inside a component are measured (they say whether two
sublattices move together or against each other), so this package keeps every
sign and fixes the gauge instead: the component's primary mode is stated
positive and the rest are read relative to it, with `domain_sign` recording
which way the refined vector was turned.

An order parameter the data does not support comes back unsupported, and the
test is a ratio. The same evenness that makes the origin a stationary point
makes a distortion the pattern cannot see a *flat* direction, so the fit leaves
the amplitudes near wherever they were seeded and reports `converged` with
numbers in them. `DISTORTION_MODE_UNSUPPORTED` fires on a component with at
least one free amplitude whose A_τ is inside two of its own esds (a held
component is a statement you made, not a measurement to warn about), and its
suggestion is the model-selection question, because that is the half you can
act on: one order parameter either pays for itself in ΔBIC against the parent
phase or it does not. Rwp improves for any added parameter.

(sec-magnetic-width)=
## When the magnetic peaks are broader than the nuclear ones

The moment and the profile are not independent, and the way they are coupled is
the reason this section exists. A phase's nuclear and magnetic contributions
share one `Phase.scale` and one peak, so if the observed magnetic reflections
are *broader* than the calculated ones the residual under them has exactly one
route down: shrink the moment until the narrow calculated peak's height
matches the broad observed peak's. |F_m|² ∝ m², so the moment comes back low by
roughly the ratio of the two widths: the peak is in the right place with the
right shape, χ² falls, the fit converges, and no number in the result says what
happened.

`Phase.magnetic_lor_size` and `Phase.magnetic_lor_strain` are the two terms
that close it. Both are extra Lorentzian FWHM coefficients applied to the
magnetic component alone (1/cosθ and tanθ, the same two laws
`Phase.lor_size` and `Phase.lor_strain` carry), so the magnetic peak is drawn
broader than its nuclear neighbour at the same position, with the same scale
and every other correction unchanged. Physically the size term is Scherrer's
with the *magnetic coherence length* in place of the crystallite size:
antiphase and domain-wall boundaries, an incompletely grown order parameter
near T_N and disorder that couples to the exchange all cut it below the
structural one. Both default to exactly zero, which is off.

The turn-on order is not optional. Both the moment and the width lower the
calculated magnetic peak's height, so freed together from a cold start they
trade against each other and the answer is whichever pair the first step
happened to like. The order is the moment with the widths held at zero, then
the widths with the moment held, then both together, and it ships as a plan:

<!-- api-doc: no-exec — it needs a converged magnetic structure -->
```python
result = ref.fit(data, plan="magnetic_width")   # RefinementPlan.magnetic_width()
```

A stage list that frees a magnetic width in the same stage that first frees the
moment is reported as `STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT` before the
first stage runs: the confound is made by the stage list, so a report after
the answer it spoiled would be too late. The middle stage seeds the width off
its exact-zero softplus floor, which it has to: the map's slope at zero is
zero, so a term freed from its default has a dead column and never moves.
Measured on a synthetic k ≠ 0 supercell, the term freed from 0.0 with no seed
came back at 1e-12 with the moment still 14 % low.

While the terms are held at zero, the report says whether they are needed.
`MAGNETIC_WIDTH_UNMODELLED` reads the *shape* of the converged residual, not an
observed width (there is no observed-peak-width measurement in this package). A
calculated peak that is too narrow under a broad observed one leaves a residual
that is negative at the centre and positive in both tails, and that
centre-versus-tails split is compared against the same statistic at the
phase's nuclear-only reflections. Differencing the two is what makes it safe:
a wrong instrument profile, a wrong `lor_size` and a wrong background all move
both sets together and cancel, so only a width belonging to the magnetic
component survives. The message names the reflections it read and says which
way the moment would move (up).

Both terms are freed together, and which one carries the effect is a
property of the dataset. Measured on three: the synthetic k ≠ 0 supercell
below puts it all in the size term (0.245 ± 0.008 against a planted 0.25) with
the strain term dead; Cr₂WO₆ at 4 K likewise (size 0.101 ± 0.035, strain
0.010 ± 0.100); and Ba₂FeSbSe₅ at 1.5 K the other way round: the strain
term takes 0.37 ± 0.28 and the size term goes to zero with no esd at all. A
plan that froze one of the two would have been blind to whichever dataset it
guessed wrong about. The cost of freeing both is reported rather than hidden:
the live term's esd roughly doubles, because the two widths are collinear over
one pattern's θ range, and the last stage can come back `max_iter` rather than
`converged` when one of them is dead (a flat direction is what the solver
walks). The answer does not move (measured: 0.2451 → 0.2449 with Rwp identical
to five digits), and `MAGNETIC_WIDTH_UNMEASURED` names the dead term, so the
status has its explanation in the same result. Loosening the last stage's
`ftol` would buy the word "converged" and change nothing else on that dataset,
and would move the last digits of every answer on one where both widths are
live, so it is not done.

And when the terms are freed, the report says whether the data could see
them. They enter the magnetic component alone, so they are identifiable
exactly to the extent that the magnetic-to-nuclear intensity ratio *differs
across reflections*. Three regimes, and the report distinguishes them rather
than returning a number for all three:

* k ≠ 0. The magnetic supercell carries parent-forbidden reflections that
  are magnetic-only, and those measure the width directly. Measured on a
  synthetic Pnma → P2₁/m `2a,b,a+c` supercell: a planted 0.25° comes back
  0.245 ± 0.008 with both moments inside 0.9σ, while the same pattern refined
  with the term held returns them 3-4 esds low and fires the diagnostic. On
  real data it can be *weakly* determined and still matter: see the
  Ba₂FeSbSe₅ case above, where the term is 1.31 esd and carries 0.18 μ_B.
* k = 0, every magnetic reflection also nuclear. Weakly determined at best.
  Measured on the LaMnO₃ 50 K tutorial pattern: `magnetic_lor_size` 0.029 with
  an esd of 0.061, an esd larger than the value, and Rwp unmoved in the
  fourth digit. On Cr₂WO₆ at 4 K, which does carry magnetic-only reflections on
  the parent's absences, it reaches 0.101 ± 0.035, still short of three esds.
* Paramagnetic. No magnetic component, so the column is flat.

An unmeasurable width comes back as `MAGNETIC_WIDTH_UNMEASURED`: |value| below
three of its own esds, the same ratio `MomentEvidence.supported` uses for a
moment. Note what it is *not*: an absent esd. `ParameterTable.unmeasured_rows`
fires on an exactly zero column, and this column is not zero: the magnetic
component really is broadened and the pattern really does change; what fails is
the separation.

And "unmeasured" is not the same statement as "droppable". The plan fits the
moment twice (once at the off state in step 1, once with the widths free in
step 3), and the difference between those two rungs is the measurement this
whole term exists to make. `MAGNETIC_WIDTH_MOVED_MOMENT` fires when releasing
the widths moved the moment by more than the moment's own error bar, and it can
fire *beside* `MAGNETIC_WIDTH_UNMEASURED` on the same term: on Ba₂FeSbSe₅ at
1.5 K the strain term is 0.370 ± 0.282 (1.31 esd, so unmeasured) while the tied
moment goes 3.908 ± 0.128 → 4.085 ± 0.180, a shift of 1.39 of the tighter esd,
and the Q-profile minimum moves 5.60 → 5.75 with the paper's 5.84 inside its
own 1σ. Unmeasured there means correlated with the moment, not absent, and
holding the term at zero puts the moment 0.18 μ_B low again. When both codes
fire, quote the released moment and report the width as an upper bound
(value + esd) rather than as a coherence length; the support row's own wording
changes to say so.

Two things this deliberately does not offer. There is no Gaussian partner
(magnetic coherence broadening is Lorentzian in shape, and a field nothing frees
is a claim nothing tests), and there is no magnetic lattice *offset*: magnetic
peaks in the wrong place are a different freedom, and rietx answers that one
with two nuclear phases.

## Determining a magnetic structure: `solve_magnetic`

The two sections above are the halves of a determination done by hand: the
satellite arm says *whether* there is something magnetic and roughly where,
and a stated `Phase.magnetic_symmetry` refines one model you already chose.
`solve_magnetic` is the call that does the middle: enumerate the models, refine
one per class the powder cannot separate, rank them by a criterion that is not
Rwp, and abstain when the top ones tie.

It is {ref}`provisional by declaration <provisional-by-declaration>`: the chain
is settled and the ranking criterion is expected to move.

<!-- api-doc: no-exec — it needs a converged neutron refinement -->
```python
import rietx as rx

ref = rx.Refinement(nuclear, instrument)
ref.fit(data, plan="mccusker_structural")

solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
print(solution)                       # the classic table
if solution.verdict == "solved":
    print(solution.best.bns_number, solution.best.moments[0].magnitude)
solution.write_magcifs("candidates/")  # one magCIF per class, on request
```

What it does, in order.

1. k: WP-1326's arm sorts the positive residual peaks. Peaks on a
   reciprocal-lattice point the nuclear structure factor *forbids* are the
   k = 0 signature and short-circuit everything else: they are never scored
   against a candidate vector, because that excess is not evidence about a k.
   Otherwise the unexplained peaks are scored against the enumerated candidate
   set and the top vector is taken, with the rest kept in
   `MagneticSolution.k_candidates` as the hypotheses this call did not test.
   `MagneticSolution.k_route` records which of the routes it was. Pass `k=` to
   state the vector instead when it is known from a single crystal.
2. candidates: for each named site, every order-parameter direction of
   every small irrep with a non-zero multiplicity, as a magnetic space group in
   its own cell. A k ≠ 0 candidate is stated through its magnetic supercell,
   with the anti-centring applied as a *constraint* on the moment DOFs and not
   only as a seed; `MagneticTrial.anti_translation_drift` is how far the
   refined structure travelled from the group it declares, and it should read
   zero.
3. one trial refinement per powder-equivalence class: never one per
   candidate. The members of a class are models this pattern, to
   `MagneticSolution.d_min`, cannot tell apart; refining each of them would
   produce N copies of one answer and invite you to rank them. They are named
   instead, in `MagneticTrial.members`, and the inability to separate them is
   the finding.
4. ranking: the answer is a `MagneticSolution`; its
   `MagneticSolution.criterion` states the rule in full and the fields below
   carry every number the rule reads.

The criterion, and why not Rwp. A candidate with more free amplitudes
always reaches a lower Rwp, so ordering by Rwp orders by freedom. The primary
key is `MagneticTrial.delta_bic` against a nuclear reference refined under the
*same* stage list minus the moment paths, so the only difference between the
two models is the moment block and `n_added` is exactly
`MagneticTrial.n_moment_parameters`. That is where parsimony enters: the
`−n_added·ln N` term charges every extra amplitude, which is why a nested
triple of groups reaching one profile comes out smallest-group-first. Behind it
is `MagneticTrial.r_magnetic`, a profile R over only the channels the
nuclear model puts nothing on, where 1 means "explains none of the intensity
there" and 0 means "explains all of it", a number a whole-pattern Rwp,
dominated by the nuclear lines, cannot give you. Behind that, parsimony as a
literal tiebreak. A supported moment is a precondition, not a column: a trial
whose every moment fails WP-1327's null test cannot win however good its ΔBIC,
and when none of them has one the verdict is that there is nothing to solve.

Several magnetic sites means several starts. A moment stage over more than
one site is not convex, and the flat equal-magnitude seed can land in a minimum
that is *provably* not the optimum: a three-amplitude fit reaching a worse Rwp
than its own one-amplitude submodel, which cannot happen at a true minimum.
Released from the one-site solution the same model reaches a better point, on a
different site. That is fatal to a ranking and not merely to a fit: candidates
compared at such points are compared at whatever minimum their seed fell into,
so the ΔBIC ordering would measure the seed. Every class with more than one
magnetic site is therefore refined from each one-site start (the other sites'
moments absent, not small, because seeding them small does not escape)
and then released, with the best converged minimum reported.
`MagneticTrial.n_starts`, `MagneticTrial.n_minima` and `MagneticTrial.start`
are that sweep made visible, and a multimodal class says so in
`MagneticSolution.caveats`.

A stage entry that frees nothing is reported. `Stage` accepts a free-list
glob matching no parameter silently, and a term this histogram's forward model
does not read returns the same Rwp to ten digits and the same parameter count
either way. In a ranking that
makes the compared models differ from the ones the plan describes, so
`solve_magnetic` checks what the stages actually froze and puts any dead glob
in the caveats. Its own defaults are axis-shaped and produce none.

The abstention is a result. Classes whose ΔBIC lies within
`MagneticSolution.tie_width` of the leader's are tied; `MagneticSolution.tied`
names them and `MagneticSolution.verdict` reads `"abstained"`. The default
width is 6.0, "strong" on the Kass & Raftery scale, the same bar peak fitting
uses to keep an added component. So is the other abstention this workflow
makes: a cubic collinear structure has one class and a modulus the data
measures well, and a direction the powder average cannot determine at all,
which comes back as a held DOF in `MomentRow.unmeasured_directions`. That is
the answer, not a failure to find one.

One refusal: a non-neutron histogram, by name. Everything else is reported.

| Field | Is | Reads as |
|---|---|---|
| `MagneticSolution.verdict` | `"solved"`, `"abstained"` or `"nothing to solve"` | the third is an answer about the specimen |
| `MagneticSolution.reason` | why, in a sentence | always non-empty |
| `MagneticSolution.criterion` | the ranking rule, stated | the same string every run |
| `MagneticSolution.best` | the winning `MagneticTrial`, or `None` | `None` for every verdict but `"solved"` (an abstention has no winner) |
| `MagneticSolution.phase`, `MagneticSolution.space_group` | which phase was solved | |
| `MagneticSolution.k` | the propagation vector used, as three rationals | `None` when the workflow abstained before choosing one |
| `MagneticSolution.k_route` | how it was chosen | `"forbidden lattice points"`, `"satellite ranking"`, `"given by the caller"`, or the abstention's own name |
| `MagneticSolution.k_reason` | why, in a sentence | separate from `MagneticSolution.reason`, which is the *verdict's* (a solved determination still has to say how it got its k) |
| `MagneticSolution.k_candidates` | the ranked vectors, `(spelling, matched, satellites in range)` | empty when the arm did not run |
| `MagneticSolution.sites` | the sites that were given a moment | |
| `MagneticSolution.n_residual_peaks` | positive residual peaks of the nuclear fit | before any sorting |
| `MagneticSolution.n_on_nuclear_lines` | those on a calculated reflection | a nuclear misfit or a k = 0 structure; deliberately not scored |
| `MagneticSolution.n_on_forbidden_lattice_points` | those at a systematic absence | the k = 0 signature, stated positively |
| `MagneticSolution.n_unexplained` | those at neither | the only ones a propagation vector is needed for |
| `MagneticSolution.trials` | the ranked list, one `MagneticTrial` per class | published whole: refusals and unsupported models included |
| `MagneticSolution.tied` | the class indices inside the tie width | one entry when the verdict is `"solved"` |
| `MagneticSolution.tie_width` | the ΔBIC below which two classes are not ranked | 6.0 by default |
| `MagneticSolution.d_min` | the d limit the equivalence classes are a statement about | a class is a claim about *a powder pattern to a limit* |
| `MagneticSolution.nuclear_rwp`, `MagneticSolution.nuclear_gof` | the reference fit every ΔBIC is against | |
| `MagneticSolution.nuclear_r_magnetic` | the reference's own magnetic-only R | ≈1 on a nuclear model that explains none of it: the scale every `MagneticTrial.r_magnetic` is read against |
| `MagneticSolution.n_magnetic_channels` | how many channels that region has | zero makes `r_magnetic` `None`, not 0 |
| `MagneticSolution.caveats` | what the run wants you to know | includes ΔBIC's raw-channel-count N |
| `MagneticSolution.write_magcifs` | writes one magCIF per refined class and returns the paths | nothing is written unless you call it or pass `cif_dir=` |
| `MagneticSolution.k_trials` | one `KTrialSummary` per propagation vector actually refined | length 1 unless a runner-up k was within the satellite step's own offset margin of the winner (`k_trials=` option, default 2) |
| `MagneticSolution.diagnostics` | structured diagnostics beside `MagneticSolution.caveats` | `K_VECTOR_UNSEPARATED` (info) and `MAGNETIC_SUBGROUP_PREFERRED` (warning) among them |
| `MagneticSolution.margin` | the winner's ΔBIC over the best *other eligible* class | `None` on an abstention or when there is no second eligible class (never negative). Diffing `trials[0]` against `trials[1]` by hand can be negative, when `trials[1]` is not itself eligible |
| `MagneticSolution.subgroup_audit` | the winner's own maximal magnetic subgroups at its k, each refit from its solution and compared by ΔBIC (one `SubgroupAudit` per subgroup found) | empty when the k was not zero (not warm-started yet) or none of the classes already enumerated is a genuine subgroup |
| `MagneticSolution.subgroup_note` | one sentence: which subgroup beat the winner and by how much, that none did, or why the audit was not attempted | always set on a solved verdict |
| `SubgroupAudit.bns_number`, `SubgroupAudit.label` | which subgroup this row is | |
| `SubgroupAudit.n_moment_parameters` | its own moment DOF count | more than the winner's, since it is a subgroup |
| `SubgroupAudit.delta_bic_over_winner` | ΔBIC with the *winner* as the restricted model | positive favours the subgroup; `None` when it refused |
| `SubgroupAudit.status`, `SubgroupAudit.refusal` | `"refined"` or `"refused"`, and why | mirrors `MagneticTrial.status`/`.refusal` |
| `KTrialSummary.k` | the propagation vector this row is about | as three rationals |
| `KTrialSummary.matched`, `KTrialSummary.worst_offset_deg` | the satellite step's own score for this k | `None` on a route with no such scoring (a given `k=`, or the k = 0 signature) |
| `KTrialSummary.best_delta_bic` | the best eligible class's ΔBIC for this k | `None` if this k reached no eligible class |
| `KTrialSummary.n_refined` | how many of this k's classes reached `"refined"` | |
| `MagneticTrial.class_index` | which powder-equivalence class | stable within one run |
| `MagneticTrial.representative` | the irrep and direction that was refined | the smallest family of the class |
| `MagneticTrial.members` | every candidate in it | the models the powder cannot separate; more than one is the finding |
| `MagneticTrial.site` | the site whose representation produced it | |
| `MagneticTrial.irrep`, `MagneticTrial.direction` | the labels | e.g. `S2`, `(a)` |
| `MagneticTrial.bns_number`, `MagneticTrial.uni_number`, `MagneticTrial.msg_type` | what spglib recognised the operator list as | `"unidentified"` and `None` are honest, not errors |
| `MagneticTrial.free_amplitudes` | amplitudes the representative site's family has before any data is looked at | per site: on a parent with several magnetic sites this is not the model's parameter count, and the ranking's parsimony key reads `MagneticTrial.n_moment_parameters` instead |
| `MagneticTrial.determinable_amplitudes` | how many of them a powder to `d_min` can determine | the deficit is the flat directions |
| `MagneticTrial.status` | `"refined"` or `"refused"` | |
| `MagneticTrial.refusal` | the message, when refused | e.g. a magnetic orbit that cannot cover the nuclear one |
| `MagneticTrial.rwp`, `MagneticTrial.gof` | the trial's own agreement | context, never the ranking key |
| `MagneticTrial.delta_bic` | the primary key | positive favours the magnetic model |
| `MagneticTrial.r_magnetic` | the magnetic-only R | compare against `MagneticSolution.nuclear_r_magnetic` |
| `MagneticTrial.n_moment_parameters` | moment DOFs left free, ΔBIC's `n_added` | |
| `MagneticTrial.n_free_parameters` | the whole free count | |
| `MagneticTrial.moments` | one `MomentRow` per site that carries one | |
| `MagneticTrial.held` | the DOFs the stage held | a direction here was not measured |
| `MagneticTrial.supported` | whether any site's moment survived the null test | false disqualifies the trial from winning |
| `MagneticTrial.anti_translation_drift` | how far a supercell refinement left its own group, μ_B | zero is the pass; `None` for k = 0, where there is no anti-centring |
| `MagneticTrial.n_starts` | how many seeds the moment stage was started from | one per magnetic site plus the flat one; 1 when the class has a single site |
| `MagneticTrial.n_minima` | how many distinct minima those starts found | more than one is a fact about the candidate: its moment problem is multimodal and one seed would have reported another answer |
| `MagneticTrial.start` | which start won, named | `"flat"` or `"<site> only, then released"` |
| `MagneticTrial.label` | what the table prints | BNS plus irrep and direction |
| `MomentRow.label`, `MomentRow.ion` | the site and its form-factor key | |
| `MomentRow.magnitude`, `MomentRow.esd` | \|m\| in μ_B and the esd of the modulus | the components carry none by design |
| `MomentRow.sigma` | \|m\| in units of its own esd | WP-1327's ratio; `None` without an esd |
| `MomentRow.crystalaxis` | the three components the DOFs imply | |
| `MomentRow.supported` | the null test's verdict for this site | |
| `MomentRow.unmeasured_directions` | direction DOFs the powder average did not determine | non-empty is a result about the measurement |
| `MomentRow.paired_with` | the other site's path this modulus is powder-degenerate with | non-empty when the fit's own correlation showed the two are not separately determined |
| `MomentRow.paired_magnitude`, `MomentRow.paired_magnitude_esd` | the quadrature sum sqrt(sum m^2) over the pair and its esd from the measured covariance | this, not `MomentRow.magnitude`, is the number the powder measures for the pair; `None` when `paired_with` is empty |

## How hard each stage is converged

`RefinementPlan.intermediate_ftol` is the termination tolerance every stage but
the last is solved at, and it defaults to `1e-6` against the solver's own
`1e-9`. `RefinementPlan.stage_ftols` is where that becomes a per-stage answer:

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
assert plan.intermediate_ftol == 1e-6

ftols = plan.stage_ftols()
assert set(ftols[:-1]) == {1e-6} and ftols[-1] is None
```

Three sources decide a stage's tolerance, in this order. A stage that declares
its own `Stage.ftol` is solved at it. The last stage takes `None`, meaning the
solver default, because it is the one that produces the answer. Every other
stage takes `intermediate_ftol`. A one-stage plan is therefore all endpoint and
nothing is loosened, which a warm series pattern collapsed to a single stage and
the indexing validation fit both want.

`StageResult.ftol` reports what each stage was actually solved at, so a result
says which schedule produced it without the plan beside it.

### What the loosened schedule costs

Stages are cumulative: each one frees its globs on top of everything already
free, so a parameter an early stage stopped short on keeps refining in every
later stage, and the last stage, at `1e-9`, polishes all of them together. That
is why stopping intermediate stages early moves the answer so little, and it
holds for any plan this runner runs rather than only for the presets.

Measured on the benchmark cases of `examples/bench_refinement.py` (`[dev]`
venv, darwin/arm64, 2026-08-22, best of three runs on an idle machine), against
the same plans with `intermediate_ftol = None`:

| case | evaluations | wall clock | largest shift | QPA |
|---|---|---|---|---|
| nac | 47 → 39 (1.21×) | 0.38 → 0.34–0.35 s | not measured | single phase |
| cpd-1a | 408 → 270 (1.51×) | 2.02–2.04 → 1.52 s | 0.027 esd, a width term | within 0.0014 wt % |
| cpd-2 | 533 → 329 (1.62×) | 3.37–3.43 → 2.27–2.28 s | 0.001 esd, a background coefficient | within 0.0003 wt % |
| trigger | 360 → 232 (1.55×) | 8.63–8.65 → 5.67–5.70 s | 0.001 esd, outside one degeneracy | within 0.0001 wt % |

Rwp agrees to five decimals or better in every case.

The degeneracy is the trigger case's instrument `x` against every phase's
`lor_size`, which moves 1.4 esd. Those parameters are exactly degenerate
(Lorentzian FWHMs add, and both terms are size-like in θ), and the measurement
shows it: `x` gained 0.0013165 while all four `lor_size` values lost
0.0012897–0.0013300 each. What moved is the split, and the width they sum to
stayed put.

A chained series is the case to measure rather than assume. Ten warm-started
patterns took 1603 evaluations against 1792 fully converged (57.2–57.6 s against
60.4–60.7 s), but the same comparison one commit earlier went the other way,
1705 against 1634. Each pattern starts from its
predecessor's answer, and a small change in one seed changes how many recovery
rungs the next pattern needs, so the chain turns a bounded per-fit difference
into an unbounded one whose sign is not fixed. A single cold fit has no such
amplifier: that one was faster in both trees.

### Converging every stage

Set `intermediate_ftol` to `None`:

```python
import rietx as rx

plan = rx.RefinementPlan.lab_bragg_brentano()
plan.intermediate_ftol = None
assert plan.stage_ftols() == [None] * len(plan.stages)
```

Every stage then stops where the solver's own default says, as every fit before
1.1 did, to the bit. Reach for it when a number is going into a
paper and you want the plan's own converged answer rather than one within a few
hundredths of an esd of it, when you are reproducing a number from an earlier
release, and in a test that pins a value: a suite whose numbers move when a
default moves is not pinning anything.

`PlanSpec.intermediate_ftol` carries the setting through JSON, so a project
file, a history header and an agent request all record which schedule ran. In
the GUI's text document it is the `tolerance` line, whose value is a number or
the word `none`.

## What a stage carries

A `Stage` is `Stage.name`, a list of globs in `Stage.turn_on`, and seven
numbers that decide how that stage is solved. `Stage.name` is a label, carried
through to `StageResult.name` and to the event stream; `Stage.turn_on` is what
the stage frees, matched with `fnmatch` against the dot-paths of [](model.md).

[](concepts.md) covers `Stage.restraint_weight_scale`, the restraint schedule,
in full; the other six are here.

```python
import rietx as rx

stage = rx.Stage("widths", ["instrument.profile.*"], max_iter=200)
assert stage.max_iter == 200
assert stage.seed == 0.0 and stage.strain_seed == 0.0
assert stage.lebail_cycles == 3
```

`Stage.max_iter` caps the least-squares iterations for that stage. A stage that
reaches it is reported with status `max_iter` rather than `converged`, which is
a result to read rather than an error to catch.

`Stage.ftol` is this stage's own termination tolerance (the relative cost
decrease below which the solver stops), and it overrides the plan's schedule
above. Unset (`None`), the stage takes whatever `RefinementPlan.stage_ftols`
gives it. Set it to say that one stage is different: an early stage whose seed
the next one is unusually sensitive to, or a single-stage fit that has to
converge as hard as an endpoint.

`Stage.seed`, `Stage.strain_seed` and `Stage.distortion_seed` all exist to
lift a parameter off an exact zero that the solver cannot move away from, and
they are not interchangeable, because the three pathologies are different.

- `Stage.seed` lifts any softplus-bounded parameter the stage frees to the given
  value. The softplus map's slope at zero is itself near zero, so a coefficient
  starting at exactly zero has no gradient and never moves. The extinction and
  surface-roughness stages use it.
- `Stage.strain_seed` puts a freed but all-zero Stephens block on a small
  microstrain, in ppm of ΔM/M. Those coefficients are identity-transformed, so
  `Stage.seed` cannot reach them, and their problem at zero is the exploding
  gradient of a square root rather than a dead one.
- `Stage.distortion_seed` moves an all-zero distortion-mode block off the
  parent, in ångströms of the furthest-moved atom, before the stage frees
  it. The gradient there is neither dead nor exploding but exactly zero,
  and for every mode of the phase at once: the parent translation the
  k-doubling lost carries the mode field to its negative, so |F|² is an even
  function of the whole amplitude vector and the parent is a local *maximum* of
  fit quality rather than a starting point. A stage that frees an all-zero
  block without this is refused by name rather than run. The value is
  signed (the overall sign of a component's amplitudes is a domain label),
  so a negative seed simply starts in the other antiphase domain;
  `rietx.strategy.staged.DISTORTION_SEED_A` is the recommended magnitude and
  its comment gives the three measurements that fix it.

All three default to `0.0`, meaning no seed.

`Stage.lebail_cycles` is the number of intensity-partitioning refreshes the
stage performs, and it applies in Le Bail mode only.

`Stage.window_slack_deg` (and its mirror `StageSpec.window_slack_deg`) is the
absolute capture slack, in °2θ, added to every evaluation-window half-width
the stage compiles. The default (`None`) uses the package constant, sized for a
fit whose starting positions are roughly right. A fit that must measure a
hypothesis it is forbidden to walk toward declares the wider capture range its
verdict needs instead of borrowing tail margin. The indexing Le Bail validation
holds its candidate cell fixed, and a wrong candidate displaces peaks by whole
degrees. Leave it unset in ordinary plans.

## Persisting a plan

`RefinementPlan` and `Stage` are plain dataclasses, pleasant to edit and useless
to store. `PlanSpec` and `StageSpec` are their
serializable mirrors, and the conversions are explicit in both directions:

```python
import rietx as rx

plan = rx.RefinementPlan.mccusker_default()

spec = rx.PlanSpec.from_plan(plan)
restored = spec.to_plan()

assert [s.name for s in restored.stages] == [s.name for s in plan.stages]
assert spec.correlation_guard == plan.correlation_guard
```

`PlanSpec.from_plan` and `PlanSpec.to_plan` are the two directions.
`PlanSpec.stages` is a list of `StageSpec`, with `StageSpec.from_stage` and
`StageSpec.to_stage` doing the same job one level down.

You do not have to call them at a boundary. Anything that takes a `PlanSpec`
also takes a `RefinementPlan`, and anything that takes a `RefinementPlan` also
takes a `PlanSpec`: a preset goes straight into an agent request, and a plan
read back off a project or a history header goes straight into `fit`:

```python
import rietx as rx

plan = rx.PLAN_PRESETS["mccusker_default"]()

assert rx.PlanSpec.model_validate(plan) == rx.PlanSpec.from_plan(plan)
```

The conversion happens in the two places that own the mirror, so no call site
carries a copy of it. Write it out yourself when you want the JSON: the
dataclasses have no `model_dump`, and asking one for it says which mirror
to use. A `StageSpec` mirrors `Stage` field for field (`StageSpec.name`,
`StageSpec.turn_on`, `StageSpec.max_iter`, `StageSpec.ftol`,
`StageSpec.lebail_cycles`, `StageSpec.seed`, `StageSpec.strain_seed`,
`StageSpec.distortion_seed`, `StageSpec.restraint_weight_scale` and
`StageSpec.window_slack_deg`), and
`PlanSpec.correlation_guard` mirrors the plan's.

What is stored is the expanded plan: every stage in full, because that is what
will run. There is deliberately no field recording which preset it came from,
since such a field could disagree with the stages beside it.

`PlanSpec.preset_name` is therefore a method rather than a field, and it answers
the question by comparison. It returns the registered preset this plan equals,
or `None` if it was edited:

```python
import rietx as rx

spec = rx.PlanSpec.from_plan(rx.RefinementPlan.mccusker_default())
assert spec.preset_name() == "mccusker_default"

spec.stages.pop()
assert spec.preset_name() is None
```

That is what lets a plan editor label a menu, and the text document print
`plan mccusker_default` instead of eight stage lines, without either of them
trusting a stored label.

This is the form a plan takes in a history tree and in a `.rex` project, so the
round trip is what makes a stored plan a record of what was actually done.

## Running one stage at a time

`Refinement.fit` runs a whole plan. `Refinement.run_stage` runs exactly one
stage against the current model and stops:

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
ref = rx.Refinement(structure, instrument)
ref.run_stage(data, rx.Stage("scale_bkg", ["phases.*.scale"]))
ref.run_stage(data, rx.Stage("cell", ["phases.*.cell.*"]))
```

Each call refines, commits a history node and leaves the model at the values it
reached, so the next call starts from there. This is the same sequence a plan
performs; running it by hand is how a caller interleaves its own decisions
between stages. `Refinement.suggest` is built for exactly that moment, and
[](history.md) is how to go back a stage when the decision was wrong.

`run_stage` takes its own `correlation_guard` rather than reading one from a
plan, because there is no plan involved.

`Refinement.snapshot` returns a `RefinementState`: the full state needed to
reconstruct the refinement exactly, taken without refining anything.
`Refinement.stage_reports_` holds the per-stage reports from the last `fit`,
when it was asked for them. Each is a `StageReport`, which carries its own
statistics rather than a `Statistics` object:

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
ref.fit(data, stage_reports=True)
for rung in ref.stage_reports_:
    print(rung.stage, rung.rwp, rung.gof)
```

That is off by default. Ask for it deliberately: a converged run's final report
is routinely its least informative, because a plan absorbs an error it cannot
free into whatever it can. [](report.md) has the argument and
what to read in a trajectory.

## What each stage reports

`RefinementResult.stages` is a list of `StageResult`, one per stage, in the
order they ran. It is the cheapest honest account of what a fit did:

<!-- api-doc: no-exec — it needs a result from the reader's own data -->
```python
for stage in result.stages:
    print(stage.name, stage.status, stage.n_iterations,
          stage.cost_initial, stage.cost_final)
```

| Field | Holds |
|---|---|
| `StageResult.name` | the stage's name, as the plan gave it |
| `StageResult.status` | `converged`, `max_iter` or `diverged` |
| `StageResult.n_iterations` | least-squares iterations taken |
| `StageResult.cost_initial` | the cost the stage started from |
| `StageResult.cost_final` | the cost it reached |
| `StageResult.freed` | the paths this stage actually freed, after globbing |
| `StageResult.ftol` | the tolerance it was solved at; `None` = the solver default |
| `StageResult.n_constraint_truncations` | steps the bounded-LM driver shortened to stay inside a linear-inequality constraint |
| `StageResult.n_degenerate_cell_probes` | trial cells this stage's residual refused as degenerate (zero or negative volume) rather than warning about and returning NaN |
| `StageResult.held` | paths the plan freed that this stage held anyway, because the data could not see their phase |
| `StageResult.held_reach` | per held path, the tied parameters it also stopped |
| `StageResult.released` | the ones it held at the start and let go again, having seen the phase appear while it solved |
| `StageResult.unknown_paths` | the literal `turn_on` paths that name no parameter of this model; `None` on a result stored before the check existed |
| `StageResult.unreached_histograms` | joint fits: per histogram, the globs that freed rows of another histogram and matched none of this one; `{}` on a single histogram, `None` on a result stored before the check existed |

`StageResult.freed` is the field to read when a stage did nothing. A glob that
matches no path is not an error, because that is how the shipped plans reach a
component your model may not declare: `lab_sample_refine` frees
`phases.*.microstrain.dof.*` whether or not a phase carries a Stephens block.
An empty list can therefore mean the stage was a no-op, and the run continues
past it.

A literal path is different. With no `*`, `?` or `[` in it, it names one
parameter, so if the model has no such row the plan is wrong: a typo, or a
path renamed under you. `StageResult.unknown_paths` lists it and the fit reports
`STAGE_PATH_UNKNOWN` at `warning` with the nearest real path. A stage asking
for the wavelength without its line index is pointed at line 0's wavelength,
the row the table actually has. It is a diagnostic, not an exception,
because one plan runs every pattern of a series ([](series.md)). A misspelt
family inside a glob looks exactly like a glob that correctly matched nothing,
so no rule can report it, and `freed` is the place to look.

A joint fit (`MultiHistogramRefinement`, in [](series.md)) has one more way to do nothing, which is to do it on
one histogram only. A glob written for one instrument's parameter names reaches
only the histograms that have them. So a stage whose globs freed rows of
histogram 0 and matched none of histogram 1 records
`StageResult.unreached_histograms == {1: [the globs]}`, and the fit reports
`STAGE_FREED_NOTHING` at `info`, one diagnostic per histogram. A glob scoped to
one histogram (`hist.0.…`) is not reported, because that is a plan aimed on
purpose. Nor is a row that exists and is force-fixed, since it was reached. A
component declared on one histogram only, such as a hump, *is* reported,
because it is a true account of what the stage did.

`StageResult.held` is the field to read when a parameter did nothing. A phase
reaches the pattern only through `scale × |F|² × profile`, so a phase whose
scale sits at its floor has no measurable structural parameter at all. Freeing
its cell asks the solver to search a direction that does not change the
calculated pattern. Where that is the case at stage start, the stage holds
those parameters and refines the rest; the phase's own `scale` is never held,
which is how the phase can still appear. The values come back as the ones you
handed in rather than as a walk, `PHASE_UNCONSTRAINED` names the phase and the
stages that held it, and the parameters are absent from
`RefinementResult.parameters` because nothing measured them.

A stage holds whichever parameter carries the freedom. Tie that cell to a
variable of your own and the variable is what stops moving, so
`StageResult.held` names `vars.A` where the cell would otherwise appear.
`StageResult.held_reach` maps each held path to the tied parameters it was
driving. A cubic `a` held on its own account lists the `b` and `c` that
followed it. A held `vars.A` lists the cell it drove. The two fields together
are every value the stage froze.

A variable driving two phases is held only while the data can see neither of
them. One visible phase gives it gradient, so it is not the flat direction a
hold exists to remove, and holding it would freeze a cell the data can measure.
A phase appearing while the stage solves lifts the hold the same way.

A hold is decided per stage, at the values that stage starts from, so a phase
that appears later refines normally from the stage where it appears. If it
appears while a stage solves, that stage lifts the hold and solves a second
time, once and never a third, and lists those paths in `StageResult.released`
instead. Both solves are counted in `n_iterations`; `cost_initial` is still the
cost the stage started at.

Both lists are empty for every fit whose phases are all visible, which is every
fit that is working.

A cost that rises from `StageResult.cost_initial` to `StageResult.cost_final`
is a diverged stage, and `StageResult.status` says so.

`StageResult.n_constraint_truncations` is `0` under the default `trf` solver,
which has no linear-inequality vocabulary at all. It counts only under
`solver="lm"`, and today the only such constraint is the Stephens strain cone.

`StageResult.n_degenerate_cell_probes` counts trials, never the answer: `Cell`
declares no bounds of its own, so an underdetermined cell stage can reach a
zero- or negative-volume metric while searching, and each such reach is pushed
back out and counted rather than crashing the stage or returning a silent
NaN. Nonzero is the ordinary outcome on a poorly-constrained cell, not a sign
that anything reported is wrong; the fit-level `CELL_DEGENERATE_PROBE`
diagnostic sums this across every stage that ran.

## Guards

A guard is a measurement taken after a stage converges. It never changes the
fit. It reports something about the fit that the fit statistics cannot show.

Every hit is a `GuardFinding`, which carries the finding as data rather than as
a sentence:

```python
import rietx as rx

finding = rx.GuardFinding.correlation("instrument.zero_shift",
                                      "instrument.geometry.sample_displacement",
                                      -0.997)
assert finding.code == "HIGH_CORRELATION"
assert finding.paths == ("instrument.zero_shift",
                         "instrument.geometry.sample_displacement")
assert finding.value == -0.997
print(finding.message)
```

`GuardFinding.code`, `GuardFinding.paths`, `GuardFinding.value` and
`GuardFinding.message` are the four fields. A client reads `paths` to offer a
link and `value` to sort; nothing has to take a string apart. `str(finding)` is
`GuardFinding.message`.

There is one constructor per kind of finding, so each format string is written
once:

| Constructor | Fires when |
|---|---|
| `GuardFinding.correlation` | two free parameters correlate above the plan's `correlation_guard` |
| `GuardFinding.at_bound` | a parameter stopped against a bound |
| `GuardFinding.background_absorption` | the background could largely reproduce a structural parameter's column |
| `GuardFinding.roughness_absorption` | the roughness correction could |
| `GuardFinding.nonpositive_adp` | an anisotropic displacement tensor is not positive definite |
| `GuardFinding.nonpositive_strain` | a Stephens block gives a negative σ²(M) for some reflection |
| `GuardFinding.narrow_hump` | a declared hump has narrowed towards the instrumental resolution, where it is a reflection rather than a background feature |
| `GuardFinding.unsupported_resolution` | the Gaussian resolution terms were refined on a pattern whose peaks are predominantly Lorentzian, where the data does not determine them |
| `GuardFinding.flat_direction` | a correlated pair reaches \|ρ\| = 1.000 to the precision the message prints, so the data does not separate them at all |
| `GuardFinding.large_biso` | an isotropic displacement parameter is past the Lindemann melting bound computed from its own phase's cell |
| `GuardFinding.nonpositive_resolution` | the Caglioti quadratic Γ_G² = U·tan²θ + V·tanθ + W goes below zero somewhere in the fitted range, where the forward model clamps Γ_G to a floor rather than raising |

`GuardFinding.value` is the headline number for the kind: the correlation
coefficient, the block R², the minimum eigenvalue, the worst σ²(M), the
worst Γ_G². It is
`None` for `GuardFinding.at_bound`, which has no number to report.

`code` is an open vocabulary of strings and deliberately not a closed type. It
is the same vocabulary as `Diagnostic.code`, so the mapping from a guard to the
diagnostic a caller reads is data rather than a hand-written branch per kind.
[](results.md) reads diagnostics.

Read a guard as evidence about what the data could support, and not as a verdict
on the model. A `nonpositive_strain` finding means those coefficients are not
quotable, and it is no measurement of anisotropy.

## Watching a run

Every fit records itself. `Refinement.fit`, `Refinement.run_stage`, `refine`
and `refine_sequential` each write a run directory under the working directory
without being asked, and `rietx watch` reads it back ([](cli.md)).

Recording is on by default, so start with how to switch it off:

| Switch | Reaches |
|---|---|
| `RIETX_TELEMETRY=0` | the process and everything it starts |
| `telemetry=False` | the one call you pass it to |
| `telemetry="/some/root"` | still records, into a root you name |
| `rietx.runs.set_enabled(False)` | this process, from python, until you set it back |

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
result = ref.fit(data, telemetry=False)
```

The environment setting outranks the keyword, and no value of `telemetry=`
argues back. On a machine with `RIETX_TELEMETRY=0` exported, no call can ask
its way back on. The one override is `rietx.runs.set_enabled(True)`, which is
python code the process ran deliberately rather than an argument to a fit.

Recording never breaks a fit. A run directory that cannot be created or written
costs you the telemetry and leaves the refinement alone. The recorder stops,
warns once per process, and where it can still write, puts the reason in the
run's own `status.json`.

### What a run directory holds

One directory per fit, named for the date, the time and the process id. A
refinement that came from a project records into that project's `live/`
instead ([](files.md)).

```text
.rietx/runs/20260915-092640-80245/
    events.jsonl    30.8 kB   one line per event, 87 of them
    snapshot.json    171 kB   the stage's decimated curves, ticks and statistics
    summary.txt      1425 B   the termination view, as `print(result)` gives it
    meta.json         203 B   label, start time, version, working directory, command
    status.json       235 B   state, pid, host, heartbeat, stage, Rwp, gof
    run.lock            0 B   held by the writing process for its life
```

That is 204 kB for a five-stage synthetic LaB6 fit, on a `[dev]` install on
macOS arm64. `snapshot.json` is most of it, and each stage overwrites it, so it
does not grow with the run. The event log does grow. It ran about 1 kB an event
on the three benchmark patterns, and a long series is where that adds up.

The cost in time is the per-stage picture. Writing the event log alone measures
1.01 to 1.03 times a bare fit's wall clock. Adding the picture takes it to 1.03
to 1.23 times, measured over three patterns of 22 003, 7251 and 4165 points.
The charge is per stage and nearly constant, so the shortest fit pays the
largest multiple: 1.23 times on a fit of a third of a second, 1.03 times on one
of six seconds. Every configuration returned the same Rwp to the last digit, so
recording does not change the answer.

:::{warning}
A run directory holds every free parameter's value at every recorded
evaluation. On a shared filesystem that is a disclosure nobody opted into, so
set `RIETX_TELEMETRY=0` where the trajectory is confidential. No pattern bytes
are ever copied into a run.
:::

### Naming a run

`label=` names the run in `rietx watch`'s list.
Without one, a run takes the name of the working directory it ran in, or of its
project.
Forty candidate fits driven from one directory write forty rows under one name.

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
result = ref.fit(data, label="candidate-07 rutile")
```

The keyword is on every verb that records a run: `Refinement.fit`,
`Refinement.run_stage`, `refine`, `SequentialRefinement.fit`,
`refine_sequential`, `Project.fit` and `Project.run_stage`.

The name goes to the run's `meta.json`.
It is telemetry rather than a refined quantity, so it reaches no history node
and no result, and naming a run changes no number the fit produces.

A series is one run directory however many patterns it walks, so `label=` names
the whole chain.
Its patterns are named by `labels=`, and that is what the watcher shows in the
row.
The two keywords are one letter apart and mean different things, so a sequence
passed to `label=` raises `TypeError` rather than being written.

### Retention

The runs root is pruned by age and size, once per process, on the first fit.
Only the root the package chose is pruned: a root you named with `telemetry=`
is yours, and a project's `live/` is the project's, so neither is ever deleted
from. Nothing younger than a week is deleted, however many runs there are.
Above a 1 GiB ceiling the oldest finished runs go first, and a root that is
over the ceiling with nothing old enough warns and keeps everything. Using your
disk is the smaller harm.

Deleting by age and size rather than by count is deliberate. "Keep the newest
50" would delete run 1 of a 200-candidate batch while the batch was still
running, and a batch is one of the cases recording exists for.

The scan costs 0.2 ms at 10 runs, 2.2 ms at 100 and 27.6 ms at 1000.

### Streaming the events yourself

`events` streams per-iteration telemetry to somewhere you choose, alongside the
run the fit records for itself. It accepts a path, in which case each event is
appended to that file as JSONL:

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
result = ref.fit(data, events="run/events.jsonl")
```

or a callable, called with each event as a plain dict:

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
def show(event):
    print(event["kind"], event["data"])

result = ref.fit(data, events=show)
```

Each event carries its kind, a Unix timestamp, and an open `data` dictionary.
The kinds are a closed set: `fit_start` and `fit_end` for the run,
`stage_start` and `stage_end` for each stage, and `eval` for each residual
evaluation. A run's state is not one of them. It travels beside the stream in
`status.json`, because a fit killed outright emits no `fit_end`.

Your callback runs outside the recorder's protection. A hook that raises takes
the fit with it, which is the behaviour you want from a hook you asked for.

Two rules matter to anyone consuming the stream. Read `data` with `.get` rather
than by unpacking a fixed shape, because fields are added to a kind without a
version bump. And a cancelled run's `fit_end` omits the statistics entirely,
because there is no fitted result to report.

`Capabilities.event_schema_version` reports the version a build emits;
[](compatibility.md) says what that version promises.

## Stopping a run

`cancel` takes a `CancelToken`, which another thread sets:

```python
import rietx as rx

token = rx.CancelToken()
assert not token.is_set()
token.cancel()
assert token.is_set()
token.reset()
```

Cancellation is cooperative. The token is read between residual evaluations and
never as an interrupt, so the frozen-per-stage state of a compiled model stays
intact.

The stage in flight is abandoned: no history node, no commit, and the models
restored to the values they held before that stage began. That restore is more
than tidiness. A seeding stage writes to the models before it solves, so leaving
them alone would leave a half-seeded model behind.

`RefinementCancelled` is then raised, carrying what did complete:

<!-- api-doc: no-exec — it needs a run cancelled from another thread -->
```python
try:
    ref.fit(data, cancel=token)
except rx.RefinementCancelled as cancelled:
    print(cancelled.stage)             # the abandoned stage's name
    print(cancelled.completed_stages)  # list[StageResult] for those that finished
    print(cancelled.node_id)           # the node the working state stands at
```

`RefinementCancelled.stage` is the abandoned one. `RefinementCancelled.completed_stages`
is empty when the first stage was cancelled. `RefinementCancelled.node_id` is
`None` with history disabled, or when nothing completed.

A cancelled run is therefore not a lost run. The working state is a real,
restorable node ([](history.md)), and the stages before it are reported in
full.

### A stop you did not arrange

A fit that passed no `cancel=` can still be stopped. Every fit writes a run
directory, and `rietx watch` puts a stop button on any run being written on this
machine ([](cli.md)). Pressing it raises the same `RefinementCancelled` in the
process running the fit, carrying the same three fields. Code that already
catches the exception needs no change. Code that does not catch it prints a
traceback and exits.

The run's `status.json` records `cancelled_by` when a request caused the stop,
and records nothing there when the caller's own token did. The exception carries
no such field. Downstream of the token there is no difference between the two,
and the fit is in no position to claim one.

`telemetry=False` removes the run directory, and the button with it. So does
`RIETX_TELEMETRY=0`. Both also remove the window a person was watching through,
which is the trade being made.

## What the result records about the run

`RefinementResult.provenance` is a `Provenance`, and it holds everything needed
to reproduce the result:

<!-- api-doc: no-exec — it needs a result from the reader's own data -->
```python
p = result.provenance
print(p.package_version, p.backend, p.solver, p.dtype)
```

| Field | Holds |
|---|---|
| `Provenance.package_version` | the version of rietx that produced it |
| `Provenance.schema_version` | the data-contract version of the objects |
| `Provenance.backend` | the backend the arrays were computed on |
| `Provenance.dtype` | the precision they were computed in |
| `Provenance.solver` | the least-squares driver used |
| `Provenance.report_thresholds_version` | the thresholds any report was judged against |
| `Provenance.created_utc` | when the result was assembled, UTC |
| `Provenance.notes` | free-form string pairs a caller can add |

Read `Provenance.backend`, `Provenance.dtype` and `Provenance.solver` back
rather than assuming them. A result is only as reproducible as its record of how
it was computed, and that record is where the answer survives once the calling
code has moved on.

The four version fields are the same contracts `capabilities()` reports.
[](compatibility.md) says what a change to one means.
