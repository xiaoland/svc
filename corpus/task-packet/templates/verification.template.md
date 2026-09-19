<!-- Create only when one owned claim needs qualification, trusted-base scope, or requalification beyond the packet's terminal Verification. Do not create a command dump or completed-work log. -->
# Verification: <Owned Claim>

## Owned Claim

<!-- State the exact claim this document qualifies and its semantic owner. -->

- Claim: <observable claim>
- Owner / consumer: <authority and reader>

## Observation / Oracle

<!-- Define what is observed and which oracle or rule decides whether it supports the claim. -->

- Observation: <measured behavior or artifact>
- Oracle: <expected rule, comparator, or acceptance relation>

## Evidence and Trusted-base Scope

<!-- Bound the evidence, its provenance, and the trusted assumptions behind it. -->

- Evidence: <links, observations, and run context>
- Trusted base: <code, schema, environment, authority, or assumptions trusted>

## Residual / Horizon

<!-- State what this evidence cannot establish and when it must be refreshed or extended. -->

- Residual: <unknown, blind spot, or risk>
- Horizon: <coverage boundary, expiry, or recheck trigger>

## Consumer Disposition / Requalification

<!-- State how the consumer uses this result and what change reopens qualification. -->

- Disposition: <qualified | partial | unavailable | rejected>
- Requalify when: <change or trigger>
