"""A sample of the 230 space groups, chosen by trap, for the sweeps' fast tier.

A sweep over every group runs in the nightly, marked ``slow``.  The fast tier
runs the same sweep over this sample (WP-1547).  A break in an unsampled group
therefore shows the next morning rather than on its pull request.  That is the
trade.

The sample is chosen by trap and never at random.  79 of gemmi's 564 settings
were once served wrong under a correct count (root CLAUDE.md, cell ties).  So
each member names what it covers.  Together they hold every pair of crystal
system and lattice centring that the 230 groups hold, sixteen in all
(``test_symmetry_orbits.py`` asserts it).  They hold five of the fifteen groups
with a pseudoreal irrep at the zone boundary, and both (group, k) pairs that
spgrep 0.7.0 declines.  A sweep over settings takes every gemmi setting of a
sampled group, which brings in the monoclinic unique axes, the origin choices
and both axes of the R lattice.
"""

from __future__ import annotations

#: Space-group number → the trap that member covers.
TRAP_SAMPLE: dict[int, str] = {
    1: "P 1: the trivial group, where every count is one",
    14: "P 21/c: a screw and a glide, in nine settings over three unique axes",
    15: "C 2/c: a centred monoclinic lattice, in eighteen settings",
    19: "P 21 21 21: three screws and no inversion; pseudoreal at the zone boundary",
    24: "I 21 21 21: a bcc P point spgrep 0.7.0 declines",
    39: "A b m 2: an A-centred cell",
    62: "P n m a: the worked case, Bertaut's 4b and the 4c control",
    63: "C m c m: C centring with a glide",
    70: "F d d d: the orthorhombic F lattice with d glides, two origin choices",
    73: "I b c a: the other bcc P point spgrep 0.7.0 declines",
    104: "P 4 n c: tetragonal P; pseudoreal at the zone boundary",
    136: "P 42/m n m: a 42 screw on the P lattice",
    141: "I 41/a m d: a 41 screw on the I lattice, two origin choices",
    158: "P 3 c 1: trigonal P; pseudoreal at the zone boundary",
    167: "R -3 c: the R lattice, on hexagonal and on rhombohedral axes",
    191: "P 6/m m m: the symmorphic hexagonal control",
    194: "P 63/m m c: a 63 screw on the hexagonal lattice",
    205: "P a -3: cubic P; pseudoreal at the zone boundary",
    219: "F -4 3 c: cubic F; pseudoreal at the zone boundary",
    221: "P m -3 m: the symmorphic cubic control",
    222: "P n -3 n: cubic P with n glides, two origin choices",
    227: "F d -3 m: diamond, its 1/8 1/8 1/8 site and two origin choices",
    230: "I a -3 d: cubic I with d glides",
}
