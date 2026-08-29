"""The agent-facing skill: where it lives, and how it reaches another repo.

`rietx` ships its operating protocol as an **Agent Skill** — a directory holding
a `SKILL.md` an agent reads whole when the task calls for it, and reference
files it loads only when it needs one (https://agentskills.io/specification, an
open standard, not a Claude feature).  The tree is `docs/skill/rietx/` in the
repository and ``rietx/data/skill/rietx/`` in the wheel; :func:`skill_path`
resolves whichever of the two this build has, so a caller never guesses.

**Why a copy per harness, and why the canonical one is `.agents/skills/`.**
The specification recommends `.agents/skills/` for a project and
`~/.agents/skills/` for a user, and most harnesses scan it — but not all, and
the exceptions are not a rounding error: Claude Code reads `.claude/skills/`
*only*.  So :func:`install` writes one real copy to `.agents/skills/<name>/`
and points every other requested harness at it with a symlink, which is what
`npx skills add` does for the same reason (a copy per harness is N copies to
keep in step).  `--copy` opts out, and Windows gets copies whatever is asked,
because a symlink there needs a privilege an install should not demand.

**The harness table is data.**  :data:`HARNESSES` carries one row per harness
with the URL its directories came from and the date they were read, because
these directories moved several times during 2026 and a stale row should be
visible rather than merely wrong.  Adding a harness is a row, not a branch.

**What this module does not do.**  It never writes a user's `AGENTS.md` or
`CLAUDE.md`: :func:`install` *prints* the two lines that name the skill and
leaves the file to its owner.  Those files are a project's own instructions to
its agents, and appending to one uninvited is editing something we do not own.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from ._about import DIST_NAME

#: The skill's directory name.  The specification requires ``name:`` in the
#: frontmatter to equal the directory it sits in, and both are the distribution
#: name, so this is not a second spelling of it.
SKILL_DIR_NAME = DIST_NAME

#: Where a skill tree lives inside the wheel, under :data:`_about.DATA_PACKAGE`.
_WHEEL_SUBPATH = ("skill", SKILL_DIR_NAME)
#: …and in the repository, relative to its root.
_REPO_SUBPATH = ("docs", "skill", SKILL_DIR_NAME)

#: The directory the specification recommends, and the one real copy
#: :func:`install` writes.  Every other harness is linked to it.
CANONICAL_DIR = ".agents/skills"
CANONICAL_USER_DIR = "~/.agents/skills"


@dataclass(frozen=True)
class Harness:
    """One agent harness, and where it looks for skills.

    ``project_dir`` and ``user_dir`` are the directories *this* harness scans,
    relative to a project root and to ``~`` respectively.  A harness whose
    directory is :data:`CANONICAL_DIR` needs no link: the canonical copy is
    already in the place it reads.
    """

    name: str
    label: str
    project_dir: str
    user_dir: str
    source: str
    verified: str

    @property
    def needs_link(self) -> bool:
        return self.project_dir != CANONICAL_DIR


#: Harness → directory, read from each product's own documentation on the date
#: in the row.  Only the *first* project directory each harness scans is listed;
#: several accept more than one, and a skill in the canonical directory is found
#: by any harness that scans it.
HARNESSES: tuple[Harness, ...] = (
    Harness("claude", "Claude Code", ".claude/skills", "~/.claude/skills",
            "https://code.claude.com/docs/en/skills", "2026-08-28"),
    Harness("codex", "Codex", CANONICAL_DIR, CANONICAL_USER_DIR,
            "https://learn.chatgpt.com/docs/build-skills", "2026-08-28"),
    Harness("cursor", "Cursor", ".cursor/skills", "~/.cursor/skills",
            "https://cursor.com/docs/context/skills", "2026-08-28"),
    Harness("copilot", "GitHub Copilot", ".github/skills", "~/.copilot/skills",
            "https://docs.github.com/en/copilot/how-tos/copilot-cli/"
            "customize-copilot/add-skills", "2026-08-28"),
    Harness("gemini", "Gemini CLI", ".gemini/skills", "~/.gemini/skills",
            "https://geminicli.com/docs/cli/skills/", "2026-08-28"),
    Harness("opencode", "opencode", ".opencode/skills",
            "~/.config/opencode/skills",
            "https://opencode.ai/docs/skills/", "2026-08-28"),
    Harness("goose", "Goose", CANONICAL_DIR, CANONICAL_USER_DIR,
            "https://github.com/block/goose/blob/main/documentation/docs/"
            "guides/context-engineering/using-skills.md", "2026-08-28"),
    Harness("cline", "Cline", ".cline/skills", "~/.cline/skills",
            "https://docs.cline.bot/customization/skills", "2026-08-28"),
    Harness("amp", "Amp", CANONICAL_DIR, "~/.config/agents/skills",
            "https://ampcode.com/docs/customize/skills", "2026-08-28"),
    Harness("kiro", "Kiro", ".kiro/skills", "~/.kiro/skills",
            "https://kiro.dev/docs/skills/", "2026-08-28"),
    Harness("devin", "Devin", CANONICAL_DIR, "~/.config/devin/skills",
            "https://docs.devin.ai/cli/extensibility/skills/overview",
            "2026-08-28"),
    Harness("zed", "Zed", CANONICAL_DIR, CANONICAL_USER_DIR,
            "https://zed.dev/docs/ai/skills", "2026-08-28"),
    Harness("junie", "JetBrains Junie", ".junie/skills", "~/.junie/skills",
            "https://junie.jetbrains.com/docs/agent-skills.html", "2026-08-28"),
    Harness("qwen", "Qwen Code", ".qwen/skills", "~/.qwen/skills",
            "https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/",
            "2026-08-28"),
    Harness("openhands", "OpenHands", CANONICAL_DIR, CANONICAL_USER_DIR,
            "https://docs.openhands.dev/overview/skills", "2026-08-28"),
)

#: What ``--install`` targets when the caller names no harness.  One name, not
#: every row: linking a skill into fifteen directories a machine does not have
#: is clutter, and the canonical copy already serves every harness that reads
#: the recommended directory.
DEFAULT_AGENTS = ("claude",)

HARNESSES_BY_NAME = {h.name: h for h in HARNESSES}


def skill_path() -> Path | None:
    """The skill directory this build can offer, or ``None``.

    The wheel's copy first (an installed user has no repository), then the
    repository's, which is what an editable install and every test see.
    """
    from importlib.resources import files

    try:
        wheel = Path(str(files(f"{DIST_NAME}.data").joinpath(*_WHEEL_SUBPATH)))
    except (ModuleNotFoundError, TypeError):  # pragma: no cover - defensive
        wheel = None
    if wheel is not None and (wheel / "SKILL.md").is_file():
        return wheel

    repo = Path(__file__).resolve().parents[2].joinpath(*_REPO_SUBPATH)
    if (repo / "SKILL.md").is_file():
        return repo
    return None


def _require_path() -> Path:
    path = skill_path()
    if path is None:  # pragma: no cover - only a broken install reaches this
        raise FileNotFoundError(
            "no skill directory in this build: neither the wheel's "
            f"{DIST_NAME}/data/skill/{SKILL_DIR_NAME} nor the repository's "
            f"docs/skill/{SKILL_DIR_NAME}"
        )
    return path


def sections() -> list[str]:
    """The names :func:`read` accepts, body first."""
    root = _require_path()
    return ["SKILL", *sorted(p.stem for p in (root / "references").glob("*.md"))]


def read(section: str | None = None) -> str:
    """The skill as text, for a harness that reads no skills at all.

    ``None`` gives the body; a section name gives that reference file; ``"all"``
    gives the whole tree, each file under a header naming it.  This is what
    Aider's ``--read`` and a custom loop's system prompt take.
    """
    root = _require_path()
    if section == "all":
        parts = []
        for name in sections():
            rel = "SKILL.md" if name == "SKILL" else f"references/{name}.md"
            text = (root / rel).read_text(encoding="utf-8")
            parts.append(f"===== {rel} =====\n\n{text}")
        return "\n\n".join(parts)
    if section in (None, "SKILL"):
        return (root / "SKILL.md").read_text(encoding="utf-8")
    path = root / "references" / f"{section}.md"
    if not path.is_file():
        raise KeyError(
            f"no section {section!r}; try one of {', '.join(sections())}"
        )
    return path.read_text(encoding="utf-8")


def _link_or_copy(source: Path, target: Path, *, copy: bool) -> str:
    """Point ``target`` at ``source``.  Returns what was done, for the report."""
    if target.is_symlink() or target.exists():
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if copy or os.name == "nt":
        shutil.copytree(source, target)
        return "copied"
    try:
        target.symlink_to(source, target_is_directory=True)
        return "linked"
    except OSError:  # a filesystem or a policy that refuses symlinks
        shutil.copytree(source, target)
        return "copied"


def install(
    root: str | os.PathLike[str] = ".",
    *,
    user: bool = False,
    agents: tuple[str, ...] | list[str] = DEFAULT_AGENTS,
    copy: bool = False,
) -> dict[str, Path]:
    """Write the skill into ``root`` (or the user's home with ``user=True``).

    One real copy lands in the canonical directory; every requested harness
    that reads somewhere else is pointed at it.  Returns ``{what: where}`` —
    ``"canonical"`` plus one entry per harness — so a caller can report or
    assert on it rather than parsing output.
    """
    unknown = [a for a in agents if a not in HARNESSES_BY_NAME]
    if unknown:
        raise KeyError(
            f"unknown harness {unknown}; known: "
            f"{', '.join(sorted(HARNESSES_BY_NAME))}"
        )

    source = _require_path()
    base = Path.home() if user else Path(root).expanduser().resolve()

    def _dir(spec: str) -> Path:
        return Path(spec.replace("~/", "", 1)) if user else Path(spec)

    written: dict[str, Path] = {}
    canonical = base / _dir(CANONICAL_USER_DIR if user else CANONICAL_DIR) / SKILL_DIR_NAME
    if canonical.is_symlink():
        canonical.unlink()
    elif canonical.exists():
        shutil.rmtree(canonical)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, canonical)
    written["canonical"] = canonical

    for name in agents:
        harness = HARNESSES_BY_NAME[name]
        if not harness.needs_link:
            written[name] = canonical
            continue
        spec = harness.user_dir if user else harness.project_dir
        target = base / _dir(spec) / SKILL_DIR_NAME
        if target == canonical:
            written[name] = canonical
            continue
        _link_or_copy(canonical, target, copy=copy)
        written[name] = target
    return written


def instructions_snippet() -> str:
    """The two lines to add to a project's `AGENTS.md` or `CLAUDE.md`.

    Printed by ``--install``, never written: those files belong to the project,
    not to this package.
    """
    return (
        f"To refine powder diffraction data with {DIST_NAME}, load the "
        f"`{SKILL_DIR_NAME}` skill in `{CANONICAL_DIR}/{SKILL_DIR_NAME}/`.\n"
        "It carries the operating protocol: what to free in what order, what to "
        "check before believing a number, and which numbers may be quoted."
    )
