# Corpus Migrations

Use these living guides when a Consumer project adopts a newer SVC Corpus
baseline. Version 15 is the current anchor and has no runtime migration chain
from pre-v15 baselines. An Agent and Human evaluate and update Consumer-owned
truth before adopting v15; SVC never rewrites or claims to have verified those
documents.

Capability-named guides describe the current semantic transition. The package
manager owns CLI installation. CLI configuration schemas are current-only
contracts and are not part of Corpus guidance.

Current guides:

- [Coding Agent debugger and profiler evidence](analysis-debugger-corpus.md)

Version classification follows Consumer behavior:

- **major** changes an obligation, default, authority or permission boundary,
  Task Packet semantic, Consumer layout, or supported CLI/Catalog address
- **minor** adds a backward-compatible optional capability
- **patch** restores or clarifies the existing contract

Every release-relevant change has a Towncrier fragment. Migration guides and
`src/version.json` are authored Corpus sources, independent of CLI release notes.
