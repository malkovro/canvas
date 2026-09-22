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

**`from_os_error` is the floor under all of it.** Every guard in the tool that
asks the filesystem a question before acting on the answer is an enumeration,
and an enumeration can always be extended by one: one directory further up, a
symlink, a path that changes between the check and the open. `from_os_error`
turns any `OSError` — `PermissionError`, `FileNotFoundError`,
`IsADirectoryError`, `NotADirectoryError`, `BrokenPipeError`, and the ones
nobody has met yet — into a refusal of this shape, so that the question "is
there any OS condition that leaves this tool as a traceback" is answered no by
construction rather than by a list. The specific guards stay: a message that
names the ledger id and says `chmod u+rx <that directory>` is better than the
generic one, and this is the floor, not a replacement for them.
"""

import errno
import os


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


# --------------------------------------------------------------------------
# The floor: any OS error, as a refusal of this shape
# --------------------------------------------------------------------------
#
# What a caller needs from an OS condition is which condition it was and what
# to do about it, and the errno is the only thing that answers the first
# honestly — `[Errno 13] Permission denied` and `[Errno 2] No such file` are
# opposite facts and the same `open()` raises both. So the errno and its
# `strerror` travel in the message, and the next action is chosen by errno
# rather than written once for whichever one somebody met first.

#: The next action, by errno. `%(path)s` is the first path the error carries,
#: `%(paths)s` all of them. Each is the imperative repair for *that* condition:
#: telling someone to `chmod` a path that is not a directory, or to create a
#: path that is already there, is a next action that provably does not succeed,
#: and a refusal whose next action does not succeed is the defect this whole
#: surface exists to close.
_OS_NEXT_ACTION = {
    errno.EACCES: (
        "make %(target)s %(need)s — `ls -ld %(target)s` shows "
        "who owns it and what its mode is, and `chmod %(mode)s %(target)s` is "
        "usually the repair%(blocked)s — and re-run"
    ),
    errno.EPERM: (
        "this process may not do that to %(target)s — `ls -ld %(target)s` "
        "names its owner and its mode; re-run as that user, or `chown` it to "
        "this one%(blocked)s, and re-run"
    ),
    errno.ENOENT: (
        "%(paths)s was there when the tool looked and is not there now, or a "
        "directory on the way to it is not there at all — `ls -ld %(path)s` "
        "says which; re-run, and if it is genuinely gone make it again with "
        "`bin/canvas create <ledger-id> --problem \"<the problem>\" "
        "--expected-value \"<the expected value>\"`"
    ),
    errno.ENOTDIR: (
        "something on the way to %(paths)s is not a directory, so no path "
        "through it can exist — `ls -l %(path)s` walks it; move or rename "
        "whatever is in the way, remake the directory, and re-run"
    ),
    errno.EISDIR: (
        "there is a directory at %(paths)s where this tool needs a file — "
        "`ls -ld %(path)s` shows it; move it aside and re-run"
    ),
    errno.EEXIST: (
        "something is already at %(paths)s — `ls -ld %(path)s` shows what; "
        "move it aside, or name a ledger id whose canvas does not exist yet, "
        "and re-run"
    ),
    errno.ELOOP: (
        "%(paths)s is reached through too many symbolic links, or through one "
        "that points at itself — `ls -l %(path)s` shows the chain; point it at "
        "a real file or remove it, and re-run"
    ),
    errno.ENAMETOOLONG: (
        "%(paths)s is longer than this filesystem allows — the ledger id "
        "becomes the file name, so re-run with a shorter one, or point "
        "OPENCLAW_WORKSPACE at a shallower directory"
    ),
    errno.ENOSPC: (
        "the filesystem holding %(paths)s is full — `df -h %(path)s` says by "
        "how much; free space on it and re-run"
    ),
    errno.EDQUOT: (
        "this user's disk quota on the filesystem holding %(paths)s is spent — "
        "free space or raise the quota, and re-run"
    ),
    errno.EROFS: (
        "the filesystem holding %(paths)s is mounted read-only — remount it "
        "writable, or point OPENCLAW_WORKSPACE at a workspace on a writable "
        "filesystem, and re-run"
    ),
    errno.EMFILE: (
        "this process has no file descriptor left to open a file with — raise "
        "the limit (`ulimit -n` shows it) and re-run"
    ),
    errno.ENFILE: (
        "this machine has no file descriptor left to open a file with — wait "
        "for the processes holding them to finish, or raise the system limit, "
        "and re-run"
    ),
    errno.EPIPE: (
        "the command reading this output closed it before the canvas had "
        "finished being written to it — re-run without the pipe, redirect to "
        "a file, or pipe into something that reads all of its input (`| cat | "
        "head -1` rather than `| head -1`)"
    ),
}

#: What a permission repair has to say depends on what the tool needed the path
#: for, and the errno does not carry that. `chmod u+rx` is the repair for a path
#: this process could not reach; a path it reached and could not *write* needs
#: `chmod u+w`, and telling a caller to run the other one is a next action that
#: provably does not succeed — the defect this whole surface exists to close.
#: The call site names which it needed; nothing here guesses.
_OS_PERMISSION_REPAIR = {
    "reach": ("reachable by this process", "u+rx"),
    "write": ("writable by this process", "u+w"),
}

#: When the errno is one this table has never met. Still concrete: it names the
#: path, it names the condition the operating system reported, and `ls -ld` is
#: the command that shows the state that produced it. A generic line is the
#: price of the guarantee being structural — the alternative is the traceback.
_OS_NEXT_ACTION_DEFAULT = (
    "the operating system reported that condition on %(paths)s and this tool "
    "has no specific repair for it — `ls -ld %(path)s` shows the state it is "
    "in, and the errno above names what was objected to; resolve that and "
    "re-run"
)

#: When the error carries no path at all. There is nothing to `ls`, so the next
#: action is the one thing that is still concrete: the store the tool works in.
_OS_NEXT_ACTION_NO_PATH = (
    "the operating system refused this command and named no path — the errno "
    "above says which condition it was; check the store with `ls -ld "
    "$OPENCLAW_WORKSPACE/state/canvas`, resolve it, and re-run"
)


def _os_error_paths(error):
    """Every path the error carries: `filename`, and `filename2` where there is
    one — `rename` and `link` fail on a pair and naming only the first sends a
    caller to look at the wrong end of it."""
    paths = []
    for attribute in ("filename", "filename2"):
        value = getattr(error, attribute, None)
        if value is None:
            continue
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        paths.append(str(value))
    return _once(paths)


def os_condition(error):
    """The errno and its `strerror`, as every refusal here prints them.

    `[Errno 13] Permission denied` and `[Errno 2] No such file or directory`
    are opposite facts raised from the same `open()`, and this string is what
    lets a caller tell them apart without guessing from the wording around it.
    """
    number = getattr(error, "errno", None)
    strerror = getattr(error, "strerror", None) or str(error)
    return "[Errno %s] %s" % ("none" if number is None else number, strerror)


def os_about(error, unless=()):
    """What an `OSError` contributes to a refusal's `about`: its paths and its
    errno. A caller that has the path but not the errno cannot tell a mode from
    a missing file, and one that has the errno but not the path cannot act.

    `unless` is the `about` the caller is already going to print. A path it has
    named — `canvas /x`, `file /x` — is not repeated under `path /x`; the errno
    always is, because nothing else in the refusal carries it.
    """
    said = " ".join(unless)
    number = getattr(error, "errno", None)
    named = errno.errorcode.get(number)
    return [
        "path %s" % path for path in _os_error_paths(error) if path not in said
    ] + [
        "errno %d %s" % (number, named) if named
        else "errno %s" % ("none" if number is None else number)
    ]


def blocking_ancestor(path):
    """The shallowest directory on the way to `path` that this process cannot
    read and traverse, or `None` when every one of them is fine.

    The reason a permission refusal names this and not the path the error
    carries. `open("$WS/state/canvas/rec.xml")` raises `EACCES` naming
    `rec.xml` when the mode that actually refuses it is on `state`, three
    levels up — and `chmod u+rx <rec.xml>`, which is what naming `rec.xml`
    tells a caller to run, fails with `EACCES` in turn, because it has to
    traverse the same directory to get there. A next action that cannot be run
    is the defect this surface exists to close, so the walk goes up until the
    filesystem stops objecting and names the first place it did.

    Root-first, because the shallowest one is the one that has to be repaired
    before any of the others can even be looked at. Bounded by the path itself
    and driven by what the filesystem answers, so it is not a check at a fixed
    depth by another name.
    """
    ancestors = []
    current = os.path.abspath(path)
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            break
        ancestors.append(parent)
        current = parent
    for directory in reversed(ancestors):
        if not os.access(directory, os.R_OK | os.X_OK):
            return directory
    return None


def os_next_action(error, aftermath=None, paths=None, need="reach"):
    """The imperative repair for this errno, naming the paths the error carries.

    One table for the whole tool, so a site that knows more than the outermost
    guard — it has the ledger id, it knows nothing was written — still gets the
    repair that matches the condition rather than writing its own guess at one.

    `paths` overrides the paths the repair points at, for the one case where
    the path the error names is not the path a caller can do anything about: a
    write goes to a temporary name beside the canvas, so an `OSError` from it
    names a file that does not exist and the thing that refused it is the
    directory. `need` says whether the caller needed to reach that path or to
    write to it, which is what decides the `chmod` — see
    `_OS_PERMISSION_REPAIR`.
    """
    paths = _once(list(paths)) if paths is not None else _os_error_paths(error)
    number = getattr(error, "errno", None)
    # The errno decides the repair; the paths only decide whether the repair
    # that errno calls for can still be stated. A broken pipe and a spent file
    # descriptor table carry no filename and do not need one — their repair is
    # about the process — so the no-path fallback is reached only when the
    # repair would have had to point at a path and there is none to point at.
    template = _OS_NEXT_ACTION.get(number, _OS_NEXT_ACTION_DEFAULT)
    if not paths and "%(path" in template:
        template = _OS_NEXT_ACTION_NO_PATH
    # `target` is what a permission repair has to be run against, which is not
    # always the path the error names: see `blocking_ancestor`.
    target = paths[0] if paths else ""
    blocked = ""
    needed, mode = _OS_PERMISSION_REPAIR[need]
    if paths and number in (errno.EACCES, errno.EPERM):
        ancestor = blocking_ancestor(paths[0])
        if ancestor is not None:
            target = ancestor
            # An ancestor that cannot be reached has to be made reachable
            # whatever the caller wanted the path below it for: `chmod u+w` on
            # a directory this process cannot traverse into does not help it
            # traverse into it.
            needed, mode = _OS_PERMISSION_REPAIR["reach"]
            blocked = (
                ". That directory is what refuses it, not %s itself: a "
                "directory that is not readable and traversable refuses "
                "everything underneath it however good the modes down there "
                "are" % paths[0]
            )
    next_action = template % {
        "path": paths[0] if paths else "",
        "paths": " and ".join(paths),
        "target": target,
        "blocked": blocked,
        "need": needed,
        "mode": mode,
    }
    if aftermath:
        next_action = "%s; %s" % (next_action, aftermath)
    return next_action


def from_os_error(kind, error, nodes=(), about=(), aftermath=None, need="reach"):
    """One `OSError`, as a refusal of `kind` — the tool's own shape.

    `kind` is the caller's own refusal class, so `bin/canvas` gets a
    `store.ToolProblem` and `bin/canvas-validate` an
    `EnvironmentProblem`: the entry point that catches this is the one that
    knows what its exit codes mean, and this function does not decide one.

    `nodes` and `about` are whatever the call site had in hand — the node the
    edit named, the ledger id it was for. The paths the error carries and the
    errno are added to `about` here, because those are the two things a caller
    cannot get anywhere else: the errno is what tells a permission problem from
    a missing one, and both `open()`s raise from the same line.

    `aftermath` is the one thing this function cannot work out — whether
    anything was written before the error. The caller says; where it does not,
    nothing is claimed, because "nothing was written" asserted by a guard that
    does not know is worse than saying nothing.
    """
    paths = _os_error_paths(error)
    where = " on %s" % " and ".join(paths) if paths else ""
    about = list(about)
    return kind(
        "the operating system refused this command%s: %s"
        % (where, os_condition(error)),
        os_next_action(error, aftermath=aftermath, need=need),
        nodes=nodes,
        about=about + os_about(error, unless=about),
    )
