"""`rietx skill`, the wheel copy, and the two committed copies (WP-1304).

`tests/test_skill.py` asserts what the skill *says*; this file asserts that it
**arrives** — that `skill_path()` resolves, that `--install` lands in both the
canonical directory and each requested harness's own, and that the copies
committed to this repository have not drifted from the tree they were made
from.

Two properties are easy to get wrong and are asserted directly.  A harness
whose directory already *is* the canonical one must not be linked to itself,
and an install over an existing skill must replace it rather than nest a second
copy inside it — the shape a naive `copytree` into an existing directory gives.
"""

from __future__ import annotations

import filecmp
import os
import subprocess
import sys
from pathlib import Path

import pytest

from rietx import capabilities, skill

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs" / "skill" / "rietx"
#: Committed so that a session working *in this repository* loads the skill
#: under any harness.  Real copies rather than symlinks: a symlink in a git
#: checkout is not portable to Windows, which the release gate tests.
COMMITTED = (ROOT / ".agents" / "skills" / "rietx",
             ROOT / ".claude" / "skills" / "rietx")


def _files(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def test_the_skill_path_resolves_and_is_the_canonical_tree():
    path = skill.skill_path()
    assert path is not None
    assert (path / "SKILL.md").is_file()
    # editable install: the repository tree, since the wheel copy is build-time
    assert path == CANONICAL


def test_capabilities_carries_the_skill_path():
    caps = capabilities()
    assert caps.skill_path == str(CANONICAL)
    assert "skill_path" in caps.model_dump(mode="json")


@pytest.mark.parametrize("copy_dir", COMMITTED, ids=lambda p: p.parts[-3])
def test_the_committed_copies_have_not_drifted(copy_dir: Path):
    """`rietx skill --install . --copy` regenerates these; this is what says so
    when an edit to `docs/skill/rietx/` forgot to."""
    assert copy_dir.is_dir(), f"{copy_dir} is missing — run: rietx skill --install . --copy"
    assert _files(copy_dir) == _files(CANONICAL), (
        f"{copy_dir.relative_to(ROOT)} has different files from the canonical "
        "tree — regenerate with: rietx skill --install . --copy"
    )
    match, mismatch, errors = filecmp.cmpfiles(
        CANONICAL, copy_dir, sorted(_files(CANONICAL)), shallow=False)
    assert not mismatch and not errors, (
        f"{copy_dir.relative_to(ROOT)} differs at {mismatch + errors} — "
        "regenerate with: rietx skill --install . --copy"
    )


def test_read_gives_the_body_a_section_and_the_whole_tree():
    body = skill.read()
    assert body.startswith("---\nname: rietx")
    assert skill.read("SKILL") == body
    assert "# 7." in skill.read("diagnostics")
    every = skill.read("all")
    for name in skill.sections():
        assert name in every
    with pytest.raises(KeyError):
        skill.read("no-such-section")


def test_install_lands_in_both_places_and_links_rather_than_copies(tmp_path):
    written = skill.install(tmp_path, agents=("claude", "codex"))

    canonical = tmp_path / ".agents" / "skills" / "rietx"
    assert written["canonical"] == canonical
    assert (canonical / "SKILL.md").read_bytes() == (CANONICAL / "SKILL.md").read_bytes()
    assert _files(canonical) == _files(CANONICAL)

    # codex reads the canonical directory, so it must not be linked to itself
    assert written["codex"] == canonical

    claude = tmp_path / ".claude" / "skills" / "rietx"
    assert written["claude"] == claude
    if os.name != "nt":
        assert claude.is_symlink()
        # relative, so a moved or re-cloned project keeps a working link
        assert not Path(os.readlink(claude)).is_absolute()
        assert claude.resolve() == canonical.resolve()
    assert (claude / "SKILL.md").is_file()


def test_install_with_copy_makes_a_real_directory(tmp_path):
    written = skill.install(tmp_path, agents=("claude",), copy=True)
    claude = written["claude"]
    assert not claude.is_symlink()
    assert _files(claude) == _files(CANONICAL)


def test_install_replaces_rather_than_nests(tmp_path):
    """A second install must not leave `…/rietx/rietx/`, which is what a
    `copytree` into an existing directory gives."""
    skill.install(tmp_path, agents=("claude",), copy=True)
    skill.install(tmp_path, agents=("claude",), copy=True)
    canonical = tmp_path / ".agents" / "skills" / "rietx"
    assert not (canonical / "rietx").exists()
    assert _files(canonical) == _files(CANONICAL)


def test_install_refuses_an_unknown_harness(tmp_path):
    with pytest.raises(KeyError, match="unknown harness"):
        skill.install(tmp_path, agents=("not-a-harness",))


def test_every_harness_row_carries_a_source_and_a_date():
    """The table is data, and a row without provenance is a guess."""
    assert len(skill.HARNESSES) >= 10
    for h in skill.HARNESSES:
        assert h.source.startswith("https://"), h.name
        assert len(h.verified) == 10 and h.verified[4] == "-", h.name
        assert h.project_dir.endswith("skills"), h.name
        assert h.user_dir.startswith("~/"), h.name
    assert len({h.name for h in skill.HARNESSES}) == len(skill.HARNESSES)
    assert set(skill.DEFAULT_AGENTS) <= set(skill.HARNESSES_BY_NAME)
    # the one that made the canonical directory insufficient on its own
    assert skill.HARNESSES_BY_NAME["claude"].needs_link


def _cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run the CLI and decode its output as **UTF-8**, not as the locale's codec.

    ``text=True`` decodes with ``locale.getpreferredencoding(False)``, which is
    cp1252 on Windows, and `rietx.cli._utf8_output` makes the child write UTF-8
    on every platform — so the two disagree and the *parent* raises
    ``UnicodeDecodeError`` on the first byte cp1252 has no code point for
    (0x81, from the ``₁`` in ``occ₁`` — byte 12858 of the body here, and 13032
    on the runner, which is the same byte: 174 newlines precede it and Windows
    text mode writes each as CRLF).

    That is the same defect as the one the CLI fix cured, standing on its other
    foot: before, the child could not encode ``α``; after, a caller that assumes
    the console code page cannot decode ``₁``.  Decoding UTF-8 here is not
    papering over it — it is what the CLI's contract now says a consumer does,
    and it is what ``tests/test_portability.py`` asserts that contract to be.
    """
    return subprocess.run([sys.executable, "-m", "rietx.cli", *args],
                          capture_output=True, encoding="utf-8", cwd=cwd)


def test_cli_path_print_and_list(tmp_path):
    out = _cli("skill", "--path")
    assert out.returncode == 0
    assert Path(out.stdout.strip()) == CANONICAL

    out = _cli("skill", "--print")
    assert out.returncode == 0 and out.stdout.startswith("---\nname: rietx")

    out = _cli("skill", "--print", "nonesuch")
    assert out.returncode == 2 and "no section" in out.stderr

    out = _cli("skill", "--list-agents")
    assert out.returncode == 0
    for h in skill.HARNESSES:
        assert h.name in out.stdout and h.source in out.stdout


def test_cli_install_prints_the_snippet_it_does_not_write(tmp_path):
    out = _cli("skill", "--install", str(tmp_path))
    assert out.returncode == 0, out.stderr
    assert (tmp_path / ".agents" / "skills" / "rietx" / "SKILL.md").is_file()
    assert skill.instructions_snippet().splitlines()[0] in out.stdout
    # the snippet is printed, never written: those files are the project's
    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / "CLAUDE.md").exists()


def test_an_installed_tree_satisfies_the_specs_own_rules(tmp_path):
    """The `skills-ref` validator is labelled demonstration-only and is not a
    dependency, so its rules are re-implemented against the installed copy —
    the shape a harness actually reads.

    Rules: agentskills.io/specification, verified 2026-08-29.
    """
    import re

    import yaml

    written = skill.install(tmp_path, agents=("claude",))
    root = written["canonical"]

    assert root.is_dir() and root.name == "rietx"
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    meta = yaml.safe_load(text.split("---\n", 2)[1])

    assert re.fullmatch(r"(?!-)(?!.*--)[a-z0-9-]{1,64}(?<!-)", meta["name"])
    assert meta["name"] == root.name
    assert 0 < len(meta["description"]) <= 1024
    assert set(meta) <= {"name", "description", "license", "compatibility",
                         "metadata", "allowed-tools"}
    assert len(meta.get("compatibility", "")) <= 500
    assert all(isinstance(v, str) for v in meta.get("metadata", {}).values())
    assert len(text.splitlines()) < 500

    # references are one level deep, as the spec asks
    for path in root.rglob("*.md"):
        assert len(path.relative_to(root).parts) <= 2, path
