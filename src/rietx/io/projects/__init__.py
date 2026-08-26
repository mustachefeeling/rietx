"""Readers for *refinement project* files, as distinct from pattern readers.

`io.readers` answers "what did the diffractometer record"; this package answers
"what model did someone already fit to it". A solved project carries the phases,
the instrument and the converged figures of merit, which makes it the cheapest
source of a validated reference for testing.

One module per format, mirroring `io/`'s organising rule: a format's
specification citation, its parser, its refusals and its licence fence are one
fact each, and several fences in one file drift.
"""

from .fullprof import FullProfPcrError, read_fullprof_pcr
from .topas import TopasInpError, read_topas_inp

# The package exports only each format's *format-named* entry point (and its
# error) — never the module's ``to_structure``. WP-1118's scope is "read a
# refinement in, write one back", so each format's module owns the symmetric
# pair ``to_structure`` / (later) ``from_structure``; that pair is right at the
# module level but a bare ``to_structure`` re-exported here would be one
# package name for two different functions the moment a sibling reader lands
# its own (the second import silently winning). So each conversion stays
# reachable as ``rietx.io.projects.<format>.to_structure`` and nothing shadows
# across formats.
__all__ = ["read_topas_inp", "TopasInpError", "read_fullprof_pcr", "FullProfPcrError"]
