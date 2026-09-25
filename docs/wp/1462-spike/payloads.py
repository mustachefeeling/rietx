"""Write the real ``/api/structure3d`` payloads the prototype draws.

Three structures from ``tests/data``: LaB6 (cubic, isotropic), NAC with the
file's anisotropic tensors, and fluorapatite (hexagonal).  Run from anywhere
with the repository's venv; the JSON lands beside this file.
"""
import json
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3

here = Path(__file__).parent
data = here.parents[2] / "tests" / "data"
cases = {
    "lab6": structure_from_cif(str(data / "cod_1000055.cif")),
    "nac": structure_from_cif(str(data / "cod_1000236.cif"), aniso=True),
    "fap": structure_from_cif(str(data / "fluorapatite.cif")),
}
#: which species sit at a polyhedron's centre, per case; a GUI control in a real viewer
CENTRES = {"lab6": [], "nac": ["Al", "Ca"], "fap": ["P"]}


def polyhedra(payload: dict, centres: list[str]) -> list[dict]:
    """A server-side stand-in: the coordination polyhedron of every drawn centre atom.

    The shell is read off the bond segments, which already run over the 27
    nearest translations, so it is complete for every atom the bonds were
    built over.  Faces are the convex hull's triangles; an edge is kept only
    where its two faces are not coplanar, so a square face draws no diagonal.
    """
    out = []
    n_bonded = 1 + max((max(b["i"], b["j"]) for b in payload["bonds"]), default=-1)
    element_at = {tuple(np.round(a["pos"], 5)): payload["sites"][a["site"]]["element"]
                  for a in payload["atoms"]}
    for k, atom in enumerate(payload["atoms"][:n_bonded]):
        site = payload["sites"][atom["site"]]
        if site["element"] not in centres:
            continue
        here_ = np.array(atom["pos"])
        shell = {}
        # a segment is keyed by its endpoints, and a contact may have been found
        # from a translated copy of the centre, so match on position, not index
        for b in payload["bonds"]:
            for mine, other in ((b["a"], b["b"]), (b["b"], b["a"])):
                if not np.allclose(mine, here_, atol=1e-5):
                    continue
                element = element_at.get(tuple(np.round(other, 5)))
                # a ligand is a non-metal of another element: P's four O, not the
                # four Ca the radius-sum bond rule also reaches at 3.1-3.2 Å
                if element and element != site["element"] and not s3.is_metal(element):
                    shell[tuple(np.round(other, 5))] = other
        vertices = np.array(list(shell.values()))
        if len(vertices) < 4:
            continue
        hull = ConvexHull(vertices)
        faces = []
        for simplex, normal in zip(hull.simplices, hull.equations[:, :3]):
            a, b, c = vertices[simplex]
            if np.dot(np.cross(b - a, c - a), normal) < 0:       # wind outward
                simplex = simplex[[0, 2, 1]]
            faces.append([int(v) for v in simplex])
        edges = set()
        for f, (simplex, nbrs) in enumerate(zip(hull.simplices, hull.neighbors)):
            for m in range(3):
                g = nbrs[m]                    # the face opposite vertex m shares the other two
                if not np.allclose(hull.equations[f], hull.equations[g], atol=1e-6):
                    edge = tuple(sorted(int(v) for v in np.delete(simplex, m)))
                    edges.add(edge)
        out.append({"center": k, "color": site["color"], "vertices": vertices.tolist(),
                    "faces": faces, "edges": sorted(edges)})
    return out


for name, structure in cases.items():
    payload = s3.build(structure, phase=0)
    payload["polyhedra"] = polyhedra(payload, CENTRES[name])
    text = json.dumps(payload)
    (here / f"{name}.json").write_text(text)
    print(f"{name}: {len(payload['atoms'])} atoms, {len(payload['bonds'])} bonds, "
          f"{sum(s['aniso'] for s in payload['sites'])} anisotropic sites, "
          f"{len(payload['polyhedra'])} polyhedra "
          f"{sorted({len(p['vertices']) for p in payload['polyhedra']})}-vertex, {len(text)} bytes")
