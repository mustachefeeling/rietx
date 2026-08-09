<script lang="ts">
  /**
   * The model pane: an import wizard when there is no project, the structure and
   * instrument editors when there is.
   *
   * A **mode over the whole window**, not a sixth tab — WP-1013's argument, and
   * for the same reason one rank up: an atom table is eight columns wide and the
   * sidebar is `clamp(340px, 38%, 560px)`.  It is also the one pane that has to
   * work with *no project open at all*, which no tab can, so the empty state and
   * this panel are the same component rather than two that must agree.
   *
   * Every edit here goes one of two ways, and which one is not a taste:
   *
   * - **The parameter table owns what it has.**  A cell edge, an occupancy, a
   *   Biso, a profile term, a coordinate DOF — those are rows in `/api/params`,
   *   so they go through `PATCH /api/params`, where ties, locks, mode-fixing and
   *   bounds already live.  A cubic `b` refuses by naming the `a` it follows;
   *   that sentence is the verb's, and re-deriving it here would be a second copy
   *   of the crystal systems.
   * - **The model owns its shape.**  A species, a label, an atom added or
   *   removed, a geometry declared, a wavelength, a background family — none of
   *   those is a number in θ, and each changes what the parameter table
   *   *contains*.  They go as a whole validated model, against a **freshly read**
   *   one: a PATCH built from the model on screen would silently revert every
   *   field it did not touch (WP-1009's rule, third outing).
   *
   * Coordinates are never typed as x/y/z.  `x` is an affine tie onto `…dof.k`, so
   * the editor offers the DOFs the site symmetry allows and a violation is
   * *unrepresentable* rather than refused — and an atom whose site allows none
   * has no coordinate control at all, with the reason where the control would be.
   */
  import { ApiError, api } from "../api";
  import {
    applyFields,
    atomRows,
    axialWarning,
    clone,
    editableValue,
    fieldText,
    instrumentFields,
    newAtom,
    splitEdits,
    structureFields,
    withAtom,
    withoutAtom,
    type Field,
    type Site,
  } from "../lib/model";
  import {
    entryLines,
    noteTone,
    siteLines,
    symbolChanged,
    symmetryLine,
    wyckoffLabel,
    type PhaseSymmetry,
    type SiteLetter,
  } from "../lib/symmetry";
  import { editState, formatEsd, formatValue, normalize, type ParamRow } from "../lib/table";
  import {
    PRESET_FIELDS,
    PRESET_TITLES,
    blocked,
    createBody,
    emptyWizard,
    patternSummary,
    seedPreset,
    structureSummary, applyInstrumentHint, scanCount,} from "../lib/wizard";
  import { fitColumns, modelStacks } from "../lib/resize";
  import type { Theme } from "../lib/theme";
  import Splitter from "./Splitter.svelte";
  import Structure3D from "./Structure3D.svelte";

  let {
    project = null,
    capabilities = null,
    head = null,
    busy = false,
    simple = true,
    active = true,
    columns = null,
    recent = [],
    theme = "light",
    say = (_line: string) => {},
    onopen = async (_path: string) => "",
    onopened = (_doc: any) => {},
    oncolumns = (_widths: number[], _done: boolean) => {},
    onmoved = () => {},
  }: {
    project?: any;
    capabilities?: any;
    head?: string | null;
    busy?: boolean;
    simple?: boolean;
    active?: boolean;
    /** what `GET /api/recent` last answered — the shell owns the fetch, because
     *  opening one of these is the shell's verb (WP-1034) */
    recent?: any[];
    /** the first two columns' widths in px, or `null` while the flex defaults
     *  hold — the shell owns the `ui` key, this pane only reports drags */
    columns?: number[] | null;
    /** passed through to the 3D viewer, whose draw effect depends on it */
    theme?: Theme;
    say?: (line: string) => void;
    /** open a recent project; resolves to the refusal, or "" if it opened */
    onopen?: (path: string) => Promise<string>;
    onopened?: (doc: any) => void;
    oncolumns?: (widths: number[], done: boolean) => void;
    onmoved?: () => void;
  } = $props();

  /** The narrowest a form column may be, and what the 3D column must keep. */
  const COL_MIN = 200;
  const VIEW_KEEP = 260;

  /** The cell edges as crystallography writes them.  The *path* keeps the
   *  spelled-out name — it is a parameter path, and a glyph in one would be a
   *  second vocabulary for the same field. */
  const CELL_GLYPH: Record<string, string> = { alpha: "α", beta: "β", gamma: "γ" };

  // -- the three columns ---------------------------------------------
  /** what the drag has set, ahead of the round trip that persists it */
  let colLocal = $state<number[] | null>(null);
  let colMeasured = $state([0, 0]);
  let editorsEl: HTMLElement | undefined = $state();
  let editorsWidth = $state(0);
  /** One column, stacked, when three cannot each hold their floor (WP-1034).
   *
   * The pane is a tab now, so it is routinely rendered into 340-560 px — and
   * three columns there are not a squeeze but a *loss*: the atom table needs
   * 472 px and side-scrolls the whole column, cell row and headings included,
   * below it.  Stacked, everything keeps its width and the pane scrolls
   * vertically, which is what a narrow column can actually do.  The threshold
   * is arithmetic over the three floors (`lib/resize.ts`), not a taste. */
  const stacked = $derived(modelStacks(editorsWidth));
  /** Clamped at *render*, not only at drag: widths chosen in one window have to
   *  survive being reopened in a smaller one, and no drag is present to clamp
   *  them.  A browser found the alternative — a 3D column 24 px wide.  Stacked,
   *  a stored width means nothing: the columns are rows. */
  const cols = $derived(stacked
    ? null
    : fitColumns(colLocal ?? columns, editorsWidth, COL_MIN, VIEW_KEEP));

  /** The rendered width of column `i`, in px — its stored value if it has one,
   *  else whatever the flex default is currently producing. */
  function colWidth(i: number): number {
    return cols?.[i] ?? colMeasured[i] ?? 0;
  }

  function dragColumn(i: number, next: number, done: boolean) {
    const widths = [colWidth(0), colWidth(1)];
    widths[i] = next;
    colLocal = widths;
    oncolumns(widths, done);
  }

  // -- the wizard ----------------------------------------------------
  let wiz = $state(emptyWizard());
  let wizardOpen = $state(false);
  let staging = $state("");
  let wizError = $state("");
  /** a refused `Project.open`, in the verb's own words, beside the list that
   *  asked for it — separate from `wizError`, which is a *staging* failure: a
   *  verb's refusal and a panel's load error must not share one field (WP-1014) */
  let openError = $state("");
  const showWizard = $derived(!project || wizardOpen);
  const anodes = $derived<any[]>(capabilities?.anodes ?? []);
  const modes = $derived<string[]>(capabilities?.modes ?? ["rietveld"]);
  const plans = $derived<any[]>(capabilities?.plans ?? []);
  /** the reader-keyword vocabulary — a control per option the format declares,
   *  so a format that adds `scan` gets its picker with no change here */
  const readerOptions = $derived<any[]>(capabilities?.reader_options ?? []);
  const cannotCreate = $derived(blocked(wiz));

  async function stage(kind: "pattern" | "cif" | "instrument", event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    staging = kind;
    wizError = "";
    try {
      const options: Record<string, string> =
        kind === "cif" && wiz.aniso ? { aniso: "1" } : {};
      const preview = await api.uploadFile(kind, file, options);
      absorb(kind, preview);
    } catch (error) {
      // the reader's own complaint, with its line and column
      wizError = (error as Error).message;
    } finally {
      staging = "";
      input.value = "";   // so choosing the same file again re-stages it
    }
  }

  function absorb(kind: string, preview: any) {
    if (kind === "pattern") {
      wiz.pattern = preview;
      // the *effective* options, so a control cleared by a change of file shows
      // what this reader honoured rather than what the last one was asked for
      wiz.readerOptions = { ...(preview.reader_options ?? {}) };
      // what the file already knows about its instrument. Only on a *new* file:
      // re-reading for another scan must not undo what a person then typed
      if (preview.instrument_hint && preview.upload !== hintedUpload) {
        hintedUpload = preview.upload;
        wiz = applyInstrumentHint(wiz, preview.instrument_hint);
      }
      scanChoices = [];
      if (!wiz.path) wiz.path = preview.suggested_project;
      say(`read_pattern("${preview.filename}")  # ${preview.format.name}, `
        + `${preview.n_points} points`);
    } else if (kind === "cif") {
      wiz.structure = preview;
      say(`structure_from_cif("${preview.filename}", aniso=${preview.aniso ? "True" : "False"})`);
    } else {
      wiz.instrument = preview;
      say(`load_instrument_profile("${preview.filename}")`);
    }
  }

  /** Re-read a staged file with different options — no second upload. */
  /** The staged pattern's scans, labelled — empty until the picker is opened. */
  let scanChoices = $state<any[]>([]);
  /** which upload the instrument form was seeded from, so re-reading the same
   *  file for another scan does not overwrite what a person typed since */
  let hintedUpload = $state("");

  async function loadScans() {
    if (scanChoices.length || !wiz.pattern) return;
    try {
      scanChoices = (await api.patternScans(wiz.pattern.upload)).scans ?? [];
    } catch {
      scanChoices = [];        // the numbered fallback below is still a picker
    }
  }

  async function restage(kind: "pattern" | "cif", options: Record<string, string>) {
    const held = kind === "pattern" ? wiz.pattern : wiz.structure;
    if (!held) return;
    try {
      absorb(kind, await api.restage(kind, held.upload, options));
      wizError = "";
    } catch (error) {
      wizError = (error as Error).message;
    }
  }

  async function create() {
    wizError = "";
    try {
      const body = createBody(wiz);
      const doc = await api.newProject(body);
      say(`Project.create("${wiz.path}", pattern=…, structure=…, `
        + `instrument=${wiz.instrument ? "load_instrument_profile(…)"
                                       : `Instrument.${wiz.preset}(…)`})`);
      wizardOpen = false;
      wiz = emptyWizard();
      onopened(doc);
    } catch (error) {
      wizError = (error as Error).message;
    }
  }

  // -- the editors ---------------------------------------------------
  let structure = $state<any>(null);
  let sites = $state<Site[]>([]);
  /** `GET /api/structure`'s free arms: what each phase's symbol *is*, and which
   *  symmetry holds each held row.  Both ride on the route this pane already
   *  refetches, so neither costs a request. */
  let symmetry = $state<PhaseSymmetry[]>([]);
  let causes = $state<Record<string, string>>({});
  /** …and the tier that is *not* free: a spglib search per atom, so it is
   *  fetched when the user asks for it and dropped on every head move rather
   *  than reloaded (WP-1035). */
  let letters = $state<SiteLetter[]>([]);
  let lettersFor = $state<number | null>(null);
  let lettersBusy = $state(false);
  /** the symbol being typed, the preview it produced, and the verb's refusal —
   *  three separate fields for WP-1014's reason: a verb's refusal and a panel's
   *  load error must not share one.  `null` is *untouched* rather than empty, so
   *  deleting the field leaves it empty instead of springing back to the model's
   *  symbol mid-edit. */
  let symbolDraft = $state<string | null>(null);
  let symPreview = $state<any>(null);
  let symError = $state("");
  let symBusy = $state(false);
  let instrument = $state<any>(null);
  let rows = $state<ParamRow[]>([]);
  let phase = $state(0);
  /** typed text for model fields, keyed by the field's path in the model */
  let edits = $state(new Map<string, string>());
  /** typed text for raw parameter rows (the coordinate DOFs and the ADP patterns) */
  let pedits = $state(new Map<string, string>());
  /** The last verb's refusal.  Separate from `loadError` because they are
   *  different facts: found in a browser, an unknown species was refused with a
   *  400 and the message vanished, because `apply` reloads after a failure (the
   *  server may be half-ahead) and `load` cleared the one variable both used.
   *  Same shape as WP-1013's wiped squiggle — two answers sharing one field. */
  let error = $state("");
  let loadError = $state("");
  let note = $state("");
  let draft = $state({ label: "", species: "", x: "0", y: "0", z: "0" });
  /** The 3D view is a **third column of this pane**, not a sixth tab and not a
   *  window of its own: it answers questions about the rows beside it (is that
   *  ADP a balloon? did that coordinate DOF move the atom off its axis?), and a
   *  view you have to switch to in order to check an edit is a view nobody
   *  checks. Toggleable because a narrow window has room for two columns. */
  let viewer = $state(true);
  /** Bumped by every successful `load()`; the 3D view redraws on it. */
  let stamp = $state(0);

  const insFields = $derived(instrument ? instrumentFields(instrument) : []);
  const strFields = $derived(structure ? structureFields(structure) : []);
  const atoms = $derived(structure ? atomRows(structure, sites, rows, phase) : []);
  const insDelta = $derived(instrument
    ? splitEdits(instrument, insFields, edits, rows, "instrument")
    : null);
  const strDelta = $derived(structure
    ? splitEdits(structure, strFields, edits, rows, "structure")
    : null);
  const pending = $derived(editState(rows, pedits));
  const dirty = $derived((insDelta?.touched ?? 0) + (strDelta?.touched ?? 0)
    + pending.touched);
  const invalid = $derived([...(insDelta?.invalid ?? []), ...(strDelta?.invalid ?? []),
                            ...pending.invalid]);
  const warning = $derived(instrument ? axialWarning(instrument) : "");
  const byPath = $derived(new Map(rows.map((r) => [r.path, r])));
  const phaseSym = $derived<PhaseSymmetry | null>(symmetry[phase] ?? null);
  const symLine = $derived(symmetryLine(phaseSym));
  const symDirty = $derived(symbolChanged(symbolDraft ?? "",
    structure?.phases?.[phase]?.space_group ?? ""));

  /** A held row's tooltip: the verb's own `held_because`, and — where symmetry
   *  is the subject — the symmetry that is responsible.  Two sentences rather
   *  than one rewritten, because `held_because` is the parameter surface's
   *  wording and this pane may not restate it (WP-1011). */
  function why(path: string): string {
    const held = byPath.get(path)?.held_because ?? "";
    const cause = causes[path] ?? "";
    return [held, cause].filter(Boolean).join(" — ");
  }

  /** Reload on every head move — the head *is* the working state (WP-1005), and
   *  a run, a checkout, a text apply and a form edit all move it.  Only while
   *  shown: this panel is mounted whether or not it is the current mode, and
   *  three routes per head move for a pane nobody is looking at is waste.
   *
   *  `projectKey`, not `project`: a `ui`-only PATCH (a theme, a pane width)
   *  replaces the project *object* without moving the head, and reading the
   *  object here made every such write reload three routes and refetch the 3D
   *  geometry (WP-1029 q).  The *path* rather than a boolean, because the head
   *  cannot tell two projects apart — node ids are sequential (`n0000`), so
   *  two fresh projects share a head — and a switch must reload even when the
   *  heads collide.  (Today `App.opened()` also forces `mode = "panes"`, so a
   *  switch re-enters through `active` anyway; the key means this effect stays
   *  correct the day that side effect changes.) */
  const projectKey = $derived(project?.path ?? null);
  $effect(() => {
    void head;
    if (projectKey !== null && active) load();
  });

  async function load() {
    try {
      const [s, i, p] = await Promise.all([api.structure(), api.instrument(),
                                           api.params()]);
      structure = s.structure;
      sites = s.sites ?? [];
      symmetry = s.symmetry ?? [];
      causes = s.causes ?? {};
      instrument = i.instrument;
      rows = normalize(p.parameters);
      loadError = "";
      // the letters were measured against a model that has just been replaced;
      // re-asking would put a spglib search per atom on every head move, which
      // is the whole reason they are not on this route
      letters = [];
      lettersFor = null;
      symPreview = null;
      symbolDraft = null;
      // the signal the 3D view follows: this runs on every head move *and*
      // immediately after every local write, which is one frame earlier than
      // the head reaches the shell
      stamp += 1;
    } catch (exc) {
      if (!(exc instanceof ApiError && exc.empty)) loadError = (exc as Error).message;
    }
  }

  function type(path: string, text: string) {
    edits = new Map(edits).set(path, text);
  }

  function typeParam(path: string, text: string) {
    pedits = new Map(pedits).set(path, text);
  }

  function revert() {
    edits = new Map();
    pedits = new Map();
    error = "";
    note = "";
  }

  /** Send the delta: values through the parameter table, shape through the model.
   *
   * Values first — the same order `params_patch` uses, and the reason the model
   * read below is fresh rather than the one on screen. */
  async function apply() {
    if (invalid.length) return;
    error = note = "";   // a refusal must not read as the last success's note
    const values = { ...(insDelta?.values ?? {}), ...(strDelta?.values ?? {}),
                     ...pending.values };
    const moves: string[] = [];
    try {
      if (Object.keys(values).length) {
        await api.patchParams({ values });
        say(`ref.set_values({${Object.entries(values)
          .map(([k, v]) => `"${k}": ${v}`).join(", ")}})`);
        moves.push(`${Object.keys(values).length} value(s)`);
      }
      if (strDelta?.fields.length) {
        const fresh = (await api.structure()).structure;
        await api.patchStructure(applyFields(fresh, strDelta.fields, edits),
                                 "structure edited");
        say("ref.edit(structure=…)");
        moves.push(`${strDelta.fields.length} structure field(s)`);
      }
      if (insDelta?.fields.length) {
        const fresh = (await api.instrument()).instrument;
        await api.patchInstrument(applyFields(fresh, insDelta.fields, edits),
                                  "instrument edited");
        say("ref.edit(instrument=…)");
        moves.push(`${insDelta.fields.length} instrument field(s)`);
      }
      revert();
      note = moves.length ? `applied ${moves.join(" + ")}` : "";
      onmoved();
      await load();
    } catch (exc) {
      // a tied path, a locked one, a bound, or a run in flight — each has a
      // different fix, so the message travels intact
      error = exc instanceof ApiError && exc.busy
        ? "a run is in flight — the model is read-only until it ends"
        : (exc as Error).message;
      await load();
    }
  }

  // -- symmetry (WP-1035) --------------------------------------------
  /** Fetch the Wyckoff letters for the phase on screen, once, on request.
   *
   * The one route in this pane that is *not* refetched on a head move: it costs
   * a spglib search per atom, which is why it is a route of its own. */
  async function showLetters() {
    if (lettersFor === phase || lettersBusy) return;
    lettersBusy = true;
    try {
      const out = await api.symmetry(phase);
      letters = out.letters ?? [];
      lettersFor = phase;
      // the better sentences: the same causes, with the oriented site symmetry
      causes = out.causes ?? causes;
      say(`site_constraints(structure.phases[${phase}].space_group, xyz)  # per atom`);
      symError = "";
    } catch (exc) {
      symError = (exc as Error).message;
    } finally {
      lettersBusy = false;
    }
  }

  /** What the typed symbol would do — applying nothing. */
  async function previewSymbol() {
    symBusy = true;
    symError = "";
    try {
      symPreview = await api.symmetryPreview(phase, (symbolDraft ?? "").trim());
    } catch (exc) {
      symPreview = null;
      symError = (exc as Error).message;
    } finally {
      symBusy = false;
    }
  }

  /** …and apply it.  The server re-runs the same preview and gates on it, so
   *  this button is a convenience and never the check itself. */
  async function applySymbol() {
    symBusy = true;
    symError = "";
    try {
      const wanted = (symbolDraft ?? "").trim();
      await api.setSymmetry(phase, wanted);
      say(`structure.phases[${phase}].space_group = "${wanted}"  # ref.edit(structure=…)`);
      symbolDraft = null;
      symPreview = null;
      onmoved();
      await load();
    } catch (exc) {
      symError = (exc as Error).message;
    } finally {
      symBusy = false;
    }
  }

  /** A model change that is not a field: an atom added or removed. */
  async function patchStructure(next: any, label: string, echo: string) {
    try {
      await api.patchStructure(next, label);
      say(echo);
      error = "";
      onmoved();
      await load();
    } catch (exc) {
      error = (exc as Error).message;
    }
  }

  async function addAtom() {
    if (!draft.label.trim() || !draft.species.trim()) {
      error = "a new atom needs a label and a species";
      return;
    }
    const xyz = [draft.x, draft.y, draft.z].map(Number);
    if (xyz.some((v) => !Number.isFinite(v))) {
      error = "a new atom's position must be three numbers";
      return;
    }
    const atom = newAtom(draft.label.trim(), draft.species.trim(), xyz);
    await patchStructure(withAtom(structure, phase, atom), `added ${atom.label}`,
      `structure.phases[${phase}].atoms.append(Atom("${atom.label}", `
      + `"${atom.species}", ${xyz.join(", ")}))`);
    draft = { label: "", species: "", x: "0", y: "0", z: "0" };
  }

  async function removeAtom(index: number) {
    const label = structure.phases[phase].atoms[index].label;
    await patchStructure(withoutAtom(structure, phase, index), `removed ${label}`,
      `del structure.phases[${phase}].atoms[${index}]  # ${label}`);
  }

  async function toggleAniso(base: string, on: boolean) {
    try {
      await api.aniso(base, on);
      say(`# ${base}: aniso ${on ? "on — AnisoU.isotropic(Uiso, cell)" : "off — Biso from U_eq"}`);
      error = "";
      onmoved();
      await load();
    } catch (exc) {
      error = (exc as Error).message;
    }
  }

  /** The Chebyshev term count is a *shape* change, so it is not a Field. */
  async function setBackgroundTerms(n: number) {
    const next = clone(instrument);
    const current = next.background.coefficients as any[];
    if (n === current.length || n < 1) return;
    next.background.coefficients = n < current.length
      ? current.slice(0, n)
      : [...current, ...Array.from({ length: n - current.length }, () => ({ value: 0 }))];
    try {
      await api.patchInstrument(next, `background: ${n} terms`);
      say(`instrument.background = BackgroundChebyshev.with_terms(${n})`);
      error = "";
      onmoved();
      await load();
    } catch (exc) {
      error = (exc as Error).message;
    }
  }

  /** Replace the whole structure or instrument from a file, in one node. */
  async function replaceFrom(kind: "cif" | "instrument", event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    try {
      const preview = await api.uploadFile(kind, file);
      if (kind === "cif") {
        await api.patchStructure({ upload: preview.upload }, `structure from ${file.name}`);
        say(`ref.edit(structure=structure_from_cif("${file.name}"))`);
      } else {
        await api.patchInstrument({ upload: preview.upload }, `instrument from ${file.name}`);
        say(`ref.edit(instrument=load_instrument_profile("${file.name}"))`);
      }
      error = "";
      onmoved();
      await load();
    } catch (exc) {
      error = (exc as Error).message;
    } finally {
      input.value = "";
    }
  }

  /** A field's current text: what the user typed, else what the cell shows. */
  function text(model: any, field: Field, kind: "structure" | "instrument"): string {
    return edits.get(field.path) ?? fieldText(model, field, byPath, kind);
  }

  function heldReason(field: Field, kind: "structure" | "instrument"): string {
    const row = byPath.get(kind === "instrument" ? `instrument.${field.path}`
                                                 : field.path);
    return row?.held_because ?? "";
  }

  /** Open the wizard over an already-open project (the palette's entry). */
  export function startImport() {
    wizardOpen = true;
  }

  /** A preview curve as one SVG path — no plotly, no decimator, 900 points. */
  function sparkline(curve: any, width = 260, height = 34): string {
    const xs: number[] = curve?.two_theta ?? [];
    const ys: number[] = curve?.intensity ?? [];
    if (xs.length < 2) return "";
    const x0 = xs[0], x1 = xs[xs.length - 1];
    const lo = Math.min(...ys), hi = Math.max(...ys);
    const span = hi - lo || 1;
    return xs.map((x, i) => {
      const px = ((x - x0) / (x1 - x0 || 1)) * width;
      const py = height - ((ys[i] - lo) / span) * height;
      return `${i ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`;
    }).join(" ");
  }
</script>

<section class="model">
  <header>
    <h1>{showWizard ? "New project" : "Structure & instrument"}</h1>
    {#if !showWizard}
      <button class="ghost small" onclick={() => (wizardOpen = true)}>New project…</button>
    {:else if project}
      <button class="ghost small" onclick={() => (wizardOpen = false)}>Back to the project</button>
    {/if}
    <span class="spacer"></span>
    {#if !showWizard}
      <button class="ghost small" class:on={viewer} onclick={() => (viewer = !viewer)}
        title="the cell, the symmetry images, the bonds and the displacement
               ellipsoids — drawn from the model on screen">3D</button>
    {/if}
    {#if !showWizard && dirty > 0}
      <span class="muted small">{dirty} edit{dirty === 1 ? "" : "s"}</span>
      <button class="small" disabled={busy || invalid.length > 0} onclick={apply}>Apply</button>
      <button class="ghost small" onclick={revert}>Revert</button>
    {/if}
  </header>

  {#if showWizard}
    <!-- ---------------------------------------------------------- -->
    <div class="wizard">
      <!-- Opening an existing project belongs where making one is (WP-1034):
           the empty state used to carry the only recent list, so with a project
           open there was no route back to it short of restarting the program.
           Opening one **replaces** this session's project — settings persist on
           the verb and the history log is already on disk (WP-1005), so there is
           nothing unsaved to warn about, and a run in flight is refused by
           `project_open`'s own 409 rather than by a dialog here. -->
      {#if recent.length}
        <section class="recent">
          <h2>Open a recent project</h2>
          <ul>
            {#each recent as entry (entry.path)}
              <li>
                <button class="ghost small" disabled={busy}
                  onclick={async () => { openError = await onopen(entry.path); }}
                  >{entry.name}</button>
                <span class="muted mono tiny">{entry.path}</span>
              </li>
            {/each}
          </ul>
          {#if openError}<p class="bad tiny">{openError}</p>{/if}
          <p class="muted tiny">
            Opening one replaces the project in this session; nothing is unsaved.
          </p>
        </section>
      {/if}
      <ol class="steps">
        <li class:done={!!wiz.pattern}>
          <h2>1 · Pattern</h2>
          <label class="file">
            <input type="file" onchange={(e) => stage("pattern", e)} />
            <span>{staging === "pattern" ? "reading…" : "Choose a data file"}</span>
          </label>
          {#if wiz.pattern}
            <p class="summary mono">{patternSummary(wiz.pattern)}</p>
            <svg class="spark" viewBox="0 0 260 34" preserveAspectRatio="none"
              aria-label="pattern preview">
              <path d={sparkline(wiz.pattern.curve)} />
            </svg>
            <p class="muted tiny">
              claimed by <strong>{wiz.pattern.format.name}</strong> —
              {wiz.pattern.format.sniff}. σ: {wiz.pattern.format.sigma}
            </p>
            {#each readerOptions.filter((o: any) =>
                wiz.pattern.format.options.includes(o.name)) as opt (opt.name)}
              <label class="inline tiny">
                {opt.name}
                {#if opt.name === "scan" && scanCount(wiz.pattern) > 1}
                  <!-- a picker, not a number box: "scan 1" tells nobody which
                       measurement it is, which is why ScanInfo carries a label.
                       The labels cost a second walk of the ranges, so they are
                       fetched when this opens and the numbers stand in until -->
                  <select class="mono" value={wiz.readerOptions.scan ?? "0"}
                    onfocus={loadScans} onpointerdown={loadScans}
                    onchange={(e) => {
                      const v = (e.currentTarget as HTMLSelectElement).value;
                      wiz.readerOptions = { ...wiz.readerOptions, scan: v };
                      restage("pattern", Object.fromEntries(
                        Object.entries(wiz.readerOptions).filter(([, s]) => s !== "")));
                    }}>
                    {#each Array.from({ length: scanCount(wiz.pattern) }, (_, i) => i) as i (i)}
                      <option value={String(i)}>
                        {scanChoices[i]?.label ?? `scan ${i}`}
                      </option>
                    {/each}
                  </select>
                {:else}
                  <input class="mono" value={wiz.readerOptions[opt.name] ?? ""}
                    inputmode={opt.kind === "int" ? "numeric" : undefined}
                    onchange={(e) => {
                      const v = (e.currentTarget as HTMLInputElement).value.trim();
                      wiz.readerOptions = { ...wiz.readerOptions, [opt.name]: v };
                      restage("pattern", Object.fromEntries(
                        Object.entries(wiz.readerOptions).filter(([, s]) => s !== "")));
                    }} />
                {/if}
                <span class="muted">{opt.help}</span>
              </label>
            {/each}
            {#if wiz.pattern.instrument_hint}
              <p class="muted tiny">
                instrument seeded from the file —
                {wiz.pattern.instrument_hint.why}
              </p>
            {/if}
            <!-- what the reader repaired or assumed: a reversed scan, a dropped
                 duplicate, an option that did not apply. The wizard is where a
                 human should see a repair, before it becomes a project. -->
            {#each wiz.pattern.diagnostics ?? [] as note (note.code + note.message)}
              <p class="tiny {note.level === 'error' ? 'bad'
                            : note.level === 'warning' ? 'warn' : 'info'}">
                <span class="mono">{note.code}</span> {note.message}
              </p>
            {/each}
          {/if}
        </li>

        <li class:done={!!wiz.structure}>
          <h2>2 · Structure</h2>
          <label class="file">
            <input type="file" accept=".cif" onchange={(e) => stage("cif", e)} />
            <span>{staging === "cif" ? "reading…" : "Choose a CIF"}</span>
          </label>
          {#if wiz.structure}
            <p class="summary mono">{structureSummary(wiz.structure)}</p>
            <label class="inline tiny" title={wiz.structure.aniso_available
              ? "keeps the file's U^ij instead of collapsing them to U_eq"
              : "this file carries no _atom_site_aniso_U_ij loop"}>
              <input type="checkbox" checked={wiz.aniso}
                disabled={!wiz.structure.aniso_available}
                onchange={(e) => {
                  wiz.aniso = (e.currentTarget as HTMLInputElement).checked;
                  restage("cif", wiz.aniso ? { aniso: "1" } : {});
                }} />
              anisotropic ADPs
              <span class="muted">
                {#if wiz.structure.aniso_available}
                  the file has a loop — off by default, because reading a file must
                  not change what a plan frees
                {:else}
                  no aniso loop in this file{wiz.structure.aniso_error
                    ? ` (${wiz.structure.aniso_error})` : ""}
                {/if}
              </span>
            </label>
            {#if wiz.structure.unknown_species.length}
              <p class="bad tiny">
                {wiz.structure.unknown_species.length} atom(s) carry a species with no
                form factor here: {wiz.structure.unknown_species
                  .map((u: any) => `${u.label} (${u.species})`).join(", ")}
              </p>
            {/if}
          {/if}
        </li>

        <li class:done={!!wiz.instrument || wiz.preset !== ""}>
          <h2>3 · Instrument</h2>
          <p class="muted tiny">
            Required, and not defaulted: <code>Instrument</code> has no default
            source, and guessing an anode would put a wavelength nobody chose into
            every refined cell.
          </p>
          {#if wiz.instrument}
            <p class="summary mono">
              {wiz.instrument.filename} · {wiz.instrument.summary.geometry} ·
              λ {wiz.instrument.summary.wavelengths.join(", ")} Å · frozen
            </p>
            <button class="ghost small" onclick={() => (wiz.instrument = null)}>
              Use the form instead</button>
          {:else}
            <select value={wiz.preset} disabled={busy}
              onchange={(e) => (wiz = seedPreset(wiz,
                (e.currentTarget as HTMLSelectElement).value))}>
              {#each Object.keys(PRESET_FIELDS) as name (name)}
                <option value={name}>{PRESET_TITLES[name]}</option>
              {/each}
            </select>
            <div class="grid">
              {#each PRESET_FIELDS[wiz.preset] as field (field.name)}
                <label class="cell" title={field.title ?? ""}>
                  <span class="muted">{field.label}{field.unit ? ` (${field.unit})` : ""}</span>
                  {#if field.kind === "anode"}
                    <select class="mono"
                      value={wiz.values[field.name] ?? field.initial ?? ""}
                      onchange={(e) => (wiz.values[field.name] =
                        (e.currentTarget as HTMLSelectElement).value)}>
                      {#each anodes as anode (anode.name)}
                        <option value={anode.name}>
                          {anode.name} — {anode.wavelengths.map((w: number) => w.toFixed(5)).join(", ")} Å
                        </option>
                      {/each}
                    </select>
                  {:else}
                    <input class="mono" value={wiz.values[field.name] ?? ""}
                      placeholder={field.kind === "optnumber" ? "default" : ""}
                      oninput={(e) => (wiz.values[field.name] =
                        (e.currentTarget as HTMLInputElement).value)} />
                  {/if}
                </label>
              {/each}
            </div>
            <label class="file small">
              <input type="file" onchange={(e) => stage("instrument", e)} />
              <span>…or load a saved instrument profile</span>
            </label>
          {/if}
        </li>

        <li class:done={!!wiz.path}>
          <h2>4 · Project</h2>
          <label class="inline">
            <span class="muted tiny">directory</span>
            <input class="mono wide" bind:value={wiz.path}
              placeholder="/path/to/my_sample.pxrd" />
          </label>
          <div class="grid">
            <label class="cell"><span class="muted">mode</span>
              <select bind:value={wiz.mode}>
                {#each modes as m (m)}<option value={m}>{m}</option>{/each}
              </select>
            </label>
            <label class="cell"><span class="muted">plan</span>
              <select bind:value={wiz.plan}>
                {#each plans as p (p.name)}
                  <option value={p.name} title={p.when_to_use}>{p.title}</option>
                {/each}
              </select>
            </label>
          </div>
        </li>
      </ol>

      {#if wizError}<p class="bad">{wizError}</p>{/if}
      <div class="create">
        <button disabled={!!cannotCreate || busy} onclick={create}>Create project</button>
        <span class="muted small">{cannotCreate
          || "nothing is written until this — every file has already been read"}</span>
      </div>
    </div>
  {:else if structure && instrument}
    <!-- ---------------------------------------------------------- -->
    <div class="editors" class:stacked bind:this={editorsEl} bind:clientWidth={editorsWidth}>
      <div class="column structure" bind:clientWidth={colMeasured[0]}
        style:flex={cols ? `0 0 ${cols[0]}px` : null}>
        <h2>Structure
          <label class="file inline-file">
            <input type="file" accept=".cif" onchange={(e) => replaceFrom("cif", e)} />
            <span class="ghost small">Replace from CIF…</span>
          </label>
        </h2>
        {#if structure.phases.length > 1}
          <nav class="phases">
            {#each structure.phases as p, i (i)}
              <button class:on={phase === i} onclick={() => (phase = i)}>{p.name}</button>
            {/each}
          </nav>
        {/if}

        <div class="grid">
          <label class="cell"><span class="muted">name</span>
            <input class="mono" data-field="phases.{phase}.name"
              value={text(structure, { path: `phases.${phase}.name`,
              label: "phase", kind: "text" }, "structure")}
              oninput={(e) => type(`phases.${phase}.name`,
                (e.currentTarget as HTMLInputElement).value)} /></label>
        </div>

        <!-- Symmetry is not one read-only string any more (WP-1035): it is the
             one field whose *effects* fill the rest of this column, so it says
             what it is, what it holds, and what changing it would invalidate —
             before anything is applied. -->
        <div class="symmetry">
          <div class="symrow">
            <span class="muted tiny">space group</span>
            <input class="mono sym" data-field="phases.{phase}.space_group"
              value={symbolDraft ?? structure.phases[phase].space_group}
              title="the Hermann-Mauguin symbol or its IT number; a setting
                extension (:H, :R) is part of it"
              oninput={(e) => (symbolDraft =
                (e.currentTarget as HTMLInputElement).value)} />
            <button class="ghost tiny" disabled={!symDirty || symBusy || busy}
              onclick={previewSymbol}>Preview…</button>
          </div>
          <p class="muted tiny nowrapish">{symLine}</p>
          {#if phaseSym?.constraints}
            <p class="muted tiny">holds: {phaseSym.constraints}</p>
          {/if}
          {#if lettersFor !== phase}
            <button class="ghost tiny" disabled={lettersBusy}
              title="a symmetry search per atom — fetched on request, not on
                every head move"
              onclick={showLetters}>{lettersBusy
                ? "searching…" : "Wyckoff letters…"}</button>
          {/if}
          {#if symError}<p class="bad tiny">{symError}</p>{/if}

          {#if symPreview}
            <div class="preview" class:blocked={symPreview.blocked}>
              <p class="small">
                <strong class="mono">{symPreview.to?.xhm ?? "?"}</strong>
                {#if !symPreview.changed}
                  — the same setting; nothing would change.
                {:else if symPreview.blocked}
                  — this model cannot carry it:
                {:else}
                  — {symPreview.to?.constraints}
                {/if}
              </p>
              {#each symPreview.refusals as refusal (refusal.where)}
                <p class="bad tiny">{refusal.message}</p>
              {/each}
              {#each symPreview.notes as note2 (note2.kind + note2.where.join())}
                <p class="tiny {noteTone(note2.kind)}">{note2.message}</p>
              {/each}
              {#if !symPreview.blocked}
                {#each entryLines(symPreview.entries) as line (line)}
                  <p class="muted tiny">{line}</p>
                {/each}
                {#each siteLines(symPreview.sites) as line (line)}
                  <p class="muted tiny">{line}</p>
                {/each}
                {#if !entryLines(symPreview.entries).length
                     && !siteLines(symPreview.sites).length && symPreview.changed}
                  <p class="muted tiny">no parameter gains or loses a tie — the
                    reflection list is what moves.</p>
                {/if}
              {/if}
              <div class="symrow">
                <button disabled={symPreview.blocked || !symPreview.changed
                  || symBusy || busy} onclick={applySymbol}>Apply</button>
                <button class="ghost small"
                  onclick={() => { symPreview = null; symbolDraft = null; }}
                  >Discard</button>
              </div>
            </div>
          {/if}
        </div>

        <h3>Cell</h3>
        <!-- one row of six, because that is how a cell is written.  A
             wrap-when-it-must flex grid put it on three ragged rows at a 309 px
             column and hid the fact that α β γ are one family. -->
        <div class="cellrow">
          {#each ["a", "b", "c", "alpha", "beta", "gamma"] as edge (edge)}
            {@const path = `phases.${phase}.cell.${edge}`}
            {@const row = byPath.get(path)}
            {@const field = { path, label: edge, kind: "number" } as Field}
            <label class="cell" title={why(path)}>
              <span class="muted">{CELL_GLYPH[edge] ?? edge}</span>
              {#if !editableValue(row)}
                <span class="mono fixed">{formatValue(row!.value, row!.esd)}</span>
              {:else}
                <input class="mono" data-field={path}
                  value={text(structure, field, "structure")}
                  oninput={(e) => type(path, (e.currentTarget as HTMLInputElement).value)} />
              {/if}
              {#if row?.esd}<span class="muted tiny">{formatEsd(row.value, row.esd)}</span>{/if}
            </label>
          {/each}
        </div>

        <h3>Atoms <span class="muted tiny">{atoms.length}</span></h3>
        <!-- the table scrolls, not the column: its `min-content` is 448 px
             (WP-1034 task 1) and a column narrower than that used to take the
             cell row and the headings sideways with it -->
        <div class="tablewrap">
        <table class="atoms">
          <thead>
            <tr><th>label</th><th>species</th><th>x y z</th><th>occ</th><th>Biso</th>
              <th title="anisotropic ADPs, opt-in per atom">aniso</th><th></th></tr>
          </thead>
          <tbody>
            {#each atoms as row (row.base)}
              <tr>
                <td><input class="mono narrow" data-field="{row.base}.label"
                  value={text(structure,
                  { path: `${row.base}.label`, label: "label", kind: "text" }, "structure")}
                  oninput={(e) => type(`${row.base}.label`,
                    (e.currentTarget as HTMLInputElement).value)} /></td>
                <td><input class="mono narrow" data-field="{row.base}.species"
                  value={text(structure,
                  { path: `${row.base}.species`, label: "species", kind: "text" }, "structure")}
                  oninput={(e) => type(`${row.base}.species`,
                    (e.currentTarget as HTMLInputElement).value)} /></td>
                <td class="mono xyz" title={why(`${row.base}.x`)
                  || `${row.xyz.join(", ")} — ` + (row.frozen || "moved by the DOFs below")}>
                  {row.xyz.map((v) => v.toFixed(4)).join(" ")}
                  {#if wyckoffLabel(letters, row.base)}
                    <span class="wyckoff">{wyckoffLabel(letters, row.base)}</span>
                  {/if}
                </td>
                {#each [`${row.base}.occ`, `${row.base}.biso`] as path (path)}
                  {@const prow = byPath.get(path)}
                  {@const cell = { path, label: path, kind: "number" } as Field}
                  <td>
                    {#if !editableValue(prow)}
                      <span class="mono fixed" title={why(path)}
                        >{formatValue(prow!.value, prow!.esd)}</span>
                    {:else}
                      <input class="mono narrow" data-field={path}
                        value={text(structure, cell, "structure")}
                        oninput={(e) => type(path,
                          (e.currentTarget as HTMLInputElement).value)} />
                    {/if}
                  </td>
                {/each}
                <td><input type="checkbox" checked={row.site?.aniso ?? false}
                  disabled={busy}
                  onchange={(e) => toggleAniso(row.base,
                    (e.currentTarget as HTMLInputElement).checked)} /></td>
                <td><button class="ghost tiny" disabled={busy}
                  title="remove this atom" onclick={() => removeAtom(row.index)}>×</button></td>
              </tr>
              {#if row.frozen}
                <tr class="sub"><td colspan="7" class="muted tiny">{row.frozen}</td></tr>
              {:else if row.dofs.length}
                <tr class="sub"><td colspan="7">
                  <span class="sublabel">moves along</span>
                  <!-- a grid, not a wrapping row: a six-component pattern and a
                       one-component one are different widths, and letting them
                       find their own put the brackets and the boxes on
                       different rhythms -->
                  <div class="dofs">
                    {#each row.dofs as dof, k (dof.path)}
                      <label class="dof mono tiny" title={dof.path}>
                        <span class="pattern">[{(row.site?.dof_directions?.[k] ?? []).join(" ")}]</span>
                        <input class="mono narrow" data-field={dof.path}
                          value={pedits.get(dof.path)
                          ?? formatValue(dof.value, dof.esd)}
                          oninput={(e) => typeParam(dof.path,
                            (e.currentTarget as HTMLInputElement).value)} />
                      </label>
                    {/each}
                  </div>
                </td></tr>
              {/if}
              {#if row.adps.length}
                <tr class="sub"><td colspan="7">
                  <span class="sublabel">U<sup>ij</sup> patterns</span>
                  <div class="dofs wide-patterns">
                    {#each row.adps as adp, k (adp.path)}
                      <label class="dof mono tiny" title={adp.path}>
                        <span class="pattern">[{(row.site?.adp_patterns?.[k] ?? []).join(" ")}]</span>
                        <input class="mono narrow" data-field={adp.path}
                          value={pedits.get(adp.path)
                          ?? formatValue(adp.value, adp.esd)}
                          oninput={(e) => typeParam(adp.path,
                            (e.currentTarget as HTMLInputElement).value)} />
                      </label>
                    {/each}
                  </div>
                </td></tr>
              {/if}
            {/each}
          </tbody>
        </table>
        </div>

        <div class="add">
          <input class="mono narrow" placeholder="label" bind:value={draft.label} />
          <input class="mono narrow" placeholder="species" bind:value={draft.species} />
          <input class="mono narrow" placeholder="x" bind:value={draft.x} />
          <input class="mono narrow" placeholder="y" bind:value={draft.y} />
          <input class="mono narrow" placeholder="z" bind:value={draft.z} />
          <button class="ghost small" disabled={busy} onclick={addAtom}>Add atom</button>
        </div>
        <p class="muted tiny">
          A new atom's position decides its site symmetry, and therefore how many
          DOFs it gets — which is why it is typed here and moved by them afterwards.
        </p>
      </div>

      <!-- no grip between rows: stacked, a column's width is the pane's -->
      {#if !stacked}
        <Splitter size={colWidth(0)} grow="right" min={COL_MIN}
          keep={colWidth(1) + VIEW_KEEP} flow="inline"
          extent={() => editorsEl?.clientWidth ?? 0}
          onsize={(next, done) => dragColumn(0, next, done)}
          title="drag to resize the structure column" />
      {/if}

      <div class="column" bind:clientWidth={colMeasured[1]}
        style:flex={cols ? `0 0 ${cols[1]}px` : null}>
        <h2>Instrument
          <label class="file inline-file">
            <input type="file" onchange={(e) => replaceFrom("instrument", e)} />
            <span class="ghost small">Load profile…</span>
          </label>
        </h2>
        {#if warning}
          <p class="warn tiny">{warning} Nudge one if you free both — the guard
            reports the pair, and two solvers escape the corner in two
            unprincipled directions.</p>
        {/if}
        <div class="grid">
          {#each insFields as field (field.path)}
            {#if !field.advanced || !simple}
              {@const held = heldReason(field, "instrument")}
              <label class="cell" title={field.title ?? held}>
                <span class="muted">{field.label}{field.unit ? ` (${field.unit})` : ""}</span>
                {#if field.kind === "choice"}
                  <select class="mono" data-field={field.path}
                    value={text(instrument, field, "instrument")}
                    onchange={(e) => type(field.path,
                      (e.currentTarget as HTMLSelectElement).value)}>
                    {#each field.choices ?? [] as choice (choice)}
                      <option value={choice}>{choice}</option>
                    {/each}
                  </select>
                {:else if held && held.includes("structurally")}
                  <span class="mono fixed">{text(instrument, field, "instrument")}</span>
                {:else}
                  <input class="mono" data-field={field.path}
                    value={text(instrument, field, "instrument")}
                    placeholder={field.kind === "optnumber" ? "unset" : ""}
                    oninput={(e) => type(field.path,
                      (e.currentTarget as HTMLInputElement).value)} />
                {/if}
              </label>
            {/if}
          {/each}
        </div>

        <h3>Background</h3>
        <p class="muted tiny">
          {instrument.background.kind}
          {#if instrument.background.kind === "chebyshev"}
            — the coefficients themselves are parameters; the count is a shape
            change, so it lands as a model edit.
          {/if}
        </p>
        {#if instrument.background.kind === "chebyshev"}
          <label class="inline tiny">
            terms
            <input class="mono narrow" type="number" min="1" max="30"
              value={instrument.background.coefficients.length}
              onchange={(e) => setBackgroundTerms(
                Number((e.currentTarget as HTMLInputElement).value))} />
          </label>
        {/if}
      </div>

      {#if viewer}
        {#if !stacked}
          <Splitter size={colWidth(1)} grow="right" min={COL_MIN} keep={VIEW_KEEP}
            flow="inline"
            extent={() => (editorsEl?.clientWidth ?? 0) - colWidth(0)}
            onsize={(next, done) => dragColumn(1, next, done)}
            title="drag to resize the instrument column" />
        {/if}
        <!-- stacked, this is a section under the forms rather than a third of a
             400 px pane, and the header's `3D` button is its collapse control —
             one control for one choice (WP-1029), not a second one down here -->
        <div class="column view">
          {#if stacked}<h2>3D</h2>{/if}
          <Structure3D {stamp} {theme} {say} />
        </div>
      {/if}
    </div>

    <footer>
      {#if error}<p class="bad">{error}</p>{/if}
      {#if loadError}<p class="bad tiny">{loadError}</p>{/if}
      {#if invalid.length}
        <p class="bad tiny">{invalid.map((i) => `${i.path}: ${i.why}`).join(" · ")}</p>
      {/if}
      {#if note}<p class="muted tiny">{note}</p>{/if}
      {#if dirty > 0}
        <p class="muted tiny">
          {Object.keys({ ...(insDelta?.values ?? {}), ...(strDelta?.values ?? {}),
                         ...pending.values }).length} through
          <code>set_values</code> ·
          {(insDelta?.fields.length ?? 0) + (strDelta?.fields.length ?? 0)} as a
          model edit
        </p>
      {/if}
    </footer>
  {:else}
    <p class="muted">{loadError || "loading…"}</p>
  {/if}
</section>

<style>
  section.model {
    height: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }

  header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-bottom: 1px solid var(--line);
    flex: 0 0 auto;
  }

  .spacer {
    margin-left: auto;
  }

  h1 {
    font-size: 13px;
    margin: 0;
  }

  h2 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin: 10px 0 4px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  h3 {
    font-size: 11.5px;
    margin: 10px 0 3px;
    font-weight: 600;
  }

  .wizard {
    overflow: auto;
    padding: 10px clamp(12px, 6vw, 80px) 30px;
  }

  ol.steps {
    list-style: none;
    margin: 0;
    padding: 0;
    max-width: 90ch;
  }

  section.recent {
    max-width: 90ch;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--line);
  }

  section.recent ul {
    margin: 2px 0 4px;
    padding: 0;
    list-style: none;
  }

  section.recent li {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin: 2px 0;
    min-width: 0;
  }

  /* the path is the disambiguator and the name is the target: clip the path */
  section.recent li span {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  ol.steps li {
    border-left: 2px solid var(--line);
    padding: 0 0 10px 14px;
    margin: 0;
  }

  ol.steps li.done {
    border-left-color: var(--ok);
  }

  .summary {
    margin: 4px 0;
    font-size: 11.5px;
  }

  svg.spark {
    width: 100%;
    max-width: 520px;
    height: 34px;
    display: block;
  }

  svg.spark path {
    fill: none;
    stroke: var(--accent);
    stroke-width: 1;
    vector-effect: non-scaling-stroke;
  }

  .file input[type="file"] {
    display: none;
  }

  .file span {
    display: inline-block;
    border: 1px dashed var(--line);
    border-radius: 5px;
    padding: 4px 10px;
    cursor: pointer;
    font-size: 11.5px;
  }

  .file span:hover {
    border-color: var(--accent);
  }

  .inline-file {
    font-weight: 400;
  }

  .inline {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 4px 0;
    flex-wrap: wrap;
  }

  .create {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 14px;
    max-width: 90ch;
  }

  .editors {
    display: flex;
    gap: 0;
    overflow: hidden;
    flex: 1 1 auto;
    min-height: 0;
  }

  /* one column, stacked, below the width three floors need (`lib/resize.ts`).
     The pane scrolls once rather than each column scrolling separately, which
     is the difference between reading a form and hunting for it. */
  .editors.stacked {
    flex-direction: column;
    overflow: auto;
  }

  .editors.stacked > .column {
    flex: 0 0 auto;
    overflow: visible;
    border-left: 0;
  }

  .editors.stacked > .column + .column {
    border-top: 1px solid var(--line);
  }

  /* the scene needs a height of its own once it is a row: a 3D view in a
     `flex: 0 0 auto` row would otherwise be its content's height, which is zero */
  .editors.stacked > .column.view {
    height: 340px;
    padding-top: 8px;
  }

  /* Each column starts at **its own floor** and shares what is left over.
     Equal `flex: 1 1 0` shares looked fair and was not: at a 1000 px pane it
     gave the structure column 306 px against the 472 its atom table needs,
     while the two columns that needed less had more than enough (measured in a
     browser, WP-1034).  A basis is not a maximum — a drag still overrides both
     with `flex: 0 0 Npx` — and the 3D column keeps the 1.25 growth WP-1015 gave
     it, so free space still favours the only two-dimensional content here. */
  .column {
    flex: 1 1 200px;
    min-width: 0;
    overflow: auto;
    padding: 4px 12px 16px;
    position: relative;
  }

  .column.structure {
    flex-basis: 472px;
  }

  /* only where no splitter sits between them — the grip carries the rule
     itself, so a column next to one must not draw a second */
  .column + .column {
    border-left: 1px solid var(--line);
  }

  /* the viewer scrolls nothing: its plot fills the column and its controls sit
     under it, so an overflow here would scroll a 3D scene out of view */
  .column.view {
    overflow: hidden;
    display: flex;
    flex-direction: column;
    padding-bottom: 6px;
    /* a quarter more of the *free* space than the two form columns, because
       this is the only one whose content is two-dimensional: a form reads fine
       in a narrow column and a cell drawn in one is a cell drawn small */
    flex: 1.25 1 260px;
  }

  nav.phases {
    display: flex;
    gap: 4px;
    margin: 4px 0;
  }

  .grid {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 10px;
    margin: 2px 0;
  }

  .cell {
    display: flex;
    flex-direction: column;
    gap: 1px;
    font-size: 11.5px;
    min-width: 92px;
  }

  .cellrow {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 2px 6px;
    margin: 2px 0;
  }

  .cellrow .cell {
    min-width: 0;
  }

  .cellrow input,
  .cellrow .fixed {
    width: 100%;
  }

  input,
  select {
    font: inherit;
    font-size: 11.5px;
    border: 1px solid var(--line);
    background: var(--bg);
    color: inherit;
    border-radius: 3px;
    padding: 1px 4px;
    min-width: 0;
    max-width: 100%;
  }

  input:focus,
  select:focus {
    border-color: var(--accent);
    outline: none;
  }

  input.narrow {
    width: 72px;
  }

  input.wide {
    width: min(60ch, 100%);
  }

  .fixed {
    opacity: 0.65;
    padding: 1px 4px;
    border: 1px solid transparent;
  }

  .tablewrap {
    overflow-x: auto;
  }

  table.atoms {
    width: 100%;
    /* its own floor, so the wrapper scrolls it instead of the browser shrinking
       eight columns into an unreadable smear (measured: 448 px on NAC) */
    min-width: 448px;
    border-collapse: collapse;
    font-size: 11.5px;
  }

  table.atoms th {
    text-align: left;
    font-weight: 600;
    color: var(--muted);
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--line);
    padding: 2px 3px;
  }

  table.atoms td {
    padding: 1px 3px;
    vertical-align: middle;
  }

  /* the column is resizable now, so the fields follow it rather than a fixed
     72 px each summing past the column's own width */
  table.atoms input.narrow {
    width: 100%;
    min-width: 44px;
  }

  tr.sub td {
    padding-bottom: 4px;
    border-bottom: 1px solid var(--line);
  }

  .xyz {
    opacity: 0.7;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  /* the sub-rows' captions in the same register as the table's own headers —
     they used to be a plain muted span against uppercase tracked `th`s */
  .sublabel {
    display: block;
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    margin: 1px 0;
  }

  .sublabel sup {
    text-transform: none;
    letter-spacing: 0;
  }

  .dofs {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 2px 8px;
  }

  /* six components rather than three, so the bracket needs the room */
  .dofs.wide-patterns {
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  }

  label.dof {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
  }

  .dof .pattern {
    flex: 0 0 auto;
    color: var(--muted);
  }

  .dof input {
    flex: 1 1 auto;
    width: auto;
    min-width: 0;
  }

  .add {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    margin-top: 6px;
  }

  footer {
    flex: 0 0 auto;
    border-top: 1px solid var(--line);
    padding: 4px 12px;
  }

  footer p {
    margin: 2px 0;
  }

  .tiny {
    font-size: 11px;
  }

  .small {
    font-size: 11.5px;
  }

  .bad {
    color: var(--bad);
  }

  .warn {
    color: var(--warn);
  }

  /* an `info` note is a fact about the change, not a complaint about it — the
     third tone `noteTone` returns, and the reason the two above are not enough */
  .info {
    opacity: 0.75;
  }

  /* ---- symmetry (WP-1035) ----
     A block rather than a `.cell`, because it is a field *and* three lines of
     consequence, and at 340 px (the sidebar's floor) those do not sit beside a
     label.  Every paragraph in it wraps: WP-1034's rule is that overflow is
     wrap, never truncation, and a refusal that says "the nearest allowed
     tensor is …" is exactly the sentence that must not be cut. */
  .symmetry {
    margin: 4px 0 2px;
  }

  .symrow {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .symrow input.sym {
    flex: 1 1 96px;
    min-width: 84px;
  }

  .symmetry p {
    margin: 2px 0 0;
    /* the refusals carry six-component tensors; they have to be able to break */
    overflow-wrap: anywhere;
  }

  .nowrapish {
    /* the summary is one line where there is room and two where there is not —
       never a scrollbar, which is what `white-space: nowrap` would have made */
    line-height: 1.35;
  }

  .preview {
    margin-top: 5px;
    padding: 5px 6px;
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    border-radius: 3px;
    background: var(--surface, transparent);
  }

  .preview.blocked {
    border-left-color: var(--bad);
  }

  .preview .symrow {
    margin-top: 6px;
  }

  /* the letter rides in the coordinate cell rather than in a column of its own:
     the atom table's `min-content` is already 448 px (WP-1034 task 1) and a
     seventh column would take the whole column sideways at the sidebar's floor */
  .wyckoff {
    margin-left: 6px;
    opacity: 0.75;
    font-size: 10.5px;
  }
</style>
