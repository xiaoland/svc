from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from svc_cli.cli import EXIT_CONFLICT, EXIT_OK, main
from tests.project_contract import write_project_config


def invoke(arguments: list[str]) -> tuple[int, dict[str, object], str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(arguments)
    payload = (
        json.loads(stdout.getvalue())
        if stdout.getvalue()
        else json.loads(stderr.getvalue())
    )
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
            "--regex",
            r"^assets/templates/AGENTS\.local\.template\.md$",
            "--scope",
            "path",
            "--limit",
            "1",
            "--json",
        ]
    )
    assert code == EXIT_OK
    assert payload["matches"][0]["path"] == "assets/templates/AGENTS.local.template.md"
    assert payload["matches"][0]["surface"] == "path"
    assert "content" not in payload["matches"][0]


def test_machine_json_is_compact_for_results_and_errors() -> None:
    code, stdout, stderr = invoke_text(["lookup", "--list", "--json"])

    assert (code, stderr) == (EXIT_OK, "")
    assert assert_compact_json(stdout)["command"] == "lookup"

    code, stdout, stderr = invoke_text(["status", "--unknown", "--json"])

    assert (code, stdout) == (2, "")
    assert assert_compact_json(stderr)["code"] == "invalid-cli-usage"

    code, stdout, stderr = invoke_text(["lookup", "--path", "../invalid.md", "--json"])

    assert (code, stdout) == (2, "")
    assert assert_compact_json(stderr)["error"]["code"] == "invalid-document-path"


def test_lookup_list_and_path_form_a_small_machine_navigation_contract() -> None:
    code, listing, stderr = invoke(["lookup", "--list", "--json"])

    assert code == EXIT_OK
    assert stderr == ""
    assert set(listing) == {
        "schema_version",
        "command",
        "corpus_version",
        "mode",
        "prefix",
        "entries",
    }
    assert listing["mode"] == "list"
    entries = listing["entries"]
    assert isinstance(entries, list)
    assert entries
    assert [item["path"] for item in entries] == sorted(
        item["path"] for item in entries
    )
    sections = next(item for item in entries if item["path"] == "sections/")
    assert sections["kind"] == "directory"

    code, nested, stderr = invoke(["lookup", "--list", sections["path"], "--json"])
    assert (code, stderr) == (EXIT_OK, "")
    selected = next(
        item
        for item in nested["entries"]
        if item["path"] == "sections/working-protocol.md"
    )
    code, document, stderr = invoke(["lookup", "--path", selected["path"], "--json"])

    assert code == EXIT_OK
    assert stderr == ""
    assert document["mode"] == "path"
    assert document["document"]["path"] == selected["path"]
    assert document["document"]["sha256"] == selected["sha256"]
    assert "content" in document["document"]


def test_lookup_help_and_failures_close_the_discovery_loop() -> None:
    code, stdout, stderr = invoke_text(["--help"])
    assert code == EXIT_OK
    assert stderr == ""
    assert "svc lookup --help" in stdout

    code, stdout, stderr = invoke_text(["lookup", "--help"])
    assert code == EXIT_OK
    assert stderr == ""
    assert "--list" in stdout
    assert "--path" in stdout
    assert "--regex" in stdout
    assert "SVC CLI usage" in stdout

    code, stdout, stderr = invoke_text(["lookup", "--list"])
    assert code == EXIT_OK
    assert stderr == ""
    assert "sections/" in stdout
    assert "Expand: svc lookup --list <directory>" in stdout

    code, payload, stderr = invoke(
        ["lookup", "--path", "sections/missing.md", "--json"]
    )
    assert code == EXIT_CONFLICT
    assert payload["error"]["code"] == "lookup-not-found"
    assert stderr

    code, _, stderr = invoke_text(["lookup", "--path", "../working-protocol.md"])
    assert code == 2
    assert "invalid-document-path" in stderr

    code, payload, _ = invoke(["lookup", "--name", ".*", "--json"])
    assert code == 2
    assert payload["code"] == "invalid-cli-usage"

    code, payload, _ = invoke(["lookup", "--list", "--limit", "1", "--json"])
    assert code == 2
    assert payload["error"]["code"] == "invalid-lookup-options"
    assert payload["error"]["message"] == (
        "--limit does not apply to --list or --path."
    )

    code, _, stderr = invoke_text([])
    assert code == 2
    assert "Hint: Use `svc lookup --help`" in stderr


def test_init_cli_is_plan_first_and_enforces_its_exact_apply_digest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        code, plan, _ = invoke(["init", str(root), "--json"])
        assert code == EXIT_OK
        assert list(root.iterdir()) == []
        digest = str(plan["plan_digest"])

        wrong_code, wrong, _ = invoke(
            ["init", str(root), "--apply", "0" * 64, "--json"]
        )
        assert wrong_code == EXIT_CONFLICT
        assert wrong["error"]["code"] == "plan-digest-mismatch"

        applied_code, applied, _ = invoke(
            ["init", str(root), "--apply", digest, "--json"]
        )
        assert applied_code == EXIT_OK
        assert applied["status"] == "applied"


def test_upgrade_cli_routes_config_before_corpus_with_compact_receipts() -> None:
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
                                    "web": {
                                        "probe": {
                                            "kind": "exec",
                                            "argv": ["check", "${dev.profile}"],
                                        },
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

        code, stdout, stderr = invoke_text(["upgrade", tmp, "--json"])
        assert (code, stderr) == (EXIT_CONFLICT, "")
        config = assert_compact_json(stdout)
        assert (config["target"], config["status"]) == (
            "config",
            "migration-required",
        )

        code, stdout, stderr = invoke_text(
            [
                "upgrade",
                tmp,
                "--target",
                "config",
                "--apply",
                str(config["plan_digest"]),
                "--json",
            ]
        )
        assert (code, stderr) == (EXIT_OK, "")
        applied = assert_compact_json(stdout)
        assert applied["status"] == "applied"
        assert applied["remaining_targets"][0]["target"] == "corpus"

        code, corpus, stderr = invoke(["upgrade", tmp, "--json"])
        assert (code, stderr) == (EXIT_CONFLICT, "")
        assert (corpus["target"], corpus["status"]) == (
            "corpus",
            "migration-required",
        )


def test_upgrade_help_explains_independent_project_targets() -> None:
    code, stdout, stderr = invoke_text(["upgrade", "--help"])

    assert (code, stderr) == (EXIT_OK, "")
    assert "--target {config,corpus}" in stdout
    assert "does not update the CLI" in stdout
    assert "Agent/Human document work" in stdout


def test_dev_identity_and_missing_configuration_status_are_machine_readable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        code, identity, _ = invoke(["dev", "identity", "--repo", str(root), "--json"])
        assert code == EXIT_OK
        assert identity["command"] == "dev identity"
        assert identity["workspace"]["repository_kind"] == "non-git"
        assert "repository_id" in identity["workspace"]
        assert "repo_common_id" not in identity["workspace"]

        text_code, stdout, stderr = invoke_text(
            ["dev", "identity", "--repo", str(root)]
        )
        assert (text_code, stderr) == (EXIT_OK, "")
        assert "svc dev identity\ninstance:" in stdout
        assert f"root: {root.resolve()}" in stdout
        assert "repository: non-git " in stdout
        assert "worktree:" in stdout and "namespace:" in stdout

        code, status, _ = invoke(["dev", "status", "--repo", str(root), "--json"])
        assert code == EXIT_CONFLICT
        assert status["status"] == "invalid-configuration"


def test_dev_stop_expected_domain_result_is_compact_stdout_not_error_stderr() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_project_config(
            root,
            dev_targets={
                "server": {
                    "scope": "repository",
                    "probe": {
                        "kind": "exec",
                        "argv": [
                            sys.executable,
                            "-c",
                            "raise SystemExit(1)",
                        ],
                    },
                    "provision": {"kind": "manual"},
                }
            },
        )

        code, stdout, stderr = invoke_text(
            ["dev", "stop", "server", "--repo", str(root), "--json"]
        )

        assert (code, stderr) == (EXIT_CONFLICT, "")
        payload = assert_compact_json(stdout)
        assert payload["status"] == "manual-action-required"
        assert payload["ready"] is False
        assert "attempt" not in payload


def test_dev_status_and_ensure_preserve_bounded_native_probe_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        diagnostic = '{"code":"RECEIPT_MISSING","ready":false}'
        write_project_config(
            root,
            dev_targets={
                "builder": {
                    "scope": "repository",
                    "probe": {
                        "kind": "exec",
                        "argv": [
                            sys.executable,
                            "-c",
                            f"print({diagnostic!r}); raise SystemExit(1)",
                        ],
                    },
                    "provision": {"kind": "manual"},
                    "access": ["offline-receipt"],
                }
            },
        )

        status_code, status_stdout, status_stderr = invoke_text(
            ["dev", "status", "--repo", str(root), "--json"]
        )
        assert (status_code, status_stderr) == (EXIT_CONFLICT, "")
        status = assert_compact_json(status_stdout)
        target = status["targets"][0]
        assert target["probe"]["exit_code"] == 1
        assert target["probe"]["output"] == diagnostic + "\n"
        assert target["continuation"] == "manual-action-required"
        assert target["access"] == ["offline-receipt"]

        ensure_code, ensure_stdout, ensure_stderr = invoke_text(
            ["dev", "ensure", "builder", "--repo", str(root), "--json"]
        )
        assert (ensure_code, ensure_stderr) == (EXIT_CONFLICT, "")
        ensured = assert_compact_json(ensure_stdout)
        assert ensured["status"] == "manual-action-required"
        assert ensured["ready"] is False
        assert ensured["probe"]["output"] == diagnostic + "\n"

        text_code, text_stdout, text_stderr = invoke_text(
            ["dev", "ensure", "builder", "--repo", str(root)]
        )
        assert (text_code, text_stderr) == (EXIT_CONFLICT, "")
        assert "svc dev builder: manual-action-required" in text_stdout
        assert "Probe: exec exit 1" in text_stdout
        assert "Access: offline-receipt" in text_stdout
        assert "No SVC command can provision this target" in text_stdout


def test_root_status_is_the_machine_first_check_and_human_text_exposes_its_gate() -> (
    None
):
    with tempfile.TemporaryDirectory() as tmp:
        code, payload, stderr = invoke(["status", tmp, "--json"])

        assert (code, stderr) == (EXIT_CONFLICT, "")
        assert payload["status"] == "unadopted"
        assert payload["next"]["action"] == "plan-integration-establishment"
        assert payload["next"]["command"][:2] == ["svc", "init"]

        code, stdout, stderr = invoke_text(["status", tmp])

        assert (code, stderr) == (EXIT_CONFLICT, "")
        assert "SVC unadopted" in stdout
        assert "plan-integration-establishment" in stdout
        assert "svc init" in stdout


def test_removed_self_update_and_dev_setup_are_absent_from_help() -> None:
    code, stdout, stderr = invoke_text(["--help"])
    assert (code, stderr) == (EXIT_OK, "")
    assert "self-update" not in stdout

    code, stdout, stderr = invoke_text(["dev", "--help"])
    assert (code, stderr) == (EXIT_OK, "")
    assert "setup" not in stdout


def test_run_json_is_one_receipt_and_suppresses_native_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_project_config(
            root,
            run_entries={
                "fails": {
                    "argv": [
                        sys.executable,
                        "-c",
                        "import sys; print('native'); print('diagnostic', file=sys.stderr); sys.exit(7)",
                    ],
                    "env": {"PRIVATE_VALUE": "must-not-appear"},
                }
            },
        )
        code, stdout, stderr = invoke_text(
            ["run", "fails", "--repo", str(root), "--json"]
        )
        assert (code, stderr) == (7, "")
        payload = assert_compact_json(stdout)
        assert payload["schema_version"] == 2
        assert payload["state"] == "exited"
        assert payload["exit_code"] == 7
        assert stdout.count("\n") == 1
        assert "must-not-appear" not in stdout
        assert "workspace_instance" in payload
        assert "workspace_id" not in payload
        assert set(payload["logs"]) == {"stdout", "stderr"}
        assert payload["logs"]["stdout"]["bytes"] == len("native\n")
        assert payload["logs"]["stderr"]["bytes"] == len("diagnostic\n")

        execution_id = str(payload["execution_id"])
        code, inspected_stdout, inspected_stderr = invoke_text(
            ["run", "--inspect", execution_id, "--repo", str(root), "--json"]
        )
        assert (code, inspected_stderr) == (EXIT_OK, "")
        inspected = assert_compact_json(inspected_stdout)
        assert inspected["command"] == "run inspect"
        assert inspected["execution_id"] == execution_id

        code, inspect_text, inspect_errors = invoke_text(
            ["run", "--inspect", execution_id, "--repo", str(root)]
        )
        assert (code, inspect_errors) == (EXIT_OK, "")
        assert "svc run inspect: fails — exited 7" in inspect_text
        assert f"execution: {execution_id}" in inspect_text
        assert "$ " in inspect_text and "cwd:" in inspect_text
        assert "logs: stdout " in inspect_text and "stderr " in inspect_text


def test_run_text_keeps_native_channels_and_wrapper_facts_separate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_project_config(
            root,
            run_entries={
                "channels": {
                    "argv": [
                        sys.executable,
                        "-c",
                        "import sys; print('native-out'); print('native-err', file=sys.stderr)",
                    ]
                }
            },
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "svc_cli.cli",
                "run",
                "channels",
                "--repo",
                str(root),
            ],
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
        assert "logs: stdout " in completed.stderr


def test_run_grammar_requires_exactly_one_selector() -> None:
    code, stdout, stderr = invoke_text(["run", "--json"])
    assert (code, stdout) == (2, "")
    assert assert_compact_json(stderr)["code"] == "invalid-cli-usage"

    code, stdout, stderr = invoke_text(["run", "check", "--follow", "bad", "--json"])
    assert (code, stdout) == (2, "")
    assert assert_compact_json(stderr)["code"] == "invalid-cli-usage"


def test_unknown_run_entry_returns_bounded_committed_names() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_project_config(
            root,
            run_entries={
                "lint": {"argv": ["lint"]},
                "test": {"argv": ["test"]},
            },
        )

        code, stdout, stderr = invoke_text(
            ["run", "missing", "--repo", str(root), "--json"]
        )

        assert (code, stdout) == (EXIT_CONFLICT, "")
        error = assert_compact_json(stderr)["error"]
        assert error["code"] == "unknown-run-entry"
        assert error["details"]["available_entries"] == ["lint", "test"]
