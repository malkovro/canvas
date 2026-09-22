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

from canvas import refusal

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


class EnvironmentProblem(refusal.Refused):
    """The tool or its invocation is wrong, as opposed to the document.

    A `refusal.Refused`, so it carries the thing it is about and the next
    action like every other refusal in the tool. None of these has a node to
    name — a validator that cannot run never read a document — so each names
    what it does have instead: the file, the schema, the binary.
    """


#: What this command's exit codes mean, as `README.md` section *Validating a
#: file by hand* states them and as `bin/canvas-validate` restates them. Printed
#: on the refusal itself, because a caller reading stderr cannot see a table in
#: a Markdown file.
EXIT_MEANING = {
    1: (
        "the document is wrong, not the validator; repair the node each "
        "diagnostic names"
    ),
    2: (
        "the tool or its invocation is wrong; the document was not examined, "
        "so do not touch the canvas"
    ),
}


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
        raise EnvironmentProblem(
            "no such file: %s" % path,
            "name a file that is there and re-run `bin/canvas-validate "
            "<file>`; a canvas the store holds is at "
            "$OPENCLAW_WORKSPACE/state/canvas/<ledger-id>.xml",
            about=["file %s" % path],
        )
    if not os.path.isfile(SCHEMA_PATH):
        raise EnvironmentProblem(
            "schema not found: %s" % SCHEMA_PATH,
            "restore schema/canvas.rng in this checkout; what a canvas node "
            "may be is written there and nowhere else, so there is nothing to "
            "validate against until it is back",
            about=["schema %s" % SCHEMA_PATH],
        )

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
        raise EnvironmentProblem(
            "cannot run xmllint: %s" % error,
            "put xmllint on PATH — it ships with libxml2, as `brew install "
            "libxml2` or `apt install libxml2-utils` — and re-run; until it is "
            "there no canvas can be validated, read or written",
            about=["command xmllint"],
        )

    if result.returncode == 0:
        return []
    if result.returncode not in _XMLLINT_DOCUMENT_PROBLEM:
        raise EnvironmentProblem(
            "xmllint exited %d validating %s against %s:\n%s"
            % (result.returncode, path, SCHEMA_PATH, result.stderr.decode("utf-8", "replace").strip()),
            "repair %s until xmllint can compile it — the lines above are "
            "xmllint's own report of why it cannot — and re-run; %s was never "
            "examined" % (SCHEMA_PATH, path),
            about=[
                "file %s" % path,
                "schema %s" % SCHEMA_PATH,
                "xmllint exit %d" % result.returncode,
            ],
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


def _refuse(refused, code):
    """Print one refusal in the shape every refusal in the tool prints."""
    for line in refusal.lines("canvas-validate", refused, code, EXIT_MEANING[code]):
        sys.stderr.write("%s\n" % line)


def main(argv):
    """Exit 0 if every file given is a valid canvas, 1 if one is not, 2 if the
    validator itself cannot run.

    Both non-zero exits print the same shape: the message, the diagnostics, the
    files the refusal is about, the next action, and the code with what it
    means. A caller reading stderr cannot see `README.md`'s table, so the
    meaning of the code travels with the refusal.

    The diagnostics are `validate_file`'s and are printed unchanged. They are
    already the best node-naming in the tool — element, `id` and `v`, or the
    element path where there is no `id` — and what they were missing is the
    line that says what to do about it.
    """
    if not argv:
        _refuse(
            refusal.Refused(
                "no file to validate: this command validates the files it is "
                "given, and it was given none",
                "name at least one file: `bin/canvas-validate <file> [<file> "
                "...]`; a canvas the store holds is at "
                "$OPENCLAW_WORKSPACE/state/canvas/<ledger-id>.xml",
                about=["argument FILE"],
                details=["usage: canvas-validate FILE [FILE ...]"],
            ),
            2,
        )
        return 2

    invalid = []
    diagnostics = []
    for path in argv:
        try:
            problems = validate_file(path)
        except EnvironmentProblem as error:
            _refuse(error, 2)
            return 2
        diagnostics.extend(problems)
        if problems:
            invalid.append(path)

    if not invalid:
        return 0
    _refuse(
        refusal.Refused(
            "not a valid canvas: %s" % ", ".join(invalid),
            "repair the file at the line each diagnostic above names, then "
            "re-run `bin/canvas-validate %s`; what a canvas node may be is "
            "written in %s and nowhere else, and `xmllint --noout --relaxng "
            "<that schema> <file>` asks it directly"
            % (" ".join(invalid), SCHEMA_PATH),
            about=["file %s" % path for path in invalid],
            details=diagnostics,
        ),
        1,
    )
    return 1
