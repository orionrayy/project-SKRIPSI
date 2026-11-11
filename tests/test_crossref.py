from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from project_skripsi.integrations.crossref import normalize_doi, verify_doi


class CrossrefTests(unittest.TestCase):
    def test_normalizes_doi_url_and_prefix(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1234/ABC.1"), "10.1234/ABC.1")
        self.assertEqual(normalize_doi("doi: 10.1234/ABC.1"), "10.1234/ABC.1")

    def test_rejects_non_doi(self):
        with self.assertRaises(ValueError):
            normalize_doi("https://example.org/paper")

    def test_retrieves_and_compares_metadata_without_transmitting_manuscript(self):
        payload = {
            "status": "ok",
            "message": {
                "DOI": "10.1234/demo",
                "title": ["An Example Study"],
                "author": [{"given": "Ayu", "family": "Sari"}],
                "container-title": ["Journal of Examples"],
                "published": {"date-parts": [[2024, 5, 1]]},
                "URL": "https://doi.org/10.1234/demo",
                "abstract": "This copyrighted abstract must not be cached.",
            },
        }
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("project_skripsi.integrations.crossref.build_opener") as opener:
                opener.return_value.open.return_value = response
                result = verify_doi(
                    "10.1234/demo",
                    expected={"title": "An Example Study", "year": 2024, "authors": ["Ayu Sari"]},
                    cache_dir=Path(tmp),
                )
            self.assertEqual(result["status"], "METADATA_RETRIEVED_REVIEW_REQUIRED")
            self.assertTrue(all(item["match"] for item in result["comparisons"]))
            self.assertEqual(len(list(Path(tmp).glob("*.json"))), 1)
            cache_file = next(Path(tmp).glob("*.json"))
            self.assertNotIn("abstract", cache_file.read_text(encoding="utf-8").casefold())
            self.assertEqual(cache_file.stat().st_mode & 0o777, 0o600)

    def test_uses_fresh_cache_without_network(self):
        payload = {
            "DOI": "10.1234/cache", "title": ["Cached title"], "author": [],
            "container-title": [], "published": {"date-parts": [[2023]]}
        }
        with tempfile.TemporaryDirectory() as tmp:
            from project_skripsi.integrations.crossref import _cache_file
            from hashlib import sha256
            cache = _cache_file(Path(tmp), "10.1234/cache")
            cache.write_text(json.dumps({"doi": "10.1234/cache", "cached_epoch": __import__("time").time(), "message": payload}))
            with patch("project_skripsi.integrations.crossref.build_opener") as opener:
                result = verify_doi("10.1234/cache", cache_dir=Path(tmp))
            opener.assert_not_called()
            self.assertTrue(result["cache_hit"])

    def test_mismatch_is_reported_without_auto_correction(self):
        payload = {"status": "ok", "message": {"DOI": "10.1234/demo", "title": ["Different title"], "author": [], "container-title": []}}
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        with patch("project_skripsi.integrations.crossref.build_opener") as opener:
            opener.return_value.open.return_value = response
            result = verify_doi("10.1234/demo", expected={"title": "Expected title"})
        self.assertEqual(result["status"], "METADATA_MISMATCH_REVIEW_REQUIRED")
        self.assertIn("bibliographic metadata only", " ".join(result["flags"]))


if __name__ == "__main__":
    unittest.main()
