# Friction: driving the canvas by hand on one real task

Written 2026-09-22 by the `friction` step of run
`bc-10326884731-deliver-the-first-priority-canvas-todo-d`, against Basecamp todo
[10326884731](https://app.basecamp.com/3934852/buckets/48039419/todos/10326884731),
*"Drive the canvas by hand on one real task"*.

The task driven was Basecamp todo **10329619223**, *errno decides the repository refusals*.
Its canvas is `canvas-store/state/canvas/bc-10329619223-errno-decides-the-repository-refusals.xml`.

Nothing was changed to write this report: no code edited, no commit made, nothing posted to
Basecamp.

## What this is written against

I read the anchoring todo's own thread before writing, as
`guidelines/correction-authority.md` requires, and I am saying here which thread and what I
found. `basecamp todos show 10326884731 --in 48039419 --md` and `basecamp comments list
10326884731 --in 48039419 --md`, oldest first, give two comments: `10329698977`, the
**Task ledger** live comment, and `10329737348`, the **Orchestrator plan** live comment. Both
are this system talking to itself — the guideline names both by prefix and says they are not
instructions and not a source of authority. So **no human comment revises this todo**, and the
highest live authority is the todo description itself, which asks for exactly:

> Record what broke in use — where the four verbs did not fit, where the vocabulary did not
> fit, where the `--base` refusal fired and whether it was right to.

and sets the done condition:

> **Done when** one real task has carried a canvas from its opening through to its end with
> every change made through `bin/canvas`, and the friction found in doing so is written down.

The headings my launch brief adds — `--why`, every refusal with its exit code, and the honest
question about whether the canvas stayed current because it was useful — are a superset of
what the description asks for and contradict none of it. Nothing here rests on the brief
alone against the description.

Every claim below points at a line of `canvas-transcript.md`, a commit in
`canvas-store/state/canvas`, or a file in the repository checkout at `canvas/`. Where the
corpus does not support an answer, I say so instead of filling it in.

## The corpus, counted

- **76** `bin/canvas` invocations are recorded in `canvas-transcript.md`
  (`grep -c '^## \`'`). Their exit codes: **71 × 0, 4 × 1, 1 × 2** (`grep -n '^exit: '`;
  the non-zero ones are at lines 118, 615, 629, 672, 808).
- By verb, over the 71 invocations whose command line begins `python3 bin/canvas`:
  **1 `create`, 43 `insert`, 11 `replace`, 15 `read`, 1 `--help`**. The remaining five are
  the same binary under a different `OPENCLAW_WORKSPACE` (transcript lines 627, 641, 652,
  667, 1562).
- **`remove` and `move` were never invoked. Neither was `history`.** Four of the seven
  subcommands `--help` lists at transcript line 1372 went unused in a canvas that ran from
  open to close. That bounds this report: I have nothing to say about `remove` or `move` in
  use, and the corpus does not support any claim about what `bin/canvas history` prints.
- The store is **55 commits**, working tree clean
  (`git -C canvas-store/state/canvas status --porcelain` is empty). Author trailers:
  **48 × `Canvas-Author: lfigea | by-hand`**, **7 × `Canvas-Author: claude-opus-5 |
  second-writer`**.
- The finished document holds **44 nodes**: 16 `text`, 14 `cell`, 7 `row`, 3 `section`,
  2 `table`, 2 `link`. **Zero `question` nodes survive** — a fact that is itself a finding,
  below.

**One caveat that qualifies everything here, stated up front.** No human being wrote to this
canvas. `canvas/cli.py:283` documents `--author` as defaulting to `'<user> | by-hand'`, so
the 48 commits trailing `lfigea | by-hand` are an agent inheriting the machine's username,
not a person at a keyboard. The todo asks whether *a person* keeps a canvas up to date when
nothing forces them to. This run cannot answer that. What it can answer — and what the rest
of this report is — is whether the tool's shape helped or hindered a writer who was keeping
it current, and where the friction is, and that part transfers.

Also: `friction-raw.md` was written mid-run and says *"The store's history is 36 commits"*.
That was true when it was written and is not true now; the final count is 55. Where this
report and `friction-raw.md` differ on a number, this report's is the one measured at the end.

---

## 1. Where the verbs did not fit

Four writing verbs — `replace`, `insert`, `remove`, `move` — and the spec's own defence of
that at `canvas/engineering-spec.md:128`: *"The semantics live in the reason, where they can
be anything, and not in a verb name, where they can only be what somebody thought of in
advance."* Where it did not hold:

**`create` needs a `read` to find out what it just made.** Transcript line 13 is the `create`;
its entire output (lines 17–20) is `Canvas-Base:` and `Canvas-File:`. It minted two nodes and
named neither. Every editing verb addresses by explicit node id and there is no selector, so
the first command after opening the canvas was the `read` at transcript line 24, whose only
purpose was to learn that the problem is `bpx2` and the expected value is `bcr2`. `insert`
prints `Canvas-Node:` precisely because it mints an id the caller did not know (transcript
line 43). `create` mints two and prints neither. **One round trip, imposed on every caller,
on their first command.**

**A table costs one command per cell.** Options table `uz6x` took **13 `insert`s** — commits
`8467e0f` (the table itself); `b7a301d`, `28985c6`, `a41ca41`, `bd1f849` (a header row and
three option rows); and `525ab66`, `65c0377`, `f54cd5a`, `8021671`, `6e29a84`, `2f10783`,
`041147e`, `4545dd3` (eight cells). Options table `ehxj` took **10** — `61ba4a9` through `213a280`.
Twenty-three commands, twenty-three reasons, twenty-three commits, to say two things. This is
not a workaround the writer chose: `README.md:375` states it as a rule — *"`insert` brings
exactly one node, and it arrives childless. There is no payload that fills a container"* — and
`README.md:386` confirms there is no `--children`, no `--file` and no stdin. **A table is not
expressible as a table.** It is expressible only as a sequence of edits that happens to end in
one.

**There is no verb that marks a question answered.** Both open questions were resolved by
`replace <question-id> --type text`: transcript line 740 (`mqxd`, commit `f7be9ea`) and
transcript line 969 (`t8zw`, commit `fad921f`). The diff the refusal at transcript line 806 printed shows
what that costs exactly: transcript line 822 is `-    <question id="mqxd" v="1">`, and the line
under it is `+    <text id="mqxd" v="2">`. **The
question stops being a question.** The finished document contains zero `question` elements —
the canvas ends with no visible trace that anything was ever asked. The writer said so in the
reason itself (`f7be9ea`): *"The question node becomes the answer because the tool has no way
to mark a question answered while leaving it standing."* That sentence is a comment about the
document's limits, written inside the document, because the document cannot carry it.

**Marking a chosen option means retyping the cell.** Commits `90907b5` (`vgke`) and `6be144a`
(`ymcz`) both prepend one word — `CHOSEN.` — and both are full retypes of cells several
hundred characters long, because `replace` takes the new text and not a patch of it. The two
command lines are at transcript lines 751 and 1212; each passes a `--text` carrying the whole
cell in order to change one word at the front of it. `90907b5`'s own reason names why: *"The tool has no way to mark a row
chosen - there is no status on a node - so the word goes in the cell's own text."*

**There is no verb that ends a canvas.** `--help` at transcript line 1372 lists seven
subcommands: `create, read, history, replace, insert, remove, move`. None is a freeze, a close
or a `done`. `canvas/engineering-spec.md` §*Lifecycle* says a canvas is frozen at `done` and is
read-only history after it. So the task reached its end and the canvas could not be brought to
one: what happened instead is the `insert` at transcript line 1399 (commit `02de26b`, node
`gjxb`) — a node that *says* the document is finished, and says in its own text that this is
weaker than a freeze: *"anybody with the ledger id can still write to it tomorrow."*

**One claim in `friction-raw.md` that the corpus does not support.** The second writer's notes
assert that *"`replace ehxj --type text` is refused because a `<table>` with children cannot
become a `<text>`"*. **No such invocation appears in the transcript.** The eleven `replace`
calls are accounted for: ten successes (`5fa80e6`, `e950b24`, `f7be9ea`, `90907b5`, `f0e23e0`,
`fad921f`, `619d585`, `6be144a`, `153152b`, `3aebd79`) and the one refusal at transcript line
806. That refusal is a real rule in the code — but it was reasoned about, not run, and I am
recording it as unverified rather than repeating it as observed.

## 2. Where the vocabulary did not fit

The vocabulary is closed and is defined in `canvas/schema/canvas.rng`, which says so in its own
header comment: *"There is no wildcard, no `<anyName/>`, no foreign namespace and no escape
hatch, by design."* The elements are `section` (nesting one level), `text`, `list`, `table`,
`figure`, `link`, `question`, and `item`/`row`/`cell` inside their own parents.

**The single largest gap: a node has no status.** Four separate wants in this canvas all
reduce to it, and every one ended as a word typed into somebody's prose:

- *"this question is answered"* — became `replace` destroying the question (`f7be9ea`,
  `fad921f`).
- *"this option is the one taken"* — became the literal word `CHOSEN.` inside a cell
  (`90907b5`, `6be144a`).
- *"the code has taken option B, and the question is still open"* — the mirror image, hit by
  the first writer at commit `35e25a1`, node `nf98`. The node ends with the sentence *"This
  node records what the code does; it does not close the question above it"* — a sentence
  about the document, inside the document, because there is no shape for a provisional state.
  It then went stale: commit `3aebd79` had to replace `nf98` because that sentence became
  false once the question *was* settled, and its reason says why that matters — *"A canvas
  whose nodes disagree about whether a question is open is worse than one that never said."*
- *"this document is finished"* — became node `gjxb` (`02de26b`).

**Authorship is on the commit, not in the document.** `--author` works: it is used verbatim
and all 7 of the second writer's commits carry `claude-opus-5 | second-writer`. But
`bin/canvas read` renders 44 nodes in one voice — the final XML carries no author attribute
anywhere. So the second writer ended up typing *"recorded by the second writer"* into the text
of node `qrpa` (commit `2d7ae95`), and the first writer typed *"by the second writer"* markers
into `mqxd`. **The same shape as the missing status: what a canvas needs to say *about* a node
has to be smuggled into the node.**

**`create`'s two nodes are untitled and indistinguishable.** Transcript lines 28–29:
`<text id="bpx2">` then `<text id="bcr2">`. Nothing in the document says one is the problem
and the other the expected value. You know it from the order and from the commit subjects
(`d65e081` *"insert bpx2: the problem the ledger row states"*). `section` carries `title` and
is the only element in the vocabulary with a human-readable name — and `create` does not use
it, and the caller cannot ask it to.

**No verbatim element.** Everything learned in this session arrived as terminal output, and
all of it went into the canvas as prose with the backticks left in as characters. Node `l32v`
(commit `61f5d74`) is the clearest case: it records seven commands and their exit codes as a
sentence — *"`ls -ld <gone>` 1; `ls -l <gone>` 1; `df -h <gone>` 1; `ulimit -n` 0"* — retyped
by hand. Node `bv2j` (`a78e225`) retypes a whole refusal message into prose. There is no
`code`, no `output`, no verbatim element; `figure` holds a source for a renderer, not a
transcript. A reader has to take the writer's word that the copying was accurate. This is
almost certainly deliberate — a closed vocabulary that admits a verbatim blob has admitted
anything — but it is the reason `canvas-transcript.md` exists beside the canvas at all, and a
user with nobody telling them to keep one would simply not have the evidence.

**The reason field has no shape.** `canvas/cli.py:239` documents `--why` as *"required, with
no default and no fallback"*, and `store.require_reason` rejects an empty or whitespace-only
one. Nothing else is checked. That is the right design — the tool has no value it could
correctly compute — but it means the field carries both *"the work made this cell wrong, not
just thin"* (`5fa80e6`) and *"column two, as above."* (`45bd148`) with no way to tell them
apart mechanically. See §5.

## 3. The staleness rule

**It fired once, on the hard branch: transcript line 806, exit 1.** The second writer
deliberately re-ran `replace mqxd` against `e950b24a…`, the base the first writer's handoff
note carried, after `mqxd` had already moved.

**Was it right to fire?** Yes, without qualification. `mqxd` really had moved — commit
`f7be9ea` replaced it — and the refused edit really had been decided against text that was no
longer there. Nothing was applied and nothing was merged, exactly as it said.

**Was what it printed enough to recover from without re-reading everything?** Yes, and the
reason it was enough is worth naming precisely. Transcript lines 810–831 carry, in order: the
message naming the node, the count (*"it moved in 1 commit(s)"*), both shas; `Canvas-Commit:
f7be9ea…`; **the intervening commit's full subject, which is the entire `--why` of the edit
that moved it**; git's own diff of the node from old text to new; four `Canvas-About:` lines
(ledger id, file, the `--base` given, the head); `Canvas-Next:` telling the caller to read
again, re-decide against the sha the read prints, and re-run with that `--base`; and
`Canvas-Exit: 1`. **The thing that made it recoverable was not the diff, it was the subject
line** — the writer could see not only that somebody had changed the node but why they said
they changed it. A `--why` of "fix" would have left the diff and nothing else. This is the one
place in the whole exercise where the mandatory reason pays for itself in a way nothing else
could substitute for.

**The soft branch fired twice, both exit 0, both applying a write against a stale base.**

- Transcript line 838, `insert qrpa`: `Canvas-Node: qrpa`, `Canvas-Base: 2d7ae95c…`,
  `Canvas-News: 6 commit(s)`, then all six intervening reasons in full, then the diff.
- Transcript line 969, `replace t8zw` against a base **seven commits old**: exit 0,
  `Canvas-News: 7 commit(s)`, seven reasons in full, then the diff.

**Was it right not to refuse?** Yes. The check is scoped to the node being written, which is
the only thing it can be scoped to without making every canvas single-writer: refusing on any
movement anywhere would mean nobody ever writes twice without re-reading, and a refusal that
fires constantly stops carrying information.

**But the cost is real and this run paid it.** The news arrives *after* the write. At
transcript line 969 the writer committed a settlement of question 1 saying *"Neither option as
written on the table below is what the tree holds"* — and node `nf98` had said since the first
half that the option taken in code is B. The contradiction was already committed by the time
the success output showed the seven commits that contained it. The repair is commit `619d585`,
whose reason states it plainly: *"I wrote it holding e950b24a, a base seven commits old, and
the tool applied the edit and told me afterwards - the soft branch - so I did not read node
nf98 … until my own contradiction of it was already committed."* **There is no way to ask the
question first**: `grep -rn "dry.run\|dry_run" canvas/` returns nothing, and `canvas/cli.py:258`
documents an omitted `--base` as *"**not** a base of 'now': it is the absence of the
question"*. A
writer who *forgets* to re-read gets the same thing, and the tool's answer to forgetting is to
tell them afterwards.

**Two further notes on `--base` in use.** First, seven reasons printed in full is several
screens; `Canvas-Base:` is at the top of it and has to be scrolled back to. *"Here is what
changed"* and *"here are seven essays"* are answered by the same output and there is no flag
that asks for the first. Second, threading the sha by hand is the only bookkeeping in this
session anyone was tempted to automate — `friction-raw.md` records the writer pulling it out
of their own transcript with `grep -o 'Canvas-Base: [0-9a-f]\{40\}' | tail -1` rather than
copying it twenty times. The flag is optional and never forced this, but *"I am the only
writer and I have just read"* and *"I want the check"* are the same situation and the tool has
no way to say the second without re-typing the first.

**What the tool does not do at all: tell you another writer exists.** `read` hands out a sha
and says nothing about how old it is, who wrote last, or whether anyone is mid-edit. The
second writer learned there had been a first one from a Markdown file beside the canvas, not
from the canvas. `git -C canvas-store/state/canvas log` answers all of it — 48 commits from
one author, 7 from another — which means **the answer exists and simply is not on the surface
the tool offers**. There is no lock and no announcement, which I think is right: `--base`
turns the race into a refusal at the moment it matters rather than into a lock somebody
forgets to release. But it makes the refusal the *only* notification, so it has to carry
everything — and on the hard branch it did.

## 4. Whether one-edit-one-node held up in use

The rule is at `canvas/engineering-spec.md:133` — *"One edit is one node. A command that would
touch two nodes is refused. This is the mechanical form of 'do not rewrite the document': the
tool cannot express a full rewrite, so no amount of drift produces one."* It is enforced in
the write path, not the parser (`canvas/store.py:1320`, `canvas/store.py:2299`), so a caller
who never touches the CLI is bound by it as hard.

**What it cost, measured.** Twenty-three of the 55 commits in this store — the two options
tables — exist only because a container arrives childless. Thirty commits landed before
the first `replace` (`git log --reverse` puts `5fa80e6` 31st). A one-word change to a cell is a full retype
(`90907b5`, `6be144a`). And it is `insert`-heavy by construction: of the 55 commits,
**44 are `insert`, 10 are `replace` and 1 is the `create`**
(`git log --format='%s' | awk '{print $1}' | sort | uniq -c`).

**What it bought, measured.** Six nodes were corrected in place, each with its own recorded
reason, and every one of the six is a case where the canvas was wrong and got fixed rather
than left:

- `5fa80e6` — `lgvs`, a cost cell that running the other route made *wrong* rather than thin.
- `e950b24` — `echr`, a call-site count the writer had got wrong by grepping.
- `f0e23e0` — `lp37`, an estimated cost replaced by the paid one.
- `619d585` — `t8zw`, a settlement that misdescribed which option it took, corrected ninety
  seconds after being committed.
- `153152b` — `smym`, the same for the other table.
- `3aebd79` — `nf98`, a sentence that went false when the question it described got settled.

**Was what it cost worth what it bought? Yes — and the mechanism is specific, not general.**
The reason these six corrections happened is that each of them was *one command*. The writer
did not have to reopen a document, find the paragraph, decide what else had drifted, and
re-justify the whole thing; they replaced one node and wrote one sentence about what changed
their mind. `619d585` is the strongest case: it is a correction made ninety seconds after the
mistake, at a moment when nothing whatsoever forced it, on a canvas nobody else was reading
yet. That is precisely the moment this exercise exists to observe, and the cheapness of the
edit is what carried it.

**The qualifier.** The payoff is supposed to be readable through `bin/canvas history <node>`,
and **`history` was never run in this session** — 0 of 76 invocations. So the six corrections
are legible in the corpus because `git log` in the store shows them, not because the tool was
asked to show them. I cannot report on what `history` prints, and `friction-raw.md`'s
statements about what `bin/canvas history <id> lgvs` "now reads as" are inferences from the
git history, not observations of the tool.

## 5. Whether `--why` earned its place

**What this is.** One canvas's worth of reasons, offered as an honest sample. There is a
sibling todo, **10326884789**, that rules on `--why` across fifty reasons; **I am not doing
that, and nothing here is a ruling.** This is the contribution of this canvas's reasons, with
the quotations, so that somebody else's verdict can be made against real text.

The store has 55 commits. Three of them — `0b2e20b` (*"create …: born at open, root only"*),
`d65e081` (*"the problem the ledger row states"*), `e694e94` (*"the expected value the ledger
row states"*) — are `create`'s own, not typed by a caller. That leaves **52 caller-written
reasons**.

**Reasons a reader is better off for having.** These change what a reader does, not just what
they know:

- `7a5b1f9` (`fdzu`): *"the launch brief for this half said to branch from main, and branching
  from main would have produced a change to a function that does not exist there. … Putting it
  at the top of the canvas because it is the first thing that would waste anybody else's
  afternoon."* A reader who skips this builds on a wrong assumption about the branch.
- `5fa80e6` (`lgvs`): *"the work made this cell wrong, not just thin. … Replacing rather than
  adding a note, because the old sentence would otherwise still be sitting there being the
  weaker argument."* Says both what changed and why it was a replace.
- `e950b24` (`echr`): *"I wrote this node an hour ago off a grep … Three of those four catch
  FileNotFoundError separately before the line I counted … checked by spying on the function
  rather than by reading the code again, because reading the code again is what produced the
  wrong count."* Tells the next reader how the first answer was wrong *and* what method to
  trust.
- `619d585` (`t8zw`): *"correcting my own resolution of this question, ninety seconds after
  writing it, and the correction is the finding."* The reason is the record of a tool
  behaviour, and it is the only place that behaviour is written down at the point it bit.
- `f7be9ea` (`mqxd`): *"Decided on evidence rather than on taste - running every command all
  fifteen `_OS_NEXT_ACTION` templates name showed four of them are not commands at all."* This
  one earned its place twice over: it is also the text the hard-branch refusal printed at
  transcript line 813, and the thing that made that refusal recoverable.
- `3aebd79` (`nf98`): *"A canvas whose nodes disagree about whether a question is open is worse
  than one that never said, because a reader trusts the nearest sentence."*
- `2ef45c2` (`fxp8`): *"a canvas that only claims the conditions hold is exactly the assertion
  it forbids. Writing the observed strings … rather than the word passed."*
- `b62b428` (`aqr3`): *"Naming the branch point in the same breath as the branch, because it is
  the single fact most likely to waste somebody's afternoon."*

**Reasons a reader is not better off for having.** Five of the 52 restate the node's own
content or its position and add nothing a reader could not see in the diff:

- `2cfb511` (`vp52`): *"column one, as above."*
- `45bd148` (`be5v`): *"column two, as above."*
- `96276cf` (`rysw`): *"the header row, matching question 1's two columns. Same shape, same
  reading."*
- `8f38fae` (`vqpn`): *"option A's row: no, it may not."*
- `8c6da79` (`yh66`): *"option B's row: yes, provided the reader can tell a diagnostic from a
  repair."*

Two more are borderline and I will name them rather than pick a side: `28985c6` (`fu7f`) —
*"option A's row. One row per option so that each one can be read, argued with and eventually
struck out on its own"* — gives a design rationale that is true of every table ever written,
and `b7a301d` (`s437`) — *"the header row: the table has two columns and nothing else in the
vocabulary can say so, since a `<table>` carries no column names and a `<cell>` carries no
header flag"* — is genuinely informative, but about the *format*, not about the work.

**What the pattern is, and it is not about the writer.** Every one of the five useless reasons
is attached to a `row` or a `table` — a structural container with no content of its own, whose
existence has one honest explanation, which is that a table needs rows. **The rule that
manufactured those five is the same rule that produced the good ones.** Of the 44 nodes in the
finished document, 23 are `table`, `row` or `cell`; the reasons on the substantive `cell`s
(`qdvs`, `lgvs`, `smym`, `lp37`, `vgke`, `ymcz`, `zksk`, `fbym`, `rt82`, `mkyr`) are mostly
good, and the reasons on the pure scaffolding are mostly padding. Whoever grades fifty reasons
should know that the proportion of scaffolding in any sample is a property of how much
tabular structure the canvas happened to need, not of the writer's diligence.

**The honest verdict from this sample.** `--why` earned its place, and the decisive evidence
is not the good reasons in the log — it is transcript line 813, where a refusal handed a
stranger somebody else's reason and that reason was enough to re-decide from. The cost is five
padded sentences out of 52. The mandatory reason is also, by the first writer's own account in
`friction-raw.md`, **the thing that stopped anyone reaching for a text editor** at the one
moment they wanted to: *"the reason I didn't reach for the file was the `--why` again, not the
tool being convenient."*

## 6. Every refusal the tool issued

Five non-zero exits in 76 invocations.

- **Transcript line 118 — `insert --into r --type row --why x` — exit 1.** A shell slip: `r`
  is not a node id. Printed: *"no node with id r in this canvas: nothing was changed"*,
  `Canvas-Node: r`, two `Canvas-About:` lines, and `Canvas-Next:` naming
  `bin/canvas read <ledger>` as printing every id, with the note that `root` names the canvas
  itself. **Right to fire** — the request was wrong against the store as it stands.
  **Did the next action work? Yes, and it was actually run**: the very next invocation, at
  transcript line 131, is that `read`, exit 0. This is the only refusal in the corpus whose
  printed next action was executed and observed to resolve the thing that caused it.
- **Transcript line 615 — `read no-such-ledger` — exit 1.** Deliberate, reproducing the
  anchoring work's own Case 2. Printed the missing path, and a `Canvas-Next:` of
  `create no-such-ledger --problem "<the problem>" --expected-value "<the expected value>"`.
  **Right to fire.** **The next action is a form, not a runnable command** — it carries
  `<placeholder>`s. Not run for this ledger id.
- **Transcript line 629 — the same refusal in a throwaway workspace — exit 1.** Same verdict.
  Here the next action *was* exercised, with the placeholders substituted: transcript line 641
  runs `create rec --problem P --expected-value V`, exit 0, and line 652 reads it back, exit 0.
  **So the advice works when a human fills the form in, and only then.**
- **Transcript line 672 — `create '<ledger-id>' --problem '<the problem>' …` — exit 2.** The
  ENOENT template's repair, run **verbatim as the template prints it**. Refused: *"not a usable
  ledger id: '<ledger-id>'"*. **Right to fire** — and this refusal's *own* `Canvas-Next:`
  (*"re-run naming a ledger id of `[A-Za-z0-9._-]` that does not start with a dot"*) is correct
  and actionable. The finding is not against this refusal but against the one upstream of it:
  a next action that a reader would take for a repair is a form. This observation is what
  settled open question 2 (node `l32v`, commit `61f5d74`; decision at `f7be9ea`).
- **Transcript line 808 — `replace mqxd --base e950b24a…` — exit 1.** The staleness refusal,
  covered in full in §3. **Right to fire.** Its next action — read, re-decide, re-run with the
  new base — **was not executed in this run**, because the edit it refused was a deliberate
  probe and `mqxd` had already been settled at transcript line 740. So I can say the printed
  next action was coherent and that its *content* was sufficient to re-decide from; I cannot
  say from this corpus that running it works, because nobody ran it.

**Summary of the recovery question.** Of five refusals, one had its next action run and
observed to work (line 118); one had an equivalent next action run successfully after a human
filled in its placeholders (line 629 → 641); two named next actions that are forms and were
not runnable as printed (lines 615, 672 — and this is a defect the canvas itself now records);
one named a next action that was never exercised (line 808). **Every one of the five was right
to fire. Not every one named something a caller could type.**

## 7. Did the canvas stay current because it was useful, or because this run was told to?

**Honest answer: it was told to, and in three specific moments it would have stayed current
anyway.** Both halves of that matter.

**It was told to.** The anchoring todo's description is explicit — *"maintain it through the
work"*, *"using the tool as the only way the canvas changes"*, *"not fixing up the file by
hand when the tool is inconvenient, because the inconvenience is the finding"*. A run under
that instruction cannot produce evidence that an uninstructed person would do the same, and I
am not going to pretend otherwise. The clean result — 55 commits, no hand edit, no `sed`, no
`git commit` inside the store, working tree clean — is a result about compliance, not about
motivation.

**Where it paid without being forced.** Three corrections happened at moments where nothing
was watching and stopping would have cost nothing:

1. **`5fa80e6`** — running the non-racy case made a cost cell the writer had authored an hour
   earlier *wrong*, not merely incomplete. One `replace`, one reason. Nobody would have known.
2. **`e950b24`** — a call-site count that was wrong because it came from a grep. The writer
   found it by checking empirically, and replaced rather than appending a retraction, on the
   argument that *"leaving it visible with a retraction under it is worse than one true
   sentence"*.
3. **`619d585`** — ninety seconds after committing a settlement, the writer noticed it
   contradicted a node three lines below and corrected it.

**What those three have in common is the unit of edit.** Correcting a node cost one command
and one sentence. The generalisable claim from this run is not *"people will keep a canvas
current"* — this run cannot show that — it is **"if being wrong costs one command to fix, it
gets fixed, and if it cost a document revision it would not."** Three data points, all in the
corpus, all at moments with no external pressure.

**Where keeping it current was overhead.** Three places, all measured:

- **The options tables.** 23 commands and 23 reasons for two tables. Five of those reasons are
  padding (§5). This is the one place the writer records having wanted a text editor.
- **Threading `--base` by hand.** Twenty-odd edits in, the sha was being extracted from the
  writer's own transcript by shell pipeline rather than copied.
- **Overlapping claims with nothing keeping them in step.** When `echr` turned out to be wrong
  (`e950b24`), the git *commit message* of the code change said the same wrong thing and had to
  be amended separately. The canvas and the commit message carry overlapping claims and nothing
  checks one against the other; that one was caught because it had just been written, not
  because anything looked.

**Where the canvas was not the thing that carried the understanding.** This is the sharpest
negative result in the corpus and it belongs in the answer. The canvas is supposed to hold the
shared understanding between a person and the agents on a task. In practice:

- The second writer found out there *was* a first writer from a Markdown file beside the
  canvas, not from the canvas (§3).
- *"Which nodes did I write?"* was answered by `git log`, not by `bin/canvas`.
- *"Are there any `question` nodes left?"* — the literal done condition of the second half —
  was answered by piping `read` through `grep`, because `read` is all-or-nothing with no
  `--type`, no `--node`, no selector. On 44 nodes that is tolerable. It grows with exactly the
  canvases worth keeping.

All three answers exist one layer below the tool, in a git repository the rules of this
exercise forbid writing to by hand. **You are allowed to read your way out of the tool's gaps
and not to write your way out of them** — which is the right asymmetry, and is also the exact
measure of how much of this canvas's usefulness came from the tool and how much from the store
underneath it.

## 8. What this report does not cover

- **`remove` and `move`.** Never invoked. The corpus supports no finding about either.
- **`history`.** Never invoked. The corpus supports no claim about what it prints, including
  the claims `friction-raw.md` makes about it.
- **Whether a *person* maintains a canvas unprompted.** All 55 commits are machine-authored;
  the `lfigea | by-hand` trailer is `--author`'s default (`canvas/cli.py:283`), not a human.
- **Whether `replace` on a populated container is refused.** Reasoned about in
  `friction-raw.md`, never run (§1).
- **A verdict on `--why` across fifty reasons.** That is todo 10326884789's. §5 is one sample
  with its text quoted, offered for that verdict to be made against.
