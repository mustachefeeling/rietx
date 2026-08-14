"""Part 1's anti-divergence guards: name resolution, and a coverage partition.

Part 2's guards work because an equation names the symbol it was transcribed
from (`test_manual.py`).  A reference manual fails differently, and this repo
has measured how: ``features["indexing"]`` was ``False`` for its entire life
because the flag's ``hasattr`` name (``index``) and the real export
(``index_pattern``) drifted apart while the meta-test asserted the flag's own
expression rather than the name (WP-1037).  A manual is a much larger surface
of exactly that bug, so what is checked here is **names**:

* every dotted rietx name Part 1 spells resolves against the live package;
* every parameter dot-path matches a real `ParameterTable` (and carries no
  brackets — stage plans glob with fnmatch, where ``[..]`` is a character
  class);
* every fenced ``python`` block parses, and either executes or carries a
  written reason it does not;
* the derived public surface (`tests/api_surface.py`) is **partitioned**:
  every name is documented in a Part 1 chapter, excluded with a reason, or in
  the generated `deferred-1.0.x` bucket.

The partition is what stops coverage from silently dropping.  A new public
method is on the derived surface the moment it is written and in none of the
three buckets, so this test fails and names it; the fix is to document it,
exclude it with a reason, or regenerate the deferred file — which is a diff a
reviewer sees.  It tightens from both sides: if the scan for documented names
ever stops matching, those names fall out of every bucket and the partition
fails; if it over-matches, they land in two buckets and it fails too.

**What it does not measure is quality.**  The cheapest way to turn a coverage
partition green is a line reading "`SharingMap` maps sharing".  The bar for
that is the executed examples and human review; this test only stops a name
from being forgotten.
"""

from __future__ import annotations

import ast
import importlib
import re
import typing
from fnmatch import fnmatch
from pathlib import Path

import pytest

from rietx import Instrument
from rietx.params.vector import ParameterTable
from tests.api_surface import (
    EXCLUDED_TYPES,
    EXCLUSIONS,
    derive_surface,
    load_deferred,
    reachable_types,
)
from tests.test_coordinates import make_rutile
from tests.test_schemas import make_lab6

REPO_ROOT = Path(__file__).resolve().parent.parent
MANUAL_DIR = REPO_ROOT / "docs" / "manual"
USING_DIR = MANUAL_DIR / "using"
PAGES = sorted(USING_DIR.rglob("*.md")) if USING_DIR.exists() else []

CODE_SPAN = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"^```\{?([\w-]+)\}?[^\n]*\n(.*?)^```", re.S | re.M)
LITERALINCLUDE = re.compile(r"^```\{literalinclude\}\s+(\S+)\s*$", re.M)
DOTTED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_*][A-Za-z0-9_*]*)*")
# A block that is not executed says why, on the line above its fence.  A bare
# exemption is how this rots, so the reason is part of the syntax.
NO_EXEC = re.compile(r"<!--\s*api-doc:\s*no-exec\s*[-—]\s*(?P<reason>[^>]+?)\s*-->")

# Roots of a parameter dot-path (`params/vector.py`), as opposed to a dotted
# python name.  The two look alike in a code span and are checked differently.
PATH_ROOTS = ("phases.", "instrument.")


def _pages() -> list[tuple[Path, str]]:
    return [(page, page.read_text(encoding="utf-8")) for page in PAGES]


def _fences(text: str, language: str) -> list[str]:
    return [body for lang, body in FENCE.findall(text) if lang == language]


def _python_blocks(page: Path, text: str) -> list[tuple[str, str | None]]:
    """Each ``python`` fence with its no-exec reason, or None if it executes.

    The marker is the HTML comment on the line above the fence, so a block and
    its exemption cannot drift apart the way a separate list of exempt blocks
    would.
    """
    out: list[tuple[str, str | None]] = []
    for match in re.finditer(r"^```python[^\n]*\n(.*?)^```", text, re.S | re.M):
        preceding = text[: match.start()].rstrip().rsplit("\n", 1)[-1]
        marker = NO_EXEC.search(preceding)
        out.append((match.group(1), marker.group("reason") if marker else None))
    return out


def _included_sources(page: Path, text: str) -> list[str]:
    """The text of every `{literalinclude}`d file.

    The walkthroughs are `examples/` scripts shown verbatim (WP-1067: one
    authority, and it is `examples/`), so what a script spells is what a
    reader of the chapter sees.
    """
    sources = []
    for target in LITERALINCLUDE.findall(text):
        path = (page.parent / target).resolve()
        assert path.exists(), f"{page.name}: literalinclude target does not exist: {target}"
        sources.append(path.read_text(encoding="utf-8"))
    return sources


def _code_text(page: Path, text: str) -> str:
    """Everything on a page that is code: spans, python fences, includes.

    Prose is deliberately not scanned.  "the Structure schema" in a sentence is
    not documentation of `Structure`, and matching it would make the partition
    satisfiable by accident.
    """
    parts = [
        *CODE_SPAN.findall(text),
        *_fences(text, "python"),
        *_included_sources(page, text),
    ]
    return "\n".join(parts)


def documented_names() -> set[str]:
    """Surface names a Part 1 chapter spells, in code, qualified.

    Qualified: a chapter documents `Statistics.rwp` by naming it, not by
    showing ``result.statistics.rwp`` — an expression cannot be attributed to a
    type without inferring one, and a reference chapter names the type anyway.
    A leading ``rietx.`` is stripped, so ``rietx.read_pattern`` and
    ``read_pattern`` are one name.
    """
    surface = derive_surface()
    found: set[str] = set()
    for page, text in _pages():
        for token in DOTTED.findall(_code_text(page, text)):
            name = token.removeprefix("rietx.")
            if name in surface:
                found.add(name)
    return found


def _parameter_paths() -> set[str]:
    """Every dot-path two representative models put on the table.

    LaB6 (cubic, tied cell, locked special positions) and rutile with free
    coordinates, which is what puts `…atoms.*.dof.*` paths in reach.
    """
    paths: set[str] = set()
    instrument = Instrument.debye_scherrer(wavelength=0.4139)
    for structure in (make_lab6(), make_rutile(vary_coords=True)):
        paths.update(entry.path for entry in ParameterTable(structure, instrument).entries)
    return paths


# --- names ----------------------------------------------------------------


def _rietx_class_in(annotation: object) -> type | None:
    """The rietx class inside an annotation, past any Optional/list/dict."""
    stack = [annotation]
    while stack:
        node = stack.pop()
        if isinstance(node, type) and (getattr(node, "__module__", "") or "").startswith("rietx"):
            return node
        stack.extend(arg for arg in typing.get_args(node) if arg is not None)
    return None


def _step(obj: object, attr: str) -> tuple[bool, object]:
    """One attribute hop, over classes and pydantic fields alike.

    A pydantic v2 model does not carry its fields as class attributes, so
    `getattr(Capabilities, "backends")` raises: a field hop reads
    `model_fields` and continues from the annotated type.
    """
    if isinstance(obj, type):
        fields = getattr(obj, "model_fields", None) or {}
        if attr in fields:
            return True, _rietx_class_in(fields[attr].annotation)
    value = getattr(obj, attr, None)
    return value is not None, value


def _resolve_absolute(page: Path, dotted: str) -> None:
    """Resolve a fully-spelled `rietx.…` name, module path included."""
    parts = dotted.split(".")
    for cut in range(len(parts), 0, -1):
        try:
            obj: object = importlib.import_module(".".join(parts[:cut]))
        except ImportError:
            continue
        for attr in parts[cut:]:
            ok, obj = _step(obj, attr)
            assert ok, f"{page.name}: `{dotted}` — no {attr!r}"
            if obj is None:
                return
        return
    raise AssertionError(f"{page.name}: `{dotted}` — nothing importable in it")


def test_every_dotted_name_resolves():
    """A dotted rietx name in Part 1 imports and attributes out.  This is the
    WP-1037 bug's shape: the manual says `index`, the package exports
    `index_pattern`, and nothing notices.

    Resolution starts from the derived type registry, not from `rietx`:
    `Statistics` and `Capabilities` are reachable and documented types that
    `__all__` does not export, and traversing from the package would refuse
    them for the wrong reason.
    """
    surface = derive_surface()
    types_by_name = reachable_types()
    roots = {name.split(".")[0] for name in surface}
    rietx = importlib.import_module("rietx")
    for page, text in _pages():
        for token in DOTTED.findall(_code_text(page, text)):
            if token.startswith("rietx.") and token not in surface:
                # A fully-spelled name is always checkable, module path and
                # all: `rietx.viz.compare.run` reaches past `__all__`, and
                # `rietx.viz` is not even an attribute until something imports
                # it, so resolution walks the longest importable prefix first.
                _resolve_absolute(page, token)
                continue
            dotted = token.removeprefix("rietx.")
            if "." not in dotted or dotted.startswith(PATH_ROOTS) or dotted in surface:
                continue
            head, _, tail = dotted.partition(".")
            if head not in roots:
                continue
            obj = types_by_name.get(head) or getattr(rietx, head, None)
            assert obj is not None, f"{page.name}: `{token}` — nothing named {head!r}"
            for attr in tail.split("."):
                ok, obj = _step(obj, attr)
                assert ok, f"{page.name}: `{token}` — {head} has no member {attr!r}"
                if obj is None:  # a field of a non-rietx type: nothing further to walk
                    break


def test_imports_shown_in_part_one_exist():
    """`from rietx import capabilities` in a chapter names something the
    package exports.  A bare name is not dotted, so the resolver above cannot
    see it, and an executed block would only catch it if the block runs — this
    catches it in a block that is exempt, and in a code span."""
    pattern = re.compile(r"from\s+(rietx[\w.]*)\s+import\s+([^\n(]+)")
    for page, text in _pages():
        for module_name, names in pattern.findall(_code_text(page, text)):
            module = importlib.import_module(module_name)
            for name in (part.strip() for part in names.split(",")):
                if not name:
                    continue
                imported = name.split(" as ")[0].strip()
                assert hasattr(module, imported), (
                    f"{page.name}: `from {module_name} import {imported}` — "
                    f"{module_name} exports no {imported!r}"
                )


def test_parameter_dot_paths_resolve():
    """Every dot-path or glob Part 1 spells matches a real ParameterTable, and
    carries no brackets: stage plans match with fnmatch, where `[..]` is a
    character class rather than an index (root CLAUDE.md § Conventions)."""
    paths = _parameter_paths()
    for page, text in _pages():
        # tokens *inside* a span, not whole spans: a path is usually quoted in
        # a call — `result.parameter("phases.0.cell.a")` — and checking only
        # spans that are paths outright would skip exactly those.
        for token in DOTTED.findall("\n".join(CODE_SPAN.findall(text))):
            if not token.startswith(PATH_ROOTS):
                continue
            assert "[" not in token and "]" not in token, (
                f"{page.name}: parameter path `{token}` uses brackets; fnmatch reads them "
                "as a character class"
            )
            assert any(fnmatch(path, token) for path in paths), (
                f"{page.name}: parameter path `{token}` matches nothing on a real table"
            )


# --- examples -------------------------------------------------------------


def test_every_python_block_parses():
    """Free, and it catches the typo class immediately — including in a block
    that is exempt from execution."""
    for page, text in _pages():
        for block, _ in _python_blocks(page, text):
            try:
                ast.parse(block)
            except SyntaxError as exc:  # pragma: no cover - the message is the point
                pytest.fail(f"{page.name}: python block does not parse: {exc}")


def test_python_blocks_execute_or_say_why():
    """A block that only builds objects or reads fields runs here, against the
    bundled fixtures.  A block that refines does not exist as inline prose at
    all — it is a `{literalinclude}` of an `examples/` script, executed by
    `tests/test_examples.py` on the acceptance cadence (WP-1067's cost model,
    under `tests/CLAUDE.md`'s rule that a wall-clock budget in a test is a
    runaway guard and never a timer).  Anything else carries a reason, because
    a bare exemption is how this rots."""
    for page, text in _pages():
        for block, reason in _python_blocks(page, text):
            if reason is not None:
                assert len(reason.split()) >= 3, f"{page.name}: no-exec reason is a shrug: {reason}"
                continue
            try:
                exec(compile(block, f"{page.name}:python", "exec"), {"__name__": "manual_block"})
            except Exception as exc:  # pragma: no cover - the message is the point
                pytest.fail(
                    f"{page.name}: python block raised {type(exc).__name__}: {exc}\n"
                    f"--- block ---\n{block}\n"
                    "Add `<!-- api-doc: no-exec — <reason> -->` above it if it cannot run."
                )


# --- the partition --------------------------------------------------------


def test_derived_surface_is_partitioned():
    """Every public name is documented, excluded with a reason, or deferred.

    Fails on a name in none of the three (a new public method nobody
    documented) and on a name in two (a deferred name a chapter has since
    documented, with the generated bucket not regenerated).
    """
    surface = set(derive_surface())
    documented = documented_names()
    deferred = set(load_deferred())

    missing = surface - documented - deferred
    assert not missing, (
        f"{len(missing)} public name(s) in no bucket — document them in a Part 1 chapter, "
        "exclude them with a reason in tests/api_surface.py, or defer them with "
        f"`python -m tests.api_surface --write-deferred`: {sorted(missing)[:20]}"
    )
    overlap = documented & deferred
    assert not overlap, (
        f"{len(overlap)} name(s) both documented and deferred — regenerate the bucket with "
        f"`python -m tests.api_surface --write-deferred`: {sorted(overlap)[:20]}"
    )


def test_deferred_bucket_has_no_stale_names():
    """A deferred name that no longer exists is a rename the bucket slept
    through — the failure mode the whole derivation exists to prevent."""
    surface = set(derive_surface())
    stale = [name for name in load_deferred() if name not in surface]
    assert not stale, f"deferred names no longer on the surface: {stale}"


def test_exclusions_are_live_and_reasoned():
    """An exclusion that matches nothing is a rename with a dead reason
    attached, and an empty reason is a shrug.  Checked against the surface
    derived *without* exclusions, which is the only place an excluded name is
    still visible."""
    unfiltered = set(derive_surface(apply_exclusions=False))
    filtered = set(derive_surface())
    for name, reason in {**EXCLUDED_TYPES, **EXCLUSIONS}.items():
        assert len(reason.split()) >= 5, f"{name}: exclusion carries no real reason"
    for name in EXCLUSIONS:
        assert "." in name, f"{name}: member exclusions are qualified (Type.member)"
        assert name in unfiltered, f"{name}: excluded name is not on the surface at all"
        assert name not in filtered, f"{name}: excluded but still derived"
    for name in EXCLUDED_TYPES:
        assert name in unfiltered, f"{name}: excluded type is not on the surface at all"
        assert name not in filtered, f"{name}: excluded type still on the surface"
