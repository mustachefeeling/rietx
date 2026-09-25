#!/usr/bin/env python3
"""Copy the pinned uPlot into ``src/rietx/viz/static``, the one step that writes it.

Every browser chart rietx draws builds on uPlot (WP-1461). The GUI bundles it,
while ``rietx watch``, ``rietx compare`` and the page ``write_html`` writes read
it from the installed package. So the package carries one copy, and this script
is the only writer of that copy. ``npm run build`` runs it before vite.

The version statement is the exact pin in ``gui/package.json``. The copy is
refused when the installed package disagrees with the pin, since a stale
``node_modules`` would otherwise vendor the wrong release under the right name.
``tests/test_gui_dist.py`` imports this file by path and holds the vendored
banner's version equal to the pin, in the ordinary suite, where there is no
node.

A pin bump therefore goes: edit the pin (or merge the Dependabot pull request),
``npm --prefix gui install``, ``npm --prefix gui run build``. The vendored
directory is in ``build_info.py``'s digest, so a hand edit of a vendored file
reads as a stale dist.

Usage (from the ``gui/`` directory)::

    python3 scripts/vendor.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

#: Where the copy goes, relative to ``gui/``.
VENDOR_RELATIVE = Path("..") / "src" / "rietx" / "viz" / "static"

#: The npm package, and each file taken from it with the name it is written as.
#: The licence travels beside the code because a file ``write_html`` writes
#: leaves the package, and MIT asks for the notice in every copy.
PACKAGE = "uplot"
FILES = {
    "dist/uPlot.iife.min.js": "uPlot.iife.min.js",
    "dist/uPlot.min.css": "uPlot.min.css",
    "LICENSE": "uPlot.LICENSE",
}

#: The file whose first line names the release: ``/*! <url> (v1.6.32) */``.
BANNERED = "uPlot.iife.min.js"


def pin(gui_dir: Path) -> str:
    """The exact version ``gui/package.json`` pins, refusing a range."""
    deps = json.loads((gui_dir / "package.json").read_text(encoding="utf-8"))
    spec = deps.get("dependencies", {}).get(PACKAGE, "")
    if not re.fullmatch(r"\d+\.\d+\.\d+", spec):
        raise SystemExit(f"gui/package.json must pin {PACKAGE} exactly, "
                         f"not {spec!r}: the vendored copy follows the pin")
    return spec


def banner_version(vendor_dir: Path) -> str | None:
    """The release the vendored file names in its banner, or None without one."""
    try:
        with (vendor_dir / BANNERED).open(encoding="utf-8") as f:
            first = f.readline()
    except OSError:
        return None
    found = re.search(r"\(v(\d+\.\d+\.\d+)\)", first)
    return found.group(1) if found else None


def main() -> int:
    gui_dir = Path(__file__).resolve().parent.parent
    source = gui_dir / "node_modules" / PACKAGE
    wanted = pin(gui_dir)
    if not (source / "package.json").is_file():
        print(f"node_modules has no {PACKAGE}: run `npm --prefix gui ci` first",
              file=sys.stderr)
        return 1
    installed = json.loads((source / "package.json").read_text(encoding="utf-8"))["version"]
    if installed != wanted:
        print(f"node_modules holds {PACKAGE} {installed}, the pin is {wanted}: "
              f"run `npm --prefix gui install` first", file=sys.stderr)
        return 1
    target = (gui_dir / VENDOR_RELATIVE).resolve()
    target.mkdir(parents=True, exist_ok=True)
    for src, name in FILES.items():
        shutil.copyfile(source / src, target / name)
    print(f"vendored {PACKAGE} {wanted} into {VENDOR_RELATIVE.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
