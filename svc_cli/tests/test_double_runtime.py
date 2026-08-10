from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from contextlib import contextmanager, suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Iterator

import pytest
import urllib3

import svc_cli.double.service as double_service
from svc_cli.double.compiler import compile_scenario
from svc_cli.double.materialization import (
    MaterializationContext,
    compact_json,
    match_body,
    matcher_accepts,
    run_materializer,
)
from svc_cli.double.model import (
    Body,
    Matcher,
    Materializer,
    Replay,
    RunObservation,
    StartResult,
    TargetBinding,
    ValueNode,
)
from svc_cli.double.runtime import BoundaryEngine, ResponderServer
from svc_cli.double.service import (
    DoubleRunStore,
    emit_event,
    observe_run,
    start_run,
    stop_run,
)
from svc_cli.errors import SvcError


FIXTURES = Path(__file__).parent / "fixtures" / "double"
MODULE = FIXTURES / "payment.double.yaml"
CLOCK = "2026-08-10T02:00:00Z"
TARGET_NAME = "consumer.payment-events"
FIRST_EXTERNAL_ID = "00000000-0000-4000-8000-000000000001"
SECOND_EXTERNAL_ID = "00000000-0000-4000-8000-000000000003"
FIRST_REQUEST_ID = "00000000-0000-4000-8000-000000000002"
SECOND_REQUEST_ID = "00000000-0000-4000-8000-000000000004"


def _engine(
    seed: int, *, ambiguous: bool = False, target_origin: str | None = None
) -> BoundaryEngine:
    scenario = compile_scenario(MODULE)
    if ambiguous:
        duplicate = scenario.interactions[0].model_copy(update={"name": "duplicate"})
        scenario = scenario.model_copy(
            update={"interactions": (*scenario.interactions, duplicate)}
        )
    context = MaterializationContext(
        replay=Replay(
            seed=seed,
            clock=CLOCK,
            generators=("svc.opaque-token/v1",),
            validators=("svc.rfc-uuid/v1",),
            runtime="svc.double.native/v0",
        ),
        scenario_name=scenario.name,
        scenario_digest=scenario.scenario_digest,
        run_context_digest=f"run-context-{seed}",
    )
    targets = (
        ()
        if target_origin is None
        else (TargetBinding(name=TARGET_NAME, origin=target_origin, remote=False),)
    )
    engine = BoundaryEngine(scenario, context, targets)
    engine.ready("http://127.0.0.1:1")
    return engine


def _payment_target(path: str = "/v1/payments") -> str:
    query = urllib.parse.urlencode({"observed-at": CLOCK, "trace": "trace-001"})
    return f"{path}?{query}"


def _engine_request(
    engine: BoundaryEngine,
    *,
    external_id: str = FIRST_EXTERNAL_ID,
    request_id: str = FIRST_REQUEST_ID,
    target: str | None = None,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    return engine.handle_request(
        method="POST",
        target=target or _payment_target(),
        headers={"content-type": "application/json", "x-request-id": request_id},
        raw_body=(compact_json({"externalId": external_id}) if body is None else body),
    )


def _http_payment(
    origin: str,
    *,
    external_id: str = FIRST_EXTERNAL_ID,
    request_id: str = FIRST_REQUEST_ID,
) -> tuple[int, dict[str, object]]:
    response = urllib3.PoolManager(retries=False).request(
        "POST",
        origin + _payment_target(),
        body=compact_json({"externalId": external_id}),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        redirect=False,
        retries=False,
        timeout=urllib3.Timeout(total=5),
        preload_content=True,
    )
    value = json.loads(response.data)
    assert isinstance(value, dict)
    return response.status, value


@contextmanager
def _callback_server(
    *, during_delivery: Callable[[], None] | None = None
) -> Iterator[tuple[str, list[dict[str, object]]]]:
    deliveries: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            deliveries.append(
                {
                    "path": self.path,
                    "headers": {
                        name.lower(): value for name, value in self.headers.items()
                    },
                    "body": json.loads(body),
                }
            )
            if during_delivery is not None:
                during_delivery()
            self.send_response_only(204)
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}", deliveries
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _start(
    tmp_path: Path,
    callback_origin: str,
    *,
    seed: int,
) -> tuple[StartResult, Path, Path]:
    run_root = tmp_path / "runs"
    execution_root = tmp_path / "execution"
    result = start_run(
        MODULE,
        seed=seed,
        clock=CLOCK,
        target_values=(f"{TARGET_NAME}={callback_origin}",),
        allow_remote_names=(),
        run_root=run_root,
        execution_root=execution_root,
    )
    return result, run_root, execution_root


def _test_carrier_pid(run_id: str, execution_root: Path) -> int:
    records = []
    for path in execution_root.glob("*/execution.json"):
        value = json.loads(path.read_bytes())
        if value.get("domain") == "double" and value.get("subject") == run_id:
            records.append(value)
    assert len(records) == 1
    process_id = records[0].get("process_id")
    assert type(process_id) is int
    return process_id


def _terminate_test_carrier(run_id: str, run_root: Path, execution_root: Path) -> None:
    record = DoubleRunStore(run_root).read_record(run_id)
    with suppress(ProcessLookupError):
        os.kill(_test_carrier_pid(run_id, execution_root), signal.SIGTERM)
    _wait_until_closed(record.control_url)


def _cleanup_run(run_id: str, run_root: Path, execution_root: Path) -> None:
    try:
        stopped = stop_run(run_id, run_root=run_root)
    except Exception:
        _terminate_test_carrier(run_id, run_root, execution_root)
        return
    if stopped.status != "stopped":
        _terminate_test_carrier(run_id, run_root, execution_root)


def _wait_until_closed(origin: str) -> None:
    parsed = urllib.parse.urlsplit(origin)
    assert parsed.hostname is not None and parsed.port is not None
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            connection = socket.create_connection(
                (parsed.hostname, parsed.port), timeout=0.05
            )
        except OSError:
            return
        connection.close()
        time.sleep(0.02)
    raise AssertionError(f"carrier control remained reachable: {origin}")


def _file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_in_process_matching_capture_and_seed_replay() -> None:
    engine = _engine(123)

    first = _engine_request(engine)
    equal_retry = _engine_request(engine)
    conflict = _engine_request(engine, external_id=SECOND_EXTERNAL_ID)

    assert first[0] == equal_retry[0] == 201
    assert first[1:] == equal_retry[1:]
    assert conflict[0] == 409
    assert json.loads(conflict[2])["error"]["code"] == "double-capture-conflict"
    assert engine.context.bindings["external_id"] == FIRST_EXTERNAL_ID
    statuses = [
        entry.status
        for entry in engine.observation(run_id="run", sealed=False).journal.entries
    ]
    assert statuses == [
        "matched",
        "matched",
        "capture-conflict",
    ]

    replayed = _engine_request(_engine(123))
    challenged = _engine_request(_engine(456))
    assert replayed[1:] == first[1:]
    assert challenged[0] == 201
    assert challenged[2] != first[2]


def test_json_null_capture_and_boolean_number_equality_are_type_safe() -> None:
    engine = _engine(123)
    interaction = engine.scenario.interactions[0]
    nullable = Body(
        kind="structured",
        template=None,
        nodes=(
            ValueNode(
                path=(),
                kind="capture",
                name="nullable",
                matcher=Matcher(kind="enum", values=(None, 1)),
            ),
        ),
    )
    request = interaction.request.model_copy(update={"body": nullable})
    engine.scenario = engine.scenario.model_copy(
        update={
            "contract": None,
            "interactions": (interaction.model_copy(update={"request": request}),),
        }
    )

    accepted = _engine_request(engine, body=b"null")
    conflict = _engine_request(engine, body=b"1")

    assert accepted[0] == 201
    assert engine.context.bindings["nullable"] is None
    assert conflict[0] == 409
    assert json.loads(conflict[2])["error"]["code"] == "double-capture-conflict"
    exact_true = Matcher(kind="exact", value=True)
    assert matcher_accepts(exact_true, True)
    assert not matcher_accepts(exact_true, 1)
    literal_true = Body(
        kind="structured",
        template=True,
        nodes=(ValueNode(path=(), kind="literal", value=True),),
    )
    matched, _reasons, _captures, _actual = match_body(
        literal_true,
        b"1",
        engine.context,
        namespace="literal-type-safety",
    )
    assert matched is False
    rfc3339 = Matcher(kind="semantic", semantic="rfc3339", using="svc.rfc3339/v1")
    assert matcher_accepts(rfc3339, "2026-08-10T10:00:00+08:00")
    assert not matcher_accepts(rfc3339, "2026-08-10 10:00:00+08:00")


def test_response_derived_value_receives_the_normalized_matched_request() -> None:
    engine = _engine(123)
    interaction = engine.scenario.interactions[0]
    assert interaction.response.body is not None
    body_node = interaction.response.body.nodes[0].model_copy(
        update={
            "expression": "request.body.value.externalId",
            "validator": Matcher(
                kind="semantic",
                semantic="rfc.uuid",
                using="svc.rfc-uuid/v1",
            ),
        }
    )
    response_body = interaction.response.body.model_copy(update={"nodes": (body_node,)})
    response = interaction.response.model_copy(update={"body": response_body})
    engine.scenario = engine.scenario.model_copy(
        update={
            "contract": None,
            "interactions": (interaction.model_copy(update={"response": response}),),
        }
    )

    status, _headers, raw = _engine_request(engine)

    assert status == 201
    assert json.loads(raw) == {"paymentId": FIRST_EXTERNAL_ID}


def test_external_materializer_stdout_is_enforced_while_reading(tmp_path: Path) -> None:
    context = _engine(123).context
    materializer = Materializer(
        argv=(sys.executable, "-c", "import sys; sys.stdout.write('x' * 4096)"),
        cwd=str(tmp_path),
        env={},
        timeout_ms=2_000,
        max_output_bytes=32,
    )

    with pytest.raises(SvcError) as caught:
        run_materializer(
            materializer,
            phase="response",
            context=context,
            request=None,
            expected_status=200,
        )

    assert caught.value.code == "double-materializer-output-too-large"


def test_recursive_local_openapi_registry_is_runtime_authority() -> None:
    scenario = compile_scenario(FIXTURES / "recursive.double.yaml")
    valid = {"value": "root", "next": {"value": "child", "next": None}}
    invalid = {"value": "root", "next": {"value": 1, "next": None}}
    interaction = scenario.interactions[0]
    request = interaction.request.model_copy(
        update={
            "body": Body(
                kind="structured",
                template=None,
                nodes=(
                    ValueNode(
                        path=(),
                        kind="capture",
                        name="payload",
                        matcher=Matcher(kind="enum", values=(valid, invalid)),
                    ),
                ),
            )
        }
    )
    scenario = scenario.model_copy(
        update={"interactions": (interaction.model_copy(update={"request": request}),)}
    )

    def execute(body: dict[str, object]) -> tuple[int, bytes]:
        context = MaterializationContext(
            replay=Replay(
                seed=1,
                clock=CLOCK,
                generators=(),
                validators=(),
                runtime="svc.double.native/v0",
            ),
            scenario_name=scenario.name,
            scenario_digest=scenario.scenario_digest,
            run_context_digest="recursive",
        )
        engine = BoundaryEngine(scenario, context, ())
        engine.ready("http://127.0.0.1:1")
        status, _headers, raw = engine.handle_request(
            method="POST",
            target="/v1/nodes",
            headers={},
            raw_body=compact_json(body),
        )
        return status, raw

    assert execute(valid)[0] == 204
    rejected_status, rejected_body = execute(invalid)
    assert rejected_status == 422
    assert (
        json.loads(rejected_body)["error"]["code"] == "double-request-contract-failed"
    )


@pytest.mark.parametrize(
    ("headers", "code"),
    [
        ({"x-derived": "ok\r\nx-injected: yes"}, "double-header-value-invalid"),
        ({"content-length": "999"}, "double-header-name-invalid"),
    ],
)
def test_materialized_headers_cannot_escape_runtime_framing(
    headers: dict[str, object], code: str
) -> None:
    engine = _engine(123)
    interaction = engine.scenario.interactions[0]
    response = interaction.response.model_copy(
        update={"headers": headers, "header_nodes": ()}
    )
    engine.scenario = engine.scenario.model_copy(
        update={
            "contract": None,
            "interactions": (interaction.model_copy(update={"response": response}),),
        }
    )

    status, _headers, raw = _engine_request(engine)

    assert status == 500
    assert json.loads(raw)["error"]["code"] == code


def test_in_process_fail_closed_matching_and_request_bounds() -> None:
    no_match_engine = _engine(123)
    no_match = _engine_request(no_match_engine, target=_payment_target("/unknown"))
    ambiguous_engine = _engine(123, ambiguous=True)
    ambiguous = _engine_request(ambiguous_engine)
    malformed_engine = _engine(123)
    malformed = _engine_request(malformed_engine, body=b"{")

    assert no_match[0] == 404
    assert json.loads(no_match[2])["error"]["code"] == "double-no-match"
    assert ambiguous[0] == 409
    assert json.loads(ambiguous[2])["error"]["code"] == "double-ambiguous-match"
    assert malformed[0] == 400
    assert json.loads(malformed[2])["error"]["code"] == "double-request-json-invalid"
    no_match_journal = no_match_engine.observation(run_id="run", sealed=False).journal
    ambiguous_journal = ambiguous_engine.observation(run_id="run", sealed=False).journal
    assert no_match_journal.entries[-1].status == "no-match"
    assert ambiguous_journal.entries[-1].status == "ambiguous-match"

    server = ResponderServer(_engine(123))
    server.start()
    connection = http.client.HTTPConnection(
        urllib.parse.urlsplit(server.url).hostname,
        urllib.parse.urlsplit(server.url).port,
        timeout=5,
    )
    try:
        connection.putrequest("POST", "/v1/payments")
        connection.putheader("Content-Length", str(1_048_577))
        connection.endheaders()
        response = connection.getresponse()
        assert response.status == 413
        assert (
            json.loads(response.read())["error"]["code"] == "double-request-too-large"
        )
    finally:
        connection.close()
        server.stop()


def test_unrelated_structured_route_does_not_parse_an_empty_request_body() -> None:
    engine = _engine(123)
    structured = engine.scenario.interactions[0]
    empty_request = structured.request.model_copy(
        update={
            "method": "GET",
            "path": "/v3/certificates",
            "query": {},
            "query_nodes": (),
            "headers": {},
            "header_nodes": (),
            "body": None,
        }
    )
    certificate = structured.model_copy(
        update={"name": "certificates", "request": empty_request}
    )
    engine.scenario = engine.scenario.model_copy(
        update={"interactions": (certificate, structured)}
    )

    status, _headers, _body = engine.handle_request(
        method="GET",
        target="/v3/certificates",
        headers={},
        raw_body=b"",
    )

    assert status == 201
    assert engine.observation(run_id="run", sealed=False).journal.entries[-1].status == "matched"


def test_service_detached_boundary_event_and_sealed_authority(tmp_path: Path) -> None:
    with _callback_server() as (callback_origin, deliveries):
        started, run_root, _execution_root = _start(tmp_path, callback_origin, seed=123)
        run_id = started.run_id
        stopped = False
        try:
            status, response = _http_payment(started.responder_url)
            assert status == 201
            payment_id = response["paymentId"]

            emitted = emit_event(run_id, "payment.succeeded", run_root=run_root)
            assert emitted.status == "acknowledged"
            assert emitted.http_status == 204
            assert len(deliveries) == 1
            assert deliveries[0]["path"] == "/webhooks/payment"
            assert deliveries[0]["body"] == {
                "externalId": FIRST_EXTERNAL_ID,
                "paymentId": payment_id,
            }

            active = observe_run(run_id, run_root=run_root)
            assert active.authority == "active-carrier"
            assert active.control_status == "available"
            assert active.observation.sealed is False
            assert active.observation.bindings == {
                "external_id": FIRST_EXTERNAL_ID,
                "payment_id": payment_id,
                "request_id": FIRST_REQUEST_ID,
            }
            assert [entry.status for entry in active.observation.journal.entries] == [
                "matched",
                "acknowledged",
            ]

            first_stop = stop_run(run_id, run_root=run_root)
            stopped = True
            assert first_stop.status == "stopped"
            assert first_stop.sealed is True
            assert first_stop.idempotent is False
            sealed = observe_run(run_id, run_root=run_root)
            assert sealed.authority == "sealed-snapshot"
            assert sealed.control_status == "not-required"
            assert sealed.observation == first_stop.observation

            repeated = stop_run(run_id, run_root=run_root)
            assert repeated.status == "stopped"
            assert repeated.sealed is True
            assert repeated.idempotent is True
            assert repeated.observation == first_stop.observation
        finally:
            if not stopped:
                _cleanup_run(run_id, run_root, _execution_root)


def test_event_consumer_can_reenter_the_responder_before_acknowledging() -> None:
    responder: dict[str, str] = {}

    def reenter_responder() -> None:
        status, _response = _http_payment(responder["origin"])
        assert status == 201

    with _callback_server(during_delivery=reenter_responder) as (
        callback_origin,
        deliveries,
    ):
        engine = _engine(123, target_origin=callback_origin)
        server = ResponderServer(engine)
        server.start()
        responder["origin"] = server.url
        try:
            status, _response = _http_payment(server.url)
            assert status == 201

            emitted = engine.emit("payment.succeeded")

            assert emitted.status == "acknowledged"
            assert emitted.http_status == 204
            assert len(deliveries) == 1
            assert [
                entry.status
                for entry in engine.observation(run_id="run", sealed=False).journal.entries
            ] == ["matched", "matched", "acknowledged"]
        finally:
            server.stop()


def test_observe_classifies_a_concurrent_sealed_control_result_as_final_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _callback_server() as (callback_origin, _deliveries):
        started, run_root, execution_root = _start(tmp_path, callback_origin, seed=123)
        try:
            store = DoubleRunStore(run_root)
            record = store.read_record(started.run_id)
            unsealed = store.read_observation(record)
            sealed = unsealed.model_copy(update={"status": "stopped", "sealed": True})

            def sealed_control_result(
                *args: object, **kwargs: object
            ) -> dict[str, object]:
                return {"observation": sealed.model_dump(mode="json")}

            with monkeypatch.context() as patch:
                patch.setattr(double_service, "_control_request", sealed_control_result)
                observed = observe_run(started.run_id, run_root=run_root)

            assert observed.authority == "sealed-snapshot"
            assert observed.control_status == "not-required"
            assert observed.observation.sealed is True
        finally:
            _cleanup_run(started.run_id, run_root, execution_root)


def test_control_failure_rereads_a_concurrently_sealed_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _callback_server() as (callback_origin, _deliveries):
        started, run_root, execution_root = _start(tmp_path, callback_origin, seed=123)
        restore_projection: tuple[Path, RunObservation] | None = None
        try:
            store = DoubleRunStore(run_root)
            record = store.read_record(started.run_id)
            unsealed = store.read_observation(record)
            sealed = unsealed.model_copy(update={"status": "stopped", "sealed": True})
            observation_path = Path(record.observation_path)
            restore_projection = (observation_path, unsealed)

            def seal_then_disappear(*args: object, **kwargs: object) -> None:
                observation_path.write_text(
                    json.dumps(sealed.model_dump(mode="json")), encoding="utf-8"
                )
                return None

            with monkeypatch.context() as patch:
                patch.setattr(double_service, "_control_request", seal_then_disappear)
                observed = observe_run(started.run_id, run_root=run_root)
            observation_path.write_text(
                json.dumps(unsealed.model_dump(mode="json")), encoding="utf-8"
            )
            with monkeypatch.context() as patch:
                patch.setattr(double_service, "_control_request", seal_then_disappear)
                stopped = stop_run(started.run_id, run_root=run_root)

            assert observed.authority == "sealed-snapshot"
            assert observed.control_status == "not-required"
            assert stopped.status == "stopped"
            assert stopped.sealed is True
            assert stopped.idempotent is True
        finally:
            if restore_projection is not None:
                path, observation = restore_projection
                path.write_text(
                    json.dumps(observation.model_dump(mode="json")), encoding="utf-8"
                )
            _cleanup_run(started.run_id, run_root, execution_root)


def test_black_box_consumer_owns_the_public_product_assertion(tmp_path: Path) -> None:
    ready_path = tmp_path / "consumer.ready"
    provider_path = tmp_path / "provider.origin"
    consumer = subprocess.Popen(
        (
            sys.executable,
            str(FIXTURES / "consumer_app.py"),
            str(ready_path),
            str(provider_path),
        ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    started = None
    stopped = False
    try:
        deadline = time.monotonic() + 5
        while not ready_path.is_file():
            if consumer.poll() is not None:
                stderr = b"" if consumer.stderr is None else consumer.stderr.read()
                raise AssertionError(f"Consumer exited before readiness: {stderr!r}")
            if time.monotonic() >= deadline:
                raise AssertionError("Consumer did not publish readiness")
            time.sleep(0.02)
        consumer_origin = ready_path.read_text(encoding="utf-8")
        started, run_root, execution_root = _start(
            tmp_path,
            consumer_origin,
            seed=123,
        )
        provider_path.write_text(started.responder_url, encoding="utf-8")

        manager = urllib3.PoolManager(retries=False)
        accepted = manager.request(
            "POST",
            consumer_origin + "/orders/pay",
            body=compact_json(
                {"externalId": FIRST_EXTERNAL_ID, "requestId": FIRST_REQUEST_ID}
            ),
            headers={"Content-Type": "application/json"},
            redirect=False,
            retries=False,
            timeout=urllib3.Timeout(total=5),
        )
        assert accepted.status == 202
        assert (
            emit_event(
                started.run_id,
                "payment.succeeded",
                run_root=run_root,
            ).status
            == "acknowledged"
        )

        public_order = manager.request(
            "GET",
            consumer_origin + f"/orders/{FIRST_EXTERNAL_ID}",
            redirect=False,
            retries=False,
            timeout=urllib3.Timeout(total=5),
        )

        assert json.loads(public_order.data) == {"status": "paid"}
        assert stop_run(started.run_id, run_root=run_root).status == "stopped"
        stopped = True
    finally:
        if started is not None and not stopped:
            _cleanup_run(started.run_id, run_root, execution_root)
        if consumer.poll() is None:
            consumer.terminate()
        consumer.wait(timeout=5)


def test_two_active_runs_keep_replay_bindings_and_stop_isolated(tmp_path: Path) -> None:
    with _callback_server() as (callback_origin, _deliveries):
        first, run_root, _execution_root = _start(tmp_path, callback_origin, seed=123)
        second = None
        stopped: set[str] = set()
        try:
            second, _same_run_root, _same_execution_root = _start(
                tmp_path, callback_origin, seed=456
            )
            assert first.run_id != second.run_id
            assert first.responder_url != second.responder_url
            assert first.scenario_digest == second.scenario_digest
            assert first.run_context_digest != second.run_context_digest
            assert first.replay.seed == 123
            assert second.replay.seed == 456

            first_status, first_response = _http_payment(first.responder_url)
            second_status, second_response = _http_payment(
                second.responder_url,
                external_id=SECOND_EXTERNAL_ID,
                request_id=SECOND_REQUEST_ID,
            )
            assert first_status == second_status == 201
            assert first_response != second_response

            first_observation = observe_run(first.run_id, run_root=run_root).observation
            second_observation = observe_run(
                second.run_id, run_root=run_root
            ).observation
            assert first_observation.bindings["external_id"] == FIRST_EXTERNAL_ID
            assert second_observation.bindings["external_id"] == SECOND_EXTERNAL_ID
            assert (
                first_observation.bindings["payment_id"]
                != second_observation.bindings["payment_id"]
            )

            assert stop_run(first.run_id, run_root=run_root).status == "stopped"
            stopped.add(first.run_id)
            retry_status, retry_response = _http_payment(
                second.responder_url,
                external_id=SECOND_EXTERNAL_ID,
                request_id=SECOND_REQUEST_ID,
            )
            assert retry_status == 201
            assert retry_response == second_response
            still_active = observe_run(second.run_id, run_root=run_root)
            assert still_active.authority == "active-carrier"
            assert still_active.observation.journal.total == 2
        finally:
            for result in (first, second):
                if result is not None and result.run_id not in stopped:
                    _cleanup_run(result.run_id, run_root, _execution_root)


def test_control_unavailable_preserves_files_without_pid_authority(
    tmp_path: Path,
) -> None:
    with _callback_server() as (callback_origin, _deliveries):
        started, run_root, execution_root = _start(tmp_path, callback_origin, seed=123)
        store = DoubleRunStore(run_root)
        record = store.read_record(started.run_id)
        carrier_terminated = False
        try:
            os.kill(_test_carrier_pid(started.run_id, execution_root), signal.SIGTERM)
            _wait_until_closed(record.control_url)
            carrier_terminated = True
            before = _file_bytes(Path(record.run_directory))

            observed = observe_run(started.run_id, run_root=run_root)
            stopped = stop_run(started.run_id, run_root=run_root)

            assert observed.authority == "unsealed-projection"
            assert observed.control_status == "control-unavailable"
            assert observed.observation.sealed is False
            assert stopped.status == "control-unavailable"
            assert stopped.sealed is False
            assert stopped.idempotent is False
            assert stopped.observation == observed.observation
            assert _file_bytes(Path(record.run_directory)) == before
            assert b"carrier_pid" not in before["record.json"]
        finally:
            if not carrier_terminated:
                _cleanup_run(started.run_id, run_root, execution_root)
