# Coding Agent Evidence Runtime

Use this [Deployment](index.md) depth for telemetry collection, bundle publication, validation, compatibility, and recovery. Analysis meaning and wire fields remain with Product Truth and Product TDD.

An explicit `--provider codex|pi` export produces evidence v4. Telemetry resolves one selected root, captures the provider-native material read-only, expands only the supported bounded relationship closure, normalizes a required trajectory v2, binds trajectory and materials into one evidence identity, and exclusively creates an absent ZIP. Codex follows parent/child rollout relationships available from session metadata or its local state database. Standard Pi follows `parentSession` lineage and preserves its entry tree; Pi subagent extensions are ignored.

Every consumer validates declared members, sizes, hashes, evidence identity, trajectory shape, and source references before use. A trajectory or material integrity failure rejects the bundle. Missing descendants are retained as collection gaps and capability issues. Analysis reads only the trajectory for common behavior; native material is used by `read` and remains available for audit or future export, not as a hidden provider-normalizer fallback.

The runtime retains the schema-v3 compatibility path for legacy Codex export and unversioned analysis v2 requests. Evidence v4 requires analysis v3. Query v3 on evidence v3 asks for re-export; read v3 can still recover its native frames. Evidence v1/v2 requires recollection.

Source size, member size, request size, response size, and page item bounds are enforced. Exact material reads use UTF-8 when lossless and base64 otherwise, and fragments reassemble byte-for-byte across cursor pages. Export never mutates the source or overwrites an existing destination. If publication fails after creating the target, the runtime removes the incomplete target when possible.

The operating system, local provider store, SQLite read-only access, and ZIP validation are trust dependencies. This is not a sandbox or redaction boundary; the caller owns evidence privacy, retention, and disclosure.
