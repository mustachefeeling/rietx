# WP-2045's probes

These are the five scripts behind WP-2045's Context bullets, "What the runaway
is". Each one runs the hostile series' cpd-1a → cpd-1b as `chained_all` does.
They wrap `refine.compile_model`, stop at cpd-1b's runaway closing compile,
and then measure one thing from the captured models. They need the IUCr QPA
round-robin data under `tests/data/qarr`. They import `tests.`, so each takes
the repository root as its one argument:

```sh
OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2045-batch/probe.py .
```

`OPENBLAS_NUM_THREADS=1` matters on Linux, because WP-2003 measured
`leggauss` at 5.4-6.0 s a call under default threading.

| Script | What it measures | Run time measured 2026-10-24 |
|---|---|---|
| `probe.py` | Work at each compile, and Rwp at the runaway answer on the frozen model, on fresh declared- and closing-precision compiles, and at the stage's start | ~20 s |
| `probe2.py` | The warm fit as short recompiling stages, every K = 400, 50, 10 and 3 iterations | ~5 min |
| `probe3.py` | The single frozen warm stage under `ftol` 1e-6 and 1e-9, at `max_iter` 100 and 400 | ~1 min |
| `probe4.py` | The Bragg intensity each stage's frozen windows drop at its answer, and the χ² ratio fresh/frozen | ~1 min |
| `probe5.py` | A re-solve from the runaway answer on fresh windows at `ftol` 1e-6 and 1e-9 | ~3 min |

The run times were on a Linux x86-64 cloud container (4 cores, `[dev]`,
Python 3.12) at `7d24e09e7`, and the numbers are in WP-2045's Context. These
scripts are records, not tests: nothing runs them, so a change to
`compile_model`'s signature or to `CompiledPhase.win`/`fcj_n` can break them
silently.
