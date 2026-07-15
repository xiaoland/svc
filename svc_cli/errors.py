"""Stable error values shared by the CLI's machine and human interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SvcError(Exception):
    """An expected, structured command failure."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
        }
