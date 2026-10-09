"""A minimal reader for the vendored COMCIFS DDLm dictionaries (WP-1319, C-a).

gemmi 0.7.5 cannot read these files: they are CIF 2.0, and gemmi rejects a
CIF 2.0 list (``_a [1 2]``), so ``cif_core.dic`` fails at its line 139.  This
module reads just enough of CIF 2.0 to answer the registry test's three
questions about a tag name — is it defined, under which ``_definition.id``,
and is this spelling deprecated — and the ``_type.purpose`` and
``_type.contents`` beside them.  It is a test helper and not a general parser:
it keeps every save frame's single items and loop columns and nothing else,
and it does not validate.

The grammar is the CIF 2.0 syntax (Bernstein et al. 2016, *J. Appl. Cryst.*
**49**, 277): ``#`` comments, ``;`` text fields at a line start, strings in
single or double quotes or in triples of either, nestable ``[ … ]`` lists and
``{ 'k':v … }`` tables, ``data_``, ``save_name``/``save_`` and ``loop_``.  The
semantics read are DDLm's (Spadaccini & Hall 2012, *J. Chem. Inf. Model.*
**52**, 1907): ``_alias.definition_id`` with ``_alias.deprecation_date`` (``.``
meaning "not deprecated"), ``_definition_replaced`` marking a whole definition
deprecated, and ``_import.get`` pulling ``_type.purpose`` and
``_type.contents`` in from the ``templ_attr.cif``/``templ_enum.cif`` frames a
definition names.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DICTIONARY_DIR = Path(__file__).parent / "data" / "cif_dictionaries"

#: The dictionaries a written tag may be defined in, in lookup order.
DICTIONARIES = ("cif_core.dic", "cif_pd.dic", "cif_mag.dic")

_DELIMITERS = "[]{}"
_NULL = {".", "?"}


# ---------------------------------------------------------------------------
# tokens
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Token:
    kind: str   # "word" (unquoted), "str" (quoted or text field), "key", or a delimiter
    text: str


def _tokens(text: str):
    """CIF 2.0 tokens.  A quoted string followed directly by ``:`` is a table key."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "#":
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif c == ";" and (i == 0 or text[i - 1] == "\n"):
            j = text.find("\n;", i)
            if j < 0:
                raise ValueError(f"unterminated text field at offset {i}")
            yield _Token("str", text[i + 1:j])
            i = j + 2
        elif c in "'\"":
            quote = c * 3 if text.startswith(c * 3, i) else c
            j = text.find(quote, i + len(quote))
            if j < 0:
                raise ValueError(f"unterminated string at offset {i}")
            value, i = text[i + len(quote):j], j + len(quote)
            if i < n and text[i] == ":":
                yield _Token("key", value)
                i += 1
            else:
                yield _Token("str", value)
        elif c in _DELIMITERS:
            yield _Token(c, c)
            i += 1
        else:
            j = i
            while j < n and text[j] not in " \t\r\n" and text[j] not in _DELIMITERS:
                j += 1
            yield _Token("word", text[i:j])
            i = j


def _reserved(token: _Token) -> bool:
    if token.kind != "word":
        return False
    low = token.text.lower()
    return low.startswith(("data_", "save_")) or low == "loop_"


def _is_tag(token: _Token) -> bool:
    return token.kind == "word" and token.text.startswith("_")


def _value(token: _Token, stream):
    """One value: a string, or a list/dict built from a ``[``/``{`` token."""
    if token.kind == "[":
        out = []
        for tok in stream:
            if tok.kind == "]":
                return out
            out.append(_value(tok, stream))
        raise ValueError("unterminated list")
    if token.kind == "{":
        out = {}
        for tok in stream:
            if tok.kind == "}":
                return out
            if tok.kind != "key":
                raise ValueError(f"a table entry needs a quoted key, got {tok.text!r}")
            out[tok.text] = _value(next(stream), stream)
        raise ValueError("unterminated table")
    if token.kind in ("word", "str"):
        return token.text
    raise ValueError(f"unexpected {token.text!r}")


# ---------------------------------------------------------------------------
# frames
# ---------------------------------------------------------------------------

def read_frames(path: Path) -> dict[str, dict[str, list]]:
    """Every save frame (and the data block's own items, under ``""``) as
    ``{lowercased tag: [values]}`` — a single item is a one-value list, a loop
    column its whole column."""
    frames: dict[str, dict[str, list]] = {"": {}}
    current = frames[""]
    stream = iter(list(_tokens(path.read_text(encoding="utf-8"))))
    pending = next(stream, None)
    while pending is not None:
        tok, pending = pending, None
        low = tok.text.lower()
        if tok.kind == "word" and low.startswith("save_"):
            name = low[len("save_"):]
            current = frames.setdefault(name, {}) if name else frames[""]
        elif tok.kind == "word" and low.startswith("data_"):
            current = frames[""]
        elif tok.kind == "word" and low == "loop_":
            names = []
            for tok in stream:
                if not _is_tag(tok):
                    pending = tok
                    break
                names.append(tok.text.lower())
            values = []
            while pending is not None and not _reserved(pending) and not _is_tag(pending):
                values.append(_value(pending, stream))
                pending = next(stream, None)
            for k, name in enumerate(names):
                current.setdefault(name, []).extend(values[k::len(names)])
        elif _is_tag(tok):
            current.setdefault(low, []).append(_value(next(stream), stream))
        else:
            raise ValueError(f"{path.name}: stray value {tok.text!r}")
        if pending is None:
            pending = next(stream, None)
    return frames


# ---------------------------------------------------------------------------
# definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Lookup:
    """What a dictionary says about one tag *spelling*."""
    definition_id: str
    purpose: str | None
    contents: str | None
    deprecated: bool
    source: str           # the dictionary file defining it


_TEMPLATES = {"cifdic_attr": "templ_attr.cif", "templ_attr": "templ_attr.cif",
              "cifdic_enum": "templ_enum.cif", "templ_enum": "templ_enum.cif"}


def _template_file(ref: str) -> str | None:
    base = ref.rsplit("/", 1)[-1].lower()
    return next((f for stem, f in _TEMPLATES.items() if base.startswith(stem)), None)


class Dictionaries:
    """The vendored core, powder and magnetic dictionaries, indexed by spelling."""

    def __init__(self, directory: Path = DICTIONARY_DIR,
                 names: tuple[str, ...] = DICTIONARIES) -> None:
        self._templates = {f: read_frames(directory / f)
                           for f in set(_TEMPLATES.values())}
        self._by_name: dict[str, Lookup] = {}
        for name in names:
            frames = read_frames(directory / name)
            replaced = {self._one(f, "_definition.id").lower()
                        for f in frames.values()
                        if self._replaced(f) and self._one(f, "_definition.id")}
            for frame in frames.values():
                did = self._one(frame, "_definition.id")
                if not did or not did.startswith("_"):
                    continue          # a head or category frame, not an item
                category = (self._one(frame, "_name.category_id") or "").lower()
                gone = self._replaced(frame) or category in replaced
                purpose = self._attribute(frame, "_type.purpose")
                contents = self._attribute(frame, "_type.contents")
                spellings = [(did, gone)]
                dates = frame.get("_alias.deprecation_date", [])
                for k, alias in enumerate(frame.get("_alias.definition_id", [])):
                    dated = k < len(dates) and dates[k] not in _NULL
                    spellings.append((alias, gone or dated))
                for spelling, deprecated in spellings:
                    self._by_name.setdefault(
                        spelling.lower(), Lookup(did, purpose, contents, deprecated, name))

    @staticmethod
    def _one(frame: dict[str, list], tag: str) -> str | None:
        values = frame.get(tag)
        return values[0] if values else None

    @staticmethod
    def _replaced(frame: dict[str, list]) -> bool:
        return any(t.startswith("_definition_replaced.") for t in frame)

    def _attribute(self, frame: dict[str, list], tag: str, depth: int = 0):
        """``tag`` as the frame sets it, else as its first ``Contents`` import does."""
        own = self._one(frame, tag)
        if own is not None or depth > 4:
            return own
        for spec in (x for imports in frame.get("_import.get", []) for x in imports):
            if str(spec.get("mode", "Contents")).lower() != "contents":
                continue
            file = _template_file(str(spec.get("file", "")))
            target = self._templates.get(file, {}).get(str(spec.get("save", "")).lower())
            if target is not None:
                found = self._attribute(target, tag, depth + 1)
                if found is not None:
                    return found
        return None

    def lookup(self, tag: str) -> Lookup | None:
        """The definition ``tag`` spells, or ``None`` if no dictionary defines it."""
        return self._by_name.get(tag.lower())

    def __len__(self) -> int:
        return len(self._by_name)
