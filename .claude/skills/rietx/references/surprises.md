# 8. Twenty-two things that will surprise you, all measured

Load it when something the fit did makes no sense. Every entry is a measured result that contradicts an intuition.

*A reference file of the `rietx` skill. The body it belongs to is [`SKILL.md`](../SKILL.md); section numbers are the ones the body cites.*

These are the findings from building the package that change how an agent
should behave. Each one cost a debugging pass.

**8.1 A correction that provably cannot improve Rwp can still be essential.**
The capillary absorption factor factors *exactly* into a constant × exp(c·sin²θ)
— a Debye-Waller shape — so applying it to a model with a free scale and free
Biso leaves the residual unchanged to machine precision. Its entire content is
that a Biso refined without it comes back **low by 0.49 Å² at µR = 1** (Cu Kα),
which is comparable to Biso itself and 19σ against its own esd. `result.absorption`
reports the bias because no fit statistic can. **Corollary for the agent: never
judge a correction by Δ Rwp. Ask which physical quantity it unbiases.**

Measured end to end on a real capillary pattern (11-BM, NIST SRM 660a LaB₆ in
the documented 0.81 mm bore, µR = 0.674): Rwp moved 3 × 10⁻⁸, the lattice
parameter 8 × 10⁻¹² Å, and **both** displacement parameters moved by
+0.0166542 Å² against a predicted 0.0166542. That is what "exact" means here.
It is not a general property of absorption corrections — see 8.12.

`rietx compare` is this rule made mechanical: a browser UI comparing refinement
settings side by side on the bundled standards, whose cumulative-Δχ² panel shows
*where* a correction acted rather than whether Rwp moved.

**8.2 The opposite also happens: an improvement that passes every statistical
test and is still rejected.** On round-robin brucite, adding anisotropic strain
improves Rwp 18.55 → 17.90 % with ΔBIC +488 — and drives σ²(M) negative on 12
of 43 reflections, so the coefficients are unphysical and unquotable. A
statistical test cannot see a violated positivity cone.

**8.3 Judge a correction at the reflections, not on the fitted grid.** The IUCr
round-robin patterns start at 5° 2θ but their first reflections are at 25–32°.
A grid-based fence cheerfully reported a 27 % low-angle intensity depression
that no modelled peak ever experienced. If you are reasoning about where a
correction has leverage, the relevant coordinate is *where the reflections are*.

**8.4 A multiplicative correction is trivially ~0.96 "scale-like".** Any
correction that rescales intensity projects almost entirely onto the scale
column, so a raw R² against a block containing the scale is a constant that
says nothing. Use the **partial** R² with the scale and background projected
out first — `optimize.statistics.block_projection_r2(..., nuisance=...)`. With
that fix the statistic tracks real identifiability (R² 0.06 → 0.95 as the
low-angle reflections leave the fitted range); without it, it saturates and the
guard is blind.

**8.5 Pairwise correlation is the wrong statistic for a block.** With ~100
spline coefficients, each individual |ρ| against a structural parameter stays
around 0.2 while the block collectively absorbs ~46 % of it. Ask "can this
*group*, acting together, imitate that one?" — that is what
`background_absorption` measures.

**8.6 Some parameters are dead at zero and some explode there.** A
softplus-transformed coefficient (extinction, roughness strength) has
dp/du → 0 at the floor, so it will never move: it needs `Stage.seed`. A
Stephens block has Λ ∝ √Σ with *unbounded* slope at Σ = 0, so it needs
`Stage.strain_seed` to start on the isotropic ray instead. These are opposite
pathologies with opposite fixes; the plans already carry both.

**8.7 A default is a decision, in either direction.** Anisotropic ADPs,
Stephens strain, surface roughness and preferred orientation are opt-in per
atom/phase, because each needs a number about *this* specimen that the file
does not carry. Anomalous dispersion is the exception and is **on by default
since v1.0**: it needs only the species and the wavelength, both already in the
model, so declining it is the choice that has to be justified. Turning any of
them on or off changes every number downstream, including published acceptance
values — if you change one, re-measure; do not carry a comparison across the
change. Note the two knock-on effects WP-1001 measured when dispersion went to
the default: on a specimen sitting inside an absorption-edge interval the
lookup **raises** rather than degrading (that is deliberate — a selective
fallback would leave some species corrected and others not, manufacturing
exactly the unequal cross-phase bias the correction exists to remove; decline
the block or supply `overrides`), and light-atom ADPs come back *less precise*
even as they come back *less biased* (rutile U11/U33 separate at 1.9σ with the
block on against 2.2σ without, because f″ raises the heavy atom's share).

**8.8 Never transfer a literature constant without a numerical check across
*all* its arguments.** A published cylinder-absorption coefficient printed as
"−0·0375" is really −0·3750; the error is invisible against a constant-θ slice
of the paper's own table (which constrains only the other two coefficients) and
is 0.082 wrong at µR = 1. What caught it was a quadrature of the exact integral
the fit approximates — which shares no constant with any published fit. The
general rule: **the strongest anchor is the integral a fit approximates, not
another code's transcription of the same fit.** The same applies to Stephens
S_HKL, where codes fold symmetry multiplicities into their templates and print
values differing by small integer factors.

**8.9 An absurd statistic is more often the linear algebra than the physics.**
JᵀJ here is routinely conditioned at ~10²⁰ — that is what the degeneracy table
in §3 *means* numerically. Until 2026-07-28 the covariance was taken with
`np.linalg.pinv`'s general SVD path, which does not know the matrix is
symmetric and returned correlations as large as |ρ| ≈ 1.6 × 10³ (and +2.75 for
`scale ~ axial_sl` on a real fluorite fit). If a reported correlation, esd or
weight-fraction uncertainty is impossible rather than merely surprising, check
the conditioning before you invent a physical story for it — and remember that
the fix is to compute the covariance properly, not to clip the output, because
clipping 2.75 to 1.0 reports a degeneracy the arithmetic invented rather than
the one the data has.

**8.10 Conventions are documented by physics, never by letter.** GSAS and
FullProf swap the X/Y size/strain labels. Most tabulations print the absorption
*correction* A\* = 1/A where this package multiplies by the *transmission*
A ≤ 1 — and both equal 1 at µR = 0, so an identity test cannot tell them apart;
only the direction of the θ-dependence can. The March coefficient r means
opposite habits in reflection and transmission geometry. **Read the docstring,
not the symbol.**

**8.11 The anode is a physics choice, not a number to look up.** All six
`radiation=` presets come from one column of one evaluation (NIST XRTE
SRD 128), and the shipped `CuKa` pair is bit-identical to it — that is what
makes the others trustworthy, so **never substitute a value from elsewhere**;
Bearden's widely-quoted numbers are a different scale, 24–26 ppm away at Mo/Ag.
Three things then follow from *which* anode, all measured:

* The Kα1/Kα2 gap grows from 20 eV at Cu to 173 eV at Ag, so the one-|F|²-per-
  source assumption gets weaker. A census over Z = 3–98 × six anodes refuses 7
  of 576 combinations, and one is a real specimen: **Ru at Ag Kα**, K edge
  22.14 keV, between the lines. The refusal is correct — split the lines into
  separate histograms or supply a measured override.
* What `DISPERSION_NEGLECTED` is warning about is anode-dependent: hematite is
  a `warning` at Co Kα (180 eV under the Fe K edge, f′ = −3.3 e) and an `info`
  at Mo Ka (f′ = +0.3 e). Same specimen, same code, different severity.
* Contamination checks are per anode. An unrecognised wavelength (synchrotron,
  an untabulated anode) yields `contamination == []` — *not checked*, not
  clean. `background.identify_anode(λ)` returns `None` there and is how you
  tell the two apart.

**8.12 "Infinitely thick" is a modelling claim you make by saying nothing.**
Every flat-plate fit in this package — and by default in every Rietveld code —
assumes the specimen is thicker than the beam penetrates. That is exactly right
for a filled well and badly wrong for a thin layer on a zero-background holder,
which is how small, precious or air-sensitive samples are usually mounted. The
error is much larger than the capillary case and has the opposite sign:
`ΔBiso = −1.5 Å² at µt = 0.2` over a Cu Kα range, because a thin specimen runs
out of material exactly where the beam penetrates deepest, and the missing
high-angle intensity reads as thermal motion.

Four consequences for an agent:

* Declare `Geometry.mu_t` (or `thickness_mm`, and let it be estimated) whenever
  the specimen is a thin mount. Silence means thick.
* The "off" value is **µt = ∞, not 0** — the reverse of every other correction
  here. `mu_t = 0` is a specimen of no thickness and is refused for reflection
  geometry rather than being taken as "no correction". Under
  `flat_plate_transmission` it is the other way round: silence means a
  transparent plate, and the sec θ footprint factor applies regardless, because
  it belongs to the tilt rather than to the absorption.
* **The reported ΔBiso is a lower bound here, not the answer.** For the
  capillary it is exact (seven decimals on real data); for a flat plate the
  bias a fit actually absorbs runs 1.06–1.5× larger, tracking
  `absorption.unabsorbed_fraction` — which is on the record for exactly this
  reason. Quote it as "at least this much", with the residue beside it.
* Unlike the capillary case this one **does** move Rwp, because it is not an
  exact reparameterisation (1–40 % of ln A survives a free scale and Biso). So
  8.1's rule inverts: here a *worse* Rwp after declaring a thickness is
  evidence the specimen was not that thin. Measured on round-robin fluorite —
  a thick back-packed mount — declaring µt = 0.5 takes Rwp 0.1793 → 0.1830 and
  drives one Biso onto its bound. That is the correction correctly refusing to
  fit a specimen that is not there.

**8.13 A stage that takes minutes is telling you it is degenerate.** Measured
on three weighed NaCl/Li₂CO₃ mixtures — identical models, identical parameter
counts, same-sized patterns — wall clock ran **39 s, 858 s and 2 838 s**, a 73×
spread with no corresponding difference in the answer, and the pass reported
`status="converged"` either way. Until v1.1 the budget made that spread far
worse than it needed to be: `max_nfev` was `max_iter × n_par`, pricing a
finite-difference Jacobian the package does not build, so at 46 free parameters
a single `max_iter=100` stage could spend **4 600** evaluations before giving
up. It is now `max_iter ×` a small measured constant (the worst
evaluations-per-iteration ratio over 28 real stages is 3.2), so a stalling
stage says so roughly 30× sooner and a converging one is untouched — every
protocol measured stops an order of magnitude inside the cap. That changes when
you hear about it, not what you should do about it. The
stages that stall are the degenerate groups of §3, so the signal is available
*before* you run them: per-phase size/strain freed against a still-free
instrument U,V,W,X,Y (they model one width curve; the package's own
`lab_sample_refine` only frees them against a **frozen** calibrated instrument),
or preferred orientation whose coefficient has reached a bound. **Corollary:
treat elapsed time as a diagnostic. If a stage runs long, do not wait for it —
look at what you freed.**

**8.14 A bound that exists is not a bound that holds.**
`PreferredOrientation.r` is declared `min=0.0` with a softplus transform, the
idiom that is supposed to keep a parameter strictly positive. The softplus
pre-image runs to −∞, so `r` reaches **exactly 0**, and the March-Dollase factor
then evaluates `(1 − c)/r` and returns inf/NaN. Nothing raises: the residual
becomes garbage and the trust region grinds through its whole budget on it (a
3-second stage that had not returned after ten minutes). Bounding `r` to
0.15–6 fixed the stall *and* the fit, Rwp 30.8 % → 13.2 %. **Corollary: for any
parameter whose model divides by it, set a real floor rather than trusting the
transform — and read `RuntimeWarning: divide by zero` as a fit-stopping error,
not noise.**

**8.15 A coverage score cannot tell a mixture from a low-symmetry single phase,
and this project already published that mistake and withdrew it.** Measured on
third-party data with an engine restricted to two metric parameters: it indexed
47–60 % of the lines of *single-phase* orthorhombic and monoclinic patterns,
82–100 % of genuinely tetragonal or hexagonal ones, and 69 % of a real
two-phase mixture. **The bands overlap.** A "this pattern contains at least two
phases" claim built on the 69 % had to be retracted, because the same number is
what a single-phase pattern of symmetry the engine could not reach produces.
`IndexingResult` therefore carries `systems_searched` beside `search_complete`
and reports failure as *"no cell found in the systems searched"*; no diagnostic
code in the indexing vocabulary asserts a phase count at all, and a test pins
that. **Corollary: partial coverage is a statement about your search, not about
the specimen. Widen the systems before you conclude anything about the sample.**

**8.16 An indexer's tolerance is not its precision, and the gap is 11σ on real
data.** The peak list carries a *fitted* σ(2θ) per line — median 0.0056° on the
bundled corundum pattern, whose cell is certified — and that σ is exactly right
for **weighting** and exactly wrong as a **matching window**: the same pattern's
lines sit a median 0.060° from the certified positions, a cos θ specimen
displacement of −0.065°. At 3σ the true cell indexes *zero* lines and both
engines return nothing, on a pattern whose answer is known. That is why every
indexing program in the literature ships a global ~0.03° tolerance, and why the
engines here add an assumed 0.05° in quadrature and say so with
`INDEX_SHIFT_ALLOWANCE`. **Corollary for the agent: a cell found under a widened
window has absorbed the shift (+1400 ppm measured), so re-fit it with
`shift_template` before quoting it — and the way to earn `high` confidence is to
supply a measured `shift_allowance_deg` — the shift's amplitude, not the
residual scatter a template leaves — from an internal standard, not to widen
further.**

**8.17 "Is there intensity here?" is not one question — it depends on what else
your hypothesis predicts nearby.** Two detectors in this package ask it with the
same window (±½ FWHM) and the same threshold (3σ), and they must use different
null models. WP-1024's `predicted_but_absent` asks it against the fitted
**background**, which is right for an oversized cell's phantom reflection because
a phantom sits in a *gap*. WP-1025's extinction screen asks it at a **forbidden**
position, which sits inside a dense predicted pattern — and measured on the FAP
lab pattern, the 003 that P 6₃/m forbids is 0.89 FWHM from an allowed neighbour
ten times stronger whose tail fills the window to **+27.6 σ**. Against the class's
own `y_calc` — background plus every reflection the class still allows — the same
window reads **−3.9 σ**. **Corollary for the agent: never compute your own
"nothing is here" test from the raw pattern minus a background.** Where nothing
else is predicted nearby the two agree; where something is, the raw test refutes
the true answer.

**8.18 A position correction belongs to a geometry, and the suggestion you get
now says which.** `cos θ` is the *flat-plate* specimen-displacement shape, and
`instrument.geometry.sample_displacement` is force-fixed on anything that is not
`bragg_brentano`. A capillary off the centre of the 2θ circle has its own pair
(McCusker eq 4): `instrument.geometry.capillary_offset_along_beam` carries sin 2θ
and `…_across_beam` carries cos 2θ, they exist only on `debye_scherrer`, and both
need `goniometer_radius_mm`, which eq (4) divides by — a value or a `vary` without
one is refused by name rather than defaulted. Free them for a laboratory capillary
or Guinier camera; at a synchrotron with a crystal analyser the paper says the
displacement error is eliminated, and measured on 11-BM NAC the fit agrees, so
freeing them there measures nothing.

The report's position templates and actions are now chosen by geometry, so the
two `refine_sample_*` actions no longer reach a capillary fit at all (before
WP-1073 they did, naming parameters that could not be freed). On
`flat_plate_transmission` they do not reach either (WP-1003): that geometry
models neither aberration, so a `cos_theta` or `sin_2theta` trend there is
reported as a shape with no action — read it as "a flat specimen off the
axis", evidence with no legal one-click repair. **And this is a
correction whose cause the endpoint hides**: measured on a synthetic capillary
with a 0.30/−0.20 mm offset, refusing the pair puts −290 ppm into `a`, and the
converged report names *no* position cause, because the zero shift and the cell
between them imitate most of eq (4). The `zero` stage's own rung names
`refine_capillary_offset_along_beam` at 0.66. **Corollary for the agent: this is
§9's rule with a concrete case — read the trajectory, not the last state.**

**8.19 A restraint's weight is a per-stage decision, and a fit can converge to
an impossible bond without saying so.** `Stage.restraint_weight_scale` is c_w of
McCusker eq (7), S = S_y + c_w·S_G: high while the structure is incomplete or
approximate, reduced as it improves. It defaults to 1.0 (every restraint exactly
as declared), and 0.0 silences the restraints for a stage while keeping their
rows, so the row count the statistics exclude never changes mid-plan.

Measured on a synthetic case whose data under-determines two oxygen sites,
starting from a Zr–O of 3.73 Å for a 1.87 Å bond: the same three stages run at
c_w = 1 throughout converge with that distance at **4.834 Å**, the restraint
148σ in tension and the coordinates 0.425 rms from truth; run at c_w = 300 then
1, the stiff stage lands the bond at 1.866 Å (0.03σ) and the relaxed stage
converges at 1.872 Å, 0.00107 rms. The plans differ in nothing but c_w.

**Corollary for the agent: this is a case where the fit statistics are the
weaker channel and you must read `result.restraints`.** The failed fit's Rwp is
0.0393 against 0.0327 and its GoF 1.23 against 1.02 — a slightly worse fit, not
an announcement of a 4.8 Å bond; `RESTRAINT_TENSION` is what fires. And a stiff
c_w makes a restraint more authoritative, not more correct: where the assumed
coordination is wrong, §8 of the paper says the refinement "will not progress
satisfactorily", and raising c_w makes that worse rather than better.
`RestraintReport.weight_scale` records which value produced a report, so the
penalty actually minimised is `weight_scale · restraint_chi2`.

**8.20 Intermediate stages are not converged, on purpose, and the last one is.**
A staged plan stops every stage but the last at `ftol = 1e-6` rather than the
solver's `1e-9` (`RefinementPlan.intermediate_ftol`, default since 1.1). The
reason is 8.13's mechanism seen from the other side: those long stages are
walking a near-degenerate direction at ≈0.93 per iteration, and 99.99 % of the
cost decrease is banked by evaluation 55 of 93 — the rest is digits the next
stage refines again anyway, because stages are cumulative and the last one
polishes everything at `1e-9`. Measured over the three lab-shaped benchmark
cases: 1.51×, 1.62× and 1.55× fewer evaluations, every non-degenerate parameter
within 0.03 esd of the fully converged plan, QPA within 0.0014 wt %.
**Corollary for the agent, in three parts.** Do not read a small parameter
difference between a 1.0.x number and a 1.1 number as a physics change; check
`StageResult.ftol` first. Set `intermediate_ftol = None` when a number is going
into a paper, or when you are reproducing an earlier release, and say that you
did. And **measure a series rather than assuming it**: the same chained
ten-pattern comparison came out 1.04× *worse* on one tree and 1.12× *better* on
the next, one commit apart, because each pattern warm-starts from its
predecessor and a different seed changes how many recovery rungs the next one
needs (§9b). The per-fit bound above does not survive a chain in either
direction.

**8.22 A tie carries its dependent's bounds back onto its source, so a source
can stop somewhere it never declared.** The least-squares box covers the *free*
column, and a tied parameter is not one — it is reconstructed from its source
after the solve — so a dependent's own limits have to reach the solver through
the tie or not at all. They do: `dependent = coefficient · source + offset`
inverts to a range on the source, intersected over every dependent that source
drives and with whatever the source declares itself. `Atom.biso` is `[0, 25] Å²`,
so under `ref.tie("phases.0.atoms.2.biso", "phases.0.atoms.0.biso", scale=2.0)`
the master is given a ceiling of **12.5** whatever its own `max` says, and
`BOUND_HIT` names the master when a stage stops there. Measured: master 0.66 and
dependent 0.33 under a declared dependent ceiling of 0.33 at coefficient 0.5,
Rwp 0.0458 — a converged fit that stopped at a derived limit, not a failed one.
(Measured: WP-1119, four-site LaB6.)

**What this means when you read a run.** A `BOUND_HIT` on a source whose own
`min`/`max` are nowhere near the value is not a bug and not a bad bound — it is
one of its dependents' ceilings arriving through the tie, and the fix is to widen
*that* parameter, not the one the diagnostic names. Check the coefficients before
touching anything.

**One case it cannot close.** A tie with *several* sources is a slanted boundary,
and the optimiser can only be handed a range, so what it gets is the smallest
range containing every allowed point — it never rules out an answer you asked
for, and it can leave a corner where two sources conspire to put a dependent out
of range. Landing there raises on write-back, after the solve, naming the
parameter, its bounds and the tie: *"writing phases.0.atoms.1.biso=40 back to
the model breaks its own bounds [0, 25]; it follows 2·phases.0.atoms.0.biso"*.
Read that as a constraint to widen, never as a corrupt model or a bad CIF.
(Measured: WP-1119.)
