"""The bracketed-label audit, as a test rather than as a table (M-3 item 5b).

WP-1419 § Inherited: "``Phase.space_group`` is read at 80 sites in 23 modules,
including five foreign-format writers … gemmi raises on the label
(``ValueError: Unknown space-group name: Pm [unnamed in 2a,b,a+c]``), so the
bracket fails loudly, which is the safety property working.  WP-1103's
third-member rule applies: audit the readers before the field lands, and the
exporters refuse rather than write a symbol they cannot honour."

The audit's *table* is a document; this is its executable half.  Every surface
below is handed a phase whose ``space_group`` is a bracketed label and whose
group is its ``symmetry_operations``, and each must land in one of two states:

* **tolerates it** — the surface routes through
  ``crystallography.symmetry.resolve_group`` (or only stores/prints the string)
  and produces the same answer it would for a named group; or
* **refuses by name** — it raises with the phase and the label in the message.

The state that is not allowed is the third: gemmi's own
``Unknown space-group name`` reaching a caller from inside a viewer endpoint or
an exporter, which names no phase and suggests nothing.

**What this fork's tree does and does not carry.**  The five foreign-format
writers the review counted are on `main`; this branch's base predates four of
them — ``io/projects/`` here holds ``fullprof.py`` and ``topas.py`` as project
*readers* (they build a ``Phase`` from a foreign file, where a bracket cannot
appear) plus ``coverage.py``, and there is no ``gsas.py``, ``gsas2.py``,
``registry.py`` or ``write_topas_inp``.  The one writer that takes a phase's
symmetry here is the CIF exporter, and it already honours the label: it writes
the bracket into ``_space_group_name_H-M_alt`` and the operations into
``_space_group_symop_operation_xyz``, which is the round trip Q-17 built.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic import supercell as sc
from rietx.crystallography.symmetry import resolve_group, split_group_label
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure

WAVELENGTH = 1.5406
TWO_THETA = np.arange(10.0, 90.0, 0.05)


def parent_phase() -> Phase:
    """The toy two-site Pnma parent (verbatim, so this file stands alone)."""
    return Phase(
        name="parent", space_group="P n m a",
        cell=Cell(a=Parameter(value=5.4), b=Parameter(value=7.6),
                  c=Parameter(value=5.3), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Ti", species="Ti", x=Parameter(value=0.1),
                    y=Parameter(value=0.25), z=Parameter(value=0.3),
                    biso=Parameter(value=0.6)),
               Atom(label="O", species="O", x=Parameter(value=0.42),
                    y=Parameter(value=0.25), z=Parameter(value=0.11),
                    biso=Parameter(value=0.8))],
        scale=Parameter(value=0.02))


@pytest.fixture(scope="module")
def labelled_phase() -> Phase:
    """A real child whose group no Hermann-Mauguin symbol names in its cell."""
    statement = sc.displacive_statement(
        parent_phase(), ("1/2", "0", "1/2"), irrep="S3", direction="(a,b)")
    phase = statement.phase
    assert split_group_label(phase.space_group) is not None, phase.space_group
    assert phase.symmetry_operations, "the label without a list is not a phase"
    return phase


@pytest.fixture(scope="module")
def fitted(labelled_phase):
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ref = rx.Refinement(Structure(phases=[labelled_phase]), ins)
    y = np.asarray(ref.predict(TWO_THETA))
    data = rx.PatternData(two_theta=TWO_THETA.tolist(),
                          intensity=np.maximum(y, 1.0).tolist())
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"], max_iter=20)]))
    return ref, result, ins


# --------------------------------------------------------------- tolerates it
def test_the_label_never_reaches_gemmi_through_resolve_group(labelled_phase):
    """The one authority: every consumer asks this and gets the operations."""
    group = resolve_group(labelled_phase.space_group,
                          labelled_phase.symmetry_operations)
    assert group.xhm() == labelled_phase.space_group
    assert len(group.operations()) == len(labelled_phase.symmetry_operations)
    # and the raw label does raise, which is the safety property working
    from rietx.crystallography.symmetry import get_spacegroup

    with pytest.raises(ValueError):
        get_spacegroup(labelled_phase.space_group)


def test_predict_fit_and_report_all_take_a_labelled_phase(fitted):
    ref, result, _ins = fitted
    assert result.status == "converged"
    assert np.isfinite(np.asarray(ref.predict(TWO_THETA))).all()
    report = ref.report()
    assert len(report.distortion) == len(ref.structure.phases[0].distortion_modes)


def test_the_cif_writer_honours_the_label_rather_than_refusing(fitted):
    """The review's own claim about the CIF route, checked on this tree.

    The bracket goes out as ``_space_group_name_H-M_alt`` and the group as the
    ``_space_group_symop_operation_xyz`` loop, so a reader gets the operations
    rather than a symbol that names a different group.
    """
    from rietx.io.exporters import write_refinement_cif

    ref, result, ins = fitted
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "refinement.cif"
        write_refinement_cif(result, ref.fitted_structure, ins, path)
        text = path.read_text(encoding="utf-8")
    assert "unnamed in" in text, "the label was dropped on the way out"
    assert "_space_group_symop_operation_xyz" in text, (
        "the operations are the group; a label without them is not a structure")


def test_the_cif_round_trip_returns_the_same_group(fitted, tmp_path):
    """Written and read back: the label and the operations both survive."""
    from rietx.crystallography.cif import structure_from_cif, structure_to_cif

    ref, _result, _ins = fitted
    phase = ref.fitted_structure.phases[0]
    path = tmp_path / "child.cif"
    structure_to_cif(Structure(phases=[phase]), str(path))
    back = structure_from_cif(str(path)).phases[0]
    assert back.space_group == phase.space_group
    assert back.symmetry_operations == phase.symmetry_operations


def test_the_3d_viewer_takes_a_labelled_phase(labelled_phase):
    """``gui.structure3d.build`` — the one reader this rung had to fix.

    It resolved the phase's symbol with ``get_spacegroup`` and would have
    raised gemmi's ``Unknown space-group name`` out of a viewer endpoint, with
    no phase named and nothing to do about it.  One line: ``resolve_group``,
    which every other consumer already calls.
    """
    from rietx.gui import structure3d

    payload = structure3d.build(Structure(phases=[labelled_phase]), 0)
    assert payload["space_group"] == labelled_phase.space_group
    assert payload["sites"], "the viewer drew nothing"


def test_the_recipe_writer_writes_no_symbol_at_all(fitted):
    """PowderLine's four tables carry cells, peaks and parameters, not a group."""
    from rietx.io.recipe import write_recipe_tables

    ref, _result, _ins = fitted
    with tempfile.TemporaryDirectory() as directory:
        written = write_recipe_tables(ref, directory)
        text = "\n".join(Path(p).read_text(encoding="utf-8")
                         for p in written.values())
    assert "unnamed in" not in text
    assert "space_group" not in text


# ------------------------------------------------------------ refuses by name
def test_a_bracketed_label_with_no_operation_list_is_refused_by_name():
    """The schema's own refusal — the bracket *is* the claim that the symbol
    does not name the group, so without the list there is nothing left to be
    one.  Named here because it is what stops a foreign-format reader, a
    recipe payload or a hand-written JSON from producing a phase no consumer
    could resolve."""
    phase = parent_phase()
    doc = phase.model_dump()
    doc["space_group"] = "Pm [unnamed in 2a,b,a+c]"
    with pytest.raises(ValueError, match="nothing is left to be the group"):
        Phase.model_validate(doc)


def test_a_recipe_payload_cannot_smuggle_a_label_in(tmp_path):
    """The recipe reader builds a ``Phase`` and the schema refuses above it.

    ``io/recipe._read_phase`` passes the payload's ``space_group`` straight to
    ``Phase``, which is the right shape: the refusal belongs to the schema, so
    every route in gets the same message rather than one per reader.
    """
    from rietx.io.recipe import RecipeError, read_recipe

    payload = {
        "pattern": {"path": "nonexistent.xy"},
        "phases": {"toy": {"structure": {
            "space_group": "Pm [unnamed in 2a,b,a+c]",
            "cell": {"a": 5.4, "b": 7.6, "c": 5.3,
                     "alpha": 90.0, "beta": 90.0, "gamma": 90.0},
            "atoms": [{"label": "Ti", "species": "Ti",
                       "x": 0.1, "y": 0.25, "z": 0.3}]}}},
    }
    with pytest.raises((RecipeError, ValueError, FileNotFoundError)):
        read_recipe(payload)


def test_the_gui_phase_endpoint_refuses_a_label_by_name():
    """``gui.session`` builds a phase from a client payload and names the field.

    A bracket arriving there is a caller's typo rather than a package-built
    child, so the refusal is the right answer — but it has to be a
    ``GuiError`` naming ``structure.space_group``, not gemmi's own text with no
    field attached.
    """
    from rietx.gui.session import GuiError, _typed_cell_structure

    with pytest.raises(GuiError) as excinfo:
        _typed_cell_structure({
            "space_group": "Pm [unnamed in 2a,b,a+c]",
            "cell": {"a": 5.4, "b": 7.6, "c": 5.3,
                     "alpha": 90.0, "beta": 90.0, "gamma": 90.0}})
    assert excinfo.value.where == ["structure.space_group"]


# ------------------------------- a child as somebody else's parent (the class)
@pytest.fixture(scope="module")
def unnamed_parent(labelled_phase) -> Phase:
    """The same child, offered as a *parent* — modes stripped so it qualifies."""
    return labelled_phase.model_copy(update={"distortion_modes": [],
                                             "name": "child-as-parent"})


def test_a_second_generation_child_is_refused_by_name(unnamed_parent):
    """The one real crash class this audit found, and the fork's own answer.

    Building a child *of a child* — adding magnetic order on top of a phase
    that is already an unnamed displacive child, which is exactly the workflow
    a second order parameter needs — used to raise

        ValueError: unknown space group symbol: 'Pm [unnamed in 2a,b,a+c]'

    from four frames down, naming no phase, no bracket convention and nothing
    to do about it.  It is a refusal rather than a pass-through because the
    derivation genuinely cannot be served: the small representations of a
    k-vector come from tables keyed on the space-group *number*, and a group
    stated only as an operation list in a non-standard cell has none.
    """
    for caller, call in (
            ("displacive_statement()",
             lambda: sc.displacive_statement(unnamed_parent, ("1/2", "0", "0"),
                                             irrep="S1", direction="(a)")),
            ("displacive_statement()",
             lambda: sc.displacive_statement(
                 unnamed_parent,
                 components=[(("1/2", "0", "0"), "S1", "(a)")])),
    ):
        with pytest.raises(ValueError) as excinfo:
            call()
        message = str(excinfo.value)
        assert message.startswith(caller), message
        assert "child-as-parent" in message, message
        assert "unnamed in 2a,b,a+c" in message, message
        assert "needs a named parent" in message, message
        assert "space-group number" in message, message


def test_the_magnetic_supercell_builder_now_tolerates_it(unnamed_parent):
    """stage3 D2 moved this call from "refuses by name" to "tolerates it".

    Superseded (2026-09-18): the refusal this test used to pin fired on the
    *bracket*, before ``transform`` was ever parsed — measured directly by
    reverting the fix and observing the same ``ValueError`` message this test
    used to assert. That reasoning ("the small representations of a k-vector
    come from tables keyed on the space-group number, and an operator list
    has none") does not hold for ``magnetic_supercell``: its own
    ``nuclear_group="parent"`` path derives the nuclear group from the
    parent's operators directly (``_nuclear_group_of``, now taking
    ``symmetry_operations`` too) rather than resolving a symbol, exactly the
    ``resolve_group`` route every other consumer of a phase's own group
    already takes. The transform now needs its origin-shift half
    (``";0,0,0"``) since there is no early exit skipping past it any more.
    """
    from rietx.crystallography.magnetic.operators import (
        MagneticGroup,
        MagneticOperator,
    )

    group = MagneticGroup.from_operations(
        [MagneticOperator.from_xyz("x,y,z,+1")])
    statement = sc.magnetic_supercell(
        unnamed_parent, group=group, transform="a,b,c;0,0,0",
        magnetic_species=["Ti"], ion={"Ti": "Mn3+"})
    assert split_group_label(unnamed_parent.space_group) is not None
    assert statement.phase.symmetry_operations is not None or \
        split_group_label(statement.child_space_group) is None


def test_the_fourier_builder_refuses_the_same_way(unnamed_parent):
    with pytest.raises(ValueError, match="needs a named parent"):
        sc.fourier_statement(
            unnamed_parent,
            [(("1/2", "0", "0"), "S1", "(a)"), (("0", "1/2", "0"), "S1", "(a)")],
            wavelength=WAVELENGTH, two_theta_max=90.0)


# --------------------------------------------------- small-fixes-20260917 item 2
def test_solve_magnetic_now_tolerates_an_unnamed_parent(unnamed_parent):
    """stage3 D2 moved this call from "refuses by name" to "tolerates it".

    Superseded (2026-09-18): ``strategy.magnetic.solve_magnetic`` used to
    reach ``enumerate_for``'s ``_isotropy.candidates(parent.space_group,
    ...)`` call refused outright by ``refuse_an_unnamed_parent`` before
    either candidate enumeration or the k != 0 supercell statement was ever
    tried — measured directly by reverting the fix and observing the exact
    ``ValueError`` this test used to assert. D-1 (COMMON.md) already builds
    every small irrep from the little group's own operators, projectively,
    with no tabulated-number lookup anywhere in
    ``crystallography.magnetic.irreps``/``isotropy``, so the parent's group
    is resolved from its operators (``resolve_group``) and threaded through
    instead. This toy displacive-child fixture carries no real magnetic
    intensity, so the answer is a workflow abstention naming that ("nothing
    to solve") rather than a raise -- the same shape a real unnamed-parent
    MAGNDATA entry with no signal would reach, and the one this test can
    build without a whole magCIF fixture.
    """
    from rietx.strategy.magnetic import solve_magnetic

    ins = rx.Instrument.constant_wavelength_neutron(1.5406, fwhm_deg=0.35)
    ref = rx.Refinement(Structure(phases=[unnamed_parent]), ins)
    y = np.asarray(ref.predict(TWO_THETA))
    data = rx.PatternData(two_theta=TWO_THETA.tolist(),
                          intensity=np.maximum(y, 1.0).tolist())
    ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"], max_iter=20)]))

    solution = solve_magnetic(ref, data)
    assert solution.verdict == "nothing to solve", solution.reason
    assert solution.space_group == unnamed_parent.space_group


def test_gui_orbits_refuses_an_unnamed_phase_by_name(unnamed_parent):
    """M3's D-h/item 5b remainder: ``gui.symmetry._orbits`` used to catch
    ``get_spacegroup``'s failure on a bracketed label and return ``[]`` —
    the audit's only *silent* wrong answer (an empty orbit list reads as "no
    collisions, multiplicity 1 everywhere" to both of its callers,
    :func:`~rietx.gui.symmetry.orbit_collisions` and the site diff's
    multiplicity column). It now refuses by name instead, checked both
    directly and through ``orbit_collisions`` (``orbits=None``), which is
    what a real caller reaches it through.
    """
    from rietx.gui import symmetry as gui_symmetry

    structure = Structure(phases=[unnamed_parent])
    for call in (lambda: gui_symmetry._orbits(structure, 0),
                lambda: gui_symmetry.orbit_collisions(structure, 0)):
        with pytest.raises(ValueError) as excinfo:
            call()
        message = str(excinfo.value)
        assert message.startswith("_orbits()"), message
        assert "child-as-parent" in message, message
        assert "unnamed in 2a,b,a+c" in message, message


def test_a_named_parent_is_untouched_by_the_guard():
    """The control: the guard fires on the bracket and on nothing else."""
    statement = sc.displacive_statement(
        parent_phase(), ("1/2", "0", "1/2"), irrep="S3", direction="(a,b)")
    assert statement.phase.distortion_modes


def test_the_guard_helper_is_the_one_authority():
    from rietx.crystallography.symmetry import refuse_an_unnamed_parent

    assert refuse_an_unnamed_parent(parent_phase(), "whatever()") is None
    with pytest.raises(ValueError, match="needs a named parent"):
        refuse_an_unnamed_parent(
            parent_phase().model_copy(
                update={"space_group": "P m [unnamed in 2a,b,c]"}),
            "whatever()")
