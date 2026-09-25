"""Write the real ``/api/structure3d`` payloads the prototype draws.

Three structures from ``tests/data``: LaB6 (cubic, isotropic), NAC with the
file's anisotropic tensors, and fluorapatite (hexagonal).  Run from anywhere
with the repository's venv; the JSON lands beside this file.
"""
import json
from pathlib import Path

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3

here = Path(__file__).parent
data = here.parents[2] / "tests" / "data"
cases = {
    "lab6": structure_from_cif(str(data / "cod_1000055.cif")),
    "nac": structure_from_cif(str(data / "cod_1000236.cif"), aniso=True),
    "fap": structure_from_cif(str(data / "fluorapatite.cif")),
}
for name, structure in cases.items():
    payload = s3.build(structure, phase=0)
    text = json.dumps(payload)
    (here / f"{name}.json").write_text(text)
    print(f"{name}: {len(payload['atoms'])} atoms, {len(payload['bonds'])} bonds, "
          f"{sum(s['aniso'] for s in payload['sites'])} anisotropic sites, {len(text)} bytes")
