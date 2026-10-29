"""
RAG retrieval eval.

Separate from the end-to-end agent suite: this grades the *retrieval layer on
its own*. For each query it checks whether the chunk the agent would need is
actually in the top-k retrieved chunks (recall@k) and whether it came from the
expected policy doc. A low score here means the agent can't answer a policy
question no matter how good the prompt is — so it's worth measuring directly.

Cases live in evals/rag_cases.json, grounded in the real backend/docs policies.

Usage:
    python evals/rag_eval.py
    python evals/rag_eval.py --k 3 --threshold 0.9

Needs OPENAI_API_KEY (embeddings). Exits non-zero if recall@k < --threshold.
"""
import argparse
import json
import os
import sys

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(EVAL_DIR, "..", "backend")
RAG_CASES_PATH = os.path.join(EVAL_DIR, "rag_cases.json")

sys.path.insert(0, BACKEND_DIR)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _load_env():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
    load_dotenv(os.path.join(BACKEND_DIR, "..", ".env"))
    load_dotenv()


def grade_case(case, retrieved):
    """
    retrieved: list of {"content", "source", "relevance"} from search_knowledge_base.
    A case is a hit if all expected phrases appear across the retrieved chunks.
    """
    blob = "\n".join(r["content"].lower() for r in retrieved)
    sources = {r["source"] for r in retrieved}
    missing = [p for p in case["expect_contains"] if p.lower() not in blob]
    source_ok = case.get("expect_source") in sources if case.get("expect_source") else True
    return {"hit": not missing, "missing": missing, "source_ok": source_ok,
            "sources": sorted(sources)}


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval recall@k.")
    parser.add_argument("--k", type=int, default=3, help="Top-k chunks to retrieve (default 3)")
    parser.add_argument("--threshold", type=float, default=0.9,
                        help="Min recall@k for exit code 0 (default 0.9)")
    args = parser.parse_args()

    _load_env()
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is required for embeddings (never printed).")
        sys.exit(2)

    from knowledge_base import build_knowledge_base, search_knowledge_base
    print("Building knowledge base...\n")
    build_knowledge_base()

    with open(RAG_CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)

    print(f"Retrieval eval: {len(cases)} queries, k={args.k}\n")
    print("=" * 78)

    hits = source_hits = 0
    for case in cases:
        retrieved = search_knowledge_base(case["query"], n_results=args.k).get("results", [])
        g = grade_case(case, retrieved)
        hits += int(g["hit"])
        source_hits += int(g["source_ok"])
        status = "HIT " if g["hit"] else "MISS"
        print(f"[{status}] {case['query']}")
        if not g["hit"]:
            print(f"        missing {g['missing']} | retrieved from {g['sources']}")
        elif not g["source_ok"]:
            print(f"        (answer found, but not from expected {case['expect_source']}; got {g['sources']})")

    print("=" * 78)
    recall = hits / len(cases) if cases else 0.0
    source_acc = source_hits / len(cases) if cases else 0.0
    print(f"\nRecall@{args.k}:        {hits}/{len(cases)} = {recall:.1%}")
    print(f"Source accuracy:   {source_hits}/{len(cases)} = {source_acc:.1%}")
    print(f"Threshold: {args.threshold:.0%}  ->  {'PASS' if recall >= args.threshold else 'FAIL'}")

    sys.exit(0 if recall >= args.threshold else 1)


if __name__ == "__main__":
    main()
