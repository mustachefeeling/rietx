"""The checks behind `docs/docs/guides/check.md`: a pattern read before any fit.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite, shipped in `rietx.examples`.
"""

# guide: start

import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "FAP.XRA")
d = rx.diagnose(data, wavelength=1.5406)

print("signal cutoffs:", d.signal_cutoffs)
print("dead channels:", d.dead_channels, "| sigma measured:", d.coverage_plateau is not None)
print(f"steps per FWHM: {d.steps_per_fwhm:.1f} over {d.n_peaks_measured} peaks")
print("contamination:", d.contamination)
print(f"air-scatter gain: {d.air_scatter_gain:.2f}")
# guide: end

# guide: ticks start
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
ref = rx.Refinement(structure, rx.Instrument.bragg_brentano(radiation="CuKa"))
fig = data.plot(model=ref, two_theta_range=(25, 40))  # path="ticks.png" writes it
# guide: ticks end

# guide: background start
choice = rx.auto_background(data, diagnostics=d)
background = choice.background
print(type(background).__name__, "with", len(background.coefficients), "coefficients")
print(f"knot step {choice.knot_step_deg:g}°: hump score "
      f"{choice.amorphous_hump_score:.3f}, trigger {choice.hump_trigger:g}")
print(f"air-scatter term {choice.air_scatter}: gain "
      f"{choice.air_scatter_gain:.2f}, trigger {choice.air_scatter_trigger:g}")
# guide: background end

assert d.signal_cutoffs == [] and d.dead_channels == [] and d.contamination == []
assert d.coverage_plateau is None  # FAP.XRA carries no esd column
assert round(d.steps_per_fwhm, 1) == 4.6 and d.n_peaks_measured == 76
assert round(d.air_scatter_gain, 2) == 0.75
assert type(background).__name__ == "BackgroundPSpline"
assert len(background.coefficients) == 41
assert background.air_scatter is not None
