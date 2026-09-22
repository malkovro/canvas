"""The canvas store: where a canvas lives, and how it is read and written.

One canvas per ledger row, at

    $OPENCLAW_WORKSPACE/state/canvas/<ledger_id>.xml

beside `state/ledger/<ledger_id>.json`. The engineering spec gives that path;
it is not chosen here.

`state/canvas` is **one git repository** holding every ledger row's file.
`node-identity.md` section 1 settles that: ids are unique across the whole
repository, and the documented history command `git log --grep='Canvas-Node:
b7'` is written with no path filter, so a repository per ledger id would
path-scope the uniqueness check by accident and make the documented command
wrong.

Every git invocation is pinned with `--git-dir` and `--work-tree`, never a bare
`git` relying on discovery from the working directory. If `state/canvas` ever
sits inside an outer git repository — someone version-controlled their
workspace — discovery would find the outer `.git` while the local "is there a
repo here" check still said no, and the commits would land in the wrong
repository. Pinning makes that impossible to express.

Every write is validated through `canvas.validate.validate_file` at a temporary
path and only then renamed into place, so an invalid canvas is never reachable
at the canvas's own path, let alone committed.
"""

import os
import re
import secrets
import subprocess

from canvas import document
from canvas.validate import EnvironmentProblem, validate_file


class Refusal(Exception):
    """The request is wrong against the store as it stands. Exit 1.

    The canvas already exists; there is no canvas for that ledger id; the
    document is invalid. Re-read and re-decide. Carries the diagnostics that
    say which, where there are any.
    """

    def __init__(self, message, details=()):
        Exception.__init__(self, message)
        self.details = list(details)


class ToolProblem(Exception):
    """The tool or its environment is wrong. Exit 2. Do not touch the canvas."""


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
            "state/canvas holds the canvases"
        )
    if not os.path.isdir(workspace):
        raise ToolProblem(
            "OPENCLAW_WORKSPACE is not a directory: %s" % workspace
        )
    return os.path.join(workspace, "state", "canvas")


def canvas_path(canvas_dir, ledger_id):
    """The file for one ledger row, or a ToolProblem if the id is not one."""
    if not _LEDGER_ID.match(ledger_id) or ledger_id.startswith("."):
        raise ToolProblem(
            "not a usable ledger id: %r; a ledger id is one or more of "
            "[A-Za-z0-9._-] and does not start with a dot" % ledger_id
        )
    return os.path.join(canvas_dir, ledger_id + ".xml")


# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------


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
        raise ToolProblem("cannot run git: %s" % error)


def _git_checked(canvas_dir, *arguments):
    result = _git(canvas_dir, *arguments)
    if result.returncode != 0:
        raise ToolProblem(
            "git %s exited %d: %s"
            % (
                " ".join(arguments),
                result.returncode,
                result.stderr.decode("utf-8", "replace").strip(),
            )
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
        raise ToolProblem("cannot create %s: %s" % (canvas_dir, error))
    # `git init <path>` names the path outright, so this does not depend on the
    # working directory either. -b main matches the code repository's default
    # branch and silences git's init.defaultBranch advice.
    result = subprocess.run(
        ["git", "init", "-b", "main", "-q", "--", canvas_dir],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise ToolProblem(
            "cannot initialise a git repository at %s: %s"
            % (canvas_dir, result.stderr.decode("utf-8", "replace").strip())
        )
    return True


def head_sha(canvas_dir):
    """The repository head, or None when it has no commits yet.

    The *repository* head, not the file's last-touching commit. That is what a
    later `--base` is compared against, and it is what makes the sha a read
    hands out usable as the base of the next write with no second lookup.
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
# Minting an id
# --------------------------------------------------------------------------


def is_free(canvas_dir, candidate):
    """Has this id ever been used anywhere in this canvas repository?

    `node-identity.md` section 1: "The uniqueness check is the git history
    itself. A candidate id is free if `git log --grep='Canvas-Node: <candidate>'`
    is empty. No registry file, no allocator state." Across the whole
    repository, with no path filter, because ids are unique across it and not
    within one file.
    """
    result = _git(
        canvas_dir, "log", "--grep=Canvas-Node: %s" % candidate, "--format=%H"
    )
    if result.returncode != 0:
        if head_sha(canvas_dir) is None:
            # No commits at all, so no id has ever been used. git log exits
            # non-zero on an unborn branch rather than printing nothing.
            return True
        raise ToolProblem(
            "cannot search the canvas history for %s: %s"
            % (candidate, result.stderr.decode("utf-8", "replace").strip())
        )
    return result.stdout.strip() == b""


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
        "could not mint a free node id in %d draws" % _MINT_ATTEMPTS
    )


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


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
        # Not an invalid document. The validator cannot run.
        raise ToolProblem("the validator cannot run: %s" % error)
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
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(document.serialise(root))
        problems = _validate(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    if problems:
        raise Refusal("refusing to create an invalid canvas at %s" % path, problems)


def write_and_commit(
    canvas_dir, path, root, subject, author, node_id=None, base=None
):
    """Validate the document, put it at `path`, commit it. Return the new sha.

    The document is written to a temporary name in the same directory and
    validated there. Only a document the validator passed is renamed onto the
    canvas's own path, so an invalid canvas is never reachable as a canvas — the
    rename is the moment it becomes one, and it is atomic.
    """
    text = document.serialise(root)
    temporary = "%s.tmp-%d" % (path, os.getpid())
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        problems = _validate(temporary, path)
        if problems:
            raise Refusal(
                "refusing to write an invalid canvas to %s" % path, problems
            )
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

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
        raise ToolProblem("committed to %s but the repository has no head" % canvas_dir)
    return sha


# --------------------------------------------------------------------------
# The two operations
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
    literally true and makes the chain self-describing. Writing a truthful
    trailer is not enforcing `--base`: nothing here compares a supplied base
    against anything.

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
            % (ledger_id, path, head_sha(canvas_dir))
        )

    if author is None:
        author = default_author(canvas_dir)

    preflight(path, ledger_id, (problem, expected_value))

    root = document.new_canvas(ledger_id)
    sha = write_and_commit(
        canvas_dir,
        path,
        root,
        "create %s: born at open, root only" % ledger_id,
        author,
    )

    first_nodes = (
        (problem, "the problem the ledger row states"),
        (expected_value, "the expected value the ledger row states"),
    )
    for content, reason in first_nodes:
        node_id = mint(canvas_dir)
        document.place_into(root, document.ROOT, document.new_text(node_id, content))
        sha = write_and_commit(
            canvas_dir,
            path,
            root,
            "insert %s: %s" % (node_id, reason),
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
        raise Refusal(
            "no canvas for ledger id %s: nothing at %s" % (ledger_id, path)
        )
    if not is_repository(canvas_dir):
        raise ToolProblem(
            "%s is not a git repository, so it has no sha to write against" % canvas_dir
        )

    sha = head_sha(canvas_dir)
    if sha is None:
        raise ToolProblem(
            "%s has no commits, so it has no sha to write against" % canvas_dir
        )

    with open(path, "rb") as handle:
        body = handle.read()
    return sha, body, _validate(path, path)
