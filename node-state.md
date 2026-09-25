# Node state

Settled 2026-09-23. This document decides whether a canvas may say anything
about a node's state, and how much. It is scoped to the four wants the friction
record collected at `docs/drive-by-hand/FRICTION.md:145-159` and to the
vocabulary in `schema/canvas.rng`; it decides nothing about the renderer beyond
the one fact the renderer will need from the document, and it decides nothing
about the canvas lifecycle. What is still open is named at the end.

The reason it is settled now and not later: the renderer's contract depends on
the answer. A renderer has to know whether "this question is open" is a fact it
reads off the document or a fact it cannot see, and it has to know that before
anybody writes the first line of it. `engineering-spec.md:108-110` already
justifies `<question>` existing on exactly that ground — *"the renderer has to
make it loud"* — so the renderer's contract and this vocabulary question are the
same question asked twice, and the vocabulary is the half that has to be settled
first. A rule arrived at implicitly, by a renderer that happens to render one
thing loudly, is a rule nobody can argue with afterwards.

It holds the spec's existing commitments fixed rather than relitigating them:

- **The vocabulary is closed.** Eleven element names and no twelfth
  (`schema/canvas.rng:13-16`, pinned by
  `tests/test_validate.py:130-143`).
- **Four verbs and no more** (`engineering-spec.md:116-123`). There is no
  `resolve`, no `collapse`, no `supersede` (`engineering-spec.md:125`).
- **The semantics live in the reason**, not in a verb name
  (`engineering-spec.md:128-130`, `product-spec.md:48`).
- **One edit is one node, one edit is one commit**, and a node's history is
  `git log --grep='Canvas-Node: <id>'` (`engineering-spec.md:133-135`,
  `node-identity.md`).
- **`v` is what the log counts** — a node's state must not become a claim the
  log cannot check (`node-identity.md` §4, and §7's rejection of an ancestor
  id at `node-identity.md:555-598`).

Every rule below was checked against those five, and where a candidate rule
contradicted one, the candidate was the thing that gave way. That is why this
ruling is narrower than the option it takes was originally phrased: see §4.

## The ruling

**Option B, and only for openness: `<question>` gains one optional attribute
recording that it has been answered, so that an answered question can stand in
the document instead of being destroyed by the `replace` that answers it — and
no other node gains any state, and the question does not gain a pointer to the
node that answered it.**

Concretely: a `<question>` may carry `answered="true"` and nothing else. The
attribute's absence means open. `answered` is legal on `<question>` and on no
other element, `true` is its only legal value, and `answered-by` — the pointer
half of the option as the todo phrased it — is refused, with the reason carrying
the pointer exactly as `node-identity.md` §7 already rules for merge lineage.

Option A is not taken and option C is not taken. §5 says why C could not be
argued past the sentence that rejects it, and §1 and §3 say why A does not reach
wants 1 and 3.

## 1. The four wants: which two this answers, and which two stay in the reason

The finding, `FRICTION.md:145-146`:

> **The single largest gap: a node has no status.** Four separate wants in this
> canvas all reduce to it, and every one ended as a word typed into somebody's
> prose:

They do not all reduce to it in the same way, and that is the whole of this
ruling. Two of the four are about a question being open, which is the one fact
`engineering-spec.md:108-112` already says the document must carry and shape
cannot derive. Two are not.

### Want 1 — *"this question is answered"* — **ANSWERED**

`FRICTION.md:148-149`:

> - *"this question is answered"* — became `replace` destroying the question
>   (`f7be9ea`, `fad921f`).

This is the want the ruling exists for, because it is the only one of the four
where the document loses the node altogether. `FRICTION.md:109-110` states the
outcome: *"The finished document contains zero `question` elements — the canvas
ends with no visible trace that anything was ever asked."* The writer said so
inside the document, in `f7be9ea`'s own reason: *"The question node becomes the
answer because the tool has no way to mark a question answered while leaving it
standing."*

Under this ruling the answering edit is still one `replace` on the question
node, still one commit, still one reason. What changes is what it produces: a
`<question>` that stays a `<question>`, carries `answered="true"`, and holds the
answer as its text. The question is still in the document, still findable, and
an agent reading the canvas can see both that something was asked and that it is
no longer open.

### Want 3 — *"the code has taken option B, and the question is still open"* — **ANSWERED**, as a consequence rather than by a second mechanism

`FRICTION.md:152-158`:

> - *"the code has taken option B, and the question is still open"* — the mirror
>   image, hit by the first writer at commit `35e25a1`, node `nf98`. The node
>   ends with the sentence *"This node records what the code does; it does not
>   close the question above it"* — a sentence about the document, inside the
>   document, because there is no shape for a provisional state. It then went
>   stale: commit `3aebd79` had to replace `nf98` because that sentence became
>   false once the question *was* settled, and its reason says why that matters
>   — *"A canvas whose nodes disagree about whether a question is open is worse
>   than one that never said."*

This want reads as a request for a *provisional* state on the `<text>` node, and
it is not one. Read what `nf98`'s sentence actually asserts: it is a claim about
**the question above it**, not about itself. The writer had to put it in `nf98`
because the question node could not be relied on to still be there, and because
nothing about a standing `<question>` said whether it was still open.

Give the question node the fact and the sentence stops needing to be written. A
`<question>` without `answered` is open; a `<text>` beside it recording what the
code does asserts nothing about it either way; and the reader derives *"the code
has taken option B and the question is still open"* from two nodes each of which
is only about itself. The sentence that went stale is a sentence this ruling
makes redundant, and a sentence nobody writes cannot go false.

`FRICTION.md:162-163` is the argument for putting the fact in one place rather than
two: *"A canvas whose nodes disagree about whether a question is open is worse
than one that never said."* Two nodes can only disagree about whether a question
is open if two nodes are both allowed to say so. Under this ruling exactly one
node says it — the question itself — so the disagreement is not merely unlikely,
it is inexpressible. That is a stronger answer than a provisional marker on
`<text>` would have been, and it costs one attribute rather than two.

What this does **not** give want 3 is a way to mark the `<text>` itself as
provisional in some sense unrelated to an open question — *"this is my best
guess"*, *"this is unverified"*. That is asserted-versus-verified, it is
canvas-versus-reality, and it is the thing `engineering-spec.md:272-276`
rejected. It stays in the reason. See §5.

### Want 2 — *"this option is the one taken"* — **DELIBERATELY LEFT IN THE REASON**

`FRICTION.md:150-151`:

> - *"this option is the one taken"* — became the literal word `CHOSEN.` inside
>   a cell (`90907b5`, `6be144a`).

Left in the reason, for two reasons that are different in kind.

**The spec already prescribes a different move, and it is the right one.**
`engineering-spec.md:131-134`: *"An options table becoming a settled decision is
`replace` on the table node, with the new node being a `<text>`, and `--why
"chose A over B: B needs a migration we are not paying for this cycle"`."* The
canvas is *"Not a wiki. A wiki accumulates. A canvas resolves"*
(`product-spec.md:52`). An options table with a winner marked in it is a canvas
that did not resolve: it keeps four rows of superseded comparison in the
document that every prompt carries, and marks one. A `state="chosen"` on a
`<cell>` would make the un-resolved shape the comfortable one, which is the
opposite of what the product is for.

**And the friction that was actually recorded is not the friction a marker
fixes.** `FRICTION.md:121-122` says what hurt: both commits *"are full retypes of
cells several hundred characters long, because `replace` takes the new text and
not a patch of it."* The cost was retyping, not the absence of a word for
chosen-ness — the writer had the word, and typed it. A `--chosen` flag would
have removed one word from a several-hundred-character retype and left the
retype. Whether `replace` should be able to change an attribute without
restating the text is a real question and it is named in *Still open*; it is not
this one, and answering this one would not have answered it.

So want 2 is left where `engineering-spec.md:128-130` puts it: the reason says
which option was chosen and why, and the table it was chosen from goes.

### Want 4 — *"this document is finished"* — **DELIBERATELY LEFT**, and handed to its own todo

`FRICTION.md:159`:

> - *"this document is finished"* — became node `gjxb` (`02de26b`).

This is not a node state at all, and it is the one of the four that is
misfiled by being on the list. It is a property of the canvas, and the canvas
root is the one element that carries no `id` and no `v` and sits outside the
identity rules entirely (`schema/canvas.rng:25-26`, `node-identity.md` §4). It
is also already specified: `engineering-spec.md:327-338` gives the lifecycle —
born at `open`, grows through `executing`, **frozen at `done`**, never deleted —
so what want 4 records is not a missing vocabulary item but a missing
*mechanism*, the freeze the spec promises and `bin/canvas` does not implement.
`FRICTION.md:127-129` says exactly that: `--help` lists seven subcommands and
*"None is a freeze, a close or a `done`."*

Giving every node a state would not have reached it either: `node-attributes` is
referenced by the ten non-root elements and not by `<canvas>`, so even option C
would have had to decide the root separately.

It is therefore handed, deliberately and by name, to
[Give a canvas an end (#10330567174)](https://app.basecamp.com/3934852/buckets/48039419/todos/10330567174),
which is already open in the same list. Until that lands, *"this document is
finished"* stays where `02de26b` put it: in a node's prose and in its reason.
This ruling does not pre-empt that todo's answer, and it does not constrain it
beyond one thing — whatever ends a canvas is a property of the root or of the
ledger, not an eleventh element and not a value of `answered`.

### The fifth finding this does not touch

`FRICTION.md:166-172` records authorship as *"The same shape as the missing
status: what a canvas needs to say *about* a node has to be smuggled into the
node."* It is not one of the four wants and the todo does not ask about it. This
ruling refuses the general form of that shape — a canvas may **not** carry
arbitrary metadata about a node — and answers exactly one instance of it, so it
leaves authorship precisely where it is: on the commit, via `--author`, not in
the document. If that is wrong it is wrong for its own reasons and needs its own
ruling.

## 2. The tripwire, and why one attribute on one element does not trip it

`product-spec.md:123`, the row in *Risks and open decisions*, in full:

> | The closed node vocabulary grows | A fixed list of node types is a topology, and topologies fall through — the same failure we already have in how step failures are categorised | Tripwire: the day somebody proposes a "decision" or "risk" node type, the taxonomy has started growing |

and the clause itself:

> Tripwire: the day somebody proposes a "decision" or "risk" node type, the
> taxonomy has started growing

**This ruling reads the tripwire in spirit and not only literally, and it
survives the broader reading.** The literal reading is easy and would be
cheating: the tripwire names a *node type*, `engineering-spec.md:99-106` names
`<decision>`, `<risk>` and `<acceptance-criterion>` — element names — and this
ruling adds no element, so on the letter it is not tripped and neither would
option C have been. That is not good enough. The failure the tripwire is
actually about is stated at `engineering-spec.md:99-104`: *"A closed list of node
types is itself a topology, and topologies fall through the moment a case
appears that nobody anticipated — the same failure this repo already has in its
handling of step failures, where each new kind of failure needed a new category
and the categorisation kept missing."* An enumerated attribute value set is a
closed list of names that has to anticipate the cases. It is a topology in a
different syntactic position, and it falls through the same way. Read in spirit,
`state="decision" | "risk" | "chosen" | "provisional"` **is** the tripwire, and
option C trips it whatever the RELAX NG spelling.

What survives the broader reading is a value set with **one member**. `answered`
is not a classification of a node; it is the negation of the one property
`engineering-spec.md:108-110` already says the document must carry. There is no
second value to reach for, so there is no case the categorisation can miss —
the shape it adds is not *"which of these is this node"* but *"is this question
still open"*, and that question has an answer for every question node that will
ever exist.

The defence at `engineering-spec.md:103-105` is that the vocabulary is
*structural* and not *semantic*: *"`table`, `text`, `list` describe shape, and
shape does not run out."* This ruling does not weaken that. `<question>` was
already the declared exception — `engineering-spec.md:108-109`, *"`<question>` is
the one semantic node, and it is the one exception worth arguing for"* — and
putting openness on it puts the semantics where the spec already put them, in
the one place it already argued for, instead of spreading them over ten
structural elements that have been semantics-free by design.

**The tripwire is therefore moved, not disarmed.** Under this ruling the day
somebody proposes a second legal value for `answered`, or `answered` on a second
element, is the day the taxonomy has started growing — and §6 makes the suite
say so out loud rather than leaving it to somebody's memory.

## 3. "The semantics live in the reason" — which reading this takes, and how FRICTION and VERDICT are reconciled

`engineering-spec.md:125-131`:

> **There is no `resolve`, no `collapse`, no `supersede`.** An options table
> becoming a settled decision is `replace` on the table node, with the new node
> being a `<text>`, and `--why "chose A over B: B needs a migration we are not
> paying for this cycle"`. The semantics live in the reason, where they can be
> anything, and not in a verb name, where they can only be what somebody thought
> of in advance. A verb per kind of intent is how you get eleven verbs and a
> twelfth case that fits none of them.

The clause, at `engineering-spec.md:128-130`:

> The semantics live in the reason, where they can be anything, and not in a
> verb name, where they can only be what somebody thought of in advance.

restated at `product-spec.md:48`:

> The meaning lives in the reason, where it can be anything, rather than in a
> verb name, where it can only be what somebody thought of in advance.

**This ruling holds the rule in full, and reads it as a rule about the space of
intents, not a rule about the location of facts.** Both sentences name the same
contrast — *anything* against *what somebody thought of in advance* — and both
name the same failure: *"A verb per kind of intent is how you get eleven verbs
and a twelfth case that fits none of them."* The rule forbids enumerating
intents. It does not forbid the document carrying a fact, and it cannot: the
document already carries `title` and `href`, and `engineering-spec.md:111-112`
proposes `<text open="true">` — a state-ish boolean on an ordinary node, written
into the spec by the spec, as the shape `<question>` would collapse into if it
earned nothing.

The test that separates the two is: **could this field ever have a twelfth
value that fits none of the ones somebody thought of?** For `state` on every
node, yes, obviously, and that is why option C fails this rule as well as the
tripwire. For `answered`, no. It is one fact with no residue. There is nothing
for a reason to add that the attribute crowds out, because the reason still
carries all of *why* the question is answered and *what* the answer is — the
attribute carries only *that* it is, which is the one part a reader of the
rendered document needs and a reason cannot give them.

### The two readings of the same event, reconciled

This is the part no file in the repository settles, and it has to be settled
here because the two strongest pieces of evidence in the corpus are about the
same commits and point in opposite directions.

`FRICTION.md:109-110`, on `f7be9ea`:

> The finished document contains zero `question` elements — the canvas ends with
> no visible trace that anything was ever asked.

`VERDICT.md:432-434`, on the same edit:

> Entry **37** is that design working — a question node becoming its own
> answer, legible only because a free-text reason said so.

Both are true, and they are not in conflict, because **they are about two
different artifacts.** `--why` lives in the git log. It is legible to somebody
running `bin/canvas history <id>`, and `VERDICT.md`'s whole method was reading
reasons out of the log, which is why from where it stood the design was working.
It is not legible to somebody reading the rendered canvas, and the rendered
canvas is the artifact `product-spec.md:52` says must be *"small enough to read
in a minute and cheap enough to put in every prompt"*. `FRICTION.md` was reading
the document. Nothing was smuggled past either of them; they looked at different
things.

So the rule this ruling extracts, and the rule the rest of it applies:

**A fact a reader of the rendered canvas must act on belongs in the document. A
fact a reader reconstructs when they ask why belongs in the reason.**

That an agent must not quietly answer an open question is a fact it must act on
before it has any occasion to run `history`, and `engineering-spec.md:108-110`
says so in as many words. Which option was chosen over which, and why, is a fact
you go looking for. The line falls between want 1 and want 2 and it falls there
for a stated reason, which is the whole of §1.

`VERDICT.md:425-434` — *"Do not give `--why` required fields or a structured
form"* — is untouched by this. `--why` gains no fields, no structure and no
required vocabulary. The freedom of that field stays exactly as load-bearing as
the verdict found it; §5.2 of the same document (`VERDICT.md:389-413`) is the
precedent that this repository does add mechanism where mechanism can decide
something without judgment, and prices what it costs. This ruling is that shape,
and §7 below prices it.

## 4. Why the answering node's id stays in the reason

The option as the todo phrased it is *"`<question>` gains a way to say it is
answered **and by which node**"*. The ruling takes the first half and refuses the
second, and it refuses it on an argument this repository has already made and
already landed.

`node-identity.md` §7 rejected an `ancestor` attribute for merge and split
lineage, and its four costs transfer to `answered-by` one for one:

- **It is `supersede` in an attribute.** An `answered-by` pointing from a
  question to the node that settled it is a lineage claim between two nodes,
  which is the verb `engineering-spec.md:125` deliberately does not have,
  wearing a different hat.
- **It would be the first piece of node state not derivable from the log**
  (`node-identity.md:568`). RELAX NG cannot check a cross-reference, so
  either the id is unchecked — a pointer that can name a node that does not
  exist — or it is checked in Python, which puts a second copy of the
  vocabulary outside `schema/canvas.rng` and breaks the one rule
  `canvas/validate.py:7-10` and `canvas/document.py:3-10` are both built to
  keep. `answered="true"` is checkable by the grammar alone; `answered-by="wxyz"`
  is not.
- **It is single-valued against an operation that is not.** Two nodes can
  jointly answer one question; an answer can be split later. One attribute
  becomes a list, and `node-identity.md:582-584` already prices a list
  attribute: *"a subtree wearing an attribute's clothes — addressed by no id,
  edited by no verb"*.
- **And it can be false at exactly the moment a run dies.** Answering a question
  with a new node is an `insert` and a `replace`: two commits, because one edit
  is one node. Stamp the pointer on the question first and the document asserts
  it was answered by a node that does not exist yet.

And `node-identity.md:527-536` gives the positive half of the argument, which
applies here unchanged: the reason has to carry the pointer anyway.
`require_reason` already refuses a bare back-reference — *"if the reason is
another node's, name that node's id and say what differs here"* — so the `--why`
on the edit that answers a question is already the place a writer names what
answered it. An attribute beside that sentence would record less of the same
fact and be believed in preference to it, because it is structured and the
sentence is not.

**`answered="true"` is not a pointer.** It is a property of the question node,
about the question node, set by the one commit that is already naming the
question node. That is the whole of why the first half of option B survives §3
and the second half does not.

## 5. Why not option C, and why the argument past `engineering-spec.md:272-276` could not be made

`engineering-spec.md:266-276`:

> **Between the canvas and reality** — the canvas says we chose A; the branch
> implements B. No amount of reading the canvas catches this, and it is the more
> dangerous of the two precisely because the canvas is what a person will use to
> spy on progress and to steer. **This specification does not solve it.** The
> mitigation is convention only: an edit whose reason is a fact about the world
> should name its evidence in `--why` — a PR, a verdict, a file and line — and a
> reader can follow it. Nothing enforces that. A state field distinguishing what
> was asserted from what was verified was considered and rejected as premature;
> if canvas-versus-reality drift turns out to bite, this is where it will be
> fixed, and it should be fixed with evidence in the reason before it is fixed
> with a new attribute.

The two binding clauses, at **272-276**:

> A state field distinguishing what was asserted from what was verified was
> considered and rejected as premature

> it should be fixed with evidence in the reason before it is fixed with a new
> attribute

The todo's instruction is that option C is available only with an argument that
gets past that sentence. **The argument could not be made, and option C is
therefore not taken.** Saying why is worth more than saying so.

The narrow reading is available and is genuinely tempting: what 272-273 rejects
is one specific field on one specific axis — asserted versus verified,
canvas versus reality — and none of the four wants is on that axis. All four are
canvas-internal. Is this question answered, is this row chosen, is this claim
provisional about an open question, is this document finished: not one of them
is a claim about whether the world matches the canvas. On the narrow reading,
272-273 simply does not reach them.

It does not rescue option C, for three reasons.

**First, 274-276 is a general ordering and it does reach them.** *"It should be
fixed with evidence in the reason before it is fixed with a new attribute"* is
not scoped to the asserted/verified axis; it states which of two remedies is
tried first. The corpus shows the reason being tried and the corpus shows what
it bought: `VERDICT.md:40-43` found 41 of 50 reasons meeting the bar, and
`VERDICT.md:432-434` scored the want-1 edit itself as the design working. The
reason was tried on all four wants and it held on two of them. The ordering has
been honoured for wants 2 and 3-as-provisional-state, and that is exactly why
they stay in the reason in §1. For want 1 the reason was tried and found to
leave the *document* — not the log — with no trace, which is a defect the reason
is structurally unable to fix because the reason is not in the document. That is
an argument for the one attribute this ruling adds. It is not an argument for
ten.

**Second, the evidence that has appeared since does not overturn "premature"; on
inspection it cuts the other way.** The one candidate is want 3's staleness:
`35e25a1` wrote a state claim in prose and `3aebd79` had to replace the node
because the claim went false. That is an instance of something biting, and the
escape clause at 274-275 invites exactly that — *"if canvas-versus-reality drift
turns out to bite, this is where it will be fixed."* But read what bit. A state
claim went stale. A `state` attribute on `<text>` would have gone stale in
precisely the same way, on the same commit, needing the same repair, because
nothing verifies an attribute either — and `node-identity.md:572-573` names that
property as disqualifying: *"an `ancestor` attribute is verifiable against
nothing — a claim about history stored outside history."* A state attribute on
every node is a claim about the world stored outside the world. Want 3's
evidence is evidence that unverifiable state claims go stale, which is evidence
**for** the 272-276 rejection, not against it. The fix §1 takes instead removes
the claim rather than relocating it.

**Third, option C fails two other tests independently**, so even a successful
argument past 272-276 would not carry it: the tripwire read in spirit (§2), and
the enumerate-the-intents rule at `engineering-spec.md:128-130` (§3). A `state`
attribute needs either an enumerated value set — a topology that will fall
through the first time somebody needs a value nobody listed — or a free token,
which puts the semantics back in free text and is option A with extra syntax and
a second place for the document to contradict itself.

Option C is refused. If canvas-versus-reality drift does turn out to bite,
`engineering-spec.md:266-276` is still where it gets fixed, and nothing here
forecloses that.

### Why option A is not taken either

Option A had to be argued rather than defaulted into, and §1 is that argument,
want by want: it is taken for wants 2 and 4, and it is refused for wants 1 and 3
for a single stated reason — the reason lives in the log, the question lives in
the document, and *"an agent has to be told not to quietly answer it"*
(`engineering-spec.md:109-110`) is a thing the document has to say to a reader
who has not run `history` and has no reason to. Option A's strongest support,
`VERDICT.md:432-434`, is not evidence against this: §3 shows it is a judgment
about the log, made by a review that was reading the log, and it stands.

## 6. What `schema/canvas.rng` must enforce, and what must fail

This is the whole of the implementable content. A later step should need no
judgment beyond it.

### The grammar

One change, in `<define name="question">` at `schema/canvas.rng:189-194`, between
the `<ref name="node-attributes"/>` and the `<text/>`:

```xml
  <define name="question">
    <element name="question">
      <ref name="node-attributes"/>
      <optional>
        <attribute name="answered">
          <value>true</value>
        </attribute>
      </optional>
      <text/>
    </element>
  </define>
```

- It is `<optional>`, so every canvas on disk and all seventeen fixtures stay
  valid. This is the first optional attribute in the grammar; there is no
  in-repo precedent for the construct and that is expected.
- Its value set has exactly one member, `true`. **`answered="false"` is
  invalid**, deliberately: absence means open, and two ways to spell the same
  state is how a document learns to contradict itself.
- It goes on `<question>` and on nothing else. `node-attributes`
  (`schema/canvas.rng:59-70`) is **not** touched — touching it is option C.
- No change to `<canvas>` at `schema/canvas.rng:27-46`. The root has no state;
  want 4 belongs to todo #10330567174.
- Add a comment above the define in the style of the existing ones
  (`schema/canvas.rng:175-176` is the nearest example), naming this document and the reason
  the value set has one member.

### What must now fail, and how

Nothing that was valid becomes invalid — the change is purely additive — so the
old shape that must fail is the *wrong new* shape. Three fixtures, in the
`tests/fixtures/unknown-node.xml` idiom: one legal node beside the illegal one,
so the diagnostic is shown to pick out the offender rather than condemn the file
wholesale. Assert with `assert_rejected_naming`
(`tests/test_validate.py:98-108`), which already requires exit 1 and not 2.

- **`answered` on an element that is not `<question>`** — e.g.
  `<text id="q4rt" v="1" answered="true">` beside a valid `<question>`. Must be
  rejected, exit 1, diagnostic naming `<text>` and `id="q4rt"`.
- **`answered` with a value other than `true`** — e.g. `answered="false"`, and a
  second case with `answered="yes"` or `answered="TRUE"` if one fixture is made
  to carry both. Must be rejected, exit 1, diagnostic naming `<question>` and
  its `id`.
- **`answered-by="…"` on a `<question>`** — the pointer §4 refuses. The closed
  grammar already rejects an undeclared attribute, so this needs no grammar
  work; the fixture exists to pin the refusal so that adding the pointer later
  means deleting a test and reopening this document. Must be rejected, exit 1,
  diagnostic naming `<question>` and its `id`.

Attribute-level violations already name the node with no change to
`canvas/validate.py` — `_describe` at `validate.py:139-158` prints element name,
`id` and `v` — and `tests/test_validate.py:228-233` and `:173-188` are the
existing proof of it. No validator work is needed.

**All three were run before this was written**, against a scratch copy of the
repository with the grammar above applied, so the shape is not being proposed
untested. `validate_file` returned one diagnostic each and
`bin/canvas-validate` exited 1 each, verbatim:

    answered-on-wrong-element.xml:4: <text> (id="q4rt", v="1"): Invalid attribute answered for element text
    answered-bad-value.xml:4: <question> (id="mqxd", v="1"): Invalid attribute answered for element question
    answered-by-pointer.xml:4: <question> (id="mqxd", v="2"): Invalid attribute answered-by for element question

Both legal shapes — a `<question>` with no attribute and one with
`answered="true"` — validated at exit 0. Note what the diagnostic does and does
not carry: it names the element, the `id` and the `v`, and it does **not** echo
the rejected value, so a test should assert the element and the id and not the
string `false`.

### The premise, pinned in the suite

Following `3bcd0ba` and `cd8d90e` — rulings in this repository pin their premise
as an invariant the suite re-runs — add to `tests/test_validate.py` the mirror
of `test_the_grammar_declares_exactly_the_vocabulary` (`:130-143`): parse the
RNG and assert the set of declared **attribute** names is exactly

    {"ledger", "schema", "id", "v", "title", "href", "answered"}

There is no such invariant today, which is why adding an attribute breaks no
existing test. That is the gap this ruling closes: §2 moves the tripwire to the
attribute set, and this is the tripwire. A twelfth attribute, or a second legal
value for `answered`, should break a test and force somebody to come back here.

### The one positive case

`tests/fixtures/valid.xml` gains an answered `<question>` beside the open one it
already has, so the legal shape is exercised and not only the illegal ones.

### The command line

`canvas/cli.py:305-333`, `_add_payload`, gains one flag beside `--title` and
`--href`:

    parser.add_argument(
        "--answered",
        action="store_true",
        help="mark a <question> answered; absence means open",
    )

and the docstring at `cli.py:309` — *"the two attributes the closed vocabulary
has that are not identity"* — becomes **three**, naming this one. A named flag
and not a general `--attr`, for the reason already given there. The flag reaches
`store.replace` and `store.insert` and is passed into the `attributes` dict at
`store.py:2349-2355` beside `title` and `href`; `document.new_node`
(`document.py:92-115`) needs no change, because it already drops a `None`.

Two consequences to write down rather than discover:

- **The attribute is restated, not sticky.** `replace` builds a new node from
  the payload, so a `replace` that omits `--answered` clears it — exactly as it
  already does for `title` and `href`. That is how a question gets reopened, and
  it needs no new verb.
- **Marking a question answered bumps `v`.** It is a commit naming the node, and
  `v` is what the log counts (`node-identity.md` §4). No new rule; noting it so
  nobody treats it as a bug.

## 7. What this costs, stated honestly

**A question is retyped to answer it.** `store.replace` builds the replacement
from the payload, so `--text` omitted means the node's character data is
dropped, not preserved (`store.py:2349-2355`). Marking a question answered
therefore means passing its text again. That is the same defect that made want 2
expensive — *"`replace` takes the new text and not a patch of it"*
(`FRICTION.md:121-122`) — and this ruling does not fix it. It is smaller here
than there: a question is a sentence, a comparison cell was several hundred
characters. But it is the same defect and it is named in *Still open* rather
than quietly absorbed.

**The first optional attribute in the grammar is a precedent.** Every attribute
today is required. Optionality is a door, and the next person who wants one will
point at this. The mitigation is the attribute-set invariant in §6, which makes
walking through that door break a test.

**`<question>` now earns its keep, which forecloses the cheaper future.**
`engineering-spec.md:111-112`: *"If it turns out to earn nothing, it folds back
into `<text open="true">`."* This ruling answers that clause in the negative and
should say so plainly: `<question>` earns something, and this document is the
argument that it does. The retirement is not available while `answered` stands,
because folding `<question>` into `<text open="true">` would put openness on an
ordinary structural element — which is §2's objection to option C, arrived at
sideways. Anyone who later wants the retirement has to reopen this.

**Two of the four wants get nothing.** Want 2 is left with a `replace` and a
reason, and want 4 with a node that says the document is finished while anybody
with the ledger id can still write to it tomorrow. §1 argues both are right. If
either is wrong, it is wrong on the record and pointable-at, which is the reason
this is a document rather than a habit.

## What this makes deliberate, and what stays free to change

These two lists are what goes into the orchestrator's
`guidelines/domain-decisions.md`.

### Deliberate — a later change may not rewrite these without reopening this document

- **A canvas says exactly one thing about a node's state: whether a
  `<question>` has been answered.** No other node carries state, in any
  spelling. *Why:* the four wants are not one want (§1), and the general form —
  a canvas carrying metadata about a node — is what
  `engineering-spec.md:272-276` rejected as premature and §5 could not argue
  past.
- **`answered` is legal on `<question>` and on no other element.** *Why:*
  `<question>` is the declared semantic exception (`engineering-spec.md:108-109`);
  putting state on structural elements is what makes the vocabulary a topology
  (§2).
- **`answered` has exactly one legal value, `true`; absence means open.**
  *Why:* a one-member value set cannot be a taxonomy that falls through, and two
  spellings for one state is how a document contradicts itself (§2, §6).
- **A `<question>` does not point at the node that answered it.** `answered-by`
  or any equivalent id-valued attribute is refused. *Why:* the four costs
  `node-identity.md` §7 prices for an ancestor id apply one for one, and the
  reason already has to name what answered it (§4).
- **The reason carries semantics; `--why` gains no fields, no structure and no
  required vocabulary.** *Why:* `engineering-spec.md:128-130`,
  `product-spec.md:48`, and `VERDICT.md:425-434` on evidence.
- **Openness is stated in exactly one place — the question node itself.** No
  other node may assert whether a question is open. *Why:* `FRICTION.md:162-163` —
  *"A canvas whose nodes disagree about whether a question is open is worse than
  one that never said"* — and want 3 is answered by making the disagreement
  inexpressible (§1).
- **The vocabulary is written down once, in `schema/canvas.rng`.** No
  vocabulary rule moves into Python, which is the reason the pointer is refused
  rather than merely deprecated. *Why:* `validate.py:7-10`, `document.py:3-10`.
- **"This document is finished" is not a node state.** Whatever ends a canvas is
  a property of the root or of the ledger. *Why:* §1, want 4;
  `engineering-spec.md:327-338`; the root carries no `id` or `v`.
- **The decision rule behind all of the above:** a fact a reader of the rendered
  canvas must act on belongs in the document; a fact a reader reconstructs when
  they ask why belongs in the reason. *Why:* it is what reconciles
  `FRICTION.md:109-110` with `VERDICT.md:432-434` (§3), and it is the test any
  future proposal of this kind should be put to.

### Free to change — implementation choices, not decisions

- **The attribute's spelling.** `answered` versus `resolved` versus `closed`;
  `answered="true"` versus a valueless spelling, if the grammar gains a cleaner
  one. The fact carried is deliberate; the word is not.
- **The CLI surface.** `--answered` as a store-true flag, the flag name, its
  help text, and the wording of the `cli.py:309` docstring. A different flag
  shape that sets the same attribute is free.
- **Whether `replace` can change an attribute without restating `--text`.**
  Today it cannot (§7). Fixing that is a change to `store.replace`, not to this
  vocabulary, and it would make marking a question answered cheap without
  touching anything above.
- **The fixture filenames and the exact diagnostic wording asserted.** The tests
  assert behaviour and not wording by standing policy
  (`tests/test_validate.py:3-6`).
- **The renderer's treatment of an answered question** — quiet, struck through,
  collapsed, or moved. This ruling settles only that the renderer *can* tell,
  and that an open question must be loud.
- **Whether a `<question>` may be born answered** via `insert --type question
  --answered`. The grammar permits it and nothing forbids it. If that turns out
  to be a nuisance it can be refused in the CLI without reopening this.
- **The attribute-set invariant's exact form** — parsed set equality is the
  obvious shape because the element invariant already uses it, but any check
  that breaks when the attribute set changes serves.

### Known tensions — unresolved, recorded

One of the five below has since been ruled on. It is kept here and marked rather
than deleted, so that a reader who was told it was unresolved is told by the same
place that it is not, and so that what settled it stays one link away from where
it was recorded. The other four stand.

- **`<question>`'s retirement clause now points the other way.**
  `engineering-spec.md:111-112` says `<question>` folds back into
  `<text open="true">` if it earns nothing. This ruling makes it earn something,
  so the spec's own named exit is closed while `answered` stands — and the spec
  has not been edited to say so. The two documents now disagree in tone if not
  in letter, and whoever next edits `engineering-spec.md` should reconcile them.
- **`FRICTION.md` and `VERDICT.md` still read the same event in opposite
  directions in their own texts. — Settled 2026-09-24: both were amended, and
  each now cites the other and this section.** §3 reconciles them here, by
  distinguishing the document from the log; when this was written neither file
  cited the other and neither had been amended, so a reader who found only one
  of them got one of the two readings whole. That is no longer true of either.
  `docs/drive-by-hand/FRICTION.md:114-118` cites `VERDICT.md:432-434` and §3;
  `docs/why-verdict/VERDICT.md:449-455` cites `FRICTION.md:109-110` and §3.
  Neither amendment widens this ruling — the verdict's own addition re-asserts
  that *"`--why` still gains no fields, no structure and no required
  vocabulary"* — and each is marked as a later addition, so both records still
  read as what their authors wrote on the day. What is settled is the finding,
  not the disagreement: the two readings stand as two readings, and §3 remains
  the only thing that reconciles them. Nothing is left open in this bullet.
- **A state claim in an attribute can go stale exactly as a state claim in prose
  can.** §5 uses this against option C, and it is equally true of `answered`:
  nothing verifies that an `answered="true"` question really was answered. The
  defence is that the marker is set by the same commit that writes the answer,
  so the window is one commit wide rather than open-ended — but it is a defence
  and not a proof, and if it turns out to bite, this is the sentence to point at.
- **Want 2's real cost is untouched and lives elsewhere.** `replace` takes whole
  text and not a patch, so marking anything means retyping the node. This ruling
  narrows how often that hurts; it does not fix it, and nothing in this
  repository owns it yet.
- **Want 4 is handed to another todo and could come back differently.**
  #10330567174 may conclude that ending a canvas needs something this ruling did
  not anticipate. The only constraint left on it is that whatever it is, it is
  not a node state.

## Still open

- **Whether `replace` should be able to change an attribute without restating
  the node's text.** Today it cannot: `store.replace` builds the replacement
  from the payload and a missing `--text` drops the character data
  (`store.py:2349-2355`). That makes marking a question answered a retype of the
  question, and it is the same defect that made `CHOSEN.` cost several hundred
  characters twice. It is a question about the verbs and not about the
  vocabulary, which is why it is not decided here, and it is the single change
  that would do most for the wants this ruling leaves in the reason.
- **What ends a canvas.** Want 4, handed by name to
  [#10330567174](https://app.basecamp.com/3934852/buckets/48039419/todos/10330567174).
  `engineering-spec.md:327-338` promises a freeze at `done` and `bin/canvas`
  does not implement one. This document constrains that answer in exactly one
  way: it is not a node state.
- **Whether authorship is the same shape.** `FRICTION.md:161-167` says what a
  canvas needs to say *about* a node has to be smuggled into the node, and names
  authorship as the other instance. This ruling refuses the general form and
  answers one instance; it does not answer that one. If authorship belongs in
  the document it needs its own argument, and *"we already did it for
  `answered`"* is not one.
- **Whether an answered `<question>` should ever be `replace`d away.** Nothing
  here forbids it, and a canvas that resolves (`product-spec.md:52`) may
  legitimately want the question gone once nobody will re-ask it. The marker is
  the preferred move and the destruction stays available. Whether that is right
  is a renderer-era question: it depends on whether an answered question still
  earns its space in an artifact that goes in every prompt.
