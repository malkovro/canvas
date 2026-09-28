"""Focused contracts for schema-v2 figures and both projections."""

import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
CANVAS = os.path.join(ROOT, "bin", "canvas")
sys.path.insert(0, ROOT)

from canvas import diagram, render, svg  # noqa: E402
from canvas.validate import validate_file  # noqa: E402


def fixture(name):
    return os.path.join(FIXTURES, name)


class CanvasDiagramOneIsTotalAndGraphical(unittest.TestCase):
    SOURCE = '\n'.join([
        'box start 1 1 "Start"',
        'box finish 1 2 "Finish"',
        'edge start -> finish "next"',
        'text 2 1 "A note"',
    ])

    def test_valid_source_draws_shapes_and_labels(self):
        output = diagram.render_text(self.SOURCE)
        root = ET.fromstring(output)
        names = {node.tag.rsplit("}", 1)[-1] for node in root.iter()}
        self.assertTrue({"svg", "rect", "line", "path", "text"} <= names)
        self.assertIn("Start", output)
        self.assertNotIn("CD1_", output)

    def test_each_source_error_becomes_a_visible_diagnostic(self):
        cases = {
            "": "CD1_EMPTY",
            "wat": "CD1_UNKNOWN",
            'box A 1 1 "x"': "CD1_ID",
            'box a 0 1 "x"': "CD1_COORDINATE",
            'box a 1 1 "x"\nbox a 2 2 "y"': "CD1_DUPLICATE_ID",
            'box a 1 1 "x"\nedge a -> absent "x"': "CD1_MISSING_ENDPOINT",
            'edge a => b "x"': "CD1_EDGE_KIND",
            'text 1 1': "CD1_ARITY",
            'box a 1 1 "unterminated': "CD1_TOKENIZE",
        }
        for source, code in cases.items():
            with self.subTest(code=code):
                self.assertIn(code, diagram.render_text(source))

    def test_arbitrary_unicode_never_raises_or_returns_non_svg(self):
        generator = random.Random(10342088688)
        alphabet = ''.join(chr(value) for value in range(32, 512))
        for _ in range(300):
            source = ''.join(generator.choice(alphabet) for _ in range(generator.randrange(120)))
            self.assertEqual("svg", ET.fromstring(diagram.render_text(source)).tag.rsplit("}", 1)[-1])


class FigureValidation(unittest.TestCase):
    def test_text_and_safe_svg_payloads_validate(self):
        self.assertEqual([], validate_file(fixture("figure-text-v2.xml")))
        self.assertEqual([], validate_file(fixture("figure-svg-v2.xml")))

    def test_schema_one_remains_valid(self):
        self.assertEqual([], validate_file(fixture("valid.xml")))

    def test_schema_one_textual_figure_still_renders(self):
        root = ET.parse(fixture("valid.xml")).getroot()
        output = render.page("legacy", "d" * 40, root, {})
        self.assertIn('<svg xmlns="http://www.w3.org/2000/svg"', output)
        self.assertIn("CD1_", output)  # legacy prose is visible, never fatal

    def test_unknown_payload_and_mixed_content_are_rejected(self):
        self.assertTrue(validate_file(fixture("figure-bad-payload-v2.xml")))
        self.assertTrue(validate_file(fixture("figure-mixed-v2.xml")))

    def test_unsafe_svg_is_rejected_after_relax_ng_accepts_the_canvas(self):
        problems = validate_file(fixture("figure-svg-unsafe-v2.xml"))
        self.assertTrue(problems)
        self.assertIn('id="f2gx"', '\n'.join(problems))
        self.assertIn("SVG_", '\n'.join(problems))

    def test_fetch_script_and_namespace_routes_are_closed(self):
        unsafe = [
            '<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://x"/></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><use href="#x"/></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><rect style="fill:red"/></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="url(https://x)"/></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:x="urn:x"><x:thing/></svg>',
            '<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg"/>',
        ]
        for source in unsafe:
            with self.subTest(source=source):
                self.assertTrue(svg.validate(source))


class FigureProjections(unittest.TestCase):
    def _root(self, name):
        return ET.parse(fixture(name)).getroot()

    def test_page_draws_text_source_as_graphical_svg(self):
        output = render.page(
            "figure-text", "a" * 40, self._root("figure-text-v2.xml"), {}
        )
        self.assertIn('<svg xmlns="http://www.w3.org/2000/svg"', output)
        self.assertIn("<rect", output)
        self.assertNotIn('<pre class="figure-source">', output)

    def test_page_renders_sanitized_inline_svg(self):
        output = render.page(
            "figure-svg", "b" * 40, self._root("figure-svg-v2.xml"), {}
        )
        self.assertIn("inline SVG escape hatch", output)
        self.assertIn("figure-drawing", output)
        self.assertNotIn("&lt;svg", output)

    def test_comment_labels_readable_fallbacks_and_has_no_less_than(self):
        for name, label in (
            ("figure-text-v2.xml", "Canvas Diagram 1 source"),
            ("figure-svg-v2.xml", "inline SVG source"),
        ):
            with self.subTest(name=name):
                output = render.comment("c" * 40, self._root(name), {})
                self.assertIn(label, output)
                self.assertIn("cannot display the picture", output)
                self.assertNotIn("<", output)


class FigureStoreAndCLI(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="canvas-figure-")
        self.addCleanup(shutil.rmtree, self.workspace, True)
        self.environment = dict(os.environ, OPENCLAW_WORKSPACE=self.workspace)

    def run_canvas(self, *arguments):
        return subprocess.run(
            [sys.executable, CANVAS] + list(arguments), env=self.environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

    def test_agents_create_both_payloads_without_editing_xml(self):
        created = self.run_canvas("create", "figures", "--problem", "P", "--expected-value", "E")
        self.assertEqual(0, created.returncode, created.stderr)
        textual = self.run_canvas(
            "insert", "figures", "--into", "root", "--type", "figure",
            "--text", 'box a 1 1 "A"', "--why", "The figure records the one relationship a reader must scan.",
        )
        self.assertEqual(0, textual.returncode, textual.stderr)
        svg_path = os.path.join(self.workspace, "safe.svg")
        with open(svg_path, "w", encoding="utf-8") as handle:
            handle.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="none" stroke="currentColor"/></svg>')
        inline = self.run_canvas(
            "insert", "figures", "--into", "root", "--type", "figure",
            "--svg-file", svg_path, "--why", "The supplied geometry cannot be expressed by Canvas Diagram 1.",
        )
        self.assertEqual(0, inline.returncode, inline.stderr)
        root = ET.parse(os.path.join(self.workspace, "state", "canvas", "figures.xml")).getroot()
        figures = list(root.iter("figure"))
        self.assertEqual("2", root.get("schema"))
        self.assertIsNone(figures[0].get("payload"))
        self.assertEqual("svg", figures[1].get("payload"))
        self.assertIn("<svg", figures[1].text)

    def test_text_and_svg_file_are_mutually_exclusive(self):
        result = self.run_canvas(
            "insert", "figures", "--into", "root", "--type", "figure",
            "--text", "x", "--svg-file", "x.svg", "--why", "Two payloads are ambiguous.",
        )
        self.assertEqual(2, result.returncode)


class VocabularyInvariant(unittest.TestCase):
    def test_schema_still_declares_exactly_eleven_element_names(self):
        grammar = ET.parse(os.path.join(ROOT, "schema", "canvas.rng"))
        names = {node.get("name") for node in grammar.iter() if node.tag.rsplit("}", 1)[-1] == "element"}
        self.assertEqual({"canvas", "section", "text", "list", "item", "table", "row", "cell", "figure", "link", "question"}, names)


if __name__ == "__main__":
    unittest.main()
