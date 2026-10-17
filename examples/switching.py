"""The fluorapatite refinement behind the Switching tab's three pages (WP-1984).

`docs/docs/switching/topas.md`, `gsas2.md` and `fullprof.md` show lines from
the files this script writes and numbers from the objects it reads back, and
none of them is typed from memory.  Every figure a page quotes is asserted
here, so a change that moves one fails `tests/test_examples.py` and the page
is corrected in the same change.

Data: the GSAS-II `LabData` tutorial fluorapatite and GSAS's converged fit of
it, `FAP.EXP`, both shipped in `rietx.examples`.  Everything it writes goes
to a temporary directory.
"""

import math
import tempfile
from pathlib import Path

import rietx as rx
from rietx.examples import examples_dir
from rietx.io.projects.topas_ties import TopasConstraints, apply_ties

OXYGENS = ["phases.0.atoms.4.biso", "phases.0.atoms.5.biso", "phases.0.atoms.6.biso"]
LIMITS = (15, 130)


def build() -> tuple[rx.PatternData, rx.Refinement]:
    data = rx.read_pattern(examples_dir() / "FAP.XRA")
    structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    instrument.geometry.axial_sl.value = 0.02
    instrument.geometry.axial_hl.value = 0.02
    instrument.background = rx.BackgroundChebyshev.with_terms(6)
    return data, rx.Refinement(structure, instrument)


def free_paths(ref: rx.Refinement) -> list[str]:
    return [row.path for row in ref.parameters() if row.vary]


def gsas2_page() -> None:
    """A four-stage plan, the counterpart of a GSAS-II refinement recipe."""
    data, ref = build()
    plan = rx.RefinementPlan(stages=[
        rx.Stage("background", turn_on=["instrument.background.*", "phases.*.scale"]),
        rx.Stage("cell", turn_on=["instrument.zero_shift", "phases.*.cell.*"]),
        rx.Stage("profile", turn_on=["instrument.profile.*"]),
        rx.Stage("atoms", turn_on=["phases.*.atoms.*.dof.*", "phases.*.atoms.*.biso"]),
    ])
    result = ref.fit(data, plan=plan, two_theta_limits=LIMITS)
    assert result.status == "converged"
    assert math.isclose(result.statistics.rwp, 0.0893, abs_tol=5e-4)
    assert [(s.name, len(s.freed)) for s in result.stages] == [
        ("background", 7), ("cell", 3), ("profile", 5), ("atoms", 19)]


def topas_page(out: Path) -> rx.Refinement:
    """A tie, a hold, and the file rietx writes for TOPAS from the refined state."""
    data, ref = build()
    first = ref.fit(data, plan="mccusker_structural", two_theta_limits=LIMITS)
    assert math.isclose(first.statistics.rwp, 0.0893, abs_tol=5e-4)
    ref.tie_equal(OXYGENS)
    ref.set_values({"instrument.zero_shift": 0.0})
    ref.hold(["instrument.zero_shift"])
    held = ref.fit(data, plan="lab_bragg_brentano", two_theta_limits=LIMITS)
    assert "HOLD_BLOCKED_PLAN" in [d.code for d in held.diagnostics]
    final = ref.fit(data, plan="mccusker_structural", two_theta_limits=LIMITS)
    assert math.isclose(final.statistics.rwp, 0.0890, abs_tol=5e-4)

    path = out / "refined.inp"
    rx.write_topas_inp(ref.fitted_structure, path, free=ref, scale="topas",
                       instrument=ref.fitted_instrument, pattern=data)
    text = path.read_text(encoding="utf-8")
    assert text.count("beq O5_biso") == 3
    assert "  th2_offset ! 0\n" in text
    assert "  bkg @ " in text and "  b p0_cell_a " in text
    assert "  weighting = 1 / SigmaYobs^2;" in text

    notes: list = []
    model = rx.read_project_model(path, diagnostics=notes)
    assert model.format.name == "topas_inp"
    assert model.stated.data_files == ["refined.xye"]
    assert (model.stated.background_terms, model.stated.background_refined) == (6, True)
    cons = TopasConstraints()
    back = rx.Refinement(model.to_structure(scale="rietx", constraints=cons),
                         rx.Instrument.bragg_brentano(radiation="CuKa"))
    apply_ties(back, cons)
    assert free_paths(back)[:4] == [
        "phases.0.cell.a", "phases.0.cell.c", "phases.0.scale", "phases.0.extinction"]
    # The oxygens' shared name came back as a tie: two of the three are not free.
    assert OXYGENS[0] in free_paths(back) and not set(OXYGENS[1:]) & set(free_paths(back))
    assert [d.code for d in model.diagnostics] == ["TOPAS_FEATURES_NOT_IMPORTED"] * 2
    # topas.md quotes this message after the file's own path.
    assert model.diagnostics[0].message.endswith(
        "this import is partial. The file states peak profile (Finger_et_al, peak_type, "
        "pv_fwhm, pv_lor) [fluorapatite]; phase scaling (scale_pks) [fluorapatite], and none "
        "of it reaches the built structure.")
    return ref


def gsas_conversions(ref: rx.Refinement, out: Path) -> None:
    """The instrument file GSAS-II reads, and the GSAS experiment file."""
    path = out / "refined.instprm"
    rx.write_gsas2_instprm(ref.fitted_instrument, path)
    u_instprm = next(float(line.split(":")[1])
                     for line in path.read_text(encoding="utf-8").splitlines()
                     if line.startswith("U:"))
    u_rietx = rx.read_gsas2_instprm(path).profile.u.value
    assert math.isclose(u_instprm * 8 * math.log(2) * 1e-4, u_rietx, rel_tol=1e-6)

    model = rx.read_project_model(examples_dir() / "FAP.EXP")
    assert (model.format.name, model.stated.rwp, model.stated.rp) == ("gsas_exp", 0.1005, 0.0766)
    assert (model.stated.n_variables, model.stated.n_observations) == (28, 5750)
    assert model.stated.profile().refined_names == ("LX", "LY", "shft")
    structure_only = rx.Refinement(model.to_structure(),
                                   rx.Instrument.bragg_brentano(radiation="CuKa"))
    assert len(free_paths(structure_only)) == 21
    assert [d.code for d in model.diagnostics] == ["GSAS_EXP_BACKGROUND_NOT_CARRIED"]
    # gsas2.md quotes this message after the file's own path.
    assert model.diagnostics[0].message.endswith(
        "histogram 1 fitted GSAS background function 5 (reciprocal expansion in Q², for "
        "low-angle air scatter) with 3 terms. The coefficients are on "
        "model.histograms[...].background.")


def fullprof_page(out: Path) -> None:
    """One codeword for each free parameter, and the same free set read back."""
    structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
    phase = structure.phases[0]
    phase.cell.a.vary = phase.cell.c.vary = phase.scale.vary = True
    phase.atoms[0].biso.vary = True
    phase.atoms[6].z.vary = True
    path = out / "flags.pcr"
    rx.write_fullprof_pcr(structure, path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert "0.0 0.0 0.0 11.0 0.0" in lines     # Ca1's B
    assert "0.0 0.0 21.0 0.0 0.0" in lines     # O7's z
    assert "31.0 0.0 0.0 0.0 0.0 0.0" in lines  # the scale
    assert "41.0 0.0 51.0 0.0 0.0 0.0" in lines  # a and c; b follows a by symmetry

    model = rx.read_project_model(path)
    ref = rx.Refinement(model.to_structure(), rx.Instrument.bragg_brentano(radiation="CuKa"))
    assert free_paths(ref) == [
        "phases.0.cell.a", "phases.0.cell.c", "phases.0.scale", "phases.0.atoms.0.biso",
        "phases.0.atoms.6.dof.0", "phases.0.atoms.6.dof.1", "phases.0.atoms.6.dof.2"]


def main() -> None:
    gsas2_page()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        ref = topas_page(out)
        gsas_conversions(ref, out)
        fullprof_page(out)
    print("every figure the Switching pages quote reproduced")


if __name__ == "__main__":
    main()
