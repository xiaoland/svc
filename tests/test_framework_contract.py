from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tools.build_monolith import MonolithBuilder


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"


def canonical_markdown_files() -> list[Path]:
    return sorted(path for path in SOURCE.rglob("*.md") if path.is_file())


def word_count(path: Path) -> int:
    return len(re.findall(r"\S+", path.read_text(encoding="utf-8")))


class FrameworkContractTests(unittest.TestCase):
    def test_all_canonical_markdown_links_resolve(self) -> None:
        for path in canonical_markdown_files():
            with self.subTest(path=path.relative_to(SOURCE).as_posix()):
                MonolithBuilder(SOURCE).build(path)

    def test_embedded_runtime_replaced_the_old_consumer_file_model(self) -> None:
        removed_code_roots = ["src/svc_cli", "src/tools", "src/.agents/codex-agents"]
        for relative in removed_code_roots:
            with self.subTest(path=relative):
                self.assertEqual(list((ROOT / relative).rglob("*.py")) if (ROOT / relative).exists() else [], [])
        fixtures = ROOT / "tests/fixtures/migrations"
        self.assertEqual([path for path in fixtures.rglob("*") if path.is_file()] if fixtures.exists() else [], [])
        self.assertTrue((ROOT / "svc_cli/cli.py").is_file())
        self.assertTrue((ROOT / "tools/build_catalog.py").is_file())
        self.assertTrue((ROOT / "tools/build_monolith.py").is_file())

        index = (SOURCE / "index.md").read_text(encoding="utf-8")
        self.assertIn("## Packaged Runtime Consumption", index)
        self.assertIn("svc lookup --name", index)
        self.assertNotIn("svc migrate", index)
        self.assertNotIn(".svc/state.json", index)
        self.assertIn("No SVC framework document is copied", index)

    def test_no_live_runtime_or_canonical_source_claims_the_removed_commands_or_state(self) -> None:
        paths = canonical_markdown_files()
        paths.extend(sorted((ROOT / "svc_cli").rglob("*.py")))
        paths.extend(sorted((ROOT / "tools").rglob("*.py")))
        paths.extend([ROOT / "pdm_build.py", ROOT / "pyproject.toml", ROOT / "README.md", ROOT / "CONTRIBUTING.md"])
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for obsolete in ("svc migrate", ".svc/state.json", "resolve_migrations", "src/svc_cli", "src/tools"):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, text)

    def test_release_metadata_is_not_a_consumer_file_inventory(self) -> None:
        metadata = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["schema_version"], 2)
        self.assertIn("behavioral_impact", metadata)
        self.assertNotIn("artifacts", metadata)
        self.assertIn(metadata["behavioral_impact"]["migration"]["status"], {"guide", "not-applicable"})

    def test_task_minimum_has_exactly_five_fields(self) -> None:
        paths = [
            "src/sections/working-protocol.md",
            "src/assets/templates/task-packet.template.md",
            "src/assets/templates/task-diagnostics-matrix.template.md",
        ]
        expected = ["Objective", "Guardrails", "Verification", "Current Truth", "Next Step"]
        for relative in paths:
            text = (ROOT / relative).read_text(encoding="utf-8")
            if relative == "src/sections/working-protocol.md":
                text = text.split("## Keep a Task Control Surface", 1)[1].split("\n## ", 1)[0]
            fields = re.findall(r"^- \*\*(Objective|Guardrails|Verification|Current Truth|Next Step)\*\*:", text, flags=re.MULTILINE)
            with self.subTest(path=relative):
                self.assertEqual(fields, expected)

    def test_pdm_exposes_runtime_and_repository_tools_from_their_new_locations(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('build-monolith = "python -m tools.build_monolith"', pyproject)
        self.assertIn('release = "python -m tools.release"', pyproject)
        self.assertIn('svc = "svc_cli.cli:main"', pyproject)
        self.assertIn('includes = ["svc_cli"]', pyproject)
        self.assertNotIn("package-dir = \"src\"", pyproject)

    def test_root_template_and_review_budgets_remain_bounded(self) -> None:
        root_template = SOURCE / "assets/templates/AGENTS.root.template.md"
        template = root_template.read_text(encoding="utf-8")
        for heading in ("## Repository Map", "## Knowledge Owners", "## Development Workflow", "## Execution Rules"):
            with self.subTest(heading=heading):
                self.assertIn(heading, template)
        for requirement in ("Replace every angle-bracket placeholder", "Task retention:", "Runtime data:", "Smoke/debug entry:"):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, template)

        protocol = SOURCE / "sections/working-protocol.md"
        taste = SOURCE / "sections/implementation-taste.md"
        self.assertLessEqual(word_count(root_template), 450)
        self.assertLessEqual(word_count(protocol), 650)
        self.assertLessEqual(word_count(taste), 650)

    def test_mutation_gate_has_one_canonical_heading(self) -> None:
        headings = []
        for path in canonical_markdown_files():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip() == "## Mutation Gate":
                    headings.append(path.relative_to(SOURCE).as_posix())
        self.assertEqual(headings, ["sections/working-protocol.md"])


if __name__ == "__main__":
    unittest.main()
