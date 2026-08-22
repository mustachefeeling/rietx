# Constraints and restraints

A **constraint** removes a parameter: the tied one is no longer free, and its
value follows its sources exactly. {ref}`constraining-parameters` is the
reference for the three verbs (`Refinement.tie`, `Refinement.tie_equal` and
`Refinement.untie`), the affine form they share, the fnmatch globs they take,
the four refusals each can raise, and how a tied row reads in the parameter
listing.

A **restraint** keeps a parameter: it adds a row to the residual pulling a bond
length or an angle towards a target, and the fit is free to disagree with it at
a cost. {ref}`restraining-a-distance` is that reference. Use a constraint for a
relation you are sure of and a restraint for one you are only mostly sure of.

The parameter *paths* both take, and the one grammatical trap in them, are in
[](model.md). The symmetry constraints you never declare (a cell edge following
another, a coordinate confined to its site-symmetry direction) are created for
you and read the same way, with `TieSpec.user` false.
