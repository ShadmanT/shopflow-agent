"""
Offline integrity tests for evals/cases.json (pytest).

Guards the case file itself: valid JSON, unique ids, real tool names, well-formed
messages, sane optional fields. Parametrized so each case is its own reported
test — a typo in one case points straight at that case.
"""
import json
import os

import pytest

CASES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cases.json")

VALID_TOOLS = {
    "check_order_status", "process_refund", "check_inventory",
    "get_product_info", "escalate_to_human", "search_knowledge_base",
}
VALID_ROLES = {"user", "assistant"}
VALID_DB_TYPES = {"order_status", "escalation_created"}

with open(CASES_PATH, encoding="utf-8") as f:
    CASES = json.load(f)


def test_is_non_empty_list():
    assert isinstance(CASES, list) and len(CASES) > 0


def test_unique_ids():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)), "duplicate case ids present"


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_well_formed(case):
    assert "id" in case and "category" in case and "messages" in case

    msgs = case["messages"]
    assert isinstance(msgs, list) and msgs, f"{case['id']} has no messages"
    assert msgs[0]["role"] == "user", f"{case['id']} must start with a user turn"
    for m in msgs:
        assert m["role"] in VALID_ROLES, f"{case['id']} bad role {m['role']}"
        assert isinstance(m["content"], str) and m["content"].strip()

    for key in ("expected_tools", "forbidden_tools"):
        for t in case.get(key, []):
            assert t in VALID_TOOLS, f"{case['id']} {key} unknown tool {t}"
    for t, args in case.get("expected_args", {}).items():
        assert t in VALID_TOOLS, f"{case['id']} expected_args unknown tool {t}"
        assert isinstance(args, dict), f"{case['id']} expected_args[{t}] not a dict"

    if "ordered" in case:
        assert isinstance(case["ordered"], bool)
    for key in ("response_must_contain", "response_must_not_contain"):
        if key in case:
            assert isinstance(case[key], list)

    for a in case.get("db_assertions", []):
        assert a.get("type") in VALID_DB_TYPES, f"{case['id']} bad db assertion type"
        if a["type"] == "order_status":
            assert "order_id" in a, f"{case['id']} order_status needs order_id"
            assert "equals" in a or "not_equals" in a, f"{case['id']} order_status needs equals/not_equals"
        else:
            assert isinstance(a.get("expected"), bool), f"{case['id']} escalation_created needs bool expected"
