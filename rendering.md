# Rendering

Settled 2026-09-23. This document decides the two questions `bin/canvas render`
could not inherit from anywhere: what the renderer does with a `<figure>`, and
what the index of open questions and the per-node marker do with a question that
has been answered. Everything else about the page — its headings, its stylesheet,
its order, its wording — is an ordinary presentation choice, belongs to
`canvas/render.py`, and is not settled here or anywhere else, because
`engineering-spec.md`'s section *The substrate* already gives the renderer every
one of them: *"It owns every presentation decision. Nothing in the canvas file is
about how it looks."*

These two are different from the rest in the same way: each of them is a
presentation choice that, taken quietly, decides something about the **document**
rather than about the page. A renderer that drew diagrams would decide which
notation a `<figure>` may hold; a renderer that hid answered questions would
decide whether an answered question is still part of the canvas. `node-state.md`
opens by refusing exactly that move — *"A rule arrived at implicitly, by a
renderer that happens to render one thing loudly, is a rule nobody can argue with
afterwards"* — so both are argued here before the page is looked at.

**Nothing in this document changes the vocabulary.** No element, no attribute and
no configuration file was added to serve the renderer, and none is proposed. The
grammar this renderer reads is `schema/canvas.rng` as it already stands, eleven
element names and no twelfth.

## 1. `<figure>` holds a textual source, and this renderer does not draw it

**Decision: a `<figure>` is rendered as its own source — the stored text,
verbatim, in a monospaced block, with the node's id in the caption. There is no
drawing step, no diagram toolchain, no subprocess and no new dependency. Inline
SVG is not passed through, because in schema v1 there is none to pass.**

### The half that was already decided

`engineering-spec.md` *Open* states the trade as two sides:

> Whether the renderer should draw `<figure>` from a textual source or only pass
> through inline SVG. Inline SVG diffs badly; a textual source needs a drawing
> step the canvas tool would have to own.

`product-spec.md:132` carries the same item. But the grammar shipped before this
document did, and it took half of it already. `schema/canvas.rng`'s
`<define name="figure">` admits character data and nothing else, and says why in
its own comment:

> A diagram. In schema v1 a `<figure>` holds a textual source only. Admitting
> inline SVG means admitting a foreign namespace with an open element set, which
> is the HTML problem the closed vocabulary exists to prevent.

`README.md` section *What the schema deliberately does not check* restates it and
prices the other side: *"Settling it the other way is a v2 change with its own
reasoning."*

So "only pass inline SVG through" is not a decision a renderer can take on its
own. There is no valid canvas that carries inline SVG for it to pass through, and
a renderer written for one would be a renderer for a document the validator
refuses. Taking that side means schema v2, and schema v2 means a foreign
namespace with an open element set inside a vocabulary whose entire argument is
that it is closed — *"A closed list that can be opened by configuration is not
closed"*. That price is not paid here and this document does not propose paying
it. The source is textual, as shipped.

### The half this renderer had to decide

What is left is the question the spec's own sentence names: a textual source
*"needs a drawing step the canvas tool would have to own"*. This renderer does
not take one, for three reasons and one that is not a reason.

- **It cannot be had for free, and this repository's rule is that everything is.**
  `README.md` section *Running the tests*: *"From a clean checkout, with no
  install step, no virtualenv and no network… Standard library only."* Every
  drawing step is the opposite of that — Mermaid is Node, Graphviz and PlantUML
  are binaries, and each is an install, a version to pin and a thing that is
  absent on the machine where somebody re-renders a page. The renderer would be
  the first thing in this repository that does not run from a clean checkout, and
  it would be the projection — the artifact that is supposed to be cheap and
  regenerable — that broke the rule.

- **Owning the drawing step means owning a second vocabulary, in a language
  nobody here wrote down.** The whole of what a canvas node may be lives in
  `schema/canvas.rng` and nowhere else; that is the property that makes a
  violation an exit code rather than a code review. A drawn `<figure>` puts a
  second grammar inside the first — Mermaid's, or dot's — defined by whichever
  binary happens to be installed, versioned by it, and validated by it. A
  `<figure>` whose source that binary rejects would be a node that passes
  `bin/canvas-validate` and fails to render: an invalid canvas that validates,
  which is the one state this repository has spent every ruling making
  unreachable.

- **A drawing step has a failure mode a projection may not have.** A projection
  is regenerated on demand and pasted into comments. If drawing can fail — a bad
  source, a missing binary, a timeout — then `render` grows a second kind of
  outcome that is neither the page nor a refusal, or it grows a refusal for a
  document that is perfectly valid. Both are worse than a monospaced block.

- **Not a reason: that drawn diagrams would look better.** They would. That is a
  real loss and it is priced below, not argued away.

### What it costs, stated because it is real

A `<figure>` in a rendered page is text in a box. An ASCII box diagram renders as
an ASCII box diagram; a Mermaid source renders as the Mermaid source. Nobody gets
a picture. What they get instead is the thing `engineering-spec.md` wanted from a
textual source in the first place — the figure a reader sees is byte for byte the
figure the canvas stores, and byte for byte what the next diff will show, which
is the property inline SVG was rejected for not having.

### What would reopen it

A canvas where figures carry real weight — where a reader of the page cannot act
on the source and needs the picture. That is evidence, and it is not in hand:
`docs/drive-by-hand/` drove a real canvas by hand and it holds no `<figure>` at
all. Whoever brings it should reopen this section rather than add a drawing step
beside it, and the first question they have to answer is not which drawer to use
but who owns the notation and what a source the drawer rejects means for a
document the validator accepted.

## 2. The index names every `<question>`, and an answered one is quiet rather than absent

**Decision: the index at the top of the page names every `<question>` id in the
document, answered ones included, in document order, and says of each which it
is. Every `<question>` node in the body carries a marker of its own — the words
"Open question" or "Answered question" — and an answered one is dimmed in both
places. Nothing is collapsed, struck through, moved or dropped.**

### What was already settled, and what was left free

`engineering-spec.md:108-110` is why `<question>` exists at all: *"an open
question has to be findable — the renderer has to make it loud, and an agent has
to be told not to quietly answer it"*. `node-state.md` settles the document side
of that — a `<question>` may carry `answered="true"`, absence means open, and no
other node may say anything about it — and then explicitly leaves this half open,
in its *Free to change*:

> **The renderer's treatment of an answered question** — quiet, struck through,
> collapsed, or moved. This ruling settles only that the renderer *can* tell, and
> that an open question must be loud.

Between those two, one presentation is genuinely free and one is not. Quiet,
struck through, collapsed, moved: free, and the choice among them is taste. Gone
— dropped from the index because the index is of *open* questions — is not, and
this is the section that says why.

### Why an answered question stays in the index

- **The done condition says so, and its test is the deliverable.** The task this
  renderer was built for states it mechanically, in the words that survive two
  readers disagreeing about what "loud" means: the page opens with an index that
  names *every* `<question>` id in the document and nothing else. An index built
  by omission does not satisfy that sentence, and the sentence was written that
  way on purpose.

- **An index built by omission cannot be checked against anything.** The page is
  pasted into a Basecamp comment, and a reader of that comment has the page and
  not the canvas. "Here is every question this document has, and here is which
  ones are open" is a claim they can hold the page to — count the markers, count
  the entries. "Here are the ones that were open at that sha" is a claim about a
  document they cannot see, and a reader cannot tell it from "nobody asked
  anything".

- **It is the recorded failure, one layer up.**
  `docs/drive-by-hand/FRICTION.md:109-110` is the complaint that produced
  `node-state.md` in the first place: *"The finished document contains zero
  `question` elements — the canvas ends with no visible trace that anything was
  ever asked."* `answered="true"` exists so that the trace survives in the
  document. A renderer that hides answered questions takes the trace back out
  again in the projection, and the projection is the artifact
  `node-state.md` §3 says the rule was written for.

- **Hiding them would answer a question this repository has deliberately left
  open.** `node-state.md` *Still open* asks *"whether an answered `<question>`
  should ever be `replace`d away"*, and says the answer *"depends on whether an
  answered question still earns its space in an artifact that goes in every
  prompt"*. A renderer that drops them from the index has answered that — by
  building, quietly, which is the move `node-state.md`'s own opening refuses. A
  quiet entry leaves the question to whoever decides it, with evidence: they will
  be able to see what answered questions cost in a real page.

### The objection this answers, and does not route around

[Todo 10331177958](https://app.basecamp.com/3934852/buckets/48039419/todos/10331177958) — *Reconcile the specs with
the node-state ruling* — raises exactly this, and raises it as a contradiction:
the sentence requiring an index of *open* questions that names every
`<question>` id was written before `answered="true"` existed, so *"a renderer
built to that sentence literally would list answered questions as open — the
exact contradiction the ruling made inexpressible in the document."*

That is true of one way of building it and not of the one built. The index does
not list an answered question **as open**: every entry says which state it is
in, and an answered one says `answered` and is dimmed. What the ruling made
inexpressible is a document in which two nodes disagree about whether a question
is open; a page that names every question and marks each one from the single
place the document states it cannot produce that disagreement, because it reads
the same attribute for every entry. The alternative — dropping answered
questions — would leave the page unable to say anything about them at all,
which is not a stronger reading of the ruling but a quieter one.

### Why the heading still says "Open questions"

Because that is what a reader scans it for, and because the open entries are the
loud ones in it. `engineering-spec.md`'s requirement is that an open question be
*findable*; an index titled "Questions", in which the open ones are three dimmed
entries down, is accurate and no longer does the thing it exists for. The heading
names the job; the entries are complete.

### How loud, concretely

- **In the index**: one entry per `<question>`, in document order, each an anchor
  to that node. An open entry carries the word `open` at full contrast; an
  answered one carries the word `answered` and is dimmed. Document order and not
  open-first, because a map whose entries are in a different order from the thing
  it maps is a second document to keep in your head.
- **On the node**: every `<question>` carries a visible marker of its own, in
  words — "Open question", "Answered question". A word and not a colour, because
  the done condition is that every question node carries a marker, and a colour is
  not something a reader of the HTML, or a test, can point at. An answered
  question is dimmed and its rule goes dotted, and that is the whole of the
  difference.
- **Nothing is moved and nothing is collapsed.** Both were free and both were
  refused for the same small reason: they make the page's order differ from the
  document's, and the id in the page is the id in the canvas, so a reader who has
  found a node in one has found it in the other.

### Free to change, without reopening this

The label wording, the dimming, the CSS, the `<ol>`, the caption, the heading
level, whether an entry shows the question's text as well as its id. All
presentation, all `canvas/render.py`'s.

What is not free without reopening this section: that **every** `<question>` id
appears in the index, that **only** `<question>` ids appear in it, and that
**every** `<question>` node carries a marker of its own. Those three are the done
condition, `tests/test_render.py` asserts each of them on a canvas with open
questions and on one with none, and a change to any of them is a change to what
the page claims rather than to how it looks.

## What this document does not decide

- **Where the page goes.** `bin/canvas render <ledger-id>` writes the page to
  stdout and nothing else; redirection is the shell's. That is a command-line
  shape, documented in `README.md`, and it is not a ruling — except for the one
  part of it that is: there is no `--output` and no path argument, because a
  projection this command could write anywhere is a projection somebody
  eventually writes into `state/canvas`.
- **Whether an answered question should be removed from the *document*.** Still
  `node-state.md`'s *Still open*, still open. This renderer is now the evidence
  that question was waiting for, not its answer.
- **Anything about the canvas file.** The vocabulary is unchanged, and a later
  renderer decision that needs a twelfth element or a twelfth attribute has found
  the tripwire rather than a requirement.

## Known tensions

- **The `<figure>` item in both specs has been reconciled with §1 above, and is
  no longer a tension.** `product-spec.md:132` and `engineering-spec.md`'s *Open*
  each stated it as a choice between drawing and passing SVG through, and neither
  had been edited. Both now keep the item, marked settled, naming this section as
  what settled it; `engineering-spec.md`'s node vocabulary row for `<figure>` no
  longer says the renderer draws or that inline SVG may be passed through. Nothing
  here is handed forward.
- **"Loud" is still a word two readers will rule differently.** What is enforced
  is the mechanical part — every question in the index, a marker on every
  question node — and the contrast, the border and the dimming are not enforced by
  anything and will drift with taste. That is the right place for the line, and it
  does mean a future renderer could satisfy every test here and be quiet.
