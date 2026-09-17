# WP-1439 — Windows, red since every fit started recording itself

Milestone: v1.5 · Status: ✅ 2026-09-17 — Windows green on the reviewed tree, 0 failed; the pre-upload gate is clear
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

### 2026-09-17 — the track's Windows bill, and the one real defect under it

The Windows nightly is green again, so a release can be cut. It had been red
for three nights, since the day after `v1.4.0` was tagged, and
`docs/RELEASING.md` step 4 makes that job the pre-upload gate for any version
repeating the OS classifier's claim. The cause was the run-recording track
landing in the four days after the tag. Three of the four failures were the
tests' own POSIX assumptions. The fourth was the package: every JSONL file it
writes carried the platform's line ending, so a `history.jsonl` written on
Windows held the same events at a different size and a different checksum from
one written anywhere else.

A fifth defect surfaced only once the first fix let the module collect, and it
is the largest of them. `liveness_of` answers by the first rung that fires,
and Windows has no `flock`, so its lock rungs never fire and the pid fallback
is the only rung it has. That rung was mute: `os.kill` raised a bare `OSError`
there rather than `ProcessLookupError`, and read as "cannot say" it meant every
run in `rietx watch` on Windows showed `unknown`.

**Corrected in review, same day.** The first fix read
`ERROR_INVALID_PARAMETER` as "no such process", on the premise that `os.kill`
on Windows is `OpenProcess`. It is not, for this signal: `0` **is**
`signal.CTRL_C_EVENT`, so the call goes to `GenerateConsoleCtrlEvent`, which
fails that same winerror for every pid that is not a console process group —
alive and dead alike — and, for one that is, delivers a Ctrl+C to the fit the
reader came to look at. So the rung would have answered `abandoned` about
running fits, and `os.kill` is not a call a reader may make there at all. The
probe on Windows is now `OpenProcess` + `GetExitCodeProcess` through `ctypes`
(`runs._pid_alive_windows`), which is the question that was meant and the one
`psutil` asks. Every unexpected failure stays `None`.

The test that was supposed to hold this asserted `!= "unknown"` about our own
pid, which a confidently wrong `abandoned` also satisfies; it now asserts
`_pid_alive(os.getpid()) is True`, on every platform, and a Windows-only case
exercises both ends of the new probe. **Verified**: run 35277708496, job
105392198673, 5300 passed, 153 skipped, 0 failed. That run is the first in
which the pid rung was actually put a question it could fail.

**Done.**

- `tests/test_runs.py` guards its `fcntl` import the way the package always
  has. Unguarded it was a collection error, so all 51 cases in that file went
  unrun behind one `error` line.
- Five cases whose assertion is about the lock skip without `flock`. The two
  about the pid rung do not, because that rung now answers on Windows.
- The unwritable-root case is parametrised over two provocations. `chmod` is
  what WP-1403 measured and stays where it reproduces that; a run root whose
  parent is a regular file defeats `new_run_dir`'s opening `mkdir` on every
  platform, so Windows covers the boundary instead of skipping it.
- Every JSONL writer pins `newline="\n"`: four sites in `runs.py`,
  `history/events.py` and `history/store.py`, plus seven fixture handles in
  the suite. Readers need no migration, since a text-mode read translates
  `\r\n` back.
- `gui_command` is unchanged and its test now compares against
  `os.path.join`. A backslash is what a reader on Windows pastes into their
  own shell, which is that test's own stated point.
- `tests/test_portability.py` grew the two rules that would have caught this,
  and `tests/CLAUDE.md` grew the one no test can hold.

**Measured.** All counts `[dev]`, and the platform is named because that is
the whole subject here.

| Round | Windows |
|---|---|
| Before, run 35211225530 | 3 failed, 5187 passed, 146 skipped, 1 error |
| After round one, 35273799888 | 2 failed, 5292 passed, 154 skipped |
| After round two, 35275114425 | 0 failed, 5298 passed, 152 skipped, 491 s |
| After review, 35277708496 | **0 failed**, 5300 passed, 153 skipped, 367 s |

Local fast selection, macOS arm64: 5319 passed, 134 skipped, 1:22. The
baseline for this branch was 5445 cases and the tree holds 5453, +8 for
exactly the eight added: one telemetry parametrisation, three pid cases and
four guard cases. A ninth was added mid-session and replaced by the review,
so it nets to nothing. Round two's totals agreed across platforms at
5450 and the reviewed tree's agree at 5453, which is the check that Windows
is skipping cases rather than losing them.

**Gotchas for whoever is next in here.**

- **The nightly is the loop, not the last check.** Each fix made the next
  failure visible, and there was no way to see the second pair until the first
  landed. Two dispatches at about nine minutes each cost less than any amount
  of reasoning about what Windows does.
- **A meta-path import blocker does not reach xdist workers.** Blocking
  `fcntl` under `-n auto` proved nothing, and the first sweep that claimed
  nothing else wanted `fcntl` was worthless. Serially it is real, and slow.
- **`-q` on top of `addopts`' own is `-qq`**, which prints no summary at all.
  It cost a 25-minute serial run its counts. The rule is already in
  `tests/CLAUDE.md`; this is the second time it has been paid.
- **Windows liveness now rests entirely on the pid rung**, which its own
  docstring calls subject to pid reuse. A held `run.lock` is what makes
  `abandoned` distinguishable from `done` without a heartbeat contract, and
  Windows has no equivalent until somebody writes one over `msvcrt.locking`.
  That is a real feature and it was fenced out of this WP deliberately.

**Deliberately not generalised.** The newline guard sits on `open` and not on
`write_text`, and the decision was measured rather than assumed. Gating
`write_text` the way the CSV rule gates, on the module naming `jsonl`, flags
125 sites. Reading every `write_text` in `src/` by hand found no real defect
among them: they write JSON documents, an empty file, a `.gitignore`, and
`summary.txt`, which is prose where the platform's ending is the right one.

**Next.** Opening v1.5 is the decision this unblocks, and it is the
maintainer's. 492 commits and 29 WPs have landed under no milestone since the
tag, which is the largest unreleased body this repo has held. If it opens, two
things follow from this WP: the release notes owe a line saying Windows works
again, and the record owes no entry, since a bug fix is neither a break nor an
addition under protocol rule 6. A Windows `run.lock` over `msvcrt.locking` is
the one candidate WP this session leaves behind.

- **2026-09-17** — created.
