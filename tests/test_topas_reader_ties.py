"""Reading a TOPAS file's constraints back as rietx ties (#721 item 4, showcase M6).

The files here are written by hand in the forms ``write_topas_inp`` writes and
TOPAS echoes into its ``.out`` (Technical Reference § 2.3): a parameter name
written at several values, and an equation affine in names. Read without
``constraints=``, every copy comes back an independent number, which is the
model with its constraints dropped.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.io.projects import topas
from rietx.io.projects.topas_ties import TopasConstraints, affine_of, apply_ties

CELL = "  a ! 5.0\n  b ! 6.0\n  c ! 7.0\n  al ! 90\n  be ! 90\n  ga ! 90\n"


def _read(tmp_path, text, **kw):
    path = tmp_path / "t.inp"
    path.write_text(text, encoding="utf-8")
    cons = TopasConstraints()
    s = topas.to_structure(topas.read_topas_inp(path), constraints=cons, **kw)
    return s, cons


NUCLEAR = f'''str
  phase_name "t"
  space_group "P 1"
  scale s1 0.5
{CELL}  site A1 x ! 0.1 y ! 0.2 z ! 0.3 occ Ba ! 1 beq bA 0.7
  site A2 x ! 0.6 y ! 0.7 z ! 0.8 occ Ba ! 1 beq bA 0.7
  site A3 x ! 0.3 y ! 0.1 z ! 0.9 occ Ba ! 1 beq = 2*bA - 0.4;
  site A4 x ! 0.9 y ! 0.4 z ! 0.2 occ Ba ! 1 beq = 0.5*bQ + 0.1;
'''


def test_a_shared_name_is_one_parameter(tmp_path):
    s, cons = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    ties = {t.path: t for t in cons.ties}
    assert ties["phases.0.atoms.1.biso"].terms == [("phases.0.atoms.0.biso", 1.0)]
    assert cons.free["phases.0.atoms.0.biso"] is True


def test_an_affine_equation_is_a_tie_on_the_value_carrying_its_name(tmp_path):
    s, cons = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    ties = {t.path: t for t in cons.ties}
    t = ties["phases.0.atoms.2.biso"]
    assert t.terms == [("phases.0.atoms.0.biso", 2.0)] and t.const == pytest.approx(-0.4)
    assert s.phases[0].atoms[2].biso.value == pytest.approx(2 * 0.7 - 0.4)


def test_a_name_no_value_carries_is_carried_by_its_first_equation(tmp_path):
    """``bQ`` is only declared (``prm``): A4's equation carries it, nothing
    else uses it, so it is A4's own free parameter, not a tie."""
    s, cons = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    assert "phases.0.atoms.3.biso" not in {t.path for t in cons.ties}
    assert cons.free["phases.0.atoms.3.biso"] is True


def test_without_constraints_the_numbers_are_unchanged(tmp_path):
    path = tmp_path / "t.inp"
    path.write_text("prm bQ 1.2\n" + NUCLEAR, encoding="utf-8")
    plain = topas.to_structure(topas.read_topas_inp(path))
    tied, _ = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    assert plain == tied


def test_an_equation_that_is_not_affine_is_read_as_its_value_and_said(tmp_path):
    text = "prm bQ 1.2\n" + NUCLEAR.replace("= 0.5*bQ + 0.1;", "= bQ*bQ;")
    s, cons = _read(tmp_path, text)
    assert any("not affine" in m for m in cons.skipped)
    assert s.phases[0].atoms[3].biso.value == pytest.approx(1.44)


@pytest.mark.parametrize("expr, terms, const", [
    ("2*a - 0.4", {"a": 2.0}, -0.4),
    ("-a", {"a": -1.0}, 0.0),
    ("a/9.0 + b*3 + 1", {"a": 1 / 9.0, "b": 3.0}, 1.0),
    ("0.25", {}, 0.25),
])
def test_affine_of(expr, terms, const):
    t, c = affine_of(expr)
    assert t == pytest.approx(terms) and c == pytest.approx(const)


def test_a_product_of_names_is_not_affine():
    with pytest.raises(ValueError):
        affine_of("a*b")


def _magnetic(part_sites: str, extra: str = "") -> str:
    return f'''neutron_data
LP_Factor(90)
prm m1 3.0
prm p0_magnetic_lor_strain 0.2 min 0
prm !p0_magnetic_lor_size 0
{extra}str
  phase_name "m"
  space_group "P 1"
  scale s1 2.0
{CELL}  site Fe1 x ! 0.1 y ! 0.2 z ! 0.3 occ Fe+3 ! 1 beq bF 0.5
  site Fe2 x ! 0.6 y ! 0.7 z ! 0.8 occ Fe+3 ! 1 beq bF 0.5
  site O1 x ! 0.3 y ! 0.4 z ! 0.5 occ O ! 1 beq ! 0.9
str
  phase_name "m magnetic part"
  mag_space_group 1.1
  scale s1 2.0
{CELL}{part_sites}'''


PART = ("  site Fe1 x ! 0.1 y ! 0.2 z ! 0.3 occ Fe+3 ! 1 beq bF 0.5 mlx ! 0 "
        "mly = 0.16666666666666666*m1; mlz ! 0 mag_only\n"
        "  site Fe2 x ! 0.6 y ! 0.7 z ! 0.8 occ Fe+3 ! 1 beq bF 0.5 mlx ! 0 "
        "mly = -0.16666666666666666*m1; mlz ! 0 mag_only\n")


def test_the_magnetic_part_is_merged_back_into_its_phase(tmp_path):
    s, _ = _read(tmp_path, _magnetic(PART))
    assert len(s.phases) == 1
    ph = s.phases[0]
    assert ph.magnetic_symmetry is not None
    fe1, fe2, o1 = ph.atoms
    assert fe1.moment.values() == pytest.approx((0.0, 3.0, 0.0))     # mly × b
    assert fe2.moment.values() == pytest.approx((0.0, -3.0, 0.0))
    assert o1.moment is None and fe1.moment.ion == "Fe3+"
    assert ph.magnetic_lor_strain.value == 0.2 and ph.magnetic_lor_strain.vary
    assert ph.magnetic_lor_size.vary is False


def test_a_part_that_is_not_all_mag_only_stays_refused(tmp_path):
    with pytest.raises(topas.TopasInpError, match="mag_only"):
        _read(tmp_path, _magnetic(PART.replace(" mag_only\n", "\n", 1)
                                  .replace("mlz ! 0\n", "mlz ! 0 mag_only\n", 0)
                                  + "  site O1 x ! 0.3 y ! 0.4 z ! 0.5 occ O ! 1 "
                                    "beq ! 0.9 mag_only\n"))


def test_one_moment_name_is_one_moment_parameter(tmp_path):
    s, cons = _read(tmp_path, _magnetic(PART))
    moment = [t for t in cons.ties if ".moment." in t.path]
    assert {t.path for t in moment} == {f"phases.0.atoms.1.moment.dof{k}" for k in range(3)}
    assert cons.free["phases.0.atoms.0.moment.dof0"] is True
    assert cons.free["phases.0.atoms.0.moment.dof1"] is False
    ref = rx.Refinement(s, rx.Instrument.constant_wavelength_neutron(2.4), history=False)
    grid = np.arange(10.0, 100.0, 0.05)
    before = np.asarray(ref.predict(grid))
    apply_ties(ref, cons)
    assert np.abs(np.asarray(ref.predict(grid)) - before).max() < 1e-9 * before.max()
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.1.moment.dof0"].tie is not None
    assert rows["phases.0.atoms.1.biso"].tie is not None
    free = sorted(r.path for r in ref.parameters() if r.vary and r.tie is None
                  and not r.path.startswith("instrument."))
    assert free == ["phases.0.atoms.0.biso", "phases.0.atoms.0.moment.dof0",
                    "phases.0.magnetic_lor_strain", "phases.0.scale"]


def test_scale_rietx_takes_out_topas_constant(tmp_path):
    s, _ = _read(tmp_path, _magnetic(PART), scale="rietx")
    assert s.phases[0].scale.value == pytest.approx(0.02)            # ÷ 100
    xray = "LP_Factor(0)\nprm bQ 1.2\n" + NUCLEAR
    s, _ = _read(tmp_path, xray, scale="rietx")
    assert s.phases[0].scale.value == pytest.approx(1.0)             # ÷ K = 0.5
    with pytest.raises(topas.TopasInpError, match="neither"):
        _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR, scale="rietx")
    s, _ = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    assert s.phases[0].scale.value == 0.5                            # the default


def test_the_extinction_is_read_back_by_the_writers_name(tmp_path):
    s, _ = _read(tmp_path, "prm !p0_extinction 8.5\nprm bQ 1.2\n" + NUCLEAR)
    assert s.phases[0].extinction.value == 8.5 and not s.phases[0].extinction.vary
