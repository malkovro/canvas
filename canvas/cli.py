"""The `bin/canvas` command line: the store, the read path and the four verbs.

Seven subcommands, and no more:

    canvas create  <ledger_id> --problem TEXT --expected-value TEXT
    canvas read    <ledger_id>
    canvas history <ledger_id> <node-id>
    canvas replace <ledger_id> <node-id> --why TEXT [--base SHA]
    canvas insert  <ledger_id> (--after <node-id> | --into <container-id>) --why TEXT [--base SHA]
    canvas remove  <ledger_id> <node-id> --why TEXT [--base SHA]
    canvas move    <ledger_id> <node-id> (--after <node-id> | --into <container-id>) --why TEXT [--base SHA]

Four editing verbs, and three reads: `create` is the only one of the other
three that writes. `history` reads the log the four verbs write, and `read`
reads the document they leave behind.

There is no `resolve`, no `collapse` and no `supersede`:
the semantics live in the reason, not in a verb name. There is no selector of
any kind either — addressing is by explicit node id, which is the property that
makes IWE's `--expect` match-count guard unnecessary, and the day a selector
exists `--expect` has to exist beside it.

`--why` is required by all four, with no default and no fallback. An absent one
is argparse's own refusal and an empty or whitespace-only one is
`store.require_reason`'s; both exit 2 and write nothing. The rule itself lives
in `canvas/store.py`, not here, because it is a property of the write path and
not of this command line.

The read hands out the current sha and all four verbs take it back as
`--base`: the sha the edit was decided against. It is optional, and an omitted
one asks for no staleness check rather than standing for the current head. What
a declared one buys is the two branches — a refusal carrying that node's diff
when the node named here moved since, and the diff of everything else when it
did not — and the rule itself lives in `canvas/store.py`, not here, for the
same reason `--why` does: it is a property of the write path. What is here is
the flag, and the soft branch's news printed after the two lines that report
success, because the todo asks for it in the same output.

This is the only module that decides an exit code.
"""

import argparse
import sys

from canvas import store


def _create(args):
    path, sha = store.create(
        args.ledger_id, args.problem, args.expected_value, args.author
    )
    sys.stdout.write("Canvas-Base: %s\nCanvas-File: %s\n" % (sha, path))
    return 0


def _read(args):
    sha, body, problems = store.read(args.ledger_id)
    # The sha first, on one line, under the same name the next write declares it
    # under. One name for one thing: the value a read hands out is literally the
    # value the next write puts in `--base` and the commit records. Full 40
    # characters — handing out an abbreviation as an identity key is a hazard as
    # the log grows, and git will still resolve an abbreviation supplied later.
    #
    # The cost, stated because it is real: stdout is not itself a valid XML
    # document. `canvas read <id> | tail -n +2` is the document alone, byte for
    # byte what is on disk.
    out = sys.stdout.buffer if hasattr(sys.stdout, "buffer") else sys.stdout
    out.write(("Canvas-Base: %s\n" % sha).encode("utf-8"))
    out.write(body)
    out.flush()
    for problem in problems:
        sys.stderr.write("%s\n" % problem)
    return 1 if problems else 0


def _history(args):
    """Print one node's edits, oldest first: sha, author, verb and reason.

    The node id once, at the top, under the same name every other verb prints
    it under — then one block per edit, oldest first, so the blocks read as the
    story of how the node got to its current text.

    The reason is the commit subject's and is printed last in its block, after
    the verb, because a reason is free text and everything before it is not. An
    edit made before a `move` is in the list like any other: the move kept the
    id, so the query that finds the move finds everything the id ever did.
    """
    edits = store.history(args.ledger_id, args.node_id)
    out = ["Canvas-Node: %s\n" % args.node_id]
    for edit in edits:
        out.append(
            "Canvas-Commit: %s\nCanvas-Author: %s\n%s: %s\n"
            % (edit.sha, edit.author, edit.verb, edit.reason)
        )
    sys.stdout.write("\n".join(out))
    return 0


def _edited(args, node_id, sha, news=None):
    """What every editing verb prints: the node it changed and the new sha.

    The node id first, because `insert` mints one the caller did not know, and
    then the sha under the same name a read hands it out under and the commit
    records it under. One name for one thing.

    Then, when a declared `--base` turned out to be behind the head and the node
    this write named had not moved, the soft branch's news: what changed in
    between, on stdout, in the same output that reports success. The writer is
    told what it did not know in the same breath as being told it succeeded,
    which is the branch's whole point and is why it is not on stderr.

    "Succeeds silently" is the case where there is no news — the two lines
    above and nothing else. It is not no output at all: those two lines are the
    verb's ordinary success output, and the sha on the second is what the next
    write bases on.
    """
    lines = ["Canvas-Node: %s\n" % node_id, "Canvas-Base: %s\n" % sha]
    lines.extend("%s\n" % line for line in news or ())
    sys.stdout.write("".join(lines))
    return 0


def _replace(args):
    sha, news = store.replace(
        args.ledger_id,
        args.node_id,
        args.why,
        node_type=args.node_type,
        text=args.text,
        title=args.title,
        href=args.href,
        author=args.author,
        base=args.base,
    )
    return _edited(args, args.node_id, sha, news)


def _insert(args):
    node_id, sha, news = store.insert(
        args.ledger_id,
        args.why,
        after=args.after,
        into=args.into,
        node_type=args.node_type,
        text=args.text,
        title=args.title,
        href=args.href,
        author=args.author,
        base=args.base,
    )
    return _edited(args, node_id, sha, news)


def _remove(args):
    sha, news = store.remove(
        args.ledger_id,
        args.node_id,
        args.why,
        author=args.author,
        base=args.base,
    )
    return _edited(args, args.node_id, sha, news)


def _move(args):
    sha, news = store.move(
        args.ledger_id,
        args.node_id,
        args.why,
        after=args.after,
        into=args.into,
        author=args.author,
        base=args.base,
    )
    return _edited(args, args.node_id, sha, news)


def _add_why(parser):
    """`--why`, required, no default, on every one of the four verbs.

    `required=True` is what makes an absent `--why` argparse's own exit 2 with
    nothing run. An empty or whitespace-only one gets past argparse — it is a
    supplied argument — and is refused by `store.require_reason` before any
    canvas is written. There is nothing here that could generate one.
    """
    parser.add_argument(
        "--why",
        required=True,
        metavar="TEXT",
        help="why this edit is being made; required, with no default",
    )


def _add_base(parser):
    """`--base`, optional, on every one of the four verbs.

    The sha this edit was decided against, as a `read` printed it. Optional,
    and an omitted one is **not** a base of "now": it is the absence of the
    question, so nothing is compared and the verb behaves as it did before the
    staleness rule existed. That is not `--why`'s shape and deliberately not —
    `--why` has no value the tool could correctly compute, so an absent one is a
    malformed invocation, while an absent `--base` asks for no check and there
    is no silently wrong answer hiding in it.

    `create` does not get one. The birth of a canvas has no prior state it
    could have been decided against, which is also why its root commit writes
    no `Canvas-Base:` trailer.
    """
    parser.add_argument(
        "--base",
        metavar="SHA",
        help=(
            "the commit sha this edit was decided against, as read printed "
            "it; refused with that node's diff if the node named here moved "
            "since, and told what else changed if anything else did"
        ),
    )


def _add_author(parser):
    parser.add_argument(
        "--author",
        help="the Canvas-Author trailer; defaults to '<user> | by-hand'",
    )


def _add_position(parser):
    """`--after` and `--into`, exactly one of them, per node-identity.md section 6."""
    position = parser.add_mutually_exclusive_group(required=True)
    position.add_argument(
        "--after",
        metavar="NODE-ID",
        help="immediately after that node, in that node's parent",
    )
    position.add_argument(
        "--into",
        metavar="CONTAINER-ID",
        help=(
            "as the last child of that container, which is how the first "
            "position of an empty one is named; 'root' names the canvas itself"
        ),
    )


def _add_payload(parser, default_type):
    """How new content arrives, which no spec settled and this command line does.

    A node type by name, and the two attributes the closed vocabulary has that
    are not identity: `<section>`'s title and `<link>`'s href. Named flags
    rather than a general `--attr name=value`, because a general one could set
    `id` and `v`, and `insert` mints ids — a caller cannot supply one.

    What element names exist, and which of these each one requires, is
    `schema/canvas.rng`'s business. A `--type decision` builds a `<decision>`
    node and the validator refuses to let it reach the canvas's path, which is
    the right division of labour: the vocabulary is written down once.
    """
    parser.add_argument(
        "--type",
        dest="node_type",
        default=default_type,
        metavar="NAME",
        help=(
            "the node type to write%s"
            % (
                "; defaults to text" if default_type
                else "; defaults to the type the node already has"
            )
        ),
    )
    parser.add_argument("--text", help="the node's character data")
    parser.add_argument("--title", help="the title attribute a <section> requires")
    parser.add_argument("--href", help="the href attribute a <link> requires")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="canvas",
        description="The canvas store: one XML file per ledger row, git-backed.",
    )
    verbs = parser.add_subparsers(dest="verb")

    create = verbs.add_parser(
        "create",
        help="make the canvas for a ledger row, with its first nodes",
        description=(
            "Make the canvas for a ledger row. Three commits: the root alone, "
            "then the problem, then the expected value, each node in its own "
            "commit. Refuses if a canvas for that ledger id already exists."
        ),
    )
    create.add_argument("ledger_id", help="the ledger row this canvas belongs to")
    create.add_argument(
        "--problem", required=True, help="the problem the ledger row states"
    )
    create.add_argument(
        "--expected-value",
        required=True,
        dest="expected_value",
        help="the expected value the ledger row states",
    )
    create.add_argument(
        "--author",
        help="the Canvas-Author trailer; defaults to '<user> | by-hand'",
    )
    create.set_defaults(handler=_create)

    read = verbs.add_parser(
        "read",
        help="print the canvas and the sha to write against",
        description=(
            "Print the current commit sha, then the canvas document. Writes "
            "nothing and commits nothing."
        ),
    )
    read.add_argument("ledger_id", help="the ledger row whose canvas to print")
    read.set_defaults(handler=_read)

    history = verbs.add_parser(
        "history",
        help="print one node's edits, oldest first, with the reason for each",
        description=(
            "Print every edit that named this node, oldest first: the commit "
            "sha, the author, the verb and the reason. The reason lives in "
            "the commit subject and nowhere else, which is why this reads the "
            "log. Edits made before a move are included — a move keeps the "
            "node's id. Writes nothing, commits nothing, and does not "
            "initialise a repository."
        ),
    )
    history.add_argument("ledger_id", help="the ledger row this canvas belongs to")
    history.add_argument(
        "node_id", metavar="node-id", help="the node whose history to print"
    )
    history.set_defaults(handler=_history)

    replace = verbs.add_parser(
        "replace",
        help="replace one node, possibly with a node of a different type",
        description=(
            "Replace one node's content. The node keeps its id, including "
            "across a type change — an options <table> settling into a <text> "
            "is this command, and it is how a decision gets made in a canvas. "
            "The type defaults to the one the node already has. One commit."
        ),
    )
    replace.add_argument("ledger_id", help="the ledger row this canvas belongs to")
    replace.add_argument("node_id", metavar="node-id", help="the node to replace")
    _add_payload(replace, None)
    _add_why(replace)
    _add_base(replace)
    _add_author(replace)
    replace.set_defaults(handler=_replace)

    insert = verbs.add_parser(
        "insert",
        help="add one node at a named position",
        description=(
            "Add one node, born at v=1 with a freshly minted id. The only verb "
            "that mints. One commit."
        ),
    )
    insert.add_argument("ledger_id", help="the ledger row this canvas belongs to")
    _add_position(insert)
    _add_payload(insert, "text")
    _add_why(insert)
    _add_base(insert)
    _add_author(insert)
    insert.set_defaults(handler=_insert)

    remove = verbs.add_parser(
        "remove",
        help="take one node out of the document",
        description=(
            "Take one node out. Its id is retired and never reminted, and the "
            "removing commit is the last entry in its history. A node that "
            "still has children is refused. One commit."
        ),
    )
    remove.add_argument("ledger_id", help="the ledger row this canvas belongs to")
    remove.add_argument("node_id", metavar="node-id", help="the node to remove")
    _add_why(remove)
    _add_base(remove)
    _add_author(remove)
    remove.set_defaults(handler=_remove)

    move = verbs.add_parser(
        "move",
        help="change one node's position and nothing else",
        description=(
            "Move one node. Its id, its content, its type and its children are "
            "unchanged; only where it sits changes. One commit."
        ),
    )
    move.add_argument("ledger_id", help="the ledger row this canvas belongs to")
    move.add_argument("node_id", metavar="node-id", help="the node to move")
    _add_position(move)
    _add_why(move)
    _add_base(move)
    _add_author(move)
    move.set_defaults(handler=_move)

    return parser


def main(argv):
    """Exit 0 if it worked, 1 if the request is wrong against the store as it
    stands, 2 if the tool or its environment is wrong."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "handler", None) is None:
        parser.print_usage(sys.stderr)
        sys.stderr.write(
            "canvas: a verb is required: create, read, history, replace, "
            "insert, remove, move\n"
        )
        return 2
    try:
        return args.handler(args)
    except store.Refusal as refusal:
        sys.stderr.write("canvas: %s\n" % refusal)
        for detail in refusal.details:
            sys.stderr.write("%s\n" % detail)
        return 1
    except store.ToolProblem as problem:
        sys.stderr.write("canvas: %s\n" % problem)
        return 2
