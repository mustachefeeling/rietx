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


def test_a_glob_two_leaves_claim_raises(monkeypatch):
    """`*` crosses dots, so a careless leaf glob can claim another leaf's paths."""
    entries = [{"paths": ["phases.*.atoms.*.moment.dof*"]}]
    claimed = [glob for _, _, leaves in reference_pages.PARAMETER_GROUPS
               for _, _, globs in leaves for glob in globs]
    assert "phases.*.atoms.*.moment.*" in claimed
    monkeypatch.setattr(reference_pages, "PARAMETER_GROUPS", reference_pages.PARAMETER_GROUPS + (
        ("Extra", "Lead.", ((None, None, ("phases.*.atoms.*",)),)),))
    with pytest.raises(RuntimeError, match="claimed by 2 leaves"):
        reference_pages.parameter_groups(entries)


@pytest.mark.parametrize("text, rendered", [
    ("1-5 μ_B for a 3d ion", "1-5 μ<sub>B</sub> for a 3d ion"),
    ("in `μ_B` as code", "in `μ_B` as code"),
    ("a `crystalaxis_*` path", "a `crystalaxis_*` path"),
    ("lor_size", "lor_size"),
])
def test_notation_renders_outside_code_spans(text, rendered):
    assert reference_pages._notation(text) == rendered


def test_the_map_shows_every_entry_once_with_its_unit():
    """One table row and one definition per registry entry."""
    text = reference_pages.parameter_map()
    for entry in help_registry()["parameters"]:
        first = f"`{entry['paths'][0]}`"
        assert text.count(f"| {first}") == 1, entry["paths"]
        assert f"\n{entry['title']}\n: " in text, entry["title"]
        if entry["unit"]:
            row = next(line for line in text.splitlines() if line.startswith(f"| {first}"))
            assert f"| {reference_pages._notation(entry['unit'])} |" in row, row


# ----------------------------------------------------------------------
# The plan ladder
# ----------------------------------------------------------------------

def test_every_preset_has_a_ladder_with_every_stage_and_glob():
    """The old tree's hand-drawn ladder dropped a stage; a drawn one cannot."""
    from rietx.strategy.staged import PLAN_PRESETS

    text = reference_pages.plan_ladder()
    sections = re.split(r"^## ", text, flags=re.M)[1:]
    heading = [s.splitlines()[0].strip('`') for s in sections]
    assert heading == list(PLAN_PRESETS)
    for name, section in zip(heading, sections):
        plan = PLAN_PRESETS[name]()
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
    """A `GuardFinding` constructor's code, a `*_CODES` table (annotated too),
    and a level."""
    pkg = tmp_path / "rietx"
    (pkg / "gui").mkdir(parents=True)
    (pkg / "a.py").write_text(
        'X_CODES = (("ONE_CODE", "ONE_OMITTED"),)\n'
        "def f():\n"
        '    GuardFinding("GUARD_CODE", (), 0.0, "")\n'
        '    Diagnostic(level="warning", code="KW_CODE", message="")\n'
        '    Diagnostic(level=lv, code="RUN_CODE", message="")\n', encoding="utf-8")
    (pkg / "gui" / "b.py").write_text('E(code="GUI_CODE")\n', encoding="utf-8")
    (pkg / "c.py").write_text('_Y_CODES: tuple = ("KW_CODE", "TYPED_CODE")\n', encoding="utf-8")
    index = reference_pages.diagnostic_index(pkg)
    assert sorted(index) == ["GUARD_CODE", "KW_CODE", "ONE_CODE", "ONE_OMITTED", "RUN_CODE",
                             "TYPED_CODE"]
    assert index["KW_CODE"]["levels"] == {"warning"}
    assert index["RUN_CODE"]["levels"] == {""}
    assert index["GUARD_CODE"]["levels"] == set()
    # A table that only lists a code raised elsewhere does not raise it.
    assert index["KW_CODE"]["files"] == {"rietx/a.py"}
    assert index["TYPED_CODE"]["files"] == {"rietx/c.py"}


# ----------------------------------------------------------------------
# The project tree
# ----------------------------------------------------------------------

def test_the_tree_names_every_writer_constant():
    text = reference_pages.project_tree()
    for module, constant, _ in reference_pages.PROJECT_ENTRIES + reference_pages.RUN_ENTRIES:
        assert f"`{module}.{constant}`" in text


def test_a_created_file_no_row_names_raises(monkeypatch):
    """A new file in a fresh project fails the build until a row describes it."""
    rows = tuple(r for r in reference_pages.PROJECT_ENTRIES if r[1] != "HISTORY_FILE")
    monkeypatch.setattr(reference_pages, "PROJECT_ENTRIES", rows)
    with pytest.raises(RuntimeError, match="history.jsonl"):
        reference_pages.project_tree()


# ----------------------------------------------------------------------
# The roadmap
# ----------------------------------------------------------------------

ROADMAP_SAMPLE = """\
## Milestones

| Milestone | Scope | Status | Acceptance |
|---|---|---|---|
| v1.9 | A cut | ✅ **shipped 2026-10-14** ([record](milestones/v1.9.md)) | rows |
| v1.10 | The next release | 🔄 **accumulating since 2026-10-14** ([record](milestones/v1.10.md)) | x |
| magnetic | The moment (was v1.6): the satellite — [§ m](#magnetic) | 🔄 **opened 2026-09-18** ([record](milestones/magnetic.md)) | rows |
| rietview | rietview (was v1.7): the figure — [WPs](wp/README.md#x): 1801 | ⬜ **queued 2026-09-27** | x |

## Work packages
"""


def test_the_roadmap_keeps_named_milestones_and_drops_maintainer_links():
    rows = reference_pages._milestone_rows(ROADMAP_SAMPLE)
    assert rows == [
        {"name": "magnetic", "scope": "The moment: the satellite",
         "status": "opened 2026-09-18", "record": "milestones/magnetic.md"},
        {"name": "rietview", "scope": "rietview: the figure",
         "status": "queued 2026-09-27", "record": None},
    ]


def test_every_export_has_one_tier_in_the_api_reference():
    """`rietx.__all__` is the floor: a new export lands in the third tier
    until the skill's index places it, and none is listed twice."""
    import rietx

    tiers = reference_pages.api_tiers()
    heads = [name.split(".")[1] for _, sections, _ in tiers for _, names in sections
             for name in names if name.count(".") == 1]
    assert set(rietx.__all__) <= set(heads), sorted(set(rietx.__all__) - set(heads))
    third = [n for _, names in tiers[-1][1] for n in names]
    assert not set(third) & {n for _, s, _ in tiers[:-1] for _, ns in s for n in ns}


# ----------------------------------------------------------------------
# The foreign-name map: hand-written, and checked against the code that reads
# and writes each format
# ----------------------------------------------------------------------

#: Column -> the modules whose string constants hold that format's names.
FOREIGN_CODE = {
    "GSAS-II": ("io/projects/gsas2.py", "io/instrument_profile.py",
                "io/instrument_tof.py", "io/recipe.py"),
    "GSAS": ("io/projects/gsas.py", "io/instrument_profile.py"),
    "TOPAS": ("io/projects/topas.py", "io/projects/topas_input.py",
              "io/projects/topas_refined.py", "io/projects/coverage.py"),
    "FullProf": ("io/projects/fullprof.py",),
}


def _string_constants(rel: str) -> set[str]:
    """Every string literal in a module that is not a docstring."""
    import ast

    tree = ast.parse((reference_pages.SOURCE_ROOT / rel).read_text(encoding="utf-8"))
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef)
                  and node.body and isinstance(node.body[0], ast.Expr)}
    return {node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docstrings}


#: A FullProf column header the reader's module quotes, ``#: ``! Lambda1 ...``.
_PCR_HEADER = re.compile(r"``!([^`]*)")


def _pcr_header_names(rel: str) -> set[str]:
    """Every name on a ``!`` column header the module quotes from a `.pcr`.

    The FullProf reader cuts at ``!``, so the format's own names live in these
    quoted headers rather than in string constants, and its constants are
    mostly rietx's lowercase keys (`x`, `biso`, `scale`).
    """
    text = (reference_pages.SOURCE_ROOT / rel).read_text(encoding="utf-8")
    return {name for header in _PCR_HEADER.findall(text) for name in header.split()}


def _foreign_table() -> tuple[list[str], list[list[str]]]:
    text = (REFERENCE_DIR / "foreign-names.md").read_text(encoding="utf-8")
    rows = [[c.strip() for c in line.strip().strip("|").split("|")]
            for line in text.splitlines() if line.startswith("| ")]
    return rows[0], [r for r in rows[1:] if not set(r[0]) <= {"-", " "}]


def test_every_foreign_name_is_one_its_reader_or_writer_uses():
    header, rows = _foreign_table()
    assert header[1:] == list(FOREIGN_CODE)
    unknown = []
    for column, modules in FOREIGN_CODE.items():
        known = set().union(*(_string_constants(m) for m in modules))
        if column == "FullProf":
            # Exact case: folded, `X` matched rietx's own `x` key, not FullProf's.
            known = set().union(*(_pcr_header_names(m) for m in modules))
        for row in rows:
            for name in re.findall(r"`([^`]+)`", row[header.index(column)]):
                found = name in known or any(k.startswith(f"{name}(") for k in known)
                if not found:
                    unknown.append(f"{column} {name!r} (row {row[0]})")
    assert not unknown, "names no reader or writer of the format uses:\n" + "\n".join(unknown)


def test_every_rietx_path_in_the_foreign_map_is_a_parameter():
    from fnmatch import fnmatchcase

    from rietx.help import PARAMETER_HELP

    _, rows = _foreign_table()
    for row in rows:
        first = re.findall(r"`([^`]+)`", row[0])[0]
        assert any(fnmatchcase(first, glob) or fnmatchcase(glob, first)
                   for glob in PARAMETER_HELP), first


def test_the_roadmap_page_links_nothing_inside_the_planning_tree():
    text = reference_pages.roadmap_page()
    assert re.findall(r"\]\((?!https://)[^)]*\)", text) == []
    assert "| magnetic |" in text
