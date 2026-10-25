# WP-2051's probes

The scripts behind WP-2051's Context. Like WP-2047's
([`2047-batch/`](../2047-batch/README.md)), they import `tests.` and take the
repository root as their first argument. They also import `2047-batch/probe7.py`.

```sh
OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2051-batch/resize_profile.py . cpd1a
```

| Script | What it measures | Run time, one run on 2026-10-25 |
|---|---|---|
| `resize_profile.py` | One resize's milliseconds by part (`phase_peaks` memo warm and cold, the k(η) bisection, bounds, FCJ extent and node counts, the batch layout, a whole `rewindow`), median over 40 sizing calls of probe 7's perEval fit | 5-15 s a family |

These scripts are records, not tests. Nothing runs them.
