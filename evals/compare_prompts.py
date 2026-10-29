"""
Prompt A/B comparison.

Runs the same eval suite against two system prompts and diffs the pass rates by
category. This is the regression harness the whole project was motivated by: it
makes a prompt change's effect on behavior measurable instead of vibes-based.

A is the agent's current system prompt (agent.py); B is a prompt file. The
bundled default B (prompts/ask_permission_variant.txt) deliberately reintroduces
the "ask the customer before acting" behavior, so you can see the proactiveness
and happy-path refund categories collapse under it — a concrete demonstration of
the eval catching a prompt regression.

Usage:
    python evals/compare_prompts.py
    python evals/compare_prompts.py --variant evals/prompts/ask_permission_variant.txt --runs 2
    python evals/compare_prompts.py --category proactiveness

Both arms hit the real agent API; cost scales with cases x runs x 2.
"""
import argparse
import os
import sys

import run_evals as R

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VARIANT = os.path.join(EVAL_DIR, "prompts", "ask_permission_variant.txt")


def _rates_by_category(summary):
    out = {}
    for cat, t in summary["cat_totals"].items():
        out[cat] = t["passed"] / t["total"] if t["total"] else 0.0
    return out


def main():
    parser = argparse.ArgumentParser(description="Compare two system prompts on the eval suite.")
    parser.add_argument("--variant", default=DEFAULT_VARIANT, help="Path to prompt B (default: ask-permission variant)")
    parser.add_argument("--case", help="Run a single case by id")
    parser.add_argument("--category", help="Run only cases in this category")
    parser.add_argument("--runs", type=int, default=1, help="Runs per case per arm (default 1)")
    args = parser.parse_args()

    R._require_keys()

    with open(args.variant, encoding="utf-8") as f:
        variant_prompt = f.read()

    cases = R.load_cases(args.case, args.category)
    if not cases:
        print("No cases matched the given filters.")
        sys.exit(2)

    print("Bootstrapping agent...\n")
    seed_fn, agent, state = R.bootstrap()
    baseline_prompt = agent.SYSTEM_PROMPT

    n = len(cases) * args.runs
    print(f"Comparing 2 prompts over {len(cases)} case(s) x {args.runs} run(s) = {2 * n} conversation(s)\n")

    print("Arm A: current prompt ...")
    a = R.run_suite(cases, args.runs, agent, state, seed_fn, system_prompt=baseline_prompt, verbose=False)
    print("Arm B: variant prompt ...")
    b = R.run_suite(cases, args.runs, agent, state, seed_fn, system_prompt=variant_prompt, verbose=False)

    agent.SYSTEM_PROMPT = baseline_prompt  # restore

    a_rates, b_rates = _rates_by_category(a), _rates_by_category(b)

    print("\n" + "=" * 60)
    print(f"  {'category':<22} {'A':>6} {'B':>6} {'Δ':>7}")
    print(f"  {'-' * 22} {'-' * 6} {'-' * 6} {'-' * 7}")
    for cat in sorted(set(a_rates) | set(b_rates)):
        ar, br = a_rates.get(cat, 0.0), b_rates.get(cat, 0.0)
        delta = br - ar
        flag = "  <-- regressed" if delta < -1e-9 else ""
        print(f"  {cat:<22} {ar:>5.0%} {br:>5.0%} {delta:>+6.0%}{flag}")
    print(f"  {'-' * 22} {'-' * 6} {'-' * 6} {'-' * 7}")
    print(f"  {'OVERALL':<22} {a['overall']:>5.0%} {b['overall']:>5.0%} {b['overall'] - a['overall']:>+6.0%}")
    print("=" * 60)
    print("\nA = current prompt (agent.py)   B =", os.path.relpath(args.variant))


if __name__ == "__main__":
    main()
