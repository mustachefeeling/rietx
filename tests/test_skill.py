"""The skill tree's format contract (WP-1304).

`docs/skill/rietx/` is the agent-facing document in the open Agent Skills
format: a `SKILL.md` an agent reads whole in one call, reference files loaded
when a task calls for them.  Three things can rot silently here and each has a
test below.

**The caps.**  The document this replaced was 144 427 B, 2.2x the Read tool's
~66 kB cap, so an agent that tried to load it got lines 1-707 and then went
hunting with `grep` and `sed` — five roundtrips for one document, with §7's
diagnostics table never reaching context at all.  A skill body is read *whole*
when the skill activates, so its size is a fixed cost paid by every session
that loads it: `SKILL_MAX_BYTES` is half the Read cap, and `SKILL_MAX_LINES` is
the specification's own recommendation.  `REFERENCE_MAX_BYTES` is the other
tool's limit — Bash output above 40 kB comes back as a 2 kB preview, so a
reference file that a session might `cat` stays under it.

Raising a cap is a decision about every future session's fixed cost.  Make it
in a commit that says so; the fix for a full body is to move a lookup into a
reference file, which is what the tree is for.

**The frontmatter.**  Fields outside the specification are ignored by some
harnesses and rejected by others, so the field *set* is asserted rather than
just the required members.

**The names.**  `references/api.md` is the document three "explore the library"
runs (114 calls) were trying to write from source, and one of them asserted
that everything public is re-exported from the top-level package, which is
false.  So the file is **generated** from the installed package by
`docs/skill/make_api_index.py` — every signature, field and default rendered,
none typed — and pinned byte for byte here, so a rename, a new keyword or a
changed default fails until it is regenerated.  The body's own `report.x` /
`result.x` names, which no generator writes, are walked through the types the
same way the manual's are (`tests/api_surface.attr_step`), and every `rx.X` in
the tree is really exported — the WP-1037 bug's shape, one document over.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from tests.api_surface import attr_step, resolve_dotted

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "docs" / "skill" / "rietx"
SKILL = SKILL_DIR / "SKILL.md"
REFERENCE_DIR = SKILL_DIR / "references"
REFERENCES = sorted(REFERENCE_DIR.glob("*.md"))
API_INDEX = REFERENCE_DIR / "api.md"

#: A skill body is read whole on activation; the Read tool returned 66 kB on
#: the document this replaced, so the body is capped at half of it.
# Half the Read tool's ~66 kB cap, the derivation this module's docstring
# states; 32_000 was that halving rounded down and WP-1131 rounded it up, in
# the commit that needed the 941 B — a fifth deliverable class (microstructure)
# in the body's own deliverable table, with its worked measurement in
# references/judging.md where the other four keep theirs.  The cost this cap
# governs — the fixed bytes every session that loads the skill pays — moves by
# 3 %, and the alternative was a deliverable whose row lived outside the table
# its peers are in, which is what the cap exists to protect against.
SKILL_MAX_BYTES = 33_000
#: agentskills.io/specification: "Keep your main SKILL.md under 500 lines."
SKILL_MAX_LINES = 500
#: Bash output above 40 kB is truncated to a ~2 kB preview, so a reference file
#: stays comfortably under that even when a session cats it rather than Reads.
REFERENCE_MAX_BYTES = 36_000

#: Every field the specification defines, and whether it is required.
#: agentskills.io/specification, verified 2026-08-29.
SPEC_FIELDS = {
    "name": True,
    "description": True,
    "license": False,
    "compatibility": False,
    "metadata": False,
    "allowed-tools": False,
}
SPEC_NAME_RE = re.compile(r"^(?!-)(?!.*--)[a-z0-9-]{1,64}(?<!-)$")
DESCRIPTION_MAX = 1024
COMPATIBILITY_MAX = 500


def _frontmatter() -> dict:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must open with YAML frontmatter"
    _, block, _ = text.split("---\n", 2)
    return yaml.safe_load(block)


def test_the_body_is_within_its_caps():
    """The whole point of the split: one Read, whole, every time."""
    size = len(SKILL.read_bytes())
    lines = len(SKILL.read_text(encoding="utf-8").splitlines())
    assert size <= SKILL_MAX_BYTES, (
        f"SKILL.md is {size} B (cap {SKILL_MAX_BYTES}). Move a lookup table "
        "into references/ — see this module's docstring on raising a cap."
    )
    assert lines < SKILL_MAX_LINES, (
        f"SKILL.md is {lines} lines (cap {SKILL_MAX_LINES}, the spec's own)."
    )


@pytest.mark.parametrize("path", REFERENCES, ids=lambda p: p.name)
def test_every_reference_file_is_within_its_cap(path: Path):
    size = len(path.read_bytes())
    assert size <= REFERENCE_MAX_BYTES, (
        f"{path.name} is {size} B (cap {REFERENCE_MAX_BYTES}); split it."
    )


def test_the_frontmatter_is_the_specs_and_nothing_else():
    meta = _frontmatter()
    unknown = sorted(set(meta) - set(SPEC_FIELDS))
    assert not unknown, (
        f"frontmatter fields outside the Agent Skills spec: {unknown} — some "
        "harnesses reject an unknown key rather than ignoring it"
    )
    missing = sorted(k for k, required in SPEC_FIELDS.items()
                     if required and k not in meta)
    assert not missing, f"required frontmatter fields missing: {missing}"


def test_the_name_matches_the_directory_and_the_specs_shape():
    name = _frontmatter()["name"]
    assert SPEC_NAME_RE.match(name), (
        f"name {name!r}: 1-64 chars of [a-z0-9-], no leading, trailing or "
        "doubled hyphen"
    )
    assert name == SKILL_DIR.name, (
        f"name {name!r} must match the parent directory {SKILL_DIR.name!r}"
    )


def test_the_description_and_compatibility_fit_their_budgets():
    """`description` is loaded for *every* skill at startup, so it is charged
    against a catalogue budget rather than this skill's own (Codex caps the
    whole catalogue at 8000 chars)."""
    meta = _frontmatter()
    assert len(meta["description"]) <= DESCRIPTION_MAX
    assert len(meta.get("compatibility", "")) <= COMPATIBILITY_MAX


def test_metadata_values_are_strings_and_the_version_is_the_packages():
    """The spec's `metadata` is a map of string to string, and a version that
    is not the package's is worse than no version at all."""
    import rietx

    meta = _frontmatter().get("metadata", {})
    non_strings = sorted(k for k, v in meta.items() if not isinstance(v, str))
    assert not non_strings, (
        f"metadata values must be strings (quote them): {non_strings}"
    )
    assert meta["version"] == rietx.__version__, (
        f"SKILL.md metadata.version is {meta['version']!r}, the package is "
        f"{rietx.__version__!r} — bump it with the version (docs/RELEASING.md)"
    )


_LINK = re.compile(r"\]\((?!https?:)([^)#]+)")


def test_every_relative_link_in_the_tree_resolves():
    for path in [SKILL, *REFERENCES]:
        for target in _LINK.findall(path.read_text(encoding="utf-8")):
            resolved = (path.parent / target).resolve()
            assert resolved.exists(), f"{path.name}: dead link {target}"


def test_every_reference_file_is_reachable_from_the_body():
    """A reference nothing points at is a file no agent will open."""
    text = SKILL.read_text(encoding="utf-8")
    unreferenced = [p.name for p in REFERENCES
                    if f"references/{p.name}" not in text]
    assert not unreferenced, (
        f"reference files the body never names: {unreferenced} — add a row to "
        "the body's index table"
    )


DOTTED = re.compile(r"`(rx\.[A-Za-z_][A-Za-z0-9_.]*|rietx\.[A-Za-z_][A-Za-z0-9_.]*)")


def test_every_dotted_name_in_the_api_index_resolves():
    """The API index cannot name something the package does not have."""
    text = API_INDEX.read_text(encoding="utf-8")
    names = {m.rstrip(".") for m in DOTTED.findall(text)}
    assert len(names) > 60, f"only {len(names)} names found — the regex broke"
    for name in sorted(names):
        dotted = name if name.startswith("rietx.") else "rietx." + name[len("rx."):]
        resolve_dotted(dotted, API_INDEX.name)


def test_the_api_index_is_what_the_generator_renders():
    """`references/api.md` is generated and committed (it ships in the wheel
    with no build step), so the committed bytes must be what the generator
    renders from *this* package — a rename, a new keyword or a changed default
    fails here until the file is regenerated."""
    import difflib
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "make_api_index", ROOT / "docs" / "skill" / "make_api_index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    rendered = mod.render()
    committed = API_INDEX.read_text(encoding="utf-8")
    if rendered != committed:
        diff = list(difflib.unified_diff(
            committed.splitlines(), rendered.splitlines(),
            "committed", "rendered", lineterm="", n=0))
        pytest.fail(
            "references/api.md is stale — regenerate with\n"
            "  .venv/bin/python docs/skill/make_api_index.py && "
            "rietx skill --install . --copy\n"
            + "\n".join(diff[:40]))
    # the selection cannot be wider than what a reader can reach
    assert " at 0x" not in rendered


#: `report.regions`, `result.statistics.rwp`, `statistics.esd_inflation`,
#: `d.suggestion` — the body's own field names, which no generator writes.
BODY_DOTTED = re.compile(
    r"`(report|result|statistics|d)((?:\.[A-Za-z_][A-Za-z0-9_]*)+)(?:\(|`)")


def test_every_dotted_name_in_the_body_resolves():
    """The judgement core names result and report fields by hand (`report.
    identifiability.exchanges`, `statistics.max_shift_over_esd`), and a rule
    written against a field that has moved is a rule nobody can follow.
    Each is walked through the types the way the manual's names are."""
    import rietx as rx

    roots = {"report": rx.FitReport, "result": rx.RefinementResult,
             "statistics": rx.Statistics, "d": rx.Diagnostic}
    text = SKILL.read_text(encoding="utf-8")
    bad = []
    for root, chain in BODY_DOTTED.findall(text):
        obj = roots[root]
        for step in chain.lstrip(".").split("."):
            ok, obj = attr_step(obj, step)
            if not ok:
                bad.append(f"{root}{chain}: no {step!r}")
                break
    assert not bad, bad
    assert len(BODY_DOTTED.findall(text)) > 15, "the regex found too little"


RX_DOT_NAME = re.compile(r"`rx\.([A-Za-z_][A-Za-z0-9_]*)")


def test_every_rx_dot_name_in_the_tree_is_reachable():
    """Writing `rx.X` promises a reader can do the same (WP-1302's rule, and
    WP-1037's bug: the flag asked `hasattr(rx, "index")` while the export was
    `index_pattern`).

    A submodule keeps the promise the same way an export does — `rx.report`,
    `rx.viz` and `rx.io` are reachable only because `rietx/__init__` imports
    them, which is exactly the fact this asserts.  Nothing else is allowed:
    an attribute that is neither in `__all__` nor a module is a name a reader
    cannot rely on.
    """
    import types

    import rietx as rx

    missing = set()
    for path in [SKILL, *REFERENCES]:
        for name in RX_DOT_NAME.findall(path.read_text(encoding="utf-8")):
            if name in rx.__all__:
                continue
            if isinstance(getattr(rx, name, None), types.ModuleType):
                continue
            missing.add((path.name, name))
    assert not missing, sorted(missing)


def test_the_body_carries_the_judgement_core():
    """The rules an orchestrator copies into a brief stay in the body, not in a
    reference file: the campaign this WP answers had workers restating rules
    from a brief 71 times and opening the document 0 times."""
    text = SKILL.read_text(encoding="utf-8")
    for anchor in ("## 1.", "## 2.", "## 3.", "## 4.", "## 4b.", "## 6.",
                   "## 10."):
        assert anchor in text, f"the body no longer carries {anchor}"
    assert "stop condition" in text.lower()


def test_the_api_index_resolves_through_a_field_hop():
    """Liveness for the resolver itself: a pydantic field is not a class
    attribute, so a walk that used plain getattr would pass this file by
    failing on its first result field."""
    import rietx as rx

    ok, obj = attr_step(rx.RefinementResult, "statistics")
    assert ok and obj is rx.Statistics
    assert not attr_step(rx.RefinementResult, "no_such_field")[0]


# --- the skill's doors -----------------------------------------------------
#
# `tests/api_surface.py` partitions the package's whole call surface against
# the **manual**, whose job is coverage.  The skill is a different document
# with a different denominator: it is a protocol, not a reference, and the
# only names it is obliged to carry are the ones a caller cannot arrive at by
# following an object already in hand.
#
# That set is derived, not listed: the module-level **functions** in
# `rietx.__all__`.  A free verb is the one thing nothing leads to.  A type is
# either returned by a verb — and the index renders its fields where the
# answer is described — or constructed from a class the index already carries
# with its full signature, so an agent holding an `Instrument` reaches its
# constructors through `help(rx.Instrument)`.  Nothing an agent holds leads to
# `read_recipe`, which is why four agents of four, both models, handed a real
# TOPAS `.inp` beside the data it describes, parsed it by hand and never
# called it (WP-1307 round 1.1; `tests/eval_agent_surface/PROTOCOL.md`).
#
# **Documented means named in `references/api.md`**, not merely somewhere in
# the tree.  `read_recipe` was in `references/diagnostics.md` the whole time,
# inside a `RECIPE_*` row that cannot fire until the door has already been
# used, so a tree-wide test would have called that coverage.  `api.md` is the
# file the routing table names for *"you are about to call rietx: entry
# points"*, and it is generated, so this gate lands on `make_api_index.py`'s
# SECTIONS selection — the thing WP-1306 had no reason to touch when it added
# the `RECIPE_*` rows and shipped the diagnostics without the door.
#
# Deliberately NOT covered, recorded so a later session reads it as a gap and
# not as a decision: alternative constructors (`Instrument.
# flat_plate_transmission`, the seven `RefinementPlan.*` presets).  Thirty of
# the thirty-five are reached another way — a plan by its name string through
# `rx.PLAN_INFO`, a `GuardFinding.*` never by a caller at all — so a partition
# over them would be thirty shrugs, which is the curated list this file exists
# to avoid.

#: An entry *row* of the api index, which always renders as ``- `rx.name(…``.
#: A prose mention is not a door: the paragraph above a section may name a verb
#: in passing, and matching those would let a sentence satisfy the gate that a
#: signature row is supposed to.
API_INDEX_ENTRY = re.compile(r"^- `rx\.([A-Za-z_][A-Za-z0-9_]*)", re.M)


def _documented_verbs() -> set[str]:
    """Names the api index gives an entry row of its own."""
    return set(API_INDEX_ENTRY.findall(API_INDEX.read_text(encoding="utf-8")))


#: A verb the skill deliberately does not carry, and why.  Each entry is a
#: *reason*, never a shrug; the meta-test below fails on one that names
#: nothing, so a rename cannot leave a dead exclusion behind.
SKILL_EXCLUDED_VERBS: dict[str, str] = {
    "help_registry": (
        "the whole corpus in one call, for the GUI server's GET /api/help "
        "(`gui/session.py`). An agent reads one path at a time with "
        "`rx.help_for(path)`, which section In carries."
    ),
    "help_key_for": (
        "the lookup behind `ParameterRow.help_key`, which `refine.py` has "
        "already done by the time a caller holds a row. The index renders "
        "that field, so a caller has the key without making the call."
    ),
}


def _public_verbs() -> dict[str, object]:
    """The package's free verbs, read out of the live package."""
    import inspect

    import rietx as rx

    return {n: getattr(rx, n) for n in rx.__all__
            if inspect.isroutine(getattr(rx, n))}


def test_every_public_verb_is_documented_in_the_skill_or_excluded():
    """A new entry point ships with its door signed, or with a reason.

    The rule CLAUDE.md already carried — a WP adding a diagnostic code adds
    its row to the skill — is what WP-1306 followed: the `RECIPE_*` rows are
    present and good. Nothing told it to add the *entry point*, so the
    diagnostics arrived and the door did not. This is that rule made
    self-enforcing.
    """
    verbs = _public_verbs()
    assert len(verbs) > 20, f"only {len(verbs)} verbs found — __all__ moved"

    documented = _documented_verbs()
    undocumented = sorted(set(verbs) - documented - set(SKILL_EXCLUDED_VERBS))
    assert not undocumented, (
        "public entry points the skill does not name — add each to "
        "docs/skill/make_api_index.py's SECTIONS (then regenerate, and "
        "`rietx skill --install . --copy`), or to SKILL_EXCLUDED_VERBS with "
        f"the reason a reader never needs it: {undocumented}")


def test_the_verb_exclusions_are_live_and_reasoned():
    """The exclusion table is the authored half, so it rots like any list.

    An entry naming a verb that no longer exists is a dead promise; one that
    is *also* documented is a contradiction, and the documentation wins.
    """
    verbs = _public_verbs()
    dead = sorted(set(SKILL_EXCLUDED_VERBS) - set(verbs))
    assert not dead, f"excluded, but no longer a public verb: {dead}"

    documented = _documented_verbs()
    both = sorted(set(SKILL_EXCLUDED_VERBS) & documented)
    assert not both, f"excluded and documented — drop the exclusion: {both}"

    for name, reason in SKILL_EXCLUDED_VERBS.items():
        assert len(reason) > 40, f"{name}'s exclusion is a shrug, not a reason"
