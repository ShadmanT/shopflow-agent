"""
Offline integrity tests for evals/cases.json.

No API calls — these guard the case file itself: valid JSON, unique ids, real
tool names, well-formed messages, and sane optional fields. If someone adds a
case with a typo in a tool name or a duplicate id, CI catches it for free.

    python -m unittest discover -s evals/tests
"""
import json
import os
import unittest

CASES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cases.json")

VALID_TOOLS = {
    "check_order_status",
    "process_refund",
    "check_inventory",
    "get_product_info",
    "escalate_to_human",
    "search_knowledge_base",
}
VALID_ROLES = {"user", "assistant"}
VALID_DB_TYPES = {"order_status", "escalation_created"}


class CasesFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CASES_PATH, encoding="utf-8") as f:
            cls.cases = json.load(f)

    def test_is_non_empty_list(self):
        self.assertIsInstance(self.cases, list)
        self.assertGreater(len(self.cases), 0)

    def test_unique_ids(self):
        ids = [c["id"] for c in self.cases]
        self.assertEqual(len(ids), len(set(ids)), "duplicate case ids present")

    def test_required_fields(self):
        for c in self.cases:
            self.assertIn("id", c)
            self.assertIn("category", c)
            self.assertIn("messages", c, f"{c.get('id')} missing messages")

    def test_messages_well_formed(self):
        for c in self.cases:
            msgs = c["messages"]
            self.assertIsInstance(msgs, list)
            self.assertGreater(len(msgs), 0, f"{c['id']} has no messages")
            self.assertEqual(msgs[0]["role"], "user", f"{c['id']} must start with a user turn")
            for m in msgs:
                self.assertIn(m["role"], VALID_ROLES, f"{c['id']} bad role {m['role']}")
                self.assertIsInstance(m["content"], str)
                self.assertTrue(m["content"].strip(), f"{c['id']} empty message content")

    def test_tool_names_valid(self):
        for c in self.cases:
            for key in ("expected_tools", "forbidden_tools"):
                for t in c.get(key, []):
                    self.assertIn(t, VALID_TOOLS, f"{c['id']} {key} unknown tool {t}")
            for t in c.get("expected_args", {}):
                self.assertIn(t, VALID_TOOLS, f"{c['id']} expected_args unknown tool {t}")

    def test_expected_args_shape(self):
        for c in self.cases:
            for tool, args in c.get("expected_args", {}).items():
                self.assertIsInstance(args, dict, f"{c['id']} expected_args[{tool}] not a dict")

    def test_ordered_is_bool(self):
        for c in self.cases:
            if "ordered" in c:
                self.assertIsInstance(c["ordered"], bool, f"{c['id']} ordered not a bool")

    def test_string_checks_are_lists(self):
        for c in self.cases:
            for key in ("response_must_contain", "response_must_not_contain"):
                if key in c:
                    self.assertIsInstance(c[key], list, f"{c['id']} {key} not a list")

    def test_db_assertions_well_formed(self):
        for c in self.cases:
            for a in c.get("db_assertions", []):
                self.assertIn(a.get("type"), VALID_DB_TYPES, f"{c['id']} bad db assertion type")
                if a["type"] == "order_status":
                    self.assertIn("order_id", a, f"{c['id']} order_status needs order_id")
                    self.assertTrue(
                        "equals" in a or "not_equals" in a,
                        f"{c['id']} order_status needs equals or not_equals",
                    )
                elif a["type"] == "escalation_created":
                    self.assertIsInstance(a.get("expected"), bool, f"{c['id']} escalation_created needs bool expected")


if __name__ == "__main__":
    unittest.main()
