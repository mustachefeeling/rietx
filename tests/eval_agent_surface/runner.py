"""Prepare, launch and collect one cell of the agent-surface round.

    python tests/eval_agent_surface/runner.py prepare <root> <cell> [--zrm DIR]
    python tests/eval_agent_surface/runner.py launch  <root> <cell>
    python tests/eval_agent_surface/runner.py collect <root> <cell>

A **cell** is `<episode>-<condition>-<model>`, e.g. `ramp-skill-opus5`.  Its
three verbs are separate on purpose: `prepare` is cheap and repeatable,
`launch` spends money, and `collect` can be re-run over a finished run as often
as a read-out needs re-reading.

**The condition is the workspace, never the prompt** (PROTOCOL.md 1.1).
`prepare` builds:

    <root>/<cell>/            the workspace: data files and nothing else,
                              plus .agents/skills + .claude/skills under `skill`
    <root>/venvs/<cell>/      the run's own venv, with the shim and its log
                              path baked into a .pth — attribution is then a
                              property of the environment, which is round 1.0's
                              own recommendation for this round
    <root>/logs/<cell>.jsonl  the trace
    <root>/runs/<cell>.json   what `launch` got back: cost, turns, session id

**What every cell inherits from this machine, and cannot be stripped without an
API key** (`--bare` refuses OAuth): the user-level `~/.claude/CLAUDE.md`, and
the user-level skills, which on the registration machine are `tufte`,
`yue-docs-style` and `yue-figure-style` — none of them about diffraction.  They
are constant across cells, so they cannot produce the `skill`/`bare`
difference, and they are declared here rather than assumed away.

**And what `bare` does not withhold, measured rather than assumed.** The
condition is the *workspace*, and the skill is reachable from outside it by two
routes, both observed in the ramp episode: it ships inside the wheel, where
`ramp-bare-sonnet` found it in site-packages, and the maintainer's own checkout
sits on the registration machine, where `ramp-bare-opus5` found
`docs/skill/rietx/SKILL.md` by `find` and read it whole.  The two are not the
same kind of leak.  The wheel's copy is a **property of the shipped package** —
every deployment has it, so a `bare` cell that reaches it is measuring what a
real unprimed user would meet.  The checkout's copy is a **property of this
machine** and no user has it.  Neither is fixed here: 1.1 is registered, and
measuring the outstanding cells differently from the ones that have run is the
one thing a round may not do to itself (PROTOCOL.md § This round's own
instrument).  A sealed workspace is round 1.2's, and until it exists every
`bare` read-out is a statement about *route and latency*, never about access.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
REPO = HARNESS.parents[1]

# Run as a script from anywhere as well as imported as a test module: the repo
# root is where `tests` is a package, and a cell is prepared from a shell.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tests.eval_agent_surface.episodes import ramp  # noqa: E402

EPISODES = ("ramp", "zrm")
CONDITIONS = ("bare", "skill")
MODELS = {"sonnet": "sonnet", "opus5": "opus"}

# The prompts are authored here and quoted by PROTOCOL.md; `test_runner.py`
# holds the two copies together, so the registered text and the launched text
# cannot drift.  Neither names a module, a plan, a method or a document.
PROMPTS = {
    "ramp": (
        "Here are 68 patterns from a variable-temperature run, 25 to 720 °C. "
        "Refine them in order, tell me what the cell does, and flag anything "
        "you would not quote."
    ),
    "zrm": (
        "`d8_01612.raw` is a variable-temperature powder reel: 82 scans from "
        "318 K to 1123 K, Cu Kα1 at λ = 1.5406 Å from a Ge(111) "
        "monochromator, Bragg–Brentano geometry. `d8_01612_vt_reel_02.inp` is "
        "the input file another program refined it with, and it holds the "
        "starting model: four phases, their cells and their sites. Refine the "
        "first five scans, tell me how the phase fractions and the cell "
        "parameters move with temperature, and flag anything you would not "
        "quote."
    ),
}

# What the 2026-08-26 baseline was given beyond its prompt, and nothing more.
PREAMBLE = (
    "The python interpreter to use is {python}. "
    "The data is in {workspace}, which is your working directory."
)

ZRM_FILES = ("d8_01612.raw", "d8_01612_vt_reel_02.inp")


def split(cell: str) -> tuple[str, str, str]:
    parts = cell.split("-")
    if len(parts) != 3:
        raise SystemExit(f"unknown cell {cell!r}: <{'|'.join(EPISODES)}>-"
                         f"<{'|'.join(CONDITIONS)}>-<{'|'.join(MODELS)}>")
    episode, condition, model = parts
    if episode not in EPISODES or condition not in CONDITIONS or model not in MODELS:
        raise SystemExit(f"unknown cell {cell!r}: <{'|'.join(EPISODES)}>-"
                         f"<{'|'.join(CONDITIONS)}>-<{'|'.join(MODELS)}>")
    return episode, condition, model


def paths(root: Path, cell: str) -> dict[str, Path]:
    return {
        "workspace": root / cell,
        "venv": root / "venvs" / cell,
        "log": root / "logs" / f"{cell}.jsonl",
        "run": root / "runs" / f"{cell}.json",
        "trail": root / "runs" / f"{cell}.trail.txt",
    }


def _run(*args: str, **kw) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, capture_output=True, text=True, **kw)
    if proc.returncode != 0:
        raise SystemExit(f"{args[0]} failed: {proc.stderr.strip()[:2000]}")
    return proc


def build_venv(venv: Path, log: Path) -> Path:
    """A venv with rietx[viz] and the shim, its log path baked into a .pth.

    Baked rather than exported: an environment variable is something a run can
    lose or overwrite, and a `.pth` runs before any of the run's own code.
    """
    _run("uv", "venv", "--python", "3.12", str(venv))
    python = venv / "bin" / "python"
    _run("uv", "pip", "install", "-q", "--python", str(python), "-e", f"{REPO}[viz]")

    purelib = Path(_run(str(python), "-c",
                        "import sysconfig; print(sysconfig.get_paths()['purelib'])"
                        ).stdout.strip())
    shutil.copyfile(HARNESS / "rietx_surface_trace.py", purelib / "rietx_surface_trace.py")
    (purelib / "rietx_surface_boot.py").write_text(
        "import rietx_surface_trace as _t\n"
        f"_t.LOG = {str(log)!r}\n", encoding="utf-8")
    # `zzz_` so it sorts after the editable install's own .pth files
    (purelib / "zzz_rietx_surface.pth").write_text("import rietx_surface_boot\n",
                                                   encoding="utf-8")
    return python


def check_unprepared(workspace: Path) -> None:
    """A cell is prepared once, and the refusal comes before anything is spent.

    Asked before the venv is built as well as inside `build_workspace`: the
    venv is minutes of `uv pip install` and it is *also* where the shim and its
    baked log path live, so re-preparing a cell that has already run would
    overwrite the environment its trace was written by before saying no.
    """
    if workspace.exists() and any(workspace.iterdir()):
        raise SystemExit(f"{workspace} is not empty — a cell is prepared once")


# Files that make an agent's context a property of where the round's root
# happens to sit.  Claude Code reads `CLAUDE.md`/`AGENTS.md` from the working
# directory *upwards* and project skills from a `.claude`/`.agents` above it,
# so a root inside any checkout hands the `bare` cells that checkout's rules
# and there is no condition left to measure.  The user-level `~/.claude` is
# declared in the module docstring and is deliberately not caught here.
INHERITED = ("CLAUDE.md", "AGENTS.md", ".claude", ".agents")


def check_no_inherited_context(workspace: Path) -> None:
    for parent in workspace.parents:
        for name in INHERITED:
            if parent == Path.home() and name in (".claude", ".agents"):
                continue  # the user-level directory, declared above
            if (parent / name).exists():
                raise SystemExit(
                    f"{parent / name} sits above the workspace: every cell would "
                    "inherit it, and the bare condition would not be bare. Put the "
                    "round's root outside any checkout.")
        if parent == Path.home() or parent == parent.parent:
            break


def build_workspace(workspace: Path, episode: str, condition: str,
                    python: Path, zrm: Path | None) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    check_unprepared(workspace)

    if episode == "ramp":
        ramp.write_workspace(workspace)
    else:
        if zrm is None:
            raise SystemExit(
                "E-ZRM needs --zrm DIR holding d8_01612.raw and "
                "d8_01612_vt_reel_02.inp; the files are a third party's and are "
                "not committed (PROTOCOL.md § The episodes)")
        for name in ZRM_FILES:
            source = zrm / name
            if not source.is_file():
                raise SystemExit(f"missing {source}")
            shutil.copyfile(source, workspace / name)

    if condition == "skill":
        _run(str(python.parent / "rietx"), "skill", "--install", str(workspace), "--copy")


def prepare(root: Path, cell: str, zrm: Path | None) -> None:
    episode, condition, _ = split(cell)
    p = paths(root, cell)
    check_unprepared(p["workspace"])
    check_no_inherited_context(p["workspace"])
    for key in ("log", "run"):
        p[key].parent.mkdir(parents=True, exist_ok=True)
    p["log"].touch()
    python = build_venv(p["venv"], p["log"])
    build_workspace(p["workspace"], episode, condition, python, zrm)
    print(f"{cell}: workspace {p['workspace']}, python {python}")


def prompt_for(cell: str, root: Path) -> str:
    episode, _, _ = split(cell)
    p = paths(root, cell)
    return (PROMPTS[episode] + "\n\n"
            + PREAMBLE.format(python=p["venv"] / "bin" / "python",
                              workspace=p["workspace"]))


def wait_quiet(log: Path, idle: float = 20.0,
               limit: float = 1800.0) -> tuple[float, bool]:
    """Block until the trace has been silent for `idle` seconds.

    **A cell's work can outlive its session.** Measured on the first pilot run
    (2026-08-29): the agent put a 68-pattern chain in the background, wrote its
    answer without it, and `refine_sequential` went on writing for 127.6 s after
    `claude -p` had returned — into the wall clock of the cell launched next.
    A round whose read-outs include wall clock cannot let two cells overlap, so
    `launch` waits here before it returns rather than trusting the exit code.

    Returns *how long the work outlived the session*, which is the time to the
    **last write** and not the time to noticing it: detection costs a whole
    `idle` window, and returning the wall clock of the wait would overstate
    every real overlap by that window while reading 0 for a cell that never
    overlapped. The flag says whether `limit` was reached, so a run still
    writing when the wait gave up cannot be read as a quiet one.
    """
    began = time.time()
    while time.time() - began < limit:
        last = log.stat().st_mtime if log.exists() else 0.0
        if time.time() - last >= idle:
            return max(0.0, last - began), False
        time.sleep(2.0)
    last = log.stat().st_mtime if log.exists() else 0.0
    return max(0.0, last - began), True


def launch(root: Path, cell: str) -> None:
    _, _, model = split(cell)
    p = paths(root, cell)
    if not p["workspace"].is_dir():
        raise SystemExit(f"{cell} is not prepared")
    session = str(uuid.uuid4())
    command = ["claude", "-p", prompt_for(cell, root),
               "--model", MODELS[model],
               "--session-id", session,
               "--permission-mode", "bypassPermissions",
               "--output-format", "json"]
    proc = subprocess.run(command, cwd=p["workspace"], capture_output=True, text=True)
    record = {"cell": cell, "session_id": session, "model": MODELS[model],
              "returncode": proc.returncode, "stderr": proc.stderr[-4000:]}
    try:
        record["result"] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        record["stdout"] = proc.stdout[-8000:]
    outlived, gave_up = wait_quiet(p["log"])
    record["outlived_session_seconds"] = round(outlived, 1)
    record["still_writing_at_limit"] = gave_up
    p["run"].write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"{cell}: rc={proc.returncode} session={session} "
          f"(work outlived the session by {record['outlived_session_seconds']}s"
          f"{', STILL WRITING when the wait gave up' if gave_up else ''}) "
          f"-> {p['run']}")


def transcript_for(root: Path, cell: str) -> Path | None:
    """The harness writes one JSONL per session, under a slug of the cwd."""
    record = json.loads(paths(root, cell)["run"].read_text(encoding="utf-8"))
    slug = str(paths(root, cell)["workspace"]).replace("/", "-").replace("_", "-")
    candidate = Path.home() / ".claude" / "projects" / slug / f"{record['session_id']}.jsonl"
    if candidate.is_file():
        return candidate
    matches = sorted((Path.home() / ".claude" / "projects").glob(
        f"*/{record['session_id']}.jsonl"))
    return matches[0] if matches else None


def collect(root: Path, cell: str) -> None:
    from tests.eval_agent_surface import trail

    p = paths(root, cell)
    transcript = transcript_for(root, cell)
    if transcript is None:
        raise SystemExit(f"{cell}: no transcript for that session id")
    text = trail.render(trail.load(transcript), trail.load(p["log"]))
    record = json.loads(p["run"].read_text(encoding="utf-8")).get("result") or {}
    # `or` rather than a default: a failed run's record carries the keys with a
    # null, and a default only covers a key that is absent.
    cost = record.get("total_cost_usd") or float("nan")
    minutes = (record.get("duration_ms") or 0) / 60000
    head = (f"cell {cell}\ntranscript {transcript}\n"
            f"cost ${cost:.2f}, {record.get('num_turns', '?')} turns, "
            f"{minutes:.1f} min reported\n\n")
    p["trail"].write_text(head + text + "\n", encoding="utf-8")
    print(head + text.rsplit("\n\n", 1)[-1])


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(__doc__)
        return 2
    verb, root, cell = argv[1], Path(argv[2]).resolve(), argv[3]
    zrm = None
    if "--zrm" in argv:
        after = argv.index("--zrm") + 1
        if after >= len(argv):
            raise SystemExit("--zrm needs a directory")
        zrm = Path(argv[after]).resolve()
    if verb == "prepare":
        prepare(root, cell, zrm)
    elif verb == "launch":
        launch(root, cell)
    elif verb == "collect":
        collect(root, cell)
    else:
        raise SystemExit(f"unknown verb {verb!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
