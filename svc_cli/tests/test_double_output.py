from __future__ import annotations

import json
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from svc_cli.cli_output.double import (
    DoubleDiagnosticOutput,
    DoubleEmitOutput,
    DoubleJournalEntryOutput,
    DoubleJournalFactsOutput,
    DoubleJournalOutput,
    DoubleObserveOutput,
    DoubleReplayOutput,
    DoubleRunObservationOutput,
    DoubleRuntimeUnavailableOutput,
    DoubleSnapshotOutput,
    DoubleStartOutput,
    DoubleStopOutput,
    DoubleTargetOutput,
    DoubleValidateOutput,
)
from svc_cli.output_schema import (
    OUTPUT_SCHEMA_KEYS,
    generate_output_schema,
    read_output_schema,
)


def _replay() -> DoubleReplayOutput:
    return DoubleReplayOutput(
        seed=123,
        clock="2026-08-10T02:00:00Z",
        generators=("svc.opaque-token/v1",),
        validators=("svc.rfc-uuid/v1",),
        runtime="svc.double/v0",
    )


def _target() -> DoubleTargetOutput:
    return DoubleTargetOutput(
        name="consumer.payment-events",
        origin="http://127.0.0.1:9010",
        remote=False,
    )


def _observation(*, sealed: bool, status: str = "ready") -> DoubleRunObservationOutput:
    return DoubleRunObservationOutput(
        run_id="ad300eca-a210-4b09-873c-95bbffdc16b8",
        scenario_name="payment-confirmed",
        status=status,
        sealed=sealed,
        responder_url="http://127.0.0.1:43811",
        scenario_digest="a" * 64,
        run_context_digest="b" * 64,
        replay=_replay(),
        targets=(_target(),),
        bindings=("external_id", "payment_id"),
        journal=DoubleJournalOutput(
            total=2,
            retained=1,
            omitted=1,
            entries=(
                DoubleJournalEntryOutput(
                    sequence=2,
                    at="2026-08-10T02:00:01Z",
                    kind="event",
                    status="acknowledged",
                    facts=DoubleJournalFactsOutput(
                        event="payment.succeeded", request_sha256="c" * 64
                    ),
                ),
            ),
        ),
        nonclaims=("consumer-egress:not-enforced",),
    )


def test_validate_and_start_expose_identity_without_snapshot_content() -> None:
    validated = DoubleValidateOutput(
        module="/workspace/payment.double.yaml",
        scenario_name="payment-confirmed",
        claim="consumer exposes a paid order",
        valid=True,
        scenario_digest="a" * 64,
        fidelity=("selected-operation-schema",),
        nonclaims=("provider-behavior:not-claimed",),
        snapshots=(
            DoubleSnapshotOutput(
                logical_path="contracts/payment.openapi.yaml",
                sha256="b" * 64,
                bytes=417,
            ),
        ),
    )
    started = DoubleStartOutput(
        run_id="ad300eca-a210-4b09-873c-95bbffdc16b8",
        module=validated.module,
        scenario_name="payment-confirmed",
        responder_url="http://127.0.0.1:43811",
        scenario_digest="a" * 64,
        run_context_digest="c" * 64,
        replay=_replay(),
        targets=(_target(),),
        nonclaims=(
            "consumer-egress:not-enforced",
            "materializer-egress:not-enforced",
        ),
    )
    invalid = DoubleValidateOutput(
        module="/workspace/unsupported.double.yaml",
        valid=False,
        fidelity=(),
        nonclaims=(),
        snapshots=(),
        diagnostic=DoubleDiagnosticOutput(
            code="unsupported-language",
            message="language must be svc.double/v0",
            path="language",
            line=1,
            column=11,
        ),
    )

    assert "content_base64" not in json.dumps(validated.as_dict())
    assert invalid.valid is False
    assert started.as_dict()["replay"]["seed"] == 123
    assert started.as_dict()["run_context_digest"] == "c" * 64
    with pytest.raises(ValidationError):
        DoubleSnapshotOutput.model_validate(
            {
                "logical_path": "secret.bin",
                "sha256": "d" * 64,
                "bytes": 6,
                "content_base64": "c2VjcmV0",
            }
        )
    with pytest.raises(ValidationError):
        DoubleJournalFactsOutput.model_validate(
            {"event": "payment.succeeded", "control_capability": "secret"}
        )


def test_runtime_unavailable_and_event_acknowledgement_are_typed_results() -> None:
    unavailable = DoubleRuntimeUnavailableOutput(command="double validate")
    acknowledged = DoubleEmitOutput(
        run_id="ad300eca-a210-4b09-873c-95bbffdc16b8",
        event="payment.succeeded",
        status="acknowledged",
        target="http://127.0.0.1:9010/webhooks/payment",
        http_status=204,
    )
    transport_failure = DoubleEmitOutput(
        run_id=acknowledged.run_id,
        event=acknowledged.event,
        status="transport-failed",
        target="http://127.0.0.1:9010/webhooks/payment",
        reason="connection-refused",
    )

    assert unavailable.continuation == "pip install 'sustainable-vibe-coding[double]'"
    assert acknowledged.status == "acknowledged"
    assert transport_failure.http_status is None
    with pytest.raises(ValidationError, match="only a 2xx"):
        DoubleEmitOutput(
            run_id=acknowledged.run_id,
            event=acknowledged.event,
            status="acknowledged",
            target=acknowledged.target,
            http_status=302,
        )


def test_observe_distinguishes_active_sealed_and_last_unsealed_projection() -> None:
    active = DoubleObserveOutput(
        observation=_observation(sealed=False),
        authority="active-carrier",
        control_status="available",
    )
    sealed = DoubleObserveOutput(
        observation=_observation(sealed=True, status="stopped"),
        authority="sealed-snapshot",
        control_status="not-required",
    )
    unavailable = DoubleObserveOutput(
        observation=_observation(sealed=False),
        authority="unsealed-projection",
        control_status="control-unavailable",
    )

    assert active.observation.journal.model_dump(exclude={"entries"}) == {
        "total": 2,
        "retained": 1,
        "omitted": 1,
    }
    assert sealed.observation.sealed is True
    assert unavailable.authority == "unsealed-projection"
    with pytest.raises(ValidationError, match="seal does not match"):
        DoubleObserveOutput(
            observation=_observation(sealed=False),
            authority="sealed-snapshot",
            control_status="not-required",
        )
    with pytest.raises(ValidationError, match="retained journal count"):
        DoubleJournalOutput(total=1, retained=1, omitted=0, entries=())


def test_stop_is_idempotent_only_from_the_sealed_authority() -> None:
    repeated = DoubleStopOutput(
        run_id="ad300eca-a210-4b09-873c-95bbffdc16b8",
        status="stopped",
        sealed=True,
        idempotent=True,
        observation=_observation(sealed=True, status="stopped"),
    )
    unavailable = DoubleStopOutput(
        run_id=repeated.run_id,
        status="control-unavailable",
        sealed=False,
        idempotent=False,
        observation=_observation(sealed=False),
    )

    assert repeated.idempotent is True
    assert unavailable.observation.sealed is False
    with pytest.raises(ValidationError, match="not an idempotent stop"):
        DoubleStopOutput(
            run_id=repeated.run_id,
            status="control-unavailable",
            sealed=False,
            idempotent=True,
            observation=_observation(sealed=False),
        )


def test_double_schemas_are_registered_packaged_and_verdict_free() -> None:
    keys = (
        "double-validate",
        "double-start",
        "double-emit",
        "double-observe",
        "double-stop",
    )
    assert OUTPUT_SCHEMA_KEYS[-5:] == keys

    for key in keys:
        generated = generate_output_schema(key)
        encoded = json.dumps(generated, sort_keys=True)
        assert read_output_schema(key) == generated
        assert generated["x-svc-result-schema-version"] == 1
        assert "double-runtime-unavailable" in encoded
        assert "product_verdict" not in encoded
        assert "control_capability" not in encoded
        assert "carrier_pid" not in encoded
        assert "content_base64" not in encoded


def test_each_double_schema_rejects_an_unavailable_result_for_another_command() -> None:
    operations = ("validate", "start", "emit", "observe", "stop")

    for index, operation in enumerate(operations):
        validator = Draft202012Validator(generate_output_schema(f"double-{operation}"))
        unavailable = {
            "schema_version": 1,
            "command": f"double {operation}",
            "status": "double-runtime-unavailable",
            "continuation": "pip install 'sustainable-vibe-coding[double]'",
        }
        assert validator.is_valid(unavailable)

        unavailable["command"] = f"double {operations[(index + 1) % len(operations)]}"
        assert not validator.is_valid(unavailable)


def test_observe_and_stop_schemas_reject_contradictory_authority() -> None:
    unsealed = _observation(sealed=False).as_dict()
    sealed = _observation(sealed=True, status="stopped").as_dict()
    valid_observe = {
        "schema_version": 1,
        "command": "double observe",
        "observation": sealed,
        "authority": "sealed-snapshot",
        "control_status": "not-required",
    }
    valid_stop = {
        "schema_version": 1,
        "command": "double stop",
        "run_id": sealed["run_id"],
        "status": "stopped",
        "sealed": True,
        "idempotent": True,
        "observation": sealed,
    }
    contradictory_observe = {
        "schema_version": 1,
        "command": "double observe",
        "observation": unsealed,
        "authority": "sealed-snapshot",
        "control_status": "not-required",
    }
    contradictory_stop = {
        "schema_version": 1,
        "command": "double stop",
        "run_id": unsealed["run_id"],
        "status": "control-unavailable",
        "sealed": True,
        "idempotent": True,
        "observation": unsealed,
    }

    observe_validator = Draft202012Validator(generate_output_schema("double-observe"))
    stop_validator = Draft202012Validator(generate_output_schema("double-stop"))

    assert observe_validator.is_valid(valid_observe)
    assert stop_validator.is_valid(valid_stop)
    assert not observe_validator.is_valid(contradictory_observe)
    assert not stop_validator.is_valid(contradictory_stop)


def test_double_output_schema_imports_without_optional_runtime() -> None:
    script = r"""
import builtins

original_import = builtins.__import__
blocked = ("svc_cli.double", "ruamel", "jsonschema", "cel_expr_python")

def guarded_import(name, *args, **kwargs):
    if name in blocked or any(name.startswith(prefix + ".") for prefix in blocked):
        raise AssertionError(f"optional import attempted: {name}")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
import svc_cli.cli_output.double
import svc_cli.output_schema
"""
    completed = subprocess.run(
        (sys.executable, "-c", script),
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
