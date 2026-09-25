# What running the experiment turned out to require

**This is not the second reading.** It is the record of an attempt to run the
experiment [`./maintenance-check.md`](./maintenance-check.md) §6 named — *a
person, a canvas of their own on a real task they are working, days rather than
hours, the tab in front of them, and nothing instructing them to write* — and of
the two things that attempt found standing in front of it. One of them is
arithmetic. The other is a finding, and it is the reason waiting will not be
enough on its own.

It is a fourth document beside [`./VERDICT.md`](./VERDICT.md),
[`./off-corpus-check.md`](./off-corpus-check.md) and
[`./maintenance-check.md`](./maintenance-check.md), and amends none of them.

**Written for Basecamp todo
[10337947736](https://app.basecamp.com/3934852/buckets/48039419/todos/10337947736)**,
*Run the experiment the first reading could not*, on 2026-09-25, ledger row
`bc-10337947736-run-the-experiment-a-person-a-canvas-days`.

---

## 0. The store this reads, named exactly

- **Path:** `/Users/lfigea/.openclaw/workspace/state/canvas`, which is what
  `$OPENCLAW_WORKSPACE/state/canvas` resolves to on the machine that runs the
  ledger — the same store `maintenance-check.md` §0 pins.
- **Head at the time of reading:** `48159af029eefd50f676727e8d4f995e24bea49c`,
  **174 commits**, twenty-two files.
- **First commit:** 2026-09-24 12:51:03 +0200. **Last:** 2026-09-25 02:02:29 +0200.

**This reading is in its own corpus and says where.** Its ledger row's three
birth commits (`bc-10337947736-run-the-experiment-a-person-a-canvas-days`,
author `task-ledger | open`) and the three nodes this reading wrote to that
canvas while working (`claude-opus-5[1m] | canvas-follow-through`) are in the
174. None of the counts in §2 is taken from any of the six: §2.1 counts person
and page writes, and none of the six is either.

Every command below names that sha rather than `HEAD`, so a later reader gets
the numbers this document reports rather than the numbers of whatever the store
has become since — which is the failure §3 is about, arriving in the smallest
possible form.

```bash
STORE=/Users/lfigea/.openclaw/workspace/state/canvas
HEAD=48159af029eefd50f676727e8d4f995e24bea49c
git -C "$STORE" rev-list --count "$HEAD"
git -C "$STORE" ls-tree --name-only "$HEAD" | grep -c '\.xml$'
git -C "$STORE" log --reverse --format=%ad --date=iso "$HEAD" | head -1
git -C "$STORE" log -1 --format=%ad --date=iso "$HEAD"
```

## 1. The window does not exist yet, and that part is arithmetic

The store is **thirteen hours and eleven minutes old**, end to end, including
every hour in which nobody was awake. The todo asks for a reading *"over a named
window of at least several days"*. Nothing done on 2026-09-25 can produce a
window of several days ending on 2026-09-25, so this is not a thing that was
attempted and failed; it is a thing that cannot be attempted yet.

That much was foreseeable. §2 is not.

## 2. The subject does not exist either, and waiting alone will not create one

**Every canvas in this store that has outlived two hours did so because
something went wrong.** That sentence is the finding, and it is what turns *wait
several days* into a precondition somebody has to supply.

Nineteen of the twenty-two files belong to ledger rows. (Three do not: `skill-validation-20260924`,
`skill-validation-b-20260924` and the §5.4 probe.) Sixteen of the nineteen
are frozen, and their lifetimes — birth to freeze — are:

| | minutes |
|---|--:|
| shortest | 3.5 |
| **median** | **29.3** |
| longest | 130.8 |

Three are unfrozen, and not one of them is a subject. *Open* is measured to the
pinned head, so it is a number a later reader gets back rather than a number
that grows while nobody looks:

| canvas | open at `48159af` | why it is still open |
|---|--:|---|
| `duplicate-invoice-criterion-output-schema` | 11.3 h | its row reached `done` at 17:28 on 2026-09-24 and the automatic freeze **failed** — `canvas:failed`, `exit 2` |
| `bc-10336256184` | 9.0 h | its row has been sitting in `executing` since 17:02 the previous afternoon |
| `bc-10337947736-…-a-canvas-days` | 0.1 h | this reading's own row, born minutes before this sentence |

So the store has never held a canvas that stayed writable for days *because the
work it belonged to lasted days*. It has held one whose freeze crashed, one
whose row is stuck, and one that is minutes old.

A canvas open by accident is the same bad sample the first reading had to work
with, arriving from the other end. §1.4 discounted its one person-written canvas
because the row's automatic `create` had failed, so making the canvas at all was
already an intervention; `duplicate-invoice-criterion-output-schema` is now
*also* the canvas whose `freeze` failed, and `bc-10336256184` is open only
because nothing is finishing its row.

The precise statement is therefore not *"wait several days"*. It is:

> **The experiment's subject cannot come from a row the follow-through loop
> drives, because the loop freezes canvases faster than a person could come back
> to one — a median of twenty-nine minutes, and never more than 2h11m when
> nothing goes wrong. It has to come from a row a person owns and works by hand
> over days, and this store has never held one.**

That precondition is a person's to supply, and supplying it is *not* the same as
being asked to write. A row somebody opens for work they were going to do anyway
leaves the question intact; a row opened in order to be written to does not.

```bash
# every freeze, with its time
git -C "$STORE" log --format='%at%x01%(trailers:key=Canvas-Freeze,valueonly)' "$HEAD" \
  | grep -v '^[0-9]*.$'
# every birth
for f in $(git -C "$STORE" ls-tree --name-only "$HEAD" | grep '\.xml$'); do
  printf '%s %s\n' "$(git -C "$STORE" log --format=%at "$HEAD" -- "$f" | tail -1)" "$f"
done
# which of them are a ledger row's
ls /Users/lfigea/.openclaw/workspace/state/ledger/*.json
```

### 2.1 What the hours since the first reading did say

Eleven more ledger-row canvases were born between the head
`maintenance-check.md` pins (`8f773f2`, 2026-09-24 18:08:08) and this one. Across
all eleven:

- **No person wrote to any of them.** All 36 `leo | via claude` commits in the
  store are still on the single file `duplicate-invoice-criterion-output-schema.xml`,
  and the last of them is still **14:48:58 on 2026-09-24** — the same burst §1.2
  describes. Nothing has been added to that census in the seven hours and fifty-four
  minutes since.
- **The tab still has zero writes.** No commit in the store carries
  `Canvas-Author: lfigea`, which is what `bin/watch-runs-web` writes for an edit
  made from the page. The three `lfigea | by-hand` commits are the CLI's default
  author, and are the §5.4 probe and its freeze.

This is a second data point pointing the same way as the first, and it is worth
almost exactly as much: eleven agent-driven rows, over one night, on a machine
whose only person was asleep for most of it. It is not evidence about a habit,
and §5 says so again rather than relying on this sentence being remembered.

## 3. The first reading's denominator had already stopped being re-derivable

`maintenance-check.md` §0 states its denominator — 7.49 canvas-hours — as an
intersection with *"the 14:46:37–18:08:08 window in which pid 33867 has been
running"*, and gives the command for it:

```bash
ps -o lstart= -p 33867
```

**That process has exited. The command prints nothing.** The number the document
published can no longer be re-derived from the document itself, which is the one
property the second reading is required to have — and over a window of days it
could not have been recovered by any command issued afterwards, because nothing
on this machine kept the fact.

Nor is one window the right shape for a longer one. Three different
`bin/watch-runs-web` processes ran between 00:10 and 01:23 on 2026-09-25 — pids
`35209`, `93489` and `72266` — because the page is restarted whenever a merge is
deployed, which on this machine happens several times an hour.

So the reading is now **sampled as it happens rather than reconstructed
afterwards**. `tasks/deployment-freshness` already asked `ps` which processes
were running out of the checkout and when each started, every fifteen minutes,
and printed it into a run log; it now also appends it to
`$OPENCLAW_WORKSPACE/state/deployment/freshness.jsonl`. `bin/canvas-hours` turns
that series plus this store's own git log into the denominator, and states two
bounds rather than absorbing them: a process's **start** is exact while its
**end** is only a last sighting, so a window is `start .. last seen` and is never
joined to the next one; and a stretch of the requested window falling outside the
series is **named as unsampled, not counted as zero**. Where an error remains it
undercounts, because this number sits underneath a count of writes.

That work is in the ledger-orchestrator repository, merged as
[`ledger-orchestrator#121`](https://github.com/malkovro/ledger-orchestrator/pull/121)
— `orchestrator/canvas_hours.py`, `orchestrator/deployment.py`,
`bin/canvas-hours`, and the decision in `docs/canvas-hours.md` — and **nothing
in it teaches this repository about the ledger**: the store's git log is one
side, a fact about processes on that machine is the other, and they are measured
separately, exactly as the first reading insisted.

**The series begins 2026-09-25 01:58.** Everything before that is unsampled and
will be reported as unsampled.

## 4. What the second reading will be

- A window running forward from **2026-09-25 01:58**, of at least several days,
  named by its two ends.
- A named set of ledger rows, and a denominator stated the same way §0 of the
  first reading states it — canvas-hours in which a canvas was born, not yet
  frozen, and the page was up — derived from the sample series and re-derivable
  by `bin/canvas-hours --since … --until …`.
- Counts from `Canvas-Author` trailers, matched exactly: `lfigea` is the page and
  `lfigea | by-hand` is the CLI, and the whole question turns on the difference.
- Whether each of the three reversal conditions in
  `ledger-orchestrator/docs/canvas-in-prompts.md` fired, naming rows and shas —
  and in particular whether the over-budget notice has yet had anything to work
  on, which as of this head it still has not. The largest canvas in the store is
  still `bc-10327745654-the-ledger-orchestrator-repository-git-g` at the same
  **11,495 bytes of XML** the first reading measured — 11,549 characters as
  `read` prints it, **57.7% of the 20,000-character budget** — and eleven more
  canvases have been born without displacing it. The condition remains
  *untested* rather than refuted, exactly as §2 of the first reading left it.
- What the evidence does not support, in its own words.

And the four things that are not up for grabs, restated because a document that
is finished months from now will be read by somebody who never saw the todo:
**nobody is prompted, reminded or nudged to write**; the answer is **never an
attribute** (`engineering-spec.md:291-295` — the todo and this document's first
draft both cited `280-284`, which is the passage about a contradiction landing
as a `<question>` node; the sentence that refuses an attribute is *"A state
field distinguishing what was asserted from what was verified was considered and
rejected as premature… it should be fixed with evidence in the reason before it
is fixed with a new attribute"*, and it is five lines further down); a finding of
staleness is **not a
licence to escalate** (`canvas-in-prompts.md` §2); and **nothing here learns
about the ledger**.

## 5. What this document does not claim

- **It does not claim the experiment failed.** It has not run. A reading that
  called thirteen hours of agent-driven rows an answer would be the failure
  `product-spec.md:124` describes, arriving as a measurement instead of as a
  canvas.
- **It does not grade a reason and does not decide whether a silence is
  staleness.** `VERDICT.md` owns the first; §1.4 of the first reading left the
  second open, and nothing here closes it.
- **It does not argue that the follow-through loop should close rows more
  slowly.** Twenty-nine minutes is what the loop is *for*. Changing how work is
  done so that a measurement becomes convenient is the wrong order, and the
  finding in §2 is a statement about where the experiment's subject must come
  from, not a request to slow anything down.
- **It is still one machine and one store**, and still a reader at no distance:
  the bar in §1 of the first reading is about somebody months later, and
  everything read here is hours old.

---

*Written 2026-09-25 for Basecamp todo
[10337947736](https://app.basecamp.com/3934852/buckets/48039419/todos/10337947736),
ledger row `bc-10337947736-run-the-experiment-a-person-a-canvas-days`. Store
`/Users/lfigea/.openclaw/workspace/state/canvas` at
`48159af029eefd50f676727e8d4f995e24bea49c`, 174 commits.*
