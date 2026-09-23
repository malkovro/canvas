"""The renderer: one canvas in, one standalone HTML page out.

`engineering-spec.md` section *The substrate* says what this is and what it is
not: *"The renderer is a separate, dumb, one-way function: XML in, HTML out. It
owns every presentation decision. Nothing in the canvas file is about how it
looks. Nobody edits the HTML; it is a projection and it is regenerated."*

So this module is a reader of the store and nothing else. It calls
`store.read`, which writes nothing, commits nothing and does not initialise a
repository, and it returns a string. There is no output path argument, no
template file, no configuration and no flag that could make it write to a
canvas: the one thing it can do with what it read is hand it back.

**Every presentation decision is here**, and every one of them is this module's
to change. The vocabulary gained no element, no attribute and no configuration
file to serve this renderer, which is the constraint the closed vocabulary
exists for. What this module reads out of a canvas is what was already in one:
eleven element names, `title`, `href`, `id`, `v`, and the one state
`node-state.md` settled — `answered` on `<question>`.

Two questions this renderer had to settle rather than inherit, both argued in
`rendering.md` at the top of this repository:

- **`<figure>` holds a textual source and this renderer does not draw it.** It
  prints the source verbatim, in a monospaced block, as the figure. Schema v1
  admits a textual source only (`schema/canvas.rng`, `<define name="figure">`),
  so inline SVG never reaches here in a valid canvas; and a drawing step is a
  dependency, an install and a subprocess this tool would then own. The figure
  a reader sees is the text the canvas stores, which is also the text that
  diffs.
- **The index names every `<question>` in the document, answered ones
  included, and says of each which it is.** An answered question is quiet in
  the index and quiet in the body — it keeps its marker and its entry, and
  loses the loudness. `node-state.md` left the presentation of an answered
  question free and required only that an open one be loud; this is the side
  taken, and `rendering.md` §2 says why omission was not.

The page carries the sha it was rendered from, in its own header, because a
rendered page is pasted into a Basecamp comment and outlives the canvas it came
from. A reader who has one has to be able to tell it from the canvas as it
stands now, and the sha is the only thing that answers that.
"""

from xml.etree import ElementTree as ET

from canvas import store


#: The one state a canvas carries, and the only attribute this module reads
#: that is not identity or structure. `node-state.md`: absence means open,
#: `true` is the only legal value, and `<question>` is the only element it may
#: appear on. Nothing here restates any other part of the vocabulary — what a
#: node may be is `schema/canvas.rng`'s business and the document reaching this
#: module has already been through the validator.
ANSWERED = "answered"

#: How each state is named in the page, in the index and on the node. One
#: string for one state, so the marker a reader sees beside a question and the
#: word beside its entry in the index cannot drift apart.
OPEN_LABEL = "Open question"
ANSWERED_LABEL = "Answered question"

#: `<section>` nests one level, so there are exactly two heading levels under
#: the page's own `<h1>`. A third level of section is invalid and never
#: arrives; the fallback keeps this a total function rather than an assertion
#: about a document the validator has already accepted.
HEADINGS = ["h2", "h3", "h4"]

STYLE = """
    :root { color-scheme: light dark; }
    body { margin: 0 auto; max-width: 46rem; padding: 2rem 1.25rem 4rem;
           font: 16px/1.55 -apple-system, "Segoe UI", system-ui, sans-serif; }
    h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
    h2 { font-size: 1.2rem; margin: 2rem 0 .5rem; }
    h3 { font-size: 1.05rem; margin: 1.5rem 0 .5rem; }
    .rendered-from { margin: 0 0 1.5rem; font-size: .8rem; opacity: .7; }
    .rendered-from code { font-size: .8rem; word-break: break-all; }
    .question-index { border: 2px solid currentColor; border-radius: .4rem;
                      padding: .75rem 1rem; margin: 0 0 2rem; }
    .question-index h2 { margin: 0 0 .5rem; font-size: 1.05rem; }
    .question-index ol { margin: 0; padding-left: 1.4rem; }
    .question-index li { margin: .25rem 0; }
    .question-index .answered { opacity: .55; }
    .question { border-left: .35rem solid currentColor; padding: .4rem 0 .4rem .75rem;
                margin: 1rem 0; }
    .question.answered { opacity: .55; border-left-style: dotted; }
    .question-marker { display: inline-block; font-size: .75rem;
                       letter-spacing: .06em; text-transform: uppercase; }
    .question-text { margin: .2rem 0 0; }
    .figure { margin: 1.25rem 0; }
    .figure-source { margin: 0; padding: .75rem; overflow-x: auto;
                     border: 1px solid currentColor; border-radius: .3rem;
                     font: 13px/1.4 ui-monospace, Menlo, Consolas, monospace; }
    figcaption { font-size: .78rem; opacity: .7; margin-top: .3rem; }
    table { border-collapse: collapse; margin: 1.25rem 0; }
    td { border: 1px solid currentColor; padding: .3rem .6rem; vertical-align: top; }
    .empty { opacity: .5; font-style: italic; }
"""


def _text(value):
    """Character data, escaped for HTML. `None` is the empty string."""
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _attribute(value):
    """An attribute value, escaped for HTML. Quoted with `"` everywhere here."""
    return _text(value).replace('"', "&quot;")


def _is_answered(node):
    return node.get(ANSWERED) == "true"


def _questions(root):
    """Every `<question>` in the document, in document order.

    Document order and not "open first", because the index is a map of the
    page and a map whose entries are in a different order from the thing it
    maps is a second document to keep in your head.
    """
    return list(root.iter("question"))


def _identity(node):
    """The `id` attribute the page gives a node: its canvas id, unchanged.

    Ids are unique across the whole store, so they are unique within one page
    by construction, and using them as the anchor is what lets the index link
    to a question and a reader link to a node from outside.
    """
    return ' id="%s"' % _attribute(node.get("id") or "")


def _question_index(questions):
    """The index the page opens with: every `<question>` id, and nothing else.

    Every question in the document, answered ones included. The entry for an
    answered one says `answered` and is quiet; the entry for an open one says
    `open` and is not. `rendering.md` §2 argues the inclusion: an index that
    silently dropped answered questions would be the one artifact in this
    system that cannot be checked against the document, and a reader could not
    tell "answered" from "never asked" — which is the failure
    `docs/drive-by-hand/FRICTION.md:109-110` recorded against a canvas that
    ended with no trace that anything had been asked.

    Nothing else is named here. No section, no text node, no link: the index
    is the question ledger and an id in it is a question's id.
    """
    out = ['<nav class="question-index" id="question-index">']
    out.append("<h2>Open questions</h2>")
    if not questions:
        out.append(
            '<p class="empty">No questions in this canvas — nothing is open '
            "and nothing has been asked.</p>"
        )
        out.append("</nav>")
        return out
    out.append("<ol>")
    for node in questions:
        answered = _is_answered(node)
        node_id = _attribute(node.get("id") or "")
        out.append(
            '<li class="%s" data-question="%s"><a href="#%s"><code>%s</code></a> '
            "— %s — %s</li>"
            % (
                "answered" if answered else "open",
                node_id,
                node_id,
                node_id,
                "answered" if answered else "open",
                _text(node.text),
            )
        )
    out.append("</ol>")
    out.append("</nav>")
    return out


def _question(node):
    """One `<question>`, with the marker of its own that every one carries.

    The marker is a word and not a colour, because the done condition is that
    every `<question>` node carries a marker of its own in the output and a
    colour is not something a reader of the HTML — or a test — can point at.
    An answered question keeps its marker and loses its loudness: that is the
    whole of the difference, and `node-state.md` left it free.
    """
    answered = _is_answered(node)
    return [
        '<div class="question %s"%s>' % (
            "answered" if answered else "open", _identity(node)
        ),
        '<span class="question-marker">%s</span>'
        % (ANSWERED_LABEL if answered else OPEN_LABEL),
        '<p class="question-text">%s</p>' % _text(node.text),
        "</div>",
    ]


def _figure(node):
    """One `<figure>`: its textual source, printed as the figure.

    The decision `rendering.md` §1 settles. Schema v1 admits a textual source
    only, so there is no inline SVG to pass through; and drawing it would mean
    a diagram toolchain — an install, a dependency and a subprocess — that this
    tool would then own, against a house rule of standard library only. What a
    reader sees is what the canvas stores and what the next diff will show.
    """
    return [
        '<figure class="figure"%s>' % _identity(node),
        '<pre class="figure-source">%s</pre>' % _text(node.text),
        "<figcaption>figure <code>%s</code> — the textual source as stored</figcaption>"
        % _attribute(node.get("id") or ""),
        "</figure>",
    ]


def _link(node):
    """One `<link>`: the label, or the target where there is no label yet.

    A pointer with an empty label is a legal intermediate state — one edit is
    one node, and the label arrives with the node — and rendering it as an
    empty anchor would make it unclickable at exactly the moment it is most
    useful.
    """
    href = node.get("href") or ""
    return [
        '<p class="link"><a%s href="%s">%s</a></p>'
        % (_identity(node), _attribute(href), _text(node.text) or _text(href))
    ]


def _node(node, depth, out):
    """One node and everything under it, appended to `out`.

    The eleven element names are the whole of what can arrive: the document
    has been through `canvas.validate` before it reaches here, so an element
    this does not know is not a case to handle but a canvas that could not
    exist. It is still rendered — as a paragraph carrying its text — rather
    than dropped, because a projection that silently loses a node is worse
    than one that shows it plainly.
    """
    tag = node.tag
    if tag == "section":
        heading = HEADINGS[min(depth, len(HEADINGS) - 1)]
        out.append('<section class="section"%s>' % _identity(node))
        out.append(
            "<%s>%s</%s>" % (heading, _text(node.get("title")), heading)
        )
        for child in node:
            _node(child, depth + 1, out)
        out.append("</section>")
    elif tag == "text":
        out.append('<p class="text"%s>%s</p>' % (_identity(node), _text(node.text)))
    elif tag == "list":
        out.append('<ul class="list"%s>' % _identity(node))
        for child in node:
            _node(child, depth, out)
        out.append("</ul>")
    elif tag == "item":
        out.append('<li class="item"%s>%s</li>' % (_identity(node), _text(node.text)))
    elif tag == "table":
        out.append('<table class="table"%s><tbody>' % _identity(node))
        for child in node:
            _node(child, depth, out)
        out.append("</tbody></table>")
    elif tag == "row":
        out.append('<tr class="row"%s>' % _identity(node))
        for child in node:
            _node(child, depth, out)
        out.append("</tr>")
    elif tag == "cell":
        out.append('<td class="cell"%s>%s</td>' % (_identity(node), _text(node.text)))
    elif tag == "figure":
        out.extend(_figure(node))
    elif tag == "link":
        out.extend(_link(node))
    elif tag == "question":
        out.extend(_question(node))
    else:
        out.append('<p class="text"%s>%s</p>' % (_identity(node), _text(node.text)))


def page(ledger_id, sha, root):
    """The whole page, as one string: a standalone HTML document.

    Standalone means what it says — one file, no stylesheet to fetch, no
    script, no font and no image. It is pasted into a Basecamp comment and
    opened from a file:// path, and a projection that needs a server to look
    right is not a projection of anything.

    The order is fixed and is the done condition's: the page opens with the
    index of questions, and the document follows it. The sha is above both,
    with the ledger id, because what a reader of a pasted page needs first is
    which canvas this is and which moment of it.
    """
    questions = _questions(root)
    out = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Canvas: %s</title>" % _text(ledger_id),
        "<style>%s</style>" % STYLE,
        "</head>",
        "<body>",
        "<header>",
        "<h1>Canvas: %s</h1>" % _text(ledger_id),
        # The sha, in full. A rendered page outlives the canvas it came from —
        # it is pasted into a comment — and this line is the only thing that
        # tells it apart from the canvas as it stands now. Forty characters,
        # for the reason `read` hands out forty: an abbreviation is not an
        # identity key as the log grows.
        '<p class="rendered-from">Rendered from <code>%s</code> — a projection '
        "of the canvas at that commit, not the canvas. Never edited and never "
        "read back; re-render to see it as it stands now.</p>" % _text(sha),
        "</header>",
    ]
    out.extend(_question_index(questions))
    out.append("<main>")
    for child in root:
        _node(child, 0, out)
    out.append("</main>")
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out) + "\n"


def render(ledger_id):
    """One ledger row's canvas, as a standalone HTML page. Writes nothing.

    A read, on exactly `read`'s terms: it goes through `store.read`, which
    writes no file, makes no commit and does not initialise a repository, and
    it works on a frozen canvas like every other read.

    **An invalid stored canvas is refused, at exit 1, with the diagnostics.**
    That is the one place this differs from `read`, and deliberately: `read`
    prints an invalid document because refusing to show it would make it
    unrepairable, and that reason is already served — `bin/canvas read` is
    right there and is the command a repair is made against. A *projection* of
    a document that breaks the grammar is a page asserting something about a
    canvas that does not exist, and it carries a sha, so it is exactly the
    artifact somebody pastes into a comment.
    """
    # No selector and no provenance: a projection is of the whole document,
    # and the header a read composes is for a caller that is about to write.
    sha, body, problems, _ = store.read(ledger_id)
    if problems:
        path = store.canvas_path(store.canvas_directory(), ledger_id)
        raise store.Refusal(
            "the canvas for %s is invalid, so there is nothing to render: a "
            "rendered page is a projection, and a projection of a document "
            "that breaks the grammar would assert a canvas that does not "
            "exist. Nothing was written" % ledger_id,
            "read it with `bin/canvas read %s`, which prints the document and "
            "these diagnostics together, and repair the node each one names "
            "with `bin/canvas replace %s <node-id> --why \"<why>\"`, one node "
            "at a time; then re-run `bin/canvas render %s`"
            % (ledger_id, ledger_id, ledger_id),
            about=["ledger id %s" % ledger_id, "canvas %s" % path],
            details=problems,
        )
    return page(ledger_id, sha, ET.fromstring(body))
