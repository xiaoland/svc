# SVC Skill Authoring

These instructions apply only to the authored framework under `corpus/`. They do not govern repository code, volatile Task Packets, or documents created in Consumer projects. This file is maintainer guidance, not a Consumer Skill.

## Write from the Semantic Owner

Keep one semantic owner for each capability and its specialist guidance. Repeat the minimum authority and responsibility boundaries in each Skill when independent use requires them; these local statements must agree. Choose an owner by the claim's meaning and consumer; use parent entries only to route to that owner. Do not copy another capability or preserve duplicate specialist guidance as context. Repair contradictions from the owner outward and keep projections non-authoritative.

The six Skill directories use `SKILL.md` as their sole entry. Put conditional explanatory depth in `references/` and opt-in artifact starting shapes in `assets/`, creating each directory only when actual resources justify it. Do not preserve a competing `index.md`, add a generated Skill layer, or make every Skill mirror the same resource tree. Root `index.md` owns repository introduction and navigation; it is not a runtime dependency. Each Skill carries a verbatim copy of the repository MIT `LICENSE`; release preparation synchronizes these copies. The root `pyproject.toml` owns the Corpus release version; migration guides explain framework release adoption.

## Make Discovery, Loading, and Action Work Together

Each Skill has standard `name`, `description`, and release `metadata` frontmatter. The line forms below are this repository's authoring convention: they are valid standard YAML, but the source checker does not implement general YAML parsing. The name is a single plain line matching its directory; the description and compact metadata object are JSON values, which are also valid YAML. Describe the goal and recognizable conditions from explicit requests and changes during ongoing work. Metadata exposes applicability and release identity before body loading; it does not guarantee host discovery or grant tool/effect authority. Add no host-specific metadata, installer, or dependency resolver without a distinct need and authorization.

Each Skill must work when its directory is copied away from the repository and installed alone. Keep every required instruction and resource inside that directory, including the authority and responsibility boundaries needed for its own work. Do not require a parent document, sibling Skill, symlink escape, or installation layout. Make the first useful action, adequate return, material exception, and stop or redirection condition discoverable. For reference-oriented Taste, explain how a pressure changes judgment rather than inventing a workflow.

Every reference starts with its narrower use condition, consumer or return, and relation to its parent. A link states the pressure that makes reading it worthwhile. Across Skills, name the relevant capability and discover its installed entry through the host only when available. Such routes provide additional guidance, not prerequisites; keep current obligations and capability gaps explicit without assuming another Skill is installed. Explain rationale beside its rule; do not retain design history as rationale. Methods compose recursively and Task Packet covers every non-trivial Task; neither becomes a fixed phase sequence.

## Use Precise, Economical Language

Prefer one stable term for one concept and concrete nouns and verbs. Make subject, action, condition, authority, and outcome explicit. Separate rules, defaults, recommendations, examples, hypotheses, and evidence. Preserve uncertainty and material exceptions instead of making a heuristic absolute.

Optimize semantic compression, not word count. A longer phrase is cheaper when it prevents ambiguity, rereading, or wrong action. Admit an SVC-specific term only when its recurring coordination value exceeds learning, recall, and translation cost. Keep Agent-only methods and specialist depth out of the ordinary Human collaboration surface. Write each prose paragraph on one semantic line; do not hard-wrap at a fixed column width. Preserve genuine list, table, and code structure.

## Match the Carrier to the Relationship

Use prose for one causal claim, bullets for independent rules, tables for exact mappings, topology for ownership or dependency, sequence diagrams for timing or authority handoff, and examples with counterexamples for boundaries. Use the smallest carrier that preserves the relationship. Do not add diagrams as decoration or duplicate every edge in prose.

Assets explain each slot with short comments or placeholders and say when the artifact should not be created. A template is an optional Consumer shape, not evidence that every project or Task needs that shape. Consumer instruction assets name the adopted guidance through Consumer-supplied pointers; Skill-local links travel with the directory; project adoption instructions refer to actual adopted entries.

## Review Proportionally

Before a material edit, check that the intended reader can identify the purpose, trigger, owner, action or return, exception, and next route without loading unrelated entries. Search for competing claims, validate all local references and metadata within each independently movable Skill directory, and confirm that simple work avoids specialist depth. Mechanical checks enforce paths and syntax; they cannot prove semantic ownership, useful prose, reliable model triggering, or good taste. Preserve all prior responsibilities and claims during content relocation unless a behavior change has been explicitly agreed.
