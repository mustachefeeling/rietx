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
  import Palette from "./panels/Palette.svelte";
  import Params from "./panels/Params.svelte";
  import Plan from "./panels/Plan.svelte";
  import Plot from "./panels/Plot.svelte";
  import Report from "./panels/Report.svelte";
  import Stubs from "./panels/Stubs.svelte";
  import { isShortcutTarget, type Command } from "./lib/palette";
  import { consoleLine, follow, type EngineEvent, type RunState } from "./lib/stream";

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

  let tab = $state<"params" | "plan" | "history" | "report" | "build">("params");
  let simple = $state(true);
  let consoleHeight = $state(150);
  let paletteOpen = $state(false);
  let paramsPanel = $state<any>(null);
  let planPanel = $state<any>(null);
  /** a 2θ window the report panel asked the plot to show, or null for all of it */
  let zoom = $state<[number, number] | null>(null);
  /** the last applied suggestion, until it is undone — carries the node to check
   *  out and the χ² it was applied at, which is what makes the *observed* Δχ²
   *  measurable beside the predicted one */
  let applied = $state<any>(null);

  const busy = $derived(run?.state !== "idle");
  const rwp = $derived(result?.statistics?.rwp ?? run?.run?.rwp ?? null);
  const gof = $derived(result?.statistics?.gof ?? run?.run?.gof ?? null);
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

  async function open(path: string) {
    try {
      project = await api.openProject(path);
      readUi();
      openError = "";
      await loadResult();
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
    { id: "report", label: "Show the fit report", echo: "ref.report()", key: "?",
      disabled: !project, run: () => (tab = "report") },
    { id: "history", label: "Show the history", echo: "ref.history.summary()", key: "h",
      disabled: !project, run: () => (tab = "history") },
    { id: "disclosure", label: simple ? "Show advanced controls" : "Hide advanced controls",
      echo: 'project.doc.ui["simple"]', disabled: !project, run: () => setSimple(!simple) },
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

  onMount(() => {
    (async () => {
      version = await api.version();
      capabilities = await api.capabilities();
      await loadProject();
      run = await api.runState();
      await loadResult();
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
          loadResult();
          if (frame.run.status === "failed") say(`FAILED  ${frame.run.error?.message ?? ""}`);
          if (frame.run.status === "cancelled")
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

  <div class="stats tabular mono">
    {#if rwp !== null}
      Rwp <strong>{(rwp * 100).toFixed(3)}%</strong>
      {#if gof !== null}<span class="muted">GoF {gof.toFixed(3)}</span>{/if}
    {/if}
  </div>

  <div class="controls">
    {#if project}
      <div class="segmented" role="group" aria-label="disclosure">
        <button class:on={simple} onclick={() => setSimple(true)}
          title="hide bounds, transforms and stage seeds">Simple</button>
        <button class:on={!simple} onclick={() => setSimple(false)}
          title="show every field a stage and a parameter carry">Advanced</button>
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

<main>
  {#if !project}
    <section class="empty">
      <h1>No project open</h1>
      {#if openError}<p class="bad">{openError}</p>{/if}
      {#if recent.length}
        <p class="muted">Recently opened:</p>
        <ul>
          {#each recent as entry (entry.path)}
            <li><button class="ghost" onclick={() => open(entry.path)}>{entry.name}</button>
              <span class="muted mono">{entry.path}</span></li>
          {/each}
        </ul>
      {:else}
        <p class="muted">
          Start one from the API or the CLI — <code>pxrdref gui my_sample.pxrd</code>.
          Creating a project in the browser needs the import flow (WP-1014).
        </p>
      {/if}
    </section>
  {:else}
    <div class="panes">
      <Plot {result} {plotKey} {zoom} error={resultError} />
      <div class="side">
        <nav class="tabs">
          <button class:on={tab === "params"} onclick={() => (tab = "params")}>Parameters</button>
          <button class:on={tab === "plan"} onclick={() => (tab = "plan")}>Plan</button>
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

  .project {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .stats {
    margin-left: auto;
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .segmented {
    display: flex;
    border: 1px solid var(--line);
    border-radius: 5px;
    overflow: hidden;
  }

  .segmented button {
    border: 0;
    border-radius: 0;
    background: transparent;
    color: var(--muted);
    font-weight: 400;
    padding: 3px 9px;
    font-size: 11.5px;
  }

  .segmented button.on {
    background: var(--accent);
    color: #fff;
  }

  .pill {
    font: var(--mono);
    padding: 2px 8px;
    border-radius: 10px;
    border: 1px solid var(--line);
    color: var(--muted);
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

  .side {
    flex: 0 0 clamp(340px, 38%, 560px);
    border-left: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    min-width: 0;
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
    padding: 3rem clamp(1rem, 6vw, 5rem);
    max-width: 70ch;
  }

  .empty h1 {
    font-size: 1.1rem;
  }

  .empty li {
    margin: 0.2rem 0;
  }

  .bad {
    color: var(--bad);
  }
</style>
