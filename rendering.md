# Rendering

Settled 2026-09-23, with the figure ruling reversed by the spec author's
2026-09-25 decision. This document decides the two questions `bin/canvas render`
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

## 1. `<figure>` is drawn from a repository-owned source, with inline SVG as an escape hatch

**Decision, reversed 2026-09-25 by the spec author:** schema v2 keeps `<figure>`
as one of the existing eleven leaf elements and distinguishes two character-data
payloads. With no `payload` attribute it is Canvas Diagram 1, the default textual
notation owned and versioned by this repository. `payload="svg"` is escaped
inline SVG admitted only through a closed safe subset. The standalone projection
draws both as real inline SVG; the Basecamp-comment projection labels and fences
the source because that transport cannot display the picture.

The **2026-09-23 ruling is reversed, not deleted**: it said the stored text was
printed verbatim and no drawing step existed. Its evidence named the condition
that would reopen it — real canvases whose figures carried enough weight that a
reader needed the picture. Fresh live-store evidence supplied that condition,
and the spec author decided on 2026-09-25 that figures should be drawn.

The history matters because the old ruling overstated what had already been
decided. The schema-v1 textual grammar shipped at commit `a56db5b`; that commit
settled the legal stored shape, not the product question of whether the renderer
should draw it. The open question was later mistakenly treated as a product
decision because one representational half had shipped. Schema v2 now states the
actual product decision while preserving an explicit schema-v1 branch, so every
old canvas remains valid and renderable without migration.

Canvas Diagram 1 pays for drawing under the clean-checkout rule. It is a small,
line-oriented explicit-grid language (`box`, `edge`, `text`) parsed and rendered
by Python's standard library. Mermaid was rejected because it adds Node and an
externally versioned grammar; Graphviz and PlantUML were rejected because they
add binaries. Malformed lines, unknown commands, duplicate ids, missing edge
endpoints and bad coordinates become escaped diagnostic rows inside the SVG,
while valid statements still draw. The textual renderer is total, so no source
accepted by the canvas schema can fail only at render time.

Inline SVG pays a different price. It diffs poorly and a replacement rewrites
the whole figure node, so its per-node history is noisier. A closed validator
rejects scripts, event attributes, CSS, links, URLs, images, reuse, foreign
objects, animation, entities and non-SVG namespaces before the store commits the
node. Rendering reparses and reserializes only that accepted tree. That safety
boundary and history cost keep SVG an explicit `payload="svg"` escape hatch;
agents are taught Canvas Diagram 1 and the CLI makes `--text` the normal path.

The standalone page remains one self-contained file with no stylesheet, script,
font, image fetch, subprocess or network. The drawing is inline SVG made
in-process, so the promise survives and now explicitly includes the cost of the
repository-owned drawer. Basecamp comments cannot carry the picture honestly;
they preserve fenced Canvas Diagram 1 source or entity-escaped fenced SVG markup,
label which payload it is, and contain no literal less-than sign.

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
- **Anything else about the canvas file.** The eleven-element vocabulary is
  unchanged. A later renderer decision that needs a twelfth element or another
  payload/state attribute has found the tripwire rather than a requirement.
- **How much of a node's `--why` history a projection shows.** Ruled on
  2026-09-28 by `problem-and-solution-space.md` beside this file, not here.
  **The renderer's non-presentation commitments are three and not two:** the
  two above, and *exactly one reason per node that crossed between the
  canvas's sections, none on any other node, and the full sha beside it*, on
  both projections. It is a question of the same kind as these two — a
  presentation choice that, taken quietly, would decide something about the
  document — and it is ruled in a different file because it is stated in terms
  of what a crossing is. That document's *Known tensions* asked for this
  sentence to be written here; this is it.

## Known tensions

- **The `<figure>` item in both specs has been reconciled with §1 above, and is
  no longer a tension.** `product-spec.md:132` and `engineering-spec.md`'s *Open*
  each stated it as a choice between drawing and passing SVG through. Both now
  keep the old item visibly marked as reversed, name the 2026-09-25 author
  decision, and state the schema-v2 two-payload result. Nothing here is handed
  forward.
- **"Loud" is still a word two readers will rule differently.** What is enforced
  is the mechanical part — every question in the index, a marker on every
  question node — and the contrast, the border and the dimming are not enforced by
  anything and will drift with taste. That is the right place for the line, and it
  does mean a future renderer could satisfy every test here and be quiet.
