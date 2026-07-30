"""Unit-cell determination from a powder pattern, and the peak picking it needs.

WP-1018 lands the first half: :func:`pick_peaks` turns a pattern into a
:class:`pxrdref.schemas.indexing.PeakList` whose every line carries a *fitted*
position with an esd, so the engines that follow weight each line by what it
actually determines instead of sharing one global tolerance knob.
"""

from .peakfit import fit_group
from .peaks import Detection, PeakGroup, detect_peaks
from .pick import pick_peaks

__all__ = [
    "Detection",
    "PeakGroup",
    "detect_peaks",
    "fit_group",
    "pick_peaks",
]
