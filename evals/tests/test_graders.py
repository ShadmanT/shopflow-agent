"""
Offline unit tests for the grading logic (pytest).

No API calls — hand-built "run records" (what the agent supposedly did) go into
the graders and we assert the verdict. This is the layer CI gates on every push:
if the grading harness regresses, these fail fast and for free.

    pytest evals/tests
"""
import sqlite3

import pytest

import graders


def run(tool_calls=None, response=""):
    """Build a minimal run record like the runner produces."""
    return {"tool_calls": tool_calls or [], "response": response}


# ── Tool checks ───────────────────────────────────────────────────────────────

def test_expected_tools_present():
    calls = [{"name": "check_order_status", "input": {}},
             {"name": "process_refund", "input": {}}]
    assert graders.check_expected_tools(calls, ["check_order_status", "process_refund"])["passed"]


def test_expected_tools_missing():
    calls = [{"name": "check_order_status", "input": {}}]
    assert not graders.check_expected_tools(calls, ["process_refund"])["passed"]


@pytest.mark.parametrize("forbidden, expected", [
    (["process_refund"], False),
    (["escalate_to_human"], True),
])
def test_forbidden_tools(forbidden, expected):
    calls = [{"name": "process_refund", "input": {}}]
    assert graders.check_forbidden_tools(calls, forbidden)["passed"] is expected


def test_order_as_subsequence():
    calls = [{"name": "check_order_status", "input": {}},
             {"name": "search_knowledge_base", "input": {}},
             {"name": "process_refund", "input": {}}]
    assert graders.check_order(calls, ["check_order_status", "process_refund"])["passed"]


def test_order_wrong():
    calls = [{"name": "process_refund", "input": {}},
             {"name": "check_order_status", "input": {}}]
    assert not graders.check_order(calls, ["check_order_status", "process_refund"])["passed"]


# ── Argument checks ───────────────────────────────────────────────────────────

def test_args_match_case_insensitive():
    calls = [{"name": "process_refund", "input": {"order_id": "ord-1001", "reason": "late"}}]
    assert graders.check_expected_args(calls, {"process_refund": {"order_id": "ORD-1001"}})["passed"]


def test_args_mismatch():
    calls = [{"name": "process_refund", "input": {"order_id": "ORD-9999"}}]
    assert not graders.check_expected_args(calls, {"process_refund": {"order_id": "ORD-1001"}})["passed"]


def test_args_tool_never_called():
    assert not graders.check_expected_args([], {"process_refund": {"order_id": "ORD-1001"}})["passed"]


# ── Response string checks ────────────────────────────────────────────────────

def test_contains_case_insensitive():
    assert graders.check_contains("Your REFUND is on the way", ["refund"])["passed"]
    assert not graders.check_contains("no match here", ["refund"])["passed"]


def test_not_contains():
    assert not graders.check_not_contains("Would you like me to check?", ["would you like me to"])["passed"]
    assert graders.check_not_contains("I've checked it.", ["would you like me to"])["passed"]


# ── DB assertions ─────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    """A seeded eval DB on disk; pytest's tmp_path cleans it up."""
    p = tmp_path / "eval.db"
    conn = sqlite3.connect(p)
    conn.executescript(
        "CREATE TABLE orders (id TEXT PRIMARY KEY, status TEXT);"
        "CREATE TABLE escalations (id INTEGER PRIMARY KEY, ticket_id TEXT);"
        "INSERT INTO orders VALUES ('ORD-1001', 'refunded');"
        "INSERT INTO orders VALUES ('ORD-1003', 'processing');"
    )
    conn.commit()
    conn.close()
    return str(p)


def test_order_status_equals(db_path):
    a = [{"type": "order_status", "order_id": "ORD-1001", "equals": "refunded"}]
    assert graders.check_db_assertions(db_path, a)["passed"]


def test_order_status_not_equals(db_path):
    a = [{"type": "order_status", "order_id": "ORD-1003", "not_equals": "refunded"}]
    assert graders.check_db_assertions(db_path, a)["passed"]


def test_order_status_equals_fails(db_path):
    a = [{"type": "order_status", "order_id": "ORD-1003", "equals": "refunded"}]
    assert not graders.check_db_assertions(db_path, a)["passed"]


def test_escalation_created_false(db_path):
    assert graders.check_db_assertions(db_path, [{"type": "escalation_created", "expected": False}])["passed"]


def test_escalation_created_true(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO escalations (ticket_id) VALUES ('TKT-1')")
    conn.commit()
    conn.close()
    assert graders.check_db_assertions(db_path, [{"type": "escalation_created", "expected": True}])["passed"]


# ── Aggregate grade_run ───────────────────────────────────────────────────────

def test_grade_run_full_pass(db_path):
    case = {
        "expected_tools": ["check_order_status", "process_refund"],
        "forbidden_tools": ["escalate_to_human"],
        "ordered": True,
        "expected_args": {"process_refund": {"order_id": "ORD-1001"}},
        "response_must_not_contain": ["would you like me to"],
        "db_assertions": [{"type": "order_status", "order_id": "ORD-1001", "equals": "refunded"}],
    }
    r = run(
        tool_calls=[
            {"name": "check_order_status", "input": {"order_id": "ORD-1001"}},
            {"name": "process_refund", "input": {"order_id": "ORD-1001", "reason": "late"}},
        ],
        response="Done — your refund is processed.",
    )
    grade = graders.grade_run(case, r, db_path)
    assert grade["passed"], graders.failed_reasons(grade)


def test_grade_run_fails_on_forbidden_tool(db_path):
    case = {"forbidden_tools": ["process_refund"]}
    r = run(tool_calls=[{"name": "process_refund", "input": {}}])
    assert not graders.grade_run(case, r, db_path)["passed"]
