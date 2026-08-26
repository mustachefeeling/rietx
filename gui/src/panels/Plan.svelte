<script lang="ts">
  /**
   * The plan editor: which preset, which stages, in which order.
   *
   * A project stores the plan **expanded through its mode**, so this list is
   * exactly what a run will execute — picking `mccusker_default` in Le Bail mode
   * shows `profile_only`'s stages, because that is what `fit` would have
   * substituted at run time (WP-1008).  The preset name beside the menu is
   * *derived* by comparing the stages against the registry, so editing a stage
   * turns the label to "custom" by itself rather than by a flag someone has to
   * remember to clear.
   *
   * `Run this stage` sends the same `StageSpec` the list is holding, through the
   * same run machinery a whole fit uses — which is what makes "run one stage,
   * look, run the next" the interactive loop the CLI never had.
   */
  import Help from "../Help.svelte";
  import { ApiError, api } from "../api";

  let {
    mode = "rietveld",
    busy = false,
    simple = true,
    say = (_line: string) => {},
    onrun = (_stage: any) => {},
  }: {
    mode?: string;
    busy?: boolean;
    simple?: boolean;
    say?: (line: string) => void;
    onrun?: (stage: any) => void;
  } = $props();

  interface Stage {
    name: string;
    turn_on: string[];
    max_iter: number;
    lebail_cycles: number;
    seed: number;
    strain_seed: number;
  }

  let stages = $state<Stage[]>([]);
  let guard = $state(0.98);
  let preset = $state<string | null>(null);
  let presets = $state<any[]>([]);
  let error = $state("");
  let dirty = $state(false);
  let dragging = $state<number | null>(null);
  /** which stage the `.` shortcut and the palette entry would run */
  let selected = $state(0);

  /** Presets whose declared modes include the project's, first. */
  const offered = $derived(
    [...presets].sort((a, b) => {
      const fit = (p: any) => (p.modes?.includes(mode) ? 0 : 1);
      return fit(a) - fit(b);
    }),
  );
  const chosen = $derived(presets.find((p) => p.name === preset) ?? null);

  async function load() {
    try {
      const [plan, registry] = await Promise.all([api.plan(), api.plans()]);
      stages = plan.plan.stages;
      guard = plan.plan.correlation_guard;
      preset = plan.preset;
      presets = registry.plans;
      dirty = false;
      error = "";
    } catch (exc) {
      if (!(exc instanceof ApiError && exc.empty)) error = (exc as Error).message;
    }
  }

  $effect(() => {
    void mode;
    load();
  });

  async function put(body: Record<string, unknown>) {
    try {
      const payload = await api.putPlan(body);
      stages = payload.plan.stages;
      guard = payload.plan.correlation_guard;
      preset = payload.preset;
      dirty = false;
      error = "";
    } catch (exc) {
      error = exc instanceof ApiError && exc.busy
        ? "a run is in flight — the plan is read-only until it ends"
        : (exc as Error).message;
    }
  }

  async function pick(name: string) {
    say(`plan = resolve_plan(${JSON.stringify(name)}, ${JSON.stringify(mode)})`);
    await put({ preset: name });
  }

  async function save() {
    say(`project.doc.plan = PlanSpec(stages=[${stages.length}], correlation_guard=${guard})`);
    await put({ plan: { stages, correlation_guard: guard } });
  }

  function touch() {
    dirty = true;
  }

  function move(from: number, to: number) {
    if (to < 0 || to >= stages.length || from === to) return;
    const next = [...stages];
    next.splice(to, 0, ...next.splice(from, 1));
    stages = next;
    touch();
  }

  function remove(index: number) {
    stages = stages.filter((_, i) => i !== index);
    touch();
  }

  function globs(index: number, text: string) {
    stages[index].turn_on = text.split(",").map((s) => s.trim()).filter(Boolean);
    touch();
  }

  export function runStage(index = selected) {
    const stage = stages[index];
    if (stage) {
      selected = index;
      say(`ref.run_stage(Stage(${JSON.stringify(stage.name)}, ${JSON.stringify(stage.turn_on)}))`);
      onrun(stage);
    }
  }

  /** The stage `.` would run, for the palette's label — "" when there is none. */
  export function selectedName(): string {
    return stages[selected]?.name ?? "";
  }
</script>

<section>
  <header>
    <select
      value={preset ?? ""}
      disabled={busy}
      onchange={(event) => pick((event.currentTarget as HTMLSelectElement).value)}>
      {#if preset === null}
        <option value="" disabled>custom ({stages.length} stages)</option>
      {/if}
      {#each offered as item (item.name)}
        <option value={item.name} title={item.when_to_use}>
          {item.title}{item.modes?.includes(mode) ? "" : ` · not for ${mode}`}
        </option>
      {/each}
    </select>
    {#if dirty}
      <button disabled={busy} onclick={save}>Save plan</button>
      <button class="ghost" disabled={busy} onclick={load}>Revert</button>
    {/if}
  </header>

  {#if chosen}
    <!-- the preset's own words are the corpus's `plans` arm, projected from
         `PLAN_INFO` — the line shown is `when_to_use`, and the description
         behind it is one click away rather than one hover (WP-1203) -->
    <p class="muted blurb">
      <Help for="plans:{chosen.name}" label="what the {chosen.title} plan does"
        >{chosen.when_to_use}</Help>
    </p>
  {:else}
    <p class="muted blurb">
      Edited — no preset matches these stages. Saving stores them as they stand.
    </p>
  {/if}

  {#if error}<p class="bad">{error}</p>{/if}

  <ol class="stages">
    {#each stages as stage, index (index)}
      <li
        class:dragging={dragging === index}
        class:selected={selected === index}
        draggable={!busy}
        ondragstart={() => (dragging = index)}
        ondragend={() => (dragging = null)}
        ondragover={(event) => event.preventDefault()}
        ondrop={() => dragging !== null && move(dragging, index)}>
        <div class="head">
          <span class="grip muted" title="drag to reorder">⠿</span>
          <input class="name mono" bind:value={stage.name} oninput={touch} disabled={busy}
            onfocus={() => (selected = index)} />
          <button
            class="ghost"
            disabled={busy}
            title="run only this stage, through the same machinery a fit uses"
            onclick={() => runStage(index)}>Run</button>
          <button class="ghost" disabled={busy} onclick={() => remove(index)} title="remove"
            >×</button>
        </div>
        <input
          class="globs mono"
          value={stage.turn_on.join(", ")}
          placeholder="dot-path globs freed here — phases.*.cell.*"
          disabled={busy}
          oninput={(event) => globs(index, (event.currentTarget as HTMLInputElement).value)} />
        {#if !simple}
          <div class="advanced mono muted">
            <label><Help for="stage_fields:max_iter">iter</Help>
              <input type="number" bind:value={stage.max_iter} oninput={touch}
                disabled={busy} /></label>
            <label><Help for="stage_fields:lebail_cycles">lebail</Help>
              <input type="number" bind:value={stage.lebail_cycles} oninput={touch}
                disabled={busy} /></label>
            <label><Help for="stage_fields:seed">seed</Help>
              <input type="number" step="any" bind:value={stage.seed} oninput={touch}
                disabled={busy} /></label>
            <label><Help for="stage_fields:strain_seed">strain</Help>
              <input type="number" step="any" bind:value={stage.strain_seed}
                oninput={touch} disabled={busy} /></label>
          </div>
        {/if}
      </li>
    {/each}
  </ol>

  {#if !simple}
    <p class="muted blurb">
      <label title="report a parameter pair correlated above this after each stage">
        correlation guard
        <input class="mono guard" type="number" step="0.01" min="0" max="1" bind:value={guard}
          oninput={touch} disabled={busy} />
      </label>
    </p>
  {/if}
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: auto;
    flex: 1 1 auto;
    padding: 6px 8px 10px;
  }

  header {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  select {
    flex: 1 1 auto;
    min-width: 0;
    padding: 3px 4px;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: var(--bg);
    color: var(--fg);
  }

  .blurb {
    margin: 4px 0;
  }

  ol.stages {
    list-style: none;
    margin: 4px 0 0;
    padding: 0;
  }

  li {
    border: 1px solid var(--line);
    border-radius: 5px;
    padding: 4px 5px;
    margin-bottom: 4px;
    background: var(--panel);
  }

  li.dragging {
    opacity: 0.5;
  }

  li.selected {
    border-color: var(--accent);
  }

  .head {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .grip {
    cursor: grab;
  }

  input {
    border: 1px solid transparent;
    background: transparent;
    color: inherit;
    border-radius: 3px;
    padding: 1px 3px;
    min-width: 0;
  }

  input:focus {
    border-color: var(--accent);
    background: var(--bg);
    outline: none;
  }

  .name {
    flex: 1 1 auto;
    font-weight: 600;
  }

  .globs {
    display: block;
    width: 100%;
    border-color: var(--line);
    margin-top: 3px;
  }

  /* four fields of one kind, so four columns — inline labels of four different
     widths put the four boxes at four different offsets on every stage */
  .advanced {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 2px 8px;
    margin-top: 3px;
    font-size: var(--text-sm);
  }

  .advanced label {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }

  .advanced input {
    width: 100%;
    border-color: var(--line);
  }

  .guard {
    width: 60px;
    border-color: var(--line);
  }

  .bad {
    color: var(--bad);
    margin: 2px 0;
  }
</style>
