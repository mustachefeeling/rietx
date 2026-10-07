"""CI's changed-surface report (`tests/skill_surface.py`, WP-1907), on synthetic texts."""

from __future__ import annotations

from tests import skill_surface as ss
from tests.skill_surface import CODE, HELP, PLAN, PUBLIC, SkillRow

ENGINE = "src/rietx/model/x.py"


def _codes(*codes: str) -> str:
    return "\n".join(f'warn(code="{c}")' for c in codes) + "\n"


def _row(text: str, n: int = 1, code: bool = False) -> SkillRow:
    return SkillRow("docs/skill/rietx/references/r.md", n, text, code)


def test_each_vocabulary_is_read_from_its_own_file():
    texts = {
        ss.INIT: '__all__ = ["Refinement", "fit"]\n',
        "src/rietx/schemas/results.py": "class RefinementResult(Base): ...\nclass _Hidden: ...\n",
        ss.STAGED: ("PLAN_PRESETS = {n: f(b) for n, b in "
                    "{'lab_calibrate': 1, 'profile_only': 2}.items()}\n"),
        ss.HELP_MODULE: ("PARAMETER_HELP: dict[str, int] = {'phases.*.scale': 1}\n"
                         "STAGE_FIELD_HELP = {'turn_on': 2}\nOTHER = {'x': 3}\n"),
        ENGINE: _codes("CELL_RUNAWAY") + 'f(code="lowercase")\n',
        "src/rietx/gui/server.py": _codes("NOT_FOUND"),
    }
    assert ss.vocabulary(texts) == {
        "Refinement": {PUBLIC}, "fit": {PUBLIC}, "RefinementResult": {PUBLIC},
        "lab_calibrate": {PLAN}, "profile_only": {PLAN},
        "phases.*.scale": {HELP}, "turn_on": {HELP}, "CELL_RUNAWAY": {CODE},
    }


def test_the_walk_reads_the_live_vocabularies():
    """The AST walk over the real tree against what the package says at import."""
    import rietx
    from rietx import help as rx_help
    from rietx.strategy.staged import PLAN_PRESETS

    root = ss.ROOT
    texts = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
             for p in sorted((root / "src" / "rietx").rglob("*.py"))}
    vocab = ss.vocabulary(texts)
    by_kind = {k: {n for n, kinds in vocab.items() if k in kinds}
               for k in (PUBLIC, PLAN, CODE, HELP)}
    assert by_kind[PLAN] == set(PLAN_PRESETS)
    assert by_kind[HELP] == {k for name in rx_help.__all__ if name.endswith("_HELP")
                             for k in getattr(rx_help, name)}
    assert set(rietx.__all__) <= by_kind[PUBLIC]
    assert len(by_kind[CODE]) >= 60


def test_a_removed_name_still_in_the_skill_fails_naming_its_rows():
    before = ss.vocabulary({ENGINE: _codes("OLD_CODE", "KEPT")})
    after = ss.vocabulary({ENGINE: _codes("KEPT")})
    rows = [_row("| `OLD_CODE` | do this |", 7), _row("| `KEPT` | other |", 8)]
    found = ss.touches(before, after, [], rows)
    assert [(t.name, t.why, t.fails) for t in found] == [("OLD_CODE", "removed", True)]
    (message,) = ss.failures(found)
    assert message.startswith(
        "OLD_CODE (diagnostic code) was removed from src/ and the skill still "
        "names it at docs/skill/rietx/references/r.md:7.")
    assert "FAILS: removed" in ss.report(found, "a base")


def test_a_removed_name_the_skill_never_named_passes():
    before = ss.vocabulary({ENGINE: _codes("OLD_CODE")})
    found = ss.touches(before, {}, [], [_row("nothing here")])
    assert [(t.name, t.why) for t in found] == [("OLD_CODE", "removed")]
    assert ss.failures(found) == []


def test_added_and_changed_line_names_print_rows_and_pass():
    before = ss.vocabulary({ss.INIT: '__all__ = ["refine_sequential", "Quiet"]\n'})
    after = ss.vocabulary({ss.INIT: '__all__ = ["refine_sequential", "Quiet", "NewThing"]\n'})
    diff = ("--- a/src/rietx/sequential.py\n+++ b/src/rietx/sequential.py\n"
            "@@ -1 +1 @@\n-def refine_sequential(a):\n+def refine_sequential(a, b):\n")
    rows = [_row("Call `rx.refine_sequential(...)` for a ramp.", 3),
            _row("`NewThing` does it.", 4)]
    found = ss.touches(before, after, ss.changed_lines(diff), rows)
    assert [(t.name, t.why, [r.line for r in t.rows]) for t in found] == [
        ("NewThing", "added", [4]),
        ("refine_sequential", "on a changed line", [3]),
    ]
    assert ss.failures(found) == []
    text = ss.report(found, "a base")
    assert "references/r.md:3: Call `rx.refine_sequential(...)`" in text
    assert "`references/r.md:4`" in ss.report(found, "a base", markdown=True)


def test_diff_headers_are_not_changed_lines():
    diff = "--- a/src/rietx/x.py\n+++ b/src/rietx/x.py\n@@ -1 +1 @@\n-old\n+new\n ctx\n"
    assert ss.changed_lines(diff) == ["old", "new"]


def test_a_name_sharing_a_prefix_is_not_matched():
    assert not ss.mentions("CELL_RUN", _row("| `CELL_RUNAWAY` | ... |"))
    assert not ss.mentions("fit", _row("`rx.fit_sequential(...)`"))
    assert not ss.mentions("index", _row("`index_pattern`"))
    assert ss.mentions("CELL_RUNAWAY", _row("| `CELL_RUNAWAY` | ... |"))
    assert ss.mentions("fit", _row("`Refinement.fit(plan=...)`"))
    # and on a changed line of the diff
    before = ss.vocabulary({ENGINE: _codes("CELL_RUN")})
    assert ss.touches(before, before, ['code="CELL_RUNAWAY"'], []) == []


def test_a_word_like_name_counts_only_in_code():
    assert not ss.mentions("seed", _row("a seed that converges"))
    assert not ss.mentions("Phase", _row("Phase one of the plan"))
    assert ss.mentions("seed", _row("set `Stage.seed` to it"))
    assert ss.mentions("Phase", _row("phase = rx.Phase(...)", code=True))
    assert ss.mentions("turn_on", _row("its turn_on globs"))


def test_a_help_glob_matches_a_concrete_dot_path():
    assert ss.mentions("phases.*.cell.*", _row("free `phases.0.cell.a` first"), glob=True)
    assert ss.mentions("phases.*.cell.*", _row("`set_vary(['phases.1.cell.c'])`"), glob=True)
    assert not ss.mentions("phases.*.cell.*", _row("free `phases.0.scale`"), glob=True)
    assert not ss.mentions("phases.*.cell.*", _row("free phases.0.cell.a"), glob=True)
    assert not ss.mentions("phases.*.cell.*", _row("`phases.0.cell.a`"))


def test_a_removed_glob_is_excused_where_a_surviving_key_covers_the_path():
    before = ss.vocabulary({ss.HELP_MODULE: "P_HELP = {'phases.*.cell.a': 1, 'phases.*.old': 2}\n"})
    after = ss.vocabulary({ss.HELP_MODULE: "P_HELP = {'phases.*.cell.*': 1}\n"})
    rows = [_row("free `phases.0.cell.a`", 1), _row("free `phases.0.old`", 2)]
    found = {t.name: t for t in ss.touches(before, after, [], rows)}
    assert found["phases.*.cell.a"].rows == ()
    assert [r.line for r in found["phases.*.old"].rows] == [2]
    assert [m.split(" ")[0] for m in ss.failures(list(found.values()))] == ["phases.*.old"]
