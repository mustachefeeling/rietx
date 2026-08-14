# rietx — manual

Release {{ release }}. The manual is in two parts.

**Part 1 — Using rietx** is the task-ordered guide to the package and its
public API: install it, run a fit, read the report it hands back, and drive
it from a program or an agent loop. It assumes you know powder diffraction
and not this package.

**Part 2 — Theory** is the equations behind that machinery, numbered and
cross-referenced, with the conventions that make them transferable — or not
— between Rietveld codes.

Read Part 1 to use the package. Part 2 is where Part 1 sends you when a
number has to be defended, rather than a prerequisite for either.

## How to read this manual

**The code is authoritative.** Every physics function in `rietx` cites
its reference (author, year, journal) in its docstring, and the heavyweight
derivations live in the module docstrings. This manual organises that
material — into numbered equations in Part 2, into a task order in Part 1;
it does not replace it. Where prose here and a docstring ever disagree, the
docstring wins, and the discrepancy is a bug worth reporting.

Both parts are guarded against drifting from the code, by mechanisms suited
to what each carries. In Part 2, every threshold or fenced constant quoted is
injected from the live package at build time (a renamed constant fails the
build), and each displayed equation carries a *Source* line naming the symbol
whose docstring it was transcribed from — a test imports every one of them, so
a moved function fails the suite. In Part 1, every dotted name and every
parameter dot-path resolves against the live package, every fenced example
either runs or says why it does not, and the walkthroughs are scripts from
`examples/` included verbatim and executed by the test suite.

## Part 1 — Using rietx

Ordered as a first session with the package runs: get it installed, get one
fit to the end, learn to read what came back, then wire it into something.

:::{note}
Part 1 is the reference and the on-ramp. It is not the operating protocol:
what to do in what order, what to check before believing a number, and the
measured findings that change an operator's behaviour live in
`docs/AGENT_PROTOCOL.md`, and these chapters link to it rather than
paraphrasing it.
:::

## Part 2 — Theory

**Conventions are stated by physics, never by letters.** Rietveld codes
disagree on letter assignments (GSAS and FullProf swap the size/strain
X/Y), on sign conventions (March-Dollase $r$), on normalisations (Stephens
$S_{HKL}$, three independent choices), and on whether a table prints a
transmission $A$ or its reciprocal $A^*$. Wherever a number could be
transferred from the literature or another code, the applicable convention
warning is beside the equation. Transfer values by matching the physics —
the θ-law, the limit, the sign of an effect — never the symbol.

**Scope.** Constant-wavelength X-ray powder data. Fundamental-parameters
profiles, neutron/TOF, and spherical-harmonics texture are out of scope
(deferred, not planned).

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

## Bibliography

```{bibliography}
```
