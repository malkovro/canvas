"""The `bin/canvas` command line: the store and the read path.

Two verbs, and only two:

    canvas create <ledger_id> --problem TEXT --expected-value TEXT [--author TEXT]
    canvas read <ledger_id>

`replace`, `insert`, `remove` and `move` are not here, and neither is `--why`.
The read hands out the current sha; it does not enforce `--base` and does not
accept one. Those are separate tasks, and building them here would mean
building the thing the next task exists to change.

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

    return parser


def main(argv):
    """Exit 0 if it worked, 1 if the request is wrong against the store as it
    stands, 2 if the tool or its environment is wrong."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "handler", None) is None:
        parser.print_usage(sys.stderr)
        sys.stderr.write("canvas: a verb is required: create, read\n")
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
