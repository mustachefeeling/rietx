"""Readers for *refinement project* files, as distinct from pattern readers.

`io.readers` answers "what did the diffractometer record"; this package answers
"what model did someone already fit to it". A solved project carries the phases,
the instrument and the converged figures of merit, which makes it the cheapest
source of a validated reference for testing.

One module per format, mirroring `io/`'s organising rule.
"""

from .topas import TopasInpError, read_topas_inp

# Only the format-named entry points are exported (WP-1118). `to_structure` is a
# *module-level* name reached as `projects.topas.to_structure`: exporting it here
# would collide with #111's FullProf `to_structure` and the collision resolves by
# silently rebinding one over the other. The reader and its error are the seam
# the package promises; the model→`Structure` conversion (and its future
# `from_structure` inverse and `write_topas_inp` writer) live on the module.
__all__ = ["read_topas_inp", "TopasInpError"]
