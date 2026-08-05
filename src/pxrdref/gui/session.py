"""The GUI's session model — every verb, and not one line of HTTP (WP-1008).

``server.py`` is transport: it parses a path, calls a method here, and serialises
what comes back.  Everything a client can *do* is a plain method on
:class:`GuiSession`, which is what makes the transport swappable — a Tauri
command handler, a notebook driver or a test calling the verbs directly all get
the same surface, and none of them needs a socket.

Three rules shape it.

**One project per session, and its head is the working state.**  The project
container (WP-1005) already decided that ``project.json`` holds the settings and
``history.jsonl`` holds the model, so this object adds no third store: a verb
that changes a parameter commits a history node, a verb that changes a setting
rewrites ``project.json`` immediately.  A GUI therefore has nothing to warn about
on close — which is a property to preserve, not a coincidence, so every settings
verb here persists rather than deferring to :meth:`Project.save`.

**Mutating verbs refuse while a run is in flight.**  Not politeness:
frozen-per-stage discreteness (CLAUDE.md) says the hkl list, the symmetry-op
subsets and the window ranges are computed at stage compile and never change
during a least-squares run.  A ``PATCH /api/params`` mid-stage would edit the
models the compiled state was derived from.  Enforcing it at the session
boundary makes that structurally impossible rather than a thing to remember, and
:class:`GuiError` carries the 409 the transport reports.

**The run is watched through events, not by polling state.**  One worker thread,
one :class:`~pxrdref.optimize.cancel.CancelToken`, and a seq-numbered ring
buffer of the engine's own event dicts with a ``Condition`` for followers.  The
buffer is a *transport* of the same stream that lands in
``<project>/live/events.jsonl``, so ``pxrdref watch`` and the GUI are two views
of one log rather than two logs.

The one place this session adds a frame the engine does not emit is the **run
state**: a fit that raises emits no ``fit_end``, so a follower watching only
engine events would wait forever on a failed run.  ``EventKind`` is a closed set
and WP-1006 deliberately declined to add a kind for a guess, so the state frame
is *not* an event — it travels beside them (a separate SSE frame type, a separate
key in the poll fallback) and is never written to the log.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import deque
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from ..capabilities import capabilities as _capabilities
from ..history.events import EventStream
from ..optimize.cancel import CancelToken, RefinementCancelled
from ..project import Project
from ..refine import _VERSION
from ..report.apply import api_call, describe_action, refusal, stage_for
from ..schemas.instrument import Instrument
from ..schemas.plan import PlanSpec, StageSpec
from ..schemas.structure import Structure
from ..strategy.staged import PLAN_PRESETS, resolve_plan
from ..viz.compare import decimation_index
from . import series as series_mod
from . import symmetry
from .imports import (
    UPLOAD_KINDS,
    UploadRefused,
    UploadStore,
    instrument_from_preset,
    preview_cif,
    preview_instrument,
    preview_pattern,
    scrub,
    unknown_species,
)

#: ``idle`` → ``running`` → (``cancelling``) → ``idle``.  There is no ``failed``
#: state: a failure ends the run, and *what* happened is on the run record.
RunState = Literal["idle", "running", "cancelling"]

#: Events kept for replay.  A staged fit on a real pattern emits one ``eval``
#: per residual evaluation — thousands — so the ring is a window, not an
#: archive; ``events_since`` reports its oldest seq so a client that fell behind
#: can tell it missed some instead of silently renumbering.  The log on disk is
#: the archive.
EVENT_RING = 4096

#: Where ``/api/recent`` is remembered.  Overridable so tests (and a sandboxed
#: build) never touch a real home directory.
STATE_DIR_ENV = "PXRDREF_STATE_DIR"

_MAX_RECENT = 12

#: Routes whose *shape* is settled here but whose behaviour belongs to a later
#: work package.  Declared rather than omitted so the frontend scaffold can be
#: written against the final path set, and answered with the WP that will fill
#: them in — a 404 saying "not yet, here is who" is a design document a client
#: can read at runtime.  Empty since WP-1027 filled in the peak/index family;
#: the mechanism stays for the next reserved surface.
RESERVED_ROUTES: dict[tuple[str, str], str] = {}

_EXPORT_DEFAULTS = {
    "cif": "refinement.cif",
    "reflections": "reflections.csv",
    "qpa": "qpa.csv",
    "html": "fit.html",
    "result_json": "result.json",
}


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class GuiError(Exception):
    """A verb refused, carrying what the transport should report.

    Same grammar as :class:`~pxrdref.schemas.diagnostics.Diagnostic` and the
    agent envelope (WP-0602): a ``code`` to branch on, a message for a human,
    and ``where`` naming the paths at fault.  The HTTP status lives here rather
    than in the router because the reason is what decides it — a run in flight
    is a 409 wherever it is reported.
    """

    def __init__(self, message: str, *, code: str = "INVALID_REQUEST",
                 status: int = 400, where: list[str] | None = None,
                 details: list[dict] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.where = list(where or [])
        #: per-item failures, as ``AgentError.details`` does it — a text document
        #: apply reports every bad line at once, because fixing them one HTTP
        #: round trip at a time is not an editing experience
        self.details = list(details or [])

    def payload(self) -> dict:
        return {"error": {"code": self.code, "message": self.message,
                          "where": self.where, "details": self.details}}


class GuiSession:
    """One project, one run at a time, and every GUI verb as a method.

    ``project`` may be ``None``: the app opens before a project exists, and the
    verbs that need one raise ``NO_PROJECT`` rather than pretending.
    """

    def __init__(self, project: Project | None = None, *, backend: str = "numpy",
                 solver: str = "trf", state_dir: str | Path | None = None) -> None:
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self.project = project
        self.backend = backend
        self.solver = solver
        self.state_dir = Path(state_dir) if state_dir is not None else Path(
            os.environ.get(STATE_DIR_ENV) or Path.home() / ".pxrdref")
        #: staged uploads (WP-1014).  Session-scoped on purpose: a token is only
        #: meaningful to the process that issued it, and the directory goes away
        #: with :meth:`close` rather than accumulating in a temp dir.
        self.uploads = UploadStore()
        self.closed = False

        self._state: RunState = "idle"
        self._cancel: CancelToken | None = None
        self._worker: threading.Thread | None = None
        self._events: deque[dict] = deque(maxlen=EVENT_RING)
        self._seq = 0
        self._n_eval = 0
        self._run: dict = _idle_run()
        #: the last completed indexing run's answer.  Session-scoped like
        #: ``refinement.result_``: peaks.json is the durable artifact, an
        #: IndexingResult is a computation over it.
        self._index_result = None
        #: ``{"screen": ExtinctionScreen, "candidate": int}`` — the last
        #: extinction screen, valid only against the ``_index_result`` it was
        #: asked of (a new indexing run renumbers the candidates, so it clears
        #: this).  WP-1025 through WP-1027's surface.
        self._extinction = None
        #: ``(cache key, PeakEditor)`` — the editor holds the lazily built
        #: Detection; the key is everything a detection depends on
        self._peak_ed: tuple[tuple, Any] | None = None
        #: the staged series and its chain settings (WP-1016).  Session-scoped
        #: because its patterns are upload tokens, which die with ``close`` —
        #: a *persisted* series would need a document, which is WP-1003's to
        #: decide rather than this WP's to add.
        self._series = series_mod.SeriesSetup()
        #: the last completed series run: the ``SequentialRefinement`` (which
        #: holds each pattern's full result and its own history tree) beside the
        #: serializable ``SeriesResult``.  One object, so "is there an answer"
        #: cannot be two answers.
        self._series_run: dict | None = None
        if project is not None:
            self._remember(project.path)

    # ------------------------------------------------------------------
    # introspection
    # ------------------------------------------------------------------
    def capabilities(self) -> dict:
        """:func:`pxrdref.capabilities`, verbatim — the client's one guess-free call."""
        return _capabilities().model_dump(mode="json")

    def version(self) -> dict:
        return {"package_version": _VERSION, "pid": os.getpid(),
                "backend": self.backend, "solver": self.solver,
                "project": None if self.project is None else str(self.project.path)}

    # ------------------------------------------------------------------
    # uploads (WP-1014)
    # ------------------------------------------------------------------
    def upload(self, kind: str, *, data: bytes | None = None, filename: str = "",
               token: str = "", options: dict | None = None) -> dict:
        """Stage a file (or re-read one already staged) and describe it.

        The two argument shapes are the two halves of one flow: **bytes plus a
        filename** stage a new file, **a token** re-reads one with different
        options — which is what the aniso checkbox and the pdCIF block picker
        need, since flipping either must not mean re-uploading a file the server
        already has.

        Not idle-gated.  An upload reads its own staged copy and touches neither
        the models nor the project, so it is one of the few verbs that is safe
        while a fit runs; the *commit* verbs it feeds are all idle-only already.
        """
        opts = dict(options or {})
        try:
            if kind not in UPLOAD_KINDS:
                raise UploadRefused(f"unknown upload kind {kind!r}; expected one "
                                    f"of {list(UPLOAD_KINDS)}", where=["kind"])
            if data:
                staged = self.uploads.stage(kind, filename, data)
            elif token:
                staged = self.uploads.get(token, kind)
            else:
                raise UploadRefused(
                    "send the file's bytes with ?filename=<name>, or "
                    "?upload=<token> to re-read one already staged",
                    where=["upload"])
            if kind == "pattern":
                return preview_pattern(staged, block=opts.get("block"))
            if kind == "cif":
                return preview_cif(staged, aniso=bool(opts.get("aniso")),
                                   phase_name=opts.get("phase_name"))
            return preview_instrument(staged)
        except UploadRefused as exc:
            raise GuiError(str(exc), code=exc.code, status=exc.status,
                           where=exc.where) from None

    # ------------------------------------------------------------------
    # project
    # ------------------------------------------------------------------
    def project_new(self, body: dict) -> dict:
        """``Project.create`` from a request body.

        Each of the three inputs takes a server-side path *or* the token of a
        staged upload (WP-1014), which is the whole of the commit step: the file
        was read once already, so a project is only ever created around bytes
        that parsed.  ``structure`` is an inline :class:`Structure` dict,
        ``{"cif": path}`` or ``{"upload": token, "aniso": bool}``; ``instrument``
        is an inline dict, ``{"preset": name, …}`` or ``{"upload": token}``, and
        is **required** because :class:`Instrument` has no default source and
        guessing a diffractometer is exactly the kind of silent assumption this
        package refuses.
        """
        self._require_idle()
        path = _need(body, "path")
        pattern = self._as_pattern_path(_need(body, "pattern"))
        structure = _as_structure(body.get("structure"), self.uploads)
        instrument = _as_instrument(body.get("instrument"), self.uploads)
        kw: dict[str, Any] = {}
        for key in ("mode", "two_theta_limits", "excluded_regions", "block", "ui"):
            if body.get(key) is not None:
                kw[key] = body[key]
        if body.get("plan") is not None:
            kw["plan"] = _as_plan_argument(body["plan"])
        try:
            project = Project.create(path, pattern=pattern, structure=structure,
                                     instrument=instrument, backend=self.backend,
                                     solver=self.solver, **kw)
        except (FileExistsError, FileNotFoundError, ValueError, KeyError) as exc:
            raise GuiError(str(exc), code="PROJECT_ERROR") from None
        self._adopt(project)
        return self.project_doc()

    def _as_pattern_path(self, pattern: Any) -> str:
        """A pattern argument as a path: a server-side one, or a staged upload's.

        The staged file is what ``Project.create`` copies, so the project owns
        its own bytes from the first moment and the staging directory can be
        thrown away with the session — the copy is byte-for-byte either way
        (WP-1005: the bytes are the contract).
        """
        if isinstance(pattern, dict):
            token = _need(pattern, "upload")
            try:
                return str(self.uploads.get(str(token), "pattern").path)
            except UploadRefused as exc:
                raise GuiError(str(exc), code=exc.code, status=exc.status,
                               where=["pattern.upload"]) from None
        return str(pattern)

    def project_open(self, body: dict) -> dict:
        """``Project.open``, with its refusal messages surfaced verbatim.

        ``Project.open`` distinguishes a missing pattern, changed bytes, a
        same-bytes/different-numbers reader change, a tree recorded against
        another pattern, a missing log, a future format major and a
        multi-pattern document — seven causes with seven remedies.  Collapsing
        them into "could not open project" would throw away the only place a
        user will ever read which one happened.
        """
        self._require_idle()
        path = _need(body, "path")
        try:
            project = Project.open(path, backend=self.backend, solver=self.solver)
        except (FileNotFoundError, ValueError) as exc:
            raise GuiError(str(exc), code="PROJECT_ERROR") from None
        self._adopt(project)
        return self.project_doc()

    def project_doc(self) -> dict:
        """The settings document plus what a client needs about the data."""
        p = self._need_project()
        ref = p.data_ref
        return {
            "path": str(p.path),
            "doc": p.doc.model_dump(mode="json"),
            "data": {
                "filename": ref.filename, "reader": ref.reader,
                "options": dict(ref.options), "n_points": ref.n_points,
                "two_theta_range": list(ref.two_theta_range),
                # which weights the fit uses is a correctness property that is
                # invisible once the file is read (CLAUDE.md, Weights)
                "has_sigma": ref.has_sigma,
                # how many channels survive the limits and the exclusions — the
                # check that a shaded band is telling the truth (WP-1033).  A
                # band drawn over points still in the residual is worse than no
                # band, and this number is what makes the difference readable
                # without re-running anything.
                "n_fitted": int(p.fitted_mask().sum()),
            },
            "head": p.refinement._head_id,
            "n_nodes": len(p.history),
        }

    def project_patch(self, body: dict) -> dict:
        """Change settings, and persist them at once.

        ``ui`` merges at the top level (the frontend owns those keys and pushes
        whole blobs for the panel it touched); a ``null`` value drops a key.
        ``excluded_regions`` goes through ``Project.set_excluded_regions`` so the
        document and the in-memory pattern cannot disagree about what is masked.

        An inverted or empty interval is refused in
        :func:`schemas.project.check_interval`'s words — the same sentence the
        ``.pxt`` document refuses with, because the document's field validators
        are what both routes run into (WP-1033).
        """
        self._require_idle()
        p = self._need_project()
        unknown = set(body) - {"mode", "two_theta_limits", "excluded_regions", "ui"}
        if unknown:
            raise GuiError(f"unknown setting(s): {sorted(unknown)}; the plan has "
                           "its own route and the model lives in the history",
                           where=sorted(unknown))
        if "mode" in body:
            p.doc.mode = body["mode"]
        if "two_theta_limits" in body:
            limits = body["two_theta_limits"]
            with self._settings_refusal("two_theta_limits"):
                p.doc.two_theta_limits = None if limits is None else tuple(limits)
        if "excluded_regions" in body:
            regions = [tuple(r) for r in (body["excluded_regions"] or [])]
            with self._settings_refusal("excluded_regions"):
                p.set_excluded_regions(regions)
        for key, value in (body.get("ui") or {}).items():
            if value is None:
                p.doc.ui.pop(key, None)
            else:
                p.doc.ui[key] = value
        p.save()
        return self.project_doc()

    @staticmethod
    @contextmanager
    def _settings_refusal(where: str):
        """Turn a document validator's refusal into this verb's 400 (WP-1033).

        The message is passed through with pydantic's ``"Value error, "`` prefix
        removed and nothing else added: the sentence a client shows is the one
        :func:`schemas.project.check_interval` wrote, so the wire route, the
        ``.pxt`` document and a bare ``doc.two_theta_limits = …`` all refuse
        alike.  Without this the assignment raises ``ValidationError`` and the
        transport answers 500 — true, and useless to the person who typed it.
        """
        from pydantic import ValidationError

        try:
            yield
        except ValidationError as exc:
            message = str(exc.errors()[0]["msg"])
            raise GuiError(message.removeprefix("Value error, "),
                           where=[where]) from None

    def project_save(self) -> dict:
        """Rewrite ``project.json``.

        Every settings verb above already saved, and the model was on disk the
        moment its node was appended, so this is a flush a client may call and
        never a thing it must call.  It exists because a "Save" affordance will
        exist, and it should do something honest.
        """
        p = self._need_project()
        p.save()
        return {"saved": str(p.path), "updated_utc": p.doc.updated_utc}

    def recent(self) -> list[dict]:
        """Recently opened projects, newest first (missing ones filtered out)."""
        try:
            raw = json.loads((self.state_dir / "recent.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        out = []
        for entry in raw if isinstance(raw, list) else []:
            path = Path(str(entry.get("path", "")))
            if (path / "project.json").is_file():
                out.append({"path": str(path), "name": path.name,
                            "opened_utc": entry.get("opened_utc", "")})
        return out

    # ------------------------------------------------------------------
    # parameters
    # ------------------------------------------------------------------
    def params(self) -> dict:
        """The whole parameter table as rows, held ones included.

        ``refinable`` and ``held_because`` are :class:`ParameterRow` *properties*
        rather than fields, so ``model_dump`` drops them — and they are the whole
        point of the surface (WP-1004), so they are added here by asking the row
        rather than by a second copy of the rule.

        While a run is in flight the values are read off models a stage is
        writing to, so a row may straddle two iterations; ``live`` says so.  That
        is deliberate — the authoritative live signal is the event stream, and
        the consistent alternative is the head node, which is a completed stage.
        """
        p = self._need_project()
        rows = []
        for row in p.parameters():  # answered for the document's mode
            item = row.model_dump(mode="json")
            item["refinable"] = row.refinable
            item["held_because"] = row.held_because
            rows.append(item)
        return {"parameters": rows,
                "n_free": sum(1 for r in rows if r["vary"]),
                "mode": p.doc.mode,
                "head": p.refinement._head_id,
                "live": self._state != "idle"}

    def params_patch(self, body: dict) -> dict:
        """``set_values`` then ``set_vary``, each committing its own node.

        Values first, then vary flags: the pair reads as "put it here, then let
        it move", which is the order that leaves a freed parameter's node last in
        the log — where a following run continues from.  ``vary`` is applied in
        the order the JSON object gave, since overlapping globs are ordinary
        (``phases.*`` then a single path back off).
        """
        self._require_idle()
        p = self._need_project()
        values = body.get("values") or {}
        vary = body.get("vary") or {}
        if not isinstance(values, dict) or not isinstance(vary, dict):
            raise GuiError("'values' maps dot-path → number and 'vary' maps "
                           "dot-path glob → bool")
        changed: dict[str, Any] = {"values": [], "vary": {}}
        if values:
            try:
                p.refinement.set_values({k: float(v) for k, v in values.items()})
            except (ValueError, TypeError) as exc:
                # a tied path names its sources, a locked one says it is
                # structural, a bound violation prints the interval — each has a
                # different fix, so the message travels intact
                raise GuiError(str(exc), where=sorted(values)) from None
            changed["values"] = sorted(values)
        for glob, flag in vary.items():
            changed["vary"][glob] = p.refinement.set_vary(glob, bool(flag))
        return {"changed": changed, **self.params()}

    # ------------------------------------------------------------------
    # plan
    # ------------------------------------------------------------------
    def plan(self) -> dict:
        """The plan the next run will use, expanded into stages.

        A project stores the *expanded* plan, so which preset button was pressed
        is not recoverable from it — ``preset`` is therefore derived by comparing
        the stored stages against every registered preset, and is ``null`` for an
        edited plan.  ``selected`` distinguishes "this project chose a plan" from
        "nothing chose, and ``fit`` would default".
        """
        p = self._need_project()
        effective = PlanSpec.from_plan(self._effective_plan())
        return {"plan": effective.model_dump(mode="json"),
                "selected": p.doc.plan is not None,
                "preset": effective.preset_name(),
                "mode": p.doc.mode}

    def plan_put(self, body: dict) -> dict:
        """Select a preset (``{"preset": name}``) or an explicit plan spec."""
        self._require_idle()
        p = self._need_project()
        if "preset" in body:
            # stored expanded, and expanded *through the mode*: a project's plan
            # is what will run verbatim (``Project.fit`` passes it as-is), so
            # picking "mccusker_default" in Le Bail mode has to store
            # profile_only's stages — the same mapping ``fit`` would apply, made
            # visible in the editor instead of happening at run time
            spec = PlanSpec.from_plan(
                resolve_plan(_as_plan_argument(body["preset"]), p.doc.mode))
        elif "plan" in body:
            spec = _validate(PlanSpec, body["plan"], "plan")
        else:
            raise GuiError("send either {'preset': name} or {'plan': {...}}")
        if not spec.stages:
            raise GuiError("a plan needs at least one stage", where=["plan.stages"])
        p.doc.plan = spec
        p.save()
        return self.plan()

    def plans(self) -> dict:
        """The preset registry, quoted through ``capabilities()``.

        Not read off ``PLAN_INFO`` directly: the capabilities arm is already the
        one answer to "what plans does this build have", and a menu that could
        disagree with it would be a second answer.
        """
        return {"plans": [item.model_dump(mode="json")
                          for item in _capabilities().plans]}

    # ------------------------------------------------------------------
    # the text document (WP-1009)
    # ------------------------------------------------------------------
    def textdoc(self) -> dict:
        """The project as text, with the CAS token for the matching ``PUT``."""
        from . import textdoc as td

        text = td.render(self._need_project())
        return {"text": text, "revision": td.revision(text),
                "format_version": td.FORMAT_VERSION}

    def textdoc_put(self, body: dict) -> dict:
        """Parse, diff against the live project, and apply — or apply nothing.

        ``base_revision`` is compare-and-set: it is the revision the editor was
        showing, and a mismatch means the project moved underneath it (a stage
        committed, a form edited a value). Rejecting is the whole conflict story
        — a three-way merge of a document that is regenerated from state would be
        inventing an authority. ``validate_only`` runs everything except the
        apply, which is what a continuously-validating editor calls.
        """
        from . import textdoc as td

        self._require_idle()
        project = self._need_project()
        text = body.get("text")
        if not isinstance(text, str):
            raise GuiError("'text' is required and must be a string",
                           where=["text"])
        current = td.render(project)
        base = body.get("base_revision")
        if base and base != td.revision(current):
            raise GuiError(
                "the project changed since this text was rendered "
                f"(revision {td.revision(current)}, you sent {base}); re-read "
                "/api/textdoc and re-apply your edit",
                code="STALE_REVISION", status=409)

        delta, errors = td.changes(td.parse(text), project)
        if errors:
            raise GuiError(
                f"{len(errors)} problem(s) in the document; nothing was applied",
                code="TEXTDOC_INVALID",
                where=sorted({e.where for e in errors if e.where}),
                details=[e.as_dict() for e in errors])
        if body.get("validate_only"):
            return {"valid": True, "applied": [], "delta": delta.as_dict(),
                    "revision": td.revision(current), "would_change":
                    not delta.is_empty()}
        editor = (self._peak_editor()
                  if (delta.peak_moves or delta.peak_flags) else None)
        try:
            applied = td.apply(project, delta, peak_editor=editor)
        except ValueError as exc:
            # the verbs' own refusals (a tied path, a bound); ``set_values``
            # validates before writing, so nothing was applied
            raise GuiError(str(exc), code="TEXTDOC_INVALID",
                           details=[_locate(str(exc), text)]) from None
        rendered = td.render(project)
        return {"valid": True, "applied": applied, "delta": delta.as_dict(),
                "text": rendered, "revision": td.revision(rendered)}

    # ------------------------------------------------------------------
    # the models
    # ------------------------------------------------------------------
    def structure(self) -> dict:
        """The structure, plus what site symmetry allows each atom to do.

        The ``sites`` arm is why an in-GUI structure editor can be safe: a
        coordinate is edited through its ``…dof.k`` parameters, so a site-symmetry
        violation is *unrepresentable* rather than refused after the fact, and a
        fully fixed special position has an empty ``dof_paths`` — which is what
        an editor renders read-only.  Derived through the same two functions
        ``ParameterTable`` uses (``stabilizer_rotations`` → ``coordinate_basis`` /
        ``adp_basis``), never a second rule.

        Two more arms since WP-1035, and both are free — one ``get_spacegroup``
        call per phase, on facts ``ParameterTable._collect`` already looks up.
        ``symmetry`` is the phase's symbol read out (number, **setting**, crystal
        system, Laue class, centring, and the cell ties and held angles it
        causes); ``causes`` names the symmetry responsible for each held row, so
        the parameter table stops showing effects with anonymous causes.

        The Wyckoff *letter* is still deliberately absent: it needs
        ``wyckoff.site_constraints``, which runs spglib per atom (**measured at
        1.8-8.7 ms an atom**, WP-1035), and this route is refetched on every head
        move — including one a ``set_vary`` made.  It rides on
        ``GET /api/structure/symmetry``, the deliberately-opened route this
        docstring already named as the escape.
        """
        structure = self._need_project().refinement.structure
        rows = symmetry.site_rows(structure)
        return {"structure": structure.model_dump(mode="json"),
                "sites": rows,
                "symmetry": symmetry.phase_summary(structure),
                "causes": symmetry.held_causes(structure, rows)}

    def structure_symmetry(self, phase: int = 0) -> dict:
        """One phase's symmetry in full, Wyckoff letters included (WP-1035).

        The tier ``GET /api/structure`` refuses to carry.  A letter is a spglib
        search per atom, so this route is *opened deliberately* — a panel fetches
        it when a user asks to see site symmetry, not on every head move — and
        what it buys beyond the free tier is the **oriented site-symmetry
        symbol** (``.3.``, ``4m.m``), which is the one form of "which element is
        responsible" that names an element rather than counting a stabiliser.
        The ``causes`` here are therefore the same sentences ``/api/structure``
        serves, upgraded wherever a letter was found.

        Not idle-gated: it reads the model, like ``/api/structure``.
        """
        structure = self._need_project().refinement.structure
        try:
            letters = symmetry.site_letters(structure, int(phase))
        except IndexError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404,
                           where=["phase"]) from None
        by_path = {row["path"]: row for row in letters if "error" not in row}
        rows = symmetry.site_rows(structure)
        return {"phase": int(phase),
                "symmetry": symmetry.phase_facts(structure.phases[int(phase)],
                                                 int(phase)),
                "letters": letters,
                "causes": symmetry.held_causes(structure, rows, by_path)}

    def symmetry_preview(self, body: dict) -> dict:
        """What changing a phase's space group would do — and nothing else.

        Built out of the existing rules rather than a second copy of them: the
        candidate model's own ``ParameterTable`` supplies the refusals verbatim
        (nearest-allowed values included, because the raises already compute
        them), the entry diff supplies the tie/lock story, and ``site_rows``
        supplies the per-atom DOF story in the shape the editor already renders.

        Read-only, but **idle-gated anyway**: what it previews is a mutation, and
        an answer computed against a model a running stage is about to move is an
        answer about nothing.
        """
        self._require_idle()
        return self._preview(body)

    def symmetry_patch(self, body: dict) -> dict:
        """Change one phase's space group, gated on :meth:`symmetry_preview`.

        The gate is the whole verb.  ``PATCH /api/structure`` accepted a changed
        symbol before WP-1035 and committed an ``edit_model`` node from a
        snapshot that never builds a ``ParameterTable`` — so an incompatible
        change *succeeded*, recorded a node, and then surfaced as a 500 on the
        panel's next ``GET /api/params``, with the head standing at a state whose
        table cannot build and a history checkout the only way out.  Nothing
        about that was specific to the space group, so the gate went one level
        down into :meth:`_edit`; this verb adds the *complete* refusal list,
        because a table stops at the first bad item and a user fixing four atoms
        one 500 at a time is not being told what is wrong.
        """
        self._require_idle()
        answer = self._preview(body)
        phase = answer["phase"]
        if answer["blocked"]:
            first = (answer["refusals"] or [
                {"message": n["message"]} for n in answer["notes"]
                if n["kind"] == "orbit_collision"])[0]["message"]
            raise GuiError(
                f"{body.get('space_group')!r} is not compatible with this model: "
                f"{first}",
                code="SYMMETRY_REFUSED", where=["space_group"],
                details=[answer])
        if not answer["changed"]:
            return {"node_id": None, "changed": False, "preview": answer,
                    **self.structure()}
        candidate = symmetry.with_symbol(
            self._need_project().refinement.structure, phase,
            str(_need(body, "space_group")))
        node = self._edit(structure=candidate,
                          label=f"phase {phase}: space group "
                                f"{answer['to'].get('xhm', '?')}")
        return {"node_id": node, "changed": True, "preview": answer,
                **self.structure()}

    def _preview(self, body: dict) -> dict:
        p = self._need_project()
        phase = int(body.get("phase", 0) or 0)
        symbol = str(_need(body, "space_group"))
        try:
            free = [row.path for row in p.parameters() if row.vary]
        except ValueError:
            free = []           # the head cannot build a table; that is a state
            # this verb exists to escape, not one it may refuse to answer in
        try:
            return symmetry.preview(p.refinement.structure, p.refinement.instrument,
                                    phase, symbol, free_paths=free)
        except IndexError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404,
                           where=["phase"]) from None
        except (ValueError, RuntimeError) as exc:
            # the same mapping ``index_adopt`` uses for an unresolvable symbol
            raise GuiError(str(exc), where=["space_group"]) from None

    def structure3d(self, phase: int = 0, *, probability: float = 0.5,
                    bond_tolerance: float | None = None) -> dict:
        """The current model as drawable geometry (WP-1015).

        A route beside ``/api/structure`` rather than an arm of it, on WP-1008's
        test for a new one: it returns what the model does **not** already say —
        the symmetry orbit with each image's rotated displacement tensor, bonds
        over the 27 nearest lattice translations, and the cell frame — none of
        which a client could reshape out of a ``Structure`` dump without owning a
        space-group table.  Computed on demand, so it is also where a per-atom
        symmetry search may live that ``/api/structure`` refused (that route
        refetches on every head move; this one is opened deliberately).

        Not idle-gated: it reads the model, like ``/api/structure``, and a fit in
        flight does not move the values the working state holds.
        """
        from . import structure3d as geometry

        structure = self._need_project().refinement.structure
        try:
            return geometry.build(
                structure, int(phase), probability=float(probability),
                bond_tolerance=(geometry.BOND_TOLERANCE if bond_tolerance is None
                                else float(bond_tolerance)))
        except IndexError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404,
                           where=["phase"]) from None
        except ValueError as exc:
            raise GuiError(str(exc), where=["probability"]) from None

    def instrument(self) -> dict:
        return {"instrument": self._need_project().refinement.instrument.model_dump(
            mode="json")}

    def structure_patch(self, body: dict) -> dict:
        """Replace the structure, recording an ``edit_model`` node.

        A whole model, validated, not a field patch: adding a phase or an
        anisotropic ADP block changes what the parameter table *contains*, and a
        partial merge would have to reimplement pydantic's validation to know
        whether the result is a legal structure.
        """
        self._require_idle()  # before validating: a state refusal outranks a
        # body complaint, or a user retyping a structure never learns that the
        # real problem is the fit still running
        node = self._edit(
            structure=_as_structure(_need(body, "structure"), self.uploads),
            label=body.get("label") or "structure edited")
        return {"node_id": node, **self.structure()}

    def instrument_patch(self, body: dict) -> dict:
        self._require_idle()
        node = self._edit(
            instrument=_as_instrument(_need(body, "instrument"), self.uploads),
            label=body.get("label") or "instrument edited")
        return {"node_id": node, **self.instrument()}

    def structure_aniso(self, body: dict) -> dict:
        """Turn one atom's anisotropic ADP block on or off (WP-1014).

        A verb of its own rather than a field of the structure patch, because
        both directions are **physics the client must not compute**.  On seeds
        ``AnisoU.isotropic`` — U^ij = Uiso·G*ᵢⱼ/(a*ᵢa*ⱼ), which is *not*
        Uiso·δᵢⱼ except for orthogonal reciprocal axes, so a TypeScript version
        would get every hexagonal cell wrong.  Off restores ``biso`` from U_eq,
        which weights by the metric.  Both live in ``crystallography.adp``, and
        this is what reaches them.

        Recorded as one ``edit_model`` node, like every other model change: it
        changes what the parameter table *contains* (six tied components and
        their ``…adp.k`` DOFs appear, ``biso`` becomes locked), which is the
        definition of a shape change here.
        """
        import math

        self._require_idle()
        p = self._need_project()
        path = str(_need(body, "path"))
        on = bool(body.get("on", True))
        match = re.fullmatch(r"phases\.(\d+)\.atoms\.(\d+)", path)
        if match is None:
            raise GuiError(f"{path!r} is not an atom path (phases.I.atoms.J)",
                           where=["path"])
        i, j = int(match.group(1)), int(match.group(2))
        structure = p.refinement.structure.model_copy(deep=True)
        try:
            phase = structure.phases[i]
            atom = phase.atoms[j]
        except IndexError:
            raise GuiError(f"no atom at {path!r}", code="NOT_FOUND",
                           status=404, where=["path"]) from None
        if on and atom.aniso is None:
            from ..schemas.structure import AnisoU

            atom.aniso = AnisoU.isotropic(atom.biso.value / (8.0 * math.pi ** 2),
                                          phase.cell)
        elif not on and atom.aniso is not None:
            from ..crystallography.adp import u_equivalent

            u_eq = u_equivalent(atom.aniso.values(), phase.cell.lengths_angles())
            biso = 8.0 * math.pi ** 2 * float(u_eq)
            atom.biso.value = min(max(biso, atom.biso.min), atom.biso.max)
            atom.aniso = None
        else:
            return {"node_id": None, "changed": False, **self.structure()}
        node = self._edit(structure=structure,
                          label=f"{atom.label}: aniso {'on' if on else 'off'}")
        return {"node_id": node, "changed": True, **self.structure()}

    def _edit(self, *, structure: Structure | None = None,
              instrument: Instrument | None = None, label: str = "") -> str | None:
        """The one funnel every whole-model edit goes through.

        The gate that used to live here is now in ``Refinement.edit`` itself
        (WP-1035), because nothing about it was a GUI concern: pydantic knows no
        crystallography, every symmetry refusal is raised when a
        ``ParameterTable`` is constructed, and the snapshot ``edit`` commits
        never constructs one — so a Python caller was exposed to exactly the
        failure a browser found. All this layer adds is the **address**: a
        ``ValueError`` carries the offending dot-path in its first token, and a
        form needs it to highlight the field.
        """
        self._require_idle()
        p = self._need_project()
        try:
            return p.refinement.edit(structure=structure, instrument=instrument,
                                     label=label)
        except ValueError as exc:
            match = _LEADING_PATH.search(str(exc))
            raise GuiError(str(exc), code="MODEL_REFUSED",
                           where=[match.group(1)] if match else []) from None

    # ------------------------------------------------------------------
    # run control
    # ------------------------------------------------------------------
    def run(self, body: dict) -> dict:
        """Start a fit (``kind="fit"``), one stage (``"stage"``) or an
        indexing run (``"index"``).

        Returns immediately with the run state; everything else about the run
        arrives as events.  The refinement kinds go through ``Project.fit`` /
        ``Project.run_stage`` rather than ``Refinement.fit`` so the document's
        mode and limits are the ones that apply — the project is the authority
        on the settings, and re-deriving them here would be the second copy
        WP-1005 exists to prevent.

        ``"index"`` (WP-1027) runs :func:`pxrdref.index_pattern` on the stored
        peak list (or lets it pick its own when none is stored) through the
        same machinery: one worker, the same 409 for every mutating verb, the
        engine's own ``index_start``/``stage_start``/``stage_end``/``index_end``
        events on the same stream.  What differs is only how the run record is
        summarised — an ``IndexingResult`` has no Rwp and commits no node, and a
        *cancelled* search returns what it has rather than raising, so its
        status is read off the token.
        """
        p = self._need_project()
        kind = body.get("kind", "fit")
        if kind not in ("fit", "stage", "index", "extinction", "series"):
            raise GuiError(f"unknown run kind {kind!r}; expected 'fit', "
                           "'stage', 'index', 'extinction' or 'series'",
                           where=["kind"])
        summarize = _summarize_refinement
        if kind == "stage":
            stage_spec = _validate(StageSpec, _need(body, "stage"), "stage")
            stage = stage_spec.to_stage()

            def call(stream, token):
                return p.run_stage(stage, events=stream, cancel=token)

            label = stage_spec.name
            n_stages = 1
        elif kind == "index":
            from ..indexing.engines import engine_names

            peak_doc = self._load_peaks(p)  # a wrong-pattern list refuses here
            peak_list = None if peak_doc is None else peak_doc.peaks
            limits = (tuple(p.doc.two_theta_limits)
                      if p.doc.two_theta_limits else None)

            def call(stream, token):
                from ..indexing.workflow import index_pattern

                result = index_pattern(
                    peak_list, data=p.data,
                    instrument=p.refinement.instrument,
                    two_theta_limits=limits, events=stream, cancel=token)
                with self._cond:
                    self._index_result = result
                    # candidate indices just changed meaning: a screen kept
                    # from the previous answer would be served against the
                    # wrong cell
                    self._extinction = None
                return result

            summarize = _summarize_index
            label = "index"
            n_stages = len(engine_names())
        elif kind == "extinction":
            # WP-1025 served (WP-1027): rank the extinction classes of one
            # candidate.  Deliberately *not* gated on the adopt verdict — on
            # real data with no measured shift ``best_or_none()`` is None by
            # design, and a screen is a read-only measurement ("IF this cell,
            # THEN these classes"); the gate stays on ``index_adopt``, where
            # the model is at stake.  It rides the run machine because it is
            # seconds-long (one profile fit, then one Le Bail per class),
            # takes ``cancel=``, and must hold the same one-worker discipline
            # as every other computation over the project.
            candidate = self._extinction_candidate(body)
            peak_doc = self._load_peaks(p)
            peak_list = None if peak_doc is None else peak_doc.peaks
            limits = (tuple(p.doc.two_theta_limits)
                      if p.doc.two_theta_limits else None)
            index = int(body["candidate"])
            max_classes = body.get("max_classes")
            max_classes = None if max_classes is None else int(max_classes)

            def call(stream, token):
                from ..indexing.extinction import determine_extinction_symbol

                screen = determine_extinction_symbol(
                    p.data, candidate, p.refinement.instrument,
                    peaks=peak_list, two_theta_limits=limits,
                    max_classes=max_classes, cancel=token)
                with self._cond:
                    self._extinction = {"screen": screen, "candidate": index}
                return screen

            summarize = _summarize_extinction
            label = "extinction"
            n_stages = 1
        elif kind == "series":
            # One run on the one machine (WP-1008's charter): a series is N fits,
            # but it is *one* long computation with one cancel token, and
            # ``SequentialRefinement`` already emits per-pattern events — since
            # WP-1016 it does, which is the half that charter assumed and the
            # library did not have.
            from ..sequential import SequentialRefinement

            setup = self._series
            if len(setup.members) < 2:
                raise GuiError(
                    f"a series needs at least two patterns; {len(setup.members)} "
                    "staged. One pattern is a fit — use Run — and the fences a "
                    "series exists for (reseed, discontinuity, path dependence) "
                    "all compare a pattern with its neighbours.",
                    code="NO_SERIES", status=409, where=["patterns"])
            plan = self._effective_plan(body.get("plan"))
            data = series_mod.read_members(setup, p.doc.excluded_regions)
            limits = (tuple(p.doc.two_theta_limits)
                      if p.doc.two_theta_limits else None)
            runner = SequentialRefinement(
                # the working state, not the root: a series warm-starts from
                # whatever the user has already got right in this project
                p.refinement.structure, p.refinement.instrument,
                backend=self.backend, solver=self.solver, carry=setup.carry,
                # in memory: the trees belong to patterns the project does not
                # own, so writing them into it would leave orphans no document
                # can interpret on the next open (see gui/series.py)
                history=True)
            members = [m.as_dict() for m in setup.members]

            def call(stream, token):
                result = runner.fit(
                    data, x=setup.x, x_label=setup.x_label,
                    labels=setup.labels, mode=p.doc.mode, plan=plan,
                    refit=setup.refit, direction=setup.direction,
                    two_theta_limits=limits, events=stream, cancel=token)
                with self._cond:
                    self._series_run = {"runner": runner, "result": result,
                                        "backward": runner.backward_,
                                        "members": members, "data": data}
                return result

            summarize = _summarize_series
            label = "series"
            n_stages = len(setup.members)
        else:
            plan = self._effective_plan(body.get("plan"))

            def call(stream, token):
                return p.fit(plan=plan, events=stream, cancel=token)

            label = ""
            n_stages = len(plan.stages)

        p.live_dir.mkdir(exist_ok=True)  # a project copied without empty dirs
        with self._cond:
            self._require_idle()
            token = CancelToken()
            stream = EventStream(path=p.live_dir / "events.jsonl",
                                 callback=self._push)
            self._state = "running"
            self._cancel = token
            self._events.clear()
            self._n_eval = 0
            self._run = {"kind": kind, "name": label, "status": None,
                         "stage": None, "stage_index": None, "n_stages": n_stages,
                         "started_utc": _utcnow(), "finished_utc": None,
                         "elapsed": None, "rwp": None, "gof": None,
                         "node_id": None, "completed_stages": [], "error": None}
            self._worker = threading.Thread(
                target=self._work, args=(call, stream, summarize),
                name="pxrdref-gui-run", daemon=True)
            self._worker.start()
            self._cond.notify_all()
        return self.state_frame()

    def cancel(self) -> dict:
        """Set the token.  Cooperative: read between residual evaluations."""
        with self._cond:
            if self._state == "idle":
                raise GuiError("nothing is running", code="NOT_RUNNING", status=409)
            if self._cancel is not None:
                self._cancel.cancel()
            self._state = "cancelling"
            self._cond.notify_all()
            return self._state_frame_locked()

    def run_state(self) -> dict:
        """The coarse state frame plus the fine progress a poller wants."""
        with self._cond:
            frame = self._state_frame_locked()
            started = self._run.get("started_utc")
            frame["n_eval"] = self._n_eval
            frame["seq"] = self._seq
            frame["last_event"] = self._events[-1] if self._events else None
            frame["run"]["elapsed"] = self._run.get("elapsed")
            if self._state != "idle" and started:
                frame["run"]["elapsed"] = self._elapsed()
            return frame

    def state_frame(self) -> dict:
        with self._cond:
            return self._state_frame_locked()

    def _state_frame_locked(self) -> dict:
        return {"state": self._state, "run": dict(self._run),
                "project": None if self.project is None else str(self.project.path),
                "head": (None if self.project is None
                         else self.project.refinement._head_id)}

    def events_since(self, since: int) -> dict:
        """Buffered events after ``since`` (the ``?poll=1`` fallback's payload).

        ``oldest`` is what tells a client it fell out of the window: if
        ``since + 1 < oldest`` the run emitted more than the ring holds and the
        gap is real, not a renumbering.
        """
        with self._cond:
            events = [e for e in self._events if e["seq"] > since]
            oldest = self._events[0]["seq"] if self._events else self._seq + 1
            return {"events": events, "next": self._seq, "oldest": oldest,
                    **self._state_frame_locked()}

    def follow(self, since: int, last_state: str = "",
               timeout: float = 1.0) -> tuple[list[dict], int, dict | None, str]:
        """Block until something changed, then hand back what did.

        Returns ``(events, next_seq, state_frame_or_None, state_key)``: the
        events after ``since``, the seq to ask for next, the state frame *only
        when it differs* from ``last_state``, and the key to pass back as
        ``last_state``.  The comparison is on the coarse frame, which is why
        ``n_eval`` is not in it — a frame per residual evaluation would make the
        state channel a duplicate of the event channel.
        """
        with self._cond:
            if not self._changed(since, last_state):
                self._cond.wait(timeout)
            events = [e for e in self._events if e["seq"] > since]
            frame = self._state_frame_locked()
            key = json.dumps(frame, sort_keys=True, default=str)
            return events, self._seq, (None if key == last_state else frame), key

    def _changed(self, since: int, last_state: str) -> bool:
        if self.closed or self._seq > since:
            return True
        key = json.dumps(self._state_frame_locked(), sort_keys=True, default=str)
        return key != last_state

    def close(self) -> None:
        """Release followers so a shutdown does not wait on a heartbeat."""
        with self._cond:
            self.closed = True
            self._cond.notify_all()
        self.uploads.close()  # staged bytes outlive nothing

    # -- the worker ----------------------------------------------------
    def _work(self, call, stream: EventStream, summarize) -> None:
        """Run one fit, stage or indexing search and record how it ended.

        Three endings, and the difference between them is the WP-1006 result: a
        cancelled *refinement* **raises** rather than returning a partial
        result, and what it leaves behind is on the exception — the stages that
        did complete and the node the working state now stands at, which is
        what a "resume" button checks out.  (A cancelled indexing search
        returns instead — it has nothing to abandon — which is why
        ``summarize`` reads the token.)
        """
        started = time.monotonic()
        token = self._cancel
        try:
            result = call(stream, token)
            finish = summarize(result, token)
        except RefinementCancelled as exc:
            finish = {"status": "cancelled", "stage": exc.stage,
                      "node_id": exc.node_id,
                      "completed_stages": [s.name for s in exc.completed_stages]}
        except Exception as exc:  # noqa: BLE001 — the run record IS the channel
            finish = {"status": "failed",
                      "error": {"code": "RUN_FAILED",
                                "message": f"{type(exc).__name__}: {exc}"}}
        finally:
            stream.close()
        with self._cond:
            self._run.update(finish)
            self._run["finished_utc"] = _utcnow()
            self._run["elapsed"] = time.monotonic() - started
            self._state = "idle"
            self._cancel = None
            self._worker = None
            self._cond.notify_all()

    def _push(self, event: dict) -> None:
        """``EventStream`` callback — runs on the worker thread, per event.

        Reads the payload with ``.get`` only.  ``data`` is an open dict by
        design (a new field is not a schema bump), so unpacking a fixed shape
        here is exactly the thing the event contract forbids.
        """
        data = event.get("data") or {}
        with self._cond:
            self._seq += 1
            self._events.append({"seq": self._seq, **event})
            kind = event.get("kind")
            series = data.get("series_index")
            if kind == "eval":
                self._n_eval = int(data.get("n_eval") or self._n_eval + 1)
            elif series is not None:
                # A series' progress is "pattern k of N", and the run record says
                # so through the *existing* three fields rather than three new
                # ones — the same reuse an indexing run makes of
                # ``stage_start``.  Its inner stages would otherwise fill them
                # with "warm_refit (1/1)", which is true and says nothing about a
                # forty-pattern chain.
                if kind == "fit_start":
                    self._run["stage"] = _series_stage_name(data, series)
                    self._run["stage_index"] = int(series) + 1
                    self._run["n_stages"] = (data.get("series_n")
                                             or self._run["n_stages"])
                elif kind == "fit_end":
                    completed = self._run["completed_stages"]
                    name = _series_stage_name(data, series)
                    if name not in completed:
                        completed.append(name)
            elif kind == "stage_start":
                self._run["stage"] = data.get("stage") or data.get("name")
                self._run["stage_index"] = data.get("index")
                if data.get("n_stages"):
                    self._run["n_stages"] = data["n_stages"]
            elif kind == "stage_end":
                completed = self._run["completed_stages"]
                name = data.get("stage") or data.get("name") or self._run["stage"]
                if name and name not in completed:
                    completed.append(name)
            self._cond.notify_all()

    def _elapsed(self) -> float:
        return max(0.0, time.time() - _parse_utc(self._run["started_utc"]))

    # ------------------------------------------------------------------
    # peaks (WP-1027)
    # ------------------------------------------------------------------
    def peaks(self) -> dict:
        """The stored peak list — or, before any pick, just the raw pattern.

        The pattern rides on every answer because the peak panel is the one
        surface that must draw *before a fit exists*: an indexing project has
        no ``/api/result/window`` to plot until a candidate is adopted and
        Le-Bail-fitted, and picking peaks by eye needs the counts on screen.
        Not idle-gated: it reads a project artifact and the pattern.
        """
        p = self._need_project()
        doc = self._load_peaks(p)
        if doc is None:
            return self._peaks_payload(None)
        return self._peaks_payload(doc, editor=self._peak_editor())

    def peaks_pick(self, body: dict) -> dict:
        """Run the picker and store the list — replacing any previous one,
        edits included, which is what "pick" has to mean."""
        self._require_idle()
        p = self._need_project()
        editor = self._peak_editor()
        shoulders = bool(body.get("shoulders", True))
        doc = editor.pick(shoulders=shoulders)
        self._save_peaks(p, doc)
        return self._peaks_payload(
            doc, editor=editor,
            api_call=f"session.pick_peaks(shoulders={shoulders})")

    def peaks_add(self, body: dict) -> dict:
        tt = self._peak_number(body, "two_theta")
        return self._peak_edit(
            lambda ed, doc: ed.add(doc, tt),
            api_call=f"session.add_peak({tt:g})", where=["two_theta"])

    def peaks_move(self, body: dict) -> dict:
        index = self._peak_index(body)
        tt = self._peak_number(body, "two_theta")
        return self._peak_edit(
            lambda ed, doc: ed.move(doc, index, tt),
            api_call=f"session.move_peak({index}, {tt:g})",
            where=["index", "two_theta"])

    def peaks_remove(self, body: dict) -> dict:
        index = self._peak_index(body)
        return self._peak_edit(
            lambda ed, doc: ed.remove(doc, index),
            api_call=f"session.remove_peak({index})", where=["index"])

    def peaks_flag(self, body: dict) -> dict:
        index = self._peak_index(body)
        use = body.get("use_for_indexing")
        flags = body.get("flags")
        if flags is not None and not isinstance(flags, list):
            raise GuiError("'flags' must be a list of flag words",
                           where=["flags"])
        args = (f"use_for_indexing={bool(use)}" if use is not None
                else f"flags={flags!r}")
        return self._peak_edit(
            lambda ed, doc: ed.flag(
                doc, index,
                use_for_indexing=None if use is None else bool(use),
                flags=flags),
            api_call=f"session.set_peak_flags({index}, {args})",
            where=["index", "flags"])

    def peaks_refit(self, body: dict) -> dict:
        group = self._peak_number(body, "group", int)
        n = body.get("n_components")
        n = None if n is None else int(n)
        args = f"{group}" if n is None else f"{group}, n_components={n}"
        return self._peak_edit(
            lambda ed, doc: ed.refit(doc, group, n_components=n),
            api_call=f"session.refit_group({args})",
            where=["group", "n_components"])

    def _peak_edit(self, edit, *, api_call: str, where: list[str]) -> dict:
        """One stored-list edit: load, apply, save, answer — with the echo.

        Every editing verb funnels through here so the rules hold once: idle
        only (an edit refits against the instrument a running stage is
        writing), the stored list is required (there is nothing to edit before
        a pick), a refused edit names its field, and the echo is the verb's own
        equivalent API line — the console transcript stays a script.
        """
        self._require_idle()
        p = self._need_project()
        editor = self._peak_editor()
        doc = self._need_peaks(p)
        try:
            doc = edit(editor, doc)
        except IndexError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404,
                           where=where) from None
        except ValueError as exc:
            raise GuiError(str(exc), where=where) from None
        self._save_peaks(p, doc)
        return self._peaks_payload(doc, editor=editor, api_call=api_call)

    def _peaks_payload(self, doc, *, editor=None, api_call: str = "") -> dict:
        from typing import get_args as _get_args

        from ..schemas.indexing import PEAK_UNUSABLE_FLAGS, PeakFlag

        out: dict[str, Any] = {
            "pattern": self._peaks_pattern(),
            # the split is the server's fact (usable() reads it); a client
            # re-deriving it from a hand-copied list would drift when the
            # vocabulary grows — the held_because rule again
            "flag_vocabulary": list(_get_args(PeakFlag)),
            "unusable_flags": sorted(PEAK_UNUSABLE_FLAGS),
        }
        if api_call:
            out["api_call"] = api_call
        if doc is None:
            out["peaks"] = None
            return out
        rows = []
        for i, peak in enumerate(doc.peaks.peaks):
            row = peak.model_dump(mode="json")
            row["index"] = i
            row["usable"] = peak.usable
            row["d"] = peak.d
            rows.append(row)
        out.update({
            "peaks": rows,
            "n_total": len(rows),
            "n_usable": sum(1 for r in rows if r["usable"]),
            "wavelength": doc.peaks.wavelength,
            "two_theta_min": doc.peaks.two_theta_min,
            "two_theta_max": doc.peaks.two_theta_max,
            "source": doc.peaks.source,
            "diagnostics": [d.model_dump(mode="json")
                            for d in doc.peaks.diagnostics],
            "pick_options": dict(doc.pick_options),
            "created_utc": doc.created_utc,
            "groups": [] if editor is None else editor.curves(doc),
        })
        return out

    def _peaks_pattern(self, max_points: int = 4000) -> dict:
        """The measured pattern, masked and decimated, for the peak plot.

        The masked channels ride along in ``excluded`` for the reason
        :meth:`_masked_arm` gives: this is the view a project has *before* any
        fit, so it is the only place the fit range can be seen at all, and it
        cropped to the limits — a user could not see what they had cut.  The
        intersection itself is :meth:`Project.fitted_mask`, so this cannot
        drift from what the residual contains.
        """
        p = self._need_project()
        data = p.data
        keep = p.fitted_mask()
        tt_all, y_all = data.tt(), data.y()
        tt, y = tt_all[keep], y_all[keep]
        out_tt, out_y = tt_all[~keep], y_all[~keep]
        excluded = {"two_theta": [], "y_obs": []}
        if len(out_tt):
            out_idx = decimation_index(out_tt, [out_y], max(2, max_points // 4))
            excluded = {"two_theta": out_tt[out_idx].tolist(),
                        "y_obs": out_y[out_idx].tolist()}
        if not len(tt):
            return {"two_theta": [], "y_obs": [], "n_total": 0,
                    "excluded": excluded, "n_excluded": int(len(out_tt))}
        idx = decimation_index(tt, [y], max_points)
        return {"two_theta": tt[idx].tolist(), "y_obs": y[idx].tolist(),
                "n_total": int(len(tt)), "excluded": excluded,
                "n_excluded": int(len(out_tt))}

    def _peak_editor(self):
        from . import peaks as store

        p = self._need_project()
        instrument = p.refinement.instrument
        key = (instrument.model_dump_json(), str(p.doc.two_theta_limits),
               str(p.doc.excluded_regions))
        if self._peak_ed is not None and self._peak_ed[0] == key:
            return self._peak_ed[1]
        limits = tuple(p.doc.two_theta_limits) if p.doc.two_theta_limits else None
        editor = store.PeakEditor(p.data, instrument, two_theta_range=limits)
        self._peak_ed = (key, editor)
        return editor

    def _load_peaks(self, p):
        from . import peaks as store

        try:
            return store.load(p)
        except ValueError as exc:
            raise GuiError(str(exc), code="PEAKS_WRONG_PATTERN",
                           status=409) from None

    def _need_peaks(self, p):
        doc = self._load_peaks(p)
        if doc is None:
            raise GuiError("no peak list yet; POST /api/peaks to pick one",
                           code="NO_PEAKS", status=409)
        return doc

    def _save_peaks(self, p, doc) -> None:
        from . import peaks as store

        store.save(p, doc)

    @staticmethod
    def _peak_number(body: dict, key: str, cast=float):
        value = _need(body, key)
        try:
            return cast(value)
        except (TypeError, ValueError):
            raise GuiError(f"{key}={value!r} is not a number",
                           where=[key]) from None

    @classmethod
    def _peak_index(cls, body: dict) -> int:
        if body.get("index") is None:
            raise GuiError("'index' is required", where=["index"])
        return cls._peak_number(body, "index", int)

    # ------------------------------------------------------------------
    # indexing (WP-1027)
    # ------------------------------------------------------------------
    def index_result(self) -> dict:
        """The last indexing answer, with the adopt gate answered per row.

        ``adopt`` runs parallel to ``result.candidates`` and is the server
        saying whether :meth:`index_adopt` would act — the button's
        enabled-ness and the route's willingness must not be two answers
        (the ``report.apply`` rule).  ``refuting_caveats`` is served so the
        client colours chips from the constant rather than a hand-written list.
        """
        from ..schemas.indexing import INDEX_REFUTING_CAVEATS

        self._need_project()
        with self._cond:
            result = self._index_result
            busy = self._state != "idle" and self._run.get("kind") == "index"
        if result is None:
            raise GuiError(
                "an indexing run is in flight; follow /api/events" if busy
                else "no indexing run has completed in this session yet; "
                     "POST /api/index", code="NO_INDEX_RESULT", status=409)
        best = result.best_or_none()
        adopt = []
        for cand in result.candidates:
            allowed = best is not None and cand is best
            adopt.append({"allowed": allowed,
                          "why": "" if allowed else _adopt_refusal(cand, best)})
        return {"result": result.model_dump(mode="json"),
                "adopt": adopt,
                "refuting_caveats": sorted(INDEX_REFUTING_CAVEATS),
                "running": busy}

    def _extinction_candidate(self, body: dict):
        """Validate and fetch the candidate an extinction screen is asked of."""
        with self._cond:
            result = self._index_result
        if result is None:
            raise GuiError("no indexing result to screen; POST /api/index "
                           "first", code="NO_INDEX_RESULT", status=409)
        if body.get("candidate") is None:
            raise GuiError("'candidate' is required", where=["candidate"])
        index = self._peak_number(body, "candidate", int)
        if not 0 <= index < len(result.candidates):
            raise GuiError(
                f"no candidate {index}; the result has "
                f"{len(result.candidates)}", code="NOT_FOUND", status=404,
                where=["candidate"])
        return result.candidates[index]

    def index_extinction(self) -> dict:
        """The last extinction screen — ranked classes, never one space group.

        ``best`` is the index :meth:`ExtinctionScreen.best_or_none` points at
        (or ``None``), served for the same reason ``adopt`` rides
        ``index_result``: the panel's badge and the package's gate must be one
        answer.  Even the best row lists *every* space group in its class —
        the one place the singleton is unmeasurable rather than merely
        unsupported (WP-1025).
        """
        self._need_project()
        with self._cond:
            entry = self._extinction
            busy = (self._state != "idle"
                    and self._run.get("kind") == "extinction")
        if entry is None:
            raise GuiError(
                "an extinction screen is in flight; follow /api/events"
                if busy else
                "no extinction screen has run; POST /api/index/extinction",
                code="NO_EXTINCTION_RESULT", status=409)
        screen = entry["screen"]
        best = screen.best_or_none()
        return {"result": screen.model_dump(mode="json"),
                "candidate": entry["candidate"],
                "best": None if best is None else screen.candidates.index(best),
                "running": busy}

    def index_adopt(self, body: dict) -> dict:
        """Adopt one candidate cell as the model — through the gate, or not at
        all.

        The gate is re-asked here rather than trusted from the panel: only the
        candidate ``best_or_none()`` would return can be adopted, so no UI path
        can hand back a cell the API itself refuses to single out.  Adoption is
        a model edit (``Refinement.edit`` → one ``edit_model`` node, no new
        NodeKind): the structure becomes WP-1024's single-phase Le Bail scaffold
        (absence-free lattice group unless a ``space_group`` from the extinction
        screen is given, one dummy atom), and the document's mode follows to
        ``lebail`` — a Rietveld fit over a dummy atom is not a thing to offer.
        """
        self._require_idle()
        p = self._need_project()
        with self._cond:
            result = self._index_result
        if result is None:
            raise GuiError("no indexing result to adopt from; POST /api/index",
                           code="NO_INDEX_RESULT", status=409)
        if body.get("candidate") is None:
            raise GuiError("'candidate' is required", where=["candidate"])
        index = self._peak_number(body, "candidate", int)
        if not 0 <= index < len(result.candidates):
            raise GuiError(
                f"no candidate {index}; the result has "
                f"{len(result.candidates)}", code="NOT_FOUND", status=404,
                where=["candidate"])
        candidate = result.candidates[index]
        best = result.best_or_none()
        if best is None or candidate is not best:
            raise GuiError(
                f"candidate {index} cannot be adopted: "
                f"{_adopt_refusal(candidate, best)}",
                code="ADOPT_GATED", status=409, where=["candidate"])
        from ..indexing.workflow import structure_from_candidate

        space_group = body.get("space_group") or None
        try:
            structure = structure_from_candidate(
                candidate, space_group=space_group,
                name=str(body.get("name") or "indexed"))
        except (ValueError, RuntimeError) as exc:
            raise GuiError(str(exc), where=["space_group"]) from None
        a, b, c = candidate.cell[:3]
        label = (f"adopted indexed cell {a:.4f} {b:.4f} {c:.4f} Å "
                 f"({candidate.system}, {space_group or candidate.lattice_group})")
        node = p.refinement.edit(structure=structure, label=label)
        if p.doc.mode != "lebail":
            p.doc.mode = "lebail"
            p.save()
        sg = f", space_group={space_group!r}" if space_group else ""
        return {"node_id": node, "mode": p.doc.mode,
                "api_call": f"session.adopt_candidate({index}{sg})",
                **self.structure()}

    # ------------------------------------------------------------------
    # series (WP-1016)
    # ------------------------------------------------------------------
    def series(self) -> dict:
        """The staged series, its chain settings, and the protocol it inherits.

        Answers before any file is staged — an empty list plus the defaults *is*
        the empty state, and a client needs the ``choices``/``carry_help`` arms to
        draw the editor at all.  Needs a project, because the protocol it reports
        (mode, plan, limits, exclusions) is the project's.
        """
        p = self._need_project()
        plan = self._effective_plan()
        with self._cond:
            entry = self._series_run
            busy = self._state != "idle" and self._run.get("kind") == "series"
        return series_mod.setup_payload(
            self._series, running=busy, has_result=entry is not None,
            mode=p.doc.mode, plan_preset=self.plan()["preset"],
            n_stages=len(plan.stages))

    def series_put(self, body: dict) -> dict:
        """Replace the staged list and/or the chain settings.

        A whole-list PUT rather than add/remove/reorder verbs: the order *is* the
        series, so every edit a panel makes is "here is the series now", and one
        round trip cannot leave the server holding an order nobody chose.  Every
        file is read here (:func:`series.members_from`), which is WP-1014's
        two-phase property at N files — a file that does not parse is a message
        about that file rather than a chain that dies half way through.

        Idle-gated: the settings are what the next run will be *called* with.
        """
        self._require_idle()
        self._need_project()
        unknown = set(body) - {"patterns", "carry", "refit", "direction", "x_label"}
        if unknown:
            raise GuiError(f"unknown series setting(s): {sorted(unknown)}; the "
                           "mode, plan, limits and excluded regions are the "
                           "project's and are set through its own verbs",
                           where=sorted(unknown))
        setup = self._series
        carry = body.get("carry", setup.carry)
        refit = body.get("refit", setup.refit)
        direction = body.get("direction", setup.direction)
        try:
            series_mod.check_settings(carry, refit, direction)
            members = (series_mod.members_from(body["patterns"], self.uploads)
                       if "patterns" in body else setup.members)
        except UploadRefused as exc:
            raise GuiError(str(exc), code=exc.code, status=exc.status,
                           where=["patterns"]) from None
        except ValueError as exc:
            raise GuiError(str(exc), where=["patterns"]) from None
        self._series = series_mod.SeriesSetup(
            members=list(members), carry=[str(g) for g in carry], refit=refit,
            direction=direction,
            x_label=str(body.get("x_label", setup.x_label) or "index"))
        return self.series()

    def series_result(self) -> dict:
        """The last series answer: entries, trajectories, and the fences.

        Session-scoped like ``Refinement.result_`` and for the same reason — a
        ``SeriesResult`` is a computation over patterns the project does not own,
        so there is nothing on disk for it to be the stale view of.
        """
        self._need_project()
        with self._cond:
            entry = self._series_run
            busy = self._state != "idle" and self._run.get("kind") == "series"
        if entry is None:
            raise GuiError(
                "a series run is in flight; follow /api/events" if busy
                else "no series has completed in this session yet; stage the "
                     "patterns with PUT /api/series, then POST /api/series/run",
                code="NO_SERIES_RESULT", status=409)
        runner = entry["runner"]
        return series_mod.result_payload(
            entry["result"], entry["backward"], running=busy,
            curves=[bool(r.two_theta) for r in runner.results_])

    def series_window(self, index: int, lo: float | None = None,
                      hi: float | None = None, max_points: int = 4000) -> dict:
        """One series member's curves, through the *same* window arithmetic.

        :func:`curve_window`, so the σ policy and the decimation are the project
        plot's (CLAUDE.md: every weighted residual divides by ``sig()``).  The
        masked-channel arm is computed from this member's own pattern through
        ``project.fitted_mask`` — the one authority — because the protocol
        applied to it was the project's while the *pattern* was not.
        """
        entry = self._series_entry()
        runner = entry["runner"]
        if not 0 <= index < len(runner.results_):
            raise GuiError(
                f"no series pattern {index}; the run reached "
                f"{len(runner.results_)}", code="NOT_FOUND", status=404,
                where=["index"])
        res = runner.results_[index]
        if not res.two_theta:
            raise GuiError("this series pattern carries no curves",
                           code="NO_RESULT", status=409)
        member = entry["members"][index]
        return {"index": index, "label": member["label"], "x": member["x"],
                **curve_window(res, lo, hi, max_points,
                               weighted=bool(member["has_sigma"])),
                **self._series_masked_arm(index, lo, hi, max_points)}

    def _series_masked_arm(self, index: int, lo: float | None, hi: float | None,
                           max_points: int) -> dict:
        """The channels this member's fit masked, for the same reason as WP-1033.

        A result carries only the channels ``compile_model`` kept, so without this
        the per-pattern plot autoranges *inside* the fit range and the protocol is
        invisible in a picture of its own output.  There is no ``stale`` arm: a
        series member's curves are the run's and cannot be re-fitted under a new
        protocol without re-running the whole chain, which replaces the answer.
        """
        from ..project import fitted_mask

        entry = self._series_entry()
        data = entry["data"][index]
        keep = fitted_mask(data, self._need_project().doc.two_theta_limits)
        tt_all, y_all = data.tt(), data.y()
        out = ~keep
        if lo is not None:
            out &= tt_all >= lo
        if hi is not None:
            out &= tt_all <= hi
        if not out.any():
            return {"excluded": {"two_theta": [], "y_obs": []}, "n_excluded": 0}
        tt, y = tt_all[out], y_all[out]
        idx = decimation_index(tt, [y], max(2, max_points // 4))
        return {"excluded": {"two_theta": tt[idx].tolist(),
                             "y_obs": y[idx].tolist()},
                "n_excluded": int(out.sum())}

    def series_history(self, index: int) -> dict:
        """One series member's own history tree — read-only, and that is the point.

        There is one tree per pattern, never one for the series
        (``TreeHeader.data_fingerprint`` pins a tree to its data), so a node here
        **cannot be checked out** into this project: its state was fitted against
        another pattern, and restoring it would be the silent rebinding
        ``Project.open`` refuses.  What it is for is reading — the warm-start link
        is recorded in the root node's ``notes``
        (``series_warm_start_tree``/``…_node``), so this payload is what makes a
        chain navigable.
        """
        entry = self._series_entry()
        runner = entry["runner"]
        if not 0 <= index < len(runner.trees_):
            raise GuiError(
                f"no series pattern {index}; the run reached "
                f"{len(runner.trees_)}", code="NOT_FOUND", status=404,
                where=["index"])
        tree = runner.trees_[index]
        if tree is None:  # pragma: no cover - the GUI always runs with history
            raise GuiError("this series was run without history",
                           code="NO_HISTORY", status=409)
        member = entry["members"][index]
        return {"index": index, "label": member["label"],
                "checkout": False, **tree_payload(tree)}

    def _series_entry(self) -> dict:
        with self._cond:
            entry = self._series_run
        if entry is None:
            raise GuiError("no series has completed in this session yet",
                           code="NO_SERIES_RESULT", status=409)
        return entry

    # ------------------------------------------------------------------
    # results
    # ------------------------------------------------------------------
    def result(self) -> dict:
        """The last result without its curves (they go through ``result_window``).

        A 40 000-point pattern is five arrays of 40 000 floats — ~4 MB of JSON
        that a browser then decimates for a plot it can only draw a few thousand
        points of.  So the arrays are excluded here and served per window, and
        what is left is the whole of the rest: statistics, refined values with
        esds, per-stage outcomes, diagnostics, QPA, absorption, provenance.

        ``maturity`` is WP-1029's one honest signal that a fit is hopeless, and
        it is deliberately **not** a new word.  It quotes the FitReport's own
        `MATURITY_MAX_RWP` — the Rwp past which Layer 1 refuses to say anything
        about individual parameters — so a client can stop rendering such a fit
        in the same register as a good one without inventing a judgement, and
        without touching the ``status`` vocabulary (a run that reaches this
        state still reports ``converged``, which is WP-1028's to fix and not
        this route's).  Served here rather than derived in the client for the
        reason ``held_because`` travels on a parameter row: a threshold the
        package owns must not have a second copy in TypeScript.
        """
        from ..report.schemas import MATURITY_MAX_RWP

        res = self._need_result()
        payload = res.model_dump(mode="json", exclude={
            "two_theta", "y_obs", "y_calc", "y_background", "sigma"})
        payload["curves"] = {
            "n_points": len(res.two_theta),
            "two_theta_range": ([res.two_theta[0], res.two_theta[-1]]
                                if res.two_theta else None)}
        rwp = float(res.statistics.rwp)
        payload["maturity"] = {
            "immature": rwp > MATURITY_MAX_RWP,
            "max_rwp": MATURITY_MAX_RWP,
            "message": (
                f"Rwp {rwp:.1%} is past the point where the report will speak "
                f"about individual parameters (Layer 1 abstains above "
                f"{MATURITY_MAX_RWP:.0%}). At this level the usual cause is not "
                f"a parameter but a premise: check that the structure and the "
                f"pattern are of the same specimen, and read Layer 0's "
                f"unmatched peaks before changing anything."
                if rwp > MATURITY_MAX_RWP else ""),
        }
        return {"result": payload}

    def result_window(self, lo: float | None = None, hi: float | None = None,
                      max_points: int = 4000) -> dict:
        """Observed, calculated, background and weighted residual over a window.

        Decimated with ``viz.compare.decimation_index`` — bucket min *and* max of
        every curve, never striding, so zooming out cannot drop a peak top and
        make a bad fit look clean.

        ``max_points`` is a **budget, not a ceiling**: the index set is the union
        of three curves' per-bucket extrema over ``max_points // 2`` buckets, so
        it can come back larger (measured: 4132 points for a 4200-point pattern
        at a budget of 4000).  ``n_returned`` is therefore the length to trust,
        and a client sizing an array from ``max_points`` would be wrong.

        The arithmetic is :func:`curve_window`, shared with the series panel's
        per-pattern route (WP-1016) for the reason every weighted residual in this
        package divides by ``RefinementResult.sig()``: a second window builder
        would be a second σ policy, which is the class of bug WP-1029 (s) found.
        What stays here is what only a *project's* result has — the masked
        channels and the ``stale`` comparison, both of which need
        ``Project.fitted_mask``.

        **Three residuals, and one of them cannot be derived from the others**
        (WP-1029).  ``delta_raw`` is obs − calc and ``delta`` is that over σ —
        either could be recomputed in a client from ``y_obs``/``y_calc``, but
        the σ is :meth:`RefinementResult.sig`, the same one the matplotlib and
        plotly panels divide by, so the picture cannot depend on which of them
        drew it.  ``cumulative_chi2`` is the one that is genuinely not derivable: it is
        Σ(Δ/σ)² accumulated over **every** point of the window and decimated
        afterwards, so it still ends at the window's true χ².  Summing the
        decimated subset instead would understate it by whatever the dropped
        points contributed, which on a wide view is most of them.

        The index set is deliberately computed from the same three curves as
        before, so adding these did not change which points come back: a
        cumulative curve is monotone, so it has no peak a bucket could miss.

        ``weighted`` is **not** "is ``delta`` divided by something" — it always
        is, because the fit always weighted by something.  It is whether that
        something was *measured*: ``DataRef.has_sigma``, the file's esd column
        against the Poisson ``√max(y,1)`` estimate, which is the same fact the
        text document renders as "σ from file".  It cannot be read off the
        result, whose ``sigma`` array has already collapsed the two into one
        list of floats; reading ``bool(res.sigma)`` instead — as this did until
        WP-1029 (s) — asked "is this a *pre-v0.2* result", a question whose
        answer is always True for anything this GUI can produce.  So the flag
        was a constant, the client's no-esd branch was unreachable, and a
        Poisson fit got its axis labelled ``(obs−calc)/σ`` with nothing saying
        the σ was an assumption.
        """
        res = self._need_result()
        if not res.two_theta:
            raise GuiError("this result carries no curves", code="NO_RESULT",
                           status=409)
        return {**curve_window(res, lo, hi, max_points,
                               weighted=self._need_project().data_ref.has_sigma),
                **self._masked_arm(lo, hi, max_points)}

    def _masked_arm(self, lo: float | None, hi: float | None,
                    max_points: int) -> dict:
        """The measured points this window covers that the protocol **masks**.

        Measured before it was written (WP-1033): a result carries only the
        channels ``compile_model`` kept, so with ``two_theta_limits`` set the
        plot's x-axis autoranges *inside* the fit range and a user cannot see
        what they cut — on the synthetic fixture, a 3–24° pattern came back as
        8.005–18.990°, with zero points inside a 3° exclusion.  A band shaded
        over that is a band over nothing.  So the excluded channels travel
        beside the fitted ones, decimated the same way, and the client draws
        them recessively under the shading.

        ``stale`` is the other half, and it is the one thing on this route that
        is about *disagreement*: settings persist on the verb while curves move
        only on a run, so between an exclusion and the next fit the result on
        screen was computed over a different channel set (measured: 586 points
        inside the new band still in the residual).  The comparison is exact —
        the fitted 2θ values, not their count — because two different masks can
        keep the same number of channels.
        """
        import numpy as np

        p = self._need_project()
        keep = p.fitted_mask()
        tt_all, y_all = p.data.tt(), p.data.y()
        # read once: the worker swaps the result wholesale (``_need_result``)
        res = p.refinement.result_
        stale = res is None or not np.array_equal(
            tt_all[keep], np.asarray(res.two_theta, dtype=float))
        out = ~keep
        if lo is not None:
            out &= tt_all >= lo
        if hi is not None:
            out &= tt_all <= hi
        if not out.any():
            return {"excluded": {"two_theta": [], "y_obs": []},
                    "n_excluded": 0, "stale": stale}
        tt, y = tt_all[out], y_all[out]
        # a quarter of the budget: these points are context, and spending the
        # same 4000 on them as on the fit would halve the fitted curve's detail
        idx = decimation_index(tt, [y], max(2, max_points // 4))
        return {"excluded": {"two_theta": tt[idx].tolist(),
                             "y_obs": y[idx].tolist()},
                "n_excluded": int(out.sum()), "stale": stale}

    def report(self, plan: str | None = None) -> dict:
        """The three-layer :class:`FitReport` for the last fit, plus what applies.

        Needs the compiled model, so it is idle-only: Layers 1-2 read the
        derivative expansion of the state a stage would be rewriting.

        ``apply`` runs **parallel to** ``report["suggested_actions"]``, one entry
        per action in the same order, and says whether :meth:`report_apply` would
        act on it and what it would run.  Parallel rather than keyed by kind
        because a kind is not unique — two textured phases emit two
        ``refine_preferred_orientation`` actions — and served here rather than
        computed in the client for the reason ``held_because`` travels on a
        parameter row: a button's enabled-ness and the route's willingness to act
        must not be two answers.
        """
        report = self._report_object(plan)
        # both hoisted: ``_held`` rebuilds a ParameterTable and ``_indexing`` probes
        # every optional dependency's import, and a report carries a dozen actions
        held, indexing = self._held(), _indexing()
        return {"report": report.model_dump(mode="json"),
                "apply": [describe_action(a, held=held, indexing=indexing)
                          for a in report.suggested_actions]}

    def _held(self) -> dict[str, str]:
        """Every parameter path → why it is held, ``""`` when it is refinable.

        The reachability half of ``report.apply`` reads this rather than a list of
        refinable paths, so a refusal can quote ``held_because`` verbatim instead
        of guessing which of the three reasons applies.
        """
        return {row.path: row.held_because
                for row in self._need_project().parameters()}

    def _report_object(self, plan: str | None = None):
        self._require_idle()
        p = self._need_project()
        self._need_result()
        try:
            return p.refinement.report(plan=plan or self._effective_plan())
        except RuntimeError as exc:
            raise GuiError(str(exc), code="NO_RESULT", status=409) from None

    def report_apply(self, body: dict) -> dict:
        """Carry out one suggested action — as one stage, through ``run``.

        The action is looked up in a report built **now**, not taken from the
        body: a client-supplied glob would make this a second spelling of
        ``POST /api/run``, and the veto (which the strategy engine holds) is a
        server-side judgement that a stale panel must not be able to skip.
        ``paths`` is only a disambiguator — a kind can appear twice, and guessing
        which of two textured phases was meant is exactly the confident-wrong
        singleton this report is built not to produce.

        Returns before the run finishes, like every other run: what is new is
        ``undo`` (the head to check out to get back — an applied action is a
        history node, so undo needs no inverse verb) and ``chi2_before``, which is
        what lets a panel put the *observed* Δχ² beside the predicted one.
        """
        self._require_idle()
        p = self._need_project()
        kind = _need(body, "kind")
        report = self._report_object(body.get("plan"))
        action = _pick_action(report, kind, body.get("paths"))
        why = refusal(action, held=self._held(), indexing=_indexing())
        if why:
            raise GuiError(
                f"{kind} cannot be applied here: {why}", code="ACTION_NOT_APPLICABLE",
                status=409, where=list(action.parameter_paths))
        stage = stage_for(action)
        undo = p.refinement._head_id
        before = p.refinement.result_.statistics.chi2
        frame = self.run({"kind": "stage", "stage": stage.model_dump(mode="json")})
        return {"applied": {"kind": action.kind,
                            "confidence": action.confidence,
                            "rationale": action.rationale,
                            "expected_delta_chi2": action.expected_delta_chi2,
                            "stage": stage.model_dump(mode="json")},
                "api_call": api_call(stage), "undo": undo,
                "chi2_before": before, **frame}

    # ------------------------------------------------------------------
    # history
    # ------------------------------------------------------------------
    def history(self) -> dict:
        """The DAG as nodes a client can draw, without any node's full state.

        A node is ~10 kB of structure and instrument; a tree of thirty is 300 kB
        of models nobody is looking at.  What a worktree panel needs is the
        shape, the action, the metrics and the diagnostics count — plus
        ``api_call``, which is the node's equivalent public-API line and turns
        the log into a script a user can copy.
        """
        return tree_payload(self._need_project().history)

    def history_diff(self, a: str, b: str) -> dict:
        tree = self._need_project().history
        try:
            diff = tree.diff(a, b)
        except KeyError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404) from None
        return {"a": tree.resolve(a), "b": tree.resolve(b),
                "diff": {path: list(pair) for path, pair in diff.items()}}

    def history_compare(self, node_ids: list[str]) -> dict:
        tree = self._need_project().history
        try:
            return {"rows": tree.compare(node_ids)}
        except KeyError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404) from None

    def history_checkout(self, body: dict) -> dict:
        """Restore a node's state as the working state (``git checkout``)."""
        self._require_idle()
        p = self._need_project()
        node_id = _need(body, "node_id")
        try:
            p.refinement.checkout(node_id)
        except KeyError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404) from None
        return {"head": p.refinement._head_id, **self.params()}

    def history_branch(self, body: dict) -> dict:
        """Check a node out **and name it** — which is what a branch is here.

        Worth being explicit, because the word promises something this DAG does
        not have: there are no moving refs, only ``head``.  A fork appears when
        you run a stage from a node that already has a child, so "branch" is not
        a separate act — the useful half is *naming the fork point* so a history
        panel can label the lane, and that is a tag.  ``Refinement.branch``
        (a second in-process working tree over one tree) has no meaning for a
        one-project session and is not what this route calls.
        """
        p = self._need_project()
        node_id = _need(body, "node_id")
        name = str(body.get("name") or "").strip()
        out = self.history_checkout({"node_id": node_id})
        if name:
            self.history_tag({"node_id": node_id, "name": name})
        return {"branched_from": p.history.resolve(node_id), "name": name, **out}

    def history_tag(self, body: dict) -> dict:
        p = self._need_project()
        try:
            p.history.tag(_need(body, "node_id"), _need(body, "name"))
        except (KeyError, ValueError) as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404) from None
        return {"tags": {k: v for k, v in p.history.refs.items() if k != "head"}}

    def history_annotate(self, body: dict) -> dict:
        p = self._need_project()
        try:
            p.history.annotate(_need(body, "node_id"), label=body.get("label"),
                               notes=body.get("notes") or {},
                               scores=body.get("scores") or {})
        except KeyError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404) from None
        return {"annotated": p.history.resolve(body["node_id"])}

    # ------------------------------------------------------------------
    # exports
    # ------------------------------------------------------------------
    def export(self, kind: str, body: dict) -> dict:
        """Write an export into ``<project>/exports/``.

        Idle-only, and not because it writes: ``write_cif`` and the reflection
        table read the *compiled model*, which a running stage owns.
        """
        self._require_idle()
        p = self._need_project()
        if kind not in _EXPORT_DEFAULTS:
            raise GuiError(f"unknown export {kind!r}; "
                           f"available: {sorted(_EXPORT_DEFAULTS)}",
                           code="NOT_FOUND", status=404)
        res = self._need_result()
        target = self._export_target(body.get("filename") or _EXPORT_DEFAULTS[kind])
        ref = p.refinement
        try:
            if kind == "cif":
                ref.write_cif(target)
            elif kind == "reflections":
                ref.write_reflection_table(target)
            elif kind == "qpa":
                ref.write_qpa_table(target)
            elif kind == "html":
                from ..viz.html import write_html

                write_html(res, str(target))
            else:
                target.write_text(res.model_dump_json(indent=2), encoding="utf-8")
        except RuntimeError as exc:
            # "no QPA on this result (Rietveld fits only)" is the interesting
            # one: a Le Bail fit has no weight fractions, and saying so beats
            # writing an empty table
            raise GuiError(str(exc), code="EXPORT_UNAVAILABLE", status=409) from None
        return {"kind": kind, "path": str(target), "name": target.name,
                "bytes": target.stat().st_size}

    def _export_target(self, filename: str) -> Path:
        p = self._need_project()
        root = p.exports_dir.resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = (root / filename).resolve()
        if not target.is_relative_to(root):
            raise GuiError(f"{filename!r} escapes the project's exports directory",
                           where=["filename"])
        return target

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _adopt(self, project: Project) -> None:
        with self._cond:
            self.project = project
            self._events.clear()
            self._seq = 0
            self._n_eval = 0
            self._run = _idle_run()
            self._index_result = None
            self._extinction = None
            self._peak_ed = None
            # a series is staged against a project's protocol and warm-started
            # from its models, so another project's series is not this one's
            self._series = series_mod.SeriesSetup()
            self._series_run = None
            self._cond.notify_all()
        self._remember(project.path)

    def _remember(self, path: Path) -> None:
        entry = {"path": str(Path(path).resolve()), "opened_utc": _utcnow()}
        kept = [e for e in self.recent() if e["path"] != entry["path"]]
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            (self.state_dir / "recent.json").write_text(
                json.dumps([entry, *kept][:_MAX_RECENT], indent=2), encoding="utf-8")
        except OSError:
            pass  # a read-only home is not a reason to fail opening a project

    def _need_project(self) -> Project:
        if self.project is None:
            raise GuiError("no project is open; POST /api/project/new or "
                           "/api/project/open first",
                           code="NO_PROJECT", status=409)
        return self.project

    def _need_result(self):
        p = self._need_project()
        result = p.refinement.result_  # read once: the worker swaps it wholesale
        if result is None:
            raise GuiError("no fit has been run in this session yet (a reopened "
                           "project resumes at its head, which carries state and "
                           "metrics but no curves — run a stage to get a result)",
                           code="NO_RESULT", status=409)
        return result

    def _require_idle(self) -> None:
        with self._cond:
            if self._state != "idle":
                raise GuiError(
                    f"a refinement is {self._state}; this verb would change the "
                    "model a compiled stage was built from (frozen-per-stage "
                    "discreteness). Cancel it or wait for it to finish.",
                    code="RUN_IN_FLIGHT", status=409)

    def _effective_plan(self, override: Any = None):
        """The plan a run would use: an override, the document's, or the default."""
        p = self._need_project()
        if override is not None:
            return resolve_plan(_as_plan_argument(override), p.doc.mode)
        if p.doc.plan is not None:
            return p.doc.plan.to_plan()
        return resolve_plan("mccusker_default", p.doc.mode)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def curve_window(res, lo: float | None, hi: float | None, max_points: int, *,
                 weighted: bool) -> dict:
    """One result's curves over a 2θ window, decimated — the shared arithmetic.

    Module-level and taking the result explicitly, because it has two callers
    that hold results from different places: ``GuiSession.result_window`` (the
    project's own fit) and ``GuiSession.series_window`` (one member of a series,
    which the project does not own).  Everything about *what* is drawn is decided
    here once, in particular the σ — ``RefinementResult.sig()``, never a
    re-derivation — so the two panels cannot draw residuals under two policies.

    ``weighted`` is the caller's fact, not this function's: it is whether the σ
    was **measured** (``DataRef.has_sigma``) rather than whether ``delta`` is
    divided by something, which it always is.  See ``result_window``'s docstring
    for what happens when that distinction is lost.
    """
    import numpy as np

    tt = np.asarray(res.two_theta, dtype=float)
    mask = np.ones(len(tt), dtype=bool)
    if lo is not None:
        mask &= tt >= lo
    if hi is not None:
        mask &= tt <= hi
    if not mask.any():
        return {"two_theta": [], "y_obs": [], "y_calc": [], "y_background": [],
                "delta": [], "delta_raw": [], "cumulative_chi2": [],
                "weighted": weighted, "ticks": {}, "n_total": 0,
                "n_returned": 0, "max_points": max_points}
    y_obs = np.asarray(res.y_obs)[mask]
    y_calc = np.asarray(res.y_calc)[mask]
    y_bkg = np.asarray(res.y_background)[mask] if res.y_background else None
    # σ over the whole pattern, then masked: RefinementResult.sig() floors
    # against the pattern's own median, and a window-local floor would make
    # the residual depend on how far the user happened to be zoomed in
    sigma = res.sig()[mask]
    tt = tt[mask]
    raw = y_obs - y_calc
    delta = raw / sigma
    # accumulated over every point, then decimated — see result_window
    cumulative = np.cumsum(delta**2)
    idx = decimation_index(tt, [y_obs, y_calc, delta], max_points)
    window = (float(tt[0]), float(tt[-1]))
    return {
        "two_theta": tt[idx].tolist(),
        "y_obs": y_obs[idx].tolist(),
        "y_calc": y_calc[idx].tolist(),
        "y_background": [] if y_bkg is None else y_bkg[idx].tolist(),
        "delta": delta[idx].tolist(),
        "delta_raw": raw[idx].tolist(),
        "cumulative_chi2": cumulative[idx].tolist(),
        # whether σ was the file's or a Poisson fallback is the *server's*
        # fact: a client labelling its axis without it can only guess
        "weighted": weighted,
        # every emission line's ticks, not just the primary — Layer 0 flags
        # each Kα2 peak as an impurity otherwise (CLAUDE.md)
        "ticks": {phase: [t for t in ticks if window[0] <= t <= window[1]]
                  for phase, ticks in res.ticks.items()},
        "window": list(window), "n_total": int(mask.sum()),
        "n_returned": len(idx), "max_points": max_points,
    }


def tree_payload(tree) -> dict:
    """A history tree as nodes a client can draw, without any node's full state.

    ``GuiSession.history``'s body, taking the tree explicitly: a series is N
    trees (one per pattern, each pinned to its own data fingerprint), and the
    panel that walks into one of them needs the same node shape the project's own
    history panel already renders — `lib/history.ts`'s lane layout is reusable
    only if the payload is identical.
    """
    tags: dict[str, list[str]] = {}
    for name, node_id in tree.refs.items():
        if name != "head":
            tags.setdefault(node_id, []).append(name)
    nodes = []
    for node_id in tree.order:
        node = tree.nodes[node_id]
        stats = node.metrics.statistics
        nodes.append({
            "id": node.id, "parents": list(node.parents),
            "label": node.label, "created_utc": node.created_utc,
            "kind": node.action.kind, "name": node.action.name,
            "action": node.action.model_dump(mode="json"),
            "api_call": node.action.api_call(),
            "status": node.metrics.status,
            "n_iterations": node.metrics.n_iterations,
            "rwp": None if stats is None else stats.rwp,
            "gof": None if stats is None else stats.gof,
            "n_free": None if stats is None else stats.n_free_parameters,
            "n_diagnostics": len(node.diagnostics),
            "diagnostics": [d.model_dump(mode="json") for d in node.diagnostics],
            "tags": tags.get(node.id, []),
            "children": [c.id for c in tree.children(node.id)],
            "scores": dict(node.scores), "notes": dict(node.notes),
        })
    return {"tree_id": tree.header.tree_id, "head": tree.head,
            "root": None if tree.root is None else tree.root.id,
            "n_nodes": len(tree), "nodes": nodes}


def _summarize_refinement(result, _token) -> dict:
    """The run-record fields a finished fit or stage supplies."""
    return {"status": result.status, "rwp": result.statistics.rwp,
            "gof": result.statistics.gof, "node_id": result.node_id,
            "completed_stages": [s.name for s in result.stages]}


def _summarize_index(result, token) -> dict:
    """The run-record fields a finished indexing search supplies.

    No Rwp, no node — an ``IndexingResult`` is not a refinement.  The status is
    read off the token because a cancelled search *returns* what it has rather
    than raising (it has no seeded stage to abandon).
    """
    cancelled = token is not None and bool(token)
    return {"status": "cancelled" if cancelled else "completed",
            "completed_stages": [f"engine:{name}"
                                 for name in result.engines_run]}


def _series_stage_name(data: dict, index: Any) -> str:
    """What the progress pill says while a series pattern is being fitted.

    The label alone would be a lie twice over on the same number: a
    ``direction="both"`` run walks every pattern a second time in reverse (so the
    counter goes 1…N and back to 1, which reads as a restart unless the pass is
    named), and a reseeded pattern is fitted **twice** by design — the warm fit
    and the cold restart that judges it.  Both facts are already on the event's
    open ``data``; this is the two of them made readable.
    """
    name = str(data.get("series_label") or index)
    if data.get("series_pass") == "backward":
        name += " (backward)"
    if data.get("series_cold"):
        name += " (cold restart)"
    return name


def _summarize_series(result, token) -> dict:
    """The run-record fields a finished series supplies.

    ``rwp``/``gof`` are the **last** entry's, not an average: a series has N of
    each and averaging them would invent a statistic no fit computed.  The status
    is read off the token for the same reason an indexing run's is — a cancelled
    series returns the patterns that completed rather than raising (the module
    docstring of :mod:`pxrdref.sequential` says why that is WP-1006's rule and
    not an exception to it) — and ``completed_stages`` is the patterns reached, so
    the header's stage list reads as the chain's progress.
    """
    cancelled = token is not None and bool(token)
    last = result.entries[-1].statistics if result.entries else None
    return {"status": "cancelled" if cancelled else "completed",
            "rwp": None if last is None else last.rwp,
            "gof": None if last is None else last.gof,
            "completed_stages": [e.label or str(e.index) for e in result.entries]}


def _summarize_extinction(result, token) -> dict:
    """The run-record fields a finished extinction screen supplies.

    Like an indexing search, a cancelled screen *returns* what it has (the
    unfitted classes stay ``screened=False`` and ``best_or_none`` abstains),
    so the status is read off the token.
    """
    cancelled = token is not None and bool(token)
    return {"status": "cancelled" if cancelled else "completed",
            "completed_stages":
                [f"classes:{result.n_screened}/{result.n_classes}"]}


def _adopt_refusal(candidate, best) -> str:
    """Why ``best_or_none()`` would not return this candidate, in one line."""
    if candidate.confidence != "high":
        caveats = ", ".join(candidate.confidence_caveats)
        return (f"confidence is {candidate.confidence!r}"
                + (f" ({caveats})" if caveats else "")
                + "; only the one candidate best_or_none() returns can be "
                  "adopted")
    if candidate.ambiguity:
        return ("a geometrically indistinguishable lattice exists; the "
                "discriminating reflections are listed on the candidate")
    return ("more than one candidate reached 'high'; the result cannot "
            "single one out")


def _idle_run() -> dict:
    return {"kind": None, "name": "", "status": None, "stage": None,
            "stage_index": None, "n_stages": None, "started_utc": None,
            "finished_utc": None, "elapsed": None, "rwp": None, "gof": None,
            "node_id": None, "completed_stages": [], "error": None}


def _parse_utc(stamp: str) -> float:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=UTC).timestamp()


def _locate(message: str, text: str) -> dict:
    """Attach a line number to a verb's refusal by finding the path it names.

    The verbs raise in their own words — ``'phases.0.cell.b' follows … as an
    affine tie``, ``phases.0.atoms.0.biso=999.0 lies outside its bounds`` — and a
    text editor needs a line, so the **path** is extracted from the message and
    matched against the document instead of the message being rewritten here.

    A row line carries its *local* path (``atoms.0.biso`` inside ``phase 0``), so
    the match is on a trailing dot-component of a full path, and the longest
    candidate wins: a tie message names both the refused path and its source, and
    the refused one is the one to point at.
    """
    candidates = sorted(re.findall(r"[A-Za-z_][\w*?]*(?:\.[\w*?]+)+", message),
                        key=len, reverse=True)
    for path in candidates:
        for n, line in enumerate(text.splitlines(), start=1):
            head = line.split("#", 1)[0].split()
            token = head[0] if head else ""
            if token and (token == path or path.endswith(f".{token}")):
                return {"line": n, "message": message, "where": path,
                        "text": line.rstrip()}
    return {"line": 0, "message": message, "where": "", "text": ""}


def _indexing() -> bool:
    """Whether this build has an indexing engine — a *derived* predicate.

    Read through ``capabilities()`` rather than by importing ``index``, so the one
    action whose availability is a build feature turns on by itself when WP-1024
    lands and nothing here has to be edited (WP-1007's rule).
    """
    return bool(_capabilities().features.get("indexing"))


def _pick_action(report, kind: str, paths: Any = None):
    """The one suggestion ``kind`` (and optionally ``paths``) names.

    ``FitReport.action`` returns the *first* match, which is wrong here: two
    textured phases emit two ``refine_preferred_orientation`` actions with
    different ``parameter_paths``, and applying the wrong one would free the wrong
    phase's March coefficient.  So an ambiguous request is refused and told how to
    disambiguate rather than resolved by position.
    """
    hits = [a for a in report.suggested_actions if a.kind == kind]
    if not hits:
        raise GuiError(
            f"this report suggests no {kind!r}; it suggests "
            f"{[a.kind for a in report.suggested_actions]}",
            code="NOT_FOUND", status=404, where=["kind"])
    if paths is not None:
        wanted = [str(p) for p in paths]
        exact = [a for a in hits if list(a.parameter_paths) == wanted]
        if not exact:
            raise GuiError(
                f"no {kind!r} suggestion carries paths {wanted}; this report has "
                f"{[list(a.parameter_paths) for a in hits]}",
                code="NOT_FOUND", status=404, where=["paths"])
        return exact[0]
    if len(hits) > 1:
        raise GuiError(
            f"{len(hits)} {kind!r} suggestions in this report; send 'paths' to say "
            f"which — {[list(a.parameter_paths) for a in hits]}",
            code="AMBIGUOUS_ACTION", where=["paths"])
    return hits[0]


def _need(body: dict, key: str):
    value = body.get(key)
    if value in (None, ""):
        raise GuiError(f"{key!r} is required", where=[key])
    return value


def _validate(model, payload, where: str):
    """``model.model_validate`` with pydantic's complaint kept addressable."""
    from pydantic import ValidationError

    if not isinstance(payload, dict):
        raise GuiError(f"{where} must be an object", where=[where])
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        # a model-level error has an empty loc; ``"structure."`` would be a
        # dot-path to nothing, and the GUI highlights fields by this string
        paths = [".".join([where, *(str(p) for p in err["loc"])])
                 for err in exc.errors()]
        raise GuiError(f"{where} failed validation: {exc.error_count()} error(s); "
                       f"{exc.errors()[0]['msg']} at {paths[0]}",
                       where=paths) from None


#: The dot-path a ``ParameterTable`` refusal opens with (``phases.0.atoms.3: the
#: anisotropic tensor …``, ``phases.0.atoms.3 sits on a fully fixed special
#: position``).  ``Refinement.edit`` prefixes its own sentence, so this
#: *searches* rather than anchors — it is what lets :meth:`GuiSession._edit`
#: address the field without parsing a sentence it does not own.
_LEADING_PATH = re.compile(r"\b((?:phases|instrument)\.[\w.]*[\w])")


def _as_structure(payload, uploads=None) -> Structure:
    """A :class:`Structure` from an inline dict, ``{"cif": path}`` or an upload.

    Every route into the model passes through here, which is where the species
    check belongs: a structure carrying a scattering species no form-factor table
    knows validates fine and fails at *stage compile*, a long way from the field
    it was typed in.  Refusing at the boundary is a GUI judgement, not a schema
    change — the Python API still accepts it — and the message names the atom.
    """
    if isinstance(payload, dict) and ("cif" in payload or "upload" in payload):
        from ..crystallography.cif import structure_from_cif

        staged = None
        if "upload" in payload:
            if uploads is None:  # pragma: no cover - every caller passes one
                raise GuiError("uploads are not available here",
                               where=["structure.upload"])
            try:
                staged = uploads.get(str(payload["upload"]), "cif")
            except UploadRefused as exc:
                raise GuiError(str(exc), code=exc.code, status=exc.status,
                               where=["structure.upload"]) from None
            path = str(staged.path)
        else:
            path = _need(payload, "cif")
        try:
            # aniso is opt-in on purpose: reading a file must not silently change
            # what a plan frees (CLAUDE.md, anisotropic ADPs)
            structure = structure_from_cif(
                path, aniso=bool(payload.get("aniso", False)),
                phase_name=payload.get("phase_name"))
        except (OSError, ValueError, RuntimeError) as exc:
            name = path if staged is None else staged.filename
            message = str(exc) if staged is None else scrub(str(exc), staged)
            raise GuiError(f"could not read structure from {name}: {message}",
                           where=["structure.cif"]) from None
    else:
        structure = _validate(Structure, payload, "structure")
    unknown = unknown_species(structure)
    if unknown:
        named = ", ".join(f"{u['label']} ({u['species']})" for u in unknown)
        raise GuiError(
            f"{len(unknown)} atom(s) carry a scattering species this build has "
            f"no form factor for: {named}. A fit would fail at stage compile "
            "with the same lookup; edit the species (ions fall back to the "
            "neutral atom, so 'O2-' is fine and 'D' is not).",
            code="UNKNOWN_SPECIES",
            where=[f"{u['path']}.species" for u in unknown])
    return structure


def _as_instrument(payload, uploads=None) -> Instrument:
    """An :class:`Instrument` from an inline dict, a preset spec, or an upload.

    The preset form is what the import wizard sends: a geometry and an anode
    name, with the *wavelengths* supplied by the package's table rather than
    typed by a client (WP-0507's scale, kept in one place).
    """
    if payload is None:
        raise GuiError("'instrument' is required: Instrument has no default "
                       "source, and guessing an anode or a geometry would put a "
                       "wavelength nobody chose into every refined cell",
                       where=["instrument"])
    if isinstance(payload, dict) and "upload" in payload:
        from ..io.instrument_profile import load_instrument_profile

        if uploads is None:  # pragma: no cover - every caller passes one
            raise GuiError("uploads are not available here",
                           where=["instrument.upload"])
        try:
            staged = uploads.get(str(payload["upload"]), "instrument")
            return load_instrument_profile(staged.path)
        except UploadRefused as exc:
            raise GuiError(str(exc), code=exc.code, status=exc.status,
                           where=["instrument.upload"]) from None
        except (ValueError, OSError, KeyError) as exc:
            raise GuiError(str(exc), where=["instrument.upload"]) from None
    if isinstance(payload, dict) and "preset" in payload:
        try:
            return instrument_from_preset(payload)
        except UploadRefused as exc:
            raise GuiError(str(exc), code=exc.code, status=exc.status,
                           where=exc.where) from None
    return _validate(Instrument, payload, "instrument")


def _as_plan_argument(plan: Any):
    """A preset name or a plan spec, as something ``resolve_plan`` accepts."""
    if isinstance(plan, str):
        if plan not in PLAN_PRESETS:
            raise GuiError(f"unknown plan preset {plan!r}; "
                           f"available: {sorted(PLAN_PRESETS)}", where=["plan"])
        return plan
    return _validate(PlanSpec, plan, "plan").to_plan()

