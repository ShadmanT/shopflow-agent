"""
Offline tests for the RAG retrieval eval.

rag_eval.grade_case is pure (operates on already-retrieved chunks), and
rag_cases.json integrity is checkable without embeddings or network.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rag_eval  # noqa: E402

RAG_CASES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rag_cases.json")
VALID_SOURCES = {"returns_policy.md", "shipping_faq.md", "warranty.md"}


class GradeCaseTests(unittest.TestCase):
    def test_hit_when_all_phrases_present(self):
        case = {"query": "q", "expect_contains": ["30 days"], "expect_source": "returns_policy.md"}
        retrieved = [{"content": "Items can be returned within 30 days of delivery.", "source": "returns_policy.md", "relevance": 0.8}]
        g = rag_eval.grade_case(case, retrieved)
        self.assertTrue(g["hit"])
        self.assertTrue(g["source_ok"])

    def test_miss_when_phrase_absent(self):
        case = {"query": "q", "expect_contains": ["30 days"], "expect_source": "returns_policy.md"}
        retrieved = [{"content": "Shipping takes 5-7 business days.", "source": "shipping_faq.md", "relevance": 0.5}]
        g = rag_eval.grade_case(case, retrieved)
        self.assertFalse(g["hit"])
        self.assertEqual(g["missing"], ["30 days"])
        self.assertFalse(g["source_ok"])

    def test_case_insensitive(self):
        case = {"query": "q", "expect_contains": ["6 Months"]}
        retrieved = [{"content": "Batteries are covered for 6 months only.", "source": "warranty.md", "relevance": 0.9}]
        self.assertTrue(rag_eval.grade_case(case, retrieved)["hit"])

    def test_answer_from_wrong_source(self):
        case = {"query": "q", "expect_contains": ["24 hours"], "expect_source": "shipping_faq.md"}
        retrieved = [{"content": "wait 24 hours", "source": "returns_policy.md", "relevance": 0.6}]
        g = rag_eval.grade_case(case, retrieved)
        self.assertTrue(g["hit"])
        self.assertFalse(g["source_ok"])


class RagCasesFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(RAG_CASES_PATH, encoding="utf-8") as f:
            cls.cases = json.load(f)

    def test_non_empty_list(self):
        self.assertIsInstance(self.cases, list)
        self.assertGreater(len(self.cases), 0)

    def test_fields_well_formed(self):
        for c in self.cases:
            self.assertTrue(c.get("query"))
            self.assertIsInstance(c["expect_contains"], list)
            self.assertGreater(len(c["expect_contains"]), 0)
            if "expect_source" in c:
                self.assertIn(c["expect_source"], VALID_SOURCES)


if __name__ == "__main__":
    unittest.main()
