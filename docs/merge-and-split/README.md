# The merge-and-split exercise

The evidence `node-identity.md` sections 7 and 8 were decided against. Those
sections rule on the two items that document's closing section left open —
what a merge and a split do to the lineage of each side, and whether a
restructure may ever be atomic — and the todo that asked for them required the
ruling be made against what `bin/canvas` actually prints rather than against a
prediction of it. This directory is that "actually".

It exists because the corpus could not answer the question. The 76 invocations
behind `../drive-by-hand/canvas-transcript.md` contain no `remove`, no `move`,
and `history` was never run once in them, so nothing recorded anywhere in this
repository said what a stranded id answers after a merge retires it.

- **`canvas-transcript.md`** — every `bin/canvas` invocation of the exercise,
  verbatim, with its exit code and its complete output, in the order it was
  run. Twenty-five invocations: a canvas built from nothing, a real split, a
  real merge, a `move` of a populated container, and eight `history` runs.
  Both refusals are in it and neither was edited out. It follows the shape
  `../drive-by-hand/canvas-transcript.md` set.
- **`FINDINGS.md`** — what that transcript shows, claim by claim, each one
  naming the invocation that supports it by the line its record starts at.
  It reports and does not rule; the ruling is `node-identity.md` §7 and §8.

**The four ids to read it by**: `e8ec` kept its id through the split, `dkjk`
was born in it, `oskz` survived the merge, and `dwqu` is the id the merge
retired. `bin/canvas history` for the surviving id and for the stranded one —
the two outputs the todo named explicitly — are at `canvas-transcript.md:266`
and `:286`. The stranded one exits `0` and prints the node's whole life.

**Where it was run.** Against a scratch store inside the run directory that
produced it, never a live workspace, with the clone left on `main` at
`798ee8c2e3372099646dd2ff044f58b44649bf1d` and its working tree clean: nothing
in this repository was edited to make the exercise. The two files were copied
here unchanged except for one filename each — they referred to each other by
the names they had in the run directory, and now refer to each other by the
names they have here.
