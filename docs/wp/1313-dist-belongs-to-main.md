# WP-1313 — the GUI dist belongs to main

Milestone: unscheduled · Status: ⬜
Depends on: — (the branch-protection toggles are the maintainer's to flip by hand)

## Goal

`src/rietx/gui/static` is fresh on `main` and only on `main`: a post-merge
workflow rebuilds and commits it there, the PR-side `build, diff, test` check
turns advisory (still reporting whether the bundle changed), and concurrent
GUI branches stop conflicting on bundler output. Releases are unaffected —
the wheel builds from a tag on main.

## Context

This is the deferred half of the maintainer's own ruling on issue #159:
"the interim lands now, the larger change is deferred. … The larger change —
dist as main's artifact, post-merge rebuild, PR check advisory — is not being
taken up in this pass. **It needs a WP**: it puts a workflow with write
access on a protected `main`, and the branch-protection settings are the
maintainer's to change by hand."

**Why the dist is committed at all** rules out "don't commit build output":
`pyproject.toml` ships `src/rietx/gui/static` inside the wheel, so
`pip install rietx` gives a working GUI with no node toolchain.

**The measured cost.** PR #118 paid four review round-trips to the same two
files (`assets/app.js`, `build-info.json`) with nothing in its code half
changing. Any two branches touching `gui/src/**` conflict by construction,
and the cost scales with the square of concurrent GUI work — v1.2's GUI
milestone had five PRs each invalidating every open GUI branch.

**Where the risk actually sits** (the maintainer's measurement, which
strengthened the case): `build-info.json` is six lines, so two edits share a
hunk and git conflicts loudly — that is *not* the dangerous case. The
dangerous case is `assets/app.js`, where two branches editing different
regions **auto-merge with no conflict at all** (measured with edits 115
lines apart in the 131-line, 280 kB bundle — both present in the result).
The failure mode is the pair together: the hash conflicts and is resolved by
taking a side, while the bundle beside it has already been spliced from two
builds — a dist that satisfies the freshness gate and corresponds to no
tree. The merged `.gitattributes` interim (`-merge -diff`, issue #163)
does not cover the silent case. The change also makes the guarantee
*stronger*: today each branch's dist is the build of that branch in
isolation, and merge order decides which bundle lands.

**The design, as ruled:** a post-merge job on main runs
`npm --prefix gui ci && npm --prefix gui run build` and commits any
difference; the PR check keeps building and diffing but reports instead of
failing; branches carry their `gui/src/**` changes and not the bundle. The
one hard part is the write path onto protected main — a workflow token (or
app) allowed to push, which interacts with the protection rules only the
maintainer can edit. The WP's deliverable therefore includes a short written
instruction for the by-hand half, not an automation of it.

## Non-goals

- **Not the `.gitattributes` interim** — merged (issue #163); it stays until
  this lands and is removed by this WP when it does.
- **Not touching how the wheel is built** — `docs/RELEASING.md`'s rule
  stands: the workflow builds from the tag; nothing here changes a release
  artefact.
- **Not GUI code or `gui/CLAUDE.md`'s session rules beyond the freshness
  clause** — one rule moves (freshness is main's obligation, not the
  branch's); nothing else.

## Tasks

- [ ] The post-merge workflow: rebuild, diff, commit-if-changed on main;
      idempotent, and a no-op commit is never created.
- [ ] The PR check turns advisory: still builds, still reports "bundle
      would change: yes/no", never blocks; the useful signal survives.
- [ ] Remove the interim `.gitattributes` entry; `gui/CLAUDE.md` and the
      Commands block's rebuild line updated to say whose obligation
      freshness now is.
- [ ] The by-hand instruction: exactly which branch-protection settings the
      maintainer must change, written next to the workflow file; land the
      workflow disabled-or-inert until that is done.
- [ ] Tests where they can exist (workflow lint/dry-run; the check's
      advisory output asserted in CI config review) + a full local
      `npm --prefix gui ci && npm --prefix gui run build` proving the
      committed dist reproduces.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build && git diff --exit-code src/rietx/gui/static
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The bar: after a merge to main touching `gui/src/**`, main's dist is the
build of main's tree (not of any branch's), the PR check reports without
blocking, and two concurrent GUI branches merge with no conflict in
`src/rietx/gui/static`.

The shipping PR carries `Closes #159`.

## References

- Issue #159 — the proposal, the maintainer's ruling, and both measurements
  (the four round-trips; the silent `app.js` auto-merge).
- Issue #163 (merged) — the interim this replaces.
- `docs/RELEASING.md` — why the wheel path is untouched.

## Handover log

- **2026-09-01** — created, from issue #159 (2026-09-01 triage; the ruling
  that deferred it is quoted in Context). Settled: the design as ruled;
  first open item is the write-path mechanism onto protected main, which
  decides how the by-hand instruction reads.
