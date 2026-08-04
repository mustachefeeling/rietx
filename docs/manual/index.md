# pxrd-refine — theory manual

Release {{ release }}. The equations behind the package, numbered and
cross-referenced, with the conventions that make them transferable — or not
— between Rietveld codes.

## How to read this manual

**The code is authoritative.** Every physics function in `pxrdref` cites
its reference (author, year, journal) in its docstring, and the heavyweight
derivations live in the module docstrings. This manual organises that
material into numbered equations; it does not replace it. Each displayed
equation carries a *Source* line naming the symbol whose docstring it was
transcribed from — where prose here and the docstring ever disagree, the
docstring wins, and the discrepancy is a bug worth reporting.

Two mechanisms keep the manual from drifting: every threshold or fenced
constant quoted here is injected from the live package at build time (a
renamed constant fails the build), and a test imports every *Source*
symbol (a moved function fails the suite).

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
