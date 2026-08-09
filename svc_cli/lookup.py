"""Browse, search, and read the packaged SVC Corpus."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Annotated, Callable, Literal, Sequence, TypeAlias, cast

from pydantic import Field

from .catalog import Catalog, CatalogEntry, normalized_document_path, sha256_bytes
from .errors import SvcError
from .machine import MachineModel
from .resources import read_document


TOKEN_RE = re.compile(r"\w+", re.UNICODE)
LIST_GUIDANCE_COMMAND = "svc lookup --list"
READ_GUIDANCE_COMMAND = "svc lookup --path <path>"
LOOKUP_DISCOVERY_HINT = (
    "Use `svc lookup --help` to browse, search, or read the SVC Corpus."
)


@dataclass(frozen=True)
class LookupQuery:
    mode: Literal["list", "path", "keyword", "regex"]
    value: str | None = None
    scope: Literal["path", "both"] = "both"
    limit: int = 10

    def __post_init__(self) -> None:
        if self.mode not in {"list", "path", "keyword", "regex"}:
            raise ValueError(f"Unsupported lookup mode: {self.mode}")
        if self.mode == "path" and not isinstance(self.value, str):
            raise ValueError("Path lookup needs one document path")
        if self.mode in {"keyword", "regex"} and (
            not isinstance(self.value, str) or not self.value.strip()
        ):
            raise ValueError("Search query must not be empty")
        if self.scope not in {"path", "both"}:
            raise ValueError("Lookup scope must be path or both")
        if not 1 <= self.limit <= 50:
            raise ValueError("Lookup limit must be between 1 and 50")


class CorpusDocumentReference(MachineModel):
    path: str
    title: str
    sha256: str

    @classmethod
    def from_entry(cls, entry: CatalogEntry) -> "CorpusDocumentReference":
        return cls(path=entry.path, title=entry.title, sha256=entry.sha256)


class LookupDirectoryEntry(MachineModel):
    kind: Literal["directory"] = "directory"
    path: str
    document_count: int


class LookupDocumentEntry(CorpusDocumentReference):
    kind: Literal["document"] = "document"


LookupListEntry: TypeAlias = Annotated[
    LookupDirectoryEntry | LookupDocumentEntry, Field(discriminator="kind")
]


class LookupDocument(CorpusDocumentReference):
    content: str


class LookupKeywordCandidate(CorpusDocumentReference):
    matched_in: tuple[Literal["path", "content"], ...]
    excerpt: str | None = None


class LookupRegexMatch(MachineModel):
    machine_exclude_none = True

    path: str
    sha256: str
    surface: Literal["path", "content"]
    line: int | None = None
    column: int | None = None
    excerpt: str | None = None


class _LookupOutput(MachineModel):
    schema_version: Literal[2] = 2
    command: Literal["lookup"] = "lookup"
    corpus_version: str


class LookupListOutput(_LookupOutput):
    mode: Literal["list"] = "list"
    prefix: str | None
    entries: tuple[LookupListEntry, ...]


class LookupPathOutput(_LookupOutput):
    mode: Literal["path"] = "path"
    document: LookupDocument


class LookupKeywordOutput(_LookupOutput):
    machine_exclude_none = True

    mode: Literal["keyword"] = "keyword"
    query: str
    scope: Literal["path", "both"]
    limit: int
    truncated: bool
    candidates: tuple[LookupKeywordCandidate, ...]


class LookupRegexOutput(_LookupOutput):
    machine_exclude_none = True

    mode: Literal["regex"] = "regex"
    query: str
    scope: Literal["path", "both"]
    limit: int
    truncated: bool
    matches: tuple[LookupRegexMatch, ...]


LookupOutput: TypeAlias = Annotated[
    LookupListOutput | LookupPathOutput | LookupKeywordOutput | LookupRegexOutput,
    Field(discriminator="mode"),
]


@dataclass(frozen=True)
class CorpusDocument:
    entry: CatalogEntry
    content: str


@dataclass(frozen=True)
class ListEntry:
    kind: str
    path: str
    title: str | None = None
    sha256: str | None = None
    document_count: int | None = None


@dataclass(frozen=True)
class KeywordCandidate:
    entry: CatalogEntry
    matched_in: tuple[Literal["path", "content"], ...]
    excerpt: str | None
    score: int


@dataclass(frozen=True)
class RegexMatch:
    entry: CatalogEntry
    surface: str
    line: int | None = None
    column: int | None = None
    excerpt: str | None = None


@dataclass(frozen=True)
class LookupResponse:
    corpus_version: str
    query: LookupQuery
    entries: tuple[ListEntry, ...] = ()
    document: CorpusDocument | None = None
    candidates: tuple[KeywordCandidate, ...] = ()
    matches: tuple[RegexMatch, ...] = ()
    truncated: bool = False
    prefix: str | None = None

    def as_output(self) -> LookupOutput:
        if self.query.mode == "list":
            entries: list[LookupListEntry] = []
            for entry in self.entries:
                if entry.kind == "directory":
                    assert entry.document_count is not None
                    entries.append(
                        LookupDirectoryEntry(
                            path=entry.path,
                            document_count=entry.document_count,
                        )
                    )
                else:
                    assert entry.title is not None and entry.sha256 is not None
                    entries.append(
                        LookupDocumentEntry(
                            path=entry.path,
                            title=entry.title,
                            sha256=entry.sha256,
                        )
                    )
            return LookupListOutput(
                corpus_version=self.corpus_version,
                prefix=self.prefix,
                entries=tuple(entries),
            )
        if self.query.mode == "path":
            assert self.document is not None
            return LookupPathOutput(
                corpus_version=self.corpus_version,
                document=LookupDocument(
                    **CorpusDocumentReference.from_entry(
                        self.document.entry
                    ).model_dump(),
                    content=self.document.content,
                ),
            )
        assert self.query.value is not None
        assert self.query.scope in {"path", "both"}
        scope: Literal["path", "both"] = (
            "path" if self.query.scope == "path" else "both"
        )
        if self.query.mode == "keyword":
            return LookupKeywordOutput(
                corpus_version=self.corpus_version,
                query=self.query.value,
                scope=scope,
                limit=self.query.limit,
                truncated=self.truncated,
                candidates=tuple(
                    LookupKeywordCandidate(
                        **CorpusDocumentReference.from_entry(item.entry).model_dump(),
                        matched_in=item.matched_in,
                        excerpt=item.excerpt,
                    )
                    for item in self.candidates
                ),
            )
        return LookupRegexOutput(
            corpus_version=self.corpus_version,
            query=self.query.value,
            scope=scope,
            limit=self.query.limit,
            truncated=self.truncated,
            matches=tuple(
                LookupRegexMatch(
                    path=item.entry.path,
                    sha256=item.entry.sha256,
                    surface="path" if item.surface == "path" else "content",
                    line=item.line,
                    column=item.column,
                    excerpt=item.excerpt,
                )
                for item in self.matches
            ),
        )


class CorpusLookup:
    def __init__(
        self,
        catalog: Catalog,
        reader: Callable[[str], bytes] = read_document,
    ) -> None:
        self.catalog = catalog
        self.reader = reader

    def lookup(self, query: LookupQuery) -> LookupResponse:
        if query.mode == "list":
            return self._lookup_list(query)
        if query.mode == "path":
            return self._lookup_path(query)
        if query.mode == "keyword":
            return self._lookup_keyword(query)
        return self._lookup_regex(query)

    def _lookup_list(self, query: LookupQuery) -> LookupResponse:
        prefix = _normalize_prefix(query.value)
        matching = [
            entry
            for entry in self.catalog.entries
            if entry.path.startswith(prefix or "")
        ]
        if prefix is not None and not matching:
            raise SvcError(
                "lookup-directory-not-found",
                "No packaged SVC Corpus directory has that prefix.",
                {"prefix": prefix},
            )
        directories: dict[str, int] = {}
        documents: list[ListEntry] = []
        for entry in matching:
            relative = entry.path[len(prefix or "") :]
            head, separator, _ = relative.partition("/")
            if separator:
                directory = f"{prefix or ''}{head}/"
                directories[directory] = directories.get(directory, 0) + 1
            else:
                documents.append(
                    ListEntry("document", entry.path, entry.title, entry.sha256)
                )
        entries = [
            ListEntry("directory", path, document_count=count)
            for path, count in directories.items()
        ] + documents
        entries.sort(key=lambda item: item.path)
        return LookupResponse(
            self.catalog.corpus_version,
            query,
            entries=tuple(entries),
            prefix=prefix,
        )

    def _lookup_path(self, query: LookupQuery) -> LookupResponse:
        assert query.value is not None
        try:
            if "\\" in query.value:
                raise ValueError("--path must use normalized POSIX separators")
            path = normalized_document_path(query.value, "--path")
        except ValueError as error:
            raise SvcError(
                "invalid-document-path", str(error), {"path": query.value}
            ) from error
        entry = next((item for item in self.catalog.entries if item.path == path), None)
        if entry is None:
            raise SvcError(
                "lookup-not-found",
                "No packaged SVC document has that exact path.",
                {"path": query.value},
            )
        return LookupResponse(
            self.catalog.corpus_version,
            query,
            document=self._document(entry),
        )

    def _lookup_keyword(self, query: LookupQuery) -> LookupResponse:
        assert query.value is not None
        phrase = query.value.casefold().strip()
        terms = tuple(dict.fromkeys(TOKEN_RE.findall(phrase)))
        ranked: list[KeywordCandidate] = []
        for entry in self.catalog.entries:
            path = entry.path.casefold()
            path_matches = _lexical_match(path, phrase, terms)
            document = self._document(entry) if query.scope == "both" else None
            body = document.content.casefold() if document is not None else ""
            content_matches = _lexical_match(body, phrase, terms)
            if not path_matches and not content_matches:
                continue
            matched_in = cast(
                tuple[Literal["path", "content"], ...],
                tuple(
                    surface
                    for surface, matched in (
                        ("path", path_matches),
                        ("content", content_matches),
                    )
                    if matched
                ),
            )
            score = _keyword_score(path, body, phrase, terms)
            excerpt = (
                _excerpt(document.content, phrase, terms)
                if document is not None and content_matches
                else None
            )
            ranked.append(KeywordCandidate(entry, matched_in, excerpt, score))
        ranked.sort(key=lambda item: (-item.score, item.entry.path))
        truncated = len(ranked) > query.limit
        return LookupResponse(
            self.catalog.corpus_version,
            query,
            candidates=tuple(ranked[: query.limit]),
            truncated=truncated,
        )

    def _lookup_regex(self, query: LookupQuery) -> LookupResponse:
        assert query.value is not None
        try:
            pattern = re.compile(query.value)
        except re.error as error:
            raise SvcError(
                "invalid-lookup-regex",
                f"Invalid --regex expression: {error}",
                {"query": query.value},
            ) from error
        matches: list[RegexMatch] = []
        for entry in self.catalog.entries:
            if pattern.search(entry.path):
                matches.append(RegexMatch(entry, "path"))
            if query.scope == "both":
                document = self._document(entry)
                for found in pattern.finditer(document.content):
                    line, column, excerpt = _match_location(document.content, found)
                    matches.append(RegexMatch(entry, "content", line, column, excerpt))
        truncated = len(matches) > query.limit
        return LookupResponse(
            self.catalog.corpus_version,
            query,
            matches=tuple(matches[: query.limit]),
            truncated=truncated,
        )

    def _document(self, entry: CatalogEntry) -> CorpusDocument:
        content = self.reader(entry.path)
        actual = sha256_bytes(content)
        if actual != entry.sha256:
            raise SvcError(
                "invalid-corpus",
                "Packaged SVC document digest does not match its catalog entry.",
                {
                    "path": entry.path,
                    "expected_sha256": entry.sha256,
                    "actual_sha256": actual,
                },
            )
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise SvcError(
                "invalid-corpus",
                "Packaged SVC document is not UTF-8 Markdown.",
                {"path": entry.path},
            ) from error
        return CorpusDocument(entry, text)


def _normalize_prefix(value: str | None) -> str | None:
    if value in {None, ""}:
        return None
    assert value is not None
    if "\\" in value or value.startswith("/"):
        raise SvcError(
            "invalid-directory-prefix",
            "--list prefix must be a normalized relative Corpus directory.",
            {"prefix": value},
        )
    stripped = value.removesuffix("/")
    path = PurePosixPath(stripped)
    if (
        not stripped
        or "." in path.parts
        or ".." in path.parts
        or any(part.startswith(".") for part in path.parts)
        or path.as_posix() != stripped
    ):
        raise SvcError(
            "invalid-directory-prefix",
            "--list prefix must be a normalized relative Corpus directory.",
            {"prefix": value},
        )
    return f"{stripped}/"


def _lexical_match(text: str, phrase: str, terms: Sequence[str]) -> bool:
    return phrase in text or bool(terms and all(term in text for term in terms))


def _keyword_score(path: str, body: str, phrase: str, terms: Sequence[str]) -> int:
    return (
        path.count(phrase) * 1000
        + body.count(phrase) * 100
        + sum(path.count(term) * 120 + body.count(term) * 10 for term in terms)
    )


def _excerpt(content: str, phrase: str, terms: Sequence[str]) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    haystack = compact.casefold()
    needle = (
        phrase
        if phrase in haystack
        else next((term for term in terms if term in haystack), "")
    )
    start = max(haystack.find(needle), 0)
    left = max(start - 70, 0)
    right = min(start + max(len(needle), 1) + 120, len(compact))
    return (
        ("…" if left else "")
        + compact[left:right].strip()
        + ("…" if right < len(compact) else "")
    )


def _match_location(content: str, match: re.Match[str]) -> tuple[int, int, str]:
    start = match.start()
    line_start = content.rfind("\n", 0, start) + 1
    line_end = content.find("\n", start)
    if line_end == -1:
        line_end = len(content)
    line = content.count("\n", 0, start) + 1
    column = start - line_start + 1
    source_line = content[line_start:line_end]
    clip_left = max(column - 1 - 70, 0)
    clip_right = min(column - 1 + max(len(match.group()), 1) + 120, len(source_line))
    excerpt = (
        ("…" if clip_left else "")
        + source_line[clip_left:clip_right]
        + ("…" if clip_right < len(source_line) else "")
    )
    return line, column, excerpt
