# WP-1324 — symmetry silences: an orbit that is not a multiplicity, and a setting nobody chose

Milestone: unscheduled · Status: ✅ 2026-09-02
Depends on: —

## Goal

Two silent wrong answers in `crystallography/symmetry.py` are closed. An
orbit's length is a multiplicity — |G| divided by the stabiliser order, which
divides |G| — or the expansion raises, never a count that depends on the order
gemmi yields operations in. And a Hermann-Mauguin symbol that arrives without
a setting suffix where the tables hold more than one setting is resolved *and
reported*, at every construction site that resolves a symbol without a file to
take the setting from — the hand-built `Phase` above all.

## Context

Two issues filed 2026-09-01, one module, one consequence: a wrong site
multiplicity is frozen onto the compiled model and reaches ZMV and every
`weight_percent`, while the fit converges.

**Issue #215 — the orbit.** `expand_orbit` deduplicates images with a greedy,
first-fit comparison at `tol = 1e-4` per fractional axis. Greedy is not
transitive (a≈b and b≈c do not give a≈c), so the partition depends on operation
order, and nothing checks the invariant. An 18h-type site of `R -3 m:H`
(|G| = 36) obeys y = 2x; perturbing that relation by ±1.0e-4 returns orbits of
**22 and 30**, neither a divisor of 36, where 18 and 36 are the only possible
answers. It bites a published CIF: ICSD 18318 (β-rhombohedral boron, 16 B
sites, coordinates to five decimals) puts several y = 2x relations off by
exactly 1e-4, and site B11 lands at `+1.0000000000000286e-04` — over `tol` by
ULPs — and expands to **30** against the CIF's own
`_atom_site_symmetry_multiplicity` of 18.

**Issue #217 — the setting.** For the 40 H-M symbols with two settings, gemmi
resolves the bare symbol to the first (`F d -3 m` → `:1`). Spinel at origin
choice 2's coordinates under `:1` **swaps** the 8a and 16d multiplicities
(A at (⅛,⅛,⅛): 16 under `:1`, 8 under `:2`; B at (½,½,½): 8 against 16), so a
phase built by hand with the symbol a paper prints and the coordinates it
lists gives A₂BO₄ where AB₂O₄ was meant — wrong `element_counts`, wrong ZMV,
wrong fractions, nothing reported. Two routes already do this right and are
the pattern to follow: `crystallography/cif.py` prefers gemmi's own reading of
the file and raises on the fallback; the TOPAS reader maps the trailing `Z` to
`:2` (WP-1118). The exposure is the object API.

**Rules that bind.** Every symmetry refusal is raised in
`ParameterTable.__init__` and a silent correction is a *reader's* to make,
never a table's — so a snapped coordinate is reported through a reader's
diagnostics channel (`CIF_SPECIES_NORMALISED` is the precedent) and a
hand-built phase gets its own channel or a refusal. Cell ties follow the
space-group *setting* (WP-1036; `read_small_structure` already picks the R
setting from the cell), which is the precedent for choosing a setting from
evidence and saying so. Multiplicities feed `phase_zmv`
(`optimize/qpa.py`), whose `element_counts` are occupancy-weighted per site.

**Prior art, concepts only.** cctbx derives a site's symmetry from the
stabiliser and snaps the coordinate to the exact special position within a
tolerance, so the multiplicity is a group-theoretic fact rather than a count;
GSAS-II does the same at atom entry and shows the site symmetry beside the
multiplicity.

## Non-goals

- Choosing the setting for the user. The bare symbol keeps gemmi's resolution;
  what changes is that the choice is visible and the alternatives named.
- Re-deriving Wyckoff constraints (`wyckoff.py` owns those and already reads
  the stabiliser).

## Tasks

- [x] `expand_orbit` by stabiliser: orbit = |G| / |stabiliser|, images generated
      once per coset, the coordinate snapped to the special position it is
      within `tol` of; raise `ORBIT_NOT_A_MULTIPLICITY` if a count ever fails
      to divide |G| (a guard that should become unreachable, kept as the
      invariant).
- [x] The snap is reported: `SITE_SNAPPED_TO_SPECIAL_POSITION` with the site,
      the shift, and the multiplicity, on `structure_from_cif`'s channel and
      on the `Phase`/`Structure` construction path.
- [x] `SPACE_GROUP_SETTING_ASSUMED` on every bare-symbol resolution where the
      tables hold more than one setting, naming the setting taken and the
      others; `Phase.space_group` validation is the one place for it, so the
      CIF and TOPAS routes (which carry a setting) stay silent.
- [x] The issue's two reproductions as tests: the ±1.2e-4 sweep on `R -3 m:H`
      prints only 18 or 36; ICSD 18318's sixteen sites match the CIF's
      multiplicities; the spinel table under `:1` and `:2`.
- [x] Skill and manual rows for the two codes; a Part 2 note that a
      multiplicity is |G|/|stabiliser|.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_wyckoff.py tests/test_symmetry_orbits.py
.venv/bin/python -m ruff check src tests examples
```

No fitted number may move for a structure whose orbits were already right;
the validation matrix's real-data suites are the check.

## References

- Issues #215 and #217 — the reproductions and the measured tables.
- International Tables Vol. A — site multiplicity as |G|/|stabiliser|.
- WP-1036 (settings decide the ties), WP-0301 (the Wyckoff derivation),
  WP-1028 (reader-side repairs are reported).

## Handover log

### 2026-09-02 — done

A phase quantification can no longer be wrong by a few per cent because of how
its atoms were counted. Two ways that used to happen are closed, and both are
now reported rather than assumed: a site sitting a whisker off its special
position is counted as being on it and told about, and a space-group symbol
written without its setting says which setting it was given and what
composition each alternative implies. Neither mistake moved Rwp, which is why
neither had ever surfaced in a fit — the published boron structure that
prompted this put 327 atoms in a cell holding 315 and refined perfectly. The
cost is nothing measurable: every op subset the forward model freezes for the
standards this repo fits is bit-identical to before.

**Done.** All five tasks; eight commits.

- **The orbit (#215).** `symmetry.site_orbit` is the one authority for a site's
  stabiliser, snapped position, multiplicity and orbit images. Four steps:
  operations fixing the site within `tol`; their Reynolds average as the snap;
  the **snapped point's own** stabiliser; one operation per left coset.
  `expand_orbit`, `expand_positions`,
  `structure_factor.select_orbit_ops` (the subset frozen onto the compiled
  model, and what `phase_zmv` counts atoms with), `wyckoff.stabilizer_rotations`
  (the constraint bases) and `site_constraints` all read it. That consolidation
  *is* the second half of the bug: taken separately, the allowed directions and
  the orbit length are answers to different questions whenever a per-operation
  threshold admits a set that is not a subgroup, and only one of the two was
  ever reported.
- **The setting (#217).** `setting_alternatives(symbol)` →
  `(taken, others)`; `refine._symmetry_silence_diagnostics` renders it.
- **Reports.** `SITE_SNAPPED_TO_SPECIAL_POSITION` on `result.diagnostics` and on
  `structure_from_cif`'s channel (one builder, `symmetry.snap_diagnostics`, so
  the two say the same thing); `SPACE_GROUP_SETTING_ASSUMED` on
  `result.diagnostics`. Skill rows in `references/diagnostics.md`; manual Part 1
  in `using/files.md`; Part 2 equation `par-multiplicity`.

**Measured** — `[dev]` venv (no jax/torch), Python 3.12.12, darwin/arm64, this
worktree, on current `origin/main` merged in:

- Acceptance `tests/test_wyckoff.py tests/test_symmetry_orbits.py`: **105
  passed**. Fast selection `-m "not slow"`: **3952 passed, 122 skipped**, up
  exactly the 32 tests `test_symmetry_orbits.py` adds from 3920/122 on `main`
  — no new skips. Full selection: see the final line of this entry.
- `ruff check src tests examples` clean; `sphinx -W` clean.
- **The invariant, over gemmi's whole table.** 564 settings × 30 positions
  (general, special, and jittered at 3e-5 / 9.9e-5 / 1.01e-4 / 5e-4 across the
  tolerance) = **16 920 sites: 0 non-divisors, 0 raises.**
- **The acceptance clause, measured against the old code rather than inferred
  from a green suite.** "No fitted number may move for a structure whose orbits
  were already right": the pre-WP greedy implementation was re-run beside the
  new one over the standards the acceptance suites fit (LaB6, spinel both
  settings, FAP, corundum, brucite, cBN/Si, NaCl/CaF2, rutile) and both bundled
  CIFs — **28 of 28 site op-subsets bit-identical**. The forward model reads
  exactly that subset, so this is the whole claim.

**Gotchas** — four things a successor should not have to rediscover.

1. **Recomputing the stabiliser after the snap is what makes the guard
   unreachable, and it was not obvious.** A first cut trusted the
   tolerance-admitted set and raised `ORBIT_NOT_A_MULTIPLICITY` on **157 of the
   16 920** fuzzed sites — all jittered cubic ¼¼¼ and ⅛⅛⅛ positions, where a
   per-operation threshold admits some members of the site symmetry and misses
   others, so the set is not a subgroup and |G|/|S| is not an integer. Steps 3
   and 4 measure one point's *own* stabiliser and one point's *own* orbit, so
   orbit-stabiliser settles it by construction. The guard is kept as the
   invariant and is provoked in the test by monkeypatching the coincidence
   tolerance, since nothing else can reach it.
2. **The tolerance comparison is inclusive to a relative 1e-9**
   (`_SITE_TOL_SLACK`), and that is what makes the boron case give 18 rather
   than 36. A file quoting five decimals lands on the boundary *exactly* —
   `1.0000000000000286e-04` against `9.999999999998899e-05` for the same
   nominal 1e-4 — so a strict `<` let binary rounding decide a crystallographic
   question. Without this the stabiliser fix alone returns a *consistent* 36,
   which satisfies the divisor invariant and still disagrees with the file.
3. **The snap is reported, not applied.** Stored coordinates are untouched:
   rewriting one moves a refinement's start values, and the deviation may be
   real. The coordinate DOF anchor (`x = x₀ + Σ Bₖθₖ`) keeps it either way, so
   the site refines from where the file put it while counting the atoms the
   symmetry says are there. `SiteOrbit.shift` reports 0.0 below `_SNAP_NOISE`
   (1e-12), because a site already on its position averages to itself only to
   within an ulp — h·x/h is not exactly x unless h is a power of two — and
   reporting that is reporting arithmetic.
4. **Outside `mode="rietveld"` the atoms are a scaffold.** A Le Bail or Pawley
   phase carries one dummy atom, so the composition line read `C8` against
   `C16` from the dummy carbon and a snap report would have described a
   placeholder. `_symmetry_silence_diagnostics(structure, mode)` drops both
   there — but still reports the *setting*, because `:H` against `:R` changes
   the operators themselves and so decides the reflection list a Le Bail fit
   partitions.

**Three departures from the WP as written**, all deliberate.

1. **Not in `Phase.space_group` validation**, which the WP named as "the one
   place for it". A pydantic validator has no diagnostics channel — the same
   reason `ParameterTable` refuses a bad cell angle instead of correcting it —
   so the report is built at fit time and lands on `result.diagnostics`. The
   silence the WP wanted falls out anyway: a symbol carrying its setting
   returns `("", ())`, so the CIF and TOPAS routes never fire it. Issue #217's
   tail ask (assert the symbol resolved, name the string that failed) is
   already `get_spacegroup`'s behaviour, and this gemmi resolves `P42/mnm`, so
   nothing was owed.
2. **ICSD 18318 is not in the tree.** The WP asked for its sixteen sites as a
   test; ICSD is licensed data and the root CLAUDE.md fences a data file at the
   point it would ship. The reproduction is pinned to the *arithmetic* that bit
   instead — `test_b11_shape_is_the_float_that_bit` asserts the five-decimal
   x/y pair's `y − 2x` is that float and is over a strict 1e-4. The mechanism
   is the coordinates, not the file.
3. **The message quotes the composition each setting implies**, not the
   symbols. That was issue #217's own "stronger version" and it is the part a
   caller can recognise: `F d -3 m:1 → Al8 Mg16 O32` against
   `:2 → Al16 Mg8 O32`, one of which is obviously not spinel. "Ambiguous
   symbol" is a warning nobody reads.

**One thing not done, and it is the maintainer's call.** `SKILL.md`'s QPA row
got a pointer — `no unresolved scale-family diagnostic` became `scale- or
ZMV-family`, +8 B — rather than naming the two codes. The body is **31 968 B
against its 32 000 cap**, and `tests/test_skill.py`'s docstring says a full
body is fixed by moving a lookup into `references/`, never by raising the cap
for one. The rows are in `references/diagnostics.md`, which is where the root
CLAUDE.md rule points. Naming both codes in the QPA row outright costs ~85 B
that something else in the body has to pay, and that is a decision about every
future session's fixed cost. WP-1118's own `### Inherited` records the same cap
pressure from 2026-08-30 (27 B of headroom then), so this is now the second
session to hit it — worth a deliberate look before a third does.

**Forward references written** (protocol step 5): `### Inherited` entries in
[1118](1118-foreign-model-files.md) (the `.pcr` reader and the exporter
registry inherit the bare-symbol choice the `.inp` reader already made, and an
exporter must write the *resolved* setting or a round-trip launders it),
[1319](1319-structure-interchange.md) (the CIF writer has the same obligation
and checkCIF cannot catch it; the XYZ half gets the sharper form) and
[1320](1320-qpa-multimodal-fraction.md) (these two are the *ZMV family* against
the scale family its background and absorption checks cover).

**Code review** (protocol step 9): `/code-review medium --fix` — outcome
recorded in the line below, added after the pass returned.

**Next.** Nothing blocks on this and no successor inherits unfinished work
here. In order: (1) close issues #215 and #217 on the PR; (2) the SKILL.md cap
decision above, whenever someone is next in that file — it is the second
session to hit it; (3) unrelated, the WPs this one sat beside in the
"what fires, and what stays silent" group are untouched — 1310, 1311, 1320,
1321, 1323 — and 1320 now has an `### Inherited` entry it did not have.

- **2026-09-01** — created from issues #215 and #217 during the roadmap
  reorder; no code touched.
