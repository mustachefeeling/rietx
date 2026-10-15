"""Write the stub pages each spike tree needs for its six tabs."""
import sys
from pathlib import Path

root = Path(sys.argv[1])
stubs = {
    "start.md": ("Start", "Install rietx and run your first fit."),
    "concepts.md": ("Concepts", "How a fit works, what the parameters mean and how to read a report."),
    "reference.md": ("Reference", "The API, the parameter map, the files, the CLI and the diagnostics."),
    "switching.md": ("Switching", "rietx at a glance for users of TOPAS, GSAS-II and FullProf."),
    "guides/index.md": ("Guides", "Step-by-step answers to one task each."),
    "theory/index.md": ("Theory", "The physics and mathematics behind each model term, with its sources."),
}
toc = {"guides/index.md": ["calibrate"], "theory/index.md": ["profiles"]}
myst = len(sys.argv) > 2 and sys.argv[2] == "myst"
for rel, (title, answer) in stubs.items():
    body = f"# {title}\n\n{answer}\n"
    if rel in toc and not myst:
        body += "\n```{toctree}\n" + "\n".join(toc[rel]) + "\n```\n"
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(body, encoding="utf-8")
