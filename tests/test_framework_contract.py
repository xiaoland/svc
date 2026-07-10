from __future__ import annotations

import re
import unittest
from pathlib import Path

from src.tools.build_monolith import MonolithBuilder


REPO_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_MARKDOWN_ROOTS = {".git", ".venv", "build", "tasks"}


def canonical_markdown_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*.md"):
        relative = path.relative_to(REPO_ROOT)
        if relative.parts and relative.parts[0] in EXCLUDED_MARKDOWN_ROOTS:
            continue
        files.append(path)
    return sorted(files)


def word_count(path: Path) -> int:
    return len(re.findall(r"\S+", path.read_text(encoding="utf-8")))


class FrameworkContractTests(unittest.TestCase):
    def test_all_canonical_markdown_links_resolve(self) -> None:
        for path in canonical_markdown_files():
            with self.subTest(path=path.relative_to(REPO_ROOT).as_posix()):
                MonolithBuilder(REPO_ROOT).build(path)

    def test_obsolete_protocol_surfaces_are_absent(self) -> None:
        removed_paths = [
            ".agents/skills/init-svc",
            ".agents/skills/edit-svc-shared-docs",
            "SEQUENCE_OF_USE.md",
            "src/.agents/codex-agents/impact_cartographer.toml",
            "src/.agents/codex-agents/svc_local_context_loader.toml",
            "src/.agents/codex-agents/svc_task_steward.toml",
            "src/assets/mappings/durable-destination-map.md",
            "src/sections/alignment.md",
            "src/sections/filesystem.md",
            "src/sections/meta-engine.md",
            "src/sections/migration-guidance.md",
            "src/sections/multi-repo.md",
            "src/sections/ontology.md",
            "src/sections/promotion-rules.md",
            "src/sections/tasks.md",
            "src/assets/templates/concepts.template.md",
            "src/assets/templates/input-artifact.template.md",
            "src/assets/templates/input-constraint.template.md",
            "src/assets/templates/input-intent.template.md",
            "src/assets/templates/input-reality.template.md",
            "src/assets/templates/mode-a-explore.template.md",
            "src/assets/templates/mode-b-solidify.template.md",
            "src/assets/templates/mode-c-execute.template.md",
            "src/assets/templates/mode-d-diagnose.template.md",
            "src/assets/templates/prd-file-set.template.md",
            "src/assets/templates/product-tdd-file-set.template.md",
            "src/tools/install_agents.py",
            "scripts/build_monolith.py",
            "tests/test_install_agents.py",
        ]
        for relative in removed_paths:
            with self.subTest(path=relative):
                self.assertFalse((REPO_ROOT / relative).exists())

    def test_no_live_reference_uses_removed_protocol_names(self) -> None:
        obsolete = (
            "meta-engine.md",
            "migration-guidance.md",
            "durable-destination-map.md",
            "input-intent.template.md",
            "input-constraint.template.md",
            "input-reality.template.md",
            "input-artifact.template.md",
            "mode-a-explore.template.md",
            "mode-b-solidify.template.md",
            "mode-c-execute.template.md",
            "mode-d-diagnose.template.md",
            "init-svc",
            "edit-svc-shared-docs",
            "install-agents",
        )
        files = [path for path in canonical_markdown_files() if path.name != "CHANGELOG.md"]
        files.extend(sorted((REPO_ROOT / "src").rglob("*.py")))
        files.extend(sorted((REPO_ROOT / "src").rglob("*.toml")))
        files.append(REPO_ROOT / "pyproject.toml")
        text = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for name in obsolete:
            with self.subTest(name=name):
                self.assertNotIn(name, text)

    def test_consumer_templates_do_not_use_removed_protocol_fields(self) -> None:
        deployment = (
            REPO_ROOT / "src/assets/templates/deployment-runbook.template.md"
        ).read_text(encoding="utf-8")
        shared_docs = (
            REPO_ROOT / "src/assets/templates/edit-shared-docs.template.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("switch mode to C", deployment)
        self.assertNotIn("- owning route:", shared_docs)

    def test_task_minimum_has_exactly_five_fields(self) -> None:
        paths = [
            "src/sections/working-protocol.md",
            "src/assets/templates/task-packet.template.md",
            "src/assets/templates/task-diagnostics-matrix.template.md",
        ]
        expected = ["Objective", "Guardrails", "Verification", "Current Truth", "Next Step"]
        for relative in paths:
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            if relative == "src/sections/working-protocol.md":
                text = text.split("## Keep a Task Control Surface", 1)[1].split("\n## ", 1)[0]
            fields = re.findall(
                r"^- \*\*(Objective|Guardrails|Verification|Current Truth|Next Step)\*\*:",
                text,
                flags=re.MULTILINE,
            )
            with self.subTest(path=relative):
                self.assertEqual(fields, expected)

    def test_minimal_consumer_kernel_has_exactly_four_documents(self) -> None:
        index = (REPO_ROOT / "src/index.md").read_text(encoding="utf-8")
        match = re.search(
            r"## Minimal Consumer Kernel.*?```text\n(.*?)```",
            index,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        paths = [line.strip() for line in match.group(1).splitlines() if line.strip()]
        self.assertEqual(
            paths,
            [
                "AGENTS.md",
                "docs/00-meta/working-protocol.md",
                "docs/00-meta/implementation-taste.md",
                "docs/10-prd/README.md",
            ],
        )

    def test_pdm_exposes_only_supported_commands(self) -> None:
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('build-monolith = "python -m src.tools.build_monolith"', pyproject)
        self.assertIn("test = \"python -m unittest discover", pyproject)
        self.assertNotIn("install-agents", pyproject)

    def test_root_template_requires_capability_closure(self) -> None:
        template = (
            REPO_ROOT / "src/assets/templates/AGENTS.root.template.md"
        ).read_text(encoding="utf-8")
        for heading in (
            "## Repository Map",
            "## Knowledge Owners",
            "## Development Workflow",
            "## Execution Rules",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, template)
        for requirement in (
            "Replace every angle-bracket placeholder",
            "Task retention:",
            "Runtime data:",
            "Smoke/debug entry:",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, template)

    def test_review_budgets(self) -> None:
        root = REPO_ROOT / "src/assets/templates/AGENTS.root.template.md"
        protocol = REPO_ROOT / "src/sections/working-protocol.md"
        taste = REPO_ROOT / "src/sections/implementation-taste.md"
        self.assertLessEqual(word_count(root), 450)
        self.assertLessEqual(word_count(protocol), 650)
        self.assertLessEqual(word_count(taste), 650)

        owners = [
            REPO_ROOT / "src/sections/prd.md",
            REPO_ROOT / "src/sections/product-tdd.md",
            REPO_ROOT / "src/sections/unit-tdd.md",
            REPO_ROOT / "src/sections/deployment.md",
        ]
        cold_start = word_count(root) + word_count(protocol) + max(map(word_count, owners))
        self.assertLessEqual(cold_start, 1900)

    def test_mutation_gate_has_one_canonical_heading(self) -> None:
        headings = []
        for path in canonical_markdown_files():
            if path.name == "CHANGELOG.md":
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip() == "## Mutation Gate":
                    headings.append(path.relative_to(REPO_ROOT).as_posix())
        self.assertEqual(headings, ["src/sections/working-protocol.md"])


if __name__ == "__main__":
    unittest.main()
