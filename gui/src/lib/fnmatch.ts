/** Python's `fnmatch.fnmatchcase`, ported — for *previewing* a glob, never for
 * deciding one.
 *
 * Every glob in this package is matched by `fnmatch.fnmatchcase` on a dot path
 * (`params/vector.py`, `sequential.py`, `report/layer2.py`), and a stage plan's
 * `turn_on` is the same vocabulary.  So the table's filter box has to agree with
 * Python about what `phases.*.cell.*` selects, or the count beside the "free
 * these" button is a different number from the one the server will act on.
 *
 * **The server stays authoritative.**  `PATCH /api/params` sends the *glob*, not
 * the matched paths, and answers with the paths `Refinement.set_vary` actually
 * changed — so a divergence here shows up as a preview that was wrong, never as
 * the wrong parameters being freed.  That is the whole reason the bulk op sends a
 * glob: one round trip, one history node, and one matcher deciding.
 *
 * Parity is pinned rather than asserted: `tests/test_gui_fnmatch.py` writes
 * `tests/data/gui/fnmatch_cases.json` from Python's own `fnmatchcase` over the
 * live parameter vocabulary, and `fnmatch.test.ts` replays every case through
 * this module.  The corpus documents its own coverage — notably that Python
 * *repairs* an inverted range (`[z-a]`) and this port does not, because no path
 * in this package contains a bracket at all (CLAUDE.md, Conventions).
 */

const CACHE = new Map<string, RegExp>();

/** `fnmatch.fnmatchcase(name, pattern)` — case-sensitive, `*` crosses dots. */
export function fnmatch(name: string, pattern: string): boolean {
  let regex = CACHE.get(pattern);
  if (regex === undefined) {
    regex = new RegExp(translate(pattern), "s");
    CACHE.set(pattern, regex);
  }
  return regex.test(name);
}

/** True when any of `patterns` matches — the `set_vary(globs)` disjunction. */
export function fnmatchAny(name: string, patterns: readonly string[]): boolean {
  return patterns.some((pattern) => fnmatch(name, pattern));
}

/**
 * The regex source `fnmatch.translate` would produce, in JavaScript's dialect.
 *
 * `*` is `.*` under the `s` flag, so it crosses a `.` separator exactly as
 * Python's does — `phases.*` matching `phases.0.cell.a` is a fact about the
 * package's globs, not a bug in this port.
 */
export function translate(pattern: string): string {
  let out = "^";
  let i = 0;
  while (i < pattern.length) {
    const c = pattern[i++];
    if (c === "*") {
      // collapse a run of stars, as translate() does, so `**` is not `.*.*`
      while (pattern[i] === "*") i++;
      out += ".*";
    } else if (c === "?") {
      out += ".";
    } else if (c === "[") {
      const close = closingBracket(pattern, i);
      if (close < 0) {
        out += "\\[";           // an unclosed `[` is a literal, per Python
      } else {
        out += characterClass(pattern.slice(i, close));
        i = close + 1;
      }
    } else {
      out += escapeLiteral(c);
    }
  }
  return out + "$";
}

/** Index of the `]` closing a class opened at `start`, or -1.
 *
 * Python's scan: a leading `!` and then a leading `]` are both taken as class
 * *content*, so `[]]` is "a literal ]" and `[!]]` is "anything but ]". */
function closingBracket(pattern: string, start: number): number {
  let j = start;
  if (pattern[j] === "!") j++;
  if (pattern[j] === "]") j++;
  while (j < pattern.length && pattern[j] !== "]") j++;
  return j >= pattern.length ? -1 : j;
}

/** Re-emit a class body for JS, keeping ranges and neutralising everything else. */
function characterClass(body: string): string {
  if (body === "") return "(?!)";          // `[]` — matches nothing
  if (body === "!") return ".";            // `[!]` — matches anything
  const negated = body[0] === "!";
  const chars = [...(negated ? body.slice(1) : body)];
  let out = "";
  for (let k = 0; k < chars.length; k++) {
    const ch = chars[k];
    // a `-` between two characters is a range; anywhere else it is a literal
    const isRange = ch === "-" && k > 0 && k < chars.length - 1;
    out += isRange ? "-" : escapeInClass(ch);
  }
  return `[${negated ? "^" : ""}${out}]`;
}

function escapeLiteral(ch: string): string {
  return /[.^$*+?()[\]{}|\\/]/.test(ch) ? `\\${ch}` : ch;
}

function escapeInClass(ch: string): string {
  return /[\\\]^\-[]/.test(ch) ? `\\${ch}` : ch;
}
