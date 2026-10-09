"""One rule for every value a CIF written by this build carries (WP-1319 C-b).

**Numbers.**  A value with a standard uncertainty is written by
:func:`~rietx.crystallography.cif.format_su`, two significant figures of su
in ``value(su)`` notation, unchanged (``SU_REFERENCE`` in
``tests/test_exporters.py`` pins it).  A value without one is written as the
shortest ``repr`` that reads back as the same double.  A fixed number of
decimals was the rule before, and it lost what it did not print: a free
monoclinic β of 90.00004 went out as ``90.0000``, an occupancy of 0.33333 as
``0.3333``, and both came back different (issue #756, four of 1121 MAGNDATA
round trips).  A value with no su states no precision, so the writer has no
business choosing one.

**Moments** keep ``repr`` for the value with the su in its own ``_su`` item
(:func:`~rietx.crystallography.magcif._moment_number` has the measured
reason), so a moment's value goes through :func:`number` with no su and its
uncertainty through :func:`su_or_dot`.

**Refusals, by tag.**  A non-finite value is refused, because ``repr`` spells
it ``nan`` or ``inf`` and no CIF reader parses that.  A text value is quoted
where it needs to be, except in a tag the dictionary types as a single token
(``_type.contents`` ``Word``, ``Code`` or ``Symop``), where whitespace is
refused: quoting would make the file parse and leave a label no other item can
reference.  Both are ``ValueError`` raised while the value is in hand and
before a file is opened, naming the tag and the value (``io/CLAUDE.md``
§ Project writers).

References
----------
- Hall, Allen & Brown (1991), *Acta Cryst.* **A47**, 655: the CIF format, its
  numeric grammar (an exponent is legal, ``1e-05``) and its quoting rules.
- COMCIFS ``cif_core.dic`` 3.3.0, doi:10.1107/cifdic_core_3.3.0: the
  ``_type.contents`` of each tag, carried in
  :data:`~rietx.io.cif.registry.TAGS`.
- Schwarzenbach et al. (1989), *Acta Cryst.* **A45**, 63: the su convention
  :func:`~rietx.crystallography.cif.format_su` writes.
"""

from __future__ import annotations

import math

import gemmi

#: The ``_type.contents`` whose values are one token: whitespace is refused.
SINGLE_TOKEN_CONTENTS: frozenset[str] = frozenset({"Word", "Code", "Symop"})


def _named(tag: str, where: str | None) -> str:
    return tag if where is None else f"{tag} of {where!r}"


def number(tag: str, value: float, su: float | None = None, *,
           where: str | None = None) -> str:
    """``value`` as ``tag`` carries it: ``value(su)`` with an su, else ``repr``.

    An su counts when it is positive and finite, the test
    :func:`~rietx.crystallography.cif.format_su` applies.  ``where`` names the
    row (a site label) in a refusal.  Formats per Hall, Allen & Brown (1991)
    and Schwarzenbach et al. (1989); see the module docstring.
    """
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(
            f"{_named(tag, where)} is {value!r}, and a CIF states numbers a "
            f"reader can parse: no CIF reader parses {value!r}, so the file "
            f"is not written")
    if su is not None and math.isfinite(su) and su > 0.0:
        from ...crystallography.cif import format_su

        return format_su(value, su)
    # np.float64's repr is 'np.float64(…)', hence the float() above
    return repr(value)


def su_or_dot(su: float | None) -> str:
    """An su written in its own ``_su`` item, or CIF's ``.`` where there is none.

    ``.`` is *inapplicable*: a moment component written back from a modulus
    DOF has no esd of its own (WP-1327), and ``0`` there would state a moment
    known exactly.  A finite su is ``repr``, as its value is.  Hall, Allen &
    Brown (1991) for the null values.
    """
    if su is None or not math.isfinite(su):
        return "."
    return repr(float(su))


def text(tag: str, value: str, *, where: str | None = None) -> str:
    """``value`` as ``tag`` carries it, quoted where CIF needs it.

    A tag whose dictionary ``_type.contents`` is a single token
    (:data:`SINGLE_TOKEN_CONTENTS`) refuses whitespace and the empty string.
    Every other text is quoted by ``gemmi.cif.quote``, which leaves a value
    that needs no quotes as it stands.  Quoting per Hall, Allen & Brown (1991);
    contents per ``cif_core.dic`` 3.3.0.
    """
    from .registry import TAGS

    if TAGS[tag].contents in SINGLE_TOKEN_CONTENTS and (
            not value or any(ch.isspace() for ch in value)):
        raise ValueError(
            f"{_named(tag, where)} is {value!r}, and the dictionary types "
            f"{tag} as a single word: whitespace would split the row in two, "
            f"or, quoted, leave a value nothing else can reference. Respell it "
            f"without whitespace")
    return gemmi.cif.quote(value)
