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
import base64, csv, json, sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import leaks  # noqa: E402  (one leak list for payload, transcript and page)
import numpy as np

PHASES = [  # column suffix, display name, formula (HTML), determined-by-data, support
    ("Cu",                 "Cu",        "Cu",                              True,  False),
    ("Cu2O",               "Cu₂O",      "Cu<sub>2</sub>O",                 True,  False),
    ("CuO",                "CuO",       "CuO",                             True,  False),
    ("support 1",           "support 1",  "support 1", True, True),
    ("support 2",            "support 2",   "support 2",   False, True),
    ("support 3",  "support 3",   "support 3", False, True),
]
# metadata token -> (display text, colour key); the contributor's programme
ATM = {"1N2atm": ("N₂", "n2"), "2H2mixatm": ("0.2 % H₂ in N₂", "h2"), "3airatm": ("air", "air")}

def build(bundle: Path) -> dict:
    z = np.load(bundle / "curves.npz")
    x = z["two_theta"].astype(np.float64)
    obs = z["y_obs"]; calc = z["y_calc"]
    assert obs.shape == calc.shape and obs.shape[1] == x.shape[0]
    assert np.all(obs == np.round(obs)), "observed counts are not integral"
    assert obs.max() < 32767 and calc.max() * 10 < 32767
    rows = list(csv.DictReader(open(bundle / "metadata.csv")))
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
        wt = [float(r[f"wtpct_{k}"]) for k, *_ in PHASES]
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
            segments.append(OrderedDict(start=i, T=f["T"], atm=f["atm"], key=ATM[r["atmosphere"]][1])); prev = key
    def b64(a: np.ndarray) -> str:
        return base64.b64encode(np.ascontiguousarray(a, dtype="<i2").tobytes()).decode("ascii")
    return OrderedDict(
        title="CuO reduction and reoxidation, in situ",
        credit="Data and refinement contributed by @mustachefeeling",
        n=len(frames), npts=int(x.shape[0]),
        two_theta=[round(float(v), 4) for v in x],
        obs_b64=b64(np.round(obs)), calc_x10_b64=b64(np.round(calc * 10)),
        phases=[OrderedDict(name=n, html=h, determined=d, support=s) for _, n, h, d, s in PHASES],
        frames=frames, segments=segments, pauses=pauses,
        rwp_median=round(float(np.median([f["rwp"] for f in frames])), 2),
        n_converged=sum(f["status"] == "converged" for f in frames),
        duration_s=frames[-1]["t"], duration_min=frames[-1]["tm"], scan_interval_s=med,
    )

# The payload also keeps the reference code's name and the raw gas tokens out; the transcript
# may name the reference code (the brief does) but never its numbers.
DEMO_TOKENS = (".xy", "xrdml", "topas", "TOPAS", "1N2atm", "2H2mixatm", "3airatm")
TRANSCRIPT_TOKENS = ("1N2atm", "2H2mixatm", "3airatm")

def check_no_leak(text: str, bundle: Path, tokens: tuple[str, ...] = DEMO_TOKENS) -> None:
    """Refuse `text` if any pattern filename, scan index or leak token from `bundle` is in it."""
    rows = list(csv.DictReader(open(bundle / "metadata.csv")))
    bad = set()
    for r in rows:
        stem = r["filename"].rsplit(".", 1)[0]
        for token in (stem, r["filename"], f"_I{r['scan_index']}_"):
            if token in text: bad.add(token)
    bad.update(leaks(text))
    bad.update(t for t in tokens if t in text)
    if bad:
        raise SystemExit(f"leak: {sorted(bad)[:5]}")

if __name__ == "__main__":
    bundle = Path(sys.argv[1]); out = Path(sys.argv[2])
    payload = build(bundle)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    check_no_leak(text, bundle)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({len(text)/1e6:.2f} MB): {payload['n']} frames × {payload['npts']} points, "
          f"{payload['n_converged']} converged, Rwp median {payload['rwp_median']} %, "
          f"{payload['duration_s']/3600:.1f} h on the clock, {payload['duration_min']:.0f} min plotted, "
          f"scan interval {payload['scan_interval_s']} s")
    print("segments:", [(s['start'], s['T'], s['atm']) for s in payload['segments']])
    print("pauses:", [(p['after'], p['seconds']) for p in payload['pauses']])
