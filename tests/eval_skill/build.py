"""Build a `claude plugin eval` plugin from a skill tree and this suite's cases.

    python tests/eval_skill/build.py <tree> <out> [--body FILE] [--python PATH]
                                     [--case GLOB ...]

WP-1905; `PROTOCOL.md` is the registration this instrument serves.

**The condition is the tree handed to `build`, never the prompt.** The skill
tree is not a plugin and must not become one (a manifest inside
`.claude/skills/rietx/` would change how every session here loads the skill), so
each round builds a throwaway plugin: the tree copied to
``<out>/skills/rietx/``, a ``.claude-plugin/plugin.json``, and the cases under
``<out>/evals/``. Two bodies are two builds and two runs of one suite. `--body`
swaps ``SKILL.md`` in the copied tree, which is how a rewrite's body is measured
against today's references without a second tree on disk. ``build.json`` beside
the manifest records what went in (the tree, the body's sha256, the
interpreter, the commit), because a result file says nothing about it.

**A case is a directory holding ``prompt.md``**, under ``cases/``, nested under
a plain directory to group (``cases/trigger/``). Two things in it are
instructions to this script rather than files the harness reads:

- ``@PYTHON@`` in ``prompt.md`` becomes the interpreter rietx is installed for
  (`--python`; default this checkout's ``.venv``). Run under Bash, the
  harness's sandbox hides the home directory, so an interpreter under it cannot
  start, and `build` says so rather than letting every fit fail in the run.
- ``inputs.txt`` lists what the run's workspace starts with, one per line:
  ``copy <repo path> [as <name>]``, or ``episode <name>`` for a generated set
  (`EPISODES`). `build` stages them into the case's ``files/`` and writes the
  ``fixture.sh`` and ``case.yaml`` that copy them in under ``--scaffold``. The
  scaffold runs with no variable naming the case, so the path is written in
  absolute at build time, which is why a build is not portable between machines.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shlex
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

CASES = HERE / "cases"
PLUGIN_NAME = "rietx-skill-eval"
PYTHON_MARK = "@PYTHON@"
INPUTS = "inputs.txt"
#: What `build` writes into every built case with inputs; a committed case
#: carrying one would be overwritten, so `cases()` refuses it.
GENERATED = ("fixture.sh", "case.yaml", "files")
#: Written into every build; its presence is what lets `build` clear `<out>`.
STAMP = "build.json"
#: The first words of every case's `description`: what its score is evidence
#: of (PROTOCOL.md § Cases). A regression guard is one today's body passes and
#: no skill fails; a deciding case is one today's body fails, the case a
#: rewrite is judged on; the last two are tier 0's triggering prompts.
ROLES = ("Regression guard.", "Deciding case.", "Should fire.", "Should not fire.")


def _placement(dest: Path, python: Path) -> None:
    from tests.eval_skill_placement import runner

    runner.build_episode(dest, python)


#: Generated workspaces, built once per build and copied into each case naming
#: them: `placement` is the skill-placement round's episode (WP-1338), the two
#: FAP files, the colleague's `fit.py` and what it printed.
EPISODES: dict[str, Callable[[Path, Path], None]] = {"placement": _placement}


def default_python() -> Path:
    venv = REPO / ".venv" / "bin" / "python"
    return venv if venv.exists() else Path(sys.executable)


def cases(root: Path = CASES) -> list[Path]:
    """Every case directory under ``root``, in path order."""
    found = sorted(p.parent for p in root.rglob("prompt.md"))
    for case in found:
        clash = [g for g in GENERATED if (case / g).exists()]
        if clash:
            raise ValueError(f"{case}: {clash} are written by build, never committed")
    return found


def parse_inputs(text: str) -> list[tuple[str, str, str]]:
    """``inputs.txt`` as ``(verb, source, name)`` rows; raises naming the line."""
    rows = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        words = line.split()
        if words[0] == "copy" and len(words) in (2, 4) and (len(words) == 2 or words[2] == "as"):
            rows.append(("copy", words[1], words[3] if len(words) == 4 else Path(words[1]).name))
        elif words[0] == "episode" and len(words) == 2:
            if words[1] not in EPISODES:
                raise ValueError(f"line {n}: no episode {words[1]!r} (have {sorted(EPISODES)})")
            rows.append(("episode", words[1], ""))
        else:
            raise ValueError(f"line {n}: expected `copy <path> [as <name>]` "
                             f"or `episode <name>`, got {raw!r}")
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_sha256(tree: Path) -> str:
    """One hash over every file's relative path and bytes, so two trees that
    share a body and differ in a reference are told apart."""
    h = hashlib.sha256()
    for f in sorted(p for p in tree.rglob("*") if p.is_file()):
        h.update(f.relative_to(tree).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def _commit() -> str | None:
    proc = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _clear(out: Path) -> None:
    if not out.exists():
        return
    if not (out / STAMP).is_file():
        raise SystemExit(f"{out} exists and holds no {STAMP}: not a build of this "
                         "script, so it is left alone")
    shutil.rmtree(out)


def _stage(case: Path, files: Path, python: Path, out: Path) -> None:
    files.mkdir(parents=True)
    for verb, source, name in parse_inputs((case / INPUTS).read_text(encoding="utf-8")):
        if verb == "copy":
            src = REPO / source
            if not src.is_file():
                raise SystemExit(f"{case / INPUTS}: no file {source}")
            shutil.copyfile(src, files / name)
        else:
            built = out / "episodes" / source
            if not built.exists():
                EPISODES[source](built, python)
            shutil.copytree(built, files, dirs_exist_ok=True)


def _scaffold(built: Path, name: str) -> None:
    fixture = built / "fixture.sh"
    fixture.write_text("#!/bin/bash\nset -e\ncp -R "
                       f"{shlex.quote(str(built / 'files'))}/. .\n", encoding="utf-8")
    fixture.chmod(0o755)
    (built / "case.yaml").write_text(
        f'schema_version: "1.1"\nname: {json.dumps(name)}\ncontext:\n  scaffold_script: fixture.sh\n',
        encoding="utf-8")


def build(tree: Path, out: Path, *, python: Path | None = None,
          body: Path | None = None, only: list[str] | None = None) -> dict:
    """Write the plugin to ``out`` and return what `STAMP` records."""
    tree, out = Path(tree).resolve(), Path(out).resolve()
    # Absolute, never resolved: a relative path names nothing in the run's
    # workspace or the episode's cwd, and resolving a venv's symlink would
    # name the base interpreter, which has no rietx.
    python = Path(python).absolute() if python else default_python()
    body = Path(body).absolute() if body is not None else None
    if not (tree / "SKILL.md").is_file():
        raise SystemExit(f"{tree} holds no SKILL.md: not a skill tree")
    if Path.home() in python.parents or Path.home() in python.resolve().parents:
        print(f"warning: {python} is under {Path.home()}, which the eval sandbox "
              "hides; Bash in a run cannot start it (pass --python)", file=sys.stderr)
    _clear(out)

    skill = out / "skills" / "rietx"
    shutil.copytree(tree, skill, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    if body is not None:
        shutil.copyfile(body, skill / "SKILL.md")
    (out / ".claude-plugin").mkdir()
    (out / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": PLUGIN_NAME, "version": "0.0.0",
        "description": "the rietx agent skill under evaluation (WP-1905)"}, indent=1) + "\n")

    chosen = []
    for case in cases():
        rel = case.relative_to(CASES)
        if only and not any(fnmatch.fnmatch(case.name, g) for g in only):
            continue
        built = out / "evals" / rel
        shutil.copytree(case, built, ignore=shutil.ignore_patterns(INPUTS, "__pycache__"))
        prompt = built / "prompt.md"
        prompt.write_text(prompt.read_text(encoding="utf-8").replace(PYTHON_MARK, str(python)),
                          encoding="utf-8")
        if (case / INPUTS).exists():
            _stage(case, built / "files", python, out)
            _scaffold(built, case.name)
        chosen.append(str(rel))

    stamp = {"tree": str(tree), "body": str(body) if body else None,
             "skill_sha256": _sha256(skill / "SKILL.md"),
             "tree_sha256": tree_sha256(skill), "python": str(python),
             "commit": _commit(), "built": date.today().isoformat(), "cases": chosen}
    (out / STAMP).write_text(json.dumps(stamp, indent=1) + "\n", encoding="utf-8")
    return stamp


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tree", type=Path, help="the skill tree, e.g. docs/skill/rietx")
    ap.add_argument("out", type=Path, help="the plugin directory to write")
    ap.add_argument("--body", type=Path, help="a SKILL.md to put in the copied tree")
    ap.add_argument("--python", type=Path, help="the interpreter rietx is installed for")
    ap.add_argument("--case", action="append", help="build only cases matching this glob")
    args = ap.parse_args(argv)
    stamp = build(args.tree, args.out, python=args.python, body=args.body, only=args.case)
    print(f"{args.out}: {len(stamp['cases'])} cases, SKILL.md {stamp['skill_sha256'][:12]}, "
          f"python {stamp['python']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
