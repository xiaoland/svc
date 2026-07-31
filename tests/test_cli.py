from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from svc_cli.cli import EXIT_CONFLICT, EXIT_OK, main


def invoke(arguments: list[str]) -> tuple[int, dict[str, object], str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(arguments)
    payload = json.loads(stdout.getvalue()) if stdout.getvalue() else json.loads(stderr.getvalue())
    return code, payload, stderr.getvalue()


def test_lookup_machine_output_uses_source_relative_path_identity() -> None:
    code, payload, _ = invoke(["lookup", "--name", r"assets/templates/AGENTS\.local\.template\.md", "--json"])
    assert code == EXIT_OK
    assert payload["results"][0]["path"] == "assets/templates/AGENTS.local.template.md"
    assert "content" in payload["results"][0]


def test_init_cli_is_plan_first_and_enforces_its_exact_apply_digest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        code, plan, _ = invoke(["init", str(root), "--json"])
        assert code == EXIT_OK
        assert list(root.iterdir()) == []
        digest = str(plan["plan_digest"])

        wrong_code, wrong, _ = invoke(["init", str(root), "--apply", "0" * 64, "--json"])
        assert wrong_code == EXIT_CONFLICT
        assert wrong["error"]["code"] == "plan-digest-mismatch"

        applied_code, applied, _ = invoke(["init", str(root), "--apply", digest, "--json"])
        assert applied_code == EXIT_OK
        assert applied["status"] == "applied"


def test_dev_identity_and_missing_configuration_status_are_machine_readable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        code, identity, _ = invoke(["dev", "identity", "--repo", str(root), "--json"])
        assert code == EXIT_OK
        assert identity["command"] == "dev identity"
        assert identity["workspace"]["repository_kind"] == "non-git"

        code, status, _ = invoke(["dev", "status", "--repo", str(root), "--json"])
        assert code == EXIT_CONFLICT
        assert status["status"] == "invalid-configuration"


def test_dev_setup_cli_is_plan_then_exact_apply() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "svc.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "svc_version": "10.0.1",
                    "dev": {
                        "profile": "local",
                        "profiles": {
                            "local": {
                                "targets": {
                                    "app": {
                                        "scope": "repository",
                                        "probe": {"kind": "exec", "argv": ["check"]},
                                        "provision": {"kind": "manual"},
                                    }
                                }
                            }
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        (root / "package.json").write_text('{"name":"fixture"}\n', encoding="utf-8")
        code, plan, _ = invoke(["dev", "setup", "npm", "app", "--repo", str(root), "--plan", "--json"])
        assert code == EXIT_OK
        assert plan["status"] == "ready"
        assert "svc:dev:app" not in (root / "package.json").read_text(encoding="utf-8")
        digest = str(plan["plan_digest"])

        code, applied, _ = invoke(["dev", "setup", "npm", "app", "--repo", str(root), "--apply", digest, "--json"])
        assert code == EXIT_OK
        assert applied["status"] == "applied"
        assert '"svc:dev:app": "svc dev ensure app"' in (root / "package.json").read_text(encoding="utf-8")
