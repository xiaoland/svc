from __future__ import annotations

import io
import json
import subprocess
import sys
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


def assert_compact_json(raw: str) -> dict[str, object]:
    assert raw.endswith("\n")
    assert raw.count("\n") == 1
    return json.loads(raw)


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


def test_machine_json_is_compact_for_results_and_errors() -> None:
    code, stdout, stderr = invoke_text(["lookup", "--list", "--json"])

    assert (code, stderr) == (EXIT_OK, "")
    assert assert_compact_json(stdout)["command"] == "lookup"

    code, stdout, stderr = invoke_text(["status", "--unknown", "--json"])

    assert (code, stdout) == (2, "")
    assert assert_compact_json(stderr)["code"] == "invalid-cli-usage"

    code, stdout, stderr = invoke_text(["lookup", "--path", "../invalid.md", "--json"])

    assert (code, stdout) == (EXIT_CONFLICT, "")
    assert assert_compact_json(stderr)["error"]["code"] == "invalid-document-path"


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


def test_root_status_is_the_machine_first_check_and_human_text_exposes_its_gate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        code, payload, stderr = invoke(["status", tmp, "--json"])

        assert (code, stderr) == (EXIT_CONFLICT, "")
        assert payload["status"] == "unadopted"
        assert payload["next"]["action"] == "request-adoption-authorization"
        assert payload["next"]["requires_human_authorization"]

        code, stdout, stderr = invoke_text(["status", tmp])

        assert (code, stderr) == (EXIT_CONFLICT, "")
        assert "SVC status: unadopted" in stdout
        assert "request-adoption-authorization" in stdout
        assert "Human authorization required" in stdout


def test_root_status_json_is_compact_across_preflight_states() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        code, stdout, stderr = invoke_text(["status", tmp, "--json"])

        assert (code, stderr) == (EXIT_CONFLICT, "")
        unadopted = assert_compact_json(stdout)
        assert (unadopted["status"], unadopted["next"]["requires_human_authorization"]) == (
            "unadopted",
            True,
        )

        code, plan, _ = invoke(["init", tmp, "--json"])
        assert code == EXIT_OK
        code, stdout, stderr = invoke_text(
            ["init", tmp, "--apply", str(plan["plan_digest"]), "--json"]
        )
        assert (code, stderr) == (EXIT_OK, "")
        assert assert_compact_json(stdout)["status"] == "applied"

        code, stdout, stderr = invoke_text(["status", tmp, "--json"])

        assert (code, stderr) == (EXIT_OK, "")
        healthy = assert_compact_json(stdout)
        assert (healthy["status"], healthy["next"]["requires_human_authorization"]) == (
            "healthy",
            False,
        )

        (root / "svc.json").write_text("{not-json", encoding="utf-8")
        code, stdout, stderr = invoke_text(["status", tmp, "--json"])

        assert (code, stderr) == (EXIT_CONFLICT, "")
        malformed = assert_compact_json(stdout)
        assert (malformed["status"], malformed["next"]["requires_human_authorization"]) == (
            "malformed",
            True,
        )


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


def test_run_json_is_one_receipt_and_suppresses_native_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "svc.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "svc_version": "11.0.0",
                    "run": {
                        "fails": {
                            "argv": [sys.executable, "-c", "import sys; print('native'); print('diagnostic', file=sys.stderr); sys.exit(7)"],
                            "env": {"PRIVATE_VALUE": "must-not-appear"},
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        code, stdout, stderr = invoke_text(["run", "fails", "--repo", str(root), "--json"])
        assert (code, stderr) == (7, "")
        payload = assert_compact_json(stdout)
        assert payload["state"] == "exited"
        assert payload["exit_code"] == 7
        assert stdout.count("\n") == 1
        assert "must-not-appear" not in stdout

        execution_id = str(payload["execution_id"])
        code, inspected_stdout, inspected_stderr = invoke_text(
            ["run", "--inspect", execution_id, "--repo", str(root), "--json"]
        )
        assert (code, inspected_stderr) == (EXIT_OK, "")
        inspected = assert_compact_json(inspected_stdout)
        assert inspected["command"] == "run inspect"
        assert inspected["execution_id"] == execution_id


def test_run_text_keeps_native_channels_and_wrapper_facts_separate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "svc.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "svc_version": "11.0.0",
                    "run": {
                        "channels": {
                            "argv": [
                                sys.executable,
                                "-c",
                                "import sys; print('native-out'); print('native-err', file=sys.stderr)",
                            ]
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [sys.executable, "-m", "svc_cli.cli", "run", "channels", "--repo", str(root)],
            cwd=Path(__file__).parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0
        assert completed.stdout == "native-out\n"
        assert "native-err\n" in completed.stderr
        assert "svc run channels: owner" in completed.stderr
        assert "$ " in completed.stderr
        assert "svc run channels: exited 0" in completed.stderr


def test_run_grammar_requires_exactly_one_selector() -> None:
    code, stdout, stderr = invoke_text(["run", "--json"])
    assert (code, stdout) == (2, "")
    assert assert_compact_json(stderr)["code"] == "invalid-cli-usage"

    code, stdout, stderr = invoke_text(["run", "check", "--follow", "bad", "--json"])
    assert (code, stdout) == (2, "")
    assert assert_compact_json(stderr)["code"] == "invalid-cli-usage"
