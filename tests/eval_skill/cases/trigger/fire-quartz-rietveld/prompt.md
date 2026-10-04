---
description: >-
  Should fire. Tier 0, triggering. A task the skill's description names; the skill should load before any fit.
tags: [trigger]
runs: 3
max_turns: 4
timeout_seconds: 180
allowed_tools: [Read, Grep, Glob, Skill]
---
I have a lab XRD pattern of quartz, quartz.xy (Cu Kα, Bragg-Brentano), and the quartz CIF. Run a Rietveld refinement with rietx and tell me the refined cell.
