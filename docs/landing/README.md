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
| `build_demo.py` | `python build_demo.py <bundle dir> data/demo.json 2` — the animation payload from the contributor's `curves.npz` + `metadata.csv`, decimated by the third argument (**always 2** for the committed file; see § The payload below). Refuses to write if any filename, scan index or specimen token from the bundle reaches the output |
| `data/transcript.json` | what the pane shows around the log: `prompt` (the run's prompt, cut to a few lines), `head` (the stdout before the series), `marks` (lines that land on a given frame: the chunk boundaries, the finalise summary), `report` (the agent's closing words, cut) and `note`. Cuts are marked `[…]`, file names and paths are bracketed stand-ins. `python tools/check_transcript.py <bundle dir> data/transcript.json` refuses any pattern filename, scan index, specimen tag, machine path or person from the bundle |
| `data/demo.json` | the built payload, **committed**, 0.99 MB: 275 × 649 obs and calc as base64 Int16, weight fractions, the gas/temperature programme. Each frame carries `t` (the file's clock, s) and `tm` (the plotted clock, min: the six pauses of 18–58 min between scans count as one 74 s interval; `pauses` lists them). Phases carry `name`, `html` and `support`; the three support phases are named `support 1`–`3` rather than by formula: `build_demo.phase_columns` takes their columns from the bundle's own header, in header order, so their names are in neither the payload nor the builder — and deliberately not in `build.LEAK` either, since a denylist publishes what it denies. Segments carry the atmosphere text and a colour `key` (`n2`, `h2`, `air`). `decimation` and `steps_per_fwhm` record the redaction. No filenames |
| `img/` | `fap-light/dark.png` from `examples/fap_lab.py`; `gui-history-light/dark.png`, the GUI at 1440×900 @2x with 24 nodes in 3 lanes |
| `tools/gui_shots.js` | builds the three-lane history in a running GUI (`rietx gui --port 8799 --no-open --state-dir …`, then `POST /api/examples/open {"name":"fap"}`) and screenshots it. Needs `playwright-core` and the cached Chromium; run from any directory with `PWC=<node_modules/playwright-core> OUT=<dir> node gui_shots.js` |
| `tools/page_shots.js` | full-page screenshots of the built page in both themes at a given width |
| `tools/check_transcript.py` | the leak check for the transcript; `build.py` runs the same token list over the whole page |
| `tools/rig_shots.js` | screenshots of the animation rig alone, both themes, at chosen frames (`FRAMES=120,274`) — the quickest check after a change to the panels |

## The agent pane

Nothing is outstanding here; both items below are in.

1. **The agent's run** (`data/transcript.json`, from the 2026-09-03 bundle's `agent_transcripts/`, the run that built the animation bundle: Claude Sonnet 5 under Claude Code, 2026-09-01, 2 h 7 min, 289 assistant messages, 154 tool calls). The pane pins the prompt at the top and streams the run log underneath, one line per pattern, in step with the panels: the page formats those lines from `demo.json` (index, temperature, atmosphere, status, Rwp — the run's own record of each fit), and `transcript.json` supplies everything around them. A gas or temperature step opens a marker; a non-converged fit is orange; the closing report arrives with the last pattern, and the loop holds ~6 s there before restarting. To re-cut it: pick messages by index from the JSONL, keep the text verbatim, mark cuts `[…]`, replace file names with `[pattern n]` (n = `series_index` from `metadata.csv`), paths with `[raw-data directory]` and people with a role, then run `tools/check_transcript.py`.

2. **The model name** in the rig header comes from `transcript.json`'s `model` field, today `Claude Sonnet 5`. With the file absent the header reads "model to confirm" instead, which is what a checkout without the payload shows.

## How it is built and served

`.github/workflows/pages.yml` runs `python docs/landing/build.py --site`, then
builds the manual with `html_extra_path = ["../landing/site"]` and
`root_doc = "manual"`. The landing page lands at `/`, the manual at
`/manual.html`, and no other URL moved. Everything the page needs is in the
repository, so a fork builds the whole thing with no secret and no fetch.

- `docs/manual/conf.py` adds `html_extra_path` only when `docs/landing/site`
  exists: `-W` makes a missing entry an error, and `tests/test_manual.py` builds
  the manual on every run.
- `dist/`, `site/` and `preview.html` are gitignored — one page built three ways.
  `data/` is **not**, and § The payload says why.
- The fluorapatite example is `examples/fap_lab.py`, with `fluorapatite.cif`
  beside it, so `tests/test_examples.py` runs it and the manual can
  `literalinclude` it.
- `rietx._about.DOCS_URL` stays `https://rietx.org`, and `help.py`'s anchors are
  `page.html#id`, so neither moved.

## The payload

`data/demo.json` is in the repository because it is **decimated to every second
measured channel**. At the acquisition's own 0.0501° step the file would be a
copy of a contributor's unpublished in-situ series; at 0.1002° it sits at 2.38
steps across a peak, against the 5-to-10 rietx itself asks for, so it is a figure
of that series and not the series. `tests/test_landing.py` asserts that rather
than trusting it. The page itself does not say so: its caption carries the
credit and nothing else, so `decimation` and `steps_per_fwhm` in the payload,
and this section, are where the redaction is on the record.

**Decimated, not averaged, and the difference matters.** A mean of *k* channels
divides the counting noise by √*k*: the observed cloud tightens onto the
calculated curve and the difference curve flattens, so the panel shows a better
fit than the Rwp printed beside it. Measured at k = 2 and k = 3 by rendering
both. Keeping every *k*-th channel keeps each point a real measured channel,
noise and all; what it costs is peak *shape*, the calculated line growing spikier
as apexes fall between retained channels.

Everything else the fence covers is unchanged: no filename, scan index, specimen
token, path or person from the bundle reaches either file, `build.py`'s `leaks()`
and `tools/check_transcript.py` enforce it case-insensitively, and the bundle's
own files (`curves.npz`, `metadata.csv`, plots, logs, `agent_transcripts/`) stay
out of the repository entirely.

## Sources behind the page's numbers

- Fluorapatite: GSAS-II tutorials `LabData` (`tests/data/README.md`); GSAS's converged values from `FAP.EXP`; the CuKa preset wavelengths are Hölzer et al. 1997 (`schemas/instrument.py`, ref 7d). Cell +60 ppm = 1.5405929/1.5405.
- Validation rows: `docs/VALIDATION.md` (generated from `tests/validation_matrix.py`), quoted verbatim from its "Measured" lines.
- Animation: the contributor's bundle README and `metadata.csv`; the atmosphere tokens decode as `1N2atm` = N₂, `2H2mixatm` = 0.2 vol % H₂ in N₂ at 1 L/min, `3airatm` = air (the leading digit is a gas-step counter; the bundle's 2026-09-03 rebuild states this, correcting its first release and the maintainer's own 5 % reading); 272/275 converged; the run reported PHASE_UNCONSTRAINED on the third support phase in every pattern (bundle README caveat 2, and the campaign report).
