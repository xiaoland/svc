# Task Map

A Task Map organizes work into independent Tracks, their convergence points, and the work after convergence. Use it only when two or more work lines can advance in parallel and their completion times differ by more than one day.

Most Tasks use a single linear plan inside `packet.md` or `plan.md`. The Task Map adds structure when parallel work justifies the coordination cost.

## Three Units

### Track

A Track is one work line that can advance independently:

- Has its own owner (Human or Agent)
- Has its own plan file: `track-<name>.md`
- Advances toward one or more convergence points
- May continue past convergence if its concern persists

**When to use**: Two or more work lines can proceed in parallel, their completion times differ by more than one day, and each Track's primary inputs — the code regions, files, and domain context it must understand to do its work — are substantially distinct from the others'. Examples:

- One Agent designs the API contract while another researches existing implementations
- Implementation proceeds in one repository while documentation updates happen in another
- Security review runs in parallel with performance testing

**When not to use**: Sequential work, parallel work that completes within hours, or parallel work whose primary inputs substantially overlap. When Tracks share the same code regions, files, or domain context, assigning them to separate owners multiplies the total investigation cost without multiplying useful output; keep them in one Track and let a single owner build understanding incrementally.

### Convergence Point

A convergence point synchronizes two or more Tracks:

- Marks where one Track waits for another
- Appears in each participating Track's plan as `## Convergence: <name>`
- States which Tracks converge here and what happens next

**Format**:

```markdown
## Convergence: <name>

Waits for:
- track-api-design (API contract finalized)
- track-implementation-research (existing patterns identified)

After convergence:
- Start implementation using agreed contract and identified patterns
```

A convergence point is not a separate file or object. It is a marked section in each Track's plan.

### Plan

A plan is a linear, ordered list of steps:

- **Default location**: inside `packet.md` as a `## 计划` section
- **Separate file**: `plan.md` when the plan exceeds 30 lines or needs independent revision history
- **Track plan**: `track-<name>.md` when using a Task Map with multiple Tracks

**Contents**: each step includes owner, input, output, and any blocking dependencies.

## When to Use a Task Map

Use a Task Map (multiple Tracks) when **both** conditions hold:

1. Two or more work lines can advance in parallel
2. Their completion times differ by more than one day

Otherwise, use a single linear plan in `packet.md` or `plan.md`.

## Task Map Example

A Task needs to:
1. Design a new API contract (3 days, requires research and Human approval)
2. Migrate existing callers to the new contract (1 day, can start after contract is finalized)
3. Update documentation (2 hours, can happen anytime after design starts)

**Decision**: Use a Task Map with two Tracks:

- `track-api-design.md`: research → draft contract → Human approval (3 days)
- `track-migration.md`: migrate callers (1 day, waits for track-api-design to finish)

Documentation stays in the migration Track because it only takes 2 hours and doesn't justify a separate Track.

**Convergence**: `track-migration.md` marks `## Convergence: api-finalized`, waits for `track-api-design`, then proceeds with migration.

## Task Map Template

When using a Task Map, add a compact projection to `packet.md`:

```markdown
## Task Map

- track-api-design: research → draft → approval
- track-migration: [waits for api-design] → migrate callers → update docs

Convergence: api-finalized (after track-api-design completes)
```

Keep the projection short. The Track files hold the full plans.

## Migration from Prior Topology

Prior versions of this Skill defined Phase, Cell, Slice, Step, and Assignment. Those units are retired. The Task Map replaces them with three simpler units:

- **Track** replaces Track (same concept, simpler lifecycle)
- **Convergence point** replaces Phase (Phase was a shared barrier; convergence is the same idea without the matrix formalism)
- **Plan** remains the same (linear ordered steps)

**Removed units**:
- **Phase**: replaced by convergence points marked in each Track's plan
- **Cell**: no longer needed; each Track owns its own plan
- **Slice**: no longer a separate unit; a plan's increments are just ordered steps
- **Step**: still exists inside a plan, but not a distinct management unit
- **Assignment**: delegation guidance moved to `svc-agent-collaboration`

If an existing Packet uses Phase/Cell/Slice, migrate by:
1. Identify each Track (independent work line)
2. Mark convergence points where Tracks wait for each other
3. Flatten each Cell's plan into its Track's linear plan
4. Remove Phase boundaries and Slice labels
