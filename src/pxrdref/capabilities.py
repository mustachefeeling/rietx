"""What this build of pxrd-refine can do, as data (WP-1007).

One call a client makes once, so it never has to guess: which backends exist and
which are *installed*, which solvers and plan presets are registered, which
intensity modes and anodes are known, what ``read_pattern`` actually opens, and
which of the five versioned contracts it is talking to.

**Every arm is quoted from the live registry, never restated.** The lesson is
measured rather than stylistic: the fourth backend name arrived two days after
the third (WP-0408), and a hand-written list would have been wrong for those two
days while looking authoritative. ``tests/test_capabilities.py`` fails if a
member of ``BACKEND_NAMES``, ``SOLVERS``, ``PLAN_PRESETS``, ``Mode``, the anode
table or ``PATTERN_FORMATS`` is missing from its arm — the WP-0602 meta-test
pattern, one level up from ``agent.tool_definition()``.

The same rule shapes :attr:`Capabilities.features`: each flag is a **derived
predicate** — a schema field's presence, a top-level export's existence — and not
a literal ``True``. A literal is a claim that cannot rot loudly; a derivation
either keeps telling the truth or stops importing.  **But a derived flag rots
too, and it rots silently** (WP-1037): ``features["indexing"]`` asked
``hasattr(pr, "index")`` from the day it was written, while the export that
landed (WP-1024) is ``index_pattern`` — so the flag read ``False`` for the whole
life of the feature, and its test asserted the same ``hasattr`` and could never
fail.  The repair is to make the *name* data: :data:`_SURFACE_FLAGS` pairs each
flag with the export it claims, ``_features()`` derives the flags from that one
table, and the meta-test checks every name in it against ``pxrdref.__all__`` —
an authority the predicate itself never consults, which is what a tautology
lacks.
"""

from __future__ import annotations

import importlib.util
from typing import get_args

from pydantic import Field

from .backend.api import (
    BACKEND_NAMES,
    BACKEND_REQUIRES,
    EXPERIMENTAL_BACKENDS,
    backend_dtype_note,
)

# The anode and Kβ tables are module-private by history (several tests import
# them the same way), and are quoted rather than copied: the registry meta-test
# fails loudly if either name moves, which is the property that matters — see the
# module docstring on derivation over restatement.
from .background.diagnostics import _KBETA
from .history.events import EVENT_SCHEMA_VERSION
from .io.readers import PATTERN_FORMATS
from .optimize.least_squares import SOLVERS
from .refine import _VERSION
from .report.schemas import THRESHOLDS_VERSION
from .schemas.common import SCHEMA_VERSION, Base, Mode
from .schemas.instrument import _KA_DOUBLETS, _RADIATIONS
from .schemas.project import PROJECT_FORMAT_VERSION

# The plans arm iterates PLAN_INFO, not PLAN_PRESETS: the two are held in
# bijection by tests/test_params_surface.py, so quoting the one that carries the
# four facts a chooser needs keeps the arm complete without a second assertion
# about the same pair (WP-1007's inherited note from WP-1004).
from .strategy.staged import PLAN_INFO


class BackendCapability(Base):
    """A Jacobian backend, and whether this machine can actually run it."""

    name: str
    #: is its optional dependency importable *here* — the question a GUI's
    #: backend menu needs answered, which the registry alone cannot answer
    available: bool
    #: kept for validation and future work, not for production refinements
    #: (torch is an order of magnitude slower than the analytic numpy path and
    #: MPS two — see docs/milestones/v0.4.md)
    experimental: bool
    #: the distribution to install, or ``None`` when always available
    requires: str | None
    #: precision this backend computes at, for ``Provenance.dtype``
    dtype: str


class PlanCapability(Base):
    """A staged-plan preset with the four facts a chooser needs (``PLAN_INFO``)."""

    name: str
    title: str
    description: str
    modes: list[Mode]
    when_to_use: str


class AnodeCapability(Base):
    """A laboratory anode this package knows the emission wavelengths of."""

    name: str
    wavelengths: list[float]
    #: ``True`` for the ``"CuKa1"``-style entries: an incident-side
    #: monochromator has removed Kα2, so there is one line rather than two
    kalpha1_only: bool
    #: Kβ1,3 for the contamination check, or ``None`` when untabulated.  Not a
    #: modelled emission line — one |F|² cannot serve Kβ and Kα together.
    kbeta: float | None


class ReaderCapability(Base):
    """A pattern format, how it is recognised, and where its σ comes from."""

    name: str
    title: str
    extensions: list[str]
    sniff: str
    sigma: str
    #: reader keywords a caller may need to supply *and* record — ``block`` for
    #: pdCIF, because the same file reads as a different pattern without it
    options: list[str]


class Capabilities(Base):
    """The whole answer.  JSON-serialisable; WP-1008 serves it verbatim."""

    package_version: str
    #: the five versioned contracts a client can be talking to, all live values.
    #: The count moved from four to five when WP-1009 added the text document,
    #: which is the argument for putting them here rather than in prose: a client
    #: reads the arm, not a paragraph that has to be remembered.
    schema_version: str
    report_thresholds_version: str
    event_schema_version: str
    project_format_version: str
    #: ``pxt N`` — the line-oriented project document (WP-1009).  A client that
    #: offers a text pane needs it *before* fetching a document
    textdoc_format_version: str

    backends: list[BackendCapability] = Field(default_factory=list)
    solvers: list[str] = Field(default_factory=list)
    plans: list[PlanCapability] = Field(default_factory=list)
    modes: list[Mode] = Field(default_factory=list)
    anodes: list[AnodeCapability] = Field(default_factory=list)
    reader_formats: list[ReaderCapability] = Field(default_factory=list)
    features: dict[str, bool] = Field(default_factory=dict)


def capabilities() -> Capabilities:
    """Everything this build can do — see the module docstring."""
    # Local, and not for cost: ``pxrdref.gui`` imports the session, which imports
    # this module, so a top-level import here would be a cycle.  By call time the
    # package is initialised and the constant is reachable — still quoted from
    # where it is defined, never copied.
    from .gui.textdoc import FORMAT_VERSION as TEXTDOC_FORMAT_VERSION

    return Capabilities(
        package_version=_VERSION,
        schema_version=SCHEMA_VERSION,
        report_thresholds_version=THRESHOLDS_VERSION,
        event_schema_version=EVENT_SCHEMA_VERSION,
        project_format_version=PROJECT_FORMAT_VERSION,
        textdoc_format_version=TEXTDOC_FORMAT_VERSION,
        backends=[_backend(name) for name in BACKEND_NAMES],
        solvers=list(SOLVERS),
        plans=[PlanCapability(name=name, title=info.title,
                              description=info.description,
                              modes=list(info.modes),
                              when_to_use=info.when_to_use)
               for name, info in sorted(PLAN_INFO.items())],
        modes=list(get_args(Mode)),
        anodes=[_anode(name) for name in sorted(_RADIATIONS)],
        reader_formats=[
            ReaderCapability(name=f.name, title=f.title,
                             extensions=list(f.extensions), sniff=f.sniff,
                             sigma=f.sigma, options=list(f.options))
            for f in PATTERN_FORMATS],
        features=_features(),
    )


def _backend(name: str) -> BackendCapability:
    requires = BACKEND_REQUIRES.get(name)
    return BackendCapability(
        name=name,
        available=requires is None or importlib.util.find_spec(requires) is not None,
        experimental=name in EXPERIMENTAL_BACKENDS,
        requires=requires,
        dtype=backend_dtype_note(name),
    )


def _anode(name: str) -> AnodeCapability:
    lines = _RADIATIONS[name]
    doublet = name if name in _KA_DOUBLETS else name[:-1]
    return AnodeCapability(
        name=name,
        wavelengths=list(lines),
        kalpha1_only=name not in _KA_DOUBLETS,
        kbeta=_KBETA.get(doublet),
    )


#: Entry-point-shaped feature flags: flag → the top-level export whose existence
#: it reports.  One table, two consumers — ``_features()`` derives the flags from
#: it, and ``tests/test_capabilities.py`` checks every name in it against
#: ``pxrdref.__all__`` — because the two halves of a derived predicate (the name
#: asked about and the name that exists) can otherwise drift with the guarding
#: test asserting the same ``hasattr``, which is how ``indexing`` stayed
#: ``False`` from the day the feature shipped (see the module docstring).
_SURFACE_FLAGS: dict[str, str] = {
    "multi_histogram": "refine_multi",
    "sequential_series": "refine_sequential",
    "project_container": "Project",
    "background_estimation": "auto_background",
    "pattern_diagnostics": "diagnose",
    "peak_picking": "pick_peaks",
    "indexing": "index_pattern",
    "agent_json": "agent",
    # run control (WP-1006): a client that cannot cancel must not offer to
    "cancellation": "CancelToken",
}


def _features() -> dict[str, bool]:
    """Feature flags, every one of them derived (see the module docstring).

    The schema-shaped ones ask the model whether it has the field, so a
    correction that is removed or renamed cannot leave a flag behind claiming
    it; the surface-shaped ones ask the package for the export
    :data:`_SURFACE_FLAGS` names, so a flag flips on its own when its entry
    point lands — provided the name is right, which is the meta-test's job.
    """
    import pxrdref as pr

    from .schemas.instrument import Geometry, Source
    from .schemas.structure import Atom, Phase

    return {
        # corrections and model extensions, asked of the schemas
        "anisotropic_adp": "aniso" in Atom.model_fields,
        "preferred_orientation": "preferred_orientation" in Phase.model_fields,
        "stephens_strain": "microstrain" in Phase.model_fields,
        "secondary_extinction": "extinction" in Phase.model_fields,
        "restraints": "restraints" in Phase.model_fields,
        "surface_roughness": "surface_roughness" in Geometry.model_fields,
        "capillary_absorption": "mu_r" in Geometry.model_fields,
        "flat_plate_absorption": "mu_t" in Geometry.model_fields,
        "anomalous_dispersion": "dispersion" in Source.model_fields,
        # …and whether dispersion is ON unless declined, which moved in WP-1001
        # and is the one default whose position changes published numbers.  Read
        # off the field rather than by constructing a Source, which would need
        # arguments and could run validators — a capability query must not.
        "anomalous_dispersion_default_on": Source.model_fields["dispersion"]
        .get_default(call_default_factory=True) is not None,
        # entry points, asked of the package through the one table the
        # meta-test also reads
        **{flag: hasattr(pr, name) for flag, name in _SURFACE_FLAGS.items()},
    }
