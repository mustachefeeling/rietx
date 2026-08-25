"""rietx: API-first Rietveld refinement of powder X-ray diffraction data."""

from . import agent

# The background estimator and the model-free pattern diagnostics were reachable
# only as ``rietx.background.auto_background`` — this module never imported
# ``background`` at all — so the two calls a client makes *before* its first fit
# were the two it had to go digging for (WP-1007).  Remember the invariant: an
# estimated background is held additively or co-refined under a penalty, never
# subtracted.
from .background import auto_background, diagnose
from .capabilities import capabilities
from .crystallography.cif import format_su
from .help import HelpEntry, help_for, help_registry
from .history import RefinementTree
from .indexing import determine_extinction_symbol, index_pattern, pick_peaks
from .io.exporters import (
    ReflectionRow,
    reflection_table,
    write_qpa_table,
    write_refinement_cif,
    write_reflection_table,
)
from .io.instrument_profile import load_instrument_profile, save_instrument_profile
from .io.readers import read_pattern, read_pdcif
from .multi import MultiHistogramRefinement, refine_multi
from .optimize.cancel import CancelToken, RefinementCancelled
from .params.multi import SharingMap
from .project import Project

# ``__version__`` is the universal python spelling of "what am I running", and
# it raised AttributeError here until WP-1110 — the first thing anyone types,
# answered only by ``capabilities().package_version``, which a caller reaches
# by already knowing about ``capabilities()``.  Re-exported rather than
# recomputed: ``refine`` resolves it once from ``importlib.metadata`` at import
# and every ``Provenance``, ``TreeHeader`` and ``project.json`` is stamped from
# that same string, so a second lookup here could disagree with what a result
# says produced it.
from .refine import _VERSION as __version__
from .refine import Refinement, estimate_mu_r, refine, replay
from .report import FitReport, RegionAttribution, SuggestedAction, build_report
from .schemas import (
    AnisoU,
    Atom,
    Cell,
    Instrument,
    Parameter,
    PatternData,
    Phase,
    PreferredOrientation,
    RefinementResult,
    Structure,
)
from .schemas.history import HistoryNode, NodeAction, RefinementState
from .schemas.indexing import (
    CellCandidate,
    ExtinctionCandidate,
    ExtinctionScreen,
    IndexingResult,
    LeBailValidation,
    PeakList,
)
from .schemas.params import ParameterRow, TieSpec
from .schemas.plan import PlanSpec, StageSpec
from .schemas.project import DataRef, ProjectDoc
from .schemas.sequential import SeriesEntry, SeriesResult, Trajectory
from .schemas.suggest import CandidateGroup, ParameterCandidate, SuggestionResult
from .sequential import SequentialRefinement, refine_sequential
from .strategy.staged import (
    PLAN_INFO,
    PLAN_PRESETS,
    GuardFinding,
    PlanInfo,
    RefinementPlan,
    Stage,
)

__all__ = [
    "__version__",
    "AnisoU",
    "Atom",
    "agent",
    "CancelToken",
    "CandidateGroup",
    "Cell",
    "CellCandidate",
    "DataRef",
    "FitReport",
    "GuardFinding",
    "HelpEntry",
    "HistoryNode",
    "Instrument",
    "ExtinctionCandidate",
    "ExtinctionScreen",
    "IndexingResult",
    "MultiHistogramRefinement",
    "NodeAction",
    "PLAN_INFO",
    "PLAN_PRESETS",
    "LeBailValidation",
    "Parameter",
    "ParameterCandidate",
    "ParameterRow",
    "PatternData",
    "PeakList",
    "Phase",
    "PlanInfo",
    "PlanSpec",
    "PreferredOrientation",
    "Project",
    "ProjectDoc",
    "Refinement",
    "RefinementCancelled",
    "RefinementPlan",
    "RefinementResult",
    "RefinementState",
    "RefinementTree",
    "ReflectionRow",
    "RegionAttribution",
    "SequentialRefinement",
    "SeriesEntry",
    "SeriesResult",
    "SharingMap",
    "Stage",
    "StageSpec",
    "Structure",
    "TieSpec",
    "Trajectory",
    "SuggestedAction",
    "SuggestionResult",
    "auto_background",
    "build_report",
    "capabilities",
    "diagnose",
    "format_su",
    "help_for",
    "help_registry",
    "determine_extinction_symbol",
    "index_pattern",
    "load_instrument_profile",
    "pick_peaks",
    "read_pattern",
    "read_pdcif",
    "reflection_table",
    "refine",
    "refine_sequential",
    "refine_multi",
    "replay",
    "save_instrument_profile",
    "write_qpa_table",
    "estimate_mu_r",
    "write_reflection_table",
    "write_refinement_cif",
]
