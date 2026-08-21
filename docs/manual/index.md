# rietx manual

Release {{ release }}. The manual is in two parts.

**Part 1 — Using rietx** is the task-ordered guide to the package and its
public API: install it, run a fit, understand what the fit did, read the report
it hands back, and drive it from a program. It assumes you know powder
diffraction and not this package.

**Part 2 — Theory** is the equations behind that machinery, numbered and
cross-referenced, with the conventions that decide whether a number transfers
between Rietveld codes.

## Who this is written for

This manual is written for a person to read.

Parts of the package are not. `rietx` is built for automated and agentic
workflows, and several of its surfaces are shaped for a program to read first:
the `FitReport` and its three layers, `agent.refine_json` and its JSON
envelope, `capabilities()`, the streaming event ladder, and the diagnostic
codes. They are documented here because a person has to understand them to
trust, debug or extend what a machine does with them. `FitReport` also answers
a question anyone looking at a plot has: where is this model wrong, and how
much of that will the package stand behind?

Notes about that half carry a marker, so you can see at a glance who a
paragraph is addressed to:

:::{admonition} For agents
:class: agent
This style marks the machine-facing half. Read these notes if you are an agent,
or are writing one. Skip them if you are refining a pattern.

If you are an agent reading this manual, read
[`docs/AGENT_PROTOCOL.md`](https://github.com/yue-here/rietx/blob/main/docs/AGENT_PROTOCOL.md)
first, then come back here for the object model. The protocol says what to do
in what order, what to check before believing a number, and which measured
findings should change what you do. This manual describes the surface, and
nothing here restates the protocol.
:::

## How to read this manual

**The code is authoritative.** Every physics function in `rietx` cites its
reference — author, year, journal — in its docstring, and the long derivations
live in the module docstrings. This manual organises that material into
numbered equations in Part 2 and into a task order in Part 1. It does not
replace it. Where this manual and a docstring disagree, the docstring wins, and
the disagreement is a bug worth reporting.

Both parts are guarded against drifting from the code, by different mechanisms,
because they fail in different ways. In Part 2 every threshold and fenced
constant is injected from the live package when the manual builds, so a renamed
constant breaks the build; each displayed equation carries a *Source* line
naming the symbol it was transcribed from, and a test imports every one of
them. In Part 1 every dotted name and every parameter dot-path resolves against
the live package, every fenced example either runs or states why it cannot, and
the walkthroughs are scripts from `examples/` included verbatim and executed by
the test suite.

**Names follow Python's own convention, so their case tells you what they
are.** `Refinement`, `RefinementResult` and `FitReport` are capitalised because
they are *classes*. `refine`, `read_pattern` and `capabilities` are functions,
`rietx.viz.compare` is a module, and `PLAN_INFO` is a module-level constant. A
capital does not mean a name matters more.

One consequence changes what you type. A method or a field is written under the
class that defines it, not under the variable you would hold it in.
`RefinementResult.plot` means "the `plot` method of a `RefinementResult`", and
in your own code that line reads `result.plot(...)`. Written this way the name
resolves, which is what lets the test suite check every name in Part 1 against
the live package.

Parameter dot-paths are the other dotted thing here, and they are never
capitalised. `phases.0.cell.a` and `instrument.profile.w` are *data* —
addresses into the parameter table, not attributes of a class.

## Part 1 — Using rietx

The chapters run in the order a first session with the package runs: install
it, get one fit to the end, learn what the three objects hold, learn how their
parameters are addressed and edited, learn why a fit is staged, run one and
control it, read the numbers it returned, read the report on top of them, go
back to any state it passed through, find out what is on disk, find the cell
when the specimen is unknown, refine a whole set of patterns rather than one,
find out how much of each phase there is, take the tables away, reach the few
jobs that belong in a terminal, then wire it into something. The closing chapter
is the 1.0 stability promise.

```{toctree}
:caption: Part 1 — Using rietx
:maxdepth: 2

using/install
using/quickstart
using/data
using/model
using/concepts
using/constraints
using/refining
using/results
using/report
using/history
using/files
using/indexing
using/series
using/qpa
using/exports
using/cli
using/agents
using/compatibility
```

## Part 2 — Theory

**Conventions are stated by physics, never by letters.** Rietveld codes
disagree on letter assignments (GSAS and FullProf swap the size and strain
terms X and Y), on sign conventions (March-Dollase $r$), on normalisations
(Stephens $S_{HKL}$, three independent choices), and on whether a table prints
a transmission $A$ or its reciprocal $A^*$. Wherever a number could be
transferred from the literature or from another code, the convention warning
sits beside the equation. Transfer a value by matching the physics — the
θ-law, the limit, the sign of the effect — never the symbol.

**Scope.** Constant-wavelength X-ray powder data. Fundamental-parameters
profiles, neutron and time-of-flight data, and spherical-harmonics texture are
not implemented today. They are planned for v2, behind seams the forward model
already carries; nothing in Part 2 describes them.

```{toctree}
:caption: Part 2 — Theory
:maxdepth: 2
:numbered:

forward-model
peak-positions
profiles
intensities
corrections
microstructure
background
estimation
parameterisation
indexing
engines
method
```

## Citing rietx

If rietx contributed to published work, cite {cite}`rietx2026`. The
repository carries the same record as `CITATION.cff`, which reference
managers and GitHub's "cite this repository" button read directly.

## Bibliography

```{bibliography}
```
