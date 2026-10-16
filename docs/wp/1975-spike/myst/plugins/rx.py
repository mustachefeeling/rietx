#!/usr/bin/env python3
"""Spike: the manual's {source} role and a package-constant role as a MyST executable plugin."""
import argparse
import importlib
import inspect
import json
import sys
from pathlib import Path

from rietx._about import REPO_URL  # a brand token, spelled in _about only

CONSTANTS = {"MIN_GAMMA_G2": ("rietx.model.profiles.caglioti", "_MIN_GAMMA_G2", "{:g}")}

plugin = {
    "name": "rietx",
    "roles": [
        {"name": "source", "doc": "Link a dotted name to its source line.", "body": {"type": "string"}},
        {"name": "const", "doc": "A constant read from the installed package.", "body": {"type": "string"}},
    ],
}


def source(dotted):
    import rietx
    module, _, attr = dotted.rpartition(".")
    obj = getattr(importlib.import_module(module), attr)
    path = Path(inspect.getsourcefile(obj)).resolve()
    rel = path.relative_to(Path(rietx.__file__).resolve().parents[2])
    line = inspect.getsourcelines(obj)[1]
    url = f"{REPO_URL}/blob/main/{rel}#L{line}"
    return [{"type": "emphasis", "children": [{"type": "text", "value": "Source: "}]},
            {"type": "link", "url": url, "children": [{"type": "inlineCode", "value": dotted}]}]


def const(name):
    module, attr, fmt = CONSTANTS[name]
    return [{"type": "text", "value": fmt.format(getattr(importlib.import_module(module), attr))}]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role")
    parser.add_argument("--directive")
    parser.add_argument("--transform")
    args = parser.parse_args()
    if args.role:
        data = json.load(sys.stdin)
        body = data["body"].strip()
        json.dump(source(body) if args.role == "source" else const(body), sys.stdout)
    else:
        json.dump(plugin, sys.stdout)
