# Off-corpus check: do the `--why` reasons hold up on a task that is not about Canvas?

A second, later reading of `--why` reasons, answering one named limit of
[`./VERDICT.md`](./VERDICT.md). It does not amend that document: `VERDICT.md` is the record of
the review of the first fifty reasons, and this is a separate and much smaller corpus read
afterwards, against the same bar.

**The limitation this answers**, `VERDICT.md` §6, second bullet, in its own words:

> **That task was about `bin/canvas` itself.** The canvas documents a decision inside the
> Canvas tool, written by writers who had just read its specs. Reasons on a task with no such
> self-referential pull may be poorer, and this corpus cannot say.

**Where this corpus came from.** Run
`bc-10330567406-deliver-the-first-priority-canvas-todo-p` (Basecamp todo
[10330567406](https://app.basecamp.com/3934852/buckets/48039419/todos/10330567406), *Put the
canvas in step prompts and take the Basecamp task out*) wired `bin/task-ledger open` to mint a
canvas and put that canvas into every step prompt, then ran a real plan to show it working.
That demonstration is `demonstration.md` in the run directory; its scratch workspace holds the
store read here. Ledger id **`json-flatten-roundtrip-limits`**; the task is an encoding
question about `simonw/json-flatten`, a third party's library, and `demonstration.md` §2
records that the three step prompts as authored contain the word *canvas* zero times, `--why`
zero times, and that nothing in them asked for any canvas edit. That is what makes it the
first canvas with no self-referential pull.

**Corpus HEAD:** `de136d38d303b70a77771a167260c9e70a48d8da` (7 commits), in
`<run>/scratch-ws/state/canvas`. Every reason below was read from
`git -C <store> log` and `bin/canvas history json-flatten-roundtrip-limits <node>` by this
step, not copied from `demonstration.md`.

---

## 1. The ruling

**Four caller-written reasons, four meet the bar. That is a first data point consistent with
`VERDICT.md`'s ruling holding off its own corpus — reasons on a task with no self-referential
pull were not poorer — but four reasons from one row cannot confirm or overturn a ruling made
on forty-seven, and this document does not claim that it does.**

Two qualifications belong in the ruling itself rather than in a footnote, because without them
the four-for-four reads as stronger evidence than it is:

- **The failing edit never arose.** All six caller-written failures in `VERDICT.md` §2.3 are
  the placement of a node that holds nothing — four empty `<row>`s and two header `<cell>`s of
  an options table. This canvas contains no table, no empty element and no scaffolding edit of
  any kind: all four edits place or correct a `<text>` node carrying a finding. So this corpus
  says nothing about whether that failure recurs away from `bin/canvas`; it only says that
  where the edit carried a decision, the reason carried one too — which is the same
  correlation §2.3 reports (*"41 of 41"*), now seen once more on a different subject.
- **These writers were handed the fix.** `VERDICT.md` §5.1 says the *"Never point at another
  reason"* rule belongs in the prompt a `--why` writer is given. By the time this run happened
  that rule was in `guidelines/canvas-why.md`, and the canvas block in each step prompt names
  that file by absolute path; `demonstration.md` §2 counts three tool calls, one per step,
  reading it. The corpus `VERDICT.md` graded was written without that rule — it is where the
  rule came from. So this is not a clean replication of the §6 condition: it measures reasons
  on a non-self-referential task **with §5.1 in hand**, and cannot separate the subject from
  the instruction.

---

## 2. The corpus, and what is excluded

Seven commits. Three are `create`'s own string literals, written by `cmd_open` when the row
was opened and alterable by no caller and no prompt — `canvas/store.py` holds them. `VERDICT.md`
§2.1 excludes its own three on that ground and this excludes these three on the same one:

- `f114ef8` — `create -` — author `task-ledger | open` — *"born at open, root only"*
- `73efcbb` — `insert ua3q` — author `task-ledger | open` — *"the problem the ledger row states"*
- `4e962f3` — `insert sd2q` — author `task-ledger | open` — *"the expected value the ledger row states"*

That leaves **four caller-written reasons**, three `insert` and one `replace`, across three
nodes and three step authors. The `Canvas-Author` trailer on each is the step id, which is what
the orchestrator passes; no reason in this corpus carries the `<user> | by-hand` string that
`VERDICT.md` §3 had to spend a section disarming.

- Entry 1 — `8d719d3` — `insert r2rb` — author `roundtrip-audit` — 614 characters
- Entry 2 — `bfc3cbe` — `insert bmxf` — author `roundtrip-fix` — 875 characters
- Entry 3 — `a0b4efa` — `insert d92y` — author `roundtrip-check` — 1041 characters
- Entry 4 — `de136d3` — `replace d92y` — author `roundtrip-check` — 680 characters

Two verbs, as in the graded fifty: no `remove` and no `move` here either, so the gap
`VERDICT.md` §6 names in its fifth bullet is not closed by this corpus.

---

## 3. The bar applied

The same bar, not a new one. `VERDICT.md` states it in its header, from `product-spec.md:42`:

> could a reader, months later, reading only this reason, tell what the node was for and decide
> whether to **honour** it or **explicitly retire** it.

Reconstructed from how §2.2 and §2.3 actually applied it, three operational readings were used
here, all of them visible in that document rather than invented by this one:

1. **A reason that only restates the diff fails.** §2.3's `restates-the-diff` label covers
   *"option A's row: no, it may not."* — true, visible in the diff, and carrying no judgment.
2. **A pointer at another reason fails.** §2.4: *"as above"* is what a stranger reading
   `canvas history` cannot resolve, because `history` prints one node's edits and never the
   node the pointer meant.
3. **Borderline cases take the harsher label** (§2.1), and length is not the test (§5.3): the
   clean 151/114-character split in the fifty is called a symptom there and explicitly must not
   be made into a rule. No reason below is graded on its length.

The convention named in `engineering-spec.md:270-272` and repeated in
`guidelines/canvas-why.md` — a reason asserting a fact about the world should name its
evidence — is treated as §2.2 treats it: a thing worth reporting when present, not a pass/fail
clause of its own.

---

## 4. The grades — every caller-written reason, quoted in full

### Entry 1 — `8d719d3` — `insert r2rb` — 614 chars — **MEETS**

Author trailer `roundtrip-audit`.

> Records what the audit settled, which sd2q asks for and ua3q says nobody had written down:
> the six failing classes and the defect-or-limit decision on each, so the step that fixes or
> documents them reads the disposition here instead of re-deriving it. Evidence is
> json_flatten.py at 78c2835 exercised directly - the rsplit crash at json_flatten.py:89, the
> root list-ification at :128-:130, the empty-key unwrap at :43 and :130 - written up with
> reproducing documents in .orchestrator-artifacts/roundtrip-findings.md. Retire this node if
> a later audit finds a seventh class or overturns one of the six dispositions.

It says what the node is for in terms of the two nodes `open` minted — it records what
`sd2q` asks for and `ua3q` says nobody had written down — names its evidence as a commit,
three `json_flatten.py` line citations and a report file, and states its own retirement
trigger, so a reader months later can honour it or retire it without opening the diff.

### Entry 2 — `bfc3cbe` — `insert bmxf` — 875 chars — **MEETS**

Author trailer `roundtrip-fix`.

> r2rb settles the disposition of each failing class but stops at 'defect or limit'; this step
> had to choose which single defect to land and where the documentation goes, and neither is
> recoverable from r2rb. This node holds that choice and the criterion behind it - flatten's
> own output failing to read back, which r2rb does not rank on and which separates 2b/4 from
> 3b/3c/5 - plus the README placement, the tested escaping recipe callers get instead of the
> unfixed classes, and one correction to r2rb's bracket rule ([n]-prefixed, not exactly [n]).
> Evidence: commit 60db66c on branch roundtrip-limits in this clone, json_flatten.py:89, the
> three added cases in test_json_flatten.py that fail before it and pass after, and README.md
> section 'Is my document safe?'. Retire it if the recipe moves into the library or a second
> defect is fixed, neither of which would retire r2rb.

It is the §5.1 clause working: it names the sibling node `r2rb` by id and says exactly what
this node holds that `r2rb` does not — the choice of which single defect to land and the
criterion behind it — names its evidence, and gives a retirement trigger that would retire
this node and not `r2rb`.

### Entry 3 — `a0b4efa` — `insert d92y` — 1041 chars — **MEETS**

Author trailer `roundtrip-check`.

> r2rb says 'Six classes fail' and states class 4 as surviving whenever '' is not alone at the
> root; both are contradicted by running the branch, and bmxf's README - which states four key
> rules - inherits the second. This node holds what only running it could settle: the seventh
> class (line-break keys, json_flatten.py:74, _types_re's '.' not matching a newline) and the
> corrected class-4 rule, neither derivable from r2rb or bmxf. r2rb's own retirement trigger
> is 'a later audit finds a seventh class', but retiring it would drop five dispositions still
> in force and still relied on by bmxf, so this amends r2rb rather than replacing it.
> Evidence: commit e85be57 on branch roundtrip-limits correcting README.md, json_flatten.py:74
> and :43, and .orchestrator-artifacts/roundtrip-check.md, which records the 33 reproducing
> documents re-run and the 24158-document fuzz that the corrected rules survive with zero
> failures. Retire this node if the re.DOTALL fix lands, which would also retire bmxf's
> criterion as unfinished business but not r2rb.

It names both prior nodes by id, says what only running the branch could settle, argues from
`r2rb`'s own stated retirement trigger why it amends rather than replaces it — a judgment no
diff contains — names its evidence, and gives its own retirement trigger.

### Entry 4 — `de136d3` — `replace d92y` — 680 chars — **MEETS**

Author trailer `roundtrip-check`.

> Corrects one number this step itself wrote into d92y at v=1: it said 29 of the 33
> reproducing documents fail as the audit described, which does not add up against the 3 that
> now round-trip. The true split is 30 and 3; the miscount came from my harness reading the
> exception type out of the wrong field for {1: 'x'}, which does fail exactly as
> roundtrip-findings.md states (TypeError: can only concatenate str (not "int") to str, raised
> inside flatten). Nothing else in the node changes - the seventh class, the class-4
> correction and the fuzz result stand as written. Evidence:
> .orchestrator-artifacts/roundtrip-check.md, whose per-class list enumerates all 33 and now
> reports 30.

It is the shape §2.2 found strongest in a `replace`: which sentence was wrong, the true
figure, the mechanism that produced the error, what in the node is unchanged, and the file
that settles it — none of which the diff between v=1 and v=2 supplies.

---

## 5. The counts, stated as §2.1 states them

One label per reason, borderline cases taking the harsher label:

- `informative` — **4** of 4
- `restates-the-diff` — **0** of 4
- `empty` — **0** of 4

Seven commits, three of them `create`'s literals, leaving **4 caller-written reasons, 4 of
which meet the bar and 0 of which do not** — 100% of four.

Per author arm, for completeness and with nothing inferred from it: `roundtrip-audit` 1 for 1,
`roundtrip-fix` 1 for 1, `roundtrip-check` 2 for 2. All three steps ran on the same worker and
the same model (`claude/claude-opus-5[1m]`, `demonstration.md` §10), so there is one arm here
in every sense that matters.

Length, measured over the four: **614, 875, 1,041 and 680** characters (mean 803, median 778).
The graded fifty in `./corpus-reasons.md` run 21–975 (median 234.5); over all 55 entries the
median is 263 and the maximum is still 975, which is entry 45. So one of these four is longer
than anything in the corpus and three are not — `demonstration.md` §10 says *"every one of
them longer than the 975-character maximum"*, which is true only of the 1,041; 614, 875 and 680
are below it. (The same sentence says *"the 266-character median of the 54 reasons
`VERDICT.md` graded"*; `./corpus-reasons.md` holds 55 entries, `VERDICT.md` graded 50 of them,
and the median over all 55 is 263.) The corrections are recorded here because these are the
numbers, and none of this document's grading rests on them: §5.3 of `VERDICT.md` rules length
out as a test and this review kept to that.

---

## 6. The ruling on `VERDICT.md` §6's second bullet

**What the evidence supports.** On a task with no self-referential pull — a third party's
encoding library, with prompts that never mentioned canvases — four reasons were written and
all four meet the same bar the fifty were held to. Each names the node's purpose in terms of
what the other nodes do not hold, each names its evidence by commit, file and line or report
file, and three of the four state a retirement trigger unprompted. The worry §6 records —
*"Reasons on a task with no such self-referential pull may be poorer"* — is not what these
four show. Nothing here degrades.

**What it does not support.** It does not confirm the verdict off-corpus. Four is not
forty-seven; one row is not a second task in any statistical sense; and the two qualifications
in §1 both cut the same way — the failing edit-kind never arose, and the §5.1 fix was already
in the writers' hands. A corpus that contains zero instances of the only failing shape the
first review found cannot report on that shape. **This is a first data point, consistent with
the ruling and too small to confirm or overturn it, and it is worth recording as exactly that.**

**Where the failures landed, which is the part a small sample can speak to.** There were no
failures, so nothing lands on §2.3's kind of edit or on a different one. The informative half
of §2.3's finding does replicate: *"every edit in the fifty that placed an option, a cost, an
argument, a correction, a piece of evidence or an outcome got a reason that meets the bar"* —
here every edit was of that kind and every reason met the bar, 4 of 4. The claim that would
have damaged the verdict is the converse one — a substantive edit drawing a thin reason — and
it did not happen once here.

**What would have changed this document's mind**, stated so it is falsifiable, in the spirit of
`VERDICT.md` §5.4: any one of the four reasons restating its diff; any reason pointing at
another node instead of saying the thing; the spec's worked tautology (*"updated the node to
reflect the change"*) appearing once; or the `replace` — the verb carrying the most semantic
load — failing. None happened.

---

## 7. What this check did not cover

- **Four reasons, one row, one model.** Everything in §1's qualifications applies here too.
- **No table, no empty node, no `remove`, no `move`.** The edit shapes that produced every
  failure in the first corpus, and the two verbs that corpus never exercised, are all absent
  from this one.
- **The §5.1 rule was in the prompt.** So subject and instruction cannot be separated. A run
  on a non-Canvas task *without* `guidelines/canvas-why.md` in the prompt is the experiment
  that would isolate the subject, and it was not run — and, now that the rule is wired into
  every step prompt, running it would mean deliberately removing the fix.
- **Nobody read these reasons months later.** The store is 26 minutes and 3 seconds long end
  to end, and the four graded reasons span 17 minutes of it. The bar is about a reader at
  distance and this review is, like the first, a reader at no distance grading text.
- **One grader, inside the run that produced the corpus.** This step graded reasons written by
  sibling steps of its own run. An independent grader remains the obvious next check, as
  `VERDICT.md` §6 already said of itself.
- **No code was read for correctness and none was changed.** No file outside
  `docs/why-verdict/` was touched, and `VERDICT.md` was not edited.

---

*Written 2026-09-23 by the `grade-why` step of run
`bc-10330567406-deliver-the-first-priority-canvas-todo-p`. Graded corpus HEAD
`de136d38d303b70a77771a167260c9e70a48d8da`, ledger id `json-flatten-roundtrip-limits`; Canvas
checkout at `f2ba7ad`, branch `docs/bc-10330567406-open-is-wired`.*
