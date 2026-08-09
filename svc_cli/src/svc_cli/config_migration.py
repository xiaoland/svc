"""The explicit, lossless schema-v2 to schema-v3 configuration transform."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

import jsonpatch  # type: ignore[import-untyped]

from .config import (
    ConfigError,
    LegacyProjectConfig,
    ProjectConfig,
    parse_json_document,
    parse_legacy_local_overlay,
    parse_legacy_project_config,
    parse_local_overlay,
    parse_project_config,
    render_config_value,
)


PROFILE_TOKEN = "${dev.profile}"


class ConfigMigrationError(ConfigError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class MigratedDocument:
    source: str
    operations: tuple[dict[str, object], ...]
    content: bytes


@dataclass(frozen=True)
class ConfigMigration:
    source_profile: str | None
    base: MigratedDocument
    local: MigratedDocument | None
    target: ProjectConfig


def migrate_v2_to_v3(
    base_content: bytes,
    local_content: bytes | None = None,
) -> ConfigMigration:
    """Generate, apply, and revalidate one explicit RFC 6902 schema step."""

    legacy = parse_legacy_project_config(base_content)
    base_raw = parse_json_document(base_content, "svc.json")
    selected = _selected_profile(legacy)
    base_operations = _base_operations(base_raw, legacy, selected)
    base_target = _apply_patch(base_raw, base_operations, "svc.json")
    base_bytes = render_config_value(base_target)
    target = parse_project_config(base_bytes)

    local_result: MigratedDocument | None = None
    if local_content is not None:
        local_raw = parse_legacy_local_overlay(local_content)
        local_operations = _local_operations(
            local_raw, selected, committed_run_entries=set(legacy.run)
        )
        _validate_legacy_effective(base_raw, local_raw)
        local_target = _apply_patch(local_raw, local_operations, "svc.local.json")
        local_bytes = render_config_value(local_target)
        parse_local_overlay(local_bytes)
        effective = _merge(base_target, local_target)
        parse_project_config(render_config_value(effective), "effective configuration")
        local_result = MigratedDocument(
            "svc.local.json", tuple(local_operations), local_bytes
        )

    return ConfigMigration(
        selected,
        MigratedDocument("svc.json", tuple(base_operations), base_bytes),
        local_result,
        target,
    )


def _selected_profile(legacy: LegacyProjectConfig) -> str | None:
    if legacy.dev is None:
        return None
    profiles = tuple(legacy.dev.profiles)
    if len(profiles) != 1:
        raise ConfigMigrationError(
            "multiple-dev-profiles",
            "Schema v2 dev configuration has multiple profiles; automatic "
            "migration would discard data.",
        )
    return legacy.dev.profile


def _base_operations(
    raw: dict[str, Any], legacy: LegacyProjectConfig, selected: str | None
) -> list[dict[str, object]]:
    operations: list[dict[str, object]] = [
        {"op": "test", "path": "/schema_version", "value": 2},
        {"op": "test", "path": "/svc_version", "value": legacy.svc_version},
        {"op": "move", "from": "/svc_version", "path": "/corpus_version"},
    ]
    if selected is not None:
        dev = raw["dev"]
        profiles = dev["profiles"]
        escaped = _pointer_part(selected)
        operations.extend(
            [
                {"op": "test", "path": "/dev/profile", "value": selected},
                {"op": "test", "path": "/dev/profiles", "value": profiles},
                {
                    "op": "move",
                    "from": f"/dev/profiles/{escaped}/targets",
                    "path": "/dev/targets",
                },
                {"op": "remove", "path": "/dev/profile"},
                {"op": "remove", "path": "/dev/profiles"},
            ]
        )
        targets = profiles[selected]["targets"]
        operations.extend(
            _profile_token_replacements(targets, "/dev/targets", selected)
        )
    operations.append({"op": "replace", "path": "/schema_version", "value": 3})
    return operations


def _local_operations(
    raw: dict[str, Any],
    selected: str | None,
    *,
    committed_run_entries: set[str],
) -> list[dict[str, object]]:
    local_run = raw.get("run")
    if isinstance(local_run, dict):
        local_only = sorted(set(local_run) - committed_run_entries)
        if local_only:
            raise ConfigMigrationError(
                "local-only-run-entry",
                f"svc.local.json cannot create run entry {local_only[0]!r}.",
            )
    operations: list[dict[str, object]] = []
    dev = raw.get("dev")
    if isinstance(dev, dict):
        local_profile = dev.get("profile")
        if local_profile is not None:
            if selected is None or local_profile != selected:
                raise ConfigMigrationError(
                    "local-profile-mismatch",
                    "svc.local.json selects a profile that cannot be preserved in v3.",
                )
            operations.extend(
                [
                    {
                        "op": "test",
                        "path": "/dev/profile",
                        "value": local_profile,
                    },
                    {"op": "remove", "path": "/dev/profile"},
                ]
            )
        profiles = dev.get("profiles")
        if isinstance(profiles, dict):
            if selected is None or set(profiles) - {selected}:
                raise ConfigMigrationError(
                    "local-profile-mismatch",
                    "svc.local.json contains a profile that cannot be preserved in v3.",
                )
            operations.append(
                {"op": "test", "path": "/dev/profiles", "value": profiles}
            )
            profile = profiles.get(selected, {})
            targets = profile.get("targets") if isinstance(profile, dict) else None
            if targets is not None:
                escaped = _pointer_part(selected)
                operations.append(
                    {
                        "op": "move",
                        "from": f"/dev/profiles/{escaped}/targets",
                        "path": "/dev/targets",
                    }
                )
                operations.extend(
                    _profile_token_replacements(targets, "/dev/targets", selected)
                )
            operations.append({"op": "remove", "path": "/dev/profiles"})
    operations.append({"op": "add", "path": "/schema_version", "value": 3})
    return operations


def _profile_token_replacements(
    value: object, pointer: str, selected: str
) -> list[dict[str, object]]:
    operations: list[dict[str, object]] = []
    for path, item in _walk_strings(value, pointer):
        if PROFILE_TOKEN in item:
            operations.append(
                {
                    "op": "replace",
                    "path": path,
                    "value": item.replace(PROFILE_TOKEN, selected),
                }
            )
    return operations


def _walk_strings(value: object, pointer: str) -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield pointer, value
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from _walk_strings(value[key], f"{pointer}/{_pointer_part(str(key))}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{pointer}/{index}")


def _pointer_part(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _apply_patch(
    source: dict[str, Any], operations: list[dict[str, object]], label: str
) -> dict[str, Any]:
    try:
        result = jsonpatch.apply_patch(deepcopy(source), operations, in_place=False)
    except jsonpatch.JsonPatchException as error:
        raise ConfigMigrationError(
            "config-patch-failed", f"RFC 6902 migration failed for {label}: {error}"
        ) from error
    if not isinstance(result, dict):
        raise ConfigMigrationError(
            "config-patch-failed", f"RFC 6902 migration replaced {label} root."
        )
    return result


def _validate_legacy_effective(base: dict[str, Any], local: dict[str, Any]) -> None:
    effective = _merge(base, local)
    parse_legacy_project_config(
        render_config_value(effective), "effective legacy configuration"
    )


def _merge(base: object, local: object) -> object:
    if isinstance(base, dict) and isinstance(local, dict):
        merged = dict(base)
        for key, value in local.items():
            merged[key] = _merge(merged[key], value) if key in merged else value
        return merged
    return local
