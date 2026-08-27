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
  import { onMount, setContext } from "svelte";

  import { ApiError, api } from "./api";
  import Help from "./Help.svelte";
  import Console from "./panels/Console.svelte";
  import History from "./panels/History.svelte";
  import Model from "./panels/Model.svelte";
  import Palette from "./panels/Palette.svelte";
  import Params from "./panels/Params.svelte";
  import Peaks from "./panels/Peaks.svelte";
  import Plan from "./panels/Plan.svelte";
  import Plot from "./panels/Plot.svelte";
  import Report from "./panels/Report.svelte";
  import Series from "./panels/Series.svelte";
  import Splitter from "./panels/Splitter.svelte";
  import Stubs from "./panels/Stubs.svelte";
  import Text from "./panels/Text.svelte";
  import {
    HELP_CONTEXT,
    type HelpOpener,
    type HelpRequest,
  } from "./lib/helpContext";
  import { manualUrl, place, resolve, splitKey, type HelpCorpus } from "./lib/help";
  import { isShortcutTarget, type Command } from "./lib/palette";
  import { cellText, type PeaksPayload } from "./lib/peaks";
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
  let corpus = $state<HelpCorpus | null>(null);
  let project = $state<any>(null);
  let recent = $state<any[]>([]);
  let examples = $state<any[]>([]);
  let openError = $state<string>("");

  let run = $state<RunState | null>(null);
  let result = $state<any>(null);
  let resultError = $state<string>("");
  let lines = $state<string[]>([]);
  let dropped = $state(0);
  let plotKey = $state(0);

  /** The nine panels, and the one that is showing.
   *
   * Model and Text joined the strip in WP-1034 — an edit and the fit it changes
   * are now one glance, which is what every other panel already had.  WP-1013
   * and WP-1014 had made both of them modes over the whole window on grounds
   * that were sound and are now **measured**: the atom table needs 472 px and
   * the `.rxt` document's editable columns 546 px, against a sidebar that
   * clamps at 560 and drags to 72 % of the window.  So they fit at the ceiling,
   * they do not fit at the 340 px floor, and the full-window layout below is
   * what covers the difference.
   *
   * `Series` is the ninth (WP-1016) and its label is one word for the reason
   * WP-1034 measured: eight already fill a 455 px strip, so a ninth costs a
   * second row at a narrow column and nothing else — the strip wraps rather than
   * shortening a label. It needs no mode of its own either: the header's
   * `Split | Full` already gives any panel the whole window. */
  const TABS = [
    { id: "params", label: "Parameters" },
    { id: "plan", label: "Plan" },
    { id: "peaks", label: "Peaks" },
    { id: "model", label: "Model" },
    { id: "text", label: "Text" },
    { id: "series", label: "Series" },
    { id: "report", label: "Report" },
    { id: "history", label: "History" },
    { id: "build", label: "Build" },
  ] as const;
  type Tab = (typeof TABS)[number]["id"];
  let tab = $state<Tab>("params");
  const modelTab = $derived(tab === "model");
  const textTab = $derived(tab === "text");
  const seriesTab = $derived(tab === "series");

  /** Whether the panel column has the whole window (WP-1034).
   *
   * The full-window surface WP-1013 and WP-1014 shipped, generalised: instead of
   * two panes each having their own mode, *the column* expands and its tab strip
   * comes with it — so the hatch covers every panel and "where am I" is still
   * read off one strip.  Session-local and unpersisted on purpose: it is a view
   * choice like the residual selector, not a setting like a width (WP-1033's
   * line between the two).
   *
   * One control for one choice (WP-1029): a segmented pair whose options *are*
   * the layout, rather than a toggle button that means two different things
   * depending on where you already are. */
  let wide = $state(false);
  const LAYOUTS: { id: boolean; label: string; title: string }[] = [
    { id: false, label: "Split", title: "the pattern beside the panel column" },
    { id: true, label: "Full",
      title: "the panel column across the whole window — the tabs stay with it" },
  ];
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
  let seriesPanel = $state<any>(null);
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
  /** streamed per-system graded shortlists (WP-1042/1045): every
   *  `consensus:<system>` stage_end of the run in flight, folded by the panel.
   *  Cleared on `index_start`, kept after the run ends — the anytime answer
   *  remains readable beside the final one. */
  let indexSnapshots = $state<Array<Record<string, any>>>([]);
  /** the last extinction screen — cleared whenever the candidates renumber,
   *  which the server enforces too (a new index run 409s the stale GET) */
  let extinction = $state<any>(null);
  /** the peak the pointer is over, wherever it is over it (WP-1032).  One index
   *  here rather than one per panel, because "which line is this" is a question
   *  about the session, and two copies would be two answers. */
  let hoveredPeak = $state<number | null>(null);
  /** Which candidate's predicted lines the plot draws (WP-1211).
   *
   *  Two indices, not one, because a preview and a selection are different
   *  claims: `pickedCandidate` is the row a person opened and `previewCandidate`
   *  the row the pointer happens to be over, which outranks it only while it
   *  lasts.  One collapsed index would make leaving a row un-select the cell
   *  underneath it. */
  let pickedCandidate = $state<number | null>(null);
  let previewCandidate = $state<number | null>(null);
  const shownCandidate = $derived(previewCandidate ?? pickedCandidate);
  /** Predicted positions per candidate index, fetched once each.
   *
   *  A cache and not a fetch-per-render because the preview above fires on
   *  every row the pointer crosses, and the answer is a pure function of a
   *  candidate that cannot change while it holds an index — so the map is
   *  dropped whole whenever a new answer renumbers them. */
  let candidateTicks = $state<Record<number, any>>({});
  const candidateOverlay = $derived.by(() => {
    const i = shownCandidate;
    const answer = i === null ? null : candidateTicks[i];
    if (i === null || !answer) return null;
    const cell = indexAnswer?.result?.candidates?.[i]?.cell;
    return {
      label: cell ? cellText(cell) : `candidate ${i}`,
      two_theta: answer.two_theta ?? [],
      n_total: answer.n_total ?? (answer.two_theta?.length ?? 0),
    };
  });
  /** Whether the *selection* has lines to show, which is what licenses clearing
   *  the plot to the data — not `pickedCandidate !== null` on its own.
   *
   *  A selection whose fetch is still in flight, or that the route refused
   *  (`INDEX_CELL_TOO_LARGE`, a lattice group gemmi will not build), would
   *  otherwise take the model curves off and put nothing in their place: the
   *  plot goes blank with no lines and no sentence saying why.  Keyed on the
   *  *picked* index and not on `candidateOverlay`, so a hover preview that
   *  fails cannot strobe the curves back on over a selection that is drawing. */
  const candidatePicked = $derived(
    pickedCandidate !== null && Boolean(candidateTicks[pickedCandidate]));
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
  /** The fit's own statistics, and the run frame's only *while it is running*.
   *
   * The frame is how a live Rwp reaches the header before a result exists — but
   * it outlives the result it described: an edit discards the curves server-side
   * (`refine.set_values`, "the fitted curve and statistics described the *old*
   * values"), and the header went on printing the last run's Rwp beside a plot
   * saying "No fitted curves yet".  Two panels contradicting each other, which
   * is precisely what putting the editor beside the plot makes visible (found in
   * WP-1034's browser pass). */
  const rwp = $derived(result?.statistics?.rwp ?? (busy ? run?.run?.rwp ?? null : null));
  const gof = $derived(result?.statistics?.gof ?? (busy ? run?.run?.gof ?? null : null));
  /** The report's own maturity gate, quoted rather than re-derived — see the
   *  header below and `GuiSession.result`. */
  const immature = $derived(Boolean(result?.maturity?.immature));
  // the head is the working state (WP-1005), so it is the one signal that says
  // "the table moved" whether a run, a checkout or an edit moved it
  const head = $derived(run?.head ?? project?.head ?? null);
  /**
   * A project with no phase cannot be refined (WP-1207), and every control that
   * would start one says so rather than offering a click whose only outcome is
   * a 400 — the wizard's `blocked()` rule, one panel up.
   */
  const noPhases = $derived(!!project && (project.n_phases ?? 1) === 0);
  const NO_PHASES_REASON =
    "This project has no phase yet. Pick peaks and index them, then adopt a cell.";

  function say(line: string) {
    lines = [...lines.slice(-400), line];
  }

  /** The `ui` keys this frontend owns, read back off the document it saved them
   *  to — one place, so a new key cannot be persisted and then never restored.
   *
   *  The theme is **not** among them and that is the point (WP-1044): these are
   *  facts about a project (it has four phases, so the table wants to be wide),
   *  and re-reading a theme per project is what made choosing dark last until
   *  the next `Open…`. It lives in `/api/settings`, loaded once at boot. */
  function readUi() {
    simple = project?.doc?.ui?.simple ?? true;
    consoleHeight = project?.doc?.ui?.console_height ?? 150;
    sideWidth = project?.doc?.ui?.side_width ?? null;
    modelColumns = project?.doc?.ui?.model_columns ?? null;
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
        await loadRecent();
        await loadExamples();
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
    tab = "params";
    indexAnswer = null;
    forgetCandidates();
    extinction = null;
    say(`# project: ${doc.path}`);
    run = await api.runState();
    await loadResult();
    await loadPeaks();
  }

  /** Open another project **in place of** this one (WP-1034).
   *
   * There is nothing to warn about and nothing to save: settings persist on the
   * verb and the history log is already on disk (WP-1005), so the session's
   * project is simply replaced — and a run in flight makes `project_open` 409
   * before any of this, which is where that rule belongs.  Returns the refusal
   * rather than only storing it, because the wizard's own list needs it beside
   * the button that was clicked; every `Project.open` refusal names a different
   * remedy, so it travels verbatim.
   */
  async function open(path: string): Promise<string> {
    try {
      project = await api.openProject(path);
      readUi();
      openError = "";
      tab = "params";
      indexAnswer = null;
      forgetCandidates();
      extinction = null;
      await loadResult();
      await loadPeaks();
      say(`project.open(${path})`);
      return "";
    } catch (error) {
      openError = (error as Error).message;
      return openError;
    }
  }

  /** The recent list, kept where both the empty state and the wizard read it. */
  async function loadRecent() {
    try {
      recent = (await api.recent()).recent ?? [];
    } catch {
      recent = [];   // an unreadable state directory is an empty list, not an error
    }
  }

  /** The examples this build ships (WP-1204), fetched beside the recent list.
   *
   * Same shape and the same reason: the shell owns the fetch because opening
   * one is the shell's verb.  A build with no examples is an empty list, not
   * an error — the section simply does not appear. */
  async function loadExamples() {
    try {
      examples = (await api.examples()).examples ?? [];
    } catch {
      examples = [];
    }
  }

  /** Open an example, building it on first use.
   *
   * Ends in the same document `openProject` returns, so it adopts through the
   * same path — an example is a project like any other from the moment it
   * exists.  Returns the refusal for the button that was clicked, as `open`
   * does, and refreshes the list because `built` has just changed. */
  async function openExample(name: string, reset = false): Promise<string> {
    try {
      const doc = reset ? await api.resetExample(name) : await api.openExample(name);
      await opened(doc);
      await loadExamples();
      say(`project.open("${doc.path}")  # ${name} example`);
      return "";
    } catch (error) {
      openError = (error as Error).message;
      return openError;
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
      forgetCandidates();
    } catch {
      // NO_INDEX_RESULT — nothing has run in this session; an empty state
    }
  }

  /** Which numbering `candidateTicks` is keyed to.  A plain `let`, not `$state`:
   *  nothing renders it, and a reactive one would make every fetch a reason to
   *  re-render the shell. */
  let candidateEra = 0;

  /** Drop everything keyed by candidate index (WP-1211).
   *
   *  Whole-map, never per entry: an index is only a name while one answer
   *  holds, so keeping any of it across a renumbering would draw one cell's
   *  lines under another cell's row.  The same staleness the server enforces on
   *  the extinction screen. */
  function forgetCandidates() {
    candidateEra += 1;
    candidateTicks = {};
    inFlightCandidates.clear();
    pickedCandidate = null;
    previewCandidate = null;
  }

  /** The indices a fetch is already out for.  The cache above only dedupes once
   *  an answer is *back*, and the route is a whole `generate_reflections`
   *  enumeration per emission line — so a pointer crossing a row twice before
   *  the first answer lands would ask for it twice.  A plain `Set`, not
   *  `$state`: nothing renders it. */
  const inFlightCandidates = new Set<number>();

  /**
   * Show one candidate's predicted lines, fetching them the first time.
   *
   * The fetch is by index and the answer is cached under it, because the
   * preview fires on every row the pointer crosses. A failure is *silent* here
   * and that is deliberate: this is a drawing, asked for by a hover, and the
   * one refusal it can meet (`INDEX_CELL_TOO_LARGE`) is already visible as the
   * absence of lines beside a cell whose own volume says why.
   *
   * **An answer that outlived its numbering is dropped**, which is the text
   * pane's stale-`seq` rule one panel over: an indexing run can finish while a
   * hover's fetch is in flight, and index 3 then names a different cell than
   * the one that was asked for. Silence is the right outcome — the row is gone
   * too.
   */
  async function showCandidate(index: number | null) {
    if (index === null || candidateTicks[index]
        || inFlightCandidates.has(index)) return;
    const era = candidateEra;
    inFlightCandidates.add(index);
    try {
      const answer = await api.candidateTicks(index);
      if (era === candidateEra) candidateTicks = { ...candidateTicks, [index]: answer };
    } catch {
      // no lines to draw; the row and the plot simply stay as they are
    } finally {
      if (era === candidateEra) inFlightCandidates.delete(index);
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
    // the document too, not only the curves: a move can add or remove the
    // project's last phase (Adopt, a structure replace, a checkout across
    // either), and `n_phases` is what disables Run (WP-1207)
    await loadProject();
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

  /** The app's own `ui` keys — the person's, not a project's (WP-1044).
   *
   *  Applied before it is sent, and a refusal costs the *persistence* rather
   *  than the choice: the state directory may be read-only (the server treats
   *  it the same way, `settings_patch`), and a theme that snapped back because
   *  a home directory is not writable would be a worse answer than a quiet one.
   */
  async function setTheme(next: ThemeChoice) {
    themeChoice = next;
    try {
      await api.patchSettings({ theme: next });
      say(`session.settings_patch({"ui": {"theme": ${JSON.stringify(next)}}})`);
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
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

  /** Show the import wizard, from anywhere — the header button, the palette.
   *
   * The wizard *is* `Model.svelte` (WP-1014), so reaching it is selecting that
   * tab and telling the pane to show it; the recent list rides inside it, which
   * is what makes "open another" reachable without restarting the program. */
  function startImport() {
    tab = "model";
    loadRecent();
    loadExamples();
    modelPanel?.startImport();
  }

  const commands = $derived<Command[]>([
    { id: "run", label: "Run the fit", echo: "ref.fit(data, plan=…)", key: "r",
      disabled: busy || !project || noPhases, run: start },
    { id: "stage", label: `Run one stage${planPanel?.selectedName() ? ` — ${planPanel.selectedName()}` : ""}`,
      echo: "ref.run_stage(stage)", key: ".", disabled: busy || !project || noPhases,
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
    { id: "series", label: "Refine a series of patterns",
      echo: "refine_sequential(patterns, structure, instrument, x=…)",
      disabled: !project || noPhases, run: () => (tab = "series") },
    { id: "report", label: "Show the fit report", echo: "ref.report()", key: "?",
      disabled: !project, run: () => (tab = "report") },
    { id: "history", label: "Show the history", echo: "ref.history.summary()", key: "h",
      disabled: !project, run: () => (tab = "history") },
    { id: "text", label: "Edit the project as text",
      echo: "print(rietx.gui.textdoc.render(project))", key: "t", disabled: !project,
      run: () => (tab = "text") },
    { id: "model", label: "Edit the structure and instrument",
      echo: "ref.edit(structure=…, instrument=…)", key: "m", disabled: !project,
      run: () => (tab = "model") },
    { id: "wide", label: wide ? "Show the pattern beside the panel" : "Give the panel the whole window",
      echo: "# a layout choice, not a setting", disabled: !project,
      run: () => (wide = !wide) },
    { id: "import", label: "Open or import a project", echo: "Project.create(path, …)",
      run: () => { tab = "model"; startImport(); } },
    { id: "disclosure", label: simple ? "Show advanced controls" : "Hide advanced controls",
      echo: 'project.doc.ui["simple"]', disabled: !project, run: () => setSimple(!simple) },
    // no `disabled`: the theme is the person's, so it is reachable in the empty
    // state too — which is the one screen a first-time user starts on
    { id: "theme", label: `Theme: ${themeChoice} — switch to ${nextTheme()}`,
      echo: 'session.settings_patch({"ui": {"theme": …}})',
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
    // help first: Esc means "close the thing that just opened", and cancelling
    // a run because a popover was open is not recoverable by pressing it again
    if (event.key === "Escape" && helpRequest) {
      closeHelp(true);
      return;
    }
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

  /* ---- the help popover (WP-1203) -------------------------------------
   *
   * One instance for the whole app, anchored to whichever `<Help>` term was
   * last activated.  One rather than one-per-term because two open
   * explanations is a state nobody asked for, and because the popover has to
   * escape every panel's `overflow: auto` — it is `position: fixed` in
   * viewport coordinates, which is exactly what `getBoundingClientRect`
   * returns and what `lib/help.ts:place` consumes.
   *
   * The size is *measured* rather than declared: the flip decision needs the
   * rendered height, and a max-width in CSS plus a paragraph of prose is not a
   * height anything here could compute.  The effect that measures runs after
   * the DOM update and before the browser paints, so the correction is not a
   * frame the eye can see; under jsdom every measurement is zero, which is why
   * the arithmetic is tested in `lib/help.test.ts` and not here. */
  let helpNode = $state<HTMLElement | null>(null);
  let helpRequest = $state<HelpRequest | null>(null);
  let helpAnchor = $state<DOMRect | null>(null);
  let popoverEl = $state<HTMLElement | null>(null);
  let popoverSize = $state({ width: 0, height: 0 });
  let viewport = $state({ width: 1024, height: 768 });

  const helpEntry = $derived(
    helpRequest?.key ? resolve(corpus, helpRequest.key) : null);
  const helpLink = $derived(manualUrl(corpus, helpEntry));
  const helpTitle = $derived(
    helpEntry?.title ?? helpRequest?.title ?? helpRequest?.key ?? "");
  const helpBody = $derived(helpEntry?.description ?? helpRequest?.text ?? "");
  /** the name behind a labelled term: a chip says `at bound`, and the flag it
   *  stands for is `position_at_bound`, which nothing else on screen shows
   *  (WP-1209) — so the popover carries it, and only where a label hid it:
   *  `excluded` labelled `excluded` hid nothing */
  const helpCode = $derived.by(() => {
    const name = helpRequest?.key ? splitKey(helpRequest.key)?.name ?? null : null;
    return helpEntry?.label && name && helpEntry.label !== name ? name : null;
  });
  const placement = $derived(helpAnchor
    ? place(helpAnchor, viewport, popoverSize)
    : { left: 0, top: 0, flipped: false });

  /** `refocus` is the caller's claim (Esc); holding focus is the popover's own.
   *
   *  A click away must not steal focus back from whatever was clicked, so the
   *  second test is `contains(activeElement)` rather than "was open": the only
   *  time closing owes the term its focus is when the popover had it, which
   *  since the popover takes focus on open is every keyboard route out. */
  function closeHelp(refocus = false) {
    const held = popoverEl?.contains(document.activeElement) === true;
    if (refocus || held) helpNode?.focus({ preventScroll: true });
    helpNode = null;
    helpRequest = null;
    helpAnchor = null;
    popoverSize = { width: 0, height: 0 };
    focusedFor = null;
  }

  setContext<HelpOpener>(HELP_CONTEXT, {
    isOpen: (node) => helpNode === node,
    toggle(node, request) {
      if (helpNode === node) {
        closeHelp();
        return;
      }
      helpNode = node;
      helpRequest = request;
      helpAnchor = node.getBoundingClientRect();
      popoverSize = { width: 0, height: 0 };
    },
  });

  $effect(() => {
    if (!popoverEl || !helpRequest) return;
    // the *rendered* body, not only the request: what `place` flips on is the
    // height, and the height is whatever is drawn.  Today that is the same
    // thing — `onMount` awaits `api.help()` before `loadProject`, so no term
    // exists until the corpus has landed or failed, and holding `/api/help`
    // for 15 s in a browser produced no term to click.  Declared here, that
    // boot order stops being load-bearing: a corpus arriving late would grow
    // the body under a height measured from "Not described yet.", and this
    // effect would re-measure rather than leaving `place` a stale number.
    void [helpTitle, helpBody, helpEntry, helpLink];
    const width = popoverEl.offsetWidth;
    const height = popoverEl.offsetHeight;
    if (width !== popoverSize.width || height !== popoverSize.height) {
      popoverSize = { width, height };
    }
  });

  /* The popover takes focus, because it is a `role="dialog"` and a dialog
   * nobody is in announces nothing: Tab from an activated term went to the next
   * input in the row, leaving the popover open behind the cursor and its
   * `in the manual →` link reachable only by tabbing the whole app.  Esc and a
   * second activation hand focus back to the term (`closeHelp`).
   *
   * `preventScroll` is load-bearing rather than tidy — `onscrollcapture` closes
   * the popover, so a focus that scrolled anything would close what it just
   * opened.  `focusedFor` is a plain `let`, not `$state`: it must not be a
   * dependency of the effect that writes it. */
  let focusedFor: HTMLElement | null = null;
  $effect(() => {
    if (!popoverEl || !helpNode) return;
    if (focusedFor === helpNode) return;
    focusedFor = helpNode;
    popoverEl.focus({ preventScroll: true });
  });

  // A resize or a scroll moves the anchor out from under the popover, and
  // there is nothing useful to do about it: re-measuring would chase a term
  // that may have left the screen entirely.  Closing is honest and costs one
  // click.
  function reanchor() {
    viewport = { width: window.innerWidth, height: window.innerHeight };
    if (helpRequest) closeHelp();
  }

  /** A click outside the popover and its own term closes it. */
  function clickAway(event: MouseEvent) {
    if (!helpRequest) return;
    const target = event.target as Node | null;
    if (target && (popoverEl?.contains(target) || helpNode?.contains(target))) return;
    closeHelp();
  }

  // "system" has to keep meaning system: a machine that switches at dusk must
  // take the app with it, which is only true if the query is *listened* to
  // rather than read once at boot
  onMount(() => {
    viewport = { width: window.innerWidth, height: window.innerHeight };
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
      // the corpus is static for the life of the build and needs no project,
      // so it is fetched once here beside capabilities.  A failure leaves it
      // null and every term says "not described yet": help is not a reason to
      // fail the boot.
      try {
        corpus = await api.help();
      } catch {
        corpus = null;
      }
      // the person's settings, before the project's: the theme is applied on
      // the first paint rather than after one in the wrong one (WP-1044)
      try {
        themeChoice = readChoice((await api.settings()).ui?.theme);
      } catch {
        // an unreadable store is the default choice, not a boot failure
      }
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
      (event: EngineEvent) => {
        say(consoleLine(event));
        // the streamed shortlist consumer (WP-1045): a completed system's
        // consensus snapshot is data on an existing kind, never a new one
        if (event.kind === "index_start") indexSnapshots = [];
        else if (event.kind === "stage_end" && event.data?.consensus)
          indexSnapshots = [...indexSnapshots, event.data];
      },
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
          } else if (frame.run.kind === "series") {
            // a series fits N patterns the project does not own: it moves no
            // curve of *this* project's and commits nothing to its tree, so the
            // outcome is the series panel's answer and nothing else here changes
            seriesPanel?.reload();
            tab = "series";
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

<svelte:window onkeydown={keydown} onclick={clickAway} onresize={reanchor}
  onscrollcapture={reanchor} />

<header>
  <div class="title">
    <strong>rietx</strong>
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
        <!-- WP-1201 moved this off a `<button>` (a chip states a fact and never
             acts), which put its message out of reach of the keyboard and of
             assistive tech.  `<Help text=…>` is that debt paid: the sentence is
             the *report's*, so no corpus can hold it, and it is now reachable
             by Tab and Enter like every other explanation. -->
        <span class="chip bad">
          <Help text={result.maturity.message} title="Not a fit yet"
            >⚠ not a fit yet</Help>
        </span>
      {/if}
    {/if}
  </div>

  <div class="controls">
    {#if project}
      <button class="ghost" onclick={startImport}
        title="open a recent project, or import a new one — this session's project
               is replaced, and nothing is unsaved (settings persist on the verb)"
        >Open…</button>
      <div class="segmented" role="group" aria-label="layout">
        {#each LAYOUTS as entry (entry.label)}
          <button class:on={wide === entry.id} onclick={() => (wide = entry.id)}
            title={entry.title}>{entry.label}</button>
        {/each}
      </div>
      <div class="segmented" role="group" aria-label="disclosure">
        <button class:on={simple} onclick={() => setSimple(true)}
          title="hide bounds, transforms and stage seeds">Simple</button>
        <button class:on={!simple} onclick={() => setSimple(false)}
          title="show every field a stage and a parameter carry">Advanced</button>
      </div>
    {/if}
    <!-- outside the `{#if project}` above, because a theme is not the
         project's (WP-1044): the empty state is a screen too, and it is the
         one a first-time user starts on -->
    <div class="segmented theme" role="group" aria-label="theme">
      {#each THEME_CHOICES as choice (choice)}
        <button class:on={themeChoice === choice} onclick={() => setTheme(choice)}
          aria-label={choice} title={THEME_TITLE[choice]}>{GLYPH[choice]}</button>
      {/each}
    </div>
    <span class="pill" data-state={run?.state ?? "idle"}>
      {#if busy}
        {run?.run.stage ?? "starting"}
        {#if run?.run.stage_index}({run.run.stage_index}/{run.run.n_stages}){/if}
      {:else}
        {run?.run.status ?? "idle"}
      {/if}
    </span>
    <button onclick={start} disabled={busy || !project || noPhases}
      title={noPhases ? NO_PHASES_REASON : null}>Run</button>
    <button class="ghost" onclick={cancel} disabled={!busy}>Cancel</button>
    <button class="ghost" onclick={() => (paletteOpen = true)} title="every command, with the call it makes">
      <kbd>⌘K</kbd>
    </button>
  </div>
</header>

<main bind:this={mainEl}>
  <!-- `Model` is mounted exactly once (WP-1205), whether or not a project is
       open — it used to sit in two separate branches of an `{#if project}`
       (the empty-state wizard and a tab panel), each its own component
       instance with its own `wizardOpen`. That let a project opened from
       *inside* the tab panel's wizard (`Open…` over an already-open project)
       leave the wizard painted over the freshly-opened project: `project`
       stayed truthy the whole time, so the tab-panel instance was never torn
       down and re-created, and nothing else ever cleared its `wizardOpen`.
       One instance removes the seam that bug lived in. Without a project the
       side column simply takes the whole window (`wide` reuses the
       full-window layout's own CSS) and no other panel exists to share it
       with. -->
  <div class="panes">
    <!-- hidden rather than unmounted in the full-window layout, for the same
         reason every panel is: a purge and a refetch on a layout click would
         throw the drawn window away -->
    {#if project}
      <div class="plotcol" class:hidden={wide}>
        <Plot {result} {plotKey} {zoom} {theme} error={resultError}
          peaks={peaksData} peaksActive={tab === "peaks"} hovered={hoveredPeak}
          candidate={candidateOverlay} {candidatePicked}
          {protocol} {extent} {channels} {protocolError} {busy}
          onhoverpeak={(i) => (hoveredPeak = i)}
          onaddpeak={addPeak} onmovepeak={movePeak} ontogglepeak={togglePeak}
          onremovepeak={removePeak} onprotocol={setProtocol} />
      </div>
    {/if}
    <div class="side" class:wide={wide || !project} bind:clientWidth={sideMeasured}
      style:flex={wide || !project || sideWidth === null ? null : `0 0 ${sideWidth}px`}>
      {#if project && !wide}
        <Splitter size={sideWidth ?? sideMeasured} grow="left" min={300} keep={360}
          extent={() => mainEl?.clientWidth ?? 0} onsize={sideSized}
          title="drag to resize the panel column" />
      {/if}
      {#if project}
        <!-- eight wide, and it **wraps** rather than truncating: measured at
             WP-1034 task 1, eight labels need 415 px squeezed and 533 px whole,
             against a column that clamps at 340 px on a narrow window.  A strip
             that hides a tab is worse than the mode buttons it replaced, so no
             label is ever shortened and the strip takes a second row instead. -->
        <nav class="tabs">
          {#each TABS as entry (entry.id)}
            <button class="tab" class:on={tab === entry.id} onclick={() => (tab = entry.id)}
              >{entry.label}</button>
          {/each}
        </nav>
      {/if}
      {#if !project && openError}<p class="bad">{openError}</p>{/if}
      <!-- the model pane and the text pane are tabs (WP-1034) and stay
           mounted like every other one: a typed species, a half-filled wizard
           and a typed `.rxt` buffer all have to survive a look at the plot.
           `active` is what keeps each from refetching on a head move it is
           not showing, and what builds the CodeMirror editor on first entry —
           and without a project, Model *is* the content, so it is always
           active and never hidden. -->
      <div class="panel" class:hidden={!!project && !modelTab}>
        <Model bind:this={modelPanel} {project} {capabilities} {head} {busy} {simple}
          {theme} {recent} {examples} {say} onexample={openExample}
          active={!project || modelTab} columns={modelColumns}
          oncolumns={modelSized} onopen={open} onopened={opened} onmoved={moved} />
      </div>
      {#if project}
        <!-- every tab stays mounted: switching must not throw away a filter, a
             pending edit, an unsaved stage list or a two-node comparison -->
        <div class="panel" class:hidden={tab !== "params"}>
          <Params bind:this={paramsPanel} {head} {busy} {simple} {say} />
        </div>
        <div class="panel" class:hidden={tab !== "plan"}>
          <Plan bind:this={planPanel} mode={project.doc.mode} {head} {busy} {simple}
            noPhasesReason={noPhases ? NO_PHASES_REASON : null}
            {say} onrun={runStage} onrunall={start} />
        </div>
        <div class="panel" class:hidden={!textTab}>
          <Text {head} {busy} active={textTab} dark={theme === "dark"} {say} onmoved={moved} />
        </div>
        <div class="panel" class:hidden={tab !== "peaks"}>
          <Peaks peaks={peaksData} {indexAnswer} {extinction} {run} {busy} {say}
            {capabilities} {corpus} doc={project?.doc ?? null}
            snapshots={indexSnapshots} onproject={loadProject}
            hovered={hoveredPeak} onhover={(i) => (hoveredPeak = i)}
            {shownCandidate}
            oncandidate={(i) => { pickedCandidate = i; showCandidate(i); }}
            oncandidatehover={(i) => { previewCandidate = i; showCandidate(i); }}
            onpeaks={(p) => (peaksData = p)}
            onindexed={(a) => { indexAnswer = a; forgetCandidates(); }}
            onzoom={(lo, hi) => (zoom = [lo, hi])} onmoved={moved} />
        </div>
        <div class="panel" class:hidden={!seriesTab}>
          <Series bind:this={seriesPanel} {project} {run} {busy} {simple} {theme}
            {say} active={seriesTab} />
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
      {/if}
    </div>
  </div>
</main>

{#if paletteOpen}
  <Palette {commands} onclose={() => (paletteOpen = false)} />
{/if}

<!-- The app's one help popover (WP-1203).  It lives here, outside every panel,
     because `position: fixed` inside a scrolling column would still be clipped
     by an ancestor that establishes a containing block, and because two open
     explanations is a state nobody asked for. -->
{#if helpRequest}
  <!-- `data-flipped` is the only way to tell a flip from a clamp that landed on
       the same pixel — a popover taller than the viewport is clamped to the top
       margin, which is exactly where flipping it would also put it — so it is
       what a browser pass reads to check the rule (WP-1203). -->
  <div class="popover" bind:this={popoverEl} role="dialog" aria-label={helpTitle}
       tabindex="-1" data-flipped={placement.flipped}
       style="left: {placement.left}px; top: {placement.top}px">
    <h2>{helpTitle}</h2>
    {#if helpBody}
      <p>{helpBody}</p>
    {:else}
      <!-- a key that resolves to nothing.  Saying so is the honest empty
           state: the corpus is where a description is owed, and inventing one
           here would put a wrong sentence under a real name. -->
      <p class="muted">Not described yet.</p>
    {/if}
    {#if helpEntry && (helpEntry.unit || helpEntry.default || helpEntry.typical
                       || helpEntry.modes?.length || helpCode)}
      <dl>
        {#if helpCode}<dt>Name</dt><dd class="mono">{helpCode}</dd>{/if}
        {#if helpEntry.unit}<dt>Unit</dt><dd>{helpEntry.unit}</dd>{/if}
        {#if helpEntry.default}<dt>Default</dt><dd class="mono">{helpEntry.default}</dd>{/if}
        {#if helpEntry.modes?.length}
          <dt>Modes</dt><dd class="mono">{helpEntry.modes.join(", ")}</dd>
        {/if}
        {#if helpEntry.typical}<dt>Typical</dt><dd>{helpEntry.typical}</dd>{/if}
      </dl>
    {/if}
    {#if helpLink}
      <a class="link" href={helpLink} target="_blank" rel="noreferrer noopener"
        >in the manual →</a>
    {/if}
  </div>
{/if}

<style>
  /* wraps rather than pushing a control off the window's edge — the tab strip's
     rule one rank up.  Measured at 860 px with a fitted project on screen:
     `Cancel` and `⌘K` were 118 px past the right edge and unreachable, because
     the row's only shrinkable item is the filename and it had already
     collapsed to nothing (WP-1034's browser pass). */
  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 14px;
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
  /* `flex-basis: 0`, not `auto`: with a wrapping header the basis is what
     decides whether the row breaks, and a long filename at its natural width
     would push the controls onto a second row while it still had room to
     ellipsise (measured — the header wrapped at 1200 px for nothing) */
  .project {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    flex: 1 1 0;
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

  .controls {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 0 0 auto;
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

  .plotcol {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .plotcol.hidden {
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

  /* the full-window layout: the column *is* the window, so neither the stored
     width nor the clamp that keeps a plot visible applies — there is no plot to
     keep visible, and the tab strip travels with it */
  .side.wide {
    flex: 1 1 auto;
    max-width: none;
    border-left: 0;
  }

  /* The overflow rule is: never shorten a label, wrap instead (WP-1034) —
     which is also why `.tab` does not grow to fill the row: with nine of them
     the strip wraps at a 340 px column, and a lone `Build` stretched across
     the second row read as a banner rather than as a tab. */
  .tabs {
    display: flex;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--line);
    flex: 0 0 auto;
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

  /* the `openError` shown above Model when there is no project yet — the
     side column used to be `.empty`'s own full-height flex box before the two
     `Model` mounts became one (WP-1205); `.side` already carries the same
     shape (`display: flex; flex-direction: column`). */
  .side > .bad {
    margin: 0.6rem 1.2rem 0;
  }
</style>
