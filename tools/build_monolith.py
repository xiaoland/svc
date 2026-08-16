from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlsplit

ATX_HEADING_RE = re.compile(r"^(#{1,6})([ \t]+.*)?$")
INLINE_LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)]+)\)")
REFERENCE_LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\[([^\]]*)\]")
REFERENCE_DEF_RE = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s*(.+?)\s*$")
FENCE_RE = re.compile(r"^[ \t]*([`~]{3,})")


@dataclass(frozen=True)
class LinkTarget:
    path: Path
    fragment: str | None = None


@dataclass(frozen=True)
class Heading:
    line_no: int
    level: int
    anchor: str


@dataclass
class Document:
    path: Path
    relpath: Path
    text: str
    links: list[LinkTarget]
    reference_definitions: dict[str, str]
    headings_by_line: dict[int, Heading]
    fragment_to_anchor: dict[str, str]
    document_anchor: str


class MonolithBuilder:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.documents: dict[Path, Document] = {}
        self.order: list[Path] = []
        self.depth_by_path: dict[Path, int] = {}

    def build(self, entry: Path) -> str:
        entry = entry.resolve()
        if not entry.exists():
            raise FileNotFoundError(f"Entry markdown does not exist: {entry}")
        if not self._is_within_root(entry):
            raise ValueError(f"Entry markdown must be inside root {self.root}: {entry}")
        self._walk(entry, depth=0)

        chunks = [self._build_header(entry)]
        for index, path in enumerate(self.order):
            if index > 0:
                chunks.append("\n\n---\n\n")
            doc = self.documents[path]
            depth = self.depth_by_path[path]
            chunks.append(f"<!-- Source: {doc.relpath.as_posix()} -->\n")
            chunks.append(self._render_document(doc, depth))
        return "".join(chunks).rstrip() + "\n"

    def _walk(self, path: Path, depth: int) -> None:
        if path in self.depth_by_path:
            return

        doc = self._load_document(path)
        self.depth_by_path[path] = depth
        self.order.append(path)

        for link in doc.links:
            target_doc = self._load_document(link.path)
            if link.fragment:
                fragment_key = slugify(unquote(link.fragment))
                if fragment_key not in target_doc.fragment_to_anchor:
                    raise ValueError(
                        "Missing Markdown fragment "
                        f"'#{link.fragment}' in {target_doc.relpath.as_posix()} "
                        f"(linked from {doc.relpath.as_posix()})"
                    )
            if link.path == path:
                continue
            self._walk(link.path, depth + 1)

    def _load_document(self, path: Path) -> Document:
        if path in self.documents:
            return self.documents[path]

        text = path.read_text(encoding="utf-8")
        relpath = path.relative_to(self.root)
        file_anchor_prefix = slugify(relpath.as_posix())

        headings_by_line: dict[int, Heading] = {}
        fragment_to_anchor: dict[str, str] = {}
        fragment_counts: defaultdict[str, int] = defaultdict(int)
        first_heading_anchor: str | None = None

        for line_no, line, is_code in iter_lines(text):
            if is_code:
                continue
            match = ATX_HEADING_RE.match(line.rstrip("\n"))
            if not match:
                continue
            level = len(match.group(1))
            raw_body = (match.group(2) or "").strip()
            cleaned_body = strip_trailing_heading_hashes(raw_body)
            fragment_base = slugify(cleaned_body)
            count = fragment_counts[fragment_base]
            fragment_counts[fragment_base] += 1
            fragment = fragment_base if count == 0 else f"{fragment_base}-{count}"
            anchor = f"{file_anchor_prefix}__{fragment}"
            headings_by_line[line_no] = Heading(line_no=line_no, level=level, anchor=anchor)
            fragment_to_anchor[fragment] = anchor
            if first_heading_anchor is None:
                first_heading_anchor = anchor

        document_anchor = first_heading_anchor or file_anchor_prefix
        if first_heading_anchor is None:
            fragment_to_anchor.setdefault(file_anchor_prefix, document_anchor)

        reference_definitions = self._parse_reference_definitions(text)
        links = self._parse_links(path, text, reference_definitions)

        doc = Document(
            path=path,
            relpath=relpath,
            text=text,
            links=links,
            reference_definitions=reference_definitions,
            headings_by_line=headings_by_line,
            fragment_to_anchor=fragment_to_anchor,
            document_anchor=document_anchor,
        )
        self.documents[path] = doc
        return doc

    def _parse_reference_definitions(self, text: str) -> dict[str, str]:
        definitions: dict[str, str] = {}
        for _, line, is_code in iter_lines(text):
            if is_code:
                continue
            match = REFERENCE_DEF_RE.match(line.rstrip("\n"))
            if not match:
                continue
            label = normalize_reference_label(match.group(1))
            destination = extract_destination(match.group(2))
            if destination:
                definitions[label] = destination
        return definitions

    def _parse_links(
        self,
        current_path: Path,
        text: str,
        reference_definitions: dict[str, str],
    ) -> list[LinkTarget]:
        visible_text = visible_text_only(text)
        matches: list[tuple[int, str]] = []

        for match in INLINE_LINK_RE.finditer(visible_text):
            destination = extract_destination(match.group(2))
            if destination:
                matches.append((match.start(), destination))

        for match in REFERENCE_LINK_RE.finditer(visible_text):
            reference_key = normalize_reference_label(match.group(2) or match.group(1))
            destination = reference_definitions.get(reference_key)
            if not destination:
                raise ValueError(
                    "Undefined Markdown reference label "
                    f"'[{reference_key}]' in {current_path.relative_to(self.root).as_posix()}"
                )
            matches.append((match.start(), destination))

        targets: list[LinkTarget] = []
        seen: set[tuple[Path, str | None]] = set()
        for _, destination in sorted(matches, key=lambda item: item[0]):
            target = self._resolve_target(current_path, destination)
            if not target:
                if is_local_markdown_destination(destination):
                    raise ValueError(
                        f"Local Markdown target escapes root {self.root}: "
                        f"{current_path.relative_to(self.root).as_posix()} -> {destination}"
                    )
                continue
            if not target.path.exists():
                raise FileNotFoundError(
                    "Local Markdown target does not exist: "
                    f"{current_path.relative_to(self.root).as_posix()} -> {destination}"
                )
            key = (target.path, target.fragment)
            if key in seen:
                continue
            seen.add(key)
            targets.append(target)
        return targets

    def _render_document(self, doc: Document, depth: int) -> str:
        rendered_lines: list[str] = []
        for line_no, line, is_code in iter_lines(doc.text):
            if is_code:
                rendered_lines.append(line)
                continue

            definition_match = REFERENCE_DEF_RE.match(line.rstrip("\n"))
            if definition_match:
                label = definition_match.group(1)
                destination = extract_destination(definition_match.group(2))
                resolved = self._resolve_render_anchor(doc.path, destination)
                if resolved:
                    rendered_lines.append(f"[{label}]: {resolved}{newline_for(line)}")
                else:
                    rendered_lines.append(line)
                continue

            heading = doc.headings_by_line.get(line_no)
            current_line = line
            if heading:
                current_line = bump_heading_depth(current_line, depth)
                rendered_lines.append(f"<a id=\"{heading.anchor}\"></a>{newline_for(line)}")

            rendered_lines.append(self._rewrite_inline_links(doc.path, current_line))

        return "".join(rendered_lines)

    def _rewrite_inline_links(self, current_path: Path, text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            label, raw_target = match.group(1), match.group(2)
            destination = extract_destination(raw_target)
            resolved = self._resolve_render_anchor(current_path, destination)
            if not resolved:
                return match.group(0)
            return f"[{label}]({resolved})"

        return INLINE_LINK_RE.sub(replace, text)

    def _resolve_render_anchor(self, current_path: Path, destination: str | None) -> str | None:
        if not destination:
            return None
        target = self._resolve_target(current_path, destination)
        if not target:
            return None
        doc = self._load_document(target.path)
        if target.fragment:
            fragment_key = slugify(unquote(target.fragment))
            anchor = doc.fragment_to_anchor.get(fragment_key)
            if anchor is None:
                raise ValueError(
                    f"Missing Markdown fragment '#{target.fragment}' in {doc.relpath.as_posix()}"
                )
        else:
            anchor = doc.document_anchor
        return f"#{anchor}"

    def _resolve_target(self, current_path: Path, destination: str) -> LinkTarget | None:
        parsed = urlsplit(destination)
        if parsed.scheme or parsed.netloc:
            return None

        if destination.startswith("#"):
            fragment = destination[1:] or None
            return LinkTarget(path=current_path.resolve(), fragment=fragment)

        path_part, hash_mark, fragment = destination.partition("#")
        if not path_part:
            if not hash_mark:
                return None
            return LinkTarget(path=current_path.resolve(), fragment=fragment or None)

        resolved_path = (current_path.parent / unquote(path_part)).resolve()
        if resolved_path.suffix.lower() != ".md":
            return None
        if not self._is_within_root(resolved_path):
            return None
        return LinkTarget(path=resolved_path, fragment=fragment or None)

    def _build_header(self, entry: Path) -> str:
        generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        lines = [
            "<!--\n",
            "Generated by tools.build_monolith\n",
            f"Entry: {entry.relative_to(self.root).as_posix()}\n",
            f"Root: {self.root.as_posix()}\n",
            f"Generated at: {generated_at}\n",
            "Included files:\n",
        ]
        for path in self.order:
            lines.append(f"- {self.documents[path].relpath.as_posix()}\n")
        lines.append("-->\n\n")
        return "".join(lines)

    def _is_within_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.root)
        except ValueError:
            return False
        return True


def bump_heading_depth(line: str, depth: int) -> str:
    match = ATX_HEADING_RE.match(line.rstrip("\n"))
    if not match:
        return line
    level = min(6, len(match.group(1)) + depth)
    rest = match.group(2) or ""
    return f"{'#' * level}{rest}{newline_for(line)}"


def extract_destination(raw_target: str) -> str | None:
    target = raw_target.strip()
    if not target:
        return None

    if target.startswith("<"):
        closing = target.find(">")
        if closing == -1:
            return None
        return target[1:closing]

    return target.split(maxsplit=1)[0]


def is_local_markdown_destination(destination: str) -> bool:
    parsed = urlsplit(destination)
    if parsed.scheme or parsed.netloc:
        return False
    path_part = destination.partition("#")[0]
    return bool(path_part) and Path(unquote(path_part)).suffix.lower() == ".md"


def iter_lines(text: str) -> Iterable[tuple[int, str, bool]]:
    in_code_block = False
    fence_char = ""
    fence_length = 0

    for line_no, line in enumerate(text.splitlines(keepends=True), start=1):
        fence_match = FENCE_RE.match(line)
        if in_code_block:
            yield line_no, line, True
            if fence_match and fence_match.group(1)[0] == fence_char and len(fence_match.group(1)) >= fence_length:
                in_code_block = False
            continue

        if fence_match:
            in_code_block = True
            fence_char = fence_match.group(1)[0]
            fence_length = len(fence_match.group(1))
            yield line_no, line, True
            continue

        yield line_no, line, False


def visible_text_only(text: str) -> str:
    chunks: list[str] = []
    for _, line, is_code in iter_lines(text):
        if is_code:
            chunks.append("\n" if line.endswith("\n") else "")
        else:
            chunks.append(line)
    return "".join(chunks)


def newline_for(text: str) -> str:
    return "\n" if text.endswith("\n") else ""


def normalize_reference_label(label: str) -> str:
    return " ".join(label.strip().lower().split())


def slugify(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"`([^`]*)`", r"\1", lowered)
    lowered = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", lowered)
    lowered = re.sub(r"<[^>]+>", "", lowered)
    lowered = re.sub(r"[*_~]", "", lowered)
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = lowered.strip("-")
    return lowered or "section"


def strip_trailing_heading_hashes(text: str) -> str:
    return re.sub(r"[ \t]+#+[ \t]*$", "", text).strip()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a monolithic markdown file or validate every canonical "
            "markdown document."
        ),
    )
    parser.add_argument(
        "--entry",
        default="src/index.md",
        help="Entry markdown file to start traversing from (default: src/index.md).",
    )
    parser.add_argument(
        "--output",
        default="build/monolith.md",
        help="Output markdown path (default: build/monolith.md).",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Root directory allowed for recursive traversal (default: entry parent).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate links and fragments in every markdown file under the root.",
    )
    return parser.parse_args(argv)


def canonical_markdown_files(root: Path) -> list[Path]:
    """Return every canonical markdown source in deterministic order."""

    return sorted(path for path in root.rglob("*.md") if path.is_file())


def validate_markdown_corpus(root: Path) -> tuple[Path, ...]:
    """Validate links and fragments for the complete canonical corpus.

    ``MonolithBuilder.build`` intentionally follows only the reachable graph
    from its entry document.  The repository quality gate needs a stronger
    invariant: an orphan document must be valid too.  Build each document as
    an entry point so this check remains independent of the generated
    monolith's traversal order.
    """

    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Markdown corpus root does not exist: {root}")

    documents = tuple(canonical_markdown_files(root))
    for path in documents:
        try:
            MonolithBuilder(root).build(path)
        except (FileNotFoundError, ValueError) as error:
            relative = path.relative_to(root).as_posix()
            raise type(error)(f"{relative}: {error}") from error
    return documents


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    entry = Path(args.entry).resolve()
    root = Path(args.root).resolve() if args.root else entry.parent.resolve()

    if args.check:
        documents = validate_markdown_corpus(root)
        print(f"Validated {len(documents)} markdown documents under {root}")
        return 0

    output = Path(args.output).resolve()

    builder = MonolithBuilder(root=root)
    content = builder.build(entry)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")

    print(f"Wrote monolith markdown to {output}")
    print(f"Included {len(builder.order)} files from {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
