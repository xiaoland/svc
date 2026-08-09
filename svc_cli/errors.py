"""Stable error values shared by the CLI's machine and human interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .machine import MachineError, MachineErrorBody, json_compatible


@dataclass
class SvcError(Exception):
    """An expected, structured command failure."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_output(self) -> MachineError:
        details = json_compatible(self.details)
        assert isinstance(details, dict)
        return MachineError(
            error=MachineErrorBody(
                code=self.code,
                message=self.message,
                details=details,
            )
        )
