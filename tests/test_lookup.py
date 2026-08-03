from __future__ import annotations

import pytest

from svc_cli.catalog import Catalog, CatalogEntry
from svc_cli.errors import SvcError
from svc_cli.lookup import CorpusLookup, LookupQuery


def fixture_lookup() -> CorpusLookup:
    documents = {
        "assets/templates/AGENTS.local.template.md": b"# Local Instructions\n\nA task packet local template.\n",
        "sections/implementation-taste.md": b"# Implementation Taste\n\nUse measured design judgment.\n",
        "sections/working-protocol.md": b"# Working Protocol\n\nUse a task packet and mutation gate.\n",
    }
    entries = tuple(
        CatalogEntry(path, content.decode().splitlines()[0][2:], __import__("hashlib").sha256(content).hexdigest())
        for path, content in sorted(documents.items())
    )
    return CorpusLookup(Catalog(1, "10.0.0", entries), documents.__getitem__)


def test_name_is_full_path_regex_and_ambiguity_requires_all() -> None:
    lookup = fixture_lookup()
    response = lookup.lookup(LookupQuery("name", r"sections/working-protocol\.md"))
    assert [item.path for item in response.results] == ["sections/working-protocol.md"]
    assert "mutation gate" in (response.results[0].content or "")

    with pytest.raises(SvcError, match="more than one path"):
        lookup.lookup(LookupQuery("name", r"sections/.*\.md"))
    many = lookup.lookup(LookupQuery("name", r"sections/.*\.md", allow_many=True))
    assert [item.path for item in many.results] == [
        "sections/implementation-taste.md",
        "sections/working-protocol.md",
    ]


def test_list_is_catalog_only_path_sorted_and_has_no_query_or_body_fields() -> None:
    fixture = fixture_lookup()

    def fail_reader(path: str) -> bytes:
        pytest.fail(f"list unexpectedly read {path}")

    response = CorpusLookup(fixture.catalog, fail_reader).lookup(LookupQuery("list"))

    assert response.as_dict() == {
        "schema_version": 1,
        "command": "lookup",
        "mode": "list",
        "results": [entry.as_dict() for entry in fixture.catalog.entries],
    }


def test_path_reads_one_exact_normalized_document() -> None:
    lookup = fixture_lookup()
    response = lookup.lookup(
        LookupQuery("path", "sections/working-protocol.md")
    )

    assert response.as_dict()["query"] == "sections/working-protocol.md"
    assert [item.path for item in response.results] == [
        "sections/working-protocol.md"
    ]
    assert "mutation gate" in (response.results[0].content or "")


@pytest.mark.parametrize(
    "path",
    (
        "",
        "   ",
        "../working-protocol.md",
        "/sections/working-protocol.md",
        "sections/working-protocol",
        ".hidden.md",
        r"sections\working-protocol.md",
    ),
)
def test_path_rejects_non_normalized_non_markdown_identity(path: str) -> None:
    with pytest.raises(SvcError) as raised:
        fixture_lookup().lookup(LookupQuery("path", path))

    assert raised.value.code == "invalid-document-path"
    assert "--list" in raised.value.details["hint"]


def test_keyword_is_deterministic_and_returns_paths_not_copied_bodies() -> None:
    lookup = fixture_lookup()
    first = lookup.lookup(LookupQuery("keyword", "task packet mutation gate"))
    second = lookup.lookup(LookupQuery("keyword", "task packet mutation gate"))
    assert first.as_dict() == second.as_dict()
    result = first.results[0]
    assert result.path == "sections/working-protocol.md"
    assert result.content is None
    assert result.excerpt is not None


def test_invalid_name_regex_is_an_explicit_failure() -> None:
    lookup = fixture_lookup()
    with pytest.raises(SvcError, match="Invalid --name") as raised:
        lookup.lookup(LookupQuery("name", "["))
    assert "--path" in raised.value.details["hint"]


def test_tampered_corpus_is_an_explicit_integrity_failure() -> None:
    bad = CorpusLookup(
        Catalog(1, "10.0.0", (CatalogEntry("sections/example.md", "Example", "0" * 64),)),
        lambda _: b"# Example\n",
    )
    with pytest.raises(SvcError, match="digest"):
        bad.lookup(LookupQuery("name", r"sections/example\.md"))
