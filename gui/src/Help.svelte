<script lang="ts">
  /**
   * The one way this app explains a name (WP-1203).
   *
   * `<Help for="stage_fields:max_iter">iterations</Help>` wraps a term in the
   * `.help` register — WP-1201's cursor-only mark, no glyph and no underline —
   * and a click opens the app's single popover on it.  A second click, Esc or
   * a click away closes it, and focus goes back to the term.
   *
   * It sits beside `App.svelte` rather than in `panels/` because it is not a
   * panel: panels use it.  It declares no styles of its own — the trigger is
   * `.help` and the popover is `.popover`, both in `app.css`, which is where a
   * register's geometry is argued about (`lib/style.test.ts`).
   *
   * Two props, and the pair is the WP's measured rule.  `for` is a corpus key
   * and is what almost every use wants: the sentence lives in `rietx.help`, so
   * the GUI, the CLI and the manual read the same one.  `text` is for a
   * sentence the **server** wrote — `held_because`, a refutation, a maturity
   * message — which no corpus can hold because it is about one row rather than
   * one name.  Those were `title=` attributes until this WP, which put them
   * out of reach of the keyboard the moment WP-1201 moved one off a `<button>`.
   *
   * The trigger is a `<span>` with `role="button"`, not a `<button>`: it wraps
   * running text (a table header, a field's label, a chip's words) and a real
   * button would take the register's fill, weight and padding with it.  What
   * matters is that it is focusable and answers Enter and Space, which it does.
   */
  import { getContext } from "svelte";

  import { HELP_CONTEXT, type HelpOpener } from "./lib/helpContext";

  let {
    for: key = null,
    text = null,
    title = null,
    label = "explain",
    children,
  }: {
    for?: string | null;
    text?: string | null;
    title?: string | null;
    /** what a screen reader announces the trigger as */
    label?: string;
    children?: import("svelte").Snippet;
  } = $props();

  const opener = getContext<HelpOpener | undefined>(HELP_CONTEXT);
  let node = $state<HTMLElement | null>(null);
  const open = $derived(!!node && opener?.isOpen(node) === true);

  function toggle(event: Event) {
    if (!node || !opener) return;
    // a term inside a row that is itself clickable must not run the row's verb
    event.stopPropagation();
    event.preventDefault();
    opener.toggle(node, { key, text, title });
  }

  function onkeydown(event: KeyboardEvent) {
    if (event.key === "Enter" || event.key === " ") toggle(event);
  }
</script>

<span
  bind:this={node}
  class="help"
  role="button"
  tabindex="0"
  aria-label={label}
  aria-haspopup="dialog"
  aria-expanded={open}
  onclick={toggle}
  {onkeydown}
>{@render children?.()}</span>
