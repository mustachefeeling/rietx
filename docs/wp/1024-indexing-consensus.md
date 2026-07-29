# WP-1024 — Consensus, `index_pattern`, Le Bail validation, agent & CLI surface

Milestone: v1.0 · Status: ⬜ not started
Depends on: 1021, 1022, 1023

## Goal

`index_pattern(...) -> IndexingResult` — the public entry point. It runs the
engines, deduplicates their candidates as reduced cells, enumerates geometrical
ambiguities, validates the survivors by Le Bail fit, and gates confidence on
**agreement**. Its API cannot express a confident wrong singleton.

## Context

- **The founding rule, enforced by the type.** `IndexingResult` has **no**
  `.cell`, `.best` or `.solution` attribute. `candidates` is always a list.
  The only singleton accessor is

  ```python
  def best_or_none(self) -> CellCandidate | None:
      """The single candidate, or None.  Returns a cell only when exactly one
      candidate has confidence == "high" and no ambiguity partners."""
  ```

  Same species of guard as `Geometry.mu_r` being a plain `float` so the type
  forbids refining it: the shape of the API, not a caller's discipline, is what
  holds.
- **The confidence gate:**

  ```
  high   ← found_by == all engines run  AND no ambiguity partners
           AND not fom_panel_disagrees  AND lebail is not None
           AND lebail.predicted_but_absent == 0
           AND indexed_fraction ≥ min_indexed_fraction
  medium ← ≥2 engines, or all with one caveat
  low    ← 1 engine, or any refuting caveat
  ```

  Agreement between engines sharing only the tolerance model and the Q form is
  a genuine independent-opinion signal — the device `direction="both"` uses in
  `sequential.py` and `tests/test_cross_backend.py` uses per Jacobian column.
- **Why Le Bail validation is mandatory, not an option.** The FoM panel is
  computed on ≤20 lines and is structurally blind to three things the whole
  pattern sees:
  1. lines beyond the panel — a cell can index the first 20 and fail from 21;
  2. **reflections predicted where there is no intensity** — the classic
     doubled/oversized-cell false positive. M₂₀ cannot see it (its `N_poss`
     denominator penalises it only weakly, which is Oishi-Tomiyasu's 2013
     critique). Layer 0's `unmatched_calc` strong-negative-residual detector
     (`report/layer0.py:104-109`) sees it directly, and `predicted_but_absent`
     is that count;
  3. impurity content — `unmatched_obs` at 8σ is the existing detector, and
     `report/layer2.layer0_actions` already emits `add_impurity_phase` with
     `alternatives=["reindex_or_recheck_cell"]`. **That pre-declared enum
     member is the seam this whole milestone closes.**

  Both source papers make whole-pattern validation their closing
  recommendation. With `data=None` every candidate caps at `medium` and
  `INDEX_NOT_VALIDATED` fires — the *result* abstains rather than one field
  being quietly downgraded.
- **`structure_from_candidate` carries two footguns; document both loudly.**
  `Phase._nonempty` raises on an empty atom list, so a Le Bail-only phase needs
  a dummy atom — which contributes nothing because `_run_stage` force-fixes
  `.atoms.`, `.scale` and `.source.lines.` in lebail/pawley mode
  (`refine.py:369-380`). And `space_group=None` must default to the
  **highest-symmetry group of the lattice with no extra absences** (`Pm-3m`,
  `P4/mmm`, `P6/mmm`, `Pmmm`, `P2/m`, `P-1`, plus centring), so validation
  tests the **lattice** — an absence-carrying group would hide exactly the
  reflections whose absence is not yet established.
- **Restricted searches must not read as verdicts.** Measured (tag
  `guillemot-study`, `audit_tools.py` check C — see References): a
  two-parameter engine scores 47-60 % on single-phase orthorhombic/monoclinic
  patterns, 82-100 % on genuinely tetragonal/hexagonal ones, and 69 % on a real
  mixture — **the bands overlap, and a "at least two phases" claim built on
  that ambiguity was withdrawn**. So `IndexingResult` carries
  `systems_searched` beside `search_complete`, and failure is reported as
  *"no cell found in the systems searched"*, never as *"this pattern is
  multiphase"*. `INDEX_SYSTEMS_NOT_COVERED` says which systems were not tried.
- **Lab cells carry a systematic no esd reports.** Measured (same commit, check
  A): sweeping `Geometry.goniometer_radius_mm` over 180-320 mm moves Rwp by
  0.029 points (the data cannot identify R), specimen displacement absorbs it
  4.6×, and **≈ ±85 ppm lands on the cell** — larger than the fit's own 1 σ.
  That study's own ROADMAP section records it as a candidate gap ("a lab cell
  quoted tighter than that with no radius supplied deserves a diagnostic");
  indexing is where it bites, because indexing *produces* a cell from lab data
  with nothing to compare against. `INDEX_CELL_SYSTEMATIC_UNQUANTIFIED` fires
  on Bragg-Brentano data when no radius was supplied.
- **`pxrdref compare` gets no new row, deliberately.** CLAUDE.md requires one
  whenever a new *correction* lands; indexing is not a correction and produces
  no alternative fit of the same model, so a variant row would be a fake
  comparison. Record that reasoning here so a future session does not add a
  meaningless row to satisfy the rule.
- **No `ActionKind` change and therefore no `THRESHOLDS_VERSION` bump.**
  `reindex_or_recheck_cell` already exists in `report/schemas.py`'s closed
  enum; only its rationale/suggestion text changes, to name the new API.

### Inherited

From **WP-1021/1022/1023**: each engine registers itself; `engines_run`,
`engine_stats` and `search_complete` come from the registry, and
`agent.tool_definition()` must quote the **live** registry so a new engine
cannot be absent from the exported schema (the WP-0602 meta-test pattern).

From **WP-1023**: if its spike returned **no-go**, engine C is dropped from the
confidence gate and `high` requires the two remaining engines — make that
change here, in the same commit, rather than leaving a gate that silently
counts a re-scorer as an independent opinion.

From **WP-1020**: `reduce.py`'s χ² cell-equality is the dedup primitive;
`ambiguity.py` supplies partners; the FoM panel supplies the Borda ranking.

## Non-goals

- No space-group determination (WP-1025) — validation uses the absence-free
  lattice group.
- No GUI (WP-1027).
- No multi-phase indexing (index the residual after subtracting a solved
  phase) — a fence, recorded not attempted.

## Tasks

- [ ] `indexing/consensus.py`: reduce → two-opinion Bravais → χ² dedup and
      `found_by` merge → ambiguity partners → Borda rank → validation →
      the confidence gate; `best_or_none`.
- [ ] `indexing/workflow.py`: `structure_from_candidate` (both footguns in the
      docstring), `validate_by_lebail` returning `LeBailValidation` with
      `predicted_but_absent` from Layer 0's `unmatched_calc`.
- [ ] `index_pattern` + `IndexingResult` in `schemas/indexing.py`
      (`systems_searched`, `search_complete`, `engine_stats`, seed in
      `Provenance`); `pxrdref/__init__.py` exports.
- [ ] All `INDEX_*` diagnostics not already owned by 1019, in particular
      `INDEX_ABSTAINED`, `INDEX_MULTIPLE_SOLUTIONS`,
      `INDEX_GEOMETRIC_AMBIGUITY`, `INDEX_SYSTEMS_NOT_COVERED`,
      `INDEX_NOT_VALIDATED`, `INDEX_IMPURITY_LINES`,
      `INDEX_VOLUME_UNPHYSICAL`, `INDEX_CELL_SYSTEMATIC_UNQUANTIFIED`.
- [ ] `agent.py`: `IndexRequest` in the discriminated task union
      (`_TASK_TAGS`), `tool_definition()` quoting the live engine registry, and
      the meta-test that fails when a registered engine is missing from the
      schema. `cli.py`: `pxrdref index`.
- [ ] `docs/AGENT_PROTOCOL.md`: the closed-loop workflow section
      (`pick_peaks → index_pattern → best_or_none → … → refine`), plus §6
      abstention and §7 code rows; `report/layer2.py` suggestion text points at
      the new API (**no enum change, no version bump** — say so in the commit).
- [ ] `tests/test_indexing.py`: the confidence gate under each caveat; the
      **API-shape test** (no unconditional singleton accessor; `best_or_none()`
      returns `None` for each gate failure); the **restricted-search test**
      (synthetic orthorhombic list with `systems=("cubic","tetragonal",
      "hexagonal")` ⇒ `INDEX_SYSTEMS_NOT_COVERED`, `systems_searched` excludes
      orthorhombic, nothing asserts multiphase; unrestricted rerun finds it).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing.py tests/test_agent_surface.py -q
.venv/bin/python -m pytest tests/test_fitreport_layers.py -q
.venv/bin/python -m ruff check src tests examples
```

Criterion: `best_or_none()` returns `None` under every gate failure and a cell
only when the gate is fully satisfied; the agent schema quotes every registered
engine; and the restricted-search test proves a limited search cannot be read
as a multiphase verdict.

## References

- Bergmann *et al.* (2004) *Z. Kristallogr.* **219**, 783-790 and Altomare
  *et al.* (2019) IT Vol. H ch. 3.4 — both close on whole-profile validation.
- Oishi-Tomiyasu, R. (2013). *J. Appl. Cryst.* **46**, 1277-1282 — why M₂₀
  cannot see predicted-but-absent reflections.
- Prior art, at the tag `guillemot-study` — **not merged into `main`, and it
  does not need to be**; every number above is restated here, so this is
  corroboration:

  ```sh
  git show guillemot-study:studies/guillemot/out/audit_full.txt   # §A, §C
  git show guillemot-study:docs/ROADMAP.md                        # the gap note
  ```

## Handover log

- **2026-07-29** — created from the indexing plan.
