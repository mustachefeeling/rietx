# WP-1940 — the kernel tier in a wheel: Rust kernels, threaded on work, with a vector exponential

Milestone: unscheduled · Status: ⬜
Track: Candidates — named on a use case, not yet on a measurement
Depends on: 1939
Priority: P2 2026-10-10 — the decision is taken (Rust, § Decisions) and every agent install pays numba's 143 MB and warm-up until this lands; the first task is a bit-neutral 1.4× that ships on its own

## Goal

`pip install rietx` into a fresh venv or a Colab notebook brings no numba and
no `numpy<2.6` ceiling. A separate `rietx-kernels` distribution, Rust under
PyO3 and built as one abi3 wheel per platform, runs the model kernels. The
thread pool engages on the calls that carry the time, the FCJ kernels use a
vectorised exponential to a stated error bound, and an install where the
kernels do not load says so instead of running the numpy path in silence.

## Context

WP-1939 spiked the five model kernels in Rust and Cython against numba and
returned the verdict Rust. This WP is the build it asked for, plus what a
review of the spike and a measurement of the fits it benchmarked turned up.
Everything below was measured 2026-10-10 on the `[dev]` venv, darwin/arm64,
python 3.12.10, numpy 2.5.3, numba 0.68.0, unless a row says otherwise.

### Decisions, 2026-10-10

Taken by the maintainer on the review of 1939. They are the premises of the
tasks and are not reopened here.

1. **Rust replaces numba in the model tier.** The reason is the install, never
   the speed: rietx is installed by agents into fresh venvs and into Colab,
   each of which pays numba's weight and warm-up every time, and Colab moves
   its numpy under the ceiling.
2. **Bit identity is relaxed for the exponential and for nothing else.** The
   rule was never about truth. It bought review by eye and the same answer
   from the same input whatever was installed. Both survive where the rule is
   free, in sums and differences, and neither is worth the exponential's
   cost. So: **transcendentals to a stated bound, associations as written**
   (§ The relaxed rule).
3. **Optimisations land with the migration.** The goldens re-pin once at the
   migration; bundling the exponential saves a second re-pin. The threading
   fix is bit-neutral and ships first, under numba.

### What 1939 established

- Rust and Cython (with `-ffp-contract=off`) agree with numba on every kernel
  call of the trigger and cpd-1a fits, on darwin/arm64, Linux x86_64 and
  Linux aarch64. Cython under clang's or gcc's default contraction differs on
  every scatter on both arm64 platforms and moved the trigger fit 4.8e-2 esd
  with nothing raised. rustc never contracts.
- Speed does not separate the languages: 1.01–1.08× numba end to end.
- One abi3 wheel per platform, 142–245 KB, 36–79 s of CI each on five
  platforms. numba is 143 MB on disk and 0.1–0.6 s of warm-up per process.
- Two Rust traps, both in `examples/aot_spike/rust/src/lib.rs`'s docstring:
  rust-numpy refuses two live writable borrows of one array, so outputs go
  through raw pointers; a loop written as a closure over captured slices ran
  at 0.59× numba, as a free function at 1.52×.
- Linux x86_64 lost 3–15 % on the two FCJ kernels. *Hypothesis:* numba
  compiles for the host (AVX2 on that runner) and the wheel targets baseline
  x86-64.

### What the review of 1939 added

**Architecture.** The precedents 1939 cites (polars, pydantic, jax) are the
inverse of rietx's shape: their compiled distribution is the product and the
python front is a shell, so they pin exactly. rietx is a large python package
with a 254-line accelerator and a working fallback. The precedent for *that*
shape is jsonschema → rpds-py, a pure-python package depending on a small
PyO3 distribution by the same maintainer, pinned as a floor
(`rpds-py>=0.25.0` on 2026-10-10). Four consequences:

- **Pin by major version equal to the kernel interface number.** The front
  declares `rietx-kernels>=N,<N+1` with N = `KERNEL_ABI`, so pip refuses a
  mismatch before anything imports, and `compiled.py` re-checks the integer
  at import. An exact pin, polars' way, would force a kernel release every
  week.
- **A decline is visible.** 1939's design points describe two silent
  fallbacks (no wheel for the platform; an ABI mismatch), which is WP-1521's
  failure in a new place. A decline warns once per process and
  `capabilities()` says why.
- **Platform markers cannot say "a wheel exists".** They enumerate five
  OS/CPU pairs and miss musllinux, free-threaded builds (abi3 does not load on
  3.13t/3.14t, where numba does ship wheels today) and any future target. The
  three honest shapes are a hard dependency with no markers and no sdist
  (pip fails loudly where no wheel exists), markers, or an optional extra.
  **Open decision, § Decisions owed.**
- **Where the crate lives and how it releases.** polars keeps both
  distributions in one repository; pydantic-core has its own. `RELEASING.md`
  builds from a tag, so one repository needs a second tag namespace
  (`kernels-vN.M`) or a path filter. **Open decision.**

**Measurement.** Windows and macOS x86_64 built wheels and never ran the
agreement pass; the Windows maths library is the one not yet shown shared
between numba and Rust. The agreement pass counts calls and never branches:
`accum` has four `n_terms` arms, Ω two spellings, `bases_fcj` the axial arm
(the trigger plan frees `axial_sl`, so that one ran; which scatter arms ran
is unknown). "rustc never contracts" covers `*` and `+`; the exponential
agreed because both sides called the same libm on three platforms, and
Rust's std could one day ship its own.

**Code, for the port.** `out2` never checks an output plane is distinct from
`x` or from its sibling outputs (aliasing a raw write with a live slice is
undefined behaviour; four pointer compares close it). `pl()` discards the
width of `om`, `dphi` and the axial planes and indexes them with `phi`'s
width, where numba reads each with its own. `rows[r] as usize` wraps on a
negative value in a release build; the slice bounds check keeps the write
inside the plane, so it is a wrong row and never a memory error.

### Where the time goes

Every kernel call timed inside the two spike fits, numba tier:

| fit | wall | kernel time | share | of which FCJ kernels |
|---|---|---|---|---|
| trigger | 6.07 s | 2.63 s | 43 % | 2.41 s |
| cpd-1a | 1.58 s | 0.12 s | 7 % | — (no FCJ) |

| kernel, trigger | calls | seconds | µs/call | rows median | rows max |
|---|---|---|---|---|---|
| `accum` | 11 278 | 0.212 | 18.8 | 224 | 564 |
| `omega_sym` | 1 156 | 0.007 | 5.8 | 13 | 48 |
| `omega_fcj` | 6 524 | 0.989 | 151.6 | 4 | 494 |
| `bases_sym` | 700 | 0.008 | 11.7 | 15 | 48 |
| `bases_fcj` | 3 736 | 1.417 | 379.3 | 4 | 494 |

Python above the kernels in `compiled.*` is 0.05 s of the 6.07. On cpd-1a no
kernel work of any kind can move the fit; its 1.03× in 1939's table is noise
over a 7 % share.

**The thread pool never engaged.** `compiled._THREAD_MIN_ROWS` is 512. The
largest call in either fit had 494 rows (`accum` is never spread). Every one
of the 12 116 trigger calls ran inline, so 1939's "threads = 8" end-to-end
table is serial kernel execution. The 512 was sized for the symmetric
kernels, where a row costs a fraction of a microsecond. An FCJ row costs
3–10 µs, since it carries 8–40 quadrature nodes across its window:

| FCJ calls in trigger | `omega_fcj` | `bases_fcj` |
|---|---|---|
| calls / seconds | 6 524 / 0.995 | 3 736 / 1.420 |
| ns per (point × node) | 2.6 | 6.1 |
| rows ≥ 64: calls, share of time, median µs | 1 156, 90 %, 559 | 700, 91 %, 1 363 |
| rows ≥ 256 | 290, 42 %, 1 539 | 175, 42 %, 3 306 |
| rows ≥ 512 | 0 | 0 |

The pool's dispatch (`_spread` over a no-op, 8 workers, idle) is
29.7–31.3 µs a call.

**The exponential is the floor.** numpy's `np.exp` and the C library's
`exp` (a numba scalar loop) are bit-identical on this platform
(0 of 4 000 000 differ) and cost 1.97 and 2.10 ns per element, against
0.33 ns for a multiply-and-add. Roughly three quarters of `omega_fcj`'s 2.6 ns
per element is the exponential. SLEEF-class vector exponentials run at
0.3–0.5 ns per element.

### The relaxed rule

Replaces the "every expression is a transcription" clause for the kernel
tier, in the root CLAUDE.md, `model/compiled.py`'s docstring and the kernel
sources. The scatter (`accum`) keeps the bit; it has no library call.

1. **Transcendentals to a stated bound, associations as written.** Each
   kernel's docstring names its `exp` implementation and the bound it holds
   (the implementation's documented maximum ulp error), and
   `tests/test_compiled_kernels.py` asserts that bound against the numpy
   builder. Every sum and difference keeps the numpy line's association: the
   scatter adds mixed-sign terms into one array and the FCJ position
   derivative is two whole sums subtracted, and reassociating either loses
   digits through cancellation by an amount the data decides.
2. **One path per process stays** (1115's rule 4). It is what keeps the last
   digits independent of machine speed.
3. **A fit-level guard.** Converged θ on the kernel path against the numpy
   path, in esd units, on the two spike cases. 1939 measured 5.3e-2 on
   trigger today, under bit-identical kernels, because a solver amplifies a
   last-bit difference into where it stops. The guard is a runaway guard at
   several times that, never a tolerance that senses termination
   (tests/CLAUDE.md § Budgets).
4. **Goldens re-pin once per change of kernel arithmetic**, on the
   `GOLDEN_PLATFORM` pin they have. If that becomes frequent, the tier's
   goldens move to a tolerance and bit goldens stay with the numpy path.
5. **The agreement pass stays zero-tolerance outside the exponential**, with
   a separate ulp column for it, so a transcription error stays visible after
   the rule changes.

Under this rule a fused multiply-add is an ulp-class change and Cython's
contraction trap stops being disqualifying; 1939's verdict then rests on
abi3 maturity and the packaging precedent, which still favour Rust.

### Optimisations, ranked by measured gain

1. **Threshold the pool on work, never on rows** (Python, bit-neutral,
   ships first). Rows × nodes × summed window width, or a per-kernel row
   floor. 90 % of 2.4 s split across 8 cores at 30 µs a dispatch leaves
   ~0.6 s; trigger lands near 4.3 s from 6.1, ~1.4×, larger than anything the
   language bought. The gain is Amdahl-bounded: 57 % of trigger is numpy and
   python outside the kernels.
2. **Vectorised exponential in the FCJ kernels** (needs the relaxed rule).
   3–4× on their 2.4 s. With (1), the kernel share of trigger drops to
   ~0.3 s and trigger lands near 3.7 s. A pure-Rust implementation also makes
   the kernel tier give the same bits on every platform; the numpy parts of
   the forward model keep their platform libm, so the fit as a whole does not.
3. **Loop interchange in the FCJ kernels**: node loop outside the window
   loop, so the compiler vectorises across window points. Bit-neutral (each
   output still sums its nodes in order). Pays only with (2).
4. **Dispatch inside Rust** once the pool engages: 30 µs of python dispatch
   is a quarter of a split 1.36 ms call; rayon dispatches in a few µs. A
   dependency and a second pool. Measure after (1).
5. **x86-64-v3 multiversioning** (`multiversion` crate) for Linux x86_64's
   3–15 % FCJ loss. Bit-neutral.
6. **Const generics for `spell` and `has_ax`**: the compiler almost
   certainly unswitches both. Zero expected; check the assembly and stop.

Does not pay: per-call overhead (0.05 s above the kernels in 6 s), unchecked
indexing (1939 measured no change), reciprocal multiplies, reassociating the
node sum.

### The other two numba tiers

Dropping numba from the dependencies waits on `indexing/_kernels_numba.py`
(514 lines, the dichotomy traversal, `dichotomy.py:180` builds it with its
own soft import) and `viz/figure3d/_kernels_numba.py` (442, the rasteriser,
`raster.py` declines on failure). Both allocate arrays inside the kernels,
which in Rust is rust-numpy array creation rather than a slice argument.
Neither was spiked. The interim shape once the model tier ships: numba
becomes an extra that only those two tiers import, and the base install runs
their fallbacks.

### Decisions owed

- Hard dependency without markers (and no sdist), markers, or an optional
  extra. *Recommended:* hard dependency without markers, since a loud
  failure where no wheel exists beats a silent slow path, with musllinux and
  abi3t wheels added when someone asks.
- Crate location and tag namespace. *Recommended:* in this repository under
  `kernels/`, polars' shape, tag `kernels-vN.M`, one `maturin-action`
  workflow on that tag.
- The threshold's shape in task 1: a per-kernel row floor is one constant per
  kernel; a work product needs the summed width, which the caller has.

## Non-goals

Porting the indexing traversal and the figure rasteriser is listed as a task
because the dependency cannot drop without them, but each is its own
commit series against its own equivalence test and may become its own WP
once the model tier ships. A rayon pool (item 4) waits on item 1's
measurement. FPA and the peaks buffer stay fenced (1122).

## Tasks

- [ ] Threading on work: `_THREAD_MIN_ROWS` replaced by a per-kernel floor
      or a work product in `compiled.py`; `bench_aot_kernels.py` reports
      pooled against inline calls; trigger end to end before and after, as
      ranges, in the handover. Under numba, bit-neutral, its own PR.
- [ ] Branch counters in the agreement pass (`n_terms` arms, `spell`,
      `has_ax`), and the pass run on Windows and macOS x86_64 (a temporary
      workflow, as 1939 did), closing 1939's two owed platforms.
- [ ] The relaxed rule written: root CLAUDE.md's compiled-tier clause,
      `compiled.py` and kernel docstrings, `test_compiled_kernels.py`'s bars
      per kernel, the fit-level guard; `tests/CLAUDE.md` § Quoting numbers'
      "which path produced it" sentence re-read against it.
- [ ] The `rietx-kernels` crate from `examples/aot_spike/rust/` into its
      decided home, with the three code fixes (distinct-buffer check, per-plane
      shape check against `phi`, checked index conversion), `KERNEL_ABI`,
      `module-name`, abi3-py311, `codegen-units = 1`, `lto = "fat"`.
- [ ] `compiled.py` loads the wheel: import, ABI check, decline that warns
      once and reaches `capabilities()`; `_SURFACE_FLAGS`/`features` updated;
      the numba model kernels and the cache-directory and warm-thread
      machinery removed from the model tier; `install.md` and
      `compatibility.md` say what changed.
- [ ] Vectorised exponential: choose and license-check an implementation
      (SLEEF is Boost-licensed, ARM optimized-routines MIT, numpy's SIMD `exp`
      BSD; GPL sources are concepts only), state its bound, loop interchange
      in the two FCJ kernels, the bound asserted, goldens re-pinned once;
      measured against the serial numbers above.
- [ ] x86-64-v3 multiversioning, measured on the Linux x86_64 runner against
      1939's 0.85–0.97×.
- [ ] Release: the wheel workflow (five jobs, 36–79 s each in 1939's run), the
      tag namespace, the agreement pass and the bounds run on every wheel
      platform in CI, a section in `RELEASING.md`; `pyproject` pins
      `rietx-kernels>=N,<N+1`.
- [ ] numba demoted to an extra for the indexing and figure tiers;
      `pyproject`'s dependency comment rewritten.
- [ ] Port the indexing traversal against `test_acceptance_indexing.py` and
      its unit equivalence tests; port the rasteriser against its own; numba
      removed.
- [ ] Tests: the guard, the bars, the branch counters, `test_capabilities`'s
      new flag writer, `test_compiled_kernels.py` on both paths; the fast
      selection's passed+skipped delta quoted.
- [ ] Skill: `references/diagnostics-indexing.md`'s `compiled_kernels`
      paragraph rewritten (no numba to omit; a wheel that imports or does
      not), and `install.md`'s agent admonition. No body change: an agent
      never sees which compiler built a kernel.

## Acceptance

```sh
# a fresh install carries no numba and the kernels import
uv venv /tmp/rx && uv pip install --python /tmp/rx/bin/python rietx && \
  /tmp/rx/bin/python -c "import rietx, rietx_kernels; print(rietx.capabilities()['features'])"
# agreement, bounds and branch coverage inside the two fits
.venv/bin/python examples/aot_spike/bench_aot_kernels.py --cases trigger,cpd-1a --repeats 5
# the kernel tests on both paths, and the fit-level guard
.venv/bin/python -m pytest tests/test_compiled_kernels.py -q
RIETX_COMPILED=0 .venv/bin/python -m pytest tests/test_compiled_kernels.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bench's agreement column is zero for every kernel outside the
exponential's ulp column, on every wheel platform. Trigger end to end is
quoted as a range against the same session's numba range; the target from
the numbers above is ~3.7 s against 5.99–6.51 s, and anything under 4.5 s
with the guard green is a pass.

## References

- WP-1939 (the spike, the verdict, the two Rust traps, the Linux run and the
  wheel matrix), WP-1115 (the tier's four rules), WP-1521 (a tier that did
  not run must say so).
- jsonschema's `pyproject.toml` (`rpds-py>=0.25.0`), github.com/python-jsonschema/jsonschema;
  rpds-py, github.com/crate-py/rpds.
- SLEEF (Shibata & Petrogalli 2020, IEEE TPDS 31(6), Boost licence);
  ARM optimized-routines `exp` (MIT); numpy `npyv` exp (BSD).
- PyO3 guide, `Python::detach` and abi3; rust-numpy README (abi3 under
  `numpy` crate); maturin, www.maturin.rs; `multiversion` crate.
- `docs/RELEASING.md` (build from the tag, never by hand).

## Handover log

### 2026-10-10 — filed from 1939's review session

Anyone picking this up knows three things that 1939 did not. The thread
pool never ran in either benchmark fit, so the first 1.4× is a Python
constant and needs no Rust. Three quarters of the FCJ kernels' time is the
exponential, so the second gain needs the bit rule relaxed, and the
maintainer has relaxed it for the exponential alone. And the decision to
replace numba is taken, for the install rather than the speed.

*Done.* Filed; no open WP owned the build (1939's Next asked for it, 1115
and 1521 are the tier's rules and its flag). Context carries the review's
findings, the measurements and the decisions. 1939 closed in the same
commit series with its two corrections.

*Measured.* Every number in § Context, `[dev]` venv, darwin/arm64, machine
idle; the probes are scratchpad scripts, re-derivable from `bench_refinement`'s
cases and a timing wrapper over `compiled._KERNELS`.

*Next.* Task 1, on its own PR under numba. Then the two owed decisions.
