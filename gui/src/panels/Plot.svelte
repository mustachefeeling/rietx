<script lang="ts">
  /**
   * Observed, calculated, difference and reflection ticks.
   *
   * **The window comes from the server.** `/api/result/window` decimates with
   * the same min/max index set `pxrdref compare` uses, so this plot and that one
   * cannot disagree about which points survive; a client-side decimator would be
   * a second answer to the one question a plot must not have two answers to. On
   * zoom we refetch the visible range at full budget, which is what makes
   * inspecting a single peak on a 45 000-point pattern honest rather than
   * interpolated.
   *
   * plotly.js is loaded at runtime from `/plotly.js`, served out of the
   * installed Python package — no vendored 4.8 MB copy in the committed dist,
   * and the page still works air-gapped.  The loader itself is `lib/plotly.ts`,
   * shared with the structure viewer since WP-1015.
   */
  import { ApiError, api } from "../api";
  import { loadPlotly } from "../lib/plotly";
  import {
    RESIDUAL_KINDS,
    SCALES,
    curveColors,
    residual,
    scaleValues,
    sqrtTicks,
    type ResidualKind,
    type Scale,
  } from "../lib/plot";
  import type { Theme } from "../lib/theme";

  let {
    result,
    plotKey,
    zoom = null,
    error,
    theme = "light",
  }: {
    result: any;
    plotKey: number;
    /** a 2θ window another panel asked for (a report region, an unindexed peak);
     *  null means the whole pattern */
    zoom?: [number, number] | null;
    error: string;
    /** the resolved theme, and a *dependency of the repaint effect*: the canvas
     *  keeps the colours it was painted with, so a theme change that only
     *  restyles the page leaves last theme's text on this plot (WP-1029 q) */
    theme?: Theme;
  } = $props();

  let node: HTMLDivElement | undefined = $state();
  let plotly: any = $state(null);
  let observer: ResizeObserver | null = null;
  let loadError = $state("");
  let shown = $state<{ n: number; total: number; lo: number; hi: number } | null>(null);
  /** Drawing choices, not facts about the fit — so neither is persisted, for
   *  WP-1015's reason one panel over: storing one would make a picture the
   *  project's opinion. */
  let kind = $state<ResidualKind>("weighted");
  let scale = $state<Scale>("linear");
  /** the payload the last draw used, so a knob redraws without a refetch */
  let held: any = $state(null);

  function layout(w: any, colors: ReturnType<typeof curveColors>): any {
    const fg = getComputedStyle(document.body).color;
    const res = residual(kind, w);
    const ticks = scale === "sqrt" ? sqrtTicks(Math.max(0, ...(w.y_obs ?? [0]))) : null;
    return {
      margin: { l: 62, r: 12, t: 8, b: 40 },
      showlegend: true,
      legend: { orientation: "h", y: 1.12, x: 0 },
      font: { color: fg, size: 11 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      // anchored to the *lower* subplot, so the ticks and the title sit under
      // the residual rather than between the two — where the title landed
      // inside the residual plot, on top of a cumulative χ² curve
      xaxis: { title: { text: "2θ (°)" }, zeroline: false, domain: [0, 1],
               anchor: "y2" },
      yaxis: {
        title: { text: scale === "linear" ? "intensity" : `intensity (${scale})` },
        domain: [0.28, 1],
        type: scale === "log" ? "log" : "linear",
        ...(ticks ? { tickmode: "array", ...ticks } : {}),
      },
      yaxis2: { title: { text: res.title }, domain: [0, 0.22],
                zeroline: res.zeroline, zerolinecolor: colors.zero },
      hovermode: "x unified",
    };
  }

  async function draw(lo?: number, hi?: number) {
    if (!node || !result) return;
    try {
      plotly = plotly ?? (await loadPlotly());
    } catch (exc) {
      loadError = (exc as Error).message;
      return;
    }
    let w: any;
    try {
      w = await api.window(lo, hi);
    } catch (exc) {
      // A `checkout` clears the result server-side while this component still
      // holds the previous one, so the window 409s `NO_RESULT` — an empty state,
      // not a failure, and an *unhandled* rejection until it was caught here (a
      // real browser reported it as a page error; jsdom never reached the fetch,
      // because it does not load the runtime plotly script).
      shown = null;
      if (!(exc instanceof ApiError && exc.empty)) loadError = (exc as Error).message;
      return;
    }
    loadError = "";
    held = w;
    shown = { n: w.n_returned, total: w.n_total, lo: w.window?.[0] ?? 0, hi: w.window?.[1] ?? 0 };
    await paint(w);
  }

  /** Redraw the payload already in hand — a residual or a scaling change is a
   *  choice about the same numbers, so it must not cost a round trip. */
  async function paint(w: any) {
    if (!node || !plotly) return;
    // sampled per paint, never held: these are what make a repaint on a theme
    // change actually change anything
    const colors = curveColors((name) =>
      getComputedStyle(document.body).getPropertyValue(name));
    const res = residual(kind, w);
    const traces: any[] = [
      { x: w.two_theta, y: scaleValues(scale, w.y_obs), name: "observed", mode: "markers",
        type: "scattergl", customdata: w.y_obs,
        marker: { size: 4, color: colors.obs },
        hovertemplate: "%{customdata:.6g}<extra>observed</extra>" },
      { x: w.two_theta, y: scaleValues(scale, w.y_calc), name: "calculated", mode: "lines",
        type: "scattergl", customdata: w.y_calc, line: { width: 1.2, color: colors.calc },
        hovertemplate: "%{customdata:.6g}<extra>calculated</extra>" },
    ];
    if (w.y_background?.length) {
      traces.push({ x: w.two_theta, y: scaleValues(scale, w.y_background), name: "background",
        mode: "lines", type: "scattergl", customdata: w.y_background,
        line: { width: 1, dash: "dot", color: colors.bkg },
        hovertemplate: "%{customdata:.6g}<extra>background</extra>" });
    }
    traces.push({ x: w.two_theta, y: res.values, name: res.label, mode: "lines",
      type: "scattergl", yaxis: "y2", line: { width: 1, color: colors.diff } });

    // every emission line's ticks, not just the primary: the Kα2 positions are
    // in here too, which is what stops a doublet reading as an impurity
    let row = 0;
    for (const [phase, ticks] of Object.entries(w.ticks ?? {})) {
      const y = -0.5 - row * 0.9;
      traces.push({ x: ticks as number[], y: (ticks as number[]).map(() => y), yaxis: "y2",
        name: phase, mode: "markers", type: "scattergl",
        marker: { symbol: "line-ns-open", size: 8, line: { width: 1 } },
        hovertemplate: `${phase} %{x:.4f}°<extra></extra>` });
      row += 1;
    }

    await plotly.react(node, traces, layout(w, colors),
                       { responsive: true, displaylogo: false });
    // plotly decorates the div with its own emitter at runtime; re-registering
    // without removing would stack one handler per redraw
    const plotNode = node as HTMLDivElement & {
      removeAllListeners?: (name: string) => void;
      on?: (name: string, handler: (ev: any) => void) => void;
    };
    plotNode.removeAllListeners?.("plotly_relayout");
    plotNode.on?.("plotly_relayout", (ev: any) => {
      const a = ev["xaxis.range[0]"];
      const b = ev["xaxis.range[1]"];
      if (typeof a === "number" && typeof b === "number") draw(a, b);
      else if (ev["xaxis.autorange"]) draw();
    });
    watch();
  }

  /**
   * Keep the canvas the size of its box.
   *
   * WP-1015 found this in the structure viewer and it landed here in WP-1029,
   * because it is not a viewer bug: plotly's `responsive: true` listens for
   * **window** resizes only, so a plot whose box shrinks without one keeps an
   * oversized canvas — which then overhangs whatever is below it and swallows
   * every click. This plot had nothing below it until the residual and scaling
   * knobs arrived, and the browser reported the result in the defect's own
   * words: a `<rect class="sdrag drag">` from the plot div "intercepts pointer
   * events" on a button 40 px underneath it.
   */
  function watch() {
    if (observer || !node || typeof ResizeObserver === "undefined") return;
    observer = new ResizeObserver(() => {
      if (node && plotly) plotly.Plots?.resize(node);
    });
    observer.observe(node);
  }

  $effect(() => () => observer?.disconnect());

  $effect(() => {
    plotKey; // redraw when the session says the curves moved
    // …and refetch the window when another panel points at one: the zoom is a
    // *server* fetch, not an axis range, so a region the report sent us to comes
    // back at full point budget rather than as the decimated overview stretched
    const window = zoom;
    if (result) draw(window?.[0], window?.[1]);
    else if (plotly && node) plotly.purge(node);
  });

  // a knob repaints what is already in hand.  Separate from the effect above so
  // that choosing Δ over Δ/σ is not a reason to ask the server anything.  The
  // theme is a knob too — the same numbers under new colours — and it *must* be
  // a dependency here: `getComputedStyle` is sampled at paint time, so a theme
  // change that repaints nothing leaves light-grey text on a white page
  // (WP-1029 q; the shell's `applyTheme` effect is created before this
  // component mounts, so the root attribute is stamped before this reruns).
  $effect(() => {
    void kind;
    void scale;
    void theme;
    if (held) paint(held);
  });
</script>

<section>
  {#if error}
    <p class="note bad">{error}</p>
  {:else if !result}
    <p class="note muted">
      No fitted curves yet. Press <strong>Run</strong> — or, if you just moved the
      history, run again: a checkout restores parameter values, not a fit.
    </p>
  {:else if loadError}
    <p class="note bad">{loadError} — install the plot extra: <code>pip install 'pxrd-refine[gui]'</code></p>
  {/if}
  <div class="plot" bind:this={node}></div>
  {#if shown}
    <div class="knobs">
      <div class="segmented" role="group" aria-label="residual">
        {#each RESIDUAL_KINDS as entry (entry.id)}
          <button class:on={kind === entry.id} onclick={() => (kind = entry.id)}
            title={entry.title}>{entry.label}</button>
        {/each}
      </div>
      <div class="segmented" role="group" aria-label="intensity scale">
        {#each SCALES as entry (entry.id)}
          <button class:on={scale === entry.id} onclick={() => (scale = entry.id)}
            title={entry.title}>{entry.label}</button>
        {/each}
      </div>
      <p class="note muted tabular">
        {shown.n} of {shown.total} points drawn, {shown.lo.toFixed(3)}–{shown.hi.toFixed(3)}°
        · min/max decimated server-side · zoom refetches the window
      </p>
    </div>
  {/if}
</section>

<style>
  section {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    min-width: 0;
    padding: 8px 10px;
  }

  .plot {
    flex: 1 1 auto;
    min-height: 240px;
  }

  .knobs {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .note {
    margin: 4px 2px;
    font-size: 11.5px;
  }

  .bad {
    color: var(--bad);
  }
</style>
