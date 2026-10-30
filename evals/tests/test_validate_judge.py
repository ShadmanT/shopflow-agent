"""
Offline tests for the judge-validation agreement math and sample set (pytest).

summarize() and is_labeled() are pure; validate_judge imports judge lazily for
the API so importing it here needs no key or network.
"""
import json
import os

import pytest

import validate_judge as vj

SAMPLES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "judge_validation", "samples.json")

with open(SAMPLES_PATH, encoding="utf-8") as f:
    SAMPLES = json.load(f)

LABELED = [
    {"human": {"groundedness": 5, "tone": 5, "conciseness": 5},
     "judge": {"groundedness": 5, "tone": 4, "conciseness": 5}},
    {"human": {"groundedness": 2, "tone": 3, "conciseness": 4},
     "judge": {"groundedness": 3, "tone": 3, "conciseness": 5}},
]


def test_per_dimension_agreement():
    s = vj.summarize(LABELED, threshold=4)
    g = s["per_dim"]["groundedness"]
    assert g["exact"] == pytest.approx(0.5)
    assert g["within1"] == pytest.approx(1.0)
    assert g["mae"] == pytest.approx(0.5)
    assert g["n"] == 2


def test_pass_fail_agreement():
    # row1: human pass (min 5) & judge pass (min 4) -> match
    # row2: human fail (min 2) & judge fail (min 3) -> match
    assert vj.summarize(LABELED, threshold=4)["pass_agreement"] == pytest.approx(1.0)


def test_pass_fail_disagreement():
    labeled = [
        {"human": {"groundedness": 5, "tone": 5, "conciseness": 5},   # pass
         "judge": {"groundedness": 2, "tone": 5, "conciseness": 5}},  # fail
    ]
    assert vj.summarize(labeled, threshold=4)["pass_agreement"] == pytest.approx(0.0)


@pytest.mark.parametrize("human, expected", [
    ({"groundedness": 5, "tone": 4, "conciseness": 5}, True),
    ({"groundedness": None, "tone": 4, "conciseness": 5}, False),
    ({}, False),
])
def test_is_labeled(human, expected):
    assert vj.is_labeled({"human": human}) is expected


def test_is_labeled_missing_human_key():
    assert vj.is_labeled({}) is False


def test_samples_shape():
    assert len(SAMPLES) > 0
    ids = [s["id"] for s in SAMPLES]
    assert len(ids) == len(set(ids)), "duplicate sample ids"
    ids_joined = " ".join(ids)
    assert "good_" in ids_joined and "bad_" in ids_joined


@pytest.mark.parametrize("sample", SAMPLES, ids=[s["id"] for s in SAMPLES])
def test_sample_well_formed(sample):
    assert sample.get("messages")
    assert "response" in sample
    assert isinstance(sample.get("tool_calls"), list)
    human = sample.get("human", {})
    for d in vj.DIMENSIONS:
        assert d in human  # present; the shipped set is fully labeled (1-5)
        assert isinstance(human[d], int) and 1 <= human[d] <= 5
