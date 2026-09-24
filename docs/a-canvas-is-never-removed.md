# A canvas is never removed, and what happened to the one that asked

*Written 2026-09-24 for Basecamp todo
[10337942957](https://app.basecamp.com/3934852/buckets/48039419/todos/10337942957),
ledger row `bc-10337942957-empty-problem-refused-before-writing`.*

`bin/canvas create` with an empty `--problem` used to land two of its three
commits and have the third refused. [`README.md`](../README.md#creating-a-canvas)
says why that happened and what `create` does now. This document answers the
other half of that todo, which is not about the bug at all: **there is no verb
that removes a canvas, and one half-made canvas sitting in the live store made
somebody ask whether there should be.**

---

## 1. The ruling: no, and the rule that says so already existed

`engineering-spec.md` §*Lifecycle* gives a canvas a life with an end in it —
born at `open`, grown through `executing`, frozen at `done` — and the word it
uses for what happens to it afterwards is **never deleted**. `README.md`'s
[*Ending a canvas*](../README.md#ending-a-canvas) carries that forward and
settles the shape of the question in advance:

> So there is no `abandon`, and the third outcome nobody has thought of yet —
> superseded, merged into another row, **cancelled before it started** — needs
> no fourth verb either.

A canvas made by a probe, or by a mistake, or by a row that turned out not to
be a row, *is* the third outcome. It is not a new case. The semantics live in
the `--why`, where they can be anything; a `remove` verb would put them in a
verb name, where they can only be what somebody thought of in advance — which
is the argument this repository has now made three times, and this is the third.

Two further things would be true of a removal verb, and each is on its own
enough:

- **An append-only store with a delete in it is not one.** The whole value of
  `state/canvas` is that `git log` is the record. A verb that removes a file
  leaves the history — so it removes nothing a reader was relying on — and a
  verb that removes the history rewrites the store, which is the one thing
  [`docs/unattributed-edits.md`](unattributed-edits.md) already refused to do
  for a commit that genuinely was wrong.
- **Nothing is harmed by a canvas that is not a row's.** Every reader of the
  store joins on a ledger id. A canvas whose ledger id names no row is reached
  by nothing except somebody listing the directory, and for that reader the
  freeze reason is a better answer than an absence would have been.

**What would reopen this.** A canvas whose *content* must not be kept — a
secret, or personal data committed by accident. That is not a "remove the
canvas" verb either; it is the ordinary secret-in-git problem, it is answered
by rotating the secret and rewriting the store under a recorded decision, and
nothing about it argues for a tenth verb.

## 2. What was done with `probe-empty-problem-20260924`

The first probe of the empty-`--problem` bug was run against the real store,
`/Users/lfigea/.openclaw/workspace/state/canvas`, before it was run against an
isolated one. It left a canvas with two commits and no expected-value node:

| | |
|---|---|
| `3aea0a2` | `create probe-empty-problem-20260924: born at open, root only` |
| `8f773f2` | `insert eh3b: the problem the ledger row states` — `eh3b` an empty `<text/>` |

It was declared where it was made, in
[`why-verdict/maintenance-check.md` §5.4](why-verdict/maintenance-check.md),
and left in place. `8f773f2` is the head that document pins in its §0, so it is
load-bearing for a reader re-running that check's commands.

**It has been frozen, not removed.** `freeze` is the verb this store already
has for the end of a canvas's life, it appends one commit, and it changes not a
byte of the document:

    bin/canvas freeze probe-empty-problem-20260924 \
      --why "cancelled before it started: this canvas is not a ledger row's. It is
             the artefact of a probe of the empty --problem bug, run against the live
             store before an isolated one, and it is half-made — node eh3b holds
             nothing and there is no expected-value node, because create's third
             commit was refused. It is frozen rather than removed: a canvas is never
             deleted, and one left writable is one somebody later mistakes for a live
             row mid-birth. The two commits that made it stand. Basecamp todo
             10337942957."

Frozen at `d7d4c79dfb1997ece103d4470db3670002e7f7d6`, 2026-09-24. The document
is unchanged — a freeze writes no byte of it — `bin/canvas read
probe-empty-problem-20260924` still returns it, and an `insert` against it is
now refused at exit `1` naming the freeze and its reason.

That is the same call, for the same reason, that `skill-validation-b-20260924`
already got at `c25aaf0` — *"a validation canvas that stays writable is one
somebody later mistakes for a live task."* This one is
worse than a validation canvas, because it is half-made: it has a problem node
holding nothing and no expected-value node at all, so a reader who found it
writable would be looking at a canvas that appears to be a live row mid-birth.
Frozen, it takes no more writes, and the reason in the log says what it is
before anybody has to go and look for a document that explains it.

**Nothing was rewritten.** `3aea0a2` and `8f773f2` stand, unchanged and in
place. §5.4's pinned head is still reachable and its commands still return what
it says they return; the freeze is a later commit, and the count of commits at
the head it pins is not affected by anything after it.

## 3. What this does not do

- **It does not reach for the other non-row canvases.** `skill-validation-20260924`
  is the same class of thing and is not frozen. It belongs to a different piece
  of work ([todo 10336754422](https://app.basecamp.com/3934852/buckets/48039419/todos/10336754422),
  whose own `-b` companion *was* frozen at the end of it), and disposing of
  another row's leftovers under this one's decision would put the reason in the
  wrong log. It is named here so that a reader who finds it knows it was seen.
- **It does not make `freeze` mean something new.** One verb for both endings
  was already the rule, and "cancelled before it started" was already one of
  the outcomes named as needing no verb of its own. This uses it; it does not
  extend it.
- **It does not add a check that refuses a canvas with no ledger row.** Nothing
  in this store knows what a ledger row is — `README.md`'s first constraint is
  that nothing here reads or writes `state/ledger` — so a guard like that would
  have to live in `bin/task-ledger`, and no evidence yet says it is needed.
