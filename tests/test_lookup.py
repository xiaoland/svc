from __future__ import annotations

import unittest

from svc_cli.catalog import Catalog, CatalogEntry
from svc_cli.errors import SvcError
from svc_cli.lookup import CorpusLookup, LookupQuery, RankedDocument


def fixture_lookup(ranker: object | None = None) -> CorpusLookup:
    documents = {
        "assets/templates/AGENTS.local.template.md": b"# Local Instructions\n\nA task packet local template.\n",
        "sections/implementation-taste.md": b"# Implementation Taste\n\nUse measured design judgment.\n",
        "sections/working-protocol.md": b"# Working Protocol\n\nUse a task packet and mutation gate.\n",
    }
    entries = tuple(
        CatalogEntry(path, content.decode().splitlines()[0][2:], __import__("hashlib").sha256(content).hexdigest())
        for path, content in sorted(documents.items())
    )
    return CorpusLookup(Catalog(1, "10.0.0", entries), documents.__getitem__, ranker)


class LookupTests(unittest.TestCase):
    def test_name_is_full_path_regex_and_ambiguity_requires_all(self) -> None:
        lookup = fixture_lookup()
        response = lookup.lookup(LookupQuery("name", r"sections/working-protocol\.md"))
        self.assertEqual([item.path for item in response.results], ["sections/working-protocol.md"])
        self.assertIn("mutation gate", response.results[0].content or "")

        with self.assertRaisesRegex(SvcError, "more than one path"):
            lookup.lookup(LookupQuery("name", r"sections/.*\.md"))
        many = lookup.lookup(LookupQuery("name", r"sections/.*\.md", allow_many=True))
        self.assertEqual(
            [item.path for item in many.results],
            ["sections/implementation-taste.md", "sections/working-protocol.md"],
        )

    def test_keyword_is_deterministic_and_returns_paths_not_copied_bodies(self) -> None:
        lookup = fixture_lookup()
        first = lookup.lookup(LookupQuery("keyword", "task packet mutation gate"))
        second = lookup.lookup(LookupQuery("keyword", "task packet mutation gate"))
        self.assertEqual(first.as_dict(), second.as_dict())
        result = first.results[0]
        self.assertEqual(result.path, "sections/working-protocol.md")
        self.assertIsNone(result.content)
        self.assertIsNotNone(result.excerpt)

    def test_query_result_boundary_accepts_an_independent_ranker(self) -> None:
        class FixedRanker:
            def rank(self, documents, query, limit):
                selected = next(document for document in documents if document.entry.path.endswith("implementation-taste.md"))
                return [RankedDocument(selected, 7, "fixed ranking")]

        response = fixture_lookup(FixedRanker()).lookup(LookupQuery("keyword", "anything"))
        self.assertEqual(response.results[0].path, "sections/implementation-taste.md")
        self.assertEqual(response.results[0].score, 7)
        self.assertEqual(response.results[0].excerpt, "fixed ranking")

    def test_invalid_regex_and_tampered_corpus_are_explicit_failures(self) -> None:
        lookup = fixture_lookup()
        with self.assertRaisesRegex(SvcError, "Invalid --name"):
            lookup.lookup(LookupQuery("name", "["))

        bad = CorpusLookup(
            Catalog(1, "10.0.0", (CatalogEntry("sections/example.md", "Example", "0" * 64),)),
            lambda _: b"# Example\n",
        )
        with self.assertRaisesRegex(SvcError, "digest"):
            bad.lookup(LookupQuery("name", r"sections/example\.md"))


if __name__ == "__main__":
    unittest.main()
