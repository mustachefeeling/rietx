<script lang="ts">
  /**
   * The peak list and the indexing answer — WP-1027's tab.
   *
   * Peak picking is the one step where a human eye beats the algorithm, so the
   * *plot* carries the interactions (click to add, drag to move, shift-click to
   * exclude) and this panel is the ledger beside it: every line with its σ and
   * flags, the fitter's own diagnostics as an inline strip (information, not an
   * interruption), and the candidate table when indexing has run.
   *
   * Two design rules come from the API's shape. The candidate list is the
   * **primary** view and the singleton a badge on it — `best_or_none()`
   * returning nothing is the *expected* first outcome on real lab data, so a
   * "here is your cell" happy path would look broken most of the time. And the
   * Adopt button's enabled-ness is the **server's** `adopt` arm, never a local
   * reading of `confidence`: the button and the route must be one answer.
   */
  import { api } from "../api";
  import {
    caveatTone,
    cellText,
    collectTo,
    flagTone,
    fomColumns,
    fomOf,
    type Candidate,
    type PeaksPayload,
  } from "../lib/peaks";
  import { formatEsd, formatValue } from "../lib/table";
  import type { RunState } from "../lib/stream";

  let {
    peaks,
    indexAnswer,
    extinction = null,
    run,
    busy,
    say = () => {},
    onpeaks = () => {},
    onindexed = () => {},
    onzoom = () => {},
    onmoved = () => {},
  }: {
    peaks: PeaksPayload | null;
    indexAnswer: any;
    extinction?: any;
    run: RunState | null;
    busy: boolean;
    say?: (line: string) => void;
    onpeaks?: (payload: PeaksPayload) => void;
    onindexed?: (answer: any) => void;
    onzoom?: (lo: number, hi: number) => void;
    onmoved?: () => void;
  } = $props();

  let failure = $state("");
  let expanded = $state<number | null>(null);
  /** the typed-2θ add box — the non-pointer route to `add_peak` */
  let addAt = $state("");

  const rows = $derived(peaks?.peaks ?? []);
  const unusable = $derived(peaks?.unusable_flags ?? []);
  const diagnostics = $derived(peaks?.diagnostics ?? []);
  const indexing = $derived(busy && run?.run?.kind === "index");
  const screening = $derived(busy && run?.run?.kind === "extinction");
  const candidates = $derived<Candidate[]>(indexAnswer?.result?.candidates ?? []);
  const refuting = $derived<string[]>(indexAnswer?.refuting_caveats ?? []);
  const verdicts = $derived<Array<{ allowed: boolean; why: string }>>(
    indexAnswer?.adopt ?? []);
  const columns = $derived(fomColumns(candidates));
  const best = $derived(verdicts.findIndex((v) => v.allowed));
  const quality = $derived(indexAnswer?.result?.quality ?? null);
  const screen = $derived(extinction?.result ?? null);
  /** may the screened candidate be adopted?  The server's verdict, reused —
   *  it decides whether a space-group chip is a button or a fact */
  const screenAdoptable = $derived(
    extinction !== null && Boolean(verdicts[extinction.candidate]?.allowed));

  async function verb(work: () => Promise<PeaksPayload>) {
    failure = "";
    try {
      const payload = await work();
      if (payload.api_call) say(payload.api_call);
      onpeaks(payload);
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  const pick = () => verb(() => api.pickPeaks());
  const remove = (index: number) => verb(() => api.removePeak(index));

  function addTyped() {
    const tt = Number(addAt);
    if (!Number.isFinite(tt)) {
      failure = `"${addAt}" is not a 2θ`;
      return;
    }
    addAt = "";
    verb(() => api.addPeak(tt));
  }
  const toggleUse = (index: number, usable: boolean) =>
    verb(() => api.flagPeak(index, { use_for_indexing: !usable }));
  const refit = (group: number) => verb(() => api.refitGroup(group));

  async function startIndex() {
    failure = "";
    try {
      await api.index();
      say("index_pattern(peaks, data=…, instrument=…)");
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  async function adopt(index: number, spaceGroup?: string) {
    failure = "";
    try {
      const answer = await api.adoptCandidate(index, spaceGroup);
      say(answer.api_call);
      onmoved(); // the head moved: the model is the adopted cell now
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  async function screenExtinctions(index: number) {
    failure = "";
    try {
      await api.screenExtinctions(index);
      say(`determine_extinction_symbol(data, result.candidates[${index}], instrument)`);
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  function zoomTo(tt: number, fwhm: number) {
    onzoom(tt - 8 * fwhm, tt + 8 * fwhm);
  }
</script>

<section>
  <div class="controls">
    <button onclick={pick} disabled={busy}
      title="fit every detectable line; replaces the stored list, edits included">
      {rows.length ? "Re-pick peaks" : "Pick peaks"}
    </button>
    <button onclick={startIndex} disabled={busy || !rows.length}
      title="run every indexing engine on the usable lines; agreement is the confidence">
      Index
    </button>
    {#if peaks?.peaks}
      <input class="add" type="text" inputmode="decimal" placeholder="add at 2θ…"
        bind:value={addAt} disabled={busy}
        onkeydown={(ev) => ev.key === "Enter" && addTyped()}
        title="seed a component at this 2θ and refit the group it lands in
(the plot's click does the same)" />
    {/if}
    {#if indexing}
      <span class="muted small">
        {run?.run?.stage ?? "starting"}
        {#if run?.run?.stage_index}({run.run.stage_index}/{run.run.n_stages}){/if}
      </span>
    {/if}
  </div>
  {#if failure}<p class="bad small">{failure}</p>{/if}

  {#if !peaks?.peaks}
    <p class="muted note">
      No peak list yet. <strong>Pick peaks</strong> fits every detectable line;
      afterwards, click the plot to add one the fitter missed, drag a marker to
      correct one, shift-click to exclude.
    </p>
  {:else}
    <p class="muted small tabular">
      {peaks.n_usable} of {peaks.n_total} lines usable for indexing
      {#if peaks.source === "positions"}
        · <span class="chip warn" title="positions were supplied, so every σ is an
          assumption — the σ(Q)/Q figure is not a property of the data">σ assumed</span>
      {/if}
    </p>

    {#if diagnostics.length}
      <ul class="strip">
        {#each diagnostics as d (d.code + d.message)}
          <li class={d.level}><span class="mono">{d.code}</span> {d.message}</li>
        {/each}
      </ul>
    {/if}

    <div class="scroll">
      <table class="tabular">
        <thead>
          <tr><th>#</th><th>2θ (°)</th><th>d (Å)</th><th>I</th><th>flags</th><th></th></tr>
        </thead>
        <tbody>
          {#each rows as p (p.index)}
            <tr class:out={!p.usable}>
              <td class="muted">{p.index}</td>
              <td>
                <button class="ghost pos" title="zoom the plot to this line"
                  onclick={() => zoomTo(p.two_theta, p.fwhm)}>
                  {formatValue(p.two_theta, p.two_theta_esd)}<span class="muted">{formatEsd(p.two_theta, p.two_theta_esd)}</span>
                </button>
              </td>
              <td>{p.d.toFixed(4)}</td>
              <td>{Number(p.intensity.toPrecision(3))}</td>
              <td class="flags">
                {#if p.origin !== "fitted"}
                  <span class="chip origin" title="a human placed or moved this line">{p.origin}</span>
                {/if}
                {#each p.flags as f (f)}
                  <span class="chip {flagTone(f, unusable)}">{f}</span>
                {/each}
              </td>
              <td class="acts">
                <input type="checkbox" checked={p.usable} disabled={busy}
                  title={p.usable ? "exclude from indexing" :
                         "use for indexing (overrules the fitter's flags)"}
                  onchange={() => toggleUse(p.index, p.usable)} />
                {#if p.n_in_group > 1}
                  <button class="ghost tiny" disabled={busy}
                    title="refit group {p.group} ({p.n_in_group} components) under the picker's own judgement"
                    onclick={() => refit(p.group)}>↻</button>
                {/if}
                <button class="ghost tiny" disabled={busy} title="remove this line"
                  onclick={() => remove(p.index)}>×</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if indexAnswer}
    <h2>Indexing</h2>
    {#if !candidates.length}
      <p class="note muted">
        No candidate cells.
        {#if quality?.abstained_reason}{quality.abstained_reason}{/if}
      </p>
      <ul class="strip">
        {#each indexAnswer.result?.diagnostics ?? [] as d (d.code + d.message)}
          <li class={d.level}><span class="mono">{d.code}</span> {d.message}</li>
        {/each}
      </ul>
    {:else}
      {#if best < 0}
        <p class="note muted" title="best_or_none() returned None — the expected
          outcome until the evidence singles one cell out">
          No candidate reaches the gate; the list below is ranked, not chosen.
        </p>
      {/if}
      <div class="scroll">
        <table class="tabular candidates">
          <thead>
            <tr>
              <th></th><th>cell</th><th>lattice</th>
              {#each columns as name (name)}<th>{name}</th>{/each}
              <th>Rwp</th><th title="reflections predicted where the pattern has
                no intensity — the oversized-cell detector">absent</th>
              <th>engines</th><th></th>
            </tr>
          </thead>
          <tbody>
            {#each candidates as c, i (i)}
              <tr class:best={i === best}>
                <td>
                  <button class="ghost tiny" title="details, caveats and ambiguity"
                    onclick={() => (expanded = expanded === i ? null : i)}>
                    {expanded === i ? "▾" : "▸"}
                  </button>
                </td>
                <td class="cell">{cellText(c.cell)}
                  <span class="chip conf {c.confidence}">{c.confidence}</span>
                  {#if i === best}<span class="chip best">best_or_none()</span>{/if}
                </td>
                <td>{c.centring} {c.system}<br /><span class="muted">{c.volume.toFixed(1)} Å³</span></td>
                {#each columns as name (name)}
                  {@const v = fomOf(c, name)}
                  <td>{v === null ? "—" : v.toFixed(1)}</td>
                {/each}
                <td>{c.lebail ? (c.lebail.rwp * 100).toFixed(1) + "%" : "—"}</td>
                <td>{c.lebail ? `${c.lebail.predicted_but_absent}/${c.lebail.n_reflections}` : "—"}</td>
                <td class="flags">
                  {#each c.found_by as e (e)}<span class="chip note">{e}</span>{/each}
                </td>
                <td>
                  <button disabled={busy || !(verdicts[i]?.allowed)}
                    title={verdicts[i]?.allowed
                      ? "adopt this cell as the model (a Le Bail scaffold; one history node)"
                      : verdicts[i]?.why ?? ""}
                    onclick={() => adopt(i)}>Adopt</button>
                </td>
              </tr>
              {#if expanded === i}
                <tr class="detail">
                  <td></td>
                  <td colspan={7 + columns.length}>
                    {#if c.confidence_caveats.length}
                      <p class="flags">
                        {#each c.confidence_caveats as caveat (caveat)}
                          <span class="chip {caveatTone(caveat, refuting)}">{caveat}</span>
                        {/each}
                      </p>
                    {/if}
                    {#each c.ambiguity as partner, k (k)}
                      <p class="small">
                        geometrically indistinguishable: {cellText(partner.cell)}
                        ({partner.system}, index {partner.index})
                        {#if partner.discriminating_two_theta?.length}
                          — separable at 2θ ≈
                          {partner.discriminating_two_theta.slice(0, 4).map((t: number) => t.toFixed(2)).join(", ")}°
                        {/if}
                      </p>
                    {/each}
                    {#if collectTo(c) !== null}
                      <p class="small warn">collect to 2θ ≈ {collectTo(c)?.toFixed(1)}°
                        to break the ambiguity — the discriminating lines are beyond
                        the measured range</p>
                    {/if}
                    <p class="small">
                      <button class="tiny" disabled={busy}
                        title="rank the extinction classes this lattice allows: one shared
profile fit, then one Le Bail per class — the answer is a ranked list of
classes, and every class lists all its space groups (WP-1025)"
                        onclick={() => screenExtinctions(i)}>Screen extinctions</button>
                      {#if extinction?.candidate === i && screen}
                        <span class="muted">screened — table below</span>
                      {/if}
                    </p>
                    <ul class="strip">
                      {#each c.diagnostics as d (d.code + d.message)}
                        <li class={d.level}><span class="mono">{d.code}</span> {d.message}</li>
                      {/each}
                    </ul>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    {#if screening && !screen}
      <p class="muted small">screening extinction classes…</p>
    {/if}
    {#if screen}
      <h2>Extinction — candidate {extinction.candidate}</h2>
      <p class="muted small tabular">
        reference {screen.lattice_group} (absence-free) ·
        {screen.n_screened} of {screen.n_classes} classes fitted ·
        2θ {screen.two_theta_range[0].toFixed(1)}–{screen.two_theta_range[1].toFixed(1)}°
      </p>
      {#if extinction.best === null}
        <p class="note muted" title="best_or_none() returned None — refuted
          classes, an indecisive ΔBIC margin, or unfitted classes leave an
          unasked question, which must not read as a clean answer">
          No class is singled out; the list below is ranked, not chosen.
        </p>
      {/if}
      <div class="scroll">
        <table class="tabular">
          <thead>
            <tr>
              <th>class</th>
              <th title="BIC(class) − BIC(absence-free reference); negative favours the class">ΔBIC</th>
              <th title="absences the data could test / absences the class asserts —
an absence outside the range or under a neighbour is not an observation">testable</th>
              <th title="testable forbidden positions carrying intensity; each one refutes the class">refuting</th>
              <th title="every space group in the class — a powder cannot
distinguish them, so a singleton here would be unmeasurable">space groups</th>
            </tr>
          </thead>
          <tbody>
            {#each screen.candidates as cls, k (cls.symbol + k)}
              <tr class:out={cls.refuted} class:best={extinction.best === k}>
                <td class="mono">{cls.symbol}
                  {#if extinction.best === k}<span class="chip best">best_or_none()</span>{/if}
                  {#if cls.refuted}
                    <span class="chip bad" title={cls.refuted_reason ?? ""}>refuted</span>
                  {:else if !cls.screened}
                    <span class="chip warn" title="left unfitted (cap or cancel) —
an unasked question, so the gate abstains">not screened</span>
                  {/if}
                </td>
                <td>{cls.screened ? cls.delta_bic.toFixed(1) : "—"}</td>
                <td>{cls.n_testable}/{cls.n_absent}</td>
                <td>
                  {#if cls.n_present}
                    {cls.n_present}:
                    {(cls.forbidden_hkl ?? []).slice(0, 3)
                      .map((hkl: number[], j: number) =>
                        `(${hkl.join("")}) ${cls.forbidden_two_theta?.[j]?.toFixed(2) ?? "?"}°`)
                      .join(" ")}
                  {:else}—{/if}
                </td>
                <td class="flags">
                  {#each cls.space_groups as sg (sg)}
                    {#if screenAdoptable && !cls.refuted}
                      <button class="chip act" disabled={busy}
                        title="adopt candidate {extinction.candidate} as a Le Bail scaffold
in {sg} — the class cannot distinguish its members, so this choice is a
convention, not a measurement"
                        onclick={() => adopt(extinction.candidate, sg)}>{sg}</button>
                    {:else}
                      <span class="chip">{sg}</span>
                    {/if}
                  {/each}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <ul class="strip">
        {#each screen.diagnostics ?? [] as d (d.code + d.message)}
          <li class={d.level}><span class="mono">{d.code}</span> {d.message}</li>
        {/each}
      </ul>
    {/if}
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

  .controls {
    display: flex;
    gap: 8px;
    align-items: center;
    flex: 0 0 auto;
  }

  .add {
    width: 90px;
    font: var(--mono);
  }

  h2 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin: 8px 0 2px;
    font-weight: 600;
  }

  /* Each table gets a bounded window of its own rather than a share of the
     section: as flex children with min-height 0, three stacked tables shrank
     each other proportionally, and the 71-row extinction table came up as a
     70 px sliver (measured). No shrink + a 45vh cap keeps a short table at
     its content height, a long one at ~20 rows under its sticky header, and
     the section's own scrollbar handles the rest. */
  .scroll {
    overflow: auto;
    flex: 0 0 auto;
    max-height: 45vh;
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
    background: var(--panel);
  }

  td {
    padding: 1px 6px;
    border-top: 1px solid var(--line);
    white-space: nowrap;
    vertical-align: top;
  }

  tr.out td {
    opacity: 0.55;
  }

  tr.best td {
    background: color-mix(in srgb, var(--ok) 8%, transparent);
  }

  .pos {
    padding: 0;
    font: inherit;
  }

  .flags {
    display: flex;
    gap: 3px;
    flex-wrap: wrap;
    align-items: center;
  }

  .chip {
    font-size: 10px;
    padding: 0 5px;
    border-radius: 7px;
    border: 1px solid var(--line);
    color: var(--muted);
    white-space: nowrap;
  }

  .chip.out { color: var(--bad); border-color: var(--bad); }
  .chip.bad { color: var(--bad); border-color: var(--bad); }
  /* a space-group chip that *acts* (adopt in this group) keeps the chip's
     shape and gains a button's affordance */
  button.chip.act { cursor: pointer; color: var(--accent); border-color: var(--accent); background: none; }
  button.chip.act:hover:not(:disabled) { background: color-mix(in srgb, var(--accent) 12%, transparent); }
  .chip.warn { color: var(--warn); border-color: var(--warn); }
  .chip.origin { color: var(--accent); border-color: var(--accent); }
  .chip.conf.high { color: var(--ok); border-color: var(--ok); }
  .chip.conf.medium { color: var(--warn); border-color: var(--warn); }
  .chip.conf.low { color: var(--muted); }
  .chip.best { color: var(--ok); border-color: var(--ok); font-weight: 600; }

  .strip {
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: 11px;
    flex: 0 0 auto;
  }

  .strip li {
    padding: 1px 0;
    color: var(--muted);
  }

  .strip li.warning { color: var(--warn); }
  .strip li.error { color: var(--bad); }

  .acts {
    display: flex;
    gap: 2px;
    align-items: center;
  }

  .tiny {
    padding: 0 4px;
    font-size: 11px;
  }

  .small { font-size: 11.5px; margin: 2px 0; }
  .note { margin: 4px 0; font-size: 12px; }
  .bad { color: var(--bad); }
  .warn { color: var(--warn); }
  td.cell { white-space: normal; min-width: 150px; }
</style>
