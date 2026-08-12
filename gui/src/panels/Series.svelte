<script lang="ts">
  /**
   * An in-situ ramp or a parametric sweep, driven from the GUI — WP-1016's tab.
   *
   * A series is N *separate* refinements chained by a warm start, and this panel
   * is built around the one thing that makes that dangerous: a sequential fit is
   * path-dependent by construction, so **a smooth curve is exactly what a
   * poisoned chain produces** (WP-0505). Hence the shape of the panel. The
   * `direction="both"` verification pass has its own control and its answer —
   * `SEQUENTIAL_PATH_DEPENDENT` — is a banner at the top, not a diagnostic in a
   * strip; a flagged trajectory is *drawn* differently and has the other chain
   * drawn beside it, because the disagreement is the evidence.
   *
   * Two structural facts about where a series lives. Its patterns are staged
   * uploads and its answer is session-scoped (`ProjectDoc.patterns` stays length
   * 1), so there is nothing to save and nothing to reopen; and it inherits the
   * *project's* protocol — mode, plan, 2θ limits, excluded regions — which the
   * strip states rather than offering, because one protocol over N specimens is
   * what makes their trajectories comparable.
   *
   * The plot area is one plotly div with two views: a parameter's trajectory
   * across the series, or one pattern's own obs/calc/Δ. Selecting a pattern
   * switches it, which is what "the plot follows" means here.
   *
   * Every control sits *above* the plot, which is WP-1015's shape — but the
   * reason it gives does not apply here and the difference is worth knowing:
   * measured in a browser, these traces render as **SVG**, so the plot div holds
   * no canvas and cannot swallow a click beneath it (`Plot.svelte` draws its
   * residual with `scattergl`, and *that* is what makes one there). What the
   * `ResizeObserver` is for is the other half: this panel scrolls and the column
   * expands, and the plot has to refit its box — 539 → 1480 px when the column
   * takes the window.
   */
  import { onDestroy } from "svelte";

  import { api } from "../api";
  import { loadPlotly } from "../lib/plotly";
  import { coalesce, seriesCompact } from "../lib/resize";
  import { curveColors, hoverLabel } from "../lib/plot";
  import {
    asRequest,
    axisTitle,
    moveBy,
    rankTrajectories,
    reseededFlags,
    sortByX,
    trajectoryNote,
    trajectoryTraces,
    unrecoveredFlags,
    type SeriesEntry,
    type SeriesPattern,
    type SeriesSetup,
    type Trajectory,
  } from "../lib/series";
  import type { RunState } from "../lib/stream";

  let {
    project,
    run,
    busy,
    simple = true,
    active = false,
    theme = "light",
    say = () => {},
  }: {
    project: any;
    run: RunState | null;
    busy: boolean;
    simple?: boolean;
    /** this tab is showing — the panel stays mounted, so a staged list and a
     *  half-typed coordinate survive a look at the plot */
    active?: boolean;
    theme?: string;
    say?: (line: string) => void;
  } = $props();

  let setup = $state<SeriesSetup | null>(null);
  let answer = $state<any>(null);
  let failure = $state("");
  let staging = $state("");
  /** the list as this panel is editing it; `null` until the server has spoken */
  let patterns = $state<SeriesPattern[]>([]);
  let carryText = $state("*");
  let selectedPath = $state<string>("");
  /** which pattern the plot and the history list are showing, or `null` for the
   *  trajectory view */
  let selectedPattern = $state<number | null>(null);
  let memberHistory = $state<any>(null);
  let plotNode = $state<HTMLDivElement | undefined>();
  /** the panel's own width, for the table reflow below its measured floor */
  let panelWidth = $state(0);
  let loaded = false;
  const compact = $derived(seriesCompact(panelWidth));

  const entries = $derived<SeriesEntry[]>(answer?.result?.entries ?? []);
  const trajectories = $derived<Trajectory[]>(answer?.trajectories ?? []);
  const ranked = $derived(rankTrajectories(trajectories));
  const flagged = $derived<string[]>(answer?.path_dependent ?? []);
  const sigmaBar = $derived<number>(answer?.path_dependence_sigma ?? 3);
  const diagnostics = $derived<any[]>(answer?.result?.diagnostics ?? []);
  /** every fence except the headline one, which has its own banner */
  const otherDiagnostics = $derived(
    diagnostics.filter((d) => d.code !== "SEQUENTIAL_PATH_DEPENDENT"));
  const current = $derived<Trajectory | null>(
    trajectories.find((t) => t.path === selectedPath)
      ?? ranked[0] ?? null);
  const running = $derived(busy && run?.run?.kind === "series");
  const settings = $derived(setup?.settings ?? null);
  const canRun = $derived(!busy && patterns.length >= 2);

  // The panel is mounted from boot (every tab is), so it must not fetch until it
  // is looked at — and then only once, because the setup is session state nothing
  // else moves.  `hasProject` rather than `project`: an effect reading the object
  // refires on every ui-only PATCH (WP-1027's third browser finding).
  const hasProject = $derived(Boolean(project));
  $effect(() => {
    if (active && hasProject && !loaded) {
      loaded = true;
      load();
    }
  });

  /** A run just ended (the shell calls this): the answer is the whole outcome,
   *  and `load` fetches it off `has_result` — so this is one call, not two. */
  export async function reload() {
    await load();
  }

  async function load() {
    try {
      absorb(await api.series());
      failure = "";
      // The session outlives this page, and a series answer lives in the
      // session: a reload — or a first look at this tab after a run started from
      // the palette — must not lose it.  The shell does the same for the indexing
      // answer on boot, and `has_result` is what makes it one fetch rather than a
      // 409 every time.
      if (setup?.has_result) await loadAnswer();
    } catch (error) {
      setup = null;
      failure = (error as Error).message;
      loaded = false;   // a failed first fetch must not make the tab inert
    }
  }

  /** The server's list becomes this panel's, always — never merged.
   *
   * The `.rxt` pane's rule at a smaller scale: the answer to a PUT is the whole
   * setup, so a local list that disagreed with it would be a second authority on
   * what the series *is*, and the labels are exactly where that bites (the server
   * disambiguates repeats by position, so the name it will run under is not
   * always the one that was typed). */
  function absorb(next: SeriesSetup) {
    setup = next;
    patterns = [...next.patterns];
    carryText = next.settings.carry.join(" ");
  }

  async function loadAnswer() {
    try {
      answer = await api.seriesResult();
      if (!selectedPath && answer.trajectories?.length) {
        selectedPath = rankTrajectories(answer.trajectories)[0].path;
      }
      draw();
    } catch {
      // NO_SERIES_RESULT — nothing has run in this session; an empty state
      answer = null;
    }
  }

  /** Send the list and the settings as one PUT — the order *is* the series. */
  async function put(extra: Record<string, unknown> = {}) {
    failure = "";
    try {
      absorb(await api.putSeries({ patterns: asRequest(patterns), ...extra }));
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  /** Stage N files, then send the list once.  Sequential on purpose: each upload
   *  is read server-side, and the line it prints is per file, so a bad file names
   *  itself instead of failing a batch. */
  async function addFiles(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = "";   // the same file twice is a legitimate series member
    if (!files.length) return;
    failure = "";
    const added: SeriesPattern[] = [];
    for (const file of files) {
      staging = `reading ${file.name}…`;
      try {
        const preview = await api.uploadFile("pattern", file);
        added.push({
          upload: preview.upload, filename: preview.filename,
          label: preview.filename.replace(/\.[^.]+$/, ""), x: null,
          reader: preview.format.name,
          reader_options: preview.reader_options ?? {},
          n_points: preview.n_points,
          two_theta_range: preview.two_theta_range,
          has_sigma: preview.has_sigma,
        });
      } catch (error) {
        failure = (error as Error).message;
        break;
      }
    }
    staging = "";
    if (added.length) {
      patterns = [...patterns, ...added];
      await put();
      say(`# staged ${added.length} pattern(s) for the series`);
    }
  }

  const move = (index: number, delta: number) => {
    const next = moveBy(patterns, index, delta);
    if (next === patterns) return;   // nothing moved: no round trip
    patterns = next;
    put();
  };

  function remove(index: number) {
    patterns = patterns.filter((_, i) => i !== index);
    put();
  }

  function setX(index: number, text: string) {
    const value = text.trim() === "" ? null : Number(text);
    if (value !== null && !Number.isFinite(value)) {
      failure = `"${text}" is not a number`;
      return;
    }
    patterns = patterns.map((p, i) => (i === index ? { ...p, x: value } : p));
    put();
  }

  /** An emptied label is sent **empty**, not filled in here: the server's own
   *  rule is "blank means the file's stem", and a client that guessed would send
   *  `T300.xye` where the run uses `T300`. */
  function setLabel(index: number, text: string) {
    patterns = patterns.map((p, i) =>
      (i === index ? { ...p, label: text.trim() } : p));
    put();
  }

  const sort = () => { patterns = sortByX(patterns); put(); };

  const setSetting = (key: string, value: unknown) => put({ [key]: value });

  /** Read off the event target rather than a bound variable: every other field
   *  here does, and `bind:value` would make this depend on an `input` event
   *  having fired before the `change` — true when a human types and not when
   *  anything else sets the value. */
  function setCarry(text: string) {
    carryText = text;
    const globs = text.split(/\s+/).filter(Boolean);
    if (!globs.length) {
      failure = "carry needs at least one glob; ['*'] carries everything";
      return;
    }
    put({ carry: globs });
  }

  async function start() {
    failure = "";
    try {
      // no local run state: the state frame from the event stream is the one
      // truth about "is a run in flight" (App.svelte's founding rule)
      await api.runSeries();
      const x = setup?.has_x ? `x=[…], x_label=${JSON.stringify(settings?.x_label)}, ` : "";
      say(`refine_sequential(patterns, structure, instrument, ${x}`
          + `carry=${JSON.stringify(settings?.carry)}, `
          + `refit=${JSON.stringify(settings?.refit)}, `
          + `direction=${JSON.stringify(settings?.direction)})`);
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  /** Walk into one pattern: its own history tree, and the plot follows. */
  async function openPattern(index: number) {
    if (selectedPattern === index) {
      selectedPattern = null;
      memberHistory = null;
      draw();
      return;
    }
    selectedPattern = index;
    failure = "";
    try {
      memberHistory = await api.seriesHistory(index);
      say(`series.trees_[${index}]  # read-only: pinned to this pattern's `
          + `fingerprint, so its nodes cannot be checked out here`);
    } catch (error) {
      memberHistory = null;
      failure = (error as Error).message;
    }
    draw();
  }

  function showTrajectory(path: string) {
    selectedPath = path;
    selectedPattern = null;
    memberHistory = null;
    draw();
  }

  // -- the plot ------------------------------------------------------
  let observer: ResizeObserver | null = null;
  const resize = coalesce(() => {
    const plotly = (globalThis as any).Plotly;
    if (plotNode) return plotly?.Plots?.resize?.(plotNode);
  });

  onDestroy(() => observer?.disconnect());

  /** Repaint on the resolved theme: a canvas keeps the colours it was painted
   *  with, so a theme click has to redraw (WP-1029 q). */
  $effect(() => {
    void theme;
    void answer;
    if (active) draw();
  });

  async function draw() {
    if (!plotNode || !answer) return;
    const plotly = await loadPlotly();
    if (!plotNode) return;
    // sampled after the loader has awaited, which is what keeps this out of the
    // shell's `applyTheme` flush (WP-1027's second pass)
    const read = (name: string) =>
      getComputedStyle(document.documentElement).getPropertyValue(name);
    const colors = curveColors(read);
    const tones = {
      ok: colors.diff,
      warn: read("--warn").trim() || "#b7791f",
      muted: colors.edge,
    };
    const base = {
      margin: { l: 56, r: 12, t: 8, b: 40 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: read("--fg").trim() || "#1b1b1b", size: 11 },
      hoverlabel: hoverLabel(read),
      showlegend: true,
      legend: { orientation: "h", y: 1.12, x: 0, font: { size: 10 } },
      xaxis: { gridcolor: colors.zero, zeroline: false },
      yaxis: { gridcolor: colors.zero, zeroline: false },
    } as any;

    if (selectedPattern !== null) {
      let window: any;
      try {
        window = await api.seriesWindow(selectedPattern);
      } catch (error) {
        failure = (error as Error).message;
        return;
      }
      const traces = [
        { type: "scatter", mode: "markers", name: "obs", x: window.two_theta,
          y: window.y_obs, marker: { size: 2.5, color: colors.obs } },
        { type: "scatter", mode: "lines", name: "calc", x: window.two_theta,
          y: window.y_calc, line: { width: 1.1, color: colors.calc } },
        { type: "scatter", mode: "lines", name: "Δ/σ", x: window.two_theta,
          y: window.delta, line: { width: 0.7, color: colors.diff },
          yaxis: "y2" },
      ];
      if (window.excluded?.two_theta?.length) {
        traces.push({ type: "scatter", mode: "markers", name: "excluded",
                      x: window.excluded.two_theta, y: window.excluded.y_obs,
                      marker: { size: 2, color: colors.edge, opacity: 0.45 } } as any);
      }
      await plotly.react(plotNode, traces, {
        ...base,
        // anchored to the *lower* subplot, `Plot.svelte`'s rule: the default
        // anchor is the first y axis, which put the "2θ" title and its ticks
        // through the middle of the residual trace (measured in a browser)
        xaxis: { ...base.xaxis, domain: [0, 1], anchor: "y2",
                 title: { text: "2θ (deg)", font: { size: 10 } } },
        yaxis: { ...base.yaxis, domain: [0.34, 1], title: { text: "counts", font: { size: 10 } } },
        yaxis2: { ...base.yaxis, domain: [0, 0.28],
                  title: { text: window.weighted ? "Δ/σ" : "Δ/σ (Poisson)",
                           font: { size: 10 } } },
        uirevision: `series-pattern-${selectedPattern}`,
      }, { displayModeBar: false, responsive: true });
    } else {
      if (!current) return;
      const traces = trajectoryTraces(current, tones,
                                      reseededFlags(current, entries),
                                      unrecoveredFlags(current, entries));
      await plotly.react(plotNode, traces, {
        ...base,
        xaxis: { ...base.xaxis,
                 title: { text: current.x_label, font: { size: 10 } } },
        yaxis: { ...base.yaxis,
                 title: { text: axisTitle(current), font: { size: 10 } } },
        uirevision: `series-traj-${current.path}`,
      }, { displayModeBar: false, responsive: true });
    }
    if (!observer && plotNode) {
      observer = new ResizeObserver(() => resize());
      observer.observe(plotNode);
    }
  }
</script>

<section bind:clientWidth={panelWidth}>
  <!-- the headline, not a footnote: the one check that separates a measured
       trajectory from an ordering artefact (WP-0505) -->
  {#if flagged.length}
    <p class="banner bad">
      <strong>{flagged.length} parameter{flagged.length === 1 ? "" : "s"}
        path-dependent</strong> — the forward and backward chains disagree by more
      than {sigmaBar}σ, so {flagged.length === 1 ? "its" : "their"} trajector{flagged.length === 1 ? "y is" : "ies are"}
      an artefact of the order the series was refined in, not a measurement.
      {#each flagged.slice(0, 6) as path (path)}
        <button class="chip warn" onclick={() => showTrajectory(path)}
          title="show this trajectory with the backward chain beside it">{path}</button>
      {/each}
      {#if flagged.length > 6}<span class="muted">+{flagged.length - 6}</span>{/if}
    </p>
  {:else if answer?.has_backward}
    <p class="banner ok">
      Both chain directions agree within their esds — the trajectories below are
      measurements rather than ordering artefacts.
    </p>
  {/if}

  {#if failure}<p class="bad small">{failure}</p>{/if}

  <h2>Patterns</h2>
  {#if setup}
    <p class="muted small">
      A series is N separate refinements chained by a warm start — one history
      tree each, not one joint residual. It runs under <em>this project's</em>
      protocol ({setup.protocol.mode}{#if setup.protocol.plan}, {setup.protocol.plan}{/if},
      {setup.protocol.n_stages} stage{setup.protocol.n_stages === 1 ? "" : "s"})
      and warm-starts from its current model.
    </p>
  {/if}

  <div class="controls">
    <label class="file">
      <input type="file" multiple disabled={busy}
        onchange={addFiles} />
      <span>Add patterns…</span>
    </label>
    {#if patterns.some((p) => p.x !== null)}
      <button class="ghost" onclick={sort} disabled={busy}
        title="order the series by its coordinate — patterns with none keep their places at the end"
        >Sort by {settings?.x_label ?? "x"}</button>
    {/if}
    {#if staging}<span class="muted small">{staging}</span>{/if}
  </div>

  {#if setup?.sigma_mixed}
    <p class="small warn" title="the fit weights by the file's esd column when it
has one and by the Poisson √max(y,1) fallback otherwise, so a mixed series is
fitted under two weighting policies — a correctness property that is invisible
once the files are read">
      ⚠ these files disagree about carrying esds: part of this series will be
      weighted by measured σ and part by the Poisson fallback.
    </p>
  {/if}

  {#if !patterns.length}
    <p class="muted note">
      No patterns staged. <strong>Add patterns…</strong> takes the ramp's files in
      one go; give each a coordinate (temperature, time, pressure) or leave them
      blank and the pattern index is the axis.
    </p>
  {:else}
    <!-- Below its measured floor the table drops the four descriptive columns
         (`lib/resize.ts:seriesCompact`) rather than side-scrolling: the reorder
         buttons are the last column and the panel's main verb, so scrolling put
         them off the right edge of a box a user then had to scroll to reorder a
         series. Nothing is lost — the four move into the label's tooltip. -->
    <div class="scroll">
      <table class="tabular">
        <thead>
          <tr>
            <th>#</th><th>label</th>
            <th title="the series coordinate — blank means the index is the axis"
              >{settings?.x_label ?? "x"}</th>
            {#if !compact}
              <th>file</th><th>pts</th><th>2θ</th><th>σ</th>
            {/if}
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each patterns as p, i (p.upload + i)}
            {@const detail = `${p.filename} · read as ${p.reader} · ${p.n_points} points`
              + ` · 2θ ${p.two_theta_range[0].toFixed(1)}–${p.two_theta_range[1].toFixed(1)}°`
              + ` · σ ${p.has_sigma ? "from file" : "Poisson fallback"}`}
            <tr>
              <td class="muted">{i}</td>
              <td title={detail}>
                <input class="label" type="text" value={p.label} disabled={busy}
                  onchange={(ev) => setLabel(i, (ev.currentTarget as HTMLInputElement).value)} />
              </td>
              <td>
                <input class="x" type="text" inputmode="decimal"
                  value={p.x === null ? "" : p.x} disabled={busy}
                  onchange={(ev) => setX(i, (ev.currentTarget as HTMLInputElement).value)} />
              </td>
              {#if !compact}
                <td class="muted" title={detail}>{p.filename}</td>
                <td>{p.n_points}</td>
                <td class="muted">{p.two_theta_range[0].toFixed(1)}–{p.two_theta_range[1].toFixed(1)}°</td>
                <td>{p.has_sigma ? "file" : "Poisson"}</td>
              {/if}
              <td class="acts">
                <button class="ghost tiny" disabled={busy || i === 0}
                  title="earlier in the series" onclick={() => move(i, -1)}>↑</button>
                <button class="ghost tiny" disabled={busy || i === patterns.length - 1}
                  title="later in the series" onclick={() => move(i, 1)}>↓</button>
                <button class="ghost tiny" disabled={busy}
                  title="remove from the series" onclick={() => remove(i)}>×</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  <h2>The chain</h2>
  <div class="controls">
    <label class="field" title="the chain direction. `both` runs the series each
way and reports every parameter the two directions disagree on — the only check
that separates a measured trajectory from an ordering artefact, and it costs a
second pass">
      direction
      <select value={settings?.direction ?? "forward"} disabled={busy}
        onchange={(ev) => setSetting("direction", (ev.currentTarget as HTMLSelectElement).value)}>
        {#each setup?.choices.direction ?? [] as choice (choice)}
          <option value={choice}>{choice}</option>
        {/each}
      </select>
    </label>
    <button onclick={start} disabled={!canRun}
      title={patterns.length < 2
        ? "a series needs at least two patterns; one pattern is a fit"
        : "run the chain: each pattern warm-started from its predecessor"}>
      {answer ? "Re-run series" : "Run series"}
    </button>
    {#if running}
      <span class="muted small">
        {run?.run.stage ?? "starting"}
        {#if run?.run.stage_index}({run.run.stage_index}/{run.run.n_stages}){/if}
      </span>
    {/if}
  </div>

  {#if !simple}
    <!-- Advanced, because both are measured results rather than preferences
         (WP-0505) and re-litigating them in the UI would invite a worse default. -->
    <div class="controls advanced">
      <label class="field" title="`single` (the default) collapses the plan into
one stage per pattern once a converged neighbour is the starting point: measured
at 904 iterations against 1623 for re-walking the staged plan, with the QPA error
identical to three decimals. `stages` re-walks it.">
        refit
        <select value={settings?.refit ?? "single"} disabled={busy}
          onchange={(ev) => setSetting("refit", (ev.currentTarget as HTMLSelectElement).value)}>
          {#each setup?.choices.refit ?? [] as choice (choice)}
            <option value={choice}>{choice}</option>
          {/each}
        </select>
      </label>
      <label class="field" title={setup?.carry_help ?? ""}>
        carry
        <input class="carry" type="text" value={carryText} disabled={busy}
          onchange={(ev) => setCarry((ev.currentTarget as HTMLInputElement).value)}
          placeholder="*" />
      </label>
      <label class="field" title="what the series coordinate is called — the
plot's x-axis title, and the column above">
        x label
        <input class="xlabel" type="text" value={settings?.x_label ?? "index"}
          disabled={busy}
          onchange={(ev) => setSetting("x_label", (ev.currentTarget as HTMLInputElement).value)} />
      </label>
    </div>
    <p class="muted small">{setup?.carry_help ?? ""}</p>
  {/if}

  {#if answer}
    <h2>
      {selectedPattern === null
        ? `Trajectory — ${current?.path ?? ""}`
        : `Pattern ${selectedPattern} — ${entries[selectedPattern]?.label ?? ""}`}
    </h2>
    <!-- every control above the plot: plotly's `responsive` listens for *window*
         resizes only, so a control row underneath keeps an oversized canvas over
         it and its clicks are swallowed (WP-1015's measured trap) -->
    <div class="controls">
      <select value={current?.path ?? ""} disabled={busy}
        onchange={(ev) => showTrajectory((ev.currentTarget as HTMLSelectElement).value)}>
        {#each ranked as t (t.path)}
          <option value={t.path}>
            {t.path_dependent ? "⚠ " : t.discontinuous ? "↕ " : ""}{t.path}
            {#if t.n_sigma !== null && t.path_dependent}({t.n_sigma.toFixed(1)}σ){/if}
          </option>
        {/each}
      </select>
      {#if selectedPattern !== null}
        <button class="ghost" onclick={() => showTrajectory(current?.path ?? "")}
          title="back to the trajectory across the series">Show trajectory</button>
      {/if}
    </div>
    {#if selectedPattern === null && current}
      <p class="small" class:warn={current.path_dependent}>
        {trajectoryNote(current, sigmaBar)}
      </p>
    {/if}
    <div class="plot" bind:this={plotNode}></div>

    <h2>Per pattern</h2>
    <div class="scroll">
      <table class="tabular">
        <thead>
          <tr>
            <th>#</th><th>label</th><th>{answer.result.x_label}</th>
            <th>status</th><th>Rwp</th>
            <!-- the same floor as the staged table one section up, and GoF is
                 what goes: Rwp is the headline and this column was the 6 px that
                 put the drill-down button off the right edge (measured) -->
            {#if !compact}<th>GoF</th>{/if}
            <th title="least-squares iterations over every attempt on this pattern,
every rung of the escalation ladder included — what the warm start actually buys">iter</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each entries as e, i (e.index)}
            <tr class:lit={selectedPattern === i} class:out={e.status === "diverged"}>
              <td class="muted">{e.index}</td>
              <td>{e.label}</td>
              <td>{e.x === null ? e.index : e.x}</td>
              <td>
                {e.status}
                {#if e.status === "diverged"}
                  <span class="chip warn" title="no rung of the escalation ladder
recovered this pattern (tried: {e.rungs_tried.join(" → ")}). It is reported because it
was measured, but the chain stepped over it: it seeded no successor and its Rwp was
left out of the series median. Read it as a failed fit, not as a datum.">unrecovered</span>
                {:else if e.reseeded}
                  <span class="chip warn" title="the warm start was rejected (it
reached Rwp {((e.rwp_warm ?? 0) * 100).toFixed(2)}%) and this pattern was refitted from the
initial model. A good fit — but its starting values did not come from its
neighbour, so it is not evidence that the trajectory is continuous here.">reseeded</span>
                {:else if e.rung === "warm_staged"}
                  <span class="chip" title="the quick warm refit was rejected (it
reached Rwp {((e.rwp_warm ?? 0) * 100).toFixed(2)}%) and the full staged plan recovered
it — still starting from the neighbour's answer, so the chain is unbroken
here">restaged</span>
                {:else if e.rwp_warm !== null}
                  <span class="chip warn" title="the reseed guard fired and no restart
rescued it (tried: {e.rungs_tried.join(" → ")}): this pattern was hard for a reason a
different starting point could not fix">hard</span>
                {/if}
              </td>
              <td title={e.statistics ? `GoF ${e.statistics.gof.toFixed(3)}` : ""}>
                {e.statistics ? (e.statistics.rwp * 100).toFixed(2) + "%" : "—"}</td>
              {#if !compact}
                <td>{e.statistics ? e.statistics.gof.toFixed(3) : "—"}</td>
              {/if}
              <td>{e.n_iterations}</td>
              <td>
                <button class="ghost tiny" disabled={busy || !answer.curves[i]}
                  title="this pattern's own fit and its own history tree"
                  onclick={() => openPattern(i)}>
                  {selectedPattern === i ? "▾" : "▸"}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="muted small tabular">
      {answer.n_iterations} iterations over the whole series
      {#if answer.has_backward}· plus a backward verification pass{/if}
    </p>

    {#if memberHistory}
      <h2>History — {memberHistory.label}</h2>
      <p class="muted small">
        One tree per pattern, pinned to that pattern by its data fingerprint — so
        these nodes are <strong>read-only here</strong>: checking one out would
        restore a state fitted against different data. The chain itself is
        recorded on the root node's notes.
      </p>
      <ul class="nodes">
        {#each memberHistory.nodes as node (node.id)}
          <li>
            <span class="mono">{node.id}</span>
            <span class="kind">{node.kind}{node.name ? ` ${node.name}` : ""}</span>
            {#if node.rwp !== null}
              <span class="tabular">Rwp {(node.rwp * 100).toFixed(2)}%</span>
            {/if}
            {#if node.n_iterations}<span class="muted">{node.n_iterations} iter</span>{/if}
            {#if node.notes?.series_warm_start_node}
              <span class="muted mono" title="the node this pattern's starting values came from">
                ← {node.notes.series_warm_start_node}
              </span>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

    {#if otherDiagnostics.length}
      <h2>Fences</h2>
      <ul class="strip">
        {#each otherDiagnostics as d (d.code + d.message)}
          <li class={d.level}>
            <span class="mono">{d.code}</span> {d.message}
            {#if d.suggestion}<span class="muted"> — {d.suggestion}</span>{/if}
          </li>
        {/each}
      </ul>
    {/if}
  {:else if patterns.length >= 2}
    <p class="muted note">
      Nothing has run yet. <strong>Run series</strong> chains the patterns above,
      each warm-started from its predecessor; with <code>direction=both</code> it
      runs the chain each way and reports every parameter the two disagree on.
    </p>
  {/if}
</section>

<style>
  section {
    padding: 8px 10px;
    overflow: auto;
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  h2 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin: 8px 0 2px;
    font-weight: 600;
  }

  .controls {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    flex: 0 0 auto;
  }

  .field {
    display: flex;
    gap: 4px;
    align-items: center;
    font-size: 11.5px;
    color: var(--muted);
  }

  /* the native file input is unstylable and says "no file chosen"; the label is
     the button and the input is the mechanism */
  .file input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
  }

  .file {
    position: relative;
    display: inline-flex;
  }

  .file span {
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 3px 9px;
    cursor: pointer;
    background: var(--panel);
  }

  .file span:hover {
    background: color-mix(in srgb, var(--accent) 10%, transparent);
  }

  .banner {
    margin: 2px 0;
    padding: 5px 8px;
    border: 1px solid var(--line);
    border-left-width: 3px;
    border-radius: 3px;
    font-size: 12px;
    flex: 0 0 auto;
  }

  .banner.bad {
    border-left-color: var(--warn);
    color: var(--fg);
  }

  .banner.ok {
    border-left-color: var(--ok);
    color: var(--muted);
  }

  /* Bounded like the peak panel's tables and for the same measured reason: as
     unbounded flex children two stacked tables shrink each other, and the plot
     between them collapses to nothing. */
  .scroll {
    overflow: auto;
    flex: 0 0 auto;
    max-height: 34vh;
  }

  table {
    border-collapse: collapse;
    font-size: 12px;
    width: 100%;
  }

  th {
    text-align: left;
    font-weight: 600;
    color: var(--muted);
    padding: 2px 6px;
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--panel);
  }

  td {
    padding: 1px 6px;
    border-top: 1px solid var(--line);
    white-space: nowrap;
    vertical-align: middle;
  }

  tr.out td {
    opacity: 0.55;
  }

  tr.lit td {
    background: color-mix(in srgb, var(--accent) 14%, transparent);
  }

  .acts {
    display: flex;
    gap: 2px;
    align-items: center;
  }

  input.x, input.xlabel {
    width: 62px;
    font: var(--mono);
  }

  input.label {
    width: 92px;
  }

  input.carry {
    width: 150px;
    font: var(--mono);
  }

  /* a fixed height, not a share: the panel scrolls, so a flex-sized plot would
     be whatever was left over after two tables — which on a short window is
     nothing */
  .plot {
    height: 260px;
    flex: 0 0 auto;
    min-height: 0;
  }

  .nodes, .strip {
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: 11px;
    flex: 0 0 auto;
  }

  .nodes li {
    display: flex;
    gap: 8px;
    padding: 1px 0;
    border-top: 1px solid var(--line);
  }

  .nodes .kind {
    color: var(--accent);
  }

  .strip li {
    padding: 1px 0;
    color: var(--muted);
  }

  .strip li.warning { color: var(--warn); }
  .strip li.error { color: var(--bad); }

  .chip {
    font-size: 10px;
    padding: 0 5px;
    border-radius: 7px;
    border: 1px solid var(--line);
    color: var(--muted);
    white-space: nowrap;
  }

  button.chip.warn {
    color: var(--warn);
    border-color: var(--warn);
    background: none;
    cursor: pointer;
  }

  .chip.warn { color: var(--warn); border-color: var(--warn); }

  .small { font-size: 11.5px; margin: 2px 0; }
  .note { margin: 4px 0; font-size: 12px; }
  .bad { color: var(--bad); }
  .warn { color: var(--warn); }
</style>
