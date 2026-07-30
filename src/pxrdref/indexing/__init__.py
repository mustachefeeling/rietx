"""Unit-cell determination from a powder pattern, and the peak picking it needs.

WP-1018 landed the first half: :func:`pick_peaks` turns a pattern into a
:class:`pxrdref.schemas.indexing.PeakList` whose every line carries a *fitted*
position with an esd, so the engines that follow weight each line by what it
actually determines instead of sharing one global tolerance knob.

WP-1019 adds the gate in front of the engines: :func:`assess_peak_list` judges a
list fit to index or **abstains** with a reason, and :func:`fit_shift_model`
attributes a systematic 2θ shift to one of three physical causes — or reports
that the causes are not separable over the range measured, which is the same
refusal-to-guess the FitReport makes one rank down.
"""

from .peakfit import fit_group
from .peaks import Detection, PeakGroup, detect_peaks
from .pick import pick_peaks
from .quality import (
    assess_peak_list,
    fit_shift_model,
    template_collinearity,
    volume_envelope,
)

__all__ = [
    "Detection",
    "PeakGroup",
    "assess_peak_list",
    "detect_peaks",
    "fit_group",
    "fit_shift_model",
    "pick_peaks",
    "template_collinearity",
    "volume_envelope",
]
