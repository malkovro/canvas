# Coherence checking

Settled 2026-09-24. This document decides where the model call described by
`engineering-spec.md` lives and how its findings enter a canvas. It chooses one
architecture: a separate synchronous post-write process. There is no model
path inside `bin/canvas`, no fallback path and no configuration that selects
between placements.

## Decision

The production orchestrator invokes `bin/canvas-coherence` after a successful
primary content write has committed. The checker owns model I/O and strict
interpretation of one response. It delegates every finding write to
`canvas.store.insert`.

That boundary preserves two rules at once. `README.md` section *Running the
tests* keeps `bin/canvas` install-free, network-free and standard-library-only;
`rendering.md` section 1 records why adding a dependency and failure mode to a
cheap local Canvas operation would be a product change rather than an
implementation detail. The store remains the single writer, so its existing
id minting, required reason, declared base, author trailer, schema validation,
one-node commit and frozen-canvas refusal apply without being reimplemented.

The trade is explicit: model latency and provider failure are visible to the
orchestrator after the primary write rather than hidden inside its commit path.
The call is synchronous so orchestration can report its result before moving
on, but the triggering write is already committed and is never rolled back.

## Trigger boundary

The command is:

    bin/canvas-coherence <ledger-id> --trigger <full-head-sha> \
        --model-command <adapter> [<adapter-argument> ...]

Orchestration invokes it once after `create` has completed its initial commits,
or after a human/agent `insert`, `replace`, `remove` or `move` exits `0`. It
does not invoke it after `read`, `render`, `history` or `freeze`, and does not
invoke it for `<question>` inserts authored by `canvas-coherence`.

The trigger is the full forty-character head returned by the successful write.
Before starting the adapter, the checker uses the store's write preflight to
refuse a frozen canvas, requires that trigger to still be the current head, and
requires the commit to be a one-node Canvas write whose only changed path is
the requested ledger's XML file. Repository HEAD alone is insufficient because
one store contains multiple canvases. It checks the head again before writing
findings. A frozen canvas, stale trigger, or trigger belonging to another
canvas is exit `1`, with no model call and no write.

## Adapter contract

The adapter is the only model boundary. It receives one UTF-8 JSON object on
stdin and must emit one UTF-8 JSON object on stdout. It does not inherit
`OPENCLAW_WORKSPACE`, and cannot choose the Canvas author, reason, position,
element type or flags. Provider credentials, SDKs, network access and retries
remain adapter concerns rather than Canvas dependencies. The subprocess has a
finite sixty-second timeout.

The version-1 request contains exactly the information needed to ground a
reading of the current document:

- `schema`: integer `1`.
- `ledger`, `trigger_sha` and `canvas_sha`.
- `canvas_xml`: the complete current document.
- `trigger`: the commit sha and subject, verb, node id where it named one,
  author and recorded reason.
- `nodes`: every node in document order, with id, element name, text,
  attributes and its full edit history oldest first.
- `instruction`: find only contradictions introduced or exposed by the
  trigger; do not rewrite, advise or manufacture a finding; an empty result is
  expected.

The version-1 response is:

```json
{
  "schema": 1,
  "findings": [
    {
      "question": "Nodes ab12 and cd34 disagree about write ordering; which statement governs?",
      "reason": "The two current nodes prescribe incompatible write behavior.",
      "node_ids": ["ab12", "cd34"]
    }
  ]
}
```

`{"schema": 1, "findings": []}` is the only no-finding response. Unknown or
missing keys, wrong types, empty strings, duplicate node ids, ids absent from
the current document, or a question that does not name each implicated id are
protocol failures. The complete response is validated before any finding is
written.

## Finding writes and provenance

Each finding becomes one call to `store.insert` with `node_type="question"`,
`into="root"`, and the question as its text. It has no `answered` attribute,
so it is open by absence. It gains no pointer attribute and no sibling note
about openness. The schema, element set and attribute set do not change.

The checker, not the adapter, derives the provenance:

- author: `canvas-coherence | trigger:<full-trigger-sha>`;
- reason: `coherence check after <trigger-sha> found nodes <ids> disagree:
  <model reason>`;
- base: the trigger sha for the first finding and the preceding finding commit
  for each later one.

Consequently every contradiction has a minted id, independent author,
evidence-bearing reason, truthful `Canvas-Base`, and its own commit. There is
no batch write and no rollback of an earlier finding if a later store insert is
refused.

## Outcomes

- No finding: exit `0`; no bytes, id, temporary or commit are written.
- One or more findings: exit `0` after the sequential store inserts.
- Adapter launch, timeout, non-zero exit, invalid UTF-8/JSON or invalid response
  contract: exit `2`; no finding is written and the primary commit remains.
- Store refusal, including frozen canvas or stale trigger: exit `1`; nothing is
  written by the refused operation.

This checker answers coherence inside the document. It does not verify the
canvas against reality; `engineering-spec.md` keeps that separate and continues
to put evidence for real-world claims in each edit's free-text reason.
