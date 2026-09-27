import json
import urllib.request

pk = ["matplotlib", "pillow", "pycairo", "cairocffi", "skia-python", "resvg-py",
      "moderngl", "glcontext", "vtk", "pyvista", "vispy", "fresnel", "pyrender",
      "cairosvg", "py3Dmol", "ase"]
for p in pk:
    try:
        d = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{p}/json", timeout=20))
    except Exception as e:
        print(f"{p:14s} ERR {e}")
        continue
    v = d["info"]["version"]
    files = d["urls"]
    date = min((f["upload_time"][:10] for f in files), default="?")
    lic = (d["info"].get("license_expression") or d["info"].get("license") or "")[:24].replace("\n", " ")

    def pick(tag):
        c = [f for f in files if f["packagetype"] == "bdist_wheel" and tag in f["filename"]
             and ("cp312" in f["filename"] or "py3" in f["filename"] or "abi3" in f["filename"])]
        return max((f["size"] for f in c), default=0)

    lin, mac, win = pick("manylinux"), pick("macosx"), pick("win_amd64")
    anyw = [f for f in files if f["filename"].endswith("none-any.whl")]
    if anyw and not (lin or mac):
        lin = mac = win = anyw[0]["size"]
    sdist = any(f["packagetype"] == "sdist" for f in files)

    def mb(x):
        return f"{x / 1e6:6.1f}" if x else "   -  "

    print(f"{p:14s} {v:12s} {date}  linux {mb(lin)}  mac {mb(mac)}  win {mb(win)}  sdist={sdist}  {lic}")
