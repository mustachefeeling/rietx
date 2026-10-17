"""The fits behind `docs/docs/guides/branch.md`: two strategies from one node, compared.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

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
limits = (15, 130)

ref.run_stage(data, rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
              two_theta_limits=limits)
cell = ref.run_stage(data, rx.Stage("cell", ["instrument.zero_shift", "phases.*.cell.*"]),
                     two_theta_limits=limits)
ref.history.tag(cell.node_id, "cell")

# Strategy A: free the five width terms together.
together = ref.run_stage(data, rx.Stage("profile", ["instrument.profile.*"]),
                         two_theta_limits=limits)

# Strategy B, on a branch from the tagged node: free w first, then all five.
alt = ref.branch("cell")
alt.run_stage(data, rx.Stage("profile_w", ["instrument.profile.w"]), two_theta_limits=limits)
w_first = alt.run_stage(data, rx.Stage("profile", ["instrument.profile.*"]),
                        two_theta_limits=limits)
# guide: end

# guide: compare start
tree = ref.history
tree.tag(together.node_id, "together")
tree.tag(w_first.node_id, "w_first")

for row in tree.compare(["together", "w_first"]):
    print(f"{row['id']}  {row['action']:<14} free {row['n_free']}  Rwp {row['rwp']:.4f}")
print("best:", tree.best("rwp").id)
# guide: compare end

# guide: diff start
for path, (a, b) in tree.diff("together", "w_first").items():
    if path.startswith("instrument.profile."):
        print(f"{path:<22} {a:.5f}  {b:.5f}")
# guide: diff end

# guide: rollback start
ref.checkout("w_first")
ref.run_stage(data, rx.Stage("biso", ["phases.*.atoms.*.biso"]), two_theta_limits=limits)
print(tree.summary())
# guide: rollback end

# guide: replay start
for name in ("together", "w_first"):
    replayed = rx.replay(tree, name, data)
    print(f"{name:<9} recorded {tree[name].rwp:.4f}  replayed {replayed.statistics.rwp:.4f}")
# guide: replay end

# The page quotes both branch ends, the winner, four widths, the tree and the replay.
assert f"{tree['together'].rwp:.4f}" == "0.1031"
assert f"{tree['w_first'].rwp:.4f}" == "0.0988"
assert tree.best("rwp").id == "n0006"  # the biso stage on top of w_first
assert tree.head == "n0006" and tree["n0006"].parent == w_first.node_id
assert {n.id for n in tree.leaves()} == {together.node_id, "n0006"}
assert tree.common_ancestor("together", "w_first") == cell.node_id
assert f"{replayed.statistics.rwp:.4f}" == "0.0992"
# A stage's result is computed as a replay is, and strategy A's gap fires the code.
assert f"{together.statistics.rwp:.4f}" == "0.1022"
assert "FROZEN_COMPILE_STALE" in {d.code for d in together.diagnostics}
assert "FROZEN_COMPILE_STALE" not in {d.code for d in w_first.diagnostics}
# `ref` and `alt` hold their own positions; the shared head follows `ref`.
assert alt._head_id == w_first.node_id
