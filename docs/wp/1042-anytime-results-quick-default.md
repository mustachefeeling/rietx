# WP-1042 — Anytime results, and `quick` as the default

Milestone: v1.0 · Status: ⬜
Depends on: WP-1037

## Goal

`index_pattern()` produces a usable ranked shortlist early instead of only at the
end: systems searched cheapest first, progress and provisional candidates streamed,
and a `quick` preset as the default. This is the behaviour-changing half of the UX
work, and it carries the acceptance re-measure that forces.

## Context

### The target, and what it actually is

The stated design target is TOPAS's indexing module — *a rapid, sufficient, ranked
list*. WP-1037's measurement establishes the honest framing: our 30–150 s per real
dataset is normal for the field (DICVOL04 reaches 3770 s on hard triclinic patterns;
McMaille needs "hours, if not a night" for a full-symmetry search; Conograph's
exhaustive quick search is ≤5 min). So responsiveness has to come from **ordering
and reporting**, not from a smaller search box: the hard cases are irreducibly slow
and pretending otherwise would be an unmeasured cost model, which is what WP-1030's
method lesson forbids.

### Why the first design — "drop the dichotomy engine" — is wrong

It was the obvious way to make a fast default and it fails twice, silently:

- `consensus.grade` (`consensus.py:326`) returns `low` when
  `len(set(found_by)) < 2`. A one-engine default grades **every** candidate `low`,
  and `low` stops meaning "refuted" and starts meaning "you ran the default".
- `trial_error` sets `search_complete = True` when it finishes its trial set
  (`trial_error.py:340,377`). That means "I covered my table", not "no cell of this
  symmetry exists". A one-engine run therefore carries **no** `search_incomplete`
  caveat and reads as *more* complete than a two-engine one.

So `quick` keeps both engines and the consensus gate. A single-engine run stays
available via `--engines` and gains an `INDEX_SINGLE_ENGINE` **diagnostic** — not a
caveat, because a *capping* caveat cannot explain a `low` that `grade` produces
structurally. **Open question, not answered here:** whether the three-level
confidence vocabulary needs a fourth value once fast single-engine runs are a
legitimate mode.

### The three mechanisms

1. **Cost-ordered systems** — cubic → hexagonal → trigonal → tetragonal →
   orthorhombic → monoclinic → triclinic. Conograph measures the same gradient
   (cubic 1.3 inner calls against triclinic 105 in Coelho's Table 5).
2. **Volume tightening from a higher-symmetry solution** — Boultif & Louër §4.1:
   each system is explored to the input volume limit *"unless a solution has been
   found with a higher symmetry. If so, the maximum value is replaced by the volume
   of the unit cell found and the search continues."*
   **This is the dangerous one and must not ship ungated.** DICVOL04 can do it
   because its dichotomy is exhaustive by volume shell and it explicitly seeks the
   smallest cell. Our scoreboard has two datasets where a *supercell* ranks first,
   and SRM 660c where a **smaller**-volume tetragonal-P rival is exactly isospectral
   with the cubic-P truth. Tightening on a wrong "solution" silently truncates the
   remaining search — against the standing **no silent caps** rule. It needs a
   quality gate on the triggering candidate plus a diagnostic recording that it
   happened and to what value, or it does not land.
3. **Streaming** — and the trap here is that streaming raw candidates may be *worse*
   than waiting. Rank comes from Borda over the FoM panel **after** cross-engine
   merge, dedup, the Bravais screen and the gate; a freshly found engine candidate
   has none of those, so a streamed list would reorder and shrink as the run
   proceeds. Stream **progress facts** (units done, elapsed/remaining, count so far,
   best M₂₀ so far) always; stream cells only as explicitly *provisional*, never
   carrying a `confidence`. Decide this in the design, do not discover it in the GUI.

### The honest cost of cost-ordering

With a binding total deadline, cost-ordering means the systems that get sacrificed
are the **low-symmetry ones** — exactly where indexing is hard and where a user most
needs the answer. That is acceptable only if WP-1037's *not reached* state is loud
in the result, the CLI and the GUI. The default `total_budget_seconds` must be
chosen knowing triclinic is what gets cut.

### The dominant cost of this WP

Flipping the default is not a tail item. Acceptance rows assert specific ranks, M₂₀
values and confidences, so many will move; `docs/VALIDATION.md` regenerates;
`validation_matrix.py` Claims move; and the eight-dataset scoreboard must be
re-measured in all three places it is copied. **Budget the re-measure as the bulk of
the work, not the finish.**

Two scoreboard defects to fix while re-measuring rather than propagate: its
arithmetic does not close (5 + 1 + 2 = 8 but nine datasets are named), and brucite
and magnetite — the two failures — were measured **before** WP-1030's prunes and are
not test rows.

### Licensing

Concepts from DICVOL04/TOPAS/McMaille/Conograph via their published papers; no code
ported from any of them.

## Non-goals

- The ceiling, the deadline, the progress ladder and the `capabilities` bug —
  WP-1037, which must land first.
- Changing what any engine searches *within* a system.

## Tasks

- [ ] **Task 0 — does ordering plus streaming actually deliver a shortlist in
      seconds?** Using WP-1037's instrumentation, record **time to first candidate**
      and time to final ranked list per dataset, split by system. If the answer is
      "no for low symmetry", that is the finding — report it, do not tune around it.
- [ ] Cost-ordered systems, overridable by `spec.systems`, with the ordering derived
      from metric DOF rather than hard-coded.
- [ ] Progress facts streamed on WP-1037's ladder; provisional candidates streamed
      **without** a confidence field and labelled as provisional in the schema.
- [ ] Gated volume tightening + `INDEX_VOLUME_TIGHTENED` diagnostic naming the
      trigger and the new limit. Test the SRM 660c isospectral case explicitly: the
      tetragonal rival must not be able to truncate the cubic search.
- [ ] `SEARCH_PRESETS` / `SEARCH_PRESET_INFO` in bijection (mirroring
      `PLAN_PRESETS`/`PLAN_INFO` and its meta-test), each carrying worst case **and**
      the measured typical range; `capabilities()` gains a `search_presets` arm
      quoted from the live registry.
- [ ] `quick` becomes the default; `IndexingResult` records which preset ran;
      `INDEX_SINGLE_ENGINE` for explicit one-engine runs.
- [ ] **The re-measure**: every acceptance row, `validation_matrix.py`,
      `docs/VALIDATION.md`, and the scoreboard in all three copies — with its
      arithmetic fixed and brucite/magnetite either promoted to rows or explicitly
      marked as prose-only.

## Acceptance

A shortlist arrives materially sooner on the high-symmetry datasets, nothing
regresses on the low-symmetry ones, the truncation is always visible, and the
scoreboard is re-measured rather than restated.

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py tests/test_indexing_consensus.py \
    tests/test_capabilities.py tests/test_run_control.py -n auto
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Boultif & Louër (2004), *J. Appl. Cryst.* **37**, 724 — §4.1 the volume-tightening
  strategy and per-system exploration. `/Users/yue/zotero-linker/derived/I2VA3ZAB/`
- Coelho (2003), *J. Appl. Cryst.* **36**, 86 — Tables 3 and 5, the per-system cost
  gradient. `/Users/yue/zotero-linker/derived/5RI7CB42/`
- Le Bail (2004), *Powder Diffr.* **19**, 249 — §IV, on-screen progress and
  save-on-cancel. `/Users/yue/zotero-linker/derived/7AEVVGH6/`
- Oishi-Tomiyasu (2014), *J. Appl. Cryst.* **47**, 593 — quick vs regular search as
  a user-facing mode. `/Users/yue/zotero-linker/derived/NWFJ8YEB/`

## Handover log

- **2026-08-04** — created by splitting WP-1037, whose first draft was twelve
  commits across ~18 files and carried a full acceptance re-measure — not one
  session. Everything that changes an answer lives here; WP-1037 keeps only what
  changes none. The volume-tightening danger and the streaming-rank problem were
  found by reviewing that draft against `consensus.py` and the SRM 660c row, not by
  measurement.
