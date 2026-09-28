# Problem and solution space

Settled 2026-09-28. This document decides two things and no third. First, what
it means — mechanically, in the vocabulary that already exists — for a node to
have moved from a canvas's problem space to its solution space. Second, how much
of a node's `--why` history a rendered projection is allowed to show. It decides
nothing about how either is drawn, nothing about what an agent is obliged to
write, and nothing about the canvas lifecycle. What is still open is named at the
end.

The reason it is settled now and not later: both halves are things a renderer
would otherwise decide by accident. A renderer that showed a reason under some
nodes and not others would have decided which nodes are *in* the solution space;
a renderer that showed every reason on every node would have decided that the
page is a transcript, which `product-spec.md`'s *What it is not* refuses in one
sentence. `node-state.md` opens by naming exactly that hazard — *"A rule arrived
at implicitly, by a renderer that happens to render one thing loudly, is a rule
nobody can argue with afterwards"* (`node-state.md:16-18`) — and the hazard is
the same one here, so the same answer applies: argue it before the page is
looked at.

It holds the existing commitments fixed rather than relitigating them:

- **The vocabulary is closed.** Eleven element names and no twelfth
  (`schema/canvas.rng`, pinned by the element invariant in
  `tests/test_validate.py`). Nothing below adds an element, an attribute or a
  configuration file. There is no `<assumption>`, no `space=`, no `status=`.
- **`<section>` is structure, not semantics.** `engineering-spec.md`'s *The node
  vocabulary* gives it one line, at `engineering-spec.md:88`: *"`<section>` | the
  only container; carries `title`; nests one level"*. The paragraph under it, at
  `engineering-spec.md:103-105`, states the defence the whole vocabulary rests
  on: *"this vocabulary is structural and not semantic: `table`, `text`, `list`
  describe shape, and shape does not run out"*.
- **The semantics live in the reason** (`engineering-spec.md:134-136`,
  `product-spec.md:48`), and a `--why` gains no fields and no required vocabulary
  (`docs/why-verdict/VERDICT.md` §5.3, `guidelines/canvas-why.md` in
  `malkovro/ledger-orchestrator`).
- **One edit is one node, one edit is one commit**, and a node's history is the
  set of commits whose `Canvas-Node:` trailer names it
  (`engineering-spec.md`'s *The timeline*, `engineering-spec.md:192` and
  `:218-223`; `canvas/store.py`'s `history`).
- **`move` changes a node's position and nothing else** — not its id, not its
  content, not its type — and its subtree travels with it untouched
  (`node-identity.md` §3 and §5).
- **No node carries state in any spelling** except `answered` on `<question>`
  (`node-state.md`'s ruling, and `engineering-spec.md:289-295`, which rejected a
  state field as premature and said it *"should be fixed with evidence in the
  reason before it is fixed with a new attribute"*).

Every rule below was checked against those six, and where a candidate rule
contradicted one, the candidate was the thing that gave way.

## The worked example this is argued from

Exactly one canvas in the live store uses `<section>` at all: the canvas for
`duplicate-invoice-criterion-output-schema`, one of 62 present on 2026-09-28.
Its shape is what this document generalises, so it is worth stating what that
shape actually is rather than what it is remembered as.

Two `<section>` nodes at the top level: `czfj`, titled `Problem space`, and
`jub8`, titled `Solution space`. Two `<text>` nodes — `q39f` and `x6fk`, the
problem and the expected value the row was born with — sit at the top level
*outside* both sections. `czfj` holds two `<figure>` nodes that show the break
and the measurement of it. `jub8` holds three `<question>` nodes and one
`<figure>` laying out three options against cost.

**Not one node in that canvas was ever moved.** `bin/canvas history
duplicate-invoice-criterion-output-schema <id>`, run against each of its eleven
nodes on 2026-09-28, returns a single `insert` for nine of them and an `insert`
followed by one `replace` for `q39f` and `x6fk`. There is no `move` commit in
that canvas's history at all. Both sections and every node in them were inserted
into the position they still occupy.

That fact is load-bearing twice over and both readings are taken below: the
shape does not require a crossing to exist (§3, first edge case), and a ruling
that made a canvas without crossings defective would condemn the only canvas
that has ever had the shape.

The other thing that history shows is a warning, and it is already on record.
Seventeen of the 36 commit subjects in that canvas are the identical string
*"describe the problem and solution space for this row"* —
`docs/why-verdict/maintenance-check.md` §1.2 counts them and rules on them:
*"That is one writer issuing batches, not a person composing a reason per node —
and it is, incidentally, the failure `VERDICT.md` §5.1 exists to stop, arriving
here through a door that review never looked at."* So the worked example is a
model of *structure* and an anti-model of *reasons*. §5 below is written knowing
that the reasons a page will be asked to show are, on today's evidence, often
that bad.

## The ruling

**1. A node has crossed when a `move` naming it changed which `<section>` it
sits in.** Precisely: an edit crosses a node when its verb is `move` and the
node's nearest `<section>` ancestor in the document at that commit differs from
its nearest `<section>` ancestor in the document at that commit's parent, where
*having no `<section>` ancestor* counts as one of the two values and is not
equal to any section. A node that has at least one crossing in its history **has
crossed**; the last such edit is **its crossing**, and the `--why` of that edit
is the assumption that carried it. Nothing else is a crossing: not an `insert`,
not a `remove`, not a `replace`, not a `move` that left the nearest `<section>`
ancestor the same, and not a `move` of some *other* node that changed where this
one sits.

**Which section is "problem space" and which is "solution space" is read off the
`title` by the person, and by nobody else.** No rule here, no test, no renderer
and no tool reads the characters of a `title`. The document never claims which
of its sections is which, because it has no way to claim it that is not a word a
renderer is expected to interpret, and `node-state.md` refuses that class of
thing by name.

**2. A projection shows exactly one reason per crossed node — the `--why` of
that node's crossing, verbatim, beside the sha of the commit it came from — and
no reason anywhere else.** A node that has not crossed carries no reason. A node
that has crossed three times carries one. No node carries two. A canvas in which
nothing has crossed renders with no reason in it at all, and that includes every
canvas in the live store today.

## 1. Why the ruling is about a crossing and not about a space

The obvious ruling is the one this does not take: *the solution space is the
section titled "Solution space", and a node is in it when it is under that
section.* Three things kill it, and the third is the one that would have been
found later and more expensively.

**It puts a keyword in the document.** `title` is free character data. A rule
that says *"Solution space"* means something to a tool makes that string a
reserved word — one that nothing validates, nothing documents in
`schema/canvas.rng`, and nothing catches when a person writes `Solutions`,
`Solution-space`, `What we think now` or `Where we landed`. The domain ruling
that governs this is `node-state.md`'s, restated in
`guidelines/domain-decisions.md` in `malkovro/ledger-orchestrator`: no node
carries state *"in any spelling — not a `status`, not a `state`, not a
`resolved`, not a word inside the text that a renderer is expected to read."* A
title a renderer is expected to read is that last clause exactly. The attribute
would be spelled `title=` instead of `status=`, and that is the only difference.

**It is the tripwire in another spelling.** The *Risks and open decisions* table
in `product-spec.md` gives the growing vocabulary a row of its own, and the
landing place in that row, at `product-spec.md:125`, is a tripwire that fires the
day somebody proposes a decision or a risk node type — at which point, in its own
words, *"the taxonomy has started growing"*. A privileged section
title is a node type declared in character data rather than in the grammar. It
is `<solution-space>` with the angle brackets taken off, and it inherits every
property of the growth `engineering-spec.md:99-106` warns about *except* the one
that would make it visible — it cannot be caught by the attribute-set invariant
or by the element invariant, because it is not an element and not an attribute.
Of the two, the undetectable one is worse.

**It does not describe the thing the work is about.** What a reader wants to see
is not *where a node is*; it is *that a node is somewhere it did not start, and
what assumption put it there*. Placement alone cannot say that: `bwbs` and `v6k5`
are in `jub8` because they were written there, and a rule keyed on placement
would claim they were carried across by an assumption that does not exist. The
event is the crossing, and the crossing is a fact about the *history*, which is
where this repository already keeps the facts you reconstruct rather than act on
(`node-state.md:343-344`, the decision rule).

So the ruling names the event and leaves the naming of the spaces to the person
who wrote the titles. A reader who sees a node under a heading that says
`Solution space`, carrying one line that says what was assumed to put it there,
has the whole thing — and got it without the document ever asserting which of
its own sections is which.

## 2. What a crossing is, mechanically

Two documents and one comparison. For an edit `E` in a node's history, with the
node id `N`:

1. `E` is a crossing only if its verb is `move`. `store.Edit` carries the verb,
   and `bin/canvas history <canvas-id> <node-id>` already prints it.
2. Let `before` be the canvas document at `E.sha^` and `after` be the document at
   `E.sha`. Both are the whole file at that commit; the canvas directory is a git
   repository and one edit is one commit (`engineering-spec.md:192`), so both
   exist for every edit that is not the first.
3. Let `S(d)` be the `id` of the nearest `<section>` ancestor of the node with id
   `N` in document `d`, or the sentinel *none* when `N` has no `<section>`
   ancestor in `d`. `<section>` nests one level (`engineering-spec.md:88`), so
   there are at most two ancestors to walk and "nearest" is unambiguous.
4. `E` crosses `N` when `S(after) ≠ S(before)`, comparing *none* as a value
   unequal to every section id.

**Why the comparison is of section ids and not of positions.** A `move` records
the node it named, the reason, the author and the base it was written against,
and no position: `canvas/store.py`'s `_write_and_commit` builds the subject
`"%s %s: %s" % (verb, subject_name, why)` and the trailers `Canvas-Node:`,
`Canvas-Author:` and `Canvas-Base:`, and `--after` / `--into` appear in none of
them. The position is in the document, not in the commit. So *where a node went*
is not a thing the log can be asked; it is a thing two documents are compared
for. This ruling is written as that comparison rather than as a query against
the log because the log genuinely does not carry it, and a rule phrased as if it
did would be unimplementable.

**Why *none* is a value and not an absence.** The worked example's `q39f` and
`x6fk` sit outside both sections. A later edit that moved `q39f` into `czfj`
would be the canvas saying *the problem the row was born with is now part of the
problem space we have drawn* — a real event with a real assumption behind it, and
one a reader should see. Treating *none* as equal to nothing would make that
event invisible while making a move out of a section into the ungrouped body
invisible too, and those are the two edits most likely to be worth reading.

**Why `v` is not the test.** A node's `v` is the number of commits naming it
(`node-identity.md` §4), and it bumps on a `replace` and an in-section reorder
just as it does on a crossing. `v > 1` says the node was edited; it says nothing
about whether it went anywhere. Nothing here reads `v`, and nothing here changes
what `v` counts.

## 3. The edge cases, ruled

Each of these is a case two readers could otherwise rule differently, and each
falls out of §2 without a special rule. They are stated anyway, because a rule
whose consequences nobody wrote down is a rule two readers will apply twice.

**A node inserted directly into the solution section, never moved.** Not a
crossing. It has no crossing, it carries no reason in any projection, and that is
correct and not a gap. It was born where it is; there was no assumption that
carried it anywhere, because it never was anywhere else. The `--why` of its
`insert` says what it is for, and `bin/canvas history` is the one command that
prints it — which is `product-spec.md:53`'s own arrangement: *"It holds the
current answer, not the path to it. The path is in the history, one command
away."*

This is the normal case and not a corner. Every one of the eleven nodes in the
worked example is in it. A ruling under which the only canvas that has ever had
the shape shows nothing is a ruling that has to be able to say so plainly, and
this one does: that canvas is a correct canvas, it has no crossings, and a page
of it carries no reasons. What it shows a reader is two titled spaces with the
right things under them, which is most of what the shape was for.

**A node moved between two sections, neither of which is a solution space.** A
crossing, and its reason is shown. This is deliberate and is the direct
consequence of never reading the title: the mechanism cannot tell a "Problem
space → Solution space" move from an "Evidence → Appendix" move, and it is not
supposed to. What the two moves have in common is the thing the rule is keyed
on — a person decided this node belongs somewhere else and had to say why. If the
reason says *"this is background now, not evidence"*, then the page says that,
and the page is right. Refusing to show it would require the rule to know which
sections are which, which is §1.

**A canvas with no sections at all.** No node has a `<section>` ancestor, `S` is
*none* everywhere and in every document, and no `move` can change it. **No
crossing is expressible**, no reason is shown, and nothing is wrong. Sixty-one of
the 62 canvases in the live store on 2026-09-28 are in this state. A canvas is
not required to have spaces, and this ruling introduces no pressure on it to
grow them: a canvas with no sections renders exactly as it renders today.

**A canvas whose sections are titled something other than "Problem space" and
"Solution space".** Not a case. No rule here reads a title, so there is nothing
for a title to be wrong for. A canvas with sections titled `Symptoms` and
`Fixes`, or `Before` and `After`, or `A` and `B`, gets crossings and reasons on
exactly the same terms. This is the property that makes the ruling survive the
second person who invents the shape without having read the first one.

**A node moved more than once.** Each `move` is tested on its own by §2, so a
node may have several crossings in its history. **Its crossing is the latest
one**, and that is the single reason shown. The earlier ones are the path, and
the path is in `bin/canvas history`, oldest first, spanning every move
(`engineering-spec.md:218`). The latest is chosen and not the first because a
canvas holds the current answer: the node is where it is now, and the assumption
a reader needs is the one that put it there, not the one that put it somewhere it
has since left. A node that crossed into the solution space, was pulled back to
the problem space, and crossed again shows the third reason — and if the second
and third matter, they matter to somebody asking *why*, which is the history's
question and not the page's.

**A node that moved more than once and ended where it began.** Still crossed, by
§2, and the reason shown is the last move's. `S(after) ≠ S(before)` is evaluated
per edit and never against the node's birthplace, so a round trip is two
crossings and not zero. That is right: the reason a person gave for putting it
back is a reason, and a rule that cancelled it would be a rule that decides,
quietly, that returning a node to where it started was not a decision.

**A node carried by a `move` of its container.** Not a crossing — of the child.
`node-identity.md` §5 rules that a `move` on a container is one node and that the
subtree travels untouched; no commit names the children, their `v` does not bump,
and their history does not record the edit at all. So a child's nearest
`<section>` ancestor can change with no edit of its own, and §2 finds nothing
because §2 only ever examines edits in the node's own history. The container
crossed; the container carries the reason; the children carry none. This is the
right answer and not a limitation: one `--why` was written, one node was named,
and one reason is shown. A rule that propagated the container's reason down to
every descendant would print one sentence N times and would attribute to each
child a decision that was made about the group.

**A node moved within one section — a reorder.** Not a crossing. `S(after) =
S(before)`, so §2 returns false and no reason is shown. Order inside a section is
presentation of the author's own making; a reason like *"put the measurement
above the diagram it explains"* is real and worth keeping, and keeping it in the
history is where it belongs.

**The first commit in a canvas.** It has no parent, so `E.sha^` does not resolve.
It is also a `create`, which names no node at all (`canvas/store.py`: the root
commit carries no `Canvas-Node:`), so no node's history contains it and §2 never
reaches step 2 for it. Nothing to rule; noted so that an implementer who hits the
missing parent knows it is unreachable rather than unhandled.

## 4. What a projection shows, and the bound on it

The bound, stated as the thing a test asserts:

- **Every crossed node carries exactly one reason**, and it is the `--why` of its
  crossing, reproduced verbatim.
- **No node carries more than one reason.**
- **A node that has not crossed carries no reason.** It follows that a canvas
  with no crossings renders with no reason in it.
- **Every reason shown is accompanied by the full sha of the commit it came
  from.**

Everything else is presentation and belongs to `canvas/render.py`: where on the
node the reason sits, what introduces it, whether it is a `<p>` or a `<figcaption>`
or a bullet, the wording of any label, the CSS, and whether the sha is a link.
`engineering-spec.md`'s *The substrate* already gives the renderer all of those —
*"It owns every presentation decision"* — and `rendering.md` makes the same split
for the question index, which is the precedent this follows.

**Both projections, one claim.** The bound is identical for `--format page` and
`--format comment`. Not because the two look alike — they do not, and the comment
projection may emit no `<` at all — but for the reason `canvas/render.py` already
gives about the index: a reader who has one projection and then the other must
not have to work out whether they are the same claim. *Which* reasons appear is
the claim; how they are drawn is not.

**The sha is required, and it is required for the same reason the page's own sha
is.** `canvas/render.py`'s `page` carries the head sha in full for a stated reason —
*"A rendered page outlives the canvas it came from"* — and the sha is the only
thing that tells a reader which of the two they hold. A reason shown on a page is a
quotation from a commit message, and `guidelines/canvas-why.md` in
`malkovro/ledger-orchestrator` is explicit about what a citation owes a reader:
*"Name something a reader can resolve without already knowing the answer."* A
reason with its sha beside it is resolvable — `git show <sha>` in the canvas
directory — by someone who has the pasted page and nothing else. A reason without
one is a sentence in quotation marks that nobody can get back to.

**Verbatim, and not truncated.** The reason is reproduced as it was written,
escaped for the transport and otherwise unaltered. No ellipsis, no first
sentence, no summary. `guidelines/canvas-why.md` again: *"Quote verbatim, or do
not use quotation marks. They are an invitation to go and find the sentence. A
paraphrase inside them costs a reader their trust in everything else the reason
names."* A renderer that shortened a long reason would be editing a person's
words under their sha, and it would be making a judgement about which half
mattered — which is exactly the quiet decision this document exists to avoid
making by accident. The cost of that is real and is stated in *What this costs*.

## 5. Why one reason and not all of them

**Because the alternative is the transcript the product spec refuses.**
`product-spec.md:52-53` states it twice in two bullets: *"A wiki accumulates. A
canvas resolves"*, and *"Not a transcript or a summary of one. It holds the
current answer, not the path to it. The path is in the history, one command away,
marked dead."* Every reason on every node *is* the path — it is `git log` with a
stylesheet. A page built that way would grow monotonically with the number of
edits, which is the defining property of the wiki the first bullet refuses, and
it would do it while the document it projects stayed the same size.

**Because the budget is a hard number and this projection goes in every prompt.**
`product-spec.md:133` settles it at 20,000 characters of the canvas as
`bin/canvas read` prints it. A canvas near that budget with a long edit history
would, under an unbounded rule, render several times its own size. The document
is the thing the budget was measured on; a projection that multiplies it defeats
the measurement without anyone noticing, because nothing counts the projection.

**Because a bound of one is the only bound that is not a taste.** The candidates
were: all reasons; the last N; the reasons since some marker; the reasons that
"look substantive". The first is ruled out above. The middle two put a number or
a threshold in the renderer that nothing in either spec can argue for, and
`node-state.md` already refused a value set whose members nobody could enumerate
in advance — *"a one-member value set cannot be a taxonomy that falls
through"*. The last is a renderer grading prose, which is not something a test
can assert and not something two readers rule the same way. One reason, on
exactly the nodes that have a crossing, is checkable by counting: count the
crossings, count the reasons, and the page is either right or wrong. That is
`rendering.md` §2's own standard — *"An index built by omission cannot be checked
against anything"* — applied to the same page in the same way.

**Because it tells a writer which sentence gets read.** Today a `--why` is
written into a log that a person reaches only by running a command, and the
measured result is `docs/why-verdict/maintenance-check.md` §1.2: seventeen
identical reasons in one canvas. A rule that says *the reason on your `move` is
the one sentence a person will see on the page* puts one `--why` in front of a
reader by default, and it says in advance which one. That is a pressure on the
reason's quality that no schema could apply, and it is applied to exactly the
edit where the repository already says the meaning lives — `node-identity.md` §7
puts the pointer across a merge or a split *"in the `--why` of the edit that made
it"*, and this is the same arrangement for the same kind of fact.

**And because showing a reason at all needs an argument, which is this.** The
page is a projection of the canvas; a reason is not in the canvas, it is in the
log. `node-state.md` §3's distinction — the document is not the log — is what
makes `answered="true"` narrow, and it could be read as forbidding the log from
reaching the page at all. It does not, and the page already disproves it: the
render sha in the header is log data, put there for a stated reason. What §3
forbids is the *document* carrying a second kind of state. A projection reading a
bounded, stated slice of the log adds nothing to the document, and the bound is
what keeps "a slice" from becoming "the log". Widen the bound and the argument
stops holding, which is why the bound is the ruling and not a default.

## What this costs, stated honestly

- **The renderer's input widens from one read to a read plus a walk of the
  log.** `canvas/render.py` today calls `store.read` once and nothing else; under
  this ruling it must also, for each node, find the crossings in that node's
  history and read two documents per `move`. That is more git than a projection
  has ever done, it makes rendering O(moves) subprocesses rather than O(1), and
  it means a render can now fail in ways a read cannot — a shallow clone, a
  rewritten history, a commit whose parent is gone. The mitigation is that moves
  are rare: there are zero in the live store. The cost is real and it is the
  price of the reason being in the log, which is where every other ruling in this
  repository put it.

- **A reason shown on a page can go stale, and nothing checks it.** This is the
  same tension `node-state.md` records for `answered="true"` and the same one
  `engineering-spec.md`'s *Between the canvas and reality* declines to solve: the
  assumption that carried a node across may have been falsified an hour later,
  and the page will still print it under its sha. The defence is thinner here
  than there, because a crossing's reason is not re-asserted by any later commit
  the way an answered question's marker sits in the current document. What the
  sha buys is that a reader can date it. That is a mitigation and not a fix.

- **A long `--why` is printed in full and there is no cap.** A four-hundred-word
  reason on a crossed node is four hundred words on the page and in the Basecamp
  comment. Refusing to truncate is argued in §4; the cost of that argument is
  paid here, and it is unbounded in the one dimension the count bound does not
  cover. If it bites, the fix is a shorter `--why`, and the place to argue
  otherwise is this paragraph.

- **The container case will surprise someone.** A person who moves a `<section>`
  from one place to another, having written a careful reason, will see it once —
  on the section — and not on the six nodes inside it that a reader is actually
  looking at. That is correct by `node-identity.md` §5 and it will still read as
  a gap. It is recorded here so that the next person to hit it finds it ruled
  rather than unnoticed.

- **Nothing here makes the shape happen.** This document says what the shape
  means when it is there. It does not teach an agent to build it, does not
  require any step to write to a canvas — settled 2026-09-23 and not reopened —
  and does not make a sectionless canvas defective. If no canvas ever grows a
  second section, every rule above is true and inert.

## What this makes deliberate, and what stays free to change

### Deliberate — a later change may not rewrite these without reopening this document

- **A crossing is a `move` that changed the node's nearest `<section>`
  ancestor**, with *no section* as one of the values. Not an `insert`, not a
  `replace`, not a reorder, not a container's move seen from a child.
- **No rule, test, renderer or tool reads the characters of a `title`.** Which
  section is the problem space and which is the solution space is the person's
  reading of their own heading, and the document does not assert it.
- **A node's crossing is the latest one**, and the reason shown is that one.
- **Exactly one reason per crossed node, none on any other node, and the full sha
  beside it.** These four claims — one per crossed node, never two, none
  elsewhere, always the sha — are what a test asserts, on both projections, on a
  canvas with crossings and on one with none.
- **The reason is reproduced verbatim.** No truncation, no summary, no ellipsis.
- **No element, attribute or configuration file was added to serve any of this**,
  and none may be. A later change that needs one has found the tripwire.

### Free to change — implementation choices, not decisions

- **Where the reason appears on the node, and everything about how it looks.**
  Above the node, below it, in a `<details>`, as a caption, as a dimmed line; the
  label wording, if there is one; the CSS; whether the sha is abbreviated in the
  display while the full one is in the markup. All `canvas/render.py`'s, on
  `engineering-spec.md`'s *The substrate*'s terms.
- **How the crossings are computed.** Two `git show`s per move, one `git log -p`,
  a cache, or a cheaper comparison somebody thinks of later. What must not change
  is the answer.
- **Whether `bin/canvas history` gains a way to print the crossings of one
  node**, or `bin/canvas read` a way to name them. Both are conveniences over the
  same computation and neither is a decision.
- **The file this ruling lives in and its name.** It is one document because the
  second ruling is stated in terms of the first; if they ever stop being coupled
  they can be split.

### Known tensions — unresolved, recorded

- **The worked example is a model of structure and an anti-model of reasons.**
  §5 leans on `docs/why-verdict/maintenance-check.md` §1.2 to argue that showing
  one reason improves reasons. It could as easily do nothing: the seventeen
  identical strings were written by a batch writer that would have written them
  the same way had it known a page would show one. Nothing here tests that, and
  the first canvas with a real crossing is the evidence.

- **`rendering.md` decided what a renderer may settle for itself and this
  document widens it.** `rendering.md` says it decides *"the two questions
  `bin/canvas render` could not inherit from anywhere"* and that everything else
  about the page is an ordinary presentation choice. This is a third question of
  the same kind, ruled in a different file. The two documents do not contradict
  each other, but a reader who finds only `rendering.md` will believe the
  renderer's non-presentation commitments are two and they are now three.
  Whoever next edits `rendering.md` should say so there.

- **`canvas/render.py`'s docstring already cites a `rendering.md` §3 that does
  not exist.** It reads *"the three claims `rendering.md` §3 says are not free"*,
  and `rendering.md` has a §1 and a §2; the claims meant are §2's. Found while
  reading for this ruling, unrelated to it, and left alone rather than fixed in
  passing — noted so the next reader of either file does not spend the same
  minute on it.

## Still open

- **Whether an agent should be taught to build the shape**, and by what words in
  `skills/canvas/SKILL.md`. This document defines what the shape means, which is
  the half that had to be settled before the teaching could be written without
  inventing a rule. **Written 2026-09-28, on this branch.**
  `skills/canvas/SKILL.md`'s *The shape over time* states the lifecycle and
  restates §2's definition of a crossing in §2's terms rather than paraphrasing
  it, and *Worked: the reason on a `move` that carries a node across* sits
  beside that file's existing `--why` section. It teaches the shape as the
  default way a canvas ends as an answer and says in as many words that none of
  it is asked of a step, which is the *Genuinely open* item
  `product-spec.md:132` settled on 2026-09-23. Whether agents then build it
  unprompted is a post-ship observation about later runs and is not something
  this branch can check.

- **Whether a crossing should be visible in `bin/canvas read`**, which is what
  goes into a step's prompt. The projections are ruled above; `read` prints the
  document and is not a projection. A step reading a canvas therefore cannot see
  that anything crossed. That may be exactly right — the prompt carries the
  current answer — or it may be the most valuable place of all to show one line.
  Undecided, and deliberately not decided by a renderer.

- **What happens to a crossing's reason when the node is later `replace`d into
  something else.** The crossing stands, the reason stands, and the text under it
  is new. Whether that reads as a stale caption or as the useful fact that this
  node arrived here for a reason that outlived its wording is not something this
  ruling can settle from zero examples.
