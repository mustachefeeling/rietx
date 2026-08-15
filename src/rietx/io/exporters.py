"""Export a finished refinement in the forms other codes and people consume.

Three artefacts, all built from state the refinement already computed and would
otherwise discard:

- a **reflection table** — one row per (emission line, reflection): hkl, d, 2θ,
  |F|², integrated intensity, multiplicity, phase, line.  Every emission line
  gets its own rows (never only λ₁): the calculated pattern really has a peak at
  each Kα₂ position, and a λ₁-only table would misrepresent the model — the same
  reasoning that makes ``RefinementResult.ticks`` carry every line.
- a **refinement CIF** — the structure with refined values *and* standard
  uncertainties, plus R-factors, wavelength and a profile/background
  description, and the observed/calculated pattern as a pdCIF loop.  The pattern
  loop uses the tags ``io.readers.read_pdcif`` reads, so the package round-trips
  against itself (export → re-read is the cheapest correctness test).
- a **QPA table** — the Hill-Howard weight fractions, carrying the
  "crystalline modelled content only" caveat into the file, not just the API.

References
----------
- Hall, Allen & Brown (1991) Acta Cryst. A47, 655 — CIF.
- Toby (2003) J. Appl. Cryst. 36, 1285 — pdCIF / powder diffraction tags.
- Toby (2006) Powder Diffraction 21, 67 — R-factor definitions.
- Hill & Howard (1987) J. Appl. Cryst. 20, 467 — ZMV weight fractions.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import gemmi
import numpy as np

from ..crystallography.cif import write_structure_block
from ..crystallography.lattice import d_spacings
from ..crystallography.structure_factor import structure_factors_squared
from ..model.forward import CompiledModel
from ..schemas.instrument import (
    BackgroundChebyshev,
    BackgroundFixedPlusChebyshev,
    BackgroundPSpline,
    Instrument,
)
from ..schemas.results import (
    PhaseAgreement,
    QuantitativePhaseAnalysis,
    RefinementResult,
)
from ..schemas.structure import Structure

_CELL_KEYS = ("a", "b", "c", "alpha", "beta", "gamma")


def _cell(values: dict[str, float], ip: int) -> tuple[float, ...]:
    return tuple(values[f"phases.{ip}.cell.{k}"] for k in _CELL_KEYS)


def _g(x: float) -> str:
    """A compact, round-trippable float string for column files."""
    return f"{x:.8g}"


# ======================================================================
# reflection table
# ======================================================================


@dataclass(frozen=True)
class ReflectionRow:
    """One (emission line, reflection) row of a reflection table.

    ``two_theta`` is the *apparent* position the model places the peak at
    (Bragg angle + zero shift + sample-displacement/transparency), matching the
    tick list — not the ideal Bragg angle.  ``f_squared`` is ``None`` in Le
    Bail/Pawley mode, where the per-reflection intensity is extracted or refined
    rather than computed from the structure.  ``intensity`` is the modelled
    integrated intensity of this (line, reflection): in Rietveld mode
    scale·multiplicity·|F|²·P·(line weight)·Lp·extinction·absorption·roughness.

    With anomalous scattering on, ``f_squared`` is the **Friedel-averaged**
    ⟨|F|²⟩ = ½(|F(h)|² + |F(−h)|²) that the powder peak actually contains, not
    the representative reflection's own |F(h)|² — the two differ in a
    non-centrosymmetric group, and only the average is observable in a powder
    (see ``crystallography.structure_factor``).
    """

    phase: str
    line: int              # emission-line index (0 = primary)
    wavelength: float      # Å
    h: int
    k: int
    l: int  # noqa: E741 - the crystallographic Miller index
    d: float               # Å
    two_theta: float       # deg, apparent position
    multiplicity: int
    f_squared: float | None
    intensity: float


REFLECTION_COLUMNS = (
    "phase", "line", "wavelength", "h", "k", "l", "d",
    "two_theta", "multiplicity", "f_squared", "intensity",
)


def reflection_table(model: CompiledModel, values: dict[str, float],
                     structure: Structure) -> list[ReflectionRow]:
    """Reflection rows for every (emission line, reflection) of every phase.

    ``model`` is the compiled model of the finished refinement,
    ``values = ParameterTable(structure, instrument).decode(x0())`` its refined
    parameter dict (see :meth:`rietx.Refinement.reflection_table`, which wires
    this up).  Reflections whose 2θ is non-physical at a given line's wavelength
    (``sinθ > 1``) are dropped for that line only.
    """
    rows: list[ReflectionRow] = []
    for ip, cp in enumerate(model.phases):
        name = structure.phases[ip].name
        cell = _cell(values, ip)
        hkl = cp.reflections.hkl
        mult = cp.reflections.multiplicity
        d = d_spacings(hkl, *cell)
        if model.mode == "rietveld":
            f2 = structure_factors_squared(hkl, d, cp.sites,
                                           *model._site_values(ip, values, cell))
        else:  # Le Bail / Pawley: intensity is extracted/refined, not from |F|²
            f2 = None
        peaks = model.phase_peaks(ip, values)
        for il, (pos, _gamma, _eta, intensity) in enumerate(peaks):
            lam = float(model.line_wavelengths[il])
            for j in range(len(hkl)):
                if not np.isfinite(pos[j]):
                    continue
                rows.append(ReflectionRow(
                    phase=name, line=il, wavelength=lam,
                    h=int(hkl[j][0]), k=int(hkl[j][1]), l=int(hkl[j][2]),
                    d=float(d[j]), two_theta=float(pos[j]),
                    multiplicity=int(mult[j]),
                    f_squared=None if f2 is None else float(f2[j]),
                    intensity=float(intensity[j]),
                ))
    return rows


def write_reflection_table(rows: list[ReflectionRow], path: str | Path, *,
                           delimiter: str | None = None) -> None:
    """Write reflection rows to CSV/TSV (delimiter inferred from suffix)."""
    p = Path(path)
    if delimiter is None:
        delimiter = "\t" if p.suffix.lower() in (".tsv", ".tab") else ","
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=delimiter)
        w.writerow(REFLECTION_COLUMNS)
        for r in rows:
            w.writerow([
                r.phase, r.line, _g(r.wavelength), r.h, r.k, r.l, _g(r.d),
                _g(r.two_theta), r.multiplicity,
                "" if r.f_squared is None else _g(r.f_squared), _g(r.intensity),
            ])


# ======================================================================
# QPA table
# ======================================================================


QPA_COLUMNS = (
    "phase", "weight_fraction", "weight_fraction_esd",
    "weight_fraction_corrected", "scale", "cell_mass", "cell_volume", "zmv",
    "mu_r", "brindley_tau", "particle_radius_um",
)


def _qpa_caveats(qpa: QuantitativePhaseAnalysis) -> list[str]:
    lines = [
        "Quantitative phase analysis — Hill & Howard (1987) ZMV weight "
        "fractions.",
        "SCOPE: fractions of the modelled CRYSTALLINE content only. An "
        "unmodelled amorphous fraction or a missing phase still makes these "
        "sum to 1.",
        f"method={qpa.method} crystalline_only={qpa.crystalline_only}",
    ]
    if qpa.microabsorption is not None:
        m = qpa.microabsorption
        lines.append(
            f"Brindley spherical microabsorption correction applied "
            f"(mu_mean={m.mu_mean_cm:.4g} 1/cm at lambda={m.wavelength:.6g} A); "
            "weight_fraction stays the UNCORRECTED Hill-Howard value, "
            "weight_fraction_corrected reported alongside. The corrected value "
            "inherits the (systematic, non-statistical) uncertainty of the "
            "supplied particle radii; the esd column belongs to the "
            "uncorrected fraction. Brindley's treatment is valid for mu_r <= "
            "0.05 — check the mu_r column.")
    elif qpa.microabsorption_skipped is not None:
        lines.append("Microabsorption correction skipped: "
                     f"{qpa.microabsorption_skipped}")
    return lines


def qpa_table_csv(qpa: QuantitativePhaseAnalysis, *, delimiter: str = ",") -> str:
    """The QPA table as CSV text, caveats carried in leading ``#`` comments.

    The crystalline-only scope and any microabsorption status are written into
    the file itself — a weight fraction quoted without them is misleading, so
    they travel with the artefact, not only the API docstring.
    """
    import io as _io

    buf = _io.StringIO()
    for line in _qpa_caveats(qpa):
        buf.write(f"# {line}\n")
    w = csv.writer(buf, delimiter=delimiter)
    w.writerow(QPA_COLUMNS)
    for q in qpa.phases:
        w.writerow([
            q.name, _g(q.weight_fraction),
            "" if q.weight_fraction_stderr is None else _g(q.weight_fraction_stderr),
            "" if q.weight_fraction_corrected is None else _g(q.weight_fraction_corrected),
            _g(q.scale), _g(q.cell_mass), _g(q.cell_volume), _g(q.zmv),
            "" if q.mu_r is None else _g(q.mu_r),
            "" if q.brindley_tau is None else _g(q.brindley_tau),
            "" if q.particle_radius_um is None else _g(q.particle_radius_um),
        ])
    return buf.getvalue()


def write_qpa_table(qpa: QuantitativePhaseAnalysis, path: str | Path, *,
                    delimiter: str | None = None) -> None:
    """Write the QPA table to CSV/TSV (delimiter inferred from suffix)."""
    p = Path(path)
    if delimiter is None:
        delimiter = "\t" if p.suffix.lower() in (".tsv", ".tab") else ","
    # newline="" is not optional and not cosmetic: qpa_table_csv builds its rows
    # with csv.writer, which emits \r\n per the CSV spec, so writing that string
    # through text mode translates each \n again and every line ends \r\r\n —
    # a file with a blank line between every row.  Invisible on POSIX, corrupt
    # on Windows, and measured there (WP-1002).  write_reflection_table above
    # already opens this way; this one did not.
    with p.open("w", newline="", encoding="utf-8") as fh:
        fh.write(qpa_table_csv(qpa, delimiter=delimiter))


# ======================================================================
# refinement CIF
# ======================================================================


def _profile_description(instrument: Instrument) -> str:
    prof = instrument.profile
    return ("TCHZ pseudo-Voigt (Thompson-Cox-Hastings) with Finger-Cox-Jephcoat "
            "axial divergence; Caglioti Gaussian U,V,W = "
            f"{prof.u.value:.6g},{prof.v.value:.6g},{prof.w.value:.6g} deg^2(2theta), "
            f"Lorentzian X,Y = {prof.x.value:.6g},{prof.y.value:.6g} deg; "
            f"FCJ S/L,H/L = {instrument.geometry.axial_sl.value:.4g},"
            f"{instrument.geometry.axial_hl.value:.4g}")


def _background_description(instrument: Instrument) -> str:
    bkg = instrument.background
    if isinstance(bkg, BackgroundChebyshev):
        return f"shifted-Chebyshev polynomial, {len(bkg.coefficients)} terms"
    if isinstance(bkg, BackgroundFixedPlusChebyshev):
        return (f"fixed estimated curve + shifted-Chebyshev, "
                f"{len(bkg.chebyshev.coefficients)} terms")
    if isinstance(bkg, BackgroundPSpline):
        return (f"penalized cubic P-spline, {len(bkg.breakpoints)} knots, "
                f"lambda_smooth={bkg.lambda_smooth:.4g}")
    return type(bkg).__name__


def _write_refinement_metadata(block, result: RefinementResult,
                               instrument: Instrument) -> None:
    st = result.statistics
    lam = instrument.source.primary_wavelength
    block.set_pair("_diffrn_radiation_wavelength", _g(lam))
    # R-factors (Toby 2006); pdCIF profile-fit tags so a powder reader picks
    # them up, and the plain _refine_ls tags for the rest.
    block.set_pair("_pd_proc_ls_prof_wR_factor", _g(st.rwp))
    block.set_pair("_pd_proc_ls_prof_R_factor", _g(st.rp))
    block.set_pair("_pd_proc_ls_prof_wR_expected", _g(st.rexp))
    block.set_pair("_refine_ls_goodness_of_fit_all", _g(st.gof))
    block.set_pair("_refine_ls_number_parameters", str(st.n_free_parameters))
    block.set_pair("_pd_proc_number_of_points", str(st.n_points))
    # McCusker et al. (1999) §10: "In any publication, the method used to
    # calculate the e.s.d.'s should be stated."  The inflation factor alone
    # does not state it — a reader cannot tell what it multiplied — so the base
    # estimator is named first and the factor second, in that order.
    esd_method = ("esds are the square roots of the diagonal of "
                  "chi^2_red * (J^T J)^-1, J the Jacobian of the weighted "
                  "residual at convergence")
    if st.esd_inflation is not None:
        esd_method += (", then multiplied by the Berar-Lelann "
                       f"serial-correlation factor {st.esd_inflation:.3g} "
                       "(Berar & Lelann, 1991, J. Appl. Cryst. 24, 1)")
    block.set_pair("_pd_proc_ls_special_details", gemmi.cif.quote(esd_method))
    block.set_pair("_pd_proc_ls_profile_function",
                   gemmi.cif.quote(_profile_description(instrument)))
    block.set_pair("_pd_proc_ls_background_function",
                   gemmi.cif.quote(_background_description(instrument)))


def _write_phase_agreement(block, row: PhaseAgreement | None) -> None:
    """R_Bragg and R_F under their dictionary tags, on one phase's block.

    Tag names checked against the COMCIFS core dictionary rather than
    remembered.  ``_refine_ls_R_I_factor`` is the one whose own definition
    names it — "most often calculated in Rietveld refinements of powder data,
    where it is referred to as R~B~ or R~Bragg~"; ``_refine_ls_R_factor_all``
    is "the conventional R factor", sum|F(meas) − F(calc)| / sum|F(meas)|,
    which is McCusker eq (13) exactly.  ``_all`` rather than ``_gt`` because
    every partitionable reflection is summed: there is no intensity threshold
    (no ``_reflns_threshold_expression`` to point at).

    Nothing is written outside Rietveld mode, where the row is absent for
    cause — an omitted tag says "not measured", a zero would be a claim.
    """
    if row is None:
        return
    if row.r_bragg is not None:
        block.set_pair("_refine_ls_R_I_factor", _g(row.r_bragg))
    if row.r_f is not None:
        block.set_pair("_refine_ls_R_factor_all", _g(row.r_f))
    if row.n_reflections:
        block.set_pair("_refine_ls_number_reflns", str(row.n_reflections))


def _write_pattern_loop(block, result: RefinementResult) -> None:
    """The observed/calculated pattern as a pdCIF loop ``read_pdcif`` reads."""
    tt = result.two_theta
    if not tt:
        return
    n = len(tt)
    yb = result.y_background or [0.0] * n
    sig = result.sigma or [0.0] * n
    loop = block.init_loop("", [
        "_pd_proc_2theta_corrected",
        "_pd_proc_intensity_total",
        "_pd_proc_intensity_total_su",
        "_pd_calc_intensity_total",
        "_pd_proc_intensity_bkg_calc",
    ])
    for i in range(n):
        loop.add_row([
            _g(tt[i]), _g(result.y_obs[i]), _g(sig[i]),
            _g(result.y_calc[i]), _g(yb[i]),
        ])


def refinement_cif_doc(result: RefinementResult, structure: Structure,
                       instrument: Instrument) -> gemmi.cif.Document:
    """Build the refinement CIF as a gemmi document (see :func:`write_refinement_cif`)."""
    import re

    doc = gemmi.cif.Document()
    agreement = {row.name: row for row in result.phase_agreement}
    for ip, phase in enumerate(structure.phases):
        block = doc.add_new_block(re.sub(r"\W+", "_", phase.name) or f"phase_{ip}")
        write_structure_block(block, phase)
        # Structure-sensitive R factors, on the phase's *own* block: both tags
        # are core-dictionary `_refine_ls` items, whose scope is the structure
        # in the block, not the pattern.  So a multi-phase export gives each
        # phase its own pair, which is how they are read.
        _write_phase_agreement(block, agreement.get(phase.name))
        if ip == 0:
            # refinement scalars + the pattern loop live on the first block, so
            # a single-phase export is one self-contained block that both
            # read_pdcif (pattern) and structure_from_cif (structure) re-read
            _write_refinement_metadata(block, result, instrument)
            _write_pattern_loop(block, result)
    return doc


def write_refinement_cif(result: RefinementResult, structure: Structure,
                         instrument: Instrument, path: str | Path) -> None:
    """Write a refinement CIF: structure (values + esds), R-factors, wavelength,
    profile/background description, and the observed/calculated pattern loop.

    ``structure`` must carry the refined values and their ``stderr`` (a fit
    leaves them on ``Refinement.fitted_structure``).  The pattern loop uses the
    pdCIF tags :func:`rietx.read_pdcif` reads and the structure block the tags
    :func:`rietx.Structure.from_cif` reads, so the file round-trips through the
    package's own readers.
    """
    refinement_cif_doc(result, structure, instrument).write_file(str(path))
