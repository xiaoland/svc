# Agent Task Analysis

Use this Explore depth when an Agent interprets recorded task evidence or an analysis query/read result. The calling Agent owns semantic conclusions; the CLI owns only bounded evidence and references. Return a supported task-performance claim with its evidence horizon and material unknowns.

Trigger this method when an Agent begins interpreting task evidence or receives an analysis query/read result. The calling Agent is the consumer and semantic owner; the CLI supplies evidence and references but is not the authority for task intent, acceptance, or conclusions. Read this method through the packaged corpus lookup before making a task-performance claim.

Keep the minimum chain explicit:

```text
objective/authority -> Agent move -> externalized state -> observation
-> observable Agent update -> verification or handoff horizon
-> terminal quality/completeness, residual unknowns, and task cost
```

Task cost here means task-visible rework, unfinished effort, or downstream
burden. It does not promote latency, token or memory use, throughput, generic
tool failures, or provider health into analysis outcomes.

Separate terminal outcome from possible contributors and observation boundaries. A completion marker, Agent statement, command result, local check, Human acceptance, and external verification are distinct evidence horizons. Before concluding, read the task opening, the terminal or handoff region, contiguous context around relevant evidence, and the declared verification horizon; a match or isolated record is navigation evidence, not a conclusion.

Use the claim ladder from observed fact to within-case inference, candidate mechanism, recurring pattern, and testable SVC gap. Preserve competing explanations and search for a boundary or counterexample before promoting a pattern. Tool or environment observations become task-performance evidence only when they are relevant to the objective and connected to an Agent update, recovery, verification, handoff, or terminal result. Missing evidence remains an explicit unknown rather than a negative finding.

Verification for this method is a packaged lookup digest plus real-thread dogfood reviewed by an independent Agent. The method must support bounded, reference-resolvable analysis without a human-only interface or a built-in semantic analyzer.
