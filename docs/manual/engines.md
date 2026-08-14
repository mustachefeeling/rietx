(ch-engines)=
# Search engines

{ref}`ch-indexing` establishes what a peak list can say about a lattice: the
quadratic form, the symmetry-allowed subspaces, the figures that score a
candidate, and the ambiguities that no amount of position data resolves. This
chapter is about the *search* — how a cell is found in the first place, what
each method assumes, and which of them can say anything at all when it finds
nothing.

Two engines are implemented. They share the Q form, the tolerance model and
the scoring panel, and nothing else: one exhausts a metric domain, the other
guesses indices and solves. Both source papers conclude that no single
indexing program wins and that running several is what raises the success
rate {cite}`bergmann2004`, which is the same device this package uses for
confidence elsewhere — agreement between independent methods is the evidence,
and disagreement is reported rather than averaged.

## Why the search is in $(A \ldots F)$ and not in $(a, b, c, \alpha, \beta, \gamma)$

Both published methods this chapter follows work in direct cell parameters.
Here the search coordinates are the metric components of
{eq}`idx-qform` instead, and the reason is that $Q$ is **linear** in them. Over
an axis-aligned box $[\theta^-, \theta^+]$ the extremes of $Q(hkl)$ are
therefore attained exactly at corners and are read off componentwise,

```{math}
:label: eng-corner

Q^{\pm}(hkl) \;=\; \sum_j \begin{cases}
  m_j \theta_j^{\pm} & m_j > 0\\
  m_j \theta_j^{\mp} & m_j \le 0
\end{cases}
\qquad m = \mathbf{d}(hkl)\,B^{\mathsf T},
```

*Source:* `rietx.indexing.dichotomy._q_bounds`

with $B$ the metric basis of {eq}`idx-subspace` and $\mathbf{d}(hkl) =
(h^2, k^2, l^2, kl, hl, hk)$ the design row of {eq}`idx-af`. No corner is
enumerated — there are $2^n$ of them —
and the bound is **tight** rather than merely valid, which matters because a
loose bound prunes less while still returning correct cells, a regression no
recovery test would notice.

The direct-space formulation has no such property. Its $Q$ is a ratio of
trigonometric expressions in the parameters, so the 1991 method needs an
eight-case monotonicity analysis for the cross terms when $hl < 0$, and its
authors attribute their own pre-1991 monoclinic cost to having got those
bounds loose {cite}`boultif1991`. In $(A \ldots F)$ that case split does not
exist in any system, triclinic included.

The box lives in the symmetry subspace, so its dimension is the metric degrees
of freedom — 1 for cubic, 6 for triclinic — and the coordinates $\theta$ are
read off the basis's pivot structure rather than tabulated per system.

## Successive dichotomy

The method divides a parameter domain into subdomains, discards any that
*provably* cannot contain a solution, and recurses
{cite}`louer1972,boultif1991,boultif2004`. What makes it worth its cost next
to a cheaper engine is the contrapositive: when it exhausts a domain and finds
nothing, **no cell of that symmetry within those bounds fits the peak list**.
That is a statement no other method here can make, and it is why
`search_complete` is reported per system rather than assumed — an unfinished
search has said nothing at all, and the two cases must not look alike
downstream.

The domain is set by the principal $d$-spacings on the diagonal components and
by an obliquity bound on the rest,

```{math}
:label: eng-domain

\frac{1}{d_{\max}^2} \le G^*_{ii} \le \frac{1}{d_{\min}^2},
\qquad
\lvert 2G^*_{ij} \rvert \;\le\; 2\cos\vartheta_{\max}\sqrt{G^*_{ii}G^*_{jj}},
```

*Source:* `rietx.indexing.dichotomy._initial_box`

the second being Cauchy–Schwarz with the reciprocal angles restricted to
$[\vartheta_{\max}, 180° - \vartheta_{\max}]$. It is reported as a **bound of
the search** and never as a claim about lattices: a cell more oblique than
this is outside the domain, and its absence from the results means nothing.

Three prunes run per box, cheapest first. Each is *monotone* under bisection —
a child's intervals are subsets of its parent's — which is what makes the
pruning sound rather than merely plausible.

**The metric cone and the volume window.** A box whose diagonal interval is
non-positive is not a lattice, and $\det G^*$ over the box must intersect the
band $[V_{\max}^{-2}, V_{\min}^{-2}]$ implied by the declared volume range.
Bounding that determinant by interval arithmetic on its expanded form is
correct and nearly useless: it evaluates $-G^*_{22}(E/2)^2$ with $E$ at the
*domain's* maximum while the diagonals are at this *box's*, and the term then
swamps $G^*_{11}G^*_{22}G^*_{33}$. Factoring the correlation matrix out
instead keeps the coupling {eq}`eng-domain` already declares,

```{math}
:label: eng-det

\det G^* \;=\; G^*_{11}G^*_{22}G^*_{33} \cdot \det R,
\qquad
R_{ij} = \frac{G^*_{ij}}{\sqrt{G^*_{ii}G^*_{jj}}},
\quad \lvert R_{ij} \rvert \le \cos\vartheta_{\max},
```

*Source:* `rietx.indexing.dichotomy._det_interval`

so that for a monoclinic box $\det R \in [1 - \cos^2\vartheta_{\max}, 1]$ and
the "this cell is too small" half of the test can fire at all.

**Line matching, and Hall's condition.** For each observed line, some trial
$hkl$'s $[Q^-, Q^+]$ must reach it within $k\sigma_{\text{eff}}$; more than
the tolerated number of misses and the box is impossible. That test alone is
the weakest necessary condition there is, because it lets several lines point
at the same reflection. An indexing is an **injective** map from lines to
reflections — one $hkl$ has one $Q$, so two resolved lines cannot both be it —
so the box must admit a matching, and Hall's theorem requires
$\lvert N(S)\rvert \ge \lvert S \rvert$ for every set $S$ of lines. Two
instances of that are free to check: $S$ = every line, whose neighbourhood is
the count of reflections still reaching anything, and $S$ = the lines with a
single candidate, where two lines forced onto one reflection is a violation at
$\lvert S \rvert = 2$.

*Source:* `rietx.indexing.dichotomy._assignment_possible`

**One grid pass per system, not per centring.** A centred trial set is a
strict subset of the primitive one, so a centred box has fewer reflections
with which to reach the same lines: its matching test is strictly harder, and
every box surviving it survives the primitive test. The centred pass can
therefore find no metric the primitive pass misses, and all it ever
contributed was the scoring — recovered by re-running the assignment under
each admissible centring at the leaves.

Two phases, and they are not a refactor of one loop. A merged depth-first
stack dives to a leaf through the first grid cell it likes and explores that
cell's entire bisection subtree, which in four dimensions is effectively
unbounded, before it looks at the second cell. So the grid is completed
breadth-first at the literature's steps — {{ AXIS_STEP }} Å in a principal
$d$-spacing and {{ ANGLE_STEP_DEG }}° in a reciprocal angle
{cite}`itc-h-indexing` — with the prunes applied *between* dimensions, and
only then are the survivors bisected, best first.

Where to stop bisecting is not the measurement tolerance, and conflating the
two breaks the search outright. Exhaustiveness comes from the pruning, which
is exact however coarse the leaves are; acceptance only has to leave a box
whose centre the assign-and-refine loop can polish onto the true cell. **The
box is small enough when the indexing inside it is unique** — no observed line
has two candidate reflections — rather than when a width crosses a threshold,
because a high-index reflection has a large $\lVert m \rVert$ and its interval
stays wide long after the assignment has stopped being ambiguous.

Tolerated unindexed lines are the single most valuable option here, and it is
the 2004 paper's own reported gain {cite}`boultif2004`. Without them one
impurity line prunes the box containing the truth and the engine returns
nothing, *confidently* — the one failure this whole subsystem exists to
prevent. Raising the count past a small default manufactures cells instead:
each extra tolerated line is one more coincidence a wrong metric is allowed to
have.

## Index-heuristic trial and error

The second engine assumes the indices of a few base lines and solves the
metric exactly {cite}`werner1964,werner1985`. With $n$ metric parameters, $n$
assigned lines determine them by an exact $n \times n$ solve, so the search is
over *index assignments* rather than over a domain — a combinatorial space
that no volume window prunes, and one where a bad base line poisons the answer
exactly where a wide domain poisons the dichotomy. That is the independence
worth having: the two engines fail on different inputs.

Its base-line index limit is small for a reason that is arithmetic rather than
heuristic: a base line of low $Q$ cannot carry a large index without implying
an axis longer than the domain allows.

*Source:* `rietx.indexing.trial_error.search_trial_error`

The engine carries **no exhaustiveness claim**. It can contribute a
`found_by` vote and a Borda rank; it can never contribute to
`search_complete`, and a restricted search is never a verdict about the
sample.

## What a zone-indexing engine would and would not add

A third engine in the ITO lineage {cite}`visser1969` was assessed and not
implemented, and the argument is worth recording because the attractive half
of it is real. ITO searches *zones*: the continuously searched dimension is
never more than one at any stage, in any system including triclinic, so a
monoclinic problem becomes three sequential one-dimensional coincidence
searches rather than a four-dimensional box. It assumes no indices, only that
two of the first few lines are real reflections whose common zone is
populated — a genuinely different failure mode from both landed engines, which
is what would make an agreement vote worth something.

What refutes the hopeful version is that it buys **no immunity to a zero-point
error**. With

```{math}
:label: eng-ito

R \;=\; \frac{1}{mn}Q(m,n) \;-\; \frac{m}{n}Q' \;-\; \frac{n}{m}Q'',
```

a constant offset $Q \to Q + \delta$ shifts the four $(m, n)$ branches by
different multiples of $\delta$, so it **splits** the coincidence peak rather
than translating it. The acceptance test is a *count*, so splitting is worse
than shifting, and per-line errors amplify. An engine with that property fails
on exactly the uncalibrated laboratory data the systematic-error model of
{ref}`ch-indexing` exists for. It also carries no exhaustiveness claim, and
its reduction is weak above twofold symmetry, making it an
orthorhombic-and-below specialist.

## The obliquity bound is a costed choice

$\vartheta_{\max}$ is the one domain parameter with no physical answer. Every
monoclinic lattice has a $b$-unique description whose $\beta$ lies in
$[60°, 120°]$ — the $a$–$c$ plane is a two-dimensional lattice, and Gauss
reduction gives $\lvert\cos\beta\rvert \le a/2c \le 1/2$ — so a narrow bound
loses no *lattice*, only some *descriptions* of it. Against that, the bound
enters the cost twice: directly, through the number of angular slabs the grid
cuts, and again through {eq}`eng-det`, where $1 - \cos^2\vartheta_{\max}$ is
the whole strength of the small-cell prune.

The reason the bound is nevertheless kept wide is that the search's setting
conventions are *prunes rather than projections* — a box straddling the
axis-ordering constraint is kept — so "the reduced description is somewhere in
the domain" is an argument about lattices that the implementation does not
structurally enforce for every system. A search bound may be loose; the one
thing it may not do is exclude the true cell.

*Source:* `rietx.indexing.dichotomy.MAX_ANGLE_COSINE`

## The reflection ceiling

Every leaf is checked before any enumeration. The count of reflections a cell
would generate to a given $2\theta$ is arithmetic on the cell, so the guard
costs nothing and never touches memory — which is the point, because the cells
a search proposes include ones no physical specimen has, and a refinement free
to move produced a 49 Å axis at $\beta = 174°$ in testing.

*Source:* `rietx.indexing.engines.reflection_ceiling_ok`
