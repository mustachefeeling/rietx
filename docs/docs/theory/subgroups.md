(ch-subgroups)=
# Maximal subgroups

A distorted structure's space group H is a subgroup of its parent's G, and a
chain of maximal subgroups links the two (a Bärnighausen tree,
{cite}`muller2011relating`). `rietx` builds the maximal subgroups of any
space group from the group's own operations, with the theory of ITA A1
{cite}`wondratschek2011,wondratschekaroyo2011`, and states each with the
transformation to a standard setting, checked exactly. Nothing is read from a
printed or online table of subgroups.

## Two kinds, and nothing else

Write T for the translation subgroup of G, with lattice L, and P for the point
group, G/T ≅ P. By Hermann's theorem a maximal subgroup H of G is one of two
kinds {cite}`wondratschek2011` (Lemma 1.2.8.1.3):

- translationengleiche (t), with H ⊇ T: H/T is a maximal subgroup of P, so
  the maximal t-subgroups are one per maximal subgroup of the point group, with
  G's own coset representatives;
- klassengleiche (k), with the point group P kept and the lattice
  reduced to a sublattice L′ < L that P maps onto itself.

## The k-subgroups over a prime field

H is a maximal k-subgroup exactly when no P-invariant lattice lies strictly
between L′ and L. Then $pL \subseteq L'$ for one prime p, and L/L′ is an
irreducible module of P over the field $\mathbb{F}_p$, so that

```{math}
:label: sub-kindex

[G : H] \;=\; [L : L'] \;=\; p^{d}, \qquad d \in \{1, 2, 3\},
```

{source}`rietx.crystallography.representation.subgroups.maximal`

{cite}`wondratschek2011` (Lemma 1.2.8.2.1). The lattices are therefore
$L' = pL + U$ for the maximal P-invariant subspaces U of
$L/pL \cong \mathbb{F}_p^3$, which a finite search over the lines and planes
of $\mathbb{F}_p^3$ finds. On one L′, a subgroup assigns to each generator g
of P one translation shift $x_g \in L/L'$, and the subgroup closes exactly
when, for every generator g and every point-group element e,

```{math}
:label: sub-closure

\pi(n_{g,e}) + x_g + \rho(g)\,\tau_e - \tau_{ge} \;=\; 0 \pmod{p},
```

{source}`rietx.crystallography.representation.subgroups.maximal`

where $\rho(g)$ is the action of g on L/L′, $\tau_e$ is the shift the
generators build up along a word for e (linear in the $x_g$), and
$n_{g,e} = w_g + g\,v_e - v_{ge} \in L$ is the lattice vector the product
of coset representatives leaves over. Every solution of this linear system is
one subgroup and every subgroup is one solution, so the list on each L′ is
complete by construction.

All maximal subgroups not isomorphic to G have index 2, 3 or 4
{cite}`wondratschek2011` (Lemma 1.2.8.2.2), so the default list, every
maximal subgroup of index at most 4, holds all of them. Isomorphic maximal
subgroups exist for infinitely many primes {cite}`wondratschekaroyo2011`
(§ 2.1.5) and are listed on demand, for one index or for the subgroups that
keep a given supercell's translations.

## Conjugacy classes

Two subgroups are conjugate when an element of G carries one onto the other.
A class is built by closing a subgroup under conjugation by the coset
representatives of P's generators and by L's basis translations, which
generate G. Both translational and orientational conjugation
{cite}`muller2011guide` (§ 3.1.5) fall out of the one closure; a subgroup of
index 2 is normal and is its own class.

## The transformation to a standard setting

Each subgroup is stated as a pair (P, p) with

```{math}
:label: sub-pp

\mathbf{r}_\text{parent} \;=\; \mathsf{P}\,\mathbf{r}_\text{child} + \mathbf{p},
\qquad
W' = \mathsf{P}^{-1} W \mathsf{P}, \quad
\mathbf{w}' = \mathsf{P}^{-1}\bigl(\mathbf{w} + (W - I)\,\mathbf{p}\bigr),
```

{source}`rietx.crystallography.representation.subgroups.MaximalSubgroup`

{cite}`wondratschekaroyo2011` (equations 2.1.3.3–2.1.3.9): the columns of P are the
subgroup's conventional axes in the parent's fractions and p is its origin in
the parent cell, the convention the displacive mode basis uses
({ref}`ch-representation-analysis`). The standard setting is the one spglib returns for
the subgroup's type {cite}`togo2024`, found from a probe structure of two
generic orbits, and every operation of $\mathsf{P}^{-1} H \mathsf{P}$ is then
compared with that setting's operations in exact rational arithmetic, so a
wrong (P, p) raises rather than passing.

The (P, p) is spglib's choice, not A1's. Every (P, p) that differs from
it by an element of H's affine normaliser describes the same subgroup, and
A1 prints one of them {cite}`wondratschekaroyo2011` (§ 2.1.2.5). spglib's can
differ, and can change with a spglib release or a move to another symmetry
library. Two transformations are therefore compared by the subgroup they
describe, rebuilt in the parent's coordinates, never entry by entry. Wyckoff
labels taken in one (P, p) belong to it, since another can permute them within
a Wyckoff set {cite}`muller2011guide` (§ 3.1.1.6).

## What the generator is checked against

The tests name seventeen entries published in A1, among them Pmn2₁'s three
t-subgroups, P3₁12's three conjugate C121, C222₁'s two triplets of index 3,
Fddd → C12/c1 with origin ⅛, ⅛, ⅛, Pm3̄m's two classes of four Im3̄m, and
AlB₂'s two non-conjugate P6₃/mmc subgroups {cite}`muller2011relating`. Each is
found exactly once with its published (P, p), up to the normaliser. Over all
230 types the generator gives 3767 maximal subgroups of index at most 4, every
one standardised exactly and rebuilt from its own (P, p) as maximal.
