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


def new_text(node_id, content):
    """A `<text>` node at birth: the minted id, and v="1"."""
    node = ET.Element("text")
    node.set("id", node_id)
    node.set("v", BIRTH_VERSION)
    node.text = content
    return node


def parse(path):
    """Read a canvas from disk into a tree.

    Comments and processing instructions outside the root cannot be represented
    by ElementTree and are lost on a round trip. Nothing in `create` or `read`
    round-trips a file — `create` builds in memory and `read` prints the bytes
    on disk verbatim — so nothing here can lose one today. Whoever writes the
    four verbs, which do re-read before they write, has to decide that.
    """
    return ET.parse(path).getroot()


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
