# Maintenance check: did a person keep a canvas current when nothing forced them to?

A reading of the canvas store itself, answering the question `product-spec.md:105` makes
step 1's whole point and `product-spec.md:124` states the risk of — *"A stale canvas
injected into every prompt is worse than no canvas, because it misleads with authority"* —
and then reporting, for each of the three judgement calls `docs/canvas-in-prompts.md` wrote down
in the ledger-orchestrator repository, whether the condition it named as reversing it has fired.

It is a third document beside [`./VERDICT.md`](./VERDICT.md) and
[`./off-corpus-check.md`](./off-corpus-check.md) and amends neither. Those two grade
`--why` reasons. This one does not grade a single reason: it counts writes, reads
timestamps, and asks who made them.

**Written for Basecamp todo
[10334523272](https://app.basecamp.com/3934852/buckets/48039419/todos/10334523272)**,
*Read what a person and the steps did with a canvas they could edit, and write the tasks
that follow*, on 2026-09-24.

---

## 0. The store this reads, named exactly

- **Path:** `/Users/lfigea/.openclaw/workspace/state/canvas` — one git repository holding
  every row's file, which is what `$OPENCLAW_WORKSPACE/state/canvas` resolves to on the
  machine that runs the ledger.
- **Head at the time of reading:** `8f773f2ce113a2aec0315b49df9f860562971d53`, **99
  commits**.
- **First commit:** `4540a32e2e385a1bcc187a7db570018f76643882`, the repository's own
  initial commit, **2026-09-24 12:51:03 +0200**. **Last:** 2026-09-24 18:08:08 +0200.
- **Window:** five hours and seventeen minutes. That is the whole of it, and §5.1 explains
  why it is not the ledger's window.

Eleven files: **eight canvases belonging to ledger rows**, two sample canvases
(`skill-validation-20260924`, `skill-validation-b-20260924`) made while validating the
Canvas skill, and one artefact this review created and did not remove (§5.4).

**This review is in its own corpus and says where.** Of the 99 commits, 94 predate it.
Three are its own ledger row's birth commits (`bc-10334523272-what-a-person-and-the-steps-did`,
author `task-ledger | open`) and two are the probe in §5.4 (author `lfigea | by-hand`).
The head pinned above **is** that probe's second commit. Nothing in §§1–4 is counted from
any of the five.

### The commands

```bash
STORE=/Users/lfigea/.openclaw/workspace/state/canvas
git -C "$STORE" rev-parse HEAD
git -C "$STORE" rev-list --count HEAD
git -C "$STORE" log --format='%(trailers:key=Canvas-Author,valueonly)' | grep -v '^$' \
  | sort | uniq -c | sort -rn
for f in "$STORE"/*.xml; do
  printf '%s %s\n' "$(git -C "$STORE" log --format=%H -- "$(basename "$f")" | wc -l)" "$(basename "$f")"
done
```

### How long a canvas was open to a tab edit

A canvas can take a write from the page only between its birth and its freeze, and only
while a server is up. Per canvas, intersected with the 14:46:37–18:08:08 window in which
pid 33867 has been running — born / frozen / hours open:

| canvas | born | frozen | open |
|---|---|---|--:|
| `duplicate-invoice-criterion-output-schema` | 14:45:08 | never | 3.36 h |
| `bc-10336603973-…` | 15:34:27 | 17:45:12 | 2.18 h |
| `bc-10336256184` | 17:02:52 | never | 1.09 h |
| `bc-10327745654-…` | 14:04:01 | 15:16:47 | 0.50 h |
| `bc-10336754422-canvas-operating-skill` | 14:57:24 | 15:13:41 | 0.27 h |
| `bc-10334522382-…` | 13:41:58 | 14:52:13 | 0.09 h |
| `bc-10334520493-verify-the-drift-check-delivery` | 12:51:03 | 13:34:12 | 0.00 h |
| | | **total** | **7.49 h** |

Freeze times are `git log --grep='^Canvas-Freeze: <ledger-id>'`; the server's start is
`ps -o lstart= -p 33867`.

### The census

| `Canvas-Author` | commits | what it is |
|---|--:|---|
| `leo \| via claude` | 36 | a person, through the CLI — §1 |
| `task-ledger \| open` | 21 | `create`'s three birth commits, ×7 rows |
| `claude-opus-5 \| canvas-follow-through` | 15 | an agent session, not a step and not a person |
| step ids (13 distinct trailers, 4 rows) | 21 | orchestrator steps writing from their prompts |
| `task-ledger \| close` | 4 | the automatic freeze at a terminal row |
| `lfigea \| by-hand` | 2 | this review's probe — §5.4 |

Per canvas: `bc-10327745654-…` 18, `duplicate-invoice-criterion-output-schema` 36,
`bc-10336754422-canvas-operating-skill` 7, `bc-10334520493-verify-the-drift-check-delivery`
6, `bc-10336603973-…` 6, `bc-10334522382-…` 4, `bc-10336256184` 3, and this review's own
row 3; plus `skill-validation-b-20260924` 6, `skill-validation-20260924` 3 and
`probe-empty-problem-20260924` 2.

---

## 1. The ruling on the question the design was built to answer

**A person wrote a canvas once, in three minutes and fifty seconds, and never went back to
it — while the row it belonged to ran for another two hours and thirty-nine minutes, was
blocked twice, resumed twice and closed. And nobody has edited a canvas from the tab at
all: the page that makes a person able to write to one without a terminal has zero writes
in this store.**

Both halves of that need their evidence, and the second half is the one that decides how
much the first is worth.

### 1.1 Nobody has used the tab

`bin/watch-runs-web` authors an edit made from the page as `$USER` when the form does not
say otherwise — `DEFAULT_AUTHOR = os.environ.get("USER") or ""`, overridable per server
with `--author` and per edit in the form. The server running on this machine is pid 33867,
started **2026-09-24 14:46:37**, `bin/watch-runs-web` with no `--author`. So a tab edit on
this machine carries the trailer `lfigea`.

**No commit in this store carries it.** The two `lfigea | by-hand` commits in the census
are a different string: that is `store.default_author`, what the tool fills in for a CLI
caller that passed no `--author` at all, and both are this review's probe (§5.4).

### 1.2 The one canvas a person wrote

All 36 `leo | via claude` commits are on one file,
`duplicate-invoice-criterion-output-schema.xml`, and they span **14:45:08 to 14:48:58** —
three minutes fifty seconds:

| time | commits |
|---|--:|
| 14:45:08 | 3 |
| 14:46:00–14:46:02 | 17 |
| 14:48:19–14:48:20 | 11 |
| 14:48:45 | 3 |
| 14:48:58 | 2 |

Two things in that table rule out the tab as the surface these came through, and neither is
an inference about intent:

- **Twenty of the 36 land before the server was running** — 14:45:08 and 14:46:00–14:46:02
  are all earlier than the 14:46:37 start of pid 33867.
- **Seventeen land inside three seconds.** The page's editor writes one node per
  submission, which is the whole shape of `/api/canvas-edit`; seventeen form submissions in
  three seconds is not a person at a page.

The reasons agree: seventeen of the 36 commit subjects are the identical string *"describe
the problem and solution space for this row"* and eleven more are the identical string
*"the canvas is a drawing surface, not a document; replace the prose with a diagram and a
table"*. That is one writer issuing batches, not a person composing a reason per node —
and it is, incidentally, the failure `VERDICT.md` §5.1 exists to stop, arriving here
through a door that review never looked at.

### 1.3 What happened to that canvas afterwards

The row's own record, from `/Users/lfigea/.openclaw/workspace/state/ledger/duplicate-invoice-criterion-output-schema.json`:

| time | event |
|---|---|
| 14:27:08 | `transition:framed` — opened |
| 14:27:09 | `canvas:failed` — `exit 2: Canvas-Exit: 2 — the tool or its environment is wrong; do not touch the canvas` |
| 14:34:35 | `transition:executing` — started |
| **14:45:08 – 14:48:58** | **the 36 writes above** |
| 15:34:43 | `transition:blocked` — the plan did not finish, `…-baseline-check` said FAIL |
| 15:54:53 | `transition:executing` — resumed |
| 16:15:11 | `transition:blocked` — the same gate, again |
| 16:48:16 | `transition:executing` — resumed |
| 17:28:00 | `transition:done` — validated |
| 17:28:10 | `canvas:failed` — `freeze: exit 2: …` |

So the canvas was born by hand *because* the automatic `create` had failed a quarter of an
hour earlier, was filled in during the run, and then recorded **none** of the two failures,
two recoveries and one close that followed it. Forty-five minutes later a step was arguing
with a gate the canvas does not know exists.

### 1.4 What this supports, and what it does not

**Supported.** In this window, on the one canvas a person touched at all, the person wrote
once and did not come back. There is no instance in this store of a person keeping a canvas
current, and no instance of a person writing to one from the tab.

**Not supported, and this is most of it.** *One* canvas, *one* person, *one* afternoon
is not a measurement of a habit. In particular:

- **The denominator is tiny, and smaller than it first looks.** The tab's write path
  merged at 2026-09-24 09:47 (ledger-orchestrator #107) and a server carrying it has been
  up since 14:46:37 — but a canvas is only open to a tab edit while it is both born and
  unfrozen, and five of the seven ledger-row canvases here were frozen by their rows
  closing. Summed over the seven, the store offers **7.5 canvas-hours** in which a person
  at that page could have written anything at all: 3.4 of them on one canvas, 2.2 on a
  second, and `bc-10334520493-verify-the-drift-check-delivery` frozen at 13:34 — before
  the server existed — contributing none. Zero tab writes across 7.5 canvas-hours is a
  real fact about those hours and a weak one about habits. Nobody was asked to write, and
  no canvas here belonged to work a person was doing by hand.
- **The one person-written canvas is the one whose row could not make its own.** Its
  automatic `create` had failed, so a person creating it at all was already an
  intervention. A canvas somebody had to build by hand before they could use it is the
  worst possible sample for "does somebody maintain one when nothing forces them to".
- **Three minutes and fifty seconds is a sitting, not a period of neglect.** What the
  store shows is a burst followed by silence. Whether that silence is *staleness* depends
  on whether anything in those 2h39m changed the shared understanding, and this review
  did not read the run's 22 output files to find out. It reports the shape and stops.

So: **a first data point, consistent with the worry `product-spec.md:124` records and far
too small to confirm it.** The experiment the design actually wants — a person with a
canvas of their own, a tab in front of them, and nothing telling them to write — has not
been run, and §6 says what running it would take.

---

## 2. Reversal condition 1 — the over-budget notice. **Did not fire, and could not have.**

`canvas-in-prompts.md` §1, in its own words:

> if over-budget canvases are observed being carried run after run with no step ever
> resolving one, then the notice is not working as an instruction and something with teeth
> — a step that may do nothing but resolve, or a `framed`-side gate — has to replace it.

The budget is `BUDGET_CHARS = 20000` in `orchestrator/canvas.py`, measured on the document
as `bin/canvas read` prints it — the `Canvas-Base:` line plus the XML.

**Largest canvas in this store, now:** `bc-10327745654-the-ledger-orchestrator-repository-git-g`,
**11,549 characters — 57.7% of the budget**. Every other one is between 392 and 5,875.

**Largest any canvas has ever been, at any commit:** the same document, 11,495 bytes of XML
at commit `2e704d2`. Measured over every commit of every file:

```bash
for f in "$STORE"/*.xml; do
  b=$(basename "$f")
  peak=$(for sha in $(git -C "$STORE" log --format=%H -- "$b"); do
           git -C "$STORE" cat-file -s "$(git -C "$STORE" rev-parse "$sha:$b")"
         done | sort -rn | head -1)
  printf '%7s  %s\n' "$peak" "$b"
done | sort -rn
```

That is bytes of XML; `read` adds the 54-character `Canvas-Base:` header line on top, which
is where 11,495 becomes 11,549.

Nothing in this store has ever been over budget, so nothing could have been carried over
budget run after run. The condition is **untested**, not refuted, and the judgement call
stands unexamined. `canvas-in-prompts.md` §1 measured its own budget against a canvas —
"canvas A", 28,262 characters, 141% — which is **not in this store**; §5.1 explains where
it went.

---

## 3. Reversal condition 2 — `is_untouched()`'s narrowing. **Fired.**

`canvas-in-prompts.md` §2, on the deliberate narrowing of
`orchestrator/canvas.py::is_untouched()` — the canvas exists, and *every* `Canvas-Author`
in its log is `task-ledger | open`:

> What it misses: a canvas written in a row's first run and never again. What would reverse
> it: seeing that case happen for real.

**That case happened, on `duplicate-invoice-criterion-output-schema`, and in a harder form
than the sentence anticipated.** `is_untouched()` returns `False` for it. The row was never
flagged, and could not have been — not because a run wrote to it, but because **no author
in its log is `task-ledger | open` at all**. The birth commits that would carry that string
were never made: `create` failed at 14:27:09, and the person who made the canvas by hand at
14:45 authored it as themselves. The predicate keys on a string that a *failed* `create`
guarantees will never appear, so the rows likeliest to have an unmaintained canvas are
exactly the rows the predicate cannot see.

Present values, for the record — `orchestrator.canvas.is_untouched(<ledger-id>)`:

| canvas | `is_untouched` | is that right? |
|---|---|---|
| `bc-10336256184` | `True` | yes — one linked run, nothing has written |
| `bc-10334523272-what-a-person-and-the-steps-did` | `True` | yes — this review's own row |
| `bc-10327745654-…` | `False` | yes — fourteen step writes |
| `bc-10334520493-verify-the-drift-check-delivery` | `False` | yes — three step writes |
| `bc-10334522382-…` | `False` | yes — one step write |
| `bc-10336603973-…` | `False` | yes — three step writes |
| `bc-10336754422-canvas-operating-skill` | `False` | yes — four agent writes |
| `duplicate-invoice-criterion-output-schema` | `False` | **no** — nothing that ran ever wrote to it |

One row, so this reverses nothing on its own; what it does is exactly what the sentence
asked for — it is the case, seen for real, and the ruling said that was the trigger for
looking again. Note what is *not* claimed: `canvas-in-prompts.md` §2 also ruled that a
finding of staleness is not a licence to escalate, and nothing here argues with that. The
question this opens is what `is_untouched` should key on, not what the sweep should do
about the answer.

---

## 4. Reversal condition 3 — `N = 10` edits in the prompt. **Did not fire.**

`canvas-in-prompts.md` §4:

> Judgement call; what would reverse it: if steps are seen re-deciding things a canvas
> settled 11 edits ago.

Only one canvas here has more than ten edits written by steps:
`bc-10327745654-the-ledger-orchestrator-repository-git-g`, 18 commits, of which 15 are
caller-written. It is also the only canvas in this store where steps re-decided anything at
all — five `replace`s. Numbering the file's own log:

| # | commit | edit | the node's previous edit | distance |
|--:|---|---|--:|--:|
| 11 | `7b4d797` | `replace wmss` | #7 | 4 |
| 12 | `a1c0515` | `replace asrt` | #9 | 3 |
| 13 | `ccffd38` | `replace mtmt` | #10 | 3 |
| 14 | `3a31ec5` | `replace mtmt` | #13 | 1 |
| 17 | `c884758` | `replace asrt` | #12 | 5 |

**Maximum distance five.** In every case the node's current state was inside the last-ten
window `EDITS_IN_PROMPT` puts in the prompt, so no step re-decided anything it had not been
shown. The other canvas with more than ten edits,
`duplicate-invoice-criterion-output-schema`, was written entirely by one writer in one
sitting and read by no step at all, so it cannot speak to this.

This is weak evidence for `N = 10` rather than evidence against it: five re-decisions on
one row, all at half the window or less. What it rules out is the specific failure the
number was chosen against, in this window.

---

## 5. Four things the reading found that nobody asked for

These are not answers to §§1–4. They are what a reading of the store turned up, and each
is recorded because the store is the only place it is visible.

### 5.1 The store's window is not the ledger's, and the reason is a deployment

`bin/task-ledger open` has created a canvas since `137859c`, merged to ledger-orchestrator
`main` on **2026-09-23 14:47**. This store's first commit is **2026-09-24 12:51:03**, and
it is the repository's *initial* commit — nothing was deleted; there was nothing here
before.

The gap is the deployment. The live checkout at `/Users/lfigea/Projects/ledger-orchestrator`
is what runs on this machine, and its own reflog shows it sitting on feature branches —
`canvas-why-brief`, then `canvas-why/bc-10334520493-evidence-clause`, then
`fix/retry-and-check-recovery` — from **2026-09-23 02:15** until **2026-09-24 11:54**.
Those branches were cut before the merge:

```bash
cd /Users/lfigea/Projects/ledger-orchestrator
git show 4b9f938:bin/task-ledger | grep -c _born_a_canvas   # 0   (canvas-why-brief)
git show 74e3c1a:bin/task-ledger | grep -c _born_a_canvas   # 0
git show e98145e:bin/task-ledger | grep -c _born_a_canvas   # 0
git show 0e9b211:bin/task-ledger | grep -c _born_a_canvas   # 4   (back on main, 11:54)
```

**Twenty-six ledger rows were opened in that window. Not one has a canvas, and not one has
a `canvas:failed` event** — a `bin/task-ledger` that does not know canvases exist cannot
report that a canvas is missing, so the degradation the design took care to make loud was
silent for twenty-one hours. Among the twenty-six are
`bc-10334519573-…` (the tab's own write path),
`bc-10334515971-…` (the tab itself) and `bc-10331851610-…` (the row's rendered-canvas
projection): the three rows that built the surfaces this document exists to measure all ran
without one.

It is also where "canvas A" went. `canvas-in-prompts.md` §1 derived the 20,000-character
budget from a 28,262-character canvas for todo 10329619223 and a second one of 1,899
characters. Neither is here, and neither is anywhere on this machine — a `find` for
`state/canvas` directories returns exactly one path. §2's "nothing has ever been over
budget" is therefore true of *this* store and says nothing about the one the budget was
measured on.

### 5.2 One commit carries two rows' edits, and `history` cannot see one of them

Exactly one of the 99 commits changes more than one file:

```
59f6946c07e1a26202ac34fa63ef9bcef793301f   2026-09-24 15:09:57
  subject:  insert ttz6: deciding to spend a test file on a Markdown document …
  trailers: Canvas-Node: ttz6 / Canvas-Author: claude-opus-5 | canvas-follow-through
  files:    bc-10336754422-canvas-operating-skill.xml            (+1  — inserts ttz6)
            bc-10327745654-the-ledger-orchestrator-…-git-g.xml   (±1 — ihfu v="1" → v="2")
```

The subject, the `Canvas-Node:` trailer and the reason are all about `ttz6` in the skill
row's canvas. The change to `ihfu` — a full rewrite of a node in a *different* row's canvas,
correcting which workflow run the merge read — rides along unnamed. And so:

```bash
bin/canvas history bc-10327745654-the-ledger-orchestrator-repository-git-g ihfu
# one edit: the insert at 6628e1c. The replace is not in the output.
```

`ihfu`'s text changed and the canvas's own history cannot say who changed it, why, or when
— which is the one thing `--why` exists to make impossible.

The mechanism is in `canvas/store.py`'s write path and is not a race in the document: the
edit is staged path-scoped, `git add -f -- <path>`, and then committed with **no pathspec**,
so anything else already in the index is committed with it. The store is one git repository
for every row — `orchestrator/canvas.py::create` says so in its own docstring — and two
writers were active at 15:09:5x. `--base` could not have caught it: staleness is scoped to
the writer's own file, by design, and this is the other file.

### 5.3 Every `canvas:failed` event records the same eight words

Eight rows opened today carry an event whose entire detail is:

```
exit 2: Canvas-Exit: 2 — the tool or its environment is wrong; do not touch the canvas
```

Byte-identical, on all eight. `orchestrator/canvas.py::create` builds it as
`"exit %d: %s" % (returncode, detail[-1])` where `detail` is the tool's stderr split into
lines — and the tool's *last* stderr line is always the `Canvas-Exit:` line, the generic
meaning of the code. The two lines above it, `Canvas-About:` and `Canvas-Next:`, are what
name the actual cause and what to do, and they are the ones dropped.

Reproduced, read-only, in the ledger repository:

```bash
env -u OPENCLAW_WORKSPACE python3 -c \
  "import sys;sys.path.insert(0,'.');from orchestrator import canvas;print(canvas.create('probe','p','e'))"
# (False, 'exit 2: Canvas-Exit: 2 — the tool or its environment is wrong; do not touch the canvas')
```

That is one of at least five conditions that produce exit 2, and it produces the recorded
string exactly — as would each of the others. So the record cannot distinguish "this
machine has no `OPENCLAW_WORKSPACE`" from "this machine has no `xmllint`", and the row that
is the only thing able to say *"this one has no document"* says it without saying why.
`bin/task-ledger` defaults `OPENCLAW_WORKSPACE` and `bin/canvas` deliberately does not,
which is the asymmetry that makes a row land correctly while its canvas cannot — but
nothing in the record establishes that this is what happened on those eight.

### 5.4 `bin/canvas create` is not atomic, and this review proved it in the wrong store

In an isolated store (`OPENCLAW_WORKSPACE` at a fresh temporary directory):

```bash
bin/canvas create probe-empty-problem --problem "" --expected-value "x"
# canvas: refusing to write a commit naming jg74 that also changes 1 other node(s) (grux):
#         one edit is one node
# Canvas-Exit: 1
# exit status 1
git -C "$TMP/state/canvas" log --oneline
# bd6782c insert grux: the problem the ledger row states     <- committed
# e1ddcfa create probe-empty-problem: born at open, root only <- committed
```

`create` makes three commits. With an empty `--problem` the first two land, the third is
refused by the tool's own one-edit-is-one-node guard, and the caller is left with a canvas
that **exists** and has no expected-value node. There is no recovery: `create` refuses to
overwrite an existing canvas. The mirror case, `--expected-value ""`, exits 0 and makes all
three. `bin/task-ledger`'s `_born_a_canvas` passes `entry.get("problem") or ""` into the
same call, so a row opened with an empty problem reaches this.

**Declared, because it is in the corpus:** the first probe of this was run against the real
store before the isolated one, and it left `probe-empty-problem-20260924.xml` there with
two commits, `3aea0a2` and `8f773f2` — the second of which is the head this document pins
in §0. It has not been removed. Rewriting an append-only store to hide a reviewer's own
mistake is worse than the mistake, and a later reader re-running §0's commands will see 99
commits and eleven files and should: that is what was there.

---

## 6. What this check did not cover

- **The experiment the question deserves was not run.** A person given a canvas of their
  own, over days rather than hours, with the tab in front of them and nothing instructing
  them to write, is what would answer §1. This read a store in which that had not happened.
- **One day, one machine, one store.** Five hours and seventeen minutes, eight ledger-row
  canvases, 94 commits not this review's own. Every count here is small enough that one
  more row could move it.
- **No reason was graded.** `VERDICT.md` and `off-corpus-check.md` own that, and this
  document deliberately does not re-open it — §1.2 notes that 28 of the 36 person-written
  reasons are two repeated strings, and stops there rather than scoring them.
- **The run's own outputs were not read.** §1.4 says the canvas recorded none of the two
  blocks and two recoveries; it does not say whether any of them *changed the shared
  understanding*, which is the only thing that would make the silence staleness rather than
  correct restraint. Twenty-two output files exist on that row and this review opened none
  of them.
- **`canvas A` is gone and its measurements cannot be rechecked.** §2's budget answer is
  scoped to a store that never held it.
- **Only one of the three reversal conditions fired**, and the two that did not, did not
  because the store contains no instance of the shape they name — not because the shape was
  looked for and found absent under pressure.
- **This is again a reader at no distance.** As in both earlier documents: the bar in §1 is
  about somebody months later, and everything read here is hours old.

---

*Written 2026-09-24 for Basecamp todo
[10334523272](https://app.basecamp.com/3934852/buckets/48039419/todos/10334523272), ledger
row `bc-10334523272-what-a-person-and-the-steps-did`. Store
`/Users/lfigea/.openclaw/workspace/state/canvas` at
`8f773f2ce113a2aec0315b49df9f860562971d53`, 99 commits; canvas checkout at `c54eaa1`,
branch `docs/bc-10334523272-maintenance-check`; ledger-orchestrator checkout at `0b35ce6`.*

---

**A later attempt to run the experiment §6 names found two things in front of
it, and wrote them down beside this document:**
[`./experiment-preconditions.md`](./experiment-preconditions.md). It reports
that the denominator §0 publishes can no longer be re-derived — `ps -o lstart= -p
33867` prints nothing now — and that no canvas in this store has ever stayed
writable long enough for the experiment to be run on it.
