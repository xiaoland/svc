# SVC Corpus Authoring

These instructions apply only to the authored Consumer Corpus under `src/`.
They do not govern repository code, volatile Task Packets, or documents later
created in Consumer projects. `AGENTS.md` itself is maintainer guidance and is
excluded from the packaged Corpus.

## Write from the Semantic Owner

Keep one canonical statement for each normative claim. Choose an owner by the
claim's meaning and consumer; use parent entries only to route to that owner.
Do not preserve duplicate wording as context. Repair contradictions from the
owner outward, and keep generated projections non-authoritative.

Every concept directory uses this stable shape:

```text
<concept>/
  index.md
  <pressure-created depth>.md
  <subconcept>/index.md
```

Symmetry applies to the node shape, not to its number of children. Do not add
empty mirrored topics. Split `index.md` only for a distinct recurring trigger,
consumer, authority boundary, or change cadence—not for line count alone.

## Make Each Entry Sufficient and Progressive

A directory `index.md` is a compact semantic interface, not a link list. In
natural prose, make these facts recoverable without required front matter:

1. why the entry exists and when to use it
2. what it owns, consumes, and does not own
3. the minimum guidance or truth needed to act
4. the causal reason and material counter-pressure for a non-obvious rule
5. which narrower question continues in which child entry

A depth document starts with its narrower use condition, consumer or return,
and relation to its parent. Explain rationale beside the rule it supports; do
not retain design history as rationale.

## Use Precise, Economical Language

Prefer one stable term for one concept and concrete nouns and verbs. Make
subject, action, condition, authority, and outcome explicit. Separate rules,
defaults, recommendations, examples, hypotheses, and evidence. Preserve
uncertainty and material exceptions instead of making a heuristic absolute.

Optimize semantic compression, not word count. A longer phrase is cheaper
when it prevents ambiguity, rereading, or wrong action. Admit an SVC-specific
term only when its recurring coordination value exceeds learning, recall, and
translation cost. Keep Agent-only methods and specialist depth out of the
ordinary Human collaboration surface.

## Match the Carrier to the Relationship

Use prose for one causal claim, bullets for independent rules, tables for
exact mappings, topology for ownership or dependency, sequence diagrams for
timing or authority handoff, and examples with counterexamples for boundaries.
Use the smallest carrier that preserves the relationship. Do not add diagrams
as decoration or duplicate every edge in prose.

Templates explain each slot with short comments or placeholders and say when
the artifact should not be created. A template is an optional Consumer shape,
not evidence that every project or Task needs that shape.

## Review Proportionally

Before a material Corpus edit, check that the intended reader can identify the
purpose, trigger, owner, action or return, exception, and next route without
loading unrelated entries. Search for competing claims, validate links and
generated projections, and confirm that simple work avoids specialist depth.
Mechanical checks enforce paths and syntax; they cannot prove semantic
ownership, useful prose, or good taste.
