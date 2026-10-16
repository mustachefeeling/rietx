# About the project

A rietx project is a directory ending in `.rex` that holds the pattern file, the settings for the next fit, and the full history of the model.
The [project directory](../reference/project.md) page lists every file in one.

## Why a directory

Every change to the model is appended to a file as it happens.
A crash leaves every earlier line intact, and a viewer can follow a running fit by reading the log.
A zip archive would have to be rewritten on every save.

## What each file is for

Each fact has one file, and no value is stored twice.

| File | Holds | Written by |
|---|---|---|
| the pattern file, under its own name | the measurement, copied byte for byte | `Project.create`, once |
| `project.json` | the settings for the next fit: the plan, the mode, the angular limits, the excluded regions, and the GUI's own settings | `Project.save` and the GUI |
| `history.jsonl` | every state of the model, one node a line | every fit and every edit, as it happens |
| `peaks.json` | the peak list from the peak picker in the GUI (`rietx gui`) | the GUI |
| `live/` | one directory for each recorded fit, which `rietx watch` shows live | each fit |
| `exports/` | CIFs, reflection tables and other exports | the GUI's export commands |

The parameter values live only in the history.
Its last node is the working state, so the history exists from `Project.create` onward and the model is never unsaved.
`Project.save` writes only `project.json`, the settings.

The settings say what the next fit will use, and a history node says what a past fit used.
So the selected plan lives in `project.json`, and each stage node records the stage it ran.

## The pattern and how it was read

The project keeps the pattern file itself, with the file's own esd column.
`project.json` records which reader opened it and with which options.
That matters because one file can hold several patterns: a pdCIF with a measured and a calculated block, or a vendor file with several scans.

`project.json` also records two fingerprints: one of the file's bytes, and one of the angles and intensities the reader produced.
`Project.open` compares both, refuses a mismatch in either, and says which:

- a changed fingerprint of the bytes means the file was edited after the project was made;
- matching bytes with a changed fingerprint of the data mean this version of rietx reads the file differently, and the file itself is intact.

## Excluded regions

Excluded regions are angular ranges the fit skips, such as a sample-holder peak.
They are settings, so they live in `project.json`, and a history node does not record them.
An interval whose start is above its end is refused, not reordered.
Outside a project, set `PatternData.excluded_regions` on the pattern instead.

## Opening a project changes it

`Project.open` resumes at the last history node and appends a line to the history saying so.
No way to open a project is read-only.
To look at one without changing it, run `rietx gui my_sample.rex --scratch`, which works on a copy in a temporary directory.
To share a project, copy the whole directory.
