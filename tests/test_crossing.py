"""Tests for a node that crossed between a canvas's spaces, in both projections.

`problem-and-solution-space.md` at the top level of this repository, settled
2026-09-28, rules two things and this file asserts both of them:

1. **A node has crossed when a `move` naming it changed which `<section>` it
   sits in**, with *no section* counted as one of the two values. Not an
   `insert`, not a `replace`, not a reorder inside one section, and not a
   container's move seen from a child. Its crossing is the **latest** such
   move.
2. **A projection shows exactly one reason per crossed node** — that crossing's
   `--why`, verbatim, beside the full sha of its commit — **and no reason
   anywhere else.**

The second is the bound, and it is the reason `CountsTheReasonsAndBoundsThem`
exists: a page that showed every reason on every node would be the transcript
`product-spec.md`'s *What it is not* refuses, and it would grow with the log
while the document stayed the same size. Every assertion in that class fails
on such a page.

Everything here runs the real `bin/canvas` as a subprocess against a temporary
directory exported as OPENCLAW_WORKSPACE, like `tests/test_render.py` and
`tests/test_store.py`, and the canvases are built by driving the real `insert`
and the real `move` — one node at a time, each with its own reason — because a
crossing is a fact about the log and no fixture can carry one. What a fixture
*can* carry is the shape a document has at one moment, and
`tests/fixtures/two-spaces.xml` carries the live store's only one, which is
what `TheNearestSectionAncestorIsTheOnlyThingRead` is asserted against.

The assertions are made against **both** projections throughout. A claim that
held on the page and not in the comment would be a second renderer deciding
the ruling for itself, and a reader who has the comment has only the comment.

No test may touch the live workspace: every workspace here is made by
`tempfile.mkdtemp` and removed afterwards. They are shared across the read-only
tests for the reason `tests/test_render.py` gives — `render` writes nothing, so
no test can leave a mark another one reads.
"""

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
CANVAS = os.path.join(ROOT, "bin", "canvas")

sys.path.insert(0, ROOT)

from canvas import document  # noqa: E402

SHA = re.compile(r"\A[0-9a-f]{40}\Z")

#: One crossing line on the page: the reason as it was written, and the full
#: sha of the commit it came from. `class="crossing"` and not `crossing-label`
#: or `crossing-sha`, so counting these counts nodes and not spans.
PAGE_CROSSING = re.compile(r'class="crossing"')
PAGE_WHY = re.compile(r'<q class="crossing-why">(.*?)</q>', re.S)
PAGE_SHA = re.compile(r'<code class="crossing-sha">([0-9a-f]{40})</code>')

#: The same line in the comment: the label, the node's id, the reason, the sha.
#: The id is on the line because a comment has no anchors and a reader matching
#: this line to its node has nothing else.
COMMENT_CROSSING = re.compile(
    r"\*\*Carried across\*\* `([a-z][a-hj-km-np-z2-9]{3})` — (.*?) — "
    r"`([0-9a-f]{40})`"
)

#: One record of `bin/canvas history`: the commit, who wrote it, and the verb
#: and reason of the edit. Parsed here so a test can name *the move's* sha and
#: not merely some forty hex characters.
HISTORY = re.compile(
    r"Canvas-Commit: ([0-9a-f]{40})\nCanvas-Author: .*\n(\w+): (.*)"
)

#: The canvases these tests are made against.
#:
#: `CROSSED` carries every crossing case the ruling enumerates in one document,
#: so that the bound can be counted over all of them at once. `NO_CROSSING` is
#: the worked example's shape — two titled spaces, nothing ever moved — and is
#: the canvas the bound bites hardest on, because a renderer that printed a
#: reason per node would show a page full of them where the ruling says there
#: is not one. `NO_SECTIONS` is the other sixty-one canvases in the live store.
#: `OTHER_TITLES` is two sections that are not spaces at all. `AWKWARD` is one
#: crossing whose reason holds every character the two transports give meaning
#: to, because a reason is free text and a projection that lost one of them
#: would have rewritten somebody's words under their sha.
CROSSED = "a-node-crossed"
NO_CROSSING = "nothing-crossed"
NO_SECTIONS = "no-sections-at-all"
OTHER_TITLES = "sections-that-are-not-spaces"
AWKWARD = "a-reason-with-awkward-characters"
#: `FOLDED` is the three nodes that exist only inside their own parent —
#: `<item>`, `<row>` and `<cell>`. Each can be moved into a container in
#: another section and so can cross on its own, and each is a node the page
#: cannot put a `<p>` beside: a `<tr>` may hold only cells, and a folded node's
#: text is part of a block in the comment rather than a block of its own.
FOLDED = "folded-nodes-that-crossed"

#: Where each canvas's nodes ended up, filled in by `setUpModule`. Keyed by the
#: name the build gave the node, because a test that reads `nodes["carried"]`
#: says what it is about and a test that reads a minted id does not.
nodes = {}

#: The reason each `move` was written with, keyed the same way. The page has to
#: show these *verbatim*, so the test compares against the string the write was
#: given and not against a rendering of it.
reasons = {}

_workspace = None


def run_canvas(workspace, *args):
    """Run bin/canvas. Returns (exit code, stdout text, stderr text)."""
    environment = dict(os.environ)
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


def head(workspace, ledger_id):
    """The sha a write has to declare, which is what `read` hands out."""
    code, stdout, stderr = run_canvas(workspace, "read", ledger_id)
    assert code == 0, stderr
    return stdout.splitlines()[0].split(": ", 1)[1]


def insert(workspace, ledger_id, why, **flags):
    """One `insert`, returning the id it minted.

    The reason is the caller's, and every one below is written to the rule in
    `guidelines/canvas-why.md`: it says what the node is for, names the
    container a structural node hangs from, and says what would retire it.
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


def move(workspace, ledger_id, node_id, why, after=None, into=None):
    """One `move`, written against the current head. Returns the reason given.

    The reason comes back so the caller can keep it: what the page has to show
    is this string and not a rendering of it, and a test that re-derived it
    from the log would be asserting the renderer against itself.
    """
    arguments = ["move", ledger_id, node_id, "--base", head(workspace, ledger_id)]
    if after is not None:
        arguments.extend(["--after", after])
    if into is not None:
        arguments.extend(["--into", into])
    arguments.extend(["--why", why])
    code, _, stderr = run_canvas(workspace, *arguments)
    if code != 0:
        raise AssertionError("move failed: %s\n%s" % (code, stderr))
    return why


def build_crossed(workspace):
    """One canvas holding every case `problem-and-solution-space.md` §3 rules.

    One document rather than one per case, so the bound in §4 — one reason per
    crossed node, none anywhere else — can be counted over all of them at once.
    A page that is right about each case separately and wrong about the total
    is a page that has become a transcript.
    """
    code, _, stderr = run_canvas(
        workspace,
        "create",
        CROSSED,
        "--problem",
        "A reader cannot tell the problem this row started with from what is "
        "now understood.",
        "--expected-value",
        "The two spaces are visibly distinct, and the assumption that carried "
        "a node between them is on the page.",
    )
    assert code == 0, stderr

    problem = insert(
        workspace, CROSSED, type="section", title="Problem space", into="root",
        why=(
            "the break this row is about is drawn under this heading, which is "
            "the half a canvas is born with; it would be unnecessary if the "
            "canvas never grew a second space to tell it from"
        ),
    )
    solution = insert(
        workspace, CROSSED, type="section", title="Solution space", into="root",
        why=(
            "section %s holds the break and this one holds what is now "
            "understood, which is the distinction this row exists to make "
            "visible; it retires if the two spaces collapse back into one "
            "document order" % problem
        ),
    )
    nodes["problem"] = problem
    nodes["solution"] = solution

    # The ordinary case: born in the problem space, carried into the solution
    # space by one move with one reason.
    nodes["carried"] = insert(
        workspace, CROSSED, type="text", into=problem,
        text="Route on structured facts rather than on detector prose.",
        why=(
            "the option that would repair the coupling is written where the "
            "break is, because nobody has decided it yet; it retires when it "
            "is either taken or refused"
        ),
    )
    reasons["carried"] = move(
        workspace, CROSSED, nodes["carried"], into=solution,
        why=(
            "the pairwise question came back yes on 2026-09-28, so routing on "
            "structured facts stopped being a description of the break and "
            "became the shape of the answer"
        ),
    )

    # §3, first edge case: inserted straight into the solution section and
    # never moved. No crossing, no reason, and that is correct and not a gap.
    nodes["native"] = insert(
        workspace, CROSSED, type="text", into=solution,
        text="A node written where it stands, which is the normal case.",
        why=(
            "every one of the eleven nodes in "
            "duplicate-invoice-criterion-output-schema is in this state and "
            "the page has to show it carrying no reason; it retires if an "
            "insert is ever ruled a crossing"
        ),
    )

    # §3: a reorder inside one section. The nearest <section> ancestor does not
    # change, so it is not a crossing however good the reason is.
    nodes["stayer"] = insert(
        workspace, CROSSED, type="text", into=problem,
        text="The measurement of the break.",
        why=(
            "section %s needs a second node before an order inside it exists "
            "at all, and this is the node the reorder below is made against"
            % problem
        ),
    )
    nodes["reordered"] = insert(
        workspace, CROSSED, type="text", into=problem,
        text="The diagram the measurement explains.",
        why=(
            "this is the node moved within section %s and never out of it, "
            "which is the reorder problem-and-solution-space.md section 3 "
            "rules is not a crossing; it retires if a reorder becomes one"
            % problem
        ),
    )
    reasons["reordered"] = move(
        workspace, CROSSED, nodes["reordered"], after=None, into=problem,
        why=(
            "put the diagram under the measurement it explains, which is an "
            "order of my own making inside one space and not a decision about "
            "which space it belongs to"
        ),
    )

    # §3: moved more than once, and ended where it began. Two crossings, and
    # what is shown is the latest.
    nodes["returned"] = insert(
        workspace, CROSSED, type="text", into=problem,
        text="Whether the field split is structural.",
        why=(
            "this is the node that crosses twice and comes back, which is the "
            "round trip problem-and-solution-space.md section 3 rules is two "
            "crossings and not zero; it retires if that is reopened"
        ),
    )
    reasons["returned first"] = move(
        workspace, CROSSED, nodes["returned"], into=solution,
        why=(
            "the probe read as settling it, so this stopped looking like part "
            "of the break and started looking like part of the answer"
        ),
    )
    reasons["returned"] = move(
        workspace, CROSSED, nodes["returned"], into=problem,
        why=(
            "the probe settled nothing: it was run against one account, so "
            "this is back among the things not yet understood"
        ),
    )

    # §2: *none* is a value. A move out of a section into the ungrouped body
    # changes the nearest <section> ancestor and is a crossing.
    nodes["ungrouped"] = insert(
        workspace, CROSSED, type="text", into=solution,
        text="What the row was actually asked for.",
        why=(
            "this is the node moved out of section %s to the top level, which "
            "is where no section counts as one of the two values; it retires "
            "if no section stops being a value" % solution
        ),
    )
    reasons["ungrouped"] = move(
        workspace, CROSSED, nodes["ungrouped"], after=nodes["problem"],
        why=(
            "this is not one of the two spaces and never was — it is what the "
            "row was asked for, and it belongs beside the problem rather than "
            "inside either space"
        ),
    )

    # §3: a node carried by a move of its container. The container crossed, the
    # container carries the reason, and the passenger carries none.
    nodes["travelling"] = insert(
        workspace, CROSSED, type="section", title="Evidence", into="root",
        why=(
            "the container that is itself moved hangs here, so that the "
            "passenger inside it can be checked for the reason it must not "
            "carry; it would be unnecessary if a container were never moved"
        ),
    )
    nodes["passenger"] = insert(
        workspace, CROSSED, type="text", into=nodes["travelling"],
        text="A node that never had an edit of its own after its birth.",
        why=(
            "section %s travels with this node inside it and no commit names "
            "this one, which is what node-identity.md section 5 rules; it "
            "retires if a container's move starts naming its children"
            % nodes["travelling"]
        ),
    )
    reasons["travelling"] = move(
        workspace, CROSSED, nodes["travelling"], into=problem,
        why=(
            "the evidence is part of the break rather than a thing beside it, "
            "so it belongs under the problem space and not at the top level"
        ),
    )

    # The last write, so that the head is not a crossing's commit and a test
    # can tell the sha on a crossing line from the sha in the page's header.
    nodes["last"] = insert(
        workspace, CROSSED, type="text", into="root",
        text="The last edit, which moved nothing.",
        why=(
            "the head has to be a commit other than any crossing before a "
            "reader can tell a crossing's sha from the page's own; it retires "
            "when that is asserted some other way"
        ),
    )


def build_no_crossing(workspace):
    """The worked example's shape: two titled spaces, and nothing ever moved.

    `problem-and-solution-space.md` states that this canvas is a correct canvas
    with no crossings whose page carries no reasons, and that a ruling which
    made it defective would condemn the only canvas that has ever had the
    shape. This is that claim, as a test.
    """
    code, _, stderr = run_canvas(
        workspace,
        "create",
        NO_CROSSING,
        "--problem",
        "Nothing declares the contract between the criterion and the reducers.",
        "--expected-value",
        "A drafted criterion and schema, and cases compared old beside new.",
    )
    assert code == 0, stderr
    problem = insert(
        workspace, NO_CROSSING, type="section", title="Problem space",
        into="root",
        why=(
            "the break is drawn under this heading, exactly as czfj is in "
            "duplicate-invoice-criterion-output-schema; it would be "
            "unnecessary if this canvas never grew a second space"
        ),
    )
    solution = insert(
        workspace, NO_CROSSING, type="section", title="Solution space",
        into="root",
        why=(
            "section %s holds the break and this holds the options against "
            "cost, which is jub8's arrangement in the live store's only "
            "sectioned canvas; it retires if the two collapse into one" % problem
        ),
    )
    insert(
        workspace, NO_CROSSING, type="figure", into=problem,
        text='box break 1 1 "free prose"\nbox reducers 1 2 "7 reducers"\n'
             'edge break -> reducers "parsed by none"',
        why=(
            "the break needs to be scannable before anyone argues about it, "
            "and this is the picture of it; it retires if the coupling it "
            "draws is removed"
        ),
    )
    insert(
        workspace, NO_CROSSING, type="question", into=solution,
        text="Does the schema mechanism support a pairwise assessment?",
        why=(
            "this is the question that decides whether the row is a candidate "
            "at all, and it is open; it retires when somebody answers it with "
            "--answered"
        ),
    )
    insert(
        workspace, NO_CROSSING, type="text", into=solution,
        text="Wording, schema, or routing on structured facts.",
        why=(
            "the three options the row has to choose between are written down "
            "in the solution space they belong to; it retires when one of them "
            "is taken"
        ),
    )


def build_no_sections(workspace):
    """Sixty-one of the 62 canvases in the live store: no `<section>` at all.

    No node has a `<section>` ancestor, `S` is *none* everywhere and in every
    document, and no `move` can change it. The move below is real and its
    reason is real; no crossing is expressible, and nothing is wrong.
    """
    code, _, stderr = run_canvas(
        workspace,
        "create",
        NO_SECTIONS,
        "--problem",
        "A canvas accumulates prose nodes in document order and nothing moves.",
        "--expected-value",
        "A canvas that resolves rather than one that accumulates.",
    )
    assert code == 0, stderr
    insert(
        workspace, NO_SECTIONS, type="text", into="root",
        text="A node at the top level of a canvas with no section in it.",
        why=(
            "a canvas with no section is the ordinary canvas and this node is "
            "what a move inside one is made against; it retires if this canvas "
            "grows a section"
        ),
    )
    nodes["sectionless"] = insert(
        workspace, NO_SECTIONS, type="text", into="root",
        text="A second node, moved, and still in no section at all.",
        why=(
            "one node cannot show that a move changed nothing about which "
            "section a node sits in, and two can; it retires if this canvas "
            "grows a section for the move to cross"
        ),
    )
    reasons["sectionless"] = move(
        workspace, NO_SECTIONS, nodes["sectionless"], after=None, into="root",
        why=(
            "this reads before the node above it rather than after it, which "
            "is an order and not a decision about any space"
        ),
    )


def build_other_titles(workspace):
    """Two sections that are not spaces, and a node moved between them.

    A crossing, and its reason is shown. `problem-and-solution-space.md` §3
    rules this deliberate and the direct consequence of never reading the
    title: the mechanism cannot tell a "Problem space -> Solution space" move
    from an "Evidence -> Appendix" one, and it is not supposed to.
    """
    code, _, stderr = run_canvas(
        workspace,
        "create",
        OTHER_TITLES,
        "--problem",
        "A second person invents the shape without having read the first one.",
        "--expected-value",
        "Their sections get crossings on exactly the same terms.",
    )
    assert code == 0, stderr
    evidence = insert(
        workspace, OTHER_TITLES, type="section", title="Evidence", into="root",
        why=(
            "what was measured is gathered under this heading, and its title "
            "is deliberately not one of the two spaces; it would be "
            "unnecessary if this canvas had nothing measured in it"
        ),
    )
    appendix = insert(
        workspace, OTHER_TITLES, type="section", title="Appendix", into="root",
        why=(
            "section %s holds what is still being argued from and this holds "
            "what is not, which is the second heading a crossing needs; it "
            "retires if nothing is ever set aside" % evidence
        ),
    )
    nodes["set aside"] = insert(
        workspace, OTHER_TITLES, type="text", into=evidence,
        text="The eight-day count that turned out to be one account.",
        why=(
            "this is the measurement that is moved out of section %s once it "
            "stops carrying weight, which is what a crossing between two "
            "sections that are not spaces looks like" % evidence
        ),
    )
    reasons["set aside"] = move(
        workspace, OTHER_TITLES, nodes["set aside"], into=appendix,
        why=(
            "this is background now and not evidence: the count was one "
            "account, so it no longer argues for anything"
        ),
    )


def build_awkward(workspace):
    """One crossing whose reason holds `&`, `<`, `>` and `"`.

    §4 requires the reason reproduced verbatim, escaped for the transport and
    otherwise unaltered. The page has to escape it and the comment has to let
    no `<` through at all, and both have to hand the reader back the sentence
    that was written.
    """
    code, _, stderr = run_canvas(
        workspace,
        "create",
        AWKWARD,
        "--problem",
        "A reason is free text and a projection may not quietly rewrite it.",
        "--expected-value",
        "The sentence a reader sees is the sentence somebody wrote.",
    )
    assert code == 0, stderr
    problem = insert(
        workspace, AWKWARD, type="section", title="Problem space", into="root",
        why=(
            "the node whose carrying reason holds awkward characters starts "
            "under this heading; it would be unnecessary if the canvas had no "
            "second space for it to cross into"
        ),
    )
    solution = insert(
        workspace, AWKWARD, type="section", title="Solution space", into="root",
        why=(
            "section %s is where that node starts and this is where it lands, "
            "which is the second half a crossing needs; it retires if the two "
            "spaces collapse into one" % problem
        ),
    )
    nodes["awkward"] = insert(
        workspace, AWKWARD, type="text", into=problem,
        text="The node the awkward reason is written about.",
        why=(
            "section %s needs the node that is later carried across before "
            "there is a move to write a reason for; it retires if that move "
            "is undone" % problem
        ),
    )
    reasons["awkward"] = move(
        workspace, AWKWARD, nodes["awkward"], into=solution,
        why=(
            'the probe read "3.0 % parseable" & the threshold was < 5 %, so '
            'this is understood now and no longer part of the break > the row '
            'started with'
        ),
    )


def build_folded(workspace):
    """An `<item>`, a `<row>` and a `<cell>`, each carried across on its own.

    `schema/canvas.rng` keeps these three inside their own parent and nowhere
    else, so each crosses by being moved into a `<list>`, a `<table>` or a
    `<row>` that sits in the other section. Nothing in §2 treats them
    differently and nothing here does either; what differs is only where the
    line can be put, which is a presentation problem and this module's.

    The cell is moved **before** the row it sits in, deliberately: move the row
    first and the cell's own move no longer changes its nearest `<section>`
    ancestor, and the case would pass without ever being exercised.
    """
    code, _, stderr = run_canvas(
        workspace,
        "create",
        FOLDED,
        "--problem",
        "A bullet, a row and a cell can each be carried across on their own.",
        "--expected-value",
        "Each one shows its reason where the element it is about can hold it.",
    )
    assert code == 0, stderr
    here = insert(
        workspace, FOLDED, type="section", title="Where they start",
        into="root",
        why=(
            "the containers a folded node leaves hang under this heading; it "
            "would be unnecessary if the canvas had only one space for them "
            "to be in"
        ),
    )
    there = insert(
        workspace, FOLDED, type="section", title="Where they land", into="root",
        why=(
            "section %s holds what they leave and this holds what they arrive "
            "in, which is the second half any crossing needs; it retires if "
            "the two spaces collapse into one" % here
        ),
    )
    from_list = insert(
        workspace, FOLDED, type="list", into=here,
        why=(
            "the bullet that crosses hangs from this container, empty at birth "
            "because one edit is one node; it would be wrong if nothing in "
            "section %s were enumerated" % here
        ),
    )
    to_list = insert(
        workspace, FOLDED, type="list", into=there,
        why=(
            "list %s is the container the bullet leaves and this is the one it "
            "arrives in; it would be unnecessary if no bullet ever moved"
            % from_list
        ),
    )
    from_table = insert(
        workspace, FOLDED, type="table", into=here,
        why=(
            "the grid whose row and cell both cross hangs from this container, "
            "empty for the reason every container is born empty; it would be "
            "wrong if nothing in section %s had columns" % here
        ),
    )
    to_table = insert(
        workspace, FOLDED, type="table", into=there,
        why=(
            "table %s is the grid the row leaves and this is the one it "
            "arrives in; it would be unnecessary if no row ever moved"
            % from_table
        ),
    )
    from_row = insert(
        workspace, FOLDED, type="row", into=from_table,
        why=(
            "table %s holds rows and nothing else, and this is the row both "
            "the moving cell and the move of the row itself start from"
            % from_table
        ),
    )
    to_row = insert(
        workspace, FOLDED, type="row", into=to_table,
        why=(
            "row %s is where the moving cell starts and this is the row it "
            "lands in, inside table %s" % (from_row, to_table)
        ),
    )
    nodes["bullet"] = insert(
        workspace, FOLDED, type="item", text="A bullet that crosses.",
        into=from_list,
        why=(
            "list %s has no bullet until it has an item, and this is the one "
            "that is later carried into the other space" % from_list
        ),
    )
    nodes["cell"] = insert(
        workspace, FOLDED, type="cell", text="left", into=from_row,
        why=(
            "row %s has no column until it has a cell, and this is the cell "
            "that crosses on its own" % from_row
        ),
    )
    nodes["stay"] = insert(
        workspace, FOLDED, type="cell", text="right", into=from_row,
        why=(
            "a single cell in row %s renders as one column, which is a "
            "paragraph; this is the second column, and it never moves"
            % from_row
        ),
    )
    reasons["cell"] = move(
        workspace, FOLDED, nodes["cell"], into=to_row,
        why=(
            "this one measurement is understood now and belongs beside what "
            "was decided, while the row it came from is still part of the break"
        ),
    )
    nodes["row"] = from_row
    reasons["row"] = move(
        workspace, FOLDED, nodes["row"], into=to_table,
        why=(
            "the whole row is understood now, so it follows the cell that left "
            "it rather than staying among the things not yet decided"
        ),
    )
    reasons["bullet"] = move(
        workspace, FOLDED, nodes["bullet"], into=to_list,
        why=(
            "this bullet stopped being a symptom and became one of the things "
            "the row now holds to be true"
        ),
    )


def setUpModule():
    global _workspace
    _workspace = tempfile.mkdtemp(prefix="canvas-crossing-test-")
    build_crossed(_workspace)
    build_no_crossing(_workspace)
    build_no_sections(_workspace)
    build_other_titles(_workspace)
    build_awkward(_workspace)
    build_folded(_workspace)


def tearDownModule():
    if _workspace:
        shutil.rmtree(_workspace, True)


class CrossingTestCase(unittest.TestCase):
    """The shared, read-only workspace, and what every test below needs."""

    def setUp(self):
        self.workspace = _workspace
        # The rule the whole suite rests on: never the live store.
        self.assertTrue(self.workspace.startswith(tempfile.gettempdir()))

    def page(self, ledger_id=CROSSED):
        code, stdout, stderr = run_canvas(self.workspace, "render", ledger_id)
        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        return stdout

    def comment(self, ledger_id=CROSSED):
        code, stdout, stderr = run_canvas(
            self.workspace, "render", ledger_id, "--format", "comment"
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        return stdout

    def document(self, ledger_id=CROSSED):
        code, stdout, stderr = run_canvas(self.workspace, "read", ledger_id)
        self.assertEqual(0, code, stderr)
        body = stdout[stdout.index("<?xml"):]
        return ElementTree.fromstring(body)

    def history(self, node_id, ledger_id=CROSSED):
        """Every edit that named the node, oldest first, as (sha, verb, reason)."""
        code, stdout, stderr = run_canvas(
            self.workspace, "history", ledger_id, node_id
        )
        self.assertEqual(0, code, stderr)
        return HISTORY.findall(stdout)

    def move_shas(self, node_id, ledger_id=CROSSED):
        return [
            sha for sha, verb, _ in self.history(node_id, ledger_id)
            if verb == "move"
        ]

    def page_reasons(self, ledger_id=CROSSED):
        """Every reason the page shows, unescaped, in document order."""
        return [
            html.unescape(why)
            for why in PAGE_WHY.findall(self.page(ledger_id))
        ]

    def comment_crossings(self, ledger_id=CROSSED):
        """Every crossing line in the comment, as (node id, reason, sha)."""
        return COMMENT_CROSSING.findall(html.unescape(self.comment(ledger_id)))


class ANodeThatCrossedShowsItOnThePage(CrossingTestCase):
    """The page projection: a node that moved between sections shows both that
    it moved and the `--why` of the edit that carried it."""

    def test_the_carrying_reason_is_on_the_page_verbatim(self):
        self.assertIn(reasons["carried"], self.page_reasons())

    def test_the_line_says_the_node_was_carried_and_not_merely_placed(self):
        # "that it moved" is the half a reason alone does not say: a bare
        # sentence under a node reads as a caption on it.
        page = self.page()
        line = re.search(
            r'<p class="crossing">.*?%s.*?</p>' % re.escape(reasons["carried"]),
            page,
            re.S,
        )
        self.assertIsNotNone(line)
        self.assertIn("Carried across", line.group(0))

    def test_the_reason_sits_with_the_node_it_carried(self):
        # Adjacency is the whole of what makes the line readable: the reason is
        # about *this* node, and it falls between it and the next node of the
        # document rather than in a list at the end of the page.
        page = self.page()
        node = page.index('id="%s"' % nodes["carried"])
        reason = page.index(html.escape(reasons["carried"], quote=False))
        following = page.index('id="%s"' % nodes["native"])
        self.assertLess(node, reason)
        self.assertLess(reason, following)

    def test_the_sha_beside_it_is_the_crossing_commit_and_not_the_head(self):
        page = self.page()
        line = re.search(
            r'<p class="crossing">(?:(?!</p>).)*?%s(?:(?!</p>).)*?</p>'
            % re.escape(reasons["carried"]),
            page,
            re.S,
        )
        self.assertIsNotNone(line)
        sha = PAGE_SHA.search(line.group(0)).group(1)
        self.assertEqual(self.move_shas(nodes["carried"]), [sha])
        # The header's sha is the head, and the head is a later commit.
        rendered_from = re.search(
            r'Rendered from <code>([0-9a-f]{40})</code>', page
        ).group(1)
        self.assertNotEqual(rendered_from, sha)

    def test_every_sha_on_the_page_is_a_full_forty_characters(self):
        shown = PAGE_SHA.findall(self.page())
        self.assertEqual(len(shown), len(PAGE_CROSSING.findall(self.page())))
        for sha in shown:
            self.assertRegex(sha, SHA)

    def test_a_reason_holding_the_characters_html_gives_meaning_to_survives(self):
        # A reason is free text and a canvas may hold any of it. The page
        # escapes and does not drop: a projection that lost a `<` would have
        # rewritten somebody's words under their sha, which §4 refuses in the
        # same breath as it refuses truncation.
        self.assertIn(reasons["awkward"], self.page_reasons(AWKWARD))
        raw = PAGE_WHY.findall(self.page(AWKWARD))
        self.assertEqual(1, len(raw))
        for character in ("<", ">", "&"):
            self.assertNotIn(character, raw[0].replace("&amp;", "")
                             .replace("&lt;", "").replace("&gt;", "")
                             .replace("&quot;", ""))


class ANodeThatCrossedShowsItInTheComment(CrossingTestCase):
    """The comment projection: the same claim, for a reader who has only it.

    `problem-and-solution-space.md` §4: the bound is identical for the two, not
    because they look alike but because a reader who has one and then the other
    must not have to work out whether they are the same claim."""

    def test_the_carrying_reason_is_in_the_comment_verbatim(self):
        found = {
            node_id: why for node_id, why, _ in self.comment_crossings()
        }
        self.assertEqual(reasons["carried"], found[nodes["carried"]])

    def test_the_line_says_the_node_was_carried_and_names_it(self):
        body = html.unescape(self.comment())
        line = [
            each for each in body.splitlines()
            if reasons["carried"] in each
        ]
        self.assertEqual(1, len(line))
        self.assertIn("Carried across", line[0])
        self.assertIn(nodes["carried"], line[0])

    def test_the_sha_beside_it_is_the_crossing_commit_and_not_the_head(self):
        found = {
            node_id: sha for node_id, _, sha in self.comment_crossings()
        }
        self.assertEqual(
            self.move_shas(nodes["carried"]), [found[nodes["carried"]]]
        )
        self.assertNotEqual(
            head(self.workspace, CROSSED), found[nodes["carried"]]
        )

    def test_the_reason_follows_the_node_it_carried(self):
        body = html.unescape(self.comment())
        self.assertLess(
            body.index("Route on structured facts"),
            body.index(reasons["carried"]),
        )
        self.assertLess(
            body.index(reasons["carried"]),
            body.index("A node written where it stands"),
        )

    def test_no_less_than_sign_reaches_the_comment_even_from_a_reason(self):
        # The one rule the whole comment projection bends to: a `<` anywhere in
        # the body turns Basecamp's Markdown conversion off for the whole
        # comment, the ledger row's own status blocks included.
        self.assertNotIn("<", self.comment())

    def test_both_projections_name_the_same_crossed_nodes_with_the_same_reasons(self):
        for ledger_id in (
            CROSSED, NO_CROSSING, NO_SECTIONS, OTHER_TITLES, AWKWARD, FOLDED
        ):
            with self.subTest(canvas=ledger_id):
                self.assertEqual(
                    self.page_reasons(ledger_id),
                    [why for _, why, _ in self.comment_crossings(ledger_id)],
                )
                self.assertEqual(
                    PAGE_SHA.findall(self.page(ledger_id)),
                    [sha for _, _, sha in self.comment_crossings(ledger_id)],
                )


class CountsTheReasonsAndBoundsThem(CrossingTestCase):
    """The bound, and the test this whole ruling turns on.

    `problem-and-solution-space.md` §4: every crossed node carries exactly one
    reason, no node carries more than one, a node that has not crossed carries
    none, and every reason is accompanied by the full sha of the commit it came
    from. §5 says why one and not all of them: every reason on every node *is*
    the path, which is `git log` with a stylesheet, and a page built that way
    would grow monotonically with the number of edits while the document it
    projects stayed the same size — the transcript `product-spec.md`'s *What it
    is not* refuses in one sentence.

    **Every assertion in this class fails on a page that showed every reason on
    every node.** That is what it is for."""

    #: The four nodes in CROSSED that have a crossing, and no others. Written
    #: out rather than computed, because a test that derived this list the way
    #: the renderer does would assert the renderer against itself.
    CROSSED_NODES = ("carried", "returned", "ungrouped", "travelling")

    def test_exactly_the_crossed_nodes_carry_a_reason_on_the_page(self):
        page = self.page()
        self.assertEqual(
            len(self.CROSSED_NODES), len(PAGE_CROSSING.findall(page))
        )
        self.assertEqual(
            sorted(reasons[name] for name in self.CROSSED_NODES),
            sorted(self.page_reasons()),
        )

    def test_exactly_the_crossed_nodes_carry_a_reason_in_the_comment(self):
        found = self.comment_crossings()
        self.assertEqual(len(self.CROSSED_NODES), len(found))
        self.assertEqual(
            sorted(nodes[name] for name in self.CROSSED_NODES),
            sorted(node_id for node_id, _, _ in found),
        )

    def test_the_page_shows_far_fewer_reasons_than_the_canvas_has_edits(self):
        # The transcript's defining property is that it grows with the log
        # while the document stays the same size. This canvas has one reason
        # per commit and four crossings, so a page that printed the log would
        # show more than three times as many.
        edits = sum(
            int(node.get("v")) for node in self.document().iter()
            if node.get("v")
        )
        shown = len(PAGE_CROSSING.findall(self.page()))
        self.assertEqual(len(self.CROSSED_NODES), shown)
        self.assertLess(shown * 3, edits)

    def test_no_node_carries_two_reasons(self):
        page = self.page()
        for node in self.document().iter():
            node_id = node.get("id")
            if node_id is None:
                continue
            # Everything between this node's id and the next crossing line's
            # end holds at most one of them.
            self.assertLessEqual(
                len(PAGE_WHY.findall(self._own_markup(page, node_id))), 1,
                node_id,
            )
        # And the same said by counting: one line per crossed node, no more.
        self.assertEqual(
            len(self.CROSSED_NODES), len(PAGE_WHY.findall(page))
        )
        self.assertEqual(
            len(self.CROSSED_NODES), len(self.comment_crossings())
        )

    def _own_markup(self, page, node_id):
        """The page from this node's id to the next node's, whatever is between."""
        start = page.index('id="%s"' % node_id)
        rest = re.search(r'\sid="[a-z][a-hj-km-np-z2-9]{3}"', page[start + 1:])
        return page[start:start + 1 + rest.start()] if rest else page[start:]

    def test_an_insert_straight_into_the_solution_section_carries_nothing(self):
        # §3, the first edge case, and the one every node in the live store's
        # only sectioned canvas is in: it was born where it is, so there was no
        # assumption that carried it anywhere.
        page = self.page()
        self.assertNotIn(
            "Carried across", self._own_markup(page, nodes["native"])
        )
        for _, _, reason in self.history(nodes["native"]):
            self.assertNotIn(reason, self.page_reasons())
            self.assertNotIn(reason, html.unescape(self.comment()))

    def test_a_reorder_inside_one_section_carries_nothing(self):
        # §3: S(after) = S(before), so it is not a crossing however good the
        # reason is. The reason is real and it stays in the history.
        self.assertNotIn(reasons["reordered"], self.page_reasons())
        self.assertNotIn(reasons["reordered"], html.unescape(self.comment()))
        self.assertEqual(1, len(self.move_shas(nodes["reordered"])))

    def test_a_node_that_crossed_twice_shows_its_latest_crossing_only(self):
        # §3: the earlier ones are the path, and the path is in the history.
        self.assertIn(reasons["returned"], self.page_reasons())
        self.assertNotIn(reasons["returned first"], self.page_reasons())
        found = {node_id: why for node_id, why, _ in self.comment_crossings()}
        self.assertEqual(reasons["returned"], found[nodes["returned"]])
        # Two moves in the log, one reason on the page.
        shas = self.move_shas(nodes["returned"])
        self.assertEqual(2, len(shas))
        shown = {node_id: sha for node_id, _, sha in self.comment_crossings()}
        self.assertEqual(shas[-1], shown[nodes["returned"]])

    def test_a_container_carries_the_reason_and_its_passenger_carries_none(self):
        # §3: a move on a container names one node and the subtree travels
        # untouched, so no commit names the children and none of them crossed.
        # A rule that propagated the reason down would print one sentence N
        # times and attribute to each child a decision made about the group.
        page = self.page()
        self.assertIn(
            "Carried across", self._own_markup(page, nodes["travelling"])
        )
        self.assertNotIn(
            "Carried across", self._own_markup(page, nodes["passenger"])
        )
        found = [node_id for node_id, _, _ in self.comment_crossings()]
        self.assertIn(nodes["travelling"], found)
        self.assertNotIn(nodes["passenger"], found)


class ACanvasWithNoCrossingHasNoReasonInIt(CrossingTestCase):
    """§3 and §4: a canvas in which nothing has crossed renders with no reason
    anywhere, and that is every canvas in the live store on 2026-09-28.

    This is the reading of the bound that bites hardest. A renderer that
    printed a reason per node would show one under every node here, and this
    canvas is the shape the whole ruling was generalised from."""

    def test_the_two_spaces_are_still_both_on_the_page(self):
        page = self.page(NO_CROSSING)
        self.assertIn("Problem space", page)
        self.assertIn("Solution space", page)

    def test_not_one_reason_reaches_the_page(self):
        self.assertEqual([], PAGE_CROSSING.findall(self.page(NO_CROSSING)))
        self.assertEqual([], self.page_reasons(NO_CROSSING))

    def test_not_one_reason_reaches_the_comment(self):
        self.assertEqual([], self.comment_crossings(NO_CROSSING))
        self.assertNotIn("Carried across", self.comment(NO_CROSSING))

    def test_no_insert_reason_in_the_canvas_is_anywhere_in_either_projection(self):
        page = self.page(NO_CROSSING)
        body = self.comment(NO_CROSSING)
        for node in self.document(NO_CROSSING).iter():
            node_id = node.get("id")
            if node_id is None:
                continue
            for _, _, reason in self.history(node_id, NO_CROSSING):
                self.assertNotIn(reason, html.unescape(page))
                self.assertNotIn(reason, html.unescape(body))


class ACanvasWithNoSectionsHasNoCrossingToExpress(CrossingTestCase):
    """§3: no node has a `<section>` ancestor, `S` is *none* everywhere, and no
    `move` can change it. Sixty-one of the 62 canvases in the live store are in
    this state and render exactly as they render today."""

    def test_a_move_in_a_canvas_with_no_sections_is_not_a_crossing(self):
        self.assertEqual(1, len(self.move_shas(nodes["sectionless"], NO_SECTIONS)))
        self.assertEqual([], PAGE_CROSSING.findall(self.page(NO_SECTIONS)))
        self.assertEqual([], self.comment_crossings(NO_SECTIONS))

    def test_the_moves_reason_is_nowhere_in_either_projection(self):
        self.assertNotIn(
            reasons["sectionless"], html.unescape(self.page(NO_SECTIONS))
        )
        self.assertNotIn(
            reasons["sectionless"], html.unescape(self.comment(NO_SECTIONS))
        )

    def test_every_node_still_reaches_both_projections(self):
        # The ruling introduces no pressure on a canvas to grow sections: one
        # that has none renders exactly as it did.
        page = self.page(NO_SECTIONS)
        body = html.unescape(self.comment(NO_SECTIONS))
        for node in self.document(NO_SECTIONS).iter():
            if node.get("id") is None:
                continue
            self.assertIn('id="%s"' % node.get("id"), page)
            if node.text:
                self.assertIn(node.text, body)


class TitlesAreNeverRead(CrossingTestCase):
    """§1 and the *Deliberate* list: no rule, test, renderer or tool reads the
    characters of a `title`. A canvas with sections titled `Evidence` and
    `Appendix` gets crossings on exactly the same terms, which is the property
    that makes the ruling survive the second person who invents the shape
    without having read the first one."""

    def test_a_move_between_two_sections_that_are_not_spaces_is_a_crossing(self):
        self.assertIn(reasons["set aside"], self.page_reasons(OTHER_TITLES))
        found = {
            node_id: why
            for node_id, why, _ in self.comment_crossings(OTHER_TITLES)
        }
        self.assertEqual(reasons["set aside"], found[nodes["set aside"]])

    def test_a_crossing_line_holds_the_label_the_reason_and_the_sha_and_no_more(self):
        # Said precisely rather than by looking for titles: the whole text of
        # a crossing line is the three things §4 requires. Nothing about the
        # section it came from or went to is in it, because the renderer never
        # looked at either one.
        for ledger_id in (CROSSED, OTHER_TITLES):
            with self.subTest(canvas=ledger_id):
                page = self.page(ledger_id)
                lines = re.findall(r'<p class="crossing">.*?</p>', page, re.S)
                self.assertTrue(lines)
                for line in lines:
                    text = html.unescape(re.sub(r"<[^>]+>", "", line))
                    why = html.unescape(PAGE_WHY.search(line).group(1))
                    sha = PAGE_SHA.search(line).group(1)
                    self.assertEqual(
                        "Carried across — %s — %s" % (why, sha), text
                    )


class ANodeFoldedIntoItsParentCrossesOnTheSameTerms(CrossingTestCase):
    """`<item>`, `<row>` and `<cell>` exist only inside their own parent, and
    each can still be moved into a container in the other section. §2 treats
    them no differently and neither does the renderer; the only thing that
    changes is where the line can be put, which is presentation."""

    def test_all_three_cross_and_each_carries_exactly_one_reason(self):
        page = self.page(FOLDED)
        self.assertEqual(3, len(PAGE_CROSSING.findall(page)))
        self.assertEqual(
            sorted(reasons[name] for name in ("bullet", "row", "cell")),
            sorted(self.page_reasons(FOLDED)),
        )
        self.assertEqual(
            sorted(nodes[name] for name in ("bullet", "row", "cell")),
            sorted(node_id for node_id, _, _ in self.comment_crossings(FOLDED)),
        )

    def test_the_cell_that_never_moved_carries_nothing(self):
        found = [node_id for node_id, _, _ in self.comment_crossings(FOLDED)]
        self.assertNotIn(nodes["stay"], found)

    def test_a_bullets_line_is_inside_its_own_li(self):
        page = self.page(FOLDED)
        item = re.search(
            r'<li class="item" id="%s">.*?</li>' % nodes["bullet"], page, re.S
        )
        self.assertIsNotNone(item)
        self.assertIn(html.escape(reasons["bullet"], quote=False), item.group(0))

    def test_a_cells_line_is_inside_its_own_td(self):
        page = self.page(FOLDED)
        cell = re.search(
            r'<td class="cell" id="%s">.*?</td>' % nodes["cell"], page, re.S
        )
        self.assertIsNotNone(cell)
        self.assertIn(html.escape(reasons["cell"], quote=False), cell.group(0))

    def test_a_rows_line_is_a_row_of_its_own_and_never_loose_in_a_tbody(self):
        # A <tr> may hold only cells and a <tbody> may hold only rows, so the
        # one position left is a row of its own, spanning the columns of the
        # row it is about.
        page = self.page(FOLDED)
        line = re.search(r'<tr class="crossing-row">.*?</tr>', page, re.S)
        self.assertIsNotNone(line)
        self.assertIn(html.escape(reasons["row"], quote=False), line.group(0))
        self.assertRegex(line.group(0), r'<td class="crossing" colspan="\d+">')
        # Nothing loose: with every cell's own contents taken out, what is
        # left inside a tbody is rows and nothing else. A `<p>` sitting
        # directly in a tbody would be the invalid markup this shape avoids.
        for body in re.findall(r"<tbody>(.*?)</tbody>", page, re.S):
            between = re.sub(r"<td\b.*?</td>", "", body, flags=re.S)
            self.assertEqual(
                [], [tag for tag in re.findall(r"</?(\w+)", between)
                     if tag != "tr"],
            )

    def test_the_comment_names_each_of_them_by_id(self):
        body = html.unescape(self.comment(FOLDED))
        for name in ("bullet", "row", "cell"):
            with self.subTest(node=name):
                line = [
                    each for each in body.splitlines()
                    if reasons[name] in each
                ]
                self.assertEqual(1, len(line))
                self.assertIn("Carried across", line[0])
                self.assertIn(nodes[name], line[0])


class TheNearestSectionAncestorIsTheOnlyThingRead(unittest.TestCase):
    """§2, step 3, on the live store's one sectioned canvas.

    `tests/fixtures/two-spaces.xml` is that canvas's shape with its own ids and
    titles. `<section>` nests one level, so "nearest" is at most two elements
    up and is never ambiguous; *none* is a value and not an absence, which is
    what makes a move out of a section into the ungrouped body visible."""

    def setUp(self):
        with open(os.path.join(FIXTURES, "two-spaces.xml"), "rb") as handle:
            self.root = ElementTree.fromstring(handle.read())

    def test_a_node_outside_every_section_answers_none(self):
        # q39f and x6fk are the problem and the expected value the row was
        # born with, and they sit outside both spaces in the real canvas.
        self.assertIsNone(document.section_of(self.root, "q39f"))
        self.assertIsNone(document.section_of(self.root, "x6fk"))

    def test_a_node_in_a_section_answers_that_section(self):
        self.assertEqual("czfj", document.section_of(self.root, "lpaq"))
        self.assertEqual("jub8", document.section_of(self.root, "bwbs"))

    def test_a_section_answers_the_section_it_is_in_and_not_itself(self):
        self.assertIsNone(document.section_of(self.root, "czfj"))
        self.assertEqual("jub8", document.section_of(self.root, "nhf8"))

    def test_the_nearest_of_two_ancestors_is_the_inner_one(self):
        self.assertEqual("nhf8", document.section_of(self.root, "rh8b"))

    def test_a_node_that_is_not_in_the_document_answers_none(self):
        self.assertIsNone(document.section_of(self.root, "zzz9"))

    def test_the_title_is_never_what_the_answer_is_keyed_on(self):
        # Rename both spaces to something meaningless and every answer is
        # unchanged. This is §1's whole argument, as a test.
        for section in self.root.iter("section"):
            section.set("title", "")
        self.assertEqual("czfj", document.section_of(self.root, "lpaq"))
        self.assertEqual("jub8", document.section_of(self.root, "bwbs"))
        self.assertEqual("nhf8", document.section_of(self.root, "rh8b"))


if __name__ == "__main__":
    unittest.main()
