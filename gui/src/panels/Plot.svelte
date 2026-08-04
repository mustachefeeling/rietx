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
  import { grabToleranceDeg, joinCurves, nearestPeak, type PeaksPayload } from "../lib/peaks";
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
    peaks = null,
    peaksActive = false,
    onaddpeak = () => {},
    onmovepeak = () => {},
    ontogglepeak = () => {},
    onrefitgroup = () => {},
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
    /** the stored peak list with its raw pattern (WP-1027) — what lets this
     *  plot draw before any fit exists, which is indexing's whole situation */
    peaks?: PeaksPayload | null;
    /** the Peaks tab is showing: only then do clicks mean add/move/exclude —
     *  a stray click while reading the report must not edit a peak list */
    peaksActive?: boolean;
    onaddpeak?: (twoTheta: number) => void;
    onmovepeak?: (index: number, twoTheta: number) => void;
    ontogglepeak?: (index: number) => void;
    onrefitgroup?: (group: number) => void;
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
    const style = getComputedStyle(document.body);
    const fg = style.color;
    // the panel border colour, for the grid: plotly's default grid is
    // near-white, which is invisible noise on a light page and glare on a
    // dark one — a themed page themes its grid too
    const line = style.getPropertyValue("--line").trim() || "#dcdcd6";
    const res = w.raw
      ? { title: "(y − fit)/σ per group", label: "", zeroline: true }
      : residual(kind, w);
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
               anchor: "y2", gridcolor: line },
      yaxis: {
        title: { text: scale === "linear" ? "intensity" : `intensity (${scale})` },
        domain: [0.28, 1],
        type: scale === "log" ? "log" : "linear",
        gridcolor: line,
        ...(ticks ? { tickmode: "array", ...ticks } : {}),
      },
      yaxis2: { title: { text: res.title }, domain: [0, 0.22], gridcolor: line,
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
    // One microtask before sampling any style: on a theme change this effect
    // and the shell's `applyTheme` effect wake in the same flush, and this one
    // can run first — sampling here synchronously painted the dark page with
    // the light page's ink (found in Chrome; the 3D panel never had the bug
    // because its draw awaits the plotly loader before it samples).
    await Promise.resolve();
    // sampled per paint, never held: these are what make a repaint on a theme
    // change actually change anything
    const colors = curveColors((name) =>
      getComputedStyle(document.body).getPropertyValue(name));
    const traces: any[] = [
      { x: w.two_theta, y: scaleValues(scale, w.y_obs), name: "observed", mode: "markers",
        type: "scattergl", customdata: w.y_obs,
        marker: { size: 4, color: colors.obs },
        hovertemplate: "%{customdata:.6g}<extra>observed</extra>" },
    ];
    if (!w.raw) {
      const res = residual(kind, w);
      traces.push({ x: w.two_theta, y: scaleValues(scale, w.y_calc), name: "calculated",
        mode: "lines", type: "scattergl", customdata: w.y_calc,
        line: { width: 1.2, color: colors.calc },
        hovertemplate: "%{customdata:.6g}<extra>calculated</extra>" });
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
    }
    traces.push(...peakTraces(w, colors));

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
      if (!result) return; // the raw view has no window route to refetch
      const a = ev["xaxis.range[0]"];
      const b = ev["xaxis.range[1]"];
      if (typeof a === "number" && typeof b === "number") draw(a, b);
      else if (ev["xaxis.autorange"]) draw();
    });
    watch();
  }

  /**
   * The peak layer (WP-1027): markers with σ error bars on the data, the
   * fitted group profiles over it, and — on the raw view, where the lower
   * subplot is otherwise empty — each group's own residual strip.
   *
   * Markers ride at the measured intensity nearest each position, so they sit
   * *on* the curve at every zoom; excluded and otherwise unusable lines are
   * hollow, human-placed ones are diamonds. The group profiles join into one
   * trace with null gaps: sixty windows as sixty traces is a legend, not a
   * layer.
   */
  function peakTraces(w: any, colors: ReturnType<typeof curveColors>): any[] {
    const list = peaks?.peaks;
    if (!list?.length) return [];
    const accent =
      getComputedStyle(document.body).getPropertyValue("--accent").trim() || "#7c6ff0";
    const bad =
      getComputedStyle(document.body).getPropertyValue("--bad").trim() || "#c0392b";
    const out: any[] = [];
    const groups = peaks?.groups ?? [];
    if (groups.length) {
      const fit = joinCurves(groups, (g) => g.y_fit);
      out.push({ x: fit.x, y: sparse(fit.y), name: "peak fit", mode: "lines",
        type: "scattergl", line: { width: 1.4, color: accent },
        hoverinfo: "skip" });
      if (w.raw) {
        const delta = joinCurves(groups, (g) => g.delta);
        out.push({ x: delta.x, y: delta.y, name: "(y−fit)/σ", mode: "lines",
          type: "scattergl", yaxis: "y2", line: { width: 1, color: colors.diff },
          showlegend: false });
      }
    }
    const y = list.map((p) => heightAt(w, p.two_theta));
    out.push({
      x: list.map((p) => p.two_theta),
      y,
      name: "peaks",
      mode: "markers",
      type: "scattergl",
      // the whisker is capped at 3×FWHM: a degenerate component reports σ in
      // *tens of degrees* (measured: 111° after a move made its group's fit
      // fail), and an uncapped bar owns the autorange and paints a line across
      // the whole axis. The number stays honest in the panel's table; here the
      // hollow `fit_failed` marker is what says "degenerate", not bar length.
      error_x: { type: "data",
                 array: list.map((p) => Math.min(p.two_theta_esd, 3 * p.fwhm)),
                 visible: true, color: accent, thickness: 1 },
      marker: {
        size: 9,
        symbol: list.map((p) =>
          p.usable ? (p.origin === "fitted" ? "circle" : "diamond")
                   : (p.origin === "fitted" ? "circle-open" : "diamond-open")),
        color: list.map((p) => (p.usable ? accent : bad)),
        line: { width: 1.2 },
      },
      customdata: list.map((p) =>
        [p.index, [p.origin === "fitted" ? "" : p.origin, ...p.flags]
          .filter(Boolean).join(" ") || "usable"]),
      hovertemplate: "#%{customdata[0]} %{x:.4f}° — %{customdata[1]}<extra>peak</extra>",
    });
    return out;
  }

  /** null-preserving √/log guard — `scaleValues` maps a gap to 0, which would
   *  draw every group profile down to the baseline between windows */
  function sparse(values: (number | null)[]): (number | null)[] {
    if (scale !== "sqrt") return values;
    return values.map((v) => (v == null ? null : v > 0 ? Math.sqrt(v) : 0));
  }

  /** the measured intensity nearest 2θ, in plot (scaled) units */
  function heightAt(w: any, tt: number): number {
    const xs: number[] = w.two_theta ?? [];
    if (!xs.length) return 0;
    let lo = 0;
    let hi = xs.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (xs[mid] < tt) lo = mid;
      else hi = mid;
    }
    const k = Math.abs(xs[lo] - tt) <= Math.abs(xs[hi] - tt) ? lo : hi;
    const v = (w.y_obs ?? [])[k] ?? 0;
    return scale === "sqrt" ? (v > 0 ? Math.sqrt(v) : 0) : v;
  }

  /** Draw the raw pattern alone — the state a project is in before any fit,
   *  which is exactly when peaks are picked and a cell is indexed. */
  async function paintRaw() {
    if (!node || !peaks?.pattern?.two_theta?.length) return;
    try {
      plotly = plotly ?? (await loadPlotly());
    } catch (exc) {
      loadError = (exc as Error).message;
      return;
    }
    loadError = "";
    const w = { raw: true, two_theta: peaks.pattern.two_theta, y_obs: peaks.pattern.y_obs };
    held = w;
    shown = {
      n: w.two_theta.length,
      total: peaks.pattern.n_total ?? w.two_theta.length,
      lo: w.two_theta[0],
      hi: w.two_theta[w.two_theta.length - 1],
    };
    await paint(w);
  }

  // -- pointer interactions (WP-1027) ---------------------------------
  // pixel → 2θ through the axis the 2θ ticks belong to.  The shared axis is
  // anchored to the *lower* subplot, but `_fullLayout.xaxis` spans both — what
  // must not be used is the upper plot's own DOM geometry.
  function thetaOf(clientX: number): number | null {
    const xa = (node as any)?._fullLayout?.xaxis;
    if (!xa || !node) return null;
    const px = clientX - node.getBoundingClientRect().left - xa._offset;
    if (px < 0 || px > xa._length) return null;
    return xa.p2d(px);
  }

  function degPerPx(): number {
    const xa = (node as any)?._fullLayout?.xaxis;
    if (!xa?._length) return 0.01;
    return Math.abs(xa.range[1] - xa.range[0]) / xa._length;
  }

  /** The gesture in flight. `move` is the hit inside the *readable* grab
   *  radius (`grabToleranceDeg` — min(10 px, 1.5× median FWHM)); only that
   *  hit captures the pointer from plotly, so at the survey view — where a
   *  line is subpixel and 10 px spans two degrees — a drag stays plotly's
   *  zoom instead of silently moving a line (measured: a zoom drag starting
   *  0.9° from a marker moved it 11°).  `click` is the coarse 10-px hit that
   *  the non-destructive gestures (shift-toggle) still aim with. */
  let gesture: { move: number; click: number; startX: number; moved: boolean } | null = null;

  function down(ev: PointerEvent) {
    if (!peaksActive || !peaks?.peaks || ev.button !== 0) return;
    const tt = thetaOf(ev.clientX);
    if (tt === null) return;
    const perPx = degPerPx();
    const move = nearestPeak(peaks.peaks, tt, grabToleranceDeg(peaks.peaks, perPx));
    const click = nearestPeak(peaks.peaks, tt, 10 * perPx);
    gesture = { move: move ?? -1, click: click ?? -1, startX: ev.clientX, moved: false };
    if (move !== null) {
      // this gesture is a peak drag, not a zoom: keep it from plotly's drag
      // layer (capture phase — we run before the <rect class="drag"> does)
      ev.stopPropagation();
      ev.preventDefault();
    }
  }

  function moved(ev: PointerEvent) {
    if (gesture && Math.abs(ev.clientX - gesture.startX) > 3) gesture.moved = true;
  }

  function up(ev: PointerEvent) {
    const g = gesture;
    gesture = null;
    if (!g || !peaksActive || !peaks?.peaks) return;
    const tt = thetaOf(ev.clientX);
    if (tt === null) return;
    if (g.moved) {
      if (g.move >= 0) onmovepeak(g.move, tt);
      // a drag that started merely *near* a marker was never captured, so
      // plotly zoomed with it — nothing to do here
    } else if (ev.shiftKey) {
      if (g.click >= 0) ontogglepeak(g.click);
    } else if (g.click < 0) {
      // a plain click on empty space adds a line; near a marker it is
      // ambiguous, and an ambiguous click must not edit anything
      onaddpeak(tt);
    }
  }

  function context(ev: MouseEvent) {
    if (!peaksActive || !peaks?.peaks) return;
    const tt = thetaOf(ev.clientX);
    if (tt === null) return;
    const hit = nearestPeak(peaks.peaks, tt, 10 * degPerPx());
    if (hit === null) return;
    ev.preventDefault();
    onrefitgroup(peaks.peaks.find((p) => p.index === hit)!.group);
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
    void peaks; // …and when a peak verb answered with a new list
    // …and refetch the window when another panel points at one: the zoom is a
    // *server* fetch, not an axis range, so a region the report sent us to comes
    // back at full point budget rather than as the decimated overview stretched
    const window = zoom;
    if (result) {
      draw(window?.[0], window?.[1]);
    } else if (peaks?.pattern?.two_theta?.length) {
      // no fit yet, but there is a pattern to pick peaks on — indexing's whole
      // situation is a project with no fittable model (WP-1027)
      paintRaw();
    } else {
      // the curves are gone server-side (a checkout): drop the held copy too,
      // or the theme/knob repaint below would redraw a state the project is no
      // longer in onto the purged canvas — WP-1012's rule, applied to the copy
      // in hand and not only to the fetch
      held = null;
      shown = null;
      if (plotly && node) plotly.purge(node);
    }
  });

  // a knob repaints what is already in hand.  Separate from the effect above so
  // that choosing Δ over Δ/σ is not a reason to ask the server anything.  The
  // theme is a knob too — the same numbers under new colours — and it *must* be
  // a dependency here: `getComputedStyle` is sampled at paint time, so a theme
  // change that repaints nothing leaves light-grey text on a white page
  // (WP-1029 q; the ordering against the shell's `applyTheme` effect is
  // settled inside `paint`, which defers one microtask before sampling).
  $effect(() => {
    void kind;
    void scale;
    void theme;
    if (held) paint(held);
  });
</script>

<svelte:window onpointermove={moved} onpointerup={up} />

<section>
  {#if error}
    <p class="note bad">{error}</p>
  {:else if !result && !peaks?.peaks?.length}
    <p class="note muted">
      No fitted curves yet. Press <strong>Run</strong> — or, if you just moved the
      history, run again: a checkout restores parameter values, not a fit.
    </p>
  {:else if !result && peaksActive}
    <p class="note muted">
      Raw pattern. Click to add a peak, drag a marker to move it, shift-click to
      exclude, right-click a marker to refit its group.
    </p>
  {:else if loadError}
    <p class="note bad">{loadError} — install the plot extra: <code>pip install 'pxrd-refine[gui]'</code></p>
  {/if}
  <!-- role: the div is a pointer-driven editing surface when the Peaks tab is
       active.  Every verb has a non-pointer route too — add by typed 2θ in the
       panel, move by editing the 2θ column of the text document — so the
       pointer path is an accelerator, not the only way in. -->
  <div class="plot" role="application" aria-label="diffraction pattern"
    bind:this={node} onpointerdowncapture={down} oncontextmenu={context}></div>
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
