# WP-1967 — what the chemist declares reaches the extinction screen

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: 1910 soft (the screen's default, PR #939, shares this work's functions)
Priority: P2 2026-10-14 — was P3 (a workaround covers it: the user drops the groups by hand after the screen); up a rung because PR #940 builds it and what remains is its review

## Goal

A caller can declare what the chemistry rules out (an enantiopure, a
centrosymmetric or a polar compound), and the extinction screen drops the
space groups that contradict the declaration from each class and names them.
With nothing declared the screen still gives a good answer, and no caller is
made to declare anything.

## Context

**Source.** Issue #935 (2026-10-13). `determine_extinction_symbol` returns
classes whose members a powder cannot separate
(`EXTINCTION_GROUPS_NOT_SEPARABLE`) and leaves the choice to chemistry. There
is no way to state the chemistry, so the user drops groups by hand. The
issue's case is a P2₁ organic salt (Z = 2, structure from a published SI). The
screen answers `P 1 2₁ 1` = {P2₁, P2₁/m} at ΔBIC −61.7 on two testable 0k0
absences, and a declared chirality leaves P2₁. The issue also asks for a
Laue-class fork inside a class. `P - - -` on a hexagonal lattice holds P6/m
and P-31m, which differ only in how overlapped multiplets partition, so a
structure solution that follows runs once per Laue class rather than once
per member.

**Checked against the tree at `ee589bab`.** `determine_extinction_symbol` is
`indexing/extinction.py:705` and `EXTINCTION_GROUPS_NOT_SEPARABLE` is
`indexing/diagnostics.py:890`. The screen takes no declaration and groups no
members by Laue class. The issue's ΔBIC comes from its own data and was not
reproduced here.

**Decided 2026-10-14** (the maintainer, answering the PR-review batch): yes,
as PR #940 builds it. Two conditions bind the work. The screen's default must
be good when nothing is declared, and no caller is ever made to declare. The
PR's questions, and one from the review, answered:

1. Z and density as a member filter: a follow-up, outside #940. It needs
   Wyckoff multiplicities, which gemmi does not ship.
2. A class the declaration empties is still fitted (about 0.1 s a class).
   That fit is how a wrong declaration shows up.
3. `restrict` is not carried on to `IndexingResult` or
   `structure_from_candidate` now. The screen is where the choice is made.
4. A declaration may steer `best_or_none`. It picks among the classes the
   declaration leaves a member in, and abstains when the data prefer an
   emptied class by the decisive margin. Every removed group is reported.

**Rules that bind the work.** `INDEXING_THRESHOLDS_VERSION` bumps when an
answer can move. Each fact is read off the group's operators, never a table:
gemmi's `is_sohncke` and `is_centrosymmetric`, and polarity as an invariant
vector shared by every rotation. A new diagnostic code needs its skill row.

### Inherited

- **2026-10-14, from the issue triage: issue #935 is in PR #940 (theirs,
  head `edb3b74b`).** It adds `restrict=` on `determine_extinction_symbol`
  (`rx.ExtinctionPrior(sohncke, centrosymmetric, polar)`, each `None`, `True`
  or `False`), `ExtinctionCandidate.excluded_groups` and `.laue_classes`, and
  the codes `EXTINCTION_PRIOR_APPLIED` and `LAUE_CLASS_NOT_SEPARABLE`. With
  nothing declared no ranking and no `best_or_none` moves, and the Laue
  diagnostic is the one change a caller sees. It shares
  `determine_extinction_symbol`, `extinction_diagnostics`, `best_or_none` and
  the thresholds version with PR #939 (WP-1910). Whichever merges second
  renumbers 1.10 to 1.11.

## Non-goals

- The screen at a small cell error, and its default prefit (WP-1910, PR #939).
- The blind search's use of what the chemist knows (WP-1510).
- Z and density inside #940 (decided as a follow-up, a task below).

## Tasks

- [x] **Decision (maintainer):** the issue's proposal, whole or in part,
      recorded as `Decided YYYY-MM-DD:` here and answered on #935.
      *Decided 2026-10-14: yes, as PR #940 builds it (Context).*
- [ ] Review and merge PR #940 against the two conditions: answers with
      nothing declared stay as on `main`, and `restrict` stays optional on
      every surface.
- [ ] Follow-up: Z and density as a member filter, from Wyckoff
      multiplicities derived off the operators.
- [ ] Tests (#940 carries `tests/test_extinction_prior.py`), and
      `tests/test_acceptance_indexing.py` green.
- [ ] Skill: the two new codes' rows (#940 puts them in
      `references/abstention.md`, since `diagnostics-indexing.md` is over its
      budget).

## Acceptance

A declared chirality removes every non-Sohncke member and names it. A
declaration the data contradict ends in an abstention, never in the declared
answer. With nothing declared, every extinction screen in the tree answers as
on `main`.

```sh
.venv/bin/python -m pytest tests/test_extinction_prior.py tests/test_extinction_symbol.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #935; PR #940.
- Flack, H. D. (2003). *Helv. Chim. Acta* 86, 905: the Sohncke groups, the
  ones a chiral compound can occupy.
- Markvardsen, A. J., David, W. I. F., Johnson, J. C. & Shankland, K. (2001).
  *Acta Cryst.* A57, 47: a powder measures the extinction symbol.

## Handover log

- **2026-10-14** — created, from the 2026-10-14 issue triage (issue #935).
  Checked against the tree at `ee589bab`: both symbols the issue names exist
  where cited, and nothing lets a caller declare chemistry to the screen. No
  open WP owns it. WP-1910 holds the screen's behaviour at a small cell
  error, which the issue fences out ("about declaring the chemistry, not the
  cell"). WP-1510's chemistry reaches the search, not the screen, and every
  task there has landed. The maintainer decided it the same day (Context).
  *Next:* PR #940's review.
