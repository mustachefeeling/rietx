# WP-1939 — an ahead-of-time kernel spike: Rust, C or Cython against numba

Milestone: unscheduled · Status: ✅ 2026-10-10 — spike done, verdict Rust, decision taken the same day; WP-1940 carries the build, the review's findings and the two platforms still owed
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

## Spike, measured 2026-10-10

`examples/aot_spike/` holds the five model kernels twice, as a Rust crate
(`rust/`) and a Cython module (`cython/`). Each exposes the numba names and
signatures, so `compiled._KERNELS` holds one in place of the other and the
package cannot tell. Cython is built three ways: with `-ffp-contract=off`,
with clang's default, and against the Limited API (3.11+). A plain-C build
would compile the same loops with the same compiler and differ only in glue,
so it is not built separately.

`bench_aot_kernels.py` measures three things. It shadows every kernel call
of a real fit and compares each candidate's output with numba's, bit for bit.
It times whole fits with the arms interleaved. And it times startup in fresh
processes. All numbers are from the `[dev]` venv, darwin/arm64, python 3.12.10,
numpy 2.5.3, numba 0.68.0, with the machine idle unless a row says otherwise.

**Agreement is exact for Rust, and for Cython only with the flag.** Every
kernel call of the trigger fit (23 303 calls) and of cpd-1a (8 247):

| candidate | calls differing from numba | final θ vs numba, trigger | cpd-1a |
|---|---|---|---|
| Rust | 0 | bit-identical | bit-identical |
| Cython, `-ffp-contract=off` | 0 | bit-identical | bit-identical |
| Cython, Limited API, `-ffp-contract=off` | 0 (trigger) | not run | not run |
| Cython, clang default | every kernel: all 11 270 scatters and 6 449 FCJ Ω, 1 131 of 1 148 symmetric Ω, and the bases | 4.8e-2 esd | 5.7e-4 esd |
| numpy (the fallback) | — | 5.3e-2 esd | bit-identical |

Clang's default fuses multiply-adds within a statement. That moves the
trigger fit as far from numba as the numpy fallback is. Nothing raises, and
the fit is 1.16× faster for it.

**Speed does not separate them.** Serial kernel time inside one fit, summed
over every call, as a ratio to numba (higher is faster):

| kernel | trigger calls | Rust | Cython | cpd-1a calls | Rust | Cython |
|---|---|---|---|---|---|---|
| `accum` | 11 270 | 1.71× | 1.68× | 6 684 | 1.52× | 1.41× |
| `omega_sym` | 1 148 | 1.03× | 1.03× | 951 | 1.10× | 1.10× |
| `omega_fcj` | 6 449 | 1.12× | 1.20× | — | | |
| `bases_sym` | 700 | 1.29× | 1.22× | 612 | 1.30× | 1.31× |
| `bases_fcj` | 3 736 | 1.02× | 1.00× | — | | |
| all | | 1.09× | 1.10× | | 1.31× | 1.28× |

End to end on the default 8 threads, 5 interleaved repeats (wall s, min–max
and median):

| arm | trigger | ×numba | cpd-1a | ×numba |
|---|---|---|---|---|
| numpy | 11.61–12.79, 11.83 | 0.53× | 3.25–4.66, 3.58 | 0.50× |
| numba | 5.99–6.51, 6.24 | 1.00× | 1.65–2.22, 1.78 | 1.00× |
| Rust | 5.95–6.38, 6.15 | 1.01× | 1.60–2.31, 1.73 | 1.03× |
| Cython, contract off | 5.88–7.66, 6.03 | 1.04× | 1.58–1.96, 1.64 | 1.08× |

The ranges overlap. All three compile the same loops through LLVM or clang at
`-O3`, and the fit outside the kernels is unchanged.

*Corrected after the fact (WP-1940, 2026-10-10):* no call in either fit
reached the 512-row pool threshold (largest 494 rows), so these are serial
kernel times on every arm, and kernel time is 43 % of trigger and 7 % of
cpd-1a. The cpd-1a ratios measure nothing about the kernels.

**Startup and install weight are where the difference is.**

| | numba | Rust | Cython |
|---|---|---|---|
| fresh process, import + ready (s) | 0.98–1.55 with a warm cache, 1.59–1.76 cold, against 0.89–1.15 with the tier off | import 0.049–0.052 against 0.049–0.087 for numpy alone | 0.048–0.053 |
| on disk | 143 MB (numba 17, llvmlite 126) | 227 KB wheel | 239 KB `.so` |
| wheels to cover 3.11–3.14 on one platform | — | 1 (abi3) | 4, or 1 under the Limited API |
| numpy ceiling | `<2.6` | none: rust-numpy loads numpy's C API at run time | none: memoryviews use the buffer protocol |

Per call with one element and twelve arguments, idle: numba 0.43 µs, Rust
0.52, Cython 0.90. Under load the Limited API build ran 1.1–1.9× slower per
call than ordinary Cython, in three runs.

**Two traps in the Rust port, both measured, both now in `lib.rs`'s
docstring.**

1. rust-numpy's borrow tracker refuses a second writable borrow of a live
   array. `compiled._spread` calls one kernel from several threads on one
   output array with disjoint rows, so outputs go through raw pointers.
2. A loop written as a closure over captured slices ran the scatter at 0.59×
   numba. Rust has no type-based alias analysis, so LLVM could not prove that
   a store through the output pointer leaves the captured slice pointers
   alone, and it reloaded them on every iteration. As a free function taking
   slices by argument, which carry `noalias`, the same loop runs at 1.52×.
   Unchecked indexing changed nothing.

**Linux agrees too, and gcc fuses wherever the instruction exists.** A
temporary workflow (run 38033895299, deleted after it reported) ran the same
agreement pass on GitHub's runners, gcc 13.3.0, glibc 2.39:

| runner | Rust | Cython, contract off | Cython, Limited API | Cython, gcc default | serial ×numba, trigger: Rust · Cython |
|---|---|---|---|---|---|
| ubuntu x86_64 | 0 differing | 0 | 0 | 0 | 0.93× · 1.00× |
| ubuntu aarch64 | 0 | 0 | 0 | every kernel, as on darwin | 1.21× · 1.03× |

So on glibc numba's `exp` and Rust's are the same function, and WP-1115's
3e-17 is between numba and numpy alone. gcc's default contraction is silent
on x86-64 because the baseline has no FMA instruction. It fires on aarch64,
where the instruction is in the base set.

Rust loses on x86_64's two FCJ kernels (0.97× and 0.85×). *Hypothesis, not
measured:* numba compiles for the host CPU, AVX2 on that runner, while a wheel
targets baseline x86-64. aarch64's baseline already has NEON and shows no loss.

**The packaging, priced.** maturin-action built the abi3 wheel on five
platforms in one run. Each job took 36–79 s of wall clock, and each wheel is
142–245 KB:

| target | job wall | wheel |
|---|---|---|
| manylinux x86_64 | 72 s | 244 KB |
| manylinux aarch64 | 63 s | 245 KB |
| macOS arm64 | 36 s | 231 KB |
| macOS x86_64 (cross-built on arm64) | 40 s | 239 KB |
| Windows x64 | 79 s | 142 KB |

## Verdict — 2026-10-10

**Rust, if anything replaces numba.** Speed does not separate the three
languages: on darwin/arm64 every candidate lands at 1.01–1.08× numba end to
end. Three things do, and Rust wins each one.

1. *Bit agreement holds by the language's rules.* rustc never contracts
   `a*b+c`, so the kernels agree with numba on all three platforms measured,
   with no flag to remember. C and Cython need `-ffp-contract=off` in every
   build configuration. Without it, every scatter differed on darwin/arm64
   and on Linux aarch64, and on the Mac the trigger fit moved 4.8e-2 esd.
   Nothing raised.
2. *abi3 is mature.* One wheel per platform covers 3.11–3.14. polars ships
   exactly this shape, rust-numpy included. Cython's Limited API also built
   and agreed here. Its documentation still calls it close to
   feature-complete, and it does not cover abi3t yet. (Its per-call figure
   was measured under load and carries no weight here; 1940's review.)
3. *The precedent matches rietx's shape.* A hatchling front package can pin a
   separately built Rust distribution, as polars pins polars-runtime-32.
   PyO3 is already in every rietx install through pydantic-core.

**Whether to replace numba at all is a packaging decision, and it is the
user's.** The gain is the 143 MB, the `numpy<2.6` ceiling, 0.1–0.6 s of
per-process warm-up, and the cache-directory and warm-thread machinery in
`compiled.py`. WP-1521's flag question would also go, because nothing is
built at run time: the extension imports or it does not. The costs:

- A second distribution, `rietx-kernels`, with its own release workflow: five
  wheel jobs, 36–79 s each in one run.
- A Rust toolchain for anyone who edits a kernel.
- 956 more lines to port: the indexing traversal (514) and the figure
  rasteriser (442). Neither was spiked.
- x86_64 may give back a few per cent unless the wheel targets
  x86-64-v3 behind a runtime check.

Three design points for a successor:

- **Publish no sdist, and gate the dependency on platform markers.** A
  platform without a wheel then installs without the kernels and runs the
  numpy path, which `compiled.py` already declines to. That is strictly better
  than today, where a platform numba has no wheel for has to build llvmlite.
  jaxlib also ships no sdist.
- **Pin by kernel interface, never by release.** rietx cuts a release every
  week, and the kernels change rarely. An exact pin, the way polars and
  pydantic do it, would force a kernel release every week. A
  `KERNEL_ABI` integer checked at import, declining on a mismatch, lets the
  two release at their own pace.
- **Keep `_spread` and the Python pool.** Every candidate threaded through it
  unchanged, so neither rayon nor OpenMP needs to enter the build.

## Non-goals

Porting the indexing or figure kernels. Changing the packaging. Both wait on
this WP's verdict.

## Tasks

- [x] Precedent: which projects ship compiled kernels beside a pure-python
      package, with which language and build tool, and what it cost them
      (§ Precedent)
- [x] Spike: the five model kernels in Rust and in Cython (three builds),
      against numba and numpy, inside real trigger and cpd-1a fits
      (`examples/aot_spike/`, § Spike)
- [x] Price the packaging: wheel matrix, CI time, sdist without a toolchain
      (§ Spike, the Linux and packaging tables; § Verdict, the design points)
- [x] Verdict, written here (§ Verdict)
- [x] Tests: none. No package code changed; the spike's own check is the
      agreement pass, which compares every kernel call bit for bit
- [x] Skill: none. An agent driving rietx never sees which compiler built a
      kernel, and nothing it calls changed

## Acceptance

Each candidate needs its toolchain: `rustup` (minimal profile) and
`maturin` for Rust, a C compiler and `cython` for Cython.

```sh
uv pip install --python .venv/bin/python maturin cython setuptools
(cd examples/aot_spike/rust && ../../../.venv/bin/maturin build --release -i ../../../.venv/bin/python)
uv pip install --python .venv/bin/python examples/aot_spike/rust/target/wheels/*.whl
(cd examples/aot_spike/cython && RIETX_SPIKE_CONTRACT=off ../../../.venv/bin/python setup.py -q build_ext --inplace \
  && RIETX_SPIKE_CONTRACT=off RIETX_SPIKE_ABI3=1 ../../../.venv/bin/python setup.py -q build_ext --inplace \
  && ../../../.venv/bin/python setup.py -q build_ext --inplace)
.venv/bin/python examples/aot_spike/bench_aot_kernels.py --cases trigger,cpd-1a --repeats 5
.venv/bin/python -m ruff check src tests examples
```

The bench prints § Spike's agreement, serial, end-to-end and startup tables.
The per-call, size, Linux and packaging figures came from one-off runs.
The bench's agreement pass is the go/no-go
criterion: zero differing calls for every candidate built with contraction
off, on every platform it runs on.

## References

- WP-1115 § Reducing the JIT cost (the AOT option, priced) and § The
  decision (numba as a required dependency).
- polars: `crates/polars-python/Cargo.toml` (`abi3-py310` beside the `numpy`
  crate), github.com/pola-rs/polars; PyPI JSON for polars 2.0.0 and
  polars-runtime-32 2.0.0.
- pydantic-core `pyproject.toml` (maturin), github.com/pydantic/pydantic-core.
- jax versioning, docs.jax.dev/en/latest/jep/9419-jax-versioning.html.
- qiskit `pyproject.toml` (setuptools-rust), github.com/Qiskit/qiskit.
- PyO3 CHANGELOG (`detach` in 0.26, free-threading opt-out in 0.28, abi3t in
  0.29); rust-numpy CHANGELOG and issue #555.
- Rust `f64::mul_add` and `f64::exp` documentation, doc.rust-lang.org; RFC
  2686 (closed unmerged), github.com/rust-lang/rfcs/pull/2686.
- Clang Users Manual, `-ffp-contract`; GCC Optimize Options, `-ffp-contract`;
  MSVC `/fp` reference.
- Cython Limited API guide, cython.readthedocs.io/en/latest/src/userguide/limited_api.html.
- numba installation table (numpy 2.0 to <2.6), numba.readthedocs.io.
- maturin distribution and project-layout docs, www.maturin.rs.

## Handover log

### 2026-10-10 (2nd session) — reviewed, decided, closed into 1940

The go/no-go is answered: numba goes, Rust replaces it, for the install
rather than the speed, and WP-1940 is the build. The review found the
verdict sound on language and thin on packaging shape, and a measurement of
the two benchmark fits found that the thread pool never engaged in either,
so the largest gain available is a Python constant and not a language.

*Done.*

- A critical review of the spike, at code, measurement and precedent level.
  Its findings are restated in 1940 § Context (the mailbox rule: a
  successor cannot read this file). Two corrections made here: the end-to-end
  table's threading note, and the Limited-API per-call figure withdrawn from
  the verdict, since the handover below had already disowned its seconds.
- The maintainer's three decisions (Rust; bit identity relaxed for the
  exponential only; optimise during the migration) recorded in 1940
  § Decisions.

*Measured.* In 1940: kernel share of wall (43 % trigger, 7 % cpd-1a), the
pool threshold never met (largest call 494 rows against 512), FCJ time by
call size, the pool's 30 µs dispatch, and the exponential at 2 ns of the
2.6 ns per element.

*Still owed, carried by 1940:* the agreement pass on Windows and macOS
x86_64; branch counters in the pass; the three code points on `lib.rs`.

*Next.* 1940, task 1.

### 2026-10-10 — filed, spiked, and the verdict is Rust

If numba is replaced, the replacement should be Rust, and it would be for
packaging, never for speed. All three ahead-of-time candidates ran the five
model kernels inside real fits at 1.01–1.08× numba, and Rust and Cython
agreed with numba on every kernel call on macOS and on both Linux
architectures. What separates them is that Rust keeps that agreement by the
language's rules, while C and Cython keep it only behind a compiler flag. One
build without the flag moved a fit by 4.8e-2 esd with nothing raised.
Replacing numba would drop 143 MB, the `numpy<2.6` ceiling and up to 0.6 s of
warm-up per process. It would cost a second distribution and a Rust toolchain
for kernel edits. That trade is the user's to make.

*Done.*

- Filed this WP. No open WP owned ahead-of-time kernels: 1115 shipped and
  closed, 1122 is the peaks buffer, 1508 the indexing traversal, 1521 the
  capability flag.
- § Precedent, from one research agent's web reading. Its wheel counts and
  pins were re-read here from PyPI.
- `examples/aot_spike/`: the Rust crate, the Cython module, and
  `bench_aot_kernels.py`.
- A temporary workflow (`spike-aot.yml`, run 38033895299) for the Linux
  agreement and the wheel matrix. It was deleted in the next commit.
- § Spike and § Verdict. WP-1521's `### Inherited` notes that the model-tier
  half of its question goes away with a wheel.

*Measured.* Every figure is in § Spike, with venv and platform: `[dev]` plus
maturin, cython and setuptools, darwin/arm64, python 3.12.10. The Linux rows
are GitHub's ubuntu x86_64 and aarch64 runners.

- The fast and full selections were not run. Nothing under `src/` or
  `tests/` changed, and no test was added.
- The machine was under a load of 38–100 from another session from about
  08:13. The Limited-API per-call figure and the second trigger agreement pass
  come from that window. Their bits are good and their seconds are not.

*Review.* `/code-review high --fix` made ten findings and fixed nine of them
in three commits:

- the bench counted per plane, its ulp distance could wrap, and it compared
  only the last repeat;
- Rust's outputs accepted a read-only or misshapen plane;
- the ignore rules were repo-wide;
- a single wall-clock figure appeared in the text.

It left the darwin default-contraction row to me. That row under-reported the
kernels it moved and is corrected.

*Gotchas.*

- rust-numpy refuses two live writable borrows of one array, and `_spread`
  makes exactly that call pattern.
- A Rust loop written as a closure over captured slices runs at 0.59×. As a
  free function it runs at 1.52× (§ Spike, the two traps).
- `maturin` needs `[tool.maturin] module-name` when the distribution name has
  a hyphen.
- The Rust toolchain is rustup's minimal profile in `~/.cargo`, off PATH.
- This machine has no container runtime, so a Linux question goes to a
  branch workflow.

*Next.* The user decides whether to replace numba. If yes, file the build WP
with § Verdict's three design points as its Context:

1. Port the model kernels into a `rietx-kernels` distribution, with the
   agreement pass as its test, run on every wheel platform in CI.
2. Port the indexing traversal (514 lines) and the figure rasteriser (442),
   each against its own equivalence test.
3. Drop numba from the dependencies.

Before step 1, measure whether an x86-64-v3 target recovers the 0.85–0.97×
on Linux x86_64's FCJ kernels. If no, close this WP 🛑 with the verdict
standing for whenever numpy 2.6 forces the question.
