---
description: >-
  Should fire. Tier 0, triggering. A task the skill's description names; the skill should load before any fit.
tags: [trigger]
runs: 3
max_turns: 4
timeout_seconds: 180
allowed_tools: [Read, Grep, Glob, Skill]
---
We have twelve candidate structures from a crystal-structure-prediction run, as CIFs. Score each one against our measured powder pattern and rank them.
