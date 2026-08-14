"""The package's public call surface, **derived** from the live package (WP-1067).

This is the enumeration the WP-1003 freeze covers, and the denominator the
user manual's coverage partition is asserted against
(`tests/test_manual_api.py`).  It is deliberately not a hand-written list.

**Why derived.** A list nobody regenerates cannot notice a *new* public
method: it never enters the denominator, the coverage partition stays green,
and coverage silently drops.  That is `_SURFACE_FLAGS` one level up —
``features["indexing"]`` was ``False`` for its entire life because a
hand-written name (``index``) and the real export (``index_pattern``) drifted
apart while the meta-test asserted the flag's own expression rather than the
name (WP-1037).  So the names are data read out of the package, and the only
hand-written halves are the exclusions below, each carrying a reason.

**Why not ``rietx.__all__``.** It is the right set of *entry points* and the
wrong denominator for a manual: almost nothing a user calls lives there.
``ref.fit``, ``ref.parameters``, ``result.statistics.rwp``,
``history.branch``/``merge``/``cherry_pick``, ``Project.create``/``open``/
``save`` are members and fields.  A manual naming ``Refinement`` once would
satisfy an ``__all__`` partition and document nothing.

Two derivation rules carry the weight, both measured 2026-08-14:

1. **"Public member" means declared, not inherited.**  34 of the 47 exported
   classes are pydantic models, so a bare ``dir()`` denominator is 1099 names,
   most of them ``model_dump``-class ``BaseModel`` machinery.  A member counts
   iff it is one of the model's own fields, or the class that *defines* it
   lives in a ``rietx`` module.  A member is attributed to its **defining**
   class, so a method a subclass inherits from a rietx base is one entry, not
   two.
2. **The surface closes over reachable unexported types.**  ``Statistics`` is
   not exported, so one level of attributes never reaches
   ``result.statistics.rwp`` — the manual's own motivating example.  The
   closure follows fields and public-method annotations of types already on
   the surface, and the signatures of exported functions: ``capabilities()``
   returns a ``Capabilities``, which is exported nowhere.  Exporting those
   types instead would be new public API, which WP-1067 forbids itself.
3. **A plain class's members are assigned, not declared.**  ``dir()`` on the
   *class* cannot see ``self.history = …`` in ``__init__``, so
   ``Refinement.history``, ``Project.doc`` and 25 others were missing until
   the manual's own guard rejected the first of them as a name that does not
   resolve.  Instance attributes are read off the class's source with ``ast``.

Run ``python -m tests.api_surface`` for a summary of the surface, or
``python -m tests.api_surface --write-deferred`` to regenerate
``api_surface_deferred.txt`` (see `tests/test_manual_api.py` for what that
file is and why it is generated rather than typed).
"""

from __future__ import annotations

import ast
import inspect
import textwrap
import types
import typing
from dataclasses import dataclass
from pathlib import Path

import rietx

TESTS_DIR = Path(__file__).resolve().parent
DEFERRED_PATH = TESTS_DIR / "api_surface_deferred.txt"


# --- what is off the surface, and why -------------------------------------
#
# Each entry is a *reason*, not a shrug.  A type listed here is removed from
# the surface and is not expanded, so the types reachable only through it drop
# out with it; that is the point of excluding a whole type rather than its
# members one at a time.  `test_manual_api.py` fails on an entry here that
# matches nothing, so a rename cannot leave a dead exclusion behind.

EXCLUDED_TYPES: dict[str, str] = {
    "CompiledModel": (
        "compile-stage internal: the frozen-per-stage state (hkl list, symmetry-op "
        "subsets, quadrature node counts, window ranges) that the invariant in "
        "CLAUDE.md forbids touching during a run. Reachable only as the type of "
        "Refinement.snapshot's model argument; a caller passes one along, never "
        "builds or reads one."
    ),
    "CancelToken": (
        "documented as the cancel= protocol rather than as a type: a caller "
        "constructs one and calls .cancel() from another thread, and the "
        "cooperative-cancellation semantics are the documentable part."
    ),
}

# Individual names, where the *type* is on the surface but one member is not.
EXCLUSIONS: dict[str, str] = {}


# --- derivation ------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    """One name on the public call surface."""

    name: str  # "refine", "RefinementResult.statistics", "agent.refine_json"
    kind: str  # "function" | "class" | "constant" | "field" | "member" | "module"
    owner: str | None = None  # the type or module the member is declared on


def is_rietx(obj: object) -> bool:
    """True for a class or function defined inside the `rietx` package."""
    module = getattr(obj, "__module__", None)
    if not isinstance(module, str):
        return False
    return module == "rietx" or module.startswith("rietx.")


def _public(name: str) -> bool:
    return not name.startswith("_")


def _defining_class(cls: type, name: str) -> type | None:
    for base in cls.__mro__:
        if name in vars(base):
            return base
    return None


# pydantic writes these into the class body of every model, so they are
# "declared in a rietx module" by the letter of rule 1 and machinery by its
# intent.  Filtered structurally rather than listed as exclusions: they are
# not this package's surface at all.
_PYDANTIC_CLASS_ATTRS = frozenset({"model_config", "model_fields", "model_computed_fields"})


def _instance_attributes(cls: type) -> set[str]:
    """Public ``self.x = ...`` attributes assigned in the class's own body.

    `Refinement.history` is one of these: a plain class assigns its attributes
    in `__init__`, so `dir()` on the *class* cannot see them and a surface
    derived from `dir()` alone silently omits a member the manual documents by
    name.  Found by the manual's own guard rejecting `Refinement.history`.
    """
    try:
        source = inspect.getsource(cls)
    except (OSError, TypeError):
        return set()
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:  # pragma: no cover - a class body that parses nowhere else either
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and _public(target.attr)
            ):
                found.add(target.attr)
    return found


def declared_members(cls: type) -> dict[str, Entry]:
    """The class's own public members, keyed by qualified name.

    Rule 1: a member counts iff it is one of the model's fields, or the class
    that defines it lives in a rietx module.  Attribution is to the defining
    class, so an inherited method is one entry.
    """
    out: dict[str, Entry] = {}
    fields = set(getattr(cls, "model_fields", None) or {})
    for name in sorted(fields):
        if _public(name):
            out[f"{cls.__name__}.{name}"] = Entry(f"{cls.__name__}.{name}", "field", cls.__name__)
    for name in sorted(dir(cls)):
        if not _public(name) or name in fields or name in _PYDANTIC_CLASS_ATTRS:
            continue
        owner = _defining_class(cls, name)
        if owner is None or not is_rietx(owner):
            continue
        qualified = f"{owner.__name__}.{name}"
        out.setdefault(qualified, Entry(qualified, "member", owner.__name__))
    for name in sorted(_instance_attributes(cls)):
        qualified = f"{cls.__name__}.{name}"
        out.setdefault(qualified, Entry(qualified, "attribute", cls.__name__))
    return out


def _annotated_types(cls: type) -> set[type]:
    """rietx-defined classes reachable from a class's fields and public methods."""
    annotations: list[object] = []
    try:
        annotations.extend(typing.get_type_hints(cls).values())
    except Exception:  # a forward reference that only resolves at runtime
        for field in (getattr(cls, "model_fields", None) or {}).values():
            annotations.append(field.annotation)
    for name in dir(cls):
        if not _public(name):
            continue
        member = inspect.getattr_static(cls, name, None)
        member = member.__func__ if isinstance(member, (classmethod, staticmethod)) else member
        if not inspect.isfunction(member):
            continue
        try:
            annotations.extend(typing.get_type_hints(member).values())
        except Exception:
            continue
    found: set[type] = set()
    stack = list(annotations)
    while stack:
        node = stack.pop()
        if inspect.isclass(node) and is_rietx(node):
            found.add(node)
        stack.extend(arg for arg in typing.get_args(node) if arg is not None)
    return found


def _module_members(module: types.ModuleType) -> list[tuple[str, object]]:
    """A module's own public names — defined there, not imported into it.

    `rietx.agent` declares no `__all__`, so `dir()` on it is mostly the types
    it imported to build its request union; `__module__` is what separates its
    own surface from its imports.
    """
    return [
        (name, value)
        for name in sorted(dir(module))
        if _public(name)
        and getattr(value := getattr(module, name), "__module__", None) == module.__name__
    ]


def _annotated_types_of(func: object) -> set[type]:
    """rietx classes named in a function's signature — its return type above
    all.  `capabilities()` returns a `Capabilities`, which is exported
    nowhere: seeding only from exported *classes* left the one type
    `using/agents.md` documents off the surface entirely.
    """
    try:
        annotations = list(typing.get_type_hints(func).values())
    except Exception:
        return set()
    found: set[type] = set()
    while annotations:
        node = annotations.pop()
        if inspect.isclass(node) and is_rietx(node):
            found.add(node)
        annotations.extend(arg for arg in typing.get_args(node) if arg is not None)
    return found


def _seed_types() -> list[type]:
    """Exported classes, the types exported functions name in their
    signatures, and the classes an exported module defines itself."""
    seeds: list[type] = []
    for name in rietx.__all__:
        obj = getattr(rietx, name)
        if inspect.isclass(obj):
            seeds.append(obj)
        elif isinstance(obj, types.ModuleType):
            for _, value in _module_members(obj):
                seeds.extend([value] if inspect.isclass(value) else _annotated_types_of(value))
        elif callable(obj):
            seeds.extend(_annotated_types_of(obj))
    return seeds


def reachable_types(*, apply_exclusions: bool = True) -> dict[str, type]:
    """The exported classes plus rietx types reachable through them (rule 2)."""
    blocked = set(EXCLUDED_TYPES) if apply_exclusions else set()
    found: dict[str, type] = {}
    frontier: list[type] = []
    for cls in _seed_types():
        if cls.__name__ not in blocked:
            found[cls.__name__] = cls
            frontier.append(cls)
    while frontier:
        for candidate in _annotated_types(frontier.pop()):
            name = candidate.__name__
            if name in found or name in blocked:
                continue
            found[name] = candidate
            frontier.append(candidate)
    return found


def derive_surface(*, apply_exclusions: bool = True) -> dict[str, Entry]:
    """Every public name a caller of this package can reach, keyed by name.

    `apply_exclusions=False` derives the same surface with the exclusions
    below switched off — the only view in which an excluded name is still
    visible, which is how `test_manual_api.py` checks that an exclusion still
    matches something live rather than a name that was renamed away.
    """
    surface: dict[str, Entry] = {}

    for name in rietx.__all__:
        obj = getattr(rietx, name)
        if inspect.isclass(obj) or isinstance(obj, types.ModuleType):
            continue
        kind = "function" if callable(obj) else "constant"
        surface[name] = Entry(name, kind, "rietx")

    for name in rietx.__all__:
        obj = getattr(rietx, name)
        if not isinstance(obj, types.ModuleType):
            continue
        surface[name] = Entry(name, "module", "rietx")
        for member, value in _module_members(obj):
            if inspect.isclass(value):
                continue  # a seed type; it enters the surface under its own name
            if not callable(value):
                continue
            qualified = f"{name}.{member}"
            surface[qualified] = Entry(qualified, "function", name)

    for name, cls in sorted(reachable_types(apply_exclusions=apply_exclusions).items()):
        surface[name] = Entry(name, "class", None)
        surface.update(declared_members(cls))

    if apply_exclusions:
        for name in EXCLUSIONS:
            surface.pop(name, None)
    return surface


def load_deferred() -> list[str]:
    """The generated `deferred-1.0.x` bucket; empty file once WP-1067 closes."""
    if not DEFERRED_PATH.exists():
        return []
    return [
        line.strip()
        for line in DEFERRED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


_DEFERRED_HEADER = """\
# Generated — do not hand-edit.  `python -m tests.api_surface --write-deferred`
#
# The `deferred-1.0.x` bucket of the manual's coverage partition (WP-1067):
# public names the floor chapters do not document, which the post-release
# chapters will.  Generated rather than typed so that a NEW public name is not
# in it, fails the partition, and has to be documented, excluded with a
# reason, or deliberately deferred by regenerating this file — which shows up
# as a diff in review.  WP-1067 closes when this file has no names left.
"""


def write_deferred(documented: set[str]) -> int:
    names = sorted(set(derive_surface()) - documented)
    DEFERRED_PATH.write_text(_DEFERRED_HEADER + "\n".join(names) + "\n", encoding="utf-8")
    return len(names)


def _main() -> None:
    import sys

    surface = derive_surface()
    if "--write-deferred" in sys.argv:
        from tests.test_manual_api import documented_names  # noqa: PLC0415 — CLI only

        print(f"{write_deferred(documented_names())} names deferred -> {DEFERRED_PATH}")
        return
    kinds: dict[str, int] = {}
    for entry in surface.values():
        kinds[entry.kind] = kinds.get(entry.kind, 0) + 1
    print(f"{len(surface)} names on the derived public surface")
    for kind, count in sorted(kinds.items()):
        print(f"  {kind:>9}: {count}")
    print(f"  deferred: {len(load_deferred())}")


if __name__ == "__main__":
    _main()
