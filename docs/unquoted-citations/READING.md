# The citations nothing was checking

Measured and written 2026-09-25, against `canvas` at `3140b5b` and
`ledger-orchestrator` at `b4d7182`.

`bin/canvas-citations` rules on a citation only where a quotation sits beside
it, because the quoted words are the evidence it needs. That is the right rule
and nothing here reopens it. What was never measured is the size of what it
leaves.

## What was measured

| | citations | distinct target ranges |
|---|---|---|
| Live `.md` citations | 140 | |
| …the checker rules on | 53 | |
| …**no quotation, nothing checked** | **87** | **48** |

The Basecamp todo that opened this said 100 across 55 ranges. That count was
taken before [canvas#37](https://github.com/malkovro/canvas/pull/37) merged; at
its parent `54190a8` the figures reproduce as 101 and 56. #37 taught the
checker to read blockquotes and stopped a `"` inside code from inverting every
quotation after it, which moved fourteen citations from unchecked to checked.
The corpus total is 140, not 150.

## The answer to the first question: 24 of the 87 are stale

All 48 ranges were read against every sentence citing them. **Twenty-four
citations across eleven ranges did not hold the passage their citing sentence
said they held. Sixty-two land. One is a record and is exempt.**

**Nineteen of the twenty-four cite `engineering-spec.md`**, and they are one
event rather than nine: the spec grew a *Projections* section, a *write path*
section and a *Lifecycle* section, and every citation beneath them stayed where
it was. `node-state.md` and `node-naming.md` each open with a "held fixed"
preamble of five bullets citing the spec; **four of those five bullets pointed
at the wrong paragraph in both documents.**

The worst of them is not subtle. `engineering-spec.md:327-338` was cited four
times for *the lifecycle — born at `open`, grows through `executing`, frozen at
`done`* — a passage that is at `369-380`, while `327-338` describes what
Basecamp's rich text drops from an HTML page. And `engineering-spec.md:272-276`
is cited three more times for the sentence refusing a state field, which is the
very defect `canvas/citations.py` opens its own docstring with; it was fixed in
`guidelines/domain-decisions.md` and left standing in three other places.

### Every range, and what reading it found

| range as written | citations | verdict | evidence |
|---|---|---|---|
| `canvas/README.md:1174` | 1 | **stale** → `README.md:1554` | scheduled-tasks.md:255 cites it for 'nothing beyond the standard library'. That sentence is ledger-orchestrator/README.md:1554 under '## Tests'. Bare README.md also resolves to canvas/README.md, which contains no dependency policy at all. |
| `canvas/README.md:167-169` | 1 | lands | 167-169 states the primary write is committed and never rolled back; canvas-coherence.md:66 cites it for exactly that. |
| `canvas/README.md:624-626` | 1 | lands | the Open question / Answered question marker bullet; corrected in canvas#37 and now right. |
| `canvas/coherence.md:25-27` | 1 | lands | 'the triggering write is already committed and is never rolled back' is at 27. |
| `canvas/docs/drive-by-hand/FRICTION.md:109-110` | 5 | lands | 'The finished document contains zero question elements' — read as the document's failure, which is what all five citers say it says. |
| `canvas/docs/drive-by-hand/FRICTION.md:114-118` | 2 | lands | the 2026-09-24 addition that cites VERDICT.md:432-434 and node-state.md §3; both citers say exactly that. |
| `canvas/docs/drive-by-hand/FRICTION.md:121-122` | 3 | lands | 'because replace takes the new text and not a patch of it' plus the several-hundred-character retype; all three citers land. |
| `canvas/docs/drive-by-hand/FRICTION.md:145-159` | 2 | **stale** → `FRICTION.md:145-164` | both citers say 'the four wants the friction record collected'. The fourth want — 'this document is finished' — is at 164; 145-159 truncates the third want mid-sentence. |
| `canvas/docs/drive-by-hand/FRICTION.md:158` | 1 | lands | single-line pointer at the first line of the stale nf98 sentence, which runs 158-159. Pointer convention. |
| `canvas/docs/drive-by-hand/FRICTION.md:166-172` | 1 | lands | the Authorship paragraph, ending 'has to be smuggled into the node' at 171-172 — what node-state.md:765 says it says. |
| `canvas/docs/drive-by-hand/FRICTION.md:169-174` | 2 | **stale** → `FRICTION.md:174-179` | both citers mean the create-naming finding. 169-172 is the authorship paragraph, which node-naming.md:8-9 explicitly disclaims deciding. node-naming.md:15-16 quotes 'Nothing in the document says one is the problem and the other the expected value' — FRICTION.md:175-176. The finding runs 174-179. |
| `canvas/docs/merge-and-split/canvas-transcript.md:148` | 1 | lands | the replace on e8ec; node-identity.md:457 cites it as that command. |
| `canvas/docs/merge-and-split/canvas-transcript.md:217` | 1 | lands | the move of section sdtf. |
| `canvas/docs/merge-and-split/canvas-transcript.md:230` | 1 | lands | history … e8ec. |
| `canvas/docs/merge-and-split/canvas-transcript.md:326` | 1 | lands | history … ps58. |
| `canvas/docs/merge-and-split/canvas-transcript.md:375` | 1 | lands | the final read. |
| `canvas/docs/why-verdict/VERDICT.md:389-413` | 1 | lands | section 5.2 runs exactly 389-413; 414 is blank and 415 opens 5.3. Cited as the precedent for adding mechanism and pricing it, which is what 5.2 does. |
| `canvas/docs/why-verdict/VERDICT.md:40-43` | 1 | lands | '41 of the 50 reasons meet the bar' is at 40. |
| `canvas/docs/why-verdict/VERDICT.md:425-434` | 3 | lands | 425 is 'Do not give --why required fields or a structured form'; 432-434 is entry 37 read as the design working. All three citers name one of those two. |
| `canvas/docs/why-verdict/VERDICT.md:432-434` | 6 | lands | 'Entry 37 is that design working — a question node becoming its own answer, legible only because a free-text reason said so.' All six citers say exactly that. |
| `canvas/docs/why-verdict/VERDICT.md:449-455` | 1 | lands | the 2026-09-24 addition citing FRICTION.md:109-110 and section 3, which is what domain-decisions.md:218 says it does. |
| `canvas/engineering-spec.md:108-109` | 1 | lands | '<question> is the one semantic node, and it is the one exception worth arguing for' at 108. |
| `canvas/engineering-spec.md:108-110` | 2 | lands | 'the renderer has to make it loud, and an agent has to be told not to quietly answer it' at 109-110. |
| `canvas/engineering-spec.md:108-112` | 2 | lands | the exception plus the retirement clause and 'that is not derivable from shape' at 110-112. |
| `canvas/engineering-spec.md:109-110` | 1 | lands | node-state.md:475 quotes 'an agent has to be told not to quietly answer it' — verbatim at 110. |
| `canvas/engineering-spec.md:111-112` | 3 | lands | 'If it turns out to earn nothing, it folds back into <text open="true">' at 111-112. All three citers say that. |
| `canvas/engineering-spec.md:116-123` | 1 | lands | 'Four verbs. No more.' at 122. Range is wide but holds it. |
| `canvas/engineering-spec.md:125` | 2 | **stale** → `engineering-spec.md:131` | both citers name 'There is no resolve, no collapse, no supersede', which is at 131. Line 125 is the `canvas insert` line of the verb listing. |
| `canvas/engineering-spec.md:128-130` | 5 | **stale** → `engineering-spec.md:131-137` | 128-130 is a blank line, '--why is required by all four and has no default', and a blank. The paragraph the five citers name — no resolve/collapse/supersede, the options-table example, 'The semantics live in the reason', and 'A verb per kind of intent is how you get eleven verbs' — runs 131-137. |
| `canvas/engineering-spec.md:133-135` | 2 | **stale** → `engineering-spec.md:139-141 and :192` | both citers say 'One edit is one node, one edit is one commit'. 133-135 holds 'The semantics live in the reason' — the previous bullet's subject. 'One edit is one node.' is at 139-141; 'one edit is one commit' at 192. Separately: the same bullet's claim that a node's history IS `git log --grep='Canvas-Node: <id>'` is contradicted by the spec at 218-223, which calls that query wrong in two reachable ways. Prose defect, named not fixed. |
| `canvas/engineering-spec.md:266-276` | 1 | **stale** → `engineering-spec.md:291-295` | node-state.md:466 cites it for 'if canvas-versus-reality drift does turn out to bite, this is still where it gets fixed'. That sentence is at 293-294. 266-276 is the coherence-checker paragraph. |
| `canvas/engineering-spec.md:272-276` | 3 | **stale** → `engineering-spec.md:291-295` | the sentence refusing a state field as premature is at 291-295. 272-276 is the post-write coherence checker. This is the exact defect citations.py's own docstring opens with, still uncorrected in three more places. |
| `canvas/engineering-spec.md:303-304` | 1 | **stale** → `engineering-spec.md:333-341` | node-naming.md:180 cites it for 'the artifact pasted into a Basecamp comment'. 303-304 is the lead-in to 'the canvas as input'. The artifact that goes in the comment is projection 2, `bin/canvas render --format comment`, at 333-341. The spec at 322-324 now says the HTML page is explicitly NOT pasteable into a Basecamp comment, so the citing clause names the wrong projection too. |
| `canvas/engineering-spec.md:327-338` | 4 | **stale** → `engineering-spec.md:369-380` | all four citers name the lifecycle — born at open, grows through executing, frozen at done, never deleted. That is the '## Lifecycle' section at 369-380. 327-338 is the HTML/Basecamp projection paragraph. |
| `canvas/engineering-spec.md:331-333` | 1 | **stale** → `engineering-spec.md:365-367` | canvas-in-the-page.md:471 cites it for 'provenance is what makes that safe'. That sentence is at 365-367: 'A browser edit is authored as the person... there is none, and provenance is what makes that safe.' |
| `canvas/engineering-spec.md:99-106` | 4 | lands | 'this vocabulary is structural and not semantic' (103-104) and the tripwire naming <decision>, <risk>, <acceptance-criterion> (105-106). All four citers name one of those. |
| `canvas/node-identity.md:446` | 1 | record | this citation sits inside a fenced block at node-identity.md:500-510 reproducing verbatim `bin/canvas history` output — a commit reason typed on 2026-09-23. It is a record, not prose anybody maintains, and renumbering it would falsify the transcript exactly as renumbering a PINNED_REPORTS citation would. As it happens 444-446 does hold the lineage sentence it quotes. Finding: canvas-citations enumerates citations inside fenced code blocks, which PINNED_REPORTS does not cover. |
| `canvas/node-identity.md:527-536` | 1 | lands | 'Why the pointer belongs in the reason and not in a field' / 'Because the reason has to carry it anyway' at 527-529. |
| `canvas/node-identity.md:555-598` | 1 | lands | section 7's 'What the rejected option would have cost' runs exactly 555-598; 599 is blank and 600 opens the next subsection. |
| `canvas/node-identity.md:568` | 1 | lands | 'It would be the first piece of node state not derivable from the log.' is exactly line 568. |
| `canvas/node-state.md:289-292` | 1 | lands | 'could this field ever have a twelfth value that fits none of the ones somebody thought of?' at 289-290, quoted verbatim by node-naming.md:99. |
| `canvas/product-spec.md:124` | 1 | lands | the risk row 'A stale canvas injected into every prompt is worse than no canvas, because it misleads with authority'. |
| `canvas/product-spec.md:130` | 1 | lands | the citation lands on the item it names. Separately: canvas-in-prompts.md:121 calls it 'the open item' while product-spec.md:130 marks it [x] Settled 2026-09-23 and names canvas-in-prompts.md as what settled it. Prose defect, named not fixed. |
| `canvas/product-spec.md:132` | 2 | lands | the <figure> item, marked settled; both citers say exactly that. |
| `canvas/product-spec.md:40` | 2 | lands | '1. One edit is one node.' — both citers use it for exactly that. |
| `canvas/product-spec.md:42` | 1 | lands | 'A node's reasons are its history, so before changing something you can ask what the current text was for' — the bar engineering-spec.md:510 says it sets. |
| `canvas/product-spec.md:48` | 3 | lands | 'The meaning lives in the reason, where it can be anything, rather than in a verb name'. |
| `canvas/product-spec.md:52` | 2 | lands | 'Not a wiki. A wiki accumulates. A canvas resolves'. |

## The answer to the second question: one check is worth adding, one is not

### Shipped — the text a citation was written against

For a citation with no quotation: blame the citing line, read the cited file at
that commit, and take the text that stood at the cited range **then** as the
quotation the citation never carried. The existing three-way rule then applies
unchanged, and the moved case still carries its own repair.

Scored against this reading, over all 87:

| | stale | lands |
|---|---|---|
| reported *moved* | **22** | 2 |
| silent (*lands*) | 0 | 54 |
| silent (*undecidable*) | 1 | 7 |

**22 of 24 caught, at two false reports** — and both of those two are ranges a
stricter reading would have tightened anyway. One of them,
`engineering-spec.md:116-123`, this reading had generously called landing
because `122` sits inside it; the check was right and it is now `122-127`.

The cruder version of the same idea — compare the two texts and report any
difference, with no attempt to locate the old text — was tried first and scores
72% against this 92%. Its extra reports are all one shape: a range edited in
place where the cited passage survived inside it. Locating the old text is what
tells those apart, and it is also what produces a repair to print.

**It is reported and does not fail the run.** The quoted rule fails on words an
author typed. This one fails on words inferred from a timestamp, and the
inference is wrong whenever a citation was already wrong when written, or the
citing line was last touched by a reflow that had nothing to do with it. That
is weaker evidence for the same claim, so it is named rather than blocking —
the shape `docs/why-verdict/VERDICT.md` §5.2 already set for a guard whose
price was one false positive in fifty.

**What it will not catch:** a citation that was wrong the day it was written
(there is no earlier text to compare); a citation whose target changed in a
commit that also touched the citing line; anything in a repository without git
history. Cross-repository citations are lined up by timestamp rather than by a
shared history, which is the weakest link and the reason a cross-repository
report deserves more suspicion than a local one.

After this change the standing report is **one item** — `node-naming.md:83`
citing `FRICTION.md:158`, where drift happened to improve the citation. That is
the running cost.

### Refused — reading a quotation that sits *before* its citation

Sixteen of the 87 have a quotation ending just before the citation rather than
after it: *"…quoted words…"* (`FRICTION.md:121-122`). Extending the association
backwards looks free, costs no git, and adds no new kind of evidence.

It was implemented and run. It raises coverage from 50 citations to 62 and
produces exactly one new failure — **and that failure is wrong.**
`node-state.md:284` quotes *"A verb per kind of intent…"*, and three lines
later cites `engineering-spec.md:111-112` for something else entirely; the
backwards rule staples the quotation to the wrong citation and calls a citation
that lands *moved*. It caught none of the 24.

That is precisely the failure mode `docs/why-verdict/DRIFT-CHECK.md` §7.2 and
this module's own docstring were written to avoid, so it is refused. Prose
attributes a quotation forwards; a rule that reads backwards is reading a
sentence the corpus does not write.

## Named, not fixed — handed on

- **`node-naming.md:30` and `node-state.md:29` both assert that a node's
  history *is* `git log --grep='Canvas-Node: <id>'`.** `engineering-spec.md:218-223`
  says that query "is wrong in two reachable ways" and that the command matches
  the trailer for equality instead. The citations beside the claim are now
  right; the claim is not. It sits in the *held fixed* preamble of two settled
  rulings, which is not a line to rewrite in a citation pass.
- **`node-naming.md:179-180` calls the rendered HTML page "the artifact pasted
  into a Basecamp comment".** `engineering-spec.md:322-324` now says the HTML
  page is explicitly *not* pasteable into one. The citation has been moved to
  the comment projection that is; the clause still names the wrong projection.
- **`canvas-in-prompts.md:121` calls `product-spec.md:130` "the open item".**
  That item is marked `[x] Settled 2026-09-23` and names
  `canvas-in-prompts.md` itself as what settled it.
- **A bare `README.md:<n>` in a `ledger-orchestrator` document resolves to
  *canvas's* README**, because `resolve` falls back to matching a basename
  anywhere under either root and canvas is passed first. The one instance is
  now spelled `../README.md:1554`. Nothing stops the next one.
- **`cited()` enumerates citations inside fenced blocks.** `node-identity.md`
  reproduces `canvas history` output whose commit reasons carry line numbers;
  those are records of what was typed. `written_against` skips them;
  the quoted rule does not, and `PINNED_REPORTS` does not cover them.
