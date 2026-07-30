<script lang="ts">
  /**
   * The event log, and the API echo beside it.
   *
   * DESIGN.md's console story: what the GUI does is printed as the call a script
   * would have made, so the log doubles as a session transcript a user can
   * paste. Engine events arrive from the stream verbatim — every field of an
   * event's open `data` dict is rendered, so a field added to a kind shows up
   * here without this panel knowing about it.
   *
   * It is a **sized** pane, not a flexible one. Sharing the sidebar with
   * `flex: 1 1 auto` gave the log half the column and the parameter table the
   * other half, which is the wrong split for a panel you read in glances: the
   * table is the work and the console is the receipt. So the height is explicit,
   * draggable from the top edge, and persisted through `ProjectDoc.ui` — the
   * owner of that key is the shell, as it is for the disclosure flag, so this
   * component reports a new height and never writes one.
   */
  let {
    lines,
    dropped,
    height = 150,
    onresize = (_height: number) => {},
  }: {
    lines: string[];
    dropped: number;
    height?: number;
    onresize?: (height: number) => void;
  } = $props();

  /** Header only — the floor a drag can reach, and what "collapsed" means. */
  const SHUT = 26;
  /** How much of the panel above must survive a drag. */
  const KEEP = 120;

  let node: HTMLPreElement | undefined = $state();
  let section: HTMLElement | undefined = $state();
  let pinned = $state(true);
  /** what a drag or a collapse set locally; `null` means "whatever was saved".
   *  Derived rather than copied from the prop, so this component has one height
   *  and not two that have to be kept in step. */
  let local = $state<number | null>(null);
  const size = $derived(Math.max(SHUT, local ?? height));

  /** The height to restore when the header is clicked open again. Plain, not
   *  `$state`: it is only ever read inside an event handler. */
  let restore = 150;
  $effect(() => {
    if (height > SHUT) restore = height;
  });

  $effect(() => {
    lines;
    if (pinned && node) node.scrollTop = node.scrollHeight;
  });

  function onScroll() {
    if (!node) return;
    pinned = node.scrollHeight - node.scrollTop - node.clientHeight < 24;
  }

  function clamp(value: number): number {
    const available = section?.parentElement?.clientHeight ?? 0;
    // never drag the panel above out of existence; with no measurable parent
    // (jsdom, or before layout) fall back to the floor alone
    const ceiling = available > KEEP + SHUT ? available - KEEP : Number.POSITIVE_INFINITY;
    return Math.round(Math.min(Math.max(value, SHUT), ceiling));
  }

  function grab(event: PointerEvent) {
    const startY = event.clientY;
    const startSize = size;
    (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
    event.preventDefault();

    const move = (moved: PointerEvent) => {
      local = clamp(startSize - (moved.clientY - startY));   // drag up to grow
    };
    const drop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", drop);
      if (size > SHUT) restore = size;
      onresize(size);            // one write per drag, not one per pixel
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", drop);
  }

  function toggle() {
    if (size > SHUT) restore = size;
    local = size > SHUT ? SHUT : clamp(restore);
    onresize(local);
  }
</script>

<section class="console" bind:this={section} style:flex="0 0 {size}px"
  class:shut={size <= SHUT}>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="grip" onpointerdown={grab} title="drag to resize"></div>
  <h2>
    <button class="caret ghost" onclick={toggle} title={size > SHUT ? "collapse" : "expand"}>
      {size > SHUT ? "▾" : "▸"} Console
    </button>
    {#if dropped > 0}
      <span class="warn" title="the server's event ring is 4096 frames">
        {dropped} frames dropped
      </span>
    {/if}
    {#if !pinned && size > SHUT}
      <button class="ghost" onclick={() => (pinned = true)}>follow</button>
    {/if}
  </h2>
  <pre bind:this={node} onscroll={onScroll}>{lines.join("\n")}</pre>
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    min-height: 0;
    border-top: 1px solid var(--line);
    position: relative;
  }

  .grip {
    position: absolute;
    top: -3px;
    left: 0;
    right: 0;
    height: 7px;
    cursor: ns-resize;
    z-index: 2;
  }

  .grip:hover {
    background: color-mix(in srgb, var(--accent) 35%, transparent);
  }

  h2 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin: 0;
    padding: 4px 10px 2px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    flex: 0 0 auto;
  }

  h2 button {
    padding: 1px 8px;
    font-size: 10px;
  }

  .caret {
    font: inherit;
    font-size: 11px;
    color: var(--muted);
    padding: 0 2px;
    letter-spacing: inherit;
    text-transform: inherit;
  }

  pre {
    flex: 1 1 auto;
    overflow: auto;
    margin: 0;
    padding: 2px 10px 8px;
    font: var(--mono);
    color: var(--fg);
    white-space: pre;
    min-height: 0;
  }

  section.shut pre {
    display: none;
  }

  .warn {
    color: var(--warn);
    text-transform: none;
    letter-spacing: 0;
  }
</style>
