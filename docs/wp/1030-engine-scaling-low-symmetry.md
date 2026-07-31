# WP-1030 — Indexing at low symmetry: search cost, and the figures that rank it

Milestone: v1.0 · Status: ✅ 2026-07-31
Depends on: 1020–1022 (all landed); 1026 soft (it owns the benchmark that grades this)

> **Renumbered 1029 → 1030 on 2026-07-31.** This WP was created as 1029 on the
> `worktree-indexer` branch on 2026-07-30, while `docs/wp/1029-gui-usability.md`
> was created and merged to `main` from the GUI worktree — two concurrent
> worktrees took the same free number, and neither could see the other. The GUI
> one was merged first, so this one moved. **Anything written before that date
> that says "1029" and means *indexing engine scaling* means this file**;
> WP-1026's earlier handover entries are the main place that happens. The
> mechanism worth fixing is upstream of both: a number is claimed by writing the
> file, and a branch that has not been merged has not claimed anything.

## Goal

Make a **monoclinic** search over a published domain finish, and rank what it
finds well enough that a supercell cannot win. Today neither holds: the
dichotomy engine does not exhaust the bethanechol domain in 300 s and returns
nothing, and the figure-of-merit panel is missing the two published members that
exist specifically to demote derivative lattices.

This is the row [1026](1026-indexing-acceptance.md)'s handover asked for when it
recorded the global benchmark score as "engine work, not acceptance work". **The
benchmark score belongs to 1026 and is unreachable until this lands** — do not
attempt it here and do not re-open it there first.

> ## What the 2026-07-31 session measured, before anything else here is read
>
> **The premise above is wrong in its first clause, and the Context below is
> measured over a different domain than the Acceptance section names.**
>
> 1. The Context table's protocol is d ∈ **[2, 12]**, not the d ∈ [5, 20] the
>    Acceptance criterion states. Reproduced exactly: 300.1 s, 0 candidates,
>    `complete=False`, 7.43 M boxes at 16.2 rows/box (the WP recorded 5.7 M at
>    15.6). At `max_d_axis = 12` the published cell's **b = 16.408 Å is outside
>    the domain**, so "0 candidates" there is *partly correct behaviour* being
>    read as a search failure.
> 2. Over the Acceptance criterion's own domain the search **already
>    completed before this WP changed anything**: 22.2 s, 532 203 boxes,
>    `search_complete["monoclinic"]` true, truth ranked **first**. It returns
>    the truth's `c + a` setting — (8.875, 16.408, 11.0099, β 139.70°),
>    V 1036.9 Å³, the published volume — which sorted-axis comparison calls a
>    miss and `reduce.same_lattice` correctly calls the answer.
> 3. So the domain that genuinely fails is d ∈ **[2, 20]**: the benchmark's
>    *default* mode, and the package's own `DEFAULT_MIN_D_AXIS = 2.0`. That is
>    the honest target, and it is a statement about the **short**-axis bound,
>    not about monoclinic.
> 4. **97.6 % of the boxes are in phase 2, the bisection — not the grid.**
>    Measured by instrumenting `_test_box`: of 692 294 boxes, ~16 k are the
>    grid pass. Every cost item ranked in Context is a phase-1 item.
> 5. The ranking of causes is close to inverted. Of the boxes reaching the
>    line-matching prune it refuses **0.0 %** (342 of 692 294); the
>    Hall's-condition test the WP ranks **fifth of five** refuses **89.9 %**,
>    and its forced-singleton half a further 26.9 %.
>
> Items 1-3 of Context are answered below on measurement; items 4 and 5 landed.
> The **bethanechol global score is now reachable** and remains
> [1026](1026-indexing-acceptance.md)'s.

## Context

Monoclinic is not an exotic case. It is where organic and pharmaceutical powders
live, and it is the whole content of the only published, scored benchmark this
package has. The two landed engines both recover monoclinic cells from clean
synthetic lists over a *narrow declared* axis range (WP-1021: 103 s; WP-1022:
91 s) and neither reaches the truth on the benchmark's own domain.

### What was measured (2026-07-30), and what it rules out

Protocol: the published bethanechol cell (8.875, 16.408, 7.137, β = 93.84°), its
**own twenty exact synthetic lines** at λ = 1.5418 over 5.39–21.66° 2θ,
`systems=("monoclinic",)`, `min_volume=800`, `max_volume=1200`,
`n_unindexed=0`, `budget_seconds=300`. Perfect data, no impurities, no shift.

| `max_d_axis` | wall | candidates | `complete` | boxes | rows/box |
|---|---|---|---|---|---|
| 12 Å | 300.1 s | **0** | False | 5 738 295 | 15.6 |
| 16 Å | 300.2 s | **0** | False | 5 824 941 | 14.5 |

So it is **budget expiry at ~19 000 boxes/s (~52 µs/box)**, and three
explanations are excluded by that table alone: it is not the tolerance (the data
are exact), not the peak list (ditto, and WP-1026 already closed that), and
**not the `MAX_GRID_CELLS` frontier cap** — a predicted overflow would return in
seconds with ~4×10⁵ boxes, and we see 5.7 M. `rows_per_box ≈ 15` also says the
trial-set filter is collapsing properly, so the per-line hkl candidate lists
DICVOL carries are *not* the lever here. **The cost is the number of boxes
generated and tested.**

### The dominant cause: the volume window prunes nothing until the last dimension is cut

Measured directly on `_det_interval` over the monoclinic domain (5–20 Å,
V ∈ [800, 1200] Å³):

```
det interval over the whole domain: [-4.7984e-05, 6.4000e-05]
volume band [800,1200] as a det band: [ 6.9444e-07, 1.5625e-06]
det_lo < 0  ->  the "cell is too small" half of the test can NEVER fire
```

and it is still true one grid cell down — A, B, C cut to 0.4 Å in d at d ≈ 10 Å
with E uncut gives `[-1.12e-05, 1.00e-06]`, i.e. "this box may contain a cell of
any volume in [1000, ∞)". So the single strongest constraint the protocol
supplies is inert over three of the four staging levels.

**Why direct space does not have this problem, and it is not about tightness.**
A first hypothesis — that the A…F reparameterisation loses the prune to
interval-arithmetic inflation — was tested and **refuted**: at grid-cell scale
the det interval is only 1.1–3.2× wider than the true volume range and 93 % of
the [800, 1200] prune survives. The real difference is structural. In DICVOL's
parameters `V = A·B·C / sin β` is a **monotone separable product** of the search
coordinates, so the volume shell is the *outer loop* and, once A, B and β are
fixed, `V ∈ [V₋, V₊]` solves in closed form for a contiguous range of the
innermost index. It sets a **loop bound**; ours sets a **test**, and cells
outside the shell are generated before being rejected.

The metric-space equivalent exists: `det G* = B·(A·C − E²/4)` is monotone
increasing in C at fixed A, B, E, so **cutting E before C** turns the volume
window into an explicit range for C. That reordering is the primary task below.

### Contributing, ranked, with what each is worth

1. **The volume-prune staging** (above). Dominant; a reordering, not a rewrite.
2. **`MAX_ANGLE_COSINE = cos 30°`** admits reciprocal angles 30–150°, i.e. β to
   150°, against DICVOL04's default **β ≤ 130°** (itself raised from 125° because
   indigo at β = 130.15° was DICVOL91's reported failure). 1.5× directly, and it
   is *also* what makes `(E/2)²` large enough to swamp `A·B·C` above — so item 1
   partly depends on it. `sin²β* ≥ 0.25` here against ≥ 0.587 there.
3. **One grid pass per centring.** `search_dichotomy` loops
   `spec.centrings_for(system)`, so monoclinic pays 2×, orthorhombic 4×. But
   `centring_allows` makes the C trial set a strict *subset* of P, so the C
   line-matching test is strictly harder and **every box surviving the C search
   survives the P search** — the C pass can find no metric the P pass misses.
   Its only value is scoring, which can be had by re-scoring each P-accepted
   metric under every admissible centring. A clean 2× on monoclinic for nothing.
4. **Data-derived parameter floors** — Louër & Louër (1972) Table 1, supplied by
   the user 2026-07-30 and transcribed below. We have the *ordering* half already
   (`axis_swaps`, derived from subspace preservation); we do not have the floors.
   Measured on the domain above, where d₁ = 16.40 Å (the b axis, exactly):

   | | monoclinic | orthorhombic |
   |---|---|---|
   | ordering convention — **we have this, as a test** | 1.95× | 5.55× |
   | plus the d₁/d₂ floors — **we do not have these** | 3.27× | 9.43× |

5. **A bipartite-matching feasibility test.** `_test_box` asks only "can *some*
   hkl reach each line" (`hit.any(axis=1)`), the weakest form of Hall's
   condition. DICVOL91 rejects a domain outright when two lines would take an
   identical hkl. The `hit` matrix is already built, so the stronger test is
   nearly free, and it *rejects* the boxes that `_push_children` currently only
   deprioritises.

Items 1, 3 and 4 together are roughly 6.5× on monoclinic. **That is enough to
change the outcome and not obviously enough to exhaust the domain** — 5.7 M
boxes at 6.5× is still ~0.9 M — so treat the target as "finishes and finds it",
measure again, and expect to need item 2 as well.

### Louër & Louër (1972) Table 1, transcribed

Supplied by the user 2026-07-30. The paper has **no monoclinic or triclinic
column**, which is the system that fails here — for those, the principle must be
*derived* and said to be derived, not cited.

| | cubic | tetragonal | hexagonal | orthorhombic |
|---|---|---|---|---|
| parameters | a ≥ d₁ − Δd₁ | a, c ≥ d₂ − Δd₂ \* | a, c ≥ d₂ − Δd₂ \* | a > b > c; a ≥ d₁ − Δd₁ \*; b ≥ d₂ − Δd₂ \* |
| on hkl | h ≥ k ≥ l | h ≥ k | h ≥ k | — |
| index limit | h²/a² ≥ Q_n + ΔQ_n | h²/a², l²/c² ≥ Q_n + ΔQ_n | (4/3)h²/a², l²/c² ≥ Q_n + ΔQ_n | h²/a², k²/b², l²/c² ≥ Q_n + ΔQ_n |

**\* The footnote is the load-bearing part and is exactly what a guess would get
wrong.** The d₂ floors hold *only if* the reciprocal vectors for d₁ and d₂ are
non-collinear, i.e. d₁/d₂ ≠ n/m for integers n, m; otherwise take the first
vector non-collinear with d₁'s. Without it the floor silently excludes the true
cell whenever the two strongest low-angle lines are successive orders along one
row — which is precisely what a long axis produces (010, 020, …), i.e. the very
population the constraint is aimed at. Same failure shape as the WP-0501 b₂
transposition.

Note also that the floors are only sound **alongside** a setting convention: the
argument "the largest observed d cannot exceed the largest principal d" needs the
cell to be in a reduced setting, which is what `axis_swaps` supplies. Rows 2 and
3 are already implemented and generalise better here than in the paper —
`_max_index` is `h ≤ max_d·√Q_max` (i.e. `Q ≥ A·h²` with `A ≥ 1/max_d²`), and the
explicit hexagonal 4/3 is automatic in A…F because `A = a*² = 4/(3a²)`.

### Should there be a third engine?

The design has always said three, and [1023](1023-engine-montecarlo.md) closed
the Monte-Carlo door, so `high` confidence currently rests on two engines that
are *both* metric-domain searches. Visser (1969) — ITO, zone indexing — was read
2026-07-30 and assessed:

- **For**: the *continuously searched* dimension is never more than one at any
  stage, in any system including triclinic. A monoclinic problem becomes three
  sequential 1-D coincidence searches (zone R, second zone R, then the dihedral
  D) instead of a 4-D box, at ~4×10⁴ scalar operations total — free next to
  85–105 s. It assumes no *indices*, only that two of the first six lines are
  real reflections whose common zone is populated, which is a genuinely different
  failure mode from both landed engines, and that independence is what makes an
  agreement vote worth something.
- **Against, and this refutes the hopeful version of the argument**: it buys
  **no zero-point immunity**. `R = (1/mn)Q(m,n) − (m/n)Q′ − (n/m)Q″`, so under
  `Q → Q + δ` the four (m,n) branches shift by −1.00, −2.00 and −1.75 δ — a
  constant offset **splits** the coincidence peak rather than translating it,
  which is worse than shifting because the acceptance test is a *count*, and
  per-line errors amplify 3×. ITO would fail on the bundled corundum pattern for
  the same reason our engines did. It also carries **no exhaustiveness claim**,
  so it can add a `found_by` vote and Borda rank but can never contribute to
  `search_complete`; and Visser states its reduction is weak above twofold
  symmetry, so it is an orthorhombic-and-below specialist.
- **Cheaper alternative first**: TREOR's **short-axis test** (Werner *et al.*
  1985) is the same dimensionality reduction inside the engine we already have —
  index the first three lines as a 2-D zone, and if the next three fit it, derive
  the remaining one or two monoclinic parameters from the first unindexable line.
  With the Smith & Kahara (1975) "020 detector" `2Q(020) + Q(h10) = Q(h30)`.
  Both are small additions to `trial_error.py`.

**Recommendation: do the cost items first and re-measure.** A third engine is a
real WP, and if items 1–4 make monoclinic affordable then its value is
confidence, not capability — which is a different and weaker argument for it.

### The two missing figures of merit

WP-1020 deferred four published figures because their formulas could not be
written from memory with correct attribution. Oishi-Tomiyasu (2013) was supplied
2026-07-30 and **closes two of them**; WRIP20 and McM₂₀ are not in it and still
need their own sources (it points at Taupin 1988, Bergmann 2007, Le Bail 2008,
Altomare *et al.* 2009).

All Q are 1/d²; `m(hkl)` is the full Laue orbit size including −h.

```
Ncal(a,b) = Σ 1/m(hkl) over centring-allowed triples with a ≤ q(hkl) ≤ b
            (include 000 iff a ≤ 0; legitimately fractional — never round)
qN, qI    = computed q closest to Qobs[n], Qobs[1]

delta_fwd = mean over i of |Qobs[i] − nearest computed q|
eps_fwd   = (qN − qI) / (2·Ncal(qI, qN))
M_tilde_n = eps_fwd / delta_fwd

delta_rev = [ Σ over hkl in [qI,qN] of |q(hkl) − nearest observed q| / m(hkl) ]
            / Ncal(qI, qN)
eps_rev   = (Qobs[n] − Qobs[1]) / (2n)
M_n_Rev   = eps_rev / delta_rev
M_n_Sym   = M_tilde_n · M_n_Rev
```

Four things that will bite:

- `trial_hkl` keeps **one hkl per Friedel pair**, while `m(hkl)` is the full
  orbit. Summing `1/m` over the half-sphere gives exactly `Ncal/2`.
- `predicted_lines` **merges** exact coincidences into one line; `N^cal`
  deliberately does not, so these figures cannot reuse its output. That merge is
  a float comparison (`LINE_COINCIDENCE_RTOL = 1e-9`) and is precisely the
  operation `N^cal` was designed to remove — on a pseudo-symmetric candidate,
  which is what an indexer produces, the threshold decides the count.
- **The scale is not M₂₀'s.** In the paper's tables `M^Rev` for *correct*
  solutions runs ~1.7–15.8 where `M̃₂₀` reaches 556. A ">10" intuition imported
  from de Wolff would reject nearly every correct cell. The paper's own screen is
  `M̃ₙ ≥ 3`, `M^Rev ≥ 1`, `12 ≤ N^cal ≤ 120`.
- The vanishing-δ floor is **ours, not the paper's** — it addresses this nowhere,
  and `delta_rev` can vanish on synthetic data exactly as `delta_fwd` does. Carry
  it in `blind_spot` as an addition, the way `m20` already does.

The paper's motivation is the failure our `predicted_seen_fraction` was built
for, reached independently: `M^Rev` is an unbounded continuous ratio where ours
is a windowed fraction, so they are complementary rather than redundant. Its
Fig. 1 decides a supercell family that `M̃₂₀` gets wrong. It also confirms our
documented blind spot — space-group extinctions penalise a *correct* cell under
`M^Rev`, as they do under our forward member.

### Inherited — consumed 2026-07-31

The mailbox is emptied here rather than deleted, because three of its entries
are **still open** and have been pushed on to the WPs that own them
([1026](1026-indexing-acceptance.md) and
[1027](1027-gui-peak-picker.md)); what follows records what happened to each.

- *A supercell outranks the truth on clean single-phase patterns* (qarr
  brucite, magnetite) — **partly addressed, not verified on those datasets.**
  `M^Rev` is the member built for exactly this failure and it separates a
  synthetic doubled axis 64-74× where M₂₀ separates it 1.8×. Neither brucite
  nor magnetite is a landed row (95 s and 218 s), so this session did not
  re-measure them; that belongs with the row, in 1026.
- *`DEFAULT_SEARCH_LINES` takes the first twenty lines in 2θ order, and on a
  synchrotron pattern that is the wrong twenty* — **untouched, and pushed to
  1026.** It is a peak-list selection question, not a search-cost one, and it
  is the third dataset in three sessions where the peak list rather than the
  search was the obstruction.
- *M₂₀ inverts the ranking on FAP* — **the tool now exists; the measurement
  does not.** `M^Rev`/`M^Sym` are the figures the entry names as "the obvious
  thing to test against it", and they are in the panel. Whether they turn that
  ranking round is a claim about `fap_index`, a 95 s slow row that belongs to
  1026's acceptance table.
- *NAC cannot be searched at its own d_min, and truncating 2θ does not fix it*
  — **still true and now better posed.** The obstruction is
  `reflection_ceiling_ok` at d_min = 0.43 Å, which is a *reflection-count*
  limit and not a domain-size one, so none of this WP's prunes touch it. The
  entry's own instruction — state the scope in terms of d_min rather than 2θ —
  stands, and it is a peak-list/scope decision for 1026.
- *`refine_with_shift` declines its own correction* — fixed in WP-1026's third
  session; the note that a shift allowance widens every `hit` matrix and so
  multiplies the box count stands and is unchanged by anything here.
- *DICVOL estimates and removes the shift before searching (Dong, Wu & Chen
  1999), which would let `assess_peak_list` report a measured `shift.source`* —
  **not attempted; the paper is still not held.** It remains the unblock for
  the `shift_allowance_assumed` caveat that makes `high` unreachable on real
  lab data, and it is `indexing/quality.py` work rather than engine work.
- *`_box_key` was silently deciding answers, so ask of each new prune not "is
  it sound" but "what does it do when two leaves are nearly the same cell"* —
  **applied.** Every prune added here refuses boxes on a *necessary* condition
  (Hall's condition; a determinant interval that must contain every lattice in
  the box), never on a tie-break between near-identical cells, and both carry a
  soundness test rather than a recovery test. `_accept` call counts were
  watched alongside box counts as instructed: `candidates.raw` is unchanged at
  126 on d ∈ [5, 20].
- *The bethanechol global score cannot be graded until the monoclinic domain
  finishes* — **unblocked.** It finishes, in both the paper's modes. The score
  is 1026's and is pushed back there.

## Non-goals

- **Not the bethanechol global score** — that is [1026](1026-indexing-acceptance.md)'s
  criterion and is graded there once this lands.
- Not triclinic. Neither paper claims it is affordable (DICVOL04 quotes up to
  3770 s), and `search_complete` already reports the truth about it.
- Not a rewrite of the A…F formulation. It is the one axis on which we are
  strictly ahead of DICVOL91 — corner-exact Q bounds in every system, where the
  paper needs an eight-case analysis for hl < 0 and attributes its *own* pre-1991
  monoclinic cost to having got those bounds loose.

## Tasks

- [x] ~~Re-stage the grid so E is cut before C~~ — **the diagnosis is right and
      the fix is not the staging.** The volume prune is inert because interval
      arithmetic on the *expanded* determinant discards a coupling the domain
      already declares, evaluating −B·(E/2)² with E at the domain's maximum
      while A and C are at the box's. Bounding through det G* = A·B·C·det R
      with every correlation clipped by `MAX_ANGLE_COSINE` fixes it **in
      place**, with no reordering — which matters, because moving E earlier
      would forfeit the per-box Cauchy-Schwarz narrowing that takes the E axis
      from 18 slabs to 1-3. Neither form dominates (the correlation form
      carries the diagonal spread twice, so it is looser once the off-diagonals
      are narrow, and alone it took the search *up* from 298 k to 441 k boxes),
      so both are computed and intersected. Also fixed `x²` over an interval
      straddling zero, whose minimum is 0 and not the negative `_imul(x, x)`
      returns.
- [x] Drop the redundant per-centring grid pass; the subset property is
      `test_every_centring_is_a_subset_of_the_primitive_trial_set`, asserted as
      set equality against the direct enumeration rather than as a count.
      **The obvious version of this is wrong, and only the real-data suite
      caught it** — see the note below.
- [x] ~~Louër & Louër Table 1 parameter floors~~ — **declined, twice over, and
      both halves are tests.** *Unsound where it is needed*: the paper prints
      no monoclinic or triclinic column because those forms are not diagonal,
      and an oblique cell inside this search's own obliquity bound
      (af = (1, ½, 1, 0, −1.7, 0)) puts its largest spacing on (101) at
      1.826 Å, above every principal spacing — so the floor would exclude the
      true cell, which is the one thing a search bound may not do. *Subsumed
      where it is sound*: the engine's line-matching test uses a complete trial
      set with corner-exact bounds and is strictly stronger, and it accounts
      for **0.0 %** of box deaths, so a floor derived from it prunes nothing.
      The d₁/d₂ non-collinearity condition is therefore also moot.
- [x] Decide `MAX_ANGLE_COSINE` — **keep 150°, and the cost is now recorded.**
      Measured on the bethanechol domain: β ≤ 150° 297 999 boxes / 24.5 s,
      β ≤ 140° 157 546 / 11.0 s, β ≤ 130° (DICVOL04's default) 131 037 / 9.1 s,
      β ≤ 120° 115 674 / 7.5 s — so narrowing to 130° is worth **2.3×**, and
      the truth is found at every bound. It is kept wide because the argument
      for narrowing ("every monoclinic lattice has a description with
      β ∈ [60°, 120°], by Gauss reduction of the a–c plane") is about
      *lattices*, while the search's setting conventions are **prunes rather
      than projections** — a box straddling the axis-ordering constraint is
      kept — so the implementation does not structurally force the reduced
      description into the domain for every system. Recorded in
      `docs/manual/engines.md` §"The obliquity bound is a costed choice" so the
      2.3× is on the table for whoever revisits it with the completeness
      argument made rigorous.
- [x] Bipartite-matching feasibility in `_test_box` (reject, don't
      deprioritise) — as the two instances of Hall's condition already sitting
      in the `hit` matrix, which is what makes it nearly free. **Not** a full
      Hopcroft-Karp: the cheap pair already refuse 89.9 % and 26.9 %, and the
      per-box budget is ~50 µs.
- [x] `M^Rev` and `M^Sym` in `fom.py` with `N^cal`, in the panel and in
      `blind_spot`. Checked on the synthetic supercell case as asked, and the
      result is the reason to have them: on a doubled orthorhombic axis M₂₀
      separates truth from supercell by 1.7-1.9× and `predicted_seen_fraction`
      by 1.8-1.9×, while **M^Rev separates them by 64-74×**. Borda still ranks
      the truth first, and the two extra members did not start tripping
      `fom_panel_disagrees` (the consensus suite is unchanged).
- [x] Decide the third engine — **no-go on ITO**, arithmetic in the manual
      chapter: a constant 2θ offset shifts its four (m, n) branches by
      different multiples of δ, so it *splits* the coincidence peak rather than
      translating it, and the acceptance test is a count. It would fail on
      exactly the uncalibrated laboratory data a third opinion is wanted for.
- [x] `docs/manual/engines.md`, registered in the toctree, with the
      DICVOL/TREOR/ITO citations moved into `references.bib` and cited there.
      Builds `-W` clean.

### The one defect this WP introduced, and what found it

**Dropping the centred *pass* also dropped the centred *pruning*, and the
fast suite was green through all of it.** The first version of the shared grid
pass tried every leaf under every admissible centring. That is one prune short:
a leaf the *union* set reached has not shown that the *centred* trial set can
reach these lines, which is precisely what the separate pass used to establish.

It surfaced as two SRM 660c rows failing with a **trigonal R cell ranked above
the certified cubic LaB6 lattice**. The cell is 4.1563·√2 by 4.1563·√3 — the
rhombohedral description of that very lattice, 570 ppm off — and it wins
`indexed_fraction` 0.967 to 0.933 because a lower-symmetry description mops up
the off-lattice tail components this pattern is documented as carrying. gemmi
calls it cubic and spglib trigonal, so it arrives with `bravais_ambiguous` and
`best_or_none()` was `None` either way: what was lost was the *ranking*, which
is exactly what those rows assert and what no gate would have caught.

The fix replays that one prune at the leaf, and **one box is enough** — every
prune in `_test_box` is monotone under bisection, so a box that survives
implies every ancestor survived, and leaf survival is exactly "the centred
search would have reached here". It costs nothing measurable (both bethanechol
domains unchanged at 234 227 and 639 134 boxes).

Two things to carry forward. **The obvious suspect was wrong**: with the panel
cut back to its five pre-1030 members the ranking is *identical*, so the new
figures were not the cause — they favour the truth (`m_rev` 105.5 against
92.9). An A/B through the real pipeline settled in two minutes what reading the
diff had not. And **`git bisect` over the session's own commits** is what
localised it to the shared-pass commit; the fast suite (115 indexing tests) was
green at every one of them.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow" -q
.venv/bin/python -m ruff check src tests examples
```

Criterion, measured and recorded here: the bethanechol domain (monoclinic,
V 800–1200 Å³, axes 5–20 Å, the published cell's own twenty lines) **completes**
with `search_complete["monoclinic"]` true and the truth ranked first, with the
wall clock quoted as a range. Report the box count alongside it — that is the
quantity being reduced, and the 5.7 M above is the baseline.

### Measured 2026-07-31, darwin/arm64 M4, `[dev,jax,torch]`

Protocol as stated: the published cell's own twenty exact lines
(5.39–21.66° 2θ, λ = 1.5418), `systems=("monoclinic",)`, V ∈ [800, 1200],
`n_unindexed=0`, σ_sys declared 1e-9. Box counts are deterministic, so they are
quoted as figures; wall clock is quoted as a range and moved by ±2× under load
from a second search on the same machine.

| domain | boxes before | boxes after | wall after | complete | truth |
|---|---|---|---|---|---|
| d ∈ [5, 20] — the criterion's own, = the paper's **manual** mode | 532 203 | **234 227** | 11–24 s | ✅ (before *and* after) | rank 0 |
| d ∈ [2, 20] — the paper's **default** mode, and `DEFAULT_MIN_D_AXIS` | — | **639 134** | **32 s** | ✅ (was ❌) | rank 0 |
| d ∈ [2, 12] — the Context table's actual protocol | 7 430 000 | — | — | — | truth outside the domain |

**The criterion as written was already met before this WP** (row 1, "before"
column) — see the box at the top. The result that is actually new is row 2:
d ∈ [2, 20] expired incomplete at 300 s with **zero** candidates and 4.24 M
boxes, and a 2 700 s run was still going when it was killed at 27 minutes. It
now completes in **32 s**, ranking the truth first. That is the domain a caller
who does not already know the answer will search, since 2 Å is the package
default, and it is the one the benchmark's default mode specifies.

Per-system timings restated (whole-file `--durations`, uncontended):

| row | before | after |
|---|---|---|
| `test_dichotomy_recovers_a_known_cell[orthorhombic]` | 0.73 s | **0.28 s** |
| `test_dichotomy_recovers_a_monoclinic_cell` | ~84 s | 85 s |
| `test_trial_error_recovers_a_monoclinic_cell` | ~91 s | 95 s (untouched engine) |
| cubic / tetragonal / hexagonal / trigonal | ≤ 0.14 s | ≤ 0.2 s |

Orthorhombic gains 2.6× because it has four centrings and now pays one grid
pass. **Monoclinic's own test row does not move, and the reason is worth
keeping**: `CASES["monoclinic"]` declares `min_volume` at its default 15 Å³
against `max_volume` 1500, a 100-fold volume band, so the determinant prune has
almost nothing to bite on. The gains here are largest exactly where the caller
declares a real volume window — which the published protocol does and the test
fixture does not.

## References

- Louër, D. & Louër, M. (1972). *J. Appl. Cryst.* **5**, 271–275 — Table 1
  transcribed above.
- Boultif, A. & Louër, D. (1991). *J. Appl. Cryst.* **24**, 987–993; (2004).
  *ibid.* **37**, 724–731.
- Werner, P.-E., Eriksson, L. & Westdahl, M. (1985). *J. Appl. Cryst.* **18**,
  367–370 — the short-axis test and Table 1's basis-line sets.
- Smith, G. & Kahara, E. (1975). *J. Appl. Cryst.* **8**, 681–683 — the 020
  detector.
- Visser, J. W. (1969). *J. Appl. Cryst.* **2**, 89–95 — ITO.
- Oishi-Tomiyasu, R. (2013). *J. Appl. Cryst.* **46**, 1277–1282 — eqs (4),
  (5), (7), (9)–(11).
- Dong, C., Wu, F. & Chen, H. (1999) — the reflection-pair zero-shift estimate,
  as cited by Boultif & Louër (2004) §3. **Not held**; request it before
  implementing that half.

## Handover log

- **2026-07-31 — closed.** Everything in Tasks is done or declined on
  measurement; the box at the top of this file is the part worth reading first.

  **Done.** Hall's condition in `_test_box` and `_push_children`
  (`186525a`); one grid pass per system instead of per centring, with the
  subset property asserted (same commit); `M^Rev`/`M^Sym` with `N^cal` and a
  vectorised `laue_multiplicity` (`79caa44`); `docs/manual/engines.md` plus six
  bib entries, and the ITO and Louër-floor no-goes (`462d575`); the determinant
  bound through the correlation form, intersected with the expansion
  (`1ef07e7`), and the centred prune replayed at the leaf (`4fa8b94`).
  Eight tests added across `test_indexing_engines.py` and
  `test_indexing_core.py`, all of them soundness or definition checks rather
  than recovery checks.

  **The result.** d ∈ [2, 20] — the paper's default mode and the package's own
  `DEFAULT_MIN_D_AXIS` — went from *expired incomplete at 300 s with zero
  candidates, still running at 27 minutes* to **complete in 32 s with the truth
  ranked first**. d ∈ [5, 20] went 532 203 → 234 227 boxes. Full table in
  Acceptance.

  **The method lesson, and it is the reason this WP's ranking was inverted.**
  Every cost item in Context was reasoned from the *algorithm's structure* —
  which prune is inert, which loop is redundant — and the ranking that produced
  was close to backwards, because the structure does not say **where the boxes
  are**. One afternoon's instrumentation of `_test_box` (count the deaths, by
  cause, and mark the phase boundary) said: 97.6 % of boxes are in phase 2, the
  line prune refuses 0.0 %, and the item ranked fifth of five refuses 89.9 %.
  The WP's item 1 was the right *diagnosis* — the volume prune really is inert,
  and the numbers quoted for it reproduce exactly — attached to the wrong
  *cause* (staging rather than interval decoupling) and the wrong *phase*.
  **Instrument before ranking**; a plausible cost model is not a profile.

  Two things a successor should not have to rediscover. **A candidate cell is a
  lattice, not a tuple** — the bethanechol truth legitimately returns as its
  `c + a` setting at β = 139.7°, so any harness comparing sorted axes will
  report a false miss; use `reduce.same_lattice`. And **a wall-clock comparison
  under a second search on the same machine is worthless** — the two extra FoM
  members were briefly blamed for a 23 → 46 s regression that was entirely a
  background job, and timing `rank_candidates` directly put its true cost at
  0.0 s of a 40 s search.

  **And the third, which is this WP's own contribution to the file's running
  theme**: every prune added here is sound, and the one that went wrong went
  wrong by being *removed* somewhere it was not noticed — see "The one defect
  this WP introduced" above. `tests/test_acceptance_indexing.py` earned its
  runtime: 115 fast indexing tests were green across every commit that carried
  the defect, and a real certified pattern was what said otherwise. Run it
  before closing anything that touches an engine.

  **Not done, and pushed rather than dropped.** The three ranking failures
  1026 handed over need *its* real-data rows to verify (brucite, magnetite,
  FAP); `DEFAULT_SEARCH_LINES` picking the wrong twenty lines on a synchrotron
  pattern is a peak-list question, untouched; NAC's `reflection_ceiling_ok`
  block is a reflection-count limit no prune here reaches; and Dong, Wu & Chen
  (1999) is still not held. All are in the consumed Inherited section above and
  have been forwarded to 1026 and 1027.

- **2026-07-30** — created from an assessment session that read seven supplied
  papers against the tree. Nothing implemented here. Every number in Context is
  measured on this branch on that date, and two hypotheses were **refuted** in
  the process and are recorded so they are not re-run: the A…F formulation does
  *not* lose the volume prune to interval inflation (1.1–3.2× at grid-cell
  scale, 93 % of the prune survives), and the failure is *not* a
  `MAX_GRID_CELLS` frontier overflow (5.7 M boxes against a 4×10⁵ cap, budget
  expiry). ITO's hoped-for zero-point immunity was also refuted, by the
  arithmetic in Context.
