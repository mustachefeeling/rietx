"""WP-1504's harness: real agents draw six structure figures, before and after 1501-1503.

    python docs/wp/1504-eval/run.py --menu                  # the costed menu
    python docs/wp/1504-eval/run.py check                   # the protocol and the shim
    python docs/wp/1504-eval/run.py prepare ROOT CONDITION  # a condition's tree and venv
    python docs/wp/1504-eval/run.py go ROOT RUN [RUN ...]   # launch, collect, judge
    python docs/wp/1504-eval/run.py launch|collect|judge ROOT RUN
    python docs/wp/1504-eval/run.py judge-references ROOT   # the judge, checked first
    python docs/wp/1504-eval/run.py table                   # the handover's table

A **run** is ``<task>-<condition>-<model>-<repeat>``, e.g. ``rutile-after-opus-1``.
``PROTOCOL.md`` is the registered round, and quotes every prompt and criterion
in this file; ``check`` holds the two copies together.

**The condition is the venv, never the prompt.**  ``prepare`` exports the
condition's commit to ``ROOT/trees/<condition>`` and installs it, not editable,
into ``ROOT/venvs/<condition>`` with ``fig_trace.py`` booted by a ``.pth``.  A
run's workspace holds the task's CIF and the skill that venv's ``rietx skill``
installs, and nothing else.  ``ROOT`` must sit outside every checkout, or each
run would inherit that checkout's ``CLAUDE.md`` and skills
(``tests/eval_agent_surface/runner.py``'s ``check_no_inherited_context``).

**What is ours and what is committed.**  ``ROOT`` keeps the full figures, the
venvs and the transcripts.  ``runs/<run>/`` here keeps the score, the run's
rows of the trace, the trail and the final figure at most ``THUMB`` px a side.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
REPO = HARNESS.parents[2]
RECORD = HARNESS / "runs"
PHASES = REPO / "tests" / "data" / "polyhedra_phases.json"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

#: The two trees.  ``before`` is WP-1470's merge: ``render_structure`` and the
#: dict, no cut, no extent, no report.  ``after`` is WP-1503's merge, the last
#: commit to touch the figure surface when the round was registered.
COMMITS = {
    "before": "5304b85ab092f629a0392b43966df8fda76563dd",
    "after": "97c1d9cc1344a73983fe2e1f2a6d287761e29d13",
}
#: What the wheel build reads, and nothing else: the tree an agent can find is
#: the package and its skill, never the tests or the planning documents.
TREE_PATHS = ("pyproject.toml", "README.md", "LICENSE", "LICENSE-3RD-PARTY.md",
              "src", "docs/skill")

MODELS = {"sonnet": "sonnet", "opus": "opus"}
REPEATS = 3
JUDGE_MODEL = "opus"
#: A runaway guard, never a budget the round is sized to: several times the
#: dearest figure run the prior allows.
MAX_BUDGET_USD = "12"
JUDGE_BUDGET_USD = "2"
#: The hosted manual is today's in both conditions, so neither gets it.
DISALLOWED = ("WebFetch", "WebSearch")
#: PROTOCOL.md § Amendment 1.1: the user-level skills stay out of a run.  A run
#: carries the version it was launched under, and only runs of this one pool.
PROTOCOL_VERSION = "1.1"
SETTING_SOURCES = "project,local"
THUMB = 800

PREAMBLE = ("rietx is installed for the python interpreter {python}. "
            "Your working directory is {workspace}.")

#: task -> the fixture row, the CIF's file name, the prompt, the criteria.
TASKS = {
    "rutile": dict(
        phase="rutile TiO2", cif="rutile.cif",
        prompt=("rutile.cif is rutile, TiO₂. Draw me its chains of edge-sharing "
                "TiO₆ octahedra, looking down c. Save the picture as figure.png."),
        criteria=(
            "Ti–O octahedra are drawn as polyhedra.",
            "The view is down c: the unit-cell outline is a square.",
            "Octahedra stand at more than one chain position in the cell, such as "
            "its corners and its centre.",
        )),
    "gypsum": dict(
        phase="gypsum CaSO4.2H2O", cif="gypsum.cif",
        prompt=("gypsum.cif is gypsum, CaSO₄·2H₂O. Draw one layer of the structure "
                "with its water molecules, seen edge-on. Save the picture as "
                "figure.png."),
        criteria=(
            "Exactly one layer is shown: the Ca and SO₄ make one band, not two or "
            "more stacked bands.",
            "Water is shown on the layer: O atoms each bonded to two H atoms.",
            "The layer is seen edge-on: it runs across the picture as a band, not "
            "face-on as a sheet.",
        )),
    "calcite": dict(
        phase="calcite CaCO3", cif="calcite.cif",
        prompt=("calcite.cif is calcite, CaCO₃. Draw only the carbonate groups: "
                "no calcium and no polyhedra. Save the picture as figure.png."),
        criteria=(
            "No Ca atoms are drawn.",
            "No polyhedra are drawn.",
            "Carbonate groups are drawn: each C bonded to three O in a triangle.",
        )),
    "nac": dict(
        phase="NAC", cif="nac.cif",
        prompt=("nac.cif is Na₂Ca₃Al₂F₁₄ (NAC). Draw its AlF₆ octahedra as a "
                "2×2×1 block of unit cells. Save the picture as figure.png."),
        criteria=(
            "Al–F octahedra are drawn as polyhedra.",
            "The picture covers two unit cells along a, two along b and one along "
            "c: not a single cell, and not a larger block.",
        )),
    "lab6": dict(
        phase="LaB6", cif="lab6.cif",
        prompt=("lab6.cif is LaB₆. Draw its B₆ octahedra without the La–B bonds. "
                "Save the picture as figure.png."),
        criteria=(
            "B₆ octahedra are visible: six B atoms bonded to each other, or drawn "
            "as an octahedral polyhedron.",
            "No bonds join La atoms to B atoms.",
        )),
    "fap": dict(
        phase="fluorapatite", cif="fluorapatite.cif",
        prompt=("fluorapatite.cif is fluorapatite, Ca₅(PO₄)₃F. I need a figure for "
                "print looking down c, 17 cm wide at 300 dpi, with a legend saying "
                "which colour is which atom. Save it as figure.png."),
        criteria=(
            "The view is down c: the cell outline is a rhombus with a 120° angle, "
            "and the channels along c are seen end-on.",
            "A legend names the atom types beside the colour each is drawn in.",
            "The legend's colours match the colours of the atoms in the picture.",
        )),
}
#: Asked of every figure, after the task's own criteria.
COMMON = ("The figure is not cut off: no atom or polyhedron is clipped by the "
          "frame's edge.",)

JUDGE = """\
You are scoring a figure that an AI agent drew for a chemist. The chemist asked:

> {prompt}

The figure is figure.png in the current directory. Read it with the Read tool and \
look at it. Read nothing else. Judge it against each criterion below. Answer yes, \
no or unclear, with one short sentence saying what you saw. Judge only the \
criteria: do not reward effort or penalise style.

{criteria}

Reply with only a JSON object, no prose around it:
{{"criteria": [{{"n": 1, "verdict": "yes", "saw": "..."}}, ...]}}"""

#: 17 cm at 300 dpi is 2007.9 px; either rounding is the agent's to make.
FAP_WIDTH = (2005, 2011)
FAP_DPI = (299.0, 301.0)

#: The menu's prior, until runs of this round replace it.  Round 1.1's cells
#: (WP-1307) were 17-35 min refinements at $1.44-3.42 on Sonnet and
#: $4.43-8.55 on Opus; a figure is a shorter job, so the prior is a third of
#: the cheapest to the cheapest of each, and the pilot is what replaces it.
PRIOR_USD = {"sonnet": (0.5, 1.9), "opus": (1.5, 4.4)}
PRIOR_MINUTES = (3.0, 12.0)
JUDGE_PRIOR_USD = (0.05, 0.30)


def runs() -> list[str]:
    return [f"{t}-{c}-{m}-{r}" for t in TASKS for c in COMMITS for m in MODELS
            for r in range(1, REPEATS + 1)]


def split(run: str) -> tuple[str, str, str, int]:
    parts = run.split("-")
    if (len(parts) != 4 or parts[0] not in TASKS or parts[1] not in COMMITS
            or parts[2] not in MODELS or not parts[3].isdigit()):
        raise SystemExit(f"unknown run {run!r}: <{'|'.join(TASKS)}>-"
                         f"<{'|'.join(COMMITS)}>-<{'|'.join(MODELS)}>-<n>")
    return parts[0], parts[1], parts[2], int(parts[3])


def paths(root: Path, run: str) -> dict[str, Path]:
    _, condition, _, _ = split(run)
    return {
        "workspace": root / "work" / run,
        "python": root / "venvs" / condition / "bin" / "python",
        "rietx": root / "venvs" / condition / "bin" / "rietx",
        "log": root / "logs" / f"{condition}.jsonl",
        "launch": root / "launches" / f"{run}.json",
        "judge": root / "judge" / run,
        "record": RECORD / run,
    }


def _run(*args: str, **kw) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, capture_output=True, text=True, **kw)
    if proc.returncode != 0:
        raise SystemExit(f"{args[0]} failed: {proc.stderr.strip()[:2000]}")
    return proc


# --- the inputs --------------------------------------------------------------

def phase_row(task: str) -> dict:
    rows = json.loads(PHASES.read_text(encoding="utf-8"))
    name = TASKS[task]["phase"]
    return next(r for r in rows if r["name"] == name)


def cif_text(task: str) -> str:
    """A plain CIF of the fixture row, the same bytes for both conditions.

    Written here rather than by either tree's ``to_cif``, so the input cannot
    differ between the conditions it is meant to hold equal.
    """
    row = phase_row(task)
    a, b, c, alpha, beta, gamma = row["cell"]
    symbol = row["space_group"].split(":")[0]
    lines = [f"# {row['name']}, from {row['source']} via tests/data/polyhedra_phases.json",
             f"data_{TASKS[task]['cif'].removesuffix('.cif')}",
             f"_cell_length_a {a}", f"_cell_length_b {b}", f"_cell_length_c {c}",
             f"_cell_angle_alpha {alpha}", f"_cell_angle_beta {beta}",
             f"_cell_angle_gamma {gamma}",
             f"_symmetry_space_group_name_H-M '{symbol}'", "",
             "loop_", "_atom_site_label", "_atom_site_type_symbol",
             "_atom_site_fract_x", "_atom_site_fract_y", "_atom_site_fract_z",
             "_atom_site_occupancy"]
    lines += [f"{label} {species} {x} {y} {z} {occ}"
              for label, species, x, y, z, occ in row["atoms"]]
    return "\n".join(lines) + "\n"


def prompt_for(root: Path, run: str) -> str:
    task = split(run)[0]
    p = paths(root, run)
    return (TASKS[task]["prompt"] + "\n\n"
            + PREAMBLE.format(python=p["python"], workspace=p["workspace"]))


# --- prepare -------------------------------------------------------------------

#: Run by each condition's own interpreter: every CIF is read and drawn, and on
#: ``after`` the report is read field-wise and whole, so the shim's rows can be
#: checked against reads known to have happened.
CHECK_SCRIPT = """\
import inspect, json, sys
import rietx as rx
out = {}
for path in sys.argv[1:]:
    fig = rx.viz.render_structure(rx.Structure.from_cif(path), size=160)
    report = getattr(fig, "report", None)
    if report is not None:
        report.hidden
        repr(report)
    out[path] = len(fig.atoms)
params = list(inspect.signature(rx.viz.render_structure).parameters)
print(json.dumps({"atoms": out, "first": params[0], "has_report": report is not None}))
"""


def instrument_check(python: Path, log: Path, condition: str, boot: str = "") -> dict:
    """Draw every task's CIF through the shim and check what it logged.

    A condition's venv boots the shim itself; ``boot`` is the line that does it
    for an interpreter that has no ``.pth`` (``check``, in this repo's venv).
    """
    with tempfile.TemporaryDirectory() as tmp:
        cifs = []
        for task, spec in TASKS.items():
            path = Path(tmp) / spec["cif"]
            path.write_text(cif_text(task), encoding="utf-8")
            cifs.append(str(path))
        run_id = f"check-{uuid.uuid4().hex[:8]}"
        env = dict(os.environ, RIETX_FIG_RUN=run_id)
        env.pop("VIRTUAL_ENV", None)
        proc = _run(str(python), "-c", boot + CHECK_SCRIPT, *cifs, env=env)
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    rows = [r for r in load(log) if r.get("run") == run_id]
    renders = [r for r in rows if r.get("name") == "render_structure" and r.get("depth") == 0]
    reads = {r["name"] for r in rows if r.get("event") == "read"}
    problems = []
    sizes = [r.get("pixels") for r in renders]
    if len(renders) != len(TASKS) or any(not p or max(p) != 160 for p in sizes):
        problems.append(f"render rows {sizes} for {len(TASKS)} renders at a long side of 160")
    if result["first"] != "structure":
        problems.append(f"the signature shows {result['first']!r} first: the shim is visible")
    if result["has_report"] != (condition == "after"):
        problems.append(f"report present = {result['has_report']} on {condition}")
    if condition == "after" and not {"report.hidden", "report.whole"} <= reads:
        problems.append(f"report reads logged: {sorted(reads)}")
    if condition == "before" and any(n.startswith("report.") for n in reads):
        problems.append("a report read logged on a tree with no report")
    patched = [r for r in rows if r.get("event") == "patched"]
    if not patched:
        problems.append("the shim never patched")
    if problems:
        raise SystemExit(f"{condition}: instrument check failed: " + "; ".join(problems))
    return {"atoms_drawn": {Path(k).name: v for k, v in result["atoms"].items()},
            "missing": patched[-1]["missing"]}


def prepare(root: Path, condition: str) -> None:
    from tests.eval_agent_surface.runner import check_no_inherited_context

    if condition not in COMMITS:
        raise SystemExit(f"unknown condition {condition!r}")
    tree, venv = root / "trees" / condition, root / "venvs" / condition
    log = root / "logs" / f"{condition}.jsonl"
    check_no_inherited_context(root / "work" / "x")
    if venv.exists():
        raise SystemExit(f"{venv} exists: a condition is prepared once")
    tree.mkdir(parents=True)
    archive = subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar",
                              COMMITS[condition], "--", *TREE_PATHS],
                             capture_output=True, check=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(tree, filter="data")
    _run("uv", "venv", "-q", "--python", "3.12", str(venv))
    python = venv / "bin" / "python"
    _run("uv", "pip", "install", "-q", "--python", str(python), f"{tree}[viz]")
    purelib = Path(_run(str(python), "-c",
                        "import sysconfig; print(sysconfig.get_paths()['purelib'])"
                        ).stdout.strip())
    shutil.copyfile(HARNESS / "fig_trace.py", purelib / "fig_trace.py")
    (purelib / "fig_trace_boot.py").write_text(
        f"import fig_trace as _t\n_t.LOG = {str(log)!r}\n", encoding="utf-8")
    (purelib / "zzz_fig_trace.pth").write_text("import fig_trace_boot\n", encoding="utf-8")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.touch()
    checked = instrument_check(python, log, condition)
    if condition == "after":  # drawing them is free; judging them is menu option J
        _run(str(python), str(HARNESS / "reference_figures.py"), str(root / "references"))
    (root / f"{condition}.prepared.json").write_text(
        json.dumps({"commit": COMMITS[condition], **checked}, indent=1), encoding="utf-8")
    print(f"{condition}: {python}, instrument checked: {checked}")


# --- launch --------------------------------------------------------------------

def agent_env(run: str) -> dict:
    """This shell's environment, less the venv it was started from."""
    env = dict(os.environ, RIETX_FIG_RUN=run)
    venv = env.pop("VIRTUAL_ENV", None)
    if venv:
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                      if not p.startswith(venv))
    return env


def launch(root: Path, run: str) -> None:
    from tests.eval_agent_surface.runner import check_no_inherited_context, wait_quiet

    task, condition, model, _ = split(run)
    p = paths(root, run)
    if not p["python"].is_file():
        raise SystemExit(f"{condition} is not prepared")
    if p["workspace"].exists():
        raise SystemExit(f"{p['workspace']} exists: a run is launched once")
    check_no_inherited_context(p["workspace"])
    p["workspace"].mkdir(parents=True)
    (p["workspace"] / TASKS[task]["cif"]).write_text(cif_text(task), encoding="utf-8")
    _run(str(p["rietx"]), "skill", "--install", str(p["workspace"]), "--copy")

    session = str(uuid.uuid4())
    command = ["claude", "-p", prompt_for(root, run), "--model", MODELS[model],
               "--session-id", session, "--permission-mode", "bypassPermissions",
               "--output-format", "json", "--strict-mcp-config",
               "--setting-sources", SETTING_SOURCES,
               "--max-budget-usd", MAX_BUDGET_USD, "--disallowedTools", *DISALLOWED]
    proc = subprocess.run(command, cwd=p["workspace"], capture_output=True, text=True,
                          env=agent_env(run))
    record = {"run": run, "session_id": session, "model": MODELS[model],
              "protocol": PROTOCOL_VERSION,
              "commit": COMMITS[condition], "returncode": proc.returncode,
              "stderr": proc.stderr[-4000:]}
    try:
        record["result"] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        record["stdout"] = proc.stdout[-8000:]
    p["launch"].parent.mkdir(parents=True, exist_ok=True)
    p["launch"].write_text(json.dumps(record, indent=1), encoding="utf-8")
    outlived, gave_up = wait_quiet(p["log"], idle=10.0, limit=600.0)
    record.update(outlived_session_seconds=round(outlived, 1), still_writing_at_limit=gave_up)
    p["launch"].write_text(json.dumps(record, indent=1), encoding="utf-8")
    result = record.get("result") or {}
    print(f"{run}: rc={proc.returncode} ${result.get('total_cost_usd', float('nan')):.2f} "
          f"{result.get('num_turns', '?')} turns")


# --- collect -------------------------------------------------------------------

def load(path: Path) -> list[dict]:
    from tests.eval_agent_surface import trail

    return trail.load(path) if Path(path).is_file() else []


def transcript_for(session: str) -> Path | None:
    matches = sorted((Path.home() / ".claude" / "projects").glob(f"*/{session}.jsonl"))
    return matches[0] if matches else None


IMAGE = re.compile(r"\.(png|jpe?g|gif|webp)$", re.I)
ABSOLUTE = re.compile(r"(?:(?<=\s)|(?<=^)|(?<=[\"'=(]))(~?/[\w.@+-]+(?:/[\w.@+-]+)+)")


def _blocks(rows: list[dict], kind: str, role: str):
    for row in rows:
        if row.get("type") != role:
            continue
        content = (row.get("message") or {}).get("content")
        if isinstance(content, list):
            for block in content:
                if block.get("type") == kind:
                    yield block


def looks(rows: list[dict]) -> list[dict]:
    """Every picture the agent saw: the file it read and the pixels it got back."""
    from PIL import Image

    asked = {b.get("id"): (b.get("input") or {}).get("file_path", "")
             for b in _blocks(rows, "tool_use", "assistant") if b.get("name") == "Read"}
    out = []
    for result in _blocks(rows, "tool_result", "user"):
        path = asked.get(result.get("tool_use_id"))
        body = result.get("content")
        if path is None or not isinstance(body, list):
            continue
        for item in body:
            data = (item.get("source") or {}).get("data") if item.get("type") == "image" else None
            if data:
                size = Image.open(io.BytesIO(base64.b64decode(data))).size
                out.append({"path": path, "pixels": list(size)})
    return out


def skills(rows: list[dict]) -> dict:
    """Which skills the agent invoked, and which files of the rietx skill it read."""
    invoked, files = [], set()
    for block in _blocks(rows, "tool_use", "assistant"):
        args = block.get("input") or {}
        if block.get("name") == "Skill":
            invoked.append(args.get("skill") or args.get("command") or "?")
        text = " ".join(str(v) for v in args.values() if isinstance(v, str))
        for hit in re.findall(r"skills/rietx/([\w./-]+\.md)", text):
            files.add(hit)
    return {"invoked": invoked, "files": sorted(files)}


def outside(rows: list[dict], allowed: tuple[str, ...]) -> list[str]:
    """Absolute paths the agent named outside the run's own places."""
    found = set()
    for block in _blocks(rows, "tool_use", "assistant"):
        args = block.get("input") or {}
        for value in args.values():
            if not isinstance(value, str):
                continue
            for path in ABSOLUTE.findall(value):
                full = os.path.expanduser(path)
                if not full.startswith(allowed):
                    found.add(path)
    return sorted(found)


def figure_facts(path: Path) -> dict:
    from PIL import Image

    if not path.is_file():
        return {"exists": False}
    with Image.open(path) as image:
        dpi = image.info.get("dpi")
        return {"exists": True, "pixels": list(image.size),
                "dpi": [round(float(d), 2) for d in dpi] if dpi else None}


def mechanical(task: str, facts: dict) -> dict:
    checks = [("figure.png exists", facts["exists"])]
    if task == "fap" and facts["exists"]:
        width = facts["pixels"][0]
        dpi = (facts.get("dpi") or [0])[0]
        checks.append((f"width {width} px within {FAP_WIDTH}",
                       FAP_WIDTH[0] <= width <= FAP_WIDTH[1]))
        checks.append((f"dpi {dpi} within {FAP_DPI}", FAP_DPI[0] <= dpi <= FAP_DPI[1]))
    return {"pass": all(ok for _, ok in checks), "checks": [[c, ok] for c, ok in checks]}


def collect(root: Path, run: str) -> dict:
    from tests.eval_agent_surface import trail

    task, condition, model, repeat = split(run)
    p = paths(root, run)
    launched = json.loads(p["launch"].read_text(encoding="utf-8"))
    transcript = transcript_for(launched["session_id"])
    if transcript is None:
        raise SystemExit(f"{run}: no transcript for session {launched['session_id']}")
    rows = trail.load(transcript)
    # the run id is what attributes a row; a process that lost the variable
    # (a script that clears its environment) falls back on its directory
    traced = [r for r in load(p["log"]) if r.get("run") == run
              or (r.get("run") is None
                  and str(r.get("cwd") or "").startswith(str(p["workspace"])))]
    bill = trail.usage(rows)
    calls = trail.tool_calls(rows)
    result = launched.get("result") or {}
    top = [r for r in traced if r.get("event") == "call" and r.get("depth") == 0]
    counts: dict[str, int] = {}
    for r in traced:
        if r.get("event") == "reads":
            for key, n in r["counts"].items():
                counts[key] = counts.get(key, 0) + n
    facts = figure_facts(p["workspace"] / "figure.png")
    score = {
        "run": run, "task": task, "condition": condition, "model": model,
        "repeat": repeat, "commit": COMMITS[condition],
        "protocol": launched.get("protocol", "1.0"),
        "session_id": launched["session_id"], "models_seen": dict(bill.models),
        "cost_usd": result.get("total_cost_usd"), "turns": result.get("num_turns"),
        "minutes": round((result.get("duration_ms") or 0) / 60000, 2),
        "api_calls": bill.api_calls,
        "tokens": {"input": bill.input_tokens, "cache_read": bill.cache_read,
                   "cache_write": bill.cache_write, "output": bill.output_tokens},
        "renders": [{"pixels": r.get("pixels"), "values": r.get("values"),
                     "first": r.get("first"), "ok": r.get("ok")}
                    for r in top if r["name"] == "render_structure"],
        "builds": [r.get("values") for r in top if r["name"] == "build"],
        "cuts": {n: sum(r["name"] == n for r in top)
                 for n in sorted({r["name"] for r in top} - {"render_structure", "build"})},
        "looks": looks(rows),
        "report_reads": {k.split(".", 1)[1]: n for k, n in sorted(counts.items())
                         if k.startswith("report.")},
        "figure_reads": {k.split(".", 1)[1]: n for k, n in sorted(counts.items())
                         if k.startswith("figure.")},
        "skills": skills(rows),
        "errors": [c.head[:160] for c in calls if c.error],
        "outside": outside(rows, (str(p["workspace"]), str(root), "/tmp", "/private/tmp",
                                  "/var/folders", "/dev/")),
        "figure": facts,
        "mechanical": mechanical(task, facts),
        "stall": None,
    }
    old = p["record"] / "score.json"
    if old.is_file():  # the judge's verdict and the hand-written stall survive a re-collect
        before = json.loads(old.read_text(encoding="utf-8"))
        for key in ("judge", "done", "stall"):
            if key in before:
                score[key] = before[key]
    p["record"].mkdir(parents=True, exist_ok=True)
    (p["record"] / "trace.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in traced), encoding="utf-8")
    (p["record"] / "trail.txt").write_text(
        f"run {run}\ntranscript {transcript}\n\n" + trail.render(rows, traced) + "\n",
        encoding="utf-8")
    if facts["exists"]:
        from PIL import Image

        with Image.open(p["workspace"] / "figure.png") as image:
            image.thumbnail((THUMB, THUMB))
            image.save(p["record"] / "figure.png", optimize=True)
    write_score(p["record"], score)
    print(f"{run}: ${score['cost_usd']}, {len(score['renders'])} renders, "
          f"{len(score['looks'])} looks, report {score['report_reads']}, "
          f"{len(score['errors'])} errors, outside {score['outside'][:4]}")
    return score


def write_score(record: Path, score: dict) -> None:
    (record / "score.json").write_text(json.dumps(score, indent=1, ensure_ascii=False) + "\n",
                                       encoding="utf-8")


# --- judge ---------------------------------------------------------------------

def judge_prompt(task: str) -> str:
    criteria = (*TASKS[task]["criteria"], *COMMON)
    return JUDGE.format(prompt=TASKS[task]["prompt"],
                        criteria="\n".join(f"{n}. {c}" for n, c in enumerate(criteria, 1)))


def ask_judge(task: str, figure: Path, where: Path) -> dict:
    """One judge session over one figure, alone in a directory of its own.

    The verdict is ``yes`` only when every criterion is: the judge says what it
    saw per criterion, and the harness, never the judge, sums that to done.
    """
    where.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(figure, where / "figure.png")
    session = str(uuid.uuid4())
    proc = subprocess.run(
        ["claude", "-p", judge_prompt(task), "--model", JUDGE_MODEL, "--session-id", session,
         "--allowedTools", "Read", "--strict-mcp-config", "--output-format", "json",
         "--max-budget-usd", JUDGE_BUDGET_USD],
        cwd=where, capture_output=True, text=True, env=agent_env(f"judge-{where.name}"))
    verdict = {"model": JUDGE_MODEL, "session_id": session, "returncode": proc.returncode}
    try:
        result = json.loads(proc.stdout)
        verdict["cost_usd"] = result.get("total_cost_usd")
        text = result.get("result") or ""
        verdict["criteria"] = json.loads(text[text.index("{"):text.rindex("}") + 1])["criteria"]
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        verdict["error"] = f"{type(exc).__name__}: {exc}"
        verdict["raw"] = proc.stdout[-4000:]
    criteria = verdict.get("criteria") or []
    n_criteria = len(TASKS[task]["criteria"]) + len(COMMON)
    verdict["yes"] = (len(criteria) == n_criteria
                      and all(c.get("verdict") == "yes" for c in criteria)) if criteria else None
    return verdict


def judge(root: Path, run: str) -> None:
    task = split(run)[0]
    p = paths(root, run)
    score = json.loads((p["record"] / "score.json").read_text(encoding="utf-8"))
    if not score["figure"]["exists"]:
        score["judge"] = {"skipped": "no figure.png"}
        score["done"] = False
    else:
        score["judge"] = ask_judge(task, p["workspace"] / "figure.png", p["judge"])
        yes = score["judge"]["yes"]
        score["done"] = None if yes is None else bool(yes and score["mechanical"]["pass"])
    write_score(p["record"], score)
    print(f"{run}: done={score['done']} " + " ".join(
        f"{c.get('n')}:{c.get('verdict')}" for c in score["judge"].get("criteria") or []))


def judge_references(root: Path) -> None:
    """The judge on ``reference_figures.py``'s pairs: every right one done, no default."""
    drawn = root / "references"
    out = {}
    for task in TASKS:
        for kind in ("right", "default"):
            verdict = ask_judge(task, drawn / f"{task}-{kind}.png",
                                root / "judge" / f"reference-{task}-{kind}")
            verdict["expected"] = kind == "right"
            out[f"{task}-{kind}"] = verdict
            print(f"{task}-{kind}: yes={verdict['yes']} (expected {verdict['expected']}) "
                  + " ".join(f"{c.get('n')}:{c.get('verdict')}"
                             for c in verdict.get("criteria") or []))
    (HARNESS / "references.json").write_text(json.dumps(out, indent=1, ensure_ascii=False)
                                             + "\n", encoding="utf-8")
    wrong = [k for k, v in out.items() if v["yes"] is not v["expected"]]
    print(f"judge disagrees with the reference on {len(wrong)} of {len(out)}: {wrong}")


# --- the menu and the table ----------------------------------------------------

def scores(current: bool = True) -> list[dict]:
    """Every run's score, or only those launched under ``PROTOCOL_VERSION``."""
    out = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(RECORD.glob("*/score.json"))]
    return [s for s in out if s.get("protocol") == PROTOCOL_VERSION] if current else out


def per_run(model: str, measured: list[dict]) -> tuple[tuple[float, float], str]:
    costs = [s["cost_usd"] for s in measured if s["model"] == model and s.get("cost_usd")]
    if len(costs) >= 2:
        return (min(costs), max(costs)), f"measured, {len(costs)} runs"
    return PRIOR_USD[model], "prior (round 1.1, scaled)"


def menu() -> None:
    measured = scores()
    judged = [s["judge"]["cost_usd"] for s in measured
              if (s.get("judge") or {}).get("cost_usd")]
    judge_cost = (min(judged), max(judged)) if len(judged) >= 2 else JUDGE_PRIOR_USD
    minutes = [s["minutes"] for s in measured if s.get("minutes")]
    wall = (min(minutes), max(minutes)) if len(minutes) >= 2 else PRIOR_MINUTES
    print(f"WP-1504 — {len(TASKS)} tasks × {len(COMMITS)} conditions × {len(MODELS)} models"
          f" × {REPEATS} repeats = {len(runs())} runs, each judged once by {JUDGE_MODEL}.")
    print(f"Already run: {len(measured)}.\n\nPer run:")
    rates = {}
    for model in MODELS:
        rates[model], source = per_run(model, measured)
        print(f"  {model:7s} ${rates[model][0]:.2f}-{rates[model][1]:.2f}  ({source})")
    print(f"  judge   ${judge_cost[0]:.2f}-{judge_cost[1]:.2f}"
          f"  wall {wall[0]:.0f}-{wall[1]:.0f} min a run, serial\n")

    finished = {s["run"] for s in measured}

    def option(name: str, chosen: list[str], what: str) -> None:
        todo = [r for r in chosen if r not in finished]
        low = sum(rates[split(r)[2]][0] + judge_cost[0] for r in todo)
        high = sum(rates[split(r)[2]][1] + judge_cost[1] for r in todo)
        print(f"{name}  {len(todo):2d} runs  ${low:.0f}-{high:.0f}  "
              f"{len(todo) * wall[0] / 60:.1f}-{len(todo) * wall[1] / 60:.1f} h")
        print(f"     {what}")
        if len(todo) <= 4:
            print("     " + " ".join(todo))

    n_refs = 2 * len(TASKS)
    done_refs = (HARNESS / "references.json").is_file()
    if done_refs:
        print("J   done: references.json")
    else:
        print(f"J  {n_refs:2d} judge calls  ${n_refs * judge_cost[0]:.0f}-"
              f"{n_refs * judge_cost[1]:.0f}  a few minutes")
    print("     the judge on a right and a default figure per task, before it scores a run")
    option("A", ["gypsum-after-sonnet-1", "gypsum-after-opus-1"],
           "pilot: the harness end to end on the one task that needs a cut, and the "
           "first measured cost per run")
    option("B", [r for r in runs() if r.endswith("-1")],
           "one repeat of every cell: done or not per task, model and condition, at N = 1")
    option("C", runs(), "the registered round: N = 3 per cell")
    option("D", [r for r in runs() if split(r)[2] == "sonnet"],
           "the registered round on Sonnet alone, the cheaper half")


def _span(values: list[float], fmt: str = "{:.0f}") -> str:
    values = [v for v in values if v is not None]
    if not values:
        return "—"
    lo, hi = min(values), max(values)
    return fmt.format(lo) if lo == hi else f"{fmt.format(lo)}-{fmt.format(hi)}"


def table() -> None:
    measured = scores()
    print("| task | model | condition | done | renders | looks | tokens (k) | "
          "minutes | $ |")
    print("|---|---|---|---|---|---|---|---|---|")
    for task in TASKS:
        for model in MODELS:
            for condition in COMMITS:
                cell = [s for s in measured if (s["task"], s["model"], s["condition"])
                        == (task, model, condition)]
                if not cell:
                    continue
                done = sum(s.get("done") is True for s in cell)
                unjudged = sum(s.get("done") is None for s in cell)
                tokens = [sum(s["tokens"].values()) / 1000 for s in cell]
                print(f"| {task} | {model} | {condition} | {done}/{len(cell)}"
                      f"{f' ({unjudged} unjudged)' if unjudged else ''} | "
                      f"{_span([len(s['renders']) for s in cell])} | "
                      f"{_span([len(s['looks']) for s in cell])} | {_span(tokens)} | "
                      f"{_span([s['minutes'] for s in cell], '{:.1f}')} | "
                      f"{_span([s['cost_usd'] for s in cell], '{:.2f}')} |")
    fields = ("hidden", "hidden_atoms", "dangling_bonds", "label_overlaps", "empty",
              "cut", "note", "warnings", "whole")
    after = [s for s in measured if s["condition"] == "after"]
    if after:
        print(f"\n`report` fields, runs reading each, of {len(after)} after-runs:")
        for name in fields:
            n = sum(name in s["report_reads"] for s in after)
            print(f"- `{name}`: {n}" + ("" if n else " — never read"))


# --- check ---------------------------------------------------------------------

def check() -> None:
    """PROTOCOL.md quotes what this file launches, and the shim works here."""
    protocol = (HARNESS / "PROTOCOL.md").read_text(encoding="utf-8")
    flat = " ".join(protocol.split())
    quoted = [*COMMITS.values(), PREAMBLE, *COMMON,
              *(t["prompt"] for t in TASKS.values()),
              *(c for t in TASKS.values() for c in t["criteria"])]
    quoted.append(JUDGE.replace("{{", "{").replace("}}", "}"))
    missing = [q for q in quoted if " ".join(q.split()) not in flat]
    if missing:
        raise SystemExit("PROTOCOL.md does not quote: " + " | ".join(m[:60] for m in missing))
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "check.jsonl"
        boot = (f"import sys; sys.path.insert(0, {str(HARNESS)!r}); import fig_trace; "
                f"fig_trace.LOG = {str(log)!r}\n")
        checked = instrument_check(Path(sys.executable), log, "after", boot)
    print(f"PROTOCOL.md quotes all {len(quoted)} strings; the shim checked here: {checked}")


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--menu":
        menu()
    elif len(argv) >= 2 and argv[1] == "check":
        check()
    elif len(argv) >= 2 and argv[1] == "table":
        table()
    elif len(argv) >= 3 and argv[1] == "judge-references":
        judge_references(Path(argv[2]).resolve())
    elif len(argv) >= 4 and argv[1] == "prepare":
        prepare(Path(argv[2]).resolve(), argv[3])
    elif len(argv) >= 4 and argv[1] in ("launch", "collect", "judge", "go"):
        root = Path(argv[2]).resolve()
        for run in argv[3:]:
            split(run)
        for run in argv[3:]:
            if argv[1] in ("launch", "go"):
                launch(root, run)
            if argv[1] in ("collect", "go"):
                collect(root, run)
            if argv[1] in ("judge", "go"):
                judge(root, run)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
