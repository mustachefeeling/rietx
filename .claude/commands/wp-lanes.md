---
description: Lane trial — start a WP session as /wp-start does, but send long, late checklist items to subagents
argument-hint: "[WP number]"
---

Start a session with this command in place of `/wp-start`, as
`/wp-lanes NNNN`. The session then works exactly as a `/wp-start` session does,
with one change. Once its context is large, a long checklist item goes to a
*lane*: a subagent that does the item while this session waits, then checks
the diff and commits it.

It is a trial. A replay of 174 WP sessions predicted that this policy cuts a
session's reads and writes by 19-28% (`docs/milestones/process.md` § Lanes
within a WP). The replay had to assume three numbers, and this trial measures
them. It also measures how well a session guesses an item's length, and how
often a lane's work needs fixing or redoing.

1. **Run `/wp-start` first.** Invoke it with the Skill tool and pass on this
   command's arguments unchanged: `$ARGUMENTS`. With none, `/wp-start` picks
   the WP as it always does. Carry its ritual through to the restatement, and
   add one line there: this session runs under the lane trial. Then work the
   checklist straight through, as any WP session does. Nothing in this
   command stops for the user.

2. **Find this session's id.** It is the name of the directory that holds
   your scratchpad. `python3 .claude/hooks/session_usage.py context
   <session-id>` prints the main context now. Run it once, before the first
   item, to check the id.

3. **Decide each item when you start it.**
   - Read the main context with the command above.
   - Estimate how many requests the item will take. A request is one round of
     tool calls. Here the median item takes 15 requests and one in ten takes
     65 or more. Implementing and testing a feature usually passes 20. A doc
     edit, an index regeneration or a one-line fix usually does not.
   - **Lane the item if the context is over 150K and the estimate is 20 or
     more.** Do anything else yourself. Below that line a lane costs more than
     it saves (the record's crossover table).
   - Write the decision as a line of its own, in exactly this form:
     `lanes: keep <item> ~<N>` or `lanes: lane <item> ~<N>`. `<item>` is the
     checklist item's short name and `<N>` the estimate. Write it for kept
     items too. The measurement compares every estimate with what happened.

   Keep an item that needs the user partway through, or a decision only this
   session can make, whatever its size. The handover is never laned. Reading
   to reach a conclusion is `/wp-start` step 6b's business.

4. **Dispatch the lane** with one `Agent` call.
   - `subagent_type: general-purpose` on the default model. The description is
     exactly `lane: <item> ~<N>`, matching the decision line. The measurement
     finds lanes by that prefix.
   - Run one lane at a time, in this worktree, with no `isolation`. Wait for
     its completion notification. Leave its files alone meanwhile.
   - The prompt carries what the lane cannot see. A lane loads the CLAUDE.md
     files but no MEMORY.md, and it knows nothing this session learned. Give it:
     - the WP file's path and the checklist item, verbatim;
     - what this session found that the item depends on, as `file:line`
       pointers (the lane reads them itself, so leave the text out);
     - each memory rule that bears on the item, restated in a line;
     - the acceptance: the tests to run, and what done means. Name the fast
       selection for the touched area. A lane never runs the full suite.
   - Tell it to leave git and the WP file alone: no commit, no tick, no push.
     Those stay here. It ends with a report under 300 words: the files it
     changed, the tests it ran with their counts, and anything unresolved,
     with `file:line`.

5. **Check it, then commit it.** Read the diff by file: `git diff --stat`,
   then ranges. Re-run the tests the lane ran. Fix small things here. If the
   lane got the item wrong, dispatch again with the same description. The
   measurement counts both: edits you make after a lane returns, and a second
   dispatch of the same item. Then commit with the `WP-NNNN:` prefix and tick
   the item in the same commit (`/wp-start` step 6). That commit closes the
   lane's window in the measurement.

**The measurement runs inside `/wp-handover`**, at its step 3b, because this
session dispatched lanes. The session invokes the handover itself as usual.
Step 3b puts the tables in the handover entry and a row in the record. The
diff audit in step 6 covers lane-written code like any other.

**What the table means.** Per lane it shows the main context at dispatch and
the lane's own size. *Re-read* is what the lane read of files this session had
already read. *Main requests* and *left in main* are what checking the lane
cost here, from dispatch to commit. *In-session $* prices the same work as if
this session had done it at its dispatch context, and *saved $* is the
difference. The lane side is measured. The in-session side is a model, the
same one the replay uses.
