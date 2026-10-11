"""Representation analysis of a space group: small irreps and symmetry-adapted modes.

``irreps`` builds the small irreps of the little group of a propagation vector
k; ``modes`` decomposes a site orbit's polar (displacement) or axial (moment)
representation into them and projects out the basis vectors.  Nothing here is
magnetic: magnetism is one consumer, through ``kind="axial"``, and displacive
distortion modes are the other (#418, WP-1419).
"""
