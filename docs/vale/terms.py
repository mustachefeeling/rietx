# The accept side of the term list, written for Vale (WP-1982).
#
# Two sources, and the accept list is their union.  `rietx.help` is the
# authority for what each name is called, so every word of its titles and chip
# labels that the en_GB dictionary lacks is accepted: a parameter named after
# a person reaches the list when it reaches the package.  `terms.txt` beside
# this file adds the crystallographer's words no entry names.
#
#   .venv/bin/python docs/vale/terms.py      # rewrite the accept list
#
# `tests/test_vale.py` holds the committed list equal to `accept_lines()`, so
# a new help entry fails that test until the list is rewritten.

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HAND_KEPT = HERE / "terms.txt"
DICTIONARY = HERE / "config" / "dictionaries" / "en_GB"
ACCEPT = HERE / "config" / "vocabularies" / "rietx" / "accept.txt"

#: A word as `rietx.help` spells one: Latin letters, an apostrophe or digits
#: inside.  Greek letters and subscripts are notation, which Vale does not
#: spell-check.
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9']*")


def dictionary_forms() -> set[str]:
    """Every form the en_GB Hunspell dictionary accepts, affixes expanded.

    A suffix flag applies where its condition matches the stem's end and a
    prefix flag where its condition matches the start; a prefix marked as
    cross-product also applies to each suffixed form (Hunspell's `man 5
    hunspell`, "Affix file general options").  Compounding is left out: it
    governs ordinals here, and a title carries none.
    """
    rules: dict[str, tuple[str, bool, list]] = {}
    for line in DICTIONARY.with_suffix(".aff").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0] not in ("PFX", "SFX"):
            continue
        kind, flag = parts[0], parts[1]
        if flag not in rules:
            rules[flag] = (kind, parts[2] == "Y", [])
            continue
        strip = "" if parts[2] == "0" else parts[2]
        add = "" if parts[3] == "0" else parts[3].split("/")[0]
        condition = parts[4] if len(parts) > 4 else "."
        anchored = condition + "$" if kind == "SFX" else "^" + condition
        rules[flag][2].append((strip, add, re.compile(anchored)))

    forms: set[str] = set()
    for line in DICTIONARY.with_suffix(".dic").read_text(encoding="utf-8").splitlines()[1:]:
        stem, _, flags = line.strip().partition("/")
        forms.add(stem)
        suffixed = [stem]
        prefixes = []
        for flag in flags:
            kind, cross, entries = rules.get(flag, ("", False, []))
            if kind == "PFX":
                prefixes.append((cross, entries))
                continue
            for strip, add, condition in entries:
                if condition.search(stem) and stem.endswith(strip):
                    form = stem[:len(stem) - len(strip)] + add
                    forms.add(form)
                    if cross:
                        suffixed.append(form)
        for cross, entries in prefixes:
            for base in suffixed if cross else [stem]:
                for strip, add, condition in entries:
                    if condition.search(base) and base.startswith(strip):
                        forms.add(add + base[len(strip):])
    return forms


def help_words(forms: set[str]) -> dict[str, bool]:
    """Each word of a help title or label that the dictionary lacks.

    The value says whether the word was ever seen anywhere but first in its
    title, which is the only place its capital could be a sentence's rather
    than a name's.  An American spelling whose British form the dictionary
    knows is left out: the package's text is WP-1985's to rewrite, and the
    term list must not accept "polarization" because a title spells it so.
    """
    from rietx.help import help_registry

    texts = []
    for arm in help_registry().values():
        for entry in arm if isinstance(arm, list) else arm.values():
            texts += [entry[field] for field in ("title", "label") if entry.get(field)]
    words: dict[str, bool] = {}
    for text in texts:
        for position, match in enumerate(_WORD.finditer(text)):
            word = match.group(0).removesuffix("'s")
            if word in forms or word.lower() in forms:
                continue
            if "iz" in word.lower() and word.lower().replace("iz", "is") in forms:
                continue
            words[word] = words.get(word, False) or position > 0
    return words


def hand_kept() -> list[str]:
    lines = HAND_KEPT.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def _entry(word: str) -> str:
    """Vale's form of one term: a lower-case word may also open a sentence.

    Vale.Terms holds each accepted word to the case it is listed in, so
    "anisotropic" alone flags the sentence "Anisotropic strain is…".
    """
    if word[0].islower():
        return f"[{word[0]}{word[0].upper()}]{word[1:]}"
    return word


def accept_lines() -> list[str]:
    """The accept list: the hand-kept terms, then every help word they miss."""
    hand = hand_kept()
    known = {word.lower() for word in hand}
    words = list(hand)
    for word, named in help_words(dictionary_forms()).items():
        if word.lower() in known:
            continue
        known.add(word.lower())
        # A capital seen only at a title's start is the title's, not a name's.
        words.append(word if named or not word[1:].islower() else word.lower())
    return [_entry(word) for word in sorted(words, key=str.lower)]


if __name__ == "__main__":
    ACCEPT.write_text("\n".join(accept_lines()) + "\n", encoding="utf-8")
    sys.stdout.write(f"wrote {ACCEPT.relative_to(HERE.parent.parent)}\n")
