"""WP-1010 — the committed frontend dist: is it current, and is it offline?

The dist under ``src/rietx/gui/static`` is committed so installing the wheel
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
DIST = ROOT / "src" / "rietx" / "gui" / "static"

REBUILD = "run `npm --prefix gui ci && npm --prefix gui run build` and commit the result"


def _build_info_module():
    """``gui/scripts/build_info.py``, imported by path (it imports no package)."""
    path = GUI_DIR / "scripts" / "build_info.py"
    if not path.is_file():
        pytest.skip(f"{path} is missing — the gui workspace is not in this checkout")
    spec = importlib.util.spec_from_file_location("rietx_gui_build_info", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(scope="module")
def build_info():
    return _build_info_module()


def test_the_dist_is_present_and_named_as_the_server_expects():
    """Stable filenames, because a committed dist has to diff reviewably."""
    from rietx.gui.server import STATIC_DIR

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
    --exit-code src/rietx/gui/static`` has to mean "stale", not "rebuilt".
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
    # --no-index because check-ignore consults the index first, and answers for
    # a *tracked* file without asking the ignore rules at all: every file here
    # is committed, so without it this test was green while asking nothing
    # (WP-1062).  The question is what the rules say, not what the index says.
    result = subprocess.run(
        ["git", "check-ignore", "-v", "--no-index", *[str(f) for f in files]],
        cwd=ROOT, capture_output=True, text=True)
    # the filter is on the *shape* of the matching rule, not its text (WP-1062):
    # check-ignore -v reports the last rule that matched, and one starting with
    # ``!`` is a negation — the file is not ignored, which is the answer wanted.
    # Spelling the un-ignore path here would be a second copy of a .gitignore
    # line: rename the package, update one of the two, and this stops testing
    # anything while still passing.
    ignored = [line for line in result.stdout.splitlines()
               if line and not line.split("\t")[0].rpartition(":")[2].startswith("!")]
    assert not ignored, f"the committed dist is gitignored: {ignored}"


#: What `npm run build` reads that is **not** under `gui/src/**`.
#:
#: `src/**` needs no list: it is `SOURCE_GLOBS`, so a file missing from a clone
#: changes the digest and `test_the_dist_is_current` fails.  These sit outside
#: the digest *and* outside the dist, which is precisely the blind spot that let
#: the entry point go missing — so they are enumerated.
BUILD_INPUTS = (
    "index.html",          # vite's entry module; the one that broke
    "vite.config.ts",
    "svelte.config.js",
    "tsconfig.json",
    "package.json",
    "package-lock.json",   # the version statement ATTRIBUTION.md cites
    "scripts/build_info.py",
)


def test_a_fresh_clone_can_rebuild_the_frontend():
    """The dist trap's other half, and the half that was still open.

    ``test_nothing_gitignores_the_dist`` guards the build's *output*: the
    repo-wide ``*.html`` rule matched ``static/index.html``, so WP-1010
    un-ignored the whole dist. The same rule also matched **``gui/index.html``**
    — vite's entry module — and nothing noticed for six work packages, because
    the file exists on every machine that has ever run the build and it is
    outside both the digest and the dist. CI found it on the first clean-clone
    build with ``[UNRESOLVED_ENTRY] Cannot resolve entry module index.html``.

    ``git ls-files`` rather than ``git check-ignore``: "not ignored" is the
    weaker question, and this file was *both* ignored and never added. What a
    fresh clone gets is what git tracks.
    """
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "--", *[f"gui/{name}" for name in BUILD_INPUTS]],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    missing = [name for name in BUILD_INPUTS if f"gui/{name}" not in tracked]
    assert not missing, (
        f"the frontend cannot be built from a clean checkout — untracked: {missing}")


@pytest.fixture(scope="module")
def wheel_entries(tmp_path_factory):
    """``{name: uncompressed size}`` of the built wheel, built once.

    Several questions are asked of it (what must be in, what must not, how big
    the package data is), and a wheel build is seconds rather than
    milliseconds, so the module fixture is pinned to one worker by
    ``xdist_group`` like every other shared build here.
    """
    import glob
    import subprocess
    import zipfile

    uv = subprocess.run(["uv", "--version"], capture_output=True)
    if uv.returncode != 0:
        pytest.skip("uv is not installed; wheel packaging is checked in CI")
    out = tmp_path_factory.mktemp("wheel")
    build = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out)],
        cwd=ROOT, capture_output=True, text=True)
    assert build.returncode == 0, build.stderr[-2000:]
    wheel = glob.glob(str(out / "*.whl"))[0]
    return {i.filename: i.file_size for i in zipfile.ZipFile(wheel).infolist()}


@pytest.fixture(scope="module")
def wheel_names(wheel_entries):
    return set(wheel_entries)


@pytest.mark.xdist_group("wheel-build")
def test_the_dist_is_in_the_wheel(wheel_names):
    """"Installing the wheel never needs node" is only true if this holds.

    Hatchling includes a package directory's non-ignored files, so this passed
    for free until WP-1110 added an exclude pattern — which is the day this test
    was written for.  Measured rather than assumed, because the whole design
    (a committed build output) rests on it.
    """
    inside = wheel_names
    wanted = ["rietx/gui/static/index.html", "rietx/gui/static/assets/app.css",
              "rietx/gui/static/build-info.json"]
    # every chunk, so a new one cannot ship as a 404 at the moment the pane that
    # needs it is opened
    wanted += [f"rietx/gui/static/assets/{p.name}"
               for p in sorted((DIST / "assets").glob("*.js"))]
    # the agent protocol rides the same build (WP-1003): force-included as
    # package data so a pip-only agent with no network has its own copy
    # offline (it was the JSON tool description's pointer until WP-1303)
    wanted.append("rietx/data/AGENT_PROTOCOL.md")
    # the GUI's *python* modules, not only its static assets: the sdist
    # excludes are gitignore-style, and an unanchored "gui" pattern once
    # matched src/rietx/gui too — the static files survived on a `!` negation
    # while the server code vanished, so a wheel install broke at the first
    # capabilities() call (WP-1003, 2026-08-16)
    wanted += ["rietx/gui/__init__.py", "rietx/gui/textdoc.py"]
    for name in wanted:
        assert name in inside, f"{name} is missing from the wheel"


@pytest.mark.xdist_group("wheel-build")
def test_the_example_inputs_are_in_the_wheel(wheel_entries):
    """The empty state's examples are package data, so they have to ship.

    Hatchling takes a package directory's non-ignored files, so this needed no
    ``pyproject`` entry — which is exactly why it needs a test: the examples
    are in the wheel by a default that a future exclude pattern could take
    away silently, the way WP-1110's ``**/CLAUDE.md`` exclude nearly did to the
    dist above.

    Asserted against ``list_examples()`` rather than a list of filenames: the
    example list is *derived* from what is in the directory, so a file that
    failed to ship would otherwise take its example out of the list and out of
    the assertion together.
    """
    from rietx.examples import _standards

    for std in _standards():
        for name in std.files:
            assert f"rietx/data/examples/{name}" in wheel_entries, (
                f"{name} is missing from the wheel")


@pytest.mark.xdist_group("wheel-build")
def test_the_example_inputs_stay_under_their_ceiling(wheel_entries):
    """A ceiling on the *examples*, not on the wheel.

    3.5 MB uncompressed against the ~520 kB they add deflated (2026-08-25:
    2.49 MB of examples in a 2.71 MB wheel).  The ceiling is here to make
    adding a large pattern a decision rather than an accident — 11-BM's SRM
    660a alone is 5.6 MB, and it was left out for that reason as much as any
    other.  Raise it deliberately; do not let it drift.
    """
    total = sum(size for name, size in wheel_entries.items()
                if name.startswith("rietx/data/examples/"))
    assert total <= 3.5 * 1024 * 1024, f"examples are {total / 1048576:.2f} MB"


@pytest.mark.xdist_group("wheel-build")
def test_the_wheel_ships_no_maintainer_rulebook(wheel_names):
    """A CLAUDE.md addresses a session changing rietx, not anyone installing it.

    `gui/`, `indexing/` and `io/` keep their rulebooks beside the code they
    govern, which puts them under the package directory — so all three shipped
    to site-packages, and an agent driving a real refinement read one there as
    though it were the package's documentation (WP-1110 item 20).  They cite
    `tests/`, `docs/wp/` and commands an installed copy does not have.

    The consumer-facing document is the force-included `AGENT_PROTOCOL.md`
    asserted above, which is why this is an exclusion and not a warning.  The
    pattern is a glob rather than three paths: a fourth rulebook lands next to
    its subsystem, never on a list here.
    """
    assert not [n for n in wheel_names if Path(n).name == "CLAUDE.md"]


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
