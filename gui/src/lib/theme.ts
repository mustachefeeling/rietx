/**
 * Light, dark, or whatever the system says (WP-1029).
 *
 * Three-way rather than a two-state toggle, because "follow the system" is a
 * *choice* and not the absence of one: a user on a machine that switches at
 * dusk wants the app to switch with it, and a user who has decided wants it to
 * stay decided through that switch.  Collapsing the two would make the toggle
 * silently mean "override until the next sunset".
 *
 * The choice is persisted on the verb (WP-1005) like every other GUI setting,
 * but **not in the project** (WP-1044): it goes to `/api/settings`, the app's
 * own `ui` dict in the state directory beside the recent list.  It landed in
 * `ProjectDoc.ui` first, and that made `readUi` re-read it per project — so
 * choosing dark and opening a second project came back `system`, measured in a
 * browser.  A width or Simple/Advanced is plausibly the project's; a theme is a
 * fact about the person and the room they are in.  Two things fall out: it
 * survives the project, the port and the browser profile, and it is settable
 * while a run is in flight, since the app store is not behind WP-1008's
 * mutating-verb 409 (the finding WP-1029 recorded and could not fix from
 * inside `POST /api/project`).
 *
 * What lands in the DOM is the *resolved* value, as `data-theme` on the root
 * element — so every consumer, CSS and CodeMirror alike, reads one answer and
 * none of them re-derives it from `matchMedia`.
 */

export type ThemeChoice = "system" | "light" | "dark";
export type Theme = "light" | "dark";

export const THEME_CHOICES: ThemeChoice[] = ["system", "light", "dark"];

/** What the choice actually means right now. */
export function resolveTheme(choice: ThemeChoice, systemDark: boolean): Theme {
  if (choice === "system") return systemDark ? "dark" : "light";
  return choice;
}

/** Anything else — a stale key, a hand-edited `project.json` — is "system". */
export function readChoice(value: unknown): ThemeChoice {
  return THEME_CHOICES.includes(value as ThemeChoice) ? (value as ThemeChoice) : "system";
}

/**
 * Stamp the resolved theme on the root element.
 *
 * `color-scheme` travels with it, and is not decoration: it is what makes the
 * native controls the app does *not* style — `select` popups, checkboxes,
 * scrollbars, the caret — follow an explicit choice.  Without it, choosing
 * light on a dark system leaves a page of dark dropdowns.
 */
export function applyTheme(theme: Theme, root: HTMLElement): void {
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
}
