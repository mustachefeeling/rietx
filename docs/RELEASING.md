# Releasing rietx

How a version reaches PyPI. This file is the authority; WP-1003's checklist
describes the by-hand 1.0.0 upload and is history, not instructions. The
kernel wheel, a second distribution, has its own section below.

**Never run `twine upload` by hand.** Publishing goes through
[`.github/workflows/release.yml`](../.github/workflows/release.yml), which
builds from the tag. The by-hand route was used once, for 1.0.1, and produced
both failures it can produce: artifacts built before three later commits
landed, so the tag had to be deleted and re-cut at the tree the files actually
came from; and no check that the tag and `pyproject.version` agree, which is
the one packaging mistake with no undo, because PyPI refuses a second upload of
a version number that has already been published.

## When

A release is cut once a week, and at once when a P1 fix lands (WP-1540). A P1
fix here is the defect half of the rubric's top tier in `docs/wp/TEMPLATE.md`:
a silent wrong answer in a shipped path, or data loss. A P1 that was a red
check or a finishing rung waits for the week. The cut carries whatever `main`
holds, and a milestone that is not finished waits for the next one.

The weekly cut is cheap to forget, so it is not left to memory. The
session-start hook prints `release owed` once the newest `v*` tag is seven days
old and `main` has merged anything since. A P1 fix has no date to read, so
`/wp-handover` says a release is owed when the WP it closes was P1.

The interval follows the measured rate. Before WP-1540 every release carried
14 to 77 merges and 210 to 301 lines of notes. By early October 2026, 80 to 177
PRs merged in a week. A fortnightly cut would carry about 1 200 lines of notes,
which is the backlog this rule exists to prevent.

## Cutting a release

1. Set `pyproject.version`. The convention is in
   [CLAUDE.md](../CLAUDE.md) and ROADMAP protocol rule 6: a release is numbered
   at its cut (WP-1540). **Three things follow it and none is automatic.** Reinstall
   (`uv pip install -e ".[dev]"`), because `rietx.__version__` is
   `importlib.metadata.version()` and reads the dist-info written at install
   time — until you do, every number the suite measures is stamped with the old
   version. Then set `metadata.version` in `docs/skill/rietx/SKILL.md` to match
   and re-sync the two committed copies with `rietx skill --install . --copy`;
   `test_metadata_values_are_strings_and_the_version_is_the_packages` fails
   until both are done, and it fails *after* the reinstall rather than before,
   which is the order that hides it. Last, rebuild the tutorial notebooks with
   `python examples/tutorials/build.py` and commit them, so the tagged tree's
   outputs come from the release itself (WP-1545). Their version stamp is
   checked to major.minor only, so nothing fails at the cut; the move to the
   next minor's `.dev0` fails `tests/test_tutorials.py` until they are rebuilt.
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
5. Tag `vX.Y.Z` and publish the GitHub release from the notes file. This reads
   as one command and is three, because `--verify-tag` requires the tag to
   already be on the remote:

   ```sh
   git tag vX.Y.Z                 # on the `main` commit from step 3
   git push origin vX.Y.Z
   gh release create vX.Y.Z --title "rietx X.Y.Z" \
     --notes-file docs/releases/X.Y.Z.md --verify-tag
   ```

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
   `rietx skill --path` resolves into the wheel, and `rietx.gui.textdoc` imports
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

## The kernel wheel

rietx's compiled model kernels are a second distribution, `rietx-kernels`,
built from `kernels/` (WP-1940). It has its own version and its own workflow,
[`.github/workflows/kernels.yml`](../.github/workflows/kernels.yml). It releases
only when the kernels change. The weekly rietx cut does not touch it.

Its major version is the kernel interface number, `rietx_kernels.KERNEL_ABI`,
and rietx pins that major version. Bump the major for any change to an
existing kernel's name, arguments or output planes, and move rietx's pin in
the same pull request. Bump the minor for anything else: a new kernel, or a
change of arithmetic. When rietx starts calling a new kernel, raise the pin's
floor to the minor that added it, because an older wheel of the same major
lacks it.

1. Set `version` in `kernels/Cargo.toml`. A build updates `kernels/Cargo.lock`
   to match. Commit both.
2. Land it on `main` through a pull request. `kernels.yml` builds the five
   platform wheels and tests each on its own platform, so the pull request
   shows them green before anything is tagged.
3. Tag the `main` commit and push the tag. Create no GitHub release:
   `release.yml` publishes rietx on every published release.

   ```sh
   git tag kernels-vX.Y.Z         # on the `main` commit from step 2
   git push origin kernels-vX.Y.Z
   ```

4. Approve the `pypi` deployment when the run pauses. The job refuses a tag
   that is not on `main`, or one that disagrees with `kernels/Cargo.toml`.
5. Verify from the index, in a fresh venv:

   ```sh
   uv venv --python 3.12 /tmp/kernels-smoke
   VIRTUAL_ENV=/tmp/kernels-smoke uv pip install --refresh "rietx-kernels==X.Y.Z"
   /tmp/kernels-smoke/bin/python -c "import rietx_kernels as k; print(k.__version__, k.KERNEL_ABI)"
   ```

The trusted publisher matches the same four claims as rietx's, with
`kernels.yml` as the workflow name. Before the first upload the project does
not exist on PyPI, so it is a *pending* publisher, added at pypi.org →
Account settings → Publishing. `gh workflow run kernels.yml --ref main`
checks it the way the dispatch run checks rietx's.

## What lives where

- The workflow's own header explains each guard and why the `publish` job is
  the only one holding `id-token: write`.
- `docs/releases/X.Y.Z.md` is the per-release record and the release body.
- `docs/milestones/vX.Y.md` is the measured record of a minor release, and
  `docs/milestones/<name>.md` that of a named milestone (WP-1540). Both are a
  different document: acceptance numbers, not upgrade notes. A patch release
  has notes and no record of either kind.
