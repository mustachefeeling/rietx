"""The fits behind `docs/docs/guides/path.md`: is a series trajectory the chain's or the data's?

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: seven synthetic LaB6 patterns from `_lab6_ramp.py` beside this script,
made from a known cell at each temperature.
"""

# guide: start

from _lab6_ramp import TEMPERATURES, TRUE_A, ramp, simulate, starting_model

import rietx as rx

patterns = ramp()
series = rx.refine_sequential(patterns, *starting_model(), plan="mccusker_default",
                              x=TEMPERATURES, x_label="T (K)", direction="both")

print([d.code for d in series.diagnostics])
forward = series.trajectory("phases.0.cell.a")
backward = series.backward.trajectory("phases.0.cell.a")
gap = max(abs(f - b) / e for f, b, e in zip(forward.value, backward.value, forward.stderr))
print(f"largest forward-backward gap: {gap:.2f} esd")
# guide: end

# guide: jump start
jumped = list(patterns)
jumped[4] = simulate(TRUE_A[4] * 1.015, seed=15)  # the 700 K cell 1.5 % larger
series = rx.refine_sequential(jumped, *starting_model(), plan="mccusker_default",
                              x=TEMPERATURES, x_label="T (K)", verify_discontinuities=True)

for d in series.diagnostics:
    if d.code == "SEQUENTIAL_DISCONTINUITY" and d.where == ["phases.0.cell.a"]:
        print(d.message)
for entry in series:
    print(f"{entry.label}  {entry.rung}")
# guide: jump end

steps = [d for d in series.diagnostics if d.code == "SEQUENTIAL_DISCONTINUITY"]
assert [d.where for d in steps] == [
    ["phases.0.cell.a"], ["phases.0.cell.b"], ["phases.0.cell.c"]]
assert all(round(d.value, 2) == 1.00 for d in steps)
assert [s.indices for s in series.discontinuities] == [(3, 4)] * 3
assert [e.rung for e in series] == [
    "cold", "warm", "warm", "warm", "warm_staged", "warm", "warm"]
# a 1.5 % jump, because 2 % and 3 % left which warm start broke to rounding: under start
# nudges of 1e-14 the 800 K one held in 3 of 8 starts at 2 %, and the 700 K one in 3 of
# 10 at 3 % on OpenBLAS, while 1.5 % broke the 700 K one at Rwp 0.946 in all 20 on both
# BLAS builds (WP-2002, 2026-10-23); the page still quotes a bound
assert series.entries[4].rwp_warm > 0.9 and series.entries[5].rwp_warm is None
# the rescued 700 K fit ends at 0.039494, 6e-6 from where a third decimal flips, so the
# page quotes two
assert all(abs(r - 0.040) < 0.001 for r in series.rwp[4:6]), series.rwp[4:6]
assert gap < 0.005
