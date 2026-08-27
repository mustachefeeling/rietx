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
    CANDIDATE_AXIS,
    RESIDUAL_KINDS,
    SCALES,
    candidateLines,
    curveColors,
    curveToggles,
    dataOnlyHidden,
    drawnRange,
    formatRegion,
    forget,
    heldRanges,
    isDataOnly,
    maskShapes,
    mergeRegions,
    movedAxes,
    nearestIndex,
    noAxes,
    normalizeRegion,
    pinPatch,
    readout,
    residual,
    scaleValues,
    shows,
    span,
    sqrtTicks,
    tickBand,
    toggleCurve,
    userRanges,
    type CandidateOverlay,
    type Protocol,
    type Ranges,
    type Readout,
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
    candidate = null,
    candidatePicked = false,
    protocol = { limits: null, regions: [] },
    extent = null,
    channels = null,
    wavelengths = null,
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
    /** the indexing candidate whose predicted lines are on the plot (WP-1211)
     *  — selected or merely hovered in the Peaks panel, which is why it arrives
     *  resolved rather than as an index: this component fetches nothing */
    candidate?: CandidateOverlay | null;
    /** whether a candidate is **selected**, as opposed to passed over by the
     *  pointer.  A separate question from which one is drawn, and it has to be:
     *  a selection clears the plot to the data, and if a preview did too then
     *  running the pointer down the candidate table would strobe the model on
     *  and off.  It stays true while a preview is showing over a selection,
     *  which is what makes that case swap the lines and nothing else. */
    candidatePicked?: boolean;
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
    /** the source's emission lines, primary first (WP-1213) — the readout says
     *  d = λ/(2 sin θ) with the first and names a candidate line with its own.
     *  The *instrument's*, off the settings document: the peak list carries a
     *  wavelength too and it is the one the picker ran at, which an instrument
     *  edit afterwards leaves behind. */
    wavelengths?: number[] | null;
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
  /** what was hidden before `data only` was pressed, so the second press puts
   *  the plot back rather than showing everything (WP-1210) */
  let beforeDataOnly = $state<string[] | null>(null);
  /** The payload the last draw used, so a knob redraws without a refetch.
   *
   *  `$state.raw`, and that is not a micro-optimisation: a plain `$state`
   *  **proxies** the object, so `held` and the `w` the fetch handed `paint` are
   *  two identities for one payload — which is the pair `fresh` asks about
   *  (`w !== paintedPayload`), and svelte says so in dev
   *  (`state_proxy_equality_mismatch`, surfaced by WP-1213's derived read of
   *  `held` and true before it). A window payload is replaced whole and never
   *  mutated, which is exactly what `$state.raw` is for; it also keeps a
   *  4000-point `y_obs` out of the proxy the knob repaint maps over. */
  let held: any = $state.raw(null);
  /** the toggles this payload offers — background only when there is one, one
   *  row per phase (WP-1032), the peak layer when a list exists (WP-1210) */
  const toggles = $derived(
    held
      ? curveToggles(held, residual(kind, held).label, {
          n: peaks?.peaks?.length ?? 0,
          groups: peaks?.groups?.length ?? 0,
          active: peaksActive,
        })
      : [],
  );
  const dataOnly = $derived(isDataOnly(toggles, hidden));
  /** The candidate overlay is drawn on the tab that can act on it, exactly as
   *  the peak layer is (WP-1210): the row that selects it is in the Peaks
   *  panel, so away from that tab there is nothing on screen the lines refer
   *  to.  Deriving it here rather than gating at each use is what makes the tab
   *  click *and* the hidden-curve handoff below both follow the tab. */
  const overlay = $derived(peaksActive ? candidate : null);
  /** …and the same gate on the selection, so leaving the tab puts the curves
   *  back as well as taking the lines off. */
  const picked = $derived(peaksActive && candidatePicked);
  /** What the last paint drew each y axis in.  Plain `let`s, not `$state`: they
   *  are read inside the paint they describe, and a reactive one would make
   *  every paint a reason to paint again. */
  let paintedScale: Scale | null = null;
  let paintedKind: ResidualKind | null = null;
  /** …and which payload, so a paint can tell "the same numbers again" from "a
   *  run landed" — the one distinction that licenses re-fitting the axes. */
  let paintedKey: number | null = null;
  let paintedResult: any = null;
  let paintedPayload: any = null;
  /** …and which axes that paint drew nothing on, so a pin outside `paint` — the
   *  raw view's double-click — asks the same question it did. */
  let paintedEmpty: string[] = [];

  /** Which axes a *person* has moved, as plotly reports each gesture.
   *
   *  Since WP-1212 every axis carries an explicit range after the first paint,
   *  so `autorange === false` no longer separates "the user zoomed" from "we
   *  pinned it" — this does, and it is fed from the relayout event rather than
   *  read back off the layout, because by the time it is read the pin has
   *  already been written (`lib/plot.ts:movedAxes`). Plain `let`s again: they
   *  belong to the paint that reads them. */
  let userSet = noAxes();
  /** True while this panel is writing the pin, so its own relayout is not
   *  mistaken for the gesture it looks like. */
  let pinning = false;
  /** Whether the div currently holds a plot.
   *
   *  The fetch effect's last branch purges it (a checkout takes the curves away
   *  server-side) while this panel keeps `plotly`, so any verb aimed at the div
   *  from outside a paint is aimed at an element plotly no longer owns. Reasoned
   *  from that path rather than observed: a browser pass could not get a
   *  checkout to reach the purge branch, so what plotly does there is unproven
   *  and this is a guard on the state, not a repair of a seen throw. */
  let plotted = false;

  /** The view on screen, handed back to the next draw (`lib/plot.ts`).
   *
   *  `fresh` is the paint that may re-fit: the first of a new payload, where a
   *  range measured on the old numbers would clip the new ones. It keeps the
   *  axes the *person* set — a zoom is not thrown away by a run finishing,
   *  which is WP-1044's rule and is now a filter rather than a side effect of
   *  reading `autorange`.
   *
   *  The knob comparison is **untracked**: this is called from inside the fetch
   *  effect as well as the repaint one, and a tracked read there would make
   *  choosing Δ over Δ/σ a reason to ask the server for the window again — the
   *  exact round trip the two effects are split to avoid (caught by the jsdom
   *  suite, which counts the reacts one click costs). */
  function view(fresh = false): Ranges {
    const all = heldRanges((node as any)?._fullLayout, untrack(() =>
      ({ yaxis: paintedScale === scale, yaxis2: paintedKind === kind })));
    return fresh ? userRanges(all, userSet) : all;
  }

  /** The 2θ window the axis is showing, or null when it is showing all of it.
   *
   *  This is the window the *next fetch* asks for, which is why a peak edit no
   *  longer silently coarsens the picture: the payload follows the axis instead
   *  of falling back to the whole pattern under a pinned range. It asks
   *  `userSet` rather than the layout because the pin makes every x range
   *  explicit — and a pinned full view is "all of it", which is a fetch with no
   *  window, not a fetch for plotly's padded range (which reaches past the
   *  pattern at both ends). */
  function shownWindow(): [number, number] | null {
    return userSet.xaxis ? view().xaxis ?? null : null;
  }

  /**
   * Make every autoranging axis explicit, so nothing that follows can move it.
   *
   * The last act of a paint, and the one that carries this WP: a `react` can
   * only hand back a range that already exists, so the *first* paint of a
   * payload has to autorange — and until this runs, the plot is left in the
   * state where a hover's `restyle` re-fits the y axis (measured: 1.03 % of the
   * span, once per row the pointer crosses). Costs a `relayout` on that first
   * paint and nothing at all afterwards, since `pinPatch` returns `{}` once
   * every axis is explicit.
   */
  async function pinAxes(empty: readonly string[] = paintedEmpty) {
    if (!node || !plotly || !plotted) return;
    const patch = pinPatch((node as any)._fullLayout, empty);
    if (!Object.keys(patch).length) return;
    pinning = true;
    try {
      await plotly.relayout?.(node, patch);
    } finally {
      pinning = false;
    }
  }

  /** The pinnable axes carrying no drawn point — plotly fits those to its own
   *  empty default, which is a number to look at and not a range to keep. */
  function emptyAxes(traces: any[]): string[] {
    const on = (axis: string) => traces.some((t) =>
      (t.yaxis ?? "y") === axis && (t.x?.length ?? 0) > 0);
    const out: string[] = [];
    if (!on("y") && !on("y2")) out.push("xaxis");
    if (!on("y")) out.push("yaxis");
    if (!on("y2")) out.push("yaxis2");
    return out;
  }

  function layout(w: any, colors: ReturnType<typeof curveColors>, nPhases: number,
                  ranges: Ranges, armed: boolean): any {
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
      // the candidate overlay's own axis, declared only while it is drawn —
      // an overlaying axis with no trace on it still costs plotly a pass
      ...(overlay ? { yaxis4: CANDIDATE_AXIS } : {}),
      // What is not being fitted, shaded where it acts.  Drawn from the
      // project document rather than inferred from a hole in the data: a gap
      // in the arrays is what an exclusion *leaves*, not what it is, and a
      // renderer that guessed would be a second authority on the protocol.
      shapes: extent ? maskShapes(protocol, extent, colors) : [],
      // The one arbitration in this panel: while a range gesture is armed the
      // drag belongs to plotly's own select box, and the peak verbs below are
      // suspended for as long as it is (see `arm`).
      dragmode: armed ? "select" : "zoom",
      selectdirection: "h",
      // The live gesture dressed as the thing it is about to become (WP-1212).
      // plotly's default marquee is a dark dotted box that says "select", and
      // what an armed drag here means is "exclude this range" — so it is drawn
      // in `maskShapes`' own two colours, from the same `curveColors` call, and
      // `selectdirection: "h"` has already made the box full height, so its two
      // long sides *are* the dotted edges the exclusion will leave behind.
      newselection: { line: { color: colors.edge, width: 1, dash: "dot" } },
      activeselection: { fillcolor: colors.mask, opacity: 1 },
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
      // The pointer's own mark on the data (WP-1213).  `across` rather than
      // plotly's default `toaxis` because the x axis is anchored to the lower
      // subplot: a spike drawn to *its* axis would stop at the residual, and
      // what the reader is lining up is a position in the pattern.
      //
      // Solid, in the page's own ink, and that is a browser finding: dotted in
      // `colors.edge` — the obvious first choice — is `maskShapes`' excluded-
      // region edge exactly, so the pointer drew a line indistinguishable from
      // a protocol boundary. It needs no `--plot-*` token of its own (WP-1210)
      // because it carries no quantity: it is chrome, so it takes `--fg`, which
      // is the one ink on the page no plot colour is near.
      xaxis: { title: { text: "2θ (°)" }, zeroline: false, domain: [0, 1],
               anchor: "y2", gridcolor: line,
               showspikes: true, spikemode: "across", spikesnap: "cursor",
               spikedash: "solid", spikethickness: 1, spikecolor: fg,
               ...span(ranges.xaxis) },
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
      // **The box is gone and the strip below has its job** (WP-1213). The
      // report was that it covered the data, and plotly offers no positioning
      // for the unified box beyond `hoverlabel.align` — so this is not a
      // setting to change but a box to delete. `hovermode: "x"` with every
      // trace at `hoverinfo: "none"` keeps the machinery that finds the point
      // and draws the spike (plotly's own gate is `!== "skip"`) and draws no
      // label at all.
      hovermode: "x",
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
    // First, so everything else draws over it: a candidate's lines are the
    // hypothesis and the points are the evidence, and at a survey view there
    // are enough lines to bury the data completely if they go on top (found in
    // Chrome on the FAP example — 426 predicted lines over 115° is ~3.7 per
    // pixel, and the pattern was simply gone).
    const traces: any[] = [...candidateTraces(colors)];
    if (shows(hidden, "obs")) {
      traces.push(
        { x: w.two_theta, y: scaleValues(scale, w.y_obs), name: "observed", mode: "markers",
          type: "scattergl", hoverinfo: "none",
          marker: { size: 4, color: colors.obs } });
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
          name: "masked", mode: "markers", type: "scattergl", hoverinfo: "none",
          marker: { size: 3, color: colors.edge, opacity: 0.45 } });
    }
    if (!w.raw) {
      const res = residual(kind, w);
      if (shows(hidden, "calc")) {
        traces.push({ x: w.two_theta, y: scaleValues(scale, w.y_calc), name: "calculated",
          mode: "lines", type: "scattergl", hoverinfo: "none",
          line: { width: 1.2, color: colors.calc } });
      }
      if (w.y_background?.length && shows(hidden, "bkg")) {
        traces.push({ x: w.two_theta, y: scaleValues(scale, w.y_background), name: "background",
          mode: "lines", type: "scattergl", hoverinfo: "none",
          line: { width: 1, dash: "dot", color: colors.bkg } });
      }
      if (shows(hidden, "diff")) {
        traces.push({ x: w.two_theta, y: res.values, name: res.label, mode: "lines",
          type: "scattergl", yaxis: "y2", hoverinfo: "none",
          line: { width: 1, color: colors.diff } });
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
          name: phase, mode: "markers", type: "scattergl", hoverinfo: "none",
          marker: { symbol: "line-ns-open", size: 8, line: { width: 1 } } });
      });
    }
    traces.push(...peakTraces(w, colors));
    // by name, not by position: the layer's traces are conditional now, so
    // counting back from the end named whichever one happened to be last
    ringAt = traces.findIndex((t: any) => t.name === "hovered");

    // read immediately before the react, never held between them (lib/plot.ts)
    //
    // `fresh` is the paint that may re-fit the axes: a run or a checkout put
    // different numbers on the plot, and a range pinned to the old ones would
    // clip them. Untracked, like the knobs beside it — the knob effect must not
    // gain `plotKey` as a dependency, or every run costs a second identical
    // react (the count WP-1044 measured and removed).
    //
    // **New numbers and a new payload**, both: a project switch moves `plotKey`
    // and `extent` in one flush, and the knob effect's paint of the payload
    // still in hand can land first — the fetch is a round trip and a repaint is
    // one microtask. With `plotKey` alone that repaint would spend the licence
    // re-fitting the axes over the *old* pattern, and the new one would then be
    // handed those ranges as a pin.
    const fresh = w !== paintedPayload
      && untrack(() => plotKey !== paintedKey || result !== paintedResult);
    // …and a knob that re-means an axis un-says whatever was said about it
    // (`forget`), which is `heldRanges`' own `live` gate one step later: that
    // one decides what this paint hands back, this one what the next re-fit may
    // keep.  Before `view`, which reads the flags it clears.
    userSet = forget(userSet, { yaxis: paintedScale === scale, yaxis2: paintedKind === kind });
    const ranges = request ? { xaxis: request } : view(fresh);
    paintedScale = scale;
    paintedKind = kind;
    paintedPayload = w;
    untrack(() => { paintedKey = plotKey; paintedResult = result; });
    await plotly.react(node, traces,
                       layout(w, colors, phases.length, ranges, untrack(() => arm !== null)),
                       // `doubleClick: "autosize"`, not plotly's default
                       // `"reset+autosize"`: reset means *back to the range the
                       // plot was drawn with*, and since the draw above hands
                       // the view back, that range is the zoom itself — measured
                       // in Chrome, a double-click out of a 9.97–14.66° window
                       // became a no-op. Autosize is what "all of it" means for
                       // a pattern, and it is the gesture the window fetch
                       // already listens for (`xaxis.autorange`).
                       { responsive: true, displaylogo: false, doubleClick: "autosize" });
    plotted = true;
    // plotly decorates the div with its own emitter at runtime; re-registering
    // without removing would stack one handler per redraw
    const plotNode = node as HTMLDivElement & {
      removeAllListeners?: (name: string) => void;
      on?: (name: string, handler: (ev: any) => void) => void;
    };
    plotNode.removeAllListeners?.("plotly_relayout");
    plotNode.on?.("plotly_relayout", (ev: any) => {
      // this panel's own pin is a relayout too, and it must not be read as the
      // gesture it is shaped like (`lib/plot.ts:movedAxes`)
      if (pinning) return;
      const { moved, reset } = movedAxes(ev);
      if (reset) userSet = noAxes();
      for (const key of moved) userSet[key] = true;
      if (!result) {
        // the raw view has no window route to refetch, so a double-click's
        // re-fit is followed by no paint at all — pin it here, or the axes are
        // left autoranging and the next hover restyle moves them again
        if (reset) queueMicrotask(() => void pinAxes());
        return;
      }
      const a = ev["xaxis.range[0]"];
      const b = ev["xaxis.range[1]"];
      if (typeof a === "number" && typeof b === "number") draw(a, b);
      else if (ev["xaxis.autorange"]) draw();
    });
    // The pointer's 2θ, which is the whole of this panel's hover state: the
    // strip is derived from it and the peak link is `nearestPeak` at the same
    // radius the pointer verbs aim with.  It used to read plotly's own match
    // (`ev.points`, the trace named `peaks`), which was a second answer to
    // "which line is under the pointer" — decided by `hoverdistance` in pixels
    // rather than by the readable radius a click obeys (WP-1027).
    plotNode.removeAllListeners?.("plotly_hover");
    plotNode.on?.("plotly_hover", (ev: any) => {
      // …and it is read through this panel's own axis map rather than off
      // `ev.points[0]`, which is whichever *trace* plotly matched first: the
      // ticks ride on reflection positions and the markers on peak positions,
      // so the first point is not a stable answer to "where is the pointer".
      // The event's own clientX is, and `thetaOf` is the same conversion every
      // pointer verb here uses.
      const px = ev?.event?.clientX;
      const from = ev?.points?.[0]?.x;
      const x = typeof px === "number" ? thetaOf(px)
        : (typeof from === "number" ? from : null);
      hoverAt = x;
      if (peaksActive && peaks?.peaks?.length && hoverAt !== null) {
        onhoverpeak(nearestPeak(peaks.peaks, hoverAt,
                                grabToleranceDeg(peaks.peaks, degPerPx())));
      }
    });
    plotNode.removeAllListeners?.("plotly_unhover");
    plotNode.on?.("plotly_unhover", () => {
      hoverAt = null;
      if (peaksActive) onhoverpeak(null);
    });
    plotNode.removeAllListeners?.("plotly_selected");
    plotNode.on?.("plotly_selected", (ev: any) => {
      // plotly fires this with `undefined` to clear a selection, which is what
      // a plain click inside select mode does — not a zero-width region
      const range = ev?.range?.x;
      if (arm && Array.isArray(range)) selected(range[0], range[1]);
    });
    // before the ring goes back on, so the restyle that puts it there cannot be
    // the thing that re-fits the axis (WP-1212's whole report).  An axis with
    // nothing drawn on it is *not* pinned: plotly's empty-axis default is a
    // number to look at, not a fit to keep (`pinPatch`, where the measurement
    // that makes this a guard rather than a repair is written down).
    paintedEmpty = emptyAxes(traces);
    await pinAxes(paintedEmpty);
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
   *
   * Three rules since WP-1210. **It is drawn where it can be edited** — the
   * Peaks tab, which is already the only tab a click on this plot means
   * anything on (WP-1027); elsewhere it was a layer nobody could act on, in a
   * colour nobody had chosen. **Its colours are its own tokens**, `--plot-peak`
   * and `--plot-peakfit`: `--accent` and `--bad` are chrome, and on the light
   * theme they are `--plot-diff` and `--plot-calc` exactly, which is why the
   * fitted curve and the model were one red line. And **the state of a line is
   * carried by its mark, never by a second colour** — hollow for unusable,
   * diamond for human-placed — so the layer spends two colours and the whole
   * palette stays separable.
   */
  function peakTraces(w: any, colors: ReturnType<typeof curveColors>): any[] {
    const list = peaks?.peaks;
    if (!list?.length || !peaksActive) return [];
    const out: any[] = [];
    const groups = peaks?.groups ?? [];
    if (groups.length && shows(hidden, "peakfit")) {
      const fit = joinCurves(groups, (g) => g.y_fit);
      out.push({ x: fit.x, y: sparse(fit.y), name: "peak fit", mode: "lines",
        type: "scattergl", showlegend: true, hoverinfo: "none",
        // dashed, because the other two curves on this axis are solid lines and
        // a reader has to tell "what the positions were fitted from" from "the
        // model" without consulting a legend.  The other half of that naming is
        // the readout strip's `peak fit` row (WP-1213): it used to be the hover
        // box's, and the box is gone.
        line: { width: 1.4, color: colors.peakfit, dash: "dash" } });
      if (w.raw) {
        const delta = joinCurves(groups, (g) => g.delta);
        out.push({ x: delta.x, y: delta.y, name: "(y−fit)/σ", mode: "lines",
          type: "scattergl", yaxis: "y2", hoverinfo: "none",
          line: { width: 1, color: colors.peakfit }, showlegend: false });
      }
    }
    if (!shows(hidden, "peaks")) return out;
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
                 visible: true, color: colors.peak, thickness: 1 },
      marker: {
        size: 9,
        symbol: list.map((p) =>
          p.usable ? (p.origin === "fitted" ? "circle" : "diamond")
                   : (p.origin === "fitted" ? "circle-open" : "diamond-open")),
        // **One colour for the whole layer**, and the ring says which state:
        // hollow is unusable, filled is in the fit.  Spending a second colour
        // on the state is the thing this WP's own rule forbids, and both
        // candidates for it are measurably wrong anyway — `--bad` *is*
        // `--plot-calc` on the light theme, `--warn` sits 0.053 from it (0.096
        // dark), and the recessive `--muted` this line used first is **0.032**
        // from `--plot-obs` on the dark theme, which is the ink of the very
        // points these markers sit on.  All three against a 0.13 floor.
        color: colors.peak,
        line: { width: 1.2 },
      },
      showlegend: true,
      hoverinfo: "none",
    });
    // The hover link's own trace, drawn empty and moved by `restyle` (WP-1032):
    // a full `react` per mouse move is exactly the cost task 1 measured, and one
    // ring that changes its two coordinates is the cheapest thing plotly does.
    // …and it is the one trace here that is **not** `scattergl`, which is a
    // browser finding rather than a preference (WP-1212): every gl trace on a
    // subplot shares one `_scene` whose batches are indexed by position, an
    // *empty* gl trace is given no index at all, and a select drag then reads
    // `scene.selectBatch[undefined].length` and throws once per pointer move —
    // measured, 7 throws over one armed exclude drag. This trace is empty
    // whenever nothing is hovered, which is most of the time. One marker in SVG
    // costs nothing and leaves the scene alone.
    out.push({
      x: [], y: [], name: "hovered", mode: "markers", type: "scatter",
      marker: { size: 16, symbol: "circle-open", color: colors.peak, line: { width: 2 } },
      showlegend: false, hoverinfo: "skip",
    });
    return out;
  }

  /**
   * An indexing candidate's predicted lines, under the data (WP-1211).
   *
   * **First** in the trace list, and that is a browser finding rather than a
   * preference: 426 predicted lines over the FAP example's 115° is ~3.7 per
   * pixel at the survey view, and drawn on top they buried the pattern
   * completely — the overlay hiding the one thing it exists to be compared
   * with. Under it, the density reads as a wash and every measured point stays
   * on top of it, which is also the honest order: the lines are a hypothesis
   * and the points are the evidence.
   *
   * Full height on an axis of their own rather than ticks in the band below,
   * for the same reason: a tick states a fitted model's position, and this is a
   * cell's claim laid *over* the data to be checked against it.
   *
   * No hover. `hovermode` is `x unified`, so plotly snaps *every* trace to its
   * nearest point in x and this one would put a row in the box at every
   * pointer position, in the same box the peak hover link reads. The hkl the
   * route serves beside the positions is what a per-line readout would say, and
   * that readout is WP-1213's.
   */
  function candidateTraces(colors: ReturnType<typeof curveColors>): any[] {
    const rows = overlay;
    if (!rows?.two_theta?.length) return [];
    const { x, y } = candidateLines(rows.two_theta);
    return [{
      x, y, yaxis: "y4", name: rows.label, mode: "lines", type: "scattergl",
      line: { width: 1, color: colors.candidate },
      showlegend: true, hoverinfo: "skip",
    }];
  }

  /**
   * The 2θ under the pointer, or null while it is off the plot (WP-1213).
   *
   * The *only* hover state this panel keeps: the strip below is derived from
   * it, so a pointer move costs one recompute of a value object and no plotly
   * call at all — which is WP-1032's rule ("a hover link costs a `restyle`,
   * never a `react`") one step cheaper, because a strip is DOM.
   */
  let hoverAt = $state<number | null>(null);

  /** What the strip prints. Derived, so the resting state and a reading are the
   *  same shape and the row of fields cannot reflow under the pointer. */
  const reading = $derived<Readout | null>(readout(held, hoverAt, {
    kind,
    wavelengths,
    peaks: peaks?.peaks ?? null,
    peaksActive,
    // the same radius the pointer verbs aim with, so the strip names the line
    // a click would take — one hit test, not a second opinion
    peakTolerance: peaks?.peaks?.length
      ? grabToleranceDeg(peaks.peaks, degPerPx()) : undefined,
    groups: peaks?.groups ?? null,
    candidate: overlay,
    candidateTolerance: 10 * degPerPx(),
    hidden,
  }));

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

  /** Hide everything but the data — or, pressed again, put back exactly what
   *  was on screen before, which is not the same as showing everything: a user
   *  who had already switched a phase's ticks off did not ask for them back. */
  function toggleDataOnly() {
    if (dataOnly) {
      hidden = beforeDataOnly ?? [];
      beforeDataOnly = null;
    } else {
      beforeDataOnly = hidden;
      hidden = dataOnlyHidden(toggles);
    }
  }

  /** The button. Pressing it by hand takes ownership of the state back from the
   *  overlay below, so a person who puts the curves up while a candidate is
   *  selected keeps them up when it is deselected. */
  function showDataOnly() {
    clearedForCandidate = false;
    toggleDataOnly();
  }

  /** Whether the *overlay's* arrival is what cleared the plot to the data.
   *
   *  There is one saved list and one path to it (`toggleDataOnly`), because two
   *  slots means four interleavings of two presses and no rule a reader could
   *  state. This flag is the rule: the press the overlay made, the overlay
   *  undoes; any other press is somebody else's. */
  let clearedForCandidate = $state(false);

  /**
   * "Through *just* the data" — selecting a candidate presses `data only`.
   *
   *  Through the button's own press rather than a mode of its own: an armed
   *  mode has to decide what a manual toggle underneath it means, which is the
   *  design WP-1210 declined for the same button. A plot already showing the
   *  data alone is left as it is and not taken over, so deselecting cannot
   *  un-clear a plot the overlay never cleared.
   *
   *  On `picked` and not on `overlay`: a hover preview draws lines without
   *  clearing anything, or running the pointer down the candidate table would
   *  strobe the model on and off once per row.
   */
  $effect(() => {
    const up = picked;
    untrack(() => {
      if (up && !clearedForCandidate && !dataOnly) {
        toggleDataOnly();
        clearedForCandidate = true;
      } else if (!up && clearedForCandidate) {
        if (dataOnly) toggleDataOnly();
        clearedForCandidate = false;
      }
    });
  });

  /** null-preserving √/log guard — `scaleValues` maps a gap to 0, which would
   *  draw every group profile down to the baseline between windows */
  function sparse(values: (number | null)[]): (number | null)[] {
    if (scale !== "sqrt") return values;
    return values.map((v) => (v == null ? null : v > 0 ? Math.sqrt(v) : 0));
  }

  /** the measured intensity nearest 2θ, in plot (scaled) units.  The nearest
   *  channel is `nearestIndex`, shared with the readout (WP-1213): one plot,
   *  one answer to "which channel is under this 2θ". */
  function heightAt(w: any, tt: number): number {
    const k = nearestIndex(w.two_theta ?? [], tt);
    if (k < 0) return 0;
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
    // `drawnRange`, not `xa.range`: on the first plot of a fresh div the two
    // disagree and only `_rl` matches the pixel map this is dividing by
    // (WP-1212).
    const range = xa?._length ? drawnRange(xa) : null;
    if (!range) return 0.01;
    return Math.abs(range[1] - range[0]) / xa._length;
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
  /** …and the same trick for the measured extent, for the same reason: both are
   *  `$derived` off `project`, so both arrive new-but-equal on every settings
   *  PATCH, and an effect keyed on the object repaints for nothing. */
  const extentKey = $derived(JSON.stringify(extent));

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
    // an asked-for window is somebody having said where to look, so it survives
    // a later re-fit exactly as a zoom drag does (`userRanges`)
    if (request) userSet.xaxis = true;
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
      plotted = false;
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
    // …and the peak layer is drawn only on the tab that can edit it (WP-1210),
    // so leaving that tab has to take it off the plot.  A repaint, not a
    // refetch: which tab is up says nothing about which channels the server
    // sent — the tab click was a redraw of nothing without this line, and
    // `App.test.ts`'s hover-link test is what said so.
    void peaksActive;
    // …and the candidate overlay is one too: selecting a row in another panel
    // has to redraw this one, and it is a repaint rather than a refetch for
    // the same reason — which lines a cell predicts says nothing about which
    // channels the server sent
    void candidate;
    // …and the shading, when the pattern it is clipped against changes.  By its
    // *value*: `extent` is `$derived` off `project`, so every settings PATCH
    // hands this effect a new array holding the same two numbers — measured as
    // one of the four reacts an exclude drag cost (WP-1212).
    void extentKey;
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

  // …and arming is not in it either, for the same reason one rank up: the drag
  // mode is a single layout key, so it is a `relayout` and not a repaint of the
  // pattern.  It was one of the four reacts an exclude drag cost, and it was
  // two of them — the mode is set on the way in and cleared on the way out
  // (WP-1212).  `layout()` still says the mode, so a react that happens while
  // armed is truthful; it reads `arm` untracked, or this line would be undone
  // by the repaint effect's own paint.
  $effect(() => {
    const mode = arm ? "select" : "zoom";
    untrack(() => {
      // `plotted` too: before this WP arming went through the repaint effect,
      // which no-oped on `held === null`, and this one does not — so it is the
      // first thing that can aim a plotly verb at a purged div (`plotted`).
      if (node && plotly && plotted) plotly.relayout?.(node, { dragmode: mode });
    });
  });
</script>

<svelte:window onpointermove={moved} onpointerup={up}
  onkeydown={(ev) => { if (ev.key === "Escape" && arm) { arm = null; clearSelection(); } }} />

<section>
  {#if error}
    <p class="hint bad">{error}</p>
  {:else if !result && !peaks?.peaks?.length}
    <p class="hint muted">
      No fitted curves yet. Press <strong>Run</strong> — or, if you just moved the
      history, run again: a checkout restores parameter values, not a fit.
    </p>
  {:else if !result && peaksActive}
    <p class="hint muted">Raw pattern — no fit yet, which is when peaks are picked.</p>
  {:else if loadError}
    <p class="hint bad">{loadError} — install the plot extra: <code>pip install 'rietx[gui]'</code></p>
  {/if}
  <!-- The gestures, stated whenever the tab that owns them is showing — fit or
       no fit (WP-1032).  This line used to render only in the *raw* state, so
       the moment a fit existed the pointer verbs were undocumented on screen.
       Each one names its non-pointer route beside it, which is WP-1027's rule
       made visible rather than only true. -->
  {#if arm}
    <!-- While a range gesture is armed it owns the canvas, and this line is
         where that is said: the peak verbs are suspended, not competing. -->
    <p class="hint arming">
      <strong>Drag on the plot</strong> to {arm === "limits"
        ? "set the fitted 2θ range" : "exclude a 2θ region"}
      <span class="muted">— the peak gestures are suspended; Esc cancels</span>
    </p>
  {:else if peaksActive && peaks?.peaks?.length}
    <p class="hint muted gestures">
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
  <!-- The readout (WP-1213), under the plot rather than over it.  The report
       was "the tooltip frequently covers a large part of the data", and plotly
       offers no positioning for its unified box beyond `hoverlabel.align` — so
       the box is deleted rather than moved, and everything it said is here,
       beside the plot's other control rows.

       Every field keeps its slot while the pointer is off the plot and prints
       an em dash: a strip that grew fields on hover would resize the canvas
       above it once per entry, and the value widths are fixed in `ch` below so
       the wrap points cannot move under the pointer either.  Which fields
       there are is a property of the payload and the tab — never of where the
       pointer is (`lib/plot.ts:readout`). -->
  {#if reading}
    <div class="readout" role="group" aria-label="under the pointer">
      <span class="field">
        <span class="key">2θ</span>
        <span class="val mono tabular">{reading.position}</span>
      </span>
      <span class="field">
        <span class="key">d</span>
        <span class="val mono tabular">{reading.d}</span>
      </span>
      {#each reading.rows as row (row.id)}
        <span class="field" class:wide={row.id === "peaks" || row.id === "candidate"}>
          <!-- the mark's own ink, so the strip says which curve is which twice
               over: `ReadoutInk` is `curveColors`' key set, and a key is the
               `--plot-*` token's suffix by construction (WP-1210's rule — a
               plot mark has a token of its own) -->
          <span class="key" title={row.label}
            style:color={row.ink ? `var(--plot-${row.ink})` : null}>{row.label}</span>
          <span class="val mono tabular">{row.value}</span>
        </span>
      {/each}
    </div>
  {/if}
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
            <!-- an absent curve is listed and disabled, its title the reason:
                 "where did my markers go" has an answer, and a missing button
                 is not it (WP-1210) -->
            <button class:on={shows(hidden, curve.id) && !curve.absent}
              disabled={!!curve.absent}
              onclick={() => (hidden = toggleCurve(hidden, curve.id))}
              title={curve.absent
                     ? `${curve.title} — ${curve.absent}`
                     : `${curve.title} — click to ${shows(hidden, curve.id) ? "hide" : "show"}`}
              >{curve.label}</button>
          {/each}
        </div>
        <!-- one press to the data and back again.  A `.segmented` of one would
             be a choice of one; this is an action, so it is a ghost button. -->
        <button class="ghost" class:on={dataOnly} onclick={showDataOnly}
          title={dataOnly
                 ? "put the other curves back"
                 : "hide every curve but the measured points"}>data only</button>
      {/if}
      <p class="hint muted tabular">
        {shown.n} of {shown.total} points drawn, {shown.lo.toFixed(3)}–{shown.hi.toFixed(3)}°
        · min/max decimated server-side · zoom refetches the window
      </p>
      <!-- The overlay has no toggle (its control is the candidate row), so this
           is where it says it is on screen — and where a thinned set admits it.
           A sample drawn without saying so would read as "these are the lines
           this cell predicts", which is the one claim the picture must not
           make falsely. -->
      {#if overlay}
        <p class="hint muted tabular candidate">
          {overlay.two_theta.length === overlay.n_total
            ? `${overlay.n_total} predicted lines`
            : `${overlay.two_theta.length} of ${overlay.n_total} predicted lines,
               sampled evenly — this cell predicts more than can be drawn`}
          · {overlay.label}
        </p>
      {/if}
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
      <button class="ghost" onclick={applyLimits} disabled={busy}
        title="send the typed range — project.doc.two_theta_limits">Set</button>
      <button class="ghost" onclick={() => onprotocol({ two_theta_limits: null })}
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
            <li>
              <span class="pill tabular"
                title="excluded from the residual">{formatRegion(region)}</span>
              <button class="ghost" disabled={busy}
                aria-label="stop excluding {formatRegion(region)}"
                title="fit these channels again"
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
        <p class="hint muted tabular count">
          {channels[0].toLocaleString()} of {channels[1].toLocaleString()} channels fitted
        </p>
      {/if}
      {#if held?.stale}
        <p class="hint warn">
          the curves shown were fitted over a different set of channels — re-run
        </p>
      {/if}
      {#if protocolError}
        <p class="hint bad">{protocolError}</p>
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

  /* …and the wash inside it, which `newselection` has no attribute for: plotly
     styles the outline's stroke from `layout.newselection.line` and writes
     `fill: rgb(0,0,0); fill-opacity: 0` **inline**, so the region being dragged
     over was outlined and not shaded — while the shape that lands a moment
     later is a wash. `!important` is what outranks an inline declaration, and
     it is the only thing that does; measured in Chrome, the rule without it
     computed to `fill-opacity: 0`. The token is `maskShapes`' own, so the
     gesture and the exclusion it leaves are one picture. `activeselection`
     above covers the *completed* selection, which this panel drops immediately
     (`clearSelection`), and neither attribute reaches the live one. */
  .plot :global(.select-outline) {
    fill: var(--plot-mask) !important;
    fill-opacity: 1 !important;
  }

  /* The readout strip (WP-1213).  Not a register: it is one panel's row of
     labelled numbers, and what keeps it from being a fourth kind of chip is
     that it has no box — the plot above it is the thing being annotated.

     The widths are the load-bearing part.  Mono digits make `ch` exact, so a
     `min-width` per field freezes the wrap points: the strip's height is then
     a function of the payload, the tab and the column width, and never of what
     the pointer happens to be over.  Without them a peak coming into reach
     rewrapped the row, which resizes the canvas — the jitter WP-1212 removed,
     arriving through its own repair. */
  .readout {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 2px 12px;
    padding: 4px 0 2px;
    font-size: var(--text-sm);
    color: var(--muted);
  }

  .readout .field {
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
  }

  /* a phase name is arbitrarily long, and it is the label of its own tick row
     — clip the label, not the strip (the curves toggle's rule, one row down) */
  .readout .key {
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .readout .val {
    color: var(--fg);
    min-width: 8ch;
  }

  /* the two fields that carry a sentence rather than a number: a picked line
     with its esd and relative intensity, and a candidate's hkl with its λ */
  .readout .field.wide .val {
    min-width: 22ch;
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

  .gestures strong {
    font-weight: 600;
    color: var(--fg);
  }

  /* The overlay's own line, in the overlay's own ink: it is the only thing in
     the knob row that names a layer nothing there can switch off, so it has to
     be attributable to the lines on the plot at a glance.  A whole row of its
     own because the point count above it is about the *data*. */
  .candidate {
    flex-basis: 100%;
    color: var(--plot-candidate);
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
    /* a strip of controls, so everything on it is control-sized — including
       the channel count, which is a readout on the strip rather than prose
       about it (it read a step larger than the fields it belongs to) */
    font-size: var(--text-sm);
  }

  .field {
    display: flex;
    align-items: center;
    gap: 5px;
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

  /* the readout and the verb that acts on it, side by side: a pill is
     non-interactive, so the × is a control of its own rather than one inside it */
  .regions li {
    display: flex;
    align-items: center;
    gap: var(--s1);
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
