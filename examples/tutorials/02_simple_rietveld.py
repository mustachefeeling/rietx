# %% [markdown]
# # A simple Rietveld refinement
#
# We refine the fluorapatite structure against the pattern notebook 01 fitted with Le Bail.
# This time the peak intensities come from the atoms, so the fit can move them.
# Along the way we look at the plan's stages, the parameter table, two parameters the data cannot tell apart, and a constraint between three atoms.
#
# **You need** `pip install "rietx[viz]"`.
# Notebook 01 introduces the pattern and how to read a fit's summary.
#
# **The data** is `FAP.XRA` from the GSAS-II `LabData` tutorial, with a CIF transcribed from the same tutorial's experiment file.
# Both ship with rietx.
# Fluorapatite, Ca₅(PO₄)₃F, has seven atomic sites in space group P6₃/m.
#
# **Runtime** is under a minute on a laptop.
#
# ## A first refinement
#
# This is the example on the rietx home page.

# %%
import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "FAP.XRA")
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.geometry.axial_sl.value = 0.02  # axial divergence
instrument.geometry.axial_hl.value = 0.02
instrument.background = rx.BackgroundChebyshev.with_terms(6)

ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan="mccusker_structural", two_theta_limits=(15, 130))

print(f"{result.status}  Rwp={result.statistics.rwp:.4f}  "
      f"GoF={result.statistics.gof:.2f}")
for name in ("a", "c"):
    p = result.parameter(f"phases.0.cell.{name}")
    print(f"  {name} = {p.value:.5f} +/- {p.stderr:.5f} A")
for d in result.diagnostics:
    print(f"  [{d.level}] {d.code}: {d.message}")

# %% [markdown]
# Three warnings came back.
#
# - `SITE_SNAPPED_TO_SPECIAL_POSITION`: the CIF gives Ca1's x as 0.3333333333, which is 1/3 to ten digits. The reader placed it exactly on the special position.
# - `RESOLUTION_UNCONSTRAINED`: the peaks are mostly Lorentzian, so the Gaussian width terms U, V and W are poorly determined. Do not quote them.
# - `PATTERN_UNDERSAMPLED`: the step count notebook 01 measured.
#
# None of them invalidates the structure, but each one limits what you can quote.
#
# ## The plan and its stages
#
# A plan frees parameters in groups, in a fixed order, and runs each group to convergence before freeing the next.
# The order follows McCusker et al. (1999): background and scale, then zero shift, cell and peak widths, then atomic coordinates and displacement parameters.
# Freeing everything at once from a poor start tends to land in a wrong minimum.

# %%
print(rx.PLAN_INFO["mccusker_structural"].description)
for stage in result.stages:
    print(f"{stage.name:22} {stage.status:10} {len(stage.freed):3} freed")

# %% [markdown]
# A stage that frees nothing belongs to a correction this model does not declare, such as preferred orientation.
# It converges at once and changes nothing.
#
# ## The parameter table
#
# `ref.parameters()` lists every parameter the model has, whether it varies or not.
# Here are the rows for one oxygen site, O7, which sits on a general position.

# %%
for row in ref.parameters():
    if row.path.startswith("phases.0.atoms.6."):
        state = "varies" if row.vary else (row.held_because or "fixed")
        esd = f"{row.esd:.5f}" if row.esd is not None else "-"
        print(f"{row.path:28} {row.value:10.5f}  esd {esd:8}  {state}")

# %% [markdown]
# The atom's x, y and z are not refined directly.
# rietx refines one `dof` per direction the site symmetry allows.
# O7 is on a general position, so it has three.
# An atom on a mirror plane has two, and one on a three-fold axis has one.
# The coordinates follow from the `dof` values, so the symmetry always holds.
#
# ## A constraint between three atoms
#
# Fluorapatite has three oxygen sites in its phosphate group: O5, O6 and O7.
# Their displacement parameters (Biso, the mean-square vibration amplitude times 8π²) are expected to be similar.
# Check that against the data before constraining anything.

# %%
OXYGENS = ["phases.0.atoms.4.biso", "phases.0.atoms.5.biso", "phases.0.atoms.6.biso"]
for path in OXYGENS:
    p = result.parameter(path)
    print(f"{path:24} {p.value:.3f} +/- {p.stderr:.3f} Å²")

# %% [markdown]
# Each value lies within about one esd of the others.
# The data cannot tell them apart, so refining one shared value loses nothing and spends two fewer parameters.
# `tie_equal` makes the second and third follow the first.
# We refit with the same plan, so the tie is the only difference from the first fit.

# %%
ref.tie_equal(OXYGENS)
tied = ref.fit(data, plan="mccusker_structural", two_theta_limits=(15, 130))

print(f"free parameters: {result.statistics.n_free_parameters} before, "
      f"{tied.statistics.n_free_parameters} after")
p = tied.parameter(OXYGENS[0])
print(f"shared oxygen Biso: {p.value:.3f} +/- {p.stderr:.3f} Å²")
print(f"Rwp: {result.statistics.rwp:.4f} before, {tied.statistics.rwp:.4f} after")

# %% [markdown]
# The shared esd is smaller than any of the three separate ones.
# That is what the constraint bought.
# Rwp barely moved, and it could not have shown the gain: a constraint is judged by its premise and its esds.
#
# ## Two parameters the data cannot separate
#
# A flat-plate diffractometer has two corrections that shift every peak: the zero shift (constant in 2θ) and the specimen displacement (proportional to cos θ).
# The `lab_bragg_brentano` plan frees both.
# Run it from where the tied fit ended and see what happens.

# %%
both = ref.fit(data, plan="lab_bragg_brentano", two_theta_limits=(15, 130))
for path in ("instrument.zero_shift", "instrument.geometry.sample_displacement", "phases.0.cell.a"):
    p = both.parameter(path)
    print(f"{path:40} {p.value:9.5f} +/- {p.stderr:.5f}")
for d in both.diagnostics:
    if d.code == "HIGH_CORRELATION" and "instrument.zero_shift" in d.where:
        print(f"[{d.level}] {d.code}: {d.message.split(' — ')[0]}")

# %% [markdown]
# The zero shift and the displacement are correlated at ρ = 1.000.
# The fit could trade one against the other without changing the pattern, so neither value is a measurement.
# The cell's esd grew too, because the cell shifts peaks in a similar way.
#
# The cure is to hold one of the pair at a value known from outside this fit.
# GSAS's own refinement of this file held the zero shift at 0 and refined the displacement.
# We do the same.
# First go back to the tied fit: every fit is a node in the refinement's history, and `checkout` restores one, tie included.

# %%
ref.checkout(tied.node_id)
ref.set_values({"instrument.zero_shift": 0.0})
ref.hold(["instrument.zero_shift"])

held = ref.fit(data, plan="lab_bragg_brentano", two_theta_limits=(15, 130))
for path in ("instrument.geometry.sample_displacement", "phases.0.cell.a"):
    p = held.parameter(path)
    print(f"{path:40} {p.value:9.5f} +/- {p.stderr:.5f}")
for d in held.diagnostics:
    if d.code == "HOLD_BLOCKED_PLAN":
        print(f"[{d.level}] {d.code}: {d.message}")

# %% [markdown]
# The displacement now has a small esd, and so does the cell.
# `HOLD_BLOCKED_PLAN` reports that the plan tried to free the zero shift and the hold stopped it.
#
# Use `ref.hold` for this, not `vary=False` on the parameter.
# A plan sets which parameters vary at each stage, so it would free a parameter marked `vary=False`.
# A hold outranks the plan.
#
# `lab_bragg_brentano` refines the profile and the instrument, not the atoms.
# Refine the structure once more, with the zero shift held, the displacement as just measured, and the tie in place.

# %%
final = ref.fit(data, plan="mccusker_structural", two_theta_limits=(15, 130))
print(f"{final.status}  Rwp={final.statistics.rwp:.4f}")

# %% [markdown]
# ## Is the structure chemically sensible?
#
# A fit can match the pattern with atoms in impossible places.
# `result.geometry` lists the bonds the refined structure implies, with esds.
# A phosphate's P–O bonds are close to 1.54 Å.

# %%
for bond in final.geometry.bonds:
    if bond.atom_1 == "P3" and bond.atom_2.startswith("O"):
        print(f"{bond.atom_1}-{bond.atom_2}  {bond.distance:.3f} +/- {bond.stderr:.3f} Å")

# %% [markdown]
# The list has one row per bond, and O7 sits on both sides of the mirror plane, so it appears twice.
# All four bonds are within 0.04 Å of 1.54 Å.
# That is chemically sensible, but some differ from it by several esds.
# An esd counts only the noise in the data, and not errors in the model, so a real structure can sit further from a reference than its esd suggests.
#
# ## The history
#
# Every stage of every fit is a node you can return to.

# %%
print(ref.history.summary())

# %% [markdown]
# ## The verdict for a declared purpose
#
# What counts as finished depends on what the fit is for.
# `ref.summary` prints the rows that decide a given deliverable.
# Here the deliverable is the structure.

# %%
print(ref.summary(deliverable="structure"))

# %% [markdown]
# The summary repeats the stages and diagnostics, then adds what needs the whole model.
#
# - `layer0/1` reads the difference curve region by region and ranks the regions by their share of χ². When too little of the misfit sits in regions it can explain, it abstains from attributing a cause. An abstention is an answer: no single correction is indicated.
# - `unmatched obs peaks` counts observed peaks with no reflection under them. Find them before quoting a structure, because a weak second phase would explain them.
# - `next` names the parameter whose release the package predicts would help most, and the ΔBIC that release would have to pass.
# - `exchangeability` lists held parameters whose effect a free one could imitate. The agent skill's rule 14 settles each with two short fits, one per rival.
# - `protocol` is what you report alongside the numbers: the plan, what was held, and the observation count.
#
# ## The final fit

# %%
final.plot()

# %% [markdown]
# ## Checking an agent's work
#
# When an agent reports a structure refinement, check these in order.
# The numbers are the rules in the rietx agent skill (`SKILL.md` §4).
#
# - **Status and every diagnostic first** (rule 9). Ask which diagnostics limit what it quotes.
# - **Correlations near 1** (§3, rule 7). Two parameters at ρ ≈ 1 are one measurement. Ask which was held, and what value it was held at.
# - **Chemistry** (rule 12). Bond lengths and Biso values should be physically possible.
# - **Constraints** (§3, rule 8). A tie needs its premise checked in an unconstrained fit first.
# - **Rwp last** (rule 16), and only against a fit of the same channels.
