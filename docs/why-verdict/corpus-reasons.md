# The corpus: every reason written to this canvas, oldest first

One entry per commit in `./corpus-store`, in `git log --reverse` order.
Generated from the repository, not retyped; the reason text is the commit
subject with the leading `<verb> <target>: ` removed, reproduced verbatim and
complete — no entry is truncated, however long.

## What this file contains

- **Total entries: 55.** One per commit; `git -C corpus-store rev-list --count HEAD` = 55.
- **The review must judge entries 1 to 50.** That is the *first fifty reasons*
  the task and `engineering-spec.md:423` name. Entries 51 to 55 are present
  below for completeness and are **outside** the fifty the verdict rules on.
- **The `create` commit counts as entry 1.** Taken as given, and stated here so
  nothing downstream has to re-decide it: `0b2e20b` is entry 1, and the
  fifty the review judges therefore run from the `create` commit through entry 50
  (`b62b428`).
- The `create` commit writes no `Canvas-Node:` trailer — `canvas/cli.py:205-206`
  says the birth of a canvas has no prior node — so its node id is rendered `-`.
  Its subject names the ledger id where the other verbs name a node id.

## Field meanings

- **sha** — short commit sha in `./corpus-store`.
- **verb** — the first word of the commit subject.
- **node** — the `Canvas-Node:` trailer's value, or `-` for the `create` commit.
- **author** — the `Canvas-Author:` trailer's value, verbatim.
- **reason** — the commit subject after `<verb> <node-id>: `, verbatim and whole.

## Composition, for orientation only

- Entries 1–50 — `lfigea | by-hand`: 43 · `claude-opus-5 | second-writer`: 7
- Entries 1–55 (whole corpus) — `lfigea | by-hand`: 48 · `claude-opus-5 | second-writer`: 7
- Verbs in 1–50 — `insert`: 39 · `replace`: 10 · `create`: 1
- The `second-writer` arm is entries 37–43, contiguous, all inside the fifty.
- Who actually typed the `by-hand` arm is settled in `./corpus-provenance.md`.
  Read that before treating the two arms as human versus model.

Corpus HEAD: `02de26b71893d1d33d1559cd0fd9bcfcaff84652`

---

## Entries 1–50 — the reasons under review

### 1. `0b2e20b` — create `-`

- **author:** `lfigea | by-hand`
- **subject target:** `bc-10329619223-errno-decides-the-repository-refusals` (ledger id, not a node id)
- **reason:**

> born at open, root only

### 2. `d65e081` — insert `bpx2`

- **author:** `lfigea | by-hand`
- **reason:**

> the problem the ledger row states

### 3. `e694e94` — insert `bcr2`

- **author:** `lfigea | by-hand`
- **reason:**

> the expected value the ledger row states

### 4. `7fcaeff` — insert `hp9p`

- **author:** `lfigea | by-hand`
- **reason:**

> the todo leaves this genuinely undecided and says so: 'Decide which is right and make the code say so'. Filing it as a section so the question and the options it is weighed against sit together, rather than as loose siblings a later reader has to associate by adjacency.

### 5. `94ce546` — insert `t8zw`

- **author:** `lfigea | by-hand`
- **reason:**

> recording the question in the words the todo asks it in, before anything is decided. It is the one thing in Case 1 that is not mechanical: the five call sites are known, the errno table is known, and only this is open.

### 6. `8467e0f` — insert `uz6x`

- **author:** `lfigea | by-hand`
- **reason:**

> the options for question 1 and what each one costs, as a table, because this is the shape the replace verb is meant to settle into a decision later. Empty for one commit: the tool brings exactly one node per edit, so the table arrives before any row it will hold.

### 7. `b7a301d` — insert `s437`

- **author:** `lfigea | by-hand`
- **reason:**

> the header row: the table has two columns and nothing else in the vocabulary can say so, since a <table> carries no column names and a <cell> carries no header flag.

### 8. `525ab66` — insert `sm4b`

- **author:** `lfigea | by-hand`
- **reason:**

> column one names the option. A header cell is an ordinary <cell>; the vocabulary has no other kind, so 'this row is the header' is carried by its position and by nothing else.

### 9. `65c0377` — insert `zyrd`

- **author:** `lfigea | by-hand`
- **reason:**

> column two is the cost, not the argument for it. The todo is explicit that this is a decision to be made, so what each route gives up is the thing worth having written down when somebody asks later why the other one was not taken.

### 10. `28985c6` — insert `fu7f`

- **author:** `lfigea | by-hand`
- **reason:**

> option A's row. One row per option so that each one can be read, argued with and eventually struck out on its own.

### 11. `f54cd5a` — insert `mkyr`

- **author:** `lfigea | by-hand`
- **reason:**

> the route the todo names first and the one the parent change's own rule points at. Writing it down as an option rather than as the answer, because the five call sites are not all alike and that is what has to be weighed.

### 12. `8021671` — insert `lgvs`

- **author:** `lfigea | by-hand`
- **reason:**

> the cost is the part a decision three weeks old is no longer able to reconstruct. Naming the call sites individually because 'classify by errno' sounds uniform and the five places it lands are not.

### 13. `a41ca41` — insert `pjt3`

- **author:** `lfigea | by-hand`
- **reason:**

> option B's row. The todo offers it explicitly as the other half of condition (1): 'or README.md section Exit codes states, in its own words, why a repository that vanished is 2 where a canvas file that vanished is 1'.

### 14. `6e29a84` — insert `ymcz`

- **author:** `lfigea | by-hand`
- **reason:**

> the todo treats this as a legitimate answer and not a cop-out, and it is: the two absences really are different kinds of thing. Recording it in the form condition (1) would accept, so that whoever settles this can take it without re-deriving the wording.

### 15. `2f10783` — insert `smym`

- **author:** `lfigea | by-hand`
- **reason:**

> the cost of B is not the prose, it is that prose is the only thing enforcing it. Writing that down because it is the argument a reviewer will make and it should not have to be made twice.

### 16. `bd1f849` — insert `nyah`

- **author:** `lfigea | by-hand`
- **reason:**

> option C's row. Not in the todo, but it is the route somebody will propose in review once option A's unevenness is pointed out, and an option that is only argued down in a review comment is an option nobody can find later.

### 17. `041147e` — insert `fbym`

- **author:** `lfigea | by-hand`
- **reason:**

> naming the third route in full so it can be rejected on its merits rather than never considered. It is the obvious answer to option A's cost cell and it needs an answer of its own.

### 18. `4545dd3` — insert `rt82`

- **author:** `lfigea | by-hand`
- **reason:**

> the cost here is that it re-introduces the thing the parent change closed. Saying so plainly, because from inside one call site it looks like the careful answer.

### 19. `2503e2c` — insert `y9hx`

- **author:** `lfigea | by-hand`
- **reason:**

> Case 2 of the todo, kept in its own section and deliberately not worked on here. A different writer takes this half, so the canvas has to carry the question in a state they can pick up without reading this one's shell history.

### 20. `9211127` — insert `mqxd`

- **author:** `lfigea | by-hand`
- **reason:**

> quoting the todo's own framing, which is careful to say this is not a bug report: 'this is not a broken repair - it is the unanswered question of whether a Canvas-Next: may name a command that exits non-zero at all'. That distinction is the whole of the question and it is the first thing a paraphrase loses.

### 21. `61ba4a9` — insert `ehxj`

- **author:** `lfigea | by-hand`
- **reason:**

> the options for question 2 and what each costs, in the same shape as question 1's so the two can be read the same way. Empty for one commit, as before.

### 22. `96276cf` — insert `rysw`

- **author:** `lfigea | by-hand`
- **reason:**

> the header row, matching question 1's two columns. Same shape, same reading.

### 23. `2cfb511` — insert `vp52`

- **author:** `lfigea | by-hand`
- **reason:**

> column one, as above.

### 24. `45bd148` — insert `be5v`

- **author:** `lfigea | by-hand`
- **reason:**

> column two, as above.

### 25. `8f38fae` — insert `vqpn`

- **author:** `lfigea | by-hand`
- **reason:**

> option A's row: no, it may not.

### 26. `96cd4bf` — insert `zksk`

- **author:** `lfigea | by-hand`
- **reason:**

> the strict reading, and the one condition (3) can be enforced mechanically: a test that runs every command and checks its status needs no list of which ones count.

### 27. `be92dab` — insert `qdvs`

- **author:** `lfigea | by-hand`
- **reason:**

> the cost of the strict rule is a real loss of information, not just a lost line of text. Saying which information, because 'we removed the ls' reads like tidying up.

### 28. `8c6da79` — insert `yh66`

- **author:** `lfigea | by-hand`
- **reason:**

> option B's row: yes, provided the reader can tell a diagnostic from a repair.

### 29. `0cdd29f` — insert `vgke`

- **author:** `lfigea | by-hand`
- **reason:**

> the other half condition (2) offers, written with the part the todo leaves implicit made explicit: 'says how a caller tells them apart' is a change to the refusal format, not only to the README.

### 30. `213a280` — insert `lp37`

- **author:** `lfigea | by-hand`
- **reason:**

> the cost of B is that 'write it down in the README' is not sufficient on its own, and that is easy to miss when reading condition (2) quickly. The test in condition (3) is what forces the distinction to be machine-readable or not to exist.

### 31. `5fa80e6` — replace `lgvs`

- **author:** `lfigea | by-hand`
- **reason:**

> the work made this cell wrong, not just thin. I wrote it saying option A's cost was that the five call sites are uneven; running the non-racy case showed the real cost, which is that _not_a_repository already answers 2 for the identical fact and exit 1 here would make the code a function of a race. Replacing rather than adding a note, because the old sentence would otherwise still be sitting there being the weaker argument.

### 32. `a78e225` — insert `bv2j`

- **author:** `lfigea | by-hand`
- **reason:**

> putting the reproduction in the canvas rather than only in a shell scrollback, because it changes what the question is. I came to this expecting to argue about 1 versus 2 and found two sentences that are false at either code. Placed directly under the question with --after, so a reader meets the evidence before the options it is supposed to weigh.

### 33. `35e25a1` — insert `nf98`

- **author:** `lfigea | by-hand`
- **reason:**

> the code moved and the canvas has to say so, or the next writer reads three open options and a green branch and cannot tell which of them is already in the tree. Writing it as a statement of where the code stands rather than as the decision, because the decision node is not mine to make here - the options table is still standing and a later pass settles it with replace.

### 34. `fe84545` — insert `echr`

- **author:** `lfigea | by-hand`
- **reason:**

> found while checking that Case 1's change did not quietly settle Case 2 for the other writer. It does not, and the count is the evidence. Recording the todo's own reproduce command being wrong here rather than only in my head, because the next writer will run it first, get a Canvas-Next with no ls in it, and lose an hour deciding whether somebody already fixed this.

### 35. `7a5b1f9` — insert `fdzu`

- **author:** `lfigea | by-hand`
- **reason:**

> the launch brief for this half said to branch from main, and branching from main would have produced a change to a function that does not exist there. Under guidelines/correction-authority.md the brief is the lowest authority and the todo description is higher, and the description cites canvas/store.py:582 by line - so the description wins and the base is PR #8's branch. Putting it at the top of the canvas because it is the first thing that would waste anybody else's afternoon.

### 36. `e950b24` — replace `echr`

- **author:** `lfigea | by-hand`
- **reason:**

> I wrote this node an hour ago off a grep for os_next_action and named four surviving call sites. Three of those four catch FileNotFoundError separately before the line I counted, so ENOENT never arrives there - checked by spying on the function rather than by reading the code again, because reading the code again is what produced the wrong count. Replacing rather than appending a correction, because the wrong number is the kind of thing a reader takes and acts on, and leaving it visible with a retraction under it is worse than one true sentence.

### 37. `f7be9ea` — replace `mqxd`

- **author:** `claude-opus-5 | second-writer`
- **reason:**

> settling open question 2: a Canvas-Next may name a command that exits non-zero, but only a diagnostic or a form may, and the word 'run' marks the one that may not. Decided on evidence rather than on taste - running every command all fifteen _OS_NEXT_ACTION templates name showed four of them are not commands at all and that the ENOENT template's own repair exits 2 verbatim, so 'every command must exit 0' cannot be held without deleting the diagnostics that make an ENOENT refusal useful. The question node becomes the answer because the tool has no way to mark a question answered while leaving it standing; the question itself is still in this node's history.

### 38. `90907b5` — replace `vgke`

- **author:** `claude-opus-5 | second-writer`
- **reason:**

> marking on the options table itself which option the decision above took, because a reader who scrolls to the table should not have to reconstruct it from the prose. The tool has no way to mark a row chosen - there is no status on a node - so the word goes in the cell's own text, and the cell now also records how the option's proviso was actually met rather than leaving it as a condition nobody has checked.

### 39. `f0e23e0` — replace `lp37`

- **author:** `claude-opus-5 | second-writer`
- **reason:**

> correcting this cost cell against what the option actually cost to implement, the way the first writer corrected lgvs after running the other route. The estimate said every existing template would have to be classified and that the exemption would survive as an allowlist; in fact one template names a runnable repair and the marker is syntactic, so neither happened. But the estimate was right that the format carries no structure for this, and the residue it was pointing at is real and is now named precisely: the marker is prose and only the chmod converse check holds it.

### 40. `61f5d74` — insert `l32v`

- **author:** `claude-opus-5 | second-writer`
- **reason:**

> the evidence the decision above stands on, written down as exit codes rather than as a claim, because the decision turns entirely on the observation that four of the things these templates name are not commands at all. Also the place two errors in the todo's own description get recorded: its Case 2 reproduce steps assert a repair runs verbatim that exits 2, and the template asserts a diagnostic answers a question it does not answer. A later reader checking my reasoning needs both, and neither is visible from the code.

### 41. `764554a` — insert `ev4w`

- **author:** `claude-opus-5 | second-writer`
- **reason:**

> so that the next reader can tell what the decision above cost in code without reading the diff, and so that the two demonstrations condition (4) asks for - the new behaviour failing before and passing after - are recorded where the decision is rather than only in a commit message. The vacuity check is in here on purpose: an assertion that runs no command passes for the wrong reason, and the canvas should say that somebody looked.

### 42. `9236168` — insert `g9ah`

- **author:** `claude-opus-5 | second-writer`
- **reason:**

> a decision that does not say what it left open reads later as if it covered everything, and the two loose ends here are both things a reviewer would otherwise have to find for themselves: the ENOENT template now names no repair, and the marker is prose held up by a check that generalises to one command. Naming the trailer that would close it, and what it would cost, so that whoever picks it up is deciding rather than rediscovering.

### 43. `2d7ae95` — insert `qrpa`

- **author:** `claude-opus-5 | second-writer`
- **reason:**

> the canvas is supposed to hold the shared understanding between the people and the agents on a task, and 'what happens when two of us write to it' is part of that understanding and was not in it. Recording what the staleness check actually did to me rather than what the README says it does, including the one thing it does not do: nothing in the tool told me another writer existed. Written against the first writer's base on purpose, so that the soft branch is demonstrated by the same edit that describes the hard one.

### 44. `fad921f` — replace `t8zw`

- **author:** `lfigea | by-hand`
- **reason:**

> settling open question 1, the question this canvas was opened to hold. Deciding it on what the two absences actually are rather than on symmetry with _cannot_read: the file case's exit 1 is actionable because creating the canvas is the repair, and the repository case's exit 1 would be advice that cannot be taken, because a read never initialises the repository, so a caller who follows it re-reads forever. The reproduction is what settled it rather than the table - I came to this expecting to argue 1 against 2 and found that the arguable part was the code and the false part was the sentence. The question node becomes the answer because the tool has no way to mark a question answered while leaving it standing; what was asked is still in this node's history. Written against e950b24a, the base I last read this canvas at, on purpose: I want on the record what the tool says to a writer who comes back holding a sha that is seven commits old.

### 45. `619d585` — replace `t8zw`

- **author:** `lfigea | by-hand`
- **reason:**

> correcting my own resolution of this question, ninety seconds after writing it, and the correction is the finding. The version I committed said neither option as written is what the tree holds. That is wrong about B: B says leave every errno at exit 2 and put the reason in README.md section Exit codes, and that is exactly what the code does. I wrote it holding e950b24a, a base seven commits old, and the tool applied the edit and told me afterwards - the soft branch - so I did not read node nf98, which has said since the first half that the option taken in code is B, until my own contradiction of it was already committed. Replacing rather than appending, because a settled question that misdescribes its own settlement is the kind of thing a reader takes and acts on; the wrong sentence stays in this node's history where a reader who wants to know what I thought first can have it. The substance of the decision is unchanged - only the claim about which option it is.

### 46. `6be144a` — replace `ymcz`

- **author:** `lfigea | by-hand`
- **reason:**

> marking on the table itself which option the decision above took, the way the second writer marked option B on the other table, because a reader who scrolls to a table of three live options should not have to reconstruct from the prose above it which one is dead. The tool has no way to mark a row chosen - a node carries no status - so the word goes in the cell's own text. Also correcting the option's own rationale against the one that survived contact: I drafted B saying the repository is the tool's environment, and what the README actually argues is the race, which is a stronger reason and a different one. Leaving the drafted rationale in place under a CHOSEN would publish a reason nobody relied on.

### 47. `153152b` — replace `smym`

- **author:** `lfigea | by-hand`
- **reason:**

> replacing the estimate with what the option actually cost, the same way lgvs and lp37 were replaced once their options had been run rather than imagined. Half of this cell turned out to be a cost of a different option: it assumed exit code and wording travel together, so leaving the code at 2 meant keeping the sentence that contradicts the errno. They do not travel together, and separating them is what made B answerable at all. The other half is still true and I am keeping it as written rather than softening it, because it is the standing risk in this change and a cost cell that only records costs that were avoided is worth nothing to the next reader. Adding what does and does not guard it, since guessing at that is the first thing the next person will have to do.

### 48. `3aebd79` — replace `nf98`

- **author:** `lfigea | by-hand`
- **reason:**

> this node ended with the sentence that it does not close the question above it, which is still open and still carries all three options, and that is no longer true - t8zw is settled and ymcz is marked. A canvas whose nodes disagree about whether a question is open is worse than one that never said, because a reader trusts the nearest sentence. Keeping the rest of the node rather than folding it into the decision, because where the code stands and what was decided go stale at different rates: the decision is stable and this one is only true of the current tree, and saying which is which is the thing that stops the next writer updating the wrong one.

### 49. `a846cb7` — insert `trhx`

- **author:** `lfigea | by-hand`
- **reason:**

> the task is finished and the canvas has to say so. engineering-spec.md section Lifecycle says a canvas is frozen at done and that the done gate's What/Why/Evidence/Verification/Links artifact is a projection of the canvas - so if the outcome is not in here, the projection has nothing to project from and the canvas ends as a record of two arguments with no ending. Putting it in its own section at the foot rather than threading it through the two question sections, because those sections are the reasoning and this is the result, and a reader arriving cold wants the result first and the reasoning only if they doubt it.

### 50. `b62b428` — insert `aqr3`

- **author:** `lfigea | by-hand`
- **reason:**

> so that a reader can tell what this task did to the tree without being handed a diff, and so that the two commits are attributable - the first is Case 1 and the second is Case 2, and they were made by different writers on the same branch. Naming the branch point in the same breath as the branch, because it is the single fact most likely to waste somebody's afternoon: this branch does not descend from main and a PR from it does not target main.

---

## Entries 51–55 — outside the fifty

Present so the corpus is the whole history and not a selection. The verdict
rules on 1–50; these are context.

### 51. `b2a2363` — insert `y44g`

- **author:** `lfigea | by-hand`
- **reason:**

> this is the part of an outcome that is hardest to reconstruct later and the part most worth having. What changed is in the diff; what is now TRUE that was not is nowhere except here, and it is the thing somebody reviewing this in three weeks actually wants - they will want to know whether the change bought anything, not which lines moved. Writing each one as a before-and-after pair rather than as a claim, because a benefit stated without the state it replaced is unfalsifiable and this canvas is supposed to be checkable.

### 52. `2ef45c2` — insert `fxp8`

- **author:** `lfigea | by-hand`
- **reason:**

> condition (4) says demonstrated, not asserted, and a canvas that only claims the conditions hold is exactly the assertion it forbids. Writing the observed strings - the message, the errno, the exit code, the failure count and where each failure landed - rather than the word passed, because a reader who doubts this node has to be able to re-run it and compare, and a number they can compare is the only part of a verification claim that is worth anything. Naming the file the full output is in rather than pasting it, because the canvas is supposed to stay readable in a minute and the specs are explicit that it is not a transcript.

### 53. `605185a` — insert `mqu7`

- **author:** `lfigea | by-hand`
- **reason:**

> the canvas holds what we think about a task and has said nothing so far about where the task itself lives. A reader who wants to check condition (3) against its own wording has to be able to get to the wording, and until now the only route was a Basecamp id typed inside a node's prose. link is the one element in the vocabulary that carries an href, so this is the one place in the document a reader can follow rather than retype.

### 54. `d3b5083` — insert `qrfs`

- **author:** `lfigea | by-hand`
- **reason:**

> the one dependency this task's branch has on something outside itself, and the one that decides what a reviewer can do with it. Saying it as a link rather than as another sentence in a text node because it is the thing a reader will want to click to find out whether the dependency has cleared, and because that fact goes stale on its own schedule - #8 merges or it does not, with nothing in this task changing.

### 55. `02de26b` — insert `gjxb`

- **author:** `lfigea | by-hand`
- **reason:**

> the last edit of a task's canvas should say that it is the last edit, because otherwise a reader cannot tell a finished canvas from an abandoned one - both look like a document that stopped. Saying where the open questions ended and which table holds the mark, so that a reader arriving at the foot can navigate back up rather than reading everything. And recording the caveat rather than writing a sentence that sounds like a freeze: the spec says frozen at done, the tool has no verb for it, and claiming this canvas is closed when any of four verbs will still change it would be the canvas asserting something about the store that is not true - which is the exact defect the task this canvas is about existed to fix. Recording the inconvenience is what the exercise asked for; expressing the nearest thing the tool does allow is the other half of it.

---

## How this file was produced

    git -C corpus-store log --reverse \
      --format='%h%x1f%s%x1f%(trailers:key=Canvas-Node,valueonly)%x1f%(trailers:key=Canvas-Author,valueonly)'

Each subject was split once on the first space (the verb), then once on the
first `: ` (the node id or ledger id). The remainder is the reason, copied
with no further processing. For every commit carrying a `Canvas-Node:`
trailer, the subject's target was asserted equal to the trailer's value; all
54 passed, so no reason was mis-sliced by a colon inside it.
