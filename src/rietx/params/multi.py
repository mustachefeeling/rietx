"""Multi-histogram parameter bookkeeping (WP-0308).

A joint refinement fits one **shared** :class:`~rietx.schemas.structure.Structure`
against several patterns, each measured on its **own**
:class:`~rietx.schemas.instrument.Instrument` (different wavelength, geometry,
resolution, background).  Physically the split is instrument-vs-sample: the
crystal (cell, coordinates, occupancies, ADPs, size/strain, extinction, texture)
is one object seen by every histogram, while the instrument and the per-pattern
scale (incident flux × illuminated volume) differ.

:class:`MultiParameterTable` owns one ordinary :class:`ParameterTable` per
histogram — so each keeps its crystal-system cell ties, Wyckoff DOFs and
transforms unchanged — and threads a single combined free vector θ through them
with a column map that folds *shared* columns onto one shared combined column
(fed to every histogram's model) while giving *per-histogram* columns their own.
The stacked residual/Jacobian in
:func:`~rietx.optimize.least_squares.run_multi_least_squares` scatters each
histogram's block through this map.

Per-histogram parameters are named with a ``hist.{h}.`` scope
(``hist.0.instrument.zero_shift``, ``hist.1.phases.0.scale``); shared parameters
keep their bare path (``phases.0.cell.a``).  A turn-on glob frees a parameter
when it matches either form, so every existing single-histogram plan
(``phases.*.scale``, ``instrument.background.*``) frees *all* histograms' copies
unchanged, while a scoped glob (``hist.1.*``) targets one.
"""

from __future__ import annotations

import fnmatch
import math
from dataclasses import dataclass, field

import numpy as np

from ..schemas.instrument import Instrument
from ..schemas.structure import Structure
from .vector import ParameterTable, _is_wavelength, check_wavelength_freedom


def _unscoped(path: str) -> str:
    """A combined path with any ``hist.{h}.`` scope removed.

    Shared paths arrive bare and come back unchanged, so this is the inverse of
    :meth:`MultiParameterTable._canonical` for exactly the cases that have one.
    """
    if path.startswith("hist."):
        return path.split(".", 2)[2]
    return path


#: Sample **size** terms and the power of λ each carries — the whole of what
#: WP-1131 found wrong with the sharing map, written as data so a new size term
#: joins it in one line.  ``lor_size`` is a FWHM coefficient and goes as λ
#: (Scherrer, ``(180/π)·K·λ/L``); ``gauss_size`` is a *variance* coefficient and
#: goes as λ².  Everything else a phase carries — strain (both), Stephens Λ(hkl),
#: extinction, texture, cell, coordinates, ADPs — is λ-free and stays shared as
#: it always was, which is what makes the strain control of WP-1131 § Finding 2
#: bit-identical across this change.
SIZE_LAMBDA_POWER = {"lor_size": 1.0, "gauss_size": 2.0}


def _longest_wavelength(instrument: Instrument) -> float | None:
    """The source's longest declared line (Å), or ``None`` if it has none.

    A **deliberate second spelling** of
    :func:`~rietx.optimize.least_squares._longest_line_wavelength`, not an
    independent choice of "which λ": that one reads a *compiled* model and this
    one a schema object, and the sharing map has to answer before anything is
    compiled.  The two are held together by
    ``tests/test_multi_histogram.py::test_the_two_wavelength_selectors_agree``
    rather than by this comment — the same idiom
    ``params.vector._SIZE_CAP_SCHERRER_K`` uses against ``caglioti.SCHERRER_K``.

    **Longest** for the reason that function gives: every size surface in the
    package attributes a coefficient to the longest line, so a Kα2 offset can
    never move an attribution on its own.
    """
    lams = [line.wavelength.value for line in instrument.source.lines
            if line.wavelength.value > 0.0]
    return max(lams) if lams else None


def size_value_scales(structure: Structure, instruments: list[Instrument],
                      sharing: "SharingMap") -> list[dict[str, float]]:
    """Per-histogram factors that turn a shared size column into one specimen.

    One entry per histogram, each mapping a size path to the factor between
    **that histogram's** coefficient and the shared column's, which is carried
    in histogram 0's wavelength (so histogram 0's map is empty and its numbers
    are unchanged, and a reader of ``phases.0.lor_size`` is reading the
    coefficient at λ₀).

    **The physics, and why the Scherrer constant is not in it** (WP-1131).  A
    size coefficient is (180/π)·K·λ/L, so for one crystallite size L two
    histograms need coefficients in the ratio λ₂/λ₁ — K and the degree
    conversion cancel, which is why sharing a size across wavelengths is
    provably wrong whatever convention K follows, and why the fix needs no
    convention at all.  Microstrain is 2·(Δd/d)·tanθ with no λ in it, so it
    stays one number and is not listed here.

    Empty maps (⇒ the pre-WP-1131 behaviour, bit for bit) in three cases, and
    each is the honest answer rather than a fallback: **one** histogram, where
    there is nothing to normalise; a source with **no declared line**, where
    there is no λ to normalise by; and equal wavelengths, where every factor is
    exactly 1.0 — which is every joint fit that existed before this change.
    """
    lams = [_longest_wavelength(ins) for ins in instruments]
    if len(lams) < 2 or any(lam is None for lam in lams):
        return [{} for _ in instruments]
    ref = lams[0]
    scales: list[dict[str, float]] = []
    for lam in lams:
        ratio = lam / ref
        one: dict[str, float] = {}
        if ratio != 1.0:
            for ip in range(len(structure.phases)):
                for term, power in SIZE_LAMBDA_POWER.items():
                    path = f"phases.{ip}.{term}"
                    if sharing.is_shared(path):
                        one[path] = ratio ** power
        scales.append(one)
    return scales


@dataclass
class SharingMap:
    """Which parameter paths are shared across histograms vs. per-histogram.

    Default rule: a path is **per-histogram** iff it starts with ``instrument.``
    or ends with ``.scale``; everything else (cell, coordinates, occupancies,
    ADPs, size/strain, extinction, preferred orientation) is **shared** — one
    specimen, one crystal.  ``per_histogram`` / ``shared`` are override glob
    lists (fnmatch on the bare unscoped path, no brackets), checked in that
    order before the default, so a caller can e.g. give each histogram its own
    preferred-orientation axis (``per_histogram=["phases.*.preferred_orientation.*"]``)
    or tie a sample-displacement across mounts.
    """

    per_histogram: list[str] = field(default_factory=list)
    shared: list[str] = field(default_factory=list)

    def is_shared(self, path: str) -> bool:
        if any(fnmatch.fnmatchcase(path, g) for g in self.per_histogram):
            return False
        if any(fnmatch.fnmatchcase(path, g) for g in self.shared):
            return True
        return not (path.startswith("instrument.") or path.endswith(".scale"))


class MultiParameterTable:
    """One :class:`ParameterTable` per histogram + a shared/per-histogram θ map."""

    def __init__(self, structure: Structure, instruments: list[Instrument], *,
                 sharing: SharingMap | None = None):
        if len(instruments) < 1:
            raise ValueError("need at least one instrument")
        self.sharing = sharing or SharingMap()
        # a private structure copy per histogram: shared parameters are written
        # identically into every copy at each commit; only the per-histogram
        # scale (and any per-histogram override) diverges.
        self.structures: list[Structure] = [structure.model_copy(deep=True)
                                             for _ in instruments]
        self.instruments: list[Instrument] = [ins.model_copy(deep=True)
                                              for ins in instruments]
        # ``joint=True``: a sub-table sees one instrument, so it would always
        # read the single-histogram case and refuse a wavelength this fit is
        # entitled to free.  The count is made once, over all of them, in
        # :meth:`_rebuild_columns`.
        # WP-1131: a *size* coefficient is not one number across wavelengths,
        # so before any table is built each copy is put into its own
        # histogram's units and the table is told the factor.  Empty maps
        # everywhere (one histogram, equal wavelengths, or a source with no
        # declared line) leave every table exactly as it was.
        self.value_scales = size_value_scales(structure, self.instruments,
                                              self.sharing)
        for struct, scale in zip(self.structures, self.value_scales, strict=True):
            for path, factor in scale.items():
                _, ip, term = path.split(".")
                param = getattr(struct.phases[int(ip)], term)
                # the declared window travels with the value: it is a limit on
                # the *specimen* quantity, so in this histogram's units it is
                # the same factor away.  Scaling the value alone would trip
                # ``Parameter``'s own min<=value<=max validator on any size
                # term carrying a finite bound, with a message that says
                # nothing about wavelengths -- and would leave the histograms
                # disagreeing about a window the caller stated once.
                lo, hi = param.min * factor, param.max * factor
                param.min, param.max = -math.inf, math.inf
                param.value = param.value * factor
                param.min, param.max = lo, hi
        self.tables: list[ParameterTable] = [
            ParameterTable(s, ins, joint=True)
            for s, ins in zip(self.structures, self.instruments, strict=True)]
        for table, scale in zip(self.tables, self.value_scales, strict=True):
            if scale:
                table.apply_value_scale(scale)
        self._rebuild_columns()

    @property
    def n_histograms(self) -> int:
        return len(self.tables)

    # -- vary control --------------------------------------------------
    def _canonical(self, h: int, path: str) -> str:
        """The scoped name of ``path`` in histogram ``h`` (bare if shared)."""
        return path if self.sharing.is_shared(path) else f"hist.{h}.{path}"

    def set_vary(self, path_globs: list[str], vary: bool) -> list[str]:
        """Free/fix by glob across every histogram; returns scoped hits.

        A glob matches an entry when it matches either the scoped canonical name
        or the bare path, so single-histogram plans keep working verbatim.
        """
        freed: list[str] = []
        for h, table in enumerate(self.tables):
            matched = []
            for e in table.entries:
                if e.tie is not None or e.locked:
                    continue
                canon = self._canonical(h, e.path)
                if any(fnmatch.fnmatchcase(canon, g)
                       or fnmatch.fnmatchcase(e.path, g) for g in path_globs):
                    matched.append(e.path)
            if matched:
                for p in table.set_vary(matched, vary):
                    freed.append(self._canonical(h, p))
        self._rebuild_columns()
        return freed

    def seed_softplus(self, scoped_paths: list[str], value: float) -> list[str]:
        """Lift softplus params off the zero floor (per histogram); see the
        single-histogram :meth:`ParameterTable.seed_softplus`."""
        seeded: list[str] = []
        for h, table in enumerate(self.tables):
            want = [self._unscope(h, p) for p in scoped_paths
                    if self._owner(p) in (None, h)]
            for p in table.seed_softplus([w for w in want if w is not None], value):
                seeded.append(self._canonical(h, p))
        if seeded:
            self._rebuild_columns()
        return seeded

    # -- combined column layout ----------------------------------------
    def _rebuild_columns(self) -> None:
        """Recompute the shared/per-histogram combined column layout.

        Shared free columns come first (in histogram 0's order, and asserted
        identical across histograms — same structure copy, same globs), then
        each histogram's per-histogram free columns in turn.  ``_col_map[h][c]``
        is the combined index of histogram ``h``'s c-th free column.
        """
        shared_order: list[str] = []
        shared_seen: set[str] = set()
        per_hist_paths: list[list[str]] = [[] for _ in self.tables]
        shared_sets: list[set[str]] = []
        for h, table in enumerate(self.tables):
            sset: set[str] = set()
            for p in table.free_paths:
                if self.sharing.is_shared(p):
                    sset.add(p)
                    if p not in shared_seen:
                        shared_seen.add(p)
                        shared_order.append(p)
                else:
                    per_hist_paths[h].append(p)
            shared_sets.append(sset)
        for h, sset in enumerate(shared_sets):
            if sset != shared_seen:
                missing = sorted(shared_seen - sset)
                extra = sorted(sset - shared_seen)
                raise ValueError(
                    f"histogram {h} disagrees on the shared free set "
                    f"(missing {missing[:3]}, extra {extra[:3]}); shared "
                    "parameters must be freed identically in every histogram")

        shared_index = {p: k for k, p in enumerate(shared_order)}
        combined_paths = list(shared_order)
        per_hist_index: list[dict[str, int]] = [{} for _ in self.tables]
        for h in range(len(self.tables)):
            for p in per_hist_paths[h]:
                per_hist_index[h][p] = len(combined_paths)
                combined_paths.append(f"hist.{h}.{p}")

        n = len(combined_paths)
        col_map: list[np.ndarray] = []
        x0 = np.zeros(n, dtype=np.float64)
        lo = np.full(n, -np.inf, dtype=np.float64)
        hi = np.full(n, np.inf, dtype=np.float64)
        for h, table in enumerate(self.tables):
            free = table.free_paths
            idx = np.array(
                [shared_index[p] if self.sharing.is_shared(p) else per_hist_index[h][p]
                 for p in free], dtype=np.int64)
            col_map.append(idx)
            xh = table.x0()
            loh, hih = table.bounds()
            # shared columns get identical values from each histogram (harmless
            # overwrite); per-histogram columns are written once.
            x0[idx] = xh
            # bounds are **intersected**, not overwritten.  A shared column has
            # to satisfy every histogram's bound, and since WP-1131 the
            # histograms can genuinely disagree about one: a size cap is a
            # physical limit on each histogram's own coefficient, which the
            # value scale divides by a different factor per histogram.  Identity
            # wherever they agree — which is every bound the three per-stage
            # freezes set, since each is made to agree deliberately — so this is
            # bit-identical on every joint fit that predates the scaling.
            lo[idx] = np.maximum(lo[idx], loh)
            hi[idx] = np.minimum(hi[idx], hih)

        # The wavelength count, made where the whole set is visible.  A
        # wavelength is per-histogram under the default sharing rule (it starts
        # with ``instrument.``), so the scoped ``hist.h.…`` name is what a user
        # reads and what the refusal must name — the check tests the *unscoped*
        # tail and reports the scoped path.  Asked after every column rebuild
        # rather than only at construction, because a staged plan frees its
        # globs one stage at a time and every :meth:`set_vary` ends here.
        n_wavelengths = sum(1 for t in self.tables for e in t.entries
                            if _is_wavelength(e.path))
        # ``SharingMap`` decides sharing per *path*, not per (path, histogram),
        # so "the cell is shared with a held-λ histogram" collapses to "the cell
        # is shared at all" — which is the strongest form this map can express,
        # and it is the right one: with a per-histogram cell *every* histogram
        # has its own, so no free λ has anything to be measured against.
        cell_shared = all(
            self.sharing.is_shared(e.path) for t in self.tables
            for e in t.entries if ".cell." in e.path)
        check_wavelength_freedom(
            [p for p in combined_paths if _is_wavelength(_unscoped(p))],
            n_wavelengths, len(self.tables), cell_shared=cell_shared)

        self.shared_paths = shared_order
        self.per_hist_paths = per_hist_paths
        self._combined_paths = combined_paths
        self._col_map = col_map
        self._x0 = x0
        self._lo = lo
        self._hi = hi
        self.n_shared = len(shared_order)

    def refresh_bounds(self) -> None:
        """Re-read the sub-tables' bounds after a per-stage freeze changed them.

        The constructor's "harmless overwrite" of a shared column holds only
        while every histogram reports the same bound for it, so a caller that
        freezes cell windows must freeze the **same** set on every sub-table —
        see ``optimize.least_squares._freeze_cell_windows_multi``, which decides
        a phase is invisible only when it is invisible in all of them.
        """
        self._lo.fill(-np.inf)
        self._hi.fill(np.inf)
        for h, table in enumerate(self.tables):
            loh, hih = table.bounds()
            idx = self._col_map[h]
            self._lo[idx] = np.maximum(self._lo[idx], loh)
            self._hi[idx] = np.minimum(self._hi[idx], hih)

    # -- optimiser interface -------------------------------------------
    @property
    def free_paths(self) -> list[str]:
        return list(self._combined_paths)

    def x0(self) -> np.ndarray:
        return self._x0.copy()

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        return self._lo.copy(), self._hi.copy()

    def col_map(self, h: int) -> np.ndarray:
        return self._col_map[h]

    def split(self, theta: np.ndarray) -> list[np.ndarray]:
        """Gather the per-histogram internal free vectors from combined θ."""
        return [theta[self._col_map[h]] for h in range(len(self.tables))]

    def decode(self, theta: np.ndarray) -> list[dict[str, float]]:
        thetas = self.split(theta)
        return [self.tables[h].decode(thetas[h]) for h in range(len(self.tables))]

    def commit(self, theta: np.ndarray) -> None:
        thetas = self.split(theta)
        for h, table in enumerate(self.tables):
            table.commit(thetas[h])

    def apply_to_models(self) -> None:
        for h, table in enumerate(self.tables):
            table.apply_to_models(self.structures[h], self.instruments[h])

    # -- helpers used by esd assembly ----------------------------------
    def _owner(self, scoped: str) -> int | None:
        """Histogram index of a scoped per-histogram path, or None if shared."""
        if scoped.startswith("hist."):
            return int(scoped.split(".", 2)[1])
        return None

    def _unscope(self, h: int, scoped: str) -> str | None:
        """Bare path of ``scoped`` as seen by histogram ``h`` (None if it
        belongs to another histogram)."""
        owner = self._owner(scoped)
        if owner is None:
            return scoped
        if owner != h:
            return None
        return scoped.split(".", 2)[2]
