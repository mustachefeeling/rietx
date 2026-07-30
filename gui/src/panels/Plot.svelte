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
   * and the page still works air-gapped.
   */
  import { api } from "../api";

  let { result, plotKey, error }: { result: any; plotKey: number; error: string } = $props();

  let node: HTMLDivElement | undefined = $state();
  let plotly: any = $state(null);
  let loadError = $state("");
  let shown = $state<{ n: number; total: number; lo: number; hi: number } | null>(null);

  const COLORS = { obs: "#8a8a8a", calc: "#c23b22", bkg: "#6b7280", diff: "#1f5fa8" };

  function loadPlotly(): Promise<any> {
    if ((window as any).Plotly) return Promise.resolve((window as any).Plotly);
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "/plotly.js";
      script.onload = () => resolve((window as any).Plotly);
      script.onerror = () => reject(new Error("could not load /plotly.js"));
      document.head.appendChild(script);
    });
  }

  function layout(): any {
    const style = getComputedStyle(document.body);
    const fg = style.color;
    return {
      margin: { l: 62, r: 12, t: 8, b: 40 },
      showlegend: true,
      legend: { orientation: "h", y: 1.12, x: 0 },
      font: { color: fg, size: 11 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: { title: { text: "2θ (°)" }, zeroline: false, domain: [0, 1] },
      yaxis: { title: { text: "intensity" }, domain: [0.28, 1] },
      yaxis2: { title: { text: "(obs−calc)/σ" }, domain: [0, 0.22], zeroline: true, zerolinecolor: "#8888" },
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
    const w = await api.window(lo, hi);
    shown = { n: w.n_returned, total: w.n_total, lo: w.window?.[0] ?? 0, hi: w.window?.[1] ?? 0 };

    const traces: any[] = [
      { x: w.two_theta, y: w.y_obs, name: "observed", mode: "markers", type: "scattergl",
        marker: { size: 2.5, color: COLORS.obs } },
      { x: w.two_theta, y: w.y_calc, name: "calculated", mode: "lines", type: "scattergl",
        line: { width: 1.2, color: COLORS.calc } },
    ];
    if (w.y_background?.length) {
      traces.push({ x: w.two_theta, y: w.y_background, name: "background", mode: "lines",
        type: "scattergl", line: { width: 1, dash: "dot", color: COLORS.bkg } });
    }
    traces.push({ x: w.two_theta, y: w.delta, name: "residual", mode: "lines", type: "scattergl",
      yaxis: "y2", line: { width: 1, color: COLORS.diff } });

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

    await plotly.react(node, traces, layout(), { responsive: true, displaylogo: false });
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
  }

  $effect(() => {
    plotKey; // redraw when the session says the curves moved
    if (result) draw();
    else if (plotly && node) plotly.purge(node);
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
    <p class="note muted tabular">
      {shown.n} of {shown.total} points drawn, {shown.lo.toFixed(3)}–{shown.hi.toFixed(3)}°
      · min/max decimated server-side · zoom refetches the window
    </p>
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

  .note {
    margin: 4px 2px;
    font-size: 11.5px;
  }

  .bad {
    color: var(--bad);
  }
</style>
