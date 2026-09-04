"""Named variables: a caller's own parameter that others follow (WP-1119).

The WP's claim is that a variable is a **renaming** — the same constraint,
written in terms of a quantity instead of in terms of whichever model
parameter happened to be nominated as its master.  That claim is checked here
where it is exact (the residual and every Jacobian column) rather than only
where it is convenient (a converged Rwp), for the reason the root CLAUDE.md
gives about a phase scale's FD column: agreeing with the wrong oracle certifies
nothing.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.optimize.least_squares import _jacobian_for, _make_residual
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.pattern import PatternData
from tests.test_refine_synthetic import (
    TRUE_A,
    TRUE_BKG,
    TRUE_SCALE,
    TRUE_W,
    TRUE_ZERO,
    WAVELENGTH,
    perturbed_models,
    synthesize,
)
from tests.test_schemas import make_lab6

#: The four Biso coefficients of the WP's own example: 1, 1, 2, and 1 + 0.5.
COEFFS = ((1.0, 0.0), (1.0, 0.0), (2.0, 0.0), (1.0, 0.5))

#: Ceiling on the master.  ``Atom.biso`` is bounded [0, 25] and the solver
#: bounds only the **free** column, so a dependent at coefficient 2 can be
#: carried past its own ceiling by a master that is inside its.  That is
#: pre-WP-1119 behaviour of ``tie`` itself (a plain ``tie(..., scale=2.0)``
#: reproduces it with no variable anywhere), and it is the reason a variable's
#: bounds have to be chosen for its *dependents*: they are the only bounds the
#: solve sees.
MASTER_MAX = 12.0

BISOS = [f"phases.0.atoms.{j}.biso" for j in range(4)]


def four_site_models(*, true: bool, master_max: float = 25.0):
    """LaB6 with two extra B sites, so there are four Biso rows to constrain."""
    s = make_lab6()
    a = TRUE_A if true else TRUE_A + 0.004
    for name in ("a", "b", "c"):
        getattr(s.phases[0].cell, name).value = a
    s.phases[0].scale.value = TRUE_SCALE if true else TRUE_SCALE * 1.8
    s.phases[0].atoms.append(rx.Atom(label="B2", species="B",
                                     x=Parameter(value=0.5),
                                     y=Parameter(value=0.1993),
                                     z=Parameter(value=0.5)))
    s.phases[0].atoms.append(rx.Atom(label="B3", species="B",
                                     x=Parameter(value=0.5),
                                     y=Parameter(value=0.5),
                                     z=Parameter(value=0.1993)))
    for j, b in enumerate((0.7, 1.4, 1.2, 0.9)):
        s.phases[0].atoms[j].biso.value = b
    s.phases[0].atoms[0].biso.max = master_max
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = TRUE_ZERO if true else 0.0
    ins.profile.w.value = TRUE_W if true else TRUE_W * 2.0
    ins.background = (
        BackgroundChebyshev(coefficients=[Parameter(value=v) for v in TRUE_BKG])
        if true else BackgroundChebyshev.with_terms(3))
    return s, ins


@pytest.fixture(scope="module")
def four_site_pattern() -> PatternData:
    s, ins = four_site_models(true=True)
    tt = np.arange(3.0, 24.0, 0.005)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(s, ins, blank, mode="rietveld")
    table = ParameterTable(s, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def dot_path_arm(*, master_max: float = 25.0) -> rx.Refinement:
    """The constraint spelled with ``atoms.0.biso`` nominated as the master."""
    ref = rx.Refinement(*four_site_models(true=False, master_max=master_max))
    for j, (scale, offset) in enumerate(COEFFS):
        if j == 0:
            continue
        ref.tie(BISOS[j], BISOS[0], scale=scale, offset=offset)
    return ref


def variable_arm(*, master_max: float = 25.0) -> rx.Refinement:
    """The same constraint spelled with a named variable as the master."""
    structure, ins = four_site_models(true=False, master_max=master_max)
    ref = rx.Refinement(structure, ins)
    master = structure.phases[0].atoms[0].biso
    ref.add_variable("B_metal", master.value, min=master.min, max=master.max,
                     transform=master.transform)
    for j, (scale, offset) in enumerate(COEFFS):
        ref.tie(BISOS[j], "vars.B_metal", scale=scale, offset=offset)
    return ref


@pytest.fixture
def ref():
    return rx.Refinement(*perturbed_models())


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


# ------------------------------------------------------------------ the object
def test_a_variable_is_a_row_like_any_other(ref):
    assert ref.add_variable("A", 0.7, min=0.0, max=25.0) == "vars.A"
    row = {r.path: r for r in ref.parameters()}["vars.A"]
    assert (row.value, row.lo, row.hi, row.transform) == (0.7, 0.0, 25.0, "identity")
    assert row.tie is None and not row.locked and not row.mode_fixed
    assert row.refinable and not row.vary
    # an ordinary dot-path from there on: the glob frees it, set_values moves it
    assert ref.set_vary("vars.*", True) == ["vars.A"]
    ref.set_values({"vars.A": 1.1})
    assert {r.path: r for r in ref.parameters()}["vars.A"].value == 1.1


def test_the_declaration_is_the_parameter_and_the_table_reads_it(ref):
    """Bounds and transform reach the table, which is what makes it a renaming."""
    ref.add_variable("S", 3.0, min=0.0, transform="softplus", unit="arb")
    entry = {e.path: e for e in ref._working_table().entries}["vars.S"]
    assert (entry.lo, entry.hi, entry.transform) == (0.0, np.inf, "softplus")


def test_add_variable_refuses_a_name_a_glob_could_not_reach(ref):
    for name in ("a.b", "A*", "", "2A"):
        with pytest.raises(ValueError, match="single identifier"):
            ref.add_variable(name, 1.0)
    ref.add_variable("A", 1.0)
    with pytest.raises(ValueError, match="already exists"):
        ref.add_variable("A", 2.0)


def test_remove_variable_refuses_under_a_dependent_and_names_it(ref):
    ref.add_variable("A", 0.7, min=0.0, max=25.0)
    ref.tie("phases.0.atoms.0.biso", "vars.A")
    with pytest.raises(ValueError, match=r"phases\.0\.atoms\.0\.biso"):
        ref.remove_variable("A")
    ref.untie("phases.0.atoms.0.biso")
    assert ref.remove_variable("A") == "vars.A"
    assert "vars.A" not in {r.path for r in ref.parameters()}
    with pytest.raises(ValueError, match="no variable named"):
        ref.remove_variable("A")


# ------------------------------------------------------------- multi-term ties
def test_tie_takes_several_sources_and_scale_multiplies_every_term(ref):
    ref.add_variable("A", 0.4, min=0.0, max=25.0)
    ref.add_variable("C", 0.3, min=0.0, max=25.0)
    ref.tie("phases.0.atoms.0.biso", {"vars.A": 1.0, "vars.C": 1.0})
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.0.biso"].tie.terms == [("vars.A", 1.0), ("vars.C", 1.0)]
    assert rows["phases.0.atoms.0.biso"].value == pytest.approx(0.7)

    # the pair-sequence spelling, and scale on every term
    ref.tie("phases.0.atoms.1.biso", [("vars.A", 1.0), ("vars.C", 2.0)], scale=2.0)
    tie = {r.path: r for r in ref.parameters()}["phases.0.atoms.1.biso"].tie
    assert tie.terms == [("vars.A", 2.0), ("vars.C", 4.0)]


def test_a_repeated_source_is_refused_rather_than_summed(ref):
    ref.add_variable("A", 0.4, min=0.0, max=25.0)
    with pytest.raises(ValueError, match="appears twice"):
        ref.tie("phases.0.atoms.0.biso", [("vars.A", 1.0), ("vars.A", 2.0)])
    with pytest.raises(ValueError, match="at least one source"):
        ref.tie("phases.0.atoms.0.biso", {})


# ------------------------------------------------------------- the chain rule
def test_a_variable_may_follow_variables_and_a_model_path_may_not(ref):
    """WP-1119's chain decision, both halves.

    The table has always flattened chains exactly, so this is a judgement about
    what a caller meant rather than a limit of the machinery: composing is the
    point between variables, and misleading on a model path, where the tie
    quietly inherits a constant nobody wrote.
    """
    ref.add_variable("A", 0.4, min=0.0, max=25.0)
    ref.add_variable("C", 0.3, min=0.0, max=25.0)
    ref.add_variable("B", 0.0, min=0.0, max=25.0)
    ref.tie("vars.B", {"vars.A": 1.0, "vars.C": 1.0})
    ref.tie("phases.0.atoms.0.biso", "vars.B")     # follows a tied variable
    ref.set_vary(["vars.A", "vars.C"], True)

    table = ref._working_table()
    paths = [e.path for e in table.entries]
    C, d = table.constraint_block()
    row = C.toarray()[paths.index("phases.0.atoms.0.biso")]
    columns = dict(zip(table.free_paths, row, strict=True))
    assert columns["vars.A"] == 1.0 and columns["vars.C"] == 1.0
    assert d[paths.index("phases.0.atoms.0.biso")] == 0.0
    assert {e.path: e.value for e in table.entries}["phases.0.atoms.0.biso"] == 0.7

    with pytest.raises(ValueError, match="carries no freedom of its own"):
        ref.tie("phases.0.atoms.1.biso", "phases.0.atoms.0.biso")


def test_a_cycle_between_variables_is_refused(ref):
    ref.add_variable("A", 0.4, min=0.0, max=25.0)
    ref.add_variable("B", 0.4, min=0.0, max=25.0)
    ref.tie("vars.B", "vars.A")
    with pytest.raises(ValueError):
        ref.tie("vars.A", "vars.B")


# ------------------------------------------------- the equivalence bar, exactly
def test_the_residual_and_every_column_match_the_dot_path_spelling(
        four_site_pattern):
    """Where the claim is exact: the model, not the solver's path through it.

    The two arms differ only in *which* free parameter the four Biso rows
    follow, so the residual must agree bit for bit and each Jacobian column
    must agree with the column carrying the same parameter.  Before the
    dispatch fix in ``_column_identities`` the master's own column disagreed by
    8.6e-7 — the variable's name matched no analytic branch, so it silently
    took the whole-model FD fallback while the dot-path arm took the peak
    chain.
    """
    a, b = dot_path_arm(), variable_arm()
    a.set_vary([BISOS[0], "phases.0.scale"], True)
    b.set_vary(["vars.B_metal", "phases.0.scale"], True)
    ta, tb = a._working_table(), b._working_table()

    # the physical state the two tables decode to is identical, path by path
    va = {e.path: e.value for e in ta.entries}
    vb = {e.path: e.value for e in tb.entries}
    assert all(va[p] == vb[p] for p in va if p in vb)

    ma = compile_model(a.structure, a.instrument, four_site_pattern,
                       mode="rietveld")
    mb = compile_model(b.structure, b.instrument, four_site_pattern,
                       mode="rietveld")
    ra = _make_residual(ma, ta)(ta.x0())
    rb = _make_residual(mb, tb)(tb.x0())
    assert np.array_equal(ra, rb), "the two spellings are not the same model"

    ja = np.asarray(_jacobian_for(ma, ta, "numpy")(ta.x0()))
    jb = np.asarray(_jacobian_for(mb, tb, "numpy")(tb.x0()))
    assert ja.shape == jb.shape
    same_column = {BISOS[0]: "vars.B_metal"}
    for i, path in enumerate(ta.free_paths):
        j = tb.free_paths.index(same_column.get(path, path))
        assert np.array_equal(ja[:, i], jb[:, j]), f"column {path} differs"


def test_the_fit_is_bit_identical_where_the_column_order_coincides(
        four_site_pattern):
    """One free column, so both arms put it at the same index of θ.

    This is the control for the tolerance the next test carries: the columns
    are identical either way (above), so anything left is the solver reading θ
    in a different order — and with one column there is no different order to
    read.  Rwp, χ², the iteration count, every dependent's value and the esd
    all come back bit for bit.
    """
    plan = rx.RefinementPlan(stages=[
        rx.Stage("biso", ["phases.*.atoms.*.biso", "vars.*"], max_iter=40)])
    a, b = dot_path_arm(master_max=MASTER_MAX), variable_arm(master_max=MASTER_MAX)
    ra = a.fit(four_site_pattern, plan=plan)
    rb = b.fit(four_site_pattern, plan=plan)

    assert a._working_table().free_paths == [BISOS[0]]
    assert b._working_table().free_paths == ["vars.B_metal"]
    assert ra.statistics.rwp == rb.statistics.rwp
    assert ra.statistics.chi2 == rb.statistics.chi2
    assert [s.n_iterations for s in ra.stages] == [s.n_iterations for s in rb.stages]
    for j in range(4):
        assert (a.fitted_structure.phases[0].atoms[j].biso.value
                == b.fitted_structure.phases[0].atoms[j].biso.value)
    esd_a = {p.path: p.stderr for p in ra.parameters}[BISOS[0]]
    esd_b = {p.path: p.stderr for p in rb.parameters}["vars.B_metal"]
    assert esd_a == esd_b


def test_the_converged_fit_agrees_when_the_variable_sits_elsewhere_in_theta(
        four_site_pattern):
    """A variable is appended, so in a multi-stage plan it is θ's *last* column.

    The columns are identical (above) and a one-column fit is bit-identical
    (above), so what is left is scipy's TRF reading the same columns in a
    different order — measured at 1.6e-9 relative on the refined Biso and
    7.8e-14 on Rwp.  The bar is set an order of magnitude above that and is a
    statement about the **solver**, not about this feature: the parameter count
    and every physical answer agree far inside any esd (the master's is 0.19).
    """
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                 max_iter=30),
        rx.Stage("cell", ["phases.*.cell.*"], max_iter=30),
        rx.Stage("biso", ["phases.*.atoms.*.biso", "vars.*"], max_iter=30),
    ])
    a, b = dot_path_arm(), variable_arm()
    ra = a.fit(four_site_pattern, plan=plan)
    rb = b.fit(four_site_pattern, plan=plan)

    assert (ra.statistics.n_free_parameters
            == rb.statistics.n_free_parameters), "a renaming changed the count"
    assert rb.statistics.rwp == pytest.approx(ra.statistics.rwp, rel=1e-12)
    for j in range(4):
        x = a.fitted_structure.phases[0].atoms[j].biso.value
        y = b.fitted_structure.phases[0].atoms[j].biso.value
        assert y == pytest.approx(x, rel=1e-8)
    esd_a = {p.path: p.stderr for p in ra.parameters}[BISOS[0]]
    esd_b = {p.path: p.stderr for p in rb.parameters}["vars.B_metal"]
    assert esd_b == pytest.approx(esd_a, rel=1e-8)


def test_the_parameter_count_drops_by_the_number_of_dependents(ref, pattern):
    before = len(ref._working_table().free_paths)
    ref.set_vary(["phases.0.atoms.*.biso"], True)
    freed = len(ref._working_table().free_paths)
    assert freed == before + 2

    ref.add_variable("B_all", 0.7, min=0.0, max=25.0, vary=True)
    for path in ("phases.0.atoms.0.biso", "phases.0.atoms.1.biso"):
        ref.tie(path, "vars.B_all")
    after = ref._working_table().free_paths
    assert len(after) == freed - 2 + 1
    assert "vars.B_all" in after
    assert not any(p.endswith(".biso") for p in after)


# ------------------------------------------------------------------ persistence
def test_a_fit_moves_the_variable_and_the_next_build_starts_from_there(
        four_site_pattern):
    """``apply_to_models`` has nothing to write a variable to, so ``_write_back``
    is the only thing that carries its refined value forward.  Without it the
    next table build re-declares the variable at its *declared* value and every
    dependent silently reverts."""
    plan = rx.RefinementPlan(stages=[
        rx.Stage("biso", ["phases.*.atoms.*.biso", "vars.*"], max_iter=40)])
    ref = variable_arm(master_max=MASTER_MAX)
    declared = ref._variables["B_metal"].value
    ref.fit(four_site_pattern, plan=plan)

    refined = ref._variables["B_metal"].value
    assert refined != declared
    rebuilt = {e.path: e.value for e in ref._working_table().entries}
    assert rebuilt["vars.B_metal"] == refined
    assert rebuilt[BISOS[2]] == pytest.approx(2.0 * refined)
    # and the models agree with the register, which is the whole point
    assert ref.fitted_structure.phases[0].atoms[0].biso.value == refined


def test_a_variable_survives_a_history_checkout_with_its_parameter_count(
        ref, pattern):
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                 max_iter=20)])
    ref.fit(pattern, plan=plan)
    before = ref.history.head

    ref.add_variable("B_all", 0.7, min=0.0, max=25.0, vary=True)
    ref.tie("phases.0.atoms.0.biso", "vars.B_all")
    ref.tie("phases.0.atoms.1.biso", "vars.B_all", scale=2.0)
    declared = ref.history.head
    n_with = len(ref._working_table().free_paths)

    ref.checkout(before)
    assert ref._variables == {}
    assert "vars.B_all" not in {r.path for r in ref.parameters()}

    ref.checkout(declared)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["vars.B_all"].vary
    assert rows["phases.0.atoms.1.biso"].tie.terms == [("vars.B_all", 2.0)]
    assert len(ref._working_table().free_paths) == n_with


def test_a_set_variable_node_renders_an_api_call_that_runs(ref, pattern):
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"], max_iter=5)])
    ref.fit(pattern, plan=plan)
    ref.add_variable("B_all", 0.7, min=0.0, max=25.0, vary=True)
    ref.add_variable("B_extra", 0.1, min=0.0, max=25.0)
    # a one-entry dict *is* a one-source tie, and renders as the spelling that
    # says so; only a genuinely multi-source tie takes the mapping form, which
    # is the call WP-1119 gave the verb and the comment it replaced
    ref.tie("phases.0.atoms.0.biso", {"vars.B_all": 1.0})
    ref.tie("phases.0.atoms.1.biso", {"vars.B_all": 1.0, "vars.B_extra": 2.0})
    calls = [n.action.api_call() for n in ref.history.nodes.values()
             if n.action.kind in ("set_variable", "set_tie")]
    assert calls == [
        "ref.add_variable('B_all', 0.7, vary=True, min=0.0, max=25.0)",
        "ref.add_variable('B_extra', 0.1, min=0.0, max=25.0)",
        "ref.tie('phases.0.atoms.0.biso', 'vars.B_all')",
        "ref.tie('phases.0.atoms.1.biso', "
        "{'vars.B_all': 1.0, 'vars.B_extra': 2.0})",
    ]
    # the rendered calls run, and reproduce the state they describe
    replay = rx.Refinement(*perturbed_models())
    for call in calls:
        eval(compile(call, "<api_call>", "eval"), {"ref": replay, "rx": rx})
    assert ({r.path: r for r in replay.parameters()}["phases.0.atoms.0.biso"]
            .tie.terms == [("vars.B_all", 1.0)])


def test_a_variable_survives_a_history_file_round_trip(ref, pattern, tmp_path):
    path = tmp_path / "vars.jsonl"
    ref = rx.Refinement(*perturbed_models(), history=str(path))
    ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"], max_iter=5)]))
    ref.add_variable("B_all", 0.7, min=0.0, max=25.0, vary=True)
    ref.tie("phases.0.atoms.0.biso", "vars.B_all")
    head = ref.history.head

    reloaded = rx.RefinementTree.load(path)
    state = reloaded[head].state
    assert state.variables["B_all"].value == 0.7
    assert state.variables["B_all"].max == 25.0
    assert state.ties["phases.0.atoms.0.biso"].terms == [("vars.B_all", 1.0)]


def test_a_dependent_that_becomes_symmetry_tied_is_reported_and_dropped(ref):
    """Symmetry outranks a user tie, and a variable's dependents inherit that."""
    ref.add_variable("L", 4.16, min=1.5, max=10.0)
    structure = ref.structure.model_copy(deep=True)
    structure.phases[0].space_group = "P 1"   # b is nobody's dependent here
    ref.edit(structure=structure)
    ref.tie("phases.0.cell.b", "vars.L")
    assert {r.path: r for r in ref.parameters()}["phases.0.cell.b"].tie.user

    structure = ref.structure.model_copy(deep=True)
    structure.phases[0].space_group = "P m -3 m"   # now b follows a
    with pytest.warns(UserWarning, match="no longer apply"):
        ref.edit(structure=structure)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.cell.b"].tie.sources == ["phases.0.cell.a"]
    assert not rows["phases.0.cell.b"].tie.user
    # the register was pruned against the model that was accepted
    assert "phases.0.cell.b" not in ref._ties
    # and the variable itself is untouched: nothing followed it any more
    assert ref.remove_variable("L") == "vars.L"
