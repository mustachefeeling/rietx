# pxrd-refine

**API-first Rietveld refinement of powder X-ray diffraction data, designed for
automated and agentic workflows.**

`pxrd-refine` is an MIT-licensed Python package for Rietveld and Le Bail
refinement built as a library first — no GUI trees, no pickles, no hidden
state:

- **Typed, JSON-round-trippable schemas** (pydantic v2) for structures,
  instruments, patterns, plans, and results. Every schema exports JSON Schema
  for LLM tool-calling; unknown fields fail loudly with actionable errors.
- **numpy + scipy float64 core** (~50 MB install). Optional autodiff/GPU
  backends (JAX first) are on the roadmap; the forward model is written to
  stay differentiable (frozen reflection lists and evaluation windows per
  refinement stage, smooth reparameterisations, no clamps in the graph).
- **Documented mathematics**: every implemented equation cites its literature
  reference in the docstring (Rietveld 1969; Caglioti 1958; Thompson-Cox-
  Hastings 1987; Waasmaier-Kirfel 1995; Toby 2006; Le Bail 1988; …).
  See `ATTRIBUTION.md` for the full source/license map.
- **Automation-first background handling**: arPLS (banded Whittaker) and SNIP
  estimators plus shifted-Chebyshev refinable backgrounds with exact analytic
  Jacobian columns.
- **Staged refinement strategies** following the IUCr guidelines
  (McCusker et al., 1999), with correlation and bound-hit guards.
- **Agent-native fit assessment**: the `FitReport` returns *numbers, not
  pixels* — cumulative-χ² breakpoints, per-region local Rwp / χ² share, and
  unmatched-peak lists that flag impurity phases — so an agent can close the
  refinement loop without reading a plot image.

## Status: v0.1 (pre-alpha)

Working today (constant-wavelength X-ray, Debye-Scherrer/capillary geometry):

| Capability | State |
|---|---|
| Rietveld & Le Bail modes, multi-phase | ✅ |
| CIF import/export (gemmi), space-group symmetry, absences, multiplicities | ✅ |
| TCHZ pseudo-Voigt + Caglioti/size/strain widths, Lp correction | ✅ |
| Chebyshev + arPLS/SNIP backgrounds | ✅ |
| Bounded TRF least squares, esds + correlation matrix, Rwp/GoF/Durbin-Watson | ✅ |
| Staged plans (`mccusker_default`, `profile_only`, custom) | ✅ |
| FitReport Layer 0 (model-free diagnostics) | ✅ |
| `.xy` / `.xye` / GSAS `.fxye/.gsas` readers | ✅ |
| obs/calc/difference/tick plot (matplotlib) | ✅ |
| Kα1/Kα2 doublet, FCJ axial asymmetry, Bragg-Brentano geometry | v0.2 |
| Atomic-coordinate refinement (Wyckoff constraints), QPA, Pawley | v0.2-0.3 |
| JAX backend (autodiff Jacobians, GPU), FitReport misfit attribution | v0.4 / v0.2 |

### Validation

The acceptance suite refines real APS 11-BM synchrotron data of the NAC
(Na₂Ca₃Al₂F₁₄) line-profile standard: Le Bail then two-phase Rietveld
converge to **a = 10.251285(12) Å, Rwp = 9.2%**, with the Layer-0 FitReport
correctly flagging the sample's CaF₂ impurity phase from its unmatched peaks
(fluorite 111/220/311/422). Synthetic round-trip tests recover known
parameters within uncertainties. Run `pytest` (fast) or
`python examples/nac_11bm.py` (full walkthrough with plot).

## Example

```python
import pxrdref as pr

data = pr.read_pattern("11BM_NAC.fxye")                  # esds read from file
structure = pr.Structure.from_cif("NAC.cif")
instrument = pr.Instrument.debye_scherrer(wavelength=0.4139090)

# Structure-free Le Bail first: cell + profile + background
ref = pr.Refinement(structure, instrument)
lebail = ref.fit(data, mode="lebail", two_theta_limits=(2, 24))

# Rietveld with the standard staged turn-on order (McCusker et al. 1999)
result = ref.fit(data, plan="mccusker_default", two_theta_limits=(2, 24))
print(result.statistics.rwp, result.statistics.gof)
print(result.parameter("phases.0.cell.a"))               # value ± stderr

report = pr.build_report(result)                          # agent-native JSON
print(report.summary)                                     # regions, unmatched peaks
result.plot(path="fit.png")                               # obs/calc/diff/ticks
```

Everything is JSON-serialisable end to end:
`structure.model_dump_json()` / `Structure.model_validate_json(...)`, and the
same for instruments, plans, results, and reports.

## Install (development)

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"
pytest              # 31 tests incl. real-data acceptance, ~5 s
ruff check src tests examples
```

Extras: `[viz]` (matplotlib, plotly), `[baselines]` (pybaselines algorithm zoo).

## Architecture (one paragraph)

Pydantic schemas are the source of truth. `params/vector.py` compiles the
model tree once per stage into a flat float64 vector (crystal-system cell
ties applied as identity constraints; softplus/logit transforms keep widths,
scales, and occupancies physical). `model/forward.py` freezes the reflection
list, symmetry-operation orbits, and per-reflection evaluation windows for
the stage, then evaluates y_calc = background + Σ intensity·profile.
`optimize/least_squares.py` drives scipy's bounded TRF with mixed
analytic/finite-difference Jacobians and derives esds from the covariance
matrix. `strategy/staged.py` walks the turn-on plan, regenerating frozen
state between stages. `report.py` turns the result into machine-readable
diagnostics.

## License

MIT. Algorithms are independent implementations from the published
literature; inspiration sources and data provenance are documented in
`ATTRIBUTION.md` and `tests/data/README.md`. GPL codebases (BGMN, Profex,
xrayutilities) were studied conceptually only — no code was ported.
