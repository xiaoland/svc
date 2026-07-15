from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from svc_cli.config import ConfigError, LOCAL_CONFIG_FILE, PROJECT_CONFIG_FILE, load_config, parse_local_overlay, parse_project_config


def base_document() -> dict[str, object]:
    return {
        "schema_version": 2,
        "svc_version": "10.0.1",
        "dev": {
            "profile": "worktree",
            "profiles": {
                "worktree": {
                    "targets": {
                        "frontend": {
                            "probe": {"kind": "http", "url": "https://frontend-${dev.instance}.localhost/health", "success_status": [200, 399]},
                            "provision": {"kind": "exec", "mode": "run", "argv": ["pnpm", "dev"]},
                            "access": ["https://frontend-${dev.instance}.localhost/"],
                        }
                    }
                },
                "shared": {
                    "targets": {
                        "database": {
                            "scope": "repository",
                            "probe": {"kind": "tcp", "host": "127.0.0.1", "port": 5432},
                            "provision": {"kind": "manual"},
                        }
                    }
                },
            },
        },
    }


class ConfigurationTests(unittest.TestCase):
    def write(self, root: Path, name: str, value: object) -> None:
        (root / name).write_text(json.dumps(value), encoding="utf-8")

    def test_complete_strict_base_and_stable_declaration_digests(self) -> None:
        document = base_document()
        first = parse_project_config(json.dumps(document).encode())
        second = parse_project_config(json.dumps(document, indent=2).encode())
        self.assertEqual(first.dev.profiles["worktree"].targets["frontend"].scope, "worktree")
        self.assertEqual(first.model_dump(), second.model_dump())

        for invalid in (
            {"schema_version": 2, "svc_version": "10.0.1", "unknown": True},
            {"schema_version": 2, "svc_version": "10.0.1", "dev": {"profile": "missing", "profiles": {}}},
            {"schema_version": 2, "svc_version": "not-a-version"},
        ):
            with self.assertRaises(ConfigError):
                parse_project_config(json.dumps(invalid).encode())

    def test_parser_rejects_duplicate_nonfinite_invalid_utf8_and_null(self) -> None:
        for content in (
            b'{"schema_version":2,"schema_version":2,"svc_version":"10.0.1"}',
            b'{"schema_version":2,"svc_version":"10.0.1","dev":NaN}',
            b'{"schema_version":2,"svc_version":"10.0.1","dev":null}',
            b'\xff',
        ):
            with self.assertRaises(ConfigError):
                parse_project_config(content)

    def test_sparse_overlay_merges_objects_and_replaces_scalars_and_arrays(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, PROJECT_CONFIG_FILE, base_document())
            self.write(
                root,
                LOCAL_CONFIG_FILE,
                {
                    "dev": {
                        "profile": "shared",
                        "profiles": {
                            "worktree": {
                                "targets": {
                                    "frontend": {
                                        "access": ["http://127.0.0.1:3000/"],
                                        "provision": {"env": {"PORT": "3000"}},
                                    }
                                }
                            }
                        },
                    }
                },
            )
            resolved = load_config(root)
            target = resolved.effective.dev.profiles["worktree"].targets["frontend"]
            self.assertEqual(resolved.effective.dev.profile, "shared")
            self.assertEqual(target.access, ["http://127.0.0.1:3000/"])
            self.assertEqual(target.provision.env, {"PORT": "3000"})
            self.assertIsNotNone(resolved.local_digest)
            self.assertNotEqual(resolved.base_digest, resolved.effective_digest)

    def test_absent_overlay_is_noop_and_effective_config_is_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, PROJECT_CONFIG_FILE, base_document())
            before = sorted(path.name for path in root.iterdir())
            resolved = load_config(root)
            self.assertIsNone(resolved.local)
            self.assertEqual(resolved.base, resolved.effective)
            self.assertEqual(sorted(path.name for path in root.iterdir()), before)

            self.write(root, LOCAL_CONFIG_FILE, {})
            empty_overlay = load_config(root)
            self.assertEqual(empty_overlay.base, empty_overlay.effective)
            self.assertIsNotNone(empty_overlay.local_digest)

    def test_overlay_refuses_adoption_authority_unknown_paths_and_invalid_effective_values(self) -> None:
        for overlay in (
            {"schema_version": 2},
            {"svc_version": "10.0.2"},
            {"profile": "worktree"},
            {"dev": {"profiles": {"worktree": {"bad": True}}}},
            {"dev": {"profiles": {"worktree": {"targets": {"frontend": {"probe": {"kind": "http", "made_up": True}}}}}}},
        ):
            with self.assertRaises(ConfigError):
                parse_local_overlay(json.dumps(overlay).encode())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, PROJECT_CONFIG_FILE, base_document())
            self.write(root, LOCAL_CONFIG_FILE, {"dev": {"profile": "does-not-exist"}})
            with self.assertRaises(ConfigError):
                load_config(root)

    def test_non_files_and_symlinks_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / PROJECT_CONFIG_FILE).mkdir()
            with self.assertRaises(ConfigError):
                load_config(root)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "actual.json"
            target.write_text(json.dumps(base_document()), encoding="utf-8")
            try:
                os.symlink(target, root / PROJECT_CONFIG_FILE)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaises(ConfigError):
                load_config(root)

    def test_scope_and_discriminated_models_enforce_bounded_contract(self) -> None:
        document = base_document()
        target = document["dev"]["profiles"]["worktree"]["targets"]["frontend"]
        target["scope"] = "host"
        with self.assertRaises(ConfigError):
            parse_project_config(json.dumps(document).encode())
        target["host_key"] = "local-machine"
        target["probe"] = {"kind": "exec", "argv": ["check"], "timeout": 1, "output_limit": 100}
        target["provision"] = {"kind": "manual"}
        self.assertEqual(parse_project_config(json.dumps(document).encode()).dev.profiles["worktree"].targets["frontend"].scope, "host")


if __name__ == "__main__":
    unittest.main()
