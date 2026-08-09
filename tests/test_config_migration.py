from __future__ import annotations

import json

import pytest

from svc_cli.config import ConfigError, parse_project_config
from svc_cli.config_migration import ConfigMigrationError, migrate_v2_to_v3


def legacy_base(*, profiles: int = 1, dev: bool = True) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": 2,
        "svc_version": "10.0.1",
        "run": {"check": {"argv": ["pdm", "run", "test"]}},
    }
    if dev:
        declared = {
            "local": {
                "targets": {
                    "web": {
                        "probe": {
                            "kind": "exec",
                            "argv": ["check", "${dev.profile}", "${dev.instance}"],
                            "cwd": ".runtime/${dev.profile}",
                        },
                        "provision": {
                            "kind": "exec",
                            "mode": "run",
                            "argv": ["start", "${dev.profile}"],
                            "env": {"PROFILE": "${dev.profile}"},
                        },
                        "access": ["http://${dev.profile}-${dev.instance}.localhost"],
                    }
                }
            }
        }
        if profiles == 2:
            declared["shared"] = {
                "targets": {
                    "database": {
                        "probe": {
                            "kind": "tcp",
                            "host": "127.0.0.1",
                            "port": 5432,
                        },
                        "provision": {"kind": "manual"},
                    }
                }
            }
        value["dev"] = {"profile": "local", "profiles": declared}
    return value


def encoded(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode()


def test_single_profile_transform_is_explicit_lossless_and_v3_valid() -> None:
    migration = migrate_v2_to_v3(encoded(legacy_base()))
    transformed = json.loads(migration.base.content)

    assert migration.source_profile == "local"
    assert transformed["schema_version"] == 3
    assert transformed["corpus_version"] == "10.0.1"
    assert "svc_version" not in transformed
    assert set(transformed["dev"]) == {"targets"}
    target = transformed["dev"]["targets"]["web"]
    assert target["probe"]["argv"] == ["check", "local", "${dev.instance}"]
    assert target["probe"]["cwd"] == ".runtime/local"
    assert target["provision"]["env"] == {"PROFILE": "local"}
    assert "stop" not in target
    assert transformed["run"] == legacy_base()["run"]
    assert parse_project_config(migration.base.content).schema_version == 3


def test_base_without_dev_only_separates_versions_and_preserves_run() -> None:
    migration = migrate_v2_to_v3(encoded(legacy_base(dev=False)))
    transformed = json.loads(migration.base.content)

    assert migration.source_profile is None
    assert transformed == {
        "corpus_version": "10.0.1",
        "run": {"check": {"argv": ["pdm", "run", "test"]}},
        "schema_version": 3,
    }


def test_present_local_overlay_is_migrated_and_effective_model_revalidated() -> None:
    local = {
        "dev": {
            "profile": "local",
            "profiles": {
                "local": {
                    "targets": {
                        "web": {
                            "access": ["http://local-${dev.profile}.localhost"],
                            "provision": {"env": {"PORT": "3000"}},
                        }
                    }
                }
            },
        },
        "run": {"check": {"env": {"LOCAL": "1"}}},
    }

    migration = migrate_v2_to_v3(encoded(legacy_base()), encoded(local))
    assert migration.local is not None
    transformed = json.loads(migration.local.content)

    assert transformed["schema_version"] == 3
    assert set(transformed["dev"]) == {"targets"}
    assert transformed["dev"]["targets"]["web"]["access"] == [
        "http://local-local.localhost"
    ]
    assert migration.target.dev is not None
    assert migration.target.dev.targets["web"].stop is None


@pytest.mark.parametrize(
    ("local", "code"),
    (
        ({"dev": {"profile": "shared"}}, "local-profile-mismatch"),
        (
            {"dev": {"profiles": {"shared": {"targets": {}}}}},
            "local-profile-mismatch",
        ),
        (
            {"run": {"local-only": {"argv": ["tool"]}}},
            "local-only-run-entry",
        ),
    ),
)
def test_local_shapes_outside_lossless_transform_block(
    local: dict[str, object], code: str
) -> None:
    with pytest.raises(ConfigMigrationError) as raised:
        migrate_v2_to_v3(encoded(legacy_base()), encoded(local))

    assert raised.value.code == code


def test_legacy_source_parser_remains_strict() -> None:
    with pytest.raises(ConfigError):
        migrate_v2_to_v3(
            b'{"schema_version":2,"schema_version":2,"svc_version":"10.0.1"}'
        )
    with pytest.raises(ConfigError):
        migrate_v2_to_v3(b'{"schema_version":2,"svc_version":"10.0.1","stop":{}}')
