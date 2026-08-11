"""Agent-in-the-loop FitReport eval (WP-1053).

Episode fixtures + a condition-enforcing shim + a deterministic scorer for
measuring whether the FitReport helps a real LLM agent converge a refinement
through the shipped ``agent.refine_json`` surface.  No LLM dependency lives
here: the runs happen in the Claude Code harness (see PROTOCOL.md), and the
only pytest-collected module is ``test_scorer.py``.
"""
