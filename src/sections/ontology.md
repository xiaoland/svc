# Progressive Ontology

The framework uses layered ontology access so agents get guardrails without paying full context cost on every task.

## Root Cheat Sheet

Root AGENTS.md should carry only the minimum ontology needed for zero-shot orientation:

- Unit: a logical technical boundary and ownership surface; it is not the same thing as a folder.
- PRD (`10-prd/`): owns business intent and observable behavior, never implementation mechanics.
- Product TDD (`20-product-tdd/`): owns cross-unit technical contracts and system topology.
- Unit TDD (`30-unit-tdd/`): owns a unit's internal logic architecture and internal contracts.

This cheat sheet is a guardrail, not a full glossary.

## On-Demand Concept Dictionary

Full framework terminology lives in `00-meta/concepts.md`.

Load it only when one of these is true:

- a term or boundary cannot be classified confidently
- two layers appear to claim the same truth
- a migration or review needs explicit ontology precision
- the user explicitly asks for framework concepts or definitions

Default behavior:

- do not preload the concept dictionary into every task
- summarize only the needed concepts into the active task packet

## Business Vocabulary Isolation

Framework ontology and business vocabulary must remain separate.

- `00-meta/concepts.md` owns framework terms such as Unit, PRD, Product TDD, and route taxonomy.
- `10-prd/glossary.md` owns business/domain-specific language, lifecycle terms, and user-visible vocabulary.

This separation prevents meta-framework language from polluting product language, and vice versa.

## Boundary Check Rule

When a word appears ambiguous, ask two questions:

1. Is this term about the framework's memory model or the product's business reality?
2. Which layer has the authority to redefine it without changing unrelated truths?

If the answer is unclear, load `00-meta/concepts.md` and resolve the ownership before editing durable docs.

## Related Assets

- [Root AGENTS Template](../assets/templates/AGENTS.root.template.md)
- [Concept Dictionary Template](../assets/templates/concepts.template.md)
- [PRD File Set Template](../assets/templates/prd-file-set.template.md)
