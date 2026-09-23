# Canvas

Canvas is a small structured document that holds the current shared understanding of a task between a person and the agents working on it.

This repository is the canonical home for both Canvas specifications:

- [Product spec](https://malkovro.github.io/canvas/product-spec.html)
- [Engineering spec](https://malkovro.github.io/canvas/engineering-spec.html)
- [Node identity](https://malkovro.github.io/canvas/node-identity.html) — how an `id` is minted, what preserves it under each of the four verbs, and what bumps `v`
- [Node state](https://malkovro.github.io/canvas/node-state.html) — whether a canvas may say anything about a node's state, and how much: `answered` on `<question>`, and nothing else anywhere
- [Node naming](https://malkovro.github.io/canvas/node-naming.html) — whether what `create` mints is distinguishable inside the document itself, and where the distinction lives instead
- [Rendering](https://malkovro.github.io/canvas/rendering.html) — what the renderer does with a `<figure>`, and how the index of open questions and the per-node marker treat a question that has been answered

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

`<question>` is the one node that carries state: it may carry
`answered="true"`, and nothing else. Absence means open, `answered="false"` is
invalid, and no other element may carry it. That is the whole of what a canvas
says about a node's state — [`node-state.md`](node-state.md) decides it and
prices what it leaves in the reason.

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
| `2` | the tool or its invocation is wrong — no arguments, file missing, unreadable, not a regular file, or in a directory this process may not look in, `xmllint` not on `PATH`, schema missing or uncompilable, or **any other condition the operating system refuses the command with**. The refusal carries the errno, so a caller can tell a permission problem from a missing file |

The `1` / `2` split is the point: an agent has to be able to tell "your canvas
is invalid, fix the node I named" from "the validator is broken, do not touch
the canvas". The refusal says which of the two it is in band — see
[what a refusal prints](#what-a-refusal-prints) — so a caller reading stderr
does not have to have read this table.

A diagnostic names the offending node — its element name, and its `id` where it
has one, or its path where it does not — and the refusal that carries it says
what to do about it:

    $ bin/canvas-validate bad.xml
    canvas-validate: not a valid canvas: bad.xml
    bad.xml:4: <decision> (id="jc5v", v="1"): Did not expect element decision there
    bad.xml:3: <text> (no id attribute, v="1", at /canvas[1]/text[1]): Element text failed to validate attributes
    bad.xml fails to validate
    Canvas-About: file bad.xml
    Canvas-Next: repair the file at the line each diagnostic above names, then re-run `bin/canvas-validate bad.xml`; what a canvas node may be is written in /…/schema/canvas.rng and nowhere else, and `xmllint --noout --relaxng <that schema> <file>` asks it directly
    Canvas-Exit: 1 — the document is wrong, not the validator; repair the node each diagnostic names

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
  history — the commits whose `Canvas-Node:` trailer names the id — which no
  document schema can see. The schema checks the *shape* of an id; `insert` checks that it is free.
- **That `v` agrees with the commit count.** Same reason — checkable against the
  log, not against the file.
- **`<figure>` content beyond a textual source.** Admitting inline SVG means
  admitting a foreign namespace with an open element set, which is the HTML
  problem the closed vocabulary exists to prevent, so schema v1 admits a
  textual source only. Settling it the other way is a v2 change with its own
  reasoning. What the renderer does with that source is now settled too, and
  separately: [`rendering.md`](rendering.md) §1 rules that it prints it
  verbatim and takes no drawing step, so nothing about the grammar moves.

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
whole of it: the uniqueness check `insert` runs is the history itself, with no
path filter, so a repository per canvas would path-scope it by accident and
hand out an id another canvas already used.

    bin/canvas create  <ledger_id> --problem TEXT --expected-value TEXT [--author TEXT]
    bin/canvas read    <ledger_id> [--id NODE-ID]... [--type NAME]... [--provenance] [--since SHA]
    bin/canvas render  <ledger_id>
    bin/canvas history <ledger_id> <node-id>
    bin/canvas replace <ledger_id> <node-id> --why TEXT [--base SHA] [--type NAME] [--text TEXT] [--title TEXT] [--href URL] [--answered] [--author TEXT]
    bin/canvas insert  <ledger_id> (--after <node-id> | --into <container-id>) --why TEXT [--base SHA] [--type NAME] [--text TEXT] [--title TEXT] [--href URL] [--answered] [--author TEXT]
    bin/canvas remove  <ledger_id> <node-id> --why TEXT [--base SHA] [--author TEXT]
    bin/canvas move    <ledger_id> <node-id> (--after <node-id> | --into <container-id>) --why TEXT [--base SHA] [--author TEXT]
    bin/canvas freeze  <ledger_id> --why TEXT [--author TEXT]

The read hands out the current sha and all four verbs take it back as
`--base`: the sha the edit was decided against. [The staleness
rule](#--base-and-the-two-branches) is what it buys.

Nine subcommands, and still **four editing verbs**. The other five are three
reads — `read`, [`render`](#rendering-a-canvas) and `history` — and the two
ends of a canvas's life: `create`, which is its birth, and
[`freeze`](#ending-a-canvas), which is its end. A freeze edits no node, so it
is not a fifth verb in the sense the four are, and a projection is not one
either: `render` writes nothing at all.

### Creating a canvas

`create` makes the canvas for a ledger row with its first nodes — the problem
and the expected value the ledger's `open` already requires — and prints the sha
and the path:

    $ bin/canvas create my-task --problem "The store does not exist." \
                                --expected-value "A writer can learn what to write against."
    Canvas-Problem: y8dk
    Canvas-Expected-Value: itpe
    Canvas-Base: e4a864130afb88ad2abc17f1b4889df707b15ded
    Canvas-File: /…/state/canvas/my-task.xml

**The two ids first**, because an id is the thing the caller did not know —
`insert` prints `Canvas-Node:` for the same reason. One name each, and not
`Canvas-Node:` twice: two lines differing only in their position would leave the
caller counting, which is the thing [`node-naming.md`](node-naming.md) rules the
document does not carry. `Canvas-Problem:` and `Canvas-Expected-Value:` name the
two flags `create` takes, one for one. The price, the same one `freeze` already
pays for `Canvas-Freeze:`: a caller grepping `Canvas-Node:` across the verbs to
collect minted ids does not see `create`'s.

The two lines below them are unchanged and in their existing order, so anything
parsing `Canvas-Base:` or `Canvas-File:` by name is unaffected.

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
subject, in the order, and in the two lines above — and
[`node-naming.md`](node-naming.md) is the ruling that settles it, says what would
reopen it, and names the one thing it costs: the rendered page shows two
unlabelled paragraphs, which the renderer is free to fix and the grammar is not.

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

**The boundary rule, once, so nothing added to the header ever breaks a second
idiom: the document begins at the `<?xml` declaration line, and everything above
it is the header.** `tail -n +2` is the document alone for a read with no flags;
`sed -n '/^<?xml/,$p'` is the document alone under any combination of them. A
unified diff in the header cannot be mistaken for the declaration — a diff
prefixes every line with a space, a `+` or a `-`.

A read is a read. It writes nothing, commits nothing, and does not initialise a
repository. That stays true of every flag below: all any of them adds is
`git log`, `git diff`, `git rev-parse` and `git merge-base --is-ancestor`. None
of them acquires anything either — none of this is a lock, and the answer can be
stale the moment it is printed. `--base` on the next write is still the only
thing that refuses.

#### Part of a canvas: `--id` and `--type`

The canvas goes into every step's prompt, so a read that is all-or-nothing is a
prompt that is all-or-nothing. Two flags select part of it, by node id and by
node type:

    $ bin/canvas read my-task --type question
    Canvas-Base: e4a864130afb88ad2abc17f1b4889df707b15ded
    <?xml version="1.0" encoding="UTF-8"?>
    <canvas ledger="my-task" schema="1">
      <question id="mqxd" v="2">Does the store re-read before it writes?</question>
    </canvas>

- **Both repeat, and they union.** Every occurrence of either adds to one
  selection: a node is printed if any selector names it. Not intersection — an
  `--id` intersected with a `--type` is either that one node or nothing.
- **A selected node brings its subtree, once.** A selected node inside another
  selected node is printed in place and not again on its own.
- **The sha is unchanged.** `Canvas-Base:` is still the first line, still the
  repository head, still forty characters, whatever was selected: the selection
  narrows what you see, not what you would be writing against.
- **What comes back is a projection of the document and not the document, and is
  not claimed to validate.** Selecting a `<cell>` without its `<row>` produces
  something the grammar refuses, and that is correct — the stored file is the
  document and is the thing that validates. Nothing runs the validator over a
  selection. A read with no selector still prints the file byte for byte.
- **A `--type` that matches nothing is exit `0` and an empty root:**
  `<canvas ledger="my-task" schema="1"/>`. A type is a predicate and "none" is
  its answer, not its failure — *are there any `question` nodes left* is the
  question this exists to answer, and a tool that refuses to say "none" has not
  answered it. **An unknown type name is not refused either**: `--type decision`
  matches nothing and says so, because refusing it would need a list of legal
  element names in Python and the vocabulary is written down once, in
  `schema/canvas.rng`, and nowhere else.
- **An `--id` that names no node in this canvas is exit `1`**, naming the id.
  An id is an assertion that a node exists — ids are minted and unique — so a
  name that matches nothing is a wrong request, which is `history`'s rule for the
  same mistake: the canvas is there; the node is not.

**This is not addressing, and does not reopen the argument against it.** See
[*Addressing is by explicit node id*](#the-four-verbs) below: that argument is
about a selector on a **write**, which can silently touch two nodes when the
writer meant one, and it is why IWE's `--expect` match-count guard would have to
exist beside one. A read selector applies nothing, mints nothing and commits
nothing, and the matches *are* the output: there is no unseen second match for a
guard to catch. No editing verb takes a selector and none is being given one.

#### Who wrote what: `--provenance`

    $ bin/canvas read my-task --provenance
    Canvas-Base: e4a864130afb88ad2abc17f1b4889df707b15ded
    Canvas-Wrote: y8dk 8b03f2ebb78897960b14ba0f159d7f0964969b26 leo | by-hand
    Canvas-Wrote: itpe e4a864130afb88ad2abc17f1b4889df707b15ded claude-opus-5 | second-writer
    <?xml version="1.0" encoding="UTF-8"?>
    …

One `Canvas-Wrote: <node-id> <sha> <author>` line per node printed, in the order
the nodes are printed, composing with the selectors. It parses by splitting
twice: the id is four characters, the sha is forty, and the author is last and
free text, which it has to be — a `Canvas-Author:` value contains spaces and
pipes.

- **"Last wrote" is the last commit whose `Canvas-Node:` trailer names the
  node**, whatever verb it was. A `move` counts: it names the node and it bumps
  `v`, and `v` is exactly the count of those commits, so any other rule would
  make this disagree with the number in the file.
- **It is derived from the log and is in the document nowhere.** No node gains an
  `author` or a `commit` attribute: the vocabulary is closed, and an attribute
  the log cannot check is the thing `engineering-spec.md` already rejected.
  Provenance is a property of the read surface only.
- **It is behind a flag and not on by default**, because the canvas is bounded by
  what is affordable to send in every prompt, and a line per node on every read
  is a permanent tax on that. A read with no flags is byte for byte what it was.
- **A node no commit names** — reachable only by hand-editing the file, which the
  store treats as out of band — gets the word `unrecorded` in both fields rather
  than no line, so a caller can count lines against nodes.
- **`Canvas-Wrote:` is a new name and not a second spelling of an existing one.**
  `history` prints `Canvas-Commit:` and `Canvas-Author:` on lines of their own;
  reusing them here would be three lines per node, run together with nothing
  separating them. This name carries the *join* of a node, a commit and an
  author, which nothing else in the tool prints.

#### What changed since a sha: `--since`

Before writing against a base, ask what moved since it — and apply nothing:

    $ bin/canvas read my-task --since 4f1a2c9
    Canvas-Base: 31499cf9c2a16a4b7b5c2e7c1e8b9a0d3f6e5c4b
    Canvas-News: 1 commit(s) between 4f1a2c9… and 31499cf…
    replace itpe: they revised the expected value
    diff --git a/my-task.xml b/my-task.xml
    …
    <?xml version="1.0" encoding="UTF-8"?>
    …

It is the `Canvas-News:` block [the soft branch](#--base-and-the-two-branches)
already prints after a write, verbatim — the same lines, in the same order, under
the same name — asked for beforehand instead of told afterwards. A writer sees
identical text in both places and does not have to learn a second shape.

- **When nothing moved it prints exactly one line and no diff:**
  `Canvas-News: 0 commit(s) between <sha> and <sha>`. The soft branch prints
  nothing in that case, which is right there because nobody asked; here the
  question *was* asked, and silence is indistinguishable from the flag having
  done nothing.
- **A malformed or unusable sha answers exactly as `--base` does**, because it is
  one rule: not a sha at all is exit `2`; a well-formed sha this repository never
  handed out is exit `1`; known but not an ancestor of the head is exit `1`. An
  abbreviation git can resolve is accepted. The one difference is the next
  action — `--base`'s *"or drop it to ask for no staleness check at all"* is
  wrong advice for a question somebody asked on purpose.
- **It is not a lock**, and must not be read as one. The answer can be stale the
  instant it is printed. `--base` on the next write is what refuses.
- **It is not a whole-canvas history verb**, and the refusal below stands —
  see [*What the store deliberately does not do*](#what-the-store-deliberately-does-not-do).

### Rendering a canvas

    bin/canvas render <ledger_id> > canvas.html

`engineering-spec.md` section *Projections* gives the canvas three of them and
this is the first: *"HTML — the renderer's output. Shareable as a file,
viewable in a browser, pasteable into a Basecamp comment."* All of them are
one-way. **A projection is never edited and never read back**, so there is no
form, no button, no route and no flag here that writes to a canvas.

    $ bin/canvas render my-task | head -3
    <!DOCTYPE html>
    <html lang="en">
    <head>

**stdout is the page, and nothing but the page.** No `Canvas-Base:` line above
the doctype and no trailer under the closing tag: unlike `read`, whose stdout
[is deliberately not a valid XML document](#reading-a-canvas), this output is a
file somebody opens in a browser or pastes into a comment, and a line of plain
text above the doctype would be a defect in the artifact. Redirecting stdout is
how the page becomes a file, and **there is no `--output`** — a projection this
command could write anywhere is a projection somebody eventually writes into
`state/canvas`.

**One standalone document.** No stylesheet to fetch, no script, no font and no
image. It opens from a `file://` path and survives being pasted somewhere with
no network.

What the page carries:

- **Every element in the vocabulary.** `<section>` with its title and its one
  level of nesting as two heading levels, `<text>` as a paragraph, `<list>` /
  `<item>`, `<table>` / `<row>` / `<cell>`, `<figure>`, `<link>`, `<question>`.
  Every node keeps its canvas `id` as the HTML `id`, so an id found in one is
  found in the other and the index can link to it.
- **A marker on every `<question>`.** In words — *Open question*, *Answered
  question* — because a colour is not a marker a reader of the HTML can point
  at.
- **An index of open questions at the top**, naming every `<question>` id in
  the document and nothing else. An answered question keeps its entry and is
  quiet; it is not dropped. [`rendering.md`](rendering.md) §2 argues that, and
  `tests/test_render.py` holds it on a canvas with open questions and on one
  with none.
- **The sha it was rendered from**, in full, in the page's own header. A
  rendered page outlives the canvas it came from — that is what pasting one
  into a comment does — and this line is the only thing that tells it apart
  from the canvas as it stands now.

**A `<figure>` is its textual source, printed verbatim. This renderer does not
draw.** Schema v1 admits a textual source only, so there is no inline SVG to
pass through; and a drawing step would be a diagram toolchain this repository
would then own — an install, a dependency and a second grammar validated by a
binary rather than by `schema/canvas.rng`. [`rendering.md`](rendering.md) §1
settles it, with what it costs and what would reopen it.

**A render is a read**, on `read`'s terms: it writes no file, makes no commit,
mints no id and does not initialise a repository, and it goes on working on a
canvas that has been [frozen](#ending-a-canvas).

| exit | meaning |
|---|---|
| `0` | the page is on stdout |
| `1` | the request is wrong against the store as it stands — there is no canvas for that ledger id, or the stored document is invalid. **An invalid canvas is refused rather than rendered**, with the validator's diagnostics: `read` prints an invalid document because refusing to show it would make it unrepairable, and a projection is the other case — a page asserting a canvas that does not exist, carrying a sha, is exactly the artifact somebody pastes into a comment. Repair it with `bin/canvas read` and `bin/canvas replace`, then re-render |
| `2` | the tool or its environment is wrong — `$OPENCLAW_WORKSPACE` unset or unusable, a ledger id that is not a filename, a missing or unrecognised argument, `git` or `xmllint` missing, the validator unable to run, or any other condition the operating system refuses the command with |

Those are [the tool's two codes](#exit-codes) and its
[one refusal shape](#what-a-refusal-prints); a new subcommand gets no third one.

### A node's history

The reason an edit was made is in the commit subject and nowhere else, so the
way to ask what a node's current text is *for* is to read the log. `history` is
the verb that does it:

    $ bin/canvas history my-task b7pk
    Canvas-Node: b7pk

    Canvas-Commit: 31499cf2d88f070dcd9f3fc7914c1e801e17d209
    Canvas-Author: leo | by-hand
    insert: the options this decision is between

    Canvas-Commit: d8cabf10a6537bab095bcc0c22d607c1af1ff6c4
    Canvas-Author: leo | step:implement | run:ship-the-flag-3
    move: file it under the decisions section

    Canvas-Commit: e29e76568379c9720c8ef2f7af59774122612c10
    Canvas-Author: leo | step:implement | run:ship-the-flag-3
    replace: chose A over B: B needs a migration we are not paying for

**Oldest first**, because the answer is a story: the reason the node was born,
then every reason it changed, ending at the reason it reads the way it does
now. One block per edit — the commit, the author, and then the verb and the
reason, which are the commit's subject taken apart. The reason is last in its
block because it is free text and everything before it is not.

**Edits made before a `move` are in the list**, and not as a special case.
`node-identity.md` §3 keeps a node's id across a move, so the commit the move
wrote names the same node the earlier commits named, and one query spans it.
That is what the id buys: a node that was drafted at the top of the canvas,
sharpened, and then filed under a section still answers for all three.

It names the canvas as well as the node, like every other verb, because
`state/canvas` holds one file per ledger row. And it is a read: it writes no
file, makes no commit, and does not initialise a repository.

**The match is on the trailer's value, for equality** — not the substring match
`git log --grep='Canvas-Node: b7'` performs. Ids are four characters, so asking
that for `b7` also returns `b7pk`'s whole life, and a `--why` that merely quotes
the string `Canvas-Node: b7pk` is counted as an edit to a node it never touched.
Both are reachable by following the documentation. `history` reads the trailer
block git itself parses and compares the value, so a prefix of an id, a longer
id that starts with it, and a reason quoting the trailer text are all excluded.
`v` is counted through the same matcher, which is what keeps the number in the
file equal to the number of commits the history shows.

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
advance. [`freeze`](#ending-a-canvas) is not a fifth one: it edits no node and
changes no byte of the document, and all four of these are refused against a
canvas it has ended.

**Addressing is by explicit node id.** No selector, no path, no "the first
heading". That is the property that makes IWE's `--expect` match-count guard
unnecessary here — a selector can match two nodes, an id cannot — and it is the
argument against ever adding one **to a write**.

[`read --id` and `read --type`](#part-of-a-canvas---id-and---type) are not that
and do not reopen it. The guard exists to catch a second match a caller never
saw, and it is needed because a write *applies* to what it matched. A read
selector applies nothing, mints nothing and commits nothing, and the matches are
the output — there is no unseen second match, and the count is legible by reading
what was printed. So there is no `--expect`, and no selector reaches any of the
four verbs.

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
nothing, commit nothing and mint nothing. Both name the node the edit was for,
too, and say what to type:

    $ bin/canvas replace a-row bn3x --text "We chose A."
    usage: canvas replace [-h] [--type NAME] [--text TEXT] [--title TITLE]
                          [--href HREF] [--answered] --why TEXT [--base SHA]
                          [--author AUTHOR]
                          ledger_id node-id
    canvas: replace: the following arguments are required: --why
    Canvas-Node: bn3x
    Canvas-About: command canvas replace
    Canvas-About: ledger id a-row
    Canvas-About: option --why
    Canvas-Next: re-run the same command with --why TEXT (why this edit is being made; required, with no default). There is no default and no fallback: a reason a tool invented is a sentence in the history that reads like somebody decided something. Nothing was written
    Canvas-Exit: 2 — the tool or its environment is wrong; do not touch the canvas

##### The rule a `--why` writer is given

`docs/why-verdict/VERDICT.md` §5.1 reads the first fifty reasons written to a
canvas and names one rule as the whole of the fix. It belongs wherever the
`--why` writing instruction lives, so it is here verbatim, and it is also in
the launch brief that puts it in front of a step that drives a canvas:
**`/Users/lfigea/Projects/ledger-orchestrator/guidelines/canvas-why.md`**.

> **Never point at another reason.** If the justification for this node is one you have
> already given for a sibling or a parent, name that node's four-character id and say what
> is *different* about this one — what it holds that the other does not, and what would
> retire this one and not the other. The words "as above", "as before", "same as", "same
> shape" and "matching X" are not reasons: `canvas history` prints one node's edits and
> never the node you meant.
>
> **When the node you are placing holds nothing** — an empty `<table>`, an empty `<row>`, a
> one-word header `<cell>` — the reason is not about the element. Say what the structure it
> belongs to is for, name the container's id, and say what would make this element wrong or
> unnecessary. Do not describe text that a later commit will put inside it.

The first clause's opening phrases are the one shape the store also refuses on
its own: a reason that contains `as above`, `as before`, `see above`, `same as
above`, `same shape`, `ditto` or `as previously` and names no other node's
four-character id is refused at exit `2` with nothing written, like an empty
one. `require_reason` in `canvas/store.py` is where that lives, and its
docstring records what it catches, what it does not, and the one reason in
forty-one the verdict priced as its accepted false positive.

##### A reason that asserts a fact about the world names its evidence

Convention, not enforcement — `engineering-spec.md` says the same thing about
the one drift this specification does not solve, and this repeats it where a
reader with only the README will meet it. An edit whose reason asserts a fact
about the world — that a PR merged, that a verdict ruled, that a file says
something — should name its evidence in `--why`: a PR, a verdict, a file and
line, so a reader can follow it. Nothing enforces that, and nothing is meant
to: the check would have to leave the canvas to run.

##### A merge or a split names the other node's id

The third convention in this place, and the same shape as the two above: about
what a reason must name, unenforced, and load-bearing because nothing else
carries it. `node-identity.md` §7 rules that a node's lineage is the set of
commits whose `Canvas-Node:` trailer names its id, and that it ends where that
set ends — the tool records no ancestor and no successor. So when an edit moves
one node's material into another id, **the `--why` of that edit is the only
place the pointer exists**, and it has to be in it:

- **A `remove` that retires the losing half of a merge names the id that took
  the material over**, and says that it now stands there. The retired node's
  history is not lost — `bin/canvas history` on a removed id still exits `0`
  and prints its whole life, with the removing commit last — but nothing in the
  document leads a reader to that id, so this sentence is the only route to it.
- **A `replace` that takes material over names the id it is taking it from**,
  while that node is still in the document to be named.
- **An `insert` that is the second half of a split names the id it was cut out
  of.** The split's `replace` cannot name the born node in return, because the
  id does not exist until the `insert` runs; that is the one direction the
  convention cannot carry, and no follow-up edit is made to repair it.

This is the same rule as `VERDICT.md` §5.1's first clause reaching its hardest
case rather than a new one. It says never to point at another reason, and to
name the other node's id and say what differs when the justification is a
sibling's;
a merge's `remove` is exactly that situation, and the reason that clears the
bar — why *this* node may go, when *"we deleted this section" is not a reason
for deleting any particular thing that was in it* — has to say that what it
held now stands inside the other node, which names it. The pointer is the
evidence the reason needs, not an extra clause. `require_reason` refuses the
version without it that a writer reaches for first: `--why "Merged upward;
reason as above."` exits `2` with nothing written.

`docs/merge-and-split/` holds the merge and the split this was decided against,
with every invocation, both refusals and the `bin/canvas history` output for
the surviving id and for the stranded one.

#### How new content is supplied

Neither spec said, so this is settled here: a node type by name, and the three
attributes the closed vocabulary has that are not identity.

| flag | what it sets |
|---|---|
| `--type NAME` | the element name. Defaults to `text` on `insert`, and on `replace` to the type the node already has |
| `--text TEXT` | the node's character data |
| `--title TEXT` | the `title` a `<section>` requires |
| `--href URL` | the `href` a `<link>` requires |
| `--answered` | marks a `<question>` answered; absence means open. The one state a canvas carries — [node-state.md](node-state.md). Restated and not sticky: a `replace` that omits it reopens the question |

Named flags rather than a general `--attr name=value`, because a general one
could set `id` and `v` — and `insert` mints ids, so a caller cannot supply one.
Which element names exist and which attributes each requires stays
`schema/canvas.rng`'s business: `--type decision` builds a `<decision>` node
and the validator refuses to let it reach the canvas's path.

#### One edit is still one node

`node-identity.md` §5 settles what "one node" means when the node has children,
and it settles it for **every container the vocabulary has** — `<section>`,
`<list>`, `<table>`, `<row>` and the root — and not for `<section>` alone. What
the store does, verb by verb:

- **`replace` on a container that has children renames it**, and that is
  permitted and ordinary. The children keep their ids, their `v`, their content
  and their order; the container's own attributes are replaced and its `v`
  bumps. A `<section>` of eight nodes is retitled by one command and the eight
  nodes are not mentioned in the commit.
- **`replace` that would change the type of a node that has children is
  refused**, because the new type has nowhere to put them. Move them out first;
  they keep their ids throughout, which is the entire benefit.
- **`replace` that would give a node with children character data is refused**,
  because a node holds children or text and never both, so the text would be
  dropped silently.
- **`remove` on a node that still has children is refused**, naming the node
  and every child id. A cascading delete either names N nodes in one trailer or
  lets N−1 vanish in a commit no grep on them will ever return. Empty it first.
- **`move` of a container carries its whole subtree, and is still one node's
  edit.** Position is a property of the child: every child is a child of the
  same container before and after, in the same order, with the same content and
  the same `v`, so not one child's record changed and not one child's history is
  missing anything. Only the moved node is named and only its `v` bumps.
- **`move` of a node into its own subtree is refused.** The subtree would leave
  the document and the commit would name one node while N disappeared.
- **`insert` brings exactly one node, and it arrives childless.** There is no
  payload that fills a container, so a subtree is built the way it is emptied —
  one node at a time, each with its own reason.

Every refusal exits `1`, writes nothing — not the file, not a commit, not a
temporary — and names the container and every child it would have touched, each
on its own `Canvas-Node:` line, with what to do instead on `Canvas-Next:`. That
is [the shape every refusal takes](#what-a-refusal-prints), and these are where
it came from.

A `replace` payload cannot express a child at all: `--type`, `--text`,
`--title`, `--href` and `--answered` are five scalars, and there is no
`--children`, no `--file`, no document body and no stdin. "One commit rewriting N children" is
**inexpressible** here rather than merely refused.

#### There is no code path that writes more than one node

The twin of the `--why` rule above, in the same place and for the same reason.
`_write_and_commit` compares the document it is about to write against the
document already on disk, and refuses unless exactly the node named in the
commit's `Canvas-Node:` trailer is the one that differs — same type, same
attributes, same character data, same parent, and the same sibling order for
every other node.

**The supported write surface is five functions**: `create`, `insert`,
`replace`, `remove` and `move`. Each takes a ledger id, a reason and at most one
node id, and **none of them takes a document**. That absence is the design:
a function that accepts a whole tree is a whole-document rewrite whatever it is
called, so the parameter is not offered and the one private function that has it
refuses the write anyway. `from canvas import store` reaches no further than
`bin/canvas` does, and `canvas.document` writes to no file at all.

**There is no code path that writes more than one node** — not a command, not a
flag, not a combination of flags, not a file-level route and not an import path.
The single write that names no node is the birth of a canvas, and the only
document it may produce is the root alone, which is why `create` is three
commits and not one.

#### `--base`, and the two branches

`--base <sha>` is the sha a write was decided against — the one a `read` handed
out. All four verbs take it and the store enforces it, and what it buys is the
split `engineering-spec.md` § *Staleness* names. Nothing reconciles and nothing
merges: **the refusal is the feature**, which is also why this is not CRDTs.

    $ bin/canvas read my-task
    Canvas-Base: 4f1a2c9…
    …
    $ bin/canvas replace my-task b7pk --text "Chose A." \
                 --why "chose A over B" --base 4f1a2c9…

**Nothing moved** — `--base` is the head, or nothing has touched this canvas
since it. The write applies and says nothing extra. A read-then-write round
trip against an unchanged canvas is silent:

    Canvas-Node: b7pk
    Canvas-Base: 9c1e0a7…

Silent means no diff, not no output. Those two lines are the verb's ordinary
success output and the sha on the second is what the next write bases on.

**Something else moved — the soft branch.** The write applies, and the same
output that reports success carries what the writer did not know: the range,
the reason for each commit in it, and git's own unified diff of this canvas
between `--base` and the head the write was applied to. The write's own commit
is not in it — it is not news to its author.

    Canvas-Node: b7pk
    Canvas-Base: 9c1e0a7…
    Canvas-News: 1 commit(s) between 4f1a2c9… and 31499cf…
    replace itpe: they revised the expected value
    diff --git a/my-task.xml b/my-task.xml
    …
    -  <text id="itpe" v="1">A writer can learn what to write against.</text>
    +  <text id="itpe" v="2">A writer learns what it did not know.</text>

**The node being written moved — the hard branch.** Exit `1`. Nothing is
applied, nothing is merged, nothing is committed, no file is written — not even
a temporary — and no id is minted. The refusal names the node and carries that
node's diff since `--base` on stderr, one block per commit that moved it: the
commit, its subject with the reason in it, and its patch. One commit is one
node, so a commit's own patch *is* that node's diff for that edit.

    $ bin/canvas replace my-task b7pk --text "Chose A." --why "…" --base 4f1a2c9…
    canvas: refusing to write b7pk: it moved in 1 commit(s) between --base
    4f1a2c9… and 31499cf…, so this edit was decided against text that is no
    longer there. …
    Canvas-Commit: 31499cf…
    replace b7pk: they got there first
    diff --git a/my-task.xml b/my-task.xml
    …

A node **removed** since `--base` is the hard branch too, with the removal as
its diff — rather than the bare "no node with id b7pk", which a writer working
from a stale read cannot learn anything from.

**`insert` never takes the hard branch.** Its node is minted after the check,
and an id no commit has ever named cannot have moved. The position anchor it
names is a different node: an anchor that is *gone* is already a refusal, and
an anchor that merely changed is reported in the news rather than refused — the
writer is told, and the node it asked to file beside it is filed beside it.

**Both branches are scoped to this canvas's own file.** `state/canvas` is one
repository holding every ledger row and the sha is repository-wide on purpose,
so without the path filter an edit to an unrelated row would make every writer
stale and the soft branch would fire carrying an empty diff. With it, the sha
stays a repository-wide identity key and the news is about the document the
writer actually read. `history` path-scopes for the same reason.

##### What an omitted `--base` means, and three ways one can be unusable

**`--base` is optional, and an omitted one is not a base of "now".** It is the
absence of the question: nothing is compared, and the verb behaves exactly as
it did before this rule existed. That is deliberately not `--why`'s shape —
`--why` has no value the tool could correctly compute, so an absent one is a
malformed invocation, while an absent `--base` asks for no check and there is
no silently wrong answer hiding in it. `create` takes none under either
reading: the birth of a canvas has no prior state it could have been decided
against, which is also why its root commit writes no `Canvas-Base:` trailer.

| the `--base` given | exit | why |
|---|---|---|
| not a sha at all | `2` | the invocation is wrong, as a malformed ledger id is |
| a well-formed sha this repository never handed out | `1` | a true statement about the store, like "no canvas for this ledger id". Re-read and re-decide |
| known, but not an ancestor of the head | `1` | the canvas repository has one line of history and nothing here branches, so this came from a rewritten history or somewhere else — and `<base>..HEAD` would answer "nothing moved" for it, a vacuous pass wearing the safe case's face |

An abbreviation git can still resolve is accepted. `read` hands out the full
forty characters, but there is no reason to refuse a shorter one supplied later.

The same three rows are
[`read --since`](#what-changed-since-a-sha---since)'s, because a sha is usable or
it is not and which command asked cannot change that. The one thing that differs
is the next action a refusal names: *"drop `--base` to ask for no staleness check
at all"* is right for a write and is wrong advice for a read that asked the
question on purpose.

The `Canvas-Base:` trailer the commit carries is a **different fact** and is
written either way: it is the truthful record of the head the edit was applied
to, not of the base the writer declared. On the soft branch those are two
different shas, and the commit records the one a reader of the history needs.

### Naming a position

`node-identity.md` §6 settles how a position is named, including the first
position of an empty container: `--after <node-id>` for the sibling case, and
`--into <container-id>` — appending as the last child — for the container case,
with the root named by the reserved word `root`. The flags ship with the four
verbs; the rule and the placement code are in `canvas/document.py` already, so
that the verbs inherit an answer instead of improvising one.

### Ending a canvas

`engineering-spec.md` §*Lifecycle* gives a canvas a life with an end in it: born
at `open`, grown through `executing`, **frozen at `done`** — "that artifact is a
projection of the canvas, and after it the canvas is read-only history" — and
**never deleted**, because "`abandoned` freezes it the same way, with the reason
as the last edit". `freeze` is that last edit:

    $ bin/canvas freeze my-task \
                 --why "done: the done-gate artifact is the What/Why/Evidence block on PR #21, merged 2026-09-23; nodes gjxb and qrpa carry the outcome"
    Canvas-Freeze: my-task
    Canvas-Base: 9c1e0a7…

It takes a `--why` like every other write, on exactly the same terms — required,
no default, no fallback, no fields, no structure and no required vocabulary, and
refused by the same [back-reference guard](#the-rule-a---why-writer-is-given).
An absent one is exit `2` and an empty or whitespace-only one is exit `2`, and
neither freezes anything. `--author` becomes the `Canvas-Author:` trailer, as it
does everywhere else. There is no `--base`: a freeze names no node and carries
no payload a moved document could invalidate, so it declares nothing, exactly as
`create` does — an omitted `--base` [is the absence of the
question](#what-an-omitted---base-means-and-three-ways-one-can-be-unusable) and
not an exception to the staleness rule. The commit still records
`Canvas-Base: <head>` truthfully.

**One verb for both endings.** `done` and `abandoned` are two things a `--why`
says, not two commands. The spec's own sentence is that `abandoned` freezes a
canvas *the same way* — the mechanism is identical and only the reason differs —
and this repository has already ruled twice that there is no `resolve`, no
`collapse` and no `supersede`, because "the semantics live in the reason, where
they can be anything, and not in a verb name, where they can only be what
somebody thought of in advance". So there is no `abandon`, and the third outcome
nobody has thought of yet — superseded, merged into another row, cancelled
before it started — needs no fourth verb either. The convention is to begin the
reason with what ended it: `--why "done: …"`, `--why "abandoned: …"`. **Nothing
enforces that**, deliberately: a value set for the outcome is a taxonomy, and
`--why` gains no required vocabulary here any more than anywhere else.

**Where the freeze is recorded: in the log, as one commit.** Its subject is
`freeze <ledger_id>: <why>` and it carries `Canvas-Freeze: <ledger_id>`:

    freeze my-task: done: the done-gate artifact is PR #21, merged 2026-09-23

    Canvas-Freeze: my-task
    Canvas-Author: leo | by-hand
    Canvas-Base: e4a8641…

It carries no `Canvas-Node:`, because a freeze edits no node — it is the second
and last write in this store whose commit names none, the other being the birth
of the canvas — and it changes **not a byte of the document**. Nothing is added
to `schema/canvas.rng`: the vocabulary is closed, it is written down once, and
what ends a canvas is not a node state. The freeze is where every reason in this
store already is, which is what makes it literally "the reason as the last
edit"; an attribute would need a second home for the reason, and the refusals
below have to name the freeze's *commit*, which a document can never carry for
the commit that wrote it. To see it:

    git -C $OPENCLAW_WORKSPACE/state/canvas log --grep='^Canvas-Freeze: my-task$'

**The query is not path-scoped, and cannot be.** A commit that changes no file
is invisible to `git log -- <path>`, so the tool matches the trailer's value for
equality across the whole repository — the same rule, in the same place, that
`history` already uses for `Canvas-Node:`.

The cost, stated because it is real: a frozen canvas's XML file, read on its own
with no repository around it, does not say it is frozen. That is the price of
not putting a twelfth attribute into a closed vocabulary, and it is the same
price `v`, authorship and every reason in this store already pay — the document
was never the whole of a canvas here.

**Every write verb is refused against a frozen canvas, at exit `1`.**
`replace`, `insert`, `remove`, `move`, a second `freeze`, and a `create` for the
same ledger id: all of them, with nothing applied, nothing committed and nothing
minted. The refusal names the freeze, its reason, its commit and its author:

    canvas: refusing to replace b7pk in my-task: this canvas was frozen at
            <40-char sha> — "<the freeze's reason>" — and a frozen canvas is
            read-only history. Nothing was applied, nothing was committed and
            nothing was minted
    Canvas-Node: b7pk
    Canvas-About: ledger id my-task
    Canvas-About: canvas /…/state/canvas/my-task.xml
    Canvas-About: freeze <40-char sha>
    Canvas-About: author leo | by-hand
    Canvas-Next: read it with `bin/canvas read my-task`; a freeze is final, …
    Canvas-Exit: 1 — the request is wrong against the store as it stands; …

`1` and not `2`, worked out from [the table above](#exit-codes) rather than
chosen: `1` is "the request is wrong against the store as it stands", and its
members include a node that moved since the `--base` declared for it — a store
that moved under a well-formed request. `2` is "the tool or its environment is
wrong", and its members are malformed invocations and OS conditions. A `replace`
against a frozen canvas is a well-formed invocation of a tool in perfect health;
the only thing wrong with it is the store's own state, and `1`'s stock advice —
re-read and re-decide — is true advice for it. An absent or empty `--why` is
still `2` even against a frozen canvas: an unexplained edit is the invocation
being wrong whatever the store's state is.

**`read` and `history` go on working, unchanged.** That is the other half of
"never deleted": a record nobody can read is deleted in every way that matters.
Both keep working *identically* — same stdout, same exit code — and in
particular `read` does not grow a `Canvas-Freeze:` line, because [its output's
shape is documented](#reading-a-canvas) as one header line and then the
document, so that `bin/canvas read my-task | tail -n +2` is the document byte
for byte. The cost: a writer learns about the freeze when it writes, not when it
reads. That is the same moment this store already tells a writer its `--base`
went stale, and the refusal is the feature.

#### When a frozen canvas's task reopens

**A freeze is final. There is no `unfreeze`, no `thaw` and no `reopen`** — those
are unknown verbs at exit `2`, and no verb in this tool takes a freeze back.
What happens instead is this, and it is the answer rather than a note that the
question exists:

The frozen canvas stays exactly where it is — readable, `history`-able, never
deleted — as the record of the work that ended. A ledger row whose task comes
back gets **a new ledger row, and therefore a new canvas**. Make it with
`bin/canvas create <the-new-ledger-id> --problem "…" --expected-value "…"`,
whose first two nodes are the reopened row's problem and expected value as the
ledger now states them, and then point it at the frozen one with a `<link>` node
whose `--why` names the freeze:

    $ bin/canvas create my-task-reopened --problem "…" --expected-value "…"
    $ bin/canvas insert my-task-reopened --into root \
                 --type link --href my-task.xml \
                 --text "The canvas this row continues." \
                 --why "my-task was frozen at 9c1e0a7… and its work has restarted here"

The old canvas is **not** edited to say it was superseded. That would be a write
to a frozen canvas, and it is refused like any other; the pointer belongs on the
document that is still alive, which is the one a reader is going to open.

The argument for taking it this way: the spec says a frozen canvas "is read-only
history", and the whole value of that sentence is that it is unconditional. An
`unfreeze` would make "frozen" a question no single commit answers — a reader
would have to find the *last* lifecycle commit rather than any freeze — and
every refusal above would have to be re-read as "frozen for now". The honest
cost is carried here: a reopened row does not resume its old canvas, and its
history is two documents joined by a link rather than one. For a store whose
canvases are per-ledger-row and whose node ids are unique across the whole
repository, that is a cheap price, and it keeps the freeze a fact rather than a
mode.

### Exit codes

| exit | meaning |
|---|---|
| `0` | it worked |
| `1` | the request is wrong against the store as it stands — the canvas already exists, there is genuinely no canvas for that ledger id (the filesystem answered `ENOENT`, not that it would not say), there is no such node in this canvas's history, **`read --id` named a node this canvas does not hold**, **the node being written moved since the `--base` declared for it**, the `--base` or `--since` is a sha this repository never handed out or one nothing here descends from, **the canvas has been [frozen](#ending-a-canvas) and takes no more writes**, or the document is invalid. Re-read and re-decide |
| `2` | the tool or its environment is wrong — `$OPENCLAW_WORKSPACE` unset, not a directory or not one this process may look at, an unknown verb, a missing or malformed argument (**including an absent or empty `--why`, and a `--base` or `--since` that is not a sha**), a ledger id that is not a filename, `git` or `xmllint` missing, the validator unable to run, or **a canvas that is there and cannot be read, a `state/canvas` that cannot be written or looked in, a directory anywhere above the canvas that this process may not traverse, something that is not a regular file where the canvas belongs, a repository this process may not read — which is never reported as a repository with no commits in it — or any other condition the operating system refuses the command with**. Do not touch the canvas |

Both non-zero codes arrive with that sentence attached, on the refusal's own
`Canvas-Exit:` line — see [what a refusal prints](#what-a-refusal-prints). A
caller reading stderr cannot see this table, and "no refusal exits with an
unexplained non-zero code" means the caller can tell which kind it hit from the
output, not that there are more codes. There are two, and there is no third.

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

A canvas this process cannot read is `2` and not `1`, which is the same call
made the other way round. "No canvas for this ledger id" is a fact about the
store and the caller can act on it; "the canvas is there and I am not allowed
to read it" is a fact about the *process*, and the store is intact. Exit `1`
would tell a caller to re-read and re-decide, and the re-read would fail in
exactly the same way. The two are told apart rather than guessed at: where
`state/canvas` cannot be looked in at all, the tool says it cannot tell whether
that canvas exists, because it cannot.

**Which of the two a refusal is, the errno decides — not the guard it landed
in.** The existence check and the `open` after it are separate syscalls, so a
canvas removed in between reaches the "cannot read it" path carrying `ENOENT`:
the filesystem has answered that it is gone, and that is the `1` above however
late the answer arrived. Exit `2` there would have the tool assert the canvas
is present one line under the errno saying it is absent, and name a `chmod`
against a file that is not there — a next action that cannot be run. So the
repair a refusal names and whatever it claims about the store are both chosen
by the errno, including for an errno this tool has never met: that one gets the
same trailers, the same documented code and a next action naming the path and
the condition, rather than inheriting the sentence written for the errno
somebody happened to meet first.

**A canvas file that vanished is `1`; the `state/canvas` repository that
vanished is `2`, and that is deliberate.** Both are `ENOENT`, both reach the
tool one syscall after a check that said otherwise, and the errno decides the
refusal in both — it is only the code the two land on that differs, because the
two absences are not the same fact. A canvas that is not there is one missing
file in a store that is otherwise intact, and the caller acts on it by creating
that canvas: `1`, "re-read and re-decide". A `state/canvas` that is not there is
the store itself missing, and that absence already has a code — the check one
syscall earlier answers "not a git repository" and refuses at `2`. Putting the
later answer at `1` would make the exit code depend on which side of a race the
caller landed on, which is the thing this section's `ENOENT` rule exists to
stop; it would just be the repository's race rather than the canvas file's. It
would also be false advice, because a read never initialises the repository, so
the re-read `1` asks for raises the same refusal again. What the errno changes
here is what the tool *says*: `ENOENT` gets the claim and the repair the check
gives — the repository is not there, make the first canvas with `bin/canvas
create` — and not "cannot tell whether there are any commits in it", which
contradicts the `errno 2 ENOENT` on the refusal's own `Canvas-About:` line.

**No failed look is reported as a finding.** That rule holds for the repository
and the workspace as well as for the canvas file, and each of the three used to
break it in the same way — a call that can fail for two reasons was read as
though it could only fail for one:

- `git rev-parse HEAD` exits `128` on a repository with no commits *and* on a
  `.git` this process may not read. Reading that as "no commits" made `read`
  announce that a repository holding three commits had none, and made `history`
  answer that a node those commits name "was never a node of this canvas". The
  question is asked as `rev-parse --verify --quiet` instead, which answers `1`
  in silence for a ref that is genuinely not there and `128` with a reason for a
  repository it could not open, and the repository is confirmed readable before
  the emptiness is believed.
- `os.path.isdir` answers False for a workspace that is absent, for one under a
  directory this process may not traverse, and for a regular file. Reading that
  as "not a directory" made the tool say so of a path `ls -ld` showed as
  `drwxr-xr-x`, and the repair it named — point `$OPENCLAW_WORKSPACE` somewhere
  that exists — could not work, because the variable was already right.

In every one of these the refusal was in the right shape, with a `Canvas-Next:`
and a `Canvas-Exit:` and no traceback. Shape is not enough: a refusal has to be
*true*, and its next action has to be one that succeeds. What the tool says
now, where it cannot look, is that it cannot tell — with the errno, and with
`chmod` against the shallowest directory that is actually refusing it.

### What a refusal prints

Every refusal in the tool prints the same five things, in this order, on
stderr, and both commands print them:

    canvas: <what is wrong, and why it cannot work>
    <whatever came with it — the validator's diagnostics, a commit and its patch>
    Canvas-Node: <one line per node the refusal involves>
    Canvas-About: <one line per thing it names where it has no node>
    Canvas-Next: <the one concrete thing to do that would succeed>
    Canvas-Exit: <the code, and what the code means>

`engineering-spec.md` section *What to copy* takes IWE's error surface
unconditionally: "a refusal names every node it matched and how to narrow,
because an agent can act on that and cannot act on the word 'refused'". These
lines are that, in the `Canvas-…:` trailer idiom the commits and the success
output already use — `Canvas-Node:` is the name a node id is printed under
everywhere else in the tool, so a refusal naming one uses the same word.

- **The message says what is wrong. `Canvas-Next:` says what to do**, and it is
  stated once, there. "Nothing was changed" is a fact about the past and an
  agent cannot act on it; the command that would succeed is on `Canvas-Next:`.
- **A refusal with no node is not an exemption.** Some genuinely have none —
  there is no canvas for this ledger id, `$OPENCLAW_WORKSPACE` is unset,
  `xmllint` is missing, a `--base` that is not a sha. Each names the thing it
  *is* about on `Canvas-About:` instead: the ledger id, the variable, the
  binary, the value that was rejected. Never an empty list of nodes.
- **A refusal names every node it has, and an `insert` that missed its position
  has none.** Every id the refusal is genuinely holding goes on a
  `Canvas-Node:` line: a `move` to a position that does not exist names the node
  being moved as well as the position it missed, because both are nodes of this
  canvas and a caller has to act on both. An `insert` that missed is the one
  placement refusal with nothing to name there — its node was minted moments
  earlier and has never been in the canvas, so no commit names it,
  `bin/canvas read` cannot show it, and the next attempt mints a different one.
  Printing that draw under `Canvas-Node:` would hand back an id a caller can
  neither look up nor reuse, so it names the ledger id and the position instead.
- **`Canvas-Exit:` is why no refusal exits with an unexplained code.** The
  meaning is this document's table's own words, printed beside the number,
  because a caller reading stderr cannot see a table in a Markdown file. The
  codes themselves are unchanged and there are still two. What a refusal did or
  did not write is the refusal's own to say, on `Canvas-Next:` — every refusal
  writes nothing, and the one check that runs after the commit has been made
  cannot have a line printed under every exit `2` claim otherwise for it.
- **The argument parser's refusals are in it too.** `canvas/cli.py` subclasses
  `ArgumentParser` so that `error()` raises rather than exiting, which is what
  lets an absent `--why` name the node the edit was for. It still exits `2`.
- **A `Canvas-Next:` may name a command that exits non-zero, and one word says
  which.** A command written after the word **`run`** is the *repair*: it is
  printed ready to run against real paths, running it is what makes the refused
  command work, and it exits `0`. Everything else a next action names is either
  a **diagnostic** — `ls -ld`, `ls -l`, `df -h`, `ulimit -n`, and `bin/canvas
  read <ledger-id>` where a staleness refusal sends you to look at the canvas
  again — there to show the state that produced the refusal; or a **form** — a
  command with a `<placeholder>` in it that the caller fills in, such as
  `bin/canvas create <ledger-id> --problem "<the problem>" --expected-value
  "<the expected value>"`.

  The rule is not about a command's exit code, it is about what the line
  *claims*: the line claims the repair, and claims nothing about the rest. A
  diagnostic's exit status is the answer rather than a failure. It may be `0` —
  `bin/canvas read` is — and on the conditions these refusals are about it is
  usually not: `ls -ld` on a path that is genuinely gone exits `1`, and so does
  every other way of looking at a path that is gone. That is why the rule
  cannot be "every command a next action names succeeds". That rule would leave
  a refusal about a missing path unable to tell a caller to look at it, which
  is the one thing a caller facing `ENOENT` most needs, and it is not even
  statable: four of the things these templates name are not runnable commands
  at all — `ulimit -n` is a shell builtin, `| cat | head -1` is a pipe
  fragment, `chown` is named bare with no operands, and a form exits `2` run
  verbatim on its own placeholder. The rule is **"every command a next action
  tells you to *run* succeeds"**.

  So `ls -ld <a canvas that was removed>` exiting `1` is the refusal working,
  and `chmod u+r <a canvas that was removed>` exiting `1` is the defect this
  surface exists to close — and a caller tells the two apart from one word,
  without having to know which commands this tool happens to use. A form is
  never marked `run`, because it cannot be run as printed.

  `tests/test_store.py` is where this stops being a convention.
  `assertRepairsRun` runs every command a next action marks `run`, whatever the
  command is, and requires that it exits `0` and carries no placeholder — and,
  in the other direction, that every `chmod` a next action names is marked,
  backticked or not, and that every backticked `git` it names is either marked
  or one of the helper's declared diagnostics, so that the rule cannot be
  escaped by dropping the word.

  **Where the word used to not mean this: four next actions in
  `canvas/store.py`.** `grep -n 'run \`' canvas/store.py` now returns nothing.
  Until [todo
  10330693749](https://app.basecamp.com/3934852/buckets/48039419/todos/10330693749)
  it returned four lines — in `_git_checked`, in `_cannot_read_repository`'s
  `complaint` arm, in `ensure_repository` and in `_log` — and every one of them
  put the marker in front of a *diagnostic*: “run `git …` yourself to see what
  it objects to”. All four predated this rule, whose scope when it was written
  was `canvas/refusal.py`'s templates, and no test reached the branches that
  print them, so `assertRepairsRun` never saw them and the suite was green with
  them in it.

  **Each of the four was decided on its own, and all four lost the marker.**
  Three of them — `_git_checked`, `_cannot_read_repository`'s `complaint` arm
  and `_log` — name the command git has just refused. Its non-zero exit is the
  condition the refusal exists for rather than a repair for it, and what git
  said about it is already in the message above the next action, so the command
  is there to look with and the line no longer claims otherwise. The fourth is
  the one this was expected to go the other way for: `ensure_repository`'s `git
  init -b main -- <dir>` is no diagnostic — `git init` only ever changes
  something — and it would have kept the marker if it could be made to exit
  `0` on the condition its refusal is about. It cannot. That condition is `git
  init` having just failed, and against a directory this process may not write
  into it exits `1` for as long as that holds. So that line names `ls -ld
  <dir>` and says what has to become true instead, and it does not name `git
  init` at all: an unmarked `git init` would be the rule escaped rather than an
  exception to it, exactly as an unmarked `chmod` is.

  Two of them also stopped being about the wrong repository. `_git_checked`
  marked a bare `git rev-parse HEAD` and `_log` a bare `git log`, neither
  pinned with `--git-dir`, in a module whose first stated invariant is that
  every git invocation is pinned. Run from anywhere else those two answer about
  whatever repository the caller happens to be standing in — so they were not
  merely failing to be repairs, they could exit `0` and be confidently about
  something else. Both are pinned now. Four tests in `tests/test_store.py`
  build the four conditions git refuses under, run a real entry point against
  each, and put every one of the four answers through `assertRepairsRun`, which
  is what stops any of this drifting back.

- **`canvas/refusal.py` is where the shape lives**, and it is a structure and
  not a convention: the next action is a constructor argument with no default,
  and a refusal that names neither a node nor anything else cannot be built.
  That is the same move `_write_and_commit` already makes for `--why`.
- **An operating system condition is a refusal like any other, at whatever
  depth.** A guard that asks the filesystem a question and acts on the answer
  is only ever true of the paths somebody thought of — one directory further
  up, a symlink, a path that changes between the check and the open, and the
  raw `OSError` came out as a traceback: Python's exit `1`, which this table
  gives to "the request is wrong against the store as it stands", and none of
  the four trailers. So the last `except` in both commands is `OSError` itself,
  and it prints this shape at exit `2`. What it carries:
  - the **errno and its `strerror`**, on `Canvas-About: errno 13 EACCES` and in
    the message, because `[Errno 13] Permission denied` and `[Errno 2] No such
    file` are opposite facts raised from the same `open()` and nothing else in
    the output tells them apart;
  - the **paths the error names** — both of them where there are two, as
    `rename` and `link` have;
  - a **`Canvas-Next:` chosen by errno**, because `chmod` is not the repair for
    a path that is not a directory and "create it" is not the repair for one
    that is already there. A permission refusal names the *shallowest* ancestor
    this process cannot traverse rather than the path the error carries,
    because `chmod u+rx <that path>` fails with `EACCES` in turn when the mode
    that refuses it is three levels up.
  This is the floor and not a replacement: every guard above it says something
  more specific, and a specific message is worth more than the generic one.
- **"Every refusal writes nothing" is a claim the outermost guard does not
  make.** It sits outside every function that knows what it had done, so rather
  than assert something it cannot see, it names the two commands that answer
  the question — `bin/canvas read <ledger-id>` and `git -C
  $OPENCLAW_WORKSPACE/state/canvas log`. `bin/canvas-validate`'s does say
  nothing was written, because that command reads and nothing it calls writes.

### What the store deliberately does not do

- **It does not reconcile or merge.** `--base` *is* enforced — see
  [the two branches](#--base-and-the-two-branches) — and enforcing it means
  refusing. A stale write is never merged into the current document, never
  rebased onto it, and never applied in part. The writer re-reads and
  re-decides, which is the one thing a CRDT cannot be made to do.
- **It does not diff a node structurally.** Both branches hand back git's own
  unified diff of the canvas file, scoped to a commit or to a range. One commit
  is one node, so a commit's patch already *is* that node's diff, and a
  node-granular differ would be restating git rather than using it.
- **It does not report a node's history beyond one node at a time.**
  `bin/canvas history <ledger_id> <node-id>` returns one node's edits, oldest
  first, with the reason for each. There is no verb that reports a whole
  canvas's history, no verb that reports a node's diffs, and none that reverts
  one: `git log`, `git show` and `git revert` are right there, and wrapping
  them would be restating git rather than using it.
  [`read --since`](#what-changed-since-a-sha---since) is inside this refusal and
  not against it. It is not a verb: the nine subcommands are still nine. It is
  bounded below by a sha the caller names and above by the head, scoped to one
  file, and it **has no default and no "all" spelling** — without it there is no
  news at all, so the tool never offers whole-canvas history as *the* question.
  What it adds is "what changed since the base I am holding". The honest edge,
  stated rather than argued away: a caller who names the canvas's own root commit
  gets everything since the birth of the canvas, which is that history arrived at
  from the other end — but the refused thing is a verb whose *job* is
  whole-canvas history, one reached for without holding a base, and this cannot
  be invoked without the caller asserting a base it holds. It does not diff a
  node structurally either: it hands back git's own unified diff of the file,
  from the same function the soft branch already calls.
- **It does not batch, and cannot be made to.** Nothing in it can touch two
  nodes in one commit, and the one function that puts a canvas on its path
  refuses a write worth more than the one node the commit names. There is no
  transaction, no multi-node payload and no whole-document verb to add one to.
- **It does not wire the ledger's `open` transition.** Nothing here knows the
  ledger exists: no path, no import, no subprocess, no read of `state/ledger`.
  That has not changed and is not going to. What has changed is on the other
  side of the call — `bin/task-ledger open` in
  [`malkovro/ledger-orchestrator`](https://github.com/malkovro/ledger-orchestrator)
  now runs `create` itself, from the `--problem` and `--expected-value` that
  transition already required, so a row's canvas is born with the row and
  `create` is no longer only driven by hand. This repository gained no
  dependency and no caller it has to keep in step with: it is a command-line
  tool, and something started running the command. If that caller goes away,
  nothing here notices.
- **It does not unfreeze.** [`freeze`](#ending-a-canvas) ends a canvas and
  nothing takes that back: there is no `unfreeze`, no `thaw` and no `reopen`,
  and those are unknown verbs at exit `2`. A ledger row whose task comes back
  gets a new ledger row and therefore a new canvas, linked to the frozen one.
  The frozen canvas is never deleted and never edited again — `read` and
  `history` go on working on it, and every write verb is refused at exit `1`.
  An `unfreeze` would make "read-only history" a claim with exceptions, and a
  reader would have to find the *last* lifecycle commit rather than any freeze.
- **It does not wire the ledger's `done` or `abandoned` transitions either.**
  `freeze` is driven by hand — and unlike `create` above, nothing calls it yet
  — and nothing here reads or writes `state/ledger`. Which of the two endings it
  was lives in the `--why` and in no field: one verb, and the semantics in the
  reason.
- **It does not shell out to `xmllint` and does not restate the vocabulary.**
  Every write goes through `canvas.validate.validate_file` at a temporary path
  and is renamed into place only once it validates, so an invalid canvas is
  never reachable as a canvas. `EnvironmentProblem` is "the validator cannot
  run" — exit `2` — and never "the document is invalid".
