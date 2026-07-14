from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as distribution_version
from pathlib import PurePosixPath
from typing import Any

from .resources import read_resource


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
FILE_CLASSES = {"svc-managed", "consumer-owned", "generated"}
IMPACT_LEVELS = {"major", "minor", "patch"}
CLASS_ACTIONS = {
    "svc-managed": ("create", "replace-clean"),
    "consumer-owned": ("create-if-absent", "preserve"),
    "generated": ("generate", "regenerate"),
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def validate_behavioral_bump(previous: str, current: str, impact_level: str) -> None:
    if impact_level not in IMPACT_LEVELS:
        raise ValueError(f"Unknown behavioral impact: {impact_level}")
    if not SEMVER_RE.fullmatch(previous) or not SEMVER_RE.fullmatch(current):
        raise ValueError("Behavioral SemVer validation requires stable x.y.z versions")
    before = tuple(int(part) for part in previous.split("."))
    after = tuple(int(part) for part in current.split("."))
    if after <= before:
        raise ValueError(f"Version must increase: {previous} -> {current}")
    actual = (
        "major"
        if after[0] != before[0]
        else "minor"
        if after[1] != before[1]
        else "patch"
    )
    if actual != impact_level:
        raise ValueError(
            f"Declared {impact_level} impact requires a {impact_level} bump, got {previous} -> {current}"
        )


def safe_relative_path(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError(f"{label} must be a normalized relative path: {value!r}")
    return path.as_posix()


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    file_class: str
    target: str
    init_action: str
    upgrade_action: str
    source: str | None = None
    digest: str | None = None
    generator: str | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "Artifact":
        artifact_id = raw.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError("Every manifest artifact requires a non-empty id")
        file_class = raw.get("class")
        if file_class not in FILE_CLASSES:
            raise ValueError(f"Unknown class for {artifact_id}: {file_class!r}")
        target = safe_relative_path(raw.get("target", ""), f"target for {artifact_id}")
        source = raw.get("source")
        digest = raw.get("sha256")
        generator = raw.get("generator")
        actions = (raw.get("init_action"), raw.get("upgrade_action"))
        if actions != CLASS_ACTIONS[file_class]:
            raise ValueError(
                f"Invalid init/upgrade actions for {artifact_id}: {actions!r}"
            )

        if file_class == "generated":
            if source is not None or digest is not None or not isinstance(generator, str):
                raise ValueError(f"Generated artifact {artifact_id} must declare only a generator")
        else:
            if not isinstance(source, str) or not isinstance(digest, str):
                raise ValueError(f"File artifact {artifact_id} requires source and sha256")
            source = safe_relative_path(source, f"source for {artifact_id}")
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"Invalid sha256 for {artifact_id}")

        return cls(
            artifact_id=artifact_id,
            file_class=file_class,
            target=target,
            init_action=str(raw.get("init_action", "")),
            upgrade_action=str(raw.get("upgrade_action", "")),
            source=source,
            digest=digest,
            generator=generator,
        )

    def content(self) -> bytes:
        if self.source is None:
            raise ValueError(f"Generated artifact {self.artifact_id} has no source payload")
        content = read_resource(self.source)
        actual = sha256_bytes(content)
        if actual != self.digest:
            raise ValueError(
                f"Release payload digest mismatch for {self.artifact_id}: "
                f"manifest={self.digest}, actual={actual}"
            )
        return content


@dataclass(frozen=True)
class ReleaseManifest:
    schema_version: int
    previous_version: str
    svc_version: str
    impact_level: str
    impact_reasons: tuple[str, ...]
    artifacts: tuple[Artifact, ...]
    digest: str

    def by_id(self, artifact_id: str) -> Artifact:
        for artifact in self.artifacts:
            if artifact.artifact_id == artifact_id:
                return artifact
        raise KeyError(artifact_id)

    @property
    def managed(self) -> tuple[Artifact, ...]:
        return tuple(a for a in self.artifacts if a.file_class == "svc-managed")

    @property
    def consumer_owned(self) -> tuple[Artifact, ...]:
        return tuple(a for a in self.artifacts if a.file_class == "consumer-owned")

    @property
    def state_artifact(self) -> Artifact:
        generated = [a for a in self.artifacts if a.generator == "svc.state.v1"]
        if len(generated) != 1:
            raise ValueError("Manifest must declare exactly one svc.state.v1 artifact")
        return generated[0]


def load_manifest() -> ReleaseManifest:
    content = read_resource("manifest.json")
    raw = json.loads(content)
    if raw.get("schema_version") != 1:
        raise ValueError(f"Unsupported manifest schema: {raw.get('schema_version')!r}")
    version = raw.get("svc_version")
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
        raise ValueError(f"Invalid SVC version: {version!r}")
    previous_version = raw.get("previous_version")
    if not isinstance(previous_version, str) or not SEMVER_RE.fullmatch(previous_version):
        raise ValueError(f"Invalid previous SVC version: {previous_version!r}")
    impact = raw.get("behavioral_impact")
    if not isinstance(impact, dict) or impact.get("level") not in IMPACT_LEVELS:
        raise ValueError("Manifest requires a valid behavioral_impact")
    reasons = impact.get("reasons")
    if not isinstance(reasons, list) or not reasons or not all(isinstance(x, str) for x in reasons):
        raise ValueError("behavioral_impact requires non-empty reasons")

    artifacts = tuple(Artifact.parse(item) for item in raw.get("artifacts", []))
    ids = [item.artifact_id for item in artifacts]
    targets = [item.target for item in artifacts]
    if len(ids) != len(set(ids)) or len(targets) != len(set(targets)):
        raise ValueError("Manifest artifact ids and targets must be unique")

    manifest = ReleaseManifest(
        schema_version=1,
        previous_version=previous_version,
        svc_version=version,
        impact_level=impact["level"],
        impact_reasons=tuple(reasons),
        artifacts=artifacts,
        digest=sha256_bytes(content),
    )
    validate_behavioral_bump(previous_version, version, manifest.impact_level)
    try:
        installed_distribution_version = distribution_version("sustainable-vibe-coding")
    except PackageNotFoundError:
        installed_distribution_version = None
    if installed_distribution_version and installed_distribution_version != version:
        raise ValueError(
            "Distribution and release manifest versions differ: "
            f"{installed_distribution_version} != {version}"
        )
    manifest.state_artifact
    for artifact in artifacts:
        if artifact.source:
            artifact.content()
    return manifest
