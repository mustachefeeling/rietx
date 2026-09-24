# WP-1456 — an editable install stamps what it runs

Milestone: unscheduled · Status: ⬜
Depends on: —
Priority: P3 2026-09-24 — a result's version stamp can name a release two milestones older than the code that produced it; reinstalling is the workaround

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

**The mechanism.** `_VERSION = version(DIST_NAME)` (`src/rietx/refine.py:121-134`)
reads the installed metadata. An editable install writes that metadata once,
at install time. The comment above it already names the stakes: `_VERSION`
reaches every result's provenance, every `TreeHeader` in every
`history.jsonl`, every `project.json` and `/api/capabilities`, "so a silent
fallback mislabels the provenance of real results". WP-1062 made the
*missing* distribution loud. A *stale* one is still silent.

The same trap is known on the maintainer's side, where a bump without a
reinstall once passed locally and failed every CI job. Here it put a wrong
number into a deliverable.

**Candidates.** When the package is imported from a source tree, read
`pyproject.toml` beside it and compare. On disagreement, either stamp the
source version with a local tag (`1.6.0.dev0+stale-install`) or warn once and
stamp the source version. Prior art to read first: how setuptools-scm and
hatch-vcs report an editable install's version, and whether either records
the commit.

## Non-goals

- Changing the version scheme or the release workflow (`docs/RELEASING.md`).

## Tasks

- [ ] Read the prior art above, and write the choice here.
- [ ] Implement the comparison where `_VERSION` is set, and nowhere else.
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
