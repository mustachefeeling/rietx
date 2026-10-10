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

## Precedent

Read 2026-10-10 from PyPI's JSON and each project's own repository. The wheel
counts and pins were re-read here; the rest is the research agent's, with its
sources in § References.

**The split package is the established shape.** A pure-python front package
pins a separately versioned compiled distribution exactly:

| front | compiled core | language, build | pin | wheels |
|---|---|---|---|---|
| polars 2.0.0 | polars-runtime-32 | Rust, maturin, `abi3-py310` + rust-numpy | `==2.0.0` | 8, all abi3, plus sdist |
| pydantic 2.14.0 | pydantic-core 2.50.0 | Rust, maturin | `==2.50.0` | 136, per interpreter, plus sdist |
| jax 0.11.2 | jaxlib | C++ (XLA) | `>=0.11.2,<=0.11.2` | 22, no sdist |
| qiskit | in-tree `_accelerate` | Rust, setuptools-rust under cibuildwheel | — | 7, all abi3, plus sdist |
| scikit-learn | in-tree | Cython, meson-python, OpenMP | — | 42 at 1.9.1, per interpreter |

pydantic-core is already in every rietx install, so a PyO3 extension adds no
new kind of artefact to rietx's dependency tree. The shape also suits
hatchling: maturin documents no hatchling integration, and polars gets round
that by building the runtime as its own distribution.

**What each language costs here.**

- *Rust (PyO3 0.29.3, rust-numpy 0.29.0).*
  - Releasing the GIL is `Python::detach`, renamed from `allow_threads` in
    0.26.
  - abi3 builds one wheel per platform for every interpreter from 3.11.
    polars ships rust-numpy under abi3 in production.
  - Free-threaded builds have been opt-out since PyO3 0.28.
  - rustc never fuses `a*b+c` into an FMA. `mul_add` is the explicit form,
    and RFC 2686, which would have allowed fusion, was closed unmerged.
  - `f64::exp` is documented as platform-dependent. It is the same libm call
    numba makes.
- *Cython 3.3.0.*
  - The Limited API is "close to feature-complete" and no longer labelled
    experimental. Typed memoryviews under it need Python 3.11, which is
    rietx's floor. abi3t is not covered yet.
  - Free-threading is supported from 3.1 behind a directive.
  - Cython emits C, so the C compiler's float flags decide, and nothing in
    Cython, setuptools or meson-python sets them.
- *C.* The same compiler rules as Cython, with hand-written glue for each of
  the 67 arguments the five kernels take.
- *The compiler defaults.*
  - clang (Apple and upstream) defaults to `-ffp-contract=on`, which fuses
    within one statement.
  - GCC defaults to `fast`, which also fuses across statements, except under
    `-std=c11` and similar.
  - MSVC 2022's `/fp:precise` does not fuse.
  - aarch64 has FMA in its base instruction set, so Apple Silicon and Linux
    arm64 fuse by default. x86-64 fuses only under `-mfma` or `-march`.
- *numba 0.68.0.* Still `numpy<2.6` ("2.0 to <2.6" in its own table). It
  ships cp314t wheels. llvmlite 0.50.0 is 40.5 MB per macOS arm64 wheel and
  ~59 MB per manylinux x86_64 wheel.

## Non-goals

Porting the indexing or figure kernels. Changing the packaging. Both wait on
this WP's verdict.

## Tasks

- [x] Precedent: which projects ship compiled kernels beside a pure-python
      package, with which language and build tool, and what it cost them
      (§ Precedent)
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
