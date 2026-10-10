# WP-1939 — an ahead-of-time kernel spike: Rust, C or Cython against numba

Milestone: unscheduled · Status: 🔄 2026-10-10 — claimed by @yue-here
Track: Candidates — named on a use case, not yet on a measurement
Depends on: —

## Goal

A go/no-go on replacing the numba tier with kernels compiled into a wheel.
The language is chosen from precedent and measured on the model kernels
against numba, for speed, bit agreement with numpy, and packaging cost.

## Context

- WP-1115 shipped numba as a required dependency on 2026-08-22. It accepted
  two costs: llvmlite's install weight and numba's `numpy<2.6` ceiling. Its
  § Reducing the JIT cost names ahead-of-time compilation as the one shape
  that removes both, and it priced Cython or C there.
- Three modules use numba today: `model/_kernels_numba.py` (254 lines, five
  kernels), `indexing/_kernels_numba.py` (514), and
  `viz/figure3d/_kernels_numba.py` (442). Dropping numba means all three.
- The kernels' contract is `model/compiled.py`'s docstring and the root
  CLAUDE.md rule on the compiled tier: every expression is a transcription of
  a numpy line, association for association.

## Non-goals

Porting the indexing or figure kernels. Changing the packaging. Both wait on
this WP's verdict.

## Tasks

- [ ] Precedent: which projects ship compiled kernels beside a pure-python
      package, with which language and build tool, and what it cost them
- [ ] Spike: the five model kernels in the chosen language(s), against numba
      and numpy, on `examples/bench_compiled_kernel.py`'s cases
- [ ] Price the packaging: wheel matrix, CI time, sdist without a toolchain
- [ ] Verdict, written here
- [ ] Skill: none expected — an agent driving rietx never sees which compiler
      built a kernel

## Acceptance

```sh
.venv/bin/python examples/bench_compiled_kernel.py
.venv/bin/python -m ruff check src tests examples
```

## References

## Handover log

- **2026-10-10** — Filed. No open WP owns ahead-of-time kernels: 1115 shipped
  and closed, 1122 is the peaks buffer, 1508 the indexing traversal, 1521 the
  capability flag.
