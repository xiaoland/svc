from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    migration_id: str
    source_version: str
    target_version: str


MIGRATIONS = (
    Migration(
        migration_id="9.8.0-to-10.0.0",
        source_version="9.8.0",
        target_version="10.0.0",
    ),
)


def resolve_migrations(source_version: str, target_version: str) -> tuple[Migration, ...]:
    if source_version == target_version:
        return ()

    current = source_version
    resolved: list[Migration] = []
    visited: set[str] = set()
    while current != target_version:
        if current in visited:
            raise ValueError(f"Migration graph contains a cycle at {current}")
        visited.add(current)
        candidates = [item for item in MIGRATIONS if item.source_version == current]
        if len(candidates) != 1:
            raise ValueError(
                f"No unique adjacent migration from {current} to {target_version}"
            )
        migration = candidates[0]
        resolved.append(migration)
        current = migration.target_version
    return tuple(resolved)
