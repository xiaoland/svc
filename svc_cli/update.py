"""Explicit, provenance-bound self-update planning for the installed CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution
from typing import Any

from . import DISTRIBUTION_NAME
from .catalog import canonical_json, require_semver, sha256_bytes
from .errors import SvcError


@dataclass(frozen=True)
class UpdateBlocker:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class SelfUpdatePlan:
    current_version: str | None
    command: tuple[str, ...] | None
    installer: str | None
    blockers: tuple[UpdateBlocker, ...]

    @property
    def status(self) -> str:
        return "blocked" if self.blockers else "ready"

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json(self.signature()))

    def signature(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": "self-update",
            "current_version": self.current_version,
            "installer": self.installer,
            "installer_command": list(self.command) if self.command else None,
            "blockers": [blocker.as_dict() for blocker in self.blockers],
        }

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": "self-update",
            "status": self.status,
            "current_version": self.current_version,
            "installer": self.installer,
            "installer_command": list(self.command) if self.command else None,
            "blockers": [blocker.as_dict() for blocker in self.blockers],
            "plan_digest": self.digest,
        }


def plan_self_update() -> SelfUpdatePlan:
    blockers: list[UpdateBlocker] = []
    try:
        installed = distribution(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return SelfUpdatePlan(
            None,
            None,
            None,
            (UpdateBlocker("distribution-not-installed", "The SVC distribution metadata is unavailable to this interpreter."),),
        )

    current = installed.version
    try:
        require_semver(current, "installed CLI version")
    except ValueError as error:
        blockers.append(UpdateBlocker("invalid-installed-version", str(error)))

    installer = (installed.read_text("INSTALLER") or "").strip() or None
    if installer != "pip":
        blockers.append(
            UpdateBlocker(
                "unsupported-installer",
                "Self-update currently supports only a non-editable pip installation in the current interpreter.",
            )
        )
    direct_url = installed.read_text("direct_url.json")
    if direct_url:
        try:
            direct = json.loads(direct_url)
        except json.JSONDecodeError:
            blockers.append(UpdateBlocker("invalid-install-provenance", "Installed direct_url metadata is invalid JSON."))
        else:
            if isinstance(direct, dict) and isinstance(direct.get("dir_info"), dict) and direct["dir_info"].get("editable"):
                blockers.append(
                    UpdateBlocker(
                        "editable-install",
                        "Self-update refuses an editable development installation; use the owning development tool instead.",
                    )
                )

    command = (sys.executable, "-m", "pip", "install", "--upgrade", DISTRIBUTION_NAME)
    return SelfUpdatePlan(current, command, installer, tuple(blockers))


def apply_self_update(plan: SelfUpdatePlan, approved_digest: str) -> dict[str, object]:
    if approved_digest != plan.digest:
        raise SvcError(
            "plan-digest-mismatch",
            "The supplied plan digest does not match the current self-update plan.",
            {"expected": plan.digest, "received": approved_digest},
        )
    if plan.blockers or plan.command is None or plan.current_version is None:
        raise SvcError(
            "plan-blocked",
            "The self-update plan has unresolved blockers.",
            {"blockers": [blocker.as_dict() for blocker in plan.blockers]},
        )
    current = _installed_version()
    if current != plan.current_version:
        raise SvcError(
            "stale-plan",
            "The installed CLI version changed after planning.",
            {"expected_version": plan.current_version, "actual_version": current},
        )
    completed = _run_update(plan.command)
    if completed.returncode != 0:
        raise SvcError(
            "self-update-failed",
            "The selected package-manager update command failed.",
            {"returncode": completed.returncode, "stderr": completed.stderr.strip()},
        )
    updated = _fresh_installed_version()
    return {
        "status": "updated" if updated != plan.current_version else "already-current",
        "previous_version": plan.current_version,
        "installed_cli_version": updated,
        "installer_command": list(plan.command),
        "plan_digest": plan.digest,
    }


def _installed_version() -> str | None:
    try:
        return distribution(DISTRIBUTION_NAME).version
    except PackageNotFoundError:
        return None


def _run_update(command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _fresh_installed_version() -> str:
    script = (
        "from importlib.metadata import version; "
        f"print(version({DISTRIBUTION_NAME!r}))"
    )
    completed = subprocess.run(
        (sys.executable, "-c", script),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise SvcError(
            "self-update-verification-failed",
            "The updated CLI version could not be verified in a fresh interpreter.",
            {"returncode": completed.returncode, "stderr": completed.stderr.strip()},
        )
    value = completed.stdout.strip()
    try:
        return require_semver(value, "updated CLI version")
    except ValueError as error:
        raise SvcError("self-update-verification-failed", str(error)) from error
