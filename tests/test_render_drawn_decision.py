"""A figure that draws a DECISION must not sit under "No questions in this canvas".

The live lifecycle canvas draws open human gates inside one SVG figure and has
no `<question>` node, so the empty index used to say nothing was open on the
same page that showed an open decision. Presentation only: the one node state
(`answered` on `<question>`) is untouched, see `node-state.md`.
"""

import os
import sys
import unittest
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from canvas import render  # noqa: E402

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60">'
       '<text x="5" y="20" font-size="12">%s</text></svg>')


def root_with(label=None, question=False):
    root = ET.Element("canvas")
    if label is not None:
        figure = ET.SubElement(root, "figure", {"id": "f001", "v": "1", "payload": "svg"})
        figure.text = SVG % label
    if question:
        q = ET.SubElement(root, "question", {"id": "q001", "v": "1"})
        q.text = "Which one?"
    return root


class DrawnDecisionIsNotNoQuestions(unittest.TestCase):
    def page(self, root):
        return render.page("T-1", "a" * 40, root, {})

    def comment(self, root):
        return render.comment("a" * 40, root, {})

    def test_empty_canvas_still_says_no_questions(self):
        self.assertIn(render.EMPTY_INDEX, self.page(root_with()))
        self.assertIn(render.EMPTY_INDEX, self.comment(root_with()))

    def test_a_figure_without_a_decision_still_says_no_questions(self):
        self.assertIn(render.EMPTY_INDEX, self.page(root_with("ESTABLISHED")))

    def test_a_drawn_decision_replaces_the_no_questions_claim_on_page_and_comment(self):
        root = root_with("DECISION")
        for out in (self.page(root), self.comment(root)):
            self.assertNotIn("No questions in this canvas", out)
            self.assertIn(render.DRAWN_DECISION_INDEX, out)

    def test_a_real_question_wins_and_the_drawn_sentence_is_not_used(self):
        out = self.page(root_with("DECISION", question=True))
        self.assertNotIn(render.DRAWN_DECISION_INDEX, out)
        self.assertNotIn("No questions in this canvas", out)


if __name__ == "__main__":
    unittest.main()
