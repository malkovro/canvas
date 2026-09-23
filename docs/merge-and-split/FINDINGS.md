# What the exercise showed

A factual reading of `canvas-transcript.md`. Every claim below names the invocation that
supports it, by the line the record starts at in that file. Nothing here is a recommendation
and nothing here rules on anything; the ruling is a later step's.

**What was run:** twenty-five `bin/canvas` invocations against a scratch store at
`…/bc-10330566962-deliver-the-first-priority-canvas-todo-s/canvas-store`, on canvas
`bc-10330566962-merge-and-split-exercise`. One `create`, eight `insert`, three `read`, two
`replace`, two `remove` (one refused), one `move`, eight `history` (one refused). The clone at
`…/canvas` was left on `main` at `798ee8c2e3372099646dd2ff044f58b44649bf1d` with an empty
`git status --porcelain`: no branch, no commit, no edit.

## The four ids

- **Split survivor — `e8ec`.** `replace` on it at `:148` returned `Canvas-Node: e8ec`. The id
  is unchanged and the final `read` at `:375` shows it at `v="2"`.
- **Split-born — `dkjk`.** The `insert --after e8ec` at `:161` minted it. `v="1"` in the final
  read at `:375`.
- **Merge survivor — `oskz`.** `replace` on it at `:174` returned `Canvas-Node: oskz`; `v="2"`
  in the final read at `:375`.
- **Stranded — `dwqu`.** `remove` at `:204` returned `Canvas-Node: dwqu` at exit 0. It is
  absent from the final `read` at `:375`: the string `dwqu` does not occur anywhere in that
  document.

## After the merge, does anything point at the stranded id?

**The document does not.** The final `read` at `:375` contains no occurrence of `dwqu`, in a
node id, in an attribute or in any text.

**The surviving node's history does — because a human typed it, not because the tool wrote
it.** `bin/canvas history … oskz` at `:266` prints two entries, and the second one, the merge's
`replace`, reads in part: *"Node dwqu holds that clause today and will hold nothing this node
does not once this commit lands."* That sentence is the whole of the pointer. It is free text
inside the `--why` the writer chose to write; had the writer not named the id, nothing in that
output would have contained it. The appendix at `:419` shows what the commit itself carries:
the trailers on the removing commit are `Canvas-Node: dwqu`, `Canvas-Author:` and
`Canvas-Base:` and nothing else. The tool minted no lineage field, no ancestor trailer and no
cross-reference of any kind.

So the pointer between the two halves of this merge exists in exactly one place: the prose of
two `--why` strings. It survives only as long as writers keep writing it.

## What `history` does with the stranded id

**It answers, at exit 0, with the node's whole life.** `bin/canvas history … dwqu` at `:286`
exits **0** and prints the `Canvas-Node: dwqu` header and two edit blocks: the original
`insert` (commit `f05035c…`) and the `remove` (commit `ce80ed3…`). The removing commit is the
last entry and its complete `--why` is printed. There is no refusal, no warning, and no
marker in the output saying the node is gone — the output for a retired id is the same shape
as the output for a live one (compare `:286` with `:266`).

**The stranded node's history is therefore not gone; it is retrievable in full.** The only
thing needed to retrieve it is the id itself. The appendix at `:419` confirms there are
exactly two commits naming `dwqu`, which are exactly the two entries `history` printed.

**But nothing in the document leads a reader to that id.** `read` at `:375` never mentions it,
and `history` takes an id as a required positional (`bin/canvas history <ledger_id> <node-id>`)
— there is no command in the exercise that listed or searched retired ids. A reader who does
not already know the string `dwqu` reaches it only through the sentence in `oskz`'s reason at
`:266`, i.e. through the convention, or not at all.

An id that never existed is a different case: `bin/canvas history … root` at `:358` exits
**1** with *"no node with id root in the history of the canvas … no commit names it, so it was
never a node of this canvas. The canvas is there; the node is not"*. So the tool does
distinguish "retired" (exit 0, full history) from "never a node" (exit 1, refusal) — but it
draws that line silently, inside the exit code, and says nothing in the exit-0 case about the
node having been removed other than the presence of a `remove:` entry.

## After the split, does the newly minted node carry anything about where it came from?

**Nothing the tool wrote.** `bin/canvas history … dkjk` at `:250` prints one entry: its own
`insert`, at commit `e9f2b03…`. The node is `v="1"` in the final read at `:375`. There is no
entry, trailer or field referring to `e8ec`, and the commit that split `e8ec` (`bacf86f…`,
recorded at `:148`) does not appear in `dkjk`'s history at all — `history` returned only the
commits whose `Canvas-Node:` trailer names `dkjk`.

**What is there is, again, only the prose.** The `--why` on that `insert` says *"This content
was the second sentence of e8ec until the replace one commit earlier"*, and `history` at `:250`
prints it. Remove that sentence from the `--why` and the newly minted node's history would
contain no trace of its origin whatsoever.

The same holds in the other direction: `history … e8ec` at `:230` shows two entries, and the
second one names no successor id — the writer described the second half as going "into its own
node" without naming `dkjk`, because at the time that `replace` ran the id did not yet exist.
That ordering is forced: the split's `replace` happens before the `insert` that mints the other
half, so the surviving node's reason *cannot* name the born id unless a later edit adds it.

## Does `--why` text appear in `history` output?

**Yes — in full, verbatim, as the body of every entry.** Every `history` record in the
transcript (`:230`, `:250`, `:266`, `:286`, `:306`, `:326`, `:342`) prints each edit as
`Canvas-Commit:` / `Canvas-Author:` / `<verb>: <reason>`, with the reason exactly as it was
typed, unwrapped and untruncated. So a convention of naming the other id inside `--why` **is**
readable back by a reader, and the command that reads it is **`bin/canvas history <ledger_id>
<node-id>` and only that command**:

- `read` (`:375`) prints the document and no reasons at all.
- `history` requires the id as a positional; it does not search reasons and does not accept a
  pattern.

The practical consequence observed here: a reader holding the surviving id `oskz` can run
`history` on it (`:266`), read `dwqu` out of the reason text, and then run `history` on `dwqu`
(`:286`) and get the stranded node's whole life. That two-hop path worked in this exercise.
It worked because both reasons happened to name the other id in prose; nothing in the tool
required it and nothing in the tool would have reported its absence.

## The refusal, and the trap

**The bare back-reference was refused.** The first `remove` attempt at `:187` used
`--why "Merged upward; reason as above."` — the reason a writer reaches for when the `remove`'s
justification is the `replace`'s. It exited **2** with *"--why must say what this node is for,
not where it sits; if the reason is another node's, name that node's id and say what differs
here."*, plus `Canvas-Node: dwqu`, two `Canvas-About:` lines, a `Canvas-Next:` and
`Canvas-Exit: 2 — the tool or its environment is wrong; do not touch the canvas`. The appendix
at `:407` shows the store holds 15 commits for 25 invocations, with no commit for that attempt:
nothing was written, committed or minted, as the refusal said.

**A reason that survives the `node-identity.md:302-304` trap was writable.** The task said to
say so if it was not; it was. The accepted `remove` at `:204` does not say "we merged this
section" — it says what was true of *this particular node*: its one clause now stands word for
word inside `oskz`, so keeping it would leave the canvas asserting the same thing twice.

One thing that fell out of writing it, stated as observation rather than as argument: the
sentence that made the reason a reason for removing *this node* is the same sentence that
carries the lineage pointer. Naming `oskz` was not an extra clause bolted on for lineage's
sake — it was the evidence the reason needed in order to be about this node at all. That is
what happened in this one case, where the merge worked by duplicating the losing node's content
into the survivor first. Nothing here establishes that it holds for merges of a different
shape.

Note on what the refusal at `:187` does and does not demonstrate: it shows that this one
phrase, with no four-character id in it, is refused. The exercise ran no invocation testing an
operation-shaped reason that contains none of the guard's phrases, so nothing here says what
the tool does with *"we deleted this section"*. That bar is the document's, not the guard's.

## `move`

**Run once, on a populated container, at exit 0.** `move … sdtf --after g4fe` at `:217` moved
section `sdtf`, which held one child `ps58`, from after `xkq2` to before it. The final read at
`:375` shows `sdtf` first among the sections with `ps58` still inside it.

- **The id is unchanged and one `history` query spans the move.** `history … sdtf` at `:306`
  prints two entries — the original `insert` and the `move` — under one `Canvas-Node: sdtf`
  header, `v="2"` in the final read.
- **The carried child paid nothing and records nothing.** `history … ps58` at `:326` prints one
  entry, its own `insert`, and `v="1"` in the final read at `:375`. No commit names `ps58` for
  the move. The child's own history contains no indication that it changed position.

## Contrast: a node that was only ever inserted

`history … ffra` at `:342` exits 0 and prints exactly one entry, its `insert`, `v="1"`. Read
against `:230`, `:266` and `:306` — all of which print two entries for nodes that were edited
once after birth — the output shape is identical; the count of entries is the only difference.
A reader cannot tell from the shape of a `history` response whether the node is live, was
edited, or was removed. Only the presence of a `remove:` entry (`:286`) says the last.
