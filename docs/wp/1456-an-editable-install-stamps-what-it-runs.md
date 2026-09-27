# WP-1456 — an editable install stamps what it runs

Milestone: unscheduled · Status: 🔄 2026-09-27 — claimed by @yue-here
Depends on: —
Priority: P2 2026-09-25 — was P3: a second session's deliverable quoted the stale version with no commit beside it, so nothing a reader holds names the code; reinstalling is the workaround

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

1. The package is not imported from a source tree, meaning no `pyproject.toml`
   whose `[project].name` is `DIST_NAME` sits beside `src/`. Or it is, and
   `pyproject.version` equals the installed metadata. Then the stamp is the
   metadata, byte for byte as before. This covers every wheel install and
   every fresh editable install, CI's included.
2. It disagrees. Then the stamp is the source version with the git node as a
   PEP 440 local label: `1.6.0.dev0+g<HEAD's 12-hex abbreviation>`, and `….dirty` when a
   tracked file differs from HEAD. That is setuptools-scm's node plus its
   `dirty-tag` word. The date adds nothing that `Provenance.created_utc` does
   not already carry. The warning fires once, at import, and names both
   versions and the reinstall.
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
- [ ] Implement the comparison where `_VERSION` is set, and nowhere else;
      the run recorder's `meta.json` reads `_VERSION` rather than asking
      `importlib.metadata` a second time (the second reader above).
- [ ] Tests: a monkeypatched metadata version that disagrees with
      `pyproject.toml` stamps the chosen form. A matching one is unchanged.
- [ ] Skill: none. An agent reads the stamp and never sets it.

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

- **2026-09-24** — created from the review of an agent session whose
  results stamped 1.4.0 while running 1.6.0.dev0 code. Checked against the
  tree at `2d42303a`. Next: the prior art.
