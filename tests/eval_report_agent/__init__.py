"""Agent-in-the-loop FitReport eval (WP-1053; protocol 2.0 is WP-1064).

Episode fixtures + a condition-enforcing shim + a deterministic scorer for
measuring whether the FitReport helps a real LLM agent reach the right
epistemic outcome through the shipped surfaces.  No LLM dependency lives
here: the runs happen in the Claude Code harness (see PROTOCOL.md).
Pytest collects ``test_scorer.py`` (fast, synthetic), ``test_landing_states.py``
(slow — the registered episode measurements) and ``test_mine_transcripts.py``
(the round-record miner).
"""
