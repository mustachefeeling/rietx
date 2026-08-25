<script lang="ts">
  /** Cmd/Ctrl-K: every action this build has, each showing the call it makes. */
  import { rank, type Command } from "../lib/palette";

  let {
    commands,
    onclose,
  }: { commands: Command[]; onclose: () => void } = $props();

  let query = $state("");
  let cursor = $state(0);

  const shown = $derived(rank(commands, query));

  function choose(command: Command | undefined) {
    if (!command || command.disabled) return;
    onclose();
    command.run();
  }

  function keydown(event: KeyboardEvent) {
    if (event.key === "Escape") return onclose();
    if (event.key === "ArrowDown") {
      cursor = Math.min(shown.length - 1, cursor + 1);
    } else if (event.key === "ArrowUp") {
      cursor = Math.max(0, cursor - 1);
    } else if (event.key === "Enter") {
      choose(shown[cursor]);
    } else {
      return;
    }
    event.preventDefault();
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onclose}>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="panel" onclick={(event) => event.stopPropagation()}>
    <!-- svelte-ignore a11y_autofocus -->
    <input
      autofocus
      placeholder="what would you like to do?"
      bind:value={query}
      oninput={() => (cursor = 0)}
      onkeydown={keydown} />
    <ul>
      {#each shown as command, index (command.id)}
        <li class:on={index === cursor} class:off={command.disabled}>
          <button class="pick" onclick={() => choose(command)} disabled={command.disabled}>
            <span class="label">{command.label}</span>
            {#if command.key}<kbd>{command.key}</kbd>{/if}
            <span class="echo mono muted">{command.echo}</span>
          </button>
        </li>
      {/each}
      {#if !shown.length}
        <li class="muted none">nothing matches</li>
      {/if}
    </ul>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.35);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 12vh;
    z-index: 10;
  }

  .panel {
    width: min(620px, 92vw);
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
    overflow: hidden;
  }

  /* the modal's subject, and it is prominent by width and padding — a field
     is control-sized like every other (WP-1201) */
  input {
    width: 100%;
    padding: 10px 12px;
    border: 0;
    border-bottom: 1px solid var(--line);
    background: transparent;
    color: var(--fg);
    outline: none;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 4px;
    max-height: 46vh;
    overflow-y: auto;
  }

  /* the `.pick` register (app.css) — a whole row is the target — with the
     modal's own rounded highlight */
  li .pick {
    display: flex;
    align-items: baseline;
    gap: var(--s3);
    width: 100%;
    border-radius: var(--r-control);
    padding: var(--s2) var(--s3);
  }

  li.on button {
    background: color-mix(in srgb, var(--accent) 18%, transparent);
  }

  li.off button {
    opacity: 0.45;
  }

  .label {
    flex: 0 0 auto;
  }

  .echo {
    flex: 1 1 auto;
    text-align: right;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  kbd {
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: 0 4px;
    color: var(--muted);
  }

  .none {
    padding: 8px;
  }
</style>
