# WP-2047's probes

These are the scripts behind WP-2047's Context, "The staleness test,
measured". Each wraps `refine.compile_model`, runs one family's fit, and then
measures the staleness candidates from the captured compiles. They import
`tests.`, so each takes the repository root as its first argument. The
`hostile` family needs the IUCr QPA round-robin data under `tests/data/qarr`
and restores the tolerance schedule from before WP-2045's option 5, under which
cpd-1b's warm stage still runs away. One family a process, because `hostile`
patches `RefinementPlan.stage_ftols`:

```sh
OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe1.py . fap
```

| Script | What it measures | Run time, one run on 2026-10-25 |
|---|---|---|
| `probe1.py` | At each stage's answer: `lost`, the χ² ratio fresh/frozen, how many windows a fresh compile widens, and a fresh compile's seconds against the stage's | 1-4 s a family |
| `probe2.py` | `lost` and the χ² ratio at every accepted iteration of the hostile warm stage's first solve | ~1 min |
| `probe3.py` | `lost` at every accepted iteration of every stage, and beside it the pseudo-Voigt estimate taken off the frozen model alone, with its cost | ~1 min a family, `hostile` ~3 min |

All three ran on macOS arm64 (`[dev]`, Python 3.12) at `28c88711d`. The
families are `tests.test_window_domain._protocol`'s four (`lab6`, `fap`,
`cpd1a`, `nac`) plus `hostile`.

These scripts are records, not tests. Nothing runs them, so a change to
`compile_model`'s signature, to `CompiledPhase.win` or to the `eval` event's
`values` can break them silently. Probe 3 gives each compile the `eval` events
between it and the next compile, read against the most recent `stage_start`.
A collapse's second solve has its own `stage_start` and no compile, so its
iterations land in the same row as the first solve's: the hostile warm stage
reads 136 iterations, 62 of them the first solve's.
