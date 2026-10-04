"""Build a `claude plugin eval` plugin from a skill tree and this pilot's cases.

    python build_pilot.py <skill tree> <out dir> <episode dir>

`<episode dir>` holds FAP.XRA, fluorapatite.cif, fit.py and fit_output.txt;
the cases' fixture scripts copy from it.  WP-1905's `tests/eval_skill/build.py`
replaces this.
"""

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(tree: Path, out: Path, episode: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    (out / ".claude-plugin").mkdir(parents=True)
    (out / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": "rietx-skill", "version": "0.0.1",
        "description": "the rietx agent skill under evaluation"}, indent=1))
    shutil.copytree(tree, out / "skills" / "rietx")
    shutil.copytree(HERE / "evals", out / "evals")
    for script in (out / "evals").glob("*/fixture.sh"):
        text = script.read_text().replace("$EPISODE", str(episode))
        script.write_text(text)
        script.chmod(0o755)


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
