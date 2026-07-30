"""WP-1010 — the committed frontend dist: is it current, and is it offline?

The dist under ``src/pxrdref/gui/static`` is committed so installing the wheel
never needs node, which buys one hazard: a dist built from sources that have
since moved.  These tests are the guard, and they run in the **ordinary** suite —
no node, no npm, milliseconds — because a check that only runs where node is
installed is a check that does not run.

The digest is not re-implemented here.  ``gui/scripts/build_info.py`` defines it
and this module imports that file by path, so there is exactly one answer to
"which files decide whether the dist is stale" (the WP sketched a JS hasher plus
a Python re-implementation; that is two answers to one question, and this repo
has paid for that shape before).
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GUI_DIR = ROOT / "gui"
DIST = ROOT / "src" / "pxrdref" / "gui" / "static"

REBUILD = "run `npm --prefix gui ci && npm --prefix gui run build` and commit the result"


def _build_info_module():
    """``gui/scripts/build_info.py``, imported by path (it imports no package)."""
    path = GUI_DIR / "scripts" / "build_info.py"
    if not path.is_file():
        pytest.skip(f"{path} is missing — the gui workspace is not in this checkout")
    spec = importlib.util.spec_from_file_location("pxrdref_gui_build_info", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(scope="module")
def build_info():
    return _build_info_module()


def test_the_dist_is_present_and_named_as_the_server_expects():
    """Stable filenames, because a committed dist has to diff reviewably."""
    from pxrdref.gui.server import STATIC_DIR

    assert STATIC_DIR == DIST
    assert (DIST / "index.html").is_file()
    assert (DIST / "assets" / "app.js").is_file()
    assert (DIST / "assets" / "app.css").is_file()
    # no content hashes: a hashed name turns every rebuild into a rename
    assert not [p for p in (DIST / "assets").iterdir()
                if re.search(r"-[0-9a-zA-Z_]{8}\.(js|css)$", p.name)]


def test_the_dist_matches_the_sources_it_was_built_from(build_info):
    """The freshness gate.  A mismatch is a stale dist, not a broken test."""
    recorded = json.loads((DIST / "build-info.json").read_text(encoding="utf-8"))
    digest, count = build_info.source_hash(GUI_DIR)
    assert recorded["source_hash"] == digest, (
        f"the committed dist was built from different sources — {REBUILD}")
    assert recorded["n_source_files"] == count


def test_build_info_carries_nothing_time_varying(build_info):
    """A timestamp would make every rebuild a dist diff.

    Which would destroy the property the digest exists to give: ``git diff
    --exit-code src/pxrdref/gui/static`` has to mean "stale", not "rebuilt".
    """
    recorded = json.loads((DIST / "build-info.json").read_text(encoding="utf-8"))
    assert set(recorded) == {"source_hash", "n_source_files", "hashed_by", "note"}
    # …and rebuilding the stamp is idempotent
    again = dict(recorded)
    digest, count = build_info.source_hash(GUI_DIR)
    assert (again["source_hash"], again["n_source_files"]) == (digest, count)


def test_the_page_references_no_external_asset():
    """The offline guarantee, executable.

    A strict-CSP or air-gapped machine must need no exception, so the page may
    not name a single remote host.  plotly.js is the interesting case: it is
    fetched at runtime from ``/plotly.js``, which the server reads out of the
    installed ``plotly`` package — no 4.8 MB vendored copy in the dist, and no
    CDN.
    """
    html = (DIST / "index.html").read_text(encoding="utf-8")
    js = (DIST / "assets" / "app.js").read_text(encoding="utf-8")
    # every built script, not just the entry: WP-1013 added chunks, and a
    # vendored library is exactly where a CDN fallback or a sourcemap URL hides
    built = [("index.html", html)] + [(p.name, p.read_text(encoding="utf-8"))
                                      for p in sorted((DIST / "assets").glob("*.js"))]
    for name, text in built:
        remote = re.findall(r"""["'(]((?:https?:)?//[^"')\s]+)""", text)
        # An XML namespace is an *identifier*, not an address: CodeMirror passes
        # `http://www.w3.org/2000/svg` to `createElementNS`, which no browser
        # ever fetches. Nothing else on that host is a legitimate asset either,
        # so the exemption is the host rather than the exact strings.
        remote = [url for url in remote if "//www.w3.org/" not in url]
        # a comment may mention a URL; an *asset reference* may not exist
        assert not remote, f"{name} references remote assets: {remote[:3]}"
    assert "/plotly.js" in js  # …and it does load plotly, from us
    assert 'src="/assets/app.js"' in html


def test_codemirror_is_split_out_and_off_the_boot_path():
    """"The editor is fetched when the text pane opens" is a claim, so measure it.

    CodeMirror is the app's one real dependency (WP-1013) and it is a *separate*
    chunk for two reasons that both stop being true silently. A committed dist
    has to diff reviewably, and ~330 kB of minified third-party bytes folded into
    `app.js` would sit in the middle of every application diff. And the boot path
    is the number WP-1010/1012 measured — the page loads `app.js` and nothing
    else, so the editor may not be reachable from it except through a dynamic
    import. A stray static import in a panel would inline the whole library and
    neither symptom would show up in a test that only counts bytes.
    """
    html = (DIST / "index.html").read_text(encoding="utf-8")
    app = (DIST / "assets" / "app.js").read_text(encoding="utf-8")
    vendor = DIST / "assets" / "vendor-cm.js"

    assert vendor.is_file(), REBUILD
    # the library is in the vendor chunk and not in the entry
    assert "@codemirror" not in app or "vendor-cm" in app
    assert "rectangularSelection" not in app, (
        "CodeMirror was inlined into app.js — check that panels/Text.svelte "
        "still imports lib/editor.ts dynamically")
    assert len(app.encode()) < len(vendor.read_bytes())

    # the page pulls the entry only; the chunk is named by the entry, on demand
    assert "vendor-cm" not in html
    assert "/assets/app.js" in html
    assert "vendor-cm.js" in app or "editor.js" in app


def test_the_sources_the_digest_covers_are_the_ones_that_matter(build_info):
    """Config files count, and vitest files count.

    A ``vite.config.ts`` change can alter the output without touching a
    component, and a ``.test.ts`` file is a source of the workspace even though
    it is not bundled — excluding either would let a real change look current.
    """
    covered = {p.relative_to(GUI_DIR).as_posix()
               for p in build_info.source_files(GUI_DIR)}
    assert {"vite.config.ts", "tsconfig.json", "package.json",
            "package-lock.json", "index.html",
            "scripts/build_info.py"} <= covered
    assert any(name.endswith(".svelte") for name in covered)
    assert any(name.endswith(".test.ts") for name in covered)
    # the dist itself is never part of its own digest
    assert not any(name.startswith("../") for name in covered)


def test_nothing_gitignores_the_dist():
    """The trap this WP nearly shipped, made permanent.

    The repo-wide ``*.html`` rule (there for the exporters' output) matched
    ``static/index.html``, so the committed dist would have been missing its
    entry point: the freshness test passes on the machine that built it while a
    fresh clone serves the placeholder page instead of the app.  ``git
    check-ignore`` is the only way to ask the question.
    """
    import subprocess

    files = [DIST / "index.html", DIST / "build-info.json",
             DIST / "assets" / "app.css", *sorted((DIST / "assets").glob("*.js"))]
    result = subprocess.run(
        ["git", "check-ignore", "-v", *[str(f) for f in files]],
        cwd=ROOT, capture_output=True, text=True)
    ignored = [line for line in result.stdout.splitlines()
               if line and not line.split("\t")[0].endswith("!src/pxrdref/gui/static/**")]
    assert not ignored, f"the committed dist is gitignored: {ignored}"


def test_the_dist_is_in_the_wheel(tmp_path):
    """"Installing the wheel never needs node" is only true if this holds.

    Hatchling includes a package directory's non-ignored files, so this passes
    for free today — and would stop the day someone adds an exclude pattern or
    re-ignores the dist.  Measured rather than assumed, because the whole design
    (a committed build output) rests on it.
    """
    import glob
    import subprocess
    import zipfile

    uv = subprocess.run(["uv", "--version"], capture_output=True)
    if uv.returncode != 0:
        pytest.skip("uv is not installed; wheel packaging is checked in CI")
    build = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True)
    assert build.returncode == 0, build.stderr[-2000:]
    wheel = glob.glob(str(tmp_path / "*.whl"))[0]
    inside = set(zipfile.ZipFile(wheel).namelist())
    wanted = ["pxrdref/gui/static/index.html", "pxrdref/gui/static/assets/app.css",
              "pxrdref/gui/static/build-info.json"]
    # every chunk, so a new one cannot ship as a 404 at the moment the pane that
    # needs it is opened
    wanted += [f"pxrdref/gui/static/assets/{p.name}"
               for p in sorted((DIST / "assets").glob("*.js"))]
    for name in wanted:
        assert name in inside, f"{name} is missing from the wheel"


def test_a_source_edit_changes_the_digest(build_info, tmp_path):
    """The guard has to actually fire — a digest that ignores an edit is decor."""
    import shutil

    copy = tmp_path / "gui"
    shutil.copytree(GUI_DIR, copy,
                    ignore=shutil.ignore_patterns("node_modules", ".vite"))
    before, _ = build_info.source_hash(copy)
    assert before == build_info.source_hash(GUI_DIR)[0]  # copying changes nothing

    (copy / "src" / "app.css").write_text("/* nudged */\n", encoding="utf-8")
    assert build_info.source_hash(copy)[0] != before
