"""
ShopFlow Agent eval runner.

Runs scripted conversations through the *real* agent (`run_agent`, no HTTP)
and grades the behavior, producing a per-case and overall pass rate.

Usage (PowerShell on Windows works as-is):

    python evals/run_evals.py
    python evals/run_evals.py --case refund_happy_path_1001
    python evals/run_evals.py --category escalation --runs 3
    python evals/run_evals.py --runs 3 --threshold 0.9
    python evals/run_evals.py --judge                 # add LLM-as-judge scoring

Behavior:
  * Resets a dedicated eval DB with seed() before every run, so cases are
    independent and your dev shopflow.db is never touched.
  * Captures tool names, arguments AND results by wrapping the agent's tool
    executor, plus token usage by wrapping the Anthropic client.
  * With --judge, an LLM grades each response for groundedness, tone, and
    conciseness (extra API calls — opt-in). See evals/judge.py.
  * Saves full results (inputs, tool calls, args, results, response, grades,
    judge scores, latency, tokens) to evals/results/<timestamp>.json.
  * Exits non-zero if the overall pass rate is below --threshold (for CI).

API keys are loaded from .env by the agent module. They are never printed.
"""
import argparse
import contextlib
import copy
import io
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

# Force UTF-8 stdout/stderr so the suite works on Windows even when output is
# redirected to a file (imported modules print characters like "✓", which the
# default cp1252 codec can't encode).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(EVAL_DIR, "..", "backend")
RESULTS_DIR = os.path.join(EVAL_DIR, "results")
CASES_PATH = os.path.join(EVAL_DIR, "cases.json")
EVAL_DB_PATH = os.path.join(EVAL_DIR, "shopflow_eval.db")

sys.path.insert(0, BACKEND_DIR)


def _require_keys() -> None:
    missing = [k for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY") if not os.environ.get(k)]
    # .env is loaded when the agent module is imported; load it early too so we
    # can fail fast with a friendly message instead of a stack trace.
    if missing:
        try:
            from dotenv import load_dotenv
            # The project keeps its keys in backend/.env (see README); also try
            # a repo-root .env and the current working directory.
            load_dotenv(os.path.join(BACKEND_DIR, ".env"))
            load_dotenv(os.path.join(BACKEND_DIR, "..", ".env"))
            load_dotenv()
        except Exception:
            pass
        missing = [k for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY") if not os.environ.get(k)]
    if missing:
        print(f"ERROR: missing required environment variable(s): {', '.join(missing)}")
        print("Set them in a .env file at the project root (keys are never printed).")
        sys.exit(2)


def bootstrap():
    """
    Point the DB at a dedicated eval file, then import seed + agent and
    install instrumentation. Returns (seed_fn, agent_module, state) where
    `state` holds the live tool-call list and token counters.
    """
    import database
    database.DB_PATH = EVAL_DB_PATH  # read at call time by get_db(); safe to repoint

    from seed import seed
    import agent  # importing triggers build_knowledge_base() once

    state = {"tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}}

    # Wrap the tool executor to capture names, arguments AND results. The result
    # is what the agent saw, so the judge can check groundedness against it.
    _real_execute = agent.execute_tool

    def _recording_execute(name, inputs):
        result = _real_execute(name, inputs)
        state["tool_calls"].append({"name": name, "input": inputs, "result": result})
        return result

    agent.execute_tool = _recording_execute

    # Wrap the Anthropic client to accumulate token usage.
    _real_create = agent.client.messages.create

    def _recording_create(*args, **kwargs):
        resp = _real_create(*args, **kwargs)
        try:
            state["usage"]["input_tokens"] += resp.usage.input_tokens
            state["usage"]["output_tokens"] += resp.usage.output_tokens
        except Exception:
            pass
        return resp

    agent.client.messages.create = _recording_create

    return seed, agent, state


def _quiet_seed(seed_fn) -> None:
    """Reset the eval DB without the noisy seed() printout."""
    with contextlib.redirect_stdout(io.StringIO()):
        seed_fn()


def load_cases(case_id=None, category=None):
    with open(CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)
    if case_id:
        cases = [c for c in cases if c["id"] == case_id]
    if category:
        cases = [c for c in cases if c["category"] == category]
    return cases


def run_one(agent, state, seed_fn, case):
    """Reset DB, run the agent once, return a run record with grade inputs."""
    _quiet_seed(seed_fn)
    state["tool_calls"] = []
    state["usage"] = {"input_tokens": 0, "output_tokens": 0}

    messages = copy.deepcopy(case["messages"])
    t0 = time.perf_counter()
    try:
        result = agent.run_agent(messages)
        response = result.get("response", "")
        error = None
    except Exception as e:  # keep the suite running even if one case blows up
        response = ""
        error = f"{type(e).__name__}: {e}"
    latency = round(time.perf_counter() - t0, 3)

    return {
        "tool_calls": list(state["tool_calls"]),
        "response": response,
        "error": error,
        "latency_s": latency,
        "tokens": dict(state["usage"]),
    }


def run_suite(cases, runs, agent, state, seed_fn, *, judge=False, judge_threshold=4,
              system_prompt=None, verbose=True):
    """
    Run every case `runs` times, grade each run, optionally judge it, and return
    a summary dict. Shared by the CLI and the prompt A/B comparison script.
    """
    import graders
    judgemod = None
    if judge:
        import judge as judgemod

    if system_prompt is not None:
        agent.SYSTEM_PROMPT = system_prompt

    results = []
    cat_totals = defaultdict(lambda: {"passed": 0, "total": 0})
    judge_scores = defaultdict(list)  # dimension -> [scores]
    total_passed = total_runs = 0

    for case in cases:
        run_records = []
        case_passed = 0

        for _ in range(runs):
            run = run_one(agent, state, seed_fn, case)
            grade = graders.grade_run(case, run, EVAL_DB_PATH)
            run["grade"] = grade
            det_pass = grade["passed"] and run["error"] is None

            judge_pass = True
            if judge and run["error"] is None:
                verdict = judgemod.judge_run(case, run, threshold=judge_threshold)
                run["judge"] = verdict
                # A judge infrastructure error (parse/API) does not fail the run.
                if verdict.get("passed") is False:
                    judge_pass = False
                for dim, sc in verdict.get("scores", {}).items():
                    judge_scores[dim].append(sc["score"])

            passed = det_pass and judge_pass
            case_passed += int(passed)
            total_passed += int(passed)
            total_runs += 1
            cat_totals[case["category"]]["passed"] += int(passed)
            cat_totals[case["category"]]["total"] += 1
            run_records.append(run)

        rate = case_passed / runs
        if verbose:
            status = "PASS" if rate == 1.0 else ("FAIL" if rate == 0.0 else "FLAKY")
            line = f"[{status:5}] {case_passed}/{runs:<2}  {case['id']}  ({case['category']})"
            if judge:
                jline = _judge_label(run_records)
                if jline:
                    line += f"  {jline}"
            print(line)
            for run in run_records:
                if not (run["grade"]["passed"] and run["error"] is None):
                    print(f"         -> {run['error'] or graders.failed_reasons(run['grade'])}")
                    break
                jv = run.get("judge")
                if jv and jv.get("passed") is False:
                    print(f"         -> judge: {jv.get('summary', 'below threshold')}")
                    break

        results.append({
            "id": case["id"],
            "category": case["category"],
            "description": case.get("description", ""),
            "messages": case["messages"],
            "runs": run_records,
            "pass_rate": rate,
        })

    return {
        "results": results,
        "cat_totals": cat_totals,
        "judge_scores": judge_scores,
        "total_passed": total_passed,
        "total_runs": total_runs,
        "overall": total_passed / total_runs if total_runs else 0.0,
    }


def _judge_label(run_records):
    """Compact 'judge: g4 t5 c5' label from the first judged run."""
    for run in run_records:
        jv = run.get("judge")
        if jv and jv.get("scores"):
            return "judge: " + " ".join(
                f"{dim[0]}{sc['score']}" for dim, sc in jv["scores"].items()
            )
    return ""


def main():
    parser = argparse.ArgumentParser(description="Run the ShopFlow Agent eval suite.")
    parser.add_argument("--case", help="Run a single case by id")
    parser.add_argument("--category", help="Run only cases in this category")
    parser.add_argument("--runs", type=int, default=1, help="Runs per case (default 1)")
    parser.add_argument("--threshold", type=float, default=0.9,
                        help="Min overall pass rate for exit code 0 (default 0.9)")
    parser.add_argument("--judge", action="store_true",
                        help="Also grade responses with an LLM judge (extra API calls)")
    parser.add_argument("--judge-threshold", type=int, default=4,
                        help="Min judge score (1-5) per dimension to pass (default 4)")
    args = parser.parse_args()

    _require_keys()

    cases = load_cases(args.case, args.category)
    if not cases:
        print("No cases matched the given filters.")
        sys.exit(2)

    print("Bootstrapping agent (building knowledge base, pointing DB at eval copy)...\n")
    seed_fn, agent, state = bootstrap()

    n = len(cases) * args.runs
    judge_note = " + LLM judge" if args.judge else ""
    print(f"Running {len(cases)} case(s) x {args.runs} run(s) = {n} agent conversation(s){judge_note}\n")
    print("=" * 78)

    summary = run_suite(cases, args.runs, agent, state, seed_fn,
                        judge=args.judge, judge_threshold=args.judge_threshold)

    print("=" * 78)

    # ── Summary by category ──────────────────────────────────────────────────
    print("\nBy category:")
    print(f"  {'category':<24} {'pass rate':>10}")
    print(f"  {'-' * 24} {'-' * 10}")
    for cat in sorted(summary["cat_totals"]):
        t = summary["cat_totals"][cat]
        pct = t["passed"] / t["total"] if t["total"] else 0.0
        print(f"  {cat:<24} {t['passed']:>3}/{t['total']:<3} {pct:>6.0%}")

    if args.judge and summary["judge_scores"]:
        print("\nLLM-judge average scores (1-5):")
        for dim in sorted(summary["judge_scores"]):
            scores = summary["judge_scores"][dim]
            avg = sum(scores) / len(scores) if scores else 0.0
            print(f"  {dim:<16} {avg:>4.2f}  (n={len(scores)})")

    overall = summary["overall"]
    tp, tr = summary["total_passed"], summary["total_runs"]
    print(f"\nOverall pass rate: {tp}/{tr} = {overall:.1%}")
    print(f"Threshold: {args.threshold:.0%}  ->  {'PASS' if overall >= args.threshold else 'FAIL'}")

    # ── Save full results ────────────────────────────────────────────────────
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(RESULTS_DIR, f"{stamp}.json")
    payload = {
        "timestamp": datetime.now().isoformat(),
        "runs_per_case": args.runs,
        "threshold": args.threshold,
        "judge": args.judge,
        "overall_pass_rate": overall,
        "by_category": {c: dict(v) for c, v in summary["cat_totals"].items()},
        "cases": summary["results"],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nFull results saved to {out_path}")

    sys.exit(0 if overall >= args.threshold else 1)


if __name__ == "__main__":
    main()
