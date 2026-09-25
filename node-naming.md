# Node naming

Settled 2026-09-23. This document decides whether what `create` mints is
distinguishable inside the document itself — whether a node gains a
human-readable name, and whether `create`'s two first nodes get one. It is
scoped to the finding at `docs/drive-by-hand/FRICTION.md:174-179` and to the
vocabulary in `schema/canvas.rng`. It decides nothing about the renderer beyond
saying that the renderer is free, and it decides nothing about authorship in the
document, which `node-state.md` *Still open* holds separately.

The reason it is settled now and not later: the read path is being fixed in the
same change, and the fix removes the round trip the finding is half about
(`create` printing the ids it mints). A question answered implicitly, by a read
surface that happens to make the document's silence bearable, is a question
nobody can argue with afterwards. The finding's other half — *"Nothing in the
document says one is the problem and the other the expected value"* — is a claim
about the **document** and has to be answered as one, or refused as one.

It holds the spec's existing commitments fixed rather than relitigating them:

- **The vocabulary is closed.** Eleven element names and no twelfth
  (`schema/canvas.rng:13-16`, pinned by `tests/test_validate.py:130-143`), and
  seven attribute names and no eighth (pinned by
  `tests/test_validate.py:145-158`).
- **The vocabulary is structural and not semantic**
  (`engineering-spec.md:99-106`). `<question>` is the one declared exception
  (`engineering-spec.md:108-112`).
- **The semantics live in the reason**, not in a verb name and not in a field
  (`engineering-spec.md:131-137`, `product-spec.md:48`).
- **One edit is one node, one edit is one commit**, and a node's history is
  `git log --grep='Canvas-Node: <id>'` (`engineering-spec.md:139-141` and `:192`,
  `node-identity.md`).
  (**Added 2026-09-25, after this ruling — the bullet above is as written
  on 2026-09-23.** That query is not the command.
  `engineering-spec.md:218-223` calls the bare `--grep` form "the same
  query written as a substring match" and "wrong in two reachable ways":
  ids are four characters, so it also answers for a longer id that starts
  with the one asked about, and a reason that quotes the trailer text is
  counted as an edit to a node it never touched. The same paragraph, at
  `engineering-spec.md:222-223`, says instead that "The command matches the
  trailer's value for equality instead" — which is what
  `canvas/store.py:1026` does, keeping an anchored `--grep` as a pre-filter
  that never decides. What this bullet holds fixed is untouched: a node has
  a history of its own, and it is exactly the set of commits whose
  `Canvas-Node:` trailer names it. Nothing this ruling decides turns on how that
  set is queried, so the ruling stands as written.)
- **The creation commit creates the root only**, and the two first nodes arrive
  as two ordinary `insert` commits (`node-identity.md` §4, quoted verbatim in
  `canvas/store.py`'s `create`).
- **The decision rule `node-state.md` §3 arrived at**, which is the test this
  turns on and is restated in §1 below.

## The ruling

**No. A node does not gain a human-readable name, `title` stays on `<section>`
and on no other element, and `create`'s two nodes stay untitled `<text>` nodes.
The distinction between them stays in the reason — the commit subject — and what
is fixed instead is the read surface: `create` now prints the two ids it mints,
under one name each.**

Concretely: `schema/canvas.rng` is not touched. No element gains an attribute, no
attribute gains a value, `title` does not move into
`<define name="node-attributes"/>`, and `create` does not mint a `<section>`.
What changes is `bin/canvas create`'s stdout, which is not the document.

## 1. It fails the decision rule, which is the test this turns on

`node-state.md` §3, carried into the orchestrator's
`guidelines/domain-decisions.md` as the rule to apply to the case nobody
anticipated:

> A fact a reader of the rendered canvas must act on belongs in the document. A
> fact a reader reconstructs when they ask *why* belongs in the reason.

Which of two nodes is the problem is not a fact anything acts on. The four verbs
treat the two identically; no rule anywhere in the tool treats the problem node
differently from any other node; nothing is forbidden on one and permitted on the
other; and no refusal, no validation and no projection branches on it.

Compare the fact that *passed* this test. *An agent must not quietly answer an
open question* is something a reader must act on before it has any occasion to
run `history`, and `engineering-spec.md:108-110` says so in as many words: the
renderer has to make it loud, and an agent has to be told not to answer it.
Nothing equivalent is true of "this paragraph is the problem statement". A reader
who does not know which is which reads two sentences instead of two labelled
sentences, and acts identically on both.

## 2. The two nodes say what they are in their own prose

A problem statement and an expected value read as what they are. They come from
the ledger row's `open`, which already stated them as two different things, in
two different fields, in words chosen to be different.

This is where the case parts company with `answered`. An open `<question>` and an
answered one are **identical in their text** — that is precisely why the fact had
to go into the document: there was no other channel, and the writer who tried to
use prose for it produced `FRICTION.md:158-159`'s stale sentence. `create`'s two
nodes are not identical in their text and never will be, because the two things
they hold are different things.

## 3. It is the tripwire in another spelling

`engineering-spec.md:99-106` is the defence of the closed vocabulary: it is
*structural* and not *semantic*, `table`, `text`, `list` describe shape, and
*"the moment somebody proposes `<decision>`, `<risk>` or
`<acceptance-criterion>`, the taxonomy has started growing and it will not
stop."*

A human-readable name on an ordinary `<text>` node is that growth wearing an
attribute's clothes. Its values are a taxonomy of roles — "Problem", "Expected
value", and then whatever the twelfth case turns out to be — and it reaches every
node rather than one. `node-state.md:304-307` gives the mechanical form of the
test: *could this field ever have a twelfth value that fits none of the ones
somebody thought of?* For a name on a node: yes, obviously, and the first
canvas anybody drives will produce one. For `answered`: no, the value set has one
member. This fails exactly where `answered` passed.

## 4. The reason already carries it, and the spec says that is where it goes first

`engineering-spec.md:291-295`, the sentence `node-state.md` §5 could not argue
past either:

> A state field distinguishing what was asserted from what was verified was
> considered and rejected as premature; if canvas-versus-reality drift turns out
> to bite, this is where it will be fixed, and it should be fixed with evidence
> in the reason before it is fixed with a new attribute.

The birth reason is written once and never rewritten — `insert sqsx: the problem
the ledger row states` — and `bin/canvas history <ledger-id> <node-id>` prints it
as the **first** block, oldest first, for the life of the node, across every
later `move` and `replace`. It is the one fact about a node that cannot go stale,
because nothing can edit it.

## 5. What naming them was supposed to buy is delivered on the read surface

`FRICTION.md:84-91` states the cost the finding actually measured: *"It minted
two nodes and named neither… **One round trip, imposed on every caller, on their
first command.**"* That round trip is what hurt, and it is gone: `create` prints

    Canvas-Problem: sqsx
    Canvas-Expected-Value: hcac

above the two lines it already printed. The ids are labelled by the flags they
answer, one for one, so the caller never counts and never reads. The rest of the
finding — which node holds what, who wrote it, what changed — is reached by
`read --id`, `read --type`, `read --provenance` and `history`, all of which are
the read surface and none of which is the grammar.

This is the ruling's load-bearing dependency and it is stated rather than
assumed: **the argument for leaving the distinction out of the document depends
on the read surface that this change builds.** Before it, the answer would have
been weaker.

## 6. Every "name them" option also disturbs the birth shape

The option that needs *no* grammar change is `create` minting
`<section title="Problem">` wrapping a `<text>`, since `<section>` already
carries `title` (`schema/canvas.rng:75-78`). It is refused on its own ground: it
doubles the nodes to four and the commits to five, against `node-identity.md` §4
as quoted in `canvas/store.py`'s `create` — *"The two nodes the ledger's `open`
contributes… arrive as two ordinary `insert` commits, each naming its own node,
each born at `v="1"`."* The birth shape is a decision, not an incidental, and an
option that has to change it to reach a cosmetic end is paying in the wrong
currency.

The other options are grammar changes: `title` on `<text>`, or `title` moved into
`<define name="node-attributes"/>`. The second reaches all ten non-root elements
at once, which is exactly the move `node-state.md` §2 refused for `answered`.

## A hazard this ruling found, which belongs in the record

**The attribute-set invariant would not have caught this change.**
`tests/test_validate.py:145-158` asserts set equality over attribute *names*, and
`title` is already in that set. Adding `<attribute name="title"/>` to
`<define name="text">` — or moving `title` into `<define name="node-attributes"/>`
— adds no new name and **breaks no test**. The tripwire that exists to send
somebody back to a ruling before a vocabulary change lands does not fire for this
one.

That is the sharpest reason this had to be settled by a written ruling rather
than left to a test to defend. Tightening the invariant to element×attribute
pairs would close it. It is not done here and this ruling does not require it:
the invariant is not wrong, it is narrower than somebody reading it would assume,
and the fix is a test change that belongs to whoever next widens the grammar.

## What this costs, stated honestly

- **Order is not stable.** `move` and `insert --after` can reorder the two or put
  anything between them (`node-identity.md` §3). After that, "the first two
  nodes" is no longer a pointer to which is which. The commit subject still is,
  and so is `create`'s own output, which the caller had in hand before anything
  moved.
- **The rendered HTML page shows two unlabelled paragraphs.** That page is the
  artifact pasted into a Basecamp comment (`engineering-spec.md:333-341`), read
  by somebody who will never run `history`. **This is the strongest argument
  against this ruling** and it is named here rather than buried. The answer: a
  projection is not the document, and may say what the document does not —
  `canvas/render.py` already prints markers in words that exist nowhere in the
  XML (*Open question*, *Answered question*, `README.md:624-626`). Whether the
  renderer labels `create`'s two nodes is [`rendering.md`](rendering.md)'s
  business, and presentation was explicitly left free. **This ruling permits that
  and does not decide it.**
  (**Added 2026-09-25, after this ruling — the cost above is as written on
  2026-09-23.** The page is not what goes into a Basecamp comment.
  `engineering-spec.md:322-332` now says of the HTML page "Not pasteable into a
  Basecamp comment", and marks that as a correction of the line that had said it
  was: the `basecamp` CLI converts a comment body from Markdown to HTML only
  when the body contains no HTML, so one tag turns the conversion off for the
  whole comment, and Basecamp's rich text then drops the doctype, the wrapper
  elements and every class the page's meaning is carried in. The projection that
  does go there is the second one — `bin/canvas render <ledger-id> --format
  comment` — which is where the citation above already points
  (`engineering-spec.md:333-341`). The cost survives the correction unchanged:
  `_comment_node` renders an untitled `<text>` node as its text and nothing else
  (`canvas/render.py:582`), so the comment shows the same two unlabelled
  paragraphs to the same reader who will never run `history`, and what was wrong
  was only which artifact the sentence named. So does the answer — both
  renderers live in `canvas/render.py` and walk what one `store.read` returned
  (`engineering-spec.md:344-345`), so a marker in words the XML does not carry
  is as available to one as to the other.)
- **Somebody will propose this again**, and should be able to tell quickly
  whether they have a new argument. What would reopen it is in *Deliberate*
  below, stated as a test rather than as a mood.
- **A `read --type text` cannot tell the two apart either.** The selector selects
  by shape, because shape is what the vocabulary carries; asking it for "the
  problem" is asking the grammar a question this ruling says it does not answer.
  `read --id <the id create printed>` is that question's real form.

## What this makes deliberate, and what stays free to change

### Deliberate — a later change may not rewrite these without reopening this document

- **A node does not carry a human-readable name.** `title` is legal on
  `<section>` and on no other element, and does not move into
  `<define name="node-attributes"/>`. *Why:* a name's values are a taxonomy of
  roles, which is `engineering-spec.md:99-106`'s tripwire (§3), and the fact is
  not one a reader of the rendered canvas acts on (§1).
- **`create`'s two first nodes are untitled `<text>` nodes, problem first, in
  two ordinary `insert` commits.** *Why:* §6, and `node-identity.md` §4.
- **Which of the two is which is carried by the commit subject and by `create`'s
  own output, and not by the document.** *Why:* §2 and §4 — the reason is
  immutable and already says it, and the prose already distinguishes them.
- **What would reopen this, stated as a test:** a canvas in which a node's role
  must be acted on by a reader of the rendered document *before* that reader has
  any occasion to ask why. That is the test `answered` passed and this fails. An
  argument that does not meet it is not a new argument.
- **If it is ever reopened, it is reopened as a vocabulary task and not in
  passing.** Reopening this reopens `node-state.md` §2's refusal of a grammar
  change that reaches every node, and it must begin by noting that
  `tests/test_validate.py:145-158` does not catch adding `title` to a second
  element.

### Free to change — implementation choices, not decisions

- **The names `Canvas-Problem:` and `Canvas-Expected-Value:`.** They name the two
  flags `create` already takes, one for one, which is why they are those words;
  any pair of names that says which id answers which argument is equivalent.
  Their order relative to `Canvas-Base:` and `Canvas-File:` is free too — what is
  not free is printing the two ids at all.
- **Whether the renderer labels `create`'s two nodes**, and how. Presentation was
  left free and this ruling does not take it back.
- **The read surface's shape** — `--id`, `--type`, `--provenance`, the
  `Canvas-Wrote:` line and its field order. The ruling depends on *a* read
  surface that reaches the same facts, not on this one's spelling.
- **Tightening the attribute-set invariant to element×attribute pairs.** Worth
  doing and not required by this ruling; see *A hazard this ruling found*.

### Known tensions — unresolved, recorded

- **`FRICTION.md` and `VERDICT.md` read the same event in opposite directions, in
  their own texts, and this ruling inherits one of the readings rather than
  re-deriving it.** `FRICTION.md:109-110` reads a question node becoming its own
  answer as the document's failure; `docs/why-verdict/VERDICT.md:425-434` reads
  the same event as the design working. `node-state.md` §3 reconciles them by
  distinguishing the document from the log, and this ruling leans on exactly that
  reconciliation, in a case §3 did not anticipate — and it leans on it to prefer
  `VERDICT.md`'s reading in a case `FRICTION.md:174-179` raises in its own voice
  as a defect **of the document**. The same file that supplies the evidence for
  the finding supplies the reading that would decide it the other way. Neither
  file cites the other and neither has been amended. **The reading is inherited
  and not re-derived**, and a reader who finds only one of the two files will get
  one of the two readings whole.
- **The invariant that should have guarded this does not.** Recorded above under
  *A hazard this ruling found*, and left open there.
- **`<question>`'s own retirement clause.** `engineering-spec.md:111-112` says
  `<question>` folds back into `<text open="true">` if it earns nothing.
  `node-state.md` already noted that its ruling closes that exit; this one adds
  nothing to the tension and does not resolve it either.

## Still open

- **Whether authorship belongs in the document.** `FRICTION.md:166-172` names it
  as the other instance of *"what a canvas needs to say about a node has to be
  smuggled into the node"*, and `node-state.md` *Still open* holds it. This
  change answers it **on the read surface** — `read --provenance` says who last
  wrote each node and at which commit, from the log, with nothing added to the
  grammar — and that is deliberately not an answer to the document question. If
  authorship belongs *in the document* it needs its own argument, and *"we
  already did it for `answered`"* is not one, and neither is *"we already did it
  for provenance"*.
- **Whether the renderer should label `create`'s two nodes.**
  [`rendering.md`](rendering.md)'s question. This ruling permits it.
- **Whether the attribute-set invariant should be element×attribute pairs.** A
  test change, owned by nobody yet.
