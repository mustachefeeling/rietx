"""Build the landing page's animation payload from the contributor's bundle.

Reads `curves.npz` + `metadata.csv` from an animation bundle directory and
writes `demo.json`: the observed and calculated curves of every frame (Int16,
base64), the refined weight fractions, the temperature/atmosphere programme.
No filename, scan index or specimen code from the bundle reaches the output;
`check_no_leak` fails the build if one does.

Time: `t` is the file's acquisition clock in seconds. `tm` is the plotted
clock in minutes, where each pause longer than twice the median scan interval
counts as one ordinary interval; `pauses` lists what was cut.
"""
import base64
import csv
import json
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from build import leaks  # noqa: E402  (one leak list for payload, transcript and page)

# The reacting phases are the animation's subject and are named here.  The support phases
# are not, and their names are not in this file either: naming them would pin the
# contributor's unpublished formulation, which is the same thing the filename and
# specimen-code fences keep out.  So the support columns are read from the bundle's own
# `metadata.csv` header — every `wtpct_` column that is not one of the three below, in
# header order — and ship as "support n".  Deliberately not a `build.LEAK` token: a denylist
# publishes what it denies, and a name written down to be refused is a name in the
# repository.  Not knowing it is the stronger fence (WP-1331).
REACTING = [  # column suffix, display name, formula (HTML)
    ("Cu",   "Cu",   "Cu"),
    ("Cu2O", "Cu₂O", "Cu<sub>2</sub>O"),
    ("CuO",  "CuO",  "CuO"),
]
WT = "wtpct_"


def phase_columns(header: list[str]) -> list[tuple[str, str, str, bool]]:
    """`(column suffix, name, html, support)` per phase, reacting first then the supports."""
    suffixes = [c[len(WT):] for c in header if c.startswith(WT)]
    named = [r[0] for r in REACTING]
    missing = [n for n in named if n not in suffixes]
    assert not missing, f"metadata.csv has no {WT}{missing[0]} column"
    out = [(c, n, h, False) for c, n, h in REACTING]
    for i, c in enumerate(s for s in suffixes if s not in named):
        out.append((c, f"support {i + 1}", f"support {i + 1}", True))
    return out
# metadata token -> (display text, colour key); the contributor's programme
ATM = {"1N2atm": ("N₂", "n2"), "2H2mixatm": ("0.2 % H₂ in N₂", "h2"), "3airatm": ("air", "air")}

#: The redaction, and why it keeps every k-th channel instead of averaging k of them
#: (WP-1331).  Averaging is the obvious reduction and it is the wrong one: it divides
#: the counting noise by sqrt(k), so the observed cloud tightens onto the calculated
#: curve and the difference curve flattens, and the panel then shows a better fit than
#: the Rwp printed beside it.  Measured at k=2 and k=3 by rendering both: the scatter
#: visibly collapses while the header still reads 13.3 %.  Decimation keeps every point
#: it keeps a real measured channel, noise and all, so the picture stays honest about
#: what the number means; what it costs is peak *shape*, the calculated line growing
#: spikier as the apexes fall between retained channels.
DECIMATE = "every k-th channel, never a mean of k"


def decimate(x: np.ndarray, *ys: np.ndarray, k: int):
    """Keep every `k`-th channel of `x` and of each row of each `y`. See DECIMATE.

    This is what lets the payload into the repository at all: a full-resolution copy
    of a contributor's unpublished in-situ series is their measurement, while one the
    package's own guideline calls unrefinable is a figure of it.  The page draws about
    520 CSS pixels of 2-theta, so the panels never needed the acquisition's own step.
    What the coarser step costs is stated in the payload as the package would state it,
    `steps_per_fwhm` against rietx's 5-to-10 (`optimize.statistics`,
    `PATTERN_UNDERSAMPLED`).
    """
    if k == 1:
        return (x, *ys)
    return (x[::k], *(y[:, ::k] for y in ys))


def steps_per_fwhm(x: np.ndarray, calc: np.ndarray) -> float:
    """Median reflection FWHM in steps, read off the *calculated* curve.

    The observed curve's counting noise is picked up as peaks by any finder and
    drags the median to about one channel; the model curve has none, and its widths
    are what a step actually has to resolve.
    """
    from scipy.signal import find_peaks, peak_widths
    meds = []
    for i in np.linspace(0, calc.shape[0] - 1, 5).astype(int):
        y = calc[i].astype(float)
        pk, _ = find_peaks(y, prominence=(y.max() - np.median(y)) * 0.05)
        if len(pk):
            meds.append(float(np.median(peak_widths(y, pk, rel_height=0.5)[0])))
    return round(float(np.median(meds)), 2) if meds else float("nan")


def build(bundle: Path, k: int = 1) -> dict:
    z = np.load(bundle / "curves.npz")
    x = z["two_theta"].astype(np.float64)
    obs = z["y_obs"]
    calc = z["y_calc"]
    assert obs.shape == calc.shape and obs.shape[1] == x.shape[0]
    assert np.all(obs == np.round(obs)), "observed counts are not integral"
    assert obs.max() < 32767 and calc.max() * 10 < 32767
    fwhm_native = steps_per_fwhm(x, calc)
    x, obs, calc = decimate(x, obs, calc, k=k)
    with open(bundle / "metadata.csv", newline="") as fh:
        reader = csv.DictReader(fh)
        cols = phase_columns(list(reader.fieldnames or []))
        rows = list(reader)
    assert len(rows) == obs.shape[0]
    assert [int(r["series_index"]) for r in rows] == list(range(len(rows)))
    # the plotted clock: pauses collapse to one ordinary interval
    t = [int(r["acquisition_seconds_since_run_start"]) for r in rows]
    dts = [b - a for a, b in zip(t, t[1:])]
    med = sorted(dts)[len(dts) // 2]
    pauses = [OrderedDict(after=i, seconds=dt) for i, dt in enumerate(dts) if dt > 2 * med]
    tm, acc = [0], 0
    for dt in dts:
        acc += med if dt > 2 * med else dt
        tm.append(acc)
    frames = []
    for i, r in enumerate(rows):
        wt = [float(r[WT + c]) for c, *_ in cols]
        frames.append(OrderedDict(
            T=int(r["temperature_c"]), atm=ATM[r["atmosphere"]][0],
            t=t[i], tm=round(tm[i] / 60, 2),
            status=r["status"], rwp=round(float(r["rwp_rietx_pct"]), 2),
            wt=[round(v, 2) for v in wt]))
    # programme segments: contiguous runs of (T, atm)
    segments, prev = [], None
    for i, (f, r) in enumerate(zip(frames, rows)):
        key = (f["T"], f["atm"])
        if key != prev:
            segments.append(OrderedDict(start=i, T=f["T"], atm=f["atm"],
                                        key=ATM[r["atmosphere"]][1]))
            prev = key
    def b64(a: np.ndarray) -> str:
        return base64.b64encode(np.ascontiguousarray(a, dtype="<i2").tobytes()).decode("ascii")
    return OrderedDict(
        title="CuO reduction and reoxidation, in situ",
        credit="Contributed by Michael W. Gaultois. Work performed with Prof. Clare Grey at the Department of Chemistry, University of Cambridge.",
        n=len(frames), npts=int(x.shape[0]),
        # what the redaction cost, in the package's own terms
        decimation=k, steps_per_fwhm=round(fwhm_native / k, 2),
        two_theta=[round(float(v), 4) for v in x],
        obs_b64=b64(np.round(obs)), calc_x10_b64=b64(np.round(calc * 10)),
        phases=[OrderedDict(name=n, html=h, support=sup) for _, n, h, sup in cols],
        frames=frames, segments=segments, pauses=pauses,
        rwp_median=round(float(np.median([f["rwp"] for f in frames])), 2),
        n_converged=sum(f["status"] == "converged" for f in frames),
        duration_s=frames[-1]["t"], duration_min=frames[-1]["tm"], scan_interval_s=med,
    )

# The payload also keeps the reference code's name and the raw gas tokens out; the transcript
# may name the reference code (the brief does) but never its numbers.
DEMO_TOKENS = (".xy", "xrdml", "topas", "1N2atm", "2H2mixatm", "3airatm")
TRANSCRIPT_TOKENS = ("1N2atm", "2H2mixatm", "3airatm")

def check_no_leak(text: str, bundle: Path, tokens: tuple[str, ...] = DEMO_TOKENS) -> None:
    """Refuse `text` if any pattern filename, scan index or leak token from `bundle` is in it.

    Case-insensitive throughout, for `build.leaks`' reason: the transcript is prose
    cut by hand, and a filename's case is not the case a sentence writes it in.
    """
    with open(bundle / "metadata.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    lowered = text.lower()
    bad = set()
    for r in rows:
        stem = r["filename"].rsplit(".", 1)[0]
        for token in (stem, r["filename"], f"_I{r['scan_index']}_"):
            if token.lower() in lowered:
                bad.add(token)
    bad.update(leaks(text))
    bad.update(t for t in tokens if t.lower() in lowered)
    if bad:
        raise SystemExit(f"leak: {sorted(bad)[:5]}")

if __name__ == "__main__":
    bundle = Path(sys.argv[1])
    out = Path(sys.argv[2])
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    payload = build(bundle, k=k)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    check_no_leak(text, bundle)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({len(text)/1e6:.2f} MB): {payload['n']} frames × {payload['npts']} points, "
          f"{payload['n_converged']} converged, Rwp median {payload['rwp_median']} %, "
          f"{payload['duration_s']/3600:.1f} h on the clock, {payload['duration_min']:.0f} min plotted, "
          f"scan interval {payload['scan_interval_s']} s")
    print("segments:", [(s['start'], s['T'], s['atm']) for s in payload['segments']])
    print("pauses:", [(p['after'], p['seconds']) for p in payload['pauses']])
