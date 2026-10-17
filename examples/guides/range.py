"""The fits behind `docs/docs/guides/range.md`: a fit range, an excluded region, and both in a project.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite, shipped in `rietx.examples`.
"""

# guide: start

import tempfile
from pathlib import Path

import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "FAP.XRA")
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.background = rx.BackgroundChebyshev.with_terms(6)
ref = rx.Refinement(structure, instrument)

data.excluded_regions = [(30.0, 31.0)]
result = ref.fit(data, plan="lab_bragg_brentano", two_theta_limits=(20, 120))

print(len(data.intensity), "channels in the file")
print(result.statistics.n_points, "channels fitted")
print(result.two_theta[0], "to", result.two_theta[-1])
# guide: end

# guide: replay start
data.excluded_regions = []
replayed = rx.replay(ref.history, ref.history.head, data)
print(replayed.statistics.n_points, "channels in the replay")
# guide: replay end

# guide: project start
with tempfile.TemporaryDirectory() as tmp:
    project = rx.Project.create(
        Path(tmp) / "fap.rex", pattern=examples_dir() / "FAP.XRA",
        structure=rx.Structure.from_cif(examples_dir() / "fluorapatite.cif"),
        instrument=instrument, plan="lab_bragg_brentano",
        two_theta_limits=(20, 120), excluded_regions=[(30.0, 31.0)])
    before = int(project.fitted_mask().sum())
    print(before, "channels the next run fits")

    project.doc.two_theta_limits = (15, 130)
    project.set_excluded_regions([])
    project.save()
    after = int(project.fitted_mask().sum())
    print(after, "channels after the change")
# guide: project end

assert len(data.intensity) == 5753
# 20-120° at 0.02° steps is 5001 channels, both ends included; 30-31° is 51 of them
assert result.statistics.n_points == len(result.two_theta) == 4950
assert (result.two_theta[0], result.two_theta[-1]) == (20.0, 120.0)
# the node recorded the range; the exclusion came from the pattern handed in
assert replayed.statistics.n_points == 5001
assert before == 4950  # the project agrees with the fit about what it fits
assert after == 5751  # 15-130° of a file ending at 130.04°
