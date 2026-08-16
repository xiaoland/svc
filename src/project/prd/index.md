# Product Truth

Product Truth owns what the product is for, what users or external systems can
observe, which rules and scope apply, and why those commitments exist. It does
not own implementation topology, internal sequencing, wire details, or local
code contracts.

Keep one concise Product owner containing, as applicable:

- purpose and pressure
- claims and how stakeholders judge them
- capabilities and user or external workflows
- rules, non-goals, and scope
- stable business language

Derive technical contracts and work from owned Product claims; do not infer
Product truth from current implementation, fixtures, or passing tests. Use
[Product Design](../../methods/design/product.md) to shape a proposed Product
solution and update this owner only when that solution is accepted as durable
truth.

Current SVC Product projections have distinct consumers and change cadence:

- [Corpus delivery and project evolution](corpus.md)
- [declared development capabilities](development.md)
- [Agent task-performance analysis](agent-analysis.md)
- [shared declared runs](run.md)
- [managed external boundaries and Double](double.md)

Create further depth only when a Product capability has enough stable content
and an independent consumer. Do not use Product depth to duplicate cross-unit
wire contracts or runtime implementation; route those to Product TDD or
Deployment.
