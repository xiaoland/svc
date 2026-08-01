# Adopt the local Agent-evidence trust boundary

SVC 12.0.0 treats Agent-thread acquisition as an explicit same-user local
workflow. It trusts the calling user, provider location, local account, and
operating system. It no longer claims confidentiality, redaction, sandboxing,
atomic output visibility, symlink/reparse exclusion, hostile same-user defense,
or adversarial path-race protection.

## Update inventory consumers

`telemetry agent-thread list` no longer probes every reported source before
returning inventory. Remove dependencies on `source_availability`,
`source_warning_code`, and `omitted_sources`. Lifecycle, recognition,
provenance, bounds, and deterministic ordering remain. Treat export—not a
stale inventory prediction—as the authority for whether one exact source can
be collected.

## Update schema-v3 consumers

The manifest no longer carries normalization, `sensitivity`, or `redaction`
policy, and source capture no longer reports the path-displacement state or
loss reason. Native evidence may contain every selected provider byte. The
optional trajectory member is a rebuildable navigation cache; its structural
omissions are not privacy controls. Keep validating the evidence core and do
not infer confidentiality from absent projection fields.

## Treat cursors as local continuation state

Query/read cursors are unsigned base64-encoded state. Their evidence ID, typed
query or read scope, and position are still validated for bounds, but the
cursor is not an authenticated capability and does not prove who produced it.
Do not use cursor possession as an authorization decision.

## Handle interrupted export explicitly

Export still keeps the source read-only, requires an absent destination,
refuses overwrite and source/output aliasing, and validates a successful
bundle before returning. It no longer promises atomic visibility. If the
process is interrupted, validate the target before use; remove an invalid
partial target under the caller's normal ownership policy before retrying.
