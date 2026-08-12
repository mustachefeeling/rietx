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

*Source:* `anatase.crystallography.lattice.inv_d_squared`

where the six coefficients are the reciprocal metric tensor's components

```{math}
:label: idx-af

(A, B, C, D, E, F) \;=\; \bigl(G^*_{11},\, G^*_{22},\, G^*_{33},\,
2G^*_{23},\, 2G^*_{13},\, 2G^*_{12}\bigr).
```

*Source:* `anatase.indexing.qspace.design_matrix`

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

*Source:* `anatase.schemas.indexing.q_esd_of_two_theta`

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

*Source:* `anatase.indexing.qspace.metric_basis`

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

### Which lines drive the search

A search is *driven* by {{ DEFAULT_SEARCH_LINES }} lines and *scored* against
every usable one. Conograph argues the driven set should be large — 48 rather
than the 20–30 its contemporaries used — on the grounds that a **missing** line
costs success while a **false** line costs only computation, because its
enumeration succeeds by a membership condition on the observed $q$ set and
adding elements cannot break one {cite}`oishitomiyasu2014`.

That asymmetry does not transfer here, and the reason is worth stating because
it is a property of the *acceptance rule* rather than of the enumeration. A
candidate is accepted only if it indexes all but {{ DEFAULT_N_UNINDEXED }} of
the driven lines — an absolute budget, not a membership test — so each foreign
line admitted spends that budget, and past it the true cell is **refused**
rather than out-ranked. Enlarging the driven set therefore has a failure mode
Conograph's does not, and measurement bears it out: on a 68-line lab pattern
carrying 16 foreign lines, going from 20 driven lines to 32 loses the certified
lattice from the candidate list altogether.

What does pay is *which* lines, not how many. The driven set is taken in order
of integrated intensity, with ties broken by $Q$, so a pattern whose low-angle
range opens on background does not spend its whole budget there — on a
synchrotron pattern beginning at $0.76^\circ\ 2\theta$ the twenty lowest-angle
components contain six of the true cell's lines, where the strongest twenty
contain eighteen. A list of bare positions carries no measured intensities, so
every line ties and the order reduces exactly to ascending $Q$: an assumed
intensity may no more reorder a search than an assumed $\sigma$ may refuse one.

The rank is applied within the lowest {{ SEARCH_POOL_MULTIPLE }}$N$ lines rather
than over the whole list, and the reason is cost rather than physics. A
branch-and-bound search sizes the trial reflection set it tests each box against
by the largest $Q$ among the driven lines, so letting the rank reach a lab
pattern's high-angle tail enlarges that set for every box in the recursion. The
bound recovers about half of what the rank costs, at a few lines of selection
quality: unbounded, the same synchrotron list scores twenty of twenty.

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

### The shift is measurable before the cell is

Fitting those templates needs reference positions, and before indexing there
is no cell to deviate from. It is tempting to conclude that the shift is
therefore unknowable until afterwards; that conclusion is **false**, and
correcting it is what lets a search widen its window by a measurement rather
than by an assumption.

Two reflections form a **reflection pair** when their planes are harmonics of
one another, $(h'k'l') = m\,(hkl)$ with $m$ integer, so that
$d_{hkl} = m\,d_{h'k'l'}$ *exactly*. Bragg's law then relates their angles
with no reference to the cell, the crystal system or the indices — the
relation follows from the lattice being self-consistent, not from which
lattice it is:

```{math}
:label: idx-pair

m \sin\theta_B \;=\; \sin\theta'_B .
```

*Source:* `anatase.indexing.pairs.pair_shift`

Writing $2\theta_B = 2\theta_\mathrm{obs} + 2\theta_z$ for a constant shift and
solving {cite}`dong1999`:

```{math}
:label: idx-pair-shift

2\theta_z \;=\; 2\arctan\!\left[
  \frac{\sin\theta' - m\sin\theta}{m\cos\theta - \cos\theta'} \right].
```

*Source:* `anatase.indexing.pairs.pair_shift`

Each pair is thus one equation in the shift and none in the cell. Substituting
a general $2\theta_B = 2\theta_\mathrm{obs} - c\,T(2\theta_\mathrm{obs})$
instead of a constant leaves a scalar equation in the amplitude $c$ of any of
the three templates, solved by Newton.

Two cautions govern how the result may be read. Real harmonic pairs agree on
$c$ while accidental ones — any two lines whose sine ratio happens to fall near
an integer — scatter, so a shift is reported only when the agreement is
significant against a **structureless null** of the same size; on a bare
twenty-line list the supply of pairs collapses and the honest answer is to
decline. And the pair evidence measures a **magnitude**, not a cause: the
constant and $\cos\theta$ templates concentrate equally well on real data, so a
pair screen may refute $\sin 2\theta$ and may not choose between the other two.

## Volume from one line

An estimate of the cell volume follows from the number of distinct
lines a lattice of that volume can show above a given $d$
{cite}`smith1977`:

```{math}
:label: idx-volume

V \;\approx\; \frac{0.6\, d_N^3}{1/N - 0.0052},
```

*Source:* `anatase.indexing.quality.volume_envelope`

which at $N = 20$ is $V \approx 13.39\, d_{20}^3$ for a **primitive
triclinic** lattice. Two scalings are needed before it can bound a search
in another system, and both are about the same thing — the published form
counts *distinct* lines: a high-symmetry lattice merges reflections into
orbits, and a centred one extinguishes them. A cubic $F$ lattice of a given
volume shows some 96 times fewer distinct lines than a primitive triclinic
one, so applying the printed constant to a cubic search bounds the volume
96-fold too tightly and excludes the true cell. Since the centring is part
of the answer, the bound uses the loosest centring each system admits.

**It is a mean line, not an envelope, and the distinction is a live one.**
Smith fits equation {eq}`idx-volume` by least squares to some forty
well-determined triclinic patterns and reports an average discrepancy of
10.6 %, with deviations running from 32 % too high to **29 % too low** —
the low side being the ordinary case, since it is what missing weak lines
produce. Writing $p$ for the fraction of possible lines actually detected,
the bound stands in ratio $1.40\,p$ to the truth, so it excludes the true
cell below $p = 0.71$ — and $1 - 0.71$ is Smith's own worst case. Used as a
hard search ceiling the relation therefore has no margin at all against the
worst pattern in its own calibration set, and the slack that makes it safe
is this package's to supply, not the paper's.

## Figures of merit, in both directions

The classical figures are de Wolff's {cite}`dewolff1968`

```{math}
:label: idx-m20

M_{20} \;=\; \frac{Q_{20}}{2\,\overline{\lvert \Delta Q \rvert}\,
N_{\mathrm{poss}}},
```

*Source:* `anatase.indexing.fom.m20`

and Smith & Snyder's {cite}`smithsnyder1979`

```{math}
:label: idx-fn

F_N \;=\; \frac{1}{\overline{\lvert \Delta 2\theta \rvert}} \cdot
\frac{N_{\mathrm{obs}}}{N_{\mathrm{poss}}},
```

*Source:* `anatase.indexing.fom.f_n`

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

Two of the panel's inputs are deliberately different quantities that a
casual reading merges. The **matching window** — how far an observed and a
calculated line may sit and still be the same line — is a statement about
the systematics the search had to open its tolerance for, while the
**measurement $\sigma$** that floors the two mean discrepancies is a
statement about what the data resolve. On a laboratory pattern with an
uncorrected specimen displacement the two differ by an order of magnitude,
and scoring coverage at the tighter one makes every candidate look as
though it explains nothing. A candidate that carries a fitted shift is
likewise scored against the *corrected* positions it claims, not the raw
ones: the alternative marks a candidate down for the very correction it
declared, which on a certified pattern demoted the true lattice below
cells that had merely been corrected less.

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

*Source:* `anatase.indexing.ambiguity.hnf_matrices`

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
synchrotron cells and splits noisy laboratory ones.

That test presumes the reduction is *canonical*, and in floating point it is
not so by default. The Křivý–Gruber algorithm {cite}`krivygruber1976` decides
its normalisation on exact equalities — when $B = C$ the tie is broken on
$\lvert \eta \rvert \le \lvert \zeta \rvert$ — and those equalities cannot be
tested with finite precision. Every comparison therefore carries a **relative**
tolerance $\varepsilon = \varepsilon_{\mathrm{rel}} V^{1/3}$ with
$\varepsilon_{\mathrm{rel}} =$ {{ NIGGLI_EPS_RELATIVE }}, the same value in the
reduction and in the predicate that checks it {cite}`grossekunstleve2004`.
Without it a lattice with two equal reduced axes reduces to $\beta$ and
$\gamma$ *swapped* depending on the setting it arrived in, so two descriptions
of one lattice are declared two lattices.

Lattice symmetry is
decided by **two independent opinions** — a Le Page 2-fold search
{cite}`lepage1982` with a tolerance in degrees of obliquity, and a
distance-tolerance standardisation {cite}`togo2024` — swept over their
tolerances, with the answer taken as the symmetry stable across the sweep
and anything appearing only at the loosest tolerance reported as ambiguous.
Agreement between independent methods is the confidence; disagreement is
reported rather than averaged.
