"""Parametric series: a parameter as a declared function of each pattern's
coordinates, refined in one joint residual (WP-1325).

What is checked here, and on what:

* the declaration (``CoordinateTable``, ``ParametricTie``) as data — its JSON
  round-trip, its shape refusals, and its resolution against the patterns:
  the reference and scale frozen once, the term labels, and every refusal
  of the WP's § The shape item 3, each by its message, before any solve;
* the joint table's wiring — per-pattern starting structures, the coupling
  that lets a plan's glob on a target free its coefficients, and the
  absent-phase hold reading what a coefficient's column *moves* (WP-1342);
* the claim that a ``constant`` declaration **is** ``refine_multi`` with the
  target shared, bit for bit, on the two-wavelength LaB6 pair of
  ``test_multi_histogram``;
* and (slow) a ten-pattern LaB6 ramp with a known a(T), whose parametric
  slope must land within one esd of the truth with an esd no larger than the
  weighted trajectory line's.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.model import compiled
from rietx.multi import (
    MultiHistogramRefinement,
    _joint_fixed_literals,
    _parametric_range_diagnostics,
    _unsupported_paths_multi,
    refine_multi,
)
from rietx.params.multi import MultiParameterTable, SharingMap
from rietx.params.parametric import (
    ResolvedParametric,
    coefficient_rows,
    resolve_parametric,
    term_label,
)
from rietx.params.vector import AffineTie
from rietx.schemas.parametric import (
    CoordinateTable,
    ParametricCoefficient,
    ParametricTie,
)
from rietx.strategy.staged import Stage
from tests.test_multi_histogram import perturbed_inputs, synthesize

OUT = Path(__file__).parent / "output"


def _tie(**kw) -> ParametricTie:
    base = dict(name="a", target="phases.0.cell.a", basis="polynomial",
                terms=[[], ["T"]])
    base.update(kw)
    return ParametricTie(**base)


def _coords(*temps: float | None, **more) -> CoordinateTable:
    cols = {"T": list(temps), **more}
    return CoordinateTable(columns=cols, units={"T": "K"})


def _lab6_instruments(n: int) -> list[rx.Instrument]:
    out = []
    for _ in range(n):
        ins = rx.Instrument.debye_scherrer(wavelength=0.41390)
        ins.background = rx.schemas.instrument.BackgroundChebyshev.with_terms(3)
        out.append(ins)
    return out


# -- the declaration as data -------------------------------------------------

def test_the_declarations_round_trip_through_json():
    coords = CoordinateTable(columns={"T": [300.0, None, 500.0], "x": [0.1, 0.2, 0.3]},
                             units={"T": "K"})
    ties = [
        _tie(patterns=[0, 2], reference={"T": 400.0}, scale={"T": 100.0}),
        ParametricTie(name="c", target="instrument.background.c2", basis="constant"),
        ParametricTie(name="d", target="phases.0.atoms.0.biso", basis="design",
                      design=[[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]]),
    ]
    row = ParametricCoefficient(tie="a", target="phases.0.cell.a", term="T",
                                path="vars.a_1", value=2.1e-5, esd=None, vary=True,
                                unit=None, reference={"T": 400.0})
    for obj in (coords, *ties, row):
        text = obj.model_dump_json()
        assert type(obj).model_validate_json(text) == obj
        assert type(obj).model_validate(json.loads(text)) == obj


@pytest.mark.parametrize("kw, fragment", [
    (dict(name="a.b"), "single identifier"),
    (dict(target="phases.*.cell.a"), "not a glob"),
    (dict(target="hist.0.phases.0.cell.a"), "model parameter"),
    (dict(target="vars.x"), "model parameter"),
    (dict(basis="constant"), "takes no terms"),
    (dict(terms=[]), "needs terms"),
    (dict(terms=[["T"], ["T"]]), "appears twice"),
    (dict(terms=[["T", "x"], ["x", "T"]]), "appears twice"),
    (dict(scale={"T": 0.0}), "must be positive"),
    (dict(reference={"x": 1.0}), "no term uses"),
    (dict(patterns=[0, 0]), "appears twice in the subset"),
    (dict(patterns=[]), "selects nothing"),
    (dict(basis="design", terms=None, design=[[1.0], [1.0, 2.0]]), "same number"),
    (dict(basis="design", terms=None, design=[[1.0]], patterns=[0, 1]), "one row per"),
])
def test_a_malformed_declaration_is_refused_by_its_shape(kw, fragment):
    with pytest.raises(ValidationError, match=fragment):
        _tie(**kw)


@pytest.mark.parametrize("columns, units, fragment", [
    ({"T": [1.0, 2.0], "x": [1.0]}, {}, "lengths differ"),
    ({"T": [1.0, float("nan")]}, {}, "must be finite"),
    ({"T": [1.0]}, {"x": "K"}, "does not have"),
    ({"2T": [1.0]}, {}, "single identifier"),
])
def test_a_malformed_coordinate_table_is_refused(columns, units, fragment):
    with pytest.raises(ValidationError, match=fragment):
        CoordinateTable(columns=columns, units=units)


# -- resolution: the reference and scale, once ------------------------------

def test_resolution_freezes_the_reference_and_scale_and_a_refit_keeps_them():
    r = resolve_parametric(_tie(), _coords(300.0, 375.0, 600.0), 3, target_unit="A")
    assert r.tie.reference == {"T": 450.0} and r.tie.scale == {"T": 150.0}
    assert r.labels == ["1", "T"]
    np.testing.assert_array_equal(r.phi[:, 1], [-1.0, -0.5, 1.0])
    assert r.units == ["A", "A/K"]
    # the campaign grows past the old range: the resolved declaration keeps
    # its reference and scale, so the old patterns' rows are unchanged and a
    # coefficient means what it meant
    grown = resolve_parametric(r.tie, _coords(300.0, 375.0, 600.0, 900.0), 4)
    assert grown.tie.reference == {"T": 450.0} and grown.tie.scale == {"T": 150.0}
    np.testing.assert_array_equal(grown.phi[:3], r.phi)
    # left unresolved, the same growth would have moved both
    fresh = resolve_parametric(_tie(), _coords(300.0, 375.0, 600.0, 900.0), 4)
    assert fresh.tie.reference == {"T": 600.0} and fresh.tie.scale == {"T": 300.0}


def test_term_labels_and_units_name_each_monomial():
    assert [term_label(t) for t in ([], ["T"], ["x", "y"], ["T", "T"],
                                    ["x", "y", "x"])] == ["1", "T", "x*y", "T^2", "x^2*y"]
    coords = CoordinateTable(columns={"x": [0.0, 1.0, 2.0, 3.0], "y": [0.0, 2.0, 1.0, 3.0]},
                             units={"x": "at%"})
    r = resolve_parametric(_tie(terms=[[], ["x"], ["y"], ["x", "x"]]), coords, 4,
                           target_unit="A")
    # y has no recorded unit, so no unit is claimed for its term
    assert r.units == ["A", "A/at%", None, "A/at%^2"]
    assert r.divisors.tolist() == [1.0, 1.5, 1.5, 2.25]


# -- refusals before any solve: from the declaration and the coordinates ----

@pytest.mark.parametrize("tie, coords, n, fragment", [
    (_tie(patterns=[0, 3]), _coords(1.0, 2.0, 3.0), 3, "out of range"),
    (_tie(), None, 3, "needs a CoordinateTable"),
    (_tie(), _coords(1.0, 2.0), 3, "2 rows for 3 patterns"),
    (_tie(terms=[[], ["x"]]), _coords(1.0, 2.0, 3.0), 3, "does not have"),
    (_tie(), _coords(1.0, None, 3.0), 3, "pattern 1 has no value"),
    (_tie(), _coords(2.0, 2.0, 2.0), 3, "takes one value"),
    (_tie(terms=[[], ["T"], ["T", "T"]]), _coords(1.0, 2.0), 2, "3 coefficients"),
    (ParametricTie(name="d", target="phases.0.cell.a", basis="design",
                   design=[[1.0], [2.0]]), None, 3, "2 design rows"),
    (ParametricTie(name="d", target="phases.0.cell.a", basis="design",
                   design=[[1.0, 2.0], [2.0, 4.0], [3.0, 6.0]]), None, 3,
     "d1 is a combination of"),
    (ParametricTie(name="d", target="phases.0.cell.a", basis="design",
                   design=[[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]), None, 3, "zero in every"),
])
def test_each_resolution_refusal_names_its_fix(tie, coords, n, fragment):
    with pytest.raises(ValueError, match=fragment):
        resolve_parametric(tie, coords, n)


def test_a_ternary_with_an_intercept_is_refused_with_the_scheffe_fix():
    """x_A + x_B + x_C = 1 on every pattern: the intercept is their sum."""
    xa = [0.6, 0.2, 0.2, 0.4, 0.3]
    xb = [0.2, 0.6, 0.2, 0.3, 0.3]
    xc = [1.0 - a - b for a, b in zip(xa, xb, strict=True)]
    coords = CoordinateTable(columns={"xa": xa, "xb": xb, "xc": xc})
    tie = _tie(terms=[[], ["xa"], ["xb"], ["xc"]])
    with pytest.raises(ValueError, match=r"rank 3 for 4.*Scheffé.*reference="):
        resolve_parametric(tie, coords, 5)
    # without the intercept the basis is full rank, but centred fractions would
    # make each coefficient a blend of pure-component values: refused until the
    # reading is stated
    scheffe = [["xa"], ["xb"], ["xc"]]
    with pytest.raises(ValueError, match=r"mixture fractions.*Scheffé form"):
        resolve_parametric(_tie(terms=scheffe), coords, 5)
    # stated: the Scheffé form resolves, uncentred
    zero, one = dict.fromkeys(coords.columns, 0.0), dict.fromkeys(coords.columns, 1.0)
    ok = resolve_parametric(_tie(terms=scheffe, reference=zero, scale=one), coords, 5)
    assert ok.labels == ["xa", "xb", "xc"]
    assert np.array_equal(ok.phi, np.column_stack([xa, xb, xc]))


# -- refusals before any solve: what the tables can carry -------------------

@pytest.mark.parametrize("tie, fragment", [
    (_tie(target="phases.0.cell.q", basis="constant", terms=None), "not a parameter"),
    (_tie(target="phases.0.cell.b", basis="constant", terms=None),
     "is tied: = 1·phases.0.cell.a.*declare the tie on phases.0.cell.a"),
    (_tie(target="phases.0.atoms.0.x", basis="constant", terms=None), "locked"),
])
def test_a_target_no_tie_can_drive_is_refused_naming_why(tie, fragment):
    s, _ = perturbed_inputs()
    with pytest.raises(ValueError, match=fragment):
        MultiParameterTable(s, _lab6_instruments(2), parametric=[tie])


def test_a_held_target_is_refused():
    """The floating origin's hold (WP-1912) is the joint table's one hold."""
    from tests.test_floating_origin import _zno

    phase = _zno()
    phase.floating_origin = "hold"
    s = rx.Structure(phases=[phase])
    tie = _tie(target="phases.0.atoms.0.dof.0", basis="constant", terms=None)
    with pytest.raises(ValueError, match="is held"):
        MultiParameterTable(s, [rx.Instrument.bragg_brentano(radiation="CuKa")] * 2,
                            parametric=[tie])


def test_two_declarations_may_share_neither_a_name_nor_a_pattern_of_one_target():
    s, _ = perturbed_inputs()
    one = _tie(basis="constant", terms=None)
    with pytest.raises(ValueError, match="both drive phases.0.cell.a on patterns 0, 1"):
        MultiParameterTable(s, _lab6_instruments(2),
                            parametric=[one, one.model_copy(update={"name": "b"})])
    with pytest.raises(ValueError, match="both drive phases.0.cell.a on pattern 1:"):
        MultiParameterTable(s, _lab6_instruments(3), parametric=[
            one.model_copy(update={"patterns": [0, 1]}),
            one.model_copy(update={"name": "b", "patterns": [1, 2]})])
    with pytest.raises(ValueError, match="two parametric ties are named 'a'"):
        MultiParameterTable(s, _lab6_instruments(2), parametric=[
            one, one.model_copy(update={"target": "phases.0.atoms.0.biso"})])


def test_two_phase_fields_take_a_law_each_on_one_target():
    """Disjoint subsets: one law per field, each pattern tied by its own."""
    s, _ = perturbed_inputs()
    lo = _tie(name="lo", basis="constant", terms=None, patterns=[0, 1])
    hi = _tie(name="hi", basis="constant", terms=None, patterns=[2, 3])
    mt = MultiParameterTable(s, _lab6_instruments(4), parametric=[lo, hi])
    sources = [mt.tables[h].entries[mt.tables[h]._paths["phases.0.cell.a"]].tie.terms
               for h in range(4)]
    assert [src for (src, _), in sources] == ["vars.lo_0", "vars.lo_0",
                                             "vars.hi_0", "vars.hi_0"]
    freed = mt.set_vary(["phases.*.cell.*"], True)
    assert {"vars.lo_0", "vars.hi_0"} <= set(freed)


def test_a_sharing_map_that_splits_a_coefficient_is_refused():
    s, _ = perturbed_inputs()
    with pytest.raises(ValueError, match="makes vars.a_0 per-histogram"):
        MultiParameterTable(s, _lab6_instruments(2),
                            sharing=SharingMap(per_histogram=["vars.*"]),
                            parametric=[_tie(basis="constant", terms=None)])


# -- the joint table's wiring ------------------------------------------------

def _ramp_table(n: int = 3, **kw) -> MultiParameterTable:
    s, _ = perturbed_inputs()
    return MultiParameterTable(
        s, _lab6_instruments(n), coordinates=_coords(*[300.0 + 100 * k for k in range(n)]),
        parametric=[_tie()], **kw)


def test_the_target_follows_the_declared_line_in_every_table():
    mt = _ramp_table()
    assert [r.target for r in mt.parametric] == ["phases.0.cell.a"]
    # the target and what follows it are per-histogram; the coefficients shared
    assert not mt.sharing.is_shared("phases.0.cell.c")
    assert all(mt.sharing.is_shared(p) for p in ("vars.a_0", "vars.a_1"))
    for t in mt.tables:
        t.entries[t._paths["vars.a_1"]].value = 0.01
        t.refresh_ties()
    for h, t in enumerate(mt.tables):
        want = 4.1606 + 0.01 * (h - 1)
        for k in "abc":
            assert t.entries[t._paths[f"phases.0.cell.{k}"]].value == pytest.approx(want, abs=1e-12)


def test_a_glob_on_the_target_frees_its_coefficients_and_names_them():
    mt = _ramp_table()
    mt.set_vary(["*"], False)
    assert mt.set_vary(["phases.*.cell.*"], True) == ["vars.a_0", "vars.a_1"]
    assert mt.shared_paths == ["vars.a_0", "vars.a_1"]
    assert mt.set_vary(["phases.0.cell.a"], False) == ["vars.a_0", "vars.a_1"]
    # scoped to a subset histogram, the glob still reaches the declaration
    assert mt.set_vary(["hist.2.phases.0.cell.a"], True) == ["vars.a_0", "vars.a_1"]
    # a plan's literal on the target is not "a tied row the stage cannot free"
    assert _joint_fixed_literals([Stage(name="cell", turn_on=["phases.0.cell.a"])],
                                 mt) == []


def test_a_column_is_held_only_when_every_phase_it_moves_is_unseen():
    """WP-1342 on the joint path: columns, never names, and all, never any."""
    s, _ = perturbed_inputs()
    nacl = rx.Phase(
        name="nacl", space_group="F m -3 m", cell=rx.Cell.cubic(5.64),
        atoms=[rx.Atom(label="Na", species="Na", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0)),
               rx.Atom(label="Cl", species="Cl", x=rx.Parameter(value=0.5),
                       y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5))])
    s.phases.append(nacl)
    tie = _tie(name="b", target="phases.1.cell.a", basis="constant", terms=None)
    mt = MultiParameterTable(s, _lab6_instruments(2), parametric=[tie])
    mt.set_vary(["*"], False)
    mt.set_vary(["phases.*.cell.*"], True)
    assert "vars.b_0" in mt.free_paths
    # by name the coefficient carries no phase; by reach it is phase 1's cell
    assert _unsupported_paths_multi(mt, {1}) == ["vars.b_0"]
    assert _unsupported_paths_multi(mt, {0}) == ["phases.0.cell.a"]
    # the same coefficient made to drive phase 0's cell too: one visible
    # phase gives it gradient, so it is held only when both are unseen
    for t in mt.tables:
        t.set_tie("phases.0.cell.a", AffineTie.identity("vars.b_0"))
        t.refresh_ties()
    mt._rebuild_columns()
    assert _unsupported_paths_multi(mt, {1}) == []
    assert _unsupported_paths_multi(mt, {0}) == []
    assert _unsupported_paths_multi(mt, {0, 1}) == ["vars.b_0"]


def test_per_pattern_starting_structures_differ_only_where_a_path_is_per_histogram():
    def start(a: float, biso: float = 0.5, sg: str = "P m -3 m") -> rx.Structure:
        s, _ = perturbed_inputs()
        s.phases[0].space_group = sg
        for k in "abc":
            getattr(s.phases[0].cell, k).value = a
        s.phases[0].atoms[0].biso.value = biso
        return s

    coords = _coords(300.0, 400.0)
    # the cell differs, but it is the parametric target: accepted, and the
    # line through the starts is the coefficients' start
    mt = MultiParameterTable([start(4.15), start(4.17)], _lab6_instruments(2),
                             coordinates=coords, parametric=[_tie()])
    t0 = mt.tables[0]
    assert t0.entries[t0._paths["vars.a_0"]].value == pytest.approx(4.16, abs=1e-12)
    assert t0.entries[t0._paths["vars.a_1"]].value == pytest.approx(0.01, abs=1e-12)
    # a per-histogram scale may differ too
    other = start(4.15)
    other.phases[0].scale.value = 7.0
    MultiParameterTable([start(4.15), other], _lab6_instruments(2))
    # a shared value may not, and the refusal names the path and the histogram
    with pytest.raises(ValueError, match=r"disagree on phases.0.atoms.0.biso.*histogram 1"):
        MultiParameterTable([start(4.15), start(4.15, biso=0.7)], _lab6_instruments(2))
    with pytest.raises(ValueError, match="disagree on phases.0.cell.a"):
        MultiParameterTable([start(4.15), start(4.17)], _lab6_instruments(2))
    with pytest.raises(ValueError, match="space group"):
        MultiParameterTable([start(4.15), start(4.15, sg="P 4/m m m")],
                            _lab6_instruments(2))
    with pytest.raises(ValueError, match="3 starting structures for 2"):
        MultiParameterTable([start(4.15)] * 3, _lab6_instruments(2))


def test_a_dependent_the_coefficients_put_out_of_range_is_named():
    s, _ = perturbed_inputs()
    tie = _tie(name="w", target="instrument.profile.w")
    mt = MultiParameterTable(s, _lab6_instruments(3), coordinates=_coords(300.0, 400.0, 500.0),
                             parametric=[tie])
    assert _parametric_range_diagnostics(mt) == []
    for t in mt.tables:      # w = 1e-3 - 2e-3·u: negative at the top of the ramp
        t.entries[t._paths["vars.w_1"]].value = -2e-3
        t.refresh_ties()
    (d,) = _parametric_range_diagnostics(mt)
    assert d.code == "PARAMETRIC_OUT_OF_RANGE" and d.level == "warning"
    assert d.where == ["hist.2.instrument.profile.w"] and d.value == 1.0
    assert "histogram 2" in d.message


def test_coefficients_are_reported_per_unit_of_the_coordinates_at_the_reference():
    r = resolve_parametric(_tie(terms=[[], ["T"], ["T", "T"]]),
                           _coords(300.0, 500.0, 700.0), 3, target_unit="A")
    assert isinstance(r, ResolvedParametric) and r.tie.scale == {"T": 200.0}
    rows = coefficient_rows(
        r, {"vars.a_0": 4.0, "vars.a_1": 0.02, "vars.a_2": 0.004},
        {"vars.a_0": 1e-5, "vars.a_1": 2e-5},           # a_2: marked unmeasured
        {"vars.a_0": True, "vars.a_1": True, "vars.a_2": True})
    assert [(c.term, c.unit) for c in rows] == [("1", "A"), ("T", "A/K"), ("T^2", "A/K^2")]
    assert rows[0].value == 4.0 and rows[0].esd == 1e-5
    assert rows[1].value == pytest.approx(1e-4) and rows[1].esd == pytest.approx(1e-7)
    assert rows[2].value == pytest.approx(1e-7) and rows[2].esd is None
    assert rows[1].reference == {"T": 500.0}
    # a coefficient that was never free has no esd, whatever the map holds
    fixed = coefficient_rows(r, {p: 1.0 for p in r.paths}, {"vars.a_0": 1e-5}, {})
    assert all(c.esd is None and not c.vary for c in fixed)


# -- the joint fit: a constant declaration is refine_multi -------------------

@pytest.fixture(scope="module")
def lab6_pair() -> list[rx.PatternData]:
    return [
        synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                   bkg=[40.0, -6.0, 1.5], seed=1),
        synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                   bkg=[70.0, 5.0, -2.0], seed=2),
    ]


@pytest.mark.xdist_group("parametric-series")
@pytest.mark.parametrize("target, follows, compiled_path", [
    ("phases.0.cell.a", ["phases.0.cell.b", "phases.0.cell.c"], False),
    ("phases.0.cell.a", ["phases.0.cell.b", "phases.0.cell.c"], True),
    ("instrument.profile.w", [], True),
], ids=["cell-numpy", "cell-compiled", "width-compiled"])
def test_a_constant_declaration_is_refine_multi_bit_for_bit(lab6_pair, target, follows,
                                                            compiled_path):
    """The WP's equivalence bar, met exactly rather than to a tolerance.

    A ``constant`` tie makes the target per-histogram and ties it in each
    table to one shared coefficient at coefficient 1, against a plain joint
    fit that shares the target (the cell by default, the width by
    ``SharingMap.shared``).  The coefficient takes the column the shared target
    had (``_rebuild_columns``), starts from its exact value
    (``least_squares_start``), carries its declared box and unit (so the
    width's floor and FD step are its own), and dispatches to the target's
    analytic branch (``_column_identities`` reads a variable as what it
    drives) — so every θ, esd and statistic is the plain fit's, to the bit.
    """
    was = compiled.set_enabled(compiled_path)
    try:
        s, ins = perturbed_inputs()
        plain = refine_multi(lab6_pair, s, ins, plan="mccusker_default",
                             sharing=SharingMap(shared=[target]))
        s, ins = perturbed_inputs()
        ref = MultiHistogramRefinement(
            s, ins, parametric=[ParametricTie(name="t", target=target, basis="constant")])
        tied = ref.fit(lab6_pair, plan="mccusker_default")
    finally:
        compiled.set_enabled(was)
    OUT.mkdir(exist_ok=True)
    tied.for_histogram(1).plot(OUT / f"parametric_constant_h1_{target}_{compiled_path}.png")
    a = {p.path: p for p in plain.parameters}
    b = {p.path: p for p in tied.parameters}
    shared = a.pop(target)
    assert (b["vars.t_0"].value, b["vars.t_0"].stderr) == (shared.value, shared.stderr)
    for path, row in a.items():
        if path in follows:
            continue          # follow the target, per histogram now
        assert (b[path].value, b[path].stderr) == (row.value, row.stderr), path
    for h in range(2):
        for path in (target, *follows):
            assert b[f"hist.{h}.{path}"].value == shared.value
    assert tied.statistics == plain.statistics
    for hp, ht in zip(plain.histograms, tied.histograms, strict=True):
        assert ht.statistics == hp.statistics
        assert ht.y_calc == hp.y_calc
    (coef,) = tied.parametric
    assert (coef.value, coef.esd, coef.term, coef.vary) == (
        shared.value, shared.stderr, "1", True)
    assert plain.parametric is None
    # the stage that freed the target freed the coefficient in its place
    stage = next(st for st in plain.stages if target in st.freed)
    assert [p.replace(target, "vars.t_0") for p in stage.freed] == next(
        st.freed for st in tied.stages if st.name == stage.name)
    assert ref.parametric == [ParametricTie(name="t", target=target, basis="constant")]


def _with_an_unseen_phase() -> rx.Structure:
    """The LaB6 pair's start plus a NaCl phase neither pattern contains."""
    s, _ = perturbed_inputs()
    s.phases.append(rx.Phase(
        name="nacl", space_group="F m -3 m", cell=rx.Cell.cubic(5.64),
        scale=rx.Parameter(value=1e-12, min=0.0),
        atoms=[rx.Atom(label="Na", species="Na", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0)),
               rx.Atom(label="Cl", species="Cl", x=rx.Parameter(value=0.5),
                       y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5))]))
    return s


@pytest.mark.xdist_group("parametric-series")
def test_a_joint_fit_holds_a_coefficient_whose_phase_no_pattern_sees(lab6_pair):
    """The latent WP-1342 bug: a name prefix would never hold ``vars.b_0``,
    and would release it at once if it had.

    Measured on this fixture: the NaCl scale fits noise to 1.6e-8 in
    histogram 0 by the cell stage, so the cell refines there, and the support
    hold takes it from ``profile_w`` on.  The parametric fit decides exactly
    as the plain one does, stage by stage, and lands on the same cell.
    """
    _, ins = perturbed_inputs()
    plain = refine_multi(lab6_pair, _with_an_unseen_phase(), ins,
                         plan="mccusker_default")
    _, ins = perturbed_inputs()
    tie = ParametricTie(name="b", target="phases.1.cell.a", basis="constant")
    result = refine_multi(lab6_pair, _with_an_unseen_phase(), ins, parametric=[tie],
                          plan="mccusker_default")
    OUT.mkdir(exist_ok=True)
    result.for_histogram(0).plot(OUT / "parametric_unseen_phase_h0.png")
    rename = {"phases.1.cell.a": "vars.b_0"}
    assert ([[rename.get(p, p) for p in st.held] for st in plain.stages]
            == [st.held for st in result.stages])
    held = [st for st in result.stages if "vars.b_0" in st.held]
    assert held and held[-1] is result.stages[-1]       # never released by its name
    for st in held:
        assert "vars.b_0" not in st.freed
        assert set(st.held_reach["vars.b_0"]) == {
            f"hist.{h}.phases.1.cell.{k}" for h in range(2) for k in "abc"}
    (coef,) = result.parametric
    assert coef.vary is False and coef.esd is None
    assert coef.value == plain.parameter("phases.1.cell.b").value
    unseen = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert unseen and "vars.b_0" in unseen[0].where
    assert result.statistics == plain.statistics


# -- the synthetic ramp (slow): a measured a₁ with its esd ------------------

@pytest.mark.slow
def test_a_parametric_slope_recovers_a_known_expansion_within_its_esd():
    """Ten LaB6 patterns, T = 300…1200 K, a(T) on a known line.

    One diffractometer, so its zero and profile are shared across the ramp —
    the regime where § Measured found the joint esd 2.6× under the weighted
    trajectory line's (R3).  Seed and protocol are ``synthetic_ramp.py``'s.
    """
    from tests.test_sequential import A0, RAMP, _simulate, _start_models

    temps = [300.0 + 100.0 * k for k in range(10)]
    patterns = [_simulate(A0 * (1.0 + RAMP * (t - 300.0) / 100.0), seed=k)
                for k, t in enumerate(temps)]
    truth = A0 * RAMP / 100.0
    structure, ins = _start_models()
    result = refine_multi(
        patterns, structure, [ins] * len(temps), plan="mccusker_default",
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=CoordinateTable(columns={"T": temps}, units={"T": "K"}),
        parametric=[ParametricTie(name="a", target="phases.0.cell.a",
                                  basis="polynomial", terms=[[], ["T"]])])
    OUT.mkdir(exist_ok=True)
    for h in (0, len(temps) - 1):
        result.for_histogram(h).plot(OUT / f"parametric_ramp_h{h}.png")
    assert result.status == "converged"
    intercept, slope = result.parametric
    assert (intercept.term, slope.term) == ("1", "T")
    assert slope.reference == {"T": 750.0}
    assert abs(slope.value - truth) < slope.esd, (slope.value, slope.esd, truth)
    a_ref = A0 * (1.0 + RAMP * (750.0 - 300.0) / 100.0)
    assert abs(intercept.value - a_ref) < 3 * intercept.esd

    structure, ins = _start_models()
    series = rx.refine_sequential(patterns, structure, ins, x=temps,
                                  plan="mccusker_default")
    traj = series.trajectory("phases.0.cell.a")
    a = np.array(traj.value)
    w = 1.0 / np.array(traj.stderr, dtype=float) ** 2
    x = np.column_stack([np.ones(len(temps)), np.array(temps) - 750.0])
    line_cov = np.linalg.inv(x.T @ (w[:, None] * x))
    assert slope.esd <= np.sqrt(line_cov[1, 1]), (slope.esd, np.sqrt(line_cov[1, 1]))
    assert abs(float((line_cov @ x.T @ (w * a))[1]) - truth) < 3 * np.sqrt(line_cov[1, 1])
