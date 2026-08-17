# Releasing rietx

How a version reaches PyPI. This file is the authority; WP-1003's checklist
describes the by-hand 1.0.0 upload and is history, not instructions.

**Never run `twine upload` by hand.** Publishing goes through
[`.github/workflows/release.yml`](../.github/workflows/release.yml), which
builds from the tag. The by-hand route was used once, for 1.0.1, and produced
both failures it can produce: artifacts built before three later commits
landed, so the tag had to be deleted and re-cut at the tree the files actually
came from; and no check that the tag and `pyproject.version` agree, which is
the one packaging mistake with no undo, because PyPI refuses a second upload of
a version number that has already been published.

## Cutting a release

1. Set `pyproject.version`. The convention is in
   [CLAUDE.md](../CLAUDE.md): the milestone in flight, or the last shipped when
   none is.
2. Write `docs/releases/X.Y.Z.md`. It becomes the GitHub release body verbatim,
   so it is written for a reader upgrading, not for a maintainer. The
   precedents are [1.0.0](releases/1.0.0.md), a milestone, and
   [1.0.1](releases/1.0.1.md), a patch that changed no source file.
3. Land both on `main` and let CI go green. Branch protection requires six
   checks (`lint`, `fast py3.11`–`py3.14`, `fast jax`), so a commit on `main`
   has already passed them, and the workflow refuses a tag that is not on
   `main` for exactly that reason.
4. Check that the nightly's Windows job is green on that commit
   (`gh run list --workflow nightly.yml`). This is the pre-upload gate WP-1003
   established: the OS classifiers claim Windows, and the claim ships only
   verified. No workflow can wait the ~2 h this takes, so it is asserted by a
   person at step 6.
5. Tag `vX.Y.Z` and publish the GitHub release from the notes file:
   `gh release create vX.Y.Z --title "rietx X.Y.Z" --notes-file docs/releases/X.Y.Z.md --verify-tag`.
   Publishing the release is what triggers the workflow.
6. Approve the `pypi` deployment when the run pauses. That approval is where
   steps 3 and 4 are asserted by a human, and it is the only manual step in the
   publish path.
7. Verify from the index, in a fresh venv, not from the build directory:

   ```sh
   uv venv --python 3.12 /tmp/smoke
   VIRTUAL_ENV=/tmp/smoke uv pip install --refresh "rietx==X.Y.Z"
   /tmp/smoke/bin/python -c "import rietx as rx; print(rx.capabilities().schema_version)"
   ```

   `--refresh` matters: uv's index cache will otherwise report the version as
   nonexistent for a while after upload. Check three things beyond the import,
   because each has failed before: `capabilities()` answers, the bundled
   `rietx/data/AGENT_PROTOCOL.md` resolves, and `rietx.gui.textdoc` imports
   with its static dist present. The last of those caught an sdist exclude that
   had silently dropped the GUI's Python modules from every wheel.

## Trusted publishing

No API token exists anywhere, and nothing needs rotating after an upload.
GitHub mints a short-lived OIDC token for the `publish` job, PyPI checks it
against a publisher it was told to trust, and returns a credential good for
that one upload. The published files carry PEP 740 attestations as a
side effect.

PyPI matches four claims exactly, configured at pypi.org → `rietx` → Manage →
Publishing:

| Claim | Value |
|---|---|
| Owner | `yue-here` |
| Repository | `rietx` |
| Workflow name | `release.yml` |
| Environment | `pypi` |

Two consequences. **Renaming the workflow file breaks the match**, and the
PyPI side has to be renamed with it. And **no API reads a project's configured
publishers back**, so the only way to check the setup is to exercise it:
`gh workflow run release.yml --ref main` runs the build and the `verify-trust`
job, which exchanges a token at `pypi.org/_/oidc/mint-token` and prints the
status code. 200 means every claim matched; 422 means it did not. A dispatch
run cannot publish, and it never uses the credential it mints. Run it after any
change to the publisher config, the `pypi` environment, or this workflow's
name. Last confirmed working 2026-08-17.

The `pypi` environment carries `yue-here` as a required reviewer, which is what
makes step 6 a real gate rather than a formality.

## What lives where

- The workflow's own header explains each guard and why the `publish` job is
  the only one holding `id-token: write`.
- `docs/releases/X.Y.Z.md` is the per-release record and the release body.
- `docs/milestones/vX.Y.md` is the measured record of a *milestone*, which is a
  different document: acceptance numbers, not upgrade notes. A patch release
  has notes and no milestone record.
