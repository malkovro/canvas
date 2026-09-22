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
        # an unexplained edit either. write_and_commit is the only function
        # that puts a canvas on its real path, and it will not.
        from canvas import store

        for reason in (None, "", "   ", "\n"):
            with self.assertRaises(store.ToolProblem):
                store.require_reason(reason)

        with self.assertRaises(store.ToolProblem):
            store.write_and_commit(
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

    def test_no_verb_accepts_base(self):
        # The staleness rule is a separate task. Nothing here compares a
        # supplied sha against anything, so nothing here accepts one.
        head = self.git("rev-parse", "HEAD").strip()
        for edit in (
            ("replace", self.problem_id, "--text", "x"),
            ("remove", self.problem_id),
            ("move", self.problem_id, "--into", "root"),
            ("insert", "--into", "root", "--text", "x"),
        ):
            before = self.state()
            code, _, _ = self.verb(*(edit + ("--base", head, "--why", "a reason")))
            self.assertEqual(2, code, edit)
            self.assertEqual(before, self.state(), edit)

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


if __name__ == "__main__":
    unittest.main()
