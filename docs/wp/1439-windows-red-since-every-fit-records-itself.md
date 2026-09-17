# WP-1439 — Windows, red since every fit started recording itself

Milestone: unscheduled · Status: 🔄 2026-09-17 — claimed by @yue-here
Depends on: — (1403, 1404 are what turned it red)

## Goal

The nightly's Windows job is green again, and the guard that was supposed to
catch this class knows about the two constructs that got past it: a POSIX-only
import at a test module's top level, and a line-oriented format inheriting the
platform's line ending.

## Context

`rietx` claims Windows in its OS classifiers, and `docs/RELEASING.md` step 4
makes a green Windows nightly the pre-upload gate for any release that repeats
the claim. The job has been red since 2026-09-15, three nights, and the last
green run was 2026-09-14 — the day the `v1.4.0` tag was cut. What landed in
between is the run-recording track, WP-1401 to 1438.

Latest failing run: `gh run view 35211225530`, **3 failed, 5187 passed, 146
skipped, 1 error**. The other three nightly jobs (full Linux, macOS, torch)
pass. Each failure, and which side of the seam it is on:

| Site | What happens on Windows | Whose bug |
|---|---|---|
| `tests/test_runs.py:12` | `import fcntl` at module top → `ModuleNotFoundError`, the whole module fails to collect (this is the `1 error`) | the test's |
| `tests/test_telemetry.py:449` | `blocked.chmod(0o500)` does not make a directory unwritable on Windows, so `attach` never fails, so nothing warns: `0 == 1` | the test's premise |
| `tests/test_bench_refinement.py:294` | `account.bytes` is 39, `st_size` is 41 — text mode translated two `\n` to `\r\n` | **the package's**, see below |
| `tests/test_watch_app.py:178` | `gui_command` is `rietx gui --scratch campaign\sample.rex`; the test pins a forward slash | the test's |

**The package half is the newline.** `runs.py:1262` opens the event log with
`open(self.path, "a", encoding="utf-8")` and `history/store.py:57,67` open
`history.jsonl` the same way. Text mode translates `\n` to the platform's
ending on write, so a JSONL file this package writes on Windows is CRLF and
one it writes anywhere else is LF. These are the package's own formats, and
`history.jsonl` is part of a `.rex` project, where the root CLAUDE.md's rule
is that the bytes are the contract. A reader tolerates the stray `\r` because
`json.loads` treats it as trailing whitespace, which is why nothing but the
byte count noticed.

**The guard already exists and has the right shape.** `tests/test_portability.py`
is WP-1002's source guard: it parses `src`, `tests` and `examples` and fails on
a construct, because the failure it prevents is invisible on the platform this
package is developed on. It carries two rules — text I/O must name its
encoding, and CSV must be written through `newline=""`. The second is this
WP's newline rule one case over: `csv.writer` emits its own `\r\n` and must
not have it translated again. A JSONL writer emits its own `\n` and must not
have it translated at all. Neither of the two constructs that broke this time
has a rule.

`os.path.relpath` returning a backslash on Windows is **correct** — a reader
pastes that command into `cmd` or PowerShell and it works — so `gui_command`
is not changed, only what the test compares against.

`attach` catches `BaseException` (`runs.py:1876`), so any `OSError` provokes
the warn-once path. That is what makes the telemetry test portable without
`chmod`: a run root whose parent is a *file* fails to `mkdir` on every
platform, and it is a real filesystem failure rather than a simulated one.

## Non-goals

- **Making Windows a supported development platform.** The claim is that the
  fast suite passes there, and that is all this restores.
- **The `torch`/`jax` backends on Windows.** Not installed by the Windows job.
- **Rewriting `run.lock` to work on Windows.** `runs.py` already answers
  `"unavailable"` without `fcntl`, which is a documented third answer and not a
  failure. A Windows locking implementation via `msvcrt.locking` is a real
  feature and belongs in its own WP, not in a suite repair.
- **Opening v1.5.** This WP clears the pre-upload gate; whether to open the
  milestone is the maintainer's call.

## Tasks

- [x] `tests/test_runs.py` imports `fcntl` the way the package does, and the cases that need a real lock skip on a platform without one
- [x] `tests/test_telemetry.py`'s unwritable-root case is provoked portably; the `chmod` provocation stays where it reproduces the measured failure
- [x] Every JSONL writer opens with `newline="\n"` (four sites in three modules, not the two this WP was filed for), so a run log and a `history.jsonl` are the same bytes on every platform
- [x] `tests/test_watch_app.py` compares `gui_command` against the platform's separator
- [x] `tests/test_portability.py` grows the two rules that would have caught this: no unguarded POSIX-only import, and a line-oriented writer names its newline
- [x] Nightly dispatched on this branch, Windows job green, counts quoted with venv and platform
- [x] Skill: none — this WP changes no surface an agent driving rietx touches, and the newline fix is invisible to a reader of either format

## Acceptance

There is no Windows machine here and no Windows job on the per-push gate, so
the criterion is the nightly's `windows` job green on this branch, dispatched
by hand. It runs the fast suite, ~6 min.

```sh
gh workflow run nightly.yml --ref wp1439-windows-red-since-every-fit-records-itself
gh run list --workflow nightly.yml --limit 3     # `gh pr checks` reads a dead run as pending
```

**Met.** Run `35275114425`, job `105383742008`: **5298 passed, 152 skipped,
0 failed** in 491 s, Windows, `[dev]`. macOS green on the same run.

Two rounds, because the first fix made the second failure visible. The
nightly is the loop, not a last check:

| Round | Windows result |
|---|---|
| Before (run 35211225530) | 3 failed, 5187 passed, 146 skipped, **1 error** — `test_runs.py` unrun |
| After round one (35273799888) | 2 failed, 5292 passed, 154 skipped |
| After round two (35275114425) | **0 failed**, 5298 passed, 152 skipped |

Local, macOS arm64, `[dev]`: 5317 passed, 133 skipped. The totals agree
across platforms — 5298 + 152 = 5317 + 133 = 5450 — which is the check that
Windows is skipping and not losing cases.

Locally, the half of the story a POSIX machine can see is `fcntl` going
missing. `tests/` is run with the import blocked, and nothing may fail for
that reason:

```sh
.venv/bin/python -m pytest tests/test_portability.py tests/test_runs.py tests/test_telemetry.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1002 built `tests/test_portability.py` and measured the seven original
  Windows failures (six `charmap` decodes, one `\r\r\n` CSV).
- `docs/RELEASING.md` step 4 — the Windows nightly as the pre-upload gate.
- Failing run: `gh run view 35211225530` (2026-09-17).

## Handover log

- **2026-09-17** — created.
