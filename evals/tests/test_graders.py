"""
Offline unit tests for the grading logic.

These run with no API calls and no network — they feed hand-built "run records"
(what the agent supposedly did) into the graders and assert the verdict. This is
the layer that CI gates on every push: if the grading harness regresses, these
fail fast and for free.

    python -m unittest discover -s evals/tests
"""
import os
import sqlite3
import sys
import tempfile
import unittest

# Make the eval package importable (graders.py lives one directory up).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import graders  # noqa: E402


def run(tool_calls=None, response=""):
    """Build a minimal run record like the runner produces."""
    return {"tool_calls": tool_calls or [], "response": response}


def exec_sql(path, *statements):
    """Run statements against a sqlite file, committing and closing the connection."""
    conn = sqlite3.connect(path)
    try:
        for s in statements:
            conn.execute(s)
        conn.commit()
    finally:
        conn.close()


class ToolCheckTests(unittest.TestCase):
    def test_expected_tools_present(self):
        calls = [{"name": "check_order_status", "input": {}},
                 {"name": "process_refund", "input": {}}]
        self.assertTrue(graders.check_expected_tools(calls, ["check_order_status", "process_refund"])["passed"])

    def test_expected_tools_missing(self):
        calls = [{"name": "check_order_status", "input": {}}]
        self.assertFalse(graders.check_expected_tools(calls, ["process_refund"])["passed"])

    def test_forbidden_tools(self):
        calls = [{"name": "process_refund", "input": {}}]
        self.assertFalse(graders.check_forbidden_tools(calls, ["process_refund"])["passed"])
        self.assertTrue(graders.check_forbidden_tools(calls, ["escalate_to_human"])["passed"])

    def test_order_as_subsequence(self):
        calls = [{"name": "check_order_status", "input": {}},
                 {"name": "search_knowledge_base", "input": {}},
                 {"name": "process_refund", "input": {}}]
        # correct relative order, extra call in between is fine
        self.assertTrue(graders.check_order(calls, ["check_order_status", "process_refund"])["passed"])

    def test_order_wrong(self):
        calls = [{"name": "process_refund", "input": {}},
                 {"name": "check_order_status", "input": {}}]
        self.assertFalse(graders.check_order(calls, ["check_order_status", "process_refund"])["passed"])


class ArgCheckTests(unittest.TestCase):
    def test_args_match_case_insensitive(self):
        calls = [{"name": "process_refund", "input": {"order_id": "ord-1001", "reason": "late"}}]
        self.assertTrue(
            graders.check_expected_args(calls, {"process_refund": {"order_id": "ORD-1001"}})["passed"]
        )

    def test_args_mismatch(self):
        calls = [{"name": "process_refund", "input": {"order_id": "ORD-9999"}}]
        self.assertFalse(
            graders.check_expected_args(calls, {"process_refund": {"order_id": "ORD-1001"}})["passed"]
        )

    def test_args_tool_never_called(self):
        self.assertFalse(
            graders.check_expected_args([], {"process_refund": {"order_id": "ORD-1001"}})["passed"]
        )


class ResponseCheckTests(unittest.TestCase):
    def test_contains_case_insensitive(self):
        self.assertTrue(graders.check_contains("Your REFUND is on the way", ["refund"])["passed"])
        self.assertFalse(graders.check_contains("no match here", ["refund"])["passed"])

    def test_not_contains(self):
        self.assertFalse(
            graders.check_not_contains("Would you like me to check?", ["would you like me to"])["passed"]
        )
        self.assertTrue(graders.check_not_contains("I've checked it.", ["would you like me to"])["passed"])


class DbAssertionTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        exec_sql(
            self.db_path,
            "CREATE TABLE orders (id TEXT PRIMARY KEY, status TEXT)",
            "CREATE TABLE escalations (id INTEGER PRIMARY KEY, ticket_id TEXT)",
            "INSERT INTO orders VALUES ('ORD-1001', 'refunded')",
            "INSERT INTO orders VALUES ('ORD-1003', 'processing')",
        )

    def tearDown(self):
        os.remove(self.db_path)

    def test_order_status_equals(self):
        a = [{"type": "order_status", "order_id": "ORD-1001", "equals": "refunded"}]
        self.assertTrue(graders.check_db_assertions(self.db_path, a)["passed"])

    def test_order_status_not_equals(self):
        a = [{"type": "order_status", "order_id": "ORD-1003", "not_equals": "refunded"}]
        self.assertTrue(graders.check_db_assertions(self.db_path, a)["passed"])

    def test_order_status_equals_fails(self):
        a = [{"type": "order_status", "order_id": "ORD-1003", "equals": "refunded"}]
        self.assertFalse(graders.check_db_assertions(self.db_path, a)["passed"])

    def test_escalation_created_false(self):
        a = [{"type": "escalation_created", "expected": False}]
        self.assertTrue(graders.check_db_assertions(self.db_path, a)["passed"])

    def test_escalation_created_true(self):
        exec_sql(self.db_path, "INSERT INTO escalations (ticket_id) VALUES ('TKT-1')")
        a = [{"type": "escalation_created", "expected": True}]
        self.assertTrue(graders.check_db_assertions(self.db_path, a)["passed"])


class GradeRunTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        exec_sql(
            self.db_path,
            "CREATE TABLE orders (id TEXT PRIMARY KEY, status TEXT)",
            "CREATE TABLE escalations (id INTEGER PRIMARY KEY, ticket_id TEXT)",
            "INSERT INTO orders VALUES ('ORD-1001', 'refunded')",
        )

    def tearDown(self):
        os.remove(self.db_path)

    def test_full_pass(self):
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
        grade = graders.grade_run(case, r, self.db_path)
        self.assertTrue(grade["passed"], graders.failed_reasons(grade))

    def test_fails_on_forbidden_tool(self):
        case = {"forbidden_tools": ["process_refund"]}
        r = run(tool_calls=[{"name": "process_refund", "input": {}}])
        self.assertFalse(graders.grade_run(case, r, self.db_path)["passed"])


if __name__ == "__main__":
    unittest.main()
