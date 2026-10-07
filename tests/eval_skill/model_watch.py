"""Name any Haiku or Sonnet model ID the models page lists and this suite has not seen.

    python tests/eval_skill/model_watch.py

WP-1907. The skill eval runs on demand (`.github/workflows/skill-eval.yml`),
and a new agent model is the event that should start one, so
`.github/workflows/model-watch.yml` runs this weekly and opens an issue when it
names a new ID. Stdlib only, so the job needs no install and no credential.

It prints every ID the page lists, then each one missing from
``models_seen.txt``. Under Actions it also writes them to ``$GITHUB_OUTPUT`` as
``new``. **A page that yields no ID exits 1**: a moved or rewritten page would
otherwise read as "nothing new" every week, and the reminder would be dead
without anything saying so.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE = "https://docs.claude.com/en/docs/about-claude/models/overview"
SEEN = HERE / "models_seen.txt"
#: The two agent models the suite runs (PROTOCOL.md § Models, N).
ID = re.compile(r"claude-(?:haiku|sonnet)(?:-[a-z0-9]+)*")
#: Words the page glues onto an ID that are not part of it: a system card's
#: link, and Bedrock's version suffix (read off the page 2026-10-07).
NOISE = re.compile(r"-(?:system-card|v\d+)$")


def model_ids(html: str) -> set[str]:
    """Every Haiku or Sonnet ID in ``html``, noise suffixes dropped."""
    return {NOISE.sub("", m) for m in ID.findall(html)}


def seen_ids(text: str) -> set[str]:
    """``models_seen.txt``: one ID a line, ``#`` comments and blanks ignored."""
    return {line.split("#", 1)[0].strip() for line in text.splitlines()} - {""}


def new_ids(found: set[str], seen: set[str]) -> list[str]:
    return sorted(found - seen)


def fetch(url: str = PAGE) -> str:
    # The page answers urllib's own User-Agent with 403 (2026-10-07).
    req = urllib.request.Request(url, headers={"User-Agent": "rietx-model-watch"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main(page: str | None = None) -> int:
    """``page`` stands in for the fetched HTML, which is how the tests run it."""
    found = model_ids(fetch() if page is None else page)
    if not found:
        print(f"no Haiku or Sonnet model ID found on {PAGE}: the page moved or "
              "changed shape, so this watch can see nothing", file=sys.stderr)
        return 1
    new = new_ids(found, seen_ids(SEEN.read_text(encoding="utf-8")))
    print("listed: " + " ".join(sorted(found)))
    print("new: " + (" ".join(new) if new else "none"))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8", newline="\n") as out:
            out.write(f"new={' '.join(new)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
