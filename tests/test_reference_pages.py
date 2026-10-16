"""The Reference tab's generated pages (WP-1981, `docs/reference_pages.py`).

Each page is built at docs-build time from the code that owns its facts.  These
tests call the same generators the build does, so they need no Sphinx run.
The page contract on each generated body is `tests/test_manual.py`'s.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from rietx.help import help_registry

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
REFERENCE_DIR = DOCS_DIR / "docs" / "reference"


def _load():
    spec = importlib.util.spec_from_file_location(
        "_reference_pages", DOCS_DIR / "reference_pages.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reference_pages = _load()


def test_every_generated_body_is_included_by_exactly_one_page():
    """A body no page includes is built and shown nowhere; two includes are one
    page twice."""
    includes = re.compile(r"^```\{include\} [./]*_generated/(\S+)$", re.M)
    found = [name for page in sorted(REFERENCE_DIR.rglob("*.md"))
             for name in includes.findall(page.read_text(encoding="utf-8"))]
    assert sorted(found) == sorted(reference_pages.BODIES)


# ----------------------------------------------------------------------
# The parameter map
# ----------------------------------------------------------------------

def test_every_parameter_glob_lands_in_exactly_one_group():
    """The build raises otherwise; this says so without one."""
    groups = reference_pages.parameter_groups()
    placed = [path for _, _, leaves in groups for _, _, members in leaves
              for entry in members for path in entry["paths"]]
    every = [path for entry in help_registry()["parameters"] for path in entry["paths"]]
    assert sorted(placed) == sorted(every)


@pytest.mark.parametrize("paths, fragment", [
    (["nowhere.at_all"], "nowhere.at_all: claimed by 0 leaves"),
    (["phases.*.cell.new", "instrument.geometry.sample_new"], "one entry split across leaves"),
])
def test_the_grouping_fails_what_it_should(paths, fragment):
    """An unplaced glob and an entry split across two leaves each raise by name."""
    entries = help_registry()["parameters"] + [{"paths": paths}]
    with pytest.raises(RuntimeError, match=re.escape(fragment)):
        reference_pages.parameter_groups(entries)


def test_a_glob_two_leaves_claim_raises():
    """`*` crosses dots, so a careless leaf glob can claim another leaf's paths."""
    entries = [{"paths": ["phases.*.atoms.*.moment.dof*"]}]
    claimed = [glob for _, _, leaves in reference_pages.PARAMETER_GROUPS
               for _, _, globs in leaves for glob in globs]
    assert "phases.*.atoms.*.moment.*" in claimed
    original = reference_pages.PARAMETER_GROUPS
    try:
        reference_pages.PARAMETER_GROUPS = original + (
            ("Extra", "Lead.", ((None, None, ("phases.*.atoms.*",)),)),)
        with pytest.raises(RuntimeError, match="claimed by 2 leaves"):
            reference_pages.parameter_groups(entries)
    finally:
        reference_pages.PARAMETER_GROUPS = original


def test_the_map_shows_every_entry_once_with_its_unit():
    """One table row and one definition per registry entry."""
    text = reference_pages.parameter_map()
    for entry in help_registry()["parameters"]:
        first = f"`{entry['paths'][0]}`"
        assert text.count(f"| {first}") == 1, entry["paths"]
        assert f"\n{entry['title']}\n: " in text, entry["title"]
        if entry["unit"]:
            row = next(line for line in text.splitlines() if line.startswith(f"| {first}"))
            assert f"| {entry['unit']} |" in row, row


# ----------------------------------------------------------------------
# The plan ladder
# ----------------------------------------------------------------------

def test_every_preset_has_a_ladder_with_every_stage_and_glob():
    """The old tree's hand-drawn ladder dropped a stage; a drawn one cannot."""
    from rietx.strategy.staged import PLAN_PRESETS

    text = reference_pages.plan_ladder()
    sections = re.split(r"^## ", text, flags=re.M)[1:]
    assert [s.splitlines()[0] for s in sections] == list(PLAN_PRESETS)
    for section in sections:
        plan = PLAN_PRESETS[section.splitlines()[0]]()
        nodes = re.findall(r'^  s\d+\["(.*)"\]$', section, flags=re.M)
        assert len(nodes) == len(plan.stages)
        for node, stage in zip(nodes, plan.stages):
            lines = node.replace("\\*", "*").split("<br>")
            assert lines[:1 + len(stage.turn_on)] == [stage.name, *stage.turn_on]


def test_the_mode_substitutions_are_what_resolve_plan_runs():
    from rietx.strategy.staged import _MODE_SUBSTITUTES, PLAN_PRESETS, resolve_plan

    text = reference_pages.plan_ladder()
    for (name, mode), twin in _MODE_SUBSTITUTES.items():
        assert resolve_plan(name, mode) == PLAN_PRESETS[twin]()
        assert f"Under `{mode}`, `{name}` runs as `{twin}`." in text


# ----------------------------------------------------------------------
# The diagnostic index
# ----------------------------------------------------------------------

def test_the_index_holds_every_code_the_skill_walk_finds():
    """Two walks of one source; the index's must not be the narrower."""
    import ast

    from tests.skill_surface import diagnostic_codes, is_engine_source

    root = reference_pages.SOURCE_ROOT.parent.parent
    skill = set()
    for path in (root / "src" / "rietx").rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if is_engine_source(rel):
            skill |= diagnostic_codes(ast.parse(path.read_text(encoding="utf-8")))
    index = reference_pages.diagnostic_index()
    assert skill <= set(index), sorted(skill - set(index))


def test_the_index_reaches_the_shapes_a_keyword_walk_misses(tmp_path):
    """A `GuardFinding` constructor's code, a `*_CODES` table, and a level."""
    pkg = tmp_path / "rietx"
    (pkg / "gui").mkdir(parents=True)
    (pkg / "a.py").write_text(
        'X_CODES = (("ONE_CODE", "ONE_OMITTED"),)\n'
        "def f():\n"
        '    GuardFinding("GUARD_CODE", (), 0.0, "")\n'
        '    Diagnostic(level="warning", code="KW_CODE", message="")\n'
        '    Diagnostic(level=lv, code="RUN_CODE", message="")\n', encoding="utf-8")
    (pkg / "gui" / "b.py").write_text('E(code="GUI_CODE")\n', encoding="utf-8")
    index = reference_pages.diagnostic_index(pkg)
    assert sorted(index) == ["GUARD_CODE", "KW_CODE", "ONE_CODE", "ONE_OMITTED", "RUN_CODE"]
    assert index["KW_CODE"]["levels"] == {"warning"}
    assert index["RUN_CODE"]["levels"] == {""}
    assert index["GUARD_CODE"]["levels"] == set()
