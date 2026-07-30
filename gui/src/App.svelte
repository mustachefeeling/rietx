<script lang="ts">
  /**
   * The shell: one header of run controls and statistics, the plot, the console.
   *
   * State lives in runes here and is passed down; there is no store library
   * because there is one session and one project, and a second source of truth
   * for "is a run in flight" is exactly the bug the server's 409 exists to
   * prevent. The `state` frame from the event stream is that truth — every
   * control's disabled attribute derives from it rather than from what the last
   * click hoped.
   */
  import { onMount } from "svelte";

  import { ApiError, api } from "./api";
  import Console from "./panels/Console.svelte";
  import Plot from "./panels/Plot.svelte";
  import Stubs from "./panels/Stubs.svelte";
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

  const busy = $derived(run?.state !== "idle");
  const rwp = $derived(result?.statistics?.rwp ?? run?.run?.rwp ?? null);
  const gof = $derived(result?.statistics?.gof ?? run?.run?.gof ?? null);

  function say(line: string) {
    lines = [...lines.slice(-400), line];
  }

  async function loadProject() {
    try {
      project = await api.project();
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

  async function cancel() {
    try {
      run = await api.cancel();
      say("token.cancel()");
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
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

    let last = run?.state ?? "idle";
    return follow(
      (event: EngineEvent) => say(consoleLine(event)),
      (frame: RunState) => {
        run = frame;
        // a run just ended (any way it ended) → the result and the history moved
        if (last !== "idle" && frame.state === "idle") {
          loadResult();
          if (frame.run.status === "failed") say(`FAILED  ${frame.run.error?.message ?? ""}`);
          if (frame.run.status === "cancelled")
            say(`cancelled at stage ${frame.run.stage} — state stands at ${frame.run.node_id}`);
        }
        last = frame.state;
      },
      { poll: (since) => api.events(since) },
    );
  });
</script>

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
      <Plot {result} {plotKey} error={resultError} />
      <div class="side">
        <Stubs {capabilities} {project} />
        <Console {lines} {dropped} />
      </div>
    </div>
  {/if}
</main>

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
    flex: 0 0 clamp(280px, 30%, 460px);
    border-left: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    min-width: 0;
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
