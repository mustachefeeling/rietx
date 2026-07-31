/** The command palette's data and its ranking — the actions live in the shell.
 *
 * Every command carries an **echo**: the Python call it is a button for.  That
 * is the GUI's teaching device rather than decoration — this package is
 * API-first, the console already prints what each control did (WP-1010), and a
 * user who learns `ref.set_vary("phases.*.cell.*", True)` from the palette can
 * leave the browser without leaving the package.
 *
 * Ranking is a subsequence match, not a substring one, so `sv` finds "set vary"
 * — but the *score* prefers a contiguous prefix, so typing `run` puts "Run" above
 * "Run this stage" instead of ordering by whatever the array happened to hold.
 */

export interface Command {
  id: string;
  label: string;
  /** the Python call this command is a button for */
  echo: string;
  /** the single-key shortcut, if it has one */
  key?: string;
  /** true when the command cannot run right now (a run in flight, no project) */
  disabled?: boolean;
  run: () => void;
}

/** Score a command against a query: lower is better, `null` when it does not match. */
export function score(label: string, query: string): number | null {
  const text = label.toLowerCase();
  const want = query.trim().toLowerCase();
  if (!want) return 0;
  const at = text.indexOf(want);
  if (at >= 0) return at;                       // contiguous: rank by how early
  let i = 0;
  let spread = 0;
  for (const ch of want) {
    const next = text.indexOf(ch, i);
    if (next < 0) return null;
    spread += next - i;
    i = next + 1;
  }
  return 1000 + spread;                          // subsequence: always after
}

/** The commands matching `query`, best first, disabled ones last.
 *
 * Disabled commands are *shown*: "Cancel" greyed out while nothing runs is how
 * a user learns the shortcut exists, and hiding it would make the palette's
 * contents depend on state in a way nobody can memorise. */
export function rank(commands: readonly Command[], query: string): Command[] {
  return commands
    .map((command, index) => ({ command, index, s: score(command.label, query) }))
    .filter((entry) => entry.s !== null)
    .sort((a, b) =>
      Number(a.command.disabled ?? false) - Number(b.command.disabled ?? false) ||
      (a.s as number) - (b.s as number) ||
      a.index - b.index)
    .map((entry) => entry.command);
}

/**
 * Whether a single-letter shortcut should fire for this event.
 *
 * False while a text field has focus (`f` belongs to the filter box being typed
 * into, not to "free the selection") and false under any modifier, which is
 * where the browser's own bindings live.
 */
export function isShortcutTarget(event: KeyboardEvent): boolean {
  if (event.metaKey || event.ctrlKey || event.altKey) return false;
  const target = event.target as HTMLElement | null;
  if (!target) return true;
  if (target.isContentEditable) return false;
  return !/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName);
}
