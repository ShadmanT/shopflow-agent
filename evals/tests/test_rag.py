"""
Offline tests for the RAG retrieval eval (pytest).

rag_eval.grade_case is pure (operates on already-retrieved chunks), and
rag_cases.json integrity is checkable without embeddings or network.
"""
import json
import os

import pytest

import rag_eval

RAG_CASES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rag_cases.json")
VALID_SOURCES = {"returns_policy.md", "shipping_faq.md", "warranty.md"}

with open(RAG_CASES_PATH, encoding="utf-8") as f:
    RAG_CASES = json.load(f)


def test_hit_when_all_phrases_present():
    case = {"query": "q", "expect_contains": ["30 days"], "expect_source": "returns_policy.md"}
    retrieved = [{"content": "Items can be returned within 30 days of delivery.", "source": "returns_policy.md", "relevance": 0.8}]
    g = rag_eval.grade_case(case, retrieved)
    assert g["hit"] and g["source_ok"]


def test_miss_when_phrase_absent():
    case = {"query": "q", "expect_contains": ["30 days"], "expect_source": "returns_policy.md"}
    retrieved = [{"content": "Shipping takes 5-7 business days.", "source": "shipping_faq.md", "relevance": 0.5}]
    g = rag_eval.grade_case(case, retrieved)
    assert not g["hit"]
    assert g["missing"] == ["30 days"]
    assert not g["source_ok"]


def test_case_insensitive():
    case = {"query": "q", "expect_contains": ["6 Months"]}
    retrieved = [{"content": "Batteries are covered for 6 months only.", "source": "warranty.md", "relevance": 0.9}]
    assert rag_eval.grade_case(case, retrieved)["hit"]


def test_answer_from_wrong_source():
    case = {"query": "q", "expect_contains": ["24 hours"], "expect_source": "shipping_faq.md"}
    retrieved = [{"content": "wait 24 hours", "source": "returns_policy.md", "relevance": 0.6}]
    g = rag_eval.grade_case(case, retrieved)
    assert g["hit"] and not g["source_ok"]


def test_rag_cases_non_empty():
    assert isinstance(RAG_CASES, list) and len(RAG_CASES) > 0


@pytest.mark.parametrize("case", RAG_CASES, ids=[c["query"][:30] for c in RAG_CASES])
def test_rag_case_well_formed(case):
    assert case.get("query")
    assert isinstance(case["expect_contains"], list) and case["expect_contains"]
    if "expect_source" in case:
        assert case["expect_source"] in VALID_SOURCES
