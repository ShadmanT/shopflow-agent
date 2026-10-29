"""
Offline tests for the judge-validation agreement math and sample set.

summarize() and is_labeled() are pure; validate_judge imports judge lazily for
the API so importing it here needs no key or network.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import validate_judge as vj  # noqa: E402

SAMPLES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "judge_validation", "samples.json")


class SummarizeTests(unittest.TestCase):
    def setUp(self):
        self.labeled = [
            {"human": {"groundedness": 5, "tone": 5, "conciseness": 5},
             "judge": {"groundedness": 5, "tone": 4, "conciseness": 5}},
            {"human": {"groundedness": 2, "tone": 3, "conciseness": 4},
             "judge": {"groundedness": 3, "tone": 3, "conciseness": 5}},
        ]

    def test_per_dimension_agreement(self):
        s = vj.summarize(self.labeled, threshold=4)
        g = s["per_dim"]["groundedness"]
        self.assertAlmostEqual(g["exact"], 0.5)
        self.assertAlmostEqual(g["within1"], 1.0)
        self.assertAlmostEqual(g["mae"], 0.5)
        self.assertEqual(g["n"], 2)

    def test_pass_fail_agreement(self):
        # row1: human pass (min 5) & judge pass (min 4) -> match
        # row2: human fail (min 2) & judge fail (min 3) -> match
        s = vj.summarize(self.labeled, threshold=4)
        self.assertAlmostEqual(s["pass_agreement"], 1.0)

    def test_pass_disagreement(self):
        labeled = [
            {"human": {"groundedness": 5, "tone": 5, "conciseness": 5},   # pass
             "judge": {"groundedness": 2, "tone": 5, "conciseness": 5}},  # fail
        ]
        s = vj.summarize(labeled, threshold=4)
        self.assertAlmostEqual(s["pass_agreement"], 0.0)


class IsLabeledTests(unittest.TestCase):
    def test_labeled(self):
        self.assertTrue(vj.is_labeled({"human": {"groundedness": 5, "tone": 4, "conciseness": 5}}))

    def test_unlabeled_null(self):
        self.assertFalse(vj.is_labeled({"human": {"groundedness": None, "tone": 4, "conciseness": 5}}))

    def test_unlabeled_missing(self):
        self.assertFalse(vj.is_labeled({"human": {}}))
        self.assertFalse(vj.is_labeled({}))


class SamplesFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SAMPLES_PATH, encoding="utf-8") as f:
            cls.samples = json.load(f)

    def test_shape(self):
        self.assertGreater(len(self.samples), 0)
        ids = [s["id"] for s in self.samples]
        self.assertEqual(len(ids), len(set(ids)), "duplicate sample ids")
        for s in self.samples:
            self.assertTrue(s.get("messages"))
            self.assertIn("response", s)
            self.assertIsInstance(s.get("tool_calls"), list)
            human = s.get("human", {})
            for d in vj.DIMENSIONS:
                self.assertIn(d, human)  # present (may be null until labeled)

    def test_includes_good_and_flawed(self):
        ids = " ".join(s["id"] for s in self.samples)
        self.assertIn("good_", ids)
        self.assertIn("bad_", ids)


if __name__ == "__main__":
    unittest.main()
