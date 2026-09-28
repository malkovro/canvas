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

> **Amended 2026-09-28.** The ruling in §1 stands. The *mechanism* §2 used to
> carry it out does not: a freeze no longer stops writes, so freezing a
> non-row canvas no longer disposes of it. §4 says exactly which sentences
> that reopens and what replaces them. Read §2 as the dated record of what was
> done on 2026-09-24, which is what it is.

---

## 1. The ruling: no, and the rule that says so already existed

`engineering-spec.md` §*Lifecycle* gives a canvas a life with an end in it —
born at `open`, grown through `executing`, ended at `done` — and the word it
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
probe-empty-problem-20260924` still returns it, and an `insert` against it was
refused at exit `1` naming the freeze and its reason. *(That last clause was
true when it was written and is no longer — see §4.)*

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

## 4. Amendment, 2026-09-28: the disposal mechanism is reopened, the ruling is not

*Written for ledger row `bc-10348813099-remove-terminal-freeze`, which removed
the Canvas terminal freeze: a frozen canvas now takes writes like any other,
and the exit-1 refusal that used to stand behind the word "frozen" is gone.*

**What stands.** §1 in full. There is still no verb that removes a canvas, and
not one of the three arguments for that turns on the refusal: *never deleted*
is the spec's word, an append-only store with a delete in it is not one, and
nothing is harmed by a canvas that is not a row's, because every reader of the
store joins on a ledger id. The *What would reopen this* clause is unchanged
and this is not it. §3 stands too.

**What is reopened: the three sentences in §2 that say a freeze disposes of
anything.**

- *"It is frozen rather than removed: a canvas is never deleted, and one left
  writable is one somebody later mistakes for a live row mid-birth"* — the
  first clause stands, the second no longer follows. Every frozen canvas is
  left writable now; that is what the removal did.
- *"a validation canvas that stays writable is one somebody later mistakes for
  a live task"* (quoted from `skill-validation-b-20260924`'s freeze reason) —
  same.
- *"Frozen, it takes no more writes"* — false as written.

**What replaces them.** A freeze is now an end marker and not a gate, so what
it does for a non-row canvas is what it does for every other one: it records,
in the log, that this canvas's work ended and why. `bin/canvas read <id>
--frozen` prints that reason. For a half-made probe canvas the reason is
exactly the thing a reader who finds it needs — *this is not a live row, here
is what it is* — and that was always the more load-bearing half of §2's
argument. What the freeze no longer supplies is the *guarantee* that nobody
writes to it. Nothing supplies that now, for any canvas, by design.

**The three canvases this makes writable again**, named because leaving them
unnamed would be leaving the reader to find out: `probe-empty-problem-20260924`
(frozen at `d7d4c79dfb1997ece103d4470db3670002e7f7d6`),
`skill-validation-20260924` (frozen at
`058d95f143394a1f32ae24fbc21fcc6091e30aa1`) and `skill-validation-b-20260924`
(frozen at `c25aaf0795c1f2f9fdbc745aa32590a929d307a1`). All three keep their
freeze commits, all three still answer `read --frozen` with the reason that
says what they are, and all three now accept an edit. That is accepted rather
than mitigated: the cost of somebody editing a dead probe canvas is one more
commit in a log that records who wrote it and why, and the removal was taken
on the ground that a refusal is the more expensive of the two.

**What would reopen *this*.** Somebody actually mistaking one of the three for
a live row and writing to it as though it were. That would be evidence for a
guard, and the place for the guard is the one §3 already names — `bin/task-ledger`,
which is the only thing that knows what a ledger row is — and not a return of
the refusal, which would take the whole store back with it.
