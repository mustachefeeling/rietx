"""The named ↔ flat-vector translation layer.

Compiles a (Structure, Instrument) pair into:

* an ordered table of every :class:`Parameter` with a stable dot-separated
  path (``phases.0.cell.a``, ``instrument.profile.w``,
  ``instrument.background.c2`` …);
* identity ties implied by the crystal system (cubic: b = a, c = a; the
  general affine-constraint machinery arrives with Wyckoff support in v0.2);
* the mapping between the free internal vector θ (what the optimiser sees)
  and the full physical value dict consumed by the forward model.

The decode path is plain float arithmetic on pre-built index lists — no
pydantic objects are touched per iteration.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..crystallography.symmetry import get_spacegroup
from ..schemas.common import Parameter
from ..schemas.instrument import BackgroundChebyshev, BackgroundPSpline, Instrument
from ..schemas.structure import Structure
from .transforms import dphys_dinternal, internal_bounds, to_internal, to_physical


def _background_parameters(bkg) -> list[tuple[str, Parameter]]:
    """(sub-path, Parameter) pairs for any background model, in design order."""
    if isinstance(bkg, BackgroundPSpline):
        out = [(f"c{n}", p) for n, p in enumerate(bkg.coefficients)]
        out.append(("air", bkg.air_scatter))
        return out
    cheb = bkg.coefficients if isinstance(bkg, BackgroundChebyshev) else bkg.chebyshev.coefficients
    return [(f"c{n}", p) for n, p in enumerate(cheb)]


@dataclass
class Entry:
    path: str
    value: float
    vary: bool
    lo: float
    hi: float
    transform: str
    tied_to: str | None = None  # identity tie (dependent ← source path)
    locked: bool = False  # structurally fixed: set_vary may never free it


# crystal-system cell ties: dependent → source for the identity ties, plus a
# set of angle values fixed by symmetry (never refinable in those systems).
_CELL_TIES: dict[str, dict[str, str]] = {
    "cubic": {"b": "a", "c": "a"},
    "tetragonal": {"b": "a"},
    "hexagonal": {"b": "a"},
    "trigonal": {"b": "a"},  # hexagonal-axes setting (gemmi default for R groups)
    "orthorhombic": {},
    "monoclinic": {},
    "triclinic": {},
}
_FIXED_ANGLES: dict[str, tuple[str, ...]] = {
    "cubic": ("alpha", "beta", "gamma"),
    "tetragonal": ("alpha", "beta", "gamma"),
    "hexagonal": ("alpha", "beta", "gamma"),
    "trigonal": ("alpha", "beta", "gamma"),
    "orthorhombic": ("alpha", "beta", "gamma"),
    "monoclinic": ("alpha", "gamma"),
    "triclinic": (),
}


class ParameterTable:
    def __init__(self, structure: Structure, instrument: Instrument):
        self.entries: list[Entry] = []
        self._collect(structure, instrument)
        self._free_idx = [i for i, e in enumerate(self.entries) if e.vary and e.tied_to is None]
        self._paths = {e.path: i for i, e in enumerate(self.entries)}

    # -- collection ----------------------------------------------------
    def _add(self, path: str, p: Parameter, *, force_fixed: bool = False,
             tied_to: str | None = None) -> None:
        self.entries.append(Entry(
            path=path, value=p.value, vary=p.vary and not force_fixed and tied_to is None,
            lo=p.min, hi=p.max, transform=p.transform, tied_to=tied_to,
            locked=force_fixed,
        ))

    def _collect(self, structure: Structure, instrument: Instrument) -> None:
        for ip, phase in enumerate(structure.phases):
            system = get_spacegroup(phase.space_group).crystal_system_str()
            ties = _CELL_TIES.get(system, {})
            fixed_angles = _FIXED_ANGLES.get(system, ())
            base = f"phases.{ip}"
            for name in ("a", "b", "c", "alpha", "beta", "gamma"):
                p: Parameter = getattr(phase.cell, name)
                if name in ties:
                    self._add(f"{base}.cell.{name}", p, tied_to=f"{base}.cell.{ties[name]}")
                elif name in fixed_angles:
                    self._add(f"{base}.cell.{name}", p, force_fixed=True)
                else:
                    self._add(f"{base}.cell.{name}", p)
            self._add(f"{base}.scale", phase.scale)
            self._add(f"{base}.lor_size", phase.lor_size)
            self._add(f"{base}.lor_strain", phase.lor_strain)
            self._add(f"{base}.gauss_size", phase.gauss_size)
            self._add(f"{base}.gauss_strain", phase.gauss_strain)
            for j, atom in enumerate(phase.atoms):
                for coord in ("x", "y", "z"):
                    cp: Parameter = getattr(atom, coord)
                    if cp.vary:
                        raise NotImplementedError(
                            f"refining atomic coordinates ({base}.atoms.{j}.{coord}) requires "
                            "Wyckoff-aware symmetry constraints, planned for v0.3; set vary=False"
                        )
                    self._add(f"{base}.atoms.{j}.{coord}", cp)
                self._add(f"{base}.atoms.{j}.occ", atom.occ)
                self._add(f"{base}.atoms.{j}.biso", atom.biso)

        self._add("instrument.zero_shift", instrument.zero_shift)
        self._add("instrument.polarization", instrument.source.polarization)
        for il, line in enumerate(instrument.source.lines):
            # line 0 defines the intensity scale: its weight is degenerate with
            # the phase scale factors, so it is always held fixed
            self._add(f"instrument.source.lines.{il}.weight", line.weight,
                      force_fixed=(il == 0))
        geom = instrument.geometry
        for name in ("sample_displacement", "sample_transparency",
                     "axial_sl", "axial_hl"):
            self._add(f"instrument.geometry.{name}", getattr(geom, name),
                      force_fixed=(geom.kind != "bragg_brentano"
                                   and name.startswith("sample_")))
        for name in ("u", "v", "w", "x", "y"):
            self._add(f"instrument.profile.{name}", getattr(instrument.profile, name))
        for sub, cp in _background_parameters(instrument.background):
            self._add(f"instrument.background.{sub}", cp)

    # -- vary control (used by the staged strategy) --------------------
    def set_vary(self, path_globs: list[str], vary: bool) -> list[str]:
        """Glob-match entry paths (fnmatch semantics on dot paths); returns hits.

        Tied and locked entries never match: symmetry-fixed cell angles and
        the line-0 emission weight cannot be freed even by a broad glob such
        as ``phases.*.cell.*``.
        """
        import fnmatch

        hits = []
        for e in self.entries:
            if any(fnmatch.fnmatchcase(e.path, g) for g in path_globs):
                if e.tied_to is None and not e.locked:
                    e.vary = vary
                    hits.append(e.path)
        self._free_idx = [i for i, e in enumerate(self.entries) if e.vary and e.tied_to is None]
        return hits

    # -- optimiser interface -------------------------------------------
    @property
    def free_paths(self) -> list[str]:
        return [self.entries[i].path for i in self._free_idx]

    def x0(self) -> np.ndarray:
        return np.array([to_internal(self.entries[i].value, self.entries[i].transform)
                         for i in self._free_idx], dtype=np.float64)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        lo, hi = [], []
        for i in self._free_idx:
            e = self.entries[i]
            low, high = internal_bounds(e.lo, e.hi, e.transform)
            lo.append(low)
            hi.append(high)
        return np.asarray(lo), np.asarray(hi)

    def decode(self, theta: np.ndarray) -> dict[str, float]:
        """Internal free vector → full physical value dict (ties applied)."""
        values = {e.path: e.value for e in self.entries}
        for t, i in zip(theta, self._free_idx, strict=True):
            e = self.entries[i]
            values[e.path] = to_physical(float(t), e.transform)
        for e in self.entries:
            if e.tied_to is not None:
                values[e.path] = values[e.tied_to]
        return values

    def commit(self, theta: np.ndarray) -> None:
        """Write refined values back into the table (used between stages)."""
        values = self.decode(theta)
        for e in self.entries:
            e.value = values[e.path]

    def stderr_physical(self, theta: np.ndarray, stderr_internal: np.ndarray) -> dict[str, float]:
        """Map internal esds to physical units via the transform chain rule."""
        out: dict[str, float] = {}
        for t, s, i in zip(theta, stderr_internal, self._free_idx, strict=True):
            e = self.entries[i]
            out[e.path] = abs(dphys_dinternal(float(t), e.transform)) * float(s)
        # tied params inherit the source esd (identity ties)
        for e in self.entries:
            if e.tied_to is not None and e.tied_to in out:
                out[e.path] = out[e.tied_to]
        return out

    def apply_to_models(self, structure: Structure, instrument: Instrument) -> None:
        """Write current table values back into (copies of) the pydantic models."""
        values = {e.path: e.value for e in self.entries}
        for ip, phase in enumerate(structure.phases):
            base = f"phases.{ip}"
            for name in ("a", "b", "c", "alpha", "beta", "gamma"):
                getattr(phase.cell, name).value = values[f"{base}.cell.{name}"]
            phase.scale.value = values[f"{base}.scale"]
            phase.lor_size.value = values[f"{base}.lor_size"]
            phase.lor_strain.value = values[f"{base}.lor_strain"]
            phase.gauss_size.value = values[f"{base}.gauss_size"]
            phase.gauss_strain.value = values[f"{base}.gauss_strain"]
            for j, atom in enumerate(phase.atoms):
                atom.occ.value = values[f"{base}.atoms.{j}.occ"]
                atom.biso.value = values[f"{base}.atoms.{j}.biso"]
        instrument.zero_shift.value = values["instrument.zero_shift"]
        instrument.source.polarization.value = values["instrument.polarization"]
        for il, line in enumerate(instrument.source.lines):
            line.weight.value = values[f"instrument.source.lines.{il}.weight"]
        for name in ("sample_displacement", "sample_transparency",
                     "axial_sl", "axial_hl"):
            getattr(instrument.geometry, name).value = values[f"instrument.geometry.{name}"]
        for name in ("u", "v", "w", "x", "y"):
            getattr(instrument.profile, name).value = values[f"instrument.profile.{name}"]
        for sub, cp in _background_parameters(instrument.background):
            cp.value = values[f"instrument.background.{sub}"]
