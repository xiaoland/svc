# Product TDD

Product TDD is an optional owner for cross-unit technical contracts. Admit a
contract only when two or more logical units must agree on authority, topology,
wire shape, lifecycle, sequencing, compatibility, or failure behavior to
interoperate safely, and code or schemas alone cannot preserve the expensive
meaning clearly enough.

It consumes accepted Product and Technical claims and returns the minimum
shared contract each participating unit must implement and verify. It does not
own Product rationale, one unit's private design, runtime operations, or Task
state. Prefer executable schemas and tests for field-level enforcement.

Current cross-unit projections are:

- [shared execution](execution.md)
- [Double boundary harness](double.md)
- [Agent evidence query/read](agent-analysis.md)

If the [multi-repo extension](../../extensions/multi-repo/index.md) is active,
keep shared Product TDD in the Hub authority and consume it read-only from
Spokes. Do not copy the contract into independently drifting owners.
