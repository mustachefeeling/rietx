from .indexing import (
    plot_candidates,
    plot_indexing,
    plot_peak_list,
    plot_validation,
)
from .plots import plot_for_vlm, plot_result, plot_trajectory

__all__ = ["LiveSession", "plot_candidates", "plot_for_vlm", "plot_indexing",
           "plot_peak_list", "plot_result", "plot_trajectory",
           "plot_validation", "write_html"]


def __getattr__(name: str):
    # write_html imports plotly lazily and LiveSession imports none at all
    # (WP-1402) — keep the base import light either way
    if name == "write_html":
        from .html import write_html

        return write_html
    if name == "LiveSession":
        from .live import LiveSession

        return LiveSession
    raise AttributeError(name)
