"""A diagnostic's level under a purpose, derived rather than authored (WP-2037).

Clause 2 of ``docs/milestones/generality.md`` § The rule: a level is the
response a reader owes, and whether it is owed depends on what the reader will
quote.  ``rietx.schemas.results.level_under`` derives it from the diagnostic's
``where`` paths and the purpose table (``rietx.purposes``), falling back on the
code's audited ``scope`` where the diagnostic names no path.

The four codes are the ones the skill's worked default on FAP returned on
2026-10-23 (``docs/wp/2037-attention/examples.md``), built here as records so
the table below is the whole claim and no fit is needed.
"""

from __future__ import annotations

import pytest

from rietx.purposes import PURPOSES
from rietx.schemas.common import Diagnostic
from rietx.schemas.results import level_under


def _d(code: str, where: list[str], level: str = "warning") -> Diagnostic:
    return Diagnostic(level=level, code=code, message="m", where=where)


FAP = {
    "SITE_SNAPPED_TO_SPECIAL_POSITION": _d("SITE_SNAPPED_TO_SPECIAL_POSITION",
                                           ["phases.0.atoms.0"]),
    "FLOOR_HIT": _d("FLOOR_HIT", ["phases.0.extinction"]),
    "RESOLUTION_UNCONSTRAINED": _d("RESOLUTION_UNCONSTRAINED",
                                   ["instrument.profile.u", "instrument.profile.v",
                                    "instrument.profile.w"]),
    "PATTERN_UNDERSAMPLED": _d("PATTERN_UNDERSAMPLED", []),
}

#: The purposes each FAP code is a warning under; ``info`` under every other.
#: A whole site bears on every number read from its atoms (structure, the
#: fraction its multiplicity sets, a moment it carries); extinction on the
#: intensities a structure and a fraction are read from; the instrument widths
#: on a size, a strain and a calibration; undersampling by its audited scope.
#: ``series`` follows every free path, so a code with a path is a warning there.
WARNING_UNDER = {
    "SITE_SNAPPED_TO_SPECIAL_POSITION": {"structure", "qpa", "magnetic", "series"},
    "FLOOR_HIT": {"structure", "qpa", "series"},
    "RESOLUTION_UNCONSTRAINED": {"microstructure", "calibration", "series"},
    "PATTERN_UNDERSAMPLED": {"qpa", "structure", "microstructure", "calibration"},
}


@pytest.mark.parametrize("code", sorted(FAP))
def test_each_fap_code_is_a_warning_exactly_where_its_purpose_reads_it(code):
    got = {p for p in PURPOSES if level_under(FAP[code], p) == "warning"}
    assert got == WARNING_UNDER[code]
    assert all(level_under(FAP[code], p) == "info" for p in set(PURPOSES) - got)


def test_no_warning_on_fap_touches_a_cell():
    """examples.md § 3: every row is ``info`` under ``cell``."""
    assert {level_under(d, "cell") for d in FAP.values()} == {"info"}


def test_an_error_is_an_error_and_an_info_an_info_for_every_purpose():
    err = _d("FLOOR_HIT", ["phases.0.extinction"], level="error")
    note = _d("FLOOR_HIT", ["phases.0.cell.a"], level="info")
    for purpose in PURPOSES:
        assert level_under(err, purpose) == "error"
        assert level_under(note, purpose) == "info"


def test_a_code_with_no_path_and_no_scope_keeps_its_level_everywhere():
    """WP-1076: a pairing nobody checked must not read as "not your concern"."""
    unscoped = _d("DATA_SUPPORT_LOW", [])
    assert {level_under(unscoped, p) for p in PURPOSES} == {"warning"}


def test_a_where_that_names_no_parameter_is_read_as_no_path():
    """A label in ``where`` is not a path, so the code's scope decides."""
    labelled = _d("PATTERN_UNDERSAMPLED", ["fluorapatite"])
    assert level_under(labelled, "qpa") == "warning"
    assert level_under(labelled, "cell") == "info"
    assert level_under(_d("DATA_SUPPORT_LOW", ["Ca1"]), "cell") == "warning"


def test_a_joint_fits_histogram_scope_is_read_through():
    scoped = _d("RESOLUTION_UNCONSTRAINED", ["hist.1.instrument.profile.u"])
    assert level_under(scoped, "microstructure") == "warning"
    assert level_under(scoped, "qpa") == "info"


def test_an_unknown_purpose_is_refused_by_name():
    with pytest.raises(ValueError, match="'phase_id'"):
        level_under(FAP["FLOOR_HIT"], "cells")
