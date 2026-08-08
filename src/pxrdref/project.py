"""The project container: one durable thing a session can point at.

A project is a **directory**, not an archive::

    my_sample.pxrd/
        project.json        settings + the data reference (schemas/project.py)
        11BM_NAC.fxye       the pattern file, byte-for-byte as measured
        history.jsonl       the refinement DAG, append-only
        live/               event streams for `pxrdref watch`
        exports/            CIFs, reflection and QPA tables

A directory because the history log's crash-safety story is *append-only writes
by one writer*, which an archive cannot keep: zipping would force a
rewrite-on-save and lose exactly the property that makes a JSONL log recoverable
and tailable while a fit runs.

**The pattern is copied verbatim.**  Not re-serialised, not normalised: the
readers derive the weights from the file's own esd column when it has one and
never override it (CLAUDE.md, Weights), so the bytes are the contract.  What
makes them trustworthy on re-open is :class:`~pxrdref.schemas.project.DataRef` —
a digest of the bytes, a digest of the *parsed* arrays, and the reader call that
produced them.

**Saving is about settings, not durability.**  Every verb that changes the model
commits a history node the moment it runs, so the work is on disk whether or not
anyone calls :meth:`Project.save`.  What ``save`` persists is the half of a
session that nothing else owns: the selected plan and mode, the excluded regions,
the UI's own keys.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .history.store import fingerprint
from .history.tree import RefinementTree
from .io.readers import identify_format, read_pattern, reader_options_for
from .refine import _VERSION, Refinement
from .schemas.common import Diagnostic, Mode
from .schemas.history import NodeAction
from .schemas.instrument import Instrument
from .schemas.pattern import PatternData
from .schemas.plan import PlanSpec
from .schemas.project import PROJECT_FORMAT_VERSION, DataRef, ProjectDoc
from .schemas.structure import Structure

#: Conventional directory suffix, so a file picker can recognise a project.
#: Not enforced — ``create`` writes wherever it is told — because silently
#: renaming a path the caller chose is worse than an unconventional name.
PROJECT_SUFFIX = ".pxrd"

PROJECT_JSON = "project.json"
HISTORY_FILE = "history.jsonl"
LIVE_DIR = "live"
EXPORTS_DIR = "exports"


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Project:
    """An openable, savable refinement session on disk.

    ``project.refinement`` is the working state (positioned at the history head)
    and ``project.data`` the pattern it is fitted against; :meth:`fit` and
    :meth:`run_stage` are thin wrappers that supply both plus the project's own
    settings, so a caller holds one object instead of four.
    """

    def __init__(self, path: str | Path, doc: ProjectDoc, data: PatternData,
                 refinement: Refinement,
                 data_diagnostics: list[Diagnostic] | None = None):
        self.path = Path(path)
        self.doc = doc
        self.data = data
        self.refinement = refinement
        #: what the reader repaired or assumed on the *last* read of the pattern
        #: — a reversed scan, a dropped duplicate, an option that did not apply.
        #: In memory only, and deliberately **not** a ``project.json`` field:
        #: they are a deterministic function of bytes + reader + options, all
        #: three of which ``DataRef`` already records, so storing them would be
        #: a second authority.  Putting the repairs in the reader also puts them
        #: under the fingerprint check, so changing one later fires the existing
        #: "a reader change, not a corrupt project" message.
        self.data_diagnostics: list[Diagnostic] = list(data_diagnostics or [])

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    @classmethod
    def create(cls, path: str | Path, *, pattern: str | Path,
               structure: Structure, instrument: Instrument,
               mode: Mode = "rietveld",
               plan: Any = None,
               two_theta_limits: tuple[float, float] | None = None,
               excluded_regions: list[tuple[float, float]] | None = None,
               reader_options: dict[str, Any] | None = None,
               ui: dict[str, Any] | None = None,
               backend: str = "numpy", solver: str = "trf") -> "Project":
        """Create a project directory around a pattern file and a model.

        ``pattern`` is a **path**, not a :class:`PatternData`: a project's
        pattern is the file as measured, and copying the bytes is what keeps the
        reader's esd-column semantics intact.  A caller holding data in memory
        writes it out first, and thereby chooses the format its esds live in.

        ``reader_options`` are :data:`~pxrdref.io.readers.READER_OPTIONS` keys —
        today ``block``, which names a pdCIF data block (several certification
        files carry a measured *and* a calculated one).  The **effective** ones
        are recorded, so re-opening reproduces the reader *call* rather than
        merely re-reading the bytes.
        """
        root = Path(path)
        src = Path(pattern)
        if (root / PROJECT_JSON).exists():
            raise FileExistsError(
                f"{root} already holds a {PROJECT_JSON}; open it instead of "
                "creating over it")
        if not src.is_file():
            raise FileNotFoundError(f"pattern file not found: {src}")
        root.mkdir(parents=True, exist_ok=True)

        copied = root / src.name
        if copied.resolve() != src.resolve():
            shutil.copyfile(src, copied)  # bytes, not a re-serialisation

        fmt = identify_format(copied)
        notes: list[Diagnostic] = []
        options = reader_options_for(fmt, reader_options or {}, diagnostics=notes)
        data = read_pattern(copied, diagnostics=notes, **options)
        if excluded_regions:
            data.excluded_regions = [tuple(r) for r in excluded_regions]

        plan_spec = _as_plan_spec(plan)
        doc = ProjectDoc(
            package_version=_VERSION,
            created_utc=_utcnow(),
            updated_utc=_utcnow(),
            patterns=[_data_ref(copied, data, fmt.name, options)],
            mode=mode,
            plan=plan_spec,
            two_theta_limits=two_theta_limits,
            excluded_regions=list(data.excluded_regions),
            history_file=HISTORY_FILE,
            ui=dict(ui or {}),
        )

        tree = RefinementTree.for_data(
            data, path=root / doc.history_file,
            plan=None if plan_spec is None else plan_spec.to_plan(),
            package_version=_VERSION)
        ref = Refinement(structure, instrument, backend=backend, solver=solver,
                         history=tree)
        # The root node is the as-created model, so "undo everything" has a
        # target from the first click.  Built from ``snapshot()`` rather than
        # hand-assembled: that is what a plain ``Refinement.fit`` records, µR
        # resolution included, and a project must not record something else.
        tree.add(parents=[], action=NodeAction(kind="root"), state=ref.snapshot())
        ref.checkout("head")  # point the working tree at it (and persist the ref)

        (root / LIVE_DIR).mkdir(exist_ok=True)
        (root / EXPORTS_DIR).mkdir(exist_ok=True)
        project = cls(root, doc, data, ref, notes)
        project.save()
        return project

    @classmethod
    def open(cls, path: str | Path, *, backend: str = "numpy",
             solver: str = "trf") -> "Project":
        """Open an existing project, resuming at the history head.

        Every binding is re-checked rather than assumed, and each failure raises
        with its own message because each has a different cause: a missing
        pattern file, bytes that changed under the project, a *reader* that now
        parses the same bytes differently, or a history tree recorded against
        another pattern entirely.  ``refine.replay`` already refuses that last
        one; a container that silently rebound a tree to different data would be
        the confident-wrong-singleton failure one level up.
        """
        root = Path(path)
        if root.is_file() and root.name == PROJECT_JSON:
            root = root.parent
        doc_path = root / PROJECT_JSON
        if not doc_path.is_file():
            raise FileNotFoundError(f"not a project directory (no {PROJECT_JSON}): {root}")
        doc = ProjectDoc.model_validate_json(doc_path.read_text(encoding="utf-8"))

        major = doc.format_version.split(".")[0]
        if major != PROJECT_FORMAT_VERSION.split(".")[0]:
            raise ValueError(
                f"{doc_path}: project format {doc.format_version} was written by "
                f"another version of pxrd-refine (this one reads "
                f"{PROJECT_FORMAT_VERSION}); it was saved by package version "
                f"{doc.package_version or 'unknown'}")
        if len(doc.patterns) != 1:
            raise ValueError(
                f"{doc_path}: this version opens single-pattern projects only, "
                f"found {len(doc.patterns)}; joint multi-histogram projects are "
                "a later milestone (the list is the seam, not a feature yet)")

        ref_doc = doc.patterns[0]
        pattern_path = root / ref_doc.filename
        if not pattern_path.is_file():
            raise FileNotFoundError(
                f"{doc_path}: the project's pattern file {ref_doc.filename} is "
                "missing from the project directory")
        actual_sha = _sha256(pattern_path)
        if actual_sha != ref_doc.sha256:
            raise ValueError(
                f"{pattern_path}: file has changed since the project was created "
                f"(sha256 {actual_sha[:8]}, recorded {ref_doc.sha256[:8]}); the "
                "history was fitted against the recorded bytes")

        notes: list[Diagnostic] = []
        data = read_pattern(pattern_path, diagnostics=notes,
                            **_reader_options(ref_doc))
        actual_fp = fingerprint(data.two_theta, data.intensity)
        if actual_fp != ref_doc.fingerprint:
            raise ValueError(
                f"{pattern_path}: the bytes match but this version parses them "
                f"differently (fingerprint {actual_fp[:8]}, recorded "
                f"{ref_doc.fingerprint[:8]}) — a reader change, not a corrupt "
                "project; the recorded reader was "
                f"{ref_doc.reader!r} with options {ref_doc.options}")
        data.excluded_regions = [tuple(r) for r in doc.excluded_regions]

        history_path = root / doc.history_file
        if not history_path.is_file():
            raise FileNotFoundError(
                f"{doc_path}: history log {doc.history_file} is missing; it holds "
                "the model state (project.json holds only the settings)")
        tree = RefinementTree.load(history_path)
        if tree.header.data_fingerprint and tree.header.data_fingerprint != actual_fp:
            raise ValueError(
                f"{history_path}: this history was recorded against a different "
                f"pattern (fingerprint {tree.header.data_fingerprint[:8]}, data "
                f"reads {actual_fp[:8]})")
        if tree.head is None:
            raise ValueError(
                f"{history_path}: no node to resume from; the log has no records")

        ref = Refinement.from_node(tree, "head", backend=backend, solver=solver)
        return cls(root, doc, data, ref, notes)

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def save(self) -> None:
        """Rewrite ``project.json``.  Never touches the pattern or the JSONL."""
        self.doc.updated_utc = _utcnow()
        target = self.path / PROJECT_JSON
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(self.doc.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, target)  # a crash leaves the previous doc, not half of one

    # ------------------------------------------------------------------
    # the session
    # ------------------------------------------------------------------
    @property
    def history(self) -> RefinementTree:
        return self.refinement._require_history()

    @property
    def live_dir(self) -> Path:
        """Where an event stream belongs, so ``pxrdref watch`` can find it."""
        return self.path / LIVE_DIR

    @property
    def exports_dir(self) -> Path:
        return self.path / EXPORTS_DIR

    @property
    def data_ref(self) -> DataRef:
        return self.doc.patterns[0]

    def set_excluded_regions(self, regions: list[tuple[float, float]]) -> None:
        """Mask 2θ regions out of the residual, in the document *and* the data.

        One verb because the two must not disagree, and it does not rebind the
        history: the fingerprint is over the measured arrays, so excluding a
        region leaves every node replayable — against a residual that no longer
        includes those points, which is why the regions are recorded here.
        """
        self.doc.excluded_regions = [tuple(r) for r in regions]
        self.data.excluded_regions = list(self.doc.excluded_regions)

    def fitted_mask(self):
        """True per measured channel for the points the *next* run will fit.

        ``compile_model``'s first act, asked of a project rather than of a
        pattern: the exclusion mask intersected with ``two_theta_limits``.  It
        exists because a picture of a masked pattern needs to draw both halves —
        the surviving channels *and* the ones the protocol removed — and every
        caller that open-coded the intersection was one edit away from
        disagreeing with the residual about what is in it (WP-1033).

        Not a duplicate of the forward model's line: that one takes a
        :class:`PatternData` and a limits tuple, which is the level a fit runs
        at, and it is pinned to this one by asserting the fitted channel count
        against ``len(result.two_theta)``.

        The arithmetic itself is :func:`fitted_mask`, so a pattern that is *not*
        this project's one — a series member (WP-1016), run under this project's
        protocol but held outside its single-pattern document — asks the same
        question of the same function rather than open-coding the intersection a
        second time.
        """
        return fitted_mask(self.data, self.doc.two_theta_limits)

    def parameters(self, **kw):
        """:meth:`Refinement.parameters` answered for *this project's* mode.

        The refinement's carried mode is what its last stage ran in, and before
        the first run it is the ``"rietveld"`` default — while the document says
        what the next run will use.  Without this, a Le Bail project's
        ``.atoms.`` rows come back with ``mode_fixed=False`` and a client renders
        the mandatory dummy atom's ``biso`` as editable, which is exactly the
        trap that flag was added to close.
        """
        kw.setdefault("mode", self.doc.mode)
        return self.refinement.parameters(**kw)

    def fit(self, **kw):
        """:meth:`Refinement.fit` on this project's data and settings."""
        kw.setdefault("mode", self.doc.mode)
        kw.setdefault("two_theta_limits", self.doc.two_theta_limits)
        if self.doc.plan is not None:
            kw.setdefault("plan", self.doc.plan.to_plan())
        return self.refinement.fit(self.data, **kw)

    def run_stage(self, stage, **kw):
        """:meth:`Refinement.run_stage` on this project's data and settings.

        ``mode`` is passed explicitly rather than left to the refinement's
        carried value: before the first run that value is the ``"rietveld"``
        default, and a Le Bail project driven one stage at a time would otherwise
        silently start in the wrong intensity model.
        """
        kw.setdefault("mode", self.doc.mode)
        kw.setdefault("two_theta_limits", self.doc.two_theta_limits)
        return self.refinement.run_stage(self.data, stage, **kw)

    def __repr__(self) -> str:  # pragma: no cover - convenience
        n = len(self.history) if self.refinement.history is not None else 0
        return (f"Project({self.path.name!r}, {self.data_ref.filename!r}, "
                f"{n} history nodes, at {self.refinement._head_id})")


# ----------------------------------------------------------------------
def fitted_mask(data: PatternData,
                two_theta_limits: tuple[float, float] | None):
    """Which of ``data``'s channels a run under these limits would fit.

    :meth:`Project.fitted_mask`'s arithmetic, taking the pattern explicitly so
    the *same* authority answers for a pattern the project does not own.  Public
    because it has a second caller (the GUI's series window) and because a third
    open-coding of ``in_range_mask() & limits`` is the drift WP-1033 measured.
    """
    import numpy as np

    mask = data.in_range_mask()
    if two_theta_limits is not None:
        lo, hi = two_theta_limits
        tt = data.tt()
        mask &= (tt >= lo) & (tt <= hi)
    return np.asarray(mask, dtype=bool)


def _as_plan_spec(plan: Any) -> PlanSpec | None:
    """A ``PlanSpec`` from a preset name, a ``RefinementPlan`` or a spec."""
    if plan is None or isinstance(plan, PlanSpec):
        return plan
    if isinstance(plan, str):
        from .strategy.staged import PLAN_PRESETS

        try:
            plan = PLAN_PRESETS[plan]()
        except KeyError:
            raise ValueError(f"unknown plan preset {plan!r}; available: "
                             f"{sorted(PLAN_PRESETS)}") from None
    return PlanSpec.from_plan(plan)


def _data_ref(path: Path, data: PatternData, reader: str,
              options: dict[str, Any]) -> DataRef:
    tt = data.two_theta
    return DataRef(
        filename=path.name,
        sha256=_sha256(path),
        fingerprint=fingerprint(data.two_theta, data.intensity),
        reader=reader,
        # the **effective** options — the ones the parse actually used, which
        # are what reopening has to replay.  A requested-but-ignored key
        # recorded here would change nothing and mislead.  ``str`` because
        # ``DataRef.options`` is dict[str, str]; ``reader_options_for`` coerces
        # them back on the way in.
        options={k: str(v) for k, v in options.items()},
        n_points=len(tt),
        two_theta_range=(tt[0], tt[-1]),
        has_sigma=data.sigma is not None,
    )


def _reader_options(ref: DataRef) -> dict[str, str]:
    """The recorded reader keywords, as ``read_pattern`` kwargs."""
    return {k: v for k, v in ref.options.items() if v is not None}
