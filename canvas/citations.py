"""Does a line-number citation still land on the passage it quotes?

These documents cite each other by line number — `engineering-spec.md:125-128`
— and a line number is a fact about a file at one moment. Inserting a paragraph
into a spec moves every passage below it and silently falsifies every citation
of them, in this repository and in `ledger-orchestrator`, which cites into this
one. Nothing here notices, because the citation still *resolves*: the lines
exist, they are simply the wrong lines.

That distinction is the whole point. A row closed recording *"All 126
line-number citations across both repositories re-read on merged main and
resolving"*, and the claim was true as stated and did not mean what it sounded
like: what had been compared was line numbers against file lengths, not cited
text against the text at the cited lines. `guidelines/domain-decisions.md:44`
cites `engineering-spec.md:272-276` for the sentence refusing a state field;
that sentence is at `291-295`, and `272-276` is an unrelated paragraph about
writing contradictions into the canvas. A reader who follows the citation lands
somewhere plausible and wrong, which is worse than landing nowhere.

## The rule, and why it fires on evidence rather than on shape

For each citation with a quotation next to it, three outcomes:

- The quoted text is inside the cited lines — **it lands**. Nothing to say.
- The quoted text is not there, but is **somewhere else in the same file** — the
  citation has drifted. This is the only failure, and it carries its own repair:
  the range that does hold the quote.
- The quoted text is **not in the cited file at all** — *undecidable*, counted
  and not failed.

The third case is the one that keeps this honest. Most quoted text near a
citation is the citing author's own sentence, not a quotation of the target —
`node-naming.md:68` cites `engineering-spec.md:108-110` and then says *"this
paragraph is the problem statement"*, which is a remark about the citation and
appears in no spec. A check that treated every nearby quotation as a claim about
the target would fail on prose that is not wrong, which is the failure mode
`docs/why-verdict/DRIFT-CHECK.md` §7.2 refused a different check for: *"a check
inside the canvas can only see the shape."* This one never rules on shape. It
speaks only when it has found the quoted words in the cited file and can say
where they are, and it is silent — visibly, with a count — whenever it cannot.

So a passing run is not a claim that every citation is correct. It is the
narrower claim that no citation quotes a passage this file can locate elsewhere.
The count of undecidable citations is printed so that the narrowness is on the
report rather than in this docstring only.

## What is not checked, and why renumbering it would be the bug

`docs/why-verdict/`, `docs/drive-by-hand/` and `docs/merge-and-split/` each hold
the output of one dated reading, written against a named sha — DRIFT-CHECK.md
says *"Measured and written 2026-09-24, against `main` at `599d5ba…`"*. Their
citations were true at that sha and are part of the record of what was read.
Correcting one to today's line numbers would silently edit a measurement to
agree with a file it never saw. They are listed in `PINNED_REPORTS` with this
reason, and the number of citations skipped for it is printed, because an
exemption nobody can see is indistinguishable from a gap.
"""

import argparse
import os
import re
import sys


#: Directories whose documents are dated readings pinned to a sha. Their
#: citations record what was there when they were written. See the module
#: docstring, *What is not checked*.
PINNED_REPORTS = (
    os.path.join("docs", "why-verdict"),
    os.path.join("docs", "drive-by-hand"),
    os.path.join("docs", "merge-and-split"),
)

#: Never walked: caches, git internals, and the verbatim session transcripts a
#: report quotes, which are records rather than prose anybody maintains.
SKIP_DIRECTORIES = (".git", "__pycache__", "node_modules", ".runs",
                    ".orchestrator-artifacts")
SKIP_FILENAMES = ("canvas-transcript.md",)

#: `path.md:12` or `path.md:12-40`, optionally inside backticks; and the bare
#: continuation form this corpus uses to cite the same file twice in one
#: sentence — *"`README.md:275-278` shows that shape and `:289-290` promises it
#: is stable"* — which inherits the file from the citation before it. Backticks
#: are required on the bare form so that a clock time or a ratio is not read as
#: a citation.
CITATION = re.compile(
    r"`?(?P<file>[A-Za-z0-9_./-]+\.(?:md|py|rng)):(?P<first>\d+)(?:-(?P<last>\d+))?`?"
    r"|`:(?P<bare_first>\d+)(?:-(?P<bare_last>\d+))?`")


#: How far after a citation a quotation may start and still be read as
#: belonging to it. A paragraph break always ends the association. The same
#: distance bounds how far a bare `:12-14` inherits the file before it.
QUOTE_DISTANCE = 160

#: Shorter than this, a fragment matches too much to mean anything.
MIN_FRAGMENT = 20

LANDS, MOVED, UNDECIDABLE = "lands", "moved", "undecidable"


def cited(text):
    """Every citation in order, as `(match, target, first, last)`.

    A bare `:12-14` carries no file of its own and means the file named
    immediately before it, **in the same sentence** — the join is `and`, not a
    paragraph. Inheriting further than that is wrong rather than merely
    imprecise: `node-identity.md` uses bare refs for *transcript* line numbers
    for pages at a time, and a rule that reached back to whatever full citation
    came last would attribute those to whichever file was mentioned in between.
    A bare ref with nothing that close in front of it names nothing and is
    dropped rather than guessed at.
    """
    found, carried, carried_end = [], None, None
    for match in CITATION.finditer(text):
        if match.group("file"):
            carried, carried_end = match.group("file"), match.end()
            first = int(match.group("first"))
            last = int(match.group("last") or first)
        else:
            if carried is None:
                continue
            between = text[carried_end:match.start()]
            if len(between) > QUOTE_DISTANCE or "\n\n" in between:
                continue
            first = int(match.group("bare_first"))
            last = int(match.group("bare_last") or first)
            carried_end = match.end()
        found.append((match, carried, first, last))
    return found


def normalise(text):
    """Markdown emphasis and line wrapping removed, so a quote that is bold in
    one file and wrapped at a different column in the other still compares
    equal. Case folded: a quotation may open a sentence mid-line."""
    return re.sub(r"\s+", " ", re.sub(r"[`*_\[\]]", "", text)).strip().lower()


def quotations(text):
    """Every quoted span, as `(start_offset, quoted_text)`.

    Straight quotes carry no direction, so they are paired in order — first
    opens, second closes, third opens. Pairing matters: reading every
    `"…"` match instead would take the prose *between* two quotations on one
    line as a quotation itself, which is a sentence that appears in no file and
    would be reported undecidable forever. Curly pairs are unambiguous, so they
    are taken first and blanked out before the straight-quote pass sees them.
    """
    found = []
    remaining = list(text)
    for match in re.finditer("“([^”]+)”", text):
        found.append((match.start(), match.group(1)))
        for index in range(match.start(), match.end()):
            remaining[index] = " "
    stripped = "".join(remaining)
    marks = [match.start() for match in re.finditer('"', stripped)]
    for opening, closing in zip(marks[::2], marks[1::2]):
        found.append((opening, stripped[opening + 1:closing]))
    return sorted(found)


def fragments(quote):
    """The parts of a quotation that must each be present.

    An elided quotation — *"A state field … it should be fixed with evidence"* —
    is two claims about the target with unknown text between them, so each side
    is located separately and both must be inside the cited range.
    """
    parts = re.split("…|\\.\\.\\.", normalise(quote))
    return [part.strip() for part in parts if len(part.strip()) >= MIN_FRAGMENT]


def _holds(lines, first, last, wanted):
    return all(part in normalise(" ".join(lines[first - 1:last])) for part in wanted)


def locate(lines, wanted, span=25):
    """The shortest line range holding every fragment, or None.

    `span` bounds how far a quotation may be spread before this stops looking.
    A quotation longer than twenty-five lines of the target is not the kind of
    citation this checks.
    """
    best = None
    for first in range(len(lines)):
        for last in range(first, min(first + span, len(lines))):
            if _holds(lines, first + 1, last + 1, wanted):
                if best is None or (last - first) < (best[1] - best[0]):
                    best = (first, last)
                break
    return (best[0] + 1, best[1] + 1) if best else None


def resolve(target, citing_file, roots):
    """The file a citation names, or None.

    Tried relative to the citing document, then to each root, then by basename
    anywhere under a root — `node-state.md`, `FRICTION.md` and
    `docs/drive-by-hand/FRICTION.md` all name one file and all three spellings
    are in use.
    """
    candidates = [os.path.join(os.path.dirname(citing_file), target)]
    for root in roots:
        candidates.append(os.path.join(root, target))
    base = os.path.basename(target)
    for root in roots:
        for directory, subdirectories, filenames in os.walk(root):
            subdirectories[:] = [name for name in subdirectories
                                 if name not in SKIP_DIRECTORIES]
            if base in filenames:
                candidates.append(os.path.join(directory, base))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def documents(roots):
    """Every markdown file under the roots that somebody maintains, with the
    pinned readings separated out rather than dropped."""
    live, pinned = [], []
    for root in roots:
        for directory, subdirectories, filenames in os.walk(root):
            subdirectories[:] = [name for name in subdirectories
                                 if name not in SKIP_DIRECTORIES]
            for filename in sorted(filenames):
                if not filename.endswith(".md") or filename in SKIP_FILENAMES:
                    continue
                path = os.path.join(directory, filename)
                relative = os.path.relpath(path, root)
                if "fixtures" in relative.split(os.sep):
                    continue
                target = pinned if any(relative.startswith(prefix)
                                       for prefix in PINNED_REPORTS) else live
                target.append((root, path))
    return live, pinned


def check_document(path, roots):
    """Every quoted citation in one document, as dicts carrying its verdict."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    citations = cited(text)
    results = []
    for offset, quote in quotations(text):
        preceding = [found for found in citations if found[0].end() <= offset]
        if not preceding:
            continue
        citation, target, first, last = preceding[-1]
        between = text[citation.end():offset]
        if len(between) > QUOTE_DISTANCE or "\n\n" in between:
            continue
        if not target.endswith(".md"):
            continue
        wanted = fragments(quote)
        if not wanted:
            continue
        resolved = resolve(target, path, roots)
        record = {
            "path": path,
            "line": text[:citation.start()].count("\n") + 1,
            # Spelled out rather than quoted back, so a bare `:289-290`
            # continuation is reported against the file it inherited.
            "citation": "%s:%d%s" % (target, first,
                                     "-%d" % last if last != first else ""),
            "quote": normalise(quote),
        }
        if resolved is None:
            results.append(dict(record, verdict=UNDECIDABLE, actual=None,
                                why="the cited file was not found"))
            continue
        with open(resolved, encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        if last <= len(lines) and _holds(lines, first, last, wanted):
            results.append(dict(record, verdict=LANDS, actual=(first, last)))
            continue
        actual = locate(lines, wanted)
        if actual is None:
            results.append(dict(record, verdict=UNDECIDABLE, actual=None,
                                why="the quoted words are not in the cited file"))
            continue
        # A single-line citation pointing at the first line of a sentence that
        # runs on is a pointer, not a range, and it lands.
        if first == last and actual[0] == first:
            results.append(dict(record, verdict=LANDS, actual=actual))
            continue
        results.append(dict(record, verdict=MOVED, actual=actual,
                            target=os.path.basename(resolved)))
    return results


def check(roots):
    live, pinned = documents(roots)
    results = []
    for _, path in live:
        results.extend(check_document(path, roots))
    skipped = sum(len(check_document(path, roots)) for _, path in pinned)
    return results, skipped, len(live), len(pinned)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="canvas-citations",
        description="Report line-number citations whose quoted passage has "
                    "moved to other lines of the file they cite.")
    parser.add_argument(
        "roots", nargs="*", default=None,
        help="repository checkouts to read. Defaults to this one. Pass a "
             "sibling checkout too to cover citations that cross repositories.")
    arguments = parser.parse_args(argv)
    roots = [os.path.abspath(root) for root in (arguments.roots or [
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))])]
    for root in roots:
        if not os.path.isdir(root):
            sys.stderr.write(
                "canvas-citations: not a directory\n"
                "Canvas-About: root %s\n"
                "Canvas-Next: run canvas-citations with a path that exists\n"
                "Canvas-Exit: 2 — the check could not run\n" % root)
            return 2

    results, skipped, live_count, pinned_count = check(roots)
    moved = [record for record in results if record["verdict"] == MOVED]
    undecidable = [record for record in results if record["verdict"] == UNDECIDABLE]
    lands = [record for record in results if record["verdict"] == LANDS]

    for record in moved:
        sys.stdout.write(
            "%s:%d\n    cites %s\n    but the quoted passage is at %s:%d-%d\n"
            "    quote: %s\n" % (
                record["path"], record["line"], record["citation"],
                record["target"], record["actual"][0], record["actual"][1],
                record["quote"][:120]))

    sys.stdout.write(
        "\n%d quoted citations in %d live documents: %d land, %d moved, "
        "%d undecidable.\n%d citations in %d pinned dated readings were not "
        "checked (see PINNED_REPORTS).\n" % (
            len(results), live_count, len(lands), len(moved),
            len(undecidable), skipped, pinned_count))
    return 1 if moved else 0


if __name__ == "__main__":
    sys.exit(main())
