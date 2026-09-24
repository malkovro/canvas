---
name: canvas
description: >-
  Drive a Canvas — the small structured XML document that holds the current shared
  understanding of one ledger-backed task between a person and the agents working on it.
  Use whenever a task has a ledger row and you need to read what is already understood,
  record a decision or an open question, settle one, render the canvas for a person, or
  end it. Covers the whole safe workflow for `bin/canvas`: read first and carry the sha
  into `--base`, one node per edit, a `--why` a later reader can resolve, and never
  editing the XML by hand. Triggers on "canvas", "bin/canvas", `--why`, "the shared
  understanding of this task", a `Canvas-Base:` / `Canvas-Node:` / `Canvas-Frozen:` line,
  or a ledger id that has a canvas.
allowed-tools: Bash, Read
---

# Canvas

A canvas is **one XML file per ledger row**, git-backed, holding what is currently
understood about that task: the problem, what is expected, the decisions taken, the
questions still open. The ledger projects a task's *lifecycle*; the canvas projects its
*content*.

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
| `1` | **your request is wrong against the store as it stands** — no canvas for that ledger id, no such node, the node you are writing moved since your `--base`, an unknown `--base` sha, the canvas is frozen, the document is invalid | re-read and re-decide. The refusal names the node and hands you its diff |
| `2` | **the tool or its environment is wrong** — `OPENCLAW_WORKSPACE` unset or unusable, `git` or `xmllint` missing, a malformed ledger id, an absent or empty `--why`, a `--base` that is not a sha | **do not touch the canvas.** Fix the environment or the invocation. Retrying the edit will not help |

A `1` is information about the task. A `2` is information about your machine. Do not
report a `2` as "the canvas refused my edit".

## The loop: read, decide, write against the sha you read

This is the only safe shape, and the staleness check is the reason the canvas can be
pasted into a prompt at all.

```bash
# 1. read — the first line is the sha you will write against
$CANVAS read <ledger-id>
# Canvas-Base: dd93708016b1eee07970a587147cab8ca7c6a5b8
# <?xml version="1.0" ...

# 2. decide

# 3. write ONE node, naming that sha
$CANVAS insert <ledger-id> --into root --type text \
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

## `--why` is the field that makes the canvas worth reading

It is required, has no default, and lives in the commit subject and nowhere else.
`bin/canvas history <ledger-id> <node-id>` is how a later reader asks what a node is *for*.

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

## When to do what, over a ledger-backed task's life

### `create` — almost never yours

`bin/task-ledger open` creates the canvas, with the row's problem and expected value as its
first two nodes. Run `create` by hand only when that failed — the row's live Basecamp
comment says `canvas:failed` and stderr named the command to run. `create` refuses to
overwrite an existing canvas (exit `1`).

    $CANVAS create <ledger-id> --problem "..." --expected-value "..."

**Neither may be blank.** An absent, empty or whitespace-only `--problem` or
`--expected-value` is exit `2` and writes nothing at all — no canvas, no commits, no
minted ids — so the ledger id is still free. If that is why the row's `canvas:failed`
fired, the repair is to run the command above with a problem and an expected value that
say what they hold, not to open a second row.

### `read` — first thing in any step that touches the task

    $CANVAS read <ledger-id>                    # sha, then the whole document
    $CANVAS read <ledger-id> --id c4kc --id ezwq # those nodes and their subtrees
    $CANVAS read <ledger-id> --type question     # every question
    $CANVAS read <ledger-id> --provenance        # + who last wrote each node, and at which sha
    $CANVAS read <ledger-id> --frozen            # + has this canvas ended, and why
    $CANVAS read <ledger-id> --since <sha>       # + what changed since a sha you held

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

### Keep it small — resolution, not deletion

The budget is **20,000 characters** of the document as `read` prints it
(`BUDGET_CHARS` in ledger-orchestrator `orchestrator/canvas.py`). Over it, the whole canvas
is still sent to every step with a loud over-budget notice above it; nothing is truncated,
and nothing is blocked. **You are the only actor who can shrink it.** The remedy is
resolution: `replace` settled nodes with what they settled, so three options and a decision
become one sentence and the argument stays in `history`. Not deletion.

### `render` — for people, one-way, never read back

    $CANVAS render <ledger-id> > canvas.html          # standalone HTML page
    $CANVAS render <ledger-id> --format comment       # block-level Markdown for a Basecamp comment

Both open with an index of every `<question>` and name the sha they were rendered from. A
render is a read: it writes nothing and works on a frozen canvas. There is no `--output`;
redirect stdout.

Redirect carefully: these shells run with `noclobber`, so `> canvas.html` **fails rather
than overwrites** if the file is already there, and `>> canvas.html` fails if it is not.
Use `>|` when you mean to replace, or a fresh filename. A render that silently did not
replace the file is a stale page carrying a sha nobody checks.

The `comment` projection is what the **ledger row** carries in the one live comment it
rewrites in place. The row is its only author — do not post a rendered canvas yourself.

### `history` — what a node is *for*

    $CANVAS history <ledger-id> c4kc

Prints every edit that named that node, oldest first: sha, author, verb, reason. Edits made
before a `move` are included, because a move keeps the id. Read this before you `replace`
something that looks wrong — it may be right for a reason the current text does not carry.

### `freeze` — at `done` and at `abandoned`, and once

    $CANVAS freeze <ledger-id> \
      --why "done: the delivered artifact is PR #26, merged 2026-09-24; nodes c4kc and ezwq carry the decisions it rests on"

One commit, naming no node and changing no byte of the document: what it records is that
the canvas has ended and why. One verb for both endings — *done* and *abandoned* are two
things a `--why` says. Afterwards every write verb is refused at exit `1`; `read`, `render`
and `history` go on working.

**There is no unfreeze.** A task that comes back gets a new ledger row and a new canvas — so
a canvas ends when its *row* reaches a terminal state, never when you finish a step.

**Which means you almost certainly should not run it.** The ledger does it for you: `apply_transition` in `bin/task-ledger` freezes on `done` and on `abandoned`,
both of them, composing the `--why` from the row's own gate text and authoring it
`task-ledger | close` (ledger-orchestrator `docs/canvas-ends-at-terminal.md`).

A freeze you ran first makes that one fail, because there is no second freeze. The row still
closes — it is designed to close whether or not the freeze lands — but it records a
`canvas:failed` event reading `freeze: exit 1`, and the row is the only thing that could have
said the canvas ended properly. You get a defect in the record in exchange for a step that
was already being taken for you.

So run `freeze` by hand in exactly two cases:

- **no ledger row is closing this canvas** — a scratch or sample canvas, or one whose row
  predates the wiring; or
- **the automatic freeze did not land** — the row closed carrying a `canvas:failed` event
  whose detail starts `freeze:`, and the ledger printed the exact command to run on stderr.

## What is not yours

- **`bin/canvas-coherence`** — the post-write model-backed contradiction checker. Orchestration
  invokes it after a successful write; it writes its findings back as `<question>` nodes
  through the store like any other writer. You do not call it per edit. See `coherence.md`.
- **The row's Basecamp comment** — the ledger row is the single author of it.
- **`bin/canvas-validate <file>`** — validating a file by hand, for when you are debugging
  the store rather than driving a task.
- **The freeze at `done` and `abandoned`** — `bin/task-ledger` runs it, and running it first
  is how you break it. See above.

## The three rules underneath all of this

1. **One edit is one node**, so a full rewrite is inexpressible.
2. **Every edit carries a reason**, and the reason is the product.
3. **A writer declares what it last read** (`--base`), and is refused or informed if the
   document moved.

Everything above is those three made operational. Canonical specs:
[product spec](https://malkovro.github.io/canvas/product-spec.html),
[engineering spec](https://malkovro.github.io/canvas/engineering-spec.html), and this
repository's `README.md` for the CLI in full.
