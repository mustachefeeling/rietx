# WP-1997 — the direct-space solver on main: site classes, kernels, chemistry, engine and entry point

Milestone: structure-solution · Status: ⬜
Depends on: 1902 (shipped, the cost); 1901 soft (the map, needed only by completion); 1940 (shipped, the kernel crate)
Priority: P2 2026-10-17 — a feature the open milestone was opened for, and three outside PRs (#1013, #1015, #1016) wait on this number

## Goal

`solve_seed` takes a verified cell, a space group and a composition, and returns
a ranked list of structure candidates with their evidence. It has no
`.structure`, and its one gated singleton is `best_or_none()`. It runs on the
cost WP-1902 built, over the Wyckoff classes of the group, with the chemistry
terms reported beside χ², and its inner loops are in `rietx-kernels`.

## Context

**Where this comes from.** Issue #562 (@mustachefeeling) scoped the work and
WP-1515 recorded the scoping. WP-1515 builds nothing, and its non-goal says
nothing from the contributor's spike merges as it stands. The spike predates
WP-1940 and is about 2 100 commits behind `main`. So each chunk below is
rebuilt on `main`, one PR each, branched off `main` and none stacked.

**The cut.** The contributor proposed it on #562 on 2026-10-16, and the
maintainer cut this WP for it on 2026-10-17.
1. The site classes (#1013), a prerequisite the 2026-09-30 review placed before
   the engine.
2. The solver's compiled kernels (#1015), WP-1515's S4 restated as the solver's
   own throughput kernel.
3. The chemistry terms (#1016), WP-1515's S3.
4. The engine, WP-1515's S2a.
5. The entry point, WP-1515's S2b.

The first three are open as PRs, each saying "WP number pending". The last two
are not yet opened.

**What is on `main`.** `solve/cost.py` (WP-1902): the profile χ² as a quadratic
form in the intensity vector, χ²(I) = c − 2rᵀI + IᵀMI with M = ΩᵀWΩ, floored by
its own least-squares solve, and refusing by name a magnetic phase, a
Rietveld-mode model, a satellite and a poor extraction. The engine calls it. It
never calls `predict()` in its loop.

**The design that is decided** (#562, 2026-09-30, and WP-1515's Inherited
entries at the time):
- The answer is a list. `high` needs agreement across independent seeds, and
  every grade ships provisional under a versioned thresholds contract, like
  `indexing_thresholds_version`. The prototype's blind-contrast threshold is
  proposed, not validated, and the Kabova et al. (2025) bars are "worthy of
  close inspection" and not pass bars.
- Special positions and Wyckoff-class enumeration are in from the start
  (amendment (b)). The enumeration reuses `symmetry.site_orbit` and
  `wyckoff.site_constraints`, so there is one orbit authority.
- A prior-off control arm of at least two seeds runs every time. If its leader
  is structurally different and at least 10 % better in χ², the prior-on leader
  is capped at `low` (amendment (c), `prior_excludes_better_fit`).
- The ladder is planned and has no burn-in. Its top temperature is the
  χ²/χ²_floor spread of random structures, and its replica count comes from
  Earl & Deem (2005), eq. 3, at C_v = n_par/2. The contributor's paired
  measurement on a synthetic P2₁/c set at 600 k evaluations per seed gave
  ≥ 17/20 seeds at 18 and 24 DOF and ≥ 15/20 at 30. The regression arm is the
  fixed ladder, reproducing the earlier numbers bit for bit. Swap acceptance is
  recorded per pair and not gated. Nothing is promised above about 30 DOF.
  These numbers are from a private prototype and are targets until the engine
  PR measures them on a public set.
- A term is reported beside χ² and never folded into it. The numpy path stays
  as the fallback and the oracle for every kernel (WP-1115's rules).

**Seams that cross chunks.**
- `model/compiled.py` gets the three entry points in #1015, with the names in a
  new `SOLVE_NAMES` beside `KERNEL_NAMES`, since nothing in `src/` calls them.
  The engine's first caller moves them into `KERNEL_NAMES` and raises
  `KERNEL_FLOOR` to 1.4 in the same change. It also carries the release note
  that rietx needs rietx-kernels 1.4.
- The kernel's contact term loops over the 27 cells around the minimum image,
  which holds every contact only while r₀ is under 1.5 plane spacings. #1015
  refuses past that bound by name, with the wording of `site_clash` in #1016.
  The engine dispatches between them and treats both refusals alike.
- A new kernel bumps the crate's minor. The `kernels-v1.4.0` tag follows
  `docs/RELEASING.md` § The kernel wheel, and the maintainer pushes it.
- The answer type moves `SCHEMA_VERSION`, which WP-1343 and PR #522 also
  contest. The entry point waits for the maintainer's call on timing. A solve
  `Capabilities` field is a registry arm, not a `features` boolean.
- #1016 carries #675's radii tables (Shannon, Pyykkö and Pauling) and its
  `ATTRIBUTION.md` rows. #675 closes as merged into #1016.

### Inherited

- **2026-10-16, from WP-1515 (the #998 triage): `solve_seed` checkpoint, resume
  and progress.** Single seeds on the reporter's blind kit (36 atoms, 4 species,
  lab X-ray) ran past 1 h and then 8 h timeouts, and each kill lost the whole
  deterministic trajectory. The entry point is asked for an atomic checkpoint at
  `_race`'s natural boundaries (RNG state, stage and round, `alive`,
  `rec`/`best_u`, ladders, `evals`/`swaps`, finished records). Resume is refused
  on a cost, spec or version mismatch. Best-so-far candidates carry
  `partial=True`, and a progress callback reports a real fraction done. The
  acceptance is that an interrupted-then-resumed run is byte-identical to an
  uninterrupted one. The reuse seams are `CancelToken` and `runs.py`, never a
  new channel. The reporter will PR it against whichever chunk lands the
  engine.
- **2026-10-05, from WP-1515 (#677): space-group competition is a later WP.**
  `high` is for now "high, given this group". The #677 design (candidates from
  the unrefuted extinction classes, group leaders compared by ΔBIC on χ²_CI at
  N_clump, `space_group_confidence`, an extraction retry, a four-outcome
  acceptance table) is not part of this WP. The radii half of #677 lands in
  #1016.

## Non-goals

- Charge flipping (WP-1515's S6a and S6b) waits for a public case that defeats
  direct space.
- The difference-Fourier map is WP-1901, and completion by difference Fourier
  (S5) needs it. The contributor asked on #562 whether direct space may land
  before 1901, and that order is the maintainer's to rule on. The engine does
  not need the map until S5.
- A general compiled |F|² kernel. `structure_factor.py` is untouched.
- Rigid-body fragment moves (the rigid-bodies milestone's R0 and R1). Free-atom
  moves come first.
- Space-group competition, preferred orientation and Z′ (S9, #677), mixed
  occupancy in the enumeration, and reducing assignments by the affine
  normaliser.
- The GUI run kind and candidates panel (S7b), and the acceptance corpus and
  scoreboard (S8). Each gets its own WP when its chunk is cut.
- Nothing from the contributor's spike merges as it stands.

## Tasks

Each item is one PR off `main`. Check off as they land.

- [ ] Site classes (#1013): `crystallography/site_classes.py`, `site_classes()`,
      `site_assignments()`, an exact count and a named refusal past
      `MAX_SITE_ASSIGNMENTS`, checked across all 564 gemmi settings
- [ ] Solve kernels (#1015): `kernels/src/solve.rs`, rietx-kernels 1.4.0, three
      entry points in `model/compiled.py`, `tests/test_solve_kernels.py`; after
      merge, the `kernels-v1.4.0` tag
- [ ] Chemistry terms (#1016): `solve/chemistry.py`, `Composition`, the
      minimum-image contact term, the coordination prior and `CandidateCost`;
      #675's radii tables; #675 closes as merged
- [ ] Engine: sites from the site classes, moves, and the planned parallel
      tempering on WP-1902's cost, calling the kernels with the numpy functions
      as fallback and oracle; the prior-off control arm (amendment (c));
      candidates clustered across seeds, symmetry-equivalent and enantiomer
      solutions as one; `SOLVE_NAMES` into `KERNEL_NAMES`, `KERNEL_FLOOR` to
      1.4, the release note; `ATTRIBUTION.md` rows for DASH (MIT), FOX (GPL-2),
      GALLOP (GPL-3), Superflip, the TOPAS reference § 10.23, Kabova and Earl &
      Deem
- [ ] Entry point: `solve_seed`, the answer type with no `.structure`, the
      provisional grades and their versioned thresholds contract, the events,
      and the #998 checkpoint, resume and progress
- [ ] Tests (unit; the acceptance rows above) + the ladder's measurement on a
      public synthetic set
- [ ] Skill: none until the entry point is public, then its routing row (root
      CLAUDE.md § skill)

## Acceptance

The commands the three open PRs state, on the PRs' own platforms:

```sh
.venv/bin/python -m pytest tests/test_site_classes.py tests/test_docs_consistency.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_site_classes.py::test_every_setting_matches_spglib -m slow -n 0
.venv/bin/python -m pytest tests/test_solve_kernels.py -q
.venv/bin/python -m pytest tests/test_solve_chemistry.py tests/test_solve_cost.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The engine and entry-point PRs add their own rows here when they are opened.
Their bars are WP-1515's: simulated structures recovered within 0.10 Å by at
least two of four seeds, symmetry-equivalent solutions clustered as one, no
`.structure` on the result, `best_or_none()` is `None` for one finder, and a
cancelled run returns what it has.

## References

- Issue #562, and its 2026-10-16 comment with the cut. Issues #677 and #998.
- WP-1515 (the scoping), WP-1902 (the cost), WP-1901 (the map), WP-1940 (the
  kernel crate).
- PRs #1013, #1015, #1016, and #675 (the radii tables, folded into #1016).
- David (2004), *J. Appl. Cryst.* 37, 621: the Rietveld and correlated-intensity
  costs (abstract read only).
- Earl & Deem (2005), *Phys. Chem. Chem. Phys.* 7, 3910, § 2.3: replica ladders.
- Favre-Nicolin & Černý (2004), *Z. Kristallogr.* 219, 847 (FOX is GPL-2:
  concepts only).
- Spillman & Shankland (2021), *CrystEngComm* 23, 6481 (GALLOP is GPL-3:
  concepts only).
- Kabova et al. (2025), *Acta Cryst.* C81, 559: proposed bars, to be checked
  against the paper's text before they become constants.

## Handover log

- **2026-10-17** — created at the maintainer's request for the #562 chain; #1013, #1015 and #1016 are open against it, reviews in progress. Next: review each PR against this file.
