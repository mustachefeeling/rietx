# WP-0304 — QPA: Hill-Howard ZMV mass fractions

Milestone: v0.3 · Status: ⬜ not started
Depends on: —

## Goal

Report quantitative phase-analysis weight fractions from the refined phase
scales via the Hill-Howard/Bish-Howard ZMV relation, with propagated
uncertainties, as a typed result object.

## Context

The relation (Hill & Howard 1987): for phase p with Rietveld scale S_p,

    W_p = S_p·(ZMV)_p / Σ_q S_q·(ZMV)_q

where Z = formula units per cell, M = formula mass, V = cell volume. All three
are already derivable from the refined model: V from
[`crystallography/lattice.py`](../../src/pxrdref/crystallography/lattice.py),
M and Z from the phase's atom list + site multiplicities
([`crystallography/symmetry.py`](../../src/pxrdref/crystallography/symmetry.py))
— **do not ask the user to type Z·M·V by hand**; that is the GUI-era ritual
this package exists to remove. Occupancies enter M (a partially occupied site
weighs less), so compute M from the *refined* occupancies, not the formula
string.

Important scope caveat to document in the API, not hide: these are fractions
of the **crystalline, modelled** content. An unmodelled amorphous fraction or
a missing phase makes them sum to 1 anyway. Internal-standard/amorphous QPA is
fenced to v2; say so in the docstring and in the report field.

Uncertainty propagation: W_p is a ratio of correlated refined scales, so
σ(W_p) must come from the scale block of the covariance matrix (the full
Cov is available in [`optimize/least_squares.py`](../../src/pxrdref/optimize/least_squares.py)),
not from σ(S_p) treated as independent. Carry the Bérar-Lelann inflation
through — the reported esds elsewhere in the package do, and a QPA number with
a differently-conditioned uncertainty would be inconsistent.

Result surface: a typed pydantic object (JSON round-trip, `extra="forbid"`)
hanging off `RefinementResult` in
[`schemas/results.py`](../../src/pxrdref/schemas/results.py) — one row per
phase with W, σ(W), Z, M, V, S. WP-0309 exports it as a table; WP-0305 adds
the Brindley correction as an adjustment to the same object.

## Non-goals

- Brindley microabsorption (WP-0305) — separate, and separately validated.
- Internal-standard / amorphous quantification (v2 fence).
- The round-robin acceptance run (WP-0310).

## Tasks

- [ ] Z, M, V derivation from the refined model (occupancy-weighted M;
      multiplicity-aware Z); unit test against hand-computed values for a
      couple of known structures
- [ ] `QuantitativePhaseAnalysis` result schema + attachment to
      `RefinementResult`; JSON round-trip test
- [ ] Weight fractions from refined scales; σ(W) from the scale block of the
      covariance (correlated ratio propagation), Bérar-Lelann carried through
- [ ] Docstring + field-level statement that fractions are of the modelled
      crystalline content only
- [ ] Two-phase synthetic test with known mixing ratio: recovered fractions
      within propagated σ

## Acceptance

Weight fractions on a synthetic two-phase mixture with a known ratio agree
within the propagated uncertainty; σ(W) demonstrably differs from the naive
independent-scale propagation (assert the correlated path is being used).

```sh
.venv/bin/python -m pytest tests/test_qpa.py -q
```

## References

- Hill & Howard (1987) J. Appl. Cryst. 20, 467 — ZMV scale-factor QPA.
- Bish & Howard (1988) J. Appl. Cryst. 21, 86.
- Madsen et al. (2001) J. Appl. Cryst. 34, 409 — IUCr QPA round robin
  (dataset target for WP-0310).

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
