# WP-1002 — CI matrix

Milestone: v1.0 · Status: ✅ 2026-07-29
Depends on: —

## Goal

Every push to `main` (and every PR) runs lint plus the fast suite on Linux; a
weekly job runs the whole suite, `slow` real-data acceptance included, plus the
rest of the supported Python range; a monthly one covers macOS and the optional
backends. A green tree therefore means "green somewhere other than the
maintainer's laptop", which is what v1.0 needs before it can freeze an API or
publish a wheel — with the two things that phrase *cannot* mean written down
rather than implied: no hosted runner has a Metal device, and none reproduces
the bit-identity goldens' capture machine.

**The cadences are set by a budget, and that is part of the design.** This repo
is private on the free plan: 2000 Actions minutes a month, billed per job
rounded up, default spending limit $0 — so over-budget means a month with no
CI, not a surprise bill. Per push 5 billed minutes, weekly 55, monthly 66.
Every job here is priced in the workflow that runs it.

## Context

The suite is already CI-shaped; almost all the work is deciding *what runs
where*, and paying for the answers with measurements rather than assumptions.

**What the workflows must run.** From CLAUDE.md's Commands block:

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup              # full, incl. slow acceptance
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow" # fast gate
.venv/bin/python -m ruff check src tests examples                 # must be clean
```

`--dist loadgroup` is **not optional**: it is what honours the `xdist_group`
marks that keep a shared expensive fixture on one worker. Plain `--dist load`
silently refits and the suite takes far longer while still passing, so a
workflow that drops it degrades quietly rather than failing.

Do **not** add `-q` on the command line: `pyproject.toml`'s
`addopts = "-q"` already supplies one, and a second makes `-qq`, which
suppresses pytest's final `N passed` summary line entirely — in a CI log that
is the one line anyone reads. (Found the hard way while measuring for this WP.)

**Files to touch.** `.github/workflows/` (new), `pyproject.toml` (a marker, if
the golden decision below needs one), `README.md` (badge + what is gated
where). No `src/` change should be needed; if the matrix forces one, that is a
portability bug and belongs in its own commit.

**Costs that shape the design.** macOS runners bill at a **10× minute
multiplier** on a private repo, and the maintainer develops on macOS/arm64, so
a per-push macOS job is simultaneously the most expensive job in the matrix and
the one re-testing the best-covered platform. Linux per push, macOS nightly and
on `workflow_dispatch`. `[torch]` is a ~500 MB wheel (jax ~100 MB) — nightly
only. When the repo goes public for the release, Actions minutes stop being
metered and macOS can be promoted; that is a WP-1003 note, not a blocker here.

**No data is fetched.** The pre-split scope says "nightly heavy validation with
fetched data", which predates the tree: all 18 MB of it is vendored under
`tests/data/` with provenance in `tests/data/README.md`. The fetch route only
matters if WP-1003 un-vendors the QARR patterns over their licence, and then it
is the Internet Archive, never iucr.org (Cloudflare JS challenge).

**The one genuinely open question is the bit-identity goldens.**
`tests/test_backend_shim.py::test_numpy_path_bit_identical_to_golden` compares
nine `tests/data/backend_goldens/*.npz` with `np.array_equal` — no tolerance.
`tests/data/README.md` states outright that these are *environment-pinned* bit
patterns captured on macOS/arm64 Accelerate, and that "a different BLAS/numpy
build may legitimately differ in final bits". A multi-OS matrix is exactly the
thing that tests that claim. Measured for this WP before any workflow existed
(same macOS/arm64 machine, three fresh interpreters, `-m "not slow"`):

| Python | numpy / scipy | fast suite |
|---|---|---|
| 3.11.15 | 2.4.6 / 1.17.1 | green |
| 3.12.12 | 2.5.1 / 1.18.0 | green (the development venv) |
| 3.13.11 | 2.5.1 / 1.18.0 | green |
| 3.14.4 | 2.5.1 / 1.18.0 | green — `[dev]` installs cleanly, no allow-fail needed yet |

So a **numpy minor version change does not move the goldens** — 2.4.6 and 2.5.1
agree bit-for-bit on the same platform. That isolates the remaining variable to
the BLAS/libm/arch axis, which only a Linux x86-64 job can answer. Get that
answer from a real run, then encode the decision (pin the goldens to one
canonical job via a marker, or relax them) rather than guessing which way it
goes.

### Inherited

From **WP-1001** (validation matrix, landed 2026-07-29) — **fresh runtime
numbers, and one new fast-suite file that the per-push job gets for free.**

- **Re-measured 2026-07-29 on a 10-core M4**, with all extras installed:
  full suite **1197 passed / 5 skipped**, `-m "not slow"` **1116 passed /
  4 skipped**, both at `-n auto --dist loadgroup`. Every earlier figure in
  this section is superseded — and quote wall clock as a *range*, because the
  same green tree measured **7:37 and 5:44 minutes apart** on the same
  machine (fast suite 45-54 s). Size the per-push / nightly split from the
  slow end; the split the scope assumes still holds comfortably.
- **`tests/test_validation_matrix.py` belongs in the per-push job**, not the
  nightly one. It is pure AST parsing and file comparison — no refinement, no
  data — so it costs ~1 s while failing on exactly the drift a CI matrix is
  supposed to catch: an acceptance test added without a matrix row, a row
  whose test was deleted, a generated `docs/VALIDATION.md` that was not
  regenerated, or an acceptance suite that silently inherits a physics
  default instead of declaring it.
- **The golden-pinning question in the WP-0401 note below is unchanged, and
  now has evidence.** WP-1001 flipped the `Source.dispersion` default, which
  moved 21 tests, and all nine `tests/data/backend_goldens/*.npz` came back
  **bit-identical** once the toy builders declared the setting — so the
  goldens really do isolate the shim from physics. That makes them a clean
  candidate for pinning to one canonical job; what would break them is still
  a BLAS/libm change, not a package change.

From **WP-0604** (theory manual, landed 2026-07-29) — the docs build is
already inside the test suite, so CI gets it for free *if* the install is
right:

- **`[docs]` rides inside `[dev]` by self-reference** (`anatase[docs]` in
  the dev extra), so any job that installs `.[dev]` gets sphinx/myst/bibtex
  and `tests/test_manual.py` runs its five guards, including a subprocess
  `sphinx -W` build (≈4 s). A job that installs a leaner set will
  `importorskip("sphinx")` and silently skip the whole file — if a docs-less
  job is ever added, assert the skip is intentional.
- No separate docs job is needed unless the manual is *published*; building
  it is already gated per-push through the suite.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — the "fetched data" in
the scope above has a known obstacle:

- **iucr.org is behind a Cloudflare JS challenge.** Every QARR round-robin
  pattern was retrieved through the Internet Archive, URL form
  `web.archive.org/web/2020id_/…/QARR/col/<name>.prn`. A fetch-on-demand job
  needs the same route; pointing it at the live site will fail in a way that
  looks like a network flake.
- **The `slow` marker is the load-bearing runtime knob.** Full suite is ~2 min
  (was ~21 s before the real-data acceptance landed); `-m "not slow"` stays
  ~20 s. That split is what makes a per-push job viable and a nightly job
  necessary — 23 tests are currently `slow`.

From **WP-0404** (cross-backend Jacobian CI, landed 2026-07-24):

- **The `[jax]`/`[torch]` optional jobs have their target file.**
  `tests/test_cross_backend.py` is the (method × config) Jacobian-agreement
  matrix; every backend row self-skips when its package is absent, so the *same
  command* is green on a numpy-only job and covers more on an extras job. There
  is no separate "with extras" invocation to configure — install the extra and
  the rows activate. A numpy-only job still runs the central-FD and
  fp32-column-policy rows (the WP-0403 policy is not a backend and needs no
  install), so the file is never a no-op.
- **Both runtime figures above are stale**, measured 2026-07-24 on an M-series
  laptop: the full suite is **~13 min** (not ~2 min) and `-m "not slow"` is
  **~85 s** (not ~20 s). WP-0404's matrix accounts for ~42 s / ~22 s of those;
  the rest accumulated across v0.3's real-data acceptance and the v0.4 jax
  tests. CLAUDE.md has been corrected. The per-push/nightly split the scope
  above assumes still holds, but size it from a fresh measurement — the numbers
  have drifted by 6× once already.
- **jit compile, not flops, is what the jax rows cost.** The matrix caches one
  built Jacobian callable per (config, backend) so the fp32 row reuses the
  compiled one — halved that file's runtime. A CI job that shards these tests
  across workers loses the cache and pays every compile again.

From **WP-0408** (torch backend, landed 2026-07-27) — the `[torch]` extra above
is no longer hypothetical, and it splits into two jobs, not one:

- **`[torch]` activates the `torch` and `torch+fp32` rows** of
  `tests/test_cross_backend.py` plus all of `tests/test_backend_torch.py`, by the
  same self-skip mechanism as jax — install the extra, the rows appear. No
  separate invocation.
- **But the Apple-GPU tests cannot run on a hosted runner.** Every
  `torch-mps` assertion is gated on `torch.backends.mps.is_available()`, which is
  False on GitHub's macOS runners (virtualised, no Metal device). So the MPS
  claims — the only *real-hardware* evidence for WP-0403's fp32-column policy —
  are **maintainer-machine-only**, exactly like `examples/validate_cuda_mixed_
  precision.py` is CUDA-box-only. Either accept that as a documented gap or plan
  a self-hosted runner; do not read a green macOS job as "MPS verified".
- **torch is a ~500 MB wheel** (jax is ~100 MB). If the extras job is
  per-push rather than nightly, cache it deliberately; it will dominate job
  setup otherwise.
- **Both runtime figures above moved again, and one moved *down***: measured
  2026-07-27 with all extras installed and v0.4 complete, the full suite is
  **8 min 34 s** (505 tests, 38 `slow`) and `-m "not slow"` is **~90 s** —
  faster than the ~13 min recorded three days earlier *despite* adding the torch
  matrix, the true-Voigt tests and the restraint suite. Machine state moves these
  as much as the test count does. Re-measure; do not trust any number here.

From **WP-0401** (op shim, landed 2026-07-24): `tests/test_backend_shim.py`
asserts **bit-identity** against environment-pinned npz goldens in
`tests/data/backend_goldens/`. A multi-OS × multi-Python matrix is exactly the
thing that breaks bit-identity (BLAS variants, libm differences). Decide up
front whether those goldens are pinned to one canonical job or relaxed to a
tolerance elsewhere — the re-baseline rule is in `tests/data/README.md`
(regenerate via `python -m tests.test_backend_shim`, only from a green tree).

## Non-goals

- **Coverage gates.** `pytest-cov` is installed; a coverage *threshold* is a
  policy decision nobody has taken, and a number chosen to be passable teaches
  nothing.
- **Publishing.** Building/uploading an sdist+wheel, trusted publishing, tag
  automation — all WP-1003.
- **A self-hosted macOS runner for the MPS assertions.** Documented gap
  (WP-0408 above); a self-hosted runner is a security and maintenance surface
  that a private research repo should take on deliberately, not incidentally.
- **Publishing the theory manual** (GitHub Pages). It is *built* under `-W` in
  the suite already; hosting it is WP-1003's call.
- **Making the goldens portable.** If they break off macOS/arm64, the answer is
  to pin where they run — not to loosen `np.array_equal`, which would destroy
  the only guard that says "no refactor changed a single computed number".

## Tasks

- [x] Expand this stub into a full WP before starting
- [x] Measure the supported Python range locally (3.11 / 3.13 / 3.14 venvs,
      fresh resolutions) so the matrix is written against evidence
- [x] `.github/workflows/ci.yml` — per-push lint + fast-suite matrix
- [x] `.github/workflows/nightly.yml` — Linux full suite, and
      `weekly.yml` for macOS + torch (the split is forced by the minutes
      arithmetic; see the handover log)
- [x] Land the golden-pinning decision on what the first cross-platform run
      actually shows
- [x] README + DESIGN: what CI runs, and the three limits a green badge does
      not cover
- [x] Forward notes into WP-1003 `### Inherited`
- [ ] Verify `nightly.yml` and `weekly.yml` by dispatching each once
- [ ] Handover log + ROADMAP sync

## Acceptance

The matrix is green on a real run, not just locally:

```sh
gh run list --workflow=ci.yml --limit 5
gh run watch <run-id>                  # lint + the fast suite, per push
gh workflow run weekly.yml             # full suite incl. slow + 3.11/3.12/3.14
gh workflow run monthly.yml            # macOS (goldens) + torch
```

Locally, the same commands the workflows run:

```sh
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

### Measured, 2026-07-29

Local tree at the end of the WP: **1117 passed / 4 skipped in 50.8 s**
(`-m "not slow"`, 10-core M4) — one test more than WP-1001's 1116, the new
`test_every_committed_golden_is_gated`.

`ci.yml`, run 30432573764, hosted 4-vCPU Linux, cold caches — **green on all
four Pythons**:

| job | conclusion | wall clock |
|---|---|---|
| lint | success | 0:12 |
| fast py3.11 | success | 3:03 |
| fast py3.12 | success | 3:10 |
| fast py3.13 `[dev,jax]` | success | 11:12 |
| fast py3.14 (allow-fail) | success | 3:15 |

The run before it (30432077485, same tree without the golden pin) is the
measurement this WP turned on: **8 failed, 976 passed** on every Linux Python,
with all eight failures the bit-identity gate and nothing else in the suite
disagreeing at all.

`weekly.yml`, dispatched twice (30433370388 then 30434029964 with the gate
deselected):

| job | conclusion | wall clock | what it showed |
|---|---|---|---|
| macOS (1st run, gate required) | failure | 5:27 | 1036 passed / 66 skipped and one golden state off — the measurement that produced the redesign |
| macOS (2nd run, gate reported) | success | 4:12 | goldens 7 of 8 bit-identical, `toy_rich` off by exactly 1 ulp, *identically* in both runs — deterministic, not flaky |
| torch (experimental) | success | 15:59 | the agreement matrix with numpy + jax + torch all installed, MPS rows self-skipping as designed |

`nightly.yml`, dispatched once (30433363168): **success — 1103 passed / 81
skipped in 43:56** (job 44:21). Every real-data acceptance suite in the repo
passes on Linux x86-64, which is the first time any of them has run off the
maintainer's machine. The 81 skips are the 8 platform-pinned goldens plus the
torch rows this job does not install.

Worth knowing before sizing anything: the run is **~5.6× the local full
suite**, and `--durations` says why — it is not spread thinly. The four
longest entries are *fixture setup*, not tests: `stephens-brucite` 861 s,
`qpa-sample1` 603 s, `qpa-dispersion` 482 s, plus a 693 s jax end-to-end call.
Runtime is set by the longest `xdist_group`, exactly as CLAUDE.md says, and on
4 cores those groups no longer hide behind each other.

**Windows, probed on a throwaway branch after the WP's own scope was met**
(the scope said Linux + macOS). Two runs on `windows-latest`, Python 3.13,
`[dev]`:

| run | result | what it showed |
|---|---|---|
| before fixes | **7 failed, 970 passed, 115 skipped** | six `'charmap' codec` decode errors, all in `tests/`; one real library bug |
| after fixes | **982 passed, 115 skipped, 0 failed** in 2:59 | clean |

The runner confirms the premise the failures rest on: `preferred encoding:
cp1252`, `stdout encoding: cp1252`, filesystem encoding utf-8. The one library
bug was `write_qpa_table` handing `csv.writer` output (which already ends
`\r\n`) to `write_text`, so text mode translated each `\n` again and every row
ended `\r\r\n` — **corrupt CSV for any Windows user**, invisible on POSIX,
and its sibling `write_reflection_table` had the `newline=""` idiom right all
along. Everything else was the suite being less portable than the code it
tests: the library's write paths were already correct, including `write_html`,
which is plotly's own UTF-8 writer. `fcntl` was already guarded, every path
already went through `pathlib`, and every dependency had a Windows wheel.

`tests/test_portability.py` now guards both rules by AST, not grep — the
multi-line `write_text(json.dumps({...}), encoding="utf-8")` in `viz/live.py`
is invisible to a line search, which is how one site survived the first sweep —
and each guard is checked against source that violates it so it cannot pass
vacuously. **Nothing runs Windows on a schedule**, so this is a point
measurement, not a standing claim; see the ROADMAP note and WP-1003.

**Two things a bump can break, learned here.** `astral-sh/setup-uv`'s latest
*release* is v9.0.0 but its highest floating **major** ref is `v7`; assuming
the two agree failed every job in three seconds. And the four actions were on
Node-20 majors that GitHub now force-runs on Node 24 — worth bumping before a
release, but bump against `git/matching-refs/tags/v`, not against
`releases/latest`.

## References

- GitHub Actions billing multipliers (macOS 10× on private repos) —
  docs.github.com/billing/managing-billing-for-github-actions
- `tests/data/README.md` § "backend_goldens/ — WP-0401 bit-identity baseline"
  for the re-baseline rule and the environment-pinning caveat.

## Handover log

- **2026-07-29 (later)** — **re-sized to a free-tier budget, on the user's
  statement that there is none.** The shipped configuration did not fit and
  nobody had priced it: measured, it billed **21 minutes per push** (lint 1 +
  py3.11 4 + py3.12 2 + py3.14 4 + `[dev,jax]` 10) and **1350 a month** for the
  nightly full suite, plus 284 for the weekly — about 1634 of a private repo's
  2000 free minutes gone before a single push, leaving room for roughly
  seventeen. Eight pushes landed on the day it shipped.

  Three cadences now, each priced in its own file: **per push** lint + the fast
  suite on 3.13 alone (5), **weekly** the full suite plus 3.11/3.12/3.14 (55),
  **monthly** macOS + torch (66). Scheduled spend drops 1634 → 303/month. Two
  levers did most of it. Dropping the `[dev,jax]` job from the per-push gate
  removes 10 of the 21 minutes for one extra opinion that the weekly full suite
  already carries, since it installs `[dev,jax]` itself. And `paths-ignore`
  makes a docs-only push cost **nothing** — which matters here specifically,
  because a roadmap session is mostly ROADMAP/WP/DESIGN commits; the ignore
  list deliberately excludes `docs/manual/**` and `docs/VALIDATION.md`, the two
  docs the suite actually reads.

  Confirmed on the first run of the new shape (30441280593): lint 18 s and the
  fast suite 3:15 — **5 billed minutes, as designed**. This very handover entry
  is the `paths-ignore` test: it touches only `docs/wp/`, so if the lever works
  the push that carries it creates no CI run at all.

  The lesson worth keeping is not the numbers, it is that **a CI matrix is a
  recurring-cost decision and this one was taken on coverage grounds alone**.
  The failure mode is quiet: GitHub's default $0 spending limit means an
  over-budget matrix does not bill, it simply stops running, so the first
  symptom is a month with no CI. Price a job before adding it —
  `gh run view <id> --json jobs` gives the durations, and billing rounds each
  job *up* to the whole minute, which makes a 23-second lint job cost the same
  as a 60-second one.

- **2026-07-29** — **built, pushed and measured.** Three workflows are live
  (`ci.yml` per push, `nightly.yml` Linux full suite, `weekly.yml` macOS +
  torch), the per-push matrix is green on Linux for 3.11/3.12/3.13/3.14, and
  the two questions the WP existed to answer both got measurements instead of
  opinions.

  **Done.** Stub expanded against local evidence (three fresh interpreters
  before a line of YAML). Workflows written, pushed, iterated to green. The
  golden-pinning decision landed with its measurement. README, CLAUDE.md,
  DESIGN.md ("Testing & validation policy") and two new `GAPS` rows in
  `tests/validation_matrix.py` all say what CI does and does not cover.
  Forward notes into WP-1003's `### Inherited`.

  **The goldens question is settled, and the answer split.** A *numpy* change
  does not move them: 3.11/2.4.6 and 3.12-3.14/2.5.1 all reproduce every state
  bit-for-bit on macOS/arm64. A *platform* change does — on Linux x86-64 all
  eight toy states diverge, identically on all three Pythons, and **nothing
  else in the suite fails there at all** (976 passed, 8 failed, every failure
  the golden gate). The *size* is what decided the design: 1 ulp on quantities
  that are a single arithmetic chain (`theta`, `lebail_intensity`,
  `pawley_x0`), up to ~1100 ulp (1.7e-13 relative) on `y_calc`, which
  accumulates ~130 windows of transcendental evaluations. A divergence that
  grows *with chain length* is a libm and summation-order difference, not a
  code difference. So `GOLDEN_PLATFORM = ("darwin", "arm64")`, skipping
  elsewhere with the measurement in the skip reason — a Linux contributor
  reads an explanation, not eight mystery failures. Loosening `array_equal` to
  a tolerance was the alternative and is the one thing that must not happen:
  any tolerance wide enough to absorb a libm difference absorbs a real one.

  **A design that was unaffordable, caught by arithmetic before it ran.** The
  first `nightly.yml` ran the full suite on Linux *and* macOS. At a 10×
  billing multiplier on a private repo that is ~400 charged minutes **per
  night** against a 2000/month quota — 6× the entire monthly budget for one
  job. Hence the nightly/weekly split, sized by what each platform uniquely
  covers rather than by importance: Linux carries the `slow` acceptance
  nightly; macOS carries the fast suite plus the goldens assertion weekly,
  because being the goldens' capture platform is the thing only it can do.

  **CI cannot gate anything yet.** `branches/main/protection` returns 403 —
  branch protection needs GitHub Pro or a public repo. So the matrix *reports*;
  nothing stops a red push landing on `main`. That is registered as a
  validation gap and pushed into WP-1003, because "make the repo public" turns
  out to be the same change as "make CI enforceable" and "make macOS
  affordable".

  **Measured job cost, hosted 4-vCPU Linux runner** (first green matrix,
  cold caches): lint 12 s; fast suite 3:03 / 3:10 / 3:15 on 3.11 / 3.12 /
  3.14; **11:12 on 3.13 with `[dev,jax]`.** The jax rows are not 3× the work,
  they are jit-*compile* bound against a cold cache — WP-0404 said so and
  xdist multiplies it, since every worker compiles independently. Confirmed
  locally by deleting `tests/.jax_cache` (106 MB, 55 entries): the two
  jax-heavy files alone go from ~12 s warm to 107 s cold on a 10-core M4.

  **The obvious fix was tried and does not work, which is the more useful
  result.** An `actions/cache` of `tests/.jax_cache` restored cleanly on its
  primary key (14 MB) and the job came back at **8:18 against 8:12 with a cold
  cache** — no gain, twice measured. jax's persistent cache holds only XLA
  compilations above a time threshold; per-process *tracing and lowering* are
  paid every run and nothing can cache them across processes. The cache steps
  were removed rather than left in as decoration. What would actually move this
  number is running the jax rows in one process (they already share a built-
  Jacobian cache within one, which is why the torch job deliberately skips
  `-n auto`), or moving jax to the nightly and leaving the per-push gate
  numpy-only — both worth measuring, neither guessed at here.

  **Gotchas worth keeping.** (1) `addopts = "-q"` plus a command-line `-q`
  makes `-qq`, which silently suppresses pytest's `N passed` summary — the one
  line a CI log is read for. (2) `--dist loadgroup` degrades rather than fails
  when dropped: the shared fixtures refit on every worker and the suite just
  gets slower. (3) A skip and a pass look identical in a summary line, which
  is why the weekly macOS job greps for `skipped`/`no tests ran` *and* asserts
  exactly 8 goldens ran, and why a new always-running test asserts
  `backend_goldens/` and `STATES` are the same set. (4) The capture entry point
  now refuses to write a golden off the pinned platform — a half-and-half
  baseline set could never be green anywhere.

  **The pin narrowed once more, and it was the last measurement of the WP.**
  Dispatching `weekly.yml` answered the question the platform tuple only
  assumed. A **hosted** macOS/arm64 runner — same numpy 2.5.1, same scipy
  1.18.0, same Accelerate as the capture machine — reproduced 7 of 8 states and
  missed `toy_rich:y_calc` by 1.4210854715202004e-14, which is **exactly one
  ulp** at a value in [64,128), on a single element. Local runs at 1/2/4/8 BLAS
  threads are bit-stable, so it is not reduction ordering; what is left is the
  system math library the machine image ships, and nothing visible from Python
  distinguishes one image from another.

  So `("darwin", "arm64")` is the right predicate for *worth attempting* — 7/8
  at one ulp, against 8/8 at up to ~1100 ulp on Linux — but it is not a promise
  of a match, and **no CI environment asserts these bits at all**. The weekly
  macOS job therefore deselects the gate from the suite and runs it as its own
  step, failing only if the goldens *skip* (a broken pin would mean nothing
  anywhere checks them) and warning on a numeric mismatch so drift in the count
  or the size stays visible. The gate is maintainer-machine evidence, exactly
  the shape of the Apple-GPU gap, and is recorded as one.

  **All three workflows are verified by a real run, not just by review** —
  per-push matrix green on four Pythons, weekly green on macOS and torch, and
  the nightly **green on the full suite including every real-data acceptance
  test: 1103 passed / 81 skipped in 43:56**. That is the first time the
  acceptance suites have run anywhere but the maintainer's machine, and they
  passed unchanged, which is the substantive claim this WP was for.

  **Next.** Nothing blocking. Three things a successor would want: the nightly
  is ~5.6× the local full suite and its `--durations` shows the cost is four
  *fixture setups* (`stephens-brucite` 861 s, `qpa-sample1` 603 s,
  `qpa-dispersion` 482 s) rather than a broad slowdown — so splitting a group
  is still the only lever, exactly as CLAUDE.md says; the jax rows want either
  a single-process run or a move to nightly (measure, do not guess — the
  obvious cache fix was tried and did nothing); and promoting macOS to nightly
  becomes free the moment WP-1003 makes the repo public.

- **2026-07-22** — created as a stub from the ROADMAP split.
