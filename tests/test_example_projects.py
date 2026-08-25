"""WP-1204 — the example projects shipped in the wheel.

Not ``test_examples.py``, which runs the ``examples/`` scripts the manual
``{literalinclude}``s.  These are ``.rex`` *projects* built from packaged data
for the GUI's empty state.

Nothing here fits anything: a build is a :meth:`Project.create`, so the whole
suite is milliseconds and carries no ``slow`` mark.  What it asserts is that
each project records the protocol its standard declares — a project whose plan
or excluded regions quietly differed would put a user's first refinement on a
protocol no acceptance suite measures.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.examples import (
    BLURBS,
    ExampleInfo,
    build_example,
    examples_dir,
    list_examples,
)
from rietx.viz.compare import STANDARD_BY_KEY

EXAMPLES = list_examples()
NAMES = [e.name for e in EXAMPLES]

#: Why every shipped file may be redistributed, quoted from
#: ``tests/data/README.md``.  A hand-written table on purpose, and the one
#: place in this package where that is the right shape: the point is that a
#: file cannot enter the wheel without someone stating its licence.  The IUCr
#: CPD round-robin patterns carry no explicit licence and are already excluded
#: from the sdist, which is why the four pure-phase standards built on them are
#: not examples however small and useful they are.
LICENCES = {
    "nist_srm660c_100a.cif": "NIST open data licence (U.S. Government work)",
    "11BM_NAC.fxye": "Argonne/APS tutorial data (U.S. Government work)",
    "cod_1000236.cif": "COD (public domain dedication)",
    "FAP.XRA": "Argonne/APS tutorial data (U.S. Government work)",
}


def test_this_build_carries_examples():
    """A guard against the whole suite passing vacuously if the data directory
    failed to ship: every assertion below is parametrised over the list."""
    assert NAMES, "no examples shipped — check src/rietx/data/examples/"


def test_the_list_is_in_bijection_with_the_data_directory():
    """The list is *derived* from the directory (``Standard.available``), so
    the failure this catches is a file with no example rather than the other
    way round — an input copied in for a standard that cannot ship, or one left
    behind by a standard that was removed."""
    on_disk = {str(p.relative_to(examples_dir()))
               for p in examples_dir().rglob("*") if p.is_file()}
    claimed = {f for name in NAMES for f in STANDARD_BY_KEY[name].files}
    assert on_disk == claimed


def test_every_shipped_file_has_a_stated_licence():
    """Ship-ability is a licence question, not a size one."""
    on_disk = {str(p.relative_to(examples_dir()))
               for p in examples_dir().rglob("*") if p.is_file()}
    assert on_disk == set(LICENCES)
    assert not [f for f in on_disk if f.startswith("qarr/")], (
        "the IUCr CPD round-robin patterns carry no explicit licence and are "
        "kept out of the sdist; a wheel on PyPI publishes them harder still")


def _scan_regions(two_theta) -> int:
    """Contiguous scan regions in a pattern — 1 for an ordinary continuous scan.

    A gap is a step more than 5x the median, which separates "the file skips a
    stretch" from ordinary step jitter and from a step that changes smoothly
    with angle (SRM 660c's own goes 0.008 -> 0.016 across its 24 windows).
    """
    step = np.diff(np.asarray(two_theta, dtype=float))
    return 1 + int((step > 5 * np.median(step)).sum())


def test_the_first_example_is_a_continuous_scan():
    """Gaps in a pattern read as broken data to a stranger, and the first
    example is the one clicked by someone with no way to know otherwise.

    SRM 660c is 24 step-scan windows with nothing measured between them (39 %
    of its 20.3-150.9° span) because that is what a certification measurement
    spends its counting time on.  That is worth shipping and worth explaining;
    it is not worth putting first.  The order is `BLURBS`', which is why this
    assertion has somewhere to bind.
    """
    first = STANDARD_BY_KEY[NAMES[0]].build(examples_dir()).data
    assert _scan_regions(first.two_theta) == 1, (
        f"the first example ({NAMES[0]}) is a stitched multi-region scan")


def test_a_gapped_example_says_so_before_it_is_opened():
    """The blurb is the only thing a person reads before clicking, so a dataset
    whose own shape would surprise them has to spend a sentence on it."""
    for e in EXAMPLES:
        data = STANDARD_BY_KEY[e.name].build(examples_dir()).data
        if _scan_regions(data.two_theta) > 1:
            assert "gap" in e.description or "window" in e.description, (
                f"{e.name} is a stitched scan and its blurb does not mention it")


def test_the_list_is_ordered_by_the_blurbs():
    """Membership is derived from the directory and order is `BLURBS`', so a
    shipped file with no blurb is still listed — and still fails the bijection
    above — rather than being filtered out of the list it is missing from."""
    assert NAMES == [k for k in BLURBS if k in {e.name for e in EXAMPLES}]


def test_every_example_has_a_blurb_and_every_blurb_an_example():
    """``BLURBS`` is the one hand-written half of ``ExampleInfo``, so it is the
    half that can drift."""
    assert set(BLURBS) == set(NAMES)
    for e in EXAMPLES:
        assert e.description == BLURBS[e.name]
        assert e.title == STANDARD_BY_KEY[e.name].title
        assert e.bytes > 0


def test_example_info_says_what_the_files_actually_weigh():
    for e in EXAMPLES:
        want = sum((examples_dir() / f).stat().st_size
                   for f in STANDARD_BY_KEY[e.name].files)
        assert e.bytes == want


@pytest.mark.parametrize("name", NAMES)
def test_an_example_records_the_protocol_its_standard_declares(name, tmp_path):
    """Field by field against ``build()``'s own answer, which is what
    ``tests/test_compare_ui.py`` pins to the acceptance suites.  Two copies
    would be one too many; this asserts there is only one."""
    inputs = STANDARD_BY_KEY[name].build(examples_dir())
    project = build_example(name, tmp_path)

    assert project.path == tmp_path / f"{name}.rex"
    assert project.doc.mode == "rietveld"
    assert project.doc.two_theta_limits == inputs.two_theta_limits
    assert [tuple(r) for r in project.doc.excluded_regions] == \
           [tuple(r) for r in inputs.data.excluded_regions]
    assert [s.name for s in project.doc.plan.stages] == \
           [s.name for s in inputs.plan.stages]
    assert [list(s.turn_on) for s in project.doc.plan.stages] == \
           [list(s.turn_on) for s in inputs.plan.stages]
    assert project.doc.plan.intermediate_ftol == inputs.plan.intermediate_ftol

    # the reader *call*, not merely the bytes: a pdCIF with a _meas and a _calc
    # block is a different pattern depending on `block`
    assert dict(project.data_ref.options) == dict(
        STANDARD_BY_KEY[name].reader_options)


@pytest.mark.parametrize("name", NAMES)
def test_an_example_fits_the_channels_its_protocol_leaves(name, tmp_path):
    """``fitted_mask`` is the one authority for which channels the next run
    fits, and it is where the limits and exclusions become a number.  On the
    fluorapatite example that number is GSAS's own 5750, which is what makes
    the two codes' agreement indices comparable at all."""
    inputs = STANDARD_BY_KEY[name].build(examples_dir())
    project = build_example(name, tmp_path)

    kept = np.asarray(inputs.data.two_theta, dtype=float)
    if inputs.two_theta_limits is not None:
        lo, hi = inputs.two_theta_limits
        kept = kept[(kept >= lo) & (kept <= hi)]
    for lo, hi in inputs.data.excluded_regions:
        kept = kept[(kept < lo) | (kept > hi)]
    assert int(project.fitted_mask().sum()) == kept.size


@pytest.mark.parametrize("name", NAMES)
def test_an_example_is_built_unfitted(name, tmp_path):
    """WP-1204's non-goal, asserted rather than intended: a build writes the
    starting values, and the refinement is the user's first click."""
    project = build_example(name, tmp_path)
    assert len(project.history) == 1
    assert project.refinement.result_ is None


@pytest.mark.parametrize("name", NAMES)
def test_a_built_example_reopens(name, tmp_path):
    """``Project.open`` re-reads the directory and checks the pattern's sha256
    *and* its parsed-array fingerprint, so this is where a copied-in file that
    is not what the reference says it is would be caught."""
    built = build_example(name, tmp_path)
    reopened = rx.Project.open(built.path)
    assert reopened.data_ref.sha256 == built.data_ref.sha256
    assert reopened.data_ref.n_points == built.data_ref.n_points


def test_an_unknown_example_names_what_this_build_carries(tmp_path):
    with pytest.raises(KeyError) as exc:
        build_example("corundum", tmp_path)
    assert all(n in str(exc.value) for n in NAMES)


def test_building_the_same_example_twice_refuses_rather_than_overwrites(tmp_path):
    build_example(NAMES[0], tmp_path)
    with pytest.raises(FileExistsError):
        build_example(NAMES[0], tmp_path)


def test_the_packaged_inputs_are_byte_identical_to_the_test_data():
    """The examples are copies of files ``tests/data/README.md`` documents, and
    the acceptance suites measure the originals.  A divergence would make the
    reference values in that README describe a file nobody ships."""
    import hashlib

    source = Path(__file__).parent / "data"
    for name in sorted(LICENCES):
        if not (source / name).exists():
            pytest.skip(f"{name} is not present in tests/data")
        packaged = (examples_dir() / name).read_bytes()
        original = (source / name).read_bytes()
        assert hashlib.sha256(packaged).digest() == \
               hashlib.sha256(original).digest(), name


def test_example_info_is_what_a_client_serialises():
    """Four fields and no more: the GUI's empty state renders this verbatim."""
    import dataclasses

    assert [f.name for f in dataclasses.fields(ExampleInfo)] == \
           ["name", "title", "description", "bytes"]
