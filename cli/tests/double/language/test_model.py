from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from svc_cli.double.model import (
    ExactMatcher,
    LiteralValueNode,
    Matcher,
    ValueNode,
)

MATCHER_ADAPTER = TypeAdapter(Matcher)
VALUE_NODE_ADAPTER = TypeAdapter(ValueNode)


def test_tagged_ir_rejects_cross_variant_and_missing_fields() -> None:
    invalid_values = (
        (MATCHER_ADAPTER, {"kind": "exact", "value": 1, "values": (1,)}),
        (MATCHER_ADAPTER, {"kind": "range"}),
        (
            VALUE_NODE_ADAPTER,
            {
                "kind": "derived",
                "path": (),
                "validator": {"kind": "exact", "value": None},
            },
        ),
        (
            VALUE_NODE_ADAPTER,
            {
                "kind": "capture",
                "path": (),
                "name": "captured",
                "matcher": {"kind": "exact", "value": 1},
                "expression": "request.body",
            },
        ),
    )

    for adapter, value in invalid_values:
        with pytest.raises(ValidationError):
            adapter.validate_python(value)

    assert ExactMatcher(value=None).value is None
    assert LiteralValueNode(path=(), value=None).value is None
