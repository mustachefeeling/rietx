from .indexing import (
    plot_candidates,
    plot_indexing,
    plot_peak_list,
    plot_validation,
)
from .plots import plot_for_vlm, plot_pattern, plot_result, plot_trajectory

__all__ = ["LiveSession", "plot_candidates", "plot_for_vlm", "plot_indexing",
           "plot_pattern", "plot_peak_list", "plot_result", "plot_trajectory",
           "plot_validation", "render_structure", "write_html"]


def __getattr__(name: str):
    # none imports a plotting library (WP-1402, WP-1461, WP-1470); all stay
    # out of the base import, which a plot does not need
    if name == "render_structure":
        from .figure3d import render_structure

        return render_structure
    if name == "write_html":
        from .html import write_html

        return write_html
    if name == "LiveSession":
        from .live import LiveSession

        return LiveSession
    raise AttributeError(name)
