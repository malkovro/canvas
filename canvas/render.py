"""The renderer: one canvas in, one projection out — a page, or a comment.

`engineering-spec.md` section *The substrate* says what this is and what it is
not: *"The renderer is a separate, dumb, one-way function: XML in, HTML out. It
owns every presentation decision. Nothing in the canvas file is about how it
looks. Nobody edits the HTML; it is a projection and it is regenerated."*

So this module is a reader of the store and nothing else. It calls
`store.read`, which writes nothing, commits nothing and does not initialise a
repository, and it returns a string. There is no output path argument, no
template file, no configuration and no flag that could make it write to a
canvas: the one thing it can do with what it read is hand it back.

**Every presentation decision is here**, and every one of them is this module's
to change. The vocabulary gained no element, no attribute and no configuration
file to serve this renderer, which is the constraint the closed vocabulary
exists for. What this module reads out of a canvas is what was already in one:
eleven element names, `title`, `href`, `payload`, `id`, `v`, and the one state
`node-state.md` settled — `answered` on `<question>`.

Two questions this renderer had to settle rather than inherit, both argued in
`rendering.md` at the top of this repository:

- **`<figure>` is drawn in the standalone page.** Schema 2 distinguishes the
  backward-compatible Canvas Diagram 1 default, explicit Mermaid source and the
  closed inline-SVG escape hatch. Schema-1 textual figures remain readable and
  use the same total diagram renderer. Mermaid is progressive enhancement from
  one exact renderer-owned CDN module; escaped source remains the no-JavaScript,
  network-failure and syntax-error fallback. The comment projection cannot
  display the picture and labels an honest fenced source/markup fallback instead.
- **The index names every `<question>` in the document, answered ones
  included, and says of each which it is.** An answered question is quiet in
  the index and quiet in the body — it keeps its marker and its entry, and
  loses the loudness. `node-state.md` left the presentation of an answered
  question free and required only that an open one be loud; this is the side
  taken, and `rendering.md` §2 says why omission was not.

A third, ruled elsewhere and in the same way — `problem-and-solution-space.md`
at the top level of this repository, settled 2026-09-28:

- **A node that crossed between a canvas's spaces carries exactly one reason,
  and no other node carries any.** A node has crossed when a `move` naming it
  changed which `<section>` it sits in, with *no section* counted as a value;
  its crossing is the latest such move, and what is shown is that move's
  `--why`, verbatim, beside the full sha of the commit it came from. A node
  that never crossed carries none, a node that crossed three times carries
  one, and a canvas in which nothing has crossed — which is every canvas in
  the live store today — renders with no reason in it at all. Showing every
  reason on every node would make the page the transcript
  `product-spec.md`'s *What it is not* refuses, and it would grow with the log
  while the document stayed the same size.

  **Nothing was added to the document to serve this.** There is no `space=`,
  no `status=` and no twelfth element: the structure says where a node is, the
  `--why` says why it is there, and `store.crossings` derives the move from the
  stored history. Where the reason sits on the node, what introduces it and
  how it looks are this module's, on `engineering-spec.md`'s *The substrate*'s
  terms; *which* reasons appear is not, and both projections make the same
  claim.

The page carries the sha it was rendered from, in its own header, because a
rendered page outlives the canvas it came from. A reader who has one has to be
able to tell it from the canvas as it stands now, and the sha is the only thing
that answers that.

**Two projections, one walk of the document.** `page` is the standalone HTML
document. `comment` is the same canvas as the block-level Markdown a Basecamp
comment actually renders, for the ledger row that rewrites its own live comment
in place. Both are reached through `render`, both come off one `store.read`
and one `store.crossings`, both take their sha from the same place, and the
three claims `rendering.md` §3 says are not free — every `<question>` id in the
index, only `<question>` ids in it, a marker on every `<question>` node — are
asserted against both.

**Markdown is repaired per form, and the two forms differ because their
transports do.** A node's character data is Markdown. The page renders it —
`_prose` escapes the text and then emits `<strong>`, `<em>` and `<code>` for
the inline Markdown the live store actually holds — following the convention
`_unfold_markdown_tables` in `orchestrator/basecamp.py` sets for this system:
text it did not write is repaired into what the destination renders. The
comment does not, and must not: its transport *is* a Markdown converter, so
the repair is already performed downstream, and a `<strong>` in that body
would trip the rule below and cost the whole comment its formatting.

`engineering-spec.md`'s *Projections* used to say the HTML page was
*"pasteable into a Basecamp comment"*. It is not, and that sentence has been
corrected there. Two facts about the transport kill it, and they compound: the
`basecamp` CLI converts a comment body from Markdown to HTML only when the body
holds no HTML at all, so one tag turns the conversion off for the *whole*
comment — including the ledger row's own status blocks around it; and Basecamp
then drops what its rich text does not accept, which is the doctype, `<html>`,
`<head>`, `<style>`, `<header>`, `<nav>` and `<figure>` — most of the page, and
every class the page's meaning is carried in. So the comment projection emits
**no raw HTML tag of any kind**: no `<` character reaches its output, and a
`<` in a canvas is written `&lt;`. That is the one rule everything below bends
to.
"""

import re

from xml.etree import ElementTree as ET

from canvas import diagram, store, svg


#: The one network dependency a standalone page may load, and only when the
#: document contains an explicit Mermaid figure. The version is exact rather
#: than a tag or range; canvas data never supplies or modifies this URL.
MERMAID_MODULE_URL = (
    "https://cdn.jsdelivr.net/npm/mermaid@11.17.2/dist/mermaid.esm.min.mjs"
)

#: Mermaid renders in the page, and some diagram forms can ask its temporary
#: render tree to fetch an image before the returned SVG can be inspected. The
#: page therefore closes every resource channel except the one exact module
#: origin the renderer owns. The document supplies none of these directives.
MERMAID_CSP = (
    "default-src 'none'; "
    "script-src 'nonce-canvas-mermaid-renderer' https://cdn.jsdelivr.net; "
    "style-src 'unsafe-inline'; img-src 'none'; font-src 'none'; "
    "connect-src 'none'; media-src 'none'; object-src 'none'; "
    "frame-src 'none'; base-uri 'none'; form-action 'none'"
)

#: Renderer-owned progressive enhancement. Figure source reaches this code only
#: through textContent; it is never interpolated into this executable string.
#: Mermaid's strict mode is one input to the boundary, not the boundary itself:
#: the returned XML is parsed in a detached document, checked against a static
#: SVG allowlist, and imported only after it passes. The page CSP separately
#: prevents Mermaid's temporary render tree from fetching a URL first.
MERMAID_BOOTSTRAP = """<script type="module" nonce="canvas-mermaid-renderer">
import mermaid from "%s";

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const SAFE_SVG_ELEMENTS = new Set([
  "svg", "g", "defs", "style", "title", "desc", "symbol", "marker", "path", "rect",
  "line", "polyline", "polygon", "circle", "ellipse", "text", "tspan",
  "clippath", "mask", "lineargradient", "radialgradient", "stop", "filter",
  "fedropshadow", "fegaussianblur", "feoffset", "feflood", "fecomposite",
  "femerge", "femergenode"
]);
const SAFE_SVG_ATTRIBUTES = new Set([
  "xmlns", "id", "class", "role", "aria-label", "aria-roledescription",
  "data-edge", "data-et", "data-from", "data-id", "data-look", "data-points",
  "data-to", "data-type", "name",
  "tabindex", "viewbox", "preserveaspectratio", "width", "height", "x", "y",
  "x1", "x2", "y1", "y2", "cx", "cy", "r", "rx", "ry", "d", "points",
  "transform", "opacity", "fill", "fill-opacity", "fill-rule", "clip-rule", "stroke",
  "stroke-width", "stroke-opacity", "stroke-linecap", "stroke-linejoin",
  "stroke-dasharray", "stroke-dashoffset", "stroke-miterlimit", "font-family",
  "font-size", "font-style", "font-weight", "text-anchor", "dominant-baseline",
  "alignment-baseline", "marker-start", "marker-mid", "marker-end", "markerwidth",
  "markerheight", "markerunits", "refx", "refy", "orient", "offset",
  "stop-color", "stop-opacity", "gradientunits", "gradienttransform",
  "spreadmethod", "fx", "fy", "fr", "filterunits", "primitiveunits", "in",
  "in2", "result", "stddeviation", "dx", "dy", "flood-color", "flood-opacity",
  "operator", "k1", "k2", "k3", "k4", "values", "type", "style"
]);

function hasExternalUrl(value) {
  const urls = value.match(/url\\s*\\([^)]*\\)/gi) || [];
  for (const url of urls) {
    const target = url.slice(url.indexOf("(") + 1, -1).trim().replace(/^(['"])(.*)\\1$/, "$2");
    if (!/^#[A-Za-z_][A-Za-z0-9_.:-]*$/.test(target)) return true;
  }
  const withoutInternalUrls = value.replace(/url\\s*\\([^)]*\\)/gi, "");
  return /url\\s*\\(|@import|@font-face|(?:-webkit-)?image-set\\s*\\(|attr\\s*\\(|javascript:|data:|https?:|\\/\\//i.test(withoutInternalUrls);
}

function sourceMayCreateUrl(source) {
  return /(?:https?:|javascript:|data:|file:|blob:|\\/\\/|url\\s*\\(|(?:^|\\s)click\\s+|(?:href|src|img|image|link|url)\\s*[:=]|<\\s*(?:a|img)\\b)/im.test(source);
}

function sanitizedMermaidSvg(markup) {
  const parsed = new DOMParser().parseFromString(markup, "image/svg+xml");
  const svg = parsed.documentElement;
  if (svg.localName !== "svg" || svg.namespaceURI !== SVG_NAMESPACE || parsed.querySelector("parsererror")) {
    throw new Error("Mermaid returned malformed SVG");
  }
  for (const element of [svg, ...svg.querySelectorAll("*")]) {
    if (element.namespaceURI !== SVG_NAMESPACE || !SAFE_SVG_ELEMENTS.has(element.localName.toLowerCase())) {
      throw new Error(`Mermaid returned unsafe element: ${element.localName}`);
    }
    if (element.localName.toLowerCase() === "style" && hasExternalUrl(element.textContent)) {
      throw new Error("Mermaid returned URL-bearing CSS");
    }
    for (const attribute of element.attributes) {
      const name = attribute.name.toLowerCase();
      if (!SAFE_SVG_ATTRIBUTES.has(name) || name === "href" || name.endsWith(":href")) {
        throw new Error(`Mermaid returned unsafe attribute: ${attribute.name}`);
      }
      if (name === "xmlns") {
        if (attribute.value !== SVG_NAMESPACE) throw new Error("Mermaid returned a foreign namespace");
      } else if (hasExternalUrl(attribute.value)) {
        throw new Error(`Mermaid returned URL-bearing attribute: ${attribute.name}`);
      }
    }
  }
  return document.importNode(svg, true);
}

const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  secure: ["securityLevel", "startOnLoad", "secure", "theme", "themeVariables", "htmlLabels", "flowchart"],
  theme: "base",
  themeVariables: dark ? {
    background: "#201c19", primaryColor: "#201c19", primaryTextColor: "#efe9e4",
    primaryBorderColor: "#70a8bb", lineColor: "#70a8bb", secondaryColor: "#2b231e",
    tertiaryColor: "#181513", fontFamily: "system-ui, sans-serif"
  } : {
    background: "#f4efe8", primaryColor: "#f4efe8", primaryTextColor: "#1d1a17",
    primaryBorderColor: "#2b5f73", lineColor: "#2b5f73", secondaryColor: "#fbf0e6",
    tertiaryColor: "#fdfcfa", fontFamily: "system-ui, sans-serif"
  },
  htmlLabels: false,
  flowchart: { htmlLabels: false }
});

for (const [index, source] of document.querySelectorAll("[data-mermaid-source]").entries()) {
  try {
    if (sourceMayCreateUrl(source.textContent)) {
      throw new Error("Mermaid source may create a URL-bearing result");
    }
    const result = await mermaid.render(`canvas-mermaid-${index}`, source.textContent);
    const drawing = document.createElement("div");
    drawing.className = "mermaid-drawing";
    drawing.setAttribute("role", "img");
    drawing.setAttribute("aria-label", "Mermaid diagram");
    drawing.append(sanitizedMermaidSvg(result.svg));
    source.before(drawing);
    source.hidden = true;
  } catch (error) {
    source.closest(".figure").classList.add("mermaid-failed");
  }
}
</script>""" % MERMAID_MODULE_URL


#: The one state a canvas carries, and the only attribute this module reads
#: that is not identity or structure. `node-state.md`: absence means open,
#: `true` is the only legal value, and `<question>` is the only element it may
#: appear on. Nothing here restates any other part of the vocabulary — what a
#: node may be is `schema/canvas.rng`'s business and the document reaching this
#: module has already been through the validator.
ANSWERED = "answered"

#: How each state is named in the page, in the index and on the node. One
#: string for one state, so the marker a reader sees beside a question and the
#: word beside its entry in the index cannot drift apart.
OPEN_LABEL = "Open question"
ANSWERED_LABEL = "Answered question"

#: What a crossed node's one line is introduced by, in both projections. One
#: string for the same reason the two above are one each: a reader who has the
#: page and then the comment must not have to work out whether the two are
#: making the same claim. The words say the event and not the space, because
#: which section is the problem space and which is the solution space is read
#: off the `title` by the person and by nobody else — this module never looks
#: at those characters, and `problem-and-solution-space.md` section 1 is why.
CROSSING_LABEL = "Carried across"

#: The two projections this module emits, named once. `PAGE` is the default
#: everywhere — every existing invocation of `bin/canvas render` predates the
#: second form and must keep getting the page it asked for.
PAGE = "page"
COMMENT = "comment"
FORMS = (PAGE, COMMENT)

#: What joins the cells of one table row once the row is a bullet, and what
#: separates a node's marker from its text. The em dash with spaces around it,
#: which is what the ledger row's own comment already uses to separate a thing
#: from what is said about it.
JOIN = " — "

#: What the index is called, and what it says when there is nothing in it.
#: Named once because both projections carry the index and a reader who has one
#: and then the other must not have to work out whether they are the same
#: claim.
INDEX_HEADING = "Open questions"
EMPTY_INDEX = (
    "No questions in this canvas — nothing is open and nothing has been "
    "asked."
)

#: `<section>` nests one level, so there are exactly two heading levels under
#: the page's own `<h1>`. A third level of section is invalid and never
#: arrives; the fallback keeps this a total function rather than an assertion
#: about a document the validator has already accepted.
HEADINGS = ["h2", "h3", "h4"]

#: The palette, the type scale and the measure — every colour, size and
#: spacing in the stylesheet below is one of these, so the dark scheme is one
#: block of overrides and there is no second copy of the design to keep in
#: step. The names are the design vocabulary this page shares with the tab
#: that frames it; the values are the only place either is written down.
#:
#: The document this is designed for is prose. Counted over
#: `state/canvas/*.xml` on 2026-09-28, the node census across the 71 canvases
#: of the live store is text 266, question 8, figure 3, section 2, list 1,
#: link 1 — a prose document with a handful of figures in it. So the
#: reading colour, the measure and the leading are what the page is judged on,
#: and the eleven elements are told apart by typographic role and one hairline
#: rather than by eleven borders competing for the same attention. Two of them
#: get more than that and both earn it: `<figure>` is the one genuinely
#: graphical element and gets a panel of its own, and `<question>` is the one
#: that must stay findable and gets the only saturated colour on the page.
#:
#: Styles stay inline. An explicit Mermaid figure adds the one pinned,
#: renderer-owned module described above; every other page still has nothing
#: external to fetch.
STYLE = """
    /* --- tokens: the palette, the type scale, the measure ---------------- */
    :root {
      color-scheme: light dark;

      /* Surfaces, warm rather than neutral, so the page sits in the same
         family as the dark chrome that frames it in the Canvas tab. */
      --paper:       #fdfcfa;
      --paper-sunk:  #f6f2ec;
      --panel:       #f4efe8;
      --rule:        #e3ddd4;
      --rule-firm:   #cbc3b8;

      /* Three weights of ink and no opacity: a dimmed element is a colour,
         because opacity dims the background through it as well and stacks
         unpredictably when two dim things nest. */
      --ink:         #1d1a17;
      --ink-soft:    #554e47;
      --ink-faint:   #756c64;

      /* The one saturated hue, and it means one thing: an open question. */
      --accent:      #b4530f;
      --accent-soft: #fbf0e6;
      --accent-rule: #e6a874;

      /* The figure's ink. Canvas Diagram 1 draws in `currentColor`, so
         setting `color` on the drawing is the whole of how a figure is
         coloured, and nothing in `canvas/diagram.py` had to learn a palette. */
      --diagram:     #2b5f73;

      --link:        #0b5c86;

      --font-prose: -apple-system, "Segoe UI", system-ui, sans-serif;
      --font-mono:  ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;

      /* A 1.2 modular scale on a 17px body. */
      --text-xs:    0.74rem;
      --text-sm:    0.885rem;
      --text-base:  1.0625rem;
      --text-lg:    1.275rem;
      --text-xl:    1.53rem;
      --text-2xl:   1.836rem;

      --leading-body:  1.65;
      --leading-tight: 1.2;

      /* Prose is held to a measure; a figure and a table are not, because a
         diagram and a grid are read across rather than down. */
      --measure: 34rem;
      --page:    46rem;
    }

    @media (prefers-color-scheme: dark) {
      :root {
        --paper:       #181513;
        --paper-sunk:  #1f1b18;
        --panel:       #201c19;
        --rule:        #302a25;
        --rule-firm:   #473f38;

        --ink:         #efe9e4;
        --ink-soft:    #b6ada5;
        --ink-faint:   #8b827b;

        --accent:      #f0a35c;
        --accent-soft: #2a1d12;
        --accent-rule: #8a5a2c;

        --diagram:     #8fc4d8;

        --link:        #79bde4;
      }
    }

    /* --- the page, and <canvas> itself ----------------------------------- */
    body { margin: 0 auto; max-width: var(--page); padding: 3rem 1.5rem 6rem;
           background: var(--paper); color: var(--ink);
           font-family: var(--font-prose); font-size: var(--text-base);
           line-height: var(--leading-body);
           -webkit-text-size-adjust: 100%; }
    code { font-family: var(--font-mono); font-size: 0.9em; }
    strong { font-weight: 650; color: var(--ink); }

    /* --- the header ------------------------------------------------------ */
    header { margin: 0 0 2rem; }
    h1 { font-size: var(--text-2xl); line-height: var(--leading-tight);
         letter-spacing: -.012em; margin: 0 0 .4rem; }
    .rendered-from { max-width: var(--measure); margin: 0;
                     font-size: var(--text-xs); line-height: 1.5;
                     color: var(--ink-faint); }
    .rendered-from code { font-size: var(--text-xs); word-break: break-all;
                          color: var(--ink-soft); }

    /* --- the index of questions ------------------------------------------ */
    .question-index { margin: 1.5rem 0 2.75rem; padding: .85rem 1.1rem;
                      background: var(--panel);
                      border: 1px solid var(--rule);
                      border-left: 3px solid var(--accent);
                      border-radius: .1rem .4rem .4rem .1rem; }
    .question-index h2 { margin: 0 0 .5rem; border: 0; padding: 0;
                         font-size: var(--text-xs); font-weight: 700;
                         letter-spacing: .1em; text-transform: uppercase;
                         color: var(--ink-faint); }
    .question-index ol { margin: 0; padding-left: 1.3rem;
                         font-size: var(--text-sm); }
    .question-index li { margin: .35rem 0; }
    .question-index li::marker { color: var(--ink-faint); }
    .question-index li.open { color: var(--ink); }
    .question-index li.open a { color: var(--accent);
                                text-decoration-color: var(--accent-rule); }
    .question-index li.answered { color: var(--ink-faint); }
    .question-index li.answered a { color: var(--ink-soft); }

    /* An index of nothing is not a section. 66 of the 71 canvases in the live
       store hold no <question> at all, so the loudest thing on almost every
       page was a box announcing its own emptiness. The claim still stands and
       is still made in the same place and the same order — the nav is here,
       before the document, and it still says in words that nothing is open —
       but it is set at the weight of the provenance line above it rather than
       at the weight of a section, and it loses the panel, the rule and the
       heading. `rendering.md` §2 records the decision and its reason. */
    .question-index[data-questions="none"] { margin: .3rem 0 2.5rem;
                                             padding: 0; background: none;
                                             border: 0; border-radius: 0; }
    .question-index[data-questions="none"] .empty {
        max-width: var(--measure); margin: 0; font-size: var(--text-xs);
        font-style: normal; color: var(--ink-faint); }

    /* --- <section>: a heading, and a rule that says a part has started ---- */
    .section { margin: 2.75rem 0; }
    .section > h2 { margin: 0 0 1rem; padding-top: .8rem;
                    border-top: 1px solid var(--rule-firm);
                    font-size: var(--text-xl); line-height: var(--leading-tight);
                    letter-spacing: -.008em; }
    .section .section { margin: 2rem 0; }
    .section > h3 { margin: 0 0 .75rem; font-size: var(--text-lg);
                    line-height: var(--leading-tight); color: var(--ink-soft); }

    /* --- <text>: the document, and what everything else is measured by ---- */
    .text { max-width: var(--measure); margin: 0 0 1.1rem; }

    /* --- <list> and <item> ----------------------------------------------- */
    .list { max-width: var(--measure); margin: 1.1rem 0; padding-left: 1.2rem;
            list-style: square; }
    .item { margin: .4rem 0; padding-left: .2rem; }
    .item::marker { color: var(--accent-rule); }

    /* --- <table>, <row> and <cell>: rules where a grid needs them and
           nowhere else. A tint tells one row from the next, a hairline tells
           one cell from the next, and the table has no outer box. ---------- */
    /* No width: a two-column table stretched to the page is a grid pretending
       to be a layout. It is as wide as it needs to be and no wider. */
    .table { max-width: 100%; margin: 1.75rem 0; border-collapse: collapse;
             font-size: var(--text-sm); line-height: 1.45;
             border-top: 1px solid var(--rule-firm);
             border-bottom: 1px solid var(--rule-firm); }
    .row:nth-child(even) { background: var(--paper-sunk); }
    .row + .row .cell { border-top: 1px solid var(--rule); }
    .cell { padding: .5rem .75rem; vertical-align: top;
            font-variant-numeric: tabular-nums; }
    .cell + .cell { border-left: 1px solid var(--rule); }
    tr.crossing-row .crossing { border-top: 1px solid var(--rule); }

    /* --- <figure>: the one genuinely graphical element ------------------- */
    .figure { margin: 2rem 0; padding: 1.25rem 1.25rem 1rem;
              background: var(--panel); border: 1px solid var(--rule);
              border-radius: .5rem; color: var(--diagram); }
    .figure-drawing { display: block; width: 100%; height: auto;
                      overflow: visible; }
    .mermaid-source { margin: 0; padding: 1rem; overflow-x: auto;
                      border: 1px solid var(--rule-firm); border-radius: .3rem;
                      background: var(--paper-sunk); color: var(--ink);
                      font: var(--text-sm)/1.5 var(--font-mono);
                      white-space: pre-wrap; overflow-wrap: anywhere; }
    .mermaid-drawing { width: 100%; overflow-x: auto; text-align: center; }
    .mermaid-drawing svg { display: block; max-width: 100%; height: auto;
                           margin: 0 auto; }
    .mermaid-failed .mermaid-source::before {
        content: "Diagram unavailable — Mermaid source follows";
        display: block; margin-bottom: .75rem; color: var(--ink-faint);
        font: 700 var(--text-xs)/1.4 var(--font-prose);
        letter-spacing: .05em; text-transform: uppercase; }
    figcaption { margin: .9rem 0 0; padding-top: .7rem;
                 border-top: 1px solid var(--rule);
                 font-size: var(--text-xs); line-height: 1.5;
                 color: var(--ink-faint); }
    figcaption code { color: var(--ink-soft); }

    /* --- <link> ---------------------------------------------------------- */
    a { color: var(--link); text-decoration-thickness: 1px;
        text-underline-offset: .18em;
        text-decoration-color: var(--accent-rule); }
    .link { max-width: var(--measure); margin: 1.1rem 0; }

    /* --- <question>: the one element that has to stay findable ----------- */
    .question { max-width: var(--measure); margin: 1.75rem 0;
                padding: .8rem 1.1rem;
                border-left: 3px solid var(--accent);
                border-radius: .1rem .4rem .4rem .1rem;
                background: var(--accent-soft); }
    .question-marker { display: block; margin-bottom: .25rem;
                       font-size: var(--text-xs); font-weight: 700;
                       letter-spacing: .1em; text-transform: uppercase;
                       color: var(--accent); }
    .question-text { margin: 0; }
    /* An answered question keeps its marker and its entry and loses its
       loudness — `rendering.md` §2. It gives up the wash and the saturated
       rule, not the shape, so it is still recognisably the same kind of
       thing. */
    .question.answered { background: none; color: var(--ink-soft);
                         border-left: 3px dotted var(--rule-firm); }
    .question.answered .question-marker { color: var(--ink-faint); }

    /* --- a node that crossed between the canvas's spaces ------------------ */
    .crossing { max-width: var(--measure); margin: .6rem 0 0;
                font-size: var(--text-sm); line-height: 1.5;
                color: var(--ink-soft); }
    .crossing-label { display: inline-block; margin-right: .35rem;
                      font-size: var(--text-xs); font-weight: 700;
                      letter-spacing: .1em; text-transform: uppercase;
                      color: var(--ink-faint); }
    .crossing-why { font-style: italic; }
    .crossing-sha { font-size: var(--text-xs); word-break: break-all;
                    color: var(--ink-faint); }

    .empty { color: var(--ink-faint); font-style: italic; }
"""



#: The inline Markdown a canvas really holds, and nothing else.
#:
#: Measured over the 71 canvases of the live store on 2026-09-28: 77 backtick
#: code spans, 4 `**bold**` runs and 2 `*emphasis*` runs, and no heading, no
#: Markdown link, no blockquote and no list marker in any node's character
#: data. This pattern is that census and not a Markdown grammar: a general
#: engine would be a second parser to keep, and every construct it added would
#: be a way for prose nobody meant as markup to come out rewritten.
#:
#: Two deliberate narrownesses, each paid for by something in the store. A code
#: span is matched first, so the `**Unrepaired finding:**` that a node quotes
#: *inside* backticks keeps its asterisks and only the one outside them goes
#: bold — which is what its author meant and what a Markdown reader would do.
#: And emphasis requires a non-space character at both ends, so the cron
#: expression `30 4 * * 1,4` on canvas `bc-10336256184` is not two asterisks
#: around a space; it is a cron expression, and it stays one.
INLINE_MARKDOWN = re.compile(
    r"`(?P<code>[^`\n]+)`"
    r"|\*\*(?P<strong>\S(?:[^*]*?\S)?)\*\*"
    r"|\*(?P<em>\S(?:[^*]*?\S)?)\*"
)

#: What each of those three becomes. The tags are this module's own, written
#: here and never taken from the canvas.
INLINE_TAGS = {"code": "code", "strong": "strong", "em": "em"}


def _text(value):
    """Character data, escaped for HTML. `None` is the empty string."""
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _prose(value):
    """Character data as the inline Markdown it is, repaired for the page.

    A `<text>` node's content is Markdown — that is what every agent and every
    person writing to a canvas types — and the page had no Markdown layer at
    all, so `**Unrepaired finding:**` on canvas
    `bc-10333741223-review-clean-20260925-k` arrived as four literal asterisks
    where its author meant bold.

    **This follows the convention already set for this system's Markdown**, in
    `_unfold_markdown_tables` in `orchestrator/basecamp.py` in
    `malkovro/ledger-orchestrator`: *"the second repair this module performs on
    text it did not write"*. Text this system did not write is repaired into
    what the destination renders, rather than passed through and left to
    arrive wrong. The destination here is a browser, so the repair is to emit
    the tags the browser renders.

    **Escape first, format second, and never the other way round.** `_text`
    runs over the whole string before this pattern sees any of it, so a `<` a
    writer really typed is already `&lt;` and cannot become a tag: a `<text>`
    node holding `<script>alert(1)</script>` comes out inert, exactly as
    before. The only `<` characters in the result are the ones `INLINE_TAGS`
    put there, around text that has already been escaped. Nothing from the
    canvas is ever passed through as HTML.

    **Decided per form, and the `comment` form does not get this.** There the
    body is handed to a Markdown converter — Basecamp's, via the `basecamp`
    CLI — which performs this very repair itself, so `_comment_text` leaves
    `*` alone and must go on leaving it alone: the same bytes are a defect on
    the page and correct on the comment, because only one of the two
    transports reads Markdown. And the comment form could not do this even if
    it wanted to. Its one absolute rule is that no raw HTML tag of any kind
    and no `<` character at all reaches its output, because one tag turns the
    CLI's Markdown conversion off for the whole comment, including the ledger
    row's own status blocks around it. A `<strong>` emitted there would cost
    the comment the very formatting it was emitted to produce.
    """
    escaped = _text(value)

    def one(match):
        for group, tag in INLINE_TAGS.items():
            found = match.group(group)
            if found is not None:
                return "<%s>%s</%s>" % (tag, found, tag)
        return match.group(0)

    return INLINE_MARKDOWN.sub(one, escaped)


def _attribute(value):
    """An attribute value, escaped for HTML. Quoted with `"` everywhere here."""
    return _text(value).replace('"', "&quot;")


def _is_answered(node):
    return node.get(ANSWERED) == "true"


def _questions(root):
    """Every `<question>` in the document, in document order.

    Document order and not "open first", because the index is a map of the
    page and a map whose entries are in a different order from the thing it
    maps is a second document to keep in your head.
    """
    return list(root.iter("question"))


def _identity(node):
    """The `id` attribute the page gives a node: its canvas id, unchanged.

    Ids are unique across the whole store, so they are unique within one page
    by construction, and using them as the anchor is what lets the index link
    to a question and a reader link to a node from outside.
    """
    return ' id="%s"' % _attribute(node.get("id") or "")


def _question_index(questions):
    """The index the page opens with: every `<question>` id, and nothing else.

    Every question in the document, answered ones included. The entry for an
    answered one says `answered` and is quiet; the entry for an open one says
    `open` and is not. `rendering.md` §2 argues the inclusion: an index that
    silently dropped answered questions would be the one artifact in this
    system that cannot be checked against the document, and a reader could not
    tell "answered" from "never asked" — which is the failure
    `docs/drive-by-hand/FRICTION.md:109-110` recorded against a canvas that
    ended with no trace that anything had been asked.

    Nothing else is named here. No section, no text node, no link: the index
    is the question ledger and an id in it is a question's id.
    """
    if not questions:
        # The empty case, which is what 66 of the 71 canvases in the live
        # store render. Same block, same place, same sentence: the nav is
        # still here and still before the document, and it still says in
        # words that nothing is open. What it loses is the weight — the
        # heading and the panel go, and the one line is set at the size of
        # the provenance line above it. `data-questions` and not a second
        # class, because the class attribute is `question-index` exactly and
        # three tests find this block by that literal string.
        return [
            '<nav class="question-index" id="question-index" '
            'data-questions="none">',
            '<p class="empty">%s</p>' % EMPTY_INDEX,
            "</nav>",
        ]
    out = ['<nav class="question-index" id="question-index">']
    out.append("<h2>%s</h2>" % INDEX_HEADING)
    out.append("<ol>")
    for node in questions:
        answered = _is_answered(node)
        node_id = _attribute(node.get("id") or "")
        out.append(
            '<li class="%s" data-question="%s"><a href="#%s"><code>%s</code></a> '
            "— %s — %s</li>"
            % (
                "answered" if answered else "open",
                node_id,
                node_id,
                node_id,
                "answered" if answered else "open",
                _prose(node.text),
            )
        )
    out.append("</ol>")
    out.append("</nav>")
    return out


def _crossing_line(edit):
    """The reason that carried a node across, and the sha it came from.

    Verbatim, escaped for HTML and otherwise unaltered: no ellipsis, no first
    sentence, no summary. `problem-and-solution-space.md` section 4 argues it
    from `guidelines/canvas-why.md` in `malkovro/ledger-orchestrator` —
    *"Quote verbatim, or do not use quotation marks"* — and the cost of it, an
    uncapped four-hundred-word reason printed in full, is stated there and
    paid here.

    The sha is in full and is not optional. A reason on a page is a quotation
    from a commit message, and the sha is what makes it resolvable — `git show
    <sha>` in the canvas directory — by a reader who has a pasted page and
    nothing else. It is forty characters for the reason the page's own header
    is: an abbreviation stops being an identity key as the log grows.

    `_text` and not `_prose`, and that is the same decision said again: this
    is a quotation, and a quotation whose asterisks the page decided were
    emphasis is no longer verbatim. A node's own character data is prose the
    page renders; a `--why` is a commit message the page quotes.
    """
    return (
        '<span class="crossing-label">%s</span>%s'
        '<q class="crossing-why">%s</q>%s'
        '<code class="crossing-sha">%s</code>'
        % (CROSSING_LABEL, JOIN, _text(edit.reason), JOIN, _text(edit.sha))
    )


def _crossing(node, crossings):
    """The one line a node that crossed carries, or nothing at all.

    Exactly one per crossed node and none on any other: `crossings` holds a
    node's *latest* crossing and holds nothing for a node that never crossed,
    so the count is the dictionary's and not a decision taken here.

    A `<tr>` may hold only cells, so a crossed `<row>` gets its line in a row
    of its own spanning the columns of the row it is about. That is the only
    element that needs a shape of its own, and it is a shape and not a second
    claim: the label, the reason and the sha are `_crossing_line`'s in both.
    """
    edit = crossings.get(node.get("id"))
    if edit is None:
        return []
    if node.tag == "row":
        return [
            '<tr class="crossing-row"><td class="crossing" colspan="%d">%s</td></tr>'
            % (max(1, len(list(node))), _crossing_line(edit))
        ]
    return ['<p class="crossing">%s</p>' % _crossing_line(edit)]


def _question(node, crossings):
    """One `<question>`, with the marker of its own that every one carries.

    The marker is a word and not a colour, because the done condition is that
    every `<question>` node carries a marker of its own in the output and a
    colour is not something a reader of the HTML — or a test — can point at.
    An answered question keeps its marker and loses its loudness: that is the
    whole of the difference, and `node-state.md` left it free.
    """
    answered = _is_answered(node)
    return [
        '<div class="question %s"%s>' % (
            "answered" if answered else "open", _identity(node)
        ),
        '<span class="question-marker">%s</span>'
        % (ANSWERED_LABEL if answered else OPEN_LABEL),
        '<p class="question-text">%s</p>' % _prose(node.text),
    ] + _crossing(node, crossings) + [
        "</div>",
    ]


def _figure(node, crossings):
    """Draw one `<figure>` using its explicit schema-v2 payload distinction.

    No `payload` means repository-owned Canvas Diagram 1, including on old
    schema-v1 canvases. `payload="svg"` has already passed the closed validator
    and is parsed and reserialized rather than copied. `payload="mermaid"`
    remains escaped source in readable markup until the fixed module enhances
    it; syntax or network failures leave that source in place.
    """
    identity = node.get("id") or ""
    if node.get("payload") == "svg":
        drawing = svg.render(node.text or "", "inline SVG figure %s" % identity)
        caption = "inline SVG escape hatch, validated and rendered"
    elif node.get("payload") == "mermaid":
        drawing = '<pre class="mermaid-source" data-mermaid-source>%s</pre>' % _text(
            node.text or ""
        )
        caption = "Mermaid source, progressively enhanced by the standalone projection"
    else:
        drawing = diagram.render_text(node.text or "")
        caption = "Canvas Diagram 1 source, drawn by the standalone projection"
    return [
        '<figure class="figure"%s>' % _identity(node),
        drawing,
        "<figcaption>figure <code>%s</code> — %s</figcaption>"
        % (_attribute(identity), caption),
    ] + _crossing(node, crossings) + [
        "</figure>",
    ]


def _link(node, crossings):
    """One `<link>`: the label, or the target where there is no label yet.

    A pointer with an empty label is a legal intermediate state — one edit is
    one node, and the label arrives with the node — and rendering it as an
    empty anchor would make it unclickable at exactly the moment it is most
    useful.
    """
    href = node.get("href") or ""
    return [
        '<p class="link"><a%s href="%s">%s</a></p>'
        % (_identity(node), _attribute(href), _text(node.text) or _text(href))
    ] + _crossing(node, crossings)


def _node(node, depth, out, crossings):
    """One node and everything under it, appended to `out`.

    The eleven element names are the whole of what can arrive: the document
    has been through `canvas.validate` before it reaches here, so an element
    this does not know is not a case to handle but a canvas that could not
    exist. It is still rendered — as a paragraph carrying its text — rather
    than dropped, because a projection that silently loses a node is worse
    than one that shows it plainly.

    A node's character data is Markdown wherever it is prose — `<text>`,
    `<item>`, `<cell>`, `<question>` — and goes through `_prose`, which
    escapes it and then emits the tags for the inline Markdown a canvas
    really holds. What does not: a `<section>`'s `title` and a `<link>`'s
    label, which are labels rather than prose and whose fallback is a URL;
    a `<figure>`'s source, which is a diagram's own notation; and a crossing
    reason, which is a quotation.

    A node that crossed carries its one line here, beside itself, and every
    element gets it in the one position that is valid HTML for that element:
    inside the `<li>`, inside the `<td>`, inside the `<figure>`, and after the
    `<p>`, the `<ul>` and the `<table>`, which cannot hold it. Adjacency is
    what makes the line readable — the reason is about *this* node — and it is
    the whole of what varies: which reasons appear is
    `problem-and-solution-space.md`'s and identical in both projections.
    """
    tag = node.tag
    if tag == "section":
        heading = HEADINGS[min(depth, len(HEADINGS) - 1)]
        out.append('<section class="section"%s>' % _identity(node))
        out.append(
            "<%s>%s</%s>" % (heading, _text(node.get("title")), heading)
        )
        out.extend(_crossing(node, crossings))
        for child in node:
            _node(child, depth + 1, out, crossings)
        out.append("</section>")
    elif tag == "text":
        out.append('<p class="text"%s>%s</p>' % (_identity(node), _prose(node.text)))
        out.extend(_crossing(node, crossings))
    elif tag == "list":
        out.append('<ul class="list"%s>' % _identity(node))
        for child in node:
            _node(child, depth, out, crossings)
        out.append("</ul>")
        out.extend(_crossing(node, crossings))
    elif tag == "item":
        out.append('<li class="item"%s>%s%s</li>' % (
            _identity(node),
            _prose(node.text),
            "".join(_crossing(node, crossings)),
        ))
    elif tag == "table":
        out.append('<table class="table"%s><tbody>' % _identity(node))
        for child in node:
            _node(child, depth, out, crossings)
        out.append("</tbody></table>")
        out.extend(_crossing(node, crossings))
    elif tag == "row":
        out.append('<tr class="row"%s>' % _identity(node))
        for child in node:
            _node(child, depth, out, crossings)
        out.append("</tr>")
        out.extend(_crossing(node, crossings))
    elif tag == "cell":
        out.append('<td class="cell"%s>%s%s</td>' % (
            _identity(node),
            _prose(node.text),
            "".join(_crossing(node, crossings)),
        ))
    elif tag == "figure":
        out.extend(_figure(node, crossings))
    elif tag == "link":
        out.extend(_link(node, crossings))
    elif tag == "question":
        out.extend(_question(node, crossings))
    else:
        out.append('<p class="text"%s>%s</p>' % (_identity(node), _prose(node.text)))
        out.extend(_crossing(node, crossings))


def page(ledger_id, sha, root, crossings):
    """The whole page, as one string: a standalone HTML document.

    Standalone still means one generated HTML file with inline styling. An
    explicit Mermaid payload adds one exact, renderer-owned CDN module import;
    all source stays readable if JavaScript or that fetch is unavailable.

    The order is fixed and is the done condition's: the page opens with the
    index of questions, and the document follows it. The sha is above both,
    with the ledger id, because what a reader of a pasted page needs first is
    which canvas this is and which moment of it.

    `crossings` is `{node_id: Edit}` — every node that crossed between the
    canvas's sections, and the edit that carried it. It is not in the document
    and could not be: it is derived from the stored history by
    `store.crossings`, and what it costs is stated there.
    """
    questions = _questions(root)
    has_mermaid = any(
        node.tag == "figure" and node.get("payload") == "mermaid"
        for node in root.iter()
    )
    out = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
    ]
    if has_mermaid:
        out.append(
            '<meta http-equiv="Content-Security-Policy" content="%s">'
            % _attribute(MERMAID_CSP)
        )
    out.extend([
        "<title>Canvas: %s</title>" % _text(ledger_id),
        "<style>%s</style>" % STYLE,
        "</head>",
        "<body>",
        "<header>",
        "<h1>Canvas: %s</h1>" % _text(ledger_id),
        # The sha, in full. A rendered page outlives the canvas it came from —
        # it is pasted into a comment — and this line is the only thing that
        # tells it apart from the canvas as it stands now. Forty characters,
        # for the reason `read` hands out forty: an abbreviation is not an
        # identity key as the log grows.
        '<p class="rendered-from">Rendered from <code>%s</code> — a projection '
        "of the canvas at that commit, not the canvas. Never edited and never "
        "read back; re-render to see it as it stands now.</p>" % _text(sha),
        "</header>",
    ])
    out.extend(_question_index(questions))
    out.append("<main>")
    for child in root:
        _node(child, 0, out, crossings)
    out.append("</main>")
    if has_mermaid:
        out.append(MERMAID_BOOTSTRAP)
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out) + "\n"


# --- the comment projection --------------------------------------------------
#
# The second projection, and the one a ledger row carries. Its shape is not a
# taste decision: `orchestrator/basecamp.py` in `malkovro/ledger-orchestrator`
# records what a Basecamp comment body does with what it is handed, from
# observed failures with the todo and comment ids attached. The Markdown table
# extension is off, so a table is not parsed at all and leaks its own pipes as
# literal text. Hard wraps are off, so a single newline is a soft break and
# consecutive lines fold into one paragraph. Raw HTML is dropped rather than
# rendered — and worse, the CLI converts a body from Markdown *only* when the
# body holds no HTML, so one tag anywhere turns the conversion off for the whole
# comment, including the ledger row's own status blocks around this one.
#
# What is left is plain block-level Markdown: paragraphs and bullet lists,
# separated by blank lines. Every block below is one of those two, and no `<`
# reaches the output.


def _comment_text(value):
    """Character data, safe in a comment body. `None` is the empty string.

    Two characters and no more. `&` and `<` become entities — `&` first, so an
    `&lt;` a canvas really holds arrives as the four characters it is — because
    a `<` in the body is what costs the *whole* comment its formatting.

    Markdown's own active characters are left alone, deliberately. A `*` in a
    canvas turning into emphasis is a cosmetic drift in one node; a `<p>` in a
    canvas is the ledger row's status blocks arriving as literal asterisks.
    """
    return (value or "").replace("&", "&amp;").replace("<", "&lt;")


def _inline(value):
    """Character data for a block that is one line: a bullet, an index entry.

    Whitespace is folded here rather than left to the converter, because a
    newline inside a bullet is a lazy continuation of it — the one place a soft
    break changes what a reader sees rather than only how it is spelled.
    """
    return " ".join(_comment_text(value).split())


def _source(value):
    """A `<figure>`'s source, for the fenced block that keeps its shape.

    Escaped for `<` and nothing else. The CLI inspects the body and not the
    rendering, so a `<` inside a fence is still a tag as far as it is concerned
    — and an escaped one shows through to the reader as `&lt;`. That is the
    cost, it is paid only by a figure that holds a `<`, and it buys the one
    thing a diagram cannot do without: a fence is the only block-level Markdown
    that keeps its columns. `&` is left alone for the mirror reason — it costs
    the comment nothing and escaping it would show.
    """
    return (value or "").replace("<", "&lt;")


def _fence(source):
    """A fence long enough for this source: three backticks, or more.

    A figure whose source is itself fenced code would otherwise end the block
    early and spill the rest of the canvas into it.
    """
    longest = 0
    run = 0
    for character in source:
        run = run + 1 if character == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)


def _comment_index(questions):
    """The index, as the heading and the list under it. Two blocks, not one.

    The same claim the page makes and for the same reason `rendering.md` §2
    gives — and that reason is *about a comment reader*: they have the
    projection and not the canvas, so "here is every question this document
    has, and here is which ones are open" has to be something they can count.
    Every `<question>` is named, answered ones included, and nothing that is
    not a `<question>` is named at all.
    """
    if not questions:
        return ["**%s**" % INDEX_HEADING, EMPTY_INDEX]
    entries = []
    for node in questions:
        entries.append(
            "- `%s`%s%s%s%s"
            % (
                _inline(node.get("id")),
                JOIN,
                "answered" if _is_answered(node) else "open",
                JOIN,
                _inline(node.text),
            )
        )
    return ["**%s**" % INDEX_HEADING, "\n".join(entries)]


def _comment_question(node):
    """One `<question>`, with the marker of its own that every one carries.

    The marker is the same word the page prints, bolded so it is the first
    thing on the line, and the id is beside it so a reader can match a node to
    its entry in the index — the page links the two and a comment cannot.
    """
    text = _inline(node.text)
    return "**%s** `%s`%s" % (
        ANSWERED_LABEL if _is_answered(node) else OPEN_LABEL,
        _inline(node.get("id")),
        (JOIN + text) if text else "",
    )


def _comment_crossing(node, crossings):
    """The one block a node that crossed carries in a comment, or nothing.

    The same claim the page makes, in the projection that reaches a reader who
    has only this. `problem-and-solution-space.md` section 4 requires the bound
    to be identical across the two and leaves the drawing free, so this is a
    block of plain Markdown carrying the same three things: the label, the
    reason as it was written, and the full sha.

    The node's id is on the line and it is not decoration. A comment has no
    anchors, so a reader matching this line to the node it is about has nothing
    but the id — which is the reason `_comment_question` puts the id beside its
    marker, and the same one.
    """
    edit = crossings.get(node.get("id"))
    if edit is None:
        return []
    return [
        "**%s** `%s`%s%s%s`%s`"
        % (
            CROSSING_LABEL,
            _inline(node.get("id")),
            JOIN,
            _inline(edit.reason),
            JOIN,
            _inline(edit.sha),
        )
    ]


def _comment_row(node):
    """One `<row>` as one line: its cells, joined.

    Empty cells drop out rather than rendering as gaps — a trailing dash says
    there is a column here whose value is missing, which is a claim the table
    did not make. A row whose cells are all empty still gets a line, because a
    repair may not change how many rows there are.
    """
    cells = [_inline(cell.text) for cell in node if cell.tag == "cell"]
    return JOIN.join(cell for cell in cells if cell) or "—"


def _comment_table(node):
    """One `<table>`: a header line, then one bullet per row after it.

    Not a Markdown table, and not because a table would be ugly: the extension
    is off, so the pipes and dashes arrive as literal text. This is the same
    repair `orchestrator/basecamp.py`'s `_unfold_markdown_tables` performs on
    authored text, for the same recorded reason, and it is done here so that
    nothing downstream has to recognise a table to fix it.
    """
    rows = [child for child in node if child.tag == "row"]
    if not rows:
        return []
    blocks = [_comment_row(rows[0])]
    if len(rows) > 1:
        blocks.append("\n".join("- %s" % _comment_row(row) for row in rows[1:]))
    return blocks


def _comment_figure(node):
    """Represent a figure honestly where Basecamp cannot display the picture.

    Canvas Diagram 1, Mermaid source and entity-escaped SVG markup are each
    labelled and fenced. No literal less-than sign reaches the comment transport.
    """
    source = _source(node.text or "").strip("\n")
    fence = _fence(source)
    labels = {
        "svg": "inline SVG source",
        "mermaid": "Mermaid source",
    }
    label = "%s (picture available in the standalone HTML projection)" % labels.get(
        node.get("payload"), "Canvas Diagram 1 source"
    )
    return [
        "**%s**" % label,
        "%s\n%s\n%s" % (fence, source, fence),
        "figure `%s`%ssource fallback; Basecamp comments cannot display the picture"
        % (_inline(node.get("id")), JOIN),
    ]


def _comment_link(node):
    """One `<link>`: the label, or the target where there is no label yet."""
    href = node.get("href") or ""
    return "[%s](%s)" % (_inline(node.text) or _inline(href), _inline(href))


def _comment_node(node, out, crossings):
    """One node and everything under it, as blocks appended to `out`.

    Same walk as the page's, and the same rule at the end of it: an element
    this does not know is a canvas that could not exist — the validator has
    already accepted this document — and it is still rendered, as its text,
    because a projection that silently loses a node is worse than one that
    shows it plainly.

    What the comment cannot carry is the *depth* of a section: there are two
    heading levels on the page and there is one weight of bold here. The order
    of the blocks is the document's, so nothing is lost but the nesting, and
    the page is where a reader goes for that.

    A crossed node's line follows the block it is about. Two blocks of the
    document fold several nodes into one — a `<list>`'s items are one bullet
    block and a `<row>`'s cells are one line — so an item's or a cell's line
    comes after the folded block rather than inside it, and names its id. That
    is a position and not a second claim: every crossed node gets exactly one
    line here and every uncrossed one gets none, which is what the page says
    too.
    """
    tag = node.tag
    if tag == "section":
        title = _inline(node.get("title"))
        if title:
            out.append("**%s**" % title)
        out.extend(_comment_crossing(node, crossings))
        for child in node:
            _comment_node(child, out, crossings)
    elif tag == "list":
        items = ["- %s" % _inline(child.text) for child in node
                 if child.tag == "item"]
        if items:
            out.append("\n".join(items))
        out.extend(_comment_crossing(node, crossings))
        for child in node:
            if child.tag == "item":
                out.extend(_comment_crossing(child, crossings))
            else:
                _comment_node(child, out, crossings)
    elif tag == "item":
        out.append("- %s" % _inline(node.text))
        out.extend(_comment_crossing(node, crossings))
    elif tag == "table":
        out.extend(_comment_table(node))
        out.extend(_comment_crossing(node, crossings))
        for row in node:
            if row.tag != "row":
                continue
            out.extend(_comment_crossing(row, crossings))
            for cell in row:
                if cell.tag == "cell":
                    out.extend(_comment_crossing(cell, crossings))
    elif tag == "row":
        out.append(_comment_row(node))
        out.extend(_comment_crossing(node, crossings))
    elif tag == "figure":
        out.extend(_comment_figure(node))
        out.extend(_comment_crossing(node, crossings))
    elif tag == "link":
        out.append(_comment_link(node))
        out.extend(_comment_crossing(node, crossings))
    elif tag == "question":
        out.append(_comment_question(node))
        out.extend(_comment_crossing(node, crossings))
    else:
        out.append(_comment_text(node.text or "").strip())
        out.extend(_comment_crossing(node, crossings))


def comment(sha, root, crossings):
    """The whole canvas as one block of a Basecamp comment.

    The ledger row rewrites one comment in place on every transition and is
    deliberately the only author on that anchor, so this is not a comment: it
    is a block the row appends to its own, below everything it already says.
    It therefore opens by naming itself and the moment it is of, and it names
    the sha in full for the reason the page's header does — a projection
    outlives the canvas it came from, and the sha is the only thing that tells
    a reader which of the two they are holding.

    The order is the page's: the sha, then the index of questions, then the
    document. What a reader of the comment needs first is which canvas this is
    and which moment of it.

    `crossings` is the page's, unchanged and used for the same bound: exactly
    one reason per crossed node, none anywhere else. This reader has the
    comment and never the canvas, which is why the bound has to be the same
    one — `problem-and-solution-space.md` section 4 — and why a reason without
    its sha would be a sentence in quotation marks nobody could get back to.
    """
    blocks = [
        "**Canvas**%srendered from `%s`" % (JOIN, _inline(sha)),
        "A projection of the canvas at that commit, not the canvas. Never "
        "edited and never read back; re-render to see it as it stands now.",
    ]
    blocks.extend(_comment_index(_questions(root)))
    for child in root:
        _comment_node(child, blocks, crossings)
    # One blank line between blocks and never two: a block boundary is one
    # separator, and the same document has to render as the same bytes for an
    # edited-in-place comment to be diffable.
    return "\n\n".join(block for block in blocks if block.strip()) + "\n"


def render(ledger_id, form=PAGE):
    """One ledger row's canvas, as a projection of it. Writes nothing.

    A read, on exactly `read`'s terms: it goes through `store.read`, which
    writes no file, makes no commit and does not initialise a repository, and
    it works on a frozen canvas like every other verb.

    **An invalid stored canvas is refused, at exit 1, with the diagnostics.**
    That is the one place this differs from `read`, and deliberately: `read`
    prints an invalid document because refusing to show it would make it
    unrepairable, and that reason is already served — `bin/canvas read` is
    right there and is the command a repair is made against. A *projection* of
    a document that breaks the grammar is a page asserting something about a
    canvas that does not exist, and it carries a sha, so it is exactly the
    artifact somebody pastes into a comment.

    `form` picks which projection: the standalone HTML page (the default, and
    what every caller that names no form gets), or the block-level Markdown a
    Basecamp comment renders. It is not a different read — one `store.read`,
    one `store.crossings`, one document, one sha, walked twice — and it is not
    a way to write: there
    is nothing this can be set to that puts a byte anywhere.
    """
    # No selector and no provenance: a projection is of the whole document,
    # and the header a read composes is for a caller that is about to write.
    sha, body, problems, _ = store.read(ledger_id)
    if problems:
        path = store.canvas_path(store.canvas_directory(), ledger_id)
        raise store.Refusal(
            "the canvas for %s is invalid, so there is nothing to render: a "
            "rendered page is a projection, and a projection of a document "
            "that breaks the grammar would assert a canvas that does not "
            "exist. Nothing was written" % ledger_id,
            "read it with `bin/canvas read %s`, which prints the document and "
            "these diagnostics together, and repair the node each one names "
            "with `bin/canvas replace %s <node-id> --why \"<why>\"`, one node "
            "at a time; then re-run `bin/canvas render %s`"
            % (ledger_id, ledger_id, ledger_id),
            about=["ledger id %s" % ledger_id, "canvas %s" % path],
            details=problems,
        )
    root = ET.fromstring(body)
    # The second read, and the one that widens this module's input from a
    # document to a document plus a walk of the log. It is still a read —
    # `store.crossings` writes nothing and initialises nothing — and it is
    # done once for both projections, so the two cannot disagree about which
    # nodes crossed.
    crossings = store.crossings(ledger_id)
    if form == COMMENT:
        return comment(sha, root, crossings)
    return page(ledger_id, sha, root, crossings)
