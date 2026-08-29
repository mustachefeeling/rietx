"""Agent-surface round harness (WP-1110 registered 1.0; WP-1307 registers 1.1).

What an agent *reaches for* when handed files and a job, measured by a shim in
the experiment venv rather than asked for in a prompt.  `PROTOCOL.md` is the
authority for every round; `score_round.py` scores 1.0 and says so.  Nothing
here runs an LLM: the runs happen in the Claude Code harness, and what pytest
collects is the harness's own machinery — `trail.py`'s two attribution rules and
`episodes/ramp.py`'s reproduction of the episode it rebuilds.

A cell here pools with nothing in `tests/eval_report_agent/`, and a 1.1 cell
pools with nothing in 1.0 (tests/CLAUDE.md § Two eval protocols).
"""
