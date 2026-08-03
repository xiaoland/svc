"""Read-only lookup over the packaged SVC corpus."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

from .catalog import Catalog, CatalogEntry, normalized_document_path, sha256_bytes
from .errors import SvcError
from .resources import read_document


TOKEN_RE = re.compile(r"\w+", re.UNICODE)
LIST_GUIDANCE_COMMAND = "svc lookup --list --json"
READ_GUIDANCE_COMMAND = "svc lookup --path <path> --json"
LOOKUP_DISCOVERY_HINT = (
    f"Run `{LIST_GUIDANCE_COMMAND}`, choose a returned path, then run "
    f"`{READ_GUIDANCE_COMMAND}`."
)


@dataclass(frozen=True)
class LookupQuery:
    mode: str
    value: str | None = None
    allow_many: bool = False
    limit: int = 10

    def __post_init__(self) -> None:
        value = self.value
        if self.mode not in {"list", "path", "name", "keyword"}:
            raise ValueError(f"Unsupported lookup mode: {self.mode}")
        if self.mode == "list" and value is not None:
            raise ValueError("List lookup does not accept a value")
        if self.mode != "list" and not isinstance(value, str):
            raise ValueError("Lookup value must be a string")
        if self.mode in {"name", "keyword"} and (
            not isinstance(value, str) or not value.strip()
        ):
            raise ValueError("Lookup value must not be empty")
        if not 1 <= self.limit <= 50:
            raise ValueError("Lookup limit must be between 1 and 50")


@dataclass(frozen=True)
class CorpusDocument:
    entry: CatalogEntry
    content: str


@dataclass(frozen=True)
class RankedDocument:
    document: CorpusDocument
    score: int
    excerpt: str


class KeywordRanker(Protocol):
    def rank(
        self,
        documents: Sequence[CorpusDocument],
        query: str,
        limit: int,
    ) -> list[RankedDocument]: ...


@dataclass(frozen=True)
class LookupResult:
    path: str
    title: str
    sha256: str
    content: str | None = None
    score: int | None = None
    excerpt: str | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "path": self.path,
            "title": self.title,
            "sha256": self.sha256,
        }
        if self.content is not None:
            result["content"] = self.content
        if self.score is not None:
            result["score"] = self.score
        if self.excerpt is not None:
            result["excerpt"] = self.excerpt
        return result


@dataclass(frozen=True)
class LookupResponse:
    query: LookupQuery
    results: tuple[LookupResult, ...]

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": 1,
            "command": "lookup",
            "mode": self.query.mode,
            "results": [result.as_dict() for result in self.results],
        }
        if self.query.value is not None:
            payload["query"] = self.query.value
        return payload


class DeterministicKeywordRanker:
    """Small-corpus, transparent ranking that keeps semantic retrieval optional."""

    def rank(
        self,
        documents: Sequence[CorpusDocument],
        query: str,
        limit: int,
    ) -> list[RankedDocument]:
        phrase = query.casefold().strip()
        terms = tuple(dict.fromkeys(TOKEN_RE.findall(phrase)))
        ranked: list[RankedDocument] = []
        for document in documents:
            path = document.entry.path.casefold()
            title = document.entry.title.casefold()
            body = document.content.casefold()
            combined = f"{path}\n{title}\n{body}"
            phrase_hits = path.count(phrase) * 1000 + title.count(phrase) * 800 + body.count(phrase) * 100
            term_hits = sum(
                path.count(term) * 120 + title.count(term) * 80 + body.count(term) * 10
                for term in terms
            )
            if phrase_hits == 0 and (not terms or not all(term in combined for term in terms)):
                continue
            score = phrase_hits + term_hits
            ranked.append(RankedDocument(document, score, _excerpt(document.content, phrase, terms)))
        return sorted(ranked, key=lambda result: (-result.score, result.document.entry.path))[:limit]


class CorpusLookup:
    """Query/result boundary shared by current deterministic and future semantic rankers."""

    def __init__(
        self,
        catalog: Catalog,
        reader: Callable[[str], bytes] = read_document,
        ranker: KeywordRanker | None = None,
    ) -> None:
        self.catalog = catalog
        self.reader = reader
        self.ranker = ranker or DeterministicKeywordRanker()

    def lookup(self, query: LookupQuery) -> LookupResponse:
        if query.mode == "list":
            return self._lookup_list(query)
        if query.mode == "path":
            return self._lookup_path(query)
        if query.mode == "name":
            return self._lookup_name(query)
        return self._lookup_keyword(query)

    def _lookup_list(self, query: LookupQuery) -> LookupResponse:
        results = tuple(
            LookupResult(entry.path, entry.title, entry.sha256)
            for entry in self.catalog.entries
        )
        return LookupResponse(query, results)

    def _lookup_path(self, query: LookupQuery) -> LookupResponse:
        assert query.value is not None
        try:
            if "\\" in query.value:
                raise ValueError("--path must use normalized POSIX separators")
            path = normalized_document_path(query.value, "--path")
        except ValueError as error:
            raise SvcError(
                "invalid-document-path",
                str(error),
                {
                    "path": query.value,
                    "hint": LOOKUP_DISCOVERY_HINT,
                },
            ) from error
        entry = next(
            (item for item in self.catalog.entries if item.path == path),
            None,
        )
        if entry is None:
            raise SvcError(
                "lookup-not-found",
                "No packaged SVC document has that exact path.",
                {
                    "path": query.value,
                    "hint": LOOKUP_DISCOVERY_HINT,
                },
            )
        return LookupResponse(query, (self._full_result(entry),))

    def _lookup_name(self, query: LookupQuery) -> LookupResponse:
        assert query.value is not None
        try:
            pattern = re.compile(query.value)
        except re.error as error:
            raise SvcError(
                "invalid-name-regex",
                f"Invalid --name regular expression: {error}",
                {
                    "hint": (
                        "--name is a regular expression. For one path returned by "
                        f"--list, use `{READ_GUIDANCE_COMMAND}` instead."
                    )
                },
            ) from error
        matches = [entry for entry in self.catalog.entries if pattern.fullmatch(entry.path)]
        if not matches:
            raise SvcError(
                "lookup-not-found",
                "No packaged SVC path matched --name.",
                {
                    "pattern": query.value,
                    "hint": LOOKUP_DISCOVERY_HINT,
                },
            )
        if len(matches) > 1 and not query.allow_many:
            raise SvcError(
                "lookup-ambiguous",
                "--name matched more than one path; refine the regex or pass --all.",
                {
                    "paths": [entry.path for entry in matches],
                    "hint": (
                        "Use --all for every match or read one returned path with "
                        f"`{READ_GUIDANCE_COMMAND}`."
                    ),
                },
            )
        results = tuple(self._full_result(entry) for entry in matches)
        return LookupResponse(query, results)

    def _lookup_keyword(self, query: LookupQuery) -> LookupResponse:
        assert query.value is not None
        documents = tuple(self._document(entry) for entry in self.catalog.entries)
        results = tuple(
            LookupResult(
                path=ranked.document.entry.path,
                title=ranked.document.entry.title,
                sha256=ranked.document.entry.sha256,
                score=ranked.score,
                excerpt=ranked.excerpt,
            )
            for ranked in self.ranker.rank(documents, query.value, query.limit)
        )
        if not results:
            raise SvcError(
                "lookup-not-found",
                "No packaged SVC content matched --keyword.",
                {
                    "query": query.value,
                    "hint": LOOKUP_DISCOVERY_HINT,
                },
            )
        return LookupResponse(query, results)

    def _full_result(self, entry: CatalogEntry) -> LookupResult:
        document = self._document(entry)
        return LookupResult(entry.path, entry.title, entry.sha256, content=document.content)

    def _document(self, entry: CatalogEntry) -> CorpusDocument:
        content = self.reader(entry.path)
        actual = sha256_bytes(content)
        if actual != entry.sha256:
            raise SvcError(
                "invalid-corpus",
                "Packaged SVC document digest does not match its catalog entry.",
                {"path": entry.path, "expected_sha256": entry.sha256, "actual_sha256": actual},
            )
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise SvcError("invalid-corpus", "Packaged SVC document is not UTF-8 Markdown.", {"path": entry.path}) from error
        return CorpusDocument(entry, text)


def _excerpt(content: str, phrase: str, terms: Sequence[str]) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    haystack = compact.casefold()
    needle = phrase if phrase in haystack else next((term for term in terms if term in haystack), "")
    start = max(haystack.find(needle), 0)
    left = max(start - 70, 0)
    right = min(start + max(len(needle), 1) + 120, len(compact))
    prefix = "…" if left else ""
    suffix = "…" if right < len(compact) else ""
    return prefix + compact[left:right].strip() + suffix
