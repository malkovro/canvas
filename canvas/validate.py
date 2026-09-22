"""The single validation path for canvas files.

Every read and every write of a canvas goes through `validate_file`. The four
verbs validate the document they are about to write *before* committing it, so
an invalid canvas is never reachable on disk.

The vocabulary is not restated here. Every rule about what is legal lives in
`schema/canvas.rng` and nowhere else; this module knows about `id` and `v` only
as labels to print in a diagnostic, because that is how a canvas node is
addressed. The verdict is always xmllint's, never this module's.
"""

import os
import re
import subprocess
import sys
from xml.parsers import expat

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "schema",
    "canvas.rng",
)

# xmllint --noout --relaxng, measured:
#   0 valid | 1 not well-formed | 3 invalid against the schema
#   5 schema missing or fails to compile
_XMLLINT_DOCUMENT_PROBLEM = (1, 3)

# file:line: element TAG: ... error : MESSAGE
_DIAGNOSTIC = re.compile(
    r"^(?P<file>.*?):(?P<line>\d+):\s*element\s+(?P<tag>\S+):\s*.*?error\s*:\s*(?P<msg>.*)$"
)


class EnvironmentProblem(Exception):
    """The tool or its invocation is wrong, as opposed to the document."""


def _scan(path):
    """Map line number -> the start tags on that line, as (tag, attrs, path).

    Built with expat, which is in the standard library of every python3, so the
    validator has no third-party dependency. A file that is not well-formed
    yields whatever was parsed before the parse stopped, which is exactly the
    part a diagnostic can still refer to.

    The element path is what names a node that has no `id` to be named by.
    """
    lines = {}
    stack = []
    parser = expat.ParserCreate()

    def start(tag, attrs):
        counts = stack[-1][1] if stack else {}
        counts[tag] = counts.get(tag, 0) + 1
        parent = stack[-1][2] if stack else ""
        where = "%s/%s[%d]" % (parent, tag, counts[tag])
        stack.append((tag, {}, where))
        lines.setdefault(parser.CurrentLineNumber, []).append((tag, attrs, where))

    def end(tag):
        if stack:
            stack.pop()

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    try:
        with open(path, "rb") as handle:
            parser.ParseFile(handle)
    except expat.ExpatError:
        pass
    return lines


def _describe(tag, attrs, where):
    """Name a node the way a canvas node is addressed.

    By element name always. By `id` where it has one — that is how every verb
    addresses a node — and by its path where it does not, so that a node whose
    missing `id` is the very problem is still identifiable.

    The root is the one node that carries neither `id` nor `v` by design, so it
    is named by what does identify it: being the root, of a stated ledger.
    """
    if where == "/canvas[1]":
        ledger = attrs.get("ledger")
        return "<canvas> (the root%s)" % ('' if ledger is None else ', ledger="%s"' % ledger)
    parts = []
    for name in ("id", "v"):
        value = attrs.get(name)
        parts.append('%s="%s"' % (name, value) if value is not None else "no %s attribute" % name)
    if attrs.get("id") is None:
        parts.append("at %s" % where)
    return "<%s> (%s)" % (tag, ", ".join(parts))


def _wellformedness_problem(path):
    """Return a diagnostic if the file is not well-formed XML, else None."""
    parser = expat.ParserCreate()
    try:
        with open(path, "rb") as handle:
            parser.ParseFile(handle)
    except expat.ExpatError as error:
        return "%s:%d: not well-formed XML: %s" % (
            path,
            error.lineno,
            expat.ErrorString(error.code),
        )
    return None


def validate_file(path):
    """Validate one canvas file against schema/canvas.rng.

    Returns a list of diagnostics, one per problem. An empty list means the file
    is a valid canvas. Each diagnostic names the offending node: the element
    name always, and its `id` and `v` where it carries them.

    Raises EnvironmentProblem when the validator itself cannot run — xmllint
    missing, the schema missing or uncompilable, the file unreadable. That is a
    different thing from an invalid document and the caller must not confuse
    them: one means "fix the node I named", the other means "do not touch the
    canvas".
    """
    if not os.path.isfile(path):
        raise EnvironmentProblem("no such file: %s" % path)
    if not os.path.isfile(SCHEMA_PATH):
        raise EnvironmentProblem("schema not found: %s" % SCHEMA_PATH)

    not_well_formed = _wellformedness_problem(path)
    if not_well_formed is not None:
        return [not_well_formed]

    try:
        result = subprocess.run(
            ["xmllint", "--noout", "--relaxng", SCHEMA_PATH, path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        raise EnvironmentProblem("cannot run xmllint: %s" % error)

    if result.returncode == 0:
        return []
    if result.returncode not in _XMLLINT_DOCUMENT_PROBLEM:
        raise EnvironmentProblem(
            "xmllint exited %d validating %s against %s:\n%s"
            % (result.returncode, path, SCHEMA_PATH, result.stderr.decode("utf-8", "replace").strip())
        )

    lines = _scan(path)
    problems = []
    for line in result.stderr.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        match = _DIAGNOSTIC.match(line)
        if match is None:
            # Never swallowed. A change in libxml2's wording degrades the
            # message and can never turn a failure into a pass.
            problems.append(line.rstrip())
            continue
        number = int(match.group("line"))
        candidates = lines.get(number, [])
        named = match.group("tag")
        # Several elements can start on one line; prefer the one xmllint named.
        found = [c for c in candidates if c[0] == named] or candidates
        tag, attrs, where = found[0] if found else (named, {}, "")
        problems.append(
            "%s:%d: %s: %s" % (match.group("file"), number, _describe(tag, attrs, where), match.group("msg"))
        )
    if not problems:
        problems.append("%s: invalid against %s (xmllint exited %d)" % (path, SCHEMA_PATH, result.returncode))
    return problems


def main(argv):
    """Exit 0 if every file given is a valid canvas, 1 if one is not, 2 if the
    validator itself cannot run."""
    if not argv:
        sys.stderr.write("usage: canvas-validate FILE [FILE ...]\n")
        return 2
    invalid = False
    for path in argv:
        try:
            problems = validate_file(path)
        except EnvironmentProblem as error:
            sys.stderr.write("canvas-validate: %s\n" % error)
            return 2
        for problem in problems:
            sys.stderr.write("%s\n" % problem)
        if problems:
            invalid = True
    return 1 if invalid else 0
