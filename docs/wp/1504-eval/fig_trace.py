"""Shim tracer for WP-1504's figure round: what an agent drew, and what it read.

Installed into a *condition's* venv by a ``.pth`` line (``run.py prepare``),
never into the package under test, so every interpreter an agent starts there
is traced however it was invoked.  It is round 1.1's tracer
(``tests/eval_agent_surface/rietx_surface_trace.py``) cut to this round's two
read-outs, and it keeps that tracer's rules: a row is written when the call
returns; ``depth`` is how deep the call sat inside other traced calls; a
wrapper carries ``functools.wraps``, so ``inspect.signature`` shows the subject
nothing (round 1.0's unwrapped tracer sent an agent to the source).

**Renders.**  ``render_structure``, ``build`` and the cut verbs, each with the
keyword names passed, the few keyword values that say which route was taken
(``_VALUES``), and for a render the pixel size of the image it returned.

**Field reads.**  The round asks which numbers of ``fig.report`` an agent read,
so a read of a field of ``FigureReport`` or ``StructureFigure`` is logged
**at depth 0 only** -- the package reading its own fields inside a traced call
is not the agent reading them.  The first read of a field in a process writes a
row; ``repr``/``str`` of the object, and ``__dict__``, write a ``whole`` row,
since printing a report puts every field in the agent's context.  A field the
``before`` tree does not have is simply never read there.

**Attribution** is the run id ``run.py launch`` puts in ``RIETX_FIG_RUN``, with
the working directory beside it as the cross-check: the log path is baked per
condition, not per run, because a venv per run would be 72 of them.
"""

from __future__ import annotations

import atexit
import dataclasses
import functools
import json
import os
import sys
import threading
import time
from importlib.abc import MetaPathFinder
from importlib.machinery import PathFinder

_T0 = time.time()
LOG = os.environ.get("RIETX_FIG_LOG", os.devnull)
RUN = os.environ.get("RIETX_FIG_RUN")

#: (module, attribute) of each traced callable, at its defining module.  The
#: re-exports in ``rietx.viz`` and ``rietx.viz.figure3d`` are found by identity
#: and replaced too, so every spelling an agent can import reaches the wrapper.
_TARGETS = (
    ("rietx.viz.figure3d.render", "render_structure"),
    ("rietx.gui.structure3d", "build"),
    ("rietx.viz.figure3d.cut", "keep"),
    ("rietx.viz.figure3d.cut", "select"),
    ("rietx.viz.figure3d.cut", "plane"),
    ("rietx.viz.figure3d.cut", "sphere"),
    ("rietx.viz.figure3d.cut", "component"),
    ("rietx.viz.figure3d.cut", "periodicity"),
    ("rietx.viz.figure3d.cut", "recolour"),
)
_REEXPORTS = ("rietx.viz", "rietx.viz.figure3d")

#: The classes whose field reads are the round's read-out.
_WATCHED = (
    ("rietx.viz.figure3d.report", "FigureReport", "report"),
    ("rietx.viz.figure3d.render", "StructureFigure", "figure"),
)

#: Keyword values recorded beside the names: each says which route was taken,
#: and none is the user's data.  ``view`` is recorded as its kind unless it is
#: a short string ("c", "auto"), since a rotation is nine floats.
_VALUES = frozenset({
    "view", "mode", "size", "supersample", "dpi", "boundary", "polyhedra",
    "hidden", "atom_labels", "outline", "extent", "max_atoms", "complete",
    "via", "turn", "up",
})

_state = threading.local()
_seen: set[tuple[str, str]] = set()
_counts: dict[str, int] = {}


def _emit(**fields) -> None:
    try:
        cwd = os.getcwd()
    except OSError:  # an agent's script can delete its own directory
        cwd = None
    fields.update(t=round(time.time(), 3), pid=os.getpid(), cwd=cwd, run=RUN)
    try:
        line = (json.dumps(fields, default=str) + "\n").encode()
        fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except (OSError, TypeError, ValueError):
        pass  # a tracer must never break the run it watches


def _short(value):
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, str):
        return value if len(value) <= 24 else "str"
    if isinstance(value, (list, tuple)):
        if all(isinstance(v, (int, float, str)) for v in value) and len(value) <= 6:
            return list(value)
        if all(isinstance(v, (list, tuple)) and len(v) <= 3 for v in value) and len(value) <= 3:
            return [list(v) for v in value]
        return f"{type(value).__name__}[{len(value)}]"
    return type(value).__name__


def _depth() -> int:
    return getattr(_state, "depth", 0)


def _wrap(original, label: str):
    def traced(*args, **kwargs):
        depth = _depth()
        _state.depth = depth + 1
        began, ok, out = time.time(), True, None
        try:
            out = original(*args, **kwargs)
            return out
        except BaseException:
            ok = False
            raise
        finally:
            row = dict(event="call", name=label, kwargs=sorted(kwargs),
                       values={k: _short(v) for k, v in kwargs.items() if k in _VALUES},
                       first=type(args[0]).__name__ if args else None,
                       depth=depth, ok=ok, dt=round(time.time() - began, 4))
            # read while the depth still says "inside a traced call", or the
            # tracer's own look at the image is scored as the agent's
            image = getattr(out, "image", None) if label == "render_structure" else None
            shape = getattr(image, "shape", None)
            if shape is not None and len(shape) >= 2:
                row["pixels"] = [int(shape[1]), int(shape[0])]
            _state.depth = depth
            _emit(**row)

    functools.update_wrapper(traced, original)
    traced._rietx_fig_traced = True
    return traced


def _read(label: str, name: str) -> None:
    key = f"{label}.{name}"
    _counts[key] = _counts.get(key, 0) + 1
    if (label, name) not in _seen:
        _seen.add((label, name))
        _emit(event="read", name=key)


def _watch(cls, label: str) -> None:
    if getattr(cls, "_rietx_fig_watched", False):
        return
    names = frozenset(f.name for f in dataclasses.fields(cls))
    get = cls.__getattribute__

    def __getattribute__(self, name):
        if _depth() == 0 and not getattr(_state, "quiet", False):
            if name in names:
                _read(label, name)
            elif name == "__dict__":
                _read(label, "whole")
        return get(self, name)

    def whole(method):
        @functools.wraps(method)
        def wrapper(self):
            if _depth() == 0:
                _read(label, "whole")
            quiet = getattr(_state, "quiet", False)
            _state.quiet = True
            try:
                return method(self)
            finally:
                _state.quiet = quiet
        return wrapper

    cls.__getattribute__ = __getattribute__
    cls.__repr__ = whole(cls.__repr__)
    if "__str__" in vars(cls):
        cls.__str__ = whole(cls.__str__)
    cls._rietx_fig_watched = True


def _patch() -> None:
    missing = []
    for module_name, attr in _TARGETS:
        module = sys.modules.get(module_name)
        original = getattr(module, attr, None) if module else None
        if original is None:
            missing.append(f"{module_name}.{attr}")
            continue
        if getattr(original, "_rietx_fig_traced", False):
            continue
        traced = _wrap(original, attr)
        for name in (module_name, *_REEXPORTS):
            other = sys.modules.get(name)
            if other is not None and getattr(other, attr, None) is original:
                setattr(other, attr, traced)
    for module_name, attr, label in _WATCHED:
        module = sys.modules.get(module_name)
        cls = getattr(module, attr, None) if module else None
        if cls is None or not dataclasses.is_dataclass(cls):
            missing.append(f"{module_name}.{attr}")
            continue
        _watch(cls, label)
    _emit(event="patched", missing=missing, argv=sys.argv[:8])


#: Patched after whichever of these finishes importing.  ``_patch`` is
#: idempotent and takes what ``sys.modules`` holds, so a run that never
#: imports figure3d still has ``build`` traced, and the ``patched`` row a
#: reader trusts is the last one a process wrote.
_HOOKED = frozenset({"rietx.viz.figure3d", "rietx.gui.structure3d"})


class _Patcher(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname not in _HOOKED:
            return None
        spec = PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        original_exec = spec.loader.exec_module

        def exec_module(module):
            original_exec(module)
            # Nothing is imported from here: structure3d can finish inside
            # figure3d's own import, and importing a sibling then would run
            # the package's imports in an order it never runs them in.
            try:
                _patch()
            except Exception:
                pass

        spec.loader.exec_module = exec_module
        return spec


def _exit() -> None:
    if _counts:
        _emit(event="reads", counts=_counts)
    _emit(event="exit", wall=round(time.time() - _T0, 4))


if not any(isinstance(f, _Patcher) for f in sys.meta_path):
    sys.meta_path.insert(0, _Patcher())
    atexit.register(_exit)
