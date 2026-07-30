<script lang="ts">
  /**
   * The event log, and the API echo beside it.
   *
   * DESIGN.md's console story: what the GUI does is printed as the call a script
   * would have made, so the log doubles as a session transcript a user can
   * paste. Engine events arrive from the stream verbatim — every field of an
   * event's open `data` dict is rendered, so a field added to a kind shows up
   * here without this panel knowing about it.
   */
  let { lines, dropped }: { lines: string[]; dropped: number } = $props();

  let node: HTMLPreElement | undefined = $state();
  let pinned = $state(true);

  $effect(() => {
    lines;
    if (pinned && node) node.scrollTop = node.scrollHeight;
  });

  function onScroll() {
    if (!node) return;
    pinned = node.scrollHeight - node.scrollTop - node.clientHeight < 24;
  }
</script>

<section>
  <h2>
    Console
    {#if dropped > 0}
      <span class="warn" title="the server's event ring is 4096 frames">
        {dropped} frames dropped
      </span>
    {/if}
    {#if !pinned}<button class="ghost" onclick={() => (pinned = true)}>follow</button>{/if}
  </h2>
  <pre bind:this={node} onscroll={onScroll}>{lines.join("\n")}</pre>
</section>

<style>
  section {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    min-height: 0;
    border-top: 1px solid var(--line);
  }

  h2 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin: 0;
    padding: 8px 10px 4px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
  }

  h2 button {
    padding: 1px 8px;
    font-size: 10px;
  }

  pre {
    flex: 1 1 auto;
    overflow: auto;
    margin: 0;
    padding: 4px 10px 10px;
    font: var(--mono);
    color: var(--fg);
    white-space: pre;
  }

  .warn {
    color: var(--warn);
    text-transform: none;
    letter-spacing: 0;
  }
</style>
