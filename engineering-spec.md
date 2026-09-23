# The canvas

A specification. Nothing here is built yet.

## What it is

**The ledger is the projection of a task's lifecycle. The canvas is the
projection of its content.**

A task's ledger row answers *where is this* — framed, executing, blocked, done —
and refuses to answer it dishonestly. It says nothing about *what we decided*,
and it cannot: that lives in a Basecamp comment thread, in a conversation
transcript, and in whatever the last agent happened to remember. Three stores,
no shared key, and "what did we agree" is a join nobody can perform. That is the
same shape as the problem the ledger row was built to solve, one axis over.

The canvas is a small structured document, one per task, holding the current
shared understanding of the work: what the problem is, what we decided, what is
still open, what we ruled out and why. Both a person and an agent read it and
write to it. It is edited a node at a time, never rewritten, and every edit
carries the reason for it.

It is a blackboard: the thing two colleagues stand in front of, that shows the
state of the world as both of them currently hold it.

## Why it exists

| failure | the fix |
|---|---|
| a position agreed at turn 40 was silently re-litigated at turn 90, because the transcript states the old one with equal confidence | the canvas is the current state and the transcript is the history of how it got there; a step is given the canvas, not the conversation |
| an agent asked to change one thing rewrote the whole document and erased what a human had edited by hand | an edit names one node and touches one node; a write that would touch two is refused |
| a decision reversed itself three weeks later because the reason it was taken in the first place was nowhere | every edit requires a reason, and a node's reasons are its history |
| "what is the state of this task" meant reading a Basecamp thread of twenty comments in posting order | one document, current, rendered |
| an agent working from a five-minute-old read overwrote an edit made in between | an edit declares the version it was decided against, and is refused if that node moved |
| doubt had no representation, so the model resolved it on its own and told nobody | an open question is a node like any other, and it sits on the board until something replaces it |

## Identity and scope

**One canvas per ledger row.** Not per run, not per step.

- `ledger row` — the task. One file per task; the only surface that joins across
  stores; the only thing that reports to Basecamp.
- `run` — one execution of a plan for that row. A row can have several,
  including ones that died.
- `step` — a prompt inside a run.

The canvas has to survive a run that dies and accumulate across the second and
third attempt at the same task. If it belonged to the run, every restart would
lose the shared picture — which is the exact thing it exists to stop. Runs and
steps are *writers*; they never own it.

    $OPENCLAW_WORKSPACE/state/canvas/<ledger_id>.xml

next to `state/ledger/<ledger_id>.json`. One fact, one place, joined on read.

## The substrate

**XML with a closed vocabulary, rendered to HTML.** Not HTML directly.

HTML is an open substrate: an agent asked to edit one will reach for a `<div>`,
then a class, then a style attribute, and within a week the document holds
layout decisions and the diff of a content change is unreadable. A closed
vocabulary makes the constraint a schema instead of a rule somebody has to
remember — and a schema violation is an exit code, not a code review.

The renderer is a separate, dumb, one-way function: XML in, HTML out. It owns
every presentation decision. Nothing in the canvas file is about how it looks.
Nobody edits the HTML; it is a projection and it is regenerated.

**Pandoc's AST was considered as the substrate and rejected.** Its `Block` type
is almost exactly this vocabulary, several of its constructors already carry an
`id`, and `pandoc` would be a free renderer to both HTML and the plain text a
prompt wants. Three things sink it. `Para` — the most common node here — has no
attribute slot at all, so every paragraph would have to be wrapped in a `Div`
just to hold an id. The stored form is deeply nested JSON that no person edits
by hand and no diff reads, which kills the blackboard. And the block list is
open enough to admit `RawBlock`, which is the HTML problem again wearing a
different hat. It stays a good idea for the *renderer* if `<figure>` ever gets
ambitious, and a good reference for the vocabulary. It is not the file.

### The node vocabulary

Deliberately tiny, deliberately generic.

| node | holds |
|---|---|
| `<canvas>` | root; carries `ledger` and the schema version |
| `<section>` | the only container; carries `title`; nests one level |
| `<text>` | a paragraph |
| `<list>` / `<item>` | bullets |
| `<table>` / `<row>` / `<cell>` | anything with two or more columns, including a comparison of options |
| `<figure>` | a diagram: inline SVG, or a textual source the renderer draws |
| `<link>` | a pointer out: a PR, a file and line, a Basecamp todo, a run id |
| `<question>` | something open |

Every node except the root carries `id` (stable for the life of the node) and
`v` (bumped on every edit to it).

**The one thing to watch here.** A closed list of node types is itself a
topology, and topologies fall through the moment a case appears that nobody
anticipated — the same failure this repo already has in its handling of step
failures, where each new kind of failure needed a new category and the
categorisation kept missing. The defence is that this vocabulary is *structural*
and not *semantic*: `table`, `text`, `list` describe shape, and shape does not
run out. The moment somebody proposes `<decision>`, `<risk>` or
`<acceptance-criterion>`, the taxonomy has started growing and it will not stop.

`<question>` is the one semantic node, and it is the one exception worth
arguing for: an open question has to be findable — the renderer has to make it
loud, and an agent has to be told not to quietly answer it — and that is not
derivable from shape. If it turns out to earn nothing, it folds back into
`<text open="true">`.

## Edits

Four verbs. No more.

    canvas replace <node-id> --why "..."      # new content, possibly a different node type
    canvas insert  --after <node-id> --why "..."
    canvas remove  <node-id> --why "..."
    canvas move    <node-id> --after <node-id> --why "..."

`--why` is required by all four and has no default.

**There is no `resolve`, no `collapse`, no `supersede`.** An options table
becoming a settled decision is `replace` on the table node, with the new node
being a `<text>`, and `--why "chose A over B: B needs a migration we are not
paying for this cycle"`. The semantics live in the reason, where they can be
anything, and not in a verb name, where they can only be what somebody thought
of in advance. A verb per kind of intent is how you get eleven verbs and a
twelfth case that fits none of them.

**One edit is one node.** A command that would touch two nodes is refused. This
is the mechanical form of "do not rewrite the document": the tool cannot express
a full rewrite, so no amount of drift produces one.

**Where that is enforced, and what it binds.** Not in the argument parser. The
store compares the document it is about to write against the document already on
disk and refuses unless exactly the node named in the commit's `Canvas-Node:`
trailer is the one that differs — same type, same attributes, same character
data, same parent and the same sibling order for every other node. The rule is
therefore a property of the write path and not of a command line, in the same
place and for the same reason as the required reason: a caller that never goes
near the CLI is bound by it exactly as hard.

**The supported write surface is five functions**, and `create`, `insert`,
`replace`, `remove` and `move` are all of them. Each takes a ledger id, a
reason, and at most one node id. **None of them takes a document.** That is the
load-bearing absence: a function that accepts a whole tree is a whole-document
rewrite whatever it is called, so the parameter is not offered, the one private
function that has it is guarded anyway, and there is no file-level route, no
stdin, no patch and no import path that reaches around either. The single write
that names no node is the birth of a canvas, and the only document it may
produce is the root alone.

**The node that has children is the case that decides this**, and
[node identity](node-identity.md) section 5 settles it in full: what `replace`,
`remove`, `move` and `insert` each do to a container and its subtree, which of
them are refused while the container has children, and why a container that
travels with its subtree is still one node's edit while a payload that rewrote
that subtree is not. A reader can predict the tool's behaviour from that section
without opening the code, which is the point of writing it there.

**On IWE's `expect` guard.** IWE is the only shipped tool that makes "touch one
thing" enforceable: every operation declares how many nodes it should match, and
a mismatch fails with the count, every node that matched, and what to narrow.
This spec does not need the flag, and the reason is worth writing down —
addressing here is by explicit node id, so a selector can never match two. That
is the same property bought more cheaply, and it is the argument against ever
adding selector-based addressing: the day `canvas replace --matching "the
caching section"` exists, `--expect` has to exist beside it. What is worth
copying unconditionally is IWE's *error surface*. A refusal names every node it
matched and how to narrow, because an agent can act on that and cannot act on
the word "refused".

## The timeline

The canvas directory is a git repository, and **one edit is one commit**.

    replace b7: chose A over B: B needs a migration we are not paying for

    Canvas-Node: b7
    Canvas-Author: leo | step:implement | run:ship-the-flag-3
    Canvas-Base: 4f1a2c9

This buys, for no new machinery: the full history, the diff of any edit, blame,
revert, and — because a commit touches exactly one node and names it — the
history of a single node. That last one is what makes the discipline usable in
practice: before changing a node, an agent can ask what that node's current text
was *for*, and either honour that reason or explicitly retire it. It is one
command:

    $ canvas history my-task b7
    Canvas-Node: b7

    Canvas-Commit: 31499cf2d88f070dcd9f3fc7914c1e801e17d209
    Canvas-Author: leo | by-hand
    insert: the options this decision is between

    Canvas-Commit: e29e76568379c9720c8ef2f7af59774122612c10
    Canvas-Author: leo | step:implement | run:ship-the-flag-3
    replace: chose A over B: B needs a migration we are not paying for

Oldest first, and spanning a `move`, because a move keeps the node's id. The
obvious `git log --grep='Canvas-Node: b7'` is the same query written as a
substring match, and it is wrong in two reachable ways: ids are short, so it
also answers for `b7pk`, and a reason that quotes the trailer text is counted as
an edit to a node it never touched. The command matches the trailer's value for
equality instead.

A superseded options table is not deleted from anywhere. It is out of the
current document, in the history, and one command away. The canvas stays small
because resolution is routine, not because anybody prunes.

The alternative — an append-only record log in the style the orchestrator
already uses everywhere — is a real option and closer to the house grain. It is
rejected here only because git already exists, already does all of it, and the
one thing the log would do better (exact node addressing instead of
commit-message convention) is bought by the one-node-per-commit rule anyway.

## Staleness

Every read of the canvas returns the current commit sha. Every write declares
the sha it was decided against:

    canvas replace b7 --base 4f1a2c9 --why "..."

- **The node moved since `--base`** → hard refusal. The tool exits non-zero and
  prints that node's diff since `--base`. The writer re-reads and re-decides.
  Nothing is applied and nothing is merged.
- **Something else moved since `--base`** → the write applies, and the tool's
  output carries the diff of everything that changed in between. The writer is
  told, in the same breath as being told it succeeded, what it did not know.

That second case is the one the person asked for: an agent that pulled the
canvas ten minutes ago and has not seen the two blocks edited by hand since gets
told so, by the write path, every time.

These two branches are not new. Google Docs has shipped exactly this split
since 2018 — `requiredRevisionId` for the hard refusal, `targetRevisionId` for
"apply against whatever landed" — and borrowing the semantics, and the fact that
they are two separate things a caller chooses between, costs nothing. What is
not in Google's version, and is the whole point of this one, is that both
branches hand back the diff.

This is deliberately not CRDTs or operational transform. One person plus
serialized agents, node-granular edits, and a cheap refusal is enough; merge
algebra is not. CRDTs are in fact the wrong shape twice over: they auto-merge
and therefore never refuse, and the refusal is the feature.

## Coherence

Two different problems wear this name and only one is cheap.

**Inside the canvas** — node 4 now says writes are synchronous, node 9 still
says the queue absorbs write bursts. This is a reading problem on a small
document, and a model does it well. It belongs *in the canvas tool*, not as an
orchestration step: after a write, the tool can ask a model whether the edit
contradicts any other node, or any other node's recorded reason.

The output of that check is written **as a `<question>` node in the canvas
itself**. Not a log line, not a warning on stderr that scrolls past. It lands on
the blackboard, where the whole point is that you will see it. No new concept is
needed to carry it.

**Between the canvas and reality** — the canvas says we chose A; the branch
implements B. No amount of reading the canvas catches this, and it is the more
dangerous of the two precisely because the canvas is what a person will use to
spy on progress and to steer. **This specification does not solve it.** The
mitigation is convention only: an edit whose reason is a fact about the world
should name its evidence in `--why` — a PR, a verdict, a file and line — and a
reader can follow it. Nothing enforces that. A state field distinguishing what
was asserted from what was verified was considered and rejected as premature;
if canvas-versus-reality drift turns out to bite, this is where it will be
fixed, and it should be fixed with evidence in the reason before it is fixed
with a new attribute.

## The canvas as input

Today a step's prompt carries the Basecamp task. The end state is that it
carries the canvas instead: the rendered current document, plus the last N
edits with their reasons, plus the current sha to write against.

This is the canvas's highest-value use and its hardest constraint. It means:

- **A size budget that has nothing to do with human readability.** The canvas
  goes into every step's prompt, so it is bounded by what is affordable to send
  every time, not by what fits on a screen. Resolution is not tidiness; it is
  the mechanism that keeps this affordable.
- **A badly maintained canvas actively misleads every worker**, rather than
  merely being a stale document nobody reads. This is the cost of giving it
  authority, and it is the reason authority has to be earned by the write path
  being disciplined rather than granted by a line in a prompt.
- **Decoupling from Basecamp.** Basecamp stops being an input and becomes one
  more projection: the ledger row's comment carries the rendered canvas. One
  author still writes to Basecamp — the row — and the canvas does not become a
  sixth voice posting its own comments.

## Projections

All one-way. A projection is never edited and never read back.

1. **HTML** — the renderer's output. Shareable as a file, viewable in a browser,
   pasteable into a Basecamp comment.
2. **The ledger row's Basecamp comment** — the rendered canvas, rewritten in
   place on change, by the row, as it already rewrites everything else.
3. **`watch-runs-web`** — a canvas tab, alongside the run list.

## The write path, and one honest problem

`watch-runs-web` states, in its own docstring, that it reads and never writes.
That invariant is load-bearing: it is why the page cannot disagree with the
sweep about what is true.

Making the canvas editable in that page makes it a writer. The way to keep the
invariant honest rather than quietly false:

- The page never touches a canvas file. An edit in the browser POSTs to the
  canvas tool, which stays the single writer, applies the same four verbs, the
  same required reason, and the same `--base` refusal an agent gets.
- The docstring changes to say what is now true. The thing this repo does not do
  is leave a claim standing that the code no longer honours.
- A browser edit is authored as the person, not as the tool. `Canvas-Author:
  leo`. That is the whole of the write asymmetry: there is none, and provenance
  is what makes that safe.

## Lifecycle

- **Born at `open`.** The ledger's `open` already requires `--problem` and
  `--expected-value`; those become the canvas's first two nodes, and the canvas
  exists from the moment the task does.
- **Grows through `executing`.** Runs and steps write to it; the person writes
  to it; it resolves as it goes.
- **Frozen at `done`.** The `done` gate already demands a structured
  What/Why/Evidence/Verification/Links artifact. That artifact is a projection
  of the canvas, and after it the canvas is read-only history.
- **Never deleted.** `abandoned` freezes it the same way, with the reason as the
  last edit.

## Does this already exist

Surveyed 2026-09-21, across agent/human canvas products, block-addressable
document stores, structured-editing stacks, agent-facing patch-edit protocols,
spec-driven-development tooling, and post-2023 blackboard implementations.

**Nothing has all three of the load-bearing properties.** The base-version
refusal is solved twice and solved well. Single-node editing is served once, and
by nobody as an *inexpressible* rewrite. A mandatory reason per edit is
implemented essentially nowhere.

The instructive finding: three separate 2026 projects — GravityKit's
`block-mcp`, GitHub Next's `chopin`, and Claude Docs — each built a correct
base-version check and then shipped a whole-document rewrite verb next to it.
`chopin` states the anti-pattern in one signature: `update_document(id,
revision, plan: full replacement MDX source)`. Making the rewrite unavailable is
the part everybody skips.

| | what it gives | what is missing |
|---|---|---|
| **Claude Docs** (Anthropic, beta, 2026-09-16) | the closest thing that exists: per-block ids and content hashes, a mandatory `ifHash` guard on any block you did not write, a hard refusal that hands back the block as it now stands, `sinceRev` incremental reads, and symmetric human/agent writes with an explicit policy that the human's words win | no reason field anywhere; a whole-tab `restore`; and it is **hosted, with no API, no self-host, no filesystem path and no git**. Mechanics here were read from the live server's own guides, not from documentation — undocumented beta, may change without notice |
| **Google Docs `WriteControl`** | the cleanest published base-version design in existence, stable since 2018, with both branches separated | character-index ranges rather than node identity — and indexes actively push an agent toward delete-and-rewrite; no reason; the refusal returns no diff; revision ids expire in 24h |
| **Notion** | block ids and a block-level API | **no concurrency control at all** — no ETag, no `If-Match`, no version field, documented last-write-wins. And in 2026 Notion moved *away* from block edits for agents, shipping a markdown `replace_content` endpoint and pointing its own MCP server at that instead |
| **OpenAI Canvas** | — | **dead**, pulled 2026-05-28. Its update tool took a Python regex over the whole document, with the system prompt instructing `.*` as the default. Recorded here as the anti-pattern so nobody proposes it again |
| **Anytype API v2** (local HTTP, pre-release) | a closed op set, an explicit refusal to accept whole-document writes, and the single best datapoint in the survey: **it deleted its `replaceBlock` op because small models used it to silently wipe content** | `If-Match` is advisory and document-level — "without the header, last write wins" — and a guard an agent can omit is not a guard; no reason; needs a GUI desktop app running to serve a headless CLI |
| **IWE** (Rust, local markdown, CLI + MCP) | the best shipped answer to "stop an agent touching two things": a mandatory `expect` target count on every op, strict always on, and an error that prints the count, every match and the fix | no base-version check, no reason, free-form markdown |
| **en-quire** (MIT, MCP over a markdown directory) | the closest architectural sibling: git-native governance, propose-branch-and-merge, and **per-section history via `git log -L`** | it addresses sections by heading text and derives history from line ranges, so a restructure breaks addressing *and* misattributes history; conflict detection is deferred to merge rather than refused at write time; a root-level section replace is a whole-file rewrite |
| **doc-agent-mcp** (MIT, Python) | blocks with ids, propose→diff→apply, a document hash that fails a stale write | the hash is document-level, not node-level; no reason; v0.1.0 |
| **ADR tooling** | the reason-per-decision discipline and explicit supersession | `adr-tools` is archived and `log4brains` is in low-maintenance mode — deader than this row used to imply. One file per decision, no current-state view. The 2026 successors are tiny; one hosted decision log is the only write API found anywhere that makes a rationale **required** |
| **Markdown in git** | history, blame, diff, revert, zero infrastructure — and git already refuses an empty commit message, so the *enforcement* half of the reason is free | no node addressing, no write-time base-version refusal, no renderer, and nothing that stops a full rewrite |
| **Tana, Roam, Logseq** | real block-level addressing and references | **Tana's API is write-only** — there is no read access — so the canvas could never be read back into a prompt, which fails the property the whole design exists for. Roam is stagnant; Logseq's DB rewrite is still beta |
| **Automerge, Loro, Yjs** | correct concurrent editing; `diff(before, after)` is literally the second branch of the staleness rule, and Loro can attach a per-change message from Python today | CRDTs auto-merge and therefore never refuse, which deletes the property we want. `automerge-py` can read a change message but has no API to write one |
| **Magentic-One's task/progress ledger** | the canonical modern blackboard, and the one most likely to be cited at us | the anti-pattern: it lives in prompt context, has no ids and no versions, is regenerated wholesale on every outer loop, and has no human write path. Adopting it re-creates the problem |
| **Spec-driven tooling** (Spec Kit, Kiro, OpenSpec, BMAD, …) | the same thesis — the spec is the source of truth the agent works from | flat markdown, git for history, and whole-file rewrite as the *primary* revision mechanism. Nothing to reuse |

### Build, and build small

The adoptable candidates are all 2026-vintage, all under fifty stars, and each
is missing two of the three load-bearing properties. Taking a v0.0.0 dependency
for the store that holds a task's decisions is worse than a few hundred lines of
Python over git.

What the survey changes is not the decision but the *size* and the *emphasis*.
The reason is nearly free — git enforces it. The renderer is small. The
base-version refusal has two shipped designs to copy. The budget that frees up
belongs on the part that is genuinely unsolved.

**The genuinely hard parts are two, and neither is where this document put the
weight.** The first is node identity across a restructure, and en-quire is the
existence proof of what punting costs: address by heading text, derive history
from line ranges, and the first rename detaches a node from its own reasons —
which is the thing the discipline is *for*. The second is making the rewrite
inexpressible, where the evidence is that three funded 2026 projects tried and
stopped halfway.

## What to copy

1. **IWE's error surface.** A refusal names every node it matched and how to
   narrow. See *Edits* for why the `expect` flag itself is not needed here.
2. **Google Docs' `WriteControl` split** — two named behaviours a caller chooses
   between, not one conflated "handle conflicts" mode. See *Staleness*.
3. **Anytype's deleted `replaceBlock`** — as evidence, not code. Somebody else
   already ran the experiment behind *one edit is one node*, with evals, and
   removed a verb because models used it to wipe content. Cite it the next time
   a convenience verb is proposed.
4. **RFC 6902's `test` operation** — the idea, not the wire format. A per-path
   precondition that aborts the whole patch on mismatch is node-granular
   optimistic concurrency, standardised, and it is the shape `--base` should
   take if commit-granularity ever proves too coarse.
5. **Not Pandoc, for the file.** See *The substrate* for why, and for when it
   would still be the right renderer.

## The path

Each step is useful on its own. The risky one is last.

1. **`bin/canvas`** — XML file per ledger id, git-backed, four verbs, `--why`
   required, one node per commit, `--base` refusal. No renderer, no UI. Drive it
   by hand on one real task and find out whether the discipline survives contact.
   **And find out whether `--why` is worth anything.** No product in the market
   ships a mandatory reason field, so there is no evidence anywhere on whether a
   model writes a useful one or a tautology — "updated the node to reflect the
   change". Per-node history is the feature this entire design is built around
   and it rests on the one assumption nobody has tested. Read the first fifty
   reasons before starting step 2; if they are noise, the thing to fix is the
   prompt or the schema of `--why`, and it is much cheaper to find that out here.
2. **The renderer** — XML → HTML, static output, linked from the ledger row.
3. **The canvas in step prompts** — steps read it and write to it with their
   step id as author.
4. **A read-only tab in `watch-runs-web`.**
5. **Editing in that tab.**
6. **The coherence check**, emitting `<question>` nodes.

Steps 1–3 are the specification. 4–6 are the part that makes it pleasant, and
none of them are worth starting until 1 has been used on a real task long enough
to know whether a person actually keeps a canvas up to date when nothing forces
them to.

## Open

- **How a node's `id` survives a restructure — decided, remainder included.**
  The survey promoted this from a footnote to the hardest open item: ids have to
  be stable for history to mean anything, and a restructure is exactly when
  somebody will want to renumber; en-quire shipped without solving it and its
  history silently attaches to the wrong text the first time a heading is
  renamed. Minting, preservation under each of the four verbs, `v` bumping, and
  what happens to a container's children when the container is replaced,
  removed or moved are now settled in [node identity](node-identity.md), and so
  is **merge and split**, which was that document's remainder. Its section 7
  rules that a node's lineage is the set of commits naming its id and ends where
  that set ends: the tool records no ancestor and no successor, and the pointer
  across a merge or a split lives in the `--why` of the edit that made it. Its
  section 8 rules that a restructure is never atomic and that a grouping
  mechanism may aggregate commits that already exist but may never be the unit
  in which a write happens. Both were decided against the real merge and split
  in [docs/merge-and-split/](docs/merge-and-split/), whose transcript holds the
  `bin/canvas history` output for the surviving id and the stranded one. What is
  still open in that document is its third item, that nothing here ages.
- **Whether a model writes a useful `--why`.** Untested by anyone, because
  nobody ships a mandatory reason field. See step 1 of *The path*.
- Whether a step that writes to the canvas should have to, or whether an empty
  canvas after a run is a legitimate outcome that the sweep should notice.
- What the size budget actually is, once the canvas is in every prompt.
- Whether the renderer should draw `<figure>` from a textual source or only pass
  through inline SVG. Inline SVG diffs badly; a textual source needs a drawing
  step the canvas tool would have to own.
