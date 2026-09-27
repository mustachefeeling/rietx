# WP-1456 — an editable install stamps what it runs

Milestone: unscheduled · Status: ✅ 2026-09-27 — a checkout whose `pyproject.version` has moved past its editable install stamps the source version and its git node, and warns; the run recorder stamps from the same authority
Track: What fires, and what stays silent
Depends on: —

## Goal

An editable install whose installed metadata disagrees with the source tree
stamps the source tree's version, or says it cannot. It never stamps the
older number in silence.

## Context

**The evidence.** An agent session on 2026-09-23 (`in-situ series 1` in the
private corpus map) used the main checkout's venv. The code there was
`644dff84`, whose `pyproject.version` is `1.6.0.dev0`. `rietx.__version__`
said `1.4.0`, because the editable install predated the version bumps since
1.4.0. Every result's `provenance.package_version` and every run's
`meta.json` say 1.4.0. The agent's report says 1.4.0 too. It names commit
`644dff84` beside it, but only because the agent recorded the commit by hand.
The results and run records carry no commit, so a reader holding only those
would install a release that does not contain the code that ran.

**The second instance, and this time no commit** (the 2026-09-25 review, folded
in from `### Inherited` on 2026-09-27). A second agent session used the same
venv, whose dist-info was still `rietx-1.4.0`, at `2d42303a`, whose
`pyproject.version` is `1.6.0.dev0`. Its report says "rietx 1.4.0 (local
checkout)" and "The run pinned rietx 1.4.0", and names no commit, so nothing
the reader holds identifies the code. All 887 run records it left in its
`.rietx/runs` carry 1.4.0 in `meta.json`.

**The mechanism.** `_VERSION = version(DIST_NAME)` (`src/rietx/refine.py:128-141`
at `ebc45b9`) reads the installed metadata. An editable install writes that
metadata once, at install time. The comment above it already names the stakes:
`_VERSION` reaches every result's provenance, every `TreeHeader` in every
`history.jsonl`, every `project.json` and `/api/capabilities`, "so a silent
fallback mislabels the provenance of real results". WP-1062 made the
*missing* distribution loud. A *stale* one is still silent.

**A second reader, superseded in part 2026-09-27.** The paragraph above names
one authority, and there are two. `runs._package_version()`
(`src/rietx/runs.py:1148`) asks `importlib.metadata` again for the `meta.json`
`version` field, so the 887 records were stamped by a lookup that never
reached `_VERSION`, and a fix there alone would have left every run record
stale. It also answers `None` where `_VERSION` answers `0.0.0+dev`, so the two
already disagreed on a missing distribution. `refine` imports `runs` at module
level, so the recorder reads `_VERSION` through a lazy import. The recorder
exists only inside a fit, where `refine` is already loaded.

The same trap is known on the maintainer's side, where a bump without a
reinstall once passed locally and failed every CI job. Here it put a wrong
number into a deliverable.

**Candidates.** When the package is imported from a source tree, read
`pyproject.toml` beside it and compare. On disagreement, either stamp the
source version with a local tag (`1.6.0.dev0+stale-install`) or warn once and
stamp the source version. Prior art to read first: how setuptools-scm and
hatch-vcs report an editable install's version, and whether either records
the commit.

**The prior art** (read 2026-09-27, from the sdists: setuptools-scm 10.3.4,
its engine vcs-versioning 2.5.0, hatch-vcs 0.5.0).

- Neither tool solves the staleness. Both write the version once, at build
  time. hatch-vcs says so in its README: "the version number in an editable
  install ... will be incorrect if the version changes and the project is not
  rebuilt". setuptools-scm 10's editable fix only makes the version *file*
  exist, and it is still written at install time.
- setuptools-scm does record the commit. Its default local scheme,
  `node-and-date` (`vcs_versioning/_modify_version._format_local_with_time`),
  renders `+{node}` off a tag and `+{node}.d{YYYYMMDD}` on a dirty tree. The
  node for git is `g<hash>`, and `dirty-tag` renders a dirty tree as
  `+dirty`.
- PEP 610's `direct_url.json` (`dir_info.editable`) says whether an install
  is editable, not whether it is stale. The comparison below is the only
  test that sees the staleness itself.

**The choice.** One resolver where `_VERSION` is set, three cases.

1. The package is not imported from a source tree, meaning the package does
   not sit in a directory named `src/` with a `pyproject.toml` beside it whose
   `[project].name` is `DIST_NAME`. Or it is, and `pyproject.version` equals
   the installed metadata, compared in PEP 440 normal form where `packaging`
   imports. Then the stamp is the metadata, byte for byte as before. This
   covers every wheel install and every fresh editable install, CI's
   included.
2. It disagrees. Then the stamp is the source version with the git node as a
   PEP 440 local label: `1.6.0.dev0+g<HEAD's 12-hex abbreviation>`, and `….dirty` when a
   tracked file differs from HEAD. That is setuptools-scm's node plus its
   `dirty-tag` word. The date adds nothing that `Provenance.created_utc` does
   not already carry. The warning fires once, at import, and names both
   versions and the reinstall. Git runs with every `GIT_*` variable stripped
   except the exec and ssh ones, which is setuptools-scm's `no_git_env` rule,
   and `status` runs without optional locks. HEAD's top level must be the
   tree itself.
3. It disagrees, and git cannot answer (no git, not a work tree, a timeout).
   Then the stamp is the bare source version, and the warning says the commit
   could not be read. That claim is exactly as strong as a fresh editable
   install's, which names no commit either.

The node is read only on the disagreeing path, so a matching install pays
nothing for it: two `git` calls there cost 1.9 ms and 3.6 ms (warm). The
missing-distribution case keeps WP-1062's `0.0.0+dev` and its warning. A
local label on the *matching* path would change the version scheme, a
non-goal, and `test_skill.py` pins the skill's `version` to
`rietx.__version__` on exactly that path.

## Non-goals

- Changing the version scheme or the release workflow (`docs/RELEASING.md`).

## Tasks

- [x] Read the prior art above, and write the choice here.
- [x] Implement the comparison where `_VERSION` is set, and nowhere else;
      the run recorder's `meta.json` reads `_VERSION` rather than asking
      `importlib.metadata` a second time (the second reader above).
- [x] Tests: a monkeypatched metadata version that disagrees with
      `pyproject.toml` stamps the chosen form. A matching one is unchanged.
- [x] Skill: none. An agent reads the stamp and never sets it.

## Acceptance

In a venv installed at one version and then bumped in source, a fit's
`provenance` names the source version, or the chosen marked form.

```sh
.venv/bin/python -m pytest tests/test_no_stale_name.py tests/test_capabilities.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1062 (the missing-distribution warning).

## Handover log

- **2026-09-27** — closed. A checkout whose version was bumped after its
  editable install no longer stamps the old number. Every result, history
  tree, project and run record now carries the version the source tree
  declares, plus the commit it was at (and `.dirty` if a tracked file was
  edited), and the import warns once, naming both versions. A reader holding
  only a result can now find the code that produced it, which the two agent
  sessions behind this WP could not. Installs whose metadata agrees, meaning
  every wheel and every fresh editable install (CI's included), are stamped
  byte for byte as before. The work also found that run records never read
  the stamp at all. They asked the metadata a second time, so fixing
  `_VERSION` alone would have left all 887 of that session's records wrong.

  *Done.* `refine._resolve_version` (and `_source_version`, `_source_node`,
  `_git_env`, `_same_version`) sets `_VERSION`. `runs._package_version` reads
  `_VERSION` through a late import, since `refine` imports `runs` at module
  level. Thirteen tests are in `tests/test_capabilities.py`. One of them is a
  meta-test that holds `refine.py` as the only module calling
  `version`/`metadata`/`distribution` on the distribution name. Also: the
  install chapter's sentence on `__version__` plus a Troubleshooting entry,
  a section in `releases/1.5.1.md`, and a paragraph in the v1.6 record. The
  WP file's Context and the choice were rewritten in place (prior art,
  second reader); `### Inherited`'s one entry, the second session's
  evidence, was still true and was folded into Context.

  *Review* (`/code-review high --fix`). It found nine things, five were
  applied and one of its fixes was corrected.
  - Applied: every `GIT_*` except exec/ssh is stripped, not a list of four,
    because `GIT_OBJECT_DIRECTORY` slipped the list. A package not under
    `src/` is never matched to a checkout's pyproject (`pip --target` into a
    checkout). The version comparison is in PEP 440 normal form where
    `packaging` imports. The dirty test now separates an untracked file from
    a tracked edit. The meta-test now also matches `metadata(` and
    `distribution(`.
  - Corrected: the review's regex added a leading `\b`, which stopped the
    meta-test matching an aliased `_dist_version(DIST_NAME)`, the case its
    docstring names. The `\b` is removed.
  - Declined:
    - Untracked files do not count as dirty. That was chosen, after
      setuptools-scm.
    - Two 10 s git timeouts can block import for up to 20 s, but only on the
      stale path, and only on a hung filesystem.
    - The review proposed moving the resolver to a leaf `_version.py`. The WP
      put it where `_VERSION` is set, and the late import is the one cost of
      that.

  *Measured.* All counts are from the `[dev]` venv (no jax or torch), Linux
  x86_64 in a cloud container, Python 3.12, 4 cores.
  - The fast selection at `4b6780d` (11 of the 13 tests present): 6436
    passed, 163 skipped and 2 failed, in one run of 19 min. Both failures
    are explained:
    - `test_portability`'s encoding rule caught the pyproject read. It was
      fixed in `b168948`.
    - `test_telemetry::…[unwritable-directory]` fails because the container
      runs as root, which `chmod 0o500` does not stop. It fails identically
      on main's code (run with `PYTHONPATH=<main checkout>/src`), so it is not
      this WP's. On a GitHub runner (non-root) it passes.
  - Commits after that run were checked module by module: `test_capabilities`,
    `test_no_stale_name`, `test_skill` and `test_portability` together gave
    148 passed. `test_manual` and `test_manual_api` passed after the install
    chapter edit.
  - Collection over the fast selection: 6595 on this branch against 6582 on
    main (`--collect-only`, same venv), a delta of 13, which is exactly the
    tests added. None is a new skip in this venv. The git rows would skip
    only where no `git` is on PATH.
  - End to end (a scratchpad script that rewrote this venv's dist-info
    `Version:` to 1.4.0 for one child process and then restored it): all five
    surfaces read `1.6.0.dev0+g<HEAD>`, namely `__version__`, capabilities,
    `provenance`, `meta.json` and the `TreeHeader`. That was `.dirty` while
    review fixes were uncommitted, and clean at a committed HEAD. The
    restored install read `1.6.0.dev0` on all five.
  - Git cost on the stale path: 1.9 ms and 3.6 ms, warm, best of five.

  *Gotchas.*
  - `rietx.refine` as an attribute is the *function*; the tests fetch the
    module with `importlib.import_module("rietx.refine")`.
  - `docs/manual/conf.py` still reads `release` from the metadata directly,
    so a stale venv building the manual prints the stale number. The pages
    workflow installs fresh, and the meta-test scans `src/rietx` only, so
    this was left.
  - The root-only telemetry failure has no owning WP. The fix is a
    `geteuid() == 0` skip beside the existing `os.name == "nt"` one.

  Next: nothing on this WP. If the manual's `release` string should follow
  the same authority, that is a one-line change in `conf.py` for whoever next
  touches the manual build.
- **2026-09-24** — created from the review of an agent session whose
  results stamped 1.4.0 while running 1.6.0.dev0 code. Checked against the
  tree at `2d42303a`. Next: the prior art.
