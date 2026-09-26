"""WP-1466 acceptance 3: the polyhedra in Chromium, Firefox and WebKit.

    .venv/bin/python docs/wp/1466-measure/engines.py frames [RUNS] [all|none]
    .venv/bin/python docs/wp/1466-measure/engines.py compare OUT

Run from the repository root with python playwright installed.  ``frames``
serves NAC, switches every centre species' polyhedra on (or, with ``none``,
the one switch off, for the baseline), and measures the
frame gaps over a trackball drag the way WP-1462's ``paired.mjs`` did: 60
moves, a gap per animation frame, and in Chromium the long animation frames.
``compare`` reads ``1462-spike/gate.py run`` pictures for the three engines
under OUT and prints each engine's difference from Chromium's.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

WATCH = """() => {
  window.__loaf = [];
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) window.__loaf.push(e.duration);
    }).observe({ type: "long-animation-frame" });
  } catch { /* not Chromium */ }
  window.__gaps = [];
  let last = performance.now();
  const tick = () => {
    const now = performance.now();
    if (!window.__gaps) return;
    window.__gaps.push(now - last);
    last = now;
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}"""


def frames(runs: int, polyhedra: str = "all") -> None:
    from playwright.sync_api import sync_playwright

    sys.path.insert(0, str(REPO / "docs/wp/1462-spike"))
    import gate

    tmp = Path(tempfile.mkdtemp(prefix="engines-"))
    url, httpd = gate._serve(tmp)
    try:
        with sync_playwright() as p:
            for engine in ("chromium", "firefox", "webkit"):
                for run in range(runs):
                    browser = getattr(p, engine).launch(**gate.CONFIGS[engine])
                    page = browser.new_page(viewport={"width": 1500, "height": 950},
                                            device_scale_factor=2)
                    page.goto(url)
                    page.get_by_role("button", name="Model", exact=True).click()
                    page.locator(".viewer canvas").wait_for()
                    gate._settle(page, 8)
                    row = page.locator(".viewer .legend").nth(1)
                    if polyhedra == "none":
                        row.get_by_role("button", name="polyhedra", exact=True).click()
                    while row.locator("button.off:not([disabled])").count():
                        row.locator("button.off:not([disabled])").first.click()
                        gate._settle(page)
                    caption = page.locator(".viewer p.muted").first.text_content() or ""
                    shown = caption.split("polyhedra ", 1)[-1]
                    box = page.locator(".viewer canvas").bounding_box()
                    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                    page.wait_for_timeout(500)
                    page.evaluate(WATCH)
                    page.mouse.move(cx - 90, cy)
                    page.mouse.down()
                    for k in range(60):
                        page.mouse.move(cx - 90 + 3 * k, cy + np.sin(k / 6) * 20)
                    page.mouse.up()
                    gaps = page.evaluate("() => { const g = window.__gaps; window.__gaps = null; return g; }")
                    loaf = page.evaluate("() => window.__loaf.length")
                    q = np.quantile(np.array(gaps), [0.5, 0.95]) if gaps else [np.nan, np.nan]
                    print(f"{engine:8} run {run}: drag gap p50 {q[0]:.1f} p95 {q[1]:.1f} ms "
                          f"over {len(gaps)} frames, long frames {loaf}, "
                          f"load {os.getloadavg()[0]:.1f} on {os.cpu_count()} cpus | {shown}")
                    browser.close()
    finally:
        httpd.shutdown()


def compare(out: Path) -> None:
    sys.path.insert(0, str(REPO / "docs/wp/1462-spike"))
    import gate

    ref = out / "chromium"
    for engine in ("firefox", "webkit"):
        print(f"\n{engine} against chromium")
        for png in sorted(ref.glob("*.png")):
            other = out / engine / png.name
            if not other.exists():
                print(f"  {png.stem:18s} missing")
                continue
            mine = gate._image(other.read_bytes())[..., :3]
            theirs = gate._image(png.read_bytes())[..., :3]
            level = gate._levels(mine, theirs)
            share = (float((np.abs(mine - theirs).max(axis=2) > 32 / 255).mean())
                     if mine.shape == theirs.shape else 1.0)
            print(f"  {png.stem:18s} {level:6.2f} levels, {100 * share:5.2f} % past 32")


if __name__ == "__main__":
    verb, *rest = sys.argv[1:]
    if verb == "frames":
        frames(int(rest[0]) if rest else 3, rest[1] if len(rest) > 1 else "all")
    else:
        compare(Path(rest[0]))
