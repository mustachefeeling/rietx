<script lang="ts">
  /**
   * The shell: one header of run controls and statistics, the plot, the panels.
   *
   * State lives in runes here and is passed down; there is no store library
   * because there is one session and one project, and a second source of truth
   * for "is a run in flight" is exactly the bug the server's 409 exists to
   * prevent. The `state` frame from the event stream is that truth — every
   * control's disabled attribute derives from it rather than from what the last
   * click hoped.
   *
   * Two things landed here in WP-1011 rather than in a panel.  The **command
   * palette** is the shell's, because its entries are every verb the app has and
   * each one echoes the Python call it makes — the palette is the API's index,
   * not a menu.  And **Simple/Advanced** is one flag persisted to
   * `ProjectDoc.ui`, whose keys the frontend owns (WP-1005): it is a property of
   * the project a user comes back to, not of this browser tab.
   */
  import { onMount } from "svelte";

  import { ApiError, api } from "./api";
  import Console from "./panels/Console.svelte";
  import History from "./panels/History.svelte";
  import Model from "./panels/Model.svelte";
  import Palette from "./panels/Palette.svelte";
  import Params from "./panels/Params.svelte";
  import Peaks from "./panels/Peaks.svelte";
  import Plan from "./panels/Plan.svelte";
  import Plot from "./panels/Plot.svelte";
  import Report from "./panels/Report.svelte";
  import Splitter from "./panels/Splitter.svelte";
  import Stubs from "./panels/Stubs.svelte";
  import Text from "./panels/Text.svelte";
  import { isShortcutTarget, type Command } from "./lib/palette";
  import type { PeaksPayload } from "./lib/peaks";
  import { consoleLine, follow, type EngineEvent, type RunState } from "./lib/stream";
  import {
    THEME_CHOICES,
    applyTheme,
    readChoice,
    resolveTheme,
    type Theme,
    type ThemeChoice,
  } from "./lib/theme";

  let version = $state<any>(null);
  let capabilities = $state<any>(null);
  let project = $state<any>(null);
  let recent = $state<any[]>([]);
  let openError = $state<string>("");

  let run = $state<RunState | null>(null);
  let result = $state<any>(null);
  let resultError = $state<string>("");
  let lines = $state<string[]>([]);
  let dropped = $state(0);
  let plotKey = $state(0);

  let tab = $state<"params" | "plan" | "peaks" | "history" | "report" | "build">("params");
  /** Two panes are **modes** over the whole window rather than tabs.
   *
   *  The text pane (WP-1013) is one because its content is line-oriented — the
   *  `.pxt` columns are aligned so a rectangular selection can hit one field,
   *  which a 340–560 px sidebar undoes.  The model pane (WP-1014) is one for two
   *  reasons: an atom table is eight columns wide, and it is the only pane that
   *  must work with **no project open at all**, which no tab can. */
  let mode = $state<"panes" | "text" | "model">("panes");
  const textMode = $derived(mode === "text");
  const modelMode = $derived(mode === "model");

  /** One control for one choice (WP-1029).
   *
   * There used to be two toggle buttons in the header plus a `Close` inside each
   * pane — two different controls for the same choice, and no button named for
   * where a click lands you.  A segmented three is the choice itself: the
   * options *are* the control, "where am I" and "where can I go" are one
   * reading, and Plot has a name rather than being the absence of the other two.
   * This is not a re-litigation of WP-1013: Model and Text remain **modes over
   * the whole window** rather than a sixth tab, and the five-wide strip below
   * stays what it is — the sidebar's tabs *within* the plot mode. */
  const MODES: { id: "panes" | "model" | "text"; label: string; title: string }[] = [
    { id: "panes", label: "Plot", title: "the pattern, the panels and the console" },
    { id: "model", label: "Model", title: "atoms, site-symmetry DOFs and the instrument" },
    { id: "text", label: "Text", title: "the whole project as one editable document" },
  ];

  function toggleMode(which: "text" | "model") {
    mode = mode === which ? "panes" : which;
  }
  let simple = $state(true);
  let consoleHeight = $state(150);
  /** The panel column's width in px, or `null` for "nobody has said".
   *
   * `null` is not laziness: while it holds, the CSS `clamp(340px, 38%, 560px)`
   * supplies the width, so a fresh project is responsive rather than frozen at
   * whatever the first window this project was ever opened in happened to be.
   * The first drag replaces it with a number, which is the user having said. */
  let sideWidth = $state<number | null>(null);
  let sideMeasured = $state(0);
  /** The Model pane's first two column widths; its third takes the rest. */
  let modelColumns = $state<number[] | null>(null);
  let mainEl: HTMLElement | undefined = $state();

  /** The theme *choice* — three-way, because "follow the system" is a decision
   *  and not the absence of one (lib/theme.ts). */
  let themeChoice = $state<ThemeChoice>("system");
  let systemDark = $state(false);
  const theme = $derived<Theme>(resolveTheme(themeChoice, systemDark));
  const GLYPH: Record<ThemeChoice, string> = { system: "◐", light: "☀", dark: "☾" };
  const THEME_TITLE: Record<ThemeChoice, string> = {
    system: "follow the system, and keep following it when it changes",
    light: "light, whatever the system does",
    dark: "dark, whatever the system does",
  };

  // one authority on the resolved theme, stamped where CSS and CodeMirror both
  // read it — no component derives it a second time from `matchMedia`
  $effect(() => applyTheme(theme, document.documentElement));
  let paletteOpen = $state(false);
  let paramsPanel = $state<any>(null);
  let planPanel = $state<any>(null);
  let modelPanel = $state<any>(null);
  /** a 2θ window the report panel asked the plot to show, or null for all of it */
  let zoom = $state<[number, number] | null>(null);
  /** the last applied suggestion, until it is undone — carries the node to check
   *  out and the χ² it was applied at, which is what makes the *observed* Δχ²
   *  measurable beside the predicted one */
  let applied = $state<any>(null);
  /** the stored peak list plus the raw pattern (WP-1027); the plot draws it and
   *  the Peaks tab is its ledger, so the state lives here, once */
  let peaksData = $state<PeaksPayload | null>(null);
  /** the last indexing answer, with the server's per-candidate adopt verdicts */
  let indexAnswer = $state<any>(null);
  /** the last extinction screen — cleared whenever the candidates renumber,
   *  which the server enforces too (a new index run 409s the stale GET) */
  let extinction = $state<any>(null);
  /** the peak the pointer is over, wherever it is over it (WP-1032).  One index
   *  here rather than one per panel, because "which line is this" is a question
   *  about the session, and two copies would be two answers. */
  let hoveredPeak = $state<number | null>(null);
  /** the last refusal from a settings patch, in the verb's own words — held
   *  beside the boxes that caused it rather than scrolled away in the console */
  let protocolError = $state("");

  /** What is being fitted (WP-1033), rebuilt from the document on every change.
   *  A *derived* object rather than plot state: `project.json` is the authority,
   *  and the plot is drawing it, not holding an opinion about it. */
  const protocol = $derived({
    limits: (project?.doc?.two_theta_limits ?? null) as [number, number] | null,
    regions: (project?.doc?.excluded_regions ?? []) as [number, number][],
  });
  const extent = $derived((project?.data?.two_theta_range ?? null) as [number, number] | null);
  const channels = $derived(project
    ? ([project.data.n_fitted ?? project.data.n_points,
        project.data.n_points] as [number, number])
    : null);

  const busy = $derived(run?.state !== "idle");
  const rwp = $derived(result?.statistics?.rwp ?? run?.run?.rwp ?? null);
  const gof = $derived(result?.statistics?.gof ?? run?.run?.gof ?? null);
  /** The report's own maturity gate, quoted rather than re-derived — see the
   *  header below and `GuiSession.result`. */
  const immature = $derived(Boolean(result?.maturity?.immature));
  // the head is the working state (WP-1005), so it is the one signal that says
  // "the table moved" whether a run, a checkout or an edit moved it
  const head = $derived(run?.head ?? project?.head ?? null);

  function say(line: string) {
    lines = [...lines.slice(-400), line];
  }

  /** The `ui` keys this frontend owns, read back off the document it saved them
   *  to — one place, so a new key cannot be persisted and then never restored. */
  function readUi() {
    simple = project?.doc?.ui?.simple ?? true;
    consoleHeight = project?.doc?.ui?.console_height ?? 150;
    sideWidth = project?.doc?.ui?.side_width ?? null;
    modelColumns = project?.doc?.ui?.model_columns ?? null;
    themeChoice = readChoice(project?.doc?.ui?.theme);
  }

  /** Persist a `ui` key on the verb, not on a later save (WP-1005/1008). */
  async function setUi(patch: Record<string, unknown>) {
    if (!project) return;
    try {
      project = await api.patchProject({ ui: patch });
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
  }

  /** What is fitted, from the plot (WP-1033) — the same route `ui` takes, and
   *  the reason `api.patchProject` stops being a `{ui: …}`-only call site.
   *
   *  It goes through the shell rather than the panel for the reason every peak
   *  verb does: the Plot stays presentation, and the console echo of the Python
   *  call belongs beside every other one.  The refusal is *held* rather than
   *  toasted, because it is about a value still on screen in a box — the user
   *  needs it while they retype. */
  async function setProtocol(patch: Record<string, unknown>) {
    if (!project) return;
    try {
      project = await api.patchProject(patch);
      protocolError = "";
      if ("two_theta_limits" in patch) {
        const limits = patch.two_theta_limits as number[] | null;
        say(`project.doc.two_theta_limits = ${limits ? `(${limits.join(", ")})` : "None"}`);
      }
      if ("excluded_regions" in patch) {
        const regions = patch.excluded_regions as number[][];
        say(`project.set_excluded_regions(${JSON.stringify(regions)})`);
      }
      // the peak plot's raw pattern is masked by the same document, so its
      // payload is stale the moment this lands (`GuiSession._peaks_pattern`)
      if (peaksData) await loadPeaks();
    } catch (error) {
      protocolError = (error as Error).message;
      say(`refused: ${(error as Error).message}`);
    }
  }

  async function loadProject() {
    try {
      project = await api.project();
      readUi();
      openError = "";
    } catch (error) {
      project = null;
      if (error instanceof ApiError && error.code === "NO_PROJECT") {
        recent = (await api.recent()).recent ?? [];
      } else {
        openError = (error as Error).message;
      }
    }
  }

  async function loadResult() {
    try {
      result = (await api.result()).result;
      resultError = "";
      plotKey += 1; // the curves moved: tell the plot to refetch its window
    } catch (error) {
      result = null;
      // NO_RESULT is an empty state, not a failure: a fresh project has no
      // curves, and a `checkout` throws the last fit's away on purpose.
      resultError = error instanceof ApiError && error.empty ? "" : (error as Error).message;
    }
  }

  /** The import wizard created one: adopt it without a reload (WP-1014).
   *
   * `project_new` answers with the same document `GET /api/project` would, so
   * there is nothing to refetch — and the panels below all key off `head`, which
   * the new project's root node supplies.
   */
  async function opened(doc: any) {
    project = doc;
    readUi();
    openError = "";
    mode = "panes";
    indexAnswer = null;
    extinction = null;
    say(`# project: ${doc.path}`);
    run = await api.runState();
    await loadResult();
    await loadPeaks();
  }

  async function open(path: string) {
    try {
      project = await api.openProject(path);
      readUi();
      openError = "";
      indexAnswer = null;
      extinction = null;
      await loadResult();
      await loadPeaks();
      say(`project.open(${path})`);
    } catch (error) {
      // every Project.open refusal names a different remedy — show it verbatim
      openError = (error as Error).message;
    }
  }

  async function start() {
    try {
      run = await api.run({ kind: "fit" });
      say("ref.fit(data, plan=…)");
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
  }

  async function runStage(stage: any) {
    try {
      run = await api.run({ kind: "stage", stage });
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
  }

  async function cancel() {
    try {
      run = await api.cancel();
      say("token.cancel()");
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
  }

  /** The peak list, refetched whole — cheap, and the payload every peak verb
   *  already answers with, so a verb's caller passes it here instead. */
  async function loadPeaks() {
    try {
      peaksData = await api.peaks();
    } catch (error) {
      peaksData = null;
      if (!(error instanceof ApiError && error.empty)) {
        say(`peaks: ${(error as Error).message}`);
      }
    }
  }

  /** One plot gesture → one verb → one console echo — the same round trip the
   *  panel's own buttons make, kept here so the Plot stays presentation. */
  async function peakVerb(work: () => Promise<PeaksPayload>) {
    try {
      const payload = await work();
      if (payload.api_call) say(payload.api_call);
      peaksData = payload;
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
  }

  const addPeak = (tt: number) => peakVerb(() => api.addPeak(tt));
  const movePeak = (i: number, tt: number) => peakVerb(() => api.movePeak(i, tt));
  const togglePeak = (i: number) => {
    const row = peaksData?.peaks?.find((p) => p.index === i);
    if (row) peakVerb(() => api.flagPeak(i, { use_for_indexing: !row.usable }));
  };
  /** Right-click on a marker removes it (WP-1032).  Refit stays on the Peaks
   *  table's `↻`, and the `window.prompt` for a component count went with it:
   *  a modal on the one pointer gesture with no undo, for a verb another
   *  control already carried. */
  const removePeak = (index: number) => peakVerb(() => api.removePeak(index));

  async function loadIndexAnswer() {
    try {
      indexAnswer = await api.indexResult();
      extinction = null; // new candidates, new numbering — the server 409s too
    } catch {
      // NO_INDEX_RESULT — nothing has run in this session; an empty state
    }
  }

  async function loadExtinction() {
    try {
      extinction = await api.extinctionResult();
    } catch {
      // NO_EXTINCTION_RESULT — none run, or cleared by a new indexing run
      extinction = null;
    }
  }

  /** A panel moved the head without running: refetch the result.
   *
   * Needed because a `checkout` **discards the fitted curves** server-side — they
   * described the values it just replaced — and the shell otherwise keeps showing
   * a plot of a state the project is no longer in.  Not an `$effect` on `head`: a
   * `set_vary` moves the head too and keeps the result, and refetching there would
   * throw away the plot's zoom on every parameter edit.
   */
  async function moved() {
    zoom = null;
    await loadResult();
  }

  /** `POST /api/report/apply` came back: a stage is running for a suggestion. */
  function absorbApply(payload: any) {
    if (payload === null) {
      applied = null;
      return;
    }
    run = payload;
    applied = {
      kind: payload.applied.kind,
      chi2_before: payload.chi2_before,
      predicted: payload.applied.expected_delta_chi2,
      undo: payload.undo,
    };
    say(payload.api_call);
  }

  async function setSimple(next: boolean) {
    simple = next;
    await setUi({ simple: next });
    say(`project.doc.ui["simple"] = ${next ? "True" : "False"}`);
  }

  async function setConsoleHeight(next: number) {
    consoleHeight = next;
    await setUi({ console_height: next });
  }

  function nextTheme(): ThemeChoice {
    return THEME_CHOICES[(THEME_CHOICES.indexOf(themeChoice) + 1) % THEME_CHOICES.length];
  }

  async function setTheme(next: ThemeChoice) {
    themeChoice = next;
    await setUi({ theme: next });
    say(`project.doc.ui["theme"] = ${JSON.stringify(next)}`);
  }

  /** Every splitter reports live and persists once — `done` is the round trip. */
  function sideSized(next: number, done: boolean) {
    sideWidth = next;
    if (done) setUi({ side_width: next });
  }

  function modelSized(next: number[], done: boolean) {
    modelColumns = next;
    if (done) setUi({ model_columns: next });
  }

  const commands = $derived<Command[]>([
    { id: "run", label: "Run the fit", echo: "ref.fit(data, plan=…)", key: "r",
      disabled: busy || !project, run: start },
    { id: "stage", label: `Run one stage${planPanel?.selectedName() ? ` — ${planPanel.selectedName()}` : ""}`,
      echo: "ref.run_stage(stage)", key: ".", disabled: busy || !project,
      run: () => { tab = "plan"; planPanel?.runStage(); } },
    { id: "cancel", label: "Cancel the run", echo: "token.cancel()", key: "Esc",
      disabled: !busy, run: cancel },
    { id: "free", label: "Free the filtered parameters", echo: 'ref.set_vary(glob, True)',
      key: "f", disabled: busy || !project,
      run: () => { tab = "params"; paramsPanel?.freeSelection(); } },
    { id: "fix", label: "Fix the filtered parameters", echo: 'ref.set_vary(glob, False)',
      key: "x", disabled: busy || !project,
      run: () => { tab = "params"; paramsPanel?.fixSelection(); } },
    { id: "filter", label: "Filter parameters", echo: "ref.parameters()", key: "/",
      disabled: !project, run: () => { tab = "params"; setTimeout(() => paramsPanel?.focusFilter(), 0); } },
    { id: "peaks", label: "Show the peak picker", echo: "session.pick_peaks()", key: "p",
      disabled: !project, run: () => (tab = "peaks") },
    { id: "index", label: "Run indexing", echo: "index_pattern(peaks, data=…, instrument=…)",
      disabled: busy || !project || !peaksData?.peaks?.length,
      run: async () => { tab = "peaks"; try { await api.index(); say("index_pattern(peaks, data=…, instrument=…)"); } catch (e) { say(`refused: ${(e as Error).message}`); } } },
    { id: "report", label: "Show the fit report", echo: "ref.report()", key: "?",
      disabled: !project, run: () => (tab = "report") },
    { id: "history", label: "Show the history", echo: "ref.history.summary()", key: "h",
      disabled: !project, run: () => (tab = "history") },
    { id: "text", label: textMode ? "Leave the text document" : "Edit the project as text",
      echo: "print(pxrdref.gui.textdoc.render(project))", key: "t", disabled: !project,
      run: () => toggleMode("text") },
    { id: "model", label: modelMode ? "Leave the model editor" : "Edit the structure and instrument",
      echo: "ref.edit(structure=…, instrument=…)", key: "m", disabled: !project,
      run: () => toggleMode("model") },
    { id: "import", label: "Import a new project", echo: "Project.create(path, …)",
      run: () => { mode = "model"; modelPanel?.startImport(); } },
    { id: "disclosure", label: simple ? "Show advanced controls" : "Hide advanced controls",
      echo: 'project.doc.ui["simple"]', disabled: !project, run: () => setSimple(!simple) },
    { id: "theme", label: `Theme: ${themeChoice} — switch to ${nextTheme()}`,
      echo: 'project.doc.ui["theme"]', disabled: !project,
      run: () => setTheme(nextTheme()) },
    { id: "save", label: "Save the project", echo: "project.save()", disabled: !project,
      run: async () => { await api.save(); say("project.save()"); } },
  ]);

  function keydown(event: KeyboardEvent) {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      paletteOpen = !paletteOpen;
      return;
    }
    // while the palette is open it owns the keyboard — Esc closes it there, and
    // `r` would otherwise start a fit from inside a search box
    if (paletteOpen) return;
    if (event.key === "Escape" && busy) {
      cancel();
      return;
    }
    if (!isShortcutTarget(event)) return;
    const command = commands.find((entry) => entry.key === event.key);
    if (command && !command.disabled) {
      event.preventDefault();
      command.run();
    }
  }

  // "system" has to keep meaning system: a machine that switches at dusk must
  // take the app with it, which is only true if the query is *listened* to
  // rather than read once at boot
  onMount(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!query) return;
    systemDark = query.matches;
    const listen = () => (systemDark = query.matches);
    query.addEventListener?.("change", listen);
    return () => query.removeEventListener?.("change", listen);
  });

  onMount(() => {
    (async () => {
      version = await api.version();
      capabilities = await api.capabilities();
      await loadProject();
      run = await api.runState();
      await loadResult();
      if (project) {
        await loadPeaks();
        // the session outlives this page: a reload must not lose an indexing
        // answer (or its extinction screen) the server still holds — both
        // loaders treat the 409 empty states as "nothing yet".  Order matters:
        // loadIndexAnswer clears the screen it assumes stale.
        await loadIndexAnswer();
        await loadExtinction();
      }
    })();

    // The run this shell has already reacted to, as (state, outcome, node).  Keyed
    // on the *outcome* rather than on having seen a `running` frame: the state
    // channel only sends a frame when the coarse frame changes, so a stage that
    // starts and finishes between two frames delivers one idle frame carrying a
    // new status — and a transition test would treat it as nothing having happened
    // and leave the previous fit's curves on screen.  `null` until the first frame,
    // so a reload does not announce the outcome of a run that ended before it.
    let seen: string | null = null;
    return follow(
      (event: EngineEvent) => say(consoleLine(event)),
      (frame: RunState) => {
        run = frame;
        const key = `${frame.state}:${frame.run.status ?? ""}:${frame.run.node_id ?? ""}`;
        // a run just ended (any way it ended) → the result and the history moved
        if (seen !== null && key !== seen && frame.state === "idle" && frame.run.status) {
          if (frame.run.kind === "index") {
            // an indexing run commits no node and moves no curves; what it
            // leaves is its answer, adopt verdicts included
            loadIndexAnswer();
            tab = "peaks";
          } else if (frame.run.kind === "extinction") {
            // same shape one rank down: the screen is the whole outcome
            loadExtinction();
            tab = "peaks";
          } else {
            loadResult();
          }
          if (frame.run.status === "failed") say(`FAILED  ${frame.run.error?.message ?? ""}`);
          if (frame.run.status === "cancelled"
              && frame.run.kind !== "index" && frame.run.kind !== "extinction")
            say(`cancelled at stage ${frame.run.stage} — state stands at ${frame.run.node_id}`);
        }
        seen = key;
      },
      { poll: (since) => api.events(since) },
    );
  });
</script>

<svelte:window onkeydown={keydown} />

<header>
  <div class="title">
    <strong>pxrdref</strong>
    <span class="muted mono">{version?.package_version ?? "…"}</span>
  </div>

  {#if project}
    <div class="project mono" title={project.path}>
      {project.path.split("/").pop()}
      <span class="muted">· {project.data.filename} · {project.data.n_points} pts</span>
      <span class="muted">· {project.doc.mode}</span>
      <span class="muted">· σ {project.data.has_sigma ? "from file" : "Poisson"}</span>
    </div>
  {/if}

  <!-- A hopeless fit must not be presented in the register of a good one
       (WP-1029 item c).  The judgement is the *report's* — `maturity` quotes
       `MATURITY_MAX_RWP`, the Rwp past which Layer 1 refuses to speak about
       individual parameters — so nothing here decides anything, and the
       `status` vocabulary (which still says `converged` at Rwp 96 %) is left
       alone: that is WP-1028's, and two owners would disagree. -->
  <div class="stats tabular mono" class:immature={immature}>
    {#if rwp !== null}
      Rwp <strong>{(rwp * 100).toFixed(3)}%</strong>
      {#if gof !== null}<span class="muted">GoF {gof.toFixed(3)}</span>{/if}
      {#if immature}
        <button class="ghost tiny warn" title={result.maturity.message}
          onclick={() => { mode = "panes"; tab = "report"; }}>
          ⚠ not a fit yet
        </button>
      {/if}
    {/if}
  </div>

  <div class="controls">
    {#if project}
      <div class="segmented" role="group" aria-label="view">
        {#each MODES as entry (entry.id)}
          <button class:on={mode === entry.id} onclick={() => (mode = entry.id)}
            title={entry.title}>{entry.label}</button>
        {/each}
      </div>
      <div class="segmented" role="group" aria-label="disclosure">
        <button class:on={simple} onclick={() => setSimple(true)}
          title="hide bounds, transforms and stage seeds">Simple</button>
        <button class:on={!simple} onclick={() => setSimple(false)}
          title="show every field a stage and a parameter carry">Advanced</button>
      </div>
      <div class="segmented theme" role="group" aria-label="theme">
        {#each THEME_CHOICES as choice (choice)}
          <button class:on={themeChoice === choice} onclick={() => setTheme(choice)}
            aria-label={choice} title={THEME_TITLE[choice]}>{GLYPH[choice]}</button>
        {/each}
      </div>
    {/if}
    <span class="pill" data-state={run?.state ?? "idle"}>
      {#if busy}
        {run?.run.stage ?? "starting"}
        {#if run?.run.stage_index}({run.run.stage_index}/{run.run.n_stages}){/if}
      {:else}
        {run?.run.status ?? "idle"}
      {/if}
    </span>
    <button onclick={start} disabled={busy || !project}>Run</button>
    <button class="ghost" onclick={cancel} disabled={!busy}>Cancel</button>
    <button class="ghost" onclick={() => (paletteOpen = true)} title="every command, with the call it makes">
      <kbd>⌘K</kbd>
    </button>
  </div>
</header>

<main bind:this={mainEl}>
  {#if !project}
    <!-- the empty state *is* the import wizard (WP-1014): one component, so
         "make a project" and "look at the model" cannot drift apart -->
    <section class="empty">
      {#if openError}<p class="bad">{openError}</p>{/if}
      {#if recent.length}
        <p class="muted small">Recently opened:</p>
        <ul class="recent">
          {#each recent as entry (entry.path)}
            <li><button class="ghost" onclick={() => open(entry.path)}>{entry.name}</button>
              <span class="muted mono">{entry.path}</span></li>
          {/each}
        </ul>
      {/if}
      <Model bind:this={modelPanel} {capabilities} {busy} {say} onopened={opened} />
    </section>
  {:else}
    <!-- the text pane stays mounted while hidden, exactly as the tabs do: a
         buffer with unedited-but-typed changes has to survive a look at the
         parameter table.  Its editor is built on first entry, not on boot. -->
    <div class="textmode" class:hidden={!textMode}>
      <Text {head} {busy} active={textMode} dark={theme === "dark"} {say} onmoved={moved} />
    </div>
    <!-- mounted while hidden, as the tabs are: a typed species or a half-filled
         wizard has to survive a look at the plot.  `active` is what keeps it from
         refetching three routes on every head move it is not showing. -->
    <div class="textmode" class:hidden={!modelMode}>
      <Model bind:this={modelPanel} {project} {capabilities} {head} {busy} {simple}
        {theme} {say} active={modelMode} columns={modelColumns} oncolumns={modelSized}
        onopened={opened} onmoved={moved} />
    </div>
    <div class="panes" class:hidden={mode !== "panes"}>
      <Plot {result} {plotKey} {zoom} {theme} error={resultError}
        peaks={peaksData} peaksActive={tab === "peaks"} hovered={hoveredPeak}
        {protocol} {extent} {channels} {protocolError} {busy}
        onhoverpeak={(i) => (hoveredPeak = i)}
        onaddpeak={addPeak} onmovepeak={movePeak} ontogglepeak={togglePeak}
        onremovepeak={removePeak} onprotocol={setProtocol} />
      <div class="side" bind:clientWidth={sideMeasured}
        style:flex={sideWidth === null ? null : `0 0 ${sideWidth}px`}>
        <Splitter size={sideWidth ?? sideMeasured} grow="left" min={300} keep={360}
          extent={() => mainEl?.clientWidth ?? 0} onsize={sideSized}
          title="drag to resize the panel column" />
        <nav class="tabs">
          <button class:on={tab === "params"} onclick={() => (tab = "params")}>Parameters</button>
          <button class:on={tab === "plan"} onclick={() => (tab = "plan")}>Plan</button>
          <button class:on={tab === "peaks"} onclick={() => (tab = "peaks")}>Peaks</button>
          <button class:on={tab === "report"} onclick={() => (tab = "report")}>Report</button>
          <button class:on={tab === "history"} onclick={() => (tab = "history")}>History</button>
          <button class:on={tab === "build"} onclick={() => (tab = "build")}>Build</button>
        </nav>
        <!-- every tab stays mounted: switching must not throw away a filter, a
             pending edit, an unsaved stage list or a two-node comparison -->
        <div class="panel" class:hidden={tab !== "params"}>
          <Params bind:this={paramsPanel} {head} {busy} {simple} {say} />
        </div>
        <div class="panel" class:hidden={tab !== "plan"}>
          <Plan bind:this={planPanel} mode={project.doc.mode} {busy} {simple} {say}
            onrun={runStage} />
        </div>
        <div class="panel" class:hidden={tab !== "peaks"}>
          <Peaks peaks={peaksData} {indexAnswer} {extinction} {run} {busy} {say}
            hovered={hoveredPeak} onhover={(i) => (hoveredPeak = i)}
            onpeaks={(p) => (peaksData = p)}
            onindexed={(a) => (indexAnswer = a)}
            onzoom={(lo, hi) => (zoom = [lo, hi])} onmoved={moved} />
        </div>
        <div class="panel" class:hidden={tab !== "report"}>
          <Report {head} {busy} {simple} {say} {applied}
            chi2={result?.statistics?.chi2 ?? null}
            onzoom={(lo, hi) => (zoom = [lo, hi])}
            onapplied={absorbApply} onmoved={moved} />
        </div>
        <div class="panel" class:hidden={tab !== "history"}>
          <History {head} {busy} {say} onmoved={moved} />
        </div>
        <div class="panel" class:hidden={tab !== "build"}>
          <Stubs {capabilities} {project} />
        </div>
        <Console {lines} {dropped} height={consoleHeight} onresize={setConsoleHeight} />
      </div>
    </div>
  {/if}
</main>

{#if paletteOpen}
  <Palette {commands} onclose={() => (paletteOpen = false)} />
{/if}

<style>
  header {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 8px 14px;
    border-bottom: 1px solid var(--line);
    background: var(--panel);
    flex: 0 0 auto;
  }

  .title {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }

  /* the one thing in the header that may be shortened: everything else is a
     control, and a clipped `Advanced` is worse than a clipped filename */
  .project {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    flex: 1 1 auto;
    min-width: 0;
  }

  .stats {
    margin-left: auto;
    flex: 0 0 auto;
    display: flex;
    align-items: baseline;
    gap: 6px;
    white-space: nowrap;
  }

  .stats.immature strong {
    color: var(--warn);
  }

  .stats button.warn {
    color: var(--warn);
    border-color: var(--warn);
    border-style: dashed;
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 0 0 auto;
  }

  .segmented.theme button {
    padding: 3px 7px;
    font-size: 12px;
    line-height: 1.1;
  }

  .pill[data-state="running"] {
    color: var(--ok);
    border-color: var(--ok);
  }

  .pill[data-state="cancelling"] {
    color: var(--warn);
    border-color: var(--warn);
  }

  main {
    flex: 1 1 auto;
    overflow: hidden;
  }

  .panes {
    display: flex;
    height: 100%;
  }

  .textmode {
    height: 100%;
  }

  .panes.hidden,
  .textmode.hidden {
    display: none;
  }

  /* The panel column is a *surface*, and says so (WP-1032).
     Reported as "transparent headings clash with other text on scroll"; what is
     actually there is a colour mismatch, measured in both themes.  The Peaks
     table's `th` is the app's only `position: sticky`, and it already paints an
     opaque `var(--panel)` backdrop — over a column that set no background at
     all and therefore showed the body's `--bg`.  Two surfaces, one strip:
     #ffffff on #fbfbfa light, #1e1e1e on #151515 dark, so the header row read
     as a band of a different colour rather than as a backdrop.  Naming the
     column `--panel` — which is what the header bar already is — makes the
     sticky backdrop match the surface it sticks to, and is why no rule here
     needs to know that a table above it is sticky. */
  .side {
    flex: 0 0 clamp(340px, 38%, 560px);
    background: var(--panel);
    border-left: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    min-width: 0;
    /* a stored width outliving the window it was chosen in must not hide the
       plot; the drag clamps against the live extent, this clamps against a
       *resize*, which no drag is present for */
    max-width: 72%;
    position: relative;
  }

  .tabs {
    display: flex;
    border-bottom: 1px solid var(--line);
    flex: 0 0 auto;
  }

  .tabs button {
    flex: 1 1 auto;
    border: 0;
    border-radius: 0;
    background: transparent;
    color: var(--muted);
    font-weight: 400;
    padding: 5px 4px;
    border-bottom: 2px solid transparent;
  }

  .tabs button.on {
    color: var(--fg);
    border-bottom-color: var(--accent);
    font-weight: 600;
  }

  .panel {
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1 1 auto;
  }

  .panel.hidden {
    display: none;
  }

  .empty {
    height: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .empty ul.recent {
    margin: 0.6rem 0 0;
    padding: 0 1.2rem;
    list-style: none;
  }

  .empty li {
    margin: 0.2rem 0;
  }

  .bad {
    color: var(--bad);
  }
</style>
