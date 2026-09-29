---
name: canvas
description: >-
  Drive a Canvas — the small structured XML document that holds the current shared
  understanding of one task between a person and the agents working on it. A Canvas may
  stand alone or use an identifier supplied by a task-ledger integration. Use whenever
  you need to read what is already understood,
  record a decision or an open question, settle one, carry something from the problem
  space into the solution space, render the canvas for a person, or
  end it. Covers the whole safe workflow for `bin/canvas`: read first and carry the sha
  into `--base`, one node per edit, a `--why` a later reader can resolve, never
  editing the XML by hand, and the shape a canvas takes from the problem it opened as to
  the answer it ends as. Triggers on "canvas", "bin/canvas", `--why`, "the shared
  understanding of this task", "problem space", "solution space", a `Canvas-Base:` /
  `Canvas-Node:` / `Canvas-Frozen:` line, or a Canvas identifier.
allowed-tools: Bash, Read
---

# Canvas

A Canvas is **one XML file per Canvas identifier**, git-backed, holding what is currently
understood about a task: the problem, what is expected, the decisions taken, and the
questions still open. It works on its own; a ledger may optionally project the task's
*lifecycle* while the Canvas projects its *content*.

You own it. Nobody is going to run the CLI for you, and nobody is going to tidy it up
afterwards.

## The tool and where it lives

    CANVAS="${CANVAS_BIN:-$HOME/Projects/canvas/bin/canvas}"

`bin/canvas` is not on `PATH`. The ledger resolves it through `CANVAS_BIN`, defaulting to
`~/Projects/canvas/bin/canvas` (ledger-orchestrator `docs/canvas-home.md`), and you should
resolve it the same way rather than inventing a second convention.

`OPENCLAW_WORKSPACE` must be set: the store is `$OPENCLAW_WORKSPACE/state/canvas`, one git
repository holding every row's file. Unset, and every verb exits `2`.

Nine verbs, no tenth: `create`, `read`, `render`, `history`, `replace`, `insert`, `remove`,
`move`, `freeze`. `bin/canvas <verb> --help` is accurate and worth reading; this file is
about *when* and *in what order*, which `--help` does not say.

## Read the two exit codes before anything else

Every refusal prints a `Canvas-Exit:` line saying which of these it is. The split is the
whole point — it tells you whether to fix your edit or stop touching the canvas.

| exit | meaning | what you do |
|---|---|---|
| `0` | it worked | carry on |
| `1` | **your request is wrong against the store as it stands** — no Canvas for that identifier, no such node, the node you are writing moved since your `--base`, an unknown `--base` sha, the document is invalid | re-read and re-decide. The refusal names the node and hands you its diff |
| `2` | **the tool or its environment is wrong** — `OPENCLAW_WORKSPACE` unset or unusable, `git` or `xmllint` missing, a malformed Canvas identifier, an absent or empty `--why`, a `--base` that is not a sha | **do not touch the canvas.** Fix the environment or the invocation. Retrying the edit will not help |

A `1` is information about the task. A `2` is information about your machine. Do not
report a `2` as "the canvas refused my edit".

## The loop: read, decide, write against the sha you read

This is the only safe shape, and the staleness check is the reason the canvas can be
pasted into a prompt at all.

```bash
# 1. read — the first line is the sha you will write against
$CANVAS read <canvas-id>
# Canvas-Base: dd93708016b1eee07970a587147cab8ca7c6a5b8
# <?xml version="1.0" ...

# 2. decide

# 3. write ONE node, naming that sha
$CANVAS insert <canvas-id> --into root --type text \
  --text "..." \
  --why "..." \
  --base dd93708016b1eee07970a587147cab8ca7c6a5b8 \
  --author "<model> | <step-or-role>"
# Canvas-Node: c4kc
# Canvas-Base: 3204627ebceb9068d606ff5984c1d0d3797da974   <- the sha for your next write
```

Every write verb prints `Canvas-Node:` and the new `Canvas-Base:`. **Use that second line
as the `--base` of your next edit** instead of re-reading; re-reading between two of your
own edits just costs a subprocess.

### What `--base` actually does

- **The node you named moved since that sha** → hard refusal, exit `1`, nothing written,
  and you get that node's diff. Somebody changed the thing you were about to change.
  Re-read and re-decide; do not re-run the same edit with a fresher sha until you have
  read what they did.
- **Something else moved** → your edit is *applied*, and the news of what changed is
  printed on stdout beside the success. This is the soft branch. Read the news: you have
  just written against a document you had not fully seen.
- **`--base` omitted** → no check at all. That is not "base of now". Omitting it on a
  canvas that anything else might touch is how you overwrite somebody quietly. Pass it.

Comparison is scoped to this row's own file, so an edit to an unrelated row does not make
you stale.

## One edit is one node. A full rewrite is inexpressible.

`replace` takes one node id. `insert` mints one node. `remove` takes one out. `move`
changes one node's position and nothing else. There is no verb that rewrites the document,
and this is a design rule, not a missing feature.

So when the understanding changes:

- A sentence that is now **wrong** → `replace` that node. Its id survives, including
  across a type change: an options `<table>` settling into a `<text>` is the same node,
  and that is how a decision gets made in a canvas.
- Something **new** → `insert --after <node-id>` (same parent) or `--into <container-id>`
  (last child; `root` names the canvas itself).
- A question you have **answered** → `replace` it with `--type question --answered`, or
  replace it with the answer and say in `--why` that this node is where the question was.
  `answered="true"` is the only state any node may carry; `answered="false"` is invalid,
  absence means open.
- Something that should **never have been there** → `remove`. Its id is retired and never
  reminted; a node with children is refused.

### Never edit the XML file directly

Not with an editor, not with `sed`, not with a Python one-liner. The store is the single
writer: it mints ids, bumps `v`, validates against `schema/canvas.rng`, writes the
`Canvas-Author` trailer, enforces the reason and makes one commit per node. A hand edit
gets none of that, and `--base` staleness becomes meaningless the moment the file and the
log disagree. The one exception the tool itself names is XML so broken it will not parse —
and that is a repair, not an edit.

The vocabulary is closed: `canvas`, `section`, `text`, `list`, `item`, `table`, `row`,
`cell`, `figure`, `link`, `question`. Eleven, and no twelfth — there is no plugin point and
no config of allowed elements. `<section>` nests one level (two deep in total). `<link>`
requires `--href`, `<section>` requires `--title`.

## Figures

Use a `<figure>` when the spatial relationship is the understanding: a flow,
dependency, boundary, sequence of handoffs, or small topology that a reader can
grasp faster as a picture than as prose. A figure earns its node when it removes
real scanning or ambiguity. Do not draw one merely because several facts exist;
a short list or paragraph is cheaper, easier to edit, and clearer when order and
connection are not the point. Keep the figure small enough that its labels are
readable in the standalone page, and put conclusions or caveats that must be
searched as prose in a neighbouring `<text>` node.

For architecture, dependency, flow, sequence and other relationship diagrams,
use **Mermaid**. Write the source to a UTF-8 file and use the named CLI route:

```bash
$CANVAS insert my-canvas --into root --type figure \
  --mermaid-file ./architecture.mmd \
  --why "This node makes the request-to-review handoff and its direction scannable; retire it if the workflow becomes a single step." \
  --base "$canvas_base" --author "<model> | <step-or-role>"
```

That produces `<figure payload="mermaid">` containing escaped character data.
The standalone page progressively enhances it with a fixed, strictly configured
Mermaid module. Until that succeeds—and whenever JavaScript is disabled, the CDN
fails or the source is invalid—the readable source remains visible. Never place
HTML, scripts, event handlers or URLs in Mermaid source. The standalone renderer
refuses to pass URL-bearing source to Mermaid, checks returned SVG against a
static element-and-attribute allowlist before importing it, and keeps this source
fallback visible when either check rejects a drawing.

**Canvas Diagram 1** remains the backward-compatible meaning of an unmarked
figure. Use it for a small manually positioned grid when its in-process,
no-network drawing is specifically useful. It is explicit-grid, line-oriented
text stored directly in the `<figure>` with no `payload` attribute:

```text
box ID ROW COLUMN "label"
edge FROM -> TO "label"
edge FROM -- TO "label"
edge FROM -x TO "label"
text ROW COLUMN "label"
```

Ids begin with a lowercase letter and then use lowercase letters, digits, `_`
or `-`; rows and columns are positive integers up to 1000. Labels are quoted and may use
`\n` for an intentional line break. `->` is directed, `--` undirected and `-x`
blocked. Source order is paint order. Unknown or malformed statements remain
visible as diagnostic rows in the drawing rather than making a validated canvas
fail later at render time.

Create that compatibility form through the store, never by editing XML:

```bash
$CANVAS insert my-canvas --into root --type figure \
  --text 'box request 1 1 "Request"
box review 1 2 "Review"
edge request -> review "submit"' \
  --why "This node makes the request-to-review handoff and its direction scannable; retire it if the workflow becomes a single step." \
  --base "$canvas_base" --author "<model> | <step-or-role>"
```

The stored node is ordinary leaf character data, one of the same eleven element
names; the CLI escapes it when serialising:

```xml
<figure id="f2gx" v="1">box request 1 1 "Request"
box review 1 2 "Review"
edge request -&gt; review "submit"</figure>
```

Reserve inline SVG for a small, simple visual element Mermaid does not express
well—not for architecture or relationship diagrams:

```bash
$CANVAS insert my-canvas --into root --type figure --svg-file ./shape.svg \
  --why "This small visual geometry is not a relationship diagram Mermaid expresses clearly; retire it if the element can return to textual source." \
  --base "$canvas_base" --author "<model> | <step-or-role>"
```

That produces `<figure payload="svg">` containing escaped markup. The validator
admits only a bounded, inert SVG shape/text subset and refuses scripts, handlers,
styles, links, URLs, images, reuse, foreign objects, animation, entities and
foreign namespaces before the write commits. SVG is not the normal diagram format because a
small visual edit rewrites noisy markup inside one node and makes that node's
per-edit history much harder to read. The explicit `--svg-file` flag, the
`payload="svg"` marker, the closed validator, and this instruction are the guard:
pay the SVG history cost only for reviewed simple geometry, never as a shortcut
around Mermaid for architecture or relationships.

The standalone HTML projection draws all three forms. The Basecamp comment
projection cannot display the picture, so it labels and fences readable Canvas
Diagram 1 or Mermaid source, or entity-escaped SVG markup, and points the reader
to the standalone projection. That fallback is intentional; do not mistake it
for a failed render or paste raw SVG into the comment.

## `--why` is the field that makes the canvas worth reading

It is required, has no default, and lives in the commit subject and nowhere else.
`bin/canvas history <canvas-id> <node-id>` is how a later reader asks what a node is *for*.

**The bar:** could a reader, months later, reading only this reason, tell what the node
was for and decide whether to **honour** it or **explicitly retire** it.

The rule you are held to is maintained by Leo, in the **ledger-orchestrator** repository at
`guidelines/canvas-why.md` — on this machine `~/Projects/ledger-orchestrator/guidelines/canvas-why.md`.
**Read that file.** It carries `docs/why-verdict/VERDICT.md` §5.1 verbatim, and it is the
current text, which this paragraph is not. If you are running as an orchestrator step, its
whole text is already inlined in your prompt (`orchestrator/canvas.py::why_rule` reads it at
call time and hands it on unchanged), so you have it without opening anything.

In short, and not as a substitute for reading it:

- **Never point at another reason.** "as above", "as before", "same as", "same shape",
  "matching X" are not reasons — `canvas history` prints one node's edits and never the
  node you meant. If the justification is one you already gave for a sibling or a parent,
  name that node's four-character id and say what is **different** about this one: what it
  holds that the other does not, and what would retire this one and not the other.
  Part of this is *enforced*, not advised: `require_reason` in `canvas/store.py` refuses a
  reason containing any of seven phrases — `as above`, `as before`, `see above`,
  `same as above`, `same shape`, `ditto`, `as previously` — that names no other node's
  four-character id. Exit `2`, nothing written, nothing committed, nothing minted. The
  advisory half of the rule is wider than the enforced list, so passing the check is not
  the same as meeting the bar.
- **When the node holds nothing** — an empty `<table>`, a header `<cell>` — the reason is
  not about the element. Say what the structure is for, name the container's id, and say
  what would make this element wrong.
- **A claim about the world names its evidence**, and names something a reader can resolve
  without already knowing the answer: a path, a sha, a pull request, a titled section, an
  identifier they can grep for. "the launch brief", "the staleness check", "the ledger row"
  name a role, not an artifact.
- **Prefer a name to a line number** — of 54 real reasons checked for whether their
  evidence still resolved, every citation that was a name survived and both bare line
  numbers now point somewhere else (`docs/why-verdict/DRIFT-CHECK.md`).
- **Quote verbatim or drop the quotation marks.**

There is no required form, no `Evidence:` line, no length floor. For calibration: real
reasons that met the bar ran 151–975 characters; every one that failed was under 115.
That is a symptom, not a rule — do not pad.

### Worked: the reason on a `move` that carries a node across

A `move` between two `<section>`s is the one edit whose reason a reader gets without
asking for it — both projections print that reason under the node, verbatim, with its sha
(`problem-and-solution-space.md`, and *The shape over time* below). So it is the reason
worth the most care, and what it owes a reader is the **assumption**: the thing you
believed that made this node belong on the other side, and the thing that, if it turns out
to be false, puts it back.

**Good.**

    --why "Carries n4tz from the problem section czfj into the solution section jub8: we
    are taking the single-writer queue. The assumption that carries it is that nothing but
    the sweep writes to state/claims — every write in bin/claim-sync and
    orchestrator/sweep.py at 4f1a2c9 goes through claim_store.write. If a second writer
    appears, n4tz goes back under czfj and the option rejected in t8wm comes back with it."

It states the assumption as an assumption, in its own words; it names evidence a reader can
resolve without already knowing the answer — two paths and the sha they were true at,
rather than a role like *the sync path*; and it says what would retire it and what goes
back if it does. A reader who finds a second writer next month knows which node to move and
where to, and does not have to ask anybody what was believed.

**Bad.** `--why "moved to the solution space"` — it states where the node went, which the
heading above it already states, and names no assumption at all, so the one line a reader
is shown under that node tells them nothing they could not see and nothing they could ever
find false.

**Bad.** `--why "moved now that we agreed the second-writer worry was overblown"` — an
agreement is not an artifact: there is nothing named here that a reader can open, so they
cannot check whether the thing you assumed still holds, which is the one question a
crossing's reason exists to let them ask.

## `--author`

Say who you are, in the shape the tool already uses (`'<user> | by-hand'` is the default).
An agent working a step gives its model and its step or role:

    --author "claude-opus-5 | step:implement | run:ship-the-flag-3"

This matters beyond bookkeeping: the orchestrator's sweep calls a canvas **untouched** when
no step id of any run linked to that row appears as a `Canvas-Author` in its log — that is,
nothing that ran ever wrote to it. So what takes a row out of that state is a **step
authoring as its own step id**, which is exactly what the protocol in its prompt hands it.
An author that is not one of that row's step ids — a person, or an agent naming its model
and its role — is a real edit and a real trailer, and it is deliberately not one of the
writes that predicate counts: a person keeping a canvas up by hand does not make the runs'
silence something else.

It used to read *every* `Canvas-Author` is `task-ledger | open`. That was reversed in
ledger-orchestrator `docs/canvas-in-prompts.md` §2, which carries the argument and the
alternatives it rejected: a `create` that **failed** never writes `task-ledger | open` at
all, so a canvas made by hand afterwards could never be called untouched, however long its
row ran without a single step writing to it.

## When to do what over a Canvas's life

A Canvas opens as the problem, gains what the work learns while it runs, and ends as the
answer with the assumptions it rests on still stated. The verbs below are how each of
those happens; *The shape over time*, further down, is what the document looks like while
it does.

### `create` — standalone by default, explicit integration when needed

For a standalone Canvas, omit the identifier. The CLI mints a collision-safe identifier,
prints it as `Canvas-ID`, and uses it for the stored file and every later command:

    created="$($CANVAS create --problem "..." --expected-value "...")"
    printf '%s\n' "$created"
    canvas_id="$(printf '%s\n' "$created" | sed -n 's/^Canvas-ID: //p')"
    $CANVAS read "$canvas_id"

An integration that already has a stable identifier supplies it positionally, unchanged:

    $CANVAS create bc-10340467739-existing-task \
      --problem "..." --expected-value "..."

`bin/task-ledger open` uses that explicit form. If its automatic creation failed, the
row's live Basecamp comment says `canvas:failed` and stderr names the repair command.
`create` refuses to overwrite an existing Canvas (exit `1`).

**Neither may be blank.** An absent, empty or whitespace-only `--problem` or
`--expected-value` is exit `2` and writes nothing at all — no canvas, no commits, no
minted ids. A supplied identifier remains free to retry; with no supplied identifier,
none has yet been minted. For an integrated row carrying `canvas:failed`, retry the exact
explicit-id command with a problem and expected value that say what they hold.

### `read` — first thing in any step that touches the task

    $CANVAS read <canvas-id>                    # sha, then the whole document
    $CANVAS read <canvas-id> --id c4kc --id ezwq # those nodes and their subtrees
    $CANVAS read <canvas-id> --type question     # every question
    $CANVAS read <canvas-id> --provenance        # + who last wrote each node, and at which sha
    $CANVAS read <canvas-id> --frozen            # + has this canvas ended, and why
    $CANVAS read <canvas-id> --since <sha>       # + what changed since a sha you held

`read` writes nothing, commits nothing and locks nothing — the answer can be stale the
moment it prints. `--base` on the write is the only thing that refuses.

If a canvas arrived inline in your prompt, it came with the sha it was read at. You may
write against that sha directly; that is what it is there for.

### While the work runs — write when there is something to say, and not otherwise

**You are not required to write.** A canvas untouched by a step is a legitimate outcome and
the orchestrator says so in writing (ledger-orchestrator `docs/canvas-in-prompts.md` §2). A step forced to write
produces "I checked X", which is the run log's job, and produces exactly the reason the
`--why` rule exists to stop.

Write when the *shared understanding changed*:

- a decision was taken, and what it rules out
- a question opened that somebody has to answer
- a question was settled, and on what evidence
- something everybody believed turned out to be false

Do not write: progress, status, what you are about to do, or a summary of your own diff.
That is the ledger row and the run log.

### The shape over time — the problem it opened as, the answer it ends as

A Canvas is born as the problem: the two nodes `create` writes are the problem and the
expected value, and at that moment they are the whole document. It should end as the
answer — what is now believed, with the assumptions under it stated where a reader can
disagree with them. In between it gains what the work learns. A Canvas that only ever
accumulates paragraphs in the order they were written never got there, and a reader of it
cannot tell the problem you started with from what you now think.

You build that with what already exists and nothing else: `<section>`, where you put a
node, and `move`. There is no `<decision>` node, no `space=` attribute, no `status=`, and
no twelfth element — a step that finds itself wanting one has found the tripwire rather
than a gap.

```bash
# a second space, once the work has actually produced one
$CANVAS insert <canvas-id> --into root --type section --title "Solution space" \
  --why "..." --base "$canvas_base" --author "..."

# what you now believe, written where it belongs
$CANVAS insert <canvas-id> --into <section-id> --type text --text "..." \
  --why "..." --base "$canvas_base" --author "..."

# and the node that changed sides
$CANVAS move <canvas-id> <node-id> --into <section-id> \
  --why "<the assumption that carried it>" --base "$canvas_base" --author "..."
```

**A node has crossed from one space to the other when a `move` naming it changed which
`<section>` it sits in.** Precisely: its nearest `<section>` ancestor in the document at
that commit differs from its nearest `<section>` ancestor at that commit's parent, where
*having no `<section>` ancestor* counts as one of the two values and is equal to no
section. A node with at least one such edit **has crossed**; the **latest** one is its
crossing, and that move's `--why` is the assumption that carried it. Nothing else is a
crossing: not an `insert` straight into a section, not a `replace`, not a `remove`, not a
`move` that left the nearest `<section>` the same, and not a `move` of a container seen
from a child — there the container crossed, the container carries the one reason that was
written, and its children carry none.

**Nothing reads the title.** Which of your sections is the problem space and which is the
solution space is your reading of your own heading, and no rule, test, renderer or tool
reads those characters. Sections titled `Symptoms` and `Fixes`, or `Before` and `After`,
behave identically. So a title cannot be spelled wrong, and a privileged one would be a
node type declared in character data — which is the tripwire above, wearing a `title=`.

**What a reader gets.** Both projections show exactly one reason per crossed node — that
crossing's `--why`, verbatim, beside the full sha of its commit — and no reason anywhere
else. A node born where it stands carries none; a node that crossed three times carries
one; no node carries two. A Canvas in which nothing has moved between sections renders
with no reason in it at all, and that is correct rather than a gap. The rule is
`problem-and-solution-space.md` in the canvas repository.

**When your step is the one that settles something**, leaving the Canvas as an answer is
two kinds of edit and no more: put what is now believed under the solution section, `move`
the nodes the work resolved into it, and let the `--why` of each move say the assumption
you are making and what would make it false. The assumption is the part a later reader most needs and the
part nobody writes down — and on a crossing it is the one sentence they are shown by
default. There is a worked one under `--why` above.

None of this is asked of you as a step. A Canvas with no sections is a valid Canvas and
almost all of them are; a second space earns its node when the work has produced one, not
before, and a Canvas that never grew one renders exactly as it renders today.

### Keep it small — resolution, not deletion

The budget is **20,000 characters** of the document as `read` prints it
(`BUDGET_CHARS` in ledger-orchestrator `orchestrator/canvas.py`). Over it, the whole canvas
is still sent to every step with a loud over-budget notice above it; nothing is truncated,
and nothing is blocked. **You are the only actor who can shrink it.** The remedy is
resolution: `replace` settled nodes with what they settled, so three options and a decision
become one sentence and the argument stays in `history`. Not deletion.

### `render` — for people, one-way, never read back

    $CANVAS render <canvas-id> > canvas.html          # standalone HTML page
    $CANVAS render <canvas-id> --format comment       # block-level Markdown for a Basecamp comment

Both open with an index of every `<question>` and name the sha they were rendered from. A
render is a read: it writes nothing, and like every verb here it works on a frozen canvas. There is no `--output`;
redirect stdout.

Redirect carefully: these shells run with `noclobber`, so `> canvas.html` **fails rather
than overwrites** if the file is already there, and `>> canvas.html` fails if it is not.
Use `>|` when you mean to replace, or a fresh filename. A render that silently did not
replace the file is a stale page carrying a sha nobody checks.

The `comment` projection exists for integrations such as the task ledger, which carries it
in one live Basecamp comment. When working through that integration, the row is the
comment's only author — do not post a second rendered copy yourself.

### `history` — what a node is *for*

    $CANVAS history <canvas-id> c4kc

Prints every edit that named that node, oldest first: sha, author, verb, reason. Edits made
before a `move` are included, because a move keeps the id. Read this before you `replace`
something that looks wrong — it may be right for a reason the current text does not carry.

### `freeze` — at `done` and at `abandoned`

    $CANVAS freeze <canvas-id> \
      --why "done: the delivered artifact is PR #26, merged 2026-09-24; nodes c4kc and ezwq carry the decisions it rests on"

One commit, naming no node and changing no byte of the document: what it records is that
the canvas has ended and why. One verb for both endings — *done* and *abandoned* are two
things a `--why` says. Everything goes on working afterwards: `read`, `render` and
`history`, and the four editing verbs too.

**A freeze is a marker and not a gate.** It refuses nothing and there is nothing to
unfreeze. A Canvas whose ledger row has closed still takes `replace`, `insert`, `remove`
and `move`, on the ordinary terms — one node, a `--why`, a `--base`. That is deliberate:
the moment a canvas is most improvable is the moment the work is over, because that is
when you finally know what it should have said. **Resumed work does not need a new Canvas
identifier** — write to the one that is already there.

`$CANVAS read <canvas-id> --frozen` is how you find out that a canvas ended and why; it
answers at exit `0` either way, and it is a report, not a warning.

For a standalone Canvas, you own this transition: freeze it when the work is done or
abandoned. For a ledger-integrated Canvas, the ledger does it for you:
`apply_transition` in `bin/task-ledger` freezes on `done` and on `abandoned`,
both of them, composing the `--why` from the row's own gate text and authoring it
`task-ledger | close` (ledger-orchestrator `docs/canvas-ends-at-terminal.md`).

A second `freeze` is legal, so running one first no longer breaks the ledger's: both
commits land, and the canvas's recorded ending is the **oldest** of them — the first one
anybody declared. Still leave it to the ledger on an integrated row, so that the reason
on record is the one composed from the row's own gate text rather than yours.

For an integrated Canvas, run `freeze` by hand only when:

- **the automatic freeze did not land** — the row closed carrying a `canvas:failed` event
  whose detail starts `freeze:`, and the ledger printed the exact command to run on stderr.

## What is not yours

- **`bin/canvas-coherence`** — the post-write model-backed contradiction checker. Orchestration
  invokes it after a successful write; it writes its findings back as `<question>` nodes
  through the store like any other writer. You do not call it per edit. See `coherence.md`.
- **An integrated row's Basecamp comment** — the ledger row is the single author of it.
- **`bin/canvas-validate <file>`** — validating a file by hand, for when you are debugging
  the store rather than driving a task.
- **An integrated Canvas's freeze at `done` and `abandoned`** — `bin/task-ledger` runs it,
  and the reason it composes from the row's gate text is the one worth having on record.
  Standalone Canvases are different: you freeze those yourself. See above.

## The three rules underneath all of this

1. **One edit is one node**, so a full rewrite is inexpressible.
2. **Every edit carries a reason**, and the reason is the product.
3. **A writer declares what it last read** (`--base`), and is refused or informed if the
   document moved.

Everything above is those three made operational. Canonical specs:
[product spec](https://malkovro.github.io/canvas/product-spec.html),
[engineering spec](https://malkovro.github.io/canvas/engineering-spec.html), and this
repository's `README.md` for the CLI in full.
