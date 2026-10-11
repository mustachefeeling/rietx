# WP-1521 — `compiled_kernels_active` says the kernels ran, per tier, or says it does not know

Milestone: unscheduled · Status: 🛑 2026-10-10 — superseded by WP-1940, whose PR #864 did its Goal
Track: What fires, and what stays silent
Depends on: — (1508 declined it at review, for a signal both tiers report)

## Goal

`capabilities()` never reports a compiled tier as active once its build has
failed. It reports the model tier and the indexing tier separately, because
their builds can fail separately, and before anything is built it says that
it has not been.

## Context

**The flag.** `capabilities.py` sets `"compiled_kernels_active":
compiled.enabled()`, and its comment says a client asks it "why is this build
slow". `model.compiled.enabled()` is read once and cached from the
`RIETX_COMPILED` switch and `available()`, which asks whether numba imports.
It never learns whether a build succeeded.

**Two tiers, two latches, one flag.**
- *Model tier* (`model/compiled.py`). `_kernels()` catches a failed
  `_kernels_numba.build()` and sets `_UNAVAILABLE`, so a **later**
  `available()` reads `False`. But `enabled()` keeps the `True` it cached
  before the failure, so `compiled_kernels` flips to `False` while
  `compiled_kernels_active` stays `True`.
- *Indexing tier* (`indexing/dichotomy._traversal_kernels`, WP-1508). It is
  built lazily on first dichotomy use under its own `_KERNELS_FAILED` latch,
  and it declines to the numpy loop. Neither `available()` nor `enabled()`
  sees that latch, so both flags can read `True` while every search runs
  numpy.

WP-1508's review found the second gap and declined it there. The model tier's
flag has the same gap, and the fix is "a signal both tiers report, not a
branch here".

**Two constraints on the fix.**
- **A capability query must not compile** (`capabilities.py`'s own comment;
  the indexing build is 4.4 s cold). Before a build the honest answer is "not
  built yet", which is `None` rather than `True`. That is root CLAUDE.md's
  rule that a field's empty state must not read as an answer (WP-1076).
- **The field is a versioned contract's member.** `capabilities()` is quoted
  by clients and meta-tested (every `*_version` field, every arm from a live
  registry, `_SURFACE_FLAGS` against `__all__`). A per-tier shape is a
  change to what a client reads. Keep `compiled_kernels_active` meaning what it
  says, or deprecate it through `docs/manual/using/compatibility.md` the way
  that page describes, and state which in the release note.

**Why the rate is low.** numba is a required dependency, so this fires only on
an install where it imports and a build fails (both builds are
`pragma: no cover`). No fit's number moves, since both tiers are held
bit-identical to their numpy paths or to a stated bar. What is wrong is a
report about speed.

## Non-goals

The tiers' fallback behaviour (correct as it is: decline, never raise, one path
a process). The `RIETX_COMPILED` switch. Making a capability query build
anything.

## Tasks

- [ ] One reading per tier, e.g. `built()` → `True | False | None`: the latch
      each tier already keeps, exposed. `enabled()` stays the hot-path switch.
- [ ] `capabilities()` reports both tiers without compiling. Tests: a forced
      build failure in each tier (monkeypatch `_kernels_numba.build` to raise)
      reads `False` for that tier and leaves the other alone; a fresh process
      reads `None` before any build.
- [ ] `docs/manual/using/install.md` (which says the flag "is whether the next
      refinement will use it", and runs it in a python block); a
      release-note line.
- [ ] Skill: `references/diagnostics-indexing.md`'s speed-flag paragraph
      quotes `features["compiled_kernels_active"]`. Reword it, then re-sync
      the copies with `rietx skill --install . --copy`.

## Acceptance

After a failed build no flag reads active for that tier. Before any build no
flag claims one ran.

```sh
.venv/bin/python -m pytest tests/test_capabilities.py tests/test_compiled_kernels.py tests/test_indexing_kernels.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

WP-1115 (the model tier and its flags); WP-1508 (the indexing tier; the
declined review finding); WP-1007 (`capabilities()`); WP-1076 (a field's empty
state).

## Handover log

### 2026-10-10 — closed, superseded by WP-1940

PR #864 merged and did this WP's whole Goal, so nothing here is left to do.
numba left all three tiers. The indexing traversal lost its compiled path, so
the model tier is the only compiled one. Its build is the import of
`rietx-kernels`, so `compiled_kernels` and a build cannot disagree.
`compiled_kernels_active` now needs `available()` as well as the switch, and a
decline warns once a process and says why in
`Capabilities.compiled_kernels_unavailable`. The three inherited entries all
said to close or fold this WP once that PR landed, and are consumed. No task
here was started.

- **2026-09-28** — filed from WP-1508's review, where it was declined for a
  signal both tiers report.
