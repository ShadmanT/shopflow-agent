"""
LLM-as-judge grader.

The deterministic graders in graders.py check *what the agent did* (tools,
arguments, DB state, string matches). This module grades *how well it answered*
on three qualitative dimensions that are hard to assert deterministically:

  * groundedness — every factual claim (order status, amounts, stock, policy)
    is supported by a tool result; nothing invented.
  * tone         — professional and warm, brief empathy, not robotic.
  * conciseness  — solves the problem without rambling; plain prose.

Each is scored 1-5 by Claude against a rubric; a response "passes" the judge if
every dimension is at or above the threshold (default 4). This costs extra API
calls, so it is opt-in (`run_evals.py --judge`).

`parse_scores` is pure and unit-tested offline; `judge_run` makes the API call.
"""
import json
import os
import re

JUDGE_MODEL = "claude-sonnet-4-5"  # same family the agent uses; proven on this account
DIMENSIONS = ("groundedness", "tone", "conciseness")

JUDGE_SYSTEM = (
    "You are a strict QA evaluator for ShopFlow's customer-support agent, Sage. "
    "You grade a single agent response against the data the agent actually had "
    "(the tool calls and their results). Be critical and consistent. "
    "Respond with JSON only — no prose, no code fences."
)

RUBRIC = """Score each dimension from 1 (poor) to 5 (excellent):

groundedness: Is every factual claim in the response — order status, refund
amounts, refund IDs, stock levels, prices, product details, policy statements —
supported by the tool results shown below? Penalize invented order details,
amounts, or policy claims not present in the tool results. If the response makes
no factual claims (e.g. a greeting or a refusal), score 5.

tone: Is it professional and warm, with at most one sentence of empathy, not
robotic or over-apologetic? Appropriate for a possibly-frustrated customer.

conciseness: Does it resolve the issue without rambling, using plain prose
(no markdown headers, bullet lists, or bold)? Penalize padding and repetition.

Return exactly this JSON shape:
{"groundedness": {"score": <1-5>, "reason": "<short>"},
 "tone": {"score": <1-5>, "reason": "<short>"},
 "conciseness": {"score": <1-5>, "reason": "<short>"}}"""

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def _user_turns(case) -> str:
    return "\n".join(
        m["content"] for m in case.get("messages", []) if m.get("role") == "user"
    )


def _tool_log(run, max_result_chars: int = 800) -> str:
    lines = []
    for call in run.get("tool_calls", []):
        result = json.dumps(call.get("result"), ensure_ascii=False)
        if len(result) > max_result_chars:
            result = result[:max_result_chars] + "...(truncated)"
        lines.append(f"- {call['name']}({json.dumps(call.get('input'), ensure_ascii=False)}) -> {result}")
    return "\n".join(lines) if lines else "(no tools were called)"


def build_prompt(case, run) -> str:
    return (
        f"{RUBRIC}\n\n"
        f"--- Customer message(s) ---\n{_user_turns(case)}\n\n"
        f"--- Tools the agent called and what they returned (the ground truth) ---\n"
        f"{_tool_log(run)}\n\n"
        f"--- Agent's final response (grade this) ---\n{run.get('response', '')}\n"
    )


def parse_scores(text: str) -> dict:
    """
    Extract the JSON object and return {dimension: {"score": int, "reason": str}}.
    Pure and deterministic — raises ValueError on malformed input. Unit-tested.
    """
    cleaned = text.strip()
    # Strip ``` / ```json fences if the model added them despite instructions.
    cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object found in judge output: {text[:200]!r}")
    data = json.loads(match.group(0))

    scores = {}
    for dim in DIMENSIONS:
        if dim not in data:
            raise ValueError(f"judge output missing dimension {dim!r}")
        entry = data[dim]
        raw = entry.get("score") if isinstance(entry, dict) else entry
        score = int(raw)
        if not 1 <= score <= 5:
            raise ValueError(f"{dim} score {score} out of range 1-5")
        reason = entry.get("reason", "") if isinstance(entry, dict) else ""
        scores[dim] = {"score": score, "reason": reason}
    return scores


def judge_run(case, run, threshold: int = 4, model: str = JUDGE_MODEL) -> dict:
    """
    Grade one run with the LLM judge. Returns:
      {"scores": {...}, "min_score": int, "passed": bool, "summary": str}
    On an API or parse failure returns {"error": str, "passed": None} so the
    caller can treat it as "not judged" rather than a real failure.
    """
    try:
        resp = _get_client().messages.create(
            model=model,
            max_tokens=600,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": build_prompt(case, run)}],
        )
        text = next((b.text for b in resp.content if hasattr(b, "text")), "")
        scores = parse_scores(text)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "passed": None}

    min_dim = min(scores, key=lambda d: scores[d]["score"])
    min_score = scores[min_dim]["score"]
    return {
        "scores": scores,
        "min_score": min_score,
        "passed": min_score >= threshold,
        "summary": f"{min_dim} {min_score}: {scores[min_dim]['reason']}",
    }
