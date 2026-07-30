/** The CodeMirror 6 wiring — the one module that imports the editor.
 *
 * It is imported **dynamically** by `panels/Text.svelte`, which is what keeps
 * CodeMirror out of the boot path: `assets/app.js` stays the size WP-1010
 * measured, and `assets/vendor-cm.js` is fetched the first time someone opens
 * the text pane. Everything the pane actually decides lives in `lib/sync.ts`
 * (the state machine) and `lib/pxt.ts` (the colours); this file is the adapter
 * between them and CM's API, so it holds no rules of its own.
 *
 * `rectangularSelection` is the reason the `.pxt` format aligns its columns at
 * all (WP-1009 sized them per block after a fixed width made the renderer emit
 * `polarization 0.99min 0`), so it, `crosshairCursor` and multi-cursor are the
 * point of the pane rather than trimmings.
 *
 * The highlighter is a `StreamLanguage` over `lib/pxt.ts` with an explicit
 * `tokenTable`: no lezer grammar to build, no second parser to drift, and the
 * token names are this package's own rather than CM's legacy-mode vocabulary.
 */
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { HighlightStyle, StreamLanguage, syntaxHighlighting } from "@codemirror/language";
import { lintGutter, setDiagnostics, type Diagnostic } from "@codemirror/lint";
import { EditorState, type Extension } from "@codemirror/state";
import {
  EditorView,
  crosshairCursor,
  drawSelection,
  highlightActiveLine,
  highlightActiveLineGutter,
  highlightSpecialChars,
  keymap,
  lineNumbers,
  rectangularSelection,
} from "@codemirror/view";
import { tags, type Tag } from "@lezer/highlight";

import { spans, type Span, type Token } from "./pxt";
import { minimalChange, type Problem } from "./sync";

/** Our token names → lezer tags. Explicit, so renaming a token here is a
 *  type error rather than a silently uncoloured document. */
const TOKEN_TAGS: Record<Token, Tag> = {
  keyword: tags.keyword,
  vary: tags.atom,
  number: tags.number,
  string: tags.string,
  comment: tags.comment,
  annotation: tags.propertyName,
  flag: tags.modifier,
  operator: tags.operator,
  path: tags.variableName,
};

/** Colours as classes, not literals: `app.css` owns them and follows the theme. */
const HIGHLIGHT = HighlightStyle.define([
  { tag: tags.keyword, class: "tok-keyword" },
  { tag: tags.atom, class: "tok-vary" },
  { tag: tags.number, class: "tok-number" },
  { tag: tags.string, class: "tok-string" },
  { tag: tags.comment, class: "tok-comment" },
  { tag: tags.propertyName, class: "tok-annotation" },
  { tag: tags.modifier, class: "tok-flag" },
  { tag: tags.operator, class: "tok-operator" },
  { tag: tags.variableName, class: "tok-path" },
]);

interface StreamState {
  spans: Span[];
  at: number;
}

/**
 * `lib/pxt.ts`'s per-line spans, walked one token at a time.
 *
 * CM asks for tokens through a `StringStream`, so the whole line is classified
 * once at `sol()` and then handed back span by span. Gaps between spans advance
 * the stream with no style, which is how "the scanner has no opinion about this"
 * is expressed to CM.
 */
const pxtLanguage = StreamLanguage.define<StreamState>({
  name: "pxt",
  startState: () => ({ spans: [], at: 0 }),
  token(stream, state) {
    if (stream.sol()) {
      state.spans = spans(stream.string);
      state.at = 0;
    }
    while (state.at < state.spans.length && state.spans[state.at].to <= stream.pos) {
      state.at += 1;
    }
    const span = state.spans[state.at];
    if (!span) {
      stream.skipToEnd();
      return null;
    }
    if (stream.pos < span.from) {
      stream.pos = span.from;
      return null;
    }
    stream.pos = span.to;
    state.at += 1;
    return span.token;
  },
  tokenTable: TOKEN_TAGS,
});

export interface EditorHandle {
  /** Replace the document with a server rendering, keeping cursor and scroll. */
  setDoc(text: string): void;
  /** Paint the server's problems as lint diagnostics. */
  setProblems(problems: Problem[]): void;
  /** Put the caret on a line (1-based) and scroll it into view. */
  goToLine(line: number): void;
  /** Re-measure after the container was hidden and shown again. */
  refresh(): void;
  text(): string;
  focus(): void;
  destroy(): void;
}

export interface EditorOptions {
  parent: HTMLElement;
  doc: string;
  /** every user edit, already debounced by nobody — the pane owns the timer */
  onChange: (text: string) => void;
  /** Cmd/Ctrl-Enter */
  onApply: () => void;
  readOnly?: boolean;
}

export function createEditor(options: EditorOptions): EditorHandle {
  /** true while `setDoc` is writing, so its own transaction is not an edit */
  let echoing = false;
  const extensions: Extension[] = [
    lineNumbers(),
    highlightActiveLineGutter(),
    highlightActiveLine(),
    highlightSpecialChars(),
    history(),
    drawSelection(),
    // the jEdit-style column edit the format's aligned columns exist for
    rectangularSelection(),
    crosshairCursor(),
    lintGutter(),
    EditorState.allowMultipleSelections.of(true),
    pxtLanguage,
    syntaxHighlighting(HIGHLIGHT),
    keymap.of([
      { key: "Mod-Enter", preventDefault: true, run: () => (options.onApply(), true) },
      ...defaultKeymap,
      ...historyKeymap,
      indentWithTab,
    ]),
    EditorView.updateListener.of((update) => {
      // `setDoc` is the server's rendering arriving, not the user typing: without
      // this guard adopting a render would report itself back as an edit and the
      // pane would call every re-read a dirty buffer
      if (update.docChanged && !echoing) options.onChange(update.state.doc.toString());
    }),
    EditorState.readOnly.of(options.readOnly ?? false),
    EditorView.theme({
      "&": { height: "100%", fontSize: "12px" },
      ".cm-scroller": { fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace" },
    }),
  ];

  const view = new EditorView({
    state: EditorState.create({ doc: options.doc, extensions }),
    parent: options.parent,
  });

  return {
    setDoc(text: string) {
      const change = minimalChange(view.state.doc.toString(), text);
      if (!change) return;
      echoing = true;
      try {
        view.dispatch({ changes: change });
      } finally {
        echoing = false;
      }
    },
    setProblems(problems: Problem[]) {
      const doc = view.state.doc;
      const diagnostics: Diagnostic[] = problems.map((problem) => {
        // clamp: a server line number outside the buffer means the buffer moved
        // on, and a diagnostic that throws is worse than one on the wrong line
        const line = doc.line(Math.min(Math.max(problem.line, 1), doc.lines));
        return {
          from: line.from,
          to: line.to,
          severity: "error",
          message: problem.where ? `${problem.where}: ${problem.message}` : problem.message,
        };
      });
      view.dispatch(setDiagnostics(view.state, diagnostics));
    },
    goToLine(line: number) {
      const at = view.state.doc.line(Math.min(Math.max(line, 1), view.state.doc.lines));
      view.dispatch({ selection: { anchor: at.from }, scrollIntoView: true });
      view.focus();
    },
    refresh() {
      view.requestMeasure();
    },
    text: () => view.state.doc.toString(),
    focus: () => view.focus(),
    destroy: () => view.destroy(),
  };
}
