"""Tests for `bin/canvas render`: the projection, and what it has to carry.

Everything here runs the real `bin/canvas` as a subprocess against a temporary
directory exported as OPENCLAW_WORKSPACE, like `tests/test_store.py`, and the
canvases the assertions are made against are built by driving the real
`insert` — one node at a time, each with its own reason, because that is the
only way a canvas is ever built.

These assert behaviour and not wording, matching the standing policy in
`tests/test_validate.py`: that a `<figure>` reaches the page carrying its
source, not the exact caption; that every question is marked, not the exact
word. The three assertions that *are* about exact structure are the done
condition's own, and they are mechanical on purpose — every element in the
vocabulary reaches the page, every `<question>` node carries a marker of its
own, and the index names every `<question>` id in the document and nothing
else.

**No test may touch the live workspace.** Every workspace here is made by
`tempfile.mkdtemp` and removed afterwards. The read-only tests share one,
built once by `setUpModule`, which is sound for exactly the reason the command
under test exists: `render` writes nothing, so no test in that group can leave
a mark another one reads. The tests that do change a workspace — a freeze, a
corrupted document, an empty one — make their own, fresh, per test.
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

sys.path.insert(0, ROOT)

SHA = re.compile(r"\A[0-9a-f]{40}\Z")

# node-identity.md section 1, and schema/canvas.rng's own pattern.
NODE_ID = re.compile(r"[a-z][a-hj-km-np-z2-9]{3}")

#: The eleven element names, minus the root. What "every element in the
#: vocabulary" means, read off `schema/canvas.rng`'s own list as `README.md`
#: states it.
VOCABULARY = [
    "section",
    "text",
    "list",
    "item",
    "table",
    "row",
    "cell",
    "figure",
    "link",
    "question",
]

#: A canvas with open questions, one with answered questions and no open ones,
#: and one with no question at all. The done condition asks for the index and
#: the markers to be asserted on a canvas that has open questions and on one
#: that has none; `only-answered` is the second of those two read the way that
#: bites hardest, because an index that dropped answered questions would still
#: pass on `no-questions`.
WITH_QUESTIONS = "with-open-questions"
ONLY_ANSWERED = "only-answered-questions"
NO_QUESTIONS = "no-questions"

#: Text with every character the page has to escape, on an ordinary node. A
#: projection that loses a `<` has silently rewritten the canvas.
AWKWARD = 'a & b < c > d "e"'

_workspace = None


def run_canvas(workspace, *args):
    """Run bin/canvas. Returns (exit code, stdout text, stderr text)."""
    environment = dict(os.environ)
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
        result.stdout.decode("utf-8", "replace"),
        result.stderr.decode("utf-8", "replace"),
    )


def insert(workspace, ledger_id, why, **flags):
    """One `insert`, returning the id it minted.

    The reason is the caller's, and every one of them below is written to the
    rule in `guidelines/canvas-why.md`: it says what the node is for, and where
    the node is an empty container it names the container the structure hangs
    from and says what would make the element unnecessary.
    """
    arguments = ["insert", ledger_id]
    for name, value in flags.items():
        option = "--%s" % name.replace("_", "-")
        if value is True:
            arguments.append(option)
        elif value is not None:
            arguments.extend([option, value])
    arguments.extend(["--why", why])
    code, stdout, stderr = run_canvas(workspace, *arguments)
    if code != 0:
        raise AssertionError("insert failed: %s\n%s" % (code, stderr))
    return stdout.splitlines()[0].split(": ", 1)[1]


def build(workspace, ledger_id, questions):
    """Build one canvas carrying every element in the vocabulary.

    `questions` says which `<question>` nodes it ends up with: both, answered
    only, or none. Everything else is the same in all three, so a difference
    between two rendered pages is a difference about questions and nothing
    else.
    """
    code, _, stderr = run_canvas(
        workspace,
        "create",
        ledger_id,
        "--problem",
        "The renderer does not exist, so a canvas can only be read as XML.",
        "--expected-value",
        "A page a reader can open, and tell from the canvas as it stands now.",
    )
    assert code == 0, stderr

    outer = insert(
        workspace,
        ledger_id,
        type="section",
        title="What the renderer has to carry",
        into="root",
        why=(
            "the page has to show a section rendering as a heading with the "
            "nodes under it, and this is the outer of the two levels the "
            "grammar allows; it would be unnecessary if the canvas were flat "
            "enough that no node needed a heading over it"
        ),
    )
    inner = insert(
        workspace,
        ledger_id,
        type="section",
        title="One level of nesting, and no more",
        into=outer,
        why=(
            "section %s is the outer level and this is the inner one, which is "
            "where the depth limit becomes visible: a third level is invalid, "
            "so this node is the deepest heading any canvas can ask the "
            "renderer for" % outer
        ),
    )
    insert(
        workspace,
        ledger_id,
        type="text",
        text=AWKWARD,
        into=inner,
        why=(
            "a paragraph whose characters are the ones HTML gives meaning to, "
            "so that a page which lost one of them fails loudly rather than "
            "quietly rewriting the canvas; it retires when escaping is "
            "checked somewhere a reader of this canvas can see"
        ),
    )
    a_list = insert(
        workspace,
        ledger_id,
        type="list",
        into="root",
        why=(
            "the bullets the page has to render hang from this container, and "
            "it is empty because one edit is one node; it would be wrong if "
            "the canvas had nothing to enumerate and a paragraph would carry "
            "the same reading"
        ),
    )
    insert(
        workspace,
        ledger_id,
        type="item",
        text="A bullet the page renders as a bullet.",
        into=a_list,
        why=(
            "list %s needs at least one item before a reader can tell a list "
            "from an empty box, and this is the first of them" % a_list
        ),
    )
    insert(
        workspace,
        ledger_id,
        type="item",
        text="A second bullet, so the order is visible.",
        into=a_list,
        why=(
            "one item in list %s cannot show that the page keeps the "
            "document's order, and two can; this one retires if order is "
            "asserted against the document directly" % a_list
        ),
    )
    table = insert(
        workspace,
        ledger_id,
        type="table",
        into="root",
        why=(
            "the comparison the page has to render as a grid hangs from this "
            "container, empty for the same reason every container is born "
            "empty; it would be unnecessary if nothing here had two columns"
        ),
    )
    row = insert(
        workspace,
        ledger_id,
        type="row",
        into=table,
        why=(
            "table %s holds rows and nothing else, so a table with no row "
            "renders as an empty grid; this is the row its cells go into"
            % table
        ),
    )
    insert(
        workspace,
        ledger_id,
        type="cell",
        text="left",
        into=row,
        why=(
            "row %s needs its first cell before the grid has a column at all, "
            "and a one-word header is what that cell holds" % row
        ),
    )
    insert(
        workspace,
        ledger_id,
        type="cell",
        text="right",
        into=row,
        why=(
            "a single cell in row %s would render as a grid of one column, "
            "which is a paragraph; the second column is what makes the table "
            "the right element for this" % row
        ),
    )
    insert(
        workspace,
        ledger_id,
        type="figure",
        text="canvas --render--> html\n   |\n   +-- never read back",
        into="root",
        why=(
            "rendering.md section 1 settles that a figure is its textual "
            "source and that this renderer does not draw it, and this node is "
            "the source a page has to show verbatim; it retires the day a "
            "schema v2 gives a figure something other than text to hold"
        ),
    )
    insert(
        workspace,
        ledger_id,
        type="link",
        href="https://malkovro.github.io/canvas/",
        text="The specifications this canvas is about.",
        into="root",
        why=(
            "a pointer out is one of the eleven elements and the page has to "
            "render it as something a reader can follow; it would be wrong if "
            "the target it names stopped being where these specs are published"
        ),
    )
    if questions in ("both", "answered"):
        insert(
            workspace,
            ledger_id,
            type="question",
            text="Does an answered question keep its entry in the index?",
            answered=True,
            into="root",
            why=(
                "rendering.md section 2 settles that an answered question is "
                "quiet rather than absent, and nothing tests that claim "
                "without a question that carries answered=true; it retires if "
                "that section is reopened and the answer changes"
            ),
        )
    if questions == "both":
        insert(
            workspace,
            ledger_id,
            type="question",
            text="Is an open question loud enough to find in a pasted page?",
            into="root",
            why=(
                "engineering-spec.md:108-110 makes findability the whole "
                "reason question exists, and an open question is what the "
                "index and the marker are measured against; it retires when "
                "somebody answers it with --answered"
            ),
        )
        insert(
            workspace,
            ledger_id,
            type="question",
            text="Are two open questions both named, or only the first?",
            into="root",
            why=(
                "one open question cannot show that the index names all of "
                "them rather than the first it met, and the page is pasted "
                "into a comment where a reader has nothing to count against; "
                "this retires if the index is checked against the document "
                "some other way"
            ),
        )


def setUpModule():
    """One temporary workspace, three canvases, built once.

    Sound because `render` writes nothing: no test below can leave a mark
    another one reads, which is the property `RenderWritesNothingToTheStore`
    asserts rather than assumes. The tests that do change a workspace make
    their own.
    """
    global _workspace
    _workspace = tempfile.mkdtemp(prefix="canvas-render-test-")
    build(_workspace, WITH_QUESTIONS, "both")
    build(_workspace, ONLY_ANSWERED, "answered")
    build(_workspace, NO_QUESTIONS, "none")


def tearDownModule():
    if _workspace:
        shutil.rmtree(_workspace, True)


class RenderTestCase(unittest.TestCase):
    """The shared, read-only workspace, and the two things every test needs."""

    def setUp(self):
        self.workspace = _workspace
        self.canvas_dir = os.path.join(_workspace, "state", "canvas")
        # The rule the whole suite rests on: never the live store.
        self.assertTrue(self.workspace.startswith(tempfile.gettempdir()))

    def render(self, ledger_id=WITH_QUESTIONS):
        code, stdout, stderr = run_canvas(self.workspace, "render", ledger_id)
        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        return stdout

    def document(self, ledger_id=WITH_QUESTIONS):
        path = os.path.join(self.canvas_dir, ledger_id + ".xml")
        return ElementTree.parse(path).getroot()

    def nodes(self, ledger_id=WITH_QUESTIONS):
        """Every node in the stored document, root excluded, in order."""
        root = self.document(ledger_id)
        return [element for element in root.iter() if element is not root]

    def question_ids(self, ledger_id=WITH_QUESTIONS):
        return [node.get("id") for node in self.document(ledger_id).iter("question")]

    def index(self, page):
        """The index block the page opens with, as text."""
        found = re.search(r'<nav class="question-index".*?</nav>', page, re.S)
        self.assertIsNotNone(found, "the page carries no question index")
        return found.group(0)

    def indexed_ids(self, page):
        """Every node id the index names, by the anchor each entry carries."""
        return re.findall(r'href="#(%s)"' % NODE_ID.pattern, self.index(page))

    def markers(self, page):
        """Every per-question marker in the body, in order."""
        return re.findall(
            r'<span class="question-marker">([^<]*)</span>', page
        )


class EveryElementInTheVocabularyIsCarried(RenderTestCase):
    """The done condition's first clause: the HTML carries every element in the
    vocabulary — section with its title and its one level of nesting, text,
    list/item, table/row/cell, figure, link, question."""

    def test_the_built_canvas_really_holds_every_element(self):
        # The premise the rest of this class rests on. A canvas that quietly
        # stopped carrying one of the eleven would make every assertion below
        # pass by vacuum.
        present = {node.tag for node in self.nodes()}
        self.assertEqual(set(VOCABULARY), present)

    def test_every_node_in_the_document_reaches_the_page(self):
        page = self.render()
        for node in self.nodes():
            self.assertIn(
                'id="%s"' % node.get("id"),
                page,
                "%s %s is not in the page" % (node.tag, node.get("id")),
            )

    def test_a_section_carries_its_title_as_a_heading(self):
        page = self.render()
        for node in self.document().iter("section"):
            self.assertRegex(page, r"<h[23]>%s</h[23]>" % re.escape(node.get("title")))

    def test_the_one_level_of_nesting_is_a_deeper_heading_inside_a_section(self):
        page = self.render()
        outer, inner = list(self.document().iter("section"))
        self.assertIsNotNone(
            re.search(
                r'<section class="section" id="%s">\s*<h2>%s</h2>.*'
                r'<section class="section" id="%s">\s*<h3>%s</h3>'
                % (
                    outer.get("id"),
                    re.escape(outer.get("title")),
                    inner.get("id"),
                    re.escape(inner.get("title")),
                ),
                page,
                re.S,
            ),
            "the inner section is not nested inside the outer one, under a "
            "deeper heading",
        )

    def test_a_text_node_is_a_paragraph_carrying_its_characters_escaped(self):
        page = self.render()
        awkward = [node for node in self.document().iter("text") if node.text == AWKWARD]
        self.assertEqual(1, len(awkward))
        self.assertIn(
            '<p class="text" id="%s">a &amp; b &lt; c &gt; d "e"</p>'
            % awkward[0].get("id"),
            page,
        )

    def test_a_list_is_a_list_and_its_items_are_items(self):
        page = self.render()
        a_list = list(self.document().iter("list"))[0]
        self.assertIn('<ul class="list" id="%s">' % a_list.get("id"), page)
        for item in a_list:
            self.assertIn(
                '<li class="item" id="%s">%s</li>' % (item.get("id"), item.text), page
            )

    def test_a_table_is_a_table_of_rows_of_cells(self):
        page = self.render()
        table = list(self.document().iter("table"))[0]
        self.assertIn('<table class="table" id="%s">' % table.get("id"), page)
        for row in table:
            self.assertIn('<tr class="row" id="%s">' % row.get("id"), page)
            for cell in row:
                self.assertIn(
                    '<td class="cell" id="%s">%s</td>' % (cell.get("id"), cell.text),
                    page,
                )

    def test_a_figure_carries_its_textual_source_verbatim(self):
        # rendering.md section 1: the figure a reader sees is the text the
        # canvas stores. Not drawn, not an image, not a script.
        page = self.render()
        figure = list(self.document().iter("figure"))[0]
        self.assertIn('<figure class="figure" id="%s">' % figure.get("id"), page)
        source = re.search(
            r'<figure class="figure" id="%s">\s*<pre class="figure-source">(.*?)</pre>'
            % figure.get("id"),
            page,
            re.S,
        )
        self.assertIsNotNone(source, page)
        # Escaped, and otherwise byte for byte: the `>` in the stored source is
        # `&gt;` in the page and nothing else about it has moved.
        self.assertEqual(
            figure.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
            source.group(1),
        )

    def test_no_figure_is_drawn_and_the_page_fetches_nothing(self):
        # The other half of the same decision, and the half that makes the page
        # standalone: no script, no image, no stylesheet to fetch, no drawing
        # step's output.
        page = self.render()
        for forbidden in ("<script", "<img", "<svg", 'rel="stylesheet"'):
            self.assertNotIn(forbidden, page)

    def test_a_link_is_an_anchor_at_its_href_carrying_its_label(self):
        page = self.render()
        link = list(self.document().iter("link"))[0]
        self.assertIn(
            '<a id="%s" href="%s">%s</a>'
            % (link.get("id"), link.get("href"), link.text),
            page,
        )

    def test_a_question_is_in_the_page_with_its_text(self):
        page = self.render()
        for node in self.document().iter("question"):
            self.assertIsNotNone(
                re.search(
                    r'<div class="question [a-z]+" id="%s">.*?%s'
                    % (node.get("id"), re.escape(node.text)),
                    page,
                    re.S,
                ),
                "question %s is not in the page with its text" % node.get("id"),
            )

    def test_the_page_is_one_standalone_html_document(self):
        page = self.render()
        self.assertTrue(page.startswith("<!DOCTYPE html>\n"), page[:40])
        self.assertTrue(page.rstrip().endswith("</html>"))
        self.assertIn('<meta charset="utf-8">', page)


class EveryQuestionCarriesAMarkerOfItsOwn(RenderTestCase):
    """The done condition's second clause, on a canvas that has open questions
    and on one that has none. Mechanical on purpose: 'loud' is a word two
    readers will rule differently, and this is the part that is not."""

    def assertEveryQuestionIsMarked(self, ledger_id):
        page = self.render(ledger_id)
        markers = self.markers(page)
        self.assertEqual(
            len(self.question_ids(ledger_id)),
            len(markers),
            "one marker per <question> node, and no other marker: %s" % markers,
        )
        for node in self.document(ledger_id).iter("question"):
            block = re.search(
                r'<div class="question [a-z]+" id="%s">(.*?)</div>' % node.get("id"),
                page,
                re.S,
            )
            self.assertIsNotNone(block, "question %s is not in the page" % node.get("id"))
            self.assertRegex(block.group(1), r'<span class="question-marker">\S')

    def test_every_question_is_marked_on_a_canvas_with_open_questions(self):
        self.assertEveryQuestionIsMarked(WITH_QUESTIONS)

    def test_every_question_is_marked_on_a_canvas_with_none_open(self):
        self.assertEveryQuestionIsMarked(ONLY_ANSWERED)

    def test_a_canvas_with_no_question_at_all_carries_no_marker(self):
        self.assertEqual([], self.question_ids(NO_QUESTIONS))
        self.assertEveryQuestionIsMarked(NO_QUESTIONS)
        self.assertEqual([], self.markers(self.render(NO_QUESTIONS)))

    def test_the_marker_says_which_state_the_question_is_in(self):
        # rendering.md section 2: an answered question keeps its marker and
        # loses its loudness. The marker is a word and not a colour, because a
        # colour is not something a reader — or this test — can point at.
        page = self.render(WITH_QUESTIONS)
        for node in self.document().iter("question"):
            block = re.search(
                r'<div class="question (\w+)" id="%s">(.*?)</div>' % node.get("id"),
                page,
                re.S,
            )
            answered = node.get("answered") == "true"
            self.assertEqual("answered" if answered else "open", block.group(1))
            marker = re.search(
                r'<span class="question-marker">([^<]*)</span>', block.group(2)
            ).group(1)
            self.assertIn("answered" if answered else "open", marker.lower())


class TheIndexNamesEveryQuestionAndNothingElse(RenderTestCase):
    """The done condition's third clause, on a canvas that has open questions
    and on one that has none: the page opens with an index of open questions
    that names every `<question>` id in the document and nothing else."""

    def assertIndexNamesExactlyTheQuestions(self, ledger_id):
        page = self.render(ledger_id)
        self.assertEqual(
            self.question_ids(ledger_id),
            self.indexed_ids(page),
            "the index names every <question> id in the document, in document "
            "order, and nothing else",
        )

    def test_the_index_names_every_question_on_a_canvas_with_open_ones(self):
        self.assertIndexNamesExactlyTheQuestions(WITH_QUESTIONS)

    def test_the_index_names_every_question_on_a_canvas_with_none_open(self):
        # rendering.md section 2: an answered question is quiet rather than
        # absent. An index that dropped them would pass on `no-questions` and
        # fail here, which is why this canvas exists.
        self.assertIndexNamesExactlyTheQuestions(ONLY_ANSWERED)

    def test_the_index_names_nothing_on_a_canvas_with_no_questions(self):
        self.assertIndexNamesExactlyTheQuestions(NO_QUESTIONS)
        self.assertEqual([], self.indexed_ids(self.render(NO_QUESTIONS)))

    def test_the_index_names_no_node_that_is_not_a_question(self):
        # The `and nothing else` half, said the other way round: not one of the
        # section, text, item, cell, figure or link ids is in it.
        page = self.render()
        questions = set(self.question_ids())
        for node in self.nodes():
            if node.get("id") in questions:
                continue
            self.assertNotIn(node.get("id"), self.index(page), node.tag)

    def test_the_index_says_of_each_entry_which_state_it_is_in(self):
        page = self.render()
        for node in self.document().iter("question"):
            entry = re.search(
                r'<li class="(\w+)" data-question="%s">' % node.get("id"),
                self.index(page),
            )
            self.assertIsNotNone(entry)
            self.assertEqual(
                "answered" if node.get("answered") == "true" else "open",
                entry.group(1),
            )

    def test_the_page_opens_with_the_index_before_any_node_of_the_document(self):
        page = self.render()
        first_node = min(
            page.index('id="%s"' % node.get("id")) for node in self.nodes()
        )
        self.assertLess(page.index('<nav class="question-index"'), first_node)


class TheOutputNamesTheShaItWasRenderedFrom(RenderTestCase):
    """The done condition's fourth clause: a rendered page pasted into a
    Basecamp comment can be told apart from the canvas as it stands now."""

    def test_the_page_carries_the_head_sha_in_full(self):
        code, stdout, stderr = run_canvas(self.workspace, "read", WITH_QUESTIONS)
        self.assertEqual(0, code, stderr)
        sha = stdout.splitlines()[0].split(": ", 1)[1]
        self.assertTrue(SHA.match(sha), sha)
        self.assertIn(sha, self.render())

    def test_the_sha_is_the_one_a_read_hands_out_for_that_canvas(self):
        # Rendering two canvases from the same repository at the same moment
        # gives the same sha: it is the repository's head, which is what a
        # later --base is compared against, not the file's last-touching commit.
        code, stdout, _ = run_canvas(self.workspace, "read", NO_QUESTIONS)
        self.assertEqual(0, code)
        self.assertIn(stdout.splitlines()[0].split(": ", 1)[1], self.render(NO_QUESTIONS))

    def test_the_page_says_it_is_a_projection_of_that_moment(self):
        page = self.render()
        header = re.search(r'<p class="rendered-from">(.*?)</p>', page, re.S)
        self.assertIsNotNone(header)
        self.assertIn("projection", header.group(1))


class RenderWritesNothingToTheStore(RenderTestCase):
    """A projection is one-way: never edited, never read back, and never a
    write. There is no form, no button, no route and no flag here that writes
    to a canvas."""

    def head(self):
        result = subprocess.run(
            [
                "git",
                "--git-dir=%s" % os.path.join(self.canvas_dir, ".git"),
                "--work-tree=%s" % self.canvas_dir,
                "rev-parse",
                "HEAD",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout.decode().strip()

    def listing(self):
        found = {}
        for directory, _, names in os.walk(self.canvas_dir):
            for name in names:
                path = os.path.join(directory, name)
                found[path] = os.stat(path).st_mtime_ns
        return found

    def test_rendering_changes_no_commit_and_no_file(self):
        before, head = self.listing(), self.head()
        self.render()
        self.render(NO_QUESTIONS)
        self.assertEqual(head, self.head())
        self.assertEqual(before, self.listing())

    def test_rendering_leaves_the_working_tree_clean(self):
        self.render()
        result = subprocess.run(
            [
                "git",
                "--git-dir=%s" % os.path.join(self.canvas_dir, ".git"),
                "--work-tree=%s" % self.canvas_dir,
                "status",
                "--porcelain",
            ],
            stdout=subprocess.PIPE,
        )
        self.assertEqual(b"", result.stdout)

    def test_render_takes_no_flag_that_could_write_anywhere(self):
        # The page goes to stdout and the shell decides where it lands. An
        # --output this command honoured is a projection somebody eventually
        # writes into state/canvas.
        code, stdout, stderr = run_canvas(self.workspace, "render", "--help")
        self.assertEqual(0, code, stderr)
        for forbidden in ("--output", "--why", "--into", "--after", "--base"):
            self.assertNotIn(forbidden, stdout)

    def test_stdout_is_the_page_and_nothing_but_the_page(self):
        # Not `read`'s shape: no `Canvas-Base:` line above the doctype, because
        # this output is a file somebody opens rather than a value somebody
        # feeds to the next write.
        page = self.render()
        self.assertFalse(page.startswith("Canvas-"))
        self.assertNotIn("Canvas-Base:", page)


class RenderIsAReadLikeTheOtherTwo(unittest.TestCase):
    """`read` and `history` write nothing, initialise nothing, and go on
    working on a frozen canvas. So does this one. Its own workspace, because a
    freeze is a write."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="canvas-render-frozen-")
        self.addCleanup(shutil.rmtree, self.workspace, True)

    def test_a_frozen_canvas_still_renders(self):
        build(self.workspace, "ended", "both")
        code, _, stderr = run_canvas(
            self.workspace,
            "freeze",
            "ended",
            "--why",
            "done: the renderer landed and this canvas is the page it was "
            "checked against; nodes are read-only history from here",
        )
        self.assertEqual(0, code, stderr)
        code, stdout, stderr = run_canvas(self.workspace, "render", "ended")
        self.assertEqual(0, code, stderr)
        self.assertIn("<!DOCTYPE html>", stdout)

    def test_a_render_does_not_initialise_a_repository(self):
        code, _, _ = run_canvas(self.workspace, "render", "never-created")
        self.assertEqual(1, code)
        self.assertFalse(os.path.exists(os.path.join(self.workspace, "state")))

    def test_rendering_a_canvas_that_is_only_a_root_is_a_page(self):
        # Every container is zeroOrMore, so a canvas with no node at all is a
        # state a real document passes through. The page still opens with the
        # index and still names the sha.
        code, _, stderr = run_canvas(
            self.workspace,
            "create",
            "just-born",
            "--problem",
            "P",
            "--expected-value",
            "V",
        )
        self.assertEqual(0, code, stderr)
        code, stdout, stderr = run_canvas(self.workspace, "render", "just-born")
        self.assertEqual(0, code, stderr)
        self.assertIn('<nav class="question-index"', stdout)


class RenderRefusesInTheShapeEveryRefusalTakes(unittest.TestCase):
    """A new subcommand's refusals are the tool's refusals: the message,
    Canvas-Node:, Canvas-About:, Canvas-Next:, Canvas-Exit:, and the same 1/2
    split — 1 for a wrong document, 2 for a wrong tool or invocation."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="canvas-render-refusal-")
        self.addCleanup(shutil.rmtree, self.workspace, True)

    def assertRefusalShape(self, stderr, code):
        lines = stderr.splitlines()
        # The message, prefixed with the command's name. The argument parser's
        # own refusals print `usage:` above it first, as they already do for
        # every other verb, so this is "a line" and not "the first line".
        self.assertTrue(
            [line for line in lines if line.startswith("canvas: ")], stderr
        )
        named = [
            line
            for line in lines
            if line.startswith(("Canvas-Node: ", "Canvas-About: "))
        ]
        self.assertTrue(named, stderr)
        self.assertEqual(
            1, len([1 for line in lines if line.startswith("Canvas-Next: ")])
        )
        self.assertIn("Canvas-Exit: %d — " % code, stderr)
        self.assertNotIn("Traceback", stderr)

    def test_no_canvas_for_that_ledger_id_is_one(self):
        code, stdout, stderr = run_canvas(self.workspace, "render", "no-such-row")
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertRefusalShape(stderr, 1)
        self.assertIn("Canvas-About: ledger id no-such-row", stderr)

    def test_an_invalid_stored_canvas_is_one_and_nothing_is_rendered(self):
        # A projection of a document that breaks the grammar would assert a
        # canvas that does not exist — and it would carry a sha, which is
        # exactly the artifact somebody pastes into a comment.
        build(self.workspace, "broken", "none")
        path = os.path.join(self.workspace, "state", "canvas", "broken.xml")
        with open(path, "w") as handle:
            handle.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<canvas ledger="broken" schema="1">\n'
                '  <decision id="ab2c" v="1">Not in the vocabulary.</decision>\n'
                "</canvas>\n"
            )
        code, stdout, stderr = run_canvas(self.workspace, "render", "broken")
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertRefusalShape(stderr, 1)

    def test_a_malformed_ledger_id_is_two(self):
        code, _, stderr = run_canvas(self.workspace, "render", "../../etc/passwd")
        self.assertEqual(2, code)
        self.assertRefusalShape(stderr, 2)

    def test_an_unset_workspace_is_two(self):
        code, _, stderr = run_canvas(None, "render", "anything")
        self.assertEqual(2, code)
        self.assertRefusalShape(stderr, 2)
        self.assertIn("OPENCLAW_WORKSPACE", stderr)

    def test_a_missing_ledger_id_is_two_and_names_the_argument(self):
        code, _, stderr = run_canvas(self.workspace, "render")
        self.assertEqual(2, code)
        self.assertRefusalShape(stderr, 2)
        self.assertIn("Canvas-About: command canvas render", stderr)

    def test_an_unrecognised_flag_is_two(self):
        build(self.workspace, "a-row", "none")
        code, _, stderr = run_canvas(
            self.workspace, "render", "a-row", "--output", "/tmp/somewhere.html"
        )
        self.assertEqual(2, code)
        self.assertRefusalShape(stderr, 2)


if __name__ == "__main__":
    unittest.main()
