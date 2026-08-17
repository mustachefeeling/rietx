# WP-1076 — A result row's unwritten fields

Milestone: 1.0.x · Status: ⬜
Depends on: WP-1067 (which found it, and left both names provisional)

## Goal

`RefinedParameter` carries no field whose empty state asserts something the
package never measured. `at_bound` becomes a real answer, sourced from the one
place that already computes it, and its unmeasured state is `None` rather than
`False`. `initial` goes, because the start of a fit has an authority already and
it is not the result.

## Context

`RefinedParameter` (`src/rietx/schemas/results.py:13`) is the row type of
`RefinementResult.parameters`. It declares six fields. The fit populates four:

```python
# src/rietx/refine.py:1822 — the only place these rows are built
for e in table.entries:
    if e.vary or e.tie is not None:
        params.append(RefinedParameter(
            path=e.path, value=e.value, vary=e.vary,
            stderr=stderr_phys.get(e.path)))
```

`initial` and `at_bound` are never written, and **nothing in the package reads
either** (verified 2026-08-17 across `report/`, `viz/`, `agent.py`,
`textdoc.py`, `project.py`, and the GUI; every other `at_bound` in the tree is
either `indexing/peakfit.py`'s per-peak array or `GuardFinding.at_bound`, both
of which work and are unrelated). No test asserts on either field, and no
on-disk fixture carries them.

**The defect is the empty state, not the absence of a writer.** Both fields
serialize, so every consumer of a result sees:

```json
{"path":"phases.0.cell.a","value":10.2512,"stderr":0.0000627,
 "initial":null,"vary":true,"at_bound":false}
```

`initial: null` reads correctly as "absent". `at_bound: false` reads as **an
answer** — "this parameter is not against a bound" — and it is not one. It says
nothing, always, including for a parameter that refined hard onto its bound.
A tool-calling agent reading the envelope cannot tell the difference, and
`docs/AGENT_PROTOCOL.md`'s table tells that agent not to quote a bound-sitting
parameter as a measurement.

That is this repo's own most-quoted rule one rank down: **a quantity that cannot
be measured is absent rather than zero** (WP-1072, McCusker §10, root CLAUDE.md).
`False` is the boolean zero and it is being used as "no information".

**The fact is already computed, once, and correctly.** `strategy/staged.py:688`
tests every free path against its internal bounds with a span-relative tolerance
and appends a `GuardFinding`, which becomes the `BOUND_HIT` diagnostic:

```python
lo, hi = table.bounds()
for k, path in enumerate(free):
    t = outcome.theta[k]
    span = hi[k] - lo[k]
    tol = 1e-8 * (span if np.isfinite(span) else 1.0)
    if (np.isfinite(lo[k]) and t - lo[k] <= tol) or (np.isfinite(hi[k]) and hi[k] - t <= tol):
        report.at_bounds.append(GuardFinding.at_bound(path))
```

So the row's flag must be a **projection of that one computation, never a second
one**. `_build_result` already receives the guard report at three of its four
call sites (`refine.py:1219`, `:1309`, `:1379`); the fourth (`:2485`) does not,
which is exactly why the flag needs a third state rather than a default.

This follows the `evidence`/`trajectory` precedent (root CLAUDE.md): a derived
view rides *beside* the answer, computed once. It is not a second authority for
the bound fact, and `BOUND_HIT` stays the reported diagnostic.

### The design decision, already taken (2026-08-17, user)

Taken with the freeze explicitly set aside: the package has no users yet, so
breaking changes and extra work were declared acceptable and the choice was made
on robustness alone.

- **`at_bound: bool | None = None`**, populated from the guard report. The
  reason for `None` over a required `bool` is that it cannot regress into a lie:
  a future `_build_result` path that forgets to populate it yields "no
  information", which is true, rather than "not at a bound", which may not be.
  Forcing every call site to pass the flag is the weaker fix, because the field
  can be made to lie again by anyone who passes `False` for convenience.
- **`initial` is deleted.** Never written, never read, and its own docstring
  names its replacement: "the start lives one node up in the history tree". One
  authority per fact, and the history tree is it. A caller assembling a result
  by hand can still record a start state; it just does not belong on this row.

### What this costs elsewhere

- `RefinedParameter` is on the **frozen** surface as of WP-1067's chapter,
  except for these two names, which that chapter deliberately left provisional
  so this WP would be free (`docs/manual/using/model.md`, and the 1.0.2 notes
  say why). So neither change is a freeze violation.
- Under `docs/manual/using/compatibility.md`, deleting a field is a **breaking
  event** that moves the schema contract version, and changing what `at_bound`
  answers is a **documented event** even though its shape barely moves. Both
  need release notes; check whether `SCHEMA_VERSION` moves once, for the pair.
- Eight `RefinedParameter(...)` constructions in `tests/` pass neither field, so
  the default keeps them compiling; deleting `initial` breaks nothing there.

## Non-goals

- **No new bound-related diagnostic, and no change to `BOUND_HIT`.** The guard
  is correct and stays the reported channel; this WP only projects it.
- **No second bound computation.** If the flag cannot be sourced from the guard
  report at a given call site, it is `None` there. Recomputing it locally is the
  bug this WP exists to avoid.
- **No audit of other schemas' defaults.** Whether any *other* field's empty
  state asserts a measurement is a real question and a separate one; if this WP
  notices candidates it lists them in its handover rather than fixing them.

## Tasks

- [ ] `at_bound: bool | None = None` on `RefinedParameter`, with the docstring
      saying what each of the three states means and that the source is the
      guard, never a local recomputation.
- [ ] Populate it in `_build_result` from `guard.at_bounds` (one set of paths,
      built once), leaving `None` when no guard was passed. Check all four call
      sites and say in the commit message which ones can supply it.
- [ ] Delete `initial`, and grep for readers before and after rather than
      trusting this file's claim that there are none.
- [ ] Tests: a real fit's rows carry `True`/`False` and not `None`; a fit with a
      parameter driven onto a deliberately tight bound reports `True` on
      **exactly** the paths `BOUND_HIT` names, which is what pins the projection
      to its single source; a hand-built result with no guard reports `None`.
- [ ] `docs/manual/using/model.md` documents both states and the field leaves
      the provisional bucket (regenerate `tests/api_surface_deferred.txt` in the
      same commit); append the promotion and the breaking change to
      `docs/releases/1.0.2.md`, which is still unreleased.
- [ ] `docs/AGENT_PROTOCOL.md`: the `BOUND_HIT` row gains the machine-readable
      form of the same rule, since an agent iterating parameters now has a
      per-row flag rather than a path cross-reference.

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -n auto --dist loadgroup        # full: schemas/results.py is source
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_docs_consistency.py
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m ruff check src tests examples
```

The full suite is not optional here: this WP edits `schemas/results.py` and
`refine.py`, so it can move a measured number, and `--durations` plus the
passed/skipped delta are what show it did not.

## References

- WP-1067's 2026-08-17 (`using/model.md`) handover entry — where this was found,
  and why the draft chapter's description of `at_bound` was wrong twice over
  (the mechanism *and* an unsourced interpretation of the esd).
- Root CLAUDE.md, WP-1072's bullet — "a quantity that cannot be measured is
  absent rather than zero", the rule this WP applies to a boolean.
- `docs/manual/using/compatibility.md` § How a change is classified — a change
  to what an existing value means is never silent.
