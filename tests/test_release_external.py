from __future__ import annotations

import pytest

from tools.release import (
    classify_bundle_retention,
    classify_github_state,
    classify_pypi_state,
)


def test_target_pypi_state_classifier_is_exact_and_fail_closed() -> None:
    hashes = {"a.whl": "a" * 64, "a.tar.gz": "b" * 64}
    cases = (
        (
            "release-absent",
            {"http_status": 404, "body": None},
            {"state": "none"},
        ),
        (
            "manifest-bound-subset",
            {
                "http_status": 200,
                "body": {
                    "urls": [
                        {
                            "filename": "a.whl",
                            "digests": {"sha256": "a" * 64},
                        }
                    ]
                },
            },
            {
                "state": "exact-subset",
                "upload": ["a.tar.gz"],
                "readback_required": True,
                "ready_for_github": False,
            },
        ),
        (
            "digest-mismatch",
            {
                "http_status": 200,
                "body": {
                    "urls": [
                        {
                            "filename": "a.whl",
                            "digests": {"sha256": "0" * 64},
                        }
                    ]
                },
            },
            {"state": "mismatch"},
        ),
        (
            "all-manifest-bound-files",
            {
                "http_status": 200,
                "body": {
                    "urls": [
                        {"filename": name, "digests": {"sha256": digest}}
                        for name, digest in hashes.items()
                    ]
                },
            },
            {
                "state": "all-exact",
                "ready_for_github": True,
                "upload": [],
            },
        ),
        (
            "unexpected-file",
            {
                "http_status": 200,
                "body": {
                    "urls": [
                        *[
                            {
                                "filename": name,
                                "digests": {"sha256": digest},
                            }
                            for name, digest in hashes.items()
                        ],
                        {
                            "filename": "unknown.whl",
                            "digests": {"sha256": "0" * 64},
                        },
                    ]
                },
            },
            {"state": "mismatch", "unexpected": ["unknown.whl"]},
        ),
    )
    for case_name, observation, expected in cases:
        classified = classify_pypi_state(hashes, observation)
        for field, expected_value in expected.items():
            assert classified[field] == expected_value, f"{case_name}:{field}"


def test_target_github_state_classifier_is_exact_and_fail_closed() -> None:
    hashes = {"a.whl": "a" * 64, "a.tar.gz": "b" * 64}
    expected = {
        "tag": "v11.0.1",
        "commit": "1" * 40,
        "title": "SVC 11.0.1",
        "notes": "notes",
        "assets": hashes,
    }
    cases = (
        (
            "manifest-bound-draft-subset",
            {
                "http_status": 200,
                "resolved_tag_commit": "1" * 40,
                "asset_sha256": {"a.whl": "a" * 64},
                "body": {
                    "tag_name": "v11.0.1",
                    "target_commitish": "main",
                    "name": "SVC 11.0.1",
                    "body": "notes",
                    "draft": True,
                    "immutable": False,
                    "assets": [{"name": "a.whl"}],
                },
            },
            {"state": "draft-subset", "upload": ["a.tar.gz"]},
        ),
        (
            "resolved-tag-commit-mismatch",
            {
                "http_status": 200,
                "resolved_tag_commit": "2" * 40,
                "asset_sha256": hashes,
                "body": {
                    "tag_name": "v11.0.1",
                    "name": "SVC 11.0.1",
                    "body": "notes",
                    "draft": False,
                    "immutable": True,
                    "assets": [{"name": name} for name in hashes],
                },
            },
            {"state": "mismatch"},
        ),
    )
    for case_name, observation, expected_fields in cases:
        classified = classify_github_state(expected, observation)
        for field, expected_value in expected_fields.items():
            assert classified[field] == expected_value, f"{case_name}:{field}"


def live_bundle_retention_case() -> tuple[dict[str, object], dict[str, object]]:
    expected = {
        "run_id": 42,
        "name": "svc-release-v11.0.1",
        "commit": "1" * 40,
    }
    observed = {
        "run": {
            "http_status": 200,
            "body": {
                "id": 42,
                "path": ".github/workflows/publish.yml@main",
                "event": "push",
                "head_sha": "1" * 40,
                "status": "completed",
                "conclusion": "failure",
            },
        },
        "artifacts": {
            "http_status": 200,
            "body": {
                "artifacts": [
                    {
                        "id": 7,
                        "name": "svc-release-v11.0.1",
                        "expired": False,
                        "expires_at": "2027-01-01T00:00:00Z",
                    }
                ]
            },
        },
    }
    return expected, observed


def test_target_bundle_retention_accepts_the_exact_live_artifact() -> None:
    expected, observed = live_bundle_retention_case()
    result = classify_bundle_retention(
        expected,
        observed,
        now="2026-09-01T00:00:00Z",
    )
    assert result["state"] == "available"
    assert result["artifact_id"] == 7


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    (
        pytest.param(
            "path",
            ".github/workflows/ci.yml",
            id="wrong-workflow-path",
        ),
        pytest.param("head_sha", "2" * 40, id="wrong-head-commit"),
        pytest.param("event", "pull_request", id="wrong-trigger-event"),
        pytest.param("status", "in_progress", id="run-not-completed"),
    ),
)
def test_target_bundle_retention_rejects_wrong_run_identity_or_status(
    field: str,
    wrong_value: object,
) -> None:
    expected, observed = live_bundle_retention_case()
    run = observed["run"]
    assert isinstance(run, dict)
    body = run["body"]
    assert isinstance(body, dict)
    body[field] = wrong_value

    assert classify_bundle_retention(
        expected,
        observed,
        now="2026-09-01T00:00:00Z",
    )["state"] == "mismatch"


def test_target_bundle_retention_enforces_expiry_and_minimum_window() -> None:
    expected, observed = live_bundle_retention_case()
    artifacts = observed["artifacts"]
    assert isinstance(artifacts, dict)
    body = artifacts["body"]
    assert isinstance(body, dict)
    entries = body["artifacts"]
    assert isinstance(entries, list)
    artifact = entries[0]
    assert isinstance(artifact, dict)
    artifact["expired"] = True
    assert classify_bundle_retention(
        expected,
        observed,
        now="2026-09-01T00:00:00Z",
    )["state"] == "expired"

    artifact["expired"] = False
    artifact["expires_at"] = "2026-09-02T00:00:00Z"
    assert classify_bundle_retention(
        expected,
        observed,
        now="2026-09-01T00:00:00Z",
    )["state"] == "expired"
    assert classify_bundle_retention(
        expected,
        observed,
        now="2026-09-01T00:00:00Z",
        minimum_days=0,
    )["state"] == "available"
