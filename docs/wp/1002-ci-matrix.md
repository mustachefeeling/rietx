# WP-1002 — CI matrix

Milestone: v1.0 · Status: 🔶 in progress
Depends on: —

## Goal

Every push to `main` (and every PR) is gated by a lint + fast-suite matrix
across the supported Python range on Linux, and a nightly job runs the whole
suite — including the `slow` real-data acceptance — on Linux *and* macOS with
the optional backends installed. A green tree therefore means "green somewhere
other than the maintainer's laptop", which is what v1.0 needs before it can
freeze an API or publish a wheel.

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

- **`[docs]` rides inside `[dev]` by self-reference** (`pxrd-refine[docs]` in
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
- [ ] `.github/workflows/ci.yml` — per-push lint + fast-suite matrix
- [ ] `.github/workflows/nightly.yml` — full suite × {Linux, macOS} + a torch job
- [ ] Land the golden-pinning decision on what the first cross-platform run
      actually shows
- [ ] README: CI badge and a short "what is gated where" note
- [ ] Handover log + ROADMAP sync + forward notes into WP-1003 `### Inherited`

## Acceptance

The matrix is green on a real run, not just locally:

```sh
gh run list --workflow=ci.yml --limit 5
gh run watch <run-id>            # every `fast` job green; 3.14 recorded either way
gh workflow run nightly.yml && gh run watch <run-id>   # full suite, both OSes
```

Locally, the same commands the workflows run:

```sh
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- GitHub Actions billing multipliers (macOS 10× on private repos) —
  docs.github.com/billing/managing-billing-for-github-actions
- `tests/data/README.md` § "backend_goldens/ — WP-0401 bit-identity baseline"
  for the re-baseline rule and the environment-pinning caveat.

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
