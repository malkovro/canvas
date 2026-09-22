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
GitHub's `ubuntu-latest` image.

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
