"""What a figure says about itself, and the view that says least against it (WP-1503).

An agent pays for each look at a picture: about width × height / 750 tokens, a
turn, and a picture seen three turns ago may be gone after a compaction.  The
numbers a look would give are computed here instead, from the scene and a small
**id pass** (:func:`.raster.id_plane`): which atom or bond half is in front at
each pixel of a 256 px frame.  A projected disc misses the stick that hides an
atom, and the id pass does not.

There is no quality score.  A single number would be the mechanical rule the
package's agent-first design argues against, so the figure reports evidence and
the caller judges.  ``view="auto"`` (:func:`choose_view`) ranks low-index
directions by the same two numbers the report carries and returns the
runners-up, so the second choice is a lookup and not a search.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import numpy as np

from . import raster, views

#: The id pass's long side, in pixels.
ID_SIZE = 256
#: An atom is hidden when more than this share of the samples it would cover
#: have something in front of them.
HIDDEN_SHARE = 0.8
#: ``view="auto"`` tries every primitive direction [u, v, w] whose indices are at
#: most this many in magnitude, and the opening view.
SEARCH_INDEX = 2
#: How many of the ranked views ``candidates`` carries.
N_CANDIDATES = 5
OPENING = "opening"


@dataclass(frozen=True)
class FigureReport:
    """The numbers a look at the figure would give.

    ``hidden`` is the share of the atoms drawn inside the cell (not the images
    outside it) that are covered over more than 80 % by an atom or bond in
    front, at a long side of 256 px, and ``hidden_atoms`` their indices into the
    geometry's ``atoms``.  An atom under one sample at that size is left out of
    both.  ``dangling_bonds`` counts bond halves whose far atom is not drawn,
    the stubs ``hidden=`` leaves included.  ``label_overlaps`` counts
    pairs of drawn letters whose boxes intersect.  ``empty`` is the share of
    the picture's pixels with nothing drawn, read off the image.  ``cut`` is
    what :func:`~rietx.viz.keep` dropped from a kept atom, and ``note`` the
    geometry's own note, which says where ``build`` trimmed to the atom cap.
    ``warnings`` are sentences.
    """
    hidden: float
    hidden_atoms: list[int]
    dangling_bonds: int
    label_overlaps: int
    empty: float
    cut: dict[str, int]
    note: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class Probe:
    """What the id pass needs of a scene, built once and read for every view."""
    arrays: dict
    boundary: np.ndarray
    points: np.ndarray
    size: object
    margin: float
    fit: Callable


@dataclass
class Look:
    """One view through the id pass."""
    hidden: float
    hidden_atoms: list[int]
    empty: float
    unjudged: int


def probe(scene: dict, geometry: Mapping, size, margin: float, fit: Callable,
          axis_labels: bool) -> Probe:
    """The scene's arrays, which packed atoms lie outside the cell, the points
    the frame must hold beyond the atoms and bonds, and the small frame's size.

    ``fit(extent, size, margin)`` is the renderer's own
    (:func:`.render._fit`); ``margin`` is what pixel-sized things add beyond
    the box, in CSS px.
    """
    arrays = raster.scene_arrays(scene)
    boundary = np.array([bool(geometry["atoms"][k]["boundary"]) for k in arrays["index"]],
                        dtype=bool)
    points = [p for line in scene["lines"] for p in (line["a"], line["b"])]
    for face in scene["faces"]:
        points += np.asarray(face["triangles"], dtype=np.float64).reshape(-1, 3).tolist()
    if axis_labels:
        points += [label["pos"] for label in scene["labels"]]
    if isinstance(size, (tuple, list)):
        k = min(1.0, ID_SIZE / max(size))
        small = (max(1, round(size[0] * k)), max(1, round(size[1] * k)))
    else:
        small = min(int(size), ID_SIZE)
    return Probe(arrays=arrays, boundary=boundary,
                 points=np.asarray(points, dtype=np.float64).reshape(-1, 3),
                 size=small, margin=margin, fit=fit)


def look(p: Probe, R, compiled_path: bool | None = None) -> Look:
    """The figure seen from rotation ``R`` through a small id pass."""
    R = np.asarray(R, dtype=np.float64)
    pk = raster.pack_ids(p.arrays, R)
    boxes = [pk["atom_reach"], pk["half_reach"]]
    if len(p.points):
        v = p.points @ R.T
        boxes.append(np.stack([v[:, 0], v[:, 0], v[:, 1], v[:, 1]], axis=1))
    box = np.concatenate([b for b in boxes if len(b)]) if any(len(b) for b in boxes) else None
    if box is None:
        extent = (-1.0, 1.0, -1.0, 1.0)
    else:
        extent = (float(box[:, 0].min()), float(box[:, 1].max()),
                  float(box[:, 2].min()), float(box[:, 3].max()))
    frame = p.fit(extent, p.size, p.margin)
    plane = raster.id_plane(pk, frame, compiled_path)
    judged = ~p.boundary & (plane.seen > 0)
    covered = judged & (plane.front < (1.0 - HIDDEN_SHARE) * plane.seen)
    n = int(judged.sum())
    return Look(hidden=float(covered.sum()) / n if n else 0.0,
                hidden_atoms=[int(k) for k in plane.index[covered]],
                empty=float((plane.ids < 0).mean()),
                unjudged=int((~p.boundary & (plane.seen == 0)).sum()))


def directions(limit: int = SEARCH_INDEX) -> list[list[int]]:
    """Every primitive [u, v, w] with indices of magnitude at most ``limit``,
    smallest indices first, then fewest minus signs, then the first index
    positive.

    A direction and its opposite leave the same share of the frame empty, and
    often hide the same atoms, so the signs decide those ties: sorted by ``d``
    alone, [-2, -2, -1] came before [2, 2, 1] and [-1, 1, 0] before [1, -1, 0].
    """
    span = range(-limit, limit + 1)
    out = [[u, v, w] for u in span for v in span for w in span
           if (u, v, w) != (0, 0, 0) and math.gcd(math.gcd(abs(u), abs(v)), abs(w)) == 1]
    return sorted(out, key=lambda d: (sum(abs(x) for x in d), max(abs(x) for x in d),
                                      sum(x < 0 for x in d), next(x for x in d if x) < 0, d))


def choose_view(geometry: Mapping, p: Probe, up, turn, compiled_path: bool | None = None):
    """The low-index view with the least hidden, then the least empty.

    Each candidate is a direction [u, v, w] toward the viewer with the
    convention's up (``up=`` if given) and ``turn`` applied, plus the opening
    view, so the answer is never worse than it on these two numbers.  Ties go
    to the smaller indices, so the search is deterministic and the rotation it
    returns is what the recipe pins.  Returns the chosen ``view`` for
    :func:`.views.resolve` and the top :data:`N_CANDIDATES` as dicts of
    ``view``, ``hidden`` and ``empty``, the numbers the search read at
    :data:`ID_SIZE` from atoms and bonds alone.
    """
    tried, refused = [], None
    for rank, view in enumerate([*directions(), OPENING]):
        try:
            R = views.resolve(geometry, view, up, turn)
        except ValueError as exc:   # an up= along this direction cannot be up
            refused = refused or exc
            continue
        seen = look(p, R, compiled_path)
        tried.append((seen.hidden, seen.empty, rank, view))
    if not tried:
        raise refused
    tried.sort(key=lambda t: t[:3])
    return tried[0][3], [{"view": v, "hidden": h, "empty": e}
                         for h, e, _, v in tried[:N_CANDIDATES]]
