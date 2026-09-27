"""A view named in crystallographic terms (WP-1470 D12).

No program surveyed takes a zone axis or a plane normal: PyMOL's ``set_view``
takes 18 numbers and ChimeraX's ``view matrix`` 12, which a caller cannot write
without first capturing one.  OVITO's camera direction and up vector are the
primitive underneath, and a lattice direction [uvw] or a plane normal (hkl)
converts to one through the metric.  So a view here is a direction toward the
viewer and a direction kept up, both in the cell's own terms, then an optional
``turn`` in ASE's rotation string.

A rotation is row-major, its rows the screen's x (right), y (up) and z (toward
the viewer) in the structure's Cartesian Å frame, as the GUI's ``View`` has
it.  The figure carries the rotation it drew, and passing that back as
``view=`` draws the same picture.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np

from .scene import OPENING_EYE, OPENING_UP, look_from, up_axis

_AXES = {"a": 0, "b": 1, "c": 2}
VIEW_FORMS = ('"opening"', '"a"', '"b"', '"c"', "[u, v, w]", '{"hkl": (h, k, l)}',
              "a 3×3 rotation")


def _lattice(geometry: Mapping) -> np.ndarray:
    return np.asarray(geometry["lattice"], dtype=np.float64)


def direction(geometry: Mapping, spec) -> np.ndarray:
    """A Cartesian direction from ``"a"``/``"b"``/``"c"``, a lattice direction
    ``[u, v, w]`` or a plane normal ``{"hkl": (h, k, l)}``."""
    lattice = _lattice(geometry)
    if isinstance(spec, str):
        if spec not in _AXES:
            raise ValueError(f"unknown direction {spec!r}; give 'a', 'b', 'c', "
                             "[u, v, w] or {'hkl': (h, k, l)}")
        return lattice[_AXES[spec]].copy()
    if isinstance(spec, Mapping):
        if set(spec) != {"hkl"}:
            raise ValueError(f"a plane normal is {{'hkl': (h, k, l)}}, not {spec!r}")
        hkl = np.asarray(spec["hkl"], dtype=np.float64)
        if hkl.shape != (3,):
            raise ValueError(f"hkl needs three indices, got {spec['hkl']!r}")
        a, b, c = lattice
        volume = float(a @ np.cross(b, c))
        reciprocal = np.array([np.cross(b, c), np.cross(c, a), np.cross(a, b)]) / volume
        d = hkl @ reciprocal
    else:
        uvw = np.asarray(spec, dtype=np.float64)
        if uvw.shape != (3,):
            raise ValueError(f"a direction is [u, v, w], got {spec!r}")
        d = uvw @ lattice
    if not np.all(np.isfinite(d)) or float(d @ d) == 0.0:
        raise ValueError(f"{spec!r} names no direction")
    return d


def default_up(geometry: Mapping, toward: np.ndarray) -> np.ndarray:
    """The convention: c up, unless c is the lattice axis nearest the view
    direction, and then b.  Never parallel to the view."""
    lattice = _lattice(geometry)
    cosines = [abs(float(v @ toward)) / math.sqrt(float(v @ v) * float(toward @ toward))
               for v in lattice]
    return lattice[up_axis(int(np.argmax(cosines)))]


def ase_rotation(turn: str) -> np.ndarray:
    """ASE's ``rotate``: ``'50x,-10y,120z'`` to a matrix, applied in order.

    Read from ``ase/utils/__init__.py``: each term post-multiplies, and ASE
    draws ``positions @ rotation``, so the turns are about the screen's axes
    and ``'50x,40z'`` differs from ``'40z,50x'``.
    """
    rotation = np.identity(3)
    if turn == "":
        return rotation
    for term in turn.split(","):
        term = term.strip()
        if not term or term[-1] not in "xyz":
            raise ValueError(f"turn term {term!r} is not an angle and an axis, "
                             "like '30y' or '-15x'")
        i = "xyz".index(term[-1])
        a = math.radians(float(term[:-1]))
        s, c = math.sin(a), math.cos(a)
        if i == 0:
            m = [(1, 0, 0), (0, c, s), (0, -s, c)]
        elif i == 1:
            m = [(c, 0, -s), (0, 1, 0), (s, 0, c)]
        else:
            m = [(c, s, 0), (-s, c, 0), (0, 0, 1)]
        rotation = rotation @ np.asarray(m, dtype=np.float64)
    return rotation


def resolve(geometry: Mapping, view="opening", up=None, turn: str | None = None) -> np.ndarray:
    """The rotation for ``view``, ``up`` and ``turn``; see the module docstring.

    ``view`` is ``"opening"`` (the GUI's first picture, down the body diagonal
    with Cartesian z up), ``"a"``/``"b"``/``"c"`` (the GUI's buttons), a
    direction ``[u, v, w]``, a plane normal ``{"hkl": (h, k, l)}``, or a 3×3
    rotation.  The named direction points at the viewer.  ``up`` names the
    direction kept up in the same forms, and defaults to the convention
    (:func:`default_up`); the opening view keeps its own.
    """
    matrix = None
    if not isinstance(view, (str, Mapping)):
        arr = np.asarray(view, dtype=np.float64)
        if arr.shape == (3, 3):
            matrix = arr
    if matrix is not None:
        if up is not None:
            raise ValueError("a rotation already says which way is up; drop up=")
        if not np.allclose(matrix @ matrix.T, np.identity(3), atol=1e-6) \
                or np.linalg.det(matrix) < 0:
            raise ValueError("view= as a matrix must be a rotation: orthonormal "
                             "rows with determinant +1")
        rotation = matrix
    elif isinstance(view, str) and view == "opening":
        toward = np.asarray(OPENING_EYE, dtype=np.float64)
        keep = np.asarray(OPENING_UP) if up is None else direction(geometry, up)
        rotation = _look(toward, keep)
    else:
        try:
            toward = direction(geometry, view)
        except ValueError as exc:
            raise ValueError(f"{exc}; view= takes {', '.join(VIEW_FORMS)}") from None
        keep = default_up(geometry, toward) if up is None else direction(geometry, up)
        rotation = _look(toward, keep)
    if turn:
        rotation = (rotation.T @ ase_rotation(turn)).T
    return rotation


def _look(toward: np.ndarray, keep: np.ndarray) -> np.ndarray:
    cross = np.cross(toward, keep)
    if float(cross @ cross) <= 1e-12 * float(toward @ toward) * float(keep @ keep):
        raise ValueError("up= is parallel to the view direction, so it cannot be up")
    return np.asarray(look_from(list(toward), list(keep)), dtype=np.float64).reshape(3, 3)


def as_list(rotation: np.ndarray) -> list[list[float]]:
    return [[float(v) for v in row] for row in np.asarray(rotation).reshape(3, 3)]

