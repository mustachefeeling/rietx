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

  const OWED: Array<[string, string]> = [
    ["Import / editing", "WP-1014"],
    ["Structure viewer", "WP-1015"],
    ["Series", "WP-1016"],
    ["Peaks / indexing", "WP-1027"],
  ];

  const features = $derived(
    Object.entries((capabilities?.features ?? {}) as Record<string, boolean>)
      .filter(([, on]) => on)
      .map(([name]) => name.replace(/_/g, " ")),
  );
</script>

<section>
  <h2>Panels still owed</h2>
  <ul class="owed">
    {#each OWED as [name, wp] (name)}
      <li>{name} <span class="muted mono">{wp}</span></li>
    {/each}
  </ul>

  <h2>This build</h2>
  <p class="muted small">
    {#if project}plan: <span class="mono">{project.doc.plan ? "selected" : "default"}</span> ·{/if}
    {features.length} features
  </p>
  <p class="small muted">{features.join(" · ")}</p>
</section>

<style>
  section {
    padding: 8px 10px 10px;
    overflow: auto;
    flex: 0 0 auto;
    max-height: 45%;
  }

  h2 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin: 6px 0 4px;
    font-weight: 600;
  }

  ul.owed {
    margin: 0;
    padding-left: 1.1em;
  }

  ul.owed li {
    margin: 1px 0;
  }

  .small {
    font-size: 11.5px;
    margin: 2px 0;
  }
</style>
