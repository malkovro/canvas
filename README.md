# Canvas

Canvas is a small structured document that holds the current shared understanding of a task between a person and the agents working on it.

This repository is the canonical home for both Canvas specifications:

- [Product spec](https://malkovro.github.io/canvas/product-spec.html)
- [Engineering spec](https://malkovro.github.io/canvas/engineering-spec.html)
- [Node identity](https://malkovro.github.io/canvas/node-identity.html) — how an `id` is minted, what preserves it under each of the four verbs, and what bumps `v`

## History/source

The original [Claude artifact](https://claude.ai/artifact/SQyYDCre5YXAhio5rd5KVc) is retained as a non-canonical historical source. The Markdown specifications in this repository are authoritative.

## The canvas file

A canvas is stored as XML with a closed vocabulary. The vocabulary is defined
once, in [`schema/canvas.rng`](schema/canvas.rng), a RELAX NG grammar — so a
schema violation is an exit code rather than a code review.

Eleven element names, and no twelfth: `canvas`, `section`, `text`, `list`,
`item`, `table`, `row`, `cell`, `figure`, `link`, `question`. `<canvas>` is the
root and carries `ledger` and `schema="1"`. `<section>` is the only container,
carries `title`, and nests one level — two levels of section in total, a third
is invalid. Every node except the root carries `id` and `v`.

The list is closed. `<decision>`, `<risk>` and `<acceptance-criterion>` are
rejected, and there is no way to register a twelfth element: no wildcard in the
grammar, no plugin point, no configuration file of allowed elements. A closed
list that can be opened by configuration is not closed.

Every container holds zero or more children, never one or more. One edit is one
node, so an empty `<list>`, an empty `<row>`, an empty `<section>` and a
childless `<canvas/>` are states a real document passes through and all of them
are valid.

### Validating a file by hand

    bin/canvas-validate <file> [<file> ...]

| exit | meaning |
|---|---|
| `0` | every file given is a valid canvas; nothing on stderr |
| `1` | the document is wrong — not well-formed, or it violates the schema. One diagnostic per problem on stderr, each naming the offending node |
| `2` | the tool or its invocation is wrong — no arguments, file missing or unreadable, `xmllint` not on `PATH`, schema missing or uncompilable |

The `1` / `2` split is the point: an agent has to be able to tell "your canvas
is invalid, fix the node I named" from "the validator is broken, do not touch
the canvas".

A diagnostic names the offending node — its element name, and its `id` where it
has one, or its path where it does not:

    bad.xml:4: <decision> (id="jc5v", v="1"): Did not expect element decision there
    bad.xml:3: <text> (no id attribute, v="1", at /canvas[1]/text[1]): Element text failed to validate attributes

The schema also stands on its own, with no Python involved at all:

    xmllint --noout --relaxng schema/canvas.rng <file>

### The validation path

Every read and every write of a canvas goes through one entry point:

```python
from canvas.validate import validate_file

problems = validate_file(path)   # list of diagnostics; empty means valid
```

`bin/canvas-validate` is a thin shim over the same function. A verb validates
the document it is about to write *before* committing it, so an invalid canvas
is never reachable on disk. Callers must not shell out to `xmllint` themselves
and must not restate any part of the vocabulary: every rule about what is legal
lives in `schema/canvas.rng` and nowhere else.

`validate_file` raises `canvas.validate.EnvironmentProblem` when the validator
itself cannot run. That is not an invalid document and must not be reported as
one.

### Running the tests

From a clean checkout, with no install step, no virtualenv and no network:

    python3 -m unittest discover -s tests -t .

Standard library only. It needs `xmllint`, which ships with macOS and with
GitHub's `ubuntu-latest` image, and `git`, because the store tests exercise the
real repository the tool builds. Every test points `$OPENCLAW_WORKSPACE` at its
own temporary directory; none of them touches a live workspace.

### What the schema deliberately does not check

- **That an `id` is globally unique.** Uniqueness is a property of the whole git
  history (`git log --grep='Canvas-Node: <id>'`), which no document schema can
  see. The schema checks the *shape* of an id; `insert` checks that it is free.
- **That `v` agrees with the commit count.** Same reason — checkable against the
  log, not against the file.
- **`<figure>` content beyond a textual source.** The engineering spec leaves
  open whether the renderer draws a figure from a textual source or passes
  through inline SVG. Admitting inline SVG means admitting a foreign namespace
  with an open element set, which is the HTML problem the closed vocabulary
  exists to prevent, so schema v1 admits a textual source only. Settling it the
  other way is a v2 change with its own reasoning.

## The store

A canvas lives in one file per ledger row:

    $OPENCLAW_WORKSPACE/state/canvas/<ledger_id>.xml

beside `state/ledger/<ledger_id>.json`. One fact, one place, joined on read.
`$OPENCLAW_WORKSPACE` has no default: a tool that falls back to a guess writes
real state whenever a caller forgets the variable, and the failure is silent and
lands on production data.

`state/canvas` is **one git repository** holding every ledger row's file,
initialised on first use and never re-initialised over one that already exists.
It is one repository and not one per canvas because ids are unique across the
whole of it, and the documented history command
`git log --grep='Canvas-Node: b7'` is written with no path filter.

    bin/canvas create  <ledger_id> --problem TEXT --expected-value TEXT [--author TEXT]
    bin/canvas read    <ledger_id>
    bin/canvas replace <ledger_id> <node-id> --why TEXT [--type NAME] [--text TEXT] [--title TEXT] [--href URL] [--author TEXT]
    bin/canvas insert  <ledger_id> (--after <node-id> | --into <container-id>) --why TEXT [--type NAME] [--text TEXT] [--title TEXT] [--href URL] [--author TEXT]
    bin/canvas remove  <ledger_id> <node-id> --why TEXT [--author TEXT]
    bin/canvas move    <ledger_id> <node-id> (--after <node-id> | --into <container-id>) --why TEXT [--author TEXT]

The read hands out the current sha; nothing enforces `--base` and no verb
accepts one.

### Creating a canvas

`create` makes the canvas for a ledger row with its first nodes — the problem
and the expected value the ledger's `open` already requires — and prints the sha
and the path:

    $ bin/canvas create my-task --problem "The store does not exist." \
                                --expected-value "A writer can learn what to write against."
    Canvas-Base: e4a864130afb88ad2abc17f1b4889df707b15ded
    Canvas-File: /…/state/canvas/my-task.xml

It is **three commits, not one**:

    create my-task: born at open, root only
    insert y8dk: the problem the ledger row states
    insert itpe: the expected value the ledger row states

`node-identity.md` §4 requires it. The creation commit creates the root only,
and the two first nodes arrive as two ordinary `insert` commits, each naming its
own node in a `Canvas-Node:` trailer, each born at `v="1"`. A single commit
holding the root and both nodes would be one commit touching two nodes, which is
the rule the tool exists to make inexpressible; the birth of a canvas gets no
exemption from it.

The root commit carries no `Canvas-Node:` — `<canvas>` is not a node — and no
`Canvas-Base:`, because there was no prior state it could have been decided
against. Each `insert` bases on the commit before it.

The two first nodes are `<text>` nodes, problem first. They carry no marker
saying which is which: the vocabulary has no semantic node and inventing one is
the `<decision>` / `<risk>` tripwire. The distinction lives in the commit
subject and in the order.

`create` refuses rather than overwrites. A canvas that already exists is exit
`1`, with the path and its current sha, and nothing is written.

`--author` becomes the `Canvas-Author:` trailer and is used verbatim, which is
how a run passes `leo | step:implement | run:ship-the-flag-3`. Driven by hand it
defaults to `<user> | by-hand` — not a synthesised `step:`/`run:`, because a run
id no run store can resolve makes `git log --grep='run:'` return rows for runs
that never existed.

### Reading a canvas

Reading is how a writer learns what to write against, so the sha is part of the
output rather than a separate lookup:

    $ bin/canvas read my-task
    Canvas-Base: e4a864130afb88ad2abc17f1b4889df707b15ded
    <?xml version="1.0" encoding="UTF-8"?>
    <canvas ledger="my-task" schema="1">
      <text id="y8dk" v="1">The store does not exist.</text>
      <text id="itpe" v="1">A writer can learn what to write against.</text>
    </canvas>

The sha comes first, on one line, under the same name the next write declares it
under: one name for one thing. It is the full forty characters — handing out an
abbreviation as an identity key is a hazard as the log grows — and it is
`git rev-parse HEAD` of the canvas repository, not the file's last-touching
commit, because that is what a later `--base` is compared against.

The cost, stated because it is real: **stdout is not itself a valid XML
document.** The document alone, byte for byte what is on disk, is

    bin/canvas read my-task | tail -n +2

A read is a read. It writes nothing, commits nothing, and does not initialise a
repository.

### The four verbs

Four editing verbs, and no more:

    $ bin/canvas replace my-task b7pk --type text \
                 --text "Chose A." \
                 --why "chose A over B: B needs a migration we are not paying for"
    Canvas-Node: b7pk
    Canvas-Base: 9c1e0a7…

Each is **one commit**, whose subject is `<verb> <node-id>: <why>` and whose
trailers are `Canvas-Node:`, `Canvas-Author:` and `Canvas-Base:` — the same
three `create`'s own `insert` commits already write. The reason is recorded in
the commit and nowhere else: there is no `Canvas-Why:` trailer and no attribute
on the node, because a node's reasons are its history.

**There is no `resolve`, no `collapse` and no `supersede`.** An options
`<table>` becoming a settled decision is `replace` on the table node with
`--type text`. The semantics live in the reason, where they can be anything,
and not in a verb name, where they can only be what somebody thought of in
advance.

**Addressing is by explicit node id.** No selector, no path, no "the first
heading". That is the property that makes IWE's `--expect` match-count guard
unnecessary here — a selector can match two nodes, an id cannot — and it is the
argument against ever adding one.

| verb | what it does | id | `v` |
|---|---|---|---|
| `insert` | adds one node at a named position | mints a fresh one, never reminting a retired id | born at `1` |
| `replace` | new content, possibly of a different node type | unchanged, including across the type change | bumps |
| `move` | position only: content, type and children untouched | unchanged | bumps |
| `remove` | takes the node out | retired, never reminted | none left to bump |

A node's `v` is written from the log rather than incremented in the file:
`node-identity.md` §4 defines `v` as the number of commits whose `Canvas-Node:`
trailer names the node, so the store counts them and adds the commit it is
about to make. The number in the file cannot drift away from its own
definition.

Each verb names the canvas as well as the node. Ids are unique across the
repository, so an id does identify a node on its own — but `state/canvas` holds
one file per ledger row, `--into root` names a root that every one of them has,
and finding the file by scanning them all would need a match-count guard for
the case where two answered. Naming the canvas is the cheaper half of that
trade, and it is what `create` and `read` already do.

#### `--why`, and what it costs to omit

`--why` is required by all four, **with no default and no fallback**. An absent
one is refused by the argument parser; an empty or whitespace-only one is
refused by the store. Both exit `2` — an unexplained edit is a malformed
invocation, not a request that is wrong against the store — and both write
nothing, commit nothing and mint nothing.

The rule lives in `canvas/store.py` and not in the command line above it.
`write_and_commit` is the only function that puts a canvas on its real path, it
takes the reason as a positional argument and it calls `require_reason` before
it opens a file. **There is no code path that writes to a canvas without a
reason** — including from Python, including for `create`, whose three commits
carry their reasons the same way.

#### How new content is supplied

Neither spec said, so this is settled here: a node type by name, and the two
attributes the closed vocabulary has that are not identity.

| flag | what it sets |
|---|---|
| `--type NAME` | the element name. Defaults to `text` on `insert`, and on `replace` to the type the node already has |
| `--text TEXT` | the node's character data |
| `--title TEXT` | the `title` a `<section>` requires |
| `--href URL` | the `href` a `<link>` requires |

Named flags rather than a general `--attr name=value`, because a general one
could set `id` and `v` — and `insert` mints ids, so a caller cannot supply one.
Which element names exist and which attributes each requires stays
`schema/canvas.rng`'s business: `--type decision` builds a `<decision>` node
and the validator refuses to let it reach the canvas's path.

#### One edit is still one node

`node-identity.md` §5 decided these in writing before any verb existed, so they
ship with the verbs rather than after them:

- **`remove` on a node that still has children is refused**, naming the node
  and every child id. A cascading delete either names N nodes in one trailer or
  lets N−1 vanish in a commit no grep on them will ever return.
- **`replace` that would change the type of a node that has children is
  refused**, because the new type has nowhere to put them. Move them out first;
  they keep their ids throughout, which is the entire benefit.
- **`replace` that would give a node with children character data is refused**,
  because a node holds children or text and never both, so the text would be
  dropped silently.
- **`move` of a node into itself is refused.** The subtree would leave the
  document and the commit would name one node while N disappeared.

A `replace` payload cannot express children at all, so "one commit rewriting N
children" is inexpressible here rather than merely refused. Replacing a
`<section>` that has children renames it: the children keep their ids, their
`v`, their content and their order.

### Naming a position

`node-identity.md` §6 settles how a position is named, including the first
position of an empty container: `--after <node-id>` for the sibling case, and
`--into <container-id>` — appending as the last child — for the container case,
with the root named by the reserved word `root`. The flags ship with the four
verbs; the rule and the placement code are in `canvas/document.py` already, so
that the verbs inherit an answer instead of improvising one.

### Exit codes

| exit | meaning |
|---|---|
| `0` | it worked |
| `1` | the request is wrong against the store as it stands — the canvas already exists, there is no canvas for that ledger id, or the document is invalid. Re-read and re-decide |
| `2` | the tool or its environment is wrong — `$OPENCLAW_WORKSPACE` unset or not a directory, an unknown verb, a missing or malformed argument (**including an absent or empty `--why`**), a ledger id that is not a filename, `git` or `xmllint` missing, or the validator unable to run. Do not touch the canvas |

This is `bin/canvas-validate`'s `1` / `2` split with its purpose preserved, and
it differs from it in one deliberate place. `canvas-validate` maps a missing
file to `2`, because there the caller supplied the path and a missing file means
the invocation named the wrong one. Here the path is *derived* from a ledger id,
so "no canvas for this ledger" is a true statement about the store rather than a
broken invocation, and the right response is to create one or re-check the id —
not to stop touching the canvas. It maps to `1`. A *malformed* ledger id stays
`2`, because that is the invocation being wrong.

A ledger id has to be a filename: one or more of `[A-Za-z0-9._-]`, not starting
with a dot. That is what stops `canvas read ../../../etc/passwd` from escaping
`state/canvas/`.

### What the store deliberately does not do

- **It does not enforce `--base`.** The read hands out the sha and stops
  there, and no verb accepts one. The `Canvas-Base:` trailer an edit writes is
  the truthful record of the head it was applied to, compared against nothing.
- **It does not report a node's history.** `git log --grep='Canvas-Node: b7'`
  is the documented command and there is no verb wrapping it.
- **It does not batch.** Nothing in it can touch two nodes in one commit.
- **It does not wire the ledger's `open` transition.** `create` is driven by hand.
- **It does not shell out to `xmllint` and does not restate the vocabulary.**
  Every write goes through `canvas.validate.validate_file` at a temporary path
  and is renamed into place only once it validates, so an invalid canvas is
  never reachable as a canvas. `EnvironmentProblem` is "the validator cannot
  run" — exit `2` — and never "the document is invalid".
