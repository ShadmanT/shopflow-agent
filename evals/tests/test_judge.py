"""
Offline tests for the LLM-judge's pure logic.

No API calls — judge.parse_scores and build_prompt are deterministic. judge.py
imports the Anthropic client lazily (only inside _get_client), so importing the
module and testing the parser needs no key and no network.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import judge  # noqa: E402

VALID = """{
  "groundedness": {"score": 5, "reason": "all claims backed by tool results"},
  "tone": {"score": 4, "reason": "warm and professional"},
  "conciseness": {"score": 5, "reason": "tight"}
}"""


class ParseScoresTests(unittest.TestCase):
    def test_valid(self):
        scores = judge.parse_scores(VALID)
        self.assertEqual(set(scores), set(judge.DIMENSIONS))
        self.assertEqual(scores["groundedness"]["score"], 5)
        self.assertEqual(scores["tone"]["reason"], "warm and professional")

    def test_strips_code_fences(self):
        fenced = "```json\n" + VALID + "\n```"
        scores = judge.parse_scores(fenced)
        self.assertEqual(scores["conciseness"]["score"], 5)

    def test_extracts_json_amid_prose(self):
        noisy = "Here is my assessment:\n" + VALID + "\nThanks!"
        scores = judge.parse_scores(noisy)
        self.assertEqual(scores["tone"]["score"], 4)

    def test_bare_int_scores(self):
        scores = judge.parse_scores('{"groundedness": 3, "tone": 4, "conciseness": 5}')
        self.assertEqual(scores["groundedness"]["score"], 3)

    def test_missing_dimension_raises(self):
        with self.assertRaises(ValueError):
            judge.parse_scores('{"groundedness": {"score": 5}, "tone": {"score": 4}}')

    def test_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            judge.parse_scores('{"groundedness": {"score": 9}, "tone": {"score": 4}, "conciseness": {"score": 5}}')

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            judge.parse_scores("I cannot produce JSON.")


class BuildPromptTests(unittest.TestCase):
    def test_includes_response_and_tool_results(self):
        case = {"messages": [{"role": "user", "content": "refund ORD-1001"}]}
        run = {
            "response": "Your refund is processed.",
            "tool_calls": [
                {"name": "process_refund", "input": {"order_id": "ORD-1001"},
                 "result": {"success": True, "amount": 89.99}},
            ],
        }
        prompt = judge.build_prompt(case, run)
        self.assertIn("refund ORD-1001", prompt)
        self.assertIn("process_refund", prompt)
        self.assertIn("89.99", prompt)
        self.assertIn("Your refund is processed.", prompt)


if __name__ == "__main__":
    unittest.main()
