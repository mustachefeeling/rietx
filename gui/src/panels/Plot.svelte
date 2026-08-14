<script lang="ts">
  /**
   * Observed, calculated, difference and reflection ticks.
   *
   * **The window comes from the server.** `/api/result/window` decimates with
   * the same min/max index set `rietx compare` uses, so this plot and that one
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
  import { untrack } from "svelte";

  import { ApiError, api } from "../api";
  import { loadPlotly } from "../lib/plotly";
  import { grabToleranceDeg, joinCurves, nearestPeak, type PeaksPayload } from "../lib/peaks";
  import {
    RESIDUAL_KINDS,
    SCALES,
    curveColors,
    curveToggles,
    formatRegion,
    heldRanges,
    hoverLabel,
    maskShapes,
    mergeRegions,
    normalizeRegion,
    residual,
    scaleValues,
    shows,
    span,
    sqrtTicks,
    tickBand,
    toggleCurve,
    type Protocol,
    type Ranges,
    type ResidualKind,
    type Scale,
  } from "../lib/plot";
  import { coalesce } from "../lib/resize";
  import type { Theme } from "../lib/theme";

  let {
    result,
    plotKey,
    zoom = null,
    error,
    theme = "light",
    peaks = null,
    peaksActive = false,
    hovered = null,
    protocol = { limits: null, regions: [] },
    extent = null,
    channels = null,
    protocolError = "",
    busy = false,
    onhoverpeak = () => {},
    onaddpeak = () => {},
    onmovepeak = () => {},
    ontogglepeak = () => {},
    onremovepeak = () => {},
    onprotocol = () => {},
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
    /** the peak the pointer is over, wherever it is over it — one index in the
     *  shell, threaded to both panels, so the table and the plot point at the
     *  same line (WP-1032) */
    hovered?: number | null;
    /** what is being fitted, from `ProjectDoc` (WP-1033) — *not* a drawing
     *  choice: these persist on the verb and change Rwp, which is why they
     *  wear a different register from the knobs beside them */
    protocol?: Protocol;
    /** the measured 2θ range, which is what the shading has to reach past */
    extent?: [number, number] | null;
    /** `[fitted, measured]` channels — the check that a band is telling the
     *  truth, because a band over points still in the residual is worse than
     *  no band at all */
    channels?: [number, number] | null;
    /** the last refusal from `POST /api/project`, in the verb's own words */
    protocolError?: string;
    busy?: boolean;
    onhoverpeak?: (index: number | null) => void;
    onaddpeak?: (twoTheta: number) => void;
    onmovepeak?: (index: number, twoTheta: number) => void;
    ontogglepeak?: (index: number) => void;
    onremovepeak?: (index: number) => void;
    onprotocol?: (patch: {
      two_theta_limits?: [number, number] | null;
      excluded_regions?: [number, number][];
    }) => void;
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
  /** curves the user has switched off, by id — an *exception* list, so a curve
   *  this build does not know about yet still arrives drawn */
  let hidden = $state<string[]>([]);
  /** the payload the last draw used, so a knob redraws without a refetch */
  let held: any = $state(null);
  /** the toggles this payload offers — background only when there is one, one
   *  row per phase (WP-1032) */
  const toggles = $derived(held ? curveToggles(held, residual(kind, held).label) : []);
  /** What the last paint drew each y axis in.  Plain `let`s, not `$state`: they
   *  are read inside the paint they describe, and a reactive one would make
   *  every paint a reason to paint again. */
  let paintedScale: Scale | null = null;
  let paintedKind: ResidualKind | null = null;

  /** The view on screen, handed back to the next draw (`lib/plot.ts`).
   *
   *  The knob comparison is **untracked**: this is called from inside the fetch
   *  effect as well as the repaint one, and a tracked read there would make
   *  choosing Δ over Δ/σ a reason to ask the server for the window again — the
   *  exact round trip the two effects are split to avoid (caught by the jsdom
   *  suite, which counts the reacts one click costs). */
  function view(): Ranges {
    return heldRanges((node as any)?._fullLayout, untrack(() =>
      ({ yaxis: paintedScale === scale, yaxis2: paintedKind === kind })));
  }

  /** The 2θ window the axis is showing, or null when it is showing all of it.
   *
   *  This is the window the *next fetch* asks for, which is why a peak edit no
   *  longer silently coarsens the picture: the payload follows the axis instead
   *  of falling back to the whole pattern under a pinned range. */
  function shownWindow(): [number, number] | null {
    return view().xaxis ?? null;
  }

  function layout(w: any, colors: ReturnType<typeof curveColors>, nPhases: number,
                  ranges: Ranges): any {
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
    const band = tickBand(nPhases);
    return {
      ...(band ? { yaxis3: band.axis } : {}),
      // What is not being fitted, shaded where it acts.  Drawn from the
      // project document rather than inferred from a hole in the data: a gap
      // in the arrays is what an exclusion *leaves*, not what it is, and a
      // renderer that guessed would be a second authority on the protocol.
      shapes: extent ? maskShapes(protocol, extent, colors) : [],
      // The one arbitration in this panel: while a range gesture is armed the
      // drag belongs to plotly's own select box, and the peak verbs below are
      // suspended for as long as it is (see `arm`).
      dragmode: arm ? "select" : "zoom",
      selectdirection: "h",
      margin: { l: 62, r: 12, t: 8, b: 40 },
      showlegend: true,
      legend: { orientation: "h", y: 1.12, x: 0 },
      font: { color: fg, size: 11 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      // Every axis the user has moved is handed back through `span` (see
      // `heldRanges`); an axis they have not keeps no `range` key at all, which
      // is what leaves plotly autoranging.
      //
      // The x axis is anchored to the *lower* subplot, so the ticks and the
      // title sit under the residual rather than between the two — where the
      // title landed inside the residual plot, on a cumulative χ² curve.
      xaxis: { title: { text: "2θ (°)" }, zeroline: false, domain: [0, 1],
               anchor: "y2", gridcolor: line, ...span(ranges.xaxis) },
      yaxis: {
        title: { text: scale === "linear" ? "intensity" : `intensity (${scale})` },
        domain: [0.28, 1],
        type: scale === "log" ? "log" : "linear",
        gridcolor: line,
        ...(ticks ? { tickmode: "array", ...ticks } : {}),
        ...span(ranges.yaxis),
      },
      yaxis2: { title: { text: res.title }, domain: [0, 0.22], gridcolor: line,
                zeroline: res.zeroline, zerolinecolor: colors.zero,
                ...span(ranges.yaxis2) },
      hovermode: "x unified",
      hoverlabel: hoverLabel((name) => style.getPropertyValue(name)),
    };
  }

  /**
   * Fetch a window and draw it.
   *
   * `request` is a window another panel *asked* for (a report region, an
   * unindexed peak) — the one case where the axis must be moved rather than
   * kept, so it overrides the held view and lets the y axes autorange over
   * whatever is there. Everything else (a zoom drag, a repaint after an edit)
   * passes nothing and keeps the view the user is looking at.
   */
  async function draw(lo?: number, hi?: number, request: [number, number] | null = null) {
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
    await paint(w, request);
  }

  /** Redraw the payload already in hand — a residual or a scaling change is a
   *  choice about the same numbers, so it must not cost a round trip. */
  async function paint(w: any, request: [number, number] | null = null) {
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
    const phases = w.raw ? [] : Object.keys(w.ticks ?? {});
    const band = tickBand(phases.length);
    const traces: any[] = [];
    if (shows(hidden, "obs")) {
      traces.push(
        { x: w.two_theta, y: scaleValues(scale, w.y_obs), name: "observed", mode: "markers",
          type: "scattergl", customdata: w.y_obs,
          marker: { size: 4, color: colors.obs },
          hovertemplate: "%{customdata:.6g}<extra>observed</extra>" });
    }
    // The channels the protocol masks, which are in no result and therefore
    // arrive on their own arm.  Without them a fit range has no *outside* to
    // shade — the axis autoranges to the surviving points, so the picture
    // simply stops where the range does and the user cannot see what they cut
    // (measured on the synthetic fixture: a 3–24° pattern came back as
    // 8.005–18.990°).  Recessive on purpose: they are context, not evidence.
    if (w.excluded?.two_theta?.length && shows(hidden, "masked")) {
      traces.push(
        { x: w.excluded.two_theta, y: scaleValues(scale, w.excluded.y_obs),
          name: "masked", mode: "markers", type: "scattergl",
          customdata: w.excluded.y_obs,
          marker: { size: 3, color: colors.edge, opacity: 0.45 },
          hovertemplate: "%{customdata:.6g}<extra>masked — not in the residual</extra>" });
    }
    if (!w.raw) {
      const res = residual(kind, w);
      if (shows(hidden, "calc")) {
        traces.push({ x: w.two_theta, y: scaleValues(scale, w.y_calc), name: "calculated",
          mode: "lines", type: "scattergl", customdata: w.y_calc,
          line: { width: 1.2, color: colors.calc },
          hovertemplate: "%{customdata:.6g}<extra>calculated</extra>" });
      }
      if (w.y_background?.length && shows(hidden, "bkg")) {
        traces.push({ x: w.two_theta, y: scaleValues(scale, w.y_background), name: "background",
          mode: "lines", type: "scattergl", customdata: w.y_background,
          line: { width: 1, dash: "dot", color: colors.bkg },
          hovertemplate: "%{customdata:.6g}<extra>background</extra>" });
      }
      if (shows(hidden, "diff")) {
        traces.push({ x: w.two_theta, y: res.values, name: res.label, mode: "lines",
          type: "scattergl", yaxis: "y2", line: { width: 1, color: colors.diff } });
      }

      // every emission line's ticks, not just the primary: the Kα2 positions are
      // in here too, which is what stops a doublet reading as an impurity.  They
      // ride on `y3`, a band of their own between the two subplots (WP-1032) —
      // on the residual axis their visibility was a property of which residual
      // was selected, and under cumulative χ² they were a line on the floor.
      phases.forEach((phase, row) => {
        if (!shows(hidden, `ticks:${phase}`)) return;
        const ticks = (w.ticks ?? {})[phase] as number[];
        const y = band!.rows[row];
        traces.push({ x: ticks, y: ticks.map(() => y), yaxis: "y3",
          name: phase, mode: "markers", type: "scattergl",
          marker: { symbol: "line-ns-open", size: 8, line: { width: 1 } },
          hovertemplate: `${phase} %{x:.4f}°<extra></extra>` });
      });
    }
    traces.push(...peakTraces(w, colors));
    ringAt = peaks?.peaks?.length ? traces.length - 1 : -1;

    // read immediately before the react, never held between them (lib/plot.ts)
    const ranges = request ? { xaxis: request } : view();
    paintedScale = scale;
    paintedKind = kind;
    await plotly.react(node, traces, layout(w, colors, phases.length, ranges),
                       // `doubleClick: "autosize"`, not plotly's default
                       // `"reset+autosize"`: reset means *back to the range the
                       // plot was drawn with*, and since the draw above hands
                       // the view back, that range is the zoom itself — measured
                       // in Chrome, a double-click out of a 9.97–14.66° window
                       // became a no-op. Autosize is what "all of it" means for
                       // a pattern, and it is the gesture the window fetch
                       // already listens for (`xaxis.autorange`).
                       { responsive: true, displaylogo: false, doubleClick: "autosize" });
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
    // the other half of the hover link: a marker under the pointer names its
    // row in the panel.  `x unified` hands over every trace's point at that 2θ,
    // so the peak — if there is one there — is the one to read.
    plotNode.removeAllListeners?.("plotly_hover");
    plotNode.on?.("plotly_hover", (ev: any) => {
      if (!peaksActive) return;
      const hit = ev.points?.find((p: any) => p.data?.name === "peaks");
      onhoverpeak(hit ? (hit.customdata?.[0] ?? null) : null);
    });
    plotNode.removeAllListeners?.("plotly_unhover");
    plotNode.on?.("plotly_unhover", () => {
      if (peaksActive) onhoverpeak(null);
    });
    plotNode.removeAllListeners?.("plotly_selected");
    plotNode.on?.("plotly_selected", (ev: any) => {
      // plotly fires this with `undefined` to clear a selection, which is what
      // a plain click inside select mode does — not a zero-width region
      const range = ev?.range?.x;
      if (arm && Array.isArray(range)) selected(range[0], range[1]);
    });
    drawRing();   // a redraw resets the trace, so the ring is put back
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
    // The hover link's own trace, drawn empty and moved by `restyle` (WP-1032):
    // a full `react` per mouse move is exactly the cost task 1 measured, and one
    // ring that changes its two coordinates is the cheapest thing plotly does.
    out.push({
      x: [], y: [], name: "hovered", mode: "markers", type: "scattergl",
      marker: { size: 16, symbol: "circle-open", color: accent, line: { width: 2 } },
      showlegend: false, hoverinfo: "skip",
    });
    return out;
  }

  /** Where the highlight ring sits in the trace list of the last draw. */
  let ringAt = $state(-1);

  /** Move the ring to the hovered line — or off the plot when nothing is. */
  function drawRing() {
    if (!node || !plotly || ringAt < 0 || !held) return;
    const row = hovered === null
      ? undefined
      : peaks?.peaks?.find((p) => p.index === hovered);
    const x = row ? [row.two_theta] : [];
    const y = row ? [heightAt(held, row.two_theta)] : [];
    plotly.restyle?.(node, { x: [x], y: [y] }, [ringAt]);
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
  async function paintRaw(request: [number, number] | null = null) {
    if (!node || !peaks?.pattern?.two_theta?.length) return;
    try {
      plotly = plotly ?? (await loadPlotly());
    } catch (exc) {
      loadError = (exc as Error).message;
      return;
    }
    loadError = "";
    // the masked channels travel here too: this is the view a project has
    // *before* any fit, so it is the only place a fit range can be seen at all
    // — and without them the axis autoranges inside the range and the shading
    // has nothing to shade (found in the browser; jsdom drew no axis)
    const w = { raw: true, two_theta: peaks.pattern.two_theta, y_obs: peaks.pattern.y_obs,
                excluded: peaks.pattern.excluded };
    held = w;
    shown = {
      n: w.two_theta.length,
      total: peaks.pattern.n_total ?? w.two_theta.length,
      lo: w.two_theta[0],
      hi: w.two_theta[w.two_theta.length - 1],
    };
    await paint(w, request);
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

  /**
   * The range gesture, and why it is a *mode* rather than a fourth drag
   * meaning (WP-1033).
   *
   * The canvas already carries five pointer meanings — peak-add, peak-move,
   * shift-toggle, right-click-remove and plotly's zoom drag — and WP-1027
   * measured what a sixth costs when two overlap: a 10 px grab radius is ±1.9°
   * at the survey view, so a zoom drag starting 0.9° from a marker silently
   * moved a line 11°.  The repair there was to make the radius *readable*
   * (`grabToleranceDeg`), so an ambiguous drag falls through to the harmless
   * verb.
   *
   * Here there is no radius to derive, because a region drag is ambiguous with
   * a zoom drag **everywhere** — same button, same shape, same distances.  So
   * the ambiguity is removed rather than arbitrated: arming is an explicit
   * click on a named control, it hands the drag to plotly's own select box
   * (`dragmode: "select"`, which is also the visible feedback), it *suspends*
   * the peak verbs while it holds, and it disarms itself after one selection.
   * Nothing is momentary except the mode the user asked for, and an
   * un-armed drag still zooms, which is the harmless thing.
   *
   * The non-pointer routes are the typed boxes in the strip below and the
   * `.rxt` document's `limits`/`excluded` lines — both of which existed
   * before this gesture did.
   */
  let arm = $state<null | "limits" | "exclude">(null);

  function selected(a: number, b: number) {
    const pair = normalizeRegion([a, b]);
    const which = arm;
    arm = null;   // one drag, one region: the mode does not linger
    if (!pair || !which) {
      clearSelection();
      return;
    }
    if (which === "limits") onprotocol({ two_theta_limits: pair });
    else onprotocol({ excluded_regions: mergeRegions(protocol.regions, pair) });
    clearSelection();
  }

  /** Drop plotly's selection rectangle — the region is now the shading's job,
   *  and a lingering marquee would claim the fact twice. */
  function clearSelection() {
    if (node && plotly) plotly.relayout?.(node, { selections: [] });
  }

  function down(ev: PointerEvent) {
    // armed: the drag is plotly's select box, and every peak verb stands down
    if (arm) return;
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
    if (arm || !g || !peaksActive || !peaks?.peaks) return;
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

  /**
   * Right-click **removes** the line under the pointer (WP-1032).
   *
   * It used to refit the line's whole group through a `window.prompt` for a
   * component count — a modal in the one gesture that has no undo, on a verb the
   * table's `↻` already carries.  Remove is the destructive edit a pointer
   * should be able to make directly; the panel's `×` is its non-pointer route,
   * and the coarse 10-px radius is the same one shift-toggle aims with, because
   * the precision of a *marker* hit does not come from the pixel radius.
   */
  function context(ev: MouseEvent) {
    if (arm || !peaksActive || !peaks?.peaks) return;
    const tt = thetaOf(ev.clientX);
    if (tt === null) return;
    const hit = nearestPeak(peaks.peaks, tt, 10 * degPerPx());
    if (hit === null) return;
    ev.preventDefault();
    onremovepeak(hit);
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
   *
   * `coalesce` is WP-1032's half: one resize costs ~111 ms here and a sidebar
   * drag delivered sixty of them, so the canvas trailed the grip by up to 1.1 s
   * (the measurement, and why the trailing re-run is not optional, are in
   * `lib/resize.ts`).
   */
  function watch() {
    if (observer || !node || typeof ResizeObserver === "undefined") return;
    const fit = coalesce(() => (node && plotly ? plotly.Plots?.resize(node) : undefined));
    observer = new ResizeObserver(fit);
    observer.observe(node);
  }

  $effect(() => () => observer?.disconnect());

  /** The protocol as a *primitive*, so this panel does not refetch on every
   *  ui-only PATCH — the effect-reads-the-project-object trap WP-1027's second
   *  pass recorded, one panel over. */
  const protocolKey = $derived(JSON.stringify([protocol.limits, protocol.regions]));

  // -- the typed route (WP-1033) -------------------------------------
  // Empty means "no limit", which is why the placeholder is the measured
  // extent rather than a zero: a blank box says the whole pattern is fitted,
  // and that is also what `limits none` means in the .rxt document.
  let loText = $state("");
  let hiText = $state("");
  $effect(() => {
    void protocolKey;
    loText = protocol.limits ? String(protocol.limits[0]) : "";
    hiText = protocol.limits ? String(protocol.limits[1]) : "";
  });

  /** Send the typed range. A half-filled or unparseable pair is sent as it
   *  reads and refused by the document's own validator — this client has no
   *  opinion about validity, which is WP-1013's rule for the text pane and the
   *  same rule here: two validators would be two answers. */
  function applyLimits() {
    if (!loText.trim() && !hiText.trim()) {
      onprotocol({ two_theta_limits: null });
      return;
    }
    const num = (text: string) => (text.trim() === "" ? NaN : Number(text));
    onprotocol({ two_theta_limits: [num(loText), num(hiText)] });
  }

  /** The `zoom` prop this panel has already acted on, by **identity**.
   *
   *  A window from another panel is a *request*, and every other reason this
   *  effect runs is not — so the two have to be told apart, and the array's
   *  identity is what does it: the shell writes a fresh pair per click, so
   *  clicking the same region twice asks twice, while a peak edit re-runs the
   *  effect with the same array and keeps the view. Deliberately not `$state`. */
  let asked: [number, number] | null | undefined;

  $effect(() => {
    plotKey; // redraw when the session says the curves moved
    void peaks; // …and when a peak verb answered with a new list
    // …and refetch — not merely repaint — when the protocol moves: the masked
    // points are an arm of the payload, so a repaint of the held copy would
    // shade a region whose points are still the old mask's
    void protocolKey;
    // …and refetch the window when another panel points at one: the zoom is a
    // *server* fetch, not an axis range, so a region the report sent us to comes
    // back at full point budget rather than as the decimated overview stretched
    const request = zoom !== asked ? zoom : null;
    asked = zoom;
    // Any other reason to redraw keeps the window on screen. It used to fall
    // back to the whole pattern, which is what made a peak toggle a zoom reset
    // — the fetch went wide and the axis autoranged after it (lib/plot.ts).
    const window = request ?? shownWindow();
    if (result) {
      draw(window?.[0], window?.[1], request);
    } else if (peaks?.pattern?.two_theta?.length) {
      // no fit yet, but there is a pattern to pick peaks on — indexing's whole
      // situation is a project with no fittable model (WP-1027).  There is no
      // window fetch here, so a request is an axis move and nothing else.
      paintRaw(request);
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
    void hidden;
    void arm;     // the drag mode is layout, so arming redraws
    void extent;
    // …and `held` is read **untracked**, which is the difference between a knob
    // and a payload: a new payload has already been painted by whoever fetched
    // it, so tracking it here made every fetch cost a second identical `react`
    // (counted in Chrome: 2 per zoom drag, 6 at boot, each ~111 ms on a real
    // pattern by WP-1032's measurement — now 1 and 3).
    const w = untrack(() => held);
    if (w) paint(w);
  });

  // the hover link is *not* in the effect above, and that is the whole point:
  // a mouse move must cost one `restyle` of one two-point trace, never a
  // repaint of the pattern (task 1 measured what a repaint costs)
  $effect(() => {
    void hovered;
    void ringAt;
    drawRing();
  });
</script>

<svelte:window onpointermove={moved} onpointerup={up}
  onkeydown={(ev) => { if (ev.key === "Escape" && arm) { arm = null; clearSelection(); } }} />

<section>
  {#if error}
    <p class="note bad">{error}</p>
  {:else if !result && !peaks?.peaks?.length}
    <p class="note muted">
      No fitted curves yet. Press <strong>Run</strong> — or, if you just moved the
      history, run again: a checkout restores parameter values, not a fit.
    </p>
  {:else if !result && peaksActive}
    <p class="note muted">Raw pattern — no fit yet, which is when peaks are picked.</p>
  {:else if loadError}
    <p class="note bad">{loadError} — install the plot extra: <code>pip install 'rietx[gui]'</code></p>
  {/if}
  <!-- The gestures, stated whenever the tab that owns them is showing — fit or
       no fit (WP-1032).  This line used to render only in the *raw* state, so
       the moment a fit existed the pointer verbs were undocumented on screen.
       Each one names its non-pointer route beside it, which is WP-1027's rule
       made visible rather than only true. -->
  {#if arm}
    <!-- While a range gesture is armed it owns the canvas, and this line is
         where that is said: the peak verbs are suspended, not competing. -->
    <p class="note arming">
      <strong>Drag on the plot</strong> to {arm === "limits"
        ? "set the fitted 2θ range" : "exclude a 2θ region"}
      <span class="muted">— the peak gestures are suspended; Esc cancels</span>
    </p>
  {:else if peaksActive && peaks?.peaks?.length}
    <p class="note muted gestures">
      <strong>Click</strong> to add a line <span class="muted">(or the panel's 2θ box)</span> ·
      <strong>drag</strong> a marker to move it <span class="muted">(or the Text pane's 2θ column)</span> ·
      <strong>shift-click</strong> to exclude <span class="muted">(or the row's checkbox)</span> ·
      <strong>right-click</strong> to remove <span class="muted">(or the row's ×)</span>
    </p>
  {/if}
  <!-- role: the div is a pointer-driven editing surface when the Peaks tab is
       active.  Every verb has a non-pointer route too — the line above names
       each — so the pointer path is an accelerator, not the only way in. -->
  <div class="plot" class:armed={arm !== null} role="application"
    aria-label="diffraction pattern"
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
      <!-- Which curves are drawn.  Unpersisted, like the two knobs beside it:
           a drawing choice is not the project's opinion (WP-1015/1029). -->
      {#if toggles.length > 1}
        <div class="segmented curves" role="group" aria-label="curves">
          {#each toggles as curve (curve.id)}
            <button class:on={shows(hidden, curve.id)}
              onclick={() => (hidden = toggleCurve(hidden, curve.id))}
              title="{curve.title} — click to {shows(hidden, curve.id) ? 'hide' : 'show'}"
              >{curve.label}</button>
          {/each}
        </div>
      {/if}
      <p class="note muted tabular">
        {shown.n} of {shown.total} points drawn, {shown.lo.toFixed(3)}–{shown.hi.toFixed(3)}°
        · min/max decimated server-side · zoom refetches the window
      </p>
    </div>
  {/if}
  <!-- The protocol strip (WP-1033), and its separation from the knobs above is
       the point rather than a layout preference: those are drawing choices,
       session-local and unpersisted, while everything here changes what is
       fitted, persists in `project.json` on the verb, and moves Rwp.  Two kinds
       of knob on one plot; if they wore the same clothes a user could not tell
       which one changes the answer. -->
  {#if extent}
    <div class="protocol" role="group" aria-label="what is fitted">
      <label class="field" title="the lowest 2θ the fit includes; empty means the
        whole measured pattern. Channels outside are dropped from the residual,
        so they are in no Rwp or χ² either.">
        <span>Fitted range</span>
        <input class="tabular" type="text" inputmode="decimal" bind:value={loText}
          placeholder={extent[0].toFixed(3)} disabled={busy}
          onkeydown={(ev) => { if (ev.key === "Enter") applyLimits(); }} />
      </label>
      <label class="field" title="the highest 2θ the fit includes; empty means the
        whole measured pattern">
        <span>–</span>
        <input class="tabular" type="text" inputmode="decimal" bind:value={hiText}
          placeholder={extent[1].toFixed(3)} disabled={busy}
          onkeydown={(ev) => { if (ev.key === "Enter") applyLimits(); }} />
      </label>
      <button class="ghost small" onclick={applyLimits} disabled={busy}
        title="send the typed range — project.doc.two_theta_limits">Set</button>
      <button class="ghost small" onclick={() => onprotocol({ two_theta_limits: null })}
        disabled={busy || !protocol.limits}
        title="fit the whole measured pattern again">All</button>

      <div class="segmented arm" role="group" aria-label="select on the plot">
        <button class:on={arm === "limits"} disabled={busy}
          onclick={() => (arm = arm === "limits" ? null : "limits")}
          title="then drag on the plot to set the fitted range — the peak
            gestures stand down while this is armed, and Esc cancels"
          >⇥ range</button>
        <button class:on={arm === "exclude"} disabled={busy}
          onclick={() => (arm = arm === "exclude" ? null : "exclude")}
          title="then drag on the plot to exclude that 2θ region from the
            residual — the peak gestures stand down while this is armed"
          >✂ exclude</button>
      </div>

      {#if protocol.regions.length}
        <ul class="regions" aria-label="excluded regions">
          {#each protocol.regions as region, i (formatRegion(region))}
            <li class="pill tabular" title="excluded from the residual — click ×
              to fit these channels again">
              {formatRegion(region)}
              <button class="ghost tiny" disabled={busy}
                aria-label="stop excluding {formatRegion(region)}"
                onclick={() => onprotocol({
                  excluded_regions: protocol.regions.filter((_, k) => k !== i) })}
                >×</button>
            </li>
          {/each}
        </ul>
      {/if}

      <!-- The check that the shading is telling the truth, on screen rather
           than only in the acceptance run: a band over channels still in the
           residual is worse than no band at all. -->
      {#if channels}
        <p class="note muted tabular count">
          {channels[0].toLocaleString()} of {channels[1].toLocaleString()} channels fitted
        </p>
      {/if}
      {#if held?.stale}
        <p class="note warn">
          the curves shown were fitted over a different set of channels — re-run
        </p>
      {/if}
      {#if protocolError}
        <p class="note bad">{protocolError}</p>
      {/if}
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

  /* An armed range gesture has to say so **where the gesture is**.
     plotly's `updateFx` gives the drag layer one cursor for everything that is
     not a pan — measured in Chrome, `dragmode: "select"` and `dragmode: "zoom"`
     both leave `g.draglayer.cursor-crosshair`, and the rects below it inherit
     it — so arming changed the mode and the pointer went on saying "zoom".
     Set on the plot-area rect rather than on the layer: an inherited cursor
     loses to any direct declaration, so this needs no specificity fight with
     plotly's own stylesheet, and it leaves the axis edge draggers alone. */
  .plot.armed :global(.nsewdrag) {
    cursor: col-resize;
  }

  .knobs {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  /* a phase name is arbitrarily long — clip the button, not the row */
  .segmented.curves button {
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .note {
    margin: 4px 2px;
    font-size: 11.5px;
  }

  .gestures strong {
    font-weight: 600;
    color: var(--fg);
  }

  .arming {
    color: var(--accent);
  }

  .arming strong {
    color: var(--accent);
  }

  /* A register of its own, and deliberately not `.knobs`: a rule above the
     strip and typed fields inside it read as "settings", where a segmented
     button reads as "view".  The only segmented control here arms a *gesture*,
     which is a view of the same setting, not a fourth drawing choice. */
  .protocol {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 6px;
    padding-top: 6px;
    border-top: 1px solid var(--line);
  }

  .field {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11.5px;
    color: var(--muted);
  }

  .field input {
    width: 76px;
    font: var(--mono);
    padding: 2px 5px;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: var(--panel);
    color: var(--fg);
  }

  .regions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .regions li {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 1px 4px 1px 8px;
  }

  .count {
    margin-left: auto;
  }

  .warn {
    color: var(--warn);
  }

  .bad {
    color: var(--bad);
  }
</style>
