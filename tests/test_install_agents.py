from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.tools.install_agents import install_agents


class InstallAgentsTests(unittest.TestCase):
    def test_install_agents_copies_toml_files_to_provider_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            source_dir = repo_root / "src" / ".agents" / "codex-agents"
            source_dir.mkdir(parents=True)
            (source_dir / "impact_cartographer.toml").write_text(
                'name = "impact_cartographer"\n',
                encoding="utf-8",
            )
            (source_dir / "svc_task_steward.toml").write_text(
                'name = "svc_task_steward"\n',
                encoding="utf-8",
            )

            user_home = Path(tmp_dir) / "home"
            installed = install_agents(repo_root=repo_root, user_home=user_home)

            expected_dir = user_home / ".codex" / "agents"
            self.assertEqual(
                [path.name for path in installed],
                ["impact_cartographer.toml", "svc_task_steward.toml"],
            )
            self.assertTrue((expected_dir / "impact_cartographer.toml").exists())
            self.assertEqual(
                (expected_dir / "svc_task_steward.toml").read_text(encoding="utf-8"),
                'name = "svc_task_steward"\n',
            )

    def test_install_agents_overwrites_existing_target_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            source_dir = repo_root / "src" / ".agents" / "codex-agents"
            source_dir.mkdir(parents=True)
            (source_dir / "impact_cartographer.toml").write_text(
                'name = "fresh"\n',
                encoding="utf-8",
            )

            target_dir = Path(tmp_dir) / "target"
            target_dir.mkdir(parents=True)
            (target_dir / "impact_cartographer.toml").write_text(
                'name = "stale"\n',
                encoding="utf-8",
            )

            install_agents(repo_root=repo_root, target_dir=target_dir)

            self.assertEqual(
                (target_dir / "impact_cartographer.toml").read_text(encoding="utf-8"),
                'name = "fresh"\n',
            )

    def test_install_agents_rejects_unknown_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "repo"
            repo_root.mkdir(parents=True)

            with self.assertRaises(ValueError):
                install_agents(provider="unknown", repo_root=repo_root)


if __name__ == "__main__":
    unittest.main()
