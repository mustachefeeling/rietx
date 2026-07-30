<script lang="ts">
  /**
   * The structure, rotatable, with **no new JS dependency** (WP-1015).
   *
   * plotly is already on the page — injected at runtime from `/plotly.js`, not
   * vendored (WP-1010) — and `mesh3d` + `scatter3d` are all a ball-and-stick or
   * thermal-ellipsoid view needs.  Everything hard is server-side: the symmetry
   * orbit with each image's *rotated* displacement tensor, the bonds, the cell
   * frame.  This component fetches Cartesian numbers and draws them.
   *
   * **The ellipsoids are the reason this exists**, and they are a diagnostic
   * rather than decoration: their axes are refined quantities, so an
   * over-flexible background — which improves Rwp while inflating ADPs
   * (CLAUDE.md's block projection R²) — arrives here as balloons, and a tensor
   * that is not positive definite arrives as a flat disc with the reason in its
   * hover. Neither is visible in the parameter table, where the same six numbers
   * look like six ordinary rows.
   *
   * Two knobs, and both are *drawing* thresholds rather than facts about the
   * sample, which is why neither is persisted: the probability level rescales
   * client-side from the table the payload carries (no refetch), and the bond
   * tolerance is a server round trip because the server owns the bond rule.
   */
  import { ApiError, api } from "../api";
  import { loadPlotly } from "../lib/plotly";
  import {
    caption,
    layout,
    legend,
    traces,
    unitSphere,
    type Geometry,
    type Mode,
  } from "../lib/structure3d";

  let {
    stamp = 0,
    say = (_line: string) => {},
  }: {
    /** bumped by the model pane every time it re-reads — see the effect below */
    stamp?: number;
    say?: (line: string) => void;
  } = $props();

  let node: HTMLDivElement | undefined = $state();
  let plotly: any = $state(null);
  let observer: ResizeObserver | null = null;
  let geo = $state<Geometry | null>(null);
  let error = $state("");
  let mode = $state<Mode>("ball");
  let phase = $state(0);
  let tolerance = $state(1.15);
  /** The chosen ellipsoid level, held here rather than read off the payload:
   *  every reload brings the server's default back, so a level picked once was
   *  silently reset by the next cell edit (found in a browser). */
  let level = $state("0.5");
  let hidden = $state(new Set<string>());
  let showBoundary = $state(true);

  const sphere = unitSphere();
  const entries = $derived(geo ? legend(geo) : []);
  const levels = $derived(geo ? Object.keys(geo.probability_levels) : []);

  /** Refetch whenever the model pane re-reads, and whenever a knob the *server*
   *  owns moves.
   *
   *  `stamp` rather than `head` directly, and the difference is not cosmetic: a
   *  head move reaches the shell one SSE frame later, while the pane around this
   *  one re-reads the moment its own Apply returns — so following the head would
   *  leave the picture a frame behind the atom table it sits beside.  The pane's
   *  reload is itself driven by the head (WP-1005: the head *is* the working
   *  state), so this is one signal, not two. */
  $effect(() => {
    void stamp;
    void phase;
    void tolerance;
    load();
  });

  /** Draw whenever the geometry or a client-side knob moves.  An `$effect` over
   *  the state rather than a call at each site — WP-1013's rule, learned when a
   *  fifth call site was the one that forgot. */
  $effect(() => {
    void geo;
    void mode;
    void hidden;
    void showBoundary;
    draw();
  });

  async function load() {
    try {
      geo = at(await api.structure3d(phase, tolerance), level);
      error = "";
    } catch (exc) {
      if (exc instanceof ApiError && exc.empty) geo = null;
      else error = (exc as Error).message;
    }
  }

  /** A payload rescaled to the chosen level — the one place the two meet.
   *
   * No refetch: the payload carries k(p) for every level it offers, so this is a
   * client multiply.  The level lives in this component and the geometry comes
   * from the server, and *this* is where they are combined, so a reload cannot
   * quietly hand the server's default back. */
  function at(payload: Geometry, key: string): Geometry {
    const scale = payload.probability_levels[key];
    return scale === undefined
      ? payload
      : { ...payload, probability: Number(key), scale };
  }

  async function draw() {
    const geometry = geo;
    if (!node || !geometry) return;
    try {
      plotly = plotly ?? (await loadPlotly());
    } catch (exc) {
      error = (exc as Error).message;
      return;
    }
    const style = getComputedStyle(document.body);
    // the cell frame is the picture's frame, so it gets the accent rather than
    // `--line`: a hairline border colour is invisible against the page in a 3D
    // scene, and the first browser run drew a box nobody could see
    const cell = style.getPropertyValue("--accent").trim() || "#1f5fa8";
    const muted = style.getPropertyValue("--muted").trim() || "#888";
    const line = style.getPropertyValue("--line").trim() || "#ccc";
    await plotly.react(
      node,
      traces(geometry, mode, sphere, { cell, bond: muted }, hidden,
             showBoundary),
      layout(style.color, line),
      { responsive: true, displaylogo: false });
    watch();
  }

  /**
   * Keep the canvas the size of its box.
   *
   * plotly's `responsive: true` listens for **window** resizes only, and this
   * plot's box changes without one: the legend, the knobs and the caption below
   * it all render *after* the first payload arrives, which shortens the plot
   * div underneath an already-sized canvas.  Found in Chrome and structurally
   * invisible to jsdom, which has no layout — the canvas overhung the legend and
   * swallowed its clicks, so the chips looked live and were not.
   */
  function watch() {
    if (observer || !node || typeof ResizeObserver === "undefined") return;
    observer = new ResizeObserver(() => {
      if (node && plotly) plotly.Plots?.resize(node);
    });
    observer.observe(node);
  }

  $effect(() => () => observer?.disconnect());

  function toggleSpecies(species: string) {
    const next = new Set(hidden);
    if (next.has(species)) next.delete(species);
    else next.add(species);
    hidden = next;
  }

  function setProbability(key: string) {
    level = key;
    if (!geo) return;
    geo = at(geo, key);
    mode = "ellipsoid";
    say(`# ellipsoids at ${(Number(key) * 100).toFixed(0)} % `
      + `(k = ${geo.scale.toFixed(4)} = √χ²₃(${key}))`);
  }
</script>

<section class="viewer">
  <header>
    <h2>View</h2>
    <div class="modes">
      <button class:on={mode === "ball"} class="tiny"
        onclick={() => (mode = "ball")}
        title="spheres at a fraction of the covalent radius — the shape of the
               structure, not of its displacement">balls</button>
      <button class:on={mode === "ellipsoid"} class="tiny"
        onclick={() => (mode = "ellipsoid")}
        title="displacement ellipsoids: refined quantities, so an inflated ADP
               is visible here and nowhere else">ellipsoids</button>
    </div>
    <span class="spacer"></span>
    {#if geo && geo.phases.length > 1}
      <select class="tiny" bind:value={phase}>
        {#each geo.phases as name, i (i)}<option value={i}>{name}</option>{/each}
      </select>
    {/if}
  </header>

  <div class="plot" bind:this={node}></div>

  {#if error}
    <p class="bad tiny">{error}</p>
  {:else if !geo}
    <p class="muted tiny">no structure yet</p>
  {:else}
    <div class="legend">
      {#each entries as entry (entry.species)}
        <button class="chip tiny" class:off={hidden.has(entry.species)}
          onclick={() => toggleSpecies(entry.species)}
          title={entry.sites.map((s) => `${s.label} ×${s.multiplicity}`
            + (s.special ? " (special)" : "")).join(", ")}>
          <span class="dot" style="background:{entry.color}"></span>{entry.species}
        </button>
      {/each}
    </div>

    <div class="knobs">
      {#if mode === "ellipsoid"}
        <label class="inline tiny">probability
          <select class="tiny" value={String(geo.probability)}
            onchange={(e) => setProbability((e.currentTarget as HTMLSelectElement).value)}>
            {#each levels as key (key)}
              <option value={key}>{(Number(key) * 100).toFixed(0)} %</option>
            {/each}
          </select>
        </label>
      {/if}
      <label class="inline tiny" title="a drawing threshold, not physics: a bond is
        drawn at d ≤ tol·(rᵢ+rⱼ) on covalent radii, and no fixed value is right
        for both a large cation and an organic">bonds ≤
        <input type="range" min="0.9" max="1.4" step="0.05" value={tolerance}
          onchange={(e) => (tolerance = Number((e.currentTarget as HTMLInputElement).value))} />
        <span class="mono">{tolerance.toFixed(2)}×</span>
      </label>
      <label class="inline tiny" title="the same atom at the opposite face (a corner
        site drawn at all eight corners) and the bonded neighbours just outside —
        off leaves the cell's own contents and sticks that end in mid-air">
        <input type="checkbox" checked={showBoundary}
          onchange={(e) => (showBoundary = (e.currentTarget as HTMLInputElement).checked)} />
        images outside the cell
      </label>
    </div>

    <p class="muted tiny">{caption(geo, mode)}</p>
    {#if geo.note}<p class="warn tiny">{geo.note}</p>{/if}
    <p class="muted tiny mono">{geo.space_group} · V = {geo.volume.toFixed(2)} Å³</p>
  {/if}
</section>

<style>
  section.viewer {
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
  }

  header {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 0 0 auto;
  }

  h2 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin: 10px 0 4px;
    font-weight: 600;
  }

  .spacer {
    margin-left: auto;
  }

  .plot {
    flex: 1 1 auto;
    min-height: 260px;
  }

  .modes button.on {
    background: var(--accent);
    color: #fff;
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    margin: 4px 0 2px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 1px 6px;
  }

  .chip.off {
    opacity: 0.4;
    text-decoration: line-through;
  }

  .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    display: inline-block;
    border: 1px solid var(--line);
  }

  .knobs {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
    margin: 2px 0;
  }

  .inline {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  input[type="range"] {
    width: 84px;
  }

  select.tiny,
  button.tiny {
    font: inherit;
    font-size: 11px;
    padding: 0 5px;
  }

  p {
    margin: 2px 0;
  }

  .tiny {
    font-size: 11px;
  }

  .bad {
    color: var(--bad);
  }

  .warn {
    color: var(--warn);
  }
</style>
