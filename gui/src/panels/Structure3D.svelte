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
    DEFAULT_CAMERA,
    axisCamera,
    caption,
    layout,
    legend,
    traces,
    unitCylinder,
    unitSphere,
    type Camera,
    type Geometry,
    type Mode,
  } from "../lib/structure3d";

  import type { Theme } from "../lib/theme";

  let {
    stamp = 0,
    theme = "light",
    say = (_line: string) => {},
  }: {
    /** bumped by the model pane every time it re-reads — see the effect below */
    stamp?: number;
    /** the resolved theme, and a dependency of the draw effect: this panel
     *  samples `--accent` and the body colour at draw time, so a theme change
     *  that does not redraw leaves the old theme's frame and labels on the
     *  canvas (WP-1029 q) */
    theme?: Theme;
    say?: (line: string) => void;
  } = $props();

  let node: HTMLDivElement | undefined = $state();
  let plotly: any = $state(null);
  let observer: ResizeObserver | null = null;
  /** The last camera handed to plotly — see `liveCamera`.  Deliberately not
   *  `$state`: nothing renders it, and making it reactive would redraw on
   *  every frame of a drag. */
  let camera: Camera = DEFAULT_CAMERA;
  /** A camera a *button* chose, which must outrank whatever is on screen. */
  let pending: Camera | null = null;
  let geo = $state<Geometry | null>(null);
  let error = $state("");
  /** Has a first load *settled*? — see `load`. */
  let ready = $state(false);
  let seq = 0;
  let mode = $state<Mode>("ball");
  let phase = $state(0);
  let tolerance = $state(1.15);
  /** The chosen ellipsoid level, held here rather than read off the payload:
   *  every reload brings the server's default back, so a level picked once was
   *  silently reset by the next cell edit (found in a browser). */
  let level = $state("0.5");
  let hidden = $state(new Set<string>());
  let showBoundary = $state(true);
  /** The bond threshold the *label* shows, which follows the drag; `tolerance`
   *  is what the fetch uses and only moves on release.  Two facts, two fields —
   *  the bug was precisely that the cheap one was tied to the expensive one. */
  let toleranceShown = $state(1.15);
  /**
   * How much bigger than k(p) the ellipsoids are drawn.
   *
   * **Not a probability, and never labelled as one.**  k(p) = √χ²₃(p) diverges
   * as p → 1 and `probability_scale(1.0)` raises, so there is no "120 %
   * ellipsoid" to ask for: wanting them bigger is a drawing scale, and the
   * caption states it beside the probability rather than folded into it.
   */
  let exaggeration = $state(1);
  /** The drawing knobs, folded away.  Every one of them was on screen at once
   *  under a 300 px plot in a 380 px column; mode and the view buttons stay in
   *  the open because they are the two anyone reaches for. */
  let knobsOpen = $state(false);
  /** Bumped by the view buttons.  The camera itself is not `$state` — nothing
   *  renders it — so this is what asks the draw effect for one more frame. */
  let view = $state(0);

  const sphere = unitSphere();
  const cylinder = unitCylinder();
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
    void exaggeration;
    void view;
    void theme; // the frame/label colours are sampled at draw time (WP-1029 q)
    draw();
  });

  /**
   * Fetch, at the level this component holds.
   *
   * `seq` is WP-1013's rule one panel over: two quick releases of the bond
   * slider put two requests in flight and they can land out of order, which
   * would leave the picture disagreeing with the control that asked for it.
   * The older answer is dropped rather than merged, for the same reason.
   *
   * `ready` separates "not fetched yet" from "fetched, and there is nothing" —
   * one `geo === null` cannot say both, and the first paint waits on the
   * payload *and* on parsing plotly (measured 605–1447 ms), so the panel spent
   * all of it saying "no structure yet" about a structure that was on its way.
   */
  async function load() {
    const mine = ++seq;
    try {
      const payload = await api.structure3d(phase, tolerance);
      if (mine !== seq) return;
      geo = at(payload, level);
      error = "";
    } catch (exc) {
      if (mine !== seq) return;
      if (exc instanceof ApiError && exc.empty) geo = null;
      else error = (exc as Error).message;
    } finally {
      if (mine === seq) ready = true;
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
    // scene, and the first browser run drew a box nobody could see.  The a/b/c
    // letters take the same colour, so frame and labels read as one object.
    const cell = style.getPropertyValue("--accent").trim() || "#1f5fa8";
    // the camera for this draw: what a button chose, else what the user has
    // rotated to, else the last one handed over
    camera = pending ?? liveCamera() ?? camera;
    pending = null;
    await plotly.react(
      node,
      // the camera is handed to `traces` as well as to `layout`: the key light
      // is computed from it, so it must be the *same* camera this draw uses
      traces(geometry, mode, sphere, cylinder, cell, hidden, showBoundary, camera,
             exaggeration),
      layout(style.color, camera),
      // the default gl3d modebar floats over a panel this small, and one of its
      // buttons (`tableRotation`) sets `dragmode: "turntable"` — which pins the
      // up vector to +z and would silently break the view-down-axis buttons.
      // `toImage` is the one worth keeping: a PNG of the structure for a slide.
      { responsive: true, displaylogo: false, modeBarButtons: [["toImage"]] });
    watch();
  }

  /**
   * The camera plotly is *actually* showing, read back before every redraw.
   *
   * The view has to be re-supplied on every draw, because each one builds new
   * trace objects and replacing a `mesh3d` tears the gl3d scene down and
   * rebuilds it from the layout — which `uirevision` does not cover.  So the
   * question is only where to read it from, and two of the three obvious
   * answers are wrong:
   *
   * - `layout.scene.camera` reports whatever was last passed **in**.  Read it
   *   back and it says the rotation was kept when it was thrown away, which is
   *   why this is measured by comparing screenshots and never by reading state.
   * - `plotly_relayout` — the public signal, and what this component listened
   *   for until now — **does not fire for a gl3d camera drag at all**.
   *   Measured in Chrome against plotly 6.9.0: zero events across a drag that
   *   moved the eye from (1.35, 1.35, 0.95) to (−0.62, −1.41, −1.47), and the
   *   next redraw put the scene back to the opening view.  It was wrong in the
   *   shipped build too, not a regression: the same probe against WP-1015's own
   *   `static/` says the same thing.
   *
   * What is left is the scene object, whose `getCamera()` returns the live
   * `up`/`center`/`eye`/`projection` — private, but it is the only reading of
   * the view that is a reading of the view.  When it is absent the last known
   * camera stands, which is exactly the behaviour it replaces.
   */
  function liveCamera(): Camera | null {
    const scene = (node as any)?._fullLayout?.scene?._scene;
    const live = scene?.getCamera?.();
    // a camera that lost its projection would put the scene back into
    // perspective — and a projection *change* disposes and re-initialises the
    // gl plot, so that is a teardown per redraw, not a cosmetic slip
    return live
      ? { ...live, projection: live.projection ?? DEFAULT_CAMERA.projection }
      : null;
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

  /** Look straight down a lattice vector — the projections a crystallographer
   *  draws, and the cure for the roll that free rotation allows. */
  function look(axis: number) {
    if (!geo) return;
    // the distance from what is on screen, so the button keeps the user's zoom
    pending = axisCamera(geo, axis, liveCamera() ?? camera);
    view += 1;
  }

  function home() {
    pending = DEFAULT_CAMERA;
    view += 1;
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
    <p class="muted tiny">{ready ? "no structure yet" : "loading the structure…"}</p>
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
      <span class="inline tiny" title="look straight down a lattice vector: down a
        puts c up and b right, and so round — the projections a structure is
        normally drawn in">view down
        <button class="tiny" onclick={() => look(0)}>a</button>
        <button class="tiny" onclick={() => look(1)}>b</button>
        <button class="tiny" onclick={() => look(2)}>c</button>
        <button class="tiny" onclick={home}>reset</button>
      </span>
      <span class="spacer"></span>
      <button class="ghost tiny" class:on={knobsOpen}
        onclick={() => (knobsOpen = !knobsOpen)}
        title="drawing thresholds — none of them is a fact about the sample, so
               none is stored in the project">{knobsOpen ? "▾" : "▸"} drawing</button>
    </div>

    {#if knobsOpen}
      <!-- Where each knob lives is settled by *what it changes*, not by taste:
           the server owns anything that changes the payload (the bond threshold
           decides which bonds exist), the client owns anything that only
           changes drawing (a probability rescale, an exaggeration). -->
      <div class="knobs drawer">
        {#if mode === "ellipsoid"}
          <label class="inline tiny">probability
            <select class="tiny" value={String(geo.probability)}
              onchange={(e) => setProbability((e.currentTarget as HTMLSelectElement).value)}>
              {#each levels as key (key)}
                <option value={key}>{(Number(key) * 100).toFixed(0)} %</option>
              {/each}
            </select>
          </label>
          <label class="inline tiny" title="a drawing scale, not a probability: k(p)
            = √χ²₃(p) diverges as p → 1, so there is no ellipsoid above 100 % to
            ask for — this makes them bigger and the caption says so">× size
            <input type="range" min="1" max="4" step="0.25" value={exaggeration}
              oninput={(e) => (exaggeration =
                Number((e.currentTarget as HTMLInputElement).value))} />
            <span class="mono">{exaggeration.toFixed(2)}×</span>
          </label>
        {/if}
        <label class="inline tiny" title="a drawing threshold, not physics: a bond is
          drawn at d ≤ tol·(rᵢ+rⱼ) on covalent radii, and no fixed value is right
          for both a large cation and an organic">bonds ≤
          <!-- the *label* follows the drag and the *fetch* waits for the release:
               one round trip per pixel would be a flood, but showing a number
               is not a fetch -->
          <input type="range" min="0.9" max="1.4" step="0.05" value={tolerance}
            oninput={(e) => (toleranceShown =
              Number((e.currentTarget as HTMLInputElement).value))}
            onchange={(e) => (tolerance =
              Number((e.currentTarget as HTMLInputElement).value))} />
          <span class="mono">{toleranceShown.toFixed(2)}×</span>
        </label>
        <label class="inline tiny" title="the same atom at the opposite face (a corner
          site drawn at all eight corners) and the bonded neighbours just outside —
          off leaves the cell's own contents and sticks that end in mid-air">
          <input type="checkbox" checked={showBoundary}
            onchange={(e) => (showBoundary = (e.currentTarget as HTMLInputElement).checked)} />
          images outside the cell
        </label>
      </div>
    {/if}

    <p class="muted tiny">{caption(geo, mode, exaggeration)}</p>
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
    min-height: 300px;
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
    align-items: center;
    gap: 4px 12px;
    margin: 2px 0;
  }

  .knobs.drawer {
    border: 1px solid var(--line);
    border-radius: 5px;
    padding: 4px 6px;
    background: var(--panel);
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
