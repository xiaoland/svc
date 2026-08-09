from __future__ import annotations

import hashlib

import pytest

from svc_cli.catalog import Catalog, CatalogEntry, CorpusMigration, CorpusRelease
from svc_cli.errors import SvcError
from svc_cli.lookup import CorpusLookup, LookupQuery


def fixture_lookup() -> CorpusLookup:
    documents = {
        "index.md": b"# Sustainable Vibe Coding\n\nSource-first framework.\n",
        "assets/templates/AGENTS.local.template.md": (
            b"# Local Instructions\n\nA task packet local template.\n"
        ),
        "sections/extensions/alignment.md": (
            b"# Alignment\n\nKeep one mutation gate.\n"
        ),
        "sections/implementation-taste.md": (
            b"# Implementation Taste\n\nUse measured design judgment.\n"
        ),
        "sections/working-protocol.md": (
            b"# Working Protocol\n\nUse a task packet and mutation gate.\n"
        ),
    }
    entries = tuple(
        CatalogEntry(
            path,
            content.decode().splitlines()[0][2:],
            hashlib.sha256(content).hexdigest(),
        )
        for path, content in sorted(documents.items())
    )
    releases = (CorpusRelease("10.0.0", "9.0.0", CorpusMigration("not-required")),)
    return CorpusLookup(Catalog(2, "10.0.0", releases, entries), documents.__getitem__)


def test_list_browses_one_logical_level_without_reading_documents() -> None:
    fixture = fixture_lookup()

    def fail_reader(path: str) -> bytes:
        pytest.fail(f"list unexpectedly read {path}")

    lookup = CorpusLookup(fixture.catalog, fail_reader)
    root = lookup.lookup(LookupQuery("list"))
    nested = lookup.lookup(LookupQuery("list", "sections/"))

    assert root.as_dict() == {
        "schema_version": 2,
        "command": "lookup",
        "corpus_version": "10.0.0",
        "mode": "list",
        "prefix": None,
        "entries": [
            {"kind": "directory", "path": "assets/", "document_count": 1},
            {
                "kind": "document",
                "path": "index.md",
                "title": "Sustainable Vibe Coding",
                "sha256": fixture.catalog.entries[1].sha256,
            },
            {"kind": "directory", "path": "sections/", "document_count": 3},
        ],
    }
    assert [entry.path for entry in nested.entries] == [
        "sections/extensions/",
        "sections/implementation-taste.md",
        "sections/working-protocol.md",
    ]
    assert nested.prefix == "sections/"


def test_missing_or_invalid_directory_is_an_exact_selection_failure() -> None:
    with pytest.raises(SvcError) as missing:
        fixture_lookup().lookup(LookupQuery("list", "missing/"))
    assert missing.value.code == "lookup-directory-not-found"

    with pytest.raises(SvcError) as invalid:
        fixture_lookup().lookup(LookupQuery("list", "../sections"))
    assert invalid.value.code == "invalid-directory-prefix"


def test_path_reads_one_exact_normalized_document() -> None:
    response = fixture_lookup().lookup(
        LookupQuery("path", "sections/working-protocol.md")
    )

    assert response.document is not None
    assert response.document.entry.path == "sections/working-protocol.md"
    assert "mutation gate" in response.document.content
    assert response.as_dict()["document"]["content"].startswith("# Working Protocol")


@pytest.mark.parametrize(
    "path",
    (
        "",
        "../working-protocol.md",
        "/sections/working-protocol.md",
        "sections/working-protocol",
        r"sections\working-protocol.md",
    ),
)
def test_path_rejects_non_normalized_non_markdown_identity(path: str) -> None:
    with pytest.raises(SvcError) as raised:
        fixture_lookup().lookup(LookupQuery("path", path))

    assert raised.value.code == "invalid-document-path"


def test_keyword_is_ranked_without_public_score_and_obeys_scope() -> None:
    lookup = fixture_lookup()
    both = lookup.lookup(
        LookupQuery("keyword", "task packet mutation gate", "both", 10)
    )
    path_only = lookup.lookup(LookupQuery("keyword", "working protocol", "path", 10))

    assert both.candidates[0].entry.path == "sections/working-protocol.md"
    assert both.candidates[0].matched_in == ("content",)
    assert both.candidates[0].excerpt is not None
    encoded = both.as_dict()["candidates"][0]
    assert "score" not in encoded
    assert path_only.candidates[0].matched_in == ("path",)
    assert path_only.candidates[0].excerpt is None


def test_regex_returns_stable_path_and_one_based_content_locations() -> None:
    response = fixture_lookup().lookup(
        LookupQuery("regex", r"mutation gate|working-protocol", "both", 10)
    )

    assert [(item.entry.path, item.surface) for item in response.matches] == [
        ("sections/extensions/alignment.md", "content"),
        ("sections/working-protocol.md", "path"),
        ("sections/working-protocol.md", "content"),
    ]
    content = response.matches[0]
    assert (content.line, content.column) == (3, 10)
    assert "mutation gate" in (content.excerpt or "")
    assert response.as_dict()["matches"][1] == {
        "path": "sections/working-protocol.md",
        "sha256": response.matches[1].entry.sha256,
        "surface": "path",
    }


def test_regex_limit_is_flat_and_reports_truncation() -> None:
    response = fixture_lookup().lookup(
        LookupQuery("regex", r"(?i)task|mutation", "both", 1)
    )

    assert len(response.matches) == 1
    assert response.truncated


def test_invalid_regex_is_an_explicit_usage_failure() -> None:
    with pytest.raises(SvcError) as raised:
        fixture_lookup().lookup(LookupQuery("regex", "["))
    assert raised.value.code == "invalid-lookup-regex"


@pytest.mark.parametrize("mode", ("keyword", "regex"))
def test_empty_search_is_a_settled_result(mode: str) -> None:
    response = fixture_lookup().lookup(
        LookupQuery(mode, "dev server readiness", "both", 10)
    )

    assert response.candidates == ()
    assert response.matches == ()
    assert not response.truncated


def test_tampered_corpus_is_an_explicit_integrity_failure() -> None:
    bad = CorpusLookup(
        Catalog(
            2,
            "10.0.0",
            (CorpusRelease("10.0.0", "9.0.0", CorpusMigration("not-required")),),
            (CatalogEntry("sections/example.md", "Example", "0" * 64),),
        ),
        lambda _: b"# Example\n",
    )
    with pytest.raises(SvcError, match="digest"):
        bad.lookup(LookupQuery("regex", "Example", "both"))
