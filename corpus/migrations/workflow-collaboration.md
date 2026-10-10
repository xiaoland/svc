# Adopt the Staged Collaboration Default

Target Corpus release: 17.0.0.

Use this guide when adopting the changed collaboration default from Corpus 16 or earlier. Previously, Workflow left the mode to the project's agreement or the Human's instruction and requested a decision when an unresolved mode choice affected a consequential action. Every non-trivial Task now requires reading and using [svc-workflow](../svc-workflow/SKILL.md), whose short entry owns the staged collaboration default without requiring the Human to name or select a mode. References supply depth only when needed.

Add the Workflow reading rule and its actual adopted entry pointer to the persistent Consumer instructions, alongside the existing Task Packet rule. The [root instruction asset](../svc-specs/assets/AGENTS.root.template.md) supplies the updated starting shape. The Workflow description declares the mandatory trigger; host discovery alone does not guarantee that it will be selected or read.

Keep both parts of Workflow's scope visible: collaboration modes govern Human–Agent commitments and feedback, while Explore, Design, Planning, and Implementation guide autonomous Agent work by the current gap. Human availability is not a prerequisite for reading the entry or applying its methods within existing authority; unresolved Human decisions still block their dependent effects.

Review Consumer-owned collaboration instructions for conflicting mode-selection rules. Preserve an established agreement or direct Human instruction selecting iterative collaboration; it overrides the default. When no such agreement exists, recover existing decisions and authority, prepare a reviewable recommendation, and obtain confirmation of unsettled scope or consequential choices before dependent realization. An already confirmed and authorized implementation continues without another approval for ordinary engineering work. Feedback and silence do not switch the mode or confer authority.

Check adoption with a non-trivial request that leaves a material product choice open: the Agent should prepare the choice and seek confirmation before implementing the dependent effect without first asking which mode to use. Also check an already authorized implementation and a project with an established iterative agreement: the former should continue its ordinary work and the latter should retain its agreed rhythm. These observations concern collaboration and authority; static source checks alone do not establish actual Agent execution reliability.
