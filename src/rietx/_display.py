"""How a rietx object reads when printed, shown in a notebook, or logged (WP-1544).

Text is the authority and HTML a projection of the same rows, because an agent
reads stdout and a person reads a notebook cell, and the two must not disagree.

Three rules hold for everything here:

- **A display reads fields; it never computes.** IPython builds text/plain *and*
  text/html for every displayed value, so a renderer calling ``report()`` or
  ``summary()`` would run a report's rival fits twice per cell.
- **No glosses.** A renderer prints a field's name, or the label ``help.py``
  carries for it.  What a name *is* is written there and nowhere else (WP-1202).
- **No colour of its own.** HTML is semantic tags only: JupyterLab's and
  GitHub's sanitisers strip styles, and a colour here would be a fourth surface
  beside ``viz/theme.py``'s three.

Private: nothing here is API.  The hooks that call it (``__repr_args__``,
``__str__``, ``_repr_pretty_``, ``_repr_html_``) are the surface.
"""

from __future__ import annotations

import numbers

import numpy as np

#: A sequence longer than this prints as a count and a range, never its items.
#: Eight keeps a cell's six lattice numbers and a short line list whole while a
#: pattern's thousands of channels collapse to one line.
ELIDE_ABOVE = 8


class _Elided:
    """A stand-in whose ``repr`` is a summary of the sequence it replaced."""

    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = text

    def __repr__(self) -> str:
        return self.text


def _kind(items) -> str:
    """A plural noun for what the sequence holds, read off its items."""
    types = {type(x) for x in items}
    if len(types) == 1:
        (t,) = types
        if issubclass(t, bool):
            return "bools"
        if issubclass(t, numbers.Integral):
            return "ints"
        if issubclass(t, numbers.Real):
            return "floats"
        if issubclass(t, str):
            return "strings"
        if t in (list, tuple, dict):
            return t.__name__ + "s"
        return t.__name__
    return "items"


def summarise(value, *, above: int = ELIDE_ABOVE):
    """``value`` itself, or an :class:`_Elided` summary when it is a long sequence.

    A numeric sequence keeps its range (``<5753 floats 15…130.04>``), since
    that is what a reader checks first; a sequence of anything else keeps its
    element type (``<212 Reflection>``).  A dict, or a sequence short enough to
    keep, is walked one level at a time, because a result's ticks are a dict
    of thousand-long lists.
    """
    if isinstance(value, dict):
        return {k: summarise(v, above=above) for k, v in value.items()}
    if isinstance(value, np.ndarray):
        if value.size <= above:
            return value
        shape = "×".join(str(n) for n in value.shape)
        if np.issubdtype(value.dtype, np.number) and np.isfinite(value).any():
            finite = value[np.isfinite(value)]
            return _Elided(f"<{shape} {value.dtype} {finite.min():g}…{finite.max():g}>")
        return _Elided(f"<{shape} {value.dtype}>")
    if not isinstance(value, (list, tuple)):
        return value
    if len(value) <= above:
        kept = [summarise(v, above=above) for v in value]
        return type(value)(kept) if isinstance(value, list) else tuple(kept)
    kind = _kind(value)
    if kind in ("floats", "ints"):
        arr = np.asarray(value, dtype=float)
        finite = arr[np.isfinite(arr)]
        if finite.size:
            return _Elided(f"<{len(value)} {kind} {finite.min():g}…{finite.max():g}>")
    return _Elided(f"<{len(value)} {kind}>")
