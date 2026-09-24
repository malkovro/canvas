"""The external, synchronous coherence check run after a successful write.

This module owns model I/O and the response contract only.  Findings go
through ``canvas.store.insert`` so ids, reasons, bases, validation, freeze
guards and one-node commits continue to have one implementation.
"""

import argparse
import json
import os
import re
import subprocess
import sys

from canvas import document, refusal, store


SCHEMA_VERSION = 1
MODEL_TIMEOUT_SECONDS = 60
_FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
_RESPONSE_KEYS = {"schema", "findings"}
_FINDING_KEYS = {"question", "reason", "node_ids"}


class ModelFailure(refusal.Refused):
    """The adapter did not return a usable model result. Exit 2."""


def _model_failure(message):
    return ModelFailure(
        message,
        "repair the model adapter and re-run this check against the same "
        "successful trigger commit while it is still the canvas head; the "
        "triggering write remains committed and no finding was written",
        about=["coherence model response"],
    )


def _trigger_record(canvas_dir, trigger):
    records = store._log(
        canvas_dir,
        ["-1", trigger],
        "cannot read coherence trigger %s" % trigger,
    )
    if not records or records[0].sha != trigger:
        raise store.Refusal(
            "the coherence trigger %s is not a commit this canvas store can read"
            % trigger,
            "run `bin/canvas read <ledger-id>` and re-run with the full "
            "Canvas-Base sha it prints; no model was called and nothing was written",
            about=["trigger commit %s" % trigger],
        )
    record = records[0]
    edit = store._edit_from(record.sha, record.subject, record.author)
    return {
        "sha": record.sha,
        "subject": record.subject,
        "verb": edit.verb,
        "node_id": record.named[0] if len(record.named) == 1 else None,
        "author": edit.author,
        "reason": edit.reason,
    }


def _require_trigger_for_canvas(canvas_dir, path, trigger, record):
    """Refuse a repository HEAD that is not a primary write to ``path``."""
    changed = store._git_checked(
        canvas_dir,
        "diff-tree",
        "--root",
        "--no-commit-id",
        "--name-only",
        "-r",
        trigger,
    ).splitlines()
    expected = os.path.relpath(path, canvas_dir)
    if (
        changed != [expected]
        or record["verb"] not in {"insert", "replace", "remove", "move"}
        or record["node_id"] is None
        or not record["author"]
    ):
        raise store.Refusal(
            "the coherence trigger %s is not a successful primary write to "
            "the canvas for %s" % (trigger, os.path.basename(path)[:-4]),
            "pass the full head sha returned by the successful write to this "
            "ledger; no model was called and nothing was written",
            about=[
                "trigger commit %s" % trigger,
                "expected canvas path %s" % expected,
                "changed paths %s" % (", ".join(changed) if changed else "none"),
            ],
        )


def _node_context(ledger_id, root):
    nodes = []
    for node in root.iter():
        node_id = node.get("id")
        if node_id is None:
            continue
        nodes.append({
            "id": node_id,
            "element": node.tag,
            "text": node.text or "",
            "attributes": dict(node.attrib),
            "history": [
                {
                    "sha": edit.sha,
                    "verb": edit.verb,
                    "reason": edit.reason,
                    "author": edit.author,
                }
                for edit in store.history(ledger_id, node_id)
            ],
        })
    return nodes


def build_request(ledger_id, trigger):
    """Preflight the store and return the adapter request and current head."""
    if not _FULL_SHA.match(trigger):
        raise store.ToolProblem(
            "--trigger must be a full forty-character lowercase commit sha",
            "re-run with the complete Canvas-Base sha printed by the successful "
            "primary write; no model was called and nothing was written",
            about=["option --trigger", "value %r" % trigger],
        )

    # This is the ordinary write preflight.  In particular, its first answer
    # for an ended canvas is the store's exit-1 frozen refusal, before a model
    # process can start and before an id can be minted.
    canvas_dir, path, root, head = store._open_canvas(
        ledger_id, "run coherence check"
    )
    if head != trigger:
        raise store.Refusal(
            "refusing coherence check for trigger %s: the current canvas head "
            "is %s, so the trigger is stale" % (trigger, head),
            "re-read with `bin/canvas read %s` and run the check for the newest "
            "successful primary write; no model was called and nothing was written"
            % ledger_id,
            about=[
                "ledger id %s" % ledger_id,
                "trigger commit %s" % trigger,
                "canvas head %s" % head,
            ],
        )

    trigger_record = _trigger_record(canvas_dir, trigger)
    _require_trigger_for_canvas(canvas_dir, path, trigger, trigger_record)

    read_sha, body, problems, _ = store.read(ledger_id)
    if problems:
        raise store.Refusal(
            "the canvas for %s is invalid and cannot be checked" % ledger_id,
            "repair the nodes named by `bin/canvas-validate %s`, then re-run; "
            "no model was called and nothing was written" % path,
            about=["ledger id %s" % ledger_id, "canvas %s" % path],
            details=problems,
        )
    if read_sha != head:
        raise store.Refusal(
            "the canvas head moved while the coherence check was preparing its input",
            "re-read with `bin/canvas read %s` and run the check for the newest "
            "successful primary write; no model was called and nothing was written"
            % ledger_id,
            about=["ledger id %s" % ledger_id, "canvas head %s" % read_sha],
        )

    if trigger_record["author"].startswith("canvas-coherence | trigger:"):
        raise store.Refusal(
            "refusing to run a coherence check recursively for checker-authored "
            "commit %s" % trigger,
            "run the check only for the successful human or agent primary write; "
            "no model was called and nothing was written",
            about=["ledger id %s" % ledger_id, "trigger commit %s" % trigger],
        )

    request = {
        "schema": SCHEMA_VERSION,
        "ledger": ledger_id,
        "trigger_sha": trigger,
        "canvas_sha": head,
        "canvas_xml": body.decode("utf-8"),
        "trigger": trigger_record,
        "nodes": _node_context(ledger_id, root),
        "instruction": (
            "Find only contradictions or coherence questions introduced or "
            "exposed by the trigger. Do not rewrite, advise, or manufacture a "
            "finding. Return an empty findings array when there is no actual "
            "contradiction; that is the expected common result."
        ),
    }
    return request, head


def call_model(command, request, timeout=MODEL_TIMEOUT_SECONDS):
    """Run the one adapter subprocess and decode its one JSON response."""
    environment = dict(os.environ)
    # The adapter interprets a request and returns JSON.  It is deliberately
    # not a Canvas writer and receives no path to the live workspace.
    environment.pop("OPENCLAW_WORKSPACE", None)
    try:
        result = subprocess.run(
            command,
            input=json.dumps(request, ensure_ascii=False).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        raise _model_failure(
            "coherence model command timed out after %s seconds" % timeout
        )
    except OSError as error:
        raise _model_failure(
            "cannot start coherence model command: %s" % error
        )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise _model_failure(
            "coherence model command exited %d%s"
            % (result.returncode, ": %s" % detail if detail else "")
        )
    try:
        output = result.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _model_failure(
            "coherence model response is not valid UTF-8: %s" % error
        )
    try:
        return json.loads(output)
    except (TypeError, ValueError) as error:
        raise _model_failure(
            "coherence model response is not valid JSON: %s" % error
        )


def validate_response(response, current_ids):
    """Return validated findings, refusing every shape outside schema 1."""
    if not isinstance(response, dict) or set(response) != _RESPONSE_KEYS:
        raise _model_failure(
            "coherence model response must contain exactly schema and findings"
        )
    if type(response["schema"]) is not int or response["schema"] != SCHEMA_VERSION:
        raise _model_failure("coherence model response schema must be the integer 1")
    findings = response["findings"]
    if not isinstance(findings, list):
        raise _model_failure("coherence model response findings must be an array")

    known = set(current_ids)
    checked = []
    for index, finding in enumerate(findings):
        label = "coherence model response finding %d" % (index + 1)
        if not isinstance(finding, dict) or set(finding) != _FINDING_KEYS:
            raise _model_failure(
                "%s must contain exactly question, reason and node_ids" % label
            )
        question = finding["question"]
        reason = finding["reason"]
        node_ids = finding["node_ids"]
        if not isinstance(question, str) or not question.strip():
            raise _model_failure("%s question must be a non-empty string" % label)
        if not isinstance(reason, str) or not reason.strip():
            raise _model_failure("%s reason must be a non-empty string" % label)
        if not isinstance(node_ids, list) or not node_ids:
            raise _model_failure("%s node_ids must be a non-empty array" % label)
        if any(not isinstance(node_id, str) or not node_id for node_id in node_ids):
            raise _model_failure("%s node_ids must contain only strings" % label)
        if len(node_ids) != len(set(node_ids)):
            raise _model_failure("%s contains duplicate node ids" % label)
        absent = [node_id for node_id in node_ids if node_id not in known]
        if absent:
            raise _model_failure(
                "%s names node ids absent from the current canvas: %s"
                % (label, ", ".join(absent))
            )
        unnamed = [node_id for node_id in node_ids if node_id not in question]
        if unnamed:
            raise _model_failure(
                "%s question does not name its implicated node ids: %s"
                % (label, ", ".join(unnamed))
            )
        checked.append({
            "question": question.strip(),
            "reason": reason.strip(),
            "node_ids": node_ids,
        })
    return checked


def write_findings(ledger_id, trigger, base, findings):
    """Insert each actual contradiction as one open question and one commit."""
    written = []
    canvas_dir = store.canvas_directory()
    current = store.head_sha(canvas_dir)
    if current != base:
        raise store.Refusal(
            "refusing coherence findings for trigger %s: the canvas moved to %s "
            "while the model check was running" % (trigger, current),
            "re-read with `bin/canvas read %s` and run the check for the newest "
            "successful primary write; no finding was written" % ledger_id,
            about=[
                "ledger id %s" % ledger_id,
                "trigger commit %s" % trigger,
                "canvas head %s" % current,
            ],
        )
    for finding in findings:
        ids = ", ".join(finding["node_ids"])
        why = (
            "coherence check after %s found nodes %s disagree: %s"
            % (trigger, ids, finding["reason"])
        )
        node_id, base, _ = store.insert(
            ledger_id,
            why,
            into=document.ROOT,
            node_type="question",
            text=finding["question"],
            author="canvas-coherence | trigger:%s" % trigger,
            base=base,
        )
        written.append((node_id, base))
    return written


def check(ledger_id, trigger, model_command):
    request, base = build_request(ledger_id, trigger)
    response = call_model(model_command, request)
    findings = validate_response(
        response, [node["id"] for node in request["nodes"]]
    )
    return write_findings(ledger_id, trigger, base, findings)


def _parser():
    parser = argparse.ArgumentParser(
        prog="canvas-coherence",
        description="check one successful canvas write for contradictions",
    )
    parser.add_argument("ledger_id")
    parser.add_argument("--trigger", required=True, metavar="SHA")
    parser.add_argument(
        "--model-command",
        required=True,
        nargs=argparse.REMAINDER,
        metavar="COMMAND",
        help="adapter executable and arguments; this must be the final option",
    )
    return parser


def _print_refusal(error, code):
    meaning = (
        "the request is wrong against the store as it stands; re-read and re-decide"
        if code == 1
        else "the coherence check, its model adapter or its environment is wrong; "
        "the successful primary write remains committed"
    )
    sys.stderr.write(
        "\n".join(refusal.lines("canvas-coherence", error, code, meaning)) + "\n"
    )


def main(argv=None):
    args = _parser().parse_args(argv)
    if not args.model_command:
        _parser().error("--model-command requires an executable")
    try:
        written = check(args.ledger_id, args.trigger, args.model_command)
    except store.Refusal as error:
        _print_refusal(error, 1)
        return 1
    except (store.ToolProblem, ModelFailure) as error:
        _print_refusal(error, 2)
        return 2
    for node_id, sha in written:
        sys.stdout.write("Canvas-Node: %s\nCanvas-Base: %s\n" % (node_id, sha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
