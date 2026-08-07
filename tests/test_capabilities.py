"""WP-1007 — capabilities(), structured guard findings, and the missing exports.

Two kinds of test here, and the second is the interesting one:

* **Registry meta-tests.** Every member of every live registry must appear in its
  arm of ``capabilities()`` (the WP-0602 pattern — a restated literal union went
  stale two days after the torch backend landed). These fail when someone adds a
  backend, solver, plan, mode, anode or reader format and forgets the arm.
* **A byte-for-byte pin on the guard strings.** ``GuardReport`` used to hold
  formatted text and now holds :class:`GuardFinding` objects; the rendered form
  is a published surface (the diagnostics' messages are built from it), so the
  expected strings below are literals copied from the pre-change output, not
  re-derived from the code that produces them.
"""

from __future__ import annotations

import json
from typing import get_args

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.backend.api import BACKEND_NAMES, EXPERIMENTAL_BACKENDS
from pxrdref.background.diagnostics import _KBETA
from pxrdref.capabilities import capabilities
from pxrdref.io.readers import PATTERN_FORMATS
from pxrdref.optimize.least_squares import SOLVERS
from pxrdref.refine import _guard_diagnostics
from pxrdref.schemas.common import Mode
from pxrdref.schemas.instrument import _RADIATIONS
from pxrdref.strategy.staged import PLAN_INFO, PLAN_PRESETS, GuardFinding, GuardReport


@pytest.fixture(scope="module")
def caps():
    return capabilities()


# --------------------------------------------------------- registry arms
def test_every_backend_appears_with_its_flags(caps):
    assert [b.name for b in caps.backends] == list(BACKEND_NAMES)
    by_name = {b.name: b for b in caps.backends}
    assert by_name["numpy"].available and not by_name["numpy"].experimental
    assert by_name["numpy"].requires is None
    for name in EXPERIMENTAL_BACKENDS:
        assert by_name[name].experimental, f"{name} is registered experimental"
    # availability is a property of *this* machine, not of the registry — the
    # question a backend menu needs answered and the registry cannot answer
    assert by_name["jax"].requires == "jax"
    assert isinstance(by_name["jax"].available, bool)
    # the Apple-GPU row is the only one that is not fp64 throughout
    assert by_name["torch-mps"].dtype == "float64/jacobian:float32"


def test_every_solver_mode_and_plan_appears(caps):
    assert caps.solvers == list(SOLVERS)
    assert caps.modes == list(get_args(Mode))
    assert {p.name for p in caps.plans} == set(PLAN_PRESETS)
    # the four facts come from PLAN_INFO, not restated here
    for plan in caps.plans:
        info = PLAN_INFO[plan.name]
        assert (plan.title, plan.description, plan.when_to_use) == \
               (info.title, info.description, info.when_to_use)
        assert plan.modes == list(info.modes)
    # modes is plural for a reason: profile_only is both a Le Bail plan and a
    # no-structure Rietveld one, so a one-plan-one-mode arm would be wrong
    assert len(PLAN_INFO["profile_only"].modes) == 2


def test_every_search_preset_appears_with_its_ceiling(caps):
    """WP-1042: the search_presets arm quotes the live registry, never a
    restatement — same meta-test as plans, one registry over."""
    from pxrdref.indexing.engines import (
        DEFAULT_SEARCH_PRESET,
        SEARCH_PRESET_INFO,
        SEARCH_PRESETS,
    )

    assert {p.name for p in caps.search_presets} == set(SEARCH_PRESETS)
    for cap in caps.search_presets:
        info = SEARCH_PRESET_INFO[cap.name]
        assert (cap.title, cap.description, cap.when_to_use) == \
               (info.title, info.description, info.when_to_use)
        assert cap.total_budget_seconds == SEARCH_PRESETS[cap.name]
        assert cap.typical_seconds == info.typical_seconds
        assert cap.default == (cap.name == DEFAULT_SEARCH_PRESET)
    # exactly one default, and it is the one index_pattern resolves
    assert sum(p.default for p in caps.search_presets) == 1


def test_every_anode_appears_with_its_lines_and_kbeta(caps):
    assert {a.name for a in caps.anodes} == set(_RADIATIONS)
    by_name = {a.name: a for a in caps.anodes}
    for name, lines in _RADIATIONS.items():
        assert by_name[name].wavelengths == list(lines)
    # a Kα1-only entry has one line, and its Kβ is the parent anode's
    assert by_name["CuKa"].kalpha1_only is False
    assert len(by_name["CuKa"].wavelengths) == 2
    assert by_name["CuKa1"].kalpha1_only is True
    assert by_name["CuKa1"].wavelengths == [by_name["CuKa"].wavelengths[0]]
    assert by_name["CuKa1"].kbeta == by_name["CuKa"].kbeta == _KBETA["CuKa"]


def test_every_reader_format_appears_in_dispatch_order(caps):
    assert [r.name for r in caps.reader_formats] == [f.name for f in PATTERN_FORMATS]
    by_name = {r.name: r for r in caps.reader_formats}
    # the arm states what read_pattern actually sniffs, sourced from the registry
    assert "BANK" in by_name["gsas"].sniff
    assert ".cif" in by_name["pdcif"].extensions
    # and it names the reader keyword a caller has to supply *and* record
    assert by_name["pdcif"].options == ["block"]
    assert by_name["xy"].options == []


def test_every_versioned_contract_is_a_live_value(caps):
    """Five of them since WP-1009 — and the count is why they live in the arm.

    A contract named only in prose is a contract someone forgets to add; this
    test fails on a ``*_version`` field whose value is not the constant it
    claims to quote, and the field list below is checked against the model, so a
    sixth contract cannot arrive unnoticed either.
    """
    from pxrdref.gui.textdoc import FORMAT_VERSION as TEXTDOC_FORMAT_VERSION
    from pxrdref.history.events import EVENT_SCHEMA_VERSION
    from pxrdref.report.schemas import THRESHOLDS_VERSION
    from pxrdref.schemas.common import SCHEMA_VERSION
    from pxrdref.schemas.project import PROJECT_FORMAT_VERSION

    live = {
        "schema_version": SCHEMA_VERSION,
        "report_thresholds_version": THRESHOLDS_VERSION,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "project_format_version": PROJECT_FORMAT_VERSION,
        "textdoc_format_version": TEXTDOC_FORMAT_VERSION,
    }
    declared = {name for name in type(caps).model_fields
                if name.endswith("_version") and name != "package_version"}
    assert declared == set(live), "a versioned contract is missing from the arm"
    for name, constant in live.items():
        assert getattr(caps, name) == constant
    assert caps.package_version and caps.package_version[0].isdigit()


def test_capabilities_survives_json(caps):
    """WP-1008 serves this verbatim, so it has to be JSON all the way down."""
    round_tripped = type(caps).model_validate_json(caps.model_dump_json())
    assert round_tripped == caps
    assert json.loads(caps.model_dump_json())["features"]["indexing"] is True


# ------------------------------------------------------------- features
def test_features_are_derived_not_asserted(caps):
    """A flag must be a predicate over the tree, not a literal.

    And the predicate's *name* must be data, because this test's first version
    was a tautology: it asserted ``features["indexing"] == hasattr(pr, "index")``
    — the very expression the flag computes — so when the export landed as
    ``index_pattern`` (WP-1024) both sides stayed ``False`` together and the
    test kept passing.  The ``is True`` lines below are what break that
    symmetry: they state what the answer *is*, not that the code equals itself.
    """
    assert caps.features["indexing"] is True
    assert caps.features["peak_picking"] is True
    assert caps.features["cancellation"] is True

    # schema-shaped flags follow the schemas
    assert caps.features["stephens_strain"] == ("microstrain" in pr.Phase.model_fields)
    assert caps.features["anisotropic_adp"] == ("aniso" in pr.Atom.model_fields)

    # the one default whose position changes published numbers (WP-1001)
    assert caps.features["anomalous_dispersion_default_on"] is True
    assert all(isinstance(v, bool) for v in caps.features.values())


def test_every_surface_flag_names_a_real_export(caps):
    """The WP-1037 meta-test: each flag's export name, checked against an
    authority the flag itself never consults.

    ``_SURFACE_FLAGS`` is the one table both the flags and this test read, so
    the failure mode it closes — flag and test drifting *together* while the
    export is called something else — needs a third party, and ``__all__`` is
    it: a name in the table but absent from ``__all__`` fails here whether or
    not ``hasattr`` happens to find it.
    """
    from pxrdref.capabilities import _SURFACE_FLAGS

    missing = set(_SURFACE_FLAGS.values()) - set(pr.__all__)
    assert not missing, f"surface flags name exports not in __all__: {missing}"
    # and the table is the source: every one of its flags is served
    assert set(_SURFACE_FLAGS) <= set(caps.features)


def test_the_documented_feature_keys_are_present(caps):
    """Removing a flag is a client-visible change, so make it a loud one."""
    expected = {
        "anisotropic_adp", "preferred_orientation", "stephens_strain",
        "secondary_extinction", "restraints", "surface_roughness",
        "capillary_absorption", "flat_plate_absorption", "anomalous_dispersion",
        "anomalous_dispersion_default_on", "multi_histogram",
        "sequential_series", "project_container", "background_estimation",
        "pattern_diagnostics", "peak_picking", "indexing", "agent_json",
        "cancellation",
    }
    assert set(caps.features) == expected


# ------------------------------------------------- the top-level exports
def test_the_pre_fit_calls_are_reachable_from_the_top_level():
    """``auto_background`` and ``diagnose`` are the two calls a client makes
    *before* its first fit, and this module never imported ``background`` at all
    until WP-1007 — so they were the two it had to go digging for."""
    for name in ("auto_background", "diagnose", "capabilities",
                 "PreferredOrientation", "GuardFinding"):
        assert name in pr.__all__, f"{name} missing from __all__"
        assert hasattr(pr, name)

    tt = np.arange(10.0, 60.0, 0.02)
    y = 120.0 + 40.0 * np.exp(-((tt - 30.0) / 0.1) ** 2)
    data = pr.PatternData(two_theta=tt.tolist(), intensity=y.tolist())
    diag = pr.diagnose(data, wavelength=1.5405929)
    assert diag.n_points == len(tt)
    bkg = pr.auto_background(data, diagnostics=diag)
    # held additively or co-refined under a penalty — never subtracted
    assert bkg.kind in {"pspline", "chebyshev", "fixed+chebyshev"}


# ------------------------------------------------------- guard findings
#: (finding, the exact string v0.2–v0.6 put in the GuardReport list).  Literals
#: copied from the pre-change output — re-deriving them from the constructors
#: would test nothing.
RENDERINGS = [
    (GuardFinding.correlation("instrument.zero_shift",
                              "instrument.geometry.sample_displacement", 0.99987),
     "instrument.zero_shift ~ instrument.geometry.sample_displacement (ρ=+1.000)"),
    (GuardFinding.correlation("a", "b", -0.9912), "a ~ b (ρ=-0.991)"),
    (GuardFinding.at_bound("phases.0.atoms.0.biso"), "phases.0.atoms.0.biso"),
    (GuardFinding.background_absorption("phases.0.atoms.1.biso", 0.4612),
     "phases.0.atoms.1.biso (R²=0.46)"),
    (GuardFinding.roughness_absorption(
        "instrument.geometry.surface_roughness.b", 0.9481),
     "instrument.geometry.surface_roughness.b (R²=0.95)"),
    (GuardFinding.nonpositive_adp("phases.0.atoms.0", -1.234e-3),
     "phases.0.atoms.0 (min eigenvalue -1.23e-03 Å²)"),
    (GuardFinding.nonpositive_strain("phases.0.microstrain", 12, 43,
                                     -5.6789e-5, (0, 0, 2)),
     "phases.0.microstrain (12 of 43 reflections, worst σ²(M) -5.68e-05 at (0, 0, 2))"),
]


@pytest.mark.parametrize("finding,expected", RENDERINGS,
                         ids=[f.code for f, _ in RENDERINGS])
def test_rendered_findings_are_unchanged(finding, expected):
    assert str(finding) == expected
    assert finding.message == expected


def test_findings_carry_paths_and_a_number_instead_of_prose():
    rho = GuardFinding.correlation("a", "b", -0.9912)
    assert rho.paths == ("a", "b") and rho.value == pytest.approx(-0.9912)
    bound = GuardFinding.at_bound("x")
    assert bound.paths == ("x",) and bound.value is None  # no number to report
    r2 = GuardFinding.background_absorption("p", 0.46)
    assert r2.code == "BACKGROUND_ABSORPTION" and r2.value == pytest.approx(0.46)


def test_diagnostics_keep_their_messages_and_gain_their_paths():
    """The whole point: identical prose, and ``where`` finally populated.

    ``_guard_diagnostics`` recovered a path with ``msg.split(" ")[0]``, which
    yields nothing usable for a correlation — two paths and no leading one — so
    ``Diagnostic.where`` was **empty** on exactly the finding a GUI most wants to
    make clickable.  Measured before the change on a real degenerate fit:
    ``where == []``.
    """
    report = GuardReport(
        high_correlations=[GuardFinding.correlation(
            "instrument.zero_shift", "instrument.geometry.sample_displacement",
            0.99987)],
        at_bounds=[GuardFinding.at_bound("phases.0.scale")],
        nonpositive_adps=[GuardFinding.nonpositive_adp("phases.0.atoms.0", -1.2e-3)],
    )
    diags = _guard_diagnostics(report)
    assert [d.code for d in diags] == [
        "HIGH_CORRELATION", "BOUND_HIT", "ADP_NOT_POSITIVE_DEFINITE"]

    corr = diags[0]
    assert corr.message == (
        "instrument.zero_shift ~ instrument.geometry.sample_displacement (ρ=+1.000)")
    assert corr.where == ["instrument.zero_shift",
                          "instrument.geometry.sample_displacement"]
    assert diags[1].where == ["phases.0.scale"]
    assert diags[1].message == "phases.0.scale refined to its bound"
    assert diags[2].where == ["phases.0.atoms.0"]
    assert "not positive definite" in diags[2].message

    # every finding reaches a diagnostic, and the codes are one vocabulary
    assert [f.code for f in report.findings()] == [d.code for d in diags]


def test_a_finding_is_immutable_and_hashable():
    """Findings are values: a report can be deduplicated or put in a set."""
    import dataclasses

    a = GuardFinding.correlation("x", "y", 0.99)
    b = GuardFinding.correlation("x", "y", 0.99)
    assert a == b and len({a, b}) == 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.value = 0.5
