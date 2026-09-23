# Node identity

Settled 2026-09-22. This document decides how a node's `id` is minted and what
keeps it stable, before any verb is written. It is scoped to what step 1 of
*The path* needs in order to be buildable — `bin/canvas`, four verbs, git-backed,
no renderer. It did not claim to settle wholesale restructure: sections 7 and
8, settled 2026-09-23, close the two parts of that remainder it first left open
— what a merge and a split do to lineage, and whether a restructure may ever be
atomic. What is still open is named at the end.

The reason it is settled now and not later: `replace`, `insert` and `move` all
either mint or preserve an id, so the first implementation of any of them
chooses an identity rule whether or not anybody wrote one down. A rule arrived
at implicitly is a rule nobody can argue with afterwards, because there is
nothing to point at.

It holds the spec's existing commitments fixed rather than relitigating them:
ids are stable for the life of the node, addressing is by explicit id, one edit
is one node, one edit is one commit, and a node's history is
`git log --grep='Canvas-Node: <id>'`. Every rule below was checked against those
five, and where a candidate rule contradicted one, the candidate was the thing
that gave way.

## What an id is

**An id names a position in the argument, not the text that currently occupies
it and not the element type that currently expresses it.**

This is the definition the rest of the document rests on, so it is worth being
blunt about what it rules out. A node is not identified by its content — content
is exactly what `replace` changes. It is not identified by its place in the tree
— place is exactly what `move` changes. It is not identified by its node type —
type is exactly what an options `<table>` settling into a `<text>` changes. What
persists across all three is the claim the document is making at that spot, and
the accumulated record of why it makes it.

That record is the point. A node's id is the key that `git log --grep` joins on,
so an id is worth precisely as much history as it can still reach. Every rule
below is chosen to maximise the span of reasons a single id still reaches, and
rejected alternatives are rejected on the same measure: how much history they
detach, and when.

en-quire is the existence proof of getting this wrong. It addresses sections by
heading text and derives history from line ranges, so the first rename detaches
a node from its own reasons — and worse than losing them, it silently attaches
them to whatever text now occupies those lines. A wrong history that looks right
is the failure mode to design against, not a missing one.

## 1. Minting an id on `insert`

**`insert` is the only verb that mints an id.** The tool mints it; there is no
`--id` flag and a caller cannot supply one.

An id is a four-character token, first character a lowercase letter, remaining
three drawn from lowercase letters and digits with the visually confusable
`l`, `1`, `o`, `0` and `i` excluded. It is drawn at random, not derived from
anything. Before it is used it is checked for having ever been used, and on a
collision it is drawn again.

**It is derived from nothing, which is the point.** The candidates that derive
an id from something all fail on the same axis:

| derivation | why it was rejected |
|---|---|
| a hash of the node's content | changes on every `replace`, which is the one thing an id must survive; and two identical paragraphs collide by construction |
| position in the tree, or a heading path | changes on every `move`, and this is precisely en-quire's failure |
| the next number after the highest id in the file | reuses the ids of removed nodes, which fuses two unrelated nodes' histories under one grep — see below |

That third one deserves its cost stated plainly, because a counter is the
obvious thing to build and it is wrong in a way that does not show up until
later. Remove node `b7`, insert a new node, and a high-water counter that
counts what is currently in the file hands the newcomer `b7` again. From that
moment `git log --grep='Canvas-Node: b7'` returns two nodes' histories
interleaved in one list, with nothing in the output marking the boundary. The
reasons for a decision that was deleted six weeks ago are now presented as the
reasons for the node that took its place. That is the en-quire failure again,
reached by a different road.

So: **a retired id is never reminted.** Uniqueness is checked against every id
that has ever existed, not against the ids currently in the file.

**The uniqueness check is the git history itself.** A candidate id is free if
`git log --grep='Canvas-Node: <candidate>'` is empty. No registry file, no
allocator state, nothing to keep in sync with the document. This works because
every node is named in at least one commit — its own `insert` — so the set of
ids ever minted is exactly the set of ids the log has ever mentioned.

**Ids are unique across the whole canvas repository, not within one file.** The
canvas directory is one git repository holding `<ledger_id>.xml` for every
ledger row, and the spec's history command is written without a path filter. If
ids were scoped per canvas, `git log --grep='Canvas-Node: b7'` would return the
histories of one node in this task and an unrelated node in some other task,
fused. Path-scoping the grep would also fix it, and was rejected: it makes the
correctness of every history lookup depend on somebody remembering a flag, and
the command as the spec writes it would be quietly wrong. A globally unique id
makes the documented command correct as written.

**Four characters is enough, and short on purpose.** Ids are typed by hand on a
command line — `canvas replace b7 --why "..."` — and read in commit trailers, so
length is a usability cost paid on every single edit. The excluded-character
alphabet gives about nine hundred thousand tokens; a canvas is bounded by what
is affordable to put in every step's prompt, so the population that has to stay
distinct is small, and the history check makes a collision a re-draw rather than
a corruption. If the repository ever grows past the point where re-draws are
noticeable, the fix is a fifth character and no change to any rule here.

**An id is stable across a re-read of the file, because it is stored in the
file.** It is an attribute, written once at insert and never recomputed. Reading
the canvas twice — or reading it after ten unrelated edits — returns the same
id for the same node. Nothing anywhere recomputes an id from content, position
or type, and no rule below introduces a case where one is recomputed.

## 2. `replace` keeps the node's id — including across a type change

**`replace` never mints and never changes an id.** The node keeps it, and it
keeps it when the new node is a different node type.

The spec's own worked example is the case that decides this. An options
`<table>` becoming a settled `<text>` is a `replace` on the table node, with
`--why "chose A over B: ..."`. There is no `resolve` and no `supersede` verb;
this is how a decision gets made in a canvas, and it is the most consequential
edit the tool supports.

**The rejected alternative was minting a new id on a type change**, on the
reasoning that a table and a paragraph are plainly not the same node. Its cost
is exact and it lands on the most important edit in the system: the settled
decision would have a history one commit long, and every argument that produced
it — the options, the comparison, the reasons each row was written — would be
stranded under an id that is no longer in the document and that nothing in the
document points at. Ask the new node what it was for and it answers "chose A
over B". Ask it why those were the options, and there is no longer a question
you can ask.

It also reintroduces, through the back door, the verb the spec deliberately does
not have. If `replace` can sever a lineage, something has to be able to say "new
node `b9` continues `b7`" — and that thing is `supersede`, wearing a different
hat, with its own attribute to maintain and its own way of being wrong.

So the definition in *What an id is* holds without exception: the id names the
slot, the element type is just how the slot is currently expressed, and changing
the expression is not changing the node. The node type is content.

## 3. `move` does nothing to an id

**`move` changes position and nothing else.** The id is unchanged, the content
is unchanged, and the node's type is unchanged. Moving a node between sections
is the same: reparenting is a position change.

This is a direct consequence of the spec's choice to address by explicit id
rather than by selector. If position were any part of identity, then addressing
by id would be a lie — the id would be a cached lookup of a position and would
have to be invalidated when the position changed.

**A node's children travel with it, and the move is still one node's edit.**
Section 5 settles that case with the rest of the container rule: position is a
property of the child, so moving a container changes where the container sits
and changes nothing any child's own record says.

**The rejected alternative — re-minting on move — would make restructure
maximally destructive**, which is the exact opposite of what the hardest open
item needs. A restructure is mostly moves. Under a re-minting rule, reordering
two paragraphs detaches both from their reasons, and reorganising a section
detaches everything in it. Under this rule, a restructure composed of moves
costs no history at all: every node keeps its id, so every node keeps its
reasons, and the history of the restructure itself is in the log as the sequence
of moves that performed it, each with its own `--why`.

## 4. What happens to `v`

**`v` is the number of edits a node has been the subject of.** It is not a
content hash, not a concurrency token and not a timestamp. Staleness is handled
by `--base` against a commit sha, as *Staleness* specifies, and `v` deliberately
does not duplicate that job.

The rule is one line:

> **`v` equals the number of commits whose `Canvas-Node:` trailer names that
> node.**

Which gives, verb by verb:

| verb | effect on `v` |
|---|---|
| `insert` | the new node is born with `v="1"` — it exists because of one edit, the one that created it. No other node's `v` changes |
| `replace` | the replaced node's `v` bumps by one. No other node's `v` changes |
| `move` | the moved node's `v` bumps by one. Neither the old nor the new parent changes |
| `remove` | the node leaves the document, so there is no `v` left to bump. The commit that removed it is the last entry in its history, and its id is retired |

**Why that invariant and not "bump on content change".** Tying `v` to the
`Canvas-Node:` trailer makes it derivable and therefore checkable:
`git log --grep='Canvas-Node: b7' | grep -c ^commit` and the file's `v="..."`
have to agree, and a canvas where they disagree is corrupt and can be found to
be corrupt by a script nobody has to think hard about. The alternative — `v`
bumps only when content changes, so `move` leaves it alone — reads more
intuitive and costs the invariant: `v` becomes a number you have to trust,
maintained by a rule with an exception in it, verifiable against nothing. The
case where it matters is also the case where it was rejected: a node shuffled
repeatedly through a restructure is exactly the node a reader should be told has
been churned, and a content-only rule reports it as untouched.

**A container's `v` does not bump when its children change.** Inserting into a
section, removing from it, or moving a node in or out of it changes the
children's `v` and never the section's. This is not a separate rule — it falls
straight out of the invariant, because the commit names the child. It also has
to be this way for a second reason: if a section's `v` bumped on a commit that
named a child, then `git log --grep` on the section would not contain the commit
that changed the section's own `v`, and `v` would become the one number in the
file that its own node's history cannot account for.

**The canvas's creation commit creates the root only.** `<canvas>` carries no
`id` and no `v`, so it is outside all of this. The two nodes the ledger's `open`
contributes — the problem and the expected value — arrive as two ordinary
`insert` commits, each naming its own node, each born at `v="1"`. Creating the
file with two nodes already in it would be one commit touching two nodes, which
is the rule the tool exists to make inexpressible; the birth of a canvas gets no
exemption from it.

The net effect is an invariant worth stating on its own, because it is what
makes the grep trustworthy:

> **A node's entire life — its birth, every edit it was the subject of, and its
> death — is exactly the set of commits that name it.**

Nothing happens to a node that its own history does not record.

## 5. What "one node" means when the node has children

**Nothing happens to the children.** `replace` on a node that has children
replaces that node and nothing else: its type, and its own attributes — a
`<section>`'s `title`. Its children keep their ids, their `v`, their content
and their order.

**The rule is about containers and not about `<section>`.** This section was
first written for the section, because the section was the container under
discussion at the time. It is not the subject. Every container the vocabulary
has is covered by it, on one argument: `<section>` holds sections and leaves,
`<list>` holds `<item>`, `<table>` holds `<row>`, `<row>` holds `<cell>`, and
`<canvas>` holds everything — and in each of them the children are separate
nodes with separate ids, edited by separate commands. So `canvas replace
<container-id>` renames a container; it does not and cannot re-express what is
inside it. Where this section says *a container*, it means any of those, and
`<section>` is only the example.

The whole of it, verb by verb:

| verb, applied to a container | what happens to the subtree | what happens to the container |
|---|---|---|
| `replace` keeping the type | untouched: every child keeps its id, its `v`, its content and its order | its own attributes are replaced, its `v` bumps |
| `replace` changing the type | — | **refused while it has children** |
| `replace` supplying character data | — | **refused while it has children** |
| `remove` | — | **refused while it has children** |
| `move` | travels with the container, untouched: no child's id, `v`, content or order changes, and no child's history records the move | its position changes, its `v` bumps |
| `move` into its own subtree | — | **refused** |
| `insert` | there is none: a node is born childless | born at `v="1"` |

### `replace` on a container: what is permitted and what is refused

The distinction is between **the payload** and **the node it is applied to**,
and getting it the wrong way round produces a different tool. Stated plainly so
that it cannot be read two ways:

- **Replacing a container that has children is permitted**, and renames it. A
  `<section>` of eight nodes can be retitled with one command, and the eight
  nodes are not touched, not re-expressed, and not mentioned in the commit.
  This is the ordinary case and it is the headline of this section.
- **What is refused is a payload that would reach into the subtree.** There is
  no flag that expresses a child — `--type`, `--text`, `--title` and `--href`
  are four scalars and there is no `--children`, no `--file` and no document
  body — so "a `replace` payload that rewrites N children" is **inexpressible**
  here rather than merely refused. Nothing has to check for it because nothing
  can say it.

Two things a payload of four scalars *can* still say reach the subtree
indirectly, and those two are the refusals:

**`replace` that would change a container's type is refused while it has
children**, because the new type has nowhere to put them. A `<text>` holds
character data and no elements; a `<list>` holds `<item>` and not `<cell>`.
Move the children out first, then replace the empty node. They keep their ids
throughout, which is the entire benefit.

**`replace` that would give a container character data is refused while it has
children**, because no node in this vocabulary holds children and text at once.
The text would be silently dropped by the serialiser, which is the failure this
whole document is designed against: a write that reports success and did not do
what it said.

Accepting either would be a single commit rewriting N nodes under one
`Canvas-Node:` trailer, which breaks one-edit-is-one-node and
one-edit-is-one-commit in the same stroke, and leaves N−1 nodes changed by a
commit their own history never sees. It is also, precisely, the whole-document
rewrite verb that three funded 2026 projects shipped next to a correct
base-version check, arriving here in the one place the vocabulary makes it look
reasonable. A root-level section replace being a whole-file rewrite is already
recorded in the survey as en-quire's third defect.

### `remove` on a container

**`remove` on a container that still has children is refused**, for the same
reason in the other direction. A cascading delete either names N nodes in one
trailer or names one and lets N−1 nodes vanish in a commit no grep on them will
ever return — so a reader asking a dead id for its history would be shown a
node that, by its own record, is still alive and was last edited cheerfully.
Empty the container first. Each child's removal is its own commit with its own
`--why`, which is a requirement and not an inconvenience: "we deleted this
section" is not a reason for deleting any particular thing that was in it.

### `move` on a container, which carries its subtree and is still one node

**A `move` takes the container's whole subtree with it, and that is one node's
edit.** N+1 nodes change where they sit in the document, one node is named, and
one node's `v` bumps: the container's.

That is consistent rather than an exception, and the reason is worth stating
because it is the same reason section 4 gives for a container's `v` not bumping
when its children change. **Position is a property of the child.** A node's own
record says whose child it is; it does not say which children it has. Move a
`<table>` into a `<section>` and every `<row>` in it is still a child of that
same `<table>`, in the same order, with the same content and the same `v`. Not
one child's record has changed, so not one child's history is missing anything,
and the invariant holds exactly: nothing happened to those nodes that their own
histories do not record, because nothing happened to those nodes.

The alternative — refusing to move a populated container, or bumping every
descendant's `v` — is the one this rule was chosen over. Refusing would make
restructure, which is mostly moves, cost the whole subtree; bumping every
descendant would report N nodes as edited by a commit that names one, which is
the same lie as the cascading delete with a friendlier face.

**`move` of a container into its own subtree is refused.** It is the one
position that is not a position: the container and everything under it would
leave the document altogether, and the commit would name one node while N
disappeared.

### `insert` on a container, and what an `insert` may bring with it

**An `insert` brings exactly one node, and the node it brings is childless.**
`insert --type section` creates an empty section; `insert --type table` creates
an empty table. There is no payload that fills one, for the same reason
`replace` has none: a flag that carried children would be a multi-node write
wearing a single verb's name.

So a populated section is built the way it is emptied — one node at a time,
each with its own reason. `schema/canvas.rng` makes every container
`zeroOrMore` and never `oneOrMore` precisely so that the empty container each
of those sequences passes through is a legal document and not a state the tool
has to hide.

### Where this is enforced

Not in the command line, and not only in the four verbs. `canvas/store.py`
compares the document it is about to write against the document already on
disk, and refuses unless exactly the node named in the commit's `Canvas-Node:`
trailer is the one that differs — same types, same attributes, same character
data, same parent and the same order for every other node. The comparison is
this section's rule expressed as data, which is why a container travelling with
its subtree passes it and a payload that rewrote that subtree does not.

The write path is private and there is no public function anywhere in the tool
that takes a document. A whole-document rewrite is therefore not a verb someone
declined to add to the command line: it is a write no code path in the tool will
perform, for any caller, from any import path. The one write that names no node
is the birth of a canvas, and the only document it may produce is the root
alone, which is section 4's rule checked by the same guard.

### The refusals name what they refused

**The refusals follow IWE's error surface**, as *What to copy* requires: a
refusal names the container, names every child id the rejected write would have
touched, and says what to do instead — each child, with its own `--why`, one
node at a time. Every one of them exits non-zero and writes nothing: not the
file, not a commit, not a temporary. An agent can act on that. It cannot act on
the word "refused".

This section described the container refusals, and it is now the tool's general
contract: every refusal anywhere in it names the nodes it involves, or the thing
it is about where it has none, and states the next action that would succeed.
README section *What a refusal prints* gives the shape.

**What this costs, stated honestly.** Restructuring is tedious. Reorganising a
section of eight nodes is eight commands and eight reasons, not one. That is the
intended trade and it is the same trade the four verbs already make everywhere
else: the tool is slow in exactly the places where being fast means being able
to destroy things. What it buys is that a restructure performed this way costs
zero history — every node keeps its id, so every node keeps every reason it ever
carried.

## 6. Naming a position, including inside an empty container

Settled while building the store, because step 1 could not be built without it.
An earlier draft listed it under *Still open*: "`insert --after <node-id>` cannot
name the first position of an empty container. There is no node to be after."

**A position is named by exactly one of two things.**

- **`--after <node-id>`** — immediately after that node, in that node's parent.
  Unchanged; this is the flag the engineering spec already has.
- **`--into <container-id>`** — as the **last child** of that container. For an
  empty container that is its first and only position, which is the gap.

`<canvas>` carries no `id`, so it is named by the reserved word **`root`**:
`--into root` appends to the document itself. `root` can never collide with a
minted id, and not by convention — by construction. The id grammar is
`[a-z][a-hj-km-np-z2-9]{3}` and `o` is excluded from positions two, three and
four, so `r-o-o-t` fails the pattern and no draw can ever produce it. (`head`
does *not* fail the pattern. Nothing in this tool may ever use `head` as a
reserved word.)

**Last child rather than first.** For an empty container the two are identical,
so either closes the gap; last is chosen because it makes one rule cover both
cases — `--into C` always means "append to C" — whereas first would mean a
document built with repeated `--into` comes out in reverse reading order, and
anything wanting reading order would fall straight back to `--after`. The
canvas's own birth is exactly that case: the problem, then the expected value.

**Rejected: let `--after <id>` accept a container id and mean "as its first
child".** It makes `--after b7` unreadable without knowing `b7`'s element type —
if `b7` is a `<section>`, does the node land after the section or inside it?
Both are plausible readings of one command and they produce different documents,
so an agent can issue a correct-looking command and get the wrong edit with no
error. That is the class of failure this document exists to avoid: addressing
that depends on anything beyond the explicit id.

**Rejected: a synthetic sentinel position per container, `--after <container>:0`.**
It invents an identity that is not a node, in a system whose one invariant is
that a node's life is the set of commits naming it. The sentinel would appear in
no commit, be born and retired with its container, and have to be excluded by
hand from the uniqueness check.

**Rejected: `--position <n>`, an index into the container.** An index is a
position, and position is exactly what `move` changes. Every index in a script
goes stale the moment anything is inserted above it — en-quire's line-range
failure arriving through a new door.

## 7. Merge and split: lineage ends at the retired id, and the reason carries the pointer

Settled 2026-09-23, against an exercise rather than against a prediction of one.
`docs/merge-and-split/` holds every `bin/canvas` invocation of a real split and
a real merge, with exit codes and complete output, and a findings file beside
it. The corpus behind the friction record could not settle this: in its 76
invocations there is no `remove`, no `move`, and `history` was never run once,
so nothing in it said what a stranded id answers. Now something does.

Of the two options the closing section named, this is the second one. **A
node's lineage is the set of commits whose `Canvas-Node:` trailer names its id,
and it ends where that set ends.** The tool records no ancestor and no
successor — not in the document, not in a trailer, not anywhere. Where a merge
or a split moves one node's material into another id, the pointer to that id
lives in the `--why` of the edit that moved it, and naming it there is part of
what makes the reason a reason rather than a decoration on one.

### What happens to each of the four ids

**The split's retained id keeps everything.** It is a `replace`, so section 2
already decides it: the id is unchanged and every reason ever written for it is
still reachable by asking for it. In the exercise the `replace` on `e8ec`
(`canvas-transcript.md:148`) returned `Canvas-Node: e8ec`, and
`history … e8ec` (`:230`) prints two entries — the original `insert` and that
`replace` — under one header, with the node at `v="2"` in the final read
(`:375`). Nothing detached.

**The retained id's reason cannot name the id born beside it, and that is
forced rather than chosen.** The `replace` that cuts the node down runs before
the `insert` that mints the other half, so at the moment the reason is written
there is no id to name. Nothing repairs it afterwards: a second `replace` whose
only content is a cross-reference is a commit whose `--why` is about the tool,
which is the one thing a reason may not be about. What the retained reason has
to say instead is what the node no longer holds and that it is going into its
own node — which is what `e8ec`'s says at `:148`, and which is enough for a
reader to know to look at what follows it.

**The split's born id starts one edit old, and that is correct rather than a
loss.** `history … dkjk` (`:250`) prints exactly one entry, its own `insert`,
and the node is `v="1"`. Under *What an id is* a node names a position in the
argument, and this position did not exist before the split: there was one claim
where there are now two, and the second one is genuinely new. What the born
node inherits is not history but a sentence. Its `insert`'s `--why` must name
the id it was cut out of, and in the exercise it does — *"This content was the
second sentence of e8ec until the replace one commit earlier"*. Take that
sentence out and the node's record holds no trace of its origin at all: the
commit that split `e8ec` does not appear in `dkjk`'s history, because `history`
returns the commits whose trailer names `dkjk` and that commit names `e8ec`.

**The merge's surviving id keeps everything and takes on the claim.** Again a
`replace`: `history … oskz` (`:266`) prints its `insert` and its `replace`,
`v="2"` in the final read. Its `replace`'s `--why` must name the id whose
material it is taking over, and at `:266` the printed reason does — *"Node dwqu
holds that clause today and will hold nothing this node does not once this
commit lands."* That sentence is the whole of the forward pointer; nothing else
in that output contains the string `dwqu`.

**The merge's stranded id is where the rule earns its name: the lineage ends,
and it ends completely rather than partially.** This is the fact the ruling
rests on and it is the one that had to be run for real.
`bin/canvas history bc-10330566962-merge-and-split-exercise dwqu`, asked after
the node was removed and gone from the document, **exits 0** and prints the
node's whole life, oldest first, with the removing commit last and its complete
reason (`:286`):

```
Canvas-Node: dwqu

Canvas-Commit: f05035c60e48dcfdab36631acad1b29acc13aa29
Canvas-Author: lfigea | by-hand
insert: States the losing half of the same merge cost, quoting node-identity.md:446. …

Canvas-Commit: ce80ed3bb301f01e1f4864edf58a7b6a60ed0aa2
Canvas-Author: lfigea | by-hand
remove: The one clause this node holds — that the losing id's reasons dead-end at a retired id the survivor does not point at — now stands word for word inside node oskz, …
```

There is no refusal, no warning, and no marker in that output saying the node
is gone; the shape is identical to a live node's, and only the presence of a
`remove:` entry says otherwise. (An id no commit ever named is a different
case and the tool does distinguish it: `history … root` at `:358` exits **1**
with *"no commit names it, so it was never a node of this canvas"*.)

**So what a merge costs is not the history. It is the path from the document to
the id.** The final `read` (`:375`) contains no occurrence of `dwqu` — not in
an id, not in an attribute, not in any text — and `history` takes the id as a
required positional. There is no command that lists retired ids and none that
searches reasons. A reader who does not already hold the string `dwqu` reaches
it by exactly one route: the sentence in `oskz`'s reason that names it. That
two-hop path was walked in the exercise and it worked, and it worked because a
person wrote the id into a reason.

### Why the pointer belongs in the reason and not in a field

Because the reason has to carry it anyway.

Section 5 sets the bar on a `remove`: each removal is its own commit with its
own `--why`, and *"we deleted this section" is not a reason for deleting any
particular thing that was in it*. Apply that to the losing half of a merge and
the phrase a writer reaches for — *merged upward* — fails on its face, because
it describes the operation and not the node. The reason that clears the bar has
to say why **this node** may go, and the only true answer is that what it held
now stands somewhere else. Saying that names the somewhere else.

The exercise ran both. The first attempt, `--why "Merged upward; reason as
above."`, was refused at exit **2** by `require_reason` with nothing written,
nothing committed and nothing minted (`:187`); the store's own message is *"if
the reason is another node's, name that node's id and say what differs here"*.
The accepted one (`:204`) says the clause this node holds now stands word for
word inside `oskz`. **The lineage pointer was not an extra clause bolted on for
lineage's sake — it was the evidence the reason needed in order to be about
this node at all.** A rule that asks for it is asking for something the reason
bar already asks for, in the one place a writer is already thinking about it.

An `ancestor` attribute would sit beside that sentence recording less of the
same fact, and would be believed in preference to it, because it is structured
and the sentence is not. The field can say that `dwqu` went into `oskz`. It
cannot say why that made `dwqu` removable, and why is the whole of what a
reader of a canvas is there for.

### What the rejected option would have cost

An ancestor id is the obvious answer, so the leaner rule has to be worth more
than it. Four costs, each of them one this document has already priced
somewhere else.

**It is `supersede` in an attribute.** Section 2 rejected exactly this, in as
many words: if `replace` can sever a lineage, something has to be able to say
"new node `b9` continues `b7`" — and that thing is the verb the spec
deliberately does not have, wearing a different hat, with its own attribute to
maintain and its own way of being wrong. Merge and split are the case section 2
anticipated. Answering them with a field is answering them with `supersede`.

**It would be the first piece of node state not derivable from the log.**
Section 4 chose the `v` invariant over the more intuitive one on exactly this
axis: `v` is what `git log --grep` counts, so a canvas whose file and log
disagree is corrupt and can be found to be corrupt by a script nobody has to
think hard about. An `ancestor` attribute is verifiable against nothing — a
claim about history stored outside history. The transcript's appendix shows
what history carries: the commit that retired `dwqu` has the trailers
`Canvas-Node: dwqu`, `Canvas-Author:` and `Canvas-Base:` and nothing else
(`:421`). Making the attribute checkable means putting the other id in a
trailer too, and a commit that names two ids is the multi-node write section 5
refuses.

**It is single-valued against an operation that is not.** Two nodes merge
today and the survivor merges again next month; three nodes merge at once; a
split's halves are later rejoined. One attribute becomes a list, and a list
attribute is a subtree wearing an attribute's clothes — addressed by no id,
edited by no verb, and outside every rule in this document.

**And it can be false at exactly the moment a run dies.** A merge is two
commits. If the survivor's `replace` stamps `ancestor="dwqu"` and the `remove`
then does not land, the document asserts that `oskz` descends from a node that
is still in it, alive, at `v="1"`: a wrong lineage that looks right, which
*What an id is* names as the failure mode to design against. That interleaving
is not hypothetical — it is what the exercise did. The `replace` on `oskz`
landed at `:174` and the first `remove` on `dwqu` was refused at `:187`, and
the canvas sat in exactly that half-merged state until the second attempt
succeeded at `:204`. Under this rule, what the canvas said in that window was
merely true: `oskz`'s reason says `dwqu` *"holds that clause today and will
hold nothing this node does not once this commit lands"* — a sentence about an
intent, which a reader can check against the document in front of them, and
which stays honest whether or not the second commit ever arrives.

### What this costs, stated honestly

**Nothing enforces it.** A writer who omits the other id writes a valid edit,
the store accepts it, and no command reports the gap. That is the same honesty
the README's *A reason that asserts a fact about the world names its evidence*
already carries, and the same limit: the check would have to leave the canvas
to run. When the pointer is missing the stranded id is not damaged, it is
unfindable — its history is intact and complete and nobody has the string to
ask for it with.

That price is payable only because the bar already pushes hard in the same
direction. `require_reason` refuses the bare back-reference outright, and
section 5 refuses an operation-shaped reason on a `remove`. A merge reason that
omits the surviving id has to get past both while still saying something true
about this node, and the exercise suggests that is hard to do by accident.

**One thing the exercise does not establish, and this rule does not claim.**
That merge worked by copying the losing node's clause into the survivor first,
so the survivor's own text was the evidence and naming it was unavoidable. A
merge that rewrites both halves into something neither of them said has a
harder reason to write, and the id is likelier to be left out of it. Nothing
here makes that case easier. It makes the requirement explicit, so that the
writer of that reason knows the other id is part of the reason and not an
extra, and so that the decision was not made by whoever happened to write
`replace` first.

## 8. A restructure is never atomic, and a grouping mechanism may never be a write

**No.** A restructure is a sequence of independent commits, each naming one
node and each carrying its own reason, and nothing will be added that lets N of
them land or fail together. This overrules nothing above; it is section 5's
refusal followed to the place the closing section said it had not yet been
followed to.

The second half of the question is the one worth spending words on, because it
has a different answer. **Could a grouping mechanism exist that is not the
batch-write verb section 5 refuses? Yes — exactly one kind, and its boundary is
one sentence: a grouping mechanism may name a set of commits that already
exist; it may never be the unit in which a write happens.**

### Why atomic is refused, taking the two shapes it could have

Atomicity over N edits has two implementations and this tool cannot have either.

**A staging area — hold N writes and apply them together — is the batch-write
verb with a queue in front of it.** The applying write touches N nodes, and
`canvas/store.py` compares the document it is about to write against the one on
disk and refuses unless exactly the node named in the commit's `Canvas-Node:`
trailer is the one that differs. That guard is in the write path, not the
command line: it holds for every caller and every import path, so the queue
would have to be given a way through it that nothing else has. And the question
section 5 asks of any such write has no good answer here either — what does
`history` print for the N−1 nodes? The join is trailer equality, so a commit
naming N ids either appears in N histories carrying one verb and one reason,
and that reason is about the operation rather than about any node in it, or it
names one and lets N−1 nodes change in a commit their own history never sees.
The exercise shows the join doing exactly the thing that makes this impossible
to fudge: the `move` of section `sdtf` (`canvas-transcript.md:217`) changed
where its child `ps58` sits, and `history … ps58` (`:326`) prints one entry,
its own `insert`. One commit, one node named, one history it turns up in.

**A rollback — let a failed restructure undo the commits it already made — is
worse than it looks.** Ids are retired and never reminted, and the uniqueness
check is a grep over the log. Remove the commits and the retired ids stop being
retired: a later `insert` may draw one again, and `history` on it would then
answer for two different nodes with one undivided list. That is a wrong history
that looks right, which is the en-quire failure this document was written
against, arriving by a door nobody was watching. **Nothing in this tool may
remove a commit from the log.**

### What the worry is actually worth

The open item's own words were that a run which dies halfway leaves the canvas
*coherent but half-reorganised*. Coherent is not luck there; it is bought, in
three places. Every intermediate state is a legal document, because
`schema/canvas.rng` makes every container `zeroOrMore` and never `oneOrMore`
precisely so the empty container each sequence passes through is legal. Every
refusal writes nothing at all — the exercise's store holds 15 commits for 25
invocations and not one of them is the refused `remove` (`:407`). And every
node's history is true about how far the restructure got, because every commit
in it names one node and describes that node's own change.

So atomicity would buy one thing: not being *seen* mid-restructure. It would
buy it with the single write this tool exists to be unable to perform.

**This is not a claim that a half-finished restructure is pleasant.** The
exercise produced one and it is not. Between `:174` and `:204` the canvas
asserted the same clause twice under two ids, and a reader meeting it in that
window reads a duplicated claim and has to work out which id to believe. That
is a real cost and it is the cost being accepted here. It is not, however, the
cost atomicity is usually sold against: the document was valid, both nodes were
live, both histories said exactly what had happened, and one more command
finished the job. A half-finished restructure is legible and repairable by
hand. What a batch write produces when it half-fails is N nodes changed by a
commit none of them records, which is neither.

### What may exist, and where the line is

A marker over commits that already exist. N commits, each still exactly one
node with its own `--why`, sharing something that lets a reader ask what one
restructure did as a whole: a further trailer beside `Canvas-Node:`, a run id,
or nothing more than the convention that the reasons name the same thing. Such
a marker writes no document state, changes no verb, adds no flag that could
carry a second node, and passes the identity guard untouched, because each
commit still differs in exactly one node. It cannot destroy anything, because
it is a name for a set and not a way of writing. It is a read-side index over
the log, and the log is already where a node's life is kept.

**The boundary, once more, because it is the whole of the ruling:** a grouping
mechanism may aggregate commits after the fact; it may never be the unit in
which a write happens. Anything on the read side of that line is a reporting
feature and may be argued for on its merits, against what it costs to maintain.
Anything on the write side is the batch-write verb whatever it is called, and
section 5's refusal stands against it unmodified.

Nothing here is being built. This section rules that something may be, within
that boundary, and that the atomic version may not be — so that neither is
decided by whoever first wants a restructure to go faster.

## Still open

This rule is scoped to step 1 and it did not settle everything the *Open*
section raised. Two of the three items below have since been ruled on and are
kept here, marked, so that a reader who was told they were open is told by the
same place that they are not. What is genuinely left is the third:

- **Merge and split have no representation, and this is the restructure
  remainder. — Settled 2026-09-23 in section 7.** The rules above mean a
  restructure made of moves, renames and one-node replaces costs no history at
  all. A restructure that *merges* two
  nodes into one, or *splits* one node into two, is not expressible without
  losing some: a split is a `replace` plus an `insert`, so one half keeps the
  original id and its reasons and the other half is born with an empty history;
  a merge is a `replace` plus a `remove`, so one node's reasons survive and the
  other's dead-end at a retired id that the surviving node does not point at.
  Nothing above makes that wrong — the verbs behave exactly as specified — but
  nothing above makes it *recoverable* either, and merge and split are what
  people actually do when they restructure prose. **This is the part of the
  hardest open item that remained open**, and the problem is left stated above
  because the ruling is a choice between the two options it names: either a way
  for a node to record an ancestor id, or a deliberate decision that lineage
  ends at a merge and that the `--why` on the merging edit has to carry the
  pointer by convention. **Section 7 takes the second one**, against the merge
  and split performed for real in `docs/merge-and-split/` — where
  `bin/canvas history` on the stranded id exits 0 and prints that node's whole
  life, so what a merge costs is the path from the document to the id and not
  the history behind it. The ancestor id is rejected there, with what it would
  have cost. Nothing is left open in this bullet.
- **Whether a restructure should ever be atomic. — Settled 2026-09-23 in
  section 8, and the answer is no.** It stays a sequence of independent commits,
  each naming one node and each carrying its own reason, and the half-reorganised
  state a dying run leaves is accepted: every intermediate state is a legal
  document, every refusal writes nothing, and every node's history is true about
  how far the restructure got. The second half of the question — whether any
  grouping mechanism can exist without becoming the batch-write verb this
  document spent a section refusing — is answered there too, and it is yes, with
  a boundary: such a mechanism may aggregate commits that already exist, and may
  never be the unit in which a write happens. Nothing is left open in this
  bullet either.
- **Nothing here ages.** A canvas is frozen at `done` and never deleted, so the
  set of retired ids grows without bound and the uniqueness check greps a log
  that only gets longer. At canvas scale this is not a problem for a long time.
  It is written down so that whoever eventually measures it knows it was a known
  consequence and not an oversight.
