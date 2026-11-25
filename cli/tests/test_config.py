from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from svc_cli.config import (
    ConfigError,
    LOCAL_CONFIG_FILE,
    PROJECT_CONFIG_FILE,
    load_config,
    parse_local_overlay,
    parse_project_config,
)


def base_document() -> dict[str, object]:
    return {
        "schema_version": 5,
        "dev": {
            "resources": {
                "frontend": {
                    "observations": {
                        "ready": {
                            "probe": {
                                "kind": "http",
                                "url": "https://frontend-${dev.instance}.localhost/health",
                                "success_status": [200, 399],
                            }
                        }
                    },
                    "actions": {
                        "ensure": {
                            "kind": "exec",
                            "intent": "启动",
                            "effect_scope": "当前实例",
                            "argv": ["pnpm", "dev"],
                            "conditions": ["ready"],
                            "convergent": True,
                        },
                        "stop": {
                            "kind": "exec",
                            "intent": "停止",
                            "effect_scope": "当前实例",
                            "argv": ["pnpm", "dev:stop", "${dev.instance}"],
                            "interruption": "terminate",
                        },
                    },
                    "access": ["https://frontend-${dev.instance}.localhost/"],
                },
                "database": {
                    "scope": "repository",
                    "observations": {
                        "ready": {
                            "probe": {"kind": "tcp", "host": "127.0.0.1", "port": 5432}
                        }
                    },
                },
            }
        },
        "run": {
            "check": {
                "argv": ["python", "-m", "pytest"],
                "cwd": ".",
                "env_files": [".env.shared"],
                "env": {"PYTHONUTF8": "1"},
            }
        },
    }


def write_config(root: Path, name: str, value: object) -> None:
    (root / name).write_text(json.dumps(value), encoding="utf-8")


def test_complete_strict_base_has_a_stable_canonical_model() -> None:
    document = base_document()
    first = parse_project_config(json.dumps(document).encode())
    second = parse_project_config(json.dumps(document, indent=2).encode())
    assert first.dev is not None
    assert first.dev.resources["frontend"].scope == "worktree"
    assert first.dev.resources["frontend"].actions["stop"] is not None
    assert first.model_dump() == second.model_dump()

    for invalid in (
        {"schema_version": 5, "unknown": True},
        {
            "schema_version": 5,
            "dev": {"resources": {}},
        },
        {"schema_version": 5, "dev": None},
        {"schema_version": 2, "svc_version": "10.0.1"},
    ):
        with pytest.raises(ConfigError):
            parse_project_config(json.dumps(invalid).encode())


def test_parser_rejects_duplicate_nonfinite_invalid_utf8_and_null() -> None:
    for content in (
        b'{"schema_version":5,"schema_version":5}',
        b'{"schema_version":5,"dev":NaN}',
        b'{"schema_version":5,"dev":null}',
        b"\xff",
    ):
        with pytest.raises(ConfigError):
            parse_project_config(content)


def test_sparse_v5_overlay_merges_objects_and_replaces_scalars_and_arrays() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_config(root, PROJECT_CONFIG_FILE, base_document())
        write_config(
            root,
            LOCAL_CONFIG_FILE,
            {
                "schema_version": 5,
                "run": {
                    "check": {
                        "argv": ["pdm", "run", "test"],
                        "cwd": "tests",
                        "env_files": [".env.local"],
                        "env": {"PYTHONUTF8": "0", "LOCAL": "yes"},
                    }
                },
                "dev": {
                    "resources": {
                        "frontend": {
                            "access": ["http://127.0.0.1:3000/"],
                            "actions": {
                                "ensure": {"env": {"PORT": "3000"}},
                                "stop": {"timeout": 120.0},
                            },
                        }
                    }
                },
            },
        )
        resolved = load_config(root)
        assert resolved.effective.dev is not None
        target = resolved.effective.dev.resources["frontend"]
        assert target.access == ["http://127.0.0.1:3000/"]
        assert target.actions["ensure"].env == {"PORT": "3000"}
        assert (
            target.actions["stop"] is not None
            and target.actions["stop"].timeout == 120.0
        )
        run = resolved.effective.run["check"]
        assert run.argv == ["pdm", "run", "test"]
        assert run.cwd == "tests"
        assert run.env_files == [".env.local"]
        assert run.env == {"PYTHONUTF8": "0", "LOCAL": "yes"}
        assert resolved.local_digest is not None
        assert resolved.base_digest != resolved.effective_digest


def test_absent_overlay_is_noop_and_effective_config_is_not_written() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_config(root, PROJECT_CONFIG_FILE, base_document())
        before = sorted(path.name for path in root.iterdir())
        resolved = load_config(root)
        assert resolved.local is None
        assert resolved.base == resolved.effective
        assert sorted(path.name for path in root.iterdir()) == before

        write_config(root, LOCAL_CONFIG_FILE, {"schema_version": 5})
        empty_overlay = load_config(root)
        assert empty_overlay.base == empty_overlay.effective
        assert empty_overlay.local_digest is not None


def test_overlay_refuses_corpus_authority_unknown_paths_and_invalid_schema() -> None:
    for overlay in (
        {},
        {"schema_version": 2},
        {"schema_version": 5, "corpus_version": "10.0.2"},
        {"schema_version": 5, "profile": "worktree"},
        {"schema_version": 5, "dev": {"profiles": {}}},
        {
            "schema_version": 5,
            "dev": {
                "resources": {
                    "frontend": {
                        "observations": {
                            "ready": {"probe": {"kind": "http", "made_up": True}}
                        }
                    }
                }
            },
        },
        {"schema_version": 5, "run": {"check": {"unknown": True}}},
    ):
        with pytest.raises(ConfigError):
            parse_local_overlay(json.dumps(overlay).encode())


def test_run_entries_are_strict_and_local_overlay_cannot_create_names() -> None:
    for entry in (
        {"argv": []},
        {"argv": [""]},
        {"argv": ["tool\0bad"]},
        {"argv": ["tool"], "cwd": ""},
        {"argv": ["tool"], "env_files": [""]},
        {"argv": ["tool"], "env": {"BAD=KEY": "value"}},
        {"argv": ["tool"], "env": {"KEY": "bad\0value"}},
    ):
        document = base_document()
        document["run"] = {"check": entry}
        with pytest.raises(ConfigError):
            parse_project_config(json.dumps(document).encode())

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_config(root, PROJECT_CONFIG_FILE, base_document())
        write_config(
            root,
            LOCAL_CONFIG_FILE,
            {
                "schema_version": 5,
                "run": {"local-only": {"argv": ["tool"]}},
            },
        )
        with pytest.raises(ConfigError, match="cannot create run entry"):
            load_config(root)


def test_non_files_and_symlinks_are_refused() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / PROJECT_CONFIG_FILE).mkdir()
        with pytest.raises(ConfigError):
            load_config(root)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "actual.json"
        target.write_text(json.dumps(base_document()), encoding="utf-8")
        try:
            os.symlink(target, root / PROJECT_CONFIG_FILE)
        except OSError as error:
            pytest.skip(f"symlinks unavailable: {error}")
        with pytest.raises(ConfigError):
            load_config(root)


def test_scope_stop_and_discriminated_models_enforce_bounded_contract() -> None:
    document = base_document()
    target = document["dev"]["resources"]["frontend"]
    target["scope"] = "host"
    with pytest.raises(ConfigError):
        parse_project_config(json.dumps(document).encode())
    target["host_key"] = "local-machine"
    target["observations"]["ready"]["probe"] = {
        "kind": "exec",
        "argv": ["check"],
        "timeout": 1,
        "output_limit": 100,
    }
    target["actions"] = {
        "stop": {
            "kind": "manual",
            "intent": "停止",
            "effect_scope": "当前实例",
            "steps": ["请运行 stop"],
        }
    }
    parsed = parse_project_config(json.dumps(document).encode())
    assert parsed.dev is not None
    assert parsed.dev.resources["frontend"].scope == "host"

    target["actions"]["stop"] = {
        "kind": "exec",
        "intent": "停止",
        "effect_scope": "当前实例",
        "argv": ["stop"],
        "interruption": "terminate",
        "timeout": 86401,
    }
    with pytest.raises(ConfigError):
        parse_project_config(json.dumps(document).encode())
