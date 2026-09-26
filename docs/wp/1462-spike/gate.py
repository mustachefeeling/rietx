"""WP-1462's GPU gate: the GUI's structure viewer on whatever GL driver a
machine has, and the same pictures compared with a reference machine's.

    .venv/bin/python docs/wp/1462-spike/gate.py run OUT CONFIG [--headed] [--payload=FILE]
    .venv/bin/python docs/wp/1462-spike/gate.py compare OUT REF

Run from the repository root with python playwright installed. ``run`` serves
NAC with its anisotropic tensors (the fixture ``tests/test_structure3d_browser.py``
uses) and drives one browser through a fixed script. It writes the pictures and
``CONFIG.json`` into ``OUT/CONFIG/``. The canvas is lifted over the page at
720 × 540 CSS px and the a/b/c overlay is hidden, so every machine draws the
same canvas and only the renderer can differ. The JSON names the GL driver each browser
reports, so a run says what it tested.

``compare`` prints each picture's difference from the reference run of the same
engine. A run passes the gate when all of these hold, set before the first CI
run on 2026-09-26:

- no page error, and the viewer did not report "no WebGL2";
- each picture's mean difference from the reference is under 2 levels of 255,
  and under 1 % of its pixels differ by more than 32 levels in a channel. The
  pictures are seven screenshots and the two exports. On the reference Mac the
  three engines agree to 0.09 levels and 0.14 %;
- the principal rings put at least ten times the ring ink of the ball picture;
- a redraw, and a context lost and restored, each land within 0.5 levels of the
  picture before them, and reset moves it by more than 2;
- both exports are 3000 px on the long side, and only the transparent one has
  a transparent corner.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

#: A browser and how it is launched. The chromium rows use the full build in
#: its new headless mode (``channel``), which has a headed browser's GPU stack;
#: the default headless shell always draws on SwiftShader.
CONFIGS: dict[str, dict] = {
    "chromium": {"channel": "chromium"},
    # ANGLE over Direct3D 11, on Windows; WARP where the machine has no GPU
    "chromium-d3d11": {"channel": "chromium",
                       "args": ["--use-angle=d3d11", "--ignore-gpu-blocklist"]},
    # ANGLE over desktop OpenGL, on Linux: Mesa where the machine has no GPU
    "chromium-gl": {"channel": "chromium",
                    "args": ["--use-angle=gl", "--ignore-gpu-blocklist"]},
    "firefox": {},
    "firefox-forced": {"firefox_user_prefs": {"webgl.force-enabled": True}},
    "webkit": {},
}

#: The canvas lifted over the page at a fixed size, so no layout, font or
#: scrollbar can cover it or change its size between machines.
PIN = """
.viewer canvas { position: fixed !important; inset: auto !important; left: 0 !important;
  top: 0 !important; width: 720px !important; height: 540px !important;
  z-index: 2147483647 !important; }
.viewer .letters { visibility: hidden !important; }
"""

DRIVER = """() => {
  const gl = document.querySelector(".viewer canvas").getContext("webgl2");
  if (!gl) return null;
  const info = gl.getExtension("WEBGL_debug_renderer_info");
  return {
    vendor: gl.getParameter(info ? info.UNMASKED_VENDOR_WEBGL : gl.VENDOR),
    renderer: gl.getParameter(info ? info.UNMASKED_RENDERER_WEBGL : gl.RENDERER),
    version: gl.getParameter(gl.VERSION),
    shading: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
    samples: gl.getParameter(gl.SAMPLES),
    maxSamples: gl.getParameter(gl.MAX_SAMPLES),
    maxRenderbuffer: gl.getParameter(gl.MAX_RENDERBUFFER_SIZE),
    attributes: gl.getContextAttributes(),
  };
}"""

LOSE_AND_RESTORE = """() => new Promise((done) => {
  const canvas = document.querySelector(".viewer canvas");
  const ext = canvas.getContext("webgl2").getExtension("WEBGL_lose_context");
  if (!ext) return done(false);
  canvas.addEventListener("webglcontextrestored", () => done(true), { once: true });
  canvas.addEventListener("webglcontextlost", () => setTimeout(() => ext.restoreContext(), 50),
                          { once: true });
  ext.loseContext();
})"""

COUNT_CONTEXTS = """() => {
  window.__gl = { made: 0, lost: 0 };
  const get = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (kind, ...rest) {
    const c = get.call(this, kind, ...rest);
    if (kind === "webgl2" && c && !this.__counted) {
      this.__counted = true;
      window.__gl.made += 1;
      this.addEventListener("webglcontextlost", () => { window.__gl.lost += 1; });
    }
    return c;
  };
}"""


def _serve(tmp: Path) -> tuple[str, object]:
    import rietx as rx
    from rietx.crystallography.cif import structure_from_cif
    from rietx.gui import GuiSession
    from tests.test_gui_server import _start
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import perturbed_models, synthesize

    data = _write_xye(tmp / "synth.xye", synthesize())
    _, instrument = perturbed_models()
    structure = structure_from_cif(str(REPO / "tests/data/cod_1000236.cif"), aniso=True)
    project = rx.Project.create(tmp / "nac.rex", pattern=data, instrument=instrument,
                                structure=structure, plan="mccusker_default")
    httpd = _start(GuiSession(project, state_dir=tmp / "state"))
    return f"http://127.0.0.1:{httpd.server_address[1]}/", httpd


def _image(png: bytes) -> np.ndarray:
    from matplotlib.image import imread

    return np.asarray(imread(io.BytesIO(png)), dtype=float)


def _drawn(rgb: np.ndarray) -> float:
    """The share of the picture that is not its background (the corner pixel)."""
    return float((np.abs(rgb - rgb[0, 0]).sum(axis=2) > 0.06).mean())


def _ring_ink(rgb: np.ndarray) -> int:
    """Pixels in the ring ink a fluorine wears: green-dominant and dark."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return int(((g < 0.30) & (g > 1.6 * r) & (g > 1.6 * b)).sum())


def _levels(a: np.ndarray, b: np.ndarray) -> float:
    """Mean absolute difference in levels of 255, or inf for two sizes."""
    return float(np.abs(a - b).mean() * 255) if a.shape == b.shape else float("inf")


def _settle(page, frames: int = 4) -> None:
    page.evaluate("n => new Promise(r => { const f = k => k ? requestAnimationFrame(() => f(k - 1)) : r(); f(n); })",
                  frames)


def run(out: Path, config: str, headed: bool, payload: Path | None = None) -> dict:
    """One configuration's run. ``payload`` replays a saved ``/api/structure3d``
    answer in place of this machine's, so two machines draw the same numbers:
    the server's eigen-decomposition is this machine's LAPACK, and a tensor
    uniaxial by symmetry has two principal axes any LAPACK may choose."""
    import tempfile

    from playwright.sync_api import sync_playwright

    engine = config.split("-")[0]
    here = out / config
    here.mkdir(parents=True, exist_ok=True)
    record: dict = {"config": config, "engine": engine, "headed": headed,
                    "platform": sys.platform, "payload": str(payload) if payload else None,
                    "errors": [], "failed": [], "pictures": {}}
    url, httpd = _serve(Path(tempfile.mkdtemp(prefix="gate-")))
    try:
        with sync_playwright() as p:
            launcher = getattr(p, engine)
            browser = launcher.launch(headless=not headed, **CONFIGS[config])
            record["browser"] = browser.version
            ctx = browser.new_context(viewport={"width": 1400, "height": 900},
                                      device_scale_factor=2, accept_downloads=True)
            page = ctx.new_page()
            page.on("pageerror", lambda e: record["errors"].append(str(e)))
            # a refused route is in `failed`; the GUI answers 409 until a fit has run
            page.on("console", lambda m: m.type == "error" and not m.text.startswith(
                "Failed to load resource") and record["errors"].append(m.text))
            page.on("response", lambda r: r.status >= 400 and record["failed"].append(f"{r.status} {r.url}"))
            page.add_init_script(COUNT_CONTEXTS.join(["(", ")()"]))
            served = []
            page.on("response", lambda r: "/api/structure3d" in r.url and served.append(r))
            if payload:
                text = payload.read_text()
                page.route("**/api/structure3d*", lambda route: route.fulfill(
                    status=200, content_type="application/json", body=text))
            page.goto(url)
            page.add_style_tag(content=PIN)
            page.get_by_role("button", name="Model", exact=True).click()
            canvas = page.locator(".viewer canvas")
            canvas.wait_for()
            _settle(page, 8)
            # the fetch can land after the settle on a slow machine
            page.wait_for_function("() => ![...document.querySelectorAll('.viewer p.muted')]"
                                   ".some((p) => p.textContent.startsWith('loading'))", timeout=60000)
            bad = page.locator(".viewer p.bad")
            record["viewer_error"] = bad.first.text_content() if bad.count() else None
            if served:
                (here / "payload.json").write_bytes(served[0].body())
            if record["viewer_error"]:
                # the viewer's own answer to a browser with no WebGL2; nothing to draw
                canvas.screenshot(path=here / "unsupported.png")
                browser.close()
                return _write(here, record)
            record["driver"] = page.evaluate(DRIVER)
            box = canvas.bounding_box()
            record["canvas_css"] = [box["width"], box["height"]]
            cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            away = (box["x"] + box["width"] + 40, box["y"] + box["height"] + 40)

            def shoot(name: str) -> np.ndarray:
                page.mouse.move(*away)
                _settle(page)
                png = canvas.screenshot()
                (here / f"{name}.png").write_bytes(png)
                rgb = _image(png)[..., :3]
                record["pictures"][name] = {"drawn": _drawn(rgb), "ring_ink": _ring_ink(rgb),
                                            "shape": list(rgb.shape[:2])}
                return rgb

            home = shoot("ball")
            # the first offset along a fixed sweep that the pick answers
            for dx in range(-90, 91, 6):
                page.mouse.move(cx + dx, cy + dx / 3)
                _settle(page, 2)
                text = (page.locator(".viewer .reading").text_content() or "").strip()
                if text:
                    record["hover"] = {"dx": dx, "reading": text}
                    break
            page.get_by_role("button", name="ellipsoids", exact=True).click()
            shoot("ellipsoid")
            page.get_by_role("button", name="▸ drawing").click()
            page.locator('.drawer input[type="range"][max="4"]').evaluate(
                "el => { el.value = '4'; el.dispatchEvent(new Event('input', { bubbles: true })); }")
            # a synthetic wheel: each engine turns a real one into its own delta
            canvas.dispatch_event("wheel", {"deltaY": -600, "deltaMode": 0,
                                            "clientX": cx, "clientY": cy})
            shoot("rings")
            page.get_by_role("button", name="balls", exact=True).click()
            shoot("rings-ball")
            page.get_by_role("button", name="reset", exact=True).click()
            page.mouse.move(cx, cy)
            page.mouse.down()
            for k in range(1, 16):
                page.mouse.move(cx + 6 * k, cy + 2 * k)
            page.mouse.up()
            dragged = shoot("dragged")
            record["reset_levels"] = _levels(dragged, home)
            page.get_by_role("button", name="ellipsoids", exact=True).click()
            _settle(page)
            page.get_by_role("button", name="balls", exact=True).click()
            record["redraw_levels"] = _levels(shoot("redrawn"), dragged)
            record["restored"] = page.evaluate(LOSE_AND_RESTORE)
            record["restore_levels"] = _levels(shoot("restored"), dragged)

            record["exports"] = []
            for transparent in (False, True):
                if transparent:
                    page.locator(".drawer label", has_text="transparent PNG").locator("input").check()
                with page.expect_download(timeout=60000) as download:
                    page.locator("section.viewer").get_by_role("button", name="PNG", exact=True).click()
                name = f"export{'-transparent' if transparent else ''}.png"
                download.value.save_as(here / name)
                png = (here / name).read_bytes()
                rgba = _image(png)
                record["exports"].append({
                    "transparent": transparent, "bytes": len(png),
                    "width": int.from_bytes(png[16:20], "big"),
                    "height": int.from_bytes(png[20:24], "big"),
                    "corner_alpha": float(rgba[0, 0, 3]) if rgba.shape[2] == 4 else 1.0,
                    "drawn": _drawn(rgba[..., :3])})
            for _ in range(5):
                page.get_by_role("button", name="3D", exact=True).click()
                _settle(page)
                page.get_by_role("button", name="3D", exact=True).click()
                _settle(page, 8)
            record["contexts"] = page.evaluate("window.__gl")
            browser.close()
    finally:
        httpd.shutdown()
    return _write(here, record)


def _write(here: Path, record: dict) -> dict:
    (here / f"{record['config']}.json").write_text(json.dumps(record, indent=1))
    return record


def compare(out: Path, ref: Path) -> bool:
    """Print every run under ``out`` against ``ref``'s run of the same engine."""
    ok = True
    for path in sorted(p for p in out.glob("*/*.json") if p.stem == p.parent.name):
        rec = json.loads(path.read_text())
        base = ref / rec["engine"]
        print(f"\n{path.parent.name}: {rec.get('browser')} on {rec['platform']}"
              + (f", replaying {Path(rec['payload']).name}" if rec.get("payload") else ""))
        if rec.get("viewer_error"):
            print(f"  the viewer declined: {rec['viewer_error']}")
            ok = False
            continue
        driver = rec.get("driver") or {}
        print(f"  driver  {driver.get('vendor')} | {driver.get('renderer')} | samples {driver.get('samples')}")
        checks = {
            "no page error": not rec["errors"],
            "viewer drew": rec.get("viewer_error") is None and driver != {},
            "rings ≥ 10× ball ink": rec["pictures"]["rings"]["ring_ink"]
                >= 10 * max(rec["pictures"]["rings-ball"]["ring_ink"], 1),
            "redraw keeps view": rec["redraw_levels"] < 0.5,
            "context restored": bool(rec["restored"]) and rec["restore_levels"] < 0.5,
            "reset moves view": rec["reset_levels"] > 2,
            "exports 3000 px": all(max(e["width"], e["height"]) == 3000 for e in rec["exports"]),
            "only the transparent export is": [e["corner_alpha"] for e in rec["exports"]] == [1.0, 0.0],
        }
        # the screenshots, and the two exports, alpha included
        for png in sorted(p for p in path.parent.glob("*.png") if p.stem != "unsupported"):
            name = png.stem
            if not (base / png.name).exists():
                print(f"  {name:18s} the reference has no such picture")
                checks[f"{name} matches reference"] = False
                continue
            mine = _image(png.read_bytes())
            theirs = _image((base / png.name).read_bytes())
            level = _levels(mine, theirs)
            share = (float((np.abs(mine - theirs).max(axis=2) > 32 / 255).mean())
                     if mine.shape == theirs.shape else 1.0)
            shot = rec["pictures"].get(name)
            print(f"  {name:18s} {level:6.2f} levels, {100 * share:5.2f} % past 32"
                  + (f"   drawn {shot['drawn']:.3f}  ring ink {shot['ring_ink']}" if shot else ""))
            checks[f"{name} matches reference"] = level < 2 and share < 0.01
        print(f"  hover   {rec.get('hover')}")
        print(f"  redraw {rec['redraw_levels']:.3f}  restore {rec['restore_levels']:.3f}"
              f"  reset {rec['reset_levels']:.2f}  contexts {rec.get('contexts')}")
        print(f"  errors  {rec['errors'][:3]}  failed {rec['failed'][:3]}")
        failed = [k for k, v in checks.items() if not v]
        print("  GO" if not failed else f"  NO-GO: {failed}")
        ok &= not failed
    return ok


if __name__ == "__main__":
    verb, *rest = sys.argv[1:]
    if verb == "run":
        replay = next((Path(a.split("=", 1)[1]) for a in rest if a.startswith("--payload=")), None)
        rec = run(Path(rest[0]), rest[1], "--headed" in rest, replay)
        print(json.dumps({k: rec.get(k) for k in ("config", "browser", "driver", "viewer_error", "errors")},
                         indent=1))
    else:
        sys.exit(0 if compare(Path(rest[0]), Path(rest[1])) else 1)
