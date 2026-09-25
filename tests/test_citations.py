"""Tests for `bin/canvas-citations`: does a citation land on what it quotes?

Two groups, and they answer different questions.

The **rule** tests drive `canvas.citations` against markdown written here, one
fixture per branch of the three-way verdict, because the point of the rule is
where it stays silent as much as where it fires. The one that matters most is
`AQuotationTheCitedFileDoesNotContainIsNotAFailure`: nearly every quoted phrase
beside a citation is the citing author's own sentence, and a check that called
those drifted would be noise a reader learns to scroll past.

The **corpus** test is the guard itself. It runs the checker over this
repository and fails if any live document quotes a passage that has moved. That
is the whole reason this exists: line numbers rot silently when a paragraph is
inserted above them, a manual re-read reported *"126 citations … resolving"*
while `guidelines/domain-decisions.md:44` pointed at an unrelated paragraph, and
re-reading by hand is not a thing that can be relied on to happen again.
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIM = os.path.join(ROOT, "bin", "canvas-citations")

sys.path.insert(0, ROOT)

from canvas import citations  # noqa: E402


def corpus(**files):
    """A throwaway repository of markdown, returned as its root directory."""
    root = tempfile.mkdtemp(prefix="canvas-citations-")
    for name, text in files.items():
        path = os.path.join(root, name.replace("__", os.sep))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    return root


SPEC = "\n".join([
    "# Spec",                                   # 1
    "",                                         # 2
    "Something else entirely lives up here.",   # 3
    "",                                         # 4
    "The vocabulary is structural and not",     # 5
    "semantic: shape does not run out.",        # 6
])


def run(root):
    """`main` over one corpus, with its report captured rather than printed
    into the test output."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        return citations.main([root])


def verdicts(root, name):
    found = citations.check_document(os.path.join(root, name), [root])
    return [(record["verdict"], record.get("actual")) for record in found]


class ACitationThatLandsOnItsQuoteIsSilent(unittest.TestCase):
    def test_quote_inside_the_cited_range(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'The defence at `spec.md:5-6` is that *"shape does not run out"*.'})
        self.assertEqual(verdicts(root, "ruling.md"), [(citations.LANDS, (5, 6))])

    def test_single_line_pointer_at_the_start_of_a_sentence_that_runs_on(self):
        # `:5` names where the sentence begins; it wraps onto 6. A pointer is
        # not a range and this is how half the corpus cites.
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'See `spec.md:5`: *"The vocabulary is structural and not semantic"*.'})
        self.assertEqual([v for v, _ in verdicts(root, "ruling.md")], [citations.LANDS])


class ACitationWhoseQuoteMovedIsReportedWithWhereItWent(unittest.TestCase):
    def test_moved_names_the_range_that_now_holds_it(self):
        # The shortest range holding the quote, so the repair is as narrow as
        # the evidence for it: these six words are all on line 6.
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'The defence at `spec.md:1-2` is that *"shape does not run out"*.'})
        self.assertEqual(verdicts(root, "ruling.md"), [(citations.MOVED, (6, 6))])

    def test_an_elided_quotation_must_have_both_halves_inside_the_range(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'At `spec.md:3` — *"The vocabulary is structural … shape does not run out"*.'})
        self.assertEqual(verdicts(root, "ruling.md"), [(citations.MOVED, (5, 6))])


class AQuotationTheCitedFileDoesNotContainIsNotAFailure(unittest.TestCase):
    """The citing author's own words beside a citation are the common case."""

    def test_undecidable_rather_than_moved(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'See `spec.md:5-6`, and *"this paragraph is the problem statement"*.'})
        self.assertEqual(verdicts(root, "ruling.md"), [(citations.UNDECIDABLE, None)])

    def test_undecidable_does_not_fail_the_run(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'See `spec.md:5-6`, and *"a sentence found in no spec at all"*.'})
        self.assertEqual(run(root), 0)


class TheTextBetweenTwoQuotationsIsNotItselfAQuotation(unittest.TestCase):
    """Straight quotes carry no direction, so they are paired in order. Reading
    every `"…"` match instead takes the prose joining two quotations as a third,
    which appears in no file and would be reported undecidable forever."""

    def test_two_quotations_on_one_line_yield_two_spans(self):
        spans = citations.quotations('says "the first thing" and then "the second thing"')
        self.assertEqual([text for _, text in spans],
                         ["the first thing", "the second thing"])

    def test_curly_pairs_are_taken_before_the_straight_pass(self):
        spans = citations.quotations("“the curly one” and \"the straight one\"")
        self.assertEqual(sorted(text for _, text in spans),
                         ["the curly one", "the straight one"])


class ABareContinuationInheritsTheFileBeforeIt(unittest.TestCase):
    """`README.md:275-278` shows that shape and `:289-290` promises it is
    stable — one sentence, two citations, one file named once."""

    def test_the_second_citation_is_read_against_the_first_ones_file(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'See `spec.md:3` and `:5-6`, which says *"shape does not run out"*.'})
        self.assertEqual(verdicts(root, "ruling.md"), [(citations.LANDS, (5, 6))])

    def test_a_drifted_continuation_is_reported_against_the_inherited_file(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'See `spec.md:3` and `:1-2`, which says *"shape does not run out"*.'})
        found = citations.check_document(os.path.join(root, "ruling.md"), [root])
        self.assertEqual(found[0]["verdict"], citations.MOVED)
        self.assertEqual(found[0]["citation"], "spec.md:1-2")

    def test_it_does_not_reach_back_across_a_paragraph(self):
        # node-identity.md writes bare refs to transcript lines for pages at a
        # time; inheriting the last file mentioned would misattribute them all.
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'See `spec.md:3`.\n\nElsewhere `:1-2` said *"shape does not run out"*.'})
        self.assertEqual(verdicts(root, "ruling.md"), [])

    def test_a_bare_reference_with_nothing_in_front_of_it_names_nothing(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'At `:1-2` — *"shape does not run out"*.'})
        self.assertEqual(verdicts(root, "ruling.md"), [])

    def test_an_unbackticked_colon_number_is_not_a_citation(self):
        # "the 02:15 firing" and "a 3:1 ratio" are not citations of anything.
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'At `spec.md:3`, the 02:15 firing said *"shape does not run out"*.'})
        found = citations.check_document(os.path.join(root, "ruling.md"), [root])
        self.assertEqual([record["citation"] for record in found], ["spec.md:3"])


class AQuotationTooFarFromItsCitationIsNotAboutIt(unittest.TestCase):
    def test_a_paragraph_break_ends_the_association(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'See `spec.md:1-2`.\n\nSeparately, *"shape does not run out"*.'})
        self.assertEqual(verdicts(root, "ruling.md"), [])


class ADatedReadingIsNotRenumberedToAgreeWithAFileItNeverSaw(unittest.TestCase):
    def test_pinned_reports_are_excluded_from_the_verdict(self):
        drifted = 'Measured then. `spec.md:1-2` said *"shape does not run out"*.'
        root = corpus(**{"spec.md": SPEC, "docs__why-verdict__READING.md": drifted})
        self.assertEqual(run(root), 0)

    def test_and_are_counted_on_the_report_rather_than_dropped(self):
        drifted = 'Measured then. `spec.md:1-2` said *"shape does not run out"*.'
        root = corpus(**{"spec.md": SPEC, "docs__why-verdict__READING.md": drifted})
        _, skipped, _, pinned = citations.check([root])
        self.assertEqual((skipped, pinned), (1, 1))


class TheCheckerReportsThroughItsExitCode(unittest.TestCase):
    def test_one_drifted_citation_exits_one(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'At `spec.md:1-2` — *"shape does not run out"*.'})
        self.assertEqual(run(root), 1)

    def test_a_root_that_is_not_a_directory_exits_two(self):
        self.assertEqual(run(os.path.join(ROOT, "no-such-directory")), 2)


class EveryCitationInThisRepositoryLandsOnWhatItQuotes(unittest.TestCase):
    """The guard. If this fails, a document quotes a passage that has moved and
    the failure names the range that now holds it."""

    def test_the_shim_exits_zero_on_the_corpus(self):
        finished = subprocess.run([sys.executable, SHIM, ROOT],
                                  capture_output=True, text=True)
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)

    def test_the_corpus_is_actually_being_read(self):
        # A guard over an empty corpus passes for the wrong reason.
        results, _, live, _ = citations.check([ROOT])
        self.assertGreater(live, 5)
        self.assertGreater(len([r for r in results if r["verdict"] == citations.LANDS]), 10)



class AQuotationMarkInsideCodeIsNotADelimiter(unittest.TestCase):
    """Straight quotes are paired in order, so one unpaired mark inverts every
    pair after it. A document naming `"` as a character the renderer escapes
    did exactly that, and every citation below it in the file went unchecked."""

    ESCAPES = "\n".join([
        "A renderer escapes `<`, `>`, `&` or `\"` before it emits anything.",
        "",
        "Then `spec.md:5-6` \u2014 *\"the vocabulary is structural and not semantic\"*.",
    ])

    def test_a_quote_named_in_code_does_not_swallow_the_quotation_after_it(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md": self.ESCAPES})
        self.assertEqual(verdicts(root, "ruling.md"), [(citations.LANDS, (5, 6))])

    def test_a_code_block_is_not_read_for_quotations(self):
        spans = citations.quotations('    <tag name="x" other="y"/>\n')
        self.assertEqual(spans, [])

    def test_a_quotation_containing_code_is_still_quoted_in_full(self):
        spans = citations.quotations('says "`replace` takes the new text"')
        self.assertEqual([text for _, text in spans], ["`replace` takes the new text"])


class AQuotationAfterTwoCitationsIsTriedAgainstBoth(unittest.TestCase):
    """*"`spec.md:5-6` and `other.md:2` both state it in their own words"* and
    then a quotation: the words are one file's, and attributing them to the
    nearer citation alone leaves the other untested and silently stale."""

    BOTH = ('`spec.md:1-2` and `other.md:1` both say it \u2014 '
            '*"the vocabulary is structural and not semantic"*.')

    def test_the_further_citation_is_reported_when_the_quote_is_its_file(self):
        root = corpus(**{"spec.md": SPEC, "other.md": "# Other\n\nNothing.\n",
                         "ruling.md": self.BOTH})
        found = citations.check_document(os.path.join(root, "ruling.md"), [root])
        self.assertEqual([(r["verdict"], r["citation"], r["actual"]) for r in found],
                         [(citations.MOVED, "spec.md:1-2", (5, 6))])

    def test_a_landing_citation_beats_a_drifted_one_in_the_same_sentence(self):
        root = corpus(**{"spec.md": SPEC, "other.md": "# Other\n\nNothing.\n",
                         "ruling.md": ('`spec.md:1-2` and `spec.md:5-6` \u2014 '
                                       '*"the vocabulary is structural and not semantic"*.')})
        self.assertEqual(verdicts(root, "ruling.md"), [(citations.LANDS, (5, 6))])

    def test_neither_containing_it_is_still_undecidable(self):
        root = corpus(**{"spec.md": SPEC, "other.md": "# Other\n\nNothing.\n",
                         "ruling.md": ('`spec.md:5-6` and `other.md:1` \u2014 '
                                       '*"a sentence found in no file at all"*.')})
        self.assertEqual(verdicts(root, "ruling.md"), [(citations.UNDECIDABLE, None)])


class AQuotationsOwnClosingPunctuationIsNotPartOfTheQuote(unittest.TestCase):
    """A writer ending a sentence on a quotation puts the full stop inside the
    marks; the source it quotes carries on."""

    def test_a_borrowed_full_stop_does_not_make_the_quote_unfindable(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         '`spec.md:5-6` \u2014 *"the vocabulary is structural and not semantic."*'})
        self.assertEqual(verdicts(root, "ruling.md"), [(citations.LANDS, (5, 6))])

    def test_it_does_not_reach_for_words_the_target_lacks(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         '`spec.md:5-6` \u2014 *"the vocabulary is structural and prescriptive."*'})
        self.assertEqual(verdicts(root, "ruling.md"), [(citations.UNDECIDABLE, None)])


class TheUndecidableCitationsAreNamedAndNotOnlyCounted(unittest.TestCase):
    """A count nobody can resolve to a location is an exemption nobody can see,
    which is the thing `PINNED_REPORTS` is printed to avoid."""

    def test_the_report_says_where_to_look(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         'See `spec.md:5-6`, and *"this paragraph is the problem statement"*.'})
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            citations.main([root])
        report = buffer.getvalue()
        self.assertIn("ruling.md:1", report)
        self.assertIn("the quoted words are not in the cited file", report)
        self.assertIn("1 undecidable", report)

    def test_a_corpus_with_nothing_undecidable_says_nothing(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md":
                         '`spec.md:5-6` \u2014 *"the vocabulary is structural and not semantic"*.'})
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            citations.main([root])
        self.assertNotIn("Undecidable", buffer.getvalue())



class ABlockquoteBeneathACitationQuotesIt(unittest.TestCase):
    """Markdown's own way of quoting a passage, and what the corpus reaches for
    when the passage is long. The association rule ends at a paragraph break
    and a blockquote always sits behind one, so every one of them was invisible
    until the break was read as the separator it is."""

    def test_a_blockquote_is_read_as_the_quotation(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md": "\n".join([
            "The clause, at `spec.md:1-2`:",
            "",
            "> The vocabulary is structural and not",
            "> semantic: shape does not run out.",
            ""])})
        found = citations.check_document(os.path.join(root, "ruling.md"), [root])
        self.assertEqual([(r["verdict"], r["actual"]) for r in found],
                         [(citations.MOVED, (5, 6))])

    def test_one_that_lands_is_silent(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md": "\n".join([
            "The clause, at `spec.md:5-6`:",
            "",
            "> The vocabulary is structural and not",
            "> semantic: shape does not run out.",
            ""])})
        self.assertEqual(verdicts(root, "ruling.md"), [(citations.LANDS, (5, 6))])

    def test_it_does_not_reach_back_past_a_second_paragraph(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md": "\n".join([
            "The clause, at `spec.md:1-2`.",
            "",
            "An intervening paragraph that cites nothing at all.",
            "",
            "> The vocabulary is structural and not",
            "> semantic: shape does not run out.",
            ""])})
        self.assertEqual(verdicts(root, "ruling.md"), [])

    def test_code_inside_a_blockquote_is_kept_in_the_quotation(self):
        found = citations.blockquotes("> takes the `new text` and not a patch\n")
        self.assertEqual([body for _, body in found],
                         ["takes the `new text` and not a patch\n"])

    def test_an_inline_quotation_inside_one_is_not_counted_twice(self):
        root = corpus(**{"spec.md": SPEC, "ruling.md": "\n".join([
            "The clause, at `spec.md:5-6`:",
            "",
            '> The vocabulary is *"structural and not semantic"*: shape does not run out.',
            ""])})
        self.assertEqual(len(verdicts(root, "ruling.md")), 1)


if __name__ == "__main__":
    unittest.main()
