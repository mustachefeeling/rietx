"""pxrd-refine: API-first Rietveld refinement of powder X-ray diffraction data."""

from . import agent
from .crystallography.cif import format_su
from .history import RefinementTree
from .indexing import pick_peaks
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
    RefinementResult,
    Structure,
)
from .schemas.history import HistoryNode, NodeAction, RefinementState
from .schemas.params import ParameterRow, TieSpec
from .schemas.plan import PlanSpec, StageSpec
from .schemas.project import DataRef, ProjectDoc
from .schemas.sequential import SeriesEntry, SeriesResult, Trajectory
from .sequential import SequentialRefinement, refine_sequential
from .strategy.staged import (
    PLAN_INFO,
    PLAN_PRESETS,
    PlanInfo,
    RefinementPlan,
    Stage,
)

__all__ = [
    "AnisoU",
    "Atom",
    "agent",
    "CancelToken",
    "Cell",
    "DataRef",
    "FitReport",
    "HistoryNode",
    "Instrument",
    "MultiHistogramRefinement",
    "NodeAction",
    "PLAN_INFO",
    "PLAN_PRESETS",
    "Parameter",
    "ParameterRow",
    "PatternData",
    "Phase",
    "PlanInfo",
    "PlanSpec",
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
    "build_report",
    "format_su",
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
