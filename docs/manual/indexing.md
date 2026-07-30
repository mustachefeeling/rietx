(ch-indexing)=
# Indexing

Refinement starts from a cell. Indexing produces one — from nothing but a
list of line positions — and the chapter's organising fact is how *little*
information that list contains: a powder pattern carries the **length** of
each reciprocal-lattice vector and nothing about its direction. Everything
below follows from that, including the two places where the honest answer
is a refusal.

## The quadratic form

With $(h,k,l)$ assigned to a line, the measured quantity is

```{math}
:label: idx-qform

Q \;\equiv\; \frac{1}{d^2} \;=\; A h^2 + B k^2 + C l^2 + D k l + E h l
+ F h k,
```

*Source:* `pxrdref.crystallography.lattice.inv_d_squared`

where the six coefficients are the reciprocal metric tensor's components

```{math}
:label: idx-af

(A, B, C, D, E, F) \;=\; \bigl(G^*_{11},\, G^*_{22},\, G^*_{33},\,
2G^*_{23},\, 2G^*_{13},\, 2G^*_{12}\bigr).
```

*Source:* `pxrdref.indexing.qspace.design_matrix`

$Q$ is **linear** in $(A \ldots F)$ {cite}`itc-h-indexing`, and that is
load-bearing three times over: fitting a cell to assigned lines is a
weighted *linear* least-squares problem; a trial-and-error engine solving
for $n$ metric parameters from $n$ base lines is an exact $n \times n$
solve; and a dichotomy engine's bounds on $Q$ over a box of cell
parameters are attained at box *corners*, so the search runs in
$(A \ldots F)$. Neither $d$ nor $2\theta$ is linear in the metric — which
is why indexing works in $Q$ and reports in $Q$, converting to a cell only
at the end.

Positions and their esds enter as $Q$ and $\sigma(Q)$, propagated by the
exact derivative

```{math}
:label: idx-sigma-q

\sigma(Q) \;=\; \frac{\pi}{90}\,
\frac{\lvert \sin 2\theta \rvert}{\lambda^2}\, \sigma(2\theta),
```

*Source:* `pxrdref.schemas.indexing.q_esd_of_two_theta`

whose constant is worth reading twice: differentiating $Q = 4\sin^2\theta /
\lambda^2$ with respect to $2\theta$ **in degrees** picks up both the
$\theta = (2\theta)/2$ chain and the degree conversion, and applying only
one of the two gives $\pi/180$ — a factor-of-two error that makes every
line's weight four times too confident.

## The symmetry-allowed subspace

A crystal system constrains the metric. The allowed $G^*$ patterns are the
invariants of the lattice point group acting as $A(R)[U] = R\,U\,R^\top$,

```{math}
:label: idx-subspace

\mathcal{M} \;=\; \bigcap_{R \in \mathcal{G}} \ker\bigl(A(R^\top) -
I\bigr),
```

*Source:* `pxrdref.indexing.qspace.metric_basis`

which is the *same* exact-rational nullspace the anisotropic-ADP basis uses
one rank down, called with the **transposed** rotations because the
reciprocal-space symmetry action is $R^\top$. Its dimension is the number
of free metric parameters: 1 cubic, 2 tetragonal, 2 hexagonal, 2 trigonal,
3 orthorhombic, 4 monoclinic, 6 triclinic. Deriving rather than tabulating
it is what keeps a non-standard setting — rhombohedral axes, a $b$-unique
monoclinic cell — correct with no case table.

## What a peak list can and cannot support

A line count is not a criterion on its own: {{ MIN_LINES_PER_DOF }} usable
lines *per free metric parameter* means 20 lines is 20-fold
over-determined for a cubic cell and 3.3-fold for a triclinic one, so the
data-quality report names the systems it can support rather than answering
yes or no. Positional precision enters as a resolving power, median
$\sigma(Q)/Q$, above {{ MAX_RELATIVE_SIGMA_Q }} at which two cells
differing by 0.1 % in a lattice parameter are indistinguishable — the scale
at which derivative-lattice ambiguity lives.

A systematic $2\theta$ shift is the failure mode both indexing benchmarks
single out {cite}`bergmann2004`. Three physical causes give three angular
dependences — a constant (detector zero point), $\cos\theta$ (specimen
displacement), $\sin 2\theta$ (specimen transparency) — and they are fitted
**one at a time**, never jointly, because a joint fit of collinear
templates returns physically absurd cancelling amplitudes. A cause is named
only when the runner-up leaves at least twice as much variance unexplained;
otherwise the magnitude is reported and the cause is not. Note what is
*not* in that basis: a $\tan\theta$ deviation is a **cell** error, and
offering it to a shift screen would let the screen explain a shift by
changing the answer indexing is about to produce.

## Volume from one line

An upper envelope on the cell volume follows from the number of distinct
lines a lattice of that volume can show above a given $d$
{cite}`smith1977`:

```{math}
:label: idx-volume

V \;\lesssim\; \frac{0.6\, d_N^3}{1/N - 0.0052},
```

*Source:* `pxrdref.indexing.quality.volume_envelope`

which at $N = 20$ is $V \lesssim 13.39\, d_{20}^3$ for a **primitive
triclinic** lattice. Two scalings are needed before it can bound a search
in another system, and both are about the same thing — the published form
counts *distinct* lines: a high-symmetry lattice merges reflections into
orbits, and a centred one extinguishes them. A cubic $F$ lattice of a given
volume shows some 96 times fewer distinct lines than a primitive triclinic
one, so applying the printed constant to a cubic search bounds the volume
96-fold too tightly and excludes the true cell. Since the centring is part
of the answer, the bound uses the loosest centring each system admits.

## Figures of merit, in both directions

The classical figures are de Wolff's {cite}`dewolff1968`

```{math}
:label: idx-m20

M_{20} \;=\; \frac{Q_{20}}{2\,\overline{\lvert \Delta Q \rvert}\,
N_{\mathrm{poss}}},
```

*Source:* `pxrdref.indexing.fom.m20`

and Smith & Snyder's {cite}`smithsnyder1979`

```{math}
:label: idx-fn

F_N \;=\; \frac{1}{\overline{\lvert \Delta 2\theta \rvert}} \cdot
\frac{N_{\mathrm{obs}}}{N_{\mathrm{poss}}},
```

*Source:* `pxrdref.indexing.fom.f_n`

where $N_{\mathrm{poss}}$ counts the lines the *lattice* allows up to the
$N$-th observed one, and both means run over every one of those $N$ lines
assigned to its nearest calculated line. Each mean is floored at the
measured precision, which is this package's addition and not the papers':
the figures divide by a discrepancy, so on data a lattice fits to within
floating-point noise they diverge, and a naive zero-guard then ranks a
*perfect* cell last. A discrepancy smaller than $\sigma$ is not knowable,
and per-line $\sigma$ is what a fitted peak list has and 1968 did not.

Both figures share a blind spot with the fraction of observed lines
indexed: a large enough cell has a line near everything. The measured case
that fixes the design is in this project's own prior art — a wrong phase
ranked *first* on share of observed intensity indexed, 83.7 %, with 390
predicted lines of which 9.0 % were present, above the truth's 79.2 % with
56.5 % of its own 23 lines seen. So coverage is scored in **both**
directions, the reverse direction being the fraction of a candidate's
predicted lines that are actually present {cite}`oishitomiyasu2013`, and
the ranking is a Borda count over the whole panel rather than a sort on any
member. Every figure of merit is reported with the blind spot attached to
the number, because a value read without it is one step from a confident
wrong answer.

## Ambiguity, which is reported and not resolved

Distinct lattices can give identical calculated line *positions*
{cite}`mighellsantoro1975`. The pattern carries $\lvert \mathbf{h}
\rvert$ only, so no counting statistics separate them: the information is
absent from the measurement rather than buried in its noise. Candidate
partners are the derivative lattices, enumerated exactly as the integer
matrices in Hermite normal form of index up to
{{ MAX_AMBIGUITY_INDEX }},

```{math}
:label: idx-hnf

H \;=\; \begin{pmatrix} a & b & c \\ 0 & d & e \\ 0 & 0 & f
\end{pmatrix}, \qquad a d f = n, \quad 0 \le b < d, \quad 0 \le c,e < f,
```

*Source:* `pxrdref.indexing.ambiguity.hnf_matrices`

whose closed sets have 7, 13 and 35 members at $n = 2, 3, 4$ — a count the
implementation is checked against. Each partner's metric follows from
$G' = H\,G\,H^\top$; those that Niggli-reduce back to the parent are
*setting changes* and are dropped, which is what keeps ambiguity distinct
from de-duplication. What makes the surviving report actionable rather than
merely honest is the list of **discriminating reflections**: the $hkl$, and
the $2\theta$, where the partner and the parent differ — the structural twin
of a fit report saying "extend the range".

De-duplication itself is a $\chi^2$ test on the Niggli-reduced
$(A \ldots F)$ against $\chi^2_6$ at 99 %, using the two candidates' joint
covariance, rather than a fixed percentage: a percentage merges distinct
synchrotron cells and splits noisy laboratory ones. Lattice symmetry is
decided by **two independent opinions** — a Le Page 2-fold search
{cite}`lepage1982` with a tolerance in degrees of obliquity, and a
distance-tolerance standardisation {cite}`togo2024` — swept over their
tolerances, with the answer taken as the symmetry stable across the sweep
and anything appearing only at the loosest tolerance reported as ambiguous.
Agreement between independent methods is the confidence; disagreement is
reported rather than averaged.
