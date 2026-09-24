"""The renderer: one canvas in, one projection out — a page, or a comment.

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
rendered page outlives the canvas it came from. A reader who has one has to be
able to tell it from the canvas as it stands now, and the sha is the only thing
that answers that.

**Two projections, one walk of the document.** `page` is the standalone HTML
document. `comment` is the same canvas as the block-level Markdown a Basecamp
comment actually renders, for the ledger row that rewrites its own live comment
in place. Both are reached through `render`, both come off one `store.read`,
both take their sha from the same place, and the three claims `rendering.md`
§3 says are not free — every `<question>` id in the index, only `<question>`
ids in it, a marker on every `<question>` node — are asserted against both.

`engineering-spec.md`'s *Projections* used to say the HTML page was
*"pasteable into a Basecamp comment"*. It is not, and that sentence has been
corrected there. Two facts about the transport kill it, and they compound: the
`basecamp` CLI converts a comment body from Markdown to HTML only when the body
holds no HTML at all, so one tag turns the conversion off for the *whole*
comment — including the ledger row's own status blocks around it; and Basecamp
then drops what its rich text does not accept, which is the doctype, `<html>`,
`<head>`, `<style>`, `<header>`, `<nav>` and `<figure>` — most of the page, and
every class the page's meaning is carried in. So the comment projection emits
**no raw HTML tag of any kind**: no `<` character reaches its output, and a
`<` in a canvas is written `&lt;`. That is the one rule everything below bends
to.
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

#: The two projections this module emits, named once. `PAGE` is the default
#: everywhere — every existing invocation of `bin/canvas render` predates the
#: second form and must keep getting the page it asked for.
PAGE = "page"
COMMENT = "comment"
FORMS = (PAGE, COMMENT)

#: What joins the cells of one table row once the row is a bullet, and what
#: separates a node's marker from its text. The em dash with spaces around it,
#: which is what the ledger row's own comment already uses to separate a thing
#: from what is said about it.
JOIN = " — "

#: What the index is called, and what it says when there is nothing in it.
#: Named once because both projections carry the index and a reader who has one
#: and then the other must not have to work out whether they are the same
#: claim.
INDEX_HEADING = "Open questions"
EMPTY_INDEX = (
    "No questions in this canvas — nothing is open and nothing has been "
    "asked."
)

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
    out.append("<h2>%s</h2>" % INDEX_HEADING)
    if not questions:
        out.append('<p class="empty">%s</p>' % EMPTY_INDEX)
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


# --- the comment projection --------------------------------------------------
#
# The second projection, and the one a ledger row carries. Its shape is not a
# taste decision: `orchestrator/basecamp.py` in `malkovro/ledger-orchestrator`
# records what a Basecamp comment body does with what it is handed, from
# observed failures with the todo and comment ids attached. The Markdown table
# extension is off, so a table is not parsed at all and leaks its own pipes as
# literal text. Hard wraps are off, so a single newline is a soft break and
# consecutive lines fold into one paragraph. Raw HTML is dropped rather than
# rendered — and worse, the CLI converts a body from Markdown *only* when the
# body holds no HTML, so one tag anywhere turns the conversion off for the whole
# comment, including the ledger row's own status blocks around this one.
#
# What is left is plain block-level Markdown: paragraphs and bullet lists,
# separated by blank lines. Every block below is one of those two, and no `<`
# reaches the output.


def _comment_text(value):
    """Character data, safe in a comment body. `None` is the empty string.

    Two characters and no more. `&` and `<` become entities — `&` first, so an
    `&lt;` a canvas really holds arrives as the four characters it is — because
    a `<` in the body is what costs the *whole* comment its formatting.

    Markdown's own active characters are left alone, deliberately. A `*` in a
    canvas turning into emphasis is a cosmetic drift in one node; a `<p>` in a
    canvas is the ledger row's status blocks arriving as literal asterisks.
    """
    return (value or "").replace("&", "&amp;").replace("<", "&lt;")


def _inline(value):
    """Character data for a block that is one line: a bullet, an index entry.

    Whitespace is folded here rather than left to the converter, because a
    newline inside a bullet is a lazy continuation of it — the one place a soft
    break changes what a reader sees rather than only how it is spelled.
    """
    return " ".join(_comment_text(value).split())


def _source(value):
    """A `<figure>`'s source, for the fenced block that keeps its shape.

    Escaped for `<` and nothing else. The CLI inspects the body and not the
    rendering, so a `<` inside a fence is still a tag as far as it is concerned
    — and an escaped one shows through to the reader as `&lt;`. That is the
    cost, it is paid only by a figure that holds a `<`, and it buys the one
    thing a diagram cannot do without: a fence is the only block-level Markdown
    that keeps its columns. `&` is left alone for the mirror reason — it costs
    the comment nothing and escaping it would show.
    """
    return (value or "").replace("<", "&lt;")


def _fence(source):
    """A fence long enough for this source: three backticks, or more.

    A figure whose source is itself fenced code would otherwise end the block
    early and spill the rest of the canvas into it.
    """
    longest = 0
    run = 0
    for character in source:
        run = run + 1 if character == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)


def _comment_index(questions):
    """The index, as the heading and the list under it. Two blocks, not one.

    The same claim the page makes and for the same reason `rendering.md` §2
    gives — and that reason is *about a comment reader*: they have the
    projection and not the canvas, so "here is every question this document
    has, and here is which ones are open" has to be something they can count.
    Every `<question>` is named, answered ones included, and nothing that is
    not a `<question>` is named at all.
    """
    if not questions:
        return ["**%s**" % INDEX_HEADING, EMPTY_INDEX]
    entries = []
    for node in questions:
        entries.append(
            "- `%s`%s%s%s%s"
            % (
                _inline(node.get("id")),
                JOIN,
                "answered" if _is_answered(node) else "open",
                JOIN,
                _inline(node.text),
            )
        )
    return ["**%s**" % INDEX_HEADING, "\n".join(entries)]


def _comment_question(node):
    """One `<question>`, with the marker of its own that every one carries.

    The marker is the same word the page prints, bolded so it is the first
    thing on the line, and the id is beside it so a reader can match a node to
    its entry in the index — the page links the two and a comment cannot.
    """
    text = _inline(node.text)
    return "**%s** `%s`%s" % (
        ANSWERED_LABEL if _is_answered(node) else OPEN_LABEL,
        _inline(node.get("id")),
        (JOIN + text) if text else "",
    )


def _comment_row(node):
    """One `<row>` as one line: its cells, joined.

    Empty cells drop out rather than rendering as gaps — a trailing dash says
    there is a column here whose value is missing, which is a claim the table
    did not make. A row whose cells are all empty still gets a line, because a
    repair may not change how many rows there are.
    """
    cells = [_inline(cell.text) for cell in node if cell.tag == "cell"]
    return JOIN.join(cell for cell in cells if cell) or "—"


def _comment_table(node):
    """One `<table>`: a header line, then one bullet per row after it.

    Not a Markdown table, and not because a table would be ugly: the extension
    is off, so the pipes and dashes arrive as literal text. This is the same
    repair `orchestrator/basecamp.py`'s `_unfold_markdown_tables` performs on
    authored text, for the same recorded reason, and it is done here so that
    nothing downstream has to recognise a table to fix it.
    """
    rows = [child for child in node if child.tag == "row"]
    if not rows:
        return []
    blocks = [_comment_row(rows[0])]
    if len(rows) > 1:
        blocks.append("\n".join("- %s" % _comment_row(row) for row in rows[1:]))
    return blocks


def _comment_figure(node):
    """One `<figure>`: its source in a fence, and the caption the page gives it.

    `rendering.md` §1 again — the figure is the text the canvas stores, and
    this renderer does not draw it either.
    """
    source = _source(node.text or "").strip("\n")
    fence = _fence(source)
    return [
        "%s\n%s\n%s" % (fence, source, fence),
        "figure `%s`%sthe textual source as stored"
        % (_inline(node.get("id")), JOIN),
    ]


def _comment_link(node):
    """One `<link>`: the label, or the target where there is no label yet."""
    href = node.get("href") or ""
    return "[%s](%s)" % (_inline(node.text) or _inline(href), _inline(href))


def _comment_node(node, out):
    """One node and everything under it, as blocks appended to `out`.

    Same walk as the page's, and the same rule at the end of it: an element
    this does not know is a canvas that could not exist — the validator has
    already accepted this document — and it is still rendered, as its text,
    because a projection that silently loses a node is worse than one that
    shows it plainly.

    What the comment cannot carry is the *depth* of a section: there are two
    heading levels on the page and there is one weight of bold here. The order
    of the blocks is the document's, so nothing is lost but the nesting, and
    the page is where a reader goes for that.
    """
    tag = node.tag
    if tag == "section":
        title = _inline(node.get("title"))
        if title:
            out.append("**%s**" % title)
        for child in node:
            _comment_node(child, out)
    elif tag == "list":
        items = ["- %s" % _inline(child.text) for child in node
                 if child.tag == "item"]
        if items:
            out.append("\n".join(items))
        for child in node:
            if child.tag != "item":
                _comment_node(child, out)
    elif tag == "item":
        out.append("- %s" % _inline(node.text))
    elif tag == "table":
        out.extend(_comment_table(node))
    elif tag == "row":
        out.append(_comment_row(node))
    elif tag == "figure":
        out.extend(_comment_figure(node))
    elif tag == "link":
        out.append(_comment_link(node))
    elif tag == "question":
        out.append(_comment_question(node))
    else:
        out.append(_comment_text(node.text or "").strip())


def comment(sha, root):
    """The whole canvas as one block of a Basecamp comment.

    The ledger row rewrites one comment in place on every transition and is
    deliberately the only author on that anchor, so this is not a comment: it
    is a block the row appends to its own, below everything it already says.
    It therefore opens by naming itself and the moment it is of, and it names
    the sha in full for the reason the page's header does — a projection
    outlives the canvas it came from, and the sha is the only thing that tells
    a reader which of the two they are holding.

    The order is the page's: the sha, then the index of questions, then the
    document. What a reader of the comment needs first is which canvas this is
    and which moment of it.
    """
    blocks = [
        "**Canvas**%srendered from `%s`" % (JOIN, _inline(sha)),
        "A projection of the canvas at that commit, not the canvas. Never "
        "edited and never read back; re-render to see it as it stands now.",
    ]
    blocks.extend(_comment_index(_questions(root)))
    for child in root:
        _comment_node(child, blocks)
    # One blank line between blocks and never two: a block boundary is one
    # separator, and the same document has to render as the same bytes for an
    # edited-in-place comment to be diffable.
    return "\n\n".join(block for block in blocks if block.strip()) + "\n"


def render(ledger_id, form=PAGE):
    """One ledger row's canvas, as a projection of it. Writes nothing.

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

    `form` picks which projection: the standalone HTML page (the default, and
    what every caller that names no form gets), or the block-level Markdown a
    Basecamp comment renders. It is not a different read — one `store.read`,
    one document, one sha, walked twice — and it is not a way to write: there
    is nothing this can be set to that puts a byte anywhere.
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
    root = ET.fromstring(body)
    if form == COMMENT:
        return comment(sha, root)
    return page(ledger_id, sha, root)
