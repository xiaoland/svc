# Design Dossier — Agent-Friendly Output

## Status

Accepted direction, deferred by Sir on 2026-08-06 to a separate unit after
`svc run`. This dossier preserves prior reasoning but is not an implementation
scope for the current task. The run-only projection is defined separately in
[`10-run-public-projection-and-process.md`](10-run-public-projection-and-process.md).

## Accepted Direction

Output design starts from meaning and consumer behavior, not a universal
serialization choice. JSON is useful for some structured results but is not the
definition of Agent-friendly. Compact JSON is preferred to prettified JSON when
JSON is selected.

## Current Design Pressure

SVC CLI currently emits several distinct shapes:

- raw canonical Markdown
- path/title and scored lookup lists
- compact JSON result objects
- short Human status summaries
- plans with operations, blockers, and digests
- diagnostics with structured detail
- analysis schemas and paginated evidence results

These shapes do not necessarily benefit from one envelope or one visual form.
The design must preserve exact paths, commands, identifiers, status, and useful
diagnostic distinctions while avoiding redundant prose, decorative structure,
deep nesting, and unbounded child-tool output.

## Accepted Split — Native Command Output and Execution Receipt

The Beluna full-test failure demonstrates two different semantic outputs:

1. **Native evidence**: compiler/test progress, AIMock readiness diagnostics,
   and other output emitted by the project command.
2. **Execution receipt**: bounded SVC facts identifying the execution, selected
   run entry, terminal lifecycle, and duration. The execution ID also addresses
   the captured native output so another caller can follow or recover it.

Embedding native evidence in the receipt would make the stable handoff object
unbounded and bury its execution facts. Returning only the receipt would remove
the evidence needed to diagnose the exact failure. The proposed semantic split
therefore preserves both while allowing different representations and
information bounds. This semantic split is accepted.

This addressability does not mean that SVC discovers project artifacts. If a
command prints a path, URI, or result ID, that text is preserved as native
output, but SVC does not know whether it denotes an artifact, whether the target
exists, what it means, or how long it remains valid. Adding such knowledge
would require an explicit project-owned artifact protocol, which current
consumer evidence does not justify. A separate native-output locator is also
not part of the minimum semantic model; the execution ID is sufficient until a
real storage or handoff trajectory proves otherwise.

No further product decision is required here. Capture representation,
retention, replay syntax, channel placement, and JSON/text rendering are
implementation choices to resolve against concrete CLI behavior and tests.
Wrapper-owned command and terminal lines may be useful output rather than
noise; Agent-friendly means clear attribution and bounded meaning, not an
artificially wrapper-free transcript.

The installed pnpm 11.20.0 provides a direct interaction precedent: when a
lifecycle command inherits stdio and is not silent, pnpm writes a clearly
prefixed `$ <command>` line to stderr before starting it. SVC can likewise make
the resolved project command visible without treating all wrapper-owned output
as contamination or requiring another product-level channel policy.
