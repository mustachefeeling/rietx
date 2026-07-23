"""The named ↔ flat-vector translation layer.

Compiles a (Structure, Instrument) pair into:

* an ordered table of every :class:`Parameter` with a stable dot-separated
  path (``phases.0.cell.a``, ``instrument.profile.w``,
  ``instrument.background.c2`` …);
* an affine constraint block **p_phys = C·p_free + d** (sparse C, rebuilt at
  every stage boundary, constant during a least-squares run — a constant
  matmul stays exact under the future autodiff backends).  Crystal-system
  cell ties are the identity-row special case; Wyckoff site constraints
  (``crystallography.wyckoff``) supply general rows;
* the mapping between the free internal vector θ (what the optimiser sees)
  and the full physical value dict consumed by the forward model.

The decode path is plain float/array arithmetic on a pre-built sparse
matrix — no pydantic objects are touched per iteration.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse

from ..crystallography.symmetry import get_spacegroup
from ..crystallography.wyckoff import coordinate_basis, stabilizer_rotations
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


@dataclass(frozen=True)
class AffineTie:
    """Declares one physical parameter as an affine function of others.

    value(path) = Σ coeff · value(source path) + const.  Sources may
    themselves be tied (chains are flattened at rebuild); cycles are an
    error.  :meth:`identity` gives the b ← a cell-tie special case.
    """

    terms: tuple[tuple[str, float], ...]
    const: float = 0.0

    @classmethod
    def identity(cls, source: str) -> "AffineTie":
        return cls(terms=((source, 1.0),))


@dataclass
class Entry:
    path: str
    value: float
    vary: bool
    lo: float
    hi: float
    transform: str
    tie: AffineTie | None = None  # affine dependence on other entries
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
        self._rebuild()

    # -- collection ----------------------------------------------------
    def _add(self, path: str, p: Parameter, *, force_fixed: bool = False,
             tie: AffineTie | None = None) -> None:
        self.entries.append(Entry(
            path=path, value=p.value, vary=p.vary and not force_fixed and tie is None,
            lo=p.min, hi=p.max, transform=p.transform, tie=tie,
            locked=force_fixed,
        ))

    def _collect(self, structure: Structure, instrument: Instrument) -> None:
        for ip, phase in enumerate(structure.phases):
            sg = get_spacegroup(phase.space_group)
            system = sg.crystal_system_str()
            ties = _CELL_TIES.get(system, {})
            fixed_angles = _FIXED_ANGLES.get(system, ())
            base = f"phases.{ip}"
            for name in ("a", "b", "c", "alpha", "beta", "gamma"):
                p: Parameter = getattr(phase.cell, name)
                if name in ties:
                    self._add(f"{base}.cell.{name}", p,
                              tie=AffineTie.identity(f"{base}.cell.{ties[name]}"))
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
                self._collect_atom_coords(f"{base}.atoms.{j}", sg, atom)
                self._add(f"{base}.atoms.{j}.occ", atom.occ)
                self._add(f"{base}.atoms.{j}.biso", atom.biso)

        self._add("instrument.zero_shift", instrument.zero_shift)
        self._collect_instrument(instrument)

    def _collect_atom_coords(self, base: str, sg, atom) -> None:
        """Coordinates enter θ through site-symmetry displacement DOFs.

        Each site contributes ``…dof.k`` parameters — one per site-symmetry-
        allowed direction (``crystallography.wyckoff``) — and x, y, z become
        affine rows x = x₀ + Σₖ Bₖ·θₖ anchored at the compile-time position.
        Fully fixed special positions contribute none (their coordinates are
        locked); ``vary=True`` on any coordinate of such a site is an error.
        A vary request on a constrained-but-free site frees *all* of the
        site's DOFs — per-axis intent does not map onto rows such as [1,1,0].
        DOFs are unbounded displacements; bounds declared on x/y/z do not
        constrain them.
        """
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        basis = coordinate_basis(stabilizer_rotations(sg, xyz))
        want_vary = any(getattr(atom, c).vary for c in ("x", "y", "z"))
        if len(basis) == 0 and want_vary:
            raise ValueError(
                f"{base} sits on a fully fixed special position; its site "
                "symmetry allows no positional freedom — set vary=False")
        dof_paths = [f"{base}.dof.{k}" for k in range(len(basis))]
        for c_idx, c in enumerate(("x", "y", "z")):
            p: Parameter = getattr(atom, c)
            terms = tuple((dof_paths[k], float(basis[k][c_idx]))
                          for k in range(len(basis)) if basis[k][c_idx] != 0)
            if terms:
                self._add(f"{base}.{c}", p, tie=AffineTie(terms=terms, const=p.value))
            else:
                self._add(f"{base}.{c}", p, force_fixed=True)
        for path in dof_paths:
            self.entries.append(Entry(path=path, value=0.0, vary=want_vary,
                                      lo=-np.inf, hi=np.inf, transform="identity"))

    def _collect_instrument(self, instrument: Instrument) -> None:
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

    # -- the affine constraint block -----------------------------------
    def _flatten(self, tie: AffineTie, _seen: tuple[str, ...] = ()
                 ) -> tuple[list[tuple[int, float]], float]:
        """Resolve a tie onto untied entries: chains collapse, cycles raise."""
        terms: list[tuple[int, float]] = []
        const = tie.const
        for path, coeff in tie.terms:
            if path in _seen:
                raise ValueError(f"cyclic parameter tie through {path!r}")
            i = self._paths.get(path)
            if i is None:
                raise ValueError(f"tie references unknown parameter {path!r}")
            src = self.entries[i]
            if src.tie is None:
                terms.append((i, coeff))
            else:
                sub_terms, sub_const = self._flatten(src.tie, _seen + (path,))
                terms.extend((j, coeff * c) for j, c in sub_terms)
                const += coeff * sub_const
        return terms, const

    def _rebuild(self) -> None:
        """Recompile p_phys = C·p_free + d from the current entries.

        Free entries get unit rows, held entries put their value in ``d``,
        tied entries scatter flattened coefficients into ``C`` (free
        sources) and ``d`` (held sources + constants).  Rebuilds happen
        only at stage boundaries (``set_vary`` / ``commit`` / ``set_tie``),
        never inside a least-squares run, so the map is a constant matmul
        while the optimiser looks at it.
        """
        self._paths = {e.path: i for i, e in enumerate(self.entries)}
        self._free_idx = [i for i, e in enumerate(self.entries) if e.vary and e.tie is None]
        col = {i: k for k, i in enumerate(self._free_idx)}
        n, m = len(self.entries), len(self._free_idx)
        c_rows: list[int] = []
        c_cols: list[int] = []
        c_vals: list[float] = []
        d = np.zeros(n, dtype=np.float64)
        for i, e in enumerate(self.entries):
            if e.tie is None:
                if i in col:
                    c_rows.append(i)
                    c_cols.append(col[i])
                    c_vals.append(1.0)
                else:
                    d[i] = e.value
            else:
                terms, const = self._flatten(e.tie, (e.path,))
                d[i] = const
                for j, coeff in terms:
                    if j in col:
                        c_rows.append(i)
                        c_cols.append(col[j])
                        c_vals.append(coeff)
                    else:
                        d[i] += coeff * self.entries[j].value
        self._C = sparse.csr_matrix((c_vals, (c_rows, c_cols)), shape=(n, m))
        self._d = d

    def constraint_block(self) -> tuple[sparse.csr_matrix, np.ndarray]:
        """The current (C, d) with rows in entry order, columns in θ order."""
        return self._C, self._d

    # -- table surgery (used by Wyckoff constraint wiring) -------------
    def add_parameter(self, path: str, value: float, *, vary: bool = False,
                      lo: float = -np.inf, hi: float = np.inf,
                      transform: str = "identity") -> None:
        """Append a synthetic parameter (e.g. a Wyckoff displacement DOF).

        Synthetic paths must not collide with existing entries; pick names
        outside the model tree, e.g. ``phases.0.atoms.2.dof.0``.
        """
        if path in self._paths:
            raise ValueError(f"parameter {path!r} already exists")
        self.entries.append(Entry(path=path, value=value, vary=vary,
                                  lo=lo, hi=hi, transform=transform))
        self._rebuild()

    def set_tie(self, path: str, tie: AffineTie | None) -> None:
        """(Re)declare an entry as an affine function of other entries.

        Tying forces ``vary=False`` (the entry leaves θ; its sources carry
        the freedom).  Locked entries cannot be retied.  ``None`` unties.
        """
        i = self._paths.get(path)
        if i is None:
            raise ValueError(f"unknown parameter {path!r}")
        e = self.entries[i]
        if e.locked:
            raise ValueError(f"cannot tie structurally locked parameter {path!r}")
        e.tie = tie
        if tie is not None:
            e.vary = False
        self._rebuild()

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
                if e.tie is None and not e.locked:
                    e.vary = vary
                    hits.append(e.path)
        self._rebuild()
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
        """Internal free vector → full physical value dict, via C·p_free + d."""
        p_free = np.array([to_physical(float(t), self.entries[i].transform)
                           for t, i in zip(theta, self._free_idx, strict=True)],
                          dtype=np.float64)
        p = self._C @ p_free + self._d if len(p_free) else self._d
        return {e.path: float(p[i]) for i, e in enumerate(self.entries)}

    def commit(self, theta: np.ndarray) -> None:
        """Write refined values back into the table (used between stages)."""
        values = self.decode(theta)
        for e in self.entries:
            e.value = values[e.path]
        self._rebuild()  # held-source contributions to d follow the new values

    def stderr_physical(self, theta: np.ndarray, stderr_internal: np.ndarray,
                        correlation: np.ndarray | None = None) -> dict[str, float]:
        """Physical esds for every free or tied parameter.

        σ²_phys = diag(C · Cov_free · Cᵀ), where Cov_free is the covariance
        of the *physical* free parameters: the internal esds chain-ruled
        through the transforms, correlated by ``correlation`` when given
        (diagonal otherwise — the pre-v0.3 behaviour).  Identity ties
        thereby report exactly the source esd; general rows get full linear
        propagation including cross terms.  Held parameters are omitted.
        """
        s = np.array([abs(dphys_dinternal(float(t), self.entries[i].transform)) * float(sd)
                      for t, sd, i in zip(theta, stderr_internal, self._free_idx, strict=True)],
                     dtype=np.float64)
        if correlation is None:
            var = self._C.multiply(self._C) @ (s * s)
        else:
            cov = np.asarray(correlation, dtype=np.float64) * np.outer(s, s)
            var = np.asarray(self._C.multiply(self._C @ cov).sum(axis=1)).ravel()
        var = np.maximum(np.asarray(var).ravel(), 0.0)
        touched = np.diff(self._C.indptr) > 0  # rows with any free source
        return {e.path: float(np.sqrt(var[i]))
                for i, e in enumerate(self.entries) if touched[i]}

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
                # coordinates too — without this, refined positions vanish at
                # the next stage's recompile (models feed compile_phase_sites)
                atom.x.value = values[f"{base}.atoms.{j}.x"]
                atom.y.value = values[f"{base}.atoms.{j}.y"]
                atom.z.value = values[f"{base}.atoms.{j}.z"]
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
