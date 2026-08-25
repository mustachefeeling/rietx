<script lang="ts">
  /**
   * What this build can do, and which panels are still owed.
   *
   * Not decoration: the rows come from `/api/capabilities`, whose flags are
   * derived predicates rather than literals, so this list stops claiming a
   * feature the moment the package stops having it. The "owed" list is the
   * reserved-route table's other half — a user seeing "Parameters (WP-1011)"
   * knows the surface exists and the panel does not, which is the truth.
   */
  let { capabilities, project }: { capabilities: any; project: any } = $props();

  /** Empty since WP-1016 built the series panel — the last one the v1.0 GUI plan
   *  named. Kept rather than deleted for the same reason `RESERVED_ROUTES` was
   *  kept when WP-1027 emptied it: the mechanism is what makes the *next* owed
   *  panel visible, and a list that vanishes when it empties has to be
   *  reinvented. */
  const OWED: Array<[string, string]> = [];

  const features = $derived(
    Object.entries((capabilities?.features ?? {}) as Record<string, boolean>)
      .filter(([, on]) => on)
      .map(([name]) => name.replace(/_/g, " ")),
  );
</script>

<section>
  <h2>Panels still owed</h2>
  {#if OWED.length}
    <ul class="owed">
      {#each OWED as [name, wp] (name)}
        <li>{name} <span class="muted mono">{wp}</span></li>
      {/each}
    </ul>
  {:else}
    <p class="muted">
      None — every panel the v1.0 GUI plan named is built.
    </p>
  {/if}

  <h2>This build</h2>
  <p class="muted">
    {#if project}plan: <span class="mono">{project.doc.plan ? "selected" : "default"}</span> ·{/if}
    {features.length} features
  </p>
  <p class="muted">{features.join(" · ")}</p>
</section>

<style>
  section {
    padding: 8px 10px 10px;
    overflow: auto;
    flex: 0 0 auto;
    max-height: 45%;
  }

  h2 {
    margin: 6px 0 var(--s2);
  }

  ul.owed {
    margin: 0;
    padding-left: 1.1em;
  }

  ul.owed li {
    margin: 1px 0;
  }

  p {
    margin: var(--s1) 0;
  }
</style>
