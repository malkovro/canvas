"""Building a canvas document, addressing a position in it, and serialising it.

This module makes the bytes that go on disk. It does not decide what is legal:
the vocabulary lives in `schema/canvas.rng` and the verdict is always
`canvas.validate.validate_file`'s. Nothing here checks an element name, an
attribute pattern or a nesting depth, so there is no second copy of the
vocabulary to drift out of step with the grammar. A writer necessarily *names*
what it writes — `canvas`, `ledger`, `text` — but naming what you are building
is not restating what is allowed, and every document this module produces is
handed to the validator before it reaches its final path.

## Addressing a position

`node-identity.md` left one gap open, in *Still open*: "`insert --after
<node-id>` cannot name the first position of an empty container. There is no
node to be after." This module answers it, so that the four verbs inherit an
answer instead of improvising one.

A position is named by exactly one of two things:

- `after(<node-id>)` — immediately after that sibling, in that sibling's parent.
- `into(<container-id>)` — as the **last** child of that container. For an empty
  container that is its first and only position, which is the gap.

The root is addressed by the reserved word `root`, because `<canvas>` carries no
`id` by design. `root` can never collide with a minted id: the id grammar is
`[a-z][a-hj-km-np-z2-9]{3}` and `o` is excluded from positions two to four, so
`r-o-o-t` fails the pattern by construction. (`head` does *not* fail it, so
`head` must never be used as a reserved word anywhere in this tool.)

Last child rather than first, because then `into C` always means "append to C"
for empty and non-empty alike, and a document built with repeated `into` comes
out in reading order.

## What a round trip preserves, and what it does not

The four verbs re-read the file before they write it, so this is now a live
question rather than a deferred one, and `parse` answers it: **a canvas is its
element tree, and nothing else.** Comments and processing instructions do not
survive a round trip, inside the root or outside it.

That is a decision and not an accident. `schema/canvas.rng` admits no comment
as content — the vocabulary is eleven element names and their attributes — so a
comment in a canvas is not part of the document the schema defines, and no
reader of a canvas can be relying on one. Preserving them would mean carrying a
parallel representation of the file through every edit for the sake of text the
grammar says is not there. What a canvas records instead is its history, which
is where a comment would have gone: the reason is the commit subject.

The practical reach of this is small, because every canvas on disk was written
by `serialise`, which emits no comments. Only a hand-edited file can lose one,
and it loses it on its first edit, visibly, in that edit's own diff.
"""

from xml.etree import ElementTree as ET

#: The schema version this writer emits. Pinned by `schema/canvas.rng` to the
#: literal 1; a file declaring anything else fails against the grammar.
SCHEMA_VERSION = "1"

#: `node-identity.md` section 4: a node is born at v="1".
BIRTH_VERSION = "1"

#: How `<canvas>` is named when a position is given, since it carries no `id`.
ROOT = "root"

INDENT = "  "
DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'


class PositionProblem(Exception):
    """A position named an id that is not in this document."""


class NotWellFormed(Exception):
    """The file on disk is not XML, so there is no tree to edit."""


def new_canvas(ledger_id):
    """The childless root, which is the whole output of the creation commit.

    `node-identity.md` section 4: "The canvas's creation commit creates the root
    only." The grammar admits it — every container is `zeroOrMore` — so a
    childless `<canvas/>` is a state the document really passes through.
    """
    root = ET.Element("canvas")
    root.set("ledger", ledger_id)
    root.set("schema", SCHEMA_VERSION)
    return root


def new_node(node_id, tag, version=BIRTH_VERSION, text=None, attributes=None):
    """A node of any type: its `id` and `v` first, then whatever else it carries.

    Which element names exist, and which attributes each one requires, is
    `schema/canvas.rng`'s business and not this function's. It will build a
    `<decision>` node quite happily; what stops that document ever reaching a
    canvas's path is the validator, which is the only thing here that ever
    decides what is legal. Nothing in this module is a second copy of the
    vocabulary.

    Attribute order is cosmetic, and chosen to match `tests/fixtures/valid.xml`:
    `id`, then `v`, then the rest. An attribute whose value is None is not
    written, so a caller can hand over the flags it was given without first
    working out which of them were supplied.
    """
    node = ET.Element(tag)
    node.set("id", node_id)
    node.set("v", version)
    for name, value in (attributes or {}).items():
        if value is not None:
            node.set(name, value)
    if text is not None:
        node.text = text
    return node


def new_text(node_id, content):
    """A `<text>` node at birth: the minted id, and v="1"."""
    return new_node(node_id, "text", text=content)


def parse(path):
    """Read a canvas from disk into a tree.

    Comments and processing instructions are lost on a round trip, which is
    *What a round trip preserves* above: a canvas is its element tree. The four
    verbs re-read before they write, and that is the decision they inherit.

    A file that is not well-formed XML is not a tree at all, and that is a
    different thing from a file whose tree breaks the grammar — the second is
    the validator's verdict and arrives with diagnostics naming the node. This
    raises `NotWellFormed` so a caller can tell the two apart and say which.

    The character data of an element that has children is dropped, because in
    this vocabulary there is no such thing: no element in the grammar holds
    character data and child elements at once, so what a parser finds there is
    `serialise`'s own indentation and nothing else. Keeping it would make an
    emptied container render as `<table id="z9sf" v="1">\n    </table>` after
    the removal of its last child — the whitespace, now the only thing left,
    having been promoted to content by a `remove` that never meant to write
    any. A leaf's character data is its content and is untouched.
    """
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise NotWellFormed("%s: not well-formed XML: %s" % (path, error))
    for element in root.iter():
        if len(element):
            element.text = None
    return root


def _parents(root):
    """Map each element to its parent. ElementTree has no parent pointer."""
    found = {}
    stack = [root]
    while stack:
        element = stack.pop()
        for child in element:
            found[id(child)] = element
            stack.append(child)
    return found


def find(root, node_id):
    """The element carrying that `id`, or None. The root is named `root`."""
    if node_id == ROOT:
        return root
    for element in root.iter():
        if element.get("id") == node_id:
            return element
    return None


def ids_in(root):
    """Every node's id, in document order.

    The root is not a node and carries none, so it is not in the list. A node
    that carries no `id` at all is not either: this keys nodes by the thing the
    grammar makes mandatory, and a document holding a node without one is a
    document the validator refuses and whose diagnostics say so.
    """
    return [
        element.get("id")
        for element in root.iter()
        if element is not root and element.get("id") is not None
    ]


def select(root, node_ids=(), node_types=()):
    """The nodes any selector names, in a fresh root. Returns (selection, missing).

    **Selectors union.** A node is selected if its `id` is one of `node_ids`
    **or** its element name is one of `node_types`. Not intersection: an `id`
    intersected with a type is either that one node or nothing, which is a
    question nobody asks, and one rule that covers repeats and mixtures alike
    is worth more than two.

    **A selected node brings its subtree, once.** A selected node that is a
    descendant of another selected node is printed in place, inside it, and not
    again on its own — so the count of top-level elements in the selection is
    never a count of matches, and reading the selection twice never reads one
    node twice.

    `missing` is the ids that named nothing, in the order they were given. An
    id is an assertion that a node exists, so a caller that refuses on it has a
    list to name; a type is a predicate, and "none" is its answer rather than
    its failure, so an unmatched type is not reported here at all.

    **The selection is a projection and is not claimed to validate.** Selecting
    a `<cell>` without its `<row>` produces something the grammar refuses, and
    that is correct: the stored file is the document and is the thing that
    validates. This builds a view of part of it.
    """
    wanted_ids = set(node_ids or ())
    wanted_types = set(node_types or ())
    selection = ET.Element(root.tag)
    for name, value in root.items():
        selection.set(name, value)

    found = set()

    def walk(element):
        for child in element:
            if child.get("id") in wanted_ids or child.tag in wanted_types:
                selection.append(child)
                found.update(each for each in ids_in(child) if each in wanted_ids)
                if child.get("id") in wanted_ids:
                    found.add(child.get("id"))
            else:
                walk(child)

    walk(root)
    missing = [each for each in (node_ids or ()) if each not in found]
    return selection, missing


def place_after(root, sibling_id, node):
    """Put `node` immediately after the node named `sibling_id`."""
    if sibling_id == ROOT:
        raise PositionProblem(
            "cannot insert after the root: the root has no siblings"
        )
    sibling = find(root, sibling_id)
    if sibling is None:
        raise PositionProblem("no node with id %s in this canvas" % sibling_id)
    parent = _parents(root).get(id(sibling))
    if parent is None:
        raise PositionProblem("no node with id %s in this canvas" % sibling_id)
    parent.insert(list(parent).index(sibling) + 1, node)


def place_into(root, container_id, node):
    """Put `node` at the end of the children of `container_id`.

    For an empty container this is its first and only position, which is the
    addressing gap `node-identity.md` left open.
    """
    container = find(root, container_id)
    if container is None:
        raise PositionProblem("no node with id %s in this canvas" % container_id)
    container.append(node)


def parent_of(root, node_id):
    """The element the named node hangs from.

    None for the root, which has none, and None for an id that is not in this
    document. ElementTree has no parent pointer, so this is a walk.
    """
    node = find(root, node_id)
    if node is None or node is root:
        return None
    return _parents(root).get(id(node))


def replace_node(root, node_id, replacement):
    """Put `replacement` at the position the named node currently occupies.

    The position is the node's index in its own parent, so nothing around it
    moves: `replace` changes one node and leaves every sibling's id, `v`,
    content and order exactly as they were.
    """
    node = find(root, node_id)
    parent = parent_of(root, node_id)
    if node is None or parent is None:
        raise PositionProblem("no node with id %s in this canvas" % node_id)
    parent[list(parent).index(node)] = replacement


def detach(root, node_id):
    """Take the named node out of the document and return it.

    `remove` throws away what this returns and `move` puts it back somewhere
    else, which is why it hands the element back rather than swallowing it.
    """
    node = find(root, node_id)
    parent = parent_of(root, node_id)
    if node is None or parent is None:
        raise PositionProblem("no node with id %s in this canvas" % node_id)
    parent.remove(node)
    return node


def contains(ancestor, candidate):
    """Is `candidate` the element `ancestor` itself, or one of its descendants?

    What `move` asks before it moves anything. A node moved inside itself would
    leave the document altogether, taking its children with it, and the commit
    that did it would name one node while N vanished.
    """
    return any(element is candidate for element in ancestor.iter())


def _escape_text(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attribute(value):
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "&#10;")
        .replace("\r", "&#13;")
        .replace("\t", "&#9;")
    )


def _start_tag(element):
    parts = [element.tag]
    for name, value in element.items():
        parts.append('%s="%s"' % (name, _escape_attribute(value)))
    return " ".join(parts)


def _render(element, depth, out):
    pad = INDENT * depth
    children = list(element)
    if children:
        out.append("%s<%s>" % (pad, _start_tag(element)))
        for child in children:
            _render(child, depth + 1, out)
        out.append("%s</%s>" % (pad, element.tag))
    elif element.text:
        out.append(
            "%s<%s>%s</%s>"
            % (pad, _start_tag(element), _escape_text(element.text), element.tag)
        )
    else:
        out.append("%s<%s/>" % (pad, _start_tag(element)))


def serialise(root):
    """The document as text: declaration, two-space indent, one node per line.

    The shape `tests/fixtures/valid.xml` already shows. Written here rather than
    taken from `ElementTree.tostring` because that writes `<list />` with a space
    where the fixture writes `<list/>`, and post-processing the difference out
    would corrupt any node whose character data happens to contain the same
    three characters.

    No element in the grammar holds character data and child elements at once,
    so a node is either a one-line leaf or a block with children.
    """
    out = [DECLARATION]
    _render(root, 0, out)
    return "\n".join(out) + "\n"
