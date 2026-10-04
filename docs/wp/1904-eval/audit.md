# Audit: `docs/skill/rietx/SKILL.md` (body) and its references

All line numbers are `SKILL.md` unless a file is named. The body below the frontmatter is 29 688 B. The budget in `tests/skill_caps.py` is `SKILL_BUDGET_BYTES = 17_000`, the agentskills.io limit of 5 000 tokens at the measured 3.4 B/token, so the body is 75 % over budget. The ceiling is 33 000 B.

**Constraints a rewrite must keep (tests):**
- `test_the_body_carries_the_judgement_core` pins the anchors `## 1.`, `## 2.`, `## 3.`, `## 4.`, `## 4b.`, `## 6.`, `## 10.` and the phrase "stop condition".
- `test_every_reference_file_is_reachable_from_the_body` pins the literal string `` `grep -rn NAME references/` ``.
- Every reference's H1 restates a body section number: judging "4/4b", abstention "6", numbers "5", diagnostics "7", surprises "8", history "9".
- Reference headings cite body rule numbers: judging "§2 rules 4-5", "§3 rule 8", "Step 9/12/13/14/16/17"; abstention cites "§7c/§7d/§7e/§8.15". Renumbering the body's rules means editing these headings in the same change.

---

## A. Structural defects

**Section numbers.**
- The body has §1, §2, §3, §4, §4b, §6 and §10, plus the unnumbered headings "The API" and "See also".
- §5, §7, §8 and §9 have no body section. They exist only as reference-file H1s: numbers.md = §5, diagnostics.md = §7, surprises.md = §8, history.md = §9.
- The routing table cites §5 (l.51), §7j (l.50), §7b-7f (l.54), §8 (l.53), §9/§9b/§9c/§9d (l.55-59). Inline prose cites §7d (l.76) and §8.1, §8.11, §8.12, §8.18, §8.29 (l.77, 88, 172, 175, 176). All of these resolve to files, not to body sections. A reader of the body sees a number sequence 1, 2, 3, 4, 4b, 6, 10 with no explanation of the gaps.
- l.30-32: "Sections 1-4 are ordinary Rietveld discipline …; sections 5-10 are specific to running it with no human at the plot." This is false for the current body. Of 5-10 the body holds only §6 and §10, and §10 (a worked default) is not specific to unattended running.
- **§-number collision with McCusker 1999.** "McCusker §7" (l.216), "McCusker §11" (l.232), and judging.md's "McCusker §9/§10" use the same `§N` notation as the skill's own §7/§9/§10. l.216 "McCusker §7 converges at ≤ 0.1" sits beside a routing table where §7 means diagnostics.
- l.317: "§10's full ladder". §10 is the worked default plus the stop conditions. The "ladder" is §4 steps 9-17. This is a mis-pointer.
- The worked-default code comments are numbered `# 1.` … `# 7.` (l.390-416). They collide with rules 1-7 and with §5: l.403 reads `# 5. numbers, not pixels`.

**Rule numbering (one global counter, 1-26).**
- Rules 1-3: l.125-136. Rules 4-5: l.149-157, under a §2 paragraph about Le Bail. Rules 6-8: §3. Rules 9-17: §4, called "steps", not rules (l.208, 233, 274). Rules 18-22: §6. Rules 24-26: §10.
- **Rule 23 is missing.**
- Rules 24-26 are not rules. They are the three clauses of one sentence ("Stop refining when", l.420-424), numbered as if they were standalone rules.
- l.122 introduces "Three ordering rules", then rules 4-5 continue the same counter under a different topic (Le Bail). Five rules under a heading that announces three.

**References that point into the body for content that moved.**
- l.208: "`print(result)` renders steps 9 and 17". The parenthetical lists "status, every diagnostic, provenance, agreement indices last". Agreement indices are step 16 (Rwp/GoF). Step 17 is R_Bragg. Either "9 and 17" means "9 through 17", or the step is wrong.
- l.80 "see §2 and §6": §2 says nothing about widths or frozen windows; §6 is abstention. The window claim's target is not in the body. (l.76 "§6" for `reindex_or_recheck_cell` is satisfied only through abstention.md's first row.)
- abstention.md l.24 points to "§7's note on reading it across a run". That note is in series.md (§9b) / diagnostics.md, not in a §7 section of the body.

**Routing table (l.46-60).**
- `references/api.md` is routed three times (l.48, l.49 "§ In", l.60 "§ Out") and a fourth time at l.446. l.438-447 ("The API") restate the l.48 row.
- No row for diagnostics.md (§7), diagnostics-reading/-projects/-gsas, or abstention.md. This is deliberate: the grep instruction at l.41-44 replaced code rows, measured at 17/18 vs 4/18 in `tests/eval_skill_placement`. abstention.md is reached only from l.370.
- `grep -rn NAME references/` assumes the agent's cwd is the skill directory. The installed copies live at `.claude/skills/rietx/references/` and similar, and the path is never stated.
- Seven "Both measurements / Why / Every … : [judging.md]" pointers to the same file: l.147, 159-160, 196, 211-212, 296, 333-334, plus routing l.52.

---

## B. Contradictions and suppositions

**B1. Le Bail first vs "a known structure is no Le Bail job".**
- l.138-141: "Structure-free first when you can … Do that first … it is the single most reliable way to avoid a structural minimum."
- l.151-152: "A known structure is no Le Bail job: use `lab_calibrate`." judging.md l.68 backs this: 43.8 s vs ~40 min.
- l.376 and l.390-391: the worked default ("A lab pattern, a CIF", i.e. a known structure) runs `ref.fit(data, mode="lebail", plan="profile_only")` first.
- The two cannot both be the default. In addition, `lab_calibrate` holds a **certified** cell (l.114, l.182-184). For a sample whose cell is not certified that is wrong advice; `lab_sample_refine` or `lab_bragg_brentano` is the plan for a sample (l.113-115).

**B2. The worked default violates rules 4 and 5.**
- Rule 4: "One `fit()` is not enough: set `plan.lebail_passes` (say 8)". The `lebail_passes` default is 1 in `strategy/staged.py:325`. l.391 passes a plan **string**, so it cannot carry `lebail_passes`, and the body never shows how to build a plan object.
- Rule 5: "Seed the background before the first pass, always". l.386 uses `auto_background(data)` unseeded, and the body gives no API for seeding (no path, no `set_values` call).
- The single most-copied block in the file contradicts the two rules placed nearest to it.

**B3. "Use the plans" vs "the sequence is a default".**
- l.92 heading: "why it is not negotiable".
- l.103: "Use them; do not hand-roll a free set unless you have a reason you can state."
- l.104-105: "the preset *sequence* is a default, because the right next group depends on the data".
- l.376-377: "Adapt … the right order depends on the data".
- The heading claims non-negotiability; the body then negotiates. The agent is given no criterion for when to leave the preset beyond "a reason you can state" and `ref.suggest`.

**B4. Rwp is not the objective, yet Rwp drives several rules.**
- l.27: "Rwp is not the objective function of your job." Literally, weighted χ² (∝ Rwp²) *is* the solver's objective. "Of your job" saves the sentence only on a careful reading.
- Against it: rule 4's stop rule is "the first pass that does not lower Rwp" (l.150). Rule 16 tells the agent to read Rwp/GoF (l.275). §4 calls Rwp "a useful *relative* number" (l.203-204).
- judging.md l.83: "Le Bail also won on Rwp … so a better Rwp does not show the cell is wrong or right". That undercuts rule 4's Rwp-based Le Bail stop.
- The defensible rule ("Rwp ranks fits of the same data over the same channels; it certifies nothing") is stated only at l.202-204, after three sections that presuppose it.

**B5. Never take `candidates[0]` vs the indexing reference.**
- l.348: "Never take `candidates[0]` because it is ranked first."
- diagnostics-indexing.md l.355: "A consumer that can weigh that is entitled to adopt the cell with its eyes open". That cell is rank 1, the fluorite worked example.
- abstention.md l.30: since WP-1046 `candidates[0]` is "corroborated, then best on the panel … closer to the gate's own reading".
- The body states an absolute rule that the reference qualifies.
- The loop in diagnostics-indexing.md l.189-191 ends at `if cell is None: ...` with no next step. The body gives no path forward when `best_or_none()` is `None`, which it calls "the most likely outcome" (l.350).

**B6. Three stop conditions vs per-deliverable stops.**
- l.420-428: three conditions, labelled structure-grade afterwards (l.427).
- l.311-317: §4b's "Stop when" column per deliverable, ordered *before* §10. The agent meets the deliverable stops first and the universal-sounding "three stop conditions" second.
- Condition 26 (l.424): "fails a ΔBIC test". l.290-292 and judging.md l.189-211 say ΔBIC at raw N blesses almost anything and must be charged at N/f² after a t-ratio check. Condition 26 omits both qualifiers, i.e. it states the test the file elsewhere calls broken.
- Condition 25: "Layer 1 attributes no remaining region". For a QPA or structure fit with `abstained_kind="immature"`, condition 25 is vacuously met, because nothing is attributed when Layer 1 abstains.

**B7. A cell that moved 0.5 % is implausible vs a starting cell within ~1 %.**
- l.76: the precondition tolerates a starting cell within ~1 %.
- l.229-230: rule 12 lists "a cell that moved 0.5 %" among physically impossible values.
- A 0.5 % move is what a 1 %-off start legitimately produces.

**B8. Width seed arithmetic.**
- l.80 gives `W ≈ (FWHM/2)²`, then says `W = 1e-3 deg²` corresponds to FWHM ≈ 0.03°. That is √1e-3 = 0.032, i.e. W = FWHM².
- The two halves imply different conventions. The unstated assumption is a half-Gaussian, half-Lorentzian split.
- `X ≈ FWHM` ignores X's angular factor. No parameter path (`instrument.profile.w`) and no way to measure the "median FWHM of the dozen most prominent peaks" (`pick_peaks`) is named.

**B9. "Quote no esd without its inflation" (l.237).**
- judging.md l.119 says the inflation is "already in every quoted esd, dividable back out".
- The body's imperative reads as an action the agent must take. The real rule is "the esds are already inflated; quote the trio beside them".

**B10. "The verdict that licenses is `ambiguous`" (l.246-247).**
- `ambiguous` is not a field value anywhere in the result types. It appears only as a docstring word in `report/schemas.py:813`. The agent is told to look for a verdict string that does not exist.
- l.259-262 then says a won swap is quoted "without caveat". l.430-433 requires unresolved diagnostics to be reported as systematics.
- The scope of "without caveat" (the exchange question only) is unstated.

**B11. Le Bail "single most reliable" (l.141) vs its cell "is the weaker half" (l.142-145).**
- The two sentences are adjacent. l.146: "on a resolved pattern skip the check". "Resolved" is defined only in judging.md (reflections per FWHM, 0.014 measured).

**B12. Undefined terms used as if known.**
- `f` in "ΔBIC at N/f²" (l.290). It is `esd_inflation`, per judging.md.
- "Le Bail gap" and the direction of its `ratio` (l.313-317). The body never says which Rwp is the numerator.
- "Layer 0/1/2": defined only in numbers.md.
- "frozen evaluation windows" (l.76, l.80).
- "the global maturity gate" (l.344).
- "δR line" (l.242).
- "capped confidence", "vetoed action" (l.329-330).
- `ZMV` (l.314).

**B13. Unverifiable "measured" appeals in the body.** None gives a number the agent can act on; each asks for trust.
- l.29-30: "Every rule below exists because one of those happened and was measured."
- l.122-123: "None is in the guidelines; each is this package's own measured finding."
- l.146-147: "both measured on external patterns".
- l.141: "the single most reliable way". A superlative with no measurement.
- l.260-261: "hedging a won swap is a measured failure rather than caution". The 0/7 is in judging.md l.147.
- l.28-29: "biased by 100 %, … wrong by 5 wt %". No source in the body.
- l.172: "5.2e-2 against 1.1e-5, a factor of ~4600". Precise but irrelevant to the action.
- l.320-322: "0.958 and 0.000 Å² … 0.46 against 0.08". Duplicated in judging.md l.283-290.

---

## C. Rhetorical overhead

Classification over 81 blocks (paragraphs, list items, tables, code), with mixed blocks split by estimated share:

| Class | Bytes | Share |
|---|---|---|
| (1) actionable rule | ~12 700 | 43 % |
| (2) evidence/justification | ~6 900 | 23 % |
| (3) rhetoric/framing | ~3 500 | 12 % |
| (4) routing/navigation/headings | ~4 400 | 15 % |
| (5) code | ~2 000 | 7 % |

Classes 2 and 3 together are ~10.4 kB, close to the 12.7 kB over budget.

**The 15 largest evidence + rhetoric loads** (block lines, block bytes, approximate class 2+3 bytes; whether the rule survives without them):

1. l.169-179, degeneracy table (2125 B, ~1490). The rows' last column carries prose plus numbers (Gram eigenvalues, "This is the big one", "Not 'correlated': singular"). **Survives** as group → signature → action. The µR, µt, capillary and extra-peak rows already live in surprises 8.1/8.12/8.18/8.23 and diagnostics.md.
2. l.73-80, preconditions table (1840, ~740). The "If you cannot" column is consequence prose. **Survives** as a checklist. The wavelength aside → §8.11.
3. l.138-147, Le Bail paragraph (801, ~480). **Survives** as two lines once B1 is resolved.
4. l.94-101, McCusker/Toby justification (556, ~445). **Survives** as one cited sentence.
5. l.279-288, R factors (734, ~440). Rule = "R_B/R_F are not evidence a correction helped; absent in Le Bail/Pawley; never compare a trace phase's". **Survives**.
6. l.202-206, Rwp framing + Hill (397, ~400). Pure evidence. **Survives** as one sentence.
7. l.254-263, the swap (777, ~390). **Survives**: "run `compare_rivals`; ratio ≥ 1.10 → adopt the winner; below → declare unresolved".
8. l.27-32, opening framing (445, ~360). Nothing actionable. **Delete**.
9. l.311-317, 4b table (2214, ~330). Mostly rule. Trim the Microstructure and Structure cells.
10. l.237-243, esd inflation (507, ~330). **Survives** in one line (see B9).
11. l.302-309, 4b intro (549, ~330). "No bar moves… answered exactly…". **Survives** as "declare the deliverable; read its row".
12. l.319-322, QPA example (300, 300). Duplicated in judging.md. **Delete**.
13. l.249-252, what converged means (271, 271). Duplicated verbatim in judging.md l.131-133. **Delete**.
14. l.22-25, audience statement (260, 260). **Delete**.
15. l.128-136, rules 2-3 justifications (~420 of 640). **Survive** as imperatives.

**LLM-prose tics (counted in the body):**
- **Contrastive negation ("X is not Y; it is Z" / "…, not …"): ~30.** Examples: l.27, 55, 68-69, 92, 96 ("The reason is not tradition"), 104, 166-167 ("They are not bugs; they are the geometry"), 171, 173, 175, 188-189, 219, 240, 246-247, 260-261, 305, 316 ("is not a smaller number to quote, it is a wider 2θ range"), 324-325 (twice), 346-347, 351, 353, 356, 359, 363, 434.
- **Aphoristic closers / epigrams: ~11.** "A poor start wanders." (151); "No sentence converts a tie into an answer." (262); "A number without its protocol is not a measurement." (433); "There is no ceiling: the report supplies evidence, judgement stays with the reader." (330); "When they do, that *is* the answer." (341); "the most common misreading of the clause" (267); "Every rule below exists because…" (29); "the two are different questions" (349-350); "the information is absent from the measurement, not buried in noise" (359); "This is the big one." (174); "None is in the guidelines" (122).
- **Intensifiers/emphatics: ~10.** "not negotiable" ×2 (92, 104); "Memorise these" (164); "This is the big one" (174); "The package's hardest rule" (340); "the single most reliable" (141); "always" (153); "almost never" (188); "and never alone" (275); "and never in isolation" (279). The last two are the same intensifier in consecutive rules.
- **Triads: 6.** l.23-25 ("what to do, in what order, what to check"); l.28-30; l.68-69 ("not structure solution, not phase identification, and not a search"); l.349-350; l.360 ("Extend the range, report both, or carry the whole list forward"); l.431-433.
- **Bold-lead sentence followed by a restatement: ~12.** l.186-187 bolds "refined one parameter and reported two", then restates it; l.340-341 restates the §6 heading; rule 18 (l.343) restates the heading again; l.353, 356, 363 each bold an aphorism then define it; l.324 restates the 4b table cell at l.313; l.426-428 restates the 4b QPA cell at l.314.
- **Emphasis density:** 72 bold spans in 29.7 kB, about one per 410 B. Emphasis no longer discriminates.
- **Headings as slogans:** "why it is not negotiable", "Memorise these", "Abstention is a result. Do not convert it into a number", "'good enough' is a question about purpose".

---

## D. Duplication between body and references

| Body (lines) | Restated in | ~B that can leave the body |
|---|---|---|
| 82-88 measured blank | surprises 8.29 | 100 |
| 77 wavelength aside | surprises 8.11 | 250 |
| 94-101 McCusker/Toby | judging (not needed) / manual | 350 |
| 138-160 Le Bail + rules 4-5 | judging "§2 rules 4-5" (l.64-86), near-verbatim | 900 |
| 169-179 µR, µt, capillary, extra-peak rows | surprises 8.1, 8.12, 8.18, 8.23; diagnostics `EXTRA_PEAK_ON_REFLECTION` | 700 |
| 186-189 rule 7 | diagnostics `HIGH_CORRELATION` | 100 |
| 190-196 rule 8 | judging "§3 rule 8" | 300 |
| 202-206 Rwp/Hill | judging Step 13 (Hill) | 300 |
| 214-218 rule 9 | judging Step 9 (two sections) | 200 |
| 229-236 rule 12 | judging Step 12 | 250 |
| 237-243 rule 13 | judging Step 13 | 330 |
| 244-267 rule 14 | judging Step 14; l.250-252 and l.265-267 near-verbatim to judging l.131-133 and 157-160 | 1 000 |
| 275-278 rule 16 | judging Step 16 | 100 |
| 279-288 rule 17 | judging Step 17 | 400 |
| 290-296 ΔBIC, other codes | judging §4 (two sections) | 250 |
| 302-309 4b intro | judging "why no bar moves" | 350 |
| 316 microstructure cell | judging Microstructure | 300 |
| 319-322 QPA example | judging §4b QPA, verbatim numbers | 300 |
| 324-326 resolution_limited | abstention row 1 | 150 |
| 340-367 §6 intro + rules 18-22 | abstention.md l.1-9 (verbatim title and first lines), rows `abstained_reason`, `gates_passed`, non-separable, `PAWLEY_OVERLAP_UNRESOLVED`, `best_or_none` (rule 19 near-verbatim), `INDEX_*`, `EXTINCTION_GROUPS_NOT_SEPARABLE`, `PHASE_UNCONSTRAINED`, `STEPHENS_STRAIN_NOT_POSITIVE` | 1 300 |
| 438-447 The API | routing l.48 | 250 |
| **Total** | | **~8 200** |

Further cuts outside the duplication:
- Removing class 3 (~3 500 B) and compressing the routing table (2 129 B; dropping "§N —" prefixes and long *When* prose saves ~800) brings the body to about 17-18 kB, at the budget, without losing a rule.
- No body rule's *evidence* is absent from the references. The only content unique to the body is the rule statements, the plan list, the deliverable table and the worked default.

---

## E. What an agent needs at fit time that the body does not give crisply

1. **A resolved first-call sequence.** B1/B2 leave the agent unsure whether to Le Bail first. When it does, it is not shown how to set `lebail_passes` (needs a `RefinementPlan` object, not a string) or how to seed the background constant.
2. **Plan by data type.** Seven plan names with one-line comments (l.111-117), with no decision rule. Lab BB with CIF → `lab_bragg_brentano`? Synchrotron capillary → `mccusker_structural` with `debye_scherrer`? Calibrated instrument → `load_instrument_profile` + `lab_sample_refine` (the workflow is in CLAUDE.md, not the skill body)? Unknown cell → §7d. `PLAN_INFO` is named but not shown.
3. **Instrument construction beyond lab Cu.** Synchrotron wavelength, `.prm` loading and `flat_plate_transmission` are not shown. l.77 says "from the beamline `.prm`" with no call.
4. **Profile-width seeding.** No parameter path or call, and the arithmetic is inconsistent (B8).
5. **Multi-phase setup.** "`Structure.from_cif` per phase" (l.75), but the worked default shows a single `Structure` and never shows how a list is passed.
6. **A single usability branch.** `result.usable` (judging.md l.27-29: `status == "converged"` and no `"error"` diagnostic) is the one-line gate a driver needs. The body never names it.
7. **How to read `print(result)`.** Only the l.208 parenthetical, which is itself confused (A). No description of the order of blocks or what to look at first.
8. **Top diagnostics → action.** The body names ~15 codes in prose. It never says "act on `d.suggestion` first, then grep the code", though the worked default prints `d.suggestion`. The responses for `HIGH_CORRELATION`, `BOUND_HIT`, `BACKGROUND_ABSORPTION`, `PHASE_UNCONSTRAINED` and `MODEL_FAR_FROM_DATA` are scattered over §3, §4, §6 or absent.
9. **The `vary=False` trap.** A plan replaces vary flags (surprises 8.25; `ref.hold`). Every hand-pinned-parameter fit needs this, and it is not in the body.
10. **Executing a Layer-2 suggestion.** `report.actions`, `ref.suggest`, `predict_then_verify` and the branch/rollback pattern appear only in passing (l.106, l.328). There is no three-line recipe.
11. **QPA output.** `result.qpa…weight_fraction` and the profile-fraction check (`ref.profile_fraction`) are named in the 4b table only by reference. The field path for a fraction is absent.
12. **Fit range and excluded regions.** `two_theta_limits` appears only as an `auto_background` argument. How to restrict the fitted range or exclude a region is absent.
13. **Writing the answer.** `write_refinement_cif` and the QPA table are only behind the l.60 routing row. "What to report" (l.430-434) lists contents but no calls.
14. **What to do when `max_shift_over_esd` is large** on a converged stage: bound the parameter, look for a correlation pair (judging.md l.17-20). The body only says to read the number.

---

## F. Size per file (bytes / 3.4 = tokens; whitespace words)

| File | Bytes | ~Tokens | Words |
|---|---|---|---|
| SKILL.md (whole) | 30 630 | 9 009 | 4 478 |
| SKILL.md body below frontmatter | 29 688 | 8 732 | n/a |
| abstention.md | 18 276 | 5 375 | 2 971 |
| api.md | 39 605 | 11 649 | 5 390 |
| api-figure.md | 8 462 | 2 489 | 1 321 |
| api-magnetic.md | 4 160 | 1 224 | 593 |
| batch.md | 23 304 | 6 854 | 3 719 |
| batch-operating.md | 18 502 | 5 442 | 3 035 |
| diagnostics.md | 34 972 | 10 286 | 5 643 |
| diagnostics-gsas.md | 23 878 | 7 023 | 3 744 |
| diagnostics-indexing.md | 35 103 | 10 324 | 5 431 |
| diagnostics-projects.md | 20 546 | 6 043 | 3 281 |
| diagnostics-reading.md | 13 253 | 3 898 | 2 212 |
| history.md | 8 009 | 2 356 | 1 201 |
| judging.md | 33 609 | 9 885 | 5 383 |
| magnetic.md | 27 637 | 8 129 | 4 287 |
| numbers.md | 9 089 | 2 673 | 1 352 |
| series.md | 34 599 | 10 176 | 5 479 |
| surprises.md | 34 593 | 10 174 | 5 560 |
| watching.md | 9 761 | 2 871 | 1 638 |
| **Total skill tree** | 427 988 | 125 879 | 66 718 |

A session that loads the body plus `api.md` (the l.48 row, "about to call rietx") pays ~20 700 tokens before its first fit. Adding judging.md, which seven body pointers send it to, makes ~30 500.
