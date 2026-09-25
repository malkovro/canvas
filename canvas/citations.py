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
`node-naming.md:84` cites `engineering-spec.md:108-110` and then says *"this
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

## The citations no quotation reaches

Fifty of this corpus's 140 live citations carry a quotation. The rule above
needs one and says nothing about the other ninety, which is most of the corpus
and was never measured until `docs/unquoted-citations/READING.md` read all of
them on 2026-09-25 and found **24 stale** — nineteen of them into
`engineering-spec.md`, which had grown three sections underneath citations
nobody had touched since.

The second half of this module answers that without abandoning the evidence
rule. A citation was written at some commit; at that commit the cited range
held some text; that text is what its author pointed at. `written_against`
blames the citing line, reads the cited file at that commit, and uses the text
that stood at the range then as the quotation the citation never carried — and
from there the same three outcomes apply, the moved case still carrying its own
repair. It is **reported and never fails the run**: the quoted rule fails on
words an author typed, this one on words inferred from a timestamp. The
commentary above `written_against` prices that difference against the reading.

## Which file, before which lines

Every rule here is about where a passage sits in a file, and every one of them
assumes the right file was opened. `resolve` took the first candidate that
existed, and the candidates were ordered by the roots the caller passed, so a
citation that spelled a path could be answered by a file in the other
repository: `docs/unquoted-citations/READING.md:51` cites
`ledger-orchestrator/README.md` and was read against this one, which has no
dependency policy in it, because `canvas` is passed first and both have a
`README.md`. Wrong twice over, and neither half was on the report.

`candidates` ranks the spellings first, then the basename matched anywhere —
the fallback is load-bearing, since `FRICTION.md` and
`docs/drive-by-hand/FRICTION.md` name one file — and among those it prefers a
path that also ends with the directories the citation wrote. What is left is
genuinely ambiguous: a bare `cli.py` where two exist decides nothing, and
neither can the reader. Those are **named on the report and never failed**, for
the reason the fallback exists at all — most of them are right, and refusing an
ambiguous name would fire on citations that are correct today. What was wrong
was the silence, not the guess.

## A citation inside a block is a record

A fenced or indented block is reproduced text. `node-identity.md:505` sets out
`bin/canvas history` output whose commit reason cites `node-identity.md:446`, a
line number typed on 2026-09-23, and renumbering it to agree with today's file
would falsify the transcript exactly as renumbering a `PINNED_REPORTS` citation
would falsify a measurement — which `PINNED_REPORTS` does not cover, because
the transcript is quoted inside a live document. `transcribed` is that
predicate and **both** rules ask it. Only the unquoted one used to: a quotation
landing beside that transcript line would have been ruled on and reported
*moved*, and the repair a moved report carries is the renumber. Nothing had
landed there yet, which is the only reason it had not happened.

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
import subprocess
import sys


#: Directories whose documents are dated readings pinned to a sha. Their
#: citations record what was there when they were written. See the module
#: docstring, *What is not checked*.
PINNED_REPORTS = (
    os.path.join("docs", "why-verdict"),
    os.path.join("docs", "drive-by-hand"),
    os.path.join("docs", "merge-and-split"),
    os.path.join("docs", "unquoted-citations"),
)

#: Never walked: caches, git internals, and the verbatim session transcripts a
#: report quotes, which are records rather than prose anybody maintains.
SKIP_DIRECTORIES = (".git", "__pycache__", ".pytest_cache", "node_modules",
                    ".runs", ".orchestrator-artifacts")
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


#: A fenced block, a line indented into a code block, and an inline code span.
#: Applied in that order, because a backtick inside a fenced block opens
#: nothing.
CODE = (re.compile(r"^(?P<fence>```|~~~).*?^(?P=fence)", re.M | re.S),
        re.compile(r"^(?: {4}|\t).*$", re.M),
        re.compile(r"`[^`\n]*`"))


def without_code(text):
    """The same document with every code region blanked to spaces.

    Offsets are preserved, so this is a lens for finding delimiters and never
    a source of quoted text.

    A `"` inside code is a character being named, not a quotation mark, and
    reading it as one is not a near miss: straight quotes are paired in order,
    so a single unpaired mark inverts every pair after it in the file. One
    such mark — ``docs/canvas-in-the-page.md`` listing the characters a
    renderer must escape, *"`<`, `>`, `&` or `"`"* — silently turned every
    quotation in the rest of that document into the prose *between* two
    quotations, and no citation in the largest document of this corpus was
    checked at all. Two stale citations were sitting behind it. A run cannot
    report coverage it does not have, so the mark has to stop counting where
    the corpus already says it is not punctuation.
    """
    characters = list(text)
    for pattern in CODE:
        for match in pattern.finditer("".join(characters)):
            for index in range(match.start(), match.end()):
                if characters[index] != "\n":
                    characters[index] = " "
    return "".join(characters)


def _verbatim(text):
    """The same document with fenced and indented blocks blanked to spaces.

    Not `without_code`, which also blanks inline spans — and nearly every
    citation in this corpus is written inside backticks, so blanking those
    would blank the whole question. What has to be excluded is the *block*
    kind: `node-identity.md` reproduces a `canvas history` transcript, and the
    commit reasons inside it cite line numbers as they were typed on the day.
    """
    characters = list(text)
    for pattern in CODE[:2]:
        for match in pattern.finditer("".join(characters)):
            for index in range(match.start(), match.end()):
                if characters[index] != "\n":
                    characters[index] = " "
    return "".join(characters)


def transcribed(text):
    """The offsets of the citations that are records rather than claims.

    A citation inside a fenced or indented block is reproduced text — a
    transcript, a sample report, a diff — and what it says is what was true
    when it was typed. `node-identity.md:505` sets out `bin/canvas history`
    output whose commit reason cites `node-identity.md:446`, a line number
    typed on 2026-09-23; renumbering it to agree with today's file would
    falsify the transcript for the same reason renumbering a `PINNED_REPORTS`
    citation would falsify a measurement, and `PINNED_REPORTS` does not cover
    a transcript quoted inside a live document.

    Both rules need this answer and only one of them used to have it. The
    unquoted rule filtered on the same lens inline; the quoted rule did not,
    so a quotation landing beside that transcript line would have been ruled
    on and reported *moved*, with the repair being the renumber. Nothing in
    the corpus had landed there yet, which is the only reason it had not
    happened. One predicate, both callers, so they cannot drift apart again.
    """
    verbatim = _verbatim(text)
    return {citation.start() for citation, _, _, _ in cited(text)
            if verbatim[citation.start():citation.end()].strip() == ""}


def quotations(text):
    """Every quoted span, as `(start_offset, quoted_text)`.

    Straight quotes carry no direction, so they are paired in order — first
    opens, second closes, third opens. Pairing matters: reading every
    `"…"` match instead would take the prose *between* two quotations on one
    line as a quotation itself, which is a sentence that appears in no file and
    would be reported undecidable forever. Curly pairs are unambiguous, so they
    are taken first and blanked out before the straight-quote pass sees them.

    Delimiters are located in `without_code(text)` and the quotation is then
    cut from `text` itself, so a quotation that contains code — *"`replace`
    takes the new text and not a patch of it"* — is still quoted in full.
    """
    found = []
    remaining = list(without_code(text))
    for start, _ in blockquotes(text):
        end = text.index("\n\n", start) if "\n\n" in text[start:] else len(text)
        for index in range(start, end):
            if remaining[index] != "\n":
                remaining[index] = " "
    for match in re.finditer("“([^”]+)”", "".join(remaining)):
        found.append((match.start(), text[match.start() + 1:match.end() - 1]))
        for index in range(match.start(), match.end()):
            remaining[index] = " "
    stripped = "".join(remaining)
    marks = [match.start() for match in re.finditer('"', stripped)]
    for opening, closing in zip(marks[::2], marks[1::2]):
        found.append((opening, text[opening + 1:closing]))
    return sorted(found)


#: A run of lines each opening with `>`: markdown's own way of quoting a
#: passage, and the corpus uses it for the long ones.
BLOCKQUOTE = re.compile(r"^(?:>[^\n]*\n)+", re.M)


def blockquotes(text):
    """Every blockquote, as `(start_offset, quoted_text)`.

    A citation followed by a blockquote is quoting its target as surely as one
    followed by `*"…"*`, and eleven of this corpus's citations do it — usually
    the long passages, where inline marks would be unreadable. They were
    invisible, and not by a rule anybody chose: the association ends at a
    paragraph break and a blockquote always sits behind one. Three of the
    eleven pointed at the wrong lines, `node-state.md:285` among them, which
    sets the quotation out in full directly beneath the range that does not
    hold it.
    """
    found = []
    for match in BLOCKQUOTE.finditer(without_code(text)):
        body = "\n".join(line.lstrip(">").strip() for line
                          in text[match.start():match.end()].split("\n"))
        found.append((match.start(), body))
    return found


def fragments(quote):
    """The parts of a quotation that must each be present.

    An elided quotation — *"A state field … it should be fixed with evidence"* —
    is two claims about the target with unknown text between them, so each side
    is located separately and both must be inside the cited range.

    Punctuation closing a fragment is dropped. A writer who ends a sentence on
    a quotation puts the full stop inside the quotation marks, and the source
    it quotes carries on — `node-state.md:642` quotes *"…it folds back into
    `<text open="true">`."* where the spec has that clause followed by an em
    dash. Requiring the borrowed full stop made a citation that lands read as
    one whose words are nowhere in the file. This drops a character the citing
    author added; it never reaches for words the target does not have.
    """
    parts = re.split("…|\\.\\.\\.", normalise(quote))
    parts = [part.strip().rstrip(".,;:!?") for part in parts]
    return [part for part in parts if len(part) >= MIN_FRAGMENT]


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


def candidates(target, citing_file, roots):
    """Every file a citation could name, best first, as `(path, spelled)`.

    The spellings come first: relative to the citing document, then under each
    root. `spelled` is True for those — the citation gave a path and a file is
    at it, so there is nothing to guess.

    Then the basename anywhere under a root, which is load-bearing rather than
    a nicety: `node-state.md`, `FRICTION.md` and
    `docs/drive-by-hand/FRICTION.md` all name one file and all three spellings
    are in use. What it must not do is throw away the directories the citation
    *did* write. Matching on the basename alone and taking whichever root was
    passed first read `ledger-orchestrator/README.md`, in
    `docs/unquoted-citations/READING.md:51`, as this repository's README —
    a file with no dependency policy in it — because `canvas` is passed first
    and both repositories have a `README.md`. So basename matches whose path
    also ends with the directories the citation spelled are ranked ahead of
    those that merely share a filename. The sort is stable, so among equals the
    order the roots were given in still decides.

    A citation that spells no directory at all — a bare `cli.py` — is left
    exactly where it was: every match ends with it, nothing is reordered, and
    the ambiguity is real rather than resolvable. `bound_by_name` reports it.
    """
    spelled = [os.path.join(os.path.dirname(citing_file), target)]
    for root in roots:
        spelled.append(os.path.join(root, target))
    base = os.path.basename(target)
    written = target.replace(os.sep, "/").strip("./")
    walked = []
    for root in roots:
        for directory, subdirectories, filenames in os.walk(root):
            # `fixtures` as `documents` already reads it: the corpora the tests
            # build are not documents anybody maintains and are not documents
            # anybody cites either. Left in, a fixture is a rival for every
            # ordinary filename — `tests/fixtures/canvas/README.md` answers to
            # `canvas/README.md` more exactly than the canvas README does.
            subdirectories[:] = [name for name in subdirectories
                                 if name not in SKIP_DIRECTORIES
                                 and name != "fixtures"]
            if base in filenames:
                walked.append(os.path.join(directory, base))
    walked.sort(key=lambda path: not
                path.replace(os.sep, "/").endswith("/" + written))
    found, seen = [], set()
    for path in spelled + walked:
        real = os.path.realpath(path)
        if os.path.isfile(path) and real not in seen:
            seen.add(real)
            found.append((path, path in spelled))
    return found


def resolve(target, citing_file, roots):
    """The file a citation names, or None."""
    found = candidates(target, citing_file, roots)
    return found[0][0] if found else None


def bound_by_name(target, citing_file, roots):
    """The files a citation could equally have named, or `[]`.

    Empty whenever the citation says which file it means and a file is there:
    then nothing was guessed. Empty too when only one file carries the name,
    however it was found. What is left is the case this cannot decide and the
    reader has to — a name matched anywhere under the roots with more than one
    file answering to it — and it is *reported*, never failed, for the reason
    the fallback exists at all: most of these are right, and a check that
    refused them would fire on citations that are correct today.
    """
    found = candidates(target, citing_file, roots)
    if len(found) < 2 or found[0][1]:
        return []
    return [path for path, _ in found]


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


def judge(citation, target, first, last, quote, path, text, roots):
    """One citation weighed against one quotation, as a record with a verdict."""
    wanted = fragments(quote)
    record = {
        "path": path,
        "line": text[:citation.start()].count("\n") + 1,
        # Spelled out rather than quoted back, so a bare `:289-290`
        # continuation is reported against the file it inherited.
        "citation": "%s:%d%s" % (target, first,
                                 "-%d" % last if last != first else ""),
        "quote": normalise(quote),
    }
    resolved = resolve(target, path, roots)
    if resolved is None:
        return dict(record, verdict=UNDECIDABLE, actual=None,
                    why="the cited file was not found")
    with open(resolved, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    if last <= len(lines) and _holds(lines, first, last, wanted):
        return dict(record, verdict=LANDS, actual=(first, last))
    actual = locate(lines, wanted)
    if actual is None:
        return dict(record, verdict=UNDECIDABLE, actual=None,
                    why="the quoted words are not in the cited file")
    # A single-line citation pointing at the first line of a sentence that
    # runs on is a pointer, not a range, and it lands.
    if first == last and actual[0] == first:
        return dict(record, verdict=LANDS, actual=actual)
    return dict(record, verdict=MOVED, actual=actual,
                target=os.path.basename(resolved))


def attributed_to(text, citations, offset, is_block):
    """The citations a quotation at `offset` is a claim about.

    Factored out because two checks need the same answer to the same question:
    the quoted rule below, and `written_against`, which needs to know which
    citations the quoted rule has *already* ruled on so that it speaks only
    about the rest.
    """
    candidates = []
    for citation, target, first, last in citations:
        if citation.end() > offset or not target.endswith(".md"):
            continue
        between = text[citation.end():offset]
        if len(between) > QUOTE_DISTANCE:
            continue
        # A blockquote always sits behind a paragraph break, so for one the
        # break that ends every other association is the separator itself
        # and only a second one means the citation is elsewhere.
        if "\n\n" in (between.rstrip() if is_block else between):
            continue
        candidates.append((citation, target, first, last))
    return candidates


#: Worst last. A quotation is weighed against every citation near it and the
#: best answer any of them gives is the one that stands, because a sentence
#: citing two files quotes one of them and the other is not thereby wrong.
PRECEDENCE = (LANDS, MOVED, UNDECIDABLE)


def check_document(path, roots):
    """Every quoted citation in one document, as dicts carrying its verdict.

    A quotation is attributed to the nearest citation before it, except that
    when several stand in the same sentence every one of them is tried. Taking
    only the nearest is wrong where the corpus writes *"`engineering-spec.md:
    128-130` and `product-spec.md:48` both state it in their own words"* and
    then quotes: the words are the spec's, the nearest citation is the product
    spec, and the verdict was *undecidable* — silence — while the spec citation
    was thirty lines stale and never tested. Trying each and keeping the best
    answer asserts nothing extra: a citation is still only called drifted when
    the quoted words have been found elsewhere in the file it names.

    A citation inside a fenced or indented block is passed over: it is a
    transcript of what somebody typed, not a claim about a file today. See
    `transcribed`.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    citations = cited(text)
    records = transcribed(text)
    results = []
    quoted = ([(offset, quote, False) for offset, quote in quotations(text)] +
              [(offset, quote, True) for offset, quote in blockquotes(text)])
    for offset, quote, is_block in sorted(quoted):
        if not fragments(quote):
            continue
        near = [candidate for candidate in
                attributed_to(text, citations, offset, is_block)
                if candidate[0].start() not in records]
        if not near:
            continue
        judged = [judge(*candidate, quote=quote, path=path, text=text,
                        roots=roots) for candidate in near]
        results.append(min(reversed(judged),
                           key=lambda record: PRECEDENCE.index(record["verdict"])))
    return results


# ---------------------------------------------------------------------------
# Citations with no quotation beside them
#
# The rule above speaks only where a quotation gives it the words to look for,
# which on this corpus is 50 citations of 140. The other 90 were checked by
# nobody, and a reading of all of them on 2026-09-25 found 24 stale — the same
# defect in nine spellings, all of them into `engineering-spec.md`, which had
# grown three sections underneath them.
#
# What follows recovers the missing quotation instead of doing without one. A
# citation was written at some commit; at that commit the cited range held some
# text; that text is what its author was pointing at. So: blame the citing
# line, read the cited file at that commit, and take the text that stood at the
# range then as the quotation the citation never carried. From there the rule
# above applies unchanged — the same three outcomes, and the moved case still
# carries its own repair.
#
# **It is reported and does not fail the run**, and the difference is not
# timidity. The quoted rule fails on words an author typed; this one fails on
# words inferred from a timestamp, and the inference is wrong whenever a
# citation was already wrong when it was written, or the citing line was last
# touched by a reflow that had nothing to do with it. Measured against the
# 2026-09-25 reading: 22 of the 24 stale citations reported, 2 reports on
# citations that land — and both of those two are ranges a stricter reading
# would have tightened anyway. A check that is right 22 times in 24 is worth
# printing and is not worth blocking a merge on, which is the shape
# `docs/why-verdict/VERDICT.md` §5.2 already set for a guard whose price was
# one false positive in fifty.


def _git(arguments, cwd):
    """`git` in `cwd`, or None if it failed or there is no git here."""
    try:
        finished = subprocess.run(["git"] + arguments, cwd=cwd, check=False,
                                  capture_output=True, text=True)
    except OSError:
        return None
    return finished.stdout if finished.returncode == 0 else None


def _repository(path, _cache={}):
    """The work tree `path` belongs to, or None.

    Resolved through `realpath` on both sides: git answers with the real path,
    and on a machine where `/tmp` is a link to `/private/tmp` an unresolved
    answer makes every `relpath` against it climb out of the repository.
    """
    directory = os.path.realpath(os.path.dirname(path))
    if directory not in _cache:
        top = _git(["rev-parse", "--show-toplevel"], directory)
        _cache[directory] = os.path.realpath(top.strip()) if top else None
    return _cache[directory]


def _inside(repository, path):
    """`path` spelled the way git wants it: relative to the work tree root."""
    return os.path.relpath(os.path.realpath(path), repository)


def _blame(path, repository):
    """`{line number: commit}` for one file, in one `git blame`.

    One call per document rather than per citation: a document cites the same
    file a dozen times and blaming it a dozen times is the same answer bought
    a dozen times.
    """
    porcelain = _git(["blame", "--porcelain", "--",
                      _inside(repository, path)], repository)
    if porcelain is None:
        return {}
    blamed, commit = {}, None
    for line in porcelain.split("\n"):
        header = re.match(r"^([0-9a-f]{40}) \d+ (\d+)", line)
        if header:
            commit, number = header.group(1), int(header.group(2))
            blamed[number] = commit
    return blamed


def _at(repository, commit, path, _cache={}):
    """One file as it stood at one commit, or None if it was not there yet."""
    key = (repository, commit, path)
    if key not in _cache:
        _cache[key] = _git(["show", "%s:%s" % (commit, path)], repository)
    return _cache[key]


def _contemporary(repository, commit, other, _cache={}):
    """The commit in `other` that was current when `commit` was made.

    A citation that crosses repositories has no shared history to ask, so the
    two are lined up by time. This is the weakest link in the check and the
    reason a cross-repository report is worth a little more suspicion than a
    local one.
    """
    if repository == other:
        return commit
    key = (repository, commit, other)
    if key not in _cache:
        when = _git(["show", "-s", "--format=%cI", commit], repository)
        found = _git(["rev-list", "-1", "--before=%s" % when.strip(), "HEAD"],
                     other) if when else None
        _cache[key] = found.strip() if found else None
    return _cache[key]


def written_against(path, roots):
    """Every citation in one document that has no quotation, weighed against
    the text its target held when the citation was written."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    repository = _repository(path)
    if repository is None:
        return []
    citations = cited(text)
    # Citations the quoted rule already rules on are left to it, and a citation
    # inside a block is a record rather than a claim — see `transcribed`, which
    # both rules now ask.
    spoken, records = set(), transcribed(text)
    quoted = ([(offset, quote, False) for offset, quote in quotations(text)] +
              [(offset, quote, True) for offset, quote in blockquotes(text)])
    for offset, quote, is_block in quoted:
        if not fragments(quote):
            continue
        for citation, _, _, _ in attributed_to(text, citations, offset, is_block):
            spoken.add(citation.start())
    blamed = _blame(path, repository)
    results = []
    for citation, target, first, last in citations:
        if not target.endswith(".md") or citation.start() in spoken:
            continue
        if citation.start() in records:
            continue
        line = text[:citation.start()].count("\n") + 1
        commit = blamed.get(line)
        resolved = resolve(target, path, roots)
        if commit is None or resolved is None:
            continue
        elsewhere = _repository(resolved)
        contemporary = _contemporary(repository, commit, elsewhere) \
            if elsewhere else None
        if contemporary is None:
            continue
        then = _at(elsewhere, contemporary, _inside(elsewhere, resolved))
        if then is None:
            continue
        held = then.split("\n")
        if last > len(held):
            continue
        wanted = [normalise(" ".join(held[first - 1:last]))]
        if len(wanted[0]) < MIN_FRAGMENT:
            continue
        with open(resolved, encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        record = {
            "path": path,
            "line": line,
            "citation": "%s:%d%s" % (target, first,
                                     "-%d" % last if last != first else ""),
            "quote": wanted[0],
            "commit": commit[:8],
        }
        if last <= len(lines) and _holds(lines, first, last, wanted):
            results.append(dict(record, verdict=LANDS, actual=(first, last)))
            continue
        # The passage occupied about this many lines when it was written, so
        # looking much further than that is looking for a different passage.
        actual = locate(lines, wanted, span=(last - first) + 12)
        if actual is None:
            results.append(dict(record, verdict=UNDECIDABLE, actual=None,
                                why="the text it pointed at is no longer in "
                                    "the cited file"))
        elif first == last and actual[0] == first:
            results.append(dict(record, verdict=LANDS, actual=actual))
        else:
            results.append(dict(record, verdict=MOVED, actual=actual,
                                target=os.path.basename(resolved)))
    return results


def guessed_files(path, roots):
    """Every citation in one document whose file the checker had to guess.

    Reported beside the verdicts rather than folded into them, because this
    says nothing about whether a citation lands: it says the checker — and the
    reader — cannot be sure which file is being talked about, so whatever
    verdict follows is about a file that may not be the one meant. A citation
    inside a block is left alone here as everywhere else; it is a record.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    records = transcribed(text)
    found, seen = [], set()
    for citation, target, _, _ in cited(text):
        if citation.start() in records or target in seen:
            continue
        also = bound_by_name(target, path, roots)
        if not also:
            continue
        seen.add(target)
        found.append({
            "path": path,
            "line": text[:citation.start()].count("\n") + 1,
            "target": target,
            "read_as": also[0],
            "also": also[1:],
        })
    return found


def check(roots):
    live, pinned = documents(roots)
    results, unquoted, guesses = [], [], []
    for _, path in live:
        results.extend(check_document(path, roots))
        unquoted.extend(written_against(path, roots))
        guesses.extend(guessed_files(path, roots))
    skipped = sum(len(check_document(path, roots)) for _, path in pinned)
    return results, unquoted, guesses, skipped, len(live), len(pinned)


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

    results, unquoted, guesses, skipped, live_count, pinned_count = check(roots)
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

    # Named, not merely counted. These are the citations this cannot rule on,
    # and they are exactly the ones a person has to read for themselves; a
    # count nobody can resolve to a location is an exemption nobody can see,
    # which is the thing PINNED_REPORTS is printed to avoid. Three defects
    # lived here — two documents' worth of quotations mispaired by a `"` in
    # code, and a spec citation thirty lines stale — and each was found by
    # calling this module directly, because the report would not say where to
    # look.
    if undecidable:
        sys.stdout.write("\nUndecidable — read these yourself:\n")
        for record in undecidable:
            sys.stdout.write(
                "%s:%d\n    cites %s — %s\n    quote: %s\n" % (
                    record["path"], record["line"], record["citation"],
                    record["why"], record["quote"][:120]))

    # The unquoted citations, weighed against what their target held when they
    # were written. Reported and never failed: see the commentary above
    # `written_against` for why the evidence here does not carry a merge block.
    drifted = [record for record in unquoted if record["verdict"] == MOVED]
    if drifted:
        sys.stdout.write(
            "\nWritten against a different file — the cited range has changed "
            "since\nthe citing line was last touched. Read these; the check "
            "cannot:\n")
        for record in drifted:
            sys.stdout.write(
                "%s:%d\n    cites %s, written at %s\n"
                "    what that range held then is now at %s:%d-%d\n"
                "    then: %s\n" % (
                    record["path"], record["line"], record["citation"],
                    record["commit"], record["target"], record["actual"][0],
                    record["actual"][1], record["quote"][:120]))

    # The citations whose *file* was a guess. One line of the report can only
    # ever be about one file, and every other line here assumes the right one
    # was opened. Named rather than counted, and never failed: the fallback
    # that produces these also carries the deliberate cross-repository
    # citations — `FRICTION.md` and `docs/drive-by-hand/FRICTION.md` are one
    # file under two spellings — so refusing an ambiguous name would fire on
    # citations that are correct today. What is wrong is that it was silent.
    if guesses:
        sys.stdout.write(
            "\nBound by filename alone — the citation spelled no path that "
            "exists, and more than\none file answers to the name. Read these; "
            "the checker read the first:\n")
        for record in guesses:
            sys.stdout.write("%s:%d\n    cites %s — read as %s\n" % (
                record["path"], record["line"], record["target"],
                record["read_as"]))
            for other in record["also"]:
                sys.stdout.write("    could equally be %s\n" % other)

    sys.stdout.write(
        "\n%d quoted citations in %d live documents: %d land, %d moved, "
        "%d undecidable.\n%d citations carry no quotation: %d still hold what "
        "they were written against, %d listed above as changed underneath,\n"
        "%d that could not be placed. %d citations in %d pinned dated readings "
        "were not checked (see PINNED_REPORTS).\n%d names above were bound by "
        "filename alone and are reported, not failed.\n" % (
            len(results), live_count, len(lands), len(moved),
            len(undecidable), len(unquoted),
            len([r for r in unquoted if r["verdict"] == LANDS]), len(drifted),
            len([r for r in unquoted if r["verdict"] == UNDECIDABLE]),
            skipped, pinned_count, len(guesses)))
    return 1 if moved else 0


if __name__ == "__main__":
    sys.exit(main())
