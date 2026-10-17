"""The fit behind `docs/docs/guides/hold.md`: a held cell through a plan that frees it.

The page shows the lines between the two `guide:` markers and quotes what they
print; every quoted number is asserted below the second marker, so a change
that moves one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite, shipped in `rietx.examples`.
"""

# guide: start

import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "FAP.XRA")
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.background = rx.BackgroundChebyshev.with_terms(6)

ref = rx.Refinement(structure, instrument)
held = ref.hold("phases.0.cell.*")
result = ref.fit(data, plan="lab_bragg_brentano", two_theta_limits=(15, 130))

print(ref.fitted_structure.phases[0].cell.a.value)
for stage in result.stages:
    if stage.blocked_by_hold:
        print(stage.name, stage.blocked_by_hold)
for d in result.diagnostics:
    if d.code == "HOLD_BLOCKED_PLAN":
        print(d.message)
# guide: end

assert result.status == "converged"
assert held == ["phases.0.cell.a", "phases.0.cell.alpha", "phases.0.cell.b",
                "phases.0.cell.beta", "phases.0.cell.c", "phases.0.cell.gamma"]
assert ref.fitted_structure.phases[0].cell.a.value == 9.3717
assert ref.fitted_structure.phases[0].cell.c.value == 6.8859
assert [(s.name, s.blocked_by_hold) for s in result.stages if s.blocked_by_hold] == [
    ("cell", ["phases.0.cell.a", "phases.0.cell.c"])]

# The same fit without the hold moves the cell: the plan's `cell` stage frees it.
free = rx.Refinement(rx.Structure.from_cif(examples_dir() / "fluorapatite.cif"), instrument)
free.fit(data, plan="lab_bragg_brentano", two_theta_limits=(15, 130))
a_free = free.fitted_structure.phases[0].cell.a.value
ppm = round(1e6 * (9.3717 - a_free) / 9.3717)
print(f"without the hold: a = {a_free:.4f}, {ppm} ppm from the held value")
# 318 ppm on the compiled path and 332 on the numpy one (RIETX_COMPILED=0),
# measured 2026-10-17: the page says "more than 300".
assert ppm > 300
