---
name: Design proposal
about: A feature or design change that is not scheduled yet
title: 'Proposal: '
labels: proposal
---

<!--
Write the design here rather than in a WP file. The maintainer opens the work
package and the ROADMAP row when the work is scheduled, and links back to this
issue. See CONTRIBUTING.md, "Proposing something that is not scheduled".

Bugs, questions and "does rietx do X" go in a blank issue instead.

The headings below are a starting shape, not a form. Delete the ones that do
not apply and add your own.
-->

## What it would do

What someone refining a pattern gets that they cannot get today.

## Prior art

How TOPAS, GSAS-II or FullProf shape this, and the papers behind it. Take
concepts only from GPL sources (BGMN, Profex, xrayutilities). TOPAS and
FullProf are closed, so papers only.

## What it touches

Schema fields, modules, and any existing behaviour that would change.

## What would show it works

The record field, diagnostic or measurement that would demonstrate the
correction is right. An Rwp comparison does not: of the eight corrections
measured for v0.5, two provably cannot move Rwp, one moves it the wrong way
when it is right, and the two largest accuracy wins are invisible in it
(`docs/milestones/v0.5.md`).

## Questions left open

Decisions that would cost a schema change if they were made late:
normalisation conventions, where a field is declared, defaults.
