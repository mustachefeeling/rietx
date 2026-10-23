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
jumped[4] = simulate(TRUE_A[4] * 1.02, seed=15)  # the 700 K cell 2 % larger
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
    "cold", "warm", "warm", "warm", "warm_staged", "warm_staged", "warm"]
# a rejected attempt's Rwp is where a diverging fit stopped: 0.917 to 0.938 between starts
# that differ by 1e-14 (WP-2002, 2026-10-22), so the page quotes a bound
assert all(e.rwp_warm > 0.9 for e in series.entries[4:6])
assert [f"{r:.3f}" for r in series.rwp[4:6]] == ["0.039", "0.040"]
assert gap < 0.005
