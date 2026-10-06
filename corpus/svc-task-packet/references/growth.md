# Grow a Task Packet

Use this guidance when the current packet shape makes Human recovery, Agent retrieval, local planning, or concurrent editing materially harder. Growth is an in-place semantic refactor, not a scale score, lifecycle event, or CLI decision.

## Run a Shape Preflight Early

After creating or recovering the minimal Packet, ask:

1. Can short `packet.md` plus one linear Plan control the foreseeable work?
2. Are there persistent concern axes that need Track continuity?
3. Is there a real shared barrier across a declared set of Tracks?
4. Which Task, Cell, or bounded unit owns each current Plan?
5. Which Inquiry, Design, Decision, or Verification state has a distinct retrieval/update owner now?
6. Where would two writers contend, or where is current truth already hard to recover?

Fix the likely shape while the move is cheap, but do not create speculative Tracks, Phases, Cells, or modules. Re-run the preflight when work topology, freshness pressure, evidence volume, or collaboration changes materially.

## Stable Root Entries

The common root vocabulary is deliberately small:

```text
packet.md
plan.md                 # only for a Task-level linear Plan
task-map.md             # admitted non-linear topology + Human projection source
inquiry.md              # optional information owner
design.md               # optional solution owner
decisions.md            # optional decision register
verification.md         # optional cross-return qualification synthesis
cells/                  # optional Cell entries and local Plans
track-*.md              # optional shallow Track control entry
phase-*.md              # optional shallow Phase/barrier control entry
```

A stable entry may grow into same-stem supporting depth, for example `design.md` plus `design/`, or `decisions.md` plus decision shards. `cells/` may contain one entry per admitted Cell. Track and Phase entries remain shallow unless demonstrated retrieval pressure justifies depth; do not mirror the entire matrix into directories.

## Migrate in Place

1. Select the owner or topology pressure before selecting filenames.
2. Create the stable entry from the applicable [template](templates.md) only when it helps.
3. Move the current semantic content before adding new analysis.
4. Replace the old location with a compact projection or route; do not keep two competing current truths.
5. Repair Plan/Cell relations and the Human `packet.md` projection in the same change.
6. Verify that a fresh Human can recover the outcome/current issue from `packet.md`, and that an Agent can find each active owner without broad search.

Unknown or custom names are allowed when they carry real task-local value. Review unfamiliar names for an identifiable owner and useful return rather than renaming them merely to fit this vocabulary. Shrink or remove a module when its management return no longer repays synchronization and navigation cost.
