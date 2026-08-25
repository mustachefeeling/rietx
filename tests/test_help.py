"""WP-1202 — the help corpus against the live vocabularies it describes.

Every arm of ``rietx.help`` is keyed by a member of a vocabulary the package
already owns, and each test here crosses one arm against its own authority in
*both* directions: a member with no entry fails, and an entry describing
nothing fails too.  That second direction is the one a hand-written corpus
loses first, because a renamed member leaves its old entry sitting there
describing a name that no longer exists.

The rule is the root CLAUDE.md's, one rank over from ``_SURFACE_FLAGS``: a
description is a claim about a name, and a claim nothing checks rots silently.
``features["indexing"]`` spent its whole life ``False`` for exactly this reason.

Two fields are checked against the schemas rather than read: ``unit`` and
``default``.  Nothing else in the corpus has an authority in the code, and
``typical`` deliberately has none.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import re
from pathlib import Path
from typing import get_args

import pytest
from pydantic import BaseModel

import rietx as rx
from rietx.gui.imports import INSTRUMENT_PRESETS
from rietx.help import (
    INSTRUMENT_FIELD_HELP,
    PARAMETER_HELP,
    PEAK_DIAGNOSTIC_HELP,
    PEAK_FLAG_HELP,
    READER_OPTION_HELP,
    STAGE_FIELD_HELP,
    UNIT_DISPLAY,
    HelpEntry,
    help_key_for,
    help_registry,
    plan_help,
)
from rietx.io.formats.base import READER_OPTIONS
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.indexing import PeakFlag
from rietx.schemas.instrument import EmissionLine, Instrument, Source
from rietx.schemas.plan import StageSpec
from rietx.schemas.structure import (
    Atom,
    Cell,
    Phase,
    PreferredOrientation,
    StephensStrain,
    Structure,
)
from rietx.strategy.staged import PLAN_INFO
from tests.test_manual import built_manual  # noqa: F401  (fixture, shared build)

ROOT = Path(__file__).resolve().parents[1]
INDEXING = ROOT / "src" / "rietx" / "indexing"


# ------------------------------------------------------------------ vocabulary
def _default_models() -> tuple[Structure, Instrument]:
    """A phase and an instrument whose every ``Parameter`` sits at its default.

    Both halves matter.  The paths are what a real ``ParameterTable`` produces,
    so the family globs are checked against the strings they will actually meet;
    and because nothing here overrides a ``Parameter``, each entry's ``value``
    *is* the schema default, which is what lets :func:`test_defaults_are_the_schemas_own`
    read the defaults off a table instead of restating them.

    Every optional block is present on purpose.  ``tests/data/gui/
    fnmatch_cases.json`` is built from two models that carry no
    preferred-orientation block, so its path list has a hole exactly where a
    family would go unchecked; this is the coverage authority, and it closes it.
    """
    def p(value: float) -> Parameter:
        return Parameter(value=value)

    cell = Cell(a=p(3.15), b=p(3.15), c=p(4.77),
                alpha=p(90.0), beta=p(90.0), gamma=p(120.0))
    phase = Phase(
        name="brucite", space_group="P -3 m 1", cell=cell,
        atoms=[
            Atom(label="Mg", species="Mg", x=p(0.0), y=p(0.0), z=p(0.0),
                 aniso=rx.AnisoU.isotropic(0.01, cell)),
            Atom(label="O", species="O", x=p(1 / 3), y=p(2 / 3), z=p(0.22)),
        ],
        preferred_orientation=PreferredOrientation(axis=(0, 0, 1)),
        # bare, not `isotropic()`: the coefficients have to sit at their
        # schema defaults for `test_defaults_are_the_schemas_own` to read
        # them off this table.  An all-zero block still produces the same
        # `dof.k` paths, since the subspace is derived from the operators.
        microstrain=StephensStrain(),
    )
    instrument = Instrument(source=Source(lines=[
        EmissionLine(wavelength=1.540598), EmissionLine(wavelength=1.544426)]))
    return Structure(phases=[phase]), instrument


def _vocabulary() -> list[str]:
    """Every parameter path the models above produce, in table order."""
    structure, instrument = _default_models()
    return [e.path for e in ParameterTable(structure, instrument).entries]


def _peak_diagnostic_codes() -> set[str]:
    """Every ``PEAK_*`` diagnostic code constructed under ``indexing/``.

    Derived by walking the source rather than listed, for the reason
    ``tests/test_docs_consistency.py`` walks it too: a code added to a screen is
    a message a person will read, and a curated list is what stops noticing.
    All twelve live in ``indexing/diagnostics.py`` today; the walk covers the
    package so one written elsewhere is still caught.
    """
    codes: set[str] = set()
    for py in sorted(INDEXING.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if (kw.arg == "code" and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                        and kw.value.value.startswith("PEAK_")):
                    codes.add(kw.value.value)
    return codes


def _preset_fields() -> set[str]:
    return {f for fields in INSTRUMENT_PRESETS.values() for f in fields}


def _arms() -> dict[str, dict[str, HelpEntry]]:
    """Every named arm, so a test can sweep all of them at once."""
    return {
        "peak_flags": PEAK_FLAG_HELP,
        "peak_diagnostics": PEAK_DIAGNOSTIC_HELP,
        "stage_fields": STAGE_FIELD_HELP,
        "reader_options": READER_OPTION_HELP,
        "instrument_fields": INSTRUMENT_FIELD_HELP,
        "plans": plan_help(),
    }


def _every_entry() -> list[tuple[str, HelpEntry]]:
    out = [(g, e) for g, e in PARAMETER_HELP.items()]
    for arm, entries in _arms().items():
        out += [(f"{arm}:{k}", e) for k, e in entries.items()]
    return out


# ------------------------------------------------------- the parameter families
def test_every_parameter_path_matches_exactly_one_family():
    """No path is undescribed, and none is described twice.

    Exactly-one is what lets :func:`rietx.help.help_key_for` return the first
    match without ranking by specificity.  Two families claiming one path would
    make its description depend on declaration order, which is not a property
    anybody should have to know about.
    """
    from fnmatch import fnmatchcase

    unclaimed, contested = [], []
    for path in _vocabulary():
        hits = [g for g in PARAMETER_HELP if fnmatchcase(path, g)]
        if not hits:
            unclaimed.append(path)
        elif len(hits) > 1:
            contested.append((path, hits))
    assert not unclaimed, (
        f"parameter paths no family describes: {unclaimed} — add a family to "
        "rietx.help.PARAMETER_HELP")
    assert not contested, (
        f"parameter paths claimed by more than one family: {contested} — "
        "help_key_for returns the first match, so this would make a "
        "description depend on declaration order")


def test_every_family_glob_describes_a_real_path():
    """The other direction: a family matching nothing describes a dead name.

    This is the half a corpus loses to a rename.  The glob keeps matching
    nothing and the entry keeps rendering into the glossary, so a reader is
    told about a parameter the package does not have.
    """
    from fnmatch import fnmatchcase

    paths = _vocabulary()
    dead = [g for g in PARAMETER_HELP
            if not any(fnmatchcase(p, g) for p in paths)]
    assert not dead, (
        f"family globs matching no live parameter path: {dead} — the "
        "parameter was renamed or removed, and its entry outlived it")


# --------------------------------------------------------------- the named arms
def test_every_peak_flag_has_an_entry():
    flags = set(get_args(PeakFlag))
    assert len(flags) >= 13, "PeakFlag import broke — the Literal moved?"
    assert set(PEAK_FLAG_HELP) == flags, (
        f"missing: {sorted(flags - set(PEAK_FLAG_HELP))}; "
        f"describing nothing: {sorted(set(PEAK_FLAG_HELP) - flags)}")


def test_every_peak_diagnostic_code_has_an_entry():
    codes = _peak_diagnostic_codes()
    assert len(codes) >= 12, (
        f"only {len(codes)} PEAK_* codes collected — the AST walk broke, it "
        "does not mean the screens got quieter")
    assert set(PEAK_DIAGNOSTIC_HELP) == codes, (
        f"missing: {sorted(codes - set(PEAK_DIAGNOSTIC_HELP))}; "
        f"describing nothing: {sorted(set(PEAK_DIAGNOSTIC_HELP) - codes)}")


def test_every_stage_field_has_an_entry():
    fields = set(StageSpec.model_fields)
    assert set(STAGE_FIELD_HELP) == fields, (
        f"missing: {sorted(fields - set(STAGE_FIELD_HELP))}; "
        f"describing nothing: {sorted(set(STAGE_FIELD_HELP) - fields)}")


def test_every_reader_option_has_an_entry():
    assert set(READER_OPTION_HELP) == set(READER_OPTIONS), (
        f"missing: {sorted(set(READER_OPTIONS) - set(READER_OPTION_HELP))}; "
        f"describing nothing: "
        f"{sorted(set(READER_OPTION_HELP) - set(READER_OPTIONS))}")


def test_every_instrument_preset_field_has_an_entry():
    """A field the wizard offers with no description is a control with no label.

    ``INSTRUMENT_PRESETS`` is the constructors' own signature list, which is
    what ``gui/src/lib/wizard.ts`` is already held to across the language
    boundary; this holds the prose to the same set.
    """
    fields = _preset_fields()
    assert set(INSTRUMENT_FIELD_HELP) == fields, (
        f"missing: {sorted(fields - set(INSTRUMENT_FIELD_HELP))}; "
        f"describing nothing: {sorted(set(INSTRUMENT_FIELD_HELP) - fields)}")


def test_the_plan_arm_is_plan_info_projected_not_restated():
    """``PLAN_INFO`` is the authority, so the arm must quote it byte for byte.

    A paraphrase here would be a second description of the same preset, kept in
    a second place, and the two would answer differently the first time one was
    edited.
    """
    plans = plan_help()
    assert set(plans) == set(PLAN_INFO)
    for name, info in PLAN_INFO.items():
        assert plans[name].title == info.title
        assert plans[name].description == info.description
        assert plans[name].typical == info.when_to_use


# ------------------------------------------------------ the schema-backed fields
#: The three places a table path is not the schema's own field path: the source
#: block's polarization flattens onto the instrument, a background coefficient
#: is indexed as ``cN``, and an ADP component loses its ``aniso`` block.  Named
#: rather than skipped, and :func:`_schema_parameters` asserts the map is
#: exhaustive, so a fourth renaming fails here instead of quietly dropping a
#: parameter out of the unit and default checks.  That guard has already earned
#: itself: the ADP rule was found by it, not by reading the table.
_PATH_RENAMES = {
    "instrument.source.polarization": "instrument.polarization",
}
_COEFFICIENT = re.compile(r"^instrument\.background\.coefficients\.(\d+)$")
_ANISO = re.compile(r"^(phases\.\d+\.atoms\.\d+)\.aniso\.(u\d\d)$")


def _schema_parameters() -> dict[str, Parameter]:
    """Every ``Parameter`` the default models hold, keyed by its table path."""
    structure, instrument = _default_models()
    walked: dict[str, Parameter] = {}

    def walk(obj: BaseModel, prefix: str) -> None:
        for name in type(obj).model_fields:
            value = getattr(obj, name)
            path = f"{prefix}.{name}"
            if isinstance(value, Parameter):
                walked[path] = value
            elif isinstance(value, BaseModel):
                walk(value, path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, Parameter):
                        walked[f"{path}.{i}"] = item
                    elif isinstance(item, BaseModel):
                        walk(item, f"{path}.{i}")

    walk(instrument, "instrument")
    walk(structure.phases[0], "phases.0")

    out: dict[str, Parameter] = {}
    for path, param in walked.items():
        coefficient = _COEFFICIENT.match(path)
        if coefficient:
            path = f"instrument.background.c{coefficient.group(1)}"
        aniso = _ANISO.match(path)
        if aniso:
            path = f"{aniso.group(1)}.{aniso.group(2)}"
        out[_PATH_RENAMES.get(path, path)] = param

    live = {e.path for e in ParameterTable(structure, instrument).entries}
    strayed = sorted(set(out) - live)
    assert not strayed, (
        f"schema field paths the parameter table does not produce: {strayed} — "
        "the table renamed a path and _PATH_RENAMES has not been told, so "
        "these parameters are silently outside the unit and default checks")
    return out


def test_units_are_the_schemas_own():
    """No entry may invent a unit, or disagree with the one the schema declares.

    The two spellings differ on purpose: a schema says ``deg^2`` because it is
    a machine-readable field, and a page says ``deg² 2θ``.  :data:`UNIT_DISPLAY`
    is the crossing, so a schema unit with no display spelling fails here rather
    than reaching a reader as ``A^-4``.
    """
    unknown, wrong = [], []
    for path, param in _schema_parameters().items():
        entry = rx.help_for(path)
        assert entry is not None, f"{path} has no entry"
        if param.unit is None:
            continue
        if param.unit not in UNIT_DISPLAY:
            unknown.append((path, param.unit))
            continue
        if entry.unit != UNIT_DISPLAY[param.unit]:
            wrong.append((path, entry.unit, UNIT_DISPLAY[param.unit]))
    assert not unknown, (
        f"schema units with no display spelling: {unknown} — add them to "
        "rietx.help.UNIT_DISPLAY")
    assert not wrong, (
        "entries whose unit disagrees with the schema "
        f"(path, entry, expected): {wrong}")

    reached = {p.unit for p in _schema_parameters().values() if p.unit}
    assert set(UNIT_DISPLAY) == reached, (
        f"display spellings for units no schema declares: "
        f"{sorted(set(UNIT_DISPLAY) - reached)} — a table nothing reads is a "
        "spelling nobody has checked")


def test_defaults_are_the_schemas_own():
    """An entry's ``default`` is the schema's value, or absent.

    Absent is the honest state for a cell edge or a coordinate, which arrive
    with the structure and have no default to quote.  What this catches is the
    other case: a retuned schema default leaving a stale number in print, which
    is the failure the fenced constants in ``docs/manual/conf.py`` exist for.
    """
    wrong = []
    for path, param in _schema_parameters().items():
        entry = rx.help_for(path)
        if entry.default is None:
            continue
        try:
            quoted = float(entry.default)
        except ValueError:  # a prose default such as "null" or "[]"
            continue
        if quoted != pytest.approx(param.value, rel=0, abs=0):
            wrong.append((path, entry.default, param.value))
    assert not wrong, (
        "entries whose default disagrees with the schema "
        f"(path, entry, schema): {wrong}")


def test_a_parameter_with_no_default_says_so_rather_than_guessing():
    """A cell edge and a coordinate carry ``default=None``, not a made-up value.

    The WP-1076 shape: a defaulted number would read as an answer about a
    parameter that has none.
    """
    for path in ("phases.0.cell.a", "phases.0.cell.beta", "phases.0.atoms.0.x"):
        assert rx.help_for(path).default is None, path


# ---------------------------------------------------------------- the row's key
def test_every_row_of_a_real_model_carries_its_family_key():
    """``ParameterRow.help_key`` is filled by ``Refinement.parameters``.

    Filled there rather than by the GUI, so ``None`` means "no family claims
    this path" for every caller.  A row whose key is missing would report the
    same ``None`` and mean something else entirely.
    """
    structure, instrument = _default_models()
    rows = rx.Refinement(structure, instrument).parameters()
    assert rows
    missing = [r.path for r in rows if r.help_key is None]
    assert not missing, f"rows with no help_key: {missing}"
    for row in rows:
        assert row.help_key == help_key_for(row.path)
        assert row.help_key in PARAMETER_HELP


# ----------------------------------------------------------------- the registry
def test_the_registry_is_json_and_carries_every_arm():
    registry = help_registry()
    assert set(registry) == {"parameters", "peak_flags", "peak_diagnostics",
                             "stage_fields", "reader_options",
                             "instrument_fields", "plans"}
    payload = json.dumps(registry)  # raises on anything unserialisable
    assert len(payload) > 10_000

    reached = {g for entry in registry["parameters"] for g in entry["paths"]}
    assert reached == set(PARAMETER_HELP), (
        "the parameters arm lost a glob in the grouping — a help_key would "
        "then index nothing")
    for entry in registry["parameters"]:
        assert entry["title"] and entry["description"]
    for name, entry in registry["plans"].items():
        assert entry["modes"] == list(PLAN_INFO[name].modes)


def test_the_help_route_serves_the_registry():
    from rietx.gui.server import ROUTES

    assert ("GET", "/api/help") in ROUTES


# -------------------------------------------------------------------- the prose
def test_every_parameter_family_carries_a_range_and_a_chapter():
    """A parameter entry must have both ``typical`` and ``anchor``; an arm need not.

    All 33 families already do, and this is the audit turning that accident
    into a checked claim: a range to compare a refined number against, and the
    chapter with the equation, are the two things a parameter entry is *for*.
    ``None`` on either would read as "nothing covers this" about a family
    nobody had finished — the defaulted-answer shape again.

    The named arms are exempt by nature, not by oversight: a peak flag has no
    typical range, and seven of the thirteen name a state no Part 2 chapter
    has an equation for.
    """
    thin = sorted({g for g, e in PARAMETER_HELP.items()
                   if e.typical is None or e.anchor is None})
    assert not thin, (
        f"parameter families with no typical range or no manual anchor: {thin}")


def test_every_entry_has_a_title_and_a_description():
    thin = [name for name, e in _every_entry()
            if not e.title or len(e.description.split()) < 8]
    assert not thin, (
        f"entries with no title or a description under eight words: {thin} — "
        "a stub reads as an answer the same way a defaulted field does")


@pytest.mark.xdist_group("manual-build")
def test_every_anchor_resolves_in_the_built_manual(built_manual):  # noqa: F811
    """An ``anchor`` names a heading the popover will jump to, so it must exist.

    Checked against the **built** HTML rather than the Markdown sources, for
    the reason ``test_no_unrendered_math_survives_the_build`` is: a heading id
    exists in the source whether or not the page renders, and a slug is
    generated rather than written, so only the output says what a link will
    find.  This is the dead-link guard WP-1017 planned, arriving early because
    the corpus is the first thing in the tree that links into Part 2 by id.
    """
    out, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual.py"
    ids: set[str] = set()
    for page in out.rglob("*.html"):
        ids |= set(re.findall(r'id="([^"]+)"', page.read_text(encoding="utf-8")))
    assert len(ids) > 100, "no ids found — did the build produce HTML?"

    broken = sorted({(name, e.anchor) for name, e in _every_entry()
                     if e.anchor and e.anchor not in ids})
    assert not broken, (
        f"entries whose anchor is not a heading in the built manual: {broken} — "
        "the heading was renamed, and the slug moved with it")


def test_entry_is_frozen_so_a_consumer_cannot_edit_the_corpus():
    entry = rx.help_for("phases.0.scale")
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.title = "something else"  # type: ignore[misc]
