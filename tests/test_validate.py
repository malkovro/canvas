"""Tests for the canvas schema and the single validation path.

These assert behaviour, not wording: for each invalid fixture, that the exit
code is non-zero and that the diagnostic names the offending node. Asserting
the full message text would couple the tests to libxml2's phrasing and break on
a libxml2 upgrade for no gain.
"""

import os
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
