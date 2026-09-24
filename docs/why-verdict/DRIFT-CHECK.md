# Drift check: does the evidence a `--why` names still resolve?

The companion measurement to [`./VERDICT.md`](./VERDICT.md), asking the question
that document names and does not ask. `VERDICT.md` read the first fifty reasons
for whether a reader could tell **what the node was for**. This one re-reads the
same fifty, plus the four in [`./off-corpus-check.md`](./off-corpus-check.md),
for whether the evidence those reasons **name** can still be followed today —
the canvas-versus-branch drift that `engineering-spec.md` §*Coherence* records
as the one risk the specification does not solve — *"Between the canvas and
reality"*, at `:280-290` on `main` today — and whose only mitigation is the
convention that a reason should name its evidence.

Measured and written 2026-09-24, against `main` at
`599d5ba1e7c84d1af958e84f1ab4370e2aa8748c`.

It does not amend `VERDICT.md`. It amends nothing: the ruling in §6 is a change
to the *instruction a `--why` writer is handed*, and it is written out here
verbatim so the step that carries it into `guidelines/canvas-why.md` and into
`README.md` has nothing to draft.

---

## 1. The ruling, in one place

**The evidence convention is not as far as this goes, and the strengthening is
prose.** `guidelines/canvas-why.md:37-44` should be replaced with the text in §6,
and `README.md`'s `--why` evidence subsection with the matching text there.

Three findings force it, and one holds it back to prose:

1. **Naming evidence works.** Of the 24 reasons that name evidence a reader can
   follow, **21 still resolve** — 87.5%. All twenty-four were followed one at a
   time, and §4 records every attempt, the passes included. Where a reason
   named a commit, a file, a grep-able identifier or a titled section,
   following it almost always landed where the reason said.
2. **The convention's own worked example is the one locator form that rotted.**
   The clause says to name "a PR, a verdict, **a file and line**". Both citations
   in this corpus that drifted are a file and a line — `canvas/store.py:582`,
   which is now `:640`, and `json_flatten.py:89`, where the code it means is at
   `:91`. Every citation that survived intact is a **name**:
   `_not_a_repository`, `os_next_action`,
   `_cannot_read`, `_OS_NEXT_ACTION`, `_types_re`, `README.md` §*Exit codes*,
   `engineering-spec.md` §*Lifecycle*. The clause recommends by name the form
   this corpus shows going stale, and says nothing about the form that held.
   §4.6 is the same finding outside the corpus and is the sharper one: **ten
   citations, in four ranges, of the single paragraph this task exists to serve
   — and today not one of them lands on it.**
3. **The largest failure is upstream of drift.** Of the 43 reasons that assert a
   fact about the world, **19 name nothing a reader could follow** — 44%. They
   are not wrong; they are unfalsifiable. The clause already asks these writers
   for evidence, so the 19 are non-compliance — but §3.3 shows the clause does
   not tell a writer that *"the ENOENT template"* is not a locator while
   `_OS_NEXT_ACTION[errno.ENOENT]` is, and those two sentences are five entries
   apart in one canvas under the same author trailer. That gap is in the
   wording.

And what holds it to prose: **no check, and no attribute.** §7 gives the
argument against each, on this evidence rather than on the specs' authority
alone. The short of it: the one drift a shape check could catch is not the drift
that happened, and all five `answered="true"` markers on this machine still hold
— the failure the corpus produced is in the reason's evidence, not in the
marker.

---

## 2. What this read, and where it got it

### 2.1 The reasons

**Fifty-four reasons, from two files in this repository**, both read at
`main` = `599d5ba1e7c84d1af958e84f1ab4370e2aa8748c`:

- **Entries 1 to 50 of [`./corpus-reasons.md`](./corpus-reasons.md)** — blob
  `7d2ba10e668838200a5560c7eb6b2a395f12e311`, md5
  `c6b3d04a19e57cdd5c9b3eb144f89ebf`, 449 lines. That file holds **55** entries
  and says so itself at its line 10 (*"Total entries: 55"*) and line 11 (*"The
  review must judge entries 1 to 50 … Entries 51 to 55 are present below for
  completeness and are **outside** the fifty the verdict rules on"*). **Entries
  51 to 55 are outside the fifty and are not read here.** One consequence is
  recorded rather than hidden: the node entry 54 inserts — `qrfs`, a `<link>` —
  still reads *"PR #8 … the parent change, still open"* in the corpus document,
  and #8 merged on 2026-09-22. That is a stale sentence in the **document**
  rather than in a reason, it is outside the fifty, and this finding does not
  rule on it.
- **The four caller-written reasons in
  [`./off-corpus-check.md`](./off-corpus-check.md)** — blob
  `9a0e80d77536795bb5ead54a7820c9a39650c408`, md5
  `d979d92556a080119a86321ab2fe5c64`, 278 lines. That file is on `main`: it
  arrived on commit `646ad31` and reached `main` on the merge commit
  `90ff1897a1e3f5bd712265cac489d11867352042` (PR #18, 2026-09-23 22:40:32 +0200).
  The Basecamp todo this finding answers was written before that merge and calls
  PR #18 unmerged; it is merged.

To extract exactly the set this finding read:

    sed -n '45,395p'  docs/why-verdict/corpus-reasons.md    # entries 1-50
    sed -n '112,190p' docs/why-verdict/off-corpus-check.md  # the four

### 2.2 The canvas stores read, each by absolute path and head sha

**Two stores were read for the reason texts themselves**, and neither is in this
repository:

- `/Users/lfigea/.openclaw/runs/bc-10326884789-deliver-the-first-priority-canvas-todo-r/corpus-store`
  — head `02de26b71893d1d33d1559cd0fd9bcfcaff84652`, 55 commits, holding one
  document, `bc-10329619223-errno-decides-the-repository-refusals.xml`. This is
  the store the fifty are the commits of: `corpus-reasons.md` cites it as
  `./corpus-store` at its lines 3, 10, 24 and 442, and **that path is not in
  this repository** — `git ls-tree -r main` lists only `VERDICT.md`,
  `corpus-reasons.md` and `off-corpus-check.md` under `docs/why-verdict/`. Its
  head and its commit count are what `corpus-reasons.md:39` and `:10` assert
  them to be. The same is true of `./corpus-provenance.md`, cited at
  `corpus-reasons.md:36`: not in this repository, present twice beside that
  store. That is itself an instance of the finding — two repository-relative
  `./` citations in a repository document that resolve only on one laptop.
- `/Users/lfigea/.openclaw/runs/bc-10330567406-deliver-the-first-priority-canvas-todo-p/scratch-ws/state/canvas`
  — head `de136d38d303b70a77771a167260c9e70a48d8da`, 7 commits, holding
  `json-flatten-roundtrip-limits.xml`. The store the four off-corpus reasons are
  the commits of.

**Twenty stores were read for the `answered="true"` count**, enumerated in §5.1
below with their head shas; the second store above is one of them.

Not a canvas store, but read as *evidence* the four off-corpus reasons name:
the clone at
`/Users/lfigea/.openclaw/runs/bc-10330567406-deliver-the-first-priority-canvas-todo-p/work/json-flatten`,
local branch `roundtrip-limits`, head
`e85be5764cd928ee68e02210fadddfb750235e57`.

### 2.3 Was there a live store at `$OPENCLAW_WORKSPACE/state/canvas`?

**No. `$OPENCLAW_WORKSPACE` is `/Users/lfigea/.openclaw/workspace`, and there was
no canvas store at `/Users/lfigea/.openclaw/workspace/state/canvas` at the time
this finding looked, on 2026-09-24.**

    $ echo "OPENCLAW_WORKSPACE=${OPENCLAW_WORKSPACE:-<unset>}"
    OPENCLAW_WORKSPACE=/Users/lfigea/.openclaw/workspace
    $ if [ -d "$OPENCLAW_WORKSPACE/state/canvas" ]; then echo EXISTS; else echo ABSENT; fi
    ABSENT

Corroborated by the enumeration in §5.1, which walks all of `/Users/lfigea` and
returns no path under `…/workspace`. `…/workspace/state` exists and holds many
files; it has no `canvas` entry. **All twenty stores sit inside a disposable
directory** — eighteen under `.openclaw/runs/…`, two under `.openclaw/tmp/…`.
Every sha in this document that is not in `malkovro/canvas` is a sha in a
directory somebody will delete.

---

## 3. The measurement

### 3.1 The rule, stated before the counts

A reason **asserts a fact about the world** when it contains at least one
declarative statement about the state of something *outside the canvas
document* — source code, a test, a command's observed behaviour, a
specification's or a todo's text, a commit, a branch or a pull request, another
document or a report file — that is true or false independently of the writer's
intentions, and that a reader could in principle check by going and looking at
that thing.

A reason that **only explains intent** is one whose every sentence is of these
kinds: what this node holds or is for; why the writer placed it here, in this
shape, in this order; what a future reader will want, or what is editorially
better or worse; what the writer expects or predicts; or a statement about
**this same canvas document** — its nodes, their content, their arrangement,
their versions.

Four qualifiers, so that a second reader classifies the same way:

- **(a) A specific artifact, not a generality.** *"The todo says X"* is in. *"A
  decision three weeks old is no longer able to reconstruct its cost"* is out —
  it names no artifact.
- **(b) The tool, the schema and the specs are the world.** *"The tool has no
  way to mark a question answered"*, *"a `<table>` carries no column names"* are
  facts about `canvas/store.py`, `canvas/cli.py` and `schema/canvas.rng`, which
  are artifacts outside the document and checkable in the repository the canvas
  describes. They count. This is stated here, before the count, because it
  materially moves the number.
- **(c) The canvas itself is not the world.** A claim about a sibling node's
  text — *"nf98 has said since the first half that the option taken in code is
  B"* — is a claim about the document, and the `--why` rule's §5.1 clause
  already governs naming siblings. Out.
- **(d) One qualifying sentence is enough.** A reason nine-tenths intent and
  one-tenth *"the five call sites are not all alike"* is in.

**What counts as evidence a reader can follow.** The convention's test is *"so a
reader can follow it"*. A reason names followable evidence when it carries at
least one **locator** — something a reader can resolve to a specific artifact
without already knowing the answer: a repository-relative path, with or without
a line; a named section of a named document; a commit sha, a branch name or a PR
number; a unique source identifier a reader can grep for (`_not_a_repository`,
`_OS_NEXT_ACTION`); a report file path; a numbered or titled clause of this
canvas's own todo, which the `ledger` attribute pins; or a verbatim quotation
attributed to the todo. **Not** a locator: a role reference with no name and no
quotation — *"the ledger row"*, *"the launch brief"*, *"the staleness check"*,
*"the ENOENT template"*. The node's own text is never counted: every reason
trivially has its node, and counting it would make count 2 equal count 1 and
measure nothing.

The rule was written before the first classification and was not refined while
reading.

### 3.2 The three counts

Over the 54 reasons of §2.1:

- **43 of 54 assert a fact about the world.**
- **24 of those 43 name evidence a reader can follow.**
- **21 of those 24 name evidence that still resolves today, and resolves to what
  the reason claims.**

**The classification is a judgment applied by hand to 54 texts; no command can
re-derive it, and this finding does not pretend otherwise.** What is given
instead is the exact enumerated list of shas behind each number, so a second
reader can check the calls one at a time rather than take a number on trust.
Each count is then re-derived from its own list by counting it.

**Count 1 — asserts a fact about the world: 43.**

    printf '%s\n' \
      d65e081 e694e94 7fcaeff 94ce546 8467e0f b7a301d 525ab66 65c0377 \
      f54cd5a 8021671 a41ca41 6e29a84 2f10783 bd1f849 4545dd3 2503e2c \
      9211127 96cd4bf 0cdd29f 213a280 5fa80e6 a78e225 35e25a1 fe84545 \
      7a5b1f9 e950b24 f7be9ea 90907b5 f0e23e0 61f5d74 764554a 9236168 \
      2d7ae95 fad921f 619d585 6be144a 153152b a846cb7 b62b428 \
      8d719d3 bfc3cbe a0b4efa de136d3 | wc -l        # 43

Thirty-nine from Part A, four from Part B — all four off-corpus reasons assert a
fact. The eleven Part A reasons that do **not**, so the partition is checkable
and not merely asserted: `0b2e20b`, `28985c6`, `041147e`, `61ba4a9`, `96276cf`,
`2cfb511`, `45bd148`, `8f38fae`, `be92dab`, `8c6da79`, `3aebd79`. 39 + 11 = 50.

**Count 2 — of those, name evidence a reader can follow: 24.**

    printf '%s\n' \
      7fcaeff a41ca41 6e29a84 2503e2c 9211127 96cd4bf 0cdd29f 213a280 \
      5fa80e6 fe84545 7a5b1f9 e950b24 f7be9ea 61f5d74 764554a 2d7ae95 \
      fad921f 619d585 6be144a a846cb7 \
      8d719d3 bfc3cbe a0b4efa de136d3 | wc -l        # 24

Twenty from Part A, four from Part B. The **19** Part A reasons that assert a
fact and name nothing followable: `d65e081`, `e694e94`, `94ce546`, `8467e0f`,
`b7a301d`, `525ab66`, `65c0377`, `f54cd5a`, `8021671`, `2f10783`, `bd1f849`,
`4545dd3`, `a78e225`, `35e25a1`, `90907b5`, `f0e23e0`, `9236168`, `153152b`,
`b62b428`. 20 + 19 = 39.

**Count 3 — of those 24, whose evidence still resolves today: 21.**

    printf '%s\n' \
      7fcaeff a41ca41 6e29a84 2503e2c 9211127 96cd4bf 213a280 5fa80e6 \
      fe84545 7a5b1f9 e950b24 61f5d74 764554a 2d7ae95 619d585 6be144a \
      a846cb7 \
      8d719d3 bfc3cbe a0b4efa de136d3 | wc -l        # 21

Does **not** resolve: `0cdd29f`, `f7be9ea`, `fad921f`. 21 + 3 = 24. §4 gives
each in full.

The reason text behind any sha above is printed by

    git -C /Users/lfigea/.openclaw/runs/bc-10326884789-deliver-the-first-priority-canvas-todo-r/corpus-store \
        log -1 --format=%s <sha>          # Part A

    git -C /Users/lfigea/.openclaw/runs/bc-10330567406-deliver-the-first-priority-canvas-todo-p/scratch-ws/state/canvas \
        log -1 --format=%s <sha>          # Part B

and each is also quoted in full in `corpus-reasons.md` and `off-corpus-check.md`
in this repository, which is the copy that survives those directories.

### 3.3 The headline of count 2 is the gap, not the number

Nineteen of forty-three — **44%** — of the reasons that assert something about
the branch name nothing a reader could check. Every one of the nineteen is a
claim about the branch or the tool: *"the five call sites are known"*, *"the tool
brings exactly one node per edit"*, *"the vocabulary has no other kind of
cell"*, *"prose is the only thing enforcing it"*, *"the code moved"*, *"this
branch does not descend from main"*. They may all be true. Nothing in the reason
lets a reader find out, and nothing ever will: these are the claims that cannot
drift *visibly*, because they cannot be checked at all.

The sharpest pair sits five entries apart in the same canvas, under the same
author trailer (`claude-opus-5 | second-writer`):

- `9236168` — *"the ENOENT template now names no repair at all"*. **Names
  nothing.** *"The ENOENT template"* is a description whose referent a reader
  must already have from the surrounding nodes.
- `f7be9ea` — the same object, called `_OS_NEXT_ACTION`. **Names something**, and
  precisely because it does, §4.3 was able to check it and find it wrong.

That is the whole of the convention's value in two sentences, and the existing
clause — *"a PR, a verdict, a file and line"* — does not distinguish them.

---

## 4. Resolution, actually attempted

Each of the 24 was followed — the artifact opened, the line read, and where the
claim was about behaviour rather than text, the command actually re-run. Where a
reason is about an older state it was checked against the state at the sha it
was written at as well as against today; all 55
corpus commits were written on 2026-09-22 between 20:57:43 and 21:49:17 +0200,
which is the "written at" baseline. **Nothing in the corpus went unresolved for
want of access.** There is no "could not check" bucket: every artifact named by
any of the 24 was found and read, and the three failures below are failures of
the claim, not of access.

### 4.1 The twenty-one that resolve, in one line each

- `7fcaeff` — quotes the todo, *"Decide which is right and make the code say
  so"*; `grep -c` over the todo → 1. Verbatim.
- `a41ca41` — quotes condition (1); `grep -c` → 1, modulo Markdown decoration.
- `6e29a84` — *"the form condition (1) would accept"*; condition (1)'s second
  branch is exactly that.
- `2503e2c` — *"Case 2 of the todo"*; the todo carries that heading.
- `9211127` — quotes *"this is not a broken repair…"*; `grep -c` → 1.
- `96cd4bf` — *"the one condition (3) can be enforced mechanically"*; it is (3)'s
  first branch.
- `213a280` — conditions (2) and (3); both say what the reason says.
- `5fa80e6` — `_not_a_repository`; its docstring and its exit 2 are as claimed,
  at `cd8d90e` and at head.
- `fe84545` — *"the todo's own reproduce command … a Canvas-Next with no ls in
  it"*; **re-run** on head, and the printed `Canvas-Next:` still carries no `ls`.
- `7a5b1f9` — three pieces: `guidelines/correction-authority.md`'s order of
  authority, the description's citation of `canvas/store.py:582`, and two
  zero-counts against `main` **as it stood when written** (`6c0c5d2`). All three
  hold. See §4.5 for the line number it repeats.
- `e950b24` — `os_next_action`; six call sites then, six now.
- `61f5d74` — the todo's Case 2 steps and the ENOENT template; the template still
  says *"says which"* and its repair still exits 2 run verbatim.
- `764554a` — condition (4); the two demonstrations are there.
- `2d7ae95` — *"the README"*, twice: the staleness check and both its branches
  are at `README.md:154`, `:755`, `:770`, and `read` was **re-run** — it names no
  other writer, exactly as the reason says.
- `619d585` — `README.md` §*Exit codes*, the sha `e950b24a` seven commits back,
  and node `nf98`. All three.
- `6be144a` — `README.md` §*Exit codes* argues the race, as claimed; and its
  other world-claim, *"a node carries no status"*, is still true —
  `schema/canvas.rng:194`, *"`answered` is legal here and on no other element"*.
- `a846cb7` — `engineering-spec.md` §*Lifecycle*, heading at `:341`, quoted word
  for word. The strongest citation in Part A.
- `8d719d3` — `json_flatten.py` at `78c2835`, four line citations and a report
  file. Every piece, at the sha it names.
- `bfc3cbe` — commit `60db66c`, *"the three added cases"* (exactly three, named),
  `README.md` §*'Is my document safe?'*. Resolves; see §4.5 for its line number.
- `a0b4efa` — commit `e85be57`, `json_flatten.py:74` (`_types_re`, exact), `:43`,
  and `roundtrip-check.md`'s 33 documents and 24,158-document fuzz. Every piece,
  exactly.
- `de136d3` — `roundtrip-check.md`'s 33 and 30. As claimed.

**Exactly one corpus reason names a pull request** — `7a5b1f9`, whose reason
reads *"the base is PR #8's branch"*:

    $ gh pr view 8 --repo malkovro/canvas --json number,state,mergedAt
    {"number":8,"state":"MERGED","mergedAt":"2026-09-22T23:30:51Z"}

Merged, its head commit `cd8d90e` is the branch point the canvas names, and the
reason's claim is true as history. **No pull request named by any of the fifty
is unmerged.**

*Recorded about all four Part B reasons:* the branch `roundtrip-limits` they
resolve on is **local only** — that clone has no `origin/roundtrip-limits`.
`bfc3cbe` says *"in this clone"* and is honest about it; `8d719d3`, `a0b4efa`
and `de136d3` do not, and their shas resolve nowhere but on this laptop. The
report files they name are untracked, in a run directory.

### 4.2 `0cdd29f` — a quotation that is not in the thing it quotes

> the other half condition (2) offers, written with the part the todo leaves
> implicit made explicit: 'says how a caller tells them apart' is a change to the
> refusal format, not only to the README.

The quoted string is attributed to condition (2) of todo 10329619223. It is not
in it:

    $ grep -c "says how a caller tells them apart" <the todo, as Markdown>
    0
    $ grep -o "says how a caller tells [a-z ]*" <the todo, as Markdown>
    says how a caller tells the diagnostic from the repair

**The substance survives; the quotation does not.** "Them" and "the diagnostic
from the repair" mean the same thing here, and the reason's point is a fair
reading of condition (2). What does not survive is that a reader who follows the
quote marks — which is precisely what the convention invites — does not find that
sentence, and must then decide whether the writer misremembered, paraphrased, or
was reading a different version. That is the failure mode the convention exists
to prevent, arriving in miniature. Contrast `213a280`, whose scare-quoted *"write
it down in the README"* is the writer's own paraphrase of option B, attributed to
nobody, and which resolves.

### 4.3 `f7be9ea` — a count that is wrong, and a claim that time falsified

> … running every command **all fifteen `_OS_NEXT_ACTION` templates** name showed
> four of them are not commands at all …
>
> … **The question node becomes the answer because the tool has no way to mark a
> question answered while leaving it standing** …

**(a) The named object holds fourteen.**

    $ python3 -c "from canvas import refusal; print(len(refusal._OS_NEXT_ACTION))"
    14

and fourteen at every sha this reason could have meant — the branch base
`cd8d90e` and both branch commits `a948431`, `8326431`. The module also carries
two fallbacks outside the dict, `_OS_NEXT_ACTION_DEFAULT` and
`_OS_NEXT_ACTION_NO_PATH`, which makes **16** templates in `canvas/refusal.py`
altogether. Neither number is fifteen. The likeliest arithmetic is 14 + the
default — right about the work, wrong about the object named — but that is a
reconstruction, and reconstructing a citation is what the convention exists to
make unnecessary. **This is reported as not resolving, not as a lie:** the work
plainly happened, and node `l32v` lists eight commands with their exit codes.

It is also the one place in the corpus where the evidence is named precisely
enough to be *contradicted*. `_OS_NEXT_ACTION` is a grep-able identifier, so the
number beside it is falsifiable. The nineteen reasons in §3.3 cannot be wrong in
this way, because they cannot be checked at all.

**(b) The claim about the tool is false today.** True when written, 2026-09-22
21:28:33 +0200. False since **2026-09-23T04:51:16Z**, when PR #14 (*node-state*)
merged — about seven hours later. Today `schema/canvas.rng:207` defines
`<attribute name="answered">` inside `<define name="question">`, and
`canvas/cli.py:496-498` carries `--answered`, *"mark a `<question>` answered;
absence means open"*. Run rather than read, on head `599d5ba` against a fresh
workspace, a `replace … --answered` produced

    <question id="kjwf" v="2" answered="true">Is this settled?</question>

— marked answered and still standing with its text intact, which is the precise
thing the reason says the tool cannot do. **The design move the reason justifies
rests on a constraint the tool no longer has.** This is canvas-versus-branch
drift in the pure form the specs name, and it took seven hours.

### 4.4 `fad921f` — the same claim, in the reason that settles Case 1

> … **The question node becomes the answer because the tool has no way to mark a
> question answered while leaving it standing**; what was asked is still in this
> node's history. …

Identical to §4.3(b), and false since the same merge. Recorded so it is not read
as a whole-reason failure: the reason's **other two** pieces of evidence do
resolve — `_cannot_read`'s docstring and its ENOENT branch are as described, and
`e950b24a` is indeed seven commits back.

That the same false sentence appears twice, in the two reasons that carry the
canvas's two decisions, is the point: the drift is not a typo. It is one belief
about the tool, held while writing, that a merge on another branch overtook.

### 4.5 Two citations that drifted without the claim failing

Not counted as disagreements — in both, the sentence the reason asserts is still
true — but recorded, because they are the same drift one step earlier, and
because they are the form the convention's own wording recommends.

- **`7a5b1f9` repeats `canvas/store.py:582`.** True at `cd8d90e`. On today's main
  `_cannot_read_repository` is at **`:640`**, and `:582` is a docstring line. A
  reader following the number today lands 58 lines short.
- **`bfc3cbe` cites `json_flatten.py:89`.** At the commit it names, `:89` is the
  comment; the code it means is at `:91`. At the *pre-fix* sha a sibling node
  cites, `:89` is the defective line — so the citation is correct against the
  wrong sha.

Every citation in this corpus that is a **name** rather than a number resolved
unchanged. That asymmetry is what *Prefer a name to a line number* in §6 rests
on.

### 4.6 The same drift, outside the corpus, in this repository's own documents

Collected while writing this rather than while measuring, and reported because
it is the clearest instance of the pattern §4.5 describes — it happens to be
about the very paragraph this whole task exists to serve.

The drift paragraph in `engineering-spec.md` — §*Coherence*, *"Between the canvas
and reality … it should be fixed with evidence in the reason before it is fixed
with a new attribute"* — is on `main` today at **`:280-290`**. It is cited by
line, by eight sentences in four documents of this repository, in three
different ranges (the block below gives each hit's path and the range it
cites; the surrounding prose of each line is elided):

    $ grep -rn 'engineering-spec.md:2[0-9][0-9]' --include='*.md' .
    node-naming.md:106                        …:272-276
    node-state.md:131                         …:272-276
    node-state.md:389                         …:272-276
    node-state.md:391                         …:266-276
    node-state.md:466                         …:266-276
    node-state.md:650                         …:272-276
    docs/why-verdict/VERDICT.md:112           …:270-272
    docs/why-verdict/off-corpus-check.md:105  …:270-272

    $ grep -n 'engineering-spec.md:2[0-9][0-9]' \
        /Users/lfigea/Projects/ledger-orchestrator/guidelines/domain-decisions.md
    44:  `engineering-spec.md:272-276` already rejected as premature: *"A state field

plus `guidelines/domain-decisions.md:44` in the ledger-orchestrator repository
and the Basecamp todo that commissioned this finding, which cites `:274-284` —
ten citations of one paragraph, in four ranges, none of them `:280-290`.
**Not one of them resolves today**, and two of the ranges are worse than merely
wrong: `:270-272` and `:272-276` now land inside the *Inside the canvas*
paragraph — the **other** of the two risks that section distinguishes, the
coherence check. A reader following `domain-decisions.md:44` today reads about
asking a model whether an edit contradicts a sibling node, and concludes that
*that* is what was rejected as premature.

The mechanism is visible in two commands, and nobody did anything wrong:

    $ git show 90ff189:engineering-spec.md | grep -n 'Between the canvas and reality'
    274:**Between the canvas and reality** — the canvas says we chose A; the branch
    $ grep -n 'Between the canvas and reality' engineering-spec.md
    280:**Between the canvas and reality** — the canvas says we chose A; the branch

At `90ff189` — `main` as it stood when the todo was written — the todo's `:274`
was exactly right. On the way to `599d5ba`, commit `cf693ac` (PR #22, *"close
`<question>`'s retirement clause, because node-state.md closed it"*) inserted six
lines at `:109`, a hunk 165 lines above and about something else, and the
paragraph moved to `:280`. **Nobody touched the citation, and nobody could have
known to.** The section title finds it in one search and always will; the number
was correct for a day.

That is the whole argument for *Prefer a name to a line number* in §6, and it
did not need the corpus to make it.

---

## 5. The `answered="true"` markers

`guidelines/domain-decisions.md` records, under *Known tensions*: *"**An
`answered="true"` can go stale exactly as a sentence in prose can.** Nothing
verifies that an answered question really was answered."* Its defence is *"that
the marker is set by the same commit that writes the answer, so the window is
one commit wide rather than open-ended — but that is a defence and not a proof.
If it bites, this is the sentence to point at."* This is the same
measurement as §3, one field over. It is asked here by name because a finding
about reasons could otherwise be complete without any marker ever being looked
at.

### 5.1 The population, stated before it is counted

The population is every directory printed on stdout by

    find /Users/lfigea -type d -path '*state/canvas'

**Twenty stores, not ten.** The Basecamp todo, written 2026-09-23, says this
command finds ten — *"eight under `.openclaw/runs/…` and two under
`.openclaw/tmp/…`"*. Today it finds **twenty**: eighteen under
`.openclaw/runs/…` and two under `.openclaw/tmp/…`. The two `tmp` stores the
todo names are both still there, unchanged in path; the ten extra were written
by runs that happened after the todo. The count below is over the twenty found
today. (`find` on this machine is `bfs` and exits 1: 163 directories under
`~/Library` and `~/.Trash` refuse traversal. Those are diagnostics on stderr,
none of them under `.openclaw`, so no candidate store was skipped by a
permission denial. `bfs` walks in parallel, so the print order is not stable and
the set is compared sorted.)

Each store is its own git repository — `git -C <store> rev-parse --show-toplevel`
returns the store path itself for all twenty. Absolute path, head sha, and
occurrences of `answered="true"`, in sorted path order:

- `/Users/lfigea/.openclaw/runs/bc-10326884519-deliver-the-first-priority-canvas-todo-i/scratch-verify/ws/state/canvas` — head `06feedbeca6f5c3c8af13031551c047e2f6ff356` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10326884731-deliver-the-first-priority-canvas-todo-d/canvas-store/state/canvas` — head `02de26b71893d1d33d1559cd0fd9bcfcaff84652` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10330566878-deliver-the-first-priority-canvas-todo-m/verify-ws/state/canvas` — head `de2dc616cc8ee33a73bd00c566807785e0694da7` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10330566962-deliver-the-first-priority-canvas-todo-s/canvas-store/state/canvas` — head `701a6736e58bde4a8c2938e971d88508d2519fed` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10330567406-deliver-the-first-priority-canvas-todo-p/measure/ws-driveby/state/canvas` — head `bbe20829154b757900aeb5e0c1cf259e87e4831c` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10330567406-deliver-the-first-priority-canvas-todo-p/measure/ws-merge/state/canvas` — head `a067e4e08631fcd34d9e45ad264edeaced4bbc4e` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10330567406-deliver-the-first-priority-canvas-todo-p/scratch-freeze-ws/state/canvas` — head `3970ec23cd972f97776b12916b1f02b333cc51aa` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10330567406-deliver-the-first-priority-canvas-todo-p/scratch-ws/state/canvas` — head `de136d38d303b70a77771a167260c9e70a48d8da` — **0** *(the off-corpus store of §2.2)*
- `/Users/lfigea/.openclaw/runs/bc-10330923765-deliver-the-first-priority-canvas-todo-a/repro-confirm/state/canvas` — head `f4b241e66dc7fa33f646d67a064607633e40c391` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10330923765-deliver-the-first-priority-canvas-todo-a/verify-ws-prefix/state/canvas` — head `ab2ccbe52390bcf2cc4c8809dc13a053836aeddc` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10330923765-deliver-the-first-priority-canvas-todo-a/verify-ws/state/canvas` — head `7b8978bd7f4f11fd4099944d68d0e423a491d781` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10332616712-deliver-the-first-priority-canvas-todo-t/scratch-after/state/canvas` — head `c9d6627e1215ad3933ff0cd243d58d63cae5f2e7` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10332616712-deliver-the-first-priority-canvas-todo-t/scratch-check/state/canvas` — head `3d1aa58cd9284f5fc802756e40086dfe523b3b71` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10332616712-deliver-the-first-priority-canvas-todo-t/scratch-freeze-probe/state/canvas` — head `bddf49f6d06bf0e793e6480d86e7687e462ebcb5` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10332616712-deliver-the-first-priority-canvas-todo-t/scratch-workspace/state/canvas` — head `7de22b73013b4e0bfe85014e7ebd7652f4d6ab97` — **0**
- `/Users/lfigea/.openclaw/runs/bc-10334515971-deliver-the-first-priority-canvas-todo-a/.demo/state/canvas` — head `071a7b3e388441c112d198025f5066ccc71f705e` — **1**
- `/Users/lfigea/.openclaw/runs/bc-10334519573-deliver-the-first-priority-canvas-todo-l/scratch-ws/state/canvas` — head `3e598582f5f1858a06850dc4cd2b100154573d88` — **2**
- `/Users/lfigea/.openclaw/runs/canvas-10331851610-recovery-20260924T053857/scratch-verify/ws/state/canvas` — head `06264e2434ecceb84a56946111d573a4efbfafda` — **1**
- `/Users/lfigea/.openclaw/tmp/canvas-sample-qlvwpoxo/state/canvas` — head `2502cdabc375d36e7985341edf16b1a878737b42` — **1**
- `/Users/lfigea/.openclaw/tmp/canvas-store-test-ss_frdng/state/canvas` — head `036cfd98231731ed4385b592955d362baee9e48c` — **0**

There is **no live store at `$OPENCLAW_WORKSPACE/state/canvas`**, as §2.3
records with the direct directory test; the `find` above returns no path under
`…/workspace`.

### 5.2 The count, with the command beside it

    while read s; do
      n=$(grep -rc 'answered="true"' "$s" 2>/dev/null | awk -F: '{t+=$NF} END{print t+0}')
      echo "$n  $s"
    done < <(find /Users/lfigea -type d -path '*state/canvas' | sort)

**Five markers, in five files, across four of the twenty stores.** The other
**sixteen return zero, and each of those sixteen is named in §5.1 with its zero
beside it** — a zero counted is evidence; an unmentioned store is not. The
per-marker lines come from

    grep -rn 'answered="true"' <store>

**What the todo expected, tested rather than assumed.** The todo expects nine
stores at zero and one store with exactly one marker, *"in a renderer sample
rather than a live ledger row's canvas"*. What is actually here: twenty stores,
five markers, four stores. The one the todo names — `kncz`, at
`/Users/lfigea/.openclaw/tmp/canvas-sample-qlvwpoxo/state/canvas/sample-canvas.xml:24`
— is still there, unchanged, at the same path and the same line, and it **is**
the renderer sample the todo says it is. The other four are in stores that did
not exist when the todo was written, and **three of the four — `cqzm`, `mbp7`
and `ayhr` — sit on a canvas minted for a ledger row rather than on a renderer
sample**. The todo's reassurance, that no row relies on any of these, no longer
covers the population.

### 5.3 Each marker, and whether what it marks answered still holds

The setting commit of each was found with
`git -C <store> log -S 'answered="true"' --format='%H %s%n%b' -- <file>`, which
in every case returns exactly one commit.

**`kncz`** — `…/tmp/canvas-sample-qlvwpoxo/state/canvas/sample-canvas.xml:24`,
*"Does an answered question keep its entry in the index?"*. Set by
`5db05c79b95c41700c35e4a9c577ea3547f7ee4f`, 2026-09-23, verb `insert` — **born
answered**. Its `--why` names `rendering.md` section 2 and states its own
retirement trigger. **Still holds:** `rendering.md:119` carries that section,
word for word — *"The index names every `<question>`, and an answered
one is quiet rather than absent"* — `:121-122` says answered ones are included,
and `:145` is a subsection titled *Why an answered question stays in the index*.
The question's answer is yes, and the trigger has not fired. *Recorded:* the
`--why` states why the **fixture** exists; it does not state the answer. The
answer lives in `rendering.md`. The marker is right because `rendering.md`
happens to be right, not because the commit made it so.

**`u4fg`** — `…/bc-10334515971-…-a/.demo/state/canvas/bc-demo-canvas-tab.xml:7`,
*"Is the served page byte-identical to the render?"*. Set by
`64a19a1a34f3fbead7149384ed1e7e8adc1ab682`, 2026-09-24, verb `insert` — **born
answered**. Its `--why` in full: *"Answered by looking: diff of the render
against the served bytes reports no difference."* **It names no file, no sha, no
command and no output** — the marker equivalent of the nineteen in §3.3.
**Still holds**, but not because the `--why` let me check it: that run's own
`CHECK.md:145-149` records sha1 `f8d12c45…` for both the rendered and the served
file and a silent `diff`. I found that by walking the run directory. The two
temporary files and the server are gone, so the check is not re-runnable; the
recorded sha1s are what is left. The node still reads as a question, so **the
answer exists only in the `--why`, and the `--why` is the part that names
nothing.**

**`cqzm`** —
`…/canvas-10331851610-recovery-20260924T053857/scratch-verify/ws/state/canvas/verify-row-10331851610.xml:6`,
on whether a sha printed in a comment block is character-for-character the sha
`bin/canvas read` reports. Set by `06264e2434ecceb84a56946111d573a4efbfafda`,
2026-09-24, verb `replace`. **The best-evidenced marker of the five** — its
`--why` names the function, the keyword argument, the produced line, both 40-char
shas and how they were compared. **It half-resolves.**

- The sha `3eb68c7dd9dfb2fbe34712a0b9967f7fba0a54f9` is a commit in that store
  and is exactly the parent of the marker commit, so `Canvas-Base: 3eb68c7…` is
  what `read` would have printed. ✓
- `orchestrator.basecamp.render_ledger_live` exists, at
  `/Users/lfigea/Projects/ledger-orchestrator/orchestrator/basecamp.py:1025`. ✓
- **`canvas_comment` is not a parameter of it and `rowsync.row_canvas` does not
  exist**: in the live checkout, `grep -c canvas_comment orchestrator/basecamp.py`
  → 0 and `grep -c 'def row_canvas' orchestrator/rowsync.py` → 0. Both exist only
  in that run's own checkout, on an unmerged branch; the canvas-side change is
  PR #23, still open.

**The arithmetic holds and the apparatus does not resolve.** A reader following
this `--why` from the live checkout today cannot reproduce the observation. This
is the textbook case: the reason named its evidence scrupulously, and the named
code is on an unmerged branch in a disposable directory. **Naming the evidence is
what made that visible.**

**`mbp7`** — `…/bc-10334519573-…-l/scratch-ws/state/canvas/demo-row.xml:4`,
*"Does a form submission reach the canvas as one bin/canvas invocation?"*. Set by
`cb338d2b1802aebfb83ad333da03d076f51b6a4b`, 2026-09-24, verb `replace`. Its
`--why` names the store's own git log as its evidence and differentiates node
`dxtb` by id. **Still holds:** that log carries four commits with
`Canvas-Author: Leo Figea`, one per form submission, and three `open`-minted
commits that are not. The best-formed of the five — it names evidence that lives
in the same store as the marker, and it satisfies the §5.1 clause besides.

**`ayhr`** — `…/bc-10334519573-…-l/scratch-ws/state/canvas/demo-row-2.xml:4`,
*"Is every argv the page sends a bin/canvas argv?"*. Set by
`369062494fb6667632f081e1d75a3ca3cb0ee25b`, 2026-09-24, verb `replace`. **Still
holds, one half followable and one half not:** *"the store's working tree stayed
clean"* is checkable and checks out (`git status --porcelain` prints nothing);
*"the wrapper logged one bin/canvas argv for every submission"* names no log — I
found `…/scratch-ws/spy.log` by walking the run directory, and its ten lines do
hold five reads and five write argvs, including this marker's own invocation.
Same shape as `u4fg`: the substance is true, the artifact exists, the reason does
not name it.

### 5.4 What the markers add up to

**Five markers. Five still hold.** None marks a question that the branch later
answered the other way, which is the failure the todo was braced for. On this
evidence the *Known tensions* sentence has not bitten, and there is no case here
for an attribute that records verification — see §7.1.

The finding is in **how** they hold:

- **The best-evidenced of the five is the one that does not resolve.** `cqzm`
  names the function, the keyword argument, the produced line and both shas —
  and the code it names is on an unmerged branch in a directory somebody will
  delete. Naming the evidence is what made that visible; the other four could
  not have failed in this way, because they do not say enough to be checked
  against anything.
- **Two of five name nothing a reader could reach** — `u4fg` entirely, `ayhr` for
  the half that carries the claim. Both are true. Each was confirmed from a file
  the `--why` does not mention — `CHECK.md`, `spy.log` — found by walking a run
  directory. **Another reader in a month, after these directories are gone,
  would have the marker and nothing else.**
- **`kncz` names its evidence, the evidence resolves, and the `--why` still does
  not state the answer.** It says why the *fixture* exists; the answer lives in
  `rendering.md` §2. The marker is right because that section is right, not
  because the commit that set it made it so.
- **Two of five** (`kncz`, `u4fg`) were set by `insert --answered` — born
  answered — so `domain-decisions.md`'s defence, *"the marker is set by the same
  commit that writes the answer, so the window is one commit wide"*, does not
  describe them at all: there was no commit that wrote the answer, only a commit
  that asserted one. That is not an argument against the attribute; it is an
  argument that the defence is doing less work than it reads as doing, and that
  what actually carries the marker is the reason beside it.

---

## 6. The ruling: strengthen the evidence clause, in prose

The convention is not as far as this goes. It is right about the *thing to do*
and silent about the two ways this corpus shows it failing — a locator nobody
else can resolve, and a locator that does not survive the week. Both gaps are
gaps in wording, and both are fixed by telling a writer something, which is
exactly where `VERDICT.md` §5.1 put the last fix and for the same reason: there
is nothing the tool could compute here; there is something a writer could be
told.

What the measurement licenses, sentence by sentence:

- *Name something a reader can resolve without already knowing the answer* —
  from §3.3: 19 of 43, and the `9236168` / `f7be9ea` pair five entries apart.
- *Prefer a name to a line number* — from §4.5, §4.1 and above all §4.6: every
  name resolved; both bare line numbers in the corpus point at something other
  than what they meant; and ten citations of the one paragraph this task serves,
  across two repositories and a Basecamp todo, all miss it today.
- *Pin a claim about how the code is today* — from §4.3(b) and §4.4: the only
  true canvas-versus-branch drift in the corpus, twice, seven hours after it was
  written.
- *Quote verbatim or do not quote* — from §4.2.
- *None of this is a required form* — from §7.2, and from `VERDICT.md` §5.3.

### 6.1 The replacement text for `guidelines/canvas-why.md`

Replaces `guidelines/canvas-why.md:37-44` — the heading and the paragraph under
it — in full. Carry it verbatim; it is written to be carried, not re-drafted.

> ## A reason that asserts a fact about the world names its evidence
>
> Convention, not enforcement. An edit whose reason asserts a fact about the
> world — that a PR merged, that a verdict ruled, that a file says something —
> should name its evidence in `--why`, so a reader can follow it. Nothing
> enforces that, and nothing is meant to; it is the only mitigation the canvas
> specs have for the canvas drifting from the branch it describes.
>
> **Name something a reader can resolve without already knowing the answer.** A
> path, a commit sha, a pull request, a titled section, a report file, or an
> identifier they can grep for. *"The ENOENT template"*, *"the staleness
> check"*, *"the launch brief"* and *"the ledger row"* name a role rather than
> an artifact: a reader who does not already know which artifact you meant
> cannot get there from the reason, and a claim nobody can reach is a claim
> nobody can check.
>
> **Prefer a name to a line number.** Fifty-four real reasons were read for
> whether the evidence they name still resolves — `docs/why-verdict/DRIFT-CHECK.md`
> in the canvas repository — and every citation that was a name resolved
> unchanged, while both that were a bare line number now point at something
> other than what they meant. Give the line if it helps, and give something
> beside it that survives an edit.
>
> **Pin a claim about how the code is today.** If the reason turns on the
> current state of something — that the tool cannot do X, that no template names
> Y — name the sha you looked at, or say what would retire the claim. Two
> reasons in that corpus rested on *"the tool has no way to mark a question
> answered while leaving it standing"*; a merge on another branch made it false
> seven hours later, and neither reason says what a reader should re-check.
>
> **Quote verbatim, or do not use quotation marks.** They are an invitation to
> go and find the sentence. A paraphrase inside them costs a reader their trust
> in everything else the reason names.
>
> None of this is a required form. There is no `Evidence:` line, no required
> word, no shape a reason has to match and nothing that checks any of it: a
> check that could tell a real citation from a plausible-looking one would have
> to leave the canvas to run, and the freedom of the field is what
> `docs/why-verdict/VERDICT.md` §5.3 found load-bearing.

### 6.2 The replacement text for `README.md`

Replaces the `##### A reason that asserts a fact about the world names its
evidence` subsection of `README.md`'s `--why` section — today its heading and
the one paragraph under it — in full.

**What "the way §5.1's rule already is" means, measured rather than read off.**
§5.1's rule has two homes today, and the carry is not free-hand: the heading
differs (`## The rule, from VERDICT.md §5.1, verbatim` in the guideline,
`##### The rule a --why writer is given` in `README.md`) and each home writes
its own framing paragraph, but the rule text itself is one text. Pulling the
blockquote out of `guidelines/canvas-why.md` and out of `README.md` §*The rule a
`--why` writer is given* and stripping the `> ` markers gives eleven lines on
both sides that sha256 to `066a493f424cba10df045094ce4b1fc8b7690374c595432a858bb08a94854eb7`,
and `diff -u` between them is empty:

```
$ sed -n '/^## The rule, from/,/^## A reason that asserts/p' \
      ../ledger-orchestrator/guidelines/canvas-why.md |
      grep '^>' | sed 's/^> \{0,1\}//' | shasum -a 256
$ sed -n '/^##### The rule a `--why` writer is given/,/^##### A reason that asserts/p' \
      README.md | grep '^>' | sed 's/^> \{0,1\}//' | shasum -a 256
```

So the carry rule is: **heading level and the home's own framing sentence are
local; the advice itself is byte-identical.** The text below therefore keeps
`README.md`'s existing framing paragraph — which cites `engineering-spec.md` and
says why the README repeats the clause at all, and has no counterpart in the
guideline — and carries the four bolded paragraphs and the closing one from §6.1
unchanged, down to the byte. Stripped of the framing paragraph, both homes'
advice sha256s to
`c2c44bf0adf4e8fe447973efcc8ede3fbb7565dd33b126c7350db6500623329d`.

Two phrasings were considered and dropped, both of which would have made the two
homes differ: naming the drift check without its repository in `README.md`
(`` `docs/why-verdict/DRIFT-CHECK.md` read fifty-four real reasons ``, on the
grounds that "in the canvas repository" is redundant inside that repository),
and closing with a clause about the back-reference the store does refuse. The
first trades a redundancy a README reader can ignore for a locator a guideline
reader cannot resolve; the second says in the closing paragraph what the
subsection two above it already says at length. A clause this section is about
to tell writers to keep resolvable is the last one to shorten, and a text that
drifts between its two homes is the failure this whole document measures.

> ##### A reason that asserts a fact about the world names its evidence
>
> Convention, not enforcement — `engineering-spec.md` says the same thing about
> the one drift this specification does not solve, and this repeats it where a
> reader with only the README will meet it. An edit whose reason asserts a fact
> about the world — that a PR merged, that a verdict ruled, that a file says
> something — should name its evidence in `--why`, so a reader can follow it.
> Nothing enforces that, and nothing is meant to: the check would have to leave
> the canvas to run.
>
> **Name something a reader can resolve without already knowing the answer.** A
> path, a commit sha, a pull request, a titled section, a report file, or an
> identifier they can grep for. *"The ENOENT template"*, *"the staleness
> check"*, *"the launch brief"* and *"the ledger row"* name a role rather than
> an artifact: a reader who does not already know which artifact you meant
> cannot get there from the reason, and a claim nobody can reach is a claim
> nobody can check.
>
> **Prefer a name to a line number.** Fifty-four real reasons were read for
> whether the evidence they name still resolves — `docs/why-verdict/DRIFT-CHECK.md`
> in the canvas repository — and every citation that was a name resolved
> unchanged, while both that were a bare line number now point at something
> other than what they meant. Give the line if it helps, and give something
> beside it that survives an edit.
>
> **Pin a claim about how the code is today.** If the reason turns on the
> current state of something — that the tool cannot do X, that no template names
> Y — name the sha you looked at, or say what would retire the claim. Two
> reasons in that corpus rested on *"the tool has no way to mark a question
> answered while leaving it standing"*; a merge on another branch made it false
> seven hours later, and neither reason says what a reader should re-check.
>
> **Quote verbatim, or do not use quotation marks.** They are an invitation to
> go and find the sentence. A paraphrase inside them costs a reader their trust
> in everything else the reason names.
>
> None of this is a required form. There is no `Evidence:` line, no required
> word, no shape a reason has to match and nothing that checks any of it: a
> check that could tell a real citation from a plausible-looking one would have
> to leave the canvas to run, and the freedom of the field is what
> `docs/why-verdict/VERDICT.md` §5.3 found load-bearing.

Nothing else moves. `schema/canvas.rng` gains no attribute, `require_reason`
gains no check, `tests/` is untouched, and the `--why` interface — one required
free-text argument, four verbs, no fields — is exactly what it was.

---

## 7. The two things this finding refuses, and why the evidence refuses them

### 7.1 No attribute, and above all no state field

`engineering-spec.md` §*Coherence* orders it, at `:288-290` today — *"it should
be fixed with evidence in the reason before it is fixed with a new attribute"* —
and `guidelines/domain-decisions.md` makes it a domain decision: a canvas says
exactly one thing about a node's state, `answered` is legal on `<question>` and
on no other element, and a step that wants a second kind of state has to reopen
`node-state.md` rather than extend the grammar. This finding does not reopen it,
and the measurement is why rather than the ordering alone:

- **Every marker on this machine holds** (§5.4). A `verified` or `checked`
  attribute would today carry `true` five times out of five and distinguish
  nothing.
- **The drift that did happen is in the reason, not in the document.** `f7be9ea`
  and `fad921f` are prose about the tool that a merge falsified. No attribute on
  a node records that; what would have recorded it is a sha in the reason.
- **An attribute recording that something was verified is a claim about the
  world like any other, and goes stale the same way.** `node-state.md` §5 makes
  precisely this argument against the wider option. Setting `verified="true"` on
  `f7be9ea`'s node on 2026-09-22 would have been true that evening and wrong by
  breakfast, with the difference that a reader would now have two things to
  distrust instead of one.
- **It fails the decision rule.** *A fact a reader of the rendered canvas must
  act on belongs in the document; a fact a reader reconstructs when they ask why
  belongs in the reason.* Whether a claim was checked, and against what, is
  reconstructed when somebody asks why. It wants a better `--why`, which is what
  §6 is.

### 7.2 No check, and the check that was considered

The temptation is a guard beside `require_reason` in `canvas/store.py` that
refuses a reason with no locator in it. It is refused, on three grounds that are
this measurement's rather than the house rules':

- **It would fire on 44% of real reasons.** Nineteen of the forty-three in §3.3
  name nothing. `require_reason`'s back-reference guard was accepted with **one
  false positive in forty-one**, priced in advance in `VERDICT.md` §5.2 and
  asserted in a test. A guard that refuses nineteen in forty-three at exit 2 is
  not that trade; it is a rule that teaches writers to paste a path.
- **It cannot tell the two cases apart without the vocabulary moving into
  Python.** The distinction that matters is `_OS_NEXT_ACTION` versus *"the
  ENOENT template"* — an identifier that exists versus a phrase that reads like
  one. Separating them means knowing the names in the repository the canvas
  describes, which is leaving the canvas to run, and the shape-only version
  (does it contain something path-like?) passes *"the ENOENT template now names
  no repair"* the moment a writer types `canvas/refusal.py` beside it.
  `guidelines/domain-decisions.md` keeps the vocabulary in `schema/canvas.rng`
  and nowhere else; a table of identifier shapes in `canvas/store.py` is the
  same mistake one repository over.
- **It would have caught none of the three failures.** `0cdd29f` names condition
  (2) and quotes it — shape-perfect, and the quote is not there. `f7be9ea` names
  `_OS_NEXT_ACTION` — shape-perfect, and the number beside it is wrong.
  `fad921f` names `_cannot_read` and a sha — shape-perfect, and one clause of it
  is false. **All three failures are in the truth, and a check inside the canvas
  can only see the shape.** The truth is what this document measured, once, by
  hand.

## 8. What would reopen this, and what this could not settle

Stated so the ruling is falsifiable, and so the next step knows what to watch:

- **A marker that no longer holds.** Today five of five do. One `answered="true"`
  on a question the branch later answered the other way is the observation
  `domain-decisions.md` says to point at, and it reopens the attribute question
  rather than this one.
- **Drift after the strengthened clause is in writers' hands.** The nineteen in
  §3.3 were written without it. If a corpus written *with* §6's text in the
  prompt still leaves a third of its world-claims unfollowable, the conclusion
  that this is a wording gap is wrong, and the next candidate is the prompt
  integration rather than more prose.
- **A citation that resolves to the wrong thing more often than it resolves.**
  21 of 24 is why the convention is worth sharpening rather than replacing. If a
  later reading returns something like 12 of 24, naming evidence is not buying
  what this corpus says it buys.
- **A reason whose named evidence has been deleted rather than moved.** Every
  failure here is a citation that points somewhere wrong, not one that points
  nowhere. Much of what this document followed — both canvas stores of §2.2,
  `spy.log`, `CHECK.md`, `roundtrip-findings.md`, `roundtrip-check.md`, and the
  `json-flatten` clone — lives only in run directories somebody will delete. The
  first reason whose evidence is *gone* is a different problem from the one
  measured here, and prose will not fix it.

What this could not settle:

- **The classification in §3.1 is a judgment, not a computation.** Two careful
  readers will agree on most of the 54 and can disagree at the edges. The shas
  are enumerated so a disagreement can be located rather than argued in the
  aggregate.
- **`u4fg`'s check is not re-runnable.** The rendered and served files and the
  server are gone; the claim is reported as holding on the pair of sha1s in a
  file, not on a re-run.
- **The "fifteen templates" count is reported as not resolving, not as a lie.**
  I did not try to reconstruct which fifteen things the writer counted, because
  reconstructing a citation is what the convention exists to make unnecessary.
- **Entries 51 to 55 of `corpus-reasons.md` were not read**, as that file
  directs. The node entry 54 inserts still calls PR #8 *"the parent change,
  still open"*; that is outside the fifty, and this finding does not rule on it.
- **One canvas, one corpus, fifty-four reasons.** `VERDICT.md` §6's limitation
  applies here unchanged: the fifty are one task about `bin/canvas` itself, and
  the four are one row on one third-party library.
