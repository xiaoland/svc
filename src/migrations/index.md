# Corpus Migrations

Use these living guides when a Consumer project adopts a newer SVC Corpus
baseline. The installed CLI selects the exact release chain; an Agent and
Human evaluate and update Consumer-owned truth, then `svc upgrade --target
corpus` records only the reviewed baseline. SVC never rewrites or claims to
have verified those documents.

Read versioned migration guides in ascending release order. Capability-named
guides describe a required semantic transition selected by that chain. The
package manager owns CLI installation; configuration migration is a separate
`svc upgrade --target config` operation.

Current guides:

- [11.0.0 Agent-thread observability migration](11.0.0.md)
- [Agent-owned query and native read](agent-analysis-query-read.md)
- [schema-v3 Agent evidence authority](agent-task-performance-analysis.md)
- [same-user local evidence boundary](local-trust-boundary.md)
- [13.0.0 symmetric Corpus and progressive Task Packets](core-mechanism-evolution.md)

Version classification follows Consumer behavior:

- **major** changes an obligation, default, authority or permission boundary,
  Task Packet semantic, Consumer layout, or supported CLI/Catalog address
- **minor** adds a backward-compatible optional capability
- **patch** restores or clarifies the existing contract

Every release-relevant change has a Changie fragment. Generated migration
guides, version index, changelog, and release artifacts project that source;
they do not replace this selection contract.
