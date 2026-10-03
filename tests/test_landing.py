"""The landing page (`docs/landing/`, WP-1331): what it may publish, and what it must not.

Three failure modes, none of which any other suite sees.

**The ignore rules, in both directions.** `site/`, `dist/` and `preview.html`
are build products and ignored — `preview.html` in particular was matched by the
`!docs/**/*.html` un-ignore and would have been committed, 3.2 MB with the
payload inlined. The other
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
import json
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
def build_demo():
    """`docs/landing/build_demo.py`, imported by path like `build.py` above."""
    spec = importlib.util.spec_from_file_location("landing_build_demo", LANDING / "build_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def site_html(build) -> str:
    """The landing page's site build, assembled without writing anything."""
    return build.assemble(True)


#: Every page `build.py` serves, read off its own table so a new page is covered by
#: adding it there.
PAGE_NAMES = list(_build_module().PAGES)


@pytest.fixture(scope="module", params=PAGE_NAMES)
def any_page(request, build) -> tuple[str, str]:
    """(name, site build) for each page in turn."""
    return request.param, build.assemble(True, request.param)


# ----------------------------------------------------------------------
# What may reach the repository
# ----------------------------------------------------------------------

#: path -> must it be ignored?
IGNORE_EXPECTED = {
    "docs/landing/src/shell.html": False,      # what every page shares
    "docs/landing/src/index.html": False,      # the landing page's own body
    "docs/landing/src/why.html": False,
    "docs/landing/build.py": False,
    "docs/landing/README.md": False,
    "docs/landing/img/fap-light.png": False,   # committed figure, under a repo-wide *.png
    "docs/landing/img/gui-history-dark.png": False,
    "docs/landing/data/demo.json": False,      # committed, and decimated to earn it
    "docs/landing/data/transcript.json": False,
    "docs/landing/preview.html": True,         # built page, payload inlined
    "docs/landing/dist/index.html": True,
    "docs/landing/site/index.html": True,
    "docs/landing/site/why.html": True,
    "docs/landing/dist/why.html": True,
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


#: rietx asks for 5-10 steps across a FWHM and raises PATTERN_UNDERSAMPLED below 5
#: (`optimize.statistics`).  The committed payload has to sit clearly under that: it
#: is what makes the file a figure of the contributor's series rather than the series.
MAX_STEPS_PER_FWHM = 3.0


def test_the_committed_payload_is_below_what_can_be_refined():
    """The redaction is asserted, not merely performed.

    `docs/landing/data/demo.json` is in the repository because it keeps every
    second measured channel; at the acquisition's own step it would be a copy of a
    contributor's unpublished in-situ series.  If someone rebuilds it at full
    resolution — `build_demo.py` takes the factor as an argument and defaults to 1 —
    nothing else would notice.

    Decimation, not averaging, for a reason worth keeping: a mean of k channels
    divides the counting noise by sqrt(k), so the observed cloud tightens onto the
    calculated curve and the difference curve flattens, and the panel then shows a
    better fit than the Rwp printed beside it.
    """
    payload = json.loads((LANDING / "data" / "demo.json").read_text(encoding="utf-8"))
    # .get, not [], so a payload built before the field existed fails with the
    # message rather than a KeyError
    assert payload.get("decimation", 1) >= 2, (
        "the committed payload is at full resolution; rebuild it with a decimation "
        "factor (build_demo.py <bundle> <out> 2)"
    )
    assert payload.get("steps_per_fwhm", 99) <= MAX_STEPS_PER_FWHM, (
        f"{payload['steps_per_fwhm']} steps across a peak is refinable data "
        f"(rietx wants 5-10); rebuild with a larger decimation factor"
    )


def test_the_animation_caption_says_what_the_data_is_and_who_it_is_owed_to(site_html):
    """The rig's caption: what the measurement was, then the credit for it.

    It once described the run and named the support phases; both went when the
    phases did, leaving the credit alone.  WP-1411 put the description back, from
    the section head above the rig, which now opens on what the agent was asked to
    do rather than on the specimen.

    Pinned, and the pin is worth more than an exact string usually is, because the
    credit is the one thing on this page that is owed to somebody and the
    description is the one thing that fences what the payload is.  Neither may
    drift silently: an edit that changes either should have to say so here, which
    is what the 2026-09-14 rewrite did.
    """
    captions = re.findall(r'<p class="caption">(.*?)</p>', site_html, re.S)
    text = re.sub(r"<[^>]+>", "", captions[0]).strip()
    assert text == (
        "The dataset is 275 in situ XRD patterns from a supported Cu/CuO redox "
        "experiment collected on a lab diffractometer with ~30 s acquisitions. "
        "The measurements were made at up to 300&nbsp;&deg;C under changing "
        "chemical environments using a bespoke gas cell. "
        "Contributed by Michael W. Gaultois. Work performed with Jamie Capel, "
        "Martin C. Chan, Stuart Scott, Felix Donat, and Prof. Dame Clare Grey at "
        "the Department of Chemistry, University of Cambridge. "
        "Visualisation constructed by Claude."
    )


def test_the_support_phases_ship_unnamed(build_demo):
    """The payload names the reacting phases; the support formulation is not named at all.

    Cu, Cu2O and CuO are the animation's subject.  The support phases would pin the
    contributor's unpublished sample, so they ship positionally as "support n" — and the
    builder does not know their names either: `phase_columns` reads every other `wtpct_`
    column straight off the bundle's own header.  Deliberately not a `build.LEAK` token,
    because a denylist publishes what it denies.
    """
    payload = json.loads((LANDING / "data" / "demo.json").read_text(encoding="utf-8"))
    support = [ph for ph in payload["phases"] if ph["support"]]
    assert support, "no support phases in the payload"
    for i, ph in enumerate(support, start=1):
        assert ph["name"] == ph["html"] == f"support {i}", ph

    named = [name for _, name, _ in build_demo.REACTING]
    assert [ph["name"] for ph in payload["phases"] if not ph["support"]] == named

    # the mechanism, on a header the bundle could have: whatever the extra columns are
    # called, they come back positional
    cols = build_demo.phase_columns(
        ["series_index"] + [f"wtpct_{c}" for c, *_ in build_demo.REACTING]
        + ["wtpct_SomePhase", "wtpct_Another"])
    assert [name for _, name, _, _ in cols] == named + ["support 1", "support 2"]
    assert [sup for *_, sup in cols] == [False] * len(named) + [True, True]


def test_no_leak_token_reaches_a_built_page(any_page, build):
    """`build.py` raises on a leak at build time; this is the same question
    asked of the assembled bytes, so a change to `leaks()` that stopped
    raising would still be caught."""
    name, page = any_page
    assert build.leaks(page) == [], name


def test_every_placeholder_is_filled(any_page):
    name, page = any_page
    assert "%%" not in page, name


def test_every_page_says_claude_wrote_it(any_page):
    """Anything published under the maintainer's name carries a line saying Claude
    wrote it, and the shell's footer is where each page says so.  The line is per
    page because the pages differ: the essay's words are the maintainer's own."""
    name, page = any_page
    notes = re.findall(r'<span class="note">(.*?)</span>', page, re.S)
    assert len(notes) == 1 and "Claude" in notes[0], f"{name}: {notes}"


# ----------------------------------------------------------------------
# What the site build has to be for a web server
# ----------------------------------------------------------------------

def test_the_site_build_is_a_document_not_a_fragment(any_page):
    """The source is authored for the Artifact runtime, which supplies the
    skeleton and refuses a file that brings its own.  A web server supplies
    none of it: without the charset every `·`, `°C` and `θ` on the page is
    mojibake unless the server happens to say utf-8."""
    head = any_page[1][:400].lower()
    assert head.startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in head
    assert "width=device-width" in head


def test_the_inline_build_stays_a_fragment(build):
    """...and the other build must NOT gain one, or the artifact publish gets a
    document inside a document."""
    assert build.DEMO.exists(), "the payload is committed; this should not be conditional"
    for name in build.PAGES:
        assert not build.assemble(False, name).lstrip().lower().startswith("<!doctype"), name


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


def test_no_link_means_the_manual_and_lands_on_this_page(any_page):
    """`/` is the landing page since WP-1331 and the manual is `/manual.html`.
    Three links in the page meant "the manual" and pointed at the site root."""
    name, page = any_page
    roots = [a for a in _links(page) if a.rstrip("/") == "https://rietx.org"]
    assert len(roots) == 1, (
        f"{name}: {len(roots)} links point at the site root; exactly one may (the brand, "
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


def test_every_relative_link_resolves_to_something_the_build_writes(any_page, build):
    """A root-relative or bare link in a page has to name a file
    `build.py --site` puts beside it, and a fragment has to name an id the page
    it points into carries: the hero's quickstart is reached by `#quickstart`
    from wherever a link to it sits.  Derived from build.py's own tables, so a
    new image or a new page is covered by adding it there."""
    name, page = any_page
    written = {"favicon.svg", "data/demo.json", "data/transcript.json"}
    written |= set(build.IMAGES.values()) | set(build.PAGES)
    for link in _links(page):
        if link.startswith("#"):
            assert f'id="{link[1:]}"' in page, f"{name}: {link!r} names an id the page does not carry"
            continue
        if link.startswith(("http://", "https://", "data:", "mailto:")):
            continue
        path, _, fragment = link.partition("#")
        path = path.lstrip("/")
        path = "index.html" if path in ("", ".", "./") else path.removeprefix("./")
        assert path in written, (
            f"{name}: {link!r} is not written by build.py --site (it writes {sorted(written)})"
        )
        if fragment:
            assert f'id="{fragment}"' in build.assemble(True, path), (
                f"{name}: {link!r} names an id {path} does not carry")


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
    for name in build.PAGES:
        assert (site / name).is_file(), f"build.py --site wrote no {name}"
    assert (site / "favicon.svg").is_file()
    for rel in build.IMAGES.values():
        assert (site / rel).is_file(), f"build.py --site wrote no {rel}"


# ----------------------------------------------------------------------
# The agent quickstart: a prompt somebody pastes, so every command in it runs
# ----------------------------------------------------------------------

def _prompt(site_html: str) -> tuple[str, list[str]]:
    """The quickstart prompt's text, and every `code` span in it."""
    block = re.search(r'<div class="qs-prompt" id="qs-prompt">(.*?)</div>', site_html, re.S)
    assert block, "no quickstart prompt on the landing page"
    codes = [_html.unescape(c) for c in re.findall(r"<code>(.*?)</code>", block.group(1))]
    return _html.unescape(re.sub(r"<[^>]+>", "", block.group(1))), codes


def test_the_quickstart_installs_this_package_from_where_it_lives(site_html):
    """Both install lines name the real package: the PyPI one by the distribution
    name, the GitHub one by the repository `_about` publishes.  The Python floor
    the prompt quotes is pyproject's, which is what pip enforces."""
    about = pytest.importorskip("rietx._about")
    text, codes = _prompt(site_html)
    assert f"pip install {about.DIST_NAME}" in codes
    assert f"pip install git+{about.REPO_URL}" in codes
    floor = re.search(r'requires-python = ">=(\d+\.\d+)"',
                      (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")).group(1)
    assert f"Python {floor} or newer" in text, f"the prompt does not quote Python {floor}"


def test_the_quickstart_skill_command_writes_the_file_it_says_to_read(site_html, tmp_path, monkeypatch):
    """`rietx skill --install`, run where the prompt runs it (the data folder),
    has to leave a SKILL.md at the path the prompt then tells the agent to read.
    Run through the CLI rather than `skill.install`, because the command is what
    the agent types."""
    cli = pytest.importorskip("rietx.cli")
    _, codes = _prompt(site_html)
    command = next(c for c in codes if c.startswith("rietx skill"))
    path = next(c for c in codes if c.endswith("SKILL.md"))
    monkeypatch.chdir(tmp_path)
    assert cli.main(command.split()[1:]) == 0
    assert (tmp_path / path).is_file(), f"{command!r} wrote no {path}"
