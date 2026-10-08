# WP-1928 — the toy_anomalous golden reads a frozen y_obs

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P2 2026-10-08 — a check that fires wrongly on every macOS 26 machine, recorded as a known failure by ten WPs' sessions

## Goal

`tests/test_backend_shim.py`'s `toy_anomalous` golden passes bit-identically on
macOS 26 and 27, because its observed pattern is stored data rather than a
re-simulation.

## Context

Issue #760 (mustachefeeling). The golden was captured on macOS 27 and fails on
macOS 26 arm64. The reporter traced the cause to the **input**:
`_state_toy_anomalous` (`tests/test_backend_shim.py:424`) builds its observed
pattern at run time by evaluating a perturbed copy of the model
(`cell.a + 0.004`, `atoms[1].z + 0.003`). That evaluation goes through libm,
so it moves with the macOS major. Measured on 26.7.1: `y_calc`, the code the
gate guards, is identical (max |Δ| 0). Only `residual` and `jacobian` move,
both of which read `y_obs`.

**Decided 2026-10-08:** freeze the synthetic `y_obs` as data for this state,
in the golden npz or a fixture beside it, and read it back. Bit-identity stays
`array_equal` and tests only the shim path. The Linux policy in the module
docstring is unchanged, since `y_calc` itself differs there. The contributor
opens the PR, capturing on macOS 26.7.1 arm64 and showing the numbers
reproduce on a second run; the maintainer confirms on 27.

Checked against the tree at `5d1f5f67`: `_state_toy_anomalous` is at
`tests/test_backend_shim.py:424` as named. The failure was not re-run here.

### Inherited

## Non-goals

- Re-capturing any other golden, or changing the Linux policy.

## Tasks

- [ ] Freeze `y_obs` for `toy_anomalous`, re-capture its golden, regenerate per `tests/data/README.md`
- [ ] Skill: none, since a test fixture changes nothing an agent driving rietx reads

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_backend_shim.py -n auto --dist loadgroup
```

passes on macOS 26 arm64 and on macOS 27.

## References

- Issue #760; WP-0401 (the backend op shim and its goldens).

## Handover log

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #760).
  Checked against the tree at `5d1f5f67`: the state builder is where the
  issue says; no open WP owns it: ten WPs cite #760 only as a known failure.
  Decided 2026-10-08 by the maintainer: the contributor opens the PR.
