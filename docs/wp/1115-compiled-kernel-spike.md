# WP-1115 — compiled-kernel spike (gated: open only if the floor still binds)

Milestone: v1.1 · Status: ⬜
Depends on: 1112, 1114 (the gate below reads their measured outcomes)

## Goal

**Gate — read first**: this WP starts only if, with 1112 landed and 1114's
go/no-go recorded, the 1111 harness still misses the milestone targets
(warm-series ~1 s/pattern band, cold trigger-shaped fit in low single-digit
seconds) *and* the remaining gap is measured to sit in python dispatch /
ragged-loop overhead rather than in evaluation count (1113's territory). If
the targets are met, close this WP 🛑 with one line and the harness table.

If it opens: a compiled version of the peak loop — numba first, Cython or a
small C extension as fallback — measured against the batched numpy path, and
a packaging decision (optional extra, never a core dependency) put to the
user with the numbers.

## Context

- **Why a compiled kernel is the third resort, not the first** (the
  2026-08-20 review's language-gap decomposition, recorded in 1109/v1.1.md):
  python's cost is ~0.6 µs dispatch per numpy call plus interpreter overhead
  per line — huge for the current per-reflection loop (≈11 µs of a 13.6 µs
  kernel call is dispatch), but 1112's batching removes most of it, and a
  memory-bound batched numpy kernel runs within ~2–3× of single-threaded
  C++. What batching *cannot* recover: (a) ragged axes — FCJ node counts
  vary 0–64 per reflection and padding cost 0605's forward prototype its
  whole win (0.58×), where a compiled loop handles raggedness for free; and
  (b) threading — TOPAS gets 2–4× on a laptop (Coelho 2018 §5.2) and the
  GIL denies numpy-level python loops any of it, while a numba
  `@njit(parallel=True)`/`prange` kernel or a nogil extension gets it back.
- **What to compile**: exactly the kernel 1112 will have isolated — the
  (line, reflection) profile + derivative-bases evaluation with its
  window scatter — behind the same interface, so the compiled path is a
  drop-in the conformance suite can diff. Nothing above it (scalar chains,
  table decode, scipy) is dispatch-bound after 1109/1112.
- **The three-backend rule still binds** (CLAUDE.md Conventions): the
  compiled path is a *numpy-path accelerator*, not a fourth backend — jax
  and torch keep the traced twin (`backend/traced.py`), and the compiled
  kernel must reproduce the numpy path bit-identically or carry the
  re-baseline argument, exactly as 1112's scopes do.
- **Packaging reality check before writing code**: numba pins numpy versions
  aggressively and adds ~an LLVM to the install; Cython/C add a build
  toolchain to source installs. That is why the decision is the user's, with
  the measured win in hand, and why the default install must keep working
  without it (`[speed]` extra shape, like `[jax]`/`[torch]`).
- **Fences already measured elsewhere, do not re-open**: GPU execution
  (46–182× slower, launch-latency-bound — v0.4 record); `torch.compile`
  (2.5× slower after 38 s, dynamo specialises per window — 0605);
  `tr_solver='lsmr'` and friends (solver-survey §2 dead ends).

## Non-goals

A rewrite of anything beyond the isolated kernel; a fourth backend; GPU;
making the compiled path the default install; opening before the gate says
so.

## Tasks

- [ ] **Check the gate** against the 1111 harness with 1112/1114 outcomes in
      hand; record the reading here (open, or close 🛑 with the table).
- [ ] numba prototype of the ragged kernel (serial first, then `prange`);
      bit-identity or recorded deviation vs the numpy path; wall on the
      trigger-shaped and series cases.
- [ ] Fallback prototype (Cython or C extension) only if numba's numbers or
      packaging disqualify it.
- [ ] Thread-scaling measurement (1/2/4/8 threads) on the series case — the
      one axis pure numpy cannot reach.
- [ ] Packaging decision with the user: `[speed]` extra vs not shipping;
      conformance-suite wiring for whichever lands.

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py     # with/without the compiled path
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

A gate reading recorded in this file either way; if opened, before/after
ranges from the harness and the equivalence bar stated per 1112's pattern.

## References

- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 210–218 §5.2 — the
  threading numbers the GIL currently denies.
- WP-0605's file — the padding measurements that make raggedness the
  compiled path's case.

## Handover log

- **2026-08-20** — created by the 1109 review session, deliberately gated;
  the gate is the first task, and closing 🛑 because the targets are already
  met is the good outcome.
