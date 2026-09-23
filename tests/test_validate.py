"""Tests for the canvas schema and the single validation path.

These assert behaviour, not wording: for each invalid fixture, that the exit
code is non-zero and that the diagnostic names the offending node. Asserting
the full message text would couple the tests to libxml2's phrasing and break on
a libxml2 upgrade for no gain.
"""

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
SHIM = os.path.join(ROOT, "bin", "canvas-validate")
SCHEMA = os.path.join(ROOT, "schema", "canvas.rng")

sys.path.insert(0, ROOT)

from canvas.validate import EnvironmentProblem, validate_file  # noqa: E402


def fixture(name):
    return os.path.join(FIXTURES, name)


def strip_namespace(tag):
    return tag.rsplit("}", 1)[-1]


@contextlib.contextmanager
def mock_schema(path):
    """Point the validator at another schema for the length of one block."""
    from canvas import validate

    was = validate.SCHEMA_PATH
    validate.SCHEMA_PATH = path
    try:
        yield
    finally:
        validate.SCHEMA_PATH = was


def run_shim(*args):
    """Run the standalone entry point. Returns (exit code, stderr)."""
    result = subprocess.run(
        [sys.executable, SHIM] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode, result.stderr.decode("utf-8", "replace")


class ValidFilesValidate(unittest.TestCase):
    """A schema that rejects nothing is useless; one that rejects a legal
    intermediate state blocks the verbs that come next."""

    def test_a_valid_canvas_validates(self):
        self.assertEqual([], validate_file(fixture("valid.xml")))

    def test_a_valid_canvas_exits_zero(self):
        code, stderr = run_shim(fixture("valid.xml"))
        self.assertEqual(0, code)
        self.assertEqual("", stderr)

    def test_the_creation_commits_output_validates(self):
        # node-identity.md section 4: the creation commit creates the root only.
        self.assertEqual([], validate_file(fixture("born.xml")))

    def test_empty_containers_are_legal(self):
        # valid.xml carries an empty <list>, <table>, <row>, inner <section>
        # and outer <section>. One edit is one node, so each of those is a
        # state the document really passes through.
        with open(fixture("valid.xml")) as handle:
            source = handle.read()
        for empty in ("<list ", "<table ", "<row ", "<section "):
            self.assertIn(empty.rstrip() + ' id=', source)
        self.assertEqual([], validate_file(fixture("valid.xml")))

    def test_the_schema_stands_on_its_own_without_python(self):
        result = subprocess.run(
            ["xmllint", "--noout", "--relaxng", SCHEMA, fixture("valid.xml")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(0, result.returncode, result.stderr)


class OutOfVocabularyNodesAreRejected(unittest.TestCase):
    """The done condition: a node type outside the vocabulary fails with a
    non-zero exit and the diagnostic names it."""

    def assert_rejected_naming(self, name, *expected):
        problems = validate_file(fixture(name))
        self.assertTrue(problems, "%s should not validate" % name)
        joined = "\n".join(problems)
        for needle in expected:
            self.assertIn(needle, joined)
        code, stderr = run_shim(fixture(name))
        self.assertNotEqual(0, code)
        self.assertEqual(1, code, "an invalid document is exit 1, not an environment error")
        for needle in expected:
            self.assertIn(needle, stderr)

    def test_decision_is_rejected_and_named(self):
        self.assert_rejected_naming("unknown-node.xml", "<decision>", 'id="jc5v"')

    def test_risk_is_rejected_and_named(self):
        self.assert_rejected_naming("risk-node.xml", "<risk>", 'id="k3xq"')

    def test_acceptance_criterion_is_rejected_and_named(self):
        self.assert_rejected_naming(
            "acceptance-criterion-node.xml", "<acceptance-criterion>", 'id="m2ph"'
        )

    def test_the_grammar_contains_no_escape_hatch(self):
        # The vocabulary is closed, so the grammar must contain no wildcard and
        # no external reference through which an unanticipated element could
        # enter. Parsed rather than grepped, so a word in a comment is not a
        # false alarm and a real wildcard cannot hide behind one.
        patterns = {strip_namespace(e.tag) for e in ElementTree.parse(SCHEMA).iter()}
        for hatch in ("anyName", "nsName", "externalRef", "include", "parentRef"):
            self.assertNotIn(hatch, patterns)

    def test_the_grammar_declares_exactly_the_vocabulary(self):
        # Eleven element names, and no twelfth. This is the closed list.
        declared = {
            e.get("name")
            for e in ElementTree.parse(SCHEMA).iter()
            if strip_namespace(e.tag) == "element"
        }
        self.assertEqual(
            {
                "canvas", "section", "text", "list", "item",
                "table", "row", "cell", "figure", "link", "question",
            },
            declared,
        )

    def test_the_grammar_declares_exactly_these_attributes(self):
        # The mirror of the element invariant, and node-state.md section 6's
        # tripwire: the ruling adds `answered` and nothing else, so a twelfth
        # attribute — or a second legal value for `answered` — must break a
        # test and send somebody back to node-state.md before it lands.
        declared = {
            e.get("name")
            for e in ElementTree.parse(SCHEMA).iter()
            if strip_namespace(e.tag) == "attribute"
        }
        self.assertEqual(
            {"ledger", "schema", "id", "v", "title", "href", "answered"},
            declared,
        )

    def test_answered_has_exactly_one_legal_value(self):
        # node-state.md: absence means open, so `true` is the only spelling
        # there is. The value set is read out of the grammar rather than
        # inferred from the fixtures, so widening it here breaks this.
        tree = ElementTree.parse(SCHEMA)
        values = []
        for attribute in tree.iter():
            if strip_namespace(attribute.tag) != "attribute":
                continue
            if attribute.get("name") != "answered":
                continue
            values.extend(
                child.text for child in attribute
                if strip_namespace(child.tag) == "value"
            )
        self.assertEqual(["true"], values)


class QuestionStateIsTheOnlyStateANodeHas(unittest.TestCase):
    """node-state.md: a canvas says exactly one thing about a node's state —
    whether a `<question>` has been answered. The legal shape validates; the
    three wrong new shapes fail, and each diagnostic names the node it is
    about, not the file."""

    def assert_rejected_naming(self, name, *expected):
        problems = validate_file(fixture(name))
        self.assertTrue(problems, "%s should not validate" % name)
        joined = "\n".join(problems)
        for needle in expected:
            self.assertIn(needle, joined)
        code, stderr = run_shim(fixture(name))
        self.assertEqual(1, code, "an invalid document is exit 1, not an environment error")
        for needle in expected:
            self.assertIn(needle, stderr)

    def test_an_answered_question_validates(self):
        # The new shape. valid.xml carries an answered <question> beside an
        # open one, so both halves of the vocabulary are exercised.
        with open(fixture("valid.xml")) as handle:
            source = handle.read()
        self.assertIn('<question id="mqxd" v="2" answered="true">', source)
        self.assertIn('<question id="k3xq" v="1">', source)  # open: no attribute
        self.assertEqual([], validate_file(fixture("valid.xml")))
        self.assertEqual(0, run_shim(fixture("valid.xml"))[0])

    def test_answered_on_an_element_that_is_not_a_question_is_rejected(self):
        # State belongs to <question> and to nothing else: putting it on a
        # structural element is what makes the vocabulary a taxonomy.
        self.assert_rejected_naming(
            "answered-on-wrong-element.xml", "<text>", 'id="q4rt"'
        )

    def test_answered_with_any_value_but_true_is_rejected(self):
        # Absence means open, so `false`, `yes` and `TRUE` are all second
        # spellings of a state the document already has one spelling for.
        # The diagnostic does not echo the rejected value, so the assertion is
        # on the element and the id.
        self.assert_rejected_naming(
            "answered-bad-value.xml", "<question>", 'id="mqxd"', 'id="jc5v"',
            'id="q4rt"',
        )

    def test_a_question_may_not_point_at_what_answered_it(self):
        # The pointer half of the option, refused: the reason names the node
        # that answered the question. The fixture pins the refusal, so adding
        # `answered-by` later means deleting this test and reopening
        # node-state.md.
        self.assert_rejected_naming(
            "answered-by-pointer.xml", "<question>", 'id="mqxd"'
        )

    def test_no_other_element_declares_a_state_attribute(self):
        # The ruling in the grammar's own terms: exactly one element carries
        # `answered`, and it is <question>.
        carriers = []
        for element in ElementTree.parse(SCHEMA).iter():
            if strip_namespace(element.tag) != "element":
                continue
            names = {
                attribute.get("name")
                for attribute in element.iter()
                if strip_namespace(attribute.tag) == "attribute"
            }
            if "answered" in names:
                carriers.append(element.get("name"))
        self.assertEqual(["question"], carriers)


class MissingIdOrVIsRejected(unittest.TestCase):
    """The done condition: a node missing `id` or `v` fails with a non-zero
    exit and the diagnostic names the offending node."""

    def test_a_node_missing_id_is_rejected_and_identified(self):
        problems = validate_file(fixture("missing-id.xml"))
        self.assertTrue(problems)
        joined = "\n".join(problems)
        self.assertIn("<text>", joined)
        self.assertIn("no id attribute", joined)
        # It has no id to be named by, so it is named by where it is.
        self.assertIn("/canvas[1]/text[1]", joined)
        code, stderr = run_shim(fixture("missing-id.xml"))
        self.assertEqual(1, code)
        self.assertIn("<text>", stderr)

    def test_a_node_missing_v_is_rejected_and_identified(self):
        problems = validate_file(fixture("missing-v.xml"))
        self.assertTrue(problems)
        joined = "\n".join(problems)
        self.assertIn("<text>", joined)
        self.assertIn('id="q4rt"', joined)
        self.assertIn("no v attribute", joined)
        code, stderr = run_shim(fixture("missing-v.xml"))
        self.assertEqual(1, code)
        self.assertIn('id="q4rt"', stderr)

    def test_ids_that_do_not_match_the_minting_rule_are_rejected(self):
        # node-identity.md section 1: four characters, first a lowercase letter,
        # the other three with l, 1, o, 0 and i excluded.
        problems = validate_file(fixture("bad-id.xml"))
        joined = "\n".join(problems)
        for bad in ('id="K3XQ"', 'id="k3x"', 'id="k3xo"', 'id="k3x1"'):
            self.assertIn(bad, joined)
        self.assertEqual(1, run_shim(fixture("bad-id.xml"))[0])

    def test_v_must_be_a_positive_integer(self):
        # node-identity.md section 4: a node is born at v="1".
        problems = validate_file(fixture("bad-v.xml"))
        joined = "\n".join(problems)
        for bad in ('v="0"', 'v="01"', 'v="two"'):
            self.assertIn(bad, joined)
        self.assertEqual(1, run_shim(fixture("bad-v.xml"))[0])


class ContainmentRulesAreEnforced(unittest.TestCase):
    """The rest of the closed vocabulary, demonstrated rather than asserted."""

    def test_a_section_three_levels_deep_is_rejected(self):
        problems = validate_file(fixture("too-deep.xml"))
        joined = "\n".join(problems)
        self.assertIn("<section>", joined)
        self.assertIn('id="f5bt"', joined)  # the third level, not the first two
        self.assertEqual(1, run_shim(fixture("too-deep.xml"))[0])

    def test_an_item_outside_a_list_is_rejected(self):
        problems = validate_file(fixture("item-outside-list.xml"))
        joined = "\n".join(problems)
        self.assertIn("<item>", joined)
        self.assertIn('id="r9tk"', joined)
        self.assertEqual(1, run_shim(fixture("item-outside-list.xml"))[0])


class RootAttributesAreRequired(unittest.TestCase):

    def test_a_root_without_ledger_is_rejected(self):
        problems = validate_file(fixture("missing-ledger.xml"))
        self.assertIn("<canvas>", "\n".join(problems))
        self.assertEqual(1, run_shim(fixture("missing-ledger.xml"))[0])

    def test_a_root_without_a_schema_version_is_rejected(self):
        problems = validate_file(fixture("missing-schema.xml"))
        self.assertIn("<canvas>", "\n".join(problems))
        self.assertEqual(1, run_shim(fixture("missing-schema.xml"))[0])

    def test_a_root_declaring_a_future_schema_version_is_rejected(self):
        # The point of pinning the version: a v2 file is not read by the v1
        # schema, it fails against it.
        problems = validate_file(fixture("future-schema.xml"))
        self.assertIn("the root", "\n".join(problems))
        self.assertEqual(1, run_shim(fixture("future-schema.xml"))[0])

    def test_a_section_without_a_title_is_rejected(self):
        problems = validate_file(fixture("missing-title.xml"))
        joined = "\n".join(problems)
        self.assertIn("<section>", joined)
        self.assertIn('id="a2jk"', joined)
        self.assertEqual(1, run_shim(fixture("missing-title.xml"))[0])

    def test_a_link_without_href_is_rejected(self):
        problems = validate_file(fixture("link-without-href.xml"))
        self.assertIn("<link>", "\n".join(problems))
        self.assertEqual(1, run_shim(fixture("link-without-href.xml"))[0])


class TheEntryPointsContract(unittest.TestCase):
    """An agent has to be able to tell 'your canvas is invalid, fix the node I
    named' from 'the validator is broken, do not touch the canvas'."""

    def test_a_file_that_is_not_well_formed_is_a_document_problem(self):
        problems = validate_file(fixture("malformed.xml"))
        self.assertTrue(problems)
        self.assertIn("not well-formed", "\n".join(problems))
        self.assertEqual(1, run_shim(fixture("malformed.xml"))[0])

    def test_a_missing_file_is_an_environment_problem(self):
        with self.assertRaises(EnvironmentProblem):
            validate_file(fixture("no-such-file.xml"))
        code, stderr = run_shim(fixture("no-such-file.xml"))
        self.assertEqual(2, code)
        self.assertIn("no such file", stderr)

    def test_no_arguments_is_an_environment_problem(self):
        code, stderr = run_shim()
        self.assertEqual(2, code)
        self.assertIn("usage", stderr)

    def test_several_files_at_once(self):
        self.assertEqual(0, run_shim(fixture("valid.xml"), fixture("born.xml"))[0])
        self.assertEqual(
            1, run_shim(fixture("valid.xml"), fixture("unknown-node.xml"))[0]
        )


class EveryRefusalNamesWhatItIsAboutAndTheNextAction(unittest.TestCase):
    """The todo's done condition, for the standalone validator.

    `bin/canvas-validate` decides its own exit codes, so it prints its own
    meaning for them. None of its refusals has a node to name — the ones that
    do are the diagnostics themselves, which already name the element, the
    `id` and the `v` — so each of the others names what it does have: the file,
    the schema, the binary, the argument it was not given.
    """

    def surface(self, stderr):
        found = {"Canvas-Node": [], "Canvas-About": [], "Canvas-Next": [],
                 "Canvas-Exit": []}
        for line in stderr.splitlines():
            for name in found:
                if line.startswith("%s: " % name):
                    found[name].append(line.split(": ", 1)[1])
        return found

    def assertSurface(self, expected_code, code, stderr, msg=None, about=(),
                      next_action=()):
        self.assertEqual(expected_code, code, "%s\n%s" % (msg, stderr))
        trailers = self.surface(stderr)
        self.assertEqual(1, len(trailers["Canvas-Next"]), stderr)
        self.assertTrue(trailers["Canvas-Next"][0].strip(), stderr)
        self.assertEqual(1, len(trailers["Canvas-Exit"]), stderr)
        self.assertTrue(
            trailers["Canvas-Exit"][0].startswith("%d " % code), stderr
        )
        self.assertTrue(
            trailers["Canvas-Node"] or trailers["Canvas-About"], stderr
        )
        for thing in about:
            self.assertTrue(
                any(thing in each for each in trailers["Canvas-About"]), stderr
            )
        for phrase in next_action:
            self.assertIn(phrase, trailers["Canvas-Next"][0], stderr)
        return trailers

    def test_an_invalid_document_keeps_its_diagnostics_and_gains_an_action(self):
        code, stderr = run_shim(fixture("unknown-node.xml"))
        self.assertSurface(
            1, code, stderr, about=["unknown-node.xml"],
            next_action=["canvas.rng", "bin/canvas-validate"],
        )
        # The diagnostic that names the node is unchanged: element, id and v.
        self.assertIn("<decision>", stderr)
        self.assertIn('id="jc5v"', stderr)

    def test_a_node_with_no_id_is_still_named_by_its_path(self):
        code, stderr = run_shim(fixture("missing-id.xml"))
        self.assertSurface(1, code, stderr, next_action=["canvas.rng"])
        self.assertIn("at /canvas[1]", stderr)

    def test_a_file_that_is_not_well_formed_says_where_and_what_to_do(self):
        code, stderr = run_shim(fixture("malformed.xml"))
        self.assertSurface(
            1, code, stderr, about=["malformed.xml"],
            next_action=["bin/canvas-validate"],
        )
        self.assertIn("not well-formed", stderr)

    def test_several_invalid_files_are_one_refusal_naming_all_of_them(self):
        code, stderr = run_shim(
            fixture("unknown-node.xml"), fixture("malformed.xml")
        )
        self.assertSurface(
            1, code, stderr,
            about=["unknown-node.xml", "malformed.xml"],
        )

    def test_no_arguments_names_the_argument_and_how_to_give_it(self):
        code, stderr = run_shim()
        self.assertSurface(
            2, code, stderr, about=["argument FILE"],
            next_action=["bin/canvas-validate"],
        )
        # The usage line it always printed is still there.
        self.assertIn("usage: canvas-validate", stderr)

    def test_a_missing_file_names_the_path_and_how_to_find_a_canvas(self):
        code, stderr = run_shim(fixture("no-such-file.xml"))
        self.assertSurface(
            2, code, stderr, about=["no-such-file.xml"],
            next_action=["OPENCLAW_WORKSPACE"],
        )

    def test_a_missing_xmllint_names_it_and_says_how_to_get_it(self):
        empty = tempfile.mkdtemp(prefix="canvas-validate-test-no-xmllint-")
        self.addCleanup(shutil.rmtree, empty, True)
        result = subprocess.run(
            [sys.executable, SHIM, fixture("valid.xml")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(os.environ, PATH=empty),
        )
        stderr = result.stderr.decode("utf-8", "replace")
        self.assertNotIn("Traceback", stderr)
        self.assertSurface(
            2, result.returncode, stderr, about=["command xmllint"],
            next_action=["xmllint"],
        )

    def test_a_schema_that_will_not_compile_names_it_and_the_file(self):
        # The one refusal that already printed an exit code — xmllint's, not
        # its own. Now it prints both.
        broken = os.path.join(
            tempfile.mkdtemp(prefix="canvas-validate-test-schema-"), "canvas.rng"
        )
        self.addCleanup(shutil.rmtree, os.path.dirname(broken), True)
        with open(broken, "w", encoding="utf-8") as handle:
            handle.write("<grammar><nonsense/></grammar>\n")
        with mock_schema(broken):
            with self.assertRaises(EnvironmentProblem) as caught:
                validate_file(fixture("valid.xml"))
        self.assertTrue(caught.exception.next_action.strip())
        self.assertTrue(caught.exception.about)
        self.assertIn("xmllint exit", "\n".join(caught.exception.about))

    def test_a_refusal_here_cannot_be_built_without_naming_something(self):
        with self.assertRaises(TypeError):
            EnvironmentProblem("something is wrong")
        with self.assertRaises(ValueError):
            EnvironmentProblem("something is wrong", "do this instead")
        with self.assertRaises(ValueError):
            EnvironmentProblem("something is wrong", "", about=["file x"])


if __name__ == "__main__":
    unittest.main()
