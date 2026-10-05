"""Check the six authored Skill interfaces and their local Markdown references."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


SKILL_NAMES = frozenset(
    {
        "svc-task-packet",
        "svc-methods",
        "svc-verification",
        "svc-sub-agents",
        "svc-specs",
        "svc-taste",
    }
)
_LINK = re.compile(r'\[[^\]\n]+\]\((?:<([^>\n]+)>|([^\s)]+))(?:\s+"[^"]*")?\)')


def skill_metadata(path: Path) -> dict[str, str]:
    """Read this repository's two-field, single-line frontmatter convention."""

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"{path}: Skill frontmatter is missing")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise ValueError(f"{path}: Skill frontmatter is unclosed") from error
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(": ")
        if not separator or key in fields or key not in {"name", "description"}:
            raise ValueError(f"{path}: unsupported or duplicate Skill metadata")
        if key == "description":
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{path}: description must be a quoted single line"
                ) from error
            if not isinstance(parsed, str):
                raise ValueError(f"{path}: description must be a string")
            value = parsed
        fields[key] = value
    if set(fields) != {"name", "description"}:
        raise ValueError(f"{path}: name and description are required")
    name = fields["name"]
    if (
        len(name) > 64
        or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None
        or name != path.parent.name
    ):
        raise ValueError(f"{path}: name must match its Skill directory")
    if not fields["description"].strip() or len(fields["description"]) > 1024:
        raise ValueError(f"{path}: description must contain 1–1024 characters")
    return fields


def _prose(text: str) -> str:
    lines = []
    fence = None
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is None and not line.startswith("    "):
            lines.append(line)
    return "\n".join(lines)


def _anchors(text: str) -> set[str]:
    anchors = set()
    counts: dict[str, int] = {}
    for title in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", _prose(text), re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        anchors.add(f"{slug}-{count}" if count else slug)
    return anchors


def check_links(source: Path, boundary: Path) -> None:
    text = _prose(source.read_text(encoding="utf-8"))
    for match in _LINK.finditer(text):
        target = match.group(1) or match.group(2)
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        destination = (
            (source.parent / unquote(parsed.path)).resolve()
            if parsed.path
            else source.resolve()
        )
        if (
            not destination.is_relative_to(boundary.resolve())
            or not destination.is_file()
        ):
            raise ValueError(f"{source}: missing or escaping local target {target}")
        if parsed.fragment:
            if destination.suffix != ".md":
                raise ValueError(f"{source}: unsupported fragment target {target}")
            if unquote(parsed.fragment) not in _anchors(
                destination.read_text(encoding="utf-8")
            ):
                raise ValueError(f"{source}: missing local fragment {target}")


def check(corpus_root: Path) -> None:
    entries = sorted(corpus_root.rglob("SKILL.md"))
    expected = {corpus_root / name / "SKILL.md" for name in SKILL_NAMES}
    if set(entries) != expected:
        raise ValueError("Corpus must contain exactly the six declared Skill entries")
    for entry in entries:
        skill_metadata(entry)
    for source in sorted(corpus_root.rglob("*.md")):
        if source.is_symlink():
            raise ValueError(f"Corpus Markdown must not be a symlink: {source}")
        check_links(source, corpus_root.parent)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    check(Path(__file__).resolve().parents[1] / "corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
