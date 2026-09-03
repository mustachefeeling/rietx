"""The landing page (`docs/landing/`, WP-1331): what it may publish, and what it must not.

Three failure modes, none of which any other suite sees.

**The ignore rules, in both directions.** The page's animation replays a
contributor's observed in-situ series. That payload is not in this repository
and may not be (root CLAUDE.md § Licensing: data carries its own fence, per
file), so `docs/landing/data/`, `site/`, `dist/` and `preview.html` are ignored —
and `preview.html` in particular was matched by the `!docs/**/*.html` un-ignore
and would have been committed, 3.2 MB with the payload inlined. The other
direction is the older bug: the repo-wide `*.png` rule has now swallowed four
directories of committed images (Part 1's figures, the GUI chapters'
screenshots, the GUI dist, and this page's four), so `img/` is un-ignored and
asserted here. `git check-ignore` is the only way to ask the question, and
reading `.gitignore` by eye is what failed the first three times
(`tests/test_gui_dist.py` § the `*.html` rule).

**A build product nobody ran.** `build.py --site` is what the Pages workflow
publishes, and until WP-1331 nobody had served its output: the page is authored
as an artifact *fragment*, so without the document skeleton the site build
rendered every `·` and `°C` as mojibake, and the payload fetch its own comments
promised did not exist. Both are asserted on the assembled bytes.

**A link that means the wrong page.** `/` is the landing page now and the manual
is `/manual.html`, so a `https://rietx.org/` in the page that meant "the manual"
silently points at the page itself.

Everything here reads `docs/landing/build.py`'s own tables rather than restating
them, so a new image or a new leak token is covered by adding it there.
"""

from __future__ import annotations

import html as _html
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LANDING = REPO_ROOT / "docs" / "landing"

# One worker for the module: `build.py --site` rmtree's and rewrites
# `docs/landing/site`, so two workers running it at once race over the same
# directory (tests/CLAUDE.md — a shared fixture stays on one worker, and this
# shares a directory rather than a fixture).  The module costs about a second.
#
# And the group is the *manual build's*, not one of its own: `conf.py` puts
# `docs/landing/site` on `html_extra_path`, so a sphinx build on another worker
# copies the very directory this module is rmtree-ing — a `-W` build that fails
# on a file that vanished under it.  Sharing the group keeps the two serialised
# on one worker, which is the only thing `--dist loadgroup` guarantees.
pytestmark = pytest.mark.xdist_group("manual-build")


def _build_module():
    """`docs/landing/build.py` imported by path: it is a script beside the page,
    not a package, and this suite reads its tables rather than copying them."""
    spec = importlib.util.spec_from_file_location("landing_build", LANDING / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def build():
    return _build_module()


@pytest.fixture(scope="module")
def site_html(build) -> str:
    """The site build's bytes, assembled without writing anything."""
    return build.assemble(True)


# ----------------------------------------------------------------------
# What may reach the repository
# ----------------------------------------------------------------------

#: path -> must it be ignored?  The six the move was measured against.
IGNORE_EXPECTED = {
    "docs/landing/src/index.html": False,      # the one source
    "docs/landing/build.py": False,
    "docs/landing/README.md": False,
    "docs/landing/img/fap-light.png": False,   # committed figure, under a repo-wide *.png
    "docs/landing/img/gui-history-dark.png": False,
    "docs/landing/preview.html": True,         # built page, payload inlined
    "docs/landing/dist/index.html": True,
    "docs/landing/site/index.html": True,
    "docs/landing/data/demo.json": True,       # the payload itself
    "docs/landing/data/transcript.json": True,
}


def _ignored(paths: list[str]) -> set[str]:
    """The subset of `paths` git ignores.

    ``--no-index`` because check-ignore consults the index first and answers for
    a *tracked* file from there, which would hide exactly the regression this
    asks about (the same reason `tests/test_gui_dist.py` passes it)."""
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", *paths],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    # rc 0: some path matched.  rc 1: none did.  Anything else is a real failure.
    assert result.returncode in (0, 1), f"git check-ignore failed: {result.stderr}"
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def test_the_payload_cannot_be_committed_and_the_figures_cannot_be_dropped():
    """Both directions at once, because the file gets them wrong both ways: a
    rule that publishes the contributor's data, and a rule that hides the
    page's images while every local checkout still has them."""
    ignored = _ignored(list(IGNORE_EXPECTED))
    for path, want in IGNORE_EXPECTED.items():
        got = path in ignored
        assert got == want, (
            f"{path}: git {'ignores' if got else 'tracks'} it, expected "
            f"{'ignored' if want else 'tracked'}.  See .gitignore's landing-page "
            f"block — order decides there, the last matching rule wins."
        )


def test_the_committed_figures_are_actually_committed():
    """The un-ignore above is necessary and not sufficient: it says git *would*
    take the files.  This says it did — a fresh clone gets the pictures."""
    tracked = subprocess.run(
        ["git", "ls-files", "docs/landing/img"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    build = _build_module()
    for rel in build.IMAGES.values():
        assert f"docs/landing/{rel}" in tracked, (
            f"{rel} is referenced by build.py but not tracked — a clone would "
            f"build the page with a broken image"
        )


def test_no_leak_token_reaches_the_built_page(site_html, build):
    """`build.py` raises on a leak at build time; this is the same question
    asked of the assembled bytes, so a change to `leaks()` that stopped
    raising would still be caught."""
    assert build.leaks(site_html) == []


def test_every_placeholder_is_filled(site_html):
    assert "%%" not in site_html


# ----------------------------------------------------------------------
# What the site build has to be for a web server
# ----------------------------------------------------------------------

def test_the_site_build_is_a_document_not_a_fragment(site_html):
    """The source is authored for the Artifact runtime, which supplies the
    skeleton and refuses a file that brings its own.  A web server supplies
    none of it: without the charset every `·`, `°C` and `θ` on the page is
    mojibake unless the server happens to say utf-8."""
    head = site_html[:400].lower()
    assert head.startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in head
    assert "width=device-width" in head


def test_the_inline_build_stays_a_fragment(build):
    """...and the other build must NOT gain one, or the artifact publish gets a
    document inside a document."""
    if not build.DEMO.exists():
        pytest.skip("no payload in this checkout; the inline build needs one")
    assert not build.assemble(False).lstrip().lower().startswith("<!doctype")


def test_the_page_fetches_the_payload_it_does_not_inline(site_html):
    """The site build leaves the data tag empty on purpose — 1.9 MB inlined is
    1.9 MB before the first paint — so the page has to fetch it.  For a whole
    release the source only *said* it did, and the animation never ran."""
    assert 'id="demo-data"></script>' in site_html.replace("\n", "")
    assert 'fetch(' in site_html, "the site build has nothing to load its payload with"
    for url in ("data/demo.json", "data/transcript.json"):
        assert url in site_html


# ----------------------------------------------------------------------
# Where the page points
# ----------------------------------------------------------------------

def _links(page: str) -> list[str]:
    return re.findall(r'(?:href|src)="([^"]+)"', page)


def test_no_link_means_the_manual_and_lands_on_this_page(site_html):
    """`/` is the landing page since WP-1331 and the manual is `/manual.html`.
    Three links in the page meant "the manual" and pointed at the site root."""
    roots = [a for a in _links(site_html) if a.rstrip("/") == "https://rietx.org"]
    assert len(roots) == 1, (
        f"{len(roots)} links point at the site root; exactly one may (the brand, "
        f"which does mean 'home').  A link meaning the manual is "
        f"https://rietx.org/manual.html."
    )


def test_the_manual_still_gives_up_index_html():
    """The other half of that: sphinx writes its root document to index.html,
    so the landing page only gets `/` while conf.py says otherwise."""
    conf = (REPO_ROOT / "docs" / "manual" / "conf.py").read_text(encoding="utf-8")
    assert 'root_doc = "manual"' in conf
    assert (REPO_ROOT / "docs" / "manual" / "manual.md").is_file()
    assert not (REPO_ROOT / "docs" / "manual" / "index.md").exists()


def test_every_relative_link_resolves_to_something_the_build_writes(site_html, build):
    """A root-relative or bare link in the page has to name a file
    `build.py --site` puts beside it.  Derived from build.py's own tables, so a
    new image is covered by adding it there."""
    written = {"favicon.svg", "data/demo.json", "data/transcript.json"}
    written |= set(build.IMAGES.values())
    for link in _links(site_html):
        if link.startswith(("http://", "https://", "#", "data:", "mailto:")):
            continue
        assert link.lstrip("/") in written, (
            f"{link!r} is not written by build.py --site (it writes {sorted(written)})"
        )


# ----------------------------------------------------------------------
# What the page claims about the package
# ----------------------------------------------------------------------

def test_every_rietx_name_the_page_shows_still_exists(site_html):
    """The page prints a complete script and its output.  A rename in the
    package would leave the published page quoting a call that no longer
    exists, and nothing else in the suite reads this file."""
    rietx = pytest.importorskip("rietx")
    text = _html.unescape(re.sub(r"<[^>]+>", "", site_html))
    names = sorted(set(re.findall(r"\brx\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)", text)))
    assert names, "found no rx.* call in the page — has the example section moved?"
    for dotted in names:
        obj = rietx
        for part in dotted.split("."):
            assert hasattr(obj, part), f"the page shows rx.{dotted}, but {part!r} does not resolve"
            obj = getattr(obj, part)


def test_the_example_the_page_quotes_is_a_script_that_runs(site_html):
    """`examples/` is the one authority for a worked walkthrough (root
    CLAUDE.md).  The page presents its own syntax-highlighted copy, so this
    checks the script exists and is the one the suite runs; what it *prints* is
    `tests/test_examples.py`'s question."""
    assert (REPO_ROOT / "examples" / "fap_lab.py").is_file()
    assert "fap_lab.py" in site_html


def test_build_py_site_runs_and_writes_the_files_it_names(build):
    """The `__main__` half — the copying, and the guard that lets an absent
    payload through.  It writes into `docs/landing/site`, which is gitignored,
    exactly as `tests/test_examples.py` accepts the scripts' PNGs."""
    result = subprocess.run(
        [sys.executable, str(LANDING / "build.py"), "--site"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"build.py --site failed:\n{result.stdout}\n{result.stderr}"
    site = LANDING / "site"
    assert (site / "index.html").is_file()
    assert (site / "favicon.svg").is_file()
    for rel in build.IMAGES.values():
        assert (site / rel).is_file(), f"build.py --site wrote no {rel}"
