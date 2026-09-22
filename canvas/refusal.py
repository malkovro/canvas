"""The shape every refusal takes, and the one place it is rendered.

`engineering-spec.md` section *What to copy* takes IWE's error surface
unconditionally: "A refusal names every node it matched and how to narrow,
because an agent can act on that and cannot act on the word 'refused'." This
module is that sentence made into a structure, so that it holds for the
refusals somebody writes next and not only for the ones written so far.

A refusal carries four things beyond its message:

- **`nodes`** — every node id involved. The ones the rejected write named, the
  ones it would have touched, the one that moved since `--base`. Not a summary:
  all of them.
- **`about`** — what it names when it has no node to name, and *as well as* the
  nodes where both apply. A refusal with no node is not exempt from naming what
  it is about: the ledger id, the file, the environment variable, the missing
  binary, the value that was rejected. Each entry reads `<what it is> <value>`,
  so `ledger id a-row`, `command git`, `option --base`.
- **`next_action`** — one concrete thing to do that would succeed, in the
  imperative, naming the command where there is one. Not what did not happen:
  "nothing was changed" is a fact about the past and an agent cannot act on it.
- **`details`** — the lines that belong under the message: validator
  diagnostics, a commit and its patch. Unchanged from what they already were.

**A refusal that names nothing is refused at construction.** `next_action` is a
positional argument with no default and `nodes` and `about` cannot both be
empty, so "this one has no node" has to be answered with the thing it names
instead rather than left out. That is the same move `_write_and_commit` already
makes for `--why` — a positional with no default is a rule the interpreter
keeps — applied to the surface instead of to the write.

Nothing here decides an exit code. The entry point that catches the refusal
decides that, and passes in what its own code means, because `bin/canvas` and
`bin/canvas-validate` document two different meanings for the same two numbers.
"""


def _once(values):
    """The values, in the order given, each of them once.

    A refusal composes its nodes from what the caller named and what it found,
    and the two overlap — a `move` whose target is the node being moved, two
    nodes sharing one container. One line per thing is what an agent reads.
    """
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


class Refused(Exception):
    """A refusal, with everything a caller needs to act on it.

    Subclassed rather than used directly: `store.Refusal` and
    `store.ToolProblem` are the two kinds `bin/canvas` exits on, and
    `validate.EnvironmentProblem` is `bin/canvas-validate`'s. What they share is
    this shape, and sharing it is what makes the shape hold for all of them.
    """

    def __init__(self, message, next_action, nodes=(), about=(), details=()):
        Exception.__init__(self, message)
        self.next_action = next_action
        self.nodes = _once(nodes)
        self.about = _once(about)
        self.details = list(details)
        if not self.next_action or not self.next_action.strip():
            raise ValueError(
                "a refusal states the next action that would succeed: %r" % message
            )
        if not self.nodes and not self.about:
            raise ValueError(
                "a refusal names the nodes it involves, or the thing it is "
                "about where it has no node: %r" % message
            )


#: The trailer block, in the same `Canvas-…:` idiom the commits and the success
#: output already use — `Canvas-Node:` is the name a node id is printed under
#: everywhere else in the tool, so a refusal naming one uses the same word.
def lines(prefix, refused, code, meaning):
    """Every line a refusal prints, in order. The caller writes them to stderr.

    The message first, prefixed with the command's name, then whatever details
    came with it, then the trailer block: one `Canvas-Node:` per node, one
    `Canvas-About:` per other thing named, the next action, and the exit code
    with what it means.

    The trailers come last so that the two lines a caller in trouble most needs
    — what to do, and which kind of wrong this was — are the last thing on
    stderr, and so that a long block of diagnostics or a patch cannot push them
    out of sight above it.
    """
    out = ["%s: %s" % (prefix, refused)]
    out.extend(refused.details)
    out.extend("Canvas-Node: %s" % node for node in refused.nodes)
    out.extend("Canvas-About: %s" % thing for thing in refused.about)
    out.append("Canvas-Next: %s" % refused.next_action)
    out.append("Canvas-Exit: %d — %s" % (code, meaning))
    return out
