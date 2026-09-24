"""Tests for the canvas store and the read path.

Everything here runs the real `bin/canvas` as a subprocess against a temporary
directory exported as OPENCLAW_WORKSPACE, and inspects the real git repository
the tool built. Nothing is mocked: the thing under test is whether a command
run from a clean workspace leaves a git-backed canvas on disk, and a mock of
git cannot answer that.

These assert behaviour, not wording, matching tests/test_validate.py's style:
exit codes, the shape of the document, the trailers on the commits, and the
sha the read hands out.

**No test may touch the live workspace.** Every test makes its own temporary
directory and points OPENCLAW_WORKSPACE at it; `LiveWorkspaceIsUntouched`
asserts that the fixtures really are temporary and that the tool refuses to
work with the variable unset, which is what makes an accidental live write
impossible rather than merely unlikely.
"""

import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANVAS = os.path.join(ROOT, "bin", "canvas")
VALIDATE = os.path.join(ROOT, "bin", "canvas-validate")

sys.path.insert(0, ROOT)

from canvas import document  # noqa: E402
from canvas import refusal, store  # noqa: E402
from canvas.validate import validate_file  # noqa: E402

SHA = re.compile(r"\A[0-9a-f]{40}\Z")

# node-identity.md section 1, and schema/canvas.rng's own pattern.
NODE_ID = re.compile(r"\A[a-z][a-hj-km-np-z2-9]{3}\Z")


class StoreTestCase(unittest.TestCase):
    """A fresh temporary workspace per test, with no state/ in it at all."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="canvas-store-test-")
        self.addCleanup(shutil.rmtree, self.workspace, True)
        self.canvas_dir = os.path.join(self.workspace, "state", "canvas")
        # The point of departure for every test: genuinely clean.
        self.assertFalse(os.path.exists(os.path.join(self.workspace, "state")))

    def run_canvas(self, *args, **kwargs):
        """Run bin/canvas. Returns (exit code, stdout bytes, stderr text)."""
        environment = dict(os.environ)
        workspace = kwargs.pop("workspace", self.workspace)
        if workspace is None:
            environment.pop("OPENCLAW_WORKSPACE", None)
        else:
            environment["OPENCLAW_WORKSPACE"] = workspace
        result = subprocess.run(
            [sys.executable, CANVAS] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        return (
            result.returncode,
            result.stdout,
            result.stderr.decode("utf-8", "replace"),
        )

    def git(self, *args):
        """Run git against the canvas repository the tool built."""
        result = subprocess.run(
            [
                "git",
                "--git-dir=%s" % os.path.join(self.canvas_dir, ".git"),
                "--work-tree=%s" % self.canvas_dir,
            ]
            + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(
            0, result.returncode, result.stderr.decode("utf-8", "replace")
        )
        return result.stdout.decode("utf-8", "replace")

    def create(self, ledger_id="a-ledger-row", problem="A problem.", value="A value."):
        code, stdout, stderr = self.run_canvas(
            "create", ledger_id, "--problem", problem, "--expected-value", value
        )
        self.assertEqual(0, code, stderr)
        return code, stdout, stderr

    def canvas_file(self, ledger_id="a-ledger-row"):
        return os.path.join(self.canvas_dir, ledger_id + ".xml")

    def header(self, stdout):
        """A read's header: every line above the `<?xml` declaration.

        README's boundary rule as the tests read it — the document begins at
        the declaration line and everything before it is the header. A diff in
        the header cannot be mistaken for it: a unified diff prefixes every
        line with a space, a `+` or a `-`, so only the document's own
        declaration starts at column zero.
        """
        lines = []
        for line in stdout.decode("utf-8").splitlines():
            if line.startswith("<?xml"):
                break
            lines.append(line)
        return lines

    def printed(self, stdout, name):
        """The values of one header line, in the order they were printed."""
        return [
            line.split(": ", 1)[1]
            for line in self.header(stdout)
            if line.startswith(name + ": ")
        ]

    def document(self, stdout):
        """The document alone, under any combination of flags."""
        text = stdout.decode("utf-8")
        return text[text.index("<?xml"):]

    def selected(self, *args, **kwargs):
        """Run a read that is expected to work, and parse what it printed."""
        code, stdout, stderr = self.run_canvas("read", *args)
        self.assertEqual(kwargs.get("code", 0), code, stderr)
        return stdout

    def subjects(self):
        return self.git("log", "--reverse", "--format=%s").splitlines()

    def bodies(self):
        return self.git("log", "--reverse", "--format=%B%x00").split("\x00")[:-1]


class CreateFromACleanWorkspace(StoreTestCase):
    """The done condition's first clause: bin/canvas runs from a clean
    workspace and creates a canvas for a ledger id as a git-backed file."""

    def test_create_exits_zero_and_reports_the_path_and_the_sha(self):
        code, stdout, stderr = self.create()
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        # By name and not by position: `create` now prints the ids it minted
        # above these two, and what a caller parses is the name.
        printed = dict(
            line.split(": ", 1) for line in stdout.decode("utf-8").splitlines()
        )
        self.assertTrue(SHA.match(printed["Canvas-Base"]), printed)
        self.assertEqual(self.canvas_file(), printed["Canvas-File"])

    def test_the_file_lands_beside_the_ledger_at_the_documented_path(self):
        self.create()
        self.assertTrue(os.path.isfile(self.canvas_file()))
        # The engineering spec's path, relative to the workspace, exactly.
        self.assertEqual(
            os.path.join("state", "canvas", "a-ledger-row.xml"),
            os.path.relpath(self.canvas_file(), self.workspace),
        )

    def test_the_canvas_directory_is_a_git_repository_afterwards(self):
        self.create()
        self.assertTrue(os.path.isdir(os.path.join(self.canvas_dir, ".git")))
        self.assertTrue(SHA.match(self.git("rev-parse", "HEAD").strip()))

    def test_the_created_document_validates(self):
        self.create()
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_the_created_document_validates_through_the_standalone_shim(self):
        self.create()
        result = subprocess.run(
            [sys.executable, VALIDATE, self.canvas_file()],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"", result.stderr)

    def test_the_document_holds_the_two_first_nodes_in_order(self):
        self.create(problem="The problem stated.", value="The value expected.")
        root = ElementTree.parse(self.canvas_file()).getroot()
        self.assertEqual("canvas", root.tag)
        self.assertEqual("a-ledger-row", root.get("ledger"))
        self.assertEqual("1", root.get("schema"))
        # The vocabulary has no semantic node, so the two first nodes are
        # <text> and the distinction lives in the order and the commit subject.
        self.assertEqual(["text", "text"], [child.tag for child in root])
        self.assertEqual(
            ["The problem stated.", "The value expected."],
            [child.text for child in root],
        )

    def test_the_root_carries_no_id_and_no_v(self):
        self.create()
        root = ElementTree.parse(self.canvas_file()).getroot()
        self.assertIsNone(root.get("id"))
        self.assertIsNone(root.get("v"))

    def test_every_node_is_born_at_v_one_with_a_well_formed_id(self):
        self.create()
        root = ElementTree.parse(self.canvas_file()).getroot()
        for child in root:
            self.assertEqual("1", child.get("v"))
            self.assertTrue(NODE_ID.match(child.get("id")), child.get("id"))

    def test_a_create_leaves_nothing_uncommitted_behind(self):
        self.create()
        self.assertEqual("", self.git("status", "--porcelain"))


class OneEditIsOneCommit(StoreTestCase):
    """node-identity.md section 4: the creation commit creates the root only,
    and the two first nodes arrive as two ordinary insert commits."""

    def test_a_create_is_three_commits(self):
        self.create()
        self.assertEqual(3, len(self.subjects()))

    def test_the_creation_commit_creates_the_root_only(self):
        self.create()
        first = self.git("log", "--reverse", "--format=%H").splitlines()[0]
        born = self.git("show", "%s:a-ledger-row.xml" % first)
        root = ElementTree.fromstring(born)
        self.assertEqual("canvas", root.tag)
        self.assertEqual([], list(root))

    def test_the_creation_commit_names_no_node(self):
        # <canvas> carries no id and no v; it is outside the identity rules
        # entirely, so a Canvas-Node: trailer would name a node that does not
        # exist and `git log --grep` would return a commit for it.
        self.create()
        self.assertNotIn("Canvas-Node:", self.bodies()[0])

    def test_each_insert_commit_names_exactly_one_node(self):
        self.create()
        for body in self.bodies()[1:]:
            self.assertEqual(1, body.count("Canvas-Node:"), body)

    def test_the_two_first_nodes_have_different_ids(self):
        self.create()
        named = [
            line.split(": ", 1)[1].strip()
            for body in self.bodies()
            for line in body.splitlines()
            if line.startswith("Canvas-Node: ")
        ]
        self.assertEqual(2, len(named))
        self.assertNotEqual(named[0], named[1])

    def test_a_nodes_history_is_exactly_the_commits_that_name_it(self):
        # node-identity.md section 4: v equals the number of commits whose
        # Canvas-Node: trailer names that node, and the documented history
        # command has no path filter.
        self.create()
        root = ElementTree.parse(self.canvas_file()).getroot()
        for child in root:
            node_id = child.get("id")
            found = self.git(
                "log", "--grep=Canvas-Node: %s" % node_id, "--format=%H"
            ).split()
            self.assertEqual(1, len(found), node_id)
            self.assertEqual(str(len(found)), child.get("v"))

    def test_every_commit_names_its_author(self):
        self.create()
        for body in self.bodies():
            self.assertIn("Canvas-Author:", body)

    def test_an_explicit_author_is_used_verbatim(self):
        code, _, stderr = self.run_canvas(
            "create",
            "a-ledger-row",
            "--problem",
            "P",
            "--expected-value",
            "E",
            "--author",
            "leo | step:implement | run:ship-the-flag-3",
        )
        self.assertEqual(0, code, stderr)
        for body in self.bodies():
            self.assertIn(
                "Canvas-Author: leo | step:implement | run:ship-the-flag-3", body
            )

    def test_the_insert_commits_base_on_the_commit_before_them(self):
        self.create()
        shas = self.git("log", "--reverse", "--format=%H").split()
        bodies = self.bodies()
        # The root commit had no prior state to be decided against.
        self.assertNotIn("Canvas-Base:", bodies[0])
        self.assertIn("Canvas-Base: %s" % shas[0], bodies[1])
        self.assertIn("Canvas-Base: %s" % shas[1], bodies[2])

    def test_the_commit_subject_names_the_verb_and_the_node(self):
        self.create()
        subjects = self.subjects()
        self.assertTrue(subjects[0].startswith("create a-ledger-row:"), subjects)
        root = ElementTree.parse(self.canvas_file()).getroot()
        for subject, child in zip(subjects[1:], root):
            self.assertTrue(
                subject.startswith("insert %s:" % child.get("id")), subject
            )


class OneCommitIsOneCanvas(StoreTestCase):
    """A write commits its own file and nothing else.

    `state/canvas` is one repository for every ledger row, which
    `node-identity.md` section 1 settles, and one repository is one *index*.
    The write path staged path-scoped and committed with no pathspec, so a
    second writer that had staged its own canvas in between had that canvas
    committed too: one commit carrying two rows' edits, under a subject, a
    `Canvas-Node:` trailer and a reason belonging to one of them. It happened
    once in 99 commits of the live store, at 59f6946 — see
    `docs/unattributed-edits.md`.

    Every test here dirties a second canvas's path and stages it *before* the
    write under test, which is the concurrent writer's half of that race made
    deterministic. There is no thread and no second process: what the race
    produces is an index entry, and an index entry is what these put there.
    """

    OTHER = "another-ledger-row"

    def two_canvases(self):
        """Two canvases in one store, with the second one staged and dirty."""
        self.create()
        self.create(self.OTHER, problem="Another problem.", value="Another value.")
        self.meddle_with(self.OTHER)

    def meddle_with(self, ledger_id):
        """Edit a canvas behind the tool's back and stage it, as a rival would.

        Not through `bin/canvas`: the point is an index entry this process did
        not put there, and a real write would commit it and leave nothing
        staged. The edit is to the text of a node, so the file genuinely
        differs and `git` genuinely stages a change.
        """
        path = self.canvas_file(ledger_id)
        with open(path, "rb") as handle:
            before = handle.read()
        after = before.replace(b"Another problem.", b"Another problem, meddled with.")
        self.assertNotEqual(before, after)
        with open(path, "wb") as handle:
            handle.write(after)
        self.git("add", "-f", "--", path)
        self.assertEqual(["M  %s.xml" % ledger_id], self.staged())

    def staged(self):
        return self.git("status", "--porcelain").splitlines()

    def files_in(self, sha="HEAD"):
        """The paths one commit changed, which is what this class is about."""
        return self.git("show", "--name-only", "--format=", sha).split()

    def commits_touching(self, ledger_id):
        return self.git(
            "log", "--format=%H", "--", self.canvas_file(ledger_id)
        ).split()

    def test_a_write_commits_its_own_file_and_nothing_else(self):
        self.two_canvases()
        code, _, stderr = self.run_canvas(
            "insert",
            "a-ledger-row",
            "--into",
            "root",
            "--text",
            "A node this commit is about.",
            "--why",
            "the node this commit is about, and the only file it may contain",
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(["a-ledger-row.xml"], self.files_in())

    def test_the_other_canvas_gains_no_commit(self):
        self.two_canvases()
        before = self.commits_touching(self.OTHER)
        code, _, stderr = self.run_canvas(
            "insert",
            "a-ledger-row",
            "--into",
            "root",
            "--text",
            "A node this commit is about.",
            "--why",
            "the node this commit is about, and the only file it may contain",
        )
        self.assertEqual(0, code, stderr)
        # The defect's visible shape: the other row's history growing a commit
        # whose reason is about a node in a different canvas, which is what
        # leaves an edit there that `history` can never attribute.
        self.assertEqual(before, self.commits_touching(self.OTHER))

    def test_the_other_writers_staged_edit_is_left_staged(self):
        self.two_canvases()
        code, _, stderr = self.run_canvas(
            "insert",
            "a-ledger-row",
            "--into",
            "root",
            "--text",
            "A node this commit is about.",
            "--why",
            "the node this commit is about, and the only file it may contain",
        )
        self.assertEqual(0, code, stderr)
        # Left for the writer that staged it, to be committed by its own commit
        # under its own reason. Stealing it and dropping it are the same defect.
        self.assertEqual(["M  %s.xml" % self.OTHER], self.staged())

    def test_every_verb_commits_its_own_file_and_nothing_else(self):
        # All four editing verbs, in one store where a rival's canvas is staged
        # throughout. The guard is in `_write_and_commit` and every verb goes
        # through it, so this is the assertion that none of them found a second
        # way out.
        self.two_canvases()
        problem_id, value_id = [
            node.get("id")
            for node in ElementTree.parse(self.canvas_file()).getroot()
        ]
        minted = None
        edits = [
            ("insert", ["--into", "root", "--text", "A fourth node."]),
            ("replace", [None, "--text", "The problem, restated."]),
            ("move", [None, "--after", "MINTED"]),
            ("remove", [None]),
        ]
        for verb, arguments in edits:
            arguments = list(arguments)
            if arguments and arguments[0] is None:
                arguments[0] = problem_id if verb == "replace" else value_id
            arguments = [minted if a == "MINTED" else a for a in arguments]
            code, stdout, stderr = self.run_canvas(
                "%s" % verb,
                "a-ledger-row",
                *(arguments + ["--why", "one canvas per commit, for %s" % verb])
            )
            self.assertEqual(0, code, stderr)
            if verb == "insert":
                minted = stdout.decode("utf-8").splitlines()[0].split(": ", 1)[1]
            self.assertEqual(["a-ledger-row.xml"], self.files_in(), verb)
            self.assertEqual(["M  %s.xml" % self.OTHER], self.staged(), verb)

    def test_a_birth_commits_only_the_canvas_being_born(self):
        # `create` makes three commits and the first of them writes a file that
        # was not tracked a moment ago, which is the one shape a pathspec on the
        # commit could have broken. It does not: the `add` before it is what
        # puts the path where a pathspec can name it.
        self.create()
        self.create(self.OTHER, problem="Another problem.", value="Another value.")
        self.meddle_with(self.OTHER)
        code, _, stderr = self.run_canvas(
            "create", "a-third-ledger-row", "--problem", "P", "--expected-value", "E"
        )
        self.assertEqual(0, code, stderr)
        for sha in self.git("log", "--format=%H", "-3").split():
            self.assertEqual(["a-third-ledger-row.xml"], self.files_in(sha))
        self.assertEqual(["M  %s.xml" % self.OTHER], self.staged())

    def test_a_freeze_still_commits_no_file_at_all(self):
        # The freeze's commit is `--allow-empty` and changes no byte of the
        # document. A pathspec does not turn it into a commit of anything: it
        # stays empty, and it stays unable to sweep up what is staged beside it.
        self.two_canvases()
        code, _, stderr = self.run_canvas(
            "freeze", "a-ledger-row", "--why", "done: the row closed, and this ends it"
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual([], self.files_in())
        self.assertEqual(["M  %s.xml" % self.OTHER], self.staged())

    def test_a_refused_write_commits_nothing_and_leaves_the_rival_staged(self):
        # The refusal path renames a document onto the canvas's own path before
        # git is asked for anything and takes it back when git refuses. What is
        # asserted here is the other half of that: a write this store refuses on
        # its own terms must not reach the rival's staged entry either.
        self.two_canvases()
        head = self.git("rev-parse", "HEAD").strip()
        code, _, stderr = self.run_canvas(
            "replace",
            "a-ledger-row",
            "zzzz",
            "--text",
            "A node that is not there.",
            "--why",
            "a write this store refuses on its own terms",
        )
        self.assertEqual(1, code, stderr)
        self.assertEqual(head, self.git("rev-parse", "HEAD").strip())
        self.assertEqual(["M  %s.xml" % self.OTHER], self.staged())


class TheReadPath(StoreTestCase):
    """The done condition's second clause: a read prints both the document and
    the sha to write against."""

    def test_read_prints_the_sha_first_then_the_document(self):
        self.create()
        code, stdout, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        head, _, body = stdout.partition(b"\n")
        self.assertEqual(
            b"Canvas-Base: " + self.git("rev-parse", "HEAD").strip().encode(), head
        )
        with open(self.canvas_file(), "rb") as handle:
            self.assertEqual(handle.read(), body)

    def test_the_sha_it_hands_out_is_the_repository_head_in_full(self):
        self.create()
        _, stdout, _ = self.run_canvas("read", "a-ledger-row")
        handed_out = stdout.decode("utf-8").splitlines()[0].split(": ", 1)[1]
        self.assertTrue(SHA.match(handed_out), handed_out)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), handed_out)

    def test_read_writes_nothing_and_commits_nothing(self):
        self.create()
        before_sha = self.git("rev-parse", "HEAD")
        before_log = self.git("log", "--format=%H")
        with open(self.canvas_file(), "rb") as handle:
            before_bytes = handle.read()
        before_listing = sorted(os.listdir(self.canvas_dir))
        a_node_id = list(ElementTree.parse(self.canvas_file()).getroot())[0].get("id")

        # Every flag the read path takes, and the bare read. None of them is a
        # write, a lock, or anything that initialises: all any of them adds is
        # git log, git diff, git rev-parse and git merge-base.
        for flags in (
            (),
            ("--type", "text"),
            ("--id", a_node_id),
            ("--provenance",),
            ("--since", before_sha.strip()),
            ("--type", "question", "--provenance", "--since", before_sha.strip()),
        ):
            code, _, stderr = self.run_canvas("read", "a-ledger-row", *flags)
            self.assertEqual(0, code, "%s\n%s" % (flags, stderr))

            self.assertEqual(before_sha, self.git("rev-parse", "HEAD"), flags)
            self.assertEqual(before_log, self.git("log", "--format=%H"), flags)
            with open(self.canvas_file(), "rb") as handle:
                self.assertEqual(before_bytes, handle.read(), flags)
            self.assertEqual(
                before_listing, sorted(os.listdir(self.canvas_dir)), flags
            )
            self.assertEqual("", self.git("status", "--porcelain"), flags)

    def test_the_document_alone_is_what_is_on_disk_byte_for_byte(self):
        self.create()
        _, stdout, _ = self.run_canvas("read", "a-ledger-row")
        # The documented way to get the document alone: tail -n +2.
        printed = b"\n".join(stdout.split(b"\n")[1:])
        with open(self.canvas_file(), "rb") as handle:
            self.assertEqual(handle.read(), printed)

    def test_the_sha_a_read_hands_out_moves_when_the_canvas_does(self):
        self.create()
        _, first, _ = self.run_canvas("read", "a-ledger-row")
        self.create(ledger_id="another-row")
        _, second, _ = self.run_canvas("read", "a-ledger-row")
        self.assertNotEqual(first.splitlines()[0], second.splitlines()[0])
        # Because it is the repository head, not the file's last-touching
        # commit: that is what a later --base is compared against.
        self.assertEqual(
            b"Canvas-Base: " + self.git("rev-parse", "HEAD").strip().encode(),
            second.splitlines()[0],
        )

    def test_read_does_not_create_a_repository(self):
        # A read is a read. A workspace with no canvas repository has no canvas
        # to read, and initialising one to say so would be a write. True under
        # every flag: none of them is a reason to make a repository either.
        for flags in (
            (),
            ("--type", "question"),
            ("--id", "abcd"),
            ("--provenance",),
            ("--since", "0123456789abcdef0123456789abcdef01234567"),
        ):
            code, stdout, stderr = self.run_canvas(
                "read", "a-ledger-row", *flags
            )
            self.assertEqual(1, code, "%s\n%s" % (flags, stderr))
            self.assertEqual(b"", stdout, flags)
            self.assertFalse(
                os.path.exists(os.path.join(self.workspace, "state")), flags
            )


class TheRepositoryIsNeverReinitialised(StoreTestCase):
    """Initialised on first use, and never over one that exists."""

    def test_a_second_create_keeps_the_first_canvas_and_its_history(self):
        self.create(ledger_id="first-row")
        first_sha = self.git("rev-parse", "HEAD").strip()
        first_log = self.git("log", "--format=%H").split()

        self.create(ledger_id="second-row")

        self.assertTrue(os.path.isfile(self.canvas_file("first-row")))
        self.assertTrue(os.path.isfile(self.canvas_file("second-row")))
        # Every commit of the first canvas is still reachable, which a re-init
        # would have destroyed.
        now = self.git("log", "--format=%H").split()
        for sha in first_log:
            self.assertIn(sha, now)
        self.assertEqual(6, len(now))
        self.git("cat-file", "-e", first_sha)

    def test_ids_are_unique_across_the_repository_not_within_one_file(self):
        self.create(ledger_id="first-row")
        self.create(ledger_id="second-row")
        ids = []
        for ledger_id in ("first-row", "second-row"):
            root = ElementTree.parse(self.canvas_file(ledger_id)).getroot()
            ids.extend(child.get("id") for child in root)
        self.assertEqual(4, len(ids))
        self.assertEqual(4, len(set(ids)), ids)
        # The documented history command carries no path filter, so a grep for
        # any one of them returns exactly its own commit and no other file's.
        for node_id in ids:
            found = self.git(
                "log", "--grep=Canvas-Node: %s" % node_id, "--format=%H"
            ).split()
            self.assertEqual(1, len(found), node_id)


class CreateRefusesRatherThanCorrupts(StoreTestCase):
    """A second create over an existing canvas must not corrupt anything."""

    def test_a_second_create_for_the_same_ledger_id_is_refused(self):
        self.create()
        code, stdout, stderr = self.run_canvas(
            "create",
            "a-ledger-row",
            "--problem",
            "Something else.",
            "--expected-value",
            "Something else again.",
        )
        self.assertEqual(1, code)
        self.assertEqual(b"", stdout)
        self.assertIn(self.canvas_file(), stderr)

    def test_a_refused_create_changes_neither_the_file_nor_the_history(self):
        self.create(problem="The original problem.")
        with open(self.canvas_file(), "rb") as handle:
            before = handle.read()
        before_log = self.git("log", "--format=%H")

        self.run_canvas(
            "create",
            "a-ledger-row",
            "--problem",
            "An overwrite.",
            "--expected-value",
            "An overwrite.",
        )

        with open(self.canvas_file(), "rb") as handle:
            self.assertEqual(before, handle.read())
        self.assertEqual(before_log, self.git("log", "--format=%H"))
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_a_refused_create_mints_no_id(self):
        self.create()
        before = self.git("log", "--format=%H").split()
        self.run_canvas(
            "create", "a-ledger-row", "--problem", "x", "--expected-value", "y"
        )
        self.assertEqual(before, self.git("log", "--format=%H").split())

    def test_text_xml_cannot_hold_is_refused_with_nothing_written(self):
        # A backspace is a legal command-line argument and an illegal XML
        # character, so this is the one way a create's document can be invalid.
        code, stdout, stderr = self.run_canvas(
            "create", "a-ledger-row", "--problem", "a\bb", "--expected-value", "E"
        )
        self.assertEqual(1, code)
        self.assertEqual(b"", stdout)
        self.assertNotEqual("", stderr)
        self.assertFalse(os.path.exists(self.canvas_file()))
        # And the rejected attempt leaves the ledger id free to try again.
        self.create()
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_no_temporary_file_survives_a_refusal(self):
        self.run_canvas(
            "create", "a-ledger-row", "--problem", "a\bb", "--expected-value", "E"
        )
        leftovers = [
            name
            for name in os.listdir(self.canvas_dir)
            if name != ".git" and not name.endswith(".xml")
        ]
        self.assertEqual([], leftovers)


class ACanvasIsNotBornBlank(StoreTestCase):
    """`create` refuses a blank `--problem` or `--expected-value`, writing nothing.

    The two first nodes are the whole of what a canvas understands at birth,
    and the store cannot hold "deliberately blank" and say so: `_render` writes
    `<text id="…" v="1"/>` for `None` and for `""` alike, and the renderer
    prints nothing for it. So a blank one reads exactly like a lost one, and
    the answer is the one `--why` already gets — absent, empty and
    whitespace-only alike, at exit 2, before the store is opened.

    It used to be two different answers for the same mistake. An empty
    `--problem` landed two of the three commits and had the third refused by
    the tool's own one-edit-is-one-node guard, naming a node the caller had
    never edited, and `create` refuses to overwrite — so the canvas existed,
    had no expected-value node, and could not be retried. An empty
    `--expected-value` exited 0 and made all three, because the blank node was
    the last one written and the one its commit named.
    """

    BLANK = ("", "   ", "\n\t ")

    def blank_create(self, flag, blank, ledger_id="a-ledger-row"):
        arguments = {"--problem": "A problem.", "--expected-value": "A value."}
        arguments[flag] = blank
        return self.run_canvas(
            "create",
            ledger_id,
            "--problem",
            arguments["--problem"],
            "--expected-value",
            arguments["--expected-value"],
        )

    def test_a_blank_problem_is_refused_at_exit_two(self):
        for blank in self.BLANK:
            with self.subTest(blank=repr(blank)):
                code, stdout, stderr = self.blank_create("--problem", blank)
                self.assertEqual(2, code, stderr)
                self.assertEqual(b"", stdout)
                self.assertIn("--problem is required and must not be empty", stderr)

    def test_a_blank_expected_value_is_refused_at_exit_two(self):
        for blank in self.BLANK:
            with self.subTest(blank=repr(blank)):
                code, stdout, stderr = self.blank_create("--expected-value", blank)
                self.assertEqual(2, code, stderr)
                self.assertEqual(b"", stdout)
                self.assertIn(
                    "--expected-value is required and must not be empty", stderr
                )

    def test_the_refusal_names_the_flag_the_ledger_id_and_the_exit_code(self):
        _, _, stderr = self.blank_create("--problem", "")
        self.assertIn("Canvas-About: option --problem", stderr)
        self.assertIn("Canvas-About: ledger id a-ledger-row", stderr)
        self.assertIn("Canvas-Exit: 2", stderr)
        self.assertIn("nothing was written, committed or minted", stderr)

    def test_a_blank_create_leaves_no_store_at_all(self):
        # Not merely no canvas: the guard runs before `ensure_repository`, so
        # a refused create does not even initialise the repository. This is
        # the half-made canvas made impossible at its source.
        for flag in ("--problem", "--expected-value"):
            with self.subTest(flag=flag):
                self.blank_create(flag, "")
                self.assertFalse(
                    os.path.exists(os.path.join(self.workspace, "state"))
                )

    def test_the_ledger_id_is_still_free_after_a_blank_create(self):
        # The whole of what went wrong before: the canvas existed, so it could
        # not be created again, and it had no expected-value node.
        self.blank_create("--problem", "")
        self.create()
        self.assertEqual([], validate_file(self.canvas_file()))
        self.assertEqual(
            [
                "create a-ledger-row: born at open, root only",
                "insert %s: the problem the ledger row states" % self.minted(0),
                "insert %s: the expected value the ledger row states" % self.minted(1),
            ],
            self.subjects(),
        )

    def minted(self, index):
        """The id of one of the two nodes in the canvas, in document order."""
        return [node.get("id") for node in document.parse(self.canvas_file())][index]

    def test_a_blank_create_over_an_existing_canvas_touches_nothing(self):
        # The invocation is wrong whatever the store holds, so the flag is
        # what the refusal is about — and the canvas that is there is neither
        # read nor written on the way to saying so.
        self.create(problem="The original problem.")
        with open(self.canvas_file(), "rb") as handle:
            before = handle.read()
        before_log = self.git("log", "--format=%H")

        code, stdout, stderr = self.blank_create("--expected-value", "")

        self.assertEqual(2, code)
        self.assertEqual(b"", stdout)
        self.assertIn("--expected-value is required", stderr)
        with open(self.canvas_file(), "rb") as handle:
            self.assertEqual(before, handle.read())
        self.assertEqual(before_log, self.git("log", "--format=%H"))
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_content_that_is_not_blank_is_stored_verbatim(self):
        # The guard decides whether there is content, not what it looks like.
        self.create(problem="  padded  ", value="A value.")
        self.assertEqual(
            "  padded  ", list(document.parse(self.canvas_file()))[0].text
        )

    def test_a_node_may_still_be_inserted_blank(self):
        # The boundary of the decision, pinned so it is not read as wider than
        # it is. An `insert` carries a `--why` saying what the node is for, so
        # a reader who finds it blank can ask `history`. `create`'s two nodes
        # get the two fixed reasons the tool writes, so a blank one would
        # arrive under a reason describing content it does not have.
        self.create()
        code, _, stderr = self.run_canvas(
            "insert",
            "a-ledger-row",
            "--into",
            "root",
            "--text",
            "",
            "--why",
            "a placeholder this row will fill once the reduction has been run",
        )
        self.assertEqual(0, code, stderr)
        self.assertIsNone(list(document.parse(self.canvas_file()))[-1].text)


class CharacterDataTheStoreCannotTellApart(StoreTestCase):
    """`None` and `""` are one state, so no guard may report them as two.

    `document._render` writes `<tag/>` for both and `document.parse` reads that
    one spelling back as `None`, so a document held in memory with `""` and the
    same document read off disk are the same bytes. `_shape` compared them raw,
    which is how the one-edit-is-one-node guard came to refuse a write for
    "also changing" a node whose character data nobody had touched.

    Reached through `_write_and_commit` rather than a command line: `create`
    now refuses the blank content that used to get there, so this is the layer
    the defect actually lived at, exercised as `create` exercised it — one root
    held in memory across successive writes.
    """

    AUTHOR = "audit | by-hand"

    def written(self, root, verb, subject, why, node_id=None, base=None):
        return store._write_and_commit(
            self.canvas_dir,
            self.canvas_file(),
            root,
            verb,
            subject,
            why,
            self.AUTHOR,
            node_id=node_id,
            base=base,
        )

    def test_the_shape_records_none_and_the_empty_string_alike(self):
        absent = document.new_canvas("a-ledger-row")
        document.place_into(absent, document.ROOT, document.new_text("qqqq", None))
        empty = document.new_canvas("a-ledger-row")
        document.place_into(empty, document.ROOT, document.new_text("qqqq", ""))
        self.assertEqual(store._shape(absent), store._shape(empty))

    def test_a_root_held_across_writes_completes_its_third_commit(self):
        # Exactly `create`'s sequence: three writes off one in-memory root,
        # whose first node's character data is the empty string. The third
        # write used to be refused — "refusing to write a commit naming pppp
        # that also changes 1 other node(s) (qqqq)" — because `qqqq` read `""`
        # in memory and `None` off disk.
        os.makedirs(self.canvas_dir)
        store.ensure_repository(self.canvas_dir)
        root = document.new_canvas("a-ledger-row")
        sha = self.written(root, "create", "a-ledger-row", "born at open, root only")

        document.place_into(root, document.ROOT, document.new_text("qqqq", ""))
        sha = self.written(
            root, "insert", "qqqq", "a node with no text in it", node_id="qqqq",
            base=sha,
        )

        document.place_into(root, document.ROOT, document.new_text("pppp", "x"))
        self.written(
            root, "insert", "pppp", "the node this commit is about", node_id="pppp",
            base=sha,
        )

        self.assertEqual(
            [
                "create a-ledger-row: born at open, root only",
                "insert qqqq: a node with no text in it",
                "insert pppp: the node this commit is about",
            ],
            self.subjects(),
        )
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_the_guard_still_refuses_a_real_change_to_another_node(self):
        # The control the normalisation must not break: text that genuinely
        # differs is still a second node changed, and still refused.
        self.create()
        tree = document.parse(self.canvas_file())
        first, second = list(tree)
        first.text = "rewritten behind the trailer's back"
        document.place_into(tree, document.ROOT, document.new_text("pppp", "x"))
        with self.assertRaises(store.Refusal) as caught:
            self.written(
                tree, "insert", "pppp", "one node too many", node_id="pppp"
            )
        self.assertIn("one edit is one node", str(caught.exception))
        self.assertIn(first.get("id"), str(caught.exception))
        self.assertNotIn(second.get("id"), str(caught.exception))

    def test_emptying_a_node_is_still_that_node_changing(self):
        # And the other control: `""` and `None` being one state says nothing
        # about `"x"` and `""`, which is an edit like any other.
        self.create()
        tree = document.parse(self.canvas_file())
        first, second = list(tree)
        second.text = ""
        with self.assertRaises(store.Refusal) as caught:
            self.written(
                tree, "replace", first.get("id"), "emptying somebody else's node",
                node_id=first.get("id"),
            )
        self.assertIn(second.get("id"), str(caught.exception))


class ReadRefusesWhatIsNotThere(StoreTestCase):
    def test_reading_a_ledger_id_with_no_canvas_exits_one(self):
        self.create(ledger_id="a-row-that-exists")
        code, stdout, stderr = self.run_canvas("read", "no-such-row")
        self.assertEqual(1, code)
        self.assertEqual(b"", stdout)
        self.assertIn("no-such-row", stderr)


class TheToolAndItsEnvironment(StoreTestCase):
    """Exit 2 is "the tool or its environment is wrong. Do not touch the
    canvas", as distinct from exit 1's "the request is wrong against the
    store as it stands"."""

    def test_an_unset_workspace_exits_two_and_writes_nothing(self):
        code, _, stderr = self.run_canvas("read", "a-ledger-row", workspace=None)
        self.assertEqual(2, code)
        self.assertIn("OPENCLAW_WORKSPACE", stderr)

    def test_a_workspace_that_is_not_a_directory_exits_two(self):
        missing = os.path.join(self.workspace, "not-here")
        code, _, stderr = self.run_canvas(
            "create",
            "a-ledger-row",
            "--problem",
            "P",
            "--expected-value",
            "E",
            workspace=missing,
        )
        self.assertEqual(2, code)
        self.assertIn("OPENCLAW_WORKSPACE", stderr)
        self.assertFalse(os.path.exists(missing))

    def test_a_ledger_id_that_is_not_a_filename_exits_two(self):
        for ledger_id in ("../../../etc/passwd", "a/b", ".hidden", "", "with space"):
            code, _, stderr = self.run_canvas("read", ledger_id)
            self.assertEqual(2, code, ledger_id)
            self.assertIn("ledger id", stderr)

    def test_a_traversing_ledger_id_writes_nothing_anywhere(self):
        before = sorted(os.listdir(self.workspace))
        code, _, _ = self.run_canvas(
            "create",
            "../escaped",
            "--problem",
            "P",
            "--expected-value",
            "E",
        )
        self.assertEqual(2, code)
        self.assertEqual(before, sorted(os.listdir(self.workspace)))
        self.assertFalse(
            os.path.exists(os.path.join(os.path.dirname(self.workspace), "escaped.xml"))
        )

    def test_no_verb_exits_two(self):
        code, _, stderr = self.run_canvas()
        self.assertEqual(2, code)
        self.assertIn("usage", stderr)

    def test_an_unknown_verb_exits_two(self):
        code, _, _ = self.run_canvas("frobnicate", "a-ledger-row")
        self.assertEqual(2, code)

    def test_a_missing_required_argument_exits_two(self):
        code, _, _ = self.run_canvas("create", "a-ledger-row", "--problem", "P")
        self.assertEqual(2, code)
        self.assertFalse(os.path.exists(self.canvas_file()))


class AddressingAPositionInAnEmptyContainer(StoreTestCase):
    """node-identity.md left this open in *Still open*; canvas/document.py
    answers it, because step 1 cannot be built without an answer."""

    def test_into_names_the_first_position_of_an_empty_container(self):
        root = document.new_canvas("a-ledger-row")
        self.assertEqual([], list(root))
        document.place_into(root, document.ROOT, document.new_text("q4rt", "first"))
        self.assertEqual(["q4rt"], [child.get("id") for child in root])

    def test_into_appends_so_repeated_inserts_come_out_in_reading_order(self):
        root = document.new_canvas("a-ledger-row")
        for node_id in ("q4rt", "jc5v", "k3xq"):
            document.place_into(root, document.ROOT, document.new_text(node_id, node_id))
        self.assertEqual(
            ["q4rt", "jc5v", "k3xq"], [child.get("id") for child in root]
        )

    def test_after_puts_a_node_next_to_its_named_sibling(self):
        root = document.new_canvas("a-ledger-row")
        for node_id in ("q4rt", "k3xq"):
            document.place_into(root, document.ROOT, document.new_text(node_id, node_id))
        document.place_after(root, "q4rt", document.new_text("jc5v", "between"))
        self.assertEqual(
            ["q4rt", "jc5v", "k3xq"], [child.get("id") for child in root]
        )

    def test_the_reserved_word_root_can_never_collide_with_a_minted_id(self):
        # The id grammar excludes `o` from positions two to four, so r-o-o-t
        # fails the pattern by construction.
        self.assertIsNone(NODE_ID.match(document.ROOT))

    def test_a_position_naming_an_absent_node_is_refused(self):
        root = document.new_canvas("a-ledger-row")
        for place in (document.place_after, document.place_into):
            with self.assertRaises(document.PositionProblem):
                place(root, "q4rt", document.new_text("jc5v", "x"))


class TheSerialisedShape(StoreTestCase):
    """The shape tests/fixtures/valid.xml already shows."""

    def test_the_file_opens_with_a_declaration_and_ends_with_one_newline(self):
        self.create()
        with open(self.canvas_file(), "rb") as handle:
            written = handle.read()
        self.assertTrue(written.startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n'))
        self.assertTrue(written.endswith(b"</canvas>\n"))
        self.assertFalse(written.endswith(b"\n\n"))

    def test_nodes_are_one_per_line_at_two_space_indentation(self):
        self.create()
        with open(self.canvas_file(), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        for line in lines[3:-1]:
            self.assertTrue(line.startswith("  <text "), line)

    def test_a_childless_root_closes_without_a_space(self):
        # <canvas .../>, the way tests/fixtures/born.xml writes it, not
        # <canvas ... /> the way ElementTree.tostring would.
        root = document.new_canvas("a-ledger-row")
        self.assertIn('schema="1"/>', document.serialise(root))

    def test_markup_in_the_text_is_escaped_and_survives_a_round_trip(self):
        awkward = 'a < b & c > d "quoted" \'single\''
        self.create(problem=awkward)
        self.assertEqual([], validate_file(self.canvas_file()))
        root = ElementTree.parse(self.canvas_file()).getroot()
        self.assertEqual(awkward, list(root)[0].text)

    def test_a_ledger_id_is_written_into_the_root_verbatim(self):
        self.create(ledger_id="bc-10326884458-deliver-the-first-priority-canvas-todo-b")
        root = ElementTree.parse(
            self.canvas_file("bc-10326884458-deliver-the-first-priority-canvas-todo-b")
        ).getroot()
        self.assertEqual(
            "bc-10326884458-deliver-the-first-priority-canvas-todo-b",
            root.get("ledger"),
        )


class LiveWorkspaceIsUntouched(StoreTestCase):
    """The live workspace holds real ledger rows. Nothing in this suite may
    write to it, and that has to be checked rather than intended."""

    def test_the_fixture_workspace_is_a_temporary_directory(self):
        self.assertTrue(
            self.workspace.startswith(tempfile.gettempdir()), self.workspace
        )
        self.assertIn("canvas-store-test-", self.workspace)

    def test_the_tool_has_no_default_workspace_to_fall_back_to(self):
        # The guard that makes an accidental write to the live workspace
        # impossible rather than unlikely: with the variable unset there is
        # nowhere for the tool to go.
        code, _, stderr = self.run_canvas(
            "create",
            "a-ledger-row",
            "--problem",
            "P",
            "--expected-value",
            "E",
            workspace=None,
        )
        self.assertEqual(2, code)
        self.assertIn("OPENCLAW_WORKSPACE", stderr)


class VerbTestCase(StoreTestCase):
    """A canvas with its two first nodes, and the means to look at it after an
    edit: the tree, the ids in it, and whether anything moved at all."""

    def setUp(self):
        StoreTestCase.setUp(self)
        self.create(problem="The problem stated.", value="The value expected.")
        self.problem_id, self.value_id = self.ids()

    def tree(self, ledger_id="a-ledger-row"):
        return ElementTree.parse(self.canvas_file(ledger_id)).getroot()

    def ids(self):
        return [node.get("id") for node in self.tree().iter() if node.get("id")]

    def node(self, node_id):
        for node in self.tree().iter():
            if node.get("id") == node_id:
                return node
        return None

    def history(self, node_id):
        """The commits that name the node — what `v` counts."""
        return self.git(
            "log", "--grep=Canvas-Node: %s" % node_id, "--format=%H"
        ).split()

    def state(self):
        """Everything an edit could have changed, in one comparable value."""
        with open(self.canvas_file(), "rb") as handle:
            return (
                handle.read(),
                self.git("log", "--format=%H"),
                self.git("status", "--porcelain"),
            )

    def verb(self, *args):
        """Run an editing verb against this canvas. Returns (code, out, err)."""
        return self.run_canvas(args[0], "a-ledger-row", *args[1:])

    def inserted(self, *args):
        """Run an insert that is expected to work, and return the minted id."""
        code, stdout, stderr = self.verb("insert", *args)
        self.assertEqual(0, code, stderr)
        return stdout.decode("utf-8").splitlines()[0].split(": ", 1)[1]


class TheFourVerbsApplyToARealCanvas(VerbTestCase):
    """The done condition's first clause: each verb applies to a canvas built
    by `create`, and what it leaves behind is a valid canvas."""

    def test_insert_adds_a_node_after_the_named_sibling(self):
        node_id = self.inserted(
            "--after", self.problem_id, "--text", "A note.", "--why", "the note"
        )
        self.assertEqual(
            [self.problem_id, node_id, self.value_id],
            [child.get("id") for child in self.tree()],
        )
        self.assertEqual("A note.", self.node(node_id).text)
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_insert_into_root_appends_to_the_document(self):
        node_id = self.inserted("--into", "root", "--text", "Last.", "--why", "the end")
        self.assertEqual(
            [self.problem_id, self.value_id, node_id],
            [child.get("id") for child in self.tree()],
        )

    def test_insert_into_an_empty_container_names_its_first_position(self):
        # node-identity.md section 6: the gap --after cannot name.
        list_id = self.inserted("--into", "root", "--type", "list", "--why", "a list")
        self.assertEqual([], list(self.node(list_id)))
        item_id = self.inserted(
            "--into", list_id, "--type", "item", "--text", "a bullet", "--why", "one"
        )
        self.assertEqual([item_id], [child.get("id") for child in self.node(list_id)])
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_insert_can_add_every_node_type_the_vocabulary_has(self):
        made = {
            "text": self.inserted("--into", "root", "--type", "text",
                                  "--text", "prose", "--why", "prose"),
            "question": self.inserted("--into", "root", "--type", "question",
                                      "--text", "open?", "--why", "a question"),
            "figure": self.inserted("--into", "root", "--type", "figure",
                                    "--text", "a -> b", "--why", "a figure"),
            "link": self.inserted("--into", "root", "--type", "link",
                                  "--href", "https://example.invalid/x",
                                  "--text", "the todo", "--why", "a link"),
            "list": self.inserted("--into", "root", "--type", "list", "--why", "a list"),
            "table": self.inserted("--into", "root", "--type", "table", "--why",
                                   "the options"),
            "section": self.inserted("--into", "root", "--type", "section",
                                     "--title", "A heading", "--why", "a section"),
        }
        for tag, node_id in made.items():
            self.assertEqual(tag, self.node(node_id).tag)
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_replace_changes_the_content_and_keeps_the_id(self):
        code, stdout, stderr = self.verb(
            "replace", self.problem_id, "--text", "The problem, restated.",
            "--why", "the first statement was too narrow",
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("The problem, restated.", self.node(self.problem_id).text)
        self.assertEqual(
            [self.problem_id, self.value_id],
            [child.get("id") for child in self.tree()],
        )
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_remove_takes_the_node_out_of_the_document(self):
        code, _, stderr = self.verb("remove", self.problem_id, "--why", "answered")
        self.assertEqual(0, code, stderr)
        self.assertEqual([self.value_id], [child.get("id") for child in self.tree()])
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_move_changes_the_position_and_nothing_else(self):
        before = self.node(self.value_id)
        code, _, stderr = self.verb(
            "move", self.value_id, "--after", "root", "--why", "wrong order"
        )
        # --after root is the one position the root cannot name.
        self.assertEqual(1, code, stderr)

        code, _, stderr = self.verb(
            "move", self.problem_id, "--after", self.value_id,
            "--why", "the value reads better first",
        )
        self.assertEqual(0, code, stderr)
        after = self.node(self.problem_id)
        self.assertEqual(
            [self.value_id, self.problem_id],
            [child.get("id") for child in self.tree()],
        )
        self.assertEqual("text", after.tag)
        self.assertEqual("The problem stated.", after.text)
        self.assertEqual(before.text, self.node(self.value_id).text)
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_move_reparents_into_a_section_and_back_out(self):
        section_id = self.inserted(
            "--into", "root", "--type", "section", "--title", "A heading",
            "--why", "somewhere to put it",
        )
        code, _, stderr = self.verb(
            "move", self.problem_id, "--into", section_id, "--why", "it belongs here"
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(
            [self.problem_id], [child.get("id") for child in self.node(section_id)]
        )
        code, _, stderr = self.verb(
            "move", self.problem_id, "--into", "root", "--why", "out again"
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual([], list(self.node(section_id)))
        self.assertEqual(
            [self.value_id, section_id, self.problem_id],
            [child.get("id") for child in self.tree()],
        )
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_every_verb_leaves_nothing_uncommitted_behind(self):
        node_id = self.inserted("--into", "root", "--text", "x", "--why", "one")
        self.verb("replace", node_id, "--text", "y", "--why", "two")
        self.verb("move", node_id, "--after", self.problem_id, "--why", "three")
        self.verb("remove", node_id, "--why", "four")
        self.assertEqual("", self.git("status", "--porcelain"))
        leftovers = [
            name for name in os.listdir(self.canvas_dir)
            if name != ".git" and not name.endswith(".xml")
        ]
        self.assertEqual([], leftovers)

    def test_every_verb_prints_the_node_it_changed_and_the_new_sha(self):
        for args in (
            ("insert", "--into", "root", "--text", "x", "--why", "one"),
            ("replace", self.problem_id, "--text", "y", "--why", "two"),
            ("move", self.problem_id, "--into", "root", "--why", "three"),
            ("remove", self.problem_id, "--why", "four"),
        ):
            code, stdout, stderr = self.verb(*args)
            self.assertEqual(0, code, stderr)
            lines = stdout.decode("utf-8").splitlines()
            self.assertTrue(lines[0].startswith("Canvas-Node: "), lines)
            self.assertTrue(NODE_ID.match(lines[0].split(": ", 1)[1]), lines[0])
            self.assertEqual(
                "Canvas-Base: %s" % self.git("rev-parse", "HEAD").strip(), lines[1]
            )


class ReadSurfaceTestCase(VerbTestCase):
    """A canvas with something in it worth selecting: the two first nodes, a
    `<question>` beside them, and a `<section>` with a `<text>` inside it."""

    def setUp(self):
        VerbTestCase.setUp(self)
        self.question_id = self.inserted(
            "--after", self.problem_id,
            "--type", "question",
            "--text", "Does the store re-read before it writes?",
            "--why",
            "the open question this canvas turns on; unlike %s, which states "
            "the problem, this names what is unknown about it, and it is "
            "retired when the write path has been read" % self.problem_id,
        )
        self.section_id = self.inserted(
            "--into", "root",
            "--type", "section",
            "--title", "Findings",
            "--why",
            "a container for what the read path learns, distinct from the "
            "problem node %s which only states the task; unnecessary if no "
            "finding ever accumulates under it" % self.problem_id,
        )
        self.child_id = self.inserted(
            "--into", self.section_id,
            "--text", "The log already carries the author.",
            "--why",
            "the first finding under section %s; unlike the problem node %s "
            "it records what was observed rather than what was asked"
            % (self.section_id, self.problem_id),
        )

    def nodes_in(self, stdout):
        """The ids of the nodes a read printed, in the order it printed them."""
        root = ElementTree.fromstring(self.document(stdout))
        return [
            element.get("id")
            for element in root.iter()
            if element is not root and element.get("id")
        ]


class TheReadSelectorReturnsPartOfACanvas(ReadSurfaceTestCase):
    """The done condition's first clause: `read` can return part of a canvas
    selected by node id and by node type, and still names the sha it read."""

    def test_an_id_returns_that_node_and_nothing_else(self):
        stdout = self.selected("a-ledger-row", "--id", self.value_id)
        self.assertEqual([self.value_id], self.nodes_in(stdout))

    def test_a_type_returns_every_node_of_that_type(self):
        stdout = self.selected("a-ledger-row", "--type", "text")
        # The two first nodes and the one inside the section, in document
        # order, and not the <question> or the <section> itself.
        self.assertEqual(
            [self.problem_id, self.value_id, self.child_id],
            self.nodes_in(stdout),
        )

    def test_a_type_answers_the_question_the_whole_document_used_to(self):
        # The literal done condition of the hand-driven task: are there any
        # question nodes left, without piping the document through grep.
        stdout = self.selected("a-ledger-row", "--type", "question")
        self.assertEqual([self.question_id], self.nodes_in(stdout))

    def test_the_selectors_union_rather_than_intersect(self):
        stdout = self.selected(
            "a-ledger-row", "--id", self.problem_id, "--type", "question"
        )
        self.assertEqual(
            [self.problem_id, self.question_id], self.nodes_in(stdout)
        )

    def test_a_selected_node_brings_its_subtree(self):
        stdout = self.selected("a-ledger-row", "--id", self.section_id)
        self.assertEqual([self.section_id, self.child_id], self.nodes_in(stdout))

    def test_a_node_selected_twice_over_is_printed_once_in_place(self):
        stdout = self.selected(
            "a-ledger-row", "--id", self.section_id, "--id", self.child_id
        )
        self.assertEqual([self.section_id, self.child_id], self.nodes_in(stdout))
        root = ElementTree.fromstring(self.document(stdout))
        self.assertEqual(1, len(list(root)))

    def test_the_selection_keeps_the_roots_own_attributes(self):
        stdout = self.selected("a-ledger-row", "--type", "question")
        root = ElementTree.fromstring(self.document(stdout))
        stored = self.tree()
        self.assertEqual("canvas", root.tag)
        self.assertEqual(stored.attrib, root.attrib)

    def test_a_selected_read_still_names_the_sha_it_read(self):
        head = self.git("rev-parse", "HEAD").strip()
        for flags in (
            ("--id", self.value_id),
            ("--type", "question"),
            ("--type", "text", "--id", self.question_id),
        ):
            stdout = self.selected("a-ledger-row", *flags)
            self.assertEqual(
                ["Canvas-Base: %s" % head], self.header(stdout), flags
            )

    def test_the_sha_is_the_one_an_unselected_read_hands_out(self):
        whole = self.selected("a-ledger-row")
        part = self.selected("a-ledger-row", "--type", "question")
        self.assertEqual(
            self.printed(whole, "Canvas-Base"),
            self.printed(part, "Canvas-Base"),
        )

    def test_an_unselected_read_is_still_the_file_byte_for_byte(self):
        code, stdout, _ = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code)
        with open(self.canvas_file(), "rb") as handle:
            self.assertEqual(handle.read(), b"\n".join(stdout.split(b"\n")[1:]))

    def test_a_type_that_matches_nothing_is_an_empty_canvas_at_exit_zero(self):
        # A type is a predicate and "none" is its answer, not its failure.
        code, stdout, stderr = self.run_canvas(
            "read", "a-ledger-row", "--type", "list"
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        self.assertEqual([], self.nodes_in(stdout))

    def test_a_type_name_the_vocabulary_does_not_have_is_not_refused(self):
        # Refusing it would need a list of legal element names in Python, and
        # the vocabulary is written down once, in schema/canvas.rng.
        code, stdout, stderr = self.run_canvas(
            "read", "a-ledger-row", "--type", "decision"
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual([], self.nodes_in(stdout))

    def test_an_id_that_names_no_node_of_this_canvas_is_refused(self):
        # An id is an assertion that a node exists, so a name that matches
        # nothing is a wrong request: history's rule for the same mistake.
        code, stdout, stderr = self.run_canvas(
            "read", "a-ledger-row", "--id", "zzzz"
        )
        self.assertEqual(1, code, stderr)
        self.assertEqual(b"", stdout)
        self.assertIn("Canvas-Node: zzzz", stderr)
        self.assertIn("Canvas-Next: ", stderr)

    def test_one_missing_id_refuses_the_whole_selection(self):
        code, stdout, stderr = self.run_canvas(
            "read", "a-ledger-row", "--id", self.value_id, "--id", "zzzz"
        )
        self.assertEqual(1, code, stderr)
        self.assertEqual(b"", stdout)
        self.assertIn("Canvas-Node: zzzz", stderr)

    def test_the_root_is_not_a_node_and_cannot_be_selected(self):
        code, _, stderr = self.run_canvas("read", "a-ledger-row", "--id", "root")
        self.assertEqual(1, code, stderr)

    def test_a_selected_read_changes_nothing_at_all(self):
        before = self.state()
        listing = sorted(os.listdir(self.canvas_dir))
        for flags in (
            ("--id", self.value_id),
            ("--type", "question"),
            ("--type", "list"),
            ("--id", "zzzz"),
        ):
            self.run_canvas("read", "a-ledger-row", *flags)
            self.assertEqual(before, self.state(), flags)
            self.assertEqual(listing, sorted(os.listdir(self.canvas_dir)), flags)

    def test_no_editing_verb_takes_a_selector(self):
        # The read selector is not addressing: no write takes one, so IWE's
        # --expect match-count guard is still unnecessary here.
        for verb in ("replace", "insert", "remove", "move"):
            code, _, stderr = self.verb(verb, "--type", "text", "--why", "w")
            self.assertEqual(2, code, stderr)
            code, _, stderr = self.verb(verb, "--id", self.value_id, "--why", "w")
            self.assertEqual(2, code, stderr)


class TheReadSurfaceSaysWhoWroteEachNode(ReadSurfaceTestCase):
    """The done condition's second clause: the read surface says who last wrote
    each node and at which commit — derived from the log, held nowhere in the
    document."""

    def wrote(self, stdout):
        """The Canvas-Wrote: lines, as {node id: (sha, author)}."""
        found = {}
        for value in self.printed(stdout, "Canvas-Wrote"):
            node_id, sha, author = value.split(" ", 2)
            found[node_id] = (sha, author)
        return found

    def test_every_node_printed_gets_exactly_one_line(self):
        stdout = self.selected("a-ledger-row", "--provenance")
        printed = self.printed(stdout, "Canvas-Wrote")
        self.assertEqual(len(self.nodes_in(stdout)), len(printed))
        self.assertEqual(
            self.nodes_in(stdout),
            [value.split(" ", 1)[0] for value in printed],
        )

    def test_it_names_the_commit_that_wrote_the_node(self):
        stdout = self.selected("a-ledger-row", "--provenance")
        for node_id, (sha, _) in self.wrote(stdout).items():
            self.assertTrue(SHA.match(sha), (node_id, sha))
            # The last commit whose Canvas-Node: trailer names that node.
            self.assertEqual(self.history(node_id)[0], sha, node_id)

    def test_it_names_the_author_the_commit_carries(self):
        stdout = self.selected("a-ledger-row", "--provenance")
        for node_id, (sha, author) in self.wrote(stdout).items():
            # The author is the trailer's value verbatim, spaces and pipes and
            # all, which is why it is last on the line and free text.
            self.assertIn(
                "Canvas-Author: %s" % author,
                self.git("show", "--format=%B", "--no-patch", sha),
                node_id,
            )

    def test_it_follows_the_last_writer_and_not_the_first(self):
        first = self.wrote(self.selected("a-ledger-row", "--provenance"))
        code, _, stderr = self.verb(
            "replace", self.child_id,
            "--text", "The log already carries the author, and the sha.",
            "--why",
            "sharpening finding %s: unlike its container %s it now names both "
            "facts the read surface hands back" % (self.child_id, self.section_id),
            "--author", "someone-else | by-hand",
        )
        self.assertEqual(0, code, stderr)
        after = self.wrote(self.selected("a-ledger-row", "--provenance"))
        self.assertNotEqual(first[self.child_id], after[self.child_id])
        self.assertEqual("someone-else | by-hand", after[self.child_id][1])
        # Every other node is where it was: one node moved, one line changed.
        for node_id in first:
            if node_id != self.child_id:
                self.assertEqual(first[node_id], after[node_id], node_id)

    def test_a_move_counts_as_having_written_the_node(self):
        # A move is a commit that names the node and it bumps v, and v is
        # exactly the count of those commits. Any other rule would make this
        # disagree with the number in the file.
        before = self.wrote(self.selected("a-ledger-row", "--provenance"))
        code, _, stderr = self.verb(
            "move", self.question_id, "--into", self.section_id,
            "--why",
            "the question %s belongs under the findings section %s now that "
            "the findings are what would answer it" % (self.question_id, self.section_id),
        )
        self.assertEqual(0, code, stderr)
        after = self.wrote(self.selected("a-ledger-row", "--provenance"))
        self.assertNotEqual(
            before[self.question_id][0], after[self.question_id][0]
        )
        self.assertEqual(
            len(self.history(self.question_id)),
            int(self.node(self.question_id).get("v")),
        )

    def test_it_composes_with_a_selector(self):
        stdout = self.selected(
            "a-ledger-row", "--type", "question", "--provenance"
        )
        self.assertEqual([self.question_id], list(self.wrote(stdout)))
        self.assertEqual([self.question_id], self.nodes_in(stdout))

    def test_a_node_no_commit_names_is_said_to_be_unrecorded(self):
        # Only reachable by hand-editing the file, which the store treats as
        # out of band. The line is printed all the same, so a caller can count
        # lines against nodes.
        with open(self.canvas_file(), "r", encoding="utf-8") as handle:
            stored = handle.read()
        with open(self.canvas_file(), "w", encoding="utf-8") as handle:
            handle.write(
                stored.replace(
                    "</canvas>", '  <text id="aaaa" v="1">By hand.</text>\n</canvas>'
                )
            )
        stdout = self.selected("a-ledger-row", "--provenance")
        self.assertEqual(("unrecorded", "unrecorded"), self.wrote(stdout)["aaaa"])
        self.assertEqual(len(self.nodes_in(stdout)), len(self.wrote(stdout)))

    def test_none_of_it_reaches_the_stored_document(self):
        # The vocabulary is closed: provenance is a property of the read
        # surface and of nothing else.
        self.selected("a-ledger-row", "--provenance")
        names = set()
        for element in self.tree().iter():
            names.update(element.attrib)
        self.assertTrue(
            names <= {"ledger", "schema", "id", "v", "title", "href", "answered"},
            names,
        )

    def test_the_default_read_prints_no_such_line(self):
        stdout = self.selected("a-ledger-row")
        self.assertEqual([], self.printed(stdout, "Canvas-Wrote"))

    def test_asking_who_wrote_it_writes_nothing(self):
        before = self.state()
        self.selected("a-ledger-row", "--provenance")
        self.selected("a-ledger-row", "--type", "question", "--provenance")
        self.assertEqual(before, self.state())


class WhatChangedSinceAShaWithoutApplyingAnything(ReadSurfaceTestCase):
    """The done condition's third clause: one command reports what changed
    since a given sha without applying anything."""

    def moved_since(self, base, *flags):
        stdout = self.selected("a-ledger-row", "--since", base, *flags)
        news = self.printed(stdout, "Canvas-News")
        self.assertEqual(1, len(news), news)
        return stdout, news[0]

    def test_it_reports_the_commits_and_the_diff_since_that_sha(self):
        base = self.git("rev-parse", "HEAD").strip()
        code, _, stderr = self.verb(
            "replace", self.child_id,
            "--text", "The log carries the author and the sha.",
            "--why",
            "sharpening finding %s: unlike its container %s it names what the "
            "read surface hands back" % (self.child_id, self.section_id),
        )
        self.assertEqual(0, code, stderr)
        stdout, news = self.moved_since(base)
        head = self.git("rev-parse", "HEAD").strip()
        self.assertEqual("1 commit(s) between %s and %s" % (base, head), news)
        header = "\n".join(self.header(stdout))
        self.assertIn("replace %s:" % self.child_id, header)
        self.assertIn("diff --git", header)
        self.assertIn("+", header)

    def test_it_reports_zero_when_nothing_moved(self):
        head = self.git("rev-parse", "HEAD").strip()
        stdout, news = self.moved_since(head)
        self.assertEqual("0 commit(s) between %s and %s" % (head, head), news)
        self.assertEqual(
            ["Canvas-Base: %s" % head, "Canvas-News: %s" % news],
            self.header(stdout),
        )

    def test_it_is_scoped_to_this_canvas(self):
        base = self.git("rev-parse", "HEAD").strip()
        self.create(ledger_id="another-row")
        head = self.git("rev-parse", "HEAD").strip()
        self.assertNotEqual(base, head)
        _, news = self.moved_since(base)
        self.assertEqual("0 commit(s) between %s and %s" % (base, head), news)

    def test_it_still_prints_the_document_and_the_sha(self):
        head = self.git("rev-parse", "HEAD").strip()
        stdout = self.selected("a-ledger-row", "--since", head)
        self.assertEqual(["Canvas-Base: %s" % head], self.header(stdout)[:1])
        with open(self.canvas_file(), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), self.document(stdout))

    def test_it_composes_with_a_selector_and_with_provenance(self):
        head = self.git("rev-parse", "HEAD").strip()
        stdout = self.selected(
            "a-ledger-row", "--type", "question", "--provenance",
            "--since", head,
        )
        # The order the header is composed in: the sha, then who wrote what,
        # then the news, then the document.
        names = [line.split(": ", 1)[0] for line in self.header(stdout)]
        self.assertEqual(["Canvas-Base", "Canvas-Wrote", "Canvas-News"], names)
        self.assertEqual([self.question_id], self.nodes_in(stdout))

    def test_an_abbreviation_git_can_resolve_is_accepted(self):
        base = self.git("rev-parse", "HEAD").strip()
        _, news = self.moved_since(base[:7])
        # Resolved to the full sha, exactly as --base is.
        self.assertIn(base, news)

    def test_a_sha_this_repository_never_handed_out_is_refused(self):
        code, stdout, stderr = self.run_canvas(
            "read", "a-ledger-row",
            "--since", "0123456789abcdef0123456789abcdef01234567",
        )
        self.assertEqual(1, code, stderr)
        self.assertEqual(b"", stdout)
        self.assertIn("--since", stderr)
        self.assertIn("Canvas-Next: ", stderr)

    def test_something_that_is_not_a_sha_at_all_is_the_invocation_being_wrong(self):
        code, stdout, stderr = self.run_canvas(
            "read", "a-ledger-row", "--since", "the-caching-section"
        )
        self.assertEqual(2, code, stderr)
        self.assertEqual(b"", stdout)
        self.assertIn("--since", stderr)

    def test_it_never_advises_dropping_a_flag_a_read_asked_on_purpose(self):
        # `--base`'s refusal offers "drop it to ask for no staleness check at
        # all", which is wrong advice for a question somebody asked.
        _, _, stderr = self.run_canvas(
            "read", "a-ledger-row", "--since", "the-caching-section"
        )
        self.assertNotIn("no staleness check", stderr)

    def test_asking_writes_nothing_commits_nothing_and_initialises_nothing(self):
        base = self.git("rev-parse", "HEAD").strip()
        before = self.state()
        listing = sorted(os.listdir(self.canvas_dir))
        for flags in (
            ("--since", base),
            ("--since", base[:7], "--provenance"),
            ("--since", "0123456789abcdef0123456789abcdef01234567"),
            ("--since", "not-a-sha"),
        ):
            self.run_canvas("read", "a-ledger-row", *flags)
            self.assertEqual(before, self.state(), flags)
            self.assertEqual(listing, sorted(os.listdir(self.canvas_dir)), flags)

    def test_it_cannot_be_spelled_without_a_base(self):
        # No default and no "all" form: the tool never offers whole-canvas
        # history as *the* question.
        code, _, stderr = self.run_canvas("read", "a-ledger-row", "--since")
        self.assertEqual(2, code, stderr)

    def test_no_read_flag_asks_for_a_whole_canvas_history(self):
        code, stdout, _ = self.run_canvas("read", "--help")
        self.assertEqual(0, code)
        printed = stdout.decode("utf-8")
        for absent in ("--history", "--log", "--all", "--everything"):
            self.assertNotIn(absent, printed)


class TheSubcommandsAreStillNine(StoreTestCase):
    """None of the read path's new answers is a new verb."""

    def test_the_tool_offers_exactly_the_nine_it_documented(self):
        code, stdout, _ = self.run_canvas("--help")
        self.assertEqual(0, code)
        printed = stdout.decode("utf-8")
        for verb in (
            "create", "read", "render", "history",
            "replace", "insert", "remove", "move", "freeze",
        ):
            self.assertIn(verb, printed)
        for absent in ("select", "provenance", "since", "changed", "diff", "log"):
            code, _, stderr = self.run_canvas(absent, "a-ledger-row")
            self.assertEqual(2, code, stderr)


class CreatePrintsTheIdsItMinted(StoreTestCase):
    """The done condition's fourth clause: `create` prints the ids it minted,
    so a caller's first command after it is no longer a `read`."""

    def minted(self, stdout):
        return dict(
            line.split(": ", 1) for line in stdout.decode("utf-8").splitlines()
        )

    def test_it_prints_one_id_for_each_of_its_two_arguments(self):
        _, stdout, _ = self.create()
        printed = self.minted(stdout)
        self.assertTrue(NODE_ID.match(printed["Canvas-Problem"]), printed)
        self.assertTrue(NODE_ID.match(printed["Canvas-Expected-Value"]), printed)
        self.assertNotEqual(
            printed["Canvas-Problem"], printed["Canvas-Expected-Value"]
        )

    def test_the_ids_it_prints_are_the_nodes_it_made(self):
        _, stdout, _ = self.create(problem="The problem.", value="The value.")
        printed = self.minted(stdout)
        root = ElementTree.parse(self.canvas_file()).getroot()
        found = {node.get("id"): node.text for node in root}
        self.assertEqual("The problem.", found[printed["Canvas-Problem"]])
        self.assertEqual("The value.", found[printed["Canvas-Expected-Value"]])

    def test_each_id_is_the_one_its_own_insert_commit_names(self):
        _, stdout, _ = self.create()
        printed = self.minted(stdout)
        for name, subject in (
            ("Canvas-Problem", "the problem the ledger row states"),
            ("Canvas-Expected-Value", "the expected value the ledger row states"),
        ):
            commits = self.git(
                "log", "--grep=Canvas-Node: %s" % printed[name], "--format=%s"
            ).splitlines()
            self.assertEqual(
                ["insert %s: %s" % (printed[name], subject)], commits
            )

    def test_the_caller_never_has_to_count_to_tell_them_apart(self):
        # The finding is not only that the ids were unprinted; it is that order
        # was the only thing telling them apart.
        _, stdout, _ = self.create()
        printed = self.minted(stdout)
        self.assertIn("Canvas-Problem", printed)
        self.assertIn("Canvas-Expected-Value", printed)
        self.assertEqual([], [
            line for line in stdout.decode("utf-8").splitlines()
            if line.startswith("Canvas-Node: ")
        ])

    def test_the_two_lines_it_already_printed_are_unchanged(self):
        _, stdout, _ = self.create()
        printed = self.minted(stdout)
        self.assertTrue(SHA.match(printed["Canvas-Base"]), printed)
        self.assertEqual(self.canvas_file(), printed["Canvas-File"])
        lines = stdout.decode("utf-8").splitlines()
        self.assertLess(
            lines.index("Canvas-Base: %s" % printed["Canvas-Base"]),
            lines.index("Canvas-File: %s" % printed["Canvas-File"]),
        )

    def test_a_first_command_after_create_is_no_longer_a_read(self):
        # What the round trip was for: the id is usable straight away.
        _, stdout, _ = self.create()
        printed = self.minted(stdout)
        code, out, stderr = self.run_canvas(
            "replace", "a-ledger-row", printed["Canvas-Problem"],
            "--text", "The problem, restated.",
            "--why",
            "restating the problem node %s from the ledger row's own words; "
            "unlike the expected value %s it says what is wrong rather than "
            "what good looks like"
            % (printed["Canvas-Problem"], printed["Canvas-Expected-Value"]),
            "--base", printed["Canvas-Base"],
        )
        self.assertEqual(0, code, stderr)
        self.assertIn(
            "Canvas-Node: %s" % printed["Canvas-Problem"], out.decode("utf-8")
        )

    def test_create_still_mints_exactly_two_ids_in_three_commits(self):
        self.create()
        self.assertEqual(3, len(self.subjects()))


class ReplaceCanProduceADifferentNodeType(VerbTestCase):
    """The spec's worked example, and the most consequential edit the tool
    supports: an options <table> settling into a <text>, under the same id."""

    def test_a_table_becomes_a_text_and_keeps_its_id(self):
        table_id = self.inserted(
            "--into", "root", "--type", "table", "--why", "the options to compare"
        )
        self.assertEqual("table", self.node(table_id).tag)

        code, _, stderr = self.verb(
            "replace", table_id, "--type", "text",
            "--text", "Chose A.",
            "--why", "chose A over B: B needs a migration we are not paying for",
        )
        self.assertEqual(0, code, stderr)

        settled = self.node(table_id)
        self.assertEqual("text", settled.tag)
        self.assertEqual(table_id, settled.get("id"))
        self.assertEqual("Chose A.", settled.text)
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_the_settled_decision_still_reaches_the_argument_that_produced_it(self):
        # The whole reason the id survives a type change: one grep, both halves.
        table_id = self.inserted(
            "--into", "root", "--type", "table", "--why", "the options to compare"
        )
        self.verb(
            "replace", table_id, "--type", "text", "--text", "Chose A.",
            "--why", "chose A over B",
        )
        subjects = self.git(
            "log", "--reverse", "--grep=Canvas-Node: %s" % table_id, "--format=%s"
        ).splitlines()
        self.assertEqual(
            ["insert %s: the options to compare" % table_id,
             "replace %s: chose A over B" % table_id],
            subjects,
        )

    def test_a_type_change_with_no_children_is_allowed_for_a_container(self):
        list_id = self.inserted("--into", "root", "--type", "list", "--why", "a list")
        code, _, stderr = self.verb(
            "replace", list_id, "--type", "question", "--text", "Still open?",
            "--why", "it was a question all along",
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("question", self.node(list_id).tag)

    def test_replacing_a_section_renames_it_and_leaves_its_children_alone(self):
        # node-identity.md section 5: children keep their ids, v, content, order.
        section_id = self.inserted(
            "--into", "root", "--type", "section", "--title", "Old heading",
            "--why", "a section",
        )
        first = self.inserted("--into", section_id, "--text", "one", "--why", "a")
        second = self.inserted("--into", section_id, "--text", "two", "--why", "b")

        code, _, stderr = self.verb(
            "replace", section_id, "--title", "New heading", "--why", "clearer name"
        )
        self.assertEqual(0, code, stderr)

        section = self.node(section_id)
        self.assertEqual("New heading", section.get("title"))
        self.assertEqual([first, second], [child.get("id") for child in section])
        self.assertEqual(["one", "two"], [child.text for child in section])
        self.assertEqual(["1", "1"], [child.get("v") for child in section])


class MarkingAQuestionAnswered(VerbTestCase):
    """node-state.md: the one state a canvas carries reaches the command line
    as `--answered`, and the attribute is restated rather than sticky."""

    def test_a_question_can_be_born_answered_and_the_canvas_stays_valid(self):
        node_id = self.inserted(
            "--into", "root", "--type", "question", "--text", "Settled?",
            "--answered", "--why", "the question and its answer arrive together",
        )
        self.assertEqual("true", self.node(node_id).get("answered"))
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_a_question_inserted_without_the_flag_is_open(self):
        # Absence means open. There is no answered="false" to write.
        node_id = self.inserted(
            "--into", "root", "--type", "question", "--text", "Open?",
            "--why", "a question nobody has answered yet",
        )
        self.assertIsNone(self.node(node_id).get("answered"))
        self.assertNotIn("answered", self.node(node_id).attrib)

    def test_marking_a_question_answered_is_a_replace_that_bumps_v(self):
        # It is a commit naming the node, and `v` is what the log counts
        # (node-identity.md section 4). Not a bug; the ruling names it.
        node_id = self.inserted(
            "--into", "root", "--type", "question", "--text", "Answered yet?",
            "--why", "the question this canvas turns on",
        )
        self.assertEqual("1", self.node(node_id).get("v"))
        code, _, stderr = self.verb(
            "replace", node_id, "--type", "question", "--text", "Answered yet?",
            "--answered", "--why", "settled by the ruling in node-state.md",
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("true", self.node(node_id).get("answered"))
        self.assertEqual("2", self.node(node_id).get("v"))
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_the_attribute_is_restated_and_not_sticky(self):
        # A replace that omits --answered clears it, exactly as one that omits
        # --title clears a title. That is how a question is reopened, and it
        # needs no fifth verb.
        node_id = self.inserted(
            "--into", "root", "--type", "question", "--text", "Settled?",
            "--answered", "--why", "answered on arrival",
        )
        code, _, stderr = self.verb(
            "replace", node_id, "--type", "question", "--text", "Settled?",
            "--why", "reopened: the answer did not survive contact",
        )
        self.assertEqual(0, code, stderr)
        self.assertIsNone(self.node(node_id).get("answered"))
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_answered_on_a_node_that_is_not_a_question_never_reaches_the_canvas(self):
        # The vocabulary is written down once: the CLI does not police this,
        # the validator does, and the write is refused before it lands.
        before = self.state()
        code, _, stderr = self.verb(
            "insert", "--into", "root", "--type", "text", "--text", "prose",
            "--answered", "--why", "state on a node that may not carry it",
        )
        self.assertNotEqual(0, code)
        self.assertIn("<text>", stderr)
        self.assertEqual(before, self.state())


class EveryVerbRequiresAReason(VerbTestCase):
    """The done condition's second and third clauses: every verb is refused
    with a non-zero exit when `--why` is absent or empty, and there is no code
    path that writes to a canvas without one."""

    def edits(self):
        """One invocation of each verb, minus its --why."""
        return (
            ("insert", "--into", "root", "--text", "A node."),
            ("replace", self.problem_id, "--text", "Restated."),
            ("remove", self.problem_id),
            ("move", self.problem_id, "--after", self.value_id),
        )

    def test_a_missing_why_is_refused_with_a_non_zero_exit(self):
        for edit in self.edits():
            before = self.state()
            code, stdout, stderr = self.verb(*edit)
            self.assertNotEqual(0, code, edit)
            self.assertEqual(b"", stdout, edit)
            self.assertIn("why", stderr, edit)
            self.assertEqual(before, self.state(), edit)

    def test_an_empty_why_is_refused_with_a_non_zero_exit(self):
        for edit in self.edits():
            before = self.state()
            code, stdout, stderr = self.verb(*(edit + ("--why", "")))
            self.assertNotEqual(0, code, edit)
            self.assertEqual(b"", stdout, edit)
            self.assertIn("--why", stderr, edit)
            self.assertEqual(before, self.state(), edit)

    def test_a_whitespace_only_why_is_refused_too(self):
        for reason in (" ", "\t", "\n", "   \t  "):
            for edit in self.edits():
                before = self.state()
                code, _, _ = self.verb(*(edit + ("--why", reason)))
                self.assertNotEqual(0, code, (edit, reason))
                self.assertEqual(before, self.state(), (edit, reason))

    def test_a_refused_edit_mints_no_id(self):
        before = self.git("log", "--format=%H").split()
        self.verb("insert", "--into", "root", "--text", "x", "--why", "")
        self.assertEqual(before, self.git("log", "--format=%H").split())

    def test_the_write_path_itself_refuses_a_reasonless_write(self):
        # The done condition is about code paths, not about the CLI surface: a
        # caller that never goes near canvas/cli.py must not be able to write
        # an unexplained edit either. _write_and_commit is the only function
        # that puts a canvas on its real path, and it will not.
        from canvas import store

        for reason in (None, "", "   ", "\n"):
            with self.assertRaises(store.ToolProblem):
                store.require_reason(reason)

        with self.assertRaises(store.ToolProblem):
            store._write_and_commit(
                self.canvas_dir,
                self.canvas_file(),
                document.new_canvas("a-ledger-row"),
                "replace",
                "q4rt",
                "  ",
                "a | by-hand",
            )
        # And it wrote nothing on the way to refusing.
        self.assertEqual(
            ["The problem stated.", "The value expected."],
            [child.text for child in self.tree()],
        )

    def test_the_reason_a_verb_was_given_is_the_commit_subject(self):
        why = "chose A over B: B needs a migration we are not paying for"
        node_id = self.inserted("--into", "root", "--text", "Chose A.", "--why", why)
        self.assertEqual("insert %s: %s" % (node_id, why), self.subjects()[-1])

    def test_the_reason_is_recorded_only_in_the_history_never_in_the_xml(self):
        why = "a reason that must not become an attribute"
        node_id = self.inserted("--into", "root", "--text", "x", "--why", why)
        with open(self.canvas_file(), encoding="utf-8") as handle:
            self.assertNotIn(why, handle.read())
        self.assertIn(why, self.git("log", "-1", "--format=%s"))
        self.assertIsNone(self.node(node_id).get("why"))


class AReasonMayNotPointAtAnotherReason(VerbTestCase):
    """`VERDICT.md` §5.2's guard: a reason that says where the node sits
    instead of what it is for is refused at exit 2 with nothing written, the
    same shape as the empty-reason refusal above.

    The texts are the corpus's own (`docs/why-verdict/corpus-reasons.md`), so
    what these tests measure is the thing the verdict measured."""

    #: The verdict's message, verbatim (`VERDICT.md` §5.2).
    MESSAGE = (
        "--why must say what this node is for, not where it sits; if the "
        "reason is another node's, name that node's id and say what differs "
        "here."
    )

    #: Corpus entries 23, 24 and 22 — the three of the six failing reasons
    #: §5.2 names as caught.
    CAUGHT = (
        "column one, as above.",
        "column two, as above.",
        "the header row, matching question 1's two columns. Same shape, "
        "same reading.",
    )

    def edits(self):
        """One invocation of each verb, minus its --why."""
        return (
            ("insert", "--into", "root", "--text", "A node."),
            ("replace", self.problem_id, "--text", "Restated."),
            ("remove", self.problem_id),
            ("move", self.problem_id, "--after", self.value_id),
        )

    def test_a_bare_back_reference_is_refused_at_exit_2_with_nothing_written(self):
        for reason in self.CAUGHT:
            for edit in self.edits():
                before = self.state()
                code, stdout, stderr = self.verb(*(edit + ("--why", reason)))
                self.assertEqual(2, code, (edit, reason))
                self.assertEqual(b"", stdout, (edit, reason))
                self.assertIn(self.MESSAGE, stderr, (edit, reason))
                self.assertEqual(before, self.state(), (edit, reason))

    def test_the_refusal_says_what_to_do_instead(self):
        _, _, stderr = self.verb(
            "replace", self.problem_id, "--text", "x", "--why", "column one, as above."
        )
        self.assertIn("Canvas-Next: ", stderr)
        self.assertIn("name its four-character id", stderr)
        self.assertIn("Canvas-Exit: 2", stderr)

    def test_naming_another_nodes_id_is_the_exemption_and_is_accepted(self):
        # The rule is "no four-character node id other than the edit's own
        # target": a writer who means "as above" and names the node they mean
        # has done what the rule asks, so the reason goes through.
        reason = (
            "as above for %s, except that this one carries the price and %s "
            "carries the decision" % (self.value_id, self.value_id)
        )
        code, _, stderr = self.verb(
            "replace", self.problem_id, "--text", "Restated.", "--why", reason
        )
        self.assertEqual(0, code, stderr)

    def test_the_edits_own_target_id_does_not_exempt_it(self):
        # Naming the node you are editing is not naming the node you pointed
        # at, so the reason is still bare.
        reason = "same shape as %s, ditto" % self.problem_id
        before = self.state()
        code, stdout, stderr = self.verb(
            "replace", self.problem_id, "--text", "Restated.", "--why", reason
        )
        self.assertEqual(2, code)
        self.assertEqual(b"", stdout)
        self.assertIn(self.MESSAGE, stderr)
        self.assertEqual(before, self.state())

    def test_entry_21_is_refused_as_the_accepted_false_positive(self):
        # Corpus entry 21 (`ehxj`), which the verdict judged *informative* and
        # which this guard refuses anyway: its closing clause is "Empty for one
        # commit, as before." and it names no other node's id. §5.2 prices this
        # at one wrongly refused out of the forty-one that met the bar and
        # accepts it — a writer who means "as before" and has a node id to name
        # is told to name it. This test asserts the false positive on purpose.
        # It is not a bug report; fixing it means deleting the guard.
        reason = (
            "the options for question 2 and what each costs, in the same shape "
            "as question 1's so the two can be read the same way. Empty for one "
            "commit, as before."
        )
        before = self.state()
        code, stdout, stderr = self.verb(
            "insert", "--into", "root", "--text", "", "--why", reason
        )
        self.assertEqual(2, code)
        self.assertEqual(b"", stdout)
        self.assertIn(self.MESSAGE, stderr)
        self.assertEqual(before, self.state())

    def test_the_write_path_itself_refuses_a_bare_back_reference(self):
        # Same as the empty-reason case: a caller that never goes near
        # canvas/cli.py must not be able to write one either.
        from canvas import store

        for reason in self.CAUGHT:
            with self.assertRaises(store.ToolProblem):
                store.require_reason(reason, nodes=["q4rt"])

    def test_a_reason_that_says_something_is_not_caught(self):
        # What the guard does not catch, and is not meant to: §5.2 is a speed
        # bump against one failing shape, not a tautology detector.
        for reason in (
            "a table of the two options, so the comparison has somewhere to go",
            "the cost column: the decision turns on price and nothing in the "
            "canvas holds it yet",
        ):
            code, _, stderr = self.verb(
                "insert", "--into", "root", "--text", "A node.", "--why", reason
            )
            self.assertEqual(0, code, (reason, stderr))


class TheVerbsAddressNodesByIdAndNothingElse(VerbTestCase):
    """Addressing is by explicit node id. An id that is not in the canvas is a
    refusal, not a silent no-op."""

    def test_an_absent_node_id_is_refused_by_every_verb(self):
        for edit in (
            ("replace", "zzzz", "--text", "x"),
            ("remove", "zzzz"),
            ("move", "zzzz", "--after", self.problem_id),
            ("move", self.problem_id, "--after", "zzzz"),
            ("move", self.problem_id, "--into", "zzzz"),
            ("insert", "--after", "zzzz", "--text", "x"),
            ("insert", "--into", "zzzz", "--text", "x"),
        ):
            before = self.state()
            code, stdout, stderr = self.verb(*(edit + ("--why", "a reason")))
            self.assertEqual(1, code, edit)
            self.assertEqual(b"", stdout, edit)
            self.assertIn("zzzz", stderr, edit)
            self.assertEqual(before, self.state(), edit)

    def test_the_root_is_not_a_node_any_verb_can_edit(self):
        for edit in (
            ("replace", "root", "--text", "x"),
            ("remove", "root"),
            ("move", "root", "--after", self.problem_id),
        ):
            before = self.state()
            code, _, stderr = self.verb(*(edit + ("--why", "a reason")))
            self.assertEqual(1, code, edit)
            self.assertIn("root", stderr, edit)
            self.assertEqual(before, self.state(), edit)

    def test_no_verb_offers_a_selector(self):
        for flag in ("--matching", "--select", "--xpath", "--heading"):
            code, _, _ = self.verb(
                "replace", flag, "the caching section", "--why", "x"
            )
            self.assertEqual(2, code, flag)

    def test_every_verb_accepts_base(self):
        # The staleness rule: each verb takes the sha the edit was decided
        # against. Each of these declares the head as it stands when it runs,
        # so nothing moved in between and each of them applies.
        for edit in (
            ("replace", self.problem_id, "--text", "x"),
            ("move", self.problem_id, "--into", "root"),
            ("insert", "--into", "root", "--text", "x"),
            ("remove", self.problem_id),
        ):
            head = self.git("rev-parse", "HEAD").strip()
            before = self.state()
            code, _, stderr = self.verb(
                *(edit + ("--base", head, "--why", "a reason"))
            )
            self.assertEqual(0, code, (edit, stderr))
            self.assertNotEqual(before, self.state(), edit)

    def test_a_position_needs_exactly_one_of_after_and_into(self):
        for edit in (
            ("insert", "--text", "x"),
            ("insert", "--after", self.problem_id, "--into", "root", "--text", "x"),
            ("move", self.problem_id),
            ("move", self.problem_id, "--after", self.problem_id, "--into", "root"),
        ):
            code, _, _ = self.verb(*(edit + ("--why", "a reason")))
            self.assertEqual(2, code, edit)

    def test_an_edit_to_a_ledger_row_with_no_canvas_is_refused(self):
        code, stdout, stderr = self.run_canvas(
            "remove", "no-such-row", self.problem_id, "--why", "a reason"
        )
        self.assertEqual(1, code)
        self.assertEqual(b"", stdout)
        self.assertIn("no-such-row", stderr)

    def test_an_edit_addresses_only_the_canvas_it_was_given(self):
        # Ids are unique across the repository, and an edit still names the
        # canvas it applies to, so a node id from another row is not found here.
        self.create(ledger_id="another-row", problem="Elsewhere.", value="Also.")
        other = [
            child.get("id")
            for child in ElementTree.parse(self.canvas_file("another-row")).getroot()
        ][0]
        code, _, stderr = self.verb("remove", other, "--why", "a reason")
        self.assertEqual(1, code)
        self.assertIn(other, stderr)
        self.assertEqual(
            [other], [child.get("id") for child in
                      ElementTree.parse(self.canvas_file("another-row")).getroot()][:1]
        )


class IdentityHoldsAcrossTheFourVerbs(VerbTestCase):
    """node-identity.md sections 1 to 4, checked over a sequence of edits: v is
    the number of commits naming the node, and nothing else is touched."""

    def test_an_inserted_node_is_born_at_v_one_with_a_minted_id(self):
        node_id = self.inserted("--into", "root", "--text", "x", "--why", "one")
        self.assertTrue(NODE_ID.match(node_id), node_id)
        self.assertEqual("1", self.node(node_id).get("v"))
        self.assertNotIn(node_id, (self.problem_id, self.value_id))

    def test_replace_and_move_bump_v_and_insert_does_not_touch_anybody_elses(self):
        self.verb("replace", self.problem_id, "--text", "Restated.", "--why", "one")
        self.assertEqual("2", self.node(self.problem_id).get("v"))
        self.verb("move", self.problem_id, "--into", "root", "--why", "two")
        self.assertEqual("3", self.node(self.problem_id).get("v"))
        self.assertEqual("1", self.node(self.value_id).get("v"))

    def test_v_always_equals_the_number_of_commits_naming_the_node(self):
        section_id = self.inserted(
            "--into", "root", "--type", "section", "--title", "A heading",
            "--why", "a section",
        )
        leaf = self.inserted("--into", section_id, "--text", "one", "--why", "a leaf")
        self.verb("replace", leaf, "--text", "two", "--why", "reworded")
        self.verb("move", leaf, "--into", "root", "--why", "it did not belong")
        self.verb("replace", section_id, "--title", "Renamed", "--why", "clearer")

        for node in self.tree().iter():
            if node.get("id") is None:
                continue
            self.assertEqual(
                str(len(self.history(node.get("id")))),
                node.get("v"),
                node.get("id"),
            )
        # And specifically: the container's v counted its own commits only, not
        # the commits that named its children.
        self.assertEqual("2", self.node(section_id).get("v"))
        # Inserted, replaced, moved: three commits name it, so v is three.
        self.assertEqual("3", self.node(leaf).get("v"))

    def test_a_removed_id_is_retired_and_never_reminted(self):
        node_id = self.inserted("--into", "root", "--text", "x", "--why", "one")
        self.verb("remove", node_id, "--why", "it was wrong")
        self.assertIsNone(self.node(node_id))
        # Its history is still there, ending with the commit that removed it,
        # which is what makes `is_free` say no for ever.
        self.assertEqual(2, len(self.history(node_id)))
        self.assertEqual(
            "remove %s: it was wrong" % node_id,
            self.git("log", "-1", "--grep=Canvas-Node: %s" % node_id, "--format=%s"
                     ).strip(),
        )
        from canvas import store
        self.assertFalse(store.is_free(self.canvas_dir, node_id))

    def test_every_edit_is_exactly_one_commit_naming_exactly_one_node(self):
        before = len(self.subjects())
        node_id = self.inserted("--into", "root", "--text", "x", "--why", "one")
        self.verb("replace", node_id, "--text", "y", "--why", "two")
        self.verb("move", node_id, "--after", self.problem_id, "--why", "three")
        self.verb("remove", node_id, "--why", "four")
        self.assertEqual(before + 4, len(self.subjects()))
        for body in self.bodies()[before:]:
            self.assertEqual(1, body.count("Canvas-Node:"), body)
            self.assertIn("Canvas-Author:", body)
            self.assertIn("Canvas-Base:", body)

    def test_an_edit_bases_on_the_head_it_was_applied_to(self):
        head = self.git("rev-parse", "HEAD").strip()
        self.inserted("--into", "root", "--text", "x", "--why", "one")
        self.assertIn("Canvas-Base: %s" % head, self.bodies()[-1])

    def test_an_explicit_author_is_used_verbatim_by_every_verb(self):
        author = "leo | step:implement | run:ship-the-flag-3"
        node_id = self.inserted(
            "--into", "root", "--text", "x", "--why", "one", "--author", author
        )
        for args in (
            ("replace", node_id, "--text", "y", "--why", "two"),
            ("move", node_id, "--after", self.problem_id, "--why", "three"),
            ("remove", node_id, "--why", "four"),
        ):
            code, _, stderr = self.verb(*(args + ("--author", author)))
            self.assertEqual(0, code, stderr)
        for body in self.bodies()[3:]:
            self.assertIn("Canvas-Author: %s" % author, body)


class OneEditIsStillOneNode(VerbTestCase):
    """node-identity.md section 5 decided these two refusals in writing before
    any verb existed. A verb that shipped without them could delete N nodes in
    one commit from the day it landed."""

    def section_with_children(self):
        section_id = self.inserted(
            "--into", "root", "--type", "section", "--title", "A heading",
            "--why", "a section",
        )
        first = self.inserted("--into", section_id, "--text", "one", "--why", "a")
        second = self.inserted("--into", section_id, "--text", "two", "--why", "b")
        return section_id, first, second

    def test_removing_a_node_that_still_has_children_is_refused(self):
        section_id, first, second = self.section_with_children()
        before = self.state()
        code, stdout, stderr = self.verb("remove", section_id, "--why", "tidying up")
        self.assertEqual(1, code)
        self.assertEqual(b"", stdout)
        # The refusal names the section and every child it would have taken.
        for named in (section_id, first, second):
            self.assertIn(named, stderr)
        self.assertEqual(before, self.state())

    def test_emptying_a_container_leaves_it_written_as_an_empty_one(self):
        # A container's character data in this vocabulary is serialise's own
        # indentation, so removing its last child must not promote that
        # whitespace to content: <table id v/>, not <table id v>\n  </table>.
        table_id = self.inserted(
            "--into", "root", "--type", "table", "--why", "the options"
        )
        row_id = self.inserted(
            "--into", table_id, "--type", "row", "--why", "the first option"
        )
        code, _, stderr = self.verb("remove", row_id, "--why", "no longer a candidate")
        self.assertEqual(0, code, stderr)

        self.assertEqual([], list(self.node(table_id)))
        self.assertIsNone(self.node(table_id).text)
        with open(self.canvas_file(), encoding="utf-8") as handle:
            self.assertIn('<table id="%s" v="1"/>' % table_id, handle.read())
        self.assertEqual([], validate_file(self.canvas_file()))

    def test_an_emptied_node_can_then_be_removed(self):
        section_id, first, second = self.section_with_children()
        for child in (first, second):
            code, _, stderr = self.verb("remove", child, "--why", "no longer needed")
            self.assertEqual(0, code, stderr)
        code, _, stderr = self.verb("remove", section_id, "--why", "empty now")
        self.assertEqual(0, code, stderr)
        self.assertIsNone(self.node(section_id))

    def test_changing_the_type_of_a_node_that_has_children_is_refused(self):
        section_id, first, second = self.section_with_children()
        before = self.state()
        code, _, stderr = self.verb(
            "replace", section_id, "--type", "text", "--text", "flattened",
            "--why", "it reads better as prose",
        )
        self.assertEqual(1, code)
        for named in (section_id, first, second):
            self.assertIn(named, stderr)
        self.assertEqual(before, self.state())

    def test_giving_a_node_with_children_character_data_is_refused(self):
        # A node holds children or text, never both, so this text would be
        # silently dropped by the serialiser. Refused instead.
        section_id, _, _ = self.section_with_children()
        before = self.state()
        code, _, stderr = self.verb(
            "replace", section_id, "--text", "prose", "--why", "a note"
        )
        self.assertEqual(1, code)
        self.assertIn(section_id, stderr)
        self.assertEqual(before, self.state())

    def test_moving_a_node_inside_itself_is_refused(self):
        section_id, first, _ = self.section_with_children()
        for position in (("--into", section_id), ("--after", first)):
            before = self.state()
            code, _, stderr = self.verb(
                *(("move", section_id) + position + ("--why", "a reason"))
            )
            self.assertEqual(1, code, position)
            self.assertIn(section_id, stderr)
            self.assertEqual(before, self.state(), position)

    def test_an_edit_that_would_write_an_invalid_canvas_is_refused(self):
        # The verdict is the validator's: <decision> is the named tripwire and
        # nothing in Python restates the vocabulary to catch it earlier.
        before = self.state()
        code, _, stderr = self.verb(
            "insert", "--into", "root", "--type", "decision", "--text", "A.",
            "--why", "a decision",
        )
        self.assertEqual(1, code)
        self.assertIn("decision", stderr)
        self.assertEqual(before, self.state())

    def test_an_edit_whose_text_xml_cannot_hold_is_refused(self):
        before = self.state()
        code, _, stderr = self.verb(
            "replace", self.problem_id, "--text", "a\bb", "--why", "a reason"
        )
        self.assertEqual(1, code)
        self.assertNotEqual("", stderr)
        self.assertEqual(before, self.state())

    def test_a_section_missing_its_required_title_is_refused(self):
        before = self.state()
        code, _, stderr = self.verb(
            "insert", "--into", "root", "--type", "section", "--why", "a section"
        )
        self.assertEqual(1, code)
        self.assertIn("section", stderr)
        self.assertEqual(before, self.state())


class TwoNodeEditsExitNonZero(VerbTestCase):
    """The done condition's third clause, in the shapes an agent actually
    reaches for: two ids in one invocation, a payload that tries to carry a
    second node, and the three container edits whose refusal is the whole of
    `node-identity.md` §5. Every one of them is non-zero with nothing written.
    """

    def section_with_children(self):
        section_id = self.inserted(
            "--into", "root", "--type", "section", "--title", "Options",
            "--why", "the options",
        )
        first = self.inserted("--into", section_id, "--text", "Option A", "--why", "a")
        second = self.inserted("--into", section_id, "--text", "Option B", "--why", "b")
        return section_id, first, second

    def test_naming_two_node_ids_in_one_invocation_exits_non_zero(self):
        section_id, first, second = self.section_with_children()
        before = self.state()
        # The argv an agent writes when it wants to settle both options at once.
        code, stdout, stderr = self.verb(
            "replace", first, second, "--type", "text", "--text", "both",
            "--why", "change both options",
        )
        self.assertEqual(2, code)
        self.assertEqual(b"", stdout)
        self.assertIn(second, stderr)
        self.assertEqual(before, self.state())

    def test_a_second_id_is_refused_by_every_verb_that_takes_one(self):
        section_id, first, second = self.section_with_children()
        for edit in (
            ("replace", first, second, "--text", "both"),
            ("remove", first, second),
            ("move", first, second, "--into", "root"),
        ):
            before = self.state()
            code, stdout, _ = self.verb(*(edit + ("--why", "a reason")))
            self.assertEqual(2, code, edit)
            self.assertEqual(b"", stdout, edit)
            self.assertEqual(before, self.state(), edit)

    def test_a_payload_carrying_a_second_node_writes_one_node_of_text(self):
        # Not a refusal but the stronger answer: the payload has no way to
        # express a node, so markup handed to --text is character data on the
        # one node the command named, and no second node comes into being.
        before = self.ids()
        smuggled = (
            '<text id="zzzz" v="1">smuggled</text>'
            '<text id="yyyy" v="1">two</text>'
        )
        code, _, stderr = self.verb(
            "replace", self.problem_id, "--text", smuggled,
            "--why", "try to write two nodes through the payload",
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(before, self.ids())
        self.assertEqual(smuggled, self.node(self.problem_id).text)

    def test_the_three_container_edits_that_would_reach_a_subtree_exit_non_zero(self):
        section_id, first, second = self.section_with_children()
        for edit in (
            # A1: turn a container into a leaf, which would reach its subtree.
            ("replace", section_id, "--type", "text", "--text", "We chose A."),
            # A2: give a container character data while it has children.
            ("replace", section_id, "--text", "We chose A."),
            # A3: remove a container while it has children.
            ("remove", section_id),
        ):
            before = self.state()
            code, stdout, stderr = self.verb(*(edit + ("--why", "settle the options")))
            self.assertEqual(1, code, edit)
            self.assertEqual(b"", stdout, edit)
            # The refusal names the container, every child it would have
            # touched, and what to do instead — each child, with its own --why.
            for named in (section_id, first, second):
                self.assertIn(named, stderr, edit)
            self.assertIn("each child", stderr, edit)
            self.assertIn("--why", stderr, edit)
            self.assertEqual(before, self.state(), edit)


class WhatOneNodeMeansWhenTheNodeHasChildren(VerbTestCase):
    """The done condition's second clause. `node-identity.md` §5 is written for
    *a node that has children* and not for `<section>` alone, so every
    container the vocabulary has is exercised here: `<section>`, `<list>`,
    `<table>` and `<row>`. A docstring is not a specification, and a rule
    stated of one element is not a rule about containers."""

    def containers(self):
        """One of every container in the vocabulary, each holding two children.

        Returns a list of (container id, its two children, a position it may
        legally be moved to). The position is per container because the schema
        says where each type may sit: a `<row>` lives in a `<table>` and
        nowhere else, and a `<section>` nests one level.
        """
        destination = self.inserted(
            "--into", "root", "--type", "section", "--title", "Elsewhere",
            "--why", "somewhere to move into",
        )
        section = self.inserted(
            "--into", "root", "--type", "section", "--title", "A heading",
            "--why", "a section",
        )
        section_children = [
            self.inserted("--into", section, "--text", text, "--why", "a leaf")
            for text in ("one", "two")
        ]
        a_list = self.inserted("--into", "root", "--type", "list", "--why", "a list")
        items = [
            self.inserted(
                "--into", a_list, "--type", "item", "--text", text, "--why", "an item"
            )
            for text in ("first", "second")
        ]
        table = self.inserted("--into", "root", "--type", "table", "--why", "a table")
        rows = [
            self.inserted("--into", table, "--type", "row", "--why", "a row")
            for _ in range(2)
        ]
        cells = [
            self.inserted(
                "--into", rows[0], "--type", "cell", "--text", text, "--why", "a cell"
            )
            for text in ("option", "cost")
        ]
        return [
            (section, section_children, ("--after", self.problem_id)),
            (a_list, items, ("--into", destination)),
            (table, rows, ("--into", destination)),
            (rows[0], cells, ("--after", rows[1])),
        ]

    def subtree(self, node_id):
        """Every descendant's id, type, v, attributes and text, in order.

        A container's own character data is the serialiser's indentation and
        not content — `canvas/document.py` drops it on every parse — so it is
        dropped here too, and a subtree that moved deeper still compares equal.
        """
        return [
            (
                node.tag,
                node.get("id"),
                node.get("v"),
                sorted(node.items()),
                None if len(node) else node.text,
            )
            for node in list(self.node(node_id).iter())[1:]
        ]

    def test_replace_on_a_container_replaces_that_node_and_nothing_else(self):
        # "Nothing. replace on a container replaces that container node and
        # nothing else. Its children keep their ids, their v, their content and
        # their order." Stated of <section> and true of every container.
        for container, _, _ in self.containers():
            before = self.subtree(container)
            was = self.node(container).get("v")
            # A <section>'s own content is its title; the other containers
            # carry nothing but their identity, so a rename is all there is.
            payload = ()
            if self.node(container).tag == "section":
                payload = ("--title", "A heading, settled")
            code, _, stderr = self.verb(
                *(("replace", container) + payload + ("--why", "rename it"))
            )
            self.assertEqual(0, code, (container, stderr))
            self.assertEqual(before, self.subtree(container), container)
            now = self.node(container).get("v")
            self.assertEqual(int(was) + 1, int(now), container)
            self.assertEqual(
                [container], self.commits_naming_only(container), container
            )

    def commits_naming_only(self, node_id):
        """The nodes named by the commit this edit just made."""
        body = self.git("log", "-1", "--format=%B")
        return [
            line.split(": ", 1)[1].strip()
            for line in body.splitlines()
            if line.startswith("Canvas-Node:")
        ]

    def test_a_replace_payload_cannot_express_a_child_at_all(self):
        # The flags a payload has are four scalars. There is no --children, no
        # --file, no --body and no stdin, so "one commit rewriting N children"
        # is inexpressible here rather than merely refused.
        for flag in ("--children", "--body", "--file", "--xml", "--content", "--stdin"):
            code, _, _ = self.verb(
                "replace", self.problem_id, flag, "x", "--why", "a reason"
            )
            self.assertEqual(2, code, flag)
        code, _, _ = self.run_canvas("replace", "a-ledger-row", self.problem_id, "-")
        self.assertEqual(2, code)

    def test_a_type_change_is_refused_while_the_node_has_children(self):
        for container, children, _ in self.containers():
            before = self.state()
            code, stdout, stderr = self.verb(
                "replace", container, "--type", "text", "--text", "flattened",
                "--why", "it reads better as prose",
            )
            self.assertEqual(1, code, container)
            self.assertEqual(b"", stdout, container)
            for named in [container] + children:
                self.assertIn(named, stderr, container)
            self.assertEqual(before, self.state(), container)

    def test_character_data_is_refused_while_the_node_has_children(self):
        for container, children, _ in self.containers():
            before = self.state()
            code, stdout, stderr = self.verb(
                "replace", container, "--text", "prose", "--why", "a note"
            )
            self.assertEqual(1, code, container)
            self.assertEqual(b"", stdout, container)
            for named in [container] + children:
                self.assertIn(named, stderr, container)
            self.assertEqual(before, self.state(), container)

    def test_remove_is_refused_while_the_node_has_children(self):
        for container, children, _ in self.containers():
            before = self.state()
            code, stdout, stderr = self.verb(
                "remove", container, "--why", "tidying up"
            )
            self.assertEqual(1, code, container)
            self.assertEqual(b"", stdout, container)
            for named in [container] + children:
                self.assertIn(named, stderr, container)
            self.assertEqual(before, self.state(), container)

    def test_an_emptied_container_can_then_be_removed_one_node_at_a_time(self):
        # The refusal is a route and not a wall: what it asks for is possible,
        # and each step of it is one node with its own reason.
        # Deepest first, because a container inside a container has to be
        # emptied before its own parent can be — which is the rule, applied to
        # itself, and is exactly what the refusals ask for.
        emptied = list(reversed(self.containers()))
        for container, children, _ in emptied:
            for child in children + [container]:
                if self.node(child) is None:
                    continue
                code, _, stderr = self.verb(
                    "remove", child, "--why", "no longer needed"
                )
                self.assertEqual(0, code, (container, child, stderr))
        for container, children, _ in emptied:
            self.assertIsNone(self.node(container), container)
            for child in children:
                self.assertIsNone(self.node(child), child)

    def test_move_carries_the_subtree_and_is_still_one_node(self):
        # The children travel with the container and not one of their records
        # changes: same id, same v, same content, same parent, same order. The
        # commit names one node, and it is the one whose position changed.
        for container, children, position in self.containers():
            before = self.subtree(container)
            was = self.node(container).get("v")
            code, _, stderr = self.verb(
                *(("move", container) + position + ("--why", "reorganise"))
            )
            self.assertEqual(0, code, (container, stderr))
            self.assertEqual(before, self.subtree(container), container)
            now = self.node(container).get("v")
            self.assertEqual(int(was) + 1, int(now), container)
            self.assertEqual(
                [container], self.commits_naming_only(container), container
            )
            for child in children:
                self.assertEqual(1, len(self.history(child)), (container, child))

    def test_moving_a_container_into_its_own_subtree_is_refused(self):
        for container, children, _ in self.containers():
            for position in (("--into", container), ("--after", children[0])):
                before = self.state()
                code, _, stderr = self.verb(
                    *(("move", container) + position + ("--why", "reorganise"))
                )
                self.assertEqual(1, code, (container, position))
                self.assertIn(container, stderr)
                self.assertEqual(before, self.state(), (container, position))

    def test_insert_brings_exactly_one_node_and_it_arrives_childless(self):
        # An insert may bring a container, and the container it brings is
        # empty: there is no payload that fills one, so a subtree is built one
        # node and one reason at a time.
        for node_type, extra in (
            ("section", ("--title", "A heading")),
            ("list", ()),
            ("table", ()),
            ("text", ("--text", "a leaf")),
        ):
            before = set(self.ids())
            node_id = self.inserted(
                *(("--into", "root", "--type", node_type)
                  + extra + ("--why", "one node"))
            )
            self.assertEqual({node_id}, set(self.ids()) - before, node_type)
            self.assertEqual([], list(self.node(node_id)), node_type)
            self.assertEqual("1", self.node(node_id).get("v"), node_type)


class TheBaseStalenessRule(VerbTestCase):
    """engineering-spec.md section "Staleness", both branches, and the third
    case that is the ordinary one.

    The todo's done condition, clause by clause: a write whose own node moved
    since `--base` is refused with that node's diff and a non-zero exit; a
    write whose node did not move applies and reports the diff of what else
    changed; a read-then-write round trip against an unchanged canvas succeeds
    silently.
    """

    def head(self):
        return self.git("rev-parse", "HEAD").strip()

    def document(self):
        with open(self.canvas_file(), "rb") as handle:
            return handle.read()

    def by_somebody_else(self, *args):
        """An edit that lands while our writer is not looking. No --base."""
        code, _, stderr = self.verb(*args)
        self.assertEqual(0, code, stderr)

    # ------------------------------------------------------------------
    # Nothing moved
    # ------------------------------------------------------------------

    def test_a_read_then_write_round_trip_against_an_unchanged_canvas_is_silent(self):
        # The sha a read hands out is literally the one the next write declares.
        code, stdout, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code, stderr)
        base = stdout.decode("utf-8").splitlines()[0].split(": ", 1)[1]

        code, stdout, stderr = self.verb(
            "replace", self.problem_id, "--text", "Restated.",
            "--why", "sharper", "--base", base,
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        # Silent means no news, not no output: the two lines every verb prints
        # are its ordinary success output, and the sha on the second is what
        # the next write bases on.
        self.assertEqual(
            ["Canvas-Node: %s" % self.problem_id, "Canvas-Base: %s" % self.head()],
            stdout.decode("utf-8").splitlines(),
        )
        self.assertEqual("Restated.", self.node(self.problem_id).text)

    def test_every_verb_is_silent_when_nothing_moved(self):
        for edit in (
            ("replace", self.problem_id, "--text", "x"),
            ("move", self.problem_id, "--into", "root"),
            ("insert", "--into", "root", "--text", "x"),
            ("remove", self.problem_id),
        ):
            base = self.head()
            code, stdout, stderr = self.verb(
                *(edit + ("--base", base, "--why", "a reason"))
            )
            self.assertEqual(0, code, (edit, stderr))
            self.assertEqual("", stderr, edit)
            self.assertEqual(2, len(stdout.decode("utf-8").splitlines()), edit)

    def test_an_omitted_base_asks_for_no_check_and_gets_none(self):
        # The decision this task took: --base is optional, and omitting it is
        # the absence of the question rather than a base of "now". A canvas
        # that moved underneath a write with no --base is still written.
        base = self.head()
        self.by_somebody_else(
            "replace", self.value_id, "--text", "Moved.", "--why", "elsewhere"
        )
        self.assertNotEqual(base, self.head())
        code, stdout, stderr = self.verb(
            "replace", self.problem_id, "--text", "Mine.", "--why", "my edit"
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        self.assertEqual(2, len(stdout.decode("utf-8").splitlines()))
        self.assertEqual("Mine.", self.node(self.problem_id).text)

    # ------------------------------------------------------------------
    # The hard branch: the node this write names moved
    # ------------------------------------------------------------------

    def test_the_hard_branch_refuses_and_leaves_head_and_document_identical(self):
        for edit in (
            ("replace", "--text", "Mine."),
            ("remove",),
            ("move", "--into", "root"),
        ):
            node_id = self.inserted(
                "--into", "root", "--text", "Ours.", "--why", "a contested node"
            )
            base = self.head()
            self.by_somebody_else(
                "replace", node_id, "--text", "Theirs.", "--why", "they got there first"
            )

            head_before = self.head()
            document_before = self.document()
            code, stdout, stderr = self.verb(
                edit[0], node_id, *(edit[1:] + ("--why", "my edit", "--base", base))
            )
            self.assertEqual(1, code, (edit, stderr))
            self.assertEqual(b"", stdout, edit)
            # Applies nothing, writes no commit, leaves the document byte-identical.
            self.assertEqual(head_before, self.head(), edit)
            self.assertEqual(document_before, self.document(), edit)
            self.assertEqual("", self.git("status", "--porcelain"), edit)
            self.assertIn(node_id, stderr, edit)

    def test_the_hard_branch_output_carries_that_nodes_diff_since_base(self):
        node_id = self.inserted(
            "--into", "root", "--text", "Before.", "--why", "a contested node"
        )
        base = self.head()
        self.by_somebody_else(
            "replace", node_id, "--text", "After.", "--why", "they got there first"
        )

        code, _, stderr = self.verb(
            "replace", node_id, "--text", "Mine.",
            "--why", "my edit", "--base", base,
        )
        self.assertEqual(1, code)
        # git's own unified diff of that node's change, and the reason for it.
        self.assertIn("--- a/", stderr)
        self.assertIn("+++ b/", stderr)
        self.assertIn('-  <text id="%s" v="1">Before.</text>' % node_id, stderr)
        self.assertIn('+  <text id="%s" v="2">After.</text>' % node_id, stderr)
        self.assertIn("replace %s: they got there first" % node_id, stderr)
        self.assertIn("Canvas-Commit: %s" % self.head(), stderr)

    def test_the_hard_branch_carries_every_commit_that_moved_the_node(self):
        node_id = self.inserted(
            "--into", "root", "--text", "One.", "--why", "born"
        )
        base = self.head()
        self.by_somebody_else("replace", node_id, "--text", "Two.", "--why", "second")
        self.by_somebody_else("move", node_id, "--after", self.problem_id,
                              "--why", "third")

        code, _, stderr = self.verb(
            "remove", node_id, "--why", "my edit", "--base", base
        )
        self.assertEqual(1, code)
        self.assertIn("replace %s: second" % node_id, stderr)
        self.assertIn("move %s: third" % node_id, stderr)
        self.assertIn("2 commit(s)", stderr)

    def test_a_node_removed_since_base_is_the_hard_branch_with_its_diff(self):
        # The ultimate move. Without the check this is the bare "no node with
        # id X", which a writer working from a stale read learns nothing from.
        node_id = self.inserted(
            "--into", "root", "--text", "Doomed.", "--why", "a node"
        )
        base = self.head()
        self.by_somebody_else("remove", node_id, "--why", "no longer needed")

        code, _, stderr = self.verb(
            "replace", node_id, "--text", "Mine.",
            "--why", "my edit", "--base", base,
        )
        self.assertEqual(1, code)
        self.assertIn("remove %s: no longer needed" % node_id, stderr)
        self.assertIn('-  <text id="%s" v="1">Doomed.</text>' % node_id, stderr)

    def test_the_hard_branch_mints_nothing_and_writes_no_temporary(self):
        node_id = self.inserted("--into", "root", "--text", "x", "--why", "a node")
        base = self.head()
        self.by_somebody_else("replace", node_id, "--text", "y", "--why", "theirs")

        before = sorted(os.listdir(self.canvas_dir))
        code, _, _ = self.verb(
            "replace", node_id, "--text", "z", "--why", "mine", "--base", base
        )
        self.assertEqual(1, code)
        # Not the file, not a commit, not a temporary — and no drawn id, so the
        # space `is_free` greps has no gap nothing can account for.
        self.assertEqual(before, sorted(os.listdir(self.canvas_dir)))

    def test_a_node_that_did_not_move_is_not_the_hard_branch_on_a_prefix(self):
        # Ids are four characters and the match is on the trailer's value for
        # equality, so a node whose id merely starts the same is not this node.
        node_id = self.inserted("--into", "root", "--text", "x", "--why", "mine")
        base = self.head()
        self.by_somebody_else(
            "replace", self.value_id, "--text",
            "quoting Canvas-Node: %s at it" % node_id, "--why",
            "a reason that quotes Canvas-Node: %s" % node_id,
        )
        code, _, stderr = self.verb(
            "replace", node_id, "--text", "y", "--why", "mine", "--base", base
        )
        # A reason quoting the trailer text is not an edit to the node it names.
        self.assertEqual(0, code, stderr)

    # ------------------------------------------------------------------
    # The soft branch: something else moved
    # ------------------------------------------------------------------

    def test_the_soft_branch_applies_and_reports_the_other_nodes_change(self):
        base = self.head()
        self.by_somebody_else(
            "replace", self.value_id, "--text", "Expected differently.",
            "--why", "they revised the expected value",
        )
        head_before = self.head()

        code, stdout, stderr = self.verb(
            "replace", self.problem_id, "--text", "Restated.",
            "--why", "my edit", "--base", base,
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        printed = stdout.decode("utf-8")
        lines = printed.splitlines()

        # It applied: one commit, the node this write named, the new head.
        self.assertEqual("Restated.", self.node(self.problem_id).text)
        self.assertEqual("Canvas-Node: %s" % self.problem_id, lines[0])
        self.assertEqual("Canvas-Base: %s" % self.head(), lines[1])

        # And the same output carries the diff of what it did not know: the
        # range, the reason, and git's own diff of the other node's change.
        self.assertIn("Canvas-News: 1 commit(s) between %s and %s"
                      % (base, head_before), printed)
        self.assertIn("replace %s: they revised the expected value"
                      % self.value_id, printed)
        self.assertIn('-  <text id="%s" v="1">The value expected.</text>'
                      % self.value_id, printed)
        self.assertIn('+  <text id="%s" v="2">Expected differently.</text>'
                      % self.value_id, printed)

    def test_the_soft_branchs_news_excludes_this_writes_own_commit(self):
        # "What it did not know" is what landed before the write, so the range
        # ends at the head the write was applied to. Its own edit is not news.
        base = self.head()
        self.by_somebody_else(
            "replace", self.value_id, "--text", "Elsewhere.", "--why", "theirs"
        )
        code, stdout, _ = self.verb(
            "replace", self.problem_id, "--text", "Mine.",
            "--why", "my edit", "--base", base,
        )
        self.assertEqual(0, code)
        printed = stdout.decode("utf-8")
        self.assertNotIn("Mine.", printed.split("Canvas-News:", 1)[1])
        self.assertNotIn("my edit", printed)

    def test_the_soft_branch_reports_every_commit_in_between(self):
        base = self.head()
        self.by_somebody_else(
            "replace", self.value_id, "--text", "One.", "--why", "first by them"
        )
        self.by_somebody_else(
            "replace", self.value_id, "--text", "Two.", "--why", "second by them"
        )
        code, stdout, _ = self.verb(
            "remove", self.problem_id, "--why", "my edit", "--base", base
        )
        self.assertEqual(0, code)
        printed = stdout.decode("utf-8")
        self.assertIn("2 commit(s)", printed)
        self.assertIn("first by them", printed)
        self.assertIn("second by them", printed)

    def test_insert_always_takes_the_soft_branch_even_when_its_anchor_moved(self):
        # The node an insert names is minted after the check, so it cannot have
        # moved. The anchor is a different node: an anchor that changed is
        # reported in the news, not refused — an anchor that is gone is already
        # `_place`'s refusal and stays there.
        base = self.head()
        self.by_somebody_else(
            "replace", self.problem_id, "--text", "Reworded.", "--why", "theirs"
        )
        code, stdout, stderr = self.verb(
            "insert", "--after", self.problem_id, "--text", "A note.",
            "--why", "filed beside it", "--base", base,
        )
        self.assertEqual(0, code, stderr)
        printed = stdout.decode("utf-8")
        node_id = printed.splitlines()[0].split(": ", 1)[1]
        self.assertIn("Canvas-News:", printed)
        self.assertIn("replace %s: theirs" % self.problem_id, printed)
        self.assertEqual(
            [self.problem_id, node_id, self.value_id],
            [child.get("id") for child in self.tree()],
        )

    def test_the_soft_branch_is_still_one_commit_with_all_three_trailers(self):
        # The invariants this rule must not weaken: one edit is one commit, and
        # the commit records the head it was applied to.
        base = self.head()
        self.by_somebody_else(
            "replace", self.value_id, "--text", "Elsewhere.", "--why", "theirs"
        )
        head_before = self.head()
        commits_before = len(self.subjects())

        code, _, stderr = self.verb(
            "replace", self.problem_id, "--text", "Mine.",
            "--why", "my edit", "--base", base,
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(commits_before + 1, len(self.subjects()))
        body = self.bodies()[-1]
        self.assertIn("Canvas-Node: %s" % self.problem_id, body)
        self.assertIn("Canvas-Author: ", body)
        # The trailer is the head the edit was applied to, not the base it
        # declared. Those are two different facts and only one is stale.
        self.assertIn("Canvas-Base: %s" % head_before, body)
        self.assertNotIn("Canvas-Base: %s" % base, body)

    def test_a_change_to_another_canvas_is_not_news_and_is_not_staleness(self):
        # state/canvas is one repository for every ledger row and the sha is
        # repository-wide on purpose. Scoping to this canvas's file is what
        # keeps the round trip silent in a store where other rows are busy.
        base = self.head()
        self.create(ledger_id="another-row", problem="Elsewhere.", value="Also.")
        self.assertNotEqual(base, self.head())

        code, stdout, stderr = self.verb(
            "replace", self.problem_id, "--text", "Mine.",
            "--why", "my edit", "--base", base,
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        self.assertEqual(2, len(stdout.decode("utf-8").splitlines()))

    # ------------------------------------------------------------------
    # A base that is not usable
    # ------------------------------------------------------------------

    def test_a_malformed_base_is_the_invocation_being_wrong(self):
        for declared in ("not-a-sha", "", "zzzz", "12", "g" * 40, "HEAD~1"):
            before = self.state()
            code, stdout, stderr = self.verb(
                "replace", self.problem_id, "--text", "x",
                "--why", "a reason", "--base", declared,
            )
            self.assertEqual(2, code, declared)
            self.assertEqual(b"", stdout, declared)
            self.assertIn("--base", stderr, declared)
            self.assertEqual(before, self.state(), declared)

    def test_a_well_formed_base_this_repository_never_handed_out_is_refused(self):
        unknown = "0123456789" * 4
        before = self.state()
        code, stdout, stderr = self.verb(
            "replace", self.problem_id, "--text", "x",
            "--why", "a reason", "--base", unknown,
        )
        self.assertEqual(1, code)
        self.assertEqual(b"", stdout)
        self.assertIn(unknown, stderr)
        self.assertEqual(before, self.state())

    def test_a_known_base_that_is_not_an_ancestor_of_the_head_is_refused(self):
        # A commit this repository has but that nothing on the current line of
        # history descends from. `<base>..HEAD` would answer "nothing moved"
        # for it, which is a vacuous pass wearing the safe case's face.
        elsewhere = self.git(
            "-c", "user.name=elsewhere", "-c", "user.email=elsewhere@localhost",
            "commit-tree", self.git("rev-parse", "HEAD^{tree}").strip(),
            "-m", "a commit on no branch",
        ).strip()
        self.assertEqual(
            elsewhere, self.git("rev-parse", "--verify", elsewhere).strip()
        )

        before = self.state()
        code, stdout, stderr = self.verb(
            "replace", self.problem_id, "--text", "x",
            "--why", "a reason", "--base", elsewhere,
        )
        self.assertEqual(1, code)
        self.assertEqual(b"", stdout)
        self.assertIn(elsewhere, stderr)
        self.assertIn("ancestor", stderr)
        self.assertEqual(before, self.state())

    def test_an_abbreviated_base_resolves(self):
        # `read` hands out the full forty characters, but git resolves an
        # abbreviation supplied later and there is no reason to refuse one.
        base = self.head()
        self.by_somebody_else(
            "replace", self.value_id, "--text", "Elsewhere.", "--why", "theirs"
        )
        code, stdout, stderr = self.verb(
            "replace", self.problem_id, "--text", "Mine.",
            "--why", "my edit", "--base", base[:12],
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("Canvas-News:", stdout.decode("utf-8"))

    def test_create_takes_no_base(self):
        # The birth of a canvas has no prior state it could have been decided
        # against, which is also why its root commit writes no Canvas-Base:.
        code, _, _ = self.run_canvas(
            "create", "yet-another-row", "--problem", "P",
            "--expected-value", "V", "--base", self.head(),
        )
        self.assertEqual(2, code)
        self.assertFalse(os.path.exists(self.canvas_file("yet-another-row")))


class ThePublicImportSurfaceHasNoWholeDocumentWrite(VerbTestCase):
    """The done condition's first clause, at the level the todo scopes it to —
    "including any file-level or import path". `from canvas import store` must
    offer no function that writes a document wholesale, and the one private
    function that puts a canvas on its path must refuse a write worth more than
    one node no matter who calls it."""

    #: Every public name `canvas.store` offers, frozen. A new one added here
    #: fails this test until somebody has classified it, which is the point: the
    #: supported write surface is six functions and the rest reads or computes.
    PUBLIC_STORE = {
        "Refusal", "ToolProblem",
        # The supported write surface, and all of it. `freeze` is a write and
        # not an editing verb: it names no node and changes no byte of the
        # document, and it is the last one a canvas ever takes.
        "create", "insert", "replace", "remove", "move", "freeze",
        # Reads, lookups and pure functions.
        "read", "history", "provenance", "Edit", "canvas_directory", "canvas_path",
        "is_repository", "ensure_repository", "head_sha", "is_free", "mint",
        "require_reason", "history_length", "next_version", "default_author",
        # A pure argument guard beside `require_reason`, and classified the
        # same way: it takes `create`'s two strings and refuses a blank one.
        # It takes no document and writes nothing.
        "require_first_nodes",
        "preflight", "frozen", "Freeze",
        # Imported modules, not API.
        "collections", "errno", "os", "re", "secrets", "stat", "subprocess",
        "document",
        "validate_file",
        "EnvironmentProblem",
        # The shape every refusal takes, and the one place it is rendered.
        "refusal",
    }

    def store(self):
        from canvas import store

        return store

    def public(self, module):
        return {name for name in vars(module) if not name.startswith("_")}

    def test_the_store_offers_no_public_function_that_takes_a_document(self):
        self.assertEqual(self.PUBLIC_STORE, self.public(self.store()))
        self.assertFalse(hasattr(self.store(), "write_and_commit"))

    def test_nothing_public_in_canvas_document_writes_to_disk(self):
        # document.py builds and serialises trees; the one function that opens
        # a file is parse, and it reads.
        import inspect

        from canvas import document as module

        for name in self.public(module):
            thing = getattr(module, name)
            if not inspect.isfunction(thing):
                continue
            source = inspect.getsource(thing)
            self.assertNotIn('open(', source.replace("ET.parse", ""), name)
            self.assertNotIn("os.replace", source, name)

    def test_the_write_path_refuses_a_whole_document_rewrite(self):
        # The audit's A17, which exited 0 and committed: build a new document
        # from nothing and hand it in. It is now a refusal, and it is one for
        # every caller, because it lives in the only function that can put a
        # canvas on its path.
        store = self.store()
        before = self.state()
        rewritten = document.new_canvas("a-ledger-row")
        document.place_into(rewritten, document.ROOT, document.new_text("qqqq", "gone"))
        document.place_into(rewritten, document.ROOT, document.new_text("pppp", "also"))

        with self.assertRaises(store.Refusal) as caught:
            store._write_and_commit(
                self.canvas_dir, self.canvas_file(), rewritten,
                "replace", "the whole document", "a whole-document rewrite",
                "audit | by-hand", node_id="qqqq",
            )
        for named in (self.problem_id, self.value_id, "pppp"):
            self.assertIn(named, str(caught.exception))
        self.assertEqual(before, self.state())

    def test_the_write_path_refuses_n_nodes_hidden_behind_one_trailer(self):
        # The worse variant node-identity.md §5 names literally: one commit
        # rewriting N nodes under one Canvas-Node: trailer, so that N-1 nodes
        # are changed by a commit their own history never sees.
        store = self.store()
        before = self.state()
        tree = document.parse(self.canvas_file())
        for node in list(tree):
            node.text = "rewritten wholesale"

        with self.assertRaises(store.Refusal) as caught:
            store._write_and_commit(
                self.canvas_dir, self.canvas_file(), tree,
                "replace", self.problem_id, "rewrite every node at once",
                "audit | by-hand", node_id=self.problem_id,
            )
        self.assertIn(self.value_id, str(caught.exception))
        self.assertNotIn("Canvas-Node: %s" % self.problem_id, self.git("log", "-1"))
        self.assertEqual(before, self.state())

    def test_the_write_path_refuses_a_second_node_born_in_the_same_commit(self):
        store = self.store()
        before = self.state()
        tree = document.parse(self.canvas_file())
        document.find(tree, self.problem_id).text = "restated"
        document.place_into(
            tree, document.ROOT, document.new_text("qqqq", "and a new one")
        )

        with self.assertRaises(store.Refusal) as caught:
            store._write_and_commit(
                self.canvas_dir, self.canvas_file(), tree,
                "replace", self.problem_id, "one edit and one smuggled birth",
                "audit | by-hand", node_id=self.problem_id,
            )
        self.assertIn("qqqq", str(caught.exception))
        self.assertEqual(before, self.state())

    def test_the_write_path_refuses_a_reorder_of_nodes_it_did_not_name(self):
        # A rewrite that shuffles two siblings changes no node's own record, so
        # the order is compared too.
        store = self.store()
        third = self.inserted("--into", "root", "--text", "a third", "--why", "a third")
        before = self.state()
        tree = document.parse(self.canvas_file())
        moved = document.detach(tree, self.value_id)
        tree.insert(0, moved)
        document.find(tree, third).text = "a third, restated"

        with self.assertRaises(store.Refusal) as caught:
            store._write_and_commit(
                self.canvas_dir, self.canvas_file(), tree,
                "replace", third, "an edit with a reshuffle in it",
                "audit | by-hand", node_id=third,
            )
        self.assertIn("root", str(caught.exception))
        self.assertEqual(before, self.state())

    def test_the_write_path_refuses_a_nameless_write_over_an_existing_canvas(self):
        # A commit that names no node changes no node's history, so the only
        # document it may write is a canvas being born.
        store = self.store()
        before = self.state()
        with self.assertRaises(store.Refusal) as caught:
            store._write_and_commit(
                self.canvas_dir, self.canvas_file(),
                document.new_canvas("a-ledger-row"),
                "replace", "whole document", "a rewrite naming nothing",
                "audit | by-hand",
            )
        self.assertIn(self.canvas_file(), str(caught.exception))
        self.assertEqual(before, self.state())

    def test_a_canvas_cannot_be_born_with_nodes_already_in_it(self):
        # node-identity.md §4: the creation commit creates the root only, and
        # the birth of a canvas gets no exemption from the rule.
        store = self.store()
        born = document.new_canvas("a-new-row")
        document.place_into(born, document.ROOT, document.new_text("qqqq", "a problem"))
        path = self.canvas_file("a-new-row")

        with self.assertRaises(store.Refusal) as caught:
            store._write_and_commit(
                self.canvas_dir, path, born, "create", "a-new-row",
                "born with two nodes in it", "audit | by-hand",
            )
        self.assertIn("qqqq", str(caught.exception))
        self.assertFalse(os.path.exists(path))

    def test_the_write_path_refuses_an_edit_to_a_canvas_that_is_not_there(self):
        # A commit naming a node is an edit of something. With no canvas at the
        # path there is nothing for it to be one edit of, and writing the whole
        # document anyway is the rewrite under another name.
        store = self.store()
        path = self.canvas_file("no-such-row")
        with self.assertRaises(store.Refusal):
            store._write_and_commit(
                self.canvas_dir, path, document.new_canvas("no-such-row"),
                "replace", "x", "an edit of nothing", "audit | by-hand",
                node_id="qqqq",
            )
        self.assertFalse(os.path.exists(path))

    def test_the_write_path_refuses_a_document_that_uses_one_id_twice(self):
        # Two nodes sharing an id share one history, so the guard cannot say
        # which of them an edit was of — and neither could a reader.
        store = self.store()
        before = self.state()
        tree = document.parse(self.canvas_file())
        document.place_into(
            tree, document.ROOT, document.new_text(self.problem_id, "a twin")
        )
        with self.assertRaises(store.Refusal) as caught:
            store._write_and_commit(
                self.canvas_dir, self.canvas_file(), tree, "insert",
                self.problem_id, "a node with a borrowed id", "audit | by-hand",
                node_id=self.problem_id,
            )
        self.assertIn(self.problem_id, str(caught.exception))
        self.assertEqual(before, self.state())

    def test_the_write_path_refuses_a_path_outside_the_canvas_repository(self):
        store = self.store()
        escaped = os.path.join(self.workspace, "escaped.xml")
        with self.assertRaises(store.ToolProblem):
            store._write_and_commit(
                self.canvas_dir, escaped, document.new_canvas("escaped"),
                "create", "escaped", "a canvas outside the store",
                "audit | by-hand",
            )
        self.assertFalse(os.path.exists(escaped))

    def test_a_refused_write_leaves_no_temporary_file_behind(self):
        store = self.store()
        tree = document.parse(self.canvas_file())
        for node in list(tree):
            node.text = "rewritten wholesale"
        with self.assertRaises(store.Refusal):
            store._write_and_commit(
                self.canvas_dir, self.canvas_file(), tree, "replace",
                self.problem_id, "a reason", "audit | by-hand",
                node_id=self.problem_id,
            )
        self.assertEqual(
            ["a-ledger-row.xml"],
            sorted(name for name in os.listdir(self.canvas_dir) if name != ".git"),
        )

    def test_the_four_verbs_still_reach_the_write_path_they_are_guarded_by(self):
        # The guard is not a wall around the store: every ordinary edit still
        # goes through it, exits 0, and makes exactly one commit.
        before = len(self.git("log", "--format=%H").split())
        node_id = self.inserted("--into", "root", "--text", "a node", "--why", "one")
        for edit in (
            ("replace", node_id, "--text", "restated", "--why", "two"),
            ("move", node_id, "--after", self.problem_id, "--why", "three"),
            ("remove", node_id, "--why", "four"),
        ):
            code, _, stderr = self.verb(*edit)
            self.assertEqual(0, code, (edit, stderr))
        self.assertEqual(before + 4, len(self.git("log", "--format=%H").split()))


class OneCommandReturnsANodesReasonHistory(VerbTestCase):
    """The done condition's second clause: one command returns the full reason
    history of a single node id, including edits made before a `move`."""

    def blocks(self, node_id, ledger_id="a-ledger-row"):
        """Run `history` and return its blocks as (sha, author, verb, reason)."""
        code, stdout, stderr = self.run_canvas("history", ledger_id, node_id)
        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        paragraphs = stdout.decode("utf-8").split("\n\n")
        self.assertEqual("Canvas-Node: %s\n" % node_id, paragraphs[0] + "\n")
        edits = []
        for paragraph in paragraphs[1:]:
            sha, author, subject = paragraph.strip("\n").split("\n")
            self.assertTrue(sha.startswith("Canvas-Commit: "), sha)
            self.assertTrue(author.startswith("Canvas-Author: "), author)
            verb, reason = subject.split(": ", 1)
            edits.append(
                (
                    sha.split(": ", 1)[1],
                    author.split(": ", 1)[1],
                    verb,
                    reason,
                )
            )
        return edits

    def test_a_node_born_by_insert_has_the_reason_it_was_born_for(self):
        node_id = self.inserted(
            "--into", "root", "--text", "A note.", "--why", "the argument needs it"
        )
        self.assertEqual(
            [("insert", "the argument needs it")],
            [(verb, reason) for _, _, verb, reason in self.blocks(node_id)],
        )

    def test_the_history_carries_the_edits_made_before_a_move(self):
        # The clause the todo singles out: insert, replace, then move into
        # another container, and the history after the move still has the
        # insert and the replace, in order. `move` keeps the node's id, so the
        # query that finds the move finds everything the id ever did.
        section_id = self.inserted(
            "--into", "root", "--type", "section", "--title", "A heading",
            "--why", "somewhere to file things",
        )
        node_id = self.inserted(
            "--into", "root", "--text", "Draft.", "--why", "the first draft"
        )
        self.verb("replace", node_id, "--text", "Sharper.", "--why", "sharpen it")
        code, _, stderr = self.verb(
            "move", node_id, "--into", section_id, "--why", "file it under the heading"
        )
        self.assertEqual(0, code, stderr)

        self.assertEqual(
            [
                ("insert", "the first draft"),
                ("replace", "sharpen it"),
                ("move", "file it under the heading"),
            ],
            [(verb, reason) for _, _, verb, reason in self.blocks(node_id)],
        )
        # And the node really did move: the history spans the move rather than
        # restarting at it.
        self.assertEqual(
            [node_id], [child.get("id") for child in self.node(section_id)]
        )

    def test_the_history_is_oldest_first_and_ends_at_the_current_text(self):
        node_id = self.inserted(
            "--into", "root", "--text", "One.", "--why", "first"
        )
        self.verb("replace", node_id, "--text", "Two.", "--why", "second")
        self.verb("replace", node_id, "--text", "Three.", "--why", "third")
        reasons = [reason for _, _, _, reason in self.blocks(node_id)]
        self.assertEqual(["first", "second", "third"], reasons)
        self.assertEqual("Three.", self.node(node_id).text)

    def test_every_block_names_the_commit_and_the_author(self):
        author = "leo | step:implement | run:ship-the-flag-3"
        node_id = self.inserted(
            "--into", "root", "--text", "x", "--why", "one", "--author", author
        )
        self.verb(
            "replace", node_id, "--text", "y", "--why", "two", "--author", author
        )
        shas = [sha for sha, _, _, _ in self.blocks(node_id)]
        self.assertEqual(2, len(shas))
        for sha in shas:
            self.assertTrue(SHA.match(sha), sha)
        # Oldest first, which is the reverse of git log's own order.
        self.assertEqual(
            shas,
            [
                sha
                for sha in self.git("log", "--reverse", "--format=%H").split()
                if sha in shas
            ],
        )
        self.assertEqual(
            [author, author], [name for _, name, _, _ in self.blocks(node_id)]
        )

    def test_a_removed_node_still_has_its_whole_history(self):
        node_id = self.inserted("--into", "root", "--text", "x", "--why", "born")
        self.verb("remove", node_id, "--why", "it was wrong")
        self.assertIsNone(self.node(node_id))
        self.assertEqual(
            [("insert", "born"), ("remove", "it was wrong")],
            [(verb, reason) for _, _, verb, reason in self.blocks(node_id)],
        )

    def test_the_first_nodes_of_a_canvas_have_the_reason_create_gave_them(self):
        self.assertEqual(
            [("insert", "the problem the ledger row states")],
            [(verb, reason) for _, _, verb, reason in self.blocks(self.problem_id)],
        )
        self.assertEqual(
            [("insert", "the expected value the ledger row states")],
            [(verb, reason) for _, _, verb, reason in self.blocks(self.value_id)],
        )


class TheHistoryCommandMatchesTheTrailerAndNotASubstring(VerbTestCase):
    """`git log --grep='Canvas-Node: b7'` matches anywhere in the message, and
    ids are four characters, so it answers for `b7pk` when it was asked about
    `b7`. This command matches the trailer's value, for equality."""

    def documented_grep(self, pattern):
        """The raw command README.md used to document, for contrast."""
        return self.git(
            "log", "--grep=Canvas-Node: %s" % pattern, "--format=%H"
        ).split()

    def test_a_prefix_of_a_real_id_is_not_that_node(self):
        node_id = self.inserted("--into", "root", "--text", "x", "--why", "born")
        self.verb("replace", node_id, "--text", "y", "--why", "reworded")
        prefix = node_id[:2]

        # The collision is reachable, not hypothetical: the documented grep
        # returns this node's whole life for two characters of its id.
        self.assertEqual(
            sorted(self.documented_grep(node_id)),
            sorted(self.documented_grep(prefix)),
        )
        # The command does not.
        code, stdout, stderr = self.run_canvas("history", "a-ledger-row", prefix)
        self.assertEqual(1, code, stderr)
        self.assertEqual(b"", stdout)
        self.assertIn(prefix, stderr)

    def test_a_reason_that_quotes_the_trailer_is_not_an_edit_to_that_node(self):
        node_id = self.inserted("--into", "root", "--text", "x", "--why", "born")
        self.inserted(
            "--into", "root", "--text", "y",
            "--why", "restates what Canvas-Node: %s already said" % node_id,
        )
        # The documented grep counts the quoting commit as an edit to the node
        # it merely mentions; the command reports only the commit that named it.
        self.assertEqual(2, len(self.documented_grep(node_id)))
        code, stdout, stderr = self.run_canvas("history", "a-ledger-row", node_id)
        self.assertEqual(0, code, stderr)
        self.assertEqual(
            1, stdout.decode("utf-8").count("Canvas-Commit: "), stdout
        )

    def test_a_quoted_trailer_does_not_bump_the_quoted_nodes_v(self):
        # The same equality, on the other side of it: `v` is the number of
        # commits naming the node, counted through the same matcher, so a
        # commit that merely mentions an id cannot move that node's version.
        node_id = self.inserted("--into", "root", "--text", "x", "--why", "born")
        self.inserted(
            "--into", "root", "--text", "y",
            "--why", "restates what Canvas-Node: %s already said" % node_id,
        )
        self.verb("replace", node_id, "--text", "z", "--why", "reworded")
        self.assertEqual("2", self.node(node_id).get("v"))

    def test_a_node_of_another_canvas_is_not_a_node_of_this_one(self):
        code, _, stderr = self.run_canvas(
            "create", "another-row", "--problem", "P", "--expected-value", "E"
        )
        self.assertEqual(0, code, stderr)
        code, stdout, stderr = self.run_canvas(
            "history", "another-row", self.problem_id
        )
        self.assertEqual(1, code, stderr)
        self.assertEqual(b"", stdout)
        self.assertIn(self.problem_id, stderr)

    def test_an_id_that_is_not_an_id_at_all_is_refused_and_not_run_as_a_pattern(self):
        # A node id typed at the command line need not be a real one. A regex
        # metacharacter in it names no node, which is the answer it gets — not
        # a crash, and not every node in the canvas.
        for pattern in (".*", "^", "[", "%s|%s" % (self.problem_id, self.value_id)):
            code, stdout, stderr = self.run_canvas(
                "history", "a-ledger-row", pattern
            )
            self.assertEqual(1, code, (pattern, stderr))
            self.assertEqual(b"", stdout)


class TheHistoryCommandRefusesWhatIsNotThere(VerbTestCase):
    """The exit-code contract: 1 when the request is wrong against the store as
    it stands, 2 when the tool or its environment is, and stderr saying which of
    the two `1`s it was."""

    def test_no_canvas_for_that_ledger_id_exits_one_and_says_so(self):
        code, stdout, stderr = self.run_canvas(
            "history", "no-such-row", self.problem_id
        )
        self.assertEqual(1, code)
        self.assertEqual(b"", stdout)
        self.assertIn("no canvas for ledger id no-such-row", stderr)

    def test_no_such_node_exits_one_and_says_something_different(self):
        code, stdout, stderr = self.run_canvas("history", "a-ledger-row", "zzzz")
        self.assertEqual(1, code)
        self.assertEqual(b"", stdout)
        self.assertIn("no node with id zzzz", stderr)
        # The two are told apart: a missing canvas and a missing node are
        # different repairs, and the message is where the caller learns which.
        self.assertNotIn("no canvas for ledger id", stderr)

    def test_a_malformed_ledger_id_exits_two(self):
        code, _, stderr = self.run_canvas(
            "history", "../../etc/passwd", self.problem_id
        )
        self.assertEqual(2, code)
        self.assertIn("not a usable ledger id", stderr)

    def test_an_unset_workspace_exits_two(self):
        code, _, stderr = self.run_canvas(
            "history", "a-ledger-row", self.problem_id, workspace=None
        )
        self.assertEqual(2, code)
        self.assertIn("OPENCLAW_WORKSPACE", stderr)

    def test_a_workspace_that_is_not_a_directory_exits_two(self):
        not_a_directory = os.path.join(self.workspace, "a-file")
        with open(not_a_directory, "w", encoding="utf-8") as handle:
            handle.write("not a workspace\n")
        code, _, stderr = self.run_canvas(
            "history", "a-ledger-row", self.problem_id, workspace=not_a_directory
        )
        self.assertEqual(2, code)
        self.assertIn("not a directory", stderr)

    def test_git_missing_from_the_environment_exits_two(self):
        # The tool is wrong, not the request: exit 2, and nothing said about
        # the node.
        empty = tempfile.mkdtemp(prefix="canvas-store-test-no-git-")
        self.addCleanup(shutil.rmtree, empty, True)
        environment = dict(os.environ, OPENCLAW_WORKSPACE=self.workspace, PATH=empty)
        result = subprocess.run(
            [sys.executable, CANVAS, "history", "a-ledger-row", self.problem_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertIn("git", result.stderr.decode("utf-8", "replace"))


class TheHistoryCommandOnlyReads(VerbTestCase):
    """A read is a read: it writes no file, makes no commit, and does not
    initialise a repository — the same contract `read` already has."""

    def test_it_changes_nothing_about_the_canvas_or_the_repository(self):
        before = self.state()
        code, _, stderr = self.run_canvas(
            "history", "a-ledger-row", self.problem_id
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(before, self.state())

    def test_it_does_not_initialise_a_repository_in_a_clean_workspace(self):
        clean = tempfile.mkdtemp(prefix="canvas-store-test-")
        self.addCleanup(shutil.rmtree, clean, True)
        code, _, stderr = self.run_canvas(
            "history", "a-ledger-row", self.problem_id, workspace=clean
        )
        self.assertEqual(1, code, stderr)
        # Nothing was created to say there was nothing there.
        self.assertEqual([], os.listdir(clean))

    def test_it_goes_through_the_pinned_git_invocation(self):
        # Every git call in the store names --git-dir and --work-tree, so a
        # canvas repository nested inside another one is still the repository
        # that answers. An outer repository here has a commit of its own, and
        # none of it reaches the history of a canvas node.
        outer = subprocess.run(
            ["git", "init", "-b", "main", "-q", "--", self.workspace],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(0, outer.returncode, outer.stderr)
        self.addCleanup(
            shutil.rmtree, os.path.join(self.workspace, ".git"), True
        )
        code, stdout, stderr = self.run_canvas(
            "history", "a-ledger-row", self.problem_id
        )
        self.assertEqual(0, code, stderr)
        self.assertIn(b"the problem the ledger row states", stdout)


class EveryAppliedEditCommitCarriesAllThreeTrailers(VerbTestCase):
    """The done condition's first clause, asserted over a canvas that has had
    every verb applied to it: one commit per edit, carrying `Canvas-Node`,
    `Canvas-Author` and `Canvas-Base` — with the root commit's two documented
    exemptions handled by name rather than by being left out."""

    def trailers(self, body):
        return dict(
            line.split(": ", 1)
            for line in body.strip().splitlines()
            if line.startswith("Canvas-")
        )

    def test_every_commit_an_edit_produced_carries_all_three(self):
        section_id = self.inserted(
            "--into", "root", "--type", "section", "--title", "A heading",
            "--why", "a container",
        )
        node_id = self.inserted(
            "--into", "root", "--text", "x", "--why", "a node"
        )
        for edit in (
            ("replace", node_id, "--text", "y", "--why", "reworded"),
            ("move", node_id, "--into", section_id, "--why", "filed"),
            ("remove", node_id, "--why", "no longer needed"),
        ):
            code, _, stderr = self.verb(*edit)
            self.assertEqual(0, code, (edit, stderr))

        bodies = self.bodies()
        subjects = self.subjects()
        # One commit per applied edit: create's root plus its two inserts, plus
        # the five edits above.
        self.assertEqual(8, len(bodies))

        root_commits = [
            index
            for index, subject in enumerate(subjects)
            if not self.trailers(bodies[index]).get("Canvas-Node")
        ]
        # Exactly one commit in the whole log names no node, and it is the
        # birth of the canvas: README.md's two documented exemptions, which
        # apply to that commit and to no other.
        self.assertEqual([0], root_commits)
        birth = self.trailers(bodies[0])
        self.assertTrue(subjects[0].startswith("create a-ledger-row: "), subjects[0])
        # <canvas> is not a node, so there is no node for a Canvas-Node: to
        # name; and there was no prior state for a Canvas-Base: to record.
        self.assertNotIn("Canvas-Node", birth)
        self.assertNotIn("Canvas-Base", birth)
        self.assertIn("Canvas-Author", birth)

        for index, body in list(enumerate(bodies))[1:]:
            trailers = self.trailers(body)
            self.assertIn("Canvas-Node", trailers, subjects[index])
            self.assertIn("Canvas-Author", trailers, subjects[index])
            self.assertIn("Canvas-Base", trailers, subjects[index])
            self.assertEqual(1, body.count("Canvas-Node:"), body)
            # The subject names the verb, the node and the reason.
            self.assertTrue(
                subjects[index].startswith(
                    "%s %s: "
                    % (subjects[index].split(" ", 1)[0], trailers["Canvas-Node"])
                ),
                subjects[index],
            )
            self.assertTrue(subjects[index].split(": ", 1)[1].strip(), subjects[index])

    def test_the_history_command_shows_the_same_three_facts_it_reads(self):
        # The trailers are what the command reads, so what it prints has to be
        # what the commits carry: the sha, the author, and the node's own id.
        node_id = self.inserted("--into", "root", "--text", "x", "--why", "a node")
        code, stdout, stderr = self.run_canvas("history", "a-ledger-row", node_id)
        self.assertEqual(0, code, stderr)
        printed = stdout.decode("utf-8")
        head = self.git("rev-parse", "HEAD").strip()
        self.assertIn("Canvas-Node: %s\n" % node_id, printed)
        self.assertIn("Canvas-Commit: %s\n" % head, printed)
        self.assertIn(
            "Canvas-Author: %s\n" % self.trailers(self.bodies()[-1])["Canvas-Author"],
            printed,
        )


class MergeAndSplitRecordNoLineageOfTheirOwn(VerbTestCase):
    """`node-identity.md` section 7's premise, as an invariant rather than as
    prose: the tool records no ancestor and no successor.

    A real merge and a real split, performed with the four verbs that exist,
    leave the pointer between the two halves in exactly one place — the text
    of a `--why` — and section 7's ruling is built on that being true. What is
    asserted here is the tool's half of it: no attribute, no trailer and no
    shared commit carries lineage, the retained and surviving ids keep every
    reason they ever had, and the stranded id still answers with its whole
    life. If a lineage field is ever added these fail, which reopens the
    ruling rather than letting it be quietly outgrown.

    The same merge and split were run by hand against `bin/canvas` and are
    recorded in `docs/merge-and-split/`; this is that exercise as something the
    suite re-runs.
    """

    TRAILER_KEYS = ("Canvas-Node", "Canvas-Author", "Canvas-Base")

    def edits(self, node_id):
        """`history`'s blocks as (verb, reason), oldest first."""
        code, stdout, stderr = self.run_canvas("history", "a-ledger-row", node_id)
        self.assertEqual(0, code, stderr)
        pairs = []
        for paragraph in stdout.decode("utf-8").split("\n\n")[1:]:
            subject = paragraph.strip("\n").splitlines()[2]
            verb, reason = subject.split(": ", 1)
            pairs.append((verb, reason))
        return pairs

    def trailer_keys(self, body):
        return [
            line.split(": ", 1)[0]
            for line in body.strip().splitlines()
            if line.startswith("Canvas-")
        ]

    def split(self):
        """A real split: `replace` cuts the node down to its first claim, and
        `insert` gives the remainder its own node. Returns (retained, born)."""
        retained = self.inserted(
            "--into", "root",
            "--text", "One claim. And a second claim.",
            "--why", "the node this test splits, deliberately holding two claims",
        )
        code, _, stderr = self.verb(
            "replace", retained,
            "--text", "One claim.",
            "--why", "cut down to the first claim; the second is going into its own node",
        )
        self.assertEqual(0, code, stderr)
        born = self.inserted(
            "--after", retained,
            "--text", "And a second claim.",
            "--why", "the second claim, which was the second sentence of %s "
                     "until the replace one commit earlier" % retained,
        )
        return retained, born

    def two_halves(self):
        """Two adjacent nodes whose content joins into one. Returns the pair."""
        survivor = self.inserted(
            "--into", "root", "--text", "The first clause.",
            "--why", "the half of the claim a merge will keep",
        )
        loser = self.inserted(
            "--after", survivor, "--text", "And the second clause.",
            "--why", "the half of the claim a merge will strand, which %s does "
                     "not state and which a reader needs" % survivor,
        )
        return survivor, loser

    def merge(self):
        """A real merge: `replace` takes both clauses onto the survivor, and
        `remove` retires the other. Returns (surviving id, stranded id)."""
        survivor, loser = self.two_halves()
        code, _, stderr = self.verb(
            "replace", survivor,
            "--text", "The first clause. And the second clause.",
            "--why", "takes on the clause node %s holds, so the claim reads as "
                     "the one claim it is" % loser,
        )
        self.assertEqual(0, code, stderr)
        code, _, stderr = self.verb(
            "remove", loser,
            "--why", "the one clause this node holds now stands word for word "
                     "inside node %s, so keeping it would assert the same thing "
                     "twice under two ids" % survivor,
        )
        self.assertEqual(0, code, stderr)
        return survivor, loser

    def test_the_node_born_in_a_split_records_nothing_about_where_it_came_from(self):
        retained, born = self.split()
        # One edit old, because it has been edited once. The commit that cut
        # the other half down is not in this node's history at all.
        self.assertEqual(1, len(self.edits(born)))
        self.assertEqual("insert", self.edits(born)[0][0])
        self.assertEqual("1", self.node(born).get("v"))
        self.assertEqual(1, len(self.history(born)))
        self.assertEqual([], [sha for sha in self.history(retained)
                              if sha in self.history(born)])

    def test_the_retained_side_of_a_split_keeps_every_reason_it_ever_had(self):
        retained, _ = self.split()
        self.assertEqual(
            ["insert", "replace"], [verb for verb, _ in self.edits(retained)]
        )
        self.assertEqual("2", self.node(retained).get("v"))

    def test_the_stranded_id_of_a_merge_still_answers_with_its_whole_life(self):
        survivor, stranded = self.merge()
        # Gone from the document — not in a node, not in an attribute, not in
        # any text — and still answering at exit 0 with the removal last.
        self.assertIsNone(self.node(stranded))
        with open(self.canvas_file(), "rb") as handle:
            self.assertNotIn(stranded.encode("utf-8"), handle.read())
        self.assertEqual(
            ["insert", "remove"], [verb for verb, _ in self.edits(stranded)]
        )
        # The shape is a live node's: the same header and the same blocks.
        code, stdout, stderr = self.run_canvas("history", "a-ledger-row", stranded)
        self.assertEqual(0, code, stderr)
        self.assertTrue(
            stdout.decode("utf-8").startswith("Canvas-Node: %s\n" % stranded)
        )
        # And an id that was never a node is still the other case entirely.
        code, _, _ = self.run_canvas("history", "a-ledger-row", "root")
        self.assertEqual(1, code)
        # The surviving side kept its id and its history spans the merge.
        self.assertEqual(
            ["insert", "replace"], [verb for verb, _ in self.edits(survivor)]
        )
        self.assertEqual("2", self.node(survivor).get("v"))

    def test_no_attribute_and_no_trailer_carries_the_pointer(self):
        retained, born = self.split()
        survivor, stranded = self.merge()
        # The document says nothing about lineage: a node carries its id and
        # the count of edits that named it, and there is nowhere else to look.
        for node_id in (retained, born, survivor):
            self.assertEqual(
                ["id", "v"], sorted(self.node(node_id).attrib), node_id
            )
        # Neither does a commit. Every edit commit carries the same three
        # trailers and names exactly one node, so an ancestor could only be
        # recorded by a commit naming two — which is the write the store
        # refuses for every caller.
        for body in self.bodies()[1:]:
            self.assertEqual(
                sorted(self.TRAILER_KEYS), sorted(set(self.trailer_keys(body))), body
            )
            self.assertEqual(1, body.count("Canvas-Node:"), body)
        # So the two halves of the merge share no commit: the pointer between
        # them exists only in the prose of the reasons, which is section 7's
        # ruling and the reason it is a convention and not a field.
        self.assertEqual([], [sha for sha in self.history(survivor)
                              if sha in self.history(stranded)])

    def test_a_merge_stopped_half_way_leaves_a_valid_canvas_and_true_histories(self):
        # Section 8's case: the state a run that dies mid-restructure leaves.
        # The exercise reached it for real — the survivor's replace landed and
        # the first remove was refused — so it is asserted here rather than
        # assumed. Coherent, legal, and every history true about how far it got.
        survivor, loser = self.two_halves()
        code, _, stderr = self.verb(
            "replace", survivor,
            "--text", "The first clause. And the second clause.",
            "--why", "takes on the clause node %s holds, so the claim reads as "
                     "the one claim it is" % loser,
        )
        self.assertEqual(0, code, stderr)

        before = self.state()
        code, _, stderr = self.verb("remove", loser, "--why", "Merged upward; reason as above.")
        self.assertEqual(2, code, stderr)
        self.assertEqual(before, self.state())

        self.assertEqual([], validate_file(self.canvas_file()))
        self.assertIsNotNone(self.node(loser))
        self.assertEqual(
            ["insert", "replace"], [verb for verb, _ in self.edits(survivor)]
        )
        self.assertEqual(["insert"], [verb for verb, _ in self.edits(loser)])
        # And the restructure finishes from here with one more command.
        code, _, stderr = self.verb(
            "remove", loser,
            "--why", "the one clause this node holds now stands word for word "
                     "inside node %s, so keeping it would assert the same thing "
                     "twice under two ids" % survivor,
        )
        self.assertEqual(0, code, stderr)
        self.assertIsNone(self.node(loser))


class RefusalSurface(object):
    """Everything the done condition asks of one refusal, as assertions.

    A mixin rather than a base test case, so that the classes checking two
    different families of refusal share the reading of the trailer block
    without inheriting each other's tests.
    """

    TRAILERS = ("Canvas-Node", "Canvas-About", "Canvas-Next", "Canvas-Exit")

    def surface(self, stderr):
        """The trailer block a refusal ends with, as a map of name -> values."""
        found = dict((name, []) for name in self.TRAILERS)
        for line in stderr.splitlines():
            for name in self.TRAILERS:
                if line.startswith("%s: " % name):
                    found[name].append(line.split(": ", 1)[1])
        return found

    def assertSurface(self, expected_code, code, stderr, msg=None, nodes=(),
                      about=(), next_action=()):
        """Everything the done condition asks of one refusal."""
        self.assertEqual(expected_code, code, "%s\n%s" % (msg, stderr))
        trailers = self.surface(stderr)
        # A concrete next action, exactly one, and not an empty one.
        self.assertEqual(1, len(trailers["Canvas-Next"]), "%s\n%s" % (msg, stderr))
        self.assertTrue(trailers["Canvas-Next"][0].strip(), msg)
        # The code, and what the code means, in band.
        self.assertEqual(1, len(trailers["Canvas-Exit"]), "%s\n%s" % (msg, stderr))
        self.assertTrue(
            trailers["Canvas-Exit"][0].startswith("%d " % code),
            "%s\n%s" % (msg, stderr),
        )
        self.assertIn("—", trailers["Canvas-Exit"][0], msg)
        # A refusal with no node names what it is about instead. Never neither.
        self.assertTrue(
            trailers["Canvas-Node"] or trailers["Canvas-About"],
            "%s\n%s" % (msg, stderr),
        )
        for node in nodes:
            self.assertIn(node, trailers["Canvas-Node"], "%s\n%s" % (msg, stderr))
        for thing in about:
            self.assertTrue(
                any(thing in each for each in trailers["Canvas-About"]),
                "%s\n%s" % (msg, stderr),
            )
        for phrase in next_action:
            self.assertIn(phrase, trailers["Canvas-Next"][0], "%s\n%s" % (msg, stderr))
        return trailers


class EveryRefusalNamesTheNodesAndTheNextAction(RefusalSurface, VerbTestCase):
    """The todo's done condition, verbatim: every refusal path in the tool
    prints the node ids involved and a concrete next action, and no refusal
    exits with an unexplained non-zero code.

    `engineering-spec.md` section *What to copy* takes IWE's error surface
    unconditionally — "a refusal names every node it matched and how to narrow,
    because an agent can act on that and cannot act on the word 'refused'" —
    and these are that sentence held to.

    These assert behaviour and not wording, like everything else here: that the
    ids that were on the command line are on `Canvas-Node:` lines, that there
    is a `Canvas-Next:` line and what it points at, that `Canvas-Exit:` carries
    the code the process actually exited with, and that the store did not move.
    """

    def section_with_children(self):
        section = self.inserted(
            "--into", "root", "--type", "section", "--title", "S",
            "--why", "a section to hold the options",
        )
        first = self.inserted("--into", section, "--text", "one", "--why", "one")
        second = self.inserted("--into", section, "--text", "two", "--why", "two")
        return section, first, second

    # -- the five families the todo names -------------------------------

    def test_an_absent_why_names_the_node_the_edit_was_for(self):
        # The family the todo names first, and argparse's own exit 2: the node
        # id was on the command line and the message never carried it.
        other = self.value_id
        for edit in (
            ("replace", self.problem_id, "--text", "restated"),
            ("remove", self.problem_id),
            ("move", self.problem_id, "--after", other),
            ("insert", "--into", "root", "--text", "a node"),
        ):
            before = self.state()
            code, stdout, stderr = self.verb(*edit)
            named = [each for each in edit[1:] if NODE_ID.match(each)]
            self.assertSurface(
                2, code, stderr, msg=edit, nodes=named,
                about=["ledger id a-ledger-row", "option --why"],
                next_action=["--why"],
            )
            self.assertEqual(b"", stdout, edit)
            self.assertEqual(before, self.state(), edit)

    def test_an_empty_why_names_the_node_the_edit_was_for(self):
        # The store's half of the same family. One family, one surface.
        for why in ("", "   ", "\t\n"):
            before = self.state()
            code, stdout, stderr = self.verb(
                "replace", self.problem_id, "--text", "restated", "--why", why
            )
            self.assertSurface(
                2, code, stderr, msg=why, nodes=[self.problem_id],
                about=["ledger id a-ledger-row", "option --why"],
                next_action=["--why"],
            )
            self.assertEqual(b"", stdout, why)
            self.assertEqual(before, self.state(), why)

    def test_a_schema_violation_names_the_node_and_points_at_the_schema(self):
        # The vocabulary is closed and is written in schema/canvas.rng alone,
        # so the next action points at the schema and does not restate it.
        before = self.state()
        code, stdout, stderr = self.verb(
            "insert", "--into", "root", "--type", "decision",
            "--text", "We chose A.", "--why", "settle it",
        )
        trailers = self.assertSurface(
            1, code, stderr, msg="decision",
            about=["state/canvas"],
            next_action=["schema/canvas.rng"],
        )
        # The node the refused write would have written, named as a node —
        # not only buried in the validator's diagnostic.
        self.assertEqual(1, len(trailers["Canvas-Node"]), stderr)
        minted = trailers["Canvas-Node"][0]
        self.assertTrue(NODE_ID.match(minted), minted)
        self.assertIn('id="%s"' % minted, stderr)
        self.assertEqual(b"", stdout)
        self.assertEqual(before, self.state())

    def test_a_two_node_edit_names_the_container_and_every_child(self):
        section, first, second = self.section_with_children()
        for edit in (
            ("replace", section, "--type", "text", "--text", "We chose A."),
            ("replace", section, "--text", "We chose A."),
            ("remove", section),
        ):
            before = self.state()
            code, stdout, stderr = self.verb(*(edit + ("--why", "settle it")))
            self.assertSurface(
                1, code, stderr, msg=edit,
                nodes=[section, first, second],
                about=["ledger id a-ledger-row"],
                next_action=["--why"],
            )
            self.assertEqual(b"", stdout, edit)
            self.assertEqual(before, self.state(), edit)

    def test_an_unknown_node_id_says_which_command_prints_the_real_ones(self):
        # "nothing was changed" is a fact about the past. The next action is
        # the command that hands back the ids that do exist.
        for edit in (
            ("replace", "zz99", "--text", "x", "--why", "w"),
            ("remove", "zz99", "--why", "w"),
            ("move", "zz99", "--after", self.value_id, "--why", "w"),
            ("move", self.problem_id, "--after", "zz99", "--why", "w"),
            ("insert", "--after", "zz99", "--text", "x", "--why", "w"),
            ("insert", "--into", "zz99", "--text", "x", "--why", "w"),
        ):
            before = self.state()
            code, stdout, stderr = self.verb(*edit)
            self.assertSurface(
                1, code, stderr, msg=edit, nodes=["zz99"],
                about=["ledger id a-ledger-row"],
                next_action=["bin/canvas read a-ledger-row"],
            )
            self.assertEqual(b"", stdout, edit)
            self.assertEqual(before, self.state(), edit)

    def test_history_of_an_unknown_node_says_which_command_prints_the_real_ones(self):
        code, stdout, stderr = self.run_canvas("history", "a-ledger-row", "zz99")
        self.assertSurface(
            1, code, stderr, msg="history", nodes=["zz99"],
            about=["ledger id a-ledger-row"],
            next_action=["bin/canvas read a-ledger-row"],
        )
        self.assertEqual(b"", stdout)

    def test_a_move_that_misses_names_the_node_being_moved_as_well(self):
        # Two nodes are involved and the refusal used to name only one of them.
        code, _, stderr = self.verb(
            "move", self.problem_id, "--after", "zz99", "--why", "w"
        )
        self.assertSurface(
            1, code, stderr, nodes=[self.problem_id, "zz99"],
            about=["ledger id a-ledger-row"],
        )

    def test_a_move_to_the_root_position_still_names_the_node_being_moved(self):
        # `--after root` is the one position that is not a node, so the
        # position side of this refusal has nothing to name and the whole
        # `Canvas-Node:` block used to be empty. The node being moved is in
        # hand all the same — `_addressed` matched it and `document.detach`
        # had already taken it out of the tree before `_place` refused — and
        # it is the thing the caller has to act on.
        before = self.state()
        code, stdout, stderr = self.verb(
            "move", self.problem_id, "--after", "root", "--why", "put it first"
        )
        trailers = self.assertSurface(
            1, code, stderr, nodes=[self.problem_id],
            about=["ledger id a-ledger-row", "position root"],
            next_action=["bin/canvas read a-ledger-row"],
        )
        # The moved node, and only it: root is a position and not a node, so
        # it stays on Canvas-About: where the rest of the tool puts it. An
        # equality and not an assertIn, because the failure this guards
        # against is the id going missing again.
        self.assertEqual([self.problem_id], trailers["Canvas-Node"], stderr)
        self.assertEqual(b"", stdout)
        self.assertEqual(before, self.state())

    def test_a_move_into_the_root_is_not_the_position_that_is_refused(self):
        # The other half of the pair, and why the refusal above is about the
        # position and not about the root: `--into root` is a real position
        # and it works. The next action the refusal prints is a true one.
        code, _, stderr = self.verb(
            "move", self.problem_id, "--into", "root", "--why", "put it last"
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(
            [self.value_id, self.problem_id],
            [child.get("id") for child in self.tree()],
        )

    def test_an_insert_that_misses_names_the_position_and_not_a_minted_id(self):
        # The deliberate other half of the same decision, pinned so that a
        # later change cannot make it by accident. `insert`'s node is minted
        # moments before `_place` and has never been in the canvas: no commit
        # names it, `bin/canvas read` cannot show it, `bin/canvas history` has
        # nothing for it, and the next attempt mints a different one. It is
        # not printed under `Canvas-Node:`, which means "a node of this
        # canvas" everywhere else in the tool. The refusal names the ledger id
        # and the position instead — never nothing.
        for edit, named in (
            (("insert", "--after", "root", "--text", "x"), []),
            (("insert", "--after", "zz99", "--text", "x"), ["zz99"]),
            (("insert", "--into", "zz99", "--text", "x"), ["zz99"]),
        ):
            before = self.state()
            code, stdout, stderr = self.verb(*(edit + ("--why", "w")))
            trailers = self.assertSurface(
                1, code, stderr, msg=edit, nodes=named,
                about=["ledger id a-ledger-row", "position"],
                next_action=["bin/canvas read a-ledger-row"],
            )
            self.assertEqual(named, trailers["Canvas-Node"], stderr)
            self.assertEqual(b"", stdout, edit)
            self.assertEqual(before, self.state(), edit)

    def test_the_library_copy_of_the_position_refusal_names_the_same_nodes(self):
        # `_one_position` is `bin/canvas`'s required mutually-exclusive group
        # written again for `from canvas import store`, and it had the same
        # omission one call earlier: `move` holds the node id and did not hand
        # it over. argparse intercepts both routes before the store sees them,
        # so this is reachable through the import path alone — and the import
        # path is a supported surface, so its refusal names what the command
        # line's names.
        from canvas import store

        before = self.state()
        for after, into in ((None, None), (self.value_id, "root")):
            with self.assertRaises(store.ToolProblem) as caught:
                store.move(
                    "a-ledger-row", self.problem_id, "w", after=after, into=into
                )
            self.assertIn(self.problem_id, caught.exception.nodes)
            self.assertNotIn("root", caught.exception.nodes)
            self.assertIn("ledger id a-ledger-row", caught.exception.about)
        self.assertEqual(before, self.state())

    def test_the_stale_base_branch_names_the_node_the_ledger_and_both_shas(self):
        base = self.read_sha()
        code, _, stderr = self.verb(
            "replace", self.problem_id, "--text", "theirs", "--why", "they revised it"
        )
        self.assertEqual(0, code, stderr)
        before = self.state()
        code, stdout, stderr = self.verb(
            "replace", self.problem_id, "--text", "mine", "--why", "mine",
            "--base", base,
        )
        self.assertSurface(
            1, code, stderr, nodes=[self.problem_id],
            about=[
                "ledger id a-ledger-row",
                "option --base %s" % base,
                "the head",
            ],
            next_action=["bin/canvas read a-ledger-row", "--base"],
        )
        # The diff is still handed back: the branch's whole point.
        self.assertIn("diff --git", stderr)
        self.assertEqual(b"", stdout)
        self.assertEqual(before, self.state())

    def test_a_base_that_is_not_an_ancestor_names_the_node_and_the_two_shas(self):
        # The third of the three ways a --base can be unusable, and the one
        # that needs a commit nothing here descends from to reach at all.
        tree = self.git("rev-parse", "HEAD^{tree}").strip()
        orphan = self.git(
            "-c", "user.name=test", "-c", "user.email=test@localhost",
            "commit-tree", "-m", "an orphan", tree,
        ).strip()
        before = self.state()
        code, stdout, stderr = self.verb(
            "replace", self.problem_id, "--text", "x", "--why", "w",
            "--base", orphan,
        )
        self.assertSurface(
            1, code, stderr, nodes=[self.problem_id],
            about=["ledger id a-ledger-row", "option --base %s" % orphan,
                   "the head"],
            next_action=["bin/canvas read a-ledger-row"],
        )
        self.assertEqual(b"", stdout)
        self.assertEqual(before, self.state())

    def read_sha(self):
        code, stdout, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code, stderr)
        return stdout.decode("utf-8").splitlines()[0].split(": ", 1)[1]

    # -- and every other refusal the command line can reach --------------

    def test_every_refusal_the_command_line_reaches_prints_the_whole_shape(self):
        """The done condition applied to the whole inventory, not five of it.

        Each of these is a refusal a caller can reach without tampering with
        the repository. Every one has to exit with the code its kind exits
        with, name something, say what to do, and say what its code means.
        """
        section, first, _ = self.section_with_children()
        for expected, args in (
            # argparse's own eight.
            (2, ()),
            (2, ("frobnicate", "a-ledger-row")),
            (2, ("read",)),
            (2, ("history", "a-ledger-row")),
            (2, ("read", "a-ledger-row", "--nope")),
            (2, ("create", "b-row", "--expected-value", "V")),
            (2, ("insert", "a-ledger-row", "--after", first, "--into", "root",
                 "--why", "w")),
            (2, ("insert", "a-ledger-row", "--why", "w", "--text", "x")),
            # The store's, exit 2: the invocation or the environment.
            (2, ("read", "../../../etc/passwd")),
            (2, ("read", ".hidden")),
            (2, ("replace", "a-ledger-row", first, "--text", "x", "--why", "w",
                 "--base", "not-a-sha")),
            # The store's, exit 1: true statements about the store.
            (1, ("create", "a-ledger-row", "--problem", "P",
                 "--expected-value", "V")),
            (1, ("read", "no-such-row")),
            (1, ("history", "no-such-row", "zz99")),
            (1, ("history", "a-ledger-row", "zz99")),
            (1, ("replace", "a-ledger-row", "root", "--text", "x", "--why", "w")),
            (1, ("remove", "a-ledger-row", "root", "--why", "w")),
            (1, ("replace", "a-ledger-row", "zz99", "--text", "x", "--why", "w")),
            (1, ("insert", "a-ledger-row", "--into", "zz99", "--text", "x",
                 "--why", "w")),
            (1, ("insert", "a-ledger-row", "--after", "zz99", "--text", "x",
                 "--why", "w")),
            (1, ("insert", "a-ledger-row", "--into", "root", "--type", "decision",
                 "--text", "x", "--why", "w")),
            (1, ("replace", "a-ledger-row", section, "--type", "text",
                 "--text", "x", "--why", "w")),
            (1, ("remove", "a-ledger-row", section, "--why", "w")),
            (1, ("move", "a-ledger-row", section, "--into", first, "--why", "w")),
            (1, ("move", "a-ledger-row", section, "--after", "zz99", "--why", "w")),
            (1, ("replace", "a-ledger-row", first, "--text", "x", "--why", "w",
                 "--base", "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")),
            (1, ("insert", "a-ledger-row", "--after", "root", "--text", "x",
                 "--why", "w")),
        ):
            before = self.state()
            code, stdout, stderr = self.run_canvas(*args)
            self.assertSurface(expected, code, stderr, msg=args)
            self.assertEqual(b"", stdout, args)
            self.assertEqual(before, self.state(), args)

    def test_a_read_of_an_invalid_stored_document_explains_its_own_exit(self):
        # The one non-zero exit that is not an exception, and the easiest to
        # miss: the document is printed and the exit code is 1 all the same.
        path = self.canvas_file()
        with open(path, "r", encoding="utf-8") as handle:
            body = handle.read()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body.replace("<text", "<decision", 1).replace(
                "</text>", "</decision>", 1
            ))
        code, stdout, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertSurface(
            1, code, stderr, about=["ledger id a-ledger-row"],
            next_action=["schema/canvas.rng"],
        )
        # The document is still handed back: a caller cannot repair what it
        # cannot see.
        self.assertIn(b"<canvas", stdout)

    # -- the refusals that have no node, and must still name something ---

    def test_the_environment_refusals_name_the_thing_they_are_about(self):
        code, _, stderr = self.run_canvas(
            "read", "a-ledger-row", workspace=None
        )
        self.assertSurface(
            2, code, stderr, about=["OPENCLAW_WORKSPACE"],
            next_action=["OPENCLAW_WORKSPACE"],
        )
        not_a_directory = os.path.join(self.workspace, "a-file")
        with open(not_a_directory, "w", encoding="utf-8") as handle:
            handle.write("not a workspace\n")
        code, _, stderr = self.run_canvas(
            "read", "a-ledger-row", workspace=not_a_directory
        )
        self.assertSurface(
            2, code, stderr, about=["OPENCLAW_WORKSPACE", not_a_directory],
            next_action=["OPENCLAW_WORKSPACE"],
        )

    def without(self, missing, *args, **kwargs):
        """Run bin/canvas with `missing` and nothing else off PATH.

        Only the one binary goes missing: with both gone, whichever the verb
        reaches first is the one that refuses, and the test would not be
        about the one it names.
        """
        empty = tempfile.mkdtemp(prefix="canvas-store-test-no-%s-" % missing)
        self.addCleanup(shutil.rmtree, empty, True)
        for tool in ("git", "xmllint"):
            if tool != missing:
                os.symlink(shutil.which(tool), os.path.join(empty, tool))
        environment = dict(
            os.environ,
            OPENCLAW_WORKSPACE=kwargs.pop("workspace", self.workspace),
            PATH=empty,
        )
        result = subprocess.run(
            [sys.executable, CANVAS] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        return result.returncode, result.stderr.decode("utf-8", "replace")

    def test_a_missing_git_names_git_and_says_what_to_do_on_every_verb(self):
        # `create` used to run `git init` outside the path that catches a
        # missing git, so it came out as a traceback and Python's exit 1 —
        # where README's table says a missing git is exit 2. An agent
        # following the documented contract would have re-read and re-decided
        # forever over a tool that is simply not installed.
        # A workspace with no canvas repository at all, so that `create`
        # really reaches `git init` rather than finding a repository already
        # there and never running it.
        fresh = tempfile.mkdtemp(prefix="canvas-store-test-fresh-")
        self.addCleanup(shutil.rmtree, fresh, True)
        for workspace, args in (
            (self.workspace, ("history", "a-ledger-row", self.problem_id)),
            (self.workspace, ("read", "a-ledger-row")),
            (self.workspace, ("replace", "a-ledger-row", self.problem_id,
                              "--text", "x", "--why", "w")),
            (fresh, ("create", "b-row", "--problem", "P",
                     "--expected-value", "V")),
        ):
            code, stderr = self.without("git", *args, workspace=workspace)
            self.assertNotIn("Traceback", stderr, args)
            self.assertSurface(
                2, code, stderr, msg=args, about=["command git"],
                next_action=["git"],
            )

    def test_a_missing_xmllint_names_the_validator_and_says_what_to_do(self):
        code, stderr = self.without(
            "xmllint", "replace", "a-ledger-row", self.problem_id,
            "--text", "x", "--why", "w",
        )
        self.assertNotIn("Traceback", stderr)
        self.assertSurface(
            2, code, stderr, about=["command xmllint"], next_action=["xmllint"],
        )

    # -- and the rule itself, which the interpreter now keeps -------------

    def test_a_refusal_cannot_be_built_without_saying_what_to_do(self):
        from canvas import store

        for kind in (store.Refusal, store.ToolProblem):
            with self.assertRaises(TypeError):
                kind("something is wrong")
            with self.assertRaises(ValueError):
                kind("something is wrong", "", about=["ledger id a-ledger-row"])

    def test_a_refusal_cannot_be_built_without_naming_something(self):
        from canvas import store

        # A refusal with no node is not an exemption: it names what it is
        # about instead, and "neither" is not a state it can be built in.
        for kind in (store.Refusal, store.ToolProblem):
            with self.assertRaises(ValueError):
                kind("something is wrong", "do this instead")
            kind("something is wrong", "do this instead", nodes=["ab2c"])
            kind("something is wrong", "do this instead", about=["ledger id x"])


class AnUnreadableCanvasIsARefusalAndNotATraceback(RefusalSurface, VerbTestCase):
    """An ordinary OS condition is a refusal in the same shape as every other.

    A canvas file this process cannot read, and a `state/canvas` it cannot
    write or look in, are conditions any real workspace produces: a file
    written by another user, a directory mounted read-only, a mode somebody
    tightened. `os.path.isfile` answers True for a mode-`000` file, so the "no
    such file" guard passes and the `open` after it used to raise — a raw
    traceback, Python's exit `1`, and none of the four trailers.

    Exit `2` and not `1` for each of them. `1` means "the request is wrong
    against the store as it stands; re-read and re-decide", and here the
    request was fine and the store is intact, so that advice invites a caller
    to retry something that will fail again in exactly the same way. `2` is
    "the tool or its environment is wrong; do not touch the canvas", which is
    what is true.

    Every test restores the mode it changed before it returns, so a failing
    assertion cannot leave an unreadable file or an undeletable directory
    behind for the tests that run after it.
    """

    def unreadable(self, path):
        """Make a file unreadable for the rest of this test, and no longer."""
        self.addCleanup(os.chmod, path, 0o644)
        os.chmod(path, 0o000)
        return path

    def unwritable(self, directory):
        """Make a directory readable but not writable, for this test only."""
        self.addCleanup(os.chmod, directory, 0o755)
        os.chmod(directory, 0o555)
        return directory

    def unlookable(self, directory):
        """Make a directory impossible to look in, for this test only."""
        self.addCleanup(os.chmod, directory, 0o755)
        os.chmod(directory, 0o000)
        return directory

    def validate(self, *paths):
        """Run bin/canvas-validate. Returns (exit code, stderr text)."""
        result = subprocess.run(
            [sys.executable, VALIDATE] + list(paths),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode, result.stderr.decode("utf-8", "replace")

    # -- store.read -------------------------------------------------------

    def test_read_of_an_unreadable_canvas_names_it_and_says_what_to_do(self):
        path = self.unreadable(self.canvas_file())
        code, _, stderr = self.verb("read")
        self.assertNotIn("Traceback", stderr)
        self.assertSurface(
            2, code, stderr, about=["ledger id a-ledger-row", path],
            next_action=["chmod"],
        )

    # -- store._open_canvas, via document.parse ---------------------------

    def test_every_editing_verb_refuses_an_unreadable_canvas(self):
        path = self.unreadable(self.canvas_file())
        for edit in (
            ("replace", self.problem_id, "--text", "restated", "--why", "w"),
            ("insert", "--after", self.problem_id, "--text", "new", "--why", "w"),
            ("remove", self.problem_id, "--why", "w"),
            ("move", self.problem_id, "--into", "root", "--why", "w"),
        ):
            code, _, stderr = self.verb(*edit)
            self.assertNotIn("Traceback", stderr, edit)
            self.assertSurface(
                2, code, stderr, msg=edit,
                about=["ledger id a-ledger-row", path], next_action=["chmod"],
            )

    # -- validate._wellformedness_problem ---------------------------------

    def test_canvas_validate_of_an_unreadable_file_is_exit_two(self):
        # README section *Validating a file by hand* and `validate_file`'s own
        # docstring have both always promised exit 2 for a file "missing or
        # unreadable". The missing half was true; the unreadable half was a
        # traceback and exit 1.
        path = self.unreadable(self.canvas_file())
        code, stderr = self.validate(path)
        self.assertNotIn("Traceback", stderr)
        self.assertSurface(
            2, code, stderr, about=["file %s" % path], next_action=["chmod"],
        )

    # -- store._write_and_commit ------------------------------------------

    def test_a_write_into_an_unwritable_directory_names_the_node(self):
        directory = self.unwritable(self.canvas_dir)
        before = self.state()
        code, _, stderr = self.verb(
            "replace", self.problem_id, "--text", "restated", "--why", "w"
        )
        self.assertNotIn("Traceback", stderr)
        self.assertSurface(
            2, code, stderr, nodes=[self.problem_id],
            about=[self.canvas_file(), directory], next_action=["chmod"],
        )
        self.assertEqual(before, self.state())

    # -- store.preflight ---------------------------------------------------

    def test_create_into_an_unwritable_directory_refuses_in_the_same_shape(self):
        directory = self.unwritable(self.canvas_dir)
        code, _, stderr = self.run_canvas(
            "create", "b-row", "--problem", "P", "--expected-value", "V"
        )
        self.assertNotIn("Traceback", stderr)
        self.assertSurface(
            2, code, stderr, about=[self.canvas_file("b-row"), directory],
            next_action=["chmod"],
        )

    # -- store._no_canvas, when the absence cannot be trusted --------------

    def test_a_directory_it_cannot_look_in_is_not_reported_as_no_canvas(self):
        # `os.path.isfile` answers False here too, and "no canvas for that
        # ledger id" would be a false statement carrying a next action —
        # create it — that would make things worse rather than better.
        directory = self.unlookable(self.canvas_dir)
        for args in (
            ("read",),
            ("replace", self.problem_id, "--text", "x", "--why", "w"),
            ("history", self.problem_id),
        ):
            code, _, stderr = self.verb(*args)
            self.assertNotIn("Traceback", stderr, args)
            self.assertSurface(
                2, code, stderr, msg=args, about=[directory],
                next_action=["chmod"],
            )

    def test_a_canvas_that_is_genuinely_absent_is_still_exit_one(self):
        # The control for the test above: the distinction it draws has to
        # leave the ordinary case exactly where README's table puts it.
        code, _, stderr = self.run_canvas("read", "no-such-row")
        self.assertSurface(
            1, code, stderr, about=["ledger id no-such-row"],
            next_action=["create"],
        )

    # -- validate_file, for the same distinction ---------------------------

    def test_canvas_validate_tells_absent_from_impossible_to_look_for(self):
        directory = self.unlookable(self.canvas_dir)
        code, stderr = self.validate(self.canvas_file())
        self.assertNotIn("Traceback", stderr)
        self.assertSurface(
            2, code, stderr, about=[directory], next_action=["chmod"],
        )

    # -- store._one_node_only, which no command line can reach -------------

    def test_the_one_node_check_refuses_a_canvas_it_cannot_re_read(self):
        # Defence in depth for the library API. From a command line
        # `_open_canvas` has already read the file by the time this runs, so
        # the only ways here are a file that becomes unreadable mid-write and
        # a caller reaching past `bin/canvas` — and neither may traceback.
        from canvas import store

        path = self.unreadable(self.canvas_file())
        root = document.new_canvas("a-ledger-row")
        with self.assertRaises(store.ToolProblem) as caught:
            store._one_node_only(path, root, self.problem_id)
        self.assertEqual([self.problem_id], caught.exception.nodes)
        self.assertTrue(caught.exception.next_action.strip())


class NoOSConditionLeavesTheToolAsATracebackOrALie(RefusalSurface, VerbTestCase):
    """The class, not the instances: no OS condition at any depth.

    Three rounds of this work each closed the conditions they were handed and
    each were shown a new one — the canvas file's own mode, then its
    directory's, then its *grand*parent's. The reason is that a guard which
    asks the filesystem a question and acts on the answer is an enumeration,
    and an enumeration can always be extended by one directory. So these tests
    do not enumerate either: `test_every_verb_survives_every_ancestor` walks
    the whole chain from the canvas file to the workspace and asserts the
    surface holds at every one of them, which is a claim a later change can
    re-run rather than take on trust.

    Every test restores the modes it set in a `finally`, so a failing
    assertion cannot leave an unreadable directory behind and break the tests
    that run after it — or defeat `shutil.rmtree` in the fixture's cleanup.
    """

    #: The canvas file, the repository beside it, then every directory above
    #: it up to the workspace. The order is deepest first, which is the order
    #: the four earlier rounds of this work discovered them in. `.git` is on
    #: the chain because the round before this one walked the directories and
    #: not the repository, and the store reads both.
    def chain(self):
        return [
            self.canvas_file(),
            os.path.join(self.canvas_dir, ".git"),
            self.canvas_dir,
            os.path.join(self.workspace, "state"),
            self.workspace,
        ]

    #: Sentences that assert a definite fact about the store: that a node was
    #: never there, that a repository is empty or absent, that a path is not a
    #: directory. Each is a statement about something the process *looked at*
    #: and found. Under a blocked ancestor nothing was looked at, the store is
    #: whole, and so every one of them is false — which is the defect that
    #: `assertConforms` cannot see, because a lie in the right shape has a
    #: `Canvas-Next:`, a `Canvas-Exit:` and no traceback exactly like the
    #: truth does.
    DEFINITE_CLAIMS = (
        "was never a node of this canvas",
        "has no commits",
        "is not a git repository",
        "no canvas for ledger id",
        "names nothing that exists",
        "is not a directory",
    )

    def at_mode(self, path, mode):
        """Set a mode for the duration of a `with` block, and put it back."""
        original = stat.S_IMODE(os.stat(path).st_mode)
        os.chmod(path, mode)
        return original

    def validate(self, *paths):
        """Run bin/canvas-validate. Returns (exit code, stderr text)."""
        result = subprocess.run(
            [sys.executable, VALIDATE] + list(paths),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode, result.stderr.decode("utf-8", "replace")

    def invocations(self):
        """Every verb of bin/canvas, with arguments that reach the store."""
        return [
            ("read", "a-ledger-row"),
            ("history", "a-ledger-row", self.problem_id),
            ("replace", "a-ledger-row", self.problem_id, "--text", "x",
             "--why", "w"),
            ("insert", "a-ledger-row", "--after", self.problem_id,
             "--text", "x", "--why", "w"),
            ("remove", "a-ledger-row", self.problem_id, "--why", "w"),
            ("move", "a-ledger-row", self.problem_id, "--into", "root",
             "--why", "w"),
            ("create", "b-row", "--problem", "P", "--expected-value", "V"),
        ]

    def assertConforms(self, code, stderr, msg):
        """Non-zero, no traceback, and the two lines a caller acts on."""
        self.assertNotIn("Traceback (most recent call last)", stderr, msg)
        self.assertNotEqual(0, code, "%s\n%s" % (msg, stderr))
        trailers = self.surface(stderr)
        self.assertEqual(1, len(trailers["Canvas-Next"]), "%s\n%s" % (msg, stderr))
        self.assertTrue(trailers["Canvas-Next"][0].strip(), msg)
        self.assertEqual(1, len(trailers["Canvas-Exit"]), "%s\n%s" % (msg, stderr))
        self.assertTrue(
            trailers["Canvas-Exit"][0].startswith("%d " % code),
            "%s\n%s" % (msg, stderr),
        )
        self.assertTrue(
            trailers["Canvas-Node"] or trailers["Canvas-About"],
            "%s\n%s" % (msg, stderr),
        )
        return trailers

    # -- the adversarial one: every verb against every ancestor ------------

    def walk(self, mode):
        """Every verb, and canvas-validate, against every ancestor at `mode`.

        Nothing here may traceback, whatever it exits, and everything that
        refuses must refuse in the shape. A command that *succeeds* is not a
        failure of this test and must not be asserted into one: `history`
        reads the git log and not the canvas file, so it answers correctly
        with that file at mode `000`, and demanding a non-zero exit there
        would be demanding a bug. What is demanded instead is that `read`,
        which cannot avoid the file, refuses at every position — that is the
        tooth in this test, and it is what stops the whole thing passing
        vacuously if the tool started exiting 0 everywhere.
        """
        for blocked in self.chain():
            original = self.at_mode(blocked, mode)
            try:
                for args in self.invocations():
                    code, _, stderr = self.run_canvas(*args)
                    self.assertNotIn(
                        "Traceback (most recent call last)", stderr,
                        (blocked, args),
                    )
                    if code != 0:
                        self.assertConforms(code, stderr, (blocked, args))
                code, stderr = self.validate(self.canvas_file())
                self.assertNotIn(
                    "Traceback (most recent call last)", stderr,
                    (blocked, "canvas-validate"),
                )
                if code != 0:
                    self.assertConforms(code, stderr, (blocked, "validate"))
            finally:
                os.chmod(blocked, original)

    def test_every_verb_survives_every_ancestor(self):
        """The canvas file and every directory above it, mode 000 in turn.

        Twenty-eight commands of `bin/canvas` and four of
        `bin/canvas-validate`, and not one of them a traceback or an
        unexplained exit code.
        """
        self.walk(0o000)

    def test_every_verb_survives_every_ancestor_unwritable(self):
        """The same chain, readable but not writable."""
        self.walk(0o555)

    def test_no_blocked_ancestor_makes_the_tool_state_a_falsehood(self):
        """The second tooth: the refusal has to be *true*, not merely shaped.

        `walk` asks whether the output conforms, and a false statement conforms
        as readily as a true one — which is how three rounds of this passed
        their own surface tests while the tool told callers that a node three
        commits name had never existed and that a repository with three commits
        in it had none. So this asserts on the content: the store here is whole
        and only a mode changed, therefore no refusal may claim that anything
        in it is absent, empty or the wrong kind of thing. Every such sentence
        is a thing the process would have had to look at to know, and it looked
        at nothing.
        """
        for blocked in self.chain():
            original = self.at_mode(blocked, 0o000)
            try:
                for args in self.invocations():
                    code, _, stderr = self.run_canvas(*args)
                    if code == 0:
                        continue
                    for claim in self.DEFINITE_CLAIMS:
                        self.assertNotIn(claim, stderr, (blocked, args, claim))
                code, stderr = self.validate(self.canvas_file())
                if code != 0:
                    for claim in self.DEFINITE_CLAIMS:
                        self.assertNotIn(claim, stderr, (blocked, "validate", claim))
            finally:
                os.chmod(blocked, original)

    # -- the repository, which the round before this one did not walk ------

    def test_a_base_is_not_called_unknown_by_a_repository_it_cannot_read(self):
        # `rev-parse --verify --quiet <sha>` exits 1 for a revision that is not
        # there and 128 for a repository it could not open, and "--base was
        # never handed out here" is a finding about a history that was read.
        # From a command line `head_sha` refuses first, so this is defence in
        # depth for the library API, for the window where the repository stops
        # being readable between the two calls, and for the next edit that
        # changes the order and quietly re-opens the hole.
        from canvas import store

        base = self.git("rev-parse", "HEAD").strip()
        git_dir = os.path.join(self.canvas_dir, ".git")
        original = self.at_mode(git_dir, 0o000)
        try:
            with self.assertRaises(store.ToolProblem) as caught:
                store._resolve_base(
                    self.canvas_dir, base, base, "a-ledger-row", self.problem_id
                )
        finally:
            os.chmod(git_dir, original)
        message = caught.exception.args[0]
        self.assertIn("cannot tell", message)
        self.assertNotIn("never handed out here", message)
        self.assertTrue(caught.exception.next_action.strip())

    def test_an_unreadable_repository_is_not_reported_as_having_no_commits(self):
        # `git rev-parse HEAD` exits 128 on an unborn branch and on a `.git`
        # it may not read, so `head_sha` used to answer None for both and
        # `read` announced that a repository with commits in it had none. The
        # next action it gave — create the first canvas — fails in turn.
        git_dir = os.path.join(self.canvas_dir, ".git")
        original = self.at_mode(git_dir, 0o000)
        try:
            code, _, stderr = self.verb("read")
            self.assertConforms(code, stderr, "read with .git unreadable")
            self.assertEqual(2, code, stderr)
            self.assertNotIn("has no commits", stderr)
            self.assertIn("cannot tell", stderr)
            self.assertIn("errno 13 EACCES", stderr)
        finally:
            os.chmod(git_dir, original)
        # The repair the refusal named, carried out: the same command works.
        code, stdout, stderr = self.verb("read")
        self.assertEqual(0, code, stderr)
        self.assertIn(b"<canvas", stdout)

    def test_an_unreadable_repository_does_not_deny_a_node_ever_existed(self):
        # The same None, reached through `_log`'s empty-history branch. An
        # empty log was read as "no commit names this id", and the id it
        # denied is one the canvas is made of.
        git_dir = os.path.join(self.canvas_dir, ".git")
        original = self.at_mode(git_dir, 0o000)
        try:
            code, _, stderr = self.verb("history", self.problem_id)
            self.assertConforms(code, stderr, "history with .git unreadable")
            self.assertEqual(2, code, stderr)
            self.assertNotIn("was never a node of this canvas", stderr)
            self.assertNotIn("no node with id", stderr)
            self.assertIn("cannot tell", stderr)
        finally:
            os.chmod(git_dir, original)
        # And the node was there the whole time.
        code, stdout, stderr = self.verb("history", self.problem_id)
        self.assertEqual(0, code, stderr)
        self.assertIn(self.problem_id.encode(), stdout)

    #: Everything inside `.git` that the store's reads depend on. Checking the
    #: mode of `.git` itself was a check at a fixed depth, and this whole
    #: surface exists because a check at a fixed depth can be defeated by going
    #: one deeper: with `.git` readable and `refs/heads` at `000`, git finds no
    #: ref and reports it exactly as it reports an unborn branch.
    INSIDE_THE_REPOSITORY = ("refs/heads", "refs", "objects", "HEAD", "config")

    def test_nothing_unreadable_inside_the_repository_is_read_as_emptiness(self):
        """The fifth instance of the same lie, one level inside `.git`.

        `_illegible` walks the whole of `.git` rather than asking after its top
        level, so the answer does not depend on the depth somebody happened to
        think of. Where git declines to answer and the walk finds anything it
        cannot read, the tool says it cannot tell.
        """
        git_dir = os.path.join(self.canvas_dir, ".git")
        for inside in self.INSIDE_THE_REPOSITORY:
            target = os.path.join(git_dir, inside)
            if not os.path.exists(target):
                continue
            original = self.at_mode(target, 0o000)
            try:
                for args in (("read",), ("history", self.problem_id)):
                    code, _, stderr = self.verb(*args)
                    if code == 0:
                        # git did not need it. Nothing was claimed, so there is
                        # nothing here that can be false.
                        continue
                    self.assertConforms(code, stderr, (inside, args))
                    self.assertEqual(2, code, "%s %s\n%s" % (inside, args, stderr))
                    for claim in self.DEFINITE_CLAIMS:
                        self.assertNotIn(claim, stderr, (inside, args, claim))
                    self.assertIn("cannot tell", stderr)
            finally:
                os.chmod(target, original)

    def test_the_repair_named_for_something_inside_the_repository_works(self):
        # The next action has to name the thing that is actually refusing, and
        # running it has to make the same command succeed. `refs/heads` is two
        # levels below the `.git` the old check looked at.
        target = os.path.join(self.canvas_dir, ".git", "refs", "heads")
        original = self.at_mode(target, 0o000)
        try:
            code, _, stderr = self.verb("read")
            self.assertEqual(2, code, stderr)
            next_action = self.surface(stderr)["Canvas-Next"][0]
            self.assertIn("chmod u+rx %s" % target, next_action)
        finally:
            os.chmod(target, original)
        code, stdout, stderr = self.verb("read")
        self.assertEqual(0, code, stderr)
        self.assertIn(b"<canvas", stdout)

    # -- above the workspace, which no chain rooted at it can reach ---------

    def nested_workspace(self):
        """A workspace some directories down inside its own tempdir.

        The fixture's workspace sits directly in `$TMPDIR`, and a test may not
        chmod that — so the only way to block something *above* a workspace is
        to build one with ancestors of its own. Every one of them is restored
        in the caller's `finally`, and the whole tree is removed by cleanup.
        """
        root = tempfile.mkdtemp(prefix="canvas-above-test-")
        self.addCleanup(shutil.rmtree, root, True)
        workspace = os.path.join(root, "a", "b", "c", "ws")
        os.makedirs(workspace)
        code, _, stderr = self.run_canvas(
            "create", "a-ledger-row", "--problem", "P",
            "--expected-value", "V",
            workspace=workspace,
        )
        self.assertEqual(0, code, stderr)
        return root, workspace

    def test_an_unreadable_ancestor_above_the_workspace_is_not_a_falsehood(self):
        """`os.path.isdir` said the workspace was not a directory when `ls -ld`
        showed that it was, because the mode that refused the look was three
        levels above it. `bin/canvas-validate` got this right and `bin/canvas`
        did not, so one store had two answers."""
        root, workspace = self.nested_workspace()
        for depth in ("a", os.path.join("a", "b"), os.path.join("a", "b", "c")):
            blocked = os.path.join(root, depth)
            original = self.at_mode(blocked, 0o000)
            try:
                code, _, stderr = self.run_canvas(
                    "read", "a-ledger-row", workspace=workspace
                )
                self.assertConforms(code, stderr, blocked)
                self.assertEqual(2, code, "%s\n%s" % (blocked, stderr))
                self.assertNotIn("is not a directory", stderr)
                self.assertIn("cannot tell", stderr)
                self.assertIn("errno 13 EACCES", stderr)
                # The repair names the shallowest blocked directory, not the
                # workspace, because `chmod` on the workspace cannot be run.
                next_action = self.surface(stderr)["Canvas-Next"][0]
                self.assertIn("chmod u+rx %s" % blocked, next_action)
            finally:
                os.chmod(blocked, original)
        # Nothing above it blocked any more: the store was whole all along.
        code, stdout, stderr = self.run_canvas(
            "read", "a-ledger-row", workspace=workspace
        )
        self.assertEqual(0, code, stderr)
        self.assertIn(b"<canvas", stdout)

    def test_every_verb_survives_every_ancestor_above_the_workspace(self):
        """The whole matrix again, above the workspace this time."""
        root, workspace = self.nested_workspace()
        for depth in ("a", os.path.join("a", "b"), os.path.join("a", "b", "c")):
            blocked = os.path.join(root, depth)
            original = self.at_mode(blocked, 0o000)
            try:
                for args in self.invocations():
                    code, _, stderr = self.run_canvas(
                        *args, workspace=workspace
                    )
                    self.assertNotIn(
                        "Traceback (most recent call last)", stderr,
                        (blocked, args),
                    )
                    if code != 0:
                        self.assertConforms(code, stderr, (blocked, args))
                        for claim in self.DEFINITE_CLAIMS:
                            self.assertNotIn(claim, stderr, (blocked, args, claim))
            finally:
                os.chmod(blocked, original)

    def test_a_read_refuses_at_every_blocked_ancestor(self):
        """The tooth in `walk`: `read` has to open the canvas *and* ask the
        repository for the sha it prints, so an unreachable file, an
        unreachable `.git` or an unreachable directory anywhere above them is
        a refusal — never a success, and never exit 1, which would tell a
        caller the request was wrong when the store was fine and the process
        could not see it.

        `bin/canvas-validate` is held to the same bar on everything it reads,
        which is the document and not the repository: it is asked whether one
        file conforms to the schema, it never opens `.git`, and demanding that
        it fail over a repository it has no business in would be demanding a
        bug.
        """
        git_dir = os.path.join(self.canvas_dir, ".git")
        for blocked in self.chain():
            original = self.at_mode(blocked, 0o000)
            try:
                code, _, stderr = self.verb("read")
                self.assertEqual(2, code, "%s\n%s" % (blocked, stderr))
                self.assertConforms(code, stderr, blocked)
                if blocked == git_dir:
                    continue
                code, stderr = self.validate(self.canvas_file())
                self.assertEqual(2, code, "%s\n%s" % (blocked, stderr))
                self.assertConforms(code, stderr, blocked)
            finally:
                os.chmod(blocked, original)

    # -- the lie the last round of this was caught by ----------------------

    def test_an_unreadable_grandparent_is_not_reported_as_no_canvas(self):
        # The canvas is there and unchanged. `os.path.isdir` answers False for
        # `state/canvas` when `state` is unreadable, which is what made the
        # one-level guard miss this and report the canvas absent at exit 1.
        state = os.path.join(self.workspace, "state")
        original = self.at_mode(state, 0o000)
        try:
            for args in (("read",), ("history", self.problem_id),
                         ("replace", self.problem_id, "--text", "x", "--why", "w")):
                code, _, stderr = self.verb(*args)
                self.assertConforms(code, stderr, args)
                self.assertEqual(2, code, "%s\n%s" % (args, stderr))
                self.assertNotIn("no canvas for ledger id", stderr)
                self.assertIn("cannot tell", stderr)
                # The errno, so a caller can tell a mode from a missing file.
                self.assertIn("errno 13 EACCES", stderr)
        finally:
            os.chmod(state, original)

    def test_the_next_action_names_the_directory_that_actually_refuses(self):
        # The heart of it: `chmod u+rx <the canvas file>` is not a command a
        # caller can run when the mode that refuses it is two levels up, so
        # the refusal names the shallowest ancestor instead — and running that
        # repair makes the very same command succeed.
        state = os.path.join(self.workspace, "state")
        original = self.at_mode(state, 0o000)
        try:
            code, _, stderr = self.verb("read")
            next_action = self.surface(stderr)["Canvas-Next"][0]
            self.assertIn("chmod u+rx %s" % state, next_action)
            self.assertNotIn("chmod u+rx %s" % self.canvas_file(), next_action)
        finally:
            os.chmod(state, original)
        # The repair the refusal named, carried out.
        code, stdout, stderr = self.verb("read")
        self.assertEqual(0, code, stderr)
        self.assertIn(b"<canvas", stdout)

    def test_canvas_validate_tells_absent_from_cannot_look_at_any_depth(self):
        state = os.path.join(self.workspace, "state")
        original = self.at_mode(state, 0o000)
        try:
            code, stderr = self.validate(self.canvas_file())
            self.assertConforms(code, stderr, "validate under a blocked state/")
            self.assertEqual(2, code, stderr)
            self.assertNotIn("no such file", stderr)
            self.assertIn("cannot tell", stderr)
        finally:
            os.chmod(state, original)

    # -- something is there, and it is not a canvas ------------------------

    def test_a_directory_where_a_canvas_belongs_is_not_reported_as_absent(self):
        # "nothing at <path>" is false, and its next action — create it —
        # refuses in turn with a different message at a different code.
        os.mkdir(self.canvas_file("d-row"))
        code, _, stderr = self.run_canvas("read", "d-row")
        self.assertConforms(code, stderr, "read of a directory")
        self.assertEqual(2, code, stderr)
        self.assertNotIn("nothing at", stderr)
        self.assertIn("a directory", stderr)

    def test_canvas_validate_of_a_directory_says_so(self):
        os.mkdir(self.canvas_file("d-row"))
        code, stderr = self.validate(self.canvas_file("d-row"))
        self.assertConforms(code, stderr, "validate of a directory")
        self.assertEqual(2, code, stderr)
        self.assertNotIn("no such file", stderr)

    def test_a_canvas_directory_that_is_a_file_is_not_reported_as_absent(self):
        # ENOTDIR, which no `chmod` repairs — so the next action must not be
        # the permission one.
        workspace = tempfile.mkdtemp(prefix="canvas-store-test-")
        self.addCleanup(shutil.rmtree, workspace, True)
        os.mkdir(os.path.join(workspace, "state"))
        with open(os.path.join(workspace, "state", "canvas"), "w") as handle:
            handle.write("not a directory\n")
        code, _, stderr = self.run_canvas(
            "read", "a-ledger-row", workspace=workspace
        )
        self.assertConforms(code, stderr, "state/canvas is a file")
        self.assertIn("errno 20 ENOTDIR", stderr)
        self.assertIn("is not a directory", self.surface(stderr)["Canvas-Next"][0])

    def test_canvas_validate_through_a_path_that_is_not_a_directory(self):
        inside = os.path.join(self.canvas_file(), "inner.xml")
        code, stderr = self.validate(inside)
        self.assertConforms(code, stderr, "validate through a file")
        self.assertEqual(2, code, stderr)
        self.assertIn("errno 20 ENOTDIR", stderr)

    # -- a broken pipe, which is an OSError like any other -----------------

    def test_a_reader_that_closes_early_is_a_refusal_and_not_a_traceback(self):
        # `bin/canvas read <id> | head -1` on a canvas that fits in the pipe
        # buffer exits 0 and always has. On one that does not, the write to
        # stdout raised BrokenPipeError out of `_read` — a traceback, and
        # Python's exit 1, which README gives to "the request is wrong against
        # the store as it stands".
        code, _, stderr = self.verb(
            "replace", self.problem_id, "--text", "x" * 300000, "--why", "big"
        )
        self.assertEqual(0, code, stderr)
        self.assertGreater(os.path.getsize(self.canvas_file()), 128 * 1024)
        producer = subprocess.Popen(
            [sys.executable, CANVAS, "read", "a-ledger-row"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(os.environ, OPENCLAW_WORKSPACE=self.workspace),
        )
        reader = subprocess.Popen(
            ["head", "-1"], stdin=producer.stdout, stdout=subprocess.DEVNULL
        )
        producer.stdout.close()
        reader.wait()
        stderr = producer.stderr.read().decode("utf-8", "replace")
        producer.stderr.close()
        producer.wait()
        self.assertConforms(producer.returncode, stderr, "read | head -1")
        self.assertIn("errno 32 EPIPE", stderr)
        # And no `Exception ignored in: <_io.BufferedWriter ...>` after it,
        # which would be a traceback by another name below the refusal.
        self.assertNotIn("Exception ignored", stderr)

    # -- the boundary itself, as a unit ------------------------------------

    def test_every_errno_produces_a_next_action_that_names_the_path(self):
        from canvas import refusal

        # Including one this tool has never met: the guarantee is that there
        # is no errno without a conforming refusal, not that somebody listed
        # them all.
        unknown = 7654
        for number in list(refusal._OS_NEXT_ACTION) + [unknown, None]:
            error = OSError(number, "some condition", self.canvas_file())
            built = refusal.from_os_error(
                refusal.Refused, error, about=["ledger id a-ledger-row"]
            )
            self.assertTrue(built.next_action.strip(), number)
            self.assertTrue(built.about, number)
            # The errno travels, because it is the only thing that tells a
            # permission problem from a missing one.
            self.assertTrue(
                any(each.startswith("errno ") for each in built.about), number
            )

    def test_an_os_error_carrying_two_paths_names_both(self):
        from canvas import refusal

        # `rename` and `link` fail on a pair, and naming only the first sends
        # a caller to look at the wrong end of it.
        error = OSError(18, "Cross-device link", "/one", None, "/two")
        built = refusal.from_os_error(refusal.Refused, error)
        self.assertIn("path /one", built.about)
        self.assertIn("path /two", built.about)

    # -- the same distinction on the one guard no command line reaches ----

    def test_the_one_node_check_tells_absent_from_cannot_look(self):
        # Defence in depth for the library API, and the last site in the store
        # that inferred absence from `os.path.isfile` alone. From a command
        # line `_open_canvas` has already read the file by the time this runs,
        # so the ways here are a mode set mid-write and a caller reaching past
        # `bin/canvas` — and neither may be told the canvas is absent when it
        # is there and this process may not look.
        from canvas import store

        root = document.new_canvas("a-ledger-row")
        state = os.path.join(self.workspace, "state")
        original = self.at_mode(state, 0o000)
        try:
            with self.assertRaises(store.ToolProblem) as caught:
                store._one_node_only(self.canvas_file(), root, self.problem_id)
        finally:
            os.chmod(state, original)
        self.assertEqual([self.problem_id], caught.exception.nodes)
        self.assertIn("is unknown", str(caught.exception))
        self.assertTrue(
            any(each.startswith("errno ") for each in caught.exception.about)
        )
        # And the control: genuinely absent is still the Refusal it was.
        with self.assertRaises(store.Refusal):
            store._one_node_only(
                self.canvas_file("no-such-row"), root, self.problem_id
            )

    def test_the_one_node_check_refuses_a_directory_at_the_canvas_path(self):
        from canvas import store

        root = document.new_canvas("a-ledger-row")
        os.mkdir(self.canvas_file("d-row"))
        with self.assertRaises(store.ToolProblem) as caught:
            store._one_node_only(self.canvas_file("d-row"), root, self.problem_id)
        self.assertIn("a directory", str(caught.exception))
        self.assertEqual([self.problem_id], caught.exception.nodes)

    def test_the_blocking_ancestor_is_the_shallowest_one(self):
        from canvas import refusal

        state = os.path.join(self.workspace, "state")
        original = self.at_mode(state, 0o000)
        try:
            # `state/canvas` is fine; `state` is not, and it is `state` that
            # has to be repaired before anything below it can be looked at.
            self.assertEqual(state, refusal.blocking_ancestor(self.canvas_file()))
        finally:
            os.chmod(state, original)
        self.assertIsNone(refusal.blocking_ancestor(self.canvas_file()))


class EveryRefusalIsTrueAndItsNextActionRuns(RefusalSurface, VerbTestCase):
    """The todo's done condition as an invariant the repository re-runs.

    Four rounds of this work each closed a refusal and each were shown one
    more, because the guarantee was being checked by somebody imagining a
    counterexample and the checking stopped when the imagining did. "Every
    refusal path" is a universal claim and cannot be discharged that way. So it
    is written here instead, against the refusal families `README.md` and the
    todo description both name, as assertions a later change has to keep
    passing rather than an opinion somebody formed once.

    For each refusal it covers:

    - the process exits non-zero with one of the two codes `README.md` section
      *Exit codes* documents — it says plainly there are two and no third, so
      a `3` is a defect however good its message is;
    - stderr carries `Canvas-Next:` and `Canvas-Exit:` and no traceback;
    - the node ids are named where nodes are involved;
    - **every fact it asserts about the store is true**, and **every repair it
      names actually succeeds when run**.

    The last two are the part shape-checking cannot see: a refusal that says
    "the canvas is there and unchanged" over an errno meaning it is gone, and
    tells the caller to `chmod` a file that does not exist, has a
    `Canvas-Next:`, a `Canvas-Exit:` and no traceback exactly like a true one.
    """

    # ------------------------------------------------------------------
    # The bar
    # ------------------------------------------------------------------

    #: The whole documented set. `README.md`: "There are two, and there is no
    #: third." A refusal outside it is unexplained by construction, because the
    #: table a caller reads has no row for it.
    DOCUMENTED_EXITS = (1, 2)

    #: A repair, as a `Canvas-Next:` writes one: a command introduced by the
    #: word `run`. `README.md` section *What a refusal prints* settles the rule
    #: this encodes — a next action **may** name a command that exits non-zero,
    #: because a refusal about a path that is gone has to be able to tell a
    #: caller to look at it and every way of looking at a path that is gone
    #: exits non-zero; what it may not do is *claim* one. The claim is the
    #: repair, the repair is the command the line says to `run`, and that one
    #: has to exit `0` when run exactly as printed.
    #:
    #: The lookbehind is what keeps `re-run` — which ends every template — from
    #: being read as a repair marker.
    REPAIR = re.compile(r"(?<![-\w])run `([^`]+)`")

    #: Every command a next action names, marked or not. Used only to check the
    #: rule in the other direction: see `CHMOD`.
    COMMAND = re.compile(r"`([^`]+)`")

    #: `chmod` is the one command in the surface that exists only to make the
    #: refused command work — `ls`, `df` and `ulimit` are there to show what
    #: state produced it — so a `chmod` that is *not* marked as a repair is the
    #: rule being escaped rather than an exception to it. This is what stops
    #: `assertRepairsRun` being satisfied by deleting the word `run`.
    CHMOD = re.compile(r"`(chmod \S+ [^`]+)`")

    #: The same escape, one punctuation mark cheaper: `CHMOD` only sees a
    #: `chmod` written inside backticks, so a next action that drops the
    #: backticks along with the word `run` slips past it. Every command this
    #: surface names is backticked, so a `chmod` found in the prose is that
    #: escape and not a command written some other legitimate way.
    BACKTICKED = re.compile(r"`[^`]*`")
    BARE_CHMOD = re.compile(r"\bchmod\b")

    #: A backticked `git …`, whatever is pinned in front of the subcommand.
    #: The reverse direction for `git`, which `git init` is the reason for:
    #: like `chmod`, it exists only to make something work and never to show
    #: what state produced a refusal, so an unmarked `git init` is the rule
    #: escaped rather than an exception to it.
    GIT = re.compile(r"`(git\b[^`]*)`")

    #: The git commands a next action may name *without* marking them, by
    #: subcommand — `assertRepairsRun`'s declared diagnostics.
    #:
    #: Deliberately the short list of the ones this surface actually names,
    #: and not a family: `git fsck`, `git cat-file` and `git show` would all
    #: read as diagnostics to anybody classifying by what a command does, and
    #: none of them is in here, so naming one in a next action fails until
    #: somebody adds it. That asymmetry with the forward direction is the
    #: point. Forward, the marker is syntactic and a repair nobody anticipated
    #: is covered the moment it is written, because the assertion can just run
    #: it and see. Backward there is nothing to run — "is this a diagnostic?"
    #: is a claim about intent — so the only honest form of the check is a
    #: list somebody decided, which a reviewer sees grow.
    GIT_DIAGNOSTICS = ("status", "rev-parse", "log")

    #: git's global options that take their value as the next word, so that
    #: word is not the subcommand. `--git-dir=…` and `--work-tree=…` carry
    #: theirs and need no entry.
    GIT_OPTIONS_WITH_A_VALUE = ("-C", "-c", "--git-dir", "--work-tree")

    #: A command with a placeholder in it is a *form* — `bin/canvas create
    #: <ledger-id> …` — and a form is never run as printed by anybody, so it is
    #: never marked as a repair. Asserted, not assumed: a marked repair that
    #: carried one would send a caller to run a command line that cannot work.
    PLACEHOLDER = re.compile(r"<[^`>]+>")

    #: Sentences that assert the canvas is still where the tool left it, and
    #: the `Canvas-About:` kinds that name the path they are asserting it of.
    PRESENCE_CLAIMS = ("the canvas is there", "the file is there")

    #: Sentences that assert the opposite. `\S+` runs to the end of the line
    #: because a path is the last thing on it.
    ABSENCE_CLAIMS = (
        re.compile(r"nothing at (\S+)"),
        re.compile(r"there is no canvas at (\S+)"),
    )

    def git_subcommand(self, command):
        """The subcommand of a backticked `git …`, past the pinning options.

        `canvas/store.py` pins every invocation with `--git-dir` and
        `--work-tree`, and `canvas/cli.py` uses `-C`, so the subcommand is
        never the second word and cannot be read off as one.
        """
        words = shlex.split(command)[1:]
        while words:
            if not words[0].startswith("-"):
                return words[0]
            words = (
                words[2:] if words[0] in self.GIT_OPTIONS_WITH_A_VALUE
                else words[1:]
            )
        return None

    def named_paths(self, trailers):
        """The paths a refusal named, by what it called them."""
        found = {}
        for thing in trailers["Canvas-About"]:
            kind, _, value = thing.partition(" ")
            found.setdefault(kind, []).append(value)
        return found

    def assertClaimsAreTrue(self, stderr, trailers, msg):
        """Whatever it said about the store, the store has to agree.

        Only the claims a refusal actually makes are checked: this asks the
        filesystem about the sentence that is printed, so a refusal that says
        nothing about presence has nothing here to fail.
        """
        paths = self.named_paths(trailers)
        subjects = paths.get("canvas", []) + paths.get("file", [])
        for claim in self.PRESENCE_CLAIMS:
            if claim in stderr:
                for path in subjects:
                    self.assertTrue(
                        os.path.exists(path),
                        "%s: said %r about %s, which is not there\n%s"
                        % (msg, claim, path, stderr),
                    )
        for pattern in self.ABSENCE_CLAIMS:
            for path in pattern.findall(stderr):
                self.assertFalse(
                    os.path.exists(path),
                    "%s: said nothing is at %s, and something is\n%s"
                    % (msg, path, stderr),
                )
        if "no canvas for ledger id" in stderr:
            for path in paths.get("canvas", []):
                self.assertFalse(
                    os.path.exists(path),
                    "%s: said there is no canvas, and %s is there\n%s"
                    % (msg, path, stderr),
                )

    def assertRepairsRun(self, trailers, msg):
        """Every command the next action says to `run` has to exit 0 when run.

        The rule `README.md` section *What a refusal prints* settles, enforced
        here rather than described: a `Canvas-Next:` **may** name a command
        that exits non-zero, and the word `run` is what marks the one it may
        not. This used to be a `chmod`-only exemption — the assertion ran the
        `chmod` a next action named and silently skipped every other command,
        because `ls -ld <a path that is gone>` exits `1` and there was no way
        to say that this was fine while `chmod u+r <a canvas that was removed>`
        exiting `1` was the defect. There is now: the first is a diagnostic and
        the line does not tell you to run it, the second is a repair and the
        line does.

        Five things are checked, and together they are the rule:

        - **every marked repair runs, whatever the command is.** Not a list of
          command names this assertion is allowed to execute — the marker is
          syntactic, so a template that adds a repair nobody here anticipated
          is covered the moment it is written.
        - **a marked repair carries no placeholder.** `bin/canvas create
          <ledger-id> …` is a form, it exits `2` run as printed, and marking it
          would be the same defect one level along.
        - **every `chmod` a next action names is marked.** Otherwise the rule
          is satisfied by deleting the word `run`, and the exemption comes back
          wearing a justification.
        - **no `chmod` is named outside backticks.** The check above reads a
          backticked `chmod`, so without this one the rule is satisfied by
          deleting the backticks as well as the word — a cheaper escape than
          the one that check exists to close.
        - **every backticked `git` a next action names is either marked or
          declared.** The same reverse direction, for the family the store's
          refusals are built out of: `git init` is never a diagnostic, so an
          unmarked one is the rule escaped, and every other git command a next
          action wants to name unmarked is named in `GIT_DIAGNOSTICS` where a
          reviewer sees it. Only backticked, because "git" is an ordinary word
          in these sentences — `canvas/store.py` says "git has to be able to
          create `.git` inside it" and means the program, not a command line —
          whereas "chmod" is only ever a command.

        Modes are put back afterwards, so a test that sets one up to be refused
        is not quietly repaired by the assertion that checks it.
        """
        next_action = trailers["Canvas-Next"][0]
        repairs = self.REPAIR.findall(next_action)
        for command in repairs:
            self.assertFalse(
                self.PLACEHOLDER.search(command),
                "%s: `%s` is marked as a repair and has a placeholder in it, "
                "so it cannot be run as printed" % (msg, command),
            )
            argv = shlex.split(command)
            self.assertTrue(
                argv, "%s: `%s` is marked as a repair and is not a command"
                % (msg, command),
            )
            paths = [word for word in argv[1:] if word.startswith("/")]
            for path in paths:
                self.assertTrue(
                    os.path.exists(path),
                    "%s: named `%s` as the repair, and %s is not there"
                    % (msg, command, path),
                )
                # Safety, asserted rather than assumed: nothing outside a
                # temporary directory this test made is ever touched.
                self.assertTrue(
                    path.startswith(tempfile.gettempdir())
                    or path.startswith(self.workspace),
                    "%s: refusing to run `%s` against %s, which is not under "
                    "a tempdir" % (msg, command, path),
                )
            modes = [(path, stat.S_IMODE(os.stat(path).st_mode)) for path in paths]
            result = subprocess.run(
                argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                self.assertEqual(
                    0, result.returncode,
                    "%s: `%s` is named as the repair and exited %d: %s"
                    % (msg, command, result.returncode,
                       result.stderr.decode("utf-8", "replace")),
                )
            finally:
                for path, mode in modes:
                    os.chmod(path, mode)
        for command in self.CHMOD.findall(next_action):
            self.assertIn(
                command, repairs,
                "%s: named `%s` without telling the caller to run it. A chmod "
                "is a repair, and a repair is marked `run `%s``, so that the "
                "caller can tell it from the diagnostics beside it and this "
                "assertion can run it\n%s" % (msg, command, command, next_action),
            )
        prose = self.BACKTICKED.sub("", next_action)
        self.assertFalse(
            self.BARE_CHMOD.search(prose),
            "%s: named a chmod with no backticks around it, where the check "
            "above cannot see it. Every command this surface names is "
            "backticked, and a chmod is a repair, so it is written "
            "`run `chmod <mode> <path>``\n%s" % (msg, next_action),
        )
        for command in self.GIT.findall(next_action):
            if command in repairs:
                continue
            subcommand = self.git_subcommand(command)
            self.assertIn(
                subcommand, self.GIT_DIAGNOSTICS,
                "%s: named `%s` without telling the caller to run it, and "
                "`git %s` is not one of this helper's declared diagnostics "
                "(%s). Either running it is what makes the refused command "
                "work — then it is a repair, the line says `run `%s``, and "
                "this assertion runs it — or it is there to show the state "
                "that produced the refusal, and it goes in GIT_DIAGNOSTICS "
                "where adding it is a decision somebody made rather than a "
                "word somebody dropped\n%s"
                % (msg, command, subcommand, ", ".join(self.GIT_DIAGNOSTICS),
                   command, next_action),
            )

    def assertActionable(self, code, stderr, msg, nodes=()):
        """The done condition, for one refusal."""
        self.assertNotIn("Traceback (most recent call last)", stderr, msg)
        self.assertNotEqual(0, code, "%s\n%s" % (msg, stderr))
        self.assertIn(
            code, self.DOCUMENTED_EXITS,
            "%s: exited %d, and README documents only %s\n%s"
            % (msg, code, ", ".join(str(each) for each in self.DOCUMENTED_EXITS),
               stderr),
        )
        trailers = self.surface(stderr)
        self.assertEqual(1, len(trailers["Canvas-Next"]), "%s\n%s" % (msg, stderr))
        self.assertTrue(trailers["Canvas-Next"][0].strip(), msg)
        self.assertEqual(1, len(trailers["Canvas-Exit"]), "%s\n%s" % (msg, stderr))
        self.assertTrue(
            trailers["Canvas-Exit"][0].startswith("%d " % code),
            "%s\n%s" % (msg, stderr),
        )
        self.assertIn("—", trailers["Canvas-Exit"][0], msg)
        self.assertTrue(
            trailers["Canvas-Node"] or trailers["Canvas-About"],
            "%s\n%s" % (msg, stderr),
        )
        for node in nodes:
            self.assertIn(node, trailers["Canvas-Node"], "%s\n%s" % (msg, stderr))
        self.assertClaimsAreTrue(stderr, trailers, msg)
        self.assertRepairsRun(trailers, msg)
        return trailers

    def validate(self, *paths):
        """Run bin/canvas-validate. Returns (exit code, stderr text)."""
        result = subprocess.run(
            [sys.executable, VALIDATE] + list(paths),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode, result.stderr.decode("utf-8", "replace")

    # ------------------------------------------------------------------
    # The six families the todo description names
    # ------------------------------------------------------------------

    def test_the_schema_violation(self):
        code, stderr = self.validate(
            os.path.join(ROOT, "tests", "fixtures", "unknown-node.xml")
        )
        self.assertEqual(1, code, stderr)
        self.assertActionable(code, stderr, "a document the schema rejects")
        # The offending node is named in band, which is what an agent narrows
        # with. `unknown-node.xml` carries one, and the diagnostic quotes it.
        self.assertIn('id="jc5v"', stderr)

    def test_the_missing_why(self):
        for args in (
            ("replace", self.problem_id, "--text", "x"),
            ("remove", self.problem_id),
            ("insert", "--after", self.problem_id, "--text", "x"),
            ("move", self.problem_id, "--into", "root"),
        ):
            code, _, stderr = self.verb(*args)
            self.assertActionable(code, stderr, ("no --why", args))

    def test_the_two_node_edit(self):
        """Both shapes: two ids in one invocation, and one edit that would
        reach a second node — a container turned into a leaf, or removed,
        while it has children. `node-identity.md` §5 is what refuses the
        second, and it has to name every child it would have touched."""
        section = self.inserted(
            "--into", "root", "--type", "section", "--title", "Options",
            "--why", "the options",
        )
        first = self.inserted("--into", section, "--text", "A", "--why", "a")
        second = self.inserted("--into", section, "--text", "B", "--why", "b")
        for edit, named, mentioned in (
            (("replace", first, second, "--text", "both"), [first], [second]),
            (("remove", first, second), [first], [second]),
            (("move", first, second, "--into", "root"), [first], [second]),
            (("replace", section, "--type", "text", "--text", "A."),
             [section, first, second], []),
            (("remove", section), [section, first, second], []),
        ):
            code, _, stderr = self.verb(*(edit + ("--why", "settle them")))
            self.assertActionable(
                code, stderr, ("two nodes", edit), nodes=named
            )
            # The second id is the argument that was rejected rather than a
            # node of the edit, so it is named in the message and the next
            # action — "drop <it> and re-run" — and not on a `Canvas-Node:`.
            for node in mentioned:
                self.assertIn(node, stderr, ("two nodes", edit))

    def test_the_unknown_node_id(self):
        for args in (
            ("replace", "zz99", "--text", "x", "--why", "w"),
            ("remove", "zz99", "--why", "w"),
            ("move", "zz99", "--into", "root", "--why", "w"),
            ("insert", "--after", "zz99", "--text", "x", "--why", "w"),
            ("history", "zz99"),
        ):
            code, _, stderr = self.verb(*args)
            self.assertActionable(code, stderr, ("no such node", args), nodes=["zz99"])

    def test_the_stale_base(self):
        code, stdout, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code, stderr)
        base = stdout.decode("utf-8").splitlines()[0].split(": ", 1)[1]
        # Somebody else moves the node this write declared a base for.
        code, _, stderr = self.verb(
            "replace", self.problem_id, "--text", "Theirs.", "--why", "theirs"
        )
        self.assertEqual(0, code, stderr)
        code, _, stderr = self.verb(
            "replace", self.problem_id, "--text", "Ours.", "--why", "ours",
            "--base", base,
        )
        self.assertActionable(
            code, stderr, "a --base the node moved since", nodes=[self.problem_id]
        )

    def test_the_os_conditions(self):
        """A mode on the canvas, and a mode on the directory it is written in.

        The repair each names is run by `assertRepairsRun`, which is the whole
        point of holding these to the same bar as the rest: `chmod` is the
        refusal's own claim about what would make the command work.
        """
        for blocked, args in (
            (self.canvas_file(), ("read",)),
            (self.canvas_file(), ("replace", self.problem_id, "--text", "x",
                                  "--why", "w")),
            (self.canvas_dir, ("replace", self.problem_id, "--text", "x",
                               "--why", "w")),
        ):
            original = stat.S_IMODE(os.stat(blocked).st_mode)
            os.chmod(blocked, 0o500 if blocked == self.canvas_dir else 0o000)
            try:
                code, _, stderr = self.verb(*args)
                self.assertActionable(code, stderr, (blocked, args))
                self.assertEqual(2, code, "%s %s\n%s" % (blocked, args, stderr))
            finally:
                os.chmod(blocked, original)

    # ------------------------------------------------------------------
    # The race: the canvas removed between the check and the open
    # ------------------------------------------------------------------
    #
    # `os.path.isfile` answers, and the `open` or the `parse` that follows it
    # is a separate syscall — so a canvas removed in between raises `ENOENT`
    # where the guard above already decided the canvas was there. That errno
    # used to reach `_cannot_read`, which asserted "the canvas is there and
    # unchanged" and named `chmod u+r <it>`: the tool exited 2 claiming
    # presence one line under the errno that says absence, and the repair it
    # named exited 1. `README.md` maps `ENOENT` to exit 1 and to "there is
    # genuinely no canvas for that ledger id"; this is that, held to.

    RACE = (
        "import os, sys\n"
        "sys.path.insert(0, %(root)r)\n"
        "target = os.path.abspath(%(target)r)\n"
        "seen = [0]\n"
        "asked = os.path.isfile\n"
        "def vanishing(path):\n"
        "    answer = asked(path)\n"
        "    if answer and os.path.abspath(path) == target:\n"
        "        seen[0] += 1\n"
        "        if seen[0] == %(nth)d:\n"
        "            os.unlink(target)\n"
        "    return answer\n"
        "os.path.isfile = vanishing\n"
        "from canvas.%(module)s import main\n"
        "sys.exit(main(%(args)r))\n"
    )

    def raced(self, args, nth=1, target=None, module="cli", workspace=None):
        """Run an entry point with the canvas removed after the nth check.

        `nth` is not a way of naming one call site: it is how every call site
        is reached without this test having to know where they are. Whichever
        guard answers first, the one after it is the one that meets the errno.
        """
        environment = dict(os.environ)
        environment["OPENCLAW_WORKSPACE"] = workspace or self.workspace
        script = self.RACE % {
            "root": ROOT,
            "target": target or self.canvas_file(),
            "nth": nth,
            "module": module,
            "args": list(args),
        }
        result = subprocess.run(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        return (
            result.returncode,
            result.stdout,
            result.stderr.decode("utf-8", "replace"),
        )

    def test_a_canvas_removed_between_the_check_and_the_open_is_actionable(self):
        """Every entry point, at every check the canvas could vanish after.

        The canvas is put back between runs rather than recreated, because
        `create` refuses a ledger id the repository already has a commit for —
        and it is put back *after* the assertions, so the claims are checked
        against the store as it was when the refusal was printed.
        """
        with open(self.canvas_file(), "rb") as handle:
            intact = handle.read()
        for nth in (1, 2, 3):
            for args in (
                ["read", "a-ledger-row"],
                ["replace", "a-ledger-row", self.problem_id, "--text", "x",
                 "--why", "w"],
                ["remove", "a-ledger-row", self.problem_id, "--why", "w"],
                ["history", "a-ledger-row", self.problem_id],
            ):
                code, _, stderr = self.raced(args, nth=nth)
                try:
                    if code == 0:
                        # It never needed the file. Nothing was claimed, so
                        # there is nothing here that can be false — `history`
                        # reads the git log and not the canvas.
                        continue
                    self.assertActionable(code, stderr, (nth, args))
                finally:
                    if not os.path.exists(self.canvas_file()):
                        with open(self.canvas_file(), "wb") as handle:
                            handle.write(intact)

    def test_the_race_is_the_documented_no_canvas_and_not_a_permission_lie(self):
        """The case the last check reproduced, at the exit code README gives it.

        Exit `1`, because `README.md` section *Exit codes* puts "there is
        genuinely no canvas for that ledger id (the filesystem answered
        `ENOENT`, not that it would not say)" there — and this is that errno,
        arriving one syscall later than the check that would have caught it.
        And the next action is run, literally, and has to work.
        """
        code, _, stderr = self.raced(["read", "a-ledger-row"])
        self.assertEqual(1, code, stderr)
        trailers = self.assertActionable(code, stderr, "the ENOENT race")
        self.assertFalse(os.path.exists(self.canvas_file()))
        self.assertNotIn("the canvas is there", stderr)
        # The next action it names, run as it names it.
        next_action = trailers["Canvas-Next"][0]
        self.assertIn("bin/canvas create a-ledger-row", next_action)
        code, _, stderr = self.run_canvas(
            "create", "a-ledger-row", "--problem", "P", "--expected-value", "V"
        )
        self.assertEqual(0, code, stderr)
        code, stdout, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code, stderr)
        self.assertIn(b"<canvas", stdout)

    def test_the_same_race_under_the_validator_is_actionable(self):
        code, _, stderr = self.raced(
            [self.canvas_file()], module="validate"
        )
        self.assertActionable(code, stderr, "the ENOENT race, canvas-validate")
        self.assertNotIn("the file is there", stderr)

    # ------------------------------------------------------------------
    # The same race, one level up: the repository removed after the check
    # ------------------------------------------------------------------
    #
    # `is_repository` asks `os.stat(.git)` and `head_sha` runs `rev-parse`
    # after it, so a `state/canvas/.git` removed in between raises `ENOENT`
    # where the guard above already decided the repository was there — the
    # canvas file's race, one level up. `_cannot_read_repository` answered it
    # with "cannot tell whether there are any commits in <dir>" at an aftermath
    # of "what that repository holds is still unknown", one line under its own
    # `Canvas-About: errno 2 ENOENT`. Both sentences are false at that errno:
    # it can tell, and what the repository holds is nothing, because there is
    # no repository. The check one syscall earlier says exactly that, in
    # `_not_a_repository`, and the two have to agree — a caller must not be
    # able to read which side of a race it landed on out of what the tool said.
    #
    # They agree at exit `2`, not at `_cannot_read`'s `1`, and `README.md`
    # section *Exit codes* carries the reason: a canvas that is gone is one
    # file missing from an intact store, and a `state/canvas` that is gone is
    # the store. Exit `1` would also be false advice here, because a read never
    # initialises the repository, so the re-read it asks for raises this again.

    REPOSITORY_RACE = (
        "import os, shutil, sys\n"
        "sys.path.insert(0, %(root)r)\n"
        "target = os.path.abspath(%(target)r)\n"
        "seen = [0]\n"
        "asked = os.stat\n"
        "def vanishing(path, *a, **k):\n"
        "    answer = asked(path, *a, **k)\n"
        "    try:\n"
        "        same = os.path.abspath(path) == target\n"
        "    except TypeError:\n"
        "        same = False\n"
        "    if same:\n"
        "        seen[0] += 1\n"
        "        if seen[0] == 1:\n"
        "            shutil.rmtree(target)\n"
        "    return answer\n"
        "os.stat = vanishing\n"
        "from canvas.cli import main\n"
        "sys.exit(main(%(args)r))\n"
    )

    def raced_repository(self, args):
        """Run an entry point with `state/canvas/.git` removed after the check.

        `os.stat` rather than `os.path.isdir`, because `is_repository` asks
        `os.stat` outright — it needs `S_ISDIR` and not a boolean, so that a
        regular file where `.git` belongs is answered definitely rather than
        inferred.
        """
        environment = dict(os.environ)
        environment["OPENCLAW_WORKSPACE"] = self.workspace
        script = self.REPOSITORY_RACE % {
            "root": ROOT,
            "target": os.path.join(self.canvas_dir, ".git"),
            "args": list(args),
        }
        result = subprocess.run(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        return (
            result.returncode,
            result.stdout,
            result.stderr.decode("utf-8", "replace"),
        )

    def test_a_repository_removed_after_the_check_says_it_is_not_there(self):
        """The racy answer and the checked answer are the same answer.

        Both routes are run against the same store, in that order — the race
        is what removes `.git`, and the plain read after it is the check
        meeting the absence head-on. What each says is then compared, because
        the claim under test is not "this message is nice" but "these two
        cannot disagree".
        """
        code, _, raced = self.raced_repository(["read", "a-ledger-row"])
        self.assertFalse(os.path.exists(os.path.join(self.canvas_dir, ".git")))
        self.assertEqual(2, code, raced)
        self.assertActionable(code, raced, "the repository ENOENT race")

        # The two false sentences, named. They are what `ENOENT` reached
        # before, and neither is true of a repository that is not there.
        self.assertNotIn("cannot tell", raced)
        self.assertNotIn("what that repository holds is still unknown", raced)

        # What it says instead is what the check says, in the check's words.
        checked_code, _, checked = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(2, checked_code, checked)
        self.assertActionable(
            checked_code, checked, "the repository absent at the check"
        )
        claim = "%s is not a git repository" % self.canvas_dir
        self.assertIn(claim, raced)
        self.assertIn(claim, checked)
        self.assertIn("errno 2 ENOENT", raced)

        # And the repair it names is run, as it names it: `create` is the one
        # thing that initialises the repository, and the read after it works.
        self.assertIn("bin/canvas create", self.surface(raced)["Canvas-Next"][0])
        code, _, stderr = self.run_canvas(
            "create", "rebuilt", "--problem", "P", "--expected-value", "V"
        )
        self.assertEqual(0, code, stderr)
        code, stdout, stderr = self.run_canvas("read", "rebuilt")
        self.assertEqual(0, code, stderr)
        self.assertIn(b"<canvas", stdout)

    def test_a_repository_that_cannot_be_read_still_says_it_cannot_tell(self):
        """`EACCES` is the look failing, and that sentence is true of it.

        The half of `_cannot_read_repository` the errno rule leaves alone. It
        is asserted here so that "`ENOENT` says the repository is not there"
        cannot be satisfied by deleting the honest sentence for every errno.
        """
        git_dir = os.path.join(self.canvas_dir, ".git")
        original = stat.S_IMODE(os.stat(git_dir).st_mode)
        os.chmod(git_dir, 0o000)
        try:
            code, _, stderr = self.run_canvas("read", "a-ledger-row")
        finally:
            os.chmod(git_dir, original)
        self.assertEqual(2, code, stderr)
        self.assertIn("cannot tell whether there are any commits in", stderr)
        self.assertIn("errno 13 EACCES", stderr)
        self.assertNotIn("is not a git repository", stderr)

    # ------------------------------------------------------------------
    # The four refusals `canvas/store.py` raises when git itself refuses
    # ------------------------------------------------------------------
    #
    # `assertRepairsRun` only ever sees a next action some test actually
    # produced, so a branch no test enters is a branch the rule above is not
    # applied to. Four of them were exactly that: `_git_checked`,
    # `_cannot_read_repository`'s `complaint` arm, `ensure_repository` and
    # `_log` each printed "run `git …` yourself to see what it objects to",
    # which puts the marker in front of a command offered for *looking* — and
    # the suite was green with them in it because nothing reached them.
    # `README.md` section *What a refusal prints* carried them as a documented
    # exception for exactly as long as that was true.
    #
    # The four tests below are what stops it being true. Each builds the
    # condition its refusal is about — git refused to stage, git refused the
    # question, git refused to initialise, git refused to read the history —
    # runs a real entry point against it, and puts the answer through
    # `assertActionable`, which is how the next action reaches
    # `assertRepairsRun` and is held to the same rule a `canvas/refusal.py`
    # template is held to.
    #
    # Two of the four also close a defect the marker was hiding: `_git_checked`
    # and `_log` named a *bare* `git rev-parse HEAD` and `git log`, with no
    # `--git-dir`, against a module whose first invariant (`canvas/store.py`
    # lines 17-22) is that every git invocation is pinned. Run from anywhere
    # else those two answer about whatever repository the caller is standing
    # in, so they do not merely fail to be repairs — they can succeed and be
    # about the wrong repository. Each test asserts the pinning.

    def test_a_stage_git_refuses_names_the_repository_that_refused_it(self):
        """`_git_checked`: the command it names is the one that just failed.

        Its non-zero exit is the condition this refusal exists for, so it is a
        diagnostic however useful it is, and what git said about it is in the
        message already. What the line offers instead is the state of the
        repository — asked of *that* repository, which the bare `git rev-parse
        HEAD` it used to mark was not.
        """
        objects = os.path.join(self.canvas_dir, ".git", "objects")
        # Mode 0o500 on `objects` itself stops git *creating* a two-hex
        # subdirectory, but not writing into one the fixture's earlier commits
        # already made — and which of the 256 a blob lands in is the first byte
        # of its hash, which varies run to run because canvas node ids are
        # random (`canvas/store.py`, `mint()`). Sealing only `objects` therefore
        # left `git add` succeeding on about 9 runs in 256, with the refusal
        # arriving one step later from `git commit` and this test failing on an
        # assertion about `git add`. Seal every existing subdirectory too, so no
        # loose object can be written anywhere and `git add` is the step that is
        # always refused. All modes are restored in the `finally`.
        sealed = [objects] + [
            os.path.join(objects, name)
            for name in sorted(os.listdir(objects))
            if len(name) == 2
            and all(character in "0123456789abcdef" for character in name)
            and os.path.isdir(os.path.join(objects, name))
        ]
        original = [
            (directory, stat.S_IMODE(os.stat(directory).st_mode))
            for directory in sealed
        ]
        for directory in sealed:
            os.chmod(directory, 0o500)
        try:
            code, _, stderr = self.verb(
                "replace", self.problem_id,
                "--text", "The problem restated.", "--why", "the restatement",
            )
            self.assertEqual(2, code, stderr)
            self.assertActionable(code, stderr, "git refused to stage")
            # The condition names the command that failed and what git said.
            self.assertIn("git add -f --", stderr)
            next_action = self.surface(stderr)["Canvas-Next"][0]
            self.assertNotIn("run `git", next_action)
            self.assertIn(
                "`git --git-dir=%s --work-tree=%s status`"
                % (os.path.join(self.canvas_dir, ".git"), self.canvas_dir),
                next_action,
            )
        finally:
            for directory, mode in original:
                os.chmod(directory, mode)

    # ------------------------------------------------------------------
    # And what the store looks like after the two of them that renamed a
    # document onto the canvas before git was asked for anything
    # ------------------------------------------------------------------
    #
    # `assertActionable` holds a refusal to what it *says*. The three below
    # hold the two git refusals in the write path to what they *leave*, which
    # is the other half of the same rule: `canvas/store.py` says a refused
    # write leaves nothing behind, and the stage and the commit are the two
    # refusals that arrive with an edit already on the canvas's own path and
    # so are the only two that can make that sentence false.
    #
    # Not merely "uncommitted". The document the rename put there carries the
    # bumped `v`, and `node-identity.md` section 4 has `v` be the number of
    # commits whose `Canvas-Node:` trailer names the node — so each of the two
    # asserts that count directly, because it is the invariant a half-applied
    # edit breaks and the reason this is a defect rather than a tidiness.

    def object_directories(self):
        """`.git/objects` and every two-hex subdirectory already in it.

        The fixture `test_a_stage_git_refuses_names_the_repository_that_refused_it`
        records above, and its comment is where the reason lives: sealing
        `objects` alone leaves `git add` succeeding whenever the blob lands in
        a subdirectory the earlier commits already made, and the refusal then
        arrives one step later from `git commit`.
        """
        objects = os.path.join(self.canvas_dir, ".git", "objects")
        return [objects] + [
            os.path.join(objects, name)
            for name in sorted(os.listdir(objects))
            if len(name) == 2
            and all(character in "0123456789abcdef" for character in name)
            and os.path.isdir(os.path.join(objects, name))
        ]

    def sealed(self, directories):
        """Set each directory to mode 500. Returns what to put back."""
        original = [
            (directory, stat.S_IMODE(os.stat(directory).st_mode))
            for directory in directories
        ]
        for directory in directories:
            os.chmod(directory, 0o500)
        return original

    def assertTheLogHasIt(self, node_id, text, msg):
        """The store holds what the log holds, and holds nothing else.

        Everything a half-applied edit changes: the worktree against `HEAD`,
        the index, the head itself, the node's `v` against the number of
        commits that name it, what a `read` hands back, and whether a
        temporary was left beside the canvas.
        """
        self.assertEqual("", self.git("status", "--porcelain"), msg)
        self.assertEqual("", self.git("diff", "--cached", "--name-only"), msg)
        with open(self.canvas_file(), "rb") as handle:
            self.assertEqual(
                self.git("show", "HEAD:a-ledger-row.xml").encode("utf-8"),
                handle.read(),
                msg,
            )
        # node-identity.md section 4. The half-applied document said `v="2"`
        # for a node one commit names.
        self.assertEqual("1", self.node(node_id).get("v"), msg)
        self.assertEqual(1, len(self.history(node_id)), msg)
        self.assertEqual(
            [".git", "a-ledger-row.xml"],
            sorted(os.listdir(self.canvas_dir)),
            msg,
        )
        code, stdout, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code, stderr)
        self.assertIn(text.encode("utf-8"), stdout, msg)

    def test_a_refused_stage_leaves_the_canvas_as_the_log_has_it(self):
        """`git add` is asked for after the rename, so its refusal has an
        edited document on the canvas's own path to take back.

        Same fixture as the test above — the whole of `.git/objects` sealed —
        and where that one asks what the refusal says, this one asks what it
        left. Before the write path took the edit back, `git status
        --porcelain` here read ` M a-ledger-row.xml` and `bin/canvas read`
        handed back `v="2"` for a node one commit names, under the sha the
        canvas was at before the command.
        """
        before = self.state()
        head = self.git("rev-parse", "HEAD").strip()
        original = self.sealed(self.object_directories())
        try:
            code, _, stderr = self.verb(
                "replace", self.problem_id,
                "--text", "The problem restated.",
                "--why", "the restatement that carries this test to the stage",
            )
            self.assertEqual(2, code, stderr)
            trailers = self.assertActionable(
                code, stderr, "a refused stage", nodes=[self.problem_id]
            )
            # Refused at the stage, and not one step later at the commit.
            self.assertIn("git add -f --", stderr)
            # The refusal says which file was put back, and to what.
            next_action = trailers["Canvas-Next"][0]
            self.assertIn(self.canvas_file(), next_action)
            self.assertIn(head, next_action)
        finally:
            for directory, mode in original:
                os.chmod(directory, mode)

        self.assertEqual(head, self.git("rev-parse", "HEAD").strip())
        self.assertEqual(before, self.state())
        self.assertTheLogHasIt(
            self.problem_id, "The problem stated.", "a refused stage"
        )

    def test_a_refused_commit_leaves_the_canvas_and_the_index_as_the_log_has_them(self):
        """`git commit` is the second of the two, and the one that has an
        index to put back as well as a file.

        `.git/refs/heads` sealed rather than `.git/objects`, so the `add`
        succeeds and the commit is what cannot lock the ref. That is the whole
        difference and it is the point: before the write path took the edit
        back, `git status --porcelain` here read `M ` in the *first* column —
        staged — so a rollback that restored the worktree and forgot the index
        leaves exactly this case half applied, and that is what the index
        assertions in `assertTheLogHasIt` are for.
        """
        before = self.state()
        head = self.git("rev-parse", "HEAD").strip()
        original = self.sealed(
            [os.path.join(self.canvas_dir, ".git", "refs", "heads")]
        )
        try:
            code, _, stderr = self.verb(
                "replace", self.value_id,
                "--text", "The value restated.",
                "--why", "the restatement that carries this test past the stage",
            )
            self.assertEqual(2, code, stderr)
            trailers = self.assertActionable(
                code, stderr, "a refused commit", nodes=[self.value_id]
            )
            # Refused at the commit, and known to have got past the stage.
            self.assertIn("commit -q", stderr)
            self.assertNotIn("git add -f --", stderr)
            next_action = trailers["Canvas-Next"][0]
            self.assertIn(self.canvas_file(), next_action)
            self.assertIn(head, next_action)
        finally:
            for directory, mode in original:
                os.chmod(directory, mode)

        self.assertEqual(head, self.git("rev-parse", "HEAD").strip())
        self.assertEqual(before, self.state())
        self.assertTheLogHasIt(
            self.value_id, "The value expected.", "a refused commit"
        )

    def test_a_rollback_that_is_itself_refused_says_so_and_names_the_file(self):
        """The one branch that can leave a half-applied edit, and it admits it.

        Putting bytes back on a filesystem that has just refused this process
        is itself fallible, so `_take_back` returns what refused it instead of
        raising — a rollback that failed has to be reportable beside the
        refusal that caused it, not instead of it — and the refusal built from
        the two names both.

        Reached by calling the helper rather than through `bin/canvas`, because
        end to end it is unreachable: `os.replace` needs the canvas directory
        writable, so any mode that would refuse the restore would have refused
        the rename first, and nothing outside the process can change the mode
        between them. Nothing is mocked for it — a real directory at mode
        `500` refuses a real write, and the `git add` below really is refused.
        The class's own rule is why it is here at all: a branch no test enters
        is a branch the rule is not applied to.
        """
        path = self.canvas_file()
        with open(path, "rb") as handle:
            previous = handle.read()
        head = self.git("rev-parse", "HEAD").strip()

        os.chmod(self.canvas_dir, 0o500)
        try:
            failure = store._take_back(
                self.canvas_dir, path, previous, staged=False
            )
        finally:
            os.chmod(self.canvas_dir, 0o700)
        # Returned, not raised. Everything else here rests on that.
        self.assertIsInstance(failure, PermissionError)

        try:
            store._git_checked(
                self.canvas_dir, "add", "-f", "--",
                os.path.join(self.canvas_dir, "no-such-canvas.xml"),
            )
            self.fail("git staged a file that is not there")
        except store.ToolProblem as error:
            refused = error

        problem = store._refused_after_the_rename(
            refused, self.canvas_dir, path, head, previous, failure,
            node_id=self.problem_id,
        )
        stderr = "\n".join(
            refusal.lines(
                "canvas", problem, 2,
                "the tool or its environment is wrong; do not touch the canvas",
            )
        )
        trailers = self.assertActionable(
            2, stderr, "a rollback that was refused too", nodes=[self.problem_id]
        )
        # Both failures, in the message: git's, and the one putting it back.
        self.assertIn("git add -f --", stderr)
        self.assertIn("was refused too", stderr)
        # And the one branch that leaves a half-applied edit says so, names
        # the file it is on, and says what re-running does about it.
        next_action = trailers["Canvas-Next"][0]
        self.assertIn(path, next_action)
        self.assertIn("still holds the edit", next_action)
        self.assertIn(head, next_action)

    def test_a_question_git_refuses_says_it_cannot_tell_and_names_the_question(self):
        """`_cannot_read_repository`'s `complaint` arm: git declined to answer.

        Reached only where `_illegible` found nothing unreadable — the whole of
        `.git` can be read and git still refuses — so the repository is
        legible and the refusal is git's own. A repository declaring a format
        version from the future is that: every byte of it readable, and every
        command about it fatal.
        """
        with open(os.path.join(self.canvas_dir, ".git", "config"), "a") as handle:
            handle.write("[core]\n\trepositoryformatversion = 99\n")
        code, _, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(2, code, stderr)
        self.assertActionable(code, stderr, "git refused the question")
        self.assertIn("git refused the question", stderr)
        self.assertIn("Expected git repo version", stderr)
        next_action = self.surface(stderr)["Canvas-Next"][0]
        self.assertNotIn("run `git", next_action)
        self.assertIn(
            "`git --git-dir=%s rev-parse HEAD`"
            % os.path.join(self.canvas_dir, ".git"),
            next_action,
        )

    def test_a_repository_that_cannot_be_initialised_does_not_mark_git_init(self):
        """`ensure_repository`: the one of the four whose command is no
        diagnostic at all, and still not a repair.

        `git init` only ever changes something, so naming it unmarked would be
        the rule escaped rather than an exception to it — which is why
        `GIT_DIAGNOSTICS` has no entry for it and the line does not name it.
        Nor may it be marked: the command the marker would claim is the command
        that just failed, and it goes on failing for as long as the condition
        the refusal is about holds. That is measured here rather than argued,
        because it is the whole of the case — the todo this test comes from
        says `git init -b main` should keep the marker *if it can be made to
        exit `0` on the conditions that refusal is about*, and it cannot.
        """
        elsewhere = tempfile.mkdtemp(prefix="canvas-store-test-")
        self.addCleanup(shutil.rmtree, elsewhere, True)
        canvas_dir = os.path.join(elsewhere, "state", "canvas")
        os.makedirs(canvas_dir)
        original = stat.S_IMODE(os.stat(canvas_dir).st_mode)
        os.chmod(canvas_dir, 0o500)
        try:
            code, _, stderr = self.run_canvas(
                "create", "a-ledger-row",
                "--problem", "The problem.", "--expected-value", "The value.",
                workspace=elsewhere,
            )
            self.assertEqual(2, code, stderr)
            self.assertActionable(code, stderr, "git refused to initialise")
            self.assertIn("cannot initialise a git repository at", stderr)
            next_action = self.surface(stderr)["Canvas-Next"][0]
            self.assertNotIn("git init", next_action)
            self.assertIn("`ls -ld %s`" % canvas_dir, next_action)
            # The measurement, under the condition the refusal is about.
            attempt = subprocess.run(
                ["git", "init", "-b", "main", "--", canvas_dir],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertNotEqual(
                0, attempt.returncode,
                "`git init -b main -- %s` exited 0 against a directory this "
                "process may not write into, so it could be marked as the "
                "repair after all and this refusal should say so"
                % canvas_dir,
            )
        finally:
            os.chmod(canvas_dir, original)
        # And what the line asks for is what makes the refused command work.
        code, _, stderr = self.run_canvas(
            "create", "a-ledger-row",
            "--problem", "The problem.", "--expected-value", "The value.",
            workspace=elsewhere,
        )
        self.assertEqual(0, code, stderr)

    def test_a_history_git_refuses_names_the_repository_that_refused_it(self):
        """`_log`: `git log` bare was the same defect as `_git_checked`'s.

        This branch is the one `head_sha` has already cleared — it is reached
        only when the repository does have a head, so "no commits" is not the
        answer and the log genuinely could not be read. A head whose commit
        object this process may not open is exactly that: `rev-parse` answers
        from the ref and `log` cannot walk it.
        """
        head = self.git("rev-parse", "HEAD").strip()
        loose = os.path.join(
            self.canvas_dir, ".git", "objects", head[:2], head[2:]
        )
        original = stat.S_IMODE(os.stat(loose).st_mode)
        os.chmod(loose, 0o000)
        try:
            code, _, stderr = self.verb("history", self.problem_id)
            self.assertEqual(2, code, stderr)
            self.assertActionable(code, stderr, "git refused the history")
            self.assertIn("cannot search the canvas history for", stderr)
            next_action = self.surface(stderr)["Canvas-Next"][0]
            self.assertNotIn("run `git", next_action)
            self.assertIn(
                "`git --git-dir=%s --work-tree=%s log`"
                % (os.path.join(self.canvas_dir, ".git"), self.canvas_dir),
                next_action,
            )
        finally:
            os.chmod(loose, original)

    # ------------------------------------------------------------------
    # The errno nobody anticipated
    # ------------------------------------------------------------------

    def test_an_unclassified_errno_still_refuses_in_the_shape(self):
        """The reason this class kept producing one more instance was that the
        message was written beside the errno rather than derived from it, so an
        errno nobody had met inherited whichever sentence somebody wrote for
        the one they had. These are the two helpers asked directly, with an
        errno the table has never heard of."""
        from canvas import store

        error = OSError(4093, "Some condition from the future")
        error.filename = self.canvas_file()
        for refused in (
            store._cannot_read(self.canvas_file(), error, ledger_id="a-ledger-row"),
            store._cannot_write(self.canvas_file(), error),
        ):
            self.assertTrue(refused.next_action.strip())
            self.assertTrue(refused.nodes or refused.about)
            # It states the condition rather than guessing at a repair for it.
            self.assertIn("4093", "\n".join(refused.about))
            self.assertNotIn("chmod", refused.next_action)
            self.assertNotIn("the canvas is there", refused.next_action)


class FrozenCanvasTestCase(VerbTestCase):
    """A canvas with its two first nodes, and one command that ends it.

    The freeze is not made in `setUp`: the first clause is about the command
    that makes it, so each class below decides when its canvas ends.
    """

    #: A reason in the shape `guidelines/canvas-why.md` asks for: it says what
    #: this freeze is for and names its evidence, rather than pointing at a
    #: reason already given. The `done:` prefix is the convention README states
    #: and nothing enforces — one verb carries both endings, and which ending
    #: it was is a thing the reason says.
    REASON = (
        "done: the done-gate artifact is the What/Why/Evidence block on PR #21, "
        "merged 2026-09-23; nodes gjxb and qrpa carry the outcome"
    )

    def freeze(self, *args, **kwargs):
        """Run `freeze` against this canvas. Returns (code, out, err)."""
        ledger_id = kwargs.pop("ledger_id", "a-ledger-row")
        return self.run_canvas("freeze", ledger_id, *args)

    def froze(self, why=None):
        """Freeze this canvas, expecting it to work. Returns the freeze's sha."""
        code, stdout, stderr = self.freeze("--why", why or self.REASON)
        self.assertEqual(0, code, stderr)
        return stdout.decode("utf-8").splitlines()[1].split(": ", 1)[1]

    def document(self):
        with open(self.canvas_file(), "rb") as handle:
            return handle.read()

    def the_store(self):
        """`canvas.store`, with the workspace pointed at this test's own.

        Every in-process call below goes through `canvas_directory()`, which
        reads the environment, and the environment a developer runs the suite
        in may well point at the live workspace. Pointing it here — and putting
        it back afterwards — is what makes `LiveWorkspaceIsUntouched`'s promise
        hold for the import path as well as for the subprocess one.
        """
        self.assertTrue(
            self.workspace.startswith(tempfile.gettempdir()), self.workspace
        )
        previous = os.environ.get("OPENCLAW_WORKSPACE")
        os.environ["OPENCLAW_WORKSPACE"] = self.workspace
        if previous is None:
            self.addCleanup(os.environ.pop, "OPENCLAW_WORKSPACE", None)
        else:
            self.addCleanup(os.environ.__setitem__, "OPENCLAW_WORKSPACE", previous)
        from canvas import store

        return store


class FreezingACanvas(FrozenCanvasTestCase):
    """The done condition's first clause: one command freezes a canvas, taking
    `--why` like every other write, so the last thing in the canvas's history
    is the reason it ended.

    `engineering-spec.md` section *Lifecycle* is the sentence being made true:
    frozen at `done`, "and after it the canvas is read-only history", and
    "`abandoned` freezes it the same way, with the reason as the last edit". An
    edit in this store is a commit and a reason lives in the commit subject, so
    a freeze that is a commit is literally the last edit with the reason on it.
    """

    def test_freeze_exits_zero_and_reports_the_ledger_row_and_the_new_sha(self):
        code, stdout, stderr = self.freeze("--why", self.REASON)
        self.assertEqual(0, code, stderr)
        first, second = stdout.decode("utf-8").splitlines()
        self.assertEqual("Canvas-Freeze: a-ledger-row", first)
        self.assertTrue(second.startswith("Canvas-Base: "), second)
        self.assertTrue(SHA.match(second.split(": ", 1)[1]), second)

    def test_the_sha_it_reports_is_the_new_head(self):
        sha = self.froze()
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), sha)

    def test_the_last_commit_carries_the_freeze_trailer_for_this_ledger_row(self):
        sha = self.froze()
        self.assertIn(
            "Canvas-Freeze: a-ledger-row", self.bodies()[-1].splitlines()
        )
        self.assertEqual(sha, self.git("log", "-1", "--format=%H").strip())

    def test_the_reason_it_ended_is_the_subject_of_that_commit(self):
        # The same shape every other write has: `<verb> <subject>: <reason>`.
        self.froze()
        self.assertEqual(
            "freeze a-ledger-row: %s" % self.REASON, self.subjects()[-1]
        )

    def test_the_freeze_names_no_node_because_it_edits_none(self):
        self.froze()
        body = self.bodies()[-1]
        self.assertNotIn("Canvas-Node:", body)
        # It still says who did it and what it was applied to, like any write.
        self.assertIn("Canvas-Author:", body)
        self.assertIn("Canvas-Base:", body)

    def test_the_document_on_disk_is_byte_identical_afterwards(self):
        before = self.document()
        self.froze()
        self.assertEqual(before, self.document())

    def test_the_freeze_leaves_nothing_uncommitted_behind(self):
        self.froze()
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_the_store_reports_the_canvas_as_frozen_with_its_reason(self):
        sha = self.froze()
        store = self.the_store()
        ended = store.frozen(self.canvas_dir, "a-ledger-row")
        self.assertIsNotNone(ended)
        self.assertEqual(sha, ended.sha)
        self.assertEqual(self.REASON, ended.reason)
        self.assertTrue(ended.author.strip())

    def test_a_canvas_nobody_froze_is_not_frozen(self):
        store = self.the_store()
        self.assertIsNone(store.frozen(self.canvas_dir, "a-ledger-row"))

    def test_freezing_one_canvas_does_not_freeze_another(self):
        self.create(ledger_id="b-row")
        self.froze()
        store = self.the_store()
        self.assertIsNone(store.frozen(self.canvas_dir, "b-row"))
        code, _, stderr = self.run_canvas(
            "insert", "b-row", "--into", "root", "--text", "x",
            "--why", "the other canvas is still alive",
        )
        self.assertEqual(0, code, stderr)

    def test_an_absent_why_exits_two_and_freezes_nothing(self):
        before = self.state()
        code, stdout, stderr = self.freeze()
        self.assertEqual(2, code, stderr)
        self.assertEqual(b"", stdout)
        self.assertEqual(before, self.state())
        self.assertIsNone(self.the_store().frozen(self.canvas_dir, "a-ledger-row"))

    def test_an_empty_why_exits_two_and_freezes_nothing(self):
        for why in ("", "   ", "\n"):
            before = self.state()
            code, stdout, stderr = self.freeze("--why", why)
            self.assertEqual(2, code, (why, stderr))
            self.assertEqual(b"", stdout, why)
            self.assertEqual(before, self.state(), why)
            self.assertIsNone(
                self.the_store().frozen(self.canvas_dir, "a-ledger-row"), why
            )

    def test_a_bare_back_reference_is_refused_like_any_other_reason(self):
        # `freeze` takes `--why` like every other write, so it goes through the
        # same reason rules: `require_reason` and `VERDICT.md` §5.2's guard,
        # with no fields, no structure and no required vocabulary added.
        before = self.state()
        code, _, stderr = self.freeze("--why", "as above")
        self.assertEqual(2, code, stderr)
        self.assertEqual(before, self.state())

    def test_freezing_a_ledger_row_with_no_canvas_is_refused(self):
        before = self.state()
        code, _, stderr = self.freeze("--why", self.REASON, ledger_id="no-such-row")
        self.assertEqual(1, code, stderr)
        self.assertEqual(before, self.state())

    def test_a_freeze_takes_no_base_and_declares_nothing(self):
        # A freeze names no node, so there is no staleness claim for it to
        # make. README documents an omitted `--base` as the absence of the
        # question; a flag that cannot be given is that absence made certain.
        code, _, _ = self.freeze(
            "--why", self.REASON, "--base", self.git("rev-parse", "HEAD").strip()
        )
        self.assertEqual(2, code)
        # And the commit still records the head it was applied to, truthfully.
        head = self.git("rev-parse", "HEAD").strip()
        self.froze()
        self.assertIn("Canvas-Base: %s" % head, self.bodies()[-1].splitlines())

    def test_an_explicit_author_is_used_verbatim(self):
        code, _, stderr = self.freeze(
            "--why", self.REASON,
            "--author", "leo | step:implement | run:ship-the-flag-3",
        )
        self.assertEqual(0, code, stderr)
        self.assertIn(
            "Canvas-Author: leo | step:implement | run:ship-the-flag-3",
            self.git("log", "-1", "--format=%B").splitlines(),
        )


class EveryWriteVerbIsRefusedAgainstAFrozenCanvas(
    RefusalSurface, FrozenCanvasTestCase
):
    """The done condition's second clause: every write verb — `replace`,
    `insert`, `remove`, `move`, and the freeze itself applied twice — is
    refused against a frozen canvas, with a refusal naming the freeze, its
    reason and its commit, at the exit code `README.md` section *Exit codes*
    justifies.

    **Exit `1`, asserted as `1` and not merely as non-zero.** `1` is "the
    request is wrong against the store as it stands", whose listed members
    include a node that moved since the `--base` declared for it — a store that
    moved under a well-formed request. `2` is "the tool or its environment is
    wrong". A `replace` against a frozen canvas is a well-formed invocation of
    a tool in perfect health, so the code is the half of this clause a test has
    to pin.

    These assert behaviour and exit codes and never the wording of a
    diagnostic, like everything else here — what is asserted about the message
    is that it carries the freeze's sha and the reason the writer needs to act
    on, both of which are values this test put there.
    """

    def setUp(self):
        FrozenCanvasTestCase.setUp(self)
        self.freeze_sha = self.froze()
        self.frozen_state = self.state()

    def writes(self):
        """One invocation per write verb, each of them well formed."""
        return (
            ("replace", "a-ledger-row", self.problem_id, "--text", "restated"),
            ("insert", "a-ledger-row", "--into", "root", "--text", "a note"),
            ("remove", "a-ledger-row", self.problem_id),
            ("move", "a-ledger-row", self.problem_id, "--into", "root"),
            ("freeze", "a-ledger-row"),
        )

    def test_every_write_verb_exits_one(self):
        for args in self.writes():
            code, stdout, stderr = self.run_canvas(
                *(args + ("--why", "a reason this edit is being made"))
            )
            self.assertEqual(1, code, (args, stderr))
            self.assertEqual(b"", stdout, args)

    def test_the_refusal_names_the_freeze_its_reason_and_its_commit(self):
        for args in self.writes():
            code, _, stderr = self.run_canvas(
                *(args + ("--why", "a reason this edit is being made"))
            )
            trailers = self.assertSurface(
                1, code, stderr, msg=args,
                about=["ledger id a-ledger-row", "freeze %s" % self.freeze_sha],
            )
            # The reason it ended, so the writer learns what ended it without a
            # second command; and the commit, so they can go and read it.
            self.assertIn(self.REASON, stderr, args)
            self.assertIn(self.freeze_sha, stderr, args)
            self.assertTrue(trailers["Canvas-Next"][0].strip(), args)

    def test_nothing_is_applied_committed_or_minted(self):
        for args in self.writes():
            self.run_canvas(*(args + ("--why", "a reason this edit is being made")))
            self.assertEqual(self.frozen_state, self.state(), args)
            self.assertEqual(
                [], [each for each in os.listdir(self.canvas_dir) if ".tmp-" in each]
            )

    def test_the_editing_verbs_still_name_the_node_they_were_refused_for(self):
        for args in (
            ("replace", "a-ledger-row", self.problem_id, "--text", "restated"),
            ("remove", "a-ledger-row", self.problem_id),
            ("move", "a-ledger-row", self.problem_id, "--into", "root"),
        ):
            code, _, stderr = self.run_canvas(*(args + ("--why", "a reason")))
            self.assertSurface(1, code, stderr, msg=args, nodes=[self.problem_id])

    def test_a_second_freeze_is_refused_naming_the_first(self):
        code, _, stderr = self.run_canvas(
            "freeze", "a-ledger-row", "--why", "abandoned: a second ending"
        )
        self.assertSurface(
            1, code, stderr, msg="a second freeze",
            about=["freeze %s" % self.freeze_sha],
        )
        self.assertEqual(self.frozen_state, self.state())
        # And the canvas is still ended by the first freeze, not the second.
        self.assertEqual(
            self.freeze_sha,
            self.the_store().frozen(self.canvas_dir, "a-ledger-row").sha,
        )

    def test_create_against_a_frozen_ledger_id_names_the_freeze(self):
        # `create` cannot reach the shared guard — it refuses earlier, on the
        # file already being there — and its ordinary advice, change it one
        # node at a time, cannot work against a frozen canvas.
        code, _, stderr = self.run_canvas(
            "create", "a-ledger-row", "--problem", "P", "--expected-value", "V"
        )
        self.assertSurface(
            1, code, stderr, msg="create over a frozen canvas",
            about=["ledger id a-ledger-row", "freeze %s" % self.freeze_sha],
        )
        self.assertIn(self.REASON, stderr)
        self.assertEqual(self.frozen_state, self.state())

    def test_an_absent_or_empty_why_is_still_the_invocation_being_wrong(self):
        # Ordering, stated so it is not discovered later: `require_reason` runs
        # first, so an unexplained edit is exit 2 whatever the store's state is.
        for args in (
            ("replace", "a-ledger-row", self.problem_id, "--text", "x"),
            ("freeze", "a-ledger-row"),
        ):
            code, _, stderr = self.run_canvas(*args)
            self.assertEqual(2, code, (args, stderr))
            code, _, stderr = self.run_canvas(*(args + ("--why", "  ")))
            self.assertEqual(2, code, (args, stderr))
        self.assertEqual(self.frozen_state, self.state())

    def test_the_guard_binds_a_caller_that_only_imports_the_store(self):
        # The rule is a property of the write path and not of the command
        # line, exactly as `--why` and "one edit is one node" are: a caller
        # that never goes near `canvas/cli.py` gets the same refusal.
        store = self.the_store()
        for call in (
            lambda: store.replace("a-ledger-row", self.problem_id, "w", text="x"),
            lambda: store.remove("a-ledger-row", self.problem_id, "w"),
            lambda: store.move("a-ledger-row", self.problem_id, "w", into="root"),
            lambda: store.insert("a-ledger-row", "w", into="root", text="x"),
            lambda: store.freeze("a-ledger-row", "w"),
        ):
            with self.assertRaises(store.Refusal) as caught:
                call()
            self.assertIn(self.freeze_sha, str(caught.exception))
            self.assertIn("freeze %s" % self.freeze_sha, caught.exception.about)
        self.assertEqual(self.frozen_state, self.state())

    def test_the_write_path_itself_refuses_a_write_to_a_frozen_canvas(self):
        # The second call site of the one guard: `_write_and_commit` is the
        # only function that puts a canvas on its real path, and it will not
        # put one there for a canvas that has ended.
        store = self.the_store()
        rewritten = document.parse(self.canvas_file())
        with self.assertRaises(store.Refusal) as caught:
            store._write_and_commit(
                self.canvas_dir,
                self.canvas_file(),
                rewritten,
                "replace",
                self.problem_id,
                "a reason this edit is being made",
                "audit | by-hand",
                node_id=self.problem_id,
            )
        self.assertIn(self.freeze_sha, str(caught.exception))
        self.assertEqual(self.frozen_state, self.state())

    def test_a_freeze_may_not_smuggle_a_document_rewrite_in_with_it(self):
        # The freeze is the second write that names no node, so it gets the
        # second guard: it may change no byte. A tree handed in with a node
        # rewritten is a whole-document rewrite arriving under the one trailer
        # that names nothing, and it is refused like any other.
        store = self.the_store()
        self.create(ledger_id="b-row")
        rewritten = document.parse(self.canvas_file("b-row"))
        for node in list(rewritten):
            node.text = "rewritten wholesale"
        before = self.state()
        with self.assertRaises(store.Refusal) as caught:
            store._write_and_commit(
                self.canvas_dir,
                self.canvas_file("b-row"),
                rewritten,
                "freeze",
                "b-row",
                "an ending that is really a rewrite",
                "audit | by-hand",
                freeze="b-row",
            )
        for named in [node.get("id") for node in rewritten]:
            self.assertIn(named, str(caught.exception))
        self.assertEqual(before, self.state())
        self.assertIsNone(store.frozen(self.canvas_dir, "b-row"))


class ReadingAndHistoryStillWorkOnAFrozenCanvas(FrozenCanvasTestCase):
    """The done condition's third clause: `read` and `history` still work on a
    frozen canvas — "never deleted" is the other half of the same spec
    sentence, and a record nobody can read is deleted in every way that
    matters.

    They keep working *identically*: same stdout, same exit code. In particular
    an **unflagged** `read` does not grow a freeze line, because `README.md`
    section *Reading a canvas* documents stdout's exact shape — one header
    line, then the document, so that `bin/canvas read my-task | tail -n +2` is
    the document byte for byte.

    `read --frozen` is how a reader asks instead, and it is the one
    non-destructive way to: it adds one header line and nothing else, it writes
    nothing, and it answers at exit `0` whether the canvas ended or not. The
    flag is what keeps the paragraph above true — a caller that does not ask
    pays nothing for a freeze somebody else made.
    """

    def setUp(self):
        FrozenCanvasTestCase.setUp(self)
        self.note = self.inserted(
            "--into", "root", "--text", "A note.", "--why", "a note to have a history"
        )
        self.verb("replace", self.note, "--text", "A sharper note.", "--why", "sharper")
        code, self.read_before, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code, stderr)
        code, self.history_before, stderr = self.run_canvas(
            "history", "a-ledger-row", self.note
        )
        self.assertEqual(0, code, stderr)
        self.freeze_sha = self.froze()

    def test_read_exits_zero_and_prints_the_same_document(self):
        code, stdout, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code, stderr)
        # The body is identical; only the head line moves, because the freeze
        # is a commit and `read` hands out the repository head.
        self.assertEqual(
            self.read_before.split(b"\n", 1)[1], stdout.split(b"\n", 1)[1]
        )

    def test_read_still_prints_exactly_one_header_line_before_the_document(self):
        code, stdout, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code, stderr)
        first, rest = stdout.split(b"\n", 1)
        self.assertEqual(b"Canvas-Base: %s" % self.freeze_sha.encode("utf-8"), first)
        self.assertEqual(self.document(), rest)

    def test_history_exits_zero_and_returns_exactly_the_edits_it_returned_before(self):
        code, stdout, stderr = self.run_canvas("history", "a-ledger-row", self.note)
        self.assertEqual(0, code, stderr)
        self.assertEqual(self.history_before, stdout)

    def test_history_of_the_canvas_first_nodes_still_works(self):
        for node_id in (self.problem_id, self.value_id):
            code, stdout, stderr = self.run_canvas(
                "history", "a-ledger-row", node_id
            )
            self.assertEqual(0, code, (node_id, stderr))
            self.assertIn(b"Canvas-Commit: ", stdout)

    def test_neither_of_them_writes_anything(self):
        before = self.state()
        self.run_canvas("read", "a-ledger-row")
        self.run_canvas("history", "a-ledger-row", self.note)
        self.assertEqual(before, self.state())

    def test_the_freeze_is_not_a_node_and_shows_up_in_no_nodes_history(self):
        # A freeze names no node, so it is in nothing's history and bumps
        # nothing's `v`. "One edit is one node" stays literally true.
        for node_id in (self.problem_id, self.value_id, self.note):
            code, stdout, stderr = self.run_canvas(
                "history", "a-ledger-row", node_id
            )
            self.assertEqual(0, code, stderr)
            self.assertNotIn(self.freeze_sha.encode("utf-8"), stdout)
        # And no node's `v` moved: the freeze named none, so it counts for none.
        self.assertEqual(
            ["1", "1", "2"],
            [self.node(each).get("v") for each in
             (self.problem_id, self.value_id, self.note)],
        )

    def test_read_frozen_names_the_freeze_and_its_reason_at_exit_zero(self):
        # The gap this flag closes: the reason a canvas ended was readable
        # only by running `git log` by hand, or by attempting a write and
        # being refused at exit 1.
        code, stdout, stderr = self.run_canvas(
            "read", "a-ledger-row", "--frozen"
        )
        self.assertEqual(0, code, stderr)
        printed = self.printed(stdout, "Canvas-Frozen")
        self.assertEqual(1, len(printed), printed)
        sha, reason = printed[0].split(" ", 1)
        self.assertEqual(self.freeze_sha, sha)
        self.assertEqual(self.REASON, reason)

    def test_read_frozen_says_none_of_a_canvas_that_has_not_ended_at_exit_zero(self):
        # `none` is an answer and not a failure, and it is printed rather than
        # omitted: the question was asked on purpose, so silence would be
        # indistinguishable from the flag having done nothing.
        self.create(ledger_id="a-second-row")
        code, stdout, stderr = self.run_canvas(
            "read", "a-second-row", "--frozen"
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(["none"], self.printed(stdout, "Canvas-Frozen"))

    def test_read_frozen_writes_nothing(self):
        # Neither answer writes: a read is a read whichever way it comes out.
        self.create(ledger_id="a-third-row")
        before = self.state()
        self.run_canvas("read", "a-ledger-row", "--frozen")
        self.run_canvas("read", "a-third-row", "--frozen")
        self.assertEqual(before, self.state())

    def test_read_frozen_prints_the_document_an_unflagged_read_prints(self):
        # The freeze stays out of the document: the line is above the `<?xml`
        # boundary `README.md` defines, and the bytes below it are the file's.
        code, stdout, stderr = self.run_canvas(
            "read", "a-ledger-row", "--frozen"
        )
        self.assertEqual(0, code, stderr)
        text = stdout.decode("utf-8")
        self.assertEqual(
            self.document(), text[text.index("<?xml"):].encode("utf-8")
        )

    def test_read_frozen_puts_its_line_under_the_base_and_above_the_rest(self):
        # It is a fact about the whole canvas; `Canvas-Wrote:` is per node.
        code, stdout, stderr = self.run_canvas(
            "read", "a-ledger-row", "--frozen", "--provenance"
        )
        self.assertEqual(0, code, stderr)
        names = [line.split(": ", 1)[0] for line in self.header(stdout)]
        self.assertEqual(["Canvas-Base", "Canvas-Frozen"], names[:2])
        self.assertEqual({"Canvas-Wrote"}, set(names[2:]))


class AFreezeIsFinal(RefusalSurface, FrozenCanvasTestCase):
    """The done condition's fourth clause, at the level a test can hold: the
    behaviour `README.md` describes when a frozen canvas's task reopens.

    The answer README states is that there is no unfreeze. The frozen canvas
    stays where it is — readable, `history`-able, never deleted — and a ledger
    row whose task comes back gets a new ledger row and therefore a new canvas,
    which points at the frozen one. So what a test can hold is that the tool
    has no verb that would unfreeze anything, that a frozen canvas is still
    frozen after every refused write, and that the route README names does
    work.
    """

    #: Every verb `bin/canvas` has, and all of it. A tenth added here fails
    #: this test until somebody has classified it, which is the point: `read`,
    #: `render` and `history` read, `create` and `freeze` are the two ends of a
    #: canvas's life, and the four in between are the editing verbs.
    #:
    #: `render` is in the reading group and not in a group of its own. It is a
    #: projection — `engineering-spec.md` section *Projections*: one-way, never
    #: edited and never read back — and what that means for this list is that
    #: it writes no file, makes no commit, mints no id and initialises no
    #: repository, so it is refused against nothing and works on a frozen
    #: canvas exactly as `read` and `history` do. `tests/test_render.py`
    #: asserts each of those.
    VERBS = (
        "create", "read", "render", "history", "replace", "insert", "remove",
        "move", "freeze",
    )

    def test_the_tool_has_exactly_the_documented_verbs(self):
        from canvas import cli

        self.assertEqual(sorted(self.VERBS), sorted(cli.build_parser().verbs))

    def test_unfreeze_reopen_and_thaw_are_unknown_verbs_at_exit_two(self):
        self.froze()
        before = self.state()
        for verb in ("unfreeze", "reopen", "thaw", "abandon"):
            code, stdout, stderr = self.run_canvas(verb, "a-ledger-row")
            self.assertSurface(2, code, stderr, msg=verb)
            self.assertEqual(b"", stdout, verb)
            self.assertEqual(before, self.state(), verb)

    def test_a_frozen_canvas_is_still_frozen_after_every_refused_write(self):
        sha = self.froze()
        store = self.the_store()
        for args in (
            ("replace", "a-ledger-row", self.problem_id, "--text", "x"),
            ("insert", "a-ledger-row", "--into", "root", "--text", "x"),
            ("remove", "a-ledger-row", self.problem_id),
            ("move", "a-ledger-row", self.problem_id, "--into", "root"),
            ("freeze", "a-ledger-row"),
        ):
            self.run_canvas(*(args + ("--why", "a reason this edit is made")))
            ended = store.frozen(self.canvas_dir, "a-ledger-row")
            self.assertIsNotNone(ended, args)
            self.assertEqual(sha, ended.sha, args)

    def test_the_reopening_route_readme_names_is_one_that_works(self):
        # A new ledger row, a new canvas, and a <link> node on the live one
        # pointing back at the frozen one. The old canvas is not edited to say
        # it was superseded — that would be a write to a frozen canvas, and the
        # pointer belongs on the document that is still alive.
        frozen_sha = self.froze()
        code, _, stderr = self.run_canvas(
            "create", "a-ledger-row-reopened",
            "--problem", "The problem, restated for the reopened row.",
            "--expected-value", "The value expected of the reopened row.",
        )
        self.assertEqual(0, code, stderr)
        code, stdout, stderr = self.run_canvas(
            "insert", "a-ledger-row-reopened", "--into", "root",
            "--type", "link", "--href", "a-ledger-row.xml",
            "--text", "The canvas this row continues.",
            "--why", "the row a-ledger-row was frozen at %s and its work has "
                     "restarted here" % frozen_sha,
        )
        self.assertEqual(0, code, stderr)
        # And the frozen one is untouched by any of it.
        self.assertEqual(
            frozen_sha,
            self.the_store().frozen(self.canvas_dir, "a-ledger-row").sha,
        )
        code, _, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code, stderr)


class TheReadmeAnswersTheReopeningCase(unittest.TestCase):
    """The done condition's fourth clause at the level it is actually written:
    `README.md` answers, in its own words, what happens when a frozen canvas's
    task reopens — as prose a reader can act on, not as a note that the
    question exists.

    Narrow on purpose, so that it is not a wording test. What it holds is that
    the section is there, that it names the command it is about, and that it
    answers the reopening question rather than only raising it — checked
    against the commands and the words a reader would have to search for,
    never against a sentence.
    """

    def readme(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as handle:
            return handle.read()

    def section(self, title):
        """One `###` section of README, from its heading to the next one."""
        text = self.readme()
        start = text.find("### %s\n" % title)
        self.assertNotEqual(-1, start, "README has no section %r" % title)
        end = text.find("\n### ", start + 1)
        return text[start:] if end == -1 else text[start:end]

    def test_readme_has_a_section_about_ending_a_canvas(self):
        section = self.section("Ending a canvas")
        self.assertIn("bin/canvas freeze", section)
        self.assertIn("--why", section)

    def test_it_says_what_a_write_against_a_frozen_canvas_does(self):
        section = self.section("Ending a canvas")
        for verb in ("replace", "insert", "remove", "move"):
            self.assertIn(verb, section)
        # The exit code, which is the half of the refusal a caller branches on.
        self.assertIn("`1`", section)

    def test_it_says_that_read_and_history_still_work(self):
        section = self.section("Ending a canvas")
        self.assertIn("bin/canvas read", section)
        self.assertIn("history", section)

    def test_it_answers_what_happens_when_the_task_reopens(self):
        # The question itself, and the answer — a new ledger row, a new canvas
        # made with `create`, and a link back — rather than a note that the
        # question exists.
        section = self.section("Ending a canvas")
        self.assertIn("reopen", section.lower())
        self.assertIn("unfreeze", section.lower())
        self.assertIn("bin/canvas create", section)
        self.assertIn("<link>", section)

    def test_the_store_section_lists_the_command(self):
        self.assertIn("bin/canvas freeze  <ledger_id> --why TEXT", self.readme())

    def test_what_the_store_does_not_do_says_it_does_not_unfreeze(self):
        self.assertIn(
            "unfreeze", self.section("What the store deliberately does not do")
        )

    def test_every_verb_readme_lists_is_a_verb_the_tool_has(self):
        # The bridge from the prose to the behaviour: README's own command list
        # and the parser's verbs are the same set, so a section that documents
        # a verb nobody implemented fails here.
        from canvas import cli

        listed = set(
            re.findall(r"^    bin/canvas (\w+)", self.readme(), re.MULTILINE)
        )
        self.assertEqual(set(cli.build_parser().verbs), listed)

if __name__ == "__main__":
    unittest.main()
