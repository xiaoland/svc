from __future__ import annotations

import math
import os
import shutil
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from svc_cli.double.compiler import (
    MAX_MODULE_BYTES,
    MAX_YAML_DEPTH,
    MAX_YAML_NODES,
    compile_scenario,
)
from svc_cli.double.materialization import (
    MaterializationContext,
    commit_bindings,
    match_body,
    match_mapping,
    materialize_body,
    materialize_mapping,
)
from svc_cli.double.model import Replay, strict_json_value
from svc_cli.errors import SvcError


FIXTURES = Path(__file__).parent / "fixtures" / "double"


def _write_module(root: Path, scenario: str) -> Path:
    module = root / "scenario.double.yaml"
    module.write_text(
        "language: svc.double/v0\nscenario:\n" + scenario,
        encoding="utf-8",
    )
    return module


def _one_interaction(
    *, request: str = "", response: str = "        status: 200\n"
) -> str:
    return (
        "  name: example\n"
        "  claim: one boundary claim\n"
        "  boundary: {name: provider, protocol: http}\n"
        "  interactions:\n"
        "    - name: call\n"
        "      provenance: {kind: synthetic, source: https://example.invalid/call}\n"
        "      request:\n"
        "        method: POST\n"
        "        path: /call\n"
        f"{request}"
        "      response:\n"
        f"{response}"
    )


def test_compile_representative_module_to_normalized_ir() -> None:
    module = FIXTURES / "payment.double.yaml"

    scenario = compile_scenario(module)

    assert scenario.name == "payment-confirmed"
    assert scenario.language == "svc.double/v0"
    assert scenario.event_target_policy == "loopback-only"
    assert len(scenario.scenario_digest) == 64
    assert scenario.scenario_digest == compile_scenario(module).scenario_digest
    assert scenario.fidelity == (
        "http-exact-boundary",
        "provenance-declared",
        "json.compact-utf8/v1",
        "selected-operation-schema",
        "local-snapshots",
    )
    assert "consumer-egress: not-enforced" in scenario.nonclaims

    interaction = scenario.interactions[0]
    assert interaction.request.query["observed-at"] == "2026-08-10T02:00:00Z"
    assert isinstance(interaction.request.query["observed-at"], str)
    assert interaction.request.query_nodes[0].path == ("trace",)
    assert interaction.request.header_nodes[0].path == ("x-request-id",)
    assert interaction.response.header_nodes[0].path == ("x-payment-id",)
    assert scenario.events[0].request.header_nodes[0].path == ("x-request-id",)
    assert interaction.request.header_nodes[0].location is not None
    assert interaction.request.header_nodes[0].location.line == 37

    assert scenario.contract is not None
    assert scenario.contract.method == "POST"
    assert scenario.contract.path == "/v1/payments"
    assert "urn:svc:double:schema-resource:" in str(scenario.contract.request_schema)
    assert "urn:svc:double:schema-resource:" in str(scenario.contract.response_schemas)
    assert len(scenario.contract.schema_resources) == 2
    assert [item.logical_path for item in scenario.snapshots] == [
        "svc_cli/tests/fixtures/double/contracts/payment.openapi.yaml",
        "svc_cli/tests/fixtures/double/contracts/schemas.yaml",
    ]
    assert interaction.provenance.snapshot_sha256 == scenario.contract.source.sha256


def test_compiled_ir_drives_matching_captures_and_output_materialization() -> None:
    scenario = compile_scenario(FIXTURES / "payment.double.yaml")
    interaction = scenario.interactions[0]
    context = MaterializationContext(
        replay=Replay(
            seed=7,
            clock="2026-08-10T02:00:00Z",
            generators=("svc.opaque-token/v1",),
            validators=("svc.rfc-uuid/v1",),
            runtime="test",
        ),
        scenario_name=scenario.name,
        scenario_digest=scenario.scenario_digest,
        run_context_digest="test-run",
    )

    query_match, _, query_captures = match_mapping(
        interaction.request.query,
        interaction.request.query_nodes,
        {"observed-at": "2026-08-10T02:00:00Z", "trace": "trace-001"},
        context,
        namespace="request-query",
    )
    header_match, _, header_captures = match_mapping(
        interaction.request.headers,
        interaction.request.header_nodes,
        {
            "content-type": "application/json",
            "x-request-id": "00000000-0000-4000-8000-000000000002",
        },
        context,
        namespace="request-headers",
    )
    body_match, _, body_captures, structured_request = match_body(
        interaction.request.body,
        b'{"externalId":"00000000-0000-4000-8000-000000000001"}',
        context,
        namespace="request-body",
    )
    assert query_match and header_match and body_match
    commit_bindings(context, {**query_captures, **header_captures, **body_captures})

    response_headers = materialize_mapping(
        interaction.response.headers,
        interaction.response.header_nodes,
        context,
        namespace="response-headers",
        request=structured_request,
    )
    raw, kind, structured = materialize_body(
        interaction.response.body,
        context,
        namespace="response-body",
        request=structured_request,
    )

    assert kind == "structured"
    assert structured == {"paymentId": response_headers["x-payment-id"]}
    assert raw == (
        b'{"paymentId":"' + str(response_headers["x-payment-id"]).encode() + b'"}'
    )


def test_scenario_digest_ignores_physical_location_and_yaml_comments(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    shutil.copytree(FIXTURES, first)
    shutil.copytree(FIXTURES, second)
    module = second / "payment.double.yaml"
    module.write_text(
        "# shifted source locations\n" + module.read_text(encoding="utf-8")
    )

    left = compile_scenario(first / "payment.double.yaml")
    right = compile_scenario(module)

    assert left.scenario_digest == right.scenario_digest
    assert left.module_path != right.module_path
    assert (
        left.interactions[0].request.header_nodes[0].location
        != right.interactions[0].request.header_nodes[0].location
    )


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("alias.double.yaml", "unsupported-double-yaml-feature"),
        ("cel-macro.double.yaml", "invalid-double-cel"),
        ("duplicate-key.double.yaml", "invalid-double-yaml"),
        ("illegal-phase.double.yaml", "illegal-double-value-phase"),
        ("multi-doc.double.yaml", "multiple-double-yaml-documents"),
        ("unavailable-binding.double.yaml", "unavailable-double-binding"),
        ("unknown-key.double.yaml", "unknown-double-key"),
    ],
)
def test_invalid_fixture_corpus_has_stable_diagnostics(name: str, code: str) -> None:
    with pytest.raises(SvcError) as caught:
        compile_scenario(FIXTURES / "invalid" / name)

    assert caught.value.code == code
    assert Path(caught.value.details["module"]).name == name
    assert caught.value.details["line"] >= 1
    assert caught.value.details["column"] >= 1


@pytest.mark.parametrize(
    ("claim", "code", "feature"),
    [
        ("!private tagged", "unsupported-double-yaml-feature", "tag"),
        ("{<<: {hidden: true}}", "unsupported-double-yaml-feature", "merge-key"),
    ],
)
def test_explicit_yaml_tags_and_merge_keys_are_rejected(
    tmp_path: Path, claim: str, code: str, feature: str
) -> None:
    module = _write_module(
        tmp_path,
        _one_interaction().replace("one boundary claim", claim),
    )

    with pytest.raises(SvcError) as caught:
        compile_scenario(module)

    assert caught.value.code == code
    assert caught.value.details["feature"] == feature


def test_parser_byte_depth_and_node_bounds_are_enforced(tmp_path: Path) -> None:
    too_large = tmp_path / "large.double.yaml"
    too_large.write_bytes(b"#" * (MAX_MODULE_BYTES + 1))
    with pytest.raises(SvcError, match="byte bound") as caught:
        compile_scenario(too_large)
    assert caught.value.code == "module-too-large"
    assert caught.value.details["max_bytes"] == MAX_MODULE_BYTES

    too_deep = tmp_path / "deep.double.yaml"
    too_deep.write_text("x: " + "[" * (MAX_YAML_DEPTH + 1) + "]" * (MAX_YAML_DEPTH + 1))
    with pytest.raises(SvcError) as caught:
        compile_scenario(too_deep)
    assert caught.value.code == "double-yaml-too-deep"
    assert caught.value.details["max_depth"] == MAX_YAML_DEPTH

    too_many = tmp_path / "nodes.double.yaml"
    too_many.write_text("x:\n" + "  - x\n" * MAX_YAML_NODES)
    with pytest.raises(SvcError) as caught:
        compile_scenario(too_many)
    assert caught.value.code == "double-yaml-too-many-nodes"
    assert caught.value.details["max_nodes"] == MAX_YAML_NODES


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_runtime_json_boundary_rejects_non_finite_numbers(value: float) -> None:
    assert not math.isfinite(value)
    with pytest.raises(TypeError, match="finite"):
        strict_json_value(value)


def test_query_and_header_typed_values_must_be_string_typed(tmp_path: Path) -> None:
    numeric_query = _write_module(
        tmp_path,
        _one_interaction(request="        query: {page: 1}\n"),
    )
    with pytest.raises(SvcError) as caught:
        compile_scenario(numeric_query)
    assert caught.value.code == "invalid-double-query"

    range_header = _write_module(
        tmp_path,
        _one_interaction(
            request=(
                "        headers:\n"
                "          x-page:\n"
                "            $bsl:\n"
                "              kind: match\n"
                "              match: {kind: range, minimum: 1, maximum: 9}\n"
            )
        ),
    )
    with pytest.raises(SvcError) as caught:
        compile_scenario(range_header)
    assert caught.value.code == "invalid-double-header"


def test_form_urlencoded_request_fields_match_capture_and_preserve_repeats(
    tmp_path: Path,
) -> None:
    module = _write_module(
        tmp_path,
        _one_interaction(
            request=(
                "        headers: {content-type: application/x-www-form-urlencoded}\n"
                "        body:\n"
                "          form-urlencoded:\n"
                "            ext_order_id:\n"
                "              $bsl:\n"
                "                kind: capture\n"
                "                name: external_order_id\n"
                "                match: {kind: regex, pattern: '^[0-9a-f-]{36}$'}\n"
                "            tag: [first, second]\n"
                "            note: Hangzhou East\n"
            )
        ),
    )
    scenario = compile_scenario(module)
    body = scenario.interactions[0].request.body
    assert body is not None
    assert body.kind == "form-urlencoded"
    assert "form-urlencoded.field-matching/v1" in scenario.fidelity
    context = MaterializationContext(
        replay=Replay(
            seed=1,
            clock="2026-08-10T02:00:00Z",
            generators=(),
            validators=(),
            runtime="test",
        ),
        scenario_name=scenario.name,
        scenario_digest=scenario.scenario_digest,
        run_context_digest="form-run",
    )

    matched, reasons, captures, parsed = match_body(
        body,
        (
            b"note=Hangzhou+East&tag=first&"
            b"ext_order_id=00000000-0000-4000-8000-000000000001&tag=second"
        ),
        context,
        namespace="form-request",
    )

    assert matched, reasons
    assert captures == {
        "external_order_id": "00000000-0000-4000-8000-000000000001"
    }
    assert parsed == {
        "ext_order_id": "00000000-0000-4000-8000-000000000001",
        "note": "Hangzhou East",
        "tag": ["first", "second"],
    }
    with pytest.raises(SvcError) as caught:
        match_body(
            body,
            b"ext_order_id=%GG&tag=first&tag=second&note=Hangzhou+East",
            context,
            namespace="invalid-form-request",
        )
    assert caught.value.code == "double-request-form-invalid"


def test_form_urlencoded_is_request_only_and_string_typed(tmp_path: Path) -> None:
    numeric = _write_module(
        tmp_path,
        _one_interaction(
            request=(
                "        body:\n"
                "          form-urlencoded:\n"
                "            page: 1\n"
            )
        ),
    )
    with pytest.raises(SvcError) as caught:
        compile_scenario(numeric)
    assert caught.value.code == "invalid-double-form"

    response_form = _write_module(
        tmp_path,
        _one_interaction(
            response=(
                "        status: 200\n"
                "        body:\n"
                "          form-urlencoded: {ok: yes}\n"
            )
        ),
    )
    with pytest.raises(SvcError) as caught:
        compile_scenario(response_form)
    assert caught.value.code == "invalid-double-body"


def test_output_binding_is_available_to_later_derived_value(tmp_path: Path) -> None:
    module = _write_module(
        tmp_path,
        _one_interaction(
            response=(
                "        status: 200\n"
                "        body:\n"
                "          structured:\n"
                "            first:\n"
                "              $bsl: {kind: example, value: stable, bind: stable_value}\n"
                "            second:\n"
                "              $bsl:\n"
                "                kind: derived\n"
                "                expression: bindings.stable_value\n"
                "                validate: {kind: exact, value: stable}\n"
            )
        ),
    )

    scenario = compile_scenario(module)

    body = scenario.interactions[0].response.body
    assert body is not None
    nodes = body.nodes
    assert nodes[0].bind == "stable_value"
    assert nodes[1].expression == "bindings.stable_value"


def test_cel_binding_text_inside_a_string_is_not_a_reference(tmp_path: Path) -> None:
    module = _write_module(
        tmp_path,
        _one_interaction(
            response=(
                "        status: 200\n"
                "        body:\n"
                "          structured:\n"
                "            text:\n"
                "              $bsl:\n"
                "                kind: derived\n"
                "                expression: \"'bindings.not_a_reference'\"\n"
                "                validate: {kind: exact, value: bindings.not_a_reference}\n"
            )
        ),
    )

    scenario = compile_scenario(module)

    body = scenario.interactions[0].response.body
    assert body is not None
    assert body.nodes[0].expression == "'bindings.not_a_reference'"


@pytest.mark.parametrize(
    ("expression", "validator"),
    [
        ("[1, 2]", "{kind: exact, value: [1, 2]}"),
        ("{'key': 1}", "{kind: exact, value: {key: 1}}"),
    ],
)
def test_cel_json_collection_return_types_are_admitted(
    tmp_path: Path, expression: str, validator: str
) -> None:
    module = _write_module(
        tmp_path,
        _one_interaction(
            response=(
                "        status: 200\n"
                "        body:\n"
                "          structured:\n"
                "            value:\n"
                "              $bsl:\n"
                "                kind: derived\n"
                f'                expression: "{expression}"\n'
                f"                validate: {validator}\n"
            )
        ),
    )

    scenario = compile_scenario(module)

    body = scenario.interactions[0].response.body
    assert body is not None and body.nodes[0].kind == "derived"


def test_cel_non_json_return_type_is_rejected(tmp_path: Path) -> None:
    module = _write_module(
        tmp_path,
        _one_interaction(
            response=(
                "        status: 200\n"
                "        body:\n"
                "          structured:\n"
                "            value:\n"
                "              $bsl:\n"
                "                kind: derived\n"
                "                expression: 'b\"not-json\"'\n"
                "                validate: {kind: exact, value: not-json}\n"
            )
        ),
    )

    with pytest.raises(SvcError) as caught:
        compile_scenario(module)

    assert caught.value.code == "invalid-double-cel"


def test_cel_static_scan_ignores_comments_and_event_string_literals(
    tmp_path: Path,
) -> None:
    scenario = _one_interaction(
        response=(
            "        status: 200\n"
            "        body:\n"
            "          structured:\n"
            "            value:\n"
            "              $bsl:\n"
            "                kind: derived\n"
            "                expression: |\n"
            "                  // bindings.not_a_reference\n"
            "                  'ok'\n"
            "                validate: {kind: exact, value: ok}\n"
        )
    )
    scenario += (
        "  events:\n"
        "    - name: explicit\n"
        "      target: consumer.events\n"
        "      provenance: {kind: synthetic, source: https://example.invalid/event}\n"
        "      request:\n"
        "        method: POST\n"
        "        path: /event\n"
        "        body:\n"
        "          structured:\n"
        "            text:\n"
        "              $bsl:\n"
        "                kind: derived\n"
        "                expression: \"'request'\"\n"
        "                validate: {kind: exact, value: request}\n"
    )

    compiled = compile_scenario(_write_module(tmp_path, scenario))

    assert compiled.events[0].name == "explicit"


def test_cross_interaction_binding_is_not_statically_available(tmp_path: Path) -> None:
    scenario = _one_interaction(
        request=(
            "        body:\n"
            "          structured:\n"
            "            id:\n"
            "              $bsl:\n"
            "                kind: capture\n"
            "                name: first_id\n"
            "                match: {kind: regex, pattern: '^x$'}\n"
        )
    )
    scenario += (
        "    - name: independent\n"
        "      provenance: {kind: synthetic, source: https://example.invalid/independent}\n"
        "      request: {method: POST, path: /independent}\n"
        "      response:\n"
        "        status: 200\n"
        "        body:\n"
        "          structured:\n"
        "            leaked:\n"
        "              $bsl:\n"
        "                kind: derived\n"
        "                expression: bindings.first_id\n"
        "                validate: {kind: regex, pattern: '^x$'}\n"
    )
    module = _write_module(tmp_path, scenario)

    with pytest.raises(SvcError) as caught:
        compile_scenario(module)

    assert caught.value.code == "unavailable-double-binding"


def test_literal_node_escapes_reserved_bsl_object(tmp_path: Path) -> None:
    module = _write_module(
        tmp_path,
        _one_interaction(
            request=(
                "        body:\n"
                "          structured:\n"
                "            providerValue:\n"
                "              $bsl:\n"
                "                kind: literal\n"
                "                value: {$bsl: provider-owned}\n"
            )
        ),
    )

    scenario = compile_scenario(module)

    body = scenario.interactions[0].request.body
    assert body is not None
    node = body.nodes[0]
    assert node.kind == "literal"
    assert node.value == {"$bsl": "provider-owned"}


def test_managed_assets_are_snapshotted_and_workspace_escape_is_rejected(
    tmp_path: Path,
) -> None:
    managed = tmp_path / "managed.json"
    managed.write_text('{"provider":"value"}', encoding="utf-8")
    module = _write_module(
        tmp_path,
        _one_interaction(
            response=(
                "        status: 200\n"
                "        body:\n"
                "          structured:\n"
                "            $bsl:\n"
                "              kind: managed\n"
                "              source: managed.json\n"
                "              media-type: application/json\n"
            )
        ),
    )

    scenario = compile_scenario(module)

    body = scenario.interactions[0].response.body
    assert body is not None and body.template == {"provider": "value"}
    assert body.nodes[0].managed_snapshot is not None
    assert body.nodes[0].managed_snapshot.sha256 == scenario.snapshots[0].sha256

    outside = tmp_path.parent / "outside-double.json"
    outside.write_text("{}", encoding="utf-8")
    escaped = module.read_text(encoding="utf-8").replace(
        "managed.json", "../outside-double.json"
    )
    module.write_text(escaped, encoding="utf-8")
    with pytest.raises(SvcError) as caught:
        compile_scenario(module)
    assert caught.value.code == "double-local-path-outside-workspace"


def test_managed_raw_body_preserves_exact_bytes(tmp_path: Path) -> None:
    payload = b"\x00provider\xffbytes\n"
    (tmp_path / "payload.bin").write_bytes(payload)
    module = _write_module(
        tmp_path,
        _one_interaction(
            response=(
                "        status: 200\n"
                "        body:\n"
                "          raw:\n"
                "            $bsl:\n"
                "              kind: managed\n"
                "              source: payload.bin\n"
                "              media-type: application/octet-stream\n"
            )
        ),
    )

    scenario = compile_scenario(module)

    body = scenario.interactions[0].response.body
    assert body is not None and body.kind == "raw" and body.raw is not None
    assert body.raw.bytes == len(payload)
    assert body.raw == scenario.snapshots[0]


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-double-symlink.json"
    outside.write_text("{}", encoding="utf-8")
    link = tmp_path / "managed.json"
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("host cannot create symlinks")
    module = _write_module(
        tmp_path,
        _one_interaction(
            response=(
                "        status: 200\n"
                "        body:\n"
                "          structured:\n"
                "            $bsl: {kind: managed, source: managed.json, media-type: application/json}\n"
            )
        ),
    )

    with pytest.raises(SvcError) as caught:
        compile_scenario(module)

    assert caught.value.code == "double-local-path-outside-workspace"


def test_compile_inspects_materializer_without_executing_it(tmp_path: Path) -> None:
    sentinel = tmp_path / "executed"
    script = tmp_path / "materializer.py"
    script.write_text(
        "from pathlib import Path\nPath('executed').write_text('unexpected')\n",
        encoding="utf-8",
    )
    response = (
        "        status: 200\n"
        "        materializer:\n"
        f"          argv: [{sys.executable!r}, materializer.py]\n"
        "          cwd: .\n"
        "          env: {}\n"
        "          timeout-ms: 2000\n"
        "          max-output-bytes: 1048576\n"
    )
    module = _write_module(tmp_path, _one_interaction(response=response))

    scenario = compile_scenario(module)

    assert scenario.uses_materializer is True
    assert not sentinel.exists()
    materializer = scenario.interactions[0].response.materializer
    assert materializer is not None
    assert materializer.argv[0] == str(Path(sys.executable).resolve())
    assert "materializer-egress: not-enforced" in scenario.nonclaims


def test_event_materializer_owns_query_headers_and_body(tmp_path: Path) -> None:
    scenario = _one_interaction() + (
        "  events:\n"
        "    - name: callback\n"
        "      target: consumer.callback\n"
        "      provenance: {kind: synthetic, source: https://example.invalid/callback}\n"
        "      request:\n"
        "        method: POST\n"
        "        path: /callback\n"
        "        query: {signature: authored-but-dead}\n"
        "        materializer:\n"
        f"          argv: [{sys.executable!r}]\n"
        "          cwd: .\n"
        "          env: {}\n"
        "          timeout-ms: 2000\n"
        "          max-output-bytes: 1048576\n"
    )

    with pytest.raises(SvcError) as caught:
        compile_scenario(_write_module(tmp_path, scenario))

    assert caught.value.code == "invalid-double-materializer"


def test_materializer_cwd_does_not_make_digest_workspace_address_dependent(
    tmp_path: Path,
) -> None:
    response = (
        "        status: 200\n"
        "        materializer:\n"
        f"          argv: [{sys.executable!r}, materializer.py]\n"
        "          cwd: .\n"
        "          env: {}\n"
        "          timeout-ms: 2000\n"
        "          max-output-bytes: 1048576\n"
    )
    roots = [tmp_path / "first", tmp_path / "second"]
    for root in roots:
        root.mkdir()
        _write_module(root, _one_interaction(response=response))

    first = compile_scenario(roots[0] / "scenario.double.yaml")
    second = compile_scenario(roots[1] / "scenario.double.yaml")

    assert first.interactions[0].response.materializer is not None
    assert second.interactions[0].response.materializer is not None
    assert (
        first.interactions[0].response.materializer.cwd
        != second.interactions[0].response.materializer.cwd
    )
    assert first.scenario_digest == second.scenario_digest


def test_provider_capture_requires_explicit_sanitization(tmp_path: Path) -> None:
    module = _write_module(
        tmp_path,
        _one_interaction().replace(
            "{kind: synthetic, source: https://example.invalid/call}",
            "{kind: provider-capture, source: capture.json}",
        ),
    )
    (tmp_path / "capture.json").write_text("{}", encoding="utf-8")

    with pytest.raises(SvcError) as caught:
        compile_scenario(module)

    assert caught.value.code == "unsanitized-double-capture"


def test_header_names_reject_case_insensitive_duplicates(tmp_path: Path) -> None:
    module = _write_module(
        tmp_path,
        _one_interaction(
            request=(
                "        headers:\n"
                "          Content-Type: application/json\n"
                "          content-type: text/plain\n"
            )
        ),
    )

    with pytest.raises(SvcError) as caught:
        compile_scenario(module)

    assert caught.value.code == "duplicate-double-header"
    assert caught.value.details["header"] == "content-type"


def test_remote_openapi_reference_is_rejected_without_retrieval(tmp_path: Path) -> None:
    (tmp_path / "openapi.yaml").write_text(
        """\
openapi: 3.1.0
info: {title: fixture, version: 1.0.0}
paths:
  /call:
    post:
      requestBody:
        content:
          application/json:
            schema: {$ref: 'https://provider.invalid/schema.json'}
      responses:
        '200': {description: ok}
""",
        encoding="utf-8",
    )
    scenario = _one_interaction().replace(
        "boundary: {name: provider, protocol: http}",
        (
            "boundary:\n"
            "    name: provider\n"
            "    protocol: http\n"
            "    contract: {kind: openapi-3.1-operation, source: openapi.yaml, method: POST, path: /call}"
        ),
    )
    module = _write_module(tmp_path, scenario)

    with pytest.raises(SvcError) as caught:
        compile_scenario(module)

    assert caught.value.code == "invalid-double-contract"
    assert caught.value.details["ref"] == "https://provider.invalid/schema.json"


def test_local_openapi_path_item_ref_and_canonical_dialect_are_admitted(
    tmp_path: Path,
) -> None:
    (tmp_path / "openapi.yaml").write_text(
        """\
openapi: 3.1.0
jsonSchemaDialect: https://spec.openapis.org/oas/3.1/dialect/base
info: {title: fixture, version: 1.0.0}
paths:
  /call:
    $ref: '#/components/pathItems/Call'
components:
  pathItems:
    Call:
      post:
        responses:
          '200': {description: ok}
""",
        encoding="utf-8",
    )
    scenario = _one_interaction().replace(
        "boundary: {name: provider, protocol: http}",
        (
            "boundary:\n"
            "    name: provider\n"
            "    protocol: http\n"
            "    contract: {kind: openapi-3.1-operation, source: openapi.yaml, method: POST, path: /call}"
        ),
    )

    compiled = compile_scenario(_write_module(tmp_path, scenario))

    assert compiled.contract is not None
    assert compiled.contract.method == "POST"


def test_cross_file_recursive_openapi_schema_uses_immutable_registry() -> None:
    scenario = compile_scenario(FIXTURES / "recursive.double.yaml")

    contract = scenario.contract
    assert contract is not None and contract.request_schema is not None
    assert len(contract.schema_resources) == 2
    assert all(
        resource.uri.startswith("urn:svc:double:schema-resource:")
        for resource in contract.schema_resources
    )
    assert all(
        resource.snapshot_sha256 in {snapshot.sha256 for snapshot in scenario.snapshots}
        for resource in contract.schema_resources
    )
    assert "urn:svc:double:schema-resource:" in str(contract.request_schema)

    registry = Registry()
    for resource in contract.schema_resources:
        registry = registry.with_resource(
            resource.uri, DRAFT202012.create_resource(resource.document)
        )
    validator = Draft202012Validator(contract.request_schema, registry=registry)

    assert validator.is_valid(
        {"value": "root", "next": {"value": "child", "next": None}}
    )
    assert not validator.is_valid({"value": "root", "next": {"value": 1}})


@pytest.mark.parametrize(
    ("version", "contract_path", "dialect", "code"),
    [
        ("3.0.3", "/call", "", "invalid-double-contract"),
        ("3.1.0", "/calls/{id}", "", "unsupported-double-contract-path"),
        (
            "3.1.0",
            "/call",
            "jsonSchemaDialect: https://example.invalid/custom\n",
            "invalid-double-contract",
        ),
    ],
)
def test_openapi_profile_rejects_unsupported_versions_templates_and_dialects(
    tmp_path: Path, version: str, contract_path: str, dialect: str, code: str
) -> None:
    (tmp_path / "openapi.yaml").write_text(
        (
            f"openapi: {version}\n"
            f"{dialect}"
            "info: {title: fixture, version: 1.0.0}\n"
            "paths:\n"
            f"  {contract_path}:\n"
            "    post:\n"
            "      responses:\n"
            "        '200': {description: ok}\n"
        ),
        encoding="utf-8",
    )
    scenario = _one_interaction().replace(
        "boundary: {name: provider, protocol: http}",
        (
            "boundary:\n"
            "    name: provider\n"
            "    protocol: http\n"
            "    contract: "
            f"{{kind: openapi-3.1-operation, source: openapi.yaml, method: POST, path: '{contract_path}'}}"
        ),
    )
    module = _write_module(tmp_path, scenario)

    with pytest.raises(SvcError) as caught:
        compile_scenario(module)

    assert caught.value.code == code


@pytest.mark.parametrize(
    "using",
    ["faker.string/v1", "provider.payment-id/v1", "project.custom/v1"],
)
def test_project_and_provider_generators_are_outside_closed_registry(
    tmp_path: Path, using: str
) -> None:
    module = _write_module(
        tmp_path,
        _one_interaction(
            response=(
                "        status: 200\n"
                "        body:\n"
                "          structured:\n"
                "            value:\n"
                "              $bsl:\n"
                "                kind: generated\n"
                "                semantic: provider-value\n"
                f"                using: {using}\n"
                "                validate: {kind: regex, pattern: '^x$'}\n"
            )
        ),
    )

    with pytest.raises(SvcError) as caught:
        compile_scenario(module)

    assert caught.value.code == "unsupported-double-generator"
    assert caught.value.details["using"] == using


def test_invalid_re2_pattern_is_a_stable_compile_error(tmp_path: Path) -> None:
    module = _write_module(
        tmp_path,
        _one_interaction(
            request=(
                "        body:\n"
                "          structured:\n"
                "            value:\n"
                "              $bsl:\n"
                "                kind: match\n"
                "                match: {kind: regex, pattern: '['}\n"
            )
        ),
    )

    with pytest.raises(SvcError) as caught:
        compile_scenario(module)

    assert caught.value.code == "invalid-double-regex"
    assert "diagnostic" in caught.value.details


def test_yaml_reader_errors_and_symlink_loops_are_structured(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.double.yaml"
    invalid.write_bytes(b"\x00")
    with pytest.raises(SvcError) as caught:
        compile_scenario(invalid)
    assert caught.value.code == "invalid-double-yaml"

    loop = tmp_path / "loop.double.yaml"
    try:
        os.symlink(loop.name, loop)
    except OSError:
        pytest.skip("host cannot create symlinks")
    with pytest.raises(SvcError) as caught:
        compile_scenario(loop)
    assert caught.value.code == "double-module-unavailable"


def test_range_null_bound_and_generator_null_validator_are_rejected(
    tmp_path: Path,
) -> None:
    null_bound = _write_module(
        tmp_path,
        _one_interaction(
            request=(
                "        body:\n"
                "          structured:\n"
                "            value:\n"
                "              $bsl:\n"
                "                kind: match\n"
                "                match: {kind: range, minimum: null, maximum: 3}\n"
            )
        ),
    )
    with pytest.raises(SvcError) as caught:
        compile_scenario(null_bound)
    assert caught.value.code == "invalid-double-matcher"

    module = _write_module(
        tmp_path,
        _one_interaction(
            response=(
                "        status: 200\n"
                "        body:\n"
                "          structured:\n"
                "            value:\n"
                "              $bsl:\n"
                "                kind: generated\n"
                "                semantic: rfc.uuid\n"
                "                using: svc.uuid-v4/v1\n"
                "                validate: {kind: exact, value: null}\n"
            )
        ),
    )
    with pytest.raises(SvcError) as caught:
        compile_scenario(module)
    assert caught.value.code == "invalid-double-generator-validator"
