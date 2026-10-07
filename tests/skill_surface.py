"""The skill rows a change should re-read: its public surface crossed against the skill (WP-1907).

    python -m tests.skill_surface       # the report, against this change's base

**Why at review.**  A session that renames a public name rarely re-reads the
skill text quoting it, and the skill (`docs/skill/rietx/`) is what an agent
driving rietx reads instead of the code.  So CI's lint job prints, for each
name a pull request touches, the skill rows that mention it.  The author reads
those rows while the change is still theirs.

**Four vocabularies**, each read from source *text* by AST, so the base
revision is read with `git show` and never imported:

- public names: the `__all__` literal in `src/rietx/__init__.py`, plus every
  top-level public class in `src/rietx/schemas/`, which `__init__` adds to
  `__all__` at import (`_schema_classes`);
- plan names: the keys of `PLAN_PRESETS` in `strategy/staged.py`;
- diagnostic codes: every UPPER_SNAKE ``code="..."`` keyword literal outside
  `gui/` (`test_docs_consistency._engine_codes` reads the same walk);
- help keys: the keys of every module-level ``*_HELP`` dict in `help.py`, some
  of them fnmatch globs over dot-paths.

**Touched** means added, removed, or present as a whole token on a changed
(+/-) line of ``git diff <base> -- 'src/rietx/*.py'``.  **Mentioned** means a whole token on
a skill row.  A name spelled like an English word, letters with at most a
leading capital (`seed`, `scan`, `Phase`, `Structure`), counts only in code:
inside a backtick span or a fenced block, since prose uses those words too.  A help
glob also matches a backticked dot-path it fnmatches (`phases.0.cell.a` for
`phases.*.cell.*`).  The generated `api*.md` files are not read: one is
rewritten from the package, and `test_skill` holds it to that.

**It fails on one thing**: a removed name the skill still mentions, because
an agent following that row calls something that is gone.  Every other touch
is a report.  A glob the change removed is excused on a dot-path that a
surviving help key still covers.

Stdlib only, like `skill_caps`, whose base revision and git helpers it reuses
(`RIETX_CAPS_BASE` overrides the base for both).
"""

from __future__ import annotations

import ast
import os
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fnmatch import fnmatchcase
from functools import lru_cache
from typing import NamedTuple

from tests.skill_caps import ROOT, SKILL_DIR, _git, base, rev_exists

PUBLIC, PLAN, CODE, HELP = "public name", "plan", "diagnostic code", "help key"
INIT = "src/rietx/__init__.py"
SCHEMAS = "src/rietx/schemas/"
STAGED = "src/rietx/strategy/staged.py"
HELP_MODULE = "src/rietx/help.py"
#: Characters of a row printed in the report before it is cut.
ROW_CHARS = 140

_CODE_SHAPE = re.compile(r"[A-Z][A-Z0-9_]+")
_WORD_LIKE = re.compile(r"[A-Za-z][a-z0-9]*")
_BACKTICKED = re.compile(r"`([^`]+)`")
_DOT_PATH = re.compile(r"[A-Za-z_][\w*?]*(?:\.[\w*?]+)+")

Vocabulary = dict[str, frozenset[str]]        # name -> the kinds it is


class SkillRow(NamedTuple):
    file: str          # repo-relative
    line: int          # 1-based
    text: str
    code: bool = False  # inside a fenced block


# -- vocabularies, from source text --------------------------------------

def is_engine_source(rel: str) -> bool:
    """A file whose ``code="..."`` literals are diagnostic codes.

    ``gui/`` is excluded on purpose: the GUI server's session codes
    (NOT_FOUND, RUN_IN_FLIGHT, ...) share the shape but are a separate
    namespace with no skill rows (§7's namespace note,
    `references/diagnostics.md`)."""
    parts = rel.split("/")
    return (rel.startswith("src/rietx/") and rel.endswith(".py")
            and "gui" not in parts[2:])


def diagnostic_codes(tree: ast.AST) -> set[str]:
    """Every UPPER_SNAKE ``code="..."`` keyword literal in ``tree``.  The
    lowercase ``GateFailure`` codes fall out of the shape filter."""
    codes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if (kw.arg == "code" and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                        and _CODE_SHAPE.fullmatch(kw.value.value)):
                    codes.add(kw.value.value)
    return codes


def _module_assignments(tree: ast.Module) -> Iterable[tuple[str, ast.expr]]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and node.value is not None:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield target.id, node.value
        elif (isinstance(node, ast.AnnAssign) and node.value is not None
                and isinstance(node.target, ast.Name)):
            yield node.target.id, node.value


def _strings(nodes: Iterable[ast.expr | None]) -> set[str]:
    return {n.value for n in nodes
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def file_vocabulary(rel: str, text: str) -> dict[str, set[str]]:
    """The names one file contributes, by kind."""
    tree = ast.parse(text, filename=rel)
    out: dict[str, set[str]] = {PUBLIC: set(), PLAN: set(), CODE: set(), HELP: set()}
    for name, value in _module_assignments(tree):
        if rel == INIT and name == "__all__" and isinstance(value, ast.List | ast.Tuple):
            out[PUBLIC] |= _strings(value.elts)
        elif rel == STAGED and name == "PLAN_PRESETS":
            for node in ast.walk(value):
                if isinstance(node, ast.Dict):
                    out[PLAN] |= _strings(node.keys)
        elif rel == HELP_MODULE and name.endswith("_HELP") and isinstance(value, ast.Dict):
            out[HELP] |= _strings(value.keys)
    if rel.startswith(SCHEMAS):
        out[PUBLIC] |= {n.name for n in tree.body
                        if isinstance(n, ast.ClassDef) and not n.name.startswith("_")}
    if is_engine_source(rel):
        out[CODE] = diagnostic_codes(tree)
    return out


def vocabulary(texts: Mapping[str, str]) -> Vocabulary:
    """Every name the files ``{repo-relative path: text}`` define, with its kinds."""
    kinds: dict[str, set[str]] = {}
    for rel, text in texts.items():
        for kind, names in file_vocabulary(rel, text).items():
            for name in names:
                kinds.setdefault(name, set()).add(kind)
    return {name: frozenset(k) for name, k in kinds.items()}


# -- matching ------------------------------------------------------------

@lru_cache(maxsize=None)
def _token(name: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")


def _is_glob(name: str) -> bool:
    return any(c in name for c in "*?[")


def changed_lines(diff: str) -> list[str]:
    """The added and removed lines of a unified diff, markers stripped."""
    return [line[1:] for line in diff.splitlines()
            if line[:1] in "+-" and not line.startswith(("+++", "---"))]


def mentions(name: str, row: SkillRow, *, glob: bool = False,
             survivors: Iterable[str] = ()) -> bool:
    """Whether a skill row names ``name``.

    ``glob`` (a help key) also accepts a dot-path in code that the key
    fnmatches, unless one of ``survivors`` matches it too."""
    spans = [row.text] if row.code else _BACKTICKED.findall(row.text)
    hay = spans if _WORD_LIKE.fullmatch(name) else [row.text]
    if any(_token(name).search(h) for h in hay):
        return True
    if glob and _is_glob(name):
        return any(fnmatchcase(path, name)
                   and not any(fnmatchcase(path, s) for s in survivors)
                   for span in spans for path in _DOT_PATH.findall(span))
    return False


# -- the report ----------------------------------------------------------

@dataclass(frozen=True)
class Touch:
    name: str
    kinds: frozenset[str]
    why: str                     # "removed" | "added" | "on a changed line"
    rows: tuple[SkillRow, ...]   # the skill rows that mention it

    @property
    def fails(self) -> bool:
        return self.why == "removed" and bool(self.rows)


_ORDER = {"removed": 0, "added": 1, "on a changed line": 2}


def touches(before: Vocabulary, after: Vocabulary, changed: Iterable[str],
            rows: Iterable[SkillRow]) -> list[Touch]:
    """Every name the change touched, with the skill rows naming it."""
    joined = "\n".join(changed)
    rows = list(rows)
    surviving_help = [n for n, k in after.items() if HELP in k and _is_glob(n)]
    out = []
    for name in before.keys() | after.keys():
        kinds = before.get(name, frozenset()) | after.get(name, frozenset())
        if name not in after:
            why = "removed"
        elif name not in before:
            why = "added"
        elif _token(name).search(joined):
            why = "on a changed line"
        else:
            continue
        survivors = surviving_help if why == "removed" else ()
        hits = tuple(r for r in rows if mentions(
            name, r, glob=HELP in kinds, survivors=survivors))
        out.append(Touch(name, kinds, why, hits))
    return sorted(out, key=lambda t: (_ORDER[t.why], t.name))


def _cut(text: str) -> str:
    text = text.strip()
    return text if len(text) <= ROW_CHARS else text[:ROW_CHARS - 1] + "…"


def _kinds(t: Touch) -> str:
    return ", ".join(sorted(t.kinds))


def report(found: list[Touch], how: str, *, markdown: bool = False) -> str:
    """The rows to re-read, grouped by name; names with none on one line."""
    code = (lambda s: f"`{s}`") if markdown else (lambda s: s)
    head = "**Skill surface**" if markdown else "Skill surface"
    with_rows = [t for t in found if t.rows]
    lines = [f"{head}, measured against {how}: {len(found)} names touched, "
             f"{len(with_rows)} named in the skill."]
    for t in with_rows:
        verdict = " (FAILS: removed, still in the skill)" if t.fails else ""
        lines += ["", f"{code(t.name)} ({_kinds(t)}), {t.why}{verdict}:"]
        for rel, n, text, _ in t.rows:
            row = f"{rel.removeprefix('docs/skill/rietx/')}:{n}"
            lines.append(f"- {code(row)} {_cut(text)}" if markdown
                         else f"  {row}: {_cut(text)}")
    quiet = [t for t in found if not t.rows]
    if quiet:
        lines += ["", "Touched, and named nowhere in the skill: "
                  + ", ".join(f"{code(t.name)} ({t.why})" for t in quiet)]
    return "\n".join(lines)


def failures(found: list[Touch]) -> list[str]:
    return [f"{t.name} ({_kinds(t)}) was removed from src/ and the skill still "
            f"names it at {', '.join(f'{r[0]}:{r[1]}' for r in t.rows)}. "
            "Rewrite those rows for what replaced it, or delete them"
            for t in found if t.fails]


# -- the tree and the base (impure) --------------------------------------

def skill_rows() -> list[SkillRow]:
    """Every line of the skill tree's authored files."""
    out = []
    for path in sorted(SKILL_DIR.rglob("*.md")):
        if path.name.startswith("api"):
            continue
        rel = path.relative_to(ROOT).as_posix()
        fenced = False
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            out.append(SkillRow(rel, n, line, fenced))
    return out


def measure(rev: str) -> list[Touch]:
    src = ROOT / "src" / "rietx"
    now = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8")
           for p in sorted(src.rglob("*.py"))}
    # --no-renames: a detected rename lists only the new path, so the old
    # file's names would never be read at the base and a removal could not fail.
    changed = set(_git("diff", "--no-renames", "--name-only", rev, "--",
                       "src/rietx").stdout.split())
    changed |= set(_git("ls-files", "--others", "--exclude-standard", "--",
                        "src/rietx").stdout.split())
    then = {rel: text for rel, text in now.items() if rel not in changed}
    for rel in changed:
        if rel.endswith(".py"):
            shown = _git("show", f"{rev}:{rel}")
            if shown.returncode == 0:
                then[rel] = shown.stdout
    # Python only, as the vocabularies are: the committed GUI dist under src/
    # is minified onto a few long lines, and one rebuild would put every
    # word-like name on a changed line.
    diff = _git("diff", "--no-color", "--no-ext-diff", "-U0", rev, "--",
                "src/rietx/*.py").stdout
    return touches(vocabulary(then), vocabulary(now), changed_lines(diff),
                   skill_rows())


def main() -> int:
    rev, how = base()
    if rev is None:
        print(f"skill surface: {how}")
        return 0
    if not rev_exists(rev):
        print(f"skill surface: {rev} is not in this checkout ({how}); "
              "the checkout needs fetch-depth: 2", file=sys.stderr)
        return 1
    found = measure(rev)
    print(report(found, how))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(report(found, how, markdown=True) + "\n")
    if os.environ.get("GITHUB_ACTIONS"):
        for t in found:
            if t.fails:
                for rel, n, _, _ in t.rows:
                    print(f"::error file={rel},line={n}::{t.name} was removed "
                          "from src/ and this row still names it")
    bad = failures(found)
    for f in bad:
        print(f, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
