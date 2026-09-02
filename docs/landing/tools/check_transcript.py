"""Leak check for data/transcript.json against the contributor's bundle.

usage: python tools/check_transcript.py <bundle dir> data/transcript.json

The prompt, the log lines and the closing report are cut by hand from the agent's run log, so
nothing generates them; this is the one step that proves the cut carries no pattern filename,
scan index, specimen tag, machine path or person before the page is built. The per-pattern
lines are not here: the page formats those from `demo.json`, which `build_demo.py` checks.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_demo import TRANSCRIPT_TOKENS, check_no_leak  # noqa: E402

bundle, path = Path(sys.argv[1]), Path(sys.argv[2])
text = path.read_text(encoding="utf-8")
doc = json.loads(text)
for key in ("agent", "model", "experiment", "prompt", "head", "marks", "report"):
    assert key in doc, f"transcript.json lacks {key!r}"
n_lines = len(doc["head"]) + sum(len(m["lines"]) for m in doc["marks"])
check_no_leak(text, bundle, TRANSCRIPT_TOKENS)
print(f"ok: {path.name}, {n_lines} log lines, {len(doc['report'])} report paragraphs, "
      f"{len(text)} chars, nothing from {bundle.name} in it")
