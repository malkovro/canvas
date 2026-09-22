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
        lines = stdout.decode("utf-8").splitlines()
        self.assertTrue(lines[0].startswith("Canvas-Base: "), lines)
        self.assertTrue(SHA.match(lines[0].split(": ", 1)[1]), lines[0])
        self.assertEqual("Canvas-File: %s" % self.canvas_file(), lines[1])

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

        code, _, _ = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(0, code)

        self.assertEqual(before_sha, self.git("rev-parse", "HEAD"))
        self.assertEqual(before_log, self.git("log", "--format=%H"))
        with open(self.canvas_file(), "rb") as handle:
            self.assertEqual(before_bytes, handle.read())
        self.assertEqual(before_listing, sorted(os.listdir(self.canvas_dir)))
        self.assertEqual("", self.git("status", "--porcelain"))

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
        # to read, and initialising one to say so would be a write.
        code, stdout, stderr = self.run_canvas("read", "a-ledger-row")
        self.assertEqual(1, code, stderr)
        self.assertEqual(b"", stdout)
        self.assertFalse(os.path.exists(os.path.join(self.workspace, "state")))


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
    #: supported write surface is five functions and the rest reads or computes.
    PUBLIC_STORE = {
        "Refusal", "ToolProblem",
        # The supported write surface, and all of it.
        "create", "insert", "replace", "remove", "move",
        # Reads, lookups and pure functions.
        "read", "history", "Edit", "canvas_directory", "canvas_path",
        "is_repository", "ensure_repository", "head_sha", "is_free", "mint",
        "require_reason", "history_length", "next_version", "default_author",
        "preflight",
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


if __name__ == "__main__":
    unittest.main()
