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
