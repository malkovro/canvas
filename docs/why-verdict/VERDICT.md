# Verdict: does `--why` carry real information?

Ruling on the first fifty reasons written to a Canvas, for Basecamp todo
[10326884789](https://app.basecamp.com/3934852/buckets/48039419/todos/10326884789).

**For a reader with none of this context.** `Canvas` is a tool that keeps one small
structured XML document per task — what we currently think about it, what is still open,
what was ruled out. It is edited one node at a time, never rewritten, and every edit is a
git commit whose subject carries a mandatory reason supplied as `--why`. Nothing generates
that reason and nothing can default it: `canvas/store.py:413-432` refuses an absent, empty
or whitespace-only one with exit 2 and writes nothing. The reason lives in the commit
subject and nowhere else; `canvas history <ledger> <node>` prints a node's edits oldest
first, each with its reason, which is how a later reader asks what a node's current text
is *for*.

The design rests on that field being worth reading. `engineering-spec.md:416-425` says so
outright and demands this review before any further work: *"No product in the market ships
a mandatory reason field, so there is no evidence anywhere on whether a model writes a
useful one or a tautology — 'updated the node to reflect the change'. … Read the first
fifty reasons before starting step 2; if they are noise, the thing to fix is the prompt or
the schema of `--why`."*

**The bar**, from `product-spec.md:42`: could a reader, months later, reading only this
reason, tell what the node was for and decide whether to **honour** it or **explicitly
retire** it.

**Inputs.** `./corpus-reasons.md` (the 55 reasons verbatim, generated from the store),
`./classification.md` (each of the first fifty labelled `informative` /
`restates-the-diff` / `empty`), `./corpus-provenance.md` (who wrote each arm),
`./spec-on-why.md` (the bar's source text), `./FRICTION.md` §5 (a preliminary opinion from
a smaller sample, which explicitly deferred the ruling to this document). Corpus HEAD
`02de26b71893d1d33d1559cd0fd9bcfcaff84652`, 55 commits, the first fifty under review. Every
quotation below was re-read from `git -C corpus-store log` by this step, not copied on
trust.

---

## 1. The verdict

**`--why` carries real information: 41 of the 50 reasons meet the bar, and all six of the
caller-written failures sit on one kind of edit — the placement of a piece of an options
table that holds no content of its own — so the field is sound and the defect is in what
the one-node-per-commit rule forces a writer to justify, not in the reason.**

That is a verdict of *useful*, not a hedge and not a split. The clause about the six is not
an escape from it; it is the line this review found, and it is stated exactly in §2.3 and
acted on in §5. `--why` is not noise.

---

## 2. The evidence

### 2.1 The counts

From `./classification.md`, one label per reason, entries 1–50, borderline cases taking the
harsher label:

- `informative` — **41** of 50
- `restates-the-diff` — **7** of 50
- `empty` — **2** of 50

Per arm (see §3 for what the arms actually are):

- long-running writer, labelled `lfigea | by-hand` (n=43) — `informative` **34**, `restates-the-diff` **7**, `empty` **2**
- cold second writer, labelled `claude-opus-5 | second-writer` (n=7) — `informative` **7**, `restates-the-diff` **0**, `empty` **0**

**Three of the nine failures are not `--why` at all.** Entries **1**, **2** and **3** are
the three commits `create` writes when a canvas is born, and their reasons are string
literals in the tool's own source — `canvas/store.py:846` (`"born at open, root only"`) and
`canvas/store.py:851-852` (`"the problem the ledger row states"`, `"the expected value the
ledger row states"`). No caller typed them and no prompt or schema change could alter them.
`./FRICTION.md` §5 excludes them on the same ground. Removing them leaves **47
caller-written reasons, 41 of which meet the bar and 6 of which do not** — 87%.

Length, measured over the fifty: `informative` reasons run **151–975 characters** (n=41,
mean 382, median 308); the nine failures run **21–114** (n=9, mean 48, median 33). No reason
at or under 114 characters met the bar and none at or over 151 failed it. §5.3 explains why
that clean split is a symptom and must not be turned into a rule.

### 2.2 Reasons that meet the bar — quoted in full

**Entry 45 — `619d585` — `replace t8zw`** (975 chars, the longest in the corpus)

> correcting my own resolution of this question, ninety seconds after writing it, and the
> correction is the finding. The version I committed said neither option as written is what
> the tree holds. That is wrong about B: B says leave every errno at exit 2 and put the
> reason in README.md section Exit codes, and that is exactly what the code does. I wrote it
> holding e950b24a, a base seven commits old, and the tool applied the edit and told me
> afterwards - the soft branch - so I did not read node nf98, which has said since the first
> half that the option taken in code is B, until my own contradiction of it was already
> committed. Replacing rather than appending, because a settled question that misdescribes
> its own settlement is the kind of thing a reader takes and acts on; the wrong sentence
> stays in this node's history where a reader who wants to know what I thought first can have
> it. The substance of the decision is unchanged - only the claim about which option it is.

This is the bar met in every clause: what the node now says, what it said before, which
sentence was wrong, the mechanism that produced the error, why `replace` rather than a note
under it, and — the part no diff can supply — which part of the decision is unchanged. A
reader months later can honour it or retire it without reading anything else.

**Entry 36 — `e950b24` — `replace echr`** (551 chars)

> I wrote this node an hour ago off a grep for os_next_action and named four surviving call
> sites. Three of those four catch FileNotFoundError separately before the line I counted, so
> ENOENT never arrives there - checked by spying on the function rather than by reading the
> code again, because reading the code again is what produced the wrong count. Replacing
> rather than appending a correction, because the wrong number is the kind of thing a reader
> takes and acts on, and leaving it visible with a retraction under it is worse than one true
> sentence.

It names its evidence and it names the *method*, which is the convention
`engineering-spec.md:270-272` asks for and nothing enforces: *"an edit whose reason is a
fact about the world should name its evidence in `--why` — a PR, a verdict, a file and
line."*

**Entry 37 — `f7be9ea` — `replace mqxd`** (663 chars, the cold second writer)

> settling open question 2: a Canvas-Next may name a command that exits non-zero, but only a
> diagnostic or a form may, and the word 'run' marks the one that may not. Decided on
> evidence rather than on taste - running every command all fifteen _OS_NEXT_ACTION templates
> name showed four of them are not commands at all and that the ENOENT template's own repair
> exits 2 verbatim, so 'every command must exit 0' cannot be held without deleting the
> diagnostics that make an ENOENT refusal useful. The question node becomes the answer
> because the tool has no way to mark a question answered while leaving it standing; the
> question itself is still in this node's history.

This one carries the load the specs say the reason must carry. `engineering-spec.md:125`:
*"There is no `resolve`, no `collapse`, no `supersede`."* `product-spec.md:48`: *"The meaning
lives in the reason, where it can be anything, rather than in a verb name, where it can only
be what somebody thought of in advance."* Entry 37 says so explicitly: a question node
becoming its own answer is legible only because the reason says that is what happened.

**Entry 31 — `5fa80e6` — `replace lgvs`** (427 chars)

> the work made this cell wrong, not just thin. I wrote it saying option A's cost was that
> the five call sites are uneven; running the non-racy case showed the real cost, which is
> that _not_a_repository already answers 2 for the identical fact and exit 1 here would make
> the code a function of a race. Replacing rather than adding a note, because the old
> sentence would otherwise still be sitting there being the weaker argument.

**Entry 35 — `7a5b1f9` — `insert fdzu`**

> the launch brief for this half said to branch from main, and branching from main would have
> produced a change to a function that does not exist there. Under
> guidelines/correction-authority.md the brief is the lowest authority and the todo
> description is higher, and the description cites canvas/store.py:582 by line - so the
> description wins and the base is PR #8's branch. Putting it at the top of the canvas
> because it is the first thing that would waste anybody else's afternoon.

**Entry 43 — `2d7ae95` — `insert qrpa`** (the cold second writer)

> the canvas is supposed to hold the shared understanding between the people and the agents
> on a task, and 'what happens when two of us write to it' is part of that understanding and
> was not in it. Recording what the staleness check actually did to me rather than what the
> README says it does, including the one thing it does not do: nothing in the tool told me
> another writer existed. Written against the first writer's base on purpose, so that the
> soft branch is demonstrated by the same edit that describes the hard one.

**Entry 48 — `3aebd79` — `replace nf98`**

> this node ended with the sentence that it does not close the question above it, which is
> still open and still carries all three options, and that is no longer true - t8zw is settled
> and ymcz is marked. A canvas whose nodes disagree about whether a question is open is worse
> than one that never said, because a reader trusts the nearest sentence. Keeping the rest of
> the node rather than folding it into the decision, because where the code stands and what
> was decided go stale at different rates: the decision is stable and this one is only true of
> the current tree, and saying which is which is the thing that stops the next writer updating
> the wrong one.

### 2.3 Reasons that do not meet the bar — quoted in full, all nine

These argue against the verdict and are reproduced complete so nobody has to take the
labelling on trust.

**Entry 23 — `2cfb511` — `insert vp52`** (21 chars) — labelled `empty`

> column one, as above.

**Entry 24 — `45bd148` — `insert be5v`** (21 chars) — labelled `empty`

> column two, as above.

**Entry 22 — `96276cf` — `insert rysw`** (76 chars) — labelled `restates-the-diff`

> the header row, matching question 1's two columns. Same shape, same reading.

**Entry 25 — `8f38fae` — `insert vqpn`** (31 chars) — labelled `restates-the-diff`

> option A's row: no, it may not.

**Entry 28 — `8c6da79` — `insert yh66`** (77 chars) — labelled `restates-the-diff`

> option B's row: yes, provided the reader can tell a diagnostic from a repair.

**Entry 10 — `28985c6` — `insert fu7f`** (114 chars) — labelled `restates-the-diff`

> option A's row. One row per option so that each one can be read, argued with and eventually
> struck out on its own.

**Entries 1, 2, 3 — `0b2e20b`, `d65e081`, `e694e94`** — `create`'s own three, string
literals at `canvas/store.py:846,851-852`, not written by any caller:

> born at open, root only

> the problem the ledger row states

> the expected value the ledger row states

**What the six caller-written failures have in common, checked in the store rather than
inferred.** Every one is the placement of a piece of one options `<table>`, and in every
case the node placed held nothing:

- **10** (`fu7f`), **22** (`rysw`), **25** (`vqpn`), **28** (`yh66`) are `<row>` elements
  committed **empty** — `git show 8f38fae` places exactly `<row id="vqpn" v="1"/>`, and
  `git show 8c6da79` places exactly `<row id="yh66" v="1"/>`. Their reasons describe text
  that a *later* commit will put inside them.
- **23** (`vp52`) and **24** (`be5v`) are the two header `<cell>`s of that table; their whole
  content is the words `Option` and `What it costs`.

Not one of the six records a judgment, because the edit did not contain one. Conversely —
and this is the finding that carries the verdict — **every edit in the fifty that placed an
option, a cost, an argument, a correction, a piece of evidence or an outcome got a reason
that meets the bar: 41 of 41.** The correlation in this corpus is with whether the edit
contained a decision, not with the writer, the hour, or fatigue.

### 2.4 Two sharper patterns, both from `./classification.md` §4

**The second copy of a structure loses its reason.** Question 1's table scaffolding is
`informative` three times over — entry **7** (`s437`): *"the header row: the table has two
columns and nothing else in the vocabulary can say so, since a `<table>` carries no column
names and a `<cell>` carries no header flag"*; entry **8** (`sm4b`): *"'this row is the
header' is carried by its position and by nothing else"*; entry **9** (`zyrd`): *"column two
is the cost, not the argument for it."* Question 2's table scaffolding is the same three
nodes, by the same writer, roughly fifteen edits later — entries **22**, **23**, **24** —
and they are the three weakest reasons in the corpus. The substance did not become
unavailable; it became *already written down somewhere else*, and the reason collapsed into
a pointer at it. That pointer — `"as above"` — is exactly what a stranger reading
`canvas history` months later cannot resolve, because `history` prints one node's edits and
never the node the pointer meant.

**Reasons improve over the run rather than decaying.** All nine failures fall in entries
**1–28**. Entries **31–50 are 20 for 20**. Mean reason length is 161 characters over entries
1–30 and 562 over 31–50. "The writer got bored and the reasons thinned out" is not what this
corpus shows: the thinnest reasons are at the beginning, the thickest at the end, after the
code had been run and there was something to correct.

**All ten `replace` reasons meet the bar**, and all five of the strongest are `replace`s
(`./classification.md` §3 names them: entries 45, 36, 31, 47 and 37, every one a `replace`;
§4.4 of the same file says "four of the five", which its own §3 contradicts). The mechanism
is legible: a `replace` must say what was wrong with text the reader can
already see, and the diff cannot supply that, whereas an `insert` of an empty row has
nothing the diff does not already show.

### 2.5 The one piece of evidence that is not a text judgment

Everything above is a reader grading reasons. There is one observation in the record of a
reason travelling out of the document and into the place a decision was being made, and it is
worth reporting apart from any grade. `./FRICTION.md` §5 points at transcript line 813. Read
in the source run's `canvas-transcript.md`, what happened there is this: the **second
writer**, after six edits of its own, *deliberately* re-ran an edit to `mqxd` against the
stale base `e950b24a` — its `--why` on that invocation says so: *"probing the staleness check
deliberately: writing the question node again against e950b24a, the base the first writer's
handoff note still holds, to see what the tool tells a second writer who arrives with it"*.
The tool refused (exit 1, nothing applied) and printed back the intervening commit's whole
reason — entry **37** (`f7be9ea`, `mqxd`), quoted in §2.2 — together with git's diff of the
node. The writer recorded the result in entry **43**: *"That is enough to act on without
asking anybody: the reason the other writer changed it is in the output, so the re-decision
can be made from the refusal itself rather than by reading the document again first."*

**What that shows, and what it does not.** It shows the refusal path carries the reason to
the point of use, and that the writer meeting it judged a reason sufficient to re-decide from
without re-reading the canvas. It is **not** a reason serving a stranger under load: the probe
was deliberate, the second writer had read the canvas on arrival, and the reason printed back
was one it had written itself minutes earlier. It is weaker than a cold reader would be, and
it is the only non-grading observation this corpus holds.

The mandatory field is also, by the first writer's own account quoted in `./FRICTION.md` §5,
*"the thing that stopped anyone reaching for a text editor"* at the one moment they wanted
to.

---

## 3. The arms

**The corpus does not support a human-versus-model comparison, and this review does not
report one.**

The todo asks to *"separate the model-written reasons from the human-written ones, because
they may fail differently."* That separation is not available here, because the second
category is empty. `./corpus-provenance.md` §2 settles it on five independent sources:

1. `lfigea | by-hand` is not a claim about a keyboard. `--author` is optional on all five
   writers, and when omitted the store synthesises `"<$USER> | by-hand"` —
   `canvas/store.py:462-471`, with the ` | by-hand` suffix a literal appended
   unconditionally. `lfigea` is the machine's Unix username. Every caller on this machine
   that omits the flag gets that string.
2. The run that produced the corpus says so itself, twice and unprompted, in `./FRICTION.md`:
   *"No human being wrote to this canvas."*
3. The artifacts that drove the canvas name themselves as steps: *"Written 2026-09-22 by the
   `open-and-drive` step of run `bc-10326884731-…`"*, whose instruction was *"be the person
   driving a canvas by hand"* — role-play, and candid about being role-play.
4. The run ledger on todo 10326884731 records all nine steps passing on
   `claude/claude-opus-5[1m]`. None was executed by a person.
5. Measured directly from the store, independent of anyone's testimony: 55 commits in 51
   minutes 34 seconds, median gap 9.5 seconds, three of them in the same second, at a mean of
   320 characters of justification per edit across the `by-hand` arm
   (`./corpus-provenance.md` §2.5 measures the 320 over that arm's 48 commits; the mean over
   all 55 is 344). Nobody types that.

So the asymmetry between the two arms is an asymmetry in **who bothered to set a flag**. Any
verdict phrased as "humans wrote good reasons, models wrote bad ones" — or its converse —
would be false on its face here.

**What the arms actually are, and it is worth reporting.** A long-running writer holding a
persona and its own accumulated context (43 of the fifty) against a second agent step that
arrived cold, read the canvas and wrote into it (7 of the fifty, entries 37–43, contiguous).
Sample sizes 43 against 7; nothing statistical follows from the cold writer's 7-for-7, and
none is claimed.

What *is* visible is not a difference in care but a difference in task. **The cold writer
wrote no scaffolding at all.** Each of its seven edits is a decision (37, 38, 39), the
evidence under one (40, 41), or a statement of what it left open (42, 43). The
context-holding writer built every table in the canvas, and therefore wrote every weak
reason — *and* four of the five strongest reasons in the corpus: `./classification.md` §3
names the strongest five as entries 45, 36, 31, 47 and 37, and the fifth of those, entry 37,
is the cold writer's. The arm that never had to build a table never wrote a reason about a
table.

The one asymmetry that really is about context: **the writer with context is the only one in
a position to write "as above"** — and that is precisely how its three weakest reasons fail.
A cold writer has no "above" to point at and must say the thing.

This corpus therefore answers half of `product-spec.md:105`, which asks step 1 to prove two
things: *"That a person keeps a canvas up to date when nothing forces them to — and that a
model writes a useful reason."* The first is untestable here and `./FRICTION.md` §8 says so.
The second is exactly what this corpus is for, and it is answered: **yes.**

---

## 4. What this means for the next iteration

The todo is explicit about the consequence: *"If the verdict is noise, the finding is not a
footnote — it means steps 2 to 6 are not the next work and fixing the reason is."*

**The verdict is not noise, so that branch does not fire. Steps 2 to 6 are the next work and
the queue behind this todo stands.** The renderer, the prompt integration and the UI can be
built on per-node history; the assumption the whole design rests on held under fifty reasons
on a real task.

The change named in §5 is a small amendment that rides alongside that work. It is not a
blocker, it does not reorder the queue, and it should not be allowed to. Two lines of
justification for treating it that way: the failures are 6 of 47 caller-written reasons, all
of one kind; and they cluster in entries 1–28, with the last twenty reasons 20 for 20.

---

## 5. What would have to change

Required by the done condition because the reasons fall short in one respect, even though
the overall verdict is that they carry information.

### 5.1 The change, and where it belongs: **the prompt**

Add one rule to the instruction given to any writer of `--why`. It is two clauses and it is
the whole of the fix:

> **Never point at another reason.** If the justification for this node is one you have
> already given for a sibling or a parent, name that node's four-character id and say what
> is *different* about this one — what it holds that the other does not, and what would
> retire this one and not the other. The words "as above", "as before", "same as", "same
> shape" and "matching X" are not reasons: `canvas history` prints one node's edits and
> never the node you meant.
>
> **When the node you are placing holds nothing** — an empty `<table>`, an empty `<row>`, a
> one-word header `<cell>` — the reason is not about the element. Say what the structure it
> belongs to is for, name the container's id, and say what would make this element wrong or
> unnecessary. Do not describe text that a later commit will put inside it.

Why the prompt and not the schema: all six caller-written failures are a writer choosing a
pointer over a sentence when the sentence was available (§2.4 — entries 7, 8 and 9 prove the
same writer could write it, fifteen edits earlier, for the identical nodes). There is nothing
the tool could compute here; there is something a writer could be told.

**Implementable as stated.** The rule goes wherever the `--why` writing instruction for
Canvas lives — today that is the launch brief given to a step that drives a canvas; when a
prompt integration exists (step 4 of *The path*), it goes in that prompt's `--why` section,
verbatim.

### 5.2 One guard worth adding to the schema, and exactly what it catches

`require_reason` (`canvas/store.py:413-432`) today checks one property: that the reason is
non-empty after `.strip()`. Everything else in the bar is unenforced intent. One more check
is cheap and needs no judgment of content:

> **Refuse a bare back-reference.** After lowercasing and stripping punctuation, if the
> reason contains one of `as above`, `as before`, `see above`, `same as above`, `same shape`,
> `ditto`, `as previously`, **and contains no four-character node id** matching
> `[a-z0-9]{4}` other than the edit's own target, raise `ToolProblem` — exit 2, nothing
> written, the same shape and code as the existing empty-reason refusal. Message:
> `--why must say what this node is for, not where it sits; if the reason is another node's, name that node's id and say what differs here.`

**What it would have caught, named exactly:** entries **23** and **24** (*"column one, as
above."* / *"column two, as above."*) and entry **22** (*"Same shape, same reading."* is the
whole of its substance). **What it would not catch:** entries **10**, **25** and **28**,
which say something — it is just something true of any table, or a preview of text not yet
committed. Those are §5.1's job. **What it would also catch, and should not:** entry **21**
(`ehxj`, labelled `informative`), whose closing clause is *"Empty for one commit, as before."*
It names no other node id, so the check as written fires on it — one false positive in fifty,
against a reason that met the bar. Three of six caught and one of forty-one wrongly refused:
that is what the check is worth and it should not be sold as more. It is a speed bump against
the one failing shape this corpus produced twice, not a tautology detector, and that false
positive is its price — a writer who means "as before" and has a node id to name is told to
name it.

### 5.3 Three changes that should **not** be made, with the evidence against each

**Do not add a length floor.** It is the obvious candidate and this corpus would appear to
endorse it: a floor at 150 characters separates the 41 from the 9 perfectly (§2.1). It is
still wrong. The short reasons are short *because* the edit carried no judgment (§2.3), so a
floor buys a longer version of "column one, as above" and a writer who pads to clear it. The
number would measure compliance, not information, and — worse — it would score entry **7**
(`s437`, 165 chars, genuinely informative) and entry **10** (`fu7f`, 114 chars, not) by the
same property that has nothing to do with why they differ.

**Do not give `--why` required fields or a structured form.** The freedom of the field is
load-bearing and deliberate. `product-spec.md:48` and `engineering-spec.md:125-129` both
state it, in their own wording rather than in identical words. `engineering-spec.md:125-129`:
*"There is no `resolve`, no `collapse`, no `supersede`. … The semantics live in the reason,
where they can be anything, and not in a verb name, where they can only be what somebody
thought of in advance."* `product-spec.md:48`: *"The meaning lives in the reason, where it
can be anything, rather than in a verb name, where it can only be what somebody thought of
in advance."* Entry **37** is that design working — a question node becoming its own
answer, legible only because a free-text reason said so. A required-fields schema would put
back the fixed vocabulary the four verbs were shrunk to avoid.
(`guidelines/domain-decisions.md` is the file that would mark which shapes are deliberate;
all three of its sections read *"Not yet filled in."*, so it does not speak to this. The
specs do, in their own words, and this review treats that as the deliberate part. Filling
that file in with this entry is worth doing and is not in this review's scope.)
(**Added 2026-09-25, after this review — the paragraph above is as written on 2026-09-22.**
That file has since been written, so its sentence about it is no longer true of it.
`guidelines/domain-decisions.md` in `ledger-orchestrator` was filled in on 2026-09-23 by
commit `ae867cf`; it is 231 lines and the phrase *"Not yet filled in."* occurs in it zero
times. Its *Domain decisions* section carries this recommendation as a decision in its own
right — *"The semantics live in the reason. `--why` gains no fields, no structure and no
required vocabulary."* — and cites `VERDICT.md:425-434`, the paragraph above, as part of
what it rests on. So what this review called worth doing and out of its own scope was done,
by someone else, the next day. The recommendation is unchanged: the file speaks to this now,
and it says the same thing.)
(**Added 2026-09-24, after this review.** `docs/drive-by-hand/FRICTION.md:109-110` reads
entry **37**'s edit the other way, as the document's failure — *"the canvas ends with no
visible trace that anything was ever asked."*
Both readings stand: `node-state.md` §3 reconciles them by distinguishing the document from
the log. This review was reading the log, where the reason is; the friction report was reading
the rendered document, where it is not. §3 leaves the recommendation above untouched — `--why`
still gains no fields, no structure and no required vocabulary.)

**Do not relax one-node-per-commit to let a table arrive in one edit.** It is the rule that
manufactured all six failures and it is still the rule that bought everything else here —
per-node history exists only because a commit touches exactly one node and names it
(`engineering-spec.md:186-192`). `node-identity.md:373-379` prices the tedium and accepts it
in as many words: *"Restructuring is tedious. Reorganising a section of eight nodes is eight
commands and eight reasons, not one. That is the intended trade."* The correct response to an
edit that contains no judgment is a reason that says what the structure is for — not fewer
commits.

### 5.4 What would have changed this review's mind

Stated so the ruling is falsifiable. Any one of these would have flipped the verdict to
noise: failures spread across substantive edits rather than confined to table scaffolding;
the spec's own worked tautology (*"updated the node to reflect the change"*) appearing even
once — it appears zero times in the fifty; reasons degrading over the run rather than
improving (they run 20 for 20 in the last twenty); or a `replace` — the verb that carries the
most semantic load — failing the bar even once. None of the four happened.

---

## 6. What this review did not cover

- **One canvas, one task.** The corpus is the canvas for Basecamp todo 10329619223 (*errno
  decides the repository refusals*), a single task on a single branch.
- **That task was about `bin/canvas` itself.** The canvas documents a decision inside the
  Canvas tool, written by writers who had just read its specs. Reasons on a task with no such
  self-referential pull may be poorer, and this corpus cannot say.
- **Fifty reasons of 55 commits.** Entries 51–55 exist in `./corpus-reasons.md` and are
  outside the ruling. Three of the fifty (entries 1–3) are `create`'s own literals, so the
  caller-written sample is 47.
- **No human arm** (§3). Both arms are `claude-opus-5[1m]`; 43 against 7. Whether a *person*
  writes a useful reason, and whether a person keeps a canvas current when nothing forces
  them to, are untested — `product-spec.md:105` asks both and this corpus answers only the
  model half.
- **Two verbs never appear.** The fifty are `insert` 39, `replace` 10, `create` 1. There is
  no `remove` and no `move` in the corpus at all, so whether those verbs attract weaker
  reasons is unknown. `node-identity.md:297-305` predicts a specific failure for `remove`
  (*"we deleted this section"* as the reason for deleting a particular child) that this review
  could not test.
- **Nobody read these reasons months later.** The bar is about a reader at distance and the
  corpus is 51 minutes long. The single non-grading observation (§2.5) is a writer meeting its
  own reason minutes later in a deliberate probe — not a stranger, and not a reader in three
  months.
- **The grading is one reviewer's, inside one run.** `./classification.md` was produced by an
  earlier step of this same orchestrated run, and this step re-read the quoted text from the
  store but did not re-label all fifty independently. An independent grader is the obvious
  next check and was not run.
- **No code was read for correctness and none was changed.** The tool was consulted only
  where this document cites it.

---

*Written 2026-09-22 by the `verdict` step of run
`bc-10326884789-deliver-the-first-priority-canvas-todo-r`. Corpus HEAD
`02de26b71893d1d33d1559cd0fd9bcfcaff84652`; Canvas checkout at `6c0c5d2`.*
