"""The TOPAS kit for the sample-absorption-factor cross-code check (issue #1867).

``inp_text(with_factor)`` is the input TOPAS v6 ran, LF line ends (the kit
writer below turns them into CRLF for ``tc.exe``).  ``python generate.py OUT``
writes both ``.inp`` and the synthetic pattern they read, ``si_synth.xye``:
the test pattern of ``tests/test_tof_absorption_factor.py`` (Si, A_B = 0.10
Å⁻¹, Biso = 0.46 Å², seed 20261127), x y e with e = √max(y, 1), rietx's own
Poisson weight.  Synthetic only; TOPAS is run as a black box.

The model is the rietx fixture bank in TOPAS keywords: ``TOF_x_axis_calibration``
with DIFC 12000 µs/Å and TZERO −5 µs held; the GSAS type-1 shape as a
pseudo-Voigt with ``pv_lor 0`` of FWHM 2.3548·√sig1·d inside the ``str`` and,
at the pattern level, a rise exponential of rate α1/d and a decay of rate
β0 + β1/d⁴ (``exp_conv_const``, negative = rise); the Lorentz factor d⁴ in
``scale_pks``, times, on the second input, the Rouse et al. (1970) cylinder
factor at µR = A_B·λ = A_B·2d·sin θ_bank with the coefficients
``rietx.model.absorption`` states (a1 + b1 sin²θ and a2 + b2 sin²θ evaluated
at 2θ = 90°).  Refined in both: the scale, a four-term Chebyshev background,
the cell edge and Biso; in the second, A_B from 0.01.
"""

from __future__ import annotations

import sys
from pathlib import Path

LN1000 = "6.907755279"
#: Rouse, Cooper, York & Chakera (1970), as rietx.model.absorption states them
A1, B1, A2, B2 = 1.7133, -0.0368, -0.0927, -0.3750
SIN2 = 0.5                       # sin²θ_bank at 2θ = 90°
TWO_SIN = "1.414213562"          # 2·sin θ_bank, so λ = 2·d·sin θ_bank
TAGS = {False: "01_Si_noAB", True: "02_Si_AB"}


def inp_text(with_factor: bool) -> str:
    tag = TAGS[with_factor]
    if with_factor:
        c1, c2 = A1 + B1 * SIN2, A2 + B2 * SIN2
        m = f"(ab * {TWO_SIN} * D_spacing)"
        # a product, not ^2: TOPAS v6 did not move a parameter inside x^2
        # from this start (measured 2026-11-27)
        scale = ("\tprm ab 0.01 min -1 max 1\n"
                 f"\tscale_pks = D_spacing^4 * Exp(-{c1:.6f} * {m} - ({c2:.6f}) * {m} * {m});\n")
    else:
        scale = "\tscale_pks = D_spacing^4;\n"
    return ("iters 100000\nchi2_convergence_criteria 0.0001\ndo_errors\n\n"
            "TOF_XYE(si_synth.xye, 3)\n\tneutron_data\n"
            f"\tOut_X_Yobs({tag}_yobs.txt)\n\tOut_X_Ycalc({tag}_ycalc.txt)\n"
            "\tx_calculation_step = Yobs_dx_at(Xo); convolution_step 4\n"
            "\tTOF_LAM(0.001)\n" + scale +
            "\tbkg @ 200 0 0 0\n\tstart_X 8000\n\tfinish_X 45000\n"
            "\tTOF_x_axis_calibration(!t0, -5, !t1, 12000, !t2, 0)\n"
            f"\texp_conv_const = -{LN1000} D_spacing / 0.45;\n"
            f"\texp_conv_const = {LN1000} / (0.055 + 0.003 / D_spacing^4);\n"
            "\tstr\n\t\tpeak_type pv\n\t\tpv_lor 0\n"
            "\t\tpv_fwhm = 2.354820045 Sqrt(300) D_spacing;\n"
            "\t\tscale @ 700000\n\t\tphase_name Si\n"
            "\t\ta lpa 5.4311946\n\t\tb lpa 5.4311946\n\t\tc lpa 5.4311946\n"
            "\t\tal 90\n\t\tbe 90\n\t\tga 90\n\t\tspace_group Fd-3m\n"
            "\t\tsite Si1 x 0 y 0 z 0 occ Si 1 beq bsi 1.0\n")


def main(out: Path) -> None:
    import numpy as np

    root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(root))
    import tests.test_tof_absorption_factor as T

    out.mkdir(parents=True, exist_ok=True)
    data = T._generated(T.silicon(T.BISO_GEN), T.ab_bank(T.AB_GEN), seed=T.SEED)
    x, y = np.asarray(data.tof), np.asarray(data.intensity)
    np.savetxt(out / "si_synth.xye", np.c_[x, y, np.sqrt(np.maximum(y, 1.0))],
               fmt="%.4f %.6f %.6f")
    for with_factor, tag in TAGS.items():
        (out / f"{tag}.inp").write_bytes(
            inp_text(with_factor).replace("\n", "\r\n").encode("latin-1"))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
