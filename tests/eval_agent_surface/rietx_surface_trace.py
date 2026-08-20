"""Shim tracer for the WP-1110 agent-surface round.

Installed into the *experiment* venv's site-packages (never the package under
test) by a ``.pth`` line, so every interpreter that venv starts is traced no
matter how an agent invokes it.  It records which public rietx entry points a
run actually reached -- the round's whole read-out -- so the condition is
enforced by the environment rather than asked for in a prompt.

One JSONL line per event, appended with O_APPEND so concurrent runs interleave
safely.  Every line carries cwd and pid, which is how a line is attributed to a
workspace when an agent runs python from somewhere else.
"""

from __future__ import annotations

import functools
import json
import os
import sys
import time
from importlib.abc import MetaPathFinder
from importlib.machinery import PathFinder

LOG = os.environ.get(
    "RIETX_SURFACE_LOG",
    "/Users/yue/.claude/jobs/9d6b0544/tmp/surface_trace.jsonl",
)

# dotted attribute paths below the ``rietx`` module, resolved after it executes
_TARGETS = (
    "agent.refine_json", "agent.tool_definition", "agent.request_schema",
    "agent.response_schema",
    "capabilities", "read_pattern",
    "crystallography.cif.structure_from_cif",
    "refine", "refine_sequential", "refine_multi", "replay",
    "index_pattern", "build_report", "diagnose", "auto_background",
    "load_instrument_profile", "save_instrument_profile",
    "Refinement.fit", "Refinement.run_stage", "Refinement.predict",
    "Refinement.parameters", "Refinement.set_vary", "Refinement.set_values",
    "Refinement.branch", "Refinement.checkout", "Refinement.tie",
    "SequentialRefinement.run",
    "Project.create", "Project.open", "Project.save",
)


def _emit(**fields) -> None:
    fields.update(t=round(time.time(), 3), pid=os.getpid(), cwd=os.getcwd())
    line = (json.dumps(fields, default=str) + "\n").encode()
    try:
        fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except OSError:
        pass


def _wrap(owner, attr: str, label: str) -> None:
    """Replace ``owner.attr`` with a logging passthrough.

    ``getattr`` resolves the descriptor for us, so a classmethod comes back
    bound and an instance method comes back as the plain function taking
    ``self`` first: calling ``original(*args)`` is correct either way, and the
    replacement is a plain function in both.
    """
    original = getattr(owner, attr, None)
    if original is None or getattr(original, "_rietx_traced", False):
        return

    def traced(*args, **kwargs):
        # the first positional argument is logged ONLY when it is a path -- it
        # is what attributes a process to a workspace when an agent runs python
        # from elsewhere and `python -c` leaves nothing in argv.  No other
        # argument value is ever recorded.
        path = None
        if args and isinstance(args[0], (str, os.PathLike)):
            candidate = os.fspath(args[0])
            if os.sep in candidate:
                path = candidate
        _emit(event="call", name=label, kwargs=sorted(kwargs), nargs=len(args),
              path=path)
        return original(*args, **kwargs)

    # functools.wraps, not a hand-copied __name__: round 1.0 wrapped without it,
    # so inspect.signature showed `traced(*args, **kwargs)` and one agent went to
    # source to recover a signature.  A shim the subject can see is an
    # observation effect, and this is the cheapest way to close it.
    functools.update_wrapper(traced, original)
    traced._rietx_traced = True
    try:
        setattr(owner, attr, traced)
    except (AttributeError, TypeError):
        pass


def _patch(module) -> None:
    import importlib

    try:
        importlib.import_module("rietx.agent")
        importlib.import_module("rietx.crystallography.cif")
    except Exception:
        pass
    for path in _TARGETS:
        owner, _, attr = path.rpartition(".")
        target = module
        try:
            for part in owner.split("."):
                if part:
                    target = getattr(target, part)
        except AttributeError:
            continue
        _wrap(target, attr, path)
    _emit(event="import", argv=sys.argv[:12])


class _Patcher(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != "rietx":
            return None
        spec = PathFinder.find_spec(fullname, path)  # bypasses meta_path
        if spec is None or spec.loader is None:
            return None
        loader = spec.loader
        original_exec = loader.exec_module

        def exec_module(module):
            original_exec(module)
            try:
                _patch(module)
            except Exception:  # a tracer must never break the run it watches
                pass

        loader.exec_module = exec_module
        return spec


if not any(isinstance(f, _Patcher) for f in sys.meta_path):
    sys.meta_path.insert(0, _Patcher())
