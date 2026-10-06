# Requirements and Oracles

Read this reference when the intended behavior, requirement interpretation, or judgment rule is uncertain, too weak, or too specific. Return a requirement-to-observation relationship that distinguishes relevant behavior from incidental implementation and names the remaining interpretation risk. This expands the [Verification Skill](../SKILL.md); use this reference directly when its pressure is already known.

Start with the result the product is meant to provide. Product purpose, a behavior requirement, a design proposal, and an implementation are related but not interchangeable. “A user can use their own workspace after signing in” constrains a result and its ownership; “the URL is `/dashboard` and the page contains an `h1`” constrains a representation unless the product explicitly promises those details. Verification can establish conformity to the written requirement, while validation can reveal that the requirement or its realized result does not serve the intended use.

Do not turn an uncertain product choice into an executable rule merely because it is precise. When the desired behavior is still being discovered, use a prototype, comparison, or other authorized product feedback to clarify it. Once a stable behavior is understood, express the part that must remain true so an implementation can be searched within that boundary.

Choose a semantic object that matches the requirement. A rule about an individual state may constrain visibility or ownership; a state transition may constrain a before-state, action, after-state, and failure result; a process may constrain an ordered history or eventual outcome; a quantitative requirement may constrain a measured distribution under named workload and environment. These forms can overlap, and the point is to preserve what the product cares about rather than complete a classification.

Trace each translation explicitly:

```text
purpose → requirement → observable result → oracle → executable check
```

For every arrow, ask what makes the next item evidence for the previous one and what assumption it adds. A save-success message does not establish that a changed setting survives the next login. A helper named `workspace_is_private` does not establish that it observes identity, ownership, and visible data. A database row can be direct evidence when persistence is the requirement, but it cannot by itself prove that the user can complete the promised product path.

An oracle has two symmetric obligations:

```text
meaningful requirement violation → the oracle can reject it
implementation change preserving the requirement → the oracle keeps accepting it
```

The second obligation is conditional on all stated requirements. If a public URL, protocol order, accessibility role, or exact response is itself part of the contract, changing it is a semantic change. Otherwise, a route, tag, private helper, collaborator call, or storage arrangement is an implementation detail that should not define product correctness. Deliberately reason through one violating candidate and one valid alternative when this boundary matters; use semantic mutation or a second implementation only when the cost and authorized isolation justify it.

Properties, contracts, and invariants are useful because they describe a space of permitted behavior instead of one current answer. A sorting failure that drops a duplicate may reveal the broader property that the output preserves the input's multiset. The concrete case still matters when its rare condition is not reliably reached by the general check, and a property still does not cover every state, history, interaction, or quality requirement. “Regression” describes a purpose—preventing an established behavior from silently disappearing—not a requirement to preserve every historical example forever.

Keep the oracle separate from condition selection. The oracle says what counts as correct; selection chooses inputs, identities, initial states, histories, concurrency, faults, and use contexts that the system will actually experience. A general property with a narrow generator is still narrow evidence. Coverage is meaningful only after naming the space covered: requirements, states, transitions, journeys, workloads, or code branches.

When an observation contradicts the requirement, determine whether the implementation violated it, the check observed the wrong thing, the conditions were invalid, or the requirement no longer represents the goal. Do not weaken the oracle merely to accept the current candidate. Revise the requirement or criterion only with the authority and reason appropriate to that change, and preserve the distinction between a corrected observation and a changed product promise.
