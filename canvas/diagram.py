"""Canvas Diagram 1: the repository-owned textual figure language.

The language is deliberately small and deterministic.  It places boxes and
text on an explicit grid and joins boxes with one of three edge styles.  The
public renderer is total for every string: source mistakes become visible
diagnostic rows in the SVG, while valid statements continue to draw.
"""

import math
import re
import shlex
from xml.etree import ElementTree as ET


SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)

ID = re.compile(r"^[a-z][a-z0-9_-]*$")
INTEGER = re.compile(r"^[1-9][0-9]*$")
MAX_COORDINATE = 1000
CELL_WIDTH = 220
CELL_HEIGHT = 100
BOX_WIDTH = 180
BOX_HEIGHT = 60
PADDING = 30


def _svg(name, attributes=None, text=None):
    node = ET.Element("{%s}%s" % (SVG, name), attributes or {})
    node.text = text
    return node


def _tokens(line):
    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _coordinate(token):
    if not INTEGER.match(token):
        raise ValueError("CD1_COORDINATE")
    value = int(token)
    if value > MAX_COORDINATE:
        raise ValueError("CD1_COORDINATE")
    return value


def _label(tokens, index, line):
    if len(tokens) != index + 1:
        raise ValueError("CD1_ARITY")
    if not re.search(r'"(?:[^"\\]|\\.)*"\s*$', line):
        raise ValueError("CD1_LABEL")
    return tokens[index].replace(r"\n", "\n")


def _parse(source):
    statements = []
    boxes = {}
    diagnostics = []
    for number, line in enumerate(source.splitlines(), 1):
        if not line.strip():
            continue
        try:
            tokens = _tokens(line)
            command = tokens[0] if tokens else ""
            if command == "box":
                if len(tokens) != 5:
                    raise ValueError("CD1_ARITY")
                identity = tokens[1]
                if not ID.match(identity):
                    raise ValueError("CD1_ID")
                if identity in boxes:
                    raise ValueError("CD1_DUPLICATE_ID")
                row = _coordinate(tokens[2])
                column = _coordinate(tokens[3])
                statement = ("box", identity, row, column, _label(tokens, 4, line))
                boxes[identity] = statement
                statements.append((number, line, statement))
            elif command == "text":
                if len(tokens) != 4:
                    raise ValueError("CD1_ARITY")
                statements.append((number, line, (
                    "text", _coordinate(tokens[1]), _coordinate(tokens[2]),
                    _label(tokens, 3, line),
                )))
            elif command == "edge":
                if len(tokens) != 5:
                    raise ValueError("CD1_ARITY")
                if tokens[2] not in ("->", "--", "-x"):
                    raise ValueError("CD1_EDGE_KIND")
                if not ID.match(tokens[1]) or not ID.match(tokens[3]):
                    raise ValueError("CD1_ID")
                statements.append((number, line, (
                    "edge", tokens[1], tokens[2], tokens[3], _label(tokens, 4, line),
                )))
            else:
                raise ValueError("CD1_UNKNOWN")
        except (ValueError, IndexError) as error:
            code = str(error)
            diagnostics.append((
                number,
                code if code.startswith("CD1_") else "CD1_TOKENIZE",
                line,
            ))
        except Exception:
            diagnostics.append((number, "CD1_TOKENIZE", line))

    if not statements and not diagnostics:
        diagnostics.append((1, "CD1_EMPTY", ""))

    accepted = []
    for number, line, statement in statements:
        if statement[0] == "edge" and (
            statement[1] not in boxes or statement[3] not in boxes
        ):
            diagnostics.append((number, "CD1_MISSING_ENDPOINT", line))
        else:
            accepted.append(statement)
    return accepted, boxes, diagnostics


def _position(row, column):
    return (
        PADDING + (column - 1) * CELL_WIDTH,
        PADDING + (row - 1) * CELL_HEIGHT,
    )


def _multiline(parent, x, y, label, anchor="middle"):
    text = _svg("text", {
        "x": str(x), "y": str(y), "text-anchor": anchor,
        "font-family": "sans-serif", "font-size": "14",
        "fill": "currentColor",
    })
    lines = label.split("\n")
    for index, value in enumerate(lines):
        attrs = {"x": str(x)}
        attrs["dy"] = "0" if index == 0 else "18"
        text.append(_svg("tspan", attrs, value))
    parent.append(text)


def _edge(group, before, kind, after, label, boxes):
    left = boxes[before]
    right = boxes[after]
    lx, ly = _position(left[2], left[3])
    rx, ry = _position(right[2], right[3])
    x1, y1 = lx + BOX_WIDTH / 2, ly + BOX_HEIGHT / 2
    x2, y2 = rx + BOX_WIDTH / 2, ry + BOX_HEIGHT / 2
    group.append(_svg("line", {
        "x1": str(x1), "y1": str(y1), "x2": str(x2), "y2": str(y2),
        "stroke": "currentColor", "stroke-width": "2",
    }))
    if kind == "->":
        length = math.hypot(x2 - x1, y2 - y1) or 1
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        px, py = -uy, ux
        bx, by = x2 - 12 * ux, y2 - 12 * uy
        group.append(_svg("path", {
            "d": "M %.1f %.1f L %.1f %.1f L %.1f %.1f z" % (
                x2, y2, bx + 6 * px, by + 6 * py, bx - 6 * px, by - 6 * py,
            ),
            "fill": "currentColor",
        }))
    elif kind == "-x":
        group.append(_svg("path", {
            "d": "M %.1f %.1f l 12 12 M %.1f %.1f l -12 12"
            % (x2 - 6, y2 - 6, x2 + 6, y2 - 6),
            "fill": "none", "stroke": "currentColor", "stroke-width": "2",
        }))
    if label:
        _multiline(group, (x1 + x2) / 2, (y1 + y2) / 2 - 8, label)


def render_text(source):
    """Render any textual source as SVG; source errors are drawn, not raised."""
    try:
        statements, boxes, diagnostics = _parse(source or "")
        rows = [1]
        columns = [1]
        for statement in statements:
            if statement[0] == "box":
                rows.append(statement[2])
                columns.append(statement[3])
            elif statement[0] == "text":
                rows.append(statement[1])
                columns.append(statement[2])
        diagram_height = max(rows) * CELL_HEIGHT + PADDING * 2
        width = max(columns) * CELL_WIDTH + PADDING * 2
        if diagnostics:
            widest_diagnostic = max(
                "line %d [%s] %s" % diagnostic
                for diagnostic in diagnostics
            )
            width = max(width, PADDING * 2 + len(widest_diagnostic) * 8)
        height = diagram_height + max(1, len(diagnostics)) * 28
        root = _svg("svg", {
            "class": "figure-drawing", "viewBox": "0 0 %d %d" % (width, height),
            "role": "img", "aria-label": "Canvas Diagram 1",
        })
        drawing = _svg("g")
        root.append(drawing)
        for statement in statements:
            if statement[0] == "box":
                _, identity, row, column, label = statement
                x, y = _position(row, column)
                drawing.append(_svg("rect", {
                    "x": str(x), "y": str(y), "width": str(BOX_WIDTH),
                    "height": str(BOX_HEIGHT), "rx": "10", "fill": "none",
                    "stroke": "currentColor", "stroke-width": "2",
                    "aria-label": identity,
                }))
                _multiline(drawing, x + BOX_WIDTH / 2, y + 26, label)
            elif statement[0] == "text":
                _, row, column, label = statement
                x, y = _position(row, column)
                _multiline(drawing, x, y + 20, label, "start")
            else:
                _edge(drawing, *statement[1:], boxes)
        for index, (number, code, line) in enumerate(diagnostics):
            y = diagram_height + 20 + index * 28
            diagnostic = _svg("text", {
                "x": str(PADDING), "y": str(y), "font-family": "monospace",
                "font-size": "13", "fill": "#b42318",
            }, "line %d [%s] %s" % (number, code, line))
            root.append(diagnostic)
        return ET.tostring(root, encoding="unicode", short_empty_elements=True)
    except Exception as error:
        # Totality is a public contract.  Even an unanticipated implementation
        # defect remains visible in the projection instead of rejecting source
        # that the schema accepted.
        root = _svg("svg", {
            "class": "figure-drawing", "viewBox": "0 0 800 80",
            "role": "img", "aria-label": "Canvas Diagram 1 diagnostic",
        })
        root.append(_svg("text", {
            "x": "20", "y": "45", "font-family": "monospace",
            "font-size": "13", "fill": "#b42318",
        }, "line 0 [CD1_INTERNAL] %s" % type(error).__name__))
        return ET.tostring(root, encoding="unicode", short_empty_elements=True)
