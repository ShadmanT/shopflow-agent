"""
Validate the LLM judge against human labels.

An LLM judge is only trustworthy if it agrees with a human. This script runs
the judge over a curated set of responses (evals/judge_validation/samples.json,
a mix of good and deliberately-flawed answers) and compares its 1-5 scores with
human labels you fill in, reporting agreement per dimension.

Workflow:
  1. Open evals/judge_validation/samples.json and fill each sample's "human"
     scores (1-5 for groundedness, tone, conciseness) with YOUR judgement.
  2. Run this script. It judges every sample and, for the labeled ones, reports
     exact-match, within-1, and pass/fail agreement with your labels.

    python evals/validate_judge.py
    python evals/validate_judge.py --limit 3        # cost control while testing

Needs ANTHROPIC_API_KEY (the judge calls Claude). Informational — exits 0.
"""
import argparse
import json
import os
import sys

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(EVAL_DIR, "..", "backend")
SAMPLES_PATH = os.path.join(EVAL_DIR, "judge_validation", "samples.json")

sys.path.insert(0, EVAL_DIR)       # for judge.py
sys.path.insert(0, BACKEND_DIR)    # for the agent's env/client

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

import judge  # noqa: E402

DIMENSIONS = judge.DIMENSIONS


def _load_env():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
    load_dotenv(os.path.join(BACKEND_DIR, "..", ".env"))
    load_dotenv()


def is_labeled(sample) -> bool:
    h = sample.get("human") or {}
    return all(isinstance(h.get(d), int) for d in DIMENSIONS)


def summarize(labeled, threshold: int):
    """
    labeled: list of {"human": {dim: int}, "judge": {dim: int}}.
    Returns per-dimension agreement plus overall pass/fail agreement. Pure.
    """
    per_dim = {}
    for dim in DIMENSIONS:
        pairs = [(row["human"][dim], row["judge"][dim]) for row in labeled]
        n = len(pairs)
        exact = sum(1 for h, j in pairs if h == j) / n if n else 0.0
        within1 = sum(1 for h, j in pairs if abs(h - j) <= 1) / n if n else 0.0
        mae = sum(abs(h - j) for h, j in pairs) / n if n else 0.0
        per_dim[dim] = {"exact": exact, "within1": within1, "mae": mae, "n": n}

    pass_match = 0
    for row in labeled:
        human_pass = min(row["human"][d] for d in DIMENSIONS) >= threshold
        judge_pass = min(row["judge"][d] for d in DIMENSIONS) >= threshold
        pass_match += int(human_pass == judge_pass)
    pass_agreement = pass_match / len(labeled) if labeled else 0.0

    return {"per_dim": per_dim, "pass_agreement": pass_agreement, "n": len(labeled)}


def main():
    parser = argparse.ArgumentParser(description="Validate the LLM judge against human labels.")
    parser.add_argument("--limit", type=int, help="Only judge the first N samples (cost control)")
    parser.add_argument("--judge-threshold", type=int, default=4, help="Pass threshold per dimension (default 4)")
    args = parser.parse_args()

    _load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is required for the judge (never printed).")
        sys.exit(2)

    with open(SAMPLES_PATH, encoding="utf-8") as f:
        samples = json.load(f)
    if args.limit:
        samples = samples[:args.limit]

    print(f"Judging {len(samples)} sample(s)\n")
    print(f"  {'sample':<26} {'dimension':<13} {'judge':>5} {'human':>5}")
    print(f"  {'-'*26} {'-'*13} {'-'*5} {'-'*5}")

    labeled = []
    for s in samples:
        case = {"messages": s["messages"]}
        run = {"response": s["response"], "tool_calls": s["tool_calls"]}
        verdict = judge.judge_run(case, run, threshold=args.judge_threshold)
        if "error" in verdict:
            print(f"  {s['id']:<26} judge error: {verdict['error']}")
            continue
        jscores = {d: verdict["scores"][d]["score"] for d in DIMENSIONS}
        human = s.get("human") or {}
        for d in DIMENSIONS:
            hv = human.get(d)
            print(f"  {s['id']:<26} {d:<13} {jscores[d]:>5} {('-' if hv is None else hv):>5}")
        if is_labeled(s):
            labeled.append({"human": {d: human[d] for d in DIMENSIONS}, "judge": jscores})

    print()
    unlabeled = len(samples) - len(labeled)
    if not labeled:
        print(f"No human labels yet — fill the \"human\" scores in {os.path.relpath(SAMPLES_PATH)} "
              f"then re-run to see agreement. ({unlabeled} sample(s) unlabeled.)")
        return

    stats = summarize(labeled, args.judge_threshold)
    print(f"Agreement with human labels (n={stats['n']}; {unlabeled} unlabeled sample(s) skipped):\n")
    print(f"  {'dimension':<14} {'exact':>7} {'within-1':>9} {'MAE':>6}")
    print(f"  {'-'*14} {'-'*7} {'-'*9} {'-'*6}")
    for dim in DIMENSIONS:
        d = stats["per_dim"][dim]
        print(f"  {dim:<14} {d['exact']:>6.0%} {d['within1']:>8.0%} {d['mae']:>6.2f}")
    print(f"\nPass/fail agreement (threshold {args.judge_threshold}): {stats['pass_agreement']:.0%}")


if __name__ == "__main__":
    main()
