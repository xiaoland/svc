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


def invoke_text(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            code = main(arguments)
        except SystemExit as error:
            code = int(error.code or 0)
    return code, stdout.getvalue(), stderr.getvalue()


def test_lookup_machine_output_uses_source_relative_path_identity() -> None:
    code, payload, _ = invoke(
        [
            "lookup",
            "--name",
            r"assets/templates/AGENTS\.local\.template\.md",
            "--limit",
            "1",
            "--json",
        ]
    )
    assert code == EXIT_OK
    assert payload["results"][0]["path"] == "assets/templates/AGENTS.local.template.md"
    assert "content" in payload["results"][0]


def test_lookup_list_and_path_form_a_small_machine_navigation_contract() -> None:
    code, listing, stderr = invoke(["lookup", "--list", "--json"])

    assert code == EXIT_OK
    assert stderr == ""
    assert set(listing) == {"schema_version", "command", "mode", "results"}
    assert listing["mode"] == "list"
    results = listing["results"]
    assert isinstance(results, list)
    assert results
    assert [item["path"] for item in results] == sorted(
        item["path"] for item in results
    )
    assert all(set(item) == {"path", "title", "sha256"} for item in results)

    selected = next(
        item for item in results if item["path"] == "sections/working-protocol.md"
    )
    code, document, stderr = invoke(
        ["lookup", "--path", selected["path"], "--json"]
    )

    assert code == EXIT_OK
    assert stderr == ""
    assert document["mode"] == "path"
    assert document["query"] == selected["path"]
    assert document["results"][0]["sha256"] == selected["sha256"]
    assert "content" in document["results"][0]


def test_lookup_help_and_failures_close_the_discovery_loop() -> None:
    code, stdout, stderr = invoke_text(["--help"])
    assert code == EXIT_OK
    assert stderr == ""
    assert "svc lookup --list --json" in stdout
    assert "svc lookup --path <path> --json" in stdout

    code, stdout, stderr = invoke_text(["lookup", "--help"])
    assert code == EXIT_OK
    assert stderr == ""
    assert "--list" in stdout
    assert "--path" in stdout
    assert "svc lookup --list --json" in stdout

    code, stdout, stderr = invoke_text(["lookup", "--list"])
    assert code == EXIT_OK
    assert stderr == ""
    assert "sections/working-protocol.md\tWorking Protocol" in stdout
    assert "Read one document with `svc lookup --path <path> --json`." in stdout

    code, payload, stderr = invoke(
        ["lookup", "--path", "sections/missing.md", "--json"]
    )
    assert code == EXIT_CONFLICT
    assert payload["error"]["code"] == "lookup-not-found"
    assert "--list" in payload["error"]["details"]["hint"]
    assert stderr

    code, _, stderr = invoke_text(
        ["lookup", "--path", "../working-protocol.md"]
    )
    assert code == EXIT_CONFLICT
    assert "invalid-document-path" in stderr
    assert "Hint: Run `svc lookup --list --json`" in stderr

    code, payload, _ = invoke(["lookup", "--list", "--all", "--json"])
    assert code == EXIT_CONFLICT
    assert payload["error"]["code"] == "invalid-lookup-options"
    assert "--list" in payload["error"]["details"]["hint"]

    code, payload, _ = invoke(
        ["lookup", "--list", "--limit", "1", "--json"]
    )
    assert code == EXIT_CONFLICT
    assert payload["error"]["code"] == "invalid-lookup-options"
    assert payload["error"]["message"] == (
        "--limit does not apply to --list or --path."
    )

    code, _, stderr = invoke_text([])
    assert code == 2
    assert "Hint: Run `svc lookup --list --json`" in stderr


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
