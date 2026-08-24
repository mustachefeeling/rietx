from .auto import auto_background
from .diagnostics import (
    ContaminationFlag,
    CoverageRegion,
    PatternDiagnostics,
    background_envelope,
    contamination_flags_from_peaks,
    counting_coverage,
    diagnose,
    identify_anode,
)
from .estimators import arpls, auto_lambda, snip, whittaker_solve
from .models import (
    bspline_design_matrix,
    chebyshev_background,
    chebyshev_design_matrix,
    interpolate_fixed,
    second_difference_matrix,
)
from .select import (
    BackgroundSelection,
    peak_mask,
    select_arpls_lambda,
    select_chebyshev_order,
)

__all__ = [
    "BackgroundSelection",
    "ContaminationFlag",
    "CoverageRegion",
    "PatternDiagnostics",
    "arpls",
    "auto_background",
    "auto_lambda",
    "background_envelope",
    "bspline_design_matrix",
    "chebyshev_background",
    "chebyshev_design_matrix",
    "contamination_flags_from_peaks",
    "counting_coverage",
    "diagnose",
    "identify_anode",
    "interpolate_fixed",
    "peak_mask",
    "second_difference_matrix",
    "select_arpls_lambda",
    "select_chebyshev_order",
    "snip",
    "whittaker_solve",
]
