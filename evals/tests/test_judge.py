"""
Offline tests for the LLM-judge's pure logic (pytest).

judge.parse_scores and build_prompt are deterministic. judge.py imports the
Anthropic client lazily (only inside _get_client), so testing the parser needs
no key and no network.
"""
import pytest

import judge

VALID = """{
  "groundedness": {"score": 5, "reason": "all claims backed by tool results"},
  "tone": {"score": 4, "reason": "warm and professional"},
  "conciseness": {"score": 5, "reason": "tight"}
}"""


def test_parse_valid():
    scores = judge.parse_scores(VALID)
    assert set(scores) == set(judge.DIMENSIONS)
    assert scores["groundedness"]["score"] == 5
    assert scores["tone"]["reason"] == "warm and professional"


def test_parse_strips_code_fences():
    assert judge.parse_scores("```json\n" + VALID + "\n```")["conciseness"]["score"] == 5


def test_parse_extracts_json_amid_prose():
    assert judge.parse_scores("Here is my assessment:\n" + VALID + "\nThanks!")["tone"]["score"] == 4


def test_parse_bare_int_scores():
    scores = judge.parse_scores('{"groundedness": 3, "tone": 4, "conciseness": 5}')
    assert scores["groundedness"]["score"] == 3


@pytest.mark.parametrize("bad", [
    '{"groundedness": {"score": 5}, "tone": {"score": 4}}',                                  # missing dimension
    '{"groundedness": {"score": 9}, "tone": {"score": 4}, "conciseness": {"score": 5}}',     # out of range
    "I cannot produce JSON.",                                                                # no JSON
])
def test_parse_raises(bad):
    with pytest.raises(ValueError):
        judge.parse_scores(bad)


def test_build_prompt_includes_response_and_tool_results():
    case = {"messages": [{"role": "user", "content": "refund ORD-1001"}]}
    run = {
        "response": "Your refund is processed.",
        "tool_calls": [
            {"name": "process_refund", "input": {"order_id": "ORD-1001"},
             "result": {"success": True, "amount": 89.99}},
        ],
    }
    prompt = judge.build_prompt(case, run)
    assert "refund ORD-1001" in prompt
    assert "process_refund" in prompt
    assert "89.99" in prompt
    assert "Your refund is processed." in prompt
