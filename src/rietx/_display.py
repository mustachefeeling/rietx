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


# ---------------------------------------------------------------------------
# The text tree every schema prints as (``Base.__str__``)
# ---------------------------------------------------------------------------

#: A model that fits on one line within this many characters prints that way.
ONE_LINE_WIDTH = 100

#: A list of models longer than this shows its first rows and a count: a
#: structure's 19 atoms stay whole, a reflection list's 2000 do not.
TREE_ROWS = 32


def _number(value: float, esd: float | None = None) -> str:
    from .crystallography.cif import format_su
    if esd is not None and esd > 0 and np.isfinite(esd) and np.isfinite(value):
        return format_su(value, esd)
    return f"{value:.8g}"


def parameter_text(p) -> str:
    """One ``Parameter`` on one line: ``value(esd) unit``, and ``(vary)`` when
    it is free.  Bounds stay in ``Refinement.parameters()``, where every row
    carries them."""
    from .help import UNIT_DISPLAY
    text = _number(p.value, p.stderr)
    if p.unit:
        text += " " + UNIT_DISPLAY.get(p.unit, p.unit)
    if p.vary:
        text += " (vary)"
    return text


def _is_model(value) -> bool:
    from .schemas.common import Base
    return isinstance(value, Base)


def _is_parameter(value) -> bool:
    from .schemas.common import Parameter
    return isinstance(value, Parameter)


def _shown(value) -> bool:
    """A field the tree prints: ``None`` and empty containers say nothing."""
    if value is None:
        return False
    if isinstance(value, (list, tuple, dict)) and not value:
        return False
    return True


def _leaf(value) -> str | None:
    """A value's one-line text, or ``None`` when it needs lines of its own."""
    if _is_parameter(value):
        return parameter_text(value)
    if _is_model(value):
        return None
    if isinstance(value, float):
        return _number(value)
    if isinstance(value, (list, tuple, dict)):
        items = value.values() if isinstance(value, dict) else value
        if any(_is_model(v) and not _is_parameter(v) for v in items):
            return None     # rows of models: `_container_lines` lists them
    if isinstance(value, (list, tuple, dict, np.ndarray)):
        value = summarise(value)
        if isinstance(value, _Elided):
            return value.text
        if isinstance(value, dict):
            parts = [f"{k}: {_leaf(v)}" for k, v in value.items()]
        else:
            parts = [_leaf(v) for v in value]
        if any(p is None for p in parts):
            return None
        bra, ket = ("{", "}") if isinstance(value, dict) else ("[", "]")
        return bra + ", ".join(parts) + ket
    return repr(value) if isinstance(value, str) else str(value)


def _fields(model, order=None, show_empty=False):
    names = list(order) if order is not None else list(type(model).model_fields)
    return [(name, getattr(model, name)) for name in names
            if show_empty or _shown(getattr(model, name))]


def _one_line(model) -> str | None:
    parts = []
    for name, value in _fields(model):
        leaf = _leaf(value)
        if leaf is None:
            return None
        parts.append(f"{name}={leaf}")
    line = f"{type(model).__name__}({', '.join(parts)})"
    return line if len(line) <= ONE_LINE_WIDTH else None


def _tree_lines(model, indent: str, order=None, show_empty=False) -> list[str]:
    lines = []
    for name, value in _fields(model, order, show_empty):
        if show_empty and not _shown(value):
            lines.append(f"{indent}{name}: {'None' if value is None else 'none'}")
            continue
        leaf = _leaf(value)
        long_container = (leaf is not None and len(indent) + len(name) + len(leaf) > ONE_LINE_WIDTH
                          and isinstance(value, (list, tuple, dict))
                          and not isinstance(summarise(value), _Elided))
        if leaf is not None and not long_container:
            lines.append(f"{indent}{name}: {leaf}")
        elif _is_model(value):
            one = _one_line(value)
            if one is not None:
                lines.append(f"{indent}{name}: {one}")
            else:
                lines.append(f"{indent}{name}: {type(value).__name__}")
                lines += _tree_lines(value, indent + "  ")
        else:
            lines += _container_lines(name, value, indent)
    return lines


def _container_lines(name, value, indent: str) -> list[str]:
    items = list(value.items()) if isinstance(value, dict) else list(enumerate(value))
    lines = [f"{indent}{name}: {len(items)} {_kind([v for _, v in items])}"]
    for key, item in items[:TREE_ROWS]:
        label = f"[{key}]" if isinstance(value, (list, tuple)) else f"{key}:"
        leaf = _leaf(item)
        if leaf is not None:
            lines.append(f"{indent}  {label} {leaf}")
            continue
        one = _one_line(item) if _is_model(item) else None
        if one is not None:
            lines.append(f"{indent}  {label} {one}")
        elif _is_model(item):
            lines.append(f"{indent}  {label} {type(item).__name__}")
            lines += _tree_lines(item, indent + "    ")
        else:
            lines += _container_lines(label, item, indent + "  ")
    if len(items) > TREE_ROWS:
        lines.append(f"{indent}  … {len(items) - TREE_ROWS} more")
    return lines


def tree(model, *, order=None, show_empty: bool = False, head: str | None = None) -> str:
    """A schema as an indented field tree: one line per ``Parameter``, a model
    that fits on one line kept on one, ``None`` and empty fields left out.

    A designed view passes ``order`` (the fields to print, in reading order)
    and ``show_empty`` where an empty list is itself a finding ("checked, and
    nothing"), and ``head`` for a first line that says what the object is of.
    """
    if _is_parameter(model):
        return parameter_text(model)
    if order is None and not show_empty and head is None:
        one = _one_line(model)
        if one is not None:
            return one
    first = head or type(model).__name__
    return "\n".join([first] + _tree_lines(model, "  ", order, show_empty))


# ---------------------------------------------------------------------------
# The parameter table: one row builder, a text and an HTML renderer
# ---------------------------------------------------------------------------

def row_state(row) -> str:
    """What a ``ParameterRow`` is doing, in the field's own words: ``vary``,
    ``fixed``, or the first of ``locked``, ``tied = …``, ``mode_fixed``,
    ``held``, ``needs_held_cell`` that holds it (``held_because``'s order)."""
    if row.locked:
        return "locked"
    if row.tie is not None:
        return f"tied = {row.tie.describe()}"
    if row.mode_fixed:
        return "mode_fixed"
    if row.held:
        return "held"
    if row.needs_held_cell:
        return "needs_held_cell"
    return "vary" if row.vary else "fixed"


def parameter_cells(row) -> tuple[str, str, str]:
    """``(path, value(esd), state)``: the one row both renderers draw."""
    return row.path, _number(row.value, row.esd), row_state(row)


def table_text(header: tuple[str, ...], rows: list[tuple[str, ...]], indent: str = "") -> list[str]:
    """Left-aligned columns, two spaces apart, header first."""
    widths = [max(len(c) for c in col) for col in zip(header, *rows)]
    out = []
    for cells in (header, *rows):
        line = "  ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip()
        out.append(indent + line)
    return out


def table_html(header: tuple[str, ...], rows: list[tuple[str, ...]], caption: str | None = None) -> str:
    """The same rows as a bare ``<table>``: no style, so the notebook's own
    theme draws it and a sanitiser has nothing to strip."""
    from html import escape
    parts = ["<table>"]
    if caption:
        parts.append(f"<caption>{escape(caption)}</caption>")
    parts.append("<thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in header)
                 + "</tr></thead><tbody>")
    for cells in rows:
        parts.append("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in cells) + "</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


PARAMETER_HEADER = ("path", "value", "state")


def pre_html(text: str) -> str:
    """Text in a ``<pre>``, escaped: the HTML form of a view with no table."""
    from html import escape
    return f"<pre>{escape(text)}</pre>"


# ---------------------------------------------------------------------------
# Refinement (not a schema, so it has no tree)
# ---------------------------------------------------------------------------

def refinement_parts(ref) -> tuple[list[str], list, int]:
    """The head lines, the free rows and the row count for a ``Refinement``.

    Reads the object's own fields and builds its parameter table, which is a
    pure function of them (milliseconds, no fit, no file written).
    """
    phases = ", ".join(f"{p.name} ({p.space_group})" for p in ref.structure.phases)
    n = len(ref.structure.phases)
    head = [f"Refinement of {n} phase{'s' if n != 1 else ''}: {phases}",
            f"  mode: {ref._mode}   backend: {ref._backend}   solver: {ref._solver}"]
    result = ref.result_
    if result is None:
        head.append("  last fit: none")
    else:
        st = result.statistics
        head.append(f"  last fit: {result.status}   Rwp {st.rwp:.4f}   GoF {st.gof:.2f}"
                    f"   {len(result.diagnostics)} diagnostics")
    tree = ref.history
    if tree is not None and len(tree):
        head.append(f"  history: {len(tree)} nodes, head {tree.head}")
    try:
        rows = ref.parameters()
    except Exception as exc:   # a display never raises over a model it is showing
        head.append(f"  parameters: not available ({type(exc).__name__}: {exc})")
        return head, [], 0
    free = [r for r in rows if r.vary]
    head.append(f"  parameters: {len(free)} of {len(rows)} vary; "
                "ref.parameters() lists every row")
    return head, free, len(rows)


def refinement_text(ref) -> str:
    head, free, _ = refinement_parts(ref)
    if free:
        head += table_text(PARAMETER_HEADER, [parameter_cells(r) for r in free], "    ")
    return "\n".join(head)


def refinement_html(ref) -> str:
    head, free, _ = refinement_parts(ref)
    html = pre_html("\n".join(head))
    if free:
        html += table_html(PARAMETER_HEADER, [parameter_cells(r) for r in free])
    return html
