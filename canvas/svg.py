"""Validation and inert reserialization for schema-v2 inline SVG figures."""

import re
from xml.etree import ElementTree as ET


SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)

MAX_BYTES = 100 * 1024
MAX_ELEMENTS = 256
MAX_DEPTH = 16
ELEMENTS = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline",
    "polygon", "text", "tspan", "title", "desc",
}
COMMON = {
    "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
    "opacity", "transform", "role", "aria-label",
}
ATTRIBUTES = {
    "svg": COMMON | {"viewBox", "width", "height"},
    "g": COMMON,
    "path": COMMON | {"d"},
    "rect": COMMON | {"x", "y", "width", "height", "rx", "ry"},
    "circle": COMMON | {"cx", "cy", "r"},
    "ellipse": COMMON | {"cx", "cy", "rx", "ry"},
    "line": COMMON | {"x1", "y1", "x2", "y2"},
    "polyline": COMMON | {"points"},
    "polygon": COMMON | {"points"},
    "text": COMMON | {"x", "y", "dx", "dy", "text-anchor", "font-family", "font-size", "font-weight"},
    "tspan": COMMON | {"x", "y", "dx", "dy", "text-anchor", "font-family", "font-size", "font-weight"},
    "title": set(),
    "desc": set(),
}
PAINT = re.compile(r"^(?:none|currentColor|#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6})$")
NUMBER = re.compile(r"^-?(?:\d+(?:\.\d+)?|\.\d+)$")
NUMBER_LIST = re.compile(r"^[\s,0-9.+-]+$")
TRANSFORM = re.compile(r"^(?:(?:translate|scale|rotate|matrix|skewX|skewY)\([\s,0-9.+-]+\)\s*)+$")


def _local(name):
    return name.split("}", 1)[1] if name.startswith("{") else name


def _namespace(name):
    return name[1:].split("}", 1)[0] if name.startswith("{") else ""


def _depth(root):
    return max((depth for _, depth in _walk(root)), default=1)


def _walk(root):
    stack = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        yield node, depth
        stack.extend((child, depth + 1) for child in reversed(list(node)))


def _attribute_safe(name, value):
    if "url(" in value.lower() or "javascript:" in value.lower() or "data:" in value.lower():
        return False
    if name in ("fill", "stroke"):
        return bool(PAINT.match(value))
    if name == "transform":
        return bool(TRANSFORM.match(value))
    if name in ("viewBox", "points"):
        return bool(NUMBER_LIST.match(value))
    if name == "font-family":
        return value in ("sans-serif", "monospace")
    if name in ("stroke-linecap",):
        return value in ("butt", "round", "square")
    if name in ("stroke-linejoin",):
        return value in ("miter", "round", "bevel")
    if name == "text-anchor":
        return value in ("start", "middle", "end")
    if name in ("role",):
        return value == "img"
    if name == "aria-label":
        return "<" not in value and ">" not in value
    if name == "d":
        return bool(re.match(r"^[\s,0-9.+\-MmLlHhVvCcSsQqTtAaZz]+$", value))
    return bool(NUMBER.match(value))


def validate(source):
    """Return stable diagnostics for unsafe or malformed inline SVG source."""
    encoded = (source or "").encode("utf-8")
    if len(encoded) > MAX_BYTES:
        return ["SVG_TOO_LARGE"]
    lowered = (source or "").lower()
    if "<!doctype" in lowered or "<!entity" in lowered or "<?" in lowered:
        return ["SVG_DECLARATION"]
    if re.search(r"\bxmlns\s*:", source or "", re.I):
        return ["SVG_NAMESPACE"]
    try:
        root = ET.fromstring(source or "")
    except ET.ParseError:
        return ["SVG_NOT_WELL_FORMED"]
    nodes = list(_walk(root))
    if len(nodes) > MAX_ELEMENTS:
        return ["SVG_TOO_MANY_ELEMENTS"]
    if _depth(root) > MAX_DEPTH:
        return ["SVG_TOO_DEEP"]
    if root.tag != "{%s}svg" % SVG:
        return ["SVG_ROOT"]
    problems = []
    for node, _ in nodes:
        namespace = _namespace(node.tag)
        name = _local(node.tag)
        if namespace != SVG or name not in ELEMENTS:
            problems.append("SVG_ELEMENT_%s" % name.upper())
            continue
        if name not in ("text", "tspan", "title", "desc") and (node.text or "").strip():
            problems.append("SVG_MIXED_CONTENT_%s" % name.upper())
        if (node.tail or "").strip():
            problems.append("SVG_TAIL_CONTENT_%s" % name.upper())
        for attribute, value in node.attrib.items():
            local = _local(attribute)
            if _namespace(attribute) or local.lower().startswith("on") or local not in ATTRIBUTES[name]:
                problems.append("SVG_ATTRIBUTE_%s_%s" % (name.upper(), local.upper()))
            elif not _attribute_safe(local, value):
                problems.append("SVG_VALUE_%s_%s" % (name.upper(), local.upper()))
    return problems


def render(source, label):
    """Reserialize already validated SVG with renderer-owned accessibility."""
    root = ET.fromstring(source)
    root.set("class", "figure-drawing")
    root.set("role", "img")
    root.set("aria-label", label)
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)
