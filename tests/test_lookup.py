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


def test_keyword_is_deterministic_and_returns_paths_not_copied_bodies() -> None:
    lookup = fixture_lookup()
    first = lookup.lookup(LookupQuery("keyword", "task packet mutation gate"))
    second = lookup.lookup(LookupQuery("keyword", "task packet mutation gate"))
    assert first.as_dict() == second.as_dict()
    result = first.results[0]
    assert result.path == "sections/working-protocol.md"
    assert result.content is None
    assert result.excerpt is not None


def test_invalid_regex_and_tampered_corpus_are_explicit_failures() -> None:
    lookup = fixture_lookup()
    with pytest.raises(SvcError, match="Invalid --name"):
        lookup.lookup(LookupQuery("name", "["))

    bad = CorpusLookup(
        Catalog(1, "10.0.0", (CatalogEntry("sections/example.md", "Example", "0" * 64),)),
        lambda _: b"# Example\n",
    )
    with pytest.raises(SvcError, match="digest"):
        bad.lookup(LookupQuery("name", r"sections/example\.md"))
