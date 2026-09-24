# Unattributed edits

Every edit this store made and cannot attribute. **There is exactly one**, and
this file is where it is recorded, because the alternative was recording it in
a Basecamp comment — which is not the repository, and not where a reader of
`bin/canvas history` will be standing when the tool does not answer them.

No history is rewritten to produce this file. The commit that caused it stands.
What is written down is what the store can still say about the edit, what it
cannot say, and why the gap cannot be closed from inside the store.

## The edit

- **Node** `ihfu`, in the canvas for ledger row
  `bc-10327745654-the-ledger-orchestrator-repository-git-g`.
- **What changed** — `v="1"` to `v="2"`, a full rewrite of the node's text.
- **The commit that carries it** —
  `59f6946c07e1a26202ac34fa63ef9bcef793301f`, 2026-09-24 15:09:57 +0200.
- **What that commit says about itself** — subject `insert ttz6: deciding to
  spend a test file on a Markdown document …`, trailers `Canvas-Node: ttz6`,
  `Canvas-Author: claude-opus-5 | canvas-follow-through`, `Canvas-Base:
  6628e1c97a9a561a9632b71e6edb9648be05e184`. Every one of those is about `ttz6`,
  a node in a **different** canvas — `bc-10336754422-canvas-operating-skill.xml`
  — which the same commit also changed.

`bin/canvas history bc-10327745654-the-ledger-orchestrator-repository-git-g
ihfu` prints one edit, the insert at `6628e1c`, and will never print this one.
That is correct behaviour and not a second defect: a node's history is the
commits whose `Canvas-Node:` trailer names it, and no commit names `ihfu`
twice. Loosening the match would make every node's history a guess.

## How it happened

`canvas/store.py::_write_and_commit` staged path-scoped — `git add -f --
<path>` — and then committed with **no pathspec**. `state/canvas` is one git
repository for every ledger row, which `node-identity.md` §1 settles and which
nothing here reopens; one repository is one *index*. So a commit with no
pathspec took whatever any other writer had staged in that index, and at
15:09:5x two writers were active.

This is the only time it happened. Read at head
`3b0cbd1954c78c59b67546c18872e8963cc5f6e9`, one commit out of 115 in the live
store touches more than one file, and it is this one. The count moves as the
store grows; the query does not, and it is the query and not the number that is
the claim:

    git -C "$OPENCLAW_WORKSPACE/state/canvas" log --format=%H |
      while read -r sha; do
        n=$(git -C "$OPENCLAW_WORKSPACE/state/canvas" show --name-only --format= "$sha" | grep -c .)
        [ "$n" -gt 1 ] && echo "$sha touches $n files"
      done

`--base` could not have caught it and is not at fault. Staleness is scoped to
the writer's own file by design — that is what keeps a read-then-write round
trip against an unchanged canvas silent in a busy store — and this was the
other file. The guard that *did* hold, "one edit is one node", is about nodes
within a document and not about documents within a commit.

It is fixed: the commit now names its path too, so git builds it from the head
plus that one file and leaves every other staged entry for the writer that
staged it. See [*What one commit contains*](../README.md#what-one-commit-contains)
and `tests/test_store.py::OneCommitIsOneCanvas`.

## What is recoverable, and what is not

**Recoverable — the edit itself.** The bytes are in the log and the store's own
read surface reaches them:

    git -C "$OPENCLAW_WORKSPACE/state/canvas" show 59f6946 \
        -- bc-10327745654-the-ledger-orchestrator-repository-git-g.xml

    bin/canvas read bc-10327745654-the-ledger-orchestrator-repository-git-g \
        --since 6628e1c

**Recoverable — who made it, and roughly what for.** Not from the store: from
the run that made it. The writer was the `ci-green` step of ledger row
`bc-10327745654-…`, and its own report says so in
`state/orchestrator/bc-10327745654-the-ledger-orchestrator-repository-git-g-state/bc-10327745654-the-ledger-orchestrator-repository-git-g-ci-green.report.md`:
it had written `ihfu` at `6628e1c`, noticed that its text fused two statements
— "the only workflow run on that sha is 36000852204 is not it but 36002820840",
which can be read as attributing the success to the run that had failed — and
issued a `replace` to separate them. That is the intent, in prose, from the
process that held it.

**Not recoverable — the reason, as the store records reasons.** A reason in
this store lives in a commit subject and nowhere else. The subject that carries
these bytes is `ttz6`'s. The `--why` the `ci-green` step wrote for its
correction was never committed anywhere, because its own `git commit` ran after
the sweep, found nothing left to commit, and exited non-zero. There is no
mechanism that can put that sentence into `59f6946` without rewriting history,
and rewriting it would falsify a commit another canvas's node legitimately
depends on. So it is recorded here as gone, and not quietly reconstructed: a
reason invented after the fact is a sentence in the history that reads like
evidence and is not.

## The second thing this cost, and why it cannot recur

The sweep did not merely steal the bytes; it left the store in a state worse
than either outcome. `_write_and_commit` takes its rename back when git refuses
the commit, so the `ci-green` step's rollback put the *pre-edit* `v="1"` back
on the path and staged it — while `v="2"` was already at HEAD, committed by
somebody else's commit. The next write by any writer would have carried the
revert silently. The step noticed, restored the file with `git restore
--source=HEAD --staged --worktree`, and said so in its report.

The rollback was right; its precondition was not. With the commit path-scoped,
the `ci-green` step's own commit finds its own staged file exactly where it left
it and succeeds, so there is no refusal, no rollback, and no edit of one
canvas riding in another canvas's commit.

## Adding to this file

If a second one is ever found, it goes here, in the same shape: the node, the
commit, what the commit says about itself, what is recoverable and from where,
and what is gone. A store that cannot attribute an edit should be able to say
which edit, once, in writing — not leave a reader to discover it by diffing.
