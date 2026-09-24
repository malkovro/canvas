"""The agent-facing skill says things about this tool. These keep it true.

`skills/canvas/SKILL.md` is loaded by an agent that will not read `README.md`
first — that is the whole point of it — so a sentence in it that has gone stale
is not a documentation defect, it is an agent driving the store on a rule that
no longer holds. The three facts below are the ones that can go stale silently
because they are *duplicated* from code: the verb list, the phrases the
back-reference guard refuses, and the two exit codes.

Nothing here checks prose. Wording, ordering and explanation are the author's,
and a test that pinned them would break on every improvement. What is pinned is
the correspondence: every verb the parser exposes is named, every phrase the
guard refuses is quoted, and no phrase is quoted that the guard permits — that
last one because a skill that invents a forbidden phrase teaches a writer to
avoid a reason the store would have accepted.
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "canvas", "SKILL.md")

sys.path.insert(0, ROOT)

from canvas import cli, store  # noqa: E402


def _skill_text():
    with open(SKILL, encoding="utf-8") as handle:
        return handle.read()


class SkillIsPresentAndWellFormed(unittest.TestCase):
    """It is discovered by the presence of the file and by its frontmatter."""

    def test_the_file_exists(self):
        self.assertTrue(
            os.path.isfile(SKILL),
            "skills/canvas/SKILL.md is what ~/.claude/skills/canvas symlinks to; "
            "moving or renaming it unregisters the skill on every machine that "
            "linked it",
        )

    def test_frontmatter_names_the_skill_and_describes_it(self):
        text = _skill_text()
        self.assertTrue(text.startswith("---\n"), "SKILL.md must open with frontmatter")
        frontmatter = text.split("---\n", 2)[1]
        self.assertRegex(
            frontmatter,
            r"(?m)^name:\s*canvas\s*$",
            "the skill's name is how an agent invokes it and must be `canvas`",
        )
        description = re.search(
            r"(?ms)^description:\s*[>|]-?\s*\n(.+?)^\w", frontmatter
        )
        self.assertIsNotNone(description, "SKILL.md must carry a description")
        self.assertGreater(
            len(description.group(1).strip()),
            80,
            "the description is the only thing an agent reads before deciding "
            "whether to load the skill",
        )


class SkillMatchesTheTool(unittest.TestCase):
    """The facts SKILL.md duplicates from code, checked against the code."""

    def test_every_verb_the_parser_exposes_is_named(self):
        text = _skill_text()
        verbs = sorted(
            action.choices
            for action in cli.build_parser()._subparsers._group_actions
            if hasattr(action, "choices")
        )[0]
        missing = [verb for verb in verbs if verb not in text]
        self.assertEqual(
            [],
            missing,
            "a verb the tool has and the skill does not name is a verb an agent "
            "will not reach for: %s" % ", ".join(missing),
        )

    def test_every_refused_phrase_is_quoted(self):
        text = _skill_text().lower()
        missing = [
            phrase
            for phrase in store._BACK_REFERENCE_PHRASES
            if "`%s`" % phrase not in text
        ]
        self.assertEqual(
            [],
            missing,
            "the guard refuses these and the skill does not warn about them, so "
            "a writer meets the refusal instead of the rule: %s"
            % ", ".join(missing),
        )

    def test_no_phrase_is_claimed_that_the_guard_permits(self):
        """The list in the skill is the list in the code, in both directions."""
        text = _skill_text()
        claimed = re.search(
            r"(?s)refuses a\s*\n?\s*reason containing any of seven phrases — (.+?) — that names",
            text,
        )
        self.assertIsNotNone(
            claimed,
            "SKILL.md must state the refused phrases in one place this test can "
            "find, so that the list cannot drift from store._BACK_REFERENCE_PHRASES",
        )
        listed = re.findall(r"`([^`]+)`", claimed.group(1))
        self.assertEqual(
            sorted(store._BACK_REFERENCE_PHRASES),
            sorted(listed),
            "the skill's list of refused phrases and the guard's own list have "
            "diverged",
        )

    def test_both_exit_codes_are_explained(self):
        text = _skill_text()
        for code, meaning in sorted(cli.EXIT_MEANING.items()):
            self.assertIn(
                "`%d`" % code,
                text,
                "exit %d is a thing an agent will see and has to act on "
                "differently: %s" % (code, meaning),
            )


if __name__ == "__main__":
    unittest.main()
