"""Shared, machine-first protocol primitives for Agent analysis tools."""

from __future__ import annotations

import base64
import json
from types import MappingProxyType
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict


class AnalysisProtocolError(ValueError):
    """Stable request, reference, and cursor error."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = MappingProxyType(dict(details or {}))

    def as_dict(self, *, version: int | None = None) -> dict[str, object]:
        value: dict[str, object] = {
            "code": self.code,
            "message": self.message,
        }
        if version == 3:
            value = {"format": "svc.analysis.error/v3", "version": 3, **value}
        if self.details:
            value["details"] = dict(self.details)
        return value


class AnalysisModel(BaseModel):
    """Strict immutable base for every typed analysis boundary object."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def encode_cursor(payload: BaseModel | Mapping[str, object]) -> str:
    """Encode one already-validated cursor model as opaque URL-safe text."""

    value = (
        payload.model_dump(mode="json")
        if isinstance(payload, BaseModel)
        else dict(payload)
    )
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_cursor(value: object) -> dict[str, Any]:
    """Decode cursor transport only; each tool owns its typed cursor model."""

    if not isinstance(value, str) or not value or len(value) > 8192:
        raise AnalysisProtocolError(
            "invalid-cursor",
            "Cursor must be bounded non-empty text.",
        )

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate cursor key")
            result[key] = item
        return result

    try:
        padding = "=" * (-len(value) % 4)
        raw = base64.b64decode(
            (value + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalysisProtocolError(
            "invalid-cursor",
            "Cursor is not a valid analysis continuation.",
        ) from error
    if not isinstance(payload, dict):
        raise AnalysisProtocolError(
            "invalid-cursor",
            "Cursor payload has an invalid shape.",
        )
    return payload


__all__ = [
    "AnalysisModel",
    "AnalysisProtocolError",
    "decode_cursor",
    "encode_cursor",
]
