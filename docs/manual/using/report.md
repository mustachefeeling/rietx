# The fit report

A converged fit gives you Rwp. The report gives you *where* the model and the
data disagree, *what kind* of error would explain it, and — separately — how
much of that the package is willing to stand behind.

:::{admonition} For automated callers
:class: agent
The `FitReport` is built for a program to read: numbers rather than pixels, so
a caller can close a refinement loop without looking at a plot. That is why the
sections below read as field lists.

A person gets more out of it than out of Rwp too, and `FitReport.summary` is a
paragraph of prose written for exactly that reader.

This chapter is the **object model**: what a `FitReport` carries, field by
field, and how to get one. The **judgement** — what to believe, in what order,
when to disbelieve Rwp, and how to act on an abstention — is
[`docs/AGENT_PROTOCOL.md`](https://github.com/yue-here/rietx/blob/main/docs/AGENT_PROTOCOL.md)
§4 to §6, and this chapter does not restate a line of it.
:::

## Building a report

`build_report` takes a `RefinementResult`. `Refinement.report` is the same thing
from the session, and it is the form to use, because it passes the compiled
model along. Without the model there is no Layer 1 at all.

Every report stamps `FitReport.thresholds_version`, the version of the gate
thresholds it was built under. Store that with any report you store: the
thresholds are a versioned contract, and a number compared across two versions
compares two different questions.

## Layer 0: statistics independent of the model

Nothing here depends on the model being right, so nothing here can be wrong
about the *data*.

- `FitReport.rwp` and `FitReport.gof`, the two headline statistics.
- `FitReport.regions` — the misfit clustered into 2θ regions, worst first. Each
  `Region` carries `Region.local_rwp`, `Region.chi2_share` (its share of the
  total χ², which is what makes it worth attention),
  `Region.max_abs_delta_over_sigma` and `Region.n_reflections`.
  `FitReport.n_regions_total` says how many there were before the list was
  truncated.
- `FitReport.unmatched` — observed peaks the model does not account for, and
  calculated peaks with no observed intensity. `UnmatchedPeak.kind` says which,
  `UnmatchedPeak.height_over_sigma` says how strong. This is how an impurity
  phase announces itself.
- `FitReport.cumulative_chi2_breakpoints` — where along 2θ the running χ² jumps,
  which localises a problem that a per-region view spreads thin.
- `FitReport.summary` — one paragraph of prose assembled from the above.

## Layer 1: attributing the misfit

Layer 1 answers a different question: *what kind* of error is this?

The residual in each region is projected onto a shape-derivative basis built
from the profile itself — intensity, position, width, mixing, axial asymmetry —
so the answer reads "the peaks here are 0.01° low and 5 % too weak", whichever
parameters happen to be free. The five columns are not orthogonal, so they are
fitted in one joint weighted solve rather than by independent dot products,
which would cross-contaminate.

`FitReport.attribution` holds one `RegionAttribution` per region, and
`RegionAttribution.coefficients` (each a `BasisCoefficient`) is the reading.

`FitReport.layer1_available` says whether the layer ran at all.

Above the per-region view, `FitReport.trends` regresses the region coefficients
against the angular templates a per-region view structurally cannot see:
position against constant, cos θ, sin 2θ and tan θ; width against 1/cos θ and
tan θ; intensity against sin²θ/λ², the displacement-parameter signature.

`TrendAnalysis.max_template_collinearity` and `TrendAnalysis.separable` are the
load-bearing pair. Over a limited angular range two templates can be
indistinguishable, and an inseparable pair is **declared inseparable** rather
than resolved into a confident wrong singleton. `FitReport.texture` and
`FitReport.strain` give preferred orientation and anisotropic strain the same
treatment.

### The four gates

None of Layer 1 is trustworthy unconditionally, which is what the gates are for.
There are four, and every statement passes all four or the region is reported as
not passing:

| Gate | Field | What it rejects |
|---|---|---|
| local significance | `RegionAttribution.chi2_reduced`, `RegionAttribution.has_significant_misfit` | a region whose "misfit" is noise |
| explanatory power | `RegionAttribution.r2` | a residual this basis does not explain at all |
| resolvability | `RegionAttribution.gram_condition` | columns too collinear here to be told apart |
| validity radius | {{ VALIDITY_RADIUS_FWHM }}·FWHM on the position coefficient | a peak far enough away that linearising it is meaningless. The answer must be "re-detect this peak", never a confident small offset |

`RegionAttribution.gates_passed` is the verdict, and
`RegionAttribution.gate_failures` names each failure with its numbers, so a
rejected reading tells you *why* it was rejected.

### When Layer 1 abstains

If the fit is too immature to linearise, Layer 1 does not guess. It abstains,
says so in `FitReport.abstained_reason`, and classifies the abstention in
`FitReport.abstained_kind`: *immature* (the starting model is bad enough that
attributing structure to the residual would be attributing structure to the
starting model), *resolution_limited*, or *unreadable*.

An abstention is information. It says the next move is a better starting model,
not a better interpretation. Do not convert it into a number.

## Supporting evidence

Four sections carry measurements that are not attributions. Each is there
because a fit statistic is blind to it.

- **`FitReport.background`** (`BackgroundEvidence`). A background flexible
  enough to imitate the peaks biases displacement parameters up and scales —
  hence phase fractions — down, *while Rwp improves*. So the flexibility is
  measured directly. `BackgroundEvidence.absorption` is the block projection of
  each structural Jacobian column onto the background column span, which a
  pairwise correlation misses, and
  `BackgroundEvidence.worst_absorption_path` names the parameter worst affected.
  The opposite failure — a background too stiff — shows in
  `BackgroundEvidence.off_region_chi2_reduced` and
  `BackgroundEvidence.off_region_durbin_watson`, which Layer 0's peak-cluster
  regions cannot see by construction.
- **`FitReport.identifiability`** (`Identifiability`). Whether the esds mean what
  they appear to: `Identifiability.top_correlations` (`CorrelationPair`),
  `Identifiability.soft_modes` (`SoftMode`, the softest directions of the normal
  matrix), and `Identifiability.exchangeability`, which lists held parameters
  whose effect a refined one could absorb. An `ExchangeFinding` carries both
  halves of the discriminator, `ExchangeFinding.r2` and
  `ExchangeFinding.partner_significance`, because R² alone is a property of the
  design matrix and fires on clean fits too.
- **`FitReport.lebail_gap`** (`LeBailGap`). `LeBailGap.ratio` is the
  structural-versus-profile triage statistic: how much of the remaining misfit a
  free-intensity fit could remove. A large gap says the problem is the structure,
  not the profile. It is `None` outside Rietveld mode, which is absence for
  cause.
- **`FitReport.restraints`** — what each soft restraint is contributing.

## Layer 2: suggested actions

`FitReport.suggested_actions` is a typed, advisory list. Each `SuggestedAction`
carries `SuggestedAction.kind`, `SuggestedAction.parameter_paths` (the dot-paths
it would free), `SuggestedAction.rationale`,
`SuggestedAction.expected_delta_chi2`, `SuggestedAction.alternatives` and
`SuggestedAction.confidence` — which weights *importance*, the share of χ² at
stake, rather than statistical significance alone. `SuggestedAction.vetoed_by`
records where the staged-strategy engine overruled an action, and
`FitReport.action` looks one up by kind.

Advisory is the design, not a limitation. The package never applies these for
you.

## Reports at every stage

**A converged report is routinely the least informative one in the run.** A plan
absorbs an error it cannot free into whatever it can, and arrives converged with
nothing to suggest, while its own first stage named the cause out loud. So the
report exists at every stage boundary, not only at the end:

<!-- api-doc: no-exec — it refines; the executed version of this is examples/nac_11bm.py -->
```python
result = ref.fit(data, stage_reports=True)
for rung in ref.stage_reports_:
    print(rung.stage, rung.rwp, rung.summary)
```

Each rung is a `StageReport`, with `StageReport.stage`, `StageReport.rwp`,
`StageReport.summary`, `StageReport.actions` and the abstention fields. They are
read off states the plan already visits, so the answer is bit-identical to the
run without them. `FitReport.for_stage` projects a report onto one rung
directly. The flag is off by default in the library, because `fit` is called in
loops.

## Comparing settings with `rietx compare`

"Did that correction help?" is not a question ΔRwp answers. Some corrections
provably cannot move Rwp — capillary absorption is an exact reparameterisation
of the scale and the displacement parameters — and others improve it by
absorbing physics that belongs elsewhere.

`rietx.viz.compare` runs a bundled standard under several settings and renders
the comparison that does settle it:

<!-- api-doc: no-exec — each call runs a full refinement of a bundled standard -->
```python
from rietx.viz import compare

record = compare.run("srm660c", "roughness_suortti")
```

Read the **cumulative Δχ² against the reference** panel rather than the Rwp. It
localises *where* along 2θ the change acted, which is what separates a
correction doing its job from one absorbing someone else's error.
`compare.STANDARDS` and `compare.VARIANTS` are the registries, and
`rietx compare --open` is the same thing with a UI.

The house rule behind all of this: a new correction ships with a record field or
a diagnostic that states what it changed, never with an Rwp comparison as its
evidence.
