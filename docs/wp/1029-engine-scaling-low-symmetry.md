# WP-1029 — Indexing at low symmetry: search cost, and the figures that rank it

Milestone: v1.0 · Status: ⬜ not started
Depends on: 1020–1022 (all landed); 1026 soft (it owns the benchmark that grades this)

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

### Inherited

**From the 2026-07-30 assessment session** (papers read, nothing implemented):
`refine_with_shift` declines its own correction on exactly the candidates that
need it — see WP-1026's handover of the same date. That is 1026's to fix, but it
interacts here: the shift allowance widens every box's `hit` matrix and so
multiplies items 1, 4 and 5. DICVOL's posture is the opposite of ours — it
*estimates and removes* the shift before the search (Dong, Wu & Chen 1999
reflection pairs, then a zero-offset variable in the final least squares) and
searches at a 0.02–0.03° window, where we search at ~0.05°. That method needs
only the peak list, so it belongs in `indexing/quality.py`, and it would let
`assess_peak_list` report a **measured** `shift.source` — which is also what
unblocks the `shift_allowance_assumed` caveat 1026 records as the reason `high`
is unreachable on real lab data. One technique, two problems.

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

- [ ] Re-stage the grid so E is cut before C, and turn `V ∈ [V₋, V₊]` into a
      closed-form range for C rather than a test on its children. Re-measure the
      table at the top of Context; it is the acceptance evidence.
- [ ] Drop the redundant per-centring grid pass; re-score P-accepted metrics
      under every admissible centring instead. Assert the subset property
      (`centring_allows` C ⊂ P) in a test so the shortcut is not folklore.
- [ ] Louër & Louër Table 1 parameter floors as **loop bounds**, with the
      non-collinearity condition on d₁/d₂ implemented and tested in both
      directions (a collinear pair must fall through to the next vector). Derive
      and *label as derived* the monoclinic form.
- [ ] Decide `MAX_ANGLE_COSINE` on measurement: a declared β ≤ 130–135° with the
      bound reported, or evidence for keeping 150°. It is a costed choice.
- [ ] Bipartite-matching feasibility in `_test_box` (reject, don't deprioritise).
- [ ] `M^Rev` and `M^Sym` in `fom.py` with `N^cal`; add them to the panel and to
      `blind_spot`; check the Borda ranking still puts the truth first on the
      1020/1024 synthetic supercell cases before trusting them on real data.
- [ ] Decide the third engine **after** re-measuring, and record the decision
      either way — a no-go here is as much a deliverable as WP-1023's was.
- [ ] The theory manual has **no engines chapter**, so `dichotomy.py` and
      `trial_error.py` implement published algorithms cited only in module
      docstrings. Add one, and move the DICVOL/TREOR/ITO citations into
      `references.bib` (they are in ATTRIBUTION.md as of 2026-07-30; the manual's
      guard requires a bib entry to be cited, which is why they are not there yet).

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

Restate the per-system timings from WP-1021/1022 afterwards: this changes them
all, and those numbers are quoted in three places.

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

- **2026-07-30** — created from an assessment session that read seven supplied
  papers against the tree. Nothing implemented here. Every number in Context is
  measured on this branch on that date, and two hypotheses were **refuted** in
  the process and are recorded so they are not re-run: the A…F formulation does
  *not* lose the volume prune to interval inflation (1.1–3.2× at grid-cell
  scale, 93 % of the prune survives), and the failure is *not* a
  `MAX_GRID_CELLS` frontier overflow (5.7 M boxes against a 4×10⁵ cap, budget
  expiry). ITO's hoped-for zero-point immunity was also refuted, by the
  arithmetic in Context.
