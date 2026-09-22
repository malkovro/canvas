"""The canvas store: where a canvas lives, and how it is read and written.

One canvas per ledger row, at

    $OPENCLAW_WORKSPACE/state/canvas/<ledger_id>.xml

beside `state/ledger/<ledger_id>.json`. The engineering spec gives that path;
it is not chosen here.

`state/canvas` is **one git repository** holding every ledger row's file.
`node-identity.md` section 1 settles that: ids are unique across the whole
repository, and the uniqueness check is the history itself with no path filter,
so a repository per ledger id would path-scope that check by accident and hand
out an id another canvas already used.

Every git invocation is pinned with `--git-dir` and `--work-tree`, never a bare
`git` relying on discovery from the working directory. If `state/canvas` ever
sits inside an outer git repository — someone version-controlled their
workspace — discovery would find the outer `.git` while the local "is there a
repo here" check still said no, and the commits would land in the wrong
repository. Pinning makes that impossible to express.

Every write is validated through `canvas.validate.validate_file` at a temporary
path and only then renamed into place, so an invalid canvas is never reachable
at the canvas's own path, let alone committed.

**No canvas is ever written without a reason.** `_write_and_commit` is the
only function that puts a canvas on its real path, and it takes the reason as
an argument and calls `require_reason` before it writes a byte. The rule is a
property of the write path itself, not of the command line above it: a future
caller that never goes near `canvas/cli.py` cannot write an unexplained edit,
because there is no function here that will do it. `create`'s three commits
carry their reasons the same way the four verbs carry `--why`.

**No canvas is ever written more than one node at a time**, and this is the
same claim in the same place. `_write_and_commit` compares the document it is
about to write against the document on disk and refuses unless exactly the node
its `Canvas-Node:` trailer names is the one that differs. A whole-document
rewrite is not a verb that was left out of `canvas/cli.py`; it is a write this
function will not perform, for any caller, from any import path.

**The supported write surface of this module is five functions**: `create`,
`insert`, `replace`, `remove` and `move`. Each of them takes a ledger id, a
reason and at most one node id, and each of them produces exactly one commit
per node it changes. There is deliberately no public function that takes a
document: a caller that hands in a whole tree is expressing a whole-document
rewrite, and the way to make that inexpressible is not to offer the parameter.
`_write_and_commit` is private for that reason and guarded anyway, because a
leading underscore is a convention and the guard is a refusal.

**No canvas is ever written against a base the writer no longer holds.** A
write may declare the sha it was decided against, and `_check_base` then splits
on what moved in between: the node this write names moved and the write is
refused, carrying that node's diff, before anything is minted, written or
committed; only something else moved and the write applies, with the news of it
handed back to the caller to print beside its success; nothing moved and there
is nothing to say. Nothing is reconciled and nothing is merged. The refusal is
the feature.
"""

import collections
import os
import re
import secrets
import stat
import subprocess

from canvas import document
from canvas import refusal
from canvas.validate import EnvironmentProblem, validate_file


class Refusal(refusal.Refused):
    """The request is wrong against the store as it stands. Exit 1.

    The canvas already exists; there is no canvas for that ledger id; the
    document is invalid. Re-read and re-decide. Carries the diagnostics that
    say which, where there are any.

    A `refusal.Refused`, so it also carries every node it involves, what it is
    about where it has no node, and the next action that would succeed —
    `canvas/refusal.py` has the argument for why those are the structure and
    not a convention. The message says what is wrong and why; the next action
    says what to do, and it is stated once, there.
    """


class ToolProblem(refusal.Refused):
    """The tool or its environment is wrong. Exit 2. Do not touch the canvas.

    Carries the same four things a `Refusal` does. It had none of them before —
    not even details — which is why `--why is required and must not be empty`
    could not name the node the edit was for even though the node was on the
    command line.
    """


# A ledger id becomes a filename, so it has to be one. This is what stops
# `canvas read ../../../etc/passwd` from escaping state/canvas/. Every ledger id
# in the live workspace matches: a hand-written slug, or bc-<todo-id>-<slug>.
_LEDGER_ID = re.compile(r"[A-Za-z0-9._-]+\Z")

# node-identity.md section 1: four characters, the first a lowercase letter, the
# remaining three from lowercase letters and digits with the visually confusable
# l, 1, o, 0 and i excluded. The exclusion is attached to "remaining three", so
# the first character is the full alphabet — as schema/canvas.rng's
# [a-z][a-hj-km-np-z2-9]{3} also has it.
_FIRST_CHARACTER = "abcdefghijklmnopqrstuvwxyz"
_REMAINING_CHARACTERS = "abcdefghjkmnpqrstuvwxyz23456789"

# 26 * 31^3 = 774,206 ids. A hundred draws that all collide means something is
# wrong with the check, not that the space is full.
_MINT_ATTEMPTS = 100


# --------------------------------------------------------------------------
# Where things are
# --------------------------------------------------------------------------


def canvas_directory():
    """`$OPENCLAW_WORKSPACE/state/canvas`, or a ToolProblem saying why not.

    There is deliberately no default. A tool that falls back to
    `~/.openclaw/workspace` writes real state whenever a caller forgets the
    variable — silently, onto production data. A tool that falls back to the
    working directory scatters canvases wherever it happened to be invoked, and
    the "one fact, one place" property is gone.
    """
    workspace = os.environ.get("OPENCLAW_WORKSPACE")
    if not workspace:
        raise ToolProblem(
            "OPENCLAW_WORKSPACE is not set; it must name the workspace whose "
            "state/canvas holds the canvases",
            "export OPENCLAW_WORKSPACE=<the workspace directory> and re-run; "
            "there is deliberately no default, because a tool that guesses one "
            "writes real state wherever it was invoked",
            about=["environment variable OPENCLAW_WORKSPACE"],
        )
    if not os.path.isdir(workspace):
        raise ToolProblem(
            "OPENCLAW_WORKSPACE is not a directory: %s" % workspace,
            "point OPENCLAW_WORKSPACE at a directory that exists and re-run; "
            "nothing was created, for the same reason there is no default",
            about=[
                "environment variable OPENCLAW_WORKSPACE",
                "value %s" % workspace,
            ],
        )
    return os.path.join(workspace, "state", "canvas")


def canvas_path(canvas_dir, ledger_id):
    """The file for one ledger row, or a ToolProblem if the id is not one."""
    if not _LEDGER_ID.match(ledger_id) or ledger_id.startswith("."):
        raise ToolProblem(
            "not a usable ledger id: %r; a ledger id is one or more of "
            "[A-Za-z0-9._-] and does not start with a dot" % ledger_id,
            "re-run naming a ledger id of [A-Za-z0-9._-] that does not start "
            "with a dot; it becomes the name of a file in state/canvas, which "
            "is what stops one escaping that directory",
            about=["ledger id %r" % ledger_id],
        )
    return os.path.join(canvas_dir, ledger_id + ".xml")


# --------------------------------------------------------------------------
# The three refusals every entry point can reach
# --------------------------------------------------------------------------
#
# `read`, `history` and the four verbs each begin by asking the same three
# questions of the store — is there a canvas for this ledger id, is there a
# repository, does it have a commit — and each used to answer them with its own
# copy of the same sentence. Three copies of one string is three places for the
# next action to be added to two of.


#: What `os.stat` found where a canvas belongs, for a refusal to name. Not an
#: exhaustive taxonomy of st_mode: what a caller needs is enough to recognise
#: the thing and move it out of the way. No symlink entry, because `os.stat`
#: follows them — a link to a directory reads as a directory, and a link to
#: nothing raises ENOENT, which is the right answer for it: a write renames
#: over the link and succeeds.
_NOT_A_FILE = (
    (stat.S_ISDIR, "a directory"),
    (stat.S_ISFIFO, "a named pipe"),
    (stat.S_ISSOCK, "a socket"),
    (stat.S_ISBLK, "a block device"),
    (stat.S_ISCHR, "a character device"),
)


def _what_is_there(mode):
    for predicate, name in _NOT_A_FILE:
        if predicate(mode):
            return name
    return "not a regular file"


def _no_canvas(ledger_id, path):
    """No canvas for that ledger id. A fact about the store, so exit 1.

    Unless it is not a fact. `os.path.isfile` answers False for a canvas that
    is not there, for one this process is not allowed to look for, and for a
    directory or a symlink loop sitting where the canvas belongs — four
    different states flattened into one bit, and "no canvas for that ledger id"
    is true of exactly one of them. The others make it a false statement whose
    next action, `create` it, provably does not succeed: `create` refuses in
    turn, at a different exit code, saying something different again.

    So the question is put to the filesystem rather than inferred from it.
    `os.stat` answers with the thing itself or with an errno, and `ENOENT` is
    the only errno that means absent — every other one means this process could
    not find out, which is a different refusal at a different exit code.

    This used to test `os.path.dirname(path)`: one level, with
    `os.path.isdir(directory) and not os.access(directory, R_OK | X_OK)`. That
    is right for the canvas's own directory and wrong for everything above it,
    because an unreadable *grandparent* makes `os.path.isdir` itself answer
    False, the guard never fires, and the tool reports a canvas absent that it
    has no way of knowing anything about. A test at a fixed depth can always be
    defeated by one more directory; asking the filesystem cannot.
    """
    try:
        found = os.stat(path)
    except FileNotFoundError:
        # The one errno that means what this refusal is about to say.
        return Refusal(
            "no canvas for ledger id %s: nothing at %s" % (ledger_id, path),
            "create it with `bin/canvas create %s --problem \"<the problem>\" "
            "--expected-value \"<the expected value>\"`, or re-run with the ledger "
            "id whose canvas you meant" % ledger_id,
            about=["ledger id %s" % ledger_id, "canvas %s" % path],
        )
    except OSError as error:
        return ToolProblem(
            "cannot tell whether there is a canvas for ledger id %s: looking "
            "at %s was refused: %s"
            % (ledger_id, path, refusal.os_condition(error)),
            refusal.os_next_action(
                error,
                aftermath=(
                    "nothing was read, written or committed, and whether that "
                    "canvas exists is still unknown"
                ),
            ),
            about=["ledger id %s" % ledger_id, "canvas %s" % path]
            + refusal.os_about(error, unless=["canvas %s" % path]),
        )
    if stat.S_ISREG(found.st_mode):
        # `os.path.isfile` said no and `os.stat` says yes, so the store changed
        # in between. Not a request to re-decide: the same request may well
        # work now.
        return ToolProblem(
            "the canvas for ledger id %s appeared at %s between the check for "
            "it and the look at it" % (ledger_id, path),
            "re-run the same command; the canvas is there now, and this "
            "refusal is the tool declining to act on a store that changed "
            "under it rather than guess which state it meant",
            about=["ledger id %s" % ledger_id, "canvas %s" % path],
        )
    # Something is there. "Nothing at <path>" would be false, and `create`,
    # which is what a caller told there is nothing would reach for, refuses
    # this with a different message again.
    return ToolProblem(
        "there is no canvas for ledger id %s at %s, but there is something "
        "there: %s" % (ledger_id, path, _what_is_there(found.st_mode)),
        "move %s out of the way — `ls -ld %s` shows what it is — and then "
        "`bin/canvas create %s --problem \"<the problem>\" --expected-value "
        "\"<the expected value>\"`; a canvas is a regular file and this store "
        "will not write over whatever that is" % (path, path, ledger_id),
        about=["ledger id %s" % ledger_id, "canvas %s" % path],
    )


def _not_a_repository(canvas_dir, wanted):
    """`state/canvas` is not a git repository. The tool's world is wrong: exit 2."""
    return ToolProblem(
        "%s is not a git repository, so it has no %s" % (canvas_dir, wanted),
        "make the first canvas with `bin/canvas create <ledger-id> --problem "
        "\"<the problem>\" --expected-value \"<the expected value>\"`; that is "
        "the only thing here that initialises the repository, and a read never "
        "writes one",
        about=["canvas repository %s" % canvas_dir],
    )


def _no_commits(canvas_dir, wanted):
    """The repository is there and empty. Also exit 2, and the same answer."""
    return ToolProblem(
        "%s has no commits, so it has no %s" % (canvas_dir, wanted),
        "make the first canvas with `bin/canvas create <ledger-id> --problem "
        "\"<the problem>\" --expected-value \"<the expected value>\"`; until one "
        "commit exists there is no sha for anything to be written against",
        about=["canvas repository %s" % canvas_dir],
    )


# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------


def _no_git(error):
    """The one refusal for `git` not being runnable, wherever it is found.

    Every git invocation in this module raises this one, `ensure_repository`'s
    `git init` included. It used to run outside `_git` and its `OSError` left
    as a traceback — exit 1, where `README.md` says a missing `git` is exit 2 —
    so a caller following the documented contract would re-read and re-decide
    forever over a tool that is simply not installed.
    """
    return ToolProblem(
        "cannot run git: %s" % error,
        "put git on PATH and re-run; the canvas store is a git repository, so "
        "nothing can be read, written or created until git is there",
        about=["command git"],
    )


def _cannot_read(path, error, ledger_id=None, node_id=None):
    """The one refusal for a canvas that is there and cannot be read.

    `os.path.isfile` answers True for a file whose mode is `000`, so the "no
    canvas for this ledger id" guard passes and the read below is where an
    ordinary permission problem lands. Exit `2` and not `1`: the store is
    intact and this process cannot see it, so "the request is wrong against the
    store as it stands; re-read and re-decide" is not merely unhelpful but
    wrong — it invites a caller to retry a request that was fine, against a
    canvas it still cannot read.
    """
    return ToolProblem(
        "cannot read %s: %s" % (path, error),
        "make that file readable — `ls -l %s` shows who owns it and what its "
        "mode is, and `chmod u+r %s` is usually the repair — and re-run; the "
        "canvas is there and unchanged, nothing was written and nothing was "
        "committed" % (path, path),
        nodes=[node_id] if node_id is not None else [],
        about=(["ledger id %s" % ledger_id] if ledger_id is not None else [])
        + ["canvas %s" % path],
    )


def _cannot_write(path, error, node_id=None):
    """The one refusal for a canvas directory that cannot be written.

    Every write this store makes goes to a temporary name beside the canvas and
    is renamed onto it, so the directory's own mode is what a write needs and
    what it is refused for. Exit `2`, and for the same reason `_cannot_read`
    is: nothing about the request is wrong.
    """
    directory = os.path.dirname(path) or "."
    return ToolProblem(
        "cannot write %s: %s" % (path, error),
        "make %s writable — `ls -ld %s` shows who owns it and what its mode "
        "is, and `chmod u+w %s` is usually the repair — and re-run; nothing "
        "was written and nothing was committed"
        % (directory, directory, directory),
        nodes=[node_id] if node_id is not None else [],
        about=["canvas %s" % path, "directory %s" % directory],
    )


def _git(canvas_dir, *arguments):
    """Run git against the canvas repository and nothing else."""
    command = [
        "git",
        "--git-dir=%s" % os.path.join(canvas_dir, ".git"),
        "--work-tree=%s" % canvas_dir,
    ] + list(arguments)
    try:
        return subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except OSError as error:
        raise _no_git(error)


def _git_checked(canvas_dir, *arguments):
    result = _git(canvas_dir, *arguments)
    if result.returncode != 0:
        raise ToolProblem(
            "git %s exited %d: %s"
            % (
                " ".join(arguments),
                result.returncode,
                result.stderr.decode("utf-8", "replace").strip(),
            ),
            "run `git %s` against %s yourself to see what it objects to, and "
            "repair the repository; nothing was written"
            % (" ".join(arguments), canvas_dir),
            about=["canvas repository %s" % canvas_dir, "command git"],
        )
    return result.stdout.decode("utf-8", "replace")


def is_repository(canvas_dir):
    """A single local check. No ancestor discovery of any kind."""
    return os.path.isdir(os.path.join(canvas_dir, ".git"))


def ensure_repository(canvas_dir):
    """Initialise the canvas repository on first use. Never over an existing one.

    Returns True if it was created here. An existing repository is not
    re-initialised, not reconfigured, not renamed and not touched.
    """
    if is_repository(canvas_dir):
        return False
    try:
        os.makedirs(canvas_dir, exist_ok=True)
    except OSError as error:
        raise ToolProblem(
            "cannot create %s: %s" % (canvas_dir, error),
            "make that directory creatable — the workspace above it has to "
            "exist and be writable — and re-run; nothing was written",
            about=["directory %s" % canvas_dir],
        )
    # `git init <path>` names the path outright, so this does not depend on the
    # working directory either. -b main matches the code repository's default
    # branch and silences git's init.defaultBranch advice.
    try:
        result = subprocess.run(
            ["git", "init", "-b", "main", "-q", "--", canvas_dir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        # The same refusal `_git` gives, and exit 2 like it. This call cannot go
        # through `_git`, which pins --git-dir at a repository that does not
        # exist yet, so it catches the same OSError here rather than letting it
        # out as a traceback and Python's exit 1.
        raise _no_git(error)
    if result.returncode != 0:
        raise ToolProblem(
            "cannot initialise a git repository at %s: %s"
            % (canvas_dir, result.stderr.decode("utf-8", "replace").strip()),
            "run `git init -b main -- %s` yourself to see what it objects to, "
            "and re-run; no canvas was created" % canvas_dir,
            about=["directory %s" % canvas_dir, "command git init"],
        )
    return True


def head_sha(canvas_dir):
    """The repository head, or None when it has no commits yet.

    The *repository* head, not the file's last-touching commit. That is what
    `--base` is compared against, and it is what makes the sha a read hands out
    usable as the base of the next write with no second lookup.
    """
    result = _git(canvas_dir, "rev-parse", "HEAD")
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", "replace").strip()


def _configured(canvas_dir, key, fallback):
    result = _git(canvas_dir, "config", "--get", key)
    value = result.stdout.decode("utf-8", "replace").strip()
    return value if result.returncode == 0 and value else fallback


# --------------------------------------------------------------------------
# Which commits name a node
# --------------------------------------------------------------------------
#
# `node-identity.md` section 4: a node's entire life is exactly the set of
# commits whose `Canvas-Node:` trailer names it. Everything below reads that
# set — `history_length` counts it, `is_free` asks whether it is empty, and
# `history` returns it — so it is read in one place and the three cannot
# disagree about what a node's history is.
#
# **The match is on the trailer's value, for equality.** The documented
# `git log --grep='Canvas-Node: b7'` is a substring match on the whole commit
# message, and ids are four characters, so it answers for `b7pk` when it was
# asked about `b7`, and it counts a commit whose reason merely quotes the
# string `Canvas-Node: b7pk` as an edit to a node it never touched. Both are
# reachable by following the documentation. `%(trailers:key=...)` reads the
# trailer block git itself parses — the message's last paragraph — and the
# value is then compared for equality here, so a prefix of an id, a longer id
# that starts with it, and a reason quoting the trailer text are all excluded.
# The anchored `--grep` below is a pre-filter on top of that and never the
# authority: it narrows what the log prints, and the equality decides.

#: A node id safe to interpolate into a POSIX extended regular expression. Ids
#: are `[a-z][a-hj-km-np-z2-9]{3}`, so a real one always is; an id typed at the
#: command line need not be, and one carrying regex metacharacters skips the
#: pre-filter rather than being rejected. It names no node either way, and
#: "there is no such node" is the answer it deserves.
_SAFE_IN_A_PATTERN = re.compile(r"\A[A-Za-z0-9_-]+\Z")

#: One record per commit: sha, subject, the Canvas-Node values, the
#: Canvas-Author values. `%x1f` between fields and `%x1e` between records, which
#: is what `_FIELD` and `_RECORD` split on; `%x1d` between repeated values of
#: one trailer. All three are control characters a commit message written by
#: this store cannot contain, so a reason with colons, newlines or pipes in it
#: cannot be mistaken for a field boundary.
_FIELD = "\x1f"
_RECORD = "\x1e"
_LOG_FORMAT = (
    "%H%x1f%s%x1f"
    "%(trailers:key=Canvas-Node,valueonly,separator=%x1d)%x1f"
    "%(trailers:key=Canvas-Author,valueonly,separator=%x1d)%x1e"
)


class _Record(collections.namedtuple("_Record", "sha subject named author")):
    """One commit, as `_LOG_FORMAT` prints it.

    The sha, the whole commit subject, the values of its `Canvas-Node:`
    trailers, and its author line. Every log query below decodes into this, so
    the ones that ask different questions cannot disagree about what a commit's
    trailers say.
    """


class Edit(collections.namedtuple("Edit", "sha verb reason author")):
    """One commit that named a node: what it did, why, and who did it.

    The reason is the commit subject's, because that is the only place a reason
    is recorded — there is no `Canvas-Why:` trailer and no attribute on the
    node. The subject's shape is `_write_and_commit`'s, `<verb> <subject>:
    <reason>`, and it is taken apart here rather than anywhere else.
    """


def _edit_from(sha, subject, author):
    verb, _, rest = subject.partition(" ")
    reason = rest.partition(": ")[2] or rest
    return Edit(sha, verb, reason, author)


def _log(canvas_dir, arguments, complaint):
    """`git log` over the canvas repository, decoded into records, oldest first.

    One place runs the query and one place decodes the format, so the callers
    below — which ask different questions of the same log — cannot drift apart
    on what a commit's trailers say.
    """
    result = _git(
        canvas_dir, *(["log", "--reverse", "--format=%s" % _LOG_FORMAT] + arguments)
    )
    if result.returncode != 0:
        if head_sha(canvas_dir) is None:
            # No commits at all. git log exits non-zero on an unborn branch
            # rather than printing nothing.
            return []
        raise ToolProblem(
            "%s: %s" % (complaint, result.stderr.decode("utf-8", "replace").strip()),
            "run `git log` against %s yourself to see what it objects to, and "
            "repair the repository; nothing was written" % canvas_dir,
            about=["canvas repository %s" % canvas_dir, "command git log"],
        )

    records = []
    for record in result.stdout.decode("utf-8", "replace").split(_RECORD):
        record = record.strip("\n")
        if not record:
            continue
        sha, subject, named, authors = record.split(_FIELD)
        records.append(
            _Record(sha, subject, named.split("\x1d"), authors.replace("\x1d", ", "))
        )
    return records


def _node_commits(canvas_dir, node_id, path=None):
    """The commits whose `Canvas-Node:` trailer is exactly `node_id`, oldest first.

    `path` scopes the answer to one canvas; without it the answer is the whole
    repository, which is what the uniqueness check needs — `node-identity.md`
    section 1 makes ids unique across `state/canvas` and not within one file,
    so a path-scoped `is_free` would hand out an id another canvas already used.
    """
    arguments = []
    if _SAFE_IN_A_PATTERN.match(node_id):
        arguments += ["--extended-regexp", "--grep=^Canvas-Node: %s$" % node_id]
    if path is not None:
        arguments += ["--", path]

    return [
        _edit_from(record.sha, record.subject, record.author)
        for record in _log(
            canvas_dir,
            arguments,
            "cannot search the canvas history for %s" % node_id,
        )
        if node_id in record.named
    ]


def _commits_in(canvas_dir, since, path):
    """Every commit that touched this canvas's file in `since..HEAD`, oldest first.

    The whole range and not one node's share of it: which node each commit
    named travels on the record, so the staleness split below reads both of its
    branches out of one query.
    """
    return _log(
        canvas_dir,
        ["%s..HEAD" % since, "--", path],
        "cannot list what changed in %s since %s" % (path, since),
    )


# --------------------------------------------------------------------------
# Minting an id
# --------------------------------------------------------------------------


def is_free(canvas_dir, candidate):
    """Has this id ever been used anywhere in this canvas repository?

    `node-identity.md` section 1: "The uniqueness check is the git history
    itself. A candidate id is free if `git log --grep='Canvas-Node: <candidate>'`
    is empty. No registry file, no allocator state." Across the whole
    repository, with no path filter, because ids are unique across it and not
    within one file.

    Asked of `_node_commits` rather than of that `--grep` literally: a
    substring match says an id is taken when a longer id merely starts with it,
    which silently shrinks the space `mint` can draw from. The question the
    section asks — has any commit named this id — is the one answered here.
    """
    return history_length(canvas_dir, candidate) == 0


def mint(canvas_dir):
    """Draw a free id at random, checked against the history, redrawn on a hit.

    Derived from nothing, which is the point: an id names a position in the
    argument, not the text that currently occupies it.
    """
    for _ in range(_MINT_ATTEMPTS):
        candidate = secrets.choice(_FIRST_CHARACTER) + "".join(
            secrets.choice(_REMAINING_CHARACTERS) for _ in range(3)
        )
        if is_free(canvas_dir, candidate):
            return candidate
    raise ToolProblem(
        "could not mint a free node id in %d draws" % _MINT_ATTEMPTS,
        "check the history in %s: %d draws from 774,206 ids all colliding "
        "means the freeness check is answering wrongly, not that the space is "
        "full. Nothing was written" % (canvas_dir, _MINT_ATTEMPTS),
        about=["canvas repository %s" % canvas_dir],
    )


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def require_reason(why, nodes=(), about=()):
    """Return the edit's reason, or refuse. Required, no default, no fallback.

    `nodes` and `about` are what the caller already knows about the edit that
    is being refused — the node it names, the canvas it is in. They are on the
    command line whenever this fires, and a refusal that has them and does not
    print them is a refusal an agent cannot act on.

    Absent, empty and whitespace-only are the same answer: no. There is no
    generated default and nothing to fall back to, because a reason a tool
    invented is worse than no reason at all — it is a sentence in the history
    that reads like somebody decided something.

    A missing or empty reason is the *invocation* being wrong rather than the
    request being wrong against the store, so it is a `ToolProblem`: exit 2,
    nothing written, the same code `canvas/cli.py` already gives any other
    malformed argument. Both codes are non-zero; this one is the one that says
    the command was not well formed, which is what an empty `--why` is.
    """
    if why is None or not why.strip():
        raise ToolProblem(
            "--why is required and must not be empty: every edit to a canvas "
            "records the reason it was made, and there is no default",
            "re-run the same command with --why \"<why this edit is being "
            "made>\"; nothing was written, committed or minted",
            nodes=nodes,
            about=["option --why"] + list(about),
        )
    return why.strip()


def history_length(canvas_dir, node_id):
    """How many commits name this node — which is exactly what `v` counts.

    `node-identity.md` section 4: "`v` equals the number of commits whose
    `Canvas-Node:` trailer names that node." Taken from the log at write time
    rather than by adding one to the attribute in the file, so the number in
    the document cannot drift away from the invariant that defines it. The log
    is the record; the `v` attribute is a cache of it.

    Counted with `_node_commits`, so the commits counted here are exactly the
    commits `history` returns. A looser count would let a node's `v` claim a
    life its own history does not show.
    """
    return len(_node_commits(canvas_dir, node_id))


def next_version(canvas_dir, node_id):
    """The `v` the node will carry once this commit has named it.

    One rule covers all three verbs that write a `v`: the commit about to be
    made is the next one to name the node, so `v` is the count so far plus one.
    A freshly minted id has a count of zero — that is what `mint` checked — so
    `insert` gets `document.BIRTH_VERSION` out of the same arithmetic.
    """
    return str(history_length(canvas_dir, node_id) + 1)


def default_author(canvas_dir):
    """Who is writing, when the caller did not say.

    `by-hand` rather than a synthesised `step:`/`run:`, because a run id that no
    run store will ever resolve makes `git log --grep='run:'` return rows for
    runs that never existed — a wrong history that looks right, which is the
    failure mode `node-identity.md` exists to design against.
    """
    who = os.environ.get("USER") or _configured(canvas_dir, "user.name", "") or "unknown"
    return "%s | by-hand" % who


def _validate(path, reported_as):
    """The one validation path. Diagnostics are reported at the real path."""
    try:
        problems = validate_file(path)
    except EnvironmentProblem as error:
        # Not an invalid document. The validator cannot run. It is already a
        # refusal with the thing it is about and the next action on it, so
        # both travel across the boundary rather than being restated here.
        raise ToolProblem(
            "the validator cannot run: %s" % error,
            error.next_action,
            nodes=error.nodes,
            about=error.about,
        )
    return [problem.replace(path, reported_as) for problem in problems]


#: A schema-valid id, used only to give the pre-flight tree well-formed nodes.
#: It is never committed and never appears in a commit message, so it is never
#: minted and never consumed.
_PREFLIGHT_ID = "aaaa"


def preflight(path, ledger_id, contents):
    """Validate the document `create` is going to end up with, before committing.

    `create` is three commits, and a validation failure partway through leaves
    the earlier ones in place — they are valid canvases and rewriting history to
    hide them would be worse. But the one thing that can actually fail is
    character data that XML cannot hold, and that is knowable before the first
    commit. Checking it here means the half-created canvas is a fallback rather
    than the ordinary outcome of a bad argument, and a rejected `create` can
    simply be run again.

    Raises Refusal with the diagnostics; writes nothing that survives.
    """
    root = document.new_canvas(ledger_id)
    for content in contents:
        document.place_into(root, document.ROOT, document.new_text(_PREFLIGHT_ID, content))
    temporary = "%s.preflight-%d" % (path, os.getpid())
    try:
        try:
            with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(document.serialise(root))
        except OSError as error:
            raise _cannot_write(path, error)
        problems = _validate(temporary, path)
    finally:
        try:
            if os.path.exists(temporary):
                os.unlink(temporary)
        except OSError as error:
            raise _cannot_write(path, error)
    if problems:
        raise Refusal(
            "refusing to create an invalid canvas at %s" % path,
            "the diagnostics above name where the document breaks; re-run "
            "`bin/canvas create %s` with a --problem and an --expected-value "
            "that XML can hold. Nothing was written and no canvas exists yet"
            % ledger_id,
            about=["ledger id %s" % ledger_id, "canvas %s" % path],
            details=problems,
        )


# --------------------------------------------------------------------------
# One write is one node
# --------------------------------------------------------------------------
#
# `node-identity.md` section 5 decides what "one node" means when the node has
# children, and section 4 states the invariant the whole rule protects: a
# node's entire life is exactly the set of commits that name it. The three
# functions below are that invariant made checkable, and they run on the only
# path that puts a canvas on its own path — so the rule binds a Python caller
# exactly as hard as it binds a command line.


def _shape(root):
    """What a one-node comparison sees: every node's record, and the order.

    Two maps, keyed by node id, with the root under `document.ROOT`:

    - **records** — `(tag, attributes, character data, the id of the parent)`.
      Whose child a node is belongs to the *child's* record and not to the
      container's, which is section 4's invariant restated as data: "a
      container's `v` does not bump when its children change". That is also
      what makes moving a populated container one node's edit — every child's
      parent is the moved node before the move and the moved node after it, so
      not one of their records has changed.
    - **order** — each container's children, in order. A rewrite that shuffles
      two siblings changes no record at all, so this is the second half of the
      comparison rather than a decoration.

    A node with no `id`, and a document that uses one id twice, both raise: a
    guard that cannot name a node cannot vouch for it.
    """
    records = {}
    order = {}
    stack = [(root, None)]
    while stack:
        element, parent_id = stack.pop()
        node_id = document.ROOT if element is root else element.get("id")
        if node_id is None:
            # Named by its container, which is the identifying thing a node
            # with no id still has — the same problem `validate._describe`
            # solves with an element path when it has to name one in a
            # diagnostic.
            raise Refusal(
                "refusing to write a <%s> with no id, under %s: every node in "
                "a canvas carries one, and a node the store cannot name is a "
                "node no history can record" % (element.tag, parent_id),
                "give it an id — `document.new_node(<id>, ...)` takes one and "
                "`insert` mints one — and write it again; nothing was written",
                nodes=[parent_id] if parent_id != document.ROOT else [],
                about=[
                    "element <%s>" % element.tag,
                    "container %s" % parent_id,
                ],
            )
        if node_id in records:
            raise Refusal(
                "refusing to write a canvas that uses the id %s twice, once "
                "under %s and once under %s: an id names one node, and two "
                "nodes sharing one would share one history"
                % (node_id, records[node_id][3], parent_id),
                "give one of the two its own id — `mint` draws one no commit "
                "has ever named — and write it again; nothing was written",
                nodes=[node_id],
                about=[
                    "container %s" % records[node_id][3],
                    "container %s" % parent_id,
                ],
            )
        records[node_id] = (
            element.tag,
            tuple(sorted(element.items())),
            element.text,
            parent_id,
        )
        children = list(element)
        if children:
            order[node_id] = tuple(child.get("id") for child in children)
        stack.extend((child, node_id) for child in children)
    return records, order


def _without(sequence, node_id):
    return tuple(each for each in sequence if each != node_id)


def _one_node_only(path, root, node_id):
    """Refuse unless this write changes exactly the node the commit names.

    The document on disk and the document about to replace it are compared node
    by node. Everything except the subject has to come through identical: same
    type, same attributes — `v` included — same character data, same parent,
    and the same siblings in the same order once the subject is taken out of
    both sequences, which is what lets the subject be inserted, moved or
    removed without every node around it counting as changed.

    The subject may therefore be born, edited, reparented, reordered or taken
    out; and nothing else may happen in the same commit. A container that
    travels with its subtree passes, because no child's record mentions where
    its container sits. A payload that rewrites that subtree does not.
    """
    if not os.path.isfile(path):
        raise Refusal(
            "refusing to write %s in a commit naming %s: there is no canvas "
            "there for that node to be one edit of. A canvas is created by "
            "`create`, and only its birth commit names no node" % (path, node_id),
            "create the canvas first, with `bin/canvas create <ledger-id> "
            "--problem \"<the problem>\" --expected-value \"<the expected "
            "value>\"`, and then edit it one node at a time",
            nodes=[node_id],
            about=["canvas %s" % path],
        )
    try:
        stored = document.parse(path)
    except document.NotWellFormed as error:
        raise Refusal(
            "%s" % error,
            "repair the XML at the line named above — `bin/canvas-validate %s` "
            "reports it — and write again; nothing was written" % path,
            nodes=[node_id],
            about=["canvas %s" % path],
        )
    except OSError as error:
        # The document on disk is what this write is held against, so a canvas
        # that cannot be read cannot be written either — there is nothing to
        # compare the one-node claim to.
        raise _cannot_read(path, error, node_id=node_id)

    before, before_order = _shape(stored)
    after, after_order = _shape(root)

    changed = sorted(
        key
        for key in set(before) | set(after)
        if key != node_id and before.get(key) != after.get(key)
    )
    reordered = sorted(
        key
        for key in set(before_order) | set(after_order)
        if _without(before_order.get(key, ()), node_id)
        != _without(after_order.get(key, ()), node_id)
    )
    if not changed and not reordered:
        return

    # IWE's error surface, as `engineering-spec.md`'s *What to copy* requires:
    # name every node the rejected write would have touched, and say what to do
    # instead. An agent can act on that; it cannot act on the word "refused".
    also = []
    if changed:
        also.append(
            "changes %d other node(s) (%s)" % (len(changed), ", ".join(changed))
        )
    if reordered:
        also.append(
            "reorders the children of %s"
            % ", ".join(
                "the root" if key == document.ROOT else key for key in reordered
            )
        )
    raise Refusal(
        "refusing to write a commit naming %s that also %s: one edit is one node"
        % (node_id, " and ".join(also)),
        "make each of those its own edit with its own reason, using insert, "
        "replace, remove or move, one node at a time",
        nodes=[node_id] + changed + [key for key in reordered if key != document.ROOT],
        about=(
            ["canvas %s" % path]
            + (["container the root"] if document.ROOT in reordered else [])
        ),
    )


def _a_canvas_is_being_born(path, root):
    """The one write that names no node: `create`'s first commit, root only.

    `node-identity.md` section 4: "The canvas's creation commit creates the root
    only." A commit with no `Canvas-Node:` trailer changes no node's history, so
    the only document it may write is one with no nodes in it — and only where
    there is no canvas there yet, because a nameless write over an existing
    canvas is exactly the whole-document rewrite this store does not have.
    """
    if os.path.exists(path):
        raise Refusal(
            "refusing to write %s in a commit that names no node: a canvas "
            "already exists there, and a write that names no node is the birth "
            "of one" % path,
            "change the canvas that is there with insert, replace, remove or "
            "move, one node at a time, each with its own reason",
            about=["canvas %s" % path],
        )
    nodes = list(root.iter())[1:]
    if nodes:
        raise Refusal(
            "refusing to create %s with %d node(s) already in it (%s): a canvas "
            "is born as its root alone"
            % (path, len(nodes), _child_ids(nodes)),
            "write the root alone, then bring each of those nodes in with its "
            "own insert and its own reason, one node at a time",
            nodes=[node.get("id") for node in nodes if node.get("id")],
            about=["canvas %s" % path],
        )


def _inside_the_store(canvas_dir, path):
    """A canvas is written at its own path in the canvas repository, or not at all.

    `canvas_path` already keeps a ledger id from escaping `state/canvas`; this
    keeps a hand-supplied path from doing it, so that the file a write produces
    is always one `git add` can stage and always one `read` can find again.
    """
    home = os.path.realpath(canvas_dir)
    where = os.path.realpath(os.path.dirname(os.path.abspath(path)))
    if where != home or not os.path.basename(path).endswith(".xml"):
        raise ToolProblem(
            "refusing to write %s: a canvas is written as <ledger-id>.xml "
            "inside %s and nowhere else" % (path, canvas_dir),
            "write it as %s/<ledger-id>.xml; `bin/canvas` derives that path "
            "from the ledger id, which is why no command line can express "
            "this one" % canvas_dir,
            about=["path %s" % path, "canvas repository %s" % canvas_dir],
        )


def _write_and_commit(
    canvas_dir, path, root, verb, subject_name, why, author, node_id=None, base=None
):
    """Validate the document, put it at `path`, commit it. Return the new sha.

    The document is written to a temporary name in the same directory and
    validated there. Only a document the validator passed is renamed onto the
    canvas's own path, so an invalid canvas is never reachable as a canvas — the
    rename is the moment it becomes one, and it is atomic.

    **This is where "no write without a reason" is enforced**, and it is here
    rather than in `canvas/cli.py` on purpose. The todo's done condition is
    about code paths and not about a command line, so the check belongs to the
    only function that can put a canvas on its path. `why` is a positional
    argument with no default, so a caller cannot forget it, and
    `require_reason` runs before the temporary file is opened, so a refused
    edit leaves nothing behind — not even a rejected temporary.

    The subject is built here and not handed in, for the same reason: a caller
    that composed its own subject could compose one with no reason in it. The
    shape is `<verb> <subject> : <reason>`, which is what `create` already
    wrote and what `engineering-spec.md` shows for `replace`.

    **This is also where "one edit is one node" is enforced**, and it is here
    for exactly the same argument. `node_id` is no longer a label used only to
    compose a trailer: it is the claim this write makes about itself, and
    `_one_node_only` holds the write to it against the document already on
    disk. A caller handing in a whole rewritten tree gets a refusal naming
    every node it would have changed, whether it came through `canvas/cli.py`
    or through `from canvas import store`. The single write that names no node
    is the birth of a canvas, and `_a_canvas_is_being_born` is the whole of
    what it is allowed to be.

    All three checks run before the temporary file is opened, so a refused
    write leaves nothing behind — not even a rejected temporary.
    """
    why = require_reason(
        why,
        nodes=[node_id] if node_id is not None else [],
        about=["canvas %s" % path],
    )
    _inside_the_store(canvas_dir, path)
    if node_id is None:
        _a_canvas_is_being_born(path, root)
    else:
        _one_node_only(path, root, node_id)
    subject = "%s %s: %s" % (verb, subject_name, why)
    text = document.serialise(root)
    temporary = "%s.tmp-%d" % (path, os.getpid())
    try:
        try:
            with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        except OSError as error:
            raise _cannot_write(path, error, node_id=node_id)
        problems = _validate(temporary, path)
        if problems:
            raise Refusal(
                "refusing to write an invalid canvas to %s%s"
                % (path, "" if node_id is None else ", naming %s" % node_id),
                "the diagnostics above name the node and what is wrong with "
                "it; what a canvas node may be is written in "
                "schema/canvas.rng and nowhere else, so read that for what "
                "this position accepts, correct the payload and re-run. "
                "Nothing was written and nothing was committed",
                nodes=[node_id] if node_id is not None else [],
                about=["canvas %s" % path],
                details=problems,
            )
        try:
            os.replace(temporary, path)
        except OSError as error:
            raise _cannot_write(path, error, node_id=node_id)
    finally:
        try:
            if os.path.exists(temporary):
                os.unlink(temporary)
        except OSError as error:
            raise _cannot_write(path, error, node_id=node_id)

    # -f so that a stray ignore rule somewhere above cannot make `add` a silent
    # no-op and the commit a confusing failure.
    _git_checked(canvas_dir, "add", "-f", "--", path)

    trailers = []
    if node_id is not None:
        trailers.append("Canvas-Node: %s" % node_id)
    trailers.append("Canvas-Author: %s" % author)
    if base is not None:
        trailers.append("Canvas-Base: %s" % base)

    # The identity is passed per call, so the tool never writes configuration —
    # not the user's global config and not the canvas repository's — and there
    # is nothing to drift and nothing to clean up. gpgsign is turned off because
    # a global signing setting would otherwise make the store depend on a key.
    _git_checked(
        canvas_dir,
        "-c",
        "user.name=%s" % _configured(canvas_dir, "user.name", "canvas"),
        "-c",
        "user.email=%s" % _configured(canvas_dir, "user.email", "canvas@localhost"),
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        subject,
        "-m",
        "\n".join(trailers),
    )
    sha = head_sha(canvas_dir)
    if sha is None:
        raise ToolProblem(
            "committed to %s but the repository has no head" % canvas_dir,
            "inspect %s with `git log` — the commit was made and the "
            "repository reports no head — and repair it before writing again"
            % canvas_dir,
            nodes=[node_id] if node_id is not None else [],
            about=["canvas repository %s" % canvas_dir],
        )
    return sha


# --------------------------------------------------------------------------
# Creating and reading
# --------------------------------------------------------------------------


def create(ledger_id, problem, expected_value, author=None):
    """Make the canvas for a ledger row, with its first nodes. Return (path, sha).

    Three commits, not one:

        create <ledger_id>: born at open, root only
        insert <id>: the problem the ledger row states
        insert <id>: the expected value the ledger row states

    `node-identity.md` section 4 requires it: "The two nodes the ledger's `open`
    contributes — the problem and the expected value — arrive as two ordinary
    `insert` commits, each naming its own node, each born at `v="1"`. Creating
    the file with two nodes already in it would be one commit touching two
    nodes, which is the rule the tool exists to make inexpressible; the birth of
    a canvas gets no exemption from it."

    So the state this returns is a canvas with two nodes in it, which is what the
    store is asked for; the route there is three commits, which is what identity
    requires. The root commit carries no `Canvas-Node:` — the root is not a node
    — and no `Canvas-Base:`, because there was no prior state to decide against.
    The two insert commits each base on the commit before them, which is
    literally true and makes the chain self-describing. `create` declares no
    `--base` of its own, and takes no flag for one: the four verbs declare the
    sha they were decided against and `_check_base` holds them to it, but the
    birth of a canvas has no prior state it could have been decided against, so
    there is nothing for it to declare and nothing to compare.

    The two nodes are `<text>` nodes, problem first. They carry no marker saying
    which is which: the vocabulary has no semantic node and inventing one is the
    `<decision>`/`<risk>` tripwire. The distinction lives in the commit subject
    and in the order, where a reader and a `git log --grep` can both find it.
    """
    canvas_dir = canvas_directory()
    path = canvas_path(canvas_dir, ledger_id)
    ensure_repository(canvas_dir)

    if os.path.exists(path):
        raise Refusal(
            "a canvas for %s already exists at %s (Canvas-Base: %s); "
            "this command creates, it does not overwrite"
            % (ledger_id, path, head_sha(canvas_dir)),
            "read it with `bin/canvas read %s`, then change it one node at a "
            "time with insert, replace, remove or move, each with its own "
            "--why" % ledger_id,
            about=[
                "ledger id %s" % ledger_id,
                "canvas %s" % path,
                "sha %s" % head_sha(canvas_dir),
            ],
        )

    if author is None:
        author = default_author(canvas_dir)

    preflight(path, ledger_id, (problem, expected_value))

    root = document.new_canvas(ledger_id)
    sha = _write_and_commit(
        canvas_dir,
        path,
        root,
        "create",
        ledger_id,
        "born at open, root only",
        author,
    )

    first_nodes = (
        (problem, "the problem the ledger row states"),
        (expected_value, "the expected value the ledger row states"),
    )
    for content, reason in first_nodes:
        node_id = mint(canvas_dir)
        document.place_into(root, document.ROOT, document.new_text(node_id, content))
        sha = _write_and_commit(
            canvas_dir,
            path,
            root,
            "insert",
            node_id,
            reason,
            author,
            node_id=node_id,
            base=sha,
        )

    return path, sha


def read(ledger_id):
    """Return (sha, the bytes on disk, diagnostics) for one ledger row.

    A read. It writes nothing, commits nothing, and does not initialise a
    repository: a workspace with no canvas repository has no canvas to read, and
    creating one to say so would be a write.

    An invalid stored document is still returned, with its diagnostics, because
    the caller has to be able to see what to repair. Refusing to show it would
    make it unrepairable.
    """
    canvas_dir = canvas_directory()
    path = canvas_path(canvas_dir, ledger_id)

    if not os.path.isfile(path):
        raise _no_canvas(ledger_id, path)
    if not is_repository(canvas_dir):
        raise _not_a_repository(canvas_dir, "sha to write against")

    sha = head_sha(canvas_dir)
    if sha is None:
        raise _no_commits(canvas_dir, "sha to write against")

    try:
        with open(path, "rb") as handle:
            body = handle.read()
    except OSError as error:
        raise _cannot_read(path, error, ledger_id=ledger_id)
    return sha, body, _validate(path, path)


def history(ledger_id, node_id):
    """Every edit that named this node, oldest first. Returns a list of `Edit`.

    A read, like `read` and for the same reasons: it writes nothing, commits
    nothing, and does not initialise a repository. A workspace with no canvas
    repository has no history to report, and creating one to say so would be a
    write.

    **Oldest first**, because the question this answers is what the node's
    current text is *for*, and that is a story: the reason it was born, then
    every reason it was changed, ending at the reason it reads the way it does
    now. `git log`'s own order is newest first, so this reverses it.

    **Edits made before a `move` are included**, and not as a special case.
    `node-identity.md` section 3 keeps a node's id across a move, so the move's
    commit names the same node the earlier commits named and one query spans
    it. That is the whole of what the id buys.

    The search is scoped to this canvas's file. Ids are unique across the
    repository, so the scope changes no answer that exists — but it is what
    makes "no such node in this canvas" a true statement rather than a guess,
    and the command names the canvas anyway.

    Refuses when there is no canvas for that ledger id, and — separately, and
    saying which — when no commit in that canvas names the node.
    """
    canvas_dir = canvas_directory()
    path = canvas_path(canvas_dir, ledger_id)

    if not os.path.isfile(path):
        raise _no_canvas(ledger_id, path)
    if not is_repository(canvas_dir):
        raise _not_a_repository(canvas_dir, "history to report")

    edits = _node_commits(canvas_dir, node_id, path)
    if not edits:
        raise Refusal(
            "no node with id %s in the history of the canvas for %s: no commit "
            "names it, so it was never a node of this canvas. The canvas is "
            "there; the node is not" % (node_id, ledger_id),
            "`bin/canvas read %s` prints the canvas and every id in it; ask "
            "one of those for its history" % ledger_id,
            nodes=[node_id],
            about=["ledger id %s" % ledger_id, "canvas %s" % path],
        )
    return edits



# --------------------------------------------------------------------------
# Staleness: what moved since --base
# --------------------------------------------------------------------------
#
# `engineering-spec.md` section "Staleness". Every read hands out the current
# sha; a write declares the sha it was decided against, and the tool splits on
# what moved in between. Two named branches, and a third case that is the
# ordinary one:
#
# - **The node this write names moved since `--base`** -> hard refusal. The
#   tool exits non-zero, applies nothing, commits nothing, mints nothing, and
#   prints that node's diff since `--base`. The writer re-reads and re-decides.
# - **Something else moved since `--base`** -> the write applies, and the same
#   output that reports success carries the diff of everything that changed in
#   between. The writer is told, in the same breath as being told it succeeded,
#   what it did not know.
# - **Nothing moved** -> the write applies and says nothing extra. A read and
#   then a write against an unchanged canvas is silent.
#
# Nothing here reconciles and nothing merges, and that is not an omission. The
# spec rejects CRDTs and operational transform twice over: they auto-merge and
# therefore never refuse, and the refusal is the feature.
#
# **Both branches are scoped to this canvas's own file.** `state/canvas` is one
# repository holding every ledger row, and `head_sha` is repository-wide on
# purpose — that is what makes the sha a read hands out an identity key rather
# than one file's version number. Without the path filter, an edit to an
# unrelated ledger row would make every writer stale and the soft branch would
# fire carrying an empty diff, so "a read-then-write round trip against an
# unchanged canvas succeeds silently" would stop being true in any busy store.
# With it, the sha stays repository-wide and the news is about the document the
# writer actually read. `history` path-scopes for the same reason.
#
# **`--base` is optional, and an omitted one is not a base of "now".** It is
# the absence of the question: the write carries no staleness claim, nothing is
# compared, and the verb behaves exactly as it did before this rule existed.
# That is deliberately not `--why`'s shape. `--why` has no value the tool could
# correctly compute, so an absent one is a malformed invocation; an absent
# `--base` asks for no check and gets none, and there is no silently wrong
# answer hiding in that case. `create` takes none under either reading: the
# birth of a canvas has no prior state it could have been decided against.


#: What `--base` may be: the sha a read handed out, or an abbreviation of one
#: git can still resolve. Anything else is the invocation being wrong rather
#: than a fact about the store, which is `README.md`'s own call for a malformed
#: ledger id — that stays `2` while a well-formed one naming nothing is `1`.
_A_SHA = re.compile(r"\A[0-9a-fA-F]{4,40}\Z")


def _resolve_base(canvas_dir, declared, head, ledger_id, node_id):
    """The full sha `--base` names, or the refusal that says why it is not one.

    Three answers, and they are three different things:

    - **Not a sha at all** -> `ToolProblem`, exit 2. The invocation is wrong.
    - **A well-formed sha this repository never handed out** -> `Refusal`, exit
      1. That is a true statement about the store as it stands, and the answer
      is to re-read and re-decide, exactly as it is for "no canvas for this
      ledger id" and "no node with id X in this canvas".
    - **Known, but not an ancestor of the head** -> `Refusal`, exit 1. The
      canvas repository has one line of history and nothing in this store ever
      creates a branch, so a known non-ancestor came from a rewritten history
      or from somewhere else. `<base>..HEAD` would answer "nothing moved" for
      it, which is a vacuous pass wearing the safe case's face. That silent
      pass is the one outcome worth spending a check to prevent.
    """
    if not _A_SHA.match(declared):
        raise ToolProblem(
            "not a usable --base: %r; a base is the commit sha a read handed "
            "out, four to forty hexadecimal characters" % declared,
            "re-run with the sha `bin/canvas read %s` printed on its "
            "Canvas-Base: line, or drop --base to ask for no staleness check "
            "at all. Nothing was written" % ledger_id,
            nodes=[node_id] if node_id is not None else [],
            about=["ledger id %s" % ledger_id, "option --base %r" % declared],
        )
    resolved = _git(
        canvas_dir, "rev-parse", "--verify", "--quiet", "%s^{commit}" % declared
    )
    if resolved.returncode != 0:
        raise Refusal(
            "no commit %s in this canvas repository: --base names the sha a "
            "read handed out, and this one was never handed out here" % declared,
            "read the canvas again with `bin/canvas read %s` and write against "
            "the sha it prints. Nothing was written" % ledger_id,
            nodes=[node_id] if node_id is not None else [],
            about=["ledger id %s" % ledger_id, "option --base %s" % declared],
        )
    base = resolved.stdout.decode("utf-8", "replace").strip()
    if base != head:
        ancestry = _git(canvas_dir, "merge-base", "--is-ancestor", base, "HEAD")
        if ancestry.returncode != 0:
            raise Refusal(
                "--base %s is not an ancestor of %s, this canvas repository's "
                "head: nothing that led here was decided against it, so what "
                "changed in between is not a question this store can answer"
                % (base, head),
                "read the canvas again with `bin/canvas read %s` and write "
                "against the sha it prints. Nothing was written" % ledger_id,
                nodes=[node_id] if node_id is not None else [],
                about=[
                    "ledger id %s" % ledger_id,
                    "option --base %s" % base,
                    "sha %s, the head" % head,
                ],
            )
    return base


def _patch(canvas_dir, sha, path):
    """One commit's own diff of this canvas's file, as git prints it.

    One commit is one node, so a commit's file-scoped patch *is* that node's
    diff for that edit, and no extraction step is needed. None is built,
    either: a node-granular structural differ is exactly what `README.md`
    section "What the store deliberately does not do" declined to write, on the
    grounds that `git show` is right there and wrapping it would be restating
    git rather than using it.
    """
    return _git_checked(
        canvas_dir, "show", "--format=", "--patch", sha, "--", path
    ).splitlines()


def _diff(canvas_dir, base, head, path):
    """The unified diff of this canvas's file between two commits."""
    return _git_checked(canvas_dir, "diff", base, head, "--", path).splitlines()


def _check_base(canvas_dir, path, ledger_id, node_id, head, declared):
    """Split on what moved since `--base`. Return the news, or None.

    `None` means there is nothing to say: no base was declared, or this canvas
    has not moved since the one that was. Anything else is the soft branch —
    the lines the verb's success output carries after it has reported the node
    and the new sha.

    The hard branch is a `Refusal` raised from here, carrying that node's diff
    since `--base` in its details, which `canvas/cli.py` already prints one line
    at a time on stderr. It is raised **before** the caller mints an id and
    before `_write_and_commit` opens anything, so a refused write leaves nothing
    behind: no file, no temporary, no commit — and no gap in the id space,
    because `is_free` decides freeness by grepping the history and a
    minted-then-refused id would be a draw nothing can account for.

    `node_id` is None for `insert`, whose node is minted after this runs and
    therefore cannot have moved: an id no commit has ever named has no history
    to have moved in. The position anchor an `insert` names is a different
    node, and an anchor that no longer exists is already a refusal, in
    `_place`. An anchor that merely changed is reported rather than refused: it
    arrives in the news the soft branch hands back, which is the writer being
    told what it did not know.
    """
    if declared is None:
        return None
    base = _resolve_base(canvas_dir, declared, head, ledger_id, node_id)
    if base == head:
        return None

    moved = _commits_in(canvas_dir, base, path)
    if not moved:
        return None

    # Equality on the trailer's value, never a substring match. Ids are four
    # characters, so `--grep='Canvas-Node: b7'` answers for `b7pk` when it was
    # asked about `b7`, and counts a reason that merely quotes the trailer text
    # as an edit. This is `_node_commits`' rule applied to the same field of the
    # same record: the anchored `--grep` there is a pre-filter and never the
    # authority, and a query already narrowed to one range and one file has
    # nothing left for a pre-filter to narrow.
    theirs = [
        record
        for record in moved
        if node_id is not None and node_id in record.named
    ]
    if theirs:
        details = []
        for record in theirs:
            if details:
                details.append("")
            details.append("Canvas-Commit: %s" % record.sha)
            details.append(record.subject)
            details.extend(_patch(canvas_dir, record.sha, path))
        raise Refusal(
            "refusing to write %s in the canvas for %s: it moved in %d "
            "commit(s) between --base %s and %s, so this edit was decided "
            "against text that is no longer there. Nothing was applied and "
            "nothing was merged. Its diff since %s follows"
            % (node_id, ledger_id, len(theirs), declared, head, declared),
            "read the canvas again with `bin/canvas read %s`, re-decide "
            "against the sha it prints, and re-run this edit with that --base"
            % ledger_id,
            nodes=[node_id],
            about=[
                "ledger id %s" % ledger_id,
                "canvas %s" % path,
                "option --base %s" % declared,
                "sha %s, the head" % head,
            ],
            details=details,
        )

    news = [
        "Canvas-News: %d commit(s) between %s and %s" % (len(moved), base, head)
    ]
    news.extend(record.subject for record in moved)
    news.extend(_diff(canvas_dir, base, head, path))
    return news


# --------------------------------------------------------------------------
# The four verbs
# --------------------------------------------------------------------------
#
# `replace`, `insert`, `remove`, `move`, and no more. There is no `resolve`, no
# `collapse` and no `supersede`: the semantics live in the reason, where they
# can be anything, and not in a verb name, where they can only be what somebody
# thought of in advance.
#
# Each of them is exactly one commit, because `_write_and_commit` writes and
# commits in one call and there is no other way to put a canvas on its path.
# Each names exactly one node in a `Canvas-Node:` trailer, which is what makes
# the commits carrying that trailer that node's whole life, and `history` the
# command that reads it back.
#
# Each takes a `ledger_id` as well as the node id. `node-identity.md` makes ids
# unique across the whole repository, so a node id alone does identify a node —
# but `state/canvas` holds one file per ledger row, `--into root` names a root
# that every one of those files has, and finding the file by scanning them all
# would need a match-count guard for the case where two files answer. Naming the
# canvas is the cheaper half of that trade, and it is what `create` and `read`
# already do.
#
# Each of them accepts an optional `base`: the sha the edit was decided
# against. `_check_base` splits on what moved since — a hard refusal carrying
# that node's diff when the node this write names moved, the news of everything
# else when it did not, and silence when nothing did. Declaring none asks for no
# check and gets none.
#
# The `Canvas-Base:` trailer the commit carries is a different fact and is
# written either way: it is the truthful record of the head this edit was
# applied to, exactly as `create`'s own insert commits already write it. What a
# writer declared and what it was applied to are the same sha whenever the write
# was not stale, and the commit records the second of them because that is the
# one a reader of the history needs.


def _open_canvas(ledger_id):
    """The canvas an edit is about to change: (dir, path, root, head sha).

    The head is both what the edit will be applied to — the `Canvas-Base:` its
    commit records — and what a declared `--base` is compared against.

    Re-read from disk on every invocation, because the document an edit applies
    to is the one that is there now and not the one its caller last saw.

    A stored document that is not well-formed is a `Refusal` and not a
    `ToolProblem`: the store is wrong, the tool is fine, and the answer is to
    repair the file rather than to stop touching canvases. That is the same
    call `README.md` already makes for "no canvas for this ledger id".
    """
    canvas_dir = canvas_directory()
    path = canvas_path(canvas_dir, ledger_id)

    if not os.path.isfile(path):
        raise _no_canvas(ledger_id, path)
    if not is_repository(canvas_dir):
        raise _not_a_repository(canvas_dir, "sha to write against")
    head = head_sha(canvas_dir)
    if head is None:
        raise _no_commits(canvas_dir, "sha to write against")
    try:
        root = document.parse(path)
    except document.NotWellFormed as error:
        raise Refusal(
            "%s" % error,
            "repair the XML at the line named above — `bin/canvas-validate %s` "
            "reports it — and re-run; nothing was written" % path,
            about=["ledger id %s" % ledger_id, "canvas %s" % path],
        )
    except OSError as error:
        # A canvas that is there and unreadable is not a wrong request, so it
        # is the one thing in this function that is a `ToolProblem` and not a
        # `Refusal`: exit 2, do not touch the canvas.
        raise _cannot_read(path, error, ledger_id=ledger_id)
    return canvas_dir, path, root, head


def _addressed(root, node_id, ledger_id):
    """The node an edit names, or a Refusal that names what was not found.

    Addressing is by explicit node id and nothing else — no selector, no path,
    no "the first heading". A selector would need a match-count guard beside it
    the day it arrived, because a selector can match two; an id cannot.
    """
    if node_id == document.ROOT:
        raise Refusal(
            "the root is not a node: <canvas> carries no id and no v, so it "
            "cannot be replaced, removed or moved. Nothing was changed",
            "name one of the canvas's own nodes instead — `bin/canvas read %s` "
            "prints every id in it — or use --into root to place a node inside "
            "the root, which is the one thing root does name" % ledger_id,
            about=["ledger id %s" % ledger_id, "position root, the <canvas> element"],
        )
    node = document.find(root, node_id)
    if node is None:
        raise Refusal(
            "no node with id %s in the canvas for %s: nothing was changed"
            % (node_id, ledger_id),
            "`bin/canvas read %s` prints the canvas and every id in it; re-run "
            "naming one of those" % ledger_id,
            nodes=[node_id],
            about=["ledger id %s" % ledger_id],
        )
    return node


def _one_position(after, into, ledger_id=None, moving=None):
    """A position is named by exactly one of `--after` and `--into`.

    `moving` is the node being placed, on the same terms as `_place`'s: the id
    `move` already holds, and nothing for `insert`, which has not minted one
    yet. `bin/canvas` puts the two flags in a required mutually-exclusive group
    and intercepts both-given and neither-given before this runs, naming the
    node off the raw argv as it goes — so this is the library API's copy of the
    same refusal, and it names the same nodes the command line's copy does.
    """
    if (after is None) == (into is None):
        given = [
            "option --after %s" % after if after is not None else None,
            "option --into %s" % into if into is not None else None,
        ]
        raise ToolProblem(
            "a position is named by exactly one of --after <node-id> or "
            "--into <container-id>, and this one names %s"
            % ("both" if after is not None else "neither"),
            "re-run with exactly one: --after <node-id> puts the node "
            "immediately after that node, and --into <container-id> puts it "
            "last among that container's children, where 'root' names the "
            "canvas itself. Nothing was written",
            nodes=[
                each
                for each in (moving, after, into)
                if each is not None and each != document.ROOT
            ],
            about=(
                [each for each in given if each]
                + (["ledger id %s" % ledger_id] if ledger_id else [])
            )
            or ["option --after", "option --into"],
        )


def _place(root, node, after, into, ledger_id, moving=None):
    """Put the node at the named position, or refuse naming every node in hand.

    `canvas/document.py` composes the problem and has never heard of a ledger
    id, so it says "this canvas" and cannot say which. The ledger id is added
    here, where it is known, rather than taught to the document module.

    `moving` is the id of the node being placed **when that node is already a
    node of this canvas**. `move` has one and passes it, because the refusal is
    holding the element it was asked to move and a refusal that names only the
    position it missed leaves out half of what the caller has to act on. The
    same verb one flag apart already names both.

    **`insert` passes none, deliberately.** Its node was minted moments earlier
    and has never been in the canvas: no commit names it, `bin/canvas read`
    cannot show it, `bin/canvas history` has nothing for it, and the next
    attempt mints a different one. `Canvas-Node:` means "a node of this canvas"
    everywhere else in the tool, and printing a discarded draw under it would
    hand an agent an id it can neither look up nor reuse. That refusal names
    the ledger id and the position instead, which are the two things about it
    that are true.
    """
    try:
        if after is not None:
            document.place_after(root, after, node)
        else:
            document.place_into(root, into, node)
    except document.PositionProblem as problem:
        named = after if after is not None else into
        raise Refusal(
            "%s: nothing was changed" % problem,
            "`bin/canvas read %s` prints the canvas and every id in it; re-run "
            "naming --after <node-id> or --into <container-id> from those, "
            "where 'root' names the canvas itself" % ledger_id,
            nodes=[
                each
                for each in (moving, named)
                if each is not None and each != document.ROOT
            ],
            about=["ledger id %s" % ledger_id, "position %s" % named],
        )


def _child_ids(children):
    return ", ".join(child.get("id") or "<no id>" for child in children)


def insert(
    ledger_id,
    why,
    after=None,
    into=None,
    node_type="text",
    text=None,
    title=None,
    href=None,
    author=None,
    base=None,
):
    """Add one node. The only verb that mints an id. Returns (node_id, sha, news).

    Born at `v="1"`, which is `next_version` of an id no commit has ever named.
    No other node's `v` changes, because no other node is named by this commit.

    `node_type` defaults to `text` — the node type `create` already makes, and
    the one a canvas is mostly built from. It is a default for a node type and
    not for a reason: `--why` has none and never will.

    `base` is the sha this edit was decided against and `news` is what changed
    between it and the head the edit was applied to — None when no base was
    declared or when this canvas did not move. **An `insert` never takes the
    hard branch**: the node it names is minted below, after the check, and an
    id no commit has ever named cannot have moved. The check still runs, for
    the news and for the three ways a base can be unusable.
    """
    why = require_reason(
        why,
        nodes=[each for each in (after, into) if each is not None],
        about=["ledger id %s" % ledger_id],
    )
    _one_position(after, into, ledger_id)
    canvas_dir, path, root, head = _open_canvas(ledger_id)
    news = _check_base(canvas_dir, path, ledger_id, None, head, base)
    if author is None:
        author = default_author(canvas_dir)

    node_id = mint(canvas_dir)
    node = document.new_node(
        node_id,
        node_type,
        text=text,
        attributes={"title": title, "href": href},
    )
    _place(root, node, after, into, ledger_id)

    sha = _write_and_commit(
        canvas_dir,
        path,
        root,
        "insert",
        node_id,
        why,
        author,
        node_id=node_id,
        base=head,
    )
    return node_id, sha, news


def replace(
    ledger_id,
    node_id,
    why,
    node_type=None,
    text=None,
    title=None,
    href=None,
    author=None,
    base=None,
):
    """Replace one node's content, possibly with a node of a different type.

    Returns `(sha, news)`: the new head, and what changed between the declared
    `base` and the head this edit was applied to — None when no base was
    declared or when this canvas did not move. A node that moved in between is
    the hard branch, and `_check_base` raises it before anything is written.

    **The type change is the point.** An options `<table>` settling into a
    `<text>` is `replace` on the table node, and it is how a decision gets made
    in a canvas. The id is unchanged across it — `node-identity.md` section 2:
    "`replace` never mints and never changes an id" — so the settled decision
    still reaches every argument that produced it. `node_type` defaults to the
    type the node already has, so renaming a section or rewriting a paragraph
    does not have to restate what it already is.

    Replacing a container that has children is permitted and renames it: the
    children keep their ids, their `v`, their content and their order. Two
    refusals, both of them `node-identity.md` section 5's — which decides the
    whole container case, for every container and not for `<section>` alone:

    - A type change while the node has children, because the new type has
      nowhere to put them. Move them out first; they keep their ids throughout,
      which is the entire benefit.
    - Character data while the node has children, because a node in this
      vocabulary never holds both, so the text would be silently dropped.

    The children of a node that keeps its type are carried over untouched: same
    ids, same `v`, same content, same order. There is no way to supply children
    in a payload at all, which is what makes "a `replace` payload that rewrites
    N children" inexpressible rather than merely refused.
    """
    why = require_reason(
        why, nodes=[node_id], about=["ledger id %s" % ledger_id]
    )
    canvas_dir, path, root, head = _open_canvas(ledger_id)
    # Before `_addressed`, so that a node *removed* since `--base` is the hard
    # branch with its own diff, rather than the bare "no node with id X" a
    # writer working from a stale read cannot learn anything from.
    news = _check_base(canvas_dir, path, ledger_id, node_id, head, base)
    node = _addressed(root, node_id, ledger_id)
    children = list(node)
    becomes = node_type or node.tag

    if children and becomes != node.tag:
        raise Refusal(
            "refusing to change <%s> %s into <%s> while it has %d child node(s) "
            "(%s): a <%s> has nowhere to put them"
            % (node.tag, node_id, becomes, len(children), _child_ids(children), becomes),
            "move each child out with its own --why first, then replace the "
            "empty node; every child keeps its id and its whole history across "
            "the move",
            nodes=[node_id] + [child.get("id") for child in children if child.get("id")],
            about=["ledger id %s" % ledger_id],
        )
    if children and text is not None:
        raise Refusal(
            "refusing to give <%s> %s character data while it has %d child "
            "node(s) (%s): a node holds children or text, never both, so the "
            "text would be dropped"
            % (node.tag, node_id, len(children), _child_ids(children)),
            "replace each child with its own --why instead, one node at a "
            "time; a container's own text is not a thing this vocabulary has",
            nodes=[node_id] + [child.get("id") for child in children if child.get("id")],
            about=["ledger id %s" % ledger_id],
        )

    if author is None:
        author = default_author(canvas_dir)

    replacement = document.new_node(
        node_id,
        becomes,
        version=next_version(canvas_dir, node_id),
        text=text,
        attributes={"title": title, "href": href},
    )
    replacement.extend(children)
    document.replace_node(root, node_id, replacement)

    sha = _write_and_commit(
        canvas_dir,
        path,
        root,
        "replace",
        node_id,
        why,
        author,
        node_id=node_id,
        base=head,
    )
    return sha, news


def remove(ledger_id, node_id, why, author=None, base=None):
    """Take one node out of the document. Its id is retired, never reminted.

    Returns `(sha, news)`, on the same terms as `replace`.

    There is no `v` left to bump: the commit that removed it is the last entry
    in its history, and `is_free` greps that history, so the id can never be
    handed to a different node later.

    A node with children is refused, for every container and not just the
    `<section>` — `node-identity.md` section 5 states it that way, so this is a
    pointer at the specification and not a second copy of it. A cascading delete
    either names N nodes in one trailer or lets N−1 nodes vanish in a commit no
    grep on them will ever return, so a reader asking a dead id for its history
    would be shown a node that, by its own record, is still alive. Empty it
    first, each removal with its own reason.
    """
    why = require_reason(
        why, nodes=[node_id], about=["ledger id %s" % ledger_id]
    )
    canvas_dir, path, root, head = _open_canvas(ledger_id)
    news = _check_base(canvas_dir, path, ledger_id, node_id, head, base)
    node = _addressed(root, node_id, ledger_id)
    children = list(node)

    if children:
        raise Refusal(
            "refusing to remove <%s> %s while it has %d child node(s) (%s): "
            "one edit is one node"
            % (node.tag, node_id, len(children), _child_ids(children)),
            "remove each child with its own --why first, then remove the empty "
            "node; a cascading delete would let those children vanish in a "
            "commit no query on them ever returns",
            nodes=[node_id] + [child.get("id") for child in children if child.get("id")],
            about=["ledger id %s" % ledger_id],
        )

    if author is None:
        author = default_author(canvas_dir)
    document.detach(root, node_id)

    sha = _write_and_commit(
        canvas_dir,
        path,
        root,
        "remove",
        node_id,
        why,
        author,
        node_id=node_id,
        base=head,
    )
    return sha, news


def move(ledger_id, node_id, why, after=None, into=None, author=None, base=None):
    """Change one node's position and nothing else.

    Returns `(sha, news)`, on the same terms as `replace`.

    `node-identity.md` section 3: the id is unchanged, the content is
    unchanged, the type is unchanged, and the node's children travel with it
    untouched. `v` bumps, because the node was the subject of an edit — and
    neither the old parent's nor the new parent's does, because a commit names
    the child and a container's `v` counts only the commits that name it.

    Moving a node inside itself is refused. It is the one position that is not
    a position: the subtree would leave the document altogether and the commit
    would name one node while N disappeared.
    """
    why = require_reason(
        why,
        nodes=[each for each in (node_id, after, into) if each is not None],
        about=["ledger id %s" % ledger_id],
    )
    _one_position(after, into, ledger_id, moving=node_id)
    canvas_dir, path, root, head = _open_canvas(ledger_id)
    news = _check_base(canvas_dir, path, ledger_id, node_id, head, base)
    node = _addressed(root, node_id, ledger_id)

    target_id = after if after is not None else into
    target = document.find(root, target_id)
    if target is None:
        raise Refusal(
            "refusing to move %s: no node with id %s in the canvas for %s, so "
            "there is no such position. Nothing was moved"
            % (node_id, target_id, ledger_id),
            "`bin/canvas read %s` prints the canvas and every id in it; re-run "
            "naming --after <node-id> or --into <container-id> from those, "
            "where 'root' names the canvas itself" % ledger_id,
            nodes=[node_id, target_id],
            about=["ledger id %s" % ledger_id],
        )
    if document.contains(node, target):
        raise Refusal(
            "refusing to move <%s> %s %s %s: that position is inside the node "
            "being moved, so the node and its children would leave the document"
            % (
                node.tag,
                node_id,
                "after" if after is not None else "into",
                target_id,
            ),
            "name a position outside %s's own subtree — `bin/canvas read %s` "
            "prints the tree — or move %s out from under it first, with its "
            "own --why" % (node_id, ledger_id, target_id),
            nodes=[node_id, target_id],
            about=["ledger id %s" % ledger_id],
        )

    if author is None:
        author = default_author(canvas_dir)

    node.set("v", next_version(canvas_dir, node_id))
    document.detach(root, node_id)
    _place(root, node, after, into, ledger_id, moving=node_id)

    sha = _write_and_commit(
        canvas_dir,
        path,
        root,
        "move",
        node_id,
        why,
        author,
        node_id=node_id,
        base=head,
    )
    return sha, news
