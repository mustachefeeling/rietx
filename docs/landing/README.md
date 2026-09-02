# rietx.org landing page

The page served at `https://rietx.org/`, beside the manual at `/manual.html`.
Written 2026-09-02 with Claude Code; entered the repository in WP-1331.
`python build.py` writes `dist/index.html`, the whole page in one file, which is
also what the mockup artifact shows.

## What is here

| path | what |
|---|---|
| `src/index.html` | the page: markup, CSS, JS. The one source. Placeholders `%%IMG:…%%`, `%%DEMO%%`, `%%TRANSCRIPT%%`, `%%FAVICON%%` |
| `src/favicon.svg` | the manual's favicon recoloured to the accent (`#d8660c` light, `#ff9d4d` dark) |
| `build.py` | `python build.py` → `dist/index.html` (everything inlined); `python build.py --site` → `site/` with `img/`, `data/`, `favicon.svg` |
| `build_demo.py` | `python build_demo.py <bundle dir> data/demo.json` — the animation payload from the contributor's `curves.npz` + `metadata.csv`. Refuses to write if any filename, scan index or specimen token from the bundle reaches the output |
| `data/transcript.json` | what the pane shows around the log: `prompt` (the brief, cut to a few lines), `head` (the stdout before the series), `marks` (lines that land on a given frame: the chunk boundaries, the finalise summary), `report` (the agent's closing words, cut) and `note`. Cuts are marked `[…]`, file names and paths are bracketed stand-ins. `python tools/check_transcript.py <bundle dir> data/transcript.json` refuses any pattern filename, scan index, specimen tag, machine path or person from the bundle |
| `data/demo.json` | the built payload, 1.9 MB: 275 × 1297 obs and calc as base64 Int16, weight fractions, the gas/temperature programme. Each frame carries `t` (the file's clock, s) and `tm` (the plotted clock, min: the six pauses of 18–58 min between scans count as one 74 s interval; `pauses` lists them). Phases carry `determined` and `support`; segments carry the atmosphere text and a colour `key` (`n2`, `h2`, `air`). No filenames |
| `img/` | `fap-light/dark.png` from `examples/fap_lab.py`; `gui-history-light/dark.png`, the GUI at 1440×900 @2x with 24 nodes in 3 lanes |
| `tools/gui_shots.js` | builds the three-lane history in a running GUI (`rietx gui --port 8799 --no-open --state-dir …`, then `POST /api/examples/open {"name":"fap"}`) and screenshots it. Needs `playwright-core` and the cached Chromium; run from any directory with `PWC=<node_modules/playwright-core> OUT=<dir> node gui_shots.js` |
| `tools/page_shots.js` | full-page screenshots of the built page in both themes at a given width |
| `tools/check_transcript.py` | the leak check for the transcript; `build.py` runs the same token list over the whole page |
| `tools/rig_shots.js` | screenshots of the animation rig alone, both themes, at chosen frames (`FRAMES=120,274`) — the quickest check after a change to the panels |

## What is still missing

1. **The agent's run** is in (`data/transcript.json`, from the 2026-09-03 bundle's `agent_transcripts/`, the run that built the animation bundle: Claude Sonnet 5 under Claude Code, 2026-09-01, 2 h 7 min, 289 assistant messages, 154 tool calls). The pane pins the brief at the top and streams the run log underneath, one line per pattern, in step with the panels: the page formats those lines from `demo.json` (index, temperature, atmosphere, status, Rwp — the run's own record of each fit), and `transcript.json` supplies everything around them. A gas or temperature step opens a marker; a non-converged fit is orange; the closing report arrives with the last pattern, and the loop holds ~6 s there before restarting. To re-cut it: pick messages by index from the JSONL, keep the text verbatim, mark cuts `[…]`, replace file names with `[pattern n]` (n = `series_index` from `metadata.csv`), paths with `[raw-data directory]` and people with a role, then run `tools/check_transcript.py`.

2. **The model name** in the rig header comes from `transcript.json` ("model to confirm" while the file is absent).

## How it is built and served

`.github/workflows/pages.yml` fetches `data/` from the private payload
repository, runs `python docs/landing/build.py --site`, then builds the manual
with `html_extra_path = ["../landing/site"]` and `root_doc = "manual"`. The
landing page lands at `/`, the manual at `/manual.html`, and no other URL moved.

- **The payload does not enter this repository.** `data/demo.json` is a
  contributor's observed series at full resolution and `data/transcript.json` is
  their agent run; the bundle's own files stay out too. `data/`, `site/`,
  `dist/` and `preview.html` are gitignored and `tests/test_landing.py` asserts
  that, in both directions. A public release asset would not do: release assets
  are public.
- Without `data/`, the page renders its pending state and the build still
  passes, so a fork builds.
- `docs/manual/conf.py` adds `html_extra_path` only when `docs/landing/site`
  exists: `-W` makes a missing entry an error, and `tests/test_manual.py` builds
  the manual on every run.
- The fluorapatite example is `examples/fap_lab.py`, with `fluorapatite.cif`
  beside it, so `tests/test_examples.py` runs it and the manual can
  `literalinclude` it.
- `rietx._about.DOCS_URL` stays `https://rietx.org`, and `help.py`'s anchors are
  `page.html#id`, so neither moved.

## Sources behind the page's numbers

- Fluorapatite: GSAS-II tutorials `LabData` (`tests/data/README.md`); GSAS's converged values from `FAP.EXP`; the CuKa preset wavelengths are Hölzer et al. 1997 (`schemas/instrument.py`, ref 7d). Cell +60 ppm = 1.5405929/1.5405.
- Validation rows: `docs/VALIDATION.md` (generated from `tests/validation_matrix.py`), quoted verbatim from its "Measured" lines.
- Animation: the contributor's bundle README and `metadata.csv`; the atmosphere tokens decode as `1N2atm` = N₂, `2H2mixatm` = 0.2 vol % H₂ in N₂ at 1 L/min, `3airatm` = air (the leading digit is a gas-step counter; the bundle's 2026-09-03 rebuild states this, correcting its first release and the maintainer's own 5 % reading); 272/275 converged; the run reported PHASE_UNCONSTRAINED on the third support phase in every pattern (bundle README caveat 2, and the campaign report).
