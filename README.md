# rietx

[![CI](https://github.com/yue-here/rietx/actions/workflows/ci.yml/badge.svg)](https://github.com/yue-here/rietx/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/rietx)](https://pypi.org/project/rietx/)

Rietveld refinement of powder X-ray diffraction data, driven from code: a
typed, JSON-round-trippable Python library with staged refinement plans, an
analytic Jacobian, and a fit report built for a program to act on. MIT
licensed.

It is for people who refine powder data from a script, a beamline pipeline, an
autonomous lab or an agent loop, and for interactive users who want the same
machinery with a local GUI over it.

## Install

```sh
pip install rietx            # Python >= 3.11; numpy/scipy core
pip install "rietx[viz]"     # + matplotlib and plotly rendering
```

CI runs the fast suite on Linux for Python 3.11, 3.12, 3.13 and 3.14, and
nightly on Windows and macOS.

## One fit, end to end

Condensed from [`examples/nac_11bm.py`](https://github.com/yue-here/rietx/blob/main/examples/nac_11bm.py),
which fits APS 11-BM synchrotron data on Na₂Ca₃Al₂F₁₄ with a CaF₂ impurity.
The scripts in [`examples/`](https://github.com/yue-here/rietx/tree/main/examples)
are the one authority for a walkthrough: the manual includes them verbatim and
the test suite executes them.

```python
import rietx as rx

data = rx.read_pattern("11BM_NAC.fxye")              # esd column read from file
structure = rx.Structure.from_cif("cod_1000236.cif")
instrument = rx.Instrument.debye_scherrer(wavelength=0.4139090)

ref = rx.Refinement(structure, instrument)

# structure-free Le Bail first: cell + profile + background
lebail = ref.fit(data, mode="lebail", two_theta_limits=(2, 24))

# then Rietveld under the staged turn-on order of McCusker et al. (1999)
result = ref.fit(data, plan="mccusker_default", two_theta_limits=(2, 24))

report = rx.build_report(result)                     # numbers, not pixels
result.plot(path="fit.png")                          # obs/calc/diff/ticks
```

Output of the full script (trimmed at the `…`):

```text
Le Bail:  status=converged  Rwp=0.1457  GoF=5.52  a=10.251214 A
Rietveld: status=converged  Rwp=0.0932  GoF=3.53
          a = 10.251216 +/- 0.000046 A (COD reference 10.257(1); high-accuracy powder ~10.2497-10.2506)
          [warning] BOUND_HIT: phases.1.atoms.0.biso refined to its bound

FitReport: Rwp=0.0932 GoF=3.53; 52 regions, top 15 shown (74% of χ²); 54 unmatched observed peak(s); …
  region  14.22- 14.54 deg  localRwp=0.154  chi2share=13.6%  max|d/sig|=49.5
  …

Refinement history (every stage is a restorable checkpoint):
t5544a638  13 nodes  data=11BM_NAC.fxye
 n0000  root                   —
└─  n0001  stage:bkg              Rwp 3.1725
   …
                                 └─ *n0012  stage:biso             Rwp 0.0932
```

## What it does

Each clause links to its manual chapter or worked example.

- Rietveld, Le Bail and Pawley modes, multi-phase, with
  [staged plans](https://yue-here.github.io/rietx/using/concepts.html)
  following the IUCr guidelines, correlation, bound and background guards, and
  crystal-system and site-symmetry constraints wired automatically.
- A [forward model](https://yue-here.github.io/rietx/forward-model.html) with
  documented physics: TCHZ and true-Voigt profiles, FCJ axial asymmetry, Kα
  doublets on the NIST SRD 128 scale, anomalous dispersion on by default,
  capillary and flat-plate absorption, preferred orientation, extinction,
  surface roughness, anisotropic ADPs and Stephens anisotropic strain. Every
  physics function cites author, year and journal in its docstring.
- Bounded least squares (scipy TRF, or an LM driver carrying
  linear-inequality constraints) with an analytic Jacobian and
  Bérar-Lelann-inflated esds. The manual chapter is
  [how the numbers are estimated](https://yue-here.github.io/rietx/estimation.html).
- [Pattern readers](https://yue-here.github.io/rietx/using/files.html) for
  `.xy`/`.xye`, GSAS raw, pdCIF, `.chi`, Rigaku `.ras`/`.rasx`, Bruker
  `.uxd`/`.brml`/`.raw` and PANalytical `.xrdml`, dispatched on content, with
  a structured diagnostic for every repair a reader makes. Exporters for
  reflection tables, refinement CIF and QPA tables.
- A three-layer [`FitReport`](https://yue-here.github.io/rietx/using/report.html):
  model-free diagnostics, misfit attributed to physical causes, and typed
  suggested actions. Every layer is gated to abstain rather than guess.
- A branchable [refinement history](https://yue-here.github.io/rietx/using/files.html)
  in which every stage auto-commits a restorable node: checkout, branch,
  merge, cherry-pick, replay. Multi-histogram joint fits, and warm-started
  sequential series for in-situ and parametric runs, with a
  forward-vs-backward path-dependence check, because a chained trajectory is
  path-dependent by construction.
- [Unit-cell indexing](https://yue-here.github.io/rietx/using/indexing.html): peak
  picking with esds, three consensus-gated search engines, whole-profile
  Le Bail validation and extinction-symbol ranking, behind an API that cannot
  express a confident wrong singleton.
- [Surfaces for agents](https://yue-here.github.io/rietx/using/agents.html):
  `rietx.agent.refine_json` (one JSON call, schema generated from the live
  registries), `capabilities()`, streaming events, and cooperative
  cancellation.
- A local refinement GUI, `rietx gui`: import, edit, refine, inspect, branch,
  export, as a Svelte build served by a stdlib HTTP server on 127.0.0.1, so
  nothing leaves the machine. The GUI ships as a beta. Its panels are still
  moving, it is deliberately undocumented at 1.0, and the API rather than the
  GUI carries the stability promise.

## What it does not do

- Constant-wavelength X-ray only, in three geometries (capillary,
  Bragg-Brentano, flat-plate transmission). Fundamental-parameters profiles,
  neutron and time-of-flight data, and spherical-harmonics texture are planned
  for v2 and not implemented today. See the
  [manual's scope statement](https://yue-here.github.io/rietx/).
- Indexing returns cells and ranked extinction symbols, not solved
  structures, and it is still under active development: its Python surface is
  documented in full and declared provisional, so those names may change in a
  1.x release.
- A sequential series is session-scoped at 1.0: its trajectories are returned,
  not persisted. The GUI's HTTP routes and its text document are provisional.
  The full list is in the
  [compatibility promise](https://yue-here.github.io/rietx/using/compatibility.html).

## Validation

Ten real-data acceptance suites run in CI, each tolerance chosen to match what
its reference actually is: a certified value, another code's converged result,
a published participant spread, or a pre-registered prediction. NIST SRM 660c
LaB₆ lands +28 ppm from NIST's cell recomputed for that dataset. The GSAS-II
fluorapatite tutorial agrees with GSAS's own fit within 116 ppm on the same
5750 channels. The IUCr QPA round robin comes back with a worst case of
1.39 wt% once anomalous dispersion is applied, a parameter-free correction
whose effect was written down before the refits.
[docs/VALIDATION.md](https://github.com/yue-here/rietx/blob/main/docs/VALIDATION.md)
is the full matrix, generated from the test suite so it cannot drift from what
is actually asserted; the SRM 660c gap to the certificate's ±8×10⁻⁶ Å band is
documented there rather than tuned away.

## Documentation

- [The manual](https://yue-here.github.io/rietx/). Part 1 is the task-ordered
  guide to the library: install, one fit, the objects a fit takes, the
  parameter table over them, what the fit did, the numbers, the report, what is
  on disk, finding the cell when the specimen is unknown, driving it from a
  program, and the compatibility promise. Part 2 is the theory, with numbered equations transcribed from the
  physics docstrings and the convention warnings that decide whether a number
  transfers between Rietveld codes.
- [AGENT_PROTOCOL.md](https://yue-here.github.io/rietx/AGENT_PROTOCOL.md), the
  operating protocol for agents: turn-on order, degeneracies, and what each
  diagnostic code forbids you from reporting. It also ships inside the wheel as
  `rietx/data/AGENT_PROTOCOL.md`, so it resolves with no network.
- Release notes for
  [1.0.1](https://github.com/yue-here/rietx/blob/main/docs/releases/1.0.1.md)
  and [1.0.0](https://github.com/yue-here/rietx/blob/main/docs/releases/1.0.0.md),
  and the [compatibility promise](https://yue-here.github.io/rietx/using/compatibility.html).
  The data contracts (schemas, the agent envelope, the project format, the
  event stream) are frozen at 1.0. The Python call surface freezes as the
  manual documents it, with declared exceptions — indexing is still under
  active development, so its names are documented and provisional.

## Development

```sh
git clone https://github.com/yue-here/rietx && cd rietx
uv venv --python 3.12 && uv pip install -e ".[dev]"
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # ~1-3 min
.venv/bin/python -m pytest -n auto --dist loadgroup                 # + real-data acceptance, ~15-30 min
.venv/bin/python -m ruff check src tests examples
```

`--dist loadgroup` is not optional: it keeps shared expensive fixtures on one
worker. Wall clock is quoted as a range on purpose, because machine state moves
it further than most changes do. See
[CONTRIBUTING.md](https://github.com/yue-here/rietx/blob/main/CONTRIBUTING.md)
for the test ladder and style, and
[AGENTS.md](https://github.com/yue-here/rietx/blob/main/AGENTS.md) if your
contributor is an agent.

## License and credits

MIT. Algorithms are independent implementations from the published literature,
and every physics function cites author, year and journal. The source and
licence map is
[ATTRIBUTION.md](https://github.com/yue-here/rietx/blob/main/ATTRIBUTION.md),
and test-data provenance is
[tests/data/README.md](https://github.com/yue-here/rietx/blob/main/tests/data/README.md).
CIF and symmetry handling is
[gemmi](https://github.com/project-gemmi/gemmi). To cite the package, use
[CITATION.cff](https://github.com/yue-here/rietx/blob/main/CITATION.cff).
