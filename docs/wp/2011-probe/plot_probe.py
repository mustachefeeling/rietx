"""obs / calc / background for each mode, one panel per mode, plus a low-angle zoom."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from probe_lebail_vs_pawley import OUT  # noqa: E402
case = sys.argv[1]
zoom = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else None

fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
for ax, mode in zip(axes, ("lebail", "pawley")):
    d = np.load(OUT / f"{case}_{mode}.npz")
    ax.plot(d["tt"], d["y_obs"], ".", ms=1.5, color="0.2", label="observed")
    ax.plot(d["tt"], d["y_calc"], lw=0.7, color="tab:red", label="calculated")
    ax.plot(d["tt"], d["y_bkg"], lw=1.0, color="tab:blue", label="background")
    ax.plot(d["tt"], d["y_obs"] - d["y_calc"] - 0.15 * d["y_obs"].max(), lw=0.5,
            color="0.5", label="obs − calc (offset)")
    ax.axhline(0.0, lw=0.5, color="k")
    ax.set_title(f"{case}: {mode}   background mean {d['y_bkg'].mean():.1f}")
    ax.set_ylabel("counts")
    if zoom:
        ax.set_xlim(*zoom)
        inside = (d["tt"] >= zoom[0]) & (d["tt"] <= zoom[1])
        lo = min(d["y_bkg"][inside].min(), 0) - 20
        ax.set_ylim(lo, 4 * np.percentile(d["y_obs"][inside], 90))
axes[0].legend(loc="upper right", fontsize=8)
axes[1].set_xlabel("2θ (°)")
fig.tight_layout()
tag = f"_{zoom[0]:.0f}-{zoom[1]:.0f}" if zoom else ""
fig.savefig(OUT / f"{case}{tag}.png", dpi=110)
print(OUT / f"{case}{tag}.png")
