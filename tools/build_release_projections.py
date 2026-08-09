"""Validate structured Changie facts and derive SVC release projections."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml
from semantic_version import Version

from svc_cli.catalog import canonical_json
from svc_cli.catalog import parse_version_index


SUPPORTED_CORPUS_ANCHOR = "10.0.1"
FRAGMENT_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_DIRECTORY_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
GUIDANCE_HEADINGS = ("### Applies when", "### Required change", "### Verify")
KINDS = ("patch", "minor", "major")
COMPONENTS = {"cli", "config", "corpus"}
MIGRATIONS = {"not-applicable", "not-required", "guide"}


class StrictLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_mapping(
    loader: StrictLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[object, object]:
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


@dataclass(frozen=True)
class ChangeFragment:
    change_id: str
    source_id: str
    kind: str
    component: str
    body: str
    migration: str
    from_schema: int | None
    to_schema: int | None
    guidance: str | None


@dataclass(frozen=True)
class Projection:
    version_index: bytes
    corpus_guides: tuple[tuple[str, bytes], ...]
    config_descriptors: tuple[tuple[str, bytes], ...]

    def files(self, root: Path) -> dict[Path, bytes]:
        files = {root / "src/version.json": self.version_index}
        files.update(
            {root / "src" / path: content for path, content in self.corpus_guides}
        )
        files.update(
            {
                root / "svc_cli/data/migrations" / name: content
                for name, content in self.config_descriptors
            }
        )
        return files


def _load_yaml(path: Path) -> dict[str, object]:
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"), Loader=StrictLoader)
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError) as error:
        raise ValueError(f"Invalid Changie fragment {path}: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError(f"Changie fragment must be an object: {path}")
    return raw


def _optional_schema(value: object, label: str, path: Path) -> int | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not value.isdigit() or int(value) < 1:
        raise ValueError(f"{path}: {label} must be a positive integer string")
    return int(value)


def read_fragment(path: Path, source_id: str) -> ChangeFragment:
    raw = _load_yaml(path)
    if set(raw) != {"kind", "component", "body", "custom", "time"}:
        raise ValueError(f"{path}: fragment has unsupported or missing fields")
    change_id = path.stem
    if not FRAGMENT_ID_RE.fullmatch(change_id):
        raise ValueError(f"{path}: filename is not a stable change identity")
    kind = raw.get("kind")
    component = raw.get("component")
    body = raw.get("body")
    custom = raw.get("custom")
    if kind not in KINDS:
        raise ValueError(f"{path}: kind must be one of {KINDS}")
    if component not in COMPONENTS:
        raise ValueError(f"{path}: component must be one of {sorted(COMPONENTS)}")
    if not isinstance(body, str) or not body.strip():
        raise ValueError(f"{path}: body must be non-empty")
    if not isinstance(custom, dict) or set(custom) != {
        "Migration",
        "FromSchema",
        "ToSchema",
        "Guidance",
    }:
        raise ValueError(f"{path}: custom migration fields are incomplete")
    migration = custom.get("Migration")
    if migration not in MIGRATIONS:
        raise ValueError(f"{path}: Migration must be one of {sorted(MIGRATIONS)}")
    from_schema = _optional_schema(custom.get("FromSchema"), "FromSchema", path)
    to_schema = _optional_schema(custom.get("ToSchema"), "ToSchema", path)
    guidance_raw = custom.get("Guidance")
    guidance = (
        guidance_raw.strip() if isinstance(guidance_raw, str) and guidance_raw.strip() else None
    )

    if component == "cli":
        if migration != "not-applicable" or any(
            value is not None for value in (from_schema, to_schema, guidance)
        ):
            raise ValueError(
                f"{path}: CLI fragments use only Migration=not-applicable"
            )
    elif component == "config":
        if migration == "not-applicable":
            raise ValueError(f"{path}: config migration needs an explicit disposition")
        if from_schema is None or to_schema is None or from_schema >= to_schema:
            raise ValueError(f"{path}: config fragment needs an advancing schema pair")
        if (migration == "guide") != (guidance is not None):
            raise ValueError(
                f"{path}: config guide disposition and Guidance must agree"
            )
    else:
        if migration == "not-applicable":
            raise ValueError(f"{path}: Corpus fragment needs a migration disposition")
        if from_schema is not None or to_schema is not None:
            raise ValueError(f"{path}: Corpus fragments cannot name config schemas")
        if (migration == "guide") != (guidance is not None):
            raise ValueError(
                f"{path}: Corpus guide disposition and Guidance must agree"
            )
        legacy_import = source_id == "v11.0.0/v11-agent-observability"
        if guidance is not None and not legacy_import:
            missing = [heading for heading in GUIDANCE_HEADINGS if heading not in guidance]
            if missing:
                raise ValueError(
                    f"{path}: Corpus guidance is missing {', '.join(missing)}"
                )

    return ChangeFragment(
        change_id=change_id,
        source_id=source_id,
        kind=str(kind),
        component=str(component),
        body=body.strip(),
        migration=str(migration),
        from_schema=from_schema,
        to_schema=to_schema,
        guidance=guidance,
    )


def _retained_groups(root: Path) -> list[tuple[str, tuple[ChangeFragment, ...]]]:
    fragments_root = root / "changes/fragments"
    groups = []
    if fragments_root.is_dir():
        directories = sorted(
            (path for path in fragments_root.iterdir() if path.is_dir()),
            key=lambda path: Version(path.name.removeprefix("v")),
        )
        for directory in directories:
            if not VERSION_DIRECTORY_RE.fullmatch(directory.name):
                raise ValueError(
                    f"Retained fragment directory is not vX.Y.Z: {directory}"
                )
            package_version = directory.name.removeprefix("v")
            fragments = tuple(
                read_fragment(path, f"{directory.name}/{path.stem}")
                for path in sorted(directory.glob("*.yaml"))
            )
            if not fragments:
                raise ValueError(f"Retained fragment directory is empty: {directory}")
            groups.append((package_version, fragments))
    unreleased = root / "changes/unreleased"
    pending = tuple(
        read_fragment(path, f"unreleased/{path.stem}")
        for path in sorted(unreleased.glob("*.yaml"))
    )
    if pending:
        groups.append(("unreleased", pending))
    return groups


def _bump(version: str, kinds: Iterable[str]) -> str:
    highest = max(kinds, key=KINDS.index)
    current = Version(version)
    if highest == "major":
        return str(current.next_major())
    if highest == "minor":
        return str(current.next_minor())
    return str(current.next_patch())


def _guide_bytes(fragment: ChangeFragment, corpus_version: str) -> bytes:
    assert fragment.guidance is not None
    if fragment.source_id == "v11.0.0/v11-agent-observability":
        if not fragment.guidance.startswith("# "):
            raise ValueError("Legacy 11.0.0 guidance import must contain its title")
        return (fragment.guidance.rstrip() + "\n").encode("utf-8")
    title = fragment.body.rstrip(".")
    return (
        f"# {title}\n\n"
        f"Corpus release: {corpus_version}.\n\n"
        f"{fragment.guidance.rstrip()}\n"
    ).encode("utf-8")


def _project_corpus(
    groups: Sequence[tuple[str, tuple[ChangeFragment, ...]]],
) -> tuple[bytes, tuple[tuple[str, bytes], ...]]:
    previous = SUPPORTED_CORPUS_ANCHOR
    releases: list[dict[str, object]] = []
    guides: list[tuple[str, bytes]] = []
    seen_guide_paths: set[str] = set()
    for _, fragments in groups:
        corpus = tuple(item for item in fragments if item.component == "corpus")
        if not corpus:
            continue
        version = _bump(previous, (item.kind for item in corpus))
        paths = []
        for fragment in corpus:
            if fragment.migration != "guide":
                continue
            path = (
                "migrations/11.0.0.md"
                if fragment.source_id == "v11.0.0/v11-agent-observability"
                else f"migrations/{fragment.change_id}.md"
            )
            if path in seen_guide_paths:
                raise ValueError(f"Corpus guide path is repeated: {path}")
            seen_guide_paths.add(path)
            paths.append(path)
            guides.append((path, _guide_bytes(fragment, version)))
        migration: dict[str, object]
        if paths:
            migration = {"status": "guide", "paths": paths}
        else:
            migration = {"status": "not-required"}
        releases.append(
            {
                "version": version,
                "previous_version": previous,
                "migration": migration,
            }
        )
        previous = version
    if not releases:
        raise ValueError("No retained or pending Corpus release facts were found")
    return canonical_json({"schema_version": 1, "releases": releases}), tuple(guides)


def _project_config(
    groups: Sequence[tuple[str, tuple[ChangeFragment, ...]]],
) -> tuple[tuple[str, bytes], ...]:
    by_step: dict[tuple[int, int], list[ChangeFragment]] = {}
    for _, fragments in groups:
        for fragment in fragments:
            if fragment.component != "config":
                continue
            assert fragment.from_schema is not None and fragment.to_schema is not None
            by_step.setdefault(
                (fragment.from_schema, fragment.to_schema), []
            ).append(fragment)
    descriptors = []
    for (from_schema, to_schema), fragments in sorted(by_step.items()):
        ordered = sorted(fragments, key=lambda item: item.source_id)
        guidance = [
            {
                "change_id": fragment.source_id,
                "body": fragment.body,
                "guidance": fragment.guidance,
            }
            for fragment in ordered
            if fragment.migration == "guide"
        ]
        guidance_bundle = canonical_json(guidance)
        descriptor = {
            "schema_version": 1,
            "from_schema": from_schema,
            "to_schema": to_schema,
            "transform": f"config-v{from_schema}-to-v{to_schema}",
            "change_ids": [fragment.source_id for fragment in ordered],
            "guidance": guidance,
            "guidance_sha256": hashlib.sha256(guidance_bundle).hexdigest(),
        }
        descriptors.append(
            (f"config-{from_schema}-{to_schema}.json", canonical_json(descriptor))
        )
    return tuple(descriptors)


def build_release_projections(root: Path) -> Projection:
    groups = _retained_groups(root)
    version_index, guides = _project_corpus(groups)
    return Projection(version_index, guides, _project_config(groups))


def apply_projection(root: Path, *, check: bool) -> None:
    projection = build_release_projections(root)
    expected = projection.files(root)
    generated_roots = (
        root / "src/migrations",
        root / "svc_cli/data/migrations",
    )
    expected_paths = set(expected)
    extras = {
        path
        for directory in generated_roots
        if directory.is_dir()
        for path in directory.glob("*.md" if directory.name == "migrations" and directory.parent.name == "src" else "*.json")
        if path not in expected_paths
    }
    # The published pre-fragment 11.0.0 guide is imported as a retained
    # fragment and therefore also appears in expected when the projection is complete.
    if check:
        changed = {
            path
            for path, content in expected.items()
            if not path.is_file() or path.read_bytes() != content
        }
        if changed or extras:
            names = [str(path.relative_to(root)) for path in sorted(changed | extras)]
            raise ValueError("Release projections are stale: " + ", ".join(names))
        return
    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for path in extras:
        path.unlink()


def validate_corpus_change(
    *, substantive_change: bool, base_version: str, current_version: str
) -> None:
    if substantive_change and Version(current_version) <= Version(base_version):
        raise ValueError(
            "Corpus source changed without advancing the Corpus release: "
            f"{base_version} -> {current_version}"
        )
    if not substantive_change and current_version != base_version:
        raise ValueError(
            "Corpus release advanced without a substantive Corpus source change: "
            f"{base_version} -> {current_version}"
        )


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ("git", *args),
        cwd=root,
        check=check,
        capture_output=True,
    )


def _base_corpus_version(root: Path, ref: str) -> str:
    indexed = _git(root, "show", f"{ref}:src/version.json", check=False)
    if indexed.returncode == 0:
        return parse_version_index(indexed.stdout).corpus_version

    # Bootstrap only: before src/version.json, released tags stamped the
    # packaged Corpus with the exact package tag. Do not use this fallback once
    # a ref contains the independent index.
    tagged = _git(root, "describe", "--tags", "--abbrev=0", ref)
    tag = tagged.stdout.decode("utf-8").strip()
    if not VERSION_DIRECTORY_RE.fullmatch(tag):
        raise ValueError(f"Cannot determine bootstrap Corpus version at {ref}")
    return tag.removeprefix("v")


def check_corpus_change(root: Path, base_ref: str) -> None:
    current = parse_version_index((root / "src/version.json").read_bytes())
    diff = _git(
        root,
        "diff",
        "--quiet",
        base_ref,
        "--",
        "src",
        ":(exclude)src/version.json",
        check=False,
    )
    if diff.returncode not in {0, 1}:
        raise ValueError(diff.stderr.decode("utf-8", errors="replace").strip())
    validate_corpus_change(
        substantive_change=diff.returncode == 1,
        base_version=_base_corpus_version(root, base_ref),
        current_version=current.corpus_version,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--compare-ref")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    apply_projection(root, check=args.check)
    if args.compare_ref:
        check_corpus_change(root, args.compare_ref)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
