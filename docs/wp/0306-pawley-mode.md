# WP-0306 — Pawley mode

Milestone: v0.3 · Status: ⬜ not started
Depends on: —

## Goal

A third refinement mode alongside `rietveld` and `lebail`: per-hkl intensities
refined **as parameters** (Pawley 1981), with the near-singular normal
equations handled explicitly and the results stored in the history container
already reserved for them.

## Context

The seam exists. `ReflectionState` in
[`schemas/history.py:117`](../../src/pxrdref/schemas/history.py#L117) was
built with `kind: Literal["lebail_extracted", "pawley_refined"]`,
`stderr: list[float] | None` ("Pawley has esds; Le Bail does not") and
`varied: bool` — its docstring states outright that this exists so Pawley mode
never has to push one dot-path per reflection into
`RefinementState.free_paths`. **Honour that**: per-hkl intensities go in the
reflection container, not into the named dot-path table in
[`params/vector.py`](../../src/pxrdref/params/vector.py). The mode seam is
`IntensityModel` (`rietveld`/`lebail`, see
[`model/forward.py`](../../src/pxrdref/model/forward.py) and
`CompiledModel.lebail_update`).

The hard part is conditioning, not bookkeeping. Overlapping reflections make
the intensity block of JᵀJ near-singular — at exact overlap it *is* singular,
and the split between the overlapping intensities is arbitrary. Options in
rough order of preference: soft equality/smoothness restraints on strongly
overlapped groups, an explicit rank-revealing solve with the null-space
directions reported, or a documented pinv fallback. Whatever is chosen, the
package rule applies: **report the ambiguity, never a confident wrong
singleton** (design record, "Outputs & fit assessment"). Overlapped groups
whose split is unresolved must come back flagged, with esds that reflect it.

The intensity block is exactly linear in the parameters, so its Jacobian
columns are analytic and cheap (same argument as the Chebyshev background
coefficients). Take the exact columns; do not let this block hit FD.

Le Bail and Pawley must remain distinguishable in stored state: a node
restored from `kind="lebail_extracted"` reseeds the fixed-point loop, while
`kind="pawley_refined"` restores refined values with their esds.

## Non-goals

- Indexing / space-group determination from Pawley output (v2 territory).
- Structure solution. Pawley here serves cell + profile extraction and
  whole-pattern fitting, same role as Le Bail.

## Tasks

- [ ] `mode="pawley"` through `Refinement.fit` / `refine()` and the
      `IntensityModel` seam; per-hkl intensities held in the compiled model,
      serialized via `ReflectionState(kind="pawley_refined", stderr=..., varied=True)`
- [ ] Analytic Jacobian columns for the intensity block (linear ⇒ exact)
- [ ] Near-singular handling: overlap grouping + restraints and/or
      rank-revealing solve; unresolved splits reported as such with honest esds
- [ ] History round-trip: checkout/replay of a Pawley node restores refined
      intensities *and* esds; Le Bail nodes keep reseeding behaviour
- [ ] Tests: synthetic pattern with a deliberately overlapped pair —
      the sum is recovered accurately while the split is flagged unresolved;
      Pawley and Le Bail agree on cell within esds on a clean pattern
- [ ] obs/calc/diff PNGs to `tests/output/` for every Pawley test refinement

## Acceptance

On a clean synthetic pattern, Pawley and Le Bail recover the same cell within
esds and comparable Rwp; on an overlapped pair the summed intensity is right
and the individual split is reported unresolved rather than confidently split.

```sh
.venv/bin/python -m pytest tests/test_pawley.py -q
```

## References

- Pawley (1981) J. Appl. Cryst. 14, 357.
- Le Bail, Duroy & Fourquet (1988) Mater. Res. Bull. 23, 447 — the contrast.

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
