# %% [markdown]
# # Sequential fits
#
# *Written by Claude Code, Anthropic's coding agent, for the rietx project.*
#
# An in-situ experiment measures one specimen many times while something changes: temperature, time, pressure, gas.
# rietx fits such a series pattern by pattern, starting each fit from the answer before it.
# That warm start makes each fit fast, but it also means a mistake can travel down the chain.
# We fit a synthetic heating ramp whose answer we know, then break it twice to see what the series reports.
#
# **You need** rietx 1.7 or later, which the next cell installs.
# Notebook 02 introduces plans and a single refinement.
#
# **Runtime** is under a minute on a laptop.

# %%
# %pip install rietx

# %% [markdown]
# ## A synthetic heating ramp
#
# The specimen is LaB₆ on a synchrotron capillary instrument.
# Its cell expands by 0.05 % per 100 K from 300 K to 900 K.
# We write the structure as a short CIF and make each pattern from the true model with Poisson noise.

# %%
import csv
import re
import tempfile
from pathlib import Path

import numpy as np

import rietx as rx

work = Path(tempfile.mkdtemp())
cif = work / "LaB6.cif"
cif.write_text(
    "data_LaB6\n_space_group_name_H-M_alt 'P m -3 m'\n"
    + "".join(f"_cell_length_{k} 4.1566\n" for k in "abc")
    + "".join(f"_cell_angle_{k} 90\n" for k in ("alpha", "beta", "gamma"))
    + "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
      "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n"
      "La1 La 0 0 0 0.4\nB1 B 0.1996 0.5 0.5 0.4\n",
    encoding="utf-8")
lab6 = rx.Structure.from_cif(cif)

TEMPERATURES = [300, 400, 500, 600, 700, 800, 900]
A0, EXPANSION = 4.1566, 5e-4               # Å at 300 K, and the fraction per step
TRUE_A = [A0 * (1 + EXPANSION * k) for k in range(len(TEMPERATURES))]

true_instrument = rx.Instrument.debye_scherrer(wavelength=0.4139)
true_instrument.zero_shift.value = 0.008
true_instrument.profile.w.value = 2.5e-4
true_instrument.background = rx.BackgroundChebyshev.with_terms(3)
for coefficient, value in zip(true_instrument.background.coefficients, (40.0, -6.0, 1.5)):
    coefficient.value = value
two_theta = np.arange(3.0, 24.0, 0.005)


def simulate(a, seed):
    """One pattern of the true specimen at cell edge a."""
    structure = lab6.model_copy(deep=True)
    for edge in "abc":
        getattr(structure.phases[0].cell, edge).value = a
    structure.phases[0].scale.value = 5e-4
    y = rx.Refinement(structure, true_instrument).predict(two_theta)
    counts = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=two_theta, intensity=counts)


patterns = [simulate(a, seed=11 + k) for k, a in enumerate(TRUE_A)]

# %% [markdown]
# The starting model is what you would have before the first fit: the cell 0.1 % off, no zero shift, and peaks 50 % too wide.

# %%
def starting_model():
    structure = lab6.model_copy(deep=True)
    for edge in "abc":
        getattr(structure.phases[0].cell, edge).value = A0 * 1.001
    instrument = rx.Instrument.debye_scherrer(wavelength=0.4139)
    instrument.profile.w.value = 2.5e-4 * 1.5
    instrument.background = rx.BackgroundChebyshev.with_terms(3)
    return structure, instrument


LABELS = [f"{t} K" for t in TEMPERATURES]

# %% [markdown]
# ## A series is a list of patterns
#
# `refine_sequential` takes the series as an ordinary Python list of `PatternData`, one per measurement, in the order to fit them.
# `x` is a list of the same length giving each pattern's place along the series (temperature here), and `labels` names each one.
# Nothing else ties them together, so the order of the list is the order of the chain.

# %%
print(type(patterns).__name__, len(patterns), type(patterns[0]).__name__)
print(patterns[0])

# %% [markdown]
# ## Loading a real series from files
#
# A real series arrives as a folder of files, and the work is putting them in the right order with the right temperature.
# Here we write our synthetic patterns out as an instrument might, numbered by scan, with the temperatures in a separate log.

# %%
folder = work / "ramp"
folder.mkdir()
for scan, (pattern, temperature) in enumerate(zip(patterns, TEMPERATURES), start=8):
    rows = "".join(f"{t:.4f} {y:.0f}\n" for t, y in zip(pattern.two_theta, pattern.intensity))
    (folder / f"scan{scan}.xy").write_text(rows, encoding="utf-8")
log = "scan,temperature_K\n" + "".join(
    f"{scan},{t}\n" for scan, t in enumerate(TEMPERATURES, start=8))
(folder / "temperatures.csv").write_text(log, encoding="utf-8")

print([p.name for p in sorted(folder.glob("*.xy"))])

# %% [markdown]
# Sorting the file names gives the wrong order: `scan10` sorts before `scan8`, because names compare as text, character by character.
# Sort by the number in the name instead, and take each temperature from the log rather than assuming the order.

# %%
def scan_number(path):
    return int(re.search(r"\d+", path.stem).group())


files = sorted(folder.glob("*.xy"), key=scan_number)
with open(folder / "temperatures.csv", encoding="utf-8", newline="") as handle:
    temperature_of = {int(row["scan"]): float(row["temperature_K"]) for row in csv.DictReader(handle)}

loaded = [rx.read_pattern(path) for path in files]
loaded_x = [temperature_of[scan_number(path)] for path in files]
print([path.name for path in files])
print(loaded_x)

# %% [markdown]
# Other naming conventions need only a different key.
# When the temperature is in the file name itself, read it with a regular expression and sort on it.

# %%
names = ["LaB6_1000K.xye", "LaB6_300K.xye", "LaB6_650.5K.xye"]


def temperature_in_name(name):
    return float(re.search(r"([\d.]+)K", name).group(1))


print(sorted(names, key=temperature_in_name))

# %% [markdown]
# A timestamp in the name sorts correctly as text only when it is written largest unit first, as in `2026-10-07T14-05-00`.
# Whatever the convention, print the sorted names and their `x` values once, as above, before fitting.
#
# ## Fit the series
#
# `refine_sequential` fits the patterns in order, starting each fit from the parameters the previous one finished with.
# The `carry` argument says which parameters pass along the chain.
# It is a list of parameter-path globs, as in a plan's stages.
# A parameter matching one starts each fit from the previous fit's value, and any other starts from the starting model.
# `["*"]` carries everything, and it is the default, written out here.
# Narrow it only when a parameter must provably not be chained.
# For example, `carry=["phases.*", "instrument.zero_shift"]` would restart the background and peak widths at every pattern.

# %%
series = rx.refine_sequential(loaded, *starting_model(), carry=["*"], plan="mccusker_default",
                              x=loaded_x, x_label="T (K)", labels=LABELS)
print(series)

# %% [markdown]
# Every pattern converged.
# The two diagnostics are `SEQUENTIAL_PERSISTENT_FINDING`: one finding repeated in every pattern, which is a property of the model and not of any single fit.
# Here they are the step size and a capillary correction this model does not use.
#
# ## The trajectory
#
# A series answers a question about how a parameter changes.
# `series.trajectory` returns one parameter across the series, with esds.

# %%
a = series.trajectory("phases.0.cell.a")
for label, value, esd, true in zip(a.labels, a.value, a.stderr, TRUE_A):
    print(f"{label:6} a = {value:.6f} +/- {esd:.6f} Å   true {true:.6f}   off by {(value - true) / esd:+.1f} esd")
slope = np.polyfit(TEMPERATURES, a.value, 1)[0]
print(f"fitted expansion {slope / A0:.4e} per K, true {EXPANSION / 100:.4e}")

# %%
series.plot("phases.0.cell.a")

# %% [markdown]
# ## Is the answer path-dependent?
#
# A warm start means each answer depends on the one before it.
# If a fit lands in a slightly wrong place, the next fit starts there.
# `direction="both"` runs the chain forward and backward and compares the two.
# A parameter the two directions disagree on is flagged `SEQUENTIAL_PATH_DEPENDENT`.
# That check is what separates a measured trend from an artefact of the order.

# %%
both = rx.refine_sequential(patterns, *starting_model(), plan="mccusker_default",
                            x=TEMPERATURES, x_label="T (K)", labels=LABELS, direction="both")
print([d.code for d in both.diagnostics])

# %% [markdown]
# No `SEQUENTIAL_PATH_DEPENDENT`: both directions agree, so the trend is not an artefact of fitting from cold to hot.
#
# ## A jump in the series
#
# Now give the 700 K pattern a cell 2 % larger than its neighbours, as a phase transition might.

# %%
jumped = list(patterns)
jumped[4] = simulate(TRUE_A[4] * 1.02, seed=15)
series_jump = rx.refine_sequential(jumped, *starting_model(), plan="mccusker_default",
                                   x=TEMPERATURES, x_label="T (K)", labels=LABELS)
for d in series_jump.diagnostics:
    if d.code == "SEQUENTIAL_DISCONTINUITY" and "cell.a" in d.message:
        print(f"[{d.level}] {d.code}: {d.message}")
print(series_jump.trajectory("phases.0.cell.a").value)

# %% [markdown]
# The 700 K fit found the larger cell.
# When a warm start fails, the series escalates: it retries in stages, then from the initial model, and keeps the best attempt.
# `SEQUENTIAL_DISCONTINUITY` marks the step.
# It cannot tell a real change from a failed fit, so check that pattern's own fit before reading the jump as physics.
#
# ## A frame the chain cannot fit
#
# Make the jump 5 %, beyond what any starting point here can reach.

# %%
broken = list(patterns)
broken[4] = simulate(TRUE_A[4] * 1.05, seed=15)
series_broken = rx.refine_sequential(broken, *starting_model(), plan="mccusker_default",
                                     x=TEMPERATURES, x_label="T (K)", labels=LABELS)
print(series_broken)

# %% [markdown]
# The 700 K pattern failed on every attempt, and `SEQUENTIAL_RWP_OUTLIER` names it.
# The 800 K pattern started from that failure, so its warm start failed too.
# `SEQUENTIAL_RESEED` says it was refitted from the initial model, and its answer is good.
#
# A pattern whose fit diverges on every attempt goes further: it is quarantined (`SEQUENTIAL_UNRECOVERED`), seeds no successor and is left out of the series' statistics.
# Either way the rest of the trajectory survives, and the summary says which points to distrust.
#
# ## Checking an agent's work
#
# When an agent reports a trajectory, check these.
# The rules are in the rietx agent skill (`SKILL.md` §4b, the trajectory row, and `references/series.md`).
#
# - **Was the chain run both ways?** Without `direction="both"`, a trend can be an artefact of the fitting order.
# - **Every series diagnostic.** A discontinuity, an outlier or a reseed names the patterns to look at one by one.
# - **A finding in most patterns is one finding** about the model, and the thing to change is the model or the plan.
# - **Each point's esd, and the precision behind the trend.** A trajectory is only as good as its worst point.
