/** The one channel between a `<Help>` term and the app's single popover.
 *
 * Context rather than a store module, for the reason `App.svelte`'s own
 * docstring gives: there is one session and one popover, state lives in runes
 * in the shell and is passed down, and a second source of truth for "what is
 * open" is the bug a single instance exists to prevent.  A `<Help>` mounted
 * with no provider degrades to a term that does nothing rather than throwing,
 * which is what keeps it usable in a component test that mounts one panel.
 */

/** What a `<Help>` term asks the shell to show. */
export interface HelpRequest {
  /** an `arm:name` corpus key, or null when the sentence is supplied */
  key: string | null;
  /** a sentence the server wrote, for a fact no corpus can hold */
  text: string | null;
  /** an optional heading for a `text` request */
  title: string | null;
}

export interface HelpOpener {
  /** open on this term, or close if it is already the open one */
  toggle(node: HTMLElement, request: HelpRequest): void;
  /** whether the popover is currently anchored to this term */
  isOpen(node: HTMLElement): boolean;
}

export const HELP_CONTEXT = Symbol("rietx.help");
