"""End-to-end tests for the external, post-write coherence checker.

The adapters are tiny executable Python programs, but the canvas, git history
and checker are all real.  Nothing here substitutes for the store write path:
every finding has to pass through it and leave the provenance it guarantees.
"""

import json
import os
import stat
import subprocess
import sys
from xml.etree import ElementTree

from tests.test_store import SHA, StoreTestCase

from canvas import coherence


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COHERENCE = os.path.join(ROOT, "bin", "canvas-coherence")


class CoherenceTestCase(StoreTestCase):
    def setUp(self):
        StoreTestCase.setUp(self)
        self.create(
            problem="Writes are synchronous.",
            value="The canvas states one current write model.",
        )

    def head(self):
        return self.git("rev-parse", "HEAD").strip()

    def state(self):
        with open(self.canvas_file(), "rb") as handle:
            return (
                handle.read(),
                self.head(),
                self.git("rev-list", "--count", "HEAD").strip(),
                self.git("status", "--porcelain"),
            )

    def primary_write(self, text="The queue absorbs write bursts."):
        base = self.head()
        code, stdout, stderr = self.run_canvas(
            "insert", "a-ledger-row", "--into", "root", "--text", text,
            "--why", "this node states the queue behavior being evaluated",
            "--base", base, "--author", "leo | step:implement",
        )
        self.assertEqual(0, code, stderr)
        node_id = stdout.decode("utf-8").splitlines()[0].split(": ", 1)[1]
        return node_id, self.head()

    def adapter(self, response=None, exit_code=0, marker=None):
        path = os.path.join(self.workspace, "adapter-%d.py" % len(os.listdir(self.workspace)))
        source = [
            "#!/usr/bin/env python3",
            "import json, sys",
            "request = json.load(sys.stdin)",
        ]
        if marker is not None:
            source.append("open(%r, 'w').write('called')" % marker)
        if response is not None:
            source.append("json.dump(%r, sys.stdout)" % response)
        source.append("raise SystemExit(%d)" % exit_code)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(source) + "\n")
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        return path

    def run_coherence(self, trigger, adapter):
        environment = dict(os.environ)
        environment["OPENCLAW_WORKSPACE"] = self.workspace
        return subprocess.run(
            [sys.executable, COHERENCE, "a-ledger-row", "--trigger", trigger,
             "--model-command", adapter],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )

    def finding(self, *node_ids, question=None, reason=None):
        return {
            "question": question or "%s disagree; which statement governs?" % " and ".join(node_ids),
            "reason": reason or "the current nodes prescribe incompatible write behavior",
            "node_ids": list(node_ids),
        }

    def nodes(self):
        return list(ElementTree.parse(self.canvas_file()).getroot())


class ARealWriteCanProduceAQuestion(CoherenceTestCase):
    def test_a_successful_primary_write_is_checked_and_one_finding_is_committed(self):
        conflicting_id, trigger = self.primary_write()
        problem_id = self.nodes()[0].get("id")
        adapter = self.adapter({
            "schema": 1,
            "findings": [self.finding(problem_id, conflicting_id)],
        })

        result = self.run_coherence(trigger, adapter)

        self.assertEqual(0, result.returncode, result.stderr.decode())
        questions = [node for node in self.nodes() if node.tag == "question"]
        self.assertEqual(1, len(questions))
        self.assertIsNone(questions[0].get("answered"))
        self.assertEqual({"id", "v"}, set(questions[0].attrib))
        self.assertIn(problem_id, questions[0].text)
        self.assertIn(conflicting_id, questions[0].text)
        self.assertEqual(1, int(self.git("rev-list", "--count", "%s..HEAD" % trigger)))

    def test_the_finding_has_independent_evidence_bearing_provenance(self):
        conflicting_id, trigger = self.primary_write()
        problem_id = self.nodes()[0].get("id")
        result = self.run_coherence(
            trigger,
            self.adapter({"schema": 1, "findings": [self.finding(problem_id, conflicting_id)]}),
        )
        self.assertEqual(0, result.returncode, result.stderr.decode())
        question_id = [node.get("id") for node in self.nodes() if node.tag == "question"][0]
        body = self.git("log", "-1", "--format=%B")
        self.assertIn("Canvas-Node: %s" % question_id, body)
        self.assertIn("Canvas-Author: canvas-coherence | trigger:%s" % trigger, body)
        self.assertIn("Canvas-Base: %s" % trigger, body)
        self.assertIn(trigger, body.splitlines()[0])
        self.assertIn(problem_id, body.splitlines()[0])
        self.assertIn(conflicting_id, body.splitlines()[0])

    def test_each_finding_is_its_own_question_and_commit(self):
        conflicting_id, trigger = self.primary_write()
        problem_id, value_id = [node.get("id") for node in self.nodes()[:2]]
        response = {
            "schema": 1,
            "findings": [
                self.finding(problem_id, conflicting_id),
                self.finding(value_id, conflicting_id),
            ],
        }
        result = self.run_coherence(trigger, self.adapter(response))
        self.assertEqual(0, result.returncode, result.stderr.decode())
        self.assertEqual(2, len([node for node in self.nodes() if node.tag == "question"]))
        commits = self.git("rev-list", "--reverse", "%s..HEAD" % trigger).splitlines()
        self.assertEqual(2, len(commits))
        first_body = self.git("show", "-s", "--format=%B", commits[0])
        second_body = self.git("show", "-s", "--format=%B", commits[1])
        self.assertIn("Canvas-Base: %s" % trigger, first_body)
        self.assertIn("Canvas-Base: %s" % commits[0], second_body)

    def test_a_checker_authored_question_cannot_trigger_a_recursive_check(self):
        conflicting_id, trigger = self.primary_write()
        problem_id = self.nodes()[0].get("id")
        first = self.run_coherence(
            trigger,
            self.adapter({"schema": 1, "findings": [self.finding(problem_id, conflicting_id)]}),
        )
        self.assertEqual(0, first.returncode, first.stderr.decode())
        finding_commit = self.head()
        before = self.state()
        marker = os.path.join(self.workspace, "adapter-was-called")
        recursive = self.run_coherence(
            finding_commit,
            self.adapter({"schema": 1, "findings": []}, marker=marker),
        )
        self.assertEqual(1, recursive.returncode)
        self.assertFalse(os.path.exists(marker))
        self.assertEqual(before, self.state())


class TheCommonAndFailureCasesWriteNothing(CoherenceTestCase):
    def test_no_finding_changes_no_byte_head_or_commit_count(self):
        _, trigger = self.primary_write()
        before = self.state()
        result = self.run_coherence(
            trigger, self.adapter({"schema": 1, "findings": []})
        )
        self.assertEqual(0, result.returncode, result.stderr.decode())
        self.assertEqual(before, self.state())

    def test_model_failure_preserves_the_successful_primary_write(self):
        inserted_id, trigger = self.primary_write()
        before = self.state()
        result = self.run_coherence(trigger, self.adapter(exit_code=7))
        self.assertEqual(2, result.returncode)
        self.assertIn("model", result.stderr.decode().lower())
        self.assertEqual(before, self.state())
        self.assertEqual(inserted_id, self.nodes()[-1].get("id"))

    def test_a_malformed_response_is_a_check_failure_and_writes_nothing(self):
        _, trigger = self.primary_write()
        before = self.state()
        result = self.run_coherence(
            trigger, self.adapter({"schema": 1, "findings": "none"})
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("response", result.stderr.decode().lower())
        self.assertEqual(before, self.state())

    def test_adapter_launch_failure_preserves_the_successful_primary_write(self):
        _, trigger = self.primary_write()
        before = self.state()
        result = self.run_coherence(
            trigger, os.path.join(self.workspace, "no-such-adapter")
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("start", result.stderr.decode().lower())
        self.assertEqual(before, self.state())

    def test_adapter_timeout_is_a_model_failure(self):
        with self.assertRaises(coherence.ModelFailure) as caught:
            coherence.call_model(
                [sys.executable, "-c", "import time; time.sleep(1)"],
                {"schema": 1},
                timeout=0.01,
            )
        self.assertIn("timed out", str(caught.exception))

    def test_the_adapter_does_not_receive_the_canvas_workspace(self):
        _, trigger = self.primary_write()
        adapter = os.path.join(self.workspace, "environment.py")
        with open(adapter, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "json.load(sys.stdin)\n"
                "assert 'OPENCLAW_WORKSPACE' not in os.environ\n"
                "json.dump({'schema': 1, 'findings': []}, sys.stdout)\n"
            )
        os.chmod(adapter, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        result = self.run_coherence(trigger, adapter)
        self.assertEqual(0, result.returncode, result.stderr.decode())


class ACoherenceWriteIsRefusedAgainstAFrozenCanvas(CoherenceTestCase):
    """The checker is a writer, so it inherits the frozen-canvas idiom."""

    def test_it_exits_one_before_calling_the_adapter_and_changes_nothing(self):
        _, trigger = self.primary_write()
        code, _, stderr = self.run_canvas(
            "freeze", "a-ledger-row", "--why",
            "done: the deliberately frozen fixture has completed its test work",
        )
        self.assertEqual(0, code, stderr)
        before = self.state()
        marker = os.path.join(self.workspace, "adapter-was-called")

        result = self.run_coherence(trigger, self.adapter(
            {"schema": 1, "findings": []}, marker=marker
        ))

        self.assertEqual(1, result.returncode, result.stderr.decode())
        self.assertEqual(b"", result.stdout)
        self.assertFalse(os.path.exists(marker))
        self.assertEqual(before, self.state())

    def test_a_stale_trigger_is_refused_before_calling_the_adapter(self):
        _, stale = self.primary_write()
        self.primary_write("A later primary write.")
        before = self.state()
        marker = os.path.join(self.workspace, "adapter-was-called")
        result = self.run_coherence(
            stale,
            self.adapter({"schema": 1, "findings": []}, marker=marker),
        )
        self.assertEqual(1, result.returncode)
        self.assertFalse(os.path.exists(marker))
        self.assertEqual(before, self.state())


class TheAdapterReceivesGroundedContext(CoherenceTestCase):
    def test_request_names_the_trigger_and_carries_node_history(self):
        inserted_id, trigger = self.primary_write()
        capture = os.path.join(self.workspace, "request.json")
        adapter = os.path.join(self.workspace, "capture.py")
        with open(adapter, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "request = json.load(sys.stdin)\n"
                "json.dump(request, open(%r, 'w'))\n"
                "json.dump({'schema': 1, 'findings': []}, sys.stdout)\n" % capture
            )
        os.chmod(adapter, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        result = self.run_coherence(trigger, adapter)
        self.assertEqual(0, result.returncode, result.stderr.decode())
        with open(capture, encoding="utf-8") as handle:
            request = json.load(handle)
        self.assertEqual(1, request["schema"])
        self.assertEqual(trigger, request["trigger_sha"])
        self.assertEqual(trigger, request["canvas_sha"])
        self.assertEqual("insert", request["trigger"]["verb"])
        self.assertEqual(inserted_id, request["trigger"]["node_id"])
        node = [each for each in request["nodes"] if each["id"] == inserted_id][0]
        self.assertEqual("text", node["element"])
        self.assertEqual(1, len(node["history"]))
        self.assertEqual("leo | step:implement", node["history"][0]["author"])


class TheCommandSurfaceIsFixed(CoherenceTestCase):
    def test_trigger_is_a_full_sha(self):
        _, trigger = self.primary_write()
        marker = os.path.join(self.workspace, "adapter-was-called")
        result = self.run_coherence(
            trigger[:12],
            self.adapter({"schema": 1, "findings": []}, marker=marker),
        )
        self.assertEqual(2, result.returncode)
        self.assertFalse(os.path.exists(marker))
        self.assertTrue(SHA.match(trigger))
