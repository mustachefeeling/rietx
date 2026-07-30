<script lang="ts">
  /**
   * The history worktree: every move this refinement made, and the four verbs
   * that move around in it.
   *
   * A *view*, with no history semantics of its own — the DAG, the checkout, the
   * tag and the annotation are all WP-1008 routes over the v0.2 tree. Three of its
   * rules come from that tree rather than from taste. **A branch is not created,
   * it appears**: there are no moving refs here, only `head` and tags, so
   * "branch" is checkout + tag and the lanes drawn are where the tree actually
   * divided (`lib/history.ts`). **A node carries no parameter values** — ~10 kB of
   * state per node is deliberately absent from the payload — so comparing two
   * nodes asks `/api/history/diff` instead of subtracting two states the client
   * does not have. And **a checkout discards the fitted curves**, which is not a
   * failure: the result described the values the checkout just replaced, so the
   * shell is told to refetch and the plot says so.
   *
   * A node's Rwp is its *cached* metric, measured on the model the stage started
   * from; `replay` recomputes at the values it ended on and can differ marginally.
   * That gap is a staleness signal, not a regression, so the badge shows the
   * difference against the parent and claims nothing about significance.
   */
  import { ApiError, api } from "../api";
  import { layout, nodeLabel, rwpDelta, diffRows, type HistoryNode } from "../lib/history";

  let {
    head = null,
    busy = false,
    say = (_line: string) => {},
    onmoved = () => {},
  }: {
    head?: string | null;
    busy?: boolean;
    say?: (line: string) => void;
    onmoved?: () => void;
  } = $props();

  const ROW = 26;
  const LANE = 14;

  let nodes = $state<HistoryNode[]>([]);
  let error = $state("");
  let selected = $state<string>("");
  let against = $state<string>("");
  let diff = $state<Record<string, Array<number | string | null>> | null>(null);
  let metrics = $state<any[]>([]);
  let query = $state("");
  let name = $state("");

  const graph = $derived(layout(nodes));
  const byId = $derived(new Map(nodes.map((n) => [n.id, n])));
  const rail = $derived(graph.lanes * LANE + 6);
  const node = $derived(byId.get(selected) ?? null);
  const rows = $derived(diff === null ? [] : diffRows(diff, query));

  async function load() {
    try {
      const payload = await api.history();
      nodes = payload.nodes;
      if (!byId.has(selected)) selected = payload.head ?? "";
      error = "";
    } catch (exc) {
      nodes = [];
      error = exc instanceof ApiError && exc.empty ? "" : (exc as Error).message;
    }
  }

  // the head is the working state, so it is the one signal that covers a run, a
  // checkout and an edit made in another panel (WP-1005)
  $effect(() => {
    void head;
    load();
  });

  function refused(exc: unknown): string {
    return exc instanceof ApiError && exc.busy
      ? "a run is in flight — the history is read-only until it ends"
      : (exc as Error).message;
  }

  async function checkout(id: string) {
    try {
      say(`ref.checkout(${JSON.stringify(id)})`);
      await api.checkout(id);
      error = "";
      onmoved();
    } catch (exc) {
      error = refused(exc);
    }
  }

  async function tag(id: string) {
    const label = name.trim();
    if (!label) return;
    try {
      say(`tree.tag(${JSON.stringify(id)}, ${JSON.stringify(label)})`);
      await api.tag(id, label);
      name = "";
      error = "";
      await load();
    } catch (exc) {
      error = refused(exc);
    }
  }

  /** Checkout **and** name: what "branch" means in a DAG with no moving refs. */
  async function branch(id: string) {
    const label = name.trim() || `from-${id}`;
    try {
      say(`ref.checkout(${JSON.stringify(id)}); tree.tag(${JSON.stringify(id)}, ${JSON.stringify(label)})`);
      await api.branch(id, label);
      name = "";
      error = "";
      onmoved();
      await load();
    } catch (exc) {
      error = refused(exc);
    }
  }

  async function annotate(id: string, label: string) {
    try {
      say(`tree.annotate(${JSON.stringify(id)}, label=${JSON.stringify(label)})`);
      await api.annotate(id, { label });
      error = "";
      await load();
    } catch (exc) {
      error = refused(exc);
    }
  }

  async function compare(a: string, b: string) {
    try {
      say(`tree.diff(${JSON.stringify(a)}, ${JSON.stringify(b)})`);
      const [d, c] = await Promise.all([api.historyDiff(a, b), api.historyCompare([a, b])]);
      diff = d.diff;
      metrics = c.rows;
      error = "";
    } catch (exc) {
      diff = null;
      error = refused(exc);
    }
  }

  function pickAgainst(id: string) {
    against = against === id ? "" : id;
    if (against && selected && against !== selected) compare(selected, against);
    else diff = null;
  }

  function laneX(lane: number): number {
    return 8 + lane * LANE;
  }

  function rowY(row: number): number {
    return row * ROW + ROW / 2;
  }

  function edgePath(e: { fromRow: number; toRow: number; fromLane: number; toLane: number }) {
    const [x1, y1] = [laneX(e.fromLane), rowY(e.fromRow)];
    const [x2, y2] = [laneX(e.toLane), rowY(e.toRow)];
    if (x1 === x2) return `M ${x1} ${y1} L ${x2} ${y2}`;
    const mid = (y1 + y2) / 2;
    return `M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`;
  }

  function pct(value: number | null): string {
    return value === null || value === undefined ? "—" : `${(value * 100).toFixed(2)}%`;
  }
</script>

<section>
  <div class="bar small">
    <span class="muted">
      {nodes.length} node{nodes.length === 1 ? "" : "s"}
      {#if graph.lanes > 1}· {graph.lanes} lanes{/if}
    </span>
    <span class="spacer"></span>
    <span class="muted" title="click a node to select it, then ⇄ on another to compare">
      select · ⇄ compare
    </span>
  </div>

  {#if error}<p class="bad small">{error}</p>{/if}

  <div class="scroller">
    {#if !nodes.length}
      <p class="muted small pad">No history yet — the tree exists from the project's
        first node, so this fills in as soon as one is open.</p>
    {:else}
      <div class="graph" style:padding-left="{rail}px" style:--row="{ROW}px">
        <svg class="rail" width={rail} height={nodes.length * ROW} aria-hidden="true">
          {#each graph.edges as edge (edge.from + edge.to)}
            <path d={edgePath(edge)} class:merge={edge.merge} />
          {/each}
          {#each graph.placed as placed (placed.node.id)}
            <circle cx={laneX(placed.lane)} cy={rowY(placed.row)}
              r={placed.node.id === head ? 4.5 : 3}
              class:head={placed.node.id === head}
              class:selected={placed.node.id === selected} />
          {/each}
        </svg>

        {#each graph.placed as placed (placed.node.id)}
          {@const n = placed.node}
          {@const delta = rwpDelta(n, byId)}
          <div class="node" class:on={n.id === selected} class:other={n.id === against}>
            <button class="pick" onclick={() => (selected = n.id)}
              title={n.api_call}>
              <span class="id mono muted">{n.id}</span>
              <span class="what">{nodeLabel(n)}</span>
              {#if n.id === head}<span class="chip head">HEAD</span>{/if}
              {#each n.tags as label (label)}<span class="chip">{label}</span>{/each}
              {#if n.n_diagnostics}
                <span class="chip warn" title="{n.n_diagnostics} diagnostic(s)">
                  ⚠ {n.n_diagnostics}</span>
              {/if}
              <span class="spacer"></span>
              {#if n.rwp !== null}
                <span class="rwp mono tabular">{pct(n.rwp)}</span>
                {#if delta !== null}
                  <span class="delta mono tabular" class:better={delta < 0}
                    class:worse={delta > 0}
                    title="against its first parent; a node's metrics are as-optimised">
                    {delta < 0 ? "▾" : "▴"}{Math.abs(delta * 100).toFixed(2)}
                  </span>
                {/if}
              {:else}
                <span class="rwp muted">—</span>
              {/if}
            </button>
            <button class="ghost tiny" title="compare with the selected node"
              onclick={() => pickAgainst(n.id)}>⇄</button>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  {#if node}
    <footer>
      <p class="call mono" title="this node's equivalent public-API call">{node.api_call}</p>
      <p class="muted small tabular">
        {node.kind}{node.status ? ` · ${node.status}` : ""}
        {#if node.n_iterations}· {node.n_iterations} iter{/if}
        {#if node.n_free !== null}· {node.n_free} free{/if}
        {#if node.gof !== null}· GoF {node.gof.toFixed(3)}{/if}
        · {node.created_utc}
      </p>
      {#each node.diagnostics as d (d.code + d.message)}
        <p class="small diag" data-level={d.level}>
          <span class="mono">{d.code}</span>
          {#if d.where?.length}<span class="mono muted">{d.where.join(" ")}</span>{/if}
          {d.message}
        </p>
      {/each}
      <div class="verbs">
        <input class="mono" placeholder="tag or branch name" bind:value={name}
          disabled={busy} />
        <button class="small" disabled={busy || node.id === head}
          onclick={() => checkout(node.id)}
          title="restore this node's state as the working state">Checkout</button>
        <button class="ghost small" disabled={busy || !name.trim()}
          onclick={() => tag(node.id)}>Tag</button>
        <button class="ghost small" disabled={busy}
          onclick={() => branch(node.id)}
          title="checkout and name the fork point — this DAG has no moving refs">
          Branch</button>
        <button class="ghost small" disabled={busy || !name.trim()}
          onclick={() => annotate(node.id, name.trim())}
          title="rename this node">Label</button>
      </div>
      {#if node.id !== head}
        <p class="muted tiny">Checking out discards the fitted curves: they described
          the values this would replace. Re-run to get a result back.</p>
      {/if}
    </footer>
  {/if}

  {#if diff !== null}
    <div class="diff">
      <div class="bar small">
        <strong class="mono">{selected} → {against}</strong>
        <span class="spacer"></span>
        <input class="mono" placeholder="filter paths" bind:value={query} />
        <button class="ghost tiny" onclick={() => { diff = null; against = ""; }}>×</button>
      </div>
      {#if metrics.length === 2}
        <p class="muted small tabular">
          Rwp {pct(metrics[0].rwp)} → {pct(metrics[1].rwp)}
          · free {metrics[0].n_free ?? "—"} → {metrics[1].n_free ?? "—"}
          · {metrics[0].action} → {metrics[1].action}
        </p>
      {/if}
      <p class="muted tiny">
        {rows.length} path{rows.length === 1 ? "" : "s"} differ — the route returns
        only what changed, so there is nothing to filter out; biggest relative move
        first, an appearing parameter on top.
      </p>
      <div class="rows">
        {#each rows.slice(0, 200) as row (row.path)}
          <div class="drow">
            <span class="path mono" title={row.path}>{row.path}</span>
            <span class="mono tabular muted">{row.a === null ? "—" : row.a.toPrecision(7)}</span>
            <span class="mono tabular">{row.b === null ? "—" : row.b.toPrecision(7)}</span>
            <span class="mono tabular" class:better={(row.delta ?? 0) !== 0}>
              {row.delta === null ? "new" : (row.delta > 0 ? "+" : "") + row.delta.toPrecision(3)}
            </span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1 1 auto;
  }

  .bar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 8px 4px;
  }

  .spacer {
    flex: 1 1 auto;
  }

  .small {
    font-size: 11.5px;
  }

  .tiny {
    font-size: 11px;
    margin: 3px 0 0;
  }

  button.small {
    padding: 2px 7px;
    font-size: 11.5px;
  }

  button.tiny {
    padding: 0 5px;
    font-size: 11px;
  }

  .scroller {
    flex: 1 1 auto;
    overflow: auto;
    border-top: 1px solid var(--line);
    min-height: 90px;
  }

  .pad {
    padding: 10px;
  }

  .graph {
    position: relative;
  }

  svg.rail {
    position: absolute;
    left: 0;
    top: 0;
  }

  svg.rail path {
    fill: none;
    stroke: var(--line);
    stroke-width: 1.5;
  }

  svg.rail path.merge {
    stroke-dasharray: 3 2;
  }

  svg.rail circle {
    fill: var(--panel);
    stroke: var(--muted);
    stroke-width: 1.5;
  }

  svg.rail circle.selected {
    stroke: var(--accent);
  }

  svg.rail circle.head {
    fill: var(--accent);
    stroke: var(--accent);
  }

  .node {
    display: flex;
    align-items: center;
    height: var(--row);
    box-sizing: border-box;
    padding-right: 6px;
  }

  .node.on {
    background: color-mix(in srgb, var(--accent) 12%, transparent);
  }

  .node.other {
    background: color-mix(in srgb, var(--warn) 12%, transparent);
  }

  button.pick {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    background: transparent;
    border: 0;
    border-radius: 0;
    color: inherit;
    font-weight: 400;
    text-align: left;
    padding: 0 4px;
    height: 100%;
  }

  .id {
    flex: 0 0 auto;
    font-size: 11px;
  }

  .what {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .chip {
    font: var(--mono);
    font-size: 10px;
    padding: 0 4px;
    border-radius: 8px;
    border: 1px solid var(--line);
    color: var(--muted);
    flex: 0 0 auto;
  }

  .chip.head {
    border-color: var(--accent);
    color: var(--accent);
  }

  .chip.warn {
    border-color: var(--warn);
    color: var(--warn);
  }

  .rwp {
    font-size: 11.5px;
    flex: 0 0 auto;
  }

  .delta {
    font-size: 10.5px;
    flex: 0 0 44px;
    text-align: right;
    color: var(--muted);
  }

  .delta.better,
  .better {
    color: var(--ok);
  }

  .delta.worse {
    color: var(--warn);
  }

  footer {
    border-top: 1px solid var(--line);
    padding: 5px 8px 7px;
    flex: 0 0 auto;
  }

  .call {
    margin: 0 0 3px;
    font-size: 11px;
    overflow: auto;
    white-space: nowrap;
    color: var(--fg);
  }

  .diag {
    margin: 2px 0;
    color: var(--muted);
  }

  .diag[data-level="warning"] {
    color: var(--warn);
  }

  .verbs {
    display: flex;
    gap: 5px;
    align-items: center;
    margin-top: 5px;
  }

  input {
    font: var(--mono);
    flex: 1 1 auto;
    min-width: 0;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: var(--bg);
    color: var(--fg);
    padding: 2px 5px;
    font-size: 11.5px;
  }

  .diff {
    border-top: 1px solid var(--line);
    flex: 0 0 auto;
    max-height: 45%;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .diff .rows {
    overflow: auto;
  }

  .diff p {
    padding: 0 8px;
    margin: 1px 0;
  }

  .drow {
    display: flex;
    gap: 6px;
    padding: 0 8px;
    font-size: 11px;
    line-height: 18px;
  }

  .drow .path {
    flex: 1 1 auto;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    direction: rtl;
    text-align: left;
  }

  .drow span:not(.path) {
    flex: 0 0 74px;
    text-align: right;
  }

  .bad {
    color: var(--bad);
    padding: 0 8px;
    margin: 2px 0;
  }
</style>
